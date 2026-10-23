#!/usr/bin/env python3
"""build_release_daily_swap.py -- a copy of an existing emulator release with ONLY its daily networks replaced
(ADR 0367: the soil-texture networks of ADR 0348 in the complete emulator).

Every file of the base release except daily.npz and release.json is copied unchanged (its old runs/ are not: they
belong to the old daily model); daily.npz is exported from the f2 members <prefix>0..4 by
build_emulator_release.export_daily; release.json is the base's, annotated. Refuses an existing --out.

Gates (abort before release.json is written):
  (1) numpy == PyTorch on 20 000 real teacher-forced input rows (export_daily, < 1e-5);
  (T) --soil-texture: the package's soil columns of every setup's cells == f2_train.soil_columns, bit for bit;
  (C) every copied file is byte-identical to the base's.

  python scripts/build_release_daily_swap.py --base .../release/v2 --out .../release/v2tex \
      --daily-members T_3x256_seed --soil-texture
"""

from __future__ import annotations

import argparse
import filecmp
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
from lpjmlfit_emulator.landemu import Setup  # noqa: E402
from lpjmlfit_emulator.landemu.daily import DailyModel  # noqa: E402

SKIP = {"daily.npz", "release.json", "runs"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--daily-members", dest="daily_members", required=True,
                    help="f2 run-tag prefix of the five daily networks (<prefix>0..4)")
    ap.add_argument("--soil-texture", dest="soil_texture", action="store_true")
    ap.add_argument("--adr", default="0367")
    a = ap.parse_args()
    if os.path.exists(a.out):
        sys.exit(f"refusing to overwrite {a.out}")
    os.makedirs(a.out)
    names = sorted(n for n in os.listdir(a.base) if n not in SKIP)
    for n in names:
        src = os.path.join(a.base, n)
        assert os.path.isfile(src), f"unexpected directory in the base release: {src}"
        shutil.copy2(src, os.path.join(a.out, n))
    members = [f"{a.daily_members}{i}" for i in range(5)]
    _, rel = BR.export_daily(a.out, members=members, soil=a.soil_texture)

    if a.soil_texture:
        import f2_train as F

        dm = DailyModel.load(os.path.join(a.out, "daily.npz"))
        for n in names:
            if n.startswith("setup_") and n.endswith(".npz"):
                su = Setup.load(os.path.join(a.out, n))
                ref = F.soil_columns(pl.DataFrame({"Cell": np.asarray(su.cell).astype(np.int64)}))
                got = dm.soil_columns(su.soil_code)
                eq = np.array_equal(got, ref)
                BR.log(f"GATE (T) {n}: package soil columns == f2_train.soil_columns for {len(su.cell)} cells: {eq}")
                assert eq, "the package's soil texture differs from the training's"

    bad = [n for n in names if not filecmp.cmp(os.path.join(a.base, n), os.path.join(a.out, n), shallow=False)]
    BR.log(f"GATE (C) {len(names)} copied files byte-identical to the base: {not bad}")
    assert not bad, f"copies differ: {bad}"

    with open(os.path.join(a.base, "release.json")) as fh:
        cfg = json.load(fh)
    base_name = os.path.basename(os.path.normpath(a.base))
    cfg.update({
        "version": os.path.basename(os.path.normpath(a.out)), "base_release": base_name,
        "base_daily_members": cfg.get("daily_members"), "daily_members": members, "soil_texture": a.soil_texture,
        "built": time.strftime("%Y-%m-%d %H:%M"), "git_sha": BR.git_sha(), "adr": a.adr,
    })
    cfg["gates"] = dict(cfg.get("gates", {}), daily_numpy_vs_torch_max_rel=rel, copies_identical=True,
                        soil_columns_exact=bool(a.soil_texture) or None)
    with open(os.path.join(a.out, "release.json"), "w") as fh:
        json.dump(cfg, fh, indent=1)
    BR.log(f"wrote {a.out} (base {base_name}, daily {members[0]}..4, texture {a.soil_texture})")


if __name__ == "__main__":
    main()
