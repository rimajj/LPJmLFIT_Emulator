#!/usr/bin/env python3
"""remap_wind_psurf_cells.py — the two forcings Component E needs and the LPJmL-FIT run never had:
daily **wind** [m/s] and **surface pressure** [Pa], remapped from the obsclim source grid onto the model's
orderA cells (line E, milestone E2).

WHY: the coupled runs currently hold wind CONSTANT and fix psurf (`photosynthesis.c` hard-codes p = 1e5), so
Component E's aerodynamic conductance and its psurf-dependent ρ, γ are driven by placeholders. E4 cannot
honestly score LE/H against a tower while the model is forced with a constant the tower was not.

SOURCE [VERIFIED 2026-07-28] — ISIMIP3a obsclim GSWP3-W5E5, i.e. the **same climate product family the
LPJmL-FIT run itself consumed** (its `*_test.clm` files were built from GSWP3-W5E5 obsclim), so wind/psurf
are physically consistent with the tas/pr/rsds/lwnet/huss the model already sees:
  /p/projects/isimip/isimip/ISIMIP3a/InputData/climate/atmosphere/obsclim/global/daily/historical/
      GSWP3-W5E5/gswp3-w5e5_obsclim_{ps,sfcwind}_global_daily_<y0>_<y1>.nc
  0.5°, lon 720 ascending (−179.75…), lat 360 DESCENDING (89.75…−89.75), `proleptic_gregorian` (leap!),
  `ps` [Pa], `sfcwind` [m s-1], float32, chunked [1, 360, 720].
There is no `ps` among the raw SSP370 GCM files (`hurs huss lwnet pr rsds sfcwind tas tasmax tasmin`) and no
LPJmL-prepared `ps` .clm anywhere on the cluster — this tree is the only obsclim-consistent pressure source.

THE TWO TRAPS THIS SCRIPT EXISTS TO GET RIGHT
  1. **Grid**: the model's orderA cell index is NOT a lat/lon-ordered index (Hainich = 42490 in the global
     orderA grid but 28008 in the repo-default SINGLESITE grid, and raw-GCM cell 42490 is a different place
     entirely). Cell -> (lat, lon) is resolved from the run's `grid.nc` `cellid[lat, lon]`, then matched to
     the source axes by value with an exactness assertion — never by assumed ordering or arithmetic.
  2. **Calendar**: the source is a real (leap) calendar; the model forcing is **noleap-365**. Every 29
     February is DROPPED so that day-of-year 1…365 lines up with the model's `.clm` bands.

Validation built in (the E2 gate — run with CHECK=1, the default):
  (a) **independent-lookup agreement**: the value picked by index arithmetic must equal an `xarray`
      `.sel(lat=…, lon=…, method="nearest")` pick, bit for bit.
  (b) **round-trip on a variable present in BOTH representations**: obsclim `tas` (NetCDF, °C) at the cell's
      lat/lon vs the model-grid `temperature_test.clm` band for the same cell-day. Agreement proves the
      lat/lon <-> orderA-cell mapping, because that `.clm` is what the LPJmL-FIT run actually read.
  (c) **calendar/pipeline agreement for wind**: the LPJmL-prepared noleap `sfcwind_gswp3-w5e5_obsclim_
      1901-2019.nc` (lat 280, leap days already removed) at the same cell-day vs this script's leap-dropped
      series — an independent check of the Feb-29 handling.
  (d) **observational cross-check at Hainich** (needs the PLUMBER2 tables of milestone E1): monthly-mean
      remapped wind/psurf vs the DE-Hai tower. Expect an offset, not equality: 0.5° grid-cell mean elevation
      != tower elevation, so psurf is biased high where the cell mean sits below the tower.

Env:
  CELLS      comma list of <name>=<orderA cell> (default: the 5 biome cells of extract_biome_forcing.py)
  YEARS      "<y0>-<y1>" (default 2010-2019, matching the committed biome_forcing_<name>.csv decade)
  OUT        output dir (default test/testitems/references)
  CHECK      1 = run the validation battery (default 1)
  NO_WRITE   1 = validate/report only
Usage (≈3 min for 5 cells × 10 yr — submit it rather than blocking the login node):
  scripts/sbatch_python.sh E-windps scripts/remap_wind_psurf_cells.py
  CELLS=temperate_hainich=42490 YEARS=2010-2010 NO_WRITE=1 python3 scripts/remap_wind_psurf_cells.py
"""

