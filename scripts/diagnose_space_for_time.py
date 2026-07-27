#!/usr/bin/env python3
"""Space-for-time test — WHY does the transient boundary help Wooddens/D95max but hurt SLA/minwscal in the
copula scenario-holdout (ADR 0027 caveat, confirmed seed-robust)? Hypothesis: the copula learns the
boundary→trait relationship from SPATIAL (cross-cell) variation; the transient boundary applies it to a
cell's TEMPORAL warming. Where the spatial and temporal gdd5→trait gradients AGREE in sign, the transient
boundary carries correct signal (helps); where they DISAGREE, it mis-signs the extrapolation (hurts).

Reads the TRANSIENT pooled copula table (Xc.f64 with gdd5 per stem, Y_<axis>.f64, cells.i64, scenario.i64).
Per (cell, regime): median trait + mean gdd5. Then per axis, across cells:
  SPATIAL  gradient = Spearman(gdd5_hist,            trait_median_hist)         [cross-cell, fixed regime]
  TEMPORAL gradient = Spearman(gdd5_ssp - gdd5_hist, trait_ssp - trait_hist)    [within-cell warming]
Opposite signs ⇒ space-for-time FAILS for that axis ⇒ transient boundary hurts it. Same sign ⇒ holds ⇒ helps.

  OUT=/p/tmp/jamirp/emulator_global/slow_copula_pooled_w20 python3 scripts/diagnose_space_for_time.py
"""
import os

import numpy as np
import polars as pl
from scipy.stats import spearmanr

DATA = os.environ.get("OUT", "/p/tmp/jamirp/emulator_global/slow_copula_pooled_w20")


def manifest(path):
    d = {}
    for ln in open(path):
        p = ln.rstrip("\n").split("\t", 1)
        if len(p) == 2:
            d[p[0]] = p[1]
    return d


def main():
    man = manifest(os.path.join(DATA, "manifest_copula.txt"))
    n = int(man["n"])
    ncond = int(man["ncond"])
    cond = man["cond_cols"].split()
    axes = man["axes"].split()
    gi = cond.index("eco_diag_gdd_5")
    Xc = np.fromfile(os.path.join(DATA, "Xc.f64"), dtype="<f8").reshape(n, ncond)
    gdd = Xc[:, gi]
    cells = np.fromfile(os.path.join(DATA, "cells.i64"), dtype="<i8")
    scen = np.fromfile(os.path.join(DATA, "scenario.i64"), dtype="<i8")
    tags = man.get("pooled_scenarios", "historic ssp370").split()
    print(f"== {n} stems, {len(np.unique(cells))} cells; gdd5 col={gi}; regimes={tags}")
    print(f"{'axis':10s} {'SPATIAL rho':>13s} {'TEMPORAL rho':>13s}  verdict")

    for ax in axes:
        y = np.fromfile(os.path.join(DATA, f"Y_{ax}.f64"), dtype="<f8")
        df = pl.DataFrame({"cell": cells, "scen": scen, "gdd": gdd, "y": y})
        agg = df.group_by(["cell", "scen"]).agg(
            pl.col("gdd").mean().alias("gdd"), pl.col("y").median().alias("ym")
        )
        h = agg.filter(pl.col("scen") == 0).select(["cell", "gdd", "ym"]).rename({"gdd": "gh", "ym": "yh"})
        s = agg.filter(pl.col("scen") == 1).select(["cell", "gdd", "ym"]).rename({"gdd": "gs", "ym": "ys"})
        j = h.join(s, on="cell", how="inner")
        gh = j["gh"].to_numpy(); yh = j["yh"].to_numpy()
        dg = j["gs"].to_numpy() - gh; dy = j["ys"].to_numpy() - yh
        # temporal gradient only meaningful where the cell actually warmed
        m = np.abs(dg) > 1e-6
        rs = spearmanr(gh, yh).statistic                       # spatial
        rt = spearmanr(dg[m], dy[m]).statistic                 # temporal
        agree = (np.sign(rs) == np.sign(rt)) and abs(rs) > 0.05 and abs(rt) > 0.05
        verdict = "space-for-time HOLDS (transient should help)" if agree else \
            ("gradients DISAGREE → space-for-time FAILS (transient hurts)" if abs(rs) > 0.05 and abs(rt) > 0.05
             else "weak gradient(s) — inconclusive")
        print(f"{ax:10s} {rs:13.3f} {rt:13.3f}  {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
