#!/usr/bin/env python3
"""Split the learned daily model's carbon gap into photosynthesis and plant respiration (ADR 0332 §1).

Usage: python scripts/f2_carbon_split.py [tag ...] [--blocks=0,1,2,4]   (default: CE_5seed)

Reads DATA/runs/<tag>/annual.npz only (seconds). Held-out cells with a 2021-2100 mean GPP >= 50 (the
f2_relative_score.py mask). Per leg, sums over cells and members, emulator / original for 2021-2040 and
2081-2100: GPP, plant respiration (GPP - NPP), NPP/GPP of both, and the median per-cell GPP / NPP error
with the share of cells the emulator puts low. A sum ratio below 1 late but not early is the
one-sided late-century shortfall ADR 0332 targets; a ratio off 1 in both windows is a constant bias.
--blocks=...: only the held-out cells of those panel blocks (ADR 0334: the four southern
blocks carry ~80 % of the respiration excess); `--blocks=-0,1,2,4` = every held-out cell EXCEPT those blocks.
"""

import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f2_train as F  # noqa: E402

WIN = {"2021-40": slice(1, 21), "2081-00": slice(61, 81)}


def main():
    blocks = [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--blocks=")]
    tags = [a for a in sys.argv[1:] if not a.startswith("--")] or ["CE_5seed"]
    cdf = pl.read_parquet(os.path.join(F.DATA, "cells.parquet"))
    ho = cdf["heldout"].to_numpy()
    if blocks:
        neg = blocks[0].startswith("-")
        sel = np.isin(cdf["block"].to_numpy(), [int(b) for b in blocks[0].lstrip("-").split(",")])
        ho = ho & (~sel if neg else sel)
        where = "outside" if neg else "in"
        print(f"held-out cells {where} blocks {blocks[0].lstrip('-')}: {ho.sum()}")
    for tag in tags:
        z = np.load(os.path.join(F.DATA, "runs", tag, "annual.npz"))
        legs = [k.split("__", 1)[1] for k in z.files if k.startswith("truth__")]
        print(f"\n## {tag}\n")
        print("| leg | window | GPP E/T | resp E/T | NPP/GPP T | NPP/GPP E | GPP med err (low) | NPP med err (low) |")
        print("|---|---|---|---|---|---|---|---|")
        for leg in legs:
            T, E = z["truth__" + leg][:, ho], z["free__" + leg][:, ho]
            m = T[..., 0].mean((0, 2)) >= 50
            T, E = T[:, m], E[:, m]
            for nm, sl in WIN.items():
                t, e = T[:, :, sl].mean(2), E[:, :, sl].mean(2)  # (member, cell, var)
                tg, eg, tn, en = t[..., 0].sum(), e[..., 0].sum(), t[..., 2].sum(), e[..., 2].sum()
                rg = (e[..., 0] - t[..., 0]) / np.abs(t[..., 0])
                rn = (e[..., 2] - t[..., 2]) / np.abs(t[..., 2])
                print(f"| {leg} | {nm} | {eg / tg:.3f} | {(eg - en) / (tg - tn):.3f} | {tn / tg:.3f} | "
                      f"{en / eg:.3f} | {np.median(rg):+.3f} ({(rg < 0).mean():.2f}) | "
                      f"{np.median(rn):+.3f} ({(rn < 0).mean():.2f}) |")  # fmt: skip


if __name__ == "__main__":
    main()
