#!/usr/bin/env python3
"""Build the flux-conditioning training table for the flux-driven Component S.

ADR 0020 (S is flux-driven, not climate-equilibrium) + ADR 0021 (Python is confined to
building this table + running the DirectEmulator OOD benchmark; S is trained + run in
native Julia). Design of record: ``docs/slow_flux_conditioning_data_spec.md``.

This is TIER 1 (no recompile): the annual ``ind`` output already carries the four
mortality drivers + npp/gpp/transp/wscal_mean + the distribution axes, and it is already
converted to parquet at ``/p/tmp/jamirp/emulator_global/ind_hist_seed{1,2}_all.parquet``
(frozen 29-col schema, :mod:`lpjmlfit_emulator.data`). The within-year flux *statistics*
ADR 0020 requires (extremes/timing/counts, not means) come from the daily set
(``/p/tmp/jamirp/esm_land_daily``). The slow bioclimatic boundary (gdd5, coldest-month T,
soil, ECO diagnostics) comes from ``cell_year_feats.parquet``; CO2 from the TRENDY file.

Per (cell, year, patch, individual) the table maps onto the runtime F->S interface
(``src/interface.jl`` ``FToS``) so S is trained on the same channel it is conditioned on:

    FToS.bm_inc       <- ind ``npp`` (= pft->anpp; runtime FToS.bm_inc = sum(npp_ind))
    FToS.growth_eff   <- INVERTED from emitted ``mort_npp`` (monotone in bm_delta/leafarea)
    FToS.water_stress <- INVERTED from emitted ``mort_water`` (+ daily within-year stats)
    FToS.temp_stress  <- INVERTED from emitted ``mort_temp`` (daily-count cross-check)
    FToS.soilmoist    <- daily root-zone moisture (EOY + growing-season), not annual mean

Every mortality/stress definition is ``[VERIFIED]`` against the LPJmL-FIT C source
(``src/tree/mortality_tree_ind.c``, ``waterstress_tree.c``, ``tempstress_tree.c``); the
beech (PFT id 3) parameter values below are read from ``par/pft_lpjmlfit.js`` +
``par/lpjparam_fit.js`` and cross-checked in this session's recon.

AGE-ALIGNMENT GOTCHA (VERIFIED here, load-bearing for training): the emitted ``Age`` is the
POST-increment year-end age, but the same row's ``mort_*`` drivers were computed with the
PRE-increment age (= ``Age - 1``). The table carries ``age_mort = Age - 1`` (the age that
produced that row's mortality) alongside ``Age``; recomputing ``mort_age`` from ``age_mort``
matches the emitted column to ~5e-8, vs ~1.4e-4 with ``Age``.

Usage (Hainich prototype; extensible to the biome set via CELLS):
    CELLS=42490 SEED=1 OUT=/p/tmp/jamirp/slow_flux python3 scripts/build_slow_flux_table.py
    CELLS=42490,45012,... SEED=1 OUT=... python3 scripts/build_slow_flux_table.py
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import polars as pl

# make the in-repo library importable without installing
_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "python" / "src"))
from lpjmlfit_emulator import data as ind_data  # noqa: E402  (schema + loaders, reuse)

# --------------------------------------------------------------------------------------
# Paths (VERIFIED this session; canonical copies in config/paths.yaml + CLAUDE.md)
# --------------------------------------------------------------------------------------
IND_PARQUET = "/p/tmp/jamirp/emulator_global/ind_hist_seed{seed}_all.parquet"
CELL_YEAR_FEATS = "/p/tmp/jamirp/emulator_global/tables/cell_year_feats.parquet"
CO2_TXT = "/p/projects/lpjml/inputs/co2/global/TRENDY/v12/global_co2_ann_1700_2022.txt"
DAILY_ROOT = "/p/tmp/jamirp/esm_land_daily"
NDAYYEAR = 365

# --------------------------------------------------------------------------------------
# [VERIFIED] beech (temperate broadleaved summergreen, PFT id 3) mortality parameters.
# mortality_tree_ind.c / waterstress_tree.c / tempstress_tree.c + par/pft_lpjmlfit.js +
# par/lpjparam_fit.js. See docs/slow_flux_conditioning_data_spec.md §4.
#   k_mort            = 0.01   (lpjparam_fit.js "k_mort"; NOT the 0.2/0.5 in unloaded files)
#   wdmort_1/2        = -2.465 / 0.148   (WD_mort1_temp / WD_mort2_temp)
#   mort_water_factor = 5      mort_temp_factor = 5.0
#   mort_water_res    = 0.75   (MORT_WATER_RES_ANGIO)   aphen_min = 60
#   longevity         = 400    (JSON key "age" = TREE_LONGEVITY; NOT the leaf "longevity"=2.0)
#   temp_stressed     = [-20.0, 54.0]
# hardcoded C constants: KMORT_2=0.2, KMORTBG_LNF=-ln(0.001), KMORTBG_Q=2.0, BM_INC_COUNTER_MAX=5
# --------------------------------------------------------------------------------------
K_MORT = 0.01
KMORT_2 = 0.2
KMORTBG_LNF = -math.log(0.001)
KMORTBG_Q = 2.0

# per-PFT-type params. Beech (3) is [VERIFIED]; the other temperate tree types at Hainich
# (1,2,4,5) are <6% of rows -> reuse the temperate values and FLAG them (scale-up must read
# each PFT's own wdmort/longevity/factors before trusting non-beech growth_eff/mort recompute).
_TEMPERATE_TREE = dict(
    wdmort_1=-2.465,
    wdmort_2=0.148,
    mort_water_factor=5.0,
    mort_temp_factor=5.0,
    mort_water_res=0.75,
    longevity=400.0,
    temp_low=-20.0,
    temp_high=54.0,
    verified=False,  # only beech is verified this session
)
PFT_PARAMS: dict[int, dict] = {
    t: dict(_TEMPERATE_TREE) for t in ind_data.TREE_TYPES  # (1,2,3,4,5)
}
PFT_PARAMS[3]["verified"] = True  # beech


def mort_max_of(wooddens: np.ndarray, p: dict) -> np.ndarray:
    """mort_max = 10^(wdmort_1 + wdmort_2 / (wooddens/1e6))  (mortality_tree_ind.c:92)."""
    wd = np.asarray(wooddens, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.power(10.0, p["wdmort_1"] + p["wdmort_2"] / (wd / 1.0e6))


def recompute_mort_age(age: np.ndarray, longevity: float) -> np.ndarray:
    """mort_age = min(1, KMORTBG_LNF*(KMORTBG_Q+1)/L * (age/L)^KMORTBG_Q)  (mort_min())."""
    a = np.asarray(age, dtype=float)
    val = KMORTBG_LNF * (KMORTBG_Q + 1.0) / longevity * np.power(a / longevity, KMORTBG_Q)
    return np.minimum(1.0, val)


def invert_growth_eff(mort_npp: np.ndarray, mort_max: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Invert growth_eff = bm_delta/leafarea_real from the emitted ``mort_npp``.

    mort_npp = mort_max / (1 + KMORT_2*exp(k_mort*greff)) * (1+counter).  Assuming
    counter==0 (growing rows), greff = ln((mort_max/mort_npp - 1)/KMORT_2) / k_mort.
    Valid only when 0 < mort_npp < mort_max (else counter>0 or a cap ⇒ not invertible here).
    Returns (growth_eff, invertible_mask).
    """
    mn = np.asarray(mort_npp, dtype=float)
    mm = np.asarray(mort_max, dtype=float)
    ok = np.isfinite(mn) & np.isfinite(mm) & (mn > 0) & (mm > 0) & (mn < mm)
    greff = np.full(mn.shape, np.nan)
    ratio = np.where(ok, mm / mn - 1.0, np.nan)
    arg = ratio / KMORT_2
    good = ok & (arg > 0)
    greff[good] = np.log(arg[good]) / K_MORT
    return greff, good


