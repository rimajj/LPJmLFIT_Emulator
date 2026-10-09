#!/usr/bin/env python3
"""explore_panel_a7.py -- LINE X: the direct window map (A7 / A7s, ADR 0315 sec. 8) on the PANEL VENUE
(explore_panel_prep.py): does wider CLIMATE COVERAGE in training make it pass, and which kind of new data would help?

MEMBERS: train m1, m2, m3; truth m4 (unseen run); replica m3 for the tolerance and the single-run ceiling. Folds 1-5 by
10-cell BLOCK (cross-fitted: fold-k model predicts fold-k cells of m4). Training rows: every (training member, training
leg, window in {w2041, w2071}) + each member's hist h2000 row. Test: m4, window 2071-2100. Scored exactly as on the
global venue (explore_glob_eval.score: six panel quantities, tolerance max(10 %, stratum median of |m4 - m3| / mean),
area totals, response). Response is reported twice: scenario - historic (2071-2100 minus 2000-2019, the global venue's
basis) AND scenario - control (minus m4's ctl_obs 2071-2100 = constant observed climate; the plan's preferred reference,
which removes the continuing stand dynamics).

SPLITS (one variable each; every one also scores the nulls on the SAME cells):
  HG:<g>     held-out CLIMATE MODEL g: train = the 4 other models x {ssp126, ssp370, ssp585} + ctl_obs + ctl_mpi370
             (dropped when g is MPI) ; test = g x {126, 370, 585}. Its warming range is covered by the other models.
  H585       held-out AMPLITUDE: train = all 5 models x {ssp126, ssp370} + controls ; test = all 5 x ssp585.
  H585G:<g>  both held out: train = other 4 models x {126, 370} + controls ; test = g x ssp585.
  NG<n>:<g>  learning curve in CLIMATE MODELS: as HG:<g> with only n of the other 4 models (every combination, n=1..4),
             test g x {370, 585}; averaged over combinations.
  NM<k>:<g>  learning curve in RUNS: as HG:<g> with only k training members (k=1: m1 | m2 | m3; k=2: three pairs;
             k=3: all), test g x {370, 585}.
NULLS: ceiling (m3), ceiling_mean (mean of m1-m3, same leg: an ORACLE), persist_h (m4's 2000-2019 carried), persist_19
(m4's 2019 snapshot), lookup (mean over the TRAINING members and TRAINING models of the same cell under the SAME scenario
label -- for H585/H585G the nearest training scenario, ssp370). The lookup is a strong null here: it already carries a
multi-model scenario response.

WRITTEN BEFORE THE RUN (ADR 0184) -- expectations, and what each null must return:
  harness   persist_h response (scenario - historic) EXACTLY 0.
  ceiling   pass 0.15-0.22 (Billing's 25-patch two-run agreement was 0.173); area ratios within 0.05 of 1.
  ceiling_mean  pass above the ceiling (0.25-0.32 expected; Billing 0.281). The survival bar is 0.5 x ceiling_mean AND
            above the best null, as amended in ADR 0315 sec. 9.
  E1 (coverage is the lever): on HG the direct map with start state (A7s) passes the bar on ssp126 and ssp370 for at
            least 4 of the 5 held-out models, with area totals within +-10 %.
  E2 (extrapolation penalty reproduces): on ssp585, H585G (amplitude never seen) is worse than HG (other models' ssp585
            seen) by >= 0.02 in pass AND its biomass-per-tree error is larger by >= 3 points, averaged over the 5 models.
  E3 (which data): pass on HG ssp585 rises with the number of training models; the last step (3 -> 4 models) still adds
            >= 0.005 => more climate models would still help. The runs curve: 1 -> 3 training runs adds less than
            1 -> 4 models. If E3's model curve is flat from 2 models on, more climate models are NOT the lever.
  FALSIFIER of the coverage hypothesis: A7s on HG fails the bar on ssp370 for >= 3 of 5 models (then the global-venue
            gap was not mainly extrapolation, and new runs with wider climates would not fix it).
Outputs: xpanel/eval/a7_<split>.csv (one row per test leg x arm), xpanel/eval/a7_summary.csv.

RESULT OF `core` (job 2451116, 2026-10-09): E1 FAILED and the falsifier FIRED as written -- A7s on HG fails the bar on
ssp370 for 5 of 5 models (pass 0.053-0.088 vs bar ~0.13), BELOW the lookup null (0.058-0.114). Totals within 4 %.
NOT anticipated when E1 was written: the split holds out CELLS (10-cell blocks) as well as the climate model, so the arm
learns place from ~840 cells (global venue: ~4 650), while the lookup null reads the SAME test cells from other runs.

MODE `seen` (pre-registered here BEFORE its run, 2026-10-09): the deployment case. The emulator will be trained on the
original's runs of EVERY cell and then run on those cells under a new climate and a new random draw, so the realistic
test holds out the RUN (m4) and the CLIMATE MODEL, not the cell. One variable per step, same splits (HG, H585G):
  A7s-seen  A7s trained on ALL cells of m1-m3 (no fold) -> m4.
  A7r       + per-cell ANCHOR: for each quantity, the mean over the training runs x training legs of the same cell and
            window, leave-one-leg-out in training rows (so a row never sees its own leg); the leg's climate MINUS the
            anchor legs' mean climate; m4's own 2000-2019 offset from the training runs' 2000-2019 mean. Target = value
            minus anchor (a residual). A7rcb: its twin (leg climate replaced by the cell's 2000-2019 climate).
  Thresholds unchanged (0.5 x ceiling_mean AND above the best null). The nulls already read the test cells.
  Expected: A7s-seen pass >= A7s + 0.01 on HG ssp370 (mean over models). A7r beats the lookup null by >= 0.02 on HG
  ssp370 for >= 4 of 5 models and passes the bar for >= 3 of 5, area totals within +-10 %; its scenario-minus-control
  tree-count slope exceeds its twin's by > 0.2. On ssp585, H585G A7r is worse than HG A7r by >= 0.02 in pass (with
  anchors, an unseen amplitude must cost more than an unseen model). Falsifier: A7r does not beat the lookup on >= 3
  of 5 models -- then per-cell memory plus climate adds nothing to "other runs of this cell", and the level score is
  set by the original's own randomness, not by the method.

MODE `curves_seen` (pre-registered here BEFORE its run, 2026-10-09) -- WHICH DATA would still help, in the deployment
setting (cells seen, A7r only, test = m4 on the held-out model's ssp370; mean over held-out models and combinations):
  NGs<n>  n = 1..4 training climate models (all combinations), all 3 scenarios + controls, runs m1-m3.
  NMs<k>  k = 1..3 training runs (all combinations), all 4 other models.
  ENV     the 4 other models WITHOUT their ssp585 legs (is the hottest scenario needed to bracket ssp370?).
  Expected: pass rises with n; the last step 3 -> 4 models adds >= 0.005 (=> more climate models still help);
  1 -> 3 runs adds >= 0.01 and 2 -> 3 adds >= 0.003 (=> more runs still help); ENV lowers pass by >= 0.01 vs the full
  HG (=> covering hotter climates than the target matters). A step below its bar => that kind of data is saturated
  at this panel size and producing more of it is NOT justified by this evidence.

MODE `more` -- the test of ADR 0316 sec. 7's PREDICTION (written there before the new runs existed; restated, not
changed): A7r, held-out model g in the FIRST five, test m4 g x ssp370 (126/585 reported too), training legs = the other
models x 3 scenarios + ctl_obs. Four training sets, five LightGBM seeds each, one process, rows sorted:
  base  4 other first-five models, runs m1-m3      (the 0.162 setting of curves_seen, re-measured here)
  mod   9 other models (4 + the 5 new), runs m1-m3
  run   4 other first-five models, runs m1, m2, m3, m5, m6
  both  9 other models, runs m1, m2, m3, m5, m6
The bar stays 0.5 x ceiling_mean (mean of m1-m3, as before) AND above the lookup of the SAME training set.
Prediction: `both` mean pass on ssp370 >= base + 0.02, bar passed on >= 12 of the 13 HG cases. Falsifier: both - base
< 0.01. The `mod` and `run` rows split the gain between the two kinds of data.
RESULT (jobs 2452217-21, 2026-10-10, ADR 0316 sec. 10): HELD -- both - base = +0.033 on ssp370 (0.161 -> 0.193), bar on
12 of 13; mod +0.023, run +0.005. Only UKESM ssp370 still fails (0.134 vs 0.151).

MODE `logt` (pre-registered 2026-10-10, BEFORE its run): ONE variable on the `both` set of mode `more`. A7r fits the
ABSOLUTE residual (value - anchor) with squared error, so dense cells dominate the loss, while every score is a PER-CELL
RELATIVE error; on the second-run measure (ADR 0316 sec. 10) A7r is 1.13-1.36x a second run in the 5-20 trees-per-patch
classes but 2.5-3.5x in the < 5 classes (~20 % of cells), where the mean of three runs reaches 0.82. A7rL = A7r with the
target for tree count and biomass per tree replaced by the LOG RATIO log((value + e) / (anchor + e)), prediction
(anchor + e) * exp(p) - e; e = 0.1 trees per patch / 1 gC per tree. Same features, rows, rounds, other four quantities.
Expected (seed 1 on the second-run measure, ssp370 and all-case medians over the five held-out models; pass over 5 seeds):
  sparse classes (< 2 and 2-5 trees per patch): tree-count ratio falls by >= 0.3 in each; biomass per tree by >= 0.2;
  all cells: tree-count ratio (typical cell) falls by >= 0.05; the 5-20 classes worsen by no more than 0.05;
  conjunctive pass rate on ssp370 not lower than A7r's by more than 0.005; area totals still within 5 %.
  Falsifier: the sparse-class tree-count ratio moves by < 0.1 => the loss weighting is NOT why sparse cells fail.
  Harness: A7r here equals mode `more`'s `both` A7r pass rate per seed (same rows, same seed, rows sorted).
"""

