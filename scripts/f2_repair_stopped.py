#!/usr/bin/env python3
"""Retrain the ensemble members of one arm that early stopping cut short, then re-run its ensemble (ADR 0336).

f2_train.py trains on a one-cycle learning-rate schedule spanning all epochs; with the default --patience 2 a
validation bump at the high mid-cycle rate stops a member before the rate anneals, and it keeps a mid-cycle state
(validation loss ~0.058-0.088 against ~0.054 for a full member). This script reads each member's own args from its
log, re-trains every stopped member under `<member>_full` with --patience = epochs (cannot stop), and re-runs the
ensemble with the original ensemble args under `<prefix>Ef_5seed`. Nothing is overwritten.

Usage: python scripts/f2_repair_stopped.py <prefix> [<prefix> ...] [--dry-run]     e.g.  D47 V L C U
"""

import ast
import os
import sys

from f2_chain_new_legs import sbatch_python

RUNS = "/p/projects/open/Jamir/esm_land_emulator_data/f2/runs"
SKIP = {"tag", "seed", "ensemble", "train_only", "device", "patience"}


def read_args(tag):
    with open(os.path.join(RUNS, tag, "log.txt")) as f:
        head = f.readline()
    return ast.literal_eval(head.split("args=", 1)[1].strip())


def n_epochs_done(tag):
    with open(os.path.join(RUNS, tag, "log.txt")) as f:
        return sum(line.startswith("epoch ") for line in f)


def to_cli(args):
    out = []
    for k, v in args.items():
        if k in SKIP or (v == "" and k != "test_legs"):  # an empty value is the default; the wrapper drops ""
            continue
        out += [f"--{k.replace('_', '-')}", "none" if (k == "test_legs" and v == "") else str(v)]
    return out


def repair(prefix, dry):
    ens_tag = f"{prefix}E_5seed"
    ens = read_args(ens_tag)
    members = ens["ensemble"].split(",")
    deps, new_members = [], []
    for m in members:
        ma = read_args(m)
        if n_epochs_done(m) >= ma["epochs"]:
            new_members.append(m)
            continue
        new = f"{m}_full"
        new_members.append(new)
        if os.path.exists(os.path.join(RUNS, new, "model.pt")):
            print(f"{new}: exists, reused")
            continue
        cli = ["--tag", new, "--seed", str(ma["seed"]), "--train-only", "--patience", str(ma["epochs"])]
        deps.append(sbatch_python(f"f2-{prefix}f-s{ma['seed']}", "scripts/f2_train.py", cli + to_cli(ma), [],
                                  part="gpu", qos="gpushort", ncpus=32, gres="gpu:1", time="01:30:00",
                                  dry=dry))  # fmt: skip
    if new_members == members:
        print(f"{prefix}: no stopped member, nothing to do")
        return
    cli = ["--tag", f"{prefix}Ef_5seed", "--ensemble", ",".join(new_members)] + to_cli(ens)
    sbatch_python(f"f2-{prefix}Ef", "scripts/f2_train.py", cli, [d for d in deps if not d.startswith("<")],
                  part="gpu", qos="gpushort", ncpus=32, gres="gpu:1", time="06:00:00", dry=dry)  # fmt: skip


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    for p in [a for a in sys.argv[1:] if not a.startswith("--")]:
        repair(p, dry)
