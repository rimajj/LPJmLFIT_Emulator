#!/usr/bin/env python3
"""explore_glob_tabeval.py -- LINE X: score a per-tree rollout of the Germany engine (explore_de_engine, run on the
global data root built by explore_glob_tabroot.py) on the global venue with the global scorer (explore_glob_eval,
ADR 0315 sec. 3-5). The per-tree arms A-TAB and, on top of it, A3 / A4 / A6 are scored here.

INPUT  an engine run dir  <XDE_ROOT>/runs/<arm>/<gcm>_s<seed>_<start>-<end>_<legs>_<clim>_r<rep>/chunk_<k>/
       y<Y>_<scen>.parquet  (EMIT columns; Cell = the root's Cell16, mapped back to grid.bin cells here)
REDUCTION  the scorer's own: explore_de_reference.living + reduce_window, NPATCH 25, the dev cells, windows
       h1985 (1985-2014) and w2071 (2071-2100). A 2014 start uses the truth member's own h1985 as its baseline (as the
       nulls that start from the truth do); a 1985 start uses its own emitted 1985-2014 (Historical part).
SCORES (per scored leg; GS370 = ssp370 is the gated one, ssp126/ssp245 are reported -- those scenarios were in the
       training set of OTHER members): E.score() -> level pass rates, area totals, response slopes. Plus, for a 1985
       start, DP-G1 (d): the 2014 snapshot's area totals against the truth member's 2014 (stems, biomass per stem).
       Speed: core-s per cell-year from the chunks' meta_<k>.json (one core).
OUTPUT <DATA>/eval/scores_<label>.csv (one row per scored leg), printed.

HARNESS CHECK (`--expect frozen`): the engine's FROZEN stepper from 2014 emits the truth's 2014 roster every year, so
its w2071 reduction must equal explore_glob_eval's persist_2014 null: n_per_patch and agb_per_stem EXACTLY (|diff| <
1e-9 relative, every cell), trait medians up to linear-interpolation of a 30x repeated sample (reported, not gated),
and therefore stems_ratio 0.907 / agb_per_stem_ratio 1.283 (ADR 0315 sec. 7). Any other result is a harness bug.

Run: explore_glob_tabeval.py --run DIR --label NAME [--legs ssp370,ssp126,ssp245] [--expect frozen]
     [--truth-seed 2 --fold 1]   (A4 calibration basis: a training member, one fold of dev cells; never gated)
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_reference as R  # noqa: E402
import explore_glob_eval as E  # noqa: E402

ROOT = os.environ.get("XDE_ROOT", os.path.join(E.DATA, "xde"))
CMAP = os.path.join(ROOT, "shared", "registry", "cell_map.parquet")
COLS = ["Year", "Cell", "Type", "isdead"] + R.TRAITS


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def read_run(run: str, scen: str, y0: int, y1: int) -> pl.LazyFrame:
    fs = []
    for y in range(y0, y1 + 1):
        fy = sorted(glob.glob(os.path.join(run, "chunk_*", f"y{y}_{scen}.parquet")))
        assert fy, f"{run}: no y{y}_{scen}"
        fs += fy
    cm = pl.read_parquet(CMAP).select(pl.col("Cell").cast(pl.Int32), pl.col("Cell_orig").cast(pl.Int32))
    lf = pl.scan_parquet(fs).select(COLS).with_columns(pl.col("Cell").cast(pl.Int32))
    return (lf.join(cm.lazy(), on="Cell", how="inner").drop("Cell").rename({"Cell_orig": "Cell"})
            .select(pl.col("Year").cast(pl.Int32), pl.col("Cell"), pl.col("Type").cast(pl.Int8),
                    pl.col("isdead").cast(pl.Int8), *[pl.col(t).cast(pl.Float32) for t in R.TRAITS]))


def reduce_lf(lf: pl.LazyFrame, y0: int, y1: int, cells: list[int]) -> pl.DataFrame:
    lf = lf.filter(pl.col("Year").is_between(y0, y1) & pl.col("Cell").is_in(cells))
    ny = lf.select(pl.col("Year").n_unique()).collect().item()
    assert ny == y1 - y0 + 1, f"{ny} years in {y0}-{y1}"
    trees = R.living(lf).collect()
    cy = pl.DataFrame({"Cell": cells, "n_years": [ny] * len(cells)})
    d = R.reduce_window(trees, cy, E.NPATCH)
    return d.with_columns(pl.when(pl.col("n_per_patch") > 0).then(pl.col("agb_stand") / pl.col("n_per_patch"))
                          .otherwise(None).alias("agb_per_stem"))


def totals(d: pl.DataFrame, cells: pl.DataFrame) -> tuple[float, float]:
    a = d.join(cells, on="Cell").with_columns(np.cos(np.deg2rad(pl.col("lat"))).alias("w")).fill_null(0.0)
    n = float((a["n_per_patch"] * a["w"]).sum())
    b = float((a["agb_stand"] * a["w"]).sum())
    return n, b / n


def speed(run: str) -> float | None:
    """Total process CPU seconds (every thread) over cell-years, from the engine's per-chunk meta_<k>.json."""
    tot_s, tot_cy = 0.0, 0
    for f in glob.glob(os.path.join(run, "**", "meta_*.json"), recursive=True):
        m = json.load(open(f))
        tot_s += float(sum(m["timing_core_s"].values()))
        tot_cy += int(m["cell_years"])
    return tot_s / tot_cy if tot_cy else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--legs", default="ssp370,ssp126,ssp245")
    ap.add_argument("--expect", default=None, choices=[None, "frozen"])
    ap.add_argument("--truth-seed", type=int, default=E.TRUTH,
                    help="member scored against (default 8 = GS370); A4 calibration uses a training member")
    ap.add_argument("--fold", type=int, default=None, help="score only the dev cells of this fold (A4 calibration)")
    a = ap.parse_args()
    TR = a.truth_seed
    rj = json.load(open(os.path.join(a.run, "run.json"))) if os.path.exists(os.path.join(a.run, "run.json")) else {}
    start = int(rj.get("start", 2014 if "_2014-" in a.run else 1985))
    cells = E.dev_cells()
    if a.fold is not None:
        cells = cells.filter(pl.col("fold") == a.fold)
    clist = cells["Cell"].to_list()
    T_h, R_h = E.lev(E.mname("historical", TR)), E.lev(E.mname("historical", E.REPLICA))
    if start <= 1985:
        P_h = reduce_lf(read_run(a.run, "Historical", 1985, 2014), 1985, 2014, clist).select(["Cell"] + E.PANEL)
        snap = reduce_lf(read_run(a.run, "Historical", 2014, 2014), 2014, 2014, clist)
        tsnap = pl.read_parquet(os.path.join(E.LEV, f"{E.mname('historical', TR)}_y2014.parquet"))
        (nP, bP), (nT, bT) = totals(snap, cells), totals(tsnap, cells)
        d_stems, d_agb = nP / nT, bP / bT
        log(f"DP-G1 (d) free run 1985 -> 2014: stems {d_stems:.3f}, biomass per stem {d_agb:.3f}")
    else:
        P_h, d_stems, d_agb = T_h, None, None
    rows = []
    for scen in a.legs.split(","):
        T_w, R_w = E.lev(E.mname(scen, TR)), E.lev(E.mname(scen, E.REPLICA))
        tb = (T_w.filter(pl.col("n_per_patch") > 0).select("Cell")
              .vstack(T_h.filter(pl.col("n_per_patch") > 0).select("Cell")).unique())
        sc = cells.join(tb, on="Cell")
        Pw_full = reduce_lf(read_run(a.run, scen, 2071, 2100), 2071, 2100, clist)
        s = E.score(Pw_full.select(["Cell"] + E.PANEL), P_h, T_w, T_h, R_w, R_h, sc)
        row = dict(label=a.label, run=os.path.basename(a.run), arm=os.path.basename(os.path.dirname(a.run)),
                   start=start, scen=scen, gated=scen == "ssp370" and TR == E.TRUTH and a.fold is None,
                   truth_seed=TR, fold=a.fold, free2014_stems=d_stems, free2014_agb_per_stem=d_agb,
                   core_s_per_cell_year=speed(a.run), **s)
        rows.append(row)
        log(scen, json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()}))
        if a.expect == "frozen":
            snap = pl.read_parquet(os.path.join(E.LEV, f"{E.mname('historical', TR)}_y2014.parquet"))
            j = Pw_full.join(snap, on="Cell", suffix="_s")
            exact = {c: float(((j[c] - j[f"{c}_s"]).abs() / j[f"{c}_s"].abs().clip(1e-12)).fill_nan(0.0).max() or 0.0)
                     for c in ("n_per_patch", "agb_per_stem")}
            med = {q: float((j[q] - j[f"{q}_s"]).abs().max() or 0.0) for q in E.PANEL[2:]}
            ok = all(v < 1e-9 for v in exact.values())
            log(f"HARNESS frozen==persist_2014: n/agb max rel diff {exact} -> {'PASS' if ok else 'FAIL'}; "
                f"median max abs diff (interpolation, not gated) {med}")
    df = pl.DataFrame(rows)
    out = os.path.join(E.EVAL, f"scores_{a.label}.csv")
    df.write_csv(out)
    log("->", out)


if __name__ == "__main__":
    main()
