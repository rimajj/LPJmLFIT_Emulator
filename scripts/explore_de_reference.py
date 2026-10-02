#!/usr/bin/env python
"""explore_de_reference.py -- the REFERENCE STATISTICS + TOLERANCES the Germany emulator is scored against.

Line X, Germany data-driven emulator exploration (2026-10-01). Read-only on the converted `ind` parquet
(/p/tmp/jamirp/X_de/ind, produced by explore_de_convert.py). Writes only under /p/tmp/jamirp/X_de/reference.

Acceptance definition implemented (ADR 0106 + its operationalisation in ADR 0111; adaptations listed in
REFERENCE_DEFINITION below and in /p/tmp/jamirp/X_de/reference/_DEFINITION.md):

  population   living trees = Type <= 6 and isdead == 0 (and Height >= 5 m, a no-op on the C output, whose writer
               only emits stems taller than 5 m; it makes an emulator roster comparable)
  per (gcm, scen, seed, window, Cell), pooled over the window's 30 years (the "climatology" basis of ADR 0111):
    n_per_patch   living tree stem-years / (years x NPATCH=250)   -- CONFIGURED patch count (ADR 0111 (c))
    agb_stand     sum of agb over living tree stem-years / (years x 250)   [gC/m2 per patch]
    share_<t>     stem-year share of PFT t (t = 0..6) among living trees
    <v>_<q>       q in q05,q25,q50,q75,q95 of v in SLA, Wooddens, D95max, minwscal, Longevity, Height, agb,
                  over all living tree stem-years of the window (linear interpolation)
  tolerance    allowed |E - C| per (cell, quantity, target), with C = seed 1, R = seed 2:
    level, relative quantity:  |C| * max(10 %, S)   S = median over the cell's density stratum of |C-R|/mean(C,R)
    level, share:              max(0.10*C, S_abs, 0.005)        S_abs = stratum median of |C-R|
    response (w - h1985), relative quantity: max(0.10*|dC|, S_r * |hist level|)
                 S_r = stratum median of |dC - dR| / |mean hist level|
    response, share:           max(0.10*|dC|, stratum median |dC-dR|, 0.005)
    Secondary columns: the literal per-cell spread (allowed_cell) and the stratum 90th percentile (allowed_q90).

Stages:
  reduce <idx>      one member-window (row idx of ind/_gates.csv) -> reference/stats/<member>.parquet (+ .json gate),
                    reference/cell_year/<member>.parquet
  submit [array]    SLURM array of `reduce` (default 0-39)
  assemble          -> reference/levels_long.parquet, reference/tolerance.parquet, reference/aggregate.parquet,
                       reference/_gates.json, reference/_DEFINITION.md; and the truth-seed-2 twins
                       tolerance_t2.parquet, aggregate_t2.parquet, _gates_t2.json (SH14)
  calibrate [ts]    re-calibrates tolerance{,_t2}.parquet in place (allowed_cal, allowed_cal_c; assemble already
                    calibrates since SH14) -- the second run passes the panel in 95 % of cells
  blocks            the same reference at ~1-degree BLOCK scale -> reference/block/, reference/block_dev/
                    (*_t2 files = truth seed 2)
  frozen            window statistics of FROZEN 1985 / 2014 rosters per gcm and seed -> reference/frozen/ (SH14)
  verify            independent duckdb recomputation of reference/stats for sample cells -> reference/_verify.json
  collect           print which members are done / missing

Env knobs (EXPORT them): DEREF_FORCE=1 re-reduce even if done. XDE_REFSET=clean|full (default clean):
  OWNER DECISION 2026-10-01 -- the 2071-2100 / 3071-3100 runs used the wrong humidity setting; the CLEAN set
  (1985-2044 only, derived files in reference/clean/) is the default for assemble/calibrate/blocks; "full" rebuilds
  the legacy reference/ files incl. the excluded windows. stats/, cell_year/, frozen/ are shared by both sets.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# SH14 repair: the data root, the configured patch count and the partition width are parameters (env knobs, EXPORT
# them), not Germany constants. Defaults = the Germany round-1/2 setup.
XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
IND = f"{XDE}/ind"
OUT = os.environ.get("XDE_REFERENCE", f"{XDE}/reference")
LOGDIR = f"{REPO}/logs"
PY = "/home/jamirp/.conda/envs/py311_new/bin/python"

NPATCH = int(os.environ.get("XDE_NPATCH", "250"))
CELLS_PER_PARTITION = int(os.environ.get("XDE_CELLS_PER_PARTITION", "500"))  # the converter's cb = Cell // 500
# SH14 repair 2: the name of the whole-domain aggregate region (the reference tables call it "DE"; a global reuse
# exports XDE_REGION_ALL=GLOBAL and rebuilds). Never hard-code the literal in a consumer: use R.REGION_ALL.
REGION_ALL = os.environ.get("XDE_REGION_ALL", "DE")
HMIN = 5.0
NMIN_STEMYEARS = 30  # fewer living stem-years than this in a window -> quantiles are not scored (null)
TRAITS = ["SLA", "Wooddens", "D95max", "minwscal", "Longevity", "Height", "agb"]
QS = [0.05, 0.25, 0.50, 0.75, 0.95]
QN = ["q05", "q25", "q50", "q75", "q95"]
PFTS = list(range(7))
WINDOWS = {"h1985": (1985, 2014), "w2015": (2015, 2044), "w2071": (2071, 2100), "w3071": (3071, 3100)}
RESPONSES = {"r2071": "w2071", "r2015": "w2015"}  # response target -> the window it is (window - h1985) of
# SH14 amendment 3: between-scenario CONTRASTS at fixed gcm and seed, X(scen, w) - X(ssp126, w)
CONTRASTS = {"c2071": "w2071", "c2015": "w2015"}  # contrast target -> the window both legs are taken in
CONTRAST_BASE = "ssp126"
CONTRAST_SCENS = ["ssp370", "ssp245"]
# ---- OWNER DECISION 2026-10-01 ("lets only use the earlier data that is correct, for now"). Every 2071-2100 and
# 3071-3100 segment ran with "relative_humidity" missing from its config (LPJmL default false, fscanconfig.c:255):
# the relative-humidity file was read as specific humidity -> VPD 0 -> water-stress mortality exactly 0 in all 24
# ssp runs. Those windows (and every target built from them) are EXCLUDED by default. The REFERENCE SET selects:
#   "clean" (DEFAULT): only 1985-2044 (h1985, w2015, r2015, c2015); derived files under reference/clean/; the
#                      calibration is fitted on these targets only; primary response = c2015.
#   "full"           : the round-1/SH14 reference incl. the corrupted late windows (reference/, legacy, kept so the
#                      old behaviour stays reachable -- NEVER use its w2071/w3071/r2071/c2071 rows as evidence).
# Select with the env knob XDE_REFSET (export it) or the scorer's --refset; R.set_refset() switches in-process.
EXCLUDED_WINDOWS = ("w2071", "w3071")
EXCLUDED_TARGETS = ("w2071", "w3071", "r2071", "c2071")
EXCLUSION_REASON = ("owner decision 2026-10-01: 2071-2100 and 3071-3100 segments ran with relative_humidity "
                    "missing from the config (humidity read as specific humidity, VPD 0, water-stress mortality 0); "
                    "only 1985-2044 is correct data")
ALL_WINDOWS, ALL_RESPONSES, ALL_CONTRASTS = dict(WINDOWS), dict(RESPONSES), dict(CONTRASTS)
REFSET = "full"
REFOUT = OUT
PRIMARY_CONTRAST = "c2071"
CRITERION_LEVELS: list[str] = []
CRITERION_TARGETS: list[str] = []
NULL_FUTURE_WINDOWS: list[str] = []


def set_refset(name: str) -> None:
    """Switch every module-level window table and the derived-file directory between the clean (default) and the
    full (legacy) reference set. Mutates WINDOWS/RESPONSES/CONTRASTS IN PLACE so importers holding the dicts see
    the change."""
    global REFSET, REFOUT, PRIMARY_CONTRAST
    assert name in ("clean", "full"), f"unknown reference set {name!r} (clean|full)"
    REFSET = name
    for d, full in [(WINDOWS, ALL_WINDOWS), (RESPONSES, ALL_RESPONSES), (CONTRASTS, ALL_CONTRASTS)]:
        d.clear()
        d.update({k: v for k, v in full.items() if name == "full" or k not in EXCLUDED_TARGETS})
    REFOUT = OUT if name == "full" else f"{OUT}/clean"
    PRIMARY_CONTRAST = "c2071" if name == "full" else "c2015"
    # whole-criterion definition: the level windows besides h1985 and the response targets it is formed with
    CRITERION_LEVELS[:] = ["w2015", "w2071"] if name == "full" else ["w2015"]
    CRITERION_TARGETS[:] = ["r2071", "c2071"] if name == "full" else ["r2015", "c2015"]
    # the future level windows the persistence / frozen-2014 nulls predict (w3071 never: equilibrium null only)
    NULL_FUTURE_WINDOWS[:] = ["w2015", "w2071"] if name == "full" else ["w2015"]


set_refset(os.environ.get("XDE_REFSET", "clean"))
STRATA_EDGES = [2.0, 5.0, 10.0, 20.0]
STRATA_LABELS = ["<2", "2-5", "5-10", "10-20", ">20"]
MIN_CELLS_STRATUM = 30
SHARE_FLOOR = 0.005
REL_FLOOR = 0.10
READ_COLS = ["Year", "Cell", "Type", "isdead"] + TRAITS

QUANTITIES = (
    ["n_per_patch", "agb_stand"]
    + [f"share_{t}" for t in PFTS]
    + [f"{v}_{q}" for v in TRAITS for q in QN]
)
PANEL106 = ["n_per_patch"] + [
    f"{v}_{q}" for v in ["SLA", "Wooddens", "D95max", "minwscal", "Height", "agb"] for q in QN
]
EXTENDED = QUANTITIES  # + Longevity quantiles, agb_stand, PFT shares


def kind(q: str) -> str:
    return "frac" if q.startswith("share_") else "rel"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------------------------------------------------
# THE reduction. The scorer imports these two functions, so a roster an emulator writes is reduced by exactly
# the same code as the C output.
# ---------------------------------------------------------------------------------------------------------
def living(lf: pl.LazyFrame) -> pl.LazyFrame:
    return lf.filter((pl.col("Type") <= 6) & (pl.col("isdead") == 0) & (pl.col("Height") >= HMIN))


def reduce_window(trees: pl.DataFrame, cells_years: pl.DataFrame, npatch: int = NPATCH) -> pl.DataFrame:
    """trees: living tree stem-years of ONE window (columns Cell, Type, TRAITS). cells_years: (Cell, n_years)
    for every cell that exists in the window (cells with no living tree get n_per_patch = 0).
    Returns one row per Cell with the QUANTITIES columns + n_stemyears, n_years."""
    aggs = [pl.len().alias("n_stemyears"), pl.col("agb").cast(pl.Float64).sum().alias("agb_sum")]
    aggs += [(pl.col("Type") == t).sum().alias(f"n_t{t}") for t in PFTS]
    aggs += [
        pl.col(v).quantile(q, interpolation="linear").alias(f"{v}_{qn}")
        for v in TRAITS
        for q, qn in zip(QS, QN, strict=True)
    ]
    g = trees.group_by("Cell").agg(aggs)
    assert g["Cell"].n_unique() == g.height, "duplicate Cell in window aggregate"
    cy = cells_years.with_columns(pl.col("Cell").cast(pl.Int32), pl.col("n_years").cast(pl.Int32))
    g = g.with_columns(pl.col("Cell").cast(pl.Int32))
    extra = set(g["Cell"].to_list()) - set(cy["Cell"].to_list())
    assert not extra, f"trees in cells absent from the census: {sorted(extra)[:10]}"
    d = cy.join(g, on="Cell", how="left").with_columns(
        pl.col("n_stemyears").fill_null(0), pl.col("agb_sum").fill_null(0.0)
    )
    d = d.with_columns([pl.col(f"n_t{t}").fill_null(0) for t in PFTS])
    den = pl.col("n_years").cast(pl.Float64) * npatch
    n = pl.col("n_stemyears").cast(pl.Float64)
    d = d.with_columns(
        (n / den).alias("n_per_patch"),
        (pl.col("agb_sum").cast(pl.Float64) / den).alias("agb_stand"),
        *[
            pl.when(n > 0).then(pl.col(f"n_t{t}") / n).otherwise(None).alias(f"share_{t}")
            for t in PFTS
        ],
    )
    small = pl.col("n_stemyears") < NMIN_STEMYEARS
    d = d.with_columns(
        [
            pl.when(small).then(None).otherwise(pl.col(f"{v}_{q}").cast(pl.Float64)).alias(f"{v}_{q}")
            for v in TRAITS
            for q in QN
        ]
    )
    cols = ["Cell", "n_years", "n_stemyears"] + QUANTITIES
    return d.select(cols).sort("Cell")


def reduce_cell_year(trees: pl.DataFrame, npatch: int = NPATCH) -> pl.DataFrame:
    """Per (Cell, Year): n_per_patch, agb_stand, per-PFT counts per patch, trait medians (diagnostic table)."""
    aggs = [pl.len().alias("n_living"), pl.col("agb").cast(pl.Float64).sum().alias("agb_sum")]
    aggs += [(pl.col("Type") == t).sum().alias(f"n_t{t}") for t in PFTS]
    aggs += [pl.col(v).median().alias(f"{v}_q50") for v in TRAITS]
    g = trees.group_by(["Cell", "Year"]).agg(aggs)
    assert g.select(["Cell", "Year"]).n_unique() == g.height, "duplicate (Cell, Year) in cell-year aggregate"
    return g.with_columns(
        (pl.col("n_living") / npatch).alias("n_per_patch"),
        (pl.col("agb_sum") / npatch).alias("agb_stand"),
    ).sort(["Cell", "Year"])


# ---------------------------------------------------------------------------------------------------------
def gates() -> pl.DataFrame:
    return pl.read_csv(f"{IND}/_gates.csv")


def member_root(r: dict) -> str:
    return f"{IND}/{r['gcm']}/{r['scen']}/s{r['seed']}/{r['window']}"


def partitions(root: str) -> list[int]:
    """The cb=NN partition ids present under a member root (globbed, not range(19): the partition count is a
    property of the converted domain, not a constant)."""
    import glob

    ids = sorted(int(os.path.basename(os.path.dirname(f)).split("=", 1)[1])
                 for f in glob.glob(f"{root}/cb=*/part-0.parquet"))
    assert ids, f"no cb=*/part-0.parquet under {root}"
    return ids


def reduce_member(idx: int) -> int:
    g = gates().filter(pl.col("idx") == idx)
    assert g.height == 1, f"no gate row idx={idx}"
    r = g.row(0, named=True)
    member = r["member"]
    os.makedirs(f"{OUT}/stats", exist_ok=True)
    os.makedirs(f"{OUT}/cell_year", exist_ok=True)
    f_stats = f"{OUT}/stats/{member}.parquet"
    f_cy = f"{OUT}/cell_year/{member}.parquet"
    f_json = f"{OUT}/stats/{member}.json"
    gate_mtime = os.path.getmtime(f"{IND}/_gates/{member}.json")
    if os.path.exists(f_json) and os.environ.get("DEREF_FORCE") != "1":
        old = json.load(open(f_json))
        if old.get("ok") and old.get("gate_json_mtime") == gate_mtime and os.path.exists(f_stats):
            log(f"{member}: already done, skip (DEREF_FORCE=1 to redo)")
            return 0
    t0 = time.time()
    census = pl.read_parquet(f"{IND}/_census/{member}.parquet")
    y0, y1 = WINDOWS[r["window"]]
    census = census.filter(pl.col("Year").is_between(y0, y1))
    cells_years = census.group_by("Cell").agg(pl.len().alias("n_years"))
    root = member_root(r)
    parts_w, parts_cy = [], []
    n_live_total = 0
    n_height_cut = 0
    for cb in partitions(root):
        f = f"{root}/cb={cb:02d}/part-0.parquet"
        if not os.path.exists(f):
            raise FileNotFoundError(f)
        lf = pl.scan_parquet(f).select(READ_COLS)
        base = lf.filter((pl.col("Type") <= 6) & (pl.col("isdead") == 0))
        trees = living(lf).collect()
        n_base = base.select(pl.len()).collect().item()
        n_height_cut += n_base - trees.height
        n_live_total += trees.height
        cyb = cells_years.filter((pl.col("Cell") // CELLS_PER_PARTITION) == cb)
        parts_w.append(reduce_window(trees, cyb))
        parts_cy.append(reduce_cell_year(trees))
        del trees
        if cb % 6 == 0:
            log(f"{member}: cb={cb:02d} done ({time.time() - t0:.0f} s)")
    w = pl.concat(parts_w)
    cy = pl.concat(parts_cy)
    assert w["Cell"].n_unique() == w.height
    assert cy.select(["Cell", "Year"]).n_unique() == cy.height
    meta = [
        pl.lit(r["gcm"]).alias("gcm"),
        pl.lit(r["scen"]).alias("scen"),
        pl.lit(int(r["seed"])).cast(pl.Int8).alias("seed"),
        pl.lit(r["window"]).alias("window"),
    ]
    w = w.with_columns(meta).select(["gcm", "scen", "seed", "window"] + [c for c in w.columns])
    cy = cy.with_columns(meta)
    sum_n = int(w["n_stemyears"].sum())
    rec = {
        "member": member,
        "idx": idx,
        "source_gate_pass_traitkey": bool(r["gate_pass_traitkey"]),
        "source_failed_checks": r["failed_checks"],
        "valid_window": bool(r["gate_pass_traitkey"]),
        "gate_json_mtime": gate_mtime,
        "n_cells": w.height,
        "n_years_min": int(w["n_years"].min()),
        "n_years_max": int(w["n_years"].max()),
        "cells_lt_full_years": int((w["n_years"] < (y1 - y0 + 1)).sum()),
        "living_tree_rows": n_live_total,
        "gate_tree_live_rows": int(r["tree_live_rows"]),
        "rows_match_gate": sum_n == int(r["tree_live_rows"]) == n_live_total,
        "height_cut_removed": n_height_cut,
        "cells_with_zero_trees": int((w["n_stemyears"] == 0).sum()),
        "cells_below_nmin": int((w["n_stemyears"] < NMIN_STEMYEARS).sum()),
        "n_per_patch_range": [float(w["n_per_patch"].min()), float(w["n_per_patch"].max())],
        "wall_s": round(time.time() - t0, 1),
    }
    rec["ok"] = bool(rec["rows_match_gate"] and n_height_cut == 0)
    w.write_parquet(f_stats)
    cy.write_parquet(f_cy)
    json.dump(rec, open(f_json, "w"), indent=1)
    log(json.dumps(rec))
    return 0 if rec["ok"] else 2


def submit(args: list[str]) -> int:
    array = args[0] if args else "0-39"
    os.makedirs(LOGDIR, exist_ok=True)
    os.makedirs(f"{XDE}/_jobs", exist_ok=True)
    jcf = f"{XDE}/_jobs/X-de-ref.jcf"
    me = os.path.abspath(__file__)
    open(jcf, "w").write(
        f"""#!/usr/bin/env bash
