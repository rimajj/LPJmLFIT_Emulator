#!/usr/bin/env python3
"""build_emulator_forcing.py -- daily WEATHER arrays for the emulator on panel legs that have no f2 arrays (ADR 0366).

The f2 builder (f2_build_daily_table.py) writes forcing only for legs with daily output of the original, because it
gates the forcing against that output. The emulator needs only the weather, so this writes it for any scenario leg:

  <F2>/forc_leg/<leg>.npy   (1050, 82*365, 5) float32 tas pr rsds lwnet huss, days of 2019..2100 in the f2 cell order;
                            2019 = observed (what the original saw before 2020), 2020..2100 = the leg's .clm files
  <F2>/forc_leg/obs_1999_2019.npy  (1050, 21*365, 5) the observed weather of 1999..2019 (the emulated-NPP history
                            of ADR 0366 sec. 1)

GATE G1 (FATAL, before anything is written): the same code re-derives existing f2 arrays bit for bit
(gfdl-esm4_ssp370 vs forc_m1_gfdl-esm4_ssp370_daily, ukesm1-0-ll_ssp370 vs forc_m1_ukesm1-0-ll_ssp370), and the
observed 2019 slice equals their first year.

Usage: python scripts/build_emulator_forcing.py [--legs a,b,...]   (default: every scenario leg without f2 forcing)
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_panel_a7 as A7  # noqa: E402
import explore_panel_prep as PP  # noqa: E402

F2 = "/p/projects/reformit/Jamir/esm_land_emulator_data/f2"
OUTD = os.path.join(F2, "forc_leg")
ORDER = ["temp", "prec", "swdown", "lwnet", "humid"]  # -> tas pr rsds lwnet huss (the f2 order)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def f2_forcing(leg: str, member: int = 1) -> str | None:
    """Path of the weather array for a scenario leg: the f2 array (same weather for every run of a scenario leg),
    else this script's forc_leg/<leg>.npy; None if neither exists."""
    for p in (os.path.join(F2, f"forc_m{member}_{leg}_daily.npy"), os.path.join(F2, f"forc_m{member}_{leg}.npy"),
              os.path.join(OUTD, f"{leg}.npy")):
        if os.path.exists(p):
            return p
    return None


def read(src: dict, years, cells: np.ndarray) -> np.ndarray:
    out = np.empty((len(cells), len(years) * 365, 5), np.float32)
    for j, v in enumerate(ORDER):
        mm, fy, sc = src[v]
        for i, y in enumerate(years):
            out[:, i * 365:(i + 1) * 365, j] = np.asarray(mm[y - fy][cells], dtype=np.float32) * sc
    return out


def build(leg: str, cells: np.ndarray, obs2019: np.ndarray) -> np.ndarray:
    fut = read(PP._open(PP._scen_paths(leg)), range(2020, 2101), cells)
    return np.concatenate([obs2019, fut], axis=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--legs", default=None)
    a = ap.parse_args()
    cells = pl.read_parquet(os.path.join(F2, "cells.parquet"))["Cell"].to_numpy()
    obs = PP._open(PP.OBS)
    hist = read(obs, range(1999, 2020), cells)
    obs2019 = hist[:, -365:]

    # GATE G1
    for leg, ref in (("gfdl-esm4_ssp370", "forc_m1_gfdl-esm4_ssp370_daily.npy"),
                     ("ukesm1-0-ll_ssp370", "forc_m1_ukesm1-0-ll_ssp370.npy")):
        r = np.load(os.path.join(F2, ref), mmap_mode="r")
        x = build(leg, cells, obs2019)
        assert x.shape == r.shape, (x.shape, r.shape)
        eq = np.array_equal(x, np.asarray(r))
        log(f"GATE G1 {leg} vs {ref}: shape {x.shape}, bit-identical {eq}, max |diff| "
            f"{float(np.abs(x - r).max()):.2e}")
        assert eq, "re-derived forcing differs from the f2 array"
        assert np.array_equal(obs2019, np.asarray(r[:, :365])), "observed 2019 differs"

    os.makedirs(OUTD, exist_ok=True)
    np.save(os.path.join(OUTD, "obs_1999_2019.npy"), hist)
    legs = a.legs.split(",") if a.legs else [lg for lg in A7.ALL_SLEGS if f2_forcing(lg) is None]
    log(f"{len(legs)} legs to write: {legs}")
    for leg in legs:
        t0 = time.time()
        x = build(leg, cells, obs2019)
        assert np.isfinite(x).all(), leg
        np.save(os.path.join(OUTD, f"{leg}.npy"), x)
        log(f"{leg}: {x.shape}, tas 2091-2100 mean {x[:, -3650:, 0].mean():.2f} C, pr {x[:, -3650:, 1].mean():.2f} "
            f"mm/d ({time.time() - t0:.0f}s)")
    missing = [lg for lg in A7.ALL_SLEGS if f2_forcing(lg) is None]
    assert not missing, missing
    log("every scenario leg has a weather array")


if __name__ == "__main__":
    main()
