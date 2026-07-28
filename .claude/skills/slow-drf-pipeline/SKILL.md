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
  age0 seed. ALSO the RECRUIT-TRAIT COPULA production pipeline (ADR 0025 — reproduce FIT's within-cell TRAIT
  distribution: 4 live axes SLA/Wooddens/D95max/minwscal, beta_2 is compile-time dead, trained on the
  SURVIVOR marginal, conditioned by live_flux_cond): build_slow_runtime_table.py MODE=copula,
  scripts/train_slow_copula.jl, scripts/eval_slow_copula.jl (K-fold-by-cell OOS), scripts/run_global_slow_copula.sh,
  DRF.save_copula/load_copula, recruit_copula_hainich.rcop, make_recruit_to_pools, live_flux_cond,
  slow_oracle_traits_tests.jl. ADR 0023/0024/0025.
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
   - **Derive `lai` from C `LAI_STAND`** → `scripts/build_laistand_lai_feature.py` (env `RUN_DIR`, `GRID`,
     `FIRSTYEAR`, `OUT`). Maps the annual `lai_stand.nc` `LAI[time,lat,lon]` → per (Cell,Year) stand LAI =
     the runtime `Σ leaf_c·sla·nind` (slow.jl:489). **Uses the GLOBAL daily run's `grid.nc` by default** —
     the ANNUAL_ONLY laistand run's own `grid.nc` has been observed corrupt (all-NaN). HARD-GATES on the
     real (non-fill, <30) fraction so a timed-out/all-fill `lai_stand.nc` can NEVER be silently written.