from __future__ import annotations

import itertools
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_glob_eval as ev  # noqa: E402
import explore_panel_prep as PP  # noqa: E402

EVAL = os.path.join(PP.OUT, "eval")
PANEL = ev.PANEL
CLIM_COLS = ["tmean_ann", "tcold_month", "twarm_month", "gdd5", "frost_days", "days_gt30", "prec_ann", "prec_hs",
             "pet_ann", "cwb_ann", "cwb_hs", "cwb_min3", "dry_spell_max", "rh_mean", "vpd_hs", "vpd_win10_sum",
             "swdown_ann", "lwnet_ann"] + [f"tstress_pft{k}" for k in range(7)]
PARAMS = dict(objective="regression", learning_rate=0.05, num_leaves=31, min_data_in_leaf=20, feature_fraction=0.8,
              bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1, num_threads=16,
              seed=int(os.environ.get("LGB_SEED", "1")))
ROUNDS = 400
LOG_EPS = {"n_per_patch": 0.1, "agb_per_stem": 1.0}  # mode `logt` only
TRAIN_M, TRUTH, REPLICA = (1, 2, 3), 4, 3
SCEN_LEGS = PP.SLEGS  # the first five models: every split of the modes core / seen / curves* is defined on these
ALL_SLEGS = PP.SLEGS + PP.NEW_SLEGS  # + the five models of ADR 0316 sec. 7 (mode `more`)
CTLS = list(PP.CTL)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def lev(m, leg, win):
    f = os.path.join(PP.LEV_DIR, f"m{m}_{leg}_{win}.parquet")
    return pl.read_parquet(f).select(["Cell"] + PANEL) if os.path.exists(f) else None


