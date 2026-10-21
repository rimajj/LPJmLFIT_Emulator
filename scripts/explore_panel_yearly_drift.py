#!/usr/bin/env python3
"""explore_panel_yearly_drift.py -- the YEAR-BY-YEAR NO-DRIFT TEST of the structure map (STATE NEXT item 5; ADR 0318
sec. 4 item 2: "the structure map is not recursive ... that property has to be SHOWN on a year-by-year run").

THE DEPLOYED FORM (what an Earth-system model would call each year): the best arm A7rH (ADR 0316 sec. 11-13) re-cast to
emit the state of ONE year y from
  * the trailing 30-year climate ending y (observed 2000-2019 -- all the panel's climate table holds -- in front of the
    leg's 2020-2100, so the windows ending 2020-2028 are shorter, 21-29 years) -- the 25 climate columns of
    explore_panel_a7.CLIM_COLS, as window means;
  * the cell's per-year ANCHOR: the mean over the training runs x training legs of that quantity IN YEAR y (a 1 050-cell
    x 81-year lookup table built from the original's runs; leave-one-leg-out on training rows, as A7r does per window);
    the leg climate minus the anchor legs' climate (same year, same trailing window);
  * the run's own 2000-2019 levels (s0) and their offset from the training runs' (memoff); lat, lon, soil code.
  Targets = the original's yearly state: tree count per patch (squared error on value - anchor, as A7rH), biomass per
  tree (log target, as A7rH), the four trait medians (value - anchor). LightGBM as explore_panel_a7.PARAMS, 400 rounds.
  Training rows: runs m1,m2,m3,m5,m6 x the 27 legs of the 9 other climate models x years 2020,2024,...,2100 (21).
  Test: the unseen run m4 x the held-out model's 3 scenarios x EVERY year 2020-2100. Held-out model g = each of the
  first five (HG, as ADR 0316 sec. 10-13).
  DIFFERENCE FROM A7rH, stated: no ctl_obs leg (its weather years were drawn per run, so its yearly climate differs by
  run; ADR 0316 sec. 2) and single-year targets instead of 30-year means.

THE MEASURE (ADR 0325 sec. 3's drift rule, applied to structure; ADR 0317's second-run ratio): per case (g x scenario,
15) and year y, over the DENSE cells (per-year anchor >= 5 trees per patch -- defined before the run, ADR 0329) and,
reported, all tree-bearing cells: e_X(y) = median over cells of |X - T| / T (T = m4 that year); e_R(y) = the same pooled
over a second run R in {m1, m2, m3}; rho50(y) = e_X / e_R (and rho90 at the 90th centile).
  DRIFT = mean rho50 over 2081-2100 / mean rho50 over 2021-2040 (the daily model's rule). Area totals per year, signed.

WRITTEN BEFORE THE RUN (2026-10-12; ADR 0184 -- what each null must return):
  harness  `second` (m5, a training run outside the pool, scored as the emulator): rho50 0.9-1.1 every decade,
           DRIFT 0.9-1.1. Else the measure, not the emulator, sets the number.
  null     `oracle` (mean of the 5 training runs on the SAME held-out leg and year -- never available to the emulator):
           rho50 ~ sqrt((1 + 1/5) / 2) = 0.77 (0.70-0.90), DRIFT 0.9-1.1.
  power    `persist` (m4's own 2019 state carried forward): DRIFT > 1.2 in most cases (stands change over the century).
           If it is not, the drift measure has no power on this panel and NO drift verdict is drawn from it.
  null     `anchor` (the per-year anchor alone, no climate shift): reported; its DRIFT shows what the trajectory of the
           training legs alone does.
  ARM `YA` (expectations): the map is not recursive, so its error can only grow with the held-out climate's departure
           from the training climates. Tree count and biomass per tree, dense cells: DRIFT median 1.0-1.15, <= 1.2 in
           >= 13 of 15 cases; the likeliest failures are the warmest legs (UKESM / IPSL ssp585). Typical-cell level
           rho50 averaged 2071-2100 near the window arm's (tree count ~1.3-1.5; single years are noisier, so the second
           run's own error is larger and the ratio may come out lower).
  PROPOSED PASS (ADR 0318's T1 "not yet defined numerically", mirrored from the daily model's 1.2): tree count AND
           biomass per tree, dense cells: DRIFT <= 1.2 in >= 13 of 15 cases and > 1.5 in none. The owner may move it.
RESULT 2026-10-12 (jobs 2467154-58, ADR 0330): harness and nulls as derived (second run drift 0.96-1.04, oracle ratio
0.79 / drift 1.00, persistence drift 1.9-3.0 = power). PROPOSED PASS FAILED as written: tree count drift median 1.17
(8/15 <= 1.2), biomass per tree 1.32 (2/15). The early ratio starts BELOW a second run (0.46-0.93: the run's own
2000-2019 state is known); it rises to a plateau by the 2050s (biomass per tree ~1.0, tree count ~1.1) with a slow
tree-count creep after (+0.01 / +0.07 / +0.12 ssp126 / 370 / 585); drift is scenario-independent -> mostly the fading
start state.
SOIL (ADR 0349): `fit --soil code` (default, every earlier result) feeds the soil code as a plain number; `--soil cat`
as a LightGBM categorical feature; `--soil phys` replaces it by sand, clay, ln Ks, ln Sf of the soil type
(config/soil_texture_by_code.csv). Non-default variants write preds_<g>_soil<cat|phys>.parquet (or --suffix).
RECENT (ADR 0351): `--recent y1` adds this and last year's 25 climate statistics as single-year values; `--recent x10`
adds to that the 10-year extremes of the water / heat statistics and the years since the driest of those 10 years (the
original's drought die-offs, ADR 0350). Files get suffix _recent<y1|x10>; `score --recent ...` scores that variant.
LEAK FIX (ADR 0352 sec. 0): before 2026-10-21 the training rows also held run m5 on the HELD-OUT model's three legs
(m5 is in TRAIN_M and is the test-side harness run), 7.9 % of the rows. Fixed; every new prediction file carries the
suffix _fx, so no stored (leaky) file is overwritten.
STATE (ADR 0352): `fit --state lag` adds the run's own tree count and biomass per tree of the year before (raw and as
deviation from this year's anchor) and runs the map FORWARD year by year (2020's lag = the run's own 2019 state, later
lags = the map's own prediction); `--state lagd` trains on cross-fitted free-run lags instead of the true ones (3 folds
by training climate model). State arms also write preds_<g><sfx>_cut.parquet (the same run from a 2019 tree count cut
by 30 %); `retention` scores how much of that start error survives.
DEPARTURE (ADR 0354): `fit --state dep` keeps the map above as the LEVEL and adds a second model of the forest's
year-to-year departure from it, ln((T+1)/(M+1)) for tree count and biomass per tree, learned from the five training
runs' mean departure (against cross-fitted level predictions, de-meaned per leg and cell) from this and last year's
weather anomaly (z-score of the 25 statistics against the 30 years before), last year's departure and the level; run
forward year by year. `--state depnw` = the same without the weather (null). Files _statedep_fx / _statedepnw_fx.
Stages: `fit --g <model>` (SLURM, ~20-40 min) -> xpanel/eval/yearly/preds_<g>.parquet ; `score` (seconds) ->
xpanel/eval/yearly/drift_cases.csv, drift_years.csv.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_panel_a7 as A7  # noqa: E402
import explore_panel_prep as PP  # noqa: E402

YEARLY = os.path.join(PP.OUT, "yearly")
OUT = os.path.join(PP.OUT, "eval", "yearly")
CLIM = A7.CLIM_COLS
TRAIN_M, TRUTH, POOL, SECOND = (1, 2, 3, 5, 6), 4, (1, 2, 3), 5
QS = ["n_per_patch", "agb_per_stem", "SLA_p50", "Wooddens_p50", "D95max_p50", "minwscal_p50"]
S0 = {"n_per_patch": "n_per_patch", "agb_per_stem": "agb_per_stem", "SLA_p50": "SLA_q50",
      "Wooddens_p50": "Wooddens_q50", "D95max_p50": "D95max_q50", "minwscal_p50": "minwscal_q50"}
LOG_EPS = {"agb_per_stem": 1.0}  # A7rH: log target on biomass per tree only
Y0, Y1 = 2020, 2100
TRAIN_YEARS = list(range(Y0, Y1 + 1, 4))
DENSE = 5.0
SOIL_PHYS = ["soil_sand", "soil_clay", "soil_lnKs", "soil_lnSf"]
# ADR 0351: 10-year minima of the water statistics, maxima of the heat / dryness statistics, years since the driest year
MIN10 = ["prec_ann", "prec_hs", "cwb_ann", "cwb_hs", "cwb_min3", "rh_mean"]
MAX10 = ["pet_ann", "days_gt30", "dry_spell_max", "vpd_hs", "vpd_win10_sum", "tmean_ann"]
# ADR 0352: the quantities fed back from year to year, and the start cut of the start-error test
STATE_Q = ("n_per_patch", "agb_per_stem")
CUT = 0.30
# ADR 0354: the departure model's arms, its log offset, and this / last year's weather anomaly columns
DEP_ARMS = ("dep", "depnw")
DEP_EPS = 1.0
DEP_W = [f"z0_{c}" for c in CLIM] + [f"z1_{c}" for c in CLIM]


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def yearly(m: int, leg: str) -> pl.DataFrame | None:
    f = os.path.join(YEARLY, f"m{m}_{leg}.parquet")
    if not os.path.exists(f):
        return None
    d = pl.read_parquet(f).filter(pl.col("Year").is_between(Y0, Y1))
    d = d.with_columns(
        pl.when(pl.col("n_living") > 0).then(pl.col("agb_sum") / pl.col("n_living")).otherwise(None)
        .alias("agb_per_stem"))
    return d.select("Cell", "Year", *QS).with_columns(pl.lit(m).alias("member"), pl.lit(leg).alias("leg"))


def window_climate(leg: str) -> pl.DataFrame:
    """Trailing 30-year means ending each year 2020-2100: observed 2000-2019 + the leg's 2020-2100 (>= 20 years)."""
    h = pl.read_parquet(os.path.join(PP.CLIM_DIR, "hist.parquet")).select("Cell", "Year", *CLIM)
    s = pl.read_parquet(os.path.join(PP.CLIM_DIR, f"{leg}.parquet")).select("Cell", "Year", *CLIM)
    d = pl.concat([h.filter(pl.col("Year") < Y0), s]).with_columns([pl.col(c).cast(pl.Float64) for c in CLIM])
    d = d.sort("Cell", "Year")
    assert d.group_by("Cell").agg(pl.col("Year").diff().max())["Year"].max() == 1, f"{leg}: gap in years"
    d = d.with_columns([pl.col(c).rolling_mean(window_size=30, min_samples=20).over("Cell") for c in CLIM])
    return d.filter(pl.col("Year") >= Y0).with_columns(pl.lit(leg).alias("leg"))


