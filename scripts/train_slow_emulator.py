#!/usr/bin/env python
"""Phase 2 — offline slow-emulator (component S) prototype: train + metric panel.

Fits the ported DIRECT climate->distribution emulator (`DirectEmulator`) on a
biome-stratified set of TRAIN cells and evaluates it by rendering a held-out
(warmest+driest decile, a space-for-time SSP proxy) set DIRECTLY, scoring the
pooled predicted distribution against the seed1-vs-seed2 NOISE FLOOR
(`DEVELOPMENT_PLAN.md` §6 Phase-2 gate: "distributional panel passes tolerances;
allocation conserves NPP").

Data (reuse the sibling's DERIVED tables as *data*, per paths.yaml `data.prior_derived`
+ ADR 0012 — the CODE is ported here; the tables are input data):
  - tree / count / frac / feats / npatch : `tables/direct_*_global.parquet`, `cell_year_feats`,
    `cell_npatch` (ready).
  - tree_step (per-tree + fan-out diagnostics + FEATURES + competition) and grass
    (Type 7-9 aggregates) : BUILT here from `ind_hist_seed1_all.parquet` (Types 0-6 = trees,
    7-9 = grass) joined to `cell_year_feats`.
  - noise-floor truth : `ind_hist_seed{1,2}_subset.parquet` (living trees, holdout cells) BUILT here.

Metrics are computed directly (dist_metrics + summarize + a per-cell error + an aggregate
NPP-conservation check) so no matplotlib/lon dependency is needed.

Usage:
  N_CELLS=600 SEED=42 OUT=<dir> python scripts/train_slow_emulator.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python" / "src"))
from lpjmlfit_emulator import train as T  # noqa: E402
from lpjmlfit_emulator.baseline import FANOUT_LIN, FANOUT_LOG, add_competition  # noqa: E402
from lpjmlfit_emulator.features import CLIM, FEATURES, STATIC, TREE_TYPES  # noqa: E402

TABLES = "/p/tmp/jamirp/emulator_global/tables"
IND = "/p/tmp/jamirp/emulator_global/ind_hist_seed{tag}_all.parquet"
GRASS_TYPES = [7, 8, 9]
FANOUT_DIAG = FANOUT_LOG + FANOUT_LIN  # agb,vegc,npp,LAI,fpc_ind,D95,transp + minwscal,k_root
TREE_STEP_EXTRA = FANOUT_DIAG + ["Longevity", "D95max"]  # diagnostics carried per tree


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def build_tree_step(cells, feats_pd):
    """Living trees (Type 0-6) for `cells`, all diagnostics, + FEATURES + competition + logHeight."""
    keep = ["Cell", "Patch", "Year", "Type", "Height", "Age", "SLA", "Wooddens", "beta_root",
            "wscal_mean"] + TREE_STEP_EXTRA
    lf = (pl.scan_parquet(IND.format(tag=1))
          .filter((pl.col("Type").is_in(TREE_TYPES)) & (pl.col("isdead") == 0)
                  & pl.col("Cell").is_in(cells))
          .select(keep))
    tr = lf.collect().to_pandas()
    tr = tr.merge(feats_pd, on=["Cell", "Year"], how="left")
    parts = []
    for _y, g in tr.groupby("Year", sort=False):
        parts.append(add_competition(g))
    tr = pd.concat(parts, ignore_index=True)
    tr["logHeight"] = np.log(tr["Height"].clip(lower=5.0))
    return tr


def build_grass(cells, feats_pd, tree_step):
    """Grass (Type 7-9) aggregates per (Cell,Patch,Year) + tree canopy context + STATIC + CLIM."""
    lf = (pl.scan_parquet(IND.format(tag=1))
          .filter((pl.col("Type").is_in(GRASS_TYPES)) & (pl.col("isdead") == 0)
                  & pl.col("Cell").is_in(cells))
          .group_by(["Cell", "Patch", "Year"])
          .agg(grass_agb=pl.col("agb").sum(), grass_vegc=pl.col("vegc").sum(),
               grass_npp=pl.col("npp").sum(), grass_LAI=pl.col("LAI").sum()))
    gr = lf.collect().to_pandas()
    # tree canopy context per (Cell,Patch,Year)
    ctx = (tree_step.groupby(["Cell", "Patch", "Year"])
           .agg(comp_n=("Height", "size"), comp_meanH=("Height", "mean"),
                comp_maxH=("Height", "max"), comp_totLAI=("LAI", "sum"),
                comp_totfpc=("fpc_ind", "sum")).reset_index())
    ctx["comp_openness"] = (1.0 - ctx["comp_totfpc"]).clip(lower=0.0)
    gr = gr.merge(ctx, on=["Cell", "Patch", "Year"], how="left").fillna(
        {"comp_n": 0, "comp_meanH": 0, "comp_maxH": 0, "comp_totLAI": 0, "comp_totfpc": 0,
         "comp_openness": 1.0})
    gr = gr.merge(feats_pd[["Cell", "Year"] + STATIC + CLIM], on=["Cell", "Year"], how="left")
    return gr


def build_subset(tag, cells, out):
    """Living-tree ind rows (EVAL_VARS) for holdout `cells`, seed `tag` -> {out}/ind_hist_seed{tag}_subset.parquet."""
    cols = ["Year", "Cell", "Patch", "ID", "Type", "isdead"] + T.EVAL_VARS  # keep isdead: load_living re-filters on it
    lf = (pl.scan_parquet(IND.format(tag=tag)))
    have = [c for c in cols if c in lf.collect_schema().names()]
    (lf.filter((pl.col("Type").is_in(TREE_TYPES)) & (pl.col("isdead") == 0)
               & pl.col("Cell").is_in(cells))
       .select(have).collect().write_parquet(f"{out}/ind_hist_seed{tag}_subset.parquet"))


def conservation_npp(model, hold_cells, feats, npatch_map, seed, data_dir):
    """Aggregate NPP conservation: rendered stand-total NPP vs true (seed1) per holdout cell."""
    fh = feats[feats["Cell"].isin(hold_cells)]
    emu = model.render(fh, npatch_map, T.YEARS, np.random.default_rng(seed))
    e = pd.concat([emu[y] for y in T.YEARS], ignore_index=True)
    # per-cell/year total npp per patch -> mean over patches (stand-level), then mean over years
    en = e.groupby(["Cell", "Year", "Patch"])["npp"].sum().groupby(["Cell", "Year"]).mean()
    en = en.groupby("Cell").mean()
    t1 = T.load_living("hist_seed1", hold_cells, T.YEARS, data_dir)
    tn = t1.groupby(["Cell", "Year", "Patch"])["npp"].sum().groupby(["Cell", "Year"]).mean()
    tn = tn.groupby("Cell").mean()
    common = en.index.intersection(tn.index)
    rel = ((en.loc[common] - tn.loc[common]) / tn.loc[common].clip(lower=1e-9)).values
    return {"n_cells": int(len(common)),
            "median_abs_rel_err": float(np.nanmedian(np.abs(rel))),
            "mean_rel_bias": float(np.nanmean(rel)),
            "p90_abs_rel_err": float(np.nanpercentile(np.abs(rel), 90))}


def main():
    n_cells = int(os.environ.get("N_CELLS", 600))
    seed = int(os.environ.get("SEED", 42))
    out = Path(os.environ.get("OUT", "/p/tmp/jamirp/esm_land_emulator_data/phase2_prototype"))
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    log(f"loading feats + selecting {n_cells} biome-stratified cells")
    feats = pl.read_parquet(f"{TABLES}/cell_year_feats.parquet").to_pandas()
    npatch = pl.read_parquet(f"{TABLES}/cell_npatch.parquet").to_pandas()
    npatch_map = dict(zip(npatch["Cell"], npatch["n_patches"]))
    static = feats[feats["Year"] == 2000][["Cell"] + STATIC].drop_duplicates("Cell")  # STATIC has 'lat'

    # biome-stratified sample: quantile-bin by lat, sample evenly
    all_cells = static["Cell"].values
    if n_cells < len(all_cells):
        lat = static.set_index("Cell").loc[all_cells, "lat"].values
        bins = np.quantile(lat, np.linspace(0, 1, 11))
        binidx = np.clip(np.digitize(lat, bins[1:-1]), 0, 9)
        per = max(1, n_cells // 10)
        sel = []
        for b in range(10):
            cb = all_cells[binidx == b]
            sel.extend(rng.choice(cb, min(per, len(cb)), replace=False))
        cells = np.array(sel)
    else:
        cells = all_cells
    st = static[static["Cell"].isin(cells)]
    hold_mode = os.environ.get("HOLDOUT_MODE", "random")  # 'random' (in-distribution) | 'climate_zone' (warm+dry OOD)
    hold_frac = float(os.environ.get("HOLDOUT_FRAC", 0.15))
    if hold_mode == "climate_zone":
        hold = set(T.climate_zone_holdout(st, frac=hold_frac, seed=seed))
    else:
        cc = np.array(sorted(int(c) for c in cells))
        hold = set(int(c) for c in rng.choice(cc, max(1, int(hold_frac * len(cc))), replace=False))
    hold = [int(c) for c in cells if int(c) in hold]
    train_cells = [int(c) for c in cells if int(c) not in set(hold)]
    log(f"cells={len(cells)} train={len(train_cells)} holdout={len(hold)} mode={hold_mode}")

    log("building tree_step (train) + grass (train) from ind parquet")
    ts = build_tree_step([int(c) for c in train_cells], feats)
    gr = build_grass([int(c) for c in train_cells], feats, ts)
    log(f"tree_step rows={len(ts)} grass rows={len(gr)}")

    log("building holdout seed1/seed2 subset parquets")
    build_subset(1, list(hold), out)
    build_subset(2, list(hold), out)

    log("fitting DirectEmulator")
    model = T.train_model(train_cells, npatch_map,
                          tree=f"{TABLES}/direct_tree_global.parquet",
                          count=f"{TABLES}/direct_count_global.parquet",
                          frac=f"{TABLES}/direct_frac_global.parquet",
                          tree_step=ts, grass=gr, seed=seed)
    model.save(out)

    log("rendering holdout + scoring vs noise floor")
    fh = feats[feats["Cell"].isin(hold)][["Cell", "Year"] + FEATURES]
    emu_by = model.render(fh, npatch_map, T.YEARS, np.random.default_rng(seed))
    t1 = T.load_living("hist_seed1", hold, T.YEARS, out)
    t2 = T.load_living("hist_seed2", hold, T.YEARS, out)
    true_by = {y: t1[t1.Year == y] for y in T.YEARS}
    floor_by = {y: t2[t2.Year == y] for y in T.YEARS}
    res = T.dist_metrics(emu_by, true_by, floor_by, T.EVAL_YEARS)
    summ = T.summarize(res, T.EVAL_YEARS)

    log("NPP conservation check")
    cons = conservation_npp(model, hold, feats[["Cell", "Year"] + FEATURES], npatch_map, seed, out)

    report = {"n_cells": len(cells), "n_train": len(train_cells), "n_holdout": len(hold),
              "holdout_mode": hold_mode, "seed": seed, "summary": summ, "npp_conservation": cons}
    (out / "phase2_metrics.json").write_text(json.dumps(report, indent=2, default=str))
    log("=== SUMMARY ===")
    print(json.dumps(report, indent=2, default=str))
    log(f"wrote {out}/phase2_metrics.json")


if __name__ == "__main__":
    main()
