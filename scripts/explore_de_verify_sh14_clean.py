#!/usr/bin/env python
"""explore_de_verify_sh14_clean.py -- adversarial verifier of SH14 (scorer amendments) AFTER the owner decision of
2026-10-01 (clean reference set, 1985-2044 only). Line X, Germany emulator exploration, round 2.

Independent of the builder's code paths wherever possible (reads the tree tables directly, recomputes levels,
contrasts, pass fractions and signal-to-noise with its own code), and probes the scorer with adversarial inputs.
Stages (argv[1], default all): excl, levels, tol, leak, probe.
Writes /p/tmp/jamirp/X_de/_verify_sh14c/*.json|csv and prints a summary.
"""

from __future__ import annotations

import glob
import json
import math
import os
import struct
import subprocess
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XDE = "/p/tmp/jamirp/X_de"
REF = f"{XDE}/reference/clean"
OUT = f"{XDE}/_verify_sh14c"
PY = "/home/jamirp/.conda/envs/py311_new/bin/python"
PROD = "/p/projects/waldspektrum/data/LPJmLFIT/productionruns_jamir"
PANEL106 = ["n_per_patch"] + [f"{v}_{q}" for v in ["SLA", "Wooddens", "D95max", "minwscal", "Height", "agb"]
                              for q in ["q05", "q25", "q50", "q75", "q95"]]
EPS = 1e-9
RES: dict = {}


def log(m):
    print(m, flush=True)


