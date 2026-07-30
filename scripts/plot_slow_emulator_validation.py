#!/usr/bin/env python3
"""plot_slow_emulator_validation.py — validation figures that show how well the GLOBAL Component-S count
DRF reproduces LPJmL-FIT tree density (n_living per patch), using the K-fold-BY-CELL OUT-OF-SAMPLE
predictions from eval_slow_drf.jl (genuine generalization, NOT in-sample fit).

Inputs (all under OUT, the runtime-consistent table dir): y.f64 (observed n_living), preds_oos.f64
(cross-validated prediction, aligned to rows), cells.i64 (per-row orderA Cell), cell_meta.parquet
(per-cell gdd5/tas_cold). GRID grid.nc maps cellid[lat,lon] -> orderA Cell (VERIFIED cellid[51.25,10.25]
== 42490 Hainich). Values are averaged over patches + years to one number per cell for the maps.

Figures written to FIGDIR (default figures/emulator_validation/<SCENARIO>/):
  01_map_observed.png   02_map_predicted.png   03_map_bias.png    (global maps, 280x720)
  04_scatter_density.png (per-row hexbin)       05_scatter_percell.png (per-cell means)
  06_distribution.png    (obs vs pred count histogram)
  07_error_by_latitude.png   08_error_by_gdd5.png   (where it works / fails)
  metrics.txt            (OOS R², RMSE, bias, per-cell R², n)
  [COPULA_OUT] 09_trait_marginals   10_trait_percell_median   11_trait_ks_map + metrics_traits.txt
  [COPULA_OUT + X.f64] 12_biomass_percell   13_map_biomass + metrics_biomass.txt

STAND BIOMASS (figs 12/13) is a COMPOSITE of the emulator's two halves, both out-of-sample: the count DRF
predicts stems per patch and the copula predicts each stem's `agb`, so
    predicted stand AGB per cell = mean_OOS(n_living) x mean_OOS(per-stem agb)
against the same product formed from LPJmL-FIT's own stems, and against the C's own per-patch stand AGB
(the `agb` column of X, = `sum(agb)` over the patch's stems).

That product is an EXACT identity when both tables cover the same (Cell,Patch,Year) rows, because the
per-cell per-stem mean is STEM-weighted: `mean(N) x [total agb / total stems] = mean(per-patch stand agb)`.
So `basis_ratio = median(obs_prod / true_stand)` is a ROW-UNIVERSE CONSISTENCY CHECK between the count table
and the copula table — "do the emulator's two halves describe the same rows?" — NOT a statistical
correction. It is non-1 only because the count table drops each scenario's first year (it needs the AR state
`n_prev`), because of any conditioning-join coverage difference, and under `STEM_CAP` because the cap keeps
whole patch-year CLUSTERS. Read it before quoting the biomass R². Both the like-for-like R² (product vs
product) and the end-to-end R² (product vs the C's stand total) go to metrics_biomass.txt, linear and log10.

  OUT=/p/tmp/jamirp/emulator_global/slow_runtime_historic SCENARIO=historic \\
    python3 scripts/plot_slow_emulator_validation.py
ENV: OUT (table dir), SCENARIO (label + default figdir), GRID (grid.nc), FIGDIR, COPULA_OUT (the MODE=copula
table dir → figs 09-13), SKIP_BIOMASS=1 (skip figs 12/13 and their X.f64 pass). The biomass pass streams
X.f64 in row blocks (11.9 GB for ssp370), so run the full set on SLURM; 01-11 alone are login-node light.
"""

from __future__ import annotations

import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import xarray as xr

NCELL_GLOBAL = 67420
GLOBAL_GRID = "/p/tmp/jamirp/esm_land_daily/daily_2000_2019_global_c0_67419_seed1/output/grid.nc"


def r2(obs, pred):
    m = np.isfinite(obs) & np.isfinite(pred)
    o, p = obs[m], pred[m]
    ss = np.sum((p - o) ** 2)
    st = np.sum((o - o.mean()) ** 2)
    return 1.0 - ss / st if st > 0 else 0.0


def ks2(a, b):
    """Two-sample Kolmogorov-Smirnov statistic.

    MODULE-LEVEL ON PURPOSE (was a closure inside `main`): `scripts/score_slow_copula_ks.py` imports THIS
    function so the ADR-0030 gate's criterion 3 ("pooled KS not degraded, <= 0.02") is scored with the same
    estimator that produced the published `metrics_traits.txt` numbers. Two independent copies of one
    definition is the ADR-0031 failure mode -- there is exactly one KS here.

    Closure-free (it reads only its arguments), so hoisting it out of `main` cannot change any figure.
    """
    a = np.sort(a)
    b = np.sort(b)
    v = np.concatenate([a, b])
    return float(np.max(np.abs(np.searchsorted(a, v, "right") / len(a) - np.searchsorted(b, v, "right") / len(b))))


def rmse(obs, pred):
    m = np.isfinite(obs) & np.isfinite(pred)
    return float(np.sqrt(np.mean((pred[m] - obs[m]) ** 2)))


