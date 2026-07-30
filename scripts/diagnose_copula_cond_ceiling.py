#!/usr/bin/env python3
"""Measure the CONDITIONING CEILING for the recruit-trait copula's per-cell trait medians (milestone S2).

WHY THIS EXISTS — the question S2 must answer BEFORE any lockstep conditioning change is written.

The ADR-0030 gate says the emulator's per-cell median `Wooddens` reaches `emu_r = 0.814` against an
attenuation-corrected ceiling of 0.964, and its between-cell dispersion `sd(pred)/sd(Y1)` is only 0.678 —
i.e. the prediction is UNDER-DISPERSED: it does not spread cells as widely as the truth does. S2's plan is
to widen `COPULA_COND_COLS` / `live_flux_cond`. But "add covariates" is a hypothesis, not a diagnosis, and
this line has twice taken credit for a basis fix (ADR 0033) — so measure first.

The GAP decomposes into two DIFFERENT causes, and only ONE of them a new covariate can fix:

  (a) MISSING INFORMATION — the covariates the copula is conditioned on genuinely do not determine a cell's
      trait median. Only new covariates help.
  (b) ESTIMATOR INEFFICIENCY — the information IS in the current 8 columns, but the copula's per-stem
      marginal-DRF-then-median pipeline does not extract it. New covariates would NOT help; the estimator
      would have to change.

This probe separates them with a cheap upper-bound experiment. It fits a DIRECT per-cell regressor
(LightGBM, K-fold BY CELL) of the per-cell median trait on per-cell covariate sets:

  * `cond8`      the CURRENT conditioning, reduced per cell exactly as the copula sees it (time-mean of the
                 4 flux drivers over the scenario's years + the 4 boundary columns).
  * `cond8+env`  `cond8` plus the wider per-cell climate/bioclimate descriptors already sitting in
                 `tables/cell_year_feats.parquet` (aridity, VPD, dry spells, warm-month/range, precip
                 seasonality, frost-free days, ...).
  * `env_only`   the wider set WITHOUT the flux drivers, to see whether the flux channel carries anything
                 the climate does not.

Read it as follows, per axis:

    r(cond8)      -  emu_r          =  the ESTIMATOR-INEFFICIENCY share of the GAP
    r(cond8+env)  -  r(cond8)       =  the NEW-COVARIATE headroom  <- the only part S2 can buy
    ceiling       -  r(cond8+env)   =  irreducible under this covariate universe

If `r(cond8)` already sits at the ceiling, S2's premise is WRONG and the milestone must be re-scoped to the
estimator, not the conditioning. That is a real possible outcome and must be reported as one.

CAVEAT, deliberately named: this is an UPPER BOUND on what conditioning can deliver, not a forecast. A
direct per-cell regressor is a strictly easier estimator than the copula's per-stem conditional-quantile
model (it optimizes the very statistic the gate scores, on ~54k rows instead of ~198M). So `r(cond8+env)`
overstates what an expanded copula would actually reach. It is used here only to bound the headroom and to
rank candidate covariates -- never as a claimed skill number.

SECOND CAVEAT — a per-cell TIME-MEAN of a flux driver is not what the copula conditions on. The copula sees
the (Cell, Year) row broadcast onto that year's stems. Reducing to a per-cell mean therefore DISCARDS the
within-cell year-to-year variation, which is real conditioning information. That biases `r(cond8)` DOWN, so
it inflates the apparent estimator-inefficiency share. `--flux-quantiles` adds per-cell q10/q90 of each flux
driver to recover part of that, and the difference between the two runs bounds the distortion.

Usage (SLURM; it reads ~3 GB of the copula table and ~14 GB of Xc columns):

    COPULA_DIR=/p/tmp/jamirp/emulator_global/slow_copula_historic_t8 \
    COPULA2_DIR=/p/tmp/jamirp/emulator_global/slow_copula_historic_seed2_t8 \
    SCENARIO=historic OUT=/p/tmp/jamirp/emulator_global/cond_ceiling_t8 \
      scripts/sbatch_python.sh S-condceil scripts/diagnose_copula_cond_ceiling.py

Env: COPULA_DIR, COPULA2_DIR, SCENARIO (historic|ssp370), AXES (default the 4 production axes),
     MINSTEM (20 — matches the ADR-0030 gate), KFOLDS (5), OUT (a dir for the per-cell table + report),
     FLUX_QUANTILES (1 to add per-cell q10/q90 flux features), NTREES (400), LEAVES (63).
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import numpy as np
import polars as pl

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "python" / "src"))

BASE = "/p/tmp/jamirp/emulator_global"
CELL_YEAR_FEATS = f"{BASE}/tables/cell_year_feats.parquet"
FIRSTYEAR = {"historic": 2000, "ssp370": 2020}
LASTYEAR = {"historic": 2019, "ssp370": 2100}

COPULA_DIR = os.environ.get("COPULA_DIR", f"{BASE}/slow_copula_historic_t8")
COPULA2_DIR = os.environ.get("COPULA2_DIR", f"{BASE}/slow_copula_historic_seed2_t8")
SCENARIO = os.environ.get("SCENARIO", "historic")
MINSTEM = int(os.environ.get("MINSTEM", "20"))
KFOLDS = int(os.environ.get("KFOLDS", "5"))
OUT = os.environ.get("OUT", f"{BASE}/cond_ceiling_t8")
FLUX_QUANTILES = os.environ.get("FLUX_QUANTILES", "0") == "1"
NTREES = int(os.environ.get("NTREES", "400"))
LEAVES = int(os.environ.get("LEAVES", "63"))

# The wider per-cell covariate universe: every column of cell_year_feats.parquet that is a CELL-LEVEL
# environmental descriptor. Deliberately EXCLUDES `Cell`/`Year` (identifiers), `lat` is KEPT (it is a real
# insolation/photoperiod proxy the boundary lacks), and the `*_anom` / `*_r3..r10` / `*_trend10` transient
# columns are kept out of the headline set -- they are year-relative, so a per-cell mean of them is ~0 and
# they would only add noise to a per-cell reduction.
ENV_COLS = [
    "lat", "soil_code",
    "temp_mean", "temp_sd", "prec_mean", "prec_sd", "swrad_mean", "swrad_sd",
    "lwrad_mean", "lwrad_sd", "humid_mean", "humid_sd",
    "eco_diag_vpd_mean", "eco_diag_vpd_max_monthly", "eco_diag_vpd_stress_months",
    "eco_diag_gdd_10", "eco_diag_frost_free_days",
    "eco_diag_pet_mean", "eco_diag_p_pet_ratio", "eco_diag_water_deficit_months",
    "eco_diag_dry_spell_max", "eco_diag_dry_spell_mean",
    "eco_diag_precip_intensity_wet_days", "eco_diag_precip_wettest_quarter_frac",
    "tas_warm_month", "tas_range", "pr_cv_monthly", "pr_driest_month",
]


def read_manifest(d):
    m = {}
    for ln in Path(d, "manifest_copula.txt").read_text().splitlines():
        if "\t" in ln:
            k, v = ln.split("\t", 1)
            m[k] = v
    return m


def percell_medians(table_dir, axes, with_pred):
    """Per-cell median of each axis (+ stem count), read straight off the .f64 sidecars."""
    cells = np.fromfile(Path(table_dir, "cells.i64"), dtype="<i8")
    n = cells.size
    cols = {"Cell": cells}
    for a in axes:
        cols[f"y_{a}"] = np.fromfile(Path(table_dir, f"Y_{a}.f64"), dtype="<f8")
        assert cols[f"y_{a}"].size == n, f"{table_dir}: Y_{a} length {cols[f'y_{a}'].size} != {n}"
        if with_pred:
            p = Path(table_dir, f"pred_{a}.f64")
            if p.exists():
                cols[f"p_{a}"] = np.fromfile(p, dtype="<f8")
    df = pl.DataFrame(cols)
    aggs = [pl.len().alias("nstem")]
    for a in axes:
        aggs.append(pl.col(f"y_{a}").median().alias(f"med_{a}"))
        if f"p_{a}" in cols:
            aggs.append(pl.col(f"p_{a}").median().alias(f"pred_{a}"))
    out = df.group_by("Cell").agg(aggs).sort("Cell")
    # ADR 0036 §5b: assert our own key set -- a duplicated group would silently double-weight a cell.
    assert out.select("Cell").n_unique() == out.height, "duplicated Cell in the per-cell aggregate"
    return out


def percell_flux(table_dir, cond_cols, nflux=4):
    """Per-cell mean (opt. q10/q90) of the flux-driver columns of Xc.f64, via a strided memmap read."""
    cells = np.fromfile(Path(table_dir, "cells.i64"), dtype="<i8")
    n, p = cells.size, len(cond_cols)
    X = np.memmap(Path(table_dir, "Xc.f64"), dtype="<f8", mode="r", shape=(n, p))
    cols = {"Cell": cells}
    for j in range(nflux):
        cols[cond_cols[j]] = np.asarray(X[:, j])
    df = pl.DataFrame(cols)
    aggs = []
    for j in range(nflux):
        c = cond_cols[j]
        aggs.append(pl.col(c).mean().alias(f"{c}__mean"))
        if FLUX_QUANTILES:
            aggs.append(pl.col(c).quantile(0.10).alias(f"{c}__q10"))
            aggs.append(pl.col(c).quantile(0.90).alias(f"{c}__q90"))
    out = df.group_by("Cell").agg(aggs).sort("Cell")
    assert out.select("Cell").n_unique() == out.height, "duplicated Cell in the flux aggregate"
    del X
    return out


def percell_env(scenario, cells):
    """Per-cell time-mean of the wider environmental descriptors over the scenario's years."""
    y0, y1 = FIRSTYEAR[scenario], LASTYEAR[scenario]
    have = pl.scan_parquet(CELL_YEAR_FEATS).collect_schema().names()
    use = [c for c in ENV_COLS if c in have]
    missing = [c for c in ENV_COLS if c not in have]
    if missing:
        print(f"   [warn] cell_year_feats lacks {len(missing)} requested column(s): {missing}")
    q = (
        pl.scan_parquet(CELL_YEAR_FEATS)
        .filter((pl.col("Year") >= y0) & (pl.col("Year") <= y1))
        .filter(pl.col("Cell").is_in(cells))
        .group_by("Cell")
        .agg([pl.col(c).cast(pl.Float64).mean().alias(c) for c in use])
    )
    out = q.collect().sort("Cell")
    assert out.select("Cell").n_unique() == out.height, "duplicated Cell in the env aggregate"
    return out, use


