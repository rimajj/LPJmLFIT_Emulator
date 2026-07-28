#!/usr/bin/env python3
"""build_rootmoist_soilmoist_feature.py — derive the `soilmoist` training feature on the SAME PHYSICAL
VARIABLE the coupled runtime feeds Component S. Supersedes build_swc_soilmoist_feature.py (ADR 0035).

WHY THIS EXISTS — the predecessor was reducing the WRONG VARIABLE (milestone S1d):
  ADR 0034 recorded the `soilmoist` runtime<->training band shift (5.1x the trained band width) as a
  TEMPORAL aggregation mismatch: an annual mean vs a year-end instant. Re-deriving the two definitions
  against the C source shows that was only the smaller half of it. The two sides were not the same
  QUANTITY at all:

    training (build_swc_soilmoist_feature.py)   the C `swc` output, `update_daily.c:411`:
        SWC[l] = (w[l]*whcs[l] + w_fw[l] + wpwps[l] + ice_depth[l] + ice_fw[l]) / wsats[l]
      = TOTAL water (plant-available + wilting-point + free + ice) as a fraction of SATURATION capacity.

    runtime  (slow.jl::flux_feature_vector)     `state.w[l]`, state.jl:38:
      = PLANT-AVAILABLE water as a fraction of WHC (field capacity - wilting point). The C's own
        `soil.w[l]` — the numerator's first term above, before the wpwp/free/ice offsets and normalised
        by a different capacity.

  `swc` therefore lives on ~[wpwp/wsat, 1] (never approaching 0 on a real soil) while `w` lives on [0, 1],
  and no temporal re-reduction of `swc` can ever make the two agree. The interface contract already says
  which one is meant: `FToS.soilmoist` is documented "root-zone soil moisture state, fraction of WHC"
  (interface.jl:37). `swc` cannot be inverted back to `w` — that needs `wsats`/`wpwps`/`w_fw`/`ice`, and
  LPJmL-FIT emits none of them (CLAUDE.md §3: "no `wsats` output => absolute mm not reconstructable").

  The ONE C output carrying `w` itself is `rootmoist` (`update_daily.c:414`):
        ROOTMOIST = SUM_{l<3} w[l] * whcs[l]        (mm, patch-ensemble mean; `forrootmoist` = the top 1 m,
                                                     soil.h:353 `for(l=0;l<3;l++)`)
  and the per-layer capacity is recoverable from the `whc_nat` output (CLAUDE.md §3 / ADR 0050:
  `whcs[l] = whc_nat[l] * soildepth[l]`, the C's own `whcs`). So

        soilmoist = ROOTMOIST / SUM_{l<3} whcs[l]                                            (*)

  is a whcs-weighted mean of `w` over the top 1 m — the same variable, on a named layer set, in [0,1].
  `slow.jl::flux_feature_vector` is changed to compute exactly (*) from `state.w` + `fc.soil.whcs`.

TEMPORAL BASIS — YEAR-END, deliberately (ADR 0035 §4, not a default):
  `soilmoist` is a STATE variable, and it is read at the instant `reconcile_demography!` runs = year end.
  Every other state column in the same training row (`hmean`/`hmax`/`agb`/`lai`/`fpc`/`age_mean`/`n_prev`)
  is a year-end quantity too, because the `ind` table is written at year end; the annual water INTEGRAL is
  already carried by a separate feature, `water_stress` = 1 - mean(wscal). So the year-end reduction is
  what makes the feature row internally consistent, and it needs no runtime accumulator (an annual-mean
  runtime `soilmoist` would need a DAILY hook in `run.jl`, which is line M's file — ADR 0035 §6).
  Day index within a 365-day noleap year: 364 (0-based) = 31 December.

Env:
  RUN_DIR    daily run output dir with grid.nc + d_rootmoist.nc + whc_nat.nc   (required)
  OUT        output parquet path                        (default RUN_DIR/cell_year_soilmoist_ye.parquet)
  FIRSTYEAR  calendar year of time index 0              (default 2000; 2020 for the SSP370 run)
  SUBSET_DEG optional lat/lon box around Hainich for a fast login-node correctness check
Usage:
  RUN_DIR=/p/tmp/jamirp/esm_land_daily/daily_2000_2019_global_c0_67419_seed1/output \
  OUT=/p/tmp/jamirp/emulator_global/tables/cell_year_soilmoist_ye_hist.parquet \
  scripts/sbatch_python.sh S-smye scripts/build_rootmoist_soilmoist_feature.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import polars as pl
import xarray as xr

NDAYYEAR = 365          # noleap; matches water_closure_check.py / build_swc_soilmoist_feature.py
YEAR_END_DOY0 = 364     # 0-based day index of 31 December — the instant reconcile_demography! reads
NROOTLAYER = 3          # `forrootmoist` = the top 1 m (include/soil.h:353) — the layer set (*) is on
EXPECT_TOP3_MM = (200.0, 300.0, 500.0)  # par/soil_20m.js, a C GLOBAL (fscansoilpar.c:36-39), not per-cell
SOILMOIST_MAX = 1.05    # `w` is a fraction of WHC in [0,1]; the C spills the excess into w_fw, so >1 is fill


def main() -> int:
    run_dir = os.environ.get("RUN_DIR")
    if not run_dir:
        print("FATAL: set RUN_DIR (daily run output dir with grid.nc + d_rootmoist.nc + whc_nat.nc)",
              file=sys.stderr)
        return 2
    firstyear = int(os.environ.get("FIRSTYEAR", "2000"))
    out = os.environ.get("OUT", os.path.join(run_dir, "cell_year_soilmoist_ye.parquet"))
    subset_deg = os.environ.get("SUBSET_DEG")

    grid = xr.open_dataset(os.path.join(run_dir, "grid.nc"))
    cellid = grid["cellid"]  # [lat, lon] — the authoritative 0-based orderA index (NOT the flatten order)
    whc = xr.open_dataset(os.path.join(run_dir, "whc_nat.nc"), decode_times=False)
    rm = xr.open_dataset(os.path.join(run_dir, "d_rootmoist.nc"), decode_times=False)

    # ── layer geometry: `depth` is the layer CENTRE, so thickness comes from depth_bnds (CLAUDE.md §3) ──
    bnds = whc["depth_bnds"].values
    thick_mm = (bnds[:, 1] - bnds[:, 0]) * 1000.0
    if not np.allclose(thick_mm[:NROOTLAYER], EXPECT_TOP3_MM):
        print(f"FATAL: top-{NROOTLAYER} layer thicknesses {thick_mm[:NROOTLAYER]} mm != expected "
              f"{EXPECT_TOP3_MM} — wrong soil discretisation, (*) would divide by the wrong capacity.",
              file=sys.stderr)
        return 3

    whc_da = whc["whc_nat"].isel(layer=slice(0, NROOTLAYER))   # [time(monthly), 3, lat, lon], fraction
    rm_da = rm["rootmoist"]                                    # [time(daily), lat, lon], mm
    if subset_deg:
        d = float(subset_deg)
        box = dict(lat=slice(51.25 - d, 51.25 + d), lon=slice(10.25 - d, 10.25 + d))
        whc_da = whc_da.sel(**box); rm_da = rm_da.sel(**box); cellid = cellid.sel(**box)

    nday = rm_da.sizes["time"]
    nyear = nday // NDAYYEAR
    if nday % NDAYYEAR:
        print(f"FATAL: d_rootmoist has {nday} days, not a whole number of {NDAYYEAR}-day years",
              file=sys.stderr)
        return 3
    nmon = whc_da.sizes["time"]
    if nmon != 12 * nyear:
        print(f"FATAL: whc_nat has {nmon} monthly steps, expected {12 * nyear} for {nyear} years",
              file=sys.stderr)
        return 3

    cid = cellid.values
    valid = np.isfinite(cid)
    cells = cid[valid].astype(np.int64)
    print(f"{nyear} years x {len(cells)} cells; top-{NROOTLAYER} thickness {thick_mm[:NROOTLAYER]} mm")

    # per-layer plant-available capacity, summed over the root layers, as a per-(cell, year) mm value.
    # whc_nat is MONTHLY and slowly time-varying (it is recomputed from the evolving soil carbon via
    # Saxton-Rawls — ADR 0050), so average the year's 12 months rather than pinning one month. Measured
    # drift at Hainich over 2000-2019 is 0.08 mm on 177.3 mm (0.04%), so this choice is not load-bearing.
    whcs_top3 = (whc_da * xr.DataArray(thick_mm[:NROOTLAYER], dims=["layer"])).sum(dim="layer")
    whcs_top3 = whcs_top3.values.reshape(nyear, 12, *whcs_top3.shape[1:]).mean(axis=1)  # [year, lat, lon]

    rows = []
    per_year_frac = []
    for y in range(nyear):
        ye = rm_da.isel(time=y * NDAYYEAR + YEAR_END_DOY0).values.astype(np.float64)   # [lat, lon], mm
        cap = whcs_top3[y].astype(np.float64)
        with np.errstate(divide="ignore", invalid="ignore"):
            sm = np.where(cap > 0.0, ye / cap, np.nan)
        vals = sm[valid]
        real = np.isfinite(vals) & (vals >= 0.0) & (vals <= SOILMOIST_MAX)
        per_year_frac.append(float(real.mean()))
        vals = np.where(real, vals, np.nan)
        rows.append(pl.DataFrame({
            "Cell": cells,
            "Year": np.full(cells.shape, firstyear + y, dtype=np.int64),
            "soilmoist": vals,
        }))
        print(f"  year {firstyear + y}: real fraction={per_year_frac[-1]:.3f}, "
              f"soilmoist mean(real)={float(np.nanmean(vals)):.4f}")

    # per-YEAR coverage gate (same rationale as the sibling derivers): a timed-out run leaves LATE years at
    # fill, which a cross-year average can still clear. Require inter-year consistency, not an absolute floor.
    med = float(np.median(per_year_frac))
    if med < 0.5 or min(per_year_frac) < 0.5 * med:
        print(f"FATAL: per-year real fraction ranges [{min(per_year_frac):.3f}, {max(per_year_frac):.3f}] "
              f"(median {med:.3f}) — incomplete/all-fill inputs. REFUSING to write {out}.", file=sys.stderr)
        return 5

    tbl = pl.concat(rows).sort(["Cell", "Year"])
    tbl = tbl.filter(pl.col("soilmoist").is_not_nan())  # is_not_NAN, NOT is_not_null (a NaN IS "not null")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    tbl.write_parquet(out)
    print(f"wrote {out}: {tbl.height} (Cell,Year) rows, "
          f"soilmoist range [{tbl['soilmoist'].min():.4f}, {tbl['soilmoist'].max():.4f}]")
    h = tbl.filter(pl.col("Cell") == 42490)
    if h.height:
        print(f"  Hainich(42490) soilmoist by year: {[round(v, 4) for v in h['soilmoist'].to_list()]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
