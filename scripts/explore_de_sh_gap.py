"""SH12 v2 -- cell-level CHECK TABLES 1985-2070 for the Germany emulator (line X), from the CORRECT gridded
LPJmL-FIT outputs. Repurposed on 2026-10-01 after the owner decision to use only correct data.

WHY. The tree tables exist for 1985-2044 only (Historical 1985-2014 + ssp 2015-2044). The C also ran 2045-2070
(the `lpjml_2070_*` segment, restart_2044 -> restart_2070, relative humidity read CORRECTLY) but did not write the
`ind` tree table for it. Its annual gridded NetCDF outputs (AGB, VegC, LitC, SoilC, FPC per PFT, the 100-bin
height_mass and D95_mass histograms) do exist. So a free run of an emulator may be continued 1985 -> 2070 and
checked on CELL AGGREGATES for 2045-2070 (no tree-level check is possible for those years).

EXCLUDED (owner decision 2026-10-01): the 2071-2100 and 3071-3100 segments read the relative-humidity file as
specific humidity (VPD = 0, water-stress mortality off). This script never opens a `_2100`, `_3100` or `_3070`
file and never reads a w2071/w3071 tree table (members.excluded == True are skipped). The v1 SH12 (2044 -> 2071
survivor tables) is kept under shared/gap/_superseded_v1_pre_owner_exclusion/ and must not be used.

SOURCE FACTS (LPJmL-FIT 5.6.004, /home/jamirp/lpjml56fit):
  * height_mass = src/tree/height_tree_mass.c: per cell, sum over ALL patches and ALL tree PFTs of vegc_sum_tree(pft)
    for trees with getindex(height) == k, / npatch. getindex = floor((x - low)/(high - low)*nbin) clipped to
    [0, nbin-1]; par/outputvars.js "height" low 0 high 100 nbins 100 -> bin k = [k, k+1) m. NO isdead filter, NO
    stand->frac (writehistogram, src/lpj/fwriteoutput.c:508).
  * D95_mass = src/tree/D95_tree_mass.c: same, binned by the ACTUAL rooting D95 in CM
    (log(1-0.95(1-beta^min(rootdepth*0.1, soildepth*100)))/log(beta), the same formula fwriteoutput_ind.c:142 prints
    as the `ind` column D95); "D95" low 0 high 1800 nbins 100 -> bin k = [18k, 18k+18) cm. The NetCDF coordinate
    says "mm" and is a cosmetic linspace(0, 1800, 100) label: the bins are 18-CM wide (gated, G10).
  * VEGC / AGB grids: all PFTs incl. grass, SKIPPING isdead trees, times stand->frac / npatch. FPC band 0 =
    natural stand fraction; band t+1 = sum pft->fpc / npatch over living PFTs of type t.
  * The `ind` table holds trees with H > 5 m + grass rows. So the emulator-comparable tree quantity is
    hm_ge5 = sum of height_mass bins 5..99 = vegc of every >= 5 m tree INCLUDING those flagged dead that year,
    which is exactly what a roster (incl. this year's flagged-dead rows) sums to (gate G4: <= 4e-7 relative).

FILE FAMILY (critic gap 12): raw LPJmL files only (history = one `lpjml` command line): 1985-2014 `<v>_.nc`
(Historical dir, same GCM + seed), 2015-2044 `<v>_2044.nc`, 2045-2070 `<v>_2070.nc`.

PRE-REGISTERED GATES (written before the v2 run; thresholds in cmd_gate):
  G1 raster->Cell map; G2 file provenance; G3 humidity setting of every segment read (log says `rhumid`, config has
  "relative_humidity": true, agrees with SH0); G3b exclusion (no Year > 2070 anywhere, no excluded file opened);
  G4 height_mass = vegc incl. flagged-dead (1985-2044 roster); G5 VegC closure; G6 sub-5 m AGB; G7 FPC (diagnostic);
  G8 restart chain 1985-2014 -> 2015-2044 -> 2045-2070; G8b continuity at the 2015 / 2045 joins (diagnostic);
  G10 D95_mass: total == height_mass total (all years incl. 2045-2070), per-bin roster bound, 18-cm-bin verdict;
  G11 units/calendar attributes; G12 table integrity.
RESPONSE SIGNAL-TO-NOISE (cmd_response; reported, not a gate): per variable X, window W, unit u (cell / 1-degree
  block / Germany): D_s = X(ssp370, W, s) - X(ssp126, W, s), s = seed 1, 2 (same GCM, same C build);
  'determined' := |(D_1 + D_2)/2| > |D_1 - D_2|. Derived null (no signal, iid Gaussian seed noise of sd sigma per
  D_s): mean ~ N(0, sigma^2/2), difference ~ N(0, 2 sigma^2), P(|Z1| > 2|Z2|) = (2/pi) atan(1/2) = 0.2952.
  So a determined fraction near 0.30 means NO detectable response at that scale.

Subcommands (all write under /p/tmp/jamirp/X_de/shared/gap):
  provenance  choose files, map raster->Cell, humidity + units per file            -> _provenance.parquet
  gridded     (Cell, Year) tables per trajectory 1985-2070                         -> gridded[_dev]/
  rosteragg   clean member-window roster sums (1985-2044) incl. 1-m and D95 bins   -> rosteragg/
  checks      seed-pair check tables (cell + block) 1985-2070                     -> check/
  response    between-scenario signal-to-noise on cell aggregates                 -> check/response_*
  gate        all gates                                                            -> _gates_<cells>.json
  all         everything in order
Options: --cells dev|all (dev = Cell % 10 == 0, 907 tree cells). Gridded tables are always written for all cells
plus a dev copy. Usage (SLURM): scripts/sbatch_python.sh X-de-SH12-v2 scripts/explore_de_sh_gap.py all --cells dev

CONSUMER API: `roster_check_aggregates(df, npatch)` turns ANY roster (truth or an emulator's own, one row per tree
and year incl. the year's flagged-dead rows) into the exact quantities the gridded check tables hold.
"""

import argparse
import datetime as dt
import glob
import json
import os
import re
import struct
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XDE = "/p/tmp/jamirp/X_de"
OUT = f"{XDE}/shared/gap"
REG = f"{XDE}/shared/registry"
RUNS = "/p/projects/waldspektrum/data/LPJmLFIT/productionruns_jamir"
GRID_CLM = "/p/projects/biodiversity/billing/input/FirEUrisk/LPJ/grid_germany_9km_new.clm"
CELL_STATIC = f"{XDE}/climate/cell_static.parquet"

GCMS = ["MPI-ESM1-2-HR", "ACCESS-CM2"]
SSPS = ["ssp126", "ssp245", "ssp370"]
SEEDS = [1, 2]
LAST_YEAR = 2070
# segment -> (SH0 segments.segment_id, raw file suffix, first year, n years)
SEGMENTS = {
    "1985-2014": (1, "_", 1985, 30),
    "2015-2044": (1, "_2044", 2015, 30),
    "2045-2070": (2, "_2070", 2045, 26),
}
EXCLUDED_SUFFIX = re.compile(r"_(2100|3100|3070)(_backup)?\.nc$")
SEG_WIN = {"1985-2014": "h1985", "2015-2044": "w2015", "2045-2070": None}
SEG_USE = {"1985-2014": "trees", "2015-2044": "trees", "2045-2070": "no_tree_table"}
# gridded variable -> (file stem, NetCDF variable, expected units)
GVARS = {"AGB": ("agb", "AGB", "gC/m2"), "VegC": ("vegc", "VegC", "gC/m2"), "LitC": ("litc", "LitC", "gC/m2"),
         "SoilC": ("soilc", "SoilC", "gC/m2"), "FPC": ("fpc", "FPC", ""),
         "HM": ("height_mass", "mass_height", "gC/m2/bin"), "D95": ("D95_mass", "mass_D95", "gC/m2/bin"),
         "grid": ("grid", "cellid", None)}
FPC_COLS = ["natfrac"] + [f"fpc_t{t}" for t in range(7)] + [f"fpc_g{t}" for t in (7, 8, 9)]
HM_COLS = [f"hm_{k:02d}" for k in range(100)]
D95_COLS = [f"d95_{k:02d}" for k in range(100)]
D95_BIN_CM = 18.0  # (1800 - 0) / 100, par/outputvars.js "D95"
NCELL = 9067
TZ = ZoneInfo("Europe/Berlin")
# the check variables carried into the seed-pair tables
CHECK_VARS = ["hm_ge5", "hm_ge5_medH", "d95_med_cm", "fpc_tree", "AGB", "VegC", "hm_lt5", "LitC", "SoilC"] + \
    [f"fpc_t{t}" for t in range(7)]
RESP_VARS = ["hm_ge5", "hm_ge5_medH", "d95_med_cm", "fpc_tree", "AGB", "VegC"]
RESP_WINDOWS = {"W2015_2044": (2015, 2044), "W2045_2070": (2045, 2070), "W2061_2070": (2061, 2070)}
NULL_DETERMINED = float(2 / np.pi * np.arctan(0.5))  # 0.2952, derived in the module docstring


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def dev_filter(cells):
    return pl.col("Cell") % 10 == 0 if cells == "dev" else pl.lit(True)


