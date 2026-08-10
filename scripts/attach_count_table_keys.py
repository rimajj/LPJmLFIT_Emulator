#!/usr/bin/env python3
"""RUNG 1 ENABLER — recover the (Cell, Patch, Year) key of every row of a FROZEN pooled count table.

WHY. The rung-1 recursion arm (ADR 0112) has to march the count prediction forward in time per
(Cell, Patch): feed the model its OWN previous-year count instead of LPJmL-FIT's. The frozen production
tables (`slow_count_pooled_w20_t8`, built before ADR 0108 added `years.i64`) ship only `cells.i64` +
`scenario.i64`, so the year and the patch are not recoverable from the table itself.

⚠ AND THEY ARE NOT RECOVERABLE BY INFERENCE EITHER, which is why this script exists rather than a heuristic.
Two tempting shortcuts both fail on the real table, measured:
  * "cut every cell block into equal-length chains" — 24.8 % of historic cells and 49.9 % of ssp370 cells have
    a block length that is not a multiple of the year span, because a patch that loses every tree for a year
    breaks its own run (the builder's `_prev_year + 1 == Year` filter);
  * "start a new chain wherever `n_prev[i+1] != y[i]`" — `n_living` is a small integer, so two adjacent
    patches whose runs happen to join on the same count are silently MERGED, and the merge is invisible.
    That would carry one patch's predicted count into another patch's first year, concentrated in the sparse
    cells where the noise floor is already worst.

SO: recompute the key from the source `ind` parquet by replaying the builder's own pipeline for the KEY
COLUMNS ONLY (a projected scan — 5 of 29 columns), and then PROVE the alignment before writing anything:

    n_living  recomputed  ==  y.f64          row for row, exactly
    n_prev    recomputed  ==  X.f64[:, j]    row for row, exactly   (j = the `n_prev` column)
    Cell      recomputed  ==  cells.i64      row for row, exactly

If all three hold on all rows, the attached `years.i64` / `patches.i64` are the frozen table's own keys and
nothing was inferred. If they do not, the script reports the per-cell mismatch and writes a `cells_ok.i64`
mask instead of pretending — the expected cause is the documented polars streaming `group_by` key-set
nondeterminism (CLAUDE.md §4: two runs of the same aggregate over these tables differed in 141 cells and
duplicated keys in 12), which is a property of the ssp370 block, not of this script.

Usage (SLURM; EXPORT every knob — sbatch_python.sh forwards only a fixed list, CLAUDE.md §9):
    export SRC=/p/tmp/jamirp/emulator_global/slow_count_pooled_w20_t8
    export OUT=/p/tmp/jamirp/emulator_global/rung1_keys_t8
    export SEED=1 BOUNDARY_WINDOW=20
    NCPUS=32 TIME=04:00:00 scripts/sbatch_python.sh S-keys scripts/attach_count_table_keys.py
Env: SRC, OUT, SEED (1), SCENARIOS (default from the source manifest's `pooled_scenarios`),
     SOIL_TBL_<SCENARIO> (override a soilmoist table path).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import polars as pl

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "python" / "src"))
from lpjmlfit_emulator import data as ind_data  # noqa: E402

BASE = "/p/tmp/jamirp/emulator_global"
IND = {"historic": f"{BASE}/ind_hist_seed{{seed}}_all.parquet",
       "ssp370": f"{BASE}/ind_ssp370_seed{{seed}}_all.parquet"}
SOIL_TBL = {"historic": f"{BASE}/tables/cell_year_soilmoist_ye_hist.parquet",
            "ssp370": f"{BASE}/tables/cell_year_soilmoist_ye_ssp.parquet"}
TREE_TYPES = list(ind_data.TREE_TYPES)

SRC = Path(os.environ.get("SRC", f"{BASE}/slow_count_pooled_w20_t8"))
OUT = Path(os.environ.get("OUT", f"{BASE}/rung1_keys_t8"))
SEED = int(os.environ.get("SEED", "1"))


def read_manifest(d: Path) -> dict[str, str]:
    man: dict[str, str] = {}
    for ln in (d / "manifest.txt").read_text().splitlines():
        if "\t" in ln:
            k, v = ln.split("\t", 1)
            man[k] = v
    return man


def recompute_keys(scenario: str) -> pl.DataFrame:
    """Replay the builder's key pipeline: survivor count per (Cell,Patch,Year) -> soilmoist inner join ->
    the AR shift/filter -> the final sort. Key columns only."""
    src = IND[scenario].format(seed=SEED)
    print(f"\n== [{scenario}] scanning {src}")
    agg = (pl.scan_parquet(src)
           .filter(pl.col("Type").is_in(TREE_TYPES) & (pl.col("isdead") == 0))
           .group_by(["Cell", "Patch", "Year"]).agg(pl.len().alias("n_living"))
           .collect(engine="streaming"))
    print(f"   aggregate: {agg.height:,} (Cell,Patch,Year) groups")
    # CLAUDE.md §4: assert the KEY SET, because streaming group_by can duplicate whole groups and the usual
    # "rows dropped" coverage statistic goes NEGATIVE when it does, so no threshold test would fire.
    nk = agg.select(["Cell", "Patch", "Year"]).n_unique()
    if nk != agg.height:
        raise SystemExit(f"FATAL: {agg.height - nk} DUPLICATE (Cell,Patch,Year) keys in the recomputed "
                         f"aggregate — polars streaming group_by nondeterminism. Re-run.")

    sm_path = os.environ.get(f"SOIL_TBL_{scenario.upper()}", SOIL_TBL[scenario])
    sm = pl.read_parquet(sm_path).select(["Cell", "Year"]).unique()
    h0 = agg.height
    agg = agg.join(sm, on=["Cell", "Year"], how="inner")
    print(f"   after soilmoist inner-join ({Path(sm_path).name}): {agg.height:,} rows "
          f"({h0 - agg.height:,} dropped)")

    agg = agg.sort(["Cell", "Patch", "Year"])
    tbl = (agg.with_columns(pl.col("n_living").shift(1).over(["Cell", "Patch"]).alias("n_prev"),
                            pl.col("Year").shift(1).over(["Cell", "Patch"]).alias("_py"))
           .filter(pl.col("_py") + 1 == pl.col("Year")).drop("_py")
           .sort(["Cell", "Patch", "Year"]))
    print(f"   after the AR shift/filter: {tbl.height:,} rows")
    return tbl


def main() -> int:
    man = read_manifest(SRC)
    n, p = int(man["n"]), int(man["p"])
    colnames = man["colnames"].split()
    jn = colnames.index("n_prev")
    scenarios = os.environ.get("SCENARIOS", man.get("pooled_scenarios", "historic ssp370")).replace(",", " ").split()
    print(f"== SRC={SRC.name} n={n:,} p={p} scenarios={scenarios} seed={SEED}")

    cells = np.fromfile(SRC / "cells.i64", dtype="<i8")
    scen = np.fromfile(SRC / man.get("scenario_tag", "scenario.i64"), dtype="<i8")
    y = np.fromfile(SRC / "y.f64", dtype="<f8")
    X = np.memmap(SRC / "X.f64", dtype="<f8", mode="r", shape=(n, p))
    nprev_frozen = np.ascontiguousarray(X[:, jn], dtype="<f8")

    years = np.full(n, -1, dtype="<i8")
    patches = np.full(n, -1, dtype="<i8")
    ok_all = True
    bad_cells: set[int] = set()

    for si, scenario in enumerate(scenarios):
        sel = np.flatnonzero(scen == si)
        if sel.size == 0:
            raise SystemExit(f"FATAL: no rows with scenario tag {si} for {scenario}")
        lo, hi = int(sel[0]), int(sel[-1]) + 1
        if hi - lo != sel.size:
            raise SystemExit(f"FATAL: scenario block {si} is not contiguous — the alignment below assumes it")
        tbl = recompute_keys(scenario)
        print(f"   frozen block rows {sel.size:,} vs recomputed {tbl.height:,}")

        rc = tbl["Cell"].to_numpy()
        rn = tbl["n_living"].to_numpy().astype("<f8")
        rp = tbl["n_prev"].to_numpy().astype("<f8")
        if tbl.height == sel.size:
            same = (rc == cells[lo:hi]) & (rn == y[lo:hi]) & (rp == nprev_frozen[lo:hi])
            print(f"   EXACT-ALIGNMENT CHECK: {same.sum():,}/{sel.size:,} rows agree "
                  f"({100.0 * same.mean():.4f} %)")
            if same.all():
                years[lo:hi] = tbl["Year"].to_numpy()
                patches[lo:hi] = tbl["Patch"].to_numpy()
                continue
        else:
            print(f"   ROW COUNT DIFFERS by {tbl.height - sel.size:,} — falling back to per-cell alignment")
        ok_all = False

        # per-cell fallback: keep only the cells whose recomputed block matches the frozen block exactly
        fr = pl.DataFrame({"_i": np.arange(lo, hi, dtype="<i8"), "Cell": cells[lo:hi],
                           "n_living": y[lo:hi], "n_prev": nprev_frozen[lo:hi]})
        gr = fr.group_by("Cell").agg(pl.len().alias("nf"))
        gt = tbl.group_by("Cell").agg(pl.len().alias("nt"))
        cmp_ = gr.join(gt, on="Cell", how="full", coalesce=True).fill_null(0)
        good = cmp_.filter(pl.col("nf") == pl.col("nt"))["Cell"].to_numpy()
        goodset = np.isin(rc, good)
        fmask = np.isin(cells[lo:hi], good)
        if int(goodset.sum()) == int(fmask.sum()):
            fi = fr.filter(pl.col("Cell").is_in(good))
            ti = tbl.filter(pl.col("Cell").is_in(good))
            same = ((ti["Cell"].to_numpy() == fi["Cell"].to_numpy())
                    & (ti["n_living"].to_numpy().astype("<f8") == fi["n_living"].to_numpy())
                    & (ti["n_prev"].to_numpy().astype("<f8") == fi["n_prev"].to_numpy()))
            idx = fi["_i"].to_numpy()[same]
            years[idx] = ti["Year"].to_numpy()[same]
            patches[idx] = ti["Patch"].to_numpy()[same]
            print(f"   per-cell fallback: {len(good):,} cells with matching block length, "
                  f"{same.sum():,} rows keyed exactly ({100.0 * same.sum() / sel.size:.3f} % of the block)")
        bad = set(cmp_.filter(pl.col("nf") != pl.col("nt"))["Cell"].to_list())
        bad_cells |= bad
        print(f"   {len(bad):,} cells could NOT be keyed (block length differs) — they are excluded, not guessed")

    OUT.mkdir(parents=True, exist_ok=True)
    years.tofile(OUT / "years.i64")
    patches.tofile(OUT / "patches.i64")
    keyed = int((years >= 0).sum())
    with open(OUT / "manifest.txt", "w") as f:
        f.write(f"src\t{SRC}\n")
        f.write(f"n\t{n}\n")
        f.write(f"keyed_rows\t{keyed}\n")
        f.write(f"keyed_frac\t{keyed / n:.6f}\n")
        f.write(f"exact_alignment\t{'yes' if ok_all else 'no'}\n")
        f.write(f"unkeyed_cells\t{len(bad_cells)}\n")
        f.write(f"seed\t{SEED}\n")
        f.write(f"scenarios\t{' '.join(scenarios)}\n")
        f.write("verified\tn_living == y.f64 and n_prev == X.f64[:,n_prev] and Cell == cells.i64, row for row\n")
        f.write("note\tunkeyed rows carry -1; a rung-1 recursion arm MUST drop them, never guess a chain\n")
    if bad_cells:
        np.array(sorted(bad_cells), dtype="<i8").tofile(OUT / "unkeyed_cells.i64")
    print(f"\n== wrote {OUT}/years.i64 + patches.i64 — {keyed:,}/{n:,} rows keyed "
          f"({100.0 * keyed / n:.4f} %), {len(bad_cells):,} cells unkeyed, exact_alignment="
          f"{'yes' if ok_all else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
