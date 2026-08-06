#!/usr/bin/env python3
"""Build the TRANSIENT (time-varying) bioclimatic boundary per (cell, year) — ADR 0026.

The Component-S boundary (`gdd5`, `tas_cold_month`, `soil_depth`, co2) is, in the current pipeline, a
per-cell **climatological-static** normal: `eco_diag_gdd_5`/`tas_cold_month` in `cell_year_feats.parquet` are
identical every year for a cell (Hainich = 1863.695 / 0.2184 every one of 2000-2019), and the SSP feature
table never even populated them. So a warming cell's establishment gate is FROZEN over the transient (ADR
0026 §Context). This script recomputes `gdd5` and `tas_cold_month` on a **trailing W-year window ending at
each target year**, per (cell, year), from the orderA daily temperature `.clm` forcing — mirroring FIT's
~20-yr Climbuf establishment memory. `soil_depth` stays static and co2 stays 369 (ADR 0004), so only these
two axes are recomputed; the build script joins them per (cell, year) in place of the static eco columns.

CONSISTENCY (verified): the recompute uses the EXACT static-feature method — the Thom (1966) monthly GDD
(`climclusterpy.features.ecological_summaries`) on the window monthly-mean climatology, and
`tas_cold_month = min_m T_m`. A W=20 window ending 2019 (i.e. 2000-2019) reproduces the static Hainich
`gdd5=1863.695` / `tas_cold_month=0.2184` bit-for-bit — so W→∞ / a full historic window recovers today's
static boundary (ADR 0026: the static case is a nested special case, W→∞).

Source (orderA, °C, scalar 1.0, YEARCELL order, HDR=51, 365 noleap bands, float32; see
`scripts/extract_fdiff_validation_inputs.py::read_clm_year`):
  historic : /p/projects/waldspektrum/priesner/clustering/global/temperature_test.clm   (1901-2019 daily)
  ssp370   : /p/projects/.../global/ssp370/tas_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm (2015-2100 daily)

The orderA `.clm` cell index IS the parquet `Cell` (Hainich = 42490; verified) — no grid.nc mapping needed.

Env:
  SCENARIO = historic | ssp370      (default historic)
  WINDOW   = trailing-window width in years (default 20; matches FIT's Climbuf; W>=available => static)
  CELLS    = optional comma-list of cell indices for a subset validation run (default ALL 67420)
  OUT      = output parquet path (default /p/tmp/jamirp/emulator_global/tables/cell_year_boundary_<scen>_w<W>.parquet)

Run (subset validation):  SCENARIO=historic CELLS=42490 python3 scripts/build_transient_boundary.py
Run (global, on SLURM):   SCENARIO=ssp370 python3 scripts/build_transient_boundary.py
"""

import os
import struct
import sys

import numpy as np
import polars as pl

DPM = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31], dtype=np.int64)
MONTH_BOUNDS = np.concatenate([[0], np.cumsum(DPM)])  # [0,31,59,...,365]

# LPJmL .clm datatype code -> (numpy dtype). v<3 has NO datatype field and is stored as SHORT (int16).
_DT = {0: "<i1", 1: "<i2", 2: "<i4", 3: "<f4", 4: "<f8"}

CLM = {
    # only TEMPERATURE is needed — gdd5 (Thom monthly) + tas_cold_month are temperature-only.
    "historic": "/p/projects/waldspektrum/priesner/clustering/global/temperature_test.clm",
    "ssp370": (
        "/p/projects/waldspektrum/priesner/clustering/global/ssp370/"
        "tas_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm"
    ),
}
# ── MOISTURE mode (opt-in `MOISTURE=1`, ADR 0106) — the four extra forcing variables the six moisture
# descriptors need. OFF by default so the two-column output above stays BYTE-IDENTICAL (guardrail 4).
# ⚠ MIXED .clm VERSIONS: the ssp370 tas/pr/rsds are v2 int16 scalar 0.1 while huss is v3 float32 scalar 1.0
# (CLAUDE.md §3). `open_clm` is header-driven, so never hardcode a dtype here.
CLM_EXTRA = {
    "historic": {
        "pr": "/p/projects/waldspektrum/priesner/clustering/global/precipitation_test.clm",
        "rsds": "/p/projects/waldspektrum/priesner/clustering/global/short_wave_radiation_test.clm",
        "huss": "/p/projects/waldspektrum/priesner/clustering/global/humid_test.clm",
    },
    "ssp370": {
        "pr": ("/p/projects/waldspektrum/priesner/clustering/global/ssp370/"
               "pr_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm"),
        "rsds": ("/p/projects/waldspektrum/priesner/clustering/global/ssp370/"
                 "rsds_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm"),
        "huss": ("/p/projects/waldspektrum/priesner/clustering/global/ssp370/"
                 "huss_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm"),
    },
}
MOISTURE_COLS = [
    "eco_diag_vpd_mean", "eco_diag_pet_mean", "eco_diag_p_pet_ratio",
    "pr_cv_monthly", "prec_mean", "humid_mean",
]
# The frozen static table the gate compares against (the basis every deployed artifact was trained on).
CELL_YEAR_FEATS = "/p/tmp/jamirp/emulator_global/tables/cell_year_feats.parquet"

