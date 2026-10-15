#!/usr/bin/env python3
"""clu_emu_maps.py -- the yearly STRUCTURE + STAND maps of the emulator trained on the nitrogen-on clustered runs
(transient CO2) and scored on their WARMING RESPONSE (ADR 0342). Runs: scripts/clu_emu_runs.sh.

Stages (data under OUT; the runs under RUNS):
  static              cells (model cell order = the grid's), lat/lon, soil code, region label, region land area
                      (the weight of the cell in a global total), held-out flag (every 5th region by label)
  climate             yearly climate statistics (the release package's YearClimate, 25 columns -- what the emulator
                      computes at run time) per forcing leg: hist 1961-2019 (GSWP3-W5E5), each GCM x SSP 2020-2100;
                      and the CO2 series per scenario (rising / fixed at 2019)
  targets <seed>      per cell-year structure (from the per-tree table: living trees >= 5 m, as every earlier
                      reduction) and stand (annual NetCDF) for the seed's hist run and every leg that exists
  train <arm>         `main`: 8 training climate models x {ssp126, ssp370, ssp585, ssp370co2fix} + hist;
                      `wrong`: the same 8 x ssp126 only (ADR 0342 sec. 5 control); training cells only
  predict <arm>       every cell x every leg of seed 2, years 2020-2100 (non-recursive: a year's state is a
                      function of the climate/CO2 window and the cell's fixed 1990-2019 anchor)
  score               ADR 0342 sec. 4 measures for the held-out climate models, emulator arms vs the original
                      (seed 2), the second run (seed 3) and persistence -> OUT/eval/response_maps.csv + .md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "python", "src"))
sys.path.insert(0, "/home/jamirp/lpjml-fit/scripts/clustered")

CLU = "/p/projects/open/Jamir/lpjml-fit-clustered"
G = f"{CLU}/grids/k674_lowrank_hist_rep1_seed1"
DIST = f"{CLU}/grids/k674_lowrank_hist_dist25_seed1"
RUNS = f"{CLU}/runs"
OUT = "/p/projects/open/Jamir/esm_land_emulator_data/clu_non"
GCMS = ["gfdl-esm4", "ipsl-cm6a-lr", "mpi-esm1-2-hr", "mri-esm2-0", "ukesm1-0-ll", "canesm5", "cnrm-cm6-1",
        "cnrm-esm2-1", "ec-earth3", "miroc6"]
TEST_GCMS = ["mpi-esm1-2-hr", "ipsl-cm6a-lr"]
TRAIN_GCMS = [g for g in GCMS if g not in TEST_GCMS]
SSPS = ["ssp126", "ssp370", "ssp585"]
NPATCH = 25
H0, H1, F0, F1 = 1990, 2019, 2020, 2100
TRAITS = ["SLA", "Wooddens", "D95max", "minwscal"]
STAND_FILES = {"vegc": ("vegc", "VegC"), "lai_stand": ("lai", "LAI")}
FORC_KEYS = ["temp", "prec", "humid", "swdown", "lwnet"]  # YearClimate(T, P, Q, SW, LW)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def struct_q():
    from lpjmlfit_emulator.landemu.annual import STRUCT_Q

    return list(STRUCT_Q)


def stand_q():
    from lpjmlfit_emulator.landemu.annual import STAND_Q

    return list(STAND_Q)


def clim_cols():
    from lpjmlfit_emulator.landemu.climate import CLIM_COLS

    return list(CLIM_COLS)


def base_dir(seed):
    return f"{RUNS}/emu-non-rep-s{seed}"


def leg_dir(seed, gcm):
    return f"{base_dir(seed)}__{gcm}"


def leg_name(gcm, tag):
    return f"{gcm}_{tag}"


FIX_TEST = ["ssp370co2fix", "ssp585co2fix"]  # ADR 0342 sec. 6a: warming-only legs of the held-out climate models


def all_legs():
    return ([(g, s) for g in GCMS for s in SSPS] + [(g, f"{s}co2fix") for g in TRAIN_GCMS for s in SSPS]
            + [(g, t) for g in TEST_GCMS for t in FIX_TEST])


def input_list():
    from cut_inputs import strip_comments

    return json.loads(strip_comments(open(f"{G}/inputs/input_clustered.cjson").read()))


# ------------------------------------------------------------------------------------------------ static
def stage_static(_a):
    m = pl.read_csv(f"{G}/nc_files/cluster_distributed_mapping_674.csv")
    full = pl.read_csv(f"{DIST}/nc_files/cluster_labels_with_coords_nr_of_clusters_674.csv")
    area = full.with_columns((np.cos(np.radians(pl.col("latitude"))) * (55.66 ** 2)).alias("a")) \
        .group_by("cluster_label").agg(pl.col("a").sum().alias("region_km2"), pl.len().alias("region_ncell"))
    ent = input_list()
    soil = np.fromfile(ent["soil"]["name"], dtype=np.uint8)
    assert soil.size == m.height, (soil.size, m.height)
    labels = sorted(m["cluster_label"].unique().to_list())
    pos = {lab: i for i, lab in enumerate(labels)}
    d = (m.select(pl.int_range(pl.len()).alias("Cell").cast(pl.Int32), "cluster_label",
                  pl.col("grid_latitude").alias("lat"), pl.col("grid_longitude").alias("lon"))
         .with_columns(pl.Series("soil_code", soil.astype(np.float64)))
         .join(area, on="cluster_label", how="left")
         .with_columns(pl.col("cluster_label").map_elements(lambda x: pos[x] % 5 == 0, return_dtype=pl.Boolean)
                       .alias("heldout")))
    assert d["region_km2"].null_count() == 0
    os.makedirs(OUT, exist_ok=True)
    d.write_parquet(f"{OUT}/cells.parquet")
    log(f"static: {d.height} cells, held out {int(d['heldout'].sum())}, regions cover "
        f"{d['region_km2'].sum() / 1e6:.1f} M km2, soil codes {sorted(set(soil.tolist()))}")


def cells():
    return pl.read_parquet(f"{OUT}/cells.parquet")


# ------------------------------------------------------------------------------------------------ climate
def forcing_files(leg):
    """config key -> cut .clm path for 'hist' or '<gcm>_<ssp>'."""
    ent = input_list()
    if leg == "hist":
        return {k: ent[k]["name"] for k in FORC_KEYS}
    g, s = leg.split("_")
    lst = json.loads(open(f"{G}/inputs/{s}_{g}/input_clustered_{s}.cjson").read().split("*/", 1)[1])
    return {k: lst[k]["name"] for k in FORC_KEYS}


def read_forcing_year(files, y):
    from build_transient_boundary import open_clm

    out = []
    for k in FORC_KEYS:
        mm, fy, ncell, nb, sc = open_clm(files[k])
        out.append(np.asarray(mm[y - fy], np.float64) * sc)
    return out  # T, P, Q, SW, LW


def stage_climate(_a):
    import explore_glob_climate as GC
    from lpjmlfit_emulator.landemu.climate import YearClimate

    c = cells()
    prm = GC.pft_temp_params()
    yc = YearClimate(c["lat"].to_numpy(), prm["temp_low"].to_numpy(), prm["temp_high"].to_numpy())
    os.makedirs(f"{OUT}/climate", exist_ok=True)
    legs = ["hist"] + [f"{g}_{s}" for g in GCMS for s in SSPS]
    for leg in legs:
        p = f"{OUT}/climate/{leg}.parquet"
        if os.path.exists(p):
            continue
        files = forcing_files(leg)
        yrs = range(1961, H1 + 1) if leg == "hist" else range(F0, F1 + 1)
        rows = []
        for y in yrs:
            T, P, Q, SW, LW = read_forcing_year(files, y)
            rows.append(yc(T, P, Q, SW, LW))
        a = np.stack(rows)  # (Y, N, 25)
        df = pl.DataFrame({"Cell": np.tile(c["Cell"].to_numpy(), len(yrs)),
                           "Year": np.repeat(np.array(list(yrs), np.int32), c.height),
                           **{k: a[:, :, j].reshape(-1) for j, k in enumerate(clim_cols())}})
        df.write_parquet(p)
        log(f"climate {leg}: {len(yrs)} years")
    # CO2 per scenario (the files the runs read): TRENDY to 2019, the SSP after; fixed = 2019 held
    co2 = {}
    for s in SSPS:
        f = f"{G}/inputs/{s}_mpi-esm1-2-hr/co2_trendy-v12-1700-2019_{s}-2020-2100.txt"
        v = dict((int(r.split()[0]), float(r.split()[1])) for r in open(f) if r.strip())
        co2[s] = v
    co2["ssp370co2fix"] = {y: (v if y <= 2019 else co2["ssp370"][2019]) for y, v in co2["ssp370"].items()}
    json.dump({k: {str(y): v for y, v in d.items()} for k, d in co2.items()}, open(f"{OUT}/climate/co2.json", "w"))
    log(f"co2: 2019 {co2['ssp370'][2019]}, 2100 ssp126/370/585 "
        f"{co2['ssp126'][2100]}/{co2['ssp370'][2100]}/{co2['ssp585'][2100]}")


def co2_series(tag):
    d = json.load(open(f"{OUT}/climate/co2.json"))
    if tag.endswith("co2fix"):  # every CO2-fixed series is the same (2019 held from 2020)
        tag = "ssp370co2fix"
    return {int(y): v for y, v in d[tag].items()}


def window(tag_or_none, gcm=None):
    """Trailing 30-yr (>= 20) climate means per Cell/Year, plus the CO2 window. tag None = hist only."""
    c = clim_cols()
    h = pl.read_parquet(f"{OUT}/climate/hist.parquet")
    if tag_or_none is not None:
        ssp = tag_or_none.replace("co2fix", "")
        h = pl.concat([h, pl.read_parquet(f"{OUT}/climate/{gcm}_{ssp}.parquet")])
    d = h.sort("Cell", "Year").with_columns(
        [pl.col(x).rolling_mean(window_size=30, min_samples=20).over("Cell") for x in c])
    co2 = co2_series(tag_or_none or "ssp370")
    ys = sorted(co2)
    arr = np.array([co2[y] for y in ys])
    cw = {y: float(arr[max(0, i - 29): i + 1].mean()) for i, y in enumerate(ys)}
    return d.with_columns(pl.col("Year").replace_strict(cw, return_dtype=pl.Float64).alias("co2_win"))


# ------------------------------------------------------------------------------------------------ targets
def reduce_ind(path, y0, y1):
    import explore_de_reference as R

    ints = {"Cell", "Year", "Type", "isdead", "Patch", "ID", "Age", "NFixing"}
    with open(path) as fh:  # pin every dtype: inference reads whole-number trait/mortality values as integers
        hdr = fh.readline().strip().split(",")
    lf = pl.scan_csv(path, schema_overrides={c: pl.Int32 if c in ints else pl.Float64 for c in hdr})
    lf = lf.filter(pl.col("Year").is_between(y0, y1)).select(
        "Year", "Cell", "Type", "isdead", pl.col("Height").cast(pl.Float64), pl.col("agb").cast(pl.Float64),
        *[pl.col(v).cast(pl.Float64) for v in TRAITS])
    g = R.living(lf).group_by(["Cell", "Year"]).agg(
        [pl.len().alias("n_living"), pl.col("agb").sum().alias("agb_sum")]
        + [pl.col(v).median().alias(f"{v}_p50") for v in TRAITS]).collect()
    cs = cells()["Cell"].to_numpy()
    census = pl.DataFrame({"Cell": np.repeat(cs, y1 - y0 + 1).astype(np.int32),
                           "Year": np.tile(np.arange(y0, y1 + 1), len(cs)).astype(np.int32)})
    assert g.join(census, on=["Cell", "Year"], how="anti").height == 0
    d = census.join(g, on=["Cell", "Year"], how="left").with_columns(
        pl.col("n_living").fill_null(0), pl.col("agb_sum").fill_null(0.0))
    return d.with_columns((pl.col("n_living") / NPATCH).alias("n_per_patch"),
                          pl.when(pl.col("n_living") > 0).then(pl.col("agb_sum") / pl.col("n_living"))
                          .otherwise(None).alias("agb_per_stem")).drop("n_living", "agb_sum")


def first_year(ds):
    """First year of an LPJmL NetCDF: units are 'years since Y' or 'days since Y-1-1' (noleap, 365-day years)."""
    u = str(ds["time"].units)
    base, t0 = int(u.split("since ")[1][:4]), float(ds["time"][0])
    return base + int(t0 // 365) if u.startswith("days") else base + int(t0)


def read_stand(odir, tag, y0, y1):
    import netCDF4 as nc
    from glob_emu import axis_index

    c = cells()
    lat, lon = c["lat"].to_numpy(), c["lon"].to_numpy()
    cols = {}
    for q, (f, v) in STAND_FILES.items():
        ds = nc.Dataset(f"{odir}/{f}_{tag}.nc")
        x = np.asarray(ds[v][:].filled(np.nan) if hasattr(ds[v][:], "filled") else ds[v][:], np.float64)
        fy = first_year(ds)
        il, io = axis_index(ds["lat"][:], lat), axis_index(ds["lon"][:], lon)
        cols[q] = x[y0 - fy: y1 - fy + 1][:, il, io]
    ds = nc.Dataset(f"{odir}/fpc_{tag}.nc")
    x = np.asarray(ds["FPC"][:].filled(np.nan) if hasattr(ds["FPC"][:], "filled") else ds["FPC"][:], np.float64)
    fy = first_year(ds)
    il, io = axis_index(ds["lat"][:], lat), axis_index(ds["lon"][:], lon)
    for p in range(1, 11):
        cols[f"fpc{p}"] = x[y0 - fy: y1 - fy + 1, p][:, il, io]
    ny = y1 - y0 + 1
    return pl.DataFrame({"Cell": np.tile(c["Cell"].to_numpy(), ny),
                         "Year": np.repeat(np.arange(y0, y1 + 1, dtype=np.int32), c.height),
                         **{q: v.reshape(-1) for q, v in cols.items()}})


def stage_targets(a):
    s = a.seed
    od = f"{OUT}/targets/s{s}"
    os.makedirs(od, exist_ok=True)
    todo = [("hist", base_dir(s), "historical", H0, H1)] + [
        (leg_name(g, t), leg_dir(s, g), t, F0, F1) for g, t in all_legs()]
    for name, d, tag, y0, y1 in todo:
        p = f"{od}/{name}.parquet"
        if os.path.exists(p) or not os.path.exists(f"{d}/output/vegc_{tag}.nc"):
            continue
        st = reduce_ind(f"{d}/output/ind_{tag}.csv", y0, y1)
        sd = read_stand(f"{d}/output", tag, y0, y1)
        st.join(sd, on=["Cell", "Year"], how="full", coalesce=True).sort("Cell", "Year").write_parquet(p)
        log(f"targets s{s} {name}: {y0}-{y1}")


def targets(seed, name):
    p = f"{OUT}/targets/s{seed}/{name}.parquet"
    return pl.read_parquet(p) if os.path.exists(p) else None


def anchors(seed):
    h = targets(seed, "hist")
    return h.group_by("Cell").agg([pl.col(q).cast(pl.Float64).mean().alias(f"anc_{q}") for q in struct_q()
                                   + stand_q()])


# ------------------------------------------------------------------------------------------------ train / predict
HR_Q = ["lai_stand", "fpc_tree", "vegc"]  # ADR 0343: quantities whose historical behaviour is a feature


def hist_response(seed):
    """Per-cell features from the seed's OWN 1990-2019 historical run (ADR 0343 sec. 2): for each HR_Q quantity the
    regression coefficients of the detrended yearly value on detrended yearly tmean_ann and cwb_ann (sens_*), the
    detrended standard deviation (sd_*) and the linear trend per year (trend_*)."""
    h = with_derived(targets(seed, "hist")).filter(pl.col("Year").is_between(H0, H1)).sort("Cell", "Year")
    cl = pl.read_parquet(f"{OUT}/climate/hist.parquet").filter(pl.col("Year").is_between(H0, H1)) \
        .select("Cell", "Year", "tmean_ann", "cwb_ann")
    d = h.join(cl, on=["Cell", "Year"], how="left").sort("Cell", "Year")
    n, ny = cells().height, H1 - H0 + 1
    assert d.height == n * ny, (d.height, n * ny)
    t = np.arange(ny, dtype=np.float64) - (ny - 1) / 2.0
    P = np.column_stack([np.ones(ny), t])  # detrend basis

    def resid(a):  # (n, ny) -> residual of a per-cell linear fit, and the slope
        a = np.where(np.isfinite(a), a, np.nanmean(a, axis=1, keepdims=True))
        a = np.nan_to_num(a)
        coef = np.linalg.lstsq(P, a.T, rcond=None)[0]  # (2, n)
        return a - (P @ coef).T, coef[1]

    xt, _ = resid(d["tmean_ann"].to_numpy().reshape(n, ny))
    xw, _ = resid(d["cwb_ann"].to_numpy().reshape(n, ny))
    out = {"Cell": d["Cell"].to_numpy().reshape(n, ny)[:, 0]}
    for q in HR_Q:
        r, tr = resid(d[q].cast(pl.Float64).to_numpy().reshape(n, ny))
        bt, bw = np.zeros(n), np.zeros(n)
        for i in range(n):
            X = np.column_stack([xt[i], xw[i]])
            if np.all(np.std(X, axis=0) > 0):
                bt[i], bw[i] = np.linalg.lstsq(X, r[i], rcond=None)[0]
        out.update({f"sens_{q}_t": bt, f"sens_{q}_w": bw, f"sd_{q}": r.std(axis=1), f"trend_{q}": tr})
    return pl.DataFrame(out).with_columns(pl.col("Cell").cast(pl.Int32))


SENS_F = [f"{k}_{q}{s}" for q in HR_Q for k, s in (("sens", "_t"), ("sens", "_w"), ("sd", ""))]
TREND_F = [f"trend_{q}" for q in HR_Q]


def feats_struct(arm="main"):
    c = clim_cols()
    cfg = ARM_CFG.get(arm, {})
    f = (c + [f"dclim_{x}" for x in c] + ["co2_win", "dco2_win"] + [f"anc_{q}" for q in struct_q()]
         + ["lat", "lon", "soil_code"] + cfg.get("add", []))
    return [x for x in f if x not in cfg.get("drop", [])]


def feats_stand(arm="main"):
    return feats_struct(arm) + [f"anc_{q}" for q in stand_q()]


def rows_for(seed, legs, years_hist, years_fut, with_targets=True):
    """Feature rows (+ targets) for the hist leg and (gcm, tag) legs of one seed."""
    c = clim_cols()
    base = window(None).filter(pl.col("Year") == H1)
    acl = base.select("Cell", *[pl.col(x).alias(f"aclim_{x}") for x in c], pl.col("co2_win").alias("aco2"))
    anc = anchors(seed)
    st = cells().select("Cell", "lat", "lon", "soil_code")
    parts = []
    specs = ([("hist", None, None, years_hist)] if years_hist else []) + [
        (leg_name(g, t), g, t, years_fut) for g, t in legs]
    for name, g, t, yrs in specs:
        w = window(t, g).filter(pl.col("Year").is_in(yrs))
        if with_targets:
            tg = targets(seed, name)
            if tg is None:
                continue
            w = w.join(tg.filter(pl.col("Year").is_in(yrs)), on=["Cell", "Year"], how="left")
        parts.append(w.with_columns(pl.lit(name).alias("leg")))
    d = pl.concat(parts, how="diagonal_relaxed")
    d = d.join(anc, on="Cell", how="left").join(acl, on="Cell", how="left").join(st, on="Cell", how="left") \
        .join(hist_response(seed), on="Cell", how="left")
    d = d.with_columns([(pl.col(x) - pl.col(f"aclim_{x}")).alias(f"dclim_{x}") for x in c]
                       + [(pl.col("co2_win") - pl.col("aco2")).alias("dco2_win")])
    return d.drop([f"aclim_{x}" for x in c] + ["aco2"])


ARMS = {"main": [(g, t) for g in TRAIN_GCMS for t in SSPS + ["ssp370co2fix"]],
        "wrong": [(g, "ssp126") for g in TRAIN_GCMS],
        # ADR 0342 sec. 6b: + the CO2-fixed twins of every scenario (warming separated from CO2)
        "main2": [(g, t) for g in TRAIN_GCMS for s in SSPS for t in (s, f"{s}co2fix")]}
# ADR 0343: one change each from main2 (why the response is worse on unseen cells)
ARM_CFG = {"m2_leaf": dict(params=dict(min_data_in_leaf=20000)),
           "m2_nogeo": dict(drop=["lat", "lon", "soil_code"]),
           "m2_sens": dict(add=SENS_F),
           "m2_trend": dict(add=TREND_F),
           # ADR 0343 sec. 7: learning curve in the number of training cells
           "m2_half": dict(cell_mod=2), "m2_quarter": dict(cell_mod=4)}
for _a in ARM_CFG:
    ARMS[_a] = ARMS["main2"]
# ADR 0344: the DEPLOYMENT maps -- main2's set-up on every climate model's every leg (rising + fixed CO2) and every
# cell (no held-out cells); not scoreable out of sample by construction, its skill is main2's
ARMS["deploy"] = all_legs()
ARM_CFG["deploy"] = dict(all_cells=True)


def stage_train(a):
    import explore_panel_a7 as A7
    import lightgbm as lgb

    out = f"{OUT}/maps/{a.arm}"
    if os.path.exists(f"{out}/annual.json"):
        sys.exit(f"{out} exists; never overwrite")
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    tr = rows_for(2, ARMS[a.arm], list(range(H0, H1 + 1, 2)), list(range(F0, F1 + 1, 2)))
    if not ARM_CFG.get(a.arm, {}).get("all_cells", False):
        ho = cells().filter(pl.col("heldout"))["Cell"].to_list()
        tr = tr.filter(~pl.col("Cell").is_in(ho))
    k = ARM_CFG.get(a.arm, {}).get("cell_mod", 1)
    tr = tr.filter(pl.col("Cell") % k == 0)
    log(f"arm {a.arm}: {tr['Cell'].n_unique()} training cells")
    log(f"arm {a.arm}: {tr.height} rows, legs {tr['leg'].n_unique()} ({time.time() - t0:.0f}s)")
    params = dict(A7.PARAMS, num_threads=int(os.environ.get("SLURM_CPUS_PER_TASK", "16")))
    params.update(ARM_CFG.get(a.arm, {}).get("params", {}))
    fs, fx = feats_struct(a.arm), feats_stand(a.arm)
    log(f"arm {a.arm}: {len(fs)} structure / {len(fx)} stand features; params {params}")
    log_eps = {"agb_per_stem": 1.0}
    nrows = {}
    for q in struct_q() + stand_q():
        f = fs if q in struct_q() else fx
        t = tr.filter(pl.col(q).is_not_null() & pl.col(q).is_not_nan() & pl.col(f"anc_{q}").is_not_null()
                      & pl.col(f"anc_{q}").is_not_nan())
        y = (np.log((t[q].to_numpy() + 1.0) / (t[f"anc_{q}"].to_numpy() + 1.0)) if q in log_eps
             else (t[q] - t[f"anc_{q}"]).to_numpy())
        lgb.train(params, lgb.Dataset(t.select(f).to_numpy(), y), A7.ROUNDS).save_model(f"{out}/lgb_{q}.txt")
        nrows[q] = t.height
        log(f"  fitted {q} on {t.height} rows ({time.time() - t0:.0f}s)")
    json.dump({"features_structure": fs, "features_stand": fx, "log_eps": log_eps, "cover_mode": "additive",
               "cover_totals": {}, "rows": nrows, "train_legs": [leg_name(g, t) for g, t in ARMS[a.arm]]},
              open(f"{out}/annual.json", "w"), indent=1)


def stage_predict(a):
    from lpjmlfit_emulator.landemu.annual import AnnualMaps

    maps = AnnualMaps.load(f"{OUT}/maps/{a.arm}")
    d = rows_for(2, all_legs(), [], list(range(F0, F1 + 1)), with_targets=False)
    feat = {k: d[k].to_numpy().astype(np.float64) for k in set(maps.f_struct) | set(maps.f_stand)}
    pred = maps.predict(feat)
    out = d.select("leg", "Cell", "Year").with_columns(
        [pl.Series(q, np.asarray(v, np.float64)) for q, v in pred.items()])
    out.write_parquet(f"{OUT}/maps/{a.arm}/preds.parquet")
    log(f"predicted {out.height} cell-years ({out['leg'].n_unique()} legs) with arm {a.arm}")


# ------------------------------------------------------------------------------------------------ score (sec. 4)
DERIVED = {"fpc_tree": [f"fpc{p}" for p in range(1, 8)], "fpc_grass": ["fpc8", "fpc9", "fpc10"]}
SCORE_Q = ["vegc", "lai_stand", "fpc_tree", "fpc_grass", "n_per_patch", "agb_per_stem", "SLA_p50",
           "Wooddens_p50", "D95max_p50", "minwscal_p50"]
DENSE_ONLY = {"n_per_patch", "agb_per_stem", "SLA_p50", "Wooddens_p50", "D95max_p50", "minwscal_p50"}
EXTENSIVE = {"vegc"}


def with_derived(df):
    return df.with_columns([pl.sum_horizontal([pl.col(c) for c in cs]).alias(k) for k, cs in DERIVED.items()])


def cell_mean(df, q, y0, y1):
    d = df.filter(pl.col("Year").is_between(y0, y1)).group_by("Cell").agg(pl.col(q).cast(pl.Float64).mean())
    v = np.full(cells().height, np.nan)
    v[d["Cell"].to_numpy()] = d[q].to_numpy()
    return v


def response_stats(dE, dT, dS, w, base, extensive):
    ok = np.isfinite(dE) & np.isfinite(dT) & np.isfinite(base)
    if dS is not None:
        ok &= np.isfinite(dS)
    e, t = dE[ok], dT[ok]
    ww = w[ok]
    if extensive:
        g = lambda d: float(np.sum(ww * d) / np.sum(ww * base[ok]))  # noqa: E731  relative global change
    else:
        g = lambda d: float(np.sum(ww * d) / np.sum(ww))  # noqa: E731  area-mean change
    vt = np.var(t)
    out = dict(n=int(ok.sum()), glob_orig=g(t), glob_emu=g(e), slope=float(np.cov(e, t)[0, 1] / vt) if vt else np.nan,
               r=float(np.corrcoef(e, t)[0, 1]) if np.std(e) > 0 and vt else np.nan,
               rmse=float(np.sqrt(np.mean((e - t) ** 2))))
    if dS is not None:
        s = dS[ok]
        out.update(glob_second=g(s), rmse_second=float(np.sqrt(np.mean((s - t) ** 2))))
        out["rmse_ratio"] = out["rmse"] / out["rmse_second"] if out["rmse_second"] > 0 else np.nan
    return out


def stage_score(a):
    c = cells()
    w = c["region_km2"].to_numpy()
    ho = c["heldout"].to_numpy()
    anc2 = anchors(2).sort("Cell")
    dense = anc2["anc_n_per_patch"].to_numpy() >= 5.0
    h2, h3 = with_derived(targets(2, "hist")), targets(3, "hist")
    h3 = with_derived(h3) if h3 is not None else None
    arms = [x for x in ARMS if os.path.exists(f"{OUT}/maps/{x}/preds.parquet")]
    preds = {x: with_derived(pl.read_parquet(f"{OUT}/maps/{x}/preds.parquet")) for x in arms}
    rows = []
    for g in TEST_GCMS:
        for s in SSPS + FIX_TEST:
            name = leg_name(g, s)
            t2, t3 = targets(2, name), targets(3, name)
            if t2 is None:
                continue
            t2 = with_derived(t2)
            t3 = with_derived(t3) if (t3 is not None and h3 is not None) else None
            for q in SCORE_Q:
                b2 = cell_mean(h2, q, H0, H1)
                dT = cell_mean(t2, q, 2071, F1) - b2
                dS = (cell_mean(t3, q, 2071, F1) - cell_mean(h3, q, H0, H1)) if t3 is not None else None
                cands = {x: cell_mean(preds[x].filter(pl.col("leg") == name), q, 2071, F1) - b2 for x in arms}
                cands["persist"] = np.zeros_like(dT)
                if t3 is not None:
                    cands["second"] = dS
                mask = dense if q in DENSE_ONLY else np.ones(len(dT), bool)
                for cand, dE in cands.items():
                    for grp, gm in (("all", mask), ("heldout_cells", mask & ho)):
                        st = response_stats(np.where(gm, dE, np.nan), dT, dS, w, b2, q in EXTENSIVE)
                        rows.append(dict(gcm=g, ssp=s, q=q, cand=cand, cells=grp, **st))
    df = pl.DataFrame(rows)
    os.makedirs(f"{OUT}/eval", exist_ok=True)
    df.write_csv(f"{OUT}/eval/response_maps.csv")
    with pl.Config(tbl_rows=400, tbl_cols=20, tbl_width_chars=260, float_precision=3):
        print(df.filter(pl.col("cells") == "all"))
    log(f"-> {OUT}/eval/response_maps.csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["static", "climate", "targets", "train", "predict", "score"])
    ap.add_argument("--seed", type=int, default=2)
    ap.add_argument("--arm", default="main", choices=list(ARMS))
    a = ap.parse_args()
    {"static": stage_static, "climate": stage_climate, "targets": stage_targets, "train": stage_train,
     "predict": stage_predict, "score": stage_score}[a.stage](a)
    log("=== DONE")


if __name__ == "__main__":
    main()
