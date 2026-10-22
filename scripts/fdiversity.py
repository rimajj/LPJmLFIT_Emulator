#!/usr/bin/env python3
"""fdiversity.py -- functional-biodiversity indices of one tree community (ADR 0363 sec. 5), applied identically to
the original's trees (scripts/build_panel_yearly_v2.py rosters) and to the emulator's virtual trees.

Traits: ln SLA, wood density, ln D95max, minwscal, standardised with FIXED constants (config/fdiversity_constants.json,
written by `fdiversity.py constants` from every living tree >= 5 m of run m1 in 2019), so indices are comparable
across cells, runs and years. Every tree counts once (individuals, unweighted).

Indices (Villeger, Mason & Mouillot 2008, Ecology 89:2290; Laliberte & Legendre 2010, Ecology 91:299; Rao 1982):
  cwm_<t>, cwv_<t>  mean and variance of each standardised trait
  fric              volume of the 4-D convex hull (NaN below 6 trees or for a degenerate hull)
  fdiv              divergence: dGbar / (mean |dG - dGbar| + dGbar), dG = distance to the hull vertices' centroid
  feve              evenness of the minimum spanning tree's branch lengths
  fdis              mean distance to the centroid
  raoq              mean pairwise distance over all ordered pairs (sum d_ij / n^2)
  type_shannon, type_simpson   over the seven tree types
  h_shannon         over 5 m height classes; h_gini  Gini coefficient of height
Above NMAX trees, raoq / feve / fric / fdiv use a fixed-seed subsample of NMAX trees.
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONST = os.path.join(REPO, "config", "fdiversity_constants.json")
TRAITS = ["SLA", "Wooddens", "D95max", "minwscal"]
LOGT = {"SLA", "D95max"}
NMAX = 1500
INDICES = ([f"cwm_{t}" for t in TRAITS] + [f"cwv_{t}" for t in TRAITS]
           + ["fric", "fdiv", "feve", "fdis", "raoq", "type_shannon", "type_simpson", "h_shannon", "h_gini", "n"])


def load_constants() -> dict:
    return json.load(open(CONST))


def standardise(cols: dict[str, np.ndarray], c: dict) -> np.ndarray:
    out = []
    for t in TRAITS:
        x = np.log(np.maximum(cols[t], 1e-12)) if t in LOGT else cols[t]
        out.append((x - c[t]["mean"]) / c[t]["sd"])
    return np.column_stack(out)


def _shannon(counts: np.ndarray) -> float:
    p = counts[counts > 0] / counts.sum()
    return float(-(p * np.log(p)).sum())


def indices(X: np.ndarray, types: np.ndarray, height: np.ndarray, rng_seed: int = 0) -> dict[str, float]:
    from scipy.sparse.csgraph import minimum_spanning_tree
    from scipy.spatial import ConvexHull, QhullError
    from scipy.spatial.distance import pdist, squareform

    n = X.shape[0]
    r: dict[str, float] = {k: np.nan for k in INDICES}
    r["n"] = float(n)
    if n == 0:
        return r
    for i, t in enumerate(TRAITS):
        r[f"cwm_{t}"] = float(X[:, i].mean())
        r[f"cwv_{t}"] = float(X[:, i].var())
    cen = X.mean(0)
    r["fdis"] = float(np.linalg.norm(X - cen, axis=1).mean())
    tc = np.bincount(types.astype(int), minlength=7)
    r["type_shannon"] = _shannon(tc)
    r["type_simpson"] = float(1.0 - ((tc / n) ** 2).sum())
    hc = np.bincount(np.clip((height // 5).astype(int), 0, 20))
    r["h_shannon"] = _shannon(hc)
    hs = np.sort(height)
    r["h_gini"] = float((2 * np.arange(1, n + 1) - n - 1).dot(hs) / (n * hs.sum())) if hs.sum() > 0 else np.nan
    S = X
    if n > NMAX:
        S = X[np.random.default_rng(rng_seed).choice(n, NMAX, replace=False)]
    m = S.shape[0]
    if m >= 2:
        d = pdist(S)
        r["raoq"] = float(2.0 * d.sum() / m**2)
        if m >= 3:
            mst = minimum_spanning_tree(squareform(d)).tocoo()
            ew = mst.data
            if ew.sum() > 0:
                pew = ew / ew.sum()
                k = m - 1
                r["feve"] = float((np.minimum(pew, 1.0 / k).sum() - 1.0 / k) / (1.0 - 1.0 / k))
    if m >= 6:
        try:
            h = ConvexHull(S)
            r["fric"] = float(h.volume)
            g = S[h.vertices].mean(0)
            dG = np.linalg.norm(S - g, axis=1)
            dbar = dG.mean()
            r["fdiv"] = float(dbar / (np.abs(dG - dbar).mean() + dbar))
        except (QhullError, ValueError):
            pass
    return r


def stage_constants() -> None:
    import polars as pl

    d = pl.read_parquet("/p/projects/reformit/Jamir/esm_land_emulator_data/xpanel_rosters/m1_hist.parquet")
    out = {}
    for t in TRAITS:
        x = d[t].to_numpy().astype(float)
        x = np.log(x) if t in LOGT else x
        out[t] = {"mean": float(x.mean()), "sd": float(x.std()), "log": t in LOGT}
    out["_source"] = "every living tree (types 0-6, height >= 5 m) of panel run m1 in 2019; ADR 0363 sec. 5"
    out["_n_trees"] = d.height
    json.dump(out, open(CONST, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "constants":
        stage_constants()
