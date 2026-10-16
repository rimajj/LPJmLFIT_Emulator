"""Score a SpeedyWeather <-> emulator coupled run (run_speedy_landemu.jl, ADR 0345).

    python score_speedy_landemu.py <coupled_dir> [<control_dir>]

1. REPLAY GATE: the recorded weather run offline through ``LandEmulator.step_year`` reproduces
   every daily and yearly output of the coupled emulator exactly (the coupled emulator IS the
   released one).
2. WATER: the water SpeedyWeather received over the emulated columns equals the emulator's
   evapotranspiration (expected difference: one day's ET per 29 February, which holds the
   previous day's flux).
3. CLIMATE over the emulated land columns (cos-latitude x land-fraction weighted), coupled vs
   control (SpeedyWeather's own land evaporation): air temperature, precipitation,
   evapotranspiration, per year.
4. SPEEDYWEATHER'S LAND CLIMATE vs the GFDL-ESM4 1985-2014 climate the emulator's 30-year window
   was seeded with (the bias the emulator reads as a climate signal).
5. The coupled emulator's land carbon/water totals beside the same emulator's offline run on
   GFDL-ESM4 ssp370 weather on the full 0.5-degree grid (global_emu/emu/ssp370), same years.
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import landemu_coupler as lc  # noqa: E402

R_EARTH = 6.371e6
V = ["tas", "pr", "rsds", "lwnet", "huss", "et", "landfrac"]  # daily_means columns


def col_area(lat, nlat=48, nlon=96):
    """m2 of a T31 full Gaussian grid column (cos-latitude approximation)."""
    return R_EARTH**2 * (np.pi / nlat) * (2 * np.pi / nlon) * np.cos(np.radians(lat))


def yearly(dm, ndays_year=365):
    """(ncols, NV, days) -> (ncols, NV, years) means over complete 365-day emulator years."""
    ny = dm.shape[2] // ndays_year
    return dm[:, :, : ny * ndays_year].reshape(dm.shape[0], dm.shape[1], ny, ndays_year).mean(3)


def main():
    cdir = sys.argv[1]
    ctl = sys.argv[2] if len(sys.argv) > 2 else None
    z = np.load(os.path.join(cdir, "landemu_record.npz"))
    rep = {}
    ny = int(z["n_years"])
    y0 = int(z["start_year"])

    # 1. replay
    worst = lc.replay(os.path.join(cdir, "landemu_record.npz"))
    rep["replay_max_abs_diff"] = worst
    rep["replay_pass"] = max(worst.values()) == 0.0

    # 2. water
    ap, pr = z["x_applied"], z["x_produced"]
    rep["water"] = {
        "applied_mm_mean": float(ap.mean()),
        "produced_mm_mean": float(pr.mean()),
        "rel_diff_total": float((ap.sum() - pr.sum()) / pr.sum()),
        "max_abs_diff_mm": float(np.abs(ap - pr).max()),
        "n_leap_days": sum(1 for y in range(y0, y0 + ny + 1) if y % 4 == 0 and y < y0 + ny),
    }

    # 3/4. climate over the emulated columns
    dm = z["x_daily_means"]  # (ncols, NV, days)
    emu = z["x_emu"] - 1  # Julia 1-based positions in cols
    lat = z["col_lat"][z["mask"]]
    w = col_area(lat) * dm[emu, 6, :].mean(1)
    Yc = yearly(dm[emu])

    def wmean(a):
        return float(np.sum(a * w) / np.sum(w))

    clim = {"coupled": {}}
    for j, v in enumerate(V[:6]):
        clim["coupled"][v] = [wmean(Yc[:, j, i]) for i in range(Yc.shape[2])]
    if ctl:
        c = np.load(os.path.join(ctl, "control_record.npz"))
        assert np.array_equal(c["cols"], z["x_cols"])
        Yk = yearly(c["daily_means"][emu])
        clim["control"] = {
            v: [wmean(Yk[:, j, i]) for i in range(Yk.shape[2])] for j, v in enumerate(V[:6])
        }
    for k in clim:  # per year -> mm/yr for the water fluxes
        for v in ("pr", "et"):
            clim[k][v] = [x * 365 for x in clim[k][v]]
    rep["climate_emulated_columns"] = clim

    su = lc.build_setup(z["cell"], y0)
    H = su.clim_hist  # (30, n, 25), GFDL-ESM4 1985-2014
    from lpjmlfit_emulator.landemu.climate import CLIM_COLS

    tm, pa = CLIM_COLS.index("tmean_ann"), CLIM_COLS.index("prec_ann")
    gfdl_t, gfdl_p = H[:, :, tm].mean(0), H[:, :, pa].mean(0)
    sw_t, sw_p = Yc[:, 0, :].mean(1), Yc[:, 1, :].mean(1) * 365
    rep["speedy_minus_gfdl_1985_2014"] = {
        "tas_degC_mean": wmean(sw_t - gfdl_t),
        "tas_degC_abs_mean": wmean(np.abs(sw_t - gfdl_t)),
        "pr_mm_mean": wmean(sw_p - gfdl_p),
        "pr_rel_mean": wmean(sw_p - gfdl_p) / wmean(gfdl_p),
        "pr_abs_rel_mean": wmean(np.abs(sw_p - gfdl_p)) / wmean(gfdl_p),
        "gfdl_tas": wmean(gfdl_t),
        "gfdl_pr": wmean(gfdl_p),
    }

    # 5. emulator totals, coupled (T31 columns) vs offline (0.5 deg, GFDL-ESM4 ssp370)
    A = col_area(lat) * dm[emu, 6, :].mean(1)
    tot = {}
    for k in ("gpp", "npp", "transp", "evap", "interc", "runoff"):
        d = z[f"d_{k}"][:, : 365 * ny].reshape(len(A), ny, 365).sum(2)  # per m2 per year
        f = 1e-15 if k in ("gpp", "npp") else 1e-12  # gC -> PgC / mm m2 -> km3
        tot[k] = [float(np.sum(d[:, i] * A) * f) for i in range(ny)]
    tot["vegc_PgC"] = [float(np.sum(z["a_vegc"][:, i] * A) * 1e-15) for i in range(ny)]
    rep["coupled_totals_T31_land"] = tot
    rep["offline_totals_0p5deg_gfdl_ssp370"] = offline_totals(y0, ny)
    print(json.dumps(rep, indent=1))
    with open(os.path.join(cdir, "score.json"), "w") as fh:
        json.dump(rep, fh, indent=1)
    return 0 if rep["replay_pass"] else 1


def offline_totals(y0, ny):
    import glob_emu as g

    st = g.cells().sort("Cell")
    area = st["area_km2_approx"].to_numpy() * 1e6
    d = os.path.join(lc.DATA, "emu", "ssp370", "chunks")
    tot = {
        k: np.zeros(ny) for k in ("gpp", "npp", "transp", "evap", "interc", "runoff", "vegc_PgC")
    }
    for fn in sorted(os.listdir(d)):
        if fn.endswith("_end.npz") or not fn.endswith(".npz"):
            continue
        z = np.load(os.path.join(d, fn))
        i0 = int(np.where(z["years"] == y0)[0][0])
        a = area[z["cell"]]
        for k in ("gpp", "npp", "transp", "evap", "interc", "runoff"):
            f = 1e-15 if k in ("gpp", "npp") else 1e-12
            tot[k] += (z[f"m_{k}"][:, i0 : i0 + ny].sum(2) * a[:, None]).sum(0) * f
        tot["vegc_PgC"] += (z["a_vegc"][:, i0 : i0 + ny] * a[:, None]).sum(0) * 1e-15
    return {k: v.tolist() for k, v in tot.items()}


if __name__ == "__main__":
    sys.exit(main())
