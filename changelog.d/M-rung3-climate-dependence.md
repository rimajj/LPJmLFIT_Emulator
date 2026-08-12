### Added

- **Rung 3 is now scored under climate change** — the paired per-stem growth harness re-run on the ssp370
  2090–2099 window (ADR 0128). New fixtures `test/testitems/references/M_growth_channel_decomposition_ssp370.csv`
  and `M_growth_channel_climate_response.csv`, new summariser `scripts/growth_channel_climate_response.py`.
  **The fast core's carbon uptake barely responds to warming at the temperate prototype** (it reproduces
  **8 %** of a decline the reference determines to 4 %) and **moves the wrong way in the semi-arid cell**
  (−0.34 of a rise of +77.6 ± 11.6 gC/m²/yr, with the level ratio falling out of band 1.119 → 0.657). The
  tropical cell passes at 1.08; two cells are unresolved because the reference's own response is not
  determined at two seeds.
- **The oracle's own two-seed noise floor on annual tree assimilate**, in both scenarios and on the
  between-window change (`scripts/diagnose_c_assimilate_noise.py`). None existed, so no rung-3 assimilate
  claim had anything to be significant against. Level floor 1.0–12.6 %; the response signal-to-noise is
  24.2 / 8.2 / 6.7 at Hainich / Amazon / Sahel but only 1.8 and 2.8 at the boreal and mediterranean cells,
  which is the quantitative case for the two extra reference seeds.

### Changed

- `scripts/build_biome_stem_growth_reference.py` and `scripts/extract_cell_individuals.py` take a
  `SCENARIO` (or explicit `IND_PARQUET`) knob, and `scripts/biome_sapwood_bg_probe.jl` takes
  `SCENARIO`/`Y0`/`Y1`/`FORCING_DIR`. **All defaults are unchanged**: the historic arm reproduces its
  committed table byte-identically and still passes the 20-number basis gate against ADR 0125's published
  panel. A scenario run writes its own suffixed fixture rather than overwriting the historic one.
