#!/usr/bin/env python3
"""explore_de_sh_trans.py — LINE X, Germany data-driven emulator, shared item SH3: PER-TREE TRANSITION TABLE.

One row per tree (Type <= 6) LIVING at year y (printed, isdead == 0), with y -> y+1 a usable pair of one continuous
trajectory (SH0 registry v2 `segments.pair_ok`). It carries the tree's state, recovered hidden state, fluxes and
patch / cell context at y, the segment flags of y+1, and the TARGETS at y+1 (fate + the grown state of a present
stem). Every track trains on this table, so it is built once.

    member windows (SH0 registry v2, excluded windows refused):
      Historical  h1985: pairs y = 1985..2013, stored once under traj = Historical
      ssp         w2015: pairs y = 2014..2043; the 2014 rows come from the same GCM/seed's Historical table
    never 2044 -> 2071 (no table for 2045-2070) and never an excluded window (owner decision 2026-10-01).

KEY (trait-extended; the raw (Cell, Patch, Type, ID) key has 2 779 duplicates in 569 M tree rows, 0 with traits):
    (Cell, Patch, Type, ID, sla_i = round(float64(SLA) * 1e9), wd_i = round(float64(Wooddens) * 10))

HIDDEN STATE: the bad-growth counter c, growth efficiency G and the water-stress integral W are recovered from each
printed row with the SH2 rule library (explore_de_sh_rules), carrying c_prev along the trajectory from its first
year (1985), so the one ambiguous counter band (r ~ 5) is resolved exactly as SH2 gates it.

COLUMNS
  ids        member, gcm, traj, seed, Year (= y), Cell, Patch, Type, ID, sla_i, wd_i, u_hash (uniform [0,1) hash of
             key + member: THE shared subsampling column, constant over a tree's life)
  traits     SLA, Wooddens, D95max, minwscal, Longevity, beta_root
  state y    Height, agb, vegc, LAI, fpc_ind, D95, Age, c_y, G_y, cenG_y, W_y, cenW_y
  fluxes y   npp, transp, wscal_mean, mort_npp, mort_age, mort_water, mort_temp, mort
  history    d_agb_prev (agb_y - agb_{y-1}; null if absent at y-1), is_new_y (absent at y-1; null in the chain's
             first year), is_reentry_y (absent at y-1 but printed at some earlier year of the chain),
             is_recruit_y = is_new_y and not is_reentry_y (never printed before)
  patch y    n_live, sum_fpc, sum_agb, height_rank (1 = tallest living stem of the patch), fpc_above (sum fpc_ind of
             STRICTLY taller living stems), grass<t>_{fpc,LAI,agb} for every grass Type t present in the data
             (nullable: no grass row in that patch-year)
  cell y     cell_stems_per_patch (= living stems / npatch, npatch from the registry), cell_share_t0..t6
  flags y+1  rh_on_y1, bin_feb2026_y1 (SH0 segments on (gcm, traj, seed, Year = y+1))
  targets    fate_y1 (0 alive, 1 flagged dead, 2 absent = not printed: dropped below the 5 m cut);
             for present stems (fate 0 or 1, both grew): Height_y1, agb_y1, vegc_y1, LAI_y1, fpc_ind_y1, D95_y1,
             npp_y1, transp_y1, wscal_mean_y1, mort_npp_y1, mort_age_y1, mort_water_y1, mort_temp_y1, mort_y1,
             hard_y1 (mort >= 1), c_y1, G_y1, cenG_y1, W_y1, cenW_y1
  Floats are stored float32 (the source precision); cast to float64 before every aggregate.
  Climate is NOT materialised: join_climate() (this module) is the ONLY feature-join code any track may use.

LAYOUT  shared/trans/<cellset>/<member>/cb=<k>/y<YYYY>.parquet  (cellset dev: cb=dev, one source file;
        cellset full: one cb per source cell-block partition of /p/tmp/jamirp/X_de/ind/...).
        Read a member with pl.scan_parquet(f"{TRANS}/<cellset>/<member>/**/*.parquet").

GATES (per member, written to <cellset>/<member>/_gates.json; aggregated by `gates`):
  key_unique         n_unique(key) == n tree rows, every year (0 duplicates)
  cells_present      every (Cell, Year) of the cell set present among the tree rows
  age_plus_one       Age_y1 == Age_y + 1 on 100 % of present pairs
  traits_identical   D95max, minwscal, Longevity, beta_root bit-identical on 100 % of present pairs
  dead_not_reappear  no flagged-dead stem at y is printed at y+1
  counter_recursion  c_y1 in {0, c_y + 1} (pairs with an uncensored counter on both sides): failure rate <= 1e-5
  rows_eq_living     table rows at y == living tree rows (Type <= 6, isdead == 0) of the source at y (independent scan)

STAGES
  build   --cellset dev|full [--member M ...] [--cb K ...]   build (idempotent; skips finished cb/years unless --force)
  gates   --cellset dev|full                                 aggregate per-member gates -> <cellset>/_gates.json
  submit  --cellset dev|full                                 write + sbatch a SLURM array over (member[, cb])
  smoke   [--member M]                                       dev, Cell % 100 == 0, first 5 pairs -> trans/_smoke
Nothing Germany-specific is hard-coded: cell sets, patch count, PFT/grass types, years and windows come from the
registry and the tables. CO2 and wind are never inputs.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
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

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
TRANS = os.environ.get("SH3_OUT", os.path.join(XDE, "shared", "trans"))
REG = os.path.join(XDE, "shared", "registry")
CLIM = os.path.join(XDE, "climate", "cell_year.parquet")
EXT = os.path.join(XDE, "shared", "climate", "cell_year_ext.parquet")
STATUS = os.path.join(XDE, "_status", "SH3.md")
PY = os.environ.get("XDE_PY", "/home/jamirp/.conda/envs/py311_new/bin/python")

MAX_TREE_TYPE = 6
KEY = ["Cell", "Patch", "Type", "ID", "sla_i", "wd_i"]
TRAITS = ["SLA", "Wooddens", "D95max", "minwscal", "Longevity", "beta_root"]
STATE = ["Height", "agb", "vegc", "LAI", "fpc_ind", "D95", "Age"]
FLUX = ["npp", "transp", "wscal_mean", "mort_npp", "mort_age", "mort_water", "mort_temp", "mort"]
TARGET_RAW = ["Height", "agb", "vegc", "LAI", "fpc_ind", "D95", "npp", "transp", "wscal_mean",
              "mort_npp", "mort_age", "mort_water", "mort_temp", "mort"]
READ_COLS = ["Year", "Cell", "Patch", "Type", "ID", "isdead"] + TRAITS + STATE + FLUX
COUNTER_FAIL_MAX = 1e-5
SMOKE = os.environ.get("SH3_SMOKE") == "1"
SMOKE_NPAIRS = 5  # smoke: only the first 5 output pairs


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def status(line: str):
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    with open(STATUS, "a") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} {line}\n")


# ------------------------------------------------------------------------------------------------ registry helpers
def registry():
    return (pl.read_parquet(os.path.join(REG, "members.parquet")),
            pl.read_parquet(os.path.join(REG, "segments.parquet")),
            pl.read_parquet(os.path.join(REG, "folds.parquet")))


def usable_members(mem: pl.DataFrame) -> list[str]:
    return mem.filter(~pl.col("excluded")).sort("gcm", "scen", "seed")["member"].to_list()


def member_row(mem: pl.DataFrame, member: str) -> dict:
    r = mem.filter(pl.col("member") == member)
    assert r.height == 1, member
    return r.row(0, named=True)


def historical_of(mem: pl.DataFrame, gcm: str, seed: int) -> dict:
    r = mem.filter((pl.col("gcm") == gcm) & (pl.col("seed") == seed) & (pl.col("scen") == "Historical"))
    assert r.height == 1, (gcm, seed)
    return r.row(0, named=True)


def sources(row: dict, cellset: str) -> dict[str, str]:
    """cb label -> parquet path(s) glob for one member window."""
    if cellset == "dev":
        return {"dev": row["ind_dev_path"]}
    out = {}
    for d in sorted(glob.glob(os.path.join(row["ind_path"], "cb=*"))):
        out[os.path.basename(d).split("=", 1)[1]] = os.path.join(d, "*.parquet")
    assert out, row["ind_path"]
    return out


def cell_list(folds: pl.DataFrame, cellset: str) -> np.ndarray:
    f = folds.filter(pl.col("is_dev")) if cellset == "dev" else folds
    c = f["Cell"].to_numpy()
    if SMOKE:
        c = c[c % 100 == 0]
    return np.sort(c)


# ------------------------------------------------------------------------------------------------ hashing
_M64 = np.uint64(0xFFFFFFFFFFFFFFFF)


def _splitmix(x: np.ndarray) -> np.ndarray:
    with np.errstate(over="ignore"):
        x = x + np.uint64(0x9E3779B97F4A7C15)
        x = (x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        return x ^ (x >> np.uint64(31))


def u_hash(df: pl.DataFrame, member: str) -> np.ndarray:
    """Deterministic uniform [0, 1) per (key, member); stable across polars/numpy versions (pure splitmix64)."""
    h = np.full(df.height, int.from_bytes(hashlib.sha256(member.encode()).digest()[:8], "big"), dtype=np.uint64)
    for k in KEY:
        v = df[k].cast(pl.Int64).to_numpy().astype(np.int64).view(np.uint64)
        h = _splitmix(h ^ v)
    return ((h >> np.uint64(11)).astype(np.float64) * (1.0 / 9007199254740992.0))


# ------------------------------------------------------------------------------------------------ per-year read
def read_year(src: str, year: int, cells: np.ndarray | None) -> pl.DataFrame:
    lf = pl.scan_parquet(src).filter(pl.col("Year") == year)
    if cells is not None:
        lf = lf.filter(pl.col("Cell").is_in(cells.tolist()))
    return lf.select(READ_COLS).collect()


def with_key(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        sla_i=(pl.col("SLA").cast(pl.Float64) * 1e9).round().cast(pl.Int64),
        wd_i=(pl.col("Wooddens").cast(pl.Float64) * 10).round().cast(pl.Int64))


def add_hidden(trees: pl.DataFrame, prev_c: pl.DataFrame | None, P) -> pl.DataFrame:
    """c, G, W (+ censor codes) for every printed tree row; c_prev from the previous year's rows of the same key."""
    if prev_c is not None and prev_c.height:
        trees = trees.join(prev_c.select(KEY + [pl.col("c").alias("_cp")]), on=KEY, how="left")
        cp = trees["_cp"].fill_null(-1).to_numpy()
        trees = trees.drop("_cp")
    else:
        cp = np.full(trees.height, -1, dtype=np.int64)
    t = trees["Type"].to_numpy().astype(np.int64)
    mm = rl.mort_max_of(trees["Wooddens"].to_numpy(), t, P)
    c, _ = rl.recover_counter(trees["mort_npp"].to_numpy(), mm, c_prev=cp)
    G, cg = rl.recover_G(trees["mort_npp"].to_numpy(), mm, c, P)
    W, cw = rl.recover_W(trees["mort_water"].to_numpy(), c, t, P)
    return trees.with_columns(pl.Series("c", c, dtype=pl.Int8), pl.Series("G", G, dtype=pl.Float32),
                              pl.Series("cenG", cg, dtype=pl.Int8), pl.Series("W", W, dtype=pl.Float32),
                              pl.Series("cenW", cw, dtype=pl.Int8))


