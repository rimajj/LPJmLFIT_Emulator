#!/usr/bin/env python3
# =============================================================================
# diagnose_oracle_run_divergence.py — IS THE SINGLE-CELL ORACLE RE-RUN THE SAME
# TRAJECTORY AS THE GLOBAL RUN THE `ind` TABLE COMES FROM?
#
# WHY YOU MUST ASK. Every F-vs-C number for the five biome cells crosses two
# different LPJmL-FIT runs without saying so:
#   * the emulator's INITIAL CANOPY and Component S's counts come from the
#     67 420-cell GLOBAL seed1 run (`ind_hist_seed1_all.parquet`);
#   * the C-side flux and structure oracle (`M_fdiff_oracle_biomes*.csv`:
#     d_gpp, d_transp, a_fpc, a_lai_stand) comes from a per-cell SINGLE-CELL
#     `-DFROM_RESTART` re-run.
# ADR 0041 measured that a subset re-run is NOT a per-cell replica of the global
# run — same binary, same restart, same forcing, and the roster diverges — so a
# year-matched comparison can be against a different realisation of a stochastic
# model rather than against the run the emulator was initialised from.
#
# THE TEST. `d_gpp.nc` exists in BOTH runs, so the two trajectories can be
# compared directly on a full-population quantity, with no >5 m truncation and no
# reconstruction in between. Report the daily correlation and the level ratio over
# the scoring window, plus the run's first year as a control (the runs share a
# restart, so year 1 must agree to ~1.0 whatever happens later).
#
# MEASURED 2026-08-12 over 2010-2019 (ADR 0125): boreal 1.000 / r 0.9999,
# Hainich 0.989 / 0.9993, mediterranean 1.002 / 0.9989, Sahel 1.004 / 0.9994 —
# but tropical_amazon 0.933 / 0.9703. So four of five re-runs track the global run
# closely enough to be used as its oracle, and the AMAZON DOES NOT: its structural
# oracle is a different realisation and a level miss there is not an F error.
#
# Usage (login node, seconds):
#   /home/jamirp/.conda/envs/py311_new/bin/python scripts/diagnose_oracle_run_divergence.py
# Env: CELLS="name:idx,..."  Y0 Y1  VAR (default d_gpp)
# =============================================================================
import os
import sys

import netCDF4 as nc
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_biome_forcing import cells_from_env  # noqa: E402  (THE canonical cell registry)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFDIR = os.path.join(REPO, "test", "testitems", "references")
RUN_ROOT = "/p/tmp/jamirp/esm_land_daily"
GLOBAL = f"{RUN_ROOT}/daily_2000_2019_global_c0_67419_seed1/output"
FIRSTYEAR = 2000


def cell_run(cell):
    """The single-cell oracle run for this cell (Hainich's predates the M_ tag) — same rule as
    `scripts/extract_biome_fdiff_oracle.py::run_dir`, kept in sync deliberately."""
    tag = "grassgpp" if cell == 42490 else "M_grass_val"
    return f"{RUN_ROOT}/daily_{FIRSTYEAR}_2019_{tag}_c{cell}_seed1/output"


def latlon_of():
    rows, hdr = [], None
    for ln in open(os.path.join(REFDIR, "M_cells.csv")):
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        f = s.split(",")
        if hdr is None:
            hdr = f
            continue
        rows.append(dict(zip(hdr, f)))
    return {int(r["cell"]): (float(r["lat"]), float(r["lon"])) for r in rows}


def main():
    cells = cells_from_env()
    y0 = int(os.environ.get("Y0", "2010"))
    y1 = int(os.environ.get("Y1", "2019"))
    var = os.environ.get("VAR", "d_gpp")
    ll = latlon_of()

    g = nc.Dataset(f"{GLOBAL}/{var}.nc")
    gname = [k for k, v in g.variables.items() if v.ndim == 3][0]
    GL = g.variables[gname]
    glat = g.variables["lat"][:]
    glon = g.variables["lon"][:]

    w0, w1 = (y0 - FIRSTYEAR) * 365, (y1 - FIRSTYEAR + 1) * 365
    print(f"=== {var}: the single-cell oracle re-run vs the GLOBAL run, {y0}-{y1} ===")
    print("(both are the SAME binary from the SAME restart; a gap is stochastic divergence, ADR 0041)\n")
    print(f"{'cell':24s} {'r_yr1':>8s} {'r_window':>9s} {'glob':>8s} {'1cell':>8s} {'ratio':>7s}  verdict")
    worst = None
    for name, cell in cells:
        d = nc.Dataset(f"{cell_run(cell)}/{var}.nc")
        vname = [k for k, v in d.variables.items() if v.ndim == 3][0]
        a = np.asarray(d.variables[vname][:]).squeeze()
        lat, lon = ll[cell]
        i = int(np.argmin(abs(glat - lat)))
        j = int(np.argmin(abs(glon - lon)))
        b = np.asarray(GL[:, i, j])
        n = min(len(a), len(b))
        a, b = a[:n], b[:n]
        r1 = float(np.corrcoef(a[:365], b[:365])[0, 1])
        rw = float(np.corrcoef(a[w0:w1], b[w0:w1])[0, 1])
        ratio = float(a[w0:w1].mean() / b[w0:w1].mean())
        ok = rw >= 0.99 and abs(ratio - 1) <= 0.02
        print(f"{name:24s} {r1:8.5f} {rw:9.5f} {b[w0:w1].mean():8.4f} {a[w0:w1].mean():8.4f} "
              f"{ratio:7.3f}  {'same trajectory' if ok else 'DIVERGED — do not read a level miss as F error'}")
        if worst is None or rw < worst[1]:
            worst = (name, rw, ratio)
    print(f"\n`r_yr1` is the control: the two runs share a restart, so the FIRST year must agree "
          f"(~1.00000) whatever happens later.")
    print(f"worst: {worst[0]} r={worst[1]:.4f} ratio={worst[2]:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