#SBATCH --job-name=X-de-ref
#SBATCH --account=waldspektrum
#SBATCH --partition=standard
#SBATCH --qos=short
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=01:00:00
#SBATCH --array={array}%20
#SBATCH --output={LOGDIR}/X-de-ref.%A_%a.out
#SBATCH --error={LOGDIR}/X-de-ref.%A_%a.out
export POLARS_MAX_THREADS=16
echo "=== X-de-ref task $SLURM_ARRAY_TASK_ID on $(hostname) at $(date) ==="
{PY} {me} reduce $SLURM_ARRAY_TASK_ID
rc=$?
echo "=== JOB DONE tag=X-de-ref task=$SLURM_ARRAY_TASK_ID exit=$rc ==="
exit $rc
"""
    )
    out = subprocess.run(["sbatch", jcf], capture_output=True, text=True)
    print(out.stdout, out.stderr)
    return out.returncode


def collect() -> None:
    g = gates()
    for r in g.iter_rows(named=True):
        f = f"{OUT}/stats/{r['member']}.json"
        if os.path.exists(f):
            j = json.load(open(f))
            print(r["idx"], r["member"], "ok" if j["ok"] else "NOT_OK", "valid" if j["valid_window"] else "INVALID",
                  j["wall_s"])
        else:
            print(r["idx"], r["member"], "not_done")


# ---------------------------------------------------------------------------------------------------------
# assemble: tolerances
# ---------------------------------------------------------------------------------------------------------
def load_levels() -> pl.DataFrame:
    """Long table of all reduced member-windows: gcm, scen, seed, window, Cell, quantity, value, valid."""
    g = gates()
    parts = []
    for r in g.iter_rows(named=True):
        j = json.load(open(f"{OUT}/stats/{r['member']}.json"))
        assert j["ok"], f"{r['member']} not ok"
        w = pl.read_parquet(f"{OUT}/stats/{r['member']}.parquet")
        lg = w.unpivot(index=["gcm", "scen", "seed", "window", "Cell"], on=QUANTITIES,
                       variable_name="quantity", value_name="value")
        parts.append(lg.with_columns(pl.lit(bool(j["valid_window"])).alias("valid")))
    d = pl.concat(parts)
    # reference set (owner decision 2026-10-01): the clean set keeps only the windows in WINDOWS (h1985, w2015)
    d = d.filter(pl.col("window").is_in(list(WINDOWS)))
    k = ["gcm", "scen", "seed", "window", "Cell", "quantity"]
    assert d.select(k).n_unique() == d.height
    return d


def stratum_expr(col: str) -> pl.Expr:
    return pl.col(col).cut(STRATA_EDGES, labels=STRATA_LABELS, left_closed=True).cast(pl.Utf8)


def strat_stats(d: pl.DataFrame, by: list[str], col: str) -> pl.DataFrame:
    """Median and q90 of `col` per (by + stratum); strata with < MIN_CELLS_STRATUM cells take the pooled value."""
    s = d.group_by(by + ["stratum"]).agg(
        pl.col(col).drop_nulls().median().alias("s_med"),
        pl.col(col).drop_nulls().quantile(0.9).alias("s_q90"),
        pl.col(col).drop_nulls().len().alias("s_n"),
    )
    p = d.group_by(by).agg(
        pl.col(col).drop_nulls().median().alias("p_med"), pl.col(col).drop_nulls().quantile(0.9).alias("p_q90")
    )
    s = s.join(p, on=by, how="left").with_columns(
        pl.when(pl.col("s_n") >= MIN_CELLS_STRATUM).then(pl.col("s_med")).otherwise(pl.col("p_med")).alias("s_med"),
        pl.when(pl.col("s_n") >= MIN_CELLS_STRATUM).then(pl.col("s_q90")).otherwise(pl.col("p_q90")).alias("s_q90"),
        (pl.col("s_n") >= MIN_CELLS_STRATUM).alias("stratum_own"),
    )
    return s.select(by + ["stratum", "s_med", "s_q90", "s_n", "stratum_own"])


def build_tolerance(lv: pl.DataFrame, truth_seed: int = 1) -> pl.DataFrame:
    """Tolerance table. truth_seed = 1 (default, the round-1 table): C = seed 1, R = seed 2. truth_seed = 2 (SH14
    amendment 2): C = seed 2, R = seed 1 -- for a hold-out whose history is shared with seed-1 training data.
    Targets: levels, responses (window - h1985, same seed) and, added by SH14 (amendment 3), CONTRASTS
    X(scen, w) - X(ssp126, w) at fixed gcm and seed (target_kind "contrast", windows c2015/c2071).
    Every round-1 column is unchanged for truth_seed = 1; new columns are appended (see DEFINITION)."""
    ts, ots = int(truth_seed), 3 - int(truth_seed)
    assert ts in (1, 2)
    k = ["gcm", "scen", "window", "Cell", "quantity"]
    s1 = lv.filter((pl.col("seed") == ts) & pl.col("valid")).select(k + [pl.col("value").alias("C")])
    s2 = (
        lv.filter((pl.col("seed") == ots) & pl.col("valid"))
        .select(k + [pl.col("value").alias("R")])
    )
    lev = s1.join(s2, on=k, how="left")
    # density stratum: 2-seed mean (truth seed alone where the other seed is invalid) of n_per_patch in that window
    dens = lev.filter(pl.col("quantity") == "n_per_patch").select(
        ["gcm", "scen", "window", "Cell", pl.when(pl.col("R").is_null()).then(pl.col("C"))
         .otherwise((pl.col("C") + pl.col("R")) / 2).alias("dens")]
    )
    lev = lev.join(dens, on=["gcm", "scen", "window", "Cell"], how="left").with_columns(
        stratum_expr("dens").alias("stratum")
    )
    # ---- levels
    lev = lev.with_columns(
        pl.when(pl.col("quantity").str.starts_with("share_"))
        .then((pl.col("C") - pl.col("R")).abs())
        .otherwise((pl.col("C") - pl.col("R")).abs() / ((pl.col("C") + pl.col("R")) / 2).abs())
        .alias("spread_cell"),
        pl.lit(None, dtype=pl.Float64).alias("scale"),
        pl.lit("level").alias("target_kind"),
    )
    # ---- responses: d = X(window) - X(h1985), same seed (one continuous trajectory per seed)
    resp_parts = []
    hist = lv.filter(pl.col("scen") == "Historical").select(
        ["gcm", "seed", "Cell", "quantity", pl.col("value").alias("H"), pl.col("valid").alias("Hvalid")]
    )
    for rname, wname in RESPONSES.items():
        fut = lv.filter((pl.col("window") == wname) & (pl.col("scen") != "Historical"))
        x = fut.join(hist, on=["gcm", "seed", "Cell", "quantity"], how="left").with_columns(
            (pl.col("value") - pl.col("H")).alias("D"), (pl.col("valid") & pl.col("Hvalid")).alias("dvalid")
        )
        c = x.filter((pl.col("seed") == ts) & pl.col("dvalid")).select(
            ["gcm", "scen", "Cell", "quantity", pl.col("D").alias("C"), pl.col("H").alias("H1")]
        )
        r = x.filter((pl.col("seed") == ots) & pl.col("dvalid")).select(
            ["gcm", "scen", "Cell", "quantity", pl.col("D").alias("R"), pl.col("H").alias("H2")]
        )
        y = c.join(r, on=["gcm", "scen", "Cell", "quantity"], how="left").with_columns(
            pl.lit(rname).alias("window")
        )
        resp_parts.append(y)
    rsp = pl.concat(resp_parts)
    rsp = rsp.with_columns(((pl.col("H1") + pl.col("H2")) / 2).abs().alias("scale"))
    # density stratum of a response = the HISTORICAL density stratum of the cell
    hdens = dens.filter(pl.col("window") == "h1985").select(["gcm", "Cell", "dens"])
    rsp = rsp.join(hdens, on=["gcm", "Cell"], how="left").with_columns(stratum_expr("dens").alias("stratum"))
    rsp = rsp.with_columns(
        pl.when(pl.col("quantity").str.starts_with("share_"))
        .then((pl.col("C") - pl.col("R")).abs())
        .otherwise((pl.col("C") - pl.col("R")).abs() / pl.col("scale"))
        .alias("spread_cell"),
        pl.lit("response").alias("target_kind"),
        # per-cell signal-to-noise of the truth's response (ADR 0111 S/N: |mean response| / |seed1 - seed2|)
    )
    # ---- contrasts (SH14 amendment 3): d = X(scen, w) - X(ssp126, w), same gcm, same seed. Both legs share the
    #      CO2 file and the segment's humidity configuration, so the contrast is free of both confounders.
    #      scale = |mean over seeds of the ssp126 leg's level| (the contrast's baseline); stratum = historical.
    con_parts = []
    basel = lv.filter(pl.col("scen") == CONTRAST_BASE).select(
        ["gcm", "seed", "window", "Cell", "quantity", pl.col("value").alias("B"), pl.col("valid").alias("Bvalid")]
    )
    for cname, wname in CONTRASTS.items():
        fut = lv.filter((pl.col("window") == wname) & pl.col("scen").is_in(CONTRAST_SCENS))
        x = fut.join(basel.filter(pl.col("window") == wname).drop("window"),
                     on=["gcm", "seed", "Cell", "quantity"], how="left").with_columns(
            (pl.col("value") - pl.col("B")).alias("D"), (pl.col("valid") & pl.col("Bvalid")).alias("dvalid"))
        c = x.filter((pl.col("seed") == ts) & pl.col("dvalid")).select(
            ["gcm", "scen", "Cell", "quantity", pl.col("D").alias("C"), pl.col("B").alias("B1"),
             pl.col("value").alias("V1")])
        r = x.filter((pl.col("seed") == ots) & pl.col("dvalid")).select(
            ["gcm", "scen", "Cell", "quantity", pl.col("D").alias("R"), pl.col("B").alias("B2"),
             pl.col("value").alias("V2")])
        con_parts.append(c.join(r, on=["gcm", "scen", "Cell", "quantity"], how="left").with_columns(
            pl.lit(cname).alias("window")))
    con = pl.concat(con_parts)
    con = con.with_columns(
        pl.when(pl.col("B2").is_null()).then(pl.col("B1").abs())
        .otherwise(((pl.col("B1") + pl.col("B2")) / 2).abs()).alias("scale"))
    con = con.join(hdens, on=["gcm", "Cell"], how="left").with_columns(stratum_expr("dens").alias("stratum"))
    con = con.with_columns(
        pl.when(pl.col("quantity").str.starts_with("share_"))
        .then((pl.col("C") - pl.col("R")).abs())
        .otherwise((pl.col("C") - pl.col("R")).abs() / pl.col("scale"))
        .alias("spread_cell"),
        pl.lit("contrast").alias("target_kind"),
        # SH14 repair (verifier: common random numbers). In the truth BOTH scenario legs of one seed restart from
        # the same 2014 state incl. its random-number state, so the replica's contrast error |C - R| is the noise
        # of a run whose legs are BRANCHED from one state. An arm whose legs are not branched carries more noise.
        # Two empirical brackets for such an arm (sigma^2 = per-leg level variance, rho = within-seed leg
        # correlation; an unbranched arm vs the truth has variance 2 sigma^2 (2 - rho)):
        #   dev_unbr_hi = |V2 - V1|              replica scen leg + the TRUTH's ssp126 leg: 2 sigma^2  (optimistic)
        #   dev_unbr_lo = |(V1 - V2) + (B1 - B2)| the two cross-seed contrasts against each other: 4 sigma^2 (1+rho)
        #                                        (pessimistic)
        (pl.col("V2") - pl.col("V1")).abs().alias("dev_unbr_hi"),
        ((pl.col("V1") - pl.col("V2")) + (pl.col("B1") - pl.col("B2"))).abs().alias("dev_unbr_lo"),
    )
    cols = ["gcm", "scen", "window", "Cell", "quantity", "target_kind", "C", "R", "scale", "dens", "stratum",
            "spread_cell"]
    ucols = ["dev_unbr_lo", "dev_unbr_hi"]
    nul = [pl.lit(None, dtype=pl.Float64).alias(c) for c in ucols]
    allt = pl.concat([lev.with_columns(nul).select(cols + ucols), rsp.with_columns(nul).select(cols + ucols),
                      con.select(cols + ucols)])
    # SH14 amendment 1: the SYMMETRIC level spread |C-R|/|C| (so |C| * S >= |C-R| holds for the replica itself);
    # identical to spread_cell for shares, responses and contrasts (those are already absolute / scale-based)
    isf0 = pl.col("quantity").str.starts_with("share_")
    allt = allt.with_columns(
        pl.when((pl.col("target_kind") == "level") & ~isf0)
        .then((pl.col("C") - pl.col("R")).abs() / pl.col("C").abs())
        .otherwise(pl.col("spread_cell")).alias("spread_cell_c"))
    allt = allt.with_columns(
        pl.when(pl.col("spread_cell_c").is_finite()).then(pl.col("spread_cell_c")).otherwise(None)
        .alias("_spc_fin"))
    # ---- stratum spreads
    by = ["gcm", "scen", "window", "quantity"]
    st = strat_stats(allt, by, "spread_cell")
    allt = allt.join(st, on=by + ["stratum"], how="left")
    stc = strat_stats(allt.drop(["s_med", "s_q90", "s_n", "stratum_own"]), by, "_spc_fin").select(
        by + ["stratum", pl.col("s_med").alias("s_med_c"), pl.col("s_q90").alias("s_q90_c")])
    allt = allt.join(stc, on=by + ["stratum"], how="left")
    # where the other seed is invalid for a whole (gcm, scen, window) (MPI ssp370 w3071 with truth seed 1), borrow
    # the stratum spread of the same gcm's OTHER scenarios for that window
    miss = allt.group_by(by).agg(pl.col("R").is_not_null().sum().alias("nR")).filter(pl.col("nR") == 0)
    allt = allt.with_columns(pl.lit("own").alias("tol_source"))
    if miss.height:
        bor = (
            allt.join(miss.select(["gcm", "window", "quantity"]).unique(), on=["gcm", "window", "quantity"])
            .filter(pl.col("R").is_not_null())
            .group_by(["gcm", "window", "quantity", "stratum"])
            .agg(pl.col("spread_cell").median().alias("b_med"), pl.col("spread_cell").quantile(0.9).alias("b_q90"),
                 pl.col("_spc_fin").drop_nulls().median().alias("b_med_c"),
                 pl.col("_spc_fin").drop_nulls().quantile(0.9).alias("b_q90_c"),
                 pl.col("scen").unique().sort().str.join("+").alias("b_src"))
        )
        allt = allt.join(miss.select(by).with_columns(pl.lit(True).alias("_m")), on=by, how="left")
        allt = allt.join(bor, on=["gcm", "window", "quantity", "stratum"], how="left").with_columns(
            pl.when(pl.col("_m")).then(pl.col("b_med")).otherwise(pl.col("s_med")).alias("s_med"),
            pl.when(pl.col("_m")).then(pl.col("b_q90")).otherwise(pl.col("s_q90")).alias("s_q90"),
            pl.when(pl.col("_m")).then(pl.col("b_med_c")).otherwise(pl.col("s_med_c")).alias("s_med_c"),
            pl.when(pl.col("_m")).then(pl.col("b_q90_c")).otherwise(pl.col("s_q90_c")).alias("s_q90_c"),
            pl.when(pl.col("_m")).then(pl.lit("borrowed:") + pl.col("b_src")).otherwise(pl.col("tol_source"))
            .alias("tol_source"),
        ).drop(["_m", "b_med", "b_q90", "b_med_c", "b_q90_c", "b_src"])
    # ---- allowed absolute error
    isf = pl.col("quantity").str.starts_with("share_")
    isr = pl.col("target_kind").is_in(["response", "contrast"])
    absC = pl.col("C").abs()

    def allowed(sp: pl.Expr) -> pl.Expr:
        return (
            pl.when(isf)
            .then(pl.max_horizontal(REL_FLOOR * absC, sp, pl.lit(SHARE_FLOOR)))
            .when(isr)
            .then(pl.max_horizontal(REL_FLOOR * absC, sp * pl.col("scale")))
            .otherwise(absC * pl.max_horizontal(pl.lit(REL_FLOOR), sp))
        )

    dCR = (pl.col("C") - pl.col("R")).abs()
    allt = allt.with_columns(
        allowed(pl.col("s_med")).alias("allowed"),
        allowed(pl.col("s_q90")).alias("allowed_q90"),
        pl.when(pl.col("spread_cell").is_null()).then(None).otherwise(allowed(pl.col("spread_cell")))
        .alias("allowed_cell"),
        pl.when(isr & pl.col("R").is_not_null())
        .then(((pl.col("C") + pl.col("R")) / 2).abs() / (pl.col("C") - pl.col("R")).abs())
        .otherwise(None)
        .alias("sn_cell"),
        # SH14 amendment 1 (appended columns)
        pl.when(pl.col("R").is_null()).then(None)
        .when(isf).then(pl.max_horizontal(REL_FLOOR * absC, dCR, pl.lit(SHARE_FLOOR)))
        .otherwise(pl.max_horizontal(REL_FLOOR * absC, dCR)).alias("allowed_cell_abs"),
        allowed(pl.col("s_med_c")).alias("allowed_c"),
        allowed(pl.col("s_q90_c")).alias("allowed_q90_c"),
    ).drop("_spc_fin")
    # trait quantiles with too few stems -> C null -> not scored
    allt = allt.filter(pl.col("C").is_not_null())
    k2 = ["gcm", "scen", "window", "Cell", "quantity"]
    assert allt.select(k2).n_unique() == allt.height, "duplicate keys in tolerance table"
    lead = ["gcm", "scen", "window", "Cell", "quantity", "target_kind", "C", "R", "scale", "dens", "stratum",
            "spread_cell", "s_med", "s_q90", "s_n", "stratum_own", "tol_source", "allowed", "allowed_q90",
            "allowed_cell", "sn_cell"]
    tail = ["spread_cell_c", "s_med_c", "s_q90_c", "allowed_cell_abs", "allowed_c", "allowed_q90_c",
            "dev_unbr_lo", "dev_unbr_hi"]
    return allt.select(lead + tail).sort(k2)


def build_aggregate(tol: pl.DataFrame) -> pl.DataFrame:
    """Area-weighted Germany-wide (and latitude-tercile) aggregate of C and R per target; S/N for responses."""
    st = pl.read_parquet(f"{XDE}/climate/cell_static.parquet").select(["Cell", "lat", "area_km2_approx"])
    t1, t2 = np.quantile(st["lat"].to_numpy(), [1 / 3, 2 / 3])
    st = st.with_columns(
        pl.when(pl.col("lat") < t1).then(pl.lit("south")).when(pl.col("lat") < t2).then(pl.lit("central"))
        .otherwise(pl.lit("north")).alias("region"),
        pl.col("Cell").cast(pl.Int32),
    )
    d = tol.select(["gcm", "scen", "window", "Cell", "quantity", "target_kind", "C", "R"]).join(st, on="Cell")
    out = []
    for reg in [REGION_ALL, "south", "central", "north"]:
        x = d if reg == REGION_ALL else d.filter(pl.col("region") == reg)
        a = x.group_by(["gcm", "scen", "window", "quantity", "target_kind"]).agg(
            ((pl.col("C") * pl.col("area_km2_approx")).sum() / pl.col("area_km2_approx").sum()).alias("aggC"),
            pl.when(pl.col("R").is_null().any()).then(None).otherwise(
                (pl.col("R") * pl.col("area_km2_approx")).sum() / pl.col("area_km2_approx").sum()).alias("aggR"),
            pl.len().alias("n_cells"),
        )
        out.append(a.with_columns(pl.lit(reg).alias("region")))
    a = pl.concat(out).with_columns(
        (pl.col("aggC") - pl.col("aggR")).abs().alias("noise"),
    ).with_columns(
        (((pl.col("aggC") + pl.col("aggR")) / 2).abs() / pl.col("noise")).alias("sn"),
        pl.max_horizontal(REL_FLOOR * pl.col("aggC").abs(), pl.col("noise")).alias("allowed"),
    )
    return a.sort(["gcm", "scen", "window", "quantity", "region"]), (float(t1), float(t2))


DEFINITION = """# Germany emulator scoring reference -- definition (line X, 2026-10-01)

