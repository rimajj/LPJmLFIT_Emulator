---
name: online-coupling-env
description: Build and run the SpeedyWeather.jl + Terrarium.jl online-coupling environment on the PIK cluster (line O, P4) — the working project at /p/tmp/jamirp/esm_online_coupling, its sbatch wrapper, and the nine traps that each cost a failed job or a wrong verdict: Julia 1.10.0 CANNOT precompile these packages (use 1.10.10), SpeedyWeather's EarthOrography DOWNLOADS an artifact inside initialize! so assets must be warmed on the login node, Terrarium state is in °C not Kelvin, and Pkg.status() throws KeyError "Dates", Terrarium's DEFAULT vegetation crashes a coupled run on a VPD=0 assertion, its DEFAULT SOIL is pure sand which SILENTLY deletes all water stress (plant_available_water == 1 everywhere), its DEFAULT hydrology is NoFlow so the soil water NEVER MOVES (any soil-moisture distribution you measure is the initializer, not a model result), and SpeedyWeather's Terrarium adapter DROPS InputSources so prescribed input fields must be passed as `fields`. Use whenever running, debugging or extending the online coupled model, prescribing soil texture or any Terrarium input, adding a Terrarium/SpeedyWeather dependency, writing a Terrarium process (AbstractPhotosynthesis / AbstractVegetation), or hitting a curl RequestError or KeyError from a coupling job. ALSO the COUPLING OF THE LEARNED EMULATOR to SpeedyWeather 0.23 (ADR 0345): scripts/online_coupling/run_speedy_landemu.jl (+ landemu_coupler.py, score_speedy_landemu.py, sbatch_speedy_landemu.sh) — daily weather per land column into LandEmulator.step_day through PythonCall, daily ET back as the land moisture flux via EmulatorLandHumidityFlux, MODE=coupled|control, DIURNAL=flat|sun, the offline replay gate, the water/leap-day accounting, and the PythonCall/0.23 API traps (get_londlatds, truncation = trunc+1, sys.path.insert, JULIA_CONDAPKG_BACKEND=Null). ALSO the ALBEDO / ROUGH / OCEAN=prescribed switches and the emulator land albedo + roughness channels (ADR 0346), diagnose_speedy_climate.py, and WHY SpeedyWeather 0.23 land is ~7 °C too cold (latitude-only grey longwave, free slab ocean; GFDL-ESM4 = W5E5 observations; the orderA vs grid.bin trap on the W5E5 files).
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

## Newer environment + speed numbers (2026-10-16)

- **SpeedyWeather 0.23.0 + Terrarium 0.1.8** live in a SEPARATE project `/p/tmp/jamirp/esm_online_coupling_sw023`
  (setup.jl, warmed T31/T63 assets). The old project above stays on 0.21.1 / 0.1.3. 0.23 changes that matter:
  radiation is one component `model.radiation = Radiation(sw, lw)` (BREAKING), land/ocean/sea ice are Euler-forward
  stepped with their own time steppers, soil temperature + moisture are time stepped, and
  `model.land_sea_mask.mask` is now **`.land_fraction`**. Source clone: `/p/tmp/jamirp/esm_reference_repos/SpeedyWeather.jl`.
- **Measured single-core cost** (`scripts/online_coupling/bench_speedyweather_speed.jl`, job 2516413, AMD EPYC 9554,
  PrimitiveWetModel, default physics, no output): **T31 L8 126 core-s per simulated year (685 SYPD), 912 land
  columns**; **T63 L8 1012 core-s/yr (85 SYPD), 3115 land columns**.
- **POEM 1.2's atmosphere for comparison** (AM2 physics, FV core, 3.75°x3° x 24 levels, hourly step; unpublished,
  builds under `/p/projects/poem/data/tuning-1.2/POEM_PROGRAM/`): its own FMS `Atmosphere` clock is 37 502 s on 20
  ranks per 50 years (`.../POEM_RUNS/0.2/spinup_6layers_maxsnowheight-20m/fms.out-1-28-0-2467238-1801`) =
  **15 000 core-s per simulated year**, ~120x SpeedyWeather T31 L8. Its land (standard LPJmL 5.9 at 0.5°, a C
  library called hourly through `src/land_atlantes/lpj_driver.F90`) is a separate `Land` clock.

## The learned emulator coupled to SpeedyWeather 0.23 (ADR 0345, 2026-10-16)

