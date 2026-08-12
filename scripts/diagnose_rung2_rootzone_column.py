#!/usr/bin/env python
"""Is the rung-2 roster dump's `rootzone_w` column the SAME quantity Component S was trained on?

The gate for the `rootzone_w` / `rootzone_whcs` columns the v6 demography hook adds to the `P`
record (`patches/lpjmlfit_rung2_hook_v6.patch`).  Those two columns exist for exactly one reason:
`soilmoist` is one of the four flux drivers in the count model's 15-column feature row
(`src/components/slow.jl::flux_feature_vector`) and it was the ONE feature no other record in the
dump could supply, so a rung-2 arm could not build a runtime-consistent row without it.

Why it needs a gate rather than a code review
---------------------------------------------
ADR 0035 is the story of this exact quantity being confused with a different one for a milestone:
the C's `swc` output is total water over SATURATION capacity while the model's `w` is
plant-available water over WHC, the two overlap numerically at Hainich (0.84-0.87 vs 0.79-1.00),
and an aggregation argument LOOKED like it explained the resulting train/inference gap.  So the
emitted column is not asserted to be right by reading the C -- it is checked against an
INDEPENDENT reader of an independent output.

What is compared
----------------
The C's own daily ``rootmoist`` output (``d_rootmoist.nc``) is
``ROOTMOIST = SUM_{l<3} w[l]*whcs[l]`` in mm (``update_daily.c:414``, ``forrootmoist`` = the top
1 m), written as the PATCH-ENSEMBLE MEAN.  The hook writes ``rootzone_w`` = that same sum divided
by ``SUM_{l<3} whcs[l]`` and ``rootzone_whcs`` = the divisor, PER PATCH.  So

    mean over patches of (rootzone_w * rootzone_whcs)   ==   rootmoist at the year-end day

must hold at every year, and the residual should sit at the float32 precision of the NetCDF output
(~6e-8 relative), not merely "close".  Both halves are emitted rather than only the ratio so this
check can be made at all -- a ratio alone cannot be compared against an absolute mm output.

The `grow` phase is the one to read: it is dumped after the year's daily loop, which is the
year-end instant the training column takes (`scripts/build_rootmoist_soilmoist_feature.py` slices
`YEAR_END_DOY0`).  Reading `pre` instead compares against the wrong day.

Usage::

    python scripts/diagnose_rung2_rootzone_column.py \
        --run  /p/tmp/jamirp/esm_land_daily/daily_2000_2019_historic_S_rung2rec_v6_c42490_seed1/\
               output \
        --dump /p/tmp/jamirp/M_rung2/S_rung2rec_v6_dump

Exit status: 0 = agrees within --tol at every year; 1 = a mismatch; 2 = inputs unusable (no
`rootzone_w` column, no `grow` phase, year count mismatch) so nothing can be concluded.
"""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

import netCDF4  # type: ignore
import numpy as np

NDAYYEAR = 365          # the model calendar is noleap
YEAR_END_DOY0 = 364     # the same 0-based year-end slice build_rootmoist_soilmoist_feature.py takes
NROOTLAYER = 3          # forrootmoist = the top 1 m (include/soil.h:353)


def read_hook_column(dump: Path) -> dict[int, list[float]]:
    """Per-year list of per-patch `rootzone_w * rootzone_whcs` (mm) off the `grow` phase.

    Schema comes from the file's own `#H P` header line, never from a hard-coded column order --
    the same rule the sibling rung-2 readers follow, so adding a column upstream cannot silently
    shift this one.
    """
    per_year: dict[int, list[float]] = collections.defaultdict(list)
    cols: dict[str, int] = {}
    for path in sorted(dump.glob("roster_rank*.txt")):
        with open(path) as fh:
            for line in fh:
                if line.startswith("#H P "):
                    cols = {n: i for i, n in enumerate(line.split()[2:])}
                    continue
                if not line.startswith("P "):
                    continue
                if not cols:
                    raise SystemExit(f"FATAL: {path}: a P record before its '#H P' header")
                for need in ("rootzone_w", "rootzone_whcs", "phase", "year"):
                    if need not in cols:
                        raise SystemExit(
                            f"FATAL: {path} has no '{need}' column. This dump predates the v6 hook "
                            "(patches/lpjmlfit_rung2_hook_v6.patch); re-record it with MODE=record."
                        )
                f = line.split()[1:]
                if f[cols["phase"]] != "grow":
                    continue
                w = float(f[cols["rootzone_w"]])
                cap = float(f[cols["rootzone_whcs"]])
                per_year[int(f[cols["year"]])].append(w * cap)
    return per_year


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", required=True, type=Path, help="run output dir with d_rootmoist.nc")
    ap.add_argument("--dump", required=True, type=Path, help="LPJ_RUNG2_DIR of the same run")
    ap.add_argument("--tol", type=float, default=1e-6,
                    help="max allowed relative difference (default 1e-6; the float32 output "
                         "precision floor is ~6e-8, so this is 16x the floor)")
    a = ap.parse_args(argv)

    rmpath = a.run / "d_rootmoist.nc"
    if not rmpath.is_file():
        print(f"FATAL: no {rmpath} -- the run must emit daily rootmoist", file=sys.stderr)
        return 2
    with netCDF4.Dataset(rmpath) as ds:
        rm = np.asarray(ds.variables["rootmoist"][:]).reshape(-1).astype(np.float64)
    if rm.size % NDAYYEAR:
        print(f"FATAL: d_rootmoist has {rm.size} days, not a whole number of {NDAYYEAR}-day years",
              file=sys.stderr)
        return 2
    nyear_nc = rm.size // NDAYYEAR
    year_end = rm.reshape(nyear_nc, NDAYYEAR)[:, YEAR_END_DOY0]

    per_year = read_hook_column(a.dump)
    if not per_year:
        print(f"FATAL: no `grow`-phase P records under {a.dump} -- a dump without the `grow` phase "
              "predates ADR 0123 and cannot be a reference basis", file=sys.stderr)
        return 2
    years = sorted(per_year)
    if len(years) != nyear_nc:
        print(f"FATAL: dump covers {len(years)} years, d_rootmoist covers {nyear_nc} -- these are "
              "not the same run", file=sys.stderr)
        return 2

    hook = np.array([float(np.mean(per_year[y])) for y in years])
    npatch = {len(per_year[y]) for y in years}
    rel = np.abs(hook - year_end) / np.where(year_end != 0.0, year_end, np.nan)

    print(f"run  = {a.run}")
    print(f"dump = {a.dump}")
    print(f"{len(years)} years x {sorted(npatch)} patches; comparing the patch-ensemble mean of "
          "rootzone_w*rootzone_whcs against the C's own d_rootmoist at the year-end day\n")
    print(f"{'year':>6} {'C rootmoist (mm)':>18} {'hook (mm)':>18} {'rel diff':>11}")
    for i, y in enumerate(years):
        print(f"{y:>6} {year_end[i]:>18.9f} {hook[i]:>18.9f} {rel[i]:>11.2e}")

    worst = float(np.nanmax(rel))
    print(f"\nmax rel diff = {worst:.3e}   median = {float(np.nanmedian(rel)):.3e}   "
          f"tol = {a.tol:.1e}")
    if not np.isfinite(worst) or worst > a.tol:
        print("VERDICT: MISMATCH -- the emitted column is NOT the training quantity. Do not "
              "build a feature row from it.", file=sys.stderr)
        return 1
    print("VERDICT: the dump's rootzone column reproduces the C's own rootmoist output. It is the "
          "`soilmoist` training quantity (ADR 0035), on the per-patch basis stated in the hook.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
