#!/usr/bin/env python3
"""build_swc_soilmoist_feature.py — derive the RUNTIME-CONSISTENT `soilmoist` feature per (Cell, Year)
from a daily-`swc` LPJmL-FIT run, replacing the constant proxy in build_slow_runtime_table.py.

WHY (train/inference consistency — the documented slow-DRF trap):
  The coupled runtime feeds Component S `soilmoist = sum(state.w) / length(state.w)` (slow.jl:498) — the
  UNWEIGHTED mean over the NSOILLAYER=23 soil layers of the fractional soil-water content `w` (fraction of
  WHC). The training table must be built the SAME way. This script reduces the daily `d_swc.nc` `SWC`
  (fractional saturation, [time, layer=23, lat, lon]) to, per (Cell, Year), the mean over
  (days-in-year × 23 layers) — i.e. the annual-mean of the runtime's layer-mean w. (The plan's
  growing-season / EOY decomposition is a future refinement; the current runtime uses a single annual
  scalar, so this matches it exactly.)

CELL MAPPING (avoids the orderA index trap — cf. Hainich = orderA 42490, NOT 28008):
  grid.nc carries `cellid[lat, lon]` = the authoritative 0-based orderA Cell index at each grid point.
  We map each valid grid point to its Cell via `cellid` — no reliance on flatten order. VERIFIED:
  cellid[51.25, 10.25] == 42490 (Hainich).

CALENDAR: files use a noleap 365-day calendar; `time` (decode_times=False) is integer days since
  firstyear-1-1, so year-index = day // 365 and calendar year = firstyear + that. Matches
  water_closure_check.py.

Memory-safe: dask-lazy, one year (one time-slice) reduced at a time; never materializes the full
  ~135 GB [time, layer, lat, lon] cube.

Env:
  RUN_DIR    daily run output dir holding grid.nc + d_swc.nc  (required)
  OUT        output parquet path                              (default RUN_DIR/cell_year_soilmoist.parquet)
  FIRSTYEAR  calendar year of time index 0                    (default 2000; use 2020 for the SSP370 run)
Usage (heavy — submit to SLURM, do NOT run on the login node for the full global cube):
  RUN_DIR=/p/tmp/jamirp/esm_land_daily/daily_2000_2019_global_c0_67419_seed1/output \
  FIRSTYEAR=2000 python3 scripts/build_swc_soilmoist_feature.py
  SUBSET_DEG=3 ...  # optional: restrict to a lat/lon box around Hainich for a fast correctness check
"""

from __future__ import annotations

import os
import sys

import numpy as np
import polars as pl
import xarray as xr

NSOILLAYER = 23  # state.jl: const NSOILLAYER = 23 — must match the runtime layer count exactly


def main() -> int:
    run_dir = os.environ.get("RUN_DIR")
    if not run_dir:
        print("FATAL: set RUN_DIR (daily run output dir with grid.nc + d_swc.nc)", file=sys.stderr)
        return 2
    firstyear = int(os.environ.get("FIRSTYEAR", "2000"))
    out = os.environ.get("OUT", os.path.join(run_dir, "cell_year_soilmoist.parquet"))
    subset_deg = os.environ.get("SUBSET_DEG")  # optional fast check around Hainich

    grid = xr.open_dataset(os.path.join(run_dir, "grid.nc"))
    cellid = grid["cellid"]  # [lat, lon], float, 0..67419 where valid; NaN elsewhere

    swc = xr.open_dataset(os.path.join(run_dir, "d_swc.nc"), decode_times=False, chunks={"time": 365})
    da = swc["SWC"]  # [time, layer, lat, lon], fractional saturation
    if da.sizes["layer"] != NSOILLAYER:
        print(f"FATAL: SWC has {da.sizes['layer']} layers, expected NSOILLAYER={NSOILLAYER}", file=sys.stderr)
        return 3

    if subset_deg:
        d = float(subset_deg)
        da = da.sel(lat=slice(51.25 - d, 51.25 + d), lon=slice(10.25 - d, 10.25 + d))
        cellid = cellid.sel(lat=slice(51.25 - d, 51.25 + d), lon=slice(10.25 - d, 10.25 + d))

    tvals = swc["time"].values.astype(np.int64)
    year_idx = tvals // 365
    years = np.unique(year_idx)

    cid = cellid.values  # [lat, lon]
    valid = np.isfinite(cid)  # [lat, lon] mask of real cells
    cells = cid[valid].astype(np.int64)  # [ncell] orderA index, grid order

    rows = []
    for y in years:
        day_pos = np.nonzero(year_idx == y)[0]
        # mean over (days-in-year, 23 layers) -> [lat, lon]; dask streams the ~6.8 GB/yr chunk
        sm = da.isel(time=slice(int(day_pos[0]), int(day_pos[-1]) + 1)).mean(dim=["time", "layer"]).values
        rows.append(
            pl.DataFrame(
                {
                    "Cell": cells,
                    "Year": np.full(cells.shape, firstyear + int(y), dtype=np.int64),
                    "soilmoist": sm[valid].astype(np.float64),
                }
            )
        )
        print(f"  year {firstyear + int(y)}: {len(cells)} cells, "
              f"soilmoist mean={float(np.nanmean(sm[valid])):.4f}")

    tbl = pl.concat(rows).sort(["Cell", "Year"])
    tbl.write_parquet(out)
    print(f"wrote {out}: {tbl.height} (Cell,Year) rows, "
          f"soilmoist range [{tbl['soilmoist'].min():.4f}, {tbl['soilmoist'].max():.4f}]")
    # correctness anchor: Hainich (orderA 42490) should be present with a plausible fraction in (0,1)
    h = tbl.filter(pl.col("Cell") == 42490)
    if h.height:
        print(f"  Hainich(42490) soilmoist by year: {h['soilmoist'].to_list()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
