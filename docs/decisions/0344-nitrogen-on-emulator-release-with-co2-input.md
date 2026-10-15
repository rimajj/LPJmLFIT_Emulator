# 0344 — Release of the nitrogen-on emulator with a CO2 input

* **Status:** accepted 2026-10-15.
* **Depends on:** ADR 0342 (the nitrogen-on, transient-CO2 clustered runs; maps arm `main2`; daily members
  `NC_s0-4`; phase-B run `NC_B3`), ADR 0343 (the held-out-cell limit of the stand map), ADR 0340 (release v1:
  package, gates, run script), ADR 0004/0107 (no CO2 input for the nitrogen-off model — unchanged).
* **Code:** `python/src/lpjmlfit_emulator/landemu/{emulator,daily}.py`, `scripts/build_emulator_release_non.py`,
  `scripts/run_emulator_non.py`, `scripts/build_emulator_release.py::export_daily` (parametrised),
  `scripts/clu_emu_maps.py` arm `deploy`, `scripts/f2_train.py --all-cells`; tests `python/tests/test_landemu.py`.

## 1. Decision

The release package gains an optional CO2 input, used only by releases of the nitrogen-on model:

* `release.json` `co2_input: true` (and `daily.npz` `co2_input`; the two must agree or loading fails).
* `LandEmulator.step_year(state, forcing, co2=ppm)` — the year's global CO2, as LPJmL's CO2 input file. The daily
  model reads `ppm / 1000` as its last input column (as `f2_train.assemble`); the maps read its trailing 30-year
  mean `co2_win` and the offset `dco2_win` from the anchor period's mean (as `clu_emu_maps.window` / `rows_for`).
* A CO2 release refuses a call without CO2; a release without the input (v1, the Billing/global ones) refuses a call
  with CO2. So the nitrogen-off rule (no CO2 response, ADR 0004/0107) cannot be broken by accident.
* `Setup` gains `co2_hist` (≥ 29 yearly values before the first emulated year) and `aco2`; anchors may be fixed per
  cell (`anc` (N,), `aclim` (N, 25)) — the nitrogen-on maps anchor on each cell's own 1990–2019 state, so a run
  has no last year (release v1's per-year anchors end in 2100).

Two releases under `/p/projects/open/Jamir/esm_land_emulator_data/release/`:

| directory | maps | daily model | purpose |
|---|---|---|---|
| `non_fold_v1/` | `main2`: 8 climate models × 3 SSPs × rising/fixed CO2, 539 training cells | `NC_s0-4`: 8 climate models, 485 cells | proves package == scored pipeline |
| `non_v1/` | `deploy`: all 10 climate models' 58 legs, all 674 cells | `NCD_s0-4`: same 58 legs, all cells (606 train / 68 validation) | **deployment** |

Both carry `setup_s2.npz`: the 674 representative cells (one per climate region), anchored on seed 2's own
1990–2019 historical state, start state = end of 2019.

## 2. Gates (all passed)

Build (both releases): numpy daily ensemble vs PyTorch on 20 000 real rows of a held-out leg, max |diff| / largest
output **7.5e-7** (fold); yearly climate statistics from the runs' `.clm` files == the training table, **exact**;
setup anchors, anchor climate and anchor CO2 == the training rows, max |diff| **5.7e-14**.

Reproduction (`run_emulator_non.py --check`, fold release, MPI-ESM1-2-HR ssp370 — a climate model and CO2 path the
release never saw, 674 cells × 81 years, every input computed by the package from daily weather + yearly CO2):
all 18 structure and stand quantities **bit-identical** to `clu_non/maps/main2/preds.parquet` (largest |diff| 0);
daily GPP / ET / NPP / runoff 2021–2100 per-cell means vs the scored phase-B run `NC_B3`: median relative
difference **5e-8 – 8e-8**, totals within 7e-8.

The release's skill is therefore exactly the scored skill of ADR 0342 §7–8 / ADR 0343 (arm `main2` + `NC_B3`);
nothing new is claimed for the deployment release beyond it.

## 3. Speed (measured)

One core, 674 cells × 81 years, excluding reading the forcing: **7.29e-3 core-s per cell-year** (fold release).
The original (nitrogen-on LPJmL-FIT, 25 patches, these 674 cells, 128 MPI tasks on one node): 381–462 s wall per
81-year leg over 58 legs (median 406 s) = **0.95 core-s per cell-year** on the allocation basis, 0.84 on the
busiest task's (6 cells). ⇒ **≈ 115–130× fewer core-seconds**. Caveats: the original's figure includes its own
output writing; the emulator's excludes the forcing read; the original is not tuned for 674 cells on 128 tasks.
The daily model is still ~97 % of the emulator's cost (ADR 0340).

## 4. Deployment release — results

Build gates as §2 (numpy vs PyTorch 7.0e-7; climate exact; setup 5.7e-14). Run on IPSL-CM6A-LR ssp585 with the
capacity fixed at 2019 (the deployment configuration), 674 cells × 81 years: all 18 yearly quantities
bit-identical to the pipeline's own predictions with the `deploy` maps (`clu_non/maps/deploy/preds.parquet`);
7.27e-3 core-s per cell-year. Every leg is in its training set, so this run shows the package works, not skill.

## 5. What it does NOT do

* **Cells:** setups exist for the 674 representative cells only. A new cell needs the original's 1990–2019 state
  there (the anchor) and its 1990–2019 climate. Each of the 674 cells stands for a climate region
  (`clu_non/cells.parquet` `region_km2`), so region-weighted totals are global totals, but the emulator has not been
  run on the full grid. Per ADR 0343 its stand response on cells the maps never saw is ~1.8–2.2× a second run's error
  (leaf area, tree cover); the deployment maps trained on all 674 cells, so on these cells that limit does not
  apply, but on any new cell it does.
* **Top-metre capacity:** fixed at the cell's 2019 value (`--cap fixed`); the original updates it from soil carbon.
  The fold check used the original's yearly values (as the scored runs).
* **The model:** this is the nitrogen-on merged LPJmL-FIT (no phosphorus), 25 patches. It is not the nitrogen-off
  LPJmL-FIT of releases v1 / the Billing runs, which keep no CO2 input.
* **Coupling:** none yet; `step_year(state, forcing, co2=...)` is the call an ESM would make.
* **PFT temperature-stress climate columns** use the nitrogen-off parameter file's temperature limits
  (`explore_glob_climate.pft_temp_params`), as the training table did; consistent, but they are climate statistics,
  not the nitrogen-on model's own stress counts.
