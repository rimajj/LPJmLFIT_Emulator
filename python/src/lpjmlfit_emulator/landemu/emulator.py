"""``LandEmulator`` -- the whole learned LPJmL-FIT emulator in one object: daily weather in, daily
carbon/water
fluxes and yearly forest structure and stand out.

Each emulated year:
  1. the daily water-carbon model runs the year's 365 days, reading the stand at the end of the
  year before;
  2. the year's climate statistics are computed from the same daily weather and pushed into the
  30-year window;
  3. the structure map and the stand map predict the year's forest state from the window, the
  cell's anchors and
     its start levels; the stand becomes next year's daily-model input.
Nothing is recursive in the structure or stand maps (a year's state is a function of the climate
window and the
cell's fixed setup), so their errors cannot accumulate; the daily model carries its water stores
day to day.

Inputs per cell are documented in ``Setup``; ``scripts/build_emulator_release.py`` writes a release
(trained models +
a setup for the panel cells) and ``scripts/run_emulator.py`` runs one.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import numpy as np

from .annual import STAND_Q, STRUCT_Q, AnnualMaps
from .climate import CLIM_COLS, TrailingWindow, YearClimate
from .daily import DailyModel, DailyState

DAILY_OUT = ["gpp", "npp", "interc", "transp", "evap", "runoff", "swe", "soilw", "deep"]


@dataclass
class Setup:
    """Per-cell inputs, N cells, years ``year0 .. year0 + Y - 1``.

    cell, lat, lon, soil_code (N,); anc: quantity -> (N, Y) anchors (the original's mean over its
    training runs for
    that cell and year), for the 6 structure + 12 stand quantities; aclim (N, Y, 25): the anchor
    runs' trailing
    30-year climate; s0 / memoff: quantity -> (N,) the continued run's own 2000-2019 levels and
    their offset from the
    training runs' mean (zero offset = the mean run); clim_hist (H, N, 25): yearly climate
    statistics of the years
    before year0 (>= 19 years); cap (N,) or (N, Y): the top-metre water capacity, mm; W0, S0, D0
    (N,): water stores
    at the end of the day before the first emulated day; stand0 (N, 12): the stand at the end of
    the year before
    (leaf area, vegetation carbon gC/m2, cover of 10 plant types); warm (N, 365, 5): the 365 days
    of weather before
    the first emulated day (tas degC, pr mm, rsds W/m2, lwnet W/m2, huss kg/kg)."""

    cell: np.ndarray
    lat: np.ndarray
    lon: np.ndarray
    soil_code: np.ndarray
    year0: int
    anc: dict
    aclim: np.ndarray
    s0: dict
    memoff: dict
    clim_hist: np.ndarray
    cap: np.ndarray
    W0: np.ndarray
    S0: np.ndarray
    D0: np.ndarray
    stand0: np.ndarray
    warm: np.ndarray

    @classmethod
    def load(cls, path):
        """A setup .npz written by scripts/build_emulator_release.py (one file per continued run of
        the original)."""
        z = np.load(path)
        qs = STRUCT_Q + STAND_Q
        return cls(
            cell=z["cell"],
            lat=z["lat"],
            lon=z["lon"],
            soil_code=z["soil_code"],
            year0=int(z["year0"]),
            anc={q: z[f"anc/{q}"] for q in qs},
            aclim=z["aclim"],
            s0={q: z[f"s0/{q}"] for q in qs},
            memoff={q: z[f"memoff/{q}"] for q in qs},
            clim_hist=z["clim_hist"],
            cap=z["cap"],
            W0=z["W0"],
            S0=z["S0"],
            D0=z["D0"],
            stand0=z["stand0"],
            warm=z["warm"],
        )


class LandEmulator:
    def __init__(self, daily: DailyModel, annual: AnnualMaps, cfg: dict):
        self.daily, self.annual, self.cfg = daily, annual, cfg

    @classmethod
    def load(cls, release_dir):
        with open(os.path.join(release_dir, "release.json")) as fh:
            cfg = json.load(fh)
        return cls(
            DailyModel.load(os.path.join(release_dir, "daily.npz")),
            AnnualMaps.load(release_dir),
            cfg,
        )

    def start(self, setup: Setup):
        st = DailyState(setup.lat, setup.W0, setup.S0, setup.D0, setup.warm)
        t = self.cfg["pft_temp_stress"]
        return {
            "setup": setup,
            "daily": st,
            "clim": YearClimate(setup.lat, t["low"], t["high"]),
            "window": TrailingWindow(setup.clim_hist),
            "stand": self.stand_input(setup.stand0),
            "iy": 0,
        }

    @staticmethod
    def stand_input(stand):
        s = np.asarray(stand, np.float32).copy()
        s[:, 1] = np.log1p(np.maximum(s[:, 1], 0))
        return s

    def step_year(self, state, forcing, first_day=0, cap=None):
        """forcing (N, 365, 5) for the next year. Returns (daily dict name -> (N, 365), annual dict
        q -> (N,))."""
        su, ds, iy = state["setup"], state["daily"], state["iy"]
        n = forcing.shape[0]
        if cap is None:
            cap = su.cap if su.cap.ndim == 1 else su.cap[:, iy]
        capd = np.asarray(cap, np.float64)
        dm = self.daily
        out = {k: np.zeros((n, 365), np.float32) for k in DAILY_OUT}
        for d in range(365):
            f = np.asarray(forcing[:, d], np.float32)
            ds.push(f)
            if d < first_day:
                continue
            x = ds.inputs(f, d, capd, state["stand"], dm.drop)
            S32 = ds.S.astype(np.float32)
            y = dm.predict(x, f[:, 1], S32).astype(np.float64)
            ds.W, ds.S, ds.D, runoff = dm.bucket(
                y, f[:, 1].astype(np.float64), ds.W, ds.S, ds.D, capd
            )
            out["interc"][:, d], out["transp"][:, d], out["evap"][:, d] = y[:, 1], y[:, 2], y[:, 3]
            out["gpp"][:, d], out["npp"][:, d], out["runoff"][:, d] = y[:, 6], y[:, 7], runoff
            out["swe"][:, d], out["soilw"][:, d], out["deep"][:, d] = ds.S, ds.W, ds.D
        clim = state["clim"](
            forcing[:, :, 0], forcing[:, :, 1], forcing[:, :, 4], forcing[:, :, 2], forcing[:, :, 3]
        )
        win = state["window"].push(clim)
        ann = self.annual.predict(self.features(su, iy, win))
        new = self.stand_input(np.column_stack([ann[q] for q in STAND_Q]))
        state["stand"] = np.where(
            np.isfinite(new), new, state["stand"]
        )  # no anchor -> keep last year's stand
        state["iy"] = iy + 1
        return out, ann

    @staticmethod
    def features(su: Setup, iy, win):
        feat = {"lat": su.lat, "lon": su.lon, "soil_code": su.soil_code}
        for j, c in enumerate(CLIM_COLS):
            feat[c] = win[:, j]
            feat[f"dclim_{c}"] = win[:, j] - su.aclim[:, iy, j]
        for q in STRUCT_Q + STAND_Q:
            feat[f"anc_{q}"] = su.anc[q][:, iy]
            feat[f"s0_{q}"] = su.s0[q]
            feat[f"memoff_{q}"] = su.memoff[q]
        return feat
