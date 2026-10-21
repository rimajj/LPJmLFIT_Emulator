#!/usr/bin/env python3
"""diagnose_dieoff_flux_oracle.py -- does the YEAR'S CARBON CRASH single out the original's die-off years? (ADR 0357)

ADR 0357: the die-offs are the leaf-carbon hard kill (a drought year's carbon balance drops trees' leaf carbon from well
above the sapling's to ~0.6 of it), and last year's nearness to the threshold barely predicts them (AUC ~0.55). So the
decisive quantity should be how much the year's carbon balance crashes. This scores, against ADR 0350's shared
tree-count events of the unseen run m4, how well each of the original's OWN yearly totals separates the event years
from the same cells' other years (AUC; z-anomaly against the cell's centred 21-year running mean and sd): NPP, GPP,
transpiration, mean top-metre soil water (f2 daily arrays, run m4), beside the daily bucket's actual/potential
evaporation (ADR 0355). These are ORACLE numbers (the original's own fluxes); the emulator's daily networks predict
NPP / GPP / transpiration / soil water, so a high AUC here says which emulated quantity to feed the departure model.
Legs: the f2 legs whose m4 run IS the panel run the events come from (mpi-esm1-2-hr x 3, ukesm1-0-ll_ssp370) and,
reported separately, the `_daily` re-runs of the other three models (their trajectories may differ from the panel's).
~5 min on SLURM.
"""

import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import build_panel_bucket_stress as BK  # noqa: E402
import explore_panel_prep as PP  # noqa: E402

F2 = BK.F2
EXACT = {"mpi-esm1-2-hr_ssp126": "mpi-esm1-2-hr_ssp126", "mpi-esm1-2-hr_ssp370": "mpi-esm1-2-hr_ssp370",
         "mpi-esm1-2-hr_ssp585": "mpi-esm1-2-hr_ssp585", "ukesm1-0-ll_ssp370": "ukesm1-0-ll_ssp370"}
RERUN = {f"{g}_{s}": f"{g}_{s}_daily" for g in ("gfdl-esm4", "ipsl-cm6a-lr", "mri-esm2-0")
         for s in ("ssp126", "ssp370", "ssp585")}
VARS = {"npp": 8, "gpp": 9, "transp": 1, "rootmoist": 6}
SIGN = {"npp": -1, "gpp": -1, "transp": -1, "rootmoist": -1, "bk_aetpet": -1}


def zcentred(a: np.ndarray, w: int = 21) -> np.ndarray:
    """(ncell, nyears) -> z against the centred w-year running mean / sd (edges use the available years)."""
    n = a.shape[1]
    z = np.zeros_like(a)
    for j in range(n):
        lo, hi = max(0, j - w // 2), min(n, j + w // 2 + 1)
        win = np.concatenate([a[:, lo:j], a[:, j + 1:hi]], axis=1)
        mu, sd = win.mean(1), win.std(1)
        z[:, j] = np.where(sd > 0, (a[:, j] - mu) / np.where(sd > 0, sd, 1.0), 0.0)
    return z


def leg_table(leg: str, f2leg: str) -> pl.DataFrame:
    fc = pl.read_parquet(os.path.join(F2, "cells.parquet"))["Cell"].to_numpy()
    d = np.load(os.path.join(F2, f"daily_m4_{f2leg}.npy"), mmap_mode="r")
    ny = d.shape[1] // 365
    cols = {}
    for nm, k in VARS.items():
        x = np.asarray(d[:, :, k], dtype=np.float64).reshape(len(fc), ny, 365)
        cols[nm] = zcentred(x.mean(2) if nm == "rootmoist" else x.sum(2))
    b = pl.read_parquet(os.path.join(BK.OUT, f"{leg}.parquet")).filter(pl.col("Year").is_between(2020, 2100))
    bw = b.sort("Cell", "Year").pivot(on="Year", index="Cell", values="bk_aetpet")
    pos = {int(c): i for i, c in enumerate(bw["Cell"].to_numpy())}
    bm = bw.drop("Cell").to_numpy()[[pos[int(c)] for c in fc]]
    cols["bk_aetpet"] = zcentred(bm.astype(np.float64))
    yrs = np.arange(2020, 2020 + ny)
    return pl.DataFrame({"Cell": np.repeat(fc.astype(np.int32), ny), "Year": np.tile(yrs.astype(np.int16), len(fc)),
                         **{k: v.ravel() for k, v in cols.items()}}).with_columns(pl.lit(leg).alias("leg"))


def main():
    ev = pl.read_parquet(os.path.join(PP.OUT, "eval", "extreme_legacy_events.parquet")).filter(
        (pl.col("q") == "tree_count") & pl.col("shared")).select(
        pl.col("case").alias("leg"), pl.col("Cell").cast(pl.Int32), pl.col("year").cast(pl.Int16).alias("Year"))
    for name, legs in (("exact panel runs", EXACT), ("_daily re-runs", RERUN)):
        T = pl.concat([leg_table(lg, f) for lg, f in legs.items()])
        evc = ev.filter(pl.col("leg").is_in(list(legs)))
        T = T.join(evc.select("leg", "Cell").unique(), on=["leg", "Cell"]).join(
            evc.with_columns(pl.lit(True).alias("event")), on=["leg", "Cell", "Year"], how="left").with_columns(
            pl.col("event").fill_null(False)).filter(pl.col("Year").is_between(2025, 2090))
        e, o = T.filter(pl.col("event")), T.filter(~pl.col("event"))
        print(f"\n== {name}: {e.height} event years, {o.height} other years of the same cells")
        for v in (*VARS, "bk_aetpet"):
            print(f"  {v:10s} z in event years median {np.median(e[v].to_numpy()):+.2f}, AUC "
                  f"{BK.auc(SIGN[v] * e[v].to_numpy(), SIGN[v] * o[v].to_numpy()):.3f}")


if __name__ == "__main__":
    main()
