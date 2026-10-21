#!/usr/bin/env python3
"""Figure: drought die-offs. Composite over the original's largest one-year tree-count drops that its other runs share
(ADR 0350: 3 291 events in dense cells, 15 held-out cases): tree count relative to the five years before the event, for
the unseen run, the further runs, the forest map alone (preds_<g>_fx) and the shipped emulator with the weather-driven
departure model (preds_<g>_statedep_fx, ADR 0354/0358). (b) The same for stand biomass (tree count x biomass per tree).
Sources: xpanel/eval/extreme_legacy_events.parquet, xpanel/yearly/m<k>_<leg>.parquet,
xpanel/eval/yearly/preds_*.parquet.
"""

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import style as S

sys.path.insert(0, os.path.join(S.REPO, "scripts"))
import explore_panel_yearly_drift as YD  # noqa: E402

K = np.arange(-5, 11)
GCMS = ["gfdl-esm4", "ipsl-cm6a-lr", "mpi-esm1-2-hr", "mri-esm2-0", "ukesm1-0-ll"]


def series(d: pl.DataFrame, col: str, cells: np.ndarray) -> dict:
    w = d.select("Cell", "Year", pl.col(col).alias("v")).pivot(on="Year", index="Cell", values="v").sort("Cell")
    pos = {int(c): i for i, c in enumerate(w["Cell"].to_numpy())}
    m = w.drop("Cell").select(sorted(w.columns[1:], key=int)).to_numpy().astype(float)
    return {int(c): m[pos[int(c)]] for c in cells if int(c) in pos}


def main():
    S.setup()
    ev = pl.read_parquet(f"{S.DATA}/xpanel/eval/extreme_legacy_events.parquet").filter(pl.col("shared"))
    comp = {q: {k: [] for k in ("truth", "second", "map", "emu")} for q in ("tree_count", "stand_biomass")}
    for g in GCMS:
        P = {k: pl.read_parquet(f"{S.DATA}/xpanel/eval/yearly/preds_{g}{sfx}.parquet").filter(
            pl.col("member") == YD.TRUTH) for k, sfx in (("map", "_fx"), ("emu", S.STRUCT_SFX))}
        for s in ("ssp126", "ssp370", "ssp585"):
            leg = f"{g}_{s}"
            for q in ("tree_count", "stand_biomass"):
                e = ev.filter((pl.col("case") == leg) & (pl.col("q") == q))
                cells = e["Cell"].to_numpy()

                def qcol(d, q=q):
                    d = d.with_columns(pl.col("Cell").cast(pl.Int64))
                    if q == "tree_count":
                        return d.with_columns(pl.col("n_per_patch").alias("x"))
                    return d.with_columns((pl.col("n_per_patch") * pl.col("agb_per_stem")).alias("x"))

                src = {"truth": [qcol(YD.yearly(YD.TRUTH, leg))], "second": [qcol(YD.yearly(m, leg)) for m in YD.POOL],
                       "map": [qcol(P["map"].filter(pl.col("leg") == leg))],
                       "emu": [qcol(P["emu"].filter(pl.col("leg") == leg))]}
                for k, ds in src.items():
                    for d in ds:
                        sr = series(d, "x", cells)
                        for c, y in zip(cells, e["year"].to_numpy(), strict=True):
                            v = sr.get(int(c))
                            if v is None:
                                continue
                            j = int(y) - YD.Y0
                            if j - 5 < 0 or j + 10 >= len(v):
                                continue
                            pre = np.nanmean(v[j - 5:j])
                            if pre > 0:
                                comp[q][k].append(v[j + K] / pre - 1.0)
    fig, axs = plt.subplots(1, 2, figsize=(S.FULL, 2.5), sharey=True, gridspec_kw=dict(wspace=0.1))
    sty = {"truth": ("Unseen run of LPJmL-FIT", S.ORIG, "-", 1.6), "second": ("Further runs", S.SECOND, "-", 1.2),
           "map": ("Forest map alone", S.MUTED, "--", 1.2), "emu": ("Emulator (with departure model)", S.EMU, "-", 1.6)}
    for ax, (q, lab), letter in zip(axs, (("tree_count", "Tree count"), ("stand_biomass", "Stand biomass")), "ab",
                                    strict=True):
        for k, (name, col, ls, lw) in sty.items():
            a = np.array(comp[q][k]) * 100
            ax.plot(K, np.nanmedian(a, 0), color=col, ls=ls, lw=lw, label=name)
        ax.axvline(0, color=S.MUTED, lw=0.6)
        ax.axhline(0, color=S.MUTED, lw=0.6)
        ax.set_xlabel("Years from the die-off")
        ax.set_xticks([-5, 0, 5, 10])
        n = len(comp[q]["truth"])
        S.panel(ax, letter, f"{lab} ({n} events)")
    axs[0].set_ylabel("Change from the 5 years before (%)")
    h, labs = axs[0].get_legend_handles_labels()
    fig.legend(h, labs, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.12), fontsize=6.5)
    S.save(fig, "fig_dieoff")


if __name__ == "__main__":
    main()