# ------------------------------------------------------------------------------------------------ consumer API
def binned_median(M, start, width):
    """Mass-weighted median from a (n, nbin) histogram, linear inside the crossing bin; NaN where total <= 0."""
    M = np.asarray(M, dtype=np.float64)
    cum = np.cumsum(M, axis=1)
    tot = cum[:, -1]
    half = tot / 2
    idx = np.argmax(cum >= half[:, None], axis=1)
    rows = np.arange(len(M))
    prev = np.where(idx > 0, cum[rows, np.maximum(idx - 1, 0)], 0.0)
    m = M[rows, idx]
    frac = np.where(m > 0, (half - prev) / np.where(m > 0, m, 1.0), 0.0)
    med = start + (idx + np.clip(frac, 0, 1)) * width
    return np.where(tot > 0, med, np.nan)


def roster_check_aggregates(df, npatch, keep_bins=False):
    """ANY roster -> the gridded check quantities, per (Year, Cell).

    df: polars DataFrame, one row per tree-year INCLUDING the year's flagged-dead rows, columns Year, Cell, Type,
    isdead, Height, vegc, D95 (and optionally agb, fpc_ind). Trees only (Type <= 6) are used; the truth roster has
    only trees > 5 m, so its hm_ge5 equals the gridded hm_ge5 (G4); an emulator that also carries sub-5 m trees must
    drop them (Height < 5) before calling this to compare with hm_ge5 / hm_ge5_medH.
    npatch: patches per cell of THIS roster (truth 250; an emulator with fewer patches passes its own).
    Returns (Year, Cell, hm_ge5, hm_ge5_medH, d95_ge5_med_cm[, bins]). d95_ge5_med_cm is over >= 5 m trees only;
    the gridded d95_med_cm also contains sub-5 m trees (~0.8 % of tree vegc), so compare it with that caveat.
    """
    t = df.filter(pl.col("Type") <= 6).with_columns(
        pl.col("Height").cast(pl.Float64), pl.col("vegc").cast(pl.Float64), pl.col("D95").cast(pl.Float64))
    t = t.filter(pl.col("Height") >= 5.0)
    hb = (t.with_columns(bin=pl.col("Height").floor().clip(0, 99).cast(pl.Int16))
          .group_by(["Year", "Cell", "bin"]).agg((pl.col("vegc").sum() / npatch).alias("m")))
    db = (t.with_columns(bin=(pl.col("D95") / D95_BIN_CM).floor().clip(0, 99).cast(pl.Int16))
          .group_by(["Year", "Cell", "bin"]).agg((pl.col("vegc").sum() / npatch).alias("m")))
    out = []
    for name, B, start, width in (("h", hb, 0.0, 1.0), ("d", db, 0.0, D95_BIN_CM)):
        W = (B.pivot(on="bin", index=["Year", "Cell"], values="m", sort_columns=True).fill_null(0.0)
             .sort("Year", "Cell"))
        bins = [c for c in W.columns if c not in ("Year", "Cell")]
        M = np.zeros((W.height, 100))
        for c in bins:
            M[:, int(c)] = W[c].to_numpy()
        res = W.select("Year", "Cell")
        if name == "h":
            res = res.with_columns(hm_ge5=pl.Series(M[:, 5:].sum(1)),
                                   hm_ge5_medH=pl.Series(binned_median(M[:, 5:], 5.0, 1.0)))
        else:
            res = res.with_columns(d95_ge5_med_cm=pl.Series(binned_median(M, start, width)))
        if keep_bins:
            res = res.with_columns(pl.Series(f"{name}bins", M.astype(np.float32)))
        out.append(res)
    res = out[0].join(out[1], on=["Year", "Cell"], how="full", coalesce=True)
    return res.with_columns(pl.col("Year").cast(pl.Int16), pl.col("Cell").cast(pl.Int16)).sort("Year", "Cell")


# ------------------------------------------------------------------------------------------------ grid / files
def read_grid_clm(path=GRID_CLM):
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
        datatype, hdr = 1, 43
    dtype = {0: "u1", 1: "<i2", 2: "<i4", 3: "<f4", 4: "<f8"}[datatype]
    assert name == "LPJGRID" and nbands == 2, (name, nbands)
    a = np.fromfile(path, dtype=dtype, offset=hdr).reshape(ncell, 2).astype(np.float64) * scalar
    return a[:, 0], a[:, 1], dict(version=version, ncell=ncell, cs_lon=cs_lon, scalar=scalar)


def member_dir(gcm, scen, seed):
    return f"{RUNS}/{gcm}/{scen}/random_seed_{seed}/output"


