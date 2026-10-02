#!/usr/bin/env python3
"""explore_de_grass_diag_truth.py — LINE X, Germany emulator: the ORIGINAL's yearly grass-cap statistics on the first
N dev cells (an engine chunk), in the same format the coupled stepper writes with XDE_GRASS_DIAG
(explore_de_tab_g2.py): mean grass cover, mean Beer-Lambert grass cover, share of patches whose cover cap binds, mean
implied hidden (< 5 m) tree cover where it binds, mean printed tree cover, mean grass LAI, recruits per patch.
Output: <out> jsonl (default shared/eval/grass_diag_truth_<gcm>_s<seed>_<leg>_c<N>.jsonl)."""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_grass2 as g2  # noqa: E402
import explore_de_recruit_grass as rg  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gcm", default="ACCESS-CM2")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--leg", default="ssp370")
    ap.add_argument("--ncells", type=int, default=100)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    cells = sorted(pl.read_parquet(g2.F.patch_file(f"{a.gcm}_Historical_s{a.seed}_h1985", 1985),
                                   columns=["Cell"])["Cell"].unique().to_list())[: a.ncells]
    S = rg.stored(a.gcm, a.seed, a.leg, cells)
    K = float(g2.Grass2("DEV-A").C["K"])
    out = a.out or os.path.join(g2.EVAL, f"grass_diag_truth_{a.gcm}_s{a.seed}_{a.leg}_c{a.ncells}.jsonl")
    with open(out, "w") as fh:
        for (y,), d in S.partition_by("Year", as_dict=True, maintain_order=True).items():
            g = d[g2.GF].cast(pl.Float64).to_numpy()
            L = d[g2.GL].cast(pl.Float64).to_numpy()
            t = d["sum_fpc_y"].cast(pl.Float64).to_numpy()
            pot = 1 - np.exp(-K * L)
            cap = (pot - g) > 1e-3
            h = 1 - g - t
            nr = d["n_recruit_y"].cast(pl.Float64).mean()  # null in the first state year (no previous year)
            fh.write(json.dumps({"Year": int(y), "n": int(d.height), "g_mean": float(g.mean()),
                                 "pot_mean": float(pot.mean()), "cap_share": float(cap.mean()),
                                 "h_mean_capped": float(h[cap].mean()) if cap.any() else None,
                                 "t1_mean": float(t.mean()), "L_mean": float(L.mean()),
                                 "nrec_pp": None if nr is None else float(nr)}) + "\n")
    print("wrote", out)


if __name__ == "__main__":
    main()
