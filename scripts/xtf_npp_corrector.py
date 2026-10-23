#!/usr/bin/env python3
"""xtf_npp_corrector.py -- ADR 0370 (SEPARATE EXPERIMENT, not for the paper): a yearly correction of the daily
model's annual NPP and GPP, aimed at the years the tree deaths depend on.

  python scripts/xtf_npp_corrector.py <src> <tag>        src = emu (the deployed networks, carbon.parquet) or a tag
                                                         of carbon_<tag>.parquet (e.g. mep); writes
                                                         xtf/treemort/carbon_<tag>.parquet ({npp,gpp}_<tag>[_anom])

Per cell-year, LightGBM predicts (true - emulated) annual NPP and GPP from the emulated NPP, GPP, their departures,
last year's emulated NPP, the 25 yearly climate statistics of the year, the year before and the trailing 30 years
(clu_emu_maps.clim_cols), latitude and CO2. Trained on the HELD-OUT cells under the 8 training climate models (where
the daily networks are out of sample), both members; validation = every 5th of those cells. Applied to every row.
Only held-out cells x held-out climate models is out of sample for both the networks and this correction.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import clu_emu_maps as M  # noqa: E402
import xtf_tree_models as TM  # noqa: E402

DATA = TM.DATA
KEYS = ["seed", "gcm", "ssp", "Cell", "Year"]
LGB = dict(objective="regression", learning_rate=0.05, num_leaves=31, min_data_in_leaf=50, feature_fraction=0.8,
           bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1, num_threads=32, seed=370)  # fmt: skip


def anom(x, x0):
    """x (nc, 80) for 2021..2100 -> departures from the previous <= 5 years over the cell's mean |value|;
    the first year keeps the uncorrected departure x0[:, 0]."""
    out = np.empty_like(x)
    out[:, 0] = x0[:, 0]
    for j in range(1, x.shape[1]):
        out[:, j] = (x[:, j] - x[:, max(0, j - 5) : j].mean(1)) / np.maximum(np.abs(x).mean(1), 10.0)
    return out


def main(src, tag):
    import lightgbm as lgb

    base = pl.read_parquet(TM.CARBON_P).select(KEYS + ["npp_true", "gpp_true", "npp_true_anom"])
    if src == "emu":
        e = pl.read_parquet(TM.CARBON_P).select(KEYS + ["npp_emu", "gpp_emu", "npp_emu_anom", "gpp_emu_anom"])
    else:
        e = pl.read_parquet(f"{DATA}/carbon_{src}.parquet").rename(
            {f"{v}_{src}{a}": f"{v}_emu{a}" for v in ("npp", "gpp") for a in ("", "_anom")})  # fmt: skip
    d = base.join(e, on=KEYS).sort(KEYS)
    d = d.with_columns(pl.col("npp_emu").shift(1).over(["seed", "gcm", "ssp", "Cell"]).alias("npp_emu_prev"))
    clim = pl.concat([TM.climate(g, s).with_columns(pl.lit(g).alias("gcm"), pl.lit(s).alias("ssp"))
                      for g in M.GCMS for s in ("ssp126", "ssp370", "ssp585")], how="diagonal_relaxed")  # fmt: skip
    d = d.join(clim, on=["gcm", "ssp", "Cell", "Year"], how="left")
    ho = M.cells().select("Cell", "heldout")
    d = d.join(ho, on="Cell", how="left")
    feats = ["npp_emu", "gpp_emu", "npp_emu_anom", "gpp_emu_anom", "npp_emu_prev"] + TM.cell_cols()
    train_gcm = pl.col("gcm").is_in(TM.TRAIN_GCMS)
    hc = sorted(d.filter(pl.col("heldout"))["Cell"].unique().to_list())
    vc = hc[::5]
    fit = d.filter(pl.col("heldout") & train_gcm & ~pl.col("Cell").is_in(vc))
    val = d.filter(pl.col("heldout") & train_gcm & pl.col("Cell").is_in(vc))
    print(f"{src} -> {tag}: fit {fit.height:,} cell-years, validation {val.height:,}, {len(feats)} inputs", flush=True)
    X = d.select(feats).to_numpy()
    cor = {}
    for v in ("npp", "gpp"):
        y = lambda f, v=v: (f[f"{v}_true"] - f[f"{v}_emu"]).to_numpy()  # noqa: E731
        ds = lgb.Dataset(fit.select(feats).to_numpy(), y(fit))
        dv = lgb.Dataset(val.select(feats).to_numpy(), y(val), reference=ds)
        b = lgb.train(LGB, ds, 2000, valid_sets=[dv], callbacks=[lgb.early_stopping(100), lgb.log_evaluation(200)])
        cor[v] = d[f"{v}_emu"].to_numpy() + b.predict(X, num_iteration=b.best_iteration)
    out = d.select(KEYS).with_columns(pl.Series(f"npp_{tag}", cor["npp"]), pl.Series(f"gpp_{tag}", cor["gpp"]))
    parts = []
    for _, g in out.with_columns(d["npp_emu_anom"], d["gpp_emu_anom"]).group_by(["seed", "gcm", "ssp"]):
        g = g.sort("Cell", "Year")
        nc = g["Cell"].n_unique()
        cols = {}
        for v in ("npp", "gpp"):
            x = g[f"{v}_{tag}"].to_numpy().reshape(nc, 80)
            cols[f"{v}_{tag}_anom"] = anom(x, g[f"{v}_emu_anom"].to_numpy().reshape(nc, 80)).reshape(-1)
        parts.append(g.drop("npp_emu_anom", "gpp_emu_anom").with_columns(
            *[pl.Series(k, a.astype(np.float32)) for k, a in cols.items()]))  # fmt: skip
    out = pl.concat(parts).with_columns(pl.col(f"npp_{tag}", f"gpp_{tag}").cast(pl.Float32))
    out.write_parquet(f"{DATA}/carbon_{tag}.parquet")
    # departure correlation, decision group, all and extreme cell-years (top 10 % |true departure| per cell)
    chk = d.select(KEYS + ["npp_true_anom", "npp_emu_anom", "heldout"]).join(
        out.select(KEYS + [f"npp_{tag}_anom"]), on=KEYS).filter(
        pl.col("heldout") & pl.col("gcm").is_in(M.TEST_GCMS)).with_columns(
        (pl.col("npp_true_anom").abs() >= pl.col("npp_true_anom").abs().quantile(0.9)
         .over(["seed", "gcm", "ssp", "Cell"])).alias("ext"))  # fmt: skip
    for nm, f in (("all", pl.lit(True)), ("extreme years", pl.col("ext"))):
        x = chk.filter(f)
        r0 = np.corrcoef(x["npp_true_anom"], x["npp_emu_anom"])[0, 1]
        r1 = np.corrcoef(x["npp_true_anom"], x[f"npp_{tag}_anom"])[0, 1]
        print(f"held-out cells x held-out models, {nm}: NPP departure r(true, {src}) {r0:.3f} -> corrected {r1:.3f}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
