#!/usr/bin/env python3
"""build_emulator_release.py -- write a RELEASE of the whole learned emulator (python/src/lpjmlfit_emulator/landemu):
the trained structure + stand maps (LightGBM model files), the daily water-carbon ensemble exported to numpy, and one
SETUP file per continued run of the original for the 1 050 panel cells. ADR 0340.

  --hold-gcm <g>   FOLD release: exactly the validated setup of ADR 0330/0331/0337 (training runs m1,m2,m3,m5,m6 x
                   the other climate models' legs, anchors over those), so scripts/run_emulator.py can show the package
                   reproduces the scored predictions with every input now computed from the daily weather.
  (default)        DEPLOYMENT release: every run (m1-m6) x every leg of all ten climate models trains; anchors over
                   all of them. Not scoreable out of sample by construction -- its skill is the fold releases'.
  --cover-mode     how the 10 plant-type covers are fit (ADR 0339): additive (default) | relative | sumconstrained.
  --departure dep  add the weather-driven departure model for tree count and biomass per tree (ADR 0354, shipped
                   by ADR 0358), trained by explore_panel_yearly_drift.fit_departure on every year of the same runs
                   and legs; its fold release reproduces preds_<g>_statedep_fx.parquet.

Gates before anything is written (a label is not evidence):
  (1) the numpy daily ensemble equals the PyTorch one on 20 000 real input rows (max |diff| / largest output < 1e-5);
  (2) the package's yearly climate statistics equal scripts/explore_glob_climate.year_features on the same daily
      weather (one leg, years 2020 + 2060, all 25 columns, exact);
  (3) the setup's anchors reproduce the training table's test-row anchors (fold release only, exact);
  (4) --departure only: the package's z-scores of the yearly statistics equal the training table's
      (explore_panel_yearly_drift.weather_anomaly) on one leg, fed the same statistics (< 1e-9).
Run on SLURM (~120 GB for the training table):
  PARTITION=priority QOS=priority NCPUS=32 TIME=02:00:00 scripts/sbatch_python.sh release-<tag> \
      scripts/build_emulator_release.py --out <dir> [--hold-gcm g]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "python", "src"))
import explore_glob_climate as GC  # noqa: E402
import explore_panel_a7 as A7  # noqa: E402
import explore_panel_prep as PP  # noqa: E402
import explore_panel_stand_map as SM  # noqa: E402
import explore_panel_yearly_drift as YD  # noqa: E402
from explore_de_climate import daylength_hours  # noqa: E402
from lpjmlfit_emulator.landemu import annual as AN  # noqa: E402
from lpjmlfit_emulator.landemu import climate as CL  # noqa: E402
from lpjmlfit_emulator.landemu import daily as DL  # noqa: E402

F2 = "/p/projects/open/Jamir/esm_land_emulator_data/f2"
MEMBERS = [f"D_3x256_seed{i}" for i in range(5)]  # arm D, the deployment daily model (ADR 0335/0336)
QA = AN.STRUCT_Q + AN.STAND_Q
COVER_TOTALS = {"fpc_tree_total": SM.FPC[:7], "fpc_grass_total": SM.FPC[7:]}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def git_sha():
    try:
        return subprocess.check_output(["git", "-C", REPO, "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


# ------------------------------------------------------------------------------------------------ daily model
def export_daily(out, members=MEMBERS, data=F2, gate_run=1, gate_leg="gfdl-esm4_ssp370_daily", co2=False):
    """Export the PyTorch ensemble `members` (runs under data/runs) to out/daily.npz and run GATE (1) on real rows of
    (gate_run, gate_leg). co2: the members read the year's CO2 (f2_train --co2, nitrogen-on model; ADR 0344)."""
    import f2_train as F
    import torch

    F.DATA, F.CO2_INPUT = data, co2
    F.NIN = F.NFORC + 3 + 4 + 12 + int(co2)
    F.NH, F.NL, F.NPP_HEAD, F.DEEP_TAU = 256, 3, "ra", 365.0
    F.DROP[:] = [F.FEAT["huss"]]
    arrs = {"n_members": np.int64(len(members)), "drop": np.array(F.DROP, np.int64), "deep_tau": np.float64(365.0),
            "co2_input": np.bool_(co2)}
    nets = []
    for i, t in enumerate(members):
        n, ck = F.load_net(os.path.join(F.DATA, "runs", t, "model.pt"), torch.device("cpu"))
        n.load_state_dict(ck)
        n.eval()
        nets.append(n)
        lin = [m for m in n.trunk if isinstance(m, torch.nn.Linear)]
        arrs[f"m{i}/n_layers"] = np.int64(len(lin) - 1)
        for j, m in enumerate(lin):
            arrs[f"m{i}/W{j}"] = m.weight.detach().numpy().astype(np.float32)
            arrs[f"m{i}/b{j}"] = m.bias.detach().numpy().astype(np.float32)
        for k in ("mu", "sd", "ysd"):
            arrs[f"m{i}/{k}"] = getattr(n, k).numpy().astype(np.float32)
    path = os.path.join(out, "daily.npz")
    np.savez(path, **arrs)
    # GATE (1): real inputs (teacher-forced rows of one leg, run 1), torch vs numpy
    lat = pl.read_parquet(os.path.join(data, "cells.parquet"))["lat"].to_numpy().astype(np.float32)
    ml = F.MemberLeg(gate_run, gate_leg, lat)
    rng = np.random.default_rng(0)
    cells = rng.integers(0, ml.daily.shape[0], 20000)
    days = rng.integers(1, F.ND, 20000)
    x = ml.inputs_teacher(cells, days)
    prec = ml.daily[cells, days, F.PREC].astype(np.float32)
    S = ml.daily[cells, days - 1, F.SWE].astype(np.float32)
    with torch.no_grad():
        yt = F.Ensemble(nets)(torch.from_numpy(x), torch.from_numpy(prec), torch.from_numpy(S)).numpy()
    yn = DL.DailyModel.load(path).predict(x, prec, S)
    # scale = each output's largest |value|: a 90th-percentile scale is ~0 for snow change (no snow on most days),
    # which turned float32 rounding (3e-5 mm on an 8 mm value) into a false 3e-3 "mismatch" on the first build
    scale = np.maximum(np.abs(yt).max(axis=0), 1e-6)
    rel = (np.abs(yn - yt) / scale).max()
    log(f"GATE (1) daily numpy vs torch: max |diff| / largest |output| per column = {rel:.2e}")
    assert rel < 1e-5, "numpy port of the daily model differs from PyTorch"
    return path, float(rel)


