#!/usr/bin/env python3
"""explore_glob_a7.py -- LINE X, arm A7 on the global venue (ADR 0315): the DIRECT, NON-RECURSIVE window map
(EXECUTION_PLAN rev. 2: "20-30-year climate window -> state distribution, no rollout -- the benchmark every recursive
arm must beat on response").

One LightGBM regressor per panel quantity, cross-fitted over the 5 spatial folds (train on folds != k, predict fold k),
on the GS370 split: training rows = members 2,3,4,6 x {historical 1985-2014, ssp126 2071-2100, ssp245 2071-2100} x dev
cells; test = member 8, ssp370 2071-2100 (and its historical window, the arm's own response baseline). Fixed
hyper-parameters, no tuning on the test member (member 7 is not used).

Variants (one variable each):
  A7     climate of the target window (30-yr means) + lon/lat/soil
  A7s    A7 + the member's own 1985-2014 panel statistics (the start state a coupled emulator would know)
  A7cb   A7's climate-blind twin: every row gets its cell's 1985-2014 climate instead of the target window's
  A7scb  A7s's climate-blind twin
Output: eval/arms/<variant>/{pred_w2071.parquet, pred_h1985.parquet}; scores appended to eval/scores_GS370.csv.
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_glob_eval as ev  # noqa: E402

CLIM = os.path.join(ev.DATA, "climate")
ARMS = os.path.join(ev.EVAL, "arms")
CLIM_COLS = ["tmean_ann", "tcold_month", "twarm_month", "gdd5", "frost_days", "days_gt30", "prec_ann", "prec_hs",
             "pet_ann", "cwb_ann", "cwb_hs", "cwb_min3", "dry_spell_max", "rh_mean", "vpd_hs", "vpd_win10_sum",
             "swdown_ann", "lwnet_ann"] + [f"tstress_pft{k}" for k in range(7)]
PARAMS = dict(objective="regression", learning_rate=0.05, num_leaves=63, min_data_in_leaf=40, feature_fraction=0.8,
              bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1, num_threads=16, seed=1)
ROUNDS = 600
LEGS = {"historical": "h1985", "ssp126": "w2071", "ssp245": "w2071", "ssp370": "w2071"}


def climate_windows(cells: list[int]) -> pl.DataFrame:
    """(scen, Cell) -> 30-year means of CLIM_COLS for that leg's window."""
    out = []
    for scen, win in LEGS.items():
        y0, y1 = ev.WIN[win]
        d = (pl.scan_parquet(os.path.join(CLIM, "cell_year", f"GFDL-ESM4_{scen}.parquet"))
             .filter(pl.col("Cell").is_in(cells) & pl.col("Year").is_between(y0, y1))
             .group_by("Cell").agg([pl.col(c).cast(pl.Float64).mean() for c in CLIM_COLS]).collect())
        out.append(d.with_columns(pl.lit(scen).alias("scen")))
    return pl.concat(out)


def build_rows(cells_df: pl.DataFrame) -> pl.DataFrame:
    cells = cells_df["Cell"].to_list()
    cw = climate_windows(cells)
    hist_clim = cw.filter(pl.col("scen") == "historical").drop("scen").rename({c: f"{c}_cb" for c in CLIM_COLS})
    st = pl.read_parquet(os.path.join(CLIM, "cell_static.parquet")).select("Cell", "lon", "soil_code")
    rows = []
    for seed in (*ev.TRAIN, ev.TRUTH):
        h = ev.lev(ev.mname("historical", seed)).rename({q: f"s0_{q}" for q in ev.PANEL})
        for scen in LEGS:
            if seed == ev.TRUTH and scen not in ("historical", "ssp370"):
                continue  # the test member: only its baseline window and the held-out scenario
            if seed != ev.TRUTH and scen == "ssp370":
                continue  # GS370: ssp370 is never seen in training
            y = ev.lev(ev.mname(scen, seed))
            rows.append(y.with_columns(pl.lit(seed).alias("seed"), pl.lit(scen).alias("scen"))
                        .join(h, on="Cell").join(cw.filter(pl.col("scen") == scen).drop("scen"), on="Cell"))
    df = pl.concat(rows).join(hist_clim, on="Cell").join(cells_df, on="Cell").join(st, on="Cell")
    return df


def fit_predict(df: pl.DataFrame, variant: str) -> pl.DataFrame:
    import lightgbm as lgb

    blind = variant.endswith("cb")
    clim = [f"{c}_cb" for c in CLIM_COLS] if blind else CLIM_COLS
    feats = clim + ["lat", "lon", "soil_code"] + ([f"s0_{q}" for q in ev.PANEL] if variant.startswith("A7s") else [])
    preds = []
    for k in range(1, 6):
        tr = df.filter((pl.col("fold") != k) & (pl.col("seed") != ev.TRUTH))
        te = df.filter((pl.col("fold") == k) & (pl.col("seed") == ev.TRUTH))
        out = te.select("Cell", "scen")
        for q in ev.PANEL:
            t = tr.filter(pl.col(q).is_not_null())
            m = lgb.train(PARAMS, lgb.Dataset(t.select(feats).to_numpy(), t[q].to_numpy()), ROUNDS)
            p = m.predict(te.select(feats).to_numpy())
            if q == "n_per_patch":
                p = np.maximum(p, 0.0)
            out = out.with_columns(pl.Series(q, p))
        preds.append(out)
    return pl.concat(preds)


def main():
    t0 = time.time()
    cells = ev.dev_cells()
    df = build_rows(cells)
    ev.log(f"rows {df.height} ({df.group_by(['seed', 'scen']).len().sort(['seed', 'scen']).rows()})")
    T_w, T_h = ev.lev(ev.mname("ssp370", ev.TRUTH)), ev.lev(ev.mname("historical", ev.TRUTH))
    R_w, R_h = ev.lev(ev.mname("ssp370", ev.REPLICA)), ev.lev(ev.mname("historical", ev.REPLICA))
    tb = (T_w.filter(pl.col("n_per_patch") > 0).select("Cell")
          .vstack(T_h.filter(pl.col("n_per_patch") > 0).select("Cell")).unique())
    scored = cells.join(tb, on="Cell")
    rows = []
    for v in ("A7", "A7cb", "A7s", "A7scb"):
        p = fit_predict(df, v)
        d = os.path.join(ARMS, v)
        os.makedirs(d, exist_ok=True)
        pw = p.filter(pl.col("scen") == "ssp370").drop("scen")
        ph = p.filter(pl.col("scen") == "historical").drop("scen")
        pw.write_parquet(os.path.join(d, "pred_w2071.parquet"))
        ph.write_parquet(os.path.join(d, "pred_h1985.parquet"))
        s = ev.score(pw, ph, T_w, T_h, R_w, R_h, scored)
        rows.append(dict(split="GS370", baseline=v, expect="arm", **s))
        ev.log(v, {k: (round(x, 4) if isinstance(x, float) else x) for k, x in s.items()})
    new = pl.DataFrame(rows)
    f = os.path.join(ev.EVAL, "scores_GS370.csv")
    base = pl.read_csv(os.path.join(ev.EVAL, "nulls_GS370.csv"))
    pl.concat([base, new], how="diagonal_relaxed").write_csv(f)
    ev.log(f"wrote {f} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