1. **Build the runtime-consistent training table** — `SCENARIO=historic|ssp370 SEED=1 [CELLS=<subset>]
   OUT=... python3 scripts/build_slow_runtime_table.py`. GLOBAL multi-cell: streams the ind agg, inner-joins
   the step-0 `soilmoist`/`lai` per (Cell,Year) (`SOIL_TBL_PATH`/`LAI_TBL_PATH` override for tests), bakes a
   **per-CELL** climatological boundary (time-constant → matches the runtime's re-appended `s.boundary`), and
   writes `X.f64`/`y.f64`/`manifest.txt` + a `cell_meta.parquet` sidecar (per-cell `n_init`/`age0`/boundary
   the coupled driver reads to build one emulator per cell — ONE pooled cell-agnostic forest; the AR ratio
   `target/n_prev` cancels count magnitude). `CELLS=<one>` also emits scalar meta = the committed Hainich demo
   path. VERIFY on a biome-stratified subset (per-cell equivalence vs solo builds; boundary varies-across /
   constant-within; no NaN) before the global run.
2. **Fit + serialize** — `train_slow_drf.jl` auto-detects mode from the manifest (global lacks the scalar
   `boundary`). **Hainich demo** (defaults): `OUT=/p/tmp/jamirp/slow_runtime julia scripts/train_slow_drf.jl`
   → COMMITTED `test/testitems/references/drf_forest_hainich.drf` + `..._meta.txt` (nfeat/nhead/boundary/
   n_init/golden). **GLOBAL**: set `DRF_OUT_PATH` to a SEPARATE artifact (NEVER the committed fixture) +
   larger `NTREES`/`MAX_DEPTH`/`MIN_LEAF`/`SUBSAMPLE`; per-cell n_init/age0/boundary stay in
   `cell_meta.parquet` (meta writes a `cell_meta` pointer, not scalars).
   - **ONE-SHOT GLOBAL (build table → train, one SLURM job, disconnect-proof):**
     `SCENARIO=historic|ssp370 scripts/run_global_slow_training.sh` → `slow_runtime_<scen>/` +
     `drf_forest_global_<scen>.drf` under `/p/tmp/jamirp/emulator_global/`. This is the preferred global path
     (atomic; logs to `logs/gslow_<scen>.<jobid>.out`). Defaults NTREES=150, MAX_DEPTH=16, MIN_LEAF=20,
     SUBSAMPLE=200000, 32 cpus, 4 h. **Chain after a feature-derivation job with `DEPENDENCY=afterok:<jid>`**
     (an arg to the script — the `SBATCH_DEPENDENCY` env does NOT propagate through the wrapper's sbatch, so
     it comes up `Dependency=(null)`; fix a live pending job with `scontrol update jobid=<j> dependency=...`).
     For SCENARIO=ssp370 you must first derive `cell_year_{soilmoist,lai}_ssp.parquet` (the swc + lai_stand
     derivers, FIRSTYEAR=2020, RUN_DIR = the ssp370 daily output dir which holds BOTH d_swc.nc and lai_stand.nc).
   - **Held-out generalization (the honest Phase-5 number, NOT in-sample R²):** `HOLDOUT_FRAC=0.2` (through
     the orchestrator or train_slow_drf.jl). The builder emits `cells.i64` (per-row Cell); the trainer holds
     out whole CELLS (`hash(cell) mod 1000 < FRAC*1000` — row-holdout leaks a cell into train+test and reads
     optimistically), fits an eval forest on train cells, prints `HELD-OUT-CELL eval: train R²=.. TEST R²=..`.
     Does NOT touch the production artifact (always fit on all rows). In-sample R² alone is NOT a Phase-5 gate.
3. **In-loop gate** — `test/testitems/slow_production_drf_tests.jl` loads the `.drf` and drives the coupled
   Hainich decade (targets INSIDE the training band ⇒ runtime-consistent; N moves; carbon ~1e-12; energy
   ~7e-15; deterministic). `drf_serialization_tests.jl` gates the bitwise round-trip + the committed golden pairs.
4. **Oracle reference + gate** — `python3 scripts/build_slow_oracle_reference.py` extracts the Hainich C
   ground-truth S-owned marginals → `references/hainich_slow_oracle_{traits,counts}.csv`;
   `test/testitems/slow_oracle_tests.jl` compares the coupled S Height distribution to the C truth as an
   IQR-normalized quantile-RMSE **drift alarm** (~0.31; recursive-vs-nonrecursive, Hainich-only — NOT parity).

## Global-build gotchas (from the adversarial review; verified against fast.jl/slow.jl)

- **`growth_eff` numerator = APPLIED npp, NOT total.** The runtime `growth_eff = applied_cell / leaf_area`
  (`fast.jl:353-369`) sums bm only over NON-stagnating cohorts (a cohort with `bm_net<=0` i.e. `bm_ind<=0`,
  or `height<=0`, contributes 0). Train it as `sum(npp | npp>0 & Height>0) / max(lai,EPS)` — NOT
  `sum(npp)/lai`. `bm_inc_cell` (head[0]) stays TOTAL `sum(npp)`. Reusing total npp for growth_eff is a
  silent train/inference shift on a primary mortality driver (the two are collinear in training but not at
  inference). Exact per-cohort `bm_net` parity isn't reconstructable from the 29-col ind — documented approx.
- **`lai`/`soilmoist` are per-CELL (patch-averaged) joined onto per-PATCH rows.** `soilmoist` is cell-level
  at runtime too (OK). `lai` (C `LAI_STAND`) is cell-mean but the single-stand runtime forms a per-patch
  stand LAI — per-patch LAI is NOT reconstructable from ind (no `leaf_c`/`nind`), so cell-mean is the best
  available BASIS (right magnitude ~4-7 vs the old per-crown-sum ~1000 proxy). Don't overclaim per-patch
  consistency; the per-patch-LAI-output vs per-cell-training-aggregation choice is an OPEN Phase-5 decision.
- **Silent-truncation guards are mandatory at global scale.** The soilmoist/lai inner-joins FAIL LOUD on a
  coverage hole (`drop_frac>0.02` or any cell fully lost) — never train on a biome-truncated set. The
  feature derivers gate PER-YEAR (reject if any year's real fraction << median → a timed-out run leaves late
  years at fill), NOT on an absolute floor (most land is legitimately low-LAI). **polars `is_not_null` is a
  NO-OP for NaN** (a NaN float IS "not null") — use `is_not_nan()`/`drop_nans()` to drop fill-marked cells.
- **Boundary — DEFAULT per-CELL TIME-CONSTANT (climatological mean); OPT-IN TRANSIENT per-(Cell,Year) via
  ADR 0026.** Default: per-cell mean, re-appended unchanged each year. `BOUNDARY_WINDOW=W` on
  `build_slow_runtime_table.py` swaps in the per-(Cell,Year) TRANSIENT `gdd5`/`tas_cold_month` (trailing-W-yr
  window, `scripts/build_transient_boundary.py` → `tables/cell_year_boundary_<scen>_wW.parquet`; soil_depth
  static, co2 369) so a warming cell's establishment gate SHIFTS (`_boundary_source` helper, both count +
  copula modes; column order unchanged ⇒ feature-order contract preserved). The runtime consumes it via
  `FluxDrivenSlowEmulator`'s opt-in `boundary_series` (advanced by `s.year` in `reconcile_demography!`), which
  keeps train/inference consistent. **`build_transient_boundary.py` gotchas:** header-driven `.clm` reader
  (v3-float32 HDR 51 vs v2-int16 HDR 43 °C×10 — see CLAUDE.md §3); gdd5 = Thom-1966 monthly (identical to the
  static climclusterpy method) so a W=20 window ending 2019 reproduces the static Hainich value bit-for-bit.
  One pooled cell-agnostic forest + `cell_meta.parquet` sidecar; the AR ratio `target/n_prev` cancels count
  magnitude so pooling cells (and — ADR 0026 — pooling SCENARIOS) is sound.

