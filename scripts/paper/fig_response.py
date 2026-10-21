#!/usr/bin/env python3
"""Figure: the warming-response test on the nitrogen-on LPJmL-FIT (ADR 0342): 674 representative cells x 25 patches,
two climate models (MPI-ESM1-2-HR, IPSL-CM6A-LR) never seen in training, rising and fixed CO2.
(a) area-weighted change of vegetation carbon, 1990-2019 -> 2071-2100: the original (seed 2), an independent second
    run (seed 3), the emulator trained on all scenarios incl. CO2-fixed twins (arm main2), and the same maps trained
    on ssp126 only (arm wrong) -- the data-coverage control. Source: clu_non/eval/response_maps.csv.
(b) per-cell change, IPSL-CM6A-LR ssp585 with CO2 fixed (the strongest warming-only loss), recomputed with the
    scorer's own functions (scripts/clu_emu_maps.py)."""

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import style as S

sys.path.insert(0, os.path.join(S.REPO, "scripts"))
import clu_emu_maps as M  # noqa: E402

LEGS = [("mpi-esm1-2-hr", "ssp370", "MPI\n370"), ("mpi-esm1-2-hr", "ssp585", "MPI\n585"),
        ("ipsl-cm6a-lr", "ssp370", "IPSL\n370"), ("ipsl-cm6a-lr", "ssp585", "IPSL\n585")]


def percell(gcm, ssp, arm="main2"):
    name = M.leg_name(gcm, ssp)
    h2, h3 = M.targets(2, "hist"), M.targets(3, "hist")
    t2, t3 = M.targets(2, name), M.targets(3, name)
    p = pl.read_parquet(f"{M.OUT}/maps/{arm}/preds.parquet").filter(pl.col("leg") == name)
    b2 = M.cell_mean(h2, "vegc", M.H0, M.H1)
    dT = M.cell_mean(t2, "vegc", 2071, M.F1) - b2
    dS = M.cell_mean(t3, "vegc", 2071, M.F1) - M.cell_mean(h3, "vegc", M.H0, M.H1)
    dE = M.cell_mean(p, "vegc", 2071, M.F1) - b2
    return dT, dE, dS, M.cells()["heldout"].to_numpy()


def main():
    S.setup()
    d = pl.read_csv(f"{S.DATA}/clu_non/eval/response_maps.csv").filter(
        (pl.col("q") == "vegc") & (pl.col("cells") == "all"))
    fig, (a, b) = plt.subplots(1, 2, figsize=(S.FULL, 2.9), gridspec_kw=dict(width_ratios=[1.55, 1], wspace=0.3))
    bars = [("orig", "LPJmL-FIT", S.ORIG), ("second", "Independent second run", S.SECOND),
            ("main2", "Emulator", S.EMU), ("wrong", "Emulator trained on SSP1-2.6 only", S.MUTED)]
    xs, labels = [], []
    w = 0.19
    for j, co2 in enumerate(("", "co2fix")):
        for i, (g, s, lab) in enumerate(LEGS):
            x0 = j * 4.6 + i
            xs.append(x0)
            labels.append(lab)
            r = d.filter((pl.col("gcm") == g) & (pl.col("ssp") == s + co2))
            vals = {"orig": r["glob_orig"][0], "second": r["glob_second"][0],
                    "main2": r.filter(pl.col("cand") == "main2")["glob_emu"][0],
                    "wrong": r.filter(pl.col("cand") == "wrong")["glob_emu"][0]}
            for k, (key, name, col) in enumerate(bars):
                a.bar(x0 + (k - 1.5) * w, 100 * vals[key], w * 0.92, color=col,
                      label=name if (i == 0 and j == 0) else None)
    a.axhline(0, color=S.INK2, lw=0.6)
    a.set_xticks(xs, labels, fontsize=6.3)
    a.set_ylabel("Change in vegetation carbon (%)")
    a.grid(axis="x", visible=False)
    a.text(1.5, 52, "rising CO$_2$", ha="center", fontsize=7, color=S.INK2)
    a.text(4.6 + 1.5, 52, "CO$_2$ fixed at 2019 (warming only)", ha="center", fontsize=7, color=S.INK2)
    a.axvline(3.8, color=S.GRID, lw=0.8)
    a.set_ylim(-30, 58)
    a.legend(loc="upper center", fontsize=6.3, ncol=2, bbox_to_anchor=(0.5, -0.17))
    S.panel(a, "a", "Global response, held-out climate models")

    dT, dE, dS, ho = percell("ipsl-cm6a-lr", "ssp585co2fix")
    k = 1e-3
    ok = np.isfinite(dT) & np.isfinite(dE) & np.isfinite(dS)
    b.scatter(k * dT[ok], k * dS[ok], s=5, color=S.SECOND, alpha=0.55, lw=0, label="Second run")
    b.scatter(k * dT[ok], k * dE[ok], s=5, color=S.EMU, alpha=0.75, lw=0, label="Emulator")
    lim = [-12, 6]
    b.plot(lim, lim, color=S.INK2, lw=0.7)
    for v, col in ((dE, S.EMU), (dS, S.SECOND)):
        sl = np.cov(v[ok], dT[ok])[0, 1] / np.var(dT[ok])
        xx = np.array(lim)
        b.plot(xx, sl * xx, color=col, lw=1.0, ls="--")
    b.set_xlim(*lim)
    b.set_ylim(*lim)
    b.set_aspect("equal")
    b.set_xlabel("LPJmL-FIT change (kgC m$^{-2}$)")
    b.set_ylabel("Predicted change (kgC m$^{-2}$)")
    b.legend(loc="upper left", fontsize=6.3, markerscale=2)
    S.panel(b, "b", "Per cell, IPSL SSP5-8.5, CO$_2$ fixed")
    print("slopes emu/second:", np.cov(dE[ok], dT[ok])[0, 1] / np.var(dT[ok]),
          np.cov(dS[ok], dT[ok])[0, 1] / np.var(dT[ok]), "n", ok.sum())
    S.save(fig, "fig_response")


if __name__ == "__main__":
    main()
