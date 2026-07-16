"""Tests for ``lpjmlfit_emulator.features``.

Covers the climate feature-name schema and the pure, portable feature builder
``build_cell_year_feats`` (anomalies, trailing rolling means, 10-yr trend, eco fill).
polars is present in the reused env; guarded with ``importorskip`` regardless. The
external ``eco_diagnostics`` (needs climclusterpy + NetCDF data) is only smoke-checked.
"""

from __future__ import annotations

import numpy as np
import pytest

from lpjmlfit_emulator import features as F

pl = pytest.importorskip("polars")


def test_feature_schema_composition():
    # FEATURES is exactly STATIC + ECO + CLIM + ANOM + ROLL + TREND, in that order.
    assert F.FEATURES == F.STATIC + F.ECO + F.CLIM + F.ANOM + F.ROLL + F.TREND
    # no duplicate feature names
    assert len(F.FEATURES) == len(set(F.FEATURES))
    # 13 climclusterpy eco-diagnostics + 5 cheap seasonality summaries = 18 eco names
    assert len(F.ECO) == 18
    assert all(s in F.ECO for s in F.SEASONAL_FEATURES)
    assert F.AXES == ["logHeight", "Age", "SLA", "Wooddens", "beta_root"]


def _synthetic_inputs(n_years=6, cells=(0, 1)):
    """A small regular (Cell x Year) climate set with a linearly rising temperature."""
    rows = []
    for c in cells:
        for i, y in enumerate(range(2000, 2000 + n_years)):
            rows.append(
                {
                    "Cell": c,
                    "Year": y,
                    "temp": 10.0 + i,  # strictly increasing -> positive trend
                    "prec": 800.0,  # constant
                    "swrad": 150.0,
                    "lwrad": -40.0,
                    "humid": 0.008,
                }
            )
    annual = pl.DataFrame(rows)
    static = pl.DataFrame(
        {
            "Cell": list(cells),
            "lat": [50.2, 48.0],
            "soil_code": [3, 4],
            "soil_depth": [2.0, 2.0],
            "temp_mean": [12.0, 12.0],
            "temp_sd": [1.0, 1.0],
            "prec_mean": [800.0, 800.0],
            "prec_sd": [10.0, 10.0],
            "swrad_mean": [150.0, 150.0],
            "swrad_sd": [5.0, 5.0],
            "lwrad_mean": [-40.0, -40.0],
            "lwrad_sd": [2.0, 2.0],
            "humid_mean": [0.008, 0.008],
            "humid_sd": [0.001, 0.001],
        }
    )
    return static, annual


def test_build_cell_year_feats_columns_and_eco_fill():
    static, annual = _synthetic_inputs()
    feats = F.build_cell_year_feats(static, annual)  # eco=None
    assert feats.columns == ["Cell", "Year"] + F.FEATURES
    assert feats.height == annual.height
    # eco columns are 0-filled when no eco table is supplied (schema stays stable)
    for c in F.ECO:
        assert feats[c].to_numpy() == pytest.approx(0.0)


def test_build_cell_year_feats_anomaly_and_rolling():
    static, annual = _synthetic_inputs(n_years=6)
    feats = F.build_cell_year_feats(static, annual).sort(["Cell", "Year"])
    sub = feats.filter(pl.col("Cell") == 0).sort("Year")
    temp = sub["temp"].to_numpy()
    # anomaly = current - static normal (temp_mean = 12.0)
    np.testing.assert_allclose(sub["temp_anom"].to_numpy(), temp - 12.0)
    # trailing rolling mean, min_periods=1: first year equals the value itself
    assert sub["temp_r3"].to_numpy()[0] == pytest.approx(temp[0])
    # 3-yr trailing mean at year index 2 = mean of first three temps
    assert sub["temp_r3"].to_numpy()[2] == pytest.approx(np.mean(temp[:3]))


def test_build_cell_year_feats_trend_sign():
    static, annual = _synthetic_inputs(n_years=6)
    feats = F.build_cell_year_feats(static, annual).sort(["Cell", "Year"])
    sub = feats.filter(pl.col("Cell") == 0).sort("Year")
    # temperature rises by 1/yr -> trailing slope is +1 once the window has >=2 points
    trend = sub["temp_trend10"].to_numpy()
    assert trend[-1] == pytest.approx(1.0, abs=1e-6)
    # constant precip -> zero trend
    assert sub["prec_trend10"].to_numpy()[-1] == pytest.approx(0.0, abs=1e-9)


def test_eco_diagnostics_is_callable_and_documented():
    # Runtime needs climclusterpy + NetCDF data (not exercised here); check the API surface.
    assert callable(F.eco_diagnostics)
    assert "climclusterpy" in (F.eco_diagnostics.__doc__ or "")
