"""Yearly climate statistics the forest-structure and stand models read (25 columns).

A dependency-free copy of the definitions in ``scripts/explore_glob_climate.year_features``
(restricted to the 25
columns of ``scripts/explore_panel_a7.CLIM_COLS``), with the helpers it uses from
``scripts/explore_de_climate`` and ``scripts/build_transient_boundary``.
``scripts/build_emulator_release.py`` gates
this copy against the original function on real forcing (exact equality) before a release is
written.
"""

from __future__ import annotations

import numpy as np

NB = 365
DPM = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31], dtype=np.int64)
MONTH_BOUNDS = np.concatenate([[0], np.cumsum(DPM)])
BETA = 0.17
PRIESTLEY_TAYLOR = 1.32
P_HPA = 1013.25

CLIM_COLS = [
    "tmean_ann",
    "tcold_month",
    "twarm_month",
    "gdd5",
    "frost_days",
    "days_gt30",
    "prec_ann",
    "prec_hs",
    "pet_ann",
    "cwb_ann",
    "cwb_hs",
    "cwb_min3",
    "dry_spell_max",
    "rh_mean",
    "vpd_hs",
    "vpd_win10_sum",
    "swdown_ann",
    "lwnet_ann",
] + [f"tstress_pft{k}" for k in range(7)]


def daylength_hours(lat):
    """petpar2.c day length in hours, (N,) lat -> (N, 365)."""
    day = np.arange(1, NB + 1, dtype=np.float64)
    delta = np.deg2rad(-23.4 * np.cos(2 * np.pi * (day + 10.0) / NB))
    u = np.sin(np.deg2rad(lat))[:, None] * np.sin(delta)[None, :]
    v = np.cos(np.deg2rad(lat))[:, None] * np.cos(delta)[None, :]
    hh = np.arccos(np.clip(-u / v, -1.0, 1.0))
    dl = 24 * hh / np.pi
    dl = np.where(u >= v, 24.0, dl)
    return np.where(u <= -v, 0.0, dl)


def window_mask(lat):
    """(N, 365): the days the original's annual stress accumulators hold at its annual call (reset
    day 14 N / 195 S)."""
    d = np.arange(NB)[None, :]
    return d >= np.where(lat >= 0.0, 14, 195)[:, None]


def summer_mask(lat):
    d = np.arange(NB)[None, :]
    jja = (d >= MONTH_BOUNDS[5]) & (d < MONTH_BOUNDS[8])
    djf = (d < MONTH_BOUNDS[2]) | (d >= MONTH_BOUNDS[11])
    return np.where((lat >= 0.0)[:, None], jja, djf)


def rh_from_q(q, temp, p=P_HPA):
    tk = temp + 273.16
    return np.minimum(0.263 * p * q / np.exp(17.67 * temp / (tk - 29.65)), 1.0)


def vpd_pa(temp, rh):
    a, b, c, d, f, h, ts = -7.90298, 5.02808, -1.3816e-7, 11.344, 8.1328e-3, 3.49149, 373.16
    tk = temp + 273.16
    z = (
        a * (ts / tk - 1)
        + b * np.log10(ts / tk)
        + c * (np.power(10.0, np.power(d, 1 - tk / ts)) - 1)
        + f * (np.power(10.0, -np.power(h, ts / tk - 1)) - 1)
    )
    return np.power(10.0, z) * (1 - np.minimum(rh, 1.0)) * 101324.6


def pet_pt(temp, swdown, lwnet, dl):
    s = 2.503e6 * np.exp(17.269 * temp / (237.3 + temp)) / ((237.3 + temp) ** 2)
    gam = 65.05 + temp * 0.064
    lam = 2.495e6 - temp * 2380
    eeq = 86400 * (s / (s + gam) / lam) * ((1 - BETA) * swdown + lwnet * dl / 24)
    return PRIESTLEY_TAYLOR * np.maximum(eeq, 0.0)


def _msum(a):
    return np.add.reduceat(a, MONTH_BOUNDS[:-1], axis=1)


