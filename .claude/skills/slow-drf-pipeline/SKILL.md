---
name: slow-drf-pipeline
description: >
  The recurring pipeline for the Component-S production DRF (the flux-driven slow demography emulator's
  learned count/marginal model): build a RUNTIME-CONSISTENT training table, fit + SERIALIZE the zero-dep
  native-Julia DRF, load it into the coupled loop, and run the Gate-3 oracle vs the LPJmL-FIT C truth at
  Hainich. Use whenever training/retraining the Component-S DRF, changing its feature set, serializing or
  loading a DRF.Forest artifact, scaling the DRF from Hainich to global, GENERATING/DERIVING the global
  training-data inputs (running a scenario's C data via run_daily_subset.sh SCENARIO=historic|ssp370, and
  deriving the runtime-consistent soilmoist feature from daily swc + lai from LAI_STAND), or wiring the
  Gaussian copula recruit-trait sampler. Names the artifacts: scripts/build_slow_runtime_table.py,
  scripts/build_swc_soilmoist_feature.py (swc->soilmoist, grid.nc cellid orderA mapping),
  scripts/train_slow_drf.jl, scripts/build_slow_oracle_reference.py, DRF.save_forest/load_forest,
  test/testitems/references/drf_forest_hainich.drf, hainich_slow_oracle_{traits,counts}.csv, cell 42490,
  the flux_feature_vector order, the age_mean train/inference trap, the dynamic-roster append/merge, and the
  age0 seed. ADR 0023/0024.
---

# slow-drf-pipeline — train / serialize / load / oracle-gate the Component-S DRF

The Component-S `FluxDrivenSlowEmulator` (`src/components/slow.jl`) sets its demography TARGET from a
trained flux-conditioned DRF (`src/drf.jl`, ADR 0022). This is the loop that produces + validates that DRF.
Everything is pure Base (empty runtime `[deps]`, ADR 0014); the DRF submodule is `using LPJmLFITEmulator.DRF`.

## The pipeline (each step names its script + gate)

0. **Generate + derive the runtime-consistent feature INPUTS (the global data-creation front).** The table
   in step 1 needs, per (Cell, Year), the real `soilmoist` and `lai` — not the historic proxies. Two sources,
   per scenario (`historic` obsclim 2000-2019 · `ssp370` 2020-2100 constant-CO2):
   - **Run the C model for the scenario** → `scripts/run_daily_subset.sh` with `SCENARIO=historic|ssp370`
     (see the **`lpjmlfit-cbinary`** skill for the mechanics: modules, `lpjcheck`, restart, SLURM). It now
     emits annual `lai_stand`/`fpc_stand` alongside the daily `d_swc` block. `ANNUAL_ONLY=yes` adds
     `lai_stand` to a scenario whose daily set already exists (e.g. historic) without regenerating ~186 GB.
     Full-global SSP370 daily ≈ 768 GB / ~2-3 h on 2048 tasks.
   - **Derive `soilmoist` from daily `swc`** → `scripts/build_swc_soilmoist_feature.py` (env `RUN_DIR`,
     `FIRSTYEAR`, `OUT`; SUBMIT to SLURM — it streams the ~135 GB `d_swc` cube dask-lazy, one year at a time).
     It reduces `SWC[time,layer=23,lat,lon]` → per (Cell,Year) mean over (days-in-year × 23 layers) = the
     runtime's `sum(state.w)/length(state.w)` (slow.jl:498) EXACTLY (NSOILLAYER=23, unweighted). **Cell mapping
     is via `grid.nc` `cellid[lat,lon]` = the authoritative orderA index** (VERIFIED cellid[51.25,10.25]==42490,
     Hainich) — never the flatten order (the 42490-vs-28008 trap). Anchor a change with `SUBSET_DEG=2` (fast,
     login-node) and confirm Hainich(42490) is present with a plausible fraction before the global SLURM run.
1. **Build the runtime-consistent training table** — `conda activate py311_new; CELLS=42490 SEED=1
   OUT=/p/tmp/jamirp/slow_runtime python3 scripts/build_slow_runtime_table.py`. Writes `X.f64`/`y.f64`/
   `manifest.txt` (a zero-dep raw-Float64 payload the Julia trainer reads with pure Base IO). Join the step-0
   `soilmoist`/`lai_stand` per (Cell,Year) to replace the proxies when scaling global.
2. **Fit + serialize** — `OUT=/p/tmp/jamirp/slow_runtime julia --project=. scripts/train_slow_drf.jl`
   (login-node fast for one cell; `scripts/sbatch_julia.sh` for global). Writes the COMMITTED artifacts
   `test/testitems/references/drf_forest_hainich.drf` + `..._meta.txt` (nfeat/nhead/boundary/n_init/golden).
3. **In-loop gate** — `test/testitems/slow_production_drf_tests.jl` loads the `.drf` and drives the coupled
   Hainich decade (targets INSIDE the training band ⇒ runtime-consistent; N moves; carbon ~1e-12; energy
   ~7e-15; deterministic). `drf_serialization_tests.jl` gates the bitwise round-trip + the committed golden pairs.
4. **Oracle reference + gate** — `python3 scripts/build_slow_oracle_reference.py` extracts the Hainich C
   ground-truth S-owned marginals → `references/hainich_slow_oracle_{traits,counts}.csv`;
   `test/testitems/slow_oracle_tests.jl` compares the coupled S Height distribution to the C truth as an
   IQR-normalized quantile-RMSE **drift alarm** (~0.31; recursive-vs-nonrecursive, Hainich-only — NOT parity).

