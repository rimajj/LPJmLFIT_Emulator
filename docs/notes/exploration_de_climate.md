# Germany emulator — climate + static inputs (line X exploration, 2026-09-30)

Script: `scripts/explore_de_climate.py` (stages `cy, assemble, yearmap, yearmap_full, gates, verify`; all ran on
SLURM, jobs 2363291 / 2363331 / 2363373 / 2363455, each log ends `JOB DONE exit=0`). Outputs under
`/p/tmp/jamirp/X_de/climate/`. Prep, not a finding about the forest.

## Outputs
| file | key | rows | notes |
|---|---|---|---|
| `cell_year.parquet` | gcm, scen, Cell, Year (asserted unique) | 5 857 282 = 2 GCM x 9067 x (65 Historical + 3x86 ssp) | 110 cols: 72 monthly + 31 annual + 3 trailing-20-yr means |
| `cell_static.parquet` | Cell | 9067 | lon/lat (LPJGRID v3), soil code + name (LPJSOIL), netCDF grid index, 1985-2014 climatology per GCM (prefix `c8514_mpi_` / `c8514_acc_`) |
| `window_clim.parquet` | gcm, scen, Cell, window (unique) | 362 680 | Historical: 1950-1979, 1985-2014; each ssp: 2015-2044, 2045-2070 (no tree table), 2071-2100, 3071-3100 expected (= 2071-2100) and realized per seed |
| `recycled_yearmap_2101_3100_by_seed.parquet` | seed, Year | 2000 | which 2071-2100 year each 2101-3100 year recycled (seed-only; identical across all members of a seed) |
| `gates.json`, `verify.json`, `yearmap_info.json` | | | gate results |

## Units [MEASURED from headers + value ranges; SOURCE from config/log]
All 48 forcing files: LPJCLIM v3, float32 (datatype 3), scalar 1.0, header 51 B, 365 bands, file size == header-implied.
temp = daily mean air temperature, deg C (range -30.8..38.3). prec = mm/day (0..263). humid = RELATIVE humidity,
fraction 0..1 (0.146..1.0; config `relative_humidity: true`, log label `rhumid`). swdown, lwdown = W/m2 daily means
(0.3..366, 124..442). wind = m/s (0..18.8) — **NOT READ by these runs** (run log lists temp/prec/lwdown/swdown/rhumid
only; fire = GlobFIRM, nitrogen off), built only because asked; do not condition on it.
Derived: PET = the C's own `petpar2` Priestley-Taylor with a fixed albedo 0.17 [ASSUMPTION], mm/yr; it reproduces the
run's own monthly PET output at pooled r 0.977, median ratio C/mine 0.96-0.97. VPD = the C's `getvpd` formula on daily
mean T, kPa. Monthly temp/humid/rad/wind = means, prec = sums, noleap calendar.

## Gates
- Headers: 48/48 pass. One file is on a different grid: `windspeed_MPI-ESM1-2-HR_ssp245_germany.clm` has 9133 cells
  (the old grid); remapped by coordinate (9067/9067 matched, max err 6.4e-5 deg; remapped wind r 0.996 vs sibling
  scenarios, a positional read gives r -0.73). Irrelevant to the model, which does not read wind.
- Ranges: all pass, no NaN.
- Independent re-read (48 random gcm/leg/cell/year samples x 52 features, own header parse + plain loops): max
  relative error 5.7e-8 (float32 rounding).
- Historical -> ssp splice (decade 2005-14 vs 2015-24, against 46 within-historic decade steps): temperature,
  precipitation, humidity, shortwave pass for both GCMs. **ACCESS-CM2 longwave has a small step**: +1.3 to +2.3 W/m2
  after removing its temperature dependence, in all three scenarios, 2.2-3.6 sd of the within-historic step and above
  its historic maximum (1.7) in 2 of 3. ~0.5 % of the flux; enters only PET. Flagged, not fixed.
- Scenarios diverge from 2015 on (0 % identical cell-years). Warming 2071-2100 minus 1985-2014 (domain mean, per-cell
  p05-p95): MPI ssp126 +0.88 (0.74-1.02), ssp245 +1.78 (1.52-2.01), ssp370 +2.95 (2.61-3.21); ACCESS ssp126 +2.64
  (2.53-2.91), ssp245 +3.39 (3.22-3.63), ssp370 +4.68 (4.44-5.03) K. ACCESS ssp126 warms more than MPI ssp245.