# ------------------------------------------------------------------------------------------------ climate gate
def gate_climate():
    import f2_train as F

    cdf = pl.read_parquet(os.path.join(F2, "cells.parquet"))
    lat = cdf["lat"].to_numpy().astype(np.float64)
    forc = np.load(os.path.join(F2, "forc_m1_gfdl-esm4_ssp370_daily.npy"), mmap_mode="r")
    prm = GC.pft_temp_params()
    lo, hi = prm["temp_low"].to_numpy(), prm["temp_high"].to_numpy()
    yc = CL.YearClimate(lat, lo, hi)
    dl, win, hs = daylength_hours(lat), GC.window_mask(lat), GC.summer_mask(lat)
    worst = 0.0
    for y in (2020, 2060):
        sl = slice(F.WARM + (y - 2020) * 365, F.WARM + (y - 2019) * 365)
        f = np.asarray(forc[:, sl], np.float64)
        ref, _ = GC.year_features(f[:, :, 0], f[:, :, 1], f[:, :, 4], f[:, :, 2], f[:, :, 3], np.zeros_like(f[:, :, 0]),
                                  dl, win, hs, lo, hi)
        got = yc(f[:, :, 0], f[:, :, 1], f[:, :, 4], f[:, :, 2], f[:, :, 3])
        for j, c in enumerate(CL.CLIM_COLS):
            d = np.abs(got[:, j] - np.asarray(ref[c], np.float64)).max()
            worst = max(worst, d)
            assert d == 0.0, f"climate column {c} differs by {d} in {y}"
    log(f"GATE (2) yearly climate statistics: package == explore_glob_climate.year_features exactly (max diff {worst})")
    return {"temp_low": lo.tolist(), "temp_high": hi.tolist()}


