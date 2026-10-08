#!/usr/bin/env python3
"""explore_glob_climate.py -- LINE X, the CLIMATE inputs for M. Billing's global LPJmL-FIT runs (ADR 0313/0314).

PREP, NOT A FINDING about the forest. Per (gcm, scen, Cell, Year) climate features for the global training set,
on the SAME feature definitions as the Germany arms (scripts/explore_de_climate.py + explore_de_sh_climate_ext.py)
so the arms can be re-targeted without touching their feature code. Read-only w.r.t. every input; writes ONLY
under /p/projects/open/Jamir/esm_land_emulator_data/billing_global/climate/ (never home: owner rule 2026-10-05).

STAGES (positional arg 1; a comma list also works)
  cy        read the daily forcing of every (forcing, leg) in decade chunks, in parallel -> parts/*.parquet
  assemble  parts -> cell_year/<gcm>_<scen>.parquet (+ *_tr20, anom_*), cell_static.parquet
  gates     headers/ranges, the printed per-tree mort_temp reproduced from tstress_pft<Type> on every converted
            dev table (the end-to-end check that file, cell order and accumulator window are what the C saw),
            and a humidity plausibility check -> _gates.json
  all       cy, assemble, gates

------------------------------------------------------------------------------------------------
WHAT THE RUNS READ (their input_*.js + logs, [VERIFIED 2026-10-08]):
  GFDL-ESM4 historical  /p/projects/lpjml/input/scenarios/ISIMIP3bv2/historical/GFDL-ESM4/<v>_gfdl-esm4_historical_1850-2014.clm
  GFDL-ESM4 ssp<x>      /p/projects/lpjml/input/scenarios/ISIMIP3bv2/ssp<x>/GFDL-ESM4/<v>_gfdl-esm4_ssp<x>_2015-2100.clm
  GSWP3-W5E5 obsclim    /p/projects/lpjml/input/historical/ISIMIP3av2/obsclim/GSWP3-W5E5/<v>_gswp3-w5e5_obsclim_1901-2019.clm
  v = tas (degC), pr (mm/d), rsds (W/m2), lwnet (W/m2, NET longwave: "radiation":"radiation"), huss (kg/kg,
  SPECIFIC humidity: "relative_humidity": false), sfcwind (listed but NOT read: initclimate opens wind only for
  SPITFIRE or nitrogen; these runs use GlobFIRM and with_nitrogen "no" -> wind_ann is built for layout parity,
  never condition on it). Cells in /p/projects/biodiversity/input_VERSION2/grid.bin order (Hainich = 28008), the
  same order as the converted tree tables -> they join on Cell directly. Mixed-version .clm: tas/pr/rsds/lwnet/
  sfcwind are v2 int16 with scalar, huss v3 float32 -> header-driven reader (build_transient_boundary.open_clm).

  HUMIDITY: getvpd.c's specific -> relative conversion rh = 0.263 * p * q / exp(17.67 T / (T + 273.16 - 29.65))
  with p = 1013.25 (hPa) returns rh as a FRACTION (the textbook form with p in Pa returns percent), clipped at 1 --
  i.e. it is CORRECT [VERIFIED 2026-10-08: mean rh 0.63 over 500 cells x 365 d of 1990]. rh_* / vpd_* below use it
  exactly; vpd_*_eff == vpd_* (no humidity defect in these runs; the _eff names exist for Germany layout parity).
  huss_mean = the raw input. VPD reaches the trees only through the water-stress mortality integral
  (waterstress_tree.c:36). The `humidity` gate checks rh stays plausible (mean in [0.3, 0.9]).

  PET: petpar2.c with islwdown = FALSE (lwnet used as is, no sigma T^4 term), fixed albedo BETA = 0.17
  [ASSUMPTION: the C uses the dynamic patch albedo] x PRIESTLEY_TAYLOR 1.32.

  ACCUMULATOR WINDOW (tempstress_tree.c / waterstress_tree.c, CLAUDE.md ADR 0244): reset AFTER the increment on
  day 14 (lat >= 0) or day 195 (lat < 0), so the annual mortality reads days 15..365 (north) / 196..365 (south).
  tstress_*, vpd_win10_sum* use that per-cell window. Soil-layer-1 temperature (the >10 C gate) is proxied by
  air temperature [ASSUMPTION; CLAUDE.md: no lag at 4 of 5 biome cells].

  JJA columns are CALENDAR June-August (layout parity with Germany); the *_hs columns are the HEMISPHERE summer
  (JJA for lat >= 0, Jan+Feb+Dec of the same calendar year for lat < 0).

CONVENTIONS: noleap 365-day calendar; features float32; key (gcm, scen, Cell, Year); scen in {historical, ssp126,
ssp245, ssp370, obsclim}. *_tr20 = trailing 20-yr mean incl. year y, computed from real forcing years (1932 on,
ssp legs continue the historical leg). anom_<f> = f minus the same gcm's 1985-2014 mean of f in that cell (its
historical leg for GFDL-ESM4, obsclim itself for GSWP3-W5E5).
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
from explore_de_climate import daylength_hours, read_lpj_header, vpd_c  # noqa: E402

OUT = "/p/projects/open/Jamir/esm_land_emulator_data/billing_global/climate"
PARTS = os.path.join(OUT, "parts")
CY_DIR = os.path.join(OUT, "cell_year")
IND_DEV = "/p/projects/open/Jamir/esm_land_emulator_data/billing_global/ind_dev"
GRID = "/p/projects/biodiversity/input_VERSION2/grid.bin"
SOIL_RAW = "/p/projects/biodiversity/input_VERSION2/soil_new_67420.bin"
PFT_CSV = os.path.join(REPO, "test", "testitems", "references", "S_pft_mortality_params.csv")
NCELL = 67420
NB = 365
BETA = 0.17
PRIESTLEY_TAYLOR = 1.32
P_HPA = 1013.25  # getvpd.c's surface pressure (hPa) -> rh as a fraction

ISIMIP3B = "/p/projects/lpjml/input/scenarios/ISIMIP3bv2"
OBSCLIM = "/p/projects/lpjml/input/historical/ISIMIP3av2/obsclim/GSWP3-W5E5"
FILEVAR = {"temp": "tas", "prec": "pr", "swdown": "rsds", "lwnet": "lwnet", "humid": "huss", "wind": "sfcwind"}
# (gcm, scen) -> (file pattern, first year computed, first year stored, last year)
LEGS = {
    ("GFDL-ESM4", "historical"): (ISIMIP3B + "/historical/GFDL-ESM4/{v}_gfdl-esm4_historical_1850-2014.clm",
                                  1932, 1951, 2014),
    ("GFDL-ESM4", "ssp126"): (ISIMIP3B + "/ssp126/GFDL-ESM4/{v}_gfdl-esm4_ssp126_2015-2100.clm", 2015, 2015, 2100),
    ("GFDL-ESM4", "ssp245"): (ISIMIP3B + "/ssp245/GFDL-ESM4/{v}_gfdl-esm4_ssp245_2015-2100.clm", 2015, 2015, 2100),
    ("GFDL-ESM4", "ssp370"): (ISIMIP3B + "/ssp370/GFDL-ESM4/{v}_gfdl-esm4_ssp370_2015-2100.clm", 2015, 2015, 2100),
    ("GSWP3-W5E5", "obsclim"): (OBSCLIM + "/{v}_gswp3-w5e5_obsclim_1901-2019.clm", 1932, 1951, 2019),
}
SSPS = ("ssp126", "ssp245", "ssp370")
RANGES = {"temp": (-80.0, 60.0), "prec": (0.0, 2000.0), "humid": (0.0, 0.06), "swdown": (0.0, 600.0),
          "lwnet": (-300.0, 150.0), "wind": (0.0, 60.0)}
KEY = ["gcm", "scen", "Cell", "Year"]
CHUNK = 10

MONTHLY_VARS = ["temp", "prec", "humid", "swdown", "lwnet", "wind"]
MONTHLY_COLS = [f"{v}_m{m:02d}" for v in MONTHLY_VARS for m in range(1, 13)]
ANNUAL_COLS = [
    "tmean_ann", "tcold_month", "twarm_month", "gdd0", "gdd5", "frost_days", "days_gt25", "days_gt30",
    "prec_ann", "prec_jja", "prec_amjjas", "wet_days_ge1", "dry_spell_max",
    "pet_ann", "pet_jja", "pet_amjjas", "cwb_ann", "cwb_jja", "cwb_amjjas", "cwb_min3",
    "rh_mean", "rh_jja", "vpd_mean", "vpd_jja", "vpd_win10_sum",
    "tstress_lt_m10", "tstress_lt_m15", "tstress_lt_m20",
    "swdown_ann", "lwnet_ann", "wind_ann",
    # global additions
    "huss_mean", "prec_hs", "cwb_hs", "vpd_hs",
]
EFF = {"vpd_mean": "vpd_mean_eff", "vpd_jja": "vpd_jja_eff", "vpd_win10_sum": "vpd_win10_sum_eff"}
TR20_SRC = ["tcold_month", "twarm_month", "gdd5"]
ANOM_SKIP = {"wind_ann"}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def pft_temp_params() -> pl.DataFrame:
    df = pl.read_csv(PFT_CSV, comment_prefix="#")
    return df.select(pl.col("pft_id").cast(pl.Int32), pl.col("temp_low").cast(pl.Float64),
                     pl.col("temp_high").cast(pl.Float64), pl.col("mort_temp_factor").cast(pl.Float64),
                     pl.col("ndayyear").cast(pl.Float64)).sort("pft_id")


def read_grid():
    h, dt = read_lpj_header(GRID)
    assert h["name"] == "LPJGRID" and h["ncell"] == NCELL and h["nbands"] == 2, h
    a = np.fromfile(GRID, dtype=dt, offset=h["hdr"]).reshape(NCELL, 2).astype(np.float64) * h["scalar"]
    return a[:, 0], a[:, 1]


def window_mask(lat):
    """(N,365) bool: the days the C's annual stress accumulators hold at the annual mortality call."""
    d = np.arange(NB)[None, :]
    start = np.where(lat >= 0.0, 14, 195)[:, None]  # 0-based index of the first day after the reset day
    return d >= start


