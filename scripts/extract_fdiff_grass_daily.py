#!/usr/bin/env python
# =============================================================================
# extract_fdiff_grass_daily.py — slice the C binary's NEW daily grass GPP/NPP outputs
# (d_grass_gpp.nc / d_grass_npp.nc, built into LPJmL-FIT this session: conf.h D_GRASS_GPP/NPP,
# daily_natural.c cell-mean write, fwriteoutput.c flush) into a small COMMITTED reference CSV for
# the F_diff grass-level validation — the way extract_fdiff_decadal.py sliced the cell GPP.
#
# Writes test/testitems/references/hainich_grass_daily_2009_2019.csv with per-day:
#   year, day, c_grass_gpp, c_grass_npp, c_cell_gpp   (gC/m2/day, cell-mean)
# for sim years 2009..2019 (the decadal-forcing window F_diff's committed structure covers).
#
#   run: /home/jamirp/.conda/envs/py311_new/bin/python scripts/extract_fdiff_grass_daily.py
# =============================================================================
import os
import numpy as np
import xarray as xr

RUN = "/p/tmp/jamirp/esm_land_daily/daily_2000_2019_grassgpp_c42490_seed1/output"
REFDIR = os.path.join(os.path.dirname(__file__), "..", "test", "testitems", "references")
FIRSTYEAR = 2000
Y0, Y1 = 2009, 2019
DPY = 365


def load(path):
    ds = xr.open_dataset(path, decode_cf=False)
    var = max((v for v in ds.data_vars if "bnds" not in v.lower()
               and "time" in [d.lower() for d in ds[v].dims]), key=lambda v: ds[v].size)
    a = np.asarray(ds[var].values).reshape(-1).astype(float)
    a[a <= -1e30] = np.nan
    ds.close()
    return a


def main():
    gpp = load(os.path.join(RUN, "d_grass_gpp.nc"))
    npp = load(os.path.join(RUN, "d_grass_npp.nc"))
    tot = load(os.path.join(RUN, "d_gpp.nc"))
    out = os.path.join(REFDIR, "hainich_grass_daily_2009_2019.csv")
    nrows = 0
    with open(out, "w") as f:
        f.write("# C-binary daily GRASS GPP/NPP (cell-mean, gC/m2/day) + cell total GPP, Hainich (global grid 42490)\n")
        f.write("# LPJmL-FIT with the added D_GRASS_GPP/D_GRASS_NPP outputs (patches/lpjmlfit_daily_grass_gpp.patch)\n")
        f.write("year,day,c_grass_gpp,c_grass_npp,c_cell_gpp\n")
        for y in range(Y0, Y1 + 1):
            i0 = (y - FIRSTYEAR) * DPY
            for d in range(DPY):
                k = i0 + d
                f.write(f"{y},{d + 1},{gpp[k]:.6g},{npp[k]:.6g},{tot[k]:.6g}\n")
                nrows += 1
    # summary
    tot_g = np.nansum([gpp[(y - FIRSTYEAR) * DPY:(y - FIRSTYEAR) * DPY + DPY].sum() for y in range(Y0, Y1 + 1)])
    print(f"wrote {out} ({nrows} rows, {Y0}-{Y1})")
    for y in range(Y0, Y1 + 1):
        i0 = (y - FIRSTYEAR) * DPY
        print(f"  {y}: grass GPP={np.nansum(gpp[i0:i0+DPY]):.1f}  NPP={np.nansum(npp[i0:i0+DPY]):.1f}  cellGPP={np.nansum(tot[i0:i0+DPY]):.1f} gC/m2/yr")
    print("DONE.")


if __name__ == "__main__":
    main()
