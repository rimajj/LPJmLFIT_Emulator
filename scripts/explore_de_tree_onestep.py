"""explore_de_tree_onestep.py — LINE X, Germany emulator: are the TAB growth and death heads biased one step ahead,
by tree size, on the original model's own states? (pre-registration: /p/tmp/jamirp/X_de/_status/TS.md)

Context: coupled TAB on MPI seed 2 (recruit_drift_ssp370_g2_mpi2.csv) matures early — stems < 15 m grow ~0.002-0.005
/yr faster than in the original from the first window on, biomass per stem runs +8..+17 %, and the trees it kills
are smaller than the original's. This checks the rollout's own one-step chain on the held-out eval rows (unweighted
u_hash sample) of the same member:
  G sampled (sign + magnitude + decile residual), counter rule, growth head + one AR innovation (e_prev = 0),
  death drawn from p_death at the drawn G/c — exactly TabHeads.transition, minus the closures.
Outputs per (member, 5-yr window, height class): survivor growth medians, death rates (drawn chain and
teacher-forced at the true G/c) and the size of the dead relative to the living.

Usage:  python explore_de_tree_onestep.py [--set SEED2] [--members ...] [--ndraw 4]
Writes /p/tmp/jamirp/X_de/shared/eval/tree_onestep_<set>.csv
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
HEDGES = [0.0, 10.0, 15.0, 25.0, 1e9]
HNAMES = ["lt10", "10-15", "15-25", "ge25"]
DEFAULT_MEMBERS = {
    "SEED2": "MPI-ESM1-2-HR_Historical_s2_h1985,MPI-ESM1-2-HR_ssp370_s2_w2015",
    "F5": "MPI-ESM1-2-HR_Historical_s1_h1985,MPI-ESM1-2-HR_ssp370_s1_w2015",
    "GCM": "ACCESS-CM2_Historical_s1_h1985,ACCESS-CM2_ssp370_s1_w2015",
}


def load(set_, member):
    fs = sorted(glob.glob(os.path.join(EVAL, set_, member, "y*.parquet")))
    assert fs, f"no eval rows for {set_}/{member}"
    D = pl.concat([pl.read_parquet(f) for f in fs], how="diagonal_relaxed")
    return D.filter((pl.col("fate_y1") <= 1) & (pl.col("Type") <= F.MAX_TREE_TYPE))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="SEED2")
    ap.add_argument("--members", default=None)
    ap.add_argument("--ndraw", type=int, default=4)
    a = ap.parse_args()
    members = (a.members or DEFAULT_MEMBERS[a.set]).split(",")
    H = Hh.TabHeads.load("DEV-A", kappa=1.0)
    P = rl.load_params()
    rng = np.random.default_rng(20261005)
    rows = []
    for m in members:
        D = load(a.set, m)
        X = F.assemble(D, P)
        n = X.height
        print(f"{m}: {n} present stems", flush=True)
        agb = X["agb"].to_numpy().astype(np.float64)
        y_true = np.log(X["agb_y1"].to_numpy() / agb)
        dead_true = X["fate_y1"].to_numpy() == 1
        G_true = X["G_y1"].to_numpy().astype(np.float64)
        c_true = X["c_y1"].to_numpy().astype(np.float64)
        pd_tf = H.p_death(X, G_true, c_true)
        typ = X["Type"].to_numpy()
        rho, sig = H.ar_params("dagb", typ, agb)
        mu_d, pd_d, dead_d = [], [], []
        for _ in range(a.ndraw):
            G1 = H.sample_G(X, rng.uniform(size=n), rng.uniform(size=n))
            c1 = H.counter(X["c_y"].to_numpy(), G1, X["Age"].to_numpy())
            mu, _, _ = H.growth(X, G1, c1)
            mu_d.append(mu + np.sqrt(1 - rho ** 2) * sig * rng.standard_normal(n))
            p = H.p_death(X, G1, c1)
            pd_d.append(p)
            dead_d.append(rng.uniform(size=n) < p)
        mu_d, pd_d, dead_d = np.column_stack(mu_d), np.column_stack(pd_d), np.column_stack(dead_d)
        hc = np.digitize(X["Height"].to_numpy(), HEDGES[1:-1])
        win = (X["Year"].to_numpy() - 1985) // 5 * 5 + 1985
        for w in np.unique(win):
            for k, name in [(-1, "all"), *enumerate(HNAMES)]:
                q = (win == w) & ((hc == k) if k >= 0 else True)
                if q.sum() < 200:
                    continue
                qa = np.where(q)[0]
                surv_m = ~dead_d[qa]
                rows.append({
                    "member": m, "win": int(w), "hcls": name, "n": int(q.sum()),
                    "grow_med_true": float(np.median(y_true[q])),
                    "grow_med_model": float(np.median(mu_d[qa])),
                    "surv_grow_med_true": float(np.median(y_true[q & ~dead_true])),
                    "surv_grow_med_model": float(np.median(mu_d[qa][surv_m])),
                    "death_true": float(dead_true[q].mean()),
                    "death_model": float(pd_d[qa].mean()),
                    "death_tf": float(pd_tf[q].mean()),
                    # size of the dead relative to all present stems of the class/window
                    "dead_rel_true": float(agb[q & dead_true].mean() / agb[q].mean()) if (q & dead_true).any()
                    else None,
                    "dead_rel_model": float((pd_d[qa] * agb[qa, None]).sum() / pd_d[qa].sum() / agb[q].mean()),
                    "dead_rel_tf": float((pd_tf[q] * agb[q]).sum() / pd_tf[q].sum() / agb[q].mean()),
                })
    R = pl.DataFrame(rows)
    out = os.path.join(XDE, "shared", "eval", f"tree_onestep_{a.set}.csv")
    R.write_csv(out)
    pl.Config.set_tbl_rows(400)
    pl.Config.set_tbl_cols(30)
    pl.Config.set_tbl_width_chars(260)
    print(R.with_columns(pl.col(pl.Float64).round(4)))
    print("wrote", out)


if __name__ == "__main__":
    main()