def s0_table() -> pl.DataFrame:
    rows = []
    for m in PP.MEMBERS:
        h = A7.lev(m, "hist", "h2000")
        if h is None:
            continue
        rows.append(h.select("Cell", *[pl.col(S0[q]).alias(f"s0_{q}") for q in QS])
                    .with_columns(pl.lit(m).alias("member")))
    s0 = pl.concat(rows)
    hm = s0.filter(pl.col("member").is_in(TRAIN_M)).group_by("Cell").agg(
        [pl.col(f"s0_{q}").mean().alias(f"hm_{q}") for q in QS])
    return s0.join(hm, on="Cell").with_columns(
        [(pl.col(f"s0_{q}") - pl.col(f"hm_{q}")).alias(f"memoff_{q}") for q in QS]).drop([f"hm_{q}" for q in QS])


def recent_cols(recent: str) -> list[str]:
    if recent == "none":
        return []
    cols = [f"y0_{c}" for c in CLIM] + [f"y1_{c}" for c in CLIM]
    if recent == "x10":
        cols += [f"mn10_{c}" for c in MIN10] + [f"mx10_{c}" for c in MAX10] + ["since10_cwb"]
    return cols


def state_cols(state: str) -> list[str]:
    return [] if state in ("none", *DEP_ARMS) else [f"{k}_{q}" for q in STATE_Q for k in ("lag", "lagdev")]


def dep_cols(state: str) -> list[str]:
    """ADR 0354: the departure model's inputs (last year's departures, the level, the 30-year climate, the weather)."""
    return ([f"dlag_{q}" for q in STATE_Q] + [f"lvl_{q}" for q in STATE_Q] + CLIM
            + (DEP_W if state == "dep" else []))


def feats(soil: str = "code", recent: str = "none", state: str = "none") -> list[str]:
    tail = SOIL_PHYS if soil == "phys" else ["soil_code"]
    return (CLIM + [f"dclim_{c}" for c in CLIM] + [f"anc_{q}" for q in QS] + [f"s0_{q}" for q in QS]
            + [f"memoff_{q}" for q in QS] + ["lat", "lon", *tail] + recent_cols(recent) + state_cols(state))


def agb_per_stem(d: pl.DataFrame) -> pl.DataFrame:
    return d.with_columns(pl.when(pl.col("n_living") > 0).then(pl.col("agb_sum") / pl.col("n_living"))
                          .otherwise(None).alias("agb_per_stem"))


