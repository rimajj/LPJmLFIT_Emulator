#!/usr/bin/env python3
"""explore_de_sh_climate_ext.py — LINE X, Germany data-driven emulator, shared item SH1.

CLIMATE EXTENSION + FROZEN-MEAN CLIMATOLOGY, built once and used by all four tracks.

v2 (2026-10-01) — OWNER DECISION: only the clean 1985-2044 truth is used. The 2071-2100 and 3071-3100 production
segments read the relative-humidity file as specific humidity (VPD = 0, no water-stress mortality), so every tree
year from 2071 on is excluded (registry v2: segments.excluded / splits role 'excluded_rh_off'). In this table:
  * the CLIMATE rows 1950-2100 are all kept (the forcing itself is correct; 2045-2070 is needed for the optional
    free-run continuation checked on cell aggregates, and 2071-2100 for a future re-run with the setting fixed);
  * `excluded` / `exclusion_reason` / `truth_usable` mark every climate year whose native production segment is
    excluded in the registry (derived from SH0 segments, not hard-coded) — consumers must filter on them, or use
    scan_ext() which drops them by default;
  * the vpd_*_eff columns (and their anomalies) are NULL on excluded rows: their only meaning is "what the C saw",
    and the C runs that saw those years are unusable;
  * out-of-range thresholds come from the registry-v2 training roles only (h1985 + w2015, i.e. 1985-2044); no
    window name is hard-coded;
  * the mort_temp reproduction gate reads only the non-excluded member windows (4 h1985 + 12 w2015).
v1 (whose thresholds included 2071-2100 training years) is kept in shared/climate/_superseded_v1_pre_owner_exclusion/.

Inputs (read-only): the round-1 climate tables /p/tmp/jamirp/X_de/climate/cell_year.parquet (built by
scripts/explore_de_climate.py), the daily temperature forcing the production runs read (re-read here with the
same header-driven reader), the SH0 registry /p/tmp/jamirp/X_de/shared/registry/, the per-PFT mortality
parameter table test/testitems/references/S_pft_mortality_params.csv (generated from the live par file by
cpp; re-verified against cpp here), and the dev tree tables for the gates.

Outputs (only under /p/tmp/jamirp/X_de/shared/climate/):
  cell_year_ext.parquet  key (gcm, scen, Cell, Year), SAME layout as climate/cell_year (Historical 1950-2014
                         stored once under scen='Historical', each ssp 2015-2100; join on (gcm, clim_scen,
                         Cell, clim_year) from SH0 segments). Columns:
      tstress_pft<k>      for every TREE PFT k of the parameter table (0..6 here): number of days in the C's
                          accumulator window (day 15..365, i.e. after the day-14 reset of tempstress_tree.c)
                          with daily air T < temp_stressed.low OR > temp_stressed.high of that PFT (Int16).
                          The C reads climate->temp (daily_natural.c:133), the same daily air temperature.
      rh_on_native        the humidity-config flag of the segment that NATIVELY used this climate year in the
                          production runs (Historical + 2015-2070: 1; 2071-2100: 0). NOT climate.
      vpd_mean_eff, vpd_jja_eff, vpd_win10_sum_eff = base * rh_on_native (critic gap 4 (2)). In the truth an
                          rh-off segment reads RH as specific humidity -> VPD == 0 -> water stress 0.
                          !! Valid ONLY for a trajectory year whose own rh_on equals rh_on_native (every year
                          <= 2070 of a real-climate run). For a climate-blind replicate or the frozen mean,
                          recompute with effective_vpd(df, rh_on_of_trajectory_year). NULL where `excluded`.
      excluded, exclusion_reason, truth_usable  registry-v2 exclusion of the climate year's native production
                          segment (2071-2100 here: humidity read wrongly). truth_usable = not excluded.
      anom_<f>            f minus the same gcm's 1985-2014 Historical mean of f in that cell, for every annual
                          feature (ANNUAL_COLS except wind, the *_tr20 means, tstress_pft*, the *_eff columns).
      out_of_range        DEFAULT flag = oor_DEV-A (below). tmean_ann > the max tmean_ann over all training
                          cell-years of split DEV-A (registry-v2 role train/train_twin: MPI-ESM1-2-HR Historical
                          1985-2014 + ssp126/ssp370 2015-2044; dev cells of folds 1-4).
      oor_<split>, oor_margin_tmean_<split>  the same for every split of SH0 splits.parquet (cellset dev_f1234);
                          margin = tmean_ann - threshold (K; > 0 means out of range).
      oor_cell_<split>, oor_cell_margin_tmean_<split>  DIAGNOSTIC per-cell version: above the max tmean_ann of the
                          SAME cell's training-climate years (defined for held-out cells too; climate is not
                          held out). Not pre-registered; the pre-registered flag is out_of_range / oor_<split>.
  clim8514.parquet       key (gcm, Cell): the per-cell 1985-2014 Historical mean (float64) of EVERY numeric
                         column of cell_year (incl. monthly and wind, for completeness) and of tstress_pft*,
                         vpd_*_eff (= base, since rh_on is 1 throughout 1985-2014). This is the frozen-mean
                         climate of the CB-mean arm. Its anomalies are 0 by definition; its *_eff must be
                         recomputed with the trajectory year's rh_on (segment flags stay live in CB runs).
  oor_thresholds.parquet (split, cellset, feature, stat, value, n_cell_years, basis): out-of-range thresholds
                         for every split and cellset (dev_f1234, dev_all, dev_xfit<k> = dev cells not in fold k,
                         all_f1234, all_xfit<k>), features tmean_ann / twarm_month / gdd5, stats max and min.
  _gates.json, _report.json, _README.md

Wind is never a feature. CO2 is never a feature (standing owner decision).

STAGES (arg 1): tstress | assemble | gates | all   (SLURM: it re-reads the daily forcing)
Nothing Germany-specific is hard-coded: cell count, year span and PFT set come from the file headers, the
climate table and the parameter table.
"""

from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
OUT = os.path.join(XDE, "shared", "climate")
PARTS = os.path.join(OUT, "parts")
CLIM = os.path.join(XDE, "climate")
REG = os.path.join(XDE, "shared", "registry")
CELL_YEAR = os.path.join(CLIM, "cell_year.parquet")
CELL_STATIC = os.path.join(CLIM, "cell_static.parquet")
EXT = os.path.join(OUT, "cell_year_ext.parquet")
C8514 = os.path.join(OUT, "clim8514.parquet")
THR = os.path.join(OUT, "oor_thresholds.parquet")
PFT_CSV = os.path.join(REPO, "test", "testitems", "references", "S_pft_mortality_params.csv")

