#!/usr/bin/env python3
"""Figure: where LPJmL-FIT spends its time (exclusive self-time profile, five biome blocks; ADR 0312 sec. 2) and
the Amdahl ceiling of replacing processes one by one (Hainich, ADR 0312 sec. 3a). Numbers transcribed from the
committed decision record (perf profiles of the unmodified production binary, 25 patches, one task)."""

import matplotlib.pyplot as plt
import numpy as np
import style as S

SITES = ["Temperate\n(Hainich)", "Tropical\n(Amazon)", "Semi-arid\n(Sahel)", "Mediterr.\n(Iberia)", "Boreal\n(Siberia)"]
# process -> share of self time (%) at the five sites, math routines attributed to their callers
PROC = [
    ("Leaf gas exchange", [45.78, 41.78, 36.17, 41.36, 38.33]),
    ("Soil water", [21.36, 27.48, 15.41, 19.37, 16.20]),
    ("Daily loop / dispatch", [7.64, 7.65, 14.83, 9.00, 13.90]),
    ("Canopy light", [7.37, 5.88, 9.75, 8.34, 10.71]),
    ("Litter + soil carbon", [6.38, 5.74, 6.37, 6.61, 4.58]),
    ("Soil heat", [3.82, 4.59, 4.45, 4.58, 3.21]),
    ("Phenology + leaf turnover", [2.53 + 1.83, 1.47 + 1.54, 7.17 + 1.16, 3.94 + 3.33, 5.85 + 2.41]),
    ("Annual demography", [0.63, 0.44, 1.03, 0.86, 1.06]),
    ("Other", [0.17 + 2.37, 0.16 + 3.33, 0.18 + 3.36, 0.18 + 2.21, 0.18 + 3.44]),
]
COLS = [S.EMU, S.NULL1, "#86b6ef", S.YELLOW, "#a8a7a1", "#c9c8c2", S.NULL2, S.SECOND, "#e4e3df"]
# cumulative Amdahl ceiling at Hainich (process made free): ADR 0312 sec. 3a
CUM = [("+ leaf gas exchange", 1.84), ("+ soil water", 3.04), ("+ canopy light", 3.92),
       ("+ litter/soil carbon", 5.23), ("+ daily loop", 8.72), ("+ soil heat", 13.1),
       ("+ phenology, solver", 30.4)]


def main():
    S.setup()
    fig, (a, b) = plt.subplots(1, 2, figsize=(S.FULL, 2.7), gridspec_kw=dict(width_ratios=[1.35, 1], wspace=0.55))
    y = np.arange(len(SITES))[::-1]
    left = np.zeros(len(SITES))
    for (name, v), c in zip(PROC, COLS, strict=True):
        v = np.array(v)
        a.barh(y, v, left=left, color=c, height=0.62, edgecolor="white", linewidth=0.8, label=name)
        left += v
    a.set_yticks(y, SITES)
    a.set_xlim(0, 100)
    a.set_xlabel("Share of LPJmL-FIT run time (%)")
    a.grid(axis="y", visible=False)
    a.legend(ncol=3, loc="upper left", bbox_to_anchor=(-0.32, -0.2), handlelength=1.0, columnspacing=0.8,
             fontsize=6.3)
    S.panel(a, "a", "Run time by process, five biomes")

    xs = np.arange(len(CUM))
    b.plot(xs, [c[1] for c in CUM], "-o", color=S.EMU, ms=4, lw=1.4)
    b.set_yscale("log")
    b.set_ylim(1, 1500)
    b.set_xticks(xs, [c[0] for c in CUM], rotation=40, ha="right", fontsize=6.3)
    for ref, lab, yf, col in ((0.267 / 0.0135, "needed for a T31 atmosphere", 0.68, S.SECOND),
                              (25, "gain from dropping 25 patches", 1.15, S.MUTED),
                              (7.06 / 0.0135, "needed at 500 patches", 1.15, S.SECOND)):
        b.axhline(ref, color=col, lw=0.8, ls="--")
        b.text(-0.1, ref * yf, lab, fontsize=6.3, color=S.INK2)
    b.set_ylabel("Max. speed-up if free (×)")
    b.grid(axis="x", visible=False)
    S.panel(b, "b", "Replacing processes one by one")
    S.save(fig, "fig02_runtime")


if __name__ == "__main__":
    main()
