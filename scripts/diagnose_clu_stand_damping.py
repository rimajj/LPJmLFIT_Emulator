"""Where does the stand map's damped per-cell response arise? (ADR 0342 sec. 8 lever 1)

Per-cell slope of the emulated 2071-2100 minus 1990-2019 change against the original's (seed 2), split into
  train GCM x train cells  (in sample: the map saw these targets)
  train GCM x held-out cells
  test GCM  x train cells
  test GCM  x held-out cells
for the stand quantities and vegetation carbon. If the slope is already < 0.9 in sample, the damping is the map's
fit (regularisation / features), not generalisation to unseen climates.

usage: python scripts/diagnose_clu_stand_damping.py [arm ...]   (default: main main2)
"""

import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clu_emu_maps as M  # noqa: E402

QS = ["lai_stand", "fpc_tree", "fpc_grass", "vegc"]


def slope(e, t):
    ok = np.isfinite(e) & np.isfinite(t)
    e, t = e[ok], t[ok]
    vt = np.var(t)
    return float(np.cov(e, t, bias=True)[0, 1] / vt) if vt > 0 else np.nan, float(np.std(e) / np.std(t))


def main():
    arms = sys.argv[1:] or ["main", "main2"]
    c = M.cells()
    ho = c["heldout"].to_numpy()
    h2 = M.with_derived(M.targets(2, "hist"))
    base = {q: M.cell_mean(h2, q, M.H0, M.H1) for q in QS}
    rows = []
    for arm in arms:
        p = M.with_derived(pl.read_parquet(f"{M.OUT}/maps/{arm}/preds.parquet"))
        for g, s in M.all_legs():
            if s == "ssp126" or "ssp126" in s:
                continue  # little warming: slope ill-conditioned
            name = M.leg_name(g, s)
            t2 = M.targets(2, name)
            if t2 is None:
                continue
            t2 = M.with_derived(t2)
            pe = p.filter(pl.col("leg") == name)
            for q in QS:
                dT = M.cell_mean(t2, q, 2071, M.F1) - base[q]
                dE = M.cell_mean(pe, q, 2071, M.F1) - base[q]
                for cg, m in (("train_cells", ~ho), ("heldout_cells", ho)):
                    b, sr = slope(np.where(m, dE, np.nan), dT)
                    rows.append(dict(arm=arm, gcm_set="test" if g in M.TEST_GCMS else "train",
                                     co2="fixed" if "co2fix" in s else "rising", q=q, cells=cg, slope=b,
                                     sd_ratio=sr))
    df = pl.DataFrame(rows)
    out = df.group_by("arm", "q", "gcm_set", "cells", "co2").agg(
        pl.len().alias("legs"), pl.col("slope").mean().alias("slope_mean"),
        pl.col("slope").min().alias("slope_min"), pl.col("slope").max().alias("slope_max"),
        pl.col("sd_ratio").mean().alias("sd_ratio_mean")).sort("arm", "q", "co2", "gcm_set", "cells")
    with pl.Config(tbl_rows=200, tbl_width_chars=200, float_precision=2):
        print(out)


if __name__ == "__main__":
    main()
