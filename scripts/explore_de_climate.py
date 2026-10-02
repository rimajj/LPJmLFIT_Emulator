#!/usr/bin/env python3
"""explore_de_climate.py — LINE X, Germany data-driven emulator: the CLIMATE + STATIC inputs it conditions on.

PREP, NOT A FINDING about the forest. It turns the daily forcing the Germany LPJmL-FIT production runs
actually read into per (gcm, scen, Cell, Year) tables, runs the forcing gates, and measures how separable
"response to warming" is from "character of the place" in this 2-GCM x 3-scenario design.

Read-only w.r.t. every input; writes ONLY under /p/tmp/jamirp/X_de/climate/.

------------------------------------------------------------------------------------------------
STAGES (positional arg 1)
  cy        read the 6 daily variables for every (gcm, leg) in parallel -> parts/cy_<gcm>_<leg>.parquet
  assemble  parts -> cell_year.parquet (+ trailing-20-yr means), cell_static.parquet, window_clim.parquet
  yearmap   recover which 2071-2100 climate year each 3071-3100 year recycled, per (gcm, scen, seed),
            from the C's own monthly PET output -> recycled_yearmap_3071_3100.parquet (+ realized
            3071-3100 window rows appended to window_clim.parquet)
  yearmap_full  the recycled sequence is seed-only, so recover the WHOLE 2101-3100 sequence per seed from two
            members each -> recycled_yearmap_2101_3100_by_seed.parquet
  verify    independent raw re-read spot check + wind remap + T-adjusted splice -> verify.json
  gates     header / range / splice / scenario-divergence / C-PET cross-check / confound -> gates.json
  all       cy, assemble, yearmap, yearmap_full, gates in order (a comma list also works: yearmap,gates)

------------------------------------------------------------------------------------------------
WHAT THE RUN READ (SOURCE + the runs' own log, stated once):
  * The run log lists exactly six climate-ish inputs: temp, prec, lwdown, swdown, co2, rhumid.
    WIND IS NOT READ: initclimate.c:170 opens it only for SPITFIRE/SPITFIRE_TMAX or with_nitrogen, and
    these runs use "fire":"fire" (GlobFIRM) and "with_nitrogen":"no". The wind columns are built because the
    task asked for them, but NOTHING in LPJmL-FIT responds to them -> do not condition on them.
  * humid is RELATIVE humidity (fraction, 0..1): config "relative_humidity": true, log label "rhumid".
    It reaches the trees only through getvpd() in waterstress_tree.c (the water-stress mortality integral).
  * PET here is the C's own petpar2 formula (radiation_lwdown branch) with a FIXED albedo BETA=0.17
    [ASSUMPTION: the C uses the dynamic patch albedo] x PRIESTLEY_TAYLOR = 1.32 (soil.h:71).
  * VPD here is the C's own getvpd() (spitfire/getvpd.c) EXACTLY, including its nonstandard nested-power
    Goff-Gratch terms, with rh clipped at 1, on DAILY MEAN temperature.
  * The C's stress accumulators reset on day 14 (COLDEST_DAY_NHEMISPHERE, all of Germany is north) AFTER
    that day's increment, so the value the annual mortality reads covers days 15..365 (1-based). The two
    "C-window" features below (vpd_win10_sum, tstress_lt_*) use that window. Soil-layer-1 temperature (the
    C's >10 C gate) is proxied by air temperature [ASSUMPTION; CLAUDE.md: no lag at 4 of 5 biome cells].

CONVENTIONS: noleap 365-day calendar (the files have 365 bands); months = DPM below; all features float32.
"""

from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from build_transient_boundary import DPM, MONTH_BOUNDS, open_clm  # noqa: E402  (canonical reader)

OUT = "/p/tmp/jamirp/X_de/climate"
PARTS = os.path.join(OUT, "parts")
FORC = "/p/projects/waldspektrum/data/FirEUrisk"
RUNS = "/p/projects/waldspektrum/data/LPJmLFIT/productionruns_jamir"
LPJIN = "/p/projects/biodiversity/billing/input/FirEUrisk/LPJ"
GRID = os.path.join(LPJIN, "grid_germany_9km_new.clm")
GRID_OLD = os.path.join(LPJIN, "grid_germany_9km.clm")  # 9133-cell grid of ONE stray wind file
SOIL = os.path.join(LPJIN, "soil_germany_9km_new.clm")

GCMS = ["MPI-ESM1-2-HR", "ACCESS-CM2"]
SSPS = ["ssp126", "ssp245", "ssp370"]
LEGS = ["Historical"] + SSPS
LEG_YEARS = {"Historical": (1950, 65), "ssp126": (2015, 86), "ssp245": (2015, 86), "ssp370": (2015, 86)}
# variable name (LPJmL config key) -> file prefix
VARS = {"temp": "TMean", "prec": "tpr", "humid": "HRMean", "swdown": "SWR", "lwdown": "LWR", "wind": "windspeed"}
NCELL = 9067
NB = 365
BETA = 0.17  # [ASSUMPTION] fixed albedo for PET (C: dynamic albedo_patch)
PRIESTLEY_TAYLOR = 1.32  # soil.h:71
SIGMA = 5.6704e-8  # petpar2.c
# soilmap from the runs' input_*.js (index = code in soil_germany_9km_new.clm)
SOILMAP = [None, "clay", "silty clay", "sandy clay", "clay loam", "silty clay loam", "sandy clay loam", "loam",
           "silt loam", "sandy loam", "silt", "loamy sand", "sand", "rock and ice"]
WIN_START0 = 14  # 0-based index of day 15 = first day the C's annual stress accumulators cover

MONTHLY_VARS = ["temp", "prec", "humid", "swdown", "lwdown", "wind"]
MONTHLY_COLS = [f"{v}_m{m:02d}" for v in MONTHLY_VARS for m in range(1, 13)]
ANNUAL_COLS = [
    "tmean_ann", "tcold_month", "twarm_month", "gdd0", "gdd5", "frost_days", "days_gt25", "days_gt30",
    "prec_ann", "prec_jja", "prec_amjjas", "wet_days_ge1", "dry_spell_max",
    "pet_ann", "pet_jja", "pet_amjjas", "cwb_ann", "cwb_jja", "cwb_amjjas", "cwb_min3",
    "rh_mean", "rh_jja", "vpd_mean", "vpd_jja", "vpd_win10_sum",
    "tstress_lt_m10", "tstress_lt_m15", "tstress_lt_m20",
    "swdown_ann", "lwdown_ann", "wind_ann",
]
TR20_SRC = ["tcold_month", "twarm_month", "gdd5"]
TR20_COLS = [f"{c}_tr20" for c in TR20_SRC]
RANGES = {"temp": (-50.0, 50.0), "prec": (0.0, 400.0), "humid": (0.0, 1.0), "swdown": (0.0, 500.0),
          "lwdown": (80.0, 550.0), "wind": (0.0, 50.0)}
GCM_TAG = {"MPI-ESM1-2-HR": "mpi", "ACCESS-CM2": "acc"}
WINDOWS = {"1950-1979_spinup_pool": (1950, 1979), "1985-2014": (1985, 2014), "2015-2044": (2015, 2044),
           "2045-2070_no_tree_table": (2045, 2070), "2071-2100": (2071, 2100)}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ----------------------------------------------------------------------------------------------- grid
def read_lpj_header(path):
    """Generic LPJ header (LPJGRID / LPJSOIL / LPJCLIM), v2 or v3. Returns dict + data offset + numpy dtype."""
    import struct

    with open(path, "rb") as f:
        raw = f.read(64)
    name = raw[:7].decode()
    version, order, firstyear, nyear, firstcell, ncell, nbands = struct.unpack("<7i", raw[7:35])
    if version >= 3:
        cs_lon, scalar, cs_lat = struct.unpack("<3f", raw[35:47])
        datatype = struct.unpack("<i", raw[47:51])[0]
        hdr = 51
    else:
        cs_lon, scalar = struct.unpack("<2f", raw[35:43])
        cs_lat, datatype, hdr = cs_lon, 1, 43
    dt = {0: "u1", 1: "<i2", 2: "<i4", 3: "<f4", 4: "<f8"}[datatype]
    size = os.path.getsize(path)
    exp = hdr + nyear * ncell * nbands * np.dtype(dt).itemsize
    if size != exp:
        raise SystemExit(f"FATAL {path}: size {size} != header-implied {exp}")
    return dict(name=name, version=version, order=order, firstyear=firstyear, nyear=nyear, firstcell=firstcell,
                ncell=ncell, nbands=nbands, cellsize_lon=cs_lon, cellsize_lat=cs_lat, scalar=scalar,
                datatype=datatype, hdr=hdr, size=size), dt