Built by `scripts/explore_de_reference.py` from the converted ind parquet. Scored by `scripts/explore_de_score.py`.

## Population and statistics
* Living trees: `Type <= 6`, `isdead == 0`, `Height >= 5 m` (the C writer emits only stems > 5 m; the height cut is a
  no-op on the C output -- measured 0 rows removed in every member -- and makes an emulator roster comparable).
* Per (gcm, scen, seed, window, Cell), pooled over the window's 30 years (stem-year weighted):
  `n_per_patch` = living stem-years / (years x 250 configured patches); `agb_stand` = sum agb / (years x 250);
  `share_t` = stem-year share of PFT t; `<v>_<q>` = q05/q25/q50/q75/q95 of SLA, Wooddens, D95max, minwscal,
  Longevity, Height, agb (polars linear-interpolated quantile). Quantiles are null (not scored) below 30 stem-years.
* Windows: h1985 = 1985-2014 (Historical), w2015 = 2015-2044, w2071 = 2071-2100, w3071 = 3071-3100 (recycled
  2071-2100 climate: equilibrium test only). Responses: r2071 = w2071 - h1985, r2015 = w2015 - h1985, per seed,
  per scenario (each seed's 1985-2100 is one continuous trajectory).

## Tolerance (allowed absolute |E - C|), C = seed 1, R = seed 2
* level, relative quantity: `|C| * max(0.10, S)`, S = median over cells of the same density stratum of
  `|C - R| / mean(C, R)` (ADR 0111's estimator of "the original's own two-run spread").
* level, PFT share: `max(0.10*C, S_abs, 0.005)`, S_abs = stratum median of `|C - R|`.
* response, relative quantity: `max(0.10*|dC|, S_r * |mean historical level|)`,
  S_r = stratum median of `|dC - dR| / |mean historical level|`.
* response, PFT share: `max(0.10*|dC|, stratum median |dC - dR|, 0.005)`.
* Density strata (stems per patch, 2-seed mean, ADR 0111 edges): <2, 2-5, 5-10, 10-20, >20; a stratum with < 30
  cells uses the pooled median. A response's stratum is the cell's historical stratum.
* Secondary: `allowed_cell` (the literal per-cell spread in place of the stratum median) and `allowed_q90` (stratum
  90th percentile).
* MPI-ESM1-2-HR ssp370 seed 2 w3071 is truncated at source (3071-3072 + half of 3073): it is NOT used. Its
  w3071 tolerance is borrowed from the same GCM's ssp126+ssp245 w3071 stratum spreads (`tol_source`).

* Calibrated (`allowed_cal`, an addition, NOT in ADR 0106/0111): `max(floor, k_q * S * base)` with one multiplier
  k_q per (quantity, level|response), all at the same quantile p of seed 2's own deviation ratio, p chosen so that
  seed 2 passes ALL panel106 quantities in 95 % of (target, cell) pairs. In-sample for the other-seed null.
* All pass tests are `|E - C| <= allowed * (1 + 1e-9)` (the epsilon removes a float-rounding failure).

## Block scale (reference/block/, added 2026-10-01)
* ~1-degree boxes of cells (boxes with < 50 cells merged into the nearest larger box). Block value = area-weighted
  mean of the per-cell quantity over the cells where seed 1 (and seed 2, when valid) is non-null; the emulator is
  averaged over the SAME cells (a missing cell makes the block missing). Tolerance, strata, calibration: the
  identical construction with blocks in place of cells. reference/block_dev/ = the same built from the dev cells
  (Cell % 10 == 0) only, used when a dev-subset arm is scored with --scope covered.
* Why: the per-cell response has per-cell S/N of order 1, so a per-cell response test that is fair to the original
  cannot distinguish a spatially uniform response from the true pattern. Blocks average ~150 independent cells.

## Panels
* panel106 = n_per_patch + q05..q95 of SLA, Wooddens, D95max, minwscal, Height, agb (31 quantities, ADR 0106 §2)
* extended = panel106 + Longevity q05..q95 + agb_stand + share_0..share_6 (44 quantities)

## SH14 amendments (round 2, 2026-10-01; round-1 columns unchanged, everything below is ADDED)
Demanded by the round-1 completeness critic; pre-edit scripts and reference backed up at
/p/tmp/jamirp/X_de/shared/scorer/backup_pre_SH14/.
1. Symmetric tolerances. The round-1 literal per-cell level tolerance `|C| * max(0.1, |C-R|/mean(C,R))` is
   smaller than `|C-R|` whenever R > C, so the original's own second run could fail it. Added:
   * `allowed_cell_abs` = `max(0.10*|C|, |C-R|)` (shares: also >= 0.005; responses/contrasts: `max(0.1|dC|, |dC-dR|)`,
     identical to allowed_cell there). The other seed passes it at 1.0 by construction.
   * `allowed_c` / `allowed_q90_c` = the stratum median / q90 versions with the level spread `|C-R|/|C|`
     (`spread_cell_c`, non-finite values excluded from the stratum statistics); shares/responses/contrasts as before.
   * `allowed_cal_c` = the calibration (same construction) on `s_med_c`.
2. Truth-seed switch. `tolerance_t2.parquet`, `aggregate_t2.parquet`, `block*/{mask,levels,tolerance}_t2.parquet`:
   the same construction with C = seed 2 and R = seed 1 (for a hold-out whose history is shared with seed-1
   training data, e.g. MPI ssp245, which continues seed 1's Historical). MPI ssp370 w3071 has no seed-2 truth
   (truncated) and is therefore not a target under truth seed 2.
3. Between-scenario CONTRASTS (target_kind "contrast"): `c2071` = X(scen, 2071-2100) - X(ssp126, 2071-2100),
   `c2015` likewise for 2015-2044, scen in {ssp370, ssp245}, same gcm, same seed (C from the truth seed, R from the
   other). scale = |two-seed mean of the ssp126 leg|, stratum = the cell's historical stratum; tolerance columns
   built exactly as for responses (all variants, own calibration). Both legs share the CO2 file and the segment's
   humidity configuration, so the contrast carries neither the 1985->2020 CO2 rise nor the 2071 humidity switch:
   c2071 is the PRIMARY response statistic. r2071 stays, labelled as containing both. ssp245 contrasts also
   contain a binary change (ssp245 ran the Feb-2026 build): reported, never used for the learned-response test.
4. Frozen rosters (reference/frozen/): window statistics of each seed's living 1985 and 2014 Historical roster
   repeated over a 30-year window (what an engine FROZEN run writes), scored by the scorer as nulls.

## SH14 repair (round 2, after the adversarial verifier; still additive for every round-1 column)
5. Contrast calibration is fitted on ssp370 rows only (CONTRAST_FIT_SCENS) and applied to all contrast rows
   (ssp245 = scenario + binary). This changes allowed_cal / allowed_cal_c on CONTRAST rows only (SH14-new rows).
6. Calibration overfit. The round-1 calibration fits one multiplier per quantity (31 free parameters per target
   kind) on the very replica it is then judged by; at block scale (52 blocks) the replica's 0.95 does not transfer
   across GCMs (verifier: fit on one GCM, apply to the other -> block responses 0.70/0.79). Added columns:
   `allowed_cal1` (ONE multiplier per target kind, = the 95 % quantile over units of the unit's largest panel106
   ratio), `allowed_cal_xg` (the round-1 per-quantity calibration fitted on the OTHER GCM only) and
   `allowed_cal1_xg` (one multiplier per kind, fitted on the other GCM). The replica's pass under a *_xg column is
   an out-of-sample ceiling. calibration_extra*.csv lists every k with its fitted-set and held-out conj.
7. Unbranched scenario legs. In the truth both legs of one seed restart from ONE 2014 state incl. its
   random-number state, so the replica's contrast error is the noise of a BRANCHED pair. Contrast rows carry
   `dev_unbr_hi` = |V2 - V1| (replica scen leg with the truth's own ssp126 leg; variance 2 s^2, optimistic) and
   `dev_unbr_lo` = |(V1 - V2) + (B1 - B2)| (the two cross-seed contrasts against each other; variance
   4 s^2 (1 + rho), pessimistic). An arm whose legs are NOT branched from one state with shared random numbers has
   variance 2 s^2 (2 - rho) and is bracketed by the two; the scorer reports the matching ceilings.
"""

CLEAN_DEFINITION = """
## CLEAN REFERENCE SET (reference/clean/, the DEFAULT since the owner decision of 2026-10-01)
Owner, verbatim: "double check if the runs after 2070 were really corrupted with the wrong settings. if its true,
lets only use the earlier data that is correct, for now." Verified by the orchestrator three ways: every
2071-2100 and 3071-3100 segment's config lacks `"relative_humidity": true` (present in all 1985-2070 configs;
LPJmL defaults it false, fscanconfig.c:255), its log lists the humidity input as `humid` (specific humidity)
instead of `rhumid`, and the share of living trees with mort_water > 0 is exactly 0 in 2071 and 2100 in all 24 ssp
runs (0.02-9.4 % in 2015-2044). So:
* Windows: h1985 (1985-2014) and w2015 (2015-2044) only. Targets: levels h1985, w2015; response r2015 = w2015 -
  h1985; contrasts c2015 = X(scen, 2015-2044) - X(ssp126, 2015-2044), scen in {ssp370, ssp245}.
* EXCLUDED everywhere in this set: w2071, w3071, r2071, c2071 (no rows exist; the scorer drops any submitted
  2071-2100 / 3071-3100 years and flags them in coverage.json).
* Every tolerance column is rebuilt from these rows only; in particular every calibration multiplier (allowed_cal,
  _c, cal1, cal_xg, cal1_xg) is FITTED on 1985-2044 targets only (the full set's multipliers pooled the corrupted
  windows). Contrast multipliers: fitted on ssp370 c2015 rows only.
* PRIMARY response statistic: c2015 for ssp370 (ssp370 - ssp126 at fixed gcm and seed; both legs share CO2 and the
  configuration). ssp245 contrasts and ssp245 levels/responses also contain the Feb-2026 binary change. r2015 is kept
  beside it (contains the 1985->2020 CO2 rise the emulator does not see).
* Whole criterion: h1985 + w2015 + the response target (r2015 or c2015), every panel quantity.
* This limits the warming that can be tested to the early century: 2015-2044 warming is smaller than 2071-2100,
  so the response signal-to-noise is lower (measured per quantity in shared/scorer/sh14_clean_snr.csv).
"""


def assemble() -> int:
    """levels_long + the tolerance tables for truth seed 1 (tolerance.parquet, the round-1 file, extended) and truth
    seed 2 (tolerance_t2.parquet, SH14), each CALIBRATED before it is written (atomic replace), + aggregates."""
    t0 = time.time()
    os.makedirs(REFOUT, exist_ok=True)
    lv = load_levels()
    log(f"levels ({REFSET} reference set, windows {sorted(lv['window'].unique().to_list())}): {lv.height} rows "
        f"-> {REFOUT}")
    if REFSET == "clean":
        assert not set(lv["window"].unique().to_list()) & set(EXCLUDED_WINDOWS), "excluded window leaked"
    write_atomic(lv, f"{REFOUT}/levels_long.parquet")
    for ts in (1, 2):
        sfx = "" if ts == 1 else "_t2"
        tol = build_tolerance(lv, ts)
        log(f"tolerance{sfx}: {tol.height} rows")
        tol, cals = calibrate_all(tol)
        for (scol, _), cal in zip(CAL_VARIANTS, cals[:2], strict=True):
            cal.sort(["target_kind", "quantity"]).write_csv(
                f"{REFOUT}/calibration{'_c' if scol.endswith('_c') else ''}{sfx}.csv")
        cals[2].write_csv(f"{REFOUT}/calibration_extra{sfx}.csv")
        write_atomic(tol, f"{REFOUT}/tolerance{sfx}.parquet")
        agg, terc = build_aggregate(tol)
        write_atomic(agg, f"{REFOUT}/aggregate{sfx}.parquet")
        agg.write_csv(f"{REFOUT}/aggregate{sfx}.csv")
        # summary of the tolerances themselves
        summ = (
            tol.group_by(["gcm", "scen", "window", "quantity"])
            .agg(
                pl.len().alias("n_cells"),
                pl.col("R").is_not_null().sum().alias("n_with_seed2"),
                pl.col("spread_cell").median().alias("spread_cell_med"),
                (pl.col("allowed") / pl.col("C").abs()).median().alias("allowed_rel_med"),
                (pl.col("allowed") > REL_FLOOR * pl.col("C").abs() * 1.0000001).mean().alias("frac_spread_binds"),
                pl.col("sn_cell").median().alias("sn_cell_med"),
                (pl.col("sn_cell") >= 3).mean().alias("frac_sn_ge3"),
                pl.col("tol_source").first(),
                pl.col("spread_cell_c").median().alias("spread_cell_c_med"),
                (pl.col("allowed_c") / pl.col("C").abs()).median().alias("allowed_c_rel_med"),
                (pl.col("allowed_cell_abs") / pl.col("C").abs()).median().alias("allowed_cell_abs_rel_med"),
            )
            .sort(["gcm", "scen", "window", "quantity"])
        )
        summ.write_csv(f"{REFOUT}/tolerance_summary{sfx}.csv")
        strata = tol.filter(pl.col("quantity") == "n_per_patch").group_by(
            ["gcm", "scen", "window", "stratum"]).len()
        gate = {
            "truth_seed": ts,
            "reference_set": REFSET,
            "windows": sorted(lv["window"].unique().to_list()),
            "targets": sorted(tol["window"].unique().to_list()),
            "excluded_targets": [] if REFSET == "full" else list(EXCLUDED_TARGETS),
            "exclusion_reason": None if REFSET == "full" else EXCLUSION_REASON,
            "levels_rows": lv.height,
            "tolerance_rows": tol.height,
            "tolerance_rows_by_kind": {r["target_kind"]: r["len"] for r in tol.group_by("target_kind").len()
                                       .iter_rows(named=True)},
            "tolerance_keys_unique": True,
            "members": lv.select(["gcm", "scen", "seed", "window"]).unique().height,
            "invalid_members": lv.filter(~pl.col("valid")).select(["gcm", "scen", "seed", "window"]).unique()
            .to_dicts(),
            "cells_per_target_min": int(tol.group_by(["gcm", "scen", "window", "quantity"]).len()["len"].min()),
            "cells_per_target_max": int(tol.group_by(["gcm", "scen", "window", "quantity"]).len()["len"].max()),
            "strata_counts": strata.sort(["gcm", "scen", "window", "stratum"]).to_dicts(),
            "lat_tercile_edges": terc,
            "calibration_p": pl.concat(cals[:2]).select(["spread_variant", "target_kind", "p", "conj_panel106"])
            .unique().sort(["spread_variant", "target_kind"]).to_dicts(),
            "calibration_extra": cals[2].to_dicts(),
            "contrast_fit_scens": CONTRAST_FIT_SCENS,
            "replica_passes_allowed_cell_abs": float(
                tol.filter(pl.col("R").is_not_null()).select(
                    ((pl.col("R") - pl.col("C")).abs() <= pl.col("allowed_cell_abs") * (1 + 1e-9)).mean()).item()),
            "wall_s": round(time.time() - t0, 1),
        }
        json.dump(gate, open(f"{REFOUT}/_gates{sfx}.json", "w"), indent=1, default=str)
        with pl.Config(tbl_rows=200, tbl_cols=20, fmt_str_lengths=40):
            print(summ.filter(pl.col("quantity").is_in(["n_per_patch", "agb_stand", "SLA_q50", "Wooddens_q50",
                                                        "D95max_q50", "minwscal_q50", "Height_q50", "share_3"])
                              & (pl.col("gcm") == "MPI-ESM1-2-HR")))
        del tol
    open(f"{REFOUT}/_DEFINITION.md", "w").write(DEFINITION + (CLEAN_DEFINITION if REFSET == "clean" else ""))
    log(f"assemble done in {time.time() - t0:.0f} s")
    return 0


# ---------------------------------------------------------------------------------------------------------
# calibrate: a tolerance under which a SECOND RUN of the original passes the whole panel in CAL_TARGET of cells
# ---------------------------------------------------------------------------------------------------------
CAL_TARGET = 0.95


def _floor_base():
    isf = pl.col("quantity").str.starts_with("share_")
    isr = pl.col("target_kind").is_in(["response", "contrast"])
    absC = pl.col("C").abs()
    floor = pl.when(isf).then(pl.max_horizontal(REL_FLOOR * absC, pl.lit(SHARE_FLOOR))).otherwise(REL_FLOOR * absC)
    base = pl.when(isf).then(pl.lit(1.0)).when(isr).then(pl.col("scale")).otherwise(absC)
    return floor, base


CAL_VARIANTS = [("s_med", "allowed_cal"), ("s_med_c", "allowed_cal_c")]  # (stratum spread column, output column)
TARGET_KINDS = ["level", "response", "contrast"]


def calibrate(truth_seed: int = 1) -> int:
    """Per (quantity, target_kind) multiplier k_q on the stratum-median spread, all k_q at the same per-quantity
    quantile p of the other-seed-vs-truth ratio, with p found by bisection so that the other seed passes ALL
    panel106 quantities in CAL_TARGET of (target, cell) pairs. In-sample by construction for the other-seed null
    (stated). Adds allowed_cal (round-1 spread) and allowed_cal_c (SH14 symmetric spread) to the tolerance file;
    writes calibration{,_c}{,_t2}.csv. (assemble already does this; this stage re-calibrates an existing file.)"""
    t0 = time.time()
    sfx = "" if truth_seed == 1 else "_t2"
    tol = pl.read_parquet(f"{REFOUT}/tolerance{sfx}.parquet")
    tol, cals = calibrate_all(tol)
    for (scol, _), cal in zip(CAL_VARIANTS, cals[:2], strict=True):
        vtag = "_c" if scol.endswith("_c") else ""
        cal.sort(["target_kind", "quantity"]).write_csv(f"{REFOUT}/calibration{vtag}{sfx}.csv")
    cals[2].write_csv(f"{REFOUT}/calibration_extra{sfx}.csv")
    write_atomic(tol, f"{REFOUT}/tolerance{sfx}.parquet")
    log(f"calibrate{sfx} done ({time.time() - t0:.0f} s)")
    with pl.Config(tbl_rows=100):
        print(cals[0].sort(["target_kind", "quantity"]))
    return 0


def calibrate_all(tol: pl.DataFrame) -> tuple[pl.DataFrame, list[pl.DataFrame]]:
    """Returns (tol, [cal_s_med, cal_s_med_c, extra_summary]); the extra columns come from calibrate_extra."""
    cals = []
    for scol, ocol in CAL_VARIANTS:
        tol, cal = calibrate_table(tol, scol, ocol)
        cals.append(cal.with_columns(pl.lit(scol).alias("spread_variant")))
    tol, extra = calibrate_extra(tol, "s_med")
    cals.append(extra)
    return tol, cals


def write_atomic(df: pl.DataFrame, path: str) -> None:
    """Write via a temp file + rename, so a concurrent scorer never reads a half-written / uncalibrated table."""
    tmp = f"{path}.tmp{os.getpid()}"
    df.write_parquet(tmp)
    os.replace(tmp, path)


CONTRAST_FIT_SCENS = ["ssp370"]  # SH14 repair: ssp245 contrasts mix the scenario with the Feb-2026 binary change,
#                                  so the contrast multiplier is fitted on ssp370 rows only (applied to both)


def _ratio_frame(tol: pl.DataFrame, s_col: str) -> pl.DataFrame:
    """Rows with a replica: dev = |R - C|, r = dev / (spread * base), r = 0 where the 10 % floor already covers dev."""
    floor, base = _floor_base()
    x = tol.filter(pl.col("R").is_not_null()).select(
        ["gcm", "scen", "window", "Cell", "quantity", "target_kind", "C", "R", pl.col(s_col).alias("s_x"), "scale"]
    ).with_columns(floor.alias("floor"), base.alias("base"), (pl.col("R") - pl.col("C")).abs().alias("dev"))
    return x.with_columns(
        pl.when(pl.col("dev") <= pl.col("floor")).then(0.0)
        .when(pl.col("s_x") * pl.col("base") > 0).then(pl.col("dev") / (pl.col("s_x") * pl.col("base")))
        .otherwise(float("inf")).alias("r")
    )


def _fit_scope(x: pl.DataFrame, kind: str) -> pl.DataFrame:
    y = x.filter(pl.col("target_kind") == kind)
    if kind == "contrast":
        y = y.filter(pl.col("scen").is_in(CONTRAST_FIT_SCENS))
    return y


def _conj_units(sub: pl.DataFrame, k: pl.DataFrame | float) -> float:
    """Fraction of (gcm, scen, window, Cell) units whose panel106 rows all have r <= k."""
    if isinstance(k, pl.DataFrame):
        y = sub.join(k, on="quantity", how="left").with_columns((pl.col("r") <= pl.col("k")).fill_null(False)
                                                                 .alias("ok"))
    else:
        y = sub.with_columns((pl.col("r") <= k).alias("ok"))
    return float(y.group_by(["gcm", "scen", "window", "Cell"]).agg(pl.col("ok").all())["ok"].mean())


def _fit_perq(x: pl.DataFrame, kind: str) -> tuple[pl.DataFrame, float, float] | None:
    """Round-1 calibration: per-quantity k = the p-quantile (higher) of r, one p for all quantities, bisected so the
    replica passes ALL panel106 quantities in CAL_TARGET of units. Returns (k per quantity, p, conj)."""
    scope = _fit_scope(x, kind)
    sub = scope.filter(pl.col("quantity").is_in(PANEL106))
    if not sub.height:
        return None

    def kq(p, sub=sub):
        return sub.group_by("quantity").agg(pl.col("r").quantile(p, interpolation="higher").alias("k"))

    lo, hi = 0.5, 1.0
    for _ in range(22):
        mid = (lo + hi) / 2
        if _conj_units(sub, kq(mid)) >= CAL_TARGET:
            hi = mid
        else:
            lo = mid
    p = hi
    c = _conj_units(sub, kq(p))
    k = scope.group_by("quantity").agg(
        pl.col("r").quantile(p, interpolation="higher").alias("k"),
        pl.col("s_x").median().alias("s_med_median"),
    )
    return k, p, c


def _fit_single(x: pl.DataFrame, kind: str) -> tuple[float | None, float] | None:
    """SH14 repair: ONE multiplier per target kind (1 free parameter instead of one per quantity, against the
    block-scale in-sample overfit): k = the CAL_TARGET quantile (higher) over units of the unit's largest panel106 r,
    i.e. exactly the smallest k under which CAL_TARGET of units pass the whole panel. Returns (k, conj)."""
    sub = _fit_scope(x, kind).filter(pl.col("quantity").is_in(PANEL106))
    if not sub.height:
        return None
    u = sub.group_by(["gcm", "scen", "window", "Cell"]).agg(pl.col("r").max().alias("m"))
    k = float(u["m"].quantile(CAL_TARGET, interpolation="higher"))
    c = float((u["m"] <= k).mean())
    return (None if not np.isfinite(k) else k), c


def calibrate_table(tol: pl.DataFrame, s_col: str = "s_med",
                    out_col: str = "allowed_cal") -> tuple[pl.DataFrame, pl.DataFrame]:
    """The calibration itself (see calibrate()); works on a cell-scale or block-scale tolerance table.
    s_col/out_col select the spread variant (round-1: s_med -> allowed_cal; SH14: s_med_c -> allowed_cal_c).
    Each target kind (level / response / contrast) is calibrated on its own rows, so adding the contrast kind
    leaves the level and response multipliers of round 1 unchanged. SH14 repair: the contrast kind is fitted on
    CONTRAST_FIT_SCENS (ssp370) rows only and applied to every contrast row. In-sample for the replica by
    construction -- read the cross-GCM columns of calibrate_extra for an out-of-sample ceiling."""
    if out_col in tol.columns:
        tol = tol.drop(out_col)
    floor, base = _floor_base()
    x = _ratio_frame(tol, s_col)
    rows = []
    for kind in TARGET_KINDS:
        f = _fit_perq(x, kind)
        if f is None:
            continue
        k, p, c = f
        k = k.with_columns(pl.lit(kind).alias("target_kind"), pl.lit(p).alias("p"), pl.lit(c).alias("conj_panel106"))
        rows.append(k)
        log(f"calibrate [{s_col}] {kind}: p = {p:.5f}, other-seed panel106 conjunctive pass = {c:.4f}")
    cal = pl.concat(rows).with_columns(
        pl.when(pl.col("k").is_infinite()).then(None).otherwise(pl.col("k")).alias("k"))
    tol = tol.join(cal.select(["quantity", "target_kind", "k"]), on=["quantity", "target_kind"], how="left")
    tol = tol.with_columns(
        pl.max_horizontal(floor, pl.col("k").fill_null(0.0) * pl.col(s_col) * base).alias(out_col)
    ).drop("k")
    return tol, cal


EXTRA_CAL_COLS = ["allowed_cal1", "allowed_cal_xg", "allowed_cal1_xg"]


def calibrate_extra(tol: pl.DataFrame, s_col: str = "s_med") -> tuple[pl.DataFrame, pl.DataFrame]:
    """SH14 repair (verifier: the block-scale calibration overfits in-sample). Three more tolerance columns on the
    round-1 spread:
      allowed_cal1     ONE multiplier per target kind, fitted on all GCMs (in-sample for the replica)
      allowed_cal_xg   the round-1 per-quantity calibration fitted on the OTHER GCM(s) only (cross-fit)
      allowed_cal1_xg  one multiplier per target kind fitted on the other GCM(s) only (cross-fit)
    The replica's pass fraction under a *_xg column is an OUT-OF-SAMPLE ceiling: its k never saw that GCM.
    Returns (tol, summary) with per (variant, target kind, applied gcm) the k, the fitted-set conj and the
    applied-set (held-out) replica conj on panel106 (contrasts: CONTRAST_FIT_SCENS rows)."""
    tol = tol.drop([c for c in EXTRA_CAL_COLS if c in tol.columns])
    floor, base = _floor_base()
    x = _ratio_frame(tol, s_col)
    gcms = sorted(tol["gcm"].unique().to_list())
    kparts = {c: [] for c in EXTRA_CAL_COLS}
    summ = []
    for kind in TARGET_KINDS:
        f1 = _fit_single(x, kind)
        if f1 is None:
            continue
        kparts["allowed_cal1"].append(pl.DataFrame({"gcm": gcms, "target_kind": [kind] * len(gcms),
                                                    "k": [f1[0]] * len(gcms)}, schema_overrides={"k": pl.Float64}))
        summ.append({"variant": "allowed_cal1", "target_kind": kind, "applied_gcm": "all", "k": f1[0],
                     "conj_fit": f1[1], "conj_applied": f1[1]})
        for g in gcms:
            xf = x.filter(pl.col("gcm") != g)
            xa = _fit_scope(x.filter(pl.col("gcm") == g), kind).filter(pl.col("quantity").is_in(PANEL106))
            if not xf.height or _fit_scope(xf, kind).height == 0:
                continue
            s1 = _fit_single(xf, kind)
            if s1 is not None:
                kparts["allowed_cal1_xg"].append(pl.DataFrame(
                    {"gcm": [g], "target_kind": [kind], "k": [s1[0]]}, schema_overrides={"k": pl.Float64}))
                summ.append({"variant": "allowed_cal1_xg", "target_kind": kind, "applied_gcm": g, "k": s1[0],
                             "conj_fit": s1[1],
                             "conj_applied": _conj_units(xa, s1[0] if s1[0] is not None else 0.0) if xa.height
                             else None})
            pq = _fit_perq(xf, kind)
            if pq is not None:
                kq, p, c = pq
                kq = kq.with_columns(pl.when(pl.col("k").is_infinite()).then(None).otherwise(pl.col("k")).alias("k"))
                kparts["allowed_cal_xg"].append(kq.select(["quantity", "k"]).with_columns(
                    pl.lit(g).alias("gcm"), pl.lit(kind).alias("target_kind")))
                summ.append({"variant": "allowed_cal_xg", "target_kind": kind, "applied_gcm": g, "k": None,
                             "p": p, "conj_fit": c,
                             "conj_applied": _conj_units(xa, kq.select(["quantity", pl.col("k").fill_null(0.0)]))
                             if xa.height else None})
    for col, parts in kparts.items():
        if not parts:
            tol = tol.with_columns(pl.lit(None, dtype=pl.Float64).alias(col))
            continue
        kk = pl.concat(parts, how="diagonal_relaxed")
        on = ["gcm", "target_kind"] + (["quantity"] if "quantity" in kk.columns else [])
        tol = tol.join(kk.select(on + ["k"]), on=on, how="left")
        # k null (an infinite quantile, as in round 1) -> the floor alone. A single-GCM domain has no *_xg fit at
        # all and gets an all-null column above (= that tolerance is not available).
        tol = tol.with_columns(
            pl.max_horizontal(floor, pl.col("k").fill_null(0.0) * pl.col(s_col) * base).alias(col)).drop("k")
    sm = pl.DataFrame(summ, infer_schema_length=None)
    for r in sm.iter_rows(named=True):
        log(f"calibrate_extra {r['variant']} {r['target_kind']} applied to {r['applied_gcm']}: k={r['k']} "
            f"conj fit {r['conj_fit']:.4f} -> applied {r['conj_applied']}")
    return tol, sm


# ---------------------------------------------------------------------------------------------------------
# BLOCK scale: ~1-degree blocks of cells. Added 2026-10-01 because the per-cell RESPONSE has a per-cell
# signal-to-noise of order 1 (ADR 0111 §5), so a per-cell response test that is fair to the original model
# cannot tell a spatially uniform response from the true pattern (measured: the Germany-mean response passes
# the calibrated per-cell response test in ~92 % of cells). Averaging ~150 independent cells per block raises
# the S/N by ~sqrt(150) and gives the response test spatial power. Same tolerance construction as the cells.
# ---------------------------------------------------------------------------------------------------------
BLOCK_DEG = 1.0
BLOCK_MIN_CELLS = 50  # a 1-degree box with fewer reference cells is merged into the nearest larger block


def block_map(cells: list[int] | None = None) -> pl.DataFrame:
    """Cell -> block (Int32 id) for the reference cells; boxes of BLOCK_DEG, small edge boxes merged into the
    nearest large box (distance on the sphere-ish: lon scaled by cos(lat))."""
    st = pl.read_parquet(f"{XDE}/climate/cell_static.parquet").select(
        [pl.col("Cell").cast(pl.Int32), "lat", "lon", "area_km2_approx"])
    # the block GEOMETRY is always built from all reference cells; a subset (dev cells) is then restricted to it
    allc = pl.read_parquet(f"{OUT}/stats/{gates()['member'][0]}.parquet")["Cell"].to_list()
    if cells is None:
        cells = allc
    st = st.filter(pl.col("Cell").is_in(allc)).with_columns(
        (pl.col("lat") / BLOCK_DEG).floor().cast(pl.Int32).alias("by"),
        (pl.col("lon") / BLOCK_DEG).floor().cast(pl.Int32).alias("bx"))
    box = st.group_by(["by", "bx"]).agg(pl.len().alias("n"), pl.col("lat").mean().alias("clat"),
                                        pl.col("lon").mean().alias("clon")).sort(["by", "bx"])
    big = box.filter(pl.col("n") >= BLOCK_MIN_CELLS).with_row_index("block").with_columns(
        pl.col("block").cast(pl.Int32))
    cl, co, bid = big["clat"].to_numpy(), big["clon"].to_numpy(), big["block"].to_numpy()
    j = st.join(big.select(["by", "bx", "block"]), on=["by", "bx"], how="left")
    lat, lon, blk = j["lat"].to_numpy(), j["lon"].to_numpy(), j["block"].to_numpy(allow_copy=True)
    blk = np.where(np.isnan(blk.astype(float)), -1, blk).astype(np.int64)
    for i in np.where(blk < 0)[0]:
        dd = (cl - lat[i]) ** 2 + ((co - lon[i]) * np.cos(np.radians(lat[i]))) ** 2
        blk[i] = int(bid[int(np.argmin(dd))])
    out = j.select(["Cell", "area_km2_approx"]).with_columns(pl.Series("block", blk, dtype=pl.Int32))
    assert out["Cell"].n_unique() == out.height
    out = out.filter(pl.col("Cell").is_in(cells))
    return out


def block_mask(lv: pl.DataFrame, bm: pl.DataFrame, truth_seed: int = 1) -> pl.DataFrame:
    """Which cells enter each block mean: per (gcm, scen, window, quantity, Cell), the truth seed is non-null and
    (the other seed is non-null or invalid for that member-window). The emulator is averaged over the SAME cells.
    truth_seed = 1 is the round-1 mask; truth_seed = 2 (SH14) swaps the roles."""
    ts, ots = int(truth_seed), 3 - int(truth_seed)
    k = ["gcm", "scen", "window", "Cell", "quantity"]
    s1 = lv.filter((pl.col("seed") == ts) & pl.col("valid")).select(k + [pl.col("value").alias("C")])
    s2 = lv.filter((pl.col("seed") == ots) & pl.col("valid")).select(k + [pl.col("value").alias("R")])
    s2m = lv.filter((pl.col("seed") == ots) & pl.col("valid")).select(["gcm", "scen", "window"]).unique() \
        .with_columns(pl.lit(True).alias("s2valid"))
    m = s1.join(s2, on=k, how="left").join(s2m, on=["gcm", "scen", "window"], how="left").with_columns(
        pl.col("s2valid").fill_null(False))
    m = m.filter(pl.col("C").is_not_null() & (pl.col("R").is_not_null() | ~pl.col("s2valid")))
    m = m.join(bm, on="Cell", how="inner")
    return m.select(["gcm", "scen", "window", "quantity", "Cell", "block", "area_km2_approx"])


def block_values(vals: pl.DataFrame, mask: pl.DataFrame, by: list[str]) -> pl.DataFrame:
    """Area-weighted block mean of `value` over the mask cells; a block whose mask has a cell without a value is
    null (= missing). vals: by + [window, quantity, Cell, value] with window/scen already aligned to the mask."""
    k = ["gcm", "scen", "window", "quantity", "Cell"]
    x = mask.join(vals, on=k, how="left")
    g = x.group_by([c for c in by if c not in k] + ["gcm", "scen", "window", "quantity", "block"]).agg(
        pl.when(pl.col("value").is_null().any()).then(None).otherwise(
            (pl.col("value") * pl.col("area_km2_approx")).sum() / pl.col("area_km2_approx").sum()).alias("value"),
        pl.len().alias("n_cells_block"))
    return g.rename({"block": "Cell"})


def build_block_reference(lv: pl.DataFrame, cells: list[int] | None = None, truth_seed: int = 1) -> dict:
    bm = block_map(cells)
    mask = block_mask(lv.filter(pl.col("Cell").is_in(bm["Cell"].to_list())), bm, truth_seed)
    parts = []
    for seed in (1, 2):
        v = lv.filter(pl.col("seed") == seed)
        val = v.select(["gcm", "scen", "window", "seed", "valid"]).unique()
        b = block_values(v.select(["gcm", "scen", "window", "quantity", "Cell", "value"]), mask, [])
        b = b.join(val, on=["gcm", "scen", "window"], how="inner")
        parts.append(b)
    blv = pl.concat(parts).select(["gcm", "scen", "seed", "window", "Cell", "quantity", "value", "valid",
                                   "n_cells_block"])
    tol = build_tolerance(blv.drop("n_cells_block"), truth_seed)
    tol, cals = calibrate_all(tol)
    ncb = blv.filter(pl.col("seed") == truth_seed).select(
        ["gcm", "scen", "window", "Cell", "quantity", "n_cells_block"])
    tol = tol.join(ncb, on=["gcm", "scen", "window", "Cell", "quantity"], how="left")
    return {"map": bm, "mask": mask, "levels": blv, "tolerance": tol, "calibration": cals[0],
            "calibration_c": cals[1], "calibration_extra": cals[2]}


def blocks() -> int:
    """Block-scale reference for all reference cells (reference/block/) and for the dev cells Cell % 10 == 0
    (reference/block_dev/), so a dev-subset arm is scored against blocks built from the same cells.
    Files without suffix = truth seed 1 (round 1, extended); *_t2 = truth seed 2 (SH14)."""
    t0 = time.time()
    lv = pl.read_parquet(f"{REFOUT}/levels_long.parquet")
    allcells = sorted(lv["Cell"].unique().to_list())
    for name, cells in [("block", allcells), ("block_dev", [c for c in allcells if c % 10 == 0])]:
        d = f"{REFOUT}/{name}"
        os.makedirs(d, exist_ok=True)
        for ts in (1, 2):
            sfx = "" if ts == 1 else "_t2"
            r = build_block_reference(lv, cells, ts)
            if ts == 1:
                write_atomic(r["map"], f"{d}/map.parquet")
            for key in ["mask", "levels", "tolerance"]:
                write_atomic(r[key], f"{d}/{key}{sfx}.parquet")
            r["calibration"].sort(["target_kind", "quantity"]).write_csv(f"{d}/calibration{sfx}.csv")
            r["calibration_c"].sort(["target_kind", "quantity"]).write_csv(f"{d}/calibration_c{sfx}.csv")
            r["calibration_extra"].write_csv(f"{d}/calibration_extra{sfx}.csv")
            nb = r["map"]["block"].n_unique()
            szs = r["map"].group_by("block").len()["len"]
            tol = r["tolerance"]
            k2 = ["gcm", "scen", "window", "Cell", "quantity"]
            assert tol.select(k2).n_unique() == tol.height
            summ = (tol.group_by(["gcm", "scen", "window", "quantity"]).agg(
                pl.len().alias("n_blocks"), pl.col("spread_cell").median().alias("spread_block_med"),
                (pl.col("allowed") / pl.col("C").abs()).median().alias("allowed_rel_med"),
                (pl.col("allowed_cal") / pl.col("C").abs()).median().alias("allowed_cal_rel_med"),
                pl.col("sn_cell").median().alias("sn_block_med"),
                (pl.col("sn_cell") >= 3).mean().alias("frac_sn_ge3"),
                (pl.col("allowed_c") / pl.col("C").abs()).median().alias("allowed_c_rel_med"),
                (pl.col("allowed_cal_c") / pl.col("C").abs()).median().alias("allowed_cal_c_rel_med"))
                .sort(["gcm", "scen", "window", "quantity"]))
            summ.write_csv(f"{d}/tolerance_summary{sfx}.csv")
            g = {"truth_seed": ts, "reference_set": REFSET, "targets": sorted(tol["window"].unique().to_list()),
                 "cells": len(cells), "blocks": nb, "block_size_min": int(szs.min()),
                 "block_size_median": float(szs.median()), "block_size_max": int(szs.max()), "block_deg": BLOCK_DEG,
                 "block_min_cells": BLOCK_MIN_CELLS, "tolerance_rows": tol.height, "keys_unique": True,
                 "tolerance_rows_by_kind": {x["target_kind"]: x["len"] for x in tol.group_by("target_kind").len()
                                            .iter_rows(named=True)},
                 "calibration_p": pl.concat([r["calibration"].with_columns(pl.lit("s_med").alias("v")),
                                             r["calibration_c"].with_columns(pl.lit("s_med_c").alias("v"))],
                                            how="diagonal_relaxed")
                 .select(["v", "target_kind", "p", "conj_panel106"]).unique().sort(["v", "target_kind"]).to_dicts(),
                 "calibration_extra": r["calibration_extra"].to_dicts(), "contrast_fit_scens": CONTRAST_FIT_SCENS}
            json.dump(g, open(f"{d}/_gates{sfx}.json", "w"), indent=1)
            log(f"{name}{sfx}: {json.dumps(g)}")
            with pl.Config(tbl_rows=60, tbl_cols=12, float_precision=3):
                print(summ.filter(pl.col("quantity").is_in(["n_per_patch", "agb_stand", "SLA_q50", "Wooddens_q50",
                                                             "D95max_q50", "minwscal_q50", "share_3"])
                                  & pl.col("window").is_in(list(RESPONSES) + list(CONTRASTS) + ["h1985"])
                                  & (pl.col("gcm") == "MPI-ESM1-2-HR")))
    log(f"blocks done in {time.time() - t0:.0f} s")
    return 0


# ---------------------------------------------------------------------------------------------------------
# frozen (SH14 amendment 4): the window statistics of a FROZEN roster -- the living trees of year Y repeated for
# every year of a 30-year window, exactly what an engine FROZEN run writes -- from each seed's Historical roster
# in 1985 and 2014. The scorer's frozen nulls read these. Also records how far a frozen window statistic is from
# the single-year statistic (the pre-registered N2 identity holds exactly for counts/shares/agb_stand but only
# approximately for linear-interpolated quantiles of a replicated sample).
# ---------------------------------------------------------------------------------------------------------
FROZEN_YEARS = (1985, 2014)
FROZEN_NREP = 30


def frozen() -> int:
    t0 = time.time()
    d = f"{OUT}/frozen"
    os.makedirs(d, exist_ok=True)
    g = gates().filter(pl.col("scen") == "Historical")
    recs = []
    for r in g.iter_rows(named=True):
        member = r["member"]
        census = pl.read_parquet(f"{IND}/_census/{member}.parquet")
        root = member_root(r)
        rep_parts = {y: [] for y in FROZEN_YEARS}
        one_parts = {y: [] for y in FROZEN_YEARS}
        nliv = {y: 0 for y in FROZEN_YEARS}
        for cb in partitions(root):
            lf = pl.scan_parquet(f"{root}/cb={cb:02d}/part-0.parquet").select(READ_COLS)
            allt = living(lf.filter(pl.col("Year").is_in(list(FROZEN_YEARS)))).collect()
            for y in FROZEN_YEARS:
                cells = census.filter((pl.col("Year") == y)
                                      & ((pl.col("Cell") // CELLS_PER_PARTITION) == cb)).select("Cell")
                trees = allt.filter(pl.col("Year") == y)
                nliv[y] += trees.height
                rep = trees.with_columns(pl.lit(list(range(FROZEN_NREP)), dtype=pl.List(pl.Int16)).alias("_r")) \
                    .explode("_r").drop("_r")
                rep_parts[y].append(reduce_window(rep, cells.with_columns(pl.lit(FROZEN_NREP).alias("n_years"))))
                one_parts[y].append(reduce_window(trees, cells.with_columns(pl.lit(1).alias("n_years"))))
        for y in FROZEN_YEARS:
            meta = [pl.lit(r["gcm"]).alias("gcm"), pl.lit(int(r["seed"])).cast(pl.Int8).alias("seed"),
                    pl.lit(y).cast(pl.Int32).alias("year")]
            rep = pl.concat(rep_parts[y]).with_columns(meta)
            one = pl.concat(one_parts[y]).with_columns(meta)
            assert rep["Cell"].n_unique() == rep.height
            write_atomic(rep, f"{d}/{r['gcm']}_s{r['seed']}_y{y}.parquet")
            write_atomic(one, f"{d}/{r['gcm']}_s{r['seed']}_y{y}_singleyear.parquet")
            j = rep.select(["Cell"] + QUANTITIES).unpivot(index="Cell", variable_name="quantity", value_name="a") \
                .join(one.select(["Cell"] + QUANTITIES).unpivot(index="Cell", variable_name="quantity",
                                                               value_name="b"), on=["Cell", "quantity"])
            j = j.filter(pl.col("a").is_not_null() & pl.col("b").is_not_null()).with_columns(
                ((pl.col("a") - pl.col("b")).abs() / pl.col("b").abs().clip(1e-12)).alias("rel"))
            per_q = j.group_by("quantity").agg(pl.col("rel").max().alias("max_rel"),
                                               pl.col("rel").median().alias("med_rel")).sort("quantity")
            rec = {"member": member, "year": y, "cells": rep.height, "living_trees": nliv[y],
                   "n_years_rep": FROZEN_NREP,
                   "rep_vs_single_max_rel_counts_shares": float(
                       j.filter(~pl.col("quantity").str.contains("_q")).select(pl.col("rel").max()).item() or 0.0),
                   "rep_vs_single_max_rel_quantiles": float(
                       j.filter(pl.col("quantity").str.contains("_q")).select(pl.col("rel").max()).item() or 0.0),
                   "rep_vs_single_median_rel_quantiles": float(
                       j.filter(pl.col("quantity").str.contains("_q")).select(pl.col("rel").median()).item()
                       or 0.0),
                   "rep_vs_single_per_quantity": per_q.to_dicts()}
            recs.append(rec)
            log(f"frozen {member} {y}: {rep.height} cells, {nliv[y]} living trees, max rel (counts/shares) "
                f"{rec['rep_vs_single_max_rel_counts_shares']:.2e}, quantiles max "
                f"{rec['rep_vs_single_max_rel_quantiles']:.2e} median {rec['rep_vs_single_median_rel_quantiles']:.2e}")
    json.dump({"frozen": recs, "wall_s": round(time.time() - t0, 1)}, open(f"{d}/_gates.json", "w"), indent=1)
    log(f"frozen done in {time.time() - t0:.0f} s")
    return 0


# ---------------------------------------------------------------------------------------------------------
# verify: an INDEPENDENT recomputation (duckdb SQL straight from the ind parquet, not the polars reduction)
# ---------------------------------------------------------------------------------------------------------
def verify() -> int:
    import duckdb

    t0 = time.time()
    con = duckdb.connect()
    con.execute(f"PRAGMA threads={os.environ.get('POLARS_MAX_THREADS', '8')}")
    g = gates()
    picks = ["MPI-ESM1-2-HR_Historical_s1_h1985", "ACCESS-CM2_ssp370_s2_w2071", "MPI-ESM1-2-HR_ssp126_s1_w3071",
             "ACCESS-CM2_ssp245_s1_w2015"]
    rng = np.random.default_rng(20261001)
    recs, ok_all = [], True
    for member in picks:
        r = g.filter(pl.col("member") == member).row(0, named=True)
        st = pl.read_parquet(f"{OUT}/stats/{member}.parquet")
        sparse = st.filter(pl.col("n_stemyears") > 0).sort("n_stemyears")["Cell"].head(2).to_list()
        cells = sorted(set(rng.choice(st["Cell"].to_numpy(), 10, replace=False).tolist()) | set(sparse))
        cbs = sorted({c // CELLS_PER_PARTITION for c in cells})
        files = ",".join(f"'{member_root(r)}/cb={cb:02d}/part-0.parquet'" for cb in cbs)
        cl = ",".join(str(c) for c in cells)
        y0, y1 = WINDOWS[r["window"]]
        qs = "[" + ",".join(str(q) for q in QS) + "]"
        sel = ", ".join(f"quantile_cont({v}::DOUBLE, {qs}) AS {v}_q" for v in TRAITS)
        sql = f"""
        WITH a AS (SELECT * FROM read_parquet([{files}]) WHERE Cell IN ({cl}) AND Year BETWEEN {y0} AND {y1}),
        ny AS (SELECT Cell, count(DISTINCT Year) AS n_years FROM a GROUP BY Cell),
        t AS (SELECT * FROM a WHERE Type <= 6 AND isdead = 0 AND Height >= {HMIN}),
        s AS (SELECT Cell, count(*)::BIGINT AS n, sum(agb::DOUBLE) AS agb_sum,
              {", ".join(f"count(*) FILTER (WHERE Type = {t})::BIGINT AS n_t{t}" for t in PFTS)}, {sel}
              FROM t GROUP BY Cell)
        SELECT ny.Cell, ny.n_years, s.* EXCLUDE (Cell) FROM ny LEFT JOIN s USING (Cell) ORDER BY ny.Cell"""
        dk = pl.from_arrow(con.execute(sql).arrow())
        assert dk.height == len(cells), f"duckdb returned {dk.height} of {len(cells)} cells"
        rows = []
        for row in dk.iter_rows(named=True):
            c = row["Cell"]
            ref = st.filter(pl.col("Cell") == c).row(0, named=True)
            n = int(row["n"] or 0)
            den = row["n_years"] * NPATCH
            exp = {"n_years": row["n_years"], "n_stemyears": n, "n_per_patch": n / den,
                   "agb_stand": (row["agb_sum"] or 0.0) / den}
            for t in PFTS:
                exp[f"share_{t}"] = (row[f"n_t{t}"] / n) if n else None
            for v in TRAITS:
                for qn, val in zip(QN, row[f"{v}_q"] or [None] * 5, strict=True):
                    exp[f"{v}_{qn}"] = val if n >= NMIN_STEMYEARS else None
            for kq, ve in exp.items():
                vr = ref[kq]
                if ve is None or vr is None:
                    bad = (ve is None) != (vr is None)
                    rel = None
                else:
                    rel = abs(ve - vr) / max(abs(ve), 1e-12)
                    bad = rel > 1e-5
                rows.append({"member": member, "Cell": c, "quantity": kq, "duckdb": ve, "polars": vr, "rel": rel,
                             "bad": bad})
        df = pl.DataFrame(rows, infer_schema_length=None)
        nb = int(df["bad"].sum())
        mx = df["rel"].drop_nulls().max()
        recs.append({"member": member, "cells": cells, "values_compared": df.height, "mismatches": nb,
                     "max_rel_diff": mx})
        ok_all &= nb == 0
        if nb:
            print(df.filter(pl.col("bad")).head(20))
        log(f"verify {member}: {df.height} values, {nb} mismatches, max rel diff {mx}")
    out = {"verify": "duckdb SQL from ind parquet vs reference/stats (polars)", "ok": ok_all, "members": recs,
           "tolerance_rel": 1e-5, "wall_s": round(time.time() - t0, 1)}
    json.dump(out, open(f"{OUT}/_verify.json", "w"), indent=1)
    print(json.dumps(out, indent=1))
    return 0 if ok_all else 4


def main() -> int:
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 1
    if a[0] == "reduce":
        return reduce_member(int(a[1]))
    if a[0] == "submit":
        return submit(a[1:])
    if a[0] == "assemble":
        return assemble()
    if a[0] == "calibrate":
        return calibrate(int(a[1]) if len(a) > 1 else 1)
    if a[0] == "frozen":
        return frozen()
    if a[0] == "blocks":
        return blocks()
    if a[0] == "verify":
        return verify()
    if a[0] == "collect":
        collect()
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
