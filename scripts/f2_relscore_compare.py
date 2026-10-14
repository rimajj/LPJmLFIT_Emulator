#!/usr/bin/env python3
"""Pairwise comparison of learned-daily-model ensembles from the output of f2_relative_score.py.

Usage: python scripts/f2_relative_score.py A B C ... > out.md
       python scripts/f2_relscore_compare.py out.md REF CAND [CAND ...] [--exclude=leg1,leg2]

For each candidate against REF, on the legs both were scored on (free runs only): the ratio CAND / REF of the
typical (30-yr p50) error per leg and flux, early and late window; the median and the worst of those ratios over
legs (GPP / NPP / ET / runoff, early and late pooled, as ADR 0335 §2 counts them); and both runs' raw typical
errors and drift per leg. --exclude drops legs from the comparison (e.g. the two legs arm D added to training, to
count "the 12 legs shared with arm W" as ADR 0335 §2 does). This is the arithmetic every arm verdict of ADR 0328-0336 needed by hand.
"""

import re
import statistics
import sys

FLUX = ("gpp", "npp", "et", "runoff")


def parse(path):
    runs, tag = {}, None
    for line in open(path):
        m = re.match(r"^## (\S+)", line)
        if m:
            tag = m.group(1)
            runs[tag] = {}
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if tag is None or len(c) < 8 or c[2] != "free":
            continue
        try:
            early, late = (float(x) for x in c[3].split("/"))
            drift = float(c[7])
        except ValueError:
            continue
        runs[tag][(c[0], c[1])] = (early, late, drift)
    return runs


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--exclude=")]
    excl = {x for a in sys.argv[1:] if a.startswith("--exclude=") for x in a[10:].split(",") if x}
    path, ref, *cands = args
    runs = parse(path)
    R = runs[ref]
    for cand in cands:
        C = runs[cand]
        legs = sorted(({leg for leg, _ in R} & {leg for leg, _ in C}) - excl)
        print(f"\n### {cand} vs {ref}  ({len(legs)} shared legs; ratio = {cand} / {ref} typical error)\n")
        print("| leg | flux | ref early/late | cand early/late | ratio early/late | drift ref -> cand |")
        print("|---|---|---|---|---|---|")
        pooled = {f: [] for f in FLUX}
        for leg in legs:
            for f in FLUX:
                if (leg, f) not in R or (leg, f) not in C:
                    continue
                (re_, rl, rd), (ce, cl, cd) = R[(leg, f)], C[(leg, f)]
                q = (ce / re_, cl / rl)
                pooled[f] += [(q[0], leg, "early"), (q[1], leg, "late")]
                print(
                    f"| {leg} | {f} | {re_:.2f}/{rl:.2f} | {ce:.2f}/{cl:.2f} | {q[0]:.3f}/{q[1]:.3f} "
                    f"| {rd:.2f} -> {cd:.2f} |"
                )
        print("\n| flux | median ratio | worst ratio (leg, window) | best ratio |")
        print("|---|---|---|---|")
        for f in FLUX:
            v = pooled[f]
            if not v:
                continue
            w, b = max(v), min(v)
            med = statistics.median(x[0] for x in v)
            print(f"| {f} | {med:.3f} | {w[0]:.3f} ({w[1]}, {w[2]}) | {b[0]:.3f} ({b[1]}, {b[2]}) |")


if __name__ == "__main__":
    main()