# --------------------------------------------------------------------------------------
# daily within-year statistics (ADR 0020: extremes / timing / counts, not means)
# --------------------------------------------------------------------------------------
GROWING_SEASON_MONTHS_NH = (4, 5, 6, 7, 8, 9)  # Apr-Sep, temperate NH growing season proxy


def _find_daily_dir(cell: int) -> str | None:
    """Prefer a single-cell daily re-run for ``cell``; else fall back to the global set."""
    single = os.path.join(DAILY_ROOT, f"daily_2000_2019_fdiff_val_c{cell}_seed1", "output")
    if os.path.isdir(single) and os.path.exists(os.path.join(single, "d_swc.nc")):
        return single
    glob_dir = os.path.join(DAILY_ROOT, "daily_2000_2019_global_c0_67419_seed1", "output")
    if os.path.isdir(glob_dir):
        return glob_dir
    return None


_COORD_VARS = {"time", "time_bnds", "lat", "lat_bnds", "lon", "lon_bnds",
               "depth", "depth_bnds", "bnds"}


def _read_daily_1d(path: str, cell_idx: int | None) -> np.ndarray | None:
    """Read the single data variable as a 1-D [time] series for one cell.

    The data variable's in-file name (GPP/NPP/transp/rootmoist/SWC/...) differs from the
    file name, so it is auto-detected as the lone non-coordinate variable.
    """
    try:
        import netCDF4  # noqa: PLC0415  (optional heavy dep, guarded)
    except Exception:
        return None
    if not os.path.exists(path):
        return None
    ds = netCDF4.Dataset(path)
    try:
        data_vars = [k for k in ds.variables if k not in _COORD_VARS]
        if not data_vars:
            return None
        v = ds.variables[data_vars[0]]
        arr = v[:]
        # squeeze lat/lon singleton dims; for the global set index the cell dim
        arr = np.asarray(arr)
        if arr.ndim == 1:
            return arr
        # collapse trailing singleton spatial dims (single-cell runs are 1x1)
        arr = np.squeeze(arr)
        if arr.ndim == 1:
            return arr
        if arr.ndim == 2 and cell_idx is not None:  # [time, ncell]
            return arr[:, cell_idx]
        return None
    finally:
        ds.close()