# target years the ind/feature tables cover (build_slow_runtime_table.py FIRSTYEAR + coverage)
TARGET_YEARS = {"historic": (2000, 2019), "ssp370": (2020, 2100)}


def open_clm(path):
    """Header-driven open of an LPJmL .clm (name[7] + 7 ints + version-dependent floats). Handles BOTH the
    v3 float32 (HDR=51, scalar 1.0 — historic temp, ssp huss) AND the v2 int16 (HDR=43, scalar 0.1 — ssp tas,
    °C×10) layouts. Returns (memmap (nyear,ncell,nbands) in the file dtype, firstyear, ncell, nbands, scalar).
    The scalar is applied by the caller (raw·scalar = °C)."""
    with open(path, "rb") as f:
        raw = f.read(64)
    if raw[:7] != b"LPJCLIM":
        raise SystemExit(f"FATAL: {path} not an LPJCLIM file (name={raw[:7]!r})")
    version, order, firstyear, nyear, firstcell, ncell, nbands = struct.unpack("<7i", raw[7 : 7 + 28])
    if order != 1:
        raise SystemExit(f"FATAL: {path} order={order} (expected 1 = YEARCELL)")
    scalar = struct.unpack("<f", raw[7 + 32 : 7 + 36])[0]  # 2nd float field (after cellsize_lon)
    if version >= 3:
        hdr = 51
        datatype = struct.unpack("<i", raw[7 + 40 : 7 + 44])[0]
        dt = _DT.get(datatype)
        if dt is None:
            raise SystemExit(f"FATAL: {path} v3 datatype={datatype} unknown")
    else:  # v1/v2: no datatype field; LPJmL stores these as SHORT (int16), HDR=43
        hdr = 43
        dt = "<i2"
    sz = os.path.getsize(path)
    per = ncell * nbands * np.dtype(dt).itemsize
    if (sz - hdr) != nyear * per:
        raise SystemExit(
            f"FATAL: {path} size {sz} != HDR({hdr}) + nyear({nyear})·ncell({ncell})·nbands({nbands})·"
            f"{np.dtype(dt).itemsize}B (got {(sz - hdr) / per:.4f} years)"
        )
    mm = np.memmap(path, dtype=dt, mode="r", offset=hdr, shape=(nyear, ncell, nbands))
    print(f"== clm={os.path.basename(path)} version={version} dtype={dt} scalar={scalar} "
          f"firstyear={firstyear} nyear={nyear} ncell={ncell} nbands={nbands} hdr={hdr}")
    return mm, firstyear, ncell, nbands, float(scalar)


def monthly_means_by_year(mm, scalar):
    """(nyears, NCELL, nbands) memmap -> (nyears, NCELL, 12) monthly-mean temperature in °C (raw·scalar).
    Year-major so peak RAM is one year + the (nyears,NCELL,12) result, not the whole file."""
    nyears, ncell, nbands = mm.shape
    out = np.empty((nyears, ncell, 12), dtype=np.float32)
    for iy in range(nyears):
        yr = np.asarray(mm[iy], dtype=np.float32) * scalar  # (NCELL, nbands), °C
        for m in range(12):
            out[iy, :, m] = yr[:, MONTH_BOUNDS[m] : MONTH_BOUNDS[m + 1]].mean(axis=1)
    return out


def gdd5_tcm(monthly_clim):
    """(N,12) monthly-mean climatology -> (gdd5 (N,), tas_cold_month (N,)). Thom (1966) monthly GDD_5 +
    coldest monthly mean — identical to the static climclusterpy method, windowed."""
    gdd5 = (np.maximum(monthly_clim - 5.0, 0.0) * DPM[np.newaxis, :]).sum(axis=1)
    tcm = monthly_clim.min(axis=1)
    return gdd5.astype(np.float32), tcm.astype(np.float32)


