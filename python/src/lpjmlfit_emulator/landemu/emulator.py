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
day to day. A release with a departure model (ADR 0354/0358) also carries, per cell, last year's
departure of tree count and biomass per tree from the structure map, driven by the year's weather
anomaly; it only changes those two outputs (the stand, hence the daily model, is not affected).

A release trained on the nitrogen-on LPJmL-FIT (ADR 0342/0344, ``release.json`` ``co2_input``)
also reads the year's atmospheric CO2 (ppm): the daily model takes the year's value, the maps its
trailing 30-year mean and that mean's offset from the anchor period's. Pass it as
``step_year(..., co2=ppm)``; a release without the input refuses one (nitrogen off: CO2 is
deliberately not an input, ADR 0004/0107).

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
from .population import POP_Q, POP_VARS, PopSetup, PopulationMaps, diversity_indices, virtual_trees

CO2_WINDOW = 30  # years in the maps' trailing CO2 mean (clu_emu_maps.window)
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
    the first emulated day (tas degC, pr mm, rsds W/m2, lwnet W/m2, huss kg/kg).

    CO2 releases only: co2_hist (H,) the yearly CO2 (ppm) of the years before year0, oldest
    first (>= 29 years); aco2: the anchor period's 30-year CO2 mean (scalar or (N,)).
    A fixed anchor (the cell's own historical state, ADR 0341/0342) may be given as anc (N,) and
    aclim (N, 25): then the run has no last year."""

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
    co2_hist: np.ndarray | None = None
    aco2: np.ndarray | float | None = None

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
            co2_hist=z["co2_hist"] if "co2_hist" in z.files else None,
            aco2=z["aco2"] if "aco2" in z.files else None,
        )


class LandEmulator:
    def __init__(self, daily: DailyModel, annual: AnnualMaps, cfg: dict, population=None):
        self.daily, self.annual, self.cfg = daily, annual, cfg
        self.pop: PopulationMaps | None = (
            population  # optional (ADR 0365): None = release without it
        )
        self.co2_input = bool(cfg.get("co2_input", False))
        assert self.co2_input == daily.co2_input, (
            "release.json and daily.npz disagree on the CO2 input"
        )

    @classmethod
    def load(cls, release_dir):
        with open(os.path.join(release_dir, "release.json")) as fh:
            cfg = json.load(fh)
        return cls(
            DailyModel.load(os.path.join(release_dir, "daily.npz")),
            AnnualMaps.load(release_dir),
            cfg,
            PopulationMaps.load(release_dir),
        )

    def start(self, setup: Setup, popsetup: PopSetup | None = None):
        """popsetup (a release with population maps only, ADR 0365) switches on the yearly
        distributions and type shares (``pop_<var>_<pn>``, ``pop_share_<t>`` in end_year's output)
        and ``virtual_trees``. Without it the run is exactly the release's structure + stand +
        daily model; with it every existing output is unchanged too (only ``pop_*`` are added)."""
        if popsetup is not None:
            if self.pop is None:
                raise ValueError("this release has no population maps (population.json)")
            if not np.array_equal(popsetup.cell, setup.cell):
                raise ValueError("population setup and setup have different cells")
        st = DailyState(setup.lat, setup.W0, setup.S0, setup.D0, setup.warm)
        t = self.cfg["pft_temp_stress"]
        co2buf = None
        if self.co2_input:
            h = setup.co2_hist
            if h is None or len(h) < CO2_WINDOW - 1 or setup.aco2 is None:
                raise ValueError(
                    f"this release reads CO2: the setup needs co2_hist (>= {CO2_WINDOW - 1}"
                    " years) and aco2"
                )
            co2buf = [float(v) for v in np.asarray(h, np.float64)[-(CO2_WINDOW - 1) :]]
        return {
            "setup": setup,
            "daily": st,
            "clim": YearClimate(setup.lat, t["low"], t["high"]),
            "window": TrailingWindow(setup.clim_hist),
            "stand": self.stand_input(setup.stand0),
            "iy": 0,
            "co2buf": co2buf,
            "pop": popsetup,
            **self._dep_start(setup),
        }

    def _dep_start(self, setup):
        """Departure-model state (ADR 0358): last year's departures (0 in the first emulated year,
        as in training), the raw yearly climate statistics of the years before (for the z-scores),
        and last year's z-scores (of the year before year0, from clim_hist)."""
        dep = self.annual.dep
        if not dep:
            return {}
        n = len(setup.cell)
        hist = [np.asarray(v, np.float64) for v in np.asarray(setup.clim_hist, np.float64)]
        w, k = int(dep["z_window"]), int(dep["z_min"])
        if len(hist) < k + 1:
            raise ValueError(f"the departure model needs >= {k + 1} years of clim_hist")
        return {
            "dlag": {q: np.zeros(n) for q in dep["quantities"]},
            "zbuf": hist[-w:],
            "zprev": self.zscore(hist[-1], hist[-1 - w : -1], k),
        }

    @staticmethod
    def zscore(x, past, kmin):
        """z of this year's statistics against the years before (ddof 1, as the training table's
        polars rolling_std); 0 where fewer than kmin years or the statistic does not vary."""
        past = np.stack(past) if len(past) else np.zeros((0,) + np.shape(x))
        if len(past) < kmin:
            return np.zeros_like(x)
        mu, sd = past.mean(0), past.std(0, ddof=1)
        ok = sd > 1e-6 * (np.abs(mu) + 1.0)
        return np.where(ok, (x - mu) / np.where(ok, sd, 1.0), 0.0)

    @staticmethod
    def stand_input(stand):
        s = np.asarray(stand, np.float32).copy()
        s[:, 1] = np.log1p(np.maximum(s[:, 1], 0))
        return s

    def step_year(self, state, forcing, first_day=0, cap=None, co2=None):
        """forcing (N, 365, 5) for the next year; co2: the year's atmospheric CO2 in ppm (CO2
        releases only; scalar, as LPJmL's CO2 input, or (N,)). Returns (daily dict name ->
        (N, 365), annual dict q -> (N,)). Days before ``first_day`` only advance the weather
        windows. Identical to ``begin_year`` + 365 x ``step_day`` + ``end_year``, which is how
        an atmosphere model drives the emulator one day at a time."""
        self.begin_year(state, cap=cap, co2=co2)
        n = forcing.shape[0]
        out = {k: np.zeros((n, 365), np.float32) for k in DAILY_OUT}
        for d in range(365):
            day = self.step_day(state, forcing[:, d], run=d >= first_day)
            if day is not None:
                for k in DAILY_OUT:
                    out[k][:, d] = day[k]
        return out, self.end_year(state)

    def begin_year(self, state, cap=None, co2=None):
        """Open a year: take the year's CO2 (CO2 releases only; ppm) and top-metre capacity
        (mm; default the setup's), and start collecting the year's weather for the yearly
        statistics."""
        su, iy = state["setup"], state["iy"]
        if state.get("year") is not None:
            raise RuntimeError("begin_year called twice without end_year")
        if self.co2_input and co2 is None:
            raise ValueError(
                "this release reads the year's CO2 (ppm): pass step_year(..., co2=...)"
            )
        if not self.co2_input and co2 is not None:
            raise ValueError("this release has no CO2 input (nitrogen-off model, ADR 0004/0107)")
        co2_win = None
        if co2 is not None:
            buf = state["co2buf"]
            buf.append(co2)
            if len(buf) > CO2_WINDOW:
                buf.pop(0)
            co2_win = np.mean(np.asarray(buf, np.float64), axis=0)
        if cap is None:
            cap = su.cap if su.cap.ndim == 1 else su.cap[:, iy]
        state["year"] = {
            "d": 0,
            "co2": co2,
            "co2_win": co2_win,
            "cap": np.asarray(cap, np.float64),
            # float64 holds float32 or float64 weather exactly, so the statistics are unchanged
            "forcing": np.zeros((len(su.cell), 365, 5), np.float64),
        }

    def step_day(self, state, f, run=True):
        """One day of weather f (N, 5: tas degC, pr mm/day, rsds W/m2, lwnet W/m2, huss kg/kg)
        inside an open year. Returns the day's outputs, name -> (N,): fluxes in mm/day and
        gC/m2/day, the stores ``swe``, ``soilw``, ``deep`` in mm at the end of the day. With
        ``run=False`` the day only advances the weather windows and None is returned."""
        yr, ds, dm = state.get("year"), state["daily"], self.daily
        if yr is None:
            raise RuntimeError("step_day outside a year: call begin_year first")
        d = yr["d"]
        if d >= 365:
            raise RuntimeError("a year has 365 days: call end_year")
        yr["forcing"][:, d] = f
        yr["d"] = d + 1
        f = np.asarray(f, np.float32)
        ds.push(f)
        if not run:
            return None
        x = ds.inputs(f, d, yr["cap"], state["stand"], dm.drop, yr["co2"])
        S32 = ds.S.astype(np.float32)
        y = dm.predict(x, f[:, 1], S32).astype(np.float64)
        ds.W, ds.S, ds.D, runoff = dm.bucket(
            y, f[:, 1].astype(np.float64), ds.W, ds.S, ds.D, yr["cap"]
        )
        return {
            "interc": y[:, 1],
            "transp": y[:, 2],
            "evap": y[:, 3],
            "gpp": y[:, 6],
            "npp": y[:, 7],
            "runoff": runoff,
            "swe": ds.S,
            "soilw": ds.W,
            "deep": ds.D,
        }

    def end_year(self, state):
        """Close a year of exactly 365 days: yearly climate statistics, structure and stand maps;
        the stand becomes next year's daily-model input. Returns dict q -> (N,)."""
        su, iy, yr = state["setup"], state["iy"], state.get("year")
        if yr is None or yr["d"] != 365:
            raise RuntimeError("end_year needs exactly 365 step_day calls since begin_year")
        forcing = yr["forcing"]
        n = forcing.shape[0]
        clim = state["clim"](
            forcing[:, :, 0], forcing[:, :, 1], forcing[:, :, 4], forcing[:, :, 2], forcing[:, :, 3]
        )
        win = state["window"].push(clim)
        feat = self.features(su, iy, win)
        if yr["co2_win"] is not None:  # as clu_emu_maps.window / rows_for
            feat["co2_win"] = np.broadcast_to(yr["co2_win"], (n,)).astype(np.float64)
            feat["dco2_win"] = feat["co2_win"] - np.broadcast_to(
                np.asarray(su.aco2, np.float64), (n,)
            )
        ann = self.annual.predict(feat)
        if self.annual.dep:
            self._apply_departure(state, clim, win, ann)
        ps = state.get("pop")
        if (
            ps is not None
        ):  # the population maps read the structure map's inputs (no departure), ADR 0363 sec. 3
            for q in POP_Q:
                a = ps.anc[q]
                feat[f"anc_{q}"] = a if a.ndim == 1 else a[:, iy]
                feat[f"s0_{q}"], feat[f"memoff_{q}"] = ps.s0[q], ps.memoff[q]
            # "pop_" prefix: the four trait medians are structure-map outputs too (must not change)
            ann.update({f"pop_{k}": x for k, x in self.pop.predict(feat).items()})
        new = self.stand_input(np.column_stack([ann[q] for q in STAND_Q]))
        state["stand"] = np.where(
            np.isfinite(new), new, state["stand"]
        )  # no anchor -> keep last year's stand
        state["iy"] = iy + 1
        state["year"] = None
        return ann

    def virtual_trees(self, state, ann, year, cells=None):
        """The year's virtual trees (ADR 0363 sec. 4, 12) from end_year's output ``ann`` of that
        year: index of the
        cell in the setup -> name -> (N,) (``Type`` and POP_VARS), for ``cells`` (indices; default
        all). Needs the
        run started with a population setup."""
        ps = state.get("pop")
        if ps is None:
            raise ValueError("start the run with a population setup to get virtual trees")
        out = {}
        for i in range(len(ps.cell)) if cells is None else cells:
            Q = {
                v: np.array([ann[f"pop_{v}_{pn}"][i] for pn in self.pop.cfg["levels"]])
                for v in POP_VARS
            }
            if not all(np.isfinite(q).all() for q in Q.values()):
                continue
            sh = np.nan_to_num(np.array([ann[f"pop_share_{t}"][i] for t in range(7)]))
            vt = virtual_trees(
                ann["n_per_patch"][i], sh, Q, ps.donor(i), seed=int(ps.cell[i]) * 7919 + int(year)
            )
            if vt is not None:
                out[i] = vt
        return out

    def diversity(self, vt):
        """Functional-diversity indices of one cell's virtual trees
        (``population.diversity_indices``)."""
        return diversity_indices(vt, self.pop.cfg["diversity_constants"])

    def _apply_departure(self, state, clim, win, ann):
        dep, e = self.annual.dep, float(self.annual.dep["eps"])
        clim = np.asarray(clim, np.float64)
        z0 = self.zscore(clim, state["zbuf"][-int(dep["z_window"]) :], int(dep["z_min"]))
        f = {f"dlag_{q}": state["dlag"][q] for q in dep["quantities"]}
        f.update({f"lvl_{q}": np.asarray(ann[q], np.float64) for q in dep["quantities"]})
        for j, c in enumerate(CLIM_COLS):
            f[c], f[f"z0_{c}"], f[f"z1_{c}"] = win[:, j], z0[:, j], state["zprev"][:, j]
        D = self.annual.departure(f)
        for q in dep["quantities"]:
            v = (np.maximum(ann[q], 0.0) + e) * np.exp(D[q]) - e
            ann[q] = np.maximum(v, 0.0) if q == "n_per_patch" else v
            state["dlag"][q] = D[q]
        state["zbuf"].append(clim)
        if len(state["zbuf"]) > int(dep["z_window"]):
            state["zbuf"].pop(0)
        state["zprev"] = z0

    @staticmethod
    def features(su: Setup, iy, win):
        feat = {"lat": su.lat, "lon": su.lon, "soil_code": su.soil_code}
        acl = su.aclim if su.aclim.ndim == 2 else su.aclim[:, iy]
        for j, c in enumerate(CLIM_COLS):
            feat[c] = win[:, j]
            feat[f"dclim_{c}"] = win[:, j] - acl[:, j]
        for q in STRUCT_Q + STAND_Q:
            a = su.anc[q]
            feat[f"anc_{q}"] = a if a.ndim == 1 else a[:, iy]
            feat[f"s0_{q}"] = su.s0[q]
            feat[f"memoff_{q}"] = su.memoff[q]
        return feat
