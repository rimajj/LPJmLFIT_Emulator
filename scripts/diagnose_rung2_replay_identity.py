#!/usr/bin/env python3
"""Score a rung-2 replay arm against the run it replays (line M).

The question this answers is NOT "is the emulator good" — it is the prior one:
**when LPJmL-FIT is handed its own recorded demography back through the
substitution hook, how closely does it re-walk its own trajectory?**  Whatever
that gap is, no later rung-2 arm can be credited with a difference smaller than
it.  It is the harness's own noise floor.

Run the three arms of ``run_rung2_replay_arm.sh`` (kills / recruits / both) and
score each here.  The arms are what make a gap attributable: the substituted
recruit path does its own ``addpft`` trait draws instead of the C's Poisson plus
inheritance draws, so it moves the per-cell RAND48 stream, which perturbs every
later mortality draw.  The kills-only arm leaves that stream alone.

Reported per year:
  n_ref / n_new     live trees in the reference vs replay `post` roster
  shared            (pft_id, treeidx) keys present in both
  kill_applied      kills the C actually applied, from the arm's audit file
  forced            "live" verdicts the C overrode because its own state could
                    not carry the tree (negative/exhausted pools, bioclimatic)

    python3 diagnose_rung2_replay_identity.py --ref <recorded LPJ_RUNG2_DIR> \
                                              --new <arm LPJ_RUNG2_DIR> \
                                              [--audit <arm apply dir>]
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from collections import defaultdict


def load_post(dump_dir: str):
    """{year: {(pft_id, treeidx): row}} for the alive trees of each `post` roster."""
    files = sorted(glob.glob(os.path.join(dump_dir, "roster_rank*.txt")))
    if not files:
        sys.exit(f"FATAL: no roster_rank*.txt under {dump_dir}")
    out: dict[int, dict] = defaultdict(dict)
    cols = None
    for path in files:
        with open(path) as fh:
            for line in fh:
                if line.startswith("#H T "):
                    cols = line.split()[2:]
                    continue
                if line[0] != "T":
                    continue
                rec = dict(zip(cols, line.split()[1:]))
                if rec["phase"] != "post" or int(rec["isdead"]):
                    continue
                out[int(rec["year"])][(int(rec["pft_id"]), int(rec["treeidx"]))] = rec
    return out


def load_audit(apply_dir: str):
    """{year: (kill_applied, forced_dead, spared_certain)} summed over patches."""
    files = sorted(glob.glob(os.path.join(apply_dir, "audit_r*.txt")))
    agg: dict[int, list[int]] = defaultdict(lambda: [0, 0, 0])
    cols = None
    for path in files:
        with open(path) as fh:
            for line in fh:
                if line.startswith("#H A "):
                    cols = line.split()[2:]
                    continue
                if line[0] != "A":
                    continue
                rec = dict(zip(cols, line.split()[1:]))
                y = int(rec["year"])
                agg[y][0] += int(rec["n_kill_applied"])
                agg[y][1] += int(rec["n_forced_dead"])
                agg[y][2] += int(rec["n_spared_certain"])
    return agg


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ref", required=True, help="LPJ_RUNG2_DIR of the recorded run")
    ap.add_argument("--new", required=True, help="LPJ_RUNG2_DIR of the replay arm")
    ap.add_argument("--audit", default=None, help="LPJ_RUNG2_APPLY_DIR of the arm (for the audit counters)")
    ap.add_argument("--label", default="", help="arm label for the header line")
    args = ap.parse_args()

    ref, new = load_post(args.ref), load_post(args.new)
    audit = load_audit(args.audit) if args.audit else {}
    years = sorted(set(ref) | set(new))

    print(f"=== rung-2 replay identity {args.label}".rstrip() + " ===")
    print(f"{'year':>5} {'n_ref':>6} {'n_new':>6} {'d':>5} {'shared':>7} {'ref_only':>8} "
          f"{'new_only':>8} {'kill_app':>8} {'forced':>6}")
    first_diff = None
    for y in years:
        a, b = ref.get(y, {}), new.get(y, {})
        ka, kb = set(a), set(b)
        shared = len(ka & kb)
        au = audit.get(y, [0, 0, 0])
        print(f"{y:5d} {len(ka):6d} {len(kb):6d} {len(kb)-len(ka):+5d} {shared:7d} "
              f"{len(ka-kb):8d} {len(kb-ka):8d} {au[0]:8d} {au[1]:6d}")
        if first_diff is None and ka != kb:
            first_diff = y

    n0, n1 = len(ref.get(years[0], {})), len(new.get(years[0], {}))
    print()
    print(f"first year ({years[0]}): {n0} vs {n1} trees, "
          f"{'IDENTICAL roster' if ref.get(years[0]) and set(ref[years[0]]) == set(new.get(years[0], {})) else 'ROSTERS DIFFER'}")
    print(f"first year whose live roster differs: {first_diff if first_diff is not None else 'none'}")
    ly = years[-1]
    la, lb = len(ref.get(ly, {})), len(new.get(ly, {}))
    if la:
        print(f"terminal ({ly}): replay/recorded = {lb/la:.3f}  ({lb} vs {la} trees)")
    tot_forced = sum(v[1] for v in audit.values())
    tot_spared = sum(v[2] for v in audit.values())
    if audit:
        print(f"C overrode a 'live' verdict {tot_forced} time(s); "
              f"{tot_spared} tree(s) spared that the C had at hazard 1.0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
