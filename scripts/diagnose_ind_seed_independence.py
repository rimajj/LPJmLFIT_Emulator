#!/usr/bin/env python
"""Is a freshly produced ``ind_*.csv`` ground-truth member actually an INDEPENDENT stochastic
realization of its sibling, or a silent byte-copy?

This exists because the first attempt at an ssp370 second seed *was* a byte-copy and nothing
complained: `random_seed` is inert under `-DFROM_RESTART` (`new_seed:false` restores the RAND48
state from the restart file), the log prints `Reading random seeds from restart file.` rather
than `Random seed: N`, and a floor built from the result reports r ≡ 1 — fabricated headroom
with no error anywhere. Run this before converting a new member to parquet.

Checks, in order (all must pass):

1. the run log reports ``lpjml successfully terminated, <ncell> grid cells processed.``
   — SLURM state is NOT sufficient: the stock job file ended with ``rc=0; exit``, so a run that
   died mid-century still showed COMPLETED 0:0 behind a plausible truncated CSV;
2. the candidate reaches the expected final year;
3. its size DIFFERS from the sibling's (equal size is the copy signature);
4. sampled MB-sized windows differ from the sibling's at every offset.

Usage::

    scripts/sbatch_python.sh S-indep scripts/diagnose_ind_seed_independence.py \
        --candidate <new>/output/ind_2020_2100.csv \
        --sibling   <seed1>/output/ind_2020_2100.csv \
        --log       <new>/lpjml_2020_2100.<jobid>.out \
        --expect-cells 67420 --expect-last-year 2100
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

WINDOW = 1 << 20  # 1 MiB


def sample_offsets(size: int, n: int = 6) -> list[int]:
    """Offsets spread through the file, all leaving room for a full window."""
    fracs = [0.0, 1 / 7, 1 / 3, 1 / 2, 2 / 3, 0.95][:n]
    last = max(0, size - WINDOW)
    return sorted({min(int(size * f), last) for f in fracs})


def window_md5(path: Path, off: int) -> str:
    with path.open("rb") as fh:
        fh.seek(off)
        return hashlib.md5(fh.read(WINDOW)).hexdigest()


def tail_last_year(path: Path, tail_bytes: int = 1 << 20) -> int | None:
    """Largest integer in the first CSV field within the last chunk of the file."""
    size = path.stat().st_size
    with path.open("rb") as fh:
        fh.seek(max(0, size - tail_bytes))
        chunk = fh.read(tail_bytes).decode("utf-8", "replace")
    years = [int(m) for m in re.findall(r"(?m)^\s*(\d{4})[,\s]", chunk)]
    return max(years) if years else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--sibling", type=Path, required=True)
    ap.add_argument("--log", type=Path, default=None, help="the C run's stdout log")
    ap.add_argument("--expect-cells", type=int, default=67420)
    ap.add_argument("--expect-last-year", type=int, default=None)
    args = ap.parse_args()

    fails: list[str] = []

    for p in (args.candidate, args.sibling):
        if not p.is_file():
            print(f"FATAL: missing {p}")
            return 2

    # 1) completion, from the log rather than from SLURM state
    if args.log is not None:
        if not args.log.is_file():
            fails.append(f"log not found: {args.log}")
        else:
            txt = args.log.read_text(errors="replace")
            want = f"lpjml successfully terminated, {args.expect_cells} grid cells processed."
            if want in txt:
                print(f"PASS  completion: '{want}'")
            else:
                m = re.search(r"lpjml successfully terminated, (\d+) grid cells processed\.", txt)
                fails.append(
                    f"log does not report {args.expect_cells} cells "
                    f"(found: {m.group(1) if m else 'no completion line at all'})"
                )
    else:
        print("SKIP  completion check (no --log given)")

    # 2) final year
    if args.expect_last_year is not None:
        ly = tail_last_year(args.candidate)
        if ly == args.expect_last_year:
            print(f"PASS  final year = {ly}")
        else:
            fails.append(f"final year in candidate tail is {ly}, expected {args.expect_last_year}")

    # 3) size must differ
    sc, ss = args.candidate.stat().st_size, args.sibling.stat().st_size
    print(f"      candidate {sc:,} B   sibling {ss:,} B   delta {sc - ss:+,} B")
    if sc == ss:
        fails.append(
            f"candidate and sibling are the SAME SIZE ({sc:,} B) — this is the byte-copy "
            "signature of an inert random_seed; check restart_filename"
        )
    else:
        print(f"PASS  sizes differ by {abs(sc - ss) / ss * 100:.4f}%")

    # 4) sampled content must differ everywhere
    offs = sample_offsets(min(sc, ss))
    same = []
    for off in offs:
        a, b = window_md5(args.candidate, off), window_md5(args.sibling, off)
        tag = "SAME" if a == b else "diff"
        print(f"      window @{off:>15,}  {tag}  {a[:12]} vs {b[:12]}")
        if a == b:
            same.append(off)
    if same:
        fails.append(
            f"{len(same)}/{len(offs)} sampled windows are IDENTICAL "
            f"to the sibling at offsets {same}"
        )
    else:
        print(f"PASS  all {len(offs)} sampled windows differ")

    print()
    if fails:
        print("=" * 72)
        print("INDEPENDENCE CHECK FAILED:")
        for f in fails:
            print(f"  - {f}")
        print("=" * 72)
        return 1
    print("=" * 72)
    print("INDEPENDENCE CHECK PASSED — this is a genuine second realization.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
