#!/usr/bin/env python3
"""One-table comparison of learned-daily-model arms (ADR 0320 bar), re-scored from annual.npz.

Usage: python scripts/f2_compare.py [tag ...]   (default: every DATA/runs/<tag> with annual.npz)
Columns: pass flags; worst (over the five legs) L2 median error for GPP/ET/NPP; worst |L3| total
error; biome cells within 5 % (min over GPP/ET/NPP) and inside the response band; per-cell
response slope and r on the two held-out legs; free-run / one-step ratio of the worst NPP L2; S1.
"""

import json
import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f2_train as F  # noqa: E402

V = ("gpp", "et", "npp")


def main():
    runs = os.path.join(F.DATA, "runs")
    tags = sys.argv[1:] or sorted(
        t for t in os.listdir(runs) if os.path.exists(os.path.join(runs, t, "annual.npz"))
    )
    cells = pl.read_parquet(os.path.join(F.DATA, "cells.parquet"))
    hdr = (
        f"{'arm':26s} {'L1 L2 L3 R1':12s} {'L2 worst g/e/n':17s} {'|L3| worst':10s} "
        f"{'L1 n':4s} {'R1 n':4s} {'slope585/uk':12s} {'r585/uk':10s} {'npp f/1':7s} S1"
    )
    print(hdr)
    with np.errstate(divide="ignore", invalid="ignore"):
        for t in tags:
            z = np.load(os.path.join(runs, t, "annual.npz"))
            ann = {tuple(k.split("__")): z[k] for k in z.files}
            S = F.score(ann, cells)
            s1 = json.load(open(os.path.join(runs, t, "summary.json"))).get(
                "S1_core_s_per_cell_year"
            )
            l2 = {
                (k, v): max(S["L2"][f"{k}|{leg}|{v}"]["median_abs_rel_err"] for leg in F.ALL_LEGS)
                for k in ("free", "onestep")
                for v in V
            }
            l3 = max(
                abs(S["L3"][f"free|{leg}|{v}"]["rel_err_total"]) for leg in F.ALL_LEGS for v in V
            )
            l1n = min(
                sum(abs(r["rel_err"]) <= 0.05 for r in S["L1"][f"free|{v}"].values()) for v in V
            )
            r1n = sum(r["inside"] for r in S["R1"]["free|mpi-esm1-2-hr_ssp370"].values())
            rp = [
                S["reports"][f"response_per_cell|free|{leg}|gpp"]
                for leg in ("mpi-esm1-2-hr_ssp585", "ukesm1-0-ll_ssp370")
            ]
            flags = "".join("P " if S["pass"][k] else "F " for k in ("L1", "L2", "L3", "R1"))
            print(
                f"{t:26s} {flags:12s} "
                f"{l2[('free', 'gpp')]:.3f}/{l2[('free', 'et')]:.3f}/{l2[('free', 'npp')]:.3f} "
                f"{l3:10.3f} {l1n:4d} {r1n:4d} "
                f"{rp[0]['slope']:.2f}/{rp[1]['slope']:.2f}   {rp[0]['r']:.2f}/{rp[1]['r']:.2f}  "
                f"{l2[('free', 'npp')] / l2[('onestep', 'npp')]:.2f}   "
                f"{s1 if s1 is None else f'{s1:.1e}'}"
            )


if __name__ == "__main__":
    main()
