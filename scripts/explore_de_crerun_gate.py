"""explore_de_crerun_gate.py — LINE X, Germany emulator: does a re-run of the original model (explore_de_crerun.py)
reproduce the PRODUCTION member's trees exactly, and what does it add below 5 m?

Gate (all must hold, or the re-run's trajectory is not the production one and its saplings cannot be paired with
the production rows):
  g1  every production `ind` row of the re-run's years and cell range occurs in the re-run (all 29 columns
      except the five mort_* columns, which the C leaves uninitialised for some trees, compared as float32),
      counted with multiplicity (the production table has duplicate keys)
  g2  every re-run row that is NOT a production row is a tree with printed Height <= 5 (the writer's cut is
      height > 5 m strictly; %g prints a 5.0000001 m tree as 5, so <= is the honest test of the printed value)
  g3  the mort_* columns of the matched rows: share identical (reported, not gated)
Reports per year: production rows, re-run rows, matched, unmatched-production, extra rows split by Height <= 5.

Usage:  python explore_de_crerun_gate.py --run <crerun dir> --gcm MPI-ESM1-2-HR --scen ssp370 --seed 2 --win w2015
Writes <run>/gate.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_convert as cv  # noqa: E402

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
MORT = ["mort_npp", "mort_age", "mort_water", "mort_temp", "mort"]


def read_rerun(run):
    f = os.path.join(run, "output", "ind.csv")
    head = open(f).readline()
    assert not re.match(r"^\s*\d", head), "expected a header line"
    return pl.read_csv(f, has_header=True, new_columns=cv.COLS, schema=cv.SCHEMA)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--gcm", required=True)
    ap.add_argument("--scen", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--win", required=True)
    a = ap.parse_args()
    R = read_rerun(a.run)
    years = sorted(R["Year"].unique().to_list())
    c0, c1 = int(R["Cell"].min()), int(R["Cell"].max())
    src = os.path.join(XDE, "ind", a.gcm, a.scen, f"s{a.seed}", a.win)
    P = (pl.scan_parquet(os.path.join(src, "cb=*", "*.parquet"))
         .filter(pl.col("Year").is_in(years) & pl.col("Cell").is_between(c0, c1)).collect())
    cols = [c for c in cv.COLS if c not in MORT]
    # multiplicity-aware match: number each row within its identical-value group on both sides
    Pn = P.with_columns(_k=pl.int_range(pl.len()).over(cols))
    Rn = R.with_columns(_k=pl.int_range(pl.len()).over(cols))
    on = [*cols, "_k"]
    M = Pn.join(Rn, on=on, how="inner", suffix="_r", nulls_equal=True)
    miss = Pn.join(Rn, on=on, how="anti", nulls_equal=True)
    extra = Rn.join(Pn, on=on, how="anti", nulls_equal=True)
    is_tree = pl.col("Type") <= 6
    out = {"run": a.run, "years": years, "cells": [c0, c1], "per_year": []}
    for y in years:
        e = extra.filter(pl.col("Year") == y)
        out["per_year"].append({
            "Year": int(y),
            "prod_rows": P.filter(pl.col("Year") == y).height,
            "rerun_rows": R.filter(pl.col("Year") == y).height,
            "matched": M.filter(pl.col("Year") == y).height,
            "prod_unmatched": miss.filter(pl.col("Year") == y).height,
            "extra_tree_le5": e.filter(is_tree & (pl.col("Height") <= 5.0)).height,
            "extra_other": e.filter(~(is_tree & (pl.col("Height") <= 5.0))).height,
        })
    same_mort = pl.all_horizontal([(pl.col(c) == pl.col(f"{c}_r")) | (pl.col(c).is_nan() & pl.col(f"{c}_r").is_nan())
                                   for c in MORT])
    out["matched_mort_identical_share"] = float(M.select(same_mort.mean()).item()) if M.height else None
    out["g1_all_prod_rows_found"] = miss.height == 0
    out["g2_extra_only_le5_trees"] = all(r["extra_other"] == 0 for r in out["per_year"])
    out["PASS"] = out["g1_all_prod_rows_found"] and out["g2_extra_only_le5_trees"]
    if miss.height:
        out["first_unmatched"] = miss.head(5).to_dicts()
        out["first_unmatched_cells"] = miss.group_by("Year").agg(pl.col("Cell").min()).to_dicts()
    print(json.dumps(out, indent=1, default=str))
    json.dump(out, open(os.path.join(a.run, "gate.json"), "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