def read_grid(path):
    h, dt = read_lpj_header(path)
    assert h["name"] == "LPJGRID" and h["nbands"] == 2, h
    a = np.fromfile(path, dtype=dt, offset=h["hdr"]).reshape(h["ncell"], 2).astype(np.float64) * h["scalar"]
    return a[:, 0], a[:, 1], h  # lon, lat


def grid_int_index(lon, lat, lon0=5.9060216, lat0=47.341064, step=0.0703125):
    return np.rint((lon - lon0) / step).astype(np.int64), np.rint((lat - lat0) / step).astype(np.int64)


def old_to_new_map():
    """Index into the 9133-cell OLD grid for every cell of the run's 9067-cell grid (matched by position)."""
    lon, lat, _ = read_grid(GRID)
    lono, lato, _ = read_grid(GRID_OLD)
    ix, iy = grid_int_index(lon, lat)
    ixo, iyo = grid_int_index(lono, lato)
    d = {(a, b): i for i, (a, b) in enumerate(zip(ixo.tolist(), iyo.tolist(), strict=True))}
    idx = np.array([d.get((a, b), -1) for a, b in zip(ix.tolist(), iy.tolist(), strict=True)])
    # residual coordinate error of the match (the two grids differ in float precision only)
    ok = idx >= 0
    err = max(np.abs(lono[idx[ok]] - lon[ok]).max(), np.abs(lato[idx[ok]] - lat[ok]).max())
    return idx, int(ok.sum()), float(err)


# ----------------------------------------------------------------------------------------------- features
def vpd_c(temp, rh):
    """spitfire/getvpd.c EXACTLY (relative_humidity=TRUE branch). temp C, rh fraction -> VPD in Pa."""
    a, b, c, d, f, h, ts = -7.90298, 5.02808, -1.3816e-7, 11.344, 8.1328e-3, 3.49149, 373.16
    tk = temp + 273.16
    z = (a * (ts / tk - 1) + b * np.log10(ts / tk) + c * (np.power(10.0, np.power(d, 1 - tk / ts)) - 1)
         + f * (np.power(10.0, -np.power(h, ts / tk - 1)) - 1))
    rh = np.minimum(rh, 1.0)
    return np.power(10.0, z) * (1 - rh) * 101324.6


def daylength_hours(lat):
    """petpar2.c daylength, (N,) lat -> (N,365)."""
    day = np.arange(1, NB + 1, dtype=np.float64)
    delta = np.deg2rad(-23.4 * np.cos(2 * np.pi * (day + 10.0) / NB))
    u = np.sin(np.deg2rad(lat))[:, None] * np.sin(delta)[None, :]
    v = np.cos(np.deg2rad(lat))[:, None] * np.cos(delta)[None, :]
    hh = np.arccos(np.clip(-u / v, -1.0, 1.0))
    dl = 24 * hh / np.pi
    dl = np.where(u >= v, 24.0, dl)
    dl = np.where(u <= -v, 0.0, dl)
    return dl


def pet_pt(temp, swdown, lwdown, dl):
    """petpar2.c (islwdown=TRUE) equilibrium ET x PRIESTLEY_TAYLOR, mm/day, fixed albedo BETA."""
    s = 2.503e6 * np.exp(17.269 * temp / (237.3 + temp)) / ((237.3 + temp) ** 2)
    gam = 65.05 + temp * 0.064
    lam = 2.495e6 - temp * 2380
    lwnet = lwdown - SIGMA * np.power(temp + 273.15, 4)
    eeq = 86400 * (s / (s + gam) / lam) * ((1 - BETA) * swdown + lwnet * dl / 24)
    return PRIESTLEY_TAYLOR * np.maximum(eeq, 0.0)


def msum(a):
    return np.add.reduceat(a, MONTH_BOUNDS[:-1], axis=1)


def mmean(a):
    return msum(a) / DPM[None, :]


def year_features(T, P, RH, SW, LW, W, dl):
    """Daily (N,365) arrays for one year -> dict of (N,) float32 features."""
    out = {}
    tm, pm = mmean(T), msum(P)
    for name, arr in (("temp", tm), ("prec", pm), ("humid", mmean(RH)), ("swdown", mmean(SW)),
                      ("lwdown", mmean(LW)), ("wind", mmean(W))):
        for m in range(12):
            out[f"{name}_m{m + 1:02d}"] = arr[:, m]
    jja = slice(MONTH_BOUNDS[5], MONTH_BOUNDS[8])
    out["tmean_ann"] = T.mean(1)
    out["tcold_month"] = tm.min(1)
    out["twarm_month"] = tm.max(1)
    out["gdd0"] = np.maximum(T, 0).sum(1)
    out["gdd5"] = np.maximum(T - 5, 0).sum(1)
    out["frost_days"] = (T < 0).sum(1)
    out["days_gt25"] = (T > 25).sum(1)
    out["days_gt30"] = (T > 30).sum(1)
    out["prec_ann"] = P.sum(1)
    out["prec_jja"] = pm[:, 5:8].sum(1)
    out["prec_amjjas"] = pm[:, 3:9].sum(1)
    dry = P < 1.0
    out["wet_days_ge1"] = (~dry).sum(1)
    run = np.zeros(T.shape[0])
    best = np.zeros(T.shape[0])
    for d in range(NB):
        run = np.where(dry[:, d], run + 1, 0.0)
        np.maximum(best, run, out=best)
    out["dry_spell_max"] = best
    pet = pet_pt(T, SW, LW, dl)
    petm = msum(pet)
    out["pet_ann"] = pet.sum(1)
    out["pet_jja"] = petm[:, 5:8].sum(1)
    out["pet_amjjas"] = petm[:, 3:9].sum(1)
    cwbm = pm - petm
    out["cwb_ann"] = out["prec_ann"] - out["pet_ann"]
    out["cwb_jja"] = cwbm[:, 5:8].sum(1)
    out["cwb_amjjas"] = cwbm[:, 3:9].sum(1)
    out["cwb_min3"] = (cwbm[:, :-2] + cwbm[:, 1:-1] + cwbm[:, 2:]).min(1)
    vpd = vpd_c(T, RH) / 1000.0  # kPa
    out["rh_mean"] = RH.mean(1)
    out["rh_jja"] = RH[:, jja].mean(1)
    out["vpd_mean"] = vpd.mean(1)
    out["vpd_jja"] = vpd[:, jja].mean(1)
    w = slice(WIN_START0, NB)
    out["vpd_win10_sum"] = np.where(T[:, w] > 10.0, vpd[:, w], 0.0).sum(1)
    out["tstress_lt_m10"] = (T[:, w] < -10.0).sum(1)
    out["tstress_lt_m15"] = (T[:, w] < -15.0).sum(1)
    out["tstress_lt_m20"] = (T[:, w] < -20.0).sum(1)
    out["swdown_ann"] = SW.mean(1)
    out["lwdown_ann"] = LW.mean(1)
    out["wind_ann"] = W.mean(1)
    return {k: np.asarray(v, dtype=np.float32) for k, v in out.items()}


def forcing_path(gcm, leg, var):
    return os.path.join(FORC, gcm, f"{VARS[var]}_{gcm}_{leg}_germany.clm")


