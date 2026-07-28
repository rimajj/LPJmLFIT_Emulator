### Fixed

- **Documented a measured defect in the Component-S training population (ADR 0031): `TREE_TYPES =
  [1,2,3,4,5]` drops a third of LPJmL-FIT's forest.** `Type` in the annual `ind` output is the 0-based
  `pftpar` index, and ids **0–6 are all seven tree PFTs** (7/8/9 grass, 10–21 crops), so the production
  DRF/copula builders silently omit id 0 (tropical broadleaved evergreen) and id 6 (boreal larch):
  **64 179 572 of 197 721 867 survivor tree stems = 32.5 %**, with **9 011 of 54 020 tree-bearing cells
  (16.7 %) invisible to Component S** — the tropical belt and the Siberian larch zone — and 41.8 % of cells
  losing more than half their stems. Because FIT draws traits uniformly from per-PFT `[low, high]` intervals,
  the truncation also biases retained cells: per-cell trait medians correlate only 0.09–0.97 between the two
  populations, and the complete set carries 1.3–2.7× more between-cell spread. Provenance is a stale sibling
  `configs/config.yaml`, never an ADR; the correct constant already exists at
  `python/src/lpjmlfit_emulator/features.py:50`, and the python LightGBM `DirectEmulator` path is unaffected.
  Every declaration site now carries an ADR-0031 pointer; the correction itself (one imported constant +
  re-derive → retrain → re-validate → re-measure the ADR-0030 gate, with versioned artifacts and an
  integration point with line M) is the next line-S work item. Committed baselines, golden fixtures and the
  runtime are untouched — Hainich contains only ids 1–5, which is why every single-cell gate stayed green.
- Recorded (not yet fixed) a related conditioning hazard: `growth_eff = applied_npp / max(lai, EPS)` divides
  by `EPS = 1e-6` where the joined `LAI_STAND` is exactly 0 (202 106 of 1 348 400 historic cell-years),
  producing a `growth_eff` maximum of **1.19e9**. The coverage guards cannot catch it — the feature tables are
  complete, so a zero is *present*, not missing.
