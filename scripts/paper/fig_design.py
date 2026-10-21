#!/usr/bin/env python3
"""Figure: the training and test design on the panel (ADR 0246/0316/0320). (a) the 1 050 panel cells (105 blocks of
ten contiguous 0.5 deg cells) on the orderA grid, with the blocks never seen by the daily model and the five biome
blocks; (b) one fold of the structure/stand maps: six independent runs of LPJmL-FIT x ten climate models x three
SSPs; one climate model and one run are held out, a further unseen run is the yardstick."""

import matplotlib.patches as mp
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import style as S

GRID = "/p/projects/waldspektrum/priesner/clustering/global/soil_code_test.grid.clm"
GCMS = ["GFDL-ESM4", "IPSL-CM6A-LR", "MPI-ESM1-2-HR", "MRI-ESM2-0", "UKESM1-0-LL", "CanESM5", "CNRM-CM6-1",
        "CNRM-ESM2-1", "EC-Earth3", "MIROC6"]
BIOME_LAB = {"tropical_amazon": "Amazon", "semiarid_sahel": "Sahel", "mediterranean_iberia": "Iberia",
             "temperate_hainich": "Hainich", "boreal_siberia": "Siberia"}


def coords():
    b = open(GRID, "rb").read()
    return np.frombuffer(b[51:], dtype="<f4").reshape(-1, 2)


def main():
    S.setup()
    xy = coords()
    c = pl.read_parquet(f"{S.DATA}/f2/cells.parquet")
    cell = c["Cell"].to_numpy()
    ho = c["heldout"].to_numpy()
    fig = plt.figure(figsize=(S.FULL, 5.2))
    ax = fig.add_axes([0.0, 0.47, 1.0, 0.5])
    img = np.full((360, 720), np.nan)
    ix = ((xy[:, 0] + 180) / 0.5).astype(int)
    iy = ((xy[:, 1] + 90) / 0.5).astype(int)
    img[iy, ix] = 0
    ax.imshow(img[::-1], extent=(-180, 180, -90, 90), cmap=plt.matplotlib.colors.ListedColormap(["#e9e8e4"]),
              interpolation="nearest")
    ax.scatter(xy[cell[~ho], 0], xy[cell[~ho], 1], s=1.6, marker="s", color=S.EMU, lw=0,
               label="Panel cells used in training")
    ax.scatter(xy[cell[ho], 0], xy[cell[ho], 1], s=1.6, marker="s", color=S.SECOND, lw=0,
               label="Blocks never seen by the daily model")
    for b, lab in BIOME_LAB.items():
        k = cell[c["biome"].to_numpy() == b]
        x0, y0 = xy[k, 0].mean(), xy[k, 1].mean()
        ax.add_patch(mp.Circle((x0, y0), 3.2, fill=False, ec=S.ORIG, lw=0.8))
        ax.text(x0 + 4.5, y0 + 2.5, lab, fontsize=6.5, color=S.ORIG)
    ax.set_xlim(-180, 180)
    ax.set_ylim(-58, 84)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.legend(loc="lower left", markerscale=4, fontsize=6.5, bbox_to_anchor=(0.0, 0.02))
    S.panel(ax, "a", "1 050 panel cells in 105 blocks of ten (25 patches each)")

    # ---- (b) one fold of the yearly maps
    ax = fig.add_axes([0.08, 0.02, 0.9, 0.38])
    runs = ["m1", "m2", "m3", "m4", "m5", "m6"]
    for i, r in enumerate(runs):
        for j, _g in enumerate(GCMS):
            for k in range(3):
                x = j * 3.3 + k
                y = len(runs) - 1 - i
                held_g = j == 0
                if r == "m4":
                    col = S.ORIG if held_g else "#ffffff"
                elif held_g:
                    col = {"m1": S.SECOND, "m2": S.SECOND, "m3": S.SECOND, "m5": S.NULL1}.get(r, "#ffffff")
                else:
                    col = S.EMU if r != "m4" else "#ffffff"
                ax.add_patch(mp.Rectangle((x, y), 0.9, 0.82, fc=col, ec="#c9c8c2", lw=0.4))
    for j, g in enumerate(GCMS):
        ax.text(j * 3.3 + 1.45, 6.15, g, ha="center", va="bottom", fontsize=5.2, rotation=0)
        for k, s in enumerate(("126", "370", "585")):
            ax.text(j * 3.3 + k + 0.45, -0.25, s, ha="center", va="top", fontsize=4.8, color=S.INK2)
    for i, r in enumerate(runs):
        ax.text(-0.4, len(runs) - 1 - i + 0.41, f"run {r[1]}", ha="right", va="center", fontsize=6.3)
    ax.set_xlim(-3.2, 33)
    ax.set_ylim(-1.3, 7.1)
    ax.axis("off")
    S.panel(ax, "b", "One test fold of the yearly forest maps (climate model and run held out)")
    h = [mp.Patch(fc=S.EMU, label="Training (5 runs × 9 climate models × 3 SSPs)"),
         mp.Patch(fc=S.ORIG, label="Test: unseen run, unseen climate model"),
         mp.Patch(fc=S.SECOND, label="Yardstick: further runs of LPJmL-FIT"),
         mp.Patch(fc=S.NULL1, label="Check: a further run scored as if it were the emulator"),
         mp.Patch(fc="white", ec="#c9c8c2", label="Not used in this fold")]
    ax.legend(handles=h, loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=3, fontsize=6.3)
    S.save(fig, "fig_design")


if __name__ == "__main__":
    main()