def summer_mask(lat):
    d = np.arange(NB)[None, :]
    jja = (d >= MONTH_BOUNDS[5]) & (d < MONTH_BOUNDS[8])
    djf = (d < MONTH_BOUNDS[2]) | (d >= MONTH_BOUNDS[11])
    return np.where((lat >= 0.0)[:, None], jja, djf)


def rh_from_q(q, temp, p=P_HPA):
    """getvpd.c's specific -> relative humidity conversion (fraction), clipped at 1."""
    tk = temp + 273.16
    return np.minimum(0.263 * p * q / np.exp(17.67 * temp / (tk - 29.65)), 1.0)


def pet_pt(temp, swdown, lwnet, dl):
    """petpar2.c (islwdown = FALSE) eeq x PRIESTLEY_TAYLOR, mm/day, fixed albedo BETA."""
    s = 2.503e6 * np.exp(17.269 * temp / (237.3 + temp)) / ((237.3 + temp) ** 2)
    gam = 65.05 + temp * 0.064
    lam = 2.495e6 - temp * 2380
    eeq = 86400 * (s / (s + gam) / lam) * ((1 - BETA) * swdown + lwnet * dl / 24)
    return PRIESTLEY_TAYLOR * np.maximum(eeq, 0.0)


def msum(a):
    return np.add.reduceat(a, MONTH_BOUNDS[:-1], axis=1)


