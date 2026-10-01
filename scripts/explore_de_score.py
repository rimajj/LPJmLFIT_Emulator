#!/usr/bin/env python
"""explore_de_score.py -- score ANY Germany emulator output against the LPJmL-FIT reference, identically.

Line X (2026-10-01). Reference + tolerances: scripts/explore_de_reference.py -> /p/tmp/jamirp/X_de/reference/.
The definition of every statistic and tolerance is in /p/tmp/jamirp/X_de/reference/_DEFINITION.md.

EMULATOR OUTPUT CONTRACT (either format; both reach the same scoring code)
  (A) roster  -- a per-tree annual table, the same columns as the ind parquet. Parquet file, directory (read
      recursively) or glob. Required columns: Year, Cell, Type, isdead, Height, SLA, Wooddens, D95max, minwscal,
      Longevity, agb (any others ignored; dtypes are cast). One row per individual per year, at least every
      LIVING tree taller than 5 m (rows with Type > 6, isdead == 1 or Height < 5 m are dropped by the scorer, so
      emitting them is harmless). Required columns gcm and scen, or pass --gcm/--scen for the whole submission.
      Years map to windows h1985 1985-2014, w2015 2015-2044, w2071 2071-2100, w3071 3071-3100; years outside
      them are ignored. Each window's statistic is normalised by the number of DISTINCT years the submission
      has in that window (reported; a partial window is flagged) and by --npatch patches (default 250).
      Cells: the cells the run covered = --cells file (one int per line) or, by default, every Cell that
      appears in the submission; a covered cell with no living tree in a window scores n_per_patch = 0.
      Historical years (1985-2014) should carry scen = "Historical"; a free run that starts in 1985 and is
      labelled with its ssp may instead carry the ssp label: its 1985-2014 rows are then used as that
      scenario's response baseline AND scored as the Historical level.
  (B) stats  -- the per-cell window statistics directly, long format: columns gcm, scen, window, Cell,
      quantity, value (quantity names as in explore_de_reference.QUANTITIES), or wide format: gcm, scen,
      window, Cell + one column per quantity. h1985 rows: scen "Historical" (or the ssp, as in (A)).
  Responses (r2071 = w2071 - h1985, r2015 = w2015 - h1985) are computed by the scorer from the submission's
  own levels. If the submission has no h1985 for a gcm, the reference seed-1 h1985 is used as its baseline
  (flagged baseline=reference) -- i.e. a run initialised from the truth in 2014.

USAGE
  score --pred PATH --format roster|stats --label NAME [--gcm G] [--scen S] [--npatch 250] [--cells FILE]
        [--scope all|covered] [--out DIR] -> DIR/<label>/{cells.parquet, summary_quantity.csv,
                                              summary_conjunctive.csv, summary_criterion.csv,
                                              aggregate_response.csv, coverage.json}  + a printed summary
        and the same at ~1-degree BLOCK scale in DIR/<label>/block/ (blocks = area-weighted means of the per-cell
        statistics over the reference's cells; scope covered uses a block reference built from the covered cells).
        summary_conjunctive.csv carries ceiling_* = the other-seed null's pass fraction under the same tolerance.
  Pass tests: |E - C| <= allowed * (1 + 1e-9). Tolerance columns: allowed (ADR 0111 stratum-median spread,
  PRIMARY), allowed_cell (literal per-cell spread, ADR 0106 wording), allowed_q90, allowed_cal (calibrated).
  nulls [--out DIR]                       -> scores the trivial baselines through the same code
  selftest                                -> the roster path reproduces the reference statistics (dev subset)
  headline [--label a,b]                  -> DIR/headline.csv (+ headline_aggregate_response.csv), light
Heavy (a full-Germany roster or `nulls`): run on SLURM.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_reference as R  # noqa: E402

REFDIR = R.OUT
DEFAULT_OUT = f"{R.OUT}/scores"
LEVEL_WINDOWS = list(R.WINDOWS)
SSPS = ["ssp126", "ssp245", "ssp370"]
ROSTER_COLS = ["Year", "Cell", "Type", "isdead", "Height"] + [t for t in R.TRAITS if t != "Height"]

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


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


EPS = 1e-9  # relative slack in every pass test: `allowed` is built through divisions and can sit 1 ulp below dev
_TOL: dict = {}


def tolerance(scale: str = "cell") -> pl.DataFrame:
    """scale "cell" = reference/tolerance.parquet; "block" / "block_dev" = reference/<scale>/tolerance.parquet;
    "blockcache:<hash>" = an on-the-fly block reference for an arbitrary covered cell set."""
    if scale not in _TOL:
        if scale == "cell":
            _TOL[scale] = pl.read_parquet(f"{REFDIR}/tolerance.parquet")
        elif scale.startswith("blockcache:"):
            _TOL[scale] = pl.read_parquet(f"{REFDIR}/block_cache/{scale.split(':', 1)[1]}/tolerance.parquet")
        else:
            _TOL[scale] = pl.read_parquet(f"{REFDIR}/{scale}/tolerance.parquet")
    return _TOL[scale]


def block_reference_for(cells: list[int] | None, scope: str) -> tuple[str, pl.DataFrame]:
    """Which block reference scores this submission: the full one (scope all), the dev one (scope covered with
    exactly the Cell % 10 == 0 cells), else one built on the fly from the covered cells (cached)."""
    if scope == "all" or cells is None:
        return "block", pl.read_parquet(f"{REFDIR}/block/mask.parquet")
    ref_cells = set(tolerance("cell").filter(pl.col("window") == "h1985")["Cell"].unique().to_list())
    cov = sorted(set(cells) & ref_cells)
    if cov == sorted(c for c in ref_cells if c % 10 == 0):
        return "block_dev", pl.read_parquet(f"{REFDIR}/block_dev/mask.parquet")
    import hashlib

    h = hashlib.sha1(",".join(map(str, cov)).encode()).hexdigest()[:16]
    d = f"{REFDIR}/block_cache/{h}"
    if not os.path.exists(f"{d}/tolerance.parquet"):
        log(f"building block reference for {len(cov)} covered cells -> {d}")
        r = R.build_block_reference(pl.read_parquet(f"{REFDIR}/levels_long.parquet"), cov)
        os.makedirs(d, exist_ok=True)
        r["mask"].write_parquet(f"{d}/mask.parquet")
        r["tolerance"].write_parquet(f"{d}/tolerance.parquet")
    return f"blockcache:{h}", pl.read_parquet(f"{d}/mask.parquet")


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


def roster_to_levels(path: str, gcm: str | None, scen: str | None, npatch: int,
                     cells: list[int] | None) -> tuple[pl.DataFrame, dict]:
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
    years = lf.select(["gcm", "scen", "Year"]).unique().collect()
    if cells is None:
        cells = sorted(lf.select("Cell").unique().collect()["Cell"].to_list())
    cov = {"files": len(files), "cells_covered": len(cells), "windows": []}
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


def stats_to_levels(path: str, gcm: str | None, scen: str | None) -> tuple[pl.DataFrame, dict]:
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
    return d, {"cells_covered": d["Cell"].n_unique()}


# ---------------------------------------------------------------------------------------------------------
# levels -> targets (levels + responses) -> scored cells
# ---------------------------------------------------------------------------------------------------------
def make_targets(lev: pl.DataFrame, scale: str = "cell") -> tuple[pl.DataFrame, list[dict]]:
    """lev: gcm, scen, window, Cell, quantity, value. Returns the prediction for every target the tolerance
    table knows (levels incl. Historical h1985 + responses) and the baseline provenance per (gcm, scen)."""
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
    ref_h = (tolerance(scale).filter(pl.col("window") == "h1985").select(["gcm", "Cell", "quantity",
                                                                       pl.col("C").alias("refH")]))
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
                base, src = None, "reference_seed1_h1985"
            if base is not None:
                b = base.select(["Cell", "quantity", pl.col("value").alias("H")])
            else:
                b = ref_h.filter(pl.col("gcm") == g).select(["Cell", "quantity", pl.col("refH").alias("H")])
            x = f.join(b, on=["Cell", "quantity"], how="left").with_columns(
                (pl.col("value") - pl.col("H")).alias("value"), pl.lit(rname).alias("window"))
            resp.append(x.select(lev.columns))
            prov.append({"gcm": g, "scen": s, "response": rname, "baseline": src})
    allp = pl.concat([levels] + resp) if resp else levels
    return allp, prov


def score_targets(pred: pl.DataFrame, scope: str = "all", scale: str = "cell") -> pl.DataFrame:
    """Join to the tolerance table; only the (gcm, scen, window) targets the prediction touches are scored.
    scope "all": within a touched target every reference cell is scored and a missing prediction is a FAIL
    (missing=True) -- the acceptance setting. scope "covered": only cells the prediction has (development
    subsets such as the Cell % 10 == 0 dev cells); the coverage is reported."""
    tol = tolerance(scale)
    touched = pred.select(["gcm", "scen", "window"]).unique()
    t = tol.join(touched, on=["gcm", "scen", "window"], how="inner")
    if scope == "covered":
        t = t.join(pred.select(["gcm", "Cell"]).unique(), on=["gcm", "Cell"], how="inner")
    k = ["gcm", "scen", "window", "Cell", "quantity"]
    d = t.join(pred.rename({"value": "E"}), on=k, how="left")
    dev = (pl.col("E") - pl.col("C")).abs()
    d = d.with_columns(
        pl.col("E").is_null().alias("missing"),
        (dev / pl.col("C").abs()).alias("err_rel"),
        (dev / pl.col("allowed")).alias("ratio"),
    ).with_columns(
        [((dev <= pl.col(a) * (1 + EPS)) & ~pl.col("missing")).fill_null(False).alias(p)
         for a, p in [("allowed", "pass"), ("allowed_cell", "pass_cell"), ("allowed_q90", "pass_q90"),
                      ("allowed_cal", "pass_cal")]]
    )
    return d.select(k + ["target_kind", "stratum", "C", "R", "E", "allowed", "allowed_cell", "allowed_q90",
                         "allowed_cal", "sn_cell", "tol_source", "missing", "err_rel", "ratio", "pass", "pass_cell",
                         "pass_q90", "pass_cal"])


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
    ).sort(by + ["quantity"])
    conj = []
    for gname, qs in GROUPS.items():
        x = d.filter(pl.col("quantity").is_in(qs))
        if not x.height:
            continue
        c = x.group_by(by + ["Cell"]).agg(
            pl.col("pass").all().alias("p"), pl.col("pass_cell").all().alias("pc"),
            pl.col("pass_q90").all().alias("p9"), pl.col("pass_cal").all().alias("pk"), pl.len().alias("nq"),
        ).group_by(by).agg(
            pl.len().alias("n_cells"), pl.col("nq").max().alias("n_quantities"),
            pl.col("p").mean().alias("all_pass_frac"), pl.col("pc").mean().alias("all_pass_cell_frac"),
            pl.col("p9").mean().alias("all_pass_q90_frac"), pl.col("pk").mean().alias("all_pass_cal_frac"),
        ).with_columns(pl.lit(gname).alias("panel"))
        conj.append(c)
    conj = pl.concat(conj).sort(by + ["panel"])
    # the whole criterion per (gcm, scen) and cell: every panel quantity passes in h1985 + w2015 + w2071 + r2071
    crit = []
    for g, s in d.filter(pl.col("scen") != "Historical").select(["gcm", "scen"]).unique().iter_rows():
        need = [("Historical", "h1985"), (s, "w2015"), (s, "w2071"), (s, "r2071")]
        x = d.filter(pl.col("gcm") == g).join(
            pl.DataFrame({"scen": [a for a, _ in need], "window": [b for _, b in need]}), on=["scen", "window"])
        have = x.select(["scen", "window"]).unique().height
        for pname in ["panel106", "extended"]:
            y = x.filter(pl.col("quantity").is_in(GROUPS[pname])).group_by("Cell").agg(
                pl.col("pass").all().alias("p"), pl.col("pass_cell").all().alias("pc"),
                pl.col("pass_q90").all().alias("p9"), pl.col("pass_cal").all().alias("pk"))
            crit.append({"gcm": g, "scen": s, "panel": pname, "targets_present": have, "targets_needed": 4,
                         "n_cells": y.height, "all_pass_frac": y["p"].mean(),
                         "all_pass_cell_frac": y["pc"].mean(), "all_pass_q90_frac": y["p9"].mean(),
                         "all_pass_cal_frac": y["pk"].mean()})
    crit = pl.DataFrame(crit) if crit else pl.DataFrame()
    return {"quantity": q, "conjunctive": conj, "criterion": crit}


def aggregate_response(d: pl.DataFrame) -> pl.DataFrame:
    """Area-weighted aggregates of the prediction vs the reference's (reference/aggregate.parquet)."""
    agg = pl.read_parquet(f"{REFDIR}/aggregate.parquet")
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
        pl.when(pl.col("target_kind") == "response").then(pl.col("determined")).otherwise(True).alias("determined")
    )
    return a.sort(["gcm", "scen", "window", "quantity", "region"])


