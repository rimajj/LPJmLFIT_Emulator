"""explore_de_gpit.py — LINE X, Germany emulator: is the TAB growth-efficiency sampler CALIBRATED one step ahead?
(pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "calibration of the G sampler one step ahead")

For every original tree-year of a member (per-tree hash subsample) the EXACT probability integral transform of the
truth's G_{y+1} under the stepper's sampler (_sample_G: sign ~ Bernoulli(sigmoid(gsign + logit_off_g)); log|G| =
magnitude head of that sign + a residual from the empirical pool of its predicted-value decile):
    g < 0:  PIT = p * P(r > log(-g) - m_neg)            g > 0:  PIT = p + (1 - p) * P(r <= log(g) - m_pos)
(continuous pools, so the tie convention does not matter). Uniform PIT = calibrated. Summaries per group: share
PIT < 0.5, < 0.1, > 0.9, in 0.25-0.75, mean PIT, and the 10-bin histogram.

Usage:  python explore_de_gpit.py --gcm MPI-ESM1-2-HR --seed 2 --cells-from <dump dir> --tag mpi2 [--y0 1985 --y1 2043]
Writes /p/tmp/jamirp/X_de/shared/eval/gpit_<tag>.parquet (per tree-year PIT + groups) and gpit_<tag>_summary.csv
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
import explore_de_tab_stepper as ts  # noqa: E402
import explore_de_tree_attrib as ta  # noqa: E402

XDE = ta.XDE


def pit(st, X: pl.DataFrame, g: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    H, k = st.H, st.k_g
    kk = "k1" if k != 0.0 else "k0"
    p = ts.sigmoid(H.raw("gsign", X, k) + st.cal["logit_off_g"])
    if hasattr(st, "gq"):  # the quantile sampler (explore_de_gquant): no pools
        return st.gq.pit(X, g, p), p, np.full(len(g), -1)
    out = np.full(len(g), np.nan)
    pool_dec = np.full(len(g), -1)
    for s in ("neg", "pos"):
        msk = (g < 0) if s == "neg" else (g > 0)
        if not msk.any():
            continue
        m = H.raw(f"gmag_{s}", X.filter(pl.Series(msk)), k)
        edges, res = H.resid[(s, kk)]
        d = np.searchsorted(edges, m)
        x = np.log(np.abs(g[msk])) - m
        cdf = np.empty(len(m))
        for j in np.unique(d):
            q = d == j
            pool = np.sort(res[j])
            cdf[q] = np.searchsorted(pool, x[q], side="right") / len(pool)
        out[msk] = p[msk] * (1.0 - cdf) if s == "neg" else p[msk] + (1.0 - p[msk]) * cdf
        pool_dec[msk] = d
    return out, p, pool_dec


def summ(df: pl.DataFrame, by: list[str]) -> pl.DataFrame:
    u = pl.col("pit")
    pb = [pl.col(c).mean() for c in ("pb_new", "pb_old") if c in df.columns]
    return (df.group_by(by).agg(
        *pb, n=pl.len(), lt50=(u < 0.5).mean(), lt10=(u < 0.1).mean(), gt90=(u > 0.9).mean(),
        mid=((u >= 0.25) & (u <= 0.75)).mean(), mean=u.mean(),
        **{f"b{i}": ((u >= i / 10) & (u < (i + 1) / 10)).mean() for i in range(10)})
        .sort(by))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gcm", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--leg", default="ssp370")
    ap.add_argument("--cells-from", required=True, help="a probe dump dir; its 1985 files give the cell set")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--y0", type=int, default=1985)
    ap.add_argument("--y1", type=int, default=2043)
    ap.add_argument("--frac", type=float, default=0.1)
    ap.add_argument("--sampler", choices=["pool", "gq"], default="pool",
                    help="pool = the TAB stepper's own; gq = the quantile model of explore_de_gquant")
    a = ap.parse_args()
    st, P = ta.stepper()
    if a.sampler == "gq":
        gq_.load(st.split).attach(st)
    cells = sorted(set().union(*[set(pl.read_parquet(f, columns=["Cell"])["Cell"].unique().to_list())
                                 for f in glob.glob(os.path.join(a.cells_from, "*", "y1985_*.parquet"))]))
    feats = []
    for h in ("gsign", "gmag_neg", "gmag_pos"):
        meta = st.H.m[h][2]
        feats += meta["features_B0"] + meta["features_B1"]
    if hasattr(st, "gq"):
        feats += st.gq.feats
    feats = list(dict.fromkeys(feats))
    print(f"cells {len(cells)}, sampler features {len(feats)}", flush=True)
    mem = {"Historical": f"{a.gcm}_Historical_s{a.seed}_h1985", a.leg: f"{a.gcm}_{a.leg}_s{a.seed}_w2015"}
    parts = []
    for y in range(a.y0, a.y1 + 1):
        m = mem["Historical" if y < 2014 else a.leg]
        T = gd.truth_year(m, y, cells, P)
        T = T.filter(pl.Series(gd.key_hash(T) < int(1000 * a.frac)) & pl.col("G_y1").is_not_null()
                     & (pl.col("G_y1") != 0))
        g = T["G_y1"].cast(pl.Float64).to_numpy()
        u, p, dec = pit(st, T.select(feats), g)
        if y == a.y0:
            # GATE: the closed-form PIT == the share of the stepper's own draws below the truth (20 draws per tree)
            rng = np.random.default_rng(7)
            emp = np.mean([st._sample_G(T.select(feats), rng.uniform(size=len(g)), rng.uniform(size=len(g)))[0] < g
                           for _ in range(20)], axis=0)
            bins = np.minimum((u * 10).astype(int), 9)
            worst = max(abs(emp[bins == i].mean() - u[bins == i].mean()) for i in range(10))
            print(f"GATE closed-form vs sampled PIT: mean {np.nanmean(u):.4f} vs {emp.mean():.4f}, "
                  f"max |diff| within PIT deciles {worst:.4f}", flush=True)
        part = T.select("Cell", "Type", "Height", "G_y", "G_y1", "Age").with_columns(
            Year=pl.lit(y, pl.Int16), pit=pl.Series(u), p_neg=pl.Series(p), pool_dec=pl.Series(dec))
        if hasattr(st, "gq"):  # sharpness: mean pinball of log|G| over the levels, this model vs the old pools
            pn, po = st.gq.pinball_pair(st, T.select(feats), g)
            part = part.with_columns(pb_new=pl.Series(pn), pb_old=pl.Series(po))
        parts.append(part)
        print(f"year {y}: {T.height} trees, share PIT<0.5 {np.nanmean(u < 0.5):.3f}", flush=True)
    D = pl.concat(parts)
    qs = D["G_y"].cast(pl.Float64).quantile
    edges = [qs(i / 10) for i in range(1, 10)]
    D = D.with_columns(
        hcls=pl.when(pl.col("Height") < 15).then(pl.lit("lt15")).otherwise(pl.lit("ge15")),
        gy_dec=pl.col("G_y").cast(pl.Float64).cut(edges, labels=[f"d{i}" for i in range(10)]).cast(pl.Utf8),
        win=((pl.col("Year") - 1985) // 10 * 10 + 1985).cast(pl.Int16))
    out = os.path.join(XDE, "shared", "eval", f"gpit_{a.tag}")
    D.write_parquet(out + ".parquet")
    S = pl.concat([summ(D, ["win", "hcls"]).with_columns(group=pl.lit("all"), level=pl.lit("all")),
                   *[summ(D, ["win", "hcls", g]).rename({g: "level"}).with_columns(
                       group=pl.lit(g), level=pl.col("level").cast(pl.Utf8))
                     for g in ("gy_dec", "Type", "pool_dec", "Year")]], how="diagonal_relaxed")
    S.write_csv(out + "_summary.csv")
    pl.Config.set_tbl_rows(200)
    pl.Config.set_tbl_cols(30)
    pl.Config.set_tbl_width_chars(260)
    cols = ["group", "level", "n", "lt50", "lt10", "gt90", "mid", "mean"] + [c for c in ("pb_new", "pb_old")
                                                                            if c in S.columns]
    for w in (1985, 1995):
        print(f"== lt15 window {w}")
        print(S.filter((pl.col("hcls") == "lt15") & (pl.col("win") == w) & (pl.col("group") != "Year"))
              .select(cols).with_columns(pl.col(pl.Float64).round(3)))
    print("== lt15 by year")
    print(S.filter((pl.col("hcls") == "lt15") & (pl.col("group") == "Year")).select(cols)
          .with_columns(pl.col(pl.Float64).round(3)))
    print("wrote", out + "*")


if __name__ == "__main__":
    main()
