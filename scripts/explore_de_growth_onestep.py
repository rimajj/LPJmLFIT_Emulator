"""explore_de_growth_onestep.py — LINE X, Germany emulator: is the TAB growth chain already biased for BIG trees
one step ahead, on the original model's own states?

Context (explore_de_recruit_drift.py / explore_de_recruit_attrib.py, 2026-10-02): in the TAB free run big trees
(>= 15 m) grow 15-25 % slower than in the original, the canopy stays too open and the recruit head honestly
over-recruits. Before blaming free-run drift, check the one-step chain on the original's held-out states (ACCESS-CM2
seed 1 = a climate model the heads never saw; A1's 2 % unweighted eval rows), split by height class, at three levels:
  tf     growth head with the TRUE next-year growth efficiency G_y1 and counter c_y1 (teacher-forced)
  EG     growth head at the plug-in expected G (no sampling noise)
  draw   the rollout's own chain: G_y1 sampled (sign head + magnitude head + decile residual), the counter rule,
         growth head, plus one AR innovation sqrt(1-rho^2) sigma z (e_prev = 0 — the first step of a chain)
Pre-registered reading: if `draw` is already >= 0.004/yr below truth for >= 15 m stems in the median, the free-run
gap (~0.005/yr) is a ONE-STEP bias of the G sampler, not drift; if `draw` matches truth there, the gap is built by
the rollout's own lagged inputs (G_y, d_agb_prev, c_y, the AR state, the stand) and needs the instrumented rerun.

Usage:  python explore_de_growth_onestep.py [--members ACCESS-CM2_Historical_s1_h1985,ACCESS-CM2_ssp370_s1_w2015]
Writes /p/tmp/jamirp/X_de/shared/eval/growth_onestep_<set>.csv
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_sh_rules as rl  # noqa: E402
import explore_de_tab_features as F  # noqa: E402
import explore_de_tab_heads as Hh  # noqa: E402

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
EVAL = os.path.join(F.SAMPLES, "DEV-A", "eval")
HBIG = 15.0


def load(set_, member):
    fs = sorted(glob.glob(os.path.join(EVAL, set_, member, "y*.parquet")))
    D = pl.concat([pl.read_parquet(f) for f in fs], how="diagonal_relaxed")
    return D.filter((pl.col("fate_y1") <= 1) & (pl.col("Type") <= F.MAX_TREE_TYPE))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="GCM")
    ap.add_argument("--members", default="ACCESS-CM2_Historical_s1_h1985,ACCESS-CM2_ssp370_s1_w2015")
    ap.add_argument("--kappa", type=float, default=1.0)
    ap.add_argument("--ndraw", type=int, default=4)
    a = ap.parse_args()
    H = Hh.TabHeads.load("DEV-A", kappa=a.kappa)
    P = rl.load_params()
    rng = np.random.default_rng(20261002)
    rows = []
    for m in a.members.split(","):
        D = load(a.set, m)
        X = F.assemble(D, P)
        n = X.height
        print(f"{m}: {n} present stems ({int((X['Height'] >= HBIG).sum())} >= {HBIG} m)", flush=True)
        y_true = np.log(X["agb_y1"].to_numpy() / X["agb"].to_numpy())
        G_true = X["G_y1"].to_numpy().astype(np.float64)
        c_true = X["c_y1"].to_numpy().astype(np.float64)
        mu_tf, _, _ = H.growth(X, G_true, c_true)
        EG = H.expected_G(X)
        cEG = H.counter(X["c_y"].to_numpy(), EG, X["Age"].to_numpy())
        mu_EG, _, _ = H.growth(X, EG, cEG)
        pneg = H.p_gneg(X)
        typ, agb = X["Type"].to_numpy(), X["agb"].to_numpy()
        rho, sig = H.ar_params("dagb", typ, agb)
        draws, Gd, negd = [], [], []
        for _ in range(a.ndraw):
            G1 = H.sample_G(X, rng.uniform(size=n), rng.uniform(size=n))
            c1 = H.counter(X["c_y"].to_numpy(), G1, X["Age"].to_numpy())
            mu, _, _ = H.growth(X, G1, c1)
            draws.append(mu + np.sqrt(1 - rho ** 2) * sig * rng.standard_normal(n))
            Gd.append(G1)
            negd.append(G1 < 0)
        mu_draw = np.column_stack(draws)
        G_draw = np.column_stack(Gd)
        big = X["Height"].to_numpy() >= HBIG
        yr = X["Year"].to_numpy()
        for y in np.unique(yr):
            for cls, msk in (("lt15", ~big), ("ge15", big), ("all", np.ones(n, bool))):
                q = (yr == y) & msk
                if q.sum() < 30:
                    continue
                rows.append({
                    "member": m, "Year": int(y), "hcls": cls, "n": int(q.sum()),
                    "true_med": float(np.median(y_true[q])), "true_mean": float(np.mean(y_true[q])),
                    "tf_med": float(np.median(mu_tf[q])), "tf_mean": float(np.mean(mu_tf[q])),
                    "EG_med": float(np.median(mu_EG[q])), "EG_mean": float(np.mean(mu_EG[q])),
                    "draw_med": float(np.median(mu_draw[q])), "draw_mean": float(np.mean(mu_draw[q])),
                    "Gtrue_med": float(np.median(G_true[q])), "Gdraw_med": float(np.median(G_draw[q])),
                    "EG_med_G": float(np.median(EG[q])),
                    "pneg_true": float(np.mean(G_true[q] < 0)), "pneg_head": float(np.mean(pneg[q])),
                    "pneg_draw": float(np.mean(np.column_stack(negd)[q])),
                })
    R = pl.DataFrame(rows)
    out = os.path.join(XDE, "shared", "eval", f"growth_onestep_{a.set}.csv")
    R.write_csv(out)
    pl.Config.set_tbl_rows(400)
    pl.Config.set_tbl_cols(30)
    pl.Config.set_tbl_width_chars(260)
    S = (R.with_columns(dec=(pl.col("Year") // 10) * 10)
         .group_by("member", "dec", "hcls")
         .agg(pl.col("n").sum(), *[pl.col(c).mean() for c in R.columns if c not in ("member", "Year", "hcls", "n")])
         .sort("member", "hcls", "dec"))
    print(S.with_columns(pl.col(pl.Float64).round(4)))
    print("wrote", out)


if __name__ == "__main__":
    main()
