#!/usr/bin/env python3
"""run_emulator_non.py -- run a NITROGEN-ON release (scripts/build_emulator_release_non.py, ADR 0344) year by year on
the 674 clustered cells from nothing but daily weather and the year's CO2, time it on one core, and check it
reproduces the scored pipeline.

  --release DIR --leg <gcm>_<ssp>[co2fix]   e.g. --leg mpi-esm1-2-hr_ssp370 (a held-out climate model)
  --cap yearly|fixed  top-metre capacity: the original's yearly value (as the scored runs; default) or the setup's
                      2019 value (deployment: the emulator has no soil-carbon model to update it)
  --check             compare with the pipeline's predictions of the same models: structure + stand vs
                      clu_non/maps/<maps_arm>/preds.parquet, and (fold release) the daily model's annual fluxes vs
                      the scored phase-B free run f2_non/runs/<--check-tag, default NC_B3>/annual.npz
  --check-ens NPZ     (ADR 0372) also compare the daily model's annual fluxes with an xtf_daily.py runens ensemble
                      run on the emulated stand (xtf/daily/ens/<arm>__stand_emul_main2/annual.npz, key free__m2__)
The forcing is read from the runs' own .clm files exactly as the training table's climate statistics were
(clu_emu_maps.read_forcing_year); the first day (Jan 1 2020) is the original's state, as in the scored runs.
Output: <release>/runs/<leg>_cap<cap>.npz (annual GPP / ET / NPP / runoff, structure and stand per cell-year).
"""

from __future__ import annotations

import os

for _v in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ[_v] = "1"

import argparse  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402
import polars as pl  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "python", "src"))
import clu_emu_maps as M  # noqa: E402
from lpjmlfit_emulator.landemu import LandEmulator, Setup  # noqa: E402
from lpjmlfit_emulator.landemu.annual import STAND_Q, STRUCT_Q  # noqa: E402
from run_emulator import compare  # noqa: E402

