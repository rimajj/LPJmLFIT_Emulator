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
"""

from __future__ import annotations

import os
import sys
import time

import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import clu_emu_maps as M  # noqa: E402

OUT = "/p/projects/open/Jamir/esm_land_emulator_data/xtf/trees"
SSPS = ["ssp126", "ssp370", "ssp585"]
KEY = ["Cell", "Patch", "Type", "ID", "SLA"]
TREE_F = ["Height", "Height_max", "Age", "agb", "vegc", "npp", "transp", "SLA", "Longevity", "Wooddens", "LAI",
          "stemdiam", "barkthickness", "fpc_ind", "minwscal", "D95", "D95max", "NFixing"]
INTS = {"Cell", "Year", "Type", "isdead", "Patch", "ID", "Age", "NFixing"}
KEEP_FRAC = 0.15


def ind_path(seed, gcm, ssp):
    return f"{M.leg_dir(seed, gcm)}/output/ind_{ssp}.csv"


def build(seed, gcm, ssp):
    t0 = time.time()
    p = ind_path(seed, gcm, ssp)
    with open(p) as fh:
        hdr = fh.readline().strip().split(",")
    d = (pl.scan_csv(p, schema_overrides={c: pl.Int32 if c in INTS else pl.Float64 for c in hdr})
         .filter((pl.col("Type") <= 6) & pl.col("Year").is_between(2020, 2100))
         .select(["Year", "isdead", "mort", "mort_fire"] + list(dict.fromkeys(KEY + TREE_F)))
         .collect())  # fmt: skip
    dup = d.select(KEY + ["Year"]).is_duplicated().sum()
    assert dup == 0, f"{dup} duplicated tree identities"
    prev = d.filter(pl.col("isdead") == 0).drop("isdead", "mort", "mort_fire")
    prev = prev.with_columns((pl.col("Year") + 1).alias("Year")).filter(pl.col("Year") <= 2100)
    cur = d.select(KEY + ["Year", pl.col("isdead").alias("dead_y"), pl.col("Age").alias("age_y"), "mort",
                          "mort_fire"])  # fmt: skip
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
    cols = ["Year"] + KEY[:-1] + TREE_F + [c for c in j.columns if c.startswith("pt_")] + [
        "heldout", "died", "patch_loss", "oracle"]
    j = j.select(cols).with_columns(pl.col(pl.Float64).cast(pl.Float32))
    os.makedirs(OUT, exist_ok=True)
    j.write_parquet(f"{OUT}/s{seed}_{gcm}_{ssp}.parquet")
    f = j.filter(~pl.col("patch_loss"))
    print(f"s{seed} {gcm} {ssp}: {j.height:,} at-risk trees kept ({j['heldout'].sum():,} held-out cells), "
          f"death rate {j['died'].mean():.4f}, patch-loss share {j['patch_loss'].mean():.4f}, "
          f"lone missing trees {gone}, "
          f"oracle calibration (no patch loss) {f['oracle'].sum() / max(f['died'].sum(), 1):.3f} "
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
