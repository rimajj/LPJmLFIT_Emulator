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
                       reference/_gates.json, reference/_DEFINITION.md
  calibrate         adds allowed_cal to tolerance.parquet (second-run passes the panel in 95 % of cells)
  blocks            the same reference at ~1-degree BLOCK scale -> reference/block/, reference/block_dev/
  verify            independent duckdb recomputation of reference/stats for sample cells -> reference/_verify.json
  collect           print which members are done / missing

Env knobs (EXPORT them): DEREF_FORCE=1 re-reduce even if done.
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
XDE = "/p/tmp/jamirp/X_de"
IND = f"{XDE}/ind"
OUT = f"{XDE}/reference"
LOGDIR = f"{REPO}/logs"
PY = "/home/jamirp/.conda/envs/py311_new/bin/python"

NPATCH = 250
HMIN = 5.0
NMIN_STEMYEARS = 30  # fewer living stem-years than this in a window -> quantiles are not scored (null)
TRAITS = ["SLA", "Wooddens", "D95max", "minwscal", "Longevity", "Height", "agb"]
QS = [0.05, 0.25, 0.50, 0.75, 0.95]
QN = ["q05", "q25", "q50", "q75", "q95"]
PFTS = list(range(7))
WINDOWS = {"h1985": (1985, 2014), "w2015": (2015, 2044), "w2071": (2071, 2100), "w3071": (3071, 3100)}
RESPONSES = {"r2071": "w2071", "r2015": "w2015"}  # response target -> the window it is (window - h1985) of
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
    for cb in range(19):
        f = f"{root}/cb={cb:02d}/part-0.parquet"
        if not os.path.exists(f):
            raise FileNotFoundError(f)
        lf = pl.scan_parquet(f).select(READ_COLS)
        base = lf.filter((pl.col("Type") <= 6) & (pl.col("isdead") == 0))
        trees = living(lf).collect()
        n_base = base.select(pl.len()).collect().item()
        n_height_cut += n_base - trees.height
        n_live_total += trees.height
        cyb = cells_years.filter((pl.col("Cell") // 500) == cb)
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


def build_tolerance(lv: pl.DataFrame) -> pl.DataFrame:
    k = ["gcm", "scen", "window", "Cell", "quantity"]
    s1 = lv.filter(pl.col("seed") == 1).select(k + [pl.col("value").alias("C")])
    s2 = (
        lv.filter((pl.col("seed") == 2) & pl.col("valid"))
        .select(k + [pl.col("value").alias("R")])
    )
    lev = s1.join(s2, on=k, how="left")
    # density stratum: 2-seed mean (seed 1 alone where seed 2 is invalid) of n_per_patch in that window
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
        c = x.filter(pl.col("seed") == 1).select(
            ["gcm", "scen", "Cell", "quantity", pl.col("D").alias("C"), pl.col("H").alias("H1")]
        )
        r = x.filter((pl.col("seed") == 2) & pl.col("dvalid")).select(
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
    cols = ["gcm", "scen", "window", "Cell", "quantity", "target_kind", "C", "R", "scale", "dens", "stratum",
            "spread_cell"]
    allt = pl.concat([lev.select(cols), rsp.select(cols)])
    # ---- stratum spreads
    by = ["gcm", "scen", "window", "quantity"]
    st = strat_stats(allt, by, "spread_cell")
    allt = allt.join(st, on=by + ["stratum"], how="left")
    # where seed 2 is invalid for a whole (gcm, scen, window) (MPI ssp370 w3071 and its responses none, since
    # r2071 uses w2071), borrow the stratum spread of the same gcm's OTHER scenarios for that window
    miss = allt.group_by(by).agg(pl.col("R").is_not_null().sum().alias("nR")).filter(pl.col("nR") == 0)
    allt = allt.with_columns(pl.lit("own").alias("tol_source"))
    if miss.height:
        bor = (
            allt.join(miss.select(["gcm", "window", "quantity"]).unique(), on=["gcm", "window", "quantity"])
            .filter(pl.col("R").is_not_null())
            .group_by(["gcm", "window", "quantity", "stratum"])
            .agg(pl.col("spread_cell").median().alias("b_med"), pl.col("spread_cell").quantile(0.9).alias("b_q90"),
                 pl.col("scen").unique().sort().str.join("+").alias("b_src"))
        )
        allt = allt.join(miss.select(by).with_columns(pl.lit(True).alias("_m")), on=by, how="left")
        allt = allt.join(bor, on=["gcm", "window", "quantity", "stratum"], how="left").with_columns(
            pl.when(pl.col("_m")).then(pl.col("b_med")).otherwise(pl.col("s_med")).alias("s_med"),
            pl.when(pl.col("_m")).then(pl.col("b_q90")).otherwise(pl.col("s_q90")).alias("s_q90"),
            pl.when(pl.col("_m")).then(pl.lit("borrowed:") + pl.col("b_src")).otherwise(pl.col("tol_source"))
            .alias("tol_source"),
        ).drop(["_m", "b_med", "b_q90", "b_src"])
    # ---- allowed absolute error
    isf = pl.col("quantity").str.starts_with("share_")
    isr = pl.col("target_kind") == "response"
    absC = pl.col("C").abs()

    def allowed(sp: pl.Expr) -> pl.Expr:
        return (
            pl.when(isf)
            .then(pl.max_horizontal(REL_FLOOR * absC, sp, pl.lit(SHARE_FLOOR)))
            .when(isr)
            .then(pl.max_horizontal(REL_FLOOR * absC, sp * pl.col("scale")))
            .otherwise(absC * pl.max_horizontal(pl.lit(REL_FLOOR), sp))
        )

    allt = allt.with_columns(
        allowed(pl.col("s_med")).alias("allowed"),
        allowed(pl.col("s_q90")).alias("allowed_q90"),
        pl.when(pl.col("spread_cell").is_null()).then(None).otherwise(allowed(pl.col("spread_cell")))
        .alias("allowed_cell"),
        pl.when(isr & pl.col("R").is_not_null())
        .then(((pl.col("C") + pl.col("R")) / 2).abs() / (pl.col("C") - pl.col("R")).abs())
        .otherwise(None)
        .alias("sn_cell"),
    )
    # trait quantiles with too few stems -> C null -> not scored
    allt = allt.filter(pl.col("C").is_not_null())
    k2 = ["gcm", "scen", "window", "Cell", "quantity"]
    assert allt.select(k2).n_unique() == allt.height, "duplicate keys in tolerance table"
    return allt.sort(k2)


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
    for reg in ["DE", "south", "central", "north"]:
        x = d if reg == "DE" else d.filter(pl.col("region") == reg)
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
"""


def assemble() -> int:
    t0 = time.time()
    lv = load_levels()
    log(f"levels: {lv.height} rows")
    lv.write_parquet(f"{OUT}/levels_long.parquet")
    tol = build_tolerance(lv)
    log(f"tolerance: {tol.height} rows")
    tol.write_parquet(f"{OUT}/tolerance.parquet")
    agg, terc = build_aggregate(tol)
    agg.write_parquet(f"{OUT}/aggregate.parquet")
    agg.write_csv(f"{OUT}/aggregate.csv")
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
        )
        .sort(["gcm", "scen", "window", "quantity"])
    )
    summ.write_csv(f"{OUT}/tolerance_summary.csv")
    strata = tol.filter(pl.col("quantity") == "n_per_patch").group_by(["gcm", "scen", "window", "stratum"]).len()
    gate = {
        "levels_rows": lv.height,
        "tolerance_rows": tol.height,
        "tolerance_keys_unique": True,
        "members": lv.select(["gcm", "scen", "seed", "window"]).unique().height,
        "invalid_members": lv.filter(~pl.col("valid")).select(["gcm", "scen", "seed", "window"]).unique().to_dicts(),
        "cells_per_target_min": int(tol.group_by(["gcm", "scen", "window", "quantity"]).len()["len"].min()),
        "cells_per_target_max": int(tol.group_by(["gcm", "scen", "window", "quantity"]).len()["len"].max()),
        "strata_counts": strata.sort(["gcm", "scen", "window", "stratum"]).to_dicts(),
        "lat_tercile_edges": terc,
        "wall_s": round(time.time() - t0, 1),
    }
    json.dump(gate, open(f"{OUT}/_gates.json", "w"), indent=1, default=str)
    open(f"{OUT}/_DEFINITION.md", "w").write(DEFINITION)
    log(f"assemble done in {time.time() - t0:.0f} s")
    with pl.Config(tbl_rows=200, tbl_cols=20, fmt_str_lengths=40):
        print(summ.filter(pl.col("quantity").is_in(["n_per_patch", "agb_stand", "SLA_q50", "Wooddens_q50",
                                                    "D95max_q50", "minwscal_q50", "Height_q50", "share_3"])))
    return 0


# ---------------------------------------------------------------------------------------------------------
# calibrate: a tolerance under which a SECOND RUN of the original passes the whole panel in CAL_TARGET of cells
# ---------------------------------------------------------------------------------------------------------
CAL_TARGET = 0.95


def _floor_base():
    isf = pl.col("quantity").str.starts_with("share_")
    isr = pl.col("target_kind") == "response"
    absC = pl.col("C").abs()
    floor = pl.when(isf).then(pl.max_horizontal(REL_FLOOR * absC, pl.lit(SHARE_FLOOR))).otherwise(REL_FLOOR * absC)
    base = pl.when(isf).then(pl.lit(1.0)).when(isr).then(pl.col("scale")).otherwise(absC)
    return floor, base


def calibrate() -> int:
    """Per (quantity, target_kind) multiplier k_q on the stratum-median spread, all k_q at the same per-quantity
    quantile p of the seed-2-vs-seed-1 ratio, with p found by bisection so that seed 2 passes ALL panel106
    quantities in CAL_TARGET of (target, cell) pairs. In-sample by construction for the other-seed null (stated).
    Adds column allowed_cal to tolerance.parquet; writes calibration.csv."""
    t0 = time.time()
    tol = pl.read_parquet(f"{OUT}/tolerance.parquet")
    tol, cal = calibrate_table(tol)
    cal.sort(["target_kind", "quantity"]).write_csv(f"{OUT}/calibration.csv")
    tol.write_parquet(f"{OUT}/tolerance.parquet")
    log(f"calibrate done ({time.time() - t0:.0f} s)")
    with pl.Config(tbl_rows=100):
        print(cal.sort(["target_kind", "quantity"]))
    return 0


def calibrate_table(tol: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """The calibration itself (see calibrate()); works on a cell-scale or block-scale tolerance table."""
    if "allowed_cal" in tol.columns:
        tol = tol.drop("allowed_cal")
    floor, base = _floor_base()
    x = tol.filter(pl.col("R").is_not_null()).select(
        ["gcm", "scen", "window", "Cell", "quantity", "target_kind", "C", "R", "s_med", "scale"]
    ).with_columns(floor.alias("floor"), base.alias("base"), (pl.col("R") - pl.col("C")).abs().alias("dev"))
    x = x.with_columns(
        pl.when(pl.col("dev") <= pl.col("floor")).then(0.0)
        .when(pl.col("s_med") * pl.col("base") > 0).then(pl.col("dev") / (pl.col("s_med") * pl.col("base")))
        .otherwise(float("inf")).alias("r")
    )
    rows = []
    for kind in ["level", "response"]:
        sub = x.filter((pl.col("target_kind") == kind) & pl.col("quantity").is_in(PANEL106))

        def conj(p, sub=sub):
            k = sub.group_by("quantity").agg(pl.col("r").quantile(p, interpolation="higher").alias("k"))
            y = sub.join(k, on="quantity").with_columns((pl.col("r") <= pl.col("k")).alias("ok"))
            return y.group_by(["gcm", "scen", "window", "Cell"]).agg(pl.col("ok").all())["ok"].mean()

        lo, hi = 0.5, 1.0
        for _ in range(22):
            mid = (lo + hi) / 2
            if conj(mid) >= CAL_TARGET:
                hi = mid
            else:
                lo = mid
        p = hi
        c = conj(p)
        allq = x.filter(pl.col("target_kind") == kind)
        k = allq.group_by("quantity").agg(
            pl.col("r").quantile(p, interpolation="higher").alias("k"),
            pl.col("s_med").median().alias("s_med_median"),
        )
        k = k.with_columns(pl.lit(kind).alias("target_kind"), pl.lit(p).alias("p"), pl.lit(c).alias("conj_panel106"))
        rows.append(k)
        log(f"calibrate {kind}: p = {p:.5f}, seed-2 panel106 conjunctive pass = {c:.4f}")
    cal = pl.concat(rows).with_columns(
        pl.when(pl.col("k").is_infinite()).then(None).otherwise(pl.col("k")).alias("k"))
    tol = tol.join(cal.select(["quantity", "target_kind", "k"]), on=["quantity", "target_kind"], how="left")
    tol = tol.with_columns(
        pl.max_horizontal(floor, pl.col("k").fill_null(0.0) * pl.col("s_med") * base).alias("allowed_cal")
    ).drop("k")
    return tol, cal


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


def block_mask(lv: pl.DataFrame, bm: pl.DataFrame) -> pl.DataFrame:
    """Which cells enter each block mean: per (gcm, scen, window, quantity, Cell), seed 1 is non-null and (seed 2
    is non-null or seed 2 is invalid for that member-window). The emulator is averaged over the SAME cells."""
    k = ["gcm", "scen", "window", "Cell", "quantity"]
    s1 = lv.filter(pl.col("seed") == 1).select(k + [pl.col("value").alias("C")])
    s2 = lv.filter((pl.col("seed") == 2) & pl.col("valid")).select(k + [pl.col("value").alias("R")])
    s2m = lv.filter((pl.col("seed") == 2) & pl.col("valid")).select(["gcm", "scen", "window"]).unique() \
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


def build_block_reference(lv: pl.DataFrame, cells: list[int] | None = None) -> dict:
    bm = block_map(cells)
    mask = block_mask(lv.filter(pl.col("Cell").is_in(bm["Cell"].to_list())), bm)
    parts = []
    for seed in (1, 2):
        v = lv.filter(pl.col("seed") == seed)
        val = v.select(["gcm", "scen", "window", "seed", "valid"]).unique()
        b = block_values(v.select(["gcm", "scen", "window", "quantity", "Cell", "value"]), mask, [])
        b = b.join(val, on=["gcm", "scen", "window"], how="inner")
        parts.append(b)
    blv = pl.concat(parts).select(["gcm", "scen", "seed", "window", "Cell", "quantity", "value", "valid",
                                   "n_cells_block"])
    tol = build_tolerance(blv.drop("n_cells_block"))
    tol, cal = calibrate_table(tol)
    ncb = blv.filter(pl.col("seed") == 1).select(["gcm", "scen", "window", "Cell", "quantity", "n_cells_block"])
    tol = tol.join(ncb, on=["gcm", "scen", "window", "Cell", "quantity"], how="left")
    return {"map": bm, "mask": mask, "levels": blv, "tolerance": tol, "calibration": cal}


def blocks() -> int:
    """Block-scale reference for all reference cells (reference/block/) and for the dev cells Cell % 10 == 0
    (reference/block_dev/), so a dev-subset arm is scored against blocks built from the same cells."""
    t0 = time.time()
    lv = pl.read_parquet(f"{OUT}/levels_long.parquet")
    allcells = sorted(lv["Cell"].unique().to_list())
    for name, cells in [("block", allcells), ("block_dev", [c for c in allcells if c % 10 == 0])]:
        d = f"{OUT}/{name}"
        os.makedirs(d, exist_ok=True)
        r = build_block_reference(lv, cells)
        for key in ["map", "mask", "levels", "tolerance"]:
            r[key].write_parquet(f"{d}/{key}.parquet")
        r["calibration"].sort(["target_kind", "quantity"]).write_csv(f"{d}/calibration.csv")
        nb = r["map"]["block"].n_unique()
        szs = r["map"].group_by("block").len()["len"]
        tol = r["tolerance"]
        k2 = ["gcm", "scen", "window", "Cell", "quantity"]
        assert tol.select(k2).n_unique() == tol.height
        summ = (tol.group_by(["gcm", "scen", "window", "quantity"]).agg(
            pl.len().alias("n_blocks"), pl.col("spread_cell").median().alias("spread_block_med"),
            (pl.col("allowed") / pl.col("C").abs()).median().alias("allowed_rel_med"),
            (pl.col("allowed_cal") / pl.col("C").abs()).median().alias("allowed_cal_rel_med"),
            pl.col("sn_cell").median().alias("sn_block_med"), (pl.col("sn_cell") >= 3).mean().alias("frac_sn_ge3"))
            .sort(["gcm", "scen", "window", "quantity"]))
        summ.write_csv(f"{d}/tolerance_summary.csv")
        g = {"cells": len(cells), "blocks": nb, "block_size_min": int(szs.min()), "block_size_median": float(
            szs.median()), "block_size_max": int(szs.max()), "block_deg": BLOCK_DEG,
             "block_min_cells": BLOCK_MIN_CELLS, "tolerance_rows": tol.height, "keys_unique": True,
             "calibration_p": r["calibration"].select(["target_kind", "p", "conj_panel106"]).unique().to_dicts()}
        json.dump(g, open(f"{d}/_gates.json", "w"), indent=1)
        log(f"{name}: {json.dumps(g)}")
        with pl.Config(tbl_rows=60, tbl_cols=12, float_precision=3):
            print(summ.filter(pl.col("quantity").is_in(["n_per_patch", "agb_stand", "SLA_q50", "Wooddens_q50",
                                                         "D95max_q50", "minwscal_q50", "share_3"])
                              & pl.col("window").is_in(["r2071", "h1985"]) & (pl.col("gcm") == "MPI-ESM1-2-HR")))
    log(f"blocks done in {time.time() - t0:.0f} s")
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
        cbs = sorted({c // 500 for c in cells})
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
        return calibrate()
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
