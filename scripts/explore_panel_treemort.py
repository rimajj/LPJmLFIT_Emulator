#!/usr/bin/env python3
"""explore_panel_treemort.py -- ADR 0364: the PER-TREE mortality model. Each tree's leaf carbon relative to its
sapling threshold is learned as a continuous quantity and the original's own rule (die when it is below 1) is applied
to it; the bad-years counter kill and the chance hazard are learned per tree too; a cell's death rate is the mean of
its at-risk trees' death probabilities plus a cell-level rate of the deaths outside the probability (fire, isneg).

Per tree (inputs = what a virtual tree of y-1 carries + BMW's cell inputs of year y, ADR 0364 sec. 3):
  mu     E[ln r_y]                       sigma  E|ln r_y - mu| * sqrt(pi/2) on cross-fitted residuals (halves by cell)
  P_h    Phi(-mu / sigma)                P_c    P(hard kill with r >= 1) (binary)       hz   E[min(1, hazards)]
  P_k = 1 - (1 - P_h)(1 - P_c);  p_death = P_k + (1 - P_k) hz
Arms: BC (deployable inputs), BCN (+ the run's own tree-NPP statistics; a bound), BCE (+ the EMULATOR's own yearly
stand NPP and GPP statistics, ADR 0366; scripts/run_emulator_npp.py -> eval/treemort/enpp/enpp.parquet).
Stages:
  fit   --g G --arm A   train on runs m1 m2 m3 m5 m6 x the 27 legs of the other nine climate models (tree_pairs/)
                        -> eval/treemort/<g>_<arm>/{mu,muA,muB,sig,pc,hz}.txt
  pred  --g G --arm A   E1: run m4's own at-risk trees; E2: the emulator's virtual trees of y-1 (ADR 0363 AQ quantiles,
                        donor = run m4's 2019 roster, no-repeat draw) -> eval/treemort/pred_<g>_<arm>.parquet
                        (per leg, Cell, Year: rates E1_* / E2_*, calibration sums)
  score [--cells clean]  every ADR 0364 sec. 4-5 measure over the held-out models present -> stdout +
                        score_treemort.csv (clean: only the 240 cells the daily networks never saw, ADR 0366
                        sec. 2 -> score_treemort_clean.csv)
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_panel_a7 as A7  # noqa: E402
import explore_panel_popjoint as J  # noqa: E402
import explore_panel_popmap as PM  # noqa: E402
import explore_panel_prep as PP  # noqa: E402
import explore_panel_yearly_drift as YD  # noqa: E402

PAIRS = os.path.join(PP.OUT, "tree_pairs")
OUT = os.path.join(PP.OUT, "eval", "treemort")
TREE_F = ["Type1", "SLA1", "Wooddens1", "D95max1", "minwscal1", "Height1", "agb1", "Age1"]
VT_MAP = {"Type1": "Type", "SLA1": "SLA", "Wooddens1": "Wooddens", "D95max1": "D95max", "minwscal1": "minwscal",
          "Height1": "Height", "agb1": "agb", "Age1": "Age"}
CELL_F = ["lat", "lon", "soil_code", *YD.CLIM, *YD.DEP_W, *YD.BK_COLS]
LNR_FLOOR = -7.0  # a leafless tree (LAI 0: leaf carbon 0, ln r = -inf); far below any threshold
NP = int(os.environ.get("NPROC", "16"))
SCENS = ["ssp126", "ssp370", "ssp585"]
ENPP = os.path.join(OUT, "enpp", "enpp.parquet")
F2 = "/p/projects/reformit/Jamir/esm_land_emulator_data/f2"
ENPP_V = ["enpp", "egpp"]
ENPP_COLS = [f"{k}_{v}" for v in ENPP_V for k in ("n0", "n1", "nr0", "nr1", "nz0", "nz1")]
OWN_RUN = ("BCN", "BCE")  # arms whose cell inputs depend on the run (member)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def feats(arm: str) -> list[str]:
    return TREE_F + CELL_F + {"BCN": PM.NPP_COLS, "BCE": ENPP_COLS}.get(arm, [])


def enpp_anomaly(members: list[int], legs: list[str]) -> pl.DataFrame:
    """ADR 0366 sec. 1: the emulator's yearly stand NPP / GPP this (n0_) and last year (n1_), the ratio to the trailing
    30-year mean (nr) and the z-score against the 30 years before (nz; >= 15 years; the emulated 2000-2019 history in
    front) -- the construction of explore_panel_popmap.npp_anomaly."""
    d = (pl.scan_parquet(ENPP).filter(pl.col("member").is_in(members) & pl.col("leg").is_in(legs))
         .select("member", "leg", "Cell", "Year", *ENPP_V).collect().sort("member", "leg", "Cell", "Year"))
    g = ["member", "leg", "Cell"]
    ex = []
    for v in ENPP_V:
        mu = pl.col(v).shift(1).rolling_mean(window_size=30, min_samples=15).over(g)
        sd = pl.col(v).shift(1).rolling_std(window_size=30, min_samples=15).over(g)
        ex += [pl.col(v).alias(f"n0_{v}"),
               pl.when(mu.abs() > 1e-9).then(pl.col(v) / mu).otherwise(1.0).alias(f"nr0_{v}"),
               pl.when(sd > 1e-6 * (mu.abs() + 1.0)).then((pl.col(v) - mu) / sd).otherwise(0.0).alias(f"nz0_{v}")]
    d = d.with_columns(ex)
    d = d.with_columns([pl.col(f"{k}0_{v}").shift(1).over(g).alias(f"{k}1_{v}") for v in ENPP_V
                        for k in ("n", "nr", "nz")])
    d = d.filter(pl.col("Year") >= YD.Y0).select("Cell", "Year", "member", "leg", *ENPP_COLS)
    assert d.height == d.select("member", "leg", "Cell", "Year").n_unique(), "duplicate emulated-NPP keys"
    return d


def cell_inputs(legs: list[str], members: list[int] | None = None, arm: str = "BCN") -> pl.DataFrame:
    """(Cell, Year, leg) -> the 30-year climate, this / last year's weather z-scores, the bucket statistics,
    lat / lon / soil. members given: also (member) -> the run's own tree-NPP statistics (BCN)."""
    cells = PP.cells().select(pl.col("Cell").cast(pl.Int32), "lat", "lon", "soil_code")
    parts = []
    for lg in legs:
        d = (YD.window_climate(lg).join(YD.weather_anomaly(lg), on=["Cell", "Year", "leg"], how="left")
             .join(YD.bucket_anomaly(lg), on=["Cell", "Year", "leg"], how="left"))
        parts.append(d.with_columns(pl.col("Cell").cast(pl.Int32), pl.col("Year").cast(pl.Int32)))
    d = pl.concat(parts, how="diagonal").join(cells, on="Cell", how="left")
    if members is not None:
        if arm == "BCE":
            n = enpp_anomaly(members, legs)
        else:
            n = pl.concat([x for m in members for lg in legs if (x := PM.npp_anomaly(m, lg)) is not None])
        n = n.with_columns(pl.col("Cell").cast(pl.Int32), pl.col("Year").cast(pl.Int32),
                           pl.col("member").cast(pl.Int8))
        d = n.join(d, on=["Cell", "Year", "leg"], how="left")
    return d


