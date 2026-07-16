#!/usr/bin/env python
"""Extract the F_diff <-> LPJmL-FIT C-binary validation inputs for the prototype cell.

Reads, for the Hainich beech prototype (GLOBAL orderA grid 0-based index 42490, lat 51.25/lon 10.25):
  * the REAL daily atmospheric forcing the C binary consumed, from the LPJmL `.clm` inputs
    (temperature/precipitation/short_wave/long_wave/humidity), read with the byte layout decoded and
    VALIDATED against the model's own `d_prec` output (precip is passed through unchanged);
  * annual CO2 (constant driver);
  * `petpar2` daylength reproduced from latitude + day-of-year (the C radiation routine), so F_diff
    is driven with the SAME daylength the C core used;
  * the C binary's daily VALIDATION TARGETS + light/structure boundary from the single-cell re-run
    (run_fdiff_validation_cell.sh): gpp, npp, transp, evap, interc, pet, runoff, prec, FAPAR (the
    phenology+structure-folded absorbed-PAR fraction — the key boundary), NV_LAI, rootmoist, swe;
  * annual canopy structure (fpc_stand, lai_stand) and the root-zone water-holding capacity (mm).

Writes:
  * <DATA>/fast_core_validation/hainich_c42490_daily_2000_2019.csv  (full period; driver + report)
  * test/testitems/references/hainich_forcing_<REFYEAR>.csv           (committed CI gate input)
  * test/testitems/references/hainich_cbinary_targets_<REFYEAR>.csv   (committed CI gate target)
  * <DATA>/fast_core_validation/hainich_c42490_meta.json             (cell, whc_mm, per-year structure)

.clm format (verified this session): LPJCLIM v3, order=1 (YEARCELL: data[year][cell][band]),
firstyear 1901, nyear 119, ncell 67420, nbands 365 (daily, noleap), datatype float32, scalar 1.0.
Header = 7-char name + int32 version + 10x int/float fields = 51 bytes.

Env: /home/jamirp/.conda/envs/py311_new/bin/python  (xarray, numpy).
"""
import json
import os
import struct
import numpy as np
import xarray as xr

# ---- fixed paths (mirror config/paths.yaml) ---------------------------------
GLOBAL = "/p/projects/waldspektrum/priesner/clustering/global"
RUN = "/p/tmp/jamirp/esm_land_daily/daily_2000_2019_fdiff_val_c42490_seed1/output"
CO2_FILE = "/p/projects/lpjml/inputs/co2/global/TRENDY/v12/global_co2_ann_1700_2022.txt"
REPO = "/p/projects/open/Jamir/esm_land_emulator"
DATA_OUT = "/p/tmp/jamirp/esm_land_emulator_data/fast_core_validation"
REF_OUT = os.path.join(REPO, "test/testitems/references")

CELL = 42490          # Hainich, GLOBAL orderA grid, 0-based
LAT = 51.25
LON = 10.25
FIRSTYEAR_RUN = 2000
LASTYEAR_RUN = 2019
REFYEAR = 2010        # committed reference year (representative: GPP 1132 vs 20-yr mean 1175)

# .clm header constants (verified)
HDR = 51
CLM_NYEAR = 119
CLM_FIRSTYEAR = 1901
NBANDS = 365
NCELL = 67420
NDAYYEAR = 365


def read_clm_year(path, cell, year, nbands=NBANDS):
    """One cell-year of a daily .clm (YEARCELL order, float32, scalar 1.0)."""
    y = year - CLM_FIRSTYEAR
    off = HDR + ((y * NCELL + cell) * nbands) * 4
    with open(path, "rb") as f:
        f.seek(off)
        buf = f.read(nbands * 4)
    return np.frombuffer(buf, dtype="<f4").astype(np.float64)


def daylength_petpar2(lat, day):
    """petpar2.c daylength (h): delta from day-of-year, hour angle from latitude."""
    delta = np.deg2rad(-23.4 * np.cos(2 * np.pi * (day + 10.0) / NDAYYEAR))
    u = np.sin(np.deg2rad(lat)) * np.sin(delta)
    v = np.cos(np.deg2rad(lat)) * np.cos(delta)
    if u >= v:
        return 24.0
    if u <= -v:
        return 0.0
    return 24.0 * np.arccos(-u / v) / np.pi


def read_co2(path):
    """Annual CO2 (ppm) keyed by year. File is 'year co2' or bare-value-per-year-from-1700."""
    years, vals = [], []
    with open(path) as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            parts = ln.split()
            if len(parts) >= 2:
                years.append(int(float(parts[0])))
                vals.append(float(parts[1]))
            else:
                vals.append(float(parts[0]))
    if years:
        return dict(zip(years, vals))
    return {1700 + i: v for i, v in enumerate(vals)}


