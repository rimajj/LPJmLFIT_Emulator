#!/usr/bin/env python3
"""Train and score arm P of the learned daily model: arm C with the structured carbon head (ADR 0332).

  five training-only members P_3x256_seed0..4   scripts/f2_train.py --train-only --carbon-head physical  (gpu)
  -> the ensemble PE_5seed, free-run + score     scripts/f2_train.py --ensemble  --carbon-head physical  (gpu)
Same legs, sizes and inputs as arm C (scripts/f2_chain_new_legs.py); the only difference is --carbon-head.
Then: python scripts/f2_relative_score.py CE_5seed PE_5seed

Usage: python scripts/f2_chain_carbon_head.py [--dry-run]
"""

import argparse

from f2_chain_new_legs import COMMON, SEEDS, TEST, TRAIN_C, sbatch_python

HEAD = ["--carbon-head", "physical"]
LEGS = ["--train-legs", ",".join(TRAIN_C), "--test-legs", ",".join(TEST)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    gpu = dict(part="gpu", qos="gpushort", ncpus=32, gres="gpu:1", dry=a.dry_run)
    mem = [
        sbatch_python(f"f2-P-s{s}", "scripts/f2_train.py",
                      ["--tag", f"P_3x256_seed{s}", "--seed", str(s), "--train-only", *LEGS, *COMMON, *HEAD],
                      [], time="01:30:00", **gpu)  # fmt: skip
        for s in SEEDS
    ]
    ens = ",".join(f"P_3x256_seed{s}" for s in SEEDS)
    sbatch_python("f2-PE", "scripts/f2_train.py",
                  ["--tag", "PE_5seed", "--ensemble", ens, "--deep-tau", "365", *LEGS, *COMMON, *HEAD],
                  mem, time="04:00:00", **gpu)  # fmt: skip


if __name__ == "__main__":
    main()