def lnr_target(x: pl.Series) -> np.ndarray:
    v = x.to_numpy().astype(np.float64)
    return np.clip(np.where(np.isfinite(v), v, LNR_FLOOR), LNR_FLOOR, 7.0)


# ------------------------------------------------------------------------------------------------ fit
def stage_fit(a) -> None:
    import lightgbm as lgb

    t0 = time.time()
    od = os.path.join(OUT, f"{a.g}_{a.arm}")
    os.makedirs(od, exist_ok=True)
    legs = [lg for lg in A7.ALL_SLEGS if A7.gcm_of(lg) != a.g]
    P = pl.concat([pl.read_parquet(f) for m in YD.TRAIN_M for lg in legs
                   if os.path.exists(f := os.path.join(PAIRS, f"m{m}_{lg}.parquet"))])
    P = P.filter(pl.col("Year") > YD.Y0).with_columns(pl.col("Cell").cast(pl.Int32), pl.col("Year").cast(pl.Int32))
    nf = sum(os.path.exists(os.path.join(PAIRS, f"m{m}_{lg}.parquet")) for m in YD.TRAIN_M for lg in legs)
    log(f"{a.g} {a.arm}: {P.height} training trees from {nf} of {len(YD.TRAIN_M) * len(legs)} run-legs "
        f"({time.time() - t0:.0f}s)")
    C = cell_inputs(legs, list(YD.TRAIN_M) if a.arm in OWN_RUN else None, a.arm)
    on = ["Cell", "Year", "leg"] + (["member"] if a.arm in OWN_RUN else [])
    if a.arm in OWN_RUN:
        P = P.with_columns(pl.col("member").cast(pl.Int8))
    P = P.join(C, on=on, how="left").sort("member", "leg", "Year", "Cell", "Patch", "ID")
    f = feats(a.arm)
    assert P.select(CELL_F[3]).null_count().item() == 0, "cell inputs missing for some trees"
    if a.arm == "BCE":
        assert P.select(ENPP_COLS[0]).null_count().item() == 0, "emulated NPP missing for some trees"
    X = P.select(f).to_numpy().astype(np.float32)
    y = lnr_target(P["lnr"])
    half = (P["Cell"].to_numpy() % 2) == 0
    prm = dict(A7.PARAMS)

    def fit(Xs, ys, params=prm, name=None):
        m = lgb.train(params, lgb.Dataset(Xs, ys), A7.ROUNDS)
        if name:
            m.save_model(os.path.join(od, f"{name}.txt"))
        log(f"  {name or 'model'}: {len(ys)} trees ({time.time() - t0:.0f}s)")
        return m

    mA, mB = fit(X[half], y[half], name="muA"), fit(X[~half], y[~half], name="muB")
    oof = np.where(half, mB.predict(X), mA.predict(X))
    fit(X, np.abs(y - oof) * np.sqrt(np.pi / 2), name="sig")
    fit(X, y, name="mu")
    yc = (P["hard"].to_numpy() & (y >= 0)).astype(np.float64)
    fit(X, yc, dict(prm, objective="binary"), name="pc")
    fit(X, np.clip(P["hz"].fill_null(0.0).to_numpy().astype(np.float64), 0, 1), name="hz")
    with open(os.path.join(od, "features.txt"), "w") as fh:
        fh.write("\n".join(f))
    log(f"{a.g} {a.arm}: counter-kill share {yc.mean():.4f}, hard share {P['hard'].mean():.4f}, "
        f"lnr < 0 among hard {float((y[P['hard'].to_numpy()] < 0).mean()):.3f} ({time.time() - t0:.0f}s)")


