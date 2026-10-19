---
name: response-proof-clustered
description: Train and score the emulator on clustered (representative, 25-patch) runs of the nitrogen-on merged LPJmL-FIT with transient CO2 — the warming-response proof of ADR 0342. Use when re-running, extending (new climate models, scenarios, seeds, CO2-fixed twins) or re-scoring that experiment, or when building any new clustered training set for the emulator.
---

# Warming-response proof on clustered nitrogen-on runs (ADR 0342)

**Data:** runs `/p/projects/reformit/Jamir/lpjml-fit-clustered/runs/emu-non-rep-s<seed>[__<gcm>]`; maps
`esm_land_emulator_data/clu_non/`; daily arrays + daily-model runs `esm_land_emulator_data/f2_non/`.
Model snapshot `lpjml-fit-clustered/trees/nitrogen-on-ef38b509e`; grid `grids/k674_lowrank_hist_rep1_seed1`
(674 cells = one per region, 25 patches; built by `scripts/clu_emu.py grid`).

## Run it
```bash
scripts/clu_emu_runs.sh inputs                                   # cut historical + 30 scenario climates (once)
scripts/clu_emu_runs.sh hist <seed>                              # 1000-yr spin-up + 1901-2019, ~80 min
scripts/clu_emu_runs.sh legs <seed> "<GCM ...>" "<ssp ...>" [rising|fixed] [afterok-ids]   # ~7 min each
P=/home/jamirp/.conda/envs/py311_new/bin/python
$P scripts/clu_emu_maps.py static|climate                        # once
scripts/clu_emu_chain.sh <seed2 leg ids> <seed3 leg ids> <climate id>   # targets -> maps -> daily model -> scores
```
Results: `clu_non/eval/response_maps.csv` (maps; cand main / wrong / second / persist) and
`f2_non/runs/<tag>/response.csv` (daily; NC_A = original stand, NC_B = emulated stand).
Every stage skips outputs that exist, so adding legs = submit legs, then re-chain targets/build/predict/score
(move `preds.parquet` / `response_maps.csv` to a `_v<n>` name first — never overwrite).

## Map arms (ADR 0343)
`clu_emu_maps.py` `ARM_CFG`: per-arm LightGBM params, dropped / added features (`SENS_F`, `TREND_F` from
`hist_response()` = the cell's own 1990–2019 historical behaviour) and `cell_mod` (train on every k-th training
cell). Add an arm there, `train --arm X` → `predict --arm X` → move `response_maps.csv` to `_v<n>` → `score` →
`python scripts/summarize_clu_arms.py` (median held-out / all-cell error vs the second run + the 0343 decision).
Held-out cells, not held-out climate models, set the stand error (ADR 0343): judge any map change there.

## Traps
* **Scratch-test the chain on the first finished leg before trusting it** (monkeypatch `M.OUT`/`F.F2N` to `/p/tmp`,
  `M.all_legs` to one leg). It caught three bugs on 2026-10-15 that would each have killed the chain silently —
  the `--wrap` jobs always exit 0, so read the logs, not `sacct`.
* The nitrogen-on build's NetCDF time is `days since 1901-1-1` with mid-year stamps (`clu_emu_maps.first_year`).
* Pin every dtype of `ind_*.csv` (31 columns incl. `NFixing`); inference reads whole-number traits as integers.
* `scenario_run.sh` names outputs by SSP only ⇒ one branch dir per GCM; two seeds of the same (ssp, GCM) with
  `CO2=fixed` share the generated fixed-CO2 input file ⇒ chain seed 3 after seed 2 (`legs ... fixed <ids>`).
* One Greenland ice cell (Cell 286, 1.7 % of the area weight) sits at the model's 20 m snow cap.
* **The per-cell slope against ONE run of the original is diluted by that run's noise**: the second run's own
  vegetation-carbon slope is 0.72–0.84. Always print the second run's slope next to the emulator's; never gate on
  slope ≥ 0.8 without it.
* `sacct -j <ids>` without `-u jamirp` can list another user's array job with the same id number.
