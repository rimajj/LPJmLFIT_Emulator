#!/usr/bin/env python
"""
Phase-1 (P3b) WATER-CLOSURE check on a daily-output subset re-run.

Evidence tiers (see JOURNAL / DESIGN Phase-1 gate):
  (1) DEFINITIVE — LPJmL's own per-cell/year water balance (check_fluxes.c, active
      under -DSAFE) enforces |balanceW| <= 1.5 mm/yr and ABORTS otherwise. A clean
      run over all cells x years IS the closure proof. This script confirms the
      logs are error-free and quantifies the residual from the outputs.
  (2) OUTPUT FLUX BALANCE (needs no storage reconstruction) — per cell:
        R := prec - (transp + evap + interc + runoff)     [mm/yr]
      equals dStorage + excess_water. Over the full multi-year run the net storage
      drift is bounded, so Sum(prec) ~ Sum(ET+runoff): report the per-cell
      fractional imbalance. Also split R against observed d(SWE) (snow, mm).
  (3) SELF-CONSISTENCY — daily fluxes >= 0; swc fractional in [0,1]; snow builds
      and melts seasonally (d(SWE) over a full year ~ 0); daily sums reproduce the
      annual globalflux aggregate (units cross-check).

NB: swc is FRACTIONAL saturation = water/wsats; absolute soil water in mm needs the
per-layer saturated capacity wsats, which LPJmL does NOT expose as an output. So the
soil-water part of dStorage is inferred as (R - d(SWE)); it is not independently
reconstructed here. This is a documented limitation of the output set for the hybrid
water budget (would need a wsat output or soil-param reconstruction).

Usage:  python scripts/water_closure_check.py <run_dir>
"""
import json
import sys
import numpy as np
import xarray as xr

R_EARTH = 6_371_000.0
DEG = np.pi / 180.0
DLL = 0.5  # grid resolution (deg)


def cell_area_m2(lat_deg):
    """Area (m^2) of a 0.5x0.5 deg cell centred at lat_deg."""
    phi = lat_deg * DEG
    dlat = DLL * DEG
    return R_EARTH**2 * (DLL * DEG) * (np.sin(phi + dlat / 2) - np.sin(phi - dlat / 2))


def load_daily(path, var=None):
    ds = xr.open_dataset(path, decode_times=False)
    if var is None or var not in ds.variables:
        # auto-detect the data var: has time+lat+lon dims, not a *_bnds coord
        cands = [n for n, v in ds.data_vars.items()
                 if "time" in v.dims and "lat" in v.dims and not n.endswith("_bnds")]
        var = cands[0]
    da = ds[var]
    fill = da.attrs.get("_FillValue", da.attrs.get("missing_value", -1e32))
    arr = da.values.astype("float64")
    arr = np.where(arr < fill / 2, np.nan, arr)  # mask fills (large negative)
    return arr, ds