def year_features(T, P, Q, SW, LW, W, dl, win, hs, lo, hi):
    out = {}
    tm, pm = msum(T) / DPM[None, :], msum(P)
    for name, arr in (("temp", tm), ("prec", pm), ("humid", msum(Q) / DPM[None, :]),
                      ("swdown", msum(SW) / DPM[None, :]), ("lwnet", msum(LW) / DPM[None, :]),
                      ("wind", msum(W) / DPM[None, :])):
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
    rh = rh_from_q(Q, T)
    vpd = vpd_c(T, rh) / 1000.0  # kPa, == getvpd(relative_humidity = FALSE) exactly
    nhs = hs.sum(1)
    out["rh_mean"] = rh.mean(1)
    out["rh_jja"] = rh[:, jja].mean(1)
    out["vpd_mean"] = vpd.mean(1)
    out["vpd_jja"] = vpd[:, jja].mean(1)
    warm_win = win & (T > 10.0)
    out["vpd_win10_sum"] = np.where(warm_win, vpd, 0.0).sum(1)
    tw = np.where(win, T, np.nan)
    with np.errstate(invalid="ignore"):
        out["tstress_lt_m10"] = (tw < -10.0).sum(1)
        out["tstress_lt_m15"] = (tw < -15.0).sum(1)
        out["tstress_lt_m20"] = (tw < -20.0).sum(1)
        for j in range(len(lo)):
            out[f"tstress_pft{j}"] = ((tw < lo[j]) | (tw > hi[j])).sum(1)
    out["swdown_ann"] = SW.mean(1)
    out["lwnet_ann"] = LW.mean(1)
    out["wind_ann"] = W.mean(1)
    out["huss_mean"] = Q.mean(1)
    out["prec_hs"] = np.where(hs, P, 0.0).sum(1)
    out["cwb_hs"] = out["prec_hs"] - np.where(hs, pet, 0.0).sum(1)
    out["vpd_hs"] = np.where(hs, vpd, 0.0).sum(1) / nhs
    res = {k: np.asarray(v, dtype=np.float32) for k, v in out.items() if not k.startswith("tstress_pft")}
    res.update({k: np.asarray(v, dtype=np.int16) for k, v in out.items() if k.startswith("tstress_pft")})
    hum = dict(rh_mean=float(rh.mean()), rh_clipped_frac=float((rh >= 1.0).mean()),
               rh_warmwin_mean=float(rh[warm_win].mean()) if warm_win.any() else None)
    return res, hum