def lag_table(states: pl.DataFrame) -> pl.DataFrame:
    """(Cell, Year=y, member, leg) -> lag_<q> = the run's own state in y-1: 2019 from its historical run (shared by all
    its legs), later years from the leg's yearly states (ADR 0352)."""
    kt = {c: states[c].dtype for c in ("Cell", "Year", "member")}
    h = []
    for m in PP.MEMBERS:
        d = agb_per_stem(pl.read_parquet(os.path.join(YEARLY, f"m{m}_hist.parquet")).filter(pl.col("Year") == Y0 - 1))
        d = d.select("Cell", *STATE_Q)
        h += [d.with_columns(pl.lit(Y0).alias("Year"), pl.lit(m).alias("member"), pl.lit(lg).alias("leg"))
              for lg in A7.ALL_SLEGS]
    s = states.filter(pl.col("Year") < Y1).select("Cell", (pl.col("Year") + 1).alias("Year"), "member", "leg",
                                                  *STATE_Q)
    cols = ["Cell", "Year", "member", "leg", *STATE_Q]
    d = pl.concat([x.select(cols).with_columns([pl.col(c).cast(t) for c, t in kt.items()]) for x in [*h, s]])
    return d.rename({q: f"lag_{q}" for q in STATE_Q})


def with_lagdev(d: pl.DataFrame) -> pl.DataFrame:
    """lagdev = last year's state against THIS year's anchor, in the target's own space (free_run repeats this)."""
    e = LOG_EPS["agb_per_stem"]
    return d.with_columns(
        (pl.col("lag_n_per_patch") - pl.col("anc_n_per_patch")).alias("lagdev_n_per_patch"),
        ((pl.col("lag_agb_per_stem") + e) / (pl.col("anc_agb_per_stem") + e)).log().alias("lagdev_agb_per_stem"))


def target(t: pl.DataFrame, q: str) -> np.ndarray:
    if q in LOG_EPS:
        e = LOG_EPS[q]
        return np.log((t[q].to_numpy() + e) / (t[f"anc_{q}"].to_numpy() + e))
    return (t[q] - t[f"anc_{q}"]).to_numpy()


def untarget(q: str, p: np.ndarray, anc: np.ndarray) -> np.ndarray:
    p = (anc + LOG_EPS[q]) * np.exp(p) - LOG_EPS[q] if q in LOG_EPS else p + anc
    return np.maximum(p, 0.0) if q == "n_per_patch" else p


def fit_q(t: pl.DataFrame, q: str, f: list[str], cat):
    import lightgbm as lgb

    t = t.filter(pl.col(q).is_not_null() & pl.col(f"anc_{q}").is_not_null())
    return lgb.train(A7.PARAMS, lgb.Dataset(t.select(f).to_numpy(), target(t, q), categorical_feature=cat),
                     A7.ROUNDS), t.height


def free_run(models: dict, d: pl.DataFrame, f: list[str], scale: float = 1.0) -> pl.DataFrame:
    """Run the map forward 2020-2100 per (member, leg, Cell): 2020's lag = the row's lag_* (the run's own 2019 state;
    tree count x `scale`), every later year's lag = the map's own prediction for the year before. Returns the keys,
    the anchors and the predictions of every quantity in `models` (ADR 0352)."""
    d = d.sort("Year", "member", "leg", "Cell")
    keys = d.select("member", "leg", "Cell").unique().sort("member", "leg", "Cell").with_row_index("kid")
    d = d.join(keys, on=["member", "leg", "Cell"], how="left").sort("Year", "member", "leg", "Cell")
    X = d.select(f).to_numpy().astype(np.float64)
    yrs, kid, nk = d["Year"].to_numpy(), d["kid"].to_numpy(), keys.height
    jc = {c: f.index(c) for c in state_cols("lag")}
    anc = {q: d[f"anc_{q}"].to_numpy().astype(float) for q in QS}
    first = yrs == Y0
    cur = {q: np.full(nk, np.nan) for q in STATE_Q}
    cur["n_per_patch"][kid[first]] = d["lag_n_per_patch"].to_numpy().astype(float)[first] * scale
    cur["agb_per_stem"][kid[first]] = d["lag_agb_per_stem"].to_numpy().astype(float)[first]
    pred = {q: np.full(d.height, np.nan) for q in models}
    e = LOG_EPS["agb_per_stem"]
    bounds = np.searchsorted(yrs, np.arange(Y0, Y1 + 2))
    for i, y in enumerate(range(Y0, Y1 + 1)):
        idx = np.arange(bounds[i], bounds[i + 1])
        assert (yrs[idx] == y).all()
        k = kid[idx]
        ln, la = cur["n_per_patch"][k], cur["agb_per_stem"][k]
        la = np.where(ln > 0, la, np.nan)  # as in the original's tables: no stems -> no biomass per tree
        X[idx, jc["lag_n_per_patch"]] = ln
        X[idx, jc["lagdev_n_per_patch"]] = ln - anc["n_per_patch"][idx]
        X[idx, jc["lag_agb_per_stem"]] = la
        with np.errstate(invalid="ignore", divide="ignore"):
            X[idx, jc["lagdev_agb_per_stem"]] = np.log((la + e) / (anc["agb_per_stem"][idx] + e))
        for q, mdl in models.items():
            pred[q][idx] = untarget(q, mdl.predict(X[idx]), anc[q][idx])
        for q in STATE_Q:
            cur[q][k] = pred[q][idx]
    return d.select("member", "leg", "Cell", "Year", *[f"anc_{q}" for q in QS]).with_columns(
        [pl.Series(q, pred[q]) for q in models])


def crossfit_lags(trall: pl.DataFrame, train_legs: list[str], train_years: list[int], f: list[str], cat,
                  t0: float) -> pl.DataFrame:
    """ADR 0352 arm lagd: per fold of 3 training climate models, fit the fed-back quantities teacher-forced on the
    other folds' training years, free-run the fold's legs 2020-2100 from the true 2019 state; return (Cell, Year,
    member, leg, lag_*) with those free-run values as next year's lag (2020 keeps the true 2019 state)."""
    gcm = {lg: A7.gcm_of(lg) for lg in train_legs}
    gs = sorted(set(gcm.values()))
    folds = [gs[i::3] for i in range(3)]
    out = []
    for fo in folds:
        legs_in = [lg for lg in train_legs if gcm[lg] in fo]
        inn = trall.filter(~pl.col("leg").is_in(legs_in) & pl.col("Year").is_in(train_years))
        models = {q: fit_q(inn, q, f, cat)[0] for q in STATE_Q}
        fr = free_run(models, trall.filter(pl.col("leg").is_in(legs_in)), f)
        nxt = fr.filter(pl.col("Year") < Y1).select("Cell", (pl.col("Year") + 1).alias("Year"), "member", "leg",
                                                    *[pl.col(q).alias(f"lag_{q}") for q in STATE_Q])
        out.append(nxt)
        log(f"cross-fit fold {fo}: {inn.height} fit rows, {fr.height} free-run rows ({time.time() - t0:.0f}s)")
    first = trall.filter(pl.col("Year") == Y0).select("Cell", "Year", "member", "leg",
                                                      *[f"lag_{q}" for q in STATE_Q])
    d = pl.concat([first, *[o.with_columns([pl.col(c).cast(first[c].dtype) for c in ("Cell", "Year", "member")])
                            for o in out]])
    assert d.select("Cell", "Year", "member", "leg").n_unique() == d.height == trall.height
    return d


