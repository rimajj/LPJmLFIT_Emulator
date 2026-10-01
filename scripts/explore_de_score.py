#!/usr/bin/env python
"""explore_de_score.py -- score ANY Germany emulator output against the LPJmL-FIT reference, identically.

Line X (2026-10-01; SH14 amendments 2026-10-01 round 2). Reference + tolerances: scripts/explore_de_reference.py ->
/p/tmp/jamirp/X_de/reference/. The definition of every statistic and tolerance is in
/p/tmp/jamirp/X_de/reference/_DEFINITION.md. Pre-SH14 copy of this script:
/p/tmp/jamirp/X_de/shared/scorer/backup_pre_SH14/scripts/.

EMULATOR OUTPUT CONTRACT (either format; both reach the same scoring code)
  (A) roster  -- a per-tree annual table, the same columns as the ind parquet. Parquet file, directory (read
      recursively) or glob. Required columns: Year, Cell, Type, isdead, Height, SLA, Wooddens, D95max, minwscal,
      Longevity, agb (any others ignored; dtypes are cast). One row per individual per year, at least every
      LIVING tree taller than 5 m (rows with Type > 6, isdead == 1 or Height < 5 m are dropped by the scorer, so
      emitting them is harmless). Required columns gcm and scen, or pass --gcm/--scen for the whole submission.
      Years map to windows h1985 1985-2014, w2015 2015-2044, w2071 2071-2100, w3071 3071-3100; years outside
      them are ignored. Each window's statistic is normalised by the number of DISTINCT years the submission
      has in that window (reported; a partial window is flagged) and by --npatch patches (default 250).
      Cells: the cells the run covered = --cells file (one int per line; SH14: rows of other cells are now
      FILTERED OUT, they used to abort the reduction) or, by default, every Cell that appears in the submission;
      a covered cell with no living tree in a window scores n_per_patch = 0 (coverage.json lists covered cells
      with no row at all in the file, so a crashed chunk is visible).
      Historical years (1985-2014) should carry scen = "Historical"; a free run that starts in 1985 and is
      labelled with its ssp may instead carry the ssp label: its 1985-2014 rows are then used as that
      scenario's response baseline AND scored as the Historical level.
  (B) stats  -- the per-cell window statistics directly, long format: columns gcm, scen, window, Cell,
      quantity, value (quantity names as in explore_de_reference.QUANTITIES), or wide format: gcm, scen,
      window, Cell + one column per quantity. h1985 rows: scen "Historical" (or the ssp, as in (A)).
  Responses (r2071 = w2071 - h1985, r2015 = w2015 - h1985) are computed by the scorer from the submission's
  own levels. If the submission has no h1985 for a gcm, the reference truth-seed h1985 is used as its baseline
  (flagged baseline=reference) -- i.e. a run initialised from the truth in 2014.
  CONTRASTS (SH14): c2071 = X(scen, 2071-2100) - X(ssp126, 2071-2100) and c2015 likewise, scen in {ssp370,
  ssp245}, computed from the submission's own levels whenever it carries that window for ssp126 AND the other
  scenario of the same gcm (one call with both scenarios: a multi-scen roster, or a --manifest). c2071 is the
  PRIMARY response statistic: CO2-free and free of the 2071 humidity-configuration switch (both legs share it).
  r2071 contains both; ssp245 contrasts also contain the ssp245 binary change (never use them for H4).

USAGE
  score --pred PATH --format roster|stats --label NAME [--gcm G] [--scen S] [--npatch 250] [--cells FILE]
        [--scope all|covered] [--truth-seed 1|2] [--start-seed 1|2] [--out DIR]
  score --manifest M.csv --label NAME [--format ...] [--cells FILE] [--fold-map F] [--truth-seed ..] ...
        manifest = POOLED CROSS-FIT mode: one row per prediction, columns pred (required), and optionally format,
        gcm, scen, cells (a cell-list file), fold (int; the cells of that fold in --fold-map, default
        /p/tmp/jamirp/X_de/shared/registry/folds.parquet). Each row is reduced restricted to ITS cells (cells file,
        or fold, intersected with the global --cells), then all rows are pooled and scored as one submission; a
        (gcm, scen, window, Cell) predicted by two rows is an error. Use it to score each fold model only on its
        own held-out fold (all 52 blocks out-of-place), or to put several scenarios into one call (contrasts).
     -> DIR/<label>/{cells.parquet, summary_quantity.csv, summary_conjunctive.csv, summary_criterion.csv,
                     aggregate_response.csv, coverage.json}  + a printed summary
        and the same at ~1-degree BLOCK scale in DIR/<label>/block/ (blocks = area-weighted means of the per-cell
        statistics over the reference's cells; scope covered uses a block reference built from the covered cells).
        summary_conjunctive.csv carries ceiling_* = the all-cell other-seed null's pass fraction (round 1) and,
        SH14, ceiling_same_* = the other seed's pass fraction on EXACTLY the scored rows (same cells, targets, scale
        and tolerance column): read every arm as a ratio to ceiling_same_*.
  --truth-seed 2 (SH14): truth C = seed 2, replica R = seed 1 (reference *_t2 files); default 1 = round 1.
  --start-seed: metadata only (coverage.json): which seed's roster the run started from; a run started from the
        truth seed's own roster inherits its first decades (flag start_state_shared_with_truth).
  Pass tests: |E - C| <= allowed * (1 + 1e-9). Tolerance columns (pass column): allowed (pass; ADR 0111 stratum
  median, PRIMARY of round 1), allowed_cell (pass_cell; literal per-cell |C-R|/mean(C,R), asymmetric),
  allowed_q90 (pass_q90), allowed_cal (pass_cal; calibrated), and SH14 symmetric ones: allowed_cell_abs
  (pass_cell_abs; max(0.1|C|, |C-R|)), allowed_c (pass_c; stratum median of |C-R|/|C|), allowed_q90_c (pass_q90_c),
  allowed_cal_c (pass_cal_c; calibrated on the symmetric spread).
  nulls [--out DIR] [--truth-seed 1|2] [--cells FILE --scope covered]
                                          -> scores the trivial baselines through the same code (incl. SH14 frozen
                                             nulls); labels carry _t2 for truth seed 2
  selftest                                -> the roster path reproduces the reference statistics (dev subset) + SH14
                                             checks (symmetry, contrasts, truth seed 2, pooled cross-fit, --cells,
                                             frozen; repair: independent contrast recompute, declared-cell misses,
                                             --start-year)
  SH14 REPAIR flags (recorded in coverage.json and printed):
    --start-year Y      the run was initialised from the truth roster of year Y: rows of Y are dropped (else the
                        truth's own roster is scored for 1/30 of h1985, or ALL of it for a 2014 start)
    --held-out-place    true|false|unknown: a whole-dev-set score of a model trained on those cells is IN-PLACE
    --legs-branched     yes|no|unknown: the truth branches every scenario leg from ONE 2014 state with shared
                        random numbers; an arm that does not must read contrasts against ceiling_unbr_lo/hi_* (the
                        bracket for unbranched legs), not ceiling_same_*
  SH14 REPAIR tolerance columns: allowed_cal1 (one multiplier per target kind), allowed_cal_xg / allowed_cal1_xg
    (fitted on the OTHER GCM: the replica's pass under these is an out-of-sample ceiling -- quote it beside every
    block number). The contrast calibration is fitted on ssp370 only. aggregate_response.csv: pass_same is passed
    by the replica by construction where the floor does not bind; read pass_floor_same against floor_binds_same and
    pass_same against p_indep_same_upper (headline: expected_indep_pass_same_determined).
  headline [--label a,b]                  -> DIR/headline.csv (+ headline_aggregate_response.csv), light
Heavy (a full-Germany roster or `nulls`): run on SLURM.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys
import time

import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_reference as R  # noqa: E402

REFDIR = R.OUT
DEFAULT_OUT = f"{R.OUT}/scores"
DEFAULT_FOLD_MAP = f"{R.XDE}/shared/registry/folds.parquet"
LEVEL_WINDOWS = list(R.WINDOWS)
SSPS = ["ssp126", "ssp245", "ssp370"]
ROSTER_COLS = ["Year", "Cell", "Type", "isdead", "Height"] + [t for t in R.TRAITS if t != "Height"]
BLOCK_CACHE_VERSION = "v3"  # SH14 repair: tolerance tables gained cal1/cal_xg/cal1_xg + dev_unbr_*; never reuse v1/v2

# (tolerance column, pass column). The first four are round 1; the last four are SH14 amendment 1.
PASS_COLS = [("allowed", "pass"), ("allowed_cell", "pass_cell"), ("allowed_q90", "pass_q90"),
             ("allowed_cal", "pass_cal"), ("allowed_cell_abs", "pass_cell_abs"), ("allowed_c", "pass_c"),
             ("allowed_q90_c", "pass_q90_c"), ("allowed_cal_c", "pass_cal_c"),
             # SH14 repair: one multiplier per target kind; and both calibrations fitted on the OTHER GCM only
             ("allowed_cal1", "pass_cal1"), ("allowed_cal_xg", "pass_cal_xg"), ("allowed_cal1_xg", "pass_cal1_xg")]
PASS_NAMES = [p for _, p in PASS_COLS]

GROUPS = {
    "panel106": R.PANEL106,
    "extended": R.EXTENDED,
    "count": ["n_per_patch"],
    "traits4_median": [f"{v}_q50" for v in ["SLA", "Wooddens", "D95max", "minwscal"]],
    "traits4_dist": [f"{v}_{q}" for v in ["SLA", "Wooddens", "D95max", "minwscal"] for q in R.QN],
    "size_dist": [f"{v}_{q}" for v in ["Height", "agb"] for q in R.QN],
    "longevity_dist": [f"Longevity_{q}" for q in R.QN],
    "pft_shares": [f"share_{t}" for t in R.PFTS],
    "agb_stand": ["agb_stand"],
}
for _v in R.TRAITS:
    GROUPS[f"{_v}_dist"] = [f"{_v}_{q}" for q in R.QN]

# what each target contains (SH14 amendment 3 labelling; joined onto every summary as target_note)
TARGET_NOTE = {
    "h1985": "level 1985-2014",
    "w2015": "level 2015-2044",
    "w2071": "level 2071-2100; truth has water-stress mortality OFF (relative_humidity missing from the config)",
    "w3071": "level 3071-3100, recycled climate (equilibrium only); truth water-stress mortality OFF",
    "r2015": "response vs 1985-2014; contains the 1985->2020 CO2 rise the emulator does not see",
    "r2071": "response vs 1985-2014; contains the 2071 humidity-configuration switch AND the CO2 rise",
    "c2015": "scenario contrast vs ssp126 at fixed gcm+seed, 2015-2044: CO2-free, same humidity config",
    "c2071": "PRIMARY response: scenario contrast vs ssp126 at fixed gcm+seed, 2071-2100: CO2-free, same "
             "humidity config in both legs",
}


def target_note_expr() -> pl.Expr:
    base = pl.col("window").replace_strict(TARGET_NOTE, default="")
    return (pl.when(pl.col("window").str.starts_with("c") & (pl.col("scen") == "ssp245"))
            .then(base + pl.lit("; ssp245 ran the Feb-2026 binary: scenario + binary contrast, not for H4"))
            .otherwise(base).alias("target_note"))


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


EPS = 1e-9  # relative slack in every pass test: `allowed` is built through divisions and can sit 1 ulp below dev
_TOL: dict = {}


def _sfx(truth_seed: int) -> str:
    return "" if int(truth_seed) == 1 else "_t2"


def tolerance(scale: str = "cell", truth_seed: int = 1) -> pl.DataFrame:
    """scale "cell" = reference/tolerance{,_t2}.parquet; "block" / "block_dev" = reference/<scale>/tolerance*.parquet;
    "blockcache:<dir>" = an on-the-fly block reference for an arbitrary covered cell set."""
    key = (scale, int(truth_seed))
    sfx = _sfx(truth_seed)
    if key not in _TOL:
        if scale == "cell":
            _TOL[key] = pl.read_parquet(f"{REFDIR}/tolerance{sfx}.parquet")
        elif scale.startswith("blockcache:"):
            _TOL[key] = pl.read_parquet(f"{REFDIR}/block_cache/{scale.split(':', 1)[1]}/tolerance.parquet")
        else:
            _TOL[key] = pl.read_parquet(f"{REFDIR}/{scale}/tolerance{sfx}.parquet")
    return _TOL[key]


def block_reference_for(cells: list[int] | None, scope: str, truth_seed: int = 1) -> tuple[str, pl.DataFrame]:
    """Which block reference scores this submission: the full one (scope all), the dev one (scope covered with
    exactly the Cell % 10 == 0 cells), else one built on the fly from the covered cells (cached, versioned)."""
    sfx = _sfx(truth_seed)
    if scope == "all" or cells is None:
        return "block", pl.read_parquet(f"{REFDIR}/block/mask{sfx}.parquet")
    ref_cells = set(tolerance("cell").filter(pl.col("window") == "h1985")["Cell"].unique().to_list())
    cov = sorted(set(cells) & ref_cells)
    if cov == sorted(c for c in ref_cells if c % 10 == 0):
        return "block_dev", pl.read_parquet(f"{REFDIR}/block_dev/mask{sfx}.parquet")
    h = hashlib.sha1(",".join(map(str, cov)).encode()).hexdigest()[:16]
    name = f"{BLOCK_CACHE_VERSION}{sfx}_{h}"
    d = f"{REFDIR}/block_cache/{name}"
    if not os.path.exists(f"{d}/tolerance.parquet"):
        log(f"building block reference (truth seed {truth_seed}) for {len(cov)} covered cells -> {d}")
        r = R.build_block_reference(pl.read_parquet(f"{REFDIR}/levels_long.parquet"), cov, int(truth_seed))
        os.makedirs(d, exist_ok=True)
        R.write_atomic(r["mask"], f"{d}/mask.parquet")
        R.write_atomic(r["tolerance"], f"{d}/tolerance.parquet")
        json.dump({"cells": cov, "truth_seed": int(truth_seed)}, open(f"{d}/cells.json", "w"))
    return f"blockcache:{name}", pl.read_parquet(f"{d}/mask.parquet")


def pred_to_blocks(lev: pl.DataFrame, mask: pl.DataFrame) -> pl.DataFrame:
    """Per-cell prediction levels -> block levels over the reference mask cells (h1985 rows carrying an ssp label
    use the Historical mask). A block with a mask cell the prediction lacks is null (= missing)."""
    x = lev.with_columns(
        pl.when(pl.col("window") == "h1985").then(pl.lit("Historical")).otherwise(pl.col("scen")).alias("mscen"))
    combos = x.select(["gcm", "scen", "mscen", "window"]).unique()
    m = mask.rename({"scen": "mscen"}).join(combos, on=["gcm", "mscen", "window"], how="inner")
    k = ["gcm", "scen", "window", "quantity", "Cell"]
    v = m.join(x.select(k + ["value"]), on=k, how="left")
    b = v.group_by(["gcm", "scen", "window", "quantity", "block"]).agg(
        pl.when(pl.col("value").is_null().any()).then(None).otherwise(
            (pl.col("value") * pl.col("area_km2_approx")).sum() / pl.col("area_km2_approx").sum()).alias("value"))
    return b.rename({"block": "Cell"}).select(["gcm", "scen", "window", "Cell", "quantity", "value"])


# ---------------------------------------------------------------------------------------------------------
# input -> long levels table (gcm, scen, window, Cell, quantity, value) + coverage info
# ---------------------------------------------------------------------------------------------------------
def _files(path: str) -> list[str]:
    if os.path.isdir(path):
        return sorted(glob.glob(f"{path}/**/*.parquet", recursive=True))
    return sorted(glob.glob(path))


def read_cells(path: str | None) -> list[int] | None:
    if not path:
        return None
    return sorted({int(x) for x in open(path).read().split()})


def roster_to_levels(path: str, gcm: str | None, scen: str | None, npatch: int,
                     cells: list[int] | None, drop_years: list[int] | None = None) -> tuple[pl.DataFrame, dict]:
    """drop_years (SH14 repair, --start-year): years whose rows are the run's INITIAL state (a truth roster it was
    started from), not a prediction -- dropped before the window statistics, and recorded in coverage.json."""
    files = _files(path)
    assert files, f"no parquet under {path}"
    lf = pl.scan_parquet(files)
    have = lf.collect_schema().names()
    miss = [c for c in ROSTER_COLS if c not in have]
    assert not miss, f"roster lacks columns {miss}"
    extra = [c for c in ["gcm", "scen"] if c in have]
    sel = [pl.col(c) for c in extra] + [
        pl.col("Year").cast(pl.Int32), pl.col("Cell").cast(pl.Int32), pl.col("Type").cast(pl.Int8),
        pl.col("isdead").cast(pl.Int8),
    ] + [pl.col(t).cast(pl.Float32) for t in R.TRAITS]
    lf = lf.select(sel)
    if "gcm" not in have:
        assert gcm, "roster has no gcm column: pass --gcm"
        lf = lf.with_columns(pl.lit(gcm).alias("gcm"))
    if "scen" not in have:
        assert scen, "roster has no scen column: pass --scen"
        lf = lf.with_columns(pl.lit(scen).alias("scen"))
    cells_filter = cells is not None
    if cells_filter:
        lf = lf.filter(pl.col("Cell").is_in(cells))  # SH14: rows outside the covered cells are dropped
    if drop_years:
        lf = lf.filter(~pl.col("Year").is_in([int(y) for y in drop_years]))
    years = lf.select(["gcm", "scen", "Year"]).unique().collect()
    present = sorted(lf.select("Cell").unique().collect()["Cell"].to_list())
    if cells is None:
        cells = present
    cov = {"files": len(files), "cells_covered": len(cells), "cells_filter": cells_filter,
           "dropped_start_years": [int(y) for y in drop_years] if drop_years else [],
           "cells_without_any_row": sorted(set(cells) - set(present))[:50],
           "n_cells_without_any_row": len(set(cells) - set(present)), "windows": []}
    out = []
    for (g, s), yy in years.group_by(["gcm", "scen"]):
        for w, (y0, y1) in R.WINDOWS.items():
            ys = sorted(y for y in yy["Year"].to_list() if y0 <= y <= y1)
            if not ys:
                continue
            ny = len(ys)
            cov["windows"].append({"gcm": g, "scen": s, "window": w, "n_years": ny, "partial": ny < y1 - y0 + 1})
            cy = pl.DataFrame({"Cell": cells, "n_years": [ny] * len(cells)})
            parts = []
            # chunk by cell blocks of 500 (bounded memory for a full-Germany roster)
            for cb in sorted({c // 500 for c in cells}):
                trees = R.living(
                    lf.filter((pl.col("gcm") == g) & (pl.col("scen") == s) & pl.col("Year").is_between(y0, y1)
                              & ((pl.col("Cell") // 500) == cb))
                ).collect()
                parts.append(R.reduce_window(trees, cy.filter((pl.col("Cell") // 500) == cb), npatch))
            wd = pl.concat(parts).with_columns(
                pl.lit(g).alias("gcm"), pl.lit(s).alias("scen"), pl.lit(w).alias("window"))
            out.append(wd)
            log(f"roster reduced: {g} {s} {w} ({ny} years, {wd.height} cells)")
    wide = pl.concat(out)
    return wide_to_long(wide), cov


def wide_to_long(wide: pl.DataFrame) -> pl.DataFrame:
    q = [c for c in R.QUANTITIES if c in wide.columns]
    return wide.unpivot(index=["gcm", "scen", "window", "Cell"], on=q, variable_name="quantity",
                        value_name="value").with_columns(pl.col("Cell").cast(pl.Int32),
                                                         pl.col("value").cast(pl.Float64))


def stats_to_levels(path: str, gcm: str | None, scen: str | None,
                    cells: list[int] | None = None) -> tuple[pl.DataFrame, dict]:
    d = pl.read_parquet(_files(path)) if not path.endswith(".csv") else pl.read_csv(path)
    if "gcm" not in d.columns:
        d = d.with_columns(pl.lit(gcm).alias("gcm"))
    if "scen" not in d.columns:
        d = d.with_columns(pl.lit(scen).alias("scen"))
    if "quantity" not in d.columns:
        d = wide_to_long(d)
    d = d.select([pl.col("gcm"), pl.col("scen"), pl.col("window"), pl.col("Cell").cast(pl.Int32),
                  pl.col("quantity"), pl.col("value").cast(pl.Float64)])
    unknown = set(d["quantity"].unique().to_list()) - set(R.QUANTITIES)
    assert not unknown, f"unknown quantities {sorted(unknown)}"
    cov = {"cells_filter": cells is not None}
    if cells is not None:
        present = set(d["Cell"].unique().to_list())
        d = d.filter(pl.col("Cell").is_in(cells))
        cov["n_cells_without_any_row"] = len(set(cells) - present)
    cov["cells_covered"] = d["Cell"].n_unique()
    return d, cov


def manifest_to_levels(path: str, default_format: str, npatch: int, cells_global: list[int] | None,
                       fold_map: str, drop_years: list[int] | None = None) -> tuple[pl.DataFrame, dict]:
    """POOLED CROSS-FIT (SH14 amendment 5): every manifest row is reduced restricted to its own cells, then pooled."""
    m = pl.read_csv(path, infer_schema_length=0)  # all strings
    assert "pred" in m.columns, "manifest needs a pred column"
    fm = None
    parts, rows = [], []
    declared: set | None = set()
    for i, r in enumerate(m.iter_rows(named=True)):
        fmt = (r.get("format") or default_format).strip()
        cells = read_cells(r.get("cells")) if r.get("cells") else None
        if r.get("fold"):
            if fm is None:
                fm = (pl.read_parquet(fold_map) if fold_map.endswith(".parquet") else pl.read_csv(fold_map)).select(
                    [pl.col("Cell").cast(pl.Int32), pl.col("fold").cast(pl.Int32)])
            fc = sorted(fm.filter(pl.col("fold") == int(r["fold"]))["Cell"].to_list())
            cells = fc if cells is None else sorted(set(cells) & set(fc))
        if cells_global is not None:
            cells = cells_global if cells is None else sorted(set(cells) & set(cells_global))
        if cells is None or declared is None:
            declared = None
        else:
            declared |= set(cells)
        if fmt == "roster":
            lev, cov = roster_to_levels(r["pred"], r.get("gcm"), r.get("scen"), npatch, cells, drop_years)
        else:
            lev, cov = stats_to_levels(r["pred"], r.get("gcm"), r.get("scen"), cells)
        parts.append(lev.with_columns(pl.lit(i).cast(pl.Int32).alias("_row")))
        rows.append({"row": i, "pred": r["pred"], "format": fmt, "fold": r.get("fold"), "gcm": r.get("gcm"),
                     "scen": r.get("scen"), "n_cells": None if cells is None else len(cells), **cov})
    allp = pl.concat(parts)
    k = ["gcm", "scen", "window", "Cell", "quantity"]
    dup = allp.group_by(k).agg(pl.col("_row").n_unique().alias("n")).filter(pl.col("n") > 1)
    assert dup.height == 0, (f"{dup.height} (gcm, scen, window, Cell, quantity) keys are predicted by more than one "
                             f"manifest row, e.g. {dup.head(3).to_dicts()}: each cell must come from one fold model")
    allp = allp.drop("_row")
    assert allp.select(k).n_unique() == allp.height
    return allp, {"manifest": path, "manifest_rows": rows, "cells_covered": allp["Cell"].n_unique(),
                  "pooled_crossfit": True, "_cells_declared": sorted(declared) if declared else None}


# ---------------------------------------------------------------------------------------------------------
# levels -> targets (levels + responses + contrasts) -> scored cells
# ---------------------------------------------------------------------------------------------------------
def make_targets(lev: pl.DataFrame, scale: str = "cell", truth_seed: int = 1) -> tuple[pl.DataFrame, list[dict]]:
    """lev: gcm, scen, window, Cell, quantity, value. Returns the prediction for every target the tolerance
    table knows (levels incl. Historical h1985 + responses + SH14 contrasts) and the baseline provenance."""
    k = ["gcm", "scen", "window", "Cell", "quantity"]
    assert lev.select(k).n_unique() == lev.height, "duplicate keys in the submission"
    # Historical level: explicit Historical rows, else the h1985 rows of the first ssp carrying them
    hist_explicit = lev.filter((pl.col("window") == "h1985") & (pl.col("scen") == "Historical"))
    hist_ssp = lev.filter((pl.col("window") == "h1985") & (pl.col("scen") != "Historical"))
    hist_level = hist_explicit
    if hist_ssp.height:
        add = (hist_ssp.sort("scen").group_by(["gcm", "Cell", "quantity"]).first()
               .join(hist_explicit.select(["gcm"]).unique(), on="gcm", how="anti")
               .with_columns(pl.lit("Historical").alias("scen")))
        hist_level = pl.concat([hist_level, add.select(hist_level.columns)])
    levels = pl.concat([lev.filter(pl.col("window") != "h1985"), hist_level.select(lev.columns)])
    ref_h = (tolerance(scale, truth_seed).filter(pl.col("window") == "h1985")
             .select(["gcm", "Cell", "quantity", pl.col("C").alias("refH")]))
    resp, prov = [], []
    for rname, wname in R.RESPONSES.items():
        fut = lev.filter((pl.col("window") == wname) & (pl.col("scen") != "Historical"))
        if not fut.height:
            continue
        for (g, s), f in fut.group_by(["gcm", "scen"]):
            own = hist_ssp.filter((pl.col("gcm") == g) & (pl.col("scen") == s))
            if own.height:
                base, src = own, "own_ssp_h1985"
            elif hist_level.filter(pl.col("gcm") == g).height:
                base, src = hist_level.filter(pl.col("gcm") == g), "own_historical_h1985"
            else:
                base, src = None, f"reference_seed{truth_seed}_h1985"
            if base is not None:
                b = base.select(["Cell", "quantity", pl.col("value").alias("H")])
            else:
                b = ref_h.filter(pl.col("gcm") == g).select(["Cell", "quantity", pl.col("refH").alias("H")])
            x = f.join(b, on=["Cell", "quantity"], how="left").with_columns(
                (pl.col("value") - pl.col("H")).alias("value"), pl.lit(rname).alias("window"))
            resp.append(x.select(lev.columns))
            prov.append({"gcm": g, "scen": s, "response": rname, "baseline": src})
    # SH14 contrasts: X(scen, w) - X(ssp126, w) from the submission's own levels (never from the reference)
    for cname, wname in R.CONTRASTS.items():
        base = lev.filter((pl.col("window") == wname) & (pl.col("scen") == R.CONTRAST_BASE))
        fut = lev.filter((pl.col("window") == wname) & pl.col("scen").is_in(R.CONTRAST_SCENS))
        if not base.height or not fut.height:
            continue
        for (g, s), f in fut.group_by(["gcm", "scen"]):
            b = base.filter(pl.col("gcm") == g).select(["Cell", "quantity", pl.col("value").alias("B")])
            if not b.height:
                continue
            x = f.join(b, on=["Cell", "quantity"], how="left").with_columns(
                (pl.col("value") - pl.col("B")).alias("value"), pl.lit(cname).alias("window"))
            resp.append(x.select(lev.columns))
            prov.append({"gcm": g, "scen": s, "contrast": cname, "baseline": f"own_{R.CONTRAST_BASE}_{wname}"})
    allp = pl.concat([levels] + resp) if resp else levels
    return allp, prov


def _passes(d: pl.DataFrame) -> pl.DataFrame:
    dev = (pl.col("E") - pl.col("C")).abs()
    return d.with_columns(
        [((dev <= pl.col(a) * (1 + EPS)) & ~pl.col("missing")).fill_null(False).alias(p) for a, p in PASS_COLS])


def score_targets(pred: pl.DataFrame, scope: str = "all", scale: str = "cell", truth_seed: int = 1,
                  cells_declared: list[int] | None = None) -> pl.DataFrame:
    """Join to the tolerance table; only the (gcm, scen, window) targets the prediction touches are scored.
    scope "all": within a touched target every reference cell is scored and a missing prediction is a FAIL
    (missing=True) -- the acceptance setting. scope "covered": only cells the prediction has (development
    subsets such as the Cell % 10 == 0 dev cells); the coverage is reported."""
    tol = tolerance(scale, truth_seed)
    touched = pred.select(["gcm", "scen", "window"]).unique()
    t = tol.join(touched, on=["gcm", "scen", "window"], how="inner")
    if scope == "covered":
        if cells_declared is not None:
            # SH14 repair: the DECLARED cells (--cells) are the scored set; a declared cell the prediction lacks is
            # a miss (it used to drop out silently)
            t = t.filter(pl.col("Cell").is_in(cells_declared))
        else:
            t = t.join(pred.select(["gcm", "Cell"]).unique(), on=["gcm", "Cell"], how="inner")
    k = ["gcm", "scen", "window", "Cell", "quantity"]
    d = t.join(pred.rename({"value": "E"}), on=k, how="left")
    dev = (pl.col("E") - pl.col("C")).abs()
    d = d.with_columns(
        pl.col("E").is_null().alias("missing"),
        (dev / pl.col("C").abs()).alias("err_rel"),
        (dev / pl.col("allowed")).alias("ratio"),
    )
    d = _passes(d)
    return d.select(k + ["target_kind", "stratum", "C", "R", "E", "allowed", "allowed_cell", "allowed_q90",
                         "allowed_cal", "sn_cell", "tol_source", "missing", "err_rel", "ratio", "pass", "pass_cell",
                         "pass_q90", "pass_cal",
                         # SH14 (appended)
                         "allowed_cell_abs", "allowed_c", "allowed_q90_c", "allowed_cal_c", "pass_cell_abs",
                         "pass_c", "pass_q90_c", "pass_cal_c",
                         # SH14 repair (appended)
                         "allowed_cal1", "allowed_cal_xg", "allowed_cal1_xg", "pass_cal1", "pass_cal_xg",
                         "pass_cal1_xg", "dev_unbr_lo", "dev_unbr_hi"])


def summarise(d: pl.DataFrame) -> dict[str, pl.DataFrame]:
    by = ["gcm", "scen", "window"]
    q = d.group_by(by + ["quantity"]).agg(
        pl.len().alias("n_cells"),
        pl.col("missing").sum().alias("n_missing"),
        pl.col("pass").mean().alias("pass_frac"),
        pl.col("pass_cell").mean().alias("pass_cell_frac"),
        pl.col("pass_q90").mean().alias("pass_q90_frac"),
        pl.col("pass_cal").mean().alias("pass_cal_frac"),
        pl.col("err_rel").median().alias("err_rel_med"),
        pl.col("ratio").median().alias("ratio_med"),
        pl.col("pass").filter(pl.col("sn_cell") >= 3).mean().alias("pass_frac_sn3"),
        (pl.col("sn_cell") >= 3).mean().alias("frac_cells_sn3"),
        *[pl.col(p).mean().alias(f"{p}_frac") for p in PASS_NAMES[4:]],
    ).sort(by + ["quantity"]).with_columns(target_note_expr())
    conj = []
    for gname, qs in GROUPS.items():
        x = d.filter(pl.col("quantity").is_in(qs))
        if not x.height:
            continue
        c = x.group_by(by + ["Cell"]).agg(
            *[pl.col(p).all().alias(f"a_{p}") for p in PASS_NAMES], pl.len().alias("nq"),
        ).group_by(by).agg(
            pl.len().alias("n_cells"), pl.col("nq").max().alias("n_quantities"),
            *[pl.col(f"a_{p}").mean().alias(f"all_{p}_frac") for p in PASS_NAMES],
        ).with_columns(pl.lit(gname).alias("panel"))
        lead = by + ["n_cells", "n_quantities"] + [f"all_{p}_frac" for p in PASS_NAMES[:4]] + ["panel"]
        conj.append(c.select(lead + [f"all_{p}_frac" for p in PASS_NAMES[4:]]))
    conj = pl.concat(conj).sort(by + ["panel"]).with_columns(target_note_expr())
    # the whole criterion per (gcm, scen) and cell: every panel quantity passes in h1985 + w2015 + w2071 + the
    # response target. Round 1: r2071 (all ssps). SH14: also c2071 (ssp370/ssp245, the CO2-free response).
    crit = []
    for g, s in d.filter(pl.col("scen") != "Historical").select(["gcm", "scen"]).unique().sort(
            ["gcm", "scen"]).iter_rows():
        for rt in ["r2071", "c2071"]:
            if rt == "c2071" and s not in R.CONTRAST_SCENS:
                continue
            need = [("Historical", "h1985"), (s, "w2015"), (s, "w2071"), (s, rt)]
            x = d.filter(pl.col("gcm") == g).join(
                pl.DataFrame({"scen": [a for a, _ in need], "window": [b for _, b in need]}), on=["scen", "window"])
            have = x.select(["scen", "window"]).unique().height
            if rt == "c2071" and not x.filter(pl.col("window") == "c2071").height:
                continue
            for pname in ["panel106", "extended"]:
                y = x.filter(pl.col("quantity").is_in(GROUPS[pname])).group_by("Cell").agg(
                    *[pl.col(p).all().alias(p) for p in PASS_NAMES])
                rec = {"gcm": g, "scen": s, "panel": pname, "targets_present": have, "targets_needed": 4,
                       "n_cells": y.height}
                rec.update({f"all_{p}_frac": (y[p].mean() if y.height else None) for p in PASS_NAMES})
                rec["response_target"] = rt
                crit.append(rec)
    crit = pl.DataFrame(crit) if crit else pl.DataFrame()
    return {"quantity": q, "conjunctive": conj, "criterion": crit}


def aggregate_response(d: pl.DataFrame, truth_seed: int = 1) -> pl.DataFrame:
    """Area-weighted aggregates of the prediction vs the reference's (reference/aggregate{,_t2}.parquet)."""
    agg = pl.read_parquet(f"{REFDIR}/aggregate{_sfx(truth_seed)}.parquet")
    st = pl.read_parquet(f"{R.XDE}/climate/cell_static.parquet").select(["Cell", "lat", "area_km2_approx"])
    t1, t2 = json.load(open(f"{REFDIR}/_gates.json"))["lat_tercile_edges"]
    st = st.with_columns(
        pl.when(pl.col("lat") < t1).then(pl.lit("south")).when(pl.col("lat") < t2).then(pl.lit("central"))
        .otherwise(pl.lit("north")).alias("region"), pl.col("Cell").cast(pl.Int32))
    x = d.filter(~pl.col("missing")).join(st, on="Cell")
    out = []
    for reg in ["DE", "south", "central", "north"]:
        y = x if reg == "DE" else x.filter(pl.col("region") == reg)
        a = y.group_by(["gcm", "scen", "window", "quantity"]).agg(
            ((pl.col("E") * pl.col("area_km2_approx")).sum() / pl.col("area_km2_approx").sum()).alias("aggE"),
            ((pl.col("C") * pl.col("area_km2_approx")).sum() / pl.col("area_km2_approx").sum()).alias("aggC_scored"),
            pl.len().alias("n_scored"),
        ).with_columns(pl.lit(reg).alias("region"))
        out.append(a)
    a = pl.concat(out).join(agg, on=["gcm", "scen", "window", "quantity", "region"], how="left")
    a = a.with_columns(
        (pl.col("aggE") / pl.col("aggC")).alias("ratio_E_over_C"),
        (pl.col("sn") >= 3).alias("determined"),
        ((pl.col("aggE") - pl.col("aggC")).abs() <= pl.col("allowed")).alias("pass"),
    ).with_columns(
        pl.when(pl.col("target_kind").is_in(["response", "contrast"])).then(pl.col("determined")).otherwise(True)
        .alias("determined")
    )
    # SH14: the same aggregate test on the SCORED cells only (dev / held-out-fold subsets). The round-1 columns
    # compare the subset's aggregate with the ALL-CELL truth aggregate, so on the 907 dev cells even the other
    # seed fails ~16-30 % of response aggregates. Here truth, replica and prediction are aggregated over the same
    # cells (rows where E, C and R all exist): aggE_same / aggC_same / aggR_same, allowed_same =
    # max(10 % |aggC_same|, |aggC_same - aggR_same|), sn_same, determined_same, pass_same.
    xs = x.filter(pl.col("R").is_not_null())
    outs = []
    for reg in ["DE", "south", "central", "north"]:
        y = xs if reg == "DE" else xs.filter(pl.col("region") == reg)
        w = pl.col("area_km2_approx")
        outs.append(y.group_by(["gcm", "scen", "window", "quantity"]).agg(
            ((pl.col("E") * w).sum() / w.sum()).alias("aggE_same"),
            ((pl.col("C") * w).sum() / w.sum()).alias("aggC_same"),
            ((pl.col("R") * w).sum() / w.sum()).alias("aggR_same"),
            pl.len().alias("n_same"),
            pl.col("target_kind").first().alias("_tk"),
        ).with_columns(pl.lit(reg).alias("region")))
    sm = pl.concat(outs).with_columns(
        (pl.col("aggC_same") - pl.col("aggR_same")).abs().alias("noise_same")).with_columns(
        pl.max_horizontal(R.REL_FLOOR * pl.col("aggC_same").abs(), pl.col("noise_same")).alias("allowed_same"),
        (((pl.col("aggC_same") + pl.col("aggR_same")) / 2).abs() / pl.col("noise_same")).alias("sn_same"),
    ).with_columns(
        ((pl.col("aggE_same") - pl.col("aggC_same")).abs() <= pl.col("allowed_same") * (1 + EPS)).alias("pass_same"),
        pl.when(pl.col("_tk").is_in(["response", "contrast"])).then(pl.col("sn_same") >= 3).otherwise(True)
        .alias("determined_same"),
        # SH14 repair (verifier): allowed_same contains |aggC - aggR|, so the replica passes pass_same BY
        # CONSTRUCTION wherever the 10 % floor does not bind; its 1.00 is not a ceiling. Two honest companions:
        #   pass_floor_same  the floor-only rule |aggE - aggC| <= 10 % |aggC|; the replica passes it exactly where
        #                    floor_binds_same, so mean(floor_binds_same) IS its (non-tautological) ceiling
        #   p_indep_same_upper  expected pass_same of an independent run exactly as good as the replica: 1 where the
        #                    floor binds, else 0.5 (|E-C| <= |R-C| with probability 1/2 for exchangeable E, R); an
        #                    upper bound (a floor-bound row is not passed with certainty)
        (pl.col("noise_same") <= R.REL_FLOOR * pl.col("aggC_same").abs()).alias("floor_binds_same"),
        ((pl.col("aggE_same") - pl.col("aggC_same")).abs() <= R.REL_FLOOR * pl.col("aggC_same").abs() * (1 + EPS))
        .alias("pass_floor_same"),
    ).with_columns(
        pl.when(pl.col("floor_binds_same")).then(1.0).otherwise(0.5).alias("p_indep_same_upper"),
    ).drop(["_tk", "noise_same"])
    a = a.join(sm, on=["gcm", "scen", "window", "quantity", "region"], how="left")
    return a.sort(["gcm", "scen", "window", "quantity", "region"])


