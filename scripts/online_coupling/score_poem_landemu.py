"""Score the POEM <-> learned-emulator runs (ADR 0347).

    python score_poem_landemu.py <run_dir> [<run_dir> ...]          -> <parent>/poem_scores.json
    python score_poem_landemu.py replay <run_dir> [nproc]           -> exit 0 iff every rank replays

Each run_dir is a POEM run made by poem/setup_poem_run.sh in mode ``shadow`` (stock POEM, the
emulator only records: the control, and the one-way result) or ``coupled``; its ``landemu/rank*/
landemu_record.npz`` hold, per emulated 0.5-degree cell and day, the weather POEM gave the
emulator, the emulator's daily outputs and yearly forest state, and LPJmL's own land
evapotranspiration, runoff and surface temperature (``x_lpj``).

Reported over the emulated cells (area weighted; cell area from latitude):
1. POEM's climate at those cells (2-m air temperature: annual / warmest / coldest month,
   precipitation, downward shortwave, net longwave) minus the same statistics of GSWP3-W5E5
   observations 1985-2014, GFDL-ESM4 historical 1985-2014 and GFDL-ESM4 historical 1850-1879
   (POEM runs a preindustrial climate, 284 ppm, so 1850-1879 is the like-for-like reference).
2. Per year: the emulator's GPP, NPP, evapotranspiration, runoff (PgC/yr, 1000 km3/yr),
   vegetation carbon (PgC), and LPJmL's own evapotranspiration and runoff at the same cells.
3. Water closure of the emulator: sum over the run of precipitation - ET - runoff - change of
   its three stores, relative to precipitation (exact up to the stores' float rounding).
4. POEM's own monthly atmosphere output, yearly means over ALL land / ocean: 2-m temperature,
   precipitation, evaporation, 2-m humidity, downward radiation, surface albedo; global 2-m T.
``replay`` re-runs every rank's recorded weather offline through ``step_year`` (in parallel):
the coupled emulator must be the released one, bit for bit.
"""

from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import diagnose_speedy_climate as dsc  # noqa: E402
import landemu_coupler as lc  # noqa: E402

R_EARTH = 6.371e6


def cell_area(lat, d=0.5):
    """Area of a d-degree cell centred at lat, m2."""
    a = np.radians(lat - d / 2), np.radians(lat + d / 2)
    return R_EARTH**2 * np.radians(d) * (np.sin(a[1]) - np.sin(a[0]))


def load_run(run):
    """All ranks of a run, concatenated over cells (each cell is on exactly one rank)."""
    paths = sorted(glob.glob(os.path.join(run, "landemu", "rank*", "landemu_record.npz")))
    assert paths, f"no records under {run}/landemu"
    zs = [np.load(p) for p in paths]
    ny = {int(z["n_years"]) for z in zs}
    assert len(ny) == 1, f"ranks disagree on the number of years: {ny}"
    keep = [
        k for k in zs[0].files if k.startswith(("d_", "a_")) or k in ("cell", "forcing", "x_lpj")
    ]
    out = {k: np.concatenate([z[k] for z in zs], 0) for k in keep}
    out["n_years"] = ny.pop()
    out["ranks"] = len(paths)
    assert len(np.unique(out["cell"])) == len(out["cell"]), "a cell on two ranks"
    return out


