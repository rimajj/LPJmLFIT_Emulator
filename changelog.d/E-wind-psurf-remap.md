### Added

- **Wind + surface pressure for Component E (line E, milestone E2; ADR 0071).**
  `scripts/remap_wind_psurf_cells.py` remaps daily `sfcwind` [m/s] and `ps` [Pa] from the ISIMIP3a obsclim
  GSWP3-W5E5 tree — the same climate family the LPJmL-FIT run itself consumed — onto the model's orderA cells
  (`grid.nc` `cellid` → lat/lon → source axis, matched by value with an exactness assertion), dropping 29
  February for the model's noleap-365 calendar. Writes the committed per-cell fixtures
  `test/testitems/references/wind_psurf_<biome>.csv` (`year,doy,wind,psurf`, 2010–2019 × 365 d) for the same
  five biome cells as `biome_forcing_<biome>.csv`. `config/paths.yaml`
  `lpjml.energy_extra_inputs.{sfcwind,ps}` are no longer TODOs.
- The script carries its own four-part gate, all **PASS at all five cells**: exact agreement with an
  independent `xarray` label lookup; an obsclim-`tas`-vs-`temperature_test.clm` round-trip
  (`max|Δ| = 0.000 °C` over 365 days) that proves the lat/lon ↔ orderA-cell mapping against a file the C run
  actually read; calendar agreement with the LPJmL-prepared noleap wind (to its 0.01 m/s quantization); and a
  physical cross-check at Hainich against the DE-Hai tower — grid wind −10.1 %, psurf +1649 Pa, i.e. a 0.5°
  cell mean ≈143 m below the tower.

### Notes

- **SSP370 surface pressure remains unsourced** — the raw MPI-ESM1-2-HR set has `sfcwind` but no `ps`, and no
  LPJmL-prepared `ps` exists on the cluster. The future branch of E stays on a fixed pressure.
- The tower comparison shows grid-cell forcing ≠ tower forcing, so E4 must drive with the **tower's** wind and
  psurf when scoring against tower fluxes, and with these remapped fields for model-grid runs.
- Feeding the fields into the coupled driver touches `src/run.jl` (line M's path) — an integration point, not
  part of this change.
