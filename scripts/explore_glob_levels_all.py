#!/usr/bin/env python3
"""explore_glob_levels_all.py -- per-cell window levels on ALL cells of the global venue (ADR 0315), not only the dev
cells (Cell % 10 == 0) that every global score so far used.

THE SAME REDUCTION as explore_glob_eval.stage_levels (it calls explore_glob_eval.reduce, i.e. explore_de_reference's
living() + reduce_window(), NPATCH = 25), read from the registry's `ind_path` (the full per-tree tables, partitioned
by cell block cb = Cell // 500) instead of `ind_dev_path`. One block at a time: every block holds a disjoint set of
cells, so the per-cell aggregation never crosses a partition boundary (CLAUDE.md sec. 4: a streamed global group_by
can emit duplicate or missing keys) -- and the assembled table is asserted to carry each non-rock cell exactly once.

Census = every non-rock cell of folds.parquet (as the dev reduction's census was every non-rock dev cell); cells
with no living tree get n_per_patch = 0.

Usage:
  explore_glob_levels_all.py reduce <member> [<member> ...]   -> eval/levels_all/<member>.parquet
                                                                 (per-block pieces kept under _blocks/ for resume)
  explore_glob_levels_all.py gate                              dev-cell rows of every levels_all file vs
                                                                 eval/levels/<member>.parquet: max |diff| per column,
                                                                 null patterns identical -> eval/levels_all/_gate.csv
Members needed by the GS370 and GM splits: Feb-build seeds 2,3,4,6,7,8 x historical/ssp126/ssp245/ssp370 (24).
The default eval/levels files and explore_glob_eval.py are untouched.
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_glob_eval as ev  # noqa: E402

OUT = os.path.join(ev.EVAL, "levels_all")
CPP = 500  # the converter's cb = Cell // 500
SEEDS = (2, 3, 4, 6, 7, 8)
SCENS = ("historical", "ssp126", "ssp245", "ssp370")
NEEDED = [ev.mname(sc, s) for s in SEEDS for sc in SCENS]


def all_cells() -> pl.DataFrame:
    f = pl.read_parquet(os.path.join(ev.REG, "folds.parquet"))
    return f.filter(~pl.col("rock")).select("Cell", "lat", "fold", "is_dev")


def reduce_member(member: str):
    m = pl.read_parquet(os.path.join(ev.REG, "members.parquet")).filter(pl.col("member") == member)
    assert m.height == 1, member
    r = m.row(0, named=True)
    y0, y1 = ev.WIN[r["window"]]
    out = os.path.join(OUT, f"{member}.parquet")
    if os.path.exists(out):
        ev.log(f"{member}: exists, skipped")
        return
    bdir = os.path.join(OUT, "_blocks", member)
    os.makedirs(bdir, exist_ok=True)
    cells = all_cells().with_columns((pl.col("Cell") // CPP).alias("cb"))
    t0 = time.time()
    parts = []
    for cb in sorted(cells["cb"].unique().to_list()):
        piece = os.path.join(bdir, f"cb={cb:02d}.parquet")
        if not os.path.exists(piece):
            src = os.path.join(r["ind_path"], f"cb={cb:02d}")
            files = sorted(os.path.join(src, x) for x in os.listdir(src) if x.endswith(".parquet"))
            assert files, f"no parquet in {src}"
            bc = cells.filter(pl.col("cb") == cb)["Cell"].to_list()
            d = ev.reduce(files if len(files) > 1 else files[0], y0, y1, bc)
            assert d.height == len(bc) and d["Cell"].n_unique() == len(bc), f"{member} cb={cb}: key set"
            d.write_parquet(piece)
        parts.append(pl.read_parquet(piece))
    d = pl.concat(parts).sort("Cell")
    assert d["Cell"].n_unique() == d.height == cells.height, f"{member}: {d.height} rows, {cells.height} cells"
    assert set(d["Cell"].to_list()) == set(cells["Cell"].to_list())
    d.write_parquet(out)
    ev.log(f"{member}: {y0}-{y1}, {d.height} cells, {int((d['n_per_patch'] > 0).sum())} with trees "
           f"({time.time() - t0:.0f}s)")


def gate():
    rows = []
    for mem in NEEDED:
        a = os.path.join(OUT, f"{mem}.parquet")
        b = os.path.join(ev.LEV, f"{mem}.parquet")
        if not os.path.exists(a):
            ev.log(f"gate: {mem} missing")
            continue
        A = pl.read_parquet(a)
        B = pl.read_parquet(b)
        j = B.join(A, on="Cell", how="left", suffix="_all")
        assert j.height == B.height and j["n_years_all"].null_count() == 0, f"{mem}: dev cell missing in levels_all"
        num = [c for c, t in B.schema.items() if c != "Cell" and t.is_numeric()]
        mx, nullmis = 0.0, 0
        worst = ""
        for c in num:
            x, y = j[c].to_numpy().astype(float), j[f"{c}_all"].to_numpy().astype(float)
            nx, ny = np.isnan(x), np.isnan(y)
            nullmis += int((nx != ny).sum())
            ok = ~nx & ~ny
            dm = float(np.max(np.abs(x[ok] - y[ok]))) if ok.any() else 0.0
            if dm > mx:
                mx, worst = dm, c
        rows.append(dict(member=mem, dev_cells=B.height, max_abs_diff=mx, worst_col=worst, null_mismatch=nullmis))
        ev.log(f"gate {mem}: max |diff| {mx:.3g} ({worst}), null-pattern mismatches {nullmis}")
    g = pl.DataFrame(rows)
    g.write_csv(os.path.join(OUT, "_gate.csv"))
    ok = g.height == len(NEEDED) and g["null_mismatch"].sum() == 0 and g["max_abs_diff"].max() < 1e-6
    ev.log(f"GATE levels_all == eval/levels on dev cells ({g.height}/{len(NEEDED)} members): "
           f"{'PASS' if ok else 'FAIL'}; max |diff| overall {g['max_abs_diff'].max():.3g}")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    st = sys.argv[1]
    if st == "reduce":
        for mem in (NEEDED if sys.argv[2:] == ["all"] else sys.argv[2:]):
            reduce_member(mem)
    elif st == "gate":
        gate()
    ev.log("=== DONE")
