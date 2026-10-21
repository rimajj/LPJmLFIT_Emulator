#!/usr/bin/env python3
"""Figure: cost per cell-year on one core (marginal rate). Numbers from the decision records: LPJmL-FIT 0.267 core-s
at 25 patches (ADR 0084, Hainich) and 7.06 measured at 500 patches (ADR 0086, Hainich); the released emulator
7.01e-3 (release v2, ADR 0358 sec. 3, job 2653214, 1 050 cells x 81 years; daily networks 97 %, ADR 0340 sec. 4.4); the ESM
allowances of EXECUTION_PLAN sec. 0 (0.030 / 0.0135)."""

import matplotlib.pyplot as plt
import style as S

ROWS = [("LPJmL-FIT, 500 patches\n(publication setting)", 7.06, S.ORIG),
        ("LPJmL-FIT, 25 patches\n(training setting)", 0.267, S.ORIG),
        ("Learned emulator\n(this study)", 7.01e-3, S.EMU)]


def main():
    S.setup()
    fig, ax = plt.subplots(figsize=(S.FULL * 0.62, 2.1))
    y = range(len(ROWS))[::-1]
    for yi, (_lab, v, c) in zip(y, ROWS, strict=True):
        ax.barh(yi, v, color=c, height=0.55)
        if v < 0.01:
            ax.text(1.12e-3, yi, "0.0070 s", va="center", fontsize=6.8, color="white", fontweight="bold")
        else:
            ax.text(v * 1.15, yi, f"{v:.3g} s", va="center", fontsize=6.8, color=S.ORIG)
    # split of the emulator bar: daily networks 97 %
    ax.barh(0, 7.01e-3 * 0.03, left=7.01e-3 * 0.97, color="#86b6ef", height=0.55)
    for v, lab in ((0.030, "T63"), (0.0135, "T31")):
        ax.axvline(v, color=S.RED, lw=0.8, ls="--")
        ax.text(v, 2.95, lab, color=S.RED, fontsize=6.3, va="bottom", ha="center")
    ax.set_xscale("log")
    ax.set_xlim(1e-3, 40)
    ax.set_ylim(-0.6, 2.9)
    ax.set_yticks(list(y), [r[0] for r in ROWS], fontsize=6.8)
    ax.set_xlabel("Core-seconds per cell-year (one core)")
    ax.grid(axis="y", visible=False)
    ax.annotate("", xy=(7.01e-3, 0.42), xytext=(0.267, 0.42),
                arrowprops=dict(arrowstyle="<->", color=S.EMU, lw=0.8))
    ax.text(0.045, 0.52, "38×", color=S.EMU, fontsize=7, ha="center", fontweight="bold")
    ax.text(0.04, -0.42, "≈ 1 000× below the 500-patch setting", color=S.EMU, fontsize=6.5)
    S.save(fig, "fig_speed")


if __name__ == "__main__":
    main()