KEY = ["gcm", "scen", "Cell", "Year"]
WIN_START0 = 14  # 0-based day index of day 15: tempstress_tree.c resets on day 14 AFTER that day's increment
BASE_YEARS = (1985, 2014)  # the frozen-mean / anomaly base period (Historical)
EFF_SRC = ["vpd_mean", "vpd_jja", "vpd_win10_sum"]
EFF_COLS = [f"{c}_eff" for c in EFF_SRC]
OOR_FEATURES = ["tmean_ann", "twarm_month", "gdd5"]
TRAIN_ROLES = ("train", "train_twin")  # registry v2: these roles never touch an excluded window
GATE_MEMBER = "MPI-ESM1-2-HR_ssp370_s1_w2015"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ----------------------------------------------------------------------------------------------- params
def pft_temp_params(path: str = PFT_CSV) -> pl.DataFrame:
    """Per tree PFT: pft_id, temp_low, temp_high, mort_temp_factor, ndayyear (from the generated CSV)."""
    df = pl.read_csv(path, comment_prefix="#")
    return df.select(
        pl.col("pft_id").cast(pl.Int32),
        pl.col("temp_low").cast(pl.Float64),
        pl.col("temp_high").cast(pl.Float64),
        pl.col("mort_temp_factor").cast(pl.Float64),
        pl.col("ndayyear").cast(pl.Float64),
    ).sort("pft_id")


def tstress_cols(params: pl.DataFrame | None = None) -> list[str]:
    params = pft_temp_params() if params is None else params
    return [f"tstress_pft{k}" for k in params["pft_id"].to_list()]


def mort_temp_from_count(n, factor=5.0, ndayyear=365.0):
    """mortality_tree_ind.c:124-126: mort_temp = min(1, mort_temp_factor * temp_stress / NDAYYEAR)."""
    return np.minimum(1.0, factor * np.asarray(n, dtype=np.float64) / ndayyear)


def effective_vpd(df: pl.DataFrame | pl.LazyFrame, rh_on: str = "rh_on"):
    """Recompute vpd_*_eff = vpd_* x rh_on with the TRAJECTORY year's rh_on (use for climate-blind replicates,
    and the frozen mean, where the climate year's native flag is not the run's)."""
    return df.with_columns([(pl.col(s).cast(pl.Float64) * pl.col(rh_on).cast(pl.Float64)).cast(pl.Float32)
                            .alias(e) for s, e in zip(EFF_SRC, EFF_COLS, strict=True)])


def oor_threshold(split: str, cellset: str = "dev_f1234", feature: str = "tmean_ann", stat: str = "max") -> float:
    t = pl.read_parquet(THR).filter(pl.col("split") == split, pl.col("cellset") == cellset,
                                    pl.col("feature") == feature, pl.col("stat") == stat)
    if t.height != 1:
        raise KeyError(f"no unique threshold for {split}/{cellset}/{feature}/{stat}")
    return float(t["value"][0])


def scan_ext(include_excluded: bool = False) -> pl.LazyFrame:
    """cell_year_ext, by default WITHOUT the excluded climate years (owner decision 2026-10-01)."""
    lf = pl.scan_parquet(EXT)
    return lf if include_excluded else lf.filter(~pl.col("excluded"))


# ----------------------------------------------------------------------------------------------- tstress
def _leg_list():
    import explore_de_climate as ec

    return [(g, leg) for g in ec.GCMS for leg in ec.LEGS]


def tstress_leg(args):
    """Re-read one (gcm, leg) daily temperature file and count per-PFT stress days in the C window."""
    gcm, leg = args
    import explore_de_climate as ec
    from build_transient_boundary import open_clm

    t0 = time.time()
    params = pft_temp_params()
    ids = params["pft_id"].to_list()
    lo = params["temp_low"].to_numpy()
    hi = params["temp_high"].to_numpy()
    path = ec.forcing_path(gcm, leg, "temp")
    h, _ = ec.read_lpj_header(path)  # size == header-implied, else FATAL
    mm, firstyear, ncell, nbands, scalar = open_clm(path)
    if nbands != 365:
        raise SystemExit(f"FATAL {path}: nbands {nbands} != 365 (noleap daily)")
    ny = mm.shape[0]
    cols = {f"tstress_pft{k}": [] for k in ids}
    hi_hits = 0
    tmin, tmax = np.inf, -np.inf
    for iy in range(ny):
        T = np.asarray(mm[iy], dtype=np.float64) * scalar  # (ncell, 365), float32 -> double as the C does
        w = T[:, WIN_START0:]
        tmin, tmax = min(tmin, float(w.min())), max(tmax, float(w.max()))
        for j, k in enumerate(ids):
            above = w > hi[j]
            hi_hits += int(above.sum())
            cols[f"tstress_pft{k}"].append(((w < lo[j]) | above).sum(1).astype(np.int16))
    years = np.repeat(np.arange(firstyear, firstyear + ny, dtype=np.int32), ncell)
    cells = np.tile(np.arange(ncell, dtype=np.int32), ny)
    df = pl.DataFrame({"gcm": [gcm] * len(years), "scen": [leg] * len(years), "Cell": cells, "Year": years,
                       **{c: np.concatenate(v) for c, v in cols.items()}})
    os.makedirs(PARTS, exist_ok=True)
    out = os.path.join(PARTS, f"tstress_{gcm}_{leg}.parquet")
    df.write_parquet(out)
    info = dict(gcm=gcm, leg=leg, path=path, firstyear=firstyear, nyear=ny, ncell=ncell, scalar=scalar,
                version=h["version"], datatype=h["datatype"], rows=df.height, high_threshold_hits=hi_hits,
                window_tmin=tmin, window_tmax=tmax, seconds=round(time.time() - t0, 1))
    with open(out.replace(".parquet", ".json"), "w") as fh:
        json.dump(info, fh, indent=1)
    log(f"tstress {gcm} {leg}: {df.height} rows, T in window [{tmin:.2f}, {tmax:.2f}], "
        f"high-threshold hits {hi_hits}, {time.time() - t0:.0f}s")
    return out


def stage_tstress():
    from multiprocessing import get_context

    jobs = _leg_list()
    nproc = min(len(jobs), max(1, int(os.environ.get("SLURM_CPUS_PER_TASK", "8"))))
    with get_context("spawn").Pool(nproc) as pool:
        for p in pool.imap_unordered(tstress_leg, jobs):
            log("part done", p)


# ----------------------------------------------------------------------------------------------- assemble
def annual_feature_cols(cy_cols: list[str]) -> list[str]:
    import explore_de_climate as ec

    base = [c for c in ec.ANNUAL_COLS if not c.startswith("wind")] + list(ec.TR20_COLS)
    missing = [c for c in base if c not in cy_cols]
    if missing:
        raise SystemExit(f"FATAL cell_year lacks {missing}")
    return base


