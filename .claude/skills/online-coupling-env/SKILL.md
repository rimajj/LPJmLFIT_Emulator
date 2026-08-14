---
name: online-coupling-env
description: Build and run the SpeedyWeather.jl + Terrarium.jl online-coupling environment on the PIK cluster (line O, P4) — the working project at /p/tmp/jamirp/esm_online_coupling, its sbatch wrapper, and the nine traps that each cost a failed job or a wrong verdict: Julia 1.10.0 CANNOT precompile these packages (use 1.10.10), SpeedyWeather's EarthOrography DOWNLOADS an artifact inside initialize! so assets must be warmed on the login node, Terrarium state is in °C not Kelvin, and Pkg.status() throws KeyError "Dates", Terrarium's DEFAULT vegetation crashes a coupled run on a VPD=0 assertion, its DEFAULT SOIL is pure sand which SILENTLY deletes all water stress (plant_available_water == 1 everywhere), its DEFAULT hydrology is NoFlow so the soil water NEVER MOVES (any soil-moisture distribution you measure is the initializer, not a model result), and SpeedyWeather's Terrarium adapter DROPS InputSources so prescribed input fields must be passed as `fields`. Use whenever running, debugging or extending the online coupled model, prescribing soil texture or any Terrarium input, adding a Terrarium/SpeedyWeather dependency, writing a Terrarium process (AbstractPhotosynthesis / AbstractVegetation), or hitting a curl RequestError or KeyError from a coupling job.
---

# online-coupling-env — SpeedyWeather + Terrarium on this cluster

**Working project: `/p/tmp/jamirp/esm_online_coupling/`** (on shared `/p`, so SLURM can read it).
Verified 2026-07-28: Terrarium **0.1.3** + SpeedyWeather **0.21.1** + `LPJmLFITEmulator` load together,
272 deps precompile clean, and the upstream coupled model runs on a compute node.

```bash
cd /p/tmp/jamirp/esm_online_coupling
./sbatch_coupling.sh <O-tag> <script.jl>      # -> logs/<tag>.<jobid>.out on shared /p
```

## The nine traps (each one cost a failed job, or a wrong verdict)

1. **Julia 1.10.0 CANNOT build this stack — use `/p/system/packages_rhel9/tools/julia/1.10.10/bin/julia`.**
   On 1.10.0, Pkg's extension resolution dies with `KeyError: key "KernelAbstractions" not found`
   precompiling RingGrids / SpeedyWeather / Terrarium (and `KeyError: key "GPUArraysCore"` for Terrarium).
   1.10.10 precompiles all 272 deps in ~81 s. This is a Pkg bug, not a compat bound — every package
   declares `julia = "1.10"`.
2. **`SpeedyWeather.EarthOrography` DOWNLOADS an artifact inside `initialize!`.** `RingGrids.get_asset` →
   `Pkg.Artifacts.create_artifact` → `Downloads.download`. Compute nodes have **no outbound network**, so a
   job dies with a curl `RequestError` deep inside `Speedy.initialize!`. **Fix: warm assets on the LOGIN
   node once** — `julia --project=. warm_assets.jl` builds the same model and calls `initialize!`, caching
   the artifact in `~/.julia/artifacts`. Add a truncation to the loop in that script if a run needs a grid
   the cache has never seen. This is the *asset* analogue of the Pkg depot warm in `CLAUDE.md` §2.
3. **Terrarium state is in °C, NOT Kelvin.** `celsius_to_kelvin` is applied only at the Thermodynamics
   boundary (`processes/thermodynamics/thermodynamics.jl:34`), so `skin_temperature`, `temperature`, air
   temperature etc. are all Celsius. A plausibility assertion written for Kelvin fails on a *good* run.
4. **Never call `Pkg.status()` in a setup script here** — it throws `KeyError: key "Dates" not found` from
   `print_status` when the project has a dev'd package carrying `[weakdeps]` (ours does), aborting the
   script before `Pkg.precompile()`.