def add_ceiling(s: dict, out: str, sub: str) -> dict:
    """Join the other-seed null's conjunctive pass fractions (same scale, same tolerance column) as ceiling_*."""
    f = f"{out}/null_a_other_seed/{sub}summary_conjunctive.csv"
    if not os.path.exists(f):
        return s
    ce = pl.read_csv(f).select(["gcm", "scen", "window", "panel"] + [
        pl.col(c).alias(f"ceiling_{c}") for c in ["all_pass_frac", "all_pass_cell_frac", "all_pass_q90_frac",
                                                   "all_pass_cal_frac"]])
    s["conjunctive"] = s["conjunctive"].join(ce, on=["gcm", "scen", "window", "panel"], how="left")
    return s


def run_score(pred_levels: pl.DataFrame, label: str, out: str, cov: dict, quiet: bool = False,
              scope: str = "all") -> dict:
    t0 = time.time()
    od = f"{out}/{label}"
    os.makedirs(od, exist_ok=True)
    targets, prov = make_targets(pred_levels)
    d = score_targets(targets, scope)
    d.write_parquet(f"{od}/cells.parquet")
    s = add_ceiling(summarise(d), out, "")
    s["quantity"].write_csv(f"{od}/summary_quantity.csv")
    s["conjunctive"].write_csv(f"{od}/summary_conjunctive.csv")
    if s["criterion"].height:
        s["criterion"].write_csv(f"{od}/summary_criterion.csv")
    ag = aggregate_response(d)
    ag.write_csv(f"{od}/aggregate_response.csv")
    # ---- block scale (same code, blocks in place of cells)
    cells = sorted(pred_levels["Cell"].unique().to_list())
    bscale, mask = block_reference_for(cells, scope)
    bl = pred_to_blocks(pred_levels, mask)
    btargets, _ = make_targets(bl, bscale)
    bd = score_targets(btargets, "all", bscale)
    os.makedirs(f"{od}/block", exist_ok=True)
    bd.write_parquet(f"{od}/block/cells.parquet")
    bs = add_ceiling(summarise(bd), out, "block/")
    bs["quantity"].write_csv(f"{od}/block/summary_quantity.csv")
    bs["conjunctive"].write_csv(f"{od}/block/summary_conjunctive.csv")
    if bs["criterion"].height:
        bs["criterion"].write_csv(f"{od}/block/summary_criterion.csv")
    cov = dict(cov, label=label, baselines=prov, scope=scope, n_scored_rows=d.height, n_missing=int(d["missing"].sum()),
               block_reference=bscale, n_blocks=int(bd["Cell"].n_unique()), n_block_rows=bd.height,
               n_block_missing=int(bd["missing"].sum()), wall_s=round(time.time() - t0, 1))
    json.dump(cov, open(f"{od}/coverage.json", "w"), indent=1, default=str)
    if not quiet:
        print_summary(label, s, ag, bs)
    return {"cells": d, **s, "aggregate": ag, "coverage": cov, "block": {"cells": bd, **bs}}


