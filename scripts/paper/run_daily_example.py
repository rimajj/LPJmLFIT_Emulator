#!/usr/bin/env python3
"""run_daily_example.py -- paper figure input: run the validated fold release of the learned emulator
(release/fold_gfdl-esm4_v1: structure/stand maps never saw GFDL-ESM4 or run m4; the daily networks never saw the
biome blocks) over GFDL-ESM4 ssp370, run m4, 2020-2100, and keep the DAILY outputs of the 50 cells of the five
biome blocks, next to the original's daily output of runs m4 (the truth) and m1 (a second run).

Output: esm_land_emulator_data/paper/daily_example.npz. One core, ~12 min (all 1 050 cells must run: the setup
and the yearly maps are vectorised over the panel). Usage: scripts/sbatch_python.sh paper-daily <this>
"""

import os

for _v in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ[_v] = "1"

import sys  # noqa: E402

import numpy as np  # noqa: E402
import polars as pl  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "python", "src"))
from lpjmlfit_emulator.landemu import LandEmulator, Setup  # noqa: E402

DATA = "/p/projects/open/Jamir/esm_land_emulator_data"
F2 = f"{DATA}/f2"
REL = f"{DATA}/release/fold_gfdl-esm4_v1"
LEG, RUN = "gfdl-esm4_ssp370_daily", 4
OUTV = ("gpp", "npp", "interc", "transp", "evap", "runoff", "swe", "soilw")


def main():
    cells = pl.read_parquet(f"{F2}/cells.parquet")
    pick = np.where(cells["biome"].to_numpy() != "")[0]
    emu = LandEmulator.load(REL)
    su = Setup.load(f"{REL}/setup_m{RUN}.npz")
    forc = np.load(f"{F2}/forc_m{RUN}_{LEG}.npy", mmap_mode="r")
    capy = np.load(f"{F2}/cap_m{RUN}_{LEG}.npy")
    st = emu.start(su)
    ny = 81
    out = {v: np.zeros((len(pick), ny * 365), np.float32) for v in OUTV}
    ann = {}
    for iy in range(ny):
        f = np.asarray(forc[:, 365 * (iy + 1): 365 * (iy + 2)], np.float32)
        d, an = emu.step_year(st, f, first_day=1 if iy == 0 else 0, cap=capy[:, iy])
        for v in OUTV:
            out[v][:, 365 * iy: 365 * (iy + 1)] = d[v][pick]
        for q, x in an.items():
            ann.setdefault(q, np.zeros((len(cells), ny)))[:, iy] = x
        print("year", 2020 + iy, flush=True)
    truth = {}
    for k in (4, 1):
        x = np.load(f"{F2}/daily_m{k}_{LEG}.npy", mmap_mode="r")
        truth[f"orig_m{k}"] = np.asarray(x[pick])
    prec = np.asarray(forc[pick, 365:, 1])
    np.savez_compressed(f"{DATA}/paper/daily_example.npz", cell=cells["Cell"].to_numpy()[pick],
                        biome=cells["biome"].to_numpy()[pick], prec=prec,
                        daily_vars=np.array(["prec", "transp", "evap", "interc", "runoff", "swe", "rootmoist",
                                             "pet", "npp", "gpp"]),
                        **{f"emu_{v}": a for v, a in out.items()}, **truth,
                        **{f"ann_{q}": a for q, a in ann.items()})
    print("=== DONE", flush=True)


if __name__ == "__main__":
    main()
