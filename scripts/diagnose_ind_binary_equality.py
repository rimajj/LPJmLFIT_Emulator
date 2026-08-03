#!/usr/bin/env python
"""Does a small-subset C re-run reproduce the global ground-truth run's ``ind`` rows for the
same cell, bit-for-bit?

This is the gate that decides whether ground truth produced by DIFFERENT builds of the C
binary may be compared as an ensemble.  Motivation: the ssp370 seed1 member was produced by
the ``Feb  5 2026`` build; the current ``bin/lpjml`` is a ``Jul 21 2026`` rebuild that is not
only "Feb-5 source + the daily-grass-GPP patch" but also a RHEL8 -> RHEL9 toolchain rebuild
(GCC 8.5.0 -> 11.5.0, GLIBC_2.14 -> 2.33/2.34).  If the rebuild moved the trajectory, a
seed1-vs-seed2 noise floor is contaminated by more than the seed.

Design — TWO runs, so a mismatch is attributable:

* run **A** = the single cell alone.
* run **B** = a small block containing that cell (the DECOMPOSITION CONTROL).

  ``A == B`` means the cell's trajectory does not depend on which other cells share the job,
  so a mismatch against the global truth is the *binary*.  ``A != B`` means the comparison
  cannot isolate the binary at all and the whole gate is void.

Comparison is on the 29 ``ind`` columns as FORMATTED TEXT.  ``fwriteoutput_ind.c:27`` writes
``%g`` = 6 significant digits, so string equality is the strongest test the file supports and
a float tolerance below ~1e-5 is meaningless.

Usage::

    scripts/sbatch_python.sh S-bineq-cmp scripts/diagnose_ind_binary_equality.py \
        --truth /p/tmp/jamirp/emulator_global/ind_ssp370_seed1_all.parquet \
        --cell 42490 \
        --run A=/p/tmp/jamirp/S_binary_equality_gate/A_cell42490/output/ind_2020_2100.csv \
        --run B=/p/tmp/jamirp/S_binary_equality_gate/B_block42480_42500/output/ind_2020_2100.csv
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import polars as pl

INT_COLS = ("Year", "ID", "Type", "Age", "isdead", "Patch", "Cell")
# Row identity within a cell-year. ID is the individual's identity in the C writer.
KEY = ("Year", "Patch", "ID")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_csv(path: Path, cell: int) -> pl.DataFrame:
    hdr = pl.scan_csv(path, n_rows=1).collect_schema().names()
    schema = {c: (pl.Int64 if c in INT_COLS else pl.Float64) for c in hdr}
    return (
        pl.scan_csv(path, schema_overrides=schema)
        .filter(pl.col("Cell") == cell)
        .collect()
        .sort(list(KEY))
    )


def load_truth(path: Path, cell: int) -> pl.DataFrame:
    return pl.scan_parquet(path).filter(pl.col("Cell") == cell).collect().sort(list(KEY))


def as_text(df: pl.DataFrame, cols: list[str]) -> pl.DataFrame:
    """Render every column with %g-equivalent 6-significant-digit formatting."""
    out = {}
    for c in cols:
        s = df[c]
        if c in INT_COLS:
            out[c] = s.cast(pl.Int64).cast(pl.Utf8)
        else:
            out[c] = s.cast(pl.Float64).map_elements(
                lambda v: format(v, ".6g"), return_dtype=pl.Utf8
            )
    return pl.DataFrame(out)


def compare(name: str, a: pl.DataFrame, b: pl.DataFrame, cols: list[str]) -> dict:
    res = {"name": name, "rows_a": a.height, "rows_b": b.height}
    if a.height != b.height:
        res["verdict"] = "ROWCOUNT_MISMATCH"
        return res
    ta, tb = as_text(a, cols), as_text(b, cols)
    per_col = {}
    for c in cols:
        n = int((ta[c] != tb[c]).sum())
        if n:
            per_col[c] = n
    res["mismatched_cols"] = per_col
    res["verdict"] = "IDENTICAL" if not per_col else "DIFFERS"
    if per_col:
        # first offending row, for a concrete failure report
        bad = None
        for c in per_col:
            idx = int((ta[c] != tb[c]).arg_max())
            bad = (c, idx, ta[c][idx], tb[c][idx])
            break
        res["first_diff"] = {"col": bad[0], "row": bad[1], "a": bad[2], "b": bad[3]}
        res["key_at_first_diff"] = {k: a[k][bad[1]] for k in KEY}
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--truth", type=Path, required=True, help="ground-truth parquet")
    ap.add_argument("--cell", type=int, required=True, help="0-based orderA cell index")
    ap.add_argument(
        "--run",
        action="append",
        required=True,
        metavar="LABEL=path/to/ind.csv",
        help="a subset re-run's ind CSV; repeat for the decomposition control",
    )
    args = ap.parse_args()

    runs: dict[str, pl.DataFrame] = {}
    for spec in args.run:
        label, _, p = spec.partition("=")
        path = Path(p)
        if not path.is_file():
            log(f"FATAL: run {label}: missing {path}")
            return 2
        runs[label] = load_csv(path, args.cell)
        log(f"run {label}: {runs[label].height} rows for cell {args.cell}  ({path})")

    truth = load_truth(args.truth, args.cell)
    log(f"truth  : {truth.height} rows for cell {args.cell}  ({args.truth})")
    if truth.height == 0:
        log("FATAL: truth has no rows for this cell — wrong parquet or wrong cell index")
        return 2

    cols = [c for c in truth.columns if c in set(next(iter(runs.values())).columns)]
    log(f"comparing {len(cols)} columns on {len(KEY)}-key sort {KEY}")

    results = []
    labels = list(runs)
    # 1) the decomposition control, first: if it fails the rest is uninterpretable
    if len(labels) >= 2:
        results.append(
            compare(
                f"{labels[0]} vs {labels[1]} (DECOMPOSITION CONTROL)",
                runs[labels[0]],
                runs[labels[1]],
                cols,
            )
        )
    # 2) each run against the global truth
    for lb in labels:
        results.append(compare(f"{lb} vs TRUTH", runs[lb], truth, cols))

    print()
    print("=" * 78)
    for r in results:
        print(f"{r['verdict']:20s} {r['name']}   rows {r['rows_a']} vs {r['rows_b']}")
        if r.get("mismatched_cols"):
            print(f"    mismatched columns: {r['mismatched_cols']}")
            print(f"    first diff: {r.get('first_diff')} at {r.get('key_at_first_diff')}")
    print("=" * 78)

    ctrl = results[0] if len(labels) >= 2 else None
    truth_cmps = [r for r in results if "TRUTH" in r["name"]]
    if ctrl and ctrl["verdict"] != "IDENTICAL":
        print("GATE VOID: the cell's trajectory depends on the cell set, so this test cannot")
        print("           isolate the binary. Do not draw a conclusion about the rebuild.")
        return 3
    if all(r["verdict"] == "IDENTICAL" for r in truth_cmps):
        print("GATE PASS: the current binary reproduces the ground-truth trajectory bit-for-bit")
        print("           (to the writer's 6-significant-digit precision). Builds are comparable.")
        return 0
    print("GATE FAIL: the current binary does NOT reproduce the ground truth for this cell.")
    print("           The toolchain rebuild moved the trajectory; a cross-build ensemble is")
    print("           not a pure seed comparison. Re-decide the basis before using the run.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