def print_summary(label: str, s: dict, ag: pl.DataFrame, bs: dict | None = None) -> None:
    print(f"\n===== {label} =====")
    with pl.Config(tbl_rows=400, tbl_cols=12, fmt_str_lengths=30, float_precision=3, tbl_width_chars=200):
        for scale, ss in [("CELL", s), ("BLOCK", bs)]:
            if ss is None:
                continue
            c = ss["conjunctive"].filter(pl.col("panel").is_in(["panel106", "extended", "count", "traits4_median",
                                                                "traits4_dist", "size_dist"]))
            for col in ["all_pass_frac", "all_pass_cal_frac"]:
                print(f"[{scale}] conjunctive pass fraction, tolerance column: {col}"
                      + ("  (ceiling = the other seed: see summary_conjunctive.csv ceiling_*)"))
                print(c.pivot(on="panel", index=["gcm", "scen", "window"], values=col).sort(["gcm", "scen", "window"]))
            if ss["criterion"].height:
                print(f"[{scale}] whole criterion (h1985 + w2015 + w2071 + r2071, every panel quantity):")
                print(ss["criterion"])
        a = ag.filter((pl.col("region") == "DE") & pl.col("window").is_in(["r2071"]) &
                      pl.col("quantity").is_in(["n_per_patch", "agb_stand", "SLA_q50", "Wooddens_q50", "D95max_q50",
                                                "minwscal_q50", "Height_q50", "share_3"]))
        if a.height:
            print(a.select(["gcm", "scen", "quantity", "aggC", "aggE", "ratio_E_over_C", "sn", "determined", "pass"]))


