### Added

- **Per-cell input provisioning for the multi-cell coupled S+F+E driver ([ADR 0050](docs/decisions/0050-per-cell-input-provisioning.md)) — milestone M1.**
  The coupled driver was already N-cell-agnostic, but all five biome cells reused **Hainich's** soil column
  and **Hainich's** canopy. Each cell now carries its own inputs, produced by two new committed extractors:
  - **`scripts/extract_cell_soilcolumn.py`** — the per-layer soil column that previously had *no* generating
    script at all. `whcs_mm` = the C's own `WHC_NAT` output (the patch-ensemble-mean `whc` fraction,
    `soilpar_output.c:42`) × the cell-invariant layer thickness read from `depth_bnds`, reduced by a mean over
    all 240 monthly steps; `rootdist` = the fpc-weighted mean over the cell's living trees of each
    individual's own `getrootdist.c` profile, using FIT's own `beta_root` with the rooted depth recovered by
    inverting the emitted `D95` (`R = ln(1−(1−β^D95)/0.95)/ln β`, [VERIFIED] `R ≥ D95` and `R ≤ 2000 cm` for
    every individual in all five cells). **Gate: re-extracting cell 42490 reproduces all 23 printed rows of
    the committed `hainich_soilcolumn.txt` byte-identically** (`max|Δwhcs| = 3.7e-5 mm`,
    `max|Δrootdist| = 4.3e-7`) — which required finding that the fixture came from the *single-cell* run, not
    the 512-task global one (they differ by 1.6e-4 relative in layer 0 under `-DPERMUTE`), and that the time
    mean must accumulate in float32.
  - **`scripts/extract_cell_individuals.py`** — the N-cell generalization of `extract_fdiff_individuals.py`
    (whose reconstruction physics it imports rather than duplicates). Reproduces the committed Hainich
    numbers exactly (`cell_fapar_leafon` 0.8339690, 297/272/25 individuals) and validates every other cell
    against **that cell's own** C daily FAPAR from a fresh single-cell re-run.
  - `scripts/extract_biome_forcing.py` now holds **the** canonical N-cell registry (`cells_from_env`), which
    both new extractors import, and `references/M_cells.csv` carries cell/lat/lon from `grid.nc` `cellid`, so
    the hard-coded `BIOMES` dict and hard-coded latitude list are gone. Its committed forcing output is
    byte-identical after the refactor.

  The emergent rooting gradient comes straight out of FIT's trait distributions: top-1 m root fraction
  99.3 % (semi-arid Sahel) → 88.6 % (boreal) → 87.8 % (Hainich) → 61.5 % (mediterranean) → 53.2 % (tropical
  Amazon), effective D95 72 cm → 690 cm. `scripts/run_coupled_biomes.jl` now runs both the per-cell and the
  legacy common-Hainich configuration, so the **vegetation+soil** contribution is separable from the climate
  contribution for the first time: +10.8 W/m² LE in the Amazon, −7.6 W/m² in the Sahel, mediterranean Bowen
  1.27 → 0.65. Energy still closes to ~1e-14 W/m² in every cell.
  Gated by `test/testitems/biome_coupled_tests.jl` (now two test items: the per-cell inputs are well-formed
  **and pairwise distinct** — the guard against silently falling back to one cell's inputs — plus the
  unchanged energy-closure and climate-partitioning assertions). Suite 106,987 pass / 0 fail / 4 broken.
  `hainich_soilcolumn.txt` and `hainich_individuals_2010.csv` are untouched, so no committed baseline moves.
  Honest limitations: the canopy reconstruction is leaf-on, so reconstructed/C peak FAPAR runs ~1.3–1.6
  across the five cells (Hainich 1.60); `getrootdist`'s permafrost redistribution of roots below
  `mean_maxthaw` is not ported (no output carries the thaw state); and every biome still runs beech ANGIO
  PFT parameters (milestone M5).
  \+ skill: `provision-coupled-cell`.
