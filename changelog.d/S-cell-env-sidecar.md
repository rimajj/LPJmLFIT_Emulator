### Added

- `scripts/build_slow_cell_env_sidecar.py` emits `tables/cell_env.parquet` — the per-cell env conditioning
  sidecar the 14-column recruit-trait copula needs to be coupled-runnable at all. Until now nothing in the
  runtime supplied those six values: every caller hand-built them from `cell_year_feats.parquet` inside a
  bespoke script, which is unreachable from CI and basis-sensitive. Both open handoffs listed this as a
  standing blocker. 67 420 cells (a superset of the pinned table's 58 766, so line M can provision any grid
  cell), 2.0 MiB, with a manifest recording the basis, the year span, and the column order a positional
  consumer must respect.

### Fixed

- The sidecar's gate caught a real train/inference shift on its first run, which is why it exists. Four of the
  six env columns are stored `Float32` in `cell_year_feats.parquet` and polars' `group_by().mean()`
  accumulates in `Float32`, so the obvious aggregation lands ~3.35e-07 relative away from the values the
  shipped artifact was conditioned on — 199 093 of 200 000 probed rows differed, max |diff| 7.63e-05 on
  `eco_diag_pet_mean` (exactly `5·2⁻¹⁶`). Casting to `Float64` before the mean reproduces the shipped
  `Xc.f64` tail **bit-exactly**. The gate compares against the shipped `Xc` rather than against a re-run of
  the producing code, because the latter would be circular. Recorded in CLAUDE.md §4.
