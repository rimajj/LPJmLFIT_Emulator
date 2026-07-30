### Added

- **M3 F-side — a per-cell F_diff-vs-C oracle for all five biome cells** (ADR 0053). The C's daily
  `d_gpp`/`d_transp` are grid-cell totals over **all** PFTs while the coupled driver's canopy is tree-only,
  so the grass share was removed **exactly** rather than caveated: four cheap single-cell re-runs
  (`CELL=<c> RUNTAG=M_grass_val scripts/run_fdiff_grass_gpp_cell.sh`, ~9 s each) added the custom per-PFT
  daily grass GPP output, giving `gpp_tree = d_gpp − d_grass_gpp`. Grass carries **42.4 %** of GPP at boreal
  Siberia, 28.4 % mediterranean, 19.3 % Sahel, 5.8 % Hainich, 0.2 % Amazon.
  - `scripts/extract_biome_fdiff_oracle.py` → the committed `test/testitems/references/M_fdiff_oracle_biomes.csv`
    (+ `_meta.json`): per-cell monthly climatology 2010–2019 of tree GPP, ET and its three components,
    tree FPC and stand LAI, each with its basis recorded and its splittability stated.
  - `scripts/biome_fdiff_oracle_probe.jl` → the F side, on the C's own **25-patch ensemble** basis, at
    ADR 0051's `wscal_leafon = true` (passed explicitly; the package default stays `false`).

### Fixed

- The F-side comparison now runs the **patch ensemble** instead of the modal patch. The modal patch that
  `run_coupled_biomes.jl` / `wscal_leafon_probe.jl` select is systematically denser than the 25-patch
  ensemble mean the C reports — FPC **1.72×** (Sahel), 1.48× (boreal), 1.19×, 1.14×, 1.12× — i.e. a
  reference-basis artifact the same size as the flux biases being measured.

### Notes

- No `src/` change; every committed baseline is byte-identical. `wscal_leafon` remains `false` by default —
  flipping it is still the open two-sided integration point with line S (ADR 0051).
