#!/usr/bin/env python3
"""run_emulator.py -- run a RELEASE of the learned emulator (scripts/build_emulator_release.py) year by year on the
panel cells from nothing but daily weather, time it on one core, and (fold release) check it reproduces the scored
predictions. ADR 0340.

  --release DIR --run k --leg <daily leg>   e.g. --run 4 --leg gfdl-esm4_ssp370_daily
  --check     fold release only: compare with the validated predictions of the same models and run --
              structure (xpanel/eval/yearly/preds_<g><sfx>.parquet), stand (xpanel/eval/stand/preds_<g><sfx>.parquet;
              <sfx> = release.json's pred_suffix, "_fx" since the leak fix) and the daily model's annual fluxes in
              the scored phase-B run (f2/runs/<CHECK_TAG>/annual.npz, default PD_B; leak-free: PD_B_fx).
              The scored runs read the climate statistics from the training table; the package computes them from
              the daily weather itself, so this check is also the one that closes ADR 0337 sec. 5's stated
              simplification.
Output: <release>/runs/<leg>_m<k>.npz (annual GPP/ET/NPP/runoff, structure and stand per cell-year) + timing.
Like the scored runs, the first day (Jan 1 2020) is the initial state and the top-metre capacity follows the
original's yearly value (--cap yearly, default); --cap fixed uses the setup's 2019 value (deployment).
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
sys.path.insert(0, os.path.join(REPO, "python", "src"))
from lpjmlfit_emulator.landemu import LandEmulator, Setup  # noqa: E402
from lpjmlfit_emulator.landemu.annual import STAND_Q, STRUCT_Q  # noqa: E402

F2 = "/p/projects/open/Jamir/esm_land_emulator_data/f2"
XP = "/p/projects/open/Jamir/esm_land_emulator_data/xpanel/eval"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def compare(name, got, ref):
    f = np.isfinite(got) & np.isfinite(ref)
    if not f.any():
        log(f"CHECK {name}: no comparable values")
        return False
    d = np.abs(got[f] - ref[f])
    scale = max(float(np.quantile(np.abs(ref[f]), 0.9)), 1e-12)
    med, mx = float(np.median(d)) / scale, float(d.max()) / scale
    p99 = float(np.quantile(d, 0.99)) / scale
    ok = med < 1e-3 and p99 < 0.05
    log(f"CHECK {name}: {int(f.sum())} values, |diff| / 90th-pct size: median {med:.1e}, 99th pct {p99:.1e}, "
        f"max {mx:.1e}, mean {got[f].mean():.4g} vs {ref[f].mean():.4g} -> {'OK' if ok else 'DIFFERS'}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", required=True)
    ap.add_argument("--run", type=int, default=4)
    ap.add_argument("--leg", default="gfdl-esm4_ssp370_daily")
    ap.add_argument("--years", type=int, default=81)
    ap.add_argument("--cap", choices=["yearly", "fixed"], default="yearly")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--check-tag", dest="check_tag", default="PD_B")
    a = ap.parse_args()

    emu = LandEmulator.load(a.release)
    su = Setup.load(os.path.join(a.release, f"setup_m{a.run}.npz"))
    tag = f"m{a.run}_{a.leg}"
    forc = np.load(os.path.join(F2, f"forc_{tag}.npy"), mmap_mode="r")  # (N, 365 + 81*365, 5); first year = warm-up
    capy = np.load(os.path.join(F2, f"cap_{tag}.npy"))  # index iy = year 2019 + iy
    cells = pl.read_parquet(os.path.join(F2, "cells.parquet"))["Cell"].cast(pl.Int32).to_numpy()
    assert np.array_equal(cells, su.cell), "setup and forcing cell order differ"
    n, ny = len(cells), a.years
    log(f"release {emu.cfg['version']} ({emu.cfg['kind']}, hold {emu.cfg['hold_gcm']}), run m{a.run}, {a.leg}, "
        f"{n} cells x {ny} years")

    st = emu.start(su)
    ann_f = np.zeros((n, ny, 4))  # gpp, et, npp, runoff
    S = {q: np.zeros((n, ny)) for q in STRUCT_Q + STAND_Q}
    wall0, cpu0 = time.perf_counter(), time.process_time()
    for iy in range(ny):
        f = np.asarray(forc[:, 365 * (iy + 1): 365 * (iy + 2)], np.float32)
        cap = capy[:, iy] if a.cap == "yearly" else None
        d, an = emu.step_year(st, f, first_day=1 if iy == 0 else 0, cap=cap)
        ann_f[:, iy] = np.stack([d["gpp"].sum(1), (d["interc"] + d["transp"] + d["evap"]).sum(1), d["npp"].sum(1),
                                 d["runoff"].sum(1)], 1)
        for q in S:
            S[q][:, iy] = an[q]
        if iy % 10 == 0:
            log(f"year {2020 + iy}: GPP {ann_f[:, iy, 0].mean():.0f} gC/m2, tree count/patch "
                f"{np.nanmean(an['n_per_patch']):.2f}, leaf area {np.nanmean(an['lai_stand']):.2f}, "
                f"stores W {st['daily'].W.mean():.0f} S {st['daily'].S.mean():.1f} D {st['daily'].D.mean():.0f} mm")
    cpu, wall = time.process_time() - cpu0, time.perf_counter() - wall0
    per = cpu / (n * ny)
    log(f"TIMED: {n * ny} cell-years, CPU {cpu:.1f} s, wall {wall:.1f} s (CPU/wall {cpu / wall:.2f}) -> "
        f"{per:.3e} core-s per cell-year; the original 0.267 at 25 patches ({0.267 / per:.0f}x), ~6.7 at 500 "
        f"({6.7 / per:.0f}x)")
    od = os.path.join(a.release, "runs")
    os.makedirs(od, exist_ok=True)
    np.savez(os.path.join(od, f"{a.leg}_m{a.run}_cap{a.cap}.npz"), cell=cells, ann=ann_f,
             core_s_per_cell_year=per, **{f"s_{q}": v for q, v in S.items()})

    if a.check:
        g = emu.cfg["hold_gcm"]
        assert g is not None, "--check needs a fold release"
        leg = a.leg.removesuffix("_daily")
        grid = pl.DataFrame({"Cell": np.repeat(cells, ny), "Year": np.tile(np.arange(2020, 2020 + ny), n)
                             .astype(np.int32)})
        ok = True
        sfx = emu.cfg.get("pred_suffix", "")  # "_fx" for releases built after the leak fix (ADR 0352 sec. 0)
        log(f"CHECK against the scored predictions preds_{g}{sfx}.parquet and the daily run {a.check_tag}")
        ssfx = emu.cfg.get("struct_pred_suffix", sfx)  # a departure release (ADR 0358): its own arm's file
        for kind, pf in (("structure", os.path.join(XP, "yearly", f"preds_{g}{ssfx}.parquet")),
                         ("stand", os.path.join(XP, "stand", f"preds_{g}{sfx}.parquet"))):
            P = pl.read_parquet(pf).filter((pl.col("member") == a.run) & (pl.col("leg") == leg)).with_columns(
                pl.col("Cell").cast(pl.Int32), pl.col("Year").cast(pl.Int32))
            P = grid.join(P, on=["Cell", "Year"], how="left")
            for q in (STRUCT_Q if kind == "structure" else STAND_Q):
                ok &= compare(f"{kind} {q}", S[q].reshape(-1), P[q].to_numpy().astype(float))
        npz = os.path.join(F2, "runs", a.check_tag, "annual.npz")
        if ny == 81 and os.path.exists(npz):
            ref = np.load(npz)[f"free__{a.leg}"][a.run - 1]
            for j, v in enumerate(("gpp", "et", "npp", "runoff")):
                x, r = ann_f[:, 1:, j].mean(1), ref[:, 1:, j].mean(1)
                m = np.abs(r) > 1.0
                rel = np.abs(x[m] / r[m] - 1)
                good = np.median(rel) < 1e-2
                ok &= bool(good)
                log(f"CHECK daily {v} (2021-2100 mean per cell vs {a.check_tag}): median |rel diff| "
                    f"{np.median(rel):.1e}, 90th pct {np.quantile(rel, 0.9):.1e}, total "
                    f"{x[m].sum() / r[m].sum() - 1:+.1e} -> {'OK' if good else 'DIFFERS'}")
        log(f"CHECKS: {'ALL OK' if ok else 'SOME DIFFER (see above)'}")
    log("=== DONE")


if __name__ == "__main__":
    main()