Direct, NOT through Terrarium (Terrarium is a 300-s process socket; the emulator is daily).
```bash
MODE=coupled DIURNAL=flat YEARS=10 scripts/online_coupling/sbatch_speedy_landemu.sh cpl-coupled-10y   # ~20 min, 1 core
MODE=control YEARS=10 scripts/online_coupling/sbatch_speedy_landemu.sh cpl-control-10y                # same diagnostics, SpeedyWeather's own land ET
PARTITION=priority QOS=priority scripts/sbatch_python.sh cpl-score scripts/online_coupling/score_speedy_landemu.py <coupled_dir> <control_dir>
```
Records go to `/p/projects/open/Jamir/esm_land_emulator_data/coupled/<run>/` (~600 MB per 10-yr coupled run).
* **Wiring:** `PrimitiveWetModel(sg; surface_humidity_flux = SurfaceHumidityFlux(sg; land = EmulatorLandHumidityFlux(sg)))`
  (prescribed flux where `use[ij]`, the bulk `SurfaceLandHumidityFlux` elsewhere) + a callback (`add!(model, :landemu => cb)`,
  called after EVERY step) that sums surface air temperature, `rain_rate + snow_rate`, `surface_shortwave_down`,
  `surface_longwave_down − land.surface_longwave_up`, lowest-level humidity per land column and calls
  `Coupler.day(F)` at each midnight (sample assigned to the day of `time − Δt/2`; 29 Feb folded into 28 Feb).
  SpeedyWeather's `LandBucketTemperature` takes latent heat from `land.surface_humidity_flux`, so energy follows.
* **Gates (score_speedy_landemu.py):** offline replay through `step_year` must be IDENTICAL (it was, 0.0); water
  applied/produced must differ only by the leap days (+0.082 % in 10 yr) and the last day's 1/36 end effect.
* **Python side:** `landemu_coupler.Coupler` = nearest 0.5° emulator cell per column (≤ `MAXDEG` 3°), start from
  `global_emu/emu/historical/chunks/c*_end.npz` (end-of-2014 state), release `global_emu/release/fold_none`.
* **Traps hit (each one cost a job):** `RingGrids.get_londlatds` returns **(lon, lat)** (there is no `get_latdlonds`);
  `SpectralGrid(trunc=31)` is deprecated → `truncation = 32`; Python's path is `pyimport("sys").path.insert(0, dir)`
  (not `pushfirst!`); PythonCall needs `JULIA_CONDAPKG_BACKEND=Null JULIA_PYTHONCALL_EXE=<py311_new python>` (no
  network on nodes) and `OMP_NUM_THREADS=1`. Test the Julia↔Python calls on the LOGIN node with a 20-line script
  (no SpeedyWeather) before spending a 2-min SLURM start on each — that is what finally worked.
* ⚠ **SpeedyWeather's own land is ~7 °C colder than GFDL-ESM4** (control run 10.5 °C over the emulated columns vs
  17.1 °C) — it is the atmosphere, not the coupling (coupled 10.55 °C). The emulator reads it as climate change.