def add_ceiling(s: dict, out: str, sub: str, truth_seed: int = 1) -> dict:
    """Round 1: join the ALL-CELL other-seed null's conjunctive pass fractions (same scale, same tolerance column)
    as ceiling_*. With --scope covered these are NOT on the same cells: use ceiling_same_* (add_ceiling_same)."""
    f = f"{out}/null_a_other_seed{_sfx(truth_seed)}/{sub}summary_conjunctive.csv"
    if s.get("_is_null_a"):
        # SH14 fix: null (a) used to read its OWN previous output here (stale by one rebuild: round 1's null_a
        # ceiling_cell differed from its own fraction by up to 0.81 after the 1e-9 epsilon fix). Its ceiling is itself.
        s["conjunctive"] = s["conjunctive"].with_columns(
            [pl.col(c).alias(f"ceiling_{c}") for c in ["all_pass_frac", "all_pass_cell_frac", "all_pass_q90_frac",
                                                       "all_pass_cal_frac"]])
        return s
    if not os.path.exists(f):
        return s
    ce = pl.read_csv(f).select(["gcm", "scen", "window", "panel"] + [
        pl.col(c).alias(f"ceiling_{c}") for c in ["all_pass_frac", "all_pass_cell_frac", "all_pass_q90_frac",
                                                   "all_pass_cal_frac"]])
    s["conjunctive"] = s["conjunctive"].join(ce, on=["gcm", "scen", "window", "panel"], how="left")
    return s


