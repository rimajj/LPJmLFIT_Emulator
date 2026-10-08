### Changed

- **Emulator training data switched from the Germany runs to M. Billing's global standard-trait LPJmL-FIT runs;
  the Germany humidity re-run is cancelled ([ADR 0313](docs/decisions/0313-train-on-billings-global-standard-trait-runs-not-germany.md)).** Owner instruction 2026-10-08. 8 independent
  members (own 1000-yr spin-ups) on GFDL-ESM4 historical 1901–2014 + ssp126/245/370 to 2100 (CO2 constant from
  2014, per-tree tables 1985–2014 and 2071–2100) plus 6 GSWP3-W5E5 reanalysis members (1990–2019), all 67 420
  cells, 25 patches, no humidity defect. Trait-vector runs (prescribed traits) excluded. Converted with line X's
  converter by the new `scripts/explore_glob_convert.py` to
  `/p/projects/open/Jamir/esm_land_emulator_data/billing_global/`; `scripts/explore_de_convert.py` now takes the
  `Cell` dtype from its schema and uses a 1e9 year multiplier in its sort checks (byte-identical for Germany).
  ⚠ These runs index cells in `grid.bin` order (Hainich = 28008), not orderA. The 18 pending Germany re-run jobs
  were cancelled before any started.