# ------------------------------------------------------------------------------------------------ annual maps
def build_tables(hold_gcm):
    """Training rows + the per-(Cell, Year) anchor / anchor-climate tables. Fold: exactly SM.build_rows(g)."""
    if hold_gcm is None:
        YD.TRAIN_M = tuple(PP.MEMBERS)  # every run trains; there are no test legs
        train_legs = list(A7.ALL_SLEGS)
        tr, _ = SM.build_rows("none")
    else:
        train_legs = [lg for lg in A7.ALL_SLEGS if A7.gcm_of(lg) != hold_gcm]
        tr, te = SM.build_rows(hold_gcm, 4)
    states = pl.concat([d for m in PP.MEMBERS for lg in A7.ALL_SLEGS if (d := YD.yearly(m, lg)) is not None])
    st = pl.concat([d for m in PP.MEMBERS for lg in A7.ALL_SLEGS if (d := SM.stand(m, lg)) is not None])
    states = states.with_columns(pl.col("Cell").cast(pl.Int32), pl.col("Year").cast(pl.Int32)).join(
        st, on=["Cell", "Year", "member", "leg"], how="left")
    base = states.filter(pl.col("member").is_in(YD.TRAIN_M) & pl.col("leg").is_in(train_legs))
    anc = base.group_by("Cell", "Year").agg([pl.col(q).mean().alias(f"anc_{q}") for q in QA])
    clim = pl.concat([YD.window_climate(lg) for lg in train_legs]).with_columns(
        pl.col("Cell").cast(pl.Int32), pl.col("Year").cast(pl.Int32))
    aclim = clim.group_by("Cell", "Year").agg([pl.col(c).mean() for c in YD.CLIM])
    if hold_gcm is not None:  # GATE (3): the setup anchors are the test rows' anchors
        t = te.filter(pl.col("member") == YD.TRUTH).select("Cell", "Year", *[f"anc_{q}" for q in QA])
        j = t.join(anc, on=["Cell", "Year"], suffix="_s")
        worst = max(float((j[f"anc_{q}"] - j[f"anc_{q}_s"]).abs().max() or 0.0) for q in QA)
        log(f"GATE (3) setup anchors vs the test rows' anchors: {j.height} rows, max |diff| {worst:.2e}")
        assert worst < 1e-9, "setup anchors differ from the validated test rows'"
    log(f"training rows {tr.height}; anchor table {anc.height}; anchor climate {aclim.height}")
    return tr, anc, aclim


def fit_annual(tr, out, cover_mode):
    import lightgbm as lgb

    fs, fx = YD.feats(), SM.stand_feats()
    t0 = time.time()

    def fit(q, f, target):
        t = tr.filter(pl.col(q).is_not_null() & pl.col(f"anc_{q}").is_not_null()) if q in QA else tr
        if target == "log":
            e = YD.LOG_EPS[q]
            y = np.log((t[q].to_numpy() + e) / (t[f"anc_{q}"].to_numpy() + e))
        elif target == "relative":
            y = (np.log(np.maximum(t[q].to_numpy().astype(float), SM.EPS_COVER))
                 - np.log(np.maximum(t[f"anc_{q}"].to_numpy().astype(float), SM.EPS_COVER)))
        else:
            y = (t[q] - t[f"anc_{q}"]).to_numpy()
        m = lgb.train(A7.PARAMS, lgb.Dataset(t.select(f).to_numpy(), y), A7.ROUNDS)
        m.save_model(os.path.join(out, f"lgb_{q}.txt"))
        log(f"fitted {q} [{target}] on {t.height} rows ({time.time() - t0:.0f}s)")

    for q in AN.STRUCT_Q:
        fit(q, fs, "log" if q in YD.LOG_EPS else "add")
    for q in AN.STAND_Q:
        fit(q, fx, "relative" if (q in SM.FPC and cover_mode == "relative") else "add")
    totals = {}
    if cover_mode == "sumconstrained":
        for name, cols in COVER_TOTALS.items():
            t = tr.filter(pl.col(cols[0]).is_not_null())
            t = t.with_columns(t.select(cols).sum_horizontal().alias(name),
                               t.select([f"anc_{c}" for c in cols]).sum_horizontal().alias(f"anc_{name}"))
            m = lgb.train(A7.PARAMS, lgb.Dataset(t.select(fx).to_numpy(), (t[name] - t[f"anc_{name}"]).to_numpy()),
                          A7.ROUNDS)
            m.save_model(os.path.join(out, f"lgb_{name}.txt"))
            totals[name] = cols
            log(f"fitted {name} [sum of {cols[0]}..{cols[-1]}]")
    cfg = {"features_structure": fs, "features_stand": fx, "log_eps": {q: YD.LOG_EPS[q] for q in YD.LOG_EPS},
           "cover_mode": cover_mode, "cover_totals": totals}
    with open(os.path.join(out, "annual.json"), "w") as fh:
        json.dump(cfg, fh, indent=1)
    assert fs == [c for c in fx if c in fs], "structure features must be the stand features' leading subset"