def add_ceiling_same(s: dict, d: pl.DataFrame) -> dict:
    """SH14: the other seed scored on EXACTLY the rows of this submission (same cells, targets, scale, tolerance):
    E := R, and a row where the other seed has no value is a miss -- the round-1 null (a) convention. A target
    (gcm, scen, window) with no other-seed value at all (MPI ssp370 w3071 under truth seed 1) has no ceiling."""
    has = d.group_by(["gcm", "scen", "window"]).agg(pl.col("R").is_not_null().any().alias("_h")).filter(
        pl.col("_h")).drop("_h")
    x = d.join(has, on=["gcm", "scen", "window"], how="inner")
    if not x.height:
        return s
    x = _passes(x.with_columns(pl.col("R").alias("E"), pl.col("R").is_null().alias("missing")))
    cs = summarise(x)
    cols = ["n_cells"] + [f"all_{p}_frac" for p in PASS_NAMES]
    ce = cs["conjunctive"].select(["gcm", "scen", "window", "panel"] + [pl.col(c).alias(f"ceiling_same_{c}")
                                                                        for c in cols])
    s["conjunctive"] = s["conjunctive"].join(ce, on=["gcm", "scen", "window", "panel"], how="left")
    if s["criterion"].height and cs["criterion"].height:
        cc = cs["criterion"].select(["gcm", "scen", "panel", "response_target"] + [
            pl.col(c).alias(f"ceiling_same_{c}") for c in cols])
        s["criterion"] = s["criterion"].join(cc, on=["gcm", "scen", "panel", "response_target"], how="left")
    # SH14 repair: the contrast ceiling of an arm whose scenario legs are NOT branched from one state with shared
    # random numbers (see reference _DEFINITION.md item 7): contrast rows get |E - C| = dev_unbr_lo (pessimistic) or
    # dev_unbr_hi (optimistic) instead of |R - C|; level/response rows keep the replica. Bracket, not a point value.
    if x.filter(pl.col("target_kind") == "contrast").height:
        for tag, dcol in [("lo", "dev_unbr_lo"), ("hi", "dev_unbr_hi")]:
            iscon = pl.col("target_kind") == "contrast"
            xu = _passes(x.with_columns(
                pl.when(iscon).then(pl.col("C") + pl.col(dcol)).otherwise(pl.col("R")).alias("E"),
                pl.when(iscon).then(pl.col(dcol).is_null()).otherwise(pl.col("R").is_null()).alias("missing")))
            cu = summarise(xu)
            ce = cu["conjunctive"].filter(pl.col("window").is_in(list(R.CONTRASTS))).select(
                ["gcm", "scen", "window", "panel"] + [pl.col(f"all_{p}_frac").alias(f"ceiling_unbr_{tag}_all_{p}_frac")
                                                      for p in PASS_NAMES])
            s["conjunctive"] = s["conjunctive"].join(ce, on=["gcm", "scen", "window", "panel"], how="left")
            if s["criterion"].height and cu["criterion"].height:
                cc = cu["criterion"].filter(pl.col("response_target") == "c2071").select(
                    ["gcm", "scen", "panel", "response_target"] + [
                        pl.col(f"all_{p}_frac").alias(f"ceiling_unbr_{tag}_all_{p}_frac") for p in PASS_NAMES])
                s["criterion"] = s["criterion"].join(cc, on=["gcm", "scen", "panel", "response_target"], how="left")
    return s