- 3071-3100: the recycled sequence depends on the seed only (seed 1: 22 distinct years, seed 2: 19); realized window
  means differ from 2071-2100 by -0.19..+0.19 K and -29..+57 mm/yr. MPI ssp370 seed 2 `mpet_3100.nc` was never written
  (consistent with its truncated tree table); its backup file was used.

## Confound check (2071-2100 minus 1985-2014, 9067 cells x 6 members)
- Annual mean temperature: 98.9 % of the variance of warming is between members at the same cell, 1.1 % between cells;
  98.1 % is a uniform per-member offset, the cell x member interaction is 0.8 %. Each cell sees six futures spanning
  3.6-4.1 K (p05-p95 of the per-cell range).
- Correlation of baseline temperature with warming: per member -0.34 to -0.02, pooled -0.03. A linear model on eight
  baseline-climate features explains 54-95 % of a member's SPATIAL warming pattern, but that pattern is small
  (sd 0.09-0.22 K); pooled, baseline climate explains 35 %, member identity alone 98 %.
- Same shape for GDD5, coldest month, water balance, precipitation, VPD (within-cell 92-99 %).
- => This design breaks the earlier confound: the warming signal is carried by the member contrast at a fixed place,
  not by geography. The residual confound is WITHIN one member (warming pattern predictable from baseline), which
  matters only if the emulator is fitted per member.
- Caveat for extrapolation: the fraction of cells whose 2071-2100 mean temperature exceeds the HOTTEST 1985-2014 cell
  in Germany is 5 % (MPI ssp126), 55 % (MPI ssp245), 92-99 % (the other four). Space-for-time within Germany cannot
  cover the future; the emulator must extrapolate in temperature for most future cell-years.
- Year level (what a year-step emulator sees), all members 1985-2100: 27 % of annual-temperature variance is between
  cells, 73 % within cell (time, member, interannual).

## Additions (builder of the tables, 2026-09-30) [MEASURED unless marked]
- **The two GCMs' 1985-2014 climate is the SAME climate (bias-adjusted to one reference):** per-cell MPI minus ACCESS
  annual temperature mean 0.005 K, sd 0.022 K (|d| p95 0.041), r 0.9997; precipitation ratio 1.005 +- 0.013. So each
  cell has ONE baseline and six futures; the member contrast is not contaminated by a baseline difference.
- **Near window (2015-2044 minus 1985-2014):** warming MPI +0.84..+0.91 K, ACCESS +1.38..+1.57 K; within-cell share of
  the warming variance 96.8 % (temperature) but only 45.8 % (VPD) and 72.9 % (annual water balance) — for moisture the
  near-term contrast is mostly geography, not member.
- **The MPI ssp370 seed-2 tree table for 3071-3100 is from a CANCELLED re-run:** job 6746126 (2026-01-30) printed only
  years 3071-3072 and was `CANCELLED AT 2026-01-30T18:14:13`; it overwrote `ind_3100.csv` (10.1 GB). The complete run
  (job 6225106, 2026-01-05, "successfully terminated") survives only as the `*_3100_backup.nc` NetCDF files — there
  is no backup of its tree table. Treat that member's `ind_3100.csv` as 3071 + a partial 3072.
- **The recycled-year sequence (2101-3100) was recovered for BOTH seeds over all 1000 years**, from two independent
  members per seed that agree 1000/1000 and match the per-member 3071-3100 map 360/360
  (`recycled_yearmap_2101_3100_by_seed.parquet`; draws per climate year 25-43 (seed 1) / 16-46 (seed 2)). A
  free-running 2101->3100 test can therefore be driven with the exact climate-year sequence the C used.
- **PET vs the C's own monthly PET (Historical seed 1, 1985-2014):** pooled r 0.977 both GCMs, domain interannual r
  0.996 (MPI) / 0.992 (ACCESS), spatial-climatology r 0.958 / 0.972; C/mine median 0.972 / 0.962 (fixed albedo 0.17
  runs ~3-4 % high).
- **Model-faithful stress drivers:** `vpd_win10_sum` and `tstress_lt_m10/15/20` use the C's accumulation window (days
  15..365, reset on day 14 after that day's increment) — the CLIMATIC factor only; the per-tree gates
  (`aphen > aphen_min`, the wscal threshold) and soil-layer-1 temperature (proxied by air T) are not applied.
