#!/usr/bin/env python3
"""glob_emu.py -- the learned emulator (release-v1 package, python/src/lpjmlfit_emulator/landemu) RETRAINED on
M. Billing's Oct-2026 GFDL-ESM4 r1_1 runs and RUN ON THE FULL GRID (67 420 cells), for the global benchmark against
the original (ILAMB + lpjmlstats). Owner instruction 2026-10-15; design and pre-registration: ADR 0341.

Training/benchmark runs (all Oct-8-2026 build, 67 420 cells, 25 patches, audited 2026-10-15):
  GCM/historical/GFDL-ESM4/r1_1   1901-2014 (gridded + per-tree output 1985-2014; rising CO2)
  GCM/ssp<126|245|370>/GFDL-ESM4/r1_1   2015-2100 from the historical run's restart_2014_nv.lpj (CO2 const from 2014);
      output_transient/ = one continuous 2015-2100 run (gridded subset, no per-tree table, no stand leaf area);
      output/ = a SECOND run of 2071-2100 restarted from the first's 2070 restart (all outputs + per-tree table).
      The two disagree from 2071 on (the original's own chaotic noise) -> `second` is a second-run yardstick.

Stages (data under DATA; nothing in $HOME):
  static            cells (grid.bin order), lat/lon -> 0.5 deg grid index, soil code, area, top-metre water capacity
                    `cap` (from the orderA global run's whc_nat, the only all-cell source -- these runs emit none)
  yearly <scen>     per cell-year structure (tree count per patch, biomass per tree, 4 trait medians), ALL cells,
                    from the converted per-tree table (explore_glob_convert.py member s1), block by block
  stand <scen>      per cell-year stand (stand leaf area, vegetation carbon, cover of 10 plant types + natural stand
                    fraction) and monthly fluxes (gpp npp transp evap interc runoff) from the gridded output;
                    futures also the `second` 2071-2100 realisation
"""

from __future__ import annotations

import os
import sys

if sys.argv[1:2] == ["run"]:  # one core per chunk: set BEFORE numpy loads its maths library (else ~200 threads each)
    for _v in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
        os.environ[_v] = "1"

import argparse  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402
import polars as pl  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "python", "src"))

SRC = "/p/projects/pbscience/billing/LPJmLFIT/global/GCM"
BG = "/p/projects/open/Jamir/esm_land_emulator_data/billing_global"
DATA = "/p/projects/open/Jamir/esm_land_emulator_data/global_emu"
SCENS = ("historical", "ssp126", "ssp245", "ssp370")
FUT = ("ssp126", "ssp245", "ssp370")
YH0, YH1, YF0, YF1, YW0 = 1985, 2014, 2015, 2100, 2071  # gridded hist / futures / per-tree future window
NCELL, NPATCH = 67420, 25
LAT0, LON0, RES = -55.75, -179.75, 0.5
WHC_NAT = "/p/tmp/jamirp/esm_land_daily/daily_2000_2019_global_c0_67419_seed1/output/whc_nat.nc"
SOIL_ORDERA_NC = "/p/projects/waldspektrum/priesner/clustering/global/soil_code_test.nc"
TRAITS = ["SLA", "Wooddens", "D95max", "minwscal"]
FLUX = {"gpp": ("mgpp", "GPP"), "npp": ("mnpp", "NPP"), "transp": ("mtransp", "transp"),
        "evap": ("mevap", "evap"), "interc": ("minterc", "interc"), "runoff": ("mrunoff", "runoff")}
V1 = "/p/projects/open/Jamir/esm_land_emulator_data/release/v1"
ISIMIP = "/p/projects/lpjml/input/scenarios/ISIMIP3bv2"
STAND = ["lai_stand", "vegc"] + [f"fpc{p}" for p in range(0, 11)]  # fpc0 = natural stand fraction


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def run_dir(scen: str) -> str:
    return f"{SRC}/{scen}/GFDL-ESM4/r1_1"


def cells() -> pl.DataFrame:
    return pl.read_parquet(os.path.join(DATA, "static.parquet"))


def axis_index(axis, x):
    """Index of each x on a 1-D coordinate axis (either direction), asserting an exact grid match."""
    axis = np.asarray(axis, np.float64)
    o = np.argsort(axis)
    k = o[np.clip(np.searchsorted(axis[o], x), 0, len(axis) - 1)]
    k2 = o[np.clip(np.searchsorted(axis[o], x) - 1, 0, len(axis) - 1)]
    k = np.where(np.abs(axis[k2] - x) < np.abs(axis[k] - x), k2, k)
    assert np.abs(axis[k] - x).max() < 1e-3, "cell not on the field's grid"
    return k


def grid_index(lat, lon):
    il = np.rint((np.asarray(lat) - LAT0) / RES).astype(np.int64)
    io = np.rint((np.asarray(lon) - LON0) / RES).astype(np.int64)
    assert np.abs(LAT0 + il * RES - lat).max() < 1e-3 and np.abs(LON0 + io * RES - lon).max() < 1e-3
    return il, io