## Load-bearing gotchas (this is why the DRF is trusted)

- **Feature order MUST match the runtime `flux_feature_vector`** (`src/components/slow.jl`): `[bm_inc_cell,
  growth_eff, water_stress, soilmoist, hmean, hmax, agb, lai, fpc, age_mean, n_prev, <boundary tail…>]`
  (ADR 0020 §6 — S is conditioned at runtime on the channel it was trained on). A mismatch ⇒ the DRF is fed
  OOD inputs and predicts nonsense while STILL conserving carbon (the error is masked). The in-loop test's
  "targets inside the training band" assertion is the runtime-consistency check.
- **`age_mean` is a TRUE nind-weighted mean cohort age (ADR 0024 — supersedes ADR 0023 §3's counter).** Since
  the roster is now dynamic (recruits APPEND at age 0), `s.age` is a genuine per-cohort age, so train
  `age_mean = mean(Age − 1)` per living tree stem (start-of-year age: the runtime feature is built BEFORE the
  `s.age .+= 1` increment; emitted `Age` is post-increment, CLAUDE.md §3). Each `ind` row is one stem, so the
  per-stem mean equals the runtime nind-weighted cohort mean. `build_slow_runtime_table.py` also emits
  `age0 = median(age_mean)` into the DRF meta; the coupled builders read it and pass `age0=` to
  `FluxDrivenSlowEmulator` so the runtime age_mean starts inside the trained band (the gates assert `age0 > 0`
  — a dropped wire-up would silently re-open the OOD shift, since the DRF leaf-clamps OOD inputs). Retraining
  MUST regenerate `drf_forest_hainich.drf` + `_meta.txt` (golden pairs) TOGETHER.
- **`water_stress` = 1 − wscal_mean** (matches `fast.jl`), NOT the `mort_water` inversion the OOD-experiment
  table used. **`soilmoist`/`lai` are proxies (const 0.7 / Σ per-crown ind-LAI) ONLY in the Hainich demo
  table** (`build_slow_runtime_table.py`); the GLOBAL runtime-consistent pipeline now sources them for real —
  `soilmoist` from daily `swc` via `scripts/build_swc_soilmoist_feature.py` (step 0), `lai` from the C annual
  `LAI_STAND` (`run_daily_subset.sh` now emits `lai_stand`). Historic is derivable now; SSP370 waits on the
  daily run. Match the runtime definition when you wire either in (soilmoist = unweighted 23-layer mean).
- **Ind `npp`/`agb` are already per-m²** (×nind baked in by the C writer), so per-patch ROW SUMS are per-m²
  stand totals matching the runtime — no `nind` factor (there is no `nind` column; CLAUDE.md §3).
- **Serialization is TEXT `.drf`, never `*.bin`** (git-ignored). `DRF.save_forest`/`load_forest` round-trip
  bitwise (Julia's shortest decimal). Keep `load_forest` closure-free (inlined `pos` cursor) — the JET 0.11.6
  boxed-closure gate (CLAUDE.md §2). The committed Hainich `.drf` is a DEMO (≤~200 KB); the global forest is
  DVC on `/p/tmp/jamirp/emulator_global/drf/`, not git.

## Copula recruit-trait sampler (WIRED as an opt-in hook, ADR 0024)

`DRF.GaussianCopula`/`chol_lower`/`norminv`/`normcdf`/`copula_uniforms!`/`sample_copula!` draw correlated
recruit traits {logHeight, Age, SLA, Wooddens, beta_root} via the Cholesky of a correlation matrix mapped
through per-axis flux-conditioned `predict_quantile` marginals. `GaussianCopula(R)` FACTORS a correlation
matrix (`from_corr=true` default); pass `from_corr=false` for a raw Cholesky `L`. As of **ADR 0024** the
consumer exists: the `FluxDrivenSlowEmulator` carries an OPT-IN `recruit_copula::RecruitCopula` field
(default `nothing`); when set, establishment's APPEND path draws `sample_copula!(s.rng, cop, axis_forests, x)`
(deterministic on the seeded RNG) and maps the traits to the recruit pools via `RecruitCopula.to_pools`.
Default `nothing` ⇒ the fixed sapling (committed gates unaffected). The **production** axis-forest artifacts
(one `store_values=true` DRF per trait axis) + the correlation matrix `R` are a **P3 (multi-cell)** follow-up
— at single-cell beech the trait axes are near-degenerate; `test/testitems/slow_membership_tests.jl` exercises
the hook end-to-end (Float64 + Float32) with in-test axis forests.

## Membership + age retrain (ADR 0024) — the recurring loop

When you change the roster/age/feature semantics: (1) edit `build_slow_runtime_table.py` (age_mean = mean(Age−1),
emit `age0`), (2) rebuild the table (`CELLS=42490 SEED=1 OUT=/p/tmp/jamirp/slow_runtime python3
scripts/build_slow_runtime_table.py`), (3) retrain (`ALLOW_LOGIN_HEAVY=1 OUT=/p/tmp/jamirp/slow_runtime julia
scripts/train_slow_drf.jl` — it includes only `drf.jl`, pure-Base, so no package precompile), (4) confirm the
meta carries `age0`, (5) the Gate-3 oracle compares coupled Height on the C `ind`-output basis (≥5 m; the C
writer excludes sub-5 m saplings, truth q05≈5.2 m) — re-measure nqrmse and widen only WITH a documented
reference-basis re-measurement (residual-diagnosis), never silently.
