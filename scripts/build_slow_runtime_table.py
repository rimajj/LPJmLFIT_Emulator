#!/usr/bin/env python3
"""Build a RUNTIME-CONSISTENT Component-S training table for the production DRF (P1 Tier-1 Step 4a).

The runtime feeds the DRF a feature row assembled by `flux_feature_vector` (src/components/slow.jl):

    [bm_inc_cell, growth_eff, water_stress, soilmoist, hmean, hmax, agb, lai, fpc, age_mean, n_prev,
     <boundary tail...>]

ADR 0020 §6 requires S be conditioned at runtime on the SAME channel it was trained on, so this table
reproduces that exact 11-head order (then a baked per-cell slow-boundary tail) from the annual `ind`
ground truth. Each `ind` row is one living stem in `individual=true`, and the emitted `npp`/`agb` are
already per-m² (×nind baked in by the C writer — npp_tree.c / agb_tree.c), so per-patch ROW SUMS give
per-m² stand totals matching the runtime aggregates without any `nind` factor (which the 29-col schema
lacks; CLAUDE.md §3).

Feature provenance (see the workflow synthesis + runtime-features report):
  bm_inc_cell = sum(npp)                         EXACT   (per-m², tree-only patch)
  growth_eff  = bm_inc_cell / max(lai, eps)      FAITHFUL (runtime = applied_bm/leaf_area)
  water_stress= 1 - mean(wscal_mean)             EXACT-in-definition (fast.jl:372: 1 - wscal_mean)
  soilmoist   = SOILMOIST_PROXY (const)          PROXY   (coupled-state WHC-fraction; no annual-ind analog)
  hmean       = sum(Height*fpc_ind)/sum(fpc_ind) NEAR-EXACT (fpc-weighted mean height)
  hmax        = max(Height)                       EXACT
  agb         = sum(agb)                           CLOSE   (per-m²; minor C turn_litt/debt offset)
  lai         = sum(LAI)                            PROXY   (ind LAI is per-CROWN; stand LAI needs leaf_c*nind)
  fpc         = min(sum(fpc_ind), 1)               NEAR-EXACT
  age_mean    = Year - firstyear                   RUNTIME-CONSISTENT COUNTER (NOT mean tree Age — the
                                                    runtime s.age is a degenerate uniform elapsed-year
                                                    counter; training on mean(Age) would be a silent
                                                    train/inference shift — the synthesis's biggest risk)
  n_prev      = previous-year n_living (same patch) AR state (target space)
  target      = n_living                            demographic count

The two PROXY channels (soilmoist, lai) and the FAITHFUL growth_eff are documented approximations of the
runtime; the fully runtime-consistent GLOBAL table (C `LAI_STAND` + daily `swc`, many cells) is the
Phase-2 SLURM follow-up. This Hainich-scale table drives the committed demonstration artifact.

Writes to $OUT (default /p/tmp/jamirp/slow_runtime): X.f64 (row-major n x p Float64), y.f64 (n),
manifest.txt (n, p, colnames, boundary values, n_init) — a zero-dep payload train_slow_drf.jl reads with
pure Base IO. Deterministic. Run inside the py311_new conda env.

Usage:
    CELLS=42490 SEED=1 OUT=/p/tmp/jamirp/slow_runtime python3 scripts/build_slow_runtime_table.py
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import polars as pl

TREE_TYPES = [1, 2, 3, 4, 5]
IND_PARQUET = "/p/tmp/jamirp/emulator_global/ind_hist_seed{seed}_all.parquet"
CELL_YEAR_FEATS = "/p/tmp/jamirp/emulator_global/tables/cell_year_feats.parquet"

# runtime head order — MUST equal src/components/slow.jl::flux_feature_vector
HEAD_COLS = ["bm_inc_cell", "growth_eff", "water_stress", "soilmoist",
             "hmean", "hmax", "agb", "lai", "fpc", "age_mean", "n_prev"]
# baked per-cell slow bioclimatic boundary tail (constant per cell → the DRF sees it as constants)
BOUNDARY_COLS = ["eco_diag_gdd_5", "tas_cold_month", "soil_depth", "co2"]

SOILMOIST_PROXY = 0.7   # matches the coupled test SharedState init w = fill(0.7, NSOILLAYER)
EPS = 1.0e-6


def main() -> int:
    seed = int(os.environ.get("SEED", "1"))
    cells = [int(c) for c in os.environ.get("CELLS", "42490").split(",") if c.strip()]
    out_dir = os.environ.get("OUT", "/p/tmp/jamirp/slow_runtime")
    os.makedirs(out_dir, exist_ok=True)

    lf = pl.scan_parquet(IND_PARQUET.format(seed=seed))
    living = (
        lf.filter(pl.col("Cell").is_in(cells) & pl.col("Type").is_in(TREE_TYPES) & (pl.col("isdead") == 0))
        .select(["Cell", "Patch", "Year", "Height", "Age", "npp", "agb", "LAI", "fpc_ind", "wscal_mean"])
        .collect()
    )
    years = sorted(living["Year"].unique().to_list())
    firstyear = years[0]
    print(f"== cells {cells}: {living.height} living-tree rows, years {firstyear}-{years[-1]}")

    # per (Cell,Patch,Year) runtime-order aggregates
    agg = living.group_by(["Cell", "Patch", "Year"]).agg(
        pl.len().alias("n_living"),
        pl.col("npp").sum().alias("bm_inc_cell"),
        pl.col("LAI").sum().alias("lai"),
        (pl.col("Height") * pl.col("fpc_ind")).sum().alias("_hfpc"),
        pl.col("fpc_ind").sum().alias("_fpc_sum"),
        pl.col("Height").max().alias("hmax"),
        pl.col("agb").sum().alias("agb"),
        pl.col("wscal_mean").mean().alias("_wscal_mean"),
    ).with_columns(
        (pl.col("bm_inc_cell") / pl.max_horizontal(pl.col("lai"), pl.lit(EPS))).alias("growth_eff"),
        (1.0 - pl.col("_wscal_mean")).alias("water_stress"),
        pl.lit(SOILMOIST_PROXY).alias("soilmoist"),
        (pl.col("_hfpc") / pl.max_horizontal(pl.col("_fpc_sum"), pl.lit(EPS))).alias("hmean"),
        pl.min_horizontal(pl.col("_fpc_sum"), pl.lit(1.0)).alias("fpc"),
        (pl.col("Year") - firstyear).cast(pl.Float64).alias("age_mean"),
    )

    # AR state: previous-year n_living for the SAME (Cell,Patch)
    ar = (agg.select(["Cell", "Patch", "Year", "n_living"])
          .with_columns((pl.col("Year") + 1).alias("Year"))
          .rename({"n_living": "n_prev"}))
    tbl = agg.join(ar, on=["Cell", "Patch", "Year"], how="inner")  # inner → drops the first year (no AR)
    tbl = tbl.sort(["Cell", "Patch", "Year"])
    print(f"== {tbl.height} training rows (with AR state)")

    # per-cell baked boundary (climatological mean over years) — constant across training rows
    cyf = (pl.scan_parquet(CELL_YEAR_FEATS).filter(pl.col("Cell").is_in(cells))
           .select(["Cell", "Year"] + [c for c in BOUNDARY_COLS if c != "co2"]).collect())
    # co2 is not in cell_year_feats — use a representative constant (constant-CO2 regime, ADR 0004)
    boundary_vals = []
    for c in BOUNDARY_COLS:
        if c == "co2":
            boundary_vals.append(369.0)  # ~year-2000 CO2 ppm (constant-CO2 regime)
        else:
            boundary_vals.append(float(cyf[c].mean()))
    print(f"== baked boundary {BOUNDARY_COLS} = {boundary_vals}")

    colnames = HEAD_COLS + BOUNDARY_COLS
    p = len(colnames)
    n = tbl.height
    X = np.empty((n, p), dtype="<f8")
    for j, c in enumerate(HEAD_COLS):
        X[:, j] = tbl[c].to_numpy().astype("float64")
    for k, c in enumerate(BOUNDARY_COLS):
        X[:, len(HEAD_COLS) + k] = boundary_vals[k]
    y = tbl["n_living"].to_numpy().astype("<f8")
    n_init = float(np.median(y))

    X.tofile(os.path.join(out_dir, "X.f64"))
    y.tofile(os.path.join(out_dir, "y.f64"))
    with open(os.path.join(out_dir, "manifest.txt"), "w") as f:
        f.write(f"n\t{n}\n")
        f.write(f"p\t{p}\n")
        f.write(f"nhead\t{len(HEAD_COLS)}\n")
        f.write(f"nboundary\t{len(BOUNDARY_COLS)}\n")
        f.write("colnames\t" + " ".join(colnames) + "\n")
        f.write("boundary\t" + " ".join(repr(v) for v in boundary_vals) + "\n")
        f.write(f"n_init\t{n_init}\n")
        f.write(f"target\tn_living\n")
        f.write(f"cells\t{','.join(str(c) for c in cells)}\n")
        f.write(f"firstyear\t{firstyear}\n")
    print(f"== wrote X {X.shape}, y ({n},), manifest to {out_dir}")
    print(f"== target n_living: min={int(y.min())} max={int(y.max())} median={n_init} mean={y.mean():.2f}")
    print(f"== feature ranges:")
    for j, c in enumerate(colnames):
        print(f"     {c:14s} min={X[:, j].min():12.4g} max={X[:, j].max():12.4g} mean={X[:, j].mean():12.4g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