def run_score(pred_levels: pl.DataFrame, label: str, out: str, cov: dict, quiet: bool = False,
              scope: str = "all", truth_seed: int = 1, cells_declared: list[int] | None = None) -> dict:
    t0 = time.time()
    od = f"{out}/{label}"
    os.makedirs(od, exist_ok=True)
    targets, prov = make_targets(pred_levels, "cell", truth_seed)
    d = score_targets(targets, scope, "cell", truth_seed, cells_declared)
    d.write_parquet(f"{od}/cells.parquet")
    isna = label.startswith("null_a_other_seed")
    s = add_ceiling_same(add_ceiling(dict(summarise(d), _is_null_a=isna), out, "", truth_seed), d)
    s.pop("_is_null_a", None)
    s["quantity"].write_csv(f"{od}/summary_quantity.csv")
    s["conjunctive"].write_csv(f"{od}/summary_conjunctive.csv")
    if s["criterion"].height:
        s["criterion"].write_csv(f"{od}/summary_criterion.csv")
    ag = aggregate_response(d, truth_seed)
    ag.write_csv(f"{od}/aggregate_response.csv")
    # ---- block scale (same code, blocks in place of cells)
    # SH14 repair: the block reference is chosen from the DECLARED cells when given, so a declared cell the
    # prediction lacks makes its blocks missing instead of silently switching to a smaller block reference
    cells = cells_declared if cells_declared is not None else sorted(pred_levels["Cell"].unique().to_list())
    bscale, mask = block_reference_for(cells, scope, truth_seed)
    bl = pred_to_blocks(pred_levels, mask)
    btargets, _ = make_targets(bl, bscale, truth_seed)
    bd = score_targets(btargets, "all", bscale, truth_seed)
    os.makedirs(f"{od}/block", exist_ok=True)
    bd.write_parquet(f"{od}/block/cells.parquet")
    bs = add_ceiling_same(add_ceiling(dict(summarise(bd), _is_null_a=isna), out, "block/", truth_seed), bd)
    bs.pop("_is_null_a", None)
    bs["quantity"].write_csv(f"{od}/block/summary_quantity.csv")
    bs["conjunctive"].write_csv(f"{od}/block/summary_conjunctive.csv")
    if bs["criterion"].height:
        bs["criterion"].write_csv(f"{od}/block/summary_criterion.csv")
    ss = cov.get("start_seed")
    cov = dict(cov, label=label, baselines=prov, scope=scope, truth_seed=int(truth_seed),
               start_state_shared_with_truth=(None if ss is None else int(ss) == int(truth_seed)),
               held_out_place=cov.get("held_out_place", "unknown"), legs_branched=cov.get("legs_branched", "unknown"),
               n_cells_declared=None if cells_declared is None else len(cells_declared),
               n_scored_rows=d.height, n_missing=int(d["missing"].sum()),
               block_reference=bscale, n_blocks=int(bd["Cell"].n_unique()), n_block_rows=bd.height,
               n_block_missing=int(bd["missing"].sum()), wall_s=round(time.time() - t0, 1))
    json.dump(cov, open(f"{od}/coverage.json", "w"), indent=1, default=str)
    if not quiet:
        print_summary(label, s, ag, bs, cov)
    return {"cells": d, **s, "aggregate": ag, "coverage": cov, "block": {"cells": bd, **bs}}


