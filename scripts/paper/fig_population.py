#!/usr/bin/env python3
"""Figure: the tree population under a held-out climate model and run (ADR 0363 sec. 9 and 12, shipped by ADR 0365).
(a) Within-cell distributions of eight tree variables (nine quantile levels), (b) functional-diversity and structure
indices of the virtual trees. Dense cells, 15 held-out cases, years 2021-2100 (indices: every 10th year). Values are the
median over cases of the typical-cell error ratio (filled) and of the worst tenth (open); the anchor alone (no learned
departure, its virtual trees drawn the same way) and a further run scored as the emulator are the references.
Source: xpanel/eval/popmap/score_popmap_unique.csv (explore_panel_popjoint.py score, VDRAW=unique: the no-repeat donor
draw that ships). Performance only: no limit lines (owner, 2026-10-21)."""

import matplotlib.pyplot as plt
import polars as pl

import style as S

VARS = [("Height", "Height"), ("agb", "Biomass\nper tree"), ("SLA", "SLA"), ("Wooddens", "Wood\ndensity"),
        ("D95max", "Max. root\ndepth"), ("minwscal", "Drought\nthresh."), ("D95", "Actual root\ndepth"),
        ("Age", "Age")]
IDX = [("cwm_SLA", "CWM\nSLA"), ("cwm_Wooddens", "CWM\nWD"), ("cwm_D95max", "CWM\nroot"),
       ("cwm_minwscal", "CWM\ndrought"), ("cwv_SLA", "CWV\nSLA"), ("cwv_Wooddens", "CWV\nWD"),
       ("cwv_D95max", "CWV\nroot"), ("cwv_minwscal", "CWV\ndrought"),
       ("fric", "Rich-\nness"), ("feve", "Even-\nness"), ("fdiv", "Diver-\ngence"), ("fdis", "Disper-\nsion"),
       ("raoq", "Rao's\nQ"), ("type_shannon", "Type\nShan."), ("type_simpson", "Type\nSimp."),
       ("h_shannon", "Height\nShan."), ("h_gini", "Height\nGini")]


def get(d: pl.DataFrame, what: str) -> tuple[float, float]:
    r = d.filter(pl.col("what") == what)
    assert r.height == 1, what
    return float(r["typ_median"][0]), float(r["worst_median"][0])


def dots(ax, rows, letter, title):
    for i, (vals, _) in enumerate(rows):
        for (typ, worst), c, dx in zip(vals, (S.EMU, S.NULL2, S.SECOND), (-0.22, 0.0, 0.22), strict=True):
            ax.scatter([i + dx], [typ], s=22, color=c, lw=0, zorder=4)
            ax.scatter([i + dx], [worst], s=22, facecolor="white", edgecolor=c, lw=1.0, zorder=3)
            ax.plot([i + dx] * 2, [typ, worst], color=c, lw=0.8, alpha=0.6, zorder=2)
    ax.axhline(1.0, color=S.MUTED, lw=0.7)
    ax.set_xticks(range(len(rows)), [lab for _, lab in rows], fontsize=6.0)
    ax.set_xlim(-0.6, len(rows) - 0.4)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Error ÷ error of a further run")
    S.panel(ax, letter, title)


def main():
    S.setup()
    d = pl.read_csv(f"{S.DATA}/xpanel/eval/popmap/score_popmap_unique.csv")
    rv = [((get(d, f"{v} all9 AQ dense"), get(d, f"{v} all9 anc dense"), get(d, f"{v} all9 T5 dense")), lab)
          for v, lab in VARS]
    ri = [((get(d, f"index {k} AQ-D0 dense"), get(d, f"index {k} A0-D0 dense"), get(d, f"index {k} harness dense")),
           lab) for k, lab in IDX]
    fig, axs = plt.subplots(2, 1, figsize=(S.FULL, 4.8), gridspec_kw=dict(hspace=0.55, height_ratios=[1, 1]))
    dots(axs[0], rv, "a", "Within-cell distributions (nine quantile levels), dense cells")
    dots(axs[1], ri, "b", "Diversity and structure indices of the virtual trees, dense cells")
    axs[0].set_ylim(0.4, 1.3)
    axs[1].set_yscale("log")
    axs[1].set_ylim(0.45, 4.6)
    axs[1].set_yticks([0.5, 0.7, 1, 1.5, 2, 3, 4], ["0.5", "0.7", "1", "1.5", "2", "3", "4"])
    axs[1].minorticks_off()
    h = [plt.Line2D([], [], marker="o", ls="", color=S.EMU, ms=4.5, label="Emulator"),
         plt.Line2D([], [], marker="o", ls="", color=S.NULL2, ms=4.5, label="Anchor alone"),
         plt.Line2D([], [], marker="o", ls="", color=S.SECOND, ms=4.5, label="A further run of LPJmL-FIT"),
         plt.Line2D([], [], marker="o", ls="", color=S.INK2, ms=4.5, label="typical cell (filled)"),
         plt.Line2D([], [], marker="o", ls="", mfc="white", mec=S.INK2, ms=4.5, label="worst tenth (open)")]
    fig.legend(handles=h, loc="lower center", ncol=5, bbox_to_anchor=(0.5, -0.03))
    S.save(fig, "fig_population")


if __name__ == "__main__":
    main()