def patch_context(live: pl.DataFrame, grass: pl.DataFrame, grass_types: list[int]) -> pl.DataFrame:
    """Per living tree at y: n_live, sum_fpc, sum_agb, height_rank, fpc_above (+ grass columns joined by patch)."""
    f64 = pl.Float64
    p = live.group_by("Cell", "Patch").agg(n_live=pl.len().cast(pl.Int16),
                                           sum_fpc=pl.col("fpc_ind").cast(f64).sum(),
                                           sum_agb=pl.col("agb").cast(f64).sum())
    # fpc of strictly taller stems: per (patch, height) sum, exclusive cumulative sum in descending height
    hs = (live.group_by("Cell", "Patch", "Height").agg(_f=pl.col("fpc_ind").cast(f64).sum())
          .sort("Cell", "Patch", "Height", descending=[False, False, True])
          .with_columns(fpc_above=(pl.col("_f").cum_sum().over("Cell", "Patch") - pl.col("_f")))
          .drop("_f"))
    out = (live.select(KEY + ["Height"])
           .with_columns(height_rank=pl.col("Height").rank("min", descending=True).over("Cell", "Patch")
                         .cast(pl.Int16))
           .join(hs, on=["Cell", "Patch", "Height"], how="left")
           .join(p, on=["Cell", "Patch"], how="left")
           .drop("Height"))
    for g in grass_types:
        gg = (grass.filter(pl.col("Type") == g)
              .group_by("Cell", "Patch")
              .agg(**{f"grass{g}_fpc": pl.col("fpc_ind").sum(), f"grass{g}_LAI": pl.col("LAI").sum(),
                      f"grass{g}_agb": pl.col("agb").sum()}))
        out = out.join(gg, on=["Cell", "Patch"], how="left")
    return out


