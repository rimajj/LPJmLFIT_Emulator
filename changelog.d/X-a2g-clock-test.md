### Added
- Line X: `scripts/explore_glob_clock.py` — tests whether the global LSTM arm reads the climate or elapsed time
  (scenario contrast + a no-warming drive against the panel's constant-climate control); ADR 0315 §14.

### Fixed
- Line X: ADR 0315 §12's LSTM tree-count response (0.86) was inflated by an input back-fill from the test member's
  future truth; the clean value is 0.65 (ADR 0315 §14.1).
