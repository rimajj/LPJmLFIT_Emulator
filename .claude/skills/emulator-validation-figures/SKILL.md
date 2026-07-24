---
name: emulator-validation-figures
description: Produce the reproducible validation-figure set that PROVES how well the global Component-S emulator reproduces LPJmL-FIT — global maps (observed / predicted / bias tree density), per-row + per-cell prediction scatter, count-distribution comparison, and skill-by-latitude / skill-by-gdd5 breakdowns — from HONEST K-fold-by-cell out-of-sample predictions. Use whenever the historic OR future (SSP370) emulator is (re)trained, its features/DRF change, or you need publication-style proof-of-skill figures. Names: scripts/eval_slow_drf.jl, scripts/plot_slow_emulator_validation.py, preds_oos.f64, figures/emulator_validation/<scenario>/, cell 42490, grid.nc cellid orderA. Complements slow-drf-pipeline (which TRAINS the DRF).
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

## Interpreting / what "works well" looks like

- `metrics.txt` OOS per-row R² should be ≈ the `HOLDOUT_FRAC` train/test R² from the DRF train (historic:
  ~0.985). A big drop vs in-sample ⇒ overfitting.
- `03_map_bias` near zero everywhere; `05_scatter_percell` tight on the 1:1 line; `06_distribution` overlapping.
- `07`/`08` reveal biome/latitude regimes where skill drops → the next modeling target.

## Scope + extension points (honest)

- This validates the **count** (`n_living`) DRF — the piece trained globally. The **trait marginals + copula**
  (height, SLA, …) are NOT yet predicted globally; add their distribution-comparison figures here once trained.
- A **skill-vs-baseline** panel (the climate-only `DirectEmulator`, `tables/direct_count_global.parquet`; the
  ADR-0020 falsifiable test) and a **coupled in-loop global** figure (S+F+E vs C trajectories) are natural
  additions — wire them into `plot_slow_emulator_validation.py` as figures 09+.
- For `SCENARIO=ssp370`: derive `cell_year_{soilmoist,lai}_ssp.parquet` + train the ssp370 DRF first
  (`slow-drf-pipeline`), then run this with `SCENARIO=ssp370`.
