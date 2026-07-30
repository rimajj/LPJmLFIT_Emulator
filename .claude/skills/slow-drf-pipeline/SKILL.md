---
name: slow-drf-pipeline
description: >
  The recurring pipeline for the Component-S production DRF (the flux-driven slow demography emulator's
  learned count/marginal model): build a RUNTIME-CONSISTENT training table, fit + SERIALIZE the zero-dep
  native-Julia DRF, load it into the coupled loop, and run the Gate-3 oracle vs the LPJmL-FIT C truth at
  Hainich. Use whenever training/retraining the Component-S DRF, changing its feature set, serializing or
  loading a DRF.Forest artifact, scaling the DRF from Hainich to global, GENERATING/DERIVING the global
  training-data inputs (running a scenario's C data via run_daily_subset.sh SCENARIO=historic|ssp370, and
  deriving the runtime-consistent soilmoist feature from daily rootmoist + whc_nat, and the per-patch stand
  LAI reconstructed in-row from the ind LAI/fpc_ind columns), or wiring the
  Gaussian copula recruit-trait sampler. Names the artifacts: scripts/build_slow_runtime_table.py,
  scripts/build_rootmoist_soilmoist_feature.py (rootmoist->soilmoist, grid.nc cellid orderA mapping),
  scripts/diagnose_patch_lai_reconstruction.py (the per-patch stand-LAI reconstruction gate),
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
   - **Derive `soilmoist` from daily `rootmoist` + `whc_nat`** → `scripts/build_rootmoist_soilmoist_feature.py`
     (env `RUN_DIR`, `FIRSTYEAR`, `OUT`, `SUBSET_DEG`). Per (Cell,Year):
     `ROOTMOIST(31 Dec) / Σ_{l<3} whc_nat[l]·thickness[l]` = the root-zone (top 1 m), `whcs`-weighted mean of
     the C's `w` at YEAR END == the runtime `root_zone_soilmoist(state, fc.soil)` (slow.jl). Light (20 of 7300
     time slices + a 3-layer whc read). **Cell mapping is via `grid.nc` `cellid[lat,lon]`** = the authoritative
     orderA index (VERIFIED cellid[51.25,10.25]==42490) — never the flatten order (the 42490-vs-28008 trap).
     Anchor a change with `SUBSET_DEG=2` on the login node before the global SLURM run.
     - **DO NOT go back to `swc` (ADR 0035).** `build_swc_soilmoist_feature.py` is SUPERSEDED: `swc` is total
       water over SATURATION capacity, a DIFFERENT VARIABLE from the runtime's plant-available fraction of
       WHC, and it is not invertible (no `wsats`/`wpwps` output). See CLAUDE.md §3. The two overlap
       numerically, which is exactly why this survived as an "aggregation" bug for a milestone.
     - `RUN_DIR`/`FIRSTYEAR` are NOT in `sbatch_python.sh`'s explicit forward list, so `export` them (the
       wrapper is integrator-owned; `--export=ALL` carries exported vars).
   - **`lai` needs NO deriver — it is reconstructed per-PATCH in the table builder (ADR 0035).**
     `build_slow_runtime_table.py::patch_stand_lai_expr` computes
     `Σ_stems LAI·fpc_ind/(1−exp(−k_pft·LAI))` from the emitted columns (per-PFT k: 0.59 BL / 0.45 NL;
     `patcharea` cancels). Validated against the C's own crown allometry by
     `scripts/diagnose_patch_lai_reconstruction.py` (median rel err 1.8e-8) — **run it if you touch the stem
     filter or the reconstruction.** `build_laistand_lai_feature.py` (the C `LAI_STAND` cell-mean) is
     SUPERSEDED for training and retained only as that diagnostic's all-trees reference: it is a
     patch-ensemble CELL-mean, which broadcast onto per-PATCH rows was the S1d spatial mismatch.