# ---------------------------------------------------------------------------------------------------------
# nulls
# ---------------------------------------------------------------------------------------------------------
def nulls(out: str) -> int:
    lv = pl.read_parquet(f"{REFDIR}/levels_long.parquet")
    s1 = lv.filter(pl.col("seed") == 1).drop(["seed", "valid"])
    s2 = lv.filter((pl.col("seed") == 2) & pl.col("valid")).drop(["seed", "valid"])
    res = {}
    # (a) the other seed: seed 2 predicting seed 1 (every valid window; responses from seed 2's own baseline)
    res["null_a_other_seed"] = run_score(s2, "null_a_other_seed", out, {"null": "seed 2 levels as prediction"})
    # (b) persistence: seed-1 1985-2014 predicting w2015 and w2071 of every scenario (its response is 0);
    #     h1985 itself is not a target (it would be the truth); the response baseline falls back to the
    #     reference seed-1 h1985, i.e. pred response = 0 exactly = (c).
    h = s1.filter(pl.col("window") == "h1985")
    parts = []
    for scen in SSPS:
        for w in ["w2015", "w2071"]:
            parts.append(h.with_columns(pl.lit(scen).alias("scen"), pl.lit(w).alias("window")))
    pers = pl.concat(parts).select(s1.columns)
    res["null_b_persistence"] = run_score(pers, "null_b_persistence", out,
                                          {"null": "seed-1 h1985 levels predicting w2015/w2071; response = 0"})
    # (d) equilibrium: seed-1 2071-2100 predicting seed-1 3071-3100 (same gcm, scen)
    eq = s1.filter(pl.col("window") == "w2071").with_columns(pl.lit("w3071").alias("window"))
    res["null_d_equilibrium"] = run_score(eq, "null_d_equilibrium", out,
                                          {"null": "seed-1 w2071 levels predicting w3071"})
    # (e) spatial null: every cell gets the Germany-wide area-weighted seed-1 mean of its target (all windows)
    st = pl.read_parquet(f"{R.XDE}/climate/cell_static.parquet").select(
        [pl.col("Cell").cast(pl.Int32), "area_km2_approx"])
    m = s1.join(st, on="Cell").group_by(["gcm", "scen", "window", "quantity"]).agg(
        ((pl.col("value") * pl.col("area_km2_approx")).sum() / pl.col("area_km2_approx").sum()).alias("m"))
    gm = s1.join(m, on=["gcm", "scen", "window", "quantity"]).with_columns(pl.col("m").alias("value")).select(
        s1.columns)
    res["null_e_germany_mean"] = run_score(gm, "null_e_germany_mean", out,
                                           {"null": "Germany-wide area-weighted mean of seed 1, every cell"})
    # one compact table across nulls
    rows = []
    for name, r in res.items():
        c = r["conjunctive"].with_columns(pl.lit(name).alias("null"))
        rows.append(c)
    allc = pl.concat(rows)
    allc.write_csv(f"{out}/nulls_conjunctive.csv")
    allq = pl.concat([r["quantity"].with_columns(pl.lit(n).alias("null")) for n, r in res.items()])
    allq.write_csv(f"{out}/nulls_quantity.csv")
    crit = [r["criterion"].with_columns(pl.lit(n).alias("null")) for n, r in res.items() if r["criterion"].height]
    if crit:
        pl.concat(crit).write_csv(f"{out}/nulls_criterion.csv")
    pl.concat([r["aggregate"].with_columns(pl.lit(n).alias("null")) for n, r in res.items()]).write_csv(
        f"{out}/nulls_aggregate.csv")
    log("nulls done")
    return 0


