"""Seed-split noise-floor diagnostics for component S — the evaluation yardstick.

An emulator of a *stochastic* model can never beat the model's own run-to-run spread.
The **noise floor** is that spread, estimated from two independent RNG seeds (seed1 vs
seed2) of the SAME ground-truth LPJmL-FIT configuration: for each cell, the relative
disagreement ``|seed1 - seed2| / |seed1|`` of a cell summary (e.g. cell-mean agb). Always
report emulator per-cell error against this floor FIRST — at or below it the emulator is
statistically indistinguishable from a fresh stochastic run of the truth, so a pooled
"accuracy" number below the floor is meaningless.

This module layers the seed-split discipline on top of :mod:`lpjmlfit_emulator.metrics`
(``noise_floor``, ``per_cell_relative_error``, ``PUBLISHED_NOISE_FLOOR``): the per-cell
magnitude floor, the ranking ceiling (best achievable cross-cell rank skill), the per-cell
error distribution (p50/p75/p90), the fraction of cells within the floor, and latitude-band
bias.

Provenance: reconstructed on 2026-07-16 from the *documented discipline* of the frozen
sibling emulator's ``eval_presentday_critical.py`` (seed1-vs-seed2 magnitude floor, ranking
ceiling, per-cell error distribution, fraction within floor, latitude-band bias, and the
published per-variable floor). The sibling source itself was NOT read — it is blocked by the
Claude Code auto-mode classifier's "eval"-filename heuristic (not an owner hook) — so this is
a faithful rebuild of the discipline, not a byte-for-byte port. This repository is the single
source of truth for component S; the sibling is frozen (ADR 0012) — port once, do not sync.
"""

from __future__ import annotations

import numpy as np

from .metrics import PUBLISHED_NOISE_FLOOR, per_cell_relative_error

__all__ = [
    "PUBLISHED_NOISE_FLOOR",
    "per_cell_magnitude_floor",
    "ranking_ceiling",
    "error_distribution",
    "fraction_within_floor",
    "latitude_band_bias",
    "noise_floor_report",
]

_EPS = 1e-12
#: Default percentiles for the per-cell |relative error| distribution.
DEFAULT_PERCENTILES: tuple[int, ...] = (50, 75, 90)
#: Default latitude-band edges (degrees) for :func:`latitude_band_bias`.
DEFAULT_LAT_BANDS: tuple[float, ...] = (-90.0, -60.0, -30.0, 0.0, 30.0, 60.0, 90.0)


def _aligned(a, b) -> tuple[np.ndarray, np.ndarray]:
    a = np.asarray(a, dtype=float).ravel()
    b = np.asarray(b, dtype=float).ravel()
    if a.size != b.size:
        raise ValueError(f"arrays must be aligned per-cell (got {a.size} vs {b.size})")
    return a, b


def per_cell_magnitude_floor(seed1, seed2, reduce: str = "median") -> float:
    """The seed-split magnitude floor ``reduce(|seed1 - seed2| / |seed1|)`` over cells.

    ``seed1`` / ``seed2`` are aligned per-cell summaries of one variable from two RNG seeds
    of the ground-truth model (``seed1`` is the reference in the denominator). Returns the
    ``"median"`` (default) or ``"mean"`` per-cell relative magnitude — the irreducible error
    an emulator is measured against. Cells with ``|seed1| ~ 0`` are dropped; NaN if none
    remain. Raises ``ValueError`` on length mismatch.
    """
    s1, s2 = _aligned(seed1, seed2)
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = np.abs(s1 - s2) / np.where(np.abs(s1) > _EPS, np.abs(s1), np.nan)
    rel = rel[np.isfinite(rel)]
    if rel.size == 0:
        return float("nan")
    return float(np.median(rel) if reduce == "median" else np.mean(rel))


def ranking_ceiling(seed1, seed2, method: str = "spearman") -> float:
    """Best achievable cross-cell ranking skill: the correlation between the two seeds'
    per-cell values. An emulator's rank correlation against truth cannot exceed this
    seed-to-seed ceiling. ``method`` is ``"spearman"`` (rank, default) or ``"pearson"``.
    Returns NaN if fewer than two finite aligned cells remain.
    """
    s1, s2 = _aligned(seed1, seed2)
    m = np.isfinite(s1) & np.isfinite(s2)
    s1, s2 = s1[m], s2[m]
    if s1.size < 2:
        return float("nan")
    if method == "spearman":
        from scipy.stats import spearmanr  # scipy is a core dep; kept local for a light import

        return float(spearmanr(s1, s2).statistic)
    if method == "pearson":
        return float(np.corrcoef(s1, s2)[0, 1])
    raise ValueError(f"unknown method {method!r} (expected 'spearman' or 'pearson')")