from __future__ import annotations

import glob
import os
import struct
from pathlib import Path

import netCDF4 as nc
import numpy as np

REPO = Path(__file__).resolve().parents[1]

OBSCLIM = (
    "/p/projects/isimip/isimip/ISIMIP3a/InputData/climate/atmosphere/obsclim/global/daily/"
    "historical/GSWP3-W5E5"
)
# LPJmL-prepared, noleap, lat-280 versions — used only as the independent check (c). No `ps` here.
LPJML_PREPARED = "/p/projects/lpjml/input/historical/ISIMIP3av2/obsclim/GSWP3-W5E5"
# The global run's grid.nc carries the authoritative cellid[lat, lon] (mirrors extract_biome_forcing.py).
GRID_NC = "/p/tmp/jamirp/esm_land_daily/daily_2000_2019_global_c0_67419_seed1/output/grid.nc"
# Model-grid forcing for the round-trip check (paths.yaml lpjml.inputs.historical.tas).
TAS_TEST_CLM = "/p/projects/waldspektrum/priesner/clustering/global/temperature_test.clm"
PLUMBER2_DERIVED = "/p/tmp/jamirp/esm_land_emulator_data/fluxnet_plumber2/derived"

# orderA cells, mirroring scripts/extract_biome_forcing.py::BIOMES (do not diverge — the committed
# biome_forcing_<name>.csv fixtures use exactly these).
BIOME_CELLS = {
    "boreal_siberia": 52059,
    "temperate_hainich": 42490,
    "mediterranean_iberia": 33335,
    "semiarid_sahel": 18371,
    "tropical_amazon": 12045,
}
NDAYYEAR = 365


# ---------------------------------------------------------------------------------------------------
# grid + source access
# ---------------------------------------------------------------------------------------------------
def cell_coords(cells: dict[str, int]) -> dict[str, tuple[float, float]]:
    """orderA cell index -> (lat, lon), from the run's grid.nc `cellid`."""
    out: dict[str, tuple[float, float]] = {}
    with nc.Dataset(GRID_NC) as g:
        cellid = np.asarray(g["cellid"][:])
        lat, lon = np.asarray(g["lat"][:]), np.asarray(g["lon"][:])
        for name, cell in cells.items():
            hit = np.argwhere(cellid == cell)
            if hit.shape[0] != 1:
                raise SystemExit(f"FATAL: cell {cell} ({name}) found {hit.shape[0]}× in grid.nc cellid")
            i, j = int(hit[0, 0]), int(hit[0, 1])
            out[name] = (float(lat[i]), float(lon[j]))
    return out


def axis_index(axis: np.ndarray, target: float, what: str, tol: float = 1e-6) -> int:
    """Index of `target` on a 0.5° axis, asserting an EXACT hit (no silent nearest-neighbour drift)."""
    idx = int(np.argmin(np.abs(axis - target)))
    if abs(float(axis[idx]) - target) > tol:
        raise SystemExit(
            f"FATAL: {what} {target} not on the source axis (nearest {float(axis[idx])}, "
            f"Δ={abs(float(axis[idx]) - target):.4f}) — the grids are not co-registered"
        )
    return idx


def source_file(var: str, year: int) -> str:
    """The decadal obsclim file containing `year` for `var` (ps | sfcwind)."""
    for path in sorted(glob.glob(f"{OBSCLIM}/gswp3-w5e5_obsclim_{var}_global_daily_*.nc")):
        y0, y1 = (int(t) for t in Path(path).stem.split("_")[-2:])
        if y0 <= year <= y1:
            return path
    raise SystemExit(f"FATAL: no obsclim {var} file covers {year} under {OBSCLIM}")


