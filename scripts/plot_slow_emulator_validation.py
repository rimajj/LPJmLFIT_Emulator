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

  OUT=/p/tmp/jamirp/emulator_global/slow_runtime_historic SCENARIO=historic \\
    python3 scripts/plot_slow_emulator_validation.py
ENV: OUT (table dir), SCENARIO (label + default figdir), GRID (grid.nc), FIGDIR. Light — login-node OK.
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
    ax.set_title(f"Count distribution: observed vs predicted ({scen})", fontsize=10)
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

    print(f"== wrote figures to {figdir}/ (01..08 + metrics.txt)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