def error_distribution(pred, truth, percentiles=DEFAULT_PERCENTILES) -> dict[str, float]:
    """Percentiles of the per-cell ``|relative error|`` between ``pred`` and ``truth``.

    Returns ``{"p50": ..., "p75": ..., "p90": ...}`` (keys follow ``percentiles``). Report
    these against the noise floor, not a single pooled number.
    """
    err = per_cell_relative_error(pred, truth)
    err = err[np.isfinite(err)]
    if err.size == 0:
        return {f"p{int(q)}": float("nan") for q in percentiles}
    return {f"p{int(q)}": float(np.percentile(err, q)) for q in percentiles}


def fraction_within_floor(pred, truth, floor: float) -> float:
    """Fraction of cells whose per-cell relative error is at or below ``floor``.

    ``floor`` is a scalar (e.g. ``PUBLISHED_NOISE_FLOOR["agb"]``). A high fraction means the
    emulator is within the irreducible seed spread over most of the domain. NaN if no cell
    has a finite error.
    """
    err = per_cell_relative_error(pred, truth)
    err = err[np.isfinite(err)]
    if err.size == 0:
        return float("nan")
    return float(np.mean(err <= floor))


def latitude_band_bias(pred, truth, lat, bands=DEFAULT_LAT_BANDS) -> list[dict[str, float]]:
    """Mean signed relative bias ``(pred - truth) / truth`` within latitude bands.

    ``lat`` is the per-cell latitude (degrees), aligned with ``pred``/``truth``. Returns one
    dict per band ``{lat_lo, lat_hi, n, mean_rel_bias}`` (``mean_rel_bias`` is NaN for an
    empty band). Bands are half-open ``[lo, hi)`` except the last, which is closed ``[lo, hi]``.
    """
    p, t = _aligned(pred, truth)
    la = np.asarray(lat, dtype=float).ravel()
    if la.size != p.size:
        raise ValueError(f"lat must be aligned per-cell (got {la.size} vs {p.size})")
    with np.errstate(divide="ignore", invalid="ignore"):
        rel_bias = (p - t) / np.where(np.abs(t) > _EPS, t, np.nan)
    out: list[dict[str, float]] = []
    edges = list(bands)
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        in_band = (la >= lo) & (la <= hi) if i == len(edges) - 2 else (la >= lo) & (la < hi)
        vals = rel_bias[in_band]
        vals = vals[np.isfinite(vals)]
        out.append(
            {
                "lat_lo": float(lo),
                "lat_hi": float(hi),
                "n": int(vals.size),
                "mean_rel_bias": float(np.mean(vals)) if vals.size else float("nan"),
            }
        )
    return out


def noise_floor_report(seed1, seed2, *, variable: str | None = None, lat=None) -> dict:
    """Full seed-split noise-floor report for one variable.

    Combines the per-cell magnitude floor, the ranking ceiling, the seed-to-seed
    disagreement distribution, and (if ``lat`` is given) the seed-to-seed latitude-band
    bias. If ``variable`` names a key in :data:`PUBLISHED_NOISE_FLOOR`, the published
    reference floor is attached for comparison. ``seed1`` is treated as the reference seed.
    """
    s1, s2 = _aligned(seed1, seed2)
    report: dict = {
        "magnitude_floor": per_cell_magnitude_floor(s1, s2),
        "ranking_ceiling": ranking_ceiling(s1, s2),
        "disagreement_dist": error_distribution(s2, s1),
        "n_cells": int(np.sum(np.isfinite(s1) & np.isfinite(s2))),
    }
    if variable is not None and variable in PUBLISHED_NOISE_FLOOR:
        report["variable"] = variable
        report["published_floor"] = PUBLISHED_NOISE_FLOOR[variable]
    if lat is not None:
        report["latitude_band_bias"] = latitude_band_bias(s2, s1, lat)
    return report
