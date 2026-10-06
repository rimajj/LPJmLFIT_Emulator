"""explore_de_monthly_oracle.py — LINE X, Germany emulator: does the ORIGINAL's own monthly cell physics (NPP, GPP,
soil water, phenology water limiter, transpiration, PET) carry the year-to-year negative-growth share that weather
features miss? An ORACLE test: these are outputs of the model being emulated, never emulator inputs. A pass says
what an intermediate "cell productivity / soil water from daily weather" model would have to deliver.
(pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "I4 ORACLE monthly cell physics")

  extract  production monthly NetCDF (m<var>_.nc = Historical 1985-2014, m<var>_2044.nc = ssp 2015-2044) at the 907
           dev cells (Cell % 10 == 0, cellmap ilat/ilon) -> shared/eval/monthly_oracle_dev.parquet
           (gcm, seed, src (Historical|ssp), Cell, Year, <V>_m01..m12)
  fit      the explore_de_gsign_info set A / B regressions plus
             Cs = A + the oracle of y1 from the SAME seed's run (the target's own stand),
             Cx = A + the oracle of y1 from the OTHER seed's run (same weather, other stand),
             BCx = B + Cx; anomalies vs that run's own 1985-2014 cell-month mean. Same training (MPI s1 Hist + ssp126 +
           ssp370), year cross-fit, held-out scoring -> shared/eval/monthly_oracle_fit.csv
Usage:  python explore_de_monthly_oracle.py extract|fit|all
"""

from __future__ import annotations

import os
import sys
import time
import zlib

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_gsign_info as gi  # noqa: E402

XDE = gi.XDE
PROD = "/p/projects/waldspektrum/data/LPJmLFIT/productionruns_jamir"
OUTP = os.path.join(gi.EVAL, "monthly_oracle_dev.parquet")
VARS = {"mnpp": "NPP", "mgpp": "GPP", "mswc1": "SWC1", "mswc2": "SWC2", "mphen_water": "phen_water",
        "mtransp": "transp", "mpet": "PET"}
GCMS = ["MPI-ESM1-2-HR", "ACCESS-CM2"]
SSPS = ["ssp126", "ssp245", "ssp370"]


def stage_extract():
    import netCDF4

    cm = pl.read_parquet(os.path.join(XDE, "shared", "gap", "cellmap.parquet")).filter(pl.col("Cell") % 10 == 0)
    cells = cm["Cell"].to_numpy()
    iy, ix = cm["ilat"].to_numpy(), cm["ilon"].to_numpy()
    parts = []
    for gcm in GCMS:
        for seed in (1, 2):
            for src, suffix, y0 in [("Historical", "", 1985)] + [(s, "2044", 2015) for s in SSPS]:
                traj = "Historical" if src == "Historical" else src
                d = os.path.join(PROD, gcm, traj, f"random_seed_{seed}", "output")
                cols = {}
                for f, v in VARS.items():
                    p = os.path.join(d, f"{f}_{suffix}.nc")
                    with netCDF4.Dataset(p) as ds:
                        assert ds["time"].units.startswith(f"days since {y0}-1-1"), (p, ds["time"].units)
                        a = np.ma.filled(ds[v][:].astype(np.float32), np.nan)[:, iy, ix]
                    assert a.shape[0] == 360, (p, a.shape)
                    assert np.isfinite(a).all(), f"non-finite in {p}"
                    a = a.reshape(30, 12, len(cells))
                    for m in range(12):
                        cols[f"{v}_m{m + 1:02d}"] = a[:, m, :].reshape(-1)
                df = pl.DataFrame({"gcm": [gcm] * (30 * len(cells)), "seed": np.full(30 * len(cells), seed, np.int8),
                                   "src": [src] * (30 * len(cells)),
                                   "Cell": np.tile(cells, 30).astype(np.int16),
                                   "Year": np.repeat(np.arange(y0, y0 + 30), len(cells)).astype(np.int16), **cols})
                parts.append(df)
                print(gcm, seed, src, df.height, flush=True)
    Om = pl.concat(parts)
    assert Om.select("gcm", "seed", "src", "Cell", "Year").n_unique() == Om.height
    Om.write_parquet(OUTP)
    print("wrote", OUTP, Om.height)


def oracle_anoms() -> tuple[pl.DataFrame, list[str]]:
    Om = pl.read_parquet(OUTP)
    mc = [c for c in Om.columns if "_m" in c and c.split("_m")[-1].isdigit()]
    base = (Om.filter(pl.col("src") == "Historical").group_by("gcm", "seed", "Cell")
            .agg(*[pl.col(c).mean().alias(f"b_{c}") for c in mc]))
    Om = Om.join(base, on=["gcm", "seed", "Cell"]).with_columns(
        *[(pl.col(c) - pl.col(f"b_{c}")).alias(f"o_{c}") for c in mc]).select(
        "gcm", "seed", "src", "Cell", "Year", *[f"o_{c}" for c in mc])
    return Om, [f"o_{c}" for c in mc]