# ------------------------------------------------------------------------------------------------ predict
_M: dict = {}


def _models(g: str, arm: str) -> dict:
    import lightgbm as lgb

    if not _M:
        od = os.path.join(OUT, f"{g}_{arm}")
        _M.update({k: lgb.Booster(model_file=os.path.join(od, f"{k}.txt")) for k in ("mu", "sig", "pc", "hz")})
        _M["f"] = open(os.path.join(od, "features.txt")).read().split("\n")
    return _M


def tree_probs(X: np.ndarray, M: dict, nthreads: int = 1) -> dict:
    from scipy.stats import norm

    mu = M["mu"].predict(X, num_threads=nthreads)
    sg = np.maximum(M["sig"].predict(X, num_threads=nthreads), 0.05)
    ph = norm.cdf(-mu / sg)
    pc = np.clip(M["pc"].predict(X, num_threads=nthreads), 0, 1)
    hz = np.clip(M["hz"].predict(X, num_threads=nthreads), 0, 1)
    pk = 1 - (1 - ph) * (1 - pc)
    return {"pk": pk, "hzp": (1 - pk) * hz, "pdeath": pk + (1 - pk) * hz, "ph": ph, "pc": pc}


def _agg(cell: np.ndarray, pr: dict, year: np.ndarray | int) -> pl.DataFrame:
    d = pl.DataFrame({"Cell": cell.astype(np.int32), "Year": np.broadcast_to(year, cell.shape).astype(np.int32),
                      **{k: pr[k] for k in ("pk", "hzp", "pdeath", "ph", "pc")}})
    return d.group_by("Cell", "Year").agg(pl.len().alias("n"), *[pl.col(k).mean() for k in
                                                                 ("pk", "hzp", "pdeath", "ph", "pc")])