def read_cell_years(var: str, lat: float, lon: float, years: list[int]) -> dict[int, np.ndarray]:
    """Per year, the 365 daily values at (lat, lon) with 29 February DROPPED (noleap alignment).

    Reads one decadal file at a time and slices only the requested years' time window, so a cell costs one
    pass over ~10 years of chunks rather than one per year.
    """
    out: dict[int, np.ndarray] = {}
    by_file: dict[str, list[int]] = {}
    for y in years:
        by_file.setdefault(source_file(var, y), []).append(y)
    for path, ys in by_file.items():
        with nc.Dataset(path) as d:
            ilat = axis_index(np.asarray(d["lat"][:]), lat, f"{var} lat")
            ilon = axis_index(np.asarray(d["lon"][:]), lon, f"{var} lon")
            tvar = d["time"]
            dates = nc.num2date(
                tvar[:], tvar.units, getattr(tvar, "calendar", "proleptic_gregorian")
            )
            yr = np.array([dt.year for dt in dates])
            mo = np.array([dt.month for dt in dates])
            dy = np.array([dt.day for dt in dates])
            sel = np.isin(yr, ys)
            t0, t1 = int(np.argmax(sel)), int(len(sel) - np.argmax(sel[::-1]))
            block = np.asarray(d[var][t0:t1, ilat, ilon], dtype="float64")
            yb, mb, db = yr[t0:t1], mo[t0:t1], dy[t0:t1]
            keep = ~((mb == 2) & (db == 29))
            for y in ys:
                vals = block[keep & (yb == y)]
                if vals.size != NDAYYEAR:
                    raise SystemExit(
                        f"FATAL: {var} {y} gave {vals.size} days after dropping 29 Feb (expected 365)"
                    )
                out[y] = vals
    return out


# ---------------------------------------------------------------------------------------------------
# validation battery (the E2 gate)
# ---------------------------------------------------------------------------------------------------
def read_test_clm_year(path: str, cell: int, year: int) -> np.ndarray:
    """One cell-year of a model-grid daily `_test.clm` (header-driven; v3 float32 or v2 int16·scalar).

    Mirrors scripts/build_transient_boundary.py::open_clm — parse the header, never assume the layout.
    """
    with open(path, "rb") as f:
        raw = f.read(64)
    if raw[:7] != b"LPJCLIM":
        raise SystemExit(f"FATAL: {path} is not an LPJCLIM file")
    version, order, firstyear, _nyear, _firstcell, ncell, nbands = struct.unpack("<7i", raw[7:35])
    if order != 1:
        raise SystemExit(f"FATAL: {path} order={order} (expected 1 = YEARCELL)")
    scalar = struct.unpack("<f", raw[39:43])[0]
    if version >= 3:
        # LPJmL datatype codes are 0-BASED: 0=byte 1=short 2=int 3=FLOAT 4=double (build_transient_boundary
        # .py::_DT). Off-by-one here reads temperature_test.clm's float32 as int32 and yields ~5.9e8 "°C".
        hdr, dt = 51, {0: "<i1", 1: "<i2", 2: "<i4", 3: "<f4", 4: "<f8"}[
            struct.unpack("<i", raw[47:51])[0]
        ]
    else:
        hdr, dt = 43, "<i2"
    isize = np.dtype(dt).itemsize
    off = hdr + (((year - firstyear) * ncell + cell) * nbands) * isize
    with open(path, "rb") as f:
        f.seek(off)
        buf = f.read(nbands * isize)
    return np.frombuffer(buf, dtype=dt).astype("float64") * scalar


def check_independent_lookup(var: str, lat: float, lon: float, year: int, mine: np.ndarray) -> str:
    """(a) index arithmetic vs an xarray label-based `.sel` — must agree exactly."""
    try:
        import xarray as xr
    except ImportError:  # pragma: no cover - xarray is present in py311_new
        return "SKIP (xarray unavailable)"
    with xr.open_dataset(source_file(var, year), decode_times=True, use_cftime=True) as ds:
        pt = ds[var].sel(lat=lat, lon=lon, method="nearest")
        stamps = pt["time"].values
        keep = np.array([not (t.month == 2 and t.day == 29) and t.year == year for t in stamps])
        theirs = np.asarray(pt.values[keep], dtype="float64")
    if theirs.size != mine.size:
        return f"FAIL (n {theirs.size} vs {mine.size})"
    dmax = float(np.nanmax(np.abs(theirs - mine)))
    return f"{'PASS' if dmax == 0.0 else 'FAIL'} (max|Δ| = {dmax:g})"


