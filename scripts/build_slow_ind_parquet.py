#!/usr/bin/env python
"""Stream a ground-truth ``ind_*.csv`` from the LPJmL-FIT C run into the Component-S
``ind`` parquet table (constant memory).

This is the ONE step between a finished C ground-truth run and every ``build_slow_*.py``
consumer.  It was previously reachable only through
``/p/projects/open/Jamir/emulator/src/global_extract.py`` (the FROZEN sibling repo), whose
``--which`` is argparse-restricted to a hard-coded three-entry ``SOURCES`` dict — so a NEW
scenario/seed could not be named at all.  This port takes ``SRC``/``OUT`` explicitly.

Usage (submit it, do not run a 193 GB scan on the login node)::

    NCPUS=16 TIME=02:00:00 scripts/sbatch_python.sh S-indparq-ssp2 \
        scripts/build_slow_ind_parquet.py <SRC.csv> <OUT.parquet>

The OUT **filename is load-bearing**: ``build_slow_runtime_table.py`` resolves
``SCENARIO``/``SEED`` to ``ind_{hist,ssp370}_seed{1,2}_all.parquet`` under
``/p/tmp/jamirp/emulator_global/``, so a table built for ``SCENARIO=ssp370 SEED=2`` must land
at exactly ``ind_ssp370_seed2_all.parquet``.

Two details are load-bearing and must not be "simplified":

* ``schema_overrides`` — polars infers ``Wooddens`` (and other trait columns) as integer from
  the first rows, which silently truncates the column later.  Every non-index column is
  forced to ``Float64``.
* ``filter(Cell >= 0)`` — the writer emits sentinel rows for skipped cells.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import polars as pl

# The frozen 29-column ``ind`` schema (python/src/lpjmlfit_emulator/data.py::IND_COLUMNS).
# Duplicated here ONLY as an assertion target: this script must be runnable from a bare
# conda env without installing the package.  If it disagrees with data.py, data.py wins.
IND_COLUMNS: tuple[str, ...] = (
    "Year",
    "ID",
    "Type",
    "Height",
    "Age",
    "agb",
    "vegc",
    "transp",
    "npp",
    "gpp",
    "wscal_mean",
    "SLA",
    "Longevity",
    "Wooddens",
    "LAI",
    "fpc_ind",
    "minwscal",
    "D95",
    "D95max",
    "beta_root",
    "k_root",
    "mort_npp",
    "mort_age",
    "mort_water",
    "mort_temp",
    "mort",
    "isdead",
    "Patch",
    "Cell",
)
INT_COLS = ("Year", "ID", "Type", "Age", "isdead", "Patch", "Cell")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src", type=Path, help="raw ind_*.csv written by the C run")
    ap.add_argument("out", type=Path, help="destination .parquet")
    ap.add_argument(
        "--allow-schema-drift",
        action="store_true",
        help="proceed even if the CSV header is not the frozen 29-column IND_COLUMNS",
    )
    args = ap.parse_args()

    if not args.src.is_file():
        log(f"FATAL: source does not exist: {args.src}")
        return 2
    if args.out.exists():
        log(f"FATAL: refusing to overwrite existing {args.out} — version it instead")
        return 2

    hdr = pl.scan_csv(args.src, n_rows=1).collect_schema().names()
    log(f"source : {args.src}  ({args.src.stat().st_size / 1e9:.1f} GB)")
    log(f"header : {len(hdr)} columns")
    if tuple(hdr) != IND_COLUMNS:
        missing = [c for c in IND_COLUMNS if c not in hdr]
        extra = [c for c in hdr if c not in IND_COLUMNS]
        msg = (
            f"header != frozen IND_COLUMNS (missing={missing} extra={extra} "
            f"order_ok={tuple(hdr) == IND_COLUMNS})"
        )
        if not args.allow_schema_drift:
            log(f"FATAL: {msg}; pass --allow-schema-drift only if this is deliberate")
            return 2
        log(f"WARNING: {msg}")

    schema = {c: (pl.Int64 if c in INT_COLS else pl.Float64) for c in hdr}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    log(f"sinking -> {args.out}")
    (
        pl.scan_csv(args.src, schema_overrides=schema)
        .filter(pl.col("Cell") >= 0)
        .sink_parquet(args.out, compression="zstd")
    )
    log(f"sink done in {time.time() - t0:.0f}s  ({args.out.stat().st_size / 1e9:.2f} GB)")

    # Coverage report. Deliberately NOT a hard gate on row count: a different stochastic
    # realization legitimately has a different number of individuals.
    lf = pl.scan_parquet(args.out)
    stats = lf.select(
        rows=pl.len(),
        cells=pl.col("Cell").n_unique(),
        y0=pl.col("Year").min(),
        y1=pl.col("Year").max(),
        types=pl.col("Type").n_unique(),
    ).collect()
    r = stats.row(0, named=True)
    log(
        f"rows={r['rows']:,}  cells={r['cells']:,}  "
        f"years={r['y0']}..{r['y1']}  distinct Type={r['types']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
