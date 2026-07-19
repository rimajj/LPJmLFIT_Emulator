#!/usr/bin/env python3
# =============================================================================
# extract_fdiff_cell_multiyear.py — the committed REAL multi-year reference for
# the CELL × MULTI-YEAR NN-hook training objective (Phase-3 scale-up step
# 7b-cell-multiyear; ADR 0016; docs §18) on the Hainich prototype cell (global
# orderA grid index 42490).
#
# §16 (scale-up step 7b-cell) fit the learned Vcmax/λ correction so the CELL-mean
# DAILY GPP matched the C binary — but with the canopy STRUCTURE frozen at its 2010
# value. §17 (step 7b-multiyear) closed the outer loop on ONE patch: per-year annual
# GPP THROUGH the structure/allocation feedback, but against a DEMO target (2010
# repeated). This step composes the two: the CELL-mean PER-YEAR annual GPP vs the C's
# OWN per-year annual GPP, each patch grown across years. That needs a REAL multi-year
# reference — this script produces the committed, CI-runnable version of it from data
# already on disk (no C re-run):
#   * per-year daily FORCING + per-year daily C GPP/FAPAR — sliced from the full-period
#     daily CSV the single-cell C re-run already wrote
#     (run_fdiff_validation_cell.sh → extract_fdiff_validation_inputs.py →
#      <DATA>/fast_core_validation/hainich_c42490_daily_2000_2019.csv);
#   * the START-YEAR (2008) per-patch reconstructed individuals (incl. heartwood) —
#     copied from the multi-year structure reconstruction
#     (extract_fdiff_individuals_multiyear.py → <DATA>/fdiff_structure/).
#
# SPAN (start-of-year convention, matching the dynamic-structure validation §12): the
# rollout STARTS from year Y0-1's reconstructed structure and simulates the SUBSEQUENT
# SIM_YEARS, so the structure entering sim year Y is F_diff's own grown structure. Here
# start = 2008 reconstruction; SIM_YEARS = 2009, 2010, 2011 (each year's real forcing +
# C FAPAR phenology drive + C annual GPP target).
#
# Run (login node OK — pure file slicing):
#   /home/jamirp/.conda/envs/py311_new/bin/python scripts/extract_fdiff_cell_multiyear.py
# Writes (committed CI-runnable references):
#   test/testitems/references/hainich_individuals_2008.csv      (start-year 25-patch structure)
#   test/testitems/references/hainich_multiyear_forcing.csv     (per-year daily forcing)
#   test/testitems/references/hainich_multiyear_targets.csv     (per-year daily C GPP + FAPAR)
# =============================================================================
import os
import shutil

import numpy as np

CELL = 42490
START_YEAR = 2008                 # reconstructed structure the rollout starts from
SIM_YEARS = [2009, 2010, 2011]    # simulated years (real forcing/phenology/target per year)

DATA = "/p/tmp/jamirp/esm_land_emulator_data"
FULL_CSV = os.path.join(DATA, "fast_core_validation", "hainich_c42490_daily_2000_2019.csv")
STRUCT_DIR = os.path.join(DATA, "fdiff_structure")
REFDIR = os.path.join(os.path.dirname(__file__), "..", "test", "testitems", "references")


def main():
    os.makedirs(REFDIR, exist_ok=True)
    d = np.genfromtxt(FULL_CSV, delimiter=",", names=True)

    # ── per-year daily forcing (the columns the driver's DailyForcing needs) ──
    fcols = ["year", "doy", "temp", "swdown", "lwnet", "precip", "huss", "daylength", "co2"]
    tcols = ["year", "doy", "fapar_C", "gpp_C"]
    fmask = np.isin(d["year"], SIM_YEARS)
    order = np.lexsort((d["doy"][fmask], d["year"][fmask]))   # (year, doy) ascending

    fmat = np.column_stack([d[c][fmask][order] for c in ["year", "doy", "temp", "swdown", "lwnet",
                                                          "precip", "huss", "daylength", "co2"]])
    ann_gpp = {int(y): float(np.nansum(d["gpp_C"][d["year"] == y])) for y in SIM_YEARS}
    hdr_f = (f"# Hainich cell {CELL} REAL LPJmL-FIT .clm daily forcing, sim years "
             f"{SIM_YEARS} (start structure {START_YEAR}). Sliced from "
             f"hainich_c42490_daily_2000_2019.csv (extract_fdiff_validation_inputs.py). Units: temp degC, "
             f"swdown/lwnet W/m2, precip mm/day, huss kg/kg, daylength h, co2 ppm.\n" + ",".join(fcols))
    np.savetxt(os.path.join(REFDIR, "hainich_multiyear_forcing.csv"), fmat,
               delimiter=",", header=hdr_f, comments="", fmt="%.6g")

    tmat = np.column_stack([d[c][fmask][order] for c in ["year", "doy", "fapar_C", "gpp_C"]])
    ann_str = "; ".join(f"{y}: {ann_gpp[y]:.1f}" for y in SIM_YEARS)
    hdr_t = (f"# LPJmL-FIT C-binary daily GPP + FAPAR for cell {CELL}, sim years {SIM_YEARS} "
             f"(cell-mean over 25 patches). Per-year annual GPP (gC/m2/yr) = [{ann_str}]. "
             f"fapar = phen+structure-folded absorbed-PAR fraction; gpp gC/m2/day.\n" + ",".join(tcols))
    np.savetxt(os.path.join(REFDIR, "hainich_multiyear_targets.csv"), tmat,
               delimiter=",", header=hdr_t, comments="", fmt="%.6g")

    # ── start-year (2008) per-patch reconstructed individuals (incl. heartwood_c) ──
    src = os.path.join(STRUCT_DIR, f"hainich_individuals_{START_YEAR}.csv")
    dst = os.path.join(REFDIR, f"hainich_individuals_{START_YEAR}.csv")
    shutil.copyfile(src, dst)

    print(f"OK  cell={CELL}  start structure={START_YEAR}  sim years={SIM_YEARS}")
    print(f"  per-year C annual GPP (cell-mean): {ann_str}")
    print(f"  wrote {REFDIR}/hainich_multiyear_forcing.csv   ({fmat.shape[0]} daily rows)")
    print(f"  wrote {REFDIR}/hainich_multiyear_targets.csv   ({tmat.shape[0]} daily rows)")
    print(f"  copied {src}")
    print(f"      -> {dst}")


if __name__ == "__main__":
    main()