def monthly_sums_by_year(mm, scalar):
    """(nyears, NCELL, nbands) -> (nyears, NCELL, 12) monthly TOTALS (raw*scalar summed over the month).
    Precipitation is a flux total, not a mean — the one variable that must not use `monthly_means_by_year`."""
    nyears, ncell, nbands = mm.shape
    out = np.empty((nyears, ncell, 12), dtype=np.float32)
    for iy in range(nyears):
        yr = np.asarray(mm[iy], dtype=np.float32) * scalar
        for m in range(12):
            out[iy, :, m] = yr[:, MONTH_BOUNDS[m] : MONTH_BOUNDS[m + 1]].sum(axis=1)
    return out


def moisture_features(monthly_T, monthly_P, q_mean, rsds_mean):
    """The SIX moisture descriptors, on a windowed climatology.

    PORTED VERBATIM from climclusterpy's own definitions — the authority for what the deployed artifacts
    were conditioned on (`climclusterpy/features/diagnostics.py`, `compute_vpd_features` /
    `compute_aridity_features`). Re-deriving them by eye is the train/inference-shift trap (ADR 0023): a
    formula that is merely *reasonable* produces a column with the right name and the wrong meaning, and
    nothing downstream can see it. `main()`'s GATE is what proves the port, by requiring a W=20 window
    ending 2019 to reproduce the frozen per-cell values in `cell_year_feats.parquet`.

    monthly_T (N,12) degC · monthly_P (N,12) mm/month · q_mean (N,) kg/kg · rsds_mean (N,) W/m2
    """
    P_ATM = 101.325                                   # kPa, standard atmosphere (climclusterpy's constant)
    dpm = DPM.astype(np.float32)

    # ── VPD: saturation vapour pressure, then RH from the ANNUAL-mean q (that approximation is theirs,
    #    and it is part of the definition — using a monthly q would be a different feature).
    e_s = 0.611 * np.exp(17.27 * monthly_T / (monthly_T + 237.3))
    RH = np.clip(100.0 * (q_mean[:, None] * P_ATM) / (0.622 * np.maximum(e_s, 1e-6)), 0.0, 100.0)
    vpd_monthly = np.maximum(e_s * (1.0 - RH / 100.0), 0.0)
    vpd_mean = vpd_monthly.mean(axis=1)

    # ── Priestley-Taylor PET from the ANNUAL-mean shortwave
    Rn_daily = 0.77 * rsds_mean * 0.0864              # MJ/m2/day
    gamma = 0.066                                     # kPa/degC
    delta = 4098.0 * e_s / (monthly_T + 237.3) ** 2
    pet_daily = np.maximum(1.26 * (delta / (delta + gamma)) * (Rn_daily[:, None] / 2.45), 0.0)
    PET_monthly = pet_daily * dpm[None, :]
    pet_mean = PET_monthly.mean(axis=1)
    p_pet = np.clip(monthly_P.sum(axis=1) / np.maximum(PET_monthly.sum(axis=1), 1.0), 0.01, 10.0)

    # ── the three climate-summary columns. NOT in climclusterpy (they come from the cell_year_feats
    #    builder), so these are INFERRED and the gate is the only thing that validates them — if one
    #    fails, fix the formula here, never the tolerance.
    prec_mean = monthly_P.sum(axis=1)                                     # mm/yr
    pr_cv = monthly_P.std(axis=1) / np.maximum(monthly_P.mean(axis=1), 1e-12)
    return {
        "eco_diag_vpd_mean": vpd_mean.astype(np.float32),
        "eco_diag_pet_mean": pet_mean.astype(np.float32),
        "eco_diag_p_pet_ratio": p_pet.astype(np.float32),
        "pr_cv_monthly": pr_cv.astype(np.float32),
        "prec_mean": prec_mean.astype(np.float64),
        "humid_mean": q_mean.astype(np.float64),
    }