def recent_climate(leg: str, recent: str) -> pl.DataFrame:
    """Single-year and 10-year-extreme climate per (Cell, Year) 2020-2100 of one leg (ADR 0351), from the same yearly
    statistics window_climate averages: observed 2000-2019 in front of the leg's 2020-2100."""
    h = pl.read_parquet(os.path.join(PP.CLIM_DIR, "hist.parquet")).select("Cell", "Year", *CLIM)
    s = pl.read_parquet(os.path.join(PP.CLIM_DIR, f"{leg}.parquet")).select("Cell", "Year", *CLIM)
    d = pl.concat([h.filter(pl.col("Year") < Y0), s]).with_columns([pl.col(c).cast(pl.Float64) for c in CLIM])
    d = d.sort("Cell", "Year")
    ex = [pl.col(c).alias(f"y0_{c}") for c in CLIM] + [pl.col(c).shift(1).over("Cell").alias(f"y1_{c}") for c in CLIM]
    if recent == "x10":
        ex += [pl.col(c).rolling_min(window_size=10, min_samples=1).over("Cell").alias(f"mn10_{c}") for c in MIN10]
        ex += [pl.col(c).rolling_max(window_size=10, min_samples=1).over("Cell").alias(f"mx10_{c}") for c in MAX10]
    d = d.with_columns(ex)
    if recent == "x10":  # years since the lowest annual water balance of the last 10 years (0 = this year)
        since = []
        for (_cell,), g in d.group_by("Cell", maintain_order=True):
            v = g["cwb_ann"].to_numpy()
            out = np.zeros(len(v))
            for i in range(len(v)):
                w = v[max(0, i - 9): i + 1]
                out[i] = (len(w) - 1) - int(np.nanargmin(w)) if np.isfinite(w).any() else np.nan
            since.append(out)
        d = d.with_columns(pl.Series("since10_cwb", np.concatenate(since)))
    return (d.filter(pl.col("Year") >= Y0).select("Cell", "Year", *recent_cols(recent))
            .with_columns(pl.lit(leg).alias("leg")))


def weather_anomaly(leg: str) -> pl.DataFrame:
    """ADR 0354: z-score of each yearly climate statistic against the 30 years before (>= 15; observed 2000-2019 in
    front of the leg, as window_climate), this year (z0_) and last year (z1_); 0 where the statistic does not vary."""
    h = pl.read_parquet(os.path.join(PP.CLIM_DIR, "hist.parquet")).select("Cell", "Year", *CLIM)
    s = pl.read_parquet(os.path.join(PP.CLIM_DIR, f"{leg}.parquet")).select("Cell", "Year", *CLIM)
    d = pl.concat([h.filter(pl.col("Year") < Y0), s]).with_columns([pl.col(c).cast(pl.Float64) for c in CLIM])
    d = d.sort("Cell", "Year")
    ex = []
    for c in CLIM:
        mu = pl.col(c).shift(1).rolling_mean(window_size=30, min_samples=15).over("Cell")
        sd = pl.col(c).shift(1).rolling_std(window_size=30, min_samples=15).over("Cell")
        ex.append(pl.when(sd > 1e-6 * (mu.abs() + 1.0)).then((pl.col(c) - mu) / sd).otherwise(0.0).alias(f"z0_{c}"))
    d = d.with_columns(ex)
    d = d.with_columns([pl.col(f"z0_{c}").shift(1).over("Cell").alias(f"z1_{c}") for c in CLIM])
    d = d.filter(pl.col("Year") >= Y0).select("Cell", "Year", *DEP_W)
    assert d.null_count().sum_horizontal().item() == 0, f"{leg}: weather anomaly has nulls"
    return d.with_columns(pl.lit(leg).alias("leg"))


def dep_free_run(fm: dict, d: pl.DataFrame, fd: list[str], start_n: float = 0.0) -> pl.DataFrame:
    """ADR 0354: run the departure models forward 2020-2100 per (member, leg, Cell); 2020's last-year departure =
    `start_n` for tree count (0 = none; ln 0.7 = the start-cut test) and 0 for biomass per tree."""
    d = d.sort("Year", "member", "leg", "Cell")
    keys = d.select("member", "leg", "Cell").unique().sort("member", "leg", "Cell").with_row_index("kid")
    d = d.join(keys, on=["member", "leg", "Cell"], how="left").sort("Year", "member", "leg", "Cell")
    X = d.select(fd).to_numpy().astype(np.float64)
    yrs, kid = d["Year"].to_numpy(), d["kid"].to_numpy()
    jl = {q: fd.index(f"dlag_{q}") for q in STATE_Q}
    cur = {q: np.zeros(keys.height) for q in STATE_Q}
    cur["n_per_patch"][:] = start_n
    D = {q: np.full(d.height, np.nan) for q in STATE_Q}
    bounds = np.searchsorted(yrs, np.arange(Y0, Y1 + 2))
    for i, y in enumerate(range(Y0, Y1 + 1)):
        idx = np.arange(bounds[i], bounds[i + 1])
        assert (yrs[idx] == y).all()
        k = kid[idx]
        for q in STATE_Q:
            X[idx, jl[q]] = cur[q][k]
        for q in STATE_Q:
            D[q][idx] = fm[q].predict(X[idx])
        for q in STATE_Q:
            cur[q][k] = D[q][idx]
    return d.drop("kid").with_columns([pl.Series(f"D_{q}", D[q]) for q in STATE_Q])


