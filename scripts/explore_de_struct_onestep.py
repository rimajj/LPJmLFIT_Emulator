"""explore_de_struct_onestep.py — LINE X, Germany emulator, STRUCT track: is the free run's
exit-below-5-m excess already there ONE STEP ahead, and is tree-growth persistence AR(1)-like?
(pre-registration /p/tmp/jamirp/X_de/_status/SD.md, H7 and H8)

H7  On the original model's own transition rows (SH3 table, teacher-forced states) of the chosen
    cells, trees below --hmax m at y: draw the STRUCT stepper's own growth step (StructHeads.sample
    with a stationary latent, --ndraw independent draws), agb_{y+1} = agb exp(dlagb), Height_{y+1}
    from the stepper's allometry (explore_de_struct_stepper.full_allometry). Per (window, Type
    group, height bin at y): sampled P(H_{y+1} < 5) and P(dlagb < 0) beside the original's realised
    share absent at y+1 (fate 2 = dropped below the print cut) among non-dead trees and its
    realised P(dlagb < 0) among present trees; also the same with the TRUE G (the size head alone).
H8  B1's out-of-fold latent scores (struct/heads/<split>/oof_z.parquet, same trees in successive
    years): lag-k autocorrelation of zG and zdlagb for k = 1, 2, 3, 5, 10 (pairs exactly k years
    apart), beside the AR(1) prediction rho^k with rho = the lag-1 value.

Usage:  python explore_de_struct_onestep.py [--gcm ACCESS-CM2] [--seed 1] [--ncells 200]
        [--hmax 7.5] [--ndraw 4]
Writes /p/tmp/jamirp/X_de/shared/eval/struct_onestep_exit_<gcm>_s<seed>.csv and
       /p/tmp/jamirp/X_de/shared/eval/struct_latent_lags.csv
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_sh_rules as rl  # noqa: E402
import explore_de_struct_heads as hd  # noqa: E402
import explore_de_struct_stepper as st  # noqa: E402

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
EVAL = os.path.join(XDE, "shared", "eval")


def tgroup(t: pl.Expr) -> pl.Expr:
    return pl.when(t == 3).then(pl.lit("beech3")).otherwise(pl.lit("other"))


def h7(a):
    mem = pl.read_parquet(os.path.join(XDE, "shared", "registry", "members.parquet")).filter(
        (pl.col("gcm") == a.gcm)
        & (pl.col("seed") == a.seed)
        & ~pl.col("excluded")
        & pl.col("scen").is_in(["Historical", "ssp370"])
    )
    cells = sorted(hd.folds()["Cell"].to_list())[: a.ncells]
    H = hd.StructHeads.load(a.split)
    allom = st.full_allometry(a.split)
    rng = np.random.default_rng(20261006)
    rows = []
    for m in mem["member"].to_list():
        df = hd.read_member_rows(
            m,
            pl.col("Cell").is_in(cells),
            (pl.col("Height") < a.hmax) & (pl.col("Type") <= 6),
        )
        if m.split("_")[1] == "Historical":
            df = df.filter(pl.col("Year") <= 2013)
        df = df.filter((pl.col("Year") <= 2043) & (pl.col("u_hash") < a.frac))
        print(m, df.height, flush=True)
        X = H.X(df)
        typ = df["Type"].to_numpy().astype(np.int64)
        scls = hd.size_class(df["Height"].to_numpy())
        agb = df["agb"].to_numpy().astype(np.float64)
        wd, sla = df["Wooddens"].to_numpy(), df["SLA"].to_numpy()
        pe, pn = np.zeros(df.height), np.zeros(df.height)
        for _ in range(a.ndraw):
            z = H.stationary(typ, scls, rng.standard_normal((df.height, len(hd.LATENT))))
            d = H.sample(X, z, typ, scls)
            h1 = rl.predict_height(agb * np.exp(d["dlagb"]), wd, sla, typ, allom)
            pe += (h1 < 5.0) / a.ndraw
            pn += (d["dlagb"] < 0) / a.ndraw
        # the size head at the TRUE G (present rows only), residual drawn from its quantile table
        gt = df["G_y1"].to_numpy().astype(np.float64)
        okg = np.isfinite(gt)
        sz = H.predict_size(X, np.where(okg, gt, 0.0))["dlagb"]
        u = rng.random(df.height)
        dl_tg = sz + H._qf("dlagb", typ, scls, u)
        h1t = rl.predict_height(agb * np.exp(dl_tg), wd, sla, typ, allom)
        df = df.with_columns(
            p_gneg=pl.Series(H.predict(X)["p_gneg"]),
            p_exit_draw=pl.Series(pe),
            p_dlneg_draw=pl.Series(pn),
            exit_trueG=pl.Series(np.where(okg, (h1t < 5.0).astype(float), np.nan)),
            win=pl.when(pl.col("Year") < 1995)
            .then(pl.lit("1985-94"))
            .when(pl.col("Year") < 2015)
            .then(pl.lit("1995-2014"))
            .otherwise(pl.lit("2015-43")),
            tg=tgroup(pl.col("Type")),
            hb=pl.col("Height").cut([5.5, 6.0, 7.5], labels=["5-5.5", "5.5-6", "6-7.5", "ge7.5"]),
        )
        alive = pl.col("fate_y1") != 1
        g = df.group_by("win", "tg", "hb").agg(
            n=pl.len(),
            n_alive=alive.sum(),
            orig_exit=((pl.col("fate_y1") == 2).sum() / alive.sum()),
            draw_exit=pl.col("p_exit_draw").filter(alive).mean(),
            trueG_exit=pl.col("exit_trueG").filter(pl.col("fate_y1") < 2).mean(),
            orig_dlneg=(pl.col("dlagb_t") < 0).filter(pl.col("fate_y1") < 2).mean(),
            draw_dlneg=pl.col("p_dlneg_draw").filter(alive).mean(),
            orig_Gneg=(pl.col("G_y1") < 0).filter(pl.col("fate_y1") < 2).mean(),
            draw_pGneg=pl.col("p_gneg").filter(alive).mean(),
        )
        rows.append(g.with_columns(member=pl.lit(m)))
    out = pl.concat(rows).sort("member", "win", "tg", "hb")
    p = os.path.join(EVAL, f"struct_onestep_exit_{a.gcm}_s{a.seed}.csv")
    out.write_csv(p)
    pl.Config.set_tbl_rows(100)
    pl.Config.set_tbl_cols(20)
    agg = (
        out.with_columns(
            w=pl.col("n_alive"),
        )
        .group_by("win", "tg", "hb")
        .agg(
            pl.col("n_alive").sum(),
            *[
                ((pl.col(c) * pl.col("w")).sum() / pl.col("w").sum()).alias(c)
                for c in (
                    "orig_exit",
                    "draw_exit",
                    "trueG_exit",
                    "orig_dlneg",
                    "draw_dlneg",
                    "orig_Gneg",
                    "draw_pGneg",
                )
            ],
        )
        .sort("win", "tg", "hb")
        .with_columns(pl.selectors.float().round(4))
    )
    print(agg)
    print("wrote", p)


def h8(a):
    Z = pl.read_parquet(os.path.join(XDE, "struct", "heads", a.split, "oof_z.parquet"))
    key = ["member", "Cell", "Patch", "Type", "ID"]
    rows = []
    for k in (1, 2, 3, 5, 10):
        j = Z.select(key + ["Year", "scls", "zG", "zdlagb"]).join(
            Z.select(key + [(pl.col("Year") - k).alias("Year"), "zG", "zdlagb"]),
            on=key + ["Year"],
            how="inner",
            suffix="_k",
        )
        for v in ("zG", "zdlagb"):
            jj = j.filter(pl.col(v).is_finite() & pl.col(f"{v}_k").is_finite())
            rows.append(
                {
                    "lag": k,
                    "var": v,
                    "scls": -1,
                    "n": jj.height,
                    "corr": float(np.corrcoef(jj[v], jj[f"{v}_k"])[0, 1]),
                }
            )
            for (s,), g in jj.group_by(["scls"]):
                if g.height > 1000:
                    rows.append(
                        {
                            "lag": k,
                            "var": v,
                            "scls": int(s),
                            "n": g.height,
                            "corr": float(np.corrcoef(g[v], g[f"{v}_k"])[0, 1]),
                        }
                    )
    L = pl.DataFrame(rows)
    r1 = L.filter(pl.col("lag") == 1).select("var", "scls", rho=pl.col("corr"))
    L = (
        L.join(r1, on=["var", "scls"], how="left")
        .with_columns(
            ar1_pred=pl.col("rho") ** pl.col("lag"),
        )
        .with_columns(excess=pl.col("corr") - pl.col("ar1_pred"))
        .sort("var", "scls", "lag")
    )
    p = os.path.join(EVAL, "struct_latent_lags.csv")
    L.write_csv(p)
    pl.Config.set_tbl_rows(100)
    print(L.with_columns(pl.selectors.float().round(3)))
    print("wrote", p)


def h10(a):
    """Sign head P(G<0) on the original's 5-6 m trees by age group (<= 15 / > 15) and type group,
    beside the realised share — the head alone (one LightGBM model, cheap)."""
    mem = pl.read_parquet(os.path.join(XDE, "shared", "registry", "members.parquet")).filter(
        (pl.col("gcm") == a.gcm)
        & (pl.col("seed") == a.seed)
        & ~pl.col("excluded")
        & pl.col("scen").is_in(["Historical", "ssp370"])
    )
    cells = sorted(hd.folds()["Cell"].to_list())[: a.ncells]
    H = hd.StructHeads.load(a.split)
    rows = []
    for m in mem["member"].to_list():
        df = hd.read_member_rows(
            m, pl.col("Cell").is_in(cells), (pl.col("Height") < 6.0) & (pl.col("Type") <= 6)
        )
        if "Historical" in m:
            df = df.filter(pl.col("Year") <= 2013)
        df = df.filter((pl.col("Year") <= 2043) & (pl.col("fate_y1") < 2))
        p = H._pred("gclf", H.X(df))
        df = df.with_columns(
            p_gneg=pl.Series(p),
            tg=pl.when(pl.col("Type") == 3)
            .then(pl.lit("beech"))
            .when(pl.col("Type").is_in([1, 2, 5]))
            .then(pl.lit("t125"))
            .otherwise(pl.lit("t046")),
            ag=pl.when(pl.col("Age") <= 15).then(pl.lit("le15")).otherwise(pl.lit("gt15")),
        )
        rows.append(
            df.group_by("tg", "ag")
            .agg(
                n=pl.len(),
                orig_Gneg=(pl.col("G_y1") < 0).mean(),
                head_pGneg=pl.col("p_gneg").mean(),
            )
            .with_columns(member=pl.lit(m))
        )
    out = pl.concat(rows).sort("member", "tg", "ag")
    p = os.path.join(EVAL, f"struct_onestep_sign_young_{a.gcm}_s{a.seed}.csv")
    out.write_csv(p)
    pl.Config.set_tbl_rows(40)
    print(out.with_columns(pl.selectors.float().round(4)))
    print("wrote", p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gcm", default="ACCESS-CM2")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--split", default="DEV-A")
    ap.add_argument("--ncells", type=int, default=200)
    ap.add_argument("--hmax", type=float, default=7.5)
    ap.add_argument("--ndraw", type=int, default=4)
    ap.add_argument("--frac", type=float, default=1.0, help="row subsample on u_hash (H7)")
    ap.add_argument("--what", default="h8,h7")
    a = ap.parse_args()
    if "h8" in a.what:
        h8(a)
    if "h7" in a.what:
        h7(a)
    if "h10" in a.what:
        h10(a)


if __name__ == "__main__":
    main()
