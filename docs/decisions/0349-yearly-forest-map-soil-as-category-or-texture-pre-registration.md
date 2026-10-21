# 0349 — Yearly forest-structure map: soil code as a category, or as texture values (pre-registration)

* **Status:** pre-registered 2026-10-21, before the fits. Results: §4.
* **Owner instruction (2026-10-21):** model fixes first, on the available data (ADR 0348 header).
* **Follows:** STATE.md to-do of 2026-10-21 item 2: the soil code enters the yearly maps as a plain number (no
  `categorical_feature` in `explore_panel_yearly_drift.py` / `explore_panel_stand_map.py` / the package), so LightGBM
  splits on code ranges that have no physical order (code 4 "clay loam" sits between "sandy clay" and "silty clay
  loam"). ADR 0343: dropping lat, lon and soil together changed the stand map's error by < 5 %.
* **Code:** `scripts/explore_panel_yearly_drift.py fit --soil {code,cat,phys} [--suffix]` (default `code` = every
  earlier result); `SUFFIX=<s> scripts/final_structure_score.py`; soil values from `config/soil_texture_by_code.csv`
  (ADR 0348).

## 1. Arms (one change each, against the deployed year-by-year map of ADR 0330 / release v1)

| arm | soil input | predictions |
|---|---|---|
| base (rerun) | soil code as a number (unchanged) | `preds_<g>_rerun.parquet` |
| `cat` | soil code as a LightGBM categorical feature | `preds_<g>_soilcat.parquet` |
| `phys` | soil code replaced by sand, clay, ln Ks, ln Sf of the soil type | `preds_<g>_soilphys.parquet` |

Everything else as ADR 0330: five held-out climate models, unseen run m4, 400 rounds, deterministic row order.

## 2. Pre-registered measures

* **Harness:** the rerun reproduces the stored `preds_<g>.parquet` exactly (max |difference| 0 on every quantity).
  If not, LightGBM is not deterministic here and the arms need replicates before any reading.
* **Score:** `final_structure_score.py` (relaxed standard, ADR 0318 §2; dense defined by the anchor, ADR 0329), per
  arm, 15 cases. Per case and quantity the ratio arm rho50 / base rho50.
* **Adopt an arm** if, over the 15 cases, the median ratio is ≤ 0.98 for tree count AND for biomass per tree (dense),
  ≤ 1.02 for every other quantity and group, and no relaxed-standard criterion that passes in base fails in the arm.
  If both pass, the larger gain on dense tree count wins.
* **Expectation:** |change| < 3 % on every quantity (soil is one of ~90 features and the per-cell anchor already
  carries each cell's level) ⇒ most likely null; then the item is closed and the package stays as it is.
* **If adopted:** the same change on the stand map (`explore_panel_stand_map.py`) is a follow-up arm with its own
  score (phase-B daily fluxes), not assumed.

## 3. Not in this record

The daily network's soil-texture input and the ensemble size: ADR 0348. Extreme-year memory: a separate record.

## 4. Results

(to be added after the fits)
