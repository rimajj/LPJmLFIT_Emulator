#!/usr/bin/env python3
"""Build the TRANSIENT (time-varying) bioclimatic boundary per (cell, year) — ADR 0026.

The Component-S boundary (`gdd5`, `tas_cold_month`, `soil_depth`, co2) is, in the current pipeline, a
per-cell **climatological-static** normal: `eco_diag_gdd_5`/`tas_cold_month` in `cell_year_feats.parquet` are
identical every year for a cell (Hainich = 1863.695 / 0.2184 every one of 2000-2019), and the SSP feature
table never even populated them. So a warming cell's establishment gate is FROZEN over the transient (ADR
0026 §Context). This script recomputes `gdd5` and `tas_cold_month` on a **trailing W-year window ending at
each target year**, per (cell, year), from the orderA daily temperature `.clm` forcing — mirroring FIT's
~20-yr Climbuf establishment memory. `soil_depth` stays static and co2 stays 369 (ADR 0004), so only these
two axes are recomputed; the build script joins them per (cell, year) in place of the static eco columns.

CONSISTENCY (verified): the recompute uses the EXACT static-feature method — the Thom (1966) monthly GDD
(`climclusterpy.features.ecological_summaries`) on the window monthly-mean climatology, and
`tas_cold_month = min_m T_m`. A W=20 window ending 2019 (i.e. 2000-2019) reproduces the static Hainich
`gdd5=1863.695` / `tas_cold_month=0.2184` bit-for-bit — so W→∞ / a full historic window recovers today's
static boundary (ADR 0026: the static case is a nested special case, W→∞).

Source (orderA, °C, scalar 1.0, YEARCELL order, HDR=51, 365 noleap bands, float32; see
`scripts/extract_fdiff_validation_inputs.py::read_clm_year`):
  historic : /p/projects/waldspektrum/priesner/clustering/global/temperature_test.clm   (1901-2019 daily)
  ssp370   : /p/projects/.../global/ssp370/tas_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm (2015-2100 daily)

The orderA `.clm` cell index IS the parquet `Cell` (Hainich = 42490; verified) — no grid.nc mapping needed.

Env:
  SCENARIO = historic | ssp370      (default historic)
  WINDOW   = trailing-window width in years (default 20; matches FIT's Climbuf; W>=available => static)
  CELLS    = optional comma-list of cell indices for a subset validation run (default ALL 67420)
  OUT      = output parquet path (default /p/tmp/jamirp/emulator_global/tables/cell_year_boundary_<scen>_w<W>.parquet)

Run (subset validation):  SCENARIO=historic CELLS=42490 python3 scripts/build_transient_boundary.py
Run (global, on SLURM):   SCENARIO=ssp370 python3 scripts/build_transient_boundary.py
"""

import os
import struct
import sys

import numpy as np
import polars as pl

DPM = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31], dtype=np.int64)
MONTH_BOUNDS = np.concatenate([[0], np.cumsum(DPM)])  # [0,31,59,...,365]

# LPJmL .clm datatype code -> (numpy dtype). v<3 has NO datatype field and is stored as SHORT (int16).
_DT = {0: "<i1", 1: "<i2", 2: "<i4", 3: "<f4", 4: "<f8"}

CLM = {
    # only TEMPERATURE is needed — gdd5 (Thom monthly) + tas_cold_month are temperature-only.
    "historic": "/p/projects/waldspektrum/priesner/clustering/global/temperature_test.clm",
    "ssp370": (
        "/p/projects/waldspektrum/priesner/clustering/global/ssp370/"
        "tas_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm"
    ),
}
# target years the ind/feature tables cover (build_slow_runtime_table.py FIRSTYEAR + coverage)
TARGET_YEARS = {"historic": (2000, 2019), "ssp370": (2020, 2100)}


def open_clm(path):
    """Header-driven open of an LPJmL .clm (name[7] + 7 ints + version-dependent floats). Handles BOTH the
    v3 float32 (HDR=51, scalar 1.0 — historic temp, ssp huss) AND the v2 int16 (HDR=43, scalar 0.1 — ssp tas,
    °C×10) layouts. Returns (memmap (nyear,ncell,nbands) in the file dtype, firstyear, ncell, nbands, scalar).
    The scalar is applied by the caller (raw·scalar = °C)."""
    with open(path, "rb") as f:
        raw = f.read(64)
    if raw[:7] != b"LPJCLIM":
        raise SystemExit(f"FATAL: {path} not an LPJCLIM file (name={raw[:7]!r})")
    version, order, firstyear, nyear, firstcell, ncell, nbands = struct.unpack("<7i", raw[7 : 7 + 28])
    if order != 1:
        raise SystemExit(f"FATAL: {path} order={order} (expected 1 = YEARCELL)")
    scalar = struct.unpack("<f", raw[7 + 32 : 7 + 36])[0]  # 2nd float field (after cellsize_lon)
    if version >= 3:
        hdr = 51
        datatype = struct.unpack("<i", raw[7 + 40 : 7 + 44])[0]
        dt = _DT.get(datatype)
        if dt is None:
            raise SystemExit(f"FATAL: {path} v3 datatype={datatype} unknown")
    else:  # v1/v2: no datatype field; LPJmL stores these as SHORT (int16), HDR=43
        hdr = 43
        dt = "<i2"
    sz = os.path.getsize(path)
    per = ncell * nbands * np.dtype(dt).itemsize
    if (sz - hdr) != nyear * per:
        raise SystemExit(
            f"FATAL: {path} size {sz} != HDR({hdr}) + nyear({nyear})·ncell({ncell})·nbands({nbands})·"
            f"{np.dtype(dt).itemsize}B (got {(sz - hdr) / per:.4f} years)"
        )
    mm = np.memmap(path, dtype=dt, mode="r", offset=hdr, shape=(nyear, ncell, nbands))
    print(f"== clm={os.path.basename(path)} version={version} dtype={dt} scalar={scalar} "
          f"firstyear={firstyear} nyear={nyear} ncell={ncell} nbands={nbands} hdr={hdr}")
    return mm, firstyear, ncell, nbands, float(scalar)


