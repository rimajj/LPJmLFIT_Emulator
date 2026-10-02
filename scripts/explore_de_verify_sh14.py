#!/usr/bin/env python
"""explore_de_verify_sh14.py -- adversarial verifier for work item SH14 (scorer amendments).

Line X, Germany emulator exploration, round 2 (2026-10-01). Independent recomputation from levels_long and the raw
dev tree tables -- it does NOT import explore_de_score's scoring functions (only path constants):
  V1  contrasts c2015/c2071 recomputed from levels_long == tolerance{,_t2}.parquet C and R (both truth seeds);
      the role swap of truth seed 2 for levels; allowed_cell_abs formula; replica passes it at 1.0.
  V2  common-random-numbers dependence of the contrast tolerance: within-seed two-leg contrast noise vs the
      noise of a contrast whose two legs come from DIFFERENT seeds (what an emulator whose scenario legs do
      not share randomness / history would show).
  V3  frozen 2014 roster statistics recomputed from the raw dev tree table for a few cells.
  V4  registry fold blocks vs the scorer's blocks (does a scorer block span several folds?); fold-5 dev count.
  V5  dev-block c2071 uniform (Germany-mean) null recomputed from levels_long + block_dev mask + tolerance,
      and its split by scenario (ssp370 vs ssp245, the latter = scenario + binary).
  V6  aggregate *_same test: share of determined rows where the 10 % floor binds (else the replica's 1.00 is
      by construction and an equally good independent run passes ~0.5).
  V7  calibration circularity: the "independent run" estimate for allowed_cal vs the replica's own pass rate.
Writes /p/tmp/jamirp/X_de/_reports/r2_verify_SH14_data.json.
"""

from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_reference as R  # noqa: E402  (constants only)

