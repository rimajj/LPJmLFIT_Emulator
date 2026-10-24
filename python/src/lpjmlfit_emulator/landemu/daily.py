"""The learned daily water-carbon model in plain numpy (no deep-learning framework at run time).

Port of ``scripts/f2_train.py`` (``Net`` with ``npp_head="ra"``, ``carbon_head="free"``,
``Ensemble``,
``bucket_step`` with a draining deep store, the input assembly of
``assemble``/``forcing_features``). The weights are
exported from the trained PyTorch members by ``scripts/build_emulator_release.py``, which gates
this port against the
PyTorch forward pass before a release is written.

Outputs per day (mm or gC/m2): interception, transpiration, soil evaporation, runoff (after the
bucket), GPP, NPP;
state: snow water equivalent ``S``, plant-available water of the top metre ``W`` (closed bucket,
capacity ``cap``) and
a deep store ``D`` that drains into runoff with time constant ``deep_tau`` days.

A model trained with ``f2_train.py --co2`` (ADR 0342; the nitrogen-on LPJmL-FIT only) reads one
more input, the year's atmospheric CO2 in ppm / 1000, as its last column
(``DailyModel.co2_input``; ADR 0344).

A model trained with ``f2_train.py --soil-texture`` (ADR 0348) reads four per-cell columns after
every other input (after CO2): sand and clay fraction, ln Ks (mm/h) and ln Sf (mm) of the cell's
soil type. The release carries them as ``soil_table`` (one row per soil code 1..13, float32,
computed as ``f2_train.soil_columns``); ``DailyModel.soil_columns`` looks a setup's codes up in it
(ADR 0367). A release without the table runs exactly as before.

A model trained with weather-memory extras (``scripts/xtf_daily.py`` arms MEPh / MEPt,
ADR 0372) reads two more groups after every other input, declared in ``daily.npz``
(``ema_tau``, ``place_mode``):
32 exponential running means of tas, rain, rsds and lwnet at the time scales ``ema_tau`` days
(updated every day, started from the mean of the warm-up year; rain as log1p of its mean), and a
52-number description of the place (the mean of each of 12 parts of the year and the daily spread
of tas, log1p rain, rsds, lwnet) over the 30 years before the run (``place_mode`` "fixed") or
before each year (``"trailing"``, rebuilt at every year end). The setup carries the 30 years'
yearly summaries (``place_year_parts``). A release without these keys runs exactly as before.
"""

from __future__ import annotations

import numpy as np

NFORC = 12
NIN = NFORC + 3 + 4 + 12
FEAT_HUSS = 4
NPLACE = 52
PLACE_MONTH = (np.arange(365) * 12) // 365  # day of year -> one of 12 parts of the year


def place_year_parts(f):
    """One year's summaries for the place description: f (N, 365, >=4) daily tas, pr, rsds, lwnet
    -> (mon (N, 12, 4) means of the 12 parts of the year, s1 (N, 4) sum, s2 (N, 4) sum of squares),
    float64, with rain as log1p (xtf_daily.trailing_place)."""
    v = np.asarray(f, np.float64)[:, :, :4].copy()
    v[..., 1] = np.log1p(v[..., 1])
    mon = np.stack([v[:, PLACE_MONTH == j].mean(1) for j in range(12)], 1)
    return mon, v.sum(1), (v * v).sum(1)


def place_description(mon, s1, s2):
    """(N, 52) float32 from the summaries of Y years (each (Y, N, ...)): the mean of the 12 parts'
    means, then the standard deviation of all daily values."""
    mon, s1, s2 = (np.asarray(a, np.float64) for a in (mon, s1, s2))
    n_days = mon.shape[0] * 365
    mu, ex2 = s1.sum(0) / n_days, s2.sum(0) / n_days
    m = mon.sum(0) / mon.shape[0]
    sd = np.sqrt(np.maximum(ex2 - mu * mu, 0))
    return np.concatenate([m.reshape(m.shape[0], 48), sd], -1).astype(np.float32)


def _softplus(x):
    return np.where(x > 20.0, x, np.log1p(np.exp(np.minimum(x, 20.0))))


