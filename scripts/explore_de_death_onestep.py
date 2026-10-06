"""explore_de_death_onestep.py — LINE X, Germany emulator: does the learned death head reproduce the original's
mortality PULSE years one step ahead, given the TRUE next-year growth efficiency or only given a sampled one?
(pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "death pulses ONE STEP")

On the original's own states (every printed living tree of a per-tree hash subsample), per year and height class:
  truth  realised death share (fate_y1 == 1)
  tf     mean p_death at the true G_{y+1} and c_{y+1}
  model  mean p_death at a sampled G1 (K draws; counter rule), with the pooled TAB sampler or the quantile one.

Usage:  python explore_de_death_onestep.py --cells-from <run dir> --gcm MPI-ESM1-2-HR --seed 2 [--sampler gqs]
        [--y0 1985] [--y1 2043] [--frac 0.1] [--K 4] [--tag gqs_mpi2]
Writes /p/tmp/jamirp/X_de/shared/eval/death_onestep_<tag>.csv
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_gdrift as gd  # noqa: E402
import explore_de_gquant as gq_  # noqa: E402
import explore_de_sh_rules as rl  # noqa: E402
import explore_de_tree_attrib as ta  # noqa: E402

HCUT = 10.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells-from", required=True, help="a run dir; its chunk files fix the cell set")
    ap.add_argument("--gcm", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--leg", default="ssp370")
    ap.add_argument("--sampler", choices=["pool", "gq", "gqs", "gqsc", "gqsc2"], default="gqs")
    ap.add_argument("--y0", type=int, default=1985)
    ap.add_argument("--y1", type=int, default=2043)
    ap.add_argument("--frac", type=float, default=0.1)
    ap.add_argument("--K", type=int, default=4)
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    st, P = ta.stepper()
    if a.sampler != "pool":
        gq_.load(st.split).attach(st, sign_cal={"gq": False, "gqs": True, "gqsc": "c", "gqsc2": "c2"}[a.sampler])
    f0 = sorted(glob.glob(os.path.join(a.cells_from, "chunk_*", "*.parquet")))
    cells = sorted(pl.concat([pl.scan_parquet(f).select("Cell") for f in f0 if os.path.basename(f).startswith(
        f"y{a.y0 + 1}_")]).unique().collect()["Cell"].to_list())
    print(f"cells: {len(cells)}", flush=True)
    mem = {"Historical": f"{a.gcm}_Historical_s{a.seed}_h1985", a.leg: f"{a.gcm}_{a.leg}_s{a.seed}_w2015"}
    sub = int(1000 * a.frac)
    rows = []
    for y in range(a.y0, a.y1 + 1):
        m = mem["Historical" if y < 2014 else a.leg]
        T = gd.truth_year(m, y, cells, P)
        T = T.filter(pl.Series(gd.key_hash(T) < sub))
        X = ta.with_agb(T)
        n = X.height
        dead = X["fate_y1"].to_numpy() == 1
        G_t = X["G_y1"].cast(pl.Float64).to_numpy()
        c_t = X["c_y1"].cast(pl.Float64).to_numpy()
        p_tf = st._p_death_learned(X, G_t, c_t)
        age = X["Age"].to_numpy()
        p_m, gneg_m, cert_m = [], [], []
        for k in range(a.K):
            G1 = st._sample_G(X, gd.unif(T, y, 2 * k), gd.unif(T, y, 2 * k + 1))[0]
            c1 = np.minimum(rl.counter_step(X["c_y"].to_numpy(), G1, age), st.cmax)
            p_m.append(st._p_death_learned(X, G1, c1))
            gneg_m.append(G1 < 0)
            cert_m.append(c1 >= st.cmax)
        p_m, gneg_m, cert_m = np.mean(p_m, axis=0), np.mean(gneg_m, axis=0), np.mean(cert_m, axis=0)
        h = X["Height"].to_numpy()
        c0 = np.rint(X["c_y"].cast(pl.Float64).to_numpy())
        for cls, q in (("lt10", h < HCUT), ("ge10", h >= HCUT), ("all", np.ones(n, bool))):
            r = {"year": y + 1, "hcls": cls, "n": int(q.sum()), "truth": float(dead[q].mean()),
                 "tf": float(p_tf[q].mean()), "model": float(p_m[q].mean()),
                 "G_true_med": float(np.median(G_t[q])),
                 "gneg_true": float((G_t[q] < 0).mean()), "gneg_model": float(gneg_m[q].mean()),
                 "certain_true": float((c_t[q] >= st.cmax).mean()), "certain_model": float(cert_m[q].mean())}
            # streak continuation by the current counter (TS.md "STREAK dynamics": start = c_y 0, p_k = c_y k)
            for kc in range(5):
                qk = q & (c0 == kc)
                r[f"n_c{kc}"] = int(qk.sum())
                r[f"gneg_true_c{kc}"] = float((G_t[qk] < 0).mean()) if qk.any() else float("nan")
                r[f"gneg_model_c{kc}"] = float(gneg_m[qk].mean()) if qk.any() else float("nan")
            rows.append(r)
        print(f"transition {y}->{y + 1}: {n} trees, truth {dead.mean():.4f} tf {p_tf.mean():.4f} "
              f"model {p_m.mean():.4f}", flush=True)
    R = pl.DataFrame(rows)
    out = os.path.join(ta.XDE, "shared", "eval", f"death_onestep_{a.tag}.csv")
    R.write_csv(out)
    pl.Config.set_tbl_rows(400)
    print(R.filter(pl.col("hcls") != "all").pivot(on="hcls", index="year", values=["truth", "tf", "model"])
          .with_columns(pl.exclude("year").round(4)))
    print("wrote", out)


if __name__ == "__main__":
    main()