def departure_stage(a, tr: pl.DataFrame, te: pl.DataFrame, models: dict, f: list[str], cat, train_legs: list[str],
                    train_years: list[int], t0: float) -> tuple[pl.DataFrame, pl.DataFrame]:
    """ADR 0354: the level map `models` (fitted as `fix`) plus a departure model per fed-back quantity. Returns the
    test predictions and the start-cut run (unseen run only)."""
    import lightgbm as lgb

    g, E = a.g, DEP_EPS
    test_legs = [f"{g}_{s}" for s in ("ssp126", "ssp370", "ssp585")]
    # 1. cross-fitted level on the training legs (3 folds by training climate model, as crossfit_lags)
    gcm = {lg: A7.gcm_of(lg) for lg in train_legs}
    gs = sorted(set(gcm.values()))
    parts = []
    for fo in [gs[i::3] for i in range(3)]:
        legs_in = [lg for lg in train_legs if gcm[lg] in fo]
        inn = tr.filter(~pl.col("leg").is_in(legs_in) & pl.col("Year").is_in(train_years))
        mo = {q: fit_q(inn, q, f, cat)[0] for q in STATE_Q}
        fold = tr.filter(pl.col("leg").is_in(legs_in))
        Xf = fold.select(f).to_numpy()
        parts.append(fold.select("member", "leg", "Cell", "Year", *STATE_Q).with_columns(
            [pl.Series(f"lvl_{q}", untarget(q, mo[q].predict(Xf), fold[f"anc_{q}"].to_numpy().astype(float)))
             for q in STATE_Q]))
        log(f"{g} departure: level cross-fit fold {fo}: {inn.height} fit rows, {fold.height} predicted "
            f"({time.time() - t0:.0f}s)")
    oof = pl.concat(parts)
    assert oof.height == tr.height
    # 2. forced departure = mean over the training runs of ln((T+1)/(M+1)), de-meaned per (leg, Cell)
    # NaN -> null: the level is NaN where the anchor is missing (no stems in the training runs that year)
    lr = [((pl.col(q) + E) / (pl.col(f"lvl_{q}").clip(lower_bound=0.0) + E)).log().fill_nan(None).alias(f"d_{q}")
          for q in STATE_Q]
    fz = oof.with_columns(lr).group_by("leg", "Cell", "Year").agg(
        [pl.col(f"d_{q}").mean().alias(f"D_{q}") for q in STATE_Q]
        + [pl.col(f"d_{q}").count().alias(f"k_{q}") for q in STATE_Q]
        + [pl.col(f"lvl_{q}").fill_nan(None).mean() for q in STATE_Q])
    fz = fz.with_columns([pl.when(pl.col(f"k_{q}") >= 3).then(pl.col(f"D_{q}")).otherwise(None).alias(f"D_{q}")
                          for q in STATE_Q])
    fz = fz.with_columns([(pl.col(f"D_{q}") - pl.col(f"D_{q}").mean().over("leg", "Cell")).alias(f"D_{q}")
                          for q in STATE_Q]).sort("leg", "Cell", "Year")
    assert fz.group_by("leg", "Cell").len()["len"].min() == Y1 - Y0 + 1, "a training series misses years"
    fz = fz.with_columns([pl.col(f"D_{q}").shift(1).over("leg", "Cell").fill_null(0.0).alias(f"dlag_{q}")
                          for q in STATE_Q])
    wz = pl.concat([weather_anomaly(lg) for lg in train_legs + test_legs])
    ctx = tr.select("leg", "Cell", "Year", *CLIM).unique(subset=["leg", "Cell", "Year"], keep="first")
    key = {c: fz[c].dtype for c in ("Cell", "Year")}
    wz = wz.with_columns([pl.col(c).cast(t) for c, t in key.items()])
    fz = fz.join(ctx, on=["leg", "Cell", "Year"], how="left").join(wz, on=["leg", "Cell", "Year"], how="left")
    fz = fz.sort("leg", "Cell", "Year")
    fd = dep_cols(a.state)
    must = [c for c in fd if not c.startswith("lvl_")]  # the level may be missing (no anchor); LightGBM takes it
    assert fz.select(must).null_count().sum_horizontal().item() == 0, "departure inputs have nulls"
    for q in STATE_Q:
        Dq = fz[f"D_{q}"].drop_nulls().to_numpy()
        r1 = np.corrcoef(fz[f"D_{q}"].fill_null(0.0), fz[f"dlag_{q}"])[0, 1]
        log(f"{g} departure {q}: sd {Dq.std():.4f}, 1st/99th centile {np.quantile(Dq, 0.01):.3f} / "
            f"{np.quantile(Dq, 0.99):.3f}, lag-1 corr {r1:.3f}")
    # 3. departure models, teacher-forced on the true last-year departure
    fm = {}
    for q in STATE_Q:
        t = fz.filter(pl.col(f"D_{q}").is_not_null())
        fm[q] = lgb.train(A7.PARAMS, lgb.Dataset(t.select(fd).to_numpy(), t[f"D_{q}"].to_numpy()), A7.ROUNDS)
        imp = sorted(zip(fd, fm[q].feature_importance("gain"), strict=True), key=lambda x: -x[1])
        tot = sum(v for _, v in imp)
        log(f"{g} departure {q}: {t.height} rows fitted ({time.time() - t0:.0f}s); top gain "
            + ", ".join(f"{n} {v / tot:.2f}" for n, v in imp[:8]))
    # 4. the test legs: the level from the full map, the departure run forward from 2020
    Xt = te.select(f).to_numpy()
    lvl = {q: untarget(q, models[q].predict(Xt), te[f"anc_{q}"].to_numpy().astype(float)) for q in QS}
    td = te.select("member", "leg", "Cell", "Year", *[f"anc_{q}" for q in QS], *CLIM).with_columns(
        [pl.Series(f"lvl_{q}", lvl[q]) for q in QS])
    td = td.join(wz, on=["leg", "Cell", "Year"], how="left").with_columns(
        [pl.lit(0.0).alias(f"dlag_{q}") for q in STATE_Q])
    must = [c for c in fd if not c.startswith("lvl_")]  # the level may be missing (no anchor); LightGBM takes it
    assert td.select(must).null_count().sum_horizontal().item() == 0, "test departure inputs have nulls"

    def assemble(r: pl.DataFrame) -> pl.DataFrame:
        ex = [pl.col(f"lvl_{q}").alias(q) for q in QS if q not in STATE_Q]
        ex += [((pl.col(f"lvl_{q}").clip(lower_bound=0.0) + E) * pl.col(f"D_{q}").exp() - E).alias(q)
               for q in STATE_Q]
        r = r.with_columns(ex).with_columns(pl.col("n_per_patch").clip(lower_bound=0.0))
        return r.select("member", "leg", "Cell", "Year", *[f"anc_{q}" for q in QS], *QS,
                        *[f"D_{q}" for q in STATE_Q]).sort("member", "leg", "Year", "Cell")

    out = assemble(dep_free_run(fm, td, fd))
    cut = assemble(dep_free_run(fm, td.filter(pl.col("member") == TRUTH), fd, float(np.log(1.0 - CUT))))
    log(f"{g}: departure free-run 2020-{Y1} done, with and without the start cut ({time.time() - t0:.0f}s)")
    # harness (ADR 0354 sec. 2): the level must equal the stored leak-free map
    fx = os.path.join(OUT, f"preds_{g}_fx.parquet")
    if os.path.exists(fx):
        ref = pl.read_parquet(fx)
        j = td.select("member", "leg", "Cell", "Year", *[f"lvl_{q}" for q in QS]).join(
            ref.select("member", "leg", "Cell", "Year", *QS), on=["member", "leg", "Cell", "Year"])
        rel = [j.select(((pl.col(f"lvl_{q}") - pl.col(q)).abs() / (pl.col(q).abs() + 1e-9)).max()).item()
               for q in QS]
        worst = max(0.0 if v is None else float(v) for v in rel)
        log(f"LEVEL HARNESS vs preds_{g}_fx: {j.height} of {td.height} rows matched, max relative difference "
            f"{worst:.2e} -> {'PASS' if (worst <= 1e-6 and j.height == td.height) else 'FAIL'}")
    else:
        log(f"LEVEL HARNESS: {fx} not found -> not checked")
    # one-step diagnostic on the test legs (true last-year departure of the unseen run + m5; reported, not scored)
    dt = td.join(te.select("member", "leg", "Cell", "Year", *STATE_Q), on=["member", "leg", "Cell", "Year"])
    dt = dt.with_columns([((pl.col(q) + E) / (pl.col(f"lvl_{q}").clip(lower_bound=0.0) + E)).log().fill_nan(None)
                          .alias(f"d_{q}") for q in STATE_Q]).group_by("leg", "Cell", "Year").agg(
        [pl.col(f"d_{q}").mean() for q in STATE_Q] + [pl.col(c).first() for c in fd if not c.startswith("dlag_")])
    dt = dt.with_columns([(pl.col(f"d_{q}") - pl.col(f"d_{q}").mean().over("leg", "Cell")).alias(f"d_{q}")
                          for q in STATE_Q]).sort("leg", "Cell", "Year")
    dt = dt.with_columns([pl.col(f"d_{q}").shift(1).over("leg", "Cell").fill_null(0.0).alias(f"dlag_{q}")
                          for q in STATE_Q]).filter(pl.col("d_n_per_patch").is_not_null())
    p1 = fm["n_per_patch"].predict(dt.select(fd).to_numpy())
    dn, dl = dt["d_n_per_patch"].to_numpy(), dt["dlag_n_per_patch"].to_numpy()
    big = (dl - dn) >= 0.15
    log(f"ONE-STEP (test legs, mean of m4+m5, tree count): corr(pred, true) {np.corrcoef(p1, dn)[0, 1]:.3f}; "
        f"one-year change corr {np.corrcoef(p1 - dl, dn - dl)[0, 1]:.3f}; {big.sum()} drops >= 0.15 in log, "
        f"median captured share {np.median((dl[big] - p1[big]) / (dl[big] - dn[big])):.3f}")
    return out, cut


