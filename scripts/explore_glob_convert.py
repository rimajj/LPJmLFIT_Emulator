#!/usr/bin/env python3
"""explore_glob_convert.py -- LINE X, convert M. Billing's GLOBAL LPJmL-FIT runs (standard random/inherited
traits) to parquet with line X's own converter (scripts/explore_de_convert.py), so they have exactly the
layout, dtypes, row order and gates of the Germany tables the emulator arms already read.

Owner instruction 2026-10-08: use Billing's global runs with randomly initialised traits for training the
emulators instead of the Germany runs; *"the emulator needs to work with every model version"*.

Source (READ-ONLY, owned by billing):  /p/projects/pbscience/billing/LPJmLFIT/global/
  GCM/<historical|ssp126|ssp245|ssp370>/GFDL-ESM4/r1_<m>/output/ind.csv
      "r1" = Billing's "full diversity: standard LPJmL-FIT" (run/FD_EF/simulation_protocol.txt);
      "prescribe_estab": false.  r2-r6 / rSLA (traits prescribed from r1) and r0 (everything-is-everywhere)
      are NOT standard runs and are excluded on purpose.  Each member has its OWN 1000-yr spin-up
      (random_seed = m), historical 1901-2014 (tree table 1985-2014), and each ssp leg restarts from THAT
      member's restart_2014_nv.lpj and writes its tree table 2071-2100 only (2015-2070 has gridded outputs
      in output_transient/ but NO tree table).  CO2 constant from 2014.  25 patches.  Humidity: huss with
      "relative_humidity": false (consistent -- NOT the Germany 2071+ defect).
      Members used: 2,3,4,6,7,8 (Feb-5-2026 build, all four legs) and 9,10 (May-26-2026 build).
      Excluded: r1_1 (its ssp legs were run with a Dec-2025 build from a historical run that was later
      overwritten by a Jan-2026 re-run, so the historical table on disk is not their parent) and r1_5 (the
      historical leg was re-run in Jun 2026 over the restart its Feb-build ssp126/245 legs started from;
      its ssp370 re-run failed).
  reanalysis/r1_<m>/output/ind.csv   GSWP3-W5E5 obsclim, 1901-2019, tree table 1990-2019, Oct-2026 builds
      (Billing's current development model: corrected GLOBFIRM, height_max as a trait, bark-thickness fire
      mortality; r1_5/r1_6/r1_7 were each run with a re-tuned rebuild).  Members 1,2,3,5,6,7 (r1_4 failed).

CELL INDEX: these runs use /p/projects/biodiversity/input_VERSION2/grid.bin (longitude-major;
Hainich = 28008),
NOT the orderA grid of the repo's existing global ground truth (Hainich = 42490).  Never join the two on Cell
without a remap (CLAUDE.md section 1).

Output:  /p/projects/open/Jamir/esm_land_emulator_data/billing_global/ind/<gcm>/<scen>/s<m>/<window>/cb=NN/
         (three digits from block 100 on)
         (+ ind_dev/ = Cell % 10 == 0, _gates/, _census/, _gates.csv), Cell stored as Int32, cb = Cell // 500.
         Windows: h1985 (historical), w2071 (ssp legs), h1990 (reanalysis).  Rows: the stock writer, so only
         trees taller than 5 m plus grass.

Usage:  python scripts/explore_glob_convert.py list | run <idx> | collect
        python scripts/explore_glob_convert.py submit <array> [part qos ncpus time]
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_convert as cv  # noqa: E402

SRC = "/p/projects/pbscience/billing/LPJmLFIT/global"
OUT = "/p/projects/open/Jamir/esm_land_emulator_data/billing_global"
GCM_MEMBERS = (2, 3, 4, 6, 7, 8, 9, 10)
GCM_LEGS = (("historical", "h1985"), ("ssp126", "w2071"), ("ssp245", "w2071"), ("ssp370", "w2071"))
REAN_MEMBERS = (1, 2, 3, 5, 6, 7)

cv.OUT_ROOT = f"{OUT}/ind"
cv.DEV_ROOT = f"{OUT}/ind_dev"
cv.GATE_DIR = f"{cv.OUT_ROOT}/_gates"
cv.CENSUS_DIR = f"{cv.OUT_ROOT}/_census"
cv.DUPKEY_DIR = f"{cv.OUT_ROOT}/_dupkeys"
cv.GATES_CSV = f"{cv.OUT_ROOT}/_gates.csv"
cv.NCELL = 67420
cv.NPATCH = 25
cv.SCHEMA = {**cv.SCHEMA, "Cell": pl.Int32}
SOIL_RAW = "/p/projects/biodiversity/input_VERSION2/soil_new_67420.bin"  # raw uint8, no header


def rock_cells() -> list[int]:
    """Soil code 13 ("rock and ice") cells, which LPJmL skips -- from the headerless raw soil file
    the runs read."""
    v = np.fromfile(SOIL_RAW, dtype=np.uint8)
    if v.size != cv.NCELL:
        raise RuntimeError(f"{SOIL_RAW}: {v.size} cells, expected {cv.NCELL}")
    return [int(i) for i in np.nonzero(v == 13)[0]]


def _entry(out: list, gcm: str, scen: str, seed: int, win: str, src: str) -> None:
    member = f"{gcm}_{scen}_s{seed}_{win}"
    out.append(dict(
        idx=len(out), gcm=gcm, scen=scen, seed=seed, window=win, src=src, member=member,
        out_dir=f"{cv.OUT_ROOT}/{gcm}/{scen}/s{seed}/{win}",
        dev_file=f"{cv.DEV_ROOT}/{member}.parquet",
        gate_json=f"{cv.GATE_DIR}/{member}.json",
        census_file=f"{cv.CENSUS_DIR}/{member}.parquet",
    ))  # fmt: skip


def manifest() -> list[dict]:
    out: list[dict] = []
    for m in GCM_MEMBERS:
        for scen, win in GCM_LEGS:
            _entry(out, "GFDL-ESM4", scen, m, win, f"{SRC}/GCM/{scen}/GFDL-ESM4/r1_{m}/output/ind.csv")
    for m in REAN_MEMBERS:
        _entry(out, "GSWP3-W5E5", "obsclim", m, "h1990", f"{SRC}/reanalysis/r1_{m}/output/ind.csv")
    return out


cv.manifest = manifest
cv.rock_cells = rock_cells


def submit(args: list[str]) -> int:
    array = args[0]
    part = args[1] if len(args) > 1 else "standard"
    qos = args[2] if len(args) > 2 else "short"
    ncpus = int(args[3]) if len(args) > 3 else 16
    tlim = args[4] if len(args) > 4 else "04:00:00"
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logdir = f"{root}/logs"
    jdir = f"{OUT}/_jobs"
    os.makedirs(logdir, exist_ok=True)
    os.makedirs(jdir, exist_ok=True)
    jcf = f"{jdir}/globconv_{time.strftime('%Y%m%d_%H%M%S')}.jcf"
    body = f"""#!/usr/bin/env bash