def monthly_means_by_year(mm, scalar):
    """(nyears, NCELL, nbands) memmap -> (nyears, NCELL, 12) monthly-mean temperature in °C (raw·scalar).
    Year-major so peak RAM is one year + the (nyears,NCELL,12) result, not the whole file."""
    nyears, ncell, nbands = mm.shape
    out = np.empty((nyears, ncell, 12), dtype=np.float32)
    for iy in range(nyears):
        yr = np.asarray(mm[iy], dtype=np.float32) * scalar  # (NCELL, nbands), °C
        for m in range(12):
            out[iy, :, m] = yr[:, MONTH_BOUNDS[m] : MONTH_BOUNDS[m + 1]].mean(axis=1)
    return out


def gdd5_tcm(monthly_clim):
    """(N,12) monthly-mean climatology -> (gdd5 (N,), tas_cold_month (N,)). Thom (1966) monthly GDD_5 +
    coldest monthly mean — identical to the static climclusterpy method, windowed."""
    gdd5 = (np.maximum(monthly_clim - 5.0, 0.0) * DPM[np.newaxis, :]).sum(axis=1)
    tcm = monthly_clim.min(axis=1)
    return gdd5.astype(np.float32), tcm.astype(np.float32)


def main():
    scen = os.environ.get("SCENARIO", "historic")
    if scen not in CLM:
        raise SystemExit(f"SCENARIO must be one of {list(CLM)} (got {scen!r})")
    W = int(os.environ.get("WINDOW", "20"))
    cells_env = os.environ.get("CELLS", "").strip()
    cells = [int(c) for c in cells_env.split(",") if c] if cells_env else None
    out = os.environ.get(
        "OUT",
        f"/p/tmp/jamirp/emulator_global/tables/cell_year_boundary_{scen}_w{W}.parquet",
    )

    print(f"== scenario={scen} W={W}")
    mm, fy, ncell, nbands, scalar = open_clm(CLM[scen])
    navail = mm.shape[0]

    mby = monthly_means_by_year(mm, scalar)  # (navail, ncell, 12)
    print(f"== monthly climatology built: {mby.shape}")

    y0, y1 = TARGET_YEARS[scen]
    rows_cell, rows_year, rows_gdd, rows_tcm = [], [], [], []
    cell_sel = np.array(cells, dtype=np.int64) if cells is not None else np.arange(ncell)
    short = 0
    for Y in range(y0, y1 + 1):
        iY = Y - fy
        if iY < 0 or iY >= navail:
            raise SystemExit(f"FATAL: target year {Y} outside .clm coverage [{fy}, {fy + navail - 1}]")
        lo = max(0, iY - W + 1)
        wyears = iY - lo + 1
        if wyears < W:
            short += 1
        clim = mby[lo : iY + 1].mean(axis=0)  # (NCELL, 12)
        gdd5, tcm = gdd5_tcm(clim)
        rows_cell.append(cell_sel)
        rows_year.append(np.full(cell_sel.shape, Y, dtype=np.int64))
        rows_gdd.append(gdd5[cell_sel])
        rows_tcm.append(tcm[cell_sel])

    df = pl.DataFrame(
        {
            "Cell": np.concatenate(rows_cell),
            "Year": np.concatenate(rows_year),
            "eco_diag_gdd_5": np.concatenate(rows_gdd),
            "tas_cold_month": np.concatenate(rows_tcm),
        }
    )
    os.makedirs(os.path.dirname(out), exist_ok=True)
    df.write_parquet(out)
    print(
        f"== wrote {df.height} rows ({df['Cell'].n_unique()} cells x {df['Year'].n_unique()} years) to {out}"
    )
    if short:
        print(f"   NOTE: {short} early target-year(s) had a SHORT trailing window (< W={W}); "
              f".clm starts {fy}, so pre-{fy} backfill is unavailable (ADR 0026 §2 documented edge).")
    # Hainich transient trace (proof the gate shifts over the transient)
    if 42490 in set(int(c) for c in cell_sel):
        h = df.filter(pl.col("Cell") == 42490).sort("Year")
        print("   Hainich(42490) transient boundary "
              f"[{y0}]: gdd5={h['eco_diag_gdd_5'][0]:.2f} tcm={h['tas_cold_month'][0]:.4f}  "
              f"[{y1}]: gdd5={h['eco_diag_gdd_5'][-1]:.2f} tcm={h['tas_cold_month'][-1]:.4f}  "
              f"(Δgdd5={h['eco_diag_gdd_5'][-1] - h['eco_diag_gdd_5'][0]:+.1f}, "
              f"Δtcm={h['tas_cold_month'][-1] - h['tas_cold_month'][0]:+.3f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
