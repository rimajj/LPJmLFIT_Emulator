#!/usr/bin/env python3
"""explore_de_sh_timing.py — LINE X, Germany data-driven emulator, shared item SH10: SINGLE-CORE TIMING HARNESS.

Times any SH6 stepper the same way: the first 100 dev cells, MPI-ESM1-2-HR ssp370 2015-2044 from the 2014 state
(30 years), ONE thread (OMP/MKL/OPENBLAS/POLARS/torch = 1), time.process_time per engine stage (climate provider,
stepper, engine bookkeeping, writing), at the 250-patch production state and at a 25-patch state (Patch % 10 == 0,
the global setting). Reports core-seconds per cell-year and per stem-year. GPU time, if a stepper uses one, is NOT
converted into core-seconds — report it separately.

Reference for the original model: 12.4 core-s per cell-year [SOURCE: production Historical run, 2048 tasks x 3556 s
/ (65 yr x 9067 cells), 250 patches, includes I/O and MPI]. A ratio to it is only meaningful at the same patch count;
quote both numbers with the patch count beside them. The emulator's own number here EXCLUDES the cost of turning
daily forcing into the annual climate features (the provider reads them precomputed). That cost is NOT measured by
this harness yet — say so beside every number until it is.

  explore_de_sh_timing.py submit --arm A --stepper module:Class [--kwargs JSON]   (priority node, one thread)
  explore_de_sh_timing.py run    ...                                               (inside the job)
-> shared/timing/<arm>.json
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "POLARS_MAX_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"

import argparse  # noqa: E402
import json  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_engine as en  # noqa: E402
import polars as pl  # noqa: E402

OUT = os.path.join(en.XDE, "shared", "timing")
ORIGINAL_CORE_S_PER_CELL_YEAR_250 = 12.4


def stage_run(a):
    try:
        import torch

        torch.set_num_threads(1)
    except ImportError:
        pass
    os.makedirs(OUT, exist_ok=True)
    res = {"arm": a.arm, "stepper": a.stepper, "kwargs": a.kwargs, "cells": a.ncells, "years": "2015-2044",
           "threads": 1, "original_core_s_per_cell_year_250": ORIGINAL_CORE_S_PER_CELL_YEAR_250, "settings": {}}
    for step in (1, 10):
        ns = argparse.Namespace(arm=f"timing_{a.arm}", stepper=a.stepper, kwargs=a.kwargs, gcm="MPI-ESM1-2-HR", seed=1,
                                start=2014, end=2044, legs="ssp370", rep=1, clim="actual", cellset="dev",
                                chunk_size=a.ncells, chunks=None, cells=None, patch_step=step)
        cells = en.chunks_of(ns)[0]
        od = os.path.join(en.RUNS, "_timing", a.arm, f"patch_step{step}")
        os.makedirs(od, exist_ok=True)
        w0 = time.time()
        m = en.run_chunk(ns, 0, cells, od)
        wall = time.time() - w0
        stems = pl.scan_parquet(os.path.join(od, "chunk_000", "*.parquet")).filter(
            (pl.col("isdead") == 0) & (pl.col("Year") > 2014)).select(pl.len()).collect().item()
        tot = sum(m["timing_core_s"].values())
        npatch = 250 // step
        res["settings"][f"{npatch}_patches"] = {
            "cell_years": m["cell_years"], "stem_years": stems, "core_s_by_stage": m["timing_core_s"],
            "core_s_per_cell_year": tot / m["cell_years"],
            "core_s_per_cell_year_step_only": m["timing_core_s"]["step"] / m["cell_years"],
            "core_s_per_stem_year": tot / max(stems, 1), "wall_s": wall,
            "speedup_vs_original_at_250": (ORIGINAL_CORE_S_PER_CELL_YEAR_250 / (tot / m["cell_years"]))
            if npatch == 250 else None}
        en.log(f"{a.arm} {npatch} patches: {tot / m['cell_years']:.4f} core-s/cell-year")
    res["note"] = ("core-s exclude the daily->annual climate-feature cost (precomputed); compare to the original only "
                   "at 250 patches; the 25-patch number is the global-setting cost, not a fidelity claim")
    json.dump(res, open(os.path.join(OUT, f"{a.arm}.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


def stage_submit(a):
    logs = os.path.join(REPO, "logs")
    args = f"--arm '{a.arm}' --stepper '{a.stepper}' --ncells {a.ncells}" + (f" --kwargs '{a.kwargs}'" if a.kwargs
                                                                            else "")
    jcf = os.path.join(en.XDE, "_jobs", f"X-de-timing-{a.arm}.jcf")
    with open(jcf, "w") as f:
        f.write(f"""#!/bin/bash
#SBATCH --job-name=X-de-timing-{a.arm}
#SBATCH --account=waldspektrum
#SBATCH --partition=priority
#SBATCH --qos=priority
#SBATCH --cpus-per-task=2  # 2 cpus for the memory (~11 GB); every library is pinned to ONE thread
#SBATCH --time=04:00:00
#SBATCH --output={logs}/X-de-timing-{a.arm}.%j.out
{en.tr.PY} {os.path.abspath(__file__)} run {args}
echo "=== JOB DONE timing exit=$? ==="
""")
    print(subprocess.run(["sbatch", "--parsable", jcf], capture_output=True, text=True, check=True).stdout.strip())


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["run", "submit"])
    ap.add_argument("--arm", required=True)
    ap.add_argument("--stepper", required=True)
    ap.add_argument("--kwargs")
    ap.add_argument("--ncells", type=int, default=100)
    a = ap.parse_args(argv)
    {"run": stage_run, "submit": stage_submit}[a.stage](a)


if __name__ == "__main__":
    main()