## The STEM POPULATION — check it before you build anything (ADR 0031)

**`Type` is the 0-based `pftpar` index; ids 0–6 are ALL SEVEN tree PFTs** (7/8/9 grass — emitted with the tree
fields *zeroed*; 10–21 crops, never emitted). Every builder here selects `TREE_TYPES=[1,2,3,4,5]`, which is a
**known DEFECT**: it drops id 0 (tropical broadleaved evergreen) + id 6 (larch) = **32.5 % of survivor tree
stems**, makes **16.7 % of tree-bearing cells invisible** (45 009 of 54 020), and biases the cells it keeps
(traits are drawn from per-PFT `[low,high]` intervals, so any per-cell trait statistic is a *composition*
statistic). `python/.../features.py:50` already has the correct `[0..6]`; `data.py:68` has the truncated one.
- **Census / reproducer:** `scripts/sbatch_python.sh S-typecomp scripts/diagnose_ind_type_composition.py`
  (~2 min) — per-`Type` stems/cells/trait medians, cells lost entirely, and the per-cell median shift a PFT-set
  change induces. **Run it whenever you change the stem filter**, and never mix populations across a
  train/eval/floor comparison (that mix is what made the pre-S1 noise floor unreadable).
- Hainich (42490) has only ids 1–5 + grass 8 ⇒ every single-cell gate is blind to this. A green Gate-3 says
  nothing about the global population.
- **`lai == 0` hazard:** `growth_eff = applied_npp/max(lai,EPS)` divides by `EPS=1e-6` where the joined
  `LAI_STAND` is exactly 0 (**202 106 of 1 348 400** historic cell-years — the table is complete, so the
  `drop_frac`/`cells_lost` guards CANNOT catch it: a zero is *present*, not missing). Measured: the seed1
  production table is clean (max 31 183, zero rows >1e6) but the seed2 build had **204 867 rows >1e6, max
  1.19e9** — so **check it, never assume**: `TIME=00:30:00 scripts/sbatch_python.sh S-ge0
  /p/tmp/jamirp/emulator_global/probe_growth_eff_lai0.py` reads the `growth_eff` column of both tables' `Xc`
  in ~1 min. Guard `lai > 0` explicitly and assert a sane `growth_eff` max in any new table build.
  **A single `max=` line in a build log is not enough** — that is what hid this (mean 121 vs 264 495 was the
  tell), so eyeball the printed cond-column MEAN too.

## The NOISE-FLOOR companion table (ADR 0030)

The trait gate needs a **SEED=2 copula table built identically to seed1** — only `SEED` may differ, and
**`STEM_CAP` must stay OFF** (it subsamples `Y`, which would inject subsampling noise into the floor; the
boundary window is free, it touches only `Xc`):
```bash
MODE=copula SCENARIO=historic SEED=2 OUT=/p/tmp/jamirp/emulator_global/slow_copula_historic_seed2 \
  TIME=02:00:00 NCPUS=32 scripts/sbatch_python.sh S-copula2 scripts/build_slow_runtime_table.py   # ~70 s
```
Then `scripts/noise_floor_vs_emulator.py` (see the **emulator-validation-figures** skill for the gate's
semantics). **`sbatch_python.sh` forwards `MODE`/`SCENARIO`/`STEM_CAP`/`BOUNDARY_WINDOW` only since
2026-07-28** — an older session's copy of this command silently built a *count* table into a copula dir.

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

## Copula recruit-trait PIPELINE (ADR 0025 — trained / serialized / validated production model)

