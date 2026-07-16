#!/usr/bin/env python
"""
Phase-1 (P3b) WATER-CLOSURE check on a daily-output re-run (subset OR full global).

Evidence tiers (see JOURNAL / docs/phase1_p3b_water_closure.md):
  (1) DEFINITIVE — LPJmL's own per-cell/year water balance (check_fluxes.c, active
      under -DSAFE) enforces |balanceW| <= 1.5 mm/yr and ABORTS otherwise. A clean
      run over all cells x years IS the closure proof (confirm via the .out/.err logs).
  (2) OUTPUT FLUX BALANCE (needs no storage reconstruction) — per cell:
        R := prec - (transp + evap + interc + runoff)     [mm/yr]  = dStorage + excess_water
      Over the full run the net storage drift is bounded, so Sum(prec) ~ Sum(ET+runoff):
      report the per-cell fractional imbalance. Also split R against observed d(SWE).
  (3) SELF-CONSISTENCY — daily fluxes >= 0; swc fractional in [0,1]; snow builds/melts
      (d(SWE) over a full year ~ 0); daily sums reproduce the annual globalflux aggregate.

Memory-safe: opens every daily NetCDF as a dask-chunked (lazy) array and reduces to
per-cell annual sums without materializing the full [time,lat,lon] cube. The 23-layer
daily `swc` (~135 GB at global scale) is only SAMPLED for its [0,1] sanity, never fully
loaded. NB: `swc` is FRACTIONAL saturation (=water/wsats); absolute soil water in mm needs
the per-layer wsats, which LPJmL does NOT expose -> the soil part of dStorage is inferred
as (R - d(SWE)), not independently reconstructed. See the report for the F-core implication.

Usage:  python scripts/water_closure_check.py <run_dir>
"""
import json
import sys
import numpy as np
import xarray as xr

R_EARTH = 6_371_000.0
DEG = np.pi / 180.0
DLL = 0.5  # grid resolution (deg)


def open_var(path, chunks={"time": 365}):
    ds = xr.open_dataset(path, decode_times=False, chunks=chunks)
    cands = [n for n, v in ds.data_vars.items()
             if "time" in v.dims and "lat" in v.dims and not n.endswith("_bnds")]
    da = ds[cands[0]]
    fill = da.attrs.get("_FillValue", da.attrs.get("missing_value", -1e32))
    return da.where(da > fill / 2), ds  # mask fills -> NaN (lazy)


def cell_area_m2(lat_deg):
    phi = lat_deg * DEG
    dlat = DLL * DEG
    return R_EARTH**2 * (DLL * DEG) * (np.sin(phi + dlat / 2) - np.sin(phi - dlat / 2))


def main(run_dir):
    out = f"{run_dir}/output"
    prec_da, dsp = open_var(f"{out}/d_prec.nc")
    lat = dsp["lat"].values
    lon = dsp["lon"].values
    tvals = dsp["time"].values.astype(int)  # days since firstyear-1-1, noleap
    years = np.unique(tvals // 365)
    yr0 = int(round(tvals.min() / 365))  # firstyear offset is 0
    firstyear = 2000  # base year in these files
    valid = prec_da.isel(time=0).notnull().values  # [lat, lon]; fill is constant in time
    ncell = int(valid.sum())
    report = {"run_dir": run_dir, "n_cells": ncell,
              "years": [int(firstyear + y) for y in years]}

    def annual_per_cell(da):
        """[time,lat,lon] lazy -> [nyear, ncell] numpy (annual sums over valid cells)."""
        rows = []
        for y in years:
            idx = np.where(tvals // 365 == y)[0]
            s = da.isel(time=slice(int(idx[0]), int(idx[-1]) + 1)).sum("time").values  # [lat,lon]
            rows.append(s[valid])
        return np.stack(rows)

    # --- (2) per-cell annual flux sums (one var at a time; peak memory ~ one chunk) ---
    A = {}
    ranges = {}
    for name, fn in [("prec", "d_prec.nc"), ("transp", "d_transp.nc"),
                     ("evap", "d_evap.nc"), ("interc", "d_interc.nc"),
                     ("runoff", "d_runoff.nc")]:
        da, _ = open_var(f"{out}/{fn}")
        A[name] = annual_per_cell(da)
        ranges[f"{name}_min"] = float(da.min().values)
        ranges[f"{name}_max"] = float(da.max().values)

    ET = A["transp"] + A["evap"] + A["interc"]
    Rres = A["prec"] - (ET + A["runoff"])  # [nyear, ncell] = dStorage + excess_water

    # d(SWE) per year (end-of-year minus start-of-year) — swe is a state (mm)
    swe_da, _ = open_var(f"{out}/d_swe.nc")
    dswe_year = []
    for y in years:
        idx = np.where(tvals // 365 == y)[0]
        a = swe_da.isel(time=int(idx[-1])).values[valid]
        b = swe_da.isel(time=int(idx[0])).values[valid]
        dswe_year.append(a - b)
    dswe_year = np.stack(dswe_year)
    ranges["swe_min"] = float(swe_da.min().values)
    ranges["swe_max"] = float(swe_da.max().values)

    # swc sanity by SAMPLING (never load the 135 GB cube)
    swc_da, _ = open_var(f"{out}/d_swc.nc", chunks={"time": 30})
    samp = swc_da.isel(time=slice(0, swc_da.sizes["time"], max(1, swc_da.sizes["time"] // 12)))
    ranges["swc_min"] = float(samp.min().values)
    ranges["swc_max"] = float(samp.max().values)
    report["sanity"] = ranges

    sum_prec = A["prec"].sum(axis=0)
    sum_loss = (ET + A["runoff"]).sum(axis=0)
    frac_imb = (sum_prec - sum_loss) / np.where(sum_prec > 1e-6, sum_prec, np.nan)

    def pct(x):
        return {f"p{p}": float(np.nanpercentile(np.abs(x), p)) for p in (50, 90, 99, 100)}

    report["closure"] = {
        "annual_residual_mm_per_yr_abs": pct(Rres.ravel()),
        "annual_residual_minus_dSWE_mm_abs": pct((Rres - dswe_year).ravel()),
        "multiyear_frac_imbalance_abs": pct(frac_imb),
        "mean_annual_prec_mm": float(np.nanmean(A["prec"])),
        "mean_annual_ET_mm": float(np.nanmean(ET)),
        "mean_annual_runoff_mm": float(np.nanmean(A["runoff"])),
        "mean_annual_residual_mm": float(np.nanmean(Rres)),
    }

    # --- units cross-check vs globalflux (subset/global aggregate) ---
    area = cell_area_m2(np.repeat(lat[:, None], lon.size, axis=1)[valid])  # [ncell] m2
    report["units_crosscheck_km3_per_yr"] = {
        k: [float((A[k][i] / 1000.0 * area).sum() / 1e9) for i in range(len(years))]
        for k in ["transp", "evap", "interc", "prec"]
    }
    report["note"] = ("Compare units_crosscheck against globalflux_*.csv "
                      "(x1e15 dm3/yr = x1000 km3): transp[y] here ~ globalflux transp[y]*1000.")

    print(json.dumps(report, indent=2))
    with open(f"{run_dir}/water_closure_summary.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nwrote {run_dir}/water_closure_summary.json")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else
         "/p/tmp/jamirp/esm_land_daily/daily_2000_2002_boreal_val_c45000_45999_seed1")
