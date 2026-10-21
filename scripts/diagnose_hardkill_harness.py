#!/usr/bin/env python3
"""diagnose_hardkill_harness.py -- why do 10-14 % of SURVIVING trees reconstruct below the sapling leaf carbon?
(ADR 0357 sec. 4: the harness of diagnose_hardkill_cause.py failed; this explains it before any number is read.)

Survivors by age: share with r < 1, r < 0.95, and the r centiles of those below 1. Recruits established AFTER the
mortality call this year start at the sapling leaf carbon (r ~ 1, below 1 by the ind writer's 6 significant digits);
older trees below 1 would mean the row's leaf area is not the one the mortality call saw. Then the near-threshold AUC
of diagnose_hardkill_cause.py recomputed on trees older than 1 year only. Three held-out legs; ~3 min on SLURM.
"""

import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import build_panel_bucket_stress as BK  # noqa: E402
import diagnose_hardkill_cause as H  # noqa: E402
import explore_panel_prep as PP  # noqa: E402

LEGS = ["gfdl-esm4_ssp370", "mpi-esm1-2-hr_ssp126", "ukesm1-0-ll_ssp585"]


def main():
    prm = H.pft_table()
    ev = pl.read_parquet(os.path.join(PP.OUT, "eval", "extreme_legacy_events.parquet")).filter(
        (pl.col("q") == "tree_count") & pl.col("shared")).select(
        pl.col("case").alias("leg"), pl.col("Cell").cast(pl.Int32), pl.col("year").cast(pl.Int16).alias("Year"))
    rows, near = [], []
    for leg in LEGS:
        cells = ev.filter(pl.col("leg") == leg)["Cell"].unique()
        lf = H.with_ratio(pl.scan_parquet(os.path.join(H.PANEL, "m4", leg, "ind.parquet")).filter(
            (pl.col("Type") <= 6) & pl.col("Cell").is_in(cells.implode())), prm)
        a = lf.filter(pl.col("cls") == "alive").with_columns(
            pl.col("Age").clip(upper_bound=5).cast(pl.Int32).alias("age"))
        rows.append(a.group_by("age").agg(
            pl.len().alias("n"), (pl.col("r") < 1.0).mean().alias("below1"),
            (pl.col("r") < 0.95).mean().alias("below095"),
            pl.col("r").filter(pl.col("r") < 1.0).quantile(0.1).alias("r_p10_below"),
            pl.col("r").filter(pl.col("r") < 1.0).median().alias("r_p50_below")).collect())
        nr = lf.filter((pl.col("cls") == "alive") & (pl.col("Age") > 1)).group_by("Cell", "Year").agg(
            pl.len().alias("n_alive"), *[(pl.col("r") < x).mean().alias(f"near{x}") for x in H.NEAR]).collect()
        near.append(nr.with_columns(pl.lit(leg).alias("leg")))
        print(f"{leg} done", flush=True)
    R = pl.concat(rows).group_by("age").agg(
        pl.col("n").sum(), *[(pl.col(c) * pl.col("n")).sum() / pl.col("n").sum() for c in ("below1", "below095")],
        pl.col("r_p10_below").median(), pl.col("r_p50_below").median()).sort("age")
    pl.Config.set_tbl_rows(20)
    print("\n== surviving trees by age (5 = 5 or more)")
    print(R)
    N = pl.concat(near).sort("leg", "Cell", "Year").with_columns(
        [pl.col(f"near{x}").shift(1).over("leg", "Cell").alias(f"prev{x}") for x in H.NEAR])
    J = N.join(ev.with_columns(pl.lit(True).alias("event")), on=["leg", "Cell", "Year"], how="left").with_columns(
        pl.col("event").fill_null(False)).filter(pl.col("Year").is_between(2025, 2090) & (pl.col("n_alive") >= 25))
    for x in H.NEAR:
        e = J.filter(pl.col("event"))[f"prev{x}"].drop_nulls().to_numpy()
        o = J.filter(~pl.col("event"))[f"prev{x}"].drop_nulls().to_numpy()
        print(f"trees older than 1 yr, last year's share with r < {x}: event median {np.median(e):.4f}, other "
              f"{np.median(o):.4f}, AUC {BK.auc(e, o):.3f} ({len(e)} events)")


if __name__ == "__main__":
    main()
