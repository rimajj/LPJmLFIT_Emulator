"""Feature engineering for the DIRECT (non-recursive) climate -> distribution emulator.

Two pieces live here, both part of component S's feature schema:

* The per-(Cell, Year) climate feature builder ``build_cell_year_feats`` (polars): static
  climatology, current-year climate, anomalies, trailing rolling means, and a 10-yr trailing
  linear-slope trend (a vectorised closed form when the year grid is regular, with a ragged
  per-cell fallback). Features are climate-only (no absolute year) so they transfer across
  scenarios; rolling/trend terms carry the transient/lagged forest response without recursion.
* The per-cell ecological CLIMATOLOGY diagnostics ``eco_diagnostics``: VPD, growing-degree-days,
  Priestley-Taylor PET, P/PET aridity, water-deficit months, dry-spell structure and
  wettest-quarter fraction (13 features, via the external sibling package ``climclusterpy``)
  plus 5 cheap seasonality summaries (cold/warm month, range, monthly precip CV, driest month).

The authoritative feature-name schema is given by the module-level constants (notably ``ECO``
and ``FEATURES``); these are the frozen column contract used by downstream models.

Provenance: ported once on 2026-07-16 from the frozen sibling emulator module(s)
/p/projects/open/Jamir/emulator/src/direct_features.py and
/p/projects/open/Jamir/emulator/src/eco_features.py (newest sibling source mtime 2026-07-14).
This repository is the single source of truth for component S; the sibling is frozen (ADR 0012)
— port once, do not sync.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import polars as pl

__all__ = [
    "TREE_TYPES",
    "CLIM",
    "STATIC",
    "ANOM",
    "ROLL",
    "TREND",
    "ECO",
    "FEATURES",
    "AXES",
    "STATIC_FIXED",
    "NORMAL_COLS",
    "SEASONAL_FEATURES",
    "DAYS_PER_MONTH",
    "DEFAULT_CLIMCLUSTERPY_SRC",
    "build_cell_year_feats",
    "eco_diagnostics",
]

TREE_TYPES = [0, 1, 2, 3, 4, 5, 6]
CLIM = ["temp", "prec", "swrad", "lwrad", "humid"]
STATIC = [
    "lat",
    "soil_code",
    "soil_depth",
    "temp_mean",
    "temp_sd",
    "prec_mean",
    "prec_sd",
    "swrad_mean",
    "swrad_sd",
    "lwrad_mean",
    "lwrad_sd",
    "humid_mean",
    "humid_sd",
]
ANOM = ["temp_anom", "prec_anom", "swrad_anom"]
ROLL = ["temp_r3", "temp_r5", "temp_r10", "prec_r3", "prec_r5", "prec_r10", "swrad_r5"]
TREND = ["temp_trend10", "prec_trend10"]
# Ecologically-motivated climatology diagnostics (from climclusterpy via eco_diagnostics) — the
# per-cell predictability lever (seasonality / water balance / aridity). Static per cell.
ECO = [
    "eco_diag_vpd_mean",
    "eco_diag_vpd_max_monthly",
    "eco_diag_vpd_stress_months",
    "eco_diag_gdd_5",
    "eco_diag_gdd_10",
    "eco_diag_frost_free_days",
    "eco_diag_pet_mean",
    "eco_diag_p_pet_ratio",
    "eco_diag_water_deficit_months",
    "eco_diag_dry_spell_max",
    "eco_diag_dry_spell_mean",
    "eco_diag_precip_intensity_wet_days",
    "eco_diag_precip_wettest_quarter_frac",
    "tas_cold_month",
    "tas_warm_month",
    "tas_range",
    "pr_cv_monthly",
    "pr_driest_month",
]
FEATURES = STATIC + ECO + CLIM + ANOM + ROLL + TREND
AXES = ["logHeight", "Age", "SLA", "Wooddens", "beta_root"]

STATIC_FIXED = ["lat", "soil_code", "soil_depth"]
NORMAL_COLS = [
    "temp_mean",
    "temp_sd",
    "prec_mean",
    "prec_sd",
    "swrad_mean",
    "swrad_sd",
    "lwrad_mean",
    "lwrad_sd",
    "humid_mean",
    "humid_sd",
]

#: Days per calendar month, used to convert mean daily precip to monthly totals.
DAYS_PER_MONTH = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31], float)
#: Extra cheap seasonality summaries (from monthly climatology).
SEASONAL_FEATURES = [
    "tas_cold_month",
    "tas_warm_month",
    "tas_range",
    "pr_cv_monthly",
    "pr_driest_month",
]

#: Default location of the external sibling ``climclusterpy`` package source tree.
DEFAULT_CLIMCLUSTERPY_SRC = "/home/jamirp/scripts/clustering/climclusterpy_package/src"


def build_cell_year_feats(
    static: pl.DataFrame,
    annual: pl.DataFrame,
    eco: pl.DataFrame = None,
    moving_normals: pl.DataFrame = None,
) -> pl.DataFrame:
    """Per (Cell,Year) climate feature row. Rolling/trend computed per cell over sorted years.
    `eco` (optional) = static per-cell eco diagnostics. `moving_normals` (optional, Phase F) =
    per-(Cell,Year) trailing-window normals — if given, the climate-normal features + the anomaly
    baseline become time-varying (so they shift under a changing climate)."""
    a = annual.sort(["Cell", "Year"])
    # anomaly baseline: moving (per Cell,Year) if provided, else static (per Cell)
    if moving_normals is not None:
        a = a.join(
            moving_normals.select(["Cell", "Year", "temp_mean", "prec_mean", "swrad_mean"]),
            on=["Cell", "Year"],
            how="left",
        )
    else:
        a = a.join(
            static.select(["Cell", "temp_mean", "prec_mean", "swrad_mean"]), on="Cell", how="left"
        )
    a = a.with_columns(
        [
            (pl.col("temp") - pl.col("temp_mean")).alias("temp_anom"),
            (pl.col("prec") - pl.col("prec_mean")).alias("prec_anom"),
            (pl.col("swrad") - pl.col("swrad_mean")).alias("swrad_anom"),
        ]
    ).drop(["temp_mean", "prec_mean", "swrad_mean"])
    # trailing rolling means (inclusive of current year), per cell
    a = a.with_columns(
        [
            pl.col("temp").rolling_mean(3, min_samples=1).over("Cell").alias("temp_r3"),
            pl.col("temp").rolling_mean(5, min_samples=1).over("Cell").alias("temp_r5"),
            pl.col("temp").rolling_mean(10, min_samples=1).over("Cell").alias("temp_r10"),
            pl.col("prec").rolling_mean(3, min_samples=1).over("Cell").alias("prec_r3"),
            pl.col("prec").rolling_mean(5, min_samples=1).over("Cell").alias("prec_r5"),
            pl.col("prec").rolling_mean(10, min_samples=1).over("Cell").alias("prec_r10"),
            pl.col("swrad").rolling_mean(5, min_samples=1).over("Cell").alias("swrad_r5"),
        ]
    )
    # 10-yr trailing linear slope. Vectorised across cells when the year grid is regular
    # (all cells share the same complete set of years); closed-form slope (no polyfit).
    ap = a.to_pandas().sort_values(["Cell", "Year"]).reset_index(drop=True)
    _, counts = np.unique(ap["Cell"].values, return_counts=True)
    L = int(counts[0])
    nC = len(counts)
    regular = bool((counts == L).all()) and L >= 2
    if regular:
        for v in ["temp", "prec"]:
            M = ap[v].values.reshape(nC, L)  # (cells, years), year-sorted within cell
            tr = np.zeros_like(M)
            for i in range(L):
                lo = max(0, i - 9)
                x = np.arange(lo, i + 1, dtype=float)
                x -= x.mean()
                if x.shape[0] >= 2:
                    tr[:, i] = (M[:, lo : i + 1] * x).sum(1) / (
                        x * x
                    ).sum()  # slope (y-mean cancels)
            ap[f"{v}_trend10"] = tr.reshape(-1)
    else:  # ragged fallback
        for v in ["temp", "prec"]:
            ap[f"{v}_trend10"] = 0.0
        for _, idx in ap.groupby("Cell").groups.items():
            sub = ap.loc[idx]
            for v in ["temp", "prec"]:
                vals = sub[v].values
                tr = np.zeros(len(vals))
                for i in range(len(vals)):
                    lo = max(0, i - 9)
                    x = np.arange(lo, i + 1, float)
                    x -= x.mean()
                    if len(x) >= 2:
                        tr[i] = (vals[lo : i + 1] * x).sum() / (x * x).sum()
                ap.loc[idx, f"{v}_trend10"] = tr
    a = pl.from_pandas(ap)
    # attach fixed static (lat/soil) + climate normals (moving per-year if given, else per-cell)
    feats = a.join(static.select(["Cell"] + STATIC_FIXED), on="Cell", how="left")
    if moving_normals is not None:
        feats = feats.join(
            moving_normals.select(["Cell", "Year"] + NORMAL_COLS), on=["Cell", "Year"], how="left"
        )
    else:
        feats = feats.join(static.select(["Cell"] + NORMAL_COLS), on="Cell", how="left")
    if eco is not None:
        feats = feats.join(eco.select(["Cell"] + ECO), on="Cell", how="left")
    else:  # eco columns absent — fill 0 so the schema stays stable
        feats = feats.with_columns([pl.lit(0.0).alias(c) for c in ECO])
    return feats.select(["Cell", "Year"] + FEATURES)


def eco_diagnostics(
    grid: pd.DataFrame,
    nc_map: dict,
    ncdir,
    years: tuple[int, int] = (2000, 2019),
    *,
    climclusterpy_src: str = DEFAULT_CLIMCLUSTERPY_SRC,
) -> pl.DataFrame:
    """Per-cell ecological CLIMATOLOGY diagnostics from daily climate NetCDFs.

    Computes the 13 climclusterpy ecological diagnostic features (VPD / GDD / PET / aridity /
    water-deficit / dry-spell / wettest-quarter) plus 5 cheap seasonality summaries over a
    climatological window, returning a polars DataFrame with a ``Cell`` column and one column per
    feature (``ECOLOGY_DIAGNOSTIC_FEATURES`` + ``SEASONAL_FEATURES``). Features are climatological
    normals ⇒ STATIC per cell.

    Parameters
    ----------
    grid:
        pandas DataFrame with ``Cell``, ``lat_idx`` and ``lon_idx`` columns; rows with
        ``Cell < 0`` are dropped (ocean / undefined cells).
    nc_map:
        mapping ``{"tas"|"pr"|"rsds"|"hurs": (filename, variable_name)}`` of daily NetCDF sources.
    ncdir:
        directory containing the NetCDF files named in ``nc_map``.
    years:
        inclusive ``(y0, y1)`` climatology window.
    climclusterpy_src:
        source-tree location of the external sibling ``climclusterpy`` package (prepended to
        ``sys.path`` before import).

    Requires the optional dependencies ``xarray`` (with the ``netCDF4`` backend) and the external
    sibling package ``climclusterpy``; each raises a clear ImportError if missing.
    """
    import sys
    from pathlib import Path

    try:
        import xarray as xr  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - optional dep
        raise ImportError(
            "eco_diagnostics requires xarray to read the daily climate NetCDFs; "
            "install it with `pip install xarray netCDF4`."
        ) from exc
    try:
        import netCDF4  # noqa: F401, PLC0415
    except ImportError as exc:  # pragma: no cover - optional dep
        raise ImportError(
            "eco_diagnostics requires the netCDF4 backend for xarray to read the daily "
            "climate NetCDFs; install it with `pip install netCDF4`."
        ) from exc

    sys.path.insert(0, climclusterpy_src)
    try:
        from climclusterpy.features.ecological_summaries import (  # noqa: PLC0415
            ECOLOGY_DIAGNOSTIC_FEATURES,
            compute_all_ecology_diagnostic_features,
        )
    except ImportError as exc:  # pragma: no cover - optional external sibling dep
        raise ImportError(
            "eco_diagnostics requires the external sibling package 'climclusterpy' "
            f"(expected under {climclusterpy_src!r}); adjust the climclusterpy_src argument "
            "or install the package to make it importable."
        ) from exc

    eco_features = list(ECOLOGY_DIAGNOSTIC_FEATURES) + SEASONAL_FEATURES

    ncdir = Path(ncdir)
    grid = grid[grid["Cell"] >= 0].reset_index(drop=True)
    li, oj = grid["lat_idx"].values, grid["lon_idx"].values
    y0, y1 = years

    def _sel_years(da, y0, y1):
        yrs = da["time"].dt.year
        return da.sel(time=(yrs >= y0) & (yrs <= y1))

    def open_da(key):
        fn, var = nc_map[key]
        ds = xr.open_dataset(ncdir / fn, decode_times=True, chunks={"time": 2000})
        return _sel_years(ds[var], y0, y1)

    tas = open_da("tas")
    tas_m = tas.groupby("time.month").mean("time").compute().values[:, li, oj].T  # (n,12) degC
    pr = open_da("pr")  # mm/day
    pr_m_daily = (
        pr.groupby("time.month").mean("time").compute().values[:, li, oj].T
    )  # (n,12) mm/day
    monthly_P = pr_m_daily * DAYS_PER_MONTH[np.newaxis, :]  # (n,12) mm/month
    pr_mean_annual = pr.mean("time").compute().values[li, oj]  # mm/day
    pr_wetdays_freq = (pr > 1.0).mean("time").compute().values[li, oj]  # fraction
    rsds_mean = open_da("rsds").mean("time").compute().values[li, oj]  # W/m2
    monthly_q = open_da("hurs").mean("time").compute().values[li, oj]  # kg/kg (specific humid)

    feats = compute_all_ecology_diagnostic_features(
        monthly_T=tas_m.astype(np.float32),
        monthly_P=monthly_P.astype(np.float32),
        monthly_q=monthly_q.astype(np.float32),
        rsds_mean=rsds_mean.astype(np.float32),
        pr_wetdays_freq=pr_wetdays_freq.astype(np.float32),
        pr_mean_annual=pr_mean_annual.astype(np.float32),
    )

    # cheap seasonality summaries
    feats["tas_cold_month"] = tas_m.min(1).astype(np.float32)
    feats["tas_warm_month"] = tas_m.max(1).astype(np.float32)
    feats["tas_range"] = (tas_m.max(1) - tas_m.min(1)).astype(np.float32)
    feats["pr_cv_monthly"] = (monthly_P.std(1) / np.maximum(monthly_P.mean(1), 1e-6)).astype(
        np.float32
    )
    feats["pr_driest_month"] = monthly_P.min(1).astype(np.float32)

    df = pd.DataFrame({"Cell": grid["Cell"].values.astype(int)})
    for k in eco_features:
        df[k] = feats[k]
    return pl.from_pandas(df)
