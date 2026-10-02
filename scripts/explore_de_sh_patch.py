#!/usr/bin/env python3
"""explore_de_sh_patch.py — LINE X, Germany data-driven emulator, shared item SH4: PATCH-YEAR + RECRUIT TABLES.

Built on the SH3 transition table (explore_de_sh_trans) plus the converted `ind` tables for the grass rows, the
flagged-dead stems and the newly printed stems. Same member windows, same chain (Historical 1985-2014, then the
ssp window 2015-2044 continuing it), same layout:

  shared/patch/<cellset>/<member>/cb=<k>/y<YYYY>.parquet     one row per (Cell, Patch, Year = y), ALL npatch
                                                             patches of every cell, zeros included
  shared/recruits/<cellset>/<member>/cb=<k>/y<YYYY>.parquet  one row per recruit printed for the first time at y+1

PATCH-YEAR COLUMNS (Year = y; outcomes of the y -> y+1 transition carry _y1)
  ids        member, gcm, traj, seed, Year, Cell, Patch
  state y    n_live_y, sum_fpc_y, sum_agb_y (living trees, Type <= 6), grass<t>_{fpc,LAI,agb}_y (every grass Type in
             the data; 0 when no row), fpc_dead_y, agb_dead_y (stems FLAGGED dead at y: the anatomy's event
             definition and a litter proxy), n_recruit_y (recruits printed for the first time at y; null in the
             chain's first year)
  history    loss_lag<k> / frac_loss_lag<k>, k = 0..19: fpc at t-1 of stems living at t-1 that are flagged dead or
             absent at t, t = y - k (lag 0 = the loss during year y), and that over the patch's living fpc at t-1
             (0/0 -> 0); null where t - 1 precedes the chain. hist_years = number of non-null lags.
  outcomes   n_recruit_y1 (keys printed at y+1 that are not living at y and were never printed before in the
             chain), n_reentry_y1 (not living at y but printed earlier: threshold flicker of an existing stem),
             deaths_y1 (flagged dead at y+1), absent_y1 (living at y, not printed at y+1), n_hard_y1 (mort = 1),
             hazard_sum_y1 (sum of printed mort over present stems), fire_D_y1 = sum over non-hard present stems of
             (1 - resist[Type]) (1 - mort), fire_E_y1 = non-hard deaths - sum of non-hard mort (the excess the fire
             channel must explain; f ~ E / D), loss_y1, frac_loss_y1
  cell y+1   n_eligible_pft_y1, elig_t<k>_y1 (SH2 rl.eligible on the y+1 climate: 20-yr tcold/twarm, the current
             year's gdd5, prec_ann — the C-faithful basis)

RECRUIT COLUMNS (Year = y; the recruit is printed at y+1)
  member, gcm, traj, seed, Year, Cell, Patch, Type, ID, sla_i, wd_i, the 6 traits, entry Height/Age/agb/vegc/LAI/
  fpc_ind/D95/isdead, c/G/cenG at entry (c_prev unknown), the patch context at y (n_live_y, sum_fpc_y, sum_agb_y,
  frac_loss_lag0, grass), and the cell's same-Type standing summary at y: std_n, and per trait std_<t>_{median,mean,
  wmean} (agb-weighted) over the cell's living stems of that Type at y (null when the Type has no standing stem).

GATES (per member/cb; aggregated by `gates`)
  patch_rows        npatch rows per (Cell, Year)
  recruits_nonzero  recruits per cell-year never 0 (truth minimum 19-27 in round 1)
  recruit_disp      per patch-year var/mean of n_recruit_y1 in [1.2, 1.4] (round 1: 1.27-1.29)
  reentry_share     re-entries / (recruits + re-entries) in [0.001, 0.007]
  deaths_match      sum of patch deaths_y1 per (Cell, Year) == SH3 fate_y1 == 1 per (Cell, Year), independent scan
  release           event-study ratio (round-1 anatomy definition: fpc_dead_y >= 0.5 (sum_fpc_y + fpc_dead_y) with
                    sum_fpc_y + fpc_dead_y > 0.3; mean n_recruit_y1 / mean n_recruit_y over event patch-years) in
                    the judge's band [3.6, 4.1]; round 1 measured 0.92-1.06 / 0.29-0.32 on whole Germany

STAGES  build --cellset dev|full [--member M] [--cb K] · gates --cellset · submit --cellset [--gates-after]
Nothing Germany-specific is hard-coded (npatch, cells, PFTs, grass types, years from the registry and tables).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_sh_rules as rl  # noqa: E402
import explore_de_sh_trans as tr  # noqa: E402

XDE = tr.XDE
PATCH = os.environ.get("SH4_PATCH_OUT", os.path.join(XDE, "shared", "patch"))
RECR = os.environ.get("SH4_RECR_OUT", os.path.join(XDE, "shared", "recruits"))
STATUS = os.path.join(XDE, "_status", "SH4.md")
NLAG = 20
KEY = tr.KEY
STD_TRAITS = ["SLA", "Wooddens", "D95max", "minwscal", "Longevity"]
BAND_DISP = (1.2, 1.4)
BAND_REENTRY = (0.001, 0.007)
BAND_RELEASE = (3.6, 4.1)
log = tr.log


def status(line: str):
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    with open(STATUS, "a") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} {line}\n")


def trans_file(cellset, member, cb, y):
    return os.path.join(tr.TRANS, cellset, member, f"cb={cb}", f"y{y}.parquet")


def build_one(member: str, cellset: str, cb: str, force: bool = False) -> dict:
    rl.assert_usable(member)
    mem, seg, folds = tr.registry()
    row = tr.member_row(mem, member)
    gcm, traj, seed, npatch = row["gcm"], row["scen"], int(row["seed"]), int(row["npatch"])
    is_hist = traj == "Historical"
    hist = row if is_hist else tr.historical_of(mem, gcm, seed)
    tg = json.load(open(os.path.join(tr.TRANS, cellset, member, f"cb={cb}", "_gates.json")))
    assert tg.get("complete"), f"SH3 not complete for {member} cb={cb}"
    out_years = [int(y) for y in tg["out_years"]]
    hy = max(int(y) for y in hist["years_complete"])
    hist_tg = json.load(open(os.path.join(tr.TRANS, cellset, hist["member"], f"cb={cb}", "_gates.json")))
    hist_years = [int(y) for y in hist_tg["out_years"]]  # Historical trans years (1985..2013)
    chain_trans = hist_years + ([] if is_hist else out_years)

    def tmember(y):
        return hist["member"] if (y in hist_years and (is_hist or y < out_years[0])) else member

    src_hist = tr.sources(hist, cellset)[cb]
    src_win = tr.sources(row, cellset)[cb]

    def src_of(y):
        return src_hist if y <= hy else src_win

    podir = os.path.join(PATCH, cellset, member, f"cb={cb}")
    rodir = os.path.join(RECR, cellset, member, f"cb={cb}")
    gpath = os.path.join(podir, "_gates.json")
    if not force and os.path.exists(gpath):
        g = json.load(open(gpath))
        if g.get("complete") and g.get("out_years") == out_years:
            log(f"{member} cb={cb}: complete, skipping")
            return g
    os.makedirs(podir, exist_ok=True)
    os.makedirs(rodir, exist_ok=True)
    P = rl.load_params()
    resist = np.asarray(P["resist"], dtype=np.float64)
    cells = tr.cells_of(cellset, folds, cb, pl.scan_parquet(src_win).select(
        pl.concat_list(pl.col("Cell").min(), pl.col("Cell").max()).alias("Cell")).collect().explode("Cell"))
    if tr.SMOKE:
        cells = cells[cells % 100 == 0]
    cell_filter = cells if tr.SMOKE else None
    universe = (pl.DataFrame({"Cell": cells.astype(np.int16)})
                .join(pl.DataFrame({"Patch": np.arange(npatch, dtype=np.int16)}), how="cross"))
    log(f"{member} cb={cb}: {len(cells)} cells x {npatch} patches, out {out_years[0]}-{out_years[-1]}")

    # ---- pass 1: per-patch loss series over the whole chain + the living-key history
    loss = {}          # t -> frame (Cell, Patch, loss, frac_loss) for the loss during year t
    seen = None        # living keys of every chain year < current
    seen_upto = {}     # y -> keys living at some year <= y-1 (only for out years)
    for y in chain_trans:
        t = pl.read_parquet(trans_file(cellset, tmember(y), cb, y), columns=KEY + ["fpc_ind", "fate_y1"])
        if cell_filter is not None:
            t = t.filter(pl.col("Cell").is_in(cell_filter.tolist()))
        lo = (t.group_by("Cell", "Patch").agg(
            _tot=pl.col("fpc_ind").cast(pl.Float64).sum(),
            loss=(pl.col("fpc_ind").cast(pl.Float64) * (pl.col("fate_y1") > 0)).sum()))
        loss[y + 1] = lo.with_columns(frac_loss=pl.when(pl.col("_tot") > 0).then(pl.col("loss") / pl.col("_tot"))
                                      .otherwise(0.0)).drop("_tot")
        if y in out_years:
            seen_upto[y] = seen
        k = t.select(KEY)
        seen = k if seen is None else pl.concat([seen, k]).unique()
    first_t = chain_trans[0] + 1  # the first year with a defined loss

    gates = {"member": member, "cellset": cellset, "cb": cb, "out_years": out_years, "years": {}}
    n_recruit_prev = None
    for y in out_years:
        raw = tr.read_year(src_of(y), y, cell_filter)
        trees_y = raw.filter(pl.col("Type") <= tr.MAX_TREE_TYPE)
        grass_y = raw.filter(pl.col("Type") > tr.MAX_TREE_TYPE)
        T = pl.read_parquet(trans_file(cellset, member if y in out_years else tmember(y), cb, y))
        if cell_filter is not None:
            T = T.filter(pl.col("Cell").is_in(cell_filter.tolist()))
        # state at y
        st = T.group_by("Cell", "Patch").agg(n_live_y=pl.len().cast(pl.Int32),
                                             sum_fpc_y=pl.col("fpc_ind").cast(pl.Float64).sum(),
                                             sum_agb_y=pl.col("agb").cast(pl.Float64).sum())
        dd = trees_y.filter(pl.col("isdead") == 1).group_by("Cell", "Patch").agg(
            fpc_dead_y=pl.col("fpc_ind").cast(pl.Float64).sum(), agb_dead_y=pl.col("agb").cast(pl.Float64).sum())
        D = universe.join(st, on=["Cell", "Patch"], how="left").join(dd, on=["Cell", "Patch"], how="left")
        for gt in sorted(int(v) for v in grass_y["Type"].unique().to_list()):
            gg = grass_y.filter(pl.col("Type") == gt).group_by("Cell", "Patch").agg(
                **{f"grass{gt}_fpc_y": pl.col("fpc_ind").cast(pl.Float64).sum(),
                   f"grass{gt}_LAI_y": pl.col("LAI").cast(pl.Float64).sum(),
                   f"grass{gt}_agb_y": pl.col("agb").cast(pl.Float64).sum()})
            D = D.join(gg, on=["Cell", "Patch"], how="left")
        # history: lags 0..NLAG-1 of the loss during year t = y - k
        for k in range(NLAG):
            t = y - k
            if t >= first_t and t in loss:
                D = D.join(loss[t].rename({"loss": f"loss_lag{k}", "frac_loss": f"frac_loss_lag{k}"}),
                           on=["Cell", "Patch"], how="left")
                D = D.with_columns(pl.col(f"loss_lag{k}").fill_null(0.0), pl.col(f"frac_loss_lag{k}").fill_null(0.0))
            else:
                D = D.with_columns(pl.lit(None, pl.Float64).alias(f"loss_lag{k}"),
                                   pl.lit(None, pl.Float64).alias(f"frac_loss_lag{k}"))
        D = D.with_columns(hist_years=pl.sum_horizontal(
            [pl.col(f"loss_lag{k}").is_not_null().cast(pl.Int8) for k in range(NLAG)]).cast(pl.Int8))
        # outcomes y+1 from the transition table
        pres = T.filter(pl.col("fate_y1") < 2)
        nh = pres.filter(~pl.col("hard_y1"))
        res = pl.Series(resist[nh["Type"].to_numpy().astype(np.int64)])
        nh = nh.with_columns(_d=(1.0 - res) * (1.0 - pl.col("mort_y1").cast(pl.Float64)))
        oc = T.group_by("Cell", "Patch").agg(
            deaths_y1=(pl.col("fate_y1") == 1).sum().cast(pl.Int32),
            absent_y1=(pl.col("fate_y1") == 2).sum().cast(pl.Int32),
            n_hard_y1=pl.col("hard_y1").fill_null(False).sum().cast(pl.Int32),
            hazard_sum_y1=pl.col("mort_y1").cast(pl.Float64).sum(),
            loss_y1=(pl.col("fpc_ind").cast(pl.Float64) * (pl.col("fate_y1") > 0)).sum())
        fire = nh.group_by("Cell", "Patch").agg(
            fire_D_y1=pl.col("_d").sum(),
            fire_E_y1=((pl.col("fate_y1") == 1).cast(pl.Float64) - pl.col("mort_y1").cast(pl.Float64)).sum())
        D = D.join(oc, on=["Cell", "Patch"], how="left").join(fire, on=["Cell", "Patch"], how="left")
        # recruits printed at y+1
        nxt = tr.with_key(tr.read_year(src_of(y + 1), y + 1, cell_filter).filter(pl.col("Type") <= tr.MAX_TREE_TYPE))
        new = nxt.join(T.select(KEY), on=KEY, how="anti")
        sb = seen_upto.get(y)
        if sb is not None and sb.height:
            new = new.join(sb.with_columns(_seen=pl.lit(True)), on=KEY, how="left").with_columns(
                _re=pl.col("_seen").fill_null(False)).drop("_seen")
        else:
            new = new.with_columns(_re=pl.lit(False))
        rec = new.filter(~pl.col("_re")).drop("_re")
        nre = new.filter(pl.col("_re"))
        rc = rec.group_by("Cell", "Patch").agg(n_recruit_y1=pl.len().cast(pl.Int32))
        rr = nre.group_by("Cell", "Patch").agg(n_reentry_y1=pl.len().cast(pl.Int32))
        D = D.join(rc, on=["Cell", "Patch"], how="left").join(rr, on=["Cell", "Patch"], how="left")
        ints = ["n_live_y", "deaths_y1", "absent_y1", "n_hard_y1", "n_recruit_y1", "n_reentry_y1"]
        flts = ["sum_fpc_y", "sum_agb_y", "fpc_dead_y", "agb_dead_y", "hazard_sum_y1", "loss_y1",
                "fire_D_y1", "fire_E_y1"] + [c for c in D.columns if c.startswith("grass")]
        D = D.with_columns([pl.col(c).fill_null(0) for c in ints] + [pl.col(c).fill_null(0.0) for c in flts])
        D = D.with_columns(frac_loss_y1=pl.when(pl.col("sum_fpc_y") > 0).then(pl.col("loss_y1") / pl.col("sum_fpc_y"))
                           .otherwise(0.0))
        if n_recruit_prev is not None:
            D = D.join(n_recruit_prev, on=["Cell", "Patch"], how="left").with_columns(
                pl.col("n_recruit_y").fill_null(0))
        elif y > chain_trans[0]:
            # first out year of an ssp window: recruits arriving at y = printed at y, not living at y-1, never
            # printed before (same definition, computed from the Historical side of the chain)
            D = D.join(recruits_arriving(cellset, cb, tmember(y - 1), y - 1, trees_y, seen_upto_prev(seen, T, y,
                                         cellset, cb, tmember, chain_trans, cell_filter), cell_filter),
                       on=["Cell", "Patch"], how="left").with_columns(pl.col("n_recruit_y").fill_null(0))
        else:
            D = D.with_columns(n_recruit_y=pl.lit(None, pl.Int32))
        n_recruit_prev = D.select("Cell", "Patch", pl.col("n_recruit_y1").alias("n_recruit_y"))
        # eligibility at y+1
        cy = pl.DataFrame({"gcm": [gcm] * len(cells), "traj": [traj] * len(cells), "seed": [seed] * len(cells),
                           "Cell": cells.astype(np.int16), "Year": [y] * len(cells)}).with_columns(
            pl.col("seed").cast(pl.Int8), pl.col("Year").cast(pl.Int16))
        cy = tr.join_climate(cy, cols=["tcold_month_tr20", "twarm_month_tr20", "gdd5", "prec_ann"], years=("y1",),
                             ext=False)
        el = rl.eligible(cy["tcold_month_tr20_y1"].to_numpy(), cy["twarm_month_tr20_y1"].to_numpy(),
                         cy["gdd5_y1"].to_numpy(), cy["prec_ann_y1"].to_numpy(), P)
        ec = cy.select("Cell").with_columns(n_eligible_pft_y1=pl.Series(el.sum(1).astype(np.int8)),
                                            **{f"elig_t{k}_y1": pl.Series(el[:, k]) for k in range(el.shape[1])})
        D = D.join(ec, on="Cell", how="left")
        D = D.with_columns(member=pl.lit(member), gcm=pl.lit(gcm), traj=pl.lit(traj), seed=pl.lit(seed, pl.Int8),
                           Year=pl.lit(y, pl.Int16))
        lead = ["member", "gcm", "traj", "seed", "Year", "Cell", "Patch"]
        D = D.select(lead + [c for c in D.columns if c not in lead]).sort("Cell", "Patch")
        f64 = [c for c, t in D.schema.items() if t == pl.Float64]
        D.with_columns([pl.col(c).cast(pl.Float32) for c in f64]).write_parquet(
            os.path.join(podir, f"y{y}.parquet"), compression="zstd")
        # recruit table
        R = tr.add_hidden(rec, None, P).drop(["mort_npp", "mort_age", "mort_water", "mort_temp", "mort", "npp",
                                              "transp", "wscal_mean", "W", "cenW"])
        ctx = D.select("Cell", "Patch", "n_live_y", "sum_fpc_y", "sum_agb_y", "frac_loss_lag0",
                       *[c for c in D.columns if c.startswith("grass")])
        R = R.join(ctx, on=["Cell", "Patch"], how="left")
        std = T.group_by("Cell", "Type").agg(
            std_n=pl.len().cast(pl.Int32),
            **{f"std_{t}_median": pl.col(t).cast(pl.Float64).median() for t in STD_TRAITS},
            **{f"std_{t}_mean": pl.col(t).cast(pl.Float64).mean() for t in STD_TRAITS},
            **{f"std_{t}_wmean": (pl.col(t).cast(pl.Float64) * pl.col("agb").cast(pl.Float64)).sum()
               / pl.col("agb").cast(pl.Float64).sum() for t in STD_TRAITS})
        R = R.join(std, on=["Cell", "Type"], how="left").with_columns(pl.col("std_n").fill_null(0))
        R = R.rename({"Year": "Year_entry"}).with_columns(
            member=pl.lit(member), gcm=pl.lit(gcm), traj=pl.lit(traj), seed=pl.lit(seed, pl.Int8),
            Year=pl.lit(y, pl.Int16))
        R = R.select(lead + [c for c in R.columns if c not in lead]).sort("Cell", "Patch", "Type", "ID")
        f64 = [c for c, t in R.schema.items() if t == pl.Float64]
        R.with_columns([pl.col(c).cast(pl.Float32) for c in f64]).write_parquet(
            os.path.join(rodir, f"y{y}.parquet"), compression="zstd")
        # per-year gate numbers
        pc = D.group_by("Cell").agg(n=pl.len(), r=pl.col("n_recruit_y1").sum())
        x = D["n_recruit_y1"].cast(pl.Float64)
        g = {"patch_rows_bad": int((pc["n"] != npatch).sum()), "cells": D["Cell"].n_unique(),
             "recruits": int(x.sum()), "reentries": int(D["n_reentry_y1"].sum()),
             "cellyear_recruits_min": int(pc["r"].min()), "cellyear_recruits_median": float(pc["r"].median()),
             "sum_x": float(x.sum()), "sum_x2": float((x * x).sum()), "n_patchyears": D.height,
             "deaths": int(D["deaths_y1"].sum())}
        ev = D.filter(pl.col("n_recruit_y").is_not_null()).with_columns(_tot=pl.col("sum_fpc_y") + pl.col("fpc_dead_y"))
        ev = ev.filter((pl.col("fpc_dead_y") >= 0.5 * pl.col("_tot")) & (pl.col("_tot") > 0.3))
        g["event_n"] = ev.height
        g["event_rec_y1"] = float(ev["n_recruit_y1"].cast(pl.Float64).sum())
        g["event_rec_y"] = float(ev["n_recruit_y"].cast(pl.Float64).sum())
        gates["years"][str(y)] = g
        log(f"  {y}: recruits {g['recruits']} reentries {g['reentries']} min/cell {g['cellyear_recruits_min']} "
            f"events {g['event_n']}")
    gates["deaths_match"] = deaths_match(cellset, member, cb, out_years, cell_filter)
    gates["complete"] = True
    gates["summary"] = summarise(gates)
    json.dump(gates, open(gpath, "w"), indent=1)
    log(f"{member} cb={cb}: DONE pass={gates['summary']['pass']} {json.dumps(gates['summary'])}")
    return gates


def seen_upto_prev(seen, T, y, cellset, cb, tmember, chain_trans, cell_filter):
    """Living keys at every chain year <= y-2 (for the recruits arriving at y, the first out year of an ssp)."""
    ks = None
    for t in [c for c in chain_trans if c <= y - 2]:
        k = pl.read_parquet(trans_file(cellset, tmember(t), cb, t), columns=KEY)
        if cell_filter is not None:
            k = k.filter(pl.col("Cell").is_in(cell_filter.tolist()))
        ks = k if ks is None else pl.concat([ks, k]).unique()
    return ks


def recruits_arriving(cellset, cb, member_prev, yprev, trees_y, seen_before, cell_filter):
    prev = pl.read_parquet(trans_file(cellset, member_prev, cb, yprev), columns=KEY)
    if cell_filter is not None:
        prev = prev.filter(pl.col("Cell").is_in(cell_filter.tolist()))
    new = tr.with_key(trees_y).join(prev, on=KEY, how="anti")
    if seen_before is not None:
        new = new.join(seen_before, on=KEY, how="anti")
    return new.group_by("Cell", "Patch").agg(n_recruit_y=pl.len().cast(pl.Int32))


def deaths_match(cellset, member, cb, out_years, cell_filter) -> dict:
    """Independent scan: per (Cell, Year), patch-table deaths == transition-table fate_y1 == 1."""
    pt = pl.scan_parquet(os.path.join(PATCH, cellset, member, f"cb={cb}", "y*.parquet")).group_by("Cell", "Year").agg(
        a=pl.col("deaths_y1").sum()).collect()
    tt = pl.scan_parquet(os.path.join(tr.TRANS, cellset, member, f"cb={cb}", "y*.parquet"))
    if cell_filter is not None:
        tt = tt.filter(pl.col("Cell").is_in(cell_filter.tolist()))
    tt = tt.filter(pl.col("Year").is_in(out_years)).group_by("Cell", "Year").agg(
        b=(pl.col("fate_y1") == 1).sum()).collect()
    j = pt.join(tt, on=["Cell", "Year"], how="full", coalesce=True).fill_null(0)
    bad = j.filter(pl.col("a") != pl.col("b"))
    return {"cell_years": j.height, "mismatch": bad.height, "pass": bad.height == 0}


def summarise(g: dict) -> dict:
    ys = list(g["years"].values())
    sx = sum(v["sum_x"] for v in ys)
    sx2 = sum(v["sum_x2"] for v in ys)
    n = sum(v["n_patchyears"] for v in ys)
    mean = sx / n
    var = sx2 / n - mean * mean
    rec, rre = sum(v["recruits"] for v in ys), sum(v["reentries"] for v in ys)
    ev_n = sum(v["event_n"] for v in ys)
    ev1, ev0 = sum(v["event_rec_y1"] for v in ys), sum(v["event_rec_y"] for v in ys)
    s = {"patch_rows_bad": sum(v["patch_rows_bad"] for v in ys),
         "cellyear_recruits_min": min(v["cellyear_recruits_min"] for v in ys),
         "recruit_mean": mean, "recruit_var_over_mean": var / mean if mean > 0 else None,
         "recruits": rec, "reentries": rre, "reentry_share": rre / max(rec + rre, 1),
         "event_n": ev_n, "event_mean_y1": ev1 / max(ev_n, 1), "event_mean_y": ev0 / max(ev_n, 1),
         "release_ratio": (ev1 / ev0) if ev0 > 0 else None,
         "deaths_match": g["deaths_match"]["pass"]}
    s["gate"] = {
        "patch_rows": s["patch_rows_bad"] == 0,
        "recruits_nonzero": s["cellyear_recruits_min"] > 0,
        "recruit_disp": s["recruit_var_over_mean"] is not None
        and BAND_DISP[0] <= s["recruit_var_over_mean"] <= BAND_DISP[1],
        "reentry_share": BAND_REENTRY[0] <= s["reentry_share"] <= BAND_REENTRY[1],
        "deaths_match": s["deaths_match"],
        "release": s["release_ratio"] is not None and BAND_RELEASE[0] <= s["release_ratio"] <= BAND_RELEASE[1]}
    s["pass"] = all(s["gate"].values())
    return s


def stage_build(a):
    mem, _, _ = tr.registry()
    members = a.member or tr.usable_members(mem)
    # Historical first: the ssp windows read its transition files for their history
    members = sorted(members, key=lambda m: 0 if "_Historical_" in m else 1)
    for m in members:
        for cb in (a.cb or list(tr.sources(tr.member_row(mem, m), a.cellset).keys())):
            t0 = time.time()
            g = build_one(m, a.cellset, cb, force=a.force)
            status(f"{a.cellset} {m} cb={cb}: pass={g['summary']['pass']} gates={g['summary']['gate']} "
                   f"{time.time() - t0:.0f} s")


def stage_gates(a):
    rows = []
    for gp in sorted(glob.glob(os.path.join(PATCH, a.cellset, "*", "cb=*", "_gates.json"))):
        g = json.load(open(gp))
        s = g["summary"]
        rows.append({"member": g["member"], "cb": g["cb"], **{k: v for k, v in s.items() if k != "gate"},
                     **{f"gate_{k}": v for k, v in s["gate"].items()}})
    mem, _, _ = tr.registry()
    expected = {(m, cb) for m in tr.usable_members(mem) for cb in tr.sources(tr.member_row(mem, m), a.cellset)}
    have = {(r["member"], r["cb"]) for r in rows}
    gk = [k for k in rows[0] if k.startswith("gate_")] if rows else []
    out = {"cellset": a.cellset, "expected": len(expected), "built": len(have & expected),
           "missing": sorted(f"{m} cb={c}" for m, c in expected - have),
           "gate_pass_counts": {k: int(sum(bool(r[k]) for r in rows)) for k in gk},
           "all_pass": bool(rows) and all(r["pass"] for r in rows) and not (expected - have),
           "per_member": rows}
    json.dump(out, open(os.path.join(PATCH, a.cellset, "_gates.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "per_member"}, indent=1))
    pl.Config.set_tbl_cols(20)
    print(pl.DataFrame(rows).select("member", "recruit_var_over_mean", "reentry_share", "release_ratio",
                                    "event_mean_y", "event_mean_y1", "cellyear_recruits_min", "pass"))


def stage_submit(a):
    mem, _, _ = tr.registry()
    ms = tr.usable_members(mem)
    hist = [m for m in ms if "_Historical_" in m]
    ssp = [m for m in ms if m not in hist]
    jobs = os.path.join(XDE, "_jobs")
    logs = os.path.join(REPO, "logs")
    os.makedirs(logs, exist_ok=True)
    ncpu = 16 if a.cellset == "dev" else 32
    prev = a.dependency
    jids = []
    for tag, group in (("hist", hist), ("ssp", ssp)):
        tasks = [(m, cb) for m in group for cb in tr.sources(tr.member_row(mem, m), a.cellset)]
        tl = os.path.join(jobs, f"SH4_{a.cellset}_{tag}_tasks.txt")
        with open(tl, "w") as f:
            f.writelines(f"{m} {cb}\n" for m, cb in tasks)
        jcf = os.path.join(jobs, f"X-de-SH4-{a.cellset}-{tag}.jcf")
        dep = f"#SBATCH --dependency=afterok:{prev}\n" if prev else ""
        with open(jcf, "w") as f:
            f.write(f"""#!/bin/bash