def gcm_of(leg):
    return leg.rsplit("_", 1)[0] if leg in ALL_SLEGS else ("mpi-esm1-2-hr" if leg == "ctl_mpi370" else "obs")


def scen_of(leg):
    return leg.rsplit("_", 1)[1] if leg in ALL_SLEGS else leg


# ------------------------------------------------------------------------------------------------ the row table
def climate_windows() -> pl.DataFrame:
    out = []
    for leg in ["hist", *ALL_SLEGS]:
        if not os.path.exists(os.path.join(PP.CLIM_DIR, f"{leg}.parquet")):
            continue
        d = pl.scan_parquet(os.path.join(PP.CLIM_DIR, f"{leg}.parquet"))
        for win, (y0, y1) in (("h2000", (2000, 2019)),) if leg == "hist" else (("w2041", (2041, 2070)),
                                                                              ("w2071", (2071, 2100))):
            g = (d.filter(pl.col("Year").is_between(y0, y1)).group_by("Cell")
                 .agg([pl.col(c).cast(pl.Float64).mean() for c in CLIM_COLS]).collect())
            out.append(g.with_columns(pl.lit(leg).alias("leg"), pl.lit(win).alias("win")))
    for leg in CTLS:  # the pool mean stands for any window of a shuffled-recycled control [ASSUMPTION, see prep]
        g = (pl.read_parquet(os.path.join(PP.CLIM_DIR, f"{leg}_pool.parquet")).group_by("Cell")
             .agg([pl.col(c).cast(pl.Float64).mean() for c in CLIM_COLS]))
        for win in ("w2041", "w2071"):
            out.append(g.with_columns(pl.lit(leg).alias("leg"), pl.lit(win).alias("win")))
    return pl.concat(out)


