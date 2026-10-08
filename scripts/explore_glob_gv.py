#!/usr/bin/env python3
"""explore_glob_gv.py -- LINE X, the model-version transfer split GV of ADR 0315 (owner: "the emulator needs to work
with every model version"). Reported, not gated (ADR 0315 sec. 5). Scorer = explore_glob_eval.score, unchanged.

THREE PARTS, each a one-variable comparison:

  A  VERSION EFFECT IN THE DATA (no model). Same climate model (GFDL-ESM4), same legs, two builds: Feb-5 (members
     2,3,4,6,7,8) vs May-26 (members 9,10). Truth = a May member, replica (tolerance + noise) = the other May member;
     both orientations (9|10, 10|9). Candidates:
       replica     the other May member              -- the May build's own single-member ceiling
       feb_mean    mean of Feb members 2,3,4,6,7     -- "the build does not matter", an expectation of the Feb model
       feb_single  Feb member 8                      -- one Feb realization
     The SAME candidates scored on a Feb truth (member 8, replica 7) are the in-build reference (`ref_feb` rows):
     there feb_mean is ADR 0315's ceiling_mean (0.281 at ssp370) and member 7 the ceiling (0.173).
  B  ARM A7 / A7s ON THE MAY BUILD. Trained on Feb members 2,3,4,6,7, ALL four legs (GV holds out the build, not a
     scenario), cross-fitted over the 5 spatial folds as in explore_glob_a7.py, fixed hyper-parameters, no tuning.
     Predicted for May members 9 and 10 (each with ITS OWN 1985-2014 state for A7s) AND for Feb member 8 (role
     `val` in the registry; used here only as the in-build reference with identical training, never for tuning).
  C  THE OCT-BUILD REANALYSIS FAMILY (GSWP3-W5E5 obsclim, 1990-2019; members 1,2,3 = Oct-1 build, 5/6/7 = Oct-6/7/8).
     Build AND forcing both differ from training -- confounded, and no Feb run on this forcing exists, so nothing
     here can separate them. Level only (one window, no response). Truth = members 1,2,3 in turn, replica = the next
     Oct-1 member (1|2, 2|3, 3|1). Candidates:
       oct_other     the replica                                   -- the Oct-1 build's single-member ceiling
       oct_mean      mean of the four OTHER Oct members (incl. Oct-6/7/8) -- oracle expectation of the Oct family
       feb_hist_mean Feb members 2,3,4,6,7, GFDL historical 1985-2014 -- "nothing differs" null
       A7            Feb-trained A7 fed the GSWP3-W5E5 1990-2019 climate
     Also: area-weighted stem ratios Oct/Feb by latitude band (tropics |lat|<23.5, temperate 23.5-50, boreal >50).

WHAT EACH MUST RETURN, written before the run (ADR 0184):
  A  If the Feb->May build change is inert for the panel: feb_mean->May pass ~ feb_mean->Feb8 pass (within the
     9-vs-10 orientation difference), feb_single->May ~ may_other, area ratios within 0.05 of 1. A version effect
     shows as feb_mean->May falling below feb_mean->Feb8 by MORE than the two orientations differ. ADR 0314 found the
     GFDL Feb and May tables match the same mortality parameters, so the prior is "inert"; this is the test of it.
  B  A7s->May ~ A7s->Feb8 if the version is inert. A7 (no state) is expected far below (0.05-0.06 on GM).
  C  ADR 0314: the Oct family uses MORT_TEMP_FACTOR 4.0 (less cold-stress mortality than 5.0) and a 14 C (not 12.5)
     tropical-tree cold limit, plus new mortality code. Expected sign: Oct/Feb stems ratio > 1 in the boreal band
     (less temperature mortality) -- the forcing difference can move it either way, so the sign is a weak test, the
     magnitude unknown. oct_other is the ceiling; feb_hist_mean and A7 are both expected well below it.
Output: eval/scores_GV.csv, eval/gv_lat_bands.csv, preds eval/arms/GV/<variant>/.
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_glob_a7 as a7  # noqa: E402
import explore_glob_eval as ev  # noqa: E402

FEB_TRAIN, FEB_VAL, MAY = (2, 3, 4, 6, 7), 8, (9, 10)
OCT1, OCT_ALL = (1, 2, 3), (1, 2, 3, 5, 6, 7)
LEGS = ("historical", "ssp126", "ssp245", "ssp370")
SUMMARY = ("pass_rate", "pass_rate_flat10", "stems_ratio", "agb_per_stem_ratio", "resp_n_per_patch_slope_deatt",
           "resp_Wooddens_q50_slope_deatt")


def oname(seed: int) -> str:
    return f"GSWP3-W5E5_obsclim_s{seed}_h1990"


def mean_of(names: list[str]) -> pl.DataFrame:
    return pl.concat([ev.lev(n) for n in names]).group_by("Cell").agg([pl.col(q).mean() for q in ev.PANEL])


def tree_cells(cells: pl.DataFrame, *ds: pl.DataFrame) -> pl.DataFrame:
    tb = pl.concat([d.filter(pl.col("n_per_patch") > 0).select("Cell") for d in ds]).unique()
    return cells.join(tb, on="Cell")


def clim(gcm: str, scen: str, y0: int, y1: int, cells: list[int]) -> pl.DataFrame:
    return (pl.scan_parquet(os.path.join(a7.CLIM, "cell_year", f"{gcm}_{scen}.parquet"))
            .filter(pl.col("Cell").is_in(cells) & pl.col("Year").is_between(y0, y1))
            .group_by("Cell").agg([pl.col(c).cast(pl.Float64).mean() for c in a7.CLIM_COLS]).collect())


def rows_for(seeds, cells_df: pl.DataFrame, cw: dict, st: pl.DataFrame) -> pl.DataFrame:
    out = []
    for seed in seeds:
        h = ev.lev(ev.mname("historical", seed)).rename({q: f"s0_{q}" for q in ev.PANEL})
        for scen in LEGS:
            y = ev.lev(ev.mname(scen, seed))
            out.append(y.with_columns(pl.lit(seed).alias("seed"), pl.lit(scen).alias("scen"))
                       .join(h, on="Cell").join(cw[scen], on="Cell"))
    return pl.concat(out).join(cells_df, on="Cell").join(st, on="Cell")


def fit_predict(tr_all: pl.DataFrame, te_all: pl.DataFrame, variant: str) -> pl.DataFrame:
    import lightgbm as lgb

    feats = a7.CLIM_COLS + ["lat", "lon", "soil_code"] + ([f"s0_{q}" for q in ev.PANEL] if variant == "A7s" else [])
    preds = []
    for k in range(1, 6):
        tr, te = tr_all.filter(pl.col("fold") != k), te_all.filter(pl.col("fold") == k)
        out = te.select("Cell", "seed", "scen")
        for q in ev.PANEL:
            t = tr.filter(pl.col(q).is_not_null())
            m = lgb.train(a7.PARAMS, lgb.Dataset(t.select(feats).to_numpy(), t[q].to_numpy()), a7.ROUNDS)
            p = m.predict(te.select(feats).to_numpy())
            out = out.with_columns(pl.Series(q, np.maximum(p, 0.0) if q == "n_per_patch" else p))
        preds.append(out)
    return pl.concat(preds)


def pick(p: pl.DataFrame, seed, scen: str) -> pl.DataFrame:
    return p.filter((pl.col("seed") == seed) & (pl.col("scen") == scen)).drop("seed", "scen")


def emit(rows: list, part: str, truth: str, leg: str, name: str, s: dict):
    rows.append(dict(part=part, truth=truth, leg=leg, candidate=name, **s))
    ev.log(part, truth, leg, name, {k: round(s[k], 4) for k in SUMMARY if s.get(k) is not None})


def lat_bands(cells: pl.DataFrame, feb: pl.DataFrame, octm: pl.DataFrame) -> pl.DataFrame:
    d = (cells.join(feb.select("Cell", pl.col("n_per_patch").alias("nF")), on="Cell")
         .join(octm.select("Cell", pl.col("n_per_patch").alias("nO")), on="Cell").fill_null(0.0)
         .with_columns(np.cos(np.deg2rad(pl.col("lat"))).alias("w"),
                       pl.col("lat").abs().cut([23.5, 50.0], labels=["tropics", "temperate", "boreal"]).alias("band")))
    ratio = (pl.col("w") * pl.col("nO")).sum() / (pl.col("w") * pl.col("nF")).sum()
    return d.group_by("band").agg(pl.len().alias("n_cells"), ratio.alias("stems_oct_over_feb")).sort("band")


def main():
    t0 = time.time()
    cells = ev.dev_cells()
    clist = cells["Cell"].to_list()
    st = pl.read_parquet(os.path.join(a7.CLIM, "cell_static.parquet")).select("Cell", "lon", "soil_code")
    rows = []

    # ---- A: version effect in the data
    for leg in LEGS:
        lw = lambda s, leg=leg: ev.lev(ev.mname(leg, s))  # noqa: E731
        lh = lambda s: ev.lev(ev.mname("historical", s))  # noqa: E731
        fm_w = mean_of([ev.mname(leg, s) for s in FEB_TRAIN])
        fm_h = mean_of([ev.mname("historical", s) for s in FEB_TRAIN])
        for tr, rp, tag in ((9, 10, "may9"), (10, 9, "may10"), (8, 7, "ref_feb8")):
            T_w, T_h, R_w, R_h = lw(tr), lh(tr), lw(rp), lh(rp)
            sc = tree_cells(cells, T_w, T_h)
            cand = {"replica": (R_w, R_h), "feb_mean": (fm_w, fm_h)}
            if tr != FEB_VAL:
                cand["feb_single"] = (lw(FEB_VAL), lh(FEB_VAL))
            for name, (pw, ph) in cand.items():
                emit(rows, "A", tag, leg, name, ev.score(pw, ph, T_w, T_h, R_w, R_h, sc))

    # ---- B: A7 / A7s trained on Feb 2,3,4,6,7 (all legs), predicted for May 9,10 and Feb 8
    cw = {s: clim("GFDL-ESM4", s, *ev.WIN[a7.LEGS[s]], clist) for s in LEGS}
    tr_rows = rows_for(FEB_TRAIN, cells, cw, st)
    te_rows = rows_for((*MAY, FEB_VAL), cells, cw, st)
    ev.log(f"B: train rows {tr_rows.height}, test rows {te_rows.height}")
    preds = {v: fit_predict(tr_rows, te_rows, v) for v in ("A7", "A7s")}
    for v, p in preds.items():
        d = os.path.join(a7.ARMS, "GV", v)
        os.makedirs(d, exist_ok=True)
        p.write_parquet(os.path.join(d, "pred_gfdl.parquet"))
    for leg in LEGS:
        for tr, rp, tag in ((9, 10, "may9"), (10, 9, "may10"), (8, 7, "ref_feb8")):
            T_w, T_h = ev.lev(ev.mname(leg, tr)), ev.lev(ev.mname("historical", tr))
            R_w, R_h = ev.lev(ev.mname(leg, rp)), ev.lev(ev.mname("historical", rp))
            sc = tree_cells(cells, T_w, T_h)
            for v, p in preds.items():
                emit(rows, "B", tag, leg, v, ev.score(pick(p, tr, leg), pick(p, tr, "historical"),
                                                      T_w, T_h, R_w, R_h, sc))

    # ---- C: the Oct reanalysis family (level only)
    feb_hist = mean_of([ev.mname("historical", s) for s in FEB_TRAIN])
    oc = clim("GSWP3-W5E5", "obsclim", *ev.WIN["h1990"], clist)
    te_o = (pl.DataFrame({"Cell": clist}).join(oc, on="Cell").join(cells, on="Cell").join(st, on="Cell")
            .with_columns(pl.lit(0).alias("seed"), pl.lit("obsclim").alias("scen")))
    pa7 = fit_predict(tr_rows, te_o, "A7")
    pa7.write_parquet(os.path.join(a7.ARMS, "GV", "A7", "pred_obsclim.parquet"))
    pa7 = pick(pa7, 0, "obsclim")
    for tr, rp in ((1, 2), (2, 3), (3, 1)):
        T, Rr = ev.lev(oname(tr)), ev.lev(oname(rp))
        sc = tree_cells(cells, T)
        cand = {"oct_other": Rr, "oct_mean": mean_of([oname(s) for s in OCT_ALL if s != tr]),
                "feb_hist_mean": feb_hist, "A7": pa7}
        for name, pw in cand.items():
            s = ev.score(pw, pw, T, T, Rr, Rr, sc)
            emit(rows, "C", f"oct{tr}", "obsclim", name, {k: x for k, x in s.items() if not k.startswith("resp_")})
    octm = mean_of([oname(s) for s in OCT_ALL])
    lb = lat_bands(tree_cells(cells, octm, feb_hist), feb_hist, octm)
    ev.log("C: Oct/Feb area-weighted stems by latitude band\n" + str(lb))
    lb.write_csv(os.path.join(ev.EVAL, "gv_lat_bands.csv"))

    pl.DataFrame(rows, infer_schema_length=None).write_csv(os.path.join(ev.EVAL, "scores_GV.csv"))
    ev.log(f"wrote scores_GV.csv ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