def training_climate_keys(split: str) -> pl.DataFrame:
    """(gcm, clim_scen, clim_year) of every tree year (+ pair start years) of the split's training windows."""
    sp = pl.read_parquet(os.path.join(REG, "splits.parquet"))
    mem = pl.read_parquet(os.path.join(REG, "members.parquet"))
    seg = pl.read_parquet(os.path.join(REG, "segments.parquet"))
    tr = (sp.filter(pl.col("split") == split, pl.col("role").is_in(TRAIN_ROLES))
          .select("gcm", "scen", "seed", "win", "src_member").unique())
    rows = []
    for r in tr.iter_rows(named=True):
        m = mem.filter(pl.col("member") == r["src_member"])
        if m.height != 1:
            raise SystemExit(f"FATAL member {r['src_member']} not unique in members.parquet ({m.height})")
        if m["excluded"][0]:
            raise SystemExit(f"FATAL training role on an excluded member {r['src_member']}")
        yrs = sorted(set(m["years_complete"][0].to_list()) | set(m["usable_pair_years"][0].to_list()))
        s = seg.filter(pl.col("gcm") == r["gcm"], pl.col("scen") == r["scen"], pl.col("seed") == r["seed"],
                       pl.col("Year").is_in(yrs))
        if s.height != len(yrs):
            raise SystemExit(f"FATAL segments miss years for {r}: {s.height} of {len(yrs)}")
        if s["excluded"].any() or s["clim_recycled"].any():
            raise SystemExit(f"FATAL training years of {r} touch an excluded or recycled segment")
        rows.append(s.select("gcm", "clim_scen", "clim_year"))
    return pl.concat(rows).unique().sort("gcm", "clim_scen", "clim_year")


def cellsets() -> dict[str, list[int]]:
    f = pl.read_parquet(os.path.join(REG, "folds.parquet"))
    folds = sorted(f["fold"].unique().to_list())
    out = {}
    for scope, sub in (("dev", f.filter(pl.col("is_dev"))), ("all", f)):
        out[f"{scope}_all"] = sub["Cell"].to_list()
        out[f"{scope}_f{''.join(str(k) for k in folds[:-1])}"] = sub.filter(pl.col("fold") != folds[-1])["Cell"].to_list()
        for k in folds:
            out[f"{scope}_xfit{k}"] = sub.filter(pl.col("fold") != k)["Cell"].to_list()
    return out


def build_thresholds(cy: pl.DataFrame) -> pl.DataFrame:
    splits = sorted(pl.read_parquet(os.path.join(REG, "splits.parquet"))["split"].unique().to_list())
    cs = cellsets()
    rows = []
    for split in splits:
        keys = training_climate_keys(split).rename({"clim_scen": "scen", "clim_year": "Year"})
        sub = cy.join(keys, on=["gcm", "scen", "Year"], how="semi")
        basis = "; ".join(f"{g}/{s}:{d['Year'].min()}-{d['Year'].max()} ({d.height} yr)" for (g, s), d in
                          keys.group_by(["gcm", "scen"], maintain_order=True))
        for cname, cells in cs.items():
            sc = sub.filter(pl.col("Cell").is_in(cells))
            for feat in OOR_FEATURES:
                v = sc[feat].cast(pl.Float64)
                for stat, val in (("max", v.max()), ("min", v.min())):
                    rows.append(dict(split=split, cellset=cname, feature=feat, stat=stat, value=float(val),
                                     n_cell_years=sc.height, n_cells=len(cells), basis=basis))
    return pl.DataFrame(rows)