# ------------------------------------------------------------------------------------------------ departure
def fit_departure_models(out, hold_gcm, arm="dep"):
    """ADR 0358: the departure model of ADR 0354 on top of the structure map, with the research code itself."""
    from lpjmlfit_emulator.landemu.emulator import LandEmulator

    t0 = time.time()
    R = YD.build_rows(hold_gcm, state=arm, t0=t0)
    f = YD.feats()
    fm, fd, _ = YD.fit_departure(hold_gcm, arm, R["tr"], f, "auto", R["train_legs"], R["train_years"], t0)
    for q, m in fm.items():
        m.save_model(os.path.join(out, f"lgb_dep_{q}.txt"))
    # GATE (4): the package's z-score == the training table's, on the same yearly statistics
    leg = R["train_legs"][0]
    ref = YD.weather_anomaly(leg).sort("Cell", "Year")
    h = pl.read_parquet(os.path.join(PP.CLIM_DIR, "hist.parquet")).filter(pl.col("Year") < YD.Y0)
    sc = pl.read_parquet(os.path.join(PP.CLIM_DIR, f"{leg}.parquet"))
    stats = (pl.concat([h.select("Cell", "Year", *YD.CLIM), sc.select("Cell", "Year", *YD.CLIM)])
             .with_columns([pl.col(c).cast(pl.Float64) for c in YD.CLIM]).sort("Year", "Cell"))
    years = sorted(stats["Year"].unique().to_list())
    cube = np.stack([stats.filter(pl.col("Year") == y).sort("Cell").select(YD.CLIM).to_numpy() for y in years])
    worst = 0.0
    for y in (YD.Y0, 2050, YD.Y1):
        i = years.index(y)
        z = LandEmulator.zscore(cube[i], list(cube[max(0, i - 30):i]), 15)
        r = ref.filter(pl.col("Year") == y).sort("Cell").select([f"z0_{c}" for c in YD.CLIM]).to_numpy()
        worst = max(worst, float(np.abs(z - r).max()))
    log(f"GATE (4) departure z-scores: package == training table on {leg} (2020/2050/2100), max |diff| {worst:.2e}")
    assert worst < 1e-9, "the package's weather anomaly differs from the training table's"
    return {"arm": arm, "features": fd, "eps": YD.DEP_EPS, "quantities": list(YD.STATE_Q), "z_window": 30,
            "z_min": 15}, worst


