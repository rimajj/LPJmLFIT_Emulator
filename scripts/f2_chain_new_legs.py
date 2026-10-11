#!/usr/bin/env python3
"""Chain everything after new daily runs of the original, for the learned daily model (ADR 0328).

  runs (submitted by trackd_panel.py submit-legs; ids in PANEL/jobs_<first leg>.json)
    -> one collector per (member, leg)        scripts/trackd_collect_panel.py   (priority, 16 cpus)
    -> the array builder for the new legs     scripts/f2_build_daily_table.py   (priority, 32 cpus)
    -> five training-only members of arm C    scripts/f2_train.py --train-only  (gpu)
    -> arm C's ensemble, free-run + score     scripts/f2_train.py --ensemble    (gpu)
    -> the control (old members, re-scored)   scripts/f2_train.py --ensemble    (gpu, after builder)
Each step depends on the previous (afterok): a failure leaves the rest pending, never a wrong score.

Usage: python scripts/f2_chain_new_legs.py [--dry-run]
"""

import argparse
import json
import os
import re
import subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL = "/p/tmp/jamirp/trackD/panel"
PY = "/home/jamirp/.conda/envs/py311_new/bin/python"
NEW = [f"{g}_{s}_daily" for g in ("gfdl-esm4", "ipsl-cm6a-lr", "mri-esm2-0")
       for s in ("ssp126", "ssp370", "ssp585")]  # fmt: skip
TRAIN_C = ["ctl_obs", "mpi-esm1-2-hr_ssp126", "mpi-esm1-2-hr_ssp370"] + [
    x for x in NEW if not x.startswith("ipsl")
]
TEST = ["mpi-esm1-2-hr_ssp585", "ukesm1-0-ll_ssp370"] + [x for x in NEW if x.startswith("ipsl")]
COMMON = ["--hidden", "256", "--layers", "3", "--npp-head", "ra", "--drop-inputs", "huss"]
SEEDS = range(5)


def sbatch_python(tag, script, args, dep, part, qos, ncpus, time, gres="", dry=False):
    env = dict(os.environ, PARTITION=part, QOS=qos, NCPUS=str(ncpus), TIME=time)
    env.pop("DEPENDENCY", None)
    env.pop("GRES", None)
    if dep:
        env["DEPENDENCY"] = "afterok:" + ":".join(dep)
    if gres:
        env["GRES"] = gres
    cmd = [os.path.join(REPO, "scripts", "sbatch_python.sh"), tag, script, *args]
    if dry:
        print("DRY", tag, dep, " ".join(args))
        return f"<{tag}>"
    out = subprocess.run(cmd, env=env, cwd=REPO, capture_output=True, text=True, check=True).stdout
    jid = re.search(rf"{re.escape(tag)}\.(\d+)\.out", out).group(1)
    print(f"{tag}: {jid}  (after {','.join(dep) or '-'})", flush=True)
    return jid


def collect(member, leg, dep, dry):
    d = os.path.join(PANEL, f"m{member}", leg)
    j = f"""#!/bin/bash
#SBATCH --job-name=f2col-m{member}-{leg[:12]}
#SBATCH --account=waldspektrum
#SBATCH --partition=priority
#SBATCH --qos=priority
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=02:00:00
#SBATCH --dependency=afterok:{dep}
#SBATCH --output={REPO}/logs/f2col-m{member}-{leg}.%j.out
export POLARS_MAX_THREADS=16
{PY} {REPO}/scripts/trackd_collect_panel.py {member} {leg}
rc=$?; echo "=== JOB DONE exit=$rc ==="; exit $rc
"""
    p = os.path.join(d, "collect.jcf")
    if dry:
        print("DRY collect", member, leg, dep)
        return f"<col{member}{leg}>"
    open(p, "w").write(j)
    out = subprocess.run(["sbatch", p], capture_output=True, text=True, check=True).stdout
    return out.split()[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    runs = json.load(open(os.path.join(PANEL, f"jobs_{NEW[0]}.json")))
    cols = [collect(k, leg, runs[f"m{k}/{leg}"], a.dry_run) for k in (1, 2, 3, 4) for leg in NEW]
    print(f"collectors: {len(cols)}", flush=True)
    b = sbatch_python("f2-build-new", "scripts/f2_build_daily_table.py", ["--legs", ",".join(NEW)],
                      cols, "priority", "priority", 32, "04:00:00", dry=a.dry_run)  # fmt: skip
    gpu = dict(part="gpu", qos="gpushort", ncpus=32, gres="gpu:1", dry=a.dry_run)
    mem = [
        sbatch_python(
            f"f2-C-s{s}",
            "scripts/f2_train.py",
            [
                "--tag",
                f"C_3x256_seed{s}",
                "--seed",
                str(s),
                "--train-only",
                "--train-legs",
                ",".join(TRAIN_C),
                "--test-legs",
                ",".join(TEST),
                *COMMON,
            ],
            [b],
            time="01:30:00",
            **gpu,
        )  # fmt: skip
        for s in SEEDS
    ]
    ens = ",".join(f"C_3x256_seed{s}" for s in SEEDS)
    sbatch_python("f2-CE", "scripts/f2_train.py",
                  ["--tag", "CE_5seed", "--ensemble", ens, "--deep-tau", "365",
                   "--train-legs", ",".join(TRAIN_C), "--test-legs", ",".join(TEST), *COMMON],
                  mem, time="04:00:00", **gpu)  # fmt: skip
    ctl_test = TEST + [x for x in NEW if not x.startswith("ipsl")]
    hens = ",".join(f"H_3x256_seed{s}" for s in SEEDS)
    sbatch_python("f2-HEdr-x", "scripts/f2_train.py",
                  ["--tag", "HEdr_x", "--ensemble", hens, "--deep-tau", "365",
                   "--test-legs", ",".join(ctl_test), *COMMON],
                  [b], time="04:00:00", **gpu)  # fmt: skip


if __name__ == "__main__":
    main()
