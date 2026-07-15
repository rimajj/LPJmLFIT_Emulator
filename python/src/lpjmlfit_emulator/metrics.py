"""Distributional evaluation metrics for the slow emulator (component S) prototype.

These are REAL, pure-numpy implementations (no scipy / POT dependency) so the test
suite runs inside the reused conda env ``/home/jamirp/.conda/envs/py311_new``
without extra installs. They are deliberately a small, tested SUBSET of the full
metric library used by the PRIOR sibling emulator at
``/p/projects/open/Jamir/emulator/src/metrics.py`` (multivariate energy distance +
its seed-split null floor, correlation-matrix Frobenius distance, per-quantile
errors, moment NRMSE / bias / R2). Reuse / port that module when the metric panel
grows; keep THIS file dependency-free.

Evaluation discipline (inherited from the sibling emulator; DESIGN.md §"Reuse"):
  * The seed1-vs-seed2 NOISE FLOOR is the yardstick, not zero error. The published
    per-cell floor on cell-mean variables is ~11% for agb, roughly
    ``{Height: 0.020, agb: 0.113, npp: 0.062, LAI: 0.025}``
    (``emulator/src/eval_presentday_critical.py``).
  * ALWAYS report per-cell error MAGNITUDE against the per-cell floor FIRST; never
    lead with a pooled metric.
  * Fixed seed 42 for all stochastic evaluation.

All 1-D metrics compare a set of TRUE samples against a set of EMULATED samples for
one variable / cell / year; samples need NOT be paired or equal-length.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike

__all__ = [
    "SEED",
    "PUBLISHED_NOISE_FLOOR",
    "wasserstein1d",
    "ks_statistic",
    "noise_floor",
    "per_cell_relative_error",
]

#: Fixed RNG seed for all stochastic evaluation (project-wide discipline).
SEED = 42

#: Published seed1-vs-seed2 per-cell noise floor (relative), from the sibling
#: emulator (``emulator/src/eval_presentday_critical.py``). agb ~ 11%.
PUBLISHED_NOISE_FLOOR = {"Height": 0.020, "agb": 0.113, "npp": 0.062, "LAI": 0.025}

_EPS = 1e-12


def _clean(x: ArrayLike) -> np.ndarray:
    """Flatten to a 1-D float array and drop non-finite entries."""
    arr = np.asarray(x, dtype=float).ravel()
    return arr[np.isfinite(arr)]


def _emd_1d(a: np.ndarray, b: np.ndarray) -> float:
    """Unnormalized 1-Wasserstein (earth-mover) distance between 1-D empirical samples.

    Equals the integral of ``|F_a - F_b|`` over the real line (same algorithm as
    ``scipy.stats.wasserstein_distance``), in pure numpy. Inputs must be non-empty.
    """
    a = np.sort(a)
    b = np.sort(b)
    grid = np.concatenate([a, b])
    grid.sort()
    deltas = np.diff(grid)
    cdf_a = np.searchsorted(a, grid[:-1], side="right") / a.size
    cdf_b = np.searchsorted(b, grid[:-1], side="right") / b.size
    return float(np.sum(np.abs(cdf_a - cdf_b) * deltas))


def wasserstein1d(a: ArrayLike, b: ArrayLike) -> float:
    """IQR-normalized 1-Wasserstein distance between two 1-D samples.

    The raw earth-mover distance is divided by the inter-quartile range of the
    POOLED sample, giving a unitless, comparable-across-variables distance that is
    symmetric and 0 iff the two empirical distributions coincide. Returns NaN if
    either sample is empty after removing non-finite values.

    (The sibling emulator's ``wasserstein_1d_normalized`` normalizes by the TRUTH
    IQR for its noise-floor tables; here we use the pooled IQR so the prototype's
    metric is a proper symmetric distance for the property tests.)
    """
    a, b = _clean(a), _clean(b)
    if a.size == 0 or b.size == 0:
        return float("nan")
    dist = _emd_1d(a, b)
    pooled = np.concatenate([a, b])
    iqr = float(np.subtract(*np.percentile(pooled, [75, 25])))
    if iqr > _EPS:
        scale = iqr
    else:
        std = float(np.std(pooled))
        scale = std if std > _EPS else 1.0
    return dist / scale


def ks_statistic(a: ArrayLike, b: ArrayLike) -> float:
    """Two-sample Kolmogorov-Smirnov statistic ``sup|F_a - F_b|`` in [0, 1] (pure numpy).

    0 iff the empirical CDFs coincide. Returns NaN if either sample is empty.
    """
    a, b = _clean(a), _clean(b)
    if a.size == 0 or b.size == 0:
        return float("nan")
    a = np.sort(a)
    b = np.sort(b)
    grid = np.concatenate([a, b])
    cdf_a = np.searchsorted(a, grid, side="right") / a.size
    cdf_b = np.searchsorted(b, grid, side="right") / b.size
    return float(np.max(np.abs(cdf_a - cdf_b)))


def noise_floor(seed1: ArrayLike, seed2: ArrayLike, reduce: str = "median") -> float:
    """Per-cell relative disagreement between two independent seeds -- THE YARDSTICK.

    ``seed1`` / ``seed2`` are aligned per-cell summaries of the same variable (e.g.
    cell-mean agb) from two RNG seeds of the ground-truth model. Returns the reduced
    (``"median"`` or ``"mean"``) symmetric relative absolute difference

        ``|seed1 - seed2| / (0.5 * (|seed1| + |seed2|))``

    which is ``>= 0`` and is the irreducible error against which an emulator is
    measured: at or below this floor the emulator is indistinguishable from a fresh
    stochastic run of the truth. For agb this is ~0.11 (see PUBLISHED_NOISE_FLOOR).
    Raises ValueError on length mismatch; returns NaN if nothing finite remains.
    """
    s1 = np.asarray(seed1, dtype=float).ravel()
    s2 = np.asarray(seed2, dtype=float).ravel()
    if s1.size != s2.size:
        raise ValueError(
            f"seed1/seed2 must be aligned per-cell (got {s1.size} vs {s2.size})"
        )
    denom = 0.5 * (np.abs(s1) + np.abs(s2))
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = np.abs(s1 - s2) / denom
    rel = rel[np.isfinite(rel)]
    if rel.size == 0:
        return float("nan")
    return float(np.median(rel) if reduce == "median" else np.mean(rel))


def per_cell_relative_error(pred: ArrayLike, truth: ArrayLike) -> np.ndarray:
    """Per-cell relative error ``|pred - truth| / |truth|`` (array, one value per cell).

    Report this against the per-cell noise floor FIRST (never lead with a pooled
    number). Cells with ``|truth| ~ 0`` yield NaN; all finite entries are ``>= 0``.
    Raises ValueError on length mismatch.
    """
    p = np.asarray(pred, dtype=float).ravel()
    t = np.asarray(truth, dtype=float).ravel()
    if p.size != t.size:
        raise ValueError(
            f"pred/truth must be aligned per-cell (got {p.size} vs {t.size})"
        )
    with np.errstate(divide="ignore", invalid="ignore"):
        err = np.abs(p - t) / np.where(np.abs(t) > _EPS, np.abs(t), np.nan)
    return err