def soil_table() -> pl.DataFrame:
    """soil_code -> sand, clay, ln Ks, ln Sf (config/soil_texture_by_code.csv, the panel build's soil file)."""
    t = pl.read_csv(os.path.join(REPO, "config", "soil_texture_by_code.csv"))
    return t.select(pl.col("code").alias("soil_code"), pl.col("sand").alias("soil_sand"),
                    pl.col("clay").alias("soil_clay"), pl.col("Ks").log().alias("soil_lnKs"),
                    pl.col("Sf").log().alias("soil_lnSf"))


def stage_fit(a) -> None:
    g = a.g
    os.makedirs(OUT, exist_ok=True)
    test_legs = [f"{g}_{s}" for s in ("ssp126", "ssp370", "ssp585")]
    train_legs = [lg for lg in A7.ALL_SLEGS if A7.gcm_of(lg) != g]
    t0 = time.time()
    states = pl.concat([d for m in PP.MEMBERS for lg in A7.ALL_SLEGS if (d := yearly(m, lg)) is not None])
    clim = pl.concat([window_climate(lg) for lg in A7.ALL_SLEGS])
    log(f"{g}: states {states.height}, climate {clim.height} ({time.time() - t0:.0f}s)")
    # per-year anchors over the training runs x training legs, with per-leg parts for leave-one-leg-out
    base = states.filter(pl.col("member").is_in(TRAIN_M) & pl.col("leg").is_in(train_legs))
    tot = base.group_by("Cell", "Year").agg([pl.col(q).sum().alias(f"S_{q}") for q in QS]
                                           + [pl.col(q).count().alias(f"N_{q}") for q in QS])
    per = base.group_by("Cell", "Year", "leg").agg([pl.col(q).sum().alias(f"s_{q}") for q in QS]
                                                  + [pl.col(q).count().alias(f"n_{q}") for q in QS])
    cb = clim.filter(pl.col("leg").is_in(train_legs))
    ctot = cb.group_by("Cell", "Year").agg([pl.col(c).sum().alias(f"S_{c}") for c in CLIM] + [pl.len().alias("N_c")])
    train_years = list(range(Y0, Y1 + 1, a.train_step))  # ADR 0351 sec. 5: step 1 = every year (default 4)
    # lagd free-runs the training legs; the departure arms learn from every year (ADR 0354)
    fit_years = list(range(Y0, Y1 + 1)) if a.state in ("lagd", *DEP_ARMS) else train_years
    rows = states.filter((pl.col("member").is_in(TRAIN_M) & pl.col("leg").is_in(train_legs)
                          & pl.col("Year").is_in(fit_years))
                         | (pl.col("member").is_in([TRUTH, SECOND]) & pl.col("leg").is_in(test_legs)))
    rows = (rows.join(tot, on=["Cell", "Year"], how="left").join(per, on=["Cell", "Year", "leg"], how="left")
            .join(clim, on=["Cell", "Year", "leg"], how="left")
            .join(cb.select("Cell", "Year", "leg", *[pl.col(c).alias(f"c_{c}") for c in CLIM]),
                  on=["Cell", "Year", "leg"], how="left")
            .join(ctot, on=["Cell", "Year"], how="left"))
    ex = []
    for q in QS:  # leave-one-leg-out: a training row never sees its own leg (s_/n_ are 0 for a test leg)
        s_, n_ = pl.col(f"s_{q}").fill_null(0.0), pl.col(f"n_{q}").fill_null(0)
        den = pl.col(f"N_{q}") - n_
        ex.append(pl.when(den > 0).then((pl.col(f"S_{q}") - s_) / den).otherwise(None).alias(f"anc_{q}"))
    own = pl.col("c_tmean_ann").is_not_null()  # the row's leg is one of the anchor legs
    for c in CLIM:
        ac = pl.when(own).then((pl.col(f"S_{c}") - pl.col(f"c_{c}")) / (pl.col("N_c") - 1)).otherwise(
            pl.col(f"S_{c}") / pl.col("N_c"))
        ex.append((pl.col(c) - ac).alias(f"dclim_{c}"))
    rows = rows.with_columns(ex)
    rows = rows.drop([x for x in rows.columns if x[:2] in ("S_", "N_", "s_", "n_", "c_") and x != "n_per_patch"])
    cells = PP.cells().select("Cell", "lat", "lon", "soil_code")
    if a.soil == "phys":
        cells = cells.join(soil_table(), on="soil_code", how="left")
        assert cells["soil_sand"].null_count() == 0, "a cell's soil code is not in the soil table"
    rows = rows.join(s0_table(), on=["Cell", "member"], how="left").join(cells, on="Cell", how="left")
    if a.recent != "none":
        rc = pl.concat([recent_climate(lg, a.recent) for lg in A7.ALL_SLEGS])
        rows = rows.join(rc, on=["Cell", "Year", "leg"], how="left")
        assert rows[f"y0_{CLIM[0]}"].null_count() == 0, "recent climate missing for some rows"
    if a.state not in ("none", *DEP_ARMS):
        rows = with_lagdev(rows.join(lag_table(states), on=["Cell", "Year", "member", "leg"], how="left"))
        assert rows["lag_n_per_patch"].null_count() == 0, "a row has no state of the year before"
    rows = rows.sort("member", "leg", "Year", "Cell")  # deterministic row order (LightGBM bagging depends on it)
    # ADR 0352 sec. 0: training rows = training runs on TRAINING legs only (m5 is also a test-side run)
    tr = rows.filter(pl.col("member").is_in(TRAIN_M) & pl.col("leg").is_in(train_legs))
    te = rows.filter(pl.col("member").is_in([TRUTH, SECOND]) & pl.col("leg").is_in(test_legs))
    assert tr.height == len(TRAIN_M) * len(train_legs) * len(fit_years) * tr["Cell"].n_unique(), "training rows"
    log(f"{g}: train rows {tr.height}, test rows {te.height} ({time.time() - t0:.0f}s)")
    f = feats(a.soil, a.recent, a.state)
    cat = [f.index("soil_code")] if a.soil == "cat" else "auto"
    log(f"{g}: soil={a.soil}, recent={a.recent}, state={a.state}, {len(f)} features, categorical {cat}")
    if a.state == "lagd":
        lags = crossfit_lags(tr, train_legs, train_years, f, cat, t0)
        tr = with_lagdev(tr.drop([f"lag_{q}" for q in STATE_Q]).join(lags, on=["Cell", "Year", "member", "leg"],
                                                                     how="left"))
        tr = tr.filter(pl.col("Year").is_in(train_years)).sort("member", "leg", "Year", "Cell")
        log(f"{g}: training lags replaced by cross-fitted free-run values; {tr.height} rows")
    models = {}
    trf = tr.filter(pl.col("Year").is_in(train_years)) if a.state in DEP_ARMS else tr  # the level = `fix`'s rows
    for q in QS:
        models[q], nfit = fit_q(trf, q, f, cat)
        log(f"{g} {q}: {nfit} rows fitted ({time.time() - t0:.0f}s)")
    if a.state in DEP_ARMS:
        out, cut = departure_stage(a, tr, te, models, f, cat, train_legs, train_years, t0)
    elif a.state == "none":
        out = te.select("member", "leg", "Cell", "Year", *[pl.col(f"anc_{q}") for q in QS]).with_columns(
            [pl.Series(q, untarget(q, models[q].predict(te.select(f).to_numpy()), te[f"anc_{q}"].to_numpy()
                                   .astype(float))) for q in QS])
        cut = out  # no state input: a start error cannot reach any year (the start-error harness must read 0)
    else:
        out = free_run(models, te, f).sort("member", "leg", "Year", "Cell")
        cut = free_run(models, te.filter(pl.col("member") == TRUTH), f, 1.0 - CUT).sort("member", "leg", "Year",
                                                                                        "Cell")
        log(f"{g}: free-run 2020-{Y1} done, with and without the start cut ({time.time() - t0:.0f}s)")
    out.write_parquet(os.path.join(OUT, f"preds_{g}{suffix(a)}.parquet"))
    cut.filter(pl.col("member") == TRUTH).write_parquet(os.path.join(OUT, f"preds_{g}{suffix(a)}_cut.parquet"))
    log(f"{g}: wrote {out.height} predictions")