def daily_flux_stats(cell: int, years: list[int]) -> pl.DataFrame:
    """Per-(cell, year) within-year flux statistics from the daily set.

    Emits, per year: seasonal peak + day-of-peak for gpp/npp/transp; end-of-year and
    growing-season root-zone soil moisture (rootmoist, mm); the growing-season mean transp.
    Falls back to an all-null frame (with a printed warning) if the daily files are absent,
    so the table build never blocks on the 186 GB set.
    """
    ddir = _find_daily_dir(cell)
    cols_out = [
        "gpp_peak", "gpp_peak_doy", "npp_peak", "npp_peak_doy",
        "transp_peak", "transp_peak_doy", "transp_gs_mean",
        "rootmoist_eoy", "rootmoist_gs_mean", "rootmoist_min", "rootmoist_min_doy",
    ]
    if ddir is None:
        print(f"  [warn] no daily dir for cell {cell}; within-year stats -> null")
        return pl.DataFrame({"Year": years, **{c: [None] * len(years) for c in cols_out}})

    # single-cell run: cell_idx None (1x1). Global set: 0-based cell index == cell.
    is_single = f"_c{cell}_" in ddir
    cell_idx = None if is_single else cell

    series = {}
    for var, fname in (("gpp", "d_gpp.nc"), ("npp", "d_npp.nc"), ("transp", "d_transp.nc"),
                       ("rootmoist", "d_rootmoist.nc")):
        s = _read_daily_1d(os.path.join(ddir, fname), cell_idx)
        series[var] = s

    rows = []
    # doy -> month (non-leap 365-day calendar the model uses)
    month_len = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    doy_month = np.repeat(np.arange(1, 13), month_len)  # length 365
    gs_mask = np.isin(doy_month, GROWING_SEASON_MONTHS_NH)
    for yi, yr in enumerate(years):
        sl = slice(yi * NDAYYEAR, (yi + 1) * NDAYYEAR)
        rec: dict = {"Year": yr}
        for var, key in (("gpp", "gpp"), ("npp", "npp"), ("transp", "transp")):
            s = series[var]
            if s is None or len(s) < (yi + 1) * NDAYYEAR:
                rec[f"{key}_peak"] = None
                rec[f"{key}_peak_doy"] = None
                continue
            y = np.asarray(s[sl], dtype=float)
            rec[f"{key}_peak"] = float(np.nanmax(y))
            rec[f"{key}_peak_doy"] = int(np.nanargmax(y) + 1)
        # growing-season mean transp
        st = series["transp"]
        rec["transp_gs_mean"] = (
            float(np.nanmean(np.asarray(st[sl], dtype=float)[gs_mask]))
            if st is not None and len(st) >= (yi + 1) * NDAYYEAR else None
        )
        rm = series["rootmoist"]
        if rm is not None and len(rm) >= (yi + 1) * NDAYYEAR:
            y = np.asarray(rm[sl], dtype=float)
            rec["rootmoist_eoy"] = float(y[-1])
            rec["rootmoist_gs_mean"] = float(np.nanmean(y[gs_mask]))
            rec["rootmoist_min"] = float(np.nanmin(y))
            rec["rootmoist_min_doy"] = int(np.nanargmin(y) + 1)
        else:
            rec["rootmoist_eoy"] = rec["rootmoist_gs_mean"] = None
            rec["rootmoist_min"] = rec["rootmoist_min_doy"] = None
        rows.append(rec)
    return pl.DataFrame(rows)


