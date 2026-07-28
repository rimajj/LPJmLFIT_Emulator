#!/usr/bin/env python3
"""validate_e_plumber2_load.py — load the PLUMBER2 reference sites for Component E and emit the
first-look sanity report (the E1 gate: half-hourly LE / H / Rn / T_skin loaded, unit-checked, summarized).

Reads what `fetch_plumber2_sites.py` staged (`manifest.json` next to the data) and produces, per site:
  1. site metadata straight out of the NetCDF (lat/lon/elevation/canopy + reference height/IGBP class),
  2. coverage (% finite) and the PLUMBER2 QC-flag composition (0 measured … 5 statistical gapfill),
  3. unit/range checks against physically admissible bounds — the "don't assume units" guardrail,
  4. the observed surface energy budget: means of Rn / LE / H / G, the closure residual under BOTH Qg sign
     conventions, and the OLS slope of (LE + H) vs (Rn − G) — the standard closure diagnostic,
  5. Bowen ratio (daytime, whole-record and warm-season) — the emergent quantity the 5-biome coupled test
     already orders across biomes (`test/testitems/biome_coupled_tests.jl`),
  6. a falsifiable check of the time axis: the mean-diurnal `SWdown` peak hour (PLUMBER2 carries no tz
     attribute; if the peak sits at 11–13 h the axis is LOCAL STANDARD time, which is what a diurnal
     comparison needs),
  7. T_skin where derivable, i.e. only where `LWup` exists (OzFlux-sourced sites — see below), inverted
     EMISSIVITY-CONSISTENTLY with `SEBParams.emissivity = 0.97`:
         T_skin = [ (LWup − (1−ε)·LWdown) / (ε·σ) ]^(1/4)
     which is the exact inverse of the closure's own longwave term, so `Rn_lw = ε·LWdown − ε·σ·T_skin⁴`
     equals the measured `LWdown − LWup` by construction (`src/components/energy.jl:131,156`). The ε = 1
     brightness temperature is reported alongside to expose the emissivity sensitivity.

[VERIFIED 2026-07-28] **PLUMBER2's FLUXNET2015- and LaThuile-sourced files carry NO upwelling longwave**,
so T_skin is NOT observable at DE-Hai from this dataset; the OzFlux-sourced files DO carry `LWup`. Hence the
staged site set pairs each biome slot with an OzFlux site where possible (ADR 0070). GF-Guy additionally
lacks `Qg`/`Qle_cor`/`Qh_cor` ⇒ no closure residual there.

CALENDAR CAVEAT for later model comparison: PLUMBER2 is a real (leap) calendar; the LPJmL-FIT / F_diff
forcing is noleap-365. Drop 29 February from the daily table before pairing with model output.

Outputs (under <root>/derived/, root from the manifest):
  halfhourly_<site>.parquet   the tidy half-hourly frame (model-facing names + qc columns)
  daily_<site>.parquet        daily means (fluxes, W/m²), precip sum (mm/day), Tair mean/min/max, counts
  diurnal_<site>.parquet      mean diurnal cycle per (month, half-hour-of-day) — the sub-daily signal kept
  site_summary.csv            one row per site: the report's headline numbers
  plumber2_sanity_report.txt  the full text report (also printed)

Env:
  SITES   comma-separated site ids (default: every site in the manifest)
  ROOT    data root (default: manifest `root`, else config/paths.yaml `data.energy_reference`)
  OUT     derived-output dir (default: <ROOT>/derived)
  NO_WRITE 1 = report only, write nothing
Usage:
  /home/jamirp/.conda/envs/py311_new/bin/python3 scripts/validate_e_plumber2_load.py
  SITES=DE-Hai NO_WRITE=1 python3 scripts/validate_e_plumber2_load.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import netCDF4 as nc
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_plumber2_sites import resolve_paths_yaml  # noqa: E402  (sibling script, same dir)

SIGMA = 5.670374419e-8  # Stefan-Boltzmann, W/m²/K⁴ (matches SEBParams.sigma)
EMISSIVITY = 0.97  # SEBParams.emissivity default — keep the inversion consistent with the closure

# PLUMBER2 name -> (model-facing name, unit, admissible range). Ranges are deliberately generous: they
# exist to catch a UNIT error (K vs °C, Pa vs hPa, kg/m²/s vs mm/h, W/m² vs MJ/m²/30min), not an unusual
# site. Where a band admits values that are strictly unphysical, the comment says why (a documented
# instrument/processing artifact of this dataset) so it stays an explicit acceptance, not a silent pass.
FLUX_VARS = {
    # Half-hourly eddy-covariance extremes: dewfall/advection drive LE to ≈ −235 W/m² and LE to ≈ 1090
    # W/m² occurs at AU-How under warm dry advection. Both are real samples, not unit slips.
    "Qle": ("le", "W/m2", (-250.0, 1200.0)),
    "Qle_cor": ("le_cor", "W/m2", (-250.0, 1200.0)),
    "Qh": ("h", "W/m2", (-350.0, 900.0)),
    "Qh_cor": ("h_cor", "W/m2", (-350.0, 900.0)),
    "Rnet": ("rn", "W/m2", (-300.0, 1100.0)),
    "Qg": ("g", "W/m2", (-400.0, 400.0)),
    # Radiometer zero offsets make a few W/m² of NEGATIVE nighttime up-welling shortwave instrumental,
    # not a unit error — hence the -10 W/m² floor rather than 0 (DE-Hai: 813 samples, min -3.4 W/m²).
    "SWup": ("swup", "W/m2", (-10.0, 700.0)),
    "LWup": ("lwup", "W/m2", (100.0, 800.0)),
    # OzFlux ships a small number of NEGATIVE friction velocities (AU-ASM: 625/122736, min −0.26 m/s) —
    # unphysical processing artifacts. Admitted here so they are counted, but any u*-based aerodynamic
    # check (E's g_a) must drop u* <= 0.
    "Ustar": ("ustar", "m/s", (-1.0, 5.0)),
    # The joint observational uncertainties PLUMBER2 ships with the EB-corrected fluxes: these ARE the
    # "PLUMBER2 error bands" the P2 gate (E4) has to validate LE / H against. A few are negative
    # (FI-Hyy min −28 W/m²) — use |uc| when forming a band.
    "Qle_cor_uc": ("le_cor_uc", "W/m2", (-50.0, 500.0)),
    "Qh_cor_uc": ("h_cor_uc", "W/m2", (-50.0, 500.0)),
    # Carbon fluxes are carried for CONTEXT only (E consumes none of them). The nighttime-partitioning
    # step makes half-hourly GPP go negative (to ≈ −48 µmol/m²/s) and NEE spike (AU-Rob to −110) — dataset
    # artifacts, admitted so they are counted rather than masking a unit error.
    "NEE": ("nee", "umol/m2/s", (-120.0, 80.0)),
    "GPP": ("gpp", "umol/m2/s", (-60.0, 100.0)),
}
MET_VARS = {
    "Tair": ("tair", "K", (200.0, 335.0)),
    "SWdown": ("swdown", "W/m2", (-10.0, 1400.0)),
    "LWdown": ("lwdown", "W/m2", (80.0, 600.0)),
    # Floor at 0: FI-Hyy's cold-dry tail reaches 4.7e-8 kg/kg. The 0.045 ceiling still catches a g/kg mix-up.
    "Qair": ("qair", "kg/kg", (0.0, 0.045)),
    "Psurf": ("psurf", "Pa", (5.0e4, 1.07e5)),
    "Wind": ("wind", "m/s", (0.0, 45.0)),
    # 0.05 kg/m²/s = 180 mm/h; AU-Rob (tropical Queensland) peaks at 0.028 = 100 mm/h in a 30-min burst.
    "Precip": ("precip", "kg/m2/s", (0.0, 0.05)),
    "VPD": ("vpd", "hPa", (0.0, 100.0)),
    # NEAR-SURFACE (in/near-canopy) CO₂, not the free-troposphere mixing ratio: nocturnal build-up under a
    # stable layer routinely exceeds 600 ppm, and AU-ASM's median is 650 ppm (suspicious — do not use that
    # site's CO₂ for anything quantitative). E does not consume CO₂; this is carried for context only.
    "CO2air": ("co2air", "ppm", (250.0, 1500.0)),
    "LAI": ("lai", "1", (0.0, 12.0)),
}
QC_LABELS = {
    0: "measured",
    1: "gapfill_good",
    2: "gapfill_medium",
    3: "gapfill_poor",
    4: "gapfill_erainterim",
    5: "gapfill_statistical",
    101: "post_processed",
}
# The variables whose presence the E-line reference contract requires (DESIGN.md §energy reference).
REQUIRED = ["le", "h", "rn", "swdown", "lwdown", "tair", "qair", "wind", "psurf", "precip"]


def _scalar(ds: nc.Dataset, name: str) -> float | None:
    if name not in ds.variables:
        return None
    return float(np.ravel(ds[name][:])[0])


def _text(ds: nc.Dataset, name: str) -> str:
    if name not in ds.variables:
        return ""
    raw = ds[name][:]
    return "".join(x.decode() if isinstance(x, bytes) else str(x) for x in np.ravel(raw)).strip()


def _series(ds: nc.Dataset, name: str) -> np.ndarray:
    """Read a (time, y, x) variable as a 1-D float64 series with `_FillValue` -> NaN.

    GOTCHA [VERIFIED 2026-07-28]: every PLUMBER2 variable declares `_FillValue = -9999.0` and netCDF4
    returns a MASKED array — but `np.asarray(masked)` silently drops the mask and hands back the raw
    -9999 fill. That poisons every mean (DE-Hai LE came out at −2283 W/m²). `np.ma.filled(..., nan)` is
    the fix; never `np.asarray` a PLUMBER2 variable.
    """
    raw = ds[name][:]
    arr = np.ma.filled(np.ma.asarray(raw).astype("float64"), np.nan)
    return arr.reshape(len(ds.dimensions["time"]), -1)[:, 0]


def load_site(entry: dict) -> tuple[pd.DataFrame, dict]:
    """Return (half-hourly frame indexed by timestamp, metadata dict) for one manifest site entry."""
    frames: dict[str, np.ndarray] = {}
    meta: dict = {"biome_slot": entry["biome_slot"], "note": entry["note"], "stem": entry["stem"]}
    index = None
    for kind, table in (("Flux", FLUX_VARS), ("Met", MET_VARS)):
        ds = nc.Dataset(entry["files"][kind]["path"])
        try:
            tvar = ds["time"]
            origin = tvar.units.split("since", 1)[1].strip()
            stamps = pd.to_datetime(origin) + pd.to_timedelta(np.asarray(tvar[:], dtype="int64"), "s")
            if index is None:
                index = stamps
                meta.update(
                    site_code=getattr(ds, "site_code", "?"),
                    site_name=getattr(ds, "site_name", "?"),
                    country=getattr(ds, "country", "?"),
                    lat=_scalar(ds, "latitude"),
                    lon=_scalar(ds, "longitude"),
                    elevation_m=_scalar(ds, "elevation"),
                    canopy_height_m=_scalar(ds, "canopy_height"),
                    reference_height_m=_scalar(ds, "reference_height"),
                    igbp=_text(ds, "IGBP_veg_short"),
                    igbp_long=_text(ds, "IGBP_veg_long"),
                    n_halfhours=len(stamps),
                    time_units=tvar.units,
                    source=getattr(ds, "source", "")[:60],
                )
            elif not stamps.equals(index):
                raise ValueError(f"{entry['stem']}: Flux and Met time axes differ")
            for src, (dst, _unit, _rng) in table.items():
                if src in ds.variables:
                    frames[dst] = _series(ds, src)
                qc = f"{src}_qc"
                if qc in ds.variables:
                    frames[f"{dst}_qc"] = _series(ds, qc)
        finally:
            ds.close()
    df = pd.DataFrame(frames, index=pd.DatetimeIndex(index, name="time"))
    step = np.diff(df.index.values[:3]).astype("timedelta64[m]").astype(int)
    meta["timestep_min"] = int(step[0]) if len(step) else -1
    return df, meta


def qc_composition(df: pd.DataFrame, col: str) -> str:
    """QC-flag composition over the PRESENT samples, plus what the missing samples are flagged as.

    [VERIFIED 2026-07-28] At DE-Hai every `Qle_qc == 5` row is exactly a `_FillValue` row (52 608 of
    52 608) and matches the variable's own `Missing_%: 23.1` attribute — i.e. in the PLUMBER2 *Flux*
    (evaluation) files a flag of 5 marks data that was left MISSING, not data that was filled. Reporting
    the composition over present samples only, with the missing fraction called out, keeps that honest.
    """
    qc = f"{col}_qc"
    if qc not in df:
        return "no qc variable"
    present = np.isfinite(df[col])
    vals = df[qc][present].dropna().astype(int)
    if vals.empty:
        return "qc all-NaN"
    frac = vals.value_counts(normalize=True).sort_index()
    text = "  ".join(f"{QC_LABELS.get(int(k), f'flag{int(k)}')}={100 * v:.1f}%" for k, v in frac.items())
    n_missing = int((~present).sum())
    if n_missing:
        flags = sorted({int(v) for v in df[qc][~present].dropna()})
        text += f"   | MISSING={100 * n_missing / len(df):.1f}% (flagged {flags})"
    return text


def ols_slope(x: np.ndarray, y: np.ndarray) -> tuple[float, float, int]:
    """Return (slope, intercept, n) of y on x over jointly-finite samples."""
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 10:
        return (np.nan, np.nan, int(ok.sum()))
    a, b = np.polyfit(x[ok], y[ok], 1)
    return (float(a), float(b), int(ok.sum()))


def skin_temperature(df: pd.DataFrame, emissivity: float) -> pd.Series:
    """Invert the closure's own longwave term: LWup = ε·σ·Ts⁴ + (1−ε)·LWdown."""
    emitted = df["lwup"] - (1.0 - emissivity) * df["lwdown"]
    return np.power(np.clip(emitted, 1.0, None) / (emissivity * SIGMA), 0.25)


