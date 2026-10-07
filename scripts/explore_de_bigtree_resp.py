"""explore_de_bigtree_resp.py — LINE X, Germany emulator: what makes the TAB growth head's one-step big-tree growth
fall too fast on ACCESS ssp370? (pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "Pre-registration BT")

Per (member, year), on 15-25 m stems present in y and y+1 (fate_y1 <= 1 = the dagb head's own training rows):
  true      mean log(agb_y1 / agb)
  tf        dagb head at the TRUE next-year G and counter, split into its tree/stand booster b0 and weather booster b1
  draw      the same at a DRAWN G (H.sample_G + the counter rule, as explore_de_tree_onestep.py; mean of --ndraw)
  a_<f>_y1  the year's weather anomalies (mean over the rows), plus cell_stems_per_patch and the drawn / true G means
Usage:  python explore_de_bigtree_resp.py [--ndraw 2]   -> shared/eval/bigtree_resp_yearly.csv
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_sh_rules as rl  # noqa: E402
import explore_de_tab_features as F  # noqa: E402
import explore_de_tab_heads as Hh  # noqa: E402
import explore_de_tree_onestep as to  # noqa: E402

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
MEMBERS = [("SCEN", "MPI-ESM1-2-HR_ssp245_s2_w2015"), ("GCM", "ACCESS-CM2_Historical_s1_h1985"),
           ("GCM", "ACCESS-CM2_ssp370_s1_w2015"), ("GCM", "ACCESS-CM2_ssp126_s1_w2015"),
           ("GCM", "ACCESS-CM2_ssp245_s1_w2015")]
HEAT = ["tmean_ann", "twarm_month", "days_gt30", "vpd_jja", "cwb_jja", "dry_spell_max", "prec_jja", "swdown_ann"]
HLO, HHI = 15.0, 25.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ndraw", type=int, default=2)
    a = ap.parse_args()
    H = Hh.TabHeads.load("DEV-A", kappa=1.0)
    P = rl.load_params()
    b0, b1, meta = H.m["dagb"]
    rng = np.random.default_rng(20261007)
    rows = []
    for set_, m in MEMBERS:
        D = to.load(set_, m)
        X = F.assemble(D, P)
        h = X["Height"].to_numpy()
        X = X.filter(pl.Series((h >= HLO) & (h < HHI)))
        n = X.height
        y_true = np.log(X["agb_y1"].to_numpy() / X["agb"].to_numpy())
        G_true, c_true = X["G_y1"].to_numpy().astype(np.float64), X["c_y1"].to_numpy().astype(np.float64)
        Xg = H._with(X, G_y1=G_true, c_y1=c_true)
        p0 = b0.predict(F.to_matrix(Xg, meta["features_B0"]), raw_score=True, num_threads=H.nthreads)
        p1 = b1.predict(F.to_matrix(Xg, meta["features_B1"]), raw_score=True, num_threads=H.nthreads)
        assert np.allclose(p0 + p1, H.raw("dagb", Xg)), "b0 + b1 must reproduce the head"
        dr, gd = np.zeros(n), np.zeros(n)
        for _ in range(a.ndraw):
            G1 = H.sample_G(X, rng.uniform(size=n), rng.uniform(size=n))
            c1 = H.counter(X["c_y"].to_numpy(), G1, X["Age"].to_numpy())
            mu, _, _ = H.growth(X, G1, c1)
            dr += mu / a.ndraw
            gd += G1 / a.ndraw
        acols = [f"a_{f}_y1" for f in HEAT if f"a_{f}_y1" in X.columns]
        T = X.select("Year", *acols, "cell_stems_per_patch").with_columns(
            true=pl.Series(y_true), tf=pl.Series(p0 + p1), b0=pl.Series(p0), b1=pl.Series(p1), draw=pl.Series(dr),
            G_true=pl.Series(G_true), G_draw=pl.Series(gd))
        Y = T.group_by("Year").agg(pl.all().mean(), n=pl.len()).sort("Year").with_columns(member=pl.lit(m))
        rows.append(Y)
        print(f"{m}: {n} stems 15-25 m", flush=True)
    R = pl.concat(rows, how="diagonal_relaxed").with_columns(r_tf=pl.col("tf") - pl.col("true"),
                                                             r_draw=pl.col("draw") - pl.col("true"))
    out = os.path.join(XDE, "shared", "eval", "bigtree_resp_yearly.csv")
    R.write_csv(out)
    print("wrote", out)
    pl.Config.set_tbl_rows(200)
    pl.Config.set_tbl_width_chars(240)
    pl.Config.set_tbl_cols(20)
    W = (R.with_columns(win=(pl.col("Year") // 5 * 5)).group_by("member", "win")
         .agg(pl.col("true", "tf", "b0", "b1", "draw", "r_tf", "r_draw").mean().round(4), pl.col("n").sum())
         .sort("member", "win"))
    print(W)
    fut = R.filter(~pl.col("member").str.contains("Historical") & (pl.col("Year") >= 2015))
    print("BT2: pooled future member-years", fut.height)
    for c in [c for c in R.columns if c.startswith("a_")] + ["cell_stems_per_patch"]:
        for r in ("r_tf", "r_draw"):
            print(f"  corr({r}, {c}) = {np.corrcoef(fut[r].to_numpy(), fut[c].to_numpy())[0, 1]:+.3f}")
    for m in R["member"].unique().sort():
        q = fut.filter(pl.col("member") == m)
        if q.height:
            print(m, " ".join(f"{c}:{np.corrcoef(q['r_tf'].to_numpy(), q[c].to_numpy())[0, 1]:+.2f}"
                              for c in R.columns if c.startswith("a_")))


if __name__ == "__main__":
    main()
