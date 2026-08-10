# LINE O — online coupling: Terrarium + SpeedyWeather (branch `line/O`, worktree `wt-O`) — P4 + P5

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/O/JOURNAL.md` (append-only). Decisions: ADR block **0080–0089**.
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## NEXT — start here

### 0☆ ⛳ THE PROGRAM CHANGED — `EXECUTION_PLAN.md` IS NOW THE ORDER OF WORK (owner-approved 2026-08-07; ADR 0093 + 0094)

**Read `EXECUTION_PLAN.md` before planning anything.** The project now runs as a strict **error-attribution
ladder**, because offline Component S (98.2 % of count variance) and the coupled driver (terminal density
0.52–1.38×) were being measured together and ADR 0105 proved they cannot be one error — *"offline bias predicts
the coupled error with the wrong size in every cell and the wrong sign in two."* **Do not climb two rungs at
once. Do not report a coupled score without the isolated ones beside it.**

Two owner decisions re-rank everything:

* **ADR 0094 — per-year ESM speed is now goal #2, ahead of everything except fidelity.** The spin-up saving is
  explicitly *not* the goal (*"boring and not my main goal"*). ⚠ And the measurement that forced it: **the
  shipped Julia emulator is 3.8× SLOWER per cell-year than the C model it replaces** (1.096 vs 0.290–0.383
  core-s), because its per-individual daily step costs **51×** the C's. **Never claim "faster than LPJmL-FIT"
  without a measured end-to-end number that names the atmosphere it is against.**
* **ADR 0093 — the patch ensemble is NOT the bottleneck.** The ~100× decomposes as **37× single-core
  engineering + ~3× patches**. Price every speed proposal against the **Julia** cost model, never the C's:
  four candidate architectures looked good against the C and are all slower than the existing code at 8 patches.

Three things that change how you score anything (skill `residual-diagnosis` §5):

1. **At the production `npatch=25` the C's own answer is already outside the 10 % band** — bootstrap CV `vegc`
   11.3 %, median Height 11.3 %, median minwscal 11.0 %, **median D95max 22.7 %**; in the <2 stems/patch
   stratum (7 964 cells) 31.6 % on counts and 42.7 % on carbon. ADR 0106's `max(10 %, the two-run spread)`
   branch is load-bearing. **Quote a noise floor with every fidelity number.**
2. **The 25 patches are worth `n_eff` 4.8–12.9**, not 25, because the cell-level seedbank couples the
   *inherited* trait pool. The control that proves it: median **Height** — same stems, not inherited — is
   `n_eff ≈ 25`.
3. **The per-cell trait response is not an observable in single-seed truth** (the two seeds disagree on the
   *sign* in 33–37 % of cells). Score responses on a multi-seed mean and **deattenuate**: doing so shows
   **two** broken axes, not four — SLA `0.851→1.08` and minwscal `0.689→0.99` are already correct; only
   Wooddens (0.63) and D95max (0.51) are broken. **Stop writing "four broken axes".**

**Refuted, do not re-propose** (ADR 0093 §4, with numbers): one big patch · structural stratification/quadrature ·
time-averaging instead of ensemble-averaging · a smooth trait density with no individuals · a roster ensemble
without daily physics.

#### YOUR ASSIGNMENT — **rung 5 (speed) is YOURS, and it is now goal #2. Start 5-pre TODAY.**

ADR 0094 makes per-cell-year ESM speed a first-class deliverable. The gate, from `EXECUTION_PLAN.md` §0:

| | core-s per cell-year, full coupled S+F+E |
|---|---|
| today, 25 patches (MEASURED) | 1.096 |
| the C it replaces (MEASURED) | 0.290–0.383 |
| **T63-class intermediate milestone** | **≤ 0.030** (37× from today) |
| **T31-class target** | **≤ 0.0135** (81×) |

⚠ Both allowances are a **convention** (10 % of a measured SpeedyWeather coupled cost), not an owner-set
budget — say so whenever you quote them, and always name the atmosphere.

**5-pre — THE TIMING GATE. Start now; nothing blocks it.** No end-to-end emulator-vs-C timing has ever
existed, which is exactly how a **3.8× regression** went unnoticed across ~40 sessions. Deliver a reproducible
harness reporting core-s per cell-year for the emulator **and** for the C on the same cells and years, plus a
profile attributing the emulator's cost. Starting point:
`/p/tmp/jamirp/npatch_analysis/bench_emulator.jl`. Then raise an **integration point** so the integrator wires
it as a required CI gate (workflows are integrator-owned) — a performance regression should red CI like a
physics one.

**5a — close the per-tree gap: 37×, ZERO fidelity risk.** The Julia per-individual daily step costs **51×**
the C's (3.998e-3 vs 7.84e-5 core-s per individual-year) while the per-patch fixed cost is only **0.066×**
(3.3e-4 vs 5.0e-3). Closing it alone takes 25 patches from 1.096 → **0.0296**; 8 patches then lands at
**0.0093**, inside the T31 allowance with 45 % margin. In the C, 72–86 % of runtime is per-individual per-day
photosynthesis and the λ bisection alone is **33.3 %** (≤30 photosynthesis calls per tree per day,
`water_stressed.c:207`) — a fixed-iteration or analytic λ closure is the first place to look, and the
gradient-friendly core wants it anyway. **It must come out byte-identical against the committed baselines** —
it is the same computation, faster.

🚫 **DO NOT EDIT `src/fdiff.jl` / `fdiff_smoothops.jl` / `components/fast.jl` until line M clears rung 4 or
records a hand-over** (CLAUDE.md §9 Gap 1 — M owns the F core). The collision is a git conflict in a 2 000-line
physics file, not a scientific one, so **profile and write the optimisation plan now, land the edits after.**

**5d threads across cells** (54 020 cells are embarrassingly parallel) then **5e GPU — deliberately LAST.**
Why last, so it is not relitigated: threads already saturate a CPU node; the 51× gap is single-core
inefficiency and a GPU running inefficient code is still inefficient; and the workload fits badly — variable
roster length per patch, a per-tree branching death test, and an iterative λ solve with a data-dependent trip
count all cause lane divergence. Re-ask with measured numbers after 5a and 5d.

**Then rung 6, the ESM coupling** — your existing remit, unchanged.

---


### 0★ 🎯 THE ACCEPTANCE CRITERION CHANGED — READ THIS BEFORE PLANNING ANYTHING (owner, 2026-08-06; ADR 0106)

The owner has stated what **finished** means, and it **supersedes every per-milestone stopping condition on
every line**, including "at the seed1-vs-seed2 noise floor" and any five-cell verdict read as sufficient:

> the emulator must **fully emulate the original model**, "of course also and **especially under climate
> change**"; done = **everything, including trait distributions AND medians, within 10 % error**; and it is
> "**only finished when it's proven to be correct on ALL cells, not only a handful of test sites**".

**All cells = the 54 020 tree-bearing cells**, not 5 biome cells. **Both scenarios AND the response between
them.** A noise-floor statement is still the right *diagnostic*; it is no longer the *acceptance test*, and
**no line may call a milestone done on a five-cell result again** — nor present one as fidelity evidence
without saying it is 5 of 54 020.

⚠ **The binding constraint is the climate-change clause, not the fidelity numbers.** Trait medians are
already 9 of 10 within 10 % at the test cells, but the emulator's warming response is indistinguishable from
zero where the original rises, and — separately — the source model itself is deliberately run at
**constant CO2** (ADR 0004/0107), which the emulator correctly inherits. **Work that improves present-day agreement is not progress
toward this criterion unless it also opens a response channel.** Plan accordingly.

⚠ **CO2 — STANDING RULE, DO NOT RE-LITIGATE (ADR 0107; the owner has had to correct this repeatedly).** The
emulator **does not see CO2 and must not respond to it**. It responds to **climate**, and the SSP scenarios
already carry the CO2-driven climate signal. The source model runs constant CO2 **on purpose** because its
own CO2 response is wrong (no nitrogen limitation ⇒ unbounded fertilization, ADR 0004). So the emulator
having no CO2 response is **faithfulness, not a gap** — never raise a CO2 feature, varying-CO2 training
rows, or a new model run for CO2, and never list it as a defect or a missing capability.

⚠ One clause needed a decision and carries a stated default, not the owner's words: the original model is
stochastic and its own two runs differ by **29 % of the mean** for the per-patch count in a low-density cell,
so a literal 10 % is unmeetable there by ANY emulator. Default in use: tolerance =
**max(10 %, the original's own two-run spread for that quantity in that cell)**. Full record: ADR 0106.

**Licensing is CLOSED (ADR 0081) — reuse Terrarium / SpeedyWeather / LPJmL-FIT / NeuralCrop.jl freely (yes,
NeuralCrop too: CC-BY-NC permits our research use), just cite them (`reuse-citation`).**

**Read `online-coupling-env` (8 traps) + `docs/notes/p4_online_coupling_design.md` + ADR 0082/0083 before touching code.**
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
reference.** Score against the **LIVE** table only (ADR 0035): `tables/cell_year_soilmoist_ye_hist.parquet`,
1 348 400 cell-years — min 0.0 · q10 0.0 · q25 0.0 · **q50 0.498** · q75 0.877 · q90 0.9999 · max 1.0078 ·
**mean 0.478**. The `swc`-derived numbers (q50 0.4635 / mean 0.5075) are **RETIRED** and porosity-normalized
— scoring against them reintroduces the exact mismatch ADR 0082 §4 rejects. The runtime target is
`root_zone_soilmoist` = the `whcs`-weighted mean over the top **3 layers = 1.0 m**, at **year end**
(`slow.jl:227`, re-verified 2026-08-05) — NOT a whole-column mean.

| run | flow | days | column | mean PAW (unweighted / top 2 m) |
|---|---|---|---|---|
| 1706262 | `NoFlow` (default) | 2 | 433 m | 0.949 / 0.925 — **the initializer, frozen** (trap 8) |
| 1706324 | `RichardsEq` | 10 | 433 m | 0.104 / 0.225 — **mid-drainage transient**, not spun up |
| ~~1706462~~ | — | — | — | **cancelled** mid-flight: it was on the retired 2 m / `swc` basis |
| 1706597 | `RichardsEq` | 30 | 19.46 m, root zone 0.988 m | **first correct-basis result** — see table below |
| **1706979** | `RichardsEq` | **90** | 19.46 m | ← **READ THIS FIRST**: the convergence check |

**Where O3b actually stands** (job 1706597, exit 0, 2973 s; water state IS a model result — saturation
spread over land 0.903, nothing pinned):

| quantile | LPJmL live `soilmoist_ye` | Terrarium root-zone PAW (30 d) |
|---|---|---|
| min / q10 / q25 | 0.0 / 0.0 / 0.0 | **0.0 / 0.0 / 0.0** ← exact agreement on the dry tail |
| q50 | 0.498 | 0.109 |
| q75 | 0.877 | 0.338 |
| q90 | 0.9999 | 0.681 |
| mean | 0.478 | 0.199 |

The **dry tail matches exactly** — the quarter of cell-years at a fully dry root zone, which is the
distinctive feature of the live reference, is reproduced untuned. The **upper half is 2.4–4.6× too dry**.

**DO NOT report this to line S as a train/inference shift yet.** Two confounds are un-excluded and both
push the same way: (1) 30 days from a near-saturated column is still draining (mean saturation 0.89 → 0.24);
(2) SpeedyWeather's own precipitation climatology has only had 30 days to establish. Compare 1706979's
distribution against the table above — **if they agree, the run has converged and the gap is real; if
1706979 is drier again, it is still draining** and the spin-up must be sized before anything is claimed.
Cost measured: **~99 s per simulated day** even on the 19.5 m column (25 TiB alloc, 47 % GC — the RRE
path's allocation behaviour dominates, not the depth), i.e. ~10 h per simulated year.

Why 1706462 is on the right basis: `ExponentialSpacing(N=30, Δz_min=0.05)` defaults to `Δz_max = 100` =
a **433 m** column, 20× LPJmL's 20 m, so an unweighted 30-layer mean is dominated by deep permanently
saturated layers and is **not the same operator** as `slow.jl`'s unweighted mean over 23 layers / 20 m.
`DZMAX=2.5` ⇒ ≈19.5 m, matching LPJmL, equilibrating ~20× faster, and putting more layers inside the top 1 m.
(The root-zone measure itself is depth-restricted, so it is insensitive to column depth; the drainage
timescale and the whole-column contrast are not.)
**One-horizon simplification:** the texture is depth-constant within a column, so `θfc − θwp` cancels and the
`whcs` weighting reduces *exactly* to thickness weighting. Do not carry that assumption into a multi-horizon
stratigraphy.

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
- `docs/notes/p4_online_coupling_design.md` (**written 2026-07-28** — the design of record; keep it current)
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
- **O2** **Write `docs/notes/p4_online_coupling_design.md`** — the missing design of record: which Terrarium
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
