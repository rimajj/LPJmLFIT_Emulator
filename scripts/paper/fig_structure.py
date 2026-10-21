#!/usr/bin/env python3
"""Figure: forest structure on the 1 050-cell panel, climate model AND run held out (15 cases), relaxed standard of
ADR 0318 on the year-by-year map the release runs (ADR 0340 sec. 4.1). Source: xpanel/eval/final_structure_anchor_fx.csv (leak-free, ADR 0352/0353)
(scripts/final_structure_score.py; dense cells defined by the anchor before the run)."""

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import style as S

Q = [("n_per_patch", "Tree\ncount"), ("agb_per_stem", "Biomass\nper tree"), ("SLA_p50", "SLA"),
     ("Wooddens_p50", "Wood\ndensity"), ("D95max_p50", "Root\ndepth"), ("minwscal_p50", "Drought\nthresh.")]


def strip(ax, d, grp, col, lim, title, letter):
    rng = np.random.default_rng(1)
    for i, (q, _) in enumerate(Q):
        for cand, c, dx in (("harness_m5", S.SECOND, 0.17), ("emulator", S.EMU, -0.17)):
            v = d.filter((pl.col("q") == q) & (pl.col("grp") == grp) & (pl.col("cand") == cand))[col].to_numpy()
            x = i + dx + rng.uniform(-0.07, 0.07, len(v))
            ax.scatter(x, v, s=9, color=c, alpha=0.75, lw=0, zorder=3)
            ax.plot([i + dx - 0.13, i + dx + 0.13], [np.median(v)] * 2, color=c, lw=2.0, zorder=4,
                    solid_capstyle="round")
    ax.axhline(1.0, color=S.MUTED, lw=0.7)
    ax.axhline(lim, color=S.RED, lw=0.9, ls="--")
    ax.text(len(Q) - 0.45, lim, f"limit {lim:g}×", color=S.RED, fontsize=6.3, va="bottom", ha="right")
    ax.set_xticks(range(len(Q)), [lab for _, lab in Q], fontsize=6.5)
    ax.set_xlim(-0.6, len(Q) - 0.4)
    ax.grid(axis="x", visible=False)
    S.panel(ax, letter, title)


def main():
    S.setup()
    d = pl.read_csv(f"{S.DATA}/xpanel/eval/final_structure_anchor_fx.csv")
    fig, axs = plt.subplots(2, 2, figsize=(S.FULL, 4.9), gridspec_kw=dict(wspace=0.22, hspace=0.42))
    axs = axs.ravel()
    strip(axs[0], d, "dense", "rho50", 1.2, "Dense, typical cell", "a")
    strip(axs[1], d, "dense", "rho90", 1.5, "Dense, worst 10 %", "b")
    strip(axs[2], d, "sparse", "rho50", 3.0, "Sparse, typical cell", "c")
    for ax in axs[:3]:
        ax.set_ylabel("Error ÷ error of a further run")
    for ax in axs[:2]:
        ax.set_ylim(0, 2.0)
    axs[2].set_ylim(0, 4.6)

    ax = axs[3]
    rng = np.random.default_rng(2)
    cats = [("dense", "tot_stems", "Stems,\ndense cells", 5), ("dense", "tot_biomass", "Biomass,\ndense cells", 5),
            ("sparse", "tot_stems", "Stems,\nsparse cells", 25), ("sparse", "tot_biomass", "Biomass,\nsparse cells", 25)]
    for i, (grp, col, _, lim) in enumerate(cats):
        e = (d.filter((pl.col("grp") == grp) & (pl.col("cand") == "emulator") & (pl.col("q") == "n_per_patch"))
             [col].to_numpy() * 100)
        r = (d.filter((pl.col("grp") == grp) & (pl.col("cand") == "emulator") & (pl.col("q") == "n_per_patch"))
             ["rep_" + col].to_numpy() * 100)
        for v, c, dx in ((r, S.SECOND, 0.17), (e, S.EMU, -0.17)):
            ax.scatter(i + dx + rng.uniform(-0.07, 0.07, len(v)), v, s=9, color=c, alpha=0.75, lw=0, zorder=3)
            ax.plot([i + dx - 0.13, i + dx + 0.13], [np.median(v)] * 2, color=c, lw=2, zorder=4)
        ax.plot([i - 0.4, i + 0.4], [lim] * 2, color=S.RED, lw=0.9, ls="--")
        ax.plot([i - 0.4, i + 0.4], [-lim] * 2, color=S.RED, lw=0.9, ls="--")
    ax.axhline(0, color=S.MUTED, lw=0.7)
    ax.set_xticks(range(4), [c[2] for c in cats], fontsize=6.5)
    ax.set_ylim(-28, 28)
    ax.set_ylabel("Area-total error (%)")
    ax.grid(axis="x", visible=False)
    S.panel(ax, "d", "Area totals, 2071–2100")
    h = [plt.Line2D([], [], marker="o", ls="", color=S.EMU, ms=4, label="Emulator (15 held-out cases)"),
         plt.Line2D([], [], marker="o", ls="", color=S.SECOND, ms=4, label="A further run of LPJmL-FIT"),
         plt.Line2D([], [], color=S.RED, ls="--", lw=0.9, label="Pass limit")]
    fig.legend(handles=h, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.04))
    S.save(fig, "fig05_structure")


if __name__ == "__main__":
    main()
