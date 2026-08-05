### Added

- **M3 S-side — the coupled demography/trait oracle vs the LPJmL-FIT C truth, closing the P3 gate**
  (ADR 0054). `scripts/extract_biome_slow_oracle.py` builds the C's per-cell demography + trait reference
  for the five biome cells from the annual `ind` parquet (historic, both seeds, 2010–2019) on ADR 0053's
  four bases — tree-only via the imported `TREE_TYPES`, the C's **25-patch ensemble** rather than a per-cell
  total, year-matched, and the writer's `height > 5 m` population — committed as
  `test/testitems/references/M_slow_oracle_{counts,traits}.csv` + `M_slow_oracle_meta.json`.
  `scripts/biome_slow_oracle_probe.jl` scores the coupled S+F+E loop against it in seed1-vs-seed2 noise
  floors, with an `n_prev` teacher-forcing arm that attributes the error.
- A CI `@testitem` guarding the new fixture's **basis** (`biome_coupled_tests.jl`): coverage, the per-patch
  identity `n_mean · npatch == n_cell_total` at `npatch == 25`, a two-extractor population cross-check
  against `M_cells.csv`'s `n_trees`, quantile monotonicity, a strictly positive q05 on every axis (the
  zeroed-grass-row tell) and `Height` q05 ≥ 5 m. The skill measurement itself stays cluster-only — the
  pinned `_t8` pair is 180 MB on `/p/tmp` and CI has no cluster.

### Fixed

- Nothing — no runtime code changed. Every committed baseline stays byte-identical; the probe passes
  `wscal_leafon = true` explicitly rather than moving the default (ADR 0051, still line S's to schedule).
