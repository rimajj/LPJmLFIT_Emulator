#!/usr/bin/env python3
"""explore_panel_popmap.py -- ADR 0363 stages A and C: the POPULATION MAP. New yearly outputs beside the release's
forest map: the distributions (9 quantile levels) of tree height, biomass per tree, the four traits, the ACTUAL 95 %
rooting depth and age; the seven tree-type shares; and the death rates (total, chance, excess). Same rows, anchors,
climate offsets, start state, held-out design and LightGBM settings as the release's forest map (`fix`, ADR 0352):
explore_panel_yearly_drift.build_rows supplies the base rows; this script adds each new quantity's values (from
xpanel/yearly2/, scripts/build_panel_yearly_v2.py), its leave-one-leg-out anchor, its 2000-2019 start level and that
level's offset from the training runs'.

Arms (ADR 0363 sec. 3, 6):
  A0   anchor alone (null; written as the anc_ columns)
  AQ   one model per quantile level (target = value - anchor; log ratio for biomass per tree); sorted per row
  ALS  median + ln(90th - 10th percentile) models; other levels = median + spread x the anchor's standardised shape
  shares: one model per type share (value - anchor), clipped at 0, renormalised
  BM   death rates from the map's inputs (30-year climate)
  BMW  BM + this / last year's weather z-scores (50) + the daily-bucket stress statistics (ADR 0355)
  BMN  (group `mortn`; oracle, ADR 0363 sec. 8) BMW + the run's own yearly tree NPP anomaly (yearly2_npp/)
Usage:
  fit --g <held-out model> --group <Height|agb|SLA|Wooddens|D95max|minwscal|D95|Age|shares|mort>
      -> xpanel/eval/popmap/preds_<g>_<group>.parquet (rows: runs m4 (truth) and m5 (harness) x the held-out legs x
         every year 2020-2100)
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
import explore_panel_yearly_drift as YD  # noqa: E402

YEARLY2 = os.path.join(PP.OUT, "yearly2")
OUT = os.path.join(PP.OUT, "eval", "popmap")
PS = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
PN = ["p01", "p05", "p10", "p25", "p50", "p75", "p90", "p95", "p99"]
VARS = ["Height", "agb", "SLA", "Wooddens", "D95max", "minwscal", "D95", "Age"]
LOGV = {"agb": 1.0}  # log-ratio target, as the release's biomass per tree
SHARES = [f"share_{t}" for t in range(7)]
MORT = ["death_rate", "chance_rate", "excess_rate"]
NPP_DIR = os.path.join(PP.OUT, "yearly2_npp")
NPP_V = ["npp_per_tree", "share_npp_neg"]
NPP_COLS = [f"{k}_{v}" for v in NPP_V for k in ("n0", "n1", "nr0", "nr1", "nz0", "nz1")]


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def group_quantities(group: str) -> list[str]:
    if group in VARS:
        return [f"{group}_{pn}" for pn in PN]
    return SHARES if group == "shares" else MORT  # mort and mortn


def yearly2(m: int, leg: str, qs: list[str]) -> pl.DataFrame | None:
    f = os.path.join(YEARLY2, f"m{m}_{leg}.parquet")
    if not os.path.exists(f):
        return None
    d = pl.read_parquet(f)
    risk = pl.col("n_living") + pl.col("n_dead")
    d = d.with_columns(
        *[pl.when(pl.col("n_living") > 0).then(pl.col(f"n_t{t}") / pl.col("n_living")).otherwise(None)
          .alias(f"share_{t}") for t in range(7)],
        pl.when(risk > 0).then(pl.col("n_dead") / risk).otherwise(None).alias("death_rate"),
        pl.when(risk > 0).then(pl.col("exp_dead") / risk).otherwise(None).alias("chance_rate"),
        pl.when(risk > 0).then((pl.col("n_dead") - pl.col("exp_dead")) / risk).otherwise(None).alias("excess_rate"))
    return d.select("Cell", "Year", *qs).with_columns(pl.lit(m).alias("member"), pl.lit(leg).alias("leg"))


def add_quantities(rows: pl.DataFrame, qs: list[str], train_legs: list[str]) -> pl.DataFrame:
    """Join each new quantity's value, its leave-one-leg-out per-year anchor (build_rows's rule) and its run's
    2000-2019 start level / offset from the training runs'. A quantity the release's map already carries (the four
    trait medians) keeps build_rows's columns (same values: yearly2 == yearly on them, build gate)."""
    have = [q for q in qs if f"anc_{q}" in rows.columns]
    qs = [q for q in qs if q not in have]
    if not qs:
        return rows
    st = pl.concat([d for m in PP.MEMBERS for lg in A7.ALL_SLEGS if (d := yearly2(m, lg, qs)) is not None])
    base = st.filter(pl.col("member").is_in(YD.TRAIN_M) & pl.col("leg").is_in(train_legs))
    tot = base.group_by("Cell", "Year").agg([pl.col(q).sum().alias(f"S_{q}") for q in qs]
                                           + [pl.col(q).count().alias(f"N_{q}") for q in qs])
    per = base.group_by("Cell", "Year", "leg").agg([pl.col(q).sum().alias(f"s_{q}") for q in qs]
                                                  + [pl.col(q).count().alias(f"n_{q}") for q in qs])
    r = (rows.join(st, on=["Cell", "Year", "member", "leg"], how="left")
         .join(tot, on=["Cell", "Year"], how="left").join(per, on=["Cell", "Year", "leg"], how="left"))
    ex = []
    for q in qs:
        s_, n_ = pl.col(f"s_{q}").fill_null(0.0), pl.col(f"n_{q}").fill_null(0)
        den = pl.col(f"N_{q}") - n_
        ex.append(pl.when(den > 0).then((pl.col(f"S_{q}") - s_) / den).otherwise(None).alias(f"anc_{q}"))
    r = r.with_columns(ex).drop([c for q in qs for c in (f"S_{q}", f"N_{q}", f"s_{q}", f"n_{q}")])
    # start level: the run's own 2000-2019 mean (shared by all its legs), offset from the training runs' mean
    h = pl.concat([d.with_columns(pl.lit(m).alias("member")) for m in PP.MEMBERS
                   if (d := yearly2(m, "hist", qs)) is not None])
    s0 = h.group_by("Cell", "member").agg([pl.col(q).mean().alias(f"s0_{q}") for q in qs])
    hm = s0.filter(pl.col("member").is_in(YD.TRAIN_M)).group_by("Cell").agg(
        [pl.col(f"s0_{q}").mean().alias(f"hm_{q}") for q in qs])
    s0 = s0.join(hm, on="Cell").with_columns(
        [(pl.col(f"s0_{q}") - pl.col(f"hm_{q}")).alias(f"memoff_{q}") for q in qs]).drop([f"hm_{q}" for q in qs])
    s0 = s0.with_columns(pl.col("member").cast(rows["member"].dtype))
    return r.join(s0, on=["Cell", "member"], how="left")