#SBATCH --job-name=X-de-SH4-{a.cellset}-{tag}
#SBATCH --account=waldspektrum
#SBATCH --partition=priority
#SBATCH --qos=priority
#SBATCH --cpus-per-task={ncpu}
#SBATCH --time=04:00:00
#SBATCH --array=1-{len(tasks)}%16
{dep}#SBATCH --output={logs}/X-de-SH4-{a.cellset}-{tag}.%A_%a.out
set -eu
read M CB < <(sed -n "${{SLURM_ARRAY_TASK_ID}}p" {tl})
export POLARS_MAX_THREADS={ncpu}
{tr.PY} {os.path.abspath(__file__)} build --cellset {a.cellset} --member "$M" --cb "$CB"
echo "=== JOB DONE task=$SLURM_ARRAY_TASK_ID member=$M cb=$CB exit=$? ==="
""")
        prev = subprocess.run(["sbatch", "--parsable", jcf], capture_output=True, text=True,
                              check=True).stdout.strip()
        jids.append(prev)
        log(f"submitted {tag} {prev}: {len(tasks)} tasks")
        status(f"submitted {a.cellset} {tag} array {prev} ({len(tasks)} tasks)")
    gj = os.path.join(jobs, f"X-de-SH4-{a.cellset}-gates.jcf")
    with open(gj, "w") as f:
        f.write(f"""#!/bin/bash
