"""explore_de_growth_attrib.py — LINE X, Germany emulator: why do BIG trees grow slower in the TAB free run than in
the original? Same-tree, input-swap attribution of the growth chain.

Context (explore_de_recruit_drift.py, explore_de_recruit_attrib.py, 2026-10-02): the free run's canopy stays too open
because stems >= 15 m grow ~15-25 % slower (median dln agb) than in the original; deaths remove the same biomass.
The TAB growth chain is  G_{y+1} ~ gsign/gmag heads(X)  ->  counter rule  ->  dlog agb = dagb head(X, G_{y+1}, c_{y+1})
+ AR residual. The dagb head is nearly a function of G_{y+1} (teacher-forced R2 0.988 vs 0.85 with one G draw), so
the question is mostly which input of X moves the G heads.

Data: the instrumented re-run (explore_de_tab_probe.py: TabAL itself + a dump of X, G1, c1, mu, e per tree >= 12 m)
and the original's SH3 transition rows of the same member-years (explore_de_tab_features.raw_training_frame: true
features, true G_{y+1}, true agb_{y+1}).
GATES (each stops the run):
  g1  the probe run's emitted rosters == the analysed tabAL run's chunk files (the dump describes THAT run)
  g2  the dagb head re-evaluated on the dumped X, G1, c1 == the dumped mu_dagb (the dump is the stepper's input)
  g3  on the paired rows the climate columns of X_free and X_truth are identical (the pairing is the same cell-year)
Pairing: the same tree (Cell, Patch, Type, ID, SLA, Wooddens) living and printed in both at year y, >= 15 m in the
free run. Statistic per decade: mean / median over paired trees of the deterministic chain
  EG(X) = plug-in E[G_{y+1}];  mu(X) = dagb head(X, EG, counter(c_y, EG, Age))
on X_truth, X_free, and X_truth with ONE group taken from X_free (and X_free with one group from X_truth).
Pre-registered: (a) LAGGED-OWN (G_y, d_agb_prev, rel_dagb_prev, c_y) carrying most of the gap = the head leans on its
own noisy past output (a free-run-only input shift); (b) TREE (LAI, fpc_ind, D95, Height, log_vegc at the same agb)
= the closure heads drift the tree's shape; (c) STAND (n_live, sum_fpc, fpc_above, height_rank, ...) = competition
from the extra stems; (d) none — X_free gives the same EG as X_truth and the gap is the G sampling itself.

Usage:  python explore_de_growth_attrib.py [--chunks 0,1]
Writes /p/tmp/jamirp/X_de/shared/eval/growth_attrib_tabAL.csv
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

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
RUN_A = os.path.join(XDE, "runs", "tabAL", "ACCESS-CM2_s1_1985-2044_ssp126+ssp245+ssp370_actual_r1")
RUN_P = os.path.join(XDE, "runs", "tabAL", "ACCESS-CM2_s1_1985-2044_ssp370_actual_r1")
DUMP = os.path.join(XDE, "runs", "_tabprobe", "dump")
KEY = ["Cell", "Patch", "Type", "ID", "SLA", "Wooddens"]
MEMBERS = {"Historical": "ACCESS-CM2_Historical_s1_h1985", "ssp370": "ACCESS-CM2_ssp370_s1_w2015"}
HBIG = 15.0
GROUPS = {
    "LAGGED_OWN": ["c_y", "G_y", "d_agb_prev", "rel_dagb_prev", "is_new"],
    "G_y": ["G_y"],
    "dagb_prev": ["d_agb_prev", "rel_dagb_prev"],
    "TREE": ["Height", "log_agb", "log_vegc", "LAI", "fpc_ind", "D95"],
    "TREE_shape": ["LAI", "fpc_ind", "D95", "log_vegc"],
    "TREE_size": ["Height", "log_agb"],
    "STAND": ["n_live", "sum_fpc", "sum_agb", "height_rank", "rel_rank", "fpc_above"],
    "fpc_above": ["fpc_above"],
    "rank": ["height_rank", "rel_rank"],
    "GRASS": ["grass8_fpc", "grass8_LAI", "grass8_agb"],
    "CELL": ["cell_stems_per_patch"],
    "LOSS_HIST": ["flo0", "flo1", "flo2", "flo3", "flo4", "flo_m5_19"],
}


def gate_roster(chunks):
    bad = []
    for k in chunks:
        fp = sorted(glob.glob(os.path.join(RUN_P, f"chunk_{k:03d}", "*.parquet")))
        assert fp, f"probe chunk {k} missing"
        for f in fp:
            g = os.path.join(RUN_A, f"chunk_{k:03d}", os.path.basename(f))
            a = pl.read_parquet(f).sort(["Year", *KEY])
            b = pl.read_parquet(g).sort(["Year", *KEY])
            if a.shape != b.shape or not a.equals(b):
                bad.append(os.path.basename(f))
    return {"files_checked": sum(len(glob.glob(os.path.join(RUN_P, f"chunk_{k:03d}", "*.parquet"))) for k in chunks),
            "differ": bad}


def chain(H, X):
    EG = H.expected_G(X)
    c1 = H.counter(X["c_y"].to_numpy(), EG, X["Age"].to_numpy())
    mu, _, _ = H.growth(X, EG, c1)
    return EG, mu


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", default="0,1")
    a = ap.parse_args()
    chunks = [int(c) for c in a.chunks.split(",")]
    g1 = gate_roster(chunks)
    print("GATE g1 (probe == analysed run):", json.dumps(g1), flush=True)
    if g1["differ"]:
        sys.exit(2)
    H = Hh.TabHeads.load("DEV-A")
    P = rl.load_params()
    A = pl.concat([pl.read_parquet(f) for f in sorted(glob.glob(os.path.join(DUMP, "*", "*.parquet")))],
                  how="vertical_relaxed").filter(pl.col("Height") >= HBIG)
    cells = sorted(A["Cell"].unique().to_list())
    print(f"dump: {A.height} rows >= {HBIG} m, {len(cells)} cells, years {A['Year'].min()}-{A['Year'].max()}",
          flush=True)
    # g2: the dump is the stepper's input
    smp = A.filter(pl.col("Year").is_in([1990, 2010, 2030]))
    mu2, _, _ = H.growth(smp, smp["G1"].to_numpy(), smp["c1"].to_numpy().astype(np.float64))
    g2 = float(np.max(np.abs(mu2 - smp["mu_dagb"].to_numpy())))
    print(f"GATE g2 max|mu(dump) - mu_dagb| = {g2:.2e}", flush=True)
    if g2 > 1e-5:
        sys.exit(2)
    feat = [c for c in A.columns if c not in KEY + ["Year", "G1", "p_gneg", "c1", "mu_dagb", "e_prev", "e_new", "da"]]
    rows_out, parts = [], []
    for y in sorted(A["Year"].unique().to_list()):
        m = MEMBERS["Historical" if y < 2014 else "ssp370"]
        T = F.assemble(F.raw_training_frame(m, y, cells).collect(), P).filter(pl.col("fate_y1") <= 1)
        T = T.select(*KEY, *feat, "agb", "agb_y1", "G_y1", "c_y1")
        Ay = A.filter(pl.col("Year") == y)
        J = Ay.join(T, on=KEY, how="inner", suffix="_T")
        parts.append(J)
    J = pl.concat(parts, how="vertical_relaxed")
    print(f"paired: {J.height} tree-years ({J.height / A.height:.3f} of the dump)", flush=True)
    clim = [c for c in feat if c.startswith("a_") or c.startswith("c85_") or c in ("tstress_own_y1", "tmean_ann_y1",
                                                                                   "twarm_month_y1", "soil_code")]
    g3 = {c: float(np.nanmax(np.abs(J[c].cast(pl.Float64).to_numpy() - J[f"{c}_T"].cast(pl.Float64).to_numpy())))
          for c in clim}
    worst = max(g3.values())
    print(f"GATE g3 climate columns identical on the pairing: worst |diff| {worst:.2e}", flush=True)
    if worst > 1e-5:
        print(json.dumps({k: v for k, v in g3.items() if v > 1e-5}))
        sys.exit(2)
    XA = J.select("Type", "SLA", "Wooddens", *feat)
    XT = J.select("Type", "SLA", "Wooddens", *[pl.col(f"{c}_T").alias(c) for c in feat])
    dec = (J["Year"].to_numpy() // 10) * 10
    real_T = np.log(J["agb_y1"].to_numpy() / J["agb"].to_numpy())
    real_A = J["da"].to_numpy()
    G_T = J["G_y1"].to_numpy().astype(np.float64)
    G_A = J["G1"].to_numpy().astype(np.float64)

    def add(label, X, extra=None):
        EG, mu = chain(H, X)
        for d in [*np.unique(dec), 0]:
            q = np.ones(len(dec), bool) if d == 0 else dec == d
            r = {"swap": label, "decade": int(d), "n": int(q.sum()), "EG_mean": float(EG[q].mean()),
                 "EG_med": float(np.median(EG[q])), "mu_mean": float(mu[q].mean()), "mu_med": float(np.median(mu[q]))}
            if extra is not None:
                r.update({k: float(f(v[q])) for k, (v, f) in extra.items()})
            rows_out.append(r)

    ex = {"real_T_med": (real_T, np.median), "real_T_mean": (real_T, np.mean), "real_A_med": (real_A, np.median),
          "real_A_mean": (real_A, np.mean), "G_T_med": (G_T, np.median), "G_A_med": (G_A, np.median),
          "G_T_mean": (G_T, np.mean), "G_A_mean": (G_A, np.mean), "pneg_T": (G_T < 0, np.mean),
          "pneg_A": (G_A < 0, np.mean), "e_A_mean": (J["e_new"].to_numpy(), np.mean),
          "muA_dump_med": (J["mu_dagb"].to_numpy(), np.median)}
    add("none (truth inputs)", XT, ex)
    add("ALL (free-run inputs)", XA)
    for g, cols in GROUPS.items():
        add(f"only {g} from free run", XT.with_columns([XA[c] for c in cols]))
        add(f"all except {g}", XA.with_columns([XT[c] for c in cols]))
    # input shift of each feature on the pairing (free - truth), median per decade
    shift = []
    for c in sorted({c for v in GROUPS.values() for c in v}):
        x, t = XA[c].cast(pl.Float64).to_numpy(), XT[c].cast(pl.Float64).to_numpy()
        for d in np.unique(dec):
            q = dec == d
            shift.append({"feature": c, "decade": int(d), "free_med": float(np.nanmedian(x[q])),
                          "truth_med": float(np.nanmedian(t[q])), "free_mean": float(np.nanmean(x[q])),
                          "truth_mean": float(np.nanmean(t[q]))})
    R = pl.DataFrame(rows_out)
    S = pl.DataFrame(shift)
    out = os.path.join(XDE, "shared", "eval", "growth_attrib_tabAL.csv")
    R.write_csv(out)
    S.write_csv(out.replace(".csv", "_shift.csv"))
    pl.Config.set_tbl_rows(400)
    pl.Config.set_tbl_cols(30)
    pl.Config.set_tbl_width_chars(260)
    print(R.filter(pl.col("swap") == "none (truth inputs)").with_columns(pl.col(pl.Float64).round(4)))
    print(R.pivot(on="decade", index="swap", values="mu_med").with_columns(pl.exclude("swap").round(4)))
    print(R.pivot(on="decade", index="swap", values="EG_mean").with_columns(pl.exclude("swap").round(4)))
    print(S.with_columns(pl.col(pl.Float64).round(4)))
    print("wrote", out)


if __name__ == "__main__":
    main()