1. **Build the runtime-consistent training table** — `SCENARIO=historic|ssp370 SEED=1 [CELLS=<subset>]
   OUT=... python3 scripts/build_slow_runtime_table.py`. GLOBAL multi-cell: streams the ind agg, inner-joins
   the step-0 `soilmoist` per (Cell,Year) (`SOIL_TBL_PATH` overrides for tests; `lai` is reconstructed in-row,
   not joined — ADR 0035), bakes a
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
   - **VERSION the artifacts, never overwrite (ADR 0029/0031).** All four `run_*_slow_*.sh` orchestrators take
     `VERSION=<tag>`, which suffixes every table dir, artifact and log (`VERSION=t7` →
     `slow_copula_historic_t7/`, `drf_forest_global_pooled_w20_t7.drf`, `logs/gpcop_slow_t7.*`). Line M **pins**
     `drf_forest_global_pooled_w20.drf` + `recruit_copula_global_pooled_w20.rcop`, so a retrain on a changed
     basis MUST write new versioned files and let M re-pin deliberately. Default (unset) = the legacy paths.
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
- **`lai` is per-PATCH and `soilmoist` is root-zone year-end — both CLOSED by ADR 0035 (S1d).** This bullet
  used to say "per-patch LAI is NOT reconstructable from ind (no `leaf_c`/`nind`), so cell-mean is the best
  available" and to call it an open Phase-5 decision. **That was wrong, and it cost a milestone**: `LAI` +
  `fpc_ind` between them carry the crown area, so the per-patch stand LAI is exact (see step 0). The lesson
  worth keeping: "column X is not reconstructable" is a claim to RE-DERIVE against the C source, not to
  inherit — as is "the two sides differ only in aggregation" (`soilmoist` was a different VARIABLE, not a
  different time reduction). Check they are the same QUANTITY before arguing about bases.
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

## The STEM POPULATION — ONE imported constant (ADR 0031, fixed 2026-07-28)

**`Type` is the 0-based `pftpar` index; ids 0–6 are ALL SEVEN tree PFTs** (7/8/9 grass — emitted with the tree
fields *zeroed*, so including them injects structural zeros; 10–21 crops, never emitted).

**`TREE_TYPES` now lives in exactly ONE place — `python/src/lpjmlfit_emulator/data.py` — and every builder
IMPORTS it** (`features.py`, `python/config/config.yaml`, all four `build_slow_*.py`,
`noise_floor_vs_emulator.py`). **Never re-declare it in a new script**: two independent copies is precisely what
caused ADR 0031, where a stale `[1,2,3,4,5]` dropped id 0 (tropical broadleaved evergreen) + id 6 (larch) =
**32.5 % of survivor tree stems** and made **16.7 % of tree-bearing cells invisible** (45 009 of 54 020) for
months. Measured effect of the widening on the historic copula table: **133.5 M → 197.8 M stems, 45 072 →
54 058 cells**, and `minwscal` from the truncated `[0.025, 0.30]` span to FIT's true `[0.025, 0.75]`.
- Traits are drawn from per-PFT `[low,high]` intervals (`new_tree.c:195-206`), so **any per-cell trait
  statistic is a *composition* statistic** — never mix populations across a train/eval/floor comparison (that
  mix is what made the pre-S1 noise floor unreadable). `noise_floor_vs_emulator.py` derives which of its
  `tree7`/`tree5` bases is `same_population` FROM the imported constant for exactly this reason.
- **Census / reproducer:** `scripts/sbatch_python.sh S-typecomp scripts/diagnose_ind_type_composition.py`
  (~2 min) — per-`Type` stems/cells/trait medians, cells lost entirely, and the per-cell median shift a PFT-set
  change induces. **Run it whenever you change the stem filter.**
- **Per-PFT mortality params are per-PFT** (`build_slow_flux_table.py::PFT_PARAMS`, all seven `[VERIFIED]` from
  the active `par/pft_lpjmlfit.js` by brace-depth parse). Widening a tree set needs each new PFT's OWN params,
  not a longer key list: the old dict applied temperate/ANGIO values to every id and was wrong for ids 1/2/4/5
  too — id 5's longevity is **125**, not `TREE_LONGEVITY` 400 (a 3.2× age-mortality error), and its
  `mort_water_factor` is 20 not 5; ids 1/2 are XERIC (0.25) not ANGIO (0.75). An unknown `Type` now RAISES.