The recruit-trait Gaussian copula reproduces LPJmL-FIT's within-cell TRAIT distribution (the count DRF does
counts/size). **4 live axes `{SLA, Wooddens, D95max, minwscal}`** — `beta_2` is compile-time DEAD
(`getrootdist.c` `#ifdef USE_BETA2`, never defined), and use `D95max` NOT the collinear `beta_root`. Trained
on FIT's **SURVIVING** stems (`isdead==0`): mortality is trait-blind ⇒ community dist == establishment dist ==
survivor marginal. Conditioned on the `live_flux_cond` subset (4 flux drivers + per-cell boundary; NOT the
6 patch-state aggregates / `n_prev`). Only SLA+Wooddens feed dynamics; D95max/minwscal are sample+validate-only.

Pipeline (mirrors the count-DRF one; the scripts are axis-count-agnostic):
1. **Per-stem table** — `MODE=copula SCENARIO=historic SEED=1 [CELLS=<subset>] OUT=... python3
   scripts/build_slow_runtime_table.py`. Forks the count path after the flux-driver agg; broadcasts the
   conditioning (`COPULA_COND_COLS` = the `live_flux_cond` order) onto every surviving stem's 4 trait targets.
   Writes `Xc.f64` / `Y_<axis>.f64` / `cells.i64` / `manifest_copula.txt`.
2. **Fit + serialize** — `OUT=... [RCOP_OUT_PATH=...] $JULIA scripts/train_slow_copula.jl`: one
   `store_values=true` marginal DRF per axis + the LATENT-NORMAL copula correlation (rank→`norminv`→Pearson,
   zero-var guard + ridge) → `DRF.save_copula` `.rcop` + `_meta` (golden seed→draw pairs). Default = the
   COMMITTED demo `test/testitems/references/recruit_copula_hainich.rcop` (~311 KB); `RCOP_OUT_PATH` overrides
   for the GLOBAL artifact (DVC, not git — `store_values` is large). Bitwise round-trip self-check.