#SBATCH --job-name=X-glob-conv
#SBATCH --account=waldspektrum
#SBATCH --partition={part}
#SBATCH --qos={qos}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task={ncpus}
#SBATCH --time={tlim}
#SBATCH --array={array}
#SBATCH --output={logdir}/X-glob-conv.%A_%a.out
#SBATCH --error={logdir}/X-glob-conv.%A_%a.out
set -uo pipefail
export POLARS_MAX_THREADS={ncpus}
export OMP_NUM_THREADS={ncpus}
echo "=== X-glob-conv task $SLURM_ARRAY_TASK_ID on $(hostname) at $(date) ==="
{cv.PY} {os.path.abspath(__file__)} run $SLURM_ARRAY_TASK_ID
code=$?
echo "=== JOB DONE tag=X-glob-conv task=$SLURM_ARRAY_TASK_ID exit=$code ==="
exit $code
"""
    with open(jcf, "w") as f:
        f.write(body)
    res = subprocess.run(["sbatch", jcf], capture_output=True, text=True)
    print(res.stdout.strip(), res.stderr.strip())
    print(f"jcf: {jcf}")
    return res.returncode


if __name__ == "__main__":
    for d in (cv.OUT_ROOT, cv.DEV_ROOT, cv.GATE_DIR, cv.CENSUS_DIR, cv.DUPKEY_DIR):
        os.makedirs(d, exist_ok=True)
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    if stage == "list":
        for m in manifest():
            print(m["idx"], m["member"], m["src"])
    elif stage == "run":
        sys.exit(cv.run(int(sys.argv[2])))
    elif stage == "collect":
        cv.collect()
        print(cv.GATES_CSV)
    elif stage == "submit":
        sys.exit(submit(sys.argv[2:]))
    else:
        print(__doc__)
        sys.exit(2)