def fold_of(cell, k):
    h = hashlib.blake2b(str(int(cell)).encode(), digest_size=8).digest()
    return int.from_bytes(h, "little") % k


def kfold_r(df, feats, target, k):
    """K-fold-BY-CELL OOS fit; returns (r, R2, sd_ratio, gain-ranked feature importance)."""
    import lightgbm as lgb

    X = df.select(feats).to_numpy()
    y = df[target].to_numpy()
    folds = np.array([fold_of(c, k) for c in df["Cell"].to_numpy()])
    pred = np.full(y.shape, np.nan)
    gains = np.zeros(len(feats))
    for f in range(k):
        tr, te = folds != f, folds == f
        if te.sum() == 0 or tr.sum() < 100:
            continue
        m = lgb.LGBMRegressor(
            n_estimators=NTREES, num_leaves=LEAVES, learning_rate=0.05,
            min_child_samples=20, subsample=0.8, subsample_freq=1,
            colsample_bytree=0.8, random_state=17 + f, verbosity=-1, n_jobs=-1,
        )
        m.fit(X[tr], y[tr])
        pred[te] = m.predict(X[te])
        gains += m.booster_.feature_importance(importance_type="gain")
    ok = np.isfinite(pred)
    assert ok.all(), f"{(~ok).sum()} cells never in a test fold"
    r = float(np.corrcoef(y, pred)[0, 1])
    ss = float(1.0 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2))
    sd = float(pred.std() / y.std())
    imp = sorted(zip(feats, gains / max(gains.sum(), 1e-30)), key=lambda t: -t[1])
    return r, ss, sd, imp


