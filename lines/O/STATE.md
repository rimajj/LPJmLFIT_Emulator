# LINE O — online coupling: Terrarium + SpeedyWeather (branch `line/O`, worktree `wt-O`) — P4 + P5

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/O/JOURNAL.md` (append-only). Decisions: ADR block **0080–0089**.
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## NEXT — start here

**Licensing is CLOSED (ADR 0081) — reuse Terrarium / SpeedyWeather / LPJmL-FIT / NeuralCrop.jl freely (yes,
NeuralCrop too: CC-BY-NC permits our research use), just cite them (`reuse-citation`).**

**Read `online-coupling-env` (8 traps) + `docs/p4_online_coupling_design.md` + ADR 0082/0083 before touching code.**
Two of those traps are new and both are SILENT: **(7)** SpeedyWeather's Terrarium adapter builds its
integrator with an empty `InputSources`, so a prescribed input `Field` must be passed as
`TerrariumLand.fields` — the documented `InputSource` path is dropped and the variable falls back to its
default; **(8)** `SoilHydrology(NF)` defaults to `NoFlow`, so the soil water never moves and any
soil-moisture distribution you measure is the initializer, not a model result.
Project `/p/tmp/jamirp/esm_online_coupling` · scripts `scripts/online_coupling/`.

**State of play.** `[VERIFIED 2026-07-28]` The coupled harness RUNS (Terrarium 0.1.3 + SpeedyWeather 0.21.1,
Julia **1.10.10**): job 1622172, 6 h, `vegetation=nothing`, 4608/4608 finite, Float32 held, exit 0 — the
CONTROL run. **ADR 0082** set the direction: the ONLINE config is **ESM-first, validated against OBSERVATIONS,
not LPJmL-FIT**; Terrarium owns skin temperature + SEB + soil; we own **vegetation** (S, FIT photosynthesis,
FIT water-limited ET). No LPJmL-FIT physics is online yet.

### O3a — ✅ DONE (2026-08-05, ADR 0083). Do not redo it.

The online soil is a single `PrescribedSoilHorizon(:soil)` carrying the ground-truth run's own soilcode map
× `par/soil_20m.js` texture, SURFEX porosity, behind `assert_nondegenerate_soil`.
Pipeline: `scripts/online_coupling/build_soil_texture_field.py` → `soil_texture.jl::prescribed_texture_soil`.
`[VERIFIED job 1706262]` clay 0.01–0.58 in the model state, `fc − wp` ∈ [0.0519, 0.0893], PAW no longer ≡ 1.

### O3b (DO THIS FIRST) — read job **1706462**, then finish the `soilmoist` comparison

**Nothing measured so far is quotable — both runs are initial-condition artifacts, and they BRACKET the
reference.** LPJmL training reference (historic, 1 348 400 cell-years): min 0.0167, q10 0.220, q25 0.3186,
**q50 0.4635**, q75 0.6644, q90 0.808, max 0.9886, **mean 0.5075**.

| run | flow | days | column | mean PAW (unweighted / top 2 m) |
|---|---|---|---|---|
| 1706262 | `NoFlow` (default) | 2 | 433 m | 0.949 / 0.925 — **the initializer, frozen** (trap 8) |
| 1706324 | `RichardsEq` | 10 | 433 m | 0.104 / 0.225 — **mid-drainage transient**, not spun up |
| **1706462** | `RichardsEq` | 30 | **≈19.5 m** (`DZMAX=2.5`) | ← **read this first** |

Why 1706462 is on the right basis: `ExponentialSpacing(N=30, Δz_min=0.05)` defaults to `Δz_max = 100` =
a **433 m** column, 20× LPJmL's 20 m, so an unweighted 30-layer mean is dominated by deep permanently
saturated layers and is **not the same operator** as `slow.jl`'s unweighted mean over 23 layers / 20 m.
`DZMAX=2.5` ⇒ ≈19.5 m, matching LPJmL, and equilibrating ~20× faster.

```bash
cd /p/tmp/jamirp/esm_online_coupling
tail -40 logs/O-soiltex-rre20m.1706462.out          # `afterok`-free, so a missing result = the job died
TIME=03:00:00 PASS="FLOW=rre DAYS=<n> DZMAX=2.5 TAG=<tag>" ./sbatch_coupling.sh O-<tag> diagnose_soilmoist_shift.jl
```

If 30 days is still draining, **size the spin-up before spending more**: RRE costs ~110 s per simulated day
on the 433 m column (8.3 TiB alloc, 47 % GC over 10 days); the 20 m column should be far cheaper, but a
multi-year spin-up is a real budget item and is now on O3b's critical path.

Map `soilmoist` ← layer-mean **`plant_available_water`**, NOT `saturation_water_ice` (porosity- vs
WHC-normalized = a definitional mismatch, ADR 0082 §4). PAW is computed by calling Terrarium's own
`compute_plant_available_water` on the coupled state — do not re-derive it (guardrail 5).
**Then raise the INTEGRATION POINT with line S**: if the distributions differ materially, S's DRF + copula
must be retrained on Terrarium-derived `soilmoist` as a **version-bumped ONLINE artifact** (never an in-place
mutation — ADR 0029's S→M contract). `slow.jl`/`drf.jl`/`scripts/*slow*` are line S's exclusive paths.

> **⚠ UPDATE from line S, 2026-07-28 — ADR 0035 (S1d) MOVED BOTH SIDES OF THIS COMPARISON. Read before O3b.**
> You reached the same insight we did, independently and on the online side: fraction-of-porosity vs
> fraction-of-WHC is a definitional mismatch, not a calibration offset. Two concrete consequences for O3b:
>
> 1. **The reference numbers quoted above are from the RETIRED table.** `min 0.0167 / q50 0.4635 /
>    q90 0.8080 / mean 0.5075` is exactly `tables/cell_year_soilmoist_hist.parquet` — which we verified is
>    the C **`swc`** output = total water over **SATURATION** capacity (`update_daily.c:411`). That is the
>    porosity-normalized quantity you are deliberately trying NOT to map onto. Calibrating
>    `plant_available_water` against it would reintroduce the mismatch from the offline side.
>    The live reference is `tables/cell_year_soilmoist_ye_hist.parquet` (same 1 348 400 cell-years):
>    **min 0.0000 · q10 0.0000 · q25 0.0000 · q50 0.4980 · q75 0.8770 · q90 0.9999 · max 1.0078 · mean
>    0.4780.** Note the means are close (0.5075 vs 0.4780) while the SHAPE is completely different — a
>    quarter of cell-years now sit at a fully dry root zone. Matching on mean alone would have hidden it.
> 2. **The runtime target changed too, so `slow.jl:191` no longer says what your script's header says.**
>    It is no longer `sum(state.w)/length(state.w)` (an unweighted mean over all 23 layers). It is
>    `root_zone_soilmoist(state, fc.soil)` = the **`whcs`-weighted mean over the top 3 layers (~1 m)**, read
>    at **year end**. Your `FieldCapacityLimitedPAW` choice is still right on the VARIABLE
>    (`min((θw−θwp)/(θfc−θwp), 1)` is exactly LPJmL's `w`) — but to be the same quantity the mapping must
>    also be depth-restricted to ~1 m, capacity-weighted, and sampled at the same instant, not a
>    whole-column annual mean.
>
> Formulas + why `swc` cannot simply be converted: **CLAUDE.md §3** and **ADR 0035**. Nothing here changes
> ADR 0082's decision — it sharpens the target it points at. No action needed from S unless O3b shows the
> Terrarium distribution differs materially from the NEW reference, in which case the version-bumped online
> artifact above is still the right shape; raise it in `lines/S/STATE.md` and S will fold it into the `t8`
> re-derivation that is already queued.

### O3c — the photosynthesis spike (recipe fully worked out in design doc §4)

`FDiffPhotosynthesis{NF} <: Terrarium.AbstractPhotosynthesis{NF}`; implement only `variables(...)` +
`compute_photosynthesis(i,j,grid,fields,photo,constants,atmos) -> (Rd,An,GPP)` (the kernel is generic).
Unit bridge: `daylength=24`, `apar = swdown·PAR_frac·fapar(LAI)·86400`, `co2_Pa = co2_ppm·1e-6·pres`, temp in
**°C**, λ from `fields.leaf_to_air_co2_ratio`; then `Rd=rd/86400`, `An=(agd−rd)/86400`, `GPP=agd/86400·1e-3`.
⚠️ Do **not** enable Terrarium's default `VegetationCarbon` as-is — `MedlynStomatalConductance` asserts
`abs(vpd) > 0` and VPD=0 is physically realizable, so a coupled run crashes (trap 5).

### Then
**O4** FIT water-limited ET behind **`AbstractEvapotranspiration`** (ADR 0082 — this is where our LE physics
belongs, solved consistently with T_skin) · the **ClimBuf two-stage spin-up** on SpeedyWeather's own climate ·
**O5** multi-cell (needs line M's M1/M2) · observed-vegetation datasets (LAI/biomass/tree-cover) are **not on
disk** and are now on the critical path for the online validation claim.

**Worth reporting upstream** (owner is in TUM-PIK-ESM): the VPD≥0 assertion and the degenerate default soil
both make Terrarium's vegetation path unusable out of the box.

## Scope + ownership (ADR 0029)

**You own (exclusive):**
- `ext/SpeedyWeatherTerrariumExt.jl` (or whatever the extension is named) + any new `ext/` file — and `ext/`
  generally (`CLAUDE.md` §9: "`ext/` to O"), which includes the existing `ext/FDiffTrainingExt.jl`
- `docs/p4_online_coupling_design.md` (**written 2026-07-28** — the design of record; keep it current)
- `scripts/online_coupling/*` (the verified SpeedyWeather+Terrarium harness)
- `docs/third_party_licensing.md` (the reuse + **citation** register; keep it current — ADR 0081)
- `lines/O/*`, `changelog.d/O-*.md`, ADRs 0080–0089

**Do NOT touch:** `src/components/slow.jl`, `src/drf.jl`, `src/climbuf.jl` (line S) ·
`src/components/energy.jl` (line E) · `src/run.jl`, `src/interface.jl` (line M — **you consume these
read-only**) · `Project.toml` (integrator — request a weakdep as an integration point).
Shared, additive-only: `src/LPJmLFITEmulator.jl` (inside `# ── line O ──`), `CLAUDE.md`, `MEMORY.md`.

**SLURM tag prefix:** `O-` · other lines' `/p/tmp` artifacts are **read-only**.

## What already exists (read this before designing anything)

- **Reference clones** at `/p/tmp/jamirp/esm_reference_repos/` (read-only, cloned 2026-07-16):
  - `Terrarium.jl/` — the coupling substrate. 61 `Abstract*` types, including all 8 vegetation interfaces
    (`AbstractPhotosynthesis`, `AbstractStomatalConductance`, `AbstractAutotrophicRespiration`,
    `AbstractPhenology`, `AbstractVegetationCarbonDynamics`, `AbstractVegetationDynamics`,
    `AbstractRootDistribution`, `AbstractPlantAvailableWater`) plus `AbstractSurfaceEnergyBalance` /
    `AbstractSkinTemperature` / `AbstractEnergyClosure` / `AbstractAerodynamics` / `AbstractTurbulentFluxes`.
    Depends on `SpeedyWeatherInternals`. Docs under `docs/extending/{core_interfaces,implementing_processes,
    coupling_processes,state_variables}.md`.
  - **The templates that matter: `Terrarium.jl/examples/simulations/speedy_{dry,wet}_land.jl`** — working
    end-to-end SpeedyWeather↔Terrarium coupling. `speedy_wet_land.jl` builds
    `RingGrids.FullGaussianGrid` → `Speedy.SpectralGrid` → `ColumnRingGrid` → `Terrarium.LandModel(grid;
    initializer, vegetation=nothing, soil)` → `Speedy.LandModel(spectral_grid, terrarium_model; timestepper,
    Δt)` → `Speedy.PrimitiveWetModel(...; land, surface_heat_flux=…PrescribedLandHeatFlux(), …)`.
    **`vegetation = nothing` is exactly the slot this project's S+F fill** — and it is unexercised in the template.
  - `LPJmL-hybrid-photosynthesis/` (TUM-PIK-ESM — reuse already done for differentiable λ);
    `NeuralCrop.jl/` (**method only — cite the paper, do not copy code**).
  - **SpeedyWeather.jl itself is NOT cloned** — clone it read-only if needed (login node has network; compute
    nodes do not).
- **The repo side of the contract is frozen and ready:** `src/interface.jl` (`SToF`, `SToE`, `FToS`, `FToE`,
  `EToF`, `EToATM`, `AtmForcing` with units) + `DESIGN.md` §8 + `DEVELOPMENT_PLAN.md` §2.5.
- **The plan of record:** `ECOSYSTEM_AND_COUPLING.md` §2/§3/§5 — **indirect coupling first** (share
  `leaf_area_index`, `gross_primary_production`, `plant_available_water`, `carbon_vegetation`,
  `ground_temperature`), then `SpeedyWeather.LandModel(spectral_grid, external_model)`;
  `PrescribedLandHeatFlux`/`PrescribedLandHumidityFlux` inject H/LE as atmospheric tendencies; multi-cell via
  `ColumnRingGrid` on a RingGrid. §Immediate-actions names the de-risking spike: *"implement one LPJmL-FIT
  process behind a Terrarium `Abstract*` interface, indirectly coupled"*.
- **Float32 readiness is already gated** — 4 testitems assert Float32 type-stability explicitly labelled
  *"(SpeedyWeather-coupling type)"*; that is the only P4 preparation that exists in code today.
- Known caveats to design around: SpeedyWeather has **no carbon cycle** (NEE is diagnostic-only — a non-issue
  per ADR 0004), its skin temperature is currently the top-soil-layer T, and its default drag ignores the
  roughness field.

## Status (2026-07-28)

**P5 is DONE + CLOSED (ADR 0080 + 0081); P4 has zero code.** `ext/` contains only `FDiffTrainingExt.jl`; every
`SpeedyWeather` / `Terrarium` hit in `src/`+`test/` is a comment or a test name. `MEMORY.md` phase table:
**6 Online / SpeedyWeather = ⬜ not started**, **7 ESM packaging = ⬜ not started**. There is still **no P4
design doc** — P4 is scoped only in prose across `ECOSYSTEM_AND_COUPLING.md`, `DEVELOPMENT_PLAN.md` §6 and
`STEERING_PROMPT.md`. What changed on 2026-07-28: the owner CLOSED licensing (ADR 0081 — he is in both
the LPJmL-FIT and TUM-PIK-ESM groups) ⇒ reuse is authorized outright and nothing gates P4 any more.

## Milestones

- **O1** ✅ **DONE + CLOSED (2026-07-28)** — the **P5 licensing ADR** ([0080](../../docs/decisions/0080-licensing-basis.md)):
  AGPL-3.0-or-later outbound (*forced* — LPJmL-FIT copyleft ∧ EUPL-1.2 Appendix), EUPL works consumed as
  **library dependencies only**, never vendored; READ/DEPEND/VENDOR separated; NeuralCrop method-only.
  Register + gate: `docs/third_party_licensing.md` + the `dependency-license-gate` skill. ADR 0017 annotated,
  not superseded. Then **ADR 0081 — the owner CLOSED the topic**: he is in both the LPJmL-FIT and TUM-PIK-ESM groups ⇒
  reuse authorized, no residual, obligation = transparent citation only. **Do not reopen.**
- **O2** **Write `docs/p4_online_coupling_design.md`** — the missing design of record: which Terrarium
  `Abstract*` interfaces S/F/E sit behind, the indirect-coupling variable list, the sub-cycling/timestep story
  (F is daily; SpeedyWeather steps ~300 s), Float32 throughout, how `ClimBuf` gets its spin-up climatology on a
  cold start, and the conservation story across the interface. Validate the design **against the real API** in
  the cloned Terrarium, not from memory.
- **O3** **The de-risking spike**: ONE LPJmL-FIT process behind ONE Terrarium `Abstract*` interface, indirectly
  coupled — no new science, no new data. Ships as a package **extension** (weakdeps), runtime `[deps]` stays
  empty. *Gate:* it runs inside a Terrarium `LandModel` and reproduces the standalone F_diff result for that
  process.
- **O4** **Wrap the existing single-cell `run_coupled_cell` as a SpeedyWeather `LandModel`** using
  `speedy_wet_land.jl` as the template, filling the `vegetation` slot. *Gate:* a short single-column coupled
  run completes, conserves, and stays Float32-stable.
- **O5** **Multi-cell online** — **needs line M's M1/M2** (per-cell inputs + the coupled multi-cell harness).
  The true P4 gate: a stable **multi-year free run** — no drift, no oscillation / AC-gap — conserving, with
  gradients still flowing; plus OOD warming at constant CO₂.
- **O6** (P7, optional) ESM packaging: the documented external-land interface + sub-daily outputs.

## Line-local gotchas

- **Runtime `[deps]` MUST stay empty (ADR 0014)** — Terrarium/SpeedyWeather are `[weakdeps]` + an extension,
  requested from the integrator. Aqua enforces no stale deps.
- **Compute nodes have NO GitHub egress** (pkg-server tarballs only) and GitHub HTTPS is blocked everywhere —
  clone/instantiate on the **login node** to warm the shared depot, then run.
- Terrarium is **v0.1.x / unstable API** (one of ADR 0017's two reasons for not depending on it for E). Pin a
  commit in the design doc and expect churn.
- Don't reintroduce a Terrarium dependency for **component E** — ADR 0017 decided E stays self-contained; this
  line couples *through* Terrarium, it does not replace E's physics. ADR 0017 stands on its **technical**
  drivers (zero runtime `[deps]` / offline nodes; v0.1.x churn), which the licensing close does not touch.
- **Do not raise licensing (ADR 0081).** Reuse of Terrarium / SpeedyWeather / LPJmL-FIT is authorized by the
  owner's membership of both groups. Cite it (`reuse-citation`) and move on.
- Any long job → SLURM; the login node is hook-blocked for heavy Julia.
