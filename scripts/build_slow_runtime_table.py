#!/usr/bin/env python3
"""Build a RUNTIME-CONSISTENT Component-S training table for the production DRF — GLOBAL multi-cell.

The runtime feeds the DRF a feature row assembled by `flux_feature_vector` (src/components/slow.jl:499-503):

    [bm_inc_cell, growth_eff, water_stress, soilmoist, hmean, hmax, agb, lai, fpc, age_mean, n_prev,
     <boundary tail...>]

ADR 0020 §6 requires S be conditioned at runtime on the SAME channel it was trained on, so this table
reproduces that exact 11-head order + a per-cell slow-boundary tail. Each `ind` row is one living stem in
`individual=true`; emitted `npp`/`agb` are already per-m² (×nind baked in by the C writer), so per-patch
ROW SUMS give per-m² stand totals matching the runtime aggregates (no `nind` factor; CLAUDE.md §3).

RUNTIME-CONSISTENT features (was the Hainich-proxy demo; now real, ADR 0023/0024, global-table spec):
  bm_inc_cell = sum(npp)                         EXACT   (per-m², tree-only patch)
  water_stress= 1 - mean(wscal_mean)             EXACT-in-definition (fast.jl: 1 - wscal_mean)
  soilmoist   = mean over 23 soil layers of swc  REAL    join cell_year_soilmoist_{scen}.parquet (Cell,Year)
                                                          == runtime sum(state.w)/length(state.w) (slow.jl:498)
  hmean       = sum(Height*fpc_ind)/sum(fpc_ind) NEAR-EXACT (fpc-weighted mean height)
  hmax        = max(Height)                       EXACT
  agb         = sum(agb)                           CLOSE   (per-m²; minor C turn_litt/debt offset)
  lai         = C LAI_STAND                        REAL basis, CELL-mean  the C LAI_STAND is emitted per grid
                                                          CELL (patch-averaged); it is joined on (Cell,Year)
                                                          so every one of a cell's ~25 patches shares the
                                                          cell-mean stand LAI. This is the right stand-LAI
                                                          BASIS (vs the old per-crown-sum proxy), but NOT the
                                                          per-patch value the single-stand runtime forms
                                                          (slow.jl:489). Per-patch stand LAI is NOT
                                                          reconstructable from the 29-col ind (no leaf_c/nind;
                                                          CLAUDE.md §3), so cell-mean is the best available —
                                                          a documented approximation for multi-patch cells.
                                                          [OPEN Phase-5 decision: per-patch LAI output, or
                                                          per-CELL training aggregation, to close this.]
  growth_eff  = applied_npp / max(lai, eps)      APPROX  numerator = APPLIED npp (npp>0 & Height>0 stems),
                                                          mirroring the runtime applied_cell/leaf_area
                                                          (fast.jl:353-369) — NOT total bm_inc_cell. Shares
                                                          lai's cell-mean caveat in its denominator.
  fpc         = min(sum(fpc_ind), 1)               NEAR-EXACT
  age_mean    = mean(Age - 1)                      TRUE per-stem mean START-OF-YEAR age (ADR 0024; emitted
                                                          Age is post-increment, runtime feature is pre-aging).
  n_prev      = previous-year n_living (same Cell,Patch)  AR state
  target      = n_living                            demographic count
  boundary    = per-CELL climatological mean of [gdd_5, tas_cold_month, soil_depth] + co2=369 (constant-CO2,
                ADR 0004). Appended TIME-CONSTANT per cell — matches the runtime, which sets s.boundary once
                and re-appends it unchanged every year (slow.jl:503). A per-YEAR boundary would be a
                train/inference shift.

Cell-agnostic pooled training: ONE global forest (the .drf carries no cell identity), with all per-cell
context (boundary, n_init, age0) in a `cell_meta.parquet` SIDECAR the coupled driver reads to build one
`FluxDrivenSlowEmulator` per cell. Sound because the AR ratio target/n_prev (slow.jl:526) cancels count
magnitude, so pooling cells does not conflate their absolute densities.

Writes to $OUT: X.f64 (row-major n×p Float64), y.f64 (n), manifest.txt, cell_meta.parquet. The X ROW ORDER
is deterministic (final sort on Cell,Patch,Year); the streaming aggregate SUMS jitter at ~1e-13 relative
(parallel partial-sum combine order under collect(engine="streaming") is not fixed) — bit-identical output
across runs is NOT guaranteed, only row order + values to ~1e-13.

Usage (SLURM — see slow-drf-pipeline skill §7 for sizing):
  # global historic:
  SCENARIO=historic SEED=1 OUT=/p/tmp/jamirp/emulator_global/slow_runtime_hist python3 scripts/build_slow_runtime_table.py
  # a biome-stratified subset (verification): CELLS=42490,<tropical>,<boreal>,<arid>
  # single-cell Hainich demo (also emits scalar meta for the committed .drf path): CELLS=42490
"""