def npp_anomaly(m: int, leg: str) -> pl.DataFrame | None:
    """ADR 0363 sec. 8: the run's own tree NPP this (n0_) and last year (n1_), its ratio to the trailing 30-year mean
    (nr) and z-score against the 30 years before (nz; >= 15 years, 2000-2019 in front; 0 where constant)."""
    fh, fl = (os.path.join(NPP_DIR, f"m{m}_{x}.parquet") for x in ("hist", leg))
    if not (os.path.exists(fh) and os.path.exists(fl)):
        return None
    d = pl.concat([pl.read_parquet(fh), pl.read_parquet(fl)]).sort("Cell", "Year")
    d = d.with_columns(pl.col("npp_per_tree").fill_null(0.0), pl.col("share_npp_neg").fill_null(0.0))
    ex = []
    for v in NPP_V:
        mu = pl.col(v).shift(1).rolling_mean(window_size=30, min_samples=15).over("Cell")
        sd = pl.col(v).shift(1).rolling_std(window_size=30, min_samples=15).over("Cell")
        ex += [pl.col(v).alias(f"n0_{v}"),
               pl.when(mu.abs() > 1e-9).then(pl.col(v) / mu).otherwise(1.0).alias(f"nr0_{v}"),
               pl.when(sd > 1e-6 * (mu.abs() + 1.0)).then((pl.col(v) - mu) / sd).otherwise(0.0).alias(f"nz0_{v}")]
    d = d.with_columns(ex)
    d = d.with_columns([pl.col(f"{k}0_{v}").shift(1).over("Cell").alias(f"{k}1_{v}")
                        for v in NPP_V for k in ("n", "nr", "nz")])
    d = d.filter(pl.col("Year") >= YD.Y0).select("Cell", "Year", *NPP_COLS)
    return d.with_columns(pl.lit(m).alias("member"), pl.lit(leg).alias("leg"))