def nc_cell(nc, varhint=None):
    """Open a single-cell daily NetCDF; return (var array [time, ...], varname), fills->NaN."""
    d = xr.open_dataset(os.path.join(RUN, nc), decode_times=False, mask_and_scale=True)
    dv = [v for v in d.data_vars if v not in ("time_bnds", "lat_bnds", "lon_bnds", "NamePFT")]
    name = varhint if (varhint and varhint in dv) else dv[0]
    a = np.asarray(d[name].isel(lat=0, lon=0))
    a = np.where(a < -1e30, np.nan, a)   # LPJmL missing value -1e32
    return a, name


def main():
    os.makedirs(DATA_OUT, exist_ok=True)
    years = list(range(FIRSTYEAR_RUN, LASTYEAR_RUN + 1))
    nyr = len(years)
    ndays = nyr * NDAYYEAR

    co2 = read_co2(CO2_FILE)

    # ---- forcing from .clm (YEARCELL) ----
    forc = {k: np.zeros(ndays) for k in ("temp", "swdown", "lwnet", "precip", "huss")}
    clm = {
        "temp": "temperature_test.clm", "swdown": "short_wave_radiation_test.clm",
        "lwnet": "long_wave_radiation_test.clm", "precip": "precipitation_test.clm",
        "huss": "humid_test.clm",
    }
    for k, fn in clm.items():
        for iy, yr in enumerate(years):
            forc[k][iy * NDAYYEAR:(iy + 1) * NDAYYEAR] = read_clm_year(os.path.join(GLOBAL, fn), CELL, yr)

    daylen = np.array([daylength_petpar2(LAT, d) for d in range(1, NDAYYEAR + 1)])
    daylen_full = np.tile(daylen, nyr)
    co2_full = np.concatenate([np.full(NDAYYEAR, co2[yr]) for yr in years])
    doy_full = np.tile(np.arange(1, NDAYYEAR + 1), nyr)
    year_full = np.repeat(years, NDAYYEAR)

    # ---- C-binary daily targets + light/structure ----
    tgt = {}
    for nc, key, hint in [
        ("d_gpp.nc", "gpp", "GPP"), ("d_npp.nc", "npp", "NPP"), ("d_transp.nc", "transp", "transp"),
        ("d_evap.nc", "evap", "evap"), ("d_interc.nc", "interc", "interc"), ("d_pet.nc", "pet", "PET"),
        ("d_runoff.nc", "runoff", "runoff"), ("d_prec.nc", "prec", "prec"),
        ("d_fapar.nc", "fapar", "FPAR"), ("d_rootmoist.nc", "rootmoist", "rootmoist"),
        ("d_swe.nc", "swe", "swe"),
    ]:
        a, _ = nc_cell(nc, hint)
        tgt[key] = a[:ndays]
    # nv_lai: sum the actual (phen-folded) LAI over natural-PFT bands
    lai, _ = nc_cell("d_nv_lai.nc", "LAI")          # (time, npft)
    tgt["nvlai"] = np.nansum(lai[:ndays], axis=1)

    # ---- self-check: the .clm precip we read must equal the model's d_prec output ----
    dprec_err = float(np.nanmax(np.abs(forc["precip"] - tgt["prec"])))
    assert dprec_err < 1e-3, f".clm precip reader disagrees with d_prec by {dprec_err} (layout/scalar bug)"

    # ---- root-zone water-holding capacity (mm): rootmoist saturates to field-cap minus wilting ----
    whc_mm = float(np.nanmax(tgt["rootmoist"]))

    # ---- annual structure (fpc_stand, lai_stand) ----
    def annual_var(nc, hint):
        d = xr.open_dataset(os.path.join(RUN, nc), decode_times=False, mask_and_scale=True)
        dv = [v for v in d.data_vars if v not in ("time_bnds", "lat_bnds", "lon_bnds", "NamePFT")]
        name = hint if hint in dv else dv[0]
        a = np.asarray(d[name].isel(lat=0, lon=0))
        a = np.where(a < -1e30, np.nan, a)
        if a.ndim > 1:
            a = np.nansum(a, axis=1)     # sum over PFT bands
        return a
    fpc_stand = annual_var("a_fpc_stand.nc", "FPC")
    lai_stand = annual_var("a_lai_stand.nc", "LAI")

    # ---- write the full-period daily CSV ----
    cols = ["year", "doy", "temp", "swdown", "lwnet", "precip", "huss", "daylength", "co2",
            "fapar_C", "nvlai_C", "gpp_C", "npp_C", "transp_C", "evap_C", "interc_C",
            "pet_C", "runoff_C", "rootmoist_C", "swe_C"]
    mat = np.column_stack([
        year_full, doy_full, forc["temp"], forc["swdown"], forc["lwnet"], forc["precip"],
        forc["huss"], daylen_full, co2_full, tgt["fapar"], tgt["nvlai"], tgt["gpp"], tgt["npp"],
        tgt["transp"], tgt["evap"], tgt["interc"], tgt["pet"], tgt["runoff"], tgt["rootmoist"], tgt["swe"],
    ])
    full_csv = os.path.join(DATA_OUT, "hainich_c42490_daily_2000_2019.csv")
    np.savetxt(full_csv, mat, delimiter=",", header=",".join(cols), comments="", fmt="%.6g")

    # ---- committed one-year reference (CI gate): forcing + targets ----
    os.makedirs(REF_OUT, exist_ok=True)
    m = year_full == REFYEAR
    fcols = ["doy", "temp", "swdown", "lwnet", "precip", "huss", "daylength", "co2"]
    fmat = np.column_stack([doy_full[m], forc["temp"][m], forc["swdown"][m], forc["lwnet"][m],
                            forc["precip"][m], forc["huss"][m], daylen_full[m], co2_full[m]])
    hdr_f = (f"# Hainich (DE-Hai) prototype cell {CELL}, lat {LAT}, lon {LON}, year {REFYEAR}. "
             f"REAL LPJmL-FIT .clm daily forcing (YEARCELL-decoded, precip validated vs d_prec) + "
             f"petpar2 daylength. Units: temp degC, swdown/lwnet W/m2, precip mm/day, huss kg/kg, "
             f"daylength h, co2 ppm.\n" + ",".join(fcols))
    np.savetxt(os.path.join(REF_OUT, f"hainich_forcing_{REFYEAR}.csv"), fmat,
               delimiter=",", header=hdr_f, comments="", fmt="%.6g")

    tcols = ["doy", "fapar_C", "gpp_C", "npp_C", "transp_C", "evap_C", "interc_C", "pet_C", "rootmoist_C"]
    tmat = np.column_stack([doy_full[m], tgt["fapar"][m], tgt["gpp"][m], tgt["npp"][m], tgt["transp"][m],
                            tgt["evap"][m], tgt["interc"][m], tgt["pet"][m], tgt["rootmoist"][m]])
    hdr_t = (f"# LPJmL-FIT C-binary daily outputs for cell {CELL}, year {REFYEAR} "
             f"(run_fdiff_validation_cell.sh). fapar = phen+structure-folded absorbed-PAR fraction; "
             f"gpp/npp gC/m2/day; transp/evap/interc/pet mm/day; rootmoist mm (top 1m).\n" + ",".join(tcols))
    np.savetxt(os.path.join(REF_OUT, f"hainich_cbinary_targets_{REFYEAR}.csv"), tmat,
               delimiter=",", header=hdr_t, comments="", fmt="%.6g")

    # ---- meta ----
    meta = {
        "cell": CELL, "lat": LAT, "lon": LON, "firstyear": FIRSTYEAR_RUN, "lastyear": LASTYEAR_RUN,
        "refyear": REFYEAR, "whc_mm": whc_mm, "alphaa": 0.55, "sla": 0.01986, "k_beer": 0.59,
        "albedo": 0.15, "clm_layout": "YEARCELL", "clm_precip_vs_dprec_maxabs": dprec_err,
        "fpc_stand_by_year": {int(y): float(fpc_stand[i]) for i, y in enumerate(years) if i < len(fpc_stand)},
        "lai_stand_by_year": {int(y): float(lai_stand[i]) for i, y in enumerate(years) if i < len(lai_stand)},
        "annual_gpp_C": {int(y): float(np.nansum(tgt["gpp"][year_full == y])) for y in years},
        "annual_transp_C": {int(y): float(np.nansum(tgt["transp"][year_full == y])) for y in years},
        "full_csv": full_csv,
    }
    with open(os.path.join(DATA_OUT, "hainich_c42490_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print(f"OK  cell={CELL} lat={LAT} lon={LON}")
    print(f"  .clm precip vs d_prec  max|diff| = {dprec_err:.3e} (0 == reader validated)")
    print(f"  whc_mm (rootmoist max) = {whc_mm:.2f}")
    print(f"  forcing 2000 mean temp = {forc['temp'][:365].mean():.2f} degC  precip = {forc['precip'][:365].sum():.1f} mm")
    print(f"  daylength range        = {daylen.min():.2f}..{daylen.max():.2f} h")
    print(f"  {REFYEAR}: fpc_stand={fpc_stand[years.index(REFYEAR)]:.3f} lai_stand={lai_stand[years.index(REFYEAR)]:.3f} "
          f"annual GPP_C={meta['annual_gpp_C'][REFYEAR]:.1f} transp_C={meta['annual_transp_C'][REFYEAR]:.1f}")
    print(f"  wrote: {full_csv}")
    print(f"         {REF_OUT}/hainich_forcing_{REFYEAR}.csv")
    print(f"         {REF_OUT}/hainich_cbinary_targets_{REFYEAR}.csv")


if __name__ == "__main__":
    main()
