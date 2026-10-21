#!/usr/bin/env python3
"""Figure: daily output of the full emulator (validated fold release: maps never saw GFDL-ESM4 or run m4; daily
networks never saw these cells) at three biome cells, GFDL-ESM4 SSP3-7.0, against the unseen run m4 of LPJmL-FIT and
an independent run m1. Top three rows: one late-century year, daily. Bottom row: annual GPP 2021-2100.
Source: esm_land_emulator_data/paper/daily_example_v2.npz (scripts/paper/run_daily_example.py)."""

import matplotlib.pyplot as plt
import numpy as np
import style as S

SITES = [("temperate_hainich", 42490, "Temperate"), ("boreal_siberia", None, "Boreal"),
         ("semiarid_sahel", None, "Semi-arid")]
YEAR = 2085
DV = ["prec", "transp", "evap", "interc", "runoff", "swe", "rootmoist", "pet", "npp", "gpp"]


def pick(z, biome, cell):
    idx = np.where(z["biome"] == biome)[0]
    if cell is not None and cell in z["cell"][idx]:
        return int(idx[list(z["cell"][idx]).index(cell)])
    # otherwise: the cell of the block with the median GPP of the truth
    g = z["orig_m4"][idx, :, 9].mean(1)
    return int(idx[np.argsort(g)[len(g) // 2]])


def main():
    S.setup()
    z = np.load(f"{S.DATA}/paper/daily_example_v2.npz", allow_pickle=True)
    iy = YEAR - 2020
    sl = slice(365 * iy, 365 * (iy + 1))
    days = np.arange(1, 366)
    fig, axs = plt.subplots(4, 3, figsize=(S.FULL, 6.4), gridspec_kw=dict(hspace=0.55, wspace=0.28))
    for j, (b, c, name) in enumerate(SITES):
        i = pick(z, b, c)
        t4, t1 = z["orig_m4"][i], z["orig_m1"][i]
        emu = {"gpp": z["emu_gpp"][i], "et": z["emu_interc"][i] + z["emu_transp"][i] + z["emu_evap"][i],
               "soilw": z["emu_soilw"][i]}
        tru = lambda t, k: t[:, 9] if k == "gpp" else (t[:, 1] + t[:, 2] + t[:, 3] if k == "et" else t[:, 6])  # noqa: E731
        rows = [("gpp", "GPP (gC m$^{-2}$ d$^{-1}$)"), ("et", "ET (mm d$^{-1}$)"), ("soilw", "Top-metre water (mm)")]
        for r, (k, lab) in enumerate(rows):
            ax = axs[r, j]
            ax.plot(days, tru(t1, k)[sl], color=S.SECOND, lw=0.7, label="A further run of LPJmL-FIT")
            ax.plot(days, tru(t4, k)[sl], color=S.ORIG, lw=0.8, label="Unseen run (truth)")
            ax.plot(days, emu[k][sl], color=S.EMU, lw=1.0, label="Emulator")
            ax.set_xlim(1, 365)
            ax.set_xticks([1, 91, 182, 274], ["Jan", "Apr", "Jul", "Oct"])
            if j == 0:
                ax.set_ylabel(lab)
            S.panel(ax, "abcdefghijkl"[3 * r + j], f"{name}, {YEAR}" if r == 0 else None)
        ax = axs[3, j]
        yrs = np.arange(2021, 2101)
        ann = lambda x: x[365:].reshape(80, 365).sum(1)  # noqa: E731
        ax.plot(yrs, ann(t1[:, 9]), color=S.SECOND, lw=0.8)
        ax.plot(yrs, ann(t4[:, 9]), color=S.ORIG, lw=0.9)
        ax.plot(yrs, ann(emu["gpp"]), color=S.EMU, lw=1.2)
        ax.set_xlim(2021, 2100)
        ax.set_xticks([2030, 2060, 2090])
        if j == 0:
            ax.set_ylabel("Annual GPP (gC m$^{-2}$)")
        S.panel(ax, "abcdefghijkl"[9 + j])
        print(name, "cell", z["cell"][i], "mean annual GPP truth/emu/second:",
              ann(t4[:, 9]).mean().round(0), ann(emu["gpp"]).mean().round(0), ann(t1[:, 9]).mean().round(0))
    h, lab = axs[0, 0].get_legend_handles_labels()
    fig.legend(h[::-1], lab[::-1], loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0.035), fontsize=7)
    S.save(fig, "fig_daily_series")


if __name__ == "__main__":
    main()
