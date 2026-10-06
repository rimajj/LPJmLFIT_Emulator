"""explore_de_gdrift.py — LINE X, Germany emulator: where does the coupled TAB free run's EARLY growth-efficiency drift
come from? (pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "early G-state drift")

The tree's last-year growth efficiency G_y is the input that carries the first-decade small-tree growth excess of the
coupled run (explore_de_tree_attrib.py). G_y in the free run is the stepper's own previous draw (_sample_G), so its
error is either (a) the start convention, (b) a one-step bias of the sampler, (c) the sampler's own lagged-G loop, or
(d) another drifted input. Four statistics, all on the original's members of the probed arm:

  S0/S1  paired trees (same tree living + printed in both runs, as in explore_de_tree_attrib): G_y free vs truth
         per year (S0 = the start year, which must be identical), and the free run's own draw G1 vs truth G_{y+1}.
  S2     one-step sampler on the ORIGINAL's inputs (K draws) vs the truth's G_{y+1}, all printed living trees of a
         fixed per-tree hash subsample.
  S3     G-ONLY CHAIN on the original: every input from the truth except G_y and c_y, which are the chain's own previous
         draw and counter; trees entering later start from the truth. Same random numbers as S2 in each year.
  S4     swap attribution of the sampled G on paired trees (tree_attrib groups), median and mean.
Statistics per year and height class (< 15 m, >= 15 m): quantiles 10/25/50/75/90, mean, P(G < 0).

Usage:  python explore_de_gdrift.py --probe <run dir> --dump <dump dir> --gcm MPI-ESM1-2-HR --seed 2 --tag g2hs_mpi2
        [--y1 2004] [--frac 0.1] [--K 4]
Writes /p/tmp/jamirp/X_de/shared/eval/gdrift_<tag>_{paired,onestep_chain,swap}.csv
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_gquant as gq_  # noqa: E402
import explore_de_sh_rules as rl  # noqa: E402
import explore_de_tab_features as F  # noqa: E402
import explore_de_tree_attrib as ta  # noqa: E402

XDE = ta.XDE
KEY = ta.KEY
HBIG = ta.HBIG
QS = (10, 25, 50, 75, 90)


def gstats(v: np.ndarray) -> dict:
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return {}
    q = np.percentile(v, QS)
    return {**{f"q{p}": float(x) for p, x in zip(QS, q, strict=True)}, "mean": float(v.mean()),
            "pneg": float((v < 0).mean()), "n": int(len(v))}


def key_hash(df: pl.DataFrame) -> np.ndarray:
    return (df.select(pl.struct(*KEY).hash(20261006)).to_series() % 1000).to_numpy()


def unif(df: pl.DataFrame, year: int, stream: int) -> np.ndarray:
    h = df.select(pl.struct(*KEY).hash(1_000_003 * year + 7919 * stream)).to_series().to_numpy()
    return (h >> np.uint64(11)).astype(np.float64) / float(1 << 53)


def truth_year(m: str, y: int, cells: list, P) -> pl.DataFrame:
    T = F.assemble(F.raw_training_frame(m, y, cells).collect(), P).filter(pl.col("fate_y1") <= 1)
    return T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", required=True)
    ap.add_argument("--dump", required=True)
    ap.add_argument("--gcm", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--leg", default="ssp370")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--y1", type=int, default=2004)
    ap.add_argument("--frac", type=float, default=0.1)
    ap.add_argument("--K", type=int, default=4)
    ap.add_argument("--sampler", choices=["pool", "gq", "gqc", "gqs"], default="pool",
                    help="pool = TAB stepper; gq = explore_de_gquant; gqc = conformalised; gqs = gq + Platt sign")
    a = ap.parse_args()
    st, P = ta.stepper()
    if a.sampler in ("gq", "gqc", "gqs"):
        gq_.load(st.split, conformal=a.sampler == "gqc").attach(st, sign_cal=a.sampler == "gqs")
    files = sorted(glob.glob(os.path.join(a.dump, "*", "*.parquet")))
    files = [f for f in files if int(os.path.basename(f)[1:5]) <= a.y1]
    A = pl.concat([pl.read_parquet(f) for f in files], how="vertical_relaxed")
    cells = sorted(A["Cell"].unique().to_list())
    years = sorted(A["Year"].unique().to_list())
    feat = [c for c in A.columns if c not in KEY + ["Year", *ta.DUMPED]]
    print(f"dump: {A.height} rows, {len(cells)} cells, years {years[0]}-{years[-1]}", flush=True)
    mem = {"Historical": f"{a.gcm}_Historical_s{a.seed}_h1985", a.leg: f"{a.gcm}_{a.leg}_s{a.seed}_w2015"}
    sub = int(1000 * a.frac)
    rows_p, rows_c, rows_s = [], [], []
    CH = None  # S3 chain state: KEY + G_ch, c_ch, yic (years in chain)
    for y in years:
        m = mem["Historical" if y < 2014 else a.leg]
        T = truth_year(m, y, cells, P)
        T = T.select(*KEY, *[c for c in feat if c not in ("Type", "SLA", "Wooddens")], "G_y1", "fate_y1")
        Ay = A.filter(pl.col("Year") == y)
        # ---- S0/S1 paired
        J = Ay.join(T, on=KEY, how="inner", suffix="_T")
        big = J["Height"].to_numpy() >= HBIG
        for cls, msk in (("lt15", ~big), ("ge15", big), ("all", np.ones(J.height, bool))):
            for lab, v in (("Gy_free", J["G_y"]), ("Gy_truth", J["G_y_T"]), ("G1_free", J["G1"]),
                           ("G1_truth", J["G_y1"])):
                rows_p.append({"year": y, "hcls": cls, "what": lab,
                               **gstats(v.cast(pl.Float64).to_numpy()[msk])})
        if y == years[0]:
            d = np.abs(J["G_y"].cast(pl.Float64).to_numpy() - J["G_y_T"].cast(pl.Float64).to_numpy())
            rel = d / np.maximum(np.abs(J["G_y_T"].cast(pl.Float64).to_numpy()), 1e-6)
            print(f"S0 start gate {y}: paired {J.height}, max|dG| {np.nanmax(d):.3e}, "
                  f"share rel>1e-3 {np.mean(rel > 1e-3):.4f}", flush=True)
        # ---- S2 one-step on truth + S3 G-only chain, per-tree hash subsample
        Ts = T.filter(pl.Series(key_hash(T) < sub))
        n = Ts.height
        X = Ts.select("Type", "SLA", "Wooddens", *[c for c in feat if c not in ("Type", "SLA", "Wooddens")])
        if CH is None:
            Xc = X.with_columns(yic=pl.lit(0, pl.Int16))
        else:
            Jc = Ts.select(KEY).with_row_index("_i").join(CH, on=KEY, how="left").sort("_i")
            has = Jc["G_ch"].is_not_null().to_numpy()
            Xc = X.with_columns(
                G_y=pl.Series(np.where(has, Jc["G_ch"].fill_null(0.0).to_numpy(), X["G_y"].to_numpy()))
                .cast(X.schema["G_y"]),
                c_y=pl.Series(np.where(has, Jc["c_ch"].fill_null(0).to_numpy(), X["c_y"].to_numpy()))
                .cast(X.schema["c_y"]),
                yic=pl.Series(np.where(has, Jc["yic"].fill_null(0).to_numpy() + 1, 0)).cast(pl.Int16))
        Xc_in = Xc.drop("yic")
        g_true = Ts["G_y1"].cast(pl.Float64).to_numpy()
        hgt = Ts["Height"].to_numpy()
        yic = Xc["yic"].to_numpy()
        G1_os, G1_ch = [], []
        for k in range(a.K):
            u_s, u_r = unif(Ts, y, 2 * k), unif(Ts, y, 2 * k + 1)
            G1_os.append(st._sample_G(X, u_s, u_r)[0])
            G1_ch.append(st._sample_G(Xc_in, u_s, u_r)[0])
        # carry draw 0 of the chain forward (survivors are found by key next year)
        age = Xc_in["Age"].to_numpy()
        c1 = rl.counter_step(Xc_in["c_y"].to_numpy(), G1_ch[0], age).astype(np.int64)
        CH = Ts.select(KEY).with_columns(G_ch=pl.Series(G1_ch[0]), c_ch=pl.Series(np.minimum(c1, st.cmax)),
                                         yic=pl.Series(yic))
        for cls, msk in (("lt15", hgt < HBIG), ("ge15", hgt >= HBIG), ("all", np.ones(n, bool))):
            rows_c.append({"year": y, "hcls": cls, "what": "truth_G1", **gstats(g_true[msk])})
            rows_c.append({"year": y, "hcls": cls, "what": "onestep_G1",
                           **gstats(np.concatenate([g[msk] for g in G1_os]))})
            rows_c.append({"year": y, "hcls": cls, "what": "chain_G1",
                           **gstats(np.concatenate([g[msk] for g in G1_ch]))})
            rows_c.append({"year": y, "hcls": cls, "what": "chain_Gy_in",
                           **gstats(Xc["G_y"].cast(pl.Float64).to_numpy()[msk])})
            rows_c.append({"year": y, "hcls": cls, "what": "truth_Gy_in",
                           **gstats(X["G_y"].cast(pl.Float64).to_numpy()[msk])})
            for lo, hi in ((1, 3), (4, 9), (10, 99)):
                q = msk & (yic >= lo) & (yic <= hi)
                if q.sum() >= 200:
                    rows_c.append({"year": y, "hcls": cls, "what": f"chain_G1_yic{lo}-{hi}",
                                   **gstats(np.concatenate([g[q] for g in G1_ch]))})
                    rows_c.append({"year": y, "hcls": cls, "what": f"truth_G1_yic{lo}-{hi}", **gstats(g_true[q])})
        # ---- S4 swaps on paired trees (subsample), years up to 1994 only
        if y <= 1994:
            Js = J.filter(pl.Series(key_hash(J) < sub))
            XA = Js.select("Type", "SLA", "Wooddens", *[c for c in feat if c not in ("Type", "SLA", "Wooddens")])
            XT = Js.select("Type", "SLA", "Wooddens",
                           *[pl.col(f"{c}_T").alias(c) for c in feat if c not in ("Type", "SLA", "Wooddens")])
            bigs = Js["Height"].to_numpy() >= HBIG
            U = [(unif(Js, y, 100 + 2 * k), unif(Js, y, 101 + 2 * k)) for k in range(a.K)]

            def sw(label, Xx, U=U, bigs=bigs, y=y):
                G = [st._sample_G(Xx, u_s, u_r)[0] for u_s, u_r in U]
                for cls, msk in (("lt15", ~bigs), ("ge15", bigs)):
                    rows_s.append({"year": y, "hcls": cls, "swap": label,
                                   **gstats(np.concatenate([g[msk] for g in G]))})

            sw("none (truth inputs)", XT)
            sw("ALL (free-run inputs)", XA)
            for g, cols in ta.GROUPS.items():
                sw(f"only {g} from free run", XT.with_columns([XA[c] for c in cols]))
                sw(f"all except {g}", XA.with_columns([XT[c] for c in cols]))
        print(f"year {y}: paired {J.height}, chain sample {n}, chain carried {(yic > 0).sum()}", flush=True)
    out = os.path.join(XDE, "shared", "eval", f"gdrift_{a.tag}")
    Pp, Pc, Ps = pl.DataFrame(rows_p), pl.DataFrame(rows_c), pl.DataFrame(rows_s)
    Pp.write_csv(out + "_paired.csv")
    Pc.write_csv(out + "_onestep_chain.csv")
    Ps.write_csv(out + "_swap.csv")
    pl.Config.set_tbl_rows(400)
    pl.Config.set_tbl_cols(30)
    pl.Config.set_tbl_width_chars(260)
    for v in ("q50", "mean"):
        print(f"== paired lt15 {v}")
        print(Pp.filter(pl.col("hcls") == "lt15").pivot(on="what", index="year", values=v).with_columns(
            pl.exclude("year").round(2)))
        print(f"== onestep/chain lt15 {v}")
        print(Pc.filter((pl.col("hcls") == "lt15") & ~pl.col("what").str.contains("yic")).pivot(
            on="what", index="year", values=v).with_columns(pl.exclude("year").round(2)))
    print("== swaps lt15 q50 / mean, 1985-94 pooled over years (mean of yearly values)")
    print(Ps.filter(pl.col("hcls") == "lt15").group_by("swap", maintain_order=True)
          .agg(pl.col("q50").mean().round(2), pl.col("mean").mean().round(2), pl.col("pneg").mean().round(4)))
    print("wrote", out + "_*.csv")


if __name__ == "__main__":
    main()
