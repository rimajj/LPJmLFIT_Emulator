#!/usr/bin/env python3
"""Figure: the emulator run on the full 0.5 deg grid (ADR 0341): retrained on M. Billing's GFDL-ESM4 r1_1 runs of
LPJmL-FIT (nitrogen off), anchored on each cell's own 1985-2014 state, each future scenario emulated by the fold that
never saw it. (a-c) vegetation carbon 2071-2100 under SSP3-7.0; (d, e) global totals 1985-2100, in % of the original's
1985-2014 mean. Sources: global_emu/{emu,orig}/<scen>/ (scripts/glob_emu.py)."""

import matplotlib.colors as mc
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import style as S

G = f"{S.DATA}/global_emu"
SCEN = [("ssp126", "SSP1-2.6", S.NULL1), ("ssp245", "SSP2-4.5", S.YELLOW), ("ssp370", "SSP3-7.0", S.RED)]


def sm(x, k=5):
    """centred running mean, k years, shrinking window at the ends"""
    x = np.asarray(x, float)
    return np.array([np.nanmean(x[max(0, i - k // 2): i + k // 2 + 1]) for i in range(len(x))])


def grid(v, st):
    img = np.full((360, 720), np.nan)
    img[st["ilat"].to_numpy(), st["ilon"].to_numpy()] = v
    return img


def orig_stand(scen, q):
    d = pl.read_parquet(f"{G}/orig/{scen}/stand.parquet").select("Cell", "Year", q)
    return d


def main():
    S.setup()
    st = pl.read_parquet(f"{G}/static.parquet").sort("Cell")
    area = st["area_km2_approx"].to_numpy()
    rock = st["rock"].to_numpy().astype(bool)

    # --- maps: vegetation carbon 2071-2100, SSP3-7.0
    e = np.load(f"{G}/emu/ssp370/annual.npz")
    yrs = e["years"]
    ve = np.nanmean(e["vegc"][:, yrs >= 2071], 1)
    o = orig_stand("ssp370", "vegc").filter(pl.col("Year") >= 2071).group_by("Cell").agg(pl.col("vegc").mean())
    vo = np.full(len(st), np.nan)
    vo[o["Cell"].to_numpy()] = o["vegc"].to_numpy()
    for v in (ve, vo):
        v[rock] = np.nan
    fig = plt.figure(figsize=(S.FULL, 5.0))
    gs = fig.add_gridspec(2, 3, height_ratios=[0.8, 1], hspace=0.38, wspace=0.28)
    cmap = mc.LinearSegmentedColormap.from_list("b", ["#f7f6f2"] + S.BLUES[1:])
    norm = mc.Normalize(0, 25)
    for j, (v, title) in enumerate(((vo, "LPJmL-FIT"), (ve, "Emulator"))):
        ax = fig.add_subplot(gs[0, j])
        im = ax.imshow(grid(v / 1e3, st)[::-1], extent=(-180, 180, -90, 90), cmap=cmap, norm=norm,
                       interpolation="nearest")
        ax.set_ylim(-58, 84)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(False)
        for sp in ax.spines.values():
            sp.set_visible(False)
        S.panel(ax, "abc"[j], title)
    cb = fig.colorbar(im, ax=fig.axes[:2], orientation="horizontal", fraction=0.05, pad=0.03, shrink=0.6)
    cb.set_label("Vegetation carbon 2071–2100, SSP3-7.0 (kgC m$^{-2}$)")
    ax = fig.add_subplot(gs[0, 2])
    diff = (ve - vo) / 1e3
    dn = mc.TwoSlopeNorm(0, -5, 5)
    dcm = mc.LinearSegmentedColormap.from_list("d", [S.DIV_NEG, S.DIV_MID, S.DIV_POS])
    im2 = ax.imshow(grid(np.where(vo > 500, diff, np.nan), st)[::-1], extent=(-180, 180, -90, 90), cmap=dcm,
                    norm=dn, interpolation="nearest")
    ax.set_ylim(-58, 84)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for sp in ax.spines.values():
        sp.set_visible(False)
    S.panel(ax, "c", "Difference (b − a)")
    cb2 = fig.colorbar(im2, ax=ax, orientation="horizontal", fraction=0.05, pad=0.03, shrink=0.9)
    cb2.set_label("kgC m$^{-2}$")

    # --- global totals as % of the original's 1985-2014 mean
    def tot_stand(scen, q, src):
        if src == "emu":
            z = np.load(f"{G}/emu/{scen}/annual.npz")
            x = z[q].copy()
            x[rock] = np.nan
            return z["years"], np.nansum(x * area[:, None], 0)
        d = orig_stand(scen, q).filter(pl.col("Cell").is_in(np.where(~rock)[0]))
        d = d.with_columns(pl.col(q).fill_nan(None)).join(
            pl.DataFrame({"Cell": np.arange(len(st), dtype=np.int32), "a": area}), on="Cell")
        t = d.group_by("Year").agg((pl.col(q) * pl.col("a")).sum()).sort("Year")
        return t["Year"].to_numpy(), t[q].to_numpy()

    def tot_gpp(scen, src):
        if src == "emu":
            z = np.load(f"{G}/emu/{scen}/monthly.npz")
            x = z["gpp"].sum(2)
            x[rock] = np.nan
            return z["years"], np.nansum(x * area[:, None], 0)
        f = "gpp_1985_2014.npy" if scen == "historical" else "gpp_2015_2100_transient.npy"
        x = np.load(f"{G}/orig/{scen}/{f}").sum(2)
        x[rock] = np.nan
        y0 = 1985 if scen == "historical" else 2015
        return np.arange(y0, y0 + x.shape[1]), np.nansum(x * area[:, None], 0)

    for k, (fun, lab, letter) in enumerate(((lambda s, src: tot_stand(s, "vegc", src), "Vegetation carbon, global", "d"),
                                             (tot_gpp, "GPP, global (5-yr mean)", "e"))):
        ax = fig.add_subplot(gs[1, k * 1.5 if False else slice(0, 1) if k == 0 else slice(1, 2)])
        yh, oh = fun("historical", "orig")
        ref = np.nanmean(oh)
        _, eh = fun("historical", "emu")
        ax.plot(yh, 100 * (sm(oh) / ref - 1), color=S.ORIG, lw=1.2)
        ax.plot(yh, 100 * (sm(eh) / ref - 1), color=S.ORIG, lw=1.2, ls="--")
        for sc, name, col in SCEN:
            y, ov = fun(sc, "orig")
            _, ev = fun(sc, "emu")
            ax.plot(y, 100 * (sm(ov) / ref - 1), color=col, lw=1.2, label=f"{name}, LPJmL-FIT")
            ax.plot(y, 100 * (sm(ev) / ref - 1), color=col, lw=1.2, ls="--", label=f"{name}, emulator")
        ax.axvline(2014.5, color=S.GRID, lw=0.8)
        ax.set_xlim(1985, 2100)
        if k == 0:
            ax.set_ylabel("Change vs 1985–2014 (%)")
        S.panel(ax, letter, lab)
        if k == 0:
            hh = [plt.Line2D([], [], color=S.ORIG, lw=1.2, label="LPJmL-FIT"),
                  plt.Line2D([], [], color=S.ORIG, lw=1.2, ls="--", label="Emulator")] + \
                 [plt.Line2D([], [], color=c, lw=3, label=n) for _, n, c in SCEN]
    axl = fig.add_subplot(gs[1, 2])
    axl.axis("off")
    axl.legend(handles=hh, loc="center left", fontsize=7)
    S.save(fig, "fig_global")


if __name__ == "__main__":
    main()
