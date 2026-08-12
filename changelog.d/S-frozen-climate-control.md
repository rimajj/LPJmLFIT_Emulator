### Added

- **A frozen-climate control for the warming-response experiment, and the decomposition it enables.** The
  two scenario legs differ in length (20 vs 81 years), so a raw historic→future difference mixes the
  climate response with 61 years of free-running drift. `BOUNDARY=frozen` reruns the future leg with the
  climate held at present day — same restart, same seeds, same leg length — so `transient − frozen` is the
  climate response with drift removed and `frozen − historic` is the drift.
  `scripts/diagnose_rung2_response.py` now reports that decomposition per cell and per arm.

### Changed

- **The measured warming response is now known to be ~0, not 1.4× too strong.** With drift differenced out,
  drift accounts for 94–100 % of the apparent response and the surviving climate term's slope against the
  original model's own change is −0.03 to +0.04 for every arm. The control validates itself: the
  do-nothing arm's climate term is exactly 0.000 at all 12 cells, as it must be. Recorded in decision
  record 0178, which narrows 0177's magnitudes without withdrawing its per-cell or sign results.
