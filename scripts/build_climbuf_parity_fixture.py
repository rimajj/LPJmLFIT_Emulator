#!/usr/bin/env python3
"""Build the committed parity fixture for the ONLINE transient boundary (the coupled-run Climbuf, ADR
0026/0027). The Julia `ClimBuf` (`src/climbuf.jl`) MUST reproduce `scripts/build_transient_boundary.py`
bit-for-method (train/inference consistency, ADR 0023); this dumps a compact Hainich (cell 42490) fixture the
`test/testitems/climbuf_tests.jl` parity test asserts against, so CI (which has NO cluster `.clm` access) can
check the contract from committed data alone.

It extracts ONLY cell 42490 from the historic temperature `.clm` (cheap strided memmap read — not the global
all-cell reduction `build_transient_boundary.py::main` does) and reproduces that script's exact float32
method:
  • per-year monthly means  = mean daily T (°C = raw·scalar) in each calendar month (noleap MONTH_BOUNDS)
  • trailing-W=20 boundary   = Thom-1966 monthly gdd5 + coldest monthly mean over the window ending each year

Outputs (float32-exact decimals, %.9g so Julia parses the same float32 value), under references/:
  climbuf_hainich_monthly.csv       year, T01..T12  (monthly-mean °C, 1981-2019 — seed window + run years)
  climbuf_hainich_boundary_w20.csv  year, gdd5, tas_cold_month  (2000-2019 — == the offline boundary_series)
  climbuf_hainich_daily_2010.csv    doy(1..365), temp_C          (one real year, to test daily accumulation)

The window ending 2019 reproduces the static Hainich gdd5=1863.695 / tas_cold=0.2184 (the committed DRF
meta's boundary), so the fixture is self-consistent with the production artifact.

Run (login node, seconds):
  /home/jamirp/.conda/envs/py311_new/bin/python scripts/build_climbuf_parity_fixture.py
"""

import os
import sys

import numpy as np

# reuse the header-driven .clm reader + the exact offline constants/method
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_transient_boundary import (
    CLM,
    MONTH_BOUNDS,
    TARGET_YEARS,
    gdd5_tcm,
    open_clm,
)

CELL = 42490                      # Hainich (DE-Hai), orderA 0-based == parquet Cell
W = 20                            # CLIMBUFSIZE (FIT Climbuf; the offline default)
SEED_START = 1981                 # first monthly-mean year to dump (W-1 seed years before target y0=2000)
DAILY_YEAR = 2010                 # the one year whose daily stream we dump for the accumulation test
REFDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "test", "testitems", "references")


def g9(x):
    """%.9g of a value cast through float32 — the shortest decimal that round-trips the offline float32."""
    return f"{float(np.float32(x)):.9g}"


def main():
    mm, fy, _ncell, nbands, scalar = open_clm(CLM["historic"])
    assert nbands == 365, f"expected 365 noleap bands, got {nbands}"
    y0, y1 = TARGET_YEARS["historic"]           # (2000, 2019)

    # one cell, all years: (nyear, 365) °C in float32 (raw·scalar), exactly the offline dtype/scale
    daily = np.asarray(mm[:, CELL, :], dtype=np.float32) * np.float32(scalar)   # (nyear, 365)

    # per-year monthly means (float32) — build_transient_boundary.monthly_means_by_year, one cell
    monthly = np.empty((daily.shape[0], 12), dtype=np.float32)
    for m in range(12):
        monthly[:, m] = daily[:, MONTH_BOUNDS[m] : MONTH_BOUNDS[m + 1]].mean(axis=1)

    os.makedirs(REFDIR, exist_ok=True)

    # (1) monthly means for the seed window + run years [SEED_START .. y1]
    p_month = os.path.join(REFDIR, "climbuf_hainich_monthly.csv")
    with open(p_month, "w") as f:
        f.write("# Hainich (42490) per-year monthly-mean temperature (degC, float32) from historic "
                "temperature_test.clm. Reproduces build_transient_boundary.monthly_means_by_year for one "
                "cell. Rows 1981-1999 seed the ClimBuf ring; 2000-2019 are the run years.\n")
        f.write("year," + ",".join(f"T{m + 1:02d}" for m in range(12)) + "\n")
        for Y in range(SEED_START, y1 + 1):
            iy = Y - fy
            f.write(f"{Y}," + ",".join(g9(monthly[iy, m]) for m in range(12)) + "\n")

    # (2) the trailing-W=20 boundary per target year 2000-2019 (== the offline boundary_series gdd5/tcm)
    p_bound = os.path.join(REFDIR, "climbuf_hainich_boundary_w20.csv")
    with open(p_bound, "w") as f:
        f.write(f"# Hainich (42490) offline TRANSIENT boundary, W={W} trailing window, from "
                "build_transient_boundary.py (gdd5 = Thom-1966 monthly GDD_5; tas_cold_month = min monthly "
                "mean). The ClimBuf must reproduce these per-year (seed ring with 1981-1999 first).\n")
        f.write("year,gdd5,tas_cold_month\n")
        for Y in range(y0, y1 + 1):
            iy = Y - fy
            lo = max(0, iy - W + 1)
            clim = monthly[lo : iy + 1].mean(axis=0)          # (12,) window climatology, float32
            gdd5, tcm = gdd5_tcm(clim[np.newaxis, :])
            f.write(f"{Y},{g9(gdd5[0])},{g9(tcm[0])}\n")

    # (3) the daily stream for one year, to test daily accumulation -> monthly means
    iy_d = DAILY_YEAR - fy
    p_daily = os.path.join(REFDIR, "climbuf_hainich_daily_2010.csv")
    with open(p_daily, "w") as f:
        f.write(f"# Hainich (42490) daily mean temperature (degC, float32) for {DAILY_YEAR} (noleap 365). "
                "Drives climbuf_accumulate! + climbuf_finalize_year! to test the daily->monthly step matches "
                f"the monthly fixture's {DAILY_YEAR} row.\n")
        f.write("doy,temp_C\n")
        f.writelines(f"{d + 1},{g9(daily[iy_d, d])}\n" for d in range(365))

    # sanity trace: the W=20 window ending 2019 must == the committed DRF meta boundary
    iy19 = y1 - fy
    clim19 = monthly[iy19 - W + 1 : iy19 + 1].mean(axis=0)
    g19, t19 = gdd5_tcm(clim19[np.newaxis, :])
    print(f"== wrote {p_month}, {p_bound}, {p_daily}")
    print(f"== W=20 window ending {y1}: gdd5={float(g19[0]):.6f} tas_cold={float(t19[0]):.6f} "
          f"(DRF meta: 1863.695068 / 0.218387)")
    b0y, b0g, b0t = y0, None, None
    with open(p_bound) as f:
        for ln in f:
            if ln.startswith(str(y0) + ","):
                _, b0g, b0t = ln.strip().split(",")
                break
    print(f"== boundary_series[{b0y}]: gdd5={b0g} tas_cold={b0t}  ..  [{y1}]: "
          f"gdd5={g9(g19[0])} tas_cold={g9(t19[0])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