def print_summary(label: str, s: dict, ag: pl.DataFrame, bs: dict | None = None, cov: dict | None = None) -> None:
    print(f"\n===== {label} =====")
    if cov is not None:
        print(f"held_out_place = {cov.get('held_out_place')}  (anything but 'true' is IN-PLACE: not evidence of skill "
              f"on unseen places) | legs_branched = {cov.get('legs_branched')}  (not 'yes' -> read contrasts against "
              f"ceiling_unbr_lo/hi_*, not ceiling_same_*) | start_seed = {cov.get('start_seed')}, "
              f"start_state_shared_with_truth = {cov.get('start_state_shared_with_truth')}, dropped start years = "
              f"{cov.get('dropped_start_years', [])}")
    with pl.Config(tbl_rows=400, tbl_cols=12, fmt_str_lengths=30, float_precision=3, tbl_width_chars=200):
        for scale, ss in [("CELL", s), ("BLOCK", bs)]:
            if ss is None:
                continue
            c = ss["conjunctive"].filter(pl.col("panel").is_in(["panel106", "extended", "count", "traits4_median",
                                                                "traits4_dist", "size_dist"]))
            for col in ["all_pass_frac", "all_pass_cal_frac", "all_pass_cal_xg_frac", "all_pass_cal1_xg_frac"]:
                print(f"[{scale}] conjunctive pass fraction, tolerance column: {col}"
                      + "  (ceiling = the other seed on the same rows: summary_conjunctive.csv ceiling_same_*)")
                print(c.pivot(on="panel", index=["gcm", "scen", "window"], values=col).sort(["gcm", "scen", "window"]))
            if ss["criterion"].height:
                print(f"[{scale}] whole criterion (h1985 + w2015 + w2071 + response target, every panel quantity):")
                print(ss["criterion"].select(["gcm", "scen", "panel", "response_target", "n_cells", "all_pass_frac",
                                              "all_pass_cal_frac", "all_pass_cal_xg_frac", "all_pass_cal1_xg_frac"]))
        a = ag.filter((pl.col("region") == "DE") & pl.col("window").is_in(["r2071", "c2071"]) &
                      pl.col("quantity").is_in(["n_per_patch", "agb_stand", "SLA_q50", "Wooddens_q50", "D95max_q50",
                                                "minwscal_q50", "Height_q50", "share_3"]))
        if a.height:
            print(a.select(["gcm", "scen", "window", "quantity", "aggC", "aggE", "ratio_E_over_C", "sn", "determined",
                            "pass"]))


# ---------------------------------------------------------------------------------------------------------
# nulls
# ---------------------------------------------------------------------------------------------------------
def frozen_levels(gcm_seed_year: list[tuple[str, int, int]]) -> pl.DataFrame:
    parts = []
    for g, sd, y in gcm_seed_year:
        w = pl.read_parquet(f"{REFDIR}/frozen/{g}_s{sd}_y{y}.parquet")
        parts.append(w.select(["Cell"] + R.QUANTITIES).with_columns(pl.lit(g).alias("gcm")))
    w = pl.concat(parts)
    return w.unpivot(index=["gcm", "Cell"], on=R.QUANTITIES, variable_name="quantity", value_name="value") \
        .with_columns(pl.col("Cell").cast(pl.Int32), pl.col("value").cast(pl.Float64))