def report_site(site: str, df: pd.DataFrame, meta: dict, out: list[str]) -> dict:
    row: dict = {"site": site, "biome_slot": meta["biome_slot"], "igbp": meta["igbp"]}
    add = out.append
    add("")
    add("=" * 100)
    add(f"{site} — {meta['site_name']}, {meta['country']}  [{meta['igbp']} — {meta['igbp_long']}]")
    add(f"  biome slot (biome_coupled_tests.jl): {meta['biome_slot']}   |   {meta['note']}")
    add(
        f"  lat {meta['lat']:.4f}  lon {meta['lon']:.4f}  elev {meta['elevation_m']:.0f} m  "
        f"canopy {meta['canopy_height_m']:.1f} m  flux ref height {meta['reference_height_m']:.1f} m"
    )
    add(
        f"  {meta['n_halfhours']} steps of {meta['timestep_min']} min  "
        f"({df.index[0]:%Y-%m-%d %H:%M} … {df.index[-1]:%Y-%m-%d %H:%M}, "
        f"{df.index[-1].year - df.index[0].year + 1} calendar years)"
    )
    row.update(
        lat=meta["lat"], lon=meta["lon"], elevation_m=meta["elevation_m"],
        canopy_height_m=meta["canopy_height_m"], reference_height_m=meta["reference_height_m"],
        years=f"{df.index[0].year}-{df.index[-1].year}", n_halfhours=meta["n_halfhours"],
        timestep_min=meta["timestep_min"],
    )

    # ---- 1. required-variable presence -------------------------------------------------------
    missing = [v for v in REQUIRED if v not in df]
    add(f"  required vars present: {len(REQUIRED) - len(missing)}/{len(REQUIRED)}" + (f"   MISSING: {missing}" if missing else "   (all)"))
    row["missing_required"] = ",".join(missing)
    row["has_lwup"] = "lwup" in df
    row["has_g"] = "g" in df

    # ---- 2/3. coverage, QC composition, unit/range checks -------------------------------------
    add("")
    add(f"  {'variable':10s} {'unit':10s} {'%finite':>8s} {'min':>10s} {'mean':>10s} {'max':>10s}  range-check / QC")
    units = {d: u for _s, (d, u, _r) in {**FLUX_VARS, **MET_VARS}.items()}
    ranges = {d: r for _s, (d, _u, r) in {**FLUX_VARS, **MET_VARS}.items()}
    fails: list[str] = []
    warns: list[str] = []
    for col in [c for c in df.columns if not c.endswith("_qc")]:
        s = df[col]
        lo, hi = ranges[col]
        n_fin = int(np.isfinite(s).sum())
        finite = 100.0 * n_fin / len(s)
        vmin, vmean, vmax = float(s.min()), float(s.mean()), float(s.max())
        bad = np.isfinite(s) & ((s < lo) | (s > hi))
        n_bad = int(bad.sum())
        if n_bad == 0:
            verdict = "OK"
        else:
            # A handful of physically-impossible samples is a known tower artifact, not a unit error;
            # a systematic excursion (>0.1% of the finite record) means the units are wrong -> FAIL.
            frac = n_bad / max(n_fin, 1)
            worst = np.sort(s[bad].to_numpy())[: min(4, n_bad)]
            tag = "WARN-outliers" if frac <= 1e-3 else "FAIL-out-of-range"
            verdict = f"{tag} {n_bad} ({frac * 100:.4f}% of finite; band {lo}…{hi}; e.g. {np.round(worst, 2)})"
            (warns if tag.startswith("WARN") else fails).append(f"{col}:{n_bad}")
        add(
            f"  {col:10s} {units[col]:10s} {finite:8.2f} {vmin:10.3f} {vmean:10.3f} {vmax:10.3f}  "
            f"{verdict}"
        )
        if col in ("le", "h", "rn", "g", "tair", "swdown", "lwdown", "precip", "wind", "psurf", "qair", "lwup"):
            add(f"  {'':32s} qc: {qc_composition(df, col)}")
        row[f"cov_{col}"] = round(finite, 3)
        row[f"mean_{col}"] = round(vmean, 4)
    row["range_failures"] = ",".join(fails)
    row["range_warnings"] = ",".join(warns)
    add(
        "  RANGE CHECK: "
        + ("PASS — every variable inside its admissible band" if not fails and not warns else "")
        + (f"PASS with outlier WARNings {warns}" if warns and not fails else "")
        + (f"FAIL {fails}" if fails else "")
    )

    # ---- 4. observed surface energy budget (jointly-valid half-hours only) --------------------
    add("")
    rn, le, h = df.get("rn"), df.get("le"), df.get("h")
    if rn is not None and le is not None and h is not None:
        g = df["g"] if "g" in df else pd.Series(0.0, index=df.index)
        ok = np.isfinite(rn) & np.isfinite(le) & np.isfinite(h) & np.isfinite(g)
        n_ok = int(ok.sum())
        add(
            f"  jointly-valid Rn/LE/H{'/G' if 'g' in df else ''} half-hours: {n_ok} "
            f"({100.0 * n_ok / len(df):.1f}% of the record)"
            + ("" if "g" in df else "   (no Qg at this site → treated as 0)")
        )
        rn_o, le_o, h_o, g_o = rn[ok], le[ok], h[ok], g[ok]
        res_down = float((rn_o - (le_o + h_o + g_o)).mean())  # Qg positive INTO the ground (ALMA)
        res_up = float((rn_o - (le_o + h_o - g_o)).mean())  # Qg positive out of the ground
        slope, icept, n = ols_slope((rn_o - g_o).to_numpy(), (le_o + h_o).to_numpy())
        add(
            f"  energy budget [W/m²]: Rn={rn_o.mean():7.2f}  LE={le_o.mean():7.2f}  H={h_o.mean():7.2f}  "
            f"G={g_o.mean():6.2f}"
        )
        add(
            f"    residual Rn−(LE+H+G) = {res_down:+7.3f}   Rn−(LE+H−G) = {res_up:+7.3f}   "
            f"⇒ Qg sign convention: {'positive INTO ground' if abs(res_down) <= abs(res_up) else 'positive OUT OF ground'}"
        )
        add(f"    closure slope (LE+H) vs (Rn−G): {slope:.3f}  intercept {icept:+.2f} W/m²  (n={n})")
        row.update(
            n_joint_valid=n_ok, mean_rn=round(float(rn_o.mean()), 3), mean_le=round(float(le_o.mean()), 3),
            mean_h=round(float(h_o.mean()), 3), mean_g=round(float(g_o.mean()), 3),
            residual_qg_down=round(res_down, 4), residual_qg_up=round(res_up, 4),
            closure_slope=round(slope, 4), closure_intercept=round(icept, 3),
        )
        if "le_cor" in df and "h_cor" in df:
            ok_c = ok & np.isfinite(df["le_cor"]) & np.isfinite(df["h_cor"])
            slope_c, icept_c, n_c = ols_slope(
                (rn - g)[ok_c].to_numpy(), (df["le_cor"] + df["h_cor"])[ok_c].to_numpy()
            )
            add(f"    closure slope with the EB-corrected fluxes: {slope_c:.3f} (intercept {icept_c:+.2f}, n={n_c})")
            row["closure_slope_cor"] = round(slope_c, 4)
        if "le_cor_uc" in df and "h_cor_uc" in df:
            # The E4 acceptance band: a model LE/H within ±uc of the corrected observation is inside the
            # dataset's own uncertainty. Reported daytime, where the fluxes (and the band) are large.
            dmask = df["swdown"] > 50.0
            le_uc, h_uc = float(df["le_cor_uc"][dmask].mean()), float(df["h_cor_uc"][dmask].mean())
            add(f"    PLUMBER2 joint uncertainty (daytime mean): LE ±{le_uc:.2f} W/m²   H ±{h_uc:.2f} W/m²")
            row.update(le_uc_daytime=round(le_uc, 3), h_uc_daytime=round(h_uc, 3))

        # ---- 5. Bowen ratio, daytime only (SWdown > 50 W/m²), from daytime SUMS -------------
        day = (df["swdown"] > 50.0) & np.isfinite(le) & np.isfinite(h)
        bowen = float(h[day].sum() / le[day].sum())
        warm = day & df.index.month.isin([6, 7, 8] if meta["lat"] >= 0 else [12, 1, 2])
        bowen_warm = float(h[warm].sum() / le[warm].sum())
        add(
            f"  Bowen (daytime ΣH/ΣLE, n={int(day.sum())}): all-record {bowen:.3f}   "
            f"{'JJA' if meta['lat'] >= 0 else 'DJF'} {bowen_warm:.3f}"
        )
        row.update(bowen_daytime=round(bowen, 4), bowen_warm_season=round(bowen_warm, 4))

    # ---- 6. time-axis check: mean-diurnal SWdown peak ----------------------------------------
    hod = df.index.hour + df.index.minute / 60.0
    sw_cycle = df.groupby(hod)["swdown"].mean()
    peak = float(sw_cycle.idxmax())
    add(
        f"  time-axis check: mean-diurnal SWdown peaks at {peak:.1f} h "
        f"⇒ {'LOCAL STANDARD time (expected 11–13 h)' if 11.0 <= peak <= 13.0 else 'NOT local solar noon — investigate before any diurnal comparison'}"
    )
    row["swdown_peak_hour"] = round(peak, 2)

    # ---- 7. T_skin ---------------------------------------------------------------------------
    if "lwup" in df and "lwdown" in df:
        ts = skin_temperature(df, EMISSIVITY)
        ts_bright = skin_temperature(df, 1.0)
        dts = (ts - df["tair"]).dropna()
        day = df["swdown"] > 50.0
        add(
            f"  T_skin from LWup (ε={EMISSIVITY}): mean {ts.mean():.2f} K  "
            f"[{ts.min():.2f}…{ts.max():.2f}]   brightness-T (ε=1) mean {ts_bright.mean():.2f} K  "
            f"(Δ={float(ts.mean() - ts_bright.mean()):+.2f} K)"
        )
        add(
            f"    T_skin − Tair: daytime {float((ts - df['tair'])[day].mean()):+.2f} K   "
            f"nighttime {float((ts - df['tair'])[~day].mean()):+.2f} K   overall {dts.mean():+.2f} K  "
            f"⇒ {'physical (daytime skin warmer than air)' if float((ts - df['tair'])[day].mean()) > 0 else 'UNEXPECTED sign — check LWup'}"
        )
        df["t_skin"] = ts
        row.update(
            mean_t_skin=round(float(ts.mean()), 3),
            dt_skin_air_day=round(float((ts - df["tair"])[day].mean()), 3),
            dt_skin_air_night=round(float((ts - df["tair"])[~day].mean()), 3),
        )
    else:
        add("  T_skin: NOT DERIVABLE — no LWup in this file (FLUXNET2015/LaThuile-sourced PLUMBER2 sites)")
    return row