def cell_context(live: pl.DataFrame, npatch: int) -> pl.DataFrame:
    n = live.group_by("Cell").agg(_n=pl.len())
    sh = live.group_by("Cell", "Type").agg(_k=pl.len())
    out = n.with_columns(cell_stems_per_patch=(pl.col("_n").cast(pl.Float64) / npatch))
    for t in range(MAX_TREE_TYPE + 1):
        out = out.join(sh.filter(pl.col("Type") == t).select("Cell", pl.col("_k").alias(f"_k{t}")),
                       on="Cell", how="left")
        out = out.with_columns((pl.col(f"_k{t}").fill_null(0).cast(pl.Float64) / pl.col("_n"))
                               .alias(f"cell_share_t{t}")).drop(f"_k{t}")
    return out.drop("_n")


# ---------------------------------------------------------------------------------------------- build one (member, cb)
def build_one(member: str, cellset: str, cb: str, force: bool = False) -> dict:
    rl.assert_usable(member)
    mem, seg, folds = registry()
    row = member_row(mem, member)
    gcm, traj, seed, npatch = row["gcm"], row["scen"], int(row["seed"]), int(row["npatch"])
    is_hist = traj == "Historical"
    hist = row if is_hist else historical_of(mem, gcm, seed)
    src_hist = sources(hist, cellset)[cb]
    src_win = sources(row, cellset)[cb]
    cells = cell_list(folds, cellset)
    cell_filter = cells if (cellset == "dev" and SMOKE) else None
    if cellset == "full":
        cell_filter = cells[np.isin(cells, pl.scan_parquet(src_win).select(pl.col("Cell").unique())
                                    .collect()["Cell"].to_numpy())] if SMOKE else None

    sg = seg.filter((pl.col("gcm") == gcm) & (pl.col("scen") == traj) & (pl.col("seed") == seed))
    pair_years = sorted(sg.filter(pl.col("pair_ok"))["Year"].to_list())
    hist_years = sorted(int(y) for y in hist["years_complete"])
    win_years = sorted(int(y) for y in row["years_complete"])
    chain_years = hist_years if is_hist else hist_years + [y for y in win_years if y > hist_years[-1]]
    if not is_hist and win_years[0] > hist_years[-1] + 1:
        # a window that does NOT continue the Historical table (global venue: 2071-2100 after a 2015-2070 gap)
        # starts its own chain: its first year has no history (as 1985 has none), never the 2014 rows.
        # Germany's windows are contiguous (w2015 follows 2014), so this never fires there.
        chain_years = win_years
    out_years = [y for y in pair_years if (y in chain_years and y + 1 in chain_years)
                 and ((is_hist and y < hist_years[-1]) or (not is_hist and y >= hist_years[-1]))]
    if SMOKE:
        out_years = out_years[:SMOKE_NPAIRS]
    flags = {int(r["Year"]): (int(r["rh_on"]), int(r["bin_feb2026"])) for r in sg.iter_rows(named=True)}
    odir = os.path.join(TRANS, cellset, member, f"cb={cb}")
    os.makedirs(odir, exist_ok=True)
    gpath = os.path.join(odir, "_gates.json")
    if not force and os.path.exists(gpath):
        g = json.load(open(gpath))
        if g.get("complete") and g.get("out_years") == out_years:
            log(f"{member} cb={cb}: complete, skipping")
            return g
    P = rl.load_params()

    def src_of(y):
        return src_hist if y <= hist_years[-1] else src_win

    log(f"{member} cb={cb}: traj={traj} chain {chain_years[0]}-{chain_years[-1]} out {out_years[0]}-{out_years[-1]}"
        f" ({len(out_years)} pairs) npatch={npatch}")
    gates = {"member": member, "cellset": cellset, "cb": cb, "out_years": out_years, "years": {}}
    seen = None          # every key printed so far in the chain (for re-entries)
    seen_prev = None     # keys printed up to y-2 (carried one iteration)
    prev = None          # year y-1 tree rows: KEY + c + agb
    cur = None           # year y tree rows (all printed trees, with hidden state)
    cur_grass = None
    grass_types: list[int] | None = None
    last_needed = out_years[-1] + 1
    for y in [yy for yy in chain_years if yy <= last_needed]:
        raw = read_year(src_of(y), y, cell_filter)
        trees = with_key(raw.filter(pl.col("Type") <= MAX_TREE_TYPE))
        grass = raw.filter(pl.col("Type") > MAX_TREE_TYPE)
        if grass_types is None:
            grass_types = sorted(int(t) for t in grass["Type"].unique().to_list())
        nkey = trees.select(KEY).n_unique()
        if nkey != trees.height:
            raise RuntimeError(f"{member} cb={cb} {y}: {trees.height - nkey} duplicate keys")
        trees = add_hidden(trees, cur.select(KEY + ["c"]) if cur is not None else None, P)
        if cur is not None and (y - 1) in out_years:
            gates["years"][str(y - 1)] = emit_pair(member, gcm, traj, seed, npatch, y - 1, prev, cur, cur_grass,
                                                   trees, seen_before=seen_prev, cells=cells_of(cellset, folds, cb,
                                                   cur), grass_types=grass_types, flags=flags, odir=odir,
                                                   first_year=chain_years[0])
            log(f"  {y - 1}->{y}: {gates['years'][str(y - 1)]['rows']} rows")
        # roll the chain
        seen_prev = seen
        ks = cur.select(KEY) if cur is not None else None
        seen = ks if seen is None else (pl.concat([seen, ks]).unique() if ks is not None else seen)
        prev = cur.select(KEY + ["c", "agb"]) if cur is not None else None
        cur, cur_grass = trees, grass
    gates["complete"] = True
    gates["summary"] = summarise(gates)
    json.dump(gates, open(gpath, "w"), indent=1)
    log(f"{member} cb={cb}: DONE pass={gates['summary']['pass']}")
    return gates


