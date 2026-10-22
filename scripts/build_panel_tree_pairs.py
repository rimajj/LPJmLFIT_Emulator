#!/usr/bin/env python3
"""build_panel_tree_pairs.py -- per-tree, year-to-year tables of the original for the PER-TREE MORTALITY MODEL
(ADR 0364) and the corrected yearly death tables.

At-risk population of year y (every leg, every run): trees of types 0-6 that were ALIVE and >= 5 m tall at the end
of year y-1 (the emulator's tree population, and what its virtual trees of y-1 represent) and have a row in year y.
(Cell, Patch, Type, ID) is a stable tree identity (ADR 0125; the
Type is needed -- two types in one patch can share an ID); a dying tree is emitted once more with isdead = 1.

Per tree at y (from the year-y row; mortality_tree_ind.c:120-146, fwriteoutput_ind.c):
  r      leaf carbon / the sapling's leaf carbon (ADR 0357: LAI, fpc_ind, SLA, the PFT's k; exact), lnr = ln r
  hz     min(1, mort_npp + mort_age + mort_water + mort_temp) -- the CHANCE death probability
  mort   the emitted death probability: = 1 when a HARD kill fired (leaf carbon below a sapling's, or five bad years
         in a row), else hz.  => the yearly2 `exp_dead` (sum of mort) INCLUDES the hard kills; deaths beyond it are
         fire and the other kills after the probability draw (ADR 0364 sec. 1).
  hard   isdead and mort >= 1 and hz < 1 (a hard kill that the chance hazards did not make certain)

Outputs per (run, leg):
  yearly3/m<k>_<leg>.parquet  per (Cell, Year): n_risk, n_dead, n_hard, n_hard_lr (hard and r < 1), sum_hz (over the
                              at-risk trees that were not hard-killed), sum_mort, n_vanish (alive >= 5 m at y-1, no
                              row at y). Rates: death_rate = n_dead / n_risk, hard_rate = n_hard / n_risk,
                              hazard_rate = sum_hz / n_risk, other_rate = (n_dead - sum_mort) / n_risk.
  tree_pairs/m<k>_<leg>.parquet  a fixed 0.5 % sample of the at-risk trees (hash of Cell, Patch, ID): the tree's
                              year y-1 state (Type, SLA, Wooddens, D95max, minwscal, Height, agb, Age, lnr) and its
                              year-y outcome (lnr, hz, isdead, hard, mort).
Gates (tree_pairs/_gate_m<k>_<leg>.json): n_vanish share; identity (age + 1); share of hard-killed trees with r < 1
  (reported: ~0.3 over all years for trees >= 5 m, 0.92 in die-off years; ADR 0364 sec. 2);
  n_dead vs yearly2's (different at-risk definitions; reported).
Usage: build_panel_tree_pairs.py build --part I --nparts N
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import diagnose_hardkill_cause as HK  # noqa: E402
import explore_panel_prep as PP  # noqa: E402

YEARLY3 = os.path.join(PP.OUT, "yearly3")
PAIRS = os.path.join(PP.OUT, "tree_pairs")
LEGS = ["hist", *PP.SLEGS, *PP.NEW_SLEGS]
SAMPLE = 200  # keep 1 in SAMPLE trees
# a tree's identity: (Cell, Patch, ID) is NOT unique -- two trees of different types, and rarely of the same type
# (37 of 685 k trees in one year), can share an ID in one patch. Type and SLA (immutable after establishment,
# bit-identical across years, ADR 0125) are added; tree-years still ambiguous on either side are dropped (counted)
KEY = ["Cell", "Patch", "ID", "Year", "Type_k", "SLA_k"]
STATE = ["Type", "SLA", "Wooddens", "D95max", "minwscal", "Height", "agb", "Age", "lnr"]


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def jobs() -> list[tuple[int, str]]:
    return [(m, lg) for m in PP.MEMBERS for lg in LEGS if PP.table_dir(m, lg) is not None]


def one(m: int, lg: str, prm: pl.DataFrame) -> dict:
    td = PP.table_dir(m, lg)
    y0, y1 = (2000, 2019) if lg == "hist" else (2020, 2100)
    blocks = list(range(105)) if lg == "hist" else PP.complete_blocks(m, lg)
    cl = PP.cells().filter(pl.col("block").is_in(blocks))["Cell"].to_list()
    hz = (pl.col("mort_npp") + pl.col("mort_age") + pl.col("mort_water") + pl.col("mort_temp")).clip(0.0, 1.0)
    lf = (pl.scan_parquet(os.path.join(td, "ind.parquet"))
          .filter(pl.col("Year").is_between(y0, y1) & pl.col("Cell").is_in(cl) & (pl.col("Type") <= 6))
          .with_columns(pl.col("Cell").cast(pl.Int32), pl.col("Year").cast(pl.Int32)))
    lf = HK.with_ratio(lf, prm).with_columns(pl.col("r").log().alias("lnr"), hz.alias("hz"))
    prev = (lf.filter((pl.col("isdead") == 0) & (pl.col("Height") >= 5.0))
            .select("Cell", "Patch", "ID", (pl.col("Year") + 1).alias("Year"), pl.col("Type").alias("Type_k"),
                    pl.col("SLA").alias("SLA_k"), *[pl.col(c).alias(f"{c}1") for c in STATE]))
    cur = lf.select("Cell", "Patch", "ID", "Year", pl.col("Type").alias("Type_k"), pl.col("SLA").alias("SLA_k"),
                    "isdead", "lnr", "hz", pl.col("mort").cast(pl.Float64), pl.col("Age").alias("Age_y"))
    prev = prev.filter(pl.len().over(KEY) == 1)
    n_amb = cur.filter(pl.len().over(KEY) > 1).select(pl.len()).collect().item()
    cur = cur.filter(pl.len().over(KEY) == 1)
    j = prev.join(cur, on=KEY, how="left").filter(pl.col("Year") <= y1)
    j = j.with_columns(
        pl.col("isdead").is_null().alias("vanish"),
        ((pl.col("isdead") == 1) & (pl.col("mort") >= 1.0) & (pl.col("hz") < 1.0)).fill_null(False).alias("hard"))
    J = j.collect(engine="streaming")
    assert J.select(KEY).n_unique() == J.height, "duplicate tree-years"
    m_ = J.filter(~pl.col("vanish"))
    age_ok = float(((m_["Age_y"] - m_["Age1"]) == 1).mean())  # identity check: age goes up by exactly 1
    R = J.filter(~pl.col("vanish"))
    y = R.group_by("Cell", "Year").agg(
        pl.len().alias("n_risk"), (pl.col("isdead") == 1).sum().alias("n_dead"), pl.col("hard").sum().alias("n_hard"),
        (pl.col("hard") & (pl.col("lnr") < 0)).sum().alias("n_hard_lr"),
        pl.when(~pl.col("hard")).then(pl.col("hz")).otherwise(0.0).sum().alias("sum_hz"),
        pl.col("mort").clip(0.0, 1.0).sum().alias("sum_mort"))
    v = J.group_by("Cell", "Year").agg(pl.col("vanish").sum().alias("n_vanish"))
    y = y.join(v, on=["Cell", "Year"], how="full", coalesce=True).with_columns(
        *[pl.col(c).fill_null(0) for c in ("n_risk", "n_dead", "n_hard", "n_hard_lr", "n_vanish")],
        *[pl.col(c).fill_null(0.0) for c in ("sum_hz", "sum_mort")]).sort("Cell", "Year")
    assert y.select("Cell", "Year").n_unique() == y.height
    y.write_parquet(os.path.join(YEARLY3, f"m{m}_{lg}.parquet"))
    key = (pl.struct("Cell", "Patch", "ID", "Type_k", "SLA_k").hash(seed=11) % SAMPLE) == 0
    s = R.filter(key).select("Cell", "Year", "Patch", "ID", *[f"{c}1" for c in STATE],
                             "lnr", "hz", "isdead", "hard", "mort")
    s.with_columns(pl.lit(m).cast(pl.Int8).alias("member"), pl.lit(lg).alias("leg")).write_parquet(
        os.path.join(PAIRS, f"m{m}_{lg}.parquet"))
    hk = R.filter(pl.col("hard"))
    gate = {"member": m, "leg": lg, "tree_years": J.height, "vanish_share": float(J["vanish"].mean()),
            "ambiguous_rows_dropped": int(n_amb), "age_plus_one_share": age_ok,
            "hard_share_of_deaths": float(R["hard"].sum() / max(1, (R["isdead"] == 1).sum())),
            "hard_r_below_1": float((hk["lnr"] < 0).mean()) if hk.height else None,
            "death_rate": float((R["isdead"] == 1).mean()), "sample_rows": s.height}
    f2 = os.path.join(PP.OUT, "yearly2", f"m{m}_{lg}.parquet")
    if os.path.exists(f2):
        d2 = pl.read_parquet(f2, columns=["Cell", "Year", "n_dead"]).join(y, on=["Cell", "Year"], suffix="_3")
        gate["n_dead_yearly2"], gate["n_dead_yearly3"] = int(d2["n_dead"].sum()), int(d2["n_dead_3"].sum())
    json.dump(gate, open(os.path.join(PAIRS, f"_gate_m{m}_{lg}.json"), "w"), indent=1)
    return gate


def stage_build(a) -> None:
    os.makedirs(YEARLY3, exist_ok=True)
    os.makedirs(PAIRS, exist_ok=True)
    prm = HK.pft_table()
    for i, (m, lg) in enumerate(jobs()):
        if i % a.nparts != a.part or os.path.exists(os.path.join(PAIRS, f"m{m}_{lg}.parquet")):
            continue
        t0 = time.time()
        g = one(m, lg, prm)
        log(f"m{m} {lg}: {g} ({time.time() - t0:.0f}s)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["build"])
    ap.add_argument("--part", type=int, default=0)
    ap.add_argument("--nparts", type=int, default=1)
    a = ap.parse_args()
    stage_build(a)
    log("=== DONE")


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