def build_rows() -> pl.DataFrame:
    c = PP.cells().select("Cell", "lat", "lon", "soil_code", "fold", "block")
    cw = climate_windows()
    hist_clim = (cw.filter(pl.col("leg") == "hist").drop("leg", "win")
                 .rename({x: f"{x}_cb" for x in CLIM_COLS}))
    rows = []
    for m in PP.MEMBERS:
        h = lev(m, "hist", "h2000")
        if h is None:
            if m in (*TRAIN_M, TRUTH):
                raise SystemExit(f"missing hist levels for m{m}")
            continue  # a new member not produced yet
        s0 = h.rename({q: f"s0_{q}" for q in PANEL})
        rows.append(h.join(s0, on="Cell").with_columns(pl.lit(m).alias("member"), pl.lit("hist").alias("leg"),
                                                       pl.lit("h2000").alias("win")))
        for leg in [*ALL_SLEGS, *CTLS]:
            for win in ("w2041", "w2071"):
                y = lev(m, leg, win)
                if y is None:
                    continue
                rows.append(y.join(s0, on="Cell").with_columns(pl.lit(m).alias("member"), pl.lit(leg).alias("leg"),
                                                               pl.lit(win).alias("win")))
    df = pl.concat(rows).join(cw, on=["Cell", "leg", "win"]).join(hist_clim, on="Cell").join(c, on="Cell")
    df = df.sort(["member", "leg", "win", "Cell"])  # deterministic row order (LightGBM's bagging depends on it)
    return df.with_columns(pl.col("leg").map_elements(gcm_of, return_dtype=pl.Utf8).alias("gcm"),
                           pl.col("leg").map_elements(scen_of, return_dtype=pl.Utf8).alias("scen"))


# ------------------------------------------------------------------------------------------------ fit / predict
def feats(variant):
    clim = [f"{x}_cb" for x in CLIM_COLS] if variant.endswith("cb") else CLIM_COLS
    return clim + ["lat", "lon", "soil_code"] + ([f"s0_{q}" for q in PANEL] if variant.startswith("A7s") else [])


def fit_predict(tr_all: pl.DataFrame, te_all: pl.DataFrame, variant: str) -> pl.DataFrame:
    import lightgbm as lgb

    f = feats(variant)
    preds = []
    for k in range(1, 6):
        tr = tr_all.filter(pl.col("fold") != k)
        te = te_all.filter(pl.col("fold") == k)
        if te.height == 0:
            continue
        out = te.select("Cell", "leg")
        for q in PANEL:
            t = tr.filter(pl.col(q).is_not_null())
            mdl = lgb.train(PARAMS, lgb.Dataset(t.select(f).to_numpy(), t[q].to_numpy()), ROUNDS)
            p = mdl.predict(te.select(f).to_numpy())
            if q == "n_per_patch":
                p = np.maximum(p, 0.0)
            out = out.with_columns(pl.Series(q, p))
        preds.append(out)
    return pl.concat(preds)


# ------------------------------------------------------------------------------------------------ scoring
def score_leg(leg, cand: dict, cells: pl.DataFrame) -> list[dict]:
    T_w, R_w = lev(TRUTH, leg, "w2071"), lev(REPLICA, leg, "w2071")
    T_h, R_h = lev(TRUTH, "hist", "h2000"), lev(REPLICA, "hist", "h2000")
    T_c, R_c = lev(TRUTH, "ctl_obs", "w2071"), lev(REPLICA, "ctl_obs", "w2071")
    if T_w is None or R_w is None:
        log(f"skip {leg}: truth/replica missing")
        return []
    common = set(T_w["Cell"]) & set(R_w["Cell"])
    tb = (T_w.filter(pl.col("n_per_patch") > 0).select("Cell").vstack(T_h.filter(pl.col("n_per_patch") > 0)
                                                                     .select("Cell")).unique())
    sc = cells.join(tb, on="Cell").filter(pl.col("Cell").is_in(list(common)))
    rows = []
    for name, (pw, ph, pc) in cand.items():
        pw = pw.filter(pl.col("Cell").is_in(sc["Cell"]))
        if pw.height < sc.height:  # a missing prediction would silently shrink the scored set: refuse
            log(f"{leg} {name}: {pw.height} predictions for {sc.height} scored cells -- SKIPPED")
            continue
        s = ev.score(pw, ph, T_w, T_h, R_w, R_h, sc)
        r = dict(test_leg=leg, arm=name, **s)
        if pc is not None and T_c is not None and R_c is not None:
            s2 = ev.score(pw, pc, T_w, T_c, R_w, R_c, sc)
            r.update({f"ctl_{k}": v for k, v in s2.items() if k.startswith("resp_")})
        rows.append(r)
    return rows


