"""Reference atmosphere profiles from GFDL-ESM4 historical 1985-2014 (SpeedyWeather cold-bias work).

    python build_speedy_profile_reference.py [out.csv]

Area-weighted (cos lat) monthly-mean temperature [K], specific humidity [g/kg] and relative
humidity [%] on GFDL-ESM4's pressure levels, per latitude band (|lat| < 15, 15-30, 30-60, >= 60,
global), all points (land + ocean; levels below the ground are masked in the source and left out
of the mean). Plus the band means of column water vapour [kg/m2] and total cloud cover [0-1].
Long table: band, var, plev_hPa, value (plev_hPa = 0 for the column quantities). GFDL-ESM4
r1i1p1f1 is the climate the emulator was trained on and matches the W5E5 land temperature to
0.01 K (ADR 0346), which is why it serves as the reference here; it is a model, not an
observation. speedy_cold_bias_repro.jl (env PROFREF) interpolates it in log p to its own layers.
"""

from __future__ import annotations

import os
import sys

import netCDF4
import numpy as np

SRC = (
    "/p/projects/climate_data_central/CMIP/CMIP6/CMIP/NOAA-GFDL/GFDL-ESM4/historical/r1i1p1f1/Amon"
)
DATA = "/p/projects/open/Jamir/esm_land_emulator_data/coupled"
OUT = (
    sys.argv[1] if len(sys.argv) > 1 else f"{DATA}/speedy_profile_reference_gfdl-esm4_1985-2014.csv"
)
BANDS = {"trop": (0, 15), "sub": (15, 30), "mid": (30, 60), "pol": (60, 91), "all": (0, 91)}
# months 1985-01 .. 2014-12 in the 1950-2014 file
T0, T1 = (1985 - 1950) * 12, (2014 - 1950 + 1) * 12


def path(var):
    d = f"{SRC}/{var}/gr1/v20190726"
    return f"{d}/{var}_Amon_GFDL-ESM4_historical_r1i1p1f1_gr1_195001-201412.nc"


def band_means(var, scale=1.0):
    """{band: levels array (or scalar)}: 1985-2014 mean, cos-lat weighted, masked-aware."""
    with netCDF4.Dataset(path(var)) as d:
        lat = d["lat"][:].astype(float)
        plev = d["plev"][:] / 100 if "plev" in d.variables else None
        out = {}
        for b, (lo, hi) in BANDS.items():
            j = np.where((np.abs(lat) >= lo) & (np.abs(lat) < hi))[0]
            # read this band's rows month-block by month-block to stay small
            num = den = 0.0
            for t in range(T0, T1, 60):
                x = d[var][
                    t : min(t + 60, T1), ..., j, :
                ]  # (time, [lev,] lat, lon), exact rows of both hemispheres
                x = np.ma.masked_invalid(x) * scale
                w = np.cos(np.deg2rad(lat[j]))[:, None] * np.ones(x.shape[-1])[None, :]
                w = np.broadcast_to(w, x.shape)
                wm = np.ma.array(w, mask=np.ma.getmaskarray(x))
                ax = (0, -2, -1)
                num = num + (x * wm).sum(axis=ax)
                den = den + wm.sum(axis=ax)
            out[b] = np.ma.filled(num / den, np.nan)
    return plev, out


def main():
    rows = []
    for var, name, scale in (("ta", "T_K", 1.0), ("hus", "q_gkg", 1000.0), ("hur", "rh_pct", 1.0)):
        plev, m = band_means(var, scale)
        for b, v in m.items():
            for p, x in zip(plev, v, strict=True):
                rows.append((b, name, float(p), float(x)))
        print(var, "done", flush=True)
    for var, name, scale in (("prw", "pw_kgm2", 1.0), ("clt", "cloud_cover", 0.01)):
        _, m = band_means(var, scale)
        for b, v in m.items():
            rows.append((b, name, 0.0, float(v)))
        print(var, "done", flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("band,var,plev_hPa,value\n")
        for r in rows:
            f.write(f"{r[0]},{r[1]},{r[2]:g},{r[3]:.6g}\n")
    print(f"wrote {OUT} ({len(rows)} rows)")
    for b in ("trop", "all"):
        print(f"\n{b}: plev  T  q  rh")
        tab = {(r[1], r[2]): r[3] for r in rows if r[0] == b}
        for p in sorted({r[2] for r in rows if r[0] == b and r[2] > 0}, reverse=True):
            t, q, rh = (tab[(v, p)] for v in ("T_K", "q_gkg", "rh_pct"))
            print(f"  {p:7.0f} {t:7.2f} {q:8.4f} {rh:6.1f}")
        pw, clt = tab[("pw_kgm2", 0.0)], tab[("cloud_cover", 0.0)]
        print(f"  column water vapour {pw:.1f} kg/m2, cloud cover {clt:.3f}")


if __name__ == "__main__":
    main()