def process_leg(args):
    gcm, leg = args
    t0 = time.time()
    fy, ny = LEG_YEARS[leg]
    lon, lat, _ = read_grid(GRID)
    dl = daylength_hours(lat)
    mms, hdrs = {}, {}
    wind_remap = None
    for v in VARS:
        p = forcing_path(gcm, leg, v)
        h, _ = read_lpj_header(p)  # size == header-implied, else FATAL
        mm, firstyear, ncell, nbands, scalar = open_clm(p)  # canonical reader (also checks size)
        hdrs[v] = dict(path=p, **h, mtime=time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(p))))
        if firstyear != fy or mm.shape[0] != ny or nbands != NB:
            raise SystemExit(f"FATAL {p}: firstyear/nyear/nbands {firstyear}/{mm.shape[0]}/{nbands} "
                             f"!= expected {fy}/{ny}/{NB}")
        if ncell != NCELL:
            if v != "wind":
                raise SystemExit(f"FATAL {p}: ncell {ncell} != {NCELL} for a variable the model READS")
            idx, nfound, err = old_to_new_map()
            if ncell != 9133 or nfound != NCELL:
                raise SystemExit(f"FATAL {p}: ncell {ncell}; remap found {nfound}/{NCELL}")
            wind_remap = idx
            hdrs[v]["remapped_from_old_9133_grid"] = dict(found=nfound, max_coord_err_deg=err)
            log(f"{gcm} {leg} wind: {ncell}-cell file on the OLD grid -> remapped by coordinate "
                f"({nfound}/{NCELL} matched, max coord err {err:.2e} deg)")
        mms[v] = (mm, scalar)
    rng = {v: [np.inf, -np.inf, 0.0, 0] for v in VARS}  # min, max, sum, nan
    cols = {c: [] for c in MONTHLY_COLS + ANNUAL_COLS}
    raw_wind = []
    for iy in range(ny):
        arr = {}
        for v, (mm, scalar) in mms.items():
            a = np.asarray(mm[iy], dtype=np.float64) * scalar
            if v == "wind" and wind_remap is not None:
                if fy + iy <= 2044:
                    raw_wind.append(a[:NCELL].mean(1).astype(np.float32))  # what a positional read gives
                a = a[wind_remap]
            r = rng[v]
            r[0] = min(r[0], float(np.nanmin(a)))
            r[1] = max(r[1], float(np.nanmax(a)))
            r[2] += float(np.nanmean(a))
            r[3] += int(np.isnan(a).sum())
            arr[v] = a
        f = year_features(arr["temp"], arr["prec"], arr["humid"], arr["swdown"], arr["lwdown"], arr["wind"], dl)
        for c in cols:
            cols[c].append(f[c])
        if iy % 10 == 0:
            log(f"{gcm} {leg} year {fy + iy} done ({time.time() - t0:.0f}s)")
    years = np.repeat(np.arange(fy, fy + ny, dtype=np.int32), NCELL)
    cells = np.tile(np.arange(NCELL, dtype=np.int32), ny)
    df = pl.DataFrame({"gcm": [gcm] * len(years), "scen": [leg] * len(years), "Cell": cells, "Year": years,
                       **{c: np.concatenate(v) for c, v in cols.items()}})
    part = os.path.join(PARTS, f"cy_{gcm}_{leg}.parquet")
    df.write_parquet(part)
    if raw_wind:
        np.save(os.path.join(PARTS, f"rawwind_{gcm}_{leg}_2015_2044.npy"), np.stack(raw_wind))
    rinfo = {v: dict(min=r[0], max=r[1], mean=r[2] / ny, nan=r[3], lo=RANGES[v][0], hi=RANGES[v][1],
                     in_range=bool(r[0] >= RANGES[v][0] and r[1] <= RANGES[v][1] and r[3] == 0))
             for v, r in rng.items()}
    info = dict(gcm=gcm, leg=leg, rows=df.height, headers=hdrs, ranges=rinfo, seconds=time.time() - t0)
    with open(os.path.join(PARTS, f"cy_{gcm}_{leg}.json"), "w") as fh:
        json.dump(info, fh, indent=1, default=str)
    log(f"{gcm} {leg}: wrote {part} rows={df.height} in {time.time() - t0:.0f}s")
    return part


def stage_cy():
    os.makedirs(PARTS, exist_ok=True)
    jobs = [(g, leg) for g in GCMS for leg in LEGS]
    nproc = min(len(jobs), max(1, int(os.environ.get("SLURM_CPUS_PER_TASK", "8"))))
    from multiprocessing import get_context

    with get_context("spawn").Pool(nproc) as pool:
        for p in pool.imap_unordered(process_leg, jobs):
            log("part done", p)


# ----------------------------------------------------------------------------------------------- assemble
def to_mat(df, col):
    """df sorted by Cell, Year for one (gcm, scen) -> (ncell, nyear) array."""
    ny = df["Year"].n_unique()
    return df[col].to_numpy().reshape(NCELL, ny)


def trailing20(series, pad):
    """series (N, Y) with a (N,) pad for the 19 pre-series years -> (N, Y) trailing 20-yr mean incl. year y."""
    full = np.concatenate([np.repeat(pad[:, None], 19, axis=1), series], axis=1).astype(np.float64)
    cs = np.cumsum(np.concatenate([np.zeros((full.shape[0], 1)), full], axis=1), axis=1)
    return ((cs[:, 20:] - cs[:, :-20]) / 20.0).astype(np.float32)


def stage_assemble():
    t0 = time.time()
    blocks = []
    for g in GCMS:
        hist = pl.read_parquet(os.path.join(PARTS, f"cy_{g}_Historical.parquet")).sort(["Cell", "Year"])
        hy = hist["Year"].unique().sort().to_numpy()
        sp = (hy >= 1950) & (hy <= 1979)
        tr_h = {}
        for c in TR20_SRC:
            H = to_mat(hist, c)
            pad = H[:, sp].mean(1)  # [ASSUMPTION] the spin-up buffer = the 1950-1979 pool mean
            tr_h[c] = (H, pad)
        blocks.append(hist.with_columns([pl.Series(f"{c}_tr20", trailing20(H, pad).ravel())
                                         for c, (H, pad) in tr_h.items()]))
        for s in SSPS:
            d = pl.read_parquet(os.path.join(PARTS, f"cy_{g}_{s}.parquet")).sort(["Cell", "Year"])
            new = []
            for c in TR20_SRC:
                H, pad = tr_h[c]
                S = to_mat(d, c)
                tr = trailing20(np.concatenate([H, S], axis=1), pad)[:, H.shape[1]:]
                new.append(pl.Series(f"{c}_tr20", tr.ravel()))
            blocks.append(d.with_columns(new))
    cy = pl.concat(blocks, how="vertical").sort(["gcm", "scen", "Cell", "Year"])
    n_unique = cy.select(["gcm", "scen", "Cell", "Year"]).n_unique()
    expect = 2 * NCELL * (65 + 3 * 86)
    assert n_unique == cy.height == expect, (n_unique, cy.height, expect)
    cy.write_parquet(os.path.join(OUT, "cell_year.parquet"), compression="zstd")
    log(f"cell_year.parquet rows={cy.height} cols={cy.width} key-unique={n_unique == cy.height} "
        f"({time.time() - t0:.0f}s)")

    # static
    lon, lat, gh = read_grid(GRID)
    sh, sdt = read_lpj_header(SOIL)
    soil = np.fromfile(SOIL, dtype=sdt, offset=sh["hdr"]).astype(np.int32)
    ix, iy = grid_int_index(lon, lat)
    old_idx, _, _ = old_to_new_map()
    import netCDF4

    with netCDF4.Dataset(os.path.join(RUNS, GCMS[0], "Historical", "random_seed_1", "output", "grid_.nc")) as ds:
        cid = np.ma.filled(ds.variables["cellid"][:], -1)
    assert (cid[iy, ix] == np.arange(NCELL)).all(), "nc_ilat/nc_ilon do not reproduce the run's grid_.nc cellid"
    log("gate: (nc_ilat, nc_ilon) reproduce the run's own grid_.nc cellid for all 9067 cells")
    area = (111.194926 * gh["cellsize_lon"]) * (111.194926 * gh["cellsize_lat"]) * np.cos(np.deg2rad(lat))
    st = pl.DataFrame({"Cell": np.arange(NCELL, dtype=np.int32), "lon": lon, "lat": lat,
                       "soil_code": soil, "soil_name": [SOILMAP[k] for k in soil],
                       "nc_ilon": ix.astype(np.int32), "nc_ilat": iy.astype(np.int32),
                       "old9133_index": old_idx.astype(np.int32), "area_km2_approx": area})
    main = ["tmean_ann", "tcold_month", "twarm_month", "gdd5", "frost_days", "prec_ann", "prec_jja",
            "pet_ann", "cwb_ann", "cwb_jja", "cwb_min3", "dry_spell_max", "rh_mean", "vpd_mean", "vpd_win10_sum",
            "swdown_ann", "lwdown_ann"]
    base = (cy.filter((pl.col("scen") == "Historical") & pl.col("Year").is_between(1985, 2014))
            .group_by(["gcm", "Cell"]).agg([pl.col(c).cast(pl.Float64).mean() for c in main]))
    assert base.select(["gcm", "Cell"]).n_unique() == base.height == 2 * NCELL
    for g in GCMS:
        b = base.filter(pl.col("gcm") == g).drop("gcm").rename({c: f"c8514_{GCM_TAG[g]}_{c}" for c in main})
        st = st.join(b, on="Cell", how="left")
    st = st.sort("Cell")
    assert st.height == NCELL and st["Cell"].n_unique() == NCELL
    st.write_parquet(os.path.join(OUT, "cell_static.parquet"))
    log(f"cell_static.parquet rows={st.height} cols={st.width}")

    # windows
    feats = MONTHLY_COLS + ANNUAL_COLS
    wparts = []
    for wname, (y0, y1) in WINDOWS.items():
        sub = cy.filter(pl.col("Year").is_between(y0, y1))
        w = (sub.group_by(["gcm", "scen", "Cell"])
             .agg([pl.len().alias("n_years")] + [pl.col(c).cast(pl.Float64).mean() for c in feats])
             .with_columns(pl.lit(wname).alias("window")))
        wparts.append(w)
    wc = pl.concat(wparts, how="vertical")
    # 3071-3100 EXPECTED: the recycled pool IS 2071-2100 (with-replacement shuffle), so its expectation = that mean
    exp_ = wc.filter(pl.col("window") == "2071-2100").with_columns(pl.lit("3071-3100_expected=2071-2100")
                                                                  .alias("window"))
    wc = pl.concat([wc, exp_], how="vertical").sort(["gcm", "scen", "window", "Cell"])
    assert wc.select(["gcm", "scen", "Cell", "window"]).n_unique() == wc.height
    wc.write_parquet(os.path.join(OUT, "window_clim.parquet"))
    log(f"window_clim.parquet rows={wc.height} windows={wc['window'].unique().to_list()}")