def per_year(z, area):
    ny, n = z["n_years"], len(z["cell"])

    def yr(a):  # (n, days) -> (n, ny) yearly sums
        return a[:, : 365 * ny].reshape(n, ny, 365).sum(2)

    pg = area[:, None] / 1e15  # gC/m2 -> PgC
    km3 = area[:, None] / 1e12  # mm = kg/m2 = 1e-3 m3/m2 -> 1000 km3
    et = z["d_interc"] + z["d_transp"] + z["d_evap"]
    lpj = z["x_lpj"]
    res = {
        "gpp_PgC": (yr(z["d_gpp"]) * pg).sum(0),
        "npp_PgC": (yr(z["d_npp"]) * pg).sum(0),
        "et_1000km3": (yr(et) * km3).sum(0),
        "runoff_1000km3": (yr(z["d_runoff"]) * km3).sum(0),
        "precip_1000km3": (yr(z["forcing"][:, :, 1]) * km3).sum(0),
        "lpj_et_1000km3": (yr(lpj[:, :, 0]) * km3).sum(0),
        "lpj_runoff_1000km3": (yr(lpj[:, :, 1]) * km3).sum(0),
    }
    if "a_vegc" in z:
        res["vegc_PgC"] = np.nansum(z["a_vegc"] * area[:, None] / 1e15, 0)
    return {k: [float(x) for x in v] for k, v in res.items()}


def water_closure(z):
    """Emulator water balance over the run, all cells: (P - ET - R - dStores) / P."""
    et = z["d_interc"] + z["d_transp"] + z["d_evap"]
    p = z["forcing"][:, :, 1]
    stores = z["d_swe"] + z["d_soilw"] + z["d_deep"]
    # the stores at the end of day 1 minus day 1's fluxes give the start stores
    s0 = stores[:, 0] - (p[:, 0] - et[:, 0] - z["d_runoff"][:, 0])
    resid = p.sum(1) - et.sum(1) - z["d_runoff"].sum(1) - (stores[:, -1] - s0)
    return {
        "max_abs_resid_mm": float(np.abs(resid).max()),
        "total_precip_mm_mean": float(p.sum(1).mean()),
    }


ATM_VARS = {  # POEM atmos_month name -> (scale, label)
    "t_ref": (1.0, "t_ref_K"),
    "precip": (86400.0, "precip_mm_day"),
    "evap": (86400.0, "evap_mm_day"),
    "q_ref": (1000.0, "q_ref_g_kg"),
    "swdn_sfc": (1.0, "swdn_W_m2"),
    "lwdn_sfc": (1.0, "lwdn_W_m2"),
    "alb_sfc": (1.0, "albedo"),
}


def atmos_summary(run):
    """POEM's own monthly atmosphere output: yearly means over ALL land and over ocean (atmosphere
    grid cells whose nearest 0.5-degree land-model cell is land), and the global 2-m temperature."""
    import netCDF4

    fa = sorted(glob.glob(os.path.join(run, "history", "*.atmos_month.nc")))
    fl = sorted(glob.glob(os.path.join(run, "history", "*.land_month.nc")))
    if not fa or not fl:
        return None
    with netCDF4.Dataset(fl[0]) as lm:
        land = ~np.ma.getmaskarray(lm["sroff"][0])
        llat, llon = lm["lat"][:], lm["lon"][:]
    out = {}
    with netCDF4.Dataset(fa[0]) as a:
        lat, lon = a["lat"][:], a["lon"][:]
        ii = np.abs(llat[:, None] - lat[None, :]).argmin(0)
        jj = np.abs(((llon[:, None] - lon[None, :] + 180) % 360) - 180).argmin(0)
        m = land[np.ix_(ii, jj)]
        w = np.cos(np.radians(lat))[:, None] * np.ones((1, len(lon)))
        nmon = a["time"].shape[0]
        ny = nmon // 12
        for v, (sc, lab) in ATM_VARS.items():
            x = np.asarray(a[v][: 12 * ny], np.float64).reshape(ny, 12, *m.shape).mean(1) * sc
            out[f"land_{lab}"] = [float((x[i] * w)[m].sum() / w[m].sum()) for i in range(ny)]
            out[f"ocean_{lab}"] = [float((x[i] * w)[~m].sum() / w[~m].sum()) for i in range(ny)]
            if v == "t_ref":
                out["global_t_ref_K"] = [float((x[i] * w).sum() / w.sum()) for i in range(ny)]
    out["n_years"] = ny
    return out