def suffix(a) -> str:
    if a.suffix is not None:
        return a.suffix
    return (("" if a.soil == "code" else f"_soil{a.soil}") + ("" if a.recent == "none" else f"_recent{a.recent}")
            + ("" if a.train_step == 4 else f"_step{a.train_step}") + ("" if a.state == "none" else f"_state{a.state}")
            + "_fx")  # ADR 0352 sec. 0: leak-free fits never overwrite the stored (leaky) files


def stage_retention(a) -> None:
    """ADR 0352 sec. 2: share of a 30 % start cut in tree count still present in year y, per case, dense cells."""
    rows = []
    for g in PP.GCMS:
        f0, f1 = (os.path.join(OUT, f"preds_{g}{suffix(a)}{x}.parquet") for x in ("", "_cut"))
        if not (os.path.exists(f0) and os.path.exists(f1)):
            log(f"skip {g}: no predictions")
            continue
        X = pl.read_parquet(f0).filter(pl.col("member") == TRUTH)
        C = pl.read_parquet(f1).select("leg", "Cell", "Year", *[pl.col(q).alias(f"c_{q}") for q in STATE_Q])
        j = X.join(C, on=["leg", "Cell", "Year"]).filter(pl.col("anc_n_per_patch") >= DENSE)
        for q in STATE_Q:
            jq = j.filter(pl.col(q) > 0)
            r = jq.group_by("leg", "Year").agg(((pl.col(q) - pl.col(f"c_{q}")) / pl.col(q)).median().alias("r"))
            rows.append(r.with_columns(pl.lit(q).alias("q"), (pl.col("r") / CUT).alias("r")))
    R = pl.concat(rows)
    R.write_csv(os.path.join(OUT, f"retention{suffix(a)}.csv"))
    for q in STATE_Q:
        Rq = R.filter(pl.col("q") == q)
        med = Rq.group_by("Year").agg(pl.col("r").median()).sort("Year")
        show = med.filter(pl.col("Year").is_in([2020, 2021, 2025, 2030, 2040, 2050, 2060, 2080, 2100]))
        print(f"\n== {q}: retained share of the start cut (median over {Rq['leg'].n_unique()} cases)")
        print(show)
        mx, late = med["r"].max(), med.filter(pl.col("Year") >= 2081)["r"].mean()
        per = Rq.filter(pl.col("Year") >= 2081).group_by("leg").agg(pl.col("r").mean()).sort("leg")
        print(per)
        if q == "n_per_patch":
            print(f"START-ERROR TEST (max r <= 1.1 and mean r 2081-2100 <= 0.5): max {mx:.3f}, late {late:.3f} -> "
                  f"{'PASS' if (mx <= 1.1 and late <= 0.5) else 'FAIL'}")


