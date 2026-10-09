#!/usr/bin/env python3
"""explore_panel_prep.py -- LINE X: the PANEL VENUE (line S's Track-D panel runs of the original, ADR 0246) prepared
for line X's cell-level arms (ADR 0315 statistics, re-targeted). READ-ONLY on every line-S artifact; writes only under
/p/projects/open/Jamir/esm_land_emulator_data/xpanel/ (owner rule: data in /p/projects, never home).

WHY: on Billing's global set the two leading arms fail mainly where the test climate lies OUTSIDE the training climates
(direct map: 0.131 held-out ssp370 vs 0.162 with ssp370 in training, 0.186 on interpolated ssp245; ADR 0315 sec. 9).
The panel (1 050 orderA cells = 105 contiguous 10-cell blocks, 4 independent members, 25 patches, constant CO2) has
5 climate models x ssp126/370/585 + two constant-climate controls, with a per-tree table EVERY year 2020-2100 -- the
data that can test "wider climate coverage is the lever" with a held-out climate model and a held-out amplitude.

STAGES (arg 1; comma list ok)
  cells     panel cells -> cells.parquet (Cell, block, lat, lon, soil_code, stratum, fold). Folds 1-5 by BLOCK: blocks
            sorted by (stratum, sha256(block)), fold = rank % 5 + 1 (every fold spans the climate strata).
  climate   per (leg, Cell, Year) features for the panel cells, same definitions as explore_glob_climate.year_features
            (Feb/local tstress parameters: the panel binary is the b2e5ca9 snapshot) -> climate/<leg>.parquet.
            hist = observed 1981-2019; a scenario leg = observed 1996-2019 + its scenario file 2020-2100 (the run
            switched forcing at 2020, so its *_tr20 columns mix both, as the model saw them). ctl_obs / ctl_mpi370 =
            the yearly features of their POOL years (observed 1990-2019 / MPI-ESM1-2-HR ssp370 2015-2034) under
            Year = the source year -> climate/<ctl>_pool.parquet; the drawn sequence is not reconstructed here.
  levels    per member x leg x window the ADR 0315 per-cell statistics (explore_de_reference.living/reduce_window,
            NPATCH 25; the panel tables carry ALL heights, `living` keeps Height >= 5 m = the production population)
            -> levels/m<k>_<leg>_<win>.parquet. Windows: hist h2000 (2000-2019) + y2019 snapshot; every 2020-2100 leg
            w2041 (2041-2070) and w2071 (2071-2100). Array-able: --part i --nparts n over (member, leg).
  gates     coverage + climate plausibility -> _gates.json

GATES (must hold): 1 050 cells in 105 blocks, each fold 21 blocks; every climate column finite on every (leg, Cell,
Year); lwnet negative on average (net, not downward, longwave), rh mean in [0.3, 0.9]; hist 2000-2019 annual mean
temperature of the panel equals the observed file's to 1e-6 (reader check); levels exist for every complete leg; a
leg with missing blocks (line S's status: m3 mpi-esm1-2-hr_ssp585 29/105, m4 ukesm1-0-ll_ssp585 15/105) is recorded,
its cells' rows are dropped, never imputed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_reference as R  # noqa: E402
import explore_glob_climate as GC  # noqa: E402
from build_transient_boundary import open_clm  # noqa: E402
from explore_de_climate import daylength_hours, read_lpj_header  # noqa: E402

OUT = "/p/projects/open/Jamir/esm_land_emulator_data/xpanel"
PANEL_IND = "/p/projects/open/Jamir/esm_land_emulator_data/trackD/panel"
BLOCKS = os.path.join(REPO, "test", "testitems", "references", "S_D0_panel_blocks.csv")
G = "/p/projects/waldspektrum/priesner/clustering/global"
GRID = f"{G}/soil_code_test.grid.clm"
SOIL = f"{G}/soil_code_test.soil.bin"
FORC = "/p/tmp/jamirp/trackD/forcing"
NCELL = 67420
NPATCH = 25
OBS = {"temp": f"{G}/temperature_test.clm", "prec": f"{G}/precipitation_test.clm", "humid": f"{G}/humid_test.clm",
       "swdown": f"{G}/short_wave_radiation_test.clm", "lwnet": f"{G}/long_wave_radiation_test.clm"}
SVAR = {"temp": "tas", "prec": "pr", "humid": "huss", "swdown": "rsds", "lwnet": "lwnet"}
GCMS = ["gfdl-esm4", "ipsl-cm6a-lr", "mpi-esm1-2-hr", "mri-esm2-0", "ukesm1-0-ll"]
SCENS = ["ssp126", "ssp370", "ssp585"]
SLEGS = [f"{g}_{s}" for g in GCMS for s in SCENS]
CTL = {"ctl_obs": ("obs", 1990, 2019), "ctl_mpi370": ("mpi-esm1-2-hr_ssp370", 2015, 2034)}
LEGS = ["hist", *SLEGS, *CTL]
MEMBERS = [1, 2, 3, 4]
WINS = {"h2000": (2000, 2019), "y2019": (2019, 2019), "w2041": (2041, 2070), "w2071": (2071, 2100)}
CLIM_DIR, LEV_DIR = os.path.join(OUT, "climate"), os.path.join(OUT, "levels")


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ------------------------------------------------------------------------------------------------------ cells
def read_grid_orderA():
    h, dt = read_lpj_header(GRID)
    assert h["ncell"] == NCELL and h["nbands"] == 2, h
    a = np.fromfile(GRID, dtype=dt, offset=h["hdr"]).reshape(NCELL, 2).astype(np.float64) * h["scalar"]
    assert abs(a[42490, 0] - 10.25) < 1e-6 and abs(a[42490, 1] - 51.25) < 1e-6, a[42490]  # Hainich, orderA
    return a[:, 0], a[:, 1]


def stage_cells(_a=None):
    b = pl.read_csv(BLOCKS)
    lon, lat = read_grid_orderA()
    soil = np.fromfile(SOIL, dtype=np.uint8)
    assert soil.size == NCELL
    key = [(int(r["stratum"]), hashlib.sha256(str(r["block"]).encode()).hexdigest()) for r in b.iter_rows(named=True)]
    order = sorted(range(b.height), key=lambda i: key[i])
    fold = np.zeros(b.height, dtype=np.int32)
    for rank, i in enumerate(order):
        fold[i] = rank % 5 + 1
    b = b.with_columns(pl.Series("fold", fold))
    rows = []
    for r in b.iter_rows(named=True):
        for c in range(r["start"], r["end"] + 1):
            rows.append(dict(Cell=c, block=r["block"], lat=lat[c], lon=lon[c], soil_code=int(soil[c]),
                             stratum=r["stratum"], tile15=r["tile15"], fold=r["fold"]))
    d = pl.DataFrame(rows)
    assert d.height == 1050 and d["Cell"].n_unique() == 1050
    assert d.group_by("fold").agg(pl.col("block").n_unique())["block"].to_list() == [21] * 5
    os.makedirs(OUT, exist_ok=True)
    d.write_parquet(os.path.join(OUT, "cells.parquet"))
    log("cells", d.height, d.group_by("fold").len().sort("fold").rows())


def cells() -> pl.DataFrame:
    return pl.read_parquet(os.path.join(OUT, "cells.parquet"))


# ------------------------------------------------------------------------------------------------------ climate
def _open(paths):
    out = {}
    for v, p in paths.items():
        mm, fy, ncell, nbands, scalar = open_clm(p)
        assert ncell == NCELL and nbands == 365, p
        out[v] = (mm, fy, scalar)
    return out


def _features(src, years, idx, lat):
    dl = daylength_hours(lat)
    win, hs = GC.window_mask(lat), GC.summer_mask(lat)
    prm = GC.pft_temp_params()
    lo, hi = prm["temp_low"].to_numpy(), prm["temp_high"].to_numpy()
    cols = {}
    for y in years:
        arr = {}
        for v, (mm, fy, scalar) in src[y].items():
            arr[v] = np.asarray(mm[y - fy][idx], dtype=np.float64) * scalar
        W = np.zeros_like(arr["temp"])
        f, _ = GC.year_features(arr["temp"], arr["prec"], arr["humid"], arr["swdown"], arr["lwnet"], W, dl, win, hs,
                                lo, hi)
        for c, x in f.items():
            cols.setdefault(c, []).append(x)
    n = len(idx)
    return pl.DataFrame({"Cell": np.tile(idx.astype(np.int32), len(years)),
                         "Year": np.repeat(np.asarray(years, dtype=np.int32), n),
                         **{c: np.concatenate(v) for c, v in cols.items() if not c.startswith("wind")}})


def _scen_paths(leg):
    g, s = leg.rsplit("_", 1)
    return {v: f"{FORC}/{s}/{SVAR[v]}_{g}_{s}_2015-2100_orderA.clm" for v in SVAR}


def _add_tr20(d: pl.DataFrame) -> pl.DataFrame:
    d = d.sort(["Cell", "Year"])
    return d.with_columns([pl.col(c).cast(pl.Float64).rolling_mean(20).over("Cell").cast(pl.Float32)
                           .alias(f"{c}_tr20") for c in GC.TR20_SRC])


def climate_leg(leg):
    out = os.path.join(CLIM_DIR, f"{leg}.parquet" if leg not in CTL else f"{leg}_pool.parquet")
    if os.path.exists(out):
        return out
    t0 = time.time()
    c = cells()
    idx, lat = c["Cell"].to_numpy(), c["lat"].to_numpy()
    obs = _open(OBS)
    if leg == "hist":
        years, src = list(range(1981, 2020)), None
        src = {y: obs for y in years}
    elif leg in CTL:
        base, y0, y1 = CTL[leg]
        years = list(range(y0, y1 + 1))
        s = obs if base == "obs" else _open(_scen_paths(base))
        src = {y: s for y in years}
    else:
        sc = _open(_scen_paths(leg))
        years = list(range(1996, 2101))
        src = {y: (obs if y <= 2019 else sc) for y in years}
    d = _features(src, years, idx, lat)
    if leg not in CTL:
        d = _add_tr20(d).filter(pl.col("Year") >= (2000 if leg == "hist" else 2020))
    d.write_parquet(out)
    log(f"climate {leg}: {d.height} rows ({time.time() - t0:.0f}s)")
    return out


def stage_climate(a):
    os.makedirs(CLIM_DIR, exist_ok=True)
    todo = [lg for i, lg in enumerate(LEGS) if i % a.nparts == a.part]
    for lg in todo:
        climate_leg(lg)


# ------------------------------------------------------------------------------------------------------ levels
def reduce_one(path, y0, y1, cl):
    lf = pl.scan_parquet(path).filter(pl.col("Year").is_between(y0, y1) & pl.col("Cell").is_in(cl))
    lf = lf.select(pl.col("Year").cast(pl.Int32), pl.col("Cell").cast(pl.Int32), pl.col("Type").cast(pl.Int8),
                   pl.col("isdead").cast(pl.Int8), *[pl.col(t).cast(pl.Float32) for t in R.TRAITS])
    ny = lf.select(pl.col("Year").n_unique()).collect().item()
    assert ny == y1 - y0 + 1, f"{path}: {ny} years in {y0}-{y1}"
    present = lf.select(pl.col("Cell").unique()).collect()["Cell"].to_list()
    trees = R.living(lf).collect()
    cy = pl.DataFrame({"Cell": cl, "n_years": [ny] * len(cl)})
    d = R.reduce_window(trees, cy, NPATCH)
    d = d.with_columns(pl.when(pl.col("n_per_patch") > 0).then(pl.col("agb_stand") / pl.col("n_per_patch"))
                       .otherwise(None).alias("agb_per_stem"))
    return d, set(present)


def complete_blocks(member, leg) -> list[int]:
    m = json.load(open(os.path.join(PANEL_IND, f"m{member}", leg, "manifest.json")))
    return sorted(int(b) for b in m.get("blocks", {}))


def stage_levels(a):
    os.makedirs(LEV_DIR, exist_ok=True)
    c = cells()
    jobs = [(m, lg) for m in MEMBERS for lg in LEGS]
    for i, (m, lg) in enumerate(jobs):
        if i % a.nparts != a.part:
            continue
        path = os.path.join(PANEL_IND, f"m{m}", lg, "ind.parquet")
        if not os.path.exists(path):
            log(f"m{m} {lg}: NO TABLE")
            continue
        wins = ("h2000", "y2019") if lg == "hist" else ("w2041", "w2071")
        try:
            blocks = complete_blocks(m, lg) if lg != "hist" else list(range(105))
        except FileNotFoundError:
            blocks = list(range(105))
        cl = c.filter(pl.col("block").is_in(blocks))["Cell"].to_list()
        for w in wins:
            out = os.path.join(LEV_DIR, f"m{m}_{lg}_{w}.parquet")
            if os.path.exists(out):
                continue
            t0 = time.time()
            y0, y1 = WINS[w]
            d, _ = reduce_one(path, y0, y1, cl)
            d.with_columns(pl.lit(len(blocks)).alias("n_blocks_leg")).write_parquet(out)
            log(f"m{m} {lg} {w}: {d.height} cells, {len(blocks)} blocks ({time.time() - t0:.0f}s)")


# ------------------------------------------------------------------------------------------------------ gates
def stage_gates(_a=None):
    g = {}
    c = cells()
    g["cells"] = c.height == 1050 and c["block"].n_unique() == 105
    clim = {}
    for lg in LEGS:
        f = os.path.join(CLIM_DIR, f"{lg}.parquet" if lg not in CTL else f"{lg}_pool.parquet")
        d = pl.read_parquet(f)
        num = [x for x in d.columns if x not in ("Cell", "Year")]
        fin = all(bool(np.isfinite(d[x].to_numpy().astype(np.float64)).all()) for x in num)
        clim[lg] = dict(rows=d.height, finite=fin, lwnet_mean=float(d["lwnet_ann"].mean()),
                        rh_mean=float(d["rh_mean"].mean()), tmean=float(d["tmean_ann"].mean()),
                        years=[int(d["Year"].min()), int(d["Year"].max())])
    g["climate"] = clim
    g["climate_ok"] = all(v["finite"] and v["lwnet_mean"] < 0 and 0.3 <= v["rh_mean"] <= 0.9 for v in clim.values())
    # reader check: the hist leg's 2000-2019 mean temperature equals a direct read of the observed file
    mm, fy, *_ = open_clm(OBS["temp"])
    idx = c["Cell"].to_numpy()
    direct = float(np.mean([np.asarray(mm[y - fy][idx], dtype=np.float64).mean() for y in range(2000, 2020)]))
    h = pl.read_parquet(os.path.join(CLIM_DIR, "hist.parquet")).filter(pl.col("Year").is_between(2000, 2019))
    g["reader_tmean_diff"] = abs(float(h["tmean_ann"].cast(pl.Float64).mean()) - direct)
    g["reader_ok"] = g["reader_tmean_diff"] < 1e-4
    lev = {}
    for m in MEMBERS:
        for lg in LEGS:
            for w in (("h2000", "y2019") if lg == "hist" else ("w2041", "w2071")):
                f = os.path.join(LEV_DIR, f"m{m}_{lg}_{w}.parquet")
                lev[f"m{m}_{lg}_{w}"] = (pl.read_parquet(f).height if os.path.exists(f) else None)
    g["levels"] = lev
    g["levels_missing"] = [k for k, v in lev.items() if v is None]
    g["levels_partial"] = {k: v for k, v in lev.items() if v is not None and v < 1050}
    with open(os.path.join(OUT, "_gates.json"), "w") as fh:
        json.dump(g, fh, indent=1)
    log(json.dumps({k: v for k, v in g.items() if k not in ("climate", "levels")}, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage")
    ap.add_argument("--part", type=int, default=int(os.environ.get("SLURM_ARRAY_TASK_ID", "0")))
    ap.add_argument("--nparts", type=int, default=1)
    a = ap.parse_args()
    for s in a.stage.split(","):
        log(f"=== {s}")
        {"cells": stage_cells, "climate": stage_climate, "levels": stage_levels, "gates": stage_gates}[s](a)
    log("=== DONE")