def stage_assemble():
    t0 = time.time()
    params = pft_temp_params()
    ts_cols = tstress_cols(params)
    cy = pl.read_parquet(CELL_YEAR)
    n_cy = cy.height
    if cy.select(KEY).n_unique() != n_cy:
        raise SystemExit("FATAL cell_year key not unique")
    parts = [os.path.join(PARTS, f"tstress_{g}_{leg}.parquet") for g, leg in _leg_list()]
    ts = pl.concat([pl.read_parquet(p) for p in parts])
    if ts.select(KEY).n_unique() != ts.height:
        raise SystemExit("FATAL tstress parts key not unique")
    log(f"cell_year {n_cy} rows, tstress {ts.height} rows")
    df = cy.join(ts, on=KEY, how="left", validate="1:1")
    if df.height != n_cy or df.select(pl.any_horizontal([pl.col(c).is_null() for c in ts_cols]).sum()).item():
        raise SystemExit("FATAL tstress join incomplete")

    # native humidity flag of the climate year (seed-independent; asserted)
    seg = pl.read_parquet(os.path.join(REG, "segments.parquet"))
    nat = (seg.filter(~pl.col("clim_recycled"))
           .select("gcm", pl.col("clim_scen").alias("scen"), pl.col("clim_year").alias("Year"), "rh_on")
           .group_by(["gcm", "scen", "Year"]).agg(pl.col("rh_on").n_unique().alias("nu"),
                                                  pl.col("rh_on").first().alias("rh_on_native")))
    if nat["nu"].max() != 1:
        raise SystemExit("FATAL rh_on differs between trajectories sharing one climate year")
    nat = nat.drop("nu").with_columns(pl.col("Year").cast(pl.Int32), pl.col("rh_on_native").cast(pl.Int8))
    df = df.join(nat, on=["gcm", "scen", "Year"], how="left", validate="m:1")
    if df["rh_on_native"].null_count():
        raise SystemExit(f"FATAL rh_on_native missing for {df['rh_on_native'].null_count()} rows")
    # registry-v2 exclusion of the climate year's native production segment (owner decision 2026-10-01)
    exc = (seg.filter(~pl.col("clim_recycled"))
           .select("gcm", pl.col("clim_scen").alias("scen"), pl.col("clim_year").alias("Year"), "excluded",
                   pl.col("exclusion_reason").fill_null(""))
           .group_by(["gcm", "scen", "Year"]).agg(pl.col("excluded").n_unique().alias("nu"),
                                                  pl.col("excluded").first().alias("excluded"),
                                                  pl.col("exclusion_reason").unique().sort().str.join("|")
                                                  .alias("exclusion_reason")))
    if exc["nu"].max() != 1:
        raise SystemExit("FATAL exclusion differs between trajectories sharing one climate year")
    exc = exc.drop("nu").with_columns(pl.col("Year").cast(pl.Int32))
    df = df.join(exc, on=["gcm", "scen", "Year"], how="left", validate="m:1")
    if df["excluded"].null_count():
        raise SystemExit(f"FATAL exclusion flag missing for {df['excluded'].null_count()} rows")
    df = df.with_columns((~pl.col("excluded")).alias("truth_usable"),
                         pl.when(pl.col("excluded")).then(pl.col("exclusion_reason")).otherwise(pl.lit(None))
                         .alias("exclusion_reason"))
    df = effective_vpd(df, "rh_on_native")
    # what the C saw in an excluded year is unusable: NULL, so no consumer can train on it by accident
    df = df.with_columns([pl.when(pl.col("excluded")).then(pl.lit(None, dtype=pl.Float32)).otherwise(pl.col(e))
                          .alias(e) for e in EFF_COLS])

    # anomalies against the same gcm's 1985-2014 Historical cell mean
    feats = annual_feature_cols(cy.columns) + ts_cols + EFF_COLS
    num_cols = [c for c in cy.columns if c not in KEY] + ts_cols + EFF_COLS
    base = df.filter(pl.col("scen") == "Historical", pl.col("Year").is_between(*BASE_YEARS))
    nby = BASE_YEARS[1] - BASE_YEARS[0] + 1
    c8514 = (base.group_by(["gcm", "Cell"])
             .agg([pl.len().alias("n_years")] + [pl.col(c).cast(pl.Float64).mean().alias(c) for c in num_cols])
             .sort("gcm", "Cell"))
    if c8514["n_years"].min() != nby or c8514["n_years"].max() != nby:
        raise SystemExit("FATAL base period incomplete")
    if c8514.select("gcm", "Cell").n_unique() != c8514.height:
        raise SystemExit("FATAL clim8514 key not unique")
    c8514.write_parquet(C8514)
    log(f"clim8514: {c8514.height} rows x {len(num_cols)} columns")
    m = c8514.select(["gcm", "Cell"] + [pl.col(c).alias(f"__m_{c}") for c in feats])
    df = df.join(m, on=["gcm", "Cell"], how="left", validate="m:1")
    df = df.with_columns([(pl.col(c).cast(pl.Float64) - pl.col(f"__m_{c}")).cast(pl.Float32).alias(f"anom_{c}")
                          for c in feats]).drop([f"__m_{c}" for c in feats])

    # out-of-range thresholds per split (and per cellset)
    thr = build_thresholds(cy)
    thr.write_parquet(THR)
    splits = sorted(thr["split"].unique().to_list())
    oor_cols = []
    for split in splits:
        v = thr.filter(pl.col("split") == split, pl.col("cellset") == "dev_f1234", pl.col("feature") == "tmean_ann",
                       pl.col("stat") == "max")["value"].item()
        oor_cols += [(pl.col("tmean_ann").cast(pl.Float64) > v).alias(f"oor_{split}"),
                     (pl.col("tmean_ann").cast(pl.Float64) - v).cast(pl.Float32).alias(f"oor_margin_tmean_{split}")]
    df = df.with_columns(oor_cols).with_columns(pl.col("oor_DEV-A").alias("out_of_range"))
    # DIAGNOSTIC per-cell version: tmean_ann above the max of the SAME cell's training-climate years (climate is
    # not the held-out quantity, so this is defined for held-out cells too). Measures warming extrapolation at a
    # place, which the global absolute threshold above cannot see (a cold cell warmed by 3 K stays "in range").
    for split in splits:
        keys = training_climate_keys(split).rename({"clim_scen": "scen", "clim_year": "Year"})
        cmax = (cy.join(keys, on=["gcm", "scen", "Year"], how="semi").group_by("Cell")
                .agg(pl.col("tmean_ann").cast(pl.Float64).max().alias("__cmax")))
        df = (df.join(cmax, on="Cell", how="left", validate="m:1")
              .with_columns((pl.col("tmean_ann").cast(pl.Float64) - pl.col("__cmax")).cast(pl.Float32)
                            .alias(f"oor_cell_margin_tmean_{split}"))
              .with_columns((pl.col(f"oor_cell_margin_tmean_{split}") > 0).alias(f"oor_cell_{split}"))
              .drop("__cmax"))

    keep = KEY + ["excluded", "exclusion_reason", "truth_usable"] + ts_cols + ["rh_on_native"] + EFF_COLS + [f"anom_{c}" for c in feats] + ["out_of_range"] + \
        [c for s in splits for c in (f"oor_{s}", f"oor_margin_tmean_{s}", f"oor_cell_{s}",
                                     f"oor_cell_margin_tmean_{s}")]
    ext = df.select(keep).sort(KEY)
    if ext.select(KEY).n_unique() != ext.height:
        raise SystemExit("FATAL ext key not unique")
    ext.write_parquet(EXT)
    log(f"wrote {EXT}: {ext.height} rows x {ext.width} cols in {time.time() - t0:.0f}s")


# ----------------------------------------------------------------------------------------------- context
RESP_FEATURES = ["tmean_ann", "twarm_month", "gdd5", "prec_jja", "cwb_jja", "vpd_jja_eff", "tstress_pft2"]
RESP_PERIODS = {"w2015": (2015, 2044), "c2045": (2045, 2070), "h1985": (1985, 2014)}


def climate_response_context(ext: pl.DataFrame, cy: pl.DataFrame, cells: list[int]) -> list[dict]:
    """Size of the CLIMATE signal the clean data can test, per dev cell: the between-scenario contrast of 30-yr
    (26-yr for 2045-2070) means at fixed GCM, and the change against 1985-2014, each as a z-score against the
    cell's own interannual variability (z = diff / sqrt(var_a/n_a + var_b/n_b)). Climate only; the vegetation
    signal-to-noise against the two-seed spread is the scorer's job (SH14)."""
    d = (cy.select(KEY + [c for c in RESP_FEATURES if c in cy.columns])
         .join(ext.select(KEY + [c for c in RESP_FEATURES if c not in cy.columns] + ["excluded"]), on=KEY,
               validate="1:1").filter(pl.col("Cell").is_in(cells), ~pl.col("excluded")))
    per = []
    for name, (y0, y1) in RESP_PERIODS.items():
        sub = d.filter(pl.col("Year").is_between(y0, y1))
        if name == "h1985":
            sub = sub.filter(pl.col("scen") == "Historical")
        per.append(sub.group_by(["gcm", "scen", "Cell"]).agg(
            [pl.lit(name).alias("period"), pl.len().alias("n")]
            + [pl.col(c).cast(pl.Float64).mean().alias(f"m_{c}") for c in RESP_FEATURES]
            + [pl.col(c).cast(pl.Float64).var().alias(f"v_{c}") for c in RESP_FEATURES]))
    agg = pl.concat(per)
    if agg.select("gcm", "scen", "Cell", "period").n_unique() != agg.height:
        raise SystemExit("FATAL response-context key not unique")
    out = []
    sc = sorted(s for s in agg["scen"].unique().to_list() if s != "Historical")
    comps = [("between_scen", a, "w2015", "ssp126", "w2015") for a in sc if a != "ssp126"]
    comps += [("between_scen", a, "c2045", "ssp126", "c2045") for a in sc if a != "ssp126"]
    comps += [("change", a, "w2015", "Historical", "h1985") for a in sc]
    for gcm in sorted(agg["gcm"].unique().to_list()):
        for stat, a, pa, b, pb in comps:
            A = agg.filter(pl.col("gcm") == gcm, pl.col("scen") == a, pl.col("period") == pa)
            B = agg.filter(pl.col("gcm") == gcm, pl.col("scen") == b, pl.col("period") == pb)
            j = A.join(B, on="Cell", suffix="_b", validate="1:1")
            for c in RESP_FEATURES:
                diff = (j[f"m_{c}"] - j[f"m_{c}_b"]).to_numpy()
                se = np.sqrt(j[f"v_{c}"].to_numpy() / j["n"].to_numpy() + j[f"v_{c}_b"].to_numpy() / j["n_b"].to_numpy())
                with np.errstate(divide="ignore", invalid="ignore"):
                    z = np.where(se > 0, diff / se, np.where(diff == 0, 0.0, np.inf * np.sign(diff)))
                out.append(dict(gcm=gcm, stat=stat, a=f"{a}:{pa}", b=f"{b}:{pb}", feature=c, n_cells=j.height,
                                median_diff=round(float(np.median(diff)), 4),
                                p05_diff=round(float(np.quantile(diff, 0.05)), 4),
                                p95_diff=round(float(np.quantile(diff, 0.95)), 4),
                                median_z=round(float(np.median(z)), 2),
                                share_abs_z_gt2=round(float(np.mean(np.abs(z) > 2)), 3)))
    return out


