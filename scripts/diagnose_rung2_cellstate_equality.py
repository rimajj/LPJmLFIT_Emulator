#!/usr/bin/env python3
"""Decide whether a rung-2 replay arm diverged through RANDOMNESS or through
hidden CELL STATE (line M, ADR 0120 §5's open question).

The question this answers.  In the ``MODE=kills`` arm the tree roster at the end
of 2001 is identical to the recorded run in every initialised per-tree column,
and yet in 2002 the C's own hazard draw wants a different number of kills.  The
null control (``MODE=none``) rules out the rendezvous machinery, so the divergence
must come from something the per-tree records cannot carry.  There are exactly
three such channels, and the ``P`` record now dumps all three:

* ``seed``        — the per-cell RAND48 stream (``cell->seed``).  Every mortality
  Bernoulli draw, every inheritance index draw and every daily ``permute`` under
  ``-DPERMUTE`` advances it, so two runs that consume a DIFFERENT NUMBER of draws
  end up at different stream positions even with identical model state.
* ``gasdev_iset`` — the parity of ``gasdev()``'s process-global spare-deviate
  cache (src/numeric/gasdev.c).  Normal deviates are generated in pairs and the
  second is returned from a file-local static on the next call, so an odd number
  of intervening ``gasdev()`` calls shifts every later trait diffusion.  This is
  the one channel that is not even per-cell.
* ``sb_*`` / ``treelen``  — the rolling top-AGB seedbank ``cell->treelist``, which
  inheritance draws recruits from (``new_tree.c:130``) and which is rebuilt yearly.
  Only its LENGTH was dumped before, so a seedbank whose length matched but whose
  CONTENTS had moved was indistinguishable from agreement.

Reading the verdict:

* seeds diverge at or before the first differing demographic year  ⇒ RANDOMNESS:
  the stream moved, so the C is drawing different numbers from identical state.
  Walk back to the first year they differ and count draws there.
* seeds agree but a ``sb_*`` column differs                        ⇒ STATE: the
  seedbank moved, which changes which parent recruits inherit from.
* everything here agrees                                           ⇒ neither
  channel; the difference is in state this record still does not carry (soil,
  litter, climbuf) and the next probe has to widen, not deepen.

Exit status is 0 whether or not the dumps differ — this is a diagnostic, not a
gate; it exits non-zero only when it cannot answer (missing or unreadable dumps,
or a dump predating the ``P``-record columns).

    python3 diagnose_rung2_cellstate_equality.py --ref <recorded_dump> --new <arm_dump>
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

# Columns whose disagreement is the answer, in the order they are reported.
CHANNELS = [
    ("seed", "per-cell RAND48 stream position"),
    ("gasdev_iset", "gasdev() pair-cache parity (process-global)"),
    ("treelen", "seedbank length"),
    ("sb_agb", "seedbank content: sum of sapling AGB"),
    ("sb_trait", "seedbank content: sum of sapling traits"),
    ("sb_year", "seedbank content: sum of sapling creation years"),
    ("sb_id", "seedbank content: sum of sapling PFT ids"),
]
# Context columns: reported too, because they say WHEN the trajectories parted.
CONTEXT = [("ntree_alive", "live trees in the patch"), ("aprec", "annual precipitation")]


def load(path: str):
    """Read the P records of one dump file, keyed by (phase, year, patch)."""
    cols, recs = None, {}
    with open(path) as fh:
        for line in fh:
            if line.startswith("#H P "):
                cols = line.split()[2:]
                continue
            if line[0] != "P":
                continue
            if cols is None:
                sys.exit(f"FATAL: {path}: a P record before its '#H P' header")
            f = line.split()[1:]
            rec = dict(zip(cols, f))
            recs[(rec["phase"], int(rec["year"]), int(rec["patch"]))] = rec
    return cols, recs


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--ref", required=True, help="the RECORDED run's LPJ_RUNG2_DIR")
    ap.add_argument("--new", required=True, help="the replay arm's LPJ_RUNG2_DIR")
    args = ap.parse_args()

    a_files = sorted(glob.glob(os.path.join(args.ref, "roster_rank*.txt")))
    b_files = sorted(glob.glob(os.path.join(args.new, "roster_rank*.txt")))
    if not a_files or not b_files:
        print(f"FATAL: no roster_rank*.txt under --ref ({len(a_files)}) or --new ({len(b_files)})")
        return 2
    if [os.path.basename(p) for p in a_files] != [os.path.basename(p) for p in b_files]:
        print("FATAL: dump file sets differ")
        return 2

    cols_a, ref = load(a_files[0])
    cols_b, new = load(b_files[0])
    for extra in a_files[1:]:
        ref.update(load(extra)[1])
    for extra in b_files[1:]:
        new.update(load(extra)[1])

    missing = [c for c, _ in CHANNELS if c not in (cols_a or []) or c not in (cols_b or [])]
    if missing:
        print(f"FATAL: dump predates the P-record cell-state columns (missing {missing}).")
        print("       Re-record the baseline with the current binary:")
        print("       MODE=record TAG=<tag> bash scripts/run_rung2_replay_arm.sh")
        return 2

    # CHRONOLOGICAL order: within a patch-year `pre` happens before `post`, and
    # they sort the other way alphabetically.  Getting this backwards misreports
    # which phase the divergence starts in, which is the whole question here.
    phase_rank = {"pre": 0, "mort": 1, "post": 2}
    keys = sorted(set(ref) & set(new), key=lambda k: (k[1], k[2], phase_rank.get(k[0], 9)))
    only_ref, only_new = len(set(ref) - set(new)), len(set(new) - set(ref))
    print(f"P records: {len(ref)} recorded, {len(new)} arm, {len(keys)} shared")
    if only_ref or only_new:
        print(f"  (unmatched patch-years: {only_ref} recorded-only, {only_new} arm-only)")

    # First differing year per column, plus how many patch-years differ overall.
    first, count = {}, {}
    for key in keys:
        ra, rb = ref[key], new[key]
        for col, _ in CHANNELS + CONTEXT:
            if ra[col] != rb[col]:
                count[col] = count.get(col, 0) + 1
                if col not in first:
                    first[col] = (key, ra[col], rb[col])

    width = max(len(c) for c, _ in CHANNELS + CONTEXT)
    print("\n=== the three hidden channels ===")
    for col, what in CHANNELS:
        if col in first:
            (ph, yr, pa), va, vb = first[col]
            print(
                f"  {col:<{width}}  DIFFERS in {count[col]:4d}/{len(keys)} patch-years; "
                f"first at {yr} patch {pa} [{ph}]: {va} -> {vb}"
            )
        else:
            print(f"  {col:<{width}}  identical in all {len(keys)} patch-years    ({what})")

    print("\n=== context: when did the trajectories part? ===")
    for col, what in CONTEXT:
        if col in first:
            (ph, yr, pa), va, vb = first[col]
            print(
                f"  {col:<{width}}  DIFFERS in {count[col]:4d}/{len(keys)} patch-years; "
                f"first at {yr} patch {pa} [{ph}]: {va} -> {vb}    ({what})"
            )
        else:
            print(f"  {col:<{width}}  identical in all {len(keys)} patch-years    ({what})")

    # Per-year summary of the seed, because "the first patch-year that differs"
    # is the whole question and a per-year table shows whether it is one patch or
    # the whole cell from that year on.
    years = sorted({k[1] for k in keys})
    print("\n=== per-year: patch-years whose `pre` seed differs (of npatch) ===")
    for yr in years:
        pres = [k for k in keys if k[1] == yr and k[0] == "pre"]
        nd = sum(1 for k in pres if ref[k]["seed"] != new[k]["seed"])
        sb = sum(1 for k in pres if ref[k]["sb_agb"] != new[k]["sb_agb"])
        nt = sum(1 for k in pres if ref[k]["ntree_alive"] != new[k]["ntree_alive"])
        flag = "" if (nd or sb or nt) else "   (all agree)"
        print(f"  {yr}  seed {nd:3d}/{len(pres):3d}   seedbank {sb:3d}   ntree_alive {nt:3d}{flag}")

    # The patch-year the divergence STARTS in, in full, because "same state in,
    # different answer out" is only established if the `pre` of that patch-year
    # still agrees — and that is one record, not a summary statistic.
    if first:
        onset = min(
            (v[0] for v in first.values()),
            key=lambda k: (k[1], k[2], phase_rank.get(k[0], 9)),
        )
        oyear, opatch = onset[1], onset[2]
        print(f"\n=== onset: every P column at {oyear} patch {opatch}, both phases ===")
        for ph in ("pre", "post"):
            key = (ph, oyear, opatch)
            if key not in ref or key not in new:
                continue
            diffs = [c for c, _ in CHANNELS + CONTEXT if ref[key][c] != new[key][c]]
            state = "ALL AGREE" if not diffs else "differs in " + ", ".join(diffs)
            print(f"  [{ph:4s}] {state}")
            for col, _ in CHANNELS + CONTEXT:
                mark = " <-- " if ref[key][col] != new[key][col] else "     "
                print(f"        {col:<{width}}{mark}{ref[key][col]}  |  {new[key][col]}")

    seed_diff = "seed" in first
    sb_diff = any(c in first for c in ("sb_agb", "sb_trait", "sb_year", "sb_id", "treelen"))
    print("\nVERDICT:")
    if seed_diff:
        (ph, yr, pa), va, vb = first["seed"]
        print(
            f"  RANDOMNESS — the per-cell random stream diverges first at {yr} patch {pa}"
            f" [{ph}]. The two runs consumed a different NUMBER of draws before that"
            " point, so identical state does not imply identical decisions."
        )
        if sb_diff:
            print("  (the seedbank also moved; with the stream already shifted that is downstream)")
    elif sb_diff:
        print(
            "  STATE — the random stream agrees but the seedbank moved, so recruits"
            " inherit from a different parent pool."
        )
    elif "gasdev_iset" in first:
        print("  RANDOMNESS — only gasdev()'s process-global pair cache differs.")
    elif not first:
        print(
            f"  NO DIVERGENCE — all {len(keys)} patch-years agree in every cell-state"
            " column: the random stream, the seedbank and the live tree count. The arm"
            " reproduced the recorded run."
        )
    else:
        print(
            "  NEITHER channel differs. The divergence is in cell state this record"
            " still does not carry (soil, litter, climbuf) — widen the record, do not"
            " deepen this one."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