def nulls(df: pl.DataFrame, leg, train_legs, train_members) -> dict:
    """lookup = mean over the training members x training legs with the same scenario label (else ssp370)."""
    scen = scen_of(leg)
    same = [lg for lg in train_legs if scen_of(lg) == scen] or [lg for lg in train_legs if scen_of(lg) == "ssp370"]
    lk = (df.filter(pl.col("member").is_in(list(train_members)) & pl.col("leg").is_in(same) & (pl.col("win") == "w2071"))
          .group_by("Cell").agg([pl.col(q).mean() for q in PANEL]))
    lk_h = (df.filter(pl.col("member").is_in(list(train_members)) & (pl.col("leg") == "hist"))
            .group_by("Cell").agg([pl.col(q).mean() for q in PANEL]))
    lk_c = (df.filter(pl.col("member").is_in(list(train_members)) & (pl.col("leg") == "ctl_obs")
                      & (pl.col("win") == "w2071")).group_by("Cell").agg([pl.col(q).mean() for q in PANEL]))
    mean_w = (df.filter(pl.col("member").is_in(list(TRAIN_M)) & (pl.col("leg") == leg) & (pl.col("win") == "w2071"))
              .group_by("Cell").agg([pl.col(q).mean() for q in PANEL]))
    T_h = lev(TRUTH, "hist", "h2000")
    out = {"ceiling": (lev(REPLICA, leg, "w2071"), lev(REPLICA, "hist", "h2000"), lev(REPLICA, "ctl_obs", "w2071")),
           "ceiling_mean": (mean_w, lk_h, lk_c),
           "persist_h": (T_h, T_h, None),
           "persist_19": (lev(TRUTH, "hist", "y2019"), T_h, None),
           "lookup": (lk, lk_h, lk_c)}
    return {k: v for k, v in out.items() if v[0] is not None}


def anchored(df: pl.DataFrame, train_legs, train_members) -> pl.DataFrame:
    """Adds anc_<q>, anc climate dclim_<c> = leg climate - anchor-legs' climate, and memoff_<q>. Leave-one-leg-out."""
    base = df.filter(pl.col("member").is_in(list(train_members)) & pl.col("leg").is_in(list(train_legs))
                     & (pl.col("win") != "h2000"))
    vals = PANEL + CLIM_COLS
    tot = base.group_by(["Cell", "win"]).agg([pl.col(v).sum().alias(f"S_{v}") for v in vals]
                                            + [pl.col(v).count().alias(f"N_{v}") for v in vals])
    per = base.group_by(["Cell", "win", "leg"]).agg([pl.col(v).sum().alias(f"s_{v}") for v in vals]
                                                   + [pl.col(v).count().alias(f"n_{v}") for v in vals])
    out = df.filter(pl.col("win") != "h2000").join(tot, on=["Cell", "win"], how="left").join(
        per, on=["Cell", "win", "leg"], how="left")
    out = out.with_columns([pl.col(f"s_{v}").fill_null(0.0) for v in vals] + [pl.col(f"n_{v}").fill_null(0) for v in vals])
    ex = []
    for v in vals:
        den = pl.col(f"N_{v}") - pl.col(f"n_{v}")
        a = pl.when(den > 0).then((pl.col(f"S_{v}") - pl.col(f"s_{v}")) / den).otherwise(None)
        ex.append(a.alias(f"anc_{v}"))
    out = out.with_columns(ex).with_columns([(pl.col(c) - pl.col(f"anc_{c}")).alias(f"dclim_{c}") for c in CLIM_COLS]
                                            + [(pl.col(f"{c}_cb") - pl.col(f"anc_{c}")).alias(f"dclim_{c}_cb")
                                               for c in CLIM_COLS])
    hm = (df.filter(pl.col("member").is_in(list(train_members)) & (pl.col("leg") == "hist"))
          .group_by("Cell").agg([pl.col(q).mean().alias(f"hm_{q}") for q in PANEL]))
    out = out.join(hm, on="Cell", how="left").with_columns(
        [(pl.col(f"s0_{q}") - pl.col(f"hm_{q}")).alias(f"memoff_{q}") for q in PANEL])
    return out.drop([c for c in out.columns if c[:2] in ("S_", "N_", "s_", "n_") and c[2:] in vals])


