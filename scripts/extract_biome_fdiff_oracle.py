#!/usr/bin/env python3
"""M3 F-side oracle — extract the C's per-cell TREE carbon/water/structure reference for the 5 biome cells.

WHY THIS SCRIPT EXISTS (the reference-basis problem it solves; `residual-diagnosis` §1).
`d_gpp` / `d_transp` / `a_lai_stand` are **grid-cell totals over ALL PFTs, grass included**, while the
coupled driver's `FDiffFastCore` is built from `M_individuals_<name>_2010.csv`, which keeps only
`type <= 6` — i.e. F_diff's canopy is **tree-only**. Comparing the two directly understates F_diff by the
grass share, and that share is NOT small: measured here it is **42.4 %** of GPP at boreal Siberia, 28.4 %
mediterranean, 19.3 % Sahel, 5.8 % Hainich, 0.2 % Amazon. That is the exact class of artifact that cost the
grass-overshoot saga ~10 sessions (CLAUDE.md §6.7), so it is removed by construction rather than caveated:

    gpp_tree = d_gpp - d_grass_gpp          # d_grass_gpp = the custom per-PFT daily grass GPP (conf.h id 419,
                                            # patches/lpjmlfit_daily_grass_gpp.patch) — NOT a stock output.

The runs this reads therefore have to be the `d_grass_gpp`-carrying ones (`scripts/run_fdiff_grass_gpp_cell.sh`,
~9 s/cell), not the `M_biome_val` set. Provisioning them for a new cell is one command:

    CELL=<orderA> RUNTAG=M_grass_val SUBMIT=yes bash scripts/run_fdiff_grass_gpp_cell.sh

WHAT IS AND IS NOT SPLITTABLE (do not "improve" this by adding a band sum — these were checked in the C source):
  * GPP  — SPLITTABLE, exactly, via `d_grass_gpp` (above).                                     => `gpp_tree`
  * FPC  — SPLITTABLE, per-PFT bands. `a_fpc_stand` band 0 is `natural stand fraction`, bands
           1..7 the seven tree PFTs (CLAUDE.md §3 `Type` order), bands 8..10 the three grasses.  => `fpc_tree`
  * transp — **NOT splittable.** There is no per-PFT daily transpiration output. Reported as the cell
           TOTAL; the grass share of GPP in the same row is the honest upper bound on its contamination.
  * LAI  — **NOT splittable on a stand basis.** `a_lai_stand` is one all-PFT band. The per-PFT daily
           `d_nv_lai` is NOT a substitute: `daily_natural.c:340` accumulates `actual_lai(pft)/npatch` and
           `actual_lai_tree` (`lai_tree.c:29`) is `leaf_c*sla/crownarea*phen` — the **within-crown**
           individual LAI, with no `nind` and no `crownarea` weighting, so summing its bands gives a sum of
           within-crown LAIs, not a ground-area stand LAI (the exact `LAI` vs stand-LAI trap in CLAUDE.md §3).
           Reported as the cell total, all-PFT, and flagged as such.

UNITS TRAP (`[VERIFIED 2026-07-30]`). The NetCDF `units` attribute on the daily files reads `gC/m2/month` /
`mm/month`, but the values ARE per-day: the writer keeps the monthly unit string when `"timestep":"daily"` is
set in the config. Confirmed by magnitude — Hainich GPP mean 3.27 => ~1195 gC/m2/yr (a correct temperate
forest); reading it as monthly would give 39 gC/m2/yr, which is absurd. Do not "fix" the values by /30.

Window is 2010-2019, matching the committed `biome_forcing_<name>.csv` the F-side probe replays.

REPRODUCIBILITY. The C is built with `-DPERMUTE` (daily Fisher-Yates PFT-depletion order on the cell's
RAND48 seed), so a re-run of the same cell is NOT bit-identical — the documented `whc_nat` spread between a
global run and a single-cell re-run is up to 1.6e-4 relative (CLAUDE.md §3, ADR 0050). The committed CSVs are
therefore a snapshot of *specific* runs, and `M_fdiff_oracle_meta.json` records each cell's run directory for
that reason. Expect small changes if the runs are regenerated; do not treat a 1e-4-level difference as a bug.

Run:  scripts/sbatch_python.sh M-oracle scripts/extract_biome_fdiff_oracle.py
      (cheap enough for a login-node check too: it reads ~5 small single-cell files)
"""
import json
import os

import netCDF4 as nc
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # never hard-code (CLAUDE.md §9.6)
REFDIR = os.path.join(REPO, "test", "testitems", "references")
RUN_ROOT = "/p/tmp/jamirp/esm_land_daily"
FIRSTYEAR, Y0, Y1 = 2000, 2010, 2019  # run start; the committed-forcing window
MONTH_LEN = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])  # noleap 365
N_TREE_BANDS = 7  # a_fpc_stand bands 1..7; band 0 = natural stand fraction, 8..10 = grass