- Hainich (42490) has only ids 1–5 + grass 8 ⇒ every single-cell gate is blind to the population. A green
  Gate-3 says nothing about the global population — gate the no-op with
  `scripts/verify_hainich_demo_artifacts.sh` (below), not with a green test suite.

### `lai == 0` → `growth_eff`: RESOLVED, and the lesson generalizes

**Match the runtime, don't floor the divisor.** `build_slow_runtime_table.py` now computes
`growth_eff = lai > 0 ? applied_npp/lai : 0.0`, which is exactly `fast.jl:369`
(`leaf_area > 0 ? applied_cell/leaf_area : zero(T)`); the C oracle guards it the same way
(`mortality_tree_ind.c:95`: `if(leafarea_real > 1e-6) … else mort_npp = 1`). The old
`÷ max(lai, EPS)` with `EPS=1e-6` turned a joined `LAI_STAND == 0` into `applied_npp × 1e6` — an ADR-0023
train/inference shift on a primary mortality driver. A `GROWTH_EFF_MAX` (default 1e6) assertion now fails the
build loud; observed maxima are 3.1e4 (seed1) / 4.3e4 (seed2).
- **The seed asymmetry ADR 0031 recorded as UNEXPLAINED is diagnosed** (`scripts/diagnose_lai0_growth_eff.py`,
  job 1621973): there is exactly **one** `cell_year_lai_*` / `cell_year_soilmoist_*` table per scenario and it
  is **seed1-derived** (`build_laistand_lai_feature.py RUN_DIR=…_seed1`). Joined onto seed1 `ind` it is
  self-consistent — **0** of 23.9 M tree groups have `lai == 0`, because a cell-year with living leafy stems in
  *that* trajectory never has `LAI_STAND == 0`. Joined onto **seed2** `ind` (a different RAND48/`-DPERMUTE`
  trajectory) it hits 21 501 groups / 204 867 stems with positive npp → max 1.19e9.
- **So a seed2 table's `Xc` can never be fully runtime-consistent** without deriving seed2 `soilmoist`/`lai`.
  Harmless for the ADR-0030 noise floor (it reads `Y` only, never `Xc`) — but do not train on a seed2 table.
- **The generalizable lesson:** the coverage guards (`drop_frac`, `cells_lost`) structurally CANNOT catch this
  class — the feature tables are *complete*, so a zero is **present**, not missing. And a single `max=` line in
  a build log is not enough: mean 121 vs 264 495 was the real tell, so eyeball the printed cond-column **MEAN**
  too. When a feature has a degenerate branch, go read what the RUNTIME does with it.

### Is my pipeline change a no-op at Hainich? — the two-tier gate

`scripts/verify_hainich_demo_artifacts.sh` regenerates all four committed Hainich demo artifacts (oracle
CSVs, `.drf` + meta, `.rcop` + meta) in one SLURM job and reports `git status` on
`test/testitems/references/`. Verdicts: `PASS` (byte-identical) · `FAIL` (exit 1) · **`STALE-FIXTURE` (exit 2)**.
The third tier exists because a bare byte-identity gate **conflates** "my edit moved the table" with "the
fixture was already out of date". The control that separates them is
`scripts/diagnose_slow_table_drift.py` (`CELL`, `REF`, `MODE`): it builds the same single-cell table with the
builder at a git ref and with the working tree and diffs `X` column-by-column.
- **RESOLVED 2026-07-28 (S1c): `drf_forest_hainich.drf` was stale — it is now regenerated onto the REAL basis
  and the gate reports `PASS` (exit 0).** It had been trained on the retired PROXY features (`soilmoist` 0.7,
  `lai` 21.2, `growth_eff` 19) while `recruit_copula_hainich.rcop` and any fresh build were on the REAL ones
  (0.85, 3.07, ~151) — one emulator, two conditioning bases. **A `STALE-FIXTURE` exit 2 is therefore no longer
  expected; treat it as a new finding.** Regenerating both fixtures from ONE build is the standing rule
  (ADR 0032 §5): they share four conditioning columns, so regenerated apart they silently re-split.