def check_tas_roundtrip(cell: int, lat: float, lon: float, year: int) -> str:
    """(b) obsclim `tas` NetCDF at (lat, lon) vs the model-grid `temperature_test.clm` — proves the mapping."""
    from_clm = read_test_clm_year(TAS_TEST_CLM, cell, year)
    with nc.Dataset(f"{LPJML_PREPARED}/tas_gswp3-w5e5_obsclim_1901-2019.nc") as d:
        ilat = axis_index(np.asarray(d["lat"][:]), lat, "tas lat")
        ilon = axis_index(np.asarray(d["lon"][:]), lon, "tas lon")
        t0 = (year - 1901) * NDAYYEAR  # this file is already noleap-365
        from_nc = np.asarray(d["temp"][t0 : t0 + NDAYYEAR, ilat, ilon], dtype="float64")
    dmax = float(np.nanmax(np.abs(from_nc - from_clm)))
    return (
        f"{'PASS' if dmax < 1e-3 else 'FAIL'} (max|Δ| = {dmax:.3e} °C over {NDAYYEAR} days; "
        f"clm mean {from_clm.mean():.3f} vs nc mean {from_nc.mean():.3f} °C)"
    )


def check_wind_pipeline(lat: float, lon: float, year: int, mine: np.ndarray) -> str:
    """(c) the LPJmL-prepared NOLEAP sfcwind .nc vs this script's leap-dropped series."""
    with nc.Dataset(f"{LPJML_PREPARED}/sfcwind_gswp3-w5e5_obsclim_1901-2019.nc") as d:
        ilat = axis_index(np.asarray(d["lat"][:]), lat, "sfcwind lat")
        ilon = axis_index(np.asarray(d["lon"][:]), lon, "sfcwind lon")
        t0 = (year - 1901) * NDAYYEAR
        theirs = np.asarray(d["windspeed"][t0 : t0 + NDAYYEAR, ilat, ilon], dtype="float64")
    dmax = float(np.nanmax(np.abs(theirs - mine)))
    # [VERIFIED 2026-07-28] the LPJmL-PREPARED wind is QUANTIZED to 0.01 m/s (its values are exact multiples
    # of 0.01; the .clm twin is int16·0.01), so the raw difference can only be bounded by half a step. The
    # equality test is therefore against `mine` rounded to the same grid.
    dquant = float(np.nanmax(np.abs(theirs - np.round(mine, 2))))
    return (
        f"{'PASS' if dquant < 1e-4 else 'FAIL'} (max|Δ| after matching the prepared file's 0.01 m/s "
        f"quantization = {dquant:.3e}; raw max|Δ| = {dmax:.3e} ≤ ½ step; prepared mean {theirs.mean():.4f} "
        f"vs remapped mean {mine.mean():.4f} m/s)"
    )


