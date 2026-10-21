#!/usr/bin/env python3
"""Ensembles of already-trained daily-model members, one free-run + score job each (ADR 0348 arm N).

Usage: python scripts/f2_ensemble_sizes.py <tag>=<member,member,...> [...] [--after JID:JID]
           [--dry-run] [-- extra f2_train args]
e.g.   python scripts/f2_ensemble_sizes.py DE_1seed=D_3x256_seed0 DE_3seed=D_3x256_seed0,... \
           --after 123 -- --train-legs ... --test-legs none
Each job runs `f2_train.py --tag <tag> --ensemble <members> --deep-tau 365 <COMMON> <extra>` on the
gpu
partition (as f2_chain_arm.py's ensemble step); the one-core timing is in runs/<tag>/summary.md.
"""

import argparse
import sys

from f2_chain_new_legs import COMMON, sbatch_python


def main():
    argv, extra = (sys.argv[1:], [])
    if "--" in argv:
        i = argv.index("--")
        argv, extra = argv[:i], argv[i + 1 :]
    ap = argparse.ArgumentParser()
    ap.add_argument("ensembles", nargs="+", help="tag=member,member,...")
    ap.add_argument("--after", default="", help="job ids to wait for (afterok), e.g. 123:456")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    dep = [j for j in a.after.split(":") if j]
    gpu = dict(part="gpu", qos="gpushort", ncpus=32, gres="gpu:1", dry=a.dry_run)
    for spec in a.ensembles:
        tag, members = spec.split("=", 1)
        args = ["--tag", tag, "--ensemble", members, "--deep-tau", "365", *COMMON, *extra]
        sbatch_python(f"f2-{tag}", "scripts/f2_train.py", args, dep, time="08:00:00", **gpu)


if __name__ == "__main__":
    main()
