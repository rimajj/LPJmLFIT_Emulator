#!/usr/bin/env python3
"""Dump the count table to raw Float64 matrices + a JSON manifest for the native-Julia DRF.

Reads the small ``slow_count_table_seed{SEED}.parquet`` (built by build_slow_count_table.py) and
writes, into ``$OUT`` (default the same dir), a zero-dependency payload the Julia OOD experiment
(``scripts/flux_ood_experiment.jl``) reads with pure Base IO (no Parquet.jl / no dep):

  X.f64        row-major (n x p) Float64 feature matrix (ALL numeric feature columns; nulls -> col mean)
  y.f64        length-n target (n_living)
  holdout.u8   length-n 0/1 warm+dry OOD mask
  cell.i32     length-n cell id (for cell-grouped train/val splits)
  manifest.json  {n, p, colnames, flux_idx, clim_idx, boundary_idx, target, ...}

The manifest carries the FLUX and CLIMATE column index groups so the Julia side slices the two
channels for the falsifiable ADR-0020 comparison without re-deriving the schema.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_slow_count_table as bct  # noqa: E402


def main() -> int:
    seed = int(os.environ.get("SEED", "1"))
    in_dir = os.environ.get("OUT", "/p/tmp/jamirp/slow_count")
    out_dir = os.environ.get("MATOUT", in_dir)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(in_dir, f"slow_count_table_seed{seed}.parquet")
    df = pl.read_parquet(path)
    print(f"== read {path}: {df.height} rows x {df.width} cols")

    id_cols = {"Cell", "Patch", "Year", "holdout", "n_living", "n_dead", "n_recruit"}
    feat_cols = [c for c in df.columns if c not in id_cols and df[c].dtype.is_numeric()]

    # column groups (ADR 0020): flux channel drops raw climate; climate channel is the DirectEmulator's.
    boundary = [c for c in bct.BOUNDARY_COLS if c in feat_cols] + (["co2"] if "co2" in feat_cols else [])
    daily_stat_cols = [c for c in feat_cols if c.split("_")[0] in
                       ("gpp", "npp", "transp", "rootmoist") and c not in bct.CLIMATE_COLS
                       and any(k in c for k in ("peak", "eoy", "gs_mean", "min", "doy"))]
    flux_cols = ([c for c in feat_cols if c.startswith(("flux_", "state_", "ar_"))]
                 + boundary + daily_stat_cols)
    clim_cols = [c for c in bct.CLIMATE_COLS if c in feat_cols] + boundary
    # de-dup while preserving order
    flux_cols = list(dict.fromkeys(flux_cols))
    clim_cols = list(dict.fromkeys(clim_cols))

    # build the numeric matrix; fill nulls/NaN with per-column mean of finite values
    X = np.empty((df.height, len(feat_cols)), dtype="<f8")
    for j, c in enumerate(feat_cols):
        col = df[c].to_numpy().astype("float64")
        finite = np.isfinite(col)
        mu = col[finite].mean() if finite.any() else 0.0
        col = np.where(finite, col, mu)
        X[:, j] = col
    y = df["n_living"].to_numpy().astype("<f8")
    holdout = df["holdout"].to_numpy().astype("uint8")
    cell = df["Cell"].to_numpy().astype("<i4")

    col_index = {c: i for i, c in enumerate(feat_cols)}
    manifest = {
        "seed": seed, "n": int(df.height), "p": len(feat_cols),
        "colnames": feat_cols,
        "flux_idx": [col_index[c] for c in flux_cols],
        "clim_idx": [col_index[c] for c in clim_cols],
        "boundary_idx": [col_index[c] for c in boundary],
        "flux_cols": flux_cols, "clim_cols": clim_cols, "boundary_cols": boundary,
        "target": "n_living",
        "n_holdout": int(holdout.sum()), "n_train": int((holdout == 0).sum()),
    }
    X.tofile(os.path.join(out_dir, "X.f64"))
    y.tofile(os.path.join(out_dir, "y.f64"))
    holdout.tofile(os.path.join(out_dir, "holdout.u8"))
    cell.tofile(os.path.join(out_dir, "cell.i32"))
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    # a trivial line-based manifest the pure-Base Julia reader consumes (no JSON dep). 0-based indices.
    with open(os.path.join(out_dir, "manifest.txt"), "w") as f:
        f.write(f"n\t{df.height}\n")
        f.write(f"p\t{len(feat_cols)}\n")
        f.write("flux_idx\t" + " ".join(str(col_index[c]) for c in flux_cols) + "\n")
        f.write("clim_idx\t" + " ".join(str(col_index[c]) for c in clim_cols) + "\n")
        f.write("boundary_idx\t" + " ".join(str(col_index[c]) for c in boundary) + "\n")
        f.write("colnames\t" + " ".join(feat_cols) + "\n")
        f.write("flux_cols\t" + " ".join(flux_cols) + "\n")
        f.write("clim_cols\t" + " ".join(clim_cols) + "\n")
    print(f"== wrote X {X.shape} (flux p={len(flux_cols)}, clim p={len(clim_cols)}, "
          f"shared boundary={len(boundary)}) to {out_dir}")
    print(f"== flux_cols: {flux_cols}")
    print(f"== clim_cols: {clim_cols}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
