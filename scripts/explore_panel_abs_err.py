#!/usr/bin/env python3
"""explore_panel_abs_err.py -- LINE X: the tree-count error of a saved panel arm in PLAIN UNITS (trees per patch, % per
cell, share of cells within 10 %, area totals signed), beside a second run of the original (m1, m2, m3 each vs m4),
split dense (>= 5 trees per patch) / sparse and by density class. Answers "how much is 1.35x a second run in numbers?".
Knobs: PRED_SET (default cnt), ARM (default A7rH), seed-1 predictions. Seconds on the login node.
RESULT 2026-10-10 (cnt / A7rH, ADR 0316 sec. 13): dense cells 7.1 % vs 5.8 % per cell (0.64 vs 0.52 trees per patch),
worst 10 % 23 % vs 17 %; dense-cell area total LOW in all 15 cases (-0.5 to -5.1 %; second run 0.5 %).
"""

import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_tolerance_measure as tm  # noqa: E402

PRED_SET, ARM = os.environ.get("PRED_SET", "cnt"), os.environ.get("ARM", "A7rH")
D = tm.D
cells = (
    pl.read_parquet(os.path.join(D, "cells.parquet"))
    .select("Cell", "lat")
    .with_columns(np.cos(np.deg2rad(pl.col("lat"))).alias("area"))
)
rows, tots = [], []
for g in tm.MODELS:
    p = pl.read_parquet(os.path.join(D, "eval", "preds_seen", "s1", f"{PRED_SET}_{g}_{ARM}.parquet"))
    for s in tm.SCENS:
        leg = f"{g}_{s}"
        T = tm.lev(tm.TRUTH, leg)
        R = {m: tm.lev(m, leg) for m in tm.POOL}
        if T is None or any(v is None for v in R.values()):
            continue
        X = p.filter(pl.col("leg") == leg).drop("leg")
        T1 = (
            T.filter(pl.col("n_per_patch") > 0)
            .select(
                "Cell",
                pl.col("n_per_patch").alias("T"),
                pl.col("n_per_patch").cut(tm.STRATA, labels=["<2", "2-5", "5-10", "10-20", ">20"]).alias("cls"),
            )
            .join(cells, on="Cell")
        )
        for name, frames in [("emulator", [X]), ("second run", [R[m] for m in tm.POOL])]:
            for F in frames:
                j = T1.join(F.select("Cell", pl.col("n_per_patch").alias("X")), on="Cell")
                rows.append(
                    j.with_columns(
                        pl.lit(name).alias("who"),
                        pl.lit(s).alias("scen"),
                        pl.lit(leg).alias("leg"),
                        (pl.col("X") - pl.col("T")).abs().alias("ae"),
                        ((pl.col("X") - pl.col("T")).abs() / pl.col("T")).alias("re"),
                    )
                )
                tots.append(
                    dict(
                        who=name,
                        scen=s,
                        leg=leg,
                        tot=float((j["area"] * j["X"]).sum() / (j["area"] * j["T"]).sum() - 1),
                        dense=float(
                            (j.filter(pl.col("T") >= 5)["area"] * j.filter(pl.col("T") >= 5)["X"]).sum()
                            / (j.filter(pl.col("T") >= 5)["area"] * j.filter(pl.col("T") >= 5)["T"]).sum()
                            - 1
                        ),
                    )
                )
a = pl.concat(rows)
a = a.with_columns(pl.when(pl.col("T") >= 5).then(pl.lit("dense >=5")).otherwise(pl.lit("sparse <5")).alias("grp"))
pl.Config.set_tbl_rows(40)
pl.Config.set_tbl_cols(12)
for sc in ["ssp370", None]:
    b = a if sc is None else a.filter(pl.col("scen") == sc)
    print("== scenario", sc or "all 15 cases", "(pooled over cases; second run = m1,m2,m3 each vs m4)")
    for by in ["grp", "cls"]:
        print(
            b.group_by("who", by)
            .agg(
                pl.col("T").median().round(2).alias("trees/patch (median)"),
                pl.col("ae").median().round(3).alias("abs err 50%"),
                pl.col("ae").quantile(0.9).round(3).alias("abs err 90%"),
                (pl.col("re").median() * 100).round(1).alias("% err 50%"),
                (pl.col("re").quantile(0.9) * 100).round(1).alias("% err 90%"),
                ((pl.col("re") <= 0.10).mean() * 100).round(1).alias("% cells within 10%"),
                (pl.len() / pl.col("leg").n_unique()).round(0).alias("cells/case"),
            )
            .sort(by, "who")
        )
    allb = b.group_by("who").agg(
        (pl.col("re").median() * 100).round(1).alias("% err 50%"),
        (pl.col("re").quantile(0.9) * 100).round(1).alias("% err 90%"),
        ((pl.col("re") <= 0.10).mean() * 100).round(1).alias("% within 10%"),
    )
    print(allb)
t = pl.DataFrame(tots)
print(
    t.group_by("who", "scen")
    .agg(
        (pl.col("tot").abs().median() * 100).round(2).alias("|total| % median"),
        (pl.col("tot").abs().max() * 100).round(2).alias("|total| % worst"),
        (pl.col("dense").abs().median() * 100).round(2).alias("|dense-cell total| % median"),
    )
    .sort("scen", "who")
)
print(
    t.filter(pl.col("who") == "emulator").select(
        "leg", (pl.col("tot") * 100).round(2).alias("total %"), (pl.col("dense") * 100).round(2).alias("dense total %")
    )
)
