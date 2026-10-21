# 0358 — Ship the weather-driven departure model in the release (owner decision)

* **Status:** accepted 2026-10-21 (owner: "c1"), release build in progress.
* **Decision:** the release carries ADR 0354's departure model `dep` on top of the yearly structure map: per cell, last
  year's departure of tree count and biomass per tree from the map, driven by this and last year's weather anomaly.
  Releases `release/fold_gfdl-esm4_v3` (validated fold) and `release/v2` (deployment), both
  `scripts/build_emulator_release.py --departure dep`. `release/v1` and `fold_gfdl-esm4_v2` stay as they were.
* **Why, although ADR 0354 did not adopt it:** ADR 0354's adoption conditions were about drought die-offs (capture ≥ 0.30,
  aftermath gap ≤ 2×), which it misses (0.18, 3.75×). The owner chose it for its general effect after ADR 0355–0357
  showed that stand-level inputs cannot reach those bars (die-offs are each tree's leaf-carbon threshold, ADR 0357).
  The two candidates that could (a cohort leaf-carbon sub-model; the emulated NPP anomaly as input) are recorded as
  future work.

## 1. What changes for the user (15 held-out cases, medians; map alone → with departure model)

| | map alone (`_fx`) | shipped (`_statedep_fx`) |
|---|---|---|
| dense: tree count typical / worst tenth (× a second run's error) | 1.256 / 1.469 | 1.215 / 1.402 |
| dense: biomass per tree typical / worst tenth | 1.180 / 1.095 | 1.180 / 1.129 |
| dense: area total stems / biomass (signed) | −0.2 % / −1.5 % | **−2.6 %** / −1.3 % |
| sparse: tree count / biomass per tree typical | 3.001 / 1.474 | 2.900 / **1.552** |
| sparse: area total stems / biomass | −5.2 % / −4.5 % | −3.3 % / −1.5 % |
| trait medians | unchanged | unchanged |
| drift 2051–2070 → 2081–2100 (tree count / biomass per tree) | 1.061 / 1.052 | 1.054 / 1.047 |
| drought die-off: share of the drop / 10-year aftermath gap | 0.027 / 4.53× | 0.183 / 3.75× |

Not uniformly better: the dense stem total moves from −0.2 to −2.6 % and sparse biomass per tree is 5 % worse. The
stand map and the daily networks are untouched, so every daily flux and the stand are identical to `release/v1`.

## 2. Implementation

* Package: `AnnualMaps.departure`, `LandEmulator._dep_start` / `_apply_departure` / `zscore`; state carried: two
  numbers per cell, the last 30 years' yearly climate statistics, last year's z-scores. A release without
  `annual.json` `departure` behaves exactly as before.
* Build: `fit_departure_models` calls `explore_panel_yearly_drift.build_rows` + `fit_departure` (the scored code);
  GATE (4): the package's z-scores equal the training table's on one leg (< 1e-9). `run_emulator.py --check` compares
  the structure with `preds_<g>_statedep_fx` (`release.json` `struct_pred_suffix`).
* Results of the build and the check: §3.

## 3. Builds and check (2026-10-21; jobs 2653114, 2653115, 2653214)

* `fold_gfdl-esm4_v3`: gates (1) 1.04e-6, (2) exact, (3) exact, (4) **3.69e-11**; built in 363 s. `v2` (deployment):
  (1) 1.04e-6, (2) exact, (4) 3.13e-11; 430 s.
* `run_emulator.py --release fold_gfdl-esm4_v3 --run 4 --leg gfdl-esm4_ssp370_daily --check --check-tag PD_B_fx`:
  structure against `preds_gfdl-esm4_statedep_fx` — tree count median |diff| 2.3e-4 of the 90th-percentile size (99th
  pct 2.2e-2), biomass per tree 4.4e-5 (2.0e-2), trait medians 0; stand 0 except `fpc7` / `fpc8` "DIFFERS" exactly as
  v1/v2 did (the 30.0 °C single-precision hot-day count, ADR 0340 §3); daily fluxes 1.5–2.8e-4. **The package with the
  departure model reproduces the scored arm.**
* One-core timing: **7.01e-3 core-s per cell-year** (v1: 7.57e-3 on another node; the departure model adds two
  LightGBM calls per year, not measurable) — 38× below the original at 25 patches, ~1 000× at 500.