# --------------------------------------------------------------------------------------
# CO2 + slow bioclimatic boundary
# --------------------------------------------------------------------------------------
def load_co2() -> dict[int, float]:
    if not os.path.exists(CO2_TXT):
        return {}
    out = {}
    with open(CO2_TXT) as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                try:
                    out[int(float(parts[0]))] = float(parts[1])
                except ValueError:
                    continue
    return out


# the slow boundary columns ADR 0020 §1c KEEPS from cell_year_feats (fluxes don't carry
# these); this-year raw climate (temp/prec/swrad/lwrad/humid) is DROPPED as a primary driver.
BOUNDARY_COLS = [
    "lat", "soil_code", "soil_depth",
    "eco_diag_gdd_5", "eco_diag_gdd_10", "eco_diag_frost_free_days",
    "eco_diag_vpd_mean", "eco_diag_vpd_max_monthly", "eco_diag_vpd_stress_months",
    "eco_diag_pet_mean", "eco_diag_p_pet_ratio", "eco_diag_water_deficit_months",
    "eco_diag_dry_spell_max", "eco_diag_dry_spell_mean",
    "tas_cold_month", "tas_warm_month", "tas_range", "pr_cv_monthly", "pr_driest_month",
    "temp_mean", "prec_mean", "swrad_mean", "lwrad_mean", "humid_mean",
]
# raw this-year climate, carried only in a separate group for the ADR-0020 OOD ablation.
DROPPED_CLIMATE_COLS = ["temp", "prec", "swrad", "lwrad", "humid",
                        "temp_anom", "prec_anom", "swrad_anom"]