# ------------------------------------------------------------------------------------------------ static
def stage_static(_a) -> None:
    import netCDF4 as nc

    st = pl.read_parquet(os.path.join(BG, "climate", "cell_static.parquet")).sort("Cell")
    assert st["Cell"].to_list() == list(range(NCELL))
    lat, lon = st["lat"].to_numpy(), st["lon"].to_numpy()
    il, io = grid_index(lat, lon)
    # the runs' own grid.nc must place every cell where grid.bin does
    g = nc.Dataset(os.path.join(run_dir("historical"), "output", "grid.nc"))
    glat, glon = np.asarray(g["lat"][:]), np.asarray(g["lon"][:])
    assert np.abs(glat[il] - lat).max() < 1e-3 and np.abs(glon[io] - lon).max() < 1e-3
    # top-metre plant-available capacity, as f2_build_daily_table.cap_of: sum_{l<3} whc_nat[l] * thickness[l] (mm),
    # here the 2000-2019 mean of the orderA global run (a lat/lon field, so no cell-order remap is involved)
    w = nc.Dataset(WHC_NAT)
    bnds = np.asarray(w["depth_bnds"][:3])
    dz = (bnds[:, 1] - bnds[:, 0]) * 1000.0
    assert np.allclose(dz, [200.0, 300.0, 500.0]), dz
    whc = np.asarray(w["whc_nat"][:, :3].filled(np.nan), np.float64).mean(0)  # (3, nlat, nlon)
    wl, wo = axis_index(w["lat"][:], lat), axis_index(w["lon"][:], lon)
    cap = (whc[:, wl, wo] * dz[:, None]).sum(0)
    s = nc.Dataset(SOIL_ORDERA_NC)
    sa = np.asarray(s["soil_code"][:])[axis_index(s["latitude"][:], lat), axis_index(s["longitude"][:], lon)]
    rock = st["rock"].to_numpy()
    sc = st["soil_code"].to_numpy()
    agree = float((sa[~rock] == sc[~rock]).mean())
    fill = ~rock & ~np.isfinite(cap)
    if fill.any():  # cells the orderA run did not simulate: the median capacity of the same soil code
        med = {k: np.nanmedian(cap[(sc == k) & np.isfinite(cap)]) for k in np.unique(sc[fill])}
        cap[fill] = [med[k] for k in sc[fill]]
    out = st.with_columns(pl.Series("ilat", il.astype(np.int32)), pl.Series("ilon", io.astype(np.int32)),
                          pl.Series("cap", cap), pl.Series("soil_orderA", np.asarray(sa, np.int16)))
    os.makedirs(DATA, exist_ok=True)
    out.write_parquet(os.path.join(DATA, "static.parquet"))
    log(f"static: {out.height} cells, rock {int(rock.sum())}; soil code == orderA map at the same lat/lon on "
        f"{agree:.4f} of non-rock cells; cap filled from soil-code median on {int(fill.sum())} cells; "
        f"cap (mm) p5/p50/p95 = {np.percentile(cap[~rock], [5, 50, 95]).round(1)}")


# ------------------------------------------------------------------------------------------------ yearly structure
def stage_yearly(a) -> None:
    import explore_de_reference as R

    scen = a.scen
    win = "h1985" if scen == "historical" else "w2071"
    y0, y1 = (YH0, YH1) if scen == "historical" else (YW0, YF1)
    root = f"{BG}/ind/GFDL-ESM4/{scen}/s1/{win}"
    out = os.path.join(DATA, "yearly", f"{scen}.parquet")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    st = cells().filter(~pl.col("rock"))
    parts = []
    t0 = time.time()
    for cb in sorted((d for d in os.listdir(root) if d.startswith("cb=")), key=lambda d: int(d[3:])):
        lf = (pl.scan_parquet(os.path.join(root, cb, "*.parquet"))
              .filter(pl.col("Year").is_between(y0, y1))
              .select(pl.col("Year").cast(pl.Int32), pl.col("Cell").cast(pl.Int32), pl.col("Type").cast(pl.Int8),
                      pl.col("isdead").cast(pl.Int8), pl.col("Height").cast(pl.Float64),
                      pl.col("agb").cast(pl.Float64), *[pl.col(v).cast(pl.Float64) for v in TRAITS]))
        g = R.living(lf).group_by(["Cell", "Year"]).agg(
            [pl.len().alias("n_living"), pl.col("agb").sum().alias("agb_sum")]
            + [pl.col(v).median().alias(f"{v}_p50") for v in TRAITS]).collect()
        parts.append(g)
    g = pl.concat(parts)
    assert g.select("Cell", "Year").n_unique() == g.height, "duplicate (Cell, Year)"
    cs = st["Cell"].to_numpy()
    census = pl.DataFrame({"Cell": np.repeat(cs, y1 - y0 + 1).astype(np.int32),
                           "Year": np.tile(np.arange(y0, y1 + 1), len(cs)).astype(np.int32)})
    extra = g.join(census, on=["Cell", "Year"], how="anti").height
    assert extra == 0, f"{extra} rows outside the non-rock census"
    d = census.join(g, on=["Cell", "Year"], how="left").with_columns(
        pl.col("n_living").fill_null(0), pl.col("agb_sum").fill_null(0.0))
    d = d.with_columns((pl.col("n_living") / NPATCH).alias("n_per_patch"),
                       pl.when(pl.col("n_living") > 0).then(pl.col("agb_sum") / pl.col("n_living"))
                       .otherwise(None).alias("agb_per_stem"))
    d.sort("Cell", "Year").write_parquet(out)
    log(f"yearly {scen}: {d.height} rows, {g.height} with trees, cells with trees "
        f"{d.filter(pl.col('n_living') > 0)['Cell'].n_unique()} ({time.time() - t0:.0f}s)")


# ------------------------------------------------------------------------------------------------ stand + fluxes
def read_cells(path, var, il, io, band=None):
    """(T, N) (or (T, B, N)) values of an LPJmL lat/lon NetCDF at the cells; fill -> NaN."""
    import netCDF4 as nc

    d = nc.Dataset(path)
    v = d[var]
    v.set_auto_mask(False)
    x = np.asarray(v[:], np.float32)
    x = x[..., il, io]
    fv = getattr(v, "_FillValue", None)
    if fv is not None:
        x[x == np.float32(fv)] = np.nan
    t = d["time"]
    return x, int(str(t.units).split("since ")[1][:4])


def stand_table(odir, years, il, io, cellv, with_lai=True) -> pl.DataFrame:
    vegc, fy = read_cells(os.path.join(odir, "vegc.nc"), "VegC", il, io)
    assert fy == years[0] and vegc.shape[0] == len(years), (odir, fy, vegc.shape)
    fpc, _ = read_cells(os.path.join(odir, "fpc.nc"), "FPC", il, io)
    assert fpc.shape[:2] == (len(years), 11)
    cols = {"Cell": np.tile(cellv, len(years)).astype(np.int32),
            "Year": np.repeat(np.asarray(years), len(cellv)).astype(np.int32), "vegc": vegc.reshape(-1)}
    if with_lai:
        lai, _ = read_cells(os.path.join(odir, "lai.nc"), "LAI", il, io)
        cols["lai_stand"] = lai.reshape(-1)
    else:
        cols["lai_stand"] = np.full(len(years) * len(cellv), np.nan, np.float32)
    for p in range(11):
        cols[f"fpc{p}"] = fpc[:, p].reshape(-1)
    return pl.DataFrame(cols).select("Cell", "Year", *STAND)


