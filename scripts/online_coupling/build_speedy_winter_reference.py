"""High-latitude winter reference for the SpeedyWeather cold-bias work, from GFDL-ESM4 historical 1985-2014.

    python build_speedy_winter_reference.py [out.csv]

For every T31 land column of the observed-land table (speedy_t31_land_reference_w5e5.csv, ADR 0346) poleward
of 50 degrees: the GFDL-ESM4 grid point nearest to it, that point's coldest calendar month in the 1985-2014
monthly climatology of near-surface air temperature, and in that month the climatological skin temperature (ts),
near-surface air temperature (tas), surface downward longwave and shortwave (rlds, rsds; daily files averaged to
the month) and the temperature profile on pressure levels 1000-300 hPa (ta; NaN below the ground).
Wide table, one row per column: ij, lat, lon, weight, cold_month, ts_K, tas_K, rlds, rsds, ta_<plev>_K ...
speedy_cold_bias_repro.jl (env WINTERREF) compares the model's own coldest-month values at the same columns.
GFDL-ESM4 r1i1p1f1 matches W5E5 land temperature to 0.01 K (annual, ADR 0346); it is a model, not observations,
but it carries a full profile, which the observations do not.
"""

from __future__ import annotations

import csv
import sys

import netCDF4
import numpy as np

SRC = "/p/projects/climate_data_central/CMIP/CMIP6/CMIP/NOAA-GFDL/GFDL-ESM4/historical/r1i1p1f1"
DATA = "/p/projects/open/Jamir/esm_land_emulator_data/coupled"
LANDREF = f"{DATA}/speedy_t31_land_reference_w5e5.csv"
OUT = (
    sys.argv[1] if len(sys.argv) > 1 else f"{DATA}/speedy_winter_reference_gfdl-esm4_1985-2014.csv"
)
PLEVS = (1000, 925, 850, 700, 600, 500, 400, 300)


def amon(var):
    return f"{SRC}/Amon/{var}/gr1/v20190726/{var}_Amon_GFDL-ESM4_historical_r1i1p1f1_gr1_195001-201412.nc"


def monthly_clim(var, jj, ii, lev=None):
    """(12, [nlev,] npoints) 1985-2014 monthly climatology at grid points (jj, ii)."""
    with netCDF4.Dataset(amon(var)) as d:
        t0 = (1985 - 1950) * 12
        x = d[var][t0 : t0 + 360]  # (360, [lev,] lat, lon)
        x = np.ma.filled(np.ma.masked_invalid(x).astype(float), np.nan)
        x = x[..., jj, ii]  # (360, [lev,] n)
        return np.nanmean(x.reshape(30, 12, *x.shape[1:]), axis=0)


def daily_monthly_clim(var, jj, ii):
    """(12, n) 1985-2014 monthly climatology from the GFDL-ESM4 daily files."""
    import glob

    files = sorted(glob.glob(f"{SRC}/day/{var}/gr1/*/{var}_day_*.nc"))
    num, den = np.zeros((12, len(jj))), np.zeros((12, 1))
    for f in files:
        with netCDF4.Dataset(f) as d:
            tv = d["time"]
            dates = netCDF4.num2date(tv[:], tv.units, getattr(tv, "calendar", "standard"))
            years = np.array([t.year for t in dates])
            sel = np.where((years >= 1985) & (years <= 2014))[0]
            if len(sel) == 0:
                continue
            months = np.array([dates[i].month for i in sel])
            x = d[var][sel[0] : sel[-1] + 1][:, jj, ii].astype(float)
            for m in range(1, 13):
                k = months == m
                num[m - 1] += x[k].sum(axis=0)
                den[m - 1] += k.sum()
    return num / den


def main():
    with open(LANDREF) as f:
        rows = [r for r in csv.DictReader(f) if abs(float(r["lat"])) >= 50]
    lat = np.array([float(r["lat"]) for r in rows])
    lon = np.array([float(r["lon"]) for r in rows]) % 360
    with netCDF4.Dataset(amon("tas")) as d:
        glat, glon = d["lat"][:].astype(float), d["lon"][:].astype(float)
        plev = d["plev"][:] / 100 if "plev" in d.variables else None
    del plev
    jj = np.abs(glat[None, :] - lat[:, None]).argmin(axis=1)
    dlon = np.abs(((glon[None, :] - lon[:, None]) + 180) % 360 - 180)
    ii = dlon.argmin(axis=1)
    tas = monthly_clim("tas", jj, ii)
    cold = tas.argmin(axis=0)  # 0-based month per column
    pick = np.arange(len(rows))
    ts = monthly_clim("ts", jj, ii)[cold, pick]
    with netCDF4.Dataset(amon("ta")) as d:
        gp = list((d["plev"][:] / 100).astype(int))
    ta = monthly_clim("ta", jj, ii)  # (12, nlev, n)
    ta_cold = {p: ta[cold, gp.index(p), pick] for p in PLEVS}
    rlds = daily_monthly_clim("rlds", jj, ii)[cold, pick]
    rsds = daily_monthly_clim("rsds", jj, ii)[cold, pick]
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["ij", "lat", "lon", "weight", "cold_month", "ts_K", "tas_K", "rlds", "rsds"]
            + [f"ta_{p}_K" for p in PLEVS]
        )
        for c, r in enumerate(rows):
            w.writerow(
                [
                    r["ij"],
                    r["lat"],
                    r["lon"],
                    r["weight"],
                    cold[c] + 1,
                    f"{ts[c]:.3f}",
                    f"{tas[cold[c], c]:.3f}",
                    f"{rlds[c]:.2f}",
                    f"{rsds[c]:.2f}",
                ]
                + [f"{ta_cold[p][c]:.3f}" for p in PLEVS]
            )
    wt = np.array([float(r["weight"]) for r in rows])

    def wm(x):
        ok = np.isfinite(x)
        return np.sum(wt[ok] * x[ok]) / np.sum(wt[ok])

    print(f"wrote {OUT}: {len(rows)} columns poleward of 50 deg")
    print(
        f"coldest month, weighted means: ts {wm(ts) - 273.15:.2f} C, tas {wm(tas[cold, pick]) - 273.15:.2f} C, rlds {wm(rlds):.1f}, rsds {wm(rsds):.1f} W/m2"
    )
    for p in PLEVS:
        print(
            f"  ta {p:4d} hPa {wm(ta_cold[p]) - 273.15:7.2f} C  ({np.isfinite(ta_cold[p]).mean() * 100:.0f} % of columns above ground)"
        )


if __name__ == "__main__":
    main()