def selftest(out: str) -> int:
    """Roster path == reference path: reduce the dev subset (Cell % 10 == 0) of one seed-2 member-window
    through the ROSTER contract and compare to the reference statistics for those cells."""
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
    rec = {"selftest": "roster path vs reference on dev subset", "member": member, "cells": len(cells),
           "rows_ref": ref.height, "rows_roster": lev.height, "unmatched": n_unmatched, "max_rel_diff": dmax,
           "ok": ok}
    # and the scorer on that roster: seed 2 scored against seed 1 must equal null (a) for these cells
    r = run_score(lev, "selftest_roster_s2_dev", out, cov, quiet=True, scope="covered")
    na = f"{out}/null_a_other_seed/cells.parquet"
    if os.path.exists(na):
        a = pl.read_parquet(na).filter((pl.col("window") == "h1985") & pl.col("Cell").is_in(cells))
        b = r["cells"].filter(pl.col("window") == "h1985")
        jj = a.join(b, on=["gcm", "scen", "window", "Cell", "quantity"], suffix="_r")
        rec["pass_mismatch_vs_null_a"] = int(
            (jj["pass"] != jj["pass_r"]).sum() + (jj["pass_cal"] != jj["pass_cal_r"]).sum())
        rec["rows_compared_vs_null_a"] = jj.height
        rec["ok"] = rec["ok"] and rec["pass_mismatch_vs_null_a"] == 0 and jj.height == b.height
    # block path: the roster's block values must equal the block_dev reference's seed-2 values exactly
    bb = r["block"]["cells"].filter((pl.col("target_kind") == "level") & pl.col("R").is_not_null())
    rec["block_reference"] = r["coverage"]["block_reference"]
    rec["block_rows_compared"] = bb.height
    rec["block_max_rel_diff_E_vs_R"] = bb.select(
        ((pl.col("E") - pl.col("R")).abs() / pl.col("R").abs().clip(1e-12)).max()).item()
    rec["block_missing"] = int(bb["missing"].sum())
    rec["ok"] = rec["ok"] and bb.height > 0 and rec["block_missing"] == 0 and rec["block_max_rel_diff_E_vs_R"] < 1e-9
    # and the full-scale other-seed null's block E must equal the block reference's R (scorer vs reference code)
    nab = f"{out}/null_a_other_seed/block/cells.parquet"
    if os.path.exists(nab):
        x = pl.read_parquet(nab).filter((pl.col("target_kind") == "level") & pl.col("R").is_not_null())
        rec["null_a_block_rows"] = x.height
        rec["null_a_block_max_rel_diff_E_vs_R"] = x.select(
            ((pl.col("E") - pl.col("R")).abs() / pl.col("R").abs().clip(1e-12)).max()).item()
        rec["ok"] = rec["ok"] and rec["null_a_block_max_rel_diff_E_vs_R"] < 1e-9
    json.dump(rec, open(f"{out}/selftest.json", "w"), indent=1)
    print(json.dumps(rec, indent=1))
    return 0 if rec["ok"] else 3