# ----------------------------------------------------------------------------------------------- gates
def _member_mort_temp(member: str) -> dict:
    """Per (Type) agreement of the printed mort_temp with the rule from tstress_pft<Type>, one member window."""
    t0 = time.time()
    params = pft_temp_params()
    mem = pl.read_parquet(os.path.join(REG, "members.parquet")).filter(pl.col("member") == member).row(0, named=True)
    seg = (pl.read_parquet(os.path.join(REG, "segments.parquet"))
           .filter(pl.col("gcm") == mem["gcm"], pl.col("seed") == mem["seed"],
                   pl.col("scen") == mem["scen"])
           .select("Year", "clim_scen", "clim_year", "rh_on"))
    tree_ids = params["pft_id"].to_list()
    ind = (pl.scan_parquet(mem["ind_dev_path"]).select("Year", "Cell", "Type", "mort_temp", "mort_water")
           .filter(pl.col("Type").is_in(tree_ids)).collect())
    ind = ind.with_columns(pl.col("Year").cast(pl.Int32), pl.col("Cell").cast(pl.Int32), pl.col("Type").cast(pl.Int32))
    ind = ind.join(seg, on="Year", how="left", validate="m:1")
    nmiss_seg = int(ind["clim_year"].null_count())
    cells = ind["Cell"].unique()
    ts = (pl.scan_parquet(EXT).filter(pl.col("gcm") == mem["gcm"], pl.col("Cell").is_in(cells.to_list()))
          .select(["scen", "Cell", "Year"] + tstress_cols(params)).collect())
    tl = ts.unpivot(index=["scen", "Cell", "Year"], variable_name="v", value_name="n").with_columns(
        pl.col("v").str.replace("tstress_pft", "").cast(pl.Int32).alias("Type")).drop("v")
    tl = tl.rename({"scen": "clim_scen", "Year": "clim_year"})
    j = ind.join(tl, on=["clim_scen", "Cell", "clim_year", "Type"], how="left", validate="m:1")
    nmiss = int(j["n"].null_count())
    j = j.join(params.rename({"pft_id": "Type"}), on="Type", how="left", validate="m:1")
    pred = np.minimum(1.0, j["mort_temp_factor"].to_numpy() * j["n"].to_numpy().astype(np.float64)
                      / j["ndayyear"].to_numpy())
    pr = j["mort_temp"].cast(pl.Float64).to_numpy()
    err = np.abs(pred - pr)
    tol = 6e-7 + 1e-6 * np.abs(pr)  # %g 6-significant-digit print (half unit <= 5e-7 below 1) + float32 storage
    ok = err <= tol
    # integer day-count recovery where the printed value is not capped at 1
    capped = pr >= 1.0
    nrec = np.rint(pr * j["ndayyear"].to_numpy() / j["mort_temp_factor"].to_numpy())
    int_ok = np.where(capped, j["n"].to_numpy() * j["mort_temp_factor"].to_numpy() >= j["ndayyear"].to_numpy(),
                      nrec == j["n"].to_numpy())
    out = dict(member=member, rows=int(j.height), seg_missing=nmiss_seg, clim_missing=nmiss,
               frac_match=float(ok.mean()) if j.height else None,
               frac_int_match=float(int_ok.mean()) if j.height else None,
               max_abs_err=float(err.max()) if j.height else None, n_nonzero_printed=int((pr > 0).sum()),
               n_capped=int(capped.sum()), by_type={},
               water_on_rows_rh_off=int(((j["mort_water"].to_numpy() > 0) & (j["rh_on"].to_numpy() == 0)).sum()),
               seconds=round(time.time() - t0, 1))
    tv = j["Type"].to_numpy()
    for t in np.unique(tv):
        s = tv == t
        out["by_type"][int(t)] = dict(n=int(s.sum()), frac_match=float(ok[s].mean()),
                                      frac_int_match=float(int_ok[s].mean()), max_abs_err=float(err[s].max()),
                                      n_nonzero=int((pr[s] > 0).sum()), mean_printed=float(pr[s].mean()),
                                      mean_pred=float(pred[s].mean()))
    print(time.strftime("%H:%M:%S"), f"mort_temp {member}: rows {out['rows']} match {out['frac_match']:.6f} "
          f"int {out['frac_int_match']:.6f} maxerr {out['max_abs_err']:.2e} ({out['seconds']}s)", flush=True)
    return out


