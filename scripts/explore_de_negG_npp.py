"""explore_de_negG_npp.py — LINE X, Germany emulator: is the original's negative-growth year a TREE-level carbon
shortfall? (pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "I5 tree NPP vs negative growth")

The C counts a negative-growth year when bm_delta = bm_inc/nind - turnover_ind < 0 (mortality_tree_ind.c:66), i.e. the
tree's own annual NPP falls short of its tissue turnover, which scales with its pools and moves slowly. The cell's
monthly NPP (incl. grass) tracks the yearly negative-growth share only at corr 0.46-0.92 (I4). Here, per tree on the
trans table (living at y, printed at y1, Type <= 6, 200 run cells): the tree's own NPP change r = npp_y1 / npp_y.
  tree level  AUC of -log r for (c_y1 >= 1); P(G < 0) by deciles of r
  yearly      corr over years of the Germany-wide neg share with (a) mean log r of trees, (b) the share of trees with
              r < 1, (c) the share with npp_y1 <= 0
Usage:  python explore_de_negG_npp.py [member ...]   (default: MPI s1 ssp245, ACCESS s1 ssp370, + their Historical)
Writes shared/eval/negG_npp_yearly.csv
"""

from __future__ import annotations

import glob
import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_gsign_info as gi  # noqa: E402

DEFAULT = ["MPI-ESM1-2-HR_Historical_s1_h1985", "MPI-ESM1-2-HR_ssp245_s1_w2015",
           "ACCESS-CM2_Historical_s1_h1985", "ACCESS-CM2_ssp370_s1_w2015"]


def auc(score: np.ndarray, lab: np.ndarray) -> float:
    o = np.argsort(score, kind="mergesort")
    rk = np.empty(len(score))
    rk[o] = np.arange(1, len(score) + 1)
    n1 = lab.sum()
    n0 = len(lab) - n1
    return float((rk[lab].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def main():
    mems = sys.argv[1:] or DEFAULT
    c2 = gi.cells200()
    rows = []
    for mem in mems:
        fs = sorted(glob.glob(os.path.join(gi.XDE, "shared", "trans", "dev", mem, "cb=dev", "y*.parquet")))
        d = (pl.concat([pl.scan_parquet(f).select("Year", "Cell", "Type", "Height", "npp", "npp_y1", "c_y1",
                                                  "fate_y1") for f in fs])
             .filter(pl.col("Cell").is_in(c2) & (pl.col("Type") <= 6) & (pl.col("fate_y1") < 2))
             .with_columns(neg=pl.col("c_y1") >= 1,
                           lr=(pl.col("npp_y1").clip(1e-3) / pl.col("npp").clip(1e-3)).log())
             .collect())
        lab, s = d["neg"].to_numpy(), -d["lr"].to_numpy()
        a = auc(s, lab)
        a2 = auc(-d["npp_y1"].to_numpy(), lab)
        dec = (d.with_columns(q=pl.col("lr").qcut(10, labels=[str(k) for k in range(10)]))
               .group_by("q").agg(pl.col("neg").mean(), pl.col("lr").median()).sort("q"))
        print(f"{mem}: {d.height} tree-transitions, P(neg) {lab.mean():.4f}, AUC(-log r) {a:.3f}, "
              f"AUC(-npp_y1) {a2:.3f}")
        print("  P(neg) by decile of log r:", [round(x, 3) for x in dec["neg"].to_list()])
        print("  median log r by decile:   ", [round(x, 3) for x in dec["lr"].to_list()])
        Y = (d.group_by("Year").agg(pl.col("neg").mean(), pl.col("lr").mean().alias("mean_lr"),
                                    (pl.col("lr") < 0).mean().alias("share_r_lt1"),
                                    (pl.col("npp_y1") <= 0).mean().alias("share_npp_le0"),
                                    pl.col("npp_y1").mean().alias("mean_npp_y1"))
             .sort("Year").with_columns(member=pl.lit(mem)))
        rows.append(Y)
        for c in ["mean_lr", "share_r_lt1", "share_npp_le0", "mean_npp_y1"]:
            print(f"  yearly corr(neg share, {c}) = {np.corrcoef(Y['neg'], Y[c])[0, 1]:.3f}")
    out = os.path.join(gi.EVAL, "negG_npp_yearly.csv")
    pl.concat(rows).write_csv(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
