---
name: obsclim-cell-remap
description: Remap a gridded lat/lon climate variable (ISIMIP3a obsclim GSWP3-W5E5, WFDE5, a raw GCM NetCDF) onto the model's orderA cell indices, and PROVE the mapping with a round-trip against the model-grid `_test.clm` the LPJmL-FIT run actually read. Use whenever sourcing a NEW per-cell forcing (wind, surface pressure, any variable the run never used), converting a leap calendar to the model's noleap-365, resolving an orderA cell index to lat/lon (or the reverse), reading a `.clm` header by hand, or debugging a per-cell input that looks physically absurd. Names scripts/remap_wind_psurf_cells.py, grid.nc cellid, temperature_test.clm, the 0-based .clm datatype codes, ADR 0071.
---

# obsclim-cell-remap — get a gridded variable onto orderA cells, and prove it

The recurring shape: a variable exists as global 0.5° lat/lon NetCDF, the model addresses cells by **orderA
index**, and a wrong mapping is *silent* — the numbers stay plausible while pointing at the wrong continent.
Worked example (line E, milestone E2, ADR 0071): `scripts/remap_wind_psurf_cells.py`, which sources daily
wind + surface pressure and carries its own gate.

```bash
# 5 biome cells × 2010-2019, full validation battery, writes the per-cell CSV fixtures (≈3 min)
scripts/sbatch_python.sh E-windps scripts/remap_wind_psurf_cells.py
# one cell, one year, report only
CELLS=temperate_hainich=42490 YEARS=2010-2010 NO_WRITE=1 \
  /home/jamirp/.conda/envs/py311_new/bin/python3 scripts/remap_wind_psurf_cells.py
```

## The route (do it in this order)

1. **orderA cell → (lat, lon)** from the global run's `grid.nc` `cellid[lat, lon]`
   (`/p/tmp/jamirp/esm_land_daily/daily_2000_2019_global_c0_67419_seed1/output/grid.nc`). `np.argwhere(cellid
   == cell)` must hit **exactly once**. Never compute the index from lat/lon arithmetic: Hainich is orderA
   **42490** in the global grid, **28008** in the repo-default SINGLESITE grid, and orderA 28008 is Sonoran
   desert.
2. **Match the source axes by VALUE with an exactness assertion** (`|axis[i] − target| < 1e-6`), not by
   arithmetic. Source-grid conventions differ per product: ISIMIP3a obsclim is lon ascending / **lat
   descending** (89.75 → −89.75, 360 rows), while the LPJmL-prepared obsclim `.nc` is **lat ascending and only
   280 rows** (−55.75…83.75, land band). Arithmetic that works on one is wrong on the other; an exactness
   assertion turns a silent 0.5°–140° offset into a crash.
3. **Calendar**: obsclim raw is `proleptic_gregorian` (leap), the model forcing is **noleap-365**. Drop every
   29 February — then assert the year has exactly 365 values. The LPJmL-*prepared* files already are noleap.
4. **Read once per decadal file, slice the year window** — obsclim is chunked `[1, 360, 720]` + zlib, so a
   single-cell full-series read decompresses every timestep (~8 s per cell-decade). Per-year reads multiply
   that; per-cell-per-file reads are the sweet spot.

## The gate — never trust a remap without it

- **(a) independent lookup**: your index arithmetic vs `xarray`'s label-based
  `.sel(lat=…, lon=…, method="nearest")`. Expect `max|Δ| = 0` exactly.
- **(b) round-trip on a variable present in BOTH representations** — *this is the one that matters*: the
  source NetCDF at (lat, lon) vs the **model-grid `_test.clm`** for the same cell-year, e.g. obsclim `tas`
  (°C) vs `/p/projects/waldspektrum/priesner/clustering/global/temperature_test.clm`. Agreement proves the
  lat/lon ↔ orderA mapping *against the file the C run actually consumed*. [VERIFIED 2026-07-28]
  `max|Δ| = 0.000 °C` over 365 days at all five biome cells (means −9.55 to +30.23 °C).
- **(c) pipeline/calendar cross-check** where a second, independently-produced version exists (e.g. the
  LPJmL-prepared noleap wind). Mind quantization before calling a mismatch a bug — see below.
- **(d) an observational sanity check** where a tower exists (PLUMBER2, skill `plumber2-reference`). Expect an
  **offset, not equality**: at Hainich the 0.5° cell gives wind −10.1 % vs the DE-Hai tower and psurf
  +1649 Pa, i.e. a cell-mean elevation ≈143 m below the tower's 430 m. Interpreting that offset (rather than
  "fixing" it) is the point — and it is *why* E4 must drive with tower forcing when scoring tower fluxes.

## Traps (each cost a debugging round)

- **`.clm` datatype codes are 0-BASED**: `0=byte 1=short 2=int 3=FLOAT 4=double`
  (`scripts/build_transient_boundary.py::_DT`). Off by one ⇒ `temperature_test.clm`'s float32 is read as int32
  and the "temperature" comes out ~5.9e8 °C. Header layout: `name[7]` + 7 ints (`version order firstyear nyear
  firstcell ncell nbands`) + 3 floats (`cellsize_lon`, **scalar**, `cellsize_lat`) + datatype ⇒ **HDR 51** for
  v3; v1/v2 have no datatype field ⇒ **HDR 43**, int16, and the `scalar` is load-bearing (0.1 ⇒ °C×10).
  `temperature_test.clm` = v3, order 1 (YEARCELL), firstyear 1901, ncell 67420, nbands 365, scalar 1.0, code 3.
- **The LPJmL-prepared obsclim wind is QUANTIZED to 0.01 m/s** (its `.clm` twin is int16·0.01). A raw
  `max|Δ| ≈ 5e-3` against a full-precision source is exactly ½ a quantization step — compare
  `round(mine, 2)` before declaring a mismatch.
- **Do not `git stash -u` while a SLURM job is writing fixtures into the worktree** — the stash removes the
  files the job just wrote (they come back on `stash pop`, but a mid-write race is real). Rebase before
  submitting, or after the job's `JOB DONE` line.
- **Product coverage is not uniform**: the raw SSP370 GCM set has `sfcwind` but **no `ps`**; WFDE5_CRU `PSurf`
  ends in 2018; there is no LPJmL-prepared `ps` at all. Check for the variable before planning around it.

## Where the outputs go

Per-cell daily fixtures are committed under `test/testitems/references/` with a **new** family name
(`wind_psurf_<biome>.csv`), matching the cells and decade of the existing `biome_forcing_<biome>.csv` — never
regenerate an existing baseline (that is an integration point, guardrail 4). Paths and provenance go to
`config/paths.yaml`; the decision goes to an ADR from your line's block.