def _e1_task(args):
    """E1, one leg: run m4's own trees alive and >= 5 m at the end of y-1 (y = 2021-2100)."""
    g, arm, leg, nth = args
    M = _models(g, arm)
    td = PP.table_dir(YD.TRUTH, leg)
    d = (pl.scan_parquet(os.path.join(td, "ind.parquet"))
         .filter(pl.col("Year").is_between(YD.Y0, YD.Y1 - 1) & (pl.col("Type") <= 6) & (pl.col("isdead") == 0)
                 & (pl.col("Height") >= 5.0))
         .select(pl.col("Cell").cast(pl.Int32), (pl.col("Year").cast(pl.Int32) + 1).alias("Year"),
                 *[pl.col(v).cast(pl.Float64).alias(k) for k, v in VT_MAP.items()]).collect())
    C = cell_inputs([leg], [YD.TRUTH] if arm in OWN_RUN else None, arm).drop("leg", "member", strict=False)
    d = d.join(C, on=["Cell", "Year"], how="left")
    out = []
    for y in range(YD.Y0 + 1, YD.Y1 + 1):
        x = d.filter(pl.col("Year") == y)
        if x.height:
            out.append(_agg(x["Cell"].to_numpy(), tree_probs(x.select(M["f"]).to_numpy().astype(np.float32), M,
                                                             nth), y))
    return pl.concat(out).with_columns(pl.lit(leg).alias("leg"))


_V: dict = {}


def _e2_inputs(g: str, arm: str) -> dict:
    if not _V:
        _V["P"] = J.preds(g)
        _V["don"] = J.by_cell(J.roster(YD.TRUTH, "hist", 2019))
        _V["C"] = {}
    return _V


def _e2_task(args):
    """E2, one (leg, y): the emulator's virtual trees of y-1 with year y's cell inputs."""
    g, arm, leg, y = args
    M, V = _models(g, arm), _e2_inputs(g, arm)
    if leg not in V["C"]:
        V["C"] = {leg: cell_inputs([leg], [YD.TRUTH] if arm in OWN_RUN else None, arm).drop("leg", "member",
                                                                                           strict=False)}
    C = V["C"][leg].filter(pl.col("Year") == y)
    P = V["P"].filter((pl.col("leg") == leg) & (pl.col("Year") == y - 1))
    cells, rows = [], []
    for r in P.iter_rows(named=True):
        don = V["don"].get(r["Cell"])
        if don is None:
            continue
        Q = {v: np.sort(np.array([r[f"AQ_{v}_{pn}"] for pn in PM.PN], float)) for v in J.QVARS}
        if not all(np.isfinite(q).all() for q in Q.values()):
            continue
        sh = np.nan_to_num(np.array([r[f"AQ_share_{t}"] for t in range(7)], float))
        vt = J.virtual_trees(int(round(J.NPATCH * max(r["X_n_per_patch"] or 0.0, 0.0))), sh, Q, don,
                             seed=r["Cell"] * 7919 + (y - 1))
        if not vt:
            continue
        cells.append(np.full(len(vt["Type"]), r["Cell"]))
        rows.append(np.column_stack([vt[VT_MAP[c]] for c in TREE_F]))
    if not rows:
        return None
    T = pl.DataFrame(np.vstack(rows), schema=TREE_F).with_columns(
        pl.Series("Cell", np.concatenate(cells)).cast(pl.Int32))
    T = T.join(C, on="Cell", how="left")
    return _agg(T["Cell"].to_numpy(), tree_probs(T.select(M["f"]).to_numpy().astype(np.float32), M), y).with_columns(
        pl.lit(leg).alias("leg"))