- Recover from a failed gate with `git checkout -- test/testitems/references/`. But when the regeneration IS
  the deliverable, do **not** restore — commit it, and re-measure the gates below in the same change.

### After regenerating a committed artifact: RE-MEASURE the gates with one probe

`scripts/measure_hainich_gate_bands_probe.jl` (SLURM: `scripts/sbatch_julia.sh S-bands --project=.
scripts/measure_hainich_gate_bands_probe.jl`) reproduces all three coupled harnesses the testitems build and
prints every quantity they bound — Height `nqrmse`/median/count ratios, the direct-draw + coupled-community
trait numbers, `target_history`, the carbon residual — plus the two checks the tests structurally cannot do:
artifact-vs-artifact **basis agreement** and **runtime-vs-trained feature band**.
- **`DRF_ART`/`DRF_META` point it at an OLD artifact** (`git show HEAD:… > /p/tmp/…`), which is how you get the
  BEFORE column of a before/after threshold table. **Do this first and check it reproduces the documented
  numbers** — that is what validates the harness before you trust the after-column (residual-diagnosis §3).
  It reproduced 0.3895 / 1.2463 / 0.6734 against the documented "≈0.39 / ≈1.25 / ≈0.67".
- **A target-band assertion CANNOT detect a conditioning shift, and this is a proof, not a caveat:** a DRF
  prediction is a convex combination of training leaf means, so it can never leave `[y_min, y_max]` however
  out-of-domain its input is. Runtime-consistency has to be checked on the INPUT side — hence
  `FluxDrivenSlowEmulator.feature_history` (the exact row fed to the forest each year, diagnostic only) and the
  `y_min`/`y_max`/`feat_min`/`feat_max` lines `train_slow_drf.jl` now writes into EVERY artifact meta. Keep
  emitting them: `slow_production_drf_tests.jl` asserts against them.