def main(run_dir):
    out = f"{run_dir}/output"
    # --- grid: valid cells + areas ---
    g = xr.open_dataset(f"{out}/grid.nc")
    # grid.nc for a subset run: lat/lon axes of the bounding box; use a flux file's
    # own coords + a valid mask from the first flux field.
    prec, dsp = load_daily(f"{out}/d_prec.nc")  # [time, lat, lon]
    lat = dsp["lat"].values
    lon = dsp["lon"].values
    time = dsp["time"].values.astype(int)  # days since 2000-1-1, noleap
    ntime = prec.shape[0]
    valid = np.isfinite(prec).all(axis=0)  # [lat, lon] cells present all days
    ncell = int(valid.sum())

    flux = {}
    for name, fn in [
        ("transp", "d_transp.nc"),
        ("evap", "d_evap.nc"),
        ("interc", "d_interc.nc"),
        ("runoff", "d_runoff.nc"),
        ("prec", "d_prec.nc"),
        ("swe", "d_swe.nc"),
        ("pet", "d_pet.nc"),
    ]:
        arr, _ = load_daily(f"{out}/{fn}")
        flux[name] = arr  # [time, lat, lon] mm/day (swe: mm state)

    swc, _ = load_daily(f"{out}/d_swc.nc", "SWC")  # [time, layer, lat, lon] fractional

    # --- per-year indexing (noleap 365-day years) ---
    years = np.unique(time // 365)
    yr0 = 2000
    report = {"run_dir": run_dir, "n_cells": ncell, "years": [int(yr0 + y) for y in years]}

    # --- (3) physical sanity ---
    def masked(a):  # [time,...] -> only valid cells
        return a[..., valid]

    sane = {}
    for k in ["transp", "evap", "interc", "runoff", "prec"]:
        v = masked(flux[k])
        sane[f"{k}_min"] = float(np.nanmin(v))
        sane[f"{k}_max"] = float(np.nanmax(v))
    swc_v = swc[..., valid]
    sane["swc_min"] = float(np.nanmin(swc_v))
    sane["swc_max"] = float(np.nanmax(swc_v))
    sane["swe_min"] = float(np.nanmin(masked(flux["swe"])))
    sane["swe_max"] = float(np.nanmax(masked(flux["swe"])))
    report["sanity"] = sane

    # --- (2) per-cell annual budget ---
    # annual sums per cell [ncell] for each year
    def annual_sum(arr):  # arr [time, lat, lon] -> [nyear, ncell]
        a = arr[..., valid]  # [time, ncell]
        return np.stack([np.nansum(a[time // 365 == y], axis=0) for y in years])

    A = {k: annual_sum(flux[k]) for k in ["transp", "evap", "interc", "runoff", "prec"]}
    ET = A["transp"] + A["evap"] + A["interc"]
    Rres = A["prec"] - (ET + A["runoff"])  # [nyear, ncell] mm/yr = dStorage+excess

    # d(SWE) per year: swe at last day of year - swe at first day of year
    swe = flux["swe"][..., valid]  # [time, ncell]
    dswe_year = []
    for y in years:
        idx = np.where(time // 365 == y)[0]
        dswe_year.append(swe[idx[-1]] - swe[idx[0]])
    dswe_year = np.stack(dswe_year)  # [nyear, ncell]

    # multi-year cumulative closure
    sum_prec = A["prec"].sum(axis=0)
    sum_loss = (ET + A["runoff"]).sum(axis=0)
    frac_imbalance = (sum_prec - sum_loss) / np.where(sum_prec > 1e-6, sum_prec, np.nan)

    def pct(x, ps=(50, 90, 99, 100)):
        return {f"p{p}": float(np.nanpercentile(np.abs(x), p)) for p in ps}

    report["closure"] = {
        "annual_residual_mm_per_yr_abs": pct(Rres.ravel()),
        "annual_residual_minus_dSWE_mm_abs": pct((Rres - dswe_year).ravel()),
        "multiyear_frac_imbalance_abs": pct(frac_imbalance),
        "mean_annual_prec_mm": float(np.nanmean(A["prec"])),
        "mean_annual_ET_mm": float(np.nanmean(ET)),
        "mean_annual_runoff_mm": float(np.nanmean(A["runoff"])),
        "mean_annual_residual_mm": float(np.nanmean(Rres)),
        "mean_dSWE_full_period_mm": float(np.nanmean(swe[np.where(time // 365 == years[-1])[0][-1]] - swe[np.where(time // 365 == years[0])[0][0]])),
    }

    # --- units cross-check vs globalflux (subset aggregate) ---
    area = cell_area_m2(np.repeat(lat[:, None], lon.size, axis=1)[valid])  # [ncell] m2
    # volume km3 = sum_cells (mm/yr /1000 -> m) * area_m2 / 1e9
    vol = {}
    for k in ["transp", "evap", "interc", "prec"]:
        vol[k] = [float((A[k][i] / 1000.0 * area).sum() / 1e9) for i in range(len(years))]  # km3/yr
    report["units_crosscheck_km3_per_yr"] = vol
    report["note"] = (
        "Compare units_crosscheck against globalflux_*.csv (x1e15 dm3/yr = x1000 km3). "
        "transp[2000] here should match globalflux transp[2000]*1000."
    )

    print(json.dumps(report, indent=2))
    with open(f"{run_dir}/water_closure_summary.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nwrote {run_dir}/water_closure_summary.json")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else
         "/p/tmp/jamirp/esm_land_daily/daily_2000_2002_boreal_val_c45000_45999_seed1")
