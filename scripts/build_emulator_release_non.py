#!/usr/bin/env python3
"""build_emulator_release_non.py -- write a RELEASE of the learned emulator of the NITROGEN-ON LPJmL-FIT with
transient CO2 (ADR 0342 data, ADR 0344): the package python/src/lpjmlfit_emulator/landemu with its CO2 input
(``release.json`` co2_input; ``step_year(..., co2=ppm)``), the yearly maps of scripts/clu_emu_maps.py, the CO2-reading
daily ensemble of scripts/f2_train.py --co2, and one SETUP for the 674 clustered cells (one per climate region).

  --kind fold     the VALIDATED set-up: maps arm `main2` (8 climate models x 3 SSPs x rising/fixed CO2, the 80 %
                  training cells) + daily members NC_s0-4 (8 climate models, the training cells). Exists so that
                  scripts/run_emulator_non.py --check can show the package reproduces the scored predictions
                  (clu_non/maps/main2/preds.parquet, f2_non/runs/NC_B3) with every input computed by the package.
  --kind deploy   the DEPLOYMENT release: maps arm `deploy` + members NCD_s0-4 -- every climate model's every leg
                  (58) and every cell. Not scoreable out of sample by construction; its skill is the fold's.

The setup is scenario-independent: each cell is anchored on its own 1990-2019 state in the original's historical
run (seed 2), so the run has no last year (anchors are per cell, not per year). The CO2 history 1990-2019 is the
historical CO2 the runs read (TRENDY).

Gates before the release is marked written:
  (1) the numpy daily ensemble (with its CO2 column) equals the PyTorch one on 20 000 real input rows;
  (2) the package's yearly climate statistics equal the training table's (clu_non/climate) for one leg, two years;
  (3) the setup's anchors / anchor climate / anchor CO2 equal the training rows' (clu_emu_maps.rows_for), exactly.
SLURM: PARTITION=priority QOS=priority NCPUS=8 TIME=01:00:00 scripts/sbatch_python.sh release-non \\
          scripts/build_emulator_release_non.py --kind fold --out <dir>
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "python", "src"))
import build_emulator_release as BR  # noqa: E402
import clu_emu_maps as M  # noqa: E402
from lpjmlfit_emulator.landemu import annual as AN  # noqa: E402
from lpjmlfit_emulator.landemu import climate as CL  # noqa: E402

F2N = "/p/projects/open/Jamir/esm_land_emulator_data/f2_non"
KINDS = {"fold": ("main2", [f"NC_s{i}" for i in range(5)]),
         "deploy": ("deploy", [f"NCD_s{i}" for i in range(5)])}
GATE_LEG = "mpi-esm1-2-hr_ssp370"  # a held-out climate model's leg
QA = AN.STRUCT_Q + AN.STAND_Q
RM, SWE = 6, 5  # f2 DAILY columns (clu_emu_f2.DAILY)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def gate_climate():
    import explore_glob_climate as GC

    c = M.cells()
    prm = GC.pft_temp_params()
    lo, hi = prm["temp_low"].to_numpy(), prm["temp_high"].to_numpy()
    yc = CL.YearClimate(c["lat"].to_numpy(), lo, hi)
    ref = pl.read_parquet(f"{M.OUT}/climate/{GATE_LEG}.parquet")
    files = M.forcing_files(GATE_LEG)
    worst = 0.0
    for y in (2020, 2060):
        got = yc(*M.read_forcing_year(files, y))
        r = c.select("Cell").join(ref.filter(pl.col("Year") == y), on="Cell", how="left").select(CL.CLIM_COLS)
        d = float(np.abs(got - r.to_numpy()).max())
        worst = max(worst, d)
        assert d == 0.0, f"climate statistics differ from the training table by {d} in {y}"
    log(f"GATE (2) yearly climate statistics == training table ({GATE_LEG}, 2020 + 2060), max diff {worst}")
    return {"low": lo.tolist(), "high": hi.tolist()}


def write_setup(out, cdf):
    """setup_s2.npz: the 674 cells, anchored on seed 2's own 1990-2019 state."""
    n = cdf.height
    key = cdf.select("Cell")
    anc = key.join(M.anchors(2), on="Cell", how="left")
    cols = M.clim_cols()
    win = M.window(None)
    acl = key.join(win.filter(pl.col("Year") == M.H1), on="Cell", how="left")
    aco2 = float(acl["co2_win"][0])
    hist = pl.read_parquet(f"{M.OUT}/climate/hist.parquet")
    H = np.stack([key.join(hist.filter(pl.col("Year") == y), on="Cell", how="left").select(cols).to_numpy()
                  for y in range(M.H0, M.H1 + 1)]).astype(np.float64)
    co2 = M.co2_series("ssp370")
    co2_hist = np.array([co2[y] for y in range(M.H0, M.H1 + 1)], np.float64)
    assert np.mean(co2_hist) == aco2, "anchor CO2 window != mean of the 1990-2019 CO2"
    tag = f"m2_{GATE_LEG}"
    daily = np.load(f"{F2N}/daily_{tag}.npy", mmap_mode="r")
    forc = np.load(f"{F2N}/forc_{tag}.npy", mmap_mode="r")
    stand = np.load(f"{F2N}/stand_{tag}.npy")
    cap = np.load(f"{F2N}/cap_{tag}.npy")
    z = {"cell": cdf["Cell"].to_numpy(), "lat": cdf["lat"].to_numpy(), "lon": cdf["lon"].to_numpy(),
         "soil_code": cdf["soil_code"].to_numpy(), "year0": np.int64(M.F0),
         "aclim": acl.select(cols).to_numpy().astype(np.float64), "clim_hist": H,
         "cap": cap[:, 0].astype(np.float64), "W0": np.array(daily[:, 0, RM], np.float64),
         "S0": np.array(daily[:, 0, SWE], np.float64), "D0": np.zeros(n), "stand0": stand[:, 0].astype(np.float64),
         "warm": np.array(forc[:, :365], np.float32), "co2_hist": co2_hist, "aco2": np.float64(aco2)}
    for q in QA:
        z[f"anc/{q}"] = anc[f"anc_{q}"].to_numpy().astype(np.float64)
        z[f"s0/{q}"] = np.zeros(n)
        z[f"memoff/{q}"] = np.zeros(n)
    # GATE (3): the setup's fixed inputs == the training/prediction rows' (one leg, all years)
    rows = M.rows_for(2, [tuple(GATE_LEG.split("_"))], [], [M.F0, 2077], with_targets=False).sort("Year", "Cell")
    worst = 0.0
    for y in (M.F0, 2077):
        r = key.join(rows.filter(pl.col("Year") == y), on="Cell", how="left")
        for q in QA:
            worst = max(worst, float(np.nanmax(np.abs(r[f"anc_{q}"].to_numpy() - z[f"anc/{q}"])) or 0.0))
            assert np.array_equal(np.isnan(r[f"anc_{q}"].to_numpy()), np.isnan(z[f"anc/{q}"])), q
        for j, x in enumerate(cols):
            d = r[x].to_numpy() - r[f"dclim_{x}"].to_numpy() - z["aclim"][:, j]
            worst = max(worst, float(np.nanmax(np.abs(d))))
        worst = max(worst, float(np.abs(r["co2_win"].to_numpy() - r["dco2_win"].to_numpy() - aco2).max()))
    log(f"GATE (3) setup anchors / anchor climate / anchor CO2 vs the training rows: max |diff| {worst:.1e}")
    assert worst < 1e-9, "setup inputs differ from the training rows'"
    p = os.path.join(out, "setup_s2.npz")
    np.savez(p, **z)
    log(f"setup: {n} cells, anchors finite {np.isfinite(z['anc/n_per_patch']).mean():.3f} (tree count) "
        f"{np.isfinite(z['anc/vegc']).mean():.3f} (vegetation carbon); CO2 window 1990-2019 {aco2:.2f} ppm")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--kind", choices=list(KINDS), required=True)
    a = ap.parse_args()
    if os.path.exists(os.path.join(a.out, "release.json")):
        sys.exit(f"{a.out} already holds a release; never overwrite one in place")
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    arm, members = KINDS[a.kind]
    _, rel = BR.export_daily(a.out, members=members, data=F2N, gate_run=2, gate_leg=GATE_LEG, co2=True)
    pft = gate_climate()
    md = f"{M.OUT}/maps/{arm}"
    acfg = json.load(open(f"{md}/annual.json"))
    for q in QA:
        shutil.copy(f"{md}/lgb_{q}.txt", os.path.join(a.out, f"lgb_{q}.txt"))
    json.dump({k: acfg[k] for k in ("features_structure", "features_stand", "log_eps", "cover_mode", "cover_totals")},
              open(os.path.join(a.out, "annual.json"), "w"), indent=1)
    setup = write_setup(a.out, M.cells())
    cfg = {"version": os.path.basename(os.path.normpath(a.out)), "git_sha": BR.git_sha(),
           "built": time.strftime("%Y-%m-%d %H:%M"), "kind": a.kind, "hold_gcm": None,
           "model": "LPJmL-FIT merged, nitrogen on (no phosphorus), transient CO2, 25 patches (ADR 0342)",
           "co2_input": True, "co2_units": "ppm, the year's global mean (as LPJmL's CO2 input file)",
           "maps_arm": arm, "maps_dir": md, "train_legs": acfg.get("train_legs"),
           "heldout_gcms": [] if a.kind == "deploy" else M.TEST_GCMS,
           "heldout_cells": "none" if a.kind == "deploy" else "every 5th region (clu_non/cells.parquet heldout)",
           "daily_members": members, "daily_dir": F2N, "anchor": "the cell's own 1990-2019 state, seed 2 (fixed)",
           "pft_temp_stress": pft, "gates": {"daily_numpy_vs_torch_max_rel": rel, "climate_exact": True,
                                             "setup_exact": True},
           "setups": [os.path.basename(setup)], "first_year": M.F0}
    json.dump(cfg, open(os.path.join(a.out, "release.json"), "w"), indent=1)
    log(f"release written to {a.out} ({time.time() - t0:.0f}s)")
    log("=== DONE")


if __name__ == "__main__":
    main()
