"""Python half of the SpeedyWeather <-> learned-emulator coupling (driven from
scripts/online_coupling/run_speedy_landemu.jl through PythonCall).

Each SpeedyWeather land column is represented by the NEAREST 0.5-degree cell of the global
emulator (ADR 0341: release ``global_emu/release/fold_none``, nitrogen off, no CO2 input, anchored
on each cell's own 1985-2014 state). Columns with no emulator cell within ``max_deg`` (Antarctica,
ice, small islands) are left to SpeedyWeather's own land evaporation.

The run starts on 1 January of ``start_year`` (default 2015) from the emulator's own end-of-2014
state of the global historical run (water stores, stand), with the 1985-2014 yearly climate in the
30-year window and the 2014 GFDL-ESM4 weather as the daily model's trailing year. From then on the
emulator only sees SpeedyWeather's weather.

``Coupler.day(F)`` takes one emulator day of weather for the emulated columns (365-day years; the
Julia side folds 29 February into 28 February) and returns the day's evapotranspiration
(interception + transpiration + soil evaporation, mm/day). Everything the emulator saw and
produced is recorded, so ``replay`` can re-run the same weather through ``step_year`` offline and
prove the coupled emulator is the released one, bit for bit.
"""

from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [os.path.join(REPO, "python", "src"), os.path.join(REPO, "scripts")]

DATA = "/p/projects/open/Jamir/esm_land_emulator_data/global_emu"
RELEASE = os.path.join(DATA, "release", "fold_none")
REC_DAILY = ["interc", "transp", "evap", "gpp", "npp", "runoff", "swe", "soilw", "deep"]


def nearest_cells(lat, lon, clat, clon, chunk=256):
    """Great-circle nearest of (clat, clon) for every (lat, lon); returns index, distance (deg)."""

    def xyz(a, o):
        a, o = np.radians(a), np.radians(o)
        return np.stack([np.cos(a) * np.cos(o), np.cos(a) * np.sin(o), np.sin(a)], -1)

    p, c = xyz(np.asarray(lat, float), np.asarray(lon, float)), xyz(clat, clon)
    idx = np.zeros(len(p), np.int64)
    dist = np.zeros(len(p))
    for i in range(0, len(p), chunk):
        dot = p[i : i + chunk] @ c.T
        k = dot.argmax(1)
        idx[i : i + chunk] = k
        dist[i : i + chunk] = np.degrees(np.arccos(np.clip(dot[np.arange(len(k)), k], -1, 1)))
    return idx, dist


def end_of_2014_state(cv):
    """The global historical emulator run's end-of-2014 stores and stand for cells cv."""
    d = os.path.join(DATA, "emu", "historical", "chunks")
    W, S, D = (np.full(len(cv), np.nan) for _ in range(3))
    stand = np.full((len(cv), 12), np.nan)
    pos = {c: i for i, c in enumerate(cv)}
    for fn in sorted(os.listdir(d)):
        if not fn.endswith("_end.npz"):
            continue
        z = np.load(os.path.join(d, fn))
        for j, c in enumerate(z["cell"]):
            for i in [pos[c]] if c in pos else []:
                W[i], S[i], D[i], stand[i] = z["W"][j], z["S"][j], z["D"][j], z["stand_raw"][j]
    assert np.isfinite(W).all() and np.isfinite(stand).all(), "cell without an end-of-2014 state"
    return W, S, D, stand


def build_setup(cv, start_year):
    """Setup for emulator cells cv (unique or not), fixed anchors (ADR 0341 sec. 3)."""
    import glob_emu as g
    from build_transient_boundary import open_clm
    from lpjmlfit_emulator.landemu import Setup
    from lpjmlfit_emulator.landemu.annual import STAND_Q, STRUCT_Q

    st = g.cells().sort("Cell")
    assert (st["Cell"].to_numpy() == np.arange(g.NCELL)).all()
    P = os.path.join(DATA, "setup")
    ancm = np.load(os.path.join(P, "anchors.npy"), mmap_mode="r")
    qorder = json.load(open(os.path.join(P, "anchors.json")))
    qs = STRUCT_Q + STAND_Q
    assert qorder == qs
    ch = np.load(os.path.join(P, "clim_hist.npy"), mmap_mode="r")  # (1951-2014, NCELL, 25)
    H = np.stack([np.asarray(ch[y - 1951, cv], np.float64) for y in range(g.YH0, g.YH1 + 1)])
    warm = []
    for v in g.FORC_VARS:  # the 2014 GFDL-ESM4 weather (the global run's own forcing)
        mm, fy, ncell, nb, sc = open_clm(g.CLM["historical"].format(v=v))
        assert ncell == g.NCELL and nb == 365
        warm.append(np.asarray(mm[g.YH1 - fy, cv], np.float64) * sc)
    W, S, D, stand0 = end_of_2014_state(cv)
    n = len(cv)
    su = Setup(
        cell=cv,
        lat=st["lat"].to_numpy()[cv],
        lon=st["lon"].to_numpy()[cv],
        soil_code=st["soil_code"].to_numpy()[cv].astype(np.float64),
        year0=start_year,
        anc={q: np.asarray(ancm[cv, j], np.float64) for j, q in enumerate(qs)},
        aclim=np.asarray(np.load(os.path.join(P, "aclim.npy"), mmap_mode="r")[cv], np.float64),
        s0={q: np.zeros(n) for q in qs},
        memoff={q: np.zeros(n) for q in qs},
        clim_hist=H,
        cap=st["cap"].to_numpy()[cv].astype(np.float64),
        W0=W,
        S0=S,
        D0=D,
        stand0=stand0,
        warm=np.stack(warm, -1).astype(np.float32),
    )
    return su


