#!/usr/bin/env python3
"""Build the biome-scale COUNT-model table for the falsifiable ADR-0020 OOD experiment.

ADR 0020 governs that Component S is **flux-driven, not climate-equilibrium**: it must
condition on F's delivered fluxes + AR state + the slow bioclimatic boundary, and the
climate-only ``DirectEmulator`` is demoted to the OOD benchmark. The falsifiable success
test (ADR 0020 §, ``docs/p1_s_in_loop_design.md`` risk #2): the flux-driven S must BEAT
the climate-only baseline on the **warm+dry OOD holdout** (a space-for-time SSP370 proxy),
at matched in-distribution accuracy.

This script materialises the one table both channels are trained/scored on, so the
comparison is apples-to-apples: one row per (Cell, Patch, Year), carrying

  * target      : ``n_living`` (living tree stems in the patch that year) + n_recruit/n_dead
  * X_flux      : per-patch aggregates of F's delivered per-tree fluxes + mortality drivers
                  (npp/gpp/transp/wscal/minwscal + mort_npp/mort_water/mort_temp/mort),
                  the previous-year count (AR state), this-year patch structure, the slow
                  bioclimatic boundary (gdd5/soil/eco-diagnostics/CO2/lat), and — unless
                  NO_DAILY=1 — the daily within-year flux statistics.  THIS-YEAR RAW CLIMATE
                  IS DROPPED (ADR 0020: F already transformed it).
  * X_clim      : the DirectEmulator channel — this-year raw climate + anomalies + rolling +
                  trend + climatology normals + the SAME slow bioclimatic boundary.
  * holdout     : bool — the warmest+driest decile of the selected cells (climate_zone_holdout).

Cells are a reproducible latitude-stratified sample of tree-bearing cells (seed 42); the
warm+dry decile of that universe is the holdout.  Annual flux drivers are complete for every
cell from the annual ``ind`` parquet (no C re-run, no 186 GB daily read) — NO_DAILY=1 (the
default at scale) skips the per-cell daily read entirely; set NO_DAILY=0 to add the daily
within-year statistics (slow — reads the global daily set per cell).

Usage:
    NCELLS=4000 SEED=1 NO_DAILY=1 OUT=/p/tmp/jamirp/slow_count python3 scripts/build_slow_count_table.py
    CELLS=42490,... SEED=1 NO_DAILY=0 OUT=... python3 scripts/build_slow_count_table.py   # explicit cells
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import polars as pl

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "python" / "src"))
sys.path.insert(0, str(_REPO / "scripts"))
from lpjmlfit_emulator import data as ind_data  # noqa: E402
import build_slow_flux_table as bsft  # noqa: E402  (reuse daily stats + CO2 + boundary cols)

IND_PARQUET = "/p/tmp/jamirp/emulator_global/ind_hist_seed{seed}_all.parquet"
CELL_YEAR_FEATS = "/p/tmp/jamirp/emulator_global/tables/cell_year_feats.parquet"

TREE_TYPES = list(ind_data.TREE_TYPES)  # (1,2,3,4,5) — temperate trees in this schema

# ---- the two channels -----------------------------------------------------------------
# Per-tree flux/mortality drivers the annual ``ind`` output already carries (F's delivered
# signal). Aggregated per patch as mean (and a few maxima) over living trees.
FLUX_TREE_VARS = ["npp", "gpp", "transp", "wscal_mean", "minwscal",
                  "mort_npp", "mort_water", "mort_temp", "mort"]
# this-year patch STATE (structure) — legitimate demographic state, not raw forcing.
STATE_TREE_VARS = ["Height", "agb", "vegc", "LAI", "fpc_ind", "Age"]

# slow bioclimatic boundary SHARED by both channels (ADR 0020 §1c: fluxes don't carry these).
BOUNDARY_COLS = [
    "lat", "soil_code", "soil_depth",
    "eco_diag_gdd_5", "eco_diag_gdd_10", "eco_diag_frost_free_days",
    "eco_diag_vpd_mean", "eco_diag_vpd_max_monthly", "eco_diag_vpd_stress_months",
    "eco_diag_pet_mean", "eco_diag_p_pet_ratio", "eco_diag_water_deficit_months",
    "eco_diag_dry_spell_max", "eco_diag_dry_spell_mean",
    "tas_cold_month", "tas_warm_month", "tas_range", "pr_cv_monthly", "pr_driest_month",
]
# raw this-year climate — the DirectEmulator channel. DROPPED from X_flux (ADR 0020).
CLIMATE_COLS = [
    "temp", "prec", "swrad", "lwrad", "humid",
    "temp_anom", "prec_anom", "swrad_anom",
    "temp_r3", "temp_r5", "temp_r10", "prec_r3", "prec_r5", "prec_r10", "swrad_r5",
    "temp_trend10", "prec_trend10",
    "temp_mean", "temp_sd", "prec_mean", "prec_sd", "swrad_mean", "swrad_sd",
    "lwrad_mean", "lwrad_sd", "humid_mean", "humid_sd",
]


def select_cells(seed: int, ncells: int) -> tuple[list[int], set[int], dict]:
    """Latitude-stratified sample of tree-bearing cells + the warm+dry holdout decile.

    Returns (all_cells, holdout_cells, diagnostics). Deterministic given (seed, ncells).
    """
    # tree-bearing cells: any living tree over the record (cheap projection scan)
    lf = pl.scan_parquet(IND_PARQUET.format(seed=seed))
    tb = (lf.filter(pl.col("Type").is_in(TREE_TYPES) & (pl.col("isdead") == 0))
          .select("Cell").unique().collect())
    tree_cells = set(tb["Cell"].to_list())
    # per-cell static climatology (constant across years) for lat strata + warm/dry stress
    cyf = pl.scan_parquet(CELL_YEAR_FEATS)
    stat = (cyf.filter(pl.col("Cell").is_in(list(tree_cells)))
            .group_by("Cell")
            .agg(pl.col("lat").first(), pl.col("temp_mean").mean(), pl.col("prec_mean").mean())
            .collect().to_pandas())
    # latitude-decile stratified sample (seed 42-style deterministic) capped at ncells
    rng = np.random.default_rng(seed)
    stat = stat.dropna(subset=["lat", "temp_mean", "prec_mean"]).reset_index(drop=True)
    lat = stat["lat"].to_numpy()
    edges = np.quantile(lat, np.linspace(0, 1, 11))
    edges[-1] += 1e-6
    strata = np.clip(np.searchsorted(edges, lat, side="right") - 1, 0, 9)
    per = max(1, ncells // 10)
    keep_idx = []
    for s in range(10):
        idx = np.where(strata == s)[0]
        if len(idx) > per:
            idx = rng.choice(idx, per, replace=False)
        keep_idx.extend(idx.tolist())
    sel = stat.iloc[sorted(keep_idx)].reset_index(drop=True)
    # warm+dry holdout decile of the SELECTED universe (climate_zone_holdout logic)
    tz = (sel["temp_mean"] - sel["temp_mean"].mean()) / sel["temp_mean"].std()
    pz = (sel["prec_mean"] - sel["prec_mean"].mean()) / sel["prec_mean"].std()
    stress = tz - pz  # hot (+) and dry (-prec) => high stress
    thr = np.quantile(stress, 0.90)
    holdout = set(sel.loc[stress >= thr, "Cell"].astype(int).tolist())
    all_cells = sorted(int(c) for c in sel["Cell"].tolist())
    diag = {
        "n_tree_cells_total": len(tree_cells),
        "n_selected": len(all_cells),
        "n_holdout": len(holdout),
        "holdout_temp_mean": float(sel.loc[sel["Cell"].isin(holdout), "temp_mean"].mean()),
        "train_temp_mean": float(sel.loc[~sel["Cell"].isin(holdout), "temp_mean"].mean()),
        "holdout_prec_mean": float(sel.loc[sel["Cell"].isin(holdout), "prec_mean"].mean()),
        "train_prec_mean": float(sel.loc[~sel["Cell"].isin(holdout), "prec_mean"].mean()),
    }
    return all_cells, holdout, diag


def build(cells: list[int], holdout: set[int], seed: int, out_dir: str,
          no_daily: bool) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    ind_path = IND_PARQUET.format(seed=seed)
    lf = pl.scan_parquet(ind_path)
    ind_data.validate_ind_schema(lf.collect_schema().names(), ordered=True)

    trees = lf.filter(pl.col("Cell").is_in(cells) & pl.col("Type").is_in(TREE_TYPES)).collect()
    living = trees.filter(pl.col("isdead") == 0)
    dead = trees.filter(pl.col("isdead") == 1)
    years = sorted(living["Year"].unique().to_list())
    print(f"== {living.height} living tree rows, {len(cells)} cells, years {years[0]}-{years[-1]}")

    # ---- per (Cell,Patch,Year) count target + flux/state aggregates --------------------
    agg_exprs = [pl.len().alias("n_living")]
    for v in FLUX_TREE_VARS:
        agg_exprs.append(pl.col(v).mean().alias(f"flux_{v}_mean"))
    for v in ["npp", "gpp", "mort_npp", "mort_water"]:
        agg_exprs.append(pl.col(v).max().alias(f"flux_{v}_max"))
    for v in STATE_TREE_VARS:
        agg_exprs.append(pl.col(v).mean().alias(f"state_{v}_mean"))
    agg_exprs.append(pl.col("Height").max().alias("state_Height_max"))
    tbl = living.group_by(["Cell", "Patch", "Year"]).agg(agg_exprs)

    n_dead = dead.group_by(["Cell", "Patch", "Year"]).agg(pl.len().alias("n_dead"))
    recruits = (living.filter(pl.col("Age") <= 1)
                .group_by(["Cell", "Patch", "Year"]).agg(pl.len().alias("n_recruit")))
    tbl = (tbl.join(n_dead, on=["Cell", "Patch", "Year"], how="left")
           .join(recruits, on=["Cell", "Patch", "Year"], how="left")
           .with_columns(pl.col("n_dead").fill_null(0), pl.col("n_recruit").fill_null(0)))

    # ---- AR state: previous-year count for the SAME (Cell,Patch) -----------------------
    ar = (tbl.select(["Cell", "Patch", "Year", "n_living"])
          .with_columns((pl.col("Year") + 1).alias("Year"))
          .rename({"n_living": "ar_prev_n_living"}))
    tbl = tbl.join(ar, on=["Cell", "Patch", "Year"], how="left")

    # ---- slow boundary + raw climate from cell_year_feats ------------------------------
    cyf = pl.scan_parquet(CELL_YEAR_FEATS).filter(pl.col("Cell").is_in(cells))
    have = cyf.collect_schema().names()
    keep = ["Cell", "Year"] + [c for c in BOUNDARY_COLS + CLIMATE_COLS if c in have]
    tbl = tbl.join(cyf.select(keep).collect(), on=["Cell", "Year"], how="left")

    # ---- CO2 (slow boundary) -----------------------------------------------------------
    co2 = bsft.load_co2()
    tbl = tbl.with_columns(
        pl.col("Year").map_elements(lambda y: co2.get(y), return_dtype=pl.Float64).alias("co2")
    )

    # ---- optional daily within-year flux statistics (per cell,year) --------------------
    if not no_daily:
        frames = []
        for c in cells:
            frames.append(bsft.daily_flux_stats(c, years).with_columns(pl.lit(c).alias("Cell")))
        daily = pl.concat(frames)
        tbl = tbl.join(daily, on=["Cell", "Year"], how="left")

    # ---- holdout flag ------------------------------------------------------------------
    tbl = tbl.with_columns(pl.col("Cell").is_in(list(holdout)).alias("holdout"))

    tbl = tbl.sort(["Cell", "Patch", "Year"])
    tag = f"seed{seed}"
    path = os.path.join(out_dir, f"slow_count_table_{tag}.parquet")
    tbl.write_parquet(path)
    print(f"== wrote {path}  ({tbl.height} rows x {tbl.width} cols)")

    n_hold_rows = int(tbl.filter(pl.col("holdout")).height)
    report = {
        "table": path, "seed": seed, "no_daily": no_daily,
        "n_rows": tbl.height, "n_cols": tbl.width,
        "n_cells": len(cells), "n_holdout_cells": len(holdout),
        "n_holdout_rows": n_hold_rows, "n_train_rows": tbl.height - n_hold_rows,
        "n_living_range": [int(tbl["n_living"].min()), int(tbl["n_living"].max())],
        "n_living_mean": float(tbl["n_living"].mean()),
        "columns": tbl.columns,
    }
    with open(os.path.join(out_dir, f"slow_count_report_{tag}.json"), "w") as f:
        json.dump(report, f, indent=2, default=float)
    return report


def main() -> int:
    seed = int(os.environ.get("SEED", "1"))
    ncells = int(os.environ.get("NCELLS", "4000"))
    no_daily = os.environ.get("NO_DAILY", "1") == "1"
    out_dir = os.environ.get("OUT", "/p/tmp/jamirp/slow_count")
    explicit = os.environ.get("CELLS", "").strip()
    if explicit:
        cells = [int(c) for c in explicit.split(",") if c.strip()]
        # holdout still by warm/dry among these (or via env HOLDOUT)
        _, holdout, diag = select_cells(seed, ncells)
        holdout = {c for c in cells if c in holdout}
    else:
        cells, holdout, diag = select_cells(seed, ncells)
    print(f"== build_slow_count_table: seed={seed} ncells={len(cells)} "
          f"holdout={len(holdout)} no_daily={no_daily} out={out_dir}")
    print(f"== cell-selection diagnostics: {json.dumps(diag, indent=2, default=float)}")
    rep = build(cells, holdout, seed, out_dir, no_daily)
    print(f"== report: {json.dumps({k: v for k, v in rep.items() if k != 'columns'}, indent=2, default=float)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
