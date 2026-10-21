#!/usr/bin/env python3
"""Figure: the structure map run year by year, 2020-2100 (ADR 0330): typical-cell error relative to a further run of
the original, dense cells, median over the 15 held-out cases, for the emulator and four reference arms.
Source: xpanel/eval/yearly/drift_years_fx.csv (leak-free, ADR 0352/0353; scripts/explore_panel_yearly_drift.py score)."""

import matplotlib.pyplot as plt
import polars as pl
import style as S

CANDS = [("persist", "2019 state carried forward", S.MUTED, "--"),
         ("anchor", "Anchor alone (no learned shift)", S.NULL2, "-"),
         ("second", "A further run of LPJmL-FIT", S.SECOND, "-"),
         ("oracle", "Mean of five other runs", S.NULL1, "-"),
         ("YA", "Emulator", S.EMU, "-")]
Q = [("n_per_patch", "Tree count"), ("agb_per_stem", "Biomass per tree"), ("Wooddens_p50", "Wood density (median)")]


def main():
    S.setup()
    d = pl.read_csv(f"{S.DATA}/xpanel/eval/yearly/drift_years_fx.csv").filter(pl.col("grp") == "dense")
    fig, axs = plt.subplots(1, 3, figsize=(S.FULL, 2.35), sharey=True, gridspec_kw=dict(wspace=0.12))
    for ax, (q, lab), letter in zip(axs, Q, "abc", strict=True):
        for cand, name, col, ls in CANDS:
            x = (d.filter((pl.col("q") == q) & (pl.col("cand") == cand)).group_by("Year")
                 .agg(pl.col("rho50").median().alias("m"), pl.col("rho50").quantile(0.1).alias("lo"),
                      pl.col("rho50").quantile(0.9).alias("hi")).sort("Year"))
            if x.height == 0:
                continue
            if cand == "YA":
                ax.fill_between(x["Year"], x["lo"], x["hi"], color=col, alpha=0.15, lw=0)
            ax.plot(x["Year"], x["m"], color=col, ls=ls, lw=1.6 if cand == "YA" else 1.1, label=name)
        ax.axhline(1.2, color=S.RED, lw=0.8, ls=":")
        ax.set_xlim(2020, 2100)
        ax.set_ylim(0.3, 2.6)
        ax.set_xticks([2030, 2060, 2090])
        S.panel(ax, letter, lab)
    axs[0].set_ylabel("Typical error ÷ further run's")
    axs[2].text(2098, 1.23, "dense-cell limit", color=S.RED, fontsize=6.3, ha="right", va="bottom")
    h, lab = axs[0].get_legend_handles_labels()
    fig.legend(h[::-1], lab[::-1], loc="lower center", ncol=5, bbox_to_anchor=(0.5, -0.1), fontsize=6.5,
               handlelength=1.8, columnspacing=1.0)
    S.save(fig, "fig07_drift")


if __name__ == "__main__":
    main()