def main():
    axes = os.environ.get("AXES", "").split() or ["SLA", "Wooddens", "D95max", "minwscal"]
    man = read_manifest(COPULA_DIR)
    cond_cols = man["cond_cols"].split()
    print("=" * 100)
    print("CONDITIONING-CEILING PROBE (milestone S2) — can NEW covariates close the per-cell trait GAP?")
    print("=" * 100)
    print(f"   seed1 table : {COPULA_DIR}")
    print(f"   seed2 table : {COPULA2_DIR}")
    print(f"   scenario    : {SCENARIO}   axes: {' '.join(axes)}")
    print(f"   cond_cols   : {' '.join(cond_cols)}  (ncond={man['ncond']}, n={man['n']})")
    print(f"   MINSTEM={MINSTEM}  KFOLDS={KFOLDS}  FLUX_QUANTILES={FLUX_QUANTILES}"
          f"  NTREES={NTREES} LEAVES={LEAVES}")

    print("\n-- per-cell medians (seed1, with OOS preds) ...", flush=True)
    e1 = percell_medians(COPULA_DIR, axes, with_pred=True)
    print(f"   seed1: {e1.height} cells")
    print("-- per-cell medians (seed2, the ADR-0030 floor) ...", flush=True)
    e2 = percell_medians(COPULA2_DIR, axes, with_pred=False)
    print(f"   seed2: {e2.height} cells")

    # Reproduce the ADR-0030 gate's exact cell set: >=MINSTEM in BOTH seeds.
    j = (
        e1.filter(pl.col("nstem") >= MINSTEM)
        .join(e2.filter(pl.col("nstem") >= MINSTEM), on="Cell", how="inner", suffix="_s2")
    )
    print(f"\n   GATE CELL SET: {j.height} cells (>= {MINSTEM} stems in both seeds)")

    # -------- harness validation: reproduce the DOCUMENTED emu_r / sd ratio before trusting anything ------
    print("\n" + "=" * 100)
    print("STEP 1 — HARNESS VALIDATION: reproduce the documented ADR-0030 numbers")
    print("=" * 100)
    print(f"   {'axis':10s} {'emu_r':>8s} {'floor_r':>8s} {'sd(pred)/sd(Y1)':>17s}")
    emu = {}
    for a in axes:
        y1 = j[f"med_{a}"].to_numpy()
        y2 = j[f"med_{a}_s2"].to_numpy()
        pv = j[f"pred_{a}"].to_numpy()
        er = float(np.corrcoef(y1, pv)[0, 1])
        fr = float(np.corrcoef(y1, y2)[0, 1])
        sdr = float(pv.std() / y1.std())
        emu[a] = (er, fr, sdr)
        print(f"   {a:10s} {er:8.3f} {fr:8.3f} {sdr:17.3f}")
    print("\n   Expected (t8 historic, ADR 0036 / lines/S/STATE.md): emu_r 0.881 / 0.814 / 0.791 / 0.945;"
          "\n   floor_r 0.973 / 0.937 / 0.833 / 0.973; sd ratio 0.907 / 0.678 / 0.714 / 0.970."
          "\n   If these do not match, STOP — the probe's basis is wrong, not the science.")

    # -------- build the per-cell covariate table ----------------------------------------------------------
    print("\n" + "=" * 100)
    print("STEP 2 — per-cell covariate table")
    print("=" * 100)
    print("-- flux drivers from Xc (strided memmap) ...", flush=True)
    fl = percell_flux(COPULA_DIR, cond_cols)
    flux_feats = [c for c in fl.columns if c != "Cell"]
    print(f"   {len(flux_feats)} flux features: {' '.join(flux_feats)}")

    cells = j["Cell"].to_list()
    print("-- boundary columns (per-cell, from the copula table's own Xc tail) ...", flush=True)
    n = int(man["n"])
    p = len(cond_cols)
    Xm = np.memmap(Path(COPULA_DIR, "Xc.f64"), dtype="<f8", mode="r", shape=(n, p))
    cc = np.fromfile(Path(COPULA_DIR, "cells.i64"), dtype="<i8")
    bnd_cols = cond_cols[4:]
    bdf = pl.DataFrame({"Cell": cc, **{c: np.asarray(Xm[:, 4 + i]) for i, c in enumerate(bnd_cols)}})
    bnd = bdf.group_by("Cell").agg([pl.col(c).first().alias(c) for c in bnd_cols]).sort("Cell")
    del Xm, bdf
    # co2 is a constant by ADR 0004; drop it from every feature set (a constant column is dead weight).
    bnd_feats = [c for c in bnd_cols if bnd[c].n_unique() > 1]
    dropped = [c for c in bnd_cols if c not in bnd_feats]
    print(f"   {len(bnd_feats)} boundary features: {' '.join(bnd_feats)}"
          + (f"   [dropped constant: {' '.join(dropped)}]" if dropped else ""))

    print("-- wider environmental descriptors ...", flush=True)
    env, env_feats = percell_env(SCENARIO, cells)
    print(f"   {len(env_feats)} env features")

    tbl = (
        j.select(["Cell", "nstem"] + [f"med_{a}" for a in axes] + [f"pred_{a}" for a in axes])
        .join(fl, on="Cell", how="inner")
        .join(bnd, on="Cell", how="inner")
        .join(env, on="Cell", how="inner")
    )
    print(f"\n   covariate table: {tbl.height} cells x {tbl.width} cols"
          f"   (lost {j.height - tbl.height} cells to the covariate joins)")
    assert tbl.height >= 0.98 * j.height, "covariate join lost >2% of the gate cell set"
    # NaN guard: polars is_not_null is a NO-OP for NaN (CLAUDE.md §4 / the skill's coverage-guard note).
    featall = flux_feats + bnd_feats + env_feats
    nan_counts = {c: int(tbl[c].is_nan().sum()) for c in featall if tbl[c].dtype.is_float()}
    bad = {k: v for k, v in nan_counts.items() if v}
    if bad:
        print(f"   [warn] NaN in covariates: {bad} — dropping those rows")
        tbl = tbl.drop_nans(subset=[c for c in bad])
        print(f"   -> {tbl.height} cells")

    Path(OUT).mkdir(parents=True, exist_ok=True)
    tbl.write_parquet(Path(OUT, f"percell_cond_ceiling_{SCENARIO}.parquet"))
    print(f"   wrote {Path(OUT, f'percell_cond_ceiling_{SCENARIO}.parquet')}")

    # -------- the experiment -----------------------------------------------------------------------------
    SETS = {
        "cond8": flux_feats + bnd_feats,
        "cond8+env": flux_feats + bnd_feats + env_feats,
        "env_only": bnd_feats + env_feats,
    }
    print("\n" + "=" * 100)
    print("STEP 3 — K-fold-BY-CELL direct per-cell regression (an UPPER BOUND, see the module docstring)")
    print("=" * 100)
    results = {}
    for a in axes:
        er, fr, sdr = emu[a]
        # The gate's attenuation-corrected ceiling needs rel_P (the emulator's own split-half); it is not
        # recomputed here, so quote sqrt(floor_r) as a CONSERVATIVE stand-in and label it as such.
        ceil_cons = float(np.sqrt(fr))
        print(f"\n   axis {a}:  emu_r={er:.3f}  floor_r={fr:.3f}  sd_ratio={sdr:.3f}"
              f"   [conservative ceiling sqrt(floor_r)={ceil_cons:.3f}]")
        print(f"      {'feature set':12s} {'r':>7s} {'R2':>7s} {'sd_ratio':>9s} | top gain-ranked features")
        results[a] = {}
        for name, feats in SETS.items():
            r, ss, sd, imp = kfold_r(tbl, feats, f"med_{a}", KFOLDS)
            results[a][name] = (r, ss, sd)
            top = ", ".join(f"{f}={g:.2f}" for f, g in imp[:6])
            print(f"      {name:12s} {r:7.3f} {ss:7.3f} {sd:9.3f} | {top}")
        r8 = results[a]["cond8"][0]
        rpe = results[a]["cond8+env"][0]
        print(f"      DECOMPOSITION of the GAP on {a}:")
        print(f"        estimator inefficiency  r(cond8) - emu_r      = {r8 - er:+.3f}")
        print(f"        NEW-COVARIATE headroom  r(cond8+env) - r(cond8) = {rpe - r8:+.3f}   <-- what S2 buys")
        print(f"        dispersion: sd_ratio {sdr:.3f} (emu) -> {results[a]['cond8'][2]:.3f} (cond8)"
              f" -> {results[a]['cond8+env'][2]:.3f} (cond8+env)")

    # -------- verdict ------------------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    print(f"   {'axis':10s} {'emu_r':>7s} {'r_cond8':>8s} {'r_+env':>8s} | {'estim.':>7s} {'covar.':>7s} |"
          f" {'sd emu':>7s} {'sd +env':>8s}")
    for a in axes:
        er, fr, sdr = emu[a]
        r8, _, s8 = results[a]["cond8"]
        rp, _, sp = results[a]["cond8+env"]
        print(f"   {a:10s} {er:7.3f} {r8:8.3f} {rp:8.3f} | {r8 - er:+7.3f} {rp - r8:+7.3f} |"
              f" {sdr:7.3f} {sp:8.3f}")
    print("\n   READ: a large 'estim.' column with a small 'covar.' column means S2's premise is WRONG —")
    print("   the information is already in the 8 conditioning columns and the ESTIMATOR must change,")
    print("   not the feature list. A large 'covar.' column is the case for expanding the conditioning.")
    print("\n   Remember this is an UPPER bound (direct per-cell fit on the scored statistic) and that the")
    print("   per-cell time-mean of a flux driver discards within-cell year-to-year conditioning — rerun")
    print("   with FLUX_QUANTILES=1 to bound that distortion.")


if __name__ == "__main__":
    main()
