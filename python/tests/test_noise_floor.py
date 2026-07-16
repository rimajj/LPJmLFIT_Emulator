"""Tests for ``lpjmlfit_emulator.noise_floor`` (seed-split evaluation yardstick).

Asserts the published per-variable noise-floor constants and validates the diagnostic
machinery on controlled synthetic seed pairs (the real seed1/seed2 ground truth is 44 GB
each and not reproduced here). Fixed seed 42.
"""

from __future__ import annotations

import numpy as np
import pytest

from lpjmlfit_emulator import noise_floor as nf

SEED = 42

# The published seed1-vs-seed2 per-cell noise floor (the yardstick; ~11% on cell-mean agb).
_PUBLISHED = {"Height": 0.020, "agb": 0.113, "npp": 0.062, "LAI": 0.025}


def test_published_noise_floor_constants():
    # regression guard on the exact published numbers (the report's yardstick)
    assert nf.PUBLISHED_NOISE_FLOOR == _PUBLISHED


@pytest.mark.parametrize(("variable", "floor"), list(_PUBLISHED.items()))
def test_magnitude_floor_reproduces_published_number(variable, floor):
    # Construct a seed pair whose per-cell disagreement is EXACTLY the published floor:
    # seed2 = seed1 * (1 + floor)  =>  |s1 - s2| / |s1| = floor for every cell.
    rng = np.random.default_rng(SEED)
    seed1 = rng.uniform(1.0, 100.0, size=500)
    seed2 = seed1 * (1.0 + floor)
    got = nf.per_cell_magnitude_floor(seed1, seed2)
    assert got == pytest.approx(floor, rel=1e-9)


def test_magnitude_floor_zero_when_identical():
    x = np.array([1.0, 2.0, 3.0, 4.0])
    assert nf.per_cell_magnitude_floor(x, x) == pytest.approx(0.0)


def test_magnitude_floor_length_mismatch_raises():
    with pytest.raises(ValueError):
        nf.per_cell_magnitude_floor([1.0, 2.0], [1.0])


def test_ranking_ceiling_perfectly_correlated_is_one():
    x = np.linspace(1.0, 10.0, 50)
    assert nf.ranking_ceiling(x, x, method="spearman") == pytest.approx(1.0)
    assert nf.ranking_ceiling(x, 2.0 * x + 1.0, method="pearson") == pytest.approx(1.0)


def test_ranking_ceiling_bad_method_raises():
    with pytest.raises(ValueError):
        nf.ranking_ceiling([1.0, 2.0, 3.0], [1.0, 2.0, 3.0], method="kendall")


def test_error_distribution_percentiles():
    # per-cell |rel err| = |pred-truth|/|truth|; truth=1 so rel err == |pred-1|
    truth = np.ones(101)
    pred = 1.0 + np.linspace(0.0, 1.0, 101)  # rel errors 0.00 .. 1.00, uniform
    d = nf.error_distribution(pred, truth, percentiles=(50, 75, 90))
    assert set(d) == {"p50", "p75", "p90"}
    assert d["p50"] == pytest.approx(0.5, abs=1e-6)
    assert d["p90"] == pytest.approx(0.9, abs=1e-6)
    assert d["p50"] <= d["p75"] <= d["p90"]


def test_fraction_within_floor():
    truth = np.ones(100)
    pred = 1.0 + np.concatenate([np.full(80, 0.05), np.full(20, 0.5)])  # 80% within 0.1
    assert nf.fraction_within_floor(pred, truth, floor=0.1) == pytest.approx(0.8)


def test_latitude_band_bias_shape_and_sign():
    # southern cells biased low (pred<truth), northern biased high (pred>truth)
    lat = np.array([-45.0, -45.0, 45.0, 45.0])
    truth = np.array([10.0, 10.0, 10.0, 10.0])
    pred = np.array([9.0, 9.0, 11.0, 11.0])
    bands = nf.latitude_band_bias(pred, truth, lat, bands=(-90, 0, 90))
    assert len(bands) == 2
    south, north = bands
    assert south["n"] == 2 and north["n"] == 2
    assert south["mean_rel_bias"] == pytest.approx(-0.1)
    assert north["mean_rel_bias"] == pytest.approx(0.1)


def test_noise_floor_report_bundles_everything():
    rng = np.random.default_rng(SEED)
    seed1 = rng.uniform(1.0, 100.0, size=300)
    seed2 = seed1 * (1.0 + 0.113)
    lat = rng.uniform(-60.0, 60.0, size=300)
    rep = nf.noise_floor_report(seed1, seed2, variable="agb", lat=lat)
    assert rep["magnitude_floor"] == pytest.approx(0.113, rel=1e-9)
    assert rep["published_floor"] == 0.113
    assert rep["variable"] == "agb"
    assert rep["n_cells"] == 300
    assert "disagreement_dist" in rep and "ranking_ceiling" in rep
    assert isinstance(rep["latitude_band_bias"], list)
