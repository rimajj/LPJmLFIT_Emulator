#!/usr/bin/env python3
"""Train and score one arm of the learned daily model: five training-only members, then the ensemble.

  members <prefix>_3x256_seed0..4   scripts/f2_train.py --train-only  (gpu, ~5 min each)
  -> ensemble <prefix>E_5seed       scripts/f2_train.py --ensemble    (gpu, free runs + score, ~1-4 h)
Network size and inputs as arm C (f2_chain_new_legs.COMMON); anything after `--` is passed to both steps
(e.g. `-- --carbon-head physical`). Then: python scripts/f2_relative_score.py <control> <prefix>E_5seed

Usage: python scripts/f2_chain_arm.py <prefix> --train-legs a,b --test-legs c,d [--dry-run] [-- extra args]
"""

import argparse
import sys

from f2_chain_new_legs import COMMON, SEEDS, sbatch_python


def main():
    argv, extra = (sys.argv[1:], [])
    if "--" in argv:
        i = argv.index("--")
        argv, extra = argv[:i], argv[i + 1 :]
    ap = argparse.ArgumentParser()
    ap.add_argument("prefix")
    ap.add_argument("--train-legs", required=True)
    ap.add_argument("--test-legs", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    legs = ["--train-legs", a.train_legs, "--test-legs", a.test_legs]
    gpu = dict(part="gpu", qos="gpushort", ncpus=32, gres="gpu:1", dry=a.dry_run)
    mem = [
        sbatch_python(f"f2-{a.prefix}-s{s}", "scripts/f2_train.py",
                      ["--tag", f"{a.prefix}_3x256_seed{s}", "--seed", str(s), "--train-only", *legs, *COMMON,
                       *extra], [], time="01:30:00", **gpu)  # fmt: skip
        for s in SEEDS
    ]
    ens = ",".join(f"{a.prefix}_3x256_seed{s}" for s in SEEDS)
    sbatch_python(f"f2-{a.prefix}E", "scripts/f2_train.py",
                  ["--tag", f"{a.prefix}E_5seed", "--ensemble", ens, "--deep-tau", "365", *legs, *COMMON, *extra],
                  mem, time="06:00:00", **gpu)  # fmt: skip


if __name__ == "__main__":
    main()
