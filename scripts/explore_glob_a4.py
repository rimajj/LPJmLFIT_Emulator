#!/usr/bin/env python3
"""explore_glob_a4.py -- LINE X: arm A4 on the global venue = free-run calibration of the per-tree stepper's
growth-efficiency channel (ADR 0315 sec. 16.4; expectations written there BEFORE this ran).

Two one-variable families on TabAL, calibrated ONLY on a training member + training scenario:
  A4k  kappa_g      in {0, 0.25, 0.5, 0.75, 1}   (shrink the learned climate effect on growth efficiency)
  A4o  logit_off_g  in {-0.15, -0.3, -0.5}        (shift the bad-year probability, climate effect kept)
Calibration basis: member 2, ssp245, from its own 2014 state, fold-1 dev cells (runs/cells_fold1.txt, root Cell16 ids),
statistic L = |ln stems P/T| + |ln biomass-per-stem P/T| at 2071-2100 against member 2's own truth.

Stages
  cal      submit the 7 calibration runs (engine arrays) + one chained scoring job each (--truth-seed 2 --fold 1)
  pick     read eval/scores_A4cal_*.csv, print L per point, the winner of each family -> eval/a4_pick.json
  confirm  run each family's winner ONCE on GS370 (member 8, ssp370, all dev cells, from 2014) + chained scoring

Every stage needs the global-root environment (exported here, so sbatch's --export=ALL carries it to the jobs):
XDE_ROOT, XDE_GRASS_TYPES=7,8,9, XDE_RECR_TYPES=0..6, XDE_TRAIT_BUILD=feb2026, XDE_LAST_SIM_YEAR=2100.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys

import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = "/p/projects/open/Jamir/esm_land_emulator_data/billing_global"
XDE = os.path.join(DATA, "xde")
EVAL = os.path.join(DATA, "eval")
PY = "/home/jamirp/.conda/envs/py311_new/bin/python"
ENV = {"XDE_ROOT": XDE, "XDE_GRASS_TYPES": "7,8,9", "XDE_RECR_TYPES": "0,1,2,3,4,5,6",
       "XDE_TRAIT_BUILD": "feb2026", "XDE_LAST_SIM_YEAR": "2100"}
CELLS = os.path.join(XDE, "runs", "cells_fold1.txt")
GRID = {"A4cal_k0": {"kappa_g": 0.0}, "A4cal_k025": {"kappa_g": 0.25}, "A4cal_k05": {"kappa_g": 0.5},
        "A4cal_k075": {"kappa_g": 0.75}, "A4cal_k1": {},
        "A4cal_o015": {"logit_off_g": -0.15}, "A4cal_o03": {"logit_off_g": -0.3}, "A4cal_o05": {"logit_off_g": -0.5}}
FAMILY = {"k": ["A4cal_k0", "A4cal_k025", "A4cal_k05", "A4cal_k075", "A4cal_k1"],
          "o": ["A4cal_k1", "A4cal_o015", "A4cal_o03", "A4cal_o05"]}


def sh(cmd: list[str]) -> str:
    print(" ".join(cmd), flush=True)
    return subprocess.run(cmd, capture_output=True, text=True, check=True, env={**os.environ, **ENV}).stdout


def run_dir(arm, seed, legs):
    return os.path.join(XDE, "runs", arm, f"GFDL-ESM4_s{seed}_2014-2100_{legs}_actual_r1")


def submit(arm, cal, seed, legs, cells, chunk, label, score_args):
    cmd = [PY, os.path.join(REPO, "scripts", "explore_de_engine.py"), "submit", "--arm", arm,
           "--stepper", "explore_de_tab_stepper:TabAL", "--kwargs", json.dumps({"cal": cal}),
           "--gcm", "GFDL-ESM4", "--seed", str(seed), "--start", "2014", "--end", "2100", "--legs", legs,
           "--cellset", "dev", "--chunk-size", str(chunk), "--parallel", "17"]
    if cells:
        cmd += ["--cells", cells]
    out = sh(cmd)
    jid = out.strip().split("submitted ")[-1].split(":")[0] if "submitted" in out else None
    if jid is None:  # the engine logs to stdout; fall back to the newest job of that name
        jid = subprocess.run(["squeue", "-u", os.environ["USER"], "-h", "-n", f"X-de-run-{arm}", "-o", "%F"],
                             capture_output=True, text=True).stdout.split()[0]
    jcf = os.path.join(XDE, "_jobs", f"X-gtabev-{label}.jcf")
    exports = " ".join(f"{k}={v}" for k, v in ENV.items())
    with open(jcf, "w") as f:
        f.write(f"""#!/bin/bash
#SBATCH --job-name=X-gtabev-{label}
#SBATCH --account=waldspektrum
#SBATCH --partition=priority
#SBATCH --qos=priority
#SBATCH --cpus-per-task=8
#SBATCH --time=01:00:00
#SBATCH --dependency=afterok:{jid}
#SBATCH --output={REPO}/logs/X-gtabev-{label}.%j.out
export {exports} POLARS_MAX_THREADS=8
{PY} {REPO}/scripts/explore_glob_tabeval.py --run {run_dir(arm, seed, legs)} --label {label} --legs {legs} {score_args}
echo "=== JOB DONE exit=$? ==="
""")
    sj = sh(["sbatch", "--parsable", jcf]).strip()
    print(f"{arm}: run {jid} -> score {sj}", flush=True)


def stage_cal(_a):
    for arm, cal in GRID.items():
        submit(arm, cal, 2, "ssp245", CELLS, 420, arm, "--truth-seed 2 --fold 1")


def stage_pick(_a):
    rows = []
    for arm in GRID:
        f = os.path.join(EVAL, f"scores_{arm}.csv")
        if not os.path.exists(f):
            print(f"{arm}: no score yet")
            continue
        d = pl.read_csv(f).row(0, named=True)
        L = abs(math.log(d["stems_ratio"])) + abs(math.log(d["agb_per_stem_ratio"]))
        rows.append(dict(arm=arm, cal=GRID[arm], stems=d["stems_ratio"], bpt=d["agb_per_stem_ratio"],
                         pass_rate=d["pass_rate"], slope=d["resp_n_per_patch_slope_deatt"], L=L))
    for r in rows:
        print(f"{r['arm']:12s} {json.dumps(r['cal']):24s} stems {r['stems']:.3f} biomass/tree {r['bpt']:.3f} "
              f"pass {r['pass_rate']:.3f} slope {r['slope']:.2f} L {r['L']:.3f}")
    pick = {}
    for fam, arms in FAMILY.items():
        rs = [r for r in rows if r["arm"] in arms]
        if len(rs) == len(arms):
            pick[fam] = min(rs, key=lambda r: r["L"])
            print(f"family {fam}: winner {pick[fam]['arm']} {pick[fam]['cal']} L {pick[fam]['L']:.3f}")
    json.dump(pick, open(os.path.join(EVAL, "a4_pick.json"), "w"), indent=1)


def stage_confirm(_a):
    pick = json.load(open(os.path.join(EVAL, "a4_pick.json")))
    for fam, r in pick.items():
        arm = f"A4{fam}_GS370"
        submit(arm, r["cal"], 8, "ssp370", None, 400, arm, "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["cal", "pick", "confirm"])
    a = ap.parse_args()
    {"cal": stage_cal, "pick": stage_pick, "confirm": stage_confirm}[a.stage](a)


if __name__ == "__main__":
    sys.exit(main())