def stage_pred(a) -> None:
    assert J.DRAW == "unique", "E2 uses the no-repeat draw (ADR 0363 sec. 12): export VDRAW=unique"
    t0 = time.time()
    legs = [f"{a.g}_{s}" for s in SCENS]
    ctx = mp.get_context("spawn")
    with ctx.Pool(3) as pool:
        e1 = pl.concat(pool.map(_e1_task, [(a.g, a.arm, lg, max(1, NP // 3)) for lg in legs]))
    log(f"E1: {e1.height} cell-years ({time.time() - t0:.0f}s)")
    tasks = [(a.g, a.arm, lg, y) for lg in legs for y in range(YD.Y0 + 1, YD.Y1 + 1)]
    with ctx.Pool(NP) as pool:
        e2 = pl.concat([x for x in pool.imap_unordered(_e2_task, tasks, chunksize=4) if x is not None])
    log(f"E2: {e2.height} cell-years ({time.time() - t0:.0f}s)")
    ren = lambda d, p: d.rename({c: f"{p}_{c}" for c in d.columns if c not in ("leg", "Cell", "Year")})  # noqa: E731
    out = ren(e1, "E1").join(ren(e2, "E2"), on=["leg", "Cell", "Year"], how="full", coalesce=True)
    out.write_parquet(os.path.join(OUT, f"pred_{a.g}_{a.arm}.parquet"))
    log(f"wrote pred_{a.g}_{a.arm}.parquet ({time.time() - t0:.0f}s)")


# ------------------------------------------------------------------------------------------------ score
def stage_score(a) -> None:
    res = []
    parts = []
    for g in PP.GCMS:
        fm = os.path.join(PM.OUT, f"preds_{g}_mort3.parquet")
        if not os.path.exists(fm):
            continue
        P = pl.read_parquet(fm).filter(pl.col("member") == YD.TRUTH).drop("member")
        fn = os.path.join(PM.OUT, f"preds_{g}_mort3n.parquet")
        if os.path.exists(fn):
            P = P.join(pl.read_parquet(fn).filter(pl.col("member") == YD.TRUTH).select("leg", "Cell", "Year",
                                                                                      "^BMN_.*$"),
                       on=["leg", "Cell", "Year"], how="left")
        for arm in ("BC", "BCN", "BCE"):
            fp = os.path.join(OUT, f"pred_{g}_{arm}.parquet")
            if not os.path.exists(fp):
                continue
            x = pl.read_parquet(fp)
            oth = P.select("leg", "Cell", "Year", pl.col(f"{'BMN' if arm == 'BCN' else 'BMW'}_other_rate").alias("o"))
            x = x.join(oth, on=["leg", "Cell", "Year"], how="left")
            ex = []
            for e in ("E1", "E2"):
                ex += [(pl.col(f"{e}_pdeath") + pl.col("o")).alias(f"{arm}{e}_death3"),
                       pl.col(f"{e}_pk").alias(f"{arm}{e}_hard_rate"),
                       pl.col(f"{e}_hzp").alias(f"{arm}{e}_hazard_rate")]
            P = P.join(x.select("leg", "Cell", "Year", *ex), on=["leg", "Cell", "Year"], how="left")
        for s in SCENS:
            leg = f"{g}_{s}"
            d = P.filter(pl.col("leg") == leg)
            for m in (1, 2, 3, 4, 5):
                t = PM.yearly3(m, leg, [*PM.MORT3, "n_risk", "n_hard", "sum_hz"])
                d = d.join(t.drop("member", "leg").rename({c: f"T{m}_{c}" for c in t.columns
                                                          if c not in ("Cell", "Year", "member", "leg")}),
                           on=["Cell", "Year"], how="left")
            parts.append(d.with_columns(pl.lit(leg).alias("case")))
    M = pl.concat(parts, how="diagonal").filter(pl.col("Year") > YD.Y0)
    if a.cells == "clean":  # ADR 0366 sec. 2: only the cells the daily networks never saw
        ho = pl.read_parquet(os.path.join(F2, "cells.parquet")).filter(pl.col("heldout"))["Cell"]
        M = M.filter(pl.col("Cell").is_in(ho.cast(M["Cell"].dtype).implode()))
        print(f"clean cells: {M['Cell'].n_unique()} cells")
    w = PP.cells().select(pl.col("Cell").cast(M["Cell"].dtype), np.cos(np.deg2rad(pl.col("lat"))).alias("w"))
    M = M.join(w, on="Cell")
    arms = [x for x in ("BCE1", "BCE2", "BCNE1", "BCNE2", "BCEE1", "BCEE2", "BM", "BMW", "BMN", "T5")
            if f"{x}_death3" in M.columns]
    dense = pl.col("anc_n_per_patch") >= J.DENSE
    for q in PM.MORT3[:3]:
        for arm in arms:
            xs = f"{arm}_{q}"
            if xs not in M.columns:
                continue
            E = M.filter(dense & pl.col(f"T4_{q}").is_not_null() & pl.col(xs).is_not_null()).with_columns(
                (pl.col(xs) - pl.col(f"T4_{q}")).abs().alias("eX"),
                *[(pl.col(f"T{m}_{q}") - pl.col(f"T4_{q}")).abs().alias(f"e{m}") for m in (1, 2, 3)])
            rr = J.ratio_rows(E.drop_nulls(["eX", "e1", "e2", "e3"]), "eX", ["e1", "e2", "e3"], "dense")
            res.append(J.case_summary(rr, f"{q} yearly {arm} dense", 1.5, None))
            L = E.filter(pl.col("Year") >= 2071).group_by("case", "Cell").agg(
                *[pl.col(c).mean() for c in (xs, f"T4_{q}", f"T1_{q}", f"T2_{q}", f"T3_{q}")])
            L = L.with_columns((pl.col(xs) - pl.col(f"T4_{q}")).abs().alias("eX"),
                               *[(pl.col(f"T{m}_{q}") - pl.col(f"T4_{q}")).abs().alias(f"e{m}") for m in (1, 2, 3)],
                               pl.lit(2085).alias("Year"))
            rr = J.ratio_rows(L.drop_nulls(["eX", "e1", "e2", "e3"]), "eX", ["e1", "e2", "e3"], "dense")
            res.append(J.case_summary(rr, f"{q} 30-yr mean 2071-2100 {arm} dense", 1.2, None))
            if q == "death3":
                tot = E.group_by("case", "Year").agg((pl.col("w") * pl.col(xs) * pl.col("T4_n_risk")).sum().alias("X"),
                                                     (pl.col("w") * pl.col("T4_death3") * pl.col("T4_n_risk")).sum()
                                                     .alias("T"))
                rel = tot.with_columns((pl.col("X") / pl.col("T") - 1).alias("r")).group_by("case").agg(
                    pl.col("r").mean())
                res.append({"what": f"total deaths {arm} dense (signed, mean over years)", "cases": rel.height,
                            "typ_median": float(rel["r"].median()), "worst_median": float(rel["r"].abs().max()),
                            "n_typ_ok": int((rel["r"].abs() <= 0.05).sum())})
    # die-off capture on ADR 0350's shared tree-count events
    ev = pl.read_parquet(os.path.join(PP.OUT, "eval", "extreme_legacy_events.parquet")).filter(
        (pl.col("q") == "tree_count") & pl.col("shared")).select(
        "case", pl.col("Cell").cast(M["Cell"].dtype), pl.col("year").cast(M["Year"].dtype))
    ev = ev.filter(pl.col("case").is_in(M["case"].unique().implode()))
    for q in ("death3", "hard_rate"):
        cols = {k: f"{k}_{q}" for k in arms if f"{k}_{q}" in M.columns} | {f"T{m}": f"T{m}_{q}" for m in (1, 2, 3, 4)}
        tl = M.select("case", "Cell", "Year", *cols.values())
        at = ev.join(tl, left_on=["case", "Cell", "year"], right_on=["case", "Cell", "Year"], how="left")
        base = (ev.join(tl.rename({"Year": "y"}), on=["case", "Cell"], how="left")
                .filter((pl.col("y") >= pl.col("year") - 5) & (pl.col("y") <= pl.col("year") - 1))
                .group_by("case", "Cell", "year").agg(*[pl.col(c).mean().alias(f"b_{c}") for c in cols.values()]))
        jn = at.join(base, on=["case", "Cell", "year"], how="inner")
        dT = (jn[cols["T4"]] - jn[f"b_{cols['T4']}"]).to_numpy()
        for k, c in cols.items():
            if k == "T4":
                continue
            dX = (jn[c] - jn[f"b_{c}"]).to_numpy()
            ok = np.isfinite(dX) & np.isfinite(dT)
            res.append({"what": f"die-off capture {q} {k} ({int(ok.sum())} events)", "cases": int(ok.sum()),
                        "typ_median": float(dX[ok].sum() / dT[ok].sum()), "worst_median": None, "n_typ_ok": None})
    # calibration (E1): predicted / observed hard kills and hazard sums, per case
    for arm in ("BC", "BCN", "BCE"):
        if f"{arm}E1_hard_rate" not in M.columns:
            continue
        c = M.filter(pl.col(f"{arm}E1_hard_rate").is_not_null()).group_by("case").agg(
            (pl.col(f"{arm}E1_hard_rate") * pl.col("T4_n_risk")).sum().alias("ph"),
            pl.col("T4_n_hard").sum().alias("oh"),
            (pl.col(f"{arm}E1_hazard_rate") * pl.col("T4_n_risk")).sum().alias("pz"), pl.col("T4_sum_hz").sum()
            .alias("oz"))
        c = c.with_columns((pl.col("ph") / pl.col("oh")).alias("rh"), (pl.col("pz") / pl.col("oz")).alias("rz"))
        for k, lab in (("rh", "hard kills"), ("rz", "hazard sum")):
            res.append({"what": f"calibration E1 {arm} {lab}: predicted / observed", "cases": c.height,
                        "typ_median": float(c[k].median()), "worst_median": float((c[k] - 1).abs().max()),
                        "n_typ_ok": int(((c[k] - 1).abs() <= 0.1).sum())})
    # ADR 0366 sec. 4 diagnostic: does the emulated NPP anomaly follow the original's tree-NPP anomaly?
    if "BCEE1_death3" in M.columns:
        dn = M.filter(dense).select("case", "Cell", "Year").unique()
        for g in PP.GCMS:
            legs = [f"{g}_{s}" for s in SCENS]
            if not os.path.exists(os.path.join(OUT, f"pred_{g}_BCE.parquet")):
                continue
            E = enpp_anomaly([YD.TRUTH], legs).select("leg", "Cell", "Year", "nz0_enpp")
            On = pl.concat([x for lg in legs if (x := PM.npp_anomaly(YD.TRUTH, lg)) is not None]).select(
                "leg", "Cell", "Year", pl.col(f"nz0_{PM.NPP_V[0]}").alias("nz_orig"))
            J2 = (E.join(On, on=["leg", "Cell", "Year"]).with_columns(pl.col("Cell").cast(M["Cell"].dtype),
                                                                    pl.col("Year").cast(M["Year"].dtype))
                  .join(dn, left_on=["leg", "Cell", "Year"], right_on=["case", "Cell", "Year"]))
            for lg in legs:
                x = J2.filter(pl.col("leg") == lg)
                r = (float(np.corrcoef(x["nz0_enpp"].to_numpy(), x["nz_orig"].to_numpy())[0, 1])
                     if x.height > 2 else None)
                xe = x.join(ev.rename({"year": "Year", "case": "leg"}), on=["leg", "Cell", "Year"])
                res.append({"what": f"NPP z: emulated vs original, corr over dense cell-years {lg} (events: mean "
                                    f"emulated / original z)", "cases": x.height, "typ_median": r,
                            "worst_median": float(xe["nz0_enpp"].mean()) if xe.height else None,
                            "n_typ_ok": None, "orig_event_z": float(xe["nz_orig"].mean()) if xe.height else None})
    R = pl.DataFrame(res)
    R.write_csv(os.path.join(OUT, f"score_treemort{'_clean' if a.cells == 'clean' else ''}.csv"))
    with pl.Config(tbl_rows=-1, tbl_width_chars=200, fmt_str_lengths=80):
        print(R)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["fit", "pred", "score"])
    ap.add_argument("--g", default="gfdl-esm4", choices=PP.GCMS)
    ap.add_argument("--arm", default="BC", choices=["BC", "BCN", "BCE"])
    ap.add_argument("--cells", default="all", choices=["all", "clean"])
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    {"fit": stage_fit, "pred": stage_pred, "score": stage_score}[a.stage](a)
    log("=== DONE")


if __name__ == "__main__":
    main()