def stage_score(a) -> None:
    w = PP.cells().select("Cell", "lat").with_columns(np.cos(np.deg2rad(pl.col("lat"))).alias("w")).drop("lat")
    hist = {m: pl.read_parquet(os.path.join(YEARLY, f"m{m}_hist.parquet")).filter(pl.col("Year") == 2019) for m in (4,)}
    yr, cs = [], []
    for g in PP.GCMS:
        pf = os.path.join(OUT, f"preds_{g}{suffix(a)}.parquet")
        if not os.path.exists(pf):
            log(f"skip {g}: no predictions")
            continue
        P = pl.read_parquet(pf)
        for s in ("ssp126", "ssp370", "ssp585"):
            leg = f"{g}_{s}"
            T = yearly(TRUTH, leg)
            if T is None:
                continue
            X = P.filter((pl.col("member") == TRUTH) & (pl.col("leg") == leg))
            R = {m: yearly(m, leg) for m in POOL}
            Om = pl.concat([yearly(m, leg) for m in TRAIN_M]).group_by("Cell", "Year").agg(pl.col(q).mean() for q in QS)
            h19 = hist[4].with_columns(
                pl.when(pl.col("n_living") > 0).then(pl.col("agb_sum") / pl.col("n_living")).otherwise(None)
                .alias("agb_per_stem")).select("Cell", *QS)
            persist = T.select("Cell", "Year").join(h19, on="Cell", how="left")
            cand = {"YA": X.select("Cell", "Year", *QS), "second": yearly(SECOND, leg).select("Cell", "Year", *QS),
                    "oracle": Om, "persist": persist,
                    "anchor": X.select("Cell", "Year", *[pl.col(f"anc_{q}").alias(q) for q in QS])}
            dense = X.select("Cell", "Year", (pl.col("anc_n_per_patch") >= DENSE).alias("dense"))
            for q in QS:
                Tq = T.select("Cell", "Year", pl.col(q).alias("T")).filter(pl.col("T").is_not_null()
                                                                         & (pl.col("T").abs() > 0))
                Tq = Tq.join(dense, on=["Cell", "Year"]).join(w, on="Cell")
                er = pl.concat([Tq.join(R[m].select("Cell", "Year", pl.col(q).alias("X")), on=["Cell", "Year"])
                                for m in POOL]).with_columns(((pl.col("X") - pl.col("T")).abs() / pl.col("T"))
                                                              .alias("e"))
                for grp, sel in (("dense", pl.col("dense")), ("all", pl.lit(True))):
                    ref = er.filter(sel).group_by("Year").agg(pl.col("e").median().alias("r50"),
                                                               pl.col("e").quantile(0.9).alias("r90"))
                    for nm, C in cand.items():
                        j = Tq.filter(sel).join(C.select("Cell", "Year", pl.col(q).alias("X")), on=["Cell", "Year"])
                        j = j.filter(pl.col("X").is_not_null())
                        e = j.with_columns(((pl.col("X") - pl.col("T")).abs() / pl.col("T")).alias("e")).group_by(
                            "Year").agg(pl.col("e").median().alias("x50"), pl.col("e").quantile(0.9).alias("x90"),
                                        ((pl.col("w") * pl.col("X")).sum() / (pl.col("w") * pl.col("T")).sum() - 1)
                                        .alias("tot"), pl.len().alias("n"))
                        e = e.join(ref, on="Year").with_columns((pl.col("x50") / pl.col("r50")).alias("rho50"),
                                                                (pl.col("x90") / pl.col("r90")).alias("rho90"))
                        e = e.with_columns(pl.lit(leg).alias("leg"), pl.lit(s).alias("scen"), pl.lit(q).alias("q"),
                                           pl.lit(grp).alias("grp"), pl.lit(nm).alias("cand"))
                        yr.append(e)
                        early = e.filter(pl.col("Year").is_between(2021, 2040))
                        late = e.filter(pl.col("Year").is_between(2081, 2100))
                        cs.append(dict(leg=leg, scen=s, q=q, grp=grp, cand=nm,
                                       rho50_early=early["rho50"].mean(), rho50_late=late["rho50"].mean(),
                                       drift=late["rho50"].mean() / early["rho50"].mean(),
                                       drift90=late["rho90"].mean() / early["rho90"].mean(),
                                       tot_early=early["tot"].mean() * 100, tot_late=late["tot"].mean() * 100,
                                       n_cells=int(e["n"].median())))
    os.makedirs(OUT, exist_ok=True)
    Y = pl.concat(yr)
    Y.write_csv(os.path.join(OUT, f"drift_years{suffix(a)}.csv"))
    C = pl.DataFrame(cs)
    C.write_csv(os.path.join(OUT, f"drift_cases{suffix(a)}.csv"))
    pl.Config.set_tbl_rows(200)
    pl.Config.set_tbl_cols(14)
    pl.Config.set_tbl_width_chars(220)
    num = ["rho50_early", "rho50_late", "drift", "drift90", "tot_early", "tot_late"]
    for grp in ("dense", "all"):
        print(f"\n== {grp} cells: per candidate x quantity, over the cases (median; count of drift <= 1.2 / > 1.5)")
        print(C.filter(pl.col("grp") == grp).group_by("cand", "q").agg(
            [pl.col(c).median().round(3) for c in num]
            + [(pl.col("drift") <= 1.2).sum().alias("#<=1.2"), (pl.col("drift") > 1.5).sum().alias("#>1.5"),
               pl.len().alias("cases")]).sort("q", "cand"))
    print("\n== YA, dense cells, tree count and biomass per tree, per case")
    print(C.filter((pl.col("grp") == "dense") & (pl.col("cand") == "YA") & pl.col("q").is_in(QS[:2]))
          .select("leg", "q", *[pl.col(c).round(3) for c in num], "n_cells").sort("q", "leg"))
    ya = C.filter((pl.col("grp") == "dense") & (pl.col("cand") == "YA") & pl.col("q").is_in(QS[:2]))
    ok = all(ya.filter(pl.col("q") == q).select(((pl.col("drift") <= 1.2).sum() >= 13)
                                                 & ((pl.col("drift") > 1.5).sum() == 0)).item() for q in QS[:2])
    print(f"\nPROPOSED PASS (tree count AND biomass per tree, dense: drift <= 1.2 in >= 13/15, none > 1.5): "
          f"{'PASS' if ok else 'FAIL'} on {ya.height // 2} cases")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["fit", "score", "retention"])
    ap.add_argument("--g", default="gfdl-esm4", choices=PP.GCMS)
    ap.add_argument("--soil", default="code", choices=["code", "cat", "phys"],
                    help="soil code as a number (default), a category, or texture values (ADR 0349)")
    ap.add_argument("--recent", default="none", choices=["none", "y1", "x10"],
                    help="single-year / 10-year-extreme climate inputs (ADR 0351)")
    ap.add_argument("--train-step", dest="train_step", type=int, default=4,
                    help="training rows every n-th year 2020-2100 (default 4; ADR 0351 sec. 5)")
    ap.add_argument("--state", default="none", choices=["none", "lag", "lagd", *DEP_ARMS],
                    help="last year's state as an input, run forward year by year (ADR 0352); dep/depnw = the "
                         "weather-driven departure model on top of the level map (ADR 0354)")
    ap.add_argument("--suffix", default=None, help="prediction file suffix (default from --soil)")
    a = ap.parse_args()
    {"fit": stage_fit, "score": stage_score, "retention": stage_retention}[a.stage](a)
    log("=== DONE")


if __name__ == "__main__":
    main()
