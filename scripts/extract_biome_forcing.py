#!/usr/bin/env python3
# =============================================================================
# extract_biome_forcing.py — Phase 5 (multi-cell / biome generalization).
#
# Extracts REAL daily atmospheric forcing (GSWP3-W5E5 obsclim, the SAME .clm the
# LPJmL-FIT global run consumed) for a set of BIOME-REPRESENTATIVE cells, so the
# coupled S+F+E emulator (Component F + the energy closure E) can be driven and
# validated across climate regimes (tropical / boreal / semi-arid / mediterranean
# / temperate), not just the Hainich prototype.
#
# The forcing is read from the model-grid "_test" .clm (YEARCELL, float32, scalar 1.0)
# — the exact grid whose cell 42490 = Hainich is validated (extract_fdiff_validation_inputs.py
# checks .clm precip == the model's d_prec). Cell -> lat/lon comes from the global run's grid.nc.
# Wind + surface pressure are NOT in these files (the run never used them); the coupled driver
# supplies a constant wind + an elevation-free psurf (documented limitation, START_HERE §8).
#
# Usage:  /home/jamirp/.conda/envs/py311_new/bin/python scripts/extract_biome_forcing.py
# Writes (committed, small): test/testitems/references/biome_forcing_<name>.csv
#   columns: year,doy,temp,swdown,lwnet,precip,huss,daylength,co2   (units as hainich_forcing_*.csv)
# =============================================================================
import os
import numpy as np
import xarray as xr

GLOBAL = "/p/projects/waldspektrum/priesner/clustering/global"
GRID = "/p/tmp/jamirp/esm_land_daily/daily_2000_2019_global_c0_67419_seed1/output/grid.nc"
CO2_FILE = "/p/projects/lpjml/inputs/co2/global/TRENDY/v12/global_co2_ann_1700_2022.txt"
REPO = "/p/projects/open/Jamir/esm_land_emulator"
REF_OUT = os.path.join(REPO, "test/testitems/references")

HDR, CLM_FIRSTYEAR, NBANDS, NCELL, NDAYYEAR = 51, 1901, 365, 67420, 365
YEARS = list(range(2010, 2020))          # committed decade (small)

CLM = {
    "temp": "temperature_test.clm", "swdown": "short_wave_radiation_test.clm",
    "lwnet": "long_wave_radiation_test.clm", "precip": "precipitation_test.clm",
    "huss": "humid_test.clm",
}

# biome-representative cells (index resolved from grid.nc; see the docstring). Ordered cold->hot.
BIOMES = {
    "boreal_siberia": 52059,        # ~61.75 N, 104.75 E  — boreal needleleaf, strong seasonality
    "temperate_hainich": 42490,     # ~51.25 N,  10.25 E  — temperate beech (the prototype)
    "mediterranean_iberia": 33335,  # ~39.75 N,  -4.25 E  — summer-dry mediterranean
    "semiarid_sahel": 18371,        # ~13.75 N,   4.75 E  — semi-arid savanna
    "tropical_amazon": 12045,       # ~-3.25 N, -60.25 E  — tropical rainforest
}


def read_clm_year(path, cell, year):
    y = year - CLM_FIRSTYEAR
    off = HDR + ((y * NCELL + cell) * NBANDS) * 4
    with open(path, "rb") as f:
        f.seek(off)
        return np.frombuffer(f.read(NBANDS * 4), dtype="<f4").astype(np.float64)


def daylength_petpar2(lat, day):
    delta = np.deg2rad(-23.4 * np.cos(2 * np.pi * (day + 10.0) / NDAYYEAR))
    u = np.sin(np.deg2rad(lat)) * np.sin(delta)
    v = np.cos(np.deg2rad(lat)) * np.cos(delta)
    if u >= v:
        return 24.0
    if u <= -v:
        return 0.0
    return 24.0 * np.arccos(-u / v) / np.pi


def read_co2(path):
    years, vals = [], []
    with open(path) as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            p = ln.split()
            years.append(int(float(p[0])))
            vals.append(float(p[1]))
    return dict(zip(years, vals))


def cell_latlon(cell):
    d = xr.open_dataset(GRID, decode_times=False)
    lat = ((d["lat_bnds"][:, 0] + d["lat_bnds"][:, 1]) / 2).values
    lon = ((d["lon_bnds"][:, 0] + d["lon_bnds"][:, 1]) / 2).values
    cid = np.asarray(d["cellid"])
    idx = np.argwhere(cid == cell)
    if len(idx) == 0:
        raise ValueError(f"cell {cell} not found in grid.nc")
    i, j = idx[0]
    return float(lat[i]), float(lon[j])


def main():
    co2 = read_co2(CO2_FILE)
    for name, cell in BIOMES.items():
        lat, lon = cell_latlon(cell)
        dl = np.array([daylength_petpar2(lat, day) for day in range(1, NDAYYEAR + 1)])
        cols = {k: [] for k in ("year", "doy", "temp", "swdown", "lwnet", "precip", "huss", "daylength", "co2")}
        for yr in YEARS:
            forc = {k: read_clm_year(os.path.join(GLOBAL, fn), cell, yr) for k, fn in CLM.items()}
            for day in range(NDAYYEAR):
                cols["year"].append(yr); cols["doy"].append(day + 1)
                for k in ("temp", "swdown", "lwnet", "precip", "huss"):
                    cols[k].append(forc[k][day])
                cols["daylength"].append(dl[day]); cols["co2"].append(co2[yr])
        mat = np.column_stack([cols[k] for k in cols])
        hdr = (f"# Biome cell {cell} ({name}) ~{lat:.2f}N/{lon:.2f}E — REAL GSWP3-W5E5 daily forcing "
               f"{YEARS[0]}-{YEARS[-1]} from the model-grid _test .clm. Units: temp degC, swdown/lwnet W/m2, "
               f"precip mm/day, huss kg/kg, daylength h, co2 ppm.\n" + ",".join(cols.keys()))
        out = os.path.join(REF_OUT, f"biome_forcing_{name}.csv")
        np.savetxt(out, mat, delimiter=",", header=hdr, comments="", fmt="%.6g")
        tmean = np.mean(cols["temp"]); pmean = np.sum(cols["precip"]) / len(YEARS)
        print(f"{name:24s} cell {cell} ({lat:.2f},{lon:.2f})  Tmean={tmean:5.1f}C  Pann={pmean:6.0f}mm  -> {os.path.basename(out)}")


if __name__ == "__main__":
    main()