def _sigmoid(x):
    with np.errstate(over="ignore"):  # exp(-x) -> inf for x << 0 gives the exact limit 0
        return 1.0 / (1.0 + np.exp(-x))


def daylength_decl(lat_deg):
    """The daily model's own day-length input (f2_train.daylength): (N,) lat -> (N, 365) hours,
    float32."""
    doy = np.arange(1, 366)
    decl = -0.4093 * np.cos(2 * np.pi * (doy + 10) / 365.0)
    t = -np.tan(np.radians(lat_deg))[:, None] * np.tan(decl)[None, :]
    return (24.0 / np.pi * np.arccos(np.clip(t, -1, 1))).astype(np.float32)


class Member:
    """One network: normalisation, an MLP trunk with SiLU activations, 9 raw outputs."""

    def __init__(self, z):
        self.mu, self.sd, self.ysd = (np.asarray(z[k], np.float32) for k in ("mu", "sd", "ysd"))
        nl = int(z["n_layers"])
        self.W = [np.asarray(z[f"W{i}"], np.float32) for i in range(nl + 1)]  # (out, in) like torch
        self.b = [np.asarray(z[f"b{i}"], np.float32) for i in range(nl + 1)]

    def __call__(self, x, prec, S_prev):
        h = (x - self.mu) / self.sd
        for W, b in zip(self.W[:-1], self.b[:-1], strict=True):
            h = h @ W.T + b
            h = h * _sigmoid(h)
        o = h @ self.W[-1].T + self.b[-1]
        ys = self.ysd
        f, m, i = _sigmoid(o[:, 0]), _sigmoid(o[:, 1]), _sigmoid(o[:, 2])
        gpp = _softplus(o[:, 7]) * ys[6]
        npp = gpp - _softplus(o[:, 8]) * ys[7]
        return np.stack(
            [
                prec * f - m * S_prev,
                prec * i,
                _softplus(o[:, 3]) * ys[2],
                _softplus(o[:, 4]) * ys[3],
                _softplus(o[:, 5]) * ys[4],
                o[:, 6] * ys[5],
                gpp,
                npp,
            ],
            -1,
        )


class DailyModel:
    """The ensemble (mean of the members' outputs) and the closed water bucket."""

    def __init__(
        self,
        members,
        drop=(FEAT_HUSS,),
        deep_tau=365.0,
        co2_input=False,
        soil_table=None,
        ema_tau=None,
        place_mode=None,
    ):
        self.members = members
        self.drop = list(drop)
        self.deep_tau = float(deep_tau)
        self.co2_input = bool(co2_input)
        self.soil_table = None if soil_table is None else np.asarray(soil_table, np.float32)
        self.ema_tau = None if ema_tau is None else tuple(float(t) for t in ema_tau)
        if place_mode not in (None, "fixed", "trailing"):
            raise ValueError(f"unknown place_mode {place_mode!r}")
        self.place_mode = place_mode

    @property
    def n_extra(self):
        """Columns of the weather-memory extras (0 for a release without them)."""
        n = 0 if self.ema_tau is None else 4 * len(self.ema_tau)
        return n + (NPLACE if self.place_mode else 0)

    @property
    def soil_input(self):
        return self.soil_table is not None

    def soil_columns(self, soil_code):
        """(N,) soil codes 1..13 -> (N, 4) float32 sand, clay, ln Ks, ln Sf (None without
        texture)."""
        if self.soil_table is None:
            return None
        code = np.asarray(soil_code).astype(np.int64)
        if code.min() < 1 or code.max() > len(self.soil_table):
            raise ValueError(f"soil code outside 1..{len(self.soil_table)}")
        return self.soil_table[code - 1]

    @classmethod
    def load(cls, path):
        z = np.load(path)
        n = int(z["n_members"])
        members = [
            Member({k.split("/", 1)[1]: z[k] for k in z.files if k.startswith(f"m{i}/")})
            for i in range(n)
        ]
        co2 = bool(z["co2_input"]) if "co2_input" in z.files else False
        soil = z["soil_table"] if "soil_table" in z.files else None
        drop, tau = list(z["drop"]), float(z["deep_tau"])
        ema = z["ema_tau"] if "ema_tau" in z.files else None
        place = str(z["place_mode"]) if "place_mode" in z.files else None
        return cls(
            members,
            drop=drop,
            deep_tau=tau,
            co2_input=co2,
            soil_table=soil,
            ema_tau=ema,
            place_mode=place,
        )

    def predict(self, x, prec, S_prev):
        return np.mean([m(x, prec, S_prev) for m in self.members], 0)

    def bucket(self, y, prec, W, S, D, cap):
        dS, interc, transp, evap, runoff, deep = (y[:, j] for j in range(6))
        S2 = S + dS
        W2 = W + prec - dS - interc - transp - evap - runoff - deep
        over = np.maximum(W2 - cap, 0.0)
        under = np.maximum(-W2, 0.0)
        W2 = W2 - over + under
        runoff = runoff + over
        deep = deep - under
        D2 = D + deep
        if self.deep_tau > 0:
            release = D2 / self.deep_tau
            D2 = D2 - release
            runoff = runoff + release
        return W2, S2, D2, runoff


