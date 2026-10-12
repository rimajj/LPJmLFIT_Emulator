#!/usr/bin/env python3
"""Does the learned daily model's carbon error grow where climate leaves the training range?

ADR 0327. Per held-out cell (the ADR 0320 L2 mask, GPP >= 50) and test leg: how far the 2081-2100
climate lies outside what the network trained on at that cell (the max/min over the training legs'
20-year means and the warmest-month mean, members pooled), against the growth of the emulator's
NPP/GPP error from 2021-2040 to
2081-2100 (relative to the cell's 2021-2100 mean, members pooled; runs/<tag>/annual.npz).

Usage: python scripts/f2_extrapolation_probe.py [tag] [train_legs] (default RE_5seed); minutes, 8 GB
Training/test legs come from runs/<tag>/legs.json when it exists (ADR 0328); a comma-separated
second argument replaces the training legs (how far would a CANDIDATE training set cover the tests).
"""

import json
import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f2_train as F  # noqa: E402

TAG = sys.argv[1] if len(sys.argv) > 1 else "RE_5seed"
E, L = slice(1, 21), slice(61, 81)  # 2021-2040, 2081-2100 (annual index 0 = 2020)
VAR = ("tas", "pr", "rsds", "lwnet", "huss")
STAND = ("lai", "lvegc", "fpc")  # the stand inputs (fpc = sum of the 10 bands), members pooled


def stand(leg):
    """(4, nc, NY, 3) stand inputs for 2020..2100 (stand arrays start at 2019)."""
    out = []
    for k in F.MEMBERS:
        st = F.stand_features(np.load(os.path.join(F.DATA, f"stand_m{k}_{leg}.npy")))[:, 1:]
        out.append(np.stack([st[..., 0], st[..., 1], st[..., 2:].sum(-1)], -1))
    return np.stack(out)


def climate(leg, k=1):
    """(nc, NY, 5) annual means and (nc, NY) warmest-month tas, for 2020..2100."""
    f = np.load(os.path.join(F.DATA, f"forc_m{k}_{leg}.npy"), mmap_mode="r")[:, F.WARM :]
    f = np.asarray(f, dtype=np.float32).reshape(f.shape[0], F.NY, 365, 5)
    ann = f.mean(2)
    mon = f[..., 0][:, :, : 12 * 30].reshape(f.shape[0], F.NY, 12, 30).mean(-1).max(-1)
    return ann, mon


def win(a, s):
    return a[:, s].mean(1)


def spearman(a, b):
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def main():
    cells = pl.read_parquet(os.path.join(F.DATA, "cells.parquet"))
    ho = cells["heldout"].to_numpy()
    z = np.load(os.path.join(F.DATA, "runs", TAG, "annual.npz"))
    lj = os.path.join(F.DATA, "runs", TAG, "legs.json")
    if os.path.exists(lj):
        legs = json.load(open(lj))
        F.TRAIN_LEGS[:], F.TEST_LEGS[:] = legs["train"], legs["test"]
    if len(sys.argv) > 2:
        F.TRAIN_LEGS[:] = sys.argv[2].split(",")
    print(f"training legs: {F.TRAIN_LEGS}")
    # training range per cell: all 20-yr windows of every training leg (ctl_obs differs by member)
    lo = {v: None for v in (*VAR, "tmax")}
    hi = {v: None for v in (*VAR, "tmax")}
    for leg in F.TRAIN_LEGS:
        for k in F.MEMBERS if leg == "ctl_obs" else [1]:
            ann, mon = climate(leg, k)
            for j, v in enumerate((*VAR, "tmax")):
                x = mon if v == "tmax" else ann[:, :, j]
                w = np.stack([x[:, s : s + 20].mean(1) for s in range(1, F.NY - 19, 5)], 1)
                lo[v] = w.min(1) if lo[v] is None else np.minimum(lo[v], w.min(1))
                hi[v] = w.max(1) if hi[v] is None else np.maximum(hi[v], w.max(1))
    for leg in F.TRAIN_LEGS:
        st = stand(leg)
        for j, v in enumerate(STAND):
            w = np.stack([st[:, :, s : s + 20, j].mean(2) for s in range(1, F.NY - 19, 5)], -1)
            lo[v] = w.min((0, 2)) if v not in lo else np.minimum(lo[v], w.min((0, 2)))
            hi[v] = w.max((0, 2)) if v not in hi else np.maximum(hi[v], w.max((0, 2)))
    print(f"== tag {TAG}; held-out cells, GPP>=50; exceedance = late-window value beyond the")
    print("   cell's training range (0 inside); error growth = late - early |E-T|/mean(T)")
    for leg in F.TEST_LEGS + ["mpi-esm1-2-hr_ssp370"]:
        t, fr = z[f"truth__{leg}"], z[f"free__{leg}"]  # (4, nc, NY, 4)
        gmean = t[:, :, 1:, 0].mean((0, 2))
        m = ho & (gmean >= 50)
        ann, mon = climate(leg)
        ex = {}
        for j, v in enumerate((*VAR, "tmax")):
            x = win(mon if v == "tmax" else ann[:, :, j], L)
            ex[v] = np.maximum(x - hi[v], 0) + np.maximum(lo[v] - x, 0)
        st = stand(leg)
        for j, v in enumerate(STAND):
            x = st[:, :, L, j].mean(2)  # (4, nc): every member's own stand
            ex[v] = (np.maximum(x - hi[v], 0) + np.maximum(lo[v] - x, 0)).mean(0)
        print(f"\n-- {leg}: {m.sum()} cells")
        for v in (*VAR, "tmax", *STAND):
            e = ex[v][m]
            print(
                f"   exceedance {v:6s}: share of cells outside {np.mean(e > 0):.2f}  "
                f"median {np.median(e):.3g}  p90 {np.quantile(e, 0.9):.3g}"
            )
        for iv, name in ((0, "gpp"), (2, "npp")):
            norm = t[:, :, 1:, iv].mean(2)  # (4, nc)
            err = np.abs(fr[..., iv] - t[..., iv]) / np.maximum(np.abs(norm), 1e-6)[..., None]
            grow = (win(err.mean(0), L) - win(err.mean(0), E))[m]
            sgn = (win((fr[..., iv] - t[..., iv]).mean(0), L) / np.abs(norm.mean(0)))[m]
            print(
                f"   {name}: error growth median {np.median(grow):+.4f} "
                f"p90 {np.quantile(grow, 0.9):+.4f}; "
                f"late signed bias median {np.median(sgn):+.4f}"
            )
            out = np.any(np.stack([ex[v][m] > 0 for v in ("tas", "tmax", "huss")]), 0)
            if 0 < out.sum() < m.sum():
                print(
                    f"      growth inside range (n={np.sum(~out)}) "
                    f"median {np.median(grow[~out]):+.4f} | "
                    f"outside tas/tmax/huss (n={out.sum()}) median {np.median(grow[out]):+.4f}"
                )
            for v in ("tas", "tmax", "huss", "pr", "rsds", *STAND):
                print(f"      spearman(growth, exceedance {v}) = {spearman(grow, ex[v][m]):+.2f}")
            print(
                f"      spearman(growth, late-minus-early tas) = "
                f"{spearman(grow, (win(ann[:, :, 0], L) - win(ann[:, :, 0], E))[m]):+.2f}"
            )


if __name__ == "__main__":
    main()