def process_chunk(args):
    gcm, scen, y0, y1 = args
    t0 = time.time()
    pat = LEGS[(gcm, scen)][0]
    lon, lat = read_grid()
    dl = daylength_hours(lat)
    win, hs = window_mask(lat), summer_mask(lat)
    prm = pft_temp_params()
    assert prm["pft_id"].to_list() == list(range(prm.height))
    lo, hi = prm["temp_low"].to_numpy(), prm["temp_high"].to_numpy()
    mms, hdrs = {}, {}
    for v, fv in FILEVAR.items():
        p = pat.format(v=fv)
        h, _ = read_lpj_header(p)  # FATAL unless size == header-implied
        mm, fy, ncell, nbands, scalar = open_clm(p)
        if ncell != NCELL or nbands != NB or not (fy <= y0 and y1 < fy + mm.shape[0]):
            raise SystemExit(f"FATAL {p}: ncell/nbands/years {ncell}/{nbands}/{fy}+{mm.shape[0]} vs {y0}-{y1}")
        hdrs[v] = dict(path=p, version=h["version"], datatype=h["datatype"], scalar=scalar, firstyear=fy,
                       nyear=int(mm.shape[0]))
        mms[v] = (mm, fy, scalar)
    rng = {v: [np.inf, -np.inf, 0] for v in FILEVAR}
    cols, hums = {}, []
    for y in range(y0, y1 + 1):
        arr = {}
        for v, (mm, fy, scalar) in mms.items():
            a = np.asarray(mm[y - fy], dtype=np.float64) * scalar
            r = rng[v]
            r[0] = min(r[0], float(np.nanmin(a)))
            r[1] = max(r[1], float(np.nanmax(a)))
            r[2] += int(np.isnan(a).sum())
            arr[v] = a
        f, hum = year_features(arr["temp"], arr["prec"], arr["humid"], arr["swdown"], arr["lwnet"], arr["wind"],
                                dl, win, hs, lo, hi)
        hums.append(dict(year=y, **hum))
        for c, x in f.items():
            cols.setdefault(c, []).append(x)
    ny = y1 - y0 + 1
    df = pl.DataFrame({"gcm": [gcm] * (ny * NCELL), "scen": [scen] * (ny * NCELL),
                       "Cell": np.tile(np.arange(NCELL, dtype=np.int32), ny),
                       "Year": np.repeat(np.arange(y0, y1 + 1, dtype=np.int32), NCELL),
                       **{c: np.concatenate(v) for c, v in cols.items()}})
    base = os.path.join(PARTS, f"cy_{gcm}_{scen}_{y0}")
    df.write_parquet(base + ".parquet")
    info = dict(gcm=gcm, scen=scen, y0=y0, y1=y1, rows=df.height, headers=hdrs,
                ranges={v: dict(min=r[0], max=r[1], nan=r[2], lo=RANGES[v][0], hi=RANGES[v][1],
                                in_range=bool(r[0] >= RANGES[v][0] and r[1] <= RANGES[v][1] and r[2] == 0))
                        for v, r in rng.items()},
                humidity=hums, seconds=round(time.time() - t0, 1))
    with open(base + ".json", "w") as fh:
        json.dump(info, fh, indent=1)
    log(f"{gcm} {scen} {y0}-{y1}: {df.height} rows, {time.time() - t0:.0f}s")
    return base