#SBATCH --job-name=X-de-SH4-{a.cellset}-gates
#SBATCH --account=waldspektrum
#SBATCH --partition=priority
#SBATCH --qos=priority
#SBATCH --cpus-per-task=2
#SBATCH --time=00:20:00
#SBATCH --dependency=afterany:{jids[-1]}
#SBATCH --output={logs}/X-de-SH4-{a.cellset}-gates.%j.out
{tr.PY} {os.path.abspath(__file__)} gates --cellset {a.cellset}
echo "=== JOB DONE gates exit=$? ==="
""")
    g = subprocess.run(["sbatch", "--parsable", gj], capture_output=True, text=True, check=True).stdout.strip()
    status(f"gates job {g} afterany {jids[-1]}")
    log(f"gates job {g}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["build", "gates", "submit", "smoke"])
    ap.add_argument("--cellset", choices=["dev", "full"], default="dev")
    ap.add_argument("--member", action="append")
    ap.add_argument("--cb", action="append")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dependency")
    a = ap.parse_args(argv)
    if a.stage == "smoke":
        global PATCH, RECR
        tr.SMOKE = True
        tr.TRANS = os.path.join(XDE, "shared", "trans", "_smoke")
        PATCH = os.path.join(XDE, "shared", "patch", "_smoke")
        RECR = os.path.join(XDE, "shared", "recruits", "_smoke")
        a.cellset = "dev"
        a.member = a.member or ["MPI-ESM1-2-HR_Historical_s1_h1985"]
        a.force = True
        stage_build(a)
        return
    {"build": stage_build, "gates": stage_gates, "submit": stage_submit}[a.stage](a)


if __name__ == "__main__":
    main()