from __future__ import annotations

import os

import numpy as np
import polars as pl

TREE_TYPES = [1, 2, 3, 4, 5]
BASE = "/p/tmp/jamirp/emulator_global"
IND = {
    "historic": f"{BASE}/ind_hist_seed{{seed}}_all.parquet",
    "ssp370": f"{BASE}/ind_ssp370_seed{{seed}}_all.parquet",
}
SOIL_TBL = {"historic": f"{BASE}/tables/cell_year_soilmoist_hist.parquet",
            "ssp370": f"{BASE}/tables/cell_year_soilmoist_ssp.parquet"}
LAI_TBL = {"historic": f"{BASE}/tables/cell_year_lai_hist.parquet",
           "ssp370": f"{BASE}/tables/cell_year_lai_ssp.parquet"}
CELL_YEAR_FEATS = f"{BASE}/tables/cell_year_feats.parquet"
FIRSTYEAR = {"historic": 2000, "ssp370": 2020}

# runtime head order — MUST equal src/components/slow.jl::flux_feature_vector
HEAD_COLS = ["bm_inc_cell", "growth_eff", "water_stress", "soilmoist",
             "hmean", "hmax", "agb", "lai", "fpc", "age_mean", "n_prev"]
BOUNDARY_COLS = ["eco_diag_gdd_5", "tas_cold_month", "soil_depth", "co2"]
CO2_CONST = 369.0        # constant-CO2 regime (ADR 0004); the runtime boundary has no co2 input
EPS = 1.0e-6
MIN_YEARS = 3            # per-cell rows floor for a trustworthy n_init/age0 median