def stage_cy():
    os.makedirs(PARTS, exist_ok=True)
    jobs = []
    for (g, s), (_, ya, _, yb) in LEGS.items():
        for y0 in range(ya, yb + 1, CHUNK):
            if not os.path.exists(os.path.join(PARTS, f"cy_{g}_{s}_{y0}.json")):
                jobs.append((g, s, y0, min(y0 + CHUNK - 1, yb)))
    # ~5 GB per worker (two dozen (67420, 365) float64 temporaries) -> NPROC caps it below the cpu count
    nproc = min(len(jobs), int(os.environ.get("NPROC", os.environ.get("SLURM_CPUS_PER_TASK", "8"))))
    log(f"{len(jobs)} chunks on {nproc} processes")
    if not jobs:
        return
    from multiprocessing import get_context

    with get_context("spawn").Pool(nproc) as pool:
        for b in pool.imap_unordered(process_chunk, jobs):
            log("part done", os.path.basename(b))


def trailing20(series):
    """(N, Y) -> (N, Y) trailing 20-yr mean incl. year y; NaN for the first 19 years."""
    cs = np.cumsum(np.concatenate([np.zeros((series.shape[0], 1)), series.astype(np.float64)], axis=1), axis=1)
    out = np.full(series.shape, np.nan, dtype=np.float32)
    out[:, 19:] = (cs[:, 20:] - cs[:, :-20]) / 20.0
    return out


def read_leg(g, s):
    _, ya, _, yb = LEGS[(g, s)]
    parts = [os.path.join(PARTS, f"cy_{g}_{s}_{y0}.parquet") for y0 in range(ya, yb + 1, CHUNK)]
    d = pl.concat([pl.read_parquet(p) for p in parts]).sort(["Cell", "Year"])
    assert d.height == NCELL * (yb - ya + 1) and d.select(KEY).n_unique() == d.height, (g, s)
    return d


def to_mat(d, c):
    return d[c].to_numpy().reshape(NCELL, d["Year"].n_unique())


def stage_assemble():
    t0 = time.time()
    os.makedirs(CY_DIR, exist_ok=True)
    anom_cols = [c for c in ANNUAL_COLS if c not in ANOM_SKIP]
    for g, base_scen, followers in (("GFDL-ESM4", "historical", SSPS), ("GSWP3-W5E5", "obsclim", ())):
        H = read_leg(g, base_scen)
        hmat = {c: to_mat(H, c) for c in TR20_SRC}
        b = (H.filter(pl.col("Year").is_between(1985, 2014)).group_by("Cell")
             .agg([pl.col(c).cast(pl.Float64).mean().alias(f"_b_{c}") for c in anom_cols]))
        assert b.height == NCELL
        for s in (base_scen, *followers):
            d = H if s == base_scen else read_leg(g, s)
            new = []
            for c in TR20_SRC:
                if s == base_scen:
                    tr = trailing20(hmat[c])
                else:
                    tr = trailing20(np.concatenate([hmat[c], to_mat(d, c)], axis=1))[:, hmat[c].shape[1]:]
                new.append(pl.Series(f"{c}_tr20", tr.ravel()))
            d = d.with_columns(new).join(b, on="Cell", how="left", validate="m:1")
            d = d.with_columns([(pl.col(c).cast(pl.Float64) - pl.col(f"_b_{c}")).cast(pl.Float32).alias(f"anom_{c}")
                                for c in anom_cols]).drop([f"_b_{c}" for c in anom_cols])
            d = d.with_columns([pl.col(k).alias(v) for k, v in EFF.items()])
            y_store = LEGS[(g, s)][2]
            d = d.filter(pl.col("Year") >= y_store).sort(["Cell", "Year"])
            tr_nan = sum(int(d[f"{c}_tr20"].is_nan().sum()) for c in TR20_SRC)
            assert tr_nan == 0, (g, s, tr_nan)
            out = os.path.join(CY_DIR, f"{g}_{s}.parquet")
            d.write_parquet(out, compression="zstd")
            log(f"{out}: rows={d.height} cols={d.width} years {d['Year'].min()}-{d['Year'].max()}")
    lon, lat = read_grid()
    soil = np.fromfile(SOIL_RAW, dtype=np.uint8)
    assert soil.size == NCELL
    st = pl.DataFrame({"Cell": np.arange(NCELL, dtype=np.int32), "lon": lon, "lat": lat,
                       "soil_code": soil.astype(np.int16), "rock": soil == 13,
                       "area_km2_approx": (111.194926 * 0.5) ** 2 * np.cos(np.deg2rad(lat))})
    st.write_parquet(os.path.join(OUT, "cell_static.parquet"))
    log(f"assemble done ({time.time() - t0:.0f}s)")


