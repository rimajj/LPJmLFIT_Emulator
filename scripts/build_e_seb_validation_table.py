#!/usr/bin/env python3
"""build_e_seb_validation_table.py — stage the tower-forced driving table for Component E's P2 validation
(line E, milestone E4, **Experiment A**: the closure ALONE, isolated from F's ET).

WHY Experiment A is the honest test of E: `FToE` hands E `le` ALREADY formed as λ·ET
(`src/components/fast.jl:236`), so **LE is F's number** — E's own predictions are `T_skin`, `H` (the residual)
and `G`. Driving `solve_seb` with the TOWER's forcing *and the tower's own LE* therefore scores E and nothing
else: a miss in H or T_skin is the closure's, not F's ET error. (Experiment B — F's LE feeding E — is the
coupled case; the A−B difference is exactly F's ET error.)

This script writes one plain CSV per site that a pure-Base Julia driver can read with no dependencies
(`scripts/validate_e_seb_vs_plumber2.jl`), taking every quantity from the observations where one exists:

  driving   swdown, lwdown, tair [K], psurf [Pa], wind [m/s]  — the tower's own measurements
  LE input  le_in = `le_cor` where the site has the energy-balance-corrected flux, else `le`
  boundary  albedo   = OBSERVED daily Σ SWup / Σ SWdown over daytime steps (per-site median as the
                       nighttime/gap fallback) — the tower measures albedo, so E need not assume one
            z0m      = 0.1 · canopy_height  (standard rule of thumb; the only unobserved boundary value)
            height   = canopy_height  [m]   from the NetCDF
            z_ref    = reference_height [m] from the NetCDF — the height the forcing was MEASURED at, which
                       must override `SEBParams.z_ref = 10.0` or `g_a` is evaluated at the wrong level
  target    h_obs (`h_cor` where present, else `h`), rn_obs, g_obs, t_skin_obs (OzFlux `LWup` sites only)
  band      h_uc = |`h_cor_uc`| — PLUMBER2's own joint uncertainty, the E4 acceptance band (FLUXNET2015
                       sites only; OzFlux files ship none)
  context   t_soil — the deep-soil reference E's `solve!` maintains as a τ=30 d EWMA of daily-mean Tair,
                       reproduced here so the driver stays a pure function (see the driver's docstring)

ROWS: only steps where every driving field, `le_in` and `h_obs` are finite. Feb 29 is KEPT (this compares
against the tower, not against noleap model output). The time axis is LOCAL STANDARD time (verified in
milestone E1 via the mean-diurnal SWdown peak), so `hour` supports the diurnal test directly.

Env:
  SITES   comma list (default: DE-Hai + the three usable T_skin sites AU-Tum,AU-ASM,AU-Rob)
  YEARS   "<y0>-<y1>" to subset (default: the whole record)
  OUT     output dir (default: <energy_reference>/derived/seb_validation)
Usage:
  /home/jamirp/.conda/envs/py311_new/bin/python3 scripts/build_e_seb_validation_table.py
  SITES=DE-Hai YEARS=2010-2012 python3 scripts/build_e_seb_validation_table.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
# sibling script in this same dir; the path insert above must run first, hence the E402 exemption
from fetch_plumber2_sites import resolve_paths_yaml  # noqa: E402

DEFAULT_SITES = ["DE-Hai", "AU-Tum", "AU-ASM", "AU-Rob"]
TAU_SOIL_DAYS = 30.0  # SEBParams.tau_soil default — keep in step with src/components/energy.jl
DRIVING = ["swdown", "lwdown", "tair", "psurf", "wind"]


def daily_albedo(df: pd.DataFrame) -> pd.Series:
    """Observed albedo per half-hour: the day's daytime Σ SWup / Σ SWdown, broadcast back to its steps.

    Nighttime albedo is undefined (both fluxes ≈ 0), and instantaneous daytime ratios are noisy at low sun,
    so the daily daytime-integrated ratio is the stable estimator. Gaps fall back to the site median.
    """
    day = df["swdown"] > 50.0
    up = df["swup"].where(day)
    dn = df["swdown"].where(day)
    date = df.index.normalize()
    num = up.groupby(date).sum(min_count=1)
    den = dn.groupby(date).sum(min_count=1)
    alb_daily = (num / den).where(den > 0)
    alb_daily = alb_daily.where((alb_daily > 0.02) & (alb_daily < 0.9))  # reject snow-flagged/instrument junk
    med = float(np.nanmedian(alb_daily)) if np.isfinite(alb_daily).any() else 0.15
    return pd.Series(date, index=df.index).map(alb_daily).fillna(med).astype("float64")


def soil_reference_temperature(df: pd.DataFrame) -> pd.Series:
    """E's deep-soil reference: an EWMA of DAILY-MEAN Tair with timescale `tau_soil` days, seeded at day 1.

    `SEBEnergyClosure.solve!` advances `t_soil` once per coupled step with `a = 1/tau_soil`; at half-hourly
    resolution the same recursion per step would decay ~48× too fast, which is exactly the sub-daily τ trap
    recorded in `lines/E/STATE.md`. Advancing once per DAY on the daily mean keeps the intended 30-day memory.
    """
    daily_tair = df["tair"].resample("1D").mean()
    a = 1.0 / TAU_SOIL_DAYS
    out = np.empty(len(daily_tair))
    prev = float(daily_tair.iloc[0])
    for i, t in enumerate(daily_tair.to_numpy()):
        prev = prev if not np.isfinite(t) else (1.0 - a) * prev + a * t
        out[i] = prev
    per_day = pd.Series(out, index=daily_tair.index)
    return pd.Series(df.index.normalize(), index=df.index).map(per_day).astype("float64")


def main() -> int:
    root = Path(resolve_paths_yaml("data.energy_reference"))
    derived = root / "derived"
    manifest = json.loads((root / "manifest.json").read_text())
    out_dir = Path(os.environ.get("OUT") or (derived / "seb_validation"))
    sites = [s.strip() for s in os.environ.get("SITES", "").split(",") if s.strip()] or DEFAULT_SITES
    yspec = os.environ.get("YEARS", "")
    out_dir.mkdir(parents=True, exist_ok=True)

    index: dict[str, dict] = {}
    for site in sites:
        hh = derived / f"halfhourly_{site}.parquet"
        if not hh.exists():
            print(f"[{site}] SKIP — {hh} absent (run scripts/validate_e_plumber2_load.py)")
            continue
        df = pd.read_parquet(hh).set_index("time").sort_index()
        if yspec:
            y0, y1 = (int(t) for t in yspec.split("-"))
            df = df[(df.index.year >= y0) & (df.index.year <= y1)]

        # site geometry straight from the NetCDF (never assumed)
        import netCDF4 as nc

        with nc.Dataset(manifest["sites"][site]["files"]["Flux"]["path"]) as ds:
            h_can = float(np.ravel(ds["canopy_height"][:])[0])
            h_ref = float(np.ravel(ds["reference_height"][:])[0])
            igbp = "".join(
                x.decode() if isinstance(x, bytes) else str(x) for x in np.ravel(ds["IGBP_veg_short"][:])
            ).strip()

        le_col = "le_cor" if "le_cor" in df else "le"
        h_col = "h_cor" if "h_cor" in df else "h"
        out = pd.DataFrame(index=df.index)
        for c in DRIVING:
            out[c] = df[c]
        out["le_in"] = df[le_col]
        out["h_obs"] = df[h_col]
        out["rn_obs"] = df["rn"] if "rn" in df else np.nan
        out["g_obs"] = df["g"] if "g" in df else 0.0
        out["t_skin_obs"] = df["t_skin"] if "t_skin" in df else np.nan
        out["h_uc"] = df["h_cor_uc"].abs() if "h_cor_uc" in df else np.nan
        out["le_uc"] = df["le_cor_uc"].abs() if "le_cor_uc" in df else np.nan
        out["albedo"] = daily_albedo(df) if "swup" in df else 0.15
        out["t_soil"] = soil_reference_temperature(df)
        out["hour"] = df.index.hour + df.index.minute / 60.0
        out["year"] = df.index.year
        out["doy"] = df.index.dayofyear

        # THE TRAP [VERIFIED 2026-07-28]: requiring only `le_in` (= `le_cor`) to be finite is NOT enough.
        # At DE-Hai the UNCORRECTED `le` is all-NaN for 2010–2012 (that is where the site's 23.1 % missing LE
        # sits), and PLUMBER2's energy-balance correction emitted **≈0 instead of a fill value** there
        # (annual mean `le_cor` = 0.39 / −0.09 / 0.04 W/m² vs 30–40 W/m² in 2000–2009), while `h_cor_uc`
        # vanishes. A finiteness test therefore passes on 36 550 rows of garbage, and feeding the closure
        # LE ≈ 0 sends all the available energy into H — it inflated DE-Hai's H bias to +39.8 W/m². So ALSO
        # require the uncorrected `le` (the physical measurement the correction is derived from) to be finite.
        out["le_raw"] = df["le"] if "le" in df else df[le_col]
        need = DRIVING + ["le_in", "le_raw", "h_obs", "albedo", "t_soil"]
        keep = np.isfinite(out[need]).all(axis=1)
        out = out.drop(columns=["le_raw"])
        need = [c for c in need if c != "le_raw"]
        kept = out[keep].copy()
        step_min = int(round((df.index[1] - df.index[0]).total_seconds() / 60))

        dest = out_dir / f"seb_drive_{site}.csv"
        kept.reset_index().rename(columns={"time": "timestamp"}).to_csv(
            dest, index=False, float_format="%.6g"
        )
        meta = {
            "site": site,
            "igbp": igbp,
            "canopy_height_m": h_can,
            "reference_height_m": h_ref,
            "z0m_m": 0.1 * h_can,
            "timestep_min": step_min,
            "le_column": le_col,
            "h_column": h_col,
            "has_t_skin": bool(np.isfinite(kept["t_skin_obs"]).any()),
            "has_uncertainty_band": bool(np.isfinite(kept["h_uc"]).any()),
            "rows": int(len(kept)),
            "rows_dropped_incomplete": int(len(out) - len(kept)),
            "years": [int(kept["year"].min()), int(kept["year"].max())],
            "mean_albedo": round(float(kept["albedo"].mean()), 4),
            "mean_le_in": round(float(kept["le_in"].mean()), 3),
            "mean_h_obs": round(float(kept["h_obs"].mean()), 3),
            "csv": str(dest),
        }
        index[site] = meta
        # Also a flat KEY=VALUE twin, so the pure-Base Julia driver needs no JSON parser (ADR 0014 keeps
        # runtime [deps] empty and this script's consumer is a plain `julia --project=.` driver).
        (out_dir / f"seb_drive_{site}.meta").write_text(
            "".join(
                f"{k}={v if not isinstance(v, list) else '-'.join(str(x) for x in v)}\n"
                for k, v in meta.items()
            )
        )
        print(
            f"[{site}] {igbp} h_can {h_can:.1f} m, z_ref {h_ref:.1f} m, {step_min} min: "
            f"{len(kept)}/{len(out)} rows kept, LE from `{le_col}`, H from `{h_col}`, "
            f"albedo {meta['mean_albedo']}, T_skin {'yes' if meta['has_t_skin'] else 'no'}, "
            f"band {'yes' if meta['has_uncertainty_band'] else 'no'} -> {dest.name}"
        )

    (out_dir / "seb_drive_index.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    print(f"\nindex: {out_dir / 'seb_drive_index.json'}  ({len(index)} site(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
