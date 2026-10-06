### Added
- Line X (Germany emulator prototype): `scripts/explore_de_gdrift.py` and `scripts/explore_de_gpit.py` — diagnosis of
  the early growth-efficiency drift (start gate, one-step, self-fed chain, input swaps) and an exact one-step
  calibration test of the growth-efficiency sampler. Finding: the drift is the sampler's distribution shape (its centre
  bends wrongly with the previous growth state), half one step ahead and half amplified by its own feedback.
### Fixed
- `scripts/explore_de_crerun_collect.py` no longer crashes on a re-run block that never ran.
