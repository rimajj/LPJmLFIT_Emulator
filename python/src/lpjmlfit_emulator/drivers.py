"""Parse annual climate drivers and CO2 for the emulator's target cell.

Climate drivers are stored as NetCDF where a single real cell's series is replicated
across many identical "fake" cells; reading a single cell index and aggregating the
sub-annual steps to annual yields the driver series. CO2 is read from a simple
two-column (year, ppm) whitespace-delimited text file. These functions return plain
pandas Series keyed by integer year, ready to be merged into an annual drivers frame.

Provenance: ported once on 2026-07-16 from the frozen sibling emulator module(s)
/p/projects/open/Jamir/emulator/src/parse_drivers.py (newest sibling source mtime
2026-07-14). This repository is the single source of truth for component S; the sibling
is frozen (ADR 0012) — port once, do not sync.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

__all__ = ["DEFAULT_NC_FILES", "load_co2", "annual_from_netcdf"]

#: Sibling short driver name -> (NetCDF filename, sub-annual aggregation).
#: Mirrors the frozen sibling's ``NC_FILES`` mapping (temperature/mean,
#: precipitation/sum, short/long-wave radiation/mean, humidity/mean).
DEFAULT_NC_FILES: dict[str, tuple[str, str]] = {
    "temp": ("temperature_repeated.nc", "mean"),
    "prec": ("precipitation_repeated.nc", "sum"),
    "swrad": ("short_wave_radiation_repeated.nc", "mean"),
    "lwrad": ("long_wave_radiation_repeated.nc", "mean"),
    "humid": ("humid_repeated.nc", "mean"),
}


def load_co2(path: str | Path) -> pd.Series:
    """Load a two-column (year, ppm) whitespace text file into a year-indexed Series.

    Only lines with exactly two whitespace-separated tokens are kept; the first is
    parsed as an ``int`` year and the second as a ``float`` ppm value. Returns a
    ``pandas.Series`` indexed by year (int) named ``"co2_ppm"``.
    """
    rows = []
    for line in Path(path).read_text().splitlines():
        parts = line.split()
        if len(parts) == 2:
            rows.append((int(parts[0]), float(parts[1])))
    return pd.Series({y: v for y, v in rows}, name="co2_ppm")


def annual_from_netcdf(path: str | Path, agg: str = "mean", cell_index: int = 0) -> pd.Series:
    """Aggregate a NetCDF driver's first data variable to an annual, year-indexed Series.

    Opens ``path`` with xarray (times decoded), takes the first data variable, collapses
    every non-time dimension to ``cell_index`` (the replicated cells are identical), then
    aggregates the sub-annual time steps to annual by ``"mean"`` or ``"sum"`` (any value
    other than ``"mean"`` sums, matching the sibling). Returns the annual Series indexed
    by integer year.

    Requires the optional ``xarray`` (and a NetCDF backend such as ``netCDF4``)
    dependency, imported lazily.
    """
    try:
        import xarray as xr
    except ImportError as exc:  # pragma: no cover - exercised only when dep is absent
        raise ImportError(
            "annual_from_netcdf requires the optional 'xarray' dependency (with a "
            "NetCDF backend such as 'netCDF4'); install them, e.g. "
            "`pip install xarray netCDF4`."
        ) from exc

    ds = xr.open_dataset(path, decode_times=True)
    # main data variable = the one with a time dimension
    varname = list(ds.data_vars)[0]
    da = ds[varname]
    # collapse all spatial dims to the chosen cell (all replicates identical)
    spatial = [d for d in da.dims if d.lower() not in ("time",)]
    for d in spatial:
        da = da.isel({d: cell_index})
    # now da is indexed by time only
    df = da.to_series().to_frame("val")
    df["year"] = df.index.year
    if agg == "mean":
        out = df.groupby("year")["val"].mean()
    else:
        out = df.groupby("year")["val"].sum()
    return out
