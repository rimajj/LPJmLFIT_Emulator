#!/usr/bin/env python3
"""SH0 -- registry, segment flags, block folds, shared climate-blind year map (line X, Germany emulator).

Builds, from the production run directories (READ-ONLY) and the converted ind tables, four shared tables that
every emulator track joins against, plus provenance tables:

  <out>/members.parquet        one row per converted member-window (gcm, scen, seed, win): paths, the C run that
                               wrote it (job, config, binary build), rh_on, truncation, complete years, usable
                               one-step pair years.
  <out>/segments.parquet       one row per (gcm, scen, seed, Year) of each TRAJECTORY (Historical, or an ssp whose
                               years <= the historical last year come from the same-seed Historical run):
                               segment id, rh_on, bin_feb2026, the build string, the climate year/scenario the C
                               actually read (recycled after 2100), tree-table window and pair_ok.
  <out>/folds.parquet          Cell -> block (reference/block/map.parquet) -> fold 1..K (greedy, deterministic,
                               balancing dev-cell counts), is_dev, lon, lat.
  <out>/blind_yearmap.parquet  (gcm, rep, Year) -> src_year in the historical baseline period, SHARED by all cells
                               and arms (climate-blind "CB-resample" arms). Drawn with a SHA-256 hash, so it does
                               not depend on numpy's RNG stream or version.
  <out>/splits.parquet         role of each member-window in DEV-A / DEV-A2 / DEV-B (incl. critic amendments).
  <out>/attempts.parquet       every lpjml.<job>.out found, parsed (provenance; failed attempts included).
  <out>/_gates.json            gate results.

Nothing Germany-specific is hard-coded: the production root, data root, block map, dev rule, fold count,
baseline period and replicate count are arguments; expected cell/block counts are passed as gate expectations.

Usage:
  python explore_de_sh_registry.py build  [--expect-cells 9065 --expect-blocks 52]
  python explore_de_sh_registry.py check  # rebuild in memory, assert frame-equal to disk (determinism gate)
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEF_PROD = "/p/projects/waldspektrum/data/LPJmLFIT/productionruns_jamir"
DEF_XDE = "/p/tmp/jamirp/X_de"

WIN_OF_TAG = {"hist": "h1985", "2044": "w2015", "2100": "w2071", "3100": "w3071"}
# segment ids by config tag (a C config = one LPJmL invocation; the chain is continuous via restarts)
SEG_OF_TAG = {
    "hist": (1, "hist_to_2044_continuous"),
    "2044": (1, "hist_to_2044_continuous"),
    "2070": (2, "gap_2045_2070"),
    "2100": (3, "w2071_2100"),
    "3070": (4, "gap_2101_3070_recycled"),
    "3100": (5, "w3071_3100_recycled"),
}

# OWNER DECISION 2026-10-01 ("lets only use the earlier data that is correct, for now"): a simulated year is
# CLEAN only if its own C configuration AND every upstream configuration of its restart chain read the humidity
# file as relative humidity (rh_on == 1). Derived from the data (cumulative minimum of rh_on along each
# trajectory), not from a year list: in this archive it excludes 2071-3100 (the lpjml_2100 and lpjml_3100
# segments are rh_on == 0, and 2101-3070 restarts from the corrupted 2100 state). The windows that touch an
# unclean year are EXCLUDED from training, testing, scoring, initial states, nulls and calibration.
OWNER_DECISION = "owner 2026-10-01: use only the correct 1985-2044 data (late-century runs read RH as specific humidity)"
EXCL_REASON_OWN = (
    "rh_off: this segment read the relative-humidity file as specific humidity (VPD = 0)"
)
EXCL_REASON_UP = "inherits rh_off state: restarts from a segment that read humidity wrongly"

RH_RE = re.compile(r'"relative_humidity"\s*:\s*(true|false)')
RH_WARN = "Name 'relative_humidity' for boolean not found, set to false"


def log(*a):
    print(*a, flush=True)


# ----------------------------------------------------------------------------------------------- parse logs
def parse_out(path: str) -> dict:
    txt = open(path, errors="replace").read()
    d = {"out_path": path, "job": int(re.search(r"lpjml\.(\d+)\.out$", path).group(1))}
    m = re.search(r"lpjml C Version (\S+) \(([A-Za-z]{3} +\d+ \d{4})\)", txt)
    d["version"] = m.group(1) if m else None
    d["build"] = re.sub(r" +", " ", m.group(2)) if m else None
    m = re.search(r"Reading configuration from '([^']+)'", txt)
    d["config"] = m.group(1) if m else None
    m = re.search(r"with options\s*\n?\s*'([^']*)'", txt)
    d["options"] = m.group(1) if m else ""
    m = re.search(r"lpjml successfully terminated, (\d+) grid cells processed", txt)
    d["ok"] = bool(m)
    d["ncell_processed"] = int(m.group(1)) if m else None
    m = re.search(r"Starting from restart file '([^']+)'", txt)
    d["restart_from"] = m.group(1) if m else ("scratch" if "Starting from scratch" in txt else None)
    m = re.search(r"Writing restart file '([^']+)' after year (\d+)", txt)
    d["restart_written"] = m.group(1) if m else None
    m = re.search(r"Random seed: (\d+)", txt)
    d["random_seed_log"] = int(m.group(1)) if m else None
    d["seeds_from_restart"] = "Reading random seeds from restart file" in txt
    m = re.search(r"Spinup years:\s+(\d+)", txt)
    d["spinup_years"] = int(m.group(1)) if m else 0
    m = re.search(r"First year:\s+(\d+)", txt)
    d["first_year"] = int(m.group(1)) if m else None
    m = re.search(r"Last year:\s+(\d+)", txt)
    d["last_year"] = int(m.group(1)) if m else None
    m = re.search(r"gap dynamics with (\d+) patches", txt)
    d["npatch"] = int(m.group(1)) if m else None
    m = re.search(r"fix climate after year (\d+) shuffling years (\d+)-(\d+)", txt)
    d["fix_climate"] = f"{m.group(1)}:{m.group(2)}-{m.group(3)}" if m else None
    errp = path[:-4] + ".err"
    etxt = open(errp, errors="replace").read() if os.path.exists(errp) else ""
    d["err_exists"] = os.path.exists(errp)
    d["rh_warn_in_err"] = RH_WARN in etxt
    # third, independent reading of the humidity setting: the input table the C printed. "rhumid" = the file is
    # read as RELATIVE humidity; "humid" = read as SPECIFIC humidity (kg/kg) -- the late-century defect.
    m = re.search(r"^(rhumid|humid)\s+\S+\s+(\S+)", txt, re.M)
    d["humid_kind"] = m.group(1) if m else None
    d["humid_file"] = m.group(2) if m else None
    d["out_mtime"] = os.path.getmtime(path)
    return d


def cfg_tag(config: str | None, scen: str, options: str, restart_from: str | None) -> str:
    if config is None:
        return "unknown"
    b = os.path.basename(config)
    m = re.match(r"lpjml_(\d{4})_", b)
    if m:
        return m.group(1)
    if scen == "Historical":
        return "hist" if (restart_from and restart_from != "scratch") else "hist_spinup"
    return "nonseg"  # e.g. an abandoned ssp config without a year tag


def rh_from_js(config: str) -> tuple[int | None, int]:
    """(rh_on, n_matches) from the config text, ignoring // comment lines. Absent key -> 0 (LPJmL default FALSE,
    fscanconfig.c:255)."""
    vals = []
    for line in open(config, errors="replace"):
        s = line.strip()
        if s.startswith("//"):
            continue
        s = s.split("//", 1)[0]
        for m in RH_RE.finditer(s):
            vals.append(m.group(1) == "true")
    if not vals:
        return 0, 0
    return int(vals[-1]), len(vals)


def sacct_times(jobs: list[int]) -> dict[int, dict]:
    out = {}
    if not jobs:
        return out
    try:
        r = subprocess.run(
            [
                "sacct",
                "-X",
                "-n",
                "-P",
                "-j",
                ",".join(map(str, jobs)),
                "--format=JobID,Start,End,State",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
    except Exception as e:  # noqa: BLE001
        log("sacct unavailable:", e)
        return out
    for line in r.stdout.splitlines():
        p = line.split("|")
        if len(p) < 4 or not p[0].isdigit():
            continue

        def ts(s):
            try:
                return dt.datetime.fromisoformat(s).timestamp()
            except ValueError:
                return None

        out[int(p[0])] = {"start": ts(p[1]), "end": ts(p[2]), "state": p[3]}
    return out


# ----------------------------------------------------------------------------------------------- builders
def build_attempts(prod: str) -> pl.DataFrame:
    rows = []
    for path in sorted(glob.glob(f"{prod}/*/*/random_seed_*/lpjml.*.out")):
        rel = os.path.relpath(path, prod).split(os.sep)
        gcm, scen, sd = rel[0], rel[1], rel[2]
        d = parse_out(path)
        d.update(gcm=gcm, scen=scen, seed=int(sd.split("_")[-1]), run_dir=os.path.dirname(path))
        d["cfg"] = cfg_tag(d["config"], scen, d["options"], d["restart_from"])
        if d["config"] and os.path.exists(d["config"]):
            d["rh_on_js"], d["rh_js_matches"] = rh_from_js(d["config"])
        else:
            d["rh_on_js"], d["rh_js_matches"] = None, 0
        rows.append(d)
    acc = sacct_times(sorted({r["job"] for r in rows}))
    for r in rows:
        a = acc.get(r["job"], {})
        r["job_start"] = a.get("start")
        r["job_end"] = a.get("end")
        r["job_state"] = a.get("state")
    df = pl.DataFrame(rows, infer_schema_length=None)
    # final attempt per (member, cfg) = highest job id
    df = df.with_columns(
        (pl.col("job") == pl.col("job").max().over(["gcm", "scen", "seed", "cfg"])).alias(
            "is_final"
        )
    )
    return df.sort(["gcm", "scen", "seed", "job"])


def build_members(xde: str, att: pl.DataFrame, dev_mod: int) -> pl.DataFrame:
    gates = pl.read_csv(f"{xde}/ind/_gates.csv", infer_schema_length=None)
    rows = []
    for g in gates.iter_rows(named=True):
        gj = json.load(open(f"{xde}/ind/_gates/{g['member']}.json"))
        src = gj["src"]
        meta = json.load(open(src + ".json"))
        hist_cfg = meta.get("history", "").split()[-1]
        jmt = os.path.getmtime(src + ".json")
        cand = att.filter(
            (pl.col("gcm") == g["gcm"])
            & (pl.col("scen") == g["scen"])
            & (pl.col("seed") == g["seed"])
            & (pl.col("config") == hist_cfg)
        )
        # writer = the attempt whose SLURM [start, end] contains the moment the csv.json header was written
        wr = cand.filter((pl.col("job_start") <= jmt + 1) & (pl.col("job_end") >= jmt - 1))
        writer = wr.row(0, named=True) if wr.height == 1 else None
        tag = WIN_OF_TAG_INV.get(g["window"])
        fin = cand.filter(pl.col("is_final") & (pl.col("cfg") == tag))
        final = fin.row(0, named=True) if fin.height == 1 else None
        cen = pl.read_parquet(f"{xde}/ind/_census/{g['member']}.parquet")
        ncells_all = cen["Cell"].n_unique()
        per_year = (
            cen.filter(pl.col("n_tree") > 0).group_by("Year").agg(pl.len().alias("n")).sort("Year")
        )
        y0, y1 = int(meta["firstyear"]), int(meta["lastyear"])
        complete = [int(r["Year"]) for r in per_year.iter_rows(named=True) if r["n"] == ncells_all]
        rows.append(
            {
                "member": g["member"],
                "gcm": g["gcm"],
                "scen": g["scen"],
                "seed": int(g["seed"]),
                "win": g["window"],
                "cfg": tag,
                "ind_path": f"{xde}/ind/{g['gcm']}/{g['scen']}/s{g['seed']}/{g['window']}",
                "ind_dev_path": f"{xde}/ind_dev/{g['member']}.parquet",
                "src_csv": src,
                "src_bytes": int(gj["src_bytes"]),
                "json_firstyear": y0,
                "json_lastyear": y1,
                "config": hist_cfg,
                "writer_job": writer["job"] if writer else None,
                "writer_ok": writer["ok"] if writer else None,
                "writer_state": writer["job_state"] if writer else None,
                "build": writer["build"] if writer else None,
                "npatch": writer["npatch"] if writer else None,
                "restart_from": writer["restart_from"] if writer else None,
                "final_job": final["job"] if final else None,
                "writer_is_final": (
                    writer is not None and final is not None and writer["job"] == final["job"]
                ),
                "n_attempts": cand.filter(pl.col("cfg") == tag).height,
                "rh_on": writer["rh_on_js"] if writer else None,
                "rh_on_log": (0 if writer["rh_warn_in_err"] else 1) if writer else None,
                "bin_feb2026": int(
                    writer["build"].startswith("Feb") and writer["build"].endswith("2026")
                )
                if writer and writer["build"]
                else None,
                "years_present": sorted(cen["Year"].unique().to_list()),
                "years_complete": complete,
                "n_years_complete": len(complete),
                "n_cells": ncells_all,
                "n_dev_cells": int(cen.filter(pl.col("Cell") % dev_mod == 0)["Cell"].n_unique()),
                "conversion_ok": bool(g["conversion_ok"]),
                "gate_pass_traitkey": bool(g["gate_pass_traitkey"]),
                "csv_tail": gj["csv_tail"],
            }
        )
    m = pl.DataFrame(rows, infer_schema_length=None)
    m = m.with_columns(
        (
            (pl.col("n_years_complete") < (pl.col("json_lastyear") - pl.col("json_firstyear") + 1))
            | (pl.col("csv_tail") == "partial")
            | ~pl.col("writer_ok").fill_null(False)
        ).alias("truncated")
    )
    # usable one-step pairs (y -> y+1, both years complete, same continuous C chain, tree tables on both sides).
    hist_last = {
        (r["gcm"], r["seed"]): (r["years_complete"], r["json_lastyear"])
        for r in m.filter(pl.col("win") == "h1985").iter_rows(named=True)
    }
    pairs = []
    for r in m.iter_rows(named=True):
        yc = set(r["years_complete"])
        ys = [y for y in sorted(yc) if y + 1 in yc]
        if (
            r["win"] == "w2015"
        ):  # the transition from the same-seed Historical last year into the ssp
            hc, hl = hist_last.get((r["gcm"], r["seed"]), ([], None))
            if hl is not None and hl in hc and hl + 1 in yc and r["json_firstyear"] == hl + 1:
                ys = [hl] + ys
        pairs.append(ys)
    m = m.with_columns(pl.Series("usable_pair_years", pairs, dtype=pl.List(pl.Int32)))
    m = m.with_columns(pl.col("usable_pair_years").list.len().alias("n_pair_years"))
    return m.sort(["gcm", "scen", "seed", "win"])


WIN_OF_TAG_INV = {v: k for k, v in WIN_OF_TAG.items()}


def build_segments(att: pl.DataFrame, mem: pl.DataFrame, xde: str, recycled: str) -> pl.DataFrame:
    rec = pl.read_parquet(recycled)
    rec_map = {
        (int(r["seed"]), int(r["Year"])): int(r["climate_year"]) for r in rec.iter_rows(named=True)
    }
    final = att.filter(pl.col("is_final") & pl.col("cfg").is_in(list(SEG_OF_TAG)))
    win_years = {}
    for r in mem.iter_rows(named=True):
        win_years[(r["gcm"], r["scen"], r["seed"])] = win_years.get(
            (r["gcm"], r["scen"], r["seed"]), {}
        )
        win_years[(r["gcm"], r["scen"], r["seed"])][r["win"]] = (
            set(r["years_complete"]),
            set(r["usable_pair_years"]),
        )
    rows = []
    trajs = final.select("gcm", "scen", "seed").unique().sort(["gcm", "scen", "seed"])
    for t in trajs.iter_rows(named=True):
        gcm, scen, seed = t["gcm"], t["scen"], t["seed"]
        own = final.filter(
            (pl.col("gcm") == gcm) & (pl.col("scen") == scen) & (pl.col("seed") == seed)
        )
        src = [own]
        if scen != "Historical":
            src.insert(
                0,
                final.filter(
                    (pl.col("gcm") == gcm)
                    & (pl.col("scen") == "Historical")
                    & (pl.col("seed") == seed)
                    & (pl.col("cfg") == "hist")
                ),
            )
        segs = pl.concat(src, how="vertical_relaxed")
        hist_last = None
        for s in segs.sort("first_year").iter_rows(named=True):
            sid, slab = SEG_OF_TAG[s["cfg"]]
            if s["cfg"] == "hist":
                hist_last = s["last_year"]
            win = WIN_OF_TAG.get(s["cfg"])
            for y in range(s["first_year"], s["last_year"] + 1):
                yc, yp = set(), set()
                if win is not None:
                    yc, yp = win_years.get((gcm, s["scen"], seed), {}).get(win, (set(), set()))
                # a pair (y -> y+1) that starts in the Historical file but continues into the ssp w2015
                if s["cfg"] == "hist" and scen != "Historical" and y == s["last_year"]:
                    _, yp15 = win_years.get((gcm, scen, seed), {}).get("w2015", (set(), set()))
                    pair_ok = y in yp15
                elif s["cfg"] == "hist" and scen == "Historical" and y == s["last_year"]:
                    pair_ok = False  # the Historical trajectory itself ends here
                else:
                    pair_ok = y in yp
                recycled_y = y > 2100 and s["fix_climate"] is not None
                rows.append(
                    {
                        "gcm": gcm,
                        "scen": scen,
                        "seed": seed,
                        "Year": y,
                        "src_scen": s["scen"],
                        "cfg": s["cfg"],
                        "segment_id": sid,
                        "segment": slab,
                        "job": s["job"],
                        "build": s["build"],
                        "bin_feb2026": int(
                            bool(s["build"])
                            and s["build"].startswith("Feb")
                            and s["build"].endswith("2026")
                        ),
                        "rh_on": s["rh_on_js"],
                        "rh_on_log": 0 if s["rh_warn_in_err"] else 1,
                        "humid_kind": s["humid_kind"],
                        "run_ok": s["ok"],
                        "tree_window": win,
                        "tree_year_complete": y in yc,
                        "pair_ok_raw": bool(pair_ok),
                        "clim_scen": "Historical"
                        if (hist_last is not None and y <= hist_last)
                        else scen,
                        "clim_recycled": recycled_y,
                        "clim_year": rec_map.get((seed, y)) if recycled_y else y,
                    }
                )
    seg = pl.DataFrame(rows, infer_schema_length=None).sort(["gcm", "scen", "seed", "Year"])
    seg = seg.with_columns(
        pl.col("Year").cast(pl.Int32),
        pl.col("seed").cast(pl.Int32),
        pl.col("clim_year").cast(pl.Int32),
    )
    return apply_owner_exclusion(seg)


def apply_owner_exclusion(seg: pl.DataFrame) -> pl.DataFrame:
    """chain_clean(Y) = min of rh_on over the trajectory's years <= Y (the restart chain is continuous, so a
    wrongly configured segment contaminates everything simulated after it). pair_ok (y -> y+1) is kept only when
    the year y+1 is clean; the pre-exclusion value stays in pair_ok_raw for provenance."""
    k = ["gcm", "scen", "seed"]
    seg = seg.sort(k + ["Year"]).with_columns(
        (pl.col("rh_on").cum_min().over(k) == 1).alias("chain_clean")
    )
    nxt = pl.col("chain_clean").shift(-1).over(k).fill_null(False)
    return seg.with_columns(
        (~pl.col("chain_clean")).alias("excluded"),
        pl.when(pl.col("chain_clean"))
        .then(pl.lit(None, dtype=pl.String))
        .when(pl.col("rh_on") == 0)
        .then(pl.lit(EXCL_REASON_OWN))
        .otherwise(pl.lit(EXCL_REASON_UP))
        .alias("exclusion_reason"),
        (pl.col("pair_ok_raw") & nxt).alias("pair_ok"),
        # what the year may be used for, in plain words
        pl.when(~pl.col("chain_clean"))
        .then(pl.lit("excluded"))
        .when(pl.col("tree_year_complete"))
        .then(pl.lit("trees"))
        .otherwise(pl.lit("no_tree_table"))
        .alias("use"),
    )


def mark_members(mem: pl.DataFrame, seg: pl.DataFrame) -> pl.DataFrame:
    """A member window is EXCLUDED when any year it covers is not chain_clean in segments (owner decision
    2026-10-01). usable_pair_years keeps only pairs whose target year is clean (so an excluded window has
    none); the pre-exclusion list stays in usable_pair_years_raw."""
    clean = {
        (r["gcm"], r["scen"], r["seed"], r["Year"]): (r["chain_clean"], r["exclusion_reason"])
        for r in seg.iter_rows(named=True)
    }
    exc, why, pairs = [], [], []
    for r in mem.iter_rows(named=True):
        ys = range(r["json_firstyear"], r["json_lastyear"] + 1)
        st = [clean.get((r["gcm"], r["scen"], r["seed"], y)) for y in ys]
        if any(v is None for v in st):
            raise RuntimeError(f"member {r['member']}: years missing from segments")
        bad = [v[1] for v in st if not v[0]]
        exc.append(bool(bad))
        why.append(sorted(set(bad))[0] if bad else None)
        # the target year y+1 of every listed pair lies on this member's own trajectory (for w2015 the first pair,
        # 2014 -> 2015, starts in the same-seed Historical run but its target year is the ssp's)
        pairs.append(
            [
                y
                for y in r["usable_pair_years"]
                if not bad and clean.get((r["gcm"], r["scen"], r["seed"], y + 1), (False,))[0]
            ]
        )
    return mem.with_columns(
        pl.col("usable_pair_years").alias("usable_pair_years_raw"),
        pl.col("n_pair_years").alias("n_pair_years_raw"),
        pl.Series("excluded", exc, dtype=pl.Boolean),
        pl.Series("exclusion_reason", why, dtype=pl.String),
        pl.Series("usable_pair_years", pairs, dtype=pl.List(pl.Int32)),
    ).with_columns(
        pl.col("usable_pair_years").list.len().alias("n_pair_years"),
        pl.when(pl.col("excluded"))
        .then(pl.lit(OWNER_DECISION))
        .otherwise(None)
        .alias("excluded_by"),
    )


def build_folds(block_map: str, cell_static: str, k: int, dev_mod: int) -> pl.DataFrame:
    bm = pl.read_parquet(block_map).select(
        pl.col("Cell").cast(pl.Int32), pl.col("block").cast(pl.Int32)
    )
    bm = bm.with_columns((pl.col("Cell") % dev_mod == 0).alias("is_dev"))
    stats = (
        bm.group_by("block")
        .agg(pl.col("is_dev").sum().alias("n_dev"), pl.len().alias("n_all"))
        .sort(["n_dev", "n_all", "block"], descending=[True, True, False])
    )
    load = {f: [0, 0] for f in range(1, k + 1)}
    assign = {}
    for r in stats.iter_rows(named=True):
        f = min(load, key=lambda f: (load[f][0], load[f][1], f))
        assign[r["block"]] = f
        load[f][0] += r["n_dev"]
        load[f][1] += r["n_all"]
    fold = pl.DataFrame(
        {"block": list(assign), "fold": list(assign.values())},
        schema={"block": pl.Int32, "fold": pl.Int8},
    )
    cs = pl.read_parquet(cell_static).select(pl.col("Cell").cast(pl.Int32), "lon", "lat")
    return bm.join(fold, on="block", how="left").join(cs, on="Cell", how="left").sort("Cell")


def hash_u64(s: str) -> int:
    return int.from_bytes(hashlib.sha256(s.encode()).digest()[:8], "big")


def build_blind_yearmap(
    gcms: list[str], reps: int, base0: int, base1: int, y0: int, y1: int, salt: str
) -> pl.DataFrame:
    nb = base1 - base0 + 1
    rows = [
        {"gcm": g, "rep": r, "Year": y, "src_year": base0 + hash_u64(f"{salt}|{g}|r{r}|{y}") % nb}
        for g in gcms
        for r in range(1, reps + 1)
        for y in range(y0, y1 + 1)
    ]
    return (
        pl.DataFrame(
            rows, schema={"gcm": pl.String, "rep": pl.Int8, "Year": pl.Int32, "src_year": pl.Int32}
        )
        .with_columns(pl.lit("Historical").alias("src_scen"))
        .sort(["gcm", "rep", "Year"])
    )


# Split definitions (data, not code). Source: round-1 comparison_protocol (DEV-A, DEV-B) and the binding critic
# amendments: gap 2 (a same-GCM scenario hold-out is scored against the OTHER seed, because the training seed's
# Historical history is training data), gap 7 (DEV-A2 = same-binary MPI scenario hold-out; ssp245 is a
# 'scenario + binary' hold-out and never enters an H4 contrast), gap 1 (cells: folds 1-4 train, fold 5 held out,
# or cross-fit one model per fold so every block is scored out-of-place).
SPLITS = {
    "DEV-A": {
        "train_gcm": "MPI-ESM1-2-HR",
        "train_seed": 1,
        "train_scens": ["Historical", "ssp126", "ssp370"],
        "same_binary_only": False,
        "test_other_gcm": True,
    },
    "DEV-A2": {
        "train_gcm": "MPI-ESM1-2-HR",
        "train_seed": 1,
        "train_scens": ["Historical", "ssp126"],
        "same_binary_only": True,
        "test_other_gcm": False,
    },
    "DEV-B": {
        "train_gcm": "ACCESS-CM2",
        "train_seed": 1,
        "train_scens": ["Historical", "ssp126", "ssp370"],
        "same_binary_only": False,
        "test_other_gcm": True,
    },
}
# Owner decision 2026-10-01: only the clean 1985-2044 trajectory is truth. w2071/w3071 stay listed in splits so a
# consumer SEES them, but with role "excluded_rh_off" and never as train/test/score/start/null/calibration.
TRAIN_WINS = ("h1985", "w2015")
SCORE_WINS = ["h1985", "w2015"]
ALL_WINS = ("h1985", "w2015", "w2071", "w3071")


def build_splits(mem: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """splits.parquet: one row per (split, TRAJECTORY gcm/scen/seed, window); the h1985 window of an ssp
    trajectory is the same-seed Historical member (src_member), so training h1985 pairs appear under every
    training ssp trajectory -- dedupe on src_member. test_pairs.parquet: one row per (split, test trajectory)."""
    mrow = {(r["gcm"], r["scen"], r["seed"], r["win"]): r for r in mem.iter_rows(named=True)}
    seeds = sorted(mem["seed"].unique().to_list())
    rows, pairs = [], []
    for split, D in SPLITS.items():
        tg, ts = D["train_gcm"], D["train_seed"]
        other = [s for s in seeds if s != ts]
        train_build = {
            mrow[k]["build"] for k in mrow if k[0] == tg and k[2] == ts and k[1] in D["train_scens"]
        }
        for g, sc in sorted({(k[0], k[1]) for k in mrow if k[1] != "Historical"}):
            traj_build = {mrow[k]["build"] for k in mrow if k[0] == g and k[1] == sc}
            bin_diff = bool(traj_build - train_build)
            if g == tg and sc in D["train_scens"]:
                kind, truth = "train", None
            elif g == tg:
                kind, truth = "scenario hold-out", other[0]
            elif D["test_other_gcm"]:
                kind, truth = "GCM hold-out", ts
            else:
                kind, truth = "excluded", None
            if kind != "train" and kind != "excluded" and D["same_binary_only"] and bin_diff:
                kind, truth = "excluded", None
            if kind not in ("train", "excluded"):
                label = kind + (" + binary (different C build)" if bin_diff else "")
                ref = [s for s in seeds if s != truth][0]
                note = f"truth C = seed {truth}, R = seed {ref}"
                if g == tg:
                    note += "; the training seed's Historical history is in training (critic gap 2)"
                pairs.append(
                    {
                        "split": split,
                        "gcm": g,
                        "scen": sc,
                        "kind": label,
                        "truth_seed": truth,
                        "ref_seed": [s for s in seeds if s != truth][0],
                        "binary_differs": bin_diff,
                        "h4_contrast_ok": not bin_diff,
                        "start_member_1985": f"{g}_Historical_s{truth}_h1985",
                        "start_member_2014": f"{g}_Historical_s{truth}_h1985",
                        "score_windows": SCORE_WINS,
                        "start_years": [
                            1985,
                            2014,
                        ],  # headline 1985 -> 2044; secondary 2014 -> 2044
                        "free_run_last_year": 2044,
                        # optional continuation, checked only on cell aggregates (SH12), no tree table
                        "aggregate_check_last_year": 2070,
                        "note": note,
                    }
                )
            for sd in seeds:
                for w in ALL_WINS:
                    src_scen = "Historical" if w == "h1985" else sc
                    r = mrow.get((g, src_scen, sd, w))
                    if r is None:
                        continue
                    if kind == "train":
                        role = "train" if sd == ts else "train_twin"
                    elif kind == "excluded":
                        role = "excluded"
                    else:
                        role = "test_truth" if sd == truth else "test_ref"
                    if w == "w3071" and role != "excluded":
                        role = "equilibrium_check_only"
                    if r["truncated"]:
                        role = "excluded_truncated"
                    if r["excluded"]:  # owner decision overrides every other role
                        role = "excluded_rh_off"
                    if role == "train" and w not in TRAIN_WINS:
                        role = "excluded"
                    rows.append(
                        {
                            "split": split,
                            "gcm": g,
                            "scen": sc,
                            "seed": sd,
                            "win": w,
                            "src_member": r["member"],
                            "role": role,
                            "h4_contrast_ok": (kind == "train" and not bin_diff)
                            or (kind not in ("train", "excluded") and not bin_diff),
                            "kind": kind,
                            "excluded_by": r["excluded_by"],
                        }
                    )
    spl = pl.DataFrame(rows, infer_schema_length=None).sort(["split", "gcm", "scen", "seed", "win"])
    tp = pl.DataFrame(pairs, infer_schema_length=None).sort(["split", "gcm", "scen"])
    return spl, tp


def build_contrasts(spl: pl.DataFrame, mem: pl.DataFrame) -> pl.DataFrame:
    """The RESPONSE statistics the owner decision makes primary, one row per (split, gcm, statistic):
      between_scen   X(a, w2015) - X(b, w2015) at fixed GCM and seed (a in {ssp370, ssp245}, b = ssp126) --
                     PRIMARY: both legs share the binary-independent CO2 file and the humidity setting.
      change         X(a, w2015) - X(a, h1985), same seed (the early-century warming change; secondary).
    truth_seed / ref_seed: the seed scored as truth and the one that gives the two-seed tolerance. For a GCM that
    is held out in the split, truth = the test pair's truth seed; for the training GCM the truth is the OTHER seed
    (its seed-1 history is training data), and the row is labelled in-sample-climate. binary_mixed = a leg ran
    the Feb-2026 build (ssp245): such a row is reported in its own line and never used as H4's reference."""
    ok = {
        r["member"]: (not r["excluded"]) and (not r["truncated"]) for r in mem.iter_rows(named=True)
    }
    binf = {(r["gcm"], r["scen"]): r["bin_feb2026"] for r in mem.iter_rows(named=True)}
    rows = []
    for split in sorted(spl["split"].unique().to_list()):
        sp = spl.filter(pl.col("split") == split)
        for g in sorted(sp["gcm"].unique().to_list()):
            sg = sp.filter(pl.col("gcm") == g)
            kinds = dict(sg.select("scen", "kind").unique().iter_rows())
            train_gcm = "train" in kinds.values()
            seeds = sorted(sg["seed"].unique().to_list())
            if train_gcm:
                truth = [sd for sd in seeds if sd != SPLITS[split]["train_seed"]][0]
            else:
                truth = SPLITS[split]["train_seed"]
            ref = [sd for sd in seeds if sd != truth][0]
            specs = [("between_scen", a, "w2015", "ssp126", "w2015") for a in ("ssp370", "ssp245")]
            specs += [("change", a, "w2015", a, "h1985") for a in ("ssp126", "ssp245", "ssp370")]
            for stat, a, wa, b, wb in specs:
                if a not in kinds or b not in kinds:
                    continue
                legs = [(a, wa), (b, wb)]
                members = {
                    sd: [f"{g}_{'Historical' if w == 'h1985' else sc}_s{sd}_{w}" for sc, w in legs]
                    for sd in (truth, ref)
                }
                avail = all(ok.get(m, False) for ms in members.values() for m in ms)
                leg_kinds = sorted({kinds[a], kinds[b]})
                if train_gcm and leg_kinds == ["train"]:
                    status = "in-sample climate (training scenarios), scored on the other seed"
                elif any(k == "excluded" for k in leg_kinds):
                    status = "not available in this split (a leg is excluded)"
                elif "train" in leg_kinds:
                    status = "one leg is a training scenario"
                else:
                    status = "held out (both legs)"
                mixed = bool(binf.get((g, a), 0) or binf.get((g, b), 0))
                rows.append(
                    {
                        "split": split,
                        "gcm": g,
                        "stat": stat,
                        "a_scen": a,
                        "a_win": wa,
                        "b_scen": b,
                        "b_win": wb,
                        "truth_seed": truth,
                        "ref_seed": ref,
                        "truth_members": members[truth],
                        "ref_members": members[ref],
                        "available": avail and status.startswith(("held", "in-sample", "one")),
                        "status": status,
                        "binary_mixed": mixed,
                        "primary": stat == "between_scen" and not mixed,
                        "h4_reference_ok": stat == "between_scen"
                        and not mixed
                        and status == "held out (both legs)",
                    }
                )
    return pl.DataFrame(rows, infer_schema_length=None).sort(["split", "gcm", "stat", "a_scen"])


