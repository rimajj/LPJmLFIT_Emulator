#!/usr/bin/env python3
"""f2_stand_attribution.py -- which stand input carries the emulated stand's added error (ADR 0338).

Usage: python scripts/f2_relative_score.py PD_A PD_B PD_L PD_V PD_C > score.md
       python scripts/f2_stand_attribution.py score.md [A=PD_A] [B=PD_B] [ARMS=PD_L,PD_V,PD_C]

Per leg x flux x window (typical-cell 30-yr error, free runs, ctl_obs excluded): the share of the
full increment carried by arm X, s_X = (X/A - 1) / (B/A - 1), only where B/A - 1 >= 0.10; per flux
the median share of each arm, the median of their sum (1 = additive), and the count of values. Also
each arm's median X/A per flux.
"""

import statistics
import sys

from f2_relscore_compare import FLUX, parse


def main():
    path = sys.argv[1]
    kw = dict(a.split("=", 1) for a in sys.argv[2:])
    A, B = kw.get("A", "PD_A"), kw.get("B", "PD_B")
    arms = kw.get("ARMS", "PD_L,PD_V,PD_C").split(",")
    runs = parse(path)
    arms = [x for x in arms if x in runs]
    legs = sorted({k[0] for k in runs[B] if k[0] != "ctl_obs"})
    print(f"### stand attribution: {', '.join(arms)} against {A} (all original) and {B} (all from"
          f" the map)\n")
    print("| flux | values (B/A-1 >= 0.10) | " + " | ".join(f"median share {x}" for x in arms)
          + " | median sum | " + " | ".join(f"median {x}/A" for x in arms) + " | median B/A |")
    print("|---|---|" + "---|" * (2 * len(arms) + 2))
    for f in FLUX:
        sh = {x: [] for x in arms}
        sums, ratio = [], {x: [] for x in arms}
        rb = []
        for lg in legs:
            for i in (0, 1):
                a, b = runs[A][(lg, f)][i], runs[B][(lg, f)][i]
                rb.append(b / a)
                for x in arms:
                    ratio[x].append(runs[x][(lg, f)][i] / a)
                if b / a - 1 < 0.10:
                    continue
                s = [(runs[x][(lg, f)][i] / a - 1) / (b / a - 1) for x in arms]
                for x, v in zip(arms, s, strict=True):
                    sh[x].append(v)
                sums.append(sum(s))
        n = len(sums)
        med = [f"{statistics.median(sh[x]):.2f}" if n else "-" for x in arms]
        row = (f"| {f} | {n} | " + " | ".join(med) + f" | {statistics.median(sums):.2f} | " if n
               else f"| {f} | 0 | " + " | ".join("-" for _ in arms) + " | - | ")
        print(row, end="")
        print(" | ".join(f"{statistics.median(ratio[x]):.3f}" for x in arms)
              + f" | {statistics.median(rb):.3f} |")


if __name__ == "__main__":
    main()
