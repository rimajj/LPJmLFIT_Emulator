"""Transform utilities for the slow emulator (component S).

Signed-log transforms for heavy-tailed non-negative size variables, and fitted
monotone derivations for the near-deterministic trait links found in EDA
(Longevity <- SLA ; D95max <- beta_root). Kept separate so both training and
inference use identical transforms.

Provenance: ported once on 2026-07-16 from the frozen sibling emulator module(s)
src/transforms.py (newest sibling source mtime 2026-07-14). This repository is the
single source of truth for component S; the sibling is frozen (ADR 0012) — port
once, do not sync.
"""

from __future__ import annotations

import numpy as np
from sklearn.isotonic import IsotonicRegression

__all__ = [
    "log1p_signed",
    "expm1_clip",
    "VarTransformer",
    "MonotoneLink",
]


# --------------------------------------------------------------------------
# Log transforms for heavy-tailed non-negative variables
# --------------------------------------------------------------------------
def log1p_signed(x):
    """log1p that tolerates tiny negatives (npp min ~ -0.03): clip at 0 first."""
    x = np.asarray(x, float)
    return np.log1p(np.clip(x, 0, None))


def expm1_clip(z):
    return np.clip(np.expm1(np.asarray(z, float)), 0, None)


class VarTransformer:
    """Per-variable forward/inverse transform (log1p for listed vars, identity else)."""

    def __init__(self, log_vars):
        self.log_vars = set(log_vars)

    def forward(self, name, x):
        return log1p_signed(x) if name in self.log_vars else np.asarray(x, float)

    def inverse(self, name, z):
        return expm1_clip(z) if name in self.log_vars else np.asarray(z, float)


# --------------------------------------------------------------------------
# Monotone derivation for near-deterministic trait links
# --------------------------------------------------------------------------
class MonotoneLink:
    """
    Fit y ~ monotone(x) with isotonic regression (+ small residual noise model)
    for near-deterministic relationships (Longevity<-SLA, D95max<-beta_root).
    Captures the mean curve and the (x-dependent) residual scale so sampling
    reproduces the small scatter around the curve.
    """

    def __init__(self, increasing="auto", n_resid_bins=20):
        self.increasing = increasing
        self.n_resid_bins = n_resid_bins

    def fit(self, x, y):
        x = np.asarray(x, float)
        y = np.asarray(y, float)
        m = np.isfinite(x) & np.isfinite(y)
        x, y = x[m], y[m]
        self.iso_ = IsotonicRegression(increasing=self.increasing, out_of_bounds="clip").fit(x, y)
        resid = y - self.iso_.predict(x)
        # residual sd as a function of x (binned), for scatter reproduction
        qs = np.quantile(x, np.linspace(0, 1, self.n_resid_bins + 1))
        qs = np.unique(qs)
        self._bin_edges = qs
        self._bin_sd = []
        for i in range(len(qs) - 1):
            in_bin = (x >= qs[i]) & (x <= qs[i + 1])
            self._bin_sd.append(
                float(np.std(resid[in_bin])) if in_bin.sum() > 5 else float(np.std(resid))
            )
        self._bin_sd = np.array(self._bin_sd)
        self._global_sd = float(np.std(resid))
        return self

    def predict_mean(self, x):
        return self.iso_.predict(np.asarray(x, float))

    def resid_sd(self, x):
        x = np.asarray(x, float)
        idx = np.clip(np.searchsorted(self._bin_edges, x) - 1, 0, len(self._bin_sd) - 1)
        return self._bin_sd[idx]

    def sample(self, x, rng, add_noise=True, nonneg=True):
        mu = self.predict_mean(x)
        if add_noise:
            mu = mu + rng.normal(0, 1, size=mu.shape) * self.resid_sd(x)
        if nonneg:
            mu = np.clip(mu, 0, None)
        return mu