def main(runs):
    import glob_emu as g

    recs = {os.path.basename(os.path.normpath(r)): load_run(r) for r in runs}
    z0 = next(iter(recs.values()))
    for k, z in recs.items():
        assert np.array_equal(np.sort(z["cell"]), np.sort(z0["cell"])), f"{k}: other cells"
    st = g.cells().sort("Cell")
    rep = {"runs": list(recs), "n_cells": len(z0["cell"])}
    print(f"{len(z0['cell'])} emulated cells; reading reference climates ...", flush=True)
    order = {k: np.argsort(z["cell"]) for k, z in recs.items()}
    cell = np.sort(z0["cell"])
    lat, lon = st["lat"].to_numpy()[cell], st["lon"].to_numpy()[cell]
    area = cell_area(lat)
    refs = dsc.references(cell, lat, lon)
    refs["GFDL-ESM4 hist 1850-1879"] = dsc.stats(
        *dsc.read_daily(g.CLM["historical"], g.FORC_VARS[:4], cell, range(1850, 1880))
    )

    def wm(a):
        return float(np.sum(a * area) / np.sum(area))

    rep["references"] = {n: {q: wm(v.mean(1)) for q, v in R.items()} for n, R in refs.items()}
    rep["by_run"] = {}
    for name, z in recs.items():
        z = {
            k: (v[order[name]] if isinstance(v, np.ndarray) and v.shape[:1] == (len(cell),) else v)
            for k, v in z.items()
        }
        ny = z["n_years"]
        F = z["forcing"][:, : 365 * ny].reshape(len(cell), ny, 365, 5)
        S = dsc.stats(F[..., 0], F[..., 1], F[..., 2], F[..., 3])
        yrs = slice(1, ny) if ny > 1 else slice(0, 1)
        rep["by_run"][name] = {
            "years": ny,
            "ranks": z["ranks"],
            "climate_per_year": {q: [wm(S[q][:, i]) for i in range(ny)] for q in S},
            "huss_per_year": [wm(F[:, i, :, 4].mean(1)) for i in range(ny)],
            "minus_reference_years2toN": {
                n: {q: wm(S[q][:, yrs].mean(1) - R[q].mean(1)) for q in S} for n, R in refs.items()
            },
            "minus_w5e5_by_band_tas": {
                b: wm(
                    np.where(
                        (np.abs(lat) >= lo) & (np.abs(lat) < hi),
                        S["tas"][:, yrs].mean(1) - refs["W5E5 obs 1985-2014"]["tas"].mean(1),
                        0,
                    )
                )
                / max(wm(((np.abs(lat) >= lo) & (np.abs(lat) < hi)).astype(float)), 1e-12)
                for b, (lo, hi) in dsc.BANDS.items()
            },
            "land_per_year": per_year(z, area),
            "water_closure": water_closure(z),
            "poem_atmosphere_per_year": atmos_summary(runs[list(recs).index(name)]),
        }
    path = os.path.join(os.path.dirname(os.path.normpath(runs[0])), "poem_scores.json")
    with open(path, "w") as fh:
        json.dump(rep, fh, indent=1)
    print(json.dumps(rep, indent=1))
    print(f"-> {path}")
    return 0


def _replay_one(p):
    w = lc.replay(p)
    return p, max(w.values()), w


def replay_all(run, nproc=20):
    from multiprocessing import Pool

    paths = sorted(glob.glob(os.path.join(run, "landemu", "rank*", "landemu_record.npz")))
    assert paths
    with Pool(nproc) as pool:
        res = pool.map(_replay_one, paths)
    worst = max(r[1] for r in res)
    for p, m, _ in res:
        print(f"{os.path.basename(os.path.dirname(p))}: max |coupled - offline| = {m}", flush=True)
    print("REPLAY", "IDENTICAL on all ranks" if worst == 0 else f"DIFFERS (worst {worst})")
    return 0 if worst == 0 else 1


if __name__ == "__main__":
    if sys.argv[1] == "replay":
        sys.exit(replay_all(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 20))
    sys.exit(main(sys.argv[1:]))
