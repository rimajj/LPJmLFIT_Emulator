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


def feats() -> list[str]:
    return (CLIM + [f"dclim_{c}" for c in CLIM] + [f"anc_{q}" for q in QS] + [f"s0_{q}" for q in QS]
            + [f"memoff_{q}" for q in QS] + ["lat", "lon", "soil_code"])


def stage_fit(a) -> None:
    import lightgbm as lgb

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
    rows = states.filter((pl.col("member").is_in(TRAIN_M) & pl.col("leg").is_in(train_legs)
                          & pl.col("Year").is_in(TRAIN_YEARS))
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
    rows = rows.join(s0_table(), on=["Cell", "member"], how="left").join(cells, on="Cell", how="left")
    rows = rows.sort("member", "leg", "Year", "Cell")  # deterministic row order (LightGBM bagging depends on it)
    tr = rows.filter(pl.col("member").is_in(TRAIN_M))
    te = rows.filter(pl.col("member").is_in([TRUTH, SECOND]))
    log(f"{g}: train rows {tr.height}, test rows {te.height} ({time.time() - t0:.0f}s)")
    f = feats()
    out = te.select("member", "leg", "Cell", "Year", *[pl.col(f"anc_{q}") for q in QS])
    for q in QS:
        t = tr.filter(pl.col(q).is_not_null() & pl.col(f"anc_{q}").is_not_null())
        if q in LOG_EPS:
            e = LOG_EPS[q]
            y = np.log((t[q].to_numpy() + e) / (t[f"anc_{q}"].to_numpy() + e))
        else:
            y = (t[q] - t[f"anc_{q}"]).to_numpy()
        mdl = lgb.train(A7.PARAMS, lgb.Dataset(t.select(f).to_numpy(), y), A7.ROUNDS)
        p = mdl.predict(te.select(f).to_numpy())
        anc = te[f"anc_{q}"].to_numpy().astype(float)
        p = (anc + LOG_EPS[q]) * np.exp(p) - LOG_EPS[q] if q in LOG_EPS else p + anc
        if q == "n_per_patch":
            p = np.maximum(p, 0.0)
        out = out.with_columns(pl.Series(q, p))
        log(f"{g} {q}: {t.height} rows fitted ({time.time() - t0:.0f}s)")
    out.write_parquet(os.path.join(OUT, f"preds_{g}.parquet"))
    log(f"{g}: wrote {out.height} predictions")


def stage_score(a) -> None:
    w = PP.cells().select("Cell", "lat").with_columns(np.cos(np.deg2rad(pl.col("lat"))).alias("w")).drop("lat")
    hist = {m: pl.read_parquet(os.path.join(YEARLY, f"m{m}_hist.parquet")).filter(pl.col("Year") == 2019) for m in (4,)}
    yr, cs = [], []
    for g in PP.GCMS:
        pf = os.path.join(OUT, f"preds_{g}.parquet")
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
    Y.write_csv(os.path.join(OUT, "drift_years.csv"))
    C = pl.DataFrame(cs)
    C.write_csv(os.path.join(OUT, "drift_cases.csv"))
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
    ap.add_argument("stage", choices=["fit", "score"])
    ap.add_argument("--g", default="gfdl-esm4", choices=PP.GCMS)
    a = ap.parse_args()
    {"fit": stage_fit, "score": stage_score}[a.stage](a)
    log("=== DONE")


if __name__ == "__main__":
    main()