def stage_gates():
    t0 = time.time()
    gates, report = [], {}
    params = pft_temp_params()
    ts_cols = tstress_cols(params)
    ext = pl.read_parquet(EXT)
    cy = pl.read_parquet(CELL_YEAR, columns=KEY + ["tmean_ann", "tstress_lt_m10", "tstress_lt_m15",
                                                   "tstress_lt_m20", "vpd_mean", "vpd_jja", "vpd_win10_sum"])

    # G0 parameter table == live par file via cpp (same expansion LPJmL uses)
    try:
        import build_mort_params_reference as bm

        live = {int(r["pft_id"]): r for r in bm.build_rows()}
        diffs = [(k, c, float(params.filter(pl.col("pft_id") == k)[c].item()), float(live[k][c]))
                 for k in params["pft_id"].to_list() for c in ("temp_low", "temp_high", "mort_temp_factor")
                 if float(params.filter(pl.col("pft_id") == k)[c].item()) != float(live[k][c])]
        gates.append(dict(name="params_csv_equal_live_cpp", pass_=not diffs,
                          detail=f"{params.height} tree PFTs; temp_low {params['temp_low'].to_list()}, temp_high "
                                 f"{params['temp_high'].unique().to_list()}, mort_temp_factor "
                                 f"{params['mort_temp_factor'].unique().to_list()}; diffs vs cpp of the live par "
                                 f"file: {diffs}"))
    except Exception as e:  # noqa: BLE001
        gates.append(dict(name="params_csv_equal_live_cpp", pass_=False, detail=f"cpp check failed: {e!r}"))

    # G1 key unique and complete, trajectory complete 1950-2100
    nu = ext.select(KEY).n_unique()
    same = ext.select(KEY).sort(KEY).equals(cy.select(KEY).sort(KEY))
    traj = []
    for (g, s), d in ext.filter(pl.col("scen") != "Historical").group_by(["gcm", "scen"], maintain_order=True):
        h = ext.filter(pl.col("gcm") == g, pl.col("scen") == "Historical")
        yrs = sorted(set(h["Year"].unique().to_list()) | set(d["Year"].unique().to_list()))
        ncell_h, ncell_s = h["Cell"].n_unique(), d["Cell"].n_unique()
        full = yrs == list(range(1950, 2101)) and h.height == ncell_h * 65 and d.height == ncell_s * 86 \
            and ncell_h == ncell_s
        traj.append(dict(gcm=g, scen=s, ok=full, years=f"{yrs[0]}-{yrs[-1]} ({len(yrs)})", cells=ncell_s))
    gates.append(dict(name="key_unique_complete_1950_2100", pass_=bool(nu == ext.height and same and
                                                                       all(t["ok"] for t in traj)),
                      detail=f"{ext.height} rows, {nu} unique keys, key set identical to cell_year: {same}; "
                             f"trajectories: {traj}"))

    # G2 tstress_pft{1,2,3} == tstress_lt_m15/m10/m20 exactly (independent code path, round 1)
    j = ext.select(KEY + ts_cols).join(cy, on=KEY, how="inner", validate="1:1")
    pairs = {}
    for k, lo in zip(params["pft_id"].to_list(), params["temp_low"].to_list(), strict=True):
        ref = {-15.0: "tstress_lt_m15", -10.0: "tstress_lt_m10", -20.0: "tstress_lt_m20"}.get(lo)
        if ref:
            nd = int((j[f"tstress_pft{k}"].cast(pl.Float64) != j[ref].cast(pl.Float64)).sum())
            pairs[f"tstress_pft{k}=={ref}"] = nd
    gates.append(dict(name="tstress_equals_round1_counts", pass_=bool(len(pairs) == 3 and
                                                                      all(v == 0 for v in pairs.values())),
                      detail=f"rows differing (of {j.height}): {pairs}"))
    # per-PFT summary
    tsum = {c: dict(mean=float(ext[c].cast(pl.Float64).mean()), max=int(ext[c].max()),
                    frac_nonzero=float((ext[c] > 0).mean())) for c in ts_cols}
    report["tstress_summary_all_rows"] = tsum
    hi_hits = {}
    for g, leg in _leg_list():
        with open(os.path.join(PARTS, f"tstress_{g}_{leg}.json")) as fh:
            info = json.load(fh)
        hi_hits[f"{g}/{leg}"] = dict(hits=info["high_threshold_hits"], tmax=info["window_tmax"],
                                     tmin=info["window_tmin"])
    report["high_threshold_hits"] = hi_hits

    # G3 vpd_eff == base * rh_on_native, and 0 exactly where rh off
    je = (ext.select(KEY + ["excluded", "rh_on_native"] + EFF_COLS)
          .join(cy.select(KEY + EFF_SRC), on=KEY, validate="1:1"))
    ju = je.filter(~pl.col("excluded"))
    bad = 0
    for s, e in zip(EFF_SRC, EFF_COLS, strict=True):
        bad += int((ju[e].cast(pl.Float64) != (ju[s].cast(pl.Float64) * ju["rh_on_native"].cast(pl.Float64))
                    .cast(pl.Float32).cast(pl.Float64)).fill_null(True).sum())
    usable_rh_off = int((ju["rh_on_native"] == 0).sum())
    exc_not_null = int(je.filter(pl.col("excluded")).select(
        pl.any_horizontal([pl.col(e).is_not_null() for e in EFF_COLS]).sum()).item())
    rh_tab = (je.group_by(["scen", "rh_on_native", "excluded"]).agg(pl.col("Year").min().alias("y0"),
              pl.col("Year").max().alias("y1"), pl.len()).sort("scen", "y0").to_dicts())
    gates.append(dict(name="vpd_eff_definition", pass_=bool(bad == 0 and usable_rh_off == 0 and exc_not_null == 0),
                      detail=f"usable rows: eff != base*rh_on_native in {bad}; usable rows with rh off "
                             f"{usable_rh_off}; excluded rows with a non-null eff {exc_not_null}; by scen: {rh_tab}"))

    # G3b exclusion flags = registry v2, and equal to the rh-off climate years (owner decision 2026-10-01)
    ex = ext.filter(pl.col("excluded"))
    ex_tab = (ex.group_by(["gcm", "scen", "exclusion_reason"]).agg(pl.col("Year").min().alias("y0"),
              pl.col("Year").max().alias("y1"), pl.col("Year").n_unique().alias("n_years"))
              .sort("gcm", "scen").to_dicts())
    off_set = ext.filter(pl.col("rh_on_native") == 0).select("gcm", "scen", "Year").unique().sort("gcm", "scen", "Year")
    ex_set = ex.select("gcm", "scen", "Year").unique().sort("gcm", "scen", "Year")
    hist_ex = int(ext.filter(pl.col("scen") == "Historical")["excluded"].sum())
    seg_r = pl.read_parquet(os.path.join(REG, "segments.parquet"))
    clean_years = (seg_r.filter(~pl.col("excluded"), ~pl.col("clim_recycled"), pl.col("scen") != "Historical")
                   ["Year"])
    usable_last = int(ext.filter(~pl.col("excluded"))["Year"].max())
    tu_ok = bool((ext["truth_usable"] == ~ext["excluded"]).all())
    gates.append(dict(name="exclusion_flags_match_registry_v2", pass_=bool(
        ex_set.equals(off_set) and hist_ex == 0 and tu_ok and ex.height > 0
        and usable_last == int(clean_years.max()) and int(ex["Year"].min()) == int(clean_years.max()) + 1),
        detail=f"{ex.height} excluded climate rows of {ext.height}; excluded (gcm,scen,Year) set == rh-off set: "
               f"{ex_set.equals(off_set)}; Historical excluded {hist_ex}; last usable year {usable_last}, last clean "
               f"ssp segment year {int(clean_years.max())}; truth_usable == not excluded: {tu_ok}; {ex_tab}"))

    # G4 anomalies: mean over 1985-2014 per (gcm, Cell) ~ 0; recompute one feature independently
    an = [c for c in ext.columns if c.startswith("anom_")]
    base = ext.filter(pl.col("scen") == "Historical", pl.col("Year").is_between(*BASE_YEARS))
    mabs = base.group_by(["gcm", "Cell"]).agg([pl.col(c).cast(pl.Float64).mean().abs().alias(c) for c in an])
    worst = {c: float(mabs[c].max()) for c in an}
    c8 = pl.read_parquet(C8514)
    scale = {c: float(c8[c.removeprefix("anom_")].abs().max()) or 1.0 for c in an}
    rel = {c: worst[c] / max(scale[c], 1e-12) for c in an}
    chk = (ext.filter(pl.col("gcm") == "ACCESS-CM2", pl.col("scen") == "ssp370", pl.col("Year") == 2044)
           .select("Cell", "anom_tmean_ann")
           .join(cy.filter(pl.col("gcm") == "ACCESS-CM2", pl.col("scen") == "ssp370", pl.col("Year") == 2044)
                 .select("Cell", "tmean_ann"), on="Cell", validate="1:1")
           .join(cy.filter(pl.col("gcm") == "ACCESS-CM2", pl.col("scen") == "Historical",
                           pl.col("Year").is_between(*BASE_YEARS))
                 .group_by("Cell").agg(pl.col("tmean_ann").cast(pl.Float64).sum().alias("s")), on="Cell"))
    ind_err = float((chk["anom_tmean_ann"].cast(pl.Float64) - (chk["tmean_ann"].cast(pl.Float64) - chk["s"] / 30.0))
                    .abs().max())
    gates.append(dict(name="anomaly_definition", pass_=bool(max(rel.values()) < 1e-5 and ind_err < 1e-5),
                      detail=f"{len(an)} anomaly columns; max over (gcm,Cell) of |mean anomaly 1985-2014| relative "
                             f"to the column scale: {max(rel.values()):.2e} (worst {max(rel, key=rel.get)}); "
                             f"independent recompute ACCESS ssp370 2044 anom_tmean_ann max err {ind_err:.2e} K"))

    # G5 clim8514 vs the round-1 cell_static c8514_* columns (computed independently in round 1)
    st = pl.read_parquet(CELL_STATIC)
    comp = {}
    for gtag, gcm in (("mpi", "MPI-ESM1-2-HR"), ("acc", "ACCESS-CM2")):
        cc = [c for c in st.columns if c.startswith(f"c8514_{gtag}_")]
        jj = c8.filter(pl.col("gcm") == gcm).join(st.select(["Cell"] + cc), on="Cell", validate="1:1")
        for c in cc:
            f = c.removeprefix(f"c8514_{gtag}_")
            d = (jj[f] - jj[c]).abs()
            comp[f"{gtag}:{f}"] = float((d / jj[c].abs().clip(lower_bound=1e-9)).max())
    worst_c = max(comp.values())
    gates.append(dict(name="clim8514_vs_round1_c8514", pass_=bool(worst_c < 1e-6),
                      detail=f"{len(comp)} columns compared over {c8.height} (gcm,Cell); max relative diff "
                             f"{worst_c:.2e} ({max(comp, key=comp.get)}); clim8514 has {c8.width - 3} value columns"))

    # G6 out_of_range thresholds and shares (dev cells, per split / member window)
    thr = pl.read_parquet(THR)
    f = pl.read_parquet(os.path.join(REG, "folds.parquet"))
    dev = f.filter(pl.col("is_dev"))["Cell"]
    sp = pl.read_parquet(os.path.join(REG, "splits.parquet"))
    mem = pl.read_parquet(os.path.join(REG, "members.parquet"))
    seg = pl.read_parquet(os.path.join(REG, "segments.parquet"))
    shares, cont, train_basis = [], [], {}
    oor_ok = True
    for split in sorted(thr["split"].unique().to_list()):
        v = thr.filter(pl.col("split") == split, pl.col("cellset") == "dev_f1234", pl.col("feature") == "tmean_ann",
                       pl.col("stat") == "max")["value"].item()
        # training cell-years themselves must never be flagged (definition check)
        keys = training_climate_keys(split).rename({"clim_scen": "scen", "clim_year": "Year"})
        trc = f.filter(pl.col("is_dev"), pl.col("fold") != f["fold"].max())["Cell"]
        tr_flag = int(ext.join(keys, on=["gcm", "scen", "Year"], how="semi")
                      .filter(pl.col("Cell").is_in(trc.to_list()))[f"oor_{split}"].sum())
        tr_cell = int(ext.join(keys, on=["gcm", "scen", "Year"], how="semi")[f"oor_cell_{split}"].sum())
        tr_last = int(keys["Year"].max())
        tr_exc = int(ext.join(keys, on=["gcm", "scen", "Year"], how="semi")["excluded"].sum())
        oor_ok &= tr_flag == 0 and tr_cell == 0 and tr_exc == 0
        train_basis[split] = dict(last_training_year=tr_last, n_training_climate_years=keys.height,
                                  training_rows_on_excluded_years=tr_exc)
        for r in sp.filter(pl.col("split") == split, ~pl.col("role").str.starts_with("excluded"))\
                   .select("gcm", "scen", "seed", "win", "role", "src_member").unique().sort("gcm", "scen", "seed", "win")\
                   .iter_rows(named=True):
            if r["seed"] != 1 and r["role"] in ("train_twin", "test_ref"):
                continue  # climate is seed-independent except the recycled 3071 map; report one seed
            m = mem.filter(pl.col("member") == r["src_member"]).row(0, named=True)
            s = seg.filter(pl.col("gcm") == r["gcm"], pl.col("scen") == r["scen"], pl.col("seed") == r["seed"],
                           pl.col("Year").is_in(m["years_complete"]))
            k = s.select("gcm", pl.col("clim_scen").alias("scen"), pl.col("clim_year").alias("Year")).unique()
            e = ext.join(k, on=["gcm", "scen", "Year"], how="semi").filter(pl.col("Cell").is_in(dev.to_list()))
            shares.append(dict(split=split, gcm=r["gcm"], scen=r["scen"], seed=r["seed"], win=r["win"],
                               role=r["role"], threshold=round(v, 4), n_cell_years=e.height,
                               share_oor=round(float(e[f"oor_{split}"].mean()), 4),
                               max_margin=round(float(e[f"oor_margin_tmean_{split}"].max()), 3),
                               share_oor_cell=round(float(e[f"oor_cell_{split}"].mean()), 4),
                               p95_cell_margin=round(float(e[f"oor_cell_margin_tmean_{split}"].quantile(0.95)), 3)))
        # optional free-run continuation 2045-2070 (clean, no tree table; checked on SH12 cell aggregates)
        tp = pl.read_parquet(os.path.join(REG, "test_pairs.parquet")).filter(pl.col("split") == split)
        for r in tp.select("gcm", "scen", "truth_seed", "free_run_last_year").unique().sort("gcm", "scen")\
                   .iter_rows(named=True):
            s = seg.filter(pl.col("gcm") == r["gcm"], pl.col("scen") == r["scen"], pl.col("seed") == r["truth_seed"],
                           pl.col("use") == "no_tree_table", ~pl.col("excluded"),
                           pl.col("Year") > r["free_run_last_year"])
            k = s.select("gcm", pl.col("clim_scen").alias("scen"), pl.col("clim_year").alias("Year")).unique()
            e = ext.join(k, on=["gcm", "scen", "Year"], how="semi").filter(pl.col("Cell").is_in(dev.to_list()))
            if e.height == 0:
                continue
            cont.append(dict(split=split, gcm=r["gcm"], scen=r["scen"], years=f"{s['Year'].min()}-{s['Year'].max()}",
                             n_cell_years=e.height, n_excluded=int(e["excluded"].sum()),
                             share_oor=round(float(e[f"oor_{split}"].mean()), 4),
                             max_margin=round(float(e[f"oor_margin_tmean_{split}"].max()), 3),
                             share_oor_cell=round(float(e[f"oor_cell_{split}"].mean()), 4),
                             p95_cell_margin=round(float(e[f"oor_cell_margin_tmean_{split}"].quantile(0.95)), 3)))
    report["oor_shares_dev"] = shares
    report["climate_response_context_dev"] = climate_response_context(ext, pl.read_parquet(CELL_YEAR),
                                                                      dev.to_list())
    report["oor_shares_dev_continuation_2045_2070"] = cont
    report["oor_training_basis"] = train_basis
    v1p = os.path.join(OUT, "_superseded_v1_pre_owner_exclusion", "oor_thresholds.parquet")
    if os.path.exists(v1p):
        v1 = pl.read_parquet(v1p).filter(pl.col("cellset") == "dev_f1234", pl.col("feature") == "tmean_ann",
                                         pl.col("stat") == "max").select("split", pl.col("value").alias("v1"))
        report["oor_threshold_v1_vs_v2_dev_f1234_tmean_max"] = (
            thr.filter(pl.col("cellset") == "dev_f1234", pl.col("feature") == "tmean_ann", pl.col("stat") == "max")
            .select("split", pl.col("value").alias("v2")).join(v1, on="split", how="left").to_dicts())
    report["oor_thresholds_dev_f1234"] = thr.filter(pl.col("cellset") == "dev_f1234").drop("basis").to_dicts()
    xf = thr.filter(pl.col("feature") == "tmean_ann", pl.col("stat") == "max",
                    pl.col("cellset").str.starts_with("dev_")).group_by("split").agg(
        pl.col("value").min().alias("min_over_dev_cellsets"), pl.col("value").max().alias("max_over_dev_cellsets"))
    report["oor_threshold_spread_over_dev_cellsets"] = xf.to_dicts()
    gates.append(dict(name="out_of_range_definition", pass_=bool(oor_ok),
                      detail="no training cell-year (dev folds 1-4, registry-v2 training roles) is flagged and none "
                             f"is an excluded year, every split; training basis {train_basis}; "
                             "thresholds dev_f1234: " + ", ".join(
                                 f"{d['split']}={d['value']:.3f}" for d in thr.filter(
                                     pl.col("cellset") == "dev_f1234", pl.col("feature") == "tmean_ann",
                                     pl.col("stat") == "max").to_dicts())))

    # G7 mort_temp reproduction: MPI ssp370 s1 w2015 dev (binding, >= 98 %) + every member window (diagnostic)
    from multiprocessing import get_context

    members = mem.filter(~pl.col("excluded"))["member"].to_list()  # never read an excluded window
    if GATE_MEMBER not in members:
        raise SystemExit(f"FATAL gate member {GATE_MEMBER} is excluded or missing")
    order = [GATE_MEMBER] + [m for m in members if m != GATE_MEMBER]
    report["mort_temp_members_skipped_excluded"] = mem.filter(pl.col("excluded"))["member"].to_list()
    nproc = min(len(order), max(1, int(os.environ.get("SLURM_CPUS_PER_TASK", "8")) // 6))
    with get_context("spawn").Pool(nproc) as pool:
        res = list(pool.imap(_member_mort_temp, order))
    report["mort_temp_by_member"] = res
    g = res[0]
    gates.append(dict(name="mort_temp_reproduced_MPI_ssp370_s1_w2015_dev",
                      pass_=bool(g["frac_match"] >= 0.98 and g["clim_missing"] == 0 and g["seg_missing"] == 0),
                      detail=f"{g['rows']} tree rows (Type<=6, all dev cells, Years of the window); printed "
                             f"mort_temp within print precision on {g['frac_match']:.6f}; integer day count "
                             f"recovered on {g['frac_int_match']:.6f}; max abs err {g['max_abs_err']:.2e}; "
                             f"nonzero printed {g['n_nonzero_printed']}, capped {g['n_capped']}; by Type "
                             + json.dumps({k: (v['n'], round(v['frac_match'], 6), v['n_nonzero'])
                                           for k, v in g["by_type"].items()})))
    allm = [r for r in res if r["rows"]]
    worst = min(allm, key=lambda r: r["frac_match"])
    gates.append(dict(name="mort_temp_reproduced_all_member_windows_dev", pass_=bool(
        all(r["frac_match"] >= 0.98 and r["clim_missing"] == 0 for r in allm)),
        detail=f"{len(allm)} non-excluded member windows (excluded ones not read); rows {sum(r['rows'] for r in allm)};"
               f" min frac_match {worst['frac_match']:.6f} ({worst['member']}); min integer-count match "
               f"{min(r['frac_int_match'] for r in allm):.6f}; max abs err {max(r['max_abs_err'] for r in allm):.2e}; "
               f"nonzero printed {sum(r['n_nonzero_printed'] for r in allm)}; clim join misses "
               f"{sum(r['clim_missing'] for r in allm)}"))

    allpass = all(gx["pass_"] for gx in gates)
    out = dict(all_pass=allpass, seconds=round(time.time() - t0, 1),
               gates=[{"name": gx["name"], "pass": gx["pass_"], "detail": gx["detail"]} for gx in gates])
    with open(os.path.join(OUT, "_gates.json"), "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    with open(os.path.join(OUT, "_report.json"), "w") as fh:
        json.dump(report, fh, indent=1, default=str)
    for gx in gates:
        log(("PASS " if gx["pass_"] else "FAIL ") + gx["name"] + " :: " + gx["detail"][:600])
    log(f"ALL PASS: {allpass}")


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    os.makedirs(OUT, exist_ok=True)
    stages = ["tstress", "assemble", "gates"] if stage == "all" else stage.split(",")
    for s in stages:
        log(f"=== stage {s}")
        {"tstress": stage_tstress, "assemble": stage_assemble, "gates": stage_gates}[s]()
    log("=== SH1 DONE")