class Coupler:
    def __init__(self, lat, lon, out_dir, max_deg=3.0, start_year=2015, release=RELEASE):
        import glob_emu as g
        import polars as pl
        from lpjmlfit_emulator.landemu import LandEmulator

        t0 = time.time()
        st = g.cells().sort("Cell").filter(~pl.col("rock"))
        cand = st["Cell"].to_numpy()
        k, dist = nearest_cells(lat, lon, st["lat"].to_numpy(), st["lon"].to_numpy())
        self.mask = dist <= max_deg
        self.cell = cand[k[self.mask]].astype(np.int64)
        self.dist = dist
        self.lat, self.lon = np.asarray(lat, float), np.asarray(lon, float)
        self.out_dir, self.release, self.start_year = out_dir, release, start_year
        os.makedirs(out_dir, exist_ok=True)
        self.emu = LandEmulator.load(release)
        self.su = build_setup(self.cell, start_year)
        self.state = self.emu.start(self.su)
        self.n = len(self.cell)
        self.doy, self.year = 0, start_year
        self.rec_forc, self.rec_day, self.rec_ann = [], {k: [] for k in REC_DAILY}, []
        self.t_emu = 0.0
        self.t_setup = time.time() - t0
        print(
            f"landemu coupler: {self.mask.sum()} of {len(self.mask)} land columns emulated "
            f"({len(np.unique(self.cell))} distinct cells, max distance "
            f"{dist[self.mask].max():.2f} deg), setup {self.t_setup:.0f} s",
            flush=True,
        )

    def day(self, F):
        """F (n, 5) float64: tas degC, pr mm/day, rsds W/m2, lwnet W/m2, huss kg/kg for the emulated
        columns, in column order. Returns the day's evapotranspiration, mm/day, (n,)."""
        t0 = time.time()
        F = np.asarray(F, np.float64)
        assert F.shape == (self.n, 5) and np.isfinite(F).all(), "bad forcing from the atmosphere"
        if self.doy == 0:
            self.emu.begin_year(self.state)
        out = self.emu.step_day(self.state, F)
        self.rec_forc.append(F.copy())
        for k in REC_DAILY:
            self.rec_day[k].append(np.asarray(out[k], np.float64).copy())
        self.doy += 1
        if self.doy == 365:
            ann = self.emu.end_year(self.state)
            self.rec_ann.append({q: np.asarray(v, np.float64) for q, v in ann.items()})
            self.doy, self.year = 0, self.year + 1
        self.t_emu += time.time() - t0
        return out["interc"] + out["transp"] + out["evap"]

    def finish(self, extra=None):
        """Write the record (complete years only are replayable)."""
        ny = len(self.rec_ann)
        z = {
            "cell": self.cell,
            "mask": self.mask,
            "dist": self.dist,
            "col_lat": self.lat,
            "col_lon": self.lon,
            "start_year": self.start_year,
            "n_years": ny,
            "forcing": np.stack(self.rec_forc, 1),  # (n, days, 5)
            "t_emu": self.t_emu,
            "t_setup": self.t_setup,
            **{f"d_{k}": np.stack(v, 1) for k, v in self.rec_day.items()},
            **{
                f"a_{q}": np.stack([a[q] for a in self.rec_ann], 1)
                for q in (self.rec_ann or [{}])[0]
            },
        }
        for k, v in (extra or {}).items():
            z[f"x_{k}"] = np.asarray(v)
        path = os.path.join(self.out_dir, "landemu_record.npz")
        np.savez(path, **z)
        print(
            f"landemu record -> {path} ({ny} full years, emulator {self.t_emu:.1f} s)", flush=True
        )
        return path


def replay(path, release=RELEASE):
    """Re-run the recorded weather through step_year offline; every output must be identical."""
    from lpjmlfit_emulator.landemu import LandEmulator

    z = np.load(path)
    cell, ny, y0 = z["cell"], int(z["n_years"]), int(z["start_year"])
    emu = LandEmulator.load(release)
    st = emu.start(build_setup(cell, y0))
    worst = {}
    for i in range(ny):
        daily, ann = emu.step_year(st, z["forcing"][:, 365 * i : 365 * (i + 1)])
        for k in REC_DAILY:
            ref = z[f"d_{k}"][:, 365 * i : 365 * (i + 1)]
            worst[k] = max(
                worst.get(k, 0.0), float(np.max(np.abs(daily[k] - ref.astype(np.float32))))
            )
        for q, v in ann.items():
            ref = z[f"a_{q}"][:, i]
            same_nan = np.array_equal(np.isnan(v), np.isnan(ref))
            diff = float(np.nanmax(np.abs(v - ref))) if same_nan else float("inf")
            worst[q] = max(worst.get(q, 0.0), diff)
    return worst


if __name__ == "__main__":  # python landemu_coupler.py replay <record.npz>
    if sys.argv[1] == "replay":
        w = replay(sys.argv[2])
        print("max |coupled - offline| per output:", json.dumps(w))
        sys.exit(0 if max(w.values()) == 0.0 else 1)
