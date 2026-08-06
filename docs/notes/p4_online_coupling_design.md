# P4 — online coupling to SpeedyWeather: the design of record

**Status 2026-07-28.** The harness is **verified running** on this cluster; our physics is **not in it yet**.
Every API statement below was read out of the installed packages or produced by a job that ran — nothing here
is from memory. Environment recipe + traps: the **`online-coupling-env`** skill. Licensing: closed, reuse
authorized (ADR 0081) — cite, don't analyse.

Versions pinned by the verified run: **Terrarium 0.1.3**, **SpeedyWeather 0.21.1**, **Julia 1.10.10**,
Terrarium clone `4f42508`.

## 1. What plugs into what

**SpeedyWeather owns the adapter.** It ships `SpeedyWeatherTerrariumExt = "Terrarium"` in `[extensions]`,
which provides

```julia
SpeedyWeather.LandModel(::SpectralGrid, ::Terrarium.AbstractModel{NF, <:Terrarium.AbstractLandGrid{NF}})
```

So Terrarium is the **supported land-model socket** for SpeedyWeather, and we write none of the
atmosphere↔land plumbing. That is the entire reason to take Terrarium as a dependency: it buys the grid
bridge, the flux exchange, and a process interface — not physics we lack.

Verified wiring (`scripts/online_coupling/run_reference_coupling.jl`, adapted from Terrarium's
`examples/simulations/speedy_wet_land.jl`):

```
RingGrids.FullGaussianGrid(24) → Speedy.SpectralGrid
                               → ColumnRingGrid(CPU(), Float32, ExponentialSpacing(N=30, Δz_min=0.05))
Terrarium.LandModel(grid; initializer, vegetation, soil)
  → Speedy.LandModel(spectral_grid, tmodel; timestepper = ForwardEuler, Δt = 300.0)
  → Speedy.PrimitiveWetModel(grid; land, surface_heat_flux, surface_humidity_flux, land_sea_mask, time_stepping)
```

H and LE go back to the atmosphere as tendencies via `PrescribedLandHeatFlux` /
`PrescribedLandHumidityFlux`. Terrarium's state lives **inside** SpeedyWeather's variable tree at
`sim.variables.prognostic.land.terrarium`.

**Verified baseline run** (job 1622172, 6 simulated hours, `vegetation = nothing`, 4608 cells):
all cells finite, `eltype === Float32`, T_skin −16.7…25.0 °C (mean 4.0), T_soil_top mean 4.7 °C,
H mean 84.9 W/m², LE mean 10.7 W/m². High H / low LE is expected — `RockyPlanetMask` with no vegetation is
bare ground. **`=== REFERENCE COUPLING OK ===`, exit 0.** This is the control: any later failure is ours.

⚠️ **Terrarium state is in °C, not Kelvin** (`celsius_to_kelvin` is applied only at the Thermodynamics
boundary). Writing a Kelvin plausibility check will fail a perfectly good run — it already did once here.

## 2. The process contract

```julia
variables(::MyProc) = (
    auxiliary(:gross_primary_production, XY(), units = u"kg/m^2/s"),   # recomputed every step
    prognostic(:carbon_vegetation,       XY(), units = u"kg/m^2"),     # integrated by the timestepper
    input(:leaf_area_index,              XY()),                        # supplied by another process
)
compute_auxiliary!(state, grid, p, constants, atmos, soil, args...)
compute_tendencies!(state, grid, p, args...)
```
Cell kernels take `(i, j, grid, fields, …)`; `fields.name[i, j]` reads, `out.name[i, j, 1]` writes;
`launch!(grid, XY, kernel!, out, fields, …)` dispatches. For photosynthesis specifically, implementing
`compute_photosynthesis(i, j, grid, fields, photo, constants, atmos) -> (Rd, An, GPP)` is **sufficient** —
`compute_photosynthesis!` and the `compute_auxiliary_kernel!` are generic over `AbstractPhotosynthesis`.

Coupling variables Terrarium already names, which map onto our `src/interface.jl` structs:
`leaf_area_index`, `gross_primary_production`, `net_primary_production`, `carbon_vegetation`,
`soil_moisture_limiting_factor`, `plant_available_water`, `leaf_to_air_co2_ratio` (their λ),
`skin_temperature`, `sensible_heat_flux`, `latent_heat_flux`, `ground_heat_flux`.

## 3. The central design problem: three timescales

| Component | Native step | Terrarium/Speedy step |
|---|---|---|
| SpeedyWeather dynamics | 15 min (`Δt_at_T31`) | — |
| Terrarium land | **300 s**, `ForwardEuler` | — |
| **F_diff** | **daily** | 288 land steps per F step |
| **S** (demography) | **annual** | 105 120 land steps per S step |

Two clean cases, and we should exploit the easy one first:

- **Rate processes have no mismatch.** Photosynthesis is a flux computed from instantaneous forcing, so an
  LPJmL-FIT photosynthesis kernel can be evaluated every 300 s directly. **This is why the de-risking spike
  is photosynthesis** (§4) — it gets our physics genuinely online without solving the hard problem first.