def tgt(q: str, v: np.ndarray, anc: np.ndarray) -> np.ndarray:
    e = LOGV.get(q.split("_p")[0])
    return np.log((v + e) / (anc + e)) if e else v - anc


def untgt(q: str, p: np.ndarray, anc: np.ndarray) -> np.ndarray:
    e = LOGV.get(q.split("_p")[0])
    return (anc + e) * np.exp(p) - e if e else p + anc


def fit(X: np.ndarray, y: np.ndarray):
    import lightgbm as lgb

    return lgb.train(YD.LGB_PARAMS, lgb.Dataset(X, y), YD.LGB_ROUNDS)


def feats_for(q: str, extra: list[str]) -> list[str]:
    return list(dict.fromkeys(YD.feats() + [f"anc_{q}", f"s0_{q}", f"memoff_{q}"] + extra))  # no duplicates


def fit_predict(tr: pl.DataFrame, te: pl.DataFrame, q: str, target: str, f: list[str], tv, uv, t0) -> np.ndarray:
    """Train on rows with a value and an anchor; predict on every test row (NaN where the anchor is missing)."""
    t = tr.filter(pl.col(target).is_not_null() & pl.col(f"anc_{target}").is_not_null())
    y = tv(t)
    ok = np.isfinite(y)
    m = fit(t.select(f).to_numpy()[ok], y[ok])
    p = uv(m.predict(te.select(f).to_numpy()), te)
    log(f"  {q}: fitted {int(ok.sum())} rows ({time.time() - t0:.0f}s)")
    return p


