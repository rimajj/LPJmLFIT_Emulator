#!/usr/bin/env python3
"""Compare two rung-2 roster dumps column by column (line M, ADR 0061).

Use it after ANY change to the observation hook's writer, or after a C rebuild,
to show that the dump still reports the same model state.  A whole-file `cmp` is
the wrong test here for the same reason it is wrong on a NetCDF (ADR 0043): the
dump carries columns that are **uninitialised memory by construction**, and those
legitimately differ between two builds of identical physics.

Two such column groups exist, and both are traps for anything consuming the dump:

* ``sapwood_old`` — a DEAD struct field.  ``Pfttree.sapwood_old`` is declared
  (include/tree.h) and is never written or read anywhere in LPJmL-FIT, and
  ``new_tree`` does not zero it.  Its column is garbage at BOTH phases, in every
  year.  Never read it.
* ``mort_prob`` / ``mort_npp`` / ``mort_age`` / ``mort_water`` / ``mort_temp`` —
  written only by ``mortality_tree_ind``, so they are garbage for any tree that
  has not been through it yet.  That is every tree at the first ``pre`` after a
  restart (already known) **and every recruit at the ``post`` of its own
  establishment year** (they are added by ``establishmentpft_ind``, which runs
  after mortality, and ``new_tree`` does not zero them).  So "valid at post" is
  true only for trees that were already alive that year.

Note what this means for the observation gate that compares the dump against the
run's own ``ind`` table: both readers read the SAME struct memory, so they agree
on the garbage too.  A consistency check between two readers of one buffer cannot
detect uninitialised memory — only a comparison of two independent RUNS can.

Exit status: 0 = equal outside the uninitialised columns, 1 = a real difference.

    python3 diagnose_rung2_dump_equality.py --ref <dirA> --new <dirB>
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from collections import defaultdict

UNINIT = {"sapwood_old", "mort_prob", "mort_npp", "mort_age", "mort_water", "mort_temp"}


def load(path: str):
    cols, rows = None, []
    with open(path) as fh:
        for line in fh:
            if line.startswith("#H T "):
                cols = line.split()[2:]
                continue
            if line[0] != "T":
                continue
            rows.append(line.split()[1:])
    return cols, rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ref", required=True, help="reference LPJ_RUNG2_DIR")
    ap.add_argument("--new", required=True, help="new LPJ_RUNG2_DIR")
    args = ap.parse_args()

    a_files = sorted(glob.glob(os.path.join(args.ref, "roster_rank*.txt")))
    b_files = sorted(glob.glob(os.path.join(args.new, "roster_rank*.txt")))
    if not a_files or [os.path.basename(p) for p in a_files] != [os.path.basename(p) for p in b_files]:
        print(f"FAIL: dump file sets differ ({len(a_files)} vs {len(b_files)})")
        return 1

    real, uninit = defaultdict(int), defaultdict(int)
    total_rows = 0
    for fa, fb in zip(a_files, b_files):
        ca, ra = load(fa)
        cb, rb = load(fb)
        if ca != cb:
            print(f"FAIL: {os.path.basename(fa)}: column schema differs")
            return 1
        if len(ra) != len(rb):
            print(f"FAIL: {os.path.basename(fa)}: {len(ra)} vs {len(rb)} tree records")
            return 1
        total_rows += len(ra)
        pi = ca.index("phase")
        for x, y in zip(ra, rb):
            if x == y:
                continue
            for i, (u, v) in enumerate(zip(x, y)):
                if u != v:
                    (uninit if ca[i] in UNINIT else real)[(x[pi], ca[i])] += 1

    print(f"compared {total_rows} tree records over {len(a_files)} dump file(s)")
    if uninit:
        print("\ndifferences in the UNINITIALISED columns (expected, not a defect):")
        for (ph, c), n in sorted(uninit.items(), key=lambda kv: -kv[1]):
            print(f"  [{ph:4s}] {c:12s} {n:7d} record(s)")
    if real:
        print("\nDIFFERENCES IN REAL MODEL STATE:")
        for (ph, c), n in sorted(real.items(), key=lambda kv: -kv[1]):
            print(f"  [{ph:4s}] {c:12s} {n:7d} record(s)")
        print("\nVERDICT: the two dumps report DIFFERENT model state.")
        return 1
    print("\nVERDICT: identical in every initialised column.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