def main() -> int:
    out_dir = os.environ.get("OUT", "/p/tmp/jamirp/emulator_global/slow_runtime_historic")
    scen = os.environ.get("SCENARIO", "historic")
    grid_path = os.environ.get("GRID", GLOBAL_GRID)
    figdir = os.environ.get("FIGDIR", os.path.join("figures", "emulator_validation", scen))
    os.makedirs(figdir, exist_ok=True)

    preds_path = os.path.join(out_dir, "preds_oos.f64")
    if not os.path.isfile(preds_path):
        print(f"FATAL: {preds_path} missing — run scripts/eval_slow_drf.jl first (OUT={out_dir}).", file=sys.stderr)
        return 2
    y = np.fromfile(os.path.join(out_dir, "y.f64"), dtype="<f8")
    pred = np.fromfile(preds_path, dtype="<f8")
    cells = np.fromfile(os.path.join(out_dir, "cells.i64"), dtype="<i8")
    assert len(y) == len(pred) == len(cells), "row-count mismatch between y/preds/cells"
    n = len(y)

    # ---- per-cell means (average over patches + years) ----
    df = pl.DataFrame({"cell": cells, "obs": y, "pred": pred})
    g = (
        df.group_by("cell")
        .agg(pl.col("obs").mean().alias("obs"), pl.col("pred").mean().alias("pred"), pl.len().alias("nrows"))
        .sort("cell")
    )
    cid_ids = g["cell"].to_numpy()
    obs_c = np.full(NCELL_GLOBAL, np.nan)
    pred_c = np.full(NCELL_GLOBAL, np.nan)
    obs_c[cid_ids] = g["obs"].to_numpy()
    pred_c[cid_ids] = g["pred"].to_numpy()
    bias_c = pred_c - obs_c

    # ---- grid geometry (cellid[lat,lon] = orderA Cell index) ----
    grid = xr.open_dataset(grid_path)
    cid = grid["cellid"].values  # [280,720], NaN over ocean
    lat = grid["lat"].values
    lon = grid["lon"].values
    valid = np.isfinite(cid)
    cid_int = cid[valid].astype(np.int64)

    def to_map(percell):
        m = np.full(cid.shape, np.nan)
        m[valid] = percell[cid_int]
        return m

    # ---- metrics ----
    oos_r2, oos_rmse = r2(y, pred), rmse(y, pred)
    cell_r2 = r2(obs_c, pred_c)
    mbias = float(np.nanmean(bias_c))
    ncell = int(np.isfinite(obs_c).sum())
    with open(os.path.join(figdir, "metrics.txt"), "w") as f:
        f.write(f"scenario\t{scen}\n")
        f.write(f"n_rows\t{n}\n")
        f.write(f"n_cells\t{ncell}\n")
        f.write(f"oos_r2_perrow\t{oos_r2:.4f}\n")
        f.write(f"oos_rmse_perrow\t{oos_rmse:.4f}\n")
        f.write(f"percell_mean_r2\t{cell_r2:.4f}\n")
        f.write(f"mean_bias_percell\t{mbias:.4f}\n")
    print(f"== metrics: OOS per-row R²={oos_r2:.4f} RMSE={oos_rmse:.3f} | per-cell-mean R²={cell_r2:.4f} bias={mbias:.3f} | {ncell} cells / {n} rows")

    vmax = float(np.nanpercentile(obs_c, 99))  # shared obs/pred colour scale, robust to outliers

    def savemap(field, title, fname, cmap, vmin, vmax_, sym=False):
        fig, ax = plt.subplots(figsize=(11, 5.2))
        pm = ax.pcolormesh(lon, lat, field, cmap=cmap, vmin=vmin, vmax=vmax_, shading="auto")
        ax.set_title(f"{title} — Component-S count DRF ({scen})", fontsize=11)
        ax.set_xlabel("lon"); ax.set_ylabel("lat")
        ax.set_xlim(-180, 180); ax.set_ylim(lat.min(), lat.max())
        fig.colorbar(pm, ax=ax, shrink=0.8, label="n_living (indiv / patch)" if not sym else "pred − obs")
        fig.tight_layout(); fig.savefig(os.path.join(figdir, fname), dpi=130); plt.close(fig)

    savemap(to_map(obs_c), "Observed mean tree density (LPJmL-FIT truth)", "01_map_observed.png", "viridis", 0, vmax)
    savemap(to_map(pred_c), "Predicted mean tree density (OOS, held-out)", "02_map_predicted.png", "viridis", 0, vmax)
    bvm = float(np.nanpercentile(np.abs(bias_c), 98))
    savemap(to_map(bias_c), "Bias (predicted − observed)", "03_map_bias.png", "RdBu_r", -bvm, bvm, sym=True)

    # ---- per-row density scatter ----
    fig, ax = plt.subplots(figsize=(6, 6))
    m = np.isfinite(y) & np.isfinite(pred)
    hb = ax.hexbin(y[m], pred[m], gridsize=80, bins="log", cmap="magma", mincnt=1)
    lim = float(np.percentile(y[m], 99.5))
    ax.plot([0, lim], [0, lim], "w--", lw=1)
    ax.set_xlim(0, lim); ax.set_ylim(0, lim)
    ax.set_xlabel("observed n_living"); ax.set_ylabel("predicted n_living (OOS)")
    ax.set_title(f"Per-row OOS prediction ({scen})\nR²={oos_r2:.3f}  RMSE={oos_rmse:.2f}  (n={n:,})", fontsize=10)
    fig.colorbar(hb, ax=ax, label="log10(count)"); fig.tight_layout()
    fig.savefig(os.path.join(figdir, "04_scatter_density.png"), dpi=130); plt.close(fig)

    # ---- per-cell mean scatter ----
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(obs_c, pred_c, s=3, alpha=0.25, edgecolors="none")
    lim = float(np.nanpercentile(obs_c, 99.5))
    ax.plot([0, lim], [0, lim], "k--", lw=1)
    ax.set_xlim(0, lim); ax.set_ylim(0, lim)
    ax.set_xlabel("observed cell-mean n_living"); ax.set_ylabel("predicted cell-mean n_living")
    ax.set_title(f"Per-cell means ({scen})  R²={cell_r2:.3f}  ({ncell:,} cells)", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(figdir, "05_scatter_percell.png"), dpi=130); plt.close(fig)

    # ---- distribution comparison ----
    fig, ax = plt.subplots(figsize=(7, 4.5))
    hi = float(np.percentile(y[m], 99))
    bins = np.linspace(0, hi, 60)
    ax.hist(y[m], bins=bins, histtype="step", lw=1.8, label="observed", color="C0", density=True)
    ax.hist(pred[m], bins=bins, histtype="step", lw=1.8, label="predicted (OOS)", color="C3", density=True)
    ax.set_yscale("log")
    ax.set_xlabel("n_living (indiv / patch)"); ax.set_ylabel("density (log)")
    # eval_slow_drf.jl scores the count DRF with DRF.predict = a CONDITIONAL MEAN (a convex combination of
    # training leaf means), NOT a quantile draw the way eval_slow_copula.jl does. So the predicted histogram is
    # narrower than the observed one BY CONSTRUCTION and that is not a distributional miss. Say it on the panel:
    # this figure was captioned "the distributional check the count DRF exists to pass", which overclaims.
    ax.set_title(f"Count distribution: observed vs predicted ({scen})\n"
                 "prediction is a CONDITIONAL MEAN, not a draw — a narrower predicted spread is expected",
                 fontsize=9)
    ax.legend(); fig.tight_layout()
    fig.savefig(os.path.join(figdir, "06_distribution.png"), dpi=130); plt.close(fig)

    # ---- error by latitude band ----
    cell_lat = np.full(NCELL_GLOBAL, np.nan)
    latgrid = np.broadcast_to(lat[:, None], cid.shape)
    cell_lat[cid_int] = latgrid[valid]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    latbins = np.arange(np.floor(lat.min() / 5) * 5, lat.max() + 5, 5)
    idx = np.digitize(cell_lat, latbins)
    centers, rmses, biases = [], [], []
    for b in range(1, len(latbins)):
        sel = (idx == b) & np.isfinite(obs_c) & np.isfinite(pred_c)
        if sel.sum() >= 10:
            centers.append((latbins[b - 1] + latbins[b]) / 2)
            rmses.append(np.sqrt(np.mean((pred_c[sel] - obs_c[sel]) ** 2)))
            biases.append(np.mean(pred_c[sel] - obs_c[sel]))
    ax.plot(centers, rmses, "-o", ms=3, label="RMSE", color="C1")
    ax.plot(centers, biases, "-o", ms=3, label="bias", color="C2")
    ax.axhline(0, color="k", lw=0.6)
    ax.set_xlabel("latitude (°)"); ax.set_ylabel("cell-mean n_living error")
    ax.set_title(f"Skill by latitude band ({scen})", fontsize=10)
    ax.legend(); fig.tight_layout()
    fig.savefig(os.path.join(figdir, "07_error_by_latitude.png"), dpi=130); plt.close(fig)

    # ---- error by gdd5 band (ecological gradient, from cell_meta) ----
    cm_path = os.path.join(out_dir, "cell_meta.parquet")
    if os.path.isfile(cm_path):
        cm = pl.read_parquet(cm_path).select(["Cell", "eco_diag_gdd_5"])
        gdd = np.full(NCELL_GLOBAL, np.nan)
        gdd[cm["Cell"].to_numpy()] = cm["eco_diag_gdd_5"].to_numpy()
        fig, ax = plt.subplots(figsize=(7, 4.5))
        qs = np.nanpercentile(gdd, np.linspace(0, 100, 13))
        qs = np.unique(qs)
        idx = np.digitize(gdd, qs)
        centers, rmses, biases = [], [], []
        for b in range(1, len(qs)):
            sel = (idx == b) & np.isfinite(obs_c) & np.isfinite(pred_c)
            if sel.sum() >= 10:
                centers.append((qs[b - 1] + qs[b]) / 2)
                rmses.append(np.sqrt(np.mean((pred_c[sel] - obs_c[sel]) ** 2)))
                biases.append(np.mean(pred_c[sel] - obs_c[sel]))
        ax.plot(centers, rmses, "-o", ms=3, label="RMSE", color="C1")
        ax.plot(centers, biases, "-o", ms=3, label="bias", color="C2")
        ax.axhline(0, color="k", lw=0.6)
        ax.set_xlabel("growing-degree-days (gdd5)"); ax.set_ylabel("cell-mean n_living error")
        ax.set_title(f"Skill by growing-degree-days ({scen})", fontsize=10)
        ax.legend(); fig.tight_layout()
        fig.savefig(os.path.join(figdir, "08_error_by_gdd5.png"), dpi=130); plt.close(fig)

    # ================= TRAIT-DISTRIBUTION figures (09+) — recruit-trait copula OOS (ADR 0025) =============
    # Gated on COPULA_OUT (the MODE=copula table dir with pred_<axis>.f64 from eval_slow_copula.jl). The
    # copula's fidelity target is the per-axis MARGINAL: for each held-out cell, the OOS-predicted marginal
    # (one copula draw per surviving stem, from forests that never saw the cell) vs the LPJmL-FIT survivor
    # marginal (Y_<axis>). KS + 1-Wasserstein are computed dependency-light (no scipy).
    copula_out = os.environ.get("COPULA_OUT", "")
    # per-cell observed/predicted medians of each STRUCT axis, harvested in the loop below and consumed by the
    # biomass composite (figs 12/13). Empty ⇒ no struct axes ⇒ no biomass figures.
    struct_percell: dict[str, tuple] = {}
    cop_scenario = ""      # the copula table's own `scenario` line; "pooled" disables the biomass composite
    cop_stem_cap = 0       # `stem_cap` if the table records it (tables built before 2026-07-29 do not)
    if copula_out and os.path.isfile(os.path.join(copula_out, "manifest_copula.txt")):
        cman = {}
        for ln in open(os.path.join(copula_out, "manifest_copula.txt")):
            parts = ln.rstrip("\n").split("\t")
            if len(parts) == 2:
                cman[parts[0]] = parts[1]
        caxes = cman["axes"].split()
        # The OPT-IN diagnostic STRUCTURE axes (`agb`, `Height`) are APPENDED after the 4 production trait
        # axes and never enter the .rcop (ADR 0025 — line M pins that artifact). Absent manifest lines ⇒ none,
        # so a pre-struct table dir plots exactly as before. They are tagged [diag] in every panel + metric so
        # a reader can never mistake a diagnostic axis for a production one.
        saxes = cman.get("struct_axes", "").split()
        allax = caxes + saxes
        cop_scenario = cman.get("scenario", "")
        cop_stem_cap = int(cman.get("stem_cap", "0") or 0)
        ccells = np.fromfile(os.path.join(copula_out, "cells.i64"), dtype="<i8")

        qs = np.array([0.05, 0.25, 0.5, 0.75, 0.95])
        tm = open(os.path.join(figdir, "metrics_traits.txt"), "w")
        tm.write(f"scenario\t{scen}\naxes\t{' '.join(caxes)}\n")
        if saxes:
            tm.write(f"struct_axes\t{' '.join(saxes)}\n")
        # panel grid sized to the axis count (4 production → 2x2, +2 struct → 2x3); never a hard-coded 2x2,
        # which silently dropped any axis past the fourth.
        ncol = 3 if len(allax) > 4 else 2
        nrow = int(np.ceil(len(allax) / ncol))
        fig9, ax9 = plt.subplots(nrow, ncol, figsize=(5.5 * ncol, 4.0 * nrow)); ax9 = np.ravel(ax9)
        fig10, ax10 = plt.subplots(nrow, ncol, figsize=(5.5 * ncol, 4.0 * nrow)); ax10 = np.ravel(ax10)
        for _a in ax9[len(allax):]:
            _a.set_visible(False)
        for _a in ax10[len(allax):]:
            _a.set_visible(False)
        ks_maps = []
        for ai, ax in enumerate(allax):
            is_struct = ax in saxes
            tag = " [diag]" if is_struct else ""
            obs = np.fromfile(os.path.join(copula_out, f"Y_{ax}.f64"), dtype="<f8")
            prd = np.fromfile(os.path.join(copula_out, f"pred_{ax}.f64"), dtype="<f8")
            oq = np.quantile(obs, qs); pq = np.quantile(prd, qs); iqr = oq[3] - oq[1]
            nq = float(np.sqrt(np.mean((pq - oq) ** 2)) / iqr) if iqr > 0 else float("nan")
            # The scale-FREE companion to nqrmse, and the number to quote on a heavy-tailed axis: the median
            # RELATIVE error across the five quantiles. `nqrmse` divides every quantile's error by ONE IQR, so on
            # per-stem `agb` (IQR ~ 25, q95 ~ 3300) the q95 term alone contributes ~10 and the metric reads 0.75
            # while every quantile is in fact within a few percent. This one says that directly.
            with np.errstate(invalid="ignore", divide="ignore"):
                rel_q = np.abs(pq - oq) / np.where(np.abs(oq) > 0, np.abs(oq), np.nan)
            med_rel_q = float(np.nanmedian(rel_q))
            pooled_ks = ks2(prd, obs)
            # fig 09 — pooled obs-vs-pred marginal histogram (do the distributions overlap)
            lo, hi = np.percentile(obs, [0.5, 99.5])
            # A heavy-tailed axis (per-stem `agb` spans ~3 to 5e4 gC m-2) is unreadable on a linear axis: 99 %
            # of the mass lands in the first bin and the panel looks like a single spike for BOTH curves, which
            # would hide a real mismatch. Detected from the data (p99.5/median), not hard-coded per axis.
            logx = bool(lo > 0 and np.median(obs) > 0 and hi / np.median(obs) > 20)
            bins = np.geomspace(max(lo, hi * 1e-6), hi, 50) if logx else np.linspace(lo, hi, 50)
            ax9[ai].hist(obs, bins=bins, density=True, alpha=0.5, label="LPJmL-FIT (obs)", color="#4477aa")
            ax9[ai].hist(prd, bins=bins, density=True, alpha=0.5, label="copula OOS", color="#ee6677")
            if logx:
                ax9[ai].set_xscale("log")
            # On a heavy-tailed axis, `nqrmse = RMSE(q05..q95)/IQR` is dominated by the q95 term (per-stem `agb`
            # has q95/IQR of order 10), so it can read ~0.7 while the two distributions are visually
            # indistinguishable and the KS is ~0.01. Say which number to trust IN the panel — this is exactly
            # the "a scale-free metric can move because its scale moved" trap the skill records for nqrmse.
            ax9[ai].set_title(f"{ax}{tag}  nqrmse={nq:.3f}  KS={pooled_ks:.3f}"
                              + ("\n(heavy-tailed: read KS, not nqrmse — the q95 term dominates)" if logx else ""),
                              fontsize=10)
            ax9[ai].legend(fontsize=8)
            # per-cell medians (≥20 stems): how well each cell's trait MEDIAN is predicted. DENSITY-coloured
            # (38k cells saturate a plain scatter, hiding the diagonal — the "totally off" misread) + the
            # per-cell-median Pearson r / Spearman ρ annotated. This is the HONEST per-cell trait skill: SLA
            # strong (r~0.87), D95max/minwscal moderate (~0.75), Wooddens weak (~0.52, regresses to the mean) —
            # the flux+boundary conditioning (which deliberately excludes stand-state, ADR 0025) under-
            # determines the low-signal axes; the POOLED marginal (fig 09) is excellent regardless.
            dfc = pl.DataFrame({"cell": ccells, "obs": obs, "pred": prd})
            medg = (dfc.group_by("cell")
                    .agg(pl.col("obs").median().alias("o"), pl.col("pred").median().alias("p"), pl.len().alias("n"))
                    .filter(pl.col("n") >= 20).sort("cell"))
            mo = medg["o"].to_numpy(); mp = medg["p"].to_numpy()
            r_med = float(np.corrcoef(mo, mp)[0, 1]) if len(mo) > 2 else float("nan")
            ro = np.argsort(np.argsort(mo)); rp = np.argsort(np.argsort(mp))
            rho_med = float(np.corrcoef(ro, rp)[0, 1]) if len(mo) > 2 else float("nan")
            lim = [float(min(mo.min(), mp.min())), float(max(mo.max(), mp.max()))]
            # same skew rule as fig 09, on the per-cell medians: hexbin `xscale="log"` needs strictly positive
            # data, so fall back to linear if any median is <= 0.
            logm = bool(logx and mo.min() > 0 and mp.min() > 0)
            hb_kw = dict(xscale="log", yscale="log") if logm else {}
            ax10[ai].hexbin(mo, mp, gridsize=60, bins="log", cmap="viridis", mincnt=1,
                            extent=(np.log10(lim[0]), np.log10(lim[1]), np.log10(lim[0]), np.log10(lim[1]))
                            if logm else (lim[0], lim[1], lim[0], lim[1]), **hb_kw)
            ax10[ai].plot(lim, lim, "k--", lw=0.8)
            ax10[ai].set_title(f"{ax}{tag} per-cell median  r={r_med:.2f} ρ={rho_med:.2f} (n={len(mo)})",
                               fontsize=10)
            ax10[ai].set_xlabel("observed"); ax10[ai].set_ylabel("predicted")
            ks_pc = np.full(NCELL_GLOBAL, np.nan)
            kss = []
            # per-cell KS: SORT-GROUP ONCE (O(N log N)) instead of a per-cell boolean mask over all N stems
            # (the old `ccells == c` in a loop was O(ncells·N) ≈ 6e12 ops at global scale → the plot timed out).
            order = np.argsort(ccells, kind="stable")
            cs = ccells[order]; po = prd[order]; oo = obs[order]
            uniq, starts = np.unique(cs, return_index=True)
            starts = np.append(starts, len(cs))
            for gi in range(len(uniq)):
                s, e = int(starts[gi]), int(starts[gi + 1])
                if e - s >= 20:
                    k = ks2(po[s:e], oo[s:e]); ks_pc[int(uniq[gi])] = k; kss.append(k)
            ks_maps.append((ax, ks_pc, tag))
            # `kind` lets a consumer (build_slow_validation_report.py) label a diagnostic axis without having
            # to re-read the table manifest.
            tm.write(f"{ax}\tkind\t{'struct' if is_struct else 'trait'}"
                     f"\tpooled_nqrmse\t{nq:.4f}\tmedian_rel_q_err\t{med_rel_q:.4f}"
                     f"\tpooled_KS\t{pooled_ks:.4f}\tmedian_percell_KS\t{np.median(kss):.4f}"
                     f"\tmedian_percell_r\t{r_med:.4f}\tmedian_percell_spearman\t{rho_med:.4f}\tn_cells\t{len(kss)}\n")
            print(f"   {'struct' if is_struct else 'trait '} {ax:10s} pooled nqrmse={nq:.3f} "
                  f"med_rel_q={med_rel_q:.4f} KS={pooled_ks:.3f} "
                  f"median-per-cell KS={np.median(kss):.3f} r={r_med:.3f} ρ={rho_med:.3f}")
            if is_struct:
                # For the biomass COMPOSITE the right per-cell statistic is the MEAN, not the median that
                # figs 09-11 use: a patch's stand total is `n_stems x mean(per-stem agb)` exactly, whereas
                # `n_stems x median` is not that quantity at all on a skewed size distribution. No ≥20-stem
                # filter either — the composite is scored on every cell the count table covers.
                mg = (dfc.group_by("cell")
                      .agg(pl.col("obs").mean().alias("o"), pl.col("pred").mean().alias("p"),
                           pl.len().alias("n")).sort("cell"))
                struct_percell[ax] = (mg["cell"].to_numpy(), mg["o"].to_numpy(), mg["p"].to_numpy(),
                                      mg["n"].to_numpy())
        fig9.suptitle(f"Recruit-trait copula — pooled OOS marginals vs LPJmL-FIT ({scen}); [diag] = structure axis")
        fig9.tight_layout(); fig9.savefig(os.path.join(figdir, "09_trait_marginals.png"), dpi=130); plt.close(fig9)
        fig10.suptitle(f"Recruit-trait copula — per-cell OOS median vs LPJmL-FIT ({scen}); [diag] = structure axis")
        fig10.tight_layout(); fig10.savefig(os.path.join(figdir, "10_trait_percell_median.png"), dpi=130); plt.close(fig10)
        # fig 11 — per-cell KS maps (where the marginal reproduction is good/poor, per axis)
        ncol11 = 3 if len(ks_maps) > 4 else 2
        nrow11 = int(np.ceil(len(ks_maps) / ncol11))
        fig11, ax11 = plt.subplots(nrow11, ncol11, figsize=(7.5 * ncol11, 4.0 * nrow11)); ax11 = np.ravel(ax11)
        for _a in ax11[len(ks_maps):]:
            _a.set_visible(False)
        for ai, (ax, ks_pc, tag) in enumerate(ks_maps):
            pm = ax11[ai].pcolormesh(lon, lat, to_map(ks_pc), cmap="magma_r", vmin=0, vmax=0.6, shading="auto")
            ax11[ai].set_title(f"{ax}{tag} per-cell KS", fontsize=10)
            ax11[ai].set_xlim(-180, 180); ax11[ai].set_ylim(lat.min(), lat.max())
            fig11.colorbar(pm, ax=ax11[ai], shrink=0.7, label="KS")
        fig11.suptitle(f"Recruit-trait copula — per-cell OOS KS statistic ({scen}); [diag] = structure axis")
        fig11.tight_layout(); fig11.savefig(os.path.join(figdir, "11_trait_ks_map.png"), dpi=130); plt.close(fig11)
        tm.close()
        print(f"== wrote trait figures 09-11 + metrics_traits.txt ({len(caxes)} trait + {len(saxes)} struct axes)")

    # ================= STAND BIOMASS (12/13) — the emulator's two halves composed ==========================
    # "Is biomass matched?" is not a single learned target: the count DRF predicts stems per patch and the
    # copula predicts each stem's `agb`. Their product is the emulator's stand-biomass prediction, and both
    # factors here are OUT-OF-SAMPLE (K-fold BY CELL, independently for the two models).
    #
    #     pred_prod(cell) = mean_OOS(n_living) x mean_OOS(per-stem agb)
    #     obs_prod(cell)  = mean(n_living)     x mean(per-stem agb)        <- the SAME functional form
    #     true_stand(cell)= mean over (patch,year) of the C's own per-patch `sum(agb)`  (X column 6)
    #
    # `obs_prod` != `true_stand` in general, for TWO reasons, and `basis_ratio` = median(obs_prod / true_stand)
    # measures their combined size instead of assuming either away:
    #   1. the count table needs the AR state `n_prev`, so it drops each scenario's FIRST YEAR, while the
    #      copula table keeps every year — this is the bulk of the residual 0.8 %;
    #   2. any coverage difference between the two conditioning joins;
    #   3. under `STEM_CAP` the copula table keeps only some of the cell's patch-years (the cap ranks by a
    #      HASH of (Cell,Patch,Year), so it is a CLUSTER subsample — see the builder), while the count factor
    #      is over all of them. That mismatch is why the pooled case is refused outright below.
    #
    # CORRECTED 2026-07-29 after an adversarial audit. This comment used to claim `basis_ratio` measured a
    # negative `Cov(N, mean stem size)` "definitional gap". That is ALGEBRAICALLY FALSE: the per-cell per-stem
    # mean below is STEM-weighted (one row per stem, so `mean` = total agb / total stems), not the mean of
    # per-patch means. Writing R for the cell's row count,
    #     obs_prod = [ (1/R) Σ_r N_r ] · [ Σ_s a_s / Σ_r N_r ] = (1/R) Σ_r Σ_{s∈r} a_s = (1/R) Σ_r stand_agb_r
    # which is `true_stand` EXACTLY — the Σ_r N_r factors cancel and no covariance term survives. So this is a
    # ROW-UNIVERSE CONSISTENCY CHECK between the two tables ("do the emulator's two halves describe the same
    # rows?"), a real and useful thing to measure, and NOT a statistical correction. A reader who wants a pure fidelity number reads `percell_r2_likeforlike`
    # (product vs product, identical form on both sides); a reader who wants the end-to-end answer reads
    # `percell_r2` (product vs the C's stand total), which carries the definitional gap inside it.
    # REFUSED for the POOLED tables, and this is a correctness stop, not caution. The pooled COUNT table is
    # ~81 % ssp370 rows (22.5 M historic + 99.0 M ssp370) while the pooled COPULA table under STEM_CAP=400 is
    # only ~53 % ssp370 stems (19.9 M + 22.3 M). A per-cell mean of each factor therefore weights the two
    # climate regimes differently, so their product is not any cell's stand biomass in either regime — it would
    # be a plausible-looking number with no referent. Per-scenario figure sets are unaffected. (Fixing it needs
    # `Year`/`scenario` alignment between the two tables, i.e. a table-schema change — see ADR 0036 section 6.)
    pooled_here = "pooled" in (cop_scenario, os.environ.get("SCENARIO", ""))
    if copula_out and "agb" in struct_percell and pooled_here:
        print("== SKIP biomass figures 12/13: this is the POOLED pair, whose count and copula tables carry "
              f"different historic:ssp370 weightings (copula stem_cap={cop_stem_cap or 'unrecorded'}). "
              "The composite would multiply factors averaged over different scenario mixes.")
    elif copula_out and "agb" in struct_percell and os.environ.get("SKIP_BIOMASS", "") in ("", "0", "no"):
        xpath = os.path.join(out_dir, "X.f64")
        cman_count = {}
        for ln in open(os.path.join(out_dir, "manifest.txt")):
            parts = ln.rstrip("\n").split("\t")
            if len(parts) >= 2:
                cman_count[parts[0]] = parts[1]
        p_cols = int(cman_count["p"])
        # `agb` column index read from the manifest's own colnames, NOT hard-coded: the feature order is a
        # frozen contract (ADR 0020 §6) but a silently reordered X is exactly the class of bug ADR 0031 was,
        # and an off-by-one here would plot `hmax` as biomass and look plausible.
        colnames = cman_count.get("colnames", "").split()
        if "agb" not in colnames:
            raise SystemExit(f"FATAL: manifest.txt colnames has no `agb` column: {colnames}")
        agb_i = colnames.index("agb")   # = sum(agb) over the patch's stems (build_slow_runtime_table.py:403)
        if os.path.isfile(xpath):
            # stream X.f64 in row blocks and accumulate per-cell sums of column `agb_i` — never materialise
            # the 2.7 GB (historic) / 11.9 GB (ssp370) matrix.
            mm = np.memmap(xpath, dtype="<f8", mode="r", shape=(n, p_cols))
            agb_sum = np.zeros(NCELL_GLOBAL)
            agb_cnt = np.zeros(NCELL_GLOBAL)
            BLK = 2_000_000
            for s in range(0, n, BLK):
                e = min(s + BLK, n)
                cb = cells[s:e]
                agb_sum += np.bincount(cb, weights=np.asarray(mm[s:e, agb_i], dtype=np.float64),
                                       minlength=NCELL_GLOBAL)
                agb_cnt += np.bincount(cb, minlength=NCELL_GLOBAL)
            del mm
            with np.errstate(invalid="ignore", divide="ignore"):
                true_stand = np.where(agb_cnt > 0, agb_sum / np.maximum(agb_cnt, 1), np.nan)

            scells, sobs, spred, snstem = struct_percell["agb"]
            aobs_c = np.full(NCELL_GLOBAL, np.nan); aobs_c[scells] = sobs
            apred_c = np.full(NCELL_GLOBAL, np.nan); apred_c[scells] = spred
            obs_prod = obs_c * aobs_c
            pred_prod = pred_c * apred_c
            # All three must be strictly POSITIVE, not merely finite: the panels below are log-log (per-stem
            # `agb` spans ~1e0..1e5, unreadable linear) and matplotlib silently drops non-positive points from a
            # log axis, which would make the count of plotted cells disagree with the reported n_cells. The C
            # does emit a rare slightly-negative per-stem `agb` (a carbon-debt stem; seed2 historic min
            # −0.31 gC m⁻²), so this is a real case, not a defensive nicety.
            ok = (np.isfinite(obs_prod) & np.isfinite(pred_prod) & np.isfinite(true_stand)
                  & (true_stand > 0) & (obs_prod > 0) & (pred_prod > 0))
            nb = int(ok.sum())
            bio_r2 = r2(true_stand[ok], pred_prod[ok])
            bio_r2_lfl = r2(obs_prod[ok], pred_prod[ok])
            # Stand AGB spans 3+ decades across cells (tens to tens-of-thousands gC m-2), so a LINEAR R² is
            # dominated by the few highest-biomass cells and says almost nothing about the low-biomass
            # semi-arid/boreal tail — which is most of the land area. The log10 R² is the same statistic on
            # the scale the panel is actually plotted on. Report BOTH; they answer different questions.
            bio_r2_log = r2(np.log10(true_stand[ok]), np.log10(pred_prod[ok]))
            med_ratio = float(np.median(pred_prod[ok] / true_stand[ok]))
            bratio = obs_prod[ok] / true_stand[ok]
            basis_ratio = float(np.median(bratio))
            # A MEDIAN-only band hides how many individual cells are off — report the 10th/90th percentiles and
            # the fraction outside +/-10 %, and require the SPREAD to be tight too, not just the centre.
            basis_p10, basis_p90 = (float(v) for v in np.percentile(bratio, [10, 90]))
            basis_frac_bad = float(np.mean(np.abs(bratio - 1.0) > 0.10))
            basis_ok = bool(0.9 <= basis_ratio <= 1.1 and 0.8 <= basis_p10 and basis_p90 <= 1.25)
            with open(os.path.join(figdir, "metrics_biomass.txt"), "w") as f:
                f.write(f"scenario\t{scen}\nn_cells\t{nb}\n")
                f.write(f"percell_r2\t{bio_r2:.4f}\n")
                f.write(f"percell_r2_log10\t{bio_r2_log:.4f}\n")
                f.write(f"percell_r2_likeforlike\t{bio_r2_lfl:.4f}\n")
                f.write(f"median_ratio\t{med_ratio:.4f}\n")
                f.write(f"basis_ratio\t{basis_ratio:.4f}\n")
                f.write(f"basis_ratio_p10\t{basis_p10:.4f}\n")
                f.write(f"basis_ratio_p90\t{basis_p90:.4f}\n")
                f.write(f"basis_frac_over_10pct\t{basis_frac_bad:.4f}\n")
                f.write(f"basis_ok\t{'yes' if basis_ok else 'no'}\n")
                f.write(f"obs_mean_stand_agb\t{float(np.nanmean(true_stand[ok])):.4f}\n")
                f.write(f"pred_mean_stand_agb\t{float(np.nanmean(pred_prod[ok])):.4f}\n")
            print(f"== biomass: per-cell R²={bio_r2:.4f} (log10 {bio_r2_log:.4f}, like-for-like {bio_r2_lfl:.4f}) "
                  f"median pred:obs={med_ratio:.3f} basis_ratio={basis_ratio:.3f} "
                  f"[p10 {basis_p10:.3f} p90 {basis_p90:.3f}, {100 * basis_frac_bad:.1f}% of cells >10% off] "
                  f"({'OK' if basis_ok else 'OUT OF BAND — read fig 12 right panel'}) over {nb} cells")

            # fig 12 — left: the composite vs the C's stand total; right: the basis cross-check
            fig, axs = plt.subplots(1, 2, figsize=(12, 5.6))
            xy = (true_stand[ok], pred_prod[ok])
            lim = [float(np.nanpercentile(xy[0], 0.5)), float(np.nanpercentile(xy[0], 99.5))]
            lim[0] = max(lim[0], 1e-2)
            axs[0].hexbin(xy[0], xy[1], gridsize=60, bins="log", cmap="viridis", mincnt=1,
                          xscale="log", yscale="log",
                          extent=(np.log10(lim[0]), np.log10(lim[1]), np.log10(lim[0]), np.log10(lim[1])))
            axs[0].plot(lim, lim, "k--", lw=0.9)
            axs[0].set_xlabel("observed stand AGB (gC m⁻² per patch, LPJmL-FIT)")
            axs[0].set_ylabel("predicted = OOS count × OOS per-stem AGB")
            axs[0].set_title(f"Stand biomass, out-of-sample ({scen})\nR²={bio_r2:.3f} (log₁₀ {bio_r2_log:.3f})  "
                             f"median pred:obs={med_ratio:.3f}  ({nb:,} cells)", fontsize=10)
            axs[1].hexbin(xy[0], obs_prod[ok], gridsize=60, bins="log", cmap="cividis", mincnt=1,
                          xscale="log", yscale="log",
                          extent=(np.log10(lim[0]), np.log10(lim[1]), np.log10(lim[0]), np.log10(lim[1])))
            axs[1].plot(lim, lim, "k--", lw=0.9)
            axs[1].set_xlabel("observed stand AGB (C's per-patch sum)")
            axs[1].set_ylabel("mean(count) × mean(per-stem AGB), observed")
            axs[1].set_title(f"BASIS cross-check: do the two tables cover the same rows?\nmedian ratio="
                             f"{basis_ratio:.3f}  (p10 {basis_p10:.3f} / p90 {basis_p90:.3f}) — exact identity "
                             f"on matched rows", fontsize=10)
            fig.tight_layout(); fig.savefig(os.path.join(figdir, "12_biomass_percell.png"), dpi=130)
            plt.close(fig)

            # fig 13 — the same three maps the counts get, on stand biomass
            fig, axs = plt.subplots(3, 1, figsize=(11, 13))
            bvmax = float(np.nanpercentile(true_stand[ok], 98))
            for a_, fld, ttl, cm_, vlo, vhi in (
                (axs[0], true_stand, "Observed stand AGB (LPJmL-FIT)", "YlGn", 0, bvmax),
                (axs[1], pred_prod, "Predicted stand AGB (OOS count × OOS per-stem AGB)", "YlGn", 0, bvmax),
                (axs[2], np.where(ok, pred_prod - true_stand, np.nan), "Bias (predicted − observed)",
                 "RdBu_r", -float(np.nanpercentile(np.abs(pred_prod[ok] - true_stand[ok]), 98)),
                 float(np.nanpercentile(np.abs(pred_prod[ok] - true_stand[ok]), 98))),
            ):
                pm = a_.pcolormesh(lon, lat, to_map(fld), cmap=cm_, vmin=vlo, vmax=vhi, shading="auto")
                a_.set_title(f"{ttl} ({scen})", fontsize=10)
                a_.set_xlim(-180, 180); a_.set_ylim(lat.min(), lat.max())
                fig.colorbar(pm, ax=a_, shrink=0.85, label="gC m⁻² per patch")
            fig.tight_layout(); fig.savefig(os.path.join(figdir, "13_map_biomass.png"), dpi=130)
            plt.close(fig)
            print("== wrote biomass figures 12-13 + metrics_biomass.txt")
        else:
            print(f"== SKIP biomass figures: {xpath} not found")

    print(f"== wrote figures to {figdir}/ (01..08 + metrics.txt" + (", 09..11 + metrics_traits.txt" if copula_out else "") + ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
