#!/usr/bin/env python3
"""build_panel_yearly_v2.py -- the panel's yearly per-cell tables, version 2: the quantities the emulator does NOT
emit yet (owner 2026-10-22: tree height, whole trait distributions for biodiversity indices, the ACTUAL rooting depth,
mortality), built from the same per-tree tables as xpanel/yearly/ (explore_panel_lstm.stage_yearly) and on the same
population (living trees, tree types 0-6, height >= 5 m = explore_de_reference.living).

Stage `yearly` -> xpanel/yearly2/m<k>_<leg>.parquet, one row per (Cell, Year) of the leg's census:
  n_living, agb_sum, n_t0..n_t6               as version 1 (gated equal to it)
  <v>_p01 .. <v>_p99, <v>_mean                 v in SLA, Wooddens, D95max, minwscal, Height, agb, D95, Age, Longevity
                                               (D95 = the ACTUAL 95 % rooting depth, cm; Age, Longevity added)
  n_dead                                       trees (types 0-6, height >= 5 m) that died this year (isdead == 1)
  exp_dead                                     sum over the same at-risk trees (living + dead) of the C's own yearly
                                               death probability `mort` (clipped to [0, 1]) = the expected CHANCE deaths
  n_dead_t0..n_dead_t6                         deaths by tree type
  -> death rate = n_dead / (n_living + n_dead); excess deaths (hard kills: leaf carbon below a sapling's or five bad
     years in a row, and fire) = n_dead - exp_dead (ADR 0356 sec. 7, 0357).
Stage `rosters` -> <ROSTER>/m<k>_<leg>.parquet: every living tree (same population) in the years 2019 (hist) or
  2020, 2025, ..., 2100 (future legs): Cell, Year, Patch, Type, Height, agb, SLA, Wooddens, D95max, minwscal, D95, Age.
  The per-tree basis of the biodiversity indices and of the joint-distribution arms.
Gate (written to yearly2/_gate_m<k>_<leg>.json): n_living / agb_sum / n_t* equal to version 1, SLA/Height medians
  within float tolerance, the share of `mort` values outside [0, 1].
Stage `npp` -> xpanel/yearly2_npp/m<k>_<leg>.parquet: per (Cell, Year) the yearly NPP of the trees >= 5 m alive
  during the year (living + dying): npp_sum, npp_per_tree, share_npp_neg (ADR 0363 sec. 8, the oracle arm BMN).
Usage: build_panel_yearly_v2.py yearly|rosters|npp --part I --nparts N
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_reference as R  # noqa: E402
import explore_panel_prep as PP  # noqa: E402

YEARLY1 = os.path.join(PP.OUT, "yearly")
YEARLY2 = os.path.join(PP.OUT, "yearly2")
ROSTER = "/p/projects/reformit/Jamir/esm_land_emulator_data/xpanel_rosters"
TRAITS2 = ["SLA", "Wooddens", "D95max", "minwscal", "Height", "agb", "D95", "Age", "Longevity"]
ROSTER_COLS = ["Patch", "Type", "Height", "agb", "SLA", "Wooddens", "D95max", "minwscal", "D95", "Age"]
PS = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
PN = ["p01", "p05", "p10", "p25", "p50", "p75", "p90", "p95", "p99"]
PFTS = list(range(7))
LEGS = ["hist", *PP.SLEGS, *PP.NEW_SLEGS, "ctl_obs"]
ROSTER_YEARS = list(range(2020, 2101, 5))


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def jobs() -> list[tuple[int, str]]:
    return [(m, lg) for m in PP.MEMBERS for lg in LEGS if PP.table_dir(m, lg) is not None]


def scan(m: int, lg: str):
    td = PP.table_dir(m, lg)
    y0, y1 = (2000, 2019) if lg == "hist" else (2020, 2100)
    blocks = list(range(105)) if lg == "hist" else PP.complete_blocks(m, lg)
    cl = PP.cells().filter(pl.col("block").is_in(blocks))["Cell"].to_list()
    lf = (pl.scan_parquet(os.path.join(td, "ind.parquet"))
          .filter(pl.col("Year").is_between(y0, y1) & pl.col("Cell").is_in(cl) & (pl.col("Type") <= 6)
                  & (pl.col("Height") >= R.HMIN))
          .select(pl.col("Year").cast(pl.Int32), pl.col("Cell").cast(pl.Int32), pl.col("Patch").cast(pl.Int16),
                  pl.col("Type").cast(pl.Int8), pl.col("isdead").cast(pl.Int8), pl.col("mort").cast(pl.Float64),
                  *[pl.col(v).cast(pl.Float64) for v in TRAITS2]))
    return lf, cl, y0, y1


def stage_yearly(a) -> None:
    os.makedirs(YEARLY2, exist_ok=True)
    for i, (m, lg) in enumerate(jobs()):
        if i % a.nparts != a.part:
            continue
        out = os.path.join(YEARLY2, f"m{m}_{lg}.parquet")
        if os.path.exists(out):
            continue
        t0 = time.time()
        lf, cl, y0, y1 = scan(m, lg)
        live = lf.filter(pl.col("isdead") == 0)
        aggs = [pl.len().alias("n_living"), pl.col("agb").sum().alias("agb_sum")]
        aggs += [(pl.col("Type") == t).sum().alias(f"n_t{t}") for t in PFTS]
        aggs += [pl.col(v).quantile(p, interpolation="linear").alias(f"{v}_{pn}")
                 for v in TRAITS2 for p, pn in zip(PS, PN, strict=True)]
        aggs += [pl.col(v).mean().alias(f"{v}_mean") for v in TRAITS2]
        g = live.group_by(["Cell", "Year"]).agg(aggs).collect()
        dd = lf.group_by(["Cell", "Year"]).agg(
            (pl.col("isdead") == 1).sum().alias("n_dead"),
            pl.col("mort").clip(0.0, 1.0).sum().alias("exp_dead"),
            ((pl.col("mort") < 0) | (pl.col("mort") > 1)).sum().alias("n_mort_out"),
            *[((pl.col("isdead") == 1) & (pl.col("Type") == t)).sum().alias(f"n_dead_t{t}") for t in PFTS]).collect()
        for x in (g, dd):
            assert x.select("Cell", "Year").n_unique() == x.height, "duplicate (Cell, Year)"
        census = pl.DataFrame({"Cell": np.repeat(cl, y1 - y0 + 1).astype(np.int32),
                               "Year": np.tile(np.arange(y0, y1 + 1), len(cl)).astype(np.int32)})
        assert g.join(census, on=["Cell", "Year"], how="anti").height == 0, "rows outside the census"
        d = census.join(g, on=["Cell", "Year"], how="left").join(dd, on=["Cell", "Year"], how="left")
        cnt = ["n_living", "n_dead", "n_mort_out", *[f"n_t{t}" for t in PFTS], *[f"n_dead_t{t}" for t in PFTS]]
        d = d.with_columns(*[pl.col(c).fill_null(0) for c in cnt], pl.col("agb_sum").fill_null(0.0),
                           pl.col("exp_dead").fill_null(0.0))
        d = d.sort("Cell", "Year")
        # gate against version 1
        gate = {"member": m, "leg": lg, "rows": d.height, "seconds": None}
        f1 = os.path.join(YEARLY1, f"m{m}_{lg}.parquet")
        if os.path.exists(f1):
            v1 = pl.read_parquet(f1).select("Cell", "Year", "n_living", "agb_sum", *[f"n_t{t}" for t in PFTS],
                                            "SLA_p50", "Height_p50")
            j = v1.join(d, on=["Cell", "Year"], how="inner", suffix="_2")
            gate["joined_v1"] = j.height
            gate["v1_rows"] = v1.height
            for c in ["n_living", *[f"n_t{t}" for t in PFTS]]:
                gate[f"{c}_mismatch"] = int((j[c] != j[f"{c}_2"]).sum())
            for c in ["agb_sum", "SLA_p50", "Height_p50"]:
                diff = (j[c] - j[f"{c}_2"]).abs() / j[c].abs().clip(1e-12)
                gate[f"{c}_max_rel"] = float(diff.max() or 0.0)
        gate["mort_out_share"] = float(d["n_mort_out"].sum() / max(1, d["n_living"].sum() + d["n_dead"].sum()))
        d.write_parquet(out)
        gate["seconds"] = round(time.time() - t0, 1)
        json.dump(gate, open(os.path.join(YEARLY2, f"_gate_m{m}_{lg}.json"), "w"), indent=1)
        log(json.dumps(gate))


def stage_rosters(a) -> None:
    os.makedirs(ROSTER, exist_ok=True)
    for i, (m, lg) in enumerate(jobs()):
        if i % a.nparts != a.part:
            continue
        out = os.path.join(ROSTER, f"m{m}_{lg}.parquet")
        if os.path.exists(out):
            continue
        t0 = time.time()
        lf, _, _, _ = scan(m, lg)
        yrs = [2019] if lg == "hist" else ROSTER_YEARS
        d = (lf.filter((pl.col("isdead") == 0) & pl.col("Year").is_in(yrs))
             .select("Cell", "Year", *[pl.col(c).cast(pl.Float32) if c not in ("Patch", "Type") else pl.col(c)
                                       for c in ROSTER_COLS]).collect().sort("Cell", "Year", "Patch"))
        d.write_parquet(out)
        log(f"rosters m{m} {lg}: {d.height} trees ({time.time() - t0:.0f}s)")


def stage_npp(a) -> None:
    out_dir = os.path.join(PP.OUT, "yearly2_npp")
    os.makedirs(out_dir, exist_ok=True)
    for i, (m, lg) in enumerate(jobs()):
        if i % a.nparts != a.part:
            continue
        out = os.path.join(out_dir, f"m{m}_{lg}.parquet")
        if os.path.exists(out):
            continue
        t0 = time.time()
        td = PP.table_dir(m, lg)
        y0, y1 = (2000, 2019) if lg == "hist" else (2020, 2100)
        d = (pl.scan_parquet(os.path.join(td, "ind.parquet"))
             .filter(pl.col("Year").is_between(y0, y1) & (pl.col("Type") <= 6) & (pl.col("Height") >= R.HMIN))
             .group_by("Cell", "Year").agg(pl.col("npp").cast(pl.Float64).sum().alias("npp_sum"),
                                           pl.col("npp").cast(pl.Float64).mean().alias("npp_per_tree"),
                                           (pl.col("npp") < 0).mean().alias("share_npp_neg"))
             .with_columns(pl.col("Cell").cast(pl.Int32), pl.col("Year").cast(pl.Int32)).collect().sort("Cell", "Year"))
        d.write_parquet(out)
        log(f"npp m{m} {lg}: {d.height} rows ({time.time() - t0:.0f}s)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["yearly", "rosters", "npp", "list"])
    ap.add_argument("--part", type=int, default=0)
    ap.add_argument("--nparts", type=int, default=1)
    a = ap.parse_args()
    if a.stage == "list":
        js = jobs()
        print(len(js), "member-legs")
        return
    {"yearly": stage_yearly, "rosters": stage_rosters, "npp": stage_npp}[a.stage](a)


if __name__ == "__main__":
    main()
