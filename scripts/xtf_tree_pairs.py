#!/usr/bin/env python3
"""xtf_tree_pairs.py -- ADR 0368 experiment 2 (SEPARATE EXPERIMENT, not for the paper): the at-risk tree table of
one clustered nitrogen-on leg (ADR 0342).

  python scripts/xtf_tree_pairs.py <seed> <gcm> <ssp>     -> xtf/trees/s<seed>_<gcm>_<ssp>.parquet
  python scripts/xtf_tree_pairs.py list                   -> the (seed, gcm, ssp) whose ind file exists

At-risk tree of year y (2021-2100): a tree of types 0-6 alive at the end of y-1 (the table carries trees >= 5 m).
Identity (Cell, Patch, Type, ID, SLA), asserted unique per year; every tree found in y must be exactly one year older.
Outcome died = a row in y with isdead = 1, or no row in y (0-1 trees per leg; patch_loss flags a patch-year where
no tree has a row in y -- none were found). oracle = clip(mort, 0, 1) of the tree's year-y row, the original's own
death probability, which in the merged nitrogen-on model ALREADY includes fire (trees with mort_fire 0.29 have mort
0.32 and die at 0.32; sum mort / deaths 0.93). Null without a row.
Kept: every patch-year of the held-out cells; a fixed 15 % of the other patch-years (hash of Cell, Patch, Year).
Inputs are the y-1 state (never the mort* columns) + patch summaries at y-1; the cell's climate is joined later
(xtf_tree_models.py) from clu_non/climate.

ADR 0369 (version 2 of the tables, xtf/trees_v2; same rows, extra columns): each tree's CARBON STATE, exact from the
`ind` columns of the merged model (mortality_tree_ind.c):
  r   leaf carbon / a sapling's leaf carbon (the hard kill fires below 1). leaf_c = LAI * crownarea / SLA with
      crownarea = patcharea * fpc_ind / (1 - exp(-k LAI)); sapling leaf carbon from the tree's own SLA.
  c   the bad-years counter (+1 in a year with biomass increment - turnover < 0, else 0; the hard kill fires at
      BM_INC_COUNTER_MAX = 10). Not written by the model, but inverted from mort_npp =
      mort_max / (1 + 0.2 exp(k_mort dB / leafarea)) * (1 + c): the factor lies in (0, 1/1.2] for dB >= 0 (c = 0)
      and in (1/1.2, 1) for dB < 0 (c >= 1), so q = mort_npp / mort_max > 1/1.2 marks a bad year exactly, and
      c in [q - 1, 1.2 q - 1). That interval holds one integer only up to c = 4, so c is the run of consecutive bad
      years along the tree's own history (it is that by definition); a run already going when the tree first
      appears (>= 5 m) starts at the smallest value its rows' intervals allow. Checked: share of rows whose c
      lies in its interval, and that c >= 10 or margin < 1 explains the hard kills.
      mort_max = 10^(wdmort_1 + wdmort_2 / (wooddens / 1e6)).
  columns lr_prev = log r at y-1, c_prev (state inputs); lr_y, c_y, bad_y = c_y > 0 (year-y truth, bound inputs
  and the carbon-state model's targets), hk_y = hard kill in y (mort >= 1 with the hazards + fire below 1).
Parameters: cpp -P of the merged model's par/pft_lpjmlfit.cjson + par/lpjparam_fit.cjson (/home/jamirp/lpjml-fit).
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import clu_emu_maps as M  # noqa: E402

OUT = "/p/projects/open/Jamir/esm_land_emulator_data/xtf/trees_v2"  # ADR 0369; v1 (xtf/trees) = same rows, no state
LPJ = "/home/jamirp/lpjml-fit"
SSPS = ["ssp126", "ssp370", "ssp585"]
KEY = ["Cell", "Patch", "Type", "ID", "SLA"]
TREE_F = ["Height", "Height_max", "Age", "agb", "vegc", "npp", "transp", "SLA", "Longevity", "Wooddens", "LAI",
          "stemdiam", "barkthickness", "fpc_ind", "minwscal", "D95", "D95max", "NFixing"]
INTS = {"Cell", "Year", "Type", "isdead", "Patch", "ID", "Age", "NFixing"}
KEEP_FRAC = 0.15
HAZ = ["mort_npp", "mort_age", "mort_water", "mort_temp", "mort_fire"]


def _cpp_json(path):
    import json
    import re
    import subprocess

    s = subprocess.run(["cpp", "-P", "-I", LPJ, path], capture_output=True, text=True, check=True, cwd=LPJ).stdout
    return json.loads(re.sub(r",(\s*[}\]])", r"\1", s))


def pft_params():
    pp = _cpp_json(f"{LPJ}/par/pft_lpjmlfit.cjson")
    par = _cpp_json(f"{LPJ}/par/lpjparam_fit.cjson")
    rows = [dict(Type=i, k=float(p["lightextcoeff"]), lai_sapl=float(p["lai_sapl"]), allom1=float(p["allom1"]),
                 wood_sapl=float(p["wood_sapl"]), kpr=float(p["kpr"]), k_latosa=float(p["k_latosa"]),
                 wd1=float(p["wdmort_1"]), wd2=float(p["wdmort_2"])) for i, p in enumerate(pp[:7])]  # fmt: skip
    return pl.DataFrame(rows).with_columns(pl.col("Type").cast(pl.Int32)), float(par["patcharea"])


def with_state(d):
    """+ r (leaf carbon / sapling's), c (bad-years counter, inverted from mort_npp), hk (hard kill)."""
    prm, patcharea = pft_params()
    d = d.join(prm, on="Type", how="left")
    ca = patcharea * pl.col("fpc_ind") / (1.0 - (-pl.col("k") * pl.col("LAI")).exp())
    leaf = pl.col("LAI") * ca / pl.col("SLA")
    h = pl.col("kpr") * 0.5
    sapl = ((pl.col("lai_sapl") * pl.col("allom1") * pl.col("wood_sapl").pow(h)
             * (4.0 * pl.col("SLA") / np.pi / pl.col("k_latosa")).pow(h) / pl.col("SLA"))
            .pow(2.0 / (2.0 - pl.col("kpr"))))  # fmt: skip
    q = pl.col("mort_npp") / (10.0 ** (pl.col("wd1") + pl.col("wd2") / (pl.col("Wooddens") / 1e6)))
    hz = pl.sum_horizontal(HAZ)
    tk = KEY  # one tree
    d = d.with_columns(q.alias("_q"), ((q > 1 / 1.2 + 1e-4) | (pl.col("mort_npp") >= 1)).alias("_bad")).sort(
        tk + ["Year"])
    d = d.with_columns((~pl.col("_bad")).cast(pl.Int32).cum_sum().over(tk).alias("_rid"))
    d = d.with_columns(pl.int_range(pl.len()).over(tk + ["_rid"]).alias("_pos"))
    # leading run (bad years since before the tree's first row): offset = the smallest start its intervals allow
    lead = pl.when((pl.col("_rid") == 0) & (pl.col("mort_npp") < 1)).then(pl.col("_q") - 1 - pl.col("_pos"))
    d = d.with_columns((lead.max().over(tk) - 1e-4).ceil().fill_null(1).clip(lower_bound=1).alias("_c0"))
    c = (pl.when(~pl.col("_bad")).then(0).when(pl.col("_rid") > 0).then(pl.col("_pos"))
         .otherwise(pl.col("_c0") + pl.col("_pos")))  # fmt: skip
    return d.with_columns(
        (leaf / sapl).alias("r"),
        c.cast(pl.Float32).alias("c"),
        ((pl.col("mort") >= 1) & (hz < 1)).alias("hk"),
    ).drop(prm.columns[1:])


def ind_path(seed, gcm, ssp):
    return f"{M.leg_dir(seed, gcm)}/output/ind_{ssp}.csv"


def build(seed, gcm, ssp):
    t0 = time.time()
    p = ind_path(seed, gcm, ssp)
    with open(p) as fh:
        hdr = fh.readline().strip().split(",")
    d = (pl.scan_csv(p, schema_overrides={c: pl.Int32 if c in INTS else pl.Float64 for c in hdr})
         .filter((pl.col("Type") <= 6) & pl.col("Year").is_between(2020, 2100))
         .select(["Year", "isdead", "mort"] + HAZ + list(dict.fromkeys(KEY + TREE_F)))
         .collect())  # fmt: skip
    d = with_state(d)
    # counter check: the share of bad-year rows (uncapped) whose c lies in the interval [q - 1, 1.2 q - 1)
    ck = d.filter(pl.col("_bad") & (pl.col("mort_npp") < 1))
    ok = ((ck["c"] >= ck["_q"] - 1 - 1e-3) & (ck["c"] < 1.2 * ck["_q"] - 1 + 1e-3)).mean()
    frac_int = d["_bad"].mean()
    d = d.drop("_q", "_bad", "_rid", "_pos", "_c0")
    dup = d.select(KEY + ["Year"]).is_duplicated().sum()
    assert dup == 0, f"{dup} duplicated tree identities"
    prev = d.filter(pl.col("isdead") == 0).drop(["isdead", "mort", "hk"] + HAZ).rename({"r": "r_prev", "c": "c_prev"})
    prev = prev.with_columns((pl.col("Year") + 1).alias("Year")).filter(pl.col("Year") <= 2100)
    cur = d.select(KEY + ["Year", pl.col("isdead").alias("dead_y"), pl.col("Age").alias("age_y"), "mort",
                          "mort_fire", pl.col("npp").alias("npp_y"), pl.col("r").alias("r_y"),
                          pl.col("c").alias("c_y"), pl.col("hk").alias("hk_y")])  # fmt: skip
    j = prev.join(cur, on=KEY + ["Year"], how="left")
    assert j.height == prev.height
    found = j.filter(pl.col("dead_y").is_not_null())
    bad = (found["age_y"] != found["Age"] + 1).sum()
    assert bad == 0, f"{bad} found trees are not exactly one year older"
    pk = ["Cell", "Patch", "Year"]
    j = j.with_columns(
        (pl.col("dead_y").is_null() | (pl.col("dead_y") == 1)).alias("died"),
        pl.col("dead_y").is_null().all().over(pk).alias("patch_loss"),
        pl.col("mort").clip(0, 1).alias("oracle"),  # already includes fire in this model (measured, ADR 0368 2a)
    )
    gone = j.filter(pl.col("dead_y").is_null() & ~pl.col("patch_loss")).height  # counted as deaths, reported
    assert gone <= 1e-5 * j.height, f"{gone} trees missing in y outside a whole-patch loss"
    # patch summaries at y-1 (over the at-risk trees)
    j = j.sort(pk + ["Height"], descending=[False, False, False, True]).with_columns(
        pl.len().over(pk).alias("pt_n"),
        pl.col("fpc_ind").sum().over(pk).alias("pt_fpc"),
        pl.col("agb").sum().over(pk).alias("pt_agb"),
        pl.col("npp").mean().over(pk).alias("pt_npp"),
        ((pl.col("Height").rank("average").over(pk) - 1) / pl.len().over(pk).clip(lower_bound=2).sub(1))
        .alias("pt_hrank"),
        (pl.col("fpc_ind").cum_sum().over(pk) - pl.col("fpc_ind")).alias("pt_fpc_taller"),
    ).with_columns((pl.col("npp") / pl.col("pt_npp").abs().clip(lower_bound=1e-3)).alias("pt_npp_rel"))
    ho = M.cells().select("Cell", "heldout")
    j = j.join(ho, on="Cell", how="left")
    h = (pl.col("Cell").cast(pl.UInt64) * 1_000_003 + pl.col("Patch").cast(pl.UInt64) * 10_007
         + pl.col("Year").cast(pl.UInt64)).hash(seed=368) % 1000  # fmt: skip
    j = j.filter(pl.col("heldout") | (h < int(KEEP_FRAC * 1000)))
    lg = lambda c: pl.col(c).clip(lower_bound=1e-3).log()  # noqa: E731
    j = j.with_columns(lg("r_prev").alias("lr_prev"), lg("r_y").alias("lr_y"),
                       (pl.col("c_y") > 0).cast(pl.Float32).alias("bad_y"))  # fmt: skip
    cols = ["Year"] + KEY[:-1] + TREE_F + [c for c in j.columns if c.startswith("pt_")] + [
        "heldout", "died", "patch_loss", "oracle", "npp_y",  # npp_y: the tree's own year-y NPP (bound input, 2b)
        "lr_prev", "c_prev", "lr_y", "c_y", "bad_y", "hk_y"]  # ADR 0369 carbon state
    j = j.select(cols).with_columns(pl.col(pl.Float64).cast(pl.Float32))
    os.makedirs(OUT, exist_ok=True)
    j.write_parquet(f"{OUT}/s{seed}_{gcm}_{ssp}.parquet")
    f = j.filter(~pl.col("patch_loss"))
    print(f"s{seed} {gcm} {ssp}: {j.height:,} at-risk trees kept ({j['heldout'].sum():,} held-out cells), "
          f"death rate {j['died'].mean():.4f}, patch-loss share {j['patch_loss'].mean():.4f}, "
          f"lone missing trees {gone}, "
          f"oracle calibration (no patch loss) {f['oracle'].sum() / max(f['died'].sum(), 1):.3f}; "
          f"bad-year share {frac_int:.4f}, counter inside its interval for {ok:.5f} of bad-year rows; "
          f"hard kills {j['hk_y'].sum():,} of {j['died'].sum():,} deaths, of them leaf carbon < sapling's "
          f"{j.filter(pl.col('hk_y'))['lr_y'].lt(0).mean():.3f}, counter >= 10 "
          f"{j.filter(pl.col('hk_y'))['c_y'].ge(10).mean():.3f} "
          f"({time.time() - t0:.0f}s)", flush=True)  # fmt: skip


def legs_available():
    return [(s, g, t) for s in (2, 3) for g in M.GCMS for t in SSPS if os.path.exists(ind_path(s, g, t))]


if __name__ == "__main__":
    if sys.argv[1] == "list":
        for s, g, t in legs_available():
            print(s, g, t)
    else:
        s, g, t = int(sys.argv[1]), sys.argv[2], sys.argv[3]
        if os.path.exists(f"{OUT}/s{s}_{g}_{t}.parquet"):
            print("exists, skipped")
        else:
            build(s, g, t)