def feats_r(variant):
    blind = variant.endswith("cb")
    clim = [f"{x}_cb" for x in CLIM_COLS] if blind else CLIM_COLS
    dcl = [f"dclim_{x}_cb" for x in CLIM_COLS] if blind else [f"dclim_{x}" for x in CLIM_COLS]
    return (clim + dcl + [f"anc_{q}" for q in PANEL] + [f"s0_{q}" for q in PANEL] + [f"memoff_{q}" for q in PANEL]
            + ["lat", "lon", "soil_code"])


def fit_predict_seen(tr: pl.DataFrame, te: pl.DataFrame, variant: str) -> pl.DataFrame:
    """No fold: the cells are seen in training (only the run and the climate are held out)."""
    import lightgbm as lgb

    resid = variant.startswith("A7r")
    logt = variant.startswith("A7rL")
    f = feats_r(variant) if resid else feats(variant.replace("-seen", ""))
    out = te.select("Cell", "leg")
    for q in PANEL:
        t = tr.filter(pl.col(q).is_not_null() & (pl.col(f"anc_{q}").is_not_null() if resid else pl.lit(True)))
        lq = logt and q in LOG_EPS
        if lq:  # mode `logt`: relative target, so a sparse cell weighs as much as a dense one
            e = LOG_EPS[q]
            y = np.log((t[q].to_numpy() + e) / (t[f"anc_{q}"].to_numpy() + e))
        else:
            y = (t[q] - t[f"anc_{q}"]).to_numpy() if resid else t[q].to_numpy()
        mdl = lgb.train(PARAMS, lgb.Dataset(t.select(f).to_numpy(), y), ROUNDS)
        p = mdl.predict(te.select(f).to_numpy())
        if resid:  # where a cell has no anchor (no trees in any training run): the direct model of the same arm
            anc = te[f"anc_{q}"].to_numpy().astype(float)
            p = (anc + LOG_EPS[q]) * np.exp(p) - LOG_EPS[q] if lq else p + anc
            miss = ~np.isfinite(anc)
            if miss.any():
                f0 = feats("A7scb" if variant.endswith("cb") else "A7s")
                t0 = tr.filter(pl.col(q).is_not_null())
                m0 = lgb.train(PARAMS, lgb.Dataset(t0.select(f0).to_numpy(), t0[q].to_numpy()), ROUNDS)
                p[miss] = m0.predict(te.filter(pl.Series(miss)).select(f0).to_numpy())
        if q == "n_per_patch":
            p = np.maximum(p, 0.0)
        out = out.with_columns(pl.Series(q, p))
    return out


def run_split_seen(df, name, train_legs, test_legs, train_members=TRAIN_M, variants=("A7s-seen", "A7r", "A7rcb")):
    t0 = time.time()
    cells = PP.cells().select("Cell", "lat")
    an = anchored(df, train_legs, train_members)
    tr_s = df.filter(pl.col("member").is_in(list(train_members))
                     & (pl.col("leg").is_in(list(train_legs)) | (pl.col("leg") == "hist")))
    te_s = df.filter((pl.col("member") == TRUTH) & pl.col("leg").is_in([*test_legs, "ctl_obs"]) & (pl.col("win") == "w2071"))
    tr_r = an.filter(pl.col("member").is_in(list(train_members)) & pl.col("leg").is_in(list(train_legs)))
    te_r = an.filter((pl.col("member") == TRUTH) & pl.col("leg").is_in([*test_legs, "ctl_obs"]) & (pl.col("win") == "w2071"))
    T_h = lev(TRUTH, "hist", "h2000")
    preds = {v: fit_predict_seen(tr_s if v == "A7s-seen" else tr_r, te_s if v == "A7s-seen" else te_r, v)
             for v in variants}
    pd = os.path.join(EVAL, "preds_seen", f"s{os.environ.get('LGB_SEED', '1')}")
    os.makedirs(pd, exist_ok=True)
    for v, p in preds.items():
        p.write_parquet(os.path.join(pd, f"{name.replace(':', '_')}_{v}.parquet"))
    rows = []
    for leg in test_legs:
        cand = {}
        for v, p in preds.items():
            pc = p.filter(pl.col("leg") == "ctl_obs").drop("leg")
            cand[v] = (p.filter(pl.col("leg") == leg).drop("leg"), T_h, pc if pc.height else None)
        cand.update(nulls(df, leg, train_legs, train_members))
        for r in score_leg(leg, cand, cells):
            rows.append(dict(split=name, n_train_legs=len(train_legs), n_train_members=len(train_members), **r))
    log(f"{name}: {len(rows)} rows ({time.time() - t0:.0f}s)")
    return rows


