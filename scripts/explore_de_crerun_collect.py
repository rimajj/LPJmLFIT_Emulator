"""explore_de_crerun_collect.py — LINE X, Germany emulator: gate + convert finished sapling re-runs of the original
(explore_de_crerun.py) into parquet, then delete the CSV.

Per run dir (…/crerun/<gcm>_<scen>_s<seed>_c<a>-<b>_<first>-<last>_<tag>):
  0. the run log carries "lpjml successfully terminated, <ncell> grid cells processed." (else: skip, not done)
  1. gate EVERY output year against the production member (explore_de_crerun_gate.py logic: every production row
     reproduced incl. mort_*, every extra row a tree with printed Height <= 5) -> <run>/gate.json; the first year
     that fails is recorded, so a slow divergence of the trajectory is dated, not hidden
  2. write /p/tmp/jamirp/X_de/ind_all/<gcm>/<scen>/s<seed>/<win>/c<a>-<b>.parquet (same 29 columns + dtypes as
     the production parquet, + `in_prod` = the row is a production row, rows sorted Year, Cell, Patch, writer order)
  3. delete output/ind.csv only if the gate passed in every year and the parquet read-back row count matches
Usage:  python explore_de_crerun_collect.py <run_dir> [<run_dir> ...]   (or --glob '<pattern>' [--task i --ntask n])
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_convert as cv  # noqa: E402

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
MORT = ["mort_npp", "mort_age", "mort_water", "mort_temp", "mort"]
NAME = re.compile(r"(?P<gcm>.+?)_(?P<scen>Historical|ssp\d+)_s(?P<seed>\d)_c(?P<a>\d+)-(?P<b>\d+)_(?P<f>\d+)-(?P<l>\d+)_")


def done(run, ncell):
    logs = sorted(glob.glob(os.path.join(run, "lpjml.*.out")), key=os.path.getmtime)
    pat = f"lpjml successfully terminated, {ncell} grid cells processed."
    return bool(logs) and any(pat in open(lg).read() for lg in logs)


def one(run):
    m = NAME.match(os.path.basename(run))
    assert m, run
    gcm, scen, seed = m["gcm"], m["scen"], int(m["seed"])
    a, b = int(m["a"]), int(m["b"])
    win = "h1985" if scen == "Historical" else "w2015"
    csv = os.path.join(run, "output", "ind.csv")
    out = os.path.join(XDE, "ind_all", gcm, scen, f"s{seed}", win, f"c{a}-{b}.parquet")
    if os.path.exists(out) and not os.path.exists(csv):
        print(f"{run}: already collected")
        return True
    if not done(run, b - a + 1):
        print(f"{run}: NOT finished (no completion line)")
        return False
    R = pl.read_csv(csv, has_header=True, new_columns=cv.COLS, schema=cv.SCHEMA).with_row_index("_w")
    src = os.path.join(XDE, "ind", gcm, scen, f"s{seed}", win)
    P = (pl.scan_parquet(os.path.join(src, "cb=*", "*.parquet"))
         .filter(pl.col("Cell").is_between(a, b) & pl.col("Year").is_in(R["Year"].unique().to_list())).collect())
    cols = [c for c in cv.COLS if c not in MORT]
    on = [*cols, "_k"]
    Pn = P.with_columns(_k=pl.int_range(pl.len()).over(cols))
    Rn = R.with_columns(_k=pl.int_range(pl.len()).over(cols))
    hit = Rn.join(Pn.select(on).with_columns(in_prod=pl.lit(True)), on=on, how="left", nulls_equal=True)
    hit = hit.with_columns(pl.col("in_prod").fill_null(False))
    miss = Pn.join(Rn.select(on), on=on, how="anti", nulls_equal=True)
    tree_le5 = (pl.col("Type") <= 6) & (pl.col("Height") <= 5.0)
    per = []
    for y in sorted(R["Year"].unique().to_list()):
        h = hit.filter(pl.col("Year") == y)
        per.append({"Year": int(y), "prod_rows": P.filter(pl.col("Year") == y).height, "rerun_rows": h.height,
                    "prod_unmatched": miss.filter(pl.col("Year") == y).height,
                    "extra_tree_le5": h.filter(~pl.col("in_prod") & tree_le5).height,
                    "extra_other": h.filter(~pl.col("in_prod") & ~tree_le5).height})
    bad = [r["Year"] for r in per if r["prod_unmatched"] or r["extra_other"]]
    g = {"run": run, "member": f"{gcm}_{scen}_s{seed}_{win}", "cells": [a, b], "per_year": per,
         "first_failing_year": bad[0] if bad else None, "PASS": not bad}
    json.dump(g, open(os.path.join(run, "gate.json"), "w"), indent=1)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    W = hit.sort(["Year", "Cell", "Patch", "_w"]).drop(["_w", "_k"])
    W.write_parquet(out, compression="zstd", row_group_size=2_000_000)
    n_back = pl.scan_parquet(out).select(pl.len()).collect().item()
    ok = g["PASS"] and n_back == R.height
    print(f"{run}: rows {R.height} (prod {P.height}), PASS={g['PASS']} first_fail={g['first_failing_year']} "
          f"-> {out} ({n_back} rows)")
    if ok:
        os.remove(csv)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="*")
    ap.add_argument("--glob", default=None)
    ap.add_argument("--task", type=int, default=None)
    ap.add_argument("--ntask", type=int, default=None)
    a = ap.parse_args()
    runs = list(a.runs) + (sorted(glob.glob(a.glob)) if a.glob else [])
    if a.task is not None:
        runs = runs[a.task::a.ntask]
    res = {r: one(r) for r in runs}
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
