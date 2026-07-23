#!/usr/bin/env python3
"""build_laistand_lai_feature.py — derive the RUNTIME-CONSISTENT `lai` feature per (Cell, Year) from a
C `LAI_STAND` annual run, replacing the per-crown-sum proxy in build_slow_runtime_table.py.

WHY (train/inference consistency):
  The coupled runtime feeds Component S `lai = Σ leaf_c·sla·nind` — the FIT STAND LAI (slow.jl:489), NOT
  the sum of per-crown individual LAI (`ind.LAI`, which double-counts overlapping crowns). The C model
  writes exactly that stand quantity as the annual `LAI_STAND` output (`lai_stand.nc`). This script maps
  that gridded annual field to per (Cell, Year) `lai`. Companion to build_swc_soilmoist_feature.py.

CELL MAPPING — use the GLOBAL run's grid.nc, NOT the LAI_STAND run's:
  grid.nc `cellid[lat, lon]` is the authoritative 0-based orderA Cell index (VERIFIED cellid[51.25,10.25]
  == 42490, Hainich). The LAI_STAND (ANNUAL_ONLY) run's OWN grid.nc has been observed corrupt (all-NaN),
  so GRID defaults to the known-good global daily run's grid.nc. Geometry is identical 280x720 orderA.

HARD FILL GATE (the reason this is a separate step, not folded into the table build):
  `lai_stand.nc` `LAI[time, lat, lon]` uses a large fill (~9.969e36) for unwritten/ocean cells, and a
  TIMED-OUT or incomplete run leaves the whole field at fill. This script REFUSES to write unless the
  valid-cell count == 67420 AND a real (non-fill, finite, < LAI_MAX) fraction of the field exists — so a
  build that consumes this parquet can never be silently poisoned by fill data.

CALENDAR: LAI_STAND is annual; `time` has one step per output year. Coords may be fill, so map year-index
  i (0..nyear-1) POSITIONALLY -> calendar year FIRSTYEAR + i.

Env:
  RUN_DIR    LAI_STAND run output dir holding lai_stand.nc         (required)
  GRID       authoritative grid.nc                                  (default: the global daily run's grid.nc)
  FIRSTYEAR  calendar year of time index 0                          (default 2000; 2020 for SSP370)
  OUT        output parquet                                         (default RUN_DIR/cell_year_lai.parquet)
Usage (light — LAI is ~16 MB, no layer dim; still submit to SLURM for consistency):
  RUN_DIR=.../daily_2000_2019_historic_laistand_c0_67419_seed1/output FIRSTYEAR=2000 \
  OUT=/p/tmp/jamirp/emulator_global/tables/cell_year_lai_hist.parquet \
  python3 scripts/build_laistand_lai_feature.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import polars as pl
import xarray as xr

NCELL_GLOBAL = 67420
FILL_THRESH = 1.0e30  # LAI_STAND fill is ~9.969e36; real stand LAI is O(0..~12)
LAI_MAX = 30.0        # outputvars.js lai limit high=30; anything above is fill/garbage
GLOBAL_GRID = ("/p/tmp/jamirp/esm_land_daily/daily_2000_2019_global_c0_67419_seed1/output/grid.nc")


def main() -> int:
    run_dir = os.environ.get("RUN_DIR")
    if not run_dir:
        print("FATAL: set RUN_DIR (LAI_STAND run output dir with lai_stand.nc)", file=sys.stderr)
        return 2
    firstyear = int(os.environ.get("FIRSTYEAR", "2000"))
    grid_path = os.environ.get("GRID", GLOBAL_GRID)
    out = os.environ.get("OUT", os.path.join(run_dir, "cell_year_lai.parquet"))

    grid = xr.open_dataset(grid_path)
    cid = grid["cellid"].values  # [lat, lon]
    valid = np.isfinite(cid)
    ncell = int(valid.sum())
    if ncell != NCELL_GLOBAL:
        print(f"FATAL: grid.nc has {ncell} valid cells, expected {NCELL_GLOBAL} — wrong/corrupt grid "
              f"({grid_path}). Point GRID at the global daily run's grid.nc.", file=sys.stderr)
        return 3
    cells = cid[valid].astype(np.int64)

    lai = xr.open_dataset(os.path.join(run_dir, "lai_stand.nc"), decode_times=False)
    da = lai["LAI"]  # [time, lat, lon] annual (no layer dim)
    nyear = da.sizes["time"]

    rows = []
    per_year_frac = []
    for i in range(nyear):
        arr = da.isel(time=i).values  # [lat, lon]
        cell_vals = arr[valid].astype(np.float64)
        # mark fill/garbage as NaN; a real LAI cell is finite, below the ~1e37 fill, and <= the 30 output cap
        real = np.isfinite(cell_vals) & (cell_vals < FILL_THRESH) & (cell_vals <= LAI_MAX)
        per_year_frac.append(float(real.mean()))
        cell_vals = np.where(real, cell_vals, np.nan)
        rows.append(
            pl.DataFrame(
                {
                    "Cell": cells,
                    "Year": np.full(cells.shape, firstyear + i, dtype=np.int64),
                    "lai": cell_vals,
                }
            )
        )
        print(f"  year {firstyear + i}: real fraction={per_year_frac[-1]:.3f}, "
              f"lai mean(real)={float(np.nanmean(cell_vals)):.3f}")

    # GATE (per-YEAR, not cross-year-averaged): (a) not all-fill; (b) EVERY year has coverage consistent with
    # the median — a timed-out/incomplete run leaves LATE years at fill (~0) while early years are real, so the
    # cross-year AVERAGE can still clear a low floor. We do NOT assume a high absolute land fraction (most land
    # is legitimately low/zero LAI); we require inter-year CONSISTENCY.
    med = float(np.median(per_year_frac))
    if med < 0.02:
        print(f"FATAL: median per-year real fraction {med:.4f} — LAI_STAND is all-fill. REFUSING to write {out}.",
              file=sys.stderr)
        return 4
    if min(per_year_frac) < 0.5 * med:
        print(f"FATAL: per-year real fraction ranges [{min(per_year_frac):.3f}, {max(per_year_frac):.3f}] "
              f"(median {med:.3f}) — an incomplete/timed-out run leaves late years at fill. REFUSING to write {out}.",
              file=sys.stderr)
        return 4

    tbl = pl.concat(rows).sort(["Cell", "Year"])
    # drop fill/ocean cells. is_not_NAN (NOT is_not_null — in polars a NaN float IS 'not null', so is_not_null
    # would be a no-op and let fill-marked NaNs through into the training join).
    tbl = tbl.filter(pl.col("lai").is_not_nan())
    tbl.write_parquet(out)
    print(f"wrote {out}: {tbl.height} (Cell,Year) rows (real-fraction {real_frac:.3f}), "
          f"lai range [{tbl['lai'].min():.3f}, {tbl['lai'].max():.3f}]")
    h = tbl.filter(pl.col("Cell") == 42490)
    if h.height:
        print(f"  Hainich(42490) lai by year: {[round(v, 2) for v in h['lai'].to_list()]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