def cells_of(cellset, folds, cb, cur):
    """Cells this (cellset, cb) must contain. dev: the dev set (smoke: Cell % 100 == 0); full: the source
    partition's cells that the registry lists as tree cells (the partition fixes the range)."""
    c = cell_list(folds, cellset)
    if cellset == "full":
        lo, hi = int(cur["Cell"].min()), int(cur["Cell"].max())
        c = c[(c >= lo) & (c <= hi)]
    return c


def emit_pair(member, gcm, traj, seed, npatch, y, prev, cur, grass_y, nxt, seen_before, cells, grass_types,
              flags, odir, first_year) -> dict:
    """Write the y -> y+1 rows (trees living at y) and return this year's gate numbers."""
    g = {}
    live = cur.filter(pl.col("isdead") == 0)
    dead = cur.filter(pl.col("isdead") == 1)
    g["rows"] = live.height
    g["rows_eq_living"] = None  # filled by the independent count below
    present_cells = np.unique(cur["Cell"].to_numpy())
    g["cells_missing"] = int(np.setdiff1d(cells, present_cells).size)
    g["cells_extra"] = int(np.setdiff1d(present_cells, cells).size)
    # history at y
    df = live
    if prev is not None:
        df = df.join(prev.select(KEY + [pl.col("agb").alias("_agb_prev")]), on=KEY, how="left")
        df = df.with_columns(d_agb_prev=(pl.col("agb") - pl.col("_agb_prev")).cast(pl.Float32),
                             is_new_y=pl.col("_agb_prev").is_null()).drop("_agb_prev")
        if seen_before is not None and seen_before.height:
            df = df.join(seen_before.with_columns(_seen=pl.lit(True)), on=KEY, how="left")
            df = df.with_columns(is_reentry_y=(pl.col("is_new_y") & pl.col("_seen").fill_null(False))).drop("_seen")
        else:
            df = df.with_columns(is_reentry_y=pl.lit(False))
        df = df.with_columns(is_recruit_y=pl.col("is_new_y") & ~pl.col("is_reentry_y"))
    else:
        assert y == first_year
        df = df.with_columns(d_agb_prev=pl.lit(None, pl.Float32), is_new_y=pl.lit(None, pl.Boolean),
                             is_reentry_y=pl.lit(None, pl.Boolean), is_recruit_y=pl.lit(None, pl.Boolean))
    # context
    df = df.join(patch_context(live, grass_y, grass_types), on=KEY, how="left")
    df = df.join(cell_context(live, npatch), on="Cell", how="left")
    rh1, bin1 = flags[y + 1]
    df = df.with_columns(rh_on_y1=pl.lit(rh1, pl.Int8), bin_feb2026_y1=pl.lit(bin1, pl.Int8))
    # targets at y+1
    tgt = nxt.select(KEY + [pl.col("isdead").alias("_isdead1"), pl.col("Age").alias("_Age1")]
                     + [pl.col(c).alias(f"{c}_y1") for c in TARGET_RAW]
                     + [pl.col("c").alias("c_y1"), pl.col("G").alias("G_y1"), pl.col("cenG").alias("cenG_y1"),
                        pl.col("W").alias("W_y1"), pl.col("cenW").alias("cenW_y1")]
                     + [pl.col(t).alias(f"_{t}1") for t in TRAITS[2:]])
    df = df.join(tgt, on=KEY, how="left")
    df = df.with_columns(fate_y1=pl.when(pl.col("_isdead1").is_null()).then(2).otherwise(pl.col("_isdead1"))
                         .cast(pl.Int8),
                         hard_y1=(pl.col("mort_y1") >= 1.0))
    pres = df.filter(pl.col("fate_y1") < 2)
    g["n_present"] = pres.height
    g["n_alive"] = int((df["fate_y1"] == 0).sum())
    g["n_flagged"] = int((df["fate_y1"] == 1).sum())
    g["n_absent"] = int((df["fate_y1"] == 2).sum())
    g["age_fail"] = int((pres["_Age1"] != pres["Age"] + 1).sum())
    g["trait_fail"] = {t: int((pres[f"_{t}1"] != pres[t]).sum()) for t in TRAITS[2:]}
    ok = (pres["cenG"] != rl.CENSOR["npp_sat"]) & (pres["cenG_y1"] != rl.CENSOR["npp_sat"])
    pc = pres.filter(ok)
    c0, c1 = pc["c"].cast(pl.Int16), pc["c_y1"].cast(pl.Int16)
    g["counter_pairs"] = pc.height
    g["counter_fail"] = int(((c1 != 0) & (c1 != c0 + 1)).sum())
    # flagged dead at y must not be printed at y+1
    g["dead_reappear"] = int(dead.select(KEY).join(nxt.select(KEY), on=KEY, how="semi").height)
    df = df.drop(["_isdead1", "_Age1"] + [f"_{t}1" for t in TRAITS[2:]])
    df = df.rename({"c": "c_y", "G": "G_y", "cenG": "cenG_y", "W": "W_y", "cenW": "cenW_y"})
    df = df.with_columns(member=pl.lit(member), gcm=pl.lit(gcm), traj=pl.lit(traj),
                         seed=pl.lit(seed, pl.Int8), Year=pl.lit(y, pl.Int16),
                         u_hash=pl.Series(u_hash(df, member)).cast(pl.Float64))
    df = df.drop("isdead")
    fl = [c for c, t in df.schema.items() if t == pl.Float64 and c != "u_hash"]
    df = df.with_columns([pl.col(c).cast(pl.Float32) for c in fl])
    lead = ["member", "gcm", "traj", "seed", "Year"] + KEY + ["u_hash"]
    df = df.select(lead + [c for c in df.columns if c not in lead]).sort(["Cell", "Patch", "Type", "ID"])
    df.write_parquet(os.path.join(odir, f"y{y}.parquet"), compression="zstd", statistics=True)
    return g


