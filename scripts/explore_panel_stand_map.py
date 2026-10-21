#!/usr/bin/env python3
"""explore_panel_stand_map.py -- the STAND MAP: the structure emulator also emits the stand inputs the learned daily
model reads (STATE NEXT item 3; skill daily-model: stand_m<k>_<leg>.npy = lai_stand, vegc, fpc_stand[1..10] at the end
of each year). Without it the daily model is still handed the ORIGINAL's stand, which flatters its score.

FORM: extra targets of the year-by-year structure arm (explore_panel_yearly_drift.py, ADR 0330), same rows, same
features (trailing 30-yr climate, its offset from the anchor legs' climate, the six structure anchors / start levels /
start offsets, lat, lon, soil code) PLUS, for each stand quantity, its own per-year anchor, the run's own 2000-2019 mean
and that mean's offset from the training runs'. One LightGBM model per stand quantity (explore_panel_a7.PARAMS, 400
rounds), target = value - anchor. lai_stand and vegc: every run (m1,m2,m3,m5,m6 train). fpc_stand per plant type
1..10 (ids 0-6 trees, 7-9 grasses): only runs m1-m4 on the first five climate models carry it, so those models train
on m1-m3 x the 12 legs of the 4 other first-five models. The six structure models are NOT refitted here.
Output: xpanel/eval/stand/preds_<g>.parquet (m4 and m5 on the held-out model's legs, every year 2020-2100);
`fit --hold k` (k = 1..3) refits with run k unseen -> preds_<g>_h<k>.parquet; `arrays` writes phase B's stand arrays
into a subdir of the f2 data dir (ADR 0331).

SCORE (stage `score`, the ADR 0330 measure): per case and year, the typical-cell (50th centile) and bad-cell (90th)
relative error vs a second run (m1, m2, m3 vs m4), dense cells (structure anchor >= 5 trees per patch) and all cells;
for lai_stand, vegc, tree cover (sum of types 1-7) and grass cover (8-10). Level = mean ratio 2071-2100; drift = mean
ratio 2081-2100 / 2051-2070 (after the start state has faded, ADR 0330 sec. 1) AND the ADR 0330 rule (/ 2021-2040).

WRITTEN BEFORE THE RUN (2026-10-12):
  harness  m5 scored as the emulator (lai_stand, vegc; m5 has no cover by type): level 0.9-1.1, drift 0.9-1.1.
  null     oracle (mean of m1-m3 on the held-out leg -- the runs that carry cover by type): level ~0.82.
  STAND MAP (expectations, not a pass -- the pass is phase B, the daily fluxes fed with this stand, pre-registered
           separately): leaf area and vegetation carbon level (dense, typical cell) 1.0-1.6x a second run, area totals
           within 3 %; tree and grass cover level 1.0-1.8x; drift (mid -> late) 0.9-1.2 for all four.
           Leaf area is the input the daily model leans on most (GPP), so it is the one to read first.
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

OUT = os.path.join(PP.OUT, "eval", "stand")
FPC = [f"fpc{p}" for p in range(1, 11)]
SQ = ["lai_stand", "vegc", *FPC]
SCORED = {"lai_stand": "lai_stand", "vegc": "vegc", "fpc_tree": FPC[:7], "fpc_grass": FPC[7:]}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def stand(m: int, leg: str, y0=YD.Y0, y1=YD.Y1) -> pl.DataFrame | None:
    d = PP.table_dir(m, leg)
    if d is None or not os.path.exists(os.path.join(d, "annual.parquet")):
        return None
    a = pl.read_parquet(os.path.join(d, "annual.parquet")).filter(pl.col("Year").is_between(y0, y1))
    a = a.select("Cell", "Year", pl.col("lai_stand").cast(pl.Float64), pl.col("vegc").cast(pl.Float64))
    fp = os.path.join(d, "fpc_stand.parquet")
    if os.path.exists(fp):
        f = (pl.read_parquet(fp).filter(pl.col("Year").is_between(y0, y1) & (pl.col("pft") >= 1))
             .with_columns(pl.format("fpc{}", pl.col("pft")).alias("p"), pl.col("fpc_stand").cast(pl.Float64))
             .pivot(on="p", index=["Cell", "Year"], values="fpc_stand"))
        a = a.join(f.select("Cell", "Year", *FPC), on=["Cell", "Year"], how="left")
    else:
        a = a.with_columns([pl.lit(None, dtype=pl.Float64).alias(c) for c in FPC])
    return a.with_columns(pl.col("Cell").cast(pl.Int32), pl.col("Year").cast(pl.Int32),
                          pl.lit(m).alias("member"), pl.lit(leg).alias("leg"))


def stand_s0() -> pl.DataFrame:
    rows = []
    for m in PP.MEMBERS:
        h = stand(m, "hist", 2000, 2019)
        if h is not None:
            rows.append(h.group_by("Cell").agg([pl.col(q).mean().alias(f"s0_{q}") for q in SQ])
                        .with_columns(pl.lit(m).alias("member")))
    s0 = pl.concat(rows)
    hm = s0.filter(pl.col("member").is_in(YD.TRAIN_M)).group_by("Cell").agg(
        [pl.col(f"s0_{q}").mean().alias(f"hm_{q}") for q in SQ])
    return s0.join(hm, on="Cell").with_columns(
        [(pl.col(f"s0_{q}") - pl.col(f"hm_{q}")).alias(f"memoff_{q}") for q in SQ]).drop([f"hm_{q}" for q in SQ])


def build_rows(g: str, hold: int = 4) -> tuple[pl.DataFrame, pl.DataFrame]:
    """The training rows (runs YD.TRAIN_M x the other climate models' legs x YD.TRAIN_YEARS) and the test rows (runs
    YD.TRUTH and YD.SECOND x model g's three legs x every year) with every feature and anchor of the structure map
    (YD.QS) AND the stand map (SQ). Shared by stage_fit and scripts/bench_coupled_speed.py."""
    if hold != 4:  # leave-one-RUN-out for phase B: the unseen run is `hold`, every other run trains
        YD.TRUTH, YD.TRAIN_M = hold, tuple(m for m in PP.MEMBERS if m != hold)
    log(f"{g}: unseen run m{YD.TRUTH}, training runs {YD.TRAIN_M}")
    test_legs = [f"{g}_{s}" for s in ("ssp126", "ssp370", "ssp585")]
    train_legs = [lg for lg in A7.ALL_SLEGS if A7.gcm_of(lg) != g]
    t0 = time.time()
    ys = pl.concat([d for m in PP.MEMBERS for lg in A7.ALL_SLEGS if (d := YD.yearly(m, lg)) is not None])
    st = pl.concat([d for m in PP.MEMBERS for lg in A7.ALL_SLEGS if (d := stand(m, lg)) is not None])
    states = ys.with_columns(pl.col("Cell").cast(pl.Int32), pl.col("Year").cast(pl.Int32)).join(
        st, on=["Cell", "Year", "member", "leg"], how="left")
    clim = pl.concat([YD.window_climate(lg) for lg in A7.ALL_SLEGS]).with_columns(
        pl.col("Cell").cast(pl.Int32), pl.col("Year").cast(pl.Int32))
    log(f"{g}: states {states.height}, climate {clim.height} ({time.time() - t0:.0f}s)")
    QA = YD.QS + SQ
    base = states.filter(pl.col("member").is_in(YD.TRAIN_M) & pl.col("leg").is_in(train_legs))
    tot = base.group_by("Cell", "Year").agg([pl.col(q).sum().alias(f"S_{q}") for q in QA]
                                           + [pl.col(q).count().alias(f"N_{q}") for q in QA])
    per = base.group_by("Cell", "Year", "leg").agg([pl.col(q).sum().alias(f"s_{q}") for q in QA]
                                                  + [pl.col(q).count().alias(f"n_{q}") for q in QA])
    cb = clim.filter(pl.col("leg").is_in(train_legs))
    ctot = cb.group_by("Cell", "Year").agg([pl.col(c).sum().alias(f"S_{c}") for c in YD.CLIM]
                                          + [pl.len().alias("N_c")])
    rows = states.filter((pl.col("member").is_in(YD.TRAIN_M) & pl.col("leg").is_in(train_legs)
                          & pl.col("Year").is_in(YD.TRAIN_YEARS))
                         | (pl.col("member").is_in([YD.TRUTH, YD.SECOND]) & pl.col("leg").is_in(test_legs)))
    rows = (rows.join(tot, on=["Cell", "Year"], how="left").join(per, on=["Cell", "Year", "leg"], how="left")
            .join(clim, on=["Cell", "Year", "leg"], how="left")
            .join(cb.select("Cell", "Year", "leg", *[pl.col(c).alias(f"c_{c}") for c in YD.CLIM]),
                  on=["Cell", "Year", "leg"], how="left")
            .join(ctot, on=["Cell", "Year"], how="left"))
    ex = []
    for q in QA:  # leave-one-leg-out anchors, exactly as explore_panel_yearly_drift.stage_fit
        s_, n_ = pl.col(f"s_{q}").fill_null(0.0), pl.col(f"n_{q}").fill_null(0)
        den = pl.col(f"N_{q}") - n_
        ex.append(pl.when(den > 0).then((pl.col(f"S_{q}") - s_) / den).otherwise(None).alias(f"anc_{q}"))
    own = pl.col("c_tmean_ann").is_not_null()
    for c in YD.CLIM:
        ac = pl.when(own).then((pl.col(f"S_{c}") - pl.col(f"c_{c}")) / (pl.col("N_c") - 1)).otherwise(
            pl.col(f"S_{c}") / pl.col("N_c"))
        ex.append((pl.col(c) - ac).alias(f"dclim_{c}"))
    rows = rows.with_columns(ex)
    rows = rows.drop([x for x in rows.columns if x[:2] in ("S_", "N_", "s_", "n_", "c_") and x != "n_per_patch"])
    cells = PP.cells().select(pl.col("Cell").cast(pl.Int32), "lat", "lon", "soil_code")
    rows = (rows.join(YD.s0_table().with_columns(pl.col("Cell").cast(pl.Int32)), on=["Cell", "member"], how="left")
            .join(stand_s0().with_columns(pl.col("Cell").cast(pl.Int32)), on=["Cell", "member"], how="left")
            .join(cells, on="Cell", how="left"))
    rows = rows.sort("member", "leg", "Year", "Cell")
    # ADR 0352 sec. 0: training runs on TRAINING legs only -- before 2026-10-21 this also took run m5 (a training run
    # AND a test-side run) on the held-out model's legs; stand-map results before then carry that leak
    tr = rows.filter(pl.col("member").is_in(YD.TRAIN_M) & pl.col("leg").is_in(train_legs))
    te = rows.filter(pl.col("member").is_in([YD.TRUTH, YD.SECOND]) & pl.col("leg").is_in(test_legs))
    log(f"{g}: train rows {tr.height}, test rows {te.height} ({time.time() - t0:.0f}s)")
    return tr, te


def stand_feats() -> list[str]:
    return YD.feats() + [f"{k}_{q}" for q in SQ for k in ("anc", "s0", "memoff")]


EPS_COVER = 1e-3  # cover-mode "relative": floor before log, so a near-zero cover doesn't blow up the ratio


def stage_fit(a) -> None:
    """ADR 0339: --cover-mode picks how the 10 per-type covers (FPC) are fit; lai_stand/vegc are always additive
    (unchanged, so `additive` reproduces the pre-ADR-0339 files byte for byte). `relative`: the per-type target is a
    LOG-RATIO to its anchor (value/anchor - 1 in log space) instead of an absolute difference, so the loss weights a
    small cover's error the same as a large one's. `sumconstrained`: per-type covers are fit additively as before,
    then RESCALED so tree covers (1-7) sum to a separately fit tree-total and grass covers (8-10) to a grass-total
    (each total's own anchor is the sum of the per-type anchors, exact when the per-type null pattern agrees, which
    it does -- cover by type is all-or-nothing per run)."""
    import lightgbm as lgb

    g = a.g
    mode = a.cover_mode
    os.makedirs(OUT, exist_ok=True)
    tr, te = build_rows(g, a.hold)
    t0 = time.time()
    f = stand_feats()
    out = te.select("member", "leg", "Cell", "Year", pl.col("anc_n_per_patch"), *[pl.col(f"anc_{q}") for q in SQ])

    def fit_one(q: str, qmode: str) -> np.ndarray:
        t = tr.filter(pl.col(q).is_not_null() & pl.col(f"anc_{q}").is_not_null())
        anc_tr = t[f"anc_{q}"].to_numpy().astype(float)
        anc_te = te[f"anc_{q}"].to_numpy().astype(float)
        if qmode == "relative":
            y = np.log(np.maximum(t[q].to_numpy().astype(float), EPS_COVER)) - np.log(np.maximum(anc_tr, EPS_COVER))
        else:
            y = (t[q] - t[f"anc_{q}"]).to_numpy()
        mdl = lgb.train(A7.PARAMS, lgb.Dataset(t.select(f).to_numpy(), y), A7.ROUNDS)
        raw = mdl.predict(te.select(f).to_numpy())
        p = np.maximum(anc_te, EPS_COVER) * np.exp(raw) if qmode == "relative" else raw + anc_te
        log(f"{g} {q} [{qmode}]: {t.height} rows fitted ({time.time() - t0:.0f}s)")
        return np.maximum(p, 0.0)

    preds = {q: fit_one(q, mode if q in FPC else "additive") for q in SQ}

    if mode == "sumconstrained":
        for cols in (FPC[:7], FPC[7:]):  # tree (1-7), grass (8-10)
            t = tr.filter(pl.col(cols[0]).is_not_null())
            total_val = t.select(cols).sum_horizontal().to_numpy().astype(float)
            anc_total_tr = t.select([f"anc_{c}" for c in cols]).sum_horizontal().to_numpy().astype(float)
            anc_total_te = te.select([f"anc_{c}" for c in cols]).sum_horizontal().to_numpy().astype(float)
            mdl = lgb.train(A7.PARAMS, lgb.Dataset(t.select(f).to_numpy(), total_val - anc_total_tr), A7.ROUNDS)
            total_pred = np.maximum(mdl.predict(te.select(f).to_numpy()) + anc_total_te, 0.0)
            cur_sum = sum(preds[c] for c in cols)
            scale = np.where(cur_sum > EPS_COVER, total_pred / np.maximum(cur_sum, EPS_COVER), 1.0)
            for c in cols:
                preds[c] = preds[c] * scale
            log(f"{g} total({cols[0]}..{cols[-1]}): rescaled, total pred mean {total_pred.mean():.3f}"
                f" vs raw sum mean {cur_sum.mean():.3f}")

    for q in SQ:
        out = out.with_columns(pl.Series(q, preds[q]))
    out.write_parquet(os.path.join(OUT, pred_name(g, a.hold, mode)))
    log(f"{g}: wrote {out.height} predictions [{mode}]")


def pred_name(g: str, hold: int, mode: str = "additive") -> str:
    suf = "" if hold == 4 else f"_h{hold}"
    msuf = "" if mode == "additive" else f"_{mode}"
    return f"preds_{g}{suf}{msuf}.parquet"


def stage_arrays(a) -> None:
    """Phase B inputs: the daily model's stand_m<k>_<leg>.npy with years 2020-2100 (indices 1-81) replaced by the stand
    map's prediction for run k (fitted with run k unseen, --hold k) and the held-out leg's climate model unseen; index 0
    (end of 2019, the known start) stays the original's. Cells without a prediction keep the original's (counted)."""
    f2 = "/p/projects/open/Jamir/esm_land_emulator_data/f2"
    od = os.path.join(f2, a.stand_dir)
    os.makedirs(od, exist_ok=True)
    cells = pl.read_parquet(os.path.join(f2, "cells.parquet"))["Cell"].cast(pl.Int32)
    for dleg in a.legs.split(","):
        leg = dleg.removesuffix("_daily")
        g = A7.gcm_of(leg)
        for k in (1, 2, 3, 4):
            src = np.load(os.path.join(f2, f"stand_m{k}_{dleg}.npy"))
            if a.copy_only:  # harness: the original's stand through the same path
                np.save(os.path.join(od, f"stand_m{k}_{dleg}.npy"), src)
                continue
            P = pl.read_parquet(os.path.join(OUT, pred_name(g, k, a.cover_mode))).filter(
                (pl.col("member") == k) & (pl.col("leg") == leg))
            grid = pl.DataFrame({"Cell": np.repeat(cells.to_numpy(), 81),
                                 "Year": np.tile(np.arange(2020, 2101), len(cells)).astype(np.int32)})
            j = grid.join(P.select("Cell", "Year", *SQ), on=["Cell", "Year"], how="left")
            v = j.select(SQ).to_numpy().reshape(len(cells), 81, len(SQ))
            miss = ~np.isfinite(v)
            if a.only:  # attribution (ADR 0338): only these stand quantities from the map, the rest the original's
                keep = np.array([q not in a.only.split(",") for q in SQ])
                miss = miss | keep[None, None, :]
            new = src.copy()
            new[:, 1:, :] = np.where(miss, src[:, 1:, :], v).astype(np.float32)
            np.save(os.path.join(od, f"stand_m{k}_{dleg}.npy"), new)
            log(f"{dleg} m{k} [{a.only or 'all'}]: replaced {int((~miss).sum())} values, "
                f"kept the original's in {int(miss.sum())};"
                f" leaf area mean {src[:, 1:, 0].mean():.3f} -> {new[:, 1:, 0].mean():.3f}")


def scored(d: pl.DataFrame) -> pl.DataFrame:
    def one(v):  # a cover sum is missing (not 0) when the run carries no cover by type
        return pl.when(pl.col(v[0]).is_not_null()).then(pl.sum_horizontal(v)).otherwise(None) if isinstance(v, list) \
            else pl.col(v)
    return d.select("Cell", "Year", *[one(v).alias(k) for k, v in SCORED.items()])


def stage_score(a) -> None:
    w = PP.cells().select(pl.col("Cell").cast(pl.Int32), "lat").with_columns(
        np.cos(np.deg2rad(pl.col("lat"))).alias("w")).drop("lat")
    yr, cs = [], []
    for g in PP.GCMS:
        pf = os.path.join(OUT, pred_name(g, 4, a.cover_mode))
        if not os.path.exists(pf):
            log(f"skip {g}: no predictions")
            continue
        P = pl.read_parquet(pf)
        for s in ("ssp126", "ssp370", "ssp585"):
            leg = f"{g}_{s}"
            T = stand(YD.TRUTH, leg)
            if T is None:
                continue
            T = scored(T)
            X = P.filter((pl.col("member") == YD.TRUTH) & (pl.col("leg") == leg))
            R = {m: scored(stand(m, leg)) for m in YD.POOL}
            Om = scored(pl.concat([stand(m, leg) for m in YD.POOL]).group_by("Cell", "Year").agg(
                [pl.col(q).mean() for q in SQ]))
            cand = {"YA": scored(X), "oracle": Om, "second": scored(stand(YD.SECOND, leg)),
                    "anchor": scored(X.select("Cell", "Year", *[pl.col(f"anc_{q}").alias(q) for q in SQ]))}
            dense = X.select("Cell", "Year", (pl.col("anc_n_per_patch") >= YD.DENSE).alias("dense"))
            for q in SCORED:
                Tq = T.select("Cell", "Year", pl.col(q).alias("T")).filter(pl.col("T").is_not_null()
                                                                         & (pl.col("T").abs() > 1e-6))
                Tq = Tq.join(dense, on=["Cell", "Year"]).join(w, on="Cell")
                er = pl.concat([Tq.join(R[m].select("Cell", "Year", pl.col(q).alias("X")), on=["Cell", "Year"])
                                for m in YD.POOL]).with_columns(((pl.col("X") - pl.col("T")).abs() / pl.col("T"))
                                                                 .alias("e")).filter(pl.col("e").is_not_null())
                for grp, sel in (("dense", pl.col("dense")), ("all", pl.lit(True))):
                    ref = er.filter(sel).group_by("Year").agg(pl.col("e").median().alias("r50"),
                                                               pl.col("e").quantile(0.9).alias("r90"))
                    for nm, C in cand.items():
                        j = Tq.filter(sel).join(C.select("Cell", "Year", pl.col(q).alias("X")), on=["Cell", "Year"])
                        j = j.filter(pl.col("X").is_not_null())
                        if j.height == 0:
                            continue
                        e = j.with_columns(((pl.col("X") - pl.col("T")).abs() / pl.col("T")).alias("e")).group_by(
                            "Year").agg(pl.col("e").median().alias("x50"), pl.col("e").quantile(0.9).alias("x90"),
                                        ((pl.col("w") * pl.col("X")).sum() / (pl.col("w") * pl.col("T")).sum() - 1)
                                        .alias("tot"))
                        e = e.join(ref, on="Year").with_columns((pl.col("x50") / pl.col("r50")).alias("rho50"),
                                                                (pl.col("x90") / pl.col("r90")).alias("rho90"))
                        e = e.with_columns(pl.lit(leg).alias("leg"), pl.lit(s).alias("scen"), pl.lit(q).alias("q"),
                                           pl.lit(grp).alias("grp"), pl.lit(nm).alias("cand"))
                        yr.append(e)

                        def mean_in(y0, y1, col="rho50", e=e):
                            return e.filter(pl.col("Year").is_between(y0, y1))[col].mean()

                        cs.append(dict(leg=leg, scen=s, q=q, grp=grp, cand=nm, level50=mean_in(2071, 2100),
                                       level90=mean_in(2071, 2100, "rho90"), early=mean_in(2021, 2040),
                                       drift_mid=mean_in(2081, 2100) / mean_in(2051, 2070),
                                       drift_0330=mean_in(2081, 2100) / mean_in(2021, 2040),
                                       tot_late=mean_in(2071, 2100, "tot") * 100))
    Y = pl.concat(yr)
    msuf = "" if a.cover_mode == "additive" else f"_{a.cover_mode}"  # never overwrite the additive files
    Y.write_csv(os.path.join(OUT, f"stand_years{msuf}.csv"))
    C = pl.DataFrame(cs)
    C.write_csv(os.path.join(OUT, f"stand_cases{msuf}.csv"))
    pl.Config.set_tbl_rows(100)
    pl.Config.set_tbl_cols(14)
    pl.Config.set_tbl_width_chars(220)
    num = ["level50", "level90", "early", "drift_mid", "drift_0330", "tot_late"]
    for grp in ("dense", "all"):
        print(f"\n== {grp} cells: median over the cases (count of mid->late drift <= 1.2)")
        print(C.filter(pl.col("grp") == grp).group_by("cand", "q").agg(
            [pl.col(c).median().round(3) for c in num] + [(pl.col("drift_mid") <= 1.2).sum().alias("#mid<=1.2"),
                                                          pl.col("tot_late").abs().max().round(2).alias("|tot| max"),
                                                          pl.len().alias("cases")]).sort("q", "cand"))
    print("\n== YA, dense cells, per case")
    print(C.filter((pl.col("grp") == "dense") & (pl.col("cand") == "YA"))
          .select("leg", "q", *[pl.col(c).round(3) for c in num]).sort("q", "leg"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["fit", "score", "arrays"])
    ap.add_argument("--g", default="gfdl-esm4", choices=PP.GCMS)
    ap.add_argument("--hold", type=int, default=4, choices=[1, 2, 3, 4], help="the unseen run (phase B: each in turn)")
    ap.add_argument("--legs", default="mpi-esm1-2-hr_ssp585,ukesm1-0-ll_ssp370", help="arrays: daily-model leg names")
    ap.add_argument("--stand-dir", dest="stand_dir", default="stand_emul", help="arrays: subdir of the f2 data dir")
    ap.add_argument("--copy-only", dest="copy_only", action="store_true", help="arrays: harness, copy the original")
    ap.add_argument("--only", default="", help="arrays: comma list of stand quantities (SQ names) taken from the map")
    ap.add_argument("--cover-mode", dest="cover_mode", default="additive",
                    choices=["additive", "relative", "sumconstrained"],
                    help="ADR 0339: how the 10 per-type covers are fit (fit/arrays/score; lai_stand/vegc unaffected)")
    a = ap.parse_args()
    {"fit": stage_fit, "score": stage_score, "arrays": stage_arrays}[a.stage](a)
    log("=== DONE")


if __name__ == "__main__":
    main()