def nulls(out: str, truth_seed: int = 1, cells: list[int] | None = None, scope: str = "all") -> int:
    ts, ots = int(truth_seed), 3 - int(truth_seed)
    sfx = _sfx(ts)
    lv = pl.read_parquet(f"{REFDIR}/levels_long.parquet")
    st = pl.read_parquet(f"{R.XDE}/climate/cell_static.parquet").select(
        [pl.col("Cell").cast(pl.Int32), "area_km2_approx"])
    truth_all = lv.filter((pl.col("seed") == ts) & pl.col("valid")).drop(["seed", "valid"])
    if cells is not None:
        lv = lv.filter(pl.col("Cell").is_in(cells))
    s1 = lv.filter((pl.col("seed") == ts) & pl.col("valid")).drop(["seed", "valid"])
    s2 = lv.filter((pl.col("seed") == ots) & pl.col("valid")).drop(["seed", "valid"])
    gcms = sorted(s1["gcm"].unique().to_list())
    res = {}

    def run(pred, name, meta):
        res[name] = run_score(pred, name, out, dict(meta, cells_given=cells is not None), scope=scope,
                              truth_seed=ts)

    # (a) the other seed predicting the truth seed (every valid window; responses/contrasts from its own levels)
    run(s2, f"null_a_other_seed{sfx}", {"null": f"seed {ots} levels as prediction of seed {ts}"})
    # (b) persistence: truth 1985-2014 predicting w2015 and w2071 of every scenario (its response and its
    #     scenario contrast are 0); h1985 itself is not a target; response baseline = reference truth h1985.
    h = s1.filter(pl.col("window") == "h1985")
    parts = []
    for scen in SSPS:
        for w in ["w2015", "w2071"]:
            parts.append(h.with_columns(pl.lit(scen).alias("scen"), pl.lit(w).alias("window")))
    pers = pl.concat(parts).select(s1.columns)
    run(pers, f"null_b_persistence{sfx}", {"null": f"seed-{ts} h1985 levels predicting w2015/w2071; response = 0; "
                                                    "scenario contrast = 0"})
    # (d) equilibrium: truth 2071-2100 predicting truth 3071-3100 (same gcm, scen)
    eq = s1.filter(pl.col("window") == "w2071").with_columns(pl.lit("w3071").alias("window"))
    run(eq, f"null_d_equilibrium{sfx}", {"null": f"seed-{ts} w2071 levels predicting w3071"})
    # (e) spatial null: every cell gets the Germany-wide area-weighted truth mean of its target (all windows;
    #     the mean is over ALL reference cells even when scoring a cell subset)
    m = truth_all.join(st, on="Cell").group_by(["gcm", "scen", "window", "quantity"]).agg(
        ((pl.col("value") * pl.col("area_km2_approx")).sum() / pl.col("area_km2_approx").sum()).alias("m"))
    gm = s1.join(m, on=["gcm", "scen", "window", "quantity"]).with_columns(pl.col("m").alias("value")).select(
        s1.columns)
    run(gm, f"null_e_germany_mean{sfx}", {"null": f"Germany-wide area-weighted mean of seed {ts}, every cell"})
    # (f, g) SH14 frozen rosters: the living Historical roster of 1985 (on h1985 + w2015) or 2014 (on w2015 +
    #     w2071) held fixed, from the truth seed's own roster (truth-initialised geometry) and from the other
    #     seed's roster (the like-for-like geometry of the other-seed ceiling).
    for from_seed in (ts, ots):
        f85 = frozen_levels([(g, from_seed, 1985) for g in gcms])
        f14 = frozen_levels([(g, from_seed, 2014) for g in gcms])
        if cells is not None:
            f85 = f85.filter(pl.col("Cell").is_in(cells))
            f14 = f14.filter(pl.col("Cell").is_in(cells))
        p85 = [f85.with_columns(pl.lit("Historical").alias("scen"), pl.lit("h1985").alias("window"))]
        p85 += [f85.with_columns(pl.lit(sc).alias("scen"), pl.lit("w2015").alias("window")) for sc in SSPS]
        run(pl.concat(p85).select(s1.columns), f"null_f_frozen1985_from_s{from_seed}{sfx}",
            {"null": f"seed-{from_seed} living 1985 roster frozen: h1985 + w2015 (response r2015 = 0)",
             "start_seed": from_seed})
        p14 = [f14.with_columns(pl.lit(sc).alias("scen"), pl.lit(w).alias("window")) for sc in SSPS
               for w in ["w2015", "w2071"]]
        run(pl.concat(p14).select(s1.columns), f"null_g_frozen2014_from_s{from_seed}{sfx}",
            {"null": f"seed-{from_seed} living 2014 roster frozen: w2015 + w2071 (baseline = reference truth h1985)",
             "start_seed": from_seed})
    # one compact table across nulls
    allc = pl.concat([r["conjunctive"].with_columns(pl.lit(n).alias("null")) for n, r in res.items()],
                     how="diagonal_relaxed")
    allc.write_csv(f"{out}/nulls_conjunctive{sfx}.csv")
    allq = pl.concat([r["quantity"].with_columns(pl.lit(n).alias("null")) for n, r in res.items()])
    allq.write_csv(f"{out}/nulls_quantity{sfx}.csv")
    crit = [r["criterion"].with_columns(pl.lit(n).alias("null")) for n, r in res.items() if r["criterion"].height]
    if crit:
        pl.concat(crit, how="diagonal_relaxed").write_csv(f"{out}/nulls_criterion{sfx}.csv")
    ballc = pl.concat([r["block"]["conjunctive"].with_columns(pl.lit(n).alias("null")) for n, r in res.items()],
                      how="diagonal_relaxed")
    ballc.write_csv(f"{out}/nulls_conjunctive_block{sfx}.csv")
    pl.concat([r["aggregate"].with_columns(pl.lit(n).alias("null")) for n, r in res.items()]).write_csv(
        f"{out}/nulls_aggregate{sfx}.csv")
    log(f"nulls{sfx} done ({len(res)} nulls, out={out})")
    return 0


# ---------------------------------------------------------------------------------------------------------
# selftest
# ---------------------------------------------------------------------------------------------------------
def _maxrel(a: pl.Expr, b: pl.Expr) -> pl.Expr:
    return ((a - b).abs() / b.abs().clip(1e-12)).max()


def _cmp_cells(a: pl.DataFrame, b: pl.DataFrame, cols: list[str]) -> dict:
    """Row-for-row equality of two scored tables on (gcm, scen, window, Cell, quantity): value columns within
    1e-12 relative, boolean columns identical, and the same key set."""
    k = ["gcm", "scen", "window", "Cell", "quantity"]
    j = a.with_columns(pl.lit(True).alias("_a")).join(b.with_columns(pl.lit(True).alias("_b")), on=k, how="full",
                                                     suffix="_r", coalesce=True)
    unmatched = j.filter(pl.col("_a").is_null() | pl.col("_b").is_null()).height
    rec = {"rows_a": a.height, "rows_b": b.height, "rows_joined": j.height, "unmatched": unmatched}
    bad = 0
    for c in cols:
        if a.schema[c] == pl.Boolean:
            nb = int((j[c] != j[f"{c}_r"]).sum() or 0)
            rec[f"diff_{c}"] = nb
            bad += nb
        else:
            nn = int((j[c].is_null() != j[f"{c}_r"].is_null()).sum())
            v = j.select(_maxrel(pl.col(c), pl.col(f"{c}_r"))).item()
            rec[f"maxrel_{c}"] = v
            bad += int((v or 0.0) > 1e-12) + nn
    rec["mismatches"] = bad
    rec["ok"] = bad == 0 and a.height == b.height == j.height and unmatched == 0
    return rec