# ----------------------------------------------------------------------------------------------- gates
def gates(att, mem, seg, folds, ym, spl, tp, args) -> dict:
    G = {}

    def put(name, ok, **kw):
        G[name] = {"pass": bool(ok), **kw}
        log(f"GATE {name}: {'PASS' if ok else 'FAIL'} {json.dumps(kw, default=str)[:600]}")

    # folds
    nb = folds["block"].n_unique()
    bf = folds.group_by("block").agg(pl.col("fold").n_unique().alias("nf"))
    per_fold = (
        folds.group_by("fold")
        .agg(
            pl.len().alias("cells"),
            pl.col("is_dev").sum().alias("dev_cells"),
            pl.col("block").n_unique().alias("blocks"),
            pl.col("lat").mean().alias("lat_mean"),
        )
        .sort("fold")
    )
    put(
        "folds_cells_blocks",
        folds.height == folds["Cell"].n_unique()
        and (args.expect_cells is None or folds.height == args.expect_cells)
        and (args.expect_blocks is None or nb == args.expect_blocks)
        and bf["nf"].max() == 1
        and folds["fold"].null_count() == 0,
        cells=folds.height,
        blocks=nb,
        dev_cells=int(folds["is_dev"].sum()),
        per_fold=per_fold.to_dicts(),
    )
    # fold climate balance (diagnostic): per-fold mean of each GCM's 1985-2014 cell climatology tmean
    cs = pl.read_parquet(args.cell_static)
    tcols = [c for c in cs.columns if c.startswith("c8514_") and c.endswith("_tmean_ann")]
    fb = (
        folds.join(cs.select(pl.col("Cell").cast(pl.Int32), *tcols), on="Cell")
        .group_by("fold")
        .agg(
            *[pl.col(c).cast(pl.Float64).mean().alias(c) for c in tcols],
            *[
                pl.col(c).cast(pl.Float64).filter(pl.col("is_dev")).mean().alias(c + "_dev")
                for c in tcols
            ],
        )
        .sort("fold")
    )
    G["_fold_climate_diag"] = fb.to_dicts()
    log("fold climate:", fb.to_dicts())
    # splits: what must never be trained on, and the test pairs
    tr = spl.filter(pl.col("role") == "train")
    bad = []
    for split, D in SPLITS.items():
        t = tr.filter(pl.col("split") == split)
        bad += t.filter(
            (pl.col("seed") != D["train_seed"])
            | (pl.col("gcm") != D["train_gcm"])
            | ~pl.col("scen").is_in(D["train_scens"])
            | ~pl.col("win").is_in(list(TRAIN_WINS))
        )["src_member"].to_list()
    trained_bins = set(
        mem.join(tr.select("src_member").unique(), left_on="member", right_on="src_member")["build"]
    )
    put(
        "splits",
        not bad and len(trained_bins) == 1,
        violations=bad,
        trained_builds=sorted(trained_bins),
        train_members={
            k: sorted(set(tr.filter(pl.col("split") == k)["src_member"].to_list())) for k in SPLITS
        },
        test_pairs=tp.select(
            "split", "gcm", "scen", "kind", "truth_seed", "h4_contrast_ok"
        ).to_dicts(),
    )
    # rh_on
    s_ssp = seg.filter(pl.col("src_scen") != "Historical")
    off_cfg = s_ssp.filter(pl.col("cfg").is_in(["2100", "3100"]))
    on_cfg = seg.filter(~pl.col("cfg").is_in(["2100", "3100"]))
    n_ssp_members = s_ssp.select("gcm", "scen", "seed").unique().height
    off_segs = off_cfg.select("gcm", "scen", "seed", "cfg").unique().height
    put(
        "rh_on_flags",
        off_cfg["rh_on"].max() == 0
        and on_cfg["rh_on"].min() == 1
        and (seg["rh_on"] == seg["rh_on_log"]).all()
        and off_segs == 2 * n_ssp_members,
        ssp_members=n_ssp_members,
        rh_off_segments=off_segs,
        rh_off_rows=off_cfg.height,
        rh_on_rows=on_cfg.height,
        js_vs_errlog_disagree=int((seg["rh_on"] != seg["rh_on_log"]).sum()),
    )
    # binary flag
    b = seg.select("src_scen", "bin_feb2026").unique()
    put(
        "bin_feb2026_flags",
        set(b.filter(pl.col("src_scen") == "ssp245")["bin_feb2026"].to_list()) == {1}
        and set(b.filter(pl.col("src_scen") != "ssp245")["bin_feb2026"].to_list()) == {0},
        builds=seg.group_by("src_scen", "build").len().sort(["src_scen", "build"]).to_dicts(),
    )
    # truncation
    tr = mem.filter(pl.col("truncated"))["member"].to_list()
    put(
        "truncation",
        tr == ["MPI-ESM1-2-HR_ssp370_s2_w3071"],
        truncated=tr,
        n_members=mem.height,
        pairs_of_truncated=mem.filter(pl.col("truncated"))["usable_pair_years"].to_list(),
    )
    # writer attribution
    put(
        "writer_attribution",
        mem["writer_job"].null_count() == 0
        and mem["writer_is_final"].all()
        and mem.filter(~pl.col("truncated"))["writer_ok"].all(),
        not_final=mem.filter(~pl.col("writer_is_final"))["member"].to_list(),
        writer_failed=mem.filter(~pl.col("writer_ok").fill_null(False))["member"].to_list(),
    )
    # restart chain continuity: each final segment starts from the previous segment's restart (same seed)
    fin = att.filter(pl.col("is_final") & pl.col("cfg").is_in(list(SEG_OF_TAG)))
    bad = []
    prev_of = {
        "2044": ("Historical", "hist"),
        "2070": (None, "2044"),
        "2100": (None, "2070"),
        "3070": (None, "2100"),
        "3100": (None, "3070"),
    }
    for r in fin.filter(pl.col("cfg") != "hist").iter_rows(named=True):
        ps, pc = prev_of[r["cfg"]]
        p = fin.filter(
            (pl.col("gcm") == r["gcm"])
            & (pl.col("scen") == (ps or r["scen"]))
            & (pl.col("seed") == r["seed"])
            & (pl.col("cfg") == pc)
        )
        if p.height != 1 or p["restart_written"][0] != r["restart_from"] or not p["ok"][0]:
            bad.append((r["gcm"], r["scen"], r["seed"], r["cfg"]))
    spin = att.filter(pl.col("cfg") == "hist_spinup")
    seeds_ok = all(r["random_seed_log"] == r["seed"] for r in spin.iter_rows(named=True))
    put(
        "restart_chain",
        not bad and seeds_ok,
        broken=bad,
        spinup_seed_matches_dir=seeds_ok,
        n_final_segments=fin.height,
        npatch=sorted(set(fin["npatch"].drop_nulls().to_list())),
    )
    # segments key + continuity of years + pair semantics
    nkey = seg.select("gcm", "scen", "seed", "Year").n_unique()
    gaps = (
        seg.sort(["gcm", "scen", "seed", "Year"])
        .with_columns(pl.col("Year").diff().over(["gcm", "scen", "seed"]).alias("dy"))
        .filter(pl.col("dy").is_not_null() & (pl.col("dy") != 1))
        .height
    )
    cross = seg.filter(
        pl.col("pair_ok") & pl.col("Year").is_in([2044, 2070, 2100, 3070, 3100])
    ).height
    put(
        "segments_keys",
        nkey == seg.height and gaps == 0 and cross == 0 and seg["clim_year"].null_count() == 0,
        rows=seg.height,
        year_gaps=gaps,
        pair_ok_across_gap=cross,
        pair_ok_per_traj=seg.filter(pl.col("pair_ok"))
        .group_by("gcm", "scen", "seed")
        .len()
        .sort(["gcm", "scen", "seed"])
        .to_dicts(),
    )
    # blind year map determinism (same function, fresh call) + coverage
    ym2 = build_blind_yearmap(*args._ym_args)
    reps = ym["rep"].unique().sort().to_list()
    diff_frac = []
    for g in ym["gcm"].unique().sort().to_list():
        for i in reps:
            for j in reps:
                if i < j:
                    a = ym.filter((pl.col("gcm") == g) & (pl.col("rep") == i))["src_year"]
                    bb = ym.filter((pl.col("gcm") == g) & (pl.col("rep") == j))["src_year"]
                    diff_frac.append(float((a != bb).mean()))
    w = ym.filter(pl.col("Year").is_between(1985, 2070))
    cover = (
        w.with_columns((pl.col("Year") // 30).alias("_"))
        .group_by("gcm", "rep")
        .agg(
            pl.col("src_year").n_unique().alias("distinct"),
            pl.col("src_year").mean().alias("mean_src"),
        )
        .sort(["gcm", "rep"])
    )
    put(
        "blind_yearmap",
        ym.equals(ym2)
        and min(diff_frac) > 0.8
        and ym["src_year"].min() >= args.base0
        and ym["src_year"].max() <= args.base1,
        rerun_identical=ym.equals(ym2),
        min_pairwise_rep_diff=min(diff_frac),
        coverage_1985_2070=cover.to_dicts(),
    )
    return G


def gates_owner_exclusion(att, mem, seg, ym, spl, tp, con, args) -> dict:
    """Gates for the owner decision of 2026-10-01 (only the clean 1985-2044 truth is used)."""
    G = {}

    def put(name, ok, **kw):
        G[name] = {"pass": bool(ok), **kw}
        log(f"GATE {name}: {'PASS' if ok else 'FAIL'} {json.dumps(kw, default=str)[:600]}")

    # (1) third independent reading: the humidity input the C actually printed in each final segment's log
    fin = att.filter(pl.col("is_final") & pl.col("cfg").is_in(list(SEG_OF_TAG)))
    exp = pl.when(pl.col("rh_on_js") == 1).then(pl.lit("rhumid")).otherwise(pl.lit("humid"))
    mis = fin.filter(pl.col("humid_kind").is_null() | (pl.col("humid_kind") != exp))
    by_cfg = (
        fin.group_by("cfg", "humid_kind")
        .agg(
            pl.len().alias("n"),
            pl.col("humid_file").str.split("/").list.last().unique().sort().alias("files"),
        )
        .sort(["cfg", "humid_kind"])
    )
    put(
        "humid_input_vs_flag",
        mis.height == 0 and fin.height > 0,
        final_segments=fin.height,
        mismatches=mis.select("gcm", "scen", "seed", "cfg", "humid_kind", "rh_on_js").to_dicts(),
        by_cfg=by_cfg.to_dicts(),
    )
    # (2) exclusion is data-derived: first unclean year per trajectory, and the excluded member set
    first_bad = (
        seg.filter(~pl.col("chain_clean"))
        .group_by("gcm", "scen", "seed")
        .agg(pl.col("Year").min().alias("first_unclean"))
        .sort(["gcm", "scen", "seed"])
    )
    trajs = seg.select("gcm", "scen", "seed").unique()
    n_ssp = trajs.filter(pl.col("scen") != "Historical").height
    gap_clean = seg.filter(
        (pl.col("scen") != "Historical") & pl.col("Year").is_between(2045, 2070)
    )["chain_clean"].all()
    excl = sorted(mem.filter(pl.col("excluded"))["member"].to_list())
    want = sorted(mem.filter(pl.col("win").is_in(["w2071", "w3071"]))["member"].to_list())
    kept = mem.filter(~pl.col("excluded")).group_by("win").len().sort("win").to_dicts()
    put(
        "owner_exclusion_members",
        excl == want
        and first_bad.height == n_ssp
        and set(first_bad["first_unclean"].to_list()) == {2071}
        and first_bad.filter(pl.col("scen") == "Historical").height == 0
        and gap_clean,
        excluded_members=len(excl),
        excluded_equals_all_w2071_w3071=excl == want,
        first_unclean_year_values=sorted(set(first_bad["first_unclean"].to_list())),
        trajectories_with_unclean_years=first_bad.height,
        ssp_trajectories=n_ssp,
        years_2045_2070_clean=gap_clean,
        kept_by_window=kept,
        reasons=mem.filter(pl.col("excluded")).group_by("win", "exclusion_reason").len().to_dicts(),
    )
    # (3) no excluded window can be reached through any role, test pair or contrast
    live_roles = ["train", "train_twin", "test_truth", "test_ref", "equilibrium_check_only"]
    leak = spl.filter(pl.col("role").is_in(live_roles) & ~pl.col("win").is_in(SCORE_WINS))
    excl_set = set(excl)
    leak2 = spl.filter(
        pl.col("role").is_in(live_roles) & pl.col("src_member").is_in(list(excl_set))
    )
    tp_bad = [r for r in tp.iter_rows(named=True) if not set(r["score_windows"]) <= set(SCORE_WINS)]
    con_bad = con.filter(
        ~pl.col("a_win").is_in(SCORE_WINS)
        | ~pl.col("b_win").is_in(SCORE_WINS)
        | (
            pl.col("available")
            & (
                pl.col("truth_members").list.eval(pl.element().is_in(list(excl_set))).list.any()
                | pl.col("ref_members").list.eval(pl.element().is_in(list(excl_set))).list.any()
            )
        )
    )
    put(
        "owner_exclusion_roles",
        leak.height == 0 and leak2.height == 0 and not tp_bad and con_bad.height == 0,
        role_counts=spl.group_by("win", "role").len().sort(["win", "role"]).to_dicts(),
        leaks=leak.height + leak2.height,
        test_pairs_bad=len(tp_bad),
        contrasts_bad=con_bad.height,
    )
    # (4) one-step pairs only inside the clean years
    po = seg.filter(pl.col("pair_ok"))
    per = po.group_by("gcm", "scen", "seed").agg(
        pl.len().alias("n"), pl.col("Year").min().alias("y0"), pl.col("Year").max().alias("y1")
    )
    ssp_n = set(per.filter(pl.col("scen") != "Historical")["n"].to_list())
    hist_n = set(per.filter(pl.col("scen") == "Historical")["n"].to_list())
    put(
        "owner_exclusion_pairs",
        po.filter(pl.col("excluded")).height == 0
        and (po["Year"].max() or 0) <= 2043
        and ssp_n == {59}
        and hist_n == {29}
        and mem.filter(pl.col("excluded"))["n_pair_years"].max() == 0,
        pairs_per_ssp_trajectory=sorted(ssp_n),
        pairs_per_hist_trajectory=sorted(hist_n),
        last_pair_start_year=po["Year"].max(),
        raw_pairs_dropped=int(seg["pair_ok_raw"].sum() - seg["pair_ok"].sum()),
        member_pairs_kept=int(mem["n_pair_years"].sum()),
        member_pairs_raw=int(mem["n_pair_years_raw"].sum()),
    )
    # (5) blind map: ends at the last clean year; rows kept identical to the pre-decision map for 1985-2070
    old_p = f"{args.out}/_superseded_v1_pre_owner_exclusion/blind_yearmap.parquet"
    same = None
    if os.path.exists(old_p):
        old = pl.read_parquet(old_p).filter(pl.col("Year") <= args.ym_y1)
        same = old.sort(["gcm", "rep", "Year"]).equals(ym.sort(["gcm", "rep", "Year"]))
    put(
        "blind_yearmap_owner_range",
        ym["Year"].max() == args.ym_y1 and ym["Year"].min() == args.ym_y0 and same is not False,
        year_range=[ym["Year"].min(), ym["Year"].max()],
        identical_to_v1_rows=same,
    )
    # (6) contrasts present for every split's held-out GCM (binding row) -- descriptive
    put(
        "contrasts",
        con.filter(pl.col("h4_reference_ok") & pl.col("available")).height > 0,
        rows=con.height,
        h4_reference_rows=con.filter(pl.col("h4_reference_ok"))
        .select("split", "gcm", "a_scen", "b_scen", "truth_seed")
        .to_dicts(),
        primary_rows=con.filter(pl.col("primary"))
        .select("split", "gcm", "a_scen", "status")
        .to_dicts(),
    )
    return G


# ----------------------------------------------------------------------------------------------- main
def build_all(args):
    att = build_attempts(args.prod)
    log("attempts:", att.height)
    mem = build_members(args.xde, att, args.dev_mod)
    log("members:", mem.height)
    seg = build_segments(att, mem, args.xde, args.recycled)
    log("segments:", seg.height)
    mem = mark_members(mem, seg)
    log("members excluded:", mem.filter(pl.col("excluded"))["member"].to_list())
    folds = build_folds(args.block_map, args.cell_static, args.k, args.dev_mod)
    gcms = sorted(mem["gcm"].unique().to_list())
    args._ym_args = (gcms, args.reps, args.base0, args.base1, args.ym_y0, args.ym_y1, args.salt)
    ym = build_blind_yearmap(*args._ym_args)
    spl, tp = build_splits(mem)
    con = build_contrasts(spl, mem)
    return att, mem, seg, folds, ym, spl, tp, con


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["build", "check"])
    ap.add_argument("--prod", default=DEF_PROD)
    ap.add_argument("--xde", default=DEF_XDE)
    ap.add_argument("--out", default=None)
    ap.add_argument("--block-map", default=None)
    ap.add_argument("--cell-static", default=None)
    ap.add_argument("--recycled", default=None)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--dev-mod", type=int, default=10)
    ap.add_argument("--reps", type=int, default=4)
    ap.add_argument("--base0", type=int, default=1985)
    ap.add_argument("--base1", type=int, default=2014)
    ap.add_argument("--ym-y0", type=int, default=1985)
    # 2070 = last clean simulated year (the optional aggregate-checked continuation); was 3100 before the owner
    # decision. Rows 1985-2070 are unchanged (same salt, per-(gcm, rep, year) hash).
    ap.add_argument("--ym-y1", type=int, default=2070)
    ap.add_argument("--salt", default="X_de/SH0/blind_yearmap/v1")
    ap.add_argument("--expect-cells", type=int, default=None)
    ap.add_argument("--expect-blocks", type=int, default=None)
    args = ap.parse_args()
    args.out = args.out or f"{args.xde}/shared/registry"
    args.block_map = args.block_map or f"{args.xde}/reference/block/map.parquet"
    args.cell_static = args.cell_static or f"{args.xde}/climate/cell_static.parquet"
    args.recycled = (
        args.recycled or f"{args.xde}/climate/recycled_yearmap_2101_3100_by_seed.parquet"
    )

    att, mem, seg, folds, ym, spl, tp, con = build_all(args)
    tables = {
        "attempts": att,
        "members": mem,
        "segments": seg,
        "folds": folds,
        "blind_yearmap": ym,
        "splits": spl,
        "test_pairs": tp,
        "contrasts": con,
    }
    if args.mode == "check":
        res = {}
        for k, df in tables.items():
            disk = pl.read_parquet(f"{args.out}/{k}.parquet")
            cols = [c for c in df.columns if c not in ("job_start", "job_end", "out_mtime")]
            res[k] = disk.select(cols).equals(df.select(cols))
            log(f"CHECK {k}: {'identical' if res[k] else 'DIFFERENT'}")
        json.dump(res, open(f"{args.out}/_check.json", "w"), indent=1)
        sys.exit(0 if all(res.values()) else 1)

    os.makedirs(args.out, exist_ok=True)
    for k, df in tables.items():
        df.write_parquet(f"{args.out}/{k}.parquet")
    G = gates(att, mem, seg, folds, ym, spl, tp, args)
    G.update(gates_owner_exclusion(att, mem, seg, ym, spl, tp, con, args))
    G["_meta"] = {
        "script": os.path.abspath(__file__),
        "repo": REPO,
        "built": dt.datetime.now().isoformat(),
        "args": {k: v for k, v in vars(args).items() if not k.startswith("_")},
        "sha256": {
            k: hashlib.sha256(open(f"{args.out}/{k}.parquet", "rb").read()).hexdigest()
            for k in tables
        },
    }
    json.dump(G, open(f"{args.out}/_gates.json", "w"), indent=1, default=str)
    ok = all(v["pass"] for k, v in G.items() if not k.startswith("_"))
    log("ALL GATES", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
