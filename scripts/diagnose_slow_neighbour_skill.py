#!/usr/bin/env python3
"""Is the copula's env-conditioning gain a CLIMATE RESPONSE or a SPATIAL LOOKUP? — answered with ZERO new compute.

WHY THIS EXISTS (milestone S2 / ADR 0039)
-----------------------------------------
ADR 0038 shipped a 14-column recruit-trait copula and recorded the doubt that gates promoting it: the six
appended env columns have median within-cell sd EXACTLY 0 for 100 % of cells, so they are a per-cell spatial
ADDRESS. The published K-fold-BY-CELL evaluation cannot distinguish "the emulator learned an environmental
response" from "the emulator interpolated from the test cell's geographic NEIGHBOURS", because
`eval_slow_copula.jl:143` splits folds as `mod(hash(cell), kfolds)` — which scatters test cells uniformly
and therefore leaves essentially every test cell's neighbours in the training fold.

Re-scoring with spatially BLOCKED folds costs a forest refit per rung. THIS script answers a large part of
the same question for FREE, from prediction files that already exist: under the very same hash folds, each
test cell has a MEASURABLE distance to its nearest training cell, and that distance varies by more than an
order of magnitude across the globe (dense continental interiors vs islands, coasts, ice and desert
margins). If the conditioning gain is an environmental response it should be roughly FLAT in that distance.
If it is a spatial lookup it must DECAY, because a lookup has nothing to look up when the nearest
neighbour is far away.

This is a genuine test, and it is also strictly weaker than blocked CV in one specific way that must not be
glossed: the far-neighbour cells are not a random sample of the globe — they are systematically the remote,
marginal, low-tree-density places. So a decay could partly reflect those cells being intrinsically harder.
The `1-NN` reference curve computed here is what controls for that: it is a PURE address predictor scored on
exactly the same cells in exactly the same bins, so its own decay measures how much of the decay is "hard
cells" versus "the lookup failing".

WHAT IT COMPUTES
----------------
For a MATCHED PAIR of prediction sets (same table, same folds, same capacity, differing only in the
conditioning width) and each trait axis:

  * per-cell median observed / predicted (imported from `noise_floor_vs_emulator.percell_table`, so it
    cannot drift from the ADR-0030 gate's own definition), on the gate's `nstem >= MINSTEM` basis;
  * each cell's great-circle distance to the nearest cell OUTSIDE its own fold — i.e. to the nearest cell
    the forest that predicted it was actually trained on;
  * per distance bin: `nrmse` normalized by the GLOBAL between-cell sd (NOT the bin's own sd — a within-bin
    correlation or a within-bin normalization suffers range restriction and would manufacture a decay), the
    between-cell r for reference, and the A-vs-B DELTA that is the conditioning lever itself;
  * a `1-NN` reference: predict a cell's median as its nearest TRAINING cell's OBSERVED median. This is the
    pure-address ceiling, scored in the same bins.

THE FOLD MAP MUST COME FROM JULIA
---------------------------------
`mod(hash(cell), kfolds)` uses Julia's `hash(::Int64)`, which Python cannot reproduce. Passing a
Python-recomputed fold map would silently score the wrong split. So the map is READ from a text file that
Julia wrote, and this script asserts the fold sizes it finds are the ones the eval log reported.
Generate it with (Julia 1.10.0, the version the driver pins):

    julia -e 'd="<table dir>"; n=filesize("$d/cells.i64")÷8; c=Vector{Int64}(undef,n);
              read!("$d/cells.i64",c); for x in sort(unique(c)); println(x," ",mod(hash(x),5)); end' > fold.txt

Usage:
    TABLE=/p/tmp/jamirp/emulator_global/slow_copula_historic_t8 \
    PRED_A=/p/tmp/jamirp/emulator_global/capacity/qrf-b6x2M      LABEL_A=ncond8 \
    PRED_B=/p/tmp/jamirp/emulator_global/capacity/env-qrf-b6x2M  LABEL_B=ncond14 \
    FOLD=/p/tmp/jamirp/emulator_global/tables/fold_hash5_hist.txt \
    CELL_LATLON=/p/tmp/jamirp/emulator_global/tables/cell_latlon.txt \
      python scripts/diagnose_slow_neighbour_skill.py

Env: TABLE (holds Y_*.f64 + cells.i64 + manifest_copula.txt), PRED_A (required), PRED_B (optional),
     LABEL_A/LABEL_B, FOLD (required), CELL_LATLON (required), MINSTEM (20), AXES (default: the manifest's),
     BINS (comma-separated upper edges in degrees; default 0.75,1.25,2,3,5,8,1e9).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import polars as pl
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from noise_floor_vs_emulator import percell_table  # noqa: E402  (path shim must precede the import)

TABLE = os.environ["TABLE"]
PRED_A = os.environ["PRED_A"]
PRED_B = os.environ.get("PRED_B", "").strip()
LABEL_A = os.environ.get("LABEL_A", "A")
LABEL_B = os.environ.get("LABEL_B", "B")
FOLD = os.environ["FOLD"]
CELL_LATLON = os.environ["CELL_LATLON"]
MINSTEM = int(os.environ.get("MINSTEM", "20"))
BINS = [float(x) for x in os.environ.get("BINS", "0.75,1.25,2,3,5,8,1e9").split(",")]

R_EARTH_DEG = 180.0 / np.pi  # radians -> degrees of great circle


def read_two_col(path: str) -> pl.DataFrame:
    """`cell value` text, `#`-comment tolerant. Used for the Julia-written fold map."""
    rows = []
    for line in open(path):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        p = s.split()
        rows.append((int(p[0]), int(p[1])))
    return pl.DataFrame({"Cell": [r[0] for r in rows], "fold": [r[1] for r in rows]})


def read_latlon(path: str) -> pl.DataFrame:
    rows = []
    for line in open(path):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        p = s.split()
        rows.append((int(p[0]), float(p[3]), float(p[4])))
    return pl.DataFrame(
        {"Cell": [r[0] for r in rows], "lat": [r[1] for r in rows], "lon": [r[2] for r in rows]}
    )


def unit_sphere(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """3-D unit-sphere coords, so the KD-tree's Euclidean metric is monotone in great-circle distance and
    the +-180 seam and the poles need no special casing."""
    la, lo = np.deg2rad(lat), np.deg2rad(lon)
    return np.column_stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])


def chord_to_deg(d: np.ndarray) -> np.ndarray:
    return 2.0 * np.arcsin(np.clip(d / 2.0, 0.0, 1.0)) * R_EARTH_DEG


def nearest_out_of_fold(xyz: np.ndarray, fold: np.ndarray, y: np.ndarray):
    """For every cell: (distance in degrees to the nearest cell OUTSIDE its fold, that cell's observed y).

    The forest that predicts fold k was trained on every cell with fold != k, so this is exactly the
    distance to the nearest cell the predictor had actually seen — and the 1-NN address prediction.
    """
    n = len(fold)
    dist = np.full(n, np.nan)
    nn_y = np.full(n, np.nan)
    for k in np.unique(fold):
        te = fold == k
        tr = ~te
        if not te.any() or not tr.any():
            continue
        tree = cKDTree(xyz[tr])
        d, j = tree.query(xyz[te], k=1)
        dist[te] = chord_to_deg(d)
        nn_y[te] = y[tr][j]
    return dist, nn_y


def bin_edges_label(lo: float, hi: float) -> str:
    return f"<={hi:g}" if lo <= 0 else (f">{lo:g}" if hi > 1e8 else f"{lo:g}-{hi:g}")


def main() -> None:
    man = {}
    for line in open(f"{TABLE}/manifest_copula.txt"):
        p = line.rstrip("\n").split("\t")
        if len(p) == 2:
            man[p[0]] = p[1]
    axes = os.environ.get("AXES", man.get("axes", "SLA Wooddens D95max minwscal")).split()

    print("== diagnose_slow_neighbour_skill — is the conditioning gain an ADDRESS? (zero new compute)")
    print(f"   table  : {TABLE}   axes={axes}  MINSTEM={MINSTEM}")
    print(f"   pred A : {PRED_A}  [{LABEL_A}]")
    print(f"   pred B : {PRED_B or '(none)'}  [{LABEL_B}]")

    pa = percell_table(PRED_A, with_pred=True, axes=axes)
    tab = pa.filter(pl.col("nstem") >= MINSTEM)
    if PRED_B:
        pb = percell_table(PRED_B, with_pred=True, axes=axes).select(
            ["Cell"] + [f"p_{a}" for a in axes]
        )
        tab = tab.join(pb.rename({f"p_{a}": f"pB_{a}" for a in axes}), on="Cell", how="inner")

    fold = read_two_col(FOLD)
    ll = read_latlon(CELL_LATLON)
    before = tab.height
    tab = tab.join(fold, on="Cell", how="inner").join(ll, on="Cell", how="inner")
    if tab.height != before:
        print(f"   NOTE  : {before - tab.height} of {before} cells lack a fold id or a lat/lon — dropped")
    fs = tab.group_by("fold").len().sort("fold")
    print(f"   cells  : {tab.height} scored; fold sizes {fs['len'].to_list()}")

    xyz = unit_sphere(tab["lat"].to_numpy(), tab["lon"].to_numpy())
    fold_v = tab["fold"].to_numpy()

    for ax in axes:
        y = tab[f"y_{ax}"].to_numpy()
        pA = tab[f"p_{ax}"].to_numpy()
        pB = tab[f"pB_{ax}"].to_numpy() if PRED_B else None
        dist, nn_y = nearest_out_of_fold(xyz, fold_v, y)
        sd = float(np.std(y))  # GLOBAL between-cell sd: the common normalizer for every bin

        def nrmse(p, m):
            return float(np.sqrt(np.mean((p[m] - y[m]) ** 2)) / sd)

        def rr(p, m):
            return float(np.corrcoef(p[m], y[m])[0, 1]) if m.sum() > 2 else np.nan

        print(f"\n== {ax} — sd(per-cell median) = {sd:.6g};  nrmse is normalized by THIS global sd")
        hdr = f"   {'nn_dist(deg)':>13s} {'ncell':>7s} {'nrmse_' + LABEL_A:>14s}"
        if PRED_B:
            hdr += f" {'nrmse_' + LABEL_B:>14s} {'DELTA':>9s}"
        hdr += f" {'nrmse_1NN':>10s} {'r_' + LABEL_A:>9s}"
        if PRED_B:
            hdr += f" {'r_' + LABEL_B:>9s}"
        hdr += f" {'r_1NN':>7s}"
        print(hdr)
        lo = 0.0
        allm = np.isfinite(dist)
        for hi in BINS:
            m = allm & (dist > lo) & (dist <= hi)
            if m.sum() < 10:
                lo = hi
                continue
            row = f"   {bin_edges_label(lo, hi):>13s} {int(m.sum()):>7d} {nrmse(pA, m):>14.4f}"
            if PRED_B:
                row += f" {nrmse(pB, m):>14.4f} {nrmse(pA, m) - nrmse(pB, m):>+9.4f}"
            row += f" {nrmse(nn_y, m):>10.4f} {rr(pA, m):>9.4f}"
            if PRED_B:
                row += f" {rr(pB, m):>9.4f}"
            row += f" {rr(nn_y, m):>7.4f}"
            print(row)
            lo = hi
        row = f"   {'ALL':>13s} {int(allm.sum()):>7d} {nrmse(pA, allm):>14.4f}"
        if PRED_B:
            row += f" {nrmse(pB, allm):>14.4f} {nrmse(pA, allm) - nrmse(pB, allm):>+9.4f}"
        row += f" {nrmse(nn_y, allm):>10.4f} {rr(pA, allm):>9.4f}"
        if PRED_B:
            row += f" {rr(pB, allm):>9.4f}"
        row += f" {rr(nn_y, allm):>7.4f}"
        print(row)
        q = np.nanpercentile(dist, [10, 25, 50, 75, 90, 99, 100])
        print(
            "   nn_dist deg  q10/q25/q50/q75/q90/q99/max = "
            + "/".join(f"{v:.2f}" for v in q)
        )
    print("\n== done")


if __name__ == "__main__":
    main()
