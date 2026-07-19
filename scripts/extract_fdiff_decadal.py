#!/usr/bin/env python3
# =============================================================================
# extract_fdiff_decadal.py — the committed REAL DECADAL (11-year) multi-year
# reference for validating F_diff's coupled multi-year canopy rollout beyond the
# 3-year span of extract_fdiff_cell_multiyear.py (Phase-3 scale-up step 10; docs §21).
#
# Same construction as extract_fdiff_cell_multiyear.py (§18) — no C re-run, all
# sliced from data already on disk — but over sim years 2009..2019 (11 years):
#   * the START-YEAR (2008) per-patch reconstructed 25-patch structure the rollout
#     grows forward (copied from extract_fdiff_individuals_multiyear.py output);
#   * per-year daily FORCING + per-year daily C GPP/FAPAR sliced from the full-period
#     single-cell daily CSV the C re-run already wrote (hainich_c42490_daily_2000_2019.csv).
#
# The rollout STARTS from the 2008 reconstructed structure and simulates 2009..2019
# self-driven (each patch grown across years by the pipe-model allocation), so the
# structure entering each sim year is F_diff's OWN grown structure (start-of-year
# convention, §12/§18); the C per-year annual GPP is the target for that self-driven
# growth. This is the decadal fidelity-horizon test: does the coupled rollout stay
# faithful to the C over a decade (not just 3 years)?
#
# Usage:
#   /home/jamirp/.conda/envs/py311_new/bin/python scripts/extract_fdiff_decadal.py
# Writes (committed, CI-runnable — no /p/tmp dependency at test time):
#   test/testitems/references/hainich_decadal_forcing.csv   (per-year daily forcing)
#   test/testitems/references/hainich_decadal_targets.csv    (per-year daily C GPP + FAPAR)
#   (reuses the already-committed hainich_individuals_2008.csv start structure.)
# =============================================================================
import os
import numpy as np

CELL = 42490
START_YEAR = 2008
SIM_YEARS = list(range(2009, 2020))          # 2009..2019 (11 sim years)

DATA = "/p/tmp/jamirp/esm_land_emulator_data"
FULL_CSV = os.path.join(DATA, "fast_core_validation", "hainich_c42490_daily_2000_2019.csv")
REFDIR = os.path.join(os.path.dirname(__file__), "..", "test", "testitems", "references")


def main():
    d = np.genfromtxt(FULL_CSV, delimiter=",", names=True)
    fmask = np.isin(d["year"], SIM_YEARS)
    order = np.lexsort((d["doy"][fmask], d["year"][fmask]))   # (year, doy) ascending

    fcols = ["year", "doy", "temp", "swdown", "lwnet", "precip", "huss", "daylength", "co2"]
    fmat = np.column_stack([d[c][fmask][order] for c in fcols])
    ann_gpp = {int(y): float(np.nansum(d["gpp_C"][d["year"] == y])) for y in SIM_YEARS}
    ann_str = "; ".join(f"{y}: {ann_gpp[y]:.1f}" for y in SIM_YEARS)
    hdr_f = (f"# Hainich cell {CELL} REAL LPJmL-FIT daily forcing, DECADAL sim years "
             f"{SIM_YEARS[0]}-{SIM_YEARS[-1]} (start structure {START_YEAR}). Sliced from "
             f"hainich_c42490_daily_2000_2019.csv. Units: temp degC, swdown/lwnet W/m2, "
             f"precip mm/day, huss kg/kg, daylength h, co2 ppm.\n" + ",".join(fcols))
    np.savetxt(os.path.join(REFDIR, "hainich_decadal_forcing.csv"), fmat,
               delimiter=",", header=hdr_f, comments="", fmt="%.6g")

    tcols = ["year", "doy", "fapar_C", "gpp_C"]
    tmat = np.column_stack([d[c][fmask][order] for c in tcols])
    hdr_t = (f"# LPJmL-FIT C-binary daily GPP + FAPAR for cell {CELL}, DECADAL sim years "
             f"{SIM_YEARS[0]}-{SIM_YEARS[-1]} (cell-mean over 25 patches). Per-year annual GPP "
             f"(gC/m2/yr) = [{ann_str}]. fapar = phen+structure-folded absorbed-PAR fraction; "
             f"gpp gC/m2/day.\n" + ",".join(tcols))
    np.savetxt(os.path.join(REFDIR, "hainich_decadal_targets.csv"), tmat,
               delimiter=",", header=hdr_t, comments="", fmt="%.6g")

    print(f"OK  cell={CELL}  start structure={START_YEAR}  decadal sim years={SIM_YEARS[0]}-{SIM_YEARS[-1]}")
    print(f"  per-year C annual GPP (cell-mean): {ann_str}")
    print(f"  wrote {REFDIR}/hainich_decadal_forcing.csv   ({fmat.shape[0]} daily rows)")
    print(f"  wrote {REFDIR}/hainich_decadal_targets.csv   ({tmat.shape[0]} daily rows)")
    print(f"  (reuses committed hainich_individuals_{START_YEAR}.csv start structure)")


if __name__ == "__main__":
    main()
