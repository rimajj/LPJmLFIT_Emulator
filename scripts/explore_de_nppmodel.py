"""explore_de_nppmodel.py — LINE X, Germany emulator: model the tree's NPP CHANGE (smooth) instead of the sign of its
growth, and get the negative-growth share through the C's own threshold. First test of the I7 design proposal.
(pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "I8 per-tree NPP model -> implied negative-growth share")

I7: a tree has a negative-growth year when its NPP falls below its loss L (turnover + reproduction + cmass_excess +
debt), and the year-to-year swing is in the NPP: P(npp_y1 < L_y) reproduces the true yearly share at corr 0.83-0.97.
Here: target lr = log(npp_y1 / npp_y) per tree (npp_y > 0), LightGBM on tree state at y + the cell's weather (the
gsign_info set B: annual + monthly anomalies), trained on MPI s1 Historical + ssp126 + ssp370 (dev cells, 3 % tree
sample) with a 5-group YEAR cross-fit for the stopping round and the out-of-year residual sd. Held out: MPI s1 ssp245
and ACCESS s1 (all legs), all trees of the 200 run cells. Implied P(neg) per tree = Phi((log(L_y/npp_y) - mu) / sd);
yearly share = its mean. Arms: W (with weather), N (no weather: the null). Reference: cf_gain (the true NPP, I7).
Usage:  python explore_de_nppmodel.py  -> shared/eval/nppmodel_yearly.csv
"""

from __future__ import annotations

import glob
import os
import sys
import time
import zlib

import numpy as np
import polars as pl
from scipy.stats import norm

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_bmdelta as bd  # noqa: E402
import explore_de_gsign_info as gi  # noqa: E402

TRAIN = ["MPI-ESM1-2-HR_Historical_s1_h1985", "MPI-ESM1-2-HR_ssp126_s1_w2015", "MPI-ESM1-2-HR_ssp370_s1_w2015"]
TEST = ["MPI-ESM1-2-HR_ssp245_s1_w2015", "ACCESS-CM2_Historical_s1_h1985", "ACCESS-CM2_ssp126_s1_w2015",
        "ACCESS-CM2_ssp245_s1_w2015", "ACCESS-CM2_ssp370_s1_w2015"]
FRAC = 0.03
TREE = ["Type", "SLA", "Wooddens", "D95max", "minwscal", "Longevity", "Height", "agb", "LAI", "fpc_ind", "D95", "Age",
        "npp", "transp", "wscal_mean", "height_rank", "fpc_above", "n_live", "sum_fpc", "sum_agb", "grass8_fpc",
        "grass8_LAI", "cell_stems_per_patch", "c_y"]


def load(mem: str, cells=None, frac=None) -> pl.DataFrame:
    fs = sorted(glob.glob(os.path.join(gi.XDE, "shared", "trans", "dev", mem, "cb=dev", "y*.parquet")))
    cols = list(dict.fromkeys(["gcm", "traj", "seed", "Year", "Cell", "u_hash", "fate_y1", "c_y1", "npp_y1", "LAI_y1",
                               "fpc_ind_y1", "G_y", "G_y1", "cenG_y", "cenG_y1", "is_new_y"] + TREE))
    lf = (pl.concat([pl.scan_parquet(f).select(cols) for f in fs])
          .filter((pl.col("Type") <= 6) & (pl.col("fate_y1") < 2) & (pl.col("cenG_y") == 0) & (pl.col("npp") > 0)
                  & (pl.col("LAI") > 0)))
    if cells is not None:
        lf = lf.filter(pl.col("Cell").is_in(cells))
    if frac is not None:
        lf = lf.filter(pl.col("u_hash") < frac)
    d = lf.collect()
    return d.with_columns(*bd.side(""), lr=(pl.col("npp_y1").cast(pl.Float64).clip(1e-6) / pl.col("npp")).log()
                          ).with_columns(thr=(pl.col("L") / (pl.col("npp").cast(pl.Float64) * bd.PATCHAREA)).log())