def selftest(out: str) -> int:
    """Round-1 check: roster path == reference path (dev subset of one seed-2 member-window) and the scorer on it
    == null (a). SH14 checks: (B) the other seed passes the symmetric per-cell tolerance at 1.0 by construction;
    (C) contrasts through a two-row manifest of seed-2 rosters equal the reference's seed-2 contrast exactly, at
    cell and block scale, with pass flags identical to null (a)'s; (D) truth seed 2: a seed-1 roster scored with
    --truth-seed 2 equals null_a_t2; (E) pooled cross-fit: the same roster split into the 5 registry folds and
    pooled equals the unsplit score exactly; (F) --cells filter == a row subset of the unsplit score; (G) a frozen
    roster (2014 living trees repeated over 2015-2044) through the roster path equals reference/frozen; (H) for
    null (a) ceiling_same_* equals its own fractions."""
    t0 = time.time()
    rec: dict = {"selftest": "roster path vs reference on dev subset + SH14 amendment checks"}
    member = "MPI-ESM1-2-HR_Historical_s2_h1985"
    f = f"{R.XDE}/ind_dev/{member}.parquet"
    cells = sorted(pl.scan_parquet(f).select("Cell").unique().collect()["Cell"].to_list())
    lev, cov = roster_to_levels(f, "MPI-ESM1-2-HR", "Historical", R.NPATCH, cells)
    ref = pl.read_parquet(f"{REFDIR}/levels_long.parquet").filter(
        (pl.col("gcm") == "MPI-ESM1-2-HR") & (pl.col("scen") == "Historical") & (pl.col("seed") == 2)
        & pl.col("Cell").is_in(cells))
    j = ref.join(lev, on=["gcm", "scen", "window", "Cell", "quantity"], how="full", suffix="_r")
    n_unmatched = j.filter(pl.col("value").is_null() != pl.col("value_r").is_null()).height
    dmax = j.select(((pl.col("value") - pl.col("value_r")).abs() / pl.col("value").abs().clip(1e-12)).max()).item()
    ok = n_unmatched == 0 and (dmax or 0.0) < 1e-9
    rec.update({"member": member, "cells": len(cells), "rows_ref": ref.height, "rows_roster": lev.height,
                "unmatched": n_unmatched, "max_rel_diff": dmax})
    checks = {"A_roster_vs_reference": ok}
    # and the scorer on that roster: seed 2 scored against seed 1 must equal null (a) for these cells
    r = run_score(lev, "selftest_roster_s2_dev", out, cov, quiet=True, scope="covered")
    na = f"{out}/null_a_other_seed/cells.parquet"
    if os.path.exists(na):
        a = pl.read_parquet(na).filter((pl.col("window") == "h1985") & pl.col("Cell").is_in(cells))
        b = r["cells"].filter(pl.col("window") == "h1985")
        jj = a.join(b, on=["gcm", "scen", "window", "Cell", "quantity"], suffix="_r")
        rec["pass_mismatch_vs_null_a"] = int(sum(int((jj[p] != jj[f"{p}_r"]).sum()) for p in PASS_NAMES))
        rec["rows_compared_vs_null_a"] = jj.height
        checks["A_scorer_vs_null_a"] = rec["pass_mismatch_vs_null_a"] == 0 and jj.height == b.height
    # block path: the roster's block values must equal the block_dev reference's seed-2 values exactly
    bb = r["block"]["cells"].filter((pl.col("target_kind") == "level") & pl.col("R").is_not_null())
    rec["block_reference"] = r["coverage"]["block_reference"]
    rec["block_rows_compared"] = bb.height
    rec["block_max_rel_diff_E_vs_R"] = bb.select(
        ((pl.col("E") - pl.col("R")).abs() / pl.col("R").abs().clip(1e-12)).max()).item()
    rec["block_missing"] = int(bb["missing"].sum())
    checks["A_block"] = bb.height > 0 and rec["block_missing"] == 0 and rec["block_max_rel_diff_E_vs_R"] < 1e-9
    # and the full-scale other-seed null's block E must equal the block reference's R (scorer vs reference code)
    nab = f"{out}/null_a_other_seed/block/cells.parquet"
    if os.path.exists(nab):
        x = pl.read_parquet(nab).filter((pl.col("target_kind") == "level") & pl.col("R").is_not_null())
        rec["null_a_block_rows"] = x.height
        rec["null_a_block_max_rel_diff_E_vs_R"] = x.select(
            ((pl.col("E") - pl.col("R")).abs() / pl.col("R").abs().clip(1e-12)).max()).item()
        checks["A_null_a_block"] = rec["null_a_block_max_rel_diff_E_vs_R"] < 1e-9
    # ---- (B) symmetry: the replica passes allowed_cell_abs everywhere (cell and block, both truth seeds)
    for sfx in ["", "_t2"]:
        for sub in ["", "block/"]:
            fp = f"{out}/null_a_other_seed{sfx}/{sub}cells.parquet"
            if not os.path.exists(fp):
                checks[f"B_symmetric{sfx}_{sub or 'cell/'}"] = False
                continue
            x = pl.read_parquet(fp).filter(pl.col("R").is_not_null())
            fr = float(x["pass_cell_abs"].mean())
            frl = float(x.filter(pl.col("target_kind") == "level")["pass_cell"].mean())
            rec[f"B_null_a{sfx}_{sub or 'cell/'}pass_cell_abs"] = fr
            rec[f"B_null_a{sfx}_{sub or 'cell/'}levels_pass_cell_round1"] = frl
            checks[f"B_symmetric{sfx}_{sub or 'cell/'}"] = fr == 1.0
    # ---- (C) contrasts via a two-row manifest of seed-2 dev rosters (MPI ssp126 + ssp370, 2071-2100)
    sd = f"{R.XDE}/shared/scorer/selftest"
    os.makedirs(sd, exist_ok=True)
    man = f"{sd}/manifest_contrast.csv"
    pl.DataFrame({"pred": [f"{R.XDE}/ind_dev/MPI-ESM1-2-HR_{s}_s2_w2071.parquet" for s in ["ssp126", "ssp370"]],
                  "gcm": ["MPI-ESM1-2-HR"] * 2, "scen": ["ssp126", "ssp370"], "format": ["roster"] * 2}).write_csv(man)
    lc, cc = manifest_to_levels(man, "roster", R.NPATCH, cells, DEFAULT_FOLD_MAP)
    rc = run_score(lc, "selftest_contrast_s2_dev", out, cc, quiet=True, scope="covered")
    for scale_name, tab in [("cell", rc["cells"]), ("block", rc["block"]["cells"])]:
        x = tab.filter((pl.col("window") == "c2071") & pl.col("R").is_not_null())
        mr = x.select(_maxrel(pl.col("E"), pl.col("R"))).item() if x.height else None
        rec[f"C_contrast_{scale_name}_rows"] = x.height
        rec[f"C_contrast_{scale_name}_max_rel_E_vs_R"] = mr
        checks[f"C_contrast_{scale_name}"] = x.height > 0 and mr is not None and mr < 1e-9 \
            and int(x["missing"].sum()) == 0
    if os.path.exists(na):
        a = pl.read_parquet(na).filter((pl.col("window") == "c2071") & (pl.col("gcm") == "MPI-ESM1-2-HR")
                                       & (pl.col("scen") == "ssp370") & pl.col("Cell").is_in(cells))
        b = rc["cells"].filter(pl.col("window") == "c2071")
        jj = a.join(b, on=["gcm", "scen", "window", "Cell", "quantity"], suffix="_r")
        rec["C_pass_mismatch_vs_null_a"] = int(sum(int((jj[p] != jj[f"{p}_r"]).sum()) for p in PASS_NAMES))
        rec["C_rows_vs_null_a"] = jj.height
        checks["C_vs_null_a"] = rec["C_pass_mismatch_vs_null_a"] == 0 and jj.height == b.height > 0
    # (H) on a prediction equal to the replica, ceiling_same == own fractions
    cj = rc["conjunctive"].filter(pl.col("window").is_in(["c2071", "w2071"]))
    dd = cj.select([(pl.col(f"all_{p}_frac") - pl.col(f"ceiling_same_all_{p}_frac")).abs().max().alias(p)
                    for p in PASS_NAMES]).row(0)
    rec["H_ceiling_same_max_abs_diff"] = max(dd)
    checks["H_ceiling_same"] = max(dd) == 0.0
    # ---- (D) truth seed 2: seed-1 dev roster scored with --truth-seed 2 == null_a_t2 on these cells
    f1 = f"{R.XDE}/ind_dev/MPI-ESM1-2-HR_Historical_s1_h1985.parquet"
    l1, c1 = roster_to_levels(f1, "MPI-ESM1-2-HR", "Historical", R.NPATCH, cells)
    r2 = run_score(l1, "selftest_truthseed2_s1_dev", out, dict(c1, start_seed=1), quiet=True, scope="covered",
                   truth_seed=2)
    x = r2["cells"].filter((pl.col("window") == "h1985") & pl.col("R").is_not_null())
    rec["D_truthseed2_rows"] = x.height
    rec["D_truthseed2_max_rel_E_vs_R"] = x.select(_maxrel(pl.col("E"), pl.col("R"))).item()
    checks["D_truthseed2_E_eq_R"] = x.height > 0 and rec["D_truthseed2_max_rel_E_vs_R"] < 1e-9
    na2 = f"{out}/null_a_other_seed_t2/cells.parquet"
    if os.path.exists(na2):
        a = pl.read_parquet(na2).filter((pl.col("window") == "h1985") & pl.col("Cell").is_in(cells)
                                        & (pl.col("gcm") == "MPI-ESM1-2-HR"))
        jj = a.join(r2["cells"].filter(pl.col("window") == "h1985"), on=["gcm", "scen", "window", "Cell", "quantity"],
                    suffix="_r")
        rec["D_pass_mismatch_vs_null_a_t2"] = int(sum(int((jj[p] != jj[f"{p}_r"]).sum()) for p in PASS_NAMES))
        rec["D_rows_vs_null_a_t2"] = jj.height
        nh = r2["cells"].filter(pl.col("window") == "h1985").height
        checks["D_vs_null_a_t2"] = rec["D_pass_mismatch_vs_null_a_t2"] == 0 and jj.height == nh > 0
        # and the C column of the t2 table IS seed 2
        chk = jj.select(_maxrel(pl.col("C"), pl.col("C_r"))).item()
        checks["D_C_consistent"] = (chk or 0.0) < 1e-12
    # ---- (E) pooled cross-fit: 5 registry folds of the same roster, pooled == unsplit
    man5 = f"{sd}/manifest_crossfit5.csv"
    pl.DataFrame({"pred": [f] * 5, "gcm": ["MPI-ESM1-2-HR"] * 5, "scen": ["Historical"] * 5,
                  "fold": [str(i) for i in range(1, 6)], "format": ["roster"] * 5}).write_csv(man5)
    cf = f"{sd}/cells_dev.txt"
    open(cf, "w").write("\n".join(map(str, cells)) + "\n")
    l5, c5 = manifest_to_levels(man5, "roster", R.NPATCH, read_cells(cf), DEFAULT_FOLD_MAP)
    r5 = run_score(l5, "selftest_crossfit5_s2_dev", out, c5, quiet=True, scope="covered")
    cols = ["C", "E", "allowed", "allowed_cal", "allowed_cal_c"] + PASS_NAMES
    rec["E_crossfit_cell"] = _cmp_cells(r5["cells"], r["cells"], cols)
    rec["E_crossfit_block"] = _cmp_cells(r5["block"]["cells"], r["block"]["cells"], cols)
    checks["E_crossfit"] = rec["E_crossfit_cell"]["ok"] and rec["E_crossfit_block"]["ok"]
    rec["E_crossfit_block_reference"] = r5["coverage"]["block_reference"]
    # ---- (F) --cells filter: fold-5 dev cells only == the subset of the unsplit score
    fm = pl.read_parquet(DEFAULT_FOLD_MAP)
    f5 = sorted(set(fm.filter(pl.col("fold") == 5)["Cell"].to_list()) & set(cells))
    lf5, cf5 = roster_to_levels(f, "MPI-ESM1-2-HR", "Historical", R.NPATCH, f5)
    rf5 = run_score(lf5, "selftest_cells_fold5_s2_dev", out, cf5, quiet=True, scope="covered")
    rec["F_cells_filter_cell"] = _cmp_cells(rf5["cells"], r["cells"].filter(pl.col("Cell").is_in(f5)), cols)
    rec["F_fold5_dev_cells"] = len(f5)
    rec["F_block_reference"] = rf5["coverage"]["block_reference"]
    checks["F_cells_filter"] = rec["F_cells_filter_cell"]["ok"]
    # ---- (G) frozen: 20 dev cells, seed-1 2014 living roster repeated over 2015-2044 -> roster path
    fz = pl.read_parquet(f"{REFDIR}/frozen/MPI-ESM1-2-HR_s1_y2014.parquet")
    c20 = cells[::45][:20]
    t14 = R.living(pl.scan_parquet(f1).select(R.READ_COLS).filter((pl.col("Year") == 2014)
                                                                    & pl.col("Cell").is_in(c20))).collect()
    rep = pl.concat([t14.with_columns(pl.lit(y).cast(t14.schema["Year"]).alias("Year")) for y in range(2015, 2045)])
    fr = f"{sd}/frozen2014_20cells.parquet"
    rep.write_parquet(fr)
    lg, _ = roster_to_levels(fr, "MPI-ESM1-2-HR", "ssp126", R.NPATCH, c20)
    ex = fz.filter(pl.col("Cell").is_in(c20)).select(["Cell"] + R.QUANTITIES).unpivot(
        index="Cell", variable_name="quantity", value_name="v").with_columns(pl.col("Cell").cast(pl.Int32))
    jg = ex.join(lg.filter(pl.col("window") == "w2015"), on=["Cell", "quantity"], how="full", coalesce=True)
    rec["G_frozen_rows"] = jg.height
    rec["G_frozen_null_mismatch"] = jg.filter(pl.col("v").is_null() != pl.col("value").is_null()).height
    rec["G_frozen_max_rel"] = jg.select(_maxrel(pl.col("value"), pl.col("v"))).item()
    checks["G_frozen"] = rec["G_frozen_null_mismatch"] == 0 and (rec["G_frozen_max_rel"] or 0.0) < 1e-9
    # ---- (I) SH14 repair: INDEPENDENT contrast recompute. Straight from levels_long by a numpy pivot (not the
    #      reference's join code): C = X(ssp370, s1) - X(ssp126, s1), R likewise for seed 2, and the two unbranched
    #      deviations, for c2071 and c2015, compared with the tolerance table row for row.
    import numpy as np

    lv = pl.read_parquet(f"{REFDIR}/levels_long.parquet").filter(
        pl.col("valid") & pl.col("scen").is_in(["ssp126", "ssp370"]) & pl.col("window").is_in(["w2015", "w2071"]))
    tolc = tolerance("cell").filter((pl.col("target_kind") == "contrast") & (pl.col("scen") == "ssp370"))
    irec = {}
    for cname, wname in R.CONTRASTS.items():
        y = lv.filter(pl.col("window") == wname)
        val = {}
        for row in y.select(["gcm", "scen", "seed", "Cell", "quantity", "value"]).iter_rows():
            val[row[:5]] = row[5]
        tt = tolc.filter(pl.col("window") == cname).select(["gcm", "Cell", "quantity", "C", "R", "dev_unbr_lo",
                                                            "dev_unbr_hi"])
        g, c, q = tt["gcm"].to_list(), tt["Cell"].to_list(), tt["quantity"].to_list()
        n = tt.height

        def get(scen, seed, g=g, c=c, q=q, n=n, val=val):
            return np.array([val.get((g[i], scen, seed, c[i], q[i])) for i in range(n)], dtype=float)

        v1, b1, v2, b2 = get("ssp370", 1), get("ssp126", 1), get("ssp370", 2), get("ssp126", 2)
        exp = {"C": v1 - b1, "R": v2 - b2, "dev_unbr_lo": np.abs((v1 - v2) + (b1 - b2)), "dev_unbr_hi": np.abs(v2 - v1)}
        r_ = {}
        for col, e in exp.items():
            got = tt[col].to_numpy().astype(float)
            both = np.isfinite(e) & np.isfinite(got)
            r_[f"{col}_nan_mismatch"] = int((np.isnan(e) != np.isnan(got)).sum())
            r_[f"{col}_max_rel"] = float(np.max(np.abs(e[both] - got[both]) / np.maximum(np.abs(e[both]), 1e-12))) \
                if both.any() else None
        r_["rows"] = n
        irec[cname] = r_
        checks[f"I_contrast_independent_{cname}"] = n > 0 and all(
            (v or 0) == 0 for k_, v in r_.items() if k_.endswith("_nan_mismatch")) and all(
            (v or 0.0) < 1e-12 for k_, v in r_.items() if k_.endswith("_max_rel"))
    rec["I_contrast_independent"] = irec
    # ---- (K) SH14 repair: a declared cell the stats submission lacks is a MISS (cell and block), not silently dropped
    drop = cells[:5]
    lk = lev.filter(~pl.col("Cell").is_in(drop))
    rk = run_score(lk, "selftest_declared_missing", out, {}, quiet=True, scope="covered", cells_declared=cells)
    nmiss_cell = rk["cells"].filter(pl.col("Cell").is_in(drop))["missing"].all()
    rec["K_declared_missing_cell_rows"] = rk["cells"].filter(pl.col("Cell").is_in(drop)).height
    rec["K_block_reference"] = rk["coverage"]["block_reference"]
    rec["K_block_missing"] = int(rk["block"]["cells"]["missing"].sum())
    checks["K_declared_missing"] = bool(nmiss_cell) and rec["K_declared_missing_cell_rows"] > 0 \
        and rec["K_block_reference"] == "block_dev" and rec["K_block_missing"] > 0
    # ---- (L) SH14 repair: --start-year drops the initial-state year (h1985 then has 29 years)
    ll, cl = roster_to_levels(f, "MPI-ESM1-2-HR", "Historical", R.NPATCH, cells, [1985])
    rec["L_windows"] = cl["windows"]
    checks["L_start_year_dropped"] = cl["windows"][0]["n_years"] == 29 and cl["dropped_start_years"] == [1985]
    rec["checks"] = checks
    rec["ok"] = all(checks.values())
    rec["wall_s"] = round(time.time() - t0, 1)
    json.dump(rec, open(f"{out}/selftest.json", "w"), indent=1, default=str)
    print(json.dumps(rec, indent=1, default=str))
    return 0 if rec["ok"] else 3


