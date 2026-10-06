"""explore_de_gsign_info.py — LINE X, Germany emulator: how much of the original's YEAR-TO-YEAR negative-growth share
is predictable from the weather, and does monthly resolution add to the annual features the heads use?
(pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "WEATHER-INFORMATION CEILING of the yearly negative-growth share")

The shipped sign head reproduces the Germany-wide yearly share of trees with a negative-growth year at corr ~0.78 on
weather years it never trained on (0.98 on trained ones). This probe separates "the information is not in the
weather" from "the heads' annual features do not carry it":
  agg      per clean member, per (Cell, Year y): trees living at y and printed at y1 (Type <= 6, fate_y1 < 2):
           n, neg = P(c_y1 >= 1), start = P(c_y1 = 1 | c_y = 0), cont1 = P(c_y1 = 2 | c_y = 1), the counter pools at y
           -> shared/eval/gsign_info_agg.parquet
  ceiling  the two spin-up seeds of one (GCM, scenario) share every weather year: corr of their yearly shares is the
           weather-explainable fraction (I0)
  fit      cell-year LightGBM regressions, out-of-year cross-fit on the training members, sets
           0 = controls only (state at y + climatology), A = 0 + the heads' annual weather anomalies,
           B = A + monthly anomalies of y1 (Jan-Dec) and y (Jul-Dec); predicted on unseen weather (I1, I2)
Usage:  python explore_de_gsign_info.py agg|ceiling|fit|all
Writes shared/eval/gsign_info_{agg.parquet,ceiling.csv,fit.csv,fit_yearly.csv}
"""

from __future__ import annotations

import glob
import json
import os
import sys
import time
import zlib

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_sh_trans as tr  # noqa: E402
import explore_de_tab_features as F  # noqa: E402

XDE = tr.XDE
EVAL = os.path.join(XDE, "shared", "eval")
AGG = os.path.join(EVAL, "gsign_info_agg.parquet")
RUN200 = os.path.join(XDE, "runs", "_probe2_g2hsgqs_mpi2", "tabAL", "MPI-ESM1-2-HR_s2_1985-2044_ssp370_actual_r1")
MON_V = ["temp", "prec", "swdown", "lwdown", "humid"]
MON_Y1 = [f"{v}_m{m:02d}" for v in MON_V for m in range(1, 13)]
MON_Y = [f"{v}_m{m:02d}" for v in MON_V for m in range(7, 13)]
TARGETS = ["neg", "start", "cont1"]
NGRP = 5


def cells200() -> list[int]:
    out = []
    for f in sorted(glob.glob(os.path.join(RUN200, "meta_*.json"))):
        out += json.load(open(f))["cells"]
    assert len(out) == 200, len(out)
    return sorted(out)


def clean_members() -> list[str]:
    m = pl.read_parquet(os.path.join(tr.REG, "members.parquet"))
    return m.filter(~pl.col("excluded"))["member"].to_list()


def stage_agg():
    t0 = time.time()
    parts = []
    for mem in clean_members():
        fs = sorted(glob.glob(os.path.join(tr.XDE, "shared", "trans", "dev", mem, "cb=dev", "y*.parquet")))
        if not fs:
            print("no trans for", mem)
            continue
        c0, c1 = pl.col("c_y"), pl.col("c_y1")
        lf = (pl.concat([pl.scan_parquet(f).select("member", "gcm", "traj", "seed", "Year", "Cell", "Type", "Height",
                                                   "c_y", "c_y1", "fate_y1") for f in fs])
              .filter((pl.col("Type") <= 6) & (pl.col("fate_y1") < 2)))
        d = (lf.group_by("member", "gcm", "traj", "seed", "Cell", "Year")
             .agg(n=pl.len(), n0=(c0 == 0).sum(), n1=(c0 == 1).sum(),
                  neg=(c1 >= 1).cast(pl.Float64).mean(),
                  neg_lt10=(c1 >= 1).filter(pl.col("Height") < 10).cast(pl.Float64).mean(),
                  start=(c1 == 1).filter(c0 == 0).cast(pl.Float64).mean(),
                  cont1=(c1 == 2).filter(c0 == 1).cast(pl.Float64).mean(),
                  neg_y=(c0 >= 1).cast(pl.Float64).mean(),
                  **{f"pool{k}": (c0 == k).cast(pl.Float64).mean() for k in range(1, 5)},
                  h_mean=pl.col("Height").cast(pl.Float64).mean(),
                  lt10=(pl.col("Height") < 10).cast(pl.Float64).mean(),
                  **{f"t{k}": (pl.col("Type") == k).cast(pl.Float64).mean() for k in range(7)})
             .collect(engine="streaming"))
        assert d.select("Cell", "Year").n_unique() == d.height, f"duplicate keys in {mem}"
        parts.append(d)
        print(f"{mem}: {d.height} cell-years, {d['n'].sum()} trees  ({time.time() - t0:.0f}s)", flush=True)
    A = pl.concat(parts, how="vertical_relaxed")
    A.write_parquet(AGG)
    print("wrote", AGG, A.height)