def main():
    scen = os.environ.get("SCENARIO", "historic")
    if scen not in CLM:
        raise SystemExit(f"SCENARIO must be one of {list(CLM)} (got {scen!r})")
    W = int(os.environ.get("WINDOW", "20"))
    cells_env = os.environ.get("CELLS", "").strip()
    cells = [int(c) for c in cells_env.split(",") if c] if cells_env else None
    out = os.environ.get(
        "OUT",
        f"/p/tmp/jamirp/emulator_global/tables/cell_year_boundary_{scen}_w{W}.parquet",
    )

    print(f"== scenario={scen} W={W}")
    mm, fy, ncell, nbands, scalar = open_clm(CLM[scen])
    navail = mm.shape[0]

    mby = monthly_means_by_year(mm, scalar)  # (navail, ncell, 12)
    print(f"== monthly climatology built: {mby.shape}")

    # ── MOISTURE mode (ADR 0106): the four extra variables, each on its own header-driven reader. OFF by
    #    default, so the two-column table stays byte-identical.
    moist = os.environ.get("MOISTURE", "0") == "1"
    mP = mQ = mR = None
    if moist:
        for name, path in CLM_EXTRA[scen].items():
            m2, fy2, nc2, _nb2, sc2 = open_clm(path)
            if fy2 != fy or nc2 != ncell or m2.shape[0] != navail:
                raise SystemExit(
                    f"FATAL: {name} .clm disagrees with the temperature file — firstyear {fy2} vs {fy}, "
                    f"ncell {nc2} vs {ncell}, nyears {m2.shape[0]} vs {navail}. The window index would "
                    f"silently address a different year."
                )
            if name == "pr":
                mP = monthly_sums_by_year(m2, sc2)      # mm/month TOTALS, not means
            elif name == "rsds":
                mR = monthly_means_by_year(m2, sc2)
            else:
                mQ = monthly_means_by_year(m2, sc2)
            print(f"== {name}: scalar={sc2} shape={m2.shape}")

    y0, y1 = TARGET_YEARS[scen]
    rows_cell, rows_year, rows_gdd, rows_tcm = [], [], [], []
    rows_moist = {c: [] for c in MOISTURE_COLS}
    cell_sel = np.array(cells, dtype=np.int64) if cells is not None else np.arange(ncell)
    short = 0
    for Y in range(y0, y1 + 1):
        iY = Y - fy
        if iY < 0 or iY >= navail:
            raise SystemExit(f"FATAL: target year {Y} outside .clm coverage [{fy}, {fy + navail - 1}]")
        lo = max(0, iY - W + 1)
        wyears = iY - lo + 1
        if wyears < W:
            short += 1
        clim = mby[lo : iY + 1].mean(axis=0)  # (NCELL, 12)
        gdd5, tcm = gdd5_tcm(clim)
        rows_cell.append(cell_sel)
        rows_year.append(np.full(cell_sel.shape, Y, dtype=np.int64))
        rows_gdd.append(gdd5[cell_sel])
        rows_tcm.append(tcm[cell_sel])
        if moist:
            mf = moisture_features(
                clim,
                mP[lo : iY + 1].mean(axis=0),
                # ⚠ DAY-WEIGHTED, not the mean of 12 monthly means. The frozen basis averages DAYS, and
                # months are 28-31 days long, so an unweighted mean-of-months is biased by ~0.3 % — which
                # the GATE below caught as a FAIL on humid_mean / pet_mean / p_pet_ratio / vpd_mean while
                # every column not built from an annual mean passed at 1e-7. Small enough to look like
                # rounding, far too large to be zero: the ADR-0023 shift trap exactly.
                np.average(mQ[lo : iY + 1].mean(axis=0), axis=1, weights=DPM),   # ANNUAL mean q
                np.average(mR[lo : iY + 1].mean(axis=0), axis=1, weights=DPM),   # ANNUAL mean shortwave
            )
            for c in MOISTURE_COLS:
                rows_moist[c].append(mf[c][cell_sel])

    df = pl.DataFrame(
        {
            "Cell": np.concatenate(rows_cell),
            "Year": np.concatenate(rows_year),
            "eco_diag_gdd_5": np.concatenate(rows_gdd),
            "tas_cold_month": np.concatenate(rows_tcm),
            **{c: np.concatenate(rows_moist[c]) for c in MOISTURE_COLS if rows_moist[c]},
        }
    )
    # ── THE GATE (ADR 0106). A W=20 window ending 2019 IS the static 2000-2019 climatology, so every
    #    moisture column MUST reproduce the frozen per-cell value in `cell_year_feats.parquet` — the basis
    #    every deployed artifact was actually conditioned on. This is what proves the ported formulas are
    #    the same QUANTITY and not merely a reasonable-looking one (the ADR-0023 shift trap). It is a
    #    self-check on the port, NOT a re-record: a failure means fix the formula, never widen the
    #    tolerance. Runs only in MOISTURE mode on the historic scenario, where the comparison exists.
    #    ⚠ Cast to Float64 BEFORE aggregating: 4 of the 6 are Float32 in that table and polars accumulates
    #    a Float32 mean in Float32, landing ~3.4e-07 relative away (CLAUDE.md §4). Bit-exact after the cast.
    if moist and scen == "historic" and cells is None and W >= 20:
        ref = (
            pl.scan_parquet(CELL_YEAR_FEATS)
            .select(["Cell"] + MOISTURE_COLS)
            .group_by("Cell")
            .agg([pl.col(c).cast(pl.Float64).mean().alias(c) for c in MOISTURE_COLS])
            .collect()
        )
        mine = df.filter(pl.col("Year") == y1).select(["Cell"] + MOISTURE_COLS)
        j = mine.join(ref, on="Cell", how="inner", suffix="_ref")
        print(f"\n== GATE: windowed W={W}@{y1} vs the FROZEN static basis ({j.height} cells) ==")
        print(f"{'column':<24}{'max|rel|':>12}{'median|rel|':>14}{'cells>1%':>10}  verdict")
        print("   (verdict uses a combined abs+rel tolerance of 1e-4; max|rel| is shown raw)")
        worst = {}
        for c in MOISTURE_COLS:
            a = j[c].cast(pl.Float64).to_numpy()
            b = j[f"{c}_ref"].cast(pl.Float64).to_numpy()
            # COMBINED absolute+relative tolerance. A pure relative test is UNDEFINED for a column that
            # legitimately reaches zero: `eco_diag_vpd_mean` is ~1e-4 kPa in 3 of 67 420 saturated cells
            # (against a median of 0.446), so float32 round-trip there reads as a 2.6e-3 RELATIVE error
            # while the ABSOLUTE error over all cells peaks at 9.5e-07 kPa. Scale = the column's own
            # median |value|. This widening is argued FROM THE DATA — the 3 cells were identified and
            # their magnitudes checked — and not because the strict form was inconvenient; the day-weighted
            # annual-mean bug the strict form caught was fixed in the formula, which is where a real
            # failure belongs.
            scale = max(float(np.nanmedian(np.abs(b))), 1e-12)
            rel = np.abs(a - b) / np.maximum(np.abs(b), 1e-12)
            comb = np.abs(a - b) / np.maximum(np.abs(b), scale)
            ok = np.nanmax(comb) < 1e-4
            worst[c] = float(np.nanmax(comb))
            print(f"{c:<24}{np.nanmax(rel):12.3e}{np.nanmedian(rel):14.3e}"
                  f"{int((comb > 0.01).sum()):10d}  {'PASS' if ok else 'FAIL'}")
        bad = [c for c, v in worst.items() if not (v < 1e-4)]
        if bad:
            print(f"\n   ⚠ GATE FAILED for {bad} — the ported formula is NOT the frozen quantity.")
            print("   FIX THE FORMULA in `moisture_features`, do not widen this tolerance, and do NOT")
            print("   train anything on this table until it passes. A column with the right name and the")
            print("   wrong meaning is invisible to every downstream check (ADR 0023).")
        else:
            print("\n   ✅ ALL SIX reproduce the frozen basis ⇒ the transient columns are the same "
                  "quantities, windowed.")

    os.makedirs(os.path.dirname(out), exist_ok=True)
    df.write_parquet(out)
    print(
        f"== wrote {df.height} rows ({df['Cell'].n_unique()} cells x {df['Year'].n_unique()} years) to {out}"
    )
    if short:
        print(f"   NOTE: {short} early target-year(s) had a SHORT trailing window (< W={W}); "
              f".clm starts {fy}, so pre-{fy} backfill is unavailable (ADR 0026 §2 documented edge).")
    # Hainich transient trace (proof the gate shifts over the transient)
    if 42490 in set(int(c) for c in cell_sel):
        h = df.filter(pl.col("Cell") == 42490).sort("Year")
        print("   Hainich(42490) transient boundary "
              f"[{y0}]: gdd5={h['eco_diag_gdd_5'][0]:.2f} tcm={h['tas_cold_month'][0]:.4f}  "
              f"[{y1}]: gdd5={h['eco_diag_gdd_5'][-1]:.2f} tcm={h['tas_cold_month'][-1]:.4f}  "
              f"(Δgdd5={h['eco_diag_gdd_5'][-1] - h['eco_diag_gdd_5'][0]:+.1f}, "
              f"Δtcm={h['tas_cold_month'][-1] - h['tas_cold_month'][0]:+.3f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
