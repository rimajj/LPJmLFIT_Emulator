---
name: emulator-validation-figures
description: Produce the reproducible validation-figure set that PROVES how well the global Component-S emulator reproduces LPJmL-FIT — global maps (observed / predicted / bias tree density), per-row + per-cell prediction scatter, count-distribution comparison, and skill-by-latitude / skill-by-gdd5 breakdowns — from HONEST K-fold-by-cell out-of-sample predictions. Use whenever the historic OR future (SSP370) emulator is (re)trained, its features/DRF change, or you need publication-style proof-of-skill figures. Also the recruit-trait COPULA trait-distribution figures (ADR 0025): per-axis pooled marginals, per-cell median scatter, per-cell KS maps (figs 09-11 + metrics_traits.txt), gated on COPULA_OUT, from scripts/eval_slow_copula.jl K-fold-by-cell OOS. Names: scripts/eval_slow_drf.jl, scripts/eval_slow_copula.jl, scripts/plot_slow_emulator_validation.py, scripts/run_global_slow_copula.sh, preds_oos.f64, pred_<axis>.f64, COPULA_OUT, figures/emulator_validation/<scenario>/, cell 42490, grid.nc cellid orderA. Complements slow-drf-pipeline (which TRAINS the DRF + copula).
---

# emulator-validation-figures — reproducible proof-of-skill figures for the global Component-S emulator

Run this AFTER the global DRF is trained (see the `slow-drf-pipeline` skill). It shows how well the emulator
reproduces LPJmL-FIT tree density (`n_living` per patch) globally, using **out-of-sample** predictions so the
figures are genuine generalization, not in-sample fit. Rerun it verbatim whenever the emulator changes — the
whole thing is deterministic and parameterized by `SCENARIO`.

## One command (disconnect-proof, SLURM)