REF = R.OUT
OUTJ = f"{R.XDE}/_reports/r2_verify_SH14_data.json"
res: dict = {}


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def maxrel(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    if not ok.any():
        return None
    return float(np.max(np.abs(a[ok] - b[ok]) / np.maximum(np.abs(b[ok]), 1e-12)))


lv = pl.read_parquet(f"{REF}/levels_long.parquet")
log(f"levels_long {lv.height}")

# ---------------- V1 contrasts + role swap
k = ["gcm", "scen", "window", "Cell", "quantity"]
v1 = {}
for ts in (1, 2):
    ots = 3 - ts
    sfx = "" if ts == 1 else "_t2"
    tol = pl.scan_parquet(f"{REF}/tolerance{sfx}.parquet").filter(pl.col("target_kind").is_in(["contrast", "level"])) \
        .select(k + ["target_kind", "C", "R", "allowed_cell_abs"]).collect()
    rec = {}
    for cname, w in {"c2071": "w2071", "c2015": "w2015"}.items():
        base = lv.filter((pl.col("scen") == "ssp126") & (pl.col("window") == w) & pl.col("valid")).select(
            ["gcm", "seed", "Cell", "quantity", pl.col("value").alias("B")])
        fut = lv.filter((pl.col("scen").is_in(["ssp370", "ssp245"])) & (pl.col("window") == w) & pl.col("valid"))
        d = fut.join(base, on=["gcm", "seed", "Cell", "quantity"], how="inner").with_columns(
            (pl.col("value") - pl.col("B")).alias("D"))
        c = d.filter(pl.col("seed") == ts).select(["gcm", "scen", "Cell", "quantity", pl.col("D").alias("Cv")])
        r = d.filter(pl.col("seed") == ots).select(["gcm", "scen", "Cell", "quantity", pl.col("D").alias("Rv")])
        cr = c.join(r, on=["gcm", "scen", "Cell", "quantity"], how="left")
        t = tol.filter(pl.col("window") == cname).join(cr, on=["gcm", "scen", "Cell", "quantity"], how="full",
                                                        coalesce=True)
        rec[cname] = {"rows_tol": int(tol.filter(pl.col("window") == cname).height), "rows_mine": cr.height,
                      "C_missing_in_tol": int(t["C"].is_null().sum()), "C_missing_mine": int(t["Cv"].is_null().sum()),
                      "maxrel_C": maxrel(t["C"].to_numpy(), t["Cv"].to_numpy()),
                      "maxrel_R": maxrel(t["R"].to_numpy(), t["Rv"].to_numpy()),
                      "R_null_mismatch": int((t["R"].is_null() != t["Rv"].is_null()).sum())}
    # levels: C must be seed ts
    lt = tol.filter(pl.col("target_kind") == "level")
    s_ts = lv.filter((pl.col("seed") == ts) & pl.col("valid")).select(k + [pl.col("value").alias("Cv")])
    s_o = lv.filter((pl.col("seed") == ots) & pl.col("valid")).select(k + [pl.col("value").alias("Rv")])
    j = lt.join(s_ts, on=k, how="left").join(s_o, on=k, how="left")
    rec["levels_maxrel_C"] = maxrel(j["C"].to_numpy(), j["Cv"].to_numpy())
    rec["levels_maxrel_R"] = maxrel(j["R"].to_numpy(), j["Rv"].to_numpy())
    # allowed_cell_abs recomputed + replica pass
    isf = j["quantity"].str.starts_with("share_").to_numpy()
    C, Rv, a = j["C"].to_numpy(), j["R"].to_numpy(), j["allowed_cell_abs"].to_numpy()
    mine = np.maximum(0.1 * np.abs(C), np.abs(C - Rv))
    mine = np.where(isf, np.maximum(mine, 0.005), mine)
    rec["levels_allowed_cell_abs_maxrel"] = maxrel(a, mine)
    ok = np.isfinite(Rv)
    rec["levels_replica_pass_cell_abs"] = float(np.mean(np.abs(Rv[ok] - C[ok]) <= a[ok] * (1 + 1e-9)))
    # truncated member excluded under truth seed 2?
    rec["MPI_ssp370_w3071_rows"] = int(lt.filter((pl.col("gcm") == "MPI-ESM1-2-HR") & (pl.col("scen") == "ssp370")
                                                 & (pl.col("window") == "w3071")).height)
    v1[f"truth_seed_{ts}"] = rec
    del tol, lt, j
res["V1_contrasts_and_roles"] = v1
log(f"V1 {json.dumps(v1)[:900]}")

# ---------------- V2 common random numbers: same-seed vs cross-seed contrast noise
v2 = []
for w in ["w2015", "w2071"]:
    x = lv.filter((pl.col("window") == w) & pl.col("scen").is_in(["ssp126", "ssp370", "ssp245"]) & pl.col("valid"))
    p = x.pivot(on=["scen", "seed"], index=["gcm", "Cell", "quantity"], values="value")
    cols = p.columns
    for sc in ["ssp370", "ssp245"]:
        need = [f'{{"{sc}",1}}', f'{{"{sc}",2}}', '{"ssp126",1}', '{"ssp126",2}']
        if not all(n in cols for n in need):
            # polars names pivot columns from a list of on-columns like {"ssp370",1}
            v2.append({"window": w, "scen": sc, "error": f"pivot cols {cols[:8]}"})
            continue
        q = p.drop_nulls(need)
        a1, a2, b1, b2 = (q[n].to_numpy() for n in need)
        same = np.abs((a1 - b1) - (a2 - b2))  # |C - R| of the within-seed contrast (what the tolerance uses)
        cross = np.abs((a1 - b2) - (a2 - b1))  # legs from different seeds
        df = q.select(["gcm", "quantity"]).with_columns(pl.Series("same", same), pl.Series("cross", cross))
        g = df.group_by(["gcm", "quantity"]).agg(pl.col("same").median().alias("med_same"),
                                                  pl.col("cross").median().alias("med_cross"))
        g = g.with_columns((pl.col("med_cross") / pl.col("med_same")).alias("ratio"))
        for gcm in g["gcm"].unique().sort().to_list():
            gg = g.filter(pl.col("gcm") == gcm)
            v2.append({"window": w, "scen": sc, "gcm": gcm,
                       "ratio_cross_over_same_median_over_quantities": float(gg["ratio"].median()),
                       "ratio_min": float(gg["ratio"].min()), "ratio_max": float(gg["ratio"].max()),
                       "n_per_patch": float(gg.filter(pl.col("quantity") == "n_per_patch")["ratio"][0]),
                       "agb_stand": float(gg.filter(pl.col("quantity") == "agb_stand")["ratio"][0]),
                       "Wooddens_q50": float(gg.filter(pl.col("quantity") == "Wooddens_q50")["ratio"][0])})
res["V2_common_random_numbers"] = v2
log(f"V2 {json.dumps(v2)[:1500]}")

# ---------------- V3 frozen recompute from raw dev table
v3 = {}
fz = pl.read_parquet(f"{REF}/frozen/MPI-ESM1-2-HR_s1_y2014.parquet")
raw = pl.read_parquet(f"{R.XDE}/ind_dev/MPI-ESM1-2-HR_Historical_s1_h1985.parquet")
liv = raw.filter((pl.col("Year") == 2014) & (pl.col("Type") <= 6) & (pl.col("isdead") == 0)
                 & (pl.col("Height") >= R.HMIN))
cells = sorted(liv["Cell"].unique().to_list())[::90][:10]
rows = []
for c in cells:
    t = liv.filter(pl.col("Cell") == c)
    f = fz.filter(pl.col("Cell") == c)
    rows.append({"Cell": c, "npp_mine": t.height / R.NPATCH, "npp_frozen": float(f["n_per_patch"][0]),
                 "agb_stand_mine": float(t["agb"].cast(pl.Float64).sum() / R.NPATCH),
                 "agb_stand_frozen": float(f["agb_stand"][0]),
                 "share3_mine": float((t["Type"] == 3).mean()), "share3_frozen": float(f["share_3"][0]),
                 "SLA_q50_mine": float(np.quantile(t["SLA"].to_numpy().astype(float), 0.5)),
                 "SLA_q50_frozen": float(f["SLA_q50"][0])})
v3["rows"] = rows
v3["npp_maxrel"] = maxrel([r["npp_mine"] for r in rows], [r["npp_frozen"] for r in rows])
v3["agb_maxrel"] = maxrel([r["agb_stand_mine"] for r in rows], [r["agb_stand_frozen"] for r in rows])
v3["SLA_q50_maxrel"] = maxrel([r["SLA_q50_mine"] for r in rows], [r["SLA_q50_frozen"] for r in rows])
res["V3_frozen"] = v3
log(f"V3 {json.dumps({x: v3[x] for x in v3 if x != 'rows'})}")

# ---------------- V4 folds vs scorer blocks
fm = pl.read_parquet(f"{R.XDE}/shared/registry/folds.parquet")
bm = pl.read_parquet(f"{REF}/block/map.parquet")
bmd = pl.read_parquet(f"{REF}/block_dev/map.parquet")
j = bm.join(fm.select(["Cell", "fold", pl.col("block").alias("reg_block")]), on="Cell")
span = j.group_by("block").agg(pl.col("fold").n_unique().alias("nf"))
jd = bmd.join(fm.select(["Cell", "fold"]), on="Cell")
spand = jd.group_by("block").agg(pl.col("fold").n_unique().alias("nf"), pl.len().alias("n"))
f5 = [int(x) for x in open(f"{R.XDE}/shared/scorer/cells_fold5_dev.txt").read().split()]
dev = [int(x) for x in open(f"{R.XDE}/shared/scorer/cells_dev.txt").read().split()]
res["V4_folds"] = {
    "scorer_blocks_all": int(bm["block"].n_unique()), "registry_blocks": int(fm["block"].n_unique()),
    "scorer_blocks_spanning_gt1_fold_all": int((span["nf"] > 1).sum()),
    "scorer_blocks_spanning_gt1_fold_dev": int((spand["nf"] > 1).sum()),
    "registry_block_equals_scorer_block": bool(
        j.group_by("block").agg(pl.col("reg_block").n_unique().alias("u"))["u"].max() == 1
        and j.group_by("reg_block").agg(pl.col("block").n_unique().alias("u"))["u"].max() == 1),
    "fold5_dev_cells": len(f5), "fold5_dev_eq_registry": sorted(f5) == sorted(
        fm.filter((pl.col("fold") == 5) & (pl.col("Cell") % 10 == 0))["Cell"].to_list()),
    "dev_cells": len(dev), "dev_all_mod10": all(c % 10 == 0 for c in dev),
    "fold5_dev_scorer_blocks_touched": int(jd.filter(pl.col("fold") == 5)["block"].n_unique()),
    "fold5_dev_scorer_blocks_entirely_fold5": int(
        jd.group_by("block").agg((pl.col("fold") == 5).all().alias("a"))["a"].sum()),
}
log(f"V4 {res['V4_folds']}")

# ---------------- V5 dev-block c2071 uniform null recompute
st = pl.read_parquet(f"{R.XDE}/climate/cell_static.parquet").select([pl.col("Cell").cast(pl.Int32),
                                                                       "area_km2_approx"])
t1 = lv.filter((pl.col("seed") == 1) & pl.col("valid")).join(st, on="Cell")
gm = t1.group_by(["gcm", "scen", "window", "quantity"]).agg(
    ((pl.col("value") * pl.col("area_km2_approx")).sum() / pl.col("area_km2_approx").sum()).alias("m"))
g126 = gm.filter((pl.col("scen") == "ssp126") & (pl.col("window") == "w2071")).select(
    ["gcm", "quantity", pl.col("m").alias("m126")])
gc = gm.filter(pl.col("scen").is_in(["ssp370", "ssp245"]) & (pl.col("window") == "w2071")).join(
    g126, on=["gcm", "quantity"]).with_columns((pl.col("m") - pl.col("m126")).alias("E")).select(
    ["gcm", "scen", "quantity", "E"])
v5 = {}
for scale in ["block_dev", "block"]:
    bt = pl.scan_parquet(f"{REF}/{scale}/tolerance.parquet").filter(
        (pl.col("window") == "c2071") & pl.col("quantity").is_in(R.PANEL106)).select(
        ["gcm", "scen", "Cell", "quantity", "C", "R", "allowed_cal", "allowed", "allowed_cell_abs"]).collect()
    x = bt.join(gc, on=["gcm", "scen", "quantity"], how="left")
    out = {}
    for col in ["allowed_cal", "allowed", "allowed_cell_abs"]:
        y = x.with_columns(((pl.col("E") - pl.col("C")).abs() <= pl.col(col) * (1 + 1e-9)).fill_null(False)
                           .alias("ok"),
                           ((pl.col("R") - pl.col("C")).abs() <= pl.col(col) * (1 + 1e-9)).fill_null(False)
                           .alias("okR"),
                           (pl.col("C").abs() <= pl.col(col) * (1 + 1e-9)).alias("ok0"))
        cj = y.group_by(["gcm", "scen", "Cell"]).agg(pl.col("ok").all(), pl.col("okR").all(), pl.col("ok0").all()) \
            .group_by(["gcm", "scen"]).agg(pl.col("ok").mean().alias("uniform"), pl.col("okR").mean().alias("replica"),
                                           pl.col("ok0").mean().alias("zero"), pl.len().alias("n_blocks")) \
            .sort(["gcm", "scen"])
        out[col] = cj.to_dicts()
        out[col + "_median_all4"] = {c: float(cj[c].median()) for c in ["uniform", "replica", "zero"]}
        cs = cj.filter(pl.col("scen") == "ssp370")
        out[col + "_median_ssp370_only"] = {c: float(cs[c].median()) for c in ["uniform", "replica", "zero"]}
        # per-quantity marginal: fraction of (target, block) rows where allowed_cal >= |C| (zero passes)
        out[col + "_frac_rows_zero_passes"] = float(y["ok0"].mean())
    v5[scale] = out
res["V5_block_c2071_nulls"] = v5
log(f"V5 {json.dumps({s: {c: v5[s][c] for c in v5[s] if 'median' in c or 'frac' in c} for s in v5})}")

# ---------------- V6 aggregate *_same: does the 10 % floor bind on determined rows?
v6 = {}
for cs_name, d in [("dev907", "scores_dev"), ("all9065", "scores"), ("fold5dev", "scores_fold5dev")]:
    f = f"{REF}/{d}/null_a_other_seed/aggregate_response.csv"
    if not os.path.exists(f):
        continue
    a = pl.read_csv(f, infer_schema_length=None).filter(pl.col("window").is_in(["c2071", "r2071", "c2015", "r2015"]))
    a = a.filter(pl.col("determined_same") == True)  # noqa: E712
    floor_binds = (0.1 * a["aggC_same"].abs()) >= (a["aggC_same"] - a["aggR_same"]).abs()
    v6[cs_name] = {"n_determined_rows": a.height, "frac_floor_binds": float(floor_binds.mean()) if a.height else None,
                   "expected_pass_independent_run_upper": (float(floor_binds.mean() + 0.5 * (1 - floor_binds.mean()))
                                                           if a.height else None),
                   "replica_pass_same": float(a["pass_same"].mean()) if a.height else None}
    for w in ["c2071", "r2071"]:
        b = a.filter(pl.col("window") == w)
        fb = (0.1 * b["aggC_same"].abs()) >= (b["aggC_same"] - b["aggR_same"]).abs()
        v6[cs_name][f"{w}_n_det"] = b.height
        v6[cs_name][f"{w}_frac_floor_binds"] = float(fb.mean()) if b.height else None
res["V6_aggregate_same"] = v6
log(f"V6 {v6}")

# ---------------- V7 calibration circularity at cell scale (levels h1985, panel106)
t = pl.scan_parquet(f"{REF}/tolerance.parquet").filter(
    (pl.col("window") == "h1985") & pl.col("quantity").is_in(R.PANEL106) & pl.col("R").is_not_null()).select(
    ["Cell", "quantity", "C", "R", "allowed_cal"]).collect()
okr = ((pl.col("R") - pl.col("C")).abs() <= pl.col("allowed_cal") * (1 + 1e-9))
marg = t.select(okr.mean()).item()
conj = t.group_by("Cell").agg(okr.all().alias("a"))["a"].mean()
res["V7_calibration"] = {"replica_marginal_pass_h1985_MPI+ACCESS": float(marg), "replica_conj_h1985": float(conj),
                         "note": "builder's independent-run marginal for allowed_cal, cell h1985 = 0.99709; "
                                 "conj (product of marginals) 0.913"}
log(f"V7 {res['V7_calibration']}")

json.dump(res, open(OUTJ, "w"), indent=1, default=str)
print("=== DONE explore_de_verify_sh14 ===", flush=True)
