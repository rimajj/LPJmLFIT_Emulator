"""Tests for ``lpjmlfit_emulator.landemu`` (the packaged learned emulator), synthetic inputs only.

The real-data gates (numpy daily model == PyTorch, climate statistics == the training
pipeline's, a fold release reproducing the scored predictions) run in
scripts/build_emulator_release.py and scripts/run_emulator.py; here the plumbing and the
conservation property are checked without any data. Fixed seed 42.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from lpjmlfit_emulator.landemu import LandEmulator, Setup
from lpjmlfit_emulator.landemu.annual import STAND_Q, STRUCT_Q
from lpjmlfit_emulator.landemu.climate import CLIM_COLS, TrailingWindow, YearClimate
from lpjmlfit_emulator.landemu.daily import NIN, DailyModel, DailyState, Member

SEED = 42
LOW = [12.5, -15.0, -10.0, -20.0, -45.0, -45.0, -70.0]
HIGH = [54.0] * 7


def _weather(rng, n):
    T = rng.normal(8.0, 10.0, (n, 365))
    P = rng.gamma(0.8, 3.0, (n, 365))
    return np.stack(
        [
            T,
            P,
            rng.uniform(20, 300, (n, 365)),
            rng.uniform(-90, -10, (n, 365)),
            np.full((n, 365), 0.006),
        ],
        -1,
    ).astype(np.float32)


def _member(rng, nh=16, nl=2, nin=NIN):
    z = {"mu": np.zeros(nin), "sd": np.ones(nin), "ysd": np.ones(8), "n_layers": nl}
    n_in = nin
    for i in range(nl):
        z[f"W{i}"], z[f"b{i}"] = rng.normal(0, 0.2, (nh, n_in)), np.zeros(nh)
        n_in = nh
    z[f"W{nl}"], z[f"b{nl}"] = rng.normal(0, 0.2, (9, n_in)), np.zeros(9)
    return Member(z)


def test_climate_counts_and_window():
    lat = np.array([51.25, -33.0])
    yc = YearClimate(lat, LOW, HIGH)
    T = np.tile(np.where(np.arange(365) < 100, -5.0, 31.0), (2, 1))
    P = np.zeros((2, 365))
    out = yc(T, P, np.full((2, 365), 0.005), np.full((2, 365), 100.0), np.full((2, 365), -50.0))
    assert out.shape == (2, len(CLIM_COLS))
    assert out[0, CLIM_COLS.index("frost_days")] == 100
    assert out[0, CLIM_COLS.index("days_gt30")] == 265
    assert out[0, CLIM_COLS.index("dry_spell_max")] == 365
    tw = TrailingWindow(np.ones((20, 2, 3)))
    assert np.allclose(tw.push(np.full((2, 3), 22.0)), (20 + 22) / 21)
    for _ in range(40):
        last = tw.push(np.full((2, 3), 5.0))
    assert np.allclose(last, 5.0)


def test_daily_bucket_closes_water_exactly():
    rng = np.random.default_rng(SEED)
    n = 7
    model = DailyModel([_member(rng), _member(rng)], drop=[4], deep_tau=365.0)
    w = _weather(rng, n)
    st = DailyState(np.linspace(-60, 70, n), np.full(n, 50.0), np.zeros(n), np.zeros(n), w)
    cap = np.full(n, 150.0)
    stand = np.zeros((n, 12), np.float32)
    W0, S0, D0 = st.W.copy(), st.S.copy(), st.D.copy()
    flux = np.zeros(n)
    for d in range(365):
        f = w[:, d]
        st.push(f)
        y = model.predict(st.inputs(f, d, cap, stand, model.drop), f[:, 1], st.S.astype(np.float32))
        y = y.astype(np.float64)
        st.W, st.S, st.D, runoff = model.bucket(
            y, f[:, 1].astype(np.float64), st.W, st.S, st.D, cap
        )
        flux += y[:, 1] + y[:, 2] + y[:, 3] + runoff
        assert np.all(st.W >= -1e-9) and np.all(st.W <= cap + 1e-9)
    storage = (st.W - W0) + (st.S - S0) + (st.D - D0)
    assert np.allclose(w[:, :, 1].sum(1, dtype=np.float64), storage + flux, atol=1e-6)


def _tiny_release(tmp_path, rng, n, co2=False):
    lgb = pytest.importorskip("lightgbm")
    fs = (
        CLIM_COLS
        + [f"dclim_{c}" for c in CLIM_COLS]
        + (["co2_win", "dco2_win"] if co2 else [])
        + [f"{k}_{q}" for k in ("anc", "s0", "memoff") for q in STRUCT_Q]
        + ["lat", "lon", "soil_code"]
    )
    fx = fs + [f"{k}_{q}" for q in STAND_Q for k in ("anc", "s0", "memoff")]
    X = rng.normal(size=(200, len(fx)))
    params = {"objective": "regression", "verbose": -1, "num_leaves": 4, "min_data_in_leaf": 5}
    if co2:  # the maps must respond to the CO2 window for the test below to see it
        X[:, fx.index("co2_win")] = rng.uniform(300, 900, 200)
    for q in STRUCT_Q + STAND_Q:
        cols = fs if q in STRUCT_Q else fx
        Xq = X[:, : len(cols)]
        y = rng.normal(0, 0.01, 200) + (1e-3 * Xq[:, cols.index("co2_win")] if co2 else 0.0)
        lgb.train(params, lgb.Dataset(Xq, y), 5).save_model(str(tmp_path / f"lgb_{q}.txt"))
    cfg = {"features_structure": fs, "features_stand": fx, "log_eps": {"agb_per_stem": 1.0}}
    (tmp_path / "annual.json").write_text(json.dumps(cfg))
    z = {"n_members": 2, "drop": np.array([4]), "deep_tau": 365.0, "co2_input": co2}
    for i in range(2):
        m = _member(rng, nin=NIN + co2)
        z[f"m{i}/n_layers"] = 2
        for j in range(3):
            z[f"m{i}/W{j}"], z[f"m{i}/b{j}"] = m.W[j], m.b[j]
        z[f"m{i}/mu"], z[f"m{i}/sd"], z[f"m{i}/ysd"] = m.mu, m.sd, m.ysd
    np.savez(tmp_path / "daily.npz", **z)
    rel = {"version": "test", "kind": "fold", "hold_gcm": None, "co2_input": co2}
    rel["pft_temp_stress"] = {"low": LOW, "high": HIGH}
    (tmp_path / "release.json").write_text(json.dumps(rel))
    Y = 3
    qs = STRUCT_Q + STAND_Q
    return Setup(
        cell=np.arange(n),
        lat=np.linspace(-40, 60, n),
        lon=np.linspace(-100, 100, n),
        soil_code=np.ones(n),
        year0=2020,
        anc={q: np.full(n, 1.0) if co2 else np.full((n, Y), 1.0) for q in qs},  # fixed / per year
        aclim=np.zeros((n, len(CLIM_COLS))) if co2 else np.zeros((n, Y, len(CLIM_COLS))),
        s0={q: np.full(n, 1.0) for q in qs},
        memoff={q: np.zeros(n) for q in qs},
        clim_hist=np.zeros((20, n, len(CLIM_COLS))),
        cap=np.full(n, 150.0),
        W0=np.full(n, 60.0),
        S0=np.zeros(n),
        D0=np.zeros(n),
        stand0=np.full((n, 12), 0.1),
        warm=_weather(rng, n),
        co2_hist=np.full(29, 400.0) if co2 else None,
        aco2=380.0 if co2 else None,
    )


def test_land_emulator_runs_years(tmp_path):
    rng = np.random.default_rng(SEED)
    n = 5
    su = _tiny_release(tmp_path, rng, n)
    emu = LandEmulator.load(tmp_path)
    st = emu.start(su)
    for _ in range(3):
        daily, ann = emu.step_year(st, _weather(rng, n))
        assert set(ann) == set(STRUCT_Q + STAND_Q)
        assert all(v.shape == (n,) and np.all(np.isfinite(v)) for v in ann.values())
        assert daily["gpp"].shape == (n, 365) and np.all(np.isfinite(daily["runoff"]))
        assert np.all(ann["n_per_patch"] >= 0) and np.all(ann["lai_stand"] >= 0)
    assert st["iy"] == 3


def test_co2_release_needs_and_uses_co2(tmp_path):
    rng = np.random.default_rng(SEED)
    n = 5
    su = _tiny_release(tmp_path, rng, n, co2=True)
    emu = LandEmulator.load(tmp_path)
    assert emu.co2_input and emu.daily.co2_input
    w = _weather(rng, n)
    with pytest.raises(ValueError, match="CO2"):
        emu.step_year(emu.start(su), w)
    outs = []
    for ppm in (400.0, 900.0):
        st = emu.start(su)
        daily, ann = emu.step_year(st, w, co2=ppm)
        assert all(np.all(np.isfinite(v)) for v in ann.values())
        assert np.isclose(np.mean(st["co2buf"]), (29 * 400.0 + ppm) / 30)
        outs.append((daily["gpp"], ann["vegc"]))
    assert not np.allclose(outs[0][0], outs[1][0])  # the daily model reads the year's CO2
    assert not np.allclose(outs[0][1], outs[1][1])  # the maps read the CO2 window
    su.co2_hist = None
    with pytest.raises(ValueError, match="co2_hist"):
        emu.start(su)


def test_release_without_co2_refuses_it(tmp_path):
    rng = np.random.default_rng(SEED)
    su = _tiny_release(tmp_path, rng, 4)
    emu = LandEmulator.load(tmp_path)
    with pytest.raises(ValueError, match="no CO2 input"):
        emu.step_year(emu.start(su), _weather(rng, 4), co2=400.0)