def stage_fit():
    import lightgbm as lgb

    t0 = time.time()
    A = pl.read_parquet(gi.AGG)
    X, sets = gi.features(A)
    Om, oc = oracle_anoms()
    # the oracle of print year y1: Historical file for y1 <= 2014, else the trajectory's ssp file
    X = X.with_columns(y1=(pl.col("Year") + 1).cast(pl.Int16),
                       src=pl.when(pl.col("Year") + 1 <= 2014).then(pl.lit("Historical")).otherwise(pl.col("traj")),
                       oseed=(3 - pl.col("seed")).cast(pl.Int8))
    Os = Om.rename({c: f"s{c}" for c in oc}).rename({"Year": "y1"})
    Ox = Om.rename({c: f"x{c}" for c in oc}).rename({"Year": "y1", "seed": "oseed"})
    X = (X.with_columns(pl.col("seed").cast(pl.Int8))
         .join(Os, on=["gcm", "seed", "src", "Cell", "y1"], how="left")
         .join(Ox, on=["gcm", "oseed", "src", "Cell", "y1"], how="left"))
    miss = X.select(pl.col(f"s{oc[0]}").is_null().sum(), pl.col(f"x{oc[0]}").is_null().sum()).row(0)
    assert miss == (0, 0), f"oracle join misses {miss}"
    sets = {"A": sets["A"], "B": sets["B"], "Cs": sets["A"] + [f"s{c}" for c in oc],
            "Cx": sets["A"] + [f"x{c}" for c in oc], "BCx": sets["B"] + [f"x{c}" for c in oc]}
    X = X.with_columns(grp=pl.concat_str([pl.col("clim_scen_y1"), pl.col("clim_year_y1").cast(pl.Utf8)])
                       .map_elements(lambda s: zlib.crc32(s.encode()) % gi.NGRP, return_dtype=pl.Int64))
    is_train = (pl.col("gcm") == "MPI-ESM1-2-HR") & (pl.col("seed") == 1) & pl.col("traj").is_in(
        ["Historical", "ssp126", "ssp370"])
    TR = X.filter(is_train)
    P = dict(objective="regression", learning_rate=0.03, num_leaves=31, min_data_in_leaf=100, feature_fraction=0.7,
             bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1,
             num_threads=int(os.environ.get("OMP_NUM_THREADS", "8")), seed=7)
    c2 = gi.cells200()
    res = []
    for t in gi.TARGETS:
        wcol = {"neg": "n", "start": "n0", "cont1": "n1"}[t]
        T = TR.filter(pl.col(t).is_not_null() & (pl.col(wcol) > 0))
        y, w, g = T[t].to_numpy(), T[wcol].to_numpy().astype(float), T["grp"].to_numpy()
        H = X.filter(~is_train & pl.col(t).is_not_null() & (pl.col(wcol) > 0))
        for sname, cols in sets.items():
            Xt = T.select(cols).to_numpy().astype(np.float32)
            best = []
            for k in range(gi.NGRP):
                te, es = g == k, g == (k + 1) % gi.NGRP
                trn = ~(te | es)
                b = lgb.train(P, lgb.Dataset(Xt[trn], y[trn], weight=w[trn]), num_boost_round=3000,
                              valid_sets=[lgb.Dataset(Xt[es], y[es], weight=w[es])],
                              callbacks=[lgb.early_stopping(50, verbose=False)])
                best.append(b.best_iteration)
            nfin = int(np.median(best))
            bf = lgb.train(P, lgb.Dataset(Xt, y, weight=w), num_boost_round=nfin)
            Hp = H.with_columns(pl.Series("p", bf.predict(H.select(cols).to_numpy().astype(np.float32))))
            for (gcm, seed, traj), grp in Hp.group_by("gcm", "seed", "traj"):
                D = grp.filter(pl.col("Cell").is_in(c2))
                r = gi.ycorr(D, t, "p", wcol)
                an = D.with_columns((pl.col(t) - pl.col(t).mean().over("Cell")).alias("ao"),
                                    (pl.col("p") - pl.col("p").mean().over("Cell")).alias("ae"))
                ao, ae, ww = an["ao"].to_numpy(), an["ae"].to_numpy(), an[wcol].to_numpy().astype(float)
                r2 = 1 - np.sum(ww * (ao - ae) ** 2) / np.sum(ww * ao ** 2)
                res.append(dict(target=t, set=sname, gcm=gcm, seed=seed, traj=traj, best_iter=nfin,
                                cellyear_anom_r2=float(r2), **r))
            print(f"{t} {sname}: {best} -> {nfin}  ({time.time() - t0:.0f}s)", flush=True)
    R = pl.DataFrame(res)
    out = os.path.join(gi.EVAL, "monthly_oracle_fit.csv")
    R.write_csv(out)
    pl.Config.set_tbl_rows(200)
    pl.Config.set_tbl_cols(20)
    pl.Config.set_tbl_width_chars(220)
    for t in gi.TARGETS:
        S = (R.filter((pl.col("target") == t) & (pl.col("seed") == 1))
             .with_columns(k=pl.concat_str([pl.col("gcm").str.slice(0, 3), pl.lit("_"), pl.col("traj")]))
             .pivot(on="set", index="k", values=["corr", "slope"]).sort("k"))
        print(t)
        print(S.with_columns(pl.col(pl.Float64).round(3)))
    print("wrote", out)


def main():
    st = sys.argv[1] if len(sys.argv) > 1 else "all"
    if st in ("extract", "all"):
        stage_extract()
    if st in ("fit", "all"):
        stage_fit()


if __name__ == "__main__":
    main()