def aggregate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (daily table, mean diurnal cycle per month) — the daily gate plus the retained sub-daily cycle."""
    flux_cols = [c for c in ("le", "le_cor", "h", "h_cor", "rn", "g", "swdown", "lwdown", "lwup", "swup",
                             "ustar", "gpp", "nee", "vpd", "wind", "psurf", "qair", "lai", "t_skin")
                 if c in df]
    daily = df.groupby(df.index.normalize())[flux_cols].mean()
    daily["tair_mean"] = df["tair"].resample("1D").mean()
    daily["tair_min"] = df["tair"].resample("1D").min()
    daily["tair_max"] = df["tair"].resample("1D").max()
    if "precip" in df:  # kg/m²/s -> mm/day
        daily["precip_mm"] = df["precip"].resample("1D").mean() * 86400.0
    steps_per_day = round(1440 / max(1, int((df.index[1] - df.index[0]).total_seconds() // 60)))
    daily["n_valid_le"] = df["le"].resample("1D").count()
    daily["n_valid_h"] = df["h"].resample("1D").count()
    if "rn" in df:
        daily["n_valid_rn"] = df["rn"].resample("1D").count()
    if "le_qc" in df:  # gap-filled fraction among the PRESENT half-hours (see qc_composition)
        gf = (df["le_qc"] > 0) & np.isfinite(df["le"])
        daily["le_gapfilled_frac"] = gf.resample("1D").sum() / daily["n_valid_le"].replace(0, np.nan)
    if "h_qc" in df:
        gf = (df["h_qc"] > 0) & np.isfinite(df["h"])
        daily["h_gapfilled_frac"] = gf.resample("1D").sum() / daily["n_valid_h"].replace(0, np.nan)
    # Recommended filter for any model-vs-obs day: >=5/6 of the day's half-hours present for both fluxes.
    thresh = int(np.ceil(5 * steps_per_day / 6))
    daily["daily_ok"] = (daily["n_valid_le"] >= thresh) & (daily["n_valid_h"] >= thresh)
    daily.index.name = "date"

    hod = df.index.hour * 60 + df.index.minute
    diurnal = df.groupby([df.index.month, hod])[flux_cols + ["tair"]].mean()
    diurnal.index.names = ["month", "minute_of_day"]
    return daily.reset_index(), diurnal.reset_index()


def main() -> int:
    root = Path(os.environ.get("ROOT") or resolve_paths_yaml("data.energy_reference"))
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        print(f"no manifest at {manifest_path} — run scripts/fetch_plumber2_sites.py first", file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text())
    root = Path(manifest.get("root", root))
    out_dir = Path(os.environ.get("OUT") or (root / "derived"))
    no_write = os.environ.get("NO_WRITE", "0") == "1"
    wanted = [s.strip() for s in os.environ.get("SITES", "").split(",") if s.strip()] or sorted(manifest["sites"])

    lines = [
        "PLUMBER2 reference sanity report — Component E (line E, milestone E1)",
        f"dataset: {manifest['dataset']}",
        f"source : {manifest['source']}",
        f"fetched: {manifest['fetched_utc']}    root: {root}",
        f"sites  : {', '.join(wanted)}",
        f"T_skin inversion: ε={EMISSIVITY} (SEBParams default), σ={SIGMA} — consistent with src/components/energy.jl",
    ]
    rows = []
    if not no_write:
        out_dir.mkdir(parents=True, exist_ok=True)
    for site in wanted:
        df, meta = load_site(manifest["sites"][site])
        rows.append(report_site(site, df, meta, lines))
        if not no_write:
            daily, diurnal = aggregate(df)
            df.reset_index().to_parquet(out_dir / f"halfhourly_{site}.parquet", index=False)
            daily.to_parquet(out_dir / f"daily_{site}.parquet", index=False)
            diurnal.to_parquet(out_dir / f"diurnal_{site}.parquet", index=False)
            lines.append(
                f"  written: halfhourly_{site}.parquet ({len(df)} rows)  daily_{site}.parquet "
                f"({len(daily)} rows)  diurnal_{site}.parquet ({len(diurnal)} rows)"
            )

    summary = pd.DataFrame(rows)
    lines += ["", "=" * 100, "SUMMARY (headline numbers per site)", ""]
    cols = [c for c in ("site", "biome_slot", "igbp", "years", "lat", "lon", "has_lwup", "has_g",
                        "mean_rn", "mean_le", "mean_h", "bowen_daytime", "closure_slope",
                        "swdown_peak_hour", "mean_t_skin", "range_failures") if c in summary]
    lines.append(summary[cols].to_string(index=False))
    text = "\n".join(lines)
    print(text)
    if not no_write:
        (out_dir / "plumber2_sanity_report.txt").write_text(text + "\n")
        summary.to_csv(out_dir / "site_summary.csv", index=False)
        print(f"\nreport: {out_dir / 'plumber2_sanity_report.txt'}\nsummary: {out_dir / 'site_summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
