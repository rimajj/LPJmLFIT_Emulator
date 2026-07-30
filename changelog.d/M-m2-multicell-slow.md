### Added

- **Line M / M2 — the flux-driven Component S now runs in the MULTI-CELL coupled loop.** All five biome
  cells (boreal / temperate / mediterranean / semi-arid / tropical) build their own `FluxDrivenSlowEmulator`
  from their own `n_init` / `age0` / slow boundary — folded into the committed `references/M_cells.csv` by
  `scripts/extract_cell_slow_init.py` — plus their own per-cell `ClimBuf` for the transient bioclimatic
  boundary. Previously the driver ran `slow=nothing`, so the coupled evidence for S was single-cell
  (Hainich) while the global evidence was offline-only.

  New gate (third test item in `test/testitems/biome_coupled_tests.jl`), asserted in **every** cell: carbon
  at the S↔F handoff ≤1e-6·C_scale and <1e-6; energy <1e-6 W/m²; deterministic under seed; a fixed-N control
  proving F alone cannot move tree N; and the `ClimBuf` driving only the two climate axes
  (`soil_depth`/`co2` pass through) with its recomputed `gdd5` ordering the cells the same way their baked
  C-derived `gdd5` does.

### Changed

- **Line M re-pinned the Component-S artifact to the `_t8` generation** (ADR 0023 — a deliberate, two-sided
  adoption): `drf_forest_global_pooled_w20_t8.drf` + `recruit_copula_global_pooled_w20_t8.rcop`, sha256s
  recorded in `lines/M/STATE.md`. `_t8` re-derives the population on the ADR-0035 feature bases, so a
  *coupled* run no longer inherits the retired `soilmoist`/`lai` bases; the previous `pooled_w20` pin had
  never been trained on the `semiarid_sahel` cell at all. Verified independently rather than from the
  handoff note — both halves deserialize, the meta `colnames`/`cond_cols` tails match
  `flux_feature_vector`/`live_flux_cond`, `nfeat = 8` per axis forest confirms ADR 0036's diagnostic axes
  are absent from the `.rcop`, and 5/5 cell coverage was read out of the parquet directly.

- `scripts/extract_cell_slow_init.py` emits round-trippable `repr` (`%.17g`) values instead of `%.6f`.
  These feed DRF split thresholds, and `%.6f` truncated Hainich's `eco_diag_gdd_5` 1863.695068359375 →
  1863.695068. With exact output, `M_cells.csv`'s Hainich row is bit-identical to the committed
  `drf_forest_hainich_meta.txt`'s own baked boundary/`n_init`/`age0`, which upgrades the provenance check
  from a tolerance to an exact equality.

### Fixed

- **The 5-biome energy/partitioning test could not detect a driver-level fallback** (M1 review debt #1): it
  passed verbatim when all five cells reverted to Hainich's soil and canopy, because its assertions were
  closure, finiteness and qualitative orderings. It now pins each cell's own mean LE and GPP (±2 % / ±3 %,
  against a 24.9…119.3 W/m² between-cell spread) and asserts the five signatures are mutually
  distinguishable at those tolerances.
