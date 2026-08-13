#!/usr/bin/env python
"""
check_rung2_campaign_coverage — which legs of a rung-2 arm campaign actually finished, and the exact
commands to re-run the ones that did not. Seconds, no dump scan.

WHY THIS EXISTS. A rung-2 arm campaign is a few hundred one-task jobs and its failures are SILENT in
every place you would normally look:

* the SLURM job always exits with the C's return code, and a dead rendezvous still returns 0 in some
  paths, so `sacct` is not evidence (CLAUDE.md §3: never judge a C run from SLURM state);
* a truncated dump looks exactly like a short one to any reader taking `max(year)` as terminal;
* and the harness's own `harness: served <N> patch-years` line is written by the FAILURE path, not
  the success path — the job file kills the harness once `lpjml` returns, so a HEALTHY run never
  prints it at all. Reading "no served line" as a failure inverts the test.

So the one trustworthy signal is the C's own completion line, which is exactly what
`diagnose_rung2_response.run_completed` checks — imported here rather than re-implemented.

WHAT IT REPORTS, per (scenario, cell, arm, seed):
    OK       the C printed `lpjml successfully terminated` AND the arm log covers every patch-year
    SHORT    completed, but the arm log is missing patch-years (the harness gave up mid-leg — raise
             MAXIDLE; it must exceed the C's own LPJ_RUNG2_APPLY_TIMEOUT of 600 s)
    DEAD     no completion line (crash, cancellation, ERROR043, or still running)
    MISSING  no run directory at all — never submitted
`REC` is checked on its dump instead, because it runs no harness and writes no arm log.

Env
    ARMS      comma or space list        (default "G0 G0h G1")
    CELLS     comma list                (default ADR 0187's 12 scoreable cells)
    SEEDS     comma list                (default 1,2,3,4,5)
    SCENS     comma or space list       (default "historic ssp370")
    NPREV     roster | predict          (default predict)
    RESUBMIT  1 to print the re-run commands for every non-OK leg (default 1)

Usage
    /home/jamirp/.conda/envs/py311_new/bin/python scripts/check_rung2_campaign_coverage.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from diagnose_rung2_map_target_response import (  # noqa: E402
    LEG,
    NPATCH,
    ROOT,
    _split_arms,
)
from diagnose_rung2_response import run_completed  # noqa: E402

ARMS = _split_arms(os.environ.get("ARMS", "G0 G0h G1"))
SCENS = _split_arms(os.environ.get("SCENS", "historic ssp370"))
SEEDS = [int(x) for x in _split_arms(os.environ.get("SEEDS", "1,2,3,4,5"))]
#: ADR 0187's scoreable set — the 12 cells whose `REC` baseline is complete in BOTH legs.
DEFAULT_CELLS = (12045, 12235, 18371, 22732, 22990, 32628, 42490, 42757, 42973, 44048, 52059, 57087)
CELLS = [int(x) for x in _split_arms(os.environ["CELLS"])] if os.environ.get("CELLS") \
    else list(DEFAULT_CELLS)
NPREV = os.environ.get("NPREV", "predict")
RESUBMIT = os.environ.get("RESUBMIT", "1") == "1"


def armlog_patchyears(scen: str, cell: int, arm: str, seed: int) -> int:
    """Patch-years in the arm's own log, or -1 if there is no log (REC, or never started)."""
    p = os.path.join(
        ROOT, f"S_r2s_{scen}_c{cell}_{arm}_{NPREV}_s{seed}_apply", "s_arm_log.txt"
    )
    if not os.path.isfile(p):
        return -1
    n = 0
    with open(p) as fh:
        for line in fh:
            if line.startswith("L "):
                n += 1
    return n


def rundir(scen: str, cell: int, arm: str, seed: int) -> str:
    y0, y1 = LEG[scen]
    tag = f"S_r2s_{scen}_c{cell}_{arm}_{NPREV}_s{seed}"
    return os.path.join(
        "/p/tmp/jamirp/esm_land_daily", f"daily_{y0}_{y1}_{scen}_{tag}_c{cell}_seed1"
    )


def main() -> int:
    print("=" * 96)
    print("  RUNG-2 CAMPAIGN COVERAGE")
    print(f"  mode NPREV={NPREV}  arms={ARMS}  seeds={SEEDS}  cells={len(CELLS)}  scens={SCENS}")
    print("=" * 96)
    tally = dict.fromkeys(("OK", "SHORT", "DEAD", "MISSING"), 0)
    bad = []
    for scen in SCENS:
        y0, y1 = LEG[scen]
        want = (y1 - y0 + 1) * NPATCH
        for cell in CELLS:
            for arm in ARMS:
                for seed in ([1] if arm in ("REC", "NP") else SEEDS):
                    if not os.path.isdir(rundir(scen, cell, arm, seed)):
                        st = "MISSING"
                    elif not run_completed(scen, cell, arm, NPREV, seed):
                        st = "DEAD"
                    elif arm == "REC":
                        st = "OK"
                    else:
                        n = armlog_patchyears(scen, cell, arm, seed)
                        st = "OK" if n == want else "SHORT"
                    tally[st] += 1
                    if st != "OK":
                        n = armlog_patchyears(scen, cell, arm, seed)
                        bad.append((scen, cell, arm, seed, st, n, want))
    print(f"  OK {tally['OK']}   SHORT {tally['SHORT']}   DEAD {tally['DEAD']}"
          f"   MISSING {tally['MISSING']}")
    if bad:
        print(f"\n  {len(bad)} leg(s) NOT OK (named, skill trap 2):")
        for scen, cell, arm, seed, st, n, want in bad:
            got = "no log" if n < 0 else f"{n}/{want} patch-years"
            print(f"      {st:<8} {scen:<9} c{cell:<6d} {arm:<4} s{seed}   {got}")
    if bad and RESUBMIT:
        print("\n  RE-RUN (MAXIDLE defaults to 900 s in the runner; keep MAXQ modest — a 40-way")
        print("  campaign is what trips the harness's idle timeout, so less concurrency helps):")
        for scen, cell, arm, seed, _st, _n, _want in bad:
            print(f"      ARM={arm} SCENARIO={scen} CELL={cell} SEED={seed} NPREV={NPREV}"
                  f" bash scripts/run_rung2_s_arm.sh")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
