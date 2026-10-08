### Added
- Line X: per-version retraining test (`scripts/explore_glob_pv.py`, ADR 0315 §11) after the owner clarified that
  "every model version" means the method retrained per build, not one emulator transferred across builds. The direct
  window-map arm reaches the same skill on the Feb, May and four October builds when trained on each build's own runs.
