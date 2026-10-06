"""explore_de_struct_stemloss.py — LINE X, Germany emulator, STRUCT track: where does the free
run lose its stems?

Read-only probe over a STRUCT free run on disk (or a counterfactual arm given as label@<run dir>)
and the original model's `ind` table for the same cells and years (pre-registration:
/p/tmp/jamirp/X_de/_status/SD.md, H0-H3, H5).

Per (source, year), over the chosen cells (stems = living printed trees, Type <= 6):
  stems_pp_<bin>   stems per patch by height bin (5-6, 6-7.5, 7.5-10, 10-15, 15-20, >= 20 m)
  flow terms       of the identity stems(y) - stems(y-1) = new_live - dead - exit (per patch):
                   dead = flagged dead at y among the living of y-1; exit = living at y-1, not
                   printed at y and not flagged dead (dropped below 5 m); new_live = living at y
                   whose key was not printed at y-1 (first appearances + re-entries); a recruit
                   flagged dead in its first year is in neither term
  exit_<bin>       exits by height at y-1, exit_type<k> by type; dead_<bin> by height at y-1
  dH_neg           share of living-to-living transitions with Height(y) < Height(y-1) - 0.01 m
  agb_stand_pp     sum agb of stems / patch; agb_q50_cellmed: per-cell median of stem agb, median
                   over cells
  pair_*           same-tree pairs: trees of the first-year roster living and printed in BOTH
                   runs at y (key Cell, Patch, Type, ID, SLA, Wooddens): median ln(agb_src /
                   agb_truth), median ln(H_src / H_truth)
Plus, on the original's stems: the residual ln H - ln Hhat(agb, Wooddens, SLA, Type) of the
stepper's own allometry (explore_de_struct_stepper.full_allometry) by height bin (H1); and on the
arm the same residual (exactly 0 for every tree stepped at least once by the base stepper).

Usage:  python explore_de_struct_stemloss.py [--arms struct_noacc] [--ncells 200] [--leg ssp370]
        [--tag _x]; an arm may be label@<run dir>
Writes /p/tmp/jamirp/X_de/shared/eval/struct_stemloss_<leg><tag>{,_pairs,_allom,_windows}.csv
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_struct_stepper as st  # noqa: E402

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
RUN = "ACCESS-CM2_s1_1985-2044_ssp126+ssp245+ssp370_actual_r1"
KEY = ["Cell", "Patch", "Type", "ID"]
PKEY = KEY + ["SLA", "Wooddens"]
COLS = ["Year", "Cell", "Patch", "Type", "ID", "isdead", "Height", "agb", "SLA", "Wooddens"]
HB = [6.0, 7.5, 10.0, 15.0, 20.0]
HBN = ["5-6", "6-7.5", "7.5-10", "10-15", "15-20", "ge20"]
NPATCH = 250


def hbin(e: pl.Expr) -> pl.Expr:
    return e.cut(HB, labels=HBN, left_closed=True).cast(pl.Utf8)


def arm_frame(arm: str, leg: str, cells: list[int] | None, ncells: int) -> pl.DataFrame:
    base = arm.split("@", 1)[1] if "@" in arm else os.path.join(XDE, "runs", arm, RUN)
    fs = []
    for d in sorted(glob.glob(os.path.join(base, "chunk_*"))):
        fs += sorted(glob.glob(os.path.join(d, "*_Historical.parquet"))) + sorted(
            glob.glob(os.path.join(d, f"*_{leg}.parquet"))
        )
    lf = pl.concat([pl.scan_parquet(f).select(COLS) for f in fs], how="vertical_relaxed")
    if cells is None:
        cells = sorted(lf.select(pl.col("Cell").unique()).collect()["Cell"].to_list())[:ncells]
    return lf.filter(pl.col("Cell").is_in(cells) & (pl.col("Type") <= 6)).collect(), cells


def truth_frame(cells, leg, gcm="ACCESS-CM2", seed=1, y0=1985, y1=2044) -> pl.DataFrame:
    m = pl.read_parquet(os.path.join(XDE, "shared", "registry", "members.parquet")).filter(
        (pl.col("gcm") == gcm)
        & (pl.col("seed") == seed)
        & ~pl.col("excluded")
        & pl.col("scen").is_in(["Historical", leg])
    )
    parts = []
    for r in m.iter_rows(named=True):
        lf = pl.scan_parquet(r["ind_dev_path"]).select(COLS)
        lf = (
            lf.filter(pl.col("Year") <= 2014)
            if r["scen"] == "Historical"
            else lf.filter(pl.col("Year") > 2014)
        )
        parts.append(lf)
    return (
        pl.concat(parts, how="vertical_relaxed")
        .filter(
            pl.col("Cell").is_in(cells) & (pl.col("Type") <= 6) & pl.col("Year").is_between(y0, y1)
        )
        .collect()
    )


def yearly(D: pl.DataFrame, src: str, npt: int) -> pl.DataFrame:
    years = sorted(D["Year"].unique().to_list())
    D = D.with_columns(hb=hbin(pl.col("Height")))
    out = []
    by_year = {y: g for (y,), g in D.group_by(["Year"])}
    for y in years:
        cur = by_year[y]
        live = cur.filter(pl.col("isdead") == 0)
        r = {"src": src, "Year": y, "stems_pp": live.height / npt}
        hc = live.group_by("hb").len()
        for b in HBN:
            v = hc.filter(pl.col("hb") == b)["len"]
            r[f"stems_pp_{b}"] = (int(v[0]) if len(v) else 0) / npt
        r["agb_stand_pp"] = float(live["agb"].sum()) / npt
        cm = live.group_by("Cell").agg(m=pl.col("agb").median())
        r["agb_q50_cellmed"] = float(cm["m"].median())
        if y > years[0]:
            prev = by_year[y - 1]
            lp = prev.filter(pl.col("isdead") == 0)
            dead = cur.filter(pl.col("isdead") == 1).join(
                lp.select(KEY + ["hb"]), on=KEY, how="inner"
            )
            ex = lp.join(cur.select(KEY), on=KEY, how="anti")
            newl = live.join(prev.select(KEY), on=KEY, how="anti")
            tt = lp.select(KEY + [pl.col("Height").alias("h0")]).join(
                live.select(KEY + [pl.col("Height").alias("h1")]), on=KEY, how="inner"
            )
            r.update(
                new_live_pp=newl.height / npt,
                dead_pp=dead.height / npt,
                exit_pp=ex.height / npt,
                dH_neg=float(((tt["h1"] - tt["h0"]) < -0.01).mean()) if tt.height else None,
                n_trans=tt.height,
            )
            for nm, F in (("exit", ex), ("dead", dead)):
                hcx = F.group_by("hb").len()
                for b in HBN:
                    v = hcx.filter(pl.col("hb") == b)["len"]
                    r[f"{nm}_{b}"] = (int(v[0]) if len(v) else 0) / npt
            tcx = ex.group_by("Type").len()
            for k in range(7):
                v = tcx.filter(pl.col("Type") == k)["len"]
                r[f"exit_type{k}"] = (int(v[0]) if len(v) else 0) / npt
            sc = lp.group_by("Type").len()
            for k in range(7):
                v = sc.filter(pl.col("Type") == k)["len"]
                r[f"stems_type{k}_prev"] = (int(v[0]) if len(v) else 0) / npt
        out.append(r)
    return pl.DataFrame(out, infer_schema_length=None)


def pairs(A: pl.DataFrame, T: pl.DataFrame, src: str) -> pl.DataFrame:
    y0 = int(T["Year"].min())
    init = T.filter((pl.col("Year") == y0) & (pl.col("isdead") == 0)).select(PKEY)
    a = (
        A.filter(pl.col("isdead") == 0)
        .join(init, on=PKEY, how="semi")
        .select(PKEY + ["Year", pl.col("agb").alias("a_e"), pl.col("Height").alias("h_e")])
    )
    t = (
        T.filter(pl.col("isdead") == 0)
        .join(init, on=PKEY, how="semi")
        .select(PKEY + ["Year", pl.col("agb").alias("a_t"), pl.col("Height").alias("h_t")])
    )
    j = a.join(t, on=PKEY + ["Year"], how="inner").with_columns(
        lr=(pl.col("a_e") / pl.col("a_t")).log(),
        lh=(pl.col("h_e") / pl.col("h_t")).log(),
        hb=hbin(pl.col("h_t")),
    )
    n_e = a.group_by("Year").len().rename({"len": "n_init_emu"})
    n_t = t.group_by("Year").len().rename({"len": "n_init_truth"})
    g = (
        j.group_by("Year")
        .agg(
            n_pair=pl.len(),
            lr_med=pl.col("lr").median(),
            lr_mean=pl.col("lr").mean(),
            lh_med=pl.col("lh").median(),
            lr_med_lt10=pl.col("lr").filter(pl.col("h_t") < 10).median(),
            lr_med_ge15=pl.col("lr").filter(pl.col("h_t") >= 15).median(),
        )
        .join(n_e, on="Year", how="left")
        .join(n_t, on="Year", how="left")
        .with_columns(src=pl.lit(src))
        .sort("Year")
    )
    return g


def cohort(A: pl.DataFrame, T: pl.DataFrame, src: str) -> pl.DataFrame:
    """Unconditioned spread: quantiles of ln agb of first-year-roster trees alive in THIS run at y
    (no pairing, no conditioning on the other run's outcome) and of all stems."""
    y0 = int(T["Year"].min())
    init = T.filter((pl.col("Year") == y0) & (pl.col("isdead") == 0)).select(PKEY)
    L = A.filter(pl.col("isdead") == 0).with_columns(la=pl.col("agb").log())
    ci = L.join(init, on=PKEY, how="semi")
    q = [0.1, 0.25, 0.5, 0.75, 0.9]
    a = ci.group_by("Year").agg(
        pl.len().alias("n_init"),
        *[pl.col("la").quantile(v).alias(f"init_q{int(v * 100)}") for v in q],
    )
    b = L.group_by("Year").agg(*[pl.col("la").quantile(v).alias(f"all_q{int(v * 100)}") for v in q])
    return a.join(b, on="Year").with_columns(src=pl.lit(src)).sort("Year")


def allom_resid(D: pl.DataFrame, src: str, coef: pl.DataFrame, years) -> pl.DataFrame:
    d = D.filter((pl.col("isdead") == 0) & pl.col("Year").is_in(years))
    hh = st.rl.predict_height(
        d["agb"].to_numpy(),
        d["Wooddens"].to_numpy(),
        d["SLA"].to_numpy(),
        d["Type"].to_numpy(),
        coef,
    )
    d = d.with_columns(
        res=pl.Series(np.log(d["Height"].to_numpy().astype(np.float64)) - np.log(hh)),
        hb=hbin(pl.col("Height")),
    )
    return (
        d.group_by("Year", "hb")
        .agg(
            n=pl.len(),
            res_mean=pl.col("res").mean(),
            res_med=pl.col("res").median(),
            res_sd=pl.col("res").std(),
            share_abs_gt_1e4=(pl.col("res").abs() > 1e-4).mean(),
        )
        .with_columns(src=pl.lit(src))
        .sort("Year", "hb")
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="struct_noacc")
    ap.add_argument("--ncells", type=int, default=200)
    ap.add_argument("--leg", default="ssp370")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    arms = a.arms.split(",")
    cells = None
    frames = {}
    for arm in arms:
        D, cells = arm_frame(arm, a.leg, cells, a.ncells)
        frames[arm.split("@")[0]] = D
        print(f"{arm}: {D.height} rows, {len(cells)} cells {cells[0]}..{cells[-1]}", flush=True)
    T = truth_frame(cells, a.leg)
    print(f"truth: {T.height} rows", flush=True)
    npt = len(cells) * NPATCH
    out = os.path.join(XDE, "shared", "eval", f"struct_stemloss_{a.leg}{a.tag}")
    Y = [yearly(T, "truth", npt)] + [yearly(D, k, npt) for k, D in frames.items()]
    Yd = pl.concat(Y, how="diagonal_relaxed")
    Yd.write_csv(out + ".csv")
    P = pl.concat([pairs(D, T, k) for k, D in frames.items()], how="diagonal_relaxed")
    P.write_csv(out + "_pairs.csv")
    C = pl.concat(
        [cohort(T, T, "truth")] + [cohort(D, T, k) for k, D in frames.items()],
        how="diagonal_relaxed",
    )
    C.write_csv(out + "_cohort.csv")
    coef = st.full_allometry("DEV-A")
    ys = [1985, 1986, 1990, 2000, 2014, 2030, 2044]
    Al = pl.concat(
        [allom_resid(T, "truth", coef, ys)]
        + [allom_resid(D, k, coef, ys) for k, D in frames.items()],
        how="diagonal_relaxed",
    )
    Al.write_csv(out + "_allom.csv")
    # windows
    W = (
        Yd.with_columns(
            win=pl.when(pl.col("Year") <= 1995)
            .then(pl.lit("1986-95"))
            .when(pl.col("Year") <= 2005)
            .then(pl.lit("1996-05"))
            .when(pl.col("Year") <= 2015)
            .then(pl.lit("2006-15"))
            .when(pl.col("Year") <= 2025)
            .then(pl.lit("2016-25"))
            .when(pl.col("Year") <= 2035)
            .then(pl.lit("2026-35"))
            .otherwise(pl.lit("2036-44"))
        )
        .filter(pl.col("Year") > 1985)
        .group_by("src", "win")
        .agg(pl.exclude("Year").mean())
        .sort("src", "win")
    )
    W.write_csv(out + "_windows.csv")
    pl.Config.set_tbl_cols(30)
    pl.Config.set_tbl_rows(60)
    pl.Config.set_fmt_float("full")
    show = [
        "src",
        "win",
        "stems_pp",
        "new_live_pp",
        "dead_pp",
        "exit_pp",
        "dH_neg",
        "agb_stand_pp",
        "agb_q50_cellmed",
    ]
    print(W.select(show).with_columns(pl.selectors.float().round(4)))
    print(
        W.select(["src", "win"] + [f"stems_pp_{b}" for b in HBN]).with_columns(
            pl.selectors.float().round(3)
        )
    )
    print(
        W.select(["src", "win"] + [f"exit_{b}" for b in HBN]).with_columns(
            pl.selectors.float().round(4)
        )
    )
    print(
        W.select(["src", "win"] + [f"dead_{b}" for b in HBN]).with_columns(
            pl.selectors.float().round(4)
        )
    )
    print(
        W.select(
            ["src", "win"]
            + [f"exit_type{k}" for k in range(7)]
            + [f"stems_type{k}_prev" for k in (3, 4)]
        ).with_columns(pl.selectors.float().round(4))
    )
    print(
        P.filter(
            pl.col("Year").is_in([1986, 1987, 1990, 1995, 2000, 2005, 2010, 2015, 2025, 2035, 2044])
        ).with_columns(pl.selectors.float().round(4))
    )
    print(
        Al.filter(pl.col("Year").is_in([1985, 1986, 2000, 2030])).with_columns(
            pl.selectors.float().round(4)
        )
    )
    print("wrote", out + "{,_pairs,_allom,_windows}.csv")


if __name__ == "__main__":
    main()
