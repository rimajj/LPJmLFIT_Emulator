### Added

- **Rung 3 (line M): F's canopy growth measured PAIRED PER STEM against LPJmL-FIT's own individuals, five
  biome cells, 2010–2019** (ADR 0125). Enabled by establishing that `(Cell, Patch, ID)` is a *stable
  cross-year individual identity* in the annual `ind` output (13 152 stem-years: `Age` +1 on all 10 323
  pairs, immutable traits bit-identical, only 8 vanishings and all within 0.4 m of the writer's 5 m cut).
  New: `scripts/build_biome_stem_growth_reference.py` (+ the committed per-cell/per-year accounting
  `test/testitems/references/M_stem_growth_reference.csv`), `scripts/biome_canopy_growth_probe.jl`,
  `scripts/diagnose_oracle_run_divergence.py`.
- `test/testitems/references/M_individuals_<cell>_2010.csv` gain `id` and `age` columns, appended last;
  every pre-existing value verified byte-identical row-by-row.

### Fixed

- `scripts/extract_cell_individuals.py` no longer eats the shared per-cell registry. It rewrote
  `M_cells.csv` from its own ten-column header and dropped every row whose field count differed, so a
  re-run would have silently deleted the six columns `extract_cell_slow_init.py` appends (the pinned
  Component-S per-cell seed: `n_init`, `age0`, the four-column boundary). The merge now preserves columns
  and comment lines it does not own; a re-run over the live registry is byte-identical.
