#!/usr/bin/env python3
"""Figure: how the yearly forest map works at single cells (ADR 0316/0330). For two panel cells and the held-out
climate model GFDL-ESM4 (SSP3-7.0): the original's training runs under the nine OTHER climate models (thin grey),
the per-cell anchor (their mean; violet), the unseen truth run m4 (black), an independent further run m5 (orange)
and the emulator (blue, year-by-year map with GFDL-ESM4 and run m4 never seen).
Sources: xpanel/yearly/m<k>_<leg>.parquet, xpanel/eval/yearly/preds_gfdl-esm4_fx.parquet (leak-free, ADR 0352/0353)."""

import os
import sys

import matplotlib.pyplot as plt
import polars as pl
import style as S

sys.path.insert(0, os.path.join(S.REPO, "scripts"))
import explore_panel_yearly_drift as YD  # noqa: E402

CELLS = [(42490, "Temperate cell (Hainich, Germany)"), (52054, "Boreal cell (Siberia)")]
LEG = "gfdl-esm4_ssp370"
OTHERS = ["ipsl-cm6a-lr", "mpi-esm1-2-hr", "mri-esm2-0", "ukesm1-0-ll", "canesm5", "cnrm-cm6-1", "cnrm-esm2-1",
          "ec-earth3", "miroc6"]
# per-tree biomass: the ind table carries density-weighted gC m-2 with nind = 1/patcharea, patcharea = 225 m2
Q = [("n_per_patch", "Trees > 5 m per patch", 1.0), ("agb_per_stem", "Above-ground biomass\nper tree (kgC)", 0.225)]


def main():
    S.setup()
    cells = [c for c, _ in CELLS]
    pred = pl.read_parquet(f"{S.DATA}/xpanel/eval/yearly/preds_gfdl-esm4_fx.parquet").filter(
        (pl.col("member") == 4) & (pl.col("leg") == LEG) & pl.col("Cell").is_in(cells)).sort("Year")
    train = [YD.yearly(m, f"{g}_ssp370") for m in YD.TRAIN_M for g in OTHERS]
    train = pl.concat([t for t in train if t is not None]).filter(pl.col("Cell").is_in(cells))
    truth = YD.yearly(4, LEG).filter(pl.col("Cell").is_in(cells))
    sec = YD.yearly(5, LEG).filter(pl.col("Cell").is_in(cells))
    fig, axs = plt.subplots(2, 2, figsize=(S.FULL, 3.9), sharex=True, gridspec_kw=dict(hspace=0.35, wspace=0.22))
    for i, (c, cname) in enumerate(CELLS):
        for j, (q, qlab, k) in enumerate(Q):
            ax = axs[j, i]
            for _key, t in train.filter(pl.col("Cell") == c).group_by(["member", "leg"]):
                t = t.sort("Year")
                ax.plot(t["Year"], k * t[q], color="#c9c8c2", lw=0.4, alpha=0.6, zorder=1)
            p = pred.filter(pl.col("Cell") == c)
            ax.plot(p["Year"], k * p[f"anc_{q}"], color=S.NULL2, lw=1.3, label="Anchor: mean of training runs")
            for d, col, lab, lw in ((truth, S.ORIG, "Unseen run of LPJmL-FIT (truth)", 1.0),
                                    (sec, S.SECOND, "A further run of LPJmL-FIT", 1.0)):
                x = d.filter(pl.col("Cell") == c).sort("Year")
                ax.plot(x["Year"], k * x[q], color=col, lw=lw, label=lab)
            ax.plot(p["Year"], k * p[q], color=S.EMU, lw=1.8, label="Emulator")
            ax.set_xlim(2020, 2100)
            ax.set_xticks([2030, 2060, 2090])
            if i == 0:
                ax.set_ylabel(qlab)
            S.panel(ax, "abcd"[2 * j + i], cname if j == 0 else None)
    h, lab = axs[0, 0].get_legend_handles_labels()
    h.insert(0, plt.Line2D([], [], color="#c9c8c2", lw=0.8))
    lab.insert(0, "Training runs, nine other climate models")
    fig.legend(h, lab, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.07), fontsize=6.5)
    S.save(fig, "fig_cell_example")


if __name__ == "__main__":
    main()