def summarise(gates: dict) -> dict:
    ys = gates["years"].values()
    tot = lambda k: int(sum(v[k] for v in ys))  # noqa: E731
    cp, cf = tot("counter_pairs"), tot("counter_fail")
    s = {"rows": tot("rows"), "n_present": tot("n_present"), "n_alive": tot("n_alive"),
         "n_flagged": tot("n_flagged"), "n_absent": tot("n_absent"),
         "cells_missing": tot("cells_missing"), "cells_extra": tot("cells_extra"),
         "age_fail": tot("age_fail"),
         "trait_fail": {t: int(sum(v["trait_fail"][t] for v in ys)) for t in TRAITS[2:]},
         "dead_reappear": tot("dead_reappear"), "counter_pairs": cp, "counter_fail": cf,
         "counter_fail_rate": cf / max(cp, 1)}
    s["pass"] = bool(s["cells_missing"] == 0 and s["age_fail"] == 0 and sum(s["trait_fail"].values()) == 0
                     and s["dead_reappear"] == 0 and s["counter_fail_rate"] <= COUNTER_FAIL_MAX)
    return s


# ---------------------------------------------------------------------------------------------- independent count gate
def rows_eq_living(member: str, cellset: str, cb: str) -> dict:
    """Independent check: table rows per year == living tree rows of the SOURCE (fresh scan, no shared code)."""
    mem, _, _ = registry()
    row = member_row(mem, member)
    hist = row if row["scen"] == "Historical" else historical_of(mem, row["gcm"], int(row["seed"]))
    g = json.load(open(os.path.join(TRANS, cellset, member, f"cb={cb}", "_gates.json")))
    hy = max(int(y) for y in hist["years_complete"])
    bad = {}
    for ys in g["out_years"]:
        y = int(ys)
        src = sources(hist if y <= hy else row, cellset)[cb]
        lf = pl.scan_parquet(src).filter((pl.col("Year") == y) & (pl.col("Type") <= MAX_TREE_TYPE)
                                          & (pl.col("isdead") == 0))
        if SMOKE:
            lf = lf.filter((pl.col("Cell") % 100) == 0)
        n_src = lf.select(pl.len()).collect().item()
        n_tab = pl.scan_parquet(os.path.join(TRANS, cellset, member, f"cb={cb}", f"y{y}.parquet")) \
            .select(pl.len()).collect().item()
        if n_src != n_tab:
            bad[y] = (n_src, n_tab)
    return {"years_checked": len(g["out_years"]), "mismatch": bad, "pass": not bad}