def headline(out: str, labels: list[str] | None = None) -> int:
    """One compact table over scored submissions: per (label, scale, target window, panel, tolerance column) the
    median / min / max over (gcm, scen) of the conjunctive pass fraction, + the DE aggregate response pass rate."""
    labels = labels or ["null_a_other_seed", "null_b_persistence", "null_d_equilibrium", "null_e_germany_mean"]
    rows = []
    for lab in labels:
        for scale, sub in [("cell", ""), ("block", "block/")]:
            f = f"{out}/{lab}/{sub}summary_conjunctive.csv"
            if not os.path.exists(f):
                continue
            c = pl.read_csv(f).filter(pl.col("panel").is_in(["panel106", "extended", "count", "traits4_median",
                                                             "traits4_dist", "size_dist", "pft_shares"]))
            for col in ["all_pass_frac", "all_pass_cell_frac", "all_pass_q90_frac", "all_pass_cal_frac"]:
                a = c.group_by(["window", "panel"]).agg(
                    pl.col(col).median().alias("med"), pl.col(col).min().alias("min"), pl.col(col).max().alias("max"),
                    pl.len().alias("n_gcm_scen"))
                rows.append(a.with_columns(pl.lit(lab).alias("label"), pl.lit(scale).alias("scale"),
                                           pl.lit(col.replace("all_pass_", "").replace("_frac", "") or "stratum")
                                           .alias("tolerance")))
    h = pl.concat(rows).with_columns(
        pl.col("tolerance").replace({"frac": "stratum"})).select(
        ["label", "scale", "tolerance", "panel", "window", "med", "min", "max", "n_gcm_scen"]).sort(
        ["label", "scale", "tolerance", "panel", "window"])
    h.write_csv(f"{out}/headline.csv")
    ag = []
    for lab in labels:
        f = f"{out}/{lab}/aggregate_response.csv"
        if os.path.exists(f):
            a = pl.read_csv(f).filter(pl.col("window").is_in(["r2015", "r2071"]))
            ag.append(a.group_by(["window", "region"]).agg(
                pl.col("pass").mean().alias("pass_frac"), pl.col("pass").filter(pl.col("determined")).mean()
                .alias("pass_frac_determined"), pl.len().alias("n")).with_columns(pl.lit(lab).alias("label")))
    if ag:
        pl.concat(ag).sort(["label", "window", "region"]).write_csv(f"{out}/headline_aggregate_response.csv")
    with pl.Config(tbl_rows=500, tbl_width_chars=200, float_precision=3):
        print(h.filter(pl.col("panel").is_in(["panel106", "extended"])
                       & pl.col("tolerance").is_in(["stratum", "cal"])))
        if ag:
            print(pl.concat(ag).sort(["label", "window", "region"]))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["score", "nulls", "selftest", "headline"])
    ap.add_argument("--pred")
    ap.add_argument("--format", choices=["roster", "stats"], default="stats")
    ap.add_argument("--label")
    ap.add_argument("--gcm")
    ap.add_argument("--scen")
    ap.add_argument("--npatch", type=int, default=R.NPATCH)
    ap.add_argument("--cells")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--scope", choices=["all", "covered"], default="all",
                    help="all = acceptance (uncovered cells fail); covered = score only the cells submitted")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if a.cmd == "nulls":
        return nulls(a.out)
    if a.cmd == "selftest":
        return selftest(a.out)
    if a.cmd == "headline":
        return headline(a.out, a.label.split(",") if a.label else None)
    assert a.pred and a.label, "score needs --pred and --label"
    if a.format == "roster":
        cells = [int(x) for x in open(a.cells).read().split()] if a.cells else None
        lev, cov = roster_to_levels(a.pred, a.gcm, a.scen, a.npatch, cells)
    else:
        lev, cov = stats_to_levels(a.pred, a.gcm, a.scen)
    cov["pred"] = a.pred
    cov["format"] = a.format
    run_score(lev, a.label, a.out, cov, scope=a.scope)
    return 0


if __name__ == "__main__":
    sys.exit(main())