# ---------------------------------------------------------------------------------------------------------
# headline
# ---------------------------------------------------------------------------------------------------------
HEADLINE_TOL = {f"all_{p}_frac": (p.replace("pass_", "").replace("pass", "") or "stratum") for p in PASS_NAMES}


def headline(out: str, labels: list[str] | None = None) -> int:
    """One compact table over scored submissions: per (label, scale, target window, panel, tolerance column) the
    median / min / max over (gcm, scen) of the conjunctive pass fraction, + the same for ceiling_same_* (the other
    seed on the same rows) + the DE aggregate response pass rate. Tolerance names: stratum, cell, q90, cal (round
    1) and cell_abs, c, q90_c, cal_c (SH14 symmetric)."""
    labels = labels or ["null_a_other_seed", "null_b_persistence", "null_d_equilibrium", "null_e_germany_mean"]
    rows = []
    for lab in labels:
        for scale, sub in [("cell", ""), ("block", "block/")]:
            f = f"{out}/{lab}/{sub}summary_conjunctive.csv"
            if not os.path.exists(f):
                continue
            c = pl.read_csv(f, infer_schema_length=None).filter(pl.col("panel").is_in(
                ["panel106", "extended", "count", "traits4_median", "traits4_dist", "size_dist", "pft_shares"]))
            for col, tname in HEADLINE_TOL.items():
                if col not in c.columns:
                    continue
                cs = f"ceiling_same_{col}"
                agg = [pl.col(col).median().alias("med"), pl.col(col).min().alias("min"),
                       pl.col(col).max().alias("max"), pl.len().alias("n_gcm_scen")]
                if cs in c.columns:
                    agg.append(pl.col(cs).median().alias("ceiling_same_med"))
                a = c.group_by(["window", "panel"]).agg(agg)
                rows.append(a.with_columns(pl.lit(lab).alias("label"), pl.lit(scale).alias("scale"),
                                           pl.lit(tname).alias("tolerance")))
    h = pl.concat(rows, how="diagonal_relaxed")
    if "ceiling_same_med" not in h.columns:
        h = h.with_columns(pl.lit(None, dtype=pl.Float64).alias("ceiling_same_med"))
    h = h.select(["label", "scale", "tolerance", "panel", "window", "med", "min", "max", "n_gcm_scen",
                  "ceiling_same_med"]).sort(["label", "scale", "tolerance", "panel", "window"])
    h.write_csv(f"{out}/headline.csv")
    ag = []
    for lab in labels:
        f = f"{out}/{lab}/aggregate_response.csv"
        if os.path.exists(f):
            a = pl.read_csv(f, infer_schema_length=None).filter(pl.col("window").is_in(
                ["r2015", "r2071", "c2015", "c2071"]))
            extra = []
            if "pass_same" in a.columns:
                ds = pl.col("determined_same")
                extra = [pl.col("pass_same").mean().alias("pass_same_frac"),
                         pl.col("pass_same").filter(ds).mean().alias("pass_same_frac_determined"),
                         pl.col("determined_same").sum().alias("n_determined_same")]
                if "pass_floor_same" in a.columns:
                    extra += [
                        # the honest companions (SH14 repair): never read pass_same against the replica's 1.00
                        pl.col("p_indep_same_upper").filter(ds).mean().alias("expected_indep_pass_same_determined"),
                        pl.col("pass_floor_same").filter(ds).mean().alias("pass_floor_same_frac_determined"),
                        pl.col("floor_binds_same").filter(ds).mean().alias("ceiling_floor_same_determined")]
            ag.append(a.group_by(["window", "region"]).agg(
                pl.col("pass").mean().alias("pass_frac"), pl.col("pass").filter(pl.col("determined")).mean()
                .alias("pass_frac_determined"), pl.len().alias("n"), *extra).with_columns(pl.lit(lab).alias("label")))
    if ag:
        pl.concat(ag, how="diagonal_relaxed").sort(["label", "window", "region"]).write_csv(
            f"{out}/headline_aggregate_response.csv")
    with pl.Config(tbl_rows=500, tbl_width_chars=200, float_precision=3):
        print(h.filter(pl.col("panel").is_in(["panel106"])
                       & pl.col("tolerance").is_in(["stratum", "cal", "cell_abs", "c", "cal_c"])))
        if ag:
            print(pl.concat(ag, how="diagonal_relaxed").sort(["label", "window", "region"]))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["score", "nulls", "selftest", "headline"])
    ap.add_argument("--pred")
    ap.add_argument("--manifest", help="pooled cross-fit / multi-prediction CSV (see USAGE)")
    ap.add_argument("--fold-map", default=DEFAULT_FOLD_MAP)
    ap.add_argument("--format", choices=["roster", "stats"], default="stats")
    ap.add_argument("--label")
    ap.add_argument("--gcm")
    ap.add_argument("--scen")
    ap.add_argument("--npatch", type=int, default=R.NPATCH)
    ap.add_argument("--cells")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--scope", choices=["all", "covered"], default="all",
                    help="all = acceptance (uncovered cells fail); covered = score only the cells submitted")
    ap.add_argument("--truth-seed", type=int, choices=[1, 2], default=1)
    ap.add_argument("--start-seed", type=int, choices=[1, 2], default=None)
    ap.add_argument("--start-year", type=int, action="append", default=None,
                    help="SH14 repair: the run was initialised from the truth roster of this year; its rows of that "
                         "year are dropped (they are the initial state, not a prediction). Repeatable.")
    ap.add_argument("--held-out-place", choices=["true", "false", "unknown"], default="unknown",
                    help="SH14 repair: were the scored cells' places unseen in training? Recorded and printed.")
    ap.add_argument("--legs-branched", choices=["yes", "no", "unknown"], default="unknown",
                    help="SH14 repair: did every scenario leg start from ONE emulator 2014 state of the same run with "
                         "shared random numbers (like the truth)? If not, read contrasts against ceiling_unbr_*.")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    cells = read_cells(a.cells)
    if a.cmd == "nulls":
        return nulls(a.out, a.truth_seed, cells, a.scope)
    if a.cmd == "selftest":
        return selftest(a.out)
    if a.cmd == "headline":
        return headline(a.out, a.label.split(",") if a.label else None)
    assert a.label and (a.pred or a.manifest), "score needs --label and --pred or --manifest"
    if a.manifest:
        lev, cov = manifest_to_levels(a.manifest, a.format, a.npatch, cells, a.fold_map, a.start_year)
    elif a.format == "roster":
        lev, cov = roster_to_levels(a.pred, a.gcm, a.scen, a.npatch, cells, a.start_year)
    else:
        assert not a.start_year, "--start-year applies to rosters (a stats submission must exclude it itself)"
        lev, cov = stats_to_levels(a.pred, a.gcm, a.scen, cells)
    declared = cells if cells is not None else cov.pop("_cells_declared", None)
    cov.pop("_cells_declared", None)
    cov["pred"] = a.pred
    cov["format"] = a.format
    cov["start_seed"] = a.start_seed
    cov["cells_file"] = a.cells
    cov["held_out_place"] = a.held_out_place
    cov["legs_branched"] = a.legs_branched
    run_score(lev, a.label, a.out, cov, scope=a.scope, truth_seed=a.truth_seed,
              cells_declared=declared if a.scope == "covered" else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