The two steps below run heavy work → submit them as ONE SLURM job (survives a dropped connection; the
user's link is unstable — see [[slurm-only-unstable-connection]]). Template (exclude the known flaky node):
```bash
export SBATCH_EXCLUDE=csn14c163                       # [[slurm-flaky-node-exit53]]
TABLE=/p/tmp/jamirp/emulator_global/slow_runtime_<scen>   # <scen> = historic | ssp370
# jcf body (see JOURNAL 2026-07-24 for the exact heredoc used for the historic run, job 1581897):
#   OUT=$TABLE KFOLDS=5 NTREES=150 MAX_DEPTH=16 MIN_LEAF=20 SUBSAMPLE=200000 julia scripts/eval_slow_drf.jl
#   OUT=$TABLE SCENARIO=<scen> <py311> scripts/plot_slow_emulator_validation.py
```
~20–25 min (5 forest fits + plotting). Julia here is plain (DRF is zero-dep pure-Base, no `--project`). The
plot step is light and can also run on the login node once `preds_oos.f64` exists.

## Step 1 — honest OUT-OF-SAMPLE predictions (`scripts/eval_slow_drf.jl`)

K-fold-**by-cell** CV (default 5): each cell is predicted by a forest that never trained on it, so a global
map is real generalization (a row-holdout would leak a cell into train+test and read optimistically — same
lesson as the `HOLDOUT_FRAC` eval in `slow-drf-pipeline`). Reads `OUT/{X.f64,y.f64,cells.i64,manifest.txt}`,
writes `OUT/preds_oos.f64` (per-row OOS prediction, aligned to X rows). **Hyperparameters MUST match the
production train** (`slow-drf-pipeline` step 2 / `run_global_slow_training.sh` defaults) or the eval forest
differs from the shipped model. Requires `cells.i64` — the builder emits it; if absent, rebuild the table.

## Step 2 — figures (`scripts/plot_slow_emulator_validation.py`)

Reads `OUT/{y.f64,preds_oos.f64,cells.i64,cell_meta.parquet}` + `grid.nc` (cellid[lat,lon] = orderA Cell
index, VERIFIED `cellid[51.25,10.25]==42490` Hainich; never flatten-order — the 42490-vs-28008 trap). Values
are averaged over patches+years → one number per cell for the maps. Writes to
`figures/emulator_validation/<scenario>/` (git-ignored — regenerable, avoids binary churn):
- `01_map_observed / 02_map_predicted / 03_map_bias` — global 280×720 `pcolormesh` (no cartopy — it's flaky
  here; plain matplotlib on the regular grid). Bias uses a symmetric diverging scale.
- `04_scatter_density` (per-row hexbin, log) · `05_scatter_percell` (per-cell means) — with R²/RMSE.
- `06_distribution` — observed vs predicted count histogram (log-y).
- `07_error_by_latitude` · `08_error_by_gdd5` — RMSE + bias vs latitude / growing-degree-days (where it
  works / fails).
- `metrics.txt` — OOS per-row R², RMSE, per-cell-mean R², bias, n. **This is the headline proof number.**

## Trait-distribution figures — the recruit-trait copula (ADR 0025)

The count DRF above predicts `n_living`; the **recruit-trait copula** predicts the within-cell TRAIT
distribution (`{SLA, Wooddens, D95max, minwscal}`). Its OOS evaluator is `scripts/eval_slow_copula.jl`
(K-fold-BY-CELL, one copula draw per surviving stem per axis → `pred_<axis>.f64`); build+eval+train the
global copula in ONE SLURM job via `scripts/run_global_slow_copula.sh` (see `slow-drf-pipeline` step 4).
**Global-scale perf/monitoring (bit me):** the OOS quantile-draw loop dominates cost (~naxes·kfolds·n forest
traversals — hundreds of millions at the 133M-stem global table); it is `Threads.@threads`-parallel over
`JULIA_NUM_THREADS` (the orchestrator exports 32) and bit-identical to serial (per-(row,axis) RNG seed). If
the log looks frozen mid-eval, that's Julia BLOCK-BUFFERING the file, NOT a hang — confirm live compute with
`sstat -j <jobid>.batch --format=AveCPU,MaxRSS` (AveCPU≈wall ⇒ burning CPU). `pred_<axis>.f64` are written
only AFTER all folds finish, so a mid-run timeout yields NOTHING — size the wall to the parallel (not serial)
runtime, and keep the per-fold `flush(stdout)`.
Then set **`COPULA_OUT=<copula table dir>`** when running `plot_slow_emulator_validation.py` (alongside the
usual count `OUT=`) and it ALSO emits:
- `09_trait_marginals` — per-axis pooled observed-vs-OOS-predicted histograms (+ nqrmse, KS).
- `10_trait_percell_median` — per-axis per-cell predicted-vs-observed median (DENSITY hexbin + per-cell
  Pearson r / Spearman ρ in the title). **READ IT RIGHT (bit the owner):** 38k cells saturate a plain
  scatter and hide the diagonal → it LOOKS "totally off" when it isn't. The honest per-cell-median skill is
  axis-dependent — GLOBAL historic: SLA r=**0.87** (strong), minwscal 0.78, D95max 0.74, **Wooddens 0.52
  (weak** — predicted per-cell spread only ~0.5× observed ⇒ regresses to the global mean). Root cause is NOT
  a bug: the copula conditions on flux+boundary and DELIBERATELY excludes stand-state (`live_flux_cond`,
  ADR 0025), so it nails the POOLED marginal (fig 09) but under-determines per-cell medians of PFT-composition-
  driven axes (esp. wood density). Improving it = richer environmental / per-PFT conditioning (P3; a frozen-
  `live_flux_cond`-contract change + global re-fit + ADR; degenerate at single-cell Hainich).
- `11_trait_ks_map` — per-axis per-cell KS map (spatial where the marginal is reproduced well/poorly).
- `metrics_traits.txt` — per-axis pooled nqrmse + pooled KS + median-per-cell KS + **median_percell_r /
  median_percell_spearman** (the paired per-cell-median skill — the honest per-cell number; pooled KS alone
  can look great while per-cell medians regress to the mean, see fig 10). **The headline trait proof numbers.** KS + 1-Wasserstein are dependency-light (no scipy). Only SLA/Wooddens feed dynamics;
  D95max/minwscal are sample+validate-only. (13-cell dev check: OOS pooled KS SLA 0.044, Wooddens 0.017,
  D95max 0.029, minwscal 0.021. GLOBAL historic OOS nqrmse SLA 0.016 / Wd 0.022 / D95max 0.028 / minwscal
  0.038; GLOBAL pooled+transient nqrmse 0.010-0.020.)

**Plot per-cell KS was O(ncells·N) → fixed to O(N log N) (sort-group once).** The old fig-11 loop did
`ccells == c` per cell (a full scan over all N stems each) → ~6e12 ops at 45009 cells × 133M stems → the plot
TIMED OUT at 1h. Now `np.argsort(ccells)` once + contiguous-group slices. Regenerating trait figs at global
scale is minutes; give the plot job a ≥1h wall anyway (it also reads 4×~1GB `pred_<axis>.f64`).

**HOLD-OUT-BY-SCENARIO evals (ADR 0026 §5, the unseen-regime proof — train on one regime, test the
held-out other).** COUNT: `scripts/eval_slow_scenario_holdout.jl` on a POOLED count table (needs
`scenario.i64` from `pool_slow_tables.py`) → per-direction R². COPULA/TRAITS:
`scripts/eval_slow_copula_scenario_holdout.jl` on a POOLED copula table → per-axis per-direction nqrmse + KS.
Run each on BOTH the transient- and static-boundary pooled tables — the static-vs-transient DELTA is what
attributes the boundary's payoff (the count scenario-holdout showed transient==static ⇒ the flux drivers,
not the boundary, carry COUNTS; the boundary's value, if any, must show on TRAITS here).

## NOISE-FLOOR gate (the P3 metric — is the emulator as good as the stochastic data allows?)

`scripts/noise_floor_vs_emulator.py` (SLURM via `sbatch_python.sh noisefloor`) compares the emulator's
per-cell skill to the **seed1-vs-seed2** irreducible spread (LPJmL-FIT is stochastic — RAND48 + -DPERMUTE —
so two seeds of the SAME cell disagree; no environment-conditioned emulator can beat that). Reads both
`ind_hist_seed{1,2}_all.parquet` (survivor TREE stems, Type≤6 & isdead==0 — the copula's own filter) +
`slow_copula_historic/{Y_,pred_}<axis>.f64`. Reports, per trait axis, emulator per-cell-median r vs the
seed1↔seed2 floor r, plus the count floor. **Result (2026-07-27):** COUNTS at the floor (emu r²=0.9994 vs
floor 0.953); TRAIT per-cell-median floor is HIGH (0.90-0.97 ⇒ learnable, NOT RNG-noise) while the emulator
is 0.52-0.87 ⇒ genuine model HEADROOM (esp. Wooddens). **Basis gotcha:** the script prints a `seed1-basis`
cross-check (parquet all-years median vs copula-table Y median) — it is LOW for discrete/year-variable axes
(minwscal 0.09, Wooddens 0.49) because their per-cell median is unstable, NOT a coverage bug; read those
axes' emu-vs-floor gap qualitatively. A basis-clean per-axis floor needs the seed2 copula table
(`build_slow_runtime_table.py MODE=copula SEED=2`). Re-run whenever the emulator is retrained.

## Interpreting / what "works well" looks like

- `metrics.txt` OOS per-row R² should be ≈ the `HOLDOUT_FRAC` train/test R² from the DRF train (historic:
  ~0.985). A big drop vs in-sample ⇒ overfitting.
- `03_map_bias` near zero everywhere; `05_scatter_percell` tight on the 1:1 line; `06_distribution` overlapping.
- `07`/`08` reveal biome/latitude regimes where skill drops → the next modeling target.

## Scope + extension points (honest)

- Figures 01-08 validate the **count** (`n_living`) DRF; figures 09-11 validate the **recruit-trait copula**
  marginals (ADR 0025, gated on `COPULA_OUT`). A per-axis JOINT-correlation check (SLA-Wooddens scatter) and a
  copula-vs-fixed-sapling A/B are natural further additions.
- A **skill-vs-baseline** panel (the climate-only `DirectEmulator`, `tables/direct_count_global.parquet`; the
  ADR-0020 falsifiable test) and a **coupled in-loop global** figure (S+F+E vs C trajectories) are natural
  additions — wire them into `plot_slow_emulator_validation.py` as figures 09+.
- For `SCENARIO=ssp370`: derive `cell_year_{soilmoist,lai}_ssp.parquet` + train the ssp370 DRF first
  (`slow-drf-pipeline`), then run this with `SCENARIO=ssp370`.
