"""Python half of the POEM <-> learned-emulator coupling (ADR 0347).

POEM 1.2 (AM2 atmosphere on the FV core, MOM5 ocean, LPJmL 5.9 land at 0.5 degrees) runs this module
inside every land MPI rank through the embedded interpreter of its LPJmL bridge
``src/land_atlantes/LPJmL/src/landemu_py.c`` (patches in ``patches/poem/``), switched on by
``LANDEMU=1``. The C side passes plain float64 arrays as ``bytes``; this module keeps one
``landemu_coupler.Coupler`` per rank.

Each LPJmL cell of the rank is represented by the emulator cell at the SAME 0.5-degree position
(``max_deg`` 0.01: the two grids coincide; no nearest-column approximation as in SpeedyWeather).
LPJmL cells without one (Antarctica, ice, rock, cells the global run does not have) keep LPJmL's
own fluxes; ``mask()`` tells the C side which.

``day(F, X, nx)`` takes one day of weather for ALL the rank's cells, (ncell, 5): 2-m air
temperature degC, precipitation mm/day, downward shortwave W/m2, net longwave W/m2, 2-m specific
humidity kg/kg (rows of unmatched cells are ignored), plus nx recorded-only columns (LPJmL's own
land evapotranspiration and runoff, mm/day, and its surface temperature, degC), and returns
(ncell, 2): the emulator's evapotranspiration and runoff, mm/day per unit land area, NaN where not
emulated. ``finish()`` writes the rank's record, which ``landemu_coupler.replay`` re-runs offline.

Environment: LANDEMU_OUT (record directory; one ``rank<NNNN>/`` per rank), LANDEMU_START_YEAR
(the emulator's label for the first year, default 2015 as ADR 0345 -- its anchors are fixed, so
the label does not change the result).
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")  # one core per MPI rank; set before numpy is imported

import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import landemu_coupler as lc  # noqa: E402

MAX_DEG = 0.01
NOUT = 2
_C = None


class PoemCoupler(lc.Coupler):
    def __init__(self, lat, lon, out_dir, rank, start_year):
        self.ncell, self.rank = len(lat), rank
        super().__init__(lat, lon, out_dir, max_deg=MAX_DEG, start_year=start_year)
        self.rec_x = []
        self.t_year = time.time()

    def day_all(self, F_all, X_all):
        out = np.full((self.ncell, NOUT), np.nan)
        et = super().day(F_all[self.mask])
        out[self.mask, 0] = et
        out[self.mask, 1] = self.last["runoff"]
        self.rec_x.append(X_all[self.mask].copy())
        if self.doy == 0:  # a year just closed
            print(
                f"landemu rank {self.rank}: year {self.year - 1} done, "
                f"{time.time() - self.t_year:.0f} s wall, emulator {self.t_emu:.1f} s so far",
                flush=True,
            )
            self.t_year = time.time()
        return out

    def finish(self, extra=None):
        ny = len(self.rec_ann)
        x = np.stack(self.rec_x[: 365 * ny], 1) if ny else np.zeros((self.n, 0, 3))
        return super().finish(extra={"lpj": x, "rank": self.rank, "ncell": self.ncell})


class NoCells:
    """A rank whose LPJmL cells have no emulator cell (e.g. the band that holds only Antarctica)."""

    def __init__(self, ncell, rank):
        self.ncell, self.rank = ncell, rank
        self.mask = np.zeros(ncell, bool)

    def day_all(self, F_all, X_all):
        return np.full((self.ncell, NOUT), np.nan)

    def finish(self):
        print(f"landemu rank {self.rank}: no emulated cells, no record", flush=True)


def n_matches(lat, lon):
    """How many of (lat, lon) the Coupler would match (same candidates and distance)."""
    import glob_emu as g
    import polars as pl

    st = g.cells().sort("Cell").filter(~pl.col("rock"))
    _, dist = lc.nearest_cells(lat, lon, st["lat"].to_numpy(), st["lon"].to_numpy())
    return int((dist <= MAX_DEG).sum())


def start(lat_b, lon_b, rank):
    global _C
    lat = np.frombuffer(lat_b, np.float64).copy()
    lon = np.frombuffer(lon_b, np.float64).copy()
    out = os.path.join(os.environ["LANDEMU_OUT"], f"rank{rank:04d}")
    with np.errstate(invalid="ignore"):  # skipped LPJmL cells come as NaN and are never matched
        if n_matches(lat, lon) == 0:
            _C = NoCells(len(lat), rank)
        else:
            _C = PoemCoupler(lat, lon, out, rank, int(os.environ.get("LANDEMU_START_YEAR", "2015")))
    return int(_C.mask.sum())


def mask():
    return _C.mask.astype(np.int8).tobytes()


def day(F_b, X_b, nx):
    F = np.frombuffer(F_b, np.float64).reshape(_C.ncell, 5)
    X = np.frombuffer(X_b, np.float64).reshape(_C.ncell, nx)
    return np.ascontiguousarray(_C.day_all(F, X), np.float64).tobytes()


def finish():
    _C.finish()
