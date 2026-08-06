### Added

- **Component S — the recruit-trait moisture conditioning can now vary with the climate (ADR 0108).** Six of
  the fourteen numbers the recruit-trait sampler is conditioned on describe a cell's moisture *climate*, and
  they were a per-cell average of 2000-2019 weather reused unchanged for every year of every scenario — so a
  tree establishing in 2100 was conditioned on its cell's present-day moisture climate. (The sampler is not
  otherwise blind to moisture: four of the remaining eight numbers do change year by year, and measured
  against the original model the emulator's per-cell trait shift between scenarios already tracks the real one
  with a slope of 0.85 for leaf area per unit mass but only 0.16 for rooting depth — partial, and worst
  exactly where a moisture climate should matter most.) Three additions open the frozen channel, all switched
  off by default:
  - `ENV_WINDOW=W` in `scripts/build_slow_runtime_table.py` builds the tail per cell **and year** from the
    trailing-W-year tables instead of averaging it away.
  - `live_flux_cond_env_series` in `src/components/slow.jl` is the matching runtime policy, advancing the tail
    one row per simulated year in step with the existing time-varying temperature tail.
  - every training table now writes a per-row `years.i64` alongside `cells.i64`, because the year cannot be
    recovered from a finished table after the fact (measured: the per-cell-year columns are ambiguous between
    two years for ~140 of 1.35 M historic cell-years).
- `scripts/run_moisture_conditioning_arm.sh` runs the comparison as one job: one base table, the old and the
  new tail appended to it, so the two differ in those six columns and nothing else and are scored on identical
  cell folds.
- `scripts/diagnose_env_window_gate.py` is the gate: with the switch off the builder reproduces the previous
  version's output byte-for-byte, with it on only the six columns move, and every probed row carries its own
  cell-and-year values re-derived independently from the source data.

### Changed

- `scripts/pool_slow_tables.py` now refuses to pool two scenarios whose conditioning tails were built on
  different time bases — a static half and a time-varying half would fabricate part of the scenario contrast —
  and carries the per-row year through to the pooled table.
