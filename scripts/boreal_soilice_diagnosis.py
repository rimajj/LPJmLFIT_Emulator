#!/usr/bin/env python3
"""ADR 0051 open item — is F_diff's missing soil ice why `wscal_leafon` under-stresses boreal Siberia?

ADR 0051 closed the `water_stress` conditioning shift in 4 of 5 biome cells but NOT `boreal_siberia`
(52059): the C says it is water stressed (0.3146) while the C-faithful leaf-on index gives exactly 0.000,
because F_diff's `emax·wr` exceeds the leaf-on demand on 100 % of days. Tagged `[ASSUMPTION]`: the C's
``wr`` is over **plant-available** water and the C's soil carries ice (``ice_depth``/``ice_fw``,
``getrootdist(…, config->permafrost)``), while F_diff has no soil-ice or permafrost state at all — so
F_diff's ``wr`` never collapses in a frozen profile.

FALSIFIABLE TEST (the one ADR 0051 recorded). Recover the C's own root-zone plant-available fraction and
look at its seasonal cycle. Per ADR 0035, the ONE C output carrying the model's ``w`` is ``rootmoist``
(``update_daily.c:414`` = ``Σ_{l<3} w[l]·whcs[l]`` mm over the top 1 m — ``swc`` is NOT invertible to
``w``), so::

    w_C(t) = rootmoist(t) / Σ_{l<3} whc_nat[l,month(t)] · soildepth[l]        soildepth = 200,300,500 mm

which is exactly the quantity `slow.jl::root_zone_soilmoist` computes for the emulator
(``ROOT_ZONE_LAYERS = 3``). PREDICTION: at 52059 the C's ``w_C`` collapses in winter/spring (ice) while
F_diff's stays high; at Hainich/Amazon both stay high. Compare against
`scripts/boreal_soilice_probe.jl`, which prints the emulator's side of the same climatology.

Run:  scripts/sbatch_python.sh M-soilice scripts/boreal_soilice_diagnosis.py
"""
import os

import netCDF4 as nc
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # never hard-code (CLAUDE.md §9.6)
OUT = "/p/tmp/jamirp/esm_land_daily/daily_2000_2019_global_c0_67419_seed1/output"
SOILDEPTH_TOP3 = np.array([200.0, 300.0, 500.0])   # mm — a C GLOBAL (fscansoilpar.c:36, par/soil_20m.js)
FIRSTYEAR, Y0, Y1 = 2000, 2010, 2019               # dataset start; the committed-forcing window
MONTH_LEN = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])   # noleap 365


def read_cells():
    """(name, lat, lon) from the committed per-cell registry."""
    rows = []
    with open(os.path.join(REPO, "test", "testitems", "references", "M_cells.csv")) as f:
        lines = [ln for ln in f if ln.strip() and not ln.startswith("#")]
    hdr = lines[0].strip().split(",")
    for ln in lines[1:]:
        p = ln.strip().split(",")
        d = dict(zip(hdr, p))
        rows.append((d["name"], float(d["lat"]), float(d["lon"])))
    return rows


def main():
    rm = nc.Dataset(f"{OUT}/d_rootmoist.nc")
    wh = nc.Dataset(f"{OUT}/whc_nat.nc")
    lats, lons = rm["lat"][:], rm["lon"][:]

    d0 = (Y0 - FIRSTYEAR) * 365
    d1 = (Y1 + 1 - FIRSTYEAR) * 365
    m0 = (Y0 - FIRSTYEAR) * 12
    m1 = (Y1 + 1 - FIRSTYEAR) * 12
    # day -> month index within the 10-yr window (noleap 365)
    doy_month = np.repeat(np.arange(12), MONTH_LEN)
    day_month = np.tile(doy_month, Y1 - Y0 + 1) + 12 * np.repeat(np.arange(Y1 - Y0 + 1), 365)

    print("=== the C's OWN root-zone plant-available fraction w (top 1 m), monthly climatology 2010-2019 ===")
    print("   w_C = rootmoist / SUM_{l<3} whc_nat[l]*soildepth[l]   (ADR 0035; the same quantity as")
    print("   slow.jl::root_zone_soilmoist, ROOT_ZONE_LAYERS=3). PREDICTION: 52059 collapses in winter.")
    print(f"\n{'cell':<22} " + " ".join(f"{m:>5}" for m in
          ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
          + f" {'min':>6} {'max':>6}")
    for name, lat, lon in read_cells():
        j = int(np.argmin(np.abs(lats - lat)))
        i = int(np.argmin(np.abs(lons - lon)))
        r = np.asarray(rm["rootmoist"][d0:d1, j, i], dtype=float)          # mm, daily
        w3 = np.asarray(wh["whc_nat"][m0:m1, :3, j, i], dtype=float)       # FRACTION, monthly, top 3 layers
        cap_m = (w3 * SOILDEPTH_TOP3[None, :]).sum(axis=1)                 # mm capacity per month
        if not np.all(np.isfinite(r)) or not np.all(np.isfinite(cap_m)) or np.any(cap_m <= 0):
            print(f"{name:<22} -- masked / no data at this grid point --")
            continue
        w_c = r / cap_m[day_month]
        clim = [w_c[day_month % 12 == m].mean() for m in range(12)]
        print(f"{name:<22} " + " ".join(f"{v:5.3f}" for v in clim)
              + f" {w_c.min():6.3f} {w_c.max():6.3f}")

    print("\nA winter collapse at boreal_siberia CONFIRMS the soil-ice hypothesis (F_diff has no ice state,")
    print("so its wr stays high year-round => emax*wr always exceeds the leaf-on demand => wscal == 1).")
    print("A flat, high w_C there REFUTES it and the boreal residual needs a different explanation.")


if __name__ == "__main__":
    main()