# ------------------------------------------------------------------------------------------------ setups
def write_setups(out, anc, aclim):
    cdf = pl.read_parquet(os.path.join(F2, "cells.parquet")).with_columns(pl.col("Cell").cast(pl.Int32))
    pc = PP.cells().select(pl.col("Cell").cast(pl.Int32), "lat", "lon", "soil_code")
    cdf = cdf.select("Cell").join(pc, on="Cell", how="left")
    cells = cdf["Cell"].to_numpy()
    n, years = len(cells), np.arange(2020, 2101)
    grid = pl.DataFrame({"Cell": np.repeat(cells, len(years)).astype(np.int32),
                         "Year": np.tile(years, n).astype(np.int32)})
    A = grid.join(anc, on=["Cell", "Year"], how="left")
    C = grid.join(aclim, on=["Cell", "Year"], how="left")
    hist = pl.read_parquet(os.path.join(PP.CLIM_DIR, "hist.parquet")).filter(pl.col("Year").is_between(2000, 2019))
    hist = hist.with_columns(pl.col("Cell").cast(pl.Int32))
    H = np.stack([pl.DataFrame({"Cell": cells}).join(hist.filter(pl.col("Year") == y), on="Cell", how="left")
                  .select([pl.col(c).cast(pl.Float64) for c in YD.CLIM]).to_numpy() for y in range(2000, 2020)])
    s0x = YD.s0_table().with_columns(pl.col("Cell").cast(pl.Int32)).join(
        SM.stand_s0().with_columns(pl.col("Cell").cast(pl.Int32)), on=["Cell", "member"], how="left")
    base = {"cell": cells, "lat": cdf["lat"].to_numpy(), "lon": cdf["lon"].to_numpy(),
            "soil_code": cdf["soil_code"].to_numpy(), "year0": np.int64(2020),
            "aclim": C.select(YD.CLIM).to_numpy().reshape(n, len(years), len(YD.CLIM)), "clim_hist": H}
    for q in QA:
        base[f"anc/{q}"] = A[f"anc_{q}"].to_numpy().astype(np.float64).reshape(n, len(years))
    written = []
    for k in (1, 2, 3, 4):  # runs with daily data (the f2 arrays); the first leg's 2019 state = the run's own
        tag = f"m{k}_gfdl-esm4_ssp370_daily"
        daily0 = np.load(os.path.join(F2, f"daily_{tag}.npy"), mmap_mode="r")
        forc = np.load(os.path.join(F2, f"forc_{tag}.npy"), mmap_mode="r")
        s = pl.DataFrame({"Cell": cells}).join(s0x.filter(pl.col("member") == k), on="Cell", how="left")
        z = dict(base)
        z.update({f"s0/{q}": s[f"s0_{q}"].to_numpy().astype(np.float64) for q in QA})
        z.update({f"memoff/{q}": s[f"memoff_{q}"].to_numpy().astype(np.float64) for q in QA})
        z.update({"cap": np.load(os.path.join(F2, f"cap_{tag}.npy"))[:, 0].astype(np.float64),
                  "W0": np.array(daily0[:, 0, 6], np.float64), "S0": np.array(daily0[:, 0, 5], np.float64),
                  "D0": np.zeros(n), "stand0": np.load(os.path.join(F2, f"stand_{tag}.npy"))[:, 0].astype(np.float64),
                  "warm": np.array(forc[:, :365], np.float32)})
        p = os.path.join(out, f"setup_m{k}.npz")
        np.savez(p, **z)
        written.append(p)
        log(f"setup m{k}: {n} cells, anchors finite {np.isfinite(z['anc/n_per_patch']).mean():.3f}, "
            f"stand anchors finite {np.isfinite(z['anc/fpc1']).mean():.3f}")
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--hold-gcm", dest="hold_gcm", default=None, choices=[None, *PP.GCMS])
    ap.add_argument("--cover-mode", dest="cover_mode", default="additive",
                    choices=["additive", "relative", "sumconstrained"])
    ap.add_argument("--departure", default=None, choices=[None, "dep"],
                    help="add the weather-driven departure model (ADR 0354/0358)")
    a = ap.parse_args()
    if os.path.exists(os.path.join(a.out, "release.json")):
        sys.exit(f"{a.out} already holds a release; never overwrite one in place")
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    _, rel = export_daily(a.out)
    pft = gate_climate()
    tr, anc, aclim = build_tables(a.hold_gcm)
    fit_annual(tr, a.out, a.cover_mode)
    del tr
    dep, zgate = (None, None)
    if a.departure:
        dep, zgate = fit_departure_models(a.out, a.hold_gcm, a.departure)
        ap_ = os.path.join(a.out, "annual.json")
        with open(ap_) as fh:
            acfg = json.load(fh)
        acfg["departure"] = dep
        with open(ap_, "w") as fh:
            json.dump(acfg, fh, indent=1)
    setups = write_setups(a.out, anc, aclim)
    cfg = {"version": os.path.basename(os.path.normpath(a.out)), "git_sha": git_sha(),
           "built": time.strftime("%Y-%m-%d %H:%M"), "kind": "deployment" if a.hold_gcm is None else "fold",
           "hold_gcm": a.hold_gcm, "train_runs": list(YD.TRAIN_M),
           "train_legs": [lg for lg in A7.ALL_SLEGS if a.hold_gcm is None or A7.gcm_of(lg) != a.hold_gcm],
           "daily_members": MEMBERS, "cover_mode": a.cover_mode, "pft_temp_stress": {"low": pft["temp_low"],
                                                                                    "high": pft["temp_high"]},
           "gates": {"daily_numpy_vs_torch_max_rel": rel, "climate_exact": True,
                     "setup_anchors_exact": a.hold_gcm is not None, "departure_z_max_abs": zgate},
           "departure": a.departure,
           "setups": [os.path.basename(p) for p in setups], "years": [2020, 2100],
           # ADR 0352 sec. 0 / 0353: built after the held-out-leg leak fix; `run_emulator.py --check` compares with
           # the leak-free scored predictions (file suffix below). Releases without the key predate the fix.
           "pred_suffix": SM.FX,
           # ADR 0358: the structure check of a release with a departure model reads that arm's predictions
           "struct_pred_suffix": f"_state{a.departure}{SM.FX}" if a.departure else SM.FX}
    with open(os.path.join(a.out, "release.json"), "w") as fh:
        json.dump(cfg, fh, indent=1)
    log(f"release written to {a.out} ({time.time() - t0:.0f}s)")
    log("=== DONE")


if __name__ == "__main__":
    main()
