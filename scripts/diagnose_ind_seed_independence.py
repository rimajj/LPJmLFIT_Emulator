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
        --log-dir   <new> \
        --expect-cells 67420 --expect-last-year 2100

Use ``--log-dir <run_dir>``, not ``--log <...>.<jobid>.out``: a jcf that pins a parent's job id
into the log path is **not resubmit-safe**, and the failure is silent-looking. When the hung ssp370
seed2 member was resubmitted, its chained gate kept reading the *cancelled* attempt's 0-byte log and
reported ``no completion line at all`` for a run that had in fact finished cleanly (ADR 0043).
``--log-dir`` resolves the newest NON-EMPTY ``lpjml_*.out`` instead, and an empty log is now a
distinct FATAL (exit 2) rather than a gate failure.
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
    ap.add_argument(
        "--log-dir",
        type=Path,
        default=None,
        help=(
            "the run directory; resolve the newest NON-EMPTY lpjml_*.out inside it. "
            "PREFER THIS over --log: a jcf that hardcodes a parent's job id in the log path is "
            "not resubmit-safe (see ADR 0043)."
        ),
    )
    ap.add_argument("--expect-cells", type=int, default=67420)
    ap.add_argument("--expect-last-year", type=int, default=None)
    args = ap.parse_args()

    fails: list[str] = []

    for p in (args.candidate, args.sibling):
        if not p.is_file():
            print(f"FATAL: missing {p}")
            return 2

    # Resolve the log. --log-dir is the resubmit-safe form: it picks the newest log that has
    # actual content, so a cancelled attempt's 0-byte corpse can never be judged in place of the
    # run that succeeded (ADR 0043 — this exact stale-job-id path made a passing member FAIL).
    log = args.log
    if args.log_dir is not None:
        if args.log is not None:
            print("FATAL: pass --log OR --log-dir, not both")
            return 2
        if not args.log_dir.is_dir():
            print(f"FATAL: --log-dir is not a directory: {args.log_dir}")
            return 2
        cands = [p for p in sorted(args.log_dir.glob("lpjml_*.out")) if p.stat().st_size > 0]
        if not cands:
            empties = sorted(args.log_dir.glob("lpjml_*.out"))
            print(
                f"FATAL: no non-empty lpjml_*.out in {args.log_dir} "
                f"({len(empties)} empty candidate(s): {[p.name for p in empties]})"
            )
            return 2
        log = max(cands, key=lambda p: p.stat().st_mtime)
        print(f"INFO  resolved log -> {log.name} ({log.stat().st_size:,} B, newest non-empty)")
        if len(cands) > 1:
            print(f"      ({len(cands)} non-empty candidates; ignored {len(cands) - 1} older)")

    # 1) completion, from the log rather than from SLURM state
    if log is not None:
        if not log.is_file():
            fails.append(f"log not found: {log}")
        elif log.stat().st_size == 0:
            # A 0-byte log is a PROVENANCE error, not a physics verdict: it is what a cancelled or
            # hung attempt leaves behind, and it is indistinguishable from "the run never finished"
            # unless it is called out separately. Do not let it read as a failed gate.
            print(f"FATAL: log is EMPTY (0 B): {log}")
            print(
                "       This is the stale-job-id trap (ADR 0043): a resubmitted run writes to a\n"
                "       NEW lpjml_<jobid>.out, so a jcf pinning the old id reads the cancelled\n"
                "       attempt's corpse. Re-run with --log-dir <run_dir> to resolve it safely."
            )
            return 2
        else:
            txt = log.read_text(errors="replace")
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