# ------------------------------------------------------------------------------------------------ climate join
def join_climate(df: pl.DataFrame | pl.LazyFrame, cols: list[str] | None = None, years=("y", "y1"),
                 ext: bool = True) -> pl.DataFrame | pl.LazyFrame:
    """THE shared feature join. Attaches climate/cell_year (+ shared/climate/cell_year_ext) columns for the
    transition's year y (suffix _y) and/or y+1 (suffix _y1), mapped through SH0 segments
    (gcm, traj, seed, Year) -> (clim_scen, clim_year). `cols` = climate column names (default: every numeric
    column of both tables except the exclusion bookkeeping). `df` needs gcm, traj, seed, Cell, Year."""
    lazy = isinstance(df, pl.LazyFrame)
    lf = df if lazy else df.lazy()
    seg = pl.scan_parquet(os.path.join(REG, "segments.parquet")).select(
        "gcm", pl.col("scen").alias("traj"), pl.col("seed").cast(pl.Int8), pl.col("Year").cast(pl.Int16),
        "clim_scen", pl.col("clim_year").cast(pl.Int32))
    cy = pl.scan_parquet(CLIM)
    if ext:
        drop = ["excluded", "exclusion_reason", "truth_usable"]
        ex = pl.scan_parquet(EXT)
        ex = ex.select([c for c in ex.collect_schema().names() if c not in drop])
        cy = cy.join(ex, on=["gcm", "scen", "Cell", "Year"], how="left")
    names = [c for c in cy.collect_schema().names() if c not in ("gcm", "scen", "Cell", "Year")]
    if cols is not None:
        miss = set(cols) - set(names)
        assert not miss, f"unknown climate columns {sorted(miss)}"
        names = list(cols)
    cy = cy.select("gcm", pl.col("scen").alias("clim_scen"), pl.col("Cell").cast(pl.Int16),
                   pl.col("Year").alias("clim_year"), *names)
    for suf, off in (("y", 0), ("y1", 1)):
        if suf not in years:
            continue
        s = seg.with_columns((pl.col("Year") - off).cast(pl.Int16).alias("Year"))
        lf = (lf.join(s, on=["gcm", "traj", "seed", "Year"], how="left")
              .join(cy, on=["gcm", "clim_scen", "Cell", "clim_year"], how="left")
              .rename({n: f"{n}_{suf}" for n in names} | {"clim_scen": f"clim_scen_{suf}",
                                                          "clim_year": f"clim_year_{suf}"}))
    return lf if lazy else lf.collect()


