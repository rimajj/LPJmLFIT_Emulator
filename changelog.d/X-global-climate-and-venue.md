### Added

- **Climate inputs, registry and a pre-registered evaluation venue for the global training set
  ([ADR 0314](docs/decisions/0314-climate-inputs-for-the-global-training-set-and-the-two-build-families.md),
  [ADR 0315](docs/decisions/0315-global-round-one-venue-splits-and-pre-registered-decision-point.md)).**
  `scripts/explore_glob_climate.py` builds per-cell, per-year climate features for M. Billing's global runs (GFDL-ESM4
  historical/ssp126/245/370, GSWP3-W5E5 obsclim) on the Germany arms' feature names; the printed per-tree temperature
  mortality is reproduced from them on all 38 converted tables (1.15 × 10⁹ rows, 100 %). The October-2026 model builds
  use different mortality parameters and a 30-column per-tree table, which `scripts/explore_glob_convert.py` now
  converts natively. `scripts/explore_glob_registry.py` writes members/builds, five balanced spatial folds and four
  held-out splits (unseen scenario, member, model build); the decision point for this venue is written down before
  any method is scored on it.
