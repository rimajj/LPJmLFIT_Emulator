"""Observed land climate at SpeedyWeather's T31 land columns, as a small CSV the stand-alone
reproducer (speedy_cold_bias_repro.jl, env LANDREF) scores any SpeedyWeather version against.

    python build_speedy_land_reference.py [control_run_dir] [out.csv]

Same columns, cells and weights as diagnose_speedy_climate.py (ADR 0346): the land columns of
run_speedy_landemu.jl whose nearest vegetated 0.5-degree cell lies within 3 degrees (1 197 at T31),
weight = cos(lat) x the column's land fraction. Reference = GSWP3-W5E5 observations 1985-2014
at those cells (matched on coordinates): annual mean, warmest- and coldest-month air temperature
[degC], precipitation [mm/yr], downward shortwave and net longwave at the surface [W/m², net LW
negative = loss].
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import diagnose_speedy_climate as dsc  # noqa: E402
import landemu_coupler as lc  # noqa: E402

DATA = "/p/projects/open/Jamir/esm_land_emulator_data/coupled"
RUN = sys.argv[1] if len(sys.argv) > 1 else f"{DATA}/speedy_t31_control_diag_10y"
OUT = sys.argv[2] if len(sys.argv) > 2 else f"{DATA}/speedy_t31_land_reference_w5e5.csv"


def main():
    import glob_emu as g
    import polars as pl

    r = dsc.load(RUN)
    cols = r["cols"]
    clat, clon = r["grid_lat"][cols - 1], r["grid_lon"][cols - 1]  # Julia 1-based ij
    st = g.cells().sort("Cell").filter(~pl.col("rock"))
    k, dist = lc.nearest_cells(clat, clon, st["lat"].to_numpy(), st["lon"].to_numpy())
    mask = dist <= 3.0
    elat, elon = st["lat"].to_numpy()[k[mask]], st["lon"].to_numpy()[k[mask]]
    w = np.cos(np.radians(clat[mask])) * r["daily_means"][mask, dsc.LF, :].mean(1)
    t, p, sw, lw = dsc.read_daily(
        dsc.OBS, dsc.OBS_VARS, dsc.orderA_index(elat, elon), range(1985, 2015)
    )
    s = dsc.stats(t, p, sw, lw)
    pl.DataFrame(
        {
            "ij": cols[mask],
            "lat": clat[mask],
            "lon": clon[mask],
            "weight": w,
            "tas": s["tas"].mean(1),
            "t_warm": s["t_warm"].mean(1),
            "t_cold": s["t_cold"].mean(1),
            "pr": s["pr"].mean(1),
            "rsds": s["rsds"].mean(1),
            "lwnet": s["lwnet"].mean(1),
        }
    ).write_csv(OUT)
    wm = lambda a: float(np.sum(a * w) / np.sum(w))  # noqa: E731
    print(f"{mask.sum()} columns -> {OUT}")
    print(
        f"weighted obs: tas {wm(s['tas'].mean(1)):.2f} degC, warm {wm(s['t_warm'].mean(1)):.2f}, "
        f"cold {wm(s['t_cold'].mean(1)):.2f}, pr {wm(s['pr'].mean(1)):.0f} mm/yr"
    )


if __name__ == "__main__":
    main()
