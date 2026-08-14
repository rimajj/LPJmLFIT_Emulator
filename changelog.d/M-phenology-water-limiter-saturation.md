### Added

- Two harnesses that price the GSI water limiter's two v1 simplifications with no simulation
  (line M, ADR 0139): `scripts/diagnose_phenology_water_inflection.py` (a per-stem parquet scan of
  the C's own output — variability audit, inflection bias, within-group spread, a basis-free
  water-availability sweep, and a saturation/straddle panel with a script-computed verdict) and
  `scripts/run_soiltemp_gate_cells.sh` + `scripts/diagnose_phenology_soiltemp_gate.py` (five
  single-cell C re-runs adding the daily `soiltemp1` output — the gate's own `patch->soil.temp[0]` —
  scored for gate-verdict flips weighted by the light at stake and damped by the filter's own
  low-pass response).

### Fixed

- `FDiff.pft_phenparams`' docstring claimed its `wscal_base` values are realised median `minwscal`
  traits. They are `100 ×` the par file's interval `"median"` field, and for PFT ids 3, 5 and 6 that
  field **exceeds the interval's own `high`** (ADR 0047's trap), so it is not a possible central
  value — measured against the C's own per-stem output it is 9.1 / 12.5 / 21.7 percentage points too
  high. The docstring now carries the par-file and realised values side by side.
- The `rollout_daily_canopy` comment that passed air temperature into the water filter's
  soil-temperature gate without remark now records the measurement: layer-1 soil temperature tracks
  air with a best-fit lag of **0 days** at four of the five biome cells, so the substitution is exact
  there, and `boreal_siberia`'s difference is a +4.40 °C snow/damping offset rather than a lag.

### Changed

- No behaviour change, no new flag. ADR 0139 closes item (c2) of the photosynthesis shortlist (its
  premise of a substantial soil-vs-air lag is refuted) and narrows item (c1) to a parameter defect
  plus a single binary case: at `semiarid_sahel` the realised water availability falls between F's
  inflection and the C's, so F's water filter reads 1.0000 where the C's reads 0.0000. Item (c) is
  struck as *the* compensating error — it binds at one cell, in the direction that makes F's
  over-production larger.
