### Added

- **Component-E observational reference (line E, milestone E1; ADR 0070).** PLUMBER2 v1-0 is now staged and
  loadable: `scripts/fetch_plumber2_sites.py` downloads 9 sites (DE-Hai — the Hainich prototype cell — plus
  one tower per biome slot of `test/testitems/biome_coupled_tests.jl`, plus the 4 OzFlux sites that carry
  `LWup`) from the anonymously-readable NCI THREDDS `ks32` collection and writes a `manifest.json` with a
  `sha256` per file; `scripts/validate_e_plumber2_load.py` loads Flux + Met into a model-facing half-hourly
  frame and emits the sanity report — coverage, QC-flag composition, unit/range checks, the observed
  `Rn = LE + H + G` residual and closure slope, daytime Bowen ratio, a mean-diurnal `SWdown` peak-hour check
  of the time axis, and `T_skin` inverted from `LWup` at E's own emissivity — plus
  `halfhourly_/daily_/diurnal_<site>.parquet` (the daily gate *and* the retained sub-daily cycle).
  `config/paths.yaml` `data.energy_reference` is no longer a TODO.

### Notes

- **T_skin is not observable at Hainich from PLUMBER2**: its FLUXNET2015/LaThuile-sourced files carry no
  upwelling longwave. T_skin validation moves to the OzFlux subset (ADR 0070); Component E's LE/H/T_skin stay
  `[ASSUMPTION]` until milestone E4.
- Observed daytime Bowen ratios reproduce the ordering `biome_coupled_tests.jl` asserts: GF-Guy 0.30 <
  AU-Rob 0.52 ≈ AU-How 0.54 < AU-Tum 0.80 < DE-Hai 0.96 < FI-Hyy 1.23 < FR-Pue 1.70 < US-SRM 3.31 < AU-ASM 4.57.