F2N = "/p/projects/open/Jamir/esm_land_emulator_data/f2_non"
RM, SWE = 6, 5


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", required=True)
    ap.add_argument("--leg", default="mpi-esm1-2-hr_ssp370")
    ap.add_argument("--years", type=int, default=81)
    ap.add_argument("--cap", choices=["yearly", "fixed"], default="yearly")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--check-tag", dest="check_tag", default="NC_B3")
    ap.add_argument("--check-ens", dest="check_ens", default="")
    a = ap.parse_args()

    emu = LandEmulator.load(a.release)
    su = Setup.load(os.path.join(a.release, "setup_s2.npz"))
    g, t = a.leg.split("_")
    files = M.forcing_files(f"{g}_{t.replace('co2fix', '')}")
    co2 = M.co2_series(t)
    tag = f"m2_{a.leg}"
    if os.path.exists(f"{F2N}/daily_{tag}.npy"):  # the leg's own Jan 1 2020 state (the setup holds one leg's)
        d0 = np.load(f"{F2N}/daily_{tag}.npy", mmap_mode="r")
        su.W0, su.S0 = np.array(d0[:, 0, RM], np.float64), np.array(d0[:, 0, SWE], np.float64)
    capy = np.load(f"{F2N}/cap_{tag}.npy") if a.cap == "yearly" else None  # index iy = year 2019 + iy
    cells = su.cell
    assert np.array_equal(cells, M.cells()["Cell"].to_numpy()), "setup and cell table order differ"
    n, ny = len(cells), a.years
    log(f"release {emu.cfg['version']} ({emu.cfg['kind']}), {a.leg}, {n} cells x {ny} years, CO2 "
        f"{co2[M.F0]:.0f} -> {co2[M.F0 + ny - 1]:.0f} ppm, capacity {a.cap}")

    st = emu.start(su)
    ann_f = np.zeros((n, ny, 4))  # gpp, et, npp, runoff
    S = {q: np.zeros((n, ny)) for q in STRUCT_Q + STAND_Q}
    cpu = wall = 0.0
    for iy in range(ny):
        y = M.F0 + iy
        T, P, Q, SW, LW = M.read_forcing_year(files, y)
        f = np.stack([T, P, SW, LW, Q], -1)  # the package's order: tas pr rsds lwnet huss
        w0, c0 = time.perf_counter(), time.process_time()
        d, an = emu.step_year(st, f, first_day=1 if iy == 0 else 0, cap=None if capy is None else capy[:, iy],
                              co2=co2[y])
        cpu, wall = cpu + time.process_time() - c0, wall + time.perf_counter() - w0
        ann_f[:, iy] = np.stack([d["gpp"].sum(1), (d["interc"] + d["transp"] + d["evap"]).sum(1), d["npp"].sum(1),
                                 d["runoff"].sum(1)], 1)
        for q in S:
            S[q][:, iy] = an[q]
        if iy % 10 == 0:
            log(f"year {y}: GPP {ann_f[:, iy, 0].mean():.0f} gC/m2, vegetation carbon {np.nanmean(an['vegc']):.0f} "
                f"gC/m2, leaf area {np.nanmean(an['lai_stand']):.2f}, stores W {st['daily'].W.mean():.0f} "
                f"S {st['daily'].S.mean():.1f} D {st['daily'].D.mean():.0f} mm")
    per = cpu / (n * ny)
    log(f"TIMED (excl. reading the forcing): {n * ny} cell-years, CPU {cpu:.1f} s, wall {wall:.1f} s -> "
        f"{per:.3e} core-s per cell-year")
    od = os.path.join(a.release, "runs")
    os.makedirs(od, exist_ok=True)
    np.savez(os.path.join(od, f"{a.leg}_cap{a.cap}.npz"), cell=cells, ann=ann_f, core_s_per_cell_year=per,
             **{f"s_{q}": v for q, v in S.items()})

    if a.check:
        ok = True
        pf = os.path.join(M.OUT, "maps", emu.cfg["maps_arm"], "preds.parquet")
        grid = pl.DataFrame({"Cell": np.repeat(cells, ny).astype(np.int32),
                             "Year": np.tile(np.arange(M.F0, M.F0 + ny), n).astype(np.int32)})
        P = grid.join(pl.read_parquet(pf).filter(pl.col("leg") == a.leg), on=["Cell", "Year"], how="left")
        worst = 0.0
        for q in STRUCT_Q + STAND_Q:
            got, ref = S[q].reshape(-1), P[q].to_numpy().astype(float)
            ok &= compare(f"map {q}", got, ref)
            both = np.isfinite(got) & np.isfinite(ref)
            worst = max(worst, float(np.abs(got[both] - ref[both]).max()))
            ok &= bool(np.array_equal(np.isfinite(got), np.isfinite(ref)))
        log(f"CHECK maps: largest |package - pipeline| over all 18 quantities {worst:.2e}")
        npz = os.path.join(F2N, "runs", a.check_tag, "annual.npz")
        if emu.cfg["kind"] == "fold" and a.cap == "yearly" and ny == 81 and os.path.exists(npz):
            z = np.load(npz)
            for j, v in enumerate(("gpp", "et", "npp", "runoff")):
                x, r = ann_f[:, 1:, j].mean(1), z[f"free__{a.leg}__{v}"][:, 1:].mean(1)
                m = np.abs(r) > 1.0
                rel = np.abs(x[m] / r[m] - 1)
                good = np.median(rel) < 1e-2
                ok &= bool(good)
                log(f"CHECK daily {v} (2021-2100 mean per cell vs {a.check_tag}): median |rel diff| "
                    f"{np.median(rel):.1e}, 90th pct {np.quantile(rel, 0.9):.1e}, total "
                    f"{x[m].sum() / r[m].sum() - 1:+.1e} -> {'OK' if good else 'DIFFERS'}")
        if a.check_ens and a.cap == "yearly" and ny == 81:
            z = np.load(a.check_ens)
            for j, v in enumerate(("gpp", "et", "npp", "runoff")):
                x, r = ann_f[:, 1:, j].mean(1), z[f"free__m2__{a.leg}__{v}"][:, 1:].mean(1)
                m = np.abs(r) > 1.0
                rel = np.abs(x[m] / r[m] - 1)
                good = np.median(rel) < 1e-2
                ok &= bool(good)
                log(f"CHECK daily {v} (2021-2100 mean per cell vs the scored ensemble run): median |rel diff| "
                    f"{np.median(rel):.1e}, 90th pct {np.quantile(rel, 0.9):.1e}, total "
                    f"{x[m].sum() / r[m].sum() - 1:+.1e} -> {'OK' if good else 'DIFFERS'}")
        log(f"CHECKS: {'ALL OK' if ok else 'SOME DIFFER (see above)'}")
    log("=== DONE")


if __name__ == "__main__":
    main()