def check_vs_plumber2(wind: dict[int, np.ndarray], psurf: dict[int, np.ndarray]) -> list[str]:
    """(d) Hainich grid cell vs the DE-Hai tower (PLUMBER2, milestone E1). An OFFSET is expected, not equality."""
    path = f"{PLUMBER2_DERIVED}/daily_DE-Hai.parquet"
    if not os.path.exists(path):
        return [f"SKIP — {path} absent (run scripts/validate_e_plumber2_load.py)"]
    import pandas as pd

    obs = pd.read_parquet(path, columns=["date", "wind", "psurf"])
    obs["year"] = pd.to_datetime(obs["date"]).dt.year
    shared = sorted(set(obs["year"]) & set(wind))
    if not shared:
        return [f"SKIP — no overlap between the tower record {obs['year'].min()}–{obs['year'].max()} "
                f"and the requested years {min(wind)}–{max(wind)}"]
    o = obs[obs["year"].isin(shared)]
    mw = float(np.mean([wind[y].mean() for y in shared]))
    mp = float(np.mean([psurf[y].mean() for y in shared]))
    ow, op = float(o["wind"].mean()), float(o["psurf"].mean())
    # ~8.4 km scale height near the surface: convert the pressure offset into an apparent elevation offset.
    dz = 8400.0 * np.log(mp / op) if op > 0 else float("nan")
    return [
        f"years {shared[0]}–{shared[-1]}: wind grid {mw:.3f} vs tower {ow:.3f} m/s (Δ {mw - ow:+.3f}, "
        f"{100 * (mw - ow) / ow:+.1f} %)",
        f"years {shared[0]}–{shared[-1]}: psurf grid {mp:.1f} vs tower {op:.1f} Pa (Δ {mp - op:+.1f} "
        f"⇒ the grid cell sits ≈{dz:+.0f} m below the tower's 430 m — expected for a 0.5° cell mean)",
    ]


# ---------------------------------------------------------------------------------------------------
def main() -> int:
    spec = os.environ.get("CELLS", "")
    cells = (
        {p.split("=")[0]: int(p.split("=")[1]) for p in spec.split(",") if p.strip()}
        if spec
        else dict(BIOME_CELLS)
    )
    y0, y1 = (int(t) for t in os.environ.get("YEARS", "2010-2019").split("-"))
    years = list(range(y0, y1 + 1))
    out_dir = Path(os.environ.get("OUT") or (REPO / "test/testitems/references"))
    do_check = os.environ.get("CHECK", "1") == "1"
    no_write = os.environ.get("NO_WRITE", "0") == "1"

    coords = cell_coords(cells)
    print(f"obsclim GSWP3-W5E5 -> orderA cells | years {y0}–{y1} | out {out_dir}")
    for name, cell in cells.items():
        lat, lon = coords[name]
        print(f"\n[{name}] orderA cell {cell} -> lat {lat} lon {lon}")
        wind = read_cell_years("sfcwind", lat, lon, years)
        psurf = read_cell_years("ps", lat, lon, years)
        wm = np.concatenate([wind[y] for y in years])
        pm = np.concatenate([psurf[y] for y in years])
        print(
            f"  wind  [m/s]: mean {wm.mean():6.3f}  min {wm.min():6.3f}  max {wm.max():6.3f}\n"
            f"  psurf [Pa ]: mean {pm.mean():9.1f}  min {pm.min():9.1f}  max {pm.max():9.1f}"
        )
        if not (0.0 <= wm.min() and wm.max() < 45.0):
            raise SystemExit(f"FATAL: {name} wind out of physical range")
        if not (5.0e4 <= pm.min() and pm.max() <= 1.07e5):
            raise SystemExit(f"FATAL: {name} psurf out of physical range — check units")

        if do_check:
            yc = years[0]
            print(f"  (a) independent lookup  sfcwind {yc}: {check_independent_lookup('sfcwind', lat, lon, yc, wind[yc])}")
            print(f"  (a) independent lookup  ps      {yc}: {check_independent_lookup('ps', lat, lon, yc, psurf[yc])}")
            print(f"  (b) tas round-trip nc vs _test.clm  : {check_tas_roundtrip(cell, lat, lon, yc)}")
            print(f"  (c) noleap wind pipeline agreement  : {check_wind_pipeline(lat, lon, yc, wind[yc])}")
            if name == "temperate_hainich":
                for line in check_vs_plumber2(wind, psurf):
                    print(f"  (d) vs PLUMBER2 DE-Hai tower        : {line}")

        if not no_write:
            out_dir.mkdir(parents=True, exist_ok=True)
            dest = out_dir / f"wind_psurf_{name}.csv"
            with dest.open("w") as f:
                f.write("year,doy,wind,psurf\n")
                for y in years:
                    for d0 in range(NDAYYEAR):
                        f.write(f"{y},{d0 + 1},{wind[y][d0]:.4f},{psurf[y][d0]:.1f}\n")
            print(f"  written {dest} ({len(years) * NDAYYEAR} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
