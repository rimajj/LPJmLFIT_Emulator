"""explore_de_tree_attrib.py — LINE X, Germany emulator: which drifted input makes the coupled TAB free run grow its
SMALL trees too fast and thin too little? Same-tree input-swap attribution of the growth and survival chain.
(pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, second section)

Data: an instrumented re-run of a scored coupled arm (explore_de_tab_probe2.py: same heads, same random numbers,
plus a dump of every head input for every printed living tree) and the original model's transition rows of the
same member-years (explore_de_tab_features.raw_training_frame: true features, true G_{y+1}, agb_{y+1}, fate).
GATES (each stops the run):
  g1  the probe run's emitted rosters == the scored run's chunk files (the dump describes THAT run)
  g2  the stepper's own growth / survival functions re-evaluated on the dumped inputs == the dumped mu_dagb / p_death
  g3  on the paired rows the climate columns of X_free and X_truth are identical (same cell-year)
Pairing: the same tree (Cell, Patch, Type, ID, SLA, Wooddens) living and printed in both at year y.
Chain (the stepper's own functions, its calibration, common random numbers across all swaps, K draws per tree):
  G1 ~ _sample_G(X; u_s, u_r) -> c1 = counter rule -> mu = _growth(X, G1, c1) without the AR term,
  p = _p_death_learned(X, G1, c1);   statistics per 10-yr window and free-run height class (< 15 m, >= 15 m):
  median / mean mu (growth), mean p (death), evaluated on X_truth, X_free and X_truth with ONE group from X_free
  (and X_free with one group from X_truth).

Usage:  python explore_de_tree_attrib.py --scored <run dir> --probe <run dir> --dump <dump dir> --gcm MPI-ESM1-2-HR
        --seed 2 [--chunks 0,1] [--tag g2hs_mpi2]
Writes /p/tmp/jamirp/X_de/shared/eval/tree_attrib_<tag>.csv (+ _shift.csv)
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_sh_rules as rl  # noqa: E402
import explore_de_tab_features as F  # noqa: E402
import explore_de_tab_heads as Hh  # noqa: E402
import explore_de_tab_stepper as ts  # noqa: E402

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
KEY = ["Cell", "Patch", "Type", "ID", "SLA", "Wooddens"]
HBIG = 15.0
K = 2
DUMPED = ["G1", "p_gneg", "c1", "mu_dagb", "e_prev", "e_new", "da", "p_death"]
GROUPS = {
    "LAGGED_OWN": ["c_y", "G_y", "d_agb_prev", "rel_dagb_prev", "is_new"],
    "G_y": ["G_y"],
    "c_y": ["c_y"],
    "dagb_prev": ["d_agb_prev", "rel_dagb_prev"],
    "TREE_size": ["Height", "log_agb"],
    "TREE_shape": ["log_vegc", "LAI", "fpc_ind", "D95"],
    "Age": ["Age"],
    "STAND": ["n_live", "sum_fpc", "sum_agb", "height_rank", "rel_rank", "fpc_above"],
    "stand_cover": ["sum_fpc", "fpc_above"],
    "stand_count_rank": ["n_live", "height_rank", "rel_rank"],
    "stand_agb": ["sum_agb"],
    "GRASS": ["grass8_fpc", "grass8_LAI", "grass8_agb"],
    "CELL": ["cell_stems_per_patch"],
    "LOSS_HIST": ["flo0", "flo1", "flo2", "flo3", "flo4", "flo_m5_19"],
}


def gate_roster(scored, probe, chunks):
    bad, n = [], 0
    for k in chunks:
        fp = sorted(glob.glob(os.path.join(probe, f"chunk_{k:03d}", "*.parquet")))
        assert fp, f"probe chunk {k} missing"
        for f in fp:
            n += 1
            g = os.path.join(scored, f"chunk_{k:03d}", os.path.basename(f))
            a = pl.read_parquet(f).sort(["Year", *KEY])
            b = pl.read_parquet(g).sort(["Year", *KEY])
            if a.shape != b.shape or not a.equals(b):
                bad.append(os.path.basename(f))
    return {"files_checked": n, "differ": bad}


def stepper():
    st = ts.TabAL()
    st.H = Hh.TabHeads.load(st.split)
    P = rl.load_params()
    c = st.cal
    st.k_g, st.k_gr, st.k_sv = st.kappa * c["kappa_g"], st.kappa * c["kappa_growth"], st.kappa * c["kappa_surv"]
    st.cmax = int(P.g["bm_inc_counter_max"])
    st.P = P
    return st, P


def with_agb(X):
    """the dump carries log_agb only; _growth reads agb solely to pick the AR (rho, sigma) size class, and the AR term
    is zero here (e_prev = z = 0), so exp(log_agb) at float32 precision cannot change mu."""
    return X if "agb" in X.columns else X.with_columns(agb=pl.col("log_agb").cast(pl.Float64).exp())


def chain(st, X, U):
    """mean over K common-random-number draws of the growth mean (no AR term) and of the survival probability."""
    X = with_agb(X)
    n = X.height
    zero = {"dagb": np.zeros(n), "dvegc": np.zeros(n)}
    mu, pd = np.zeros(n), np.zeros(n)
    c_y, age = X["c_y"].to_numpy(), X["Age"].to_numpy()
    for u_s, u_r in U:
        G1, _ = st._sample_G(X, u_s, u_r)
        c1 = rl.counter_step(c_y, G1, age).astype(np.int64)
        da, _, _ = st._growth(X, G1, c1, zero, zero)
        mu += da / len(U)
        pd += st._p_death_learned(X, G1, c1) / len(U)
    return mu, pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scored", required=True)
    ap.add_argument("--probe", required=True)
    ap.add_argument("--dump", required=True)
    ap.add_argument("--gcm", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--leg", default="ssp370")
    ap.add_argument("--chunks", default="0,1")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--frac", type=float, default=0.1)
    a = ap.parse_args()
    chunks = [int(c) for c in a.chunks.split(",")]
    g1 = gate_roster(a.scored, a.probe, chunks)
    print("GATE g1 (probe == scored run):", json.dumps(g1), flush=True)
    if g1["differ"]:
        sys.exit(2)
    st, P = stepper()
    A = pl.concat([pl.read_parquet(f) for f in sorted(glob.glob(os.path.join(a.dump, "*", "*.parquet")))],
                  how="vertical_relaxed")
    cells = sorted(A["Cell"].unique().to_list())
    print(f"dump: {A.height} rows, {len(cells)} cells, years {A['Year'].min()}-{A['Year'].max()}", flush=True)
    # g2: the stepper's functions on the dumped inputs reproduce the dumped outputs
    smp = with_agb(A.filter(pl.col("Year").is_in([1990, 2010, 2030])))
    n0 = smp.height
    zero = {"dagb": np.zeros(n0), "dvegc": np.zeros(n0)}
    G1, c1 = smp["G1"].to_numpy().astype(np.float64), smp["c1"].to_numpy().astype(np.int64)
    mu2, _, _ = st._growth(smp, G1, c1, zero, zero)
    pd2 = st._p_death_learned(smp, G1, c1)
    g2 = {"growth": float(np.max(np.abs(mu2 - smp["mu_dagb"].to_numpy()))),
          "death": float(np.nanmax(np.abs(pd2 - smp["p_death"].to_numpy())))}
    print(f"GATE g2 max|stepper(dump) - dumped|: {g2}", flush=True)
    if max(g2.values()) > 1e-5:
        sys.exit(2)
    feat = [c for c in A.columns if c not in KEY + ["Year", *DUMPED]]
    mem = {"Historical": f"{a.gcm}_Historical_s{a.seed}_h1985", a.leg: f"{a.gcm}_{a.leg}_s{a.seed}_w2015"}
    parts = []
    for y in sorted(A["Year"].unique().to_list()):
        m = mem["Historical" if y < 2014 else a.leg]
        T = F.assemble(F.raw_training_frame(m, y, cells).collect(), P).filter(pl.col("fate_y1") <= 1)
        T = T.select(*KEY, *feat, "agb", "agb_y1", "G_y1", "fate_y1")
        parts.append(A.filter(pl.col("Year") == y).join(T, on=KEY, how="inner", suffix="_T"))
    J = pl.concat(parts, how="vertical_relaxed")
    print(f"paired: {J.height} tree-years ({J.height / A.height:.3f} of the dump)", flush=True)
    # fixed random subsample of tree-years (cost: every swap re-evaluates four boosted heads K times)
    J = J.filter((pl.struct(*KEY, "Year").hash(20261005) % 1000) < int(1000 * a.frac))
    print(f"subsample frac {a.frac}: {J.height} tree-years", flush=True)
    clim = [c for c in feat if c.startswith(("a_", "c85_")) or c in ("tstress_own_y1", "tmean_ann_y1",
                                                                     "twarm_month_y1", "soil_code")]
    g3 = {c: float(np.nanmax(np.abs(J[c].cast(pl.Float64).to_numpy() - J[f"{c}_T"].cast(pl.Float64).to_numpy())))
          for c in clim}
    print(f"GATE g3 climate columns identical on the pairing: worst |diff| {max(g3.values()):.2e}", flush=True)
    if max(g3.values()) > 1e-5:
        print(json.dumps({k: v for k, v in g3.items() if v > 1e-5}))
        sys.exit(2)
    XA = J.select("Type", "SLA", "Wooddens", *feat)
    XT = J.select("Type", "SLA", "Wooddens", *[pl.col(f"{c}_T").alias(c) for c in feat])
    n = J.height
    rng = np.random.default_rng(20261005)
    U = [(rng.uniform(size=n), rng.uniform(size=n)) for _ in range(K)]
    win = (J["Year"].to_numpy() - 1985) // 10 * 10 + 1985
    big = J["Height"].to_numpy() >= HBIG
    real_T = np.log(J["agb_y1"].to_numpy() / J["agb"].to_numpy())
    dead_T = J["fate_y1"].to_numpy() == 1
    rows = []

    def add(label, X):
        mu, pd = chain(st, X, U)
        for w in np.unique(win):
            for cls, msk in (("lt15", ~big), ("ge15", big)):
                q = (win == w) & msk
                if q.sum() < 100:
                    continue
                r = {"swap": label, "win": int(w), "hcls": cls, "n": int(q.sum()),
                     "mu_med": float(np.median(mu[q])), "mu_mean": float(np.mean(mu[q])),
                     "pdeath_mean": float(np.mean(pd[q]))}
                if label.startswith("none"):
                    r.update({"real_T_med": float(np.median(real_T[q])), "dead_T": float(dead_T[q].mean()),
                              "real_A_med": float(np.median(J["da"].to_numpy()[q])),
                              "pdeath_A_dump": float(np.nanmean(J["p_death"].to_numpy()[q]))})
                rows.append(r)
        print(f"  {label}", flush=True)

    add("none (truth inputs)", XT)
    add("ALL (free-run inputs)", XA)
    for g, cols in GROUPS.items():
        add(f"only {g} from free run", XT.with_columns([XA[c] for c in cols]))
        add(f"all except {g}", XA.with_columns([XT[c] for c in cols]))
    shift = []
    for c in sorted({c for v in GROUPS.values() for c in v}):
        x, t = XA[c].cast(pl.Float64).to_numpy(), XT[c].cast(pl.Float64).to_numpy()
        for w in np.unique(win):
            for cls, msk in (("lt15", ~big), ("ge15", big)):
                q = (win == w) & msk
                shift.append({"feature": c, "win": int(w), "hcls": cls, "free_med": float(np.nanmedian(x[q])),
                              "truth_med": float(np.nanmedian(t[q])), "free_mean": float(np.nanmean(x[q])),
                              "truth_mean": float(np.nanmean(t[q]))})
    R, S = pl.DataFrame(rows), pl.DataFrame(shift)
    out = os.path.join(XDE, "shared", "eval", f"tree_attrib_{a.tag}.csv")
    R.write_csv(out)
    S.write_csv(out.replace(".csv", "_shift.csv"))
    pl.Config.set_tbl_rows(400)
    pl.Config.set_tbl_cols(30)
    pl.Config.set_tbl_width_chars(260)
    print(R.filter(pl.col("swap").str.starts_with("none")).with_columns(pl.col(pl.Float64).round(4)))
    for v in ("mu_med", "pdeath_mean"):
        for cls in ("lt15", "ge15"):
            print(v, cls)
            print(R.filter(pl.col("hcls") == cls).pivot(on="win", index="swap", values=v)
                  .with_columns(pl.exclude("swap").round(4)))
    print("wrote", out)


if __name__ == "__main__":
    main()
