"""Why is SpeedyWeather's land cold, and what do the extra land -> atmosphere channels change?
(ADR 0346)

    python diagnose_speedy_climate.py <run_dir> [<run_dir> ...]
        -> <parent of the first run_dir>/climate_diagnosis.json

Each run_dir is a run of run_speedy_landemu.jl made with the climate diagnostics (control or
coupled, any OCEAN / ALBEDO / ROUGH). For every run, over the land columns the emulator represents
(nearest 0.5-degree cell within 3 degrees, cos-latitude x land-fraction weighted, as
score_speedy_landemu.py):

1. REFERENCE CLIMATES at those same cells, all computed the same way from daily weather:
   GSWP3-W5E5 observations 1985-2014, GFDL-ESM4 historical 1985-2014 (ISIMIP3b, bias-adjusted
   towards W5E5) and GFDL-ESM4 ssp370 2015-2024 (what the emulator saw offline for the years the
   coupled run covers).
2. SpeedyWeather minus each reference, per year and over years 2..N: annual / warmest-month /
   coldest-month air temperature, precipitation, downward shortwave, net longwave; by latitude.
3. MOUNTAINS: SpeedyWeather's T31 orography under the column against the real elevation of the
   0.5-degree cell (input_VERSION2 elevation.bin, matched on coordinates); the temperature that
   height difference explains at a standard 6.5 K/km lapse rate.
4. DRIFT: global daily means of air temperature (all / land / ocean points), sea-surface
   temperature and sea ice area, per year.
5. LAND SURFACE (per year): land albedo, absorbed shortwave, sensible heat flux,
   evapotranspiration, top soil temperature, SpeedyWeather's own snow.
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import landemu_coupler as lc  # noqa: E402

REPO = lc.REPO
OBS = (
    "/p/projects/waldspektrum/priesner/clustering/global/{v}_test.clm"  # GSWP3-W5E5 obsclim, orderA
)
# orderA coordinates (v3 .clm, header 51, float32 lon/lat pairs). The emulator's cells and the
# GFDL-ESM4 files are in grid.bin order, so the observations are matched ON COORDINATES
# (CLAUDE.md sec. 1: the two 67 420-cell orders disagree, and pairing them silently shifts cells).
OBS_GRID = "/p/projects/waldspektrum/priesner/clustering/global/soil_code_test.grid.clm"
OBS_VARS = ("temperature", "precipitation", "short_wave_radiation", "long_wave_radiation")
ELEV = "/p/projects/biodiversity/input_VERSION2/elevation.bin"  # int16 m, ordered as grid.bin
GRID = "/p/projects/biodiversity/input_VERSION2/grid.bin"  # int16 lon, lat x 0.01 (NOT orderA)
DPM = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
MB = np.concatenate([[0], np.cumsum(DPM)])
LAPSE = 6.5e-3  # K/m
BANDS = {"tropics |lat|<23.5": (0, 23.5), "mid 23.5-50": (23.5, 50), "high >50": (50, 91)}
# daily_means columns of run_speedy_landemu.jl
TAS, PR, RSDS, LWNET, HUSS, ET, LF, ALB, SH, TSOIL, SNOW = range(11)


def load(run):
    """A run's record as a dict without the coupled record's x_ prefix."""
    for fn in ("landemu_record.npz", "control_record.npz"):
        p = os.path.join(run, fn)
        if os.path.exists(p):
            z = np.load(p)
            return {(k[2:] if k.startswith("x_") else k): z[k] for k in z.files}
    raise FileNotFoundError(f"no record in {run}")


def stats(t, p, sw, lw):
    """Daily (n, years, 365) -> dict of (n, years): annual / warmest / coldest month T,
    precipitation sum, shortwave, net longwave."""
    mon = np.stack([t[:, :, MB[m] : MB[m + 1]].mean(2) for m in range(12)], -1)
    return {
        "tas": t.mean(2),
        "t_warm": mon.max(-1),
        "t_cold": mon.min(-1),
        "pr": p.sum(2),
        "rsds": sw.mean(2),
        "lwnet": lw.mean(2),
    }


def read_daily(path_fmt, names, cells, years):
    from build_transient_boundary import open_clm

    out = []
    for v in names:
        mm, fy, ncell, nb, sc = open_clm(path_fmt.format(v=v))
        assert ncell == 67420 and nb == 365
        out.append(np.stack([np.asarray(mm[y - fy, cells], np.float64) * sc for y in years], 1))
    return out


def orderA_index(lat, lon):
    """orderA positions of 0.5-degree cells at (lat, lon)."""
    a = np.fromfile(OBS_GRID, "<f4", offset=51).reshape(-1, 2)
    assert len(a) == 67420
    key = {(round(float(y), 2), round(float(x), 2)): i for i, (x, y) in enumerate(a)}
    return np.array([key[(round(y, 2), round(x, 2))] for y, x in zip(lat, lon, strict=True)])


def references(cells, lat, lon):
    import glob_emu as g

    yh = range(1985, 2015)
    f4 = g.FORC_VARS[:4]
    assert f4 == ("tas", "pr", "rsds", "lwnet")
    return {
        "W5E5 obs 1985-2014": stats(*read_daily(OBS, OBS_VARS, orderA_index(lat, lon), yh)),
        "GFDL-ESM4 hist 1985-2014": stats(*read_daily(g.CLM["historical"], f4, cells, yh)),
        "GFDL-ESM4 ssp370 2015-2024": stats(
            *read_daily(g.CLM["ssp370"], f4, cells, range(2015, 2025))
        ),
    }


def cell_elevation(lat, lon):
    """Real elevation [m] of 0.5-degree cells at (lat, lon) (input_VERSION2, by coordinates)."""
    g = np.fromfile(GRID, "<i2", offset=43).reshape(-1, 2) * 0.01
    e = np.fromfile(ELEV, "<i2", offset=43).astype(np.float64)
    assert len(g) == len(e) == 67420
    key = {(round(a, 2), round(o, 2)): i for i, (o, a) in enumerate(g)}
    idx = np.array([key[(round(a, 2), round(o, 2))] for a, o in zip(lat, lon, strict=True)])
    return e[idx]


def main():
    import glob_emu as g
    import polars as pl

    runs = sys.argv[1:]
    recs = {os.path.basename(os.path.normpath(r)): load(r) for r in runs}
    r0 = next(iter(recs.values()))
    cols = r0["cols"]
    for k, z in recs.items():
        assert np.array_equal(z["cols"], cols), f"{k}: different land columns"
    lat_all, lon_all = r0["grid_lat"], r0["grid_lon"]
    clat, clon = lat_all[cols - 1], lon_all[cols - 1]  # Julia 1-based ij
    # the emulated columns and their cells, exactly as Coupler builds them
    st = g.cells().sort("Cell").filter(~pl.col("rock"))
    k, dist = lc.nearest_cells(clat, clon, st["lat"].to_numpy(), st["lon"].to_numpy())
    mask = dist <= 3.0
    cell = st["Cell"].to_numpy()[k[mask]]
    for name, z in recs.items():  # a coupled run's own mapping must be this one
        if "cell" in z:
            assert np.array_equal(z["mask"], mask) and np.array_equal(z["cell"], cell), name
    elat, elon = st["lat"].to_numpy()[k[mask]], st["lon"].to_numpy()[k[mask]]
    lat = clat[mask]
    w0 = np.cos(np.radians(lat))

    rep = {"runs": list(recs), "n_emulated_columns": int(mask.sum())}
    print(f"{mask.sum()} emulated columns; reading reference climates ...", flush=True)
    refs = references(cell, elat, elon)

    def wm(a, w):
        return float(np.sum(a * w) / np.sum(w))

    # 3. mountains
    z_cell = cell_elevation(elat, elon)
    z_speedy = r0["col_orog"][mask]
    dz = z_speedy - z_cell
    w_lf = w0 * r0["daily_means"][mask, LF, :].mean(1)
    rep["mountains"] = {
        "speedy_orography_m": wm(z_speedy, w_lf),
        "cell_elevation_m": wm(z_cell, w_lf),
        "speedy_minus_cell_m": wm(dz, w_lf),
        "abs_diff_m": wm(np.abs(dz), w_lf),
        "lapse_rate_effect_K": wm(-LAPSE * dz, w_lf),
        "by_band_lapse_effect_K": {
            b: wm(-LAPSE * dz * ((np.abs(lat) >= lo) & (np.abs(lat) < hi)), w_lf)
            / max(wm(((np.abs(lat) >= lo) & (np.abs(lat) < hi)).astype(float), w_lf), 1e-12)
            for b, (lo, hi) in BANDS.items()
        },
    }
    rep["references"] = {n: {q: wm(v.mean(1), w_lf) for q, v in R.items()} for n, R in refs.items()}

    rep["by_run"] = {}
    for name, z in recs.items():
        dm = z["daily_means"][mask].astype(np.float64)  # (n, NV, days)
        ny = dm.shape[2] // 365
        D = dm[:, :, : 365 * ny].reshape(dm.shape[0], dm.shape[1], ny, 365)
        S = stats(D[:, TAS], D[:, PR], D[:, RSDS], D[:, LWNET])
        w = w0 * dm[:, LF].mean(1)
        yrs = (
            slice(1, ny) if ny > 1 else slice(0, 1)
        )  # years 2..N (year 1 = spin-up from the start state)
        out = {"years": ny, "per_year": {q: [wm(S[q][:, i], w) for i in range(ny)] for q in S}}
        if dm.shape[1] > ALB:
            out["per_year"].update(
                {
                    "albedo": [wm(D[:, ALB, i].mean(1), w) for i in range(ny)],
                    "sw_absorbed": [
                        wm((D[:, RSDS, i] * (1 - D[:, ALB, i])).mean(1), w) for i in range(ny)
                    ],
                    "sensible_heat": [wm(D[:, SH, i].mean(1), w) for i in range(ny)],
                    "et_mm": [wm(D[:, ET, i].sum(1), w) for i in range(ny)],
                    "soil_temp_top": [wm(D[:, TSOIL, i].mean(1), w) for i in range(ny)],
                    "speedy_snow_mm": [wm(D[:, SNOW, i].mean(1) * 1000, w) for i in range(ny)],
                }
            )
        out["minus_reference_years2toN"] = {
            n: {q: wm(S[q][:, yrs].mean(1) - R[q].mean(1), w) for q in S} for n, R in refs.items()
        }
        out["minus_w5e5_by_band_tas"] = {}
        for b, (lo, hi) in BANDS.items():
            sel = (np.abs(lat) >= lo) & (np.abs(lat) < hi)
            R = refs["W5E5 obs 1985-2014"]
            out["minus_w5e5_by_band_tas"][b] = {
                q: wm((S[q][:, yrs].mean(1) - R[q].mean(1))[sel], w[sel])
                for q in ("tas", "t_warm", "t_cold")
            }
        if "global_daily" in z:
            G = z["global_daily"]  # (5, days)
            gy = G[:, : 365 * (G.shape[1] // 365)].reshape(5, -1, 365).mean(2)
            out["global_per_year"] = {
                q: gy[i].tolist()
                for i, q in enumerate(("tas_all", "tas_land", "tas_ocean", "sst", "sea_ice_frac"))
            }
        out["meta"] = {k2_: str(z[k2_]) for k2_ in ("ocean", "albedo", "rough") if k2_ in z}
        rep["by_run"][name] = out

    path = os.path.join(os.path.dirname(os.path.normpath(runs[0])), "climate_diagnosis.json")
    with open(path, "w") as fh:
        json.dump(rep, fh, indent=1)
    print(json.dumps(rep, indent=1))
    print(f"-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
