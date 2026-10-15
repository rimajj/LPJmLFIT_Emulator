"""Year-by-year area-weighted totals for the ADR 0342 warming-response proof -> one JSON for a results page.

Per held-out climate model x scenario (incl. the CO2-fixed twins): the original (seed 2), its second run (seed 3)
and the emulator, summed over the 674 clustered cells with each cell's region area.
  structure/stand (1990-2100): vegc [PgC], lai_stand [area mean], tree cover [area mean of fpc1..7]
      emulator = map arm main2 (2020-2100; before 2020 every line is the original's own state), plus the
      ssp126-only arm `wrong` as the wrong-training-data control
  daily exchange (2020-2100): gpp, npp [PgC/yr], et, runoff [1000 km3/yr]
      emu_full = daily model fed the emulated stand (NC_B3 = main2 stand); emu_daily = fed the original's (NC_A2)

usage: python scripts/build_response_timeseries.py <out.json>
"""

import json
import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clu_emu_maps as M  # noqa: E402

F2N = "/p/projects/open/Jamir/esm_land_emulator_data/f2_non"
STAND_Q = {"vegc": 1e-9, "lai_stand": None, "fpc_tree": None}  # factor -> sum (gC/m2 * km2 -> PgC); None = mean
DAILY_Q = {"gpp": 1e-9, "npp": 1e-9, "et": 1e-9, "runoff": 1e-9}  # gC/m2 or mm per yr * km2 -> PgC or 1000 km3


def series(df, q, w, n, fac):
    d = df.select("Cell", "Year", pl.col(q).cast(pl.Float64)).filter(pl.col(q).is_finite())
    years = sorted(d["Year"].unique().to_list())
    out = []
    for y in years:
        dy = d.filter(pl.col("Year") == y)
        v = np.full(n, np.nan)
        v[dy["Cell"].to_numpy()] = dy[q].to_numpy()
        ok = np.isfinite(v)
        out.append(float(np.sum(w[ok] * v[ok]) * fac) if fac else float(np.sum(w[ok] * v[ok]) / np.sum(w[ok])))
    return years, out


def r(xs, k=4):
    return [None if x is None or not np.isfinite(x) else round(x, k) for x in xs]


def main():
    c = M.cells()
    w, n = c["region_km2"].to_numpy(), c.height
    h = {s: M.with_derived(M.targets(s, "hist")) for s in (2, 3)}
    preds = {a: M.with_derived(pl.read_parquet(f"{M.OUT}/maps/{a}/preds.parquet")) for a in ("main2", "wrong")}
    ann = {t: np.load(f"{F2N}/runs/{t}/annual.npz") for t in ("NC_A2", "NC_B3")}
    import f2_train as F  # second run's daily totals (seed 3), as clu_emu_f2.stage_run computes them

    F.DATA = F2N
    lat = c["lat"].to_numpy().astype(np.float32)
    out = {"years_hist": list(range(M.H0, M.H1 + 1)), "years_fut": list(range(M.F0, M.F1 + 1)), "cases": {}}
    for g in M.TEST_GCMS:
        for s in M.SSPS + M.FIX_TEST:
            leg = M.leg_name(g, s)
            case = {}
            t = {sd: M.with_derived(M.targets(sd, leg)) for sd in (2, 3)}
            for q, fac in STAND_Q.items():
                case[q] = {
                    "orig": r(series(h[2], q, w, n, fac)[1] + series(t[2], q, w, n, fac)[1]),
                    "second": r(series(h[3], q, w, n, fac)[1] + series(t[3], q, w, n, fac)[1]),
                    "emu": r(series(preds["main2"].filter(pl.col("leg") == leg), q, w, n, fac)[1]),
                    "wrong": r(series(preds["wrong"].filter(pl.col("leg") == leg), q, w, n, fac)[1]),
                }
            sec = F.truth_annual(F.MemberLeg(3, leg, lat))
            for q, fac in DAILY_Q.items():
                tot = lambda a, f=fac: r(list((w[:, None] * a).sum(0) * f))  # noqa: E731
                case[q] = {"orig": tot(ann["NC_B3"][f"truth__{leg}__{q}"]), "second": tot(sec[q]),
                           "emu": tot(ann["NC_B3"][f"free__{leg}__{q}"]),
                           "emu_daily": tot(ann["NC_A2"][f"free__{leg}__{q}"])}
            out["cases"][f"{g}|{s}"] = case
            M.log(f"{leg} done")
    json.dump(out, open(sys.argv[1], "w"), separators=(",", ":"))


if __name__ == "__main__":
    main()
