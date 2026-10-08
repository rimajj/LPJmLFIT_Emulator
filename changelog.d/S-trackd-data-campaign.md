### Added

- **Track D data campaign of the original model, launched ([ADR 0246](docs/decisions/0246-track-d-real-scenarios-two-controls-four-members-on-a-contiguous-block-panel.md)).**
  A fixed global panel of 105 contiguous 10-cell blocks (1 050 cells, 20 climate strata, 96 distinct 15° tiles;
  `test/testitems/references/S_D0_panel_blocks.csv`), run under real ISIMIP3b climate of five climate models ×
  ssp126/ssp370/ssp585 (65 new orderA forcing files, procedure gated by re-deriving the ground truth's MPI file
  byte-identically), two constant-climate controls, and four members (two of them new 1000-year spin-ups), with
  per-tree tables carrying trees below 5 m and real per-tree GPP, and daily water/carbon fluxes on six legs. The
  twelve Germany members are re-run 2045-2100 with the humidity setting fixed, with a per-tree table for 2045-2070
  for the first time; the four ssp245 members wait on an automatic row gate of the Feb-2026 build. Outputs are
  collected into parquet under `/p/projects/open/Jamir/esm_land_emulator_data/trackD/` by chained jobs. Tooling
  `scripts/trackd_*`; procedure and traps in the new skill `trackd-data`.