- **Stateful daily/annual processes need a buffered, piecewise-constant tendency.** F accumulates its
  drivers over a day into a per-cell buffer; on a day boundary it steps once; between boundaries its outputs
  are held constant and its prognostic tendency is held at `daily_total / 86400`. Because `ForwardEuler`
  integrates a constant tendency exactly, the 288 sub-steps sum to precisely the daily total — so **daily
  conservation survives sub-daily integration by construction**, which is the property to assert in the gate.
  S is the same pattern at annual scale, and additionally needs `ClimBuf` to accumulate the running
  climatology online (there is no restart file in a coupled cold start — see §5).

## 4. Next step — the spike: LPJmL-FIT photosynthesis behind `AbstractPhotosynthesis`

Replace Terrarium's `LUEPhotosynthesis` with ours inside their `VegetationCarbon` container, leaving their
stomatal conductance, respiration, phenology, carbon dynamics, soil and SEB untouched. Smallest possible
surface area, and it is exactly the spike `ECOSYSTEM_AND_COUPLING.md` §Immediate-actions names.

```julia
struct FDiffPhotosynthesis{NF} <: Terrarium.AbstractPhotosynthesis{NF}
    photo::LPJmLFITEmulator.FDiff.PhotoParams{NF}
end
```

Ours is `FDiff.photosynthesis(p, λ, tstress, co2_Pa, temp, apar, daylength; comp_vm=true) -> (agd, rd, vm, adtmm)`.

**The unit bridge is the whole difficulty, so state it explicitly.** LPJmL is a **daily** photosynthesis
formulation: `apar` is daily PAR (J/m²/day), `daylength` is hours, and `agd` is gC/m²/**day**. Terrarium wants
`Rd`, `An` in gC/m²/s and `GPP` in kgC/m²/s from *instantaneous* forcing. Evaluate the FIT kernel in
"instantaneous-rate mode": treat the current forcing as if it persisted for a full 24 h, then divide out the
day.

- `apar = swdown · PAR_frac · fapar(LAI) · 86400` (J/m²/day equivalent), `daylength = 24`
- `co2_Pa = co2_ppm · 1e-6 · pres`, `temp` in °C (Terrarium's convention — no conversion)
- `λ` from `fields.leaf_to_air_co2_ratio[i,j]` (their Medlyn scheme), so the spike does not also have to
  own the λ solve
- `Rd = rd/86400`, `An = (agd − rd)/86400`, `GPP = agd/86400 · 1e-3`

This is an **approximation with a real cost**: LPJmL's daily kernel integrates over a photoperiod, so
driving it instantaneously changes the diurnal weighting. It is right for a plumbing spike and **wrong as a
final answer** — the honest end state is the daily-buffered F of §3. Record the discrepancy against the
offline daily F_diff rather than assuming it is small.

*Gate:* the coupled run completes, GPP is finite and positive over vegetated cells, Float32 holds, and the
daily-integrated online GPP is compared against offline F_diff at Hainich with the gap quantified.

## 5. Open items — §5.1/§5.2 are now DECIDED by ADR 0082

> **[ADR 0082](decisions/0082-online-esm-first-ownership-and-validation.md) settled the two big ones**
> (owner decision, 2026-07-28): the ONLINE configuration is **ESM-first, not LPJmL-FIT-faithful**, and is
> validated against **observations** (PLUMBER2/FLUXNET fluxes, observed LAI/biomass/tree-cover), *not* against
> the C binary. **Terrarium owns skin temperature + the SEB and the soil water/thermal column**; our
> contribution online is **vegetation** — S, FIT photosynthesis behind `AbstractPhotosynthesis`, and FIT's
> water-limited ET behind **`AbstractEvapotranspiration`** (a pluggable slot, so LE stays our physics but is
> solved *consistently with T_skin* by Terrarium's implicit solver — which Component E does not do).
> **ClimBuf** cold-starts from a ~20–30 yr SpeedyWeather-only spin-up on **its own** climate, not obsclim.
> The OFFLINE configuration is unchanged and keeps guardrail 3 (C binary is the oracle).
> Conservation (guardrail 2) binds **both**.

- **`ClimBuf` cold start.** A coupled run has no spin-up restart, so the ~20-yr bioclimatic climatology S
  conditions on must be accumulated online (the `climbuf.jl` online transient-boundary work) or seeded from
  an offline climatology and flagged as prescribed. This gates S, not F.
- **Who owns soil water and skin temperature.** Terrarium's `LandModel` carries `soil`,
  `surface_energy_balance` and `surface_hydrology`, and we already have all three (F_diff's bucket,
  Component E). The spike sidesteps this by touching only photosynthesis. Resolving it is a *modelling*
  decision, not a wiring one: either we run as a vegetation module inside Terrarium's land physics, or we
  displace those slots with ours. **Do not let this be decided implicitly** by whichever slot is convenient.
- **Conservation across the interface.** Water ~1e-12, carbon, energy ~1e-14 are CI gates offline; they must
  be re-asserted on the coupled path, where SpeedyWeather owns precipitation and radiation.
- **Gradients.** SpeedyWeather ships `SpeedyWeatherEnzymeExt`, so an end-to-end differentiable coupled
  rollout is plausible — untested here, and not required before O4.
- SpeedyWeather has **no carbon cycle** (a non-issue, ADR 0004: NEE is diagnostic-only), its skin temperature
  is the top-soil-layer T, and its default drag ignores the roughness field.