3. **Single-cell gate** — `test/testitems/slow_oracle_traits_tests.jl`: loads the `.rcop`, rebuilds `to_pools`
   via `make_recruit_to_pools(axes)` + `live_flux_cond`, runs the coupled Hainich decade. Asserts golden pairs
   (bitwise), conservation, a TIGHT **direct-draw** marginal check (openlibm ⇒ platform-independent: SLA
   nqrmse≈0.13, Wooddens≈0.035) + a COARSE coupled-community alarm (≤0.45, median-ratio-led — the 20-yr Float64
   coupled trajectory's tails diverge by CPU microarch, so it is NOT tight). Plumbing, NOT cross-cell skill.
4. **GLOBAL + OOS (the real fidelity proof)** — `SCENARIO=historic scripts/run_global_slow_copula.sh` = one
   SLURM job: build `MODE=copula` table → `eval_slow_copula.jl` (K-fold-BY-CELL OOS, per-axis `pred_<axis>.f64`)
   → train the pooled global `.rcop`. Then the trait figures 09-11 (see the **emulator-validation-figures**
   skill: `COPULA_OUT=<table dir>` → `metrics_traits.txt`). SSP370 after its features exist.

**Load-bearing:** the copula conditioning order MUST match `src/components/slow.jl::live_flux_cond` (4 flux +
boundary) — the same channel-consistency trap as the count DRF's `flux_feature_vector`. Retraining the `.rcop`
⇒ re-measure the `slow_oracle_traits_tests` thresholds (residual-diagnosis). The sampler primitives
(`DRF.GaussianCopula`/`sample_copula!`/`predict_quantile`, `save_copula`/`load_copula`) are pure-Base (ADR
0014); `RecruitCopula` (default `nothing`) keeps committed gates byte-identical until deliberately enabled.

## Membership + age retrain (ADR 0024) — the recurring loop

When you change the roster/age/feature semantics: (1) edit `build_slow_runtime_table.py` (age_mean = mean(Age−1),
emit `age0`), (2) rebuild the table (`CELLS=42490 SEED=1 OUT=/p/tmp/jamirp/slow_runtime python3
scripts/build_slow_runtime_table.py`), (3) retrain (`ALLOW_LOGIN_HEAVY=1 OUT=/p/tmp/jamirp/slow_runtime julia
scripts/train_slow_drf.jl` — it includes only `drf.jl`, pure-Base, so no package precompile), (4) confirm the
meta carries `age0`, (5) the Gate-3 oracle compares coupled Height on the C `ind`-output basis (≥5 m; the C
writer excludes sub-5 m saplings, truth q05≈5.2 m) — re-measure nqrmse and widen only WITH a documented
reference-basis re-measurement (residual-diagnosis), never silently.

## Pooled MULTI-REGIME + TRANSIENT boundary (ADR 0026) — ONE model across scenarios

The long-term goal is ONE environment-conditioned emulator across CLIMATE regimes + the transient, not a
model per scenario. Prereq = the TRANSIENT boundary (opt-in, above): `scripts/build_transient_boundary.py`
(trailing-W-yr gdd5/tas_cold from the orderA temperature `.clm`) → `BOUNDARY_WINDOW=W` on
`build_slow_runtime_table.py`. Pipeline (`scripts/run_pooled_slow_training.sh`, ONE SLURM job):
build historic + ssp370 transient count tables → `scripts/pool_slow_tables.py` (row-concat + per-row
`scenario.i64`; each scenario built INDEPENDENTLY so AR `n_prev` never crosses the historic↔ssp
discontinuity / splices two climate models) → `train_slow_drf.jl` on the pooled table (consumes it unchanged —
reads X/y/cells/manifest, no cell_meta) → `scripts/eval_slow_scenario_holdout.jl` (the HOLD-OUT-BY-SCENARIO
unseen-regime proof: train on the other regime, test the held-out one; + a pooled by-cell baseline). CO2 stays
constant (ADR 0004 — NOT a feature). `pool_slow_tables.py` asserts matching p/colnames (count) or
ncond/axes/cond_cols (copula) — a mismatch means the two scenarios were built with different feature contracts.
**Pooled COPULA:** `scripts/run_pooled_slow_copula.sh` (build both scenarios' `MODE=copula BOUNDARY_WINDOW=W
STEM_CAP` tables → pool → `eval_slow_copula.jl` K-fold → `train_slow_copula.jl`). The un-capped pooled copula
is ~730M stems (historic 133M + ssp ~600M) — busts the 4h qos — so `STEM_CAP=N` (opt-in, default 0=all;
per-cell random subsample) caps each cell's stems (a marginal/KS needs only a few hundred; 700 GB nodes so the
~600M-stem ssp collect fits regardless). Applied AFTER the coverage gate; deterministic (hash(Cell,Patch,Year,
seed)+row rank per cell).

## ONLINE transient boundary — the coupled-run Climbuf (ADR 0027; the runtime counterpart of `boundary_series`)

Offline, the transient boundary ships as a per-(cell,year) `boundary_series` baked by
`build_transient_boundary.py`. ONLINE (coupled runs / P4), climate evolves as the run proceeds, so the
boundary is recomputed live by **`ClimBuf`** (`src/climbuf.jl`) — a per-cell trailing-W-yr ring the driver
feeds daily air temperature; each year end it recomputes `gdd5`/`tas_cold_month` and refreshes the
`FluxDrivenSlowEmulator`'s `s.boundary`. Wired as the opt-in **`run_coupled_cell(...; climbuf=ClimBuf{T}())`**
(default `nothing` ⇒ static, byte-identical). Seed the ring with the pre-run climatology
(`climbuf_seed!`) so year 1 has a full window. **Load-bearing contract: it MUST reproduce
`build_transient_boundary.py`** (Thom-1966 monthly gdd5 + coldest-month over the trailing window) or train
(offline table) and inference (online loop) diverge — verified to float32-summation-order (NOT bitwise:
numpy pairwise vs the buffer's sequential reductions).
- **Regenerate the parity fixture (needs cluster `.clm`; login node, seconds):**
  `/home/jamirp/.conda/envs/py311_new/bin/python scripts/build_climbuf_parity_fixture.py` → committed
  `test/testitems/references/climbuf_hainich_{monthly,boundary_w20,daily_2010}.csv`. It reuses
  `build_transient_boundary.py`'s reader + method for cell 42490 only (cheap strided memmap read, NOT the
  global all-cell reduction). Gate: `test/testitems/climbuf_tests.jl` (offline parity + coupled wiring).
- **Gotchas:** `AtmForcing.tair` is KELVIN — the driver converts `tair-273.15` (as F does) before accumulating.
  The Climbuf assumes a **365-day noleap** year (the offline month binning) and requires `boundary_series ===
  nothing` (mutually exclusive) — both are guarded in `run_coupled_cell`. Conditioning-only: no carbon/water/
  energy, so it cannot affect conservation.