# --------------------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------------------
def build(cells: list[int], seed: int, out_dir: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    ind_path = IND_PARQUET.format(seed=seed)
    print(f"== ind parquet: {ind_path}")
    lf = pl.scan_parquet(ind_path)
    ind_data.validate_ind_schema(lf.collect_schema().names(), ordered=True)

    ind = lf.filter(pl.col("Cell").is_in(cells)).collect()
    print(f"== loaded {ind.height} ind rows for cells {cells}")
    years = sorted(ind["Year"].unique().to_list())

    tree_types = list(ind_data.TREE_TYPES)
    living = ind.filter((pl.col("Type").is_in(tree_types)) & (pl.col("isdead") == 0))

    # ---- per-individual flux features (numpy for the physics inversions) --------------
    df = living.to_pandas()
    wd = df["Wooddens"].to_numpy()
    mm = np.full(len(df), np.nan)
    mage_rc = np.full(len(df), np.nan)
    # [VERIFIED this session] AGE ALIGNMENT: the emitted `Age` column is the POST-increment
    # age (getind at year-end, annual_tree.c:46), but the row's mortality drivers were
    # computed with the PRE-increment age (mortality_tree_ind at annual_tree.c:31-38). So the
    # age that produced this row's mort_* is `Age - 1`. Recomputing mort_age with Age-1 matches
    # the emitted column to 5e-8 (%g rounding floor); with Age it is off by up to 1.4e-4.
    age_mort = df["Age"].to_numpy().astype(float) - 1.0
    df["age_mort"] = age_mort
    for t, p in PFT_PARAMS.items():
        m = (df["Type"].to_numpy() == t)
        if not m.any():
            continue
        mm[m] = mort_max_of(wd[m], p)
        mage_rc[m] = recompute_mort_age(age_mort[m], p["longevity"])
    greff, greff_ok = invert_growth_eff(df["mort_npp"].to_numpy(), mm)

    # water/temp stress inverted from the emitted drivers (counter==0 assumption; flagged).
    # mort_water = (factor*water_stress/365)*(1+counter);  mort_temp = factor*temp_stress/365.
    mwf = np.array([PFT_PARAMS.get(t, _TEMPERATE_TREE)["mort_water_factor"] for t in df["Type"]])
    mtf = np.array([PFT_PARAMS.get(t, _TEMPERATE_TREE)["mort_temp_factor"] for t in df["Type"]])
    water_stress = df["mort_water"].to_numpy() * NDAYYEAR / mwf  # counter==0
    temp_stress = df["mort_temp"].to_numpy() * NDAYYEAR / mtf

    df["bm_inc"] = df["npp"].to_numpy()  # runtime-consistent FToS.bm_inc (= pft->anpp)
    df["growth_eff"] = greff
    df["growth_eff_invertible"] = greff_ok
    df["water_stress"] = water_stress
    df["temp_stress"] = temp_stress
    df["mort_max"] = mm
    df["mort_age_recomputed"] = mage_rc

    feat = pl.from_pandas(df)

    # ---- AR state: previous-year (cell,patch) distribution summary + N_prev ------------
    summ = ind_data.build_patch_summaries(
        living, summary_vars=list(ind_data.TRAIT_VARS) + ["Height", "Age", "agb", "npp"],
        stats=("mean", "sd", "q25", "q50", "q75"),
    )  # per (Cell,Patch,Year): n_trees + <var>_<stat> + frac_type<t>
    ar = summ.with_columns((pl.col("Year") + 1).alias("Year")).rename(
        {c: f"prev_{c}" for c in summ.columns if c not in ("Cell", "Patch", "Year")}
    )
    feat = feat.join(ar, on=["Cell", "Patch", "Year"], how="left")

    # ---- slow bioclimatic boundary (cell_year_feats) + CO2 ----------------------------
    if os.path.exists(CELL_YEAR_FEATS):
        cyf = pl.scan_parquet(CELL_YEAR_FEATS).filter(pl.col("Cell").is_in(cells))
        keep = ["Cell", "Year"] + [c for c in BOUNDARY_COLS + DROPPED_CLIMATE_COLS
                                   if c in cyf.collect_schema().names()]
        feat = feat.join(cyf.select(keep).collect(), on=["Cell", "Year"], how="left")
    else:
        print(f"  [warn] {CELL_YEAR_FEATS} missing; boundary features skipped")
    co2 = load_co2()
    feat = feat.with_columns(
        pl.col("Year").map_elements(lambda y: co2.get(y), return_dtype=pl.Float64).alias("co2")
    )

    # ---- daily within-year flux statistics per (cell, year) ---------------------------
    daily_frames = []
    for c in cells:
        d = daily_flux_stats(c, years).with_columns(pl.lit(c).alias("Cell"))
        daily_frames.append(d)
    daily = pl.concat(daily_frames)
    feat = feat.join(daily, on=["Cell", "Year"], how="left")

    # ---- per-(cell,patch,year) demography table (count / establishment / mortality) ----
    demog = _demography_table(ind, tree_types)

    # ---- write outputs ----------------------------------------------------------------
    tag = f"seed{seed}"
    tbl_path = os.path.join(out_dir, f"slow_flux_table_{tag}.parquet")
    demog_path = os.path.join(out_dir, f"slow_demography_{tag}.parquet")
    feat.write_parquet(tbl_path)
    demog.write_parquet(demog_path)
    print(f"== wrote {tbl_path}  ({feat.height} rows x {feat.width} cols)")
    print(f"== wrote {demog_path} ({demog.height} rows)")

    report = validate(feat, ind, tree_types)
    rep_path = os.path.join(out_dir, f"slow_flux_validation_{tag}.json")
    with open(rep_path, "w") as f:
        json.dump(report, f, indent=2, default=float)
    print(f"== wrote {rep_path}")

    # small committed fixture: Hainich, a compact column subset
    if 42490 in cells:
        _write_fixture(feat, out_dir)

    return {"table": tbl_path, "demography": demog_path, "report": rep_path, **report}


def _demography_table(ind: pl.DataFrame, tree_types: list[int]) -> pl.DataFrame:
    """Per (Cell,Patch,Year): living-tree count, deaths this year, mean mortality drivers."""
    trees = ind.filter(pl.col("Type").is_in(tree_types))
    living = trees.filter(pl.col("isdead") == 0)
    dead = trees.filter(pl.col("isdead") == 1)
    n_liv = living.group_by(["Cell", "Patch", "Year"]).agg(
        pl.len().alias("n_living"),
        pl.col("mort_npp").mean().alias("mort_npp_mean"),
        pl.col("mort_age").mean().alias("mort_age_mean"),
        pl.col("mort_water").mean().alias("mort_water_mean"),
        pl.col("mort_temp").mean().alias("mort_temp_mean"),
        pl.col("Age").min().alias("age_min"),
    )
    n_dead = dead.group_by(["Cell", "Patch", "Year"]).agg(pl.len().alias("n_dead"))
    out = n_liv.join(n_dead, on=["Cell", "Patch", "Year"], how="left").with_columns(
        pl.col("n_dead").fill_null(0)
    )
    # establishment proxy = new recruits = living rows with Age<=1 this year
    recruits = living.filter(pl.col("Age") <= 1).group_by(["Cell", "Patch", "Year"]).agg(
        pl.len().alias("n_recruit")
    )
    out = out.join(recruits, on=["Cell", "Patch", "Year"], how="left").with_columns(
        pl.col("n_recruit").fill_null(0)
    )
    return out.sort(["Cell", "Patch", "Year"])


# --------------------------------------------------------------------------------------
# validation (spec §7) — on real data
# --------------------------------------------------------------------------------------
def validate(feat: pl.DataFrame, ind: pl.DataFrame, tree_types: list[int]) -> dict:
    rep: dict = {}
    df = feat.to_pandas()

    # §7.1a mort_age EXACT recompute (tier-1 achievable: depends only on Age + longevity).
    beech = df[df["Type"] == 3]
    if len(beech):
        err = np.abs(beech["mort_age_recomputed"].to_numpy() - beech["mort_age"].to_numpy())
        rep["mort_age_parity"] = {
            "pft": 3, "n": int(len(beech)),
            "max_abs_err": float(np.nanmax(err)),
            "mean_abs_err": float(np.nanmean(err)),
            "pass_1e-6": bool(np.nanmax(err) < 1e-6),
        }

    # §7.1b mort-sum identity: mort_npp+mort_age+mort_water+mort_temp == emitted `mort`
    #        on NON-OVERRIDE rows (mort_prob is saved post cap / counter>=5 / ghost-tree,
    #        so override rows legitimately differ — flag & exclude them).
    trees = ind.filter((pl.col("Type").is_in(tree_types)) & (pl.col("isdead") == 0)).to_pandas()
    comp_sum = (trees["mort_npp"] + trees["mort_age"] + trees["mort_water"]
                + trees["mort_temp"]).to_numpy()
    emitted = trees["mort"].to_numpy()
    # a row is a suspected override if emitted==1 while the component sum < 1 (cap/immediate
    # death/ghost-tree), or emitted differs from a sum that is itself <1.
    override = (np.isclose(emitted, 1.0) & (comp_sum < 0.999))
    non_ov = ~override
    d = np.abs(comp_sum[non_ov] - emitted[non_ov])
    rep["mort_sum_identity"] = {
        "n_total": int(len(emitted)),
        "n_override_excluded": int(override.sum()),
        "n_checked": int(non_ov.sum()),
        "max_abs_err": float(np.nanmax(d)) if d.size else None,
        "mean_abs_err": float(np.nanmean(d)) if d.size else None,
        "pass_1e-6": bool(np.nanmax(d) < 1e-6) if d.size else None,
    }

    # §7.2 temp_stress consistency: at Hainich beech never crosses [-20,54] -> mort_temp==0.
    rep["temp_stress"] = {
        "max_emitted_mort_temp": float(np.nanmax(trees["mort_temp"].to_numpy())),
        "all_zero": bool(np.allclose(trees["mort_temp"].to_numpy(), 0.0)),
        "note": "daily-temp day-count cross-check deferred to scale-up (needs the .clm forcing)",
    }

    # growth_eff invertibility coverage (tier-1 diagnostic; exact needs tier-3 nind/turnover)
    gi = df["growth_eff_invertible"].to_numpy()
    rep["growth_eff_inversion"] = {
        "n": int(len(gi)),
        "n_invertible": int(np.nansum(gi)),
        "frac_invertible": float(np.nanmean(gi)),
        "note": "non-invertible rows have mort_npp>=mort_max (counter>0 or cap); need tier-3 bm_inc_counter",
    }

    # §7.3 budget tie-out (tier-1 approximate): per (cell,year) sum of per-individual npp
    #      vs the stand; exact per-individual bm_inc budget needs tier-3 nind. Report the
    #      cell/year total npp so the coupled 1e-6 gate can be cross-witnessed later.
    npp_cell = (feat.group_by(["Cell", "Year"]).agg(pl.col("npp").sum().alias("npp_sum"))
                .sort(["Cell", "Year"]))
    rep["npp_budget"] = {
        "note": "tier-1: sum of emitted per-individual npp per (cell,year); exact bm_inc budget needs tier-3",
        "n_cell_years": int(npp_cell.height),
        "npp_sum_range": [float(npp_cell["npp_sum"].min()), float(npp_cell["npp_sum"].max())],
    }
    return rep


FIXTURE_COLS = [
    "Cell", "Year", "Patch", "ID", "Type", "Age", "age_mort", "isdead",
    # distribution (S-owned targets)
    "Height", "SLA", "Wooddens", "beta_root", "LAI", "fpc_ind", "agb", "vegc",
    # flux features (ADR 0020 §1a) mapped to FToS
    "bm_inc", "growth_eff", "growth_eff_invertible", "water_stress", "temp_stress",
    "mort_npp", "mort_age", "mort_water", "mort_temp", "mort", "mort_max",
    # within-year flux statistics (ADR 0020: extremes/timing)
    "gpp_peak", "gpp_peak_doy", "transp_peak", "transp_gs_mean",
    "rootmoist_eoy", "rootmoist_gs_mean", "rootmoist_min",
    # slow bioclimatic boundary (ADR 0020 §1c) + AR state
    "eco_diag_gdd_5", "tas_cold_month", "soil_code", "soil_depth", "co2",
    "prev_n_trees", "prev_Height_q50", "prev_Wooddens_q50",
]


def _write_fixture(feat: pl.DataFrame, out_dir: str) -> None:
    """Small committed fixture: Hainich beech, years 2000/2010/2018, compact columns."""
    fx = feat.filter(
        (pl.col("Cell") == 42490) & (pl.col("Type") == 3)
        & (pl.col("Year").is_in([2000, 2010, 2018])) & (pl.col("Patch") <= 2)
    )
    cols = [c for c in FIXTURE_COLS if c in fx.columns]
    fx = fx.select(cols)
    ref_dir = _REPO / "test" / "testitems" / "references"
    ref_dir.mkdir(parents=True, exist_ok=True)
    path = ref_dir / "slow_flux_table_hainich.csv"
    header_comment = (
        "# Flux-conditioning training-table fixture for Component S (ADR 0020/0021).\n"
        "# Hainich (global-grid cell 42490), beech (Type 3), patches 0-2, years 2000/2010/2018.\n"
        "# Built by scripts/build_slow_flux_table.py from the tier-1 annual ind parquet\n"
        "# + daily set; flux features are FToS-mapped (see the script header). seed1.\n"
    )
    body = fx.write_csv(file=None, float_precision=6)  # returns the CSV as a string
    path.write_text(header_comment + body)
    print(f"== wrote fixture {path} ({fx.height} rows)")

    # also write a schema JSON alongside (committed) documenting the full-table columns
    schema = {"columns": {c: str(feat.schema[c]) for c in feat.columns}}
    (ref_dir / "slow_flux_table_schema.json").write_text(json.dumps(schema, indent=2))
    print(f"== wrote schema {ref_dir / 'slow_flux_table_schema.json'}")


def main() -> int:
    cells = [int(c) for c in os.environ.get("CELLS", "42490").split(",") if c.strip()]
    seed = int(os.environ.get("SEED", "1"))
    out_dir = os.environ.get("OUT", "/p/tmp/jamirp/slow_flux")
    print(f"== build_slow_flux_table: cells={cells} seed={seed} out={out_dir}")
    res = build(cells, seed, out_dir)
    print("== validation report:")
    print(json.dumps({k: v for k, v in res.items()
                      if k not in ("table", "demography", "report")}, indent=2, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