def run_split(df, name, train_legs, test_legs, train_members=TRAIN_M, variants=("A7s", "A7scb", "A7"),
              with_nulls=True):
    t0 = time.time()
    cells = PP.cells().select("Cell", "lat")
    tr = df.filter(pl.col("member").is_in(list(train_members))
                   & (pl.col("leg").is_in(list(train_legs)) | (pl.col("leg") == "hist")))
    te = df.filter((pl.col("member") == TRUTH) & (pl.col("leg").is_in([*test_legs, "hist", "ctl_obs"]))
                   & pl.col("win").is_in(["w2071", "h2000"]))
    preds = {v: fit_predict(tr, te, v) for v in variants}
    rows = []
    for leg in test_legs:
        cand = {}
        for v, p in preds.items():
            pw = p.filter(pl.col("leg") == leg).drop("leg")
            ph = p.filter(pl.col("leg") == "hist").drop("leg")
            pc = p.filter(pl.col("leg") == "ctl_obs").drop("leg")
            cand[v] = (pw, ph, pc if pc.height else None)
        if with_nulls:
            cand.update(nulls(df, leg, train_legs, train_members))
        for r in score_leg(leg, cand, cells):
            rows.append(dict(split=name, n_train_legs=len(train_legs), n_train_members=len(train_members), **r))
    log(f"{name}: {len(rows)} rows ({time.time() - t0:.0f}s)")
    return rows