def yearly(df: pl.DataFrame, col: str, by=("gcm", "traj", "seed", "Year")) -> pl.DataFrame:
    w = pl.col("n").cast(pl.Float64)
    return df.group_by(*by).agg(((pl.col(col) * w).sum() / w.filter(pl.col(col).is_not_null()).sum()).alias(col))


def stage_ceiling():
    A = pl.read_parquet(AGG)
    c2 = cells200()
    rows = []
    for cs_name, cs in (("200", c2), ("907", None)):
        D = A if cs is None else A.filter(pl.col("Cell").is_in(cs))
        for t in TARGETS + ["neg_lt10"]:
            Y = yearly(D.filter(pl.col(t).is_not_null()), t)
            for (g, traj), grp in Y.group_by("gcm", "traj"):
                p = grp.pivot(on="seed", index="Year", values=t).drop_nulls()
                if p.width < 3 or p.height < 10:
                    continue
                a, b = p["1"].to_numpy(), p["2"].to_numpy()
                r = float(np.corrcoef(a, b)[0, 1])
                rows.append(dict(cells=cs_name, target=t, gcm=g, traj=traj, n_years=p.height, r_ss=r,
                                 ceiling=float(np.sqrt(max(r, 0))), sd1=float(a.std()), sd2=float(b.std()),
                                 mean1=float(a.mean()), mean2=float(b.mean())))
            # within-cell interannual anomalies, seed vs seed, cell-year level
            if t == "neg":
                Dd = D.with_columns((pl.col(t) - pl.col(t).mean().over("member", "Cell")).alias("an"))
                p = Dd.pivot(on="seed", index=["gcm", "traj", "Cell", "Year"], values="an").drop_nulls()
                for (g, traj), grp in p.group_by("gcm", "traj"):
                    r = float(np.corrcoef(grp["1"].to_numpy(), grp["2"].to_numpy())[0, 1])
                    rows.append(dict(cells=cs_name, target="neg_cellyear_anom", gcm=g, traj=traj,
                                     n_years=grp.height, r_ss=r, ceiling=float(np.sqrt(max(r, 0)))))
    R = pl.DataFrame(rows).sort("cells", "target", "gcm", "traj")
    out = os.path.join(EVAL, "gsign_info_ceiling.csv")
    R.write_csv(out)
    pl.Config.set_tbl_rows(200)
    pl.Config.set_tbl_cols(20)
    pl.Config.set_tbl_width_chars(200)
    print(R.with_columns(pl.col(pl.Float64).round(4)))
    print("wrote", out)