def main():
    import lightgbm as lgb

    t0 = time.time()
    A = pl.read_parquet(gi.AGG)
    X, sets = gi.features(A)
    wcols = [c for c in sets["B"] if c not in sets["0"]] + [c for c in sets["0"] if c.startswith("c85_")]
    W = X.select("gcm", "traj", pl.col("seed").cast(pl.Int8), pl.col("Cell").cast(pl.Int16),
                 pl.col("Year").cast(pl.Int16), "clim_scen_y1", "clim_year_y1", *wcols)
    join = ["gcm", "traj", "seed", "Cell", "Year"]
    TR = pl.concat([load(m, frac=FRAC) for m in TRAIN], how="vertical_relaxed").join(W, on=join, how="left")
    assert TR[wcols[0]].null_count() == 0
    TR = TR.with_columns(grp=pl.concat_str([pl.col("clim_scen_y1"), pl.col("clim_year_y1").cast(pl.Utf8)])
                         .map_elements(lambda s: zlib.crc32(s.encode()) % gi.NGRP, return_dtype=pl.Int64))
    print(f"train rows {TR.height} ({time.time() - t0:.0f}s)", flush=True)
    P = dict(objective="regression", learning_rate=0.05, num_leaves=127, min_data_in_leaf=200, feature_fraction=0.7,
             bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1,
             num_threads=int(os.environ.get("OMP_NUM_THREADS", "8")), seed=7)
    arms = {"W": TREE + wcols, "N": TREE + [c for c in wcols if c.startswith("c85_")]}
    y, g = TR["lr"].to_numpy(), TR["grp"].to_numpy()
    models = {}
    for an, cols in arms.items():
        Xt = TR.select(cols).to_numpy().astype(np.float32)
        oof = np.full(len(y), np.nan)
        best = []
        for k in range(gi.NGRP):
            te, es = g == k, g == (k + 1) % gi.NGRP
            trn = ~(te | es)
            b = lgb.train(P, lgb.Dataset(Xt[trn], y[trn], categorical_feature=[0]), num_boost_round=3000,
                          valid_sets=[lgb.Dataset(Xt[es], y[es], categorical_feature=[0])],
                          callbacks=[lgb.early_stopping(50, verbose=False)])
            best.append(b.best_iteration)
            oof[te] = b.predict(Xt[te], num_iteration=b.best_iteration)
        res = y - oof
        sd = float(np.std(res))
        bf = lgb.train(P, lgb.Dataset(Xt, y, categorical_feature=[0]), num_boost_round=int(np.median(best)))
        models[an] = (bf, cols, sd)
        print(f"arm {an}: best {best}, out-of-year residual sd {sd:.4f} (target sd {y.std():.4f}, "
              f"R2 {1 - res.var() / y.var():.3f})  ({time.time() - t0:.0f}s)", flush=True)
    c2 = gi.cells200()
    rows = []
    for mem in TEST:
        D = load(mem, cells=c2).join(W, on=join, how="left")
        assert D[wcols[0]].null_count() == 0
        D = D.with_columns(*bd.side("_y1"))
        out = D.select("Year", true=(pl.col("gain_y1") < pl.col("L_y1")).cast(pl.Float64),
                       cf_gain=(pl.col("gain_y1") < pl.col("L")).cast(pl.Float64))
        for an, (bf, cols, sd) in models.items():
            mu = bf.predict(D.select(cols).to_numpy().astype(np.float32))
            out = out.with_columns(pl.Series(f"p_{an}", norm.cdf((D["thr"].to_numpy() - mu) / sd)))
        Y = out.group_by("Year").agg(pl.all().mean()).sort("Year").with_columns(member=pl.lit(mem))
        rows.append(Y)
        msg = [f"{c} corr {np.corrcoef(Y['true'], Y[c])[0, 1]:.3f} slope "
               f"{np.cov(Y['true'], Y[c])[0, 1] / Y['true'].var():.3f} mean {Y[c].mean():.4f}"
               for c in ("cf_gain", "p_W", "p_N")]
        print(f"{mem} (true mean {Y['true'].mean():.4f}): " + " | ".join(msg), flush=True)
        if mem.startswith("ACCESS") or "ssp245" in mem:
            Yf = Y.filter(pl.col("Year") >= 2014)
            if Yf.height >= 10:
                print(f"   2015-44 only: p_W corr {np.corrcoef(Yf['true'], Yf['p_W'])[0, 1]:.3f}", flush=True)
    out = os.path.join(gi.EVAL, "nppmodel_yearly.csv")
    pl.concat(rows).write_csv(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
