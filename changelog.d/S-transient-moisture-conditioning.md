### Added

- Component S — the six moisture descriptors can now be built **per cell and per year** for both scenarios
  (`scripts/build_transient_boundary.py`, opt-in `MOISTURE=1`), which is the data layer the emulator needs
  before it can respond to a changing climate at all. Previously they were frozen at a single present-day
  value per cell, identical in every year and in both scenarios, so no warming signal could reach the
  recruit model through them (ADR 0106 §5, milestone S2).
  Built and validated for all **67 420** cells: `cell_year_env_historic_w20.parquet` (2000–2019) and
  `cell_year_env_ssp370_w20.parquet` (2020–2100). The signal is real — global mean humidity deficit
  **+20.4 %** and evaporative demand **+4.9 %** from 2019 to 2100.
  The formulas are **ported verbatim** from the original feature package and **gated** on reproducing the
  frozen per-cell values a 20-year window ending 2019 must reproduce; all six pass at 1e-7. The default
  output is unchanged, so the existing two-column boundary tables stay byte-identical.
