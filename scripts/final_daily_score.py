#!/usr/bin/env python3
"""final_daily_score.py -- the daily-flux numbers proposed in ADR 0325 sec. 3, read off the output of
scripts/f2_relative_score.py for one run (default PD_B = the deployment daily model fed the EMULATED stand, i.e. the
whole learned emulator; ADR 0337), per flux over the 13 climate-model legs (the observed-climate control is left out:
the stand there is the original's).

  L1  typical-cell error of 30-yr means (both windows)     <= 3x a second run
  L2  worst-10 % cells (both windows)                      <= 3x
  L3  climate response (late - early), typical cell        <= 1.5x
  T   area totals                                          within 5 %
  D   drift: single-year typical ratio 2081-2100 / 2021-2040 <= 1.2
Usage: python scripts/f2_relative_score.py PD_B > x.md ; python scripts/final_daily_score.py x.md [TAG]
"""

import re
import statistics
import sys

LIM = {"L1": 3.0, "L2": 3.0, "L3": 1.5, "T": 0.05, "D": 1.2}


def main():
    path, tag = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "PD_B")
    rows, cur = [], None
    for line in open(path):
        m = re.match(r"^## (\S+)", line)
        if m:
            cur = m.group(1)
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if cur != tag or len(c) < 10 or c[2] != "free" or c[0] == "ctl_obs":
            continue
        e, la = (float(x) for x in c[3].split("/"))
        p9e, p9l = (float(x) for x in c[4].split("/"))
        r50 = float(c[5].split("/")[0])
        tot = float(c[8].split()[0])
        rows.append(dict(leg=c[0], flux=c[1], L1=max(e, la), L2=max(p9e, p9l), L3=r50, T=tot, D=float(c[7])))
    print(f"{tag}: {len({r['leg'] for r in rows})} legs; a value passes at <= its limit; median and legs passing")
    print("| flux | " + " | ".join(f"{k} (<= {v})" for k, v in LIM.items()) + " |")
    print("|---|" + "---|" * len(LIM))
    for fl in ("gpp", "npp", "et", "runoff"):
        rs = [r for r in rows if r["flux"] == fl]
        cells = []
        for k, lim in LIM.items():
            v = [r[k] for r in rs]
            ok = sum(x <= lim for x in v)
            cells.append(f"{statistics.median(v):.2f} ({ok}/{len(v)}; worst {max(v):.2f})")
        print(f"| {fl} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