class DailyState:
    """Everything the daily model carries from one day to the next for N cells: the stores and the
    trailing weather
    sums of the last 365 days (rain), 30 days (air temperature, shortwave) and 10 days (air
    temperature)."""

    def __init__(self, lat, W, S, D, warm, soil=None, ema_tau=None, place=None, place_mode=None):
        """warm: (N, 365, 5) the 365 days before the first emulated day (tas, pr, rsds, lwnet,
        huss); soil: (N, 4) the texture columns of a texture model (``DailyModel.soil_columns``);
        ema_tau / place / place_mode: the weather-memory extras of a model that has them
        (``DailyModel.ema_tau``, ``place_mode``), place = (mon, s1, s2) the yearly summaries of
        the 30 years before the first emulated year (``place_year_parts``, each (30, N, ...))."""
        lat = np.asarray(lat, np.float64)
        self.soil = None if soil is None else np.asarray(soil, np.float32)
        self.slat = np.sin(np.radians(lat)).astype(np.float32)
        self.dl = daylength_decl(lat)
        self.W, self.S, self.D = (np.asarray(v, np.float64).copy() for v in (W, S, D))
        warm = np.asarray(warm, np.float32)
        self.b10 = warm[:, -10:, 0].copy()
        self.b30t = warm[:, -30:, 0].copy()
        self.b30r = warm[:, -30:, 2].copy()
        self.bp = warm[:, :, 1].copy()
        self.s = {
            "t10": self.b10.sum(1, dtype=np.float64),
            "t30": self.b30t.sum(1, dtype=np.float64),
            "r30": self.b30r.sum(1, dtype=np.float64),
            "p30": self.bp[:, -30:].sum(1, dtype=np.float64),
            "p90": self.bp[:, -90:].sum(1, dtype=np.float64),
            "p365": self.bp.sum(1, dtype=np.float64),
        }
        self.k = 0  # days pushed so far (ring-buffer position)
        self.ema = None
        # as xtf_daily.ema_bank: start at the warm-up year's mean, then run through its days
        if ema_tau is not None:
            K = len(ema_tau)
            v = warm[:, :, :4].astype(np.float64)
            self.tau = np.tile(np.asarray(ema_tau, np.float64), 4)
            self.ema = np.repeat(v.mean(1), K, axis=1)
            for t in range(v.shape[1]):
                self.ema = self.ema + (np.repeat(v[:, t], K, axis=1) - self.ema) / self.tau
        self.place_mode, self.place_parts, self.place = place_mode, None, None
        if place_mode is not None:
            if place is None:
                raise ValueError("this daily model reads a place description: setup needs place_*")
            self.place_parts = [list(np.asarray(a, np.float64)) for a in place]  # 3 lists of years
            self.place = place_description(*place)

    def end_year(self, forcing):
        """A trailing place description moves on by the year just finished (N, 365, >=4)."""
        if self.place_mode != "trailing":
            return
        for buf, new in zip(self.place_parts, place_year_parts(forcing), strict=True):
            buf.append(new)
            buf.pop(0)
        self.place = place_description(*(np.stack(b) for b in self.place_parts))

    def push(self, f):
        """Advance the trailing sums by one day of weather f (N, 5)."""
        tas, pr, rs = f[:, 0], f[:, 1], f[:, 2]
        i10, i30, i365 = self.k % 10, self.k % 30, self.k % 365
        s = self.s
        s["t10"] += tas - self.b10[:, i10]
        self.b10[:, i10] = tas
        s["t30"] += tas - self.b30t[:, i30]
        self.b30t[:, i30] = tas
        s["r30"] += rs - self.b30r[:, i30]
        self.b30r[:, i30] = rs
        s["p365"] += pr - self.bp[:, i365]
        s["p90"] += pr - self.bp[:, (i365 - 90) % 365]
        s["p30"] += pr - self.bp[:, (i365 - 30) % 365]
        self.bp[:, i365] = pr
        self.k += 1
        if self.ema is not None:
            K = len(self.tau) // 4
            today = np.repeat(f[:, :4].astype(np.float64), K, axis=1)
            self.ema = self.ema + (today - self.ema) / self.tau

    def extras(self):
        """(N, n_extra) float32: the running means (rain as log1p) then the place description."""
        parts = []
        if self.ema is not None:
            e = self.ema.astype(np.float32)
            K = e.shape[1] // 4
            e[:, K : 2 * K] = np.log1p(np.maximum(e[:, K : 2 * K], 0))
            parts.append(e)
        if self.place is not None:
            parts.append(self.place)
        return np.concatenate(parts, -1) if parts else None

    def inputs(self, f, doy0, cap, stand, drop, co2=None):
        """The network input (N, NIN) for today's weather f, 0-based day of year doy0, soil
        capacity cap (N,) and the
        stand vector (N, 12: leaf area, log1p vegetation carbon, cover of the 10 plant types);
        with ``co2`` (the year's CO2, ppm, scalar or (N,)) one more column, (N, NIN + 1); with
        texture (``self.soil``) four more after it."""
        n = f.shape[0]
        nc = NIN + (co2 is not None)
        ex = self.extras()
        ns = nc + 4 * (self.soil is not None)
        x = np.empty((n, ns + (0 if ex is None else ex.shape[1])), np.float32)
        s = self.s
        x[:, 0], x[:, 1], x[:, 2], x[:, 3], x[:, 4] = (
            f[:, 0],
            np.log1p(f[:, 1]),
            f[:, 2],
            f[:, 3],
            f[:, 4] * 1000.0,
        )
        x[:, 5], x[:, 6], x[:, 7] = s["t10"] / 10, s["t30"] / 30, s["r30"] / 30
        x[:, 8], x[:, 9], x[:, 10] = np.log1p(s["p30"]), np.log1p(s["p90"]), np.log1p(s["p365"])
        x[:, 11] = self.dl[:, doy0]
        a = (
            2 * np.pi * (doy0 + 1) / 365.0
        )  # float64, cast on assignment (as f2_train.calendar_features)
        x[:, NFORC], x[:, NFORC + 1], x[:, NFORC + 2] = np.sin(a), np.cos(a), self.slat
        Wf, capf = self.W.astype(np.float32), np.asarray(cap, np.float32)
        x[:, NFORC + 3] = Wf / np.maximum(capf, 1.0)
        x[:, NFORC + 4] = Wf / 1000.0
        x[:, NFORC + 5] = np.log1p(self.S.astype(np.float32))
        x[:, NFORC + 6] = capf / 1000.0
        x[:, NFORC + 7 : NIN] = stand
        if co2 is not None:  # as f2_train.assemble: float32 ppm / 1000
            x[:, NIN] = np.asarray(co2, np.float32) / np.float32(1000.0)
        if self.soil is not None:  # as f2_train.assemble: after every other column
            x[:, nc:ns] = self.soil
        if ex is not None:  # as xtf_daily (ADR 0372): after B's whole input vector
            x[:, ns:] = ex
        if drop:
            x[:, drop] = 0.0
        return x
