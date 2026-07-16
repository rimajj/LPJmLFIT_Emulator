"""Tests for ``lpjmlfit_emulator.metrics`` (pytest + Hypothesis property tests).

Hypothesis is OPTIONAL: the reused env ``py311_new`` may not have it installed, so
the property tests SKIP (never fail) when Hypothesis is absent, while the plain
pytest cases always run. Fixed seed 42 throughout.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from lpjmlfit_emulator import metrics as M

SEED = 42

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    HAS_HYPOTHESIS = True
except ImportError:  # pragma: no cover - exercised only when hypothesis is absent
    HAS_HYPOTHESIS = False

    def given(*_a, **_k):  # no-op decorator so the module still imports
        def deco(fn):
            return fn

        return deco

    def settings(*_a, **_k):
        def deco(fn):
            return fn

        return deco

    class _Dummy:
        """Chainable stand-in for a Hypothesis strategy (supports .filter/.map/...)."""

        def __getattr__(self, _name):
            return lambda *a, **k: self

    class _NoStrategies:
        def __getattr__(self, _name):
            return lambda *a, **k: _Dummy()

    st = _NoStrategies()


requires_hypothesis = pytest.mark.skipif(
    not HAS_HYPOTHESIS, reason="hypothesis not installed in this env"
)

_finite = (
    st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
    if HAS_HYPOTHESIS
    else None
)


# --------------------------------------------------------------------------
# Plain unit tests (always run)
# --------------------------------------------------------------------------
def test_wasserstein_self_is_zero():
    rng = np.random.default_rng(SEED)
    x = rng.normal(0, 1, 2000)
    assert M.wasserstein1d(x, x) == 0.0


def test_wasserstein_symmetric():
    rng = np.random.default_rng(SEED)
    a = rng.normal(0.0, 1.0, 1500)
    b = rng.normal(0.5, 1.3, 1200)
    assert math.isclose(M.wasserstein1d(a, b), M.wasserstein1d(b, a), rel_tol=1e-12, abs_tol=1e-12)


def test_wasserstein_positive_for_shifted():
    rng = np.random.default_rng(SEED)
    a = rng.normal(0.0, 1.0, 3000)
    b = rng.normal(3.0, 1.0, 3000)
    assert M.wasserstein1d(a, b) > 0.5


def test_wasserstein_empty_is_nan():
    assert math.isnan(M.wasserstein1d([], [1.0, 2.0]))


def test_ks_self_is_zero():
    rng = np.random.default_rng(SEED)
    x = rng.normal(size=1000)
    assert M.ks_statistic(x, x) == 0.0


def test_ks_in_unit_interval():
    rng = np.random.default_rng(SEED)
    a = rng.normal(0.0, 1.0, 800)
    b = rng.normal(2.0, 1.0, 900)
    ks = M.ks_statistic(a, b)
    assert 0.0 <= ks <= 1.0
    assert ks > 0.0


def test_noise_floor_zero_when_identical_and_nonneg():
    rng = np.random.default_rng(SEED)
    cell_means = rng.uniform(1.0, 100.0, 200)
    assert M.noise_floor(cell_means, cell_means) == 0.0
    perturbed = cell_means * (1.0 + rng.normal(0.0, 0.1, cell_means.size))
    assert M.noise_floor(cell_means, perturbed) >= 0.0


def test_noise_floor_length_mismatch_raises():
    with pytest.raises(ValueError):
        M.noise_floor([1, 2, 3], [1, 2])


def test_per_cell_relative_error_self_is_zero():
    rng = np.random.default_rng(SEED)
    truth = rng.uniform(1.0, 50.0, 100)
    err = M.per_cell_relative_error(truth, truth)
    assert np.allclose(err, 0.0)


def test_per_cell_relative_error_values():
    err = M.per_cell_relative_error([11.0, 8.0], [10.0, 10.0])
    assert np.allclose(err, [0.1, 0.2])


def test_per_cell_relative_error_length_mismatch_raises():
    with pytest.raises(ValueError):
        M.per_cell_relative_error([1.0, 2.0], [1.0])


def test_published_noise_floor_agb_about_11pct():
    assert math.isclose(M.PUBLISHED_NOISE_FLOOR["agb"], 0.113, abs_tol=1e-6)


# --------------------------------------------------------------------------
# Hypothesis property tests (skipped if hypothesis absent)
# --------------------------------------------------------------------------
@requires_hypothesis
@settings(deadline=None, derandomize=True, max_examples=100)
@given(st.lists(_finite, min_size=1, max_size=200))
def test_prop_wasserstein_self_zero(xs):
    assert M.wasserstein1d(xs, xs) == 0.0


@requires_hypothesis
@settings(deadline=None, derandomize=True, max_examples=100)
@given(
    st.lists(_finite, min_size=1, max_size=200),
    st.lists(_finite, min_size=1, max_size=200),
)
def test_prop_wasserstein_symmetric(a, b):
    assert np.isclose(M.wasserstein1d(a, b), M.wasserstein1d(b, a), rtol=1e-9, atol=1e-9)


@requires_hypothesis
@settings(deadline=None, derandomize=True, max_examples=100)
@given(
    st.lists(_finite, min_size=1, max_size=200),
    st.lists(_finite, min_size=1, max_size=200),
)
def test_prop_ks_in_unit_interval(a, b):
    ks = M.ks_statistic(a, b)
    assert 0.0 <= ks <= 1.0


@requires_hypothesis
@settings(deadline=None, derandomize=True, max_examples=100)
@given(st.lists(st.tuples(_finite, _finite), min_size=1, max_size=200))
def test_prop_noise_floor_nonneg(pairs):
    s1 = [p[0] for p in pairs]
    s2 = [p[1] for p in pairs]
    nf = M.noise_floor(s1, s2)
    assert math.isnan(nf) or nf >= 0.0