def run_dir(cell):
    """The `d_grass_gpp`-carrying single-cell run for this cell (Hainich's predates the M_ tag)."""
    tag = "grassgpp" if cell == 42490 else "M_grass_val"
    return f"{RUN_ROOT}/daily_{FIRSTYEAR}_{Y1}_{tag}_c{cell}_seed1/output"


def read_cells():
    """(name, cell, lat) from the committed per-cell registry."""
    with open(os.path.join(REFDIR, "M_cells.csv")) as f:
        lines = [ln for ln in f if ln.strip() and not ln.startswith("#")]
    hdr = lines[0].strip().split(",")
    out = []
    for ln in lines[1:]:
        d = dict(zip(hdr, ln.strip().split(",")))
        out.append((d["name"], int(d["cell"]), float(d["lat"])))
    return out


def var(path, name=None):
    """The single data variable of a 1-cell NetCDF, as a plain float array."""
    d = nc.Dataset(path)
    if name is None:
        name = [k for k, v in d.variables.items() if v.ndim >= 3][0]
    return np.asarray(d[name][:], dtype=float)


def main():
    d0, d1 = (Y0 - FIRSTYEAR) * 365, (Y1 + 1 - FIRSTYEAR) * 365
    a0, a1 = Y0 - FIRSTYEAR, Y1 + 1 - FIRSTYEAR
    nyear = Y1 - Y0 + 1
    doy_month = np.repeat(np.arange(12), MONTH_LEN)
    day_month = np.tile(doy_month, nyear)  # month index 0..11 of every day in the window

    rows = []
    meta = {
        "window": f"{Y0}-{Y1}",
        "basis": {
            "gpp_tree": "d_gpp - d_grass_gpp, gC/m2/day (grass removed EXACTLY; conf.h id 419)",
            "transp_total": "d_transp, mm/day, cell total ALL PFTs — no per-PFT daily transp output exists",
            "et_total": "d_transp + d_evap + d_interc, mm/day — matches F's et = transp+evap+interc",
            "fpc_tree": "sum of a_fpc_stand bands 1..7 (the 7 tree PFTs)",
            "lai_stand_total": "a_lai_stand, all-PFT stand LAI — NOT tree-only (d_nv_lai is within-crown)",
        },
        "units_trap": "the NetCDF units attribute says /month; the DAILY files are per-day (see docstring)",
        "cells": {},
    }
    print("=== the C's per-cell TREE reference, monthly climatology %d-%d ===" % (Y0, Y1))
    print("   gpp_tree = d_gpp - d_grass_gpp (grass removed exactly). transp/LAI are cell totals.\n")

    for name, cell, _lat in read_cells():
        p = run_dir(cell)
        if not os.path.isdir(p):
            print(f"{name:<22} -- MISSING {p} (run scripts/run_fdiff_grass_gpp_cell.sh for this cell) --")
            continue
        gpp_tot = var(f"{p}/d_gpp.nc")[d0:d1, 0, 0]
        gpp_gr = var(f"{p}/d_grass_gpp.nc")[d0:d1, 0, 0]
        transp = var(f"{p}/d_transp.nc")[d0:d1, 0, 0]
        evap = var(f"{p}/d_evap.nc")[d0:d1, 0, 0]
        interc = var(f"{p}/d_interc.nc")[d0:d1, 0, 0]
        fpc = var(f"{p}/a_fpc_stand.nc")[a0:a1, :, 0, 0]
        lai = var(f"{p}/a_lai_stand.nc")[a0:a1, 0, 0]
        gpp_tree = gpp_tot - gpp_gr

        fpc_tree = fpc[:, 1 : 1 + N_TREE_BANDS].sum(axis=1)
        fpc_grass = fpc[:, 1 + N_TREE_BANDS :].sum(axis=1)
        gr_share = float(gpp_gr.mean() / gpp_tot.mean()) if gpp_tot.mean() > 0 else float("nan")
        meta["cells"][name] = {
            "cell": cell,
            "run": p,
            "gpp_grass_share": round(gr_share, 5),
            "gpp_tree_annual_gC_m2_yr": round(float(gpp_tree.mean() * 365), 2),
            "fpc_tree_mean": round(float(fpc_tree.mean()), 5),
            "fpc_grass_mean": round(float(fpc_grass.mean()), 5),
            "lai_stand_total_mean": round(float(lai.mean()), 5),
        }
        for m in range(12):
            sel = day_month == m
            rows.append(
                dict(
                    name=name,
                    cell=cell,
                    month=m + 1,
                    gpp_tree=gpp_tree[sel].mean(),
                    gpp_grass=gpp_gr[sel].mean(),
                    gpp_total=gpp_tot[sel].mean(),
                    transp_total=transp[sel].mean(),
                    evap=evap[sel].mean(),
                    interc=interc[sel].mean(),
                    et_total=(transp + evap + interc)[sel].mean(),
                    fpc_tree=fpc_tree.mean(),
                    fpc_grass=fpc_grass.mean(),
                    lai_stand_total=lai.mean(),
                )
            )
        print(
            f"{name:<22} grass {100 * gr_share:4.1f}% of GPP | tree GPP "
            f"{gpp_tree.mean():6.3f} gC/m2/d ({gpp_tree.mean() * 365:7.1f}/yr) | "
            f"transp {transp.mean():5.3f} mm/d | fpc_tree {fpc_tree.mean():5.3f} | "
            f"lai_stand {lai.mean():5.3f}"
        )

    # ── the ANNUAL series, so a level comparison can be YEAR-MATCHED ────────────────────────────────
    # The monthly climatology above is a 10-yr mean, and the emulator's canopy DRIFTS over those 10 yr
    # under `slow=nothing` (-13.5 % to +64.5 % FPC), so a 10-yr-mean ratio confounds F's flux physics with
    # F's structural drift. Comparing F's year k against the C's year k removes that confound.
    ann = []
    for name, cell, _lat in read_cells():
        p = run_dir(cell)
        if not os.path.isdir(p):
            continue
        gt = var(f"{p}/d_gpp.nc")[d0:d1, 0, 0] - var(f"{p}/d_grass_gpp.nc")[d0:d1, 0, 0]
        et = (
            var(f"{p}/d_transp.nc")[d0:d1, 0, 0]
            + var(f"{p}/d_evap.nc")[d0:d1, 0, 0]
            + var(f"{p}/d_interc.nc")[d0:d1, 0, 0]
        )
        fpc = var(f"{p}/a_fpc_stand.nc")[a0:a1, :, 0, 0]
        lai = var(f"{p}/a_lai_stand.nc")[a0:a1, 0, 0]
        for iy in range(nyear):
            sl = slice(iy * 365, (iy + 1) * 365)
            ann.append(
                dict(
                    name=name, cell=cell, year=Y0 + iy,
                    gpp_tree=gt[sl].mean(), et_total=et[sl].mean(),
                    fpc_tree=fpc[iy, 1 : 1 + N_TREE_BANDS].sum(),
                    lai_stand_total=lai[iy],
                )
            )
    acols = ["name", "cell", "year", "gpp_tree", "et_total", "fpc_tree", "lai_stand_total"]
    aout = os.path.join(REFDIR, "M_fdiff_oracle_biomes_annual.csv")
    with open(aout, "w") as f:
        f.write(
            "# Per-cell ANNUAL means of the same C reference (see M_fdiff_oracle_biomes.csv for the full\n"
            "# basis). Exists so an F-vs-C LEVEL comparison can be year-matched: the emulator's canopy\n"
            "# drifts over the window, so a 10-yr-mean ratio mixes flux physics with structural drift.\n"
        )
        f.write(",".join(acols) + "\n")
        for r in ann:
            f.write(
                ",".join(
                    str(r[c]) if c in ("name", "cell", "year") else f"{r[c]:.6f}" for c in acols
                )
                + "\n"
            )
    print(f"wrote {aout}  ({len(ann)} rows)")

    out = os.path.join(REFDIR, "M_fdiff_oracle_biomes.csv")
    cols = [
        "name", "cell", "month", "gpp_tree", "gpp_grass", "gpp_total",
        "transp_total", "evap", "interc", "et_total", "fpc_tree", "fpc_grass", "lai_stand_total",
    ]
    with open(out, "w") as f:
        f.write(
            f"# The C oracle's per-cell TREE reference, monthly climatology {Y0}-{Y1}, from the\n"
            f"# d_grass_gpp-carrying single-cell runs. gpp_* gC/m2/day, transp mm/day (DAILY despite the\n"
            f"# NetCDF '/month' units label). gpp_tree = gpp_total - gpp_grass (grass removed EXACTLY).\n"
            f"# transp_total and lai_stand_total are cell totals over ALL PFTs and are NOT splittable —\n"
            f"# use gpp_grass/gpp_total as the honest bound on their grass contamination.\n"
            f"# Emitted by scripts/extract_biome_fdiff_oracle.py — see that docstring for the full basis.\n"
        )
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(
                ",".join(
                    str(r[c]) if c in ("name", "cell", "month") else f"{r[c]:.6f}" for c in cols
                )
                + "\n"
            )
    with open(os.path.join(REFDIR, "M_fdiff_oracle_meta.json"), "w") as f:
        json.dump(meta, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"\nwrote {out}  ({len(rows)} rows) + M_fdiff_oracle_meta.json")


if __name__ == "__main__":
    main()
