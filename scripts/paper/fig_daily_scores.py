#!/usr/bin/env python3
"""Figure: the daily water-carbon fluxes of the full emulator against the second-run yardstick (ADR 0325 sec. 3),
238 held-out cells, 13 climate-model legs. Two arms differing in one thing: the daily model fed the ORIGINAL's stand
(PD_A) or the stand the emulator's own maps produce (PD_B = the whole emulator; ADR 0337/0340 sec. 4.2).
Source: f2/runs/relative_score_PD_ADR0337.md (scripts/f2_relative_score.py)."""

import re

import matplotlib.pyplot as plt
import numpy as np
import style as S

FLUX = [("gpp", "GPP"), ("npp", "NPP"), ("et", "ET"), ("runoff", "Runoff")]


def parse(path):
    rows, cur = [], None
    for line in open(path):
        m = re.match(r"^## (\S+)", line)
        if m:
            cur = m.group(1)
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) < 10 or c[2] != "free" or c[0] == "ctl_obs":
            continue
        e, la = (float(x) for x in c[3].split("/"))
        rows.append(dict(arm=cur, leg=c[0], flux=c[1], typ=max(e, la), p90=max(float(x) for x in c[4].split("/")),
                         resp=float(c[5].split("/")[0]), drift=float(c[7]), tot=float(c[8].split()[0])))
    return rows


def main():
    S.setup()
    rows = parse(f"{S.DATA}/f2/runs/relative_score_PD_ADR0337.md")
    stats = [("typ", "Typical cell, 30-year means", 3.0, (0, 8.5)), ("resp", "Climate response, typical cell", 1.5, (0, 3.2)),
             ("drift", "Drift relative to LPJmL-FIT", 1.2, (0.6, 1.4)), ("tot", "Area totals", 5, (0, 5.6))]
    fig, axs = plt.subplots(2, 2, figsize=(S.FULL, 4.2), gridspec_kw=dict(wspace=0.25, hspace=0.4))
    axs = axs.ravel()
    rng = np.random.default_rng(3)
    for ax, (k, title, lim, yl), letter in zip(axs, stats, "abcd", strict=True):
        for i, (f, _) in enumerate(FLUX):
            for arm, col, dx in (("PD_A", S.NULL1, -0.18), ("PD_B", S.EMU, 0.18)):
                v = np.array([r[k] for r in rows if r["arm"] == arm and r["flux"] == f])
                if k == "tot":
                    v = 100 * v
                ax.scatter(i + dx + rng.uniform(-0.07, 0.07, len(v)), v, s=8, color=col, alpha=0.75, lw=0, zorder=3)
                ax.plot([i + dx - 0.13, i + dx + 0.13], [np.median(v)] * 2, color=col, lw=2, zorder=4)
        ax.axhline(lim, color=S.RED, lw=0.9, ls="--")
        if k != "tot":
            ax.axhline(1.0, color=S.SECOND, lw=0.9)
        ax.set_ylim(*yl)
        ax.set_xticks(range(len(FLUX)), [lab for _, lab in FLUX], fontsize=6.5)
        ax.set_xlim(-0.6, len(FLUX) - 0.4)
        ax.grid(axis="x", visible=False)
        S.panel(ax, letter, title)
    for ax in axs[:2]:
        ax.set_ylabel("Error ÷ further run's error")
    axs[2].set_ylabel("Late ÷ early error ratio")
    axs[3].set_ylabel("Area-total error (%)")
    h = [plt.Line2D([], [], marker="o", ls="", color=S.EMU, ms=4, label="Full emulator (emulated stand)"),
         plt.Line2D([], [], marker="o", ls="", color=S.NULL1, ms=4, label="Daily model on LPJmL-FIT's stand"),
         plt.Line2D([], [], color=S.SECOND, lw=0.9, label="A further run of LPJmL-FIT"),
         plt.Line2D([], [], color=S.RED, ls="--", lw=0.9, label="Proposed limit")]
    fig.legend(handles=h, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.04), fontsize=6.5)
    S.save(fig, "fig_daily_scores")


if __name__ == "__main__":
    main()