def main():
    os.makedirs(EVAL, exist_ok=True)
    mode = sys.argv[1] if len(sys.argv) > 1 else "core"
    df = build_rows()
    log(f"rows {df.height}: {df.group_by(['member']).len().sort('member').rows()}")
    G = PP.GCMS
    rows = []
    if mode == "core":
        for g in G:
            other = [lg for lg in SCEN_LEGS if gcm_of(lg) != g]
            ctl = [c for c in CTLS if not (c == "ctl_mpi370" and g == "mpi-esm1-2-hr")]
            rows += run_split(df, f"HG:{g}", other + ctl, [f"{g}_{s}" for s in PP.SCENS])
            o585 = [lg for lg in other if scen_of(lg) != "ssp585"]
            rows += run_split(df, f"H585G:{g}", o585 + ctl, [f"{g}_ssp585"])
        rows += run_split(df, "H585", [lg for lg in SCEN_LEGS if scen_of(lg) != "ssp585"] + CTLS,
                          [lg for lg in SCEN_LEGS if scen_of(lg) == "ssp585"])
    elif mode == "seen":
        for g in G:
            other = [lg for lg in SCEN_LEGS if gcm_of(lg) != g]
            ctl = [c for c in CTLS if not (c == "ctl_mpi370" and g == "mpi-esm1-2-hr")]
            rows += run_split_seen(df, f"HG:{g}", other + ctl, [f"{g}_{s}" for s in PP.SCENS])
            o585 = [lg for lg in other if scen_of(lg) != "ssp585"]
            rows += run_split_seen(df, f"H585G:{g}", o585 + ctl, [f"{g}_ssp585"])
    elif mode == "more":
        new_m = [m for m in (5, 6) if lev(m, "hist", "h2000") is not None]
        sets = {"base": (SCEN_LEGS, TRAIN_M), "mod": (ALL_SLEGS, TRAIN_M),
                "run": (SCEN_LEGS, (*TRAIN_M, *new_m)), "both": (ALL_SLEGS, (*TRAIN_M, *new_m))}
        log(f"new members present: {new_m}")
        for g in G:
            for nm, (pool, mem) in sets.items():
                legs = [lg for lg in pool if gcm_of(lg) != g] + ["ctl_obs"]
                legs = [lg for lg in legs if df.filter(pl.col("leg") == lg).height > 0]
                var = ("A7r", "A7rcb") if nm == "both" else ("A7r",)
                rows += run_split_seen(df, f"{nm}:{g}", legs, [f"{g}_{s}" for s in PP.SCENS], mem, var)
    elif mode == "logt":
        new_m = [m for m in (5, 6) if lev(m, "hist", "h2000") is not None]
        for g in G:
            legs = [lg for lg in ALL_SLEGS if gcm_of(lg) != g] + ["ctl_obs"]
            legs = [lg for lg in legs if df.filter(pl.col("leg") == lg).height > 0]
            rows += run_split_seen(df, f"logt:{g}", legs, [f"{g}_{s}" for s in PP.SCENS], (*TRAIN_M, *new_m),
                                   ("A7r", "A7rL"))
    elif mode == "curves_seen":
        def one(name, legs, test, mem=TRAIN_M):
            an = anchored(df, legs, mem)
            tr = an.filter(pl.col("member").is_in(list(mem)) & pl.col("leg").is_in(list(legs)))
            te = an.filter((pl.col("member") == TRUTH) & pl.col("leg").is_in([test, "ctl_obs"])
                           & (pl.col("win") == "w2071"))
            p = fit_predict_seen(tr, te, "A7r")
            pc = p.filter(pl.col("leg") == "ctl_obs").drop("leg")
            cand = {"A7r": (p.filter(pl.col("leg") == test).drop("leg"), lev(TRUTH, "hist", "h2000"), pc)}
            return [dict(split=name, n_train_legs=len(legs), n_train_members=len(mem), **r)
                    for r in score_leg(test, cand, PP.cells().select("Cell", "lat"))]
        for g in G:
            others = [x for x in G if x != g]
            test = f"{g}_ssp370"
            for n in range(1, 5):
                for combo in itertools.combinations(others, n):
                    legs = [lg for lg in SCEN_LEGS if gcm_of(lg) in combo] + ["ctl_obs"]
                    rows += one(f"NGs{n}:{g}:{'+'.join(combo)}", legs, test)
            full = [lg for lg in SCEN_LEGS if gcm_of(lg) != g] + ["ctl_obs"]
            for k in range(1, 4):
                for mem in itertools.combinations(TRAIN_M, k):
                    rows += one(f"NMs{k}:{g}:{'+'.join(map(str, mem))}", full, test, mem)
            rows += one(f"ENV:{g}", [lg for lg in full if not lg.endswith("ssp585")], test)
            log(f"curves_seen {g} done")
    elif mode == "curves":
        for g in G:
            others = [x for x in G if x != g]
            for n in range(1, 5):
                for combo in itertools.combinations(others, n):
                    legs = [lg for lg in SCEN_LEGS if gcm_of(lg) in combo]
                    ctl = [c for c in CTLS if not (c == "ctl_mpi370" and "mpi-esm1-2-hr" not in combo)]
                    rows += run_split(df, f"NG{n}:{g}:{'+'.join(combo)}", legs + ctl,
                                      [f"{g}_ssp370", f"{g}_ssp585"], variants=("A7s",), with_nulls=False)
            legs = [lg for lg in SCEN_LEGS if gcm_of(lg) != g] + [c for c in CTLS
                                                                    if not (c == "ctl_mpi370" and g == "mpi-esm1-2-hr")]
            for k in (1, 2):
                for mem in itertools.combinations(TRAIN_M, k):
                    rows += run_split(df, f"NM{k}:{g}:{'+'.join(map(str, mem))}", legs,
                                      [f"{g}_ssp370", f"{g}_ssp585"], train_members=mem, variants=("A7s",),
                                      with_nulls=False)
    out = pl.DataFrame(rows)
    sfx = os.environ.get("LGB_SEED", "")
    out.write_csv(os.path.join(EVAL, f"a7_{mode}{'_s' + sfx if sfx else ''}.csv"))
    keep = ["split", "test_leg", "arm", "n_cells", "pass_rate", "pass_rate_flat10", "stems_ratio",
            "agb_per_stem_ratio", "resp_n_per_patch_slope_deatt", "ctl_resp_n_per_patch_slope_deatt"]
    with pl.Config(tbl_rows=400, tbl_cols=20, fmt_str_lengths=40):
        print(out.select([c for c in keep if c in out.columns]))


if __name__ == "__main__":
    main()
