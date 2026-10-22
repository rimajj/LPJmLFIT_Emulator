"""The tree POPULATION of a cell: distributions, virtual trees and functional-diversity indices
(ADR 0363, 0365).

Optional part of a release (``population.json`` present). Port of the inference half of
``scripts/explore_panel_popmap.py`` (arm ``AQ``) and ``scripts/explore_panel_popjoint.py``.

* **Distributions.** For each of eight variables of the living trees >= 5 m (height, biomass per
  tree, SLA, wood density, maximum rooting depth ``D95max``, drought threshold ``minwscal``, the
  ACTUAL 95 % rooting depth ``D95``, age) nine quantile levels (1 ... 99 %), each its own
  gradient-boosted model of the departure from the cell's anchor, read from the structure map's
  inputs plus the quantity's own anchor and start level. Crossing levels are sorted. The seven
  tree-type shares: one model each, clipped at 0 and renormalised.
* **Virtual trees** (``virtual_trees``): N = round(25 x tree count per patch) trees whose values are
  the emulated quantile functions read at the ranks of real DONOR trees (the run's own 2019 trees),
  so the joint structure between variables is the donors' (Schaake shuffle). Donors are drawn
  without repeats while the roster lasts (ADR 0363 sec. 12: a repeated donor gives near-identical
  trees and biased functional evenness).
* **Indices** (``diversity_indices``): community means / variances of the four standardised traits,
  functional richness, divergence, evenness, dispersion, Rao's Q, type Shannon / Simpson, height
  Shannon / Gini.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import numpy as np

POP_VARS = ["Height", "agb", "SLA", "Wooddens", "D95max", "minwscal", "D95", "Age"]
PS = np.array([0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99])
PN = ["p01", "p05", "p10", "p25", "p50", "p75", "p90", "p95", "p99"]
SHARES = [f"share_{t}" for t in range(7)]
POP_Q = [f"{v}_{pn}" for v in POP_VARS for pn in PN] + SHARES
NPATCH = 25
TRAITS = ["SLA", "Wooddens", "D95max", "minwscal"]
INDICES = (
    [f"cwm_{t}" for t in TRAITS]
    + [f"cwv_{t}" for t in TRAITS]
    + [
        "fric",
        "fdiv",
        "feve",
        "fdis",
        "raoq",
        "type_shannon",
        "type_simpson",
        "h_shannon",
        "h_gini",
        "n",
    ]
)


@dataclass
class PopSetup:
    """Per-cell population inputs, N cells (the order of the release's ``Setup``), years year0 ..
    year0 + Y - 1.

    anc: quantity -> (N, Y) anchors; s0 / memoff: quantity -> (N,) the run's own 2000-2019 level
    and its offset from
    the training runs' mean; donor roster: ``ptr`` (N + 1,) offsets into the flat per-tree arrays
    ``trees``
    (name -> (T,), names Type + POP_VARS) -- the run's own living trees >= 5 m of 2019."""

    cell: np.ndarray
    anc: dict
    s0: dict
    memoff: dict
    ptr: np.ndarray
    trees: dict

    @classmethod
    def load(cls, path):
        z = np.load(path)
        return cls(
            cell=z["cell"],
            anc={q: z[f"anc/{q}"] for q in POP_Q},
            s0={q: z[f"s0/{q}"] for q in POP_Q},
            memoff={q: z[f"memoff/{q}"] for q in POP_Q},
            ptr=z["ptr"],
            trees={k: z[f"tree/{k}"] for k in ["Type", *POP_VARS]},
        )

    def donor(self, i):
        a, b = int(self.ptr[i]), int(self.ptr[i + 1])
        return {k: v[a:b] for k, v in self.trees.items()}


class PopulationMaps:
    def __init__(self, cfg, boosters):
        self.cfg, self.b = cfg, boosters
        self.log_eps = cfg["log_eps"]  # variable -> e: target ln((v + e) / (anchor + e))

    @classmethod
    def load(cls, d):
        p = os.path.join(d, "population.json")
        if not os.path.exists(p):
            return None
        import lightgbm as lgb

        with open(p) as fh:
            cfg = json.load(fh)
        return cls(
            cfg, {q: lgb.Booster(model_file=os.path.join(d, f"lgb_pop_{q}.txt")) for q in POP_Q}
        )

    def predict(self, feat):
        """feat: name -> (N,), the structure map's inputs plus anc_ / s0_ / memoff_ of every
        population quantity.
        Returns name -> (N,): ``<var>_<pn>`` (sorted across levels) and ``share_<t>`` (sum 1 where
        any is > 0)."""
        out = {}
        for v in POP_VARS:
            cols = []
            for pn in PN:
                q = f"{v}_{pn}"
                X = np.column_stack([feat[c] for c in self.cfg["features"][q]])
                p, anc = self.b[q].predict(X, num_threads=1), feat[f"anc_{q}"]
                e = self.log_eps.get(v)
                cols.append((anc + e) * np.exp(p) - e if e else p + anc)
            Q = np.sort(np.column_stack(cols), axis=1)
            for j, pn in enumerate(PN):
                out[f"{v}_{pn}"] = Q[:, j]
        S = []
        for q in SHARES:
            X = np.column_stack([feat[c] for c in self.cfg["features"][q]])
            S.append(self.b[q].predict(X, num_threads=1) + feat[f"anc_{q}"])
        S = np.clip(np.nan_to_num(np.column_stack(S)), 0.0, None)
        tot = S.sum(1, keepdims=True)
        S = S / np.where(tot > 0, tot, 1.0)
        for t, q in enumerate(SHARES):
            out[q] = S[:, t]
        return out


# ------------------------------------------------------------------------------------------------ v
def qfun(q, u):
    """Quantile function through the nine levels (q sorted), linear tails, clipped at 0."""
    x = np.interp(u, PS, q)
    lo, hi = u < PS[0], u > PS[-1]
    x[lo] = q[0] - (q[1] - q[0]) / (PS[1] - PS[0]) * (PS[0] - u[lo])
    x[hi] = q[-1] + (q[-1] - q[-2]) / (PS[-1] - PS[-2]) * (u[hi] - PS[-1])
    return np.maximum(x, 0.0)


def _ranks01(v, rng):
    o = np.lexsort((rng.random(len(v)), v))
    r = np.empty(len(v))
    r[o] = np.arange(len(v))
    return (r + 0.5) / len(v)


def _largest_remainder(n, s):
    x = n * s
    k = np.floor(x).astype(int)
    rest = n - k.sum()
    if rest > 0:
        k[np.argsort(-(x - k))[:rest]] += 1
    return k


def _draw_unique(k, types, rng):
    used = np.zeros(len(types), bool)
    idx, typ = [], []
    for t in range(7):
        pool = np.flatnonzero((types == t) & ~used)
        take = rng.choice(pool, min(k[t], len(pool)), replace=False) if k[t] else np.array([], int)
        used[take] = True
        idx.append(take)
        typ.append(np.full(len(take), t))
    got = [len(x) for x in idx]
    for t in range(7):
        short = k[t] - got[t]
        if short <= 0:
            continue
        rest = np.flatnonzero(~used)
        take = rng.choice(rest, min(short, len(rest)), replace=False)
        used[take] = True
        if short > len(take):
            take = np.concatenate([take, rng.choice(len(types), short - len(take), replace=True)])
        idx.append(take)
        typ.append(np.full(len(take), t))
    return np.concatenate(idx), np.concatenate(typ)


def virtual_trees(n_per_patch, shares, quantiles, donor, seed):
    """One cell: shares (7,), quantiles var -> (9,) sorted, donor name -> (T,). Returns name ->
    (N,) with ``Type``
    and every variable of POP_VARS, or None (no trees, or no donor trees)."""
    N = int(round(NPATCH * max(float(n_per_patch), 0.0)))
    if N <= 0 or len(donor["Type"]) == 0:
        return None
    rng = np.random.default_rng(seed)
    s = (
        shares
        if shares.sum() > 0
        else np.bincount(donor["Type"].astype(int), minlength=7) / len(donor["Type"])
    )
    idx, typ = _draw_unique(_largest_remainder(N, s), donor["Type"].astype(int), rng)
    out = {"Type": typ}
    for v, q in quantiles.items():
        out[v] = qfun(q, _ranks01(donor[v][idx], rng))
    return out


# ------------------------------------------------------------------------------------------------ i
def _shannon(c):
    p = c[c > 0] / c.sum()
    return float(-(p * np.log(p)).sum())


def diversity_indices(vt, const, nmax=1500, rng_seed=0):
    """vt: name -> (N,) trees (Type, Height, the four traits); const: trait -> {mean, sd, log}
    (population.json
    ``diversity_constants``). Same code as scripts/fdiversity.py, used on the original's trees in
    the scores."""
    from scipy.sparse.csgraph import minimum_spanning_tree
    from scipy.spatial import ConvexHull, QhullError
    from scipy.spatial.distance import pdist, squareform

    n = len(vt["Type"])
    r = {k: np.nan for k in INDICES}
    r["n"] = float(n)
    if n == 0:
        return r
    X = np.column_stack(
        [
            ((np.log(np.maximum(vt[t], 1e-12)) if const[t]["log"] else vt[t]) - const[t]["mean"])
            / const[t]["sd"]
            for t in TRAITS
        ]
    )
    for i, t in enumerate(TRAITS):
        r[f"cwm_{t}"], r[f"cwv_{t}"] = float(X[:, i].mean()), float(X[:, i].var())
    r["fdis"] = float(np.linalg.norm(X - X.mean(0), axis=1).mean())
    tc = np.bincount(vt["Type"].astype(int), minlength=7)
    r["type_shannon"], r["type_simpson"] = _shannon(tc), float(1.0 - ((tc / n) ** 2).sum())
    h = vt["Height"]
    r["h_shannon"] = _shannon(np.bincount(np.clip((h // 5).astype(int), 0, 20)))
    hs = np.sort(h)
    r["h_gini"] = (
        float((2 * np.arange(1, n + 1) - n - 1).dot(hs) / (n * hs.sum()))
        if hs.sum() > 0
        else np.nan
    )
    S = X if n <= nmax else X[np.random.default_rng(rng_seed).choice(n, nmax, replace=False)]
    m = S.shape[0]
    if m >= 2:
        d = pdist(S)
        r["raoq"] = float(2.0 * d.sum() / m**2)
        if m >= 3:
            ew = minimum_spanning_tree(squareform(d)).tocoo().data
            if ew.sum() > 0:
                pew, k = ew / ew.sum(), m - 1
                r["feve"] = float((np.minimum(pew, 1.0 / k).sum() - 1.0 / k) / (1.0 - 1.0 / k))
    if m >= 6:
        try:
            hull = ConvexHull(S)
            r["fric"] = float(hull.volume)
            dG = np.linalg.norm(S - S[hull.vertices].mean(0), axis=1)
            r["fdiv"] = float(dG.mean() / (np.abs(dG - dG.mean()).mean() + dG.mean()))
        except (QhullError, ValueError):
            pass
    return r