def flux_arrays(odir, years, il, io) -> dict:
    out = {}
    for k, (f, v) in FLUX.items():
        x, fy = read_cells(os.path.join(odir, f"{f}.nc"), v, il, io)
        assert fy == years[0] and x.shape[0] == 12 * len(years), (f, fy, x.shape)
        out[k] = np.ascontiguousarray(x.reshape(len(years), 12, -1).transpose(2, 0, 1))  # (N, Y, 12)
    return out


def stage_stand(a) -> None:
    scen = a.scen
    st = cells()
    il, io, cv = st["ilat"].to_numpy(), st["ilon"].to_numpy(), st["Cell"].to_numpy()
    od = os.path.join(DATA, "orig", scen)
    os.makedirs(od, exist_ok=True)
    t0 = time.time()
    if scen == "historical":
        yrs = list(range(YH0, YH1 + 1))
        stand_table(os.path.join(run_dir(scen), "output"), yrs, il, io, cv).write_parquet(f"{od}/stand.parquet")
        fl = flux_arrays(os.path.join(run_dir(scen), "output"), yrs, il, io)
        for k, x in fl.items():
            np.save(f"{od}/{k}_{YH0}_{YH1}.npy", x)
    else:
        tr = os.path.join(run_dir(scen), "output_transient")
        yt = list(range(YF0, YF1 + 1))
        s_tr = stand_table(tr, yt, il, io, cv, with_lai=False)
        yw = list(range(YW0, YF1 + 1))
        s_w = stand_table(os.path.join(run_dir(scen), "output"), yw, il, io, cv)
        # main realisation: continuous run 2015-2070 + the per-tree-table run 2071-2100 (what the structure targets
        # come from); `second`: the continuous run's own 2071-2100
        pl.concat([s_tr.filter(pl.col("Year") < YW0), s_w]).write_parquet(f"{od}/stand.parquet")
        s_tr.filter(pl.col("Year") >= YW0).write_parquet(f"{od}/stand_second.parquet")
        for k, x in flux_arrays(tr, yt, il, io).items():
            np.save(f"{od}/{k}_{YF0}_{YF1}_transient.npy", x)
        for k, x in flux_arrays(os.path.join(run_dir(scen), "output"), yw, il, io).items():
            np.save(f"{od}/{k}_{YW0}_{YF1}.npy", x)
    log(f"stand/fluxes {scen} written to {od} ({time.time() - t0:.0f}s)")


# --------------------------------------------------------------------------------------- training (ADR 0341 sec. 3)
def clim_cols():
    from lpjmlfit_emulator.landemu.climate import CLIM_COLS

    return list(CLIM_COLS)


def struct_q():
    from lpjmlfit_emulator.landemu.annual import STRUCT_Q

    return list(STRUCT_Q)


def stand_q():
    from lpjmlfit_emulator.landemu.annual import STAND_Q

    return list(STAND_Q)


def feats_struct() -> list[str]:
    c = clim_cols()
    return c + [f"dclim_{x}" for x in c] + [f"anc_{q}" for q in struct_q()] + ["lat", "lon", "soil_code"]


def feats_stand() -> list[str]:
    return feats_struct() + [f"anc_{q}" for q in stand_q()]


def cell_year(scen: str) -> pl.DataFrame:
    c = clim_cols()
    return (pl.read_parquet(os.path.join(BG, "climate", "cell_year", f"GFDL-ESM4_{scen}.parquet"),
                            columns=["Cell", "Year", *c])
            .with_columns(pl.col("Cell").cast(pl.Int32), pl.col("Year").cast(pl.Int32),
                          *[pl.col(x).cast(pl.Float64) for x in c]))


def window_climate(scen: str) -> pl.DataFrame:
    """Trailing 30-yr means (>= 20 years, as the release's TrailingWindow and explore_panel_yearly_drift)."""
    c = clim_cols()
    d = cell_year("historical")
    if scen != "historical":
        d = pl.concat([d, cell_year(scen)])
    d = d.sort("Cell", "Year")
    assert d.group_by("Cell").agg(pl.col("Year").diff().max())["Year"].max() == 1, f"{scen}: gap in years"
    return d.with_columns([pl.col(x).rolling_mean(window_size=30, min_samples=20).over("Cell") for x in c])


def anchors() -> pl.DataFrame:
    """Per cell: the original's 1985-2014 mean of every structure and stand quantity (ADR 0341 sec. 3)."""
    y = pl.read_parquet(os.path.join(DATA, "yearly", "historical.parquet"))
    sd = pl.read_parquet(os.path.join(DATA, "orig", "historical", "stand.parquet"))
    a = y.group_by("Cell").agg([pl.col(q).mean().alias(f"anc_{q}") for q in struct_q()])
    b = sd.group_by("Cell").agg([pl.col(q).cast(pl.Float64).mean().alias(f"anc_{q}") for q in stand_q()])
    return a.join(b, on="Cell", how="full", coalesce=True)


def anchor_climate() -> pl.DataFrame:
    c = clim_cols()
    return window_climate("historical").filter(pl.col("Year") == YH1).select(
        "Cell", *[pl.col(x).alias(f"aclim_{x}") for x in c])


def leg_rows(scen: str, struct_years: list[int], stand_years: list[int]) -> pl.DataFrame:
    yrs = sorted(set(struct_years) | set(stand_years))
    y = pl.read_parquet(os.path.join(DATA, "yearly", f"{scen}.parquet")).select("Cell", "Year", *struct_q())
    y = y.filter(pl.col("Year").is_in(struct_years))
    sd = pl.read_parquet(os.path.join(DATA, "orig", scen, "stand.parquet")).filter(pl.col("Year").is_in(stand_years))
    sd = sd.select("Cell", "Year", *[pl.col(q).cast(pl.Float64) for q in stand_q()])
    nr = cells().filter(~pl.col("rock")).select(pl.col("Cell").cast(pl.Int32))
    base = nr.join(pl.DataFrame({"Year": np.asarray(yrs, np.int32)}), how="cross")
    d = base.join(y, on=["Cell", "Year"], how="left").join(sd, on=["Cell", "Year"], how="left")
    w = window_climate(scen).filter(pl.col("Year").is_in(yrs))
    return d.join(w, on=["Cell", "Year"], how="left").with_columns(pl.lit(scen).alias("leg"))