# ----------------------------------------------------------------------------------------------- yearmap
def nc_years(ds):
    t = ds.variables["time"]
    y0 = int(t.units.split("since")[1].strip().split("-")[0])
    return y0 + (np.asarray(t[:]) // 365).astype(int)


def read_mpet(path, years, ilat, ilon):
    """C monthly PET for the requested years -> (len(years), 12, NCELL)."""
    import netCDF4

    with netCDF4.Dataset(path) as ds:
        yrs = nc_years(ds)
        out = np.empty((len(years), 12, NCELL), dtype=np.float64)
        v = ds.variables["PET"]
        for k, y in enumerate(years):
            idx = np.nonzero(yrs == y)[0]
            if len(idx) != 12:
                raise ValueError(f"{path}: year {y} has {len(idx)} months")
            a = np.ma.filled(v[idx[0]:idx[-1] + 1], np.nan)
            out[k] = a[:, ilat, ilon]
    return out


def nc_span(path):
    """(first, last) year on the file's time axis, or None when the axis is all fill (an unwritten file)."""
    import netCDF4

    with netCDF4.Dataset(path) as ds:
        t = np.ma.filled(ds.variables["time"][:].astype(np.float64), np.nan)
        if not np.isfinite(t).any():
            return None
        y0 = int(ds.variables["time"].units.split("since")[1].strip().split("-")[0])
    t = t[np.isfinite(t)]
    return int(y0 + t.min() // 365), int(y0 + t.max() // 365)


def usable(path, y0, y1):
    if not os.path.exists(path):
        return False
    sp = nc_span(path)
    return sp is not None and sp[0] <= y0 and sp[1] >= y1


def stage_yearmap():
    st = pl.read_parquet(os.path.join(OUT, "cell_static.parquet")).sort("Cell")
    ilat, ilon = st["nc_ilat"].to_numpy(), st["nc_ilon"].to_numpy()
    ref_years = list(range(2071, 2101))
    tgt_years = list(range(3071, 3101))
    rows, info = [], []
    for g in GCMS:
        for s in SSPS:
            for seed in (1, 2):
                od = os.path.join(RUNS, g, s, f"random_seed_{seed}", "output")
                ref_p = next(p for p in [os.path.join(od, "mpet_2100.nc"), os.path.join(od, "mpet_2100_backup.nc")]
                             if usable(p, 2071, 2100))
                ref = read_mpet(ref_p, ref_years, ilat, ilon)
                mu = ref.mean(0, keepdims=True)
                sd = ref.std(0, keepdims=True) + 1e-9
                rz = ((ref - mu) / sd).reshape(len(ref_years), -1)
                rz = rz / np.linalg.norm(rz, axis=1, keepdims=True)
                for fname in ("mpet_3100.nc", "mpet_3100_backup.nc"):
                    tp = os.path.join(od, fname)
                    if not os.path.exists(tp):
                        continue
                    span = nc_span(tp)
                    if not usable(tp, 3071, 3100):
                        info.append(dict(gcm=g, scen=s, seed=seed, file=fname, span=span, used=False,
                                         reason="time axis all fill (file never written)" if span is None
                                         else "does not cover 3071-3100"))
                        log(f"yearmap {g} {s} s{seed} {fname}: UNUSABLE span={span}")
                        continue
                    tgt = read_mpet(tp, tgt_years, ilat, ilon)
                    tz = ((tgt - mu) / sd).reshape(len(tgt_years), -1)
                    tz = tz / np.linalg.norm(tz, axis=1, keepdims=True)
                    C = tz @ rz.T
                    order = np.argsort(-C, axis=1)
                    best = C[np.arange(len(tgt_years)), order[:, 0]]
                    second = C[np.arange(len(tgt_years)), order[:, 1]]
                    for k, y in enumerate(tgt_years):
                        rows.append(dict(gcm=g, scen=s, seed=seed, source_file=fname, Year=y,
                                         climate_year=ref_years[order[k, 0]], corr_best=float(best[k]),
                                         corr_second=float(second[k]), margin=float(best[k] - second[k])))
                    info.append(dict(gcm=g, scen=s, seed=seed, file=fname, span=span, used=True,
                                     min_best=float(best.min()), min_margin=float((best - second).min())))
                    log(f"yearmap {g} {s} s{seed} {fname}: min best corr {best.min():.4f} "
                        f"min margin {(best - second).min():.4f} distinct years {len(set(order[:, 0]))}")
    ym = pl.DataFrame(rows)
    ym.write_parquet(os.path.join(OUT, "recycled_yearmap_3071_3100.parquet"))
    with open(os.path.join(OUT, "yearmap_info.json"), "w") as fh:
        json.dump(info, fh, indent=1)
    # realized 3071-3100 window climatology per seed (from the primary file mpet_3100.nc)
    cy = pl.read_parquet(os.path.join(OUT, "cell_year.parquet"),
                         columns=["gcm", "scen", "Cell", "Year"] + MONTHLY_COLS + ANNUAL_COLS)
    feats = MONTHLY_COLS + ANNUAL_COLS
    wparts = []
    # primary = mpet_3100.nc when usable, else the backup (MPI ssp370 seed 2: its mpet_3100.nc is unwritten)
    has_main = ym.group_by(["gcm", "scen", "seed"]).agg((pl.col("source_file") == "mpet_3100.nc").any().alias("m"))
    ym = ym.join(has_main, on=["gcm", "scen", "seed"]).with_columns(
        pl.when(pl.col("m")).then(pl.col("source_file") == "mpet_3100.nc")
        .otherwise(pl.col("source_file") == "mpet_3100_backup.nc").alias("primary")).drop("m")
    ym.write_parquet(os.path.join(OUT, "recycled_yearmap_3071_3100.parquet"))
    prim = ym.filter(pl.col("primary"))
    # is the recycled sequence a function of the seed only (identical across gcm x scen)?
    seqs = {}
    for (g, s, seed), grp in prim.group_by(["gcm", "scen", "seed"]):
        seqs[(g, s, seed)] = tuple(grp.sort("Year")["climate_year"].to_list())
    same = {}
    for seed in (1, 2):
        ss = [v for k, v in seqs.items() if k[2] == seed]
        same[f"seed{seed}_members"] = len(ss)
        same[f"seed{seed}_identical_across_members"] = len(set(ss)) == 1
        same[f"seed{seed}_sequence"] = list(ss[0]) if len(set(ss)) == 1 else None
        same[f"seed{seed}_distinct_years"] = len(set(ss[0]))
    same["seed1_equals_seed2"] = same["seed1_sequence"] == same["seed2_sequence"]
    info.append(dict(sequence_check=same))
    with open(os.path.join(OUT, "yearmap_info.json"), "w") as fh:
        json.dump(info, fh, indent=1)
    log(f"yearmap sequence check: {same}")
    for (g, s, seed), grp in prim.group_by(["gcm", "scen", "seed"]):
        mult = grp.group_by("climate_year").agg(pl.len().alias("w")).rename({"climate_year": "Year"})
        sub = cy.filter((pl.col("gcm") == g) & (pl.col("scen") == s)).join(mult, on="Year", how="inner")
        w = (sub.group_by(["gcm", "scen", "Cell"])
             .agg([pl.col("w").sum().alias("n_years")]
                  + [((pl.col(c).cast(pl.Float64) * pl.col("w")).sum() / pl.col("w").sum()).alias(c)
                     for c in feats])
             .with_columns(pl.lit(f"3071-3100_realized_s{seed}").alias("window")))
        wparts.append(w)
    wc = pl.read_parquet(os.path.join(OUT, "window_clim.parquet"))
    wc = wc.filter(~pl.col("window").str.starts_with("3071-3100_realized"))
    wc = pl.concat([wc] + [w.select(wc.columns).cast(wc.schema) for w in wparts], how="vertical")
    wc = wc.sort(["gcm", "scen", "window", "Cell"])
    assert wc.select(["gcm", "scen", "Cell", "window"]).n_unique() == wc.height
    wc.write_parquet(os.path.join(OUT, "window_clim.parquet"))
    log(f"window_clim.parquet now rows={wc.height} windows={sorted(wc['window'].unique().to_list())}")


def stage_yearmap_full():
    """The recycled sequence proved seed-only (identical across all 6 gcm x scen members of a seed), so recover the
    WHOLE 2101-3100 sequence once per seed, from two independent members that carry a merged 2101-3100 mpet file,
    and require the two to agree year by year."""
    import netCDF4

    st = pl.read_parquet(os.path.join(OUT, "cell_static.parquet")).sort("Cell")
    ilat, ilon = st["nc_ilat"].to_numpy(), st["nc_ilon"].to_numpy()
    ref_years = list(range(2071, 2101))
    rows = []
    for seed in (1, 2):
        cands = []
        for g in GCMS:
            for s in SSPS:
                p = os.path.join(RUNS, g, s, f"random_seed_{seed}", "output", "mpet_3100.nc")
                if usable(p, 2101, 3100):
                    cands.append((g, s, p))
        use = cands[:1] + cands[-1:] if len(cands) >= 2 else cands
        log(f"seed {seed}: {len(cands)} members carry 2101-3100; using {[(g, s) for g, s, _ in use]}")
        seqs = []
        for g, s, p in use:
            od = os.path.dirname(p)
            ref_p = next(q for q in [os.path.join(od, "mpet_2100.nc"), os.path.join(od, "mpet_2100_backup.nc")]
                         if usable(q, 2071, 2100))
            ref = read_mpet(ref_p, ref_years, ilat, ilon)
            mu, sd = ref.mean(0, keepdims=True), ref.std(0, keepdims=True) + 1e-9
            rz = ((ref - mu) / sd).reshape(len(ref_years), -1)
            rz /= np.linalg.norm(rz, axis=1, keepdims=True)
            with netCDF4.Dataset(p) as ds:
                yrs = nc_years(ds)
                a = np.ma.filled(ds.variables["PET"][:], np.nan)[:, ilat, ilon].astype(np.float64)
            years = np.arange(2101, 3101)
            tz = np.empty((len(years), 12 * NCELL))
            for k, y in enumerate(years):
                idx = np.nonzero(yrs == y)[0]
                assert len(idx) == 12, (p, y, len(idx))
                tz[k] = ((a[idx] - mu[0]) / sd[0]).ravel()
            tz /= np.linalg.norm(tz, axis=1, keepdims=True)
            C = tz @ rz.T
            order = np.argsort(-C, axis=1)
            best = C[np.arange(len(years)), order[:, 0]]
            second = C[np.arange(len(years)), order[:, 1]]
            seqs.append(dict(member=f"{g}/{s}", cy=np.array(ref_years)[order[:, 0]], best=best, margin=best - second))
            log(f"  {g}/{s}: min corr {best.min():.4f} min margin {(best - second).min():.4f}")
        agree = np.all([q["cy"] == seqs[0]["cy"] for q in seqs], axis=0)
        for k, y in enumerate(range(2101, 3101)):
            rows.append(dict(seed=seed, Year=y, climate_year=int(seqs[0]["cy"][k]),
                             corr_best_min=float(min(q["best"][k] for q in seqs)),
                             margin_min=float(min(q["margin"][k] for q in seqs)),
                             n_members=len(seqs), members_agree=bool(agree[k]),
                             members=";".join(q["member"] for q in seqs)))
        log(f"seed {seed}: members agree on {int(agree.sum())}/{len(agree)} years")
    df = pl.DataFrame(rows)
    # consistency with the 3071-3100 per-member map
    ym = pl.read_parquet(os.path.join(OUT, "recycled_yearmap_3071_3100.parquet")).filter(pl.col("primary"))
    chk = ym.join(df.select(["seed", "Year", pl.col("climate_year").alias("cy_full")]), on=["seed", "Year"])
    log(f"3071-3100 per-member map vs full per-seed map: {int((chk['climate_year'] == chk['cy_full']).sum())}"
        f"/{chk.height} rows agree")
    df.write_parquet(os.path.join(OUT, "recycled_yearmap_2101_3100_by_seed.parquet"))


# ----------------------------------------------------------------------------------------------- gates
def decomp(dt):
    """dt (N cells, M members) -> variance fractions (between-cell, within-cell) + two-way SS shares."""
    grand = dt.mean()
    tot = ((dt - grand) ** 2).sum()
    cell_m = dt.mean(1, keepdims=True)
    mem_m = dt.mean(0, keepdims=True)
    between = (dt.shape[1] * ((cell_m - grand) ** 2)).sum()
    within = ((dt - cell_m) ** 2).sum()
    ss_mem = (dt.shape[0] * ((mem_m - grand) ** 2)).sum()
    ss_int = ((dt - cell_m - mem_m + grand) ** 2).sum()
    return dict(total_var=float(tot / dt.size), frac_between_cell=float(between / tot),
                frac_within_cell=float(within / tot), frac_member_main=float(ss_mem / tot),
                frac_cell_x_member=float(ss_int / tot),
                within_cell_range_p05_p50_p95=[float(x) for x in np.percentile(dt.max(1) - dt.min(1), [5, 50, 95])])


def r2_linear(X, y):
    X1 = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    res = y - X1 @ beta
    return float(1 - res.var() / y.var())


def stage_gates():
    t0 = time.time()
    G = {"basis": "2 GCMs x (Historical 1950-2014 + ssp126/245/370 2015-2100), 9067 cells, daily forcing the runs "
                  "READ (wind: not read by the model)"}
    # 1 header + range gates (from the cy parts)
    hdr, rng = [], []
    for g in GCMS:
        for leg in LEGS:
            with open(os.path.join(PARTS, f"cy_{g}_{leg}.json")) as fh:
                info = json.load(fh)
            for v, h in info["headers"].items():
                hdr.append(dict(gcm=g, leg=leg, var=v, file=os.path.basename(h["path"]), version=h["version"],
                                datatype=h["datatype"], scalar=h["scalar"], firstyear=h["firstyear"],
                                nyear=h["nyear"], ncell=h["ncell"], nbands=h["nbands"], hdr=h["hdr"],
                                size=h["size"], size_matches_header=True,
                                remap=h.get("remapped_from_old_9133_grid")))
            for v, r in info["ranges"].items():
                rng.append(dict(gcm=g, leg=leg, var=v, **r))
    G["headers"] = hdr
    G["headers_pass"] = all(h["ncell"] == NCELL or h["remap"] is not None for h in hdr)
    G["ranges"] = rng
    G["ranges_pass"] = all(r["in_range"] for r in rng)
    log(f"headers {len(hdr)} files, pass={G['headers_pass']}; ranges pass={G['ranges_pass']}")

    cy = pl.read_parquet(os.path.join(OUT, "cell_year.parquet"))
    SPL = ["tmean_ann", "prec_ann", "rh_mean", "swdown_ann", "lwdown_ann", "wind_ann", "pet_ann", "vpd_mean"]

    cache = {}

    def mat(g, s, col):
        if (g, s) not in cache:
            cache[(g, s)] = cy.filter((pl.col("gcm") == g) & (pl.col("scen") == s)).sort(["Cell", "Year"])
        d = cache[(g, s)]
        return to_mat(d, col).astype(np.float64), d["Year"].unique().sort().to_numpy()

    # 2 splice
    spl = []
    for g in GCMS:
        for col in SPL:
            H, hy = mat(g, "Historical", col)
            steps, rs, sds = [], [], []
            for y in range(1960, 2006):  # decade (y..y+9) minus decade (y-10..y-1), all within historic
                a = H[:, (hy >= y - 10) & (hy <= y - 1)].mean(1)
                b = H[:, (hy >= y) & (hy <= y + 9)].mean(1)
                steps.append((b - a).mean())
                sds.append((b - a).std())
                rs.append(np.corrcoef(a, b)[0, 1])
            steps, rs, sds = np.array(steps), np.array(rs), np.array(sds)
            D2 = H[:, (hy >= 2005) & (hy <= 2014)].mean(1)
            for s in SSPS:
                S, sy = mat(g, s, col)
                D3 = S[:, (sy >= 2015) & (sy <= 2024)].mean(1)
                st_ = (D3 - D2).mean()
                z = (st_ - steps.mean()) / (steps.std() + 1e-12)
                r = float(np.corrcoef(D2, D3)[0, 1])
                sdc = float((D3 - D2).std())
                zres = None
                if col != "tmean_ann":  # the same step after removing its linear dependence on temperature
                    TH, _ = mat(g, "Historical", "tmean_ann")
                    TS, _ = mat(g, s, "tmean_ann")
                    xh, yh = TH.mean(0), H.mean(0)  # domain-mean annual series
                    b = np.polyfit(xh, yh, 1)
                    rh_ = yh - np.polyval(b, xh)
                    rs_ = S.mean(0) - np.polyval(b, TS.mean(0))
                    wsteps = np.array([rh_[(hy >= y) & (hy <= y + 9)].mean()
                                       - rh_[(hy >= y - 10) & (hy <= y - 1)].mean() for y in range(1960, 2006)])
                    rstep = rs_[(sy >= 2015) & (sy <= 2024)].mean() - rh_[(hy >= 2005) & (hy <= 2014)].mean()
                    zres = float((rstep - wsteps.mean()) / (wsteps.std() + 1e-12))
                ok = bool((abs(z) < 3 or (zres is not None and abs(zres) < 3)) and r >= rs.min() - 0.02
                          and sdc <= 2 * sds.max())
                spl.append(dict(gcm=g, scen=s, var=col, z_after_removing_T_dependence=zres,
                                step_2005_14_to_2015_24=float(st_),
                                within_hist_step_mean=float(steps.mean()), within_hist_step_sd=float(steps.std()),
                                within_hist_step_absmax=float(np.abs(steps).max()), z=float(z),
                                spatial_r_across_splice=r, within_hist_spatial_r_min=float(rs.min()),
                                percell_sd_splice=sdc, within_hist_percell_sd_max=float(sds.max()), pass_=ok))
    # raw-order wind of the stray file (what a positional read of the 9133-cell file gives)
    for p in sorted(os.listdir(PARTS)):
        if p.startswith("rawwind_"):
            g = p.split("_")[1]
            leg = p.split("_")[2]
            raw = np.load(os.path.join(PARTS, p))  # (30, NCELL) 2015-2044
            H, hy = mat(g, "Historical", "wind_ann")
            D2 = H[:, (hy >= 2005) & (hy <= 2014)].mean(1)
            spl.append(dict(gcm=g, scen=leg, var="wind_ann_RAW_POSITIONAL_READ",
                            step_2005_14_to_2015_24=float((raw[:10].mean(0) - D2).mean()),
                            spatial_r_across_splice=float(np.corrcoef(D2, raw[:10].mean(0))[0, 1]),
                            percell_sd_splice=float((raw[:10].mean(0) - D2).std()), pass_=False,
                            note="diagnostic only: this is what LPJmL WOULD read if it opened wind (it does not)"))
    G["splice"] = spl
    G["splice_pass"] = all(x["pass_"] for x in spl if not x["var"].endswith("RAW_POSITIONAL_READ"))
    log(f"splice pass={G['splice_pass']}; fails: "
        f"{[(x['gcm'], x['scen'], x['var']) for x in spl if not x['pass_']]}")

    # 3 scenario divergence + per-cell warming
    div, warm = [], []
    DV = ["tmean_ann", "prec_ann", "cwb_ann", "vpd_mean", "gdd5", "tcold_month", "twarm_month", "rh_mean",
          "swdown_ann", "pet_ann"]
    for g in GCMS:
        base = {c: mat(g, "Historical", c) for c in DV}
        per = {}
        for s in SSPS:
            for c in DV:
                S, sy = mat(g, s, c)
                H, hy = base[c]
                per[(s, c)] = (S[:, (sy >= 2071) & (sy <= 2100)].mean(1) - H[:, (hy >= 1985) & (hy <= 2014)].mean(1))
            S, sy = mat(g, s, "tmean_ann")
            d = per[(s, "tmean_ann")]
            warm.append(dict(gcm=g, scen=s, dT_mean=float(d.mean()), dT_sd=float(d.std()), dT_min=float(d.min()),
                             dT_p05=float(np.percentile(d, 5)), dT_p50=float(np.median(d)),
                             dT_p95=float(np.percentile(d, 95)), dT_max=float(d.max()),
                             **{f"d_{c}_mean": float(per[(s, c)].mean()) for c in DV if c != "tmean_ann"},
                             dprec_pct_mean=float((per[(s, "prec_ann")] /
                                                   base["prec_ann"][0][:, (base["prec_ann"][1] >= 1985) &
                                                                       (base["prec_ann"][1] <= 2014)].mean(1)).mean()
                                                  * 100)))
        for a, b in (("ssp126", "ssp245"), ("ssp245", "ssp370"), ("ssp126", "ssp370")):
            Sa, sy = mat(g, a, "tmean_ann")
            Sb, _ = mat(g, b, "tmean_ann")
            ident_2015 = float((Sa[:, sy == 2015] == Sb[:, sy == 2015]).mean())
            ident_all = float((Sa == Sb).mean())
            dd = per[(b, "tmean_ann")] - per[(a, "tmean_ann")]
            div.append(dict(gcm=g, pair=f"{b}-{a}", frac_identical_celly_tmean_2015=ident_2015,
                            frac_identical_celly_tmean_2015_2100=ident_all,
                            diff_2015_domain_mean=float((Sb[:, sy == 2015] - Sa[:, sy == 2015]).mean()),
                            dT_2071_2100_diff_mean=float(dd.mean()), dT_diff_min=float(dd.min()),
                            dT_diff_max=float(dd.max()), frac_cells_b_warmer=float((dd > 0).mean())))
    G["scenario_divergence"] = div
    G["warming_per_member"] = warm
    log("warming", [(w["gcm"], w["scen"], round(w["dT_mean"], 3)) for w in warm])

    # 4 C-PET cross-check (Historical seed 1, 1985-2014)
    st = pl.read_parquet(os.path.join(OUT, "cell_static.parquet")).sort("Cell")
    ilat, ilon = st["nc_ilat"].to_numpy(), st["nc_ilon"].to_numpy()
    petg = []
    for g in GCMS:
        p = os.path.join(RUNS, g, "Historical", "random_seed_1", "output", "mpet_.nc")
        yrs = list(range(1985, 2015))
        cp = read_mpet(p, yrs, ilat, ilon)  # (30,12,N)
        c_ann = cp.sum(1)  # (30, N)
        c_jja = cp[:, 5:8].sum(1)
        mine, _ = mat(g, "Historical", "pet_ann")
        minej, hy = mat(g, "Historical", "pet_jja")
        sel = (hy >= 1985) & (hy <= 2014)
        m_ann, m_jja = mine[:, sel].T, minej[:, sel].T
        ratio = c_ann / m_ann
        petg.append(dict(gcm=g, basis="Historical seed1 1985-2014, 9067 cells x 30 yr",
                         corr_ann_pooled=float(np.corrcoef(c_ann.ravel(), m_ann.ravel())[0, 1]),
                         corr_ann_spatial_clim=float(np.corrcoef(c_ann.mean(0), m_ann.mean(0))[0, 1]),
                         corr_ann_interannual_domain=float(np.corrcoef(c_ann.mean(1), m_ann.mean(1))[0, 1]),
                         ratio_C_over_mine_p05_p50_p95=[float(x) for x in np.percentile(ratio, [5, 50, 95])],
                         corr_jja_pooled=float(np.corrcoef(c_jja.ravel(), m_jja.ravel())[0, 1]),
                         ratio_jja_p50=float(np.median(c_jja / m_jja)),
                         C_ann_mean=float(c_ann.mean()), mine_ann_mean=float(m_ann.mean())))
    G["pet_vs_C"] = petg
    log("pet vs C", petg)

    # 5 confound
    CF = ["tmean_ann", "prec_ann", "cwb_ann", "vpd_mean", "gdd5", "tcold_month", "cwb_jja"]
    BASEF = ["tmean_ann", "tcold_month", "twarm_month", "prec_ann", "cwb_ann", "rh_mean", "swdown_ann", "gdd5"]
    members = [(g, s) for g in GCMS for s in SSPS]
    bl = {}
    for g in GCMS:
        for c in set(CF) | set(BASEF):
            H, hy = mat(g, "Historical", c)
            bl[(g, c)] = H[:, (hy >= 1985) & (hy <= 2014)].mean(1)
    fut, fut_near = {}, {}
    for g, s in members:
        for c in CF:
            S, sy = mat(g, s, c)
            fut[(g, s, c)] = S[:, (sy >= 2071) & (sy <= 2100)].mean(1)
            fut_near[(g, s, c)] = S[:, (sy >= 2015) & (sy <= 2044)].mean(1)
    conf = {}
    for c in CF:
        dt = np.column_stack([fut[(g, s, c)] - bl[(g, c)] for g, s in members])  # (N, 6)
        entry = decomp(dt)
        per_m = []
        for k, (g, s) in enumerate(members):
            X = np.column_stack([bl[(g, b)] for b in BASEF])
            per_m.append(dict(member=f"{g}/{s}", corr_with_baseline_T=float(np.corrcoef(bl[(g, "tmean_ann")],
                                                                                         dt[:, k])[0, 1]),
                              r2_on_baseline_climate=r2_linear(X, dt[:, k]), mean=float(dt[:, k].mean()),
                              sd_across_cells=float(dt[:, k].std())))
        entry["per_member"] = per_m
        yb = dt.T.ravel()  # member-major
        Xb = np.vstack([np.column_stack([bl[(g, b)] for b in BASEF]) for g, s in members])
        entry["pooled_corr_with_baseline_T"] = float(np.corrcoef(Xb[:, 0], yb)[0, 1])
        entry["pooled_r2_on_baseline_climate"] = r2_linear(Xb, yb)
        dummies = np.zeros((len(yb), len(members) - 1))
        for k in range(1, len(members)):
            dummies[k * NCELL:(k + 1) * NCELL, k - 1] = 1
        entry["pooled_r2_member_dummies_only"] = r2_linear(dummies, yb)
        entry["pooled_r2_baseline_plus_member"] = r2_linear(np.column_stack([Xb, dummies]), yb)
        dn = np.column_stack([fut_near[(g, s, c)] - bl[(g, c)] for g, s in members])
        near = decomp(dn)
        near["per_member_mean"] = [float(x) for x in dn.mean(0)]
        near["per_member_sd_across_cells"] = [float(x) for x in dn.std(0)]
        near["per_member_corr_with_baseline_T"] = [float(np.corrcoef(bl[(g, "tmean_ann")], dn[:, k])[0, 1])
                                                   for k, (g, s) in enumerate(members)]
        entry["horizon_2015_2044_vs_1985_2014"] = near
        conf[c] = entry
        log(f"confound {c}: within-cell frac {entry['frac_within_cell']:.3f} "
            f"pooled r2(baseline) {entry['pooled_r2_on_baseline_climate']:.3f} "
            f"per-member r2 {[round(x['r2_on_baseline_climate'], 3) for x in per_m]}")
    # annual temperature at the YEAR level (what a year-step emulator sees): variance between vs within cell
    sub = cy.filter(pl.col("Year").is_between(1985, 2100))
    tot = sub["tmean_ann"].cast(pl.Float64).var(ddof=0)
    cm = sub.group_by("Cell").agg(pl.col("tmean_ann").cast(pl.Float64).mean().alias("m"),
                                  pl.len().alias("n"))
    gm = sub["tmean_ann"].cast(pl.Float64).mean()
    betw = float(((cm["m"] - gm) ** 2 * cm["n"]).sum() / cm["n"].sum())
    conf["annual_tmean_rows_1985_2100_all_members"] = dict(
        rows=sub.height, total_var=float(tot), frac_between_cell=betw / float(tot),
        frac_within_cell=1 - betw / float(tot))
    # is a cell's future hotter than ANY cell's baseline? (extrapolation beyond the present-day envelope)
    hot = {}
    for g, s in members:
        f_ = fut[(g, s, "tmean_ann")]
        hot[f"{g}/{s}"] = float((f_ > max(bl[(gg, "tmean_ann")].max() for gg in GCMS)).mean())
    conf["frac_cells_future_tmean_above_hottest_baseline_cell"] = hot
    G["confound"] = conf

    with open(os.path.join(OUT, "gates.json"), "w") as fh:
        json.dump(G, fh, indent=1, default=float)
    log(f"gates.json written ({time.time() - t0:.0f}s)")


def stage_verify():
    """Independent re-read of the RAW daily files (own header parse + memmap, not open_clm / year_features) for
    random (gcm, leg, cell, year) samples, recomputing features with plain loops and comparing to cell_year.parquet;
    plus the wind-remap check and the T-adjusted per-cell splice residual. -> verify.json"""
    import struct

    rng_ = np.random.default_rng(20260930)
    cy = pl.read_parquet(os.path.join(OUT, "cell_year.parquet"))
    dpm = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    starts = np.concatenate([[0], np.cumsum(dpm)])
    V = {}

    def raw_cell_year(path, cell, year):
        with open(path, "rb") as f:
            b = f.read(51)
        assert b[:7] == b"LPJCLIM"
        ver, _o, fy, ny, _fc, nc, nb = struct.unpack("<7i", b[7:35])
        assert ver == 3
        _csl, sc, _csa = struct.unpack("<3f", b[35:47])
        dt = struct.unpack("<i", b[47:51])[0]
        assert dt == 3, dt
        assert os.path.getsize(path) == 51 + ny * nc * nb * 4
        m = np.memmap(path, dtype="<f4", mode="r", offset=51, shape=(ny, nc, nb))
        return np.asarray(m[year - fy, cell], dtype=np.float64) * sc, nc

    samples, worst = [], {}
    for _ in range(48):
        g = GCMS[rng_.integers(2)]
        leg = LEGS[rng_.integers(4)]
        fy, ny = LEG_YEARS[leg]
        year = int(fy + rng_.integers(ny))
        cell = int(rng_.integers(NCELL))
        d = {}
        for v in ["temp", "prec", "humid", "swdown", "lwdown"]:
            d[v], nc = raw_cell_year(forcing_path(g, leg, v), cell, year)
            assert nc == NCELL
        T, P = d["temp"], d["prec"]
        mine = {}
        tm = [T[starts[k]:starts[k + 1]].mean() for k in range(12)]
        pm = [P[starts[k]:starts[k + 1]].sum() for k in range(12)]
        for k in range(12):
            mine[f"temp_m{k + 1:02d}"] = tm[k]
            mine[f"prec_m{k + 1:02d}"] = pm[k]
            mine[f"humid_m{k + 1:02d}"] = d["humid"][starts[k]:starts[k + 1]].mean()
        mine["tmean_ann"] = T.mean()
        mine["tcold_month"] = min(tm)
        mine["twarm_month"] = max(tm)
        mine["gdd0"] = sum(max(t, 0.0) for t in T)
        mine["gdd5"] = sum(max(t - 5.0, 0.0) for t in T)
        mine["frost_days"] = sum(1 for t in T if t < 0)
        mine["days_gt25"] = sum(1 for t in T if t > 25)
        mine["days_gt30"] = sum(1 for t in T if t > 30)
        mine["prec_ann"] = P.sum()
        mine["prec_jja"] = P[starts[5]:starts[8]].sum()
        mine["prec_amjjas"] = P[starts[3]:starts[9]].sum()
        mine["wet_days_ge1"] = sum(1 for p in P if p >= 1.0)
        run = best = 0
        for p in P:
            run = run + 1 if p < 1.0 else 0
            best = max(best, run)
        mine["dry_spell_max"] = best
        mine["rh_mean"] = d["humid"].mean()
        mine["swdown_ann"] = d["swdown"].mean()
        mine["lwdown_ann"] = d["lwdown"].mean()
        row = cy.filter((pl.col("gcm") == g) & (pl.col("scen") == leg) & (pl.col("Cell") == cell)
                        & (pl.col("Year") == year))
        assert row.height == 1
        errs = {}
        for c, val in mine.items():
            e = abs(float(row[c][0]) - float(val)) / max(1.0, abs(float(val)))
            errs[c] = e
            worst[c] = max(worst.get(c, 0.0), e)
        samples.append(dict(gcm=g, leg=leg, cell=cell, year=year, max_rel_err=max(errs.values())))
    V["spot_check"] = dict(n_samples=len(samples), n_features=len(worst), worst_rel_err_by_feature=worst,
                           max_rel_err=max(worst.values()), pass_=bool(max(worst.values()) < 1e-5),
                           samples=samples,
                           note="rel err = |parquet - independent| / max(1,|independent|); parquet is float32")
    log(f"spot check: {len(samples)} samples x {len(worst)} features, max rel err {max(worst.values()):.2e}")

    # wind remap: MPI ssp245 (the one 9133-cell file) vs its sibling scenarios over 2015-2024
    def wmean(s, y0, y1):
        return (cy.filter((pl.col("gcm") == "MPI-ESM1-2-HR") & (pl.col("scen") == s)
                          & pl.col("Year").is_between(y0, y1))
                .group_by("Cell").agg(pl.col("wind_ann").cast(pl.Float64).mean()).sort("Cell"))["wind_ann"].to_numpy()

    wm = {s: wmean(s, 2015, 2024) for s in SSPS}
    h = wmean("Historical", 2005, 2014)
    raw = np.load(os.path.join(PARTS, "rawwind_MPI-ESM1-2-HR_ssp245_2015_2044.npy"))[:10].mean(0)
    V["wind_remap"] = dict(
        r_remapped_ssp245_vs_ssp126=float(np.corrcoef(wm["ssp245"], wm["ssp126"])[0, 1]),
        r_remapped_ssp245_vs_ssp370=float(np.corrcoef(wm["ssp245"], wm["ssp370"])[0, 1]),
        r_ssp126_vs_ssp370=float(np.corrcoef(wm["ssp126"], wm["ssp370"])[0, 1]),
        r_remapped_ssp245_vs_hist_2005_2014=float(np.corrcoef(wm["ssp245"], h)[0, 1]),
        r_positional_ssp245_vs_hist_2005_2014=float(np.corrcoef(raw, h)[0, 1]),
        note="wind is NOT read by these runs (run log lists temp/prec/lwdown/swdown/rhumid only)")
    log(f"wind remap: {V['wind_remap']}")

    # splice after removing the linear (domain-mean) T dependence, evaluated per cell
    spl = []
    for g in GCMS:
        hist = cy.filter((pl.col("gcm") == g) & (pl.col("scen") == "Historical")).sort(["Cell", "Year"])
        hy = hist["Year"].unique().sort().to_numpy()
        TH = to_mat(hist, "tmean_ann").astype(np.float64)
        for col in ["lwdown_ann", "swdown_ann", "rh_mean", "prec_ann"]:
            H = to_mat(hist, col).astype(np.float64)
            b = np.polyfit(TH.mean(0), H.mean(0), 1)[0]
            rh = H - b * TH
            d2 = rh[:, (hy >= 2005) & (hy <= 2014)].mean(1)
            hsteps = np.array([rh[:, (hy >= y) & (hy <= y + 9)].mean() - rh[:, (hy >= y - 10) & (hy <= y - 1)].mean()
                               for y in range(1960, 2006)])
            for s in SSPS:
                d = cy.filter((pl.col("gcm") == g) & (pl.col("scen") == s)).sort(["Cell", "Year"])
                S = to_mat(d, col).astype(np.float64)
                TS = to_mat(d, "tmean_ann").astype(np.float64)
                sy = d["Year"].unique().sort().to_numpy()
                st_ = (S - b * TS)[:, (sy >= 2015) & (sy <= 2024)].mean(1) - d2
                spl.append(dict(gcm=g, scen=s, var=col, slope_per_K=float(b), resid_step_mean=float(st_.mean()),
                                resid_step_cell_p05_p95=[float(x) for x in np.percentile(st_, [5, 95])],
                                within_hist_resid_step_sd=float(hsteps.std()),
                                within_hist_resid_step_absmax=float(np.abs(hsteps).max()),
                                z=float((st_.mean() - hsteps.mean()) / (hsteps.std() + 1e-12))))
    V["splice_T_adjusted"] = spl
    for x in spl:
        log(f"splice {x['gcm']} {x['scen']} {x['var']}: T-adj step {x['resid_step_mean']:.3f} "
            f"(hist sd {x['within_hist_resid_step_sd']:.3f}, absmax {x['within_hist_resid_step_absmax']:.3f}) "
            f"z {x['z']:.2f}")
    with open(os.path.join(OUT, "verify.json"), "w") as fh:
        json.dump(V, fh, indent=1, default=float)
    log("verify.json written")


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    os.makedirs(OUT, exist_ok=True)
    stages = {"cy": stage_cy, "assemble": stage_assemble, "yearmap": stage_yearmap,
              "yearmap_full": stage_yearmap_full, "gates": stage_gates, "verify": stage_verify}
    for s in (list(stages) if stage == "all" else stage.split(",")):
        log(f"=== stage {s} ===")
        stages[s]()
    log("=== explore_de_climate DONE ===")