- **Known, PINNED out-of-band columns (ADR 0034), not a pass:** `water_stress` 6.6× band width (an F_diff-vs-C
  difference — line M's file), `soilmoist` 5.1× (year-end instant vs the annual-mean training basis), `lai`
  2.9× and `fpc` 0.03× (one patch vs the C's cell-mean `LAI_STAND`). The test pins that exact set, so a NEW
  column drifting out reds CI. Do not "fix" a band violation by widening the band — the band is a measurement
  of the training data, not a tunable.

## STRUCT axes — validating the emulator's BIOMASS and SIZE distributions (opt-in, ADR 0036)

"Are the trait distributions matched?" is figs 09-11. "Is the **biomass** matched? are the **tree sizes**
matched?" needed one more thing: `STRUCT_AXES` adds per-stem **`agb`** and **`Height`** to the `MODE=copula`
table as extra `Y_<axis>.f64` columns, so they get the *same* per-cell K-fold-BY-CELL OOS validation the four
production traits get (own marginal DRF, same `live_flux_cond` conditioning, own `pred_<axis>.f64`).
```bash
VERSION=t8 SCENARIO=historic STRUCT_AXES=agb,Height STEM_CAP=0 NCPUS=64 scripts/run_global_slow_copula.sh
VERSION=t8              STRUCT_AXES=agb,Height STEM_CAP=400 NCPUS=96 scripts/run_pooled_slow_copula.sh
```
- **They are DIAGNOSTIC ONLY and must never reach the `.rcop`.** Line M pins that artifact and
  `slow.jl::make_recruit_to_pools` maps exactly the 4 production axes onto carbon pools (ADR 0025, frozen).
  This holds *structurally*, not by care: `train_slow_copula.jl` reads the manifest's `axes` line, while the
  struct set is a SEPARATE `nstruct`/`struct_axes` pair — so `axes`/`naxes` keep meaning the production axes.
- **They are APPENDED, never interleaved, and that is load-bearing.** `eval_slow_copula.jl` seeds each axis's
  forest (`seed = a`) and per-row draw RNG (`Xoshiro256pp(i*131 + a)`) from the axis **INDEX**, so appending
  leaves every production prediction **bit-identical** (guardrail 4). Any reorder silently moves them.
- **The two defaults differ ON PURPOSE:** `build_slow_runtime_table.py` defaults `STRUCT_AXES` EMPTY (so its
  own output stays byte-identical), while both copula ORCHESTRATORS default it to `agb,Height` (producing the
  validation generation is their job). `STRUCT_AXES=` opts out.
- **Gate it with the 50-cell smoke, don't trust the claim:** `/p/tmp/jamirp/emulator_global/smoke_struct_t8.jcf`
  builds the same table with the axes OFF and ON, `cmp`s every shared file and every production
  `pred_<axis>.f64`, asserts the `.rcop` meta declares no struct axis, and asserts `pool_slow_tables.py`
  REFUSES a mismatched struct set. `[VERIFIED 2026-07-29]` all four production predictions identical.
- **`eval_slow_copula.jl` FOLD TRAP — never smoke-test it on a handful of cells.** Folds are
  `hash(cell) mod K`, so 5 cells can all land in fold 0: the other fold then fits a forest on **0 rows**, its
  predictions come back `NaN`, and the failure surfaces as the misleading
  `AssertionError: axis SLA: some rows never in a test fold` — which sounds like a coverage bug in the split
  and is not. Use ≥~50 stratified cells (the smoke jcf's list), or raise `KFOLDS` awareness of `ncells`.
- **`agb` can be slightly NEGATIVE** (a carbon-debt stem; historic seed2 min −0.31 gC m⁻²), so any log-scaled
  plot or ratio over it needs a strict-positive mask, not just `isfinite`.

## Is the trait GAP a MISSING COVARIATE or the ESTIMATOR? — decompose it before "expanding the conditioning"

**Run this BEFORE any conditioning change.** Milestone S2 was scoped as "widen `COPULA_COND_COLS` /
`live_flux_cond`". Measurement refuted that as the primary cause, and the two probes below are how.

1. **`scripts/diagnose_copula_cond_ceiling.py`** — splits the ADR-0030 per-cell GAP into the only two causes
   it can have, by fitting a DIRECT per-cell regressor (LightGBM, K-fold BY CELL) on per-cell covariate sets:
   `cond8` (the CURRENT conditioning, time-reduced per cell) · `cond8+env` (plus ~28 climate/bioclimate
   descriptors already in `tables/cell_year_feats.parquet`) · `env_only`.
   * `r(cond8) − emu_r` = **ESTIMATOR INEFFICIENCY** — the information is already there and a new column
     cannot help.
   * `r(cond8+env) − r(cond8)` = **NEW-COVARIATE headroom** — the only part a conditioning change buys.
   It VALIDATES ITSELF FIRST by reproducing the documented `emu_r`/`floor_r`/`sd_ratio` and STOPS if they
   don't match. `FLUX_QUANTILES=1` adds per-cell q10/q90 to bound the "a per-cell time-mean discards
   within-cell year-to-year conditioning" caveat — **run both**; if the caveat run moves the split further
   toward the estimator, that is the strongest form of the evidence (it adds information the copula already
   receives).
   It is an **UPPER BOUND, not a forecast** — a direct per-cell fit optimizes the very statistic the gate
   scores, on ~54k rows instead of ~198M. Use it to bound headroom and rank covariates, never as a skill claim.
   `[VERIFIED 2026-07-30]` on `t8` historic: estimator **+0.080/+0.102/+0.089/+0.032** vs covariates
   **+0.011/+0.025/+0.042/+0.004** (SLA/Wooddens/D95max/minwscal) ⇒ the GAP is the ESTIMATOR (ADR 0037).

2. **`scripts/diagnose_copula_capacity.sh`** — re-runs the K-fold OOS at a chosen capacity on an **UNCHANGED**
   table and scores the ADR-0030 gate, so capacity is measured in ISOLATION from any conditioning change
   (ADR 0033 records this line twice crediting one change with another's effect). `CAPTAG=<tag>
   EVAL_NTREES=… EVAL_SUBSAMPLE=… MAX_DEPTH=… TRAIT_ONLY=1`.

### The mechanism, and why every pooled metric misses it

`SUBSAMPLE=50000` against ~158M training rows over ~54k cells is **~1 row per cell per tree**. Measured on the
production artifact (`recruit_copula_global_historic_t8.rcop`): **1063 leaves per tree for 54 020 cells** — each
leaf hands ~51 cells ONE identical conditional distribution — 47.1 values/leaf, load 2.92 s at 42 MB/s.

`DRF.predict_quantile` **POOLS** the leaf values of all trees into one sorted array and takes the u-quantile of
that MIXTURE. So a mixture over 40 leaves each spanning ~51 cells reproduces the GLOBAL marginal beautifully
(pooled `nqrmse` 0.013, KS 0.0065) while the per-cell conditional stays under-resolved (`sd(pred)/sd(Y1)` 0.678,
slope `Y1~pred` **1.20** = the textbook attenuation signature). **Pooled-marginal metrics — `nqrmse`, pooled KS,
`median_rel_q_err` — are STRUCTURALLY BLIND to a badly under-resolved conditional.** Check `sd(pred)/sd(Y1)` and
the `Y1~pred` slope, and confirm `sd(Y2)/sd(Y1)` ≈ 1 so the under-dispersion is the emulator's and not the
target's. Opposite failure to watch for: too FEW trees ⇒ a noisy per-cell quantile ⇒ `sd_ratio` rises while
`emu_r` FALLS. The gate measures both — report both.

### The forest was not using its own estimator — QRF leaf weighting (ADR 0037, opt-in `qrf=true`)

`DRF.predict_quantile`'s DEFAULT concatenates every tree's leaf values and takes an UNWEIGHTED quantile, so a
value's weight is `1/Σ_t|L_t(x)|` and **a tree contributes in proportion to how LARGE its leaf happens to
be**. A quantile-regression forest (Meinshausen 2006) is defined by the opposite — each tree contributes
`1/T`, spread inside ITS leaf: `w_i(x) = (1/T)·Σ_t 1{i∈L_t(x)}/|L_t(x)|`. `qrf=true` implements that;
`DRF.predict` was ALREADY correct (leaf means at `1/T`), so **the count DRF is unaffected** — this is a
distributional-path-only defect.

**Before implementing a weighting fix, TEST THAT IT IS NOT INERT.** The two estimators coincide exactly when
all leaves are the same size, so the fix is worthless unless leaf sizes are skewed. Measure it on the real
artifact, not in principle: over the `t8` Wooddens marginal's 70 854 leaves the sizes are min 20 / median 26 /
q99 371 / **max 4016**, CV **2.01**, and per query the largest of 60 leaves takes **17–21 %** of the weight
against QRF's **1.7 %** — a 10–12× over-weight. That is the number that justified the change.

**The bias has a DIRECTION, and that is why it mattered rather than being untidy.** A large leaf is one that
stopped splitting early, so it spans a wide region of conditioning space and its values approximate the
GLOBAL marginal. Over-weighting it drags every cell's conditional toward that marginal — an ATTENUATION
mechanism. It also explains an otherwise puzzling ladder result: **more trees did not improve per-cell
dispersion**, because more trees means more chances to land in one dominating big leaf.

**SEPARATE THE CONFOUND before believing any measurement.** Switching to QRF also switches the quantile
CONVENTION (the default indexes `1 + floor(u·(n−1))`; a weighted ECDF must be inverted instead). Measure the
two contributions independently by scoring an equal-weight INVERSE-CDF variant on the same pooled values:
convention **0.002–0.014 %** vs weighting **1.67–4.43 %** (315–1507×) on the production artifact, so the
attribution is clean. Without that check the whole result would rest on a plausible story — the ADR-0036
lesson.

Measure the gate effect with `QRF=1` on `diagnose_copula_capacity.sh`, holding the capacity at the BASELINE so
the weighting is isolated from resolution. **`train_slow_copula.jl` needs the same knob before shipping an
artifact**, or the `.rcop` is fit/served under a different estimator than it was scored with (ADR 0023) —
record the choice in the `.rcop` meta.

### Extended conditioning: 6 columns, not 28 (ADR 0037)

`COPULA_ENV_COLS` (builder) + `live_flux_cond_env(env)` (slow.jl) add a per-cell environmental tail AFTER the
boundary. Done as a policy FACTORY because `RecruitCopula.cond` is already pluggable ⇒ no struct change, no
`.rcop` format change, `live_flux_cond` untouched, and the count DRF's SHARED boundary tail (hence its
`nfeat`) left alone. **Do NOT add all 28 `cell_year_feats` columns**: `Xc` goes 12.6 → ~57 GB and
`mtry = round(√p)` goes 3-of-8 → 6-of-36, diluting the informative columns among correlated climate ones.
Measured with the probe's `ENV_SETS` ranking, six columns — `prec_mean, eco_diag_p_pet_ratio,
eco_diag_pet_mean, eco_diag_vpd_mean, pr_cv_monthly, humid_mean` — capture **64–72 %** of the full-28 gain
(`+lat` adds only +0.002 more). Physical reason the gain exists at all: the boundary tail carries NO moisture
or precipitation climatology while FIT's establishment gates are temperature AND moisture.
**The `.rcop`'s `cond_cols` line is the train/inference contract and a mismatch fails SILENTLY** — the
marginals get read at the wrong coordinates while still returning in-range traits.

### Cost model + artifact budget (measured — this decides which rung is shippable)

Fit ∝ `ntrees·subsample`; predict over ~198M rows ∝ `ntrees`. So raising the subsample at CONSTANT `ntrees` is
expensive (40 × 500k ≈ 4× the 50k baseline per axis-fold, overruns a 4 h wall), while **trading trees for
depth+subsample at a fixed `ntrees·subsample` budget is CHEAPER than baseline on the predict side and
multiplies leaf resolution**. `.rcop` bytes ≈ **`10.7 · ntrees · subsample · naxes`** (122 MB at 60 × 50000 × 4),
so resolution is NOT free — the coupled runtime must load it (≤ ~512 MB ⇒ ~12 s). `TRAIT_ONLY=1` trims the 2
diagnostic struct axes (−33 %; they cannot change the gate's verdict).

### Two traps this work hit

- **NEVER point `eval_slow_copula.jl` at a real table dir to re-evaluate it** — it writes `pred_<axis>.f64`
  into `OUT` and would DESTROY the validated generation the figures and ADR rest on. Use the shadow dir of
  input-only symlinks that `diagnose_copula_capacity.sh` builds; `pred_*` must NEVER be symlinked (the write
  would follow the link back into the source).
- **Make a clobber guard LOCALE-PROOF.** That guard hashed `ls pred_*.f64 | sort`; the login node collates
  `en_US.UTF-8` (case-insensitive) and the SLURM batch shell `C` (uppercase first), so the SAME six untouched
  files hashed differently and it reported `FATAL: the shadow leaked`. Use `LC_ALL=C sort` on BOTH sides and
  print the mtime triples on failure — a guard that cries wolf is worse than none, because you cannot tell a
  real incident from its own bug. (The guard runs AFTER the eval, so a false fire loses only the gate step:
  re-run it against the preserved shadow preds instead of redoing hours of eval.)
- **`sbatch_python.sh` forwards only its explicit list** — `SKIP_PARQUET`/`SKIP_LEGACY`/`FLUX_QUANTILES`/
  `STRUCT_AXES` are NOT on it, so a `VAR=v scripts/sbatch_python.sh …` prefix SILENTLY takes the default.
  `export` them or write a raw `.jcf` (also the only way to get `--dependency=`).

## The NOISE-FLOOR companion table (ADR 0030)

The trait gate needs a **SEED=2 copula table built identically to seed1** — only `SEED` may differ, and
**`STEM_CAP` must stay OFF** (it subsamples `Y`, which would inject subsampling noise into the floor; the
boundary window is free, it touches only `Xc`). It must also be on the **same tree population** as the emulator
it is scored against — mixing `tree5` and `tree7` is what made the pre-S1 floor unreadable, and since 2026-07-28
the population is the imported `TREE_TYPES = [0..6]` (so the ADR-0030 floor moves to the `tree7` numbers):
```bash
MODE=copula SCENARIO=historic SEED=2 OUT=/p/tmp/jamirp/emulator_global/slow_copula_historic_seed2 \
  TIME=02:00:00 NCPUS=32 scripts/sbatch_python.sh S-copula2 scripts/build_slow_runtime_table.py   # ~70 s
```
**"Identically" now includes `STRUCT_AXES`.** If seed1's table carries the struct axes and seed2's does not,
`noise_floor_vs_emulator.py` prints the disagreement and SKIPS every struct row rather than intersecting the
two sets (a silently-narrowed column list is the ADR-0031 failure mode). The t8 pair was built as
`STEM_CAP=0 STRUCT_AXES=agb,Height`, seed 1 vs 2 the only difference — `slow_copula_historic_seed2_t8`,
197 802 377 stems / 54 058 cells, 1.5 min at 64 cpus (job 1641325). `sbatch_python.sh` does NOT forward
`STRUCT_AXES` (integrator-owned list), so `export` it or use a raw `.jcf`.
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
  `soilmoist` from daily `rootmoist`+`whc_nat` via `scripts/build_rootmoist_soilmoist_feature.py` (step 0),
  `lai` reconstructed per-patch in the builder. Historic is derived (`cell_year_soilmoist_ye_hist.parquet`);
  SSP370 still needs its `_ye` table. Match the runtime definition when you wire either in — since ADR 0035
  that is `soilmoist` = root-zone (top 1 m) `whcs`-weighted mean of `w` at YEAR END, NOT a 23-layer mean and
  NOT an annual mean.
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

**"Published" means LOAD-VERIFIED, not "the job exited 0".** Before telling line M an artifact pair is ready,
deserialize both halves and assert the contract — a training job can exit 0 having written a file the runtime
cannot consume, and M pins these. One login-node check, seconds:
```julia
include("src/drf.jl"); using .DRF
f = DRF.load_forest("…_t7.drf");              @assert f.nfeat == 15    # 11 head + 4 boundary
(cop, marg, xfb, ax, cc) = DRF.load_copula("…_t7.rcop")                # NOTE: returns a 5-TUPLE, not a struct
@assert length(ax) == 4 && length(cc) == 8 && length(marg) == 4        # axes / live_flux_cond / marginals
```
Three API traps in that snippet, each of which fails on the first attempt: `load_copula` returns
`(GaussianCopula, Vector{Forest}, Vector{Float64}, axes, cond_cols)` — **a tuple, so `x.axes` throws
`type Tuple has no field axes`**; `GaussianCopula`'s fields are `(:L, :d)`, **not** `corr`; and binding the
axes to a variable literally named `axes` fails with `cannot assign a value to imported variable Base.axes`.
Reference numbers for the `t7` pair: `.drf` 150 trees / `nfeat=15` / 1.5 s · `.rcop` 128 MB / 2.9 s.

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
STEM_CAP` tables → pool → `eval_slow_copula.jl` K-fold → `train_slow_copula.jl`). `STEM_CAP=N` (opt-in,
default 0=all; deterministic per-cell random subsample) caps each cell's stems — a marginal/KS needs only a few
hundred (historic: 197.7M → 19.9M at `STEM_CAP=400`, median 369 stems/cell over 54 020 cells).
- **`STEM_CAP` does NOT bound the PEAK MEMORY, and on `tree7` the ssp370 build OOM-KILLS at 32 cpus
  (`[VERIFIED 2026-07-28]`, job 1622330 exit 137 + `Detected 1 oom_kill event`).** The cap is applied *after*
  the conditioning-join, deliberately, so the `drop_frac` coverage guard still sees true join coverage — so the
  **full** per-stem collect+join happens in memory first. ssp370 spans 81 years (~99M patch-years) and `tree7`
  adds 48 % more stems, i.e. ~890M stems ≈ 200-300 GB peak, while 32 of a 128-cpu/700 GB node's cpus only carry
  ~175 GB. **Use `NCPUS=96` (~525 GB) for any pooled/ssp370 copula build on the complete tree set.** Historic
  alone (20 years) is fine at 32-48. Symptom to recognise: `Killed` + exit **137**, never a Python traceback. Applied AFTER the coverage gate; deterministic (hash(Cell,Patch,Year,
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
