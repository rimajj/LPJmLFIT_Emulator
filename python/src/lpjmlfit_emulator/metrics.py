# Ported from /p/projects/open/Jamir/emulator/src/metrics.py on 2026-07-16 (sibling is
# not a git repo; newest source mtime 2026-07-14). This repo is now the single source of
# truth for component S — do NOT sync with the sibling.
# Merged with the pre-existing prototype stub: the original pure-numpy metrics
# (``wasserstein1d``/``ks_statistic``/``noise_floor``/``per_cell_relative_error``) and the
# ``PUBLISHED_NOISE_FLOOR`` dict are kept as-is; the full sibling metric library
# (scipy-based) is added alongside them.
"""Distributional evaluation metrics for the slow emulator (component S).

Two layers live here, both first-class:

* The dependency-light PROTOTYPE metrics (pure numpy): ``wasserstein1d`` (symmetric,
  pooled-IQR-normalised), ``ks_statistic``, ``noise_floor`` and ``per_cell_relative_error``.
* The full metric library PORTED from the prior sibling emulator (scipy-based, declared
  dependency): 1-D Wasserstein (raw + true-IQR-normalised), KS, per-quantile errors,
  multivariate energy distance + its seed-split null floor, correlation-matrix Frobenius
  distance, and moment NRMSE / relative-bias / R2 aggregates.

Evaluation discipline (DESIGN.md §"Reuse"; see also ``lpjmlfit_emulator.evaluation``):
  * The seed1-vs-seed2 NOISE FLOOR is the yardstick, not zero error. The published
    per-cell floor on cell-mean variables is ~11% for agb, roughly
    ``{Height: 0.020, agb: 0.113, npp: 0.062, LAI: 0.025}``.
  * ALWAYS report per-cell error MAGNITUDE against the per-cell floor FIRST; never
    lead with a pooled metric.
  * Fixed seed 42 for all stochastic evaluation.

All 1-D metrics compare a set of TRUE samples against a set of EMULATED samples for
one variable / cell / year; samples need NOT be paired or equal-length.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike
from scipy import stats as sps
from scipy.spatial.distance import cdist

__all__ = [
    "SEED",
    "PUBLISHED_NOISE_FLOOR",
    "QUANTILES",
    # prototype (pure-numpy) metrics
    "wasserstein1d",
    "ks_statistic",
    "noise_floor",
    "per_cell_relative_error",
    # ported marginal metrics
    "wasserstein_1d",
    "wasserstein_1d_normalized",
    "ks_stat",
    "quantile_errors",
    "marginal_metrics",
    # ported joint / multivariate metrics
    "energy_distance_mv",
    "energy_distance_null",
    "corr_frobenius",
    "corr_matrices",
    # ported aggregate / moment metrics
    "nrmse",
    "relative_bias",
    "r2",
    "moment_series_metrics",
    "aggregate_error",
]

#: Fixed RNG seed for all stochastic evaluation (project-wide discipline).
SEED = 42

#: Published seed1-vs-seed2 per-cell noise floor (relative), from the sibling
#: emulator (``eval_presentday_critical.py``). agb ~ 11%.
PUBLISHED_NOISE_FLOOR = {"Height": 0.020, "agb": 0.113, "npp": 0.062, "LAI": 0.025}

#: Quantiles (percent) reported by the marginal metrics.
QUANTILES = [5, 25, 50, 75, 95]

_EPS = 1e-12


def _clean(x: ArrayLike) -> np.ndarray:
    """Flatten to a 1-D float array and drop non-finite entries."""
    arr = np.asarray(x, dtype=float).ravel()
    return arr[np.isfinite(arr)]


# ==========================================================================
# Prototype (pure-numpy) metrics — kept dependency-light for the property tests
# ==========================================================================
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
        raise ValueError(f"seed1/seed2 must be aligned per-cell (got {s1.size} vs {s2.size})")
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
        raise ValueError(f"pred/truth must be aligned per-cell (got {p.size} vs {t.size})")
    with np.errstate(divide="ignore", invalid="ignore"):
        err = np.abs(p - t) / np.where(np.abs(t) > _EPS, np.abs(t), np.nan)
    return err


# ==========================================================================
# Ported marginal (1-D) metrics (scipy-based)
# ==========================================================================
def wasserstein_1d(true, pred):
    """Raw 1-Wasserstein (earth-mover) distance between two 1-D samples."""
    true, pred = _clean(true), _clean(pred)
    if true.size == 0 or pred.size == 0:
        return np.nan
    return float(sps.wasserstein_distance(true, pred))


def wasserstein_1d_normalized(true, pred):
    """Wasserstein scaled by the TRUE distribution's IQR (unitless, comparable across vars).

    Note: this normalisation is by the truth IQR (not the pooled IQR), so it is NOT
    symmetric in ``(true, pred)`` — it is the sibling's noise-floor-table convention.
    """
    true, pred = _clean(true), _clean(pred)
    if true.size == 0 or pred.size == 0:
        return np.nan
    iqr = np.subtract(*np.percentile(true, [75, 25]))
    scale = iqr if iqr > 1e-12 else (np.std(true) if np.std(true) > 1e-12 else 1.0)
    return float(sps.wasserstein_distance(true, pred) / scale)


def ks_stat(true, pred):
    """Two-sample Kolmogorov-Smirnov statistic via ``scipy.stats.ks_2samp`` (in [0, 1])."""
    true, pred = _clean(true), _clean(pred)
    if true.size == 0 or pred.size == 0:
        return np.nan
    return float(sps.ks_2samp(true, pred).statistic)


def quantile_errors(true, pred, quantiles=QUANTILES):
    """Per-quantile true/pred values with absolute and relative errors."""
    true, pred = _clean(true), _clean(pred)
    if true.size == 0 or pred.size == 0:
        return {f"q{q}_abs_err": np.nan for q in quantiles}
    qt = np.percentile(true, quantiles)
    qp = np.percentile(pred, quantiles)
    out = {}
    for q, a, b in zip(quantiles, qt, qp, strict=False):
        out[f"q{q}_true"] = float(a)
        out[f"q{q}_pred"] = float(b)
        out[f"q{q}_abs_err"] = float(abs(a - b))
        out[f"q{q}_rel_err"] = float(abs(a - b) / abs(a)) if abs(a) > 1e-12 else np.nan
    return out


def marginal_metrics(true, pred, quantiles=QUANTILES):
    """Full 1-D marginal comparison for one variable/year."""
    m = {
        "n_true": int(_clean(true).size),
        "n_pred": int(_clean(pred).size),
        "wasserstein": wasserstein_1d(true, pred),
        "wasserstein_norm": wasserstein_1d_normalized(true, pred),
        "ks": ks_stat(true, pred),
        "mean_true": float(np.mean(_clean(true))) if _clean(true).size else np.nan,
        "mean_pred": float(np.mean(_clean(pred))) if _clean(pred).size else np.nan,
        "sd_true": float(np.std(_clean(true))) if _clean(true).size else np.nan,
        "sd_pred": float(np.std(_clean(pred))) if _clean(pred).size else np.nan,
    }
    m.update(quantile_errors(true, pred, quantiles))
    return m


# ==========================================================================
# Ported joint / multivariate metrics
# ==========================================================================
def energy_distance_mv(X_true, X_pred, standardize=True, max_n=2000, seed=0, n_repeats=3):
    """Multivariate energy distance.

    ``D^2 = 2 E||X-Y|| - E||X-X'|| - E||Y-Y'||`` averaged over ``n_repeats``
    subsamples of size ``max_n`` for tractability. Variables standardized (by pooled
    std) so all contribute comparably. Returns ``sqrt(D^2)`` (>= 0; 0 iff identical).
    """
    X = np.asarray(X_true, float)
    Y = np.asarray(X_pred, float)
    X = X[np.isfinite(X).all(1)]
    Y = Y[np.isfinite(Y).all(1)]
    if X.shape[0] < 5 or Y.shape[0] < 5:
        return np.nan
    if standardize:
        mu = X.mean(0)
        sd = X.std(0)
        sd[sd < 1e-12] = 1.0
        X = (X - mu) / sd
        Y = (Y - mu) / sd
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_repeats):
        xi = X[rng.choice(X.shape[0], min(max_n, X.shape[0]), replace=False)]
        yi = Y[rng.choice(Y.shape[0], min(max_n, Y.shape[0]), replace=False)]
        d_xy = cdist(xi, yi).mean()
        d_xx = cdist(xi, xi).mean()
        d_yy = cdist(yi, yi).mean()
        d2 = 2 * d_xy - d_xx - d_yy
        vals.append(max(d2, 0.0))
    return float(np.sqrt(np.mean(vals)))


def energy_distance_null(X_true, standardize=True, max_n=2000, seed=0, n_repeats=3):
    """Irreducible floor: energy distance between two independent halves of the TRUE sample.

    An emulator's energy distance should be compared against this floor (a value near
    the floor = indistinguishable from a fresh draw of the truth).
    """
    X = np.asarray(X_true, float)
    X = X[np.isfinite(X).all(1)]
    if X.shape[0] < 10:
        return np.nan
    rng = np.random.default_rng(seed)
    perm = rng.permutation(X.shape[0])
    half = X.shape[0] // 2
    return energy_distance_mv(
        X[perm[:half]],
        X[perm[half:]],
        standardize=standardize,
        max_n=max_n,
        seed=seed,
        n_repeats=n_repeats,
    )


def corr_frobenius(X_true, X_pred, method="spearman"):
    """Frobenius norm of the difference of correlation matrices (joint-structure preservation)."""
    X = np.asarray(X_true, float)
    Y = np.asarray(X_pred, float)
    X = X[np.isfinite(X).all(1)]
    Y = Y[np.isfinite(Y).all(1)]
    if X.shape[0] < 5 or Y.shape[0] < 5 or X.shape[1] < 2:
        return np.nan
    if method == "spearman":
        Ct = sps.spearmanr(X).correlation
        Cp = sps.spearmanr(Y).correlation
    else:
        Ct = np.corrcoef(X, rowvar=False)
        Cp = np.corrcoef(Y, rowvar=False)
    Ct = np.atleast_2d(Ct)
    Cp = np.atleast_2d(Cp)
    diff = np.nan_to_num(Ct - Cp)
    return float(np.linalg.norm(diff, "fro"))


def corr_matrices(X, cols, method="spearman"):
    """Return the correlation matrix (for plotting true vs pred heatmaps)."""
    X = np.asarray(X, float)
    X = X[np.isfinite(X).all(1)]
    if method == "spearman":
        C = sps.spearmanr(X).correlation
    else:
        C = np.corrcoef(X, rowvar=False)
    return np.atleast_2d(C)


# ==========================================================================
# Ported aggregate / moment metrics (paper-comparable)
# ==========================================================================
def nrmse(true, pred, norm="mean"):
    """Normalized RMSE across a series (e.g. per-year moments). norm in {mean,range,std}."""
    true, pred = _clean(true), _clean(pred)
    if true.size == 0:
        return np.nan
    rmse = np.sqrt(np.mean((true - pred) ** 2))
    if norm == "mean":
        denom = abs(np.mean(true))
    elif norm == "range":
        denom = np.ptp(true)
    else:
        denom = np.std(true)
    return float(rmse / denom) if denom > 1e-12 else np.nan


def relative_bias(true, pred):
    """Mean signed relative bias ``mean(pred - true) / mean(true)``."""
    true, pred = _clean(true), _clean(pred)
    if true.size == 0:
        return np.nan
    denom = np.mean(true)
    return float(np.mean(pred - true) / denom) if abs(denom) > 1e-12 else np.nan


def r2(true, pred):
    """Coefficient of determination between two aligned series."""
    true, pred = _clean(true), _clean(pred)
    if true.size < 2:
        return np.nan
    ss_res = np.sum((true - pred) ** 2)
    ss_tot = np.sum((true - np.mean(true)) ** 2)
    return float(1 - ss_res / ss_tot) if ss_tot > 1e-12 else np.nan


def moment_series_metrics(true_series, pred_series):
    """NRMSE / relative-bias / R2 between two aligned series (e.g. per-year means)."""
    return {
        "nrmse_mean": nrmse(true_series, pred_series, "mean"),
        "nrmse_range": nrmse(true_series, pred_series, "range"),
        "rel_bias": relative_bias(true_series, pred_series),
        "r2": r2(true_series, pred_series),
    }


def aggregate_error(true_total, pred_total):
    """Absolute + relative error of a single aggregate total (e.g. tree count, total biomass)."""
    if abs(true_total) < 1e-12:
        return {"true": float(true_total), "pred": float(pred_total), "rel_err": np.nan}
    return {
        "true": float(true_total),
        "pred": float(pred_total),
        "abs_err": float(abs(true_total - pred_total)),
        "rel_err": float(abs(true_total - pred_total) / abs(true_total)),
    }
