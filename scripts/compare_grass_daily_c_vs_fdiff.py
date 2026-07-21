#!/usr/bin/env python
# =============================================================================
# compare_grass_daily_c_vs_fdiff.py — SEASON vs AMPLITUDE decomposition of the grass-NPP LEVEL gap,
# using the C binary's NEW daily grass GPP/NPP outputs (built this session: conf.h D_GRASS_GPP/NPP)
# overlaid on F_diff's cell-mean daily grass NPP curve.
#
# Reads the single-cell C daily NetCDF (d_grass_gpp.nc, d_grass_npp.nc, d_gpp.nc) from the grass-gpp
# re-run, slices per-year 365-day curves, and compares the target year's C daily grass NPP to F_diff's
# curve (logs/fdiff_grass_daily_npp_<year>.csv). Answers: is F_diff's grass leaf-on/active FEWER days
# (season) or LOWER on the days it is active (amplitude / GPP-per-day)?
#
#   run: /home/jamirp/.conda/envs/py311_new/bin/python scripts/compare_grass_daily_c_vs_fdiff.py
# =============================================================================
import os
import numpy as np

LOGS = os.path.join(os.path.dirname(__file__), "..", "logs")
REFDIR = os.path.join(os.path.dirname(__file__), "..", "test", "testitems", "references")
REF = os.path.join(REFDIR, "hainich_grass_daily_2009_2019.csv")
# F_diff curves for the decadal forcing years (2009..2019)
FDIFF_YEARS = list(range(2009, 2020))

# committed C daily grass reference (year, day, c_grass_gpp, c_grass_npp, c_cell_gpp)
# file = two '#' comment lines + a 'year,day,...' header + data (skiprows counts comment lines)
_REF = np.loadtxt(REF, delimiter=",", comments="#", skiprows=3)
_YEARS = _REF[:, 0].astype(int)
FIRSTYEAR = int(_YEARS.min())


def c_year(col, year):
    """Return the C daily series (col: 2=grass_gpp,3=grass_npp,4=cell_gpp) for a year."""
    m = _YEARS == year
    return _REF[m, col]


def year_slice(series, year, days_per_year=365):
    """Slice a full-series numpy array to one year (F_diff curves are already per-year)."""
    i0 = (year - FIRSTYEAR) * days_per_year
    return series[i0:i0 + days_per_year]


def summarize(curve, thr=1e-4):
    curve = np.asarray(curve, float)
    ann = float(np.nansum(curve))
    act = float(np.mean(curve > thr))
    on = curve[curve > thr]
    mean_on = float(np.mean(on)) if on.size else 0.0
    peak = float(np.nanmax(curve)) if curve.size else 0.0
    return dict(annual=ann, active_frac=act, mean_on_active=mean_on, peak=peak, n_active=int((curve > thr).sum()))


def main():
    years = sorted(set(_YEARS.tolist()))
    print(f"C daily grass reference: {REF} ({len(years)} years {years[0]}-{years[-1]})")

    # whole-series sanity: grass fraction of total GPP
    gall = np.concatenate([c_year(2, y) for y in years])
    tall = np.concatenate([c_year(4, y) for y in years])
    print(f"C grass GPP / C total GPP (all years) = {np.nansum(gall)/max(np.nansum(tall),1e-9):.3f}  (grass is a minority of cell GPP)")

    print("\n=== per-year C grass GPP/NPP (season + amplitude structure) ===")
    print(f"{'year':6}{'gGPP':>9}{'gNPP':>9}{'CUE':>7}{'act':>7}{'meanON':>9}{'peak':>8}")
    for y in years:
        cg = summarize(c_year(2, y)); cn = summarize(c_year(3, y))
        cue = cn['annual'] / cg['annual'] if cg['annual'] > 1e-9 else float('nan')
        print(f"{y:<6}{cg['annual']:>9.1f}{cn['annual']:>9.1f}{cue:>7.2f}{cn['active_frac']:>7.2f}{cn['mean_on_active']:>9.3f}{cn['peak']:>8.2f}")

    print("\n=== SEASON vs AMPLITUDE: C vs F_diff daily grass NPP, per available year ===")
    print(f"{'year':6}{'C_ann':>8}{'F_ann':>8}{'F/C':>6}{'C_act':>7}{'F_act':>7}{'actR':>6}{'C_onA':>8}{'F_onA':>8}{'ampR':>6}{'corr':>6}")
    fcs, ccs = [], []
    for y in FDIFF_YEARS:
        fcsv = os.path.join(LOGS, f"fdiff_grass_daily_npp_{y}.csv")
        if not os.path.exists(fcsv):
            print(f"{y:<6}  (no F_diff curve {os.path.basename(fcsv)})")
            continue
        # file = one '#' comment line + a 'day,fdiff_cell_grass_npp' header + data rows
        fd = np.loadtxt(fcsv, delimiter=",", comments="#", skiprows=2, usecols=1)
        cn = c_year(3, y)
        n = min(len(cn), len(fd))
        cn, fd = cn[:n], fd[:n]
        cs, fs = summarize(cn), summarize(fd)
        actR = fs['active_frac'] / cs['active_frac'] if cs['active_frac'] > 1e-9 else float('nan')
        ampR = fs['mean_on_active'] / cs['mean_on_active'] if cs['mean_on_active'] > 1e-9 else float('nan')
        fc = fs['annual'] / cs['annual'] if cs['annual'] > 1e-9 else float('nan')
        if np.std(cn) > 1e-9 and np.std(fd) > 1e-9:
            corr = float(np.corrcoef(cn, fd)[0, 1])
        else:
            corr = float('nan')
        print(f"{y:<6}{cs['annual']:>8.1f}{fs['annual']:>8.1f}{fc:>6.2f}{cs['active_frac']:>7.2f}{fs['active_frac']:>7.2f}{actR:>6.2f}{cs['mean_on_active']:>8.3f}{fs['mean_on_active']:>8.3f}{ampR:>6.2f}{corr:>6.2f}")
        fcs.append(fs['annual']); ccs.append(cs['annual'])

    if ccs:
        fcs, ccs = np.array(fcs), np.array(ccs)
        print(f"\nAGGREGATE over {len(ccs)} years: SUM_F/SUM_C = {fcs.sum()/ccs.sum():.3f}  |  mean per-year F/C = {np.mean(fcs/ccs):.3f}  (range {np.min(fcs/ccs):.2f}-{np.max(fcs/ccs):.2f})")

    print("\nINTERPRETATION:")
    print("  actR = F_diff active-day fraction / C's  (≈1 → season length faithful; <1 → F_diff season too short)")
    print("  ampR = F_diff mean NPP on active days / C's (≈1 → per-day amplitude faithful; <1 → GPP/day-per-leaf gap)")
    print("  F/C ≈ actR × ampR — whichever is further below 1 is the DOMINANT lever.")
    print("DONE.")


if __name__ == "__main__":
    main()