def training_table(fold: str) -> pl.DataFrame:
    legs = [s for s in SCENS if s != fold]
    parts = []
    for s in legs:
        if s == "historical":
            parts.append(leg_rows(s, list(range(YH0, YH1 + 1, 2)), list(range(YH0, YH1 + 1, 2))))
        else:
            parts.append(leg_rows(s, list(range(YW0, YF1 + 1, 2)), list(range(YF0, YF1 + 1, 3))))
    d = pl.concat(parts)
    st = cells().select(pl.col("Cell").cast(pl.Int32), "lat", "lon", pl.col("soil_code").cast(pl.Float64))
    d = d.join(anchors(), on="Cell", how="left").join(anchor_climate(), on="Cell", how="left").join(st, on="Cell")
    d = d.with_columns([(pl.col(x) - pl.col(f"aclim_{x}")).alias(f"dclim_{x}") for x in clim_cols()])
    return d.drop([f"aclim_{x}" for x in clim_cols()])


def stage_train(a) -> None:
    import shutil

    import explore_glob_climate as GC
    import explore_panel_a7 as A7
    import lightgbm as lgb

    fold = a.fold
    out = os.path.join(DATA, "release", f"fold_{fold}")
    if os.path.exists(os.path.join(out, "release.json")):
        sys.exit(f"{out} already holds a release; never overwrite one in place")
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    tr = training_table(fold)
    log(f"fold {fold}: {tr.height} rows, legs {tr['leg'].unique().sort().to_list()} ({time.time() - t0:.0f}s)")
    params = dict(A7.PARAMS, num_threads=int(os.environ.get("SLURM_CPUS_PER_TASK", "16")))
    fs, fx = feats_struct(), feats_stand()
    log_eps = {"agb_per_stem": 1.0}  # as release v1 (explore_panel_yearly_drift.LOG_EPS)
    nrows = {}
    for q in struct_q() + stand_q():
        f = fs if q in struct_q() else fx
        t = tr.filter(pl.col(q).is_not_null() & pl.col(q).is_not_nan() & pl.col(f"anc_{q}").is_not_null()
                      & pl.col(f"anc_{q}").is_not_nan())
        if q in log_eps:
            e = log_eps[q]
            y = np.log((t[q].to_numpy() + e) / (t[f"anc_{q}"].to_numpy() + e))
        else:
            y = (t[q] - t[f"anc_{q}"]).to_numpy()
        m = lgb.train(params, lgb.Dataset(t.select(f).to_numpy(), y), A7.ROUNDS)
        m.save_model(os.path.join(out, f"lgb_{q}.txt"))
        nrows[q] = t.height
        log(f"  fitted {q} on {t.height} rows ({time.time() - t0:.0f}s)")
    with open(os.path.join(out, "annual.json"), "w") as fh:
        json.dump({"features_structure": fs, "features_stand": fx, "log_eps": log_eps, "cover_mode": "additive",
                   "cover_totals": {}}, fh, indent=1)
    shutil.copy(os.path.join(V1, "daily.npz"), os.path.join(out, "daily.npz"))
    prm = GC.pft_temp_params()
    cfg = {"version": f"global_fold_{fold}", "git_sha": git_sha(), "built": time.strftime("%Y-%m-%d %H:%M"),
           "kind": "deployment" if fold == "none" else "fold", "hold_scenario": None if fold == "none" else fold,
           "train_legs": [s for s in SCENS if s != fold], "anchor": "own 1985-2014 state (ADR 0341 sec. 3)",
           "daily_model": "release v1 daily.npz, not retrained (ADR 0341 sec. 2)", "rows": nrows,
           "pft_temp_stress": {"low": prm["temp_low"].to_list(), "high": prm["temp_high"].to_list()}}
    with open(os.path.join(out, "release.json"), "w") as fh:
        json.dump(cfg, fh, indent=1)
    log(f"release written to {out} ({time.time() - t0:.0f}s)")


