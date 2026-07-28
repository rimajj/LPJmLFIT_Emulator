---
name: online-coupling-env
description: Build and run the SpeedyWeather.jl + Terrarium.jl online-coupling environment on the PIK cluster (line O, P4) — the working project at /p/tmp/jamirp/esm_online_coupling, its sbatch wrapper, and the six traps that each cost a failed job: Julia 1.10.0 CANNOT precompile these packages (use 1.10.10), SpeedyWeather's EarthOrography DOWNLOADS an artifact inside initialize! so assets must be warmed on the login node, Terrarium state is in °C not Kelvin, and Pkg.status() throws KeyError "Dates", Terrarium's DEFAULT vegetation crashes a coupled run on a VPD=0 assertion, and its DEFAULT SOIL is pure sand which SILENTLY deletes all water stress (plant_available_water == 1 everywhere). Use whenever running, debugging or extending the online coupled model, adding a Terrarium/SpeedyWeather dependency, writing a Terrarium process (AbstractPhotosynthesis / AbstractVegetation), or hitting a curl RequestError or KeyError from a coupling job.
---

# online-coupling-env — SpeedyWeather + Terrarium on this cluster

**Working project: `/p/tmp/jamirp/esm_online_coupling/`** (on shared `/p`, so SLURM can read it).
Verified 2026-07-28: Terrarium **0.1.3** + SpeedyWeather **0.21.1** + `LPJmLFITEmulator` load together,
272 deps precompile clean, and the upstream coupled model runs on a compute node.

```bash
cd /p/tmp/jamirp/esm_online_coupling
./sbatch_coupling.sh <O-tag> <script.jl>      # -> logs/<tag>.<jobid>.out on shared /p
```

## The six traps (each one cost a failed job)

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