# ------------------------------------------------------------------------------------------------ stages
def stage_build(a):
    mem, _, _ = registry()
    members = a.member or usable_members(mem)
    for m in members:
        cbs = a.cb or list(sources(member_row(mem, m), a.cellset).keys())
        for cb in cbs:
            t0 = time.time()
            g = build_one(m, a.cellset, cb, force=a.force)
            r = rows_eq_living(m, a.cellset, cb)
            g["rows_eq_living"] = r
            g["summary"]["pass"] = bool(g["summary"]["pass"] and r["pass"])
            json.dump(g, open(os.path.join(TRANS, a.cellset, m, f"cb={cb}", "_gates.json"), "w"), indent=1)
            status(f"{a.cellset} {m} cb={cb}: rows {g['summary']['rows']}, pass={g['summary']['pass']}, "
                   f"{time.time() - t0:.0f} s")


def stage_gates(a):
    rows = []
    for gp in sorted(glob.glob(os.path.join(TRANS, a.cellset, "*", "cb=*", "_gates.json"))):
        g = json.load(open(gp))
        s = g["summary"]
        rows.append({"member": g["member"], "cb": g["cb"], **{k: v for k, v in s.items() if k != "trait_fail"},
                     "trait_fail": sum(s["trait_fail"].values()),
                     "rows_eq_living": g.get("rows_eq_living", {}).get("pass")})
    mem, _, _ = registry()
    expected = {(m, cb) for m in usable_members(mem) for cb in sources(member_row(mem, m), a.cellset)}
    have = {(r["member"], r["cb"]) for r in rows}
    out = {"cellset": a.cellset, "expected": len(expected), "built": len(have & expected),
           "missing": sorted(f"{m} cb={c}" for m, c in expected - have),
           "all_pass": bool(rows) and all(r["pass"] for r in rows) and not (expected - have),
           "totals": {k: int(sum(r[k] for r in rows)) for k in
                      ("rows", "n_present", "n_alive", "n_flagged", "n_absent", "age_fail", "trait_fail",
                       "dead_reappear", "counter_pairs", "counter_fail", "cells_missing")},
           "per_member": rows}
    out["totals"]["counter_fail_rate"] = out["totals"]["counter_fail"] / max(out["totals"]["counter_pairs"], 1)
    json.dump(out, open(os.path.join(TRANS, a.cellset, "_gates.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "per_member"}, indent=1))


def stage_submit(a):
    mem, _, _ = registry()
    tasks = [(m, cb) for m in usable_members(mem) for cb in sources(member_row(mem, m), a.cellset)]
    jobs = os.path.join(XDE, "_jobs")
    os.makedirs(jobs, exist_ok=True)
    tl = os.path.join(jobs, f"SH3_{a.cellset}_tasks.txt")
    with open(tl, "w") as f:
        f.writelines(f"{m} {cb}\n" for m, cb in tasks)
    logs = os.path.join(REPO, "logs")
    os.makedirs(logs, exist_ok=True)
    ncpu = 16 if a.cellset == "dev" else 32
    jcf = os.path.join(jobs, f"X-de-SH3-{a.cellset}.jcf")
    with open(jcf, "w") as f:
        f.write(f"""#!/bin/bash
#SBATCH --job-name=X-de-SH3-{a.cellset}
#SBATCH --account=waldspektrum
#SBATCH --partition=priority
#SBATCH --qos=priority
#SBATCH --cpus-per-task={ncpu}
#SBATCH --time=04:00:00
#SBATCH --array=1-{len(tasks)}%{a.parallel}
#SBATCH --output={logs}/X-de-SH3-{a.cellset}.%A_%a.out
set -eu
read M CB < <(sed -n "${{SLURM_ARRAY_TASK_ID}}p" {tl})
export POLARS_MAX_THREADS={ncpu}
{PY} {os.path.abspath(__file__)} build --cellset {a.cellset} --member "$M" --cb "$CB"
echo "=== JOB DONE task=$SLURM_ARRAY_TASK_ID member=$M cb=$CB exit=$? ==="
""")
    jid = subprocess.run(["sbatch", "--parsable", jcf], capture_output=True, text=True, check=True).stdout.strip()
    log(f"submitted {jid}: {len(tasks)} tasks, jcf {jcf}")
    status(f"submitted {a.cellset} array {jid} ({len(tasks)} tasks), log logs/X-de-SH3-{a.cellset}.{jid}_<k>.out")
    if a.gates_after:
        gj = os.path.join(jobs, f"X-de-SH3-{a.cellset}-gates.jcf")
        with open(gj, "w") as f:
            f.write(f"""#!/bin/bash
#SBATCH --job-name=X-de-SH3-{a.cellset}-gates
#SBATCH --account=waldspektrum
#SBATCH --partition=priority
#SBATCH --qos=priority
#SBATCH --cpus-per-task=2
#SBATCH --time=00:20:00
#SBATCH --dependency=afterany:{jid}
#SBATCH --output={logs}/X-de-SH3-{a.cellset}-gates.%j.out
{PY} {os.path.abspath(__file__)} gates --cellset {a.cellset}
echo "=== JOB DONE gates exit=$? ==="
""")
        g = subprocess.run(["sbatch", "--parsable", gj], capture_output=True, text=True, check=True).stdout.strip()
        log(f"gates job {g} (afterany:{jid})")
        status(f"gates job {g} afterany {jid}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["build", "gates", "submit", "smoke"])
    ap.add_argument("--cellset", choices=["dev", "full"], default="dev")
    ap.add_argument("--member", action="append")
    ap.add_argument("--cb", action="append")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--parallel", type=int, default=16)
    ap.add_argument("--gates-after", action="store_true")
    a = ap.parse_args(argv)
    if a.stage == "smoke":
        global TRANS, SMOKE
        SMOKE = True
        TRANS = os.path.join(XDE, "shared", "trans", "_smoke")
        a.cellset = "dev"
        a.member = a.member or ["MPI-ESM1-2-HR_Historical_s1_h1985"]
        a.force = True
        stage_build(a)
        return
    {"build": stage_build, "gates": stage_gates, "submit": stage_submit}[a.stage](a)


if __name__ == "__main__":
    main()