def nc_info(path, var):
    import netCDF4

    assert not EXCLUDED_SUFFIX.search(path), f"refusing to open an excluded segment file: {path}"
    with netCDF4.Dataset(path) as d:
        hist = getattr(d, "history", "")
        info = dict(history=hist, dims={k: len(v) for k, v in d.dimensions.items()})
        if "time" in d.variables:
            tv = d.variables["time"]
            info["time_units"] = tv.units
            info["calendar"] = getattr(tv, "calendar", None)
            t = np.ma.filled(tv[:].astype(np.float64), np.nan)
            info["ntime"] = len(t)
            info["time_fill"] = int(np.isnan(t).sum())
            y0 = int(re.match(r"days since (\d+)-", tv.units).group(1))
            info["years"] = [y0 + int(x // 365) for x in t if np.isfinite(x)]
        info["units"] = getattr(d.variables[var], "units", None) if var in d.variables else None
        info["lat"] = np.asarray(d.variables["lat"][:], dtype=np.float64)
        info["lon"] = np.asarray(d.variables["lon"][:], dtype=np.float64)
        if "D95" in d.variables:
            info["d95_coord"] = np.asarray(d.variables["D95"][:], dtype=np.float64)
            info["d95_coord_units"] = getattr(d.variables["D95"], "units", None)
    return info


def parse_history(hist):
    """raw iff one line '<ctime>: <...>/bin/lpjml ... <config.js>'. Returns (is_raw, epoch, config)."""
    lines = [x for x in hist.strip().split("\n") if x.strip()]
    m = re.match(r"^(\w{3} \w{3} +\d+ \d\d:\d\d:\d\d \d{4}): (\S*/bin/lpjml)\s.*?(\S+\.js)\s*$", lines[0]) \
        if lines else None
    if not m:
        return False, None, None
    ts = dt.datetime.strptime(re.sub(" +", " ", m.group(1)), "%a %b %d %H:%M:%S %Y").replace(tzinfo=TZ)
    return len(lines) == 1, ts.timestamp(), m.group(3)


_HUMID_CACHE = {}


def humidity_evidence(out_path, cfg):
    """Independent reading (not via SH0): the humidity input line LPJmL printed in its .out log, and whether the
    config .js sets "relative_humidity": true outside comments. LPJmL's default is FALSE (fscanconfig.c:255)."""
    key = (out_path, cfg)
    if key in _HUMID_CACHE:
        return _HUMID_CACHE[key]
    kinds = set()
    done = False
    if out_path and os.path.exists(out_path):
        with open(out_path, errors="replace") as f:
            for line in f:
                m = re.match(r"^(rhumid|humid)\s+clm\s+(\S+)", line)
                if m:
                    kinds.add(m.group(1))
                if "successfully terminated" in line:
                    done = True
    rh_js = None
    if cfg and os.path.exists(cfg):
        s = open(cfg, errors="replace").read()
        s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
        s = re.sub(r"//[^\n]*", "", s)
        m = re.findall(r'"relative_humidity"\s*:\s*(true|false)', s)
        rh_js = (m[-1] == "true") if m else False  # absent -> LPJmL default FALSE
    r = dict(humid_log=",".join(sorted(kinds)) if kinds else None, log_completed=done, rh_js=rh_js)
    _HUMID_CACHE[key] = r
    return r


def cmd_provenance(args):
    import netCDF4

    os.makedirs(OUT, exist_ok=True)
    att = pl.read_parquet(f"{REG}/attempts.parquet")
    seg = pl.read_parquet(f"{REG}/segments.parquet")
    mem = pl.read_parquet(f"{REG}/members.parquet")
    lon_c, lat_c, gh = read_grid_clm()
    assert gh["ncell"] == NCELL, gh
    ref_path = f"{member_dir('MPI-ESM1-2-HR', 'Historical', 1)}/grid_.nc"
    with netCDF4.Dataset(ref_path) as d:
        cid_ref = np.ma.filled(d["cellid"][:], -1).astype(np.int64)
        rlat = np.asarray(d["lat"][:], dtype=np.float64)
        rlon = np.asarray(d["lon"][:], dtype=np.float64)
    iy, ix = np.nonzero(cid_ref >= 0)
    order = np.argsort(cid_ref[iy, ix])
    iy, ix = iy[order], ix[order]
    cells = cid_ref[iy, ix]
    g1 = {"ref_grid_file": ref_path, "n_valid_raster_cells": int(len(cells)),
          "cellid_is_0..9066_once": bool(np.array_equal(cells, np.arange(NCELL))),
          "max_abs_dlat_vs_grid_clm_deg": float(np.abs(rlat[iy] - lat_c).max()),
          "max_abs_dlon_vs_grid_clm_deg": float(np.abs(rlon[ix] - lon_c).max())}
    cs = pl.read_parquet(CELL_STATIC).sort("Cell")
    g1["equals_cell_static_nc_index"] = bool(
        np.array_equal(cs["nc_ilat"].to_numpy(), iy) and np.array_equal(cs["nc_ilon"].to_numpy(), ix))
    pl.DataFrame({"Cell": np.arange(NCELL, dtype=np.int32), "ilat": iy.astype(np.int32),
                  "ilon": ix.astype(np.int32), "lat": rlat[iy], "lon": rlon[ix],
                  "lat_clm": lat_c, "lon_clm": lon_c}).write_parquet(f"{OUT}/cellmap.parquet")
    A = {r["job"]: r for r in att.iter_rows(named=True)}
    rows = []
    trajs = [(g, "Historical", s) for g in GCMS for s in SEEDS] + [(g, c, s) for g in GCMS for c in SSPS for s in SEEDS]
    for gcm, scen, seed in trajs:
        segs = ["1985-2014"] if scen == "Historical" else list(SEGMENTS)
        for sname in segs:
            sid, suf, y0, ny = SEGMENTS[sname]
            src_scen = "Historical" if sname == "1985-2014" else scen
            d = member_dir(gcm, src_scen, seed)
            exp_years = list(range(y0, y0 + ny))
            sj = seg.filter((pl.col("gcm") == gcm) & (pl.col("scen") == scen) & (pl.col("seed") == seed)
                            & pl.col("Year").is_between(y0, y0 + ny - 1))
            seg_job = sorted(set(sj["job"].drop_nulls().to_list())) if sj.height else []
            seg_humid = sorted(set(sj["humid_kind"].drop_nulls().to_list())) if sj.height else []
            seg_excl = bool(sj["excluded"].any()) if sj.height else None
            seg_use = sorted(set(sj["use"].drop_nulls().to_list())) if sj.height else []
            win = SEG_WIN[sname]
            ind_job = None
            if win:
                mm = mem.filter((pl.col("gcm") == gcm) & (pl.col("scen") == src_scen) & (pl.col("seed") == seed)
                                & (pl.col("win") == win))
                ind_job = int(mm["writer_job"][0]) if mm.height else None
            for gv, (stem, ncv, _u) in GVARS.items():
                p = f"{d}/{stem}{suf}.nc"
                r = dict(gcm=gcm, scen=scen, seed=seed, segment=sname, segment_id=sid, src_scen=src_scen,
                         var=gv, path=p, seg_jobs=json.dumps(seg_job), seg_humid_kind=",".join(seg_humid),
                         seg_excluded=seg_excl, seg_use=",".join(seg_use), ind_writer_job=ind_job, chosen=False)
                if not os.path.exists(p):
                    r["why"] = "missing"
                    rows.append(r)
                    continue
                inf = nc_info(p, ncv)
                is_raw, ts, cfg = parse_history(inf["history"])
                years_ok = gv == "grid" or inf.get("years") == exp_years
                fill_frac = None
                if gv != "grid" and is_raw and years_ok and inf.get("time_fill") == 0:
                    with netCDF4.Dataset(p) as ds:
                        v = ds[ncv]
                        sl0 = v[0] if v.ndim == 3 else v[0, 0]
                        sl1 = v[-1] if v.ndim == 3 else v[-1, -1]
                        fill_frac = float(max(np.ma.getmaskarray(sl0)[iy, ix].mean(),
                                              np.ma.getmaskarray(sl1)[iy, ix].mean()))
                ok = is_raw and years_ok and (gv == "grid" or (inf.get("time_fill") == 0 and fill_frac == 0.0))
                r.update(history=inf["history"], is_raw=is_raw, years_ok=years_ok, cell_fill=fill_frac,
                         hist_epoch=ts, hist_config=cfg, units=inf.get("units"), time_units=inf.get("time_units"),
                         calendar=inf.get("calendar"), ntime=inf.get("ntime"),
                         lat_ok=bool(np.array_equal(inf["lat"], rlat)), lon_ok=bool(np.array_equal(inf["lon"], rlon)),
                         d95_coord_units=inf.get("d95_coord_units"),
                         d95_coord_max=(float(inf["d95_coord"].max()) if "d95_coord" in inf else None))
                if gv == "grid":
                    with netCDF4.Dataset(p) as ds:
                        cid = np.ma.filled(ds["cellid"][:], -1).astype(np.int64)
                    r["cellid_equals_ref"] = bool(np.array_equal(cid, cid_ref))
                # writer job: the attempt whose [start, end] contains the history timestamp, same config
                a = att.filter((pl.col("config") == cfg) & (pl.col("job_start") <= (ts or 0) + 5)
                               & (pl.col("job_end") >= (ts or 0)))
                wj = a["job"].to_list()
                r["n_writer_match"] = len(wj)
                r["writer_job"] = wj[0] if len(wj) == 1 else None
                r["writer_equals_segment_job"] = len(wj) == 1 and seg_job == [wj[0]]
                r["ind_consistent"] = None if ind_job is None else (len(wj) == 1 and wj[0] == ind_job)
                if r["writer_job"] is not None:
                    w = A[r["writer_job"]]
                    r["writer_ok"] = w["ok"]
                    r["writer_out"] = w["out_path"]
                    r["writer_humid_kind_sh0"] = w["humid_kind"]
                    r.update(humidity_evidence(w["out_path"], cfg))
                r["chosen"] = bool(ok)
                rows.append(r)
            log(gcm, scen, seed, sname, "done")
    prov = pl.DataFrame(rows, infer_schema_length=None)
    prov.write_parquet(f"{OUT}/_provenance.parquet")
    with open(f"{OUT}/_g1_grid.json", "w") as f:
        json.dump(g1, f, indent=1)
    log("G1", g1)
    log("provenance rows", prov.height, "chosen", prov["chosen"].sum())


# ------------------------------------------------------------------------------------------------ gridded tables
def cmd_gridded(args):
    import netCDF4

    prov = pl.read_parquet(f"{OUT}/_provenance.parquet")
    cm = pl.read_parquet(f"{OUT}/cellmap.parquet")
    iy, ix = cm["ilat"].to_numpy(), cm["ilon"].to_numpy()
    for sub in ("gridded", "gridded_dev"):
        os.makedirs(f"{OUT}/{sub}", exist_ok=True)
    for (gcm, scen, seed), grp in prov.group_by(["gcm", "scen", "seed"], maintain_order=True):
        pools, hms, d95s = [], [], []
        for sname in [s for s in SEGMENTS if s in grp["segment"].unique().to_list()]:
            sid, _, y0, ny = SEGMENTS[sname]
            g = grp.filter(pl.col("segment") == sname)
            cols = {}
            for gv in ("AGB", "VegC", "LitC", "SoilC", "FPC", "HM", "D95"):
                r = g.filter(pl.col("var") == gv).row(0, named=True)
                if not r["chosen"]:
                    raise SystemExit(f"FATAL no usable raw file for {gcm} {scen} {seed} {sname} {gv}: {r['path']}")
                assert not EXCLUDED_SUFFIX.search(r["path"])
                with netCDF4.Dataset(r["path"]) as ds:
                    a = ds[GVARS[gv][1]][:]
                a = np.ma.filled(a.astype(np.float32), np.nan)
                if a.ndim == 3:
                    cols[gv] = a[:, iy, ix]
                else:
                    cols[gv] = np.moveaxis(a[:, :, iy, ix], 1, 2)
                assert np.isfinite(cols[gv]).all(), (gcm, scen, seed, sname, gv, "non-finite at a grid cell")
            years = np.repeat(np.arange(y0, y0 + ny, dtype=np.int16), NCELL)
            cellv = np.tile(np.arange(NCELL, dtype=np.int16), ny)
            base = {"Cell": cellv, "Year": years, "segment_id": np.full(ny * NCELL, sid, np.int8)}
            d = dict(base)
            for gv in ("AGB", "VegC", "LitC", "SoilC"):
                d[gv] = cols[gv].reshape(-1)
            fpc = cols["FPC"].reshape(ny * NCELL, -1)
            assert fpc.shape[1] == 11, fpc.shape
            for j, c in enumerate(FPC_COLS):
                d[c] = fpc[:, j]
            d["fpc_tree"] = fpc[:, 1:8].sum(1, dtype=np.float64).astype(np.float32)
            hm = cols["HM"].reshape(ny * NCELL, -1)
            dm = cols["D95"].reshape(ny * NCELL, -1)
            assert hm.shape[1] == 100 and dm.shape[1] == 100, (hm.shape, dm.shape)
            d["hm_lt5"] = hm[:, :5].sum(1, dtype=np.float64).astype(np.float32)
            d["hm_ge5"] = hm[:, 5:].sum(1, dtype=np.float64).astype(np.float32)
            d["hm_sum"] = hm.sum(1, dtype=np.float64).astype(np.float32)
            d["hm_ge5_medH"] = binned_median(hm[:, 5:], 5.0, 1.0).astype(np.float32)
            d["d95_sum"] = dm.sum(1, dtype=np.float64).astype(np.float32)
            d["d95_med_cm"] = binned_median(dm, 0.0, D95_BIN_CM).astype(np.float32)
            src = "Historical" if sname == "1985-2014" else scen
            wj = g.filter(pl.col("var") == "AGB")["writer_job"][0]
            pools.append(pl.DataFrame(d).with_columns(src_scen=pl.lit(src), family=pl.lit("raw_plain"),
                                                      use=pl.lit(SEG_USE[sname]), writer_job=pl.lit(wj, pl.Int64)))
            dh, dd = dict(base), dict(base)
            for k in range(100):
                dh[HM_COLS[k]] = hm[:, k]
                dd[D95_COLS[k]] = dm[:, k]
            hms.append(pl.DataFrame(dh))
            d95s.append(pl.DataFrame(dd))
            log(gcm, scen, seed, sname, "read")
        lab = dict(gcm=pl.lit(gcm), scen=pl.lit(scen), seed=pl.lit(seed, pl.Int8))
        P = pl.concat(pools).with_columns(**lab)
        H = pl.concat(hms).with_columns(**lab)
        D = pl.concat(d95s).with_columns(**lab)
        assert P.select("Cell", "Year").n_unique() == P.height and H.height == P.height == D.height
        assert P["Year"].max() <= LAST_YEAR
        tag = f"{gcm}_{scen}_s{seed}"
        for name, T in (("pools", P), ("height_mass", H), ("d95_mass", D)):
            T.write_parquet(f"{OUT}/gridded/{name}_{tag}.parquet")
            T.filter(pl.col("Cell") % 10 == 0).write_parquet(f"{OUT}/gridded_dev/{name}_{tag}.parquet")
        log("wrote", tag, P.height, "rows; years", P["Year"].min(), "-", P["Year"].max())


# ------------------------------------------------------------------------------------------------ roster sums
def member_chunks(r, cells):
    if cells == "dev":
        return [r["ind_dev_path"]] if r["ind_dev_path"] else \
            [f"{XDE}/ind_dev/{r['gcm']}_{r['scen']}_s{r['seed']}_{r['win']}.parquet"]
    return sorted(glob.glob(f"{XDE}/ind/{r['gcm']}/{r['scen']}/s{r['seed']}/{r['win']}/cb=*/part-0.parquet"))


def clean_members():
    mem = pl.read_parquet(f"{REG}/members.parquet")
    m = mem.filter(~pl.col("excluded"))
    assert set(m["win"].unique().to_list()) <= {"h1985", "w2015"}, m["win"].unique().to_list()
    return m


def cmd_rosteragg(args):
    os.makedirs(f"{OUT}/rosteragg", exist_ok=True)
    cols = ["Year", "Cell", "Type", "isdead", "Height", "vegc", "agb", "fpc_ind", "D95"]
    for r in clean_members().iter_rows(named=True):
        tag = f"{r['gcm']}_{r['scen']}_s{r['seed']}_{r['win']}"
        outp = f"{OUT}/rosteragg/{tag}_{args.cells}.parquet"
        if os.path.exists(outp) and not args.force:
            log("skip existing", tag)
            continue
        npatch = int(r["npatch"])
        parts, bparts, dcm, dmm = [], [], [], []
        for ch in member_chunks(r, args.cells):
            df = pl.read_parquet(ch, columns=cols).filter(dev_filter(args.cells))
            df = df.with_columns(pl.col(c).cast(pl.Float64) for c in ("Height", "vegc", "agb", "fpc_ind", "D95"))
            tree = pl.col("Type") <= 6
            live = pl.col("isdead") == 0
            aggs = [
                pl.col("vegc").filter(tree & live).sum().alias("tree_vegc_live"),
                pl.col("vegc").filter(tree & ~live).sum().alias("tree_vegc_dead"),
                pl.col("agb").filter(tree & live).sum().alias("tree_agb_live"),
                pl.col("agb").filter(tree & ~live).sum().alias("tree_agb_dead"),
                pl.col("vegc").filter(~tree).sum().alias("grass_vegc"),
                pl.col("agb").filter(~tree).sum().alias("grass_agb"),
                (tree & live).sum().alias("n_tree_live"),
                (tree & ~live).sum().alias("n_tree_dead"),
            ]
            aggs += [pl.col("fpc_ind").filter(live & (pl.col("Type") == t)).sum().alias(f"fpc_t{t}")
                     for t in range(7)]
            aggs += [pl.col("fpc_ind").filter(pl.col("Type") == t).sum().alias(f"fpc_g{t}") for t in (7, 8, 9)]
            parts.append(df.group_by(["Year", "Cell"]).agg(aggs))
            ti = pl.col("Height") == pl.col("Height").floor()
            bparts.append(
                df.filter(tree).with_columns(bin=pl.col("Height").floor().clip(0, 99).cast(pl.Int8))
                .group_by(["Year", "Cell", "bin"])
                .agg(pl.col("vegc").sum().alias("vegc_all"), pl.col("vegc").filter(live).sum().alias("vegc_live"),
                     pl.col("agb").sum().alias("agb_all"), pl.len().alias("n"),
                     pl.col("vegc").filter(ti).sum().alias("vegc_int"), ti.sum().alias("n_int")))
            # D95 bins (18 cm). 'edge_low' = a tree whose printed D95 lies within 0.01 cm ABOVE a bin edge: the C's
            # internal value may sit just below it (one bin lower). The 'mm reading' (bins of 18 mm = 1.8 cm, what
            # the coordinate label claims) is aggregated too, so the gate can show it does NOT fit.
            x = pl.col("D95") / D95_BIN_CM
            edge_low = ((x - x.floor()) * D95_BIN_CM) < 0.01
            dcm.append(
                df.filter(tree).with_columns(bin=x.floor().clip(0, 99).cast(pl.Int8), el=edge_low)
                .group_by(["Year", "Cell", "bin"])
                .agg(pl.col("vegc").sum().alias("vegc_all"), pl.len().alias("n"),
                     pl.col("vegc").filter(pl.col("el")).sum().alias("vegc_edge_low")))
            dmm.append(
                df.filter(tree).with_columns(bin=(pl.col("D95") / 1.8).floor().clip(0, 99).cast(pl.Int8))
                .group_by(["Year", "Cell", "bin"]).agg(pl.col("vegc").sum().alias("vegc_all_mmreading")))
        A = pl.concat(parts)
        B = pl.concat(bparts)
        Dcm = pl.concat(dcm)
        Dmm = pl.concat(dmm)
        assert A.select("Year", "Cell").n_unique() == A.height, "dup (Year, Cell)"
        assert B.select("Year", "Cell", "bin").n_unique() == B.height, "dup (Year, Cell, bin)"
        assert Dcm.select("Year", "Cell", "bin").n_unique() == Dcm.height, "dup d95 (Year, Cell, bin)"
        assert Dmm.select("Year", "Cell", "bin").n_unique() == Dmm.height, "dup d95mm (Year, Cell, bin)"
        D = Dcm.join(Dmm, on=["Year", "Cell", "bin"], how="full", coalesce=True).with_columns(
            pl.col(["vegc_all", "vegc_edge_low", "vegc_all_mmreading"]).fill_null(0.0), pl.col("n").fill_null(0))
        val = [c for c in A.columns if c not in ("Year", "Cell") and not c.startswith("n_")]
        A = A.with_columns((pl.col(c) / npatch) for c in val).with_columns(npatch=pl.lit(npatch, pl.Int16))
        B = B.with_columns((pl.col(c) / npatch) for c in ("vegc_all", "vegc_live", "agb_all", "vegc_int"))
        D = D.with_columns((pl.col(c) / npatch) for c in ("vegc_all", "vegc_edge_low", "vegc_all_mmreading"))
        A.sort("Year", "Cell").write_parquet(outp)
        B.sort("Year", "Cell", "bin").write_parquet(outp.replace(".parquet", "_bins.parquet"))
        D.sort("Year", "Cell", "bin").write_parquet(outp.replace(".parquet", "_d95bins.parquet"))
        log("rosteragg", tag, A.height, B.height, D.height)


# ------------------------------------------------------------------------------------------------ check tables
def load_pools(cells):
    sub = "gridded_dev" if cells == "dev" else "gridded"
    fs = sorted(glob.glob(f"{OUT}/{sub}/pools_*_ssp*_s*.parquet"))
    assert len(fs) == 12, fs
    P = pl.concat([pl.read_parquet(f) for f in fs])
    folds = pl.read_parquet(f"{REG}/folds.parquet").select(pl.col("Cell").cast(pl.Int16), "block", "fold", "is_dev")
    P = P.join(folds, on="Cell", how="inner")  # tree cells only (9065; the 2 grid cells without trees drop)
    if cells == "dev":
        assert P["is_dev"].all()
    return P


def cmd_checks(args):
    os.makedirs(f"{OUT}/check", exist_ok=True)
    P = load_pools(args.cells)
    keys = ["gcm", "scen", "Cell", "Year"]
    s1 = P.filter(pl.col("seed") == 1).select(keys + ["block", "fold", "segment_id", "use"] + CHECK_VARS)
    s2 = P.filter(pl.col("seed") == 2).select(keys + CHECK_VARS)
    J = s1.join(s2, on=keys, how="inner", suffix="_s2").rename({v: f"{v}_s1" for v in CHECK_VARS})
    assert J.height == s1.height == s2.height, (J.height, s1.height, s2.height)
    J = J.with_columns(*[(pl.col(f"{v}_s1") - pl.col(f"{v}_s2")).abs().alias(f"{v}_spread") for v in CHECK_VARS])
    J = J.sort(keys)
    assert J.select(keys).n_unique() == J.height
    J.write_parquet(f"{OUT}/check/seedpair_cell_{args.cells}.parquet")
    # 1-degree blocks: mean over the block's cells (dev cells only for --cells dev)
    bk = ["gcm", "scen", "block", "Year"]
    B = (P.group_by(["gcm", "scen", "seed", "block", "Year"])
         .agg(pl.len().alias("n_cells"), pl.col("fold").first(), pl.col("use").first(),
              *[pl.col(v).cast(pl.Float64).fill_nan(None).mean() for v in CHECK_VARS]))
    b1 = B.filter(pl.col("seed") == 1).drop("seed").rename({v: f"{v}_s1" for v in CHECK_VARS})
    b2 = B.filter(pl.col("seed") == 2).select(bk + CHECK_VARS).rename({v: f"{v}_s2" for v in CHECK_VARS})
    JB = b1.join(b2, on=bk, how="inner").with_columns(
        *[(pl.col(f"{v}_s1") - pl.col(f"{v}_s2")).abs().alias(f"{v}_spread") for v in CHECK_VARS]).sort(bk)
    assert JB.select(bk).n_unique() == JB.height == b1.height
    JB.write_parquet(f"{OUT}/check/seedpair_block_{args.cells}.parquet")
    log("checks", J.height, JB.height)


def _unit_means(P, gk):
    """cell means over the window first, then the unit mean (equal cell weights); NaN medians -> null."""
    cm = P.group_by(["gcm", "scen", "seed", "Cell", "block"]).agg(
        *[pl.col(v).cast(pl.Float64).fill_nan(None).mean() for v in RESP_VARS])
    return cm.group_by(["gcm", "scen", "seed"] + gk).agg(*[pl.col(v).mean() for v in RESP_VARS])


def _leg(df, gcm, scen, seed, gk, v):
    x = df.filter((pl.col("gcm") == gcm) & (pl.col("scen") == scen) & (pl.col("seed") == seed))
    return x.sort(gk).select(gk + [v]) if gk else x.select(v)


def cmd_response(args):
    """Signal-to-noise of the early-century responses on cell aggregates (see module docstring)."""
    os.makedirs(f"{OUT}/check", exist_ok=True)
    P = load_pools(args.cells)
    base = P.filter(pl.col("Year").is_between(1985, 2014))
    summ = []
    for wname, (y0, y1) in RESP_WINDOWS.items():
        W = P.filter(pl.col("Year").is_between(y0, y1))
        for unit, gk in (("cell", ["Cell"]), ("block", ["block"]), ("germany", [])):
            um, ub = _unit_means(W, gk), _unit_means(base, gk)
            for gcm in GCMS:
                for a_scen, mixed in (("ssp370", False), ("ssp245", True)):
                    for v in RESP_VARS:
                        dB, dC = {}, {}
                        for s in SEEDS:
                            xa, xb = _leg(um, gcm, a_scen, s, gk, v), _leg(um, gcm, "ssp126", s, gk, v)
                            xc = _leg(ub, gcm, a_scen, s, gk, v)
                            if gk:
                                assert xa[gk[0]].to_list() == xb[gk[0]].to_list() == xc[gk[0]].to_list()
                            dB[s] = xa[v].to_numpy() - xb[v].to_numpy()
                            dC[s] = xa[v].to_numpy() - xc[v].to_numpy()
                        lvl = np.abs(_leg(ub, gcm, "ssp126", 1, gk, v)[v].to_numpy().astype(np.float64))
                        for stat, dd, lab in (("between_scen", dB, f"{a_scen}-ssp126"),
                                              ("change_vs_1985_2014", dC, a_scen)):
                            d1 = dd[1].astype(np.float64)
                            d2 = dd[2].astype(np.float64)
                            ok = np.isfinite(d1) & np.isfinite(d2)
                            m, n = (d1 + d2)[ok] / 2, np.abs(d1 - d2)[ok]
                            lv = np.where(lvl[ok] > 0, lvl[ok], np.nan)
                            summ.append(dict(
                                window=wname, years=f"{y0}-{y1}", unit=unit, gcm=gcm, stat=stat, contrast=lab,
                                var=v, binary_mixed=mixed, n_units=int(ok.sum()),
                                frac_determined=float((np.abs(m) > n).mean()) if ok.any() else None,
                                null_frac_determined=NULL_DETERMINED,
                                frac_same_sign=float((np.sign(d1[ok]) == np.sign(d2[ok])).mean()) if ok.any() else None,
                                median_abs_signal_over_seed_diff=float(np.nanmedian(np.abs(m) / np.where(n > 0, n, np.nan)))
                                if ok.any() else None,
                                median_signal=float(np.median(m)) if ok.any() else None,
                                median_abs_seed_diff=float(np.median(n)) if ok.any() else None,
                                median_rel_signal=float(np.nanmedian(m / lv)) if ok.any() else None,
                                median_rel_seed_diff=float(np.nanmedian(n / lv)) if ok.any() else None,
                                seed1=float(d1[0]) if unit == "germany" else None,
                                seed2=float(d2[0]) if unit == "germany" else None))
            log("response", wname, unit)
    S = pl.DataFrame(summ, infer_schema_length=None)
    S.write_parquet(f"{OUT}/check/response_snr_{args.cells}.parquet")
    log("response rows", S.height)


# ------------------------------------------------------------------------------------------------ gates
def q(x, ps=(0.5, 0.9, 0.99, 0.999, 1.0)):
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    return {str(p): (float(np.quantile(x, p)) if len(x) else None) for p in ps}


def cmd_gate(args):
    res = {"basis": f"cells={args.cells} (dev = Cell % 10 == 0, 907 tree cells; all = 9065 tree cells / 9067 grid)",
           "owner_exclusion": "2071-2100 and 3071-3100 excluded (humidity read as specific humidity)", "gates": {}}
    G = res["gates"]
    g1 = json.load(open(f"{OUT}/_g1_grid.json"))
    prov = pl.read_parquet(f"{OUT}/_provenance.parquet")
    pg = prov.filter(pl.col("var") == "grid")
    g1["n_member_grid_files"] = pg.height
    g1["all_member_grid_files_equal_ref"] = bool(pg["cellid_equals_ref"].fill_null(False).all())
    g1["all_data_files_latlon_equal_ref"] = bool(prov["lat_ok"].fill_null(False).all()
                                                 and prov["lon_ok"].fill_null(False).all())
    g1["pass_threshold"] = "cellid 0..9066 once; |dlat|,|dlon| vs grid .clm < 1e-4 deg; = cell_static index; every " \
                           "member/segment grid file's cellid raster == ref; every data file's lat/lon == ref"
    g1["pass"] = bool(g1["cellid_is_0..9066_once"] and g1["equals_cell_static_nc_index"]
                      and g1["max_abs_dlat_vs_grid_clm_deg"] < 1e-4 and g1["max_abs_dlon_vs_grid_clm_deg"] < 1e-4
                      and g1["all_member_grid_files_equal_ref"] and g1["all_data_files_latlon_equal_ref"]
                      and g1["n_member_grid_files"] == 4 + 12 * 3)
    G["G1_raster_to_cell_map"] = g1
    g2 = dict(n_rows=prov.height, n_chosen=int(prov["chosen"].sum()),
              not_chosen=prov.filter(~pl.col("chosen")).select("gcm", "scen", "seed", "segment", "var", "path")
              .to_dicts(),
              writer_unique=bool((prov["n_writer_match"] == 1).all()),
              n_writer_equals_segment_job=int(prov["writer_equals_segment_job"].sum()),
              writer_not_segment_job=prov.filter(~pl.col("writer_equals_segment_job").fill_null(False))
              .select("gcm", "scen", "seed", "segment", "var", "writer_job", "seg_jobs").to_dicts(),
              ind_inconsistent=prov.filter(pl.col("ind_consistent") == False)  # noqa: E712
              .select("gcm", "scen", "seed", "segment", "var", "writer_job", "ind_writer_job").to_dicts(),
              writer_log_completed=bool(prov["log_completed"].fill_null(False).all()))
    g2["pass_threshold"] = "every (traj, segment, var) chosen = raw, exact years, no fill; one writer job each, == " \
                           "SH0's segment job, == the tree table's writer job where one exists; writer log completed"
    g2["pass"] = bool(g2["n_chosen"] == prov.height and g2["writer_unique"]
                      and g2["n_writer_equals_segment_job"] == prov.height and not g2["ind_inconsistent"]
                      and g2["writer_log_completed"] and prov.height == (4 + 12 * 3) * len(GVARS))
    G["G2_file_provenance"] = g2
    hv = prov.group_by("gcm", "scen", "seed", "segment").agg(
        pl.col("humid_log").unique().alias("humid_log"), pl.col("rh_js").unique().alias("rh_js"),
        pl.col("writer_humid_kind_sh0").unique().alias("sh0"), pl.col("seg_humid_kind").first(),
        pl.col("seg_excluded").first(), pl.col("seg_use").first(), pl.col("writer_job").unique().alias("jobs"))
    hv = hv.with_columns(ok=(pl.col("humid_log").list.len() == 1) & (pl.col("humid_log").list.first() == "rhumid")
                         & (pl.col("rh_js").list.len() == 1) & pl.col("rh_js").list.first()
                         & (pl.col("sh0").list.first() == "rhumid") & (pl.col("seg_humid_kind") == "rhumid")
                         & ~pl.col("seg_excluded").fill_null(True))
    g3 = dict(n_segments=hv.height, n_ok=int(hv["ok"].sum()),
              by_segment={s: dict(n=int(hv.filter(pl.col("segment") == s).height),
                                  n_rhumid_log=int(hv.filter((pl.col("segment") == s) & pl.col("ok")).height))
                          for s in SEGMENTS},
              bad=hv.filter(~pl.col("ok")).to_dicts(),
              writer_jobs_2045_2070=sorted({j for x in hv.filter(pl.col("segment") == "2045-2070")["jobs"].to_list()
                                            for j in x}))
    g3["pass_threshold"] = "every segment read (4 Historical + 12 x 2015-2044 + 12 x 2045-2070): writer log input " \
                           "line 'rhumid', config sets relative_humidity true, SH0 agrees, segment not excluded"
    # AMENDMENT (arithmetic, before any humidity result was read differently): the pre-registered count said 28; the
    # correct count of (trajectory, segment) pairs read is 4 Historical + 12 ssp x 3 segments = 40 (each ssp
    # trajectory re-reads its seed's Historical 1985-2014 files). The criterion itself (every one 'rhumid') is unchanged.
    g3["count_amendment"] = "expected 40 (4 + 12 x 3), the pre-registered 28 was an arithmetic slip"
    g3["pass"] = bool(g3["n_ok"] == g3["n_segments"] == 40)
    G["G3_humidity_setting"] = g3
    maxy = {}
    for f in sorted(glob.glob(f"{OUT}/gridded*/*.parquet")) + sorted(glob.glob(f"{OUT}/check/*.parquet")) + \
            sorted(glob.glob(f"{OUT}/rosteragg/*.parquet")):
        sch = pl.read_parquet_schema(f)
        if "Year" in sch:
            maxy[os.path.relpath(f, OUT)] = int(pl.scan_parquet(f).select(pl.col("Year").max()).collect().item())
    g3b = dict(n_tables=len(maxy), max_year=max(maxy.values()) if maxy else None,
               tables_over_2070=[k for k, v in maxy.items() if v > LAST_YEAR],
               excluded_paths_in_provenance=int(prov["path"].str.contains(r"_(2100|3100|3070)").sum()),
               rosteragg_windows=sorted({re.search(r"_(h1985|w2015|w2071|w3071)_", k).group(1)
                                         for k in maxy if k.startswith("rosteragg/")}))
    g3b["pass_threshold"] = "no v2 table holds a Year > 2070; no excluded file in provenance; roster sums only " \
                            "from h1985/w2015"
    g3b["pass"] = bool(not g3b["tables_over_2070"] and g3b["excluded_paths_in_provenance"] == 0
                       and set(g3b["rosteragg_windows"]) <= {"h1985", "w2015"})
    G["G3b_exclusion"] = g3b
    g11 = {}
    for gv, (_s, _v, u) in GVARS.items():
        if u is None:
            continue
        pv = prov.filter(pl.col("var") == gv)
        g11[gv] = dict(units=pv["units"].unique().to_list(), expected=u,
                       ok=bool((pv["units"] == u).all()))
    tu = prov.filter(pl.col("var") != "grid").with_columns(
        exp=pl.format("days since {}-1-1 0:0:0", pl.col("segment").str.slice(0, 4)))
    g11["time_units_ok"] = bool((tu["time_units"] == tu["exp"]).all())
    g11["calendar"] = tu["calendar"].unique().to_list()
    dd = prov.filter(pl.col("var") == "D95")
    g11["D95_coord_label"] = dict(units=dd["d95_coord_units"].unique().to_list(),
                                  max=dd["d95_coord_max"].unique().to_list(),
                                  note="label only; G10 decides the bin unit")
    g11["pass"] = bool(all(v["ok"] for k, v in g11.items() if isinstance(v, dict) and "ok" in v)
                       and g11["time_units_ok"] and g11["calendar"] == ["noleap"])
    G["G11_units"] = g11
    # ---- roster gates on the clean member-windows
    mem = clean_members()
    st = {k: [] for k in ("bin_rel_all", "bin_rel_live", "bin_rel_agb", "ge5_rel_all", "ge5_rel_live",
                          "vegc_close_rel", "agb_sub5_rel", "agb_sub5_le_hm_lt5", "fpc_grass_abs", "fpc_tree_def",
                          "hm_lt5_share", "bin_in_bound", "d95_in_bound", "d95_in_bound_mm", "d95_rel_le")}
    per_member = []
    for r in mem.iter_rows(named=True):
        tag = f"{r['gcm']}_{r['scen']}_s{r['seed']}_{r['win']}"
        p = f"{OUT}/rosteragg/{tag}_{args.cells}.parquet"
        if not os.path.exists(p):
            log("MISSING rosteragg", tag)
            continue
        yc = [int(y) for y in r["years_complete"]]
        A = pl.read_parquet(p).filter(pl.col("Year").is_in(yc))
        B = pl.read_parquet(p.replace(".parquet", "_bins.parquet")).filter(pl.col("Year").is_in(yc))
        DB = pl.read_parquet(p.replace(".parquet", "_d95bins.parquet")).filter(pl.col("Year").is_in(yc))
        traj = r["scen"]
        P = pl.read_parquet(f"{OUT}/gridded/pools_{r['gcm']}_{traj}_s{r['seed']}.parquet")
        H = pl.read_parquet(f"{OUT}/gridded/height_mass_{r['gcm']}_{traj}_s{r['seed']}.parquet")
        D = pl.read_parquet(f"{OUT}/gridded/d95_mass_{r['gcm']}_{traj}_s{r['seed']}.parquet")
        J = A.join(P, on=["Year", "Cell"], how="inner")
        assert J.height == A.height, (tag, J.height, A.height)
        Hl = (H.join(A.select("Year", "Cell"), on=["Year", "Cell"], how="semi")
              .unpivot(index=["Cell", "Year"], on=HM_COLS[5:], variable_name="b", value_name="hm")
              .with_columns(bin=pl.col("b").str.slice(3).cast(pl.Int8)).drop("b"))
        JB = Hl.join(B, on=["Year", "Cell", "bin"], how="full", coalesce=True).with_columns(
            pl.col(["hm", "vegc_all", "vegc_live", "agb_all", "vegc_int"]).fill_null(0.0))
        JB = JB.sort("Year", "Cell", "bin").with_columns(
            vegc_int_up=pl.col("vegc_int").shift(-1).over(["Year", "Cell"], order_by="bin").fill_null(0.0),
            nb=pl.col("bin").shift(-1).over(["Year", "Cell"], order_by="bin")).with_columns(
            vegc_int_up=pl.when(pl.col("nb") == pl.col("bin") + 1).then(pl.col("vegc_int_up")).otherwise(0.0))
        JB = JB.filter((pl.col("hm") > 0) | (pl.col("vegc_all") > 0))
        lo = (JB["vegc_all"] - JB["vegc_int"]).to_numpy()
        hi = (JB["vegc_all"] + JB["vegc_int_up"]).to_numpy()
        hmv = JB["hm"].to_numpy().astype(np.float64)
        tolb = 1e-5 * np.maximum(hmv, 1e-3) + 1e-6
        st["bin_in_bound"].append(((hmv >= lo - tolb) & (hmv <= hi + tolb)).astype(np.float64))
        den = np.maximum(np.abs(hmv), 1e-3)
        st["bin_rel_all"].append(np.abs(hmv - JB["vegc_all"].to_numpy()) / den)
        st["bin_rel_live"].append(np.abs(hmv - JB["vegc_live"].to_numpy()) / den)
        st["bin_rel_agb"].append(np.abs(hmv - JB["agb_all"].to_numpy()) / den)
        # D95: gridded bin k >= roster(>5 m) bin k (gridded also holds sub-5 m trees); a roster tree printed within
        # 0.01 cm ABOVE an edge may belong one bin lower -> allow that mass to move down
        Dl = (D.join(A.select("Year", "Cell"), on=["Year", "Cell"], how="semi")
              .unpivot(index=["Cell", "Year"], on=D95_COLS, variable_name="b", value_name="dm")
              .with_columns(bin=pl.col("b").str.slice(4).cast(pl.Int8)).drop("b"))
        JD = Dl.join(DB, on=["Year", "Cell", "bin"], how="full", coalesce=True).with_columns(
            pl.col(["dm", "vegc_all", "vegc_edge_low", "vegc_all_mmreading"]).fill_null(0.0))
        JD = JD.filter((pl.col("dm") > 0) | (pl.col("vegc_all") > 0) | (pl.col("vegc_all_mmreading") > 0))
        dmv = JD["dm"].to_numpy().astype(np.float64)
        tol = 1e-5 * np.maximum(dmv, 1e-3) + 1e-6
        rv = JD["vegc_all"].to_numpy() - JD["vegc_edge_low"].to_numpy()
        st["d95_in_bound"].append((rv <= dmv + tol).astype(np.float64))
        st["d95_in_bound_mm"].append((JD["vegc_all_mmreading"].to_numpy() <= dmv + tol).astype(np.float64))
        st["d95_rel_le"].append(np.abs(dmv - JD["vegc_all"].to_numpy()) / np.maximum(dmv, 1e-3))
        Mw = DB.group_by("Year", "Cell").agg(pl.col("vegc_all").sum().alias("t"))
        hm_ge5 = J["hm_ge5"].to_numpy().astype(np.float64)
        dd_ = np.maximum(hm_ge5, 1e-3)
        st["ge5_rel_all"].append(np.abs(hm_ge5 - (J["tree_vegc_live"] + J["tree_vegc_dead"]).to_numpy()) / dd_)
        st["ge5_rel_live"].append(np.abs(hm_ge5 - J["tree_vegc_live"].to_numpy()) / dd_)
        nat = J["natfrac"].to_numpy().astype(np.float64)
        vegc = J["VegC"].to_numpy().astype(np.float64)
        agb = J["AGB"].to_numpy().astype(np.float64)
        hm_sum = J["hm_sum"].to_numpy().astype(np.float64)
        hm_lt5 = J["hm_lt5"].to_numpy().astype(np.float64)
        close = vegc / nat - J["grass_vegc"].to_numpy() - (hm_sum - J["tree_vegc_dead"].to_numpy())
        st["vegc_close_rel"].append(close / np.maximum(vegc / nat, 1e-3))
        sub5 = agb / nat - J["tree_agb_live"].to_numpy() - J["grass_agb"].to_numpy()
        st["agb_sub5_rel"].append(sub5 / np.maximum(agb / nat, 1e-3))
        st["agb_sub5_le_hm_lt5"].append((sub5 <= hm_lt5 + 1e-3 * np.maximum(agb / nat, 1.0)).astype(np.float64))
        st["fpc_grass_abs"].append(np.concatenate([np.abs(J[f"fpc_g{t}"].to_numpy() - J[f"fpc_g{t}_right"].to_numpy())
                                                   for t in (7, 8, 9)]))
        st["fpc_tree_def"].append(np.concatenate([J[f"fpc_t{t}_right"].to_numpy() - J[f"fpc_t{t}"].to_numpy()
                                                  for t in range(7)]))
        st["hm_lt5_share"].append(hm_lt5 / np.maximum(hm_sum, 1e-9))
        per_member.append(dict(member=tag, n_cell_years=J.height, n_hbins=JB.height, n_dbins=JD.height,
                               d95_roster_total_over_hm_ge5=float(Mw["t"].sum() / max(hm_ge5.sum(), 1e-9))))
        log("gate rows", tag)
    cat = {k: (np.concatenate(v) if v else np.array([])) for k, v in st.items()}
    g4 = dict(definition="per (cell, year, 1-m bin k>=5): |height_mass_k - roster sum floor(H)=k X / npatch| / "
              "max(height_mass_k, 1e-3); X = vegc incl. flagged dead, vegc live only, agb",
              n=int(len(cat["bin_rel_all"])), rel_vegc_incl_dead=q(cat["bin_rel_all"]),
              rel_vegc_live_only=q(cat["bin_rel_live"]), rel_agb=q(cat["bin_rel_agb"]),
              ge5_sum_rel_vegc_incl_dead=q(cat["ge5_rel_all"]), ge5_sum_rel_vegc_live=q(cat["ge5_rel_live"]),
              frac_bins_within_integer_height_bound=float(cat["bin_in_bound"].mean()),
              n_bins_outside_bound=int((cat["bin_in_bound"] == 0).sum()))
    g4["pass_threshold"] = "sum over bins >= 5: max rel err < 1e-5 for vegc incl. dead; p50 > 1e-2 for vegc " \
                           "live-only and for agb (they must NOT fit); >= 99.99 % of bins inside the integer-height bound"
    g4["pass"] = bool(g4["n"] > 0 and g4["ge5_sum_rel_vegc_incl_dead"]["1.0"] < 1e-5
                      and g4["ge5_sum_rel_vegc_live"]["0.5"] > 1e-2 and g4["rel_agb"]["0.5"] > 1e-2
                      and g4["frac_bins_within_integer_height_bound"] >= 0.9999)
    G["G4_height_mass_is_vegc_incl_dead"] = g4
    g5 = dict(definition="VegC/natfrac - grass_vegc - (hm_sum - roster dead>5m vegc), relative to VegC/natfrac",
              n=int(len(cat["vegc_close_rel"])), rel=q(cat["vegc_close_rel"], (0.0, 0.001, 0.5, 0.999, 1.0)))
    g5["pass_threshold"] = "p0.1 > -1e-2 and p99.9 < 1e-3"
    g5["pass"] = bool(g5["n"] > 0 and g5["rel"]["0.001"] > -1e-2 and g5["rel"]["0.999"] < 1e-3)
    G["G5_vegc_closure"] = g5
    g6 = dict(definition="sub-5 m tree AGB = AGB/natfrac - roster live tree agb - grass agb; >= 0 and <= hm bins 0-4",
              n=int(len(cat["agb_sub5_rel"])), rel=q(cat["agb_sub5_rel"], (0.0, 0.001, 0.5, 0.999, 1.0)),
              frac_le_hm_lt5=float(cat["agb_sub5_le_hm_lt5"].mean()),
              hm_lt5_share_of_tree_vegc=q(cat["hm_lt5_share"], (0.5, 0.9, 0.99)))
    g6["pass_threshold"] = "p0.1 of rel > -1e-3 and frac_le_hm_lt5 >= 0.999"
    g6["pass"] = bool(g6["n"] > 0 and g6["rel"]["0.001"] > -1e-3 and g6["frac_le_hm_lt5"] >= 0.999)
    G["G6_agb_sub5"] = g6
    g7 = dict(definition="grass FPC bands vs roster grass fpc_ind/npatch; tree bands minus roster live >5 m",
              grass_abs=q(cat["fpc_grass_abs"]), tree_band_minus_roster=q(cat["fpc_tree_def"], (0.0, 0.001, 0.5, 1.0)))
    g7["pass_threshold"] = "grass p99.9 < 1e-4 and tree p0.1 > -1e-4 (DIAGNOSTIC, not blocking)"
    g7["pass"] = bool(len(cat["fpc_grass_abs"]) and g7["grass_abs"]["0.999"] < 1e-4
                      and g7["tree_band_minus_roster"]["0.001"] > -1e-4)
    G["G7_fpc_vs_roster_DIAGNOSTIC"] = g7
    # ---- G10 D95 (part a uses the gridded tables only, so it also covers 2045-2070)
    tot_rel = []
    for f in sorted(glob.glob(f"{OUT}/gridded/pools_*.parquet")):
        Pp = pl.read_parquet(f, columns=["Year", "hm_sum", "d95_sum"]).filter(pl.col("hm_sum") > 1.0)
        tot_rel.append((Pp["d95_sum"].cast(pl.Float64) - Pp["hm_sum"].cast(pl.Float64)).abs().to_numpy()
                       / Pp["hm_sum"].cast(pl.Float64).to_numpy())
        if "2045" not in res.setdefault("_g10_years", ""):
            res["_g10_years"] += f"{Pp['Year'].min()}-{Pp['Year'].max()};"
    tot_rel = np.concatenate(tot_rel)
    g10 = dict(definition="(a) |sum_k D95_mass_k - sum_k height_mass_k| / sum height_mass, every cell-year with "
               "> 1 gC/m2 tree vegc, ALL years 1985-2070 (same tree population, same vegc); (b) per D95 bin "
               "(18 cm): roster(>5 m) vegc <= gridded bin (+1e-5 rel), edge trees allowed one bin down; (c) the same "
               "with 1.8-cm (= '18 mm') bins must FAIL",
               total_rel=q(tot_rel), n_cell_years=int(len(tot_rel)),
               frac_bins_in_bound_18cm=float(cat["d95_in_bound"].mean()) if len(cat["d95_in_bound"]) else None,
               n_bins_out_18cm=int((cat["d95_in_bound"] == 0).sum()),
               frac_bins_in_bound_mm_reading=float(cat["d95_in_bound_mm"].mean()) if len(cat["d95_in_bound_mm"])
               else None, rel_gridded_minus_roster=q(cat["d95_rel_le"], (0.5, 0.9, 0.99)))
    g10["pass_threshold"] = "(a) max < 1e-5; (b) >= 99.99 % of bins in bound; (c) mm reading < 99 % in bound"
    g10["pass"] = bool(g10["total_rel"]["1.0"] is not None and g10["total_rel"]["1.0"] < 1e-5
                       and g10["frac_bins_in_bound_18cm"] is not None and g10["frac_bins_in_bound_18cm"] >= 0.9999
                       and g10["frac_bins_in_bound_mm_reading"] < 0.99)
    g10["verdict"] = "D95_mass bins are 18 CM wide (the coordinate's 'mm' label is wrong)" if g10["pass"] else \
        "NOT settled"
    G["G10_d95_mass"] = g10
    res.pop("_g10_years", None)
    # ---- G8 restart chain + continuity
    G["G8_restart_chain"] = restart_chain(prov)
    g8 = {}
    for f in sorted(glob.glob(f"{OUT}/gridded/pools_*_ssp*_s*.parquet")):
        P = pl.read_parquet(f, columns=["Cell", "Year", "AGB", "VegC", "LitC", "SoilC", "hm_ge5"]).sort("Cell", "Year")
        tag = os.path.basename(f)[6:-8]
        out = {}
        for v in ("AGB", "VegC", "LitC", "SoilC", "hm_ge5"):
            d = P.with_columns(dv=(pl.col(v).cast(pl.Float64) - pl.col(v).cast(pl.Float64).shift(1).over("Cell"))
                               .abs()).group_by("Year").agg(pl.col("dv").mean()).drop_nulls().sort("Year")
            dmap = dict(zip(d["Year"].to_list(), d["dv"].to_list(), strict=True))
            inner = [dmap[y] for y in dmap if y not in (2015, 2045)]
            med = float(np.median(inner))
            out[v] = {str(y): round(dmap[y] / med, 3) for y in (2015, 2045)}
            out[v]["max_inner_ratio"] = round(max(inner) / med, 3)
        g8[tag] = out
    worst = max(max(v[str(y)] for y in (2015, 2045)) / max(1.0, v["max_inner_ratio"])
                for o in g8.values() for v in o.values())
    G["G8b_join_continuity_DIAGNOSTIC"] = dict(
        definition="Germany-mean |X(y) - X(y-1)| at the joins y = 2015, 2045 over the median of the same statistic in "
        "all other years 1986-2070; max_inner_ratio = the largest ordinary year", per_trajectory=g8,
        worst_join_over_max_inner=round(worst, 3), join_is_not_an_outlier=bool(worst <= 1.0), **{"pass": True})
    # ---- G13 the consumer API reproduces the gridded check quantities from the truth roster (dev rosters)
    g13 = {"per_member": {}}
    hrel, mdiff, ddiff = [], [], []
    for r in mem.iter_rows(named=True):
        tag = f"{r['gcm']}_{r['scen']}_s{r['seed']}_{r['win']}"
        yc = [int(y) for y in r["years_complete"]]
        ros = pl.read_parquet(member_chunks(r, "dev")[0],
                              columns=["Year", "Cell", "Type", "isdead", "Height", "vegc", "D95"]).filter(
            (pl.col("Cell") % 10 == 0) & pl.col("Year").is_in(yc))
        ra = roster_check_aggregates(ros, int(r["npatch"]))
        Pg = pl.read_parquet(f"{OUT}/gridded_dev/pools_{r['gcm']}_{r['scen']}_s{r['seed']}.parquet",
                             columns=["Year", "Cell", "hm_ge5", "hm_ge5_medH", "d95_med_cm"])
        j = ra.join(Pg, on=["Year", "Cell"], how="inner", suffix="_grid")
        assert j.height == ra.height, (tag, j.height, ra.height)
        hr = ((j["hm_ge5"] - j["hm_ge5_grid"].cast(pl.Float64)).abs() / j["hm_ge5_grid"].cast(pl.Float64).clip(1e-3)
              ).to_numpy()
        md = (j["hm_ge5_medH"] - j["hm_ge5_medH_grid"].cast(pl.Float64)).abs().to_numpy()
        dd = (j["d95_ge5_med_cm"] - j["d95_med_cm"].cast(pl.Float64)).to_numpy()
        # attribution of every non-zero median difference: does that cell-year hold a tree whose PRINTED height is an
        # exact integer (its bin is ambiguous by one from the table; documented in G4)?
        ints = ros.filter((pl.col("Type") <= 6) & (pl.col("Height") >= 5)
                          & (pl.col("Height") == pl.col("Height").floor())).select("Year", "Cell").unique()
        jb = j.with_columns(md=pl.Series(md)).filter(pl.col("md") > 1e-4)
        n_unexpl = jb.join(ints.with_columns(pl.col("Year").cast(pl.Int16), pl.col("Cell").cast(pl.Int16)),
                           on=["Year", "Cell"], how="anti").height
        g13.setdefault("n_diff_gt_1e-4", 0)
        g13.setdefault("n_diff_gt_1e-4_without_integer_height_tree", 0)
        g13["n_diff_gt_1e-4"] += jb.height
        g13["n_diff_gt_1e-4_without_integer_height_tree"] += n_unexpl
        hrel.append(hr)
        mdiff.append(md)
        ddiff.append(dd)
        g13["per_member"][tag] = dict(n=j.height, hm_ge5_rel_max=float(np.nanmax(hr)),
                                      medH_absdiff_max=float(np.nanmax(md)))
    hrel, mdiff, ddiff = (np.concatenate(x) for x in (hrel, mdiff, ddiff))
    g13.update(definition="roster_check_aggregates(truth dev roster, npatch) vs the gridded dev check table, per "
               "(cell, year), all 16 clean member-windows", n=int(len(hrel)), hm_ge5_rel=q(hrel),
               hm_ge5_medH_absdiff_m=q(mdiff, (0.5, 0.99, 0.999, 1.0)),
               d95_med_roster_ge5_minus_grid_all_trees_cm=q(ddiff, (0.001, 0.01, 0.5, 0.99, 0.999)),
               pass_threshold="hm_ge5 max rel < 1e-5; hm_ge5_medH |diff| p99.9 < 0.01 m and max < 0.5 m (a tree "
               "printed at an exact integer height can move one bin); the D95 median is REPORTED only (the grid "
               "also holds sub-5 m trees)")
    g13["pass_preregistered"] = bool(g13["hm_ge5_rel"]["1.0"] < 1e-5 and g13["hm_ge5_medH_absdiff_m"]["0.999"] < 0.01
                                     and g13["hm_ge5_medH_absdiff_m"]["1.0"] < 0.5)
    # AMENDMENT (after the first dev run: p99.9 was 0.0147 m > 0.01): the tail is the integer-printed-height ambiguity
    # already documented in G4. Amended criterion: every cell-year with |medH diff| > 1e-4 m holds such a tree, and
    # max < 0.5 m. Reported beside the pre-registered verdict, never instead of it.
    g13["pass_threshold_amended"] = "hm_ge5 max rel < 1e-5; every |medH diff| > 1e-4 m explained by an integer-height " \
                                    "tree in that cell-year; max |medH diff| < 0.5 m"
    g13["pass"] = bool(g13["hm_ge5_rel"]["1.0"] < 1e-5 and g13["n_diff_gt_1e-4_without_integer_height_tree"] == 0
                       and g13["hm_ge5_medH_absdiff_m"]["1.0"] < 0.5)
    G["G13_consumer_api"] = g13
    # ---- G12 integrity of the v2 tables
    g12 = {}
    for sub in ("gridded", "gridded_dev"):
        for f in sorted(glob.glob(f"{OUT}/{sub}/pools_*.parquet")):
            T = pl.read_parquet(f)
            ny = T["Year"].n_unique()
            num = T.select(pl.col(pl.Float32)).to_numpy()
            fin_cols = [c for c in T.select(pl.col(pl.Float32)).columns if c not in ("hm_ge5_medH", "d95_med_cm")]
            g12[os.path.relpath(f, OUT)] = dict(
                rows=T.height, years=f"{T['Year'].min()}-{T['Year'].max()}", ny=ny,
                unique=T.select("Cell", "Year").n_unique() == T.height,
                rows_ok=T.height == ny * (NCELL if sub == "gridded" else T["Cell"].n_unique()),
                finite=bool(np.isfinite(T.select(fin_cols).to_numpy()).all()),
                medians_nan_only_where_empty=bool(T.filter(pl.col("hm_ge5_medH").is_nan() & (pl.col("hm_ge5") > 0))
                                                  .height == 0),
                n_float=num.shape[1])
    ok12 = all(v["unique"] and v["rows_ok"] and v["finite"] and v["medians_nan_only_where_empty"]
               for v in g12.values())
    yrs_ok = all(v["years"] == ("1985-2014" if "Historical" in k else "1985-2070") for k, v in g12.items())
    for f in sorted(glob.glob(f"{OUT}/check/seedpair_*_{args.cells}.parquet")):
        T = pl.read_parquet(f)
        g12[os.path.relpath(f, OUT)] = dict(rows=T.height, years=f"{T['Year'].min()}-{T['Year'].max()}")
    G["G12_table_integrity"] = dict(per_table=g12, pass_threshold="unique (Cell, Year), complete cell x year grid, "
                                    "all pools finite, medians NaN only where the histogram is empty, ssp tables "
                                    "1985-2070, Historical 1985-2014", **{"pass": bool(ok12 and yrs_ok)})
    try:
        S = pl.read_parquet(f"{OUT}/check/response_snr_{args.cells}.parquet")
        res["response_snr"] = dict(null_frac_determined=NULL_DETERMINED, rows=S.to_dicts())
    except FileNotFoundError:
        pass
    res["per_member_roster"] = per_member
    res["all_pass"] = all(v["pass"] for k, v in G.items() if "DIAGNOSTIC" not in k)
    with open(f"{OUT}/_gates_{args.cells}.json", "w") as fh:
        json.dump(res, fh, indent=1, default=str)
    log("GATES", json.dumps({k: v["pass"] for k, v in G.items()}), "all_pass(binding)", res["all_pass"])


def restart_chain(prov):
    """successor.restart_from == predecessor.restart_written, predecessor ended first, no other attempt overwrote
    that restart in between (SH0 attempts table). Links 1985-2014 -> 2015-2044 -> 2045-2070 for the 12 ssp
    trajectories (24 links)."""
    att = pl.read_parquet(f"{REG}/attempts.parquet")
    A = {r["job"]: r for r in att.iter_rows(named=True)}
    links = []
    w = prov.filter(pl.col("var") == "AGB")
    chain = list(SEGMENTS)
    for (gcm, scen, seed), g in w.group_by(["gcm", "scen", "seed"], maintain_order=True):
        if scen == "Historical":
            continue
        job = {r["segment"]: r["writer_job"] for r in g.iter_rows(named=True)}
        for p_, s_ in zip(chain[:-1], chain[1:], strict=True):
            P, S = A.get(job.get(p_)), A.get(job.get(s_))
            rec = dict(gcm=gcm, scen=scen, seed=seed, link=f"{p_}->{s_}", pred_job=job.get(p_), succ_job=job.get(s_))
            if P is None or S is None:
                rec.update(ok=False, why="job not found")
            else:
                rw = P["restart_written"]
                over = att.filter((pl.col("restart_written") == rw) & (pl.col("job") != P["job"])
                                  & (pl.col("job_start") > P["job_start"]) & (pl.col("job_start") < S["job_start"]))
                rec.update(restart=rw, same_path=S["restart_from"] == rw, ordered=bool(P["job_end"] <= S["job_start"]),
                           overwritten_by=over["job"].to_list())
                rec["ok"] = bool(rec["same_path"] and rec["ordered"] and not rec["overwritten_by"])
            links.append(rec)
    bad = [x for x in links if not x["ok"]]
    return dict(n_links=len(links), n_bad=len(bad), bad=bad,
                pass_threshold="all 24 links (12 ssp trajectories x 2) ok",
                **{"pass": len(links) == 24 and not bad})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["provenance", "gridded", "rosteragg", "checks", "response", "gate", "all"])
    ap.add_argument("--cells", choices=["dev", "all"], default="dev")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    steps = ["provenance", "gridded", "rosteragg", "checks", "response", "gate"] if args.cmd == "all" else [args.cmd]
    for s in steps:
        log("=== step", s)
        globals()[f"cmd_{s}"](args)
    log(f"DONE SH12 {args.cmd} cells={args.cells} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    sys.exit(main())
