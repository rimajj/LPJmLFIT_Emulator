"""Tests for ``lpjmlfit_emulator.transforms`` (pytest + optional Hypothesis).

Covers the signed-log heavy-tail transform pair and the monotone (isotonic) trait
link used for the near-deterministic relationships (Longevity<-SLA, D95max<-beta_root).
Hypothesis is OPTIONAL (skips gracefully when absent). Fixed seed 42 throughout.
"""

from __future__ import annotations

import numpy as np

from lpjmlfit_emulator.transforms import (
    MonotoneLink,
    VarTransformer,
    expm1_clip,
    log1p_signed,
)

SEED = 42

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    HAS_HYPOTHESIS = True
except ImportError:  # py311_new may not have hypothesis; property tests skip
    HAS_HYPOTHESIS = False


def test_log1p_expm1_round_trip_nonneg():
    x = np.array([0.0, 0.5, 1.0, 10.0, 1e3, 1e5])
    back = expm1_clip(log1p_signed(x))
    np.testing.assert_allclose(back, x, rtol=1e-9, atol=1e-9)


def test_log1p_signed_clips_tiny_negatives():
    # npp can dip slightly negative (~-0.03): clip at 0 before log1p, never NaN.
    z = log1p_signed(np.array([-0.03, -1e-6, 0.0]))
    assert np.all(np.isfinite(z))
    np.testing.assert_allclose(z, 0.0, atol=1e-12)


def test_expm1_clip_nonneg():
    # inverse never returns negative values even for negative inputs
    assert np.all(expm1_clip(np.array([-5.0, -0.1, 0.0, 2.0])) >= 0.0)


def test_var_transformer_log_vs_identity():
    vt = VarTransformer(log_vars=["agb"])
    x = np.array([0.0, 3.0, 20.0])
    # a log var round-trips through log1p/expm1
    np.testing.assert_allclose(vt.inverse("agb", vt.forward("agb", x)), x, rtol=1e-9)
    # a non-log var is identity both ways
    np.testing.assert_allclose(vt.forward("SLA", x), x)
    np.testing.assert_allclose(vt.inverse("SLA", x), x)


def test_monotone_link_recovers_decreasing_relationship():
    rng = np.random.default_rng(SEED)
    x = rng.uniform(0.007, 0.043, 20000)  # SLA
    y = 0.02 / x + rng.normal(0, 0.05, x.size)  # Longevity ~ 1/SLA (decreasing)
    link = MonotoneLink(increasing=False).fit(x, y)
    # fitted mean curve tracks the truth
    assert np.corrcoef(link.predict_mean(x), y)[0, 1] > 0.9
    # monotone (non-increasing) in x
    order = np.argsort(x)
    mu_sorted = link.predict_mean(x[order])
    assert np.all(np.diff(mu_sorted) <= 1e-9)


def test_monotone_link_sample_no_noise_is_mean_clipped():
    rng = np.random.default_rng(SEED)
    x = rng.uniform(0.007, 0.043, 2000)
    y = 0.02 / x
    link = MonotoneLink(increasing=False).fit(x, y)
    s = link.sample(x, rng, add_noise=False, nonneg=True)
    np.testing.assert_allclose(s, np.clip(link.predict_mean(x), 0, None))


def test_monotone_link_sample_is_deterministic_under_seed():
    x = np.linspace(0.007, 0.043, 500)
    y = 0.02 / x
    link = MonotoneLink(increasing=False).fit(x, y)
    a = link.sample(x, np.random.default_rng(SEED))
    b = link.sample(x, np.random.default_rng(SEED))
    np.testing.assert_array_equal(a, b)
    assert np.all(a >= 0.0)  # nonneg enforced by default


if HAS_HYPOTHESIS:

    @settings(max_examples=50, deadline=None, derandomize=True)
    @given(
        st.lists(
            st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=200,
        )
    )
    def test_prop_log1p_expm1_round_trip(xs):
        x = np.asarray(xs, float)
        np.testing.assert_allclose(expm1_clip(log1p_signed(x)), x, rtol=1e-6, atol=1e-6)