5. **Terrarium's DEFAULT vegetation is not coupled-run-robust.** Switching
   `vegetation = VegetationCarbon(NF)` on (instead of the template's `nothing`) crashes a coupled run with
   `AssertionError: vapor pressure deficit must be greater than zero` — `MedlynStomatalConductance`
   hard-asserts `abs(vpd) > 0` (`medlyn_stomatal_conductance.jl:51`), and **VPD = 0 is physically realizable**
   in a coupled atmosphere (saturated air, fog, night-time dew). `[VERIFIED 2026-07-28, job 1622826.]` That
   slot is genuinely unexercised upstream, so expect to harden anything you put in it — and this one is worth
   reporting to the Terrarium maintainers. Workaround for diagnostics: run `vegetation = nothing` and
   reconstruct vegetation-side quantities post-hoc from the soil state using Terrarium's own property
   functions (`scripts/online_coupling/diagnose_soilmoist_shift.jl` does exactly this for
   plant-available water).

6. **⚠️ THE WORST ONE — Terrarium's DEFAULT SOIL silently deletes water stress.** `ConstantSoilHorizon`
   defaults to `texture = SoilTexture(NF)` = **`sand=1.0, clay=0.0`**, and `SoilHydraulicsSURFEX` computes
   `wilting_point = 37.13e-3*sqrt(clay*100)` and `field_capacity = 89.0e-3*(clay*100)^0.35` — **both exactly
   ZERO when `clay = 0`**. So
   `plant_available_water = max(min(1, (θw−θwp)/(θfc−θwp)), 0) ≡ 1.0` wherever θw > 0.
   **It does not error — it reports "fully unstressed everywhere",** deleting the drought response while
   looking entirely plausible, and it silently feeds Terrarium's own `soil_moisture_limiting_factor` →
   photosynthesis chain. `[VERIFIED 2026-07-28, job 1622830.]`
   **Fix: prescribe a real clay fraction + porosity** via `PrescribedSoilHorizon` (`TerrariumRastersExt` reads
   raster maps), and **add a guard rejecting any soil config with `field_capacity <= wilting_point`** so this
   class of degeneracy fails loudly. **No online run with default soil may be used to judge vegetation.**
   Done: `scripts/online_coupling/build_soil_texture_field.py` (LPJmL soilcode × `par/soil_20m.js` texture,
   orderA) → `soil_texture.jl::prescribed_texture_soil` (+ `assert_nondegenerate_soil`), ADR 0083.

7. **A prescribed input `Field` must be passed as `fields`, NOT `inputs`, under SpeedyWeather.**
   `SpeedyWeatherTerrariumExt.timestep!`/`initialize!` construct their `ModelIntegrator` with an
   **empty `InputSources(NF)`** — deliberately, so the adapter's own `set!` of the atmospheric forcings
   is not overwritten. Consequence: the `InputSource`-based prescription used by Terrarium's own
   `examples/simulations/soil_heat_global_soilgrids.jl` is **silently dropped** in a coupled run, and the
   input falls back to its declared `default` (for `PrescribedSoilHorizon`, `sand_fraction = 1` — i.e.
   straight back into trap 6). Only `TerrariumLand.fields` is forwarded, via
   `Terrarium.initialize(...; fields)` → `StateVariables`, which resolves `ns_fields = get(fields,
   varname(ns), (;))` per namespace. So for a horizon named `:soil`:
   ```julia
   Speedy.LandModel(spectral_grid, tmodel; timestepper, Δt,
       fields = (soil = (sand_fraction = fs, silt_fraction = fi, clay_fraction = fc),))
   ```
   and then **assert it arrived** — read `state.soil.clay_fraction` back and check it is non-zero *and*
   spatially varying. A silently-dropped prescription looks exactly like a working one.

8. **Terrarium's DEFAULT hydrology is `NoFlow` — the soil water NEVER MOVES.**
   `SoilHydrology(NF)` defaults to `vertical_flow = NoFlow()`, so `saturation_water_ice` stays at whatever
   `SoilInitializer`'s `SaturationWaterTable` wrote (vadose zone 0.75, saturated below 5 m) forever — and
   *identically in every column* — even though the adapter faithfully pushes `rainfall`/`snowfall` into the
   Terrarium inputs each step. `[VERIFIED 2026-08-05, job 1706262: layer-mean saturation min == max ==
   0.8917 over all 4608 columns after 2 coupled days.]` Any soil-moisture distribution measured this way is
   the **initializer**, not a model result — and PAW then varies only through texture. Use
   `SoilHydrology(NF; vertical_flow = RichardsEq())` for anything hydrological.
   `RichardsEq` is verified to work coupled (`[VERIFIED 2026-08-05, job 1706324, exit 0]`, 10 days,
   4608×30) but costs **~110 s per simulated day** and allocated 8.3 TiB with 47 % GC time — budget the
   spin-up before promising a distribution.
   **And fix the column depth while you are there:** `ExponentialSpacing(N=30, Δz_min=0.05)` defaults to
   `Δz_max = 100`, giving a **433 m** column — 20× LPJmL's 20 m — so an unweighted layer mean is dominated
   by deep, permanently saturated layers and is *not* the same operator as `slow.jl`'s unweighted mean over
   23 layers. Pass `Δz_max = 2.5` for ≈19.5 m (matches LPJmL, equilibrates ~20× faster), or compare on a
   thickness-weighted root-zone basis. **A run started near saturation is still draining after 10 days** —
   a transient is not a spin-up. Two independent spin-ups are in play and **both dry the soil**, so they
   cannot be told apart from a genuinely drier equilibrium by inspection: the soil column draining, *and*
   **SpeedyWeather's own precipitation climatology establishing from its default initial state**. The only
   honest test is to run two lengths (e.g. 30 d and 90 d) and check the distribution has **stopped moving**
   before quoting it — ⚠ **but that check is NOT SUFFICIENT ON ITS OWN; see trap 9. A clipped diagnostic
   stops moving whether or not the physics converged, and reading "stopped moving" as "converged" is exactly
   how O3b nearly reported a bogus training mismatch to line S.** Shrinking the column does *not* buy speed: `[VERIFIED 2026-08-05, job 1706597]` the
   19.5 m column still costs **~99 s per simulated day** (25 TiB allocated, 47 % GC over 30 days) — the RRE
   path is allocation-bound, not depth-bound, so budget ~10 h per simulated year regardless of `Δz_max`.

9. **`plant_available_water` is CLIPPED AT BOTH ENDS, so a vegetation-free run reports a 10-level STEP
   FUNCTION and it looks exactly like a converged distribution.** `FieldCapacityLimitedPAW` is
   `W = min(max((θw−θwp)/(θfc−θwp), 0), 1)`: a layer at or above field capacity reports exactly `1.0`, one at
   or below wilting point exactly `0.0`, **regardless of how much water is actually there**. So when every
   root-zone layer sits at a clamp, the thickness-weighted root-zone mean can only take the `nlayer+1` values
   of the cumulative-thickness ladder `ladder[m] = (Σ top m thicknesses)/(total)` — one per wetting-front
   position. `[VERIFIED 2026-08-14, jobs 1706597 + 1706979, ADR 0085]` **94.0 % of the 1987 land columns lie
   exactly on that ladder** (|Δ| < 1e-5), 90 % on just **four** front positions, 47.9 % bone dry, **90.8 %
   bit-identical across 60 extra simulated days**, whole-column saturation +0.070 %. The 30 d and 90 d
   quantiles agreed to **four significant figures** — which trap 8's two-lengths rule reads as "converged".
   It was not; the diagnostic was saturated.
   **Why it happens: `vegetation = nothing` (forced by trap 5) removes transpiration, and transpiration is
   the process that POPULATES the informative `(θwp, θfc)` band** — the only other sinks are top-layer
   evaporation and gravity drainage, which drive layers *to* the clamps. Compounded by a narrow SURFEX window
   (`fc − wp ∈ [0.052, 0.089]` volumetric ⇒ a layer crosses the whole informative range on ~7 % water
   change). The dominant levels match the ladder measured **from the surface down**, i.e. a *stalled
   infiltration front*, not drying from above.
   **Always run the check before quoting any PAW distribution** (post-hoc, no simulation, ~1 s):
   ```bash
   python3 scripts/online_coupling/diagnose_paw_clamping.py \
       /p/tmp/jamirp/esm_online_coupling/terrarium_soilmoist_candidates_{A,B}.csv   # exit 1 = CLAMPED
   ```
   **A `CLAMPED` verdict means the comparison is VOID, not that the model is dry** — do not score those
   quantiles against LPJmL's `soilmoist_ye` and do not report a train/inference shift to line S. The
   generalisation, now in `residual-diagnosis`: checking the *reference* basis is not enough, **also confirm
   the measured quantity is not saturated at its own clamps** — no statistic computed on a clipped field can
   tell the two apart, only the structural ladder test or a cross-run bit-identity count.

## The coupling architecture (verified from source, not docs)

- **SpeedyWeather owns the adapter**: it ships `SpeedyWeatherTerrariumExt = "Terrarium"` in `[extensions]`,
  providing `SpeedyWeather.LandModel(::SpectralGrid, ::Terrarium.AbstractModel{NF,<:AbstractLandGrid{NF}})`.
  So Terrarium is the *supported* land-model socket; we do not write the SpeedyWeather plumbing.
- Wiring (from `Terrarium.jl/examples/simulations/speedy_wet_land.jl`):
  `RingGrids.FullGaussianGrid` → `Speedy.SpectralGrid` → `ColumnRingGrid` →
  `Terrarium.LandModel(grid; initializer, vegetation, soil)` → `Speedy.LandModel(spectral_grid, tmodel;
  timestepper=ForwardEuler, Δt=300.0)` → `Speedy.PrimitiveWetModel(...; land, surface_heat_flux =
  SurfaceHeatFlux(..., land=PrescribedLandHeatFlux()), ...)`.
- Terrarium state lives **inside** SpeedyWeather's tree: `sim.variables.prognostic.land.terrarium`
  (`.skin_temperature`, `.sensible_heat_flux`, `.latent_heat_flux`, `.temperature`, …). Read with
  `Array(interior(f)[:, 1])`. `Terrarium.checkfinite!(ls.prognostic)` is the built-in sanity check.
- Strip `CUDA` / `Rasters` / `NCDatasets` / `CairoMakie` / `GeoMakie` from upstream examples — headless
  compute node, no GPU, no plotting. Assert on numbers instead.

## Writing a Terrarium process (the contract)

```julia
struct MyProc{NF} <: Terrarium.AbstractPhotosynthesis{NF} ... end
variables(::MyProc) = (
    auxiliary(:gross_primary_production, XY(), units = u"kg/m^2/s"),
    prognostic(:carbon_vegetation,       XY(), units = u"kg/m^2"),
    input(:leaf_area_index,              XY()),          # consumed from another process
)
# photosynthesis: return (Rd, An, GPP); the generic kernel + compute_photosynthesis! come for free
compute_photosynthesis(i, j, grid, fields, p::MyProc, constants::PhysicalConstants, atmos) = (Rd, An, GPP)
```
`auxiliary` = recomputed each step · `prognostic` = integrated by the timestepper · `input` = supplied
elsewhere. Cell kernels take `(i, j, grid, fields, ...)`; `launch!(grid, XY, kernel!, out, fields, ...)`.
Field access is `fields.name[i, j]`; outputs go to `out.name[i, j, 1]`.

**The timestep mismatch to design around:** Terrarium steps at **Δt = 300 s** under `ForwardEuler`, our F is
**daily** and S is **annual**. A *rate* process (photosynthesis) has no mismatch — compute it from
instantaneous forcing. Anything with daily/annual state must buffer forcing and hold a **piecewise-constant
tendency** over the interval, which ForwardEuler then integrates to exactly the daily total (conserving).