def git_sha():
    import subprocess

    try:
        return subprocess.check_output(["git", "-C", REPO, "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


# ------------------------------------------------------------------------------------------------ global run (sec. 4)
FORC_VARS = ("tas", "pr", "rsds", "lwnet", "huss")  # the package's forcing order
CLM = {"historical": ISIMIP + "/historical/GFDL-ESM4/{v}_gfdl-esm4_historical_1850-2014.clm",
       **{s: ISIMIP + f"/{s}/GFDL-ESM4/{{v}}_gfdl-esm4_{s}_2015-2100.clm" for s in FUT}}
RUN_YEARS = {"historical": (1975, YH1), **{s: (YF0, YF1) for s in FUT}}
FOLD_OF = {"historical": "none", **{s: s for s in FUT}}  # each future leg by the fold that never saw it
MONTH_BOUNDS = np.concatenate([[0], np.cumsum([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])])
MFLUX = ["gpp", "npp", "interc", "transp", "evap", "runoff"]  # monthly sums
MSTATE = ["swe", "soilw", "deep"]  # monthly means


class Forcing:
    """Daily weather of a contiguous cell range from the runs' own .clm files, float64 physical units."""

    def __init__(self, scen, c0, c1, keep):
        from build_transient_boundary import open_clm

        self.c0, self.c1, self.keep = c0, c1, keep
        self.src = {}
        for leg in ("historical", scen):
            self.src[leg] = [open_clm(CLM[leg].format(v=v)) for v in FORC_VARS]

    def year(self, y) -> np.ndarray:
        leg = "historical" if y <= YH1 else [k for k in self.src if k != "historical"][0]
        out = []
        for mm, fy, ncell, nb, sc in self.src[leg]:
            assert ncell == NCELL and nb == 365
            out.append(np.asarray(mm[y - fy, self.c0:self.c1], np.float64)[self.keep] * sc)
        return np.stack(out, -1)  # (n, 365, 5)


def chunk_cells(k, nchunk):
    st = cells()
    edges = np.linspace(0, NCELL, nchunk + 1).astype(int)
    c0, c1 = int(edges[k]), int(edges[k + 1])
    sub = st.filter(pl.col("Cell").is_between(c0, c1 - 1)).sort("Cell")
    keep = ~sub["rock"].to_numpy()
    return c0, c1, keep, sub.filter(~pl.col("rock"))


def make_setup(scen, k, nchunk, emu_start=None):
    from lpjmlfit_emulator.landemu import Setup

    c0, c1, keep, sub = chunk_cells(k, nchunk)
    cv = sub["Cell"].to_numpy().astype(np.int32)
    n = len(cv)
    y0, y1 = RUN_YEARS[scen]
    ny = y1 - y0 + 1
    key = pl.DataFrame({"Cell": cv})
    P = os.path.join(DATA, "setup")
    ancm = np.load(os.path.join(P, "anchors.npy"), mmap_mode="r")
    qorder = json.load(open(os.path.join(P, "anchors.json")))
    anc = {q: np.asarray(ancm[cv, j], np.float64) for j, q in enumerate(qorder)}
    acl = np.asarray(np.load(os.path.join(P, "aclim.npy"), mmap_mode="r")[cv], np.float64)
    ch = np.load(os.path.join(P, "clim_hist.npy"), mmap_mode="r")  # (years 1951-2014, NCELL, 25)
    hy = range(1951, y0) if scen == "historical" else range(YH0, YH1 + 1)
    H = np.stack([np.asarray(ch[y - 1951, cv], np.float64) for y in hy])
    f = Forcing(scen, c0, c1, keep)
    qs = struct_q() + stand_q()
    if emu_start is None:  # historical: the original's 1985 stand, empty stores, 10 warm-up years
        sd = pl.read_parquet(os.path.join(DATA, "orig", "historical", "stand.parquet")).filter(pl.col("Year") == YH0)
        stand0 = key.join(sd, on="Cell", how="left").select(stand_q()).to_numpy().astype(np.float64)
        stand0 = np.nan_to_num(stand0)
        cap = sub["cap"].to_numpy()
        W0, S0, D0 = 0.5 * cap, np.zeros(n), np.zeros(n)
    else:  # a future leg continues the emulated historical run's end-of-2014 state
        z = np.load(emu_start)
        assert np.array_equal(z["cell"], cv)
        stand0, W0, S0, D0 = z["stand_raw"], z["W"], z["S"], z["D"]
    su = Setup(cell=cv, lat=sub["lat"].to_numpy(), lon=sub["lon"].to_numpy(),
               soil_code=sub["soil_code"].to_numpy().astype(np.float64), year0=y0,
               anc={q: np.repeat(anc[q][:, None], ny, 1) for q in qs},
               aclim=np.repeat(acl[:, None, :], ny, 1), s0={q: np.zeros(n) for q in qs},
               memoff={q: np.zeros(n) for q in qs}, clim_hist=H, cap=sub["cap"].to_numpy(),
               W0=W0, S0=S0, D0=D0, stand0=stand0, warm=f.year(y0 - 1).astype(np.float32))
    return su, f


def stage_prep(_a) -> None:
    """Per-cell anchors, anchor climate and the 1951-2014 yearly climate as arrays indexed by Cell (each run
    chunk reads its slice instead of rebuilding the tables)."""
    P = os.path.join(DATA, "setup")
    os.makedirs(P, exist_ok=True)
    qs = struct_q() + stand_q()
    key = pl.DataFrame({"Cell": np.arange(NCELL, dtype=np.int32)})
    a = key.join(anchors(), on="Cell", how="left")
    np.save(os.path.join(P, "anchors.npy"), a.select([f"anc_{q}" for q in qs]).to_numpy().astype(np.float64))
    json.dump(qs, open(os.path.join(P, "anchors.json"), "w"))
    c = clim_cols()
    ac = key.join(anchor_climate(), on="Cell", how="left").select([f"aclim_{x}" for x in c]).to_numpy()
    np.save(os.path.join(P, "aclim.npy"), ac.astype(np.float64))
    cy = cell_year("historical").sort("Year", "Cell")
    assert cy.height == NCELL * (YH1 - 1951 + 1) and cy["Year"].min() == 1951
    np.save(os.path.join(P, "clim_hist.npy"), cy.select(c).to_numpy().reshape(YH1 - 1951 + 1, NCELL, len(c)))
    log(f"setup arrays -> {P}: anchors finite {np.isfinite(a['anc_n_per_patch'].to_numpy()).mean():.3f}, "
        f"aclim finite {np.isfinite(ac).all(1).mean():.3f}")


def stage_run(a) -> None:
    scen, k, nchunk = a.scen, a.chunk, a.nchunk
    od = os.path.join(DATA, "emu", scen, "chunks")
    os.makedirs(od, exist_ok=True)
    out = os.path.join(od, f"c{k:03d}.npz")
    if os.path.exists(out):
        log(f"{out} exists, skipped")
        return
    from lpjmlfit_emulator.landemu import LandEmulator

    emu = LandEmulator.load(os.path.join(DATA, "release", f"fold_{FOLD_OF[scen]}"))
    start = None if scen == "historical" else os.path.join(DATA, "emu", "historical", "chunks", f"c{k:03d}_end.npz")
    t0 = time.time()
    su, f = make_setup(scen, k, nchunk, start)
    n = len(su.cell)
    y0, y1 = RUN_YEARS[scen]
    st = emu.start(su)
    ny = y1 - y0 + 1
    M = {v: np.zeros((n, ny, 12), np.float32) for v in MFLUX + MSTATE}
    A = {}
    gate = None
    t1 = time.time()
    for i, y in enumerate(range(y0, y1 + 1)):
        forc = f.year(y)
        if i == 0:  # GATE: the package's yearly climate == the training table's row for this cell-year
            got = st["clim"](forc[:, :, 0], forc[:, :, 1], forc[:, :, 4], forc[:, :, 2], forc[:, :, 3])
            src = "historical" if y <= YH1 else scen
            ref = (pl.DataFrame({"Cell": su.cell}).join(cell_year(src).filter(pl.col("Year") == y), on="Cell",
                                                         how="left").select(clim_cols()).to_numpy())
            gate = float(np.nanmax(np.abs(got - ref) / np.maximum(np.abs(ref), 1.0)))
            assert gate < 1e-5, f"package climate differs from the training table by {gate}"
        daily, ann = emu.step_year(st, forc)
        for v in MFLUX:
            M[v][:, i] = np.add.reduceat(daily[v], MONTH_BOUNDS[:-1], axis=1)
        for v in MSTATE:
            M[v][:, i] = np.add.reduceat(daily[v], MONTH_BOUNDS[:-1], axis=1) / np.diff(MONTH_BOUNDS)
        for q, x in ann.items():
            A.setdefault(q, np.zeros((n, ny), np.float32))[:, i] = x
    sec = time.time() - t1
    np.savez(out, cell=su.cell, years=np.arange(y0, y1 + 1), **{f"m_{v}": x for v, x in M.items()},
             **{f"a_{q}": x for q, x in A.items()}, seconds=sec, gate_clim=gate)
    if scen == "historical":
        ds, s = st["daily"], np.asarray(st["stand"], np.float64).copy()
        s[:, 1] = np.expm1(s[:, 1])  # back from the daily model's log1p vegetation carbon
        np.savez(os.path.join(od, f"c{k:03d}_end.npz"), cell=su.cell, W=ds.W, S=ds.S, D=ds.D, stand_raw=s)
    log(f"{scen} chunk {k}/{nchunk}: {n} cells x {ny} years, {sec:.0f}s run "
        f"({sec / (n * ny):.2e} core-s per cell-year), setup {t1 - t0:.0f}s, climate gate {gate:.1e}")


def stage_runall(a) -> None:
    """All chunks of one leg on the job's cpus (one process per chunk)."""
    import subprocess
    from concurrent.futures import ThreadPoolExecutor

    ncpu = int(os.environ.get("SLURM_CPUS_PER_TASK", "8"))
    py = sys.executable

    def one(k):
        env = dict(os.environ, OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", OMP_NUM_THREADS="1",
                   POLARS_MAX_THREADS="1")
        r = subprocess.run([py, os.path.abspath(__file__), "run", "--scen", a.scen, "--chunk", str(k),
                            "--nchunk", str(a.nchunk)], capture_output=True, text=True, env=env)
        print(r.stdout.strip()[-400:], r.stderr.strip()[-2000:] if r.returncode else "", flush=True)
        return r.returncode

    with ThreadPoolExecutor(ncpu) as ex:
        codes = list(ex.map(one, range(a.nchunk)))
    bad = [k for k, c in enumerate(codes) if c]
    log(f"{a.scen}: {a.nchunk - len(bad)} of {a.nchunk} chunks ok; failed {bad}")
    if bad:
        sys.exit(1)


# ------------------------------------------------------------------------------------------------ benchmark layout
BENCH = os.path.join(DATA, "bench")
# the lpjml-fit converter (scripts/benchmark/prepare_benchmark.py, source `chunks:<dir>`) reads
# <dir>/chunk_*/output/<fitname>_<phase>.nc -- one "chunk" holding the whole grid
NC_OUT = {"mgpp": ("GPP", "gC/m2/month", "gpp"), "mnpp": ("NPP", "gC/m2/month", "npp"),
          "mtransp": ("transp", "mm/month", "transp"), "mevap": ("evap", "mm/month", "evap"),
          "minterc": ("interc", "mm/month", "interc"), "mrunoff": ("runoff", "mm/month", "runoff")}
LINK_ORIG = ["mgpp", "mnpp", "mtransp", "mevap", "minterc", "mrunoff", "vegc", "lai", "fpc"]


def write_nc(path, var, data, firstyear, nstep, unit, lat_axis, lon_axis, st):
    """data (T, N) or (T, B, N) on the static cells -> LPJmL-style (time, [band,] lat, lon) NetCDF, noleap."""
    import netCDF4 as nc

    il, io = st["ilat"].to_numpy(), st["ilon"].to_numpy()
    nt = data.shape[0]
    ds = nc.Dataset(path, "w", format="NETCDF4")
    ds.createDimension("time", nt)
    ds.createDimension("lat", len(lat_axis))
    ds.createDimension("lon", len(lon_axis))
    ds.createDimension("bnds", 2)
    dpm = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31], float)
    if nstep == 12:
        ends = np.cumsum(np.tile(dpm, nt // 12))
        starts = ends - np.tile(dpm, nt // 12)
    else:
        starts = np.arange(nt) * 365.0
        ends = starts + 365.0
    t = ds.createVariable("time", "f8", ("time",))
    t.units, t.calendar, t.bounds = f"days since {firstyear}-1-1 0:0:0", "noleap", "time_bnds"
    t[:] = (starts + ends) / 2 - 0.5
    ds.createVariable("time_bnds", "f8", ("time", "bnds"))[:] = np.stack([starts, ends], 1)
    for nm, ax, u in (("lat", lat_axis, "degrees_north"), ("lon", lon_axis, "degrees_east")):
        v = ds.createVariable(nm, "f8", (nm,))
        v.units = u
        v[:] = ax
    dims = ("time", "lat", "lon") if data.ndim == 2 else ("time", "npft", "lat", "lon")
    if data.ndim == 3:
        ds.createDimension("npft", data.shape[1])
    shp = (nt, len(lat_axis), len(lon_axis)) if data.ndim == 2 else (nt, data.shape[1], len(lat_axis), len(lon_axis))
    # one compressed HDF5 chunk per time step, whole array written once (slab-by-slab writes into the default
    # multi-step chunks rewrote ~60x the file size, 3 min per variable)
    v = ds.createVariable(var, "f4", dims, fill_value=np.float32(-1e32), zlib=True, complevel=1,
                          chunksizes=(1, *shp[1:]))
    v.units = unit
    v.long_name = f"{var} (learned emulator, ADR 0341)"
    f = np.full(shp, np.float32(-1e32), np.float32)
    f[..., il, io] = np.nan_to_num(np.asarray(data, np.float32), nan=-1e32)
    v[:] = f
    ds.close()


def stage_assemble(a) -> None:
    """Emulator chunks of one leg -> full-grid arrays + LPJmL-style NetCDF under bench/models/Emu."""
    import netCDF4 as nc

    scen = a.scen
    st = cells()
    nr = st.filter(~pl.col("rock"))
    files = sorted(f for f in os.listdir(os.path.join(DATA, "emu", scen, "chunks")) if f.endswith(".npz")
                   and not f.endswith("_end.npz"))
    assert len(files) == a.nchunk, f"{scen}: {len(files)} chunks of {a.nchunk}"
    zs = [np.load(os.path.join(DATA, "emu", scen, "chunks", f)) for f in files]
    cell = np.concatenate([z["cell"] for z in zs])
    assert np.array_equal(cell, nr["Cell"].to_numpy()), "chunks do not cover the non-rock cells exactly once"
    years = zs[0]["years"]
    keep = years >= (YH0 if scen == "historical" else YF0)  # drop the historical warm-up years
    years = years[keep]
    pos = cell  # Cell == row of `st` (sorted 0..NCELL-1)
    full_m, full_a = {}, {}
    for v in MFLUX + MSTATE:
        x = np.zeros((NCELL, len(years), 12), np.float32)  # rock cells: 0, as the original writes them
        x[pos] = np.concatenate([z[f"m_{v}"] for z in zs])[:, keep]
        full_m[v] = x
    for q in struct_q() + stand_q():
        x = np.full((NCELL, len(years)), np.nan, np.float32)
        x[pos] = np.concatenate([z[f"a_{q}"] for z in zs])[:, keep]
        full_a[q] = x
    sec = sum(float(z["seconds"]) for z in zs)
    ncy = sum(len(z["cell"]) * len(z["years"]) for z in zs)
    gate = max(float(z["gate_clim"]) for z in zs)
    od = os.path.join(DATA, "emu", scen)
    np.savez(os.path.join(od, "monthly.npz"), years=years, **full_m)
    np.savez(os.path.join(od, "annual.npz"), years=years, **full_a)
    # NetCDF in the original's layout
    ref = nc.Dataset(os.path.join(run_dir(scen), "output", "vegc.nc"))
    lat_axis, lon_axis = np.asarray(ref["lat"][:]), np.asarray(ref["lon"][:])
    out = os.path.join(BENCH, "models", "Emu", "chunk_0", "output")
    os.makedirs(out, exist_ok=True)
    y0 = int(years[0])
    for fit, (var, unit, key) in NC_OUT.items():
        d = full_m[key].transpose(1, 2, 0).reshape(-1, NCELL)  # (Y*12, N)
        write_nc(os.path.join(out, f"{fit}_{scen}.nc"), var, d, y0, 12, unit, lat_axis, lon_axis, st)
    rockless = lambda x: np.where(st["rock"].to_numpy()[None, :], 0.0, np.nan_to_num(x.T))  # noqa: E731
    write_nc(os.path.join(out, f"vegc_{scen}.nc"), "VegC", rockless(full_a["vegc"]), y0, 1, "gC/m2",
             lat_axis, lon_axis, st)
    write_nc(os.path.join(out, f"lai_{scen}.nc"), "LAI", rockless(full_a["lai_stand"]), y0, 1, "",
             lat_axis, lon_axis, st)
    fpc = np.stack([np.ones((len(years), NCELL))] + [rockless(full_a[f"fpc{p}"]) for p in range(1, 11)], 1)
    write_nc(os.path.join(out, f"fpc_{scen}.nc"), "FPC", fpc, y0, 1, "", lat_axis, lon_axis, st)
    log(f"assembled {scen}: {len(years)} years {y0}-{years[-1]}, {len(cell)} cells; run {sec:.0f} core-s = "
        f"{sec / ncy:.2e} core-s per cell-year; climate gate max {gate:.1e}; NetCDF -> {out}")


def stage_layout(_a) -> None:
    """The original's files linked into the same layout: FIT (benchmark truth: historical output/ 1985-2014,
    futures output/ 2071-2100) and FIT2 (futures output_transient/, the second 2071-2100 realisation)."""
    for model, sub, scens in (("FIT", "output", SCENS), ("FIT2", "output_transient", FUT)):
        out = os.path.join(BENCH, "models", model, "chunk_0", "output")
        os.makedirs(out, exist_ok=True)
        for scen in scens:
            for fit in LINK_ORIG:
                src = os.path.join(run_dir(scen), sub, f"{fit}.nc")
                dst = os.path.join(out, f"{fit}_{scen}.nc")
                if os.path.exists(src) and not os.path.lexists(dst):
                    os.symlink(src, dst)
        log(f"{model}: {len(os.listdir(out))} links in {out}")


# ------------------------------------------------------------------------------------------------ scores (sec. 5)
FLOOR = {"gpp": 50.0, "npp": 20.0, "et": 20.0, "runoff": 5.0, "vegc": 100.0, "lai_stand": 0.1, "fpc_tree": 0.05,
         "fpc_grass": 0.05, "n_per_patch": 0.04}  # truth below this: cell not scored for that quantity (relative error)


def orig_flux(scen, which):
    """{gpp,npp,et,runoff}: (N, Y) annual sums of the original. which: main | second | transient."""
    od = os.path.join(DATA, "orig", scen)
    tag = {"main": f"{YH0}_{YH1}" if scen == "historical" else f"{YW0}_{YF1}",
           "second": f"{YF0}_{YF1}_transient", "transient": f"{YF0}_{YF1}_transient"}[which]
    x = {k: np.load(os.path.join(od, f"{k}_{tag}.npy")).sum(2) for k in FLUX}
    if which == "second":
        x = {k: v[:, YW0 - YF0:] for k, v in x.items()}
    x["et"] = x["transp"] + x["evap"] + x["interc"]
    return x


def emu_flux(scen):
    z = np.load(os.path.join(DATA, "emu", scen, "monthly.npz"))
    x = {k: z[k].sum(2) for k in ("gpp", "npp", "transp", "evap", "interc", "runoff")}
    x["et"] = x["transp"] + x["evap"] + x["interc"]
    return z["years"], x


def stand_mat(df: pl.DataFrame, years, q) -> np.ndarray:
    """(N, Y) of a stand/structure quantity from a (Cell, Year) table; fpc_tree / fpc_grass = sums of types."""
    cols = {"fpc_tree": [f"fpc{p}" for p in range(1, 8)], "fpc_grass": ["fpc8", "fpc9", "fpc10"]}.get(q, [q])
    d = df.filter(pl.col("Year").is_in(list(years))).sort("Cell", "Year")
    v = d.select(pl.sum_horizontal([pl.col(c).cast(pl.Float64) for c in cols]) if len(cols) > 1
                 else pl.col(cols[0]).cast(pl.Float64)).to_series().to_numpy()
    out = np.full((NCELL, len(years)), np.nan)
    out[d["Cell"].to_numpy(), d["Year"].to_numpy() - years[0]] = v
    return out


def rel_stats(E, T, w, floor):
    ok = np.isfinite(E) & np.isfinite(T) & (np.abs(T) >= floor)
    r = np.abs(E[ok] - T[ok]) / np.abs(T[ok])
    tot = np.nansum(np.where(np.isfinite(E) & np.isfinite(T), E, 0) * w) / np.nansum(
        np.where(np.isfinite(E) & np.isfinite(T), T, 0) * w) - 1.0
    return (float(np.median(r)) if r.size else np.nan, float(np.percentile(r, 90)) if r.size else np.nan,
            float(tot), int(ok.sum()))


def stage_score(_a) -> None:
    st = cells()
    w = st["area_km2_approx"].to_numpy()
    anc = pl.DataFrame({"Cell": st["Cell"]}).join(anchors(), on="Cell", how="left")
    dense = anc["anc_n_per_patch"].to_numpy() >= 5.0
    sparse = (anc["anc_n_per_patch"].to_numpy() > 0) & ~dense
    rows = []
    for scen in SCENS:
        yrs, ef = emu_flux(scen)
        win = np.arange(YH0, YH1 + 1) if scen == "historical" else np.arange(YW0, YF1 + 1)
        sel = np.isin(yrs, win)
        tf = orig_flux(scen, "main")
        sf = None if scen == "historical" else orig_flux(scen, "second")
        ea = np.load(os.path.join(DATA, "emu", scen, "annual.npz"))
        tst = pl.read_parquet(os.path.join(DATA, "orig", scen, "stand.parquet"))
        sst = (None if scen == "historical"
               else pl.read_parquet(os.path.join(DATA, "orig", scen, "stand_second.parquet")))
        ty = pl.read_parquet(os.path.join(DATA, "yearly", f"{scen}.parquet"))
        hy = pl.read_parquet(os.path.join(DATA, "yearly", "historical.parquet"))
        hst = pl.read_parquet(os.path.join(DATA, "orig", "historical", "stand.parquet"))
        hwin = np.arange(YH0, YH1 + 1)
        htf = orig_flux("historical", "main")

        def add(q, E, T, S, Pn, group="all", mask=None, scen=scen):
            m = np.ones(NCELL, bool) if mask is None else mask
            fl = FLOOR.get(q, 0.0)
            em, e90, etot, n = rel_stats(np.where(m, E, np.nan), T, w, fl)
            row = dict(scen=scen, q=q, group=group, n_cells=n, emu_typ=em, emu_p90=e90, emu_total=etot)
            if S is not None:
                sm, s90, stot, _ = rel_stats(np.where(m, S, np.nan), T, w, fl)
                row.update(second_typ=sm, second_p90=s90, second_total=stot, ratio_typ=em / sm if sm else np.nan,
                           ratio_p90=e90 / s90 if s90 else np.nan)
            if Pn is not None:
                pm, p90, ptot, _ = rel_stats(np.where(m, Pn, np.nan), T, w, fl)
                row.update(persist_typ=pm, persist_p90=p90, persist_total=ptot)
            rows.append(row)

        for k in ("gpp", "npp", "et", "runoff"):
            E = ef[k][:, sel].mean(1)
            T = tf[k].mean(1)
            S = None if sf is None else sf[k].mean(1)
            Pn = None if scen == "historical" else htf[k].mean(1)
            add(k, E, T, S, Pn)
        for q in ("vegc", "lai_stand", "fpc_tree", "fpc_grass"):
            if q in ("fpc_tree", "fpc_grass"):
                cols = range(1, 8) if q == "fpc_tree" else range(8, 11)
                E = sum(ea[f"fpc{p}"][:, sel] for p in cols).mean(1)
            else:
                E = ea[q][:, sel].mean(1)
            T = np.nanmean(stand_mat(tst, win, q), 1)
            S = None if (sst is None or q == "lai_stand") else np.nanmean(stand_mat(sst, win, q), 1)
            Pn = None if scen == "historical" else np.nanmean(stand_mat(hst, hwin, q), 1)
            add(q, E, T, S, Pn)
        for q in struct_q():
            E = np.nanmean(ea[q][:, sel], 1)
            T = np.nanmean(stand_mat(ty, win, q), 1)
            Pn = None if scen == "historical" else np.nanmean(stand_mat(hy, hwin, q), 1)
            add(q, E, T, None, Pn, "dense", dense)
            add(q, E, T, None, Pn, "sparse", sparse)
    df = pl.DataFrame(rows)
    out = os.path.join(DATA, "eval")
    os.makedirs(out, exist_ok=True)
    df.write_csv(os.path.join(out, "scores.csv"))
    with pl.Config(tbl_rows=200, tbl_cols=20, tbl_width_chars=250, float_precision=3):
        print(df)
    log(f"scores -> {out}/scores.csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["static", "yearly", "stand", "train", "run", "runall", "assemble",
                                          "layout", "score", "prep"])
    ap.add_argument("--scen", choices=SCENS)
    ap.add_argument("--fold", choices=["none", *FUT])
    ap.add_argument("--chunk", type=int, default=0)
    ap.add_argument("--nchunk", type=int, default=64)
    a = ap.parse_args()
    {"static": stage_static, "yearly": stage_yearly, "stand": stage_stand, "train": stage_train, "run": stage_run,
     "runall": stage_runall, "assemble": stage_assemble, "layout": stage_layout,
     "score": stage_score, "prep": stage_prep}[a.stage](a)
    log("=== DONE")


if __name__ == "__main__":
    main()