def stage_fit(a) -> None:
    os.makedirs(OUT, exist_ok=True)
    g, group = a.g, a.group
    t0 = time.time()
    R = YD.build_rows(g, t0=t0)
    tr, te, train_legs = R["tr"], R["te"], R["train_legs"]
    tr = tr.filter(pl.col("Year").is_in(R["train_years"]))
    qs = group_quantities(group)
    extra_q: list[str] = []
    tr = add_quantities(tr, qs, train_legs)
    te = add_quantities(te, qs, train_legs)
    log(f"{g} {group}: train {tr.height}, test {te.height} rows ({time.time() - t0:.0f}s)")
    keep = ["member", "leg", "Cell", "Year", "anc_n_per_patch"]
    out = te.select(*keep, *[pl.col(f"anc_{q}") for q in qs])
    cols = []
    if group in VARS:
        # AQ: one model per level
        P = []
        for q in qs:
            f = feats_for(q, extra_q)
            P.append(fit_predict(tr, te, q, q, f,
                                 lambda t, q=q: tgt(q, t[q].to_numpy().astype(float), t[f"anc_{q}"].to_numpy()
                                                    .astype(float)),
                                 lambda p, d, q=q: untgt(q, p, d[f"anc_{q}"].to_numpy().astype(float)), t0))
        P = np.sort(np.column_stack(P), axis=1)  # monotone rearrangement
        cols += [pl.Series(f"AQ_{q}", P[:, i]) for i, q in enumerate(qs)]
        # ALS: median + ln spread; shape from the anchor
        v, med = group, f"{group}_p50"
        lo, hi = f"{group}_p10", f"{group}_p90"

        def lsp(d, a_=""):
            return np.log(np.maximum(d[f"{a_}{hi}"].to_numpy().astype(float) - d[f"{a_}{lo}"].to_numpy()
                                     .astype(float), 0.0) + 1e-6 * np.abs(d[f"{a_}{med}"].to_numpy().astype(float))
                          + 1e-9)

        pmed = fit_predict(tr, te, f"ALS {med}", med, feats_for(med, extra_q),
                           lambda t: tgt(med, t[med].to_numpy().astype(float), t[f"anc_{med}"].to_numpy()
                                         .astype(float)),
                           lambda p, d: untgt(med, p, d[f"anc_{med}"].to_numpy().astype(float)), t0)
        trs = tr.filter(pl.col(hi).is_not_null() & pl.col(f"anc_{hi}").is_not_null())
        fs = feats_for(med, extra_q) + [f"anc_{hi}", f"anc_{lo}"]
        ms = fit(trs.select(fs).to_numpy(), lsp(trs) - lsp(trs, "anc_"))
        spread = np.exp(ms.predict(te.select(fs).to_numpy()) + lsp(te, "anc_"))
        log(f"  ALS spread {v}: fitted {trs.height} rows ({time.time() - t0:.0f}s)")
        asp = np.exp(lsp(te, "anc_"))
        amed = te[f"anc_{med}"].to_numpy().astype(float)
        for q in qs:
            shape = (te[f"anc_{q}"].to_numpy().astype(float) - amed) / np.where(asp > 0, asp, np.nan)
            cols.append(pl.Series(f"ALS_{q}", pmed + spread * np.nan_to_num(shape)))
    elif group == "shares":
        P = []
        for q in qs:
            P.append(fit_predict(tr, te, q, q, feats_for(q, extra_q),
                                 lambda t, q=q: (t[q] - t[f"anc_{q}"]).to_numpy().astype(float),
                                 lambda p, d, q=q: p + d[f"anc_{q}"].to_numpy().astype(float), t0))
        P = np.clip(np.nan_to_num(np.column_stack(P)), 0.0, None)
        P = P / np.where(P.sum(1, keepdims=True) > 0, P.sum(1, keepdims=True), 1.0)
        cols += [pl.Series(f"AQ_{q}", P[:, i]) for i, q in enumerate(qs)]
    else:  # mortality: BM and BMW
        wx = pl.concat([YD.weather_anomaly(lg) for lg in A7.ALL_SLEGS])
        bk = pl.concat([YD.bucket_anomaly(lg) for lg in A7.ALL_SLEGS])
        wcols = YD.DEP_W + YD.BK_COLS
        trw = tr.join(wx, on=["Cell", "Year", "leg"], how="left").join(bk, on=["Cell", "Year", "leg"], how="left")
        tew = te.join(wx, on=["Cell", "Year", "leg"], how="left").join(bk, on=["Cell", "Year", "leg"], how="left")
        assert trw.height == tr.height and tew.height == te.height
        arms = {"BM": (tr, te, []), "BMW": (trw, tew, wcols)}
        if group == "mortn":
            npp = pl.concat([d for m in PP.MEMBERS for lg in A7.ALL_SLEGS if (d := npp_anomaly(m, lg)) is not None])
            npp = npp.with_columns(pl.col("member").cast(tr["member"].dtype), pl.col("Cell").cast(tr["Cell"].dtype),
                                   pl.col("Year").cast(tr["Year"].dtype))
            trn = trw.join(npp, on=["Cell", "Year", "member", "leg"], how="left")
            ten = tew.join(npp, on=["Cell", "Year", "member", "leg"], how="left")
            assert trn["n0_npp_per_tree"].null_count() == 0 and ten["n0_npp_per_tree"].null_count() == 0, "NPP"
            arms = {"BMN": (trn, ten, wcols + NPP_COLS)}
        for arm, (TR, TE, ext) in arms.items():
            for q in qs:
                p = fit_predict(TR, TE, f"{arm} {q}", q, feats_for(q, ext),
                                lambda t, q=q: (t[q] - t[f"anc_{q}"]).to_numpy().astype(float),
                                lambda p, d, q=q: p + d[f"anc_{q}"].to_numpy().astype(float), t0)
                cols.append(pl.Series(f"{arm}_{q}", p))
    out = out.with_columns(cols)
    fo = os.path.join(OUT, f"preds_{g}_{group}.parquet")
    out.write_parquet(fo)
    log(f"{g} {group}: wrote {out.height} rows -> {fo} ({time.time() - t0:.0f}s)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["fit"])
    ap.add_argument("--g", default="gfdl-esm4", choices=PP.GCMS)
    ap.add_argument("--group", default="Height", choices=[*VARS, "shares", "mort", "mortn"])
    a = ap.parse_args()
    {"fit": stage_fit}[a.stage](a)
    log("=== DONE")


if __name__ == "__main__":
    main()