def scan_cy(gcm: str | None = None, scen: str | None = None) -> pl.LazyFrame:
    pat = f"{gcm or '*'}_{scen or '*'}.parquet"
    return pl.scan_parquet(os.path.join(CY_DIR, pat))


# The Oct-2026 builds (reanalysis members) read Billing's LIVE par file, which since 2026-10 sets MORT_TEMP_FACTOR 4.0
# (not 5.0) and the tropical tree's temp_stressed.low 14.0 (not 12.5) [VERIFIED 2026-10-08: par/pft_lpjmlfit.js:117,
# 200; the printed mort_temp implies exactly 0.8 x the day count]. tstress_pft0 here uses 12.5, so type 0 is reported
# but not gated for that build family. Parameters a run read are inferable only from its output: the par file is
# read at run start from a directory that is edited in place.
PARAM_OVERRIDE = {"GSWP3-W5E5": dict(mort_temp_factor=4.0, ungated_types=(0,))}


def mort_temp_check(path, gcm, scen, prm):
    """Printed per-tree mort_temp vs min(1, factor * tstress_pft<Type> / ndayyear), dev cells, all but the first
    output year (its mort_* can be uninitialised in a restarted run)."""
    t = (pl.scan_parquet(path).filter(pl.col("Type") <= 6)
         .select("Cell", pl.col("Year").cast(pl.Int32), pl.col("Type").cast(pl.Int32), "mort_temp").collect())
    t = t.filter(pl.col("Year") > t["Year"].min())
    years = t["Year"].unique().to_list()
    ts = (scan_cy(gcm, scen).filter(pl.col("Year").is_in(years))
          .select(["Cell", "Year"] + [f"tstress_pft{k}" for k in prm["pft_id"]]).collect()
          .unpivot(index=["Cell", "Year"], variable_name="v", value_name="n")
          .with_columns(pl.col("v").str.replace("tstress_pft", "").cast(pl.Int32).alias("Type")).drop("v"))
    j = t.join(ts, on=["Cell", "Year", "Type"], how="left")
    miss = int(j["n"].null_count())
    ov = PARAM_OVERRIDE.get(gcm, {})
    p2 = prm.with_columns(pl.lit(ov["mort_temp_factor"]).alias("mort_temp_factor")) if ov else prm
    j = j.drop_nulls("n").join(p2.select(pl.col("pft_id").alias("Type"), "mort_temp_factor", "ndayyear"), on="Type")
    ungated = j["Type"].is_in(list(ov.get("ungated_types", ()))).to_numpy()
    pred = np.minimum(1.0, j["mort_temp_factor"].to_numpy() * j["n"].to_numpy() / j["ndayyear"].to_numpy())
    got = j["mort_temp"].to_numpy().astype(np.float64)
    err = np.abs(pred - got)
    ok = err <= 1e-5 * np.maximum(1.0, np.abs(got)) + 1e-6
    by = {}
    for k in sorted(set(j["Type"].to_list())):
        m = j["Type"].to_numpy() == k
        by[int(k)] = dict(n=int(m.sum()), frac_match=float(ok[m].mean()), n_nonzero=int((got[m] > 0).sum()))
    return dict(table=os.path.basename(path), rows=int(len(got)), clim_missing=miss,
                frac_match=float(ok[~ungated].mean()), ungated_types=list(ov.get("ungated_types", ())),
                param_override=ov,
                max_abs_err=float(err.max()) if len(err) else 0.0, n_nonzero_printed=int((got > 0).sum()), by_type=by)


