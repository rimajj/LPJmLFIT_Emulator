### Fixed

- **The F-vs-C canopy-cover comparison scored the wrong one of the C's two FPC outputs, and correcting it
  flips the sign in four of five biome cells** (ADR 0060). LPJmL-FIT writes both `a_fpc` (the patch-mean sum
  of individual crown covers, `fpc_tree.c:28`) and `a_fpc_stand` (per-PFT leaf area through a single
  Beer–Lambert saturation over the whole patch) — different functional forms of different arguments,
  differing 1.5–2.3× in the same cell-year. The fast core computes the crown form, so `a_fpc` is the
  comparable output; the oracle used `a_fpc_stand`. **Withdraws ADR 0053 finding 4** ("the fast core
  under-predicts tree FPC in all five cells, 0.31–0.72×"): on the comparable output it *over*-predicts in
  four cells (1.05–1.47×) and under-predicts only in the semi-arid Sahel (0.54×).

### Added

- `fpc_tree_crown` (and `fpc_grass_crown` on the monthly table) in
  `test/testitems/references/M_fdiff_oracle_biomes{,_annual}.csv`, plus `fpc_tree_crown_mean`,
  `fpc_grass_crown_mean` and `crown_over_stand_fpc` in `M_fdiff_oracle_meta.json`. Appended last, with both
  `basis` strings now naming which functional form they are — **every pre-existing column is byte-identical**
  (verified row-by-row), so no committed baseline moves.
- `scripts/biome_fdiff_oracle_probe.jl` PART 6: year-matched FPC ratios on the crown basis, the `>5m_frac`
  column (the fraction of the C's own crown cover that lives in the stems above 5 m the `ind` writer
  actually emits — 0.71 at boreal and the Sahel, so no ratio may be read against 1.0), and F's crown cover
  at **t = 0**. That last column separates the canopy reconstruction from the fast core's growth and shows
  the **reconstruction is faithful (1.00–1.04 in all five cells)**, eliminating it as a cause.
  `biome_slow_oracle_probe.jl`'s canopy report now prints both bases side by side.