class YearClimate:
    """Per-cell constants for the yearly statistics; ``__call__`` maps one year of daily weather to
    (N, 25)."""

    def __init__(self, lat, temp_low, temp_high):
        lat = np.asarray(lat, dtype=np.float64)
        self.dl = daylength_hours(lat)
        self.win = window_mask(lat)
        self.hs = summer_mask(lat)
        self.lo = np.asarray(temp_low, dtype=np.float64)
        self.hi = np.asarray(temp_high, dtype=np.float64)

    def __call__(self, T, P, Q, SW, LW):
        """Daily tas (degC), pr (mm), huss (kg/kg), rsds (W/m2), lwnet (W/m2), each (N, 365) -> (N,
        25) float64,
        rounded through the storage types of the training table (float32; int16 for the stress-day
        counts)."""
        T, P, Q, SW, LW = (np.asarray(a, dtype=np.float64) for a in (T, P, Q, SW, LW))
        out = {}
        tm, pm = _msum(T) / DPM[None, :], _msum(P)
        out["tmean_ann"] = T.mean(1)
        out["tcold_month"] = tm.min(1)
        out["twarm_month"] = tm.max(1)
        out["gdd5"] = np.maximum(T - 5, 0).sum(1)
        out["frost_days"] = (T < 0).sum(1)
        out["days_gt30"] = (T > 30).sum(1)
        out["prec_ann"] = P.sum(1)
        dry = P < 1.0
        run = np.zeros(T.shape[0])
        best = np.zeros(T.shape[0])
        for d in range(NB):
            run = np.where(dry[:, d], run + 1, 0.0)
            np.maximum(best, run, out=best)
        out["dry_spell_max"] = best
        pet = pet_pt(T, SW, LW, self.dl)
        petm = _msum(pet)
        out["pet_ann"] = pet.sum(1)
        cwbm = pm - petm
        out["cwb_ann"] = out["prec_ann"] - out["pet_ann"]
        out["cwb_min3"] = (cwbm[:, :-2] + cwbm[:, 1:-1] + cwbm[:, 2:]).min(1)
        rh = rh_from_q(Q, T)
        vpd = vpd_pa(T, rh) / 1000.0
        out["rh_mean"] = rh.mean(1)
        out["vpd_win10_sum"] = np.where(self.win & (T > 10.0), vpd, 0.0).sum(1)
        tw = np.where(self.win, T, np.nan)
        with np.errstate(invalid="ignore"):
            for j in range(len(self.lo)):
                out[f"tstress_pft{j}"] = ((tw < self.lo[j]) | (tw > self.hi[j])).sum(1)
        out["swdown_ann"] = SW.mean(1)
        out["lwnet_ann"] = LW.mean(1)
        out["prec_hs"] = np.where(self.hs, P, 0.0).sum(1)
        out["cwb_hs"] = out["prec_hs"] - np.where(self.hs, pet, 0.0).sum(1)
        out["vpd_hs"] = np.where(self.hs, vpd, 0.0).sum(1) / self.hs.sum(1)
        cols = []
        for c in CLIM_COLS:
            v = out[c]
            cols.append(
                np.asarray(v, np.int16 if c.startswith("tstress_pft") else np.float32).astype(
                    np.float64
                )
            )
        return np.stack(cols, 1)


class TrailingWindow:
    """Mean of the last ``n`` yearly vectors (fewer at the start, as the training table's rolling
    mean with
    ``min_samples`` = 20: the caller must seed it with at least 19 years before the first emulated
    year)."""

    def __init__(self, history, n=30):
        history = np.asarray(history, dtype=np.float64)  # (n_years, N, 25), oldest first
        self.n = n
        self.buf = list(history[-(n - 1) :]) if len(history) else []

    def push(self, year_vec):
        self.buf.append(np.asarray(year_vec, dtype=np.float64))
        if len(self.buf) > self.n:
            self.buf.pop(0)
        return np.mean(np.stack(self.buf), 0)