# ------------------------------------------------------------------------------------------------- exclusion
def read_clm_sample(path, ncell_take=5, day=180):
    with open(path, "rb") as f:
        hdr = f.read(64)
    name = hdr[:7].decode(errors="replace")
    ver = struct.unpack("<i", hdr[7:11])[0]
    order, fy, ny, fc, nc, nb = struct.unpack("<6i", hdr[11:35])
    if ver >= 3:
        cs_lon, scalar, cs_lat = struct.unpack("<3f", hdr[35:47])
        dt = struct.unpack("<i", hdr[47:51])[0]
        hl = 51
    else:
        cs, scalar = struct.unpack("<2f", hdr[35:43])
        dt, hl = 1, 43
    np_dt = {0: np.uint8, 1: np.int16, 2: np.int32, 3: np.float32, 4: np.float64}[dt]
    item = np.dtype(np_dt).itemsize
    vals = []
    with open(path, "rb") as f:
        for yoff in [0, ny - 1]:
            for c in range(0, nc, max(1, nc // ncell_take)):
                off = hl + ((yoff * nc + c) * nb + day) * item
                f.seek(off)
                vals.append(float(np.frombuffer(f.read(item), dtype=np_dt)[0]) * scalar)
    return {"name": name, "version": ver, "firstyear": fy, "nyear": ny, "ncell": nc, "nbands": nb,
            "scalar": scalar, "datatype": dt, "sample_values": vals, "min": min(vals), "max": max(vals)}


def stage_excl():
    r = {}
    # (a) configs
    for seg in ["2044", "2070", "2100", "3070", "3100"]:
        fs = sorted(glob.glob(f"{PROD}/*/ssp*/random_seed_*/lpjml_{seg}_*.js"))
        on = [f for f in fs if any('"relative_humidity"' in ln and "true" in ln and not ln.strip().startswith("//")
                                   for ln in open(f))]
        r[f"cfg_{seg}"] = {"n": len(fs), "rh_true": len(on)}
    # (b) humidity file content (the one the ssp370 configs name)
    hum = None
    for ln in open(glob.glob(f"{PROD}/MPI-ESM1-2-HR/ssp370/random_seed_1/input_*.js")[0]):
        if '"humid"' in ln:
            hum = ln.split('"name"')[1].split('"')[1]
    r["humid_file"] = hum
    try:
        r["humid_sample"] = read_clm_sample(hum)
    except Exception as e:  # noqa: BLE001
        r["humid_sample"] = f"ERR {e}"
    # (c) tree tables, independent read incl. Height filter variant
    mem = ["MPI-ESM1-2-HR_ssp370_s1_w2015", "MPI-ESM1-2-HR_ssp370_s1_w2071", "MPI-ESM1-2-HR_ssp370_s1_w3071",
           "ACCESS-CM2_ssp126_s2_w2071", "ACCESS-CM2_ssp126_s2_w2015", "MPI-ESM1-2-HR_ssp245_s2_w2071",
           "ACCESS-CM2_Historical_s2_h1985"]
    rows = []
    for m in mem:
        f = f"{XDE}/ind_dev/{m}.parquet"
        d = (pl.scan_parquet(f).select(["Year", "Type", "isdead", "mort_water", "Height"])
             .filter((pl.col("Type") <= 6) & (pl.col("isdead") == 0))
             .group_by("Year").agg(pl.len().alias("n"), (pl.col("mort_water") > 0).sum().alias("npos"),
                                   pl.col("mort_water").is_null().sum().alias("nnull"),
                                   pl.col("mort_water").max().alias("mwmax"),
                                   ((pl.col("Height") >= 5) & (pl.col("mort_water") > 0)).sum().alias("npos5"))
             .collect().sort("Year"))
        assert d["Year"].n_unique() == d.height
        rows.append({"member": m, "years": [int(d["Year"].min()), int(d["Year"].max())], "n_years": d.height,
                     "share_min": float((d["npos"] / d["n"]).min()), "share_max": float((d["npos"] / d["n"]).max()),
                     "years_exactly_zero": int((d["npos"] == 0).sum()), "n_null": int(d["nnull"].sum()),
                     "mort_water_max": float(d["mwmax"].max())})
        log(f"excl {rows[-1]}")
    r["tree_tables"] = rows
    RES["excl"] = r


# ------------------------------------------------------------------------------------------------- levels
def my_levels(member: str, years: tuple[int, int], cells: list[int], npatch=250) -> pl.DataFrame:
    f = f"{XDE}/ind_dev/{member}.parquet"
    lf = pl.scan_parquet(f).select(["Year", "Cell", "Type", "isdead", "Height", "Wooddens", "agb"]).filter(
        pl.col("Year").is_between(*years))
    ny = lf.select(pl.col("Year").n_unique()).collect().item()
    liv = lf.filter((pl.col("Type") <= 6) & (pl.col("isdead") == 0) & (pl.col("Height") >= 5.0))
    g = liv.group_by("Cell").agg(pl.len().alias("n"), pl.col("Wooddens").cast(pl.Float64).alias("wd"),
                                 pl.col("Height").cast(pl.Float64).alias("h")).collect()
    out = []
    for c, n, wd, h in zip(g["Cell"].to_list(), g["n"].to_list(), g["wd"].to_list(), g["h"].to_list(),
                           strict=True):
        out.append({"Cell": int(c), "n_per_patch": n / (ny * npatch),
                    "Wooddens_q50": float(np.percentile(np.asarray(wd, dtype=np.float32), 50)) if n >= 30 else None,
                    "Height_q95": float(np.percentile(np.asarray(h, dtype=np.float32), 95)) if n >= 30 else None})
    d = pl.DataFrame(out, schema={"Cell": pl.Int32, "n_per_patch": pl.Float64, "Wooddens_q50": pl.Float64,
                                  "Height_q95": pl.Float64})
    allc = pl.DataFrame({"Cell": cells}, schema={"Cell": pl.Int32})
    d = allc.join(d, on="Cell", how="left").with_columns(pl.col("n_per_patch").fill_null(0.0))
    return d.unpivot(index="Cell", variable_name="quantity", value_name="mine"), ny


def stage_levels():
    cells = sorted(int(x) for x in open(f"{XDE}/shared/scorer/cells_dev.txt").read().split())
    assert cells == list(range(0, max(cells) + 1, 10))[: len(cells)] or all(c % 10 == 0 for c in cells)
    lv = pl.read_parquet(f"{REF}/levels_long.parquet")
    r = {"levels_windows": sorted(lv["window"].unique().to_list()), "levels_rows": lv.height,
         "levels_cells": lv["Cell"].n_unique()}
    mine = {}
    specs = [("Historical", "h1985", (1985, 2014)), ("ssp126", "w2015", (2015, 2044)),
             ("ssp370", "w2015", (2015, 2044)), ("ssp245", "w2015", (2015, 2044))]
    cmp = []
    for gcm in ["MPI-ESM1-2-HR"]:
        for scen, win, yrs in specs:
            for seed in [1, 2]:
                m, ny = my_levels(f"{gcm}_{scen}_s{seed}_{win}", yrs, cells)
                mine[(gcm, scen, seed, win)] = m
                ref = lv.filter((pl.col("gcm") == gcm) & (pl.col("scen") == scen) & (pl.col("seed") == seed)
                                & (pl.col("window") == win)).select(["Cell", "quantity", "value", "valid"])
                j = m.join(ref, on=["Cell", "quantity"], how="left")
                both = j.filter(pl.col("mine").is_not_null() & pl.col("value").is_not_null())
                rel = ((both["mine"] - both["value"]).abs() / both["value"].abs().clip(1e-12)).max()
                cmp.append({"gcm": gcm, "scen": scen, "seed": seed, "window": win, "n_years": ny,
                            "n_cmp": both.height, "n_ref_missing": int(j["value"].is_null().sum()),
                            "n_mine_null_ref_notnull": int((j["mine"].is_null() & j["value"].is_not_null()).sum()),
                            "max_rel_diff": float(rel) if rel is not None else None})
                log(f"levels {cmp[-1]}")
    r["level_cmp"] = cmp
    # contrast + response C/R vs tolerance table (truth seed 1) and truth seed 2
    tol = pl.read_parquet(f"{REF}/tolerance.parquet")
    tol2 = pl.read_parquet(f"{REF}/tolerance_t2.parquet")
    g = "MPI-ESM1-2-HR"

    def lvl(scen, seed, win):
        return mine[(g, scen, seed, win)]

    def diff(a, b, name):
        return a.join(b, on=["Cell", "quantity"], suffix="_b").with_columns(
            (pl.col("mine") - pl.col("mine_b")).alias(name)).select(["Cell", "quantity", name])

    checks = []
    for target, scen, a_fn, b_fn in [
        ("c2015", "ssp370", lambda s: lvl("ssp370", s, "w2015"), lambda s: lvl("ssp126", s, "w2015")),
        ("r2015", "ssp370", lambda s: lvl("ssp370", s, "w2015"), lambda s: lvl("Historical", s, "h1985")),
        ("c2015", "ssp245", lambda s: lvl("ssp245", s, "w2015"), lambda s: lvl("ssp126", s, "w2015")),
    ]:
        for ts, tt in [(1, tol), (2, tol2)]:
            C = diff(a_fn(ts), b_fn(ts), "Cm")
            Rr = diff(a_fn(3 - ts), b_fn(3 - ts), "Rm")
            t = tt.filter((pl.col("gcm") == g) & (pl.col("scen") == scen) & (pl.col("window") == target)).select(
                ["Cell", "quantity", "C", "R"])
            j = C.join(Rr, on=["Cell", "quantity"]).join(t, on=["Cell", "quantity"], how="inner").drop_nulls()
            checks.append({"target": target, "scen": scen, "truth_seed": ts, "n": j.height,
                           "max_abs_C": float((j["Cm"] - j["C"]).abs().max()),
                           "max_abs_R": float((j["Rm"] - j["R"]).abs().max()),
                           "scale_C": float(j["C"].abs().median())})
            log(f"target {checks[-1]}")
    # truth seed 2 level for ssp245 w2015 equals seed-2 levels
    t2 = tol2.filter((pl.col("gcm") == g) & (pl.col("scen") == "ssp245") & (pl.col("window") == "w2015")).select(
        ["Cell", "quantity", "C", "R"])
    j = lvl("ssp245", 2, "w2015").join(t2, on=["Cell", "quantity"]).drop_nulls()
    checks.append({"target": "w2015_t2_C_is_seed2", "n": j.height, "max_abs": float((j["mine"] - j["C"]).abs().max())})
    r["target_cmp"] = checks
    RES["levels"] = r


# ------------------------------------------------------------------------------------------------- tolerance
def conj(t: pl.DataFrame, pred: str, tolcol: str) -> pl.DataFrame:
    """per (gcm, scen) fraction of cells whose panel106 rows ALL pass |pred - C| <= tol (pred null -> fail)."""
    x = t.filter(pl.col("quantity").is_in(PANEL106)).with_columns(
        ((pl.col(pred) - pl.col("C")).abs() <= pl.col(tolcol) * (1 + EPS)).fill_null(False).alias("ok"))
    u = x.group_by(["gcm", "scen", "Cell"]).agg(pl.col("ok").all())
    return u.group_by(["gcm", "scen"]).agg(pl.col("ok").mean().alias("frac"), pl.len().alias("n")).sort(
        ["gcm", "scen"])


def stage_tol():
    r = {}
    for scale, f in [("cell", f"{REF}/tolerance.parquet"), ("block", f"{REF}/block/tolerance.parquet"),
                     ("block_dev", f"{REF}/block_dev/tolerance.parquet")]:
        t = pl.read_parquet(f).with_columns(pl.lit(0.0).alias("ZERO"))
        rr = {"windows": sorted(t["window"].unique().to_list())}
        for win in ["h1985", "w2015", "r2015", "c2015"]:
            tw = t.filter(pl.col("window") == win)
            for col in ["allowed_cal", "allowed_cal_xg", "allowed_cal1"]:
                rep = conj(tw, "R", col)
                rr[f"{win}|{col}|replica"] = rep.to_dicts()
                if win in ("r2015", "c2015"):
                    rr[f"{win}|{col}|zero"] = conj(tw, "ZERO", col).to_dicts()
            # replica handicap: units with any panel106 R missing
            miss = (tw.filter(pl.col("quantity").is_in(PANEL106)).group_by(["gcm", "scen", "Cell"])
                    .agg(pl.col("R").is_null().any().alias("m")).group_by(["gcm", "scen"])
                    .agg(pl.col("m").mean().alias("frac_units_with_missing_R")).sort(["gcm", "scen"]))
            rr[f"{win}|missingR"] = miss.to_dicts()
        # signal-to-noise with its pure-noise null
        sn = []
        for win in ["c2015", "r2015"]:
            x = t.filter((pl.col("window") == win) & pl.col("R").is_not_null()).with_columns(
                (((pl.col("C") + pl.col("R")) / 2).abs() / (pl.col("C") - pl.col("R")).abs()).alias("sn"),
                ((pl.col("C") * pl.col("R")) > 0).alias("same_sign"))
            for (scen, q), y in x.filter(pl.col("quantity").is_in(
                    ["n_per_patch", "Wooddens_q50", "SLA_q50", "D95max_q50", "minwscal_q50", "Height_q50",
                     "agb_stand"])).group_by(["scen", "quantity"]):
                v = y["sn"].fill_nan(None).drop_nulls()
                sn.append({"window": win, "scen": scen, "quantity": q, "n": y.height,
                           "sn_med": float(v.median()) if v.len() else None,
                           "frac_gt1": float((v > 1).mean()) if v.len() else None,
                           "frac_ge3": float((v >= 3).mean()) if v.len() else None,
                           "sign_agree": float(y.filter((pl.col("C") != 0) & (pl.col("R") != 0))["same_sign"].mean())
                           if y.height else None})
        rr["sn"] = sorted(sn, key=lambda d: (d["window"], d["scen"], d["quantity"]))
        r[scale] = rr
        log(f"tol {scale} done")
    # pure-noise expectation of the S/N statistic |(C+R)/2| / |C-R| for iid normal C, R with zero mean:
    #  = 0.5 |z1| / |z2|, P(>1) = (2/pi) atan(1/2), P(>=3) = (2/pi) atan(1/6), median 0.5, sign agreement 0.5
    rng = np.random.default_rng(1)
    c, rr_ = rng.normal(size=10**6), rng.normal(size=10**6)
    s = np.abs((c + rr_) / 2) / np.abs(c - rr_)
    r["sn_pure_noise_null"] = {"median": float(np.median(s)), "frac_gt1": float((s > 1).mean()),
                               "frac_ge3": float((s >= 3).mean()), "analytic_gt1": 2 / math.pi * math.atan(0.5),
                               "analytic_ge3": 2 / math.pi * math.atan(1 / 6), "sign_agree": 0.5}
    RES["tol"] = r


# ------------------------------------------------------------------------------------------------- leakage
def stage_leak():
    r = {}
    lv = pl.read_parquet(f"{REF}/levels_long.parquet")
    a = lv.filter((pl.col("scen") == "Historical") & (pl.col("seed") == 1))
    p = a.filter(pl.col("gcm") == "MPI-ESM1-2-HR").join(a.filter(pl.col("gcm") == "ACCESS-CM2"),
                                                       on=["Cell", "quantity"], suffix="_a")
    r["hist_MPI_vs_ACCESS_identical_frac"] = float((p["value"] == p["value_a"]).mean())
    # all clean tables free of excluded windows
    bad = {}
    for f in glob.glob(f"{REF}/**/*.parquet", recursive=True):
        try:
            sch = pl.read_parquet_schema(f)
        except Exception:  # noqa: BLE001
            continue
        if "window" in sch:
            w = set(pl.read_parquet(f, columns=["window"])["window"].unique().to_list())
            hit = w & {"w2071", "w3071", "r2071", "c2071"}
            if hit:
                bad[f] = sorted(hit)
    for f in glob.glob(f"{REF}/**/*.csv", recursive=True):
        s = open(f).read()
        hit = [w for w in ["w2071", "w3071", "r2071", "c2071"] if f",{w}," in s or s.startswith(f"{w},")]
        if hit:
            bad[f] = hit
    r["clean_files_with_excluded_windows"] = bad
    # registry
    sp = pl.read_parquet(f"{XDE}/shared/registry/splits.parquet")
    r["registry_splits_late_roles"] = (sp.filter(pl.col("win").is_in(["w2071", "w3071"]))
                                       .group_by("role").len().to_dicts())
    r["registry_splits_roles"] = sp.group_by(["role"]).len().to_dicts()
    tp = pl.read_parquet(f"{XDE}/shared/registry/test_pairs.parquet")
    r["test_pairs"] = tp.select(["split", "gcm", "scen", "truth_seed", "ref_seed", "score_windows"]).to_dicts()
    # dev cells
    cells = sorted(int(x) for x in open(f"{XDE}/shared/scorer/cells_dev.txt").read().split())
    allc = sorted(lv["Cell"].unique().to_list())
    r["dev_cells_are_mod10"] = cells == [c for c in allc if c % 10 == 0]
    r["n_dev"], r["n_all"] = len(cells), len(allc)
    RES["leak"] = r


# ------------------------------------------------------------------------------------------------- probes
def run_score(args, label):
    od = f"{OUT}/probe_scores"
    cmd = [PY, f"{REPO}/scripts/explore_de_score.py", "score", "--label", label, "--out", od] + args
    p = subprocess.run(cmd, capture_output=True, text=True)
    return {"rc": p.returncode, "tail": (p.stdout + p.stderr)[-1500:], "out": f"{od}/{label}"}


def stage_probe():
    r = {}
    os.makedirs(f"{OUT}/probe_in", exist_ok=True)
    lv = pl.read_parquet(f"{REF}/levels_long.parquet")
    cells_f = f"{XDE}/shared/scorer/cells_dev.txt"
    cells = [int(x) for x in open(cells_f).read().split()]
    g = "ACCESS-CM2"
    # (P1) a stats submission that ONLY carries an excluded window
    s2 = lv.filter((pl.col("gcm") == g) & (pl.col("seed") == 2) & (pl.col("scen") == "ssp370")
                   & (pl.col("window") == "w2015") & pl.col("Cell").is_in(cells)).select(
        ["gcm", "scen", "window", "Cell", "quantity", "value"]).with_columns(pl.lit("w2071").alias("window"))
    s2.write_parquet(f"{OUT}/probe_in/only_w2071.parquet")
    r["P1_only_excluded_window"] = run_score(["--pred", f"{OUT}/probe_in/only_w2071.parquet", "--format", "stats",
                                              "--cells", cells_f, "--scope", "covered"], "P1_only_w2071")
    # (P2) the replica (seed 2) of ACCESS Historical + ssp126 + ssp370, dev cells, through the scorer -> compare
    #      its c2015 ssp370 cell-scale panel106 pass_cal with an independent recompute from the tolerance table
    rep = lv.filter((pl.col("gcm") == g) & (pl.col("seed") == 2) & pl.col("scen").is_in(
        ["Historical", "ssp126", "ssp370"]) & pl.col("Cell").is_in(cells)).filter(pl.col("valid")).select(
        ["gcm", "scen", "window", "Cell", "quantity", "value"])
    rep.write_parquet(f"{OUT}/probe_in/replica_access.parquet")
    pr = run_score(["--pred", f"{OUT}/probe_in/replica_access.parquet", "--format", "stats", "--cells", cells_f,
                    "--scope", "covered"], "P2_replica_access")
    r["P2_replica_access"] = {k: v for k, v in pr.items() if k != "tail"} | {"rc": pr["rc"]}
    if pr["rc"] == 0:
        sc = pl.read_csv(f"{pr['out']}/summary_conjunctive.csv", infer_schema_length=None).filter(
            (pl.col("panel") == "panel106"))
        r["P2_scorer"] = sc.select(["gcm", "scen", "window", "n_cells", "all_pass_cal_frac",
                                    "all_pass_cal_xg_frac"]).to_dicts()
        t = pl.read_parquet(f"{REF}/tolerance.parquet").filter(pl.col("gcm") == g)
        t = t.filter(pl.col("Cell").is_in(cells))
        mine = []
        for win in ["h1985", "w2015", "r2015", "c2015"]:
            for col in ["allowed_cal", "allowed_cal_xg"]:
                mine += [dict(d, window=win, tol=col) for d in conj(t.filter(pl.col("window") == win), "R", col)
                         .to_dicts()]
        r["P2_mine"] = mine
    else:
        r["P2_tail"] = pr["tail"]
    # (P3) zero-contrast null on dev cells via scorer: ssp370 w2015 := ssp126 w2015 (seed-1 truth levels)
    base = lv.filter((pl.col("gcm") == g) & (pl.col("seed") == 1) & pl.col("Cell").is_in(cells)
                     & pl.col("valid"))
    hist = base.filter(pl.col("scen") == "Historical")
    s126 = base.filter((pl.col("scen") == "ssp126") & (pl.col("window") == "w2015"))
    z = pl.concat([hist, s126, s126.with_columns(pl.lit("ssp370").alias("scen"))]).select(
        ["gcm", "scen", "window", "Cell", "quantity", "value"])
    z.write_parquet(f"{OUT}/probe_in/zero_contrast_access.parquet")
    pz = run_score(["--pred", f"{OUT}/probe_in/zero_contrast_access.parquet", "--format", "stats", "--cells",
                    cells_f, "--scope", "covered"], "P3_zero_contrast")
    if pz["rc"] == 0:
        sc = pl.read_csv(f"{pz['out']}/summary_conjunctive.csv", infer_schema_length=None).filter(
            (pl.col("panel") == "panel106") & pl.col("window").is_in(["c2015", "w2015", "h1985"]))
        r["P3_scorer"] = sc.select(["gcm", "scen", "window", "n_cells", "all_pass_cal_frac",
                                    "all_pass_cal_xg_frac"]).to_dicts()
        bs = f"{pz['out']}/block/summary_conjunctive.csv"
        if os.path.exists(bs):
            r["P3_scorer_block"] = pl.read_csv(bs, infer_schema_length=None).filter(
                (pl.col("panel") == "panel106") & (pl.col("window") == "c2015")).select(
                ["gcm", "scen", "window", "n_cells", "all_pass_cal_frac", "all_pass_cal_xg_frac"]).to_dicts()
    else:
        r["P3_tail"] = pz["tail"]
    # (P4) MPI ssp245 submitted WITHOUT --truth-seed: which seed is it scored against? (seed-1 levels as pred)
    m245 = lv.filter((pl.col("gcm") == "MPI-ESM1-2-HR") & (pl.col("seed") == 1) & (pl.col("scen") == "ssp245")
                     & (pl.col("window") == "w2015") & pl.col("Cell").is_in(cells) & pl.col("valid")).select(
        ["gcm", "scen", "window", "Cell", "quantity", "value"])
    m245.write_parquet(f"{OUT}/probe_in/mpi245_seed1.parquet")
    p4 = run_score(["--pred", f"{OUT}/probe_in/mpi245_seed1.parquet", "--format", "stats", "--cells", cells_f,
                    "--scope", "covered"], "P4_mpi245_default_truth")
    if p4["rc"] == 0:
        sc = pl.read_csv(f"{p4['out']}/summary_conjunctive.csv", infer_schema_length=None).filter(
            (pl.col("panel") == "panel106") & (pl.col("window") == "w2015"))
        r["P4_scorer"] = sc.select(["gcm", "scen", "window", "n_cells", "all_pass_cal_frac"]).to_dicts()
        r["P4_warning_in_log"] = any(w in p4["tail"].lower() for w in ["truth-seed", "truth seed 2", "in-sample"])
    else:
        r["P4_tail"] = p4["tail"]
    RES["probe"] = r


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    stages = sys.argv[1:] or ["excl", "levels", "tol", "leak", "probe"]
    for s in stages:
        globals()[f"stage_{s}"]()
        json.dump(RES, open(f"{OUT}/verify_{'_'.join(stages)}.json", "w"), indent=1, default=str)
    log(json.dumps(RES, indent=1, default=str)[:20000])
    log("VERIFY DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
