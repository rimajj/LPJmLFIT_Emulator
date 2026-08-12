### Added

- Rung-2 arm `S0h` (`scripts/rung2_s_demography_harness.jl`): uniform thinning that does not override
  deaths LPJmL-FIT's own hazard had already settled. It is the decomposition control that separates the
  two effects bundled into the trait-mortality arm (ADR 0176).

### Changed

- `scripts/diagnose_rung2_armc.py` now auto-discovers the line-S arm dumps (`--glob`) and reads the
  harness log **by its `#H L` header** instead of by column position — the two harnesses that write that
  file do not share a column order, so the positional reader would silently have scored one arm on
  another's columns.

### Fixed

- Nothing shipped changed. The persistence-null arm is confirmed seed-independent — two runs identical in
  every initialised column over 55 546 tree records (ADR 0176 §5).