def features(A: pl.DataFrame) -> tuple[pl.DataFrame, dict[str, list[str]]]:
    ann = [f"anom_{f}" for f in F.CLIM_F] + [f"anom_tstress_pft{k}" for k in range(4)]
    cols = sorted(set(ann + [f"anom_{f}" for f in F.TR20] + F.ABS_Y1 + MON_Y1))
    X = tr.join_climate(A.with_columns(pl.col("Cell").cast(pl.Int16), pl.col("Year").cast(pl.Int16),
                                       pl.col("seed").cast(pl.Int8)), cols=cols, years=("y", "y1"), ext=True)
    c85 = pl.read_parquet(os.path.join(XDE, "shared", "climate", "clim8514.parquet"))
    c85 = c85.select("gcm", pl.col("Cell").cast(pl.Int16), *[pl.col(f).alias(f"c85_{f}") for f in F.C85_F],
                     *[pl.col(m).alias(f"c85m_{m}") for m in MON_Y1])
    X = X.join(c85, on=["gcm", "Cell"], how="left")
    X = X.with_columns(*[(pl.col(f"{m}_y1") - pl.col(f"c85m_{m}")).alias(f"ma_{m}_y1") for m in MON_Y1],
                       *[(pl.col(f"{m}_y") - pl.col(f"c85m_{m}")).alias(f"ma_{m}_y") for m in MON_Y])
    state = ["neg_y", "pool1", "pool2", "pool3", "pool4", "h_mean", "lt10"] + [f"t{k}" for k in range(7)] + [
        "log_n"]
    X = X.with_columns(log_n=pl.col("n").cast(pl.Float64).log())
    s0 = state + [f"c85_{f}" for f in F.C85_F]
    sA = s0 + [f"{c}_{s}" for c in ann for s in ("y", "y1")] + [f"anom_{f}_y1" for f in F.TR20] + [
        f"{f}_y1" for f in F.ABS_Y1]
    sB = sA + [f"ma_{m}_y1" for m in MON_Y1] + [f"ma_{m}_y" for m in MON_Y]
    return X, {"0": s0, "A": sA, "B": sB}


def ycorr(D: pl.DataFrame, t: str, p: str, wcol: str = "n") -> dict:
    w = pl.col(wcol).cast(pl.Float64)
    Y = (D.filter(pl.col(t).is_not_null()).group_by("Year")
         .agg(((pl.col(t) * w).sum() / w.sum()).alias("o"), ((pl.col(p) * w).sum() / w.sum()).alias("e"))
         .sort("Year"))
    o, e = Y["o"].to_numpy(), Y["e"].to_numpy()
    r = float(np.corrcoef(o, e)[0, 1])
    slope = float(np.cov(o, e)[0, 1] / o.var(ddof=1))
    return dict(n_years=len(o), corr=r, slope=slope, mean_o=float(o.mean()), mean_e=float(e.mean()))