* Measured: emulator 8.8 s per simulated year at T31 (1 197 columns, 7 % of the run); atmosphere ~110–130 s.
* **More channels + climate diagnostics (ADR 0346):** `ALBEDO=emulator` (`EmulatorLandAlbedo`: SpeedyWeather's
  `LandSnowAlbedo` formula fed `Coupler.surface()` = tree cover (fpc1–7), grass cover (fpc8–10), snow water m),
  `ROUGH=emulator` (`EmulatorSurfaceRoughness`, log-blend of `Z0_HIGH/LOW/BARE` = 2.0/0.2/0.013 m),
  `OCEAN=prescribed` (`SeasonalOceanClimatology`; `ThermodynamicSeaIce` then just follows the SST). Every run now also
  writes land albedo, land sensible heat, top soil T, SpeedyWeather snow (`daily_means` columns 8–11, appended so the
  scorer's 0–6 are unchanged), column orography, `global_daily` and `yearly_fields`. Score with
  `diagnose_speedy_climate.py <run_dir>...` (SLURM, 16 cpus, ~5 min: reads 70 years of daily weather).
  Custom components: subtype `SpeedyWeather.AbstractAlbedo` and extend `SpeedyWeather.albedo!(ij, albedo, vars, a, model)`;
  for roughness subtype `AbstractSurfaceRoughness` and extend `surface_roughness!(ij, vars, r, land_sea_mask)` (it is
  called with the MASK, not the model) and define the ONE-argument `initialize!(r)` (`BoundaryLayer` calls that).
  A stepped prognostic (snow, slab SST) is read with `get_prognostic_step(v, SpeedyWeather.time_stepper(model.time_stepping, :land|:ocean), cb)`.
* ⚠ **Why SpeedyWeather 0.23's land is cold (ADR 0346) — check before blaming the coupling or the reference:**
  its defaults are a FREE 50 m slab ocean with no ocean heat transport (drifts +2 K warm, more sea ice), and a
  Frierson grey longwave whose optical depth depends on LATITUDE ONLY (no water vapour, clouds, CO2; clouds act on
  shortwave only). Land air −6.6 °C vs W5E5 with +8–15 W/m² sun and −18–28 W/m² net longwave; top soil 9 K warmer
  than the air. GFDL-ESM4 (ISIMIP3b) equals W5E5 at the cells to 0.01 °C.
* ⚠ **The W5E5 forcing under `.../clustering/global/*_test.clm` is orderA; the emulator's cells and the GFDL-ESM4
  ISIMIP files are grid.bin order.** Indexing one with the other's cell numbers gave "W5E5 9.6 vs GFDL 17.1 °C" — match
  on coordinates (`diagnose_speedy_climate.py::orderA_index`). `input_VERSION2/elevation.bin` is grid.bin order.
* ⚠ `score_speedy_landemu.py`'s "offline" totals sum the WHOLE 0.5° grid, not the emulated cells — not comparable
  with the coupled totals (ADR 0346 §5).

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

## SpeedyWeather cold-bias experiments (stand-alone, no emulator) — 2026-10-21

- **Search upstream first**: SpeedyWeather issues/PRs (#1279, #1283, #1262, #1284, #1332, #1335, #1333) already hold
  most fixes; the maintainers' agent account is `milankl-claude`.
- Branch builds: worktrees of `/p/tmp/jamirp/speedy_main_src` (`git fetch origin pull/<n>/head:pr<n>`; the clone was
  shallow — `git fetch --unshallow` before any merge-base). Durable copies: `patches/speedyweather/*.diff` + README.
  Each worktree needs `RingGrids/Artifacts.toml` copied from `speedy_main_src` (git-ignored; without it
  `initialize!` tries to download orography on the compute node and dies). Env per worktree: copy
  `/p/tmp/jamirp/speedy_armE_env` and `sed` the Manifest paths; a stale registry entry pinning ProgressMeter
  needs `Pkg.update("ProgressMeter")`, not `Pkg.resolve()`.
- Run: `scripts/online_coupling/sbatch_speedy_cold_repro.sh <tag> <env> prescribed|slab <years>` with env knobs
  `LW=fourband|analytic`, `T0=speedy`, `LWKW="name=value,..."` (FourBandLongwave), `CLOUDKW=...` (DiagnosticClouds),
  `LANDREF=/p/projects/open/Jamir/esm_land_emulator_data/coupled/speedy_t31_land_reference_w5e5.csv` (observed
  land at the 1 197 T31 columns; rebuild with `build_speedy_land_reference.py`). ~8 min per 3-yr run, ×3 with
  FourBandLongwave/AnalyticBandLongwave. Table: `summarize_speedy_cold_runs.py logs/speedy-*.out`.
- Read **both** oceans: prescribed SST hides a top-of-atmosphere imbalance (the ocean silently supplies it); a 3-yr
  slab run is not in equilibrium — run 5+ years and read the per-year TOA net.
- SpeedyWeather's `surface_air_temperature` is the lowermost layer (~500 m at L8) brought down the dry adiabat, not
  a 2 m temperature — in winter inversions it is several K warmer than a 2 m observation.
- **Score the atmosphere against a measured profile, not remembered values:** `PROFREF=/p/projects/open/Jamir/
  esm_land_emulator_data/coupled/speedy_profile_reference_gfdl-esm4_1985-2014.csv` (GFDL-ESM4 band-mean T/q/RH on
  pressure levels + column water vapour + cloud cover; rebuild `build_speedy_profile_reference.py` on SLURM, ~2 min)
  makes the reproducer print the tropical profile against it at the model's own layer pressures, plus the
  convective / large-scale precipitation split. No TOA longwave exists in the CMIP6 data on disk.
- **Convection knobs:** `CONVKW="relative_humidity=..,σ_entrainment=..,surface_entrainment=..,ascent_substeps=N,
  entrainment_mse=1"` (last two: branch coldfix-E ≥ 684c181c only). `speedy_convection_diag.jl` (same knobs; raw
  `sbatch --wrap`, ~10 min) recomputes the Betts–Miller internals on tropical columns: deep/shallow fractions, the
  energy shift ΔT, the LZB, and the parcel adiabat vs the environment per layer.
- ⚠ **Before blaming radiation for a warm upper troposphere, compare the environment to the scheme's OWN parcel
  adiabat** (`speedy_convection_diag.jl`): Betts–Miller relaxes the column to it, so if it is warm the column is warm.
  Two defects found that way (JOURNAL 2026-10-21 night): one explicit step per 125-hPa layer with the lower level's
  lapse rate (+2.7 K at σ 0.31, +8.8 K at σ 0.19), and entrainment that mixes T and q then re-saturates without
  evaporative cooling (dry air never cools the parcel). With both fixed (`ascent_substeps=10, entrainment_mse=1,
  σ_entrainment=0`) the tropical 300–550 hPa profile is within 1.5 K of GFDL-ESM4 on both oceans. Lowering the
  target `relative_humidity` dries the column but barely cools it — a humidity knob is not a temperature fix.
- Byte-identity of a new default-off option: rerun the control with the option at its default and `diff` the log
  from `global mean near-surface` on — the scorer prints enough digits to catch any change.
