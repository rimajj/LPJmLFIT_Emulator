#!/usr/bin/env python3
"""explore_de_grass_climrange.py — LINE X, Germany emulator: are ACCESS's bad grass years outside the weather the grass
model was trained on? For the grass model's climate inputs (explore_de_tab_heads.GRASS_CLIM), the training range =
the DEV-A training members (MPI s1 Historical / ssp126 / ssp370) on their training cells; for every ACCESS s1 year
(Historical then <leg>) on the given cells: share of cells outside that range per feature, the yearly cell-mean
anomaly, and the yearly mean closed-patch one-step log residual from explore_de_grass_onestep.py.
Writes shared/eval/grass_climrange_ACCESS-CM2_s1_<leg>_c<N>.csv."""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_grass2 as g2  # noqa: E402
import explore_de_grass_attrib as ga  # noqa: E402
import explore_de_sh_trans as tr  # noqa: E402
import explore_de_tab_features as F  # noqa: E402
import explore_de_tab_heads as th  # noqa: E402

LEG = "ssp370"


def cell_years(gcm, seed, traj, years, cells):
    D = pl.DataFrame({"Cell": np.repeat(cells, len(years)).astype(np.int16),
                      "Year": np.tile(years, len(cells)).astype(np.int16)}).with_columns(
        gcm=pl.lit(gcm), traj=pl.lit(traj), seed=pl.lit(seed, pl.Int8))
    D = tr.join_climate(D, cols=[f"anom_{f}" for f in F.CLIM_F] + F.ABS_Y1, years=("y1",), ext=True)
    return D.with_columns(*[pl.col(f"anom_{f}_y1").alias(f"a_{f}_y1") for f in F.CLIM_F])


def main():
    spec = json.load(open(os.path.join(F.SAMPLES, "DEV-A", "split.json")))
    rd = ga.run_dir("_tabg2_ar", "ACCESS-CM2", 1, LEG)
    cells = sorted(sum((json.load(open(os.path.join(rd, f"meta_{c:03d}.json")))["cells"] for c in (0, 1)), []))
    ctrain = json.loads(spec["cells_train"]) if isinstance(spec["cells_train"], str) else spec["cells_train"]
    T = []
    for m in spec["train"]:
        gcm, traj, s, _ = m.split("_")
        yrs = list(range(1985, 2014)) if traj == "Historical" else list(range(2014, 2043))
        T.append(cell_years(gcm, int(s[1:]), traj, yrs, ctrain))
    T = pl.concat(T)
    A = pl.concat([cell_years("ACCESS-CM2", 1, "Historical", list(range(1985, 2014)), cells),
                   cell_years("ACCESS-CM2", 1, LEG, list(range(2014, 2043)), cells)])
    feats = th.GRASS_CLIM
    lo = {f: float(T[f].min()) for f in feats}
    hi = {f: float(T[f].max()) for f in feats}
    A = A.with_columns(**{f"out_{f}": ((pl.col(f) < lo[f]) | (pl.col(f) > hi[f])).cast(pl.Float64) for f in feats})
    A = A.with_columns(n_out=pl.sum_horizontal([f"out_{f}" for f in feats]))
    Y = A.group_by("Year").agg(pl.col("n_out").mean(), (pl.col("n_out") > 0).mean().alias("cells_any_out"),
                               *[pl.col(f"out_{f}").mean() for f in feats], *[pl.col(f).mean() for f in feats])
    Y = Y.with_columns((pl.col("Year") + 1).alias("Year1"))
    E = pl.read_parquet(os.path.join(g2.EVAL, f"grass_onestep_ACCESS-CM2_s1_{LEG}_c{len(cells)}_resid.parquet"))
    r = E.group_by("Year").agg(resid=pl.col("resid").mean())
    Y = Y.join(r, left_on="Year1", right_on="Year", how="left").sort("Year")
    out = os.path.join(g2.EVAL, f"grass_climrange_ACCESS-CM2_s1_{LEG}_c{len(cells)}.csv")
    Y.write_csv(out)
    pl.Config.set_tbl_rows(80)
    pl.Config.set_tbl_width_chars(220)
    print("training range:", {f: (round(lo[f], 2), round(hi[f], 2)) for f in feats})
    print(Y.select("Year1", "resid", "cells_any_out", "n_out").with_columns(pl.exclude("Year1").round(3)))
    rr = Y["resid"].to_numpy()
    print("corr(yearly resid, yearly cell-mean feature) and share of cell-years out of range:")
    for f in feats:
        x = Y[f].to_numpy()
        ok = ~np.isnan(rr) & ~np.isnan(x)
        print(f"  {f:22s} corr {np.corrcoef(rr[ok], x[ok])[0, 1]:+.2f}   out {float(A[f'out_{f}'].mean()):.3f}")
    ok = ~np.isnan(rr)
    print("corr(resid, cells_any_out)", round(float(np.corrcoef(rr[ok], Y["cells_any_out"].to_numpy()[ok])[0, 1]), 2))
    print("wrote", out)


if __name__ == "__main__":
    main()