def stage_gates():
    t0 = time.time()
    gates = []
    infos = [json.load(open(os.path.join(PARTS, f))) for f in sorted(os.listdir(PARTS)) if f.endswith(".json")]
    bad = [(i["gcm"], i["scen"], i["y0"], v, r) for i in infos for v, r in i["ranges"].items() if not r["in_range"]]
    gates.append(dict(name="forcing_headers_and_ranges", pass_=not bad,
                      detail=f"{len(infos)} chunks; out-of-range/NaN: {bad[:10]}"))
    vers = {(v, h["version"], h["datatype"], round(h["scalar"], 6)) for i in infos for v, h in i["headers"].items()}
    gates.append(dict(name="forcing_header_kinds", pass_=True, detail=str(sorted(vers))))
    # humidity plausibility, per leg (the C's own conversion; ADR 0314 records why there is no unit defect)
    hum = {}
    for i in infos:
        hum.setdefault(f"{i['gcm']}_{i['scen']}", []).extend(i["humidity"])
    hum_sum = {k: dict(rh_mean=float(np.mean([h["rh_mean"] for h in v])),
                       rh_clipped_frac=float(np.mean([h["rh_clipped_frac"] for h in v])),
                       rh_warmwin_mean=float(np.mean([h["rh_warmwin_mean"] for h in v])))
               for k, v in hum.items()}
    gates.append(dict(name="humidity_plausible", pass_=all(0.3 <= h["rh_mean"] <= 0.9 for h in hum_sum.values()),
                      detail=json.dumps(hum_sum)))
    # mort_temp end-to-end
    prm = pft_temp_params()
    res = []
    for f in sorted(os.listdir(IND_DEV)):
        if not f.endswith(".parquet"):
            continue
        g, s = f.split("_")[0], f.split("_")[1]
        if (g, s) not in LEGS:
            continue
        res.append(mort_temp_check(os.path.join(IND_DEV, f), g, s, prm))
        r = res[-1]
        log(f"mort_temp {r['table']}: rows {r['rows']} match {r['frac_match']:.6f} max err {r['max_abs_err']:.2e} "
            f"nonzero {r['n_nonzero_printed']} miss {r['clim_missing']}")
    if res:
        worst = min(res, key=lambda r: r["frac_match"])
        gates.append(dict(name="mort_temp_reproduced_all_dev_tables",
                          pass_=all(r["frac_match"] >= 0.98 and r["clim_missing"] == 0 for r in res),
                          detail=f"{len(res)} tables, {sum(r['rows'] for r in res)} tree rows; min frac_match "
                                 f"{worst['frac_match']:.6f} ({worst['table']}); nonzero printed "
                                 f"{sum(r['n_nonzero_printed'] for r in res)}; clim misses "
                                 f"{sum(r['clim_missing'] for r in res)}"))
    allpass = all(gx["pass_"] for gx in gates)
    with open(os.path.join(OUT, "_gates.json"), "w") as fh:
        json.dump(dict(all_pass=allpass, seconds=round(time.time() - t0, 1),
                       gates=[{"name": gx["name"], "pass": gx["pass_"], "detail": gx["detail"]} for gx in gates],
                       mort_temp=res, humidity=hum_sum), fh, indent=1)
    for gx in gates:
        log(("PASS " if gx["pass_"] else "FAIL ") + gx["name"] + " :: " + gx["detail"][:800])
    log(f"ALL PASS: {allpass}")


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    os.makedirs(OUT, exist_ok=True)
    for s in (["cy", "assemble", "gates"] if stage == "all" else stage.split(",")):
        log(f"=== stage {s}")
        {"cy": stage_cy, "assemble": stage_assemble, "gates": stage_gates}[s]()
    log("=== DONE")