def main() -> int:
    seed = int(os.environ.get("SEED", "1"))
    scenario = os.environ.get("SCENARIO", "historic")
    if scenario not in IND:
        raise SystemExit(f"SCENARIO must be one of {list(IND)} (got {scenario!r})")
    cells = [int(c) for c in os.environ.get("CELLS", "").split(",") if c.strip()] or None
    default_out = f"{BASE}/slow_runtime_{scenario}" + (f"_seed{seed}" if seed != 1 else "")
    out_dir = os.environ.get("OUT", default_out)
    os.makedirs(out_dir, exist_ok=True)
    firstyear = FIRSTYEAR[scenario]

    # --- streaming aggregate straight from the LazyFrame (projection+predicate pushdown) ---
    filt = pl.col("Type").is_in(TREE_TYPES) & (pl.col("isdead") == 0)
    if cells:
        filt = filt & pl.col("Cell").is_in(cells)
    agg = (
        pl.scan_parquet(IND[scenario].format(seed=seed)).filter(filt)
        .group_by(["Cell", "Patch", "Year"]).agg(
            pl.len().alias("n_living"),
            pl.col("npp").sum().alias("bm_inc_cell"),
            # APPLIED npp = non-stagnating stems only (npp>0 & Height>0), mirroring the runtime applied_cell
            # (fast.jl:353-369: a cohort with bm_net<=0 i.e. bm_ind<=0, or height<=0, contributes 0). This is
            # the growth_eff numerator; bm_inc_cell (total) stays the head[0] flux. Approximation of the
            # per-cohort bm_net rule — exact parity is not reconstructable from the 29-col ind output.
            pl.col("npp").filter((pl.col("npp") > 0) & (pl.col("Height") > 0)).sum().alias("_applied_npp"),
            (pl.col("Height") * pl.col("fpc_ind")).sum().alias("_hfpc"),
            pl.col("fpc_ind").sum().alias("_fpc_sum"),
            pl.col("Height").max().alias("hmax"),
            pl.col("agb").sum().alias("agb"),
            pl.col("wscal_mean").mean().alias("_wscal_mean"),
            ((pl.col("Age") - 1).mean()).cast(pl.Float64).alias("age_mean"),
        )
        .collect(engine="streaming")
    )
    print(f"== scenario={scenario} seed={seed} cells={'ALL' if not cells else cells}: "
          f"{agg.height} (Cell,Patch,Year) groups")

    agg = agg.with_columns(
        (1.0 - pl.col("_wscal_mean")).alias("water_stress"),
        (pl.col("_hfpc") / pl.max_horizontal(pl.col("_fpc_sum"), pl.lit(EPS))).alias("hmean"),
        pl.min_horizontal(pl.col("_fpc_sum"), pl.lit(1.0)).alias("fpc"),
    )

    # --- REAL feature joins (soilmoist, lai); inner + height-assert = the anti-NaN guard ---
    # SOIL_TBL_PATH/LAI_TBL_PATH override the scenario defaults (subset verification, seed/scenario variants).
    sm = pl.read_parquet(os.environ.get("SOIL_TBL_PATH", SOIL_TBL[scenario])).select(["Cell", "Year", "soilmoist"])
    lai = pl.read_parquet(os.environ.get("LAI_TBL_PATH", LAI_TBL[scenario])).select(["Cell", "Year", "lai"])
    h0 = agg.height
    cells_before = set(agg["Cell"].unique().to_list())
    agg = agg.join(sm, on=["Cell", "Year"], how="inner").join(lai, on=["Cell", "Year"], how="inner")
    dropped = h0 - agg.height
    drop_frac = dropped / max(h0, 1)
    cells_lost = cells_before - set(agg["Cell"].unique().to_list())
    print(f"== after soilmoist+lai inner-join: {agg.height} rows ({dropped} dropped, {drop_frac:.4f}); "
          f"{len(cells_lost)} cells fully lost")
    # COVERAGE GATE (the anti-silent-drop guard): soilmoist+lai should cover every tree (Cell,Year). A large
    # drop or an entirely-lost cell = a coverage hole in a feature table (e.g. an incomplete LAI_STAND run) —
    # fail loud rather than silently train on a biome-truncated global set.
    if drop_frac > 0.02 or cells_lost:
        raise SystemExit(
            f"FATAL: feature-join coverage hole — {dropped} rows ({drop_frac:.3f}) dropped, "
            f"{len(cells_lost)} cells fully lost (e.g. {sorted(cells_lost)[:10]}). "
            f"Check cell_year_soilmoist/cell_year_lai completeness for scenario={scenario}.")
    agg = agg.with_columns(
        (pl.col("_applied_npp").fill_null(0.0) / pl.max_horizontal(pl.col("lai"), pl.lit(EPS))).alias("growth_eff"))

    # --- AR state: previous-year n_living for the SAME (Cell,Patch) ---
    ar = (agg.select(["Cell", "Patch", "Year", "n_living"])
          .with_columns((pl.col("Year") + 1).alias("Year")).rename({"n_living": "n_prev"}))
    tbl = agg.join(ar, on=["Cell", "Patch", "Year"], how="inner")  # drops the first year per (Cell,Patch)

    # --- per-CELL boundary (climatological mean; time-constant → matches runtime s.boundary) ---
    cyf = (pl.scan_parquet(CELL_YEAR_FEATS)
           .select(["Cell", "eco_diag_gdd_5", "tas_cold_month", "soil_depth"])
           .group_by("Cell").mean().collect())
    tbl = (tbl.join(cyf, on="Cell", how="left").with_columns(pl.lit(CO2_CONST).alias("co2")))
    tbl = tbl.sort(["Cell", "Patch", "Year"])  # MUST sort AFTER all joins → deterministic X row order
    n = tbl.height
    if n == 0:
        raise SystemExit("FATAL: 0 training rows after joins (check feature-table coverage / cells).")
    print(f"== {n} training rows (with AR state)")

    # --- X / y ---
    colnames = HEAD_COLS + BOUNDARY_COLS
    X = tbl.select(colnames).to_numpy().astype("<f8", copy=False)  # C-contiguous row-major n×15 (no-op copy on x86 LE)
    y = tbl["n_living"].to_numpy().astype("<f8", copy=False)
    assert not np.isnan(X).any(), "NaN in X (join coverage hole slipped through)"
    assert np.isfinite(X).all(), "non-finite in X"

    # --- per-cell seed sidecar (n_init/age0/boundary) with a MIN_YEARS floor ---
    cell_meta = (tbl.group_by("Cell").agg(
        pl.col("n_living").median().alias("n_init"),
        pl.col("age_mean").median().alias("age0"),
        pl.col("eco_diag_gdd_5").first(),
        pl.col("tas_cold_month").first(),
        pl.col("soil_depth").first(),
        pl.col("co2").first(),
        pl.len().alias("n_rows"),
    ).sort("Cell"))
    weak = cell_meta.filter(pl.col("n_rows") < MIN_YEARS).height
    if weak:
        print(f"== NOTE: {weak} cells have < {MIN_YEARS} rows (their n_init/age0 medians are less robust)")
    cell_meta.write_parquet(os.path.join(out_dir, "cell_meta.parquet"))

    X.tofile(os.path.join(out_dir, "X.f64"))
    y.tofile(os.path.join(out_dir, "y.f64"))
    p = len(colnames)
    with open(os.path.join(out_dir, "manifest.txt"), "w") as f:
        f.write(f"n\t{n}\n")
        f.write(f"p\t{p}\n")
        f.write(f"nhead\t{len(HEAD_COLS)}\n")
        f.write(f"nboundary\t{len(BOUNDARY_COLS)}\n")
        f.write("colnames\t" + " ".join(colnames) + "\n")
        f.write(f"target\tn_living\n")
        f.write(f"scenario\t{scenario}\n")
        f.write(f"ncells\t{tbl['Cell'].n_unique()}\n")
        f.write(f"firstyear\t{firstyear}\n")
        f.write("cell_meta\tcell_meta.parquet\n")
        # single-cell demo: ALSO emit the scalar boundary/n_init/age0 so train_slow_drf.jl (unchanged)
        # still produces the committed Hainich demo meta (slow-drf-pipeline step 2).
        if cells and len(cells) == 1:
            bvals = [float(cell_meta[c][0]) for c in ["eco_diag_gdd_5", "tas_cold_month", "soil_depth"]] + [CO2_CONST]
            f.write("boundary\t" + " ".join(repr(v) for v in bvals) + "\n")
            f.write(f"n_init\t{float(cell_meta['n_init'][0])}\n")
            f.write(f"age0\t{float(cell_meta['age0'][0])}\n")
            f.write(f"cells\t{','.join(str(c) for c in cells)}\n")

    print(f"== wrote X {X.shape}, y ({n},), cell_meta ({cell_meta.height} cells), manifest to {out_dir}")
    print(f"== target n_living: min={int(y.min())} max={int(y.max())} median={np.median(y):.1f} mean={y.mean():.2f}")
    for j, c in enumerate(colnames):
        print(f"     {c:16s} min={X[:, j].min():12.4g} max={X[:, j].max():12.4g} mean={X[:, j].mean():12.4g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