def stage_fit():
    import lightgbm as lgb

    t0 = time.time()
    A = pl.read_parquet(AGG)
    X, sets = features(A)
    X = X.with_columns(wkey=pl.concat_str([pl.col("clim_scen_y1"), pl.col("clim_year_y1").cast(pl.Utf8)]))
    X = X.with_columns(grp=pl.col("wkey").map_elements(lambda s: zlib.crc32(s.encode()) % NGRP,
                                                       return_dtype=pl.Int64))
    is_train = (pl.col("gcm") == "MPI-ESM1-2-HR") & (pl.col("seed") == 1) & pl.col("traj").is_in(
        ["Historical", "ssp126", "ssp370"])
    TR = X.filter(is_train)
    print(f"train cell-years {TR.height}, weather years {TR['wkey'].n_unique()}  ({time.time() - t0:.0f}s)", flush=True)
    P = dict(objective="regression", learning_rate=0.03, num_leaves=31, min_data_in_leaf=100, feature_fraction=0.7,
             bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1, num_threads=int(os.environ.get(
                 "OMP_NUM_THREADS", "8")), seed=7)
    c2 = cells200()
    res = []
    preds = {}
    for t in TARGETS:
        wcol = {"neg": "n", "start": "n0", "cont1": "n1"}[t]
        T = TR.filter(pl.col(t).is_not_null() & (pl.col(wcol) > 0))
        y, w, g = T[t].to_numpy(), T[wcol].to_numpy().astype(float), T["grp"].to_numpy()
        for sname, cols in sets.items():
            Xt = T.select(cols).to_numpy().astype(np.float32)
            oof = np.full(len(y), np.nan)
            best = []
            for k in range(NGRP):
                te, es = g == k, g == (k + 1) % NGRP
                trn = ~(te | es)
                b = lgb.train(P, lgb.Dataset(Xt[trn], y[trn], weight=w[trn]), num_boost_round=3000,
                              valid_sets=[lgb.Dataset(Xt[es], y[es], weight=w[es])],
                              callbacks=[lgb.early_stopping(50, verbose=False)])
                best.append(b.best_iteration)
                oof[te] = b.predict(Xt[te], num_iteration=b.best_iteration)
            nfin = int(np.median(best))
            bf = lgb.train(P, lgb.Dataset(Xt, y, weight=w), num_boost_round=nfin)
            Tt = T.with_columns(pl.Series("p", oof))
            for cs_name, cs in (("200", c2), ("907", None)):
                D = Tt if cs is None else Tt.filter(pl.col("Cell").is_in(cs))
                for traj in ["Historical", "ssp126", "ssp370"]:
                    r = ycorr(D.filter(pl.col("traj") == traj), t, "p", wcol)
                    res.append(dict(target=t, set=sname, eval="train_OOF_year", gcm="MPI-ESM1-2-HR", seed=1,
                                    traj=traj, cells=cs_name, best_iter=nfin, **r))
            # unseen / held-out members
            H = X.filter(~is_train & pl.col(t).is_not_null() & (pl.col(wcol) > 0))
            ph = bf.predict(H.select(cols).to_numpy().astype(np.float32))
            H = H.with_columns(pl.Series("p", ph))
            preds[(t, sname)] = H.select("gcm", "traj", "seed", "Cell", "Year", "p")
            for (gcm, seed, traj), grp in H.group_by("gcm", "seed", "traj"):
                for cs_name, cs in (("200", c2), ("907", None)):
                    D = grp if cs is None else grp.filter(pl.col("Cell").is_in(cs))
                    for win, lo, hi in (("all", 0, 9999), ("2015-44", 2014, 2044)):
                        Dw = D.filter((pl.col("Year") >= lo) & (pl.col("Year") < hi))
                        if Dw["Year"].n_unique() < 10:
                            continue
                        r = ycorr(Dw, t, "p", wcol)
                        # within-cell interannual R2 (anomaly vs the cell's member mean)
                        an = Dw.with_columns((pl.col(t) - pl.col(t).mean().over("Cell")).alias("ao"),
                                             (pl.col("p") - pl.col("p").mean().over("Cell")).alias("ae"))
                        ao, ae, ww = an["ao"].to_numpy(), an["ae"].to_numpy(), an[wcol].to_numpy().astype(float)
                        r2 = 1 - np.sum(ww * (ao - ae) ** 2) / np.sum(ww * ao ** 2)
                        res.append(dict(target=t, set=sname, eval=f"heldout_{win}", gcm=gcm, seed=seed, traj=traj,
                                        cells=cs_name, best_iter=nfin, cellyear_anom_r2=float(r2), **r))
            print(f"{t} set {sname}: best iters {best} -> {nfin}  ({time.time() - t0:.0f}s)", flush=True)
    R = pl.DataFrame(res)
    out = os.path.join(EVAL, "gsign_info_fit.csv")
    R.write_csv(out)
    pl.Config.set_tbl_rows(400)
    pl.Config.set_tbl_cols(20)
    pl.Config.set_tbl_width_chars(220)
    show = R.filter(pl.col("cells") == "200").select("target", "set", "eval", "gcm", "seed", "traj", "n_years",
                                                     "corr", "slope", "cellyear_anom_r2", "mean_o", "mean_e")
    print(show.sort("target", "eval", "gcm", "seed", "traj", "set").with_columns(pl.col(pl.Float64).round(3)))
    print("wrote", out)


def main():
    st = sys.argv[1] if len(sys.argv) > 1 else "all"
    if st in ("agg", "all"):
        stage_agg()
    if st in ("ceiling", "all"):
        stage_ceiling()
    if st in ("fit", "all"):
        stage_fit()


if __name__ == "__main__":
    main()
