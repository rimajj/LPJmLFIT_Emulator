#!/usr/bin/env python3
"""explore_glob_tolerance.py -- LINE X, ADR 0317's "as close as a second run" measure on the GLOBAL venue (ADR 0315).

The panel venue (explore_tolerance_measure.py) held out a whole climate MODEL. This venue holds out the SCENARIO
(ssp370) and the RUN (member 8) of one climate model (GFDL-ESM4), cells seen in training -- the deployment setting of
ADR 0316 sec. 5. Same measure, imported from explore_tolerance_measure.py:
  per cell and quantity e_X = |X - T| / |T|, T = member 8 ssp370 2071-2100;
  rho_k = P_k[e_X] / P_k[e_R], k = 50 / 90, e_R pooled over the second runs R in POOL (Feb-build members 2,3,4,6,7;
  a candidate that IS a member is scored against the pool without itself);
  response d = X(ssp370 2071-2100) - X(historical 1985-2014), absolute error |dX - dT|;
  subgroups: the truth's density stratum and three latitude zones; area totals |X/T - 1| beside a second run's.
Cells: the 5 809 dev cells that bear trees in member 8 (either window), as in explore_glob_eval.score.

Candidates:
  rep7      member 7 scored against {2,3,4,6}                      -- harness: a second run.
  mean5     mean of members 2,3,4,6,7 at ssp370                    -- ORACLE (sees the held-out scenario).
  lookup    mean of the training runs 2,3,4,6 at ssp245 (response baseline: their historical mean) -- the null.
  A7r_t4 / A7r_t5   ADR 0316 sec. 5's anchored direct map trained on runs 2,3,4,6 / 2,3,4,6,7, LightGBM seeds 1-5;
            response = its own ssp370 prediction minus its own historical prediction (both legs predicted, as on the
            panel). rho is computed per seed; the mean and the spread over seeds are reported.
  A7rcb_t4  the climate-blind twin (runs 2,3,4,6).

WRITTEN BEFORE THE RUN (ADR 0184), 2026-10-09:
  rep7     rho_50 and rho_90 in 0.90-1.10 on every quantity, levels and response (it is a draw from the pool).
  mean5    Gaussian argument sqrt((1 + 1/5) / 2) = 0.77 on levels; expect 0.65-0.90.
  lookup   rho_50 > 1.2 on tree count and biomass per tree (ssp245 is a cooler climate than ssp370).
  A7r_t4   EASIER than the panel (same climate model, only the scenario is new), so better than the panel's
           tree count 1.43 / 2.23 and biomass per tree 1.63 / 1.76 (rho_50 / rho_90). Expected: tree count and biomass
           per tree rho_50 in 1.0-1.4, traits below 1. Falsifier of "the global venue is easier": tree-count
           rho_50 >= 1.43.
  A7r_t5   rho on tree count and biomass per tree lower than A7r_t4 by 0.00-0.10 (one more run; the global pass rate
           moved only +0.003). A drop > 0.10 would say the ratio measure is far more sensitive to data than the pass
           rate is.
  A7rcb_t4 worse than A7r_t4 on the response ratio.

Output: billing_global/eval/tolerance_glob.csv (+ _groups.csv). ~10 min on 16 cores (SLURM).
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_glob_a7 as A7  # noqa: E402
import explore_glob_a7r as R7  # noqa: E402
import explore_glob_eval as ev  # noqa: E402
import explore_tolerance_measure as tm  # noqa: E402

PANEL = ev.PANEL
POOL = (2, 3, 4, 6, 7)
TRAIN_SETS = {"t4": (2, 3, 4, 6), "t5": (2, 3, 4, 6, 7)}
OUT = os.path.join(ev.EVAL, "tolerance_glob.csv")


def mean_of(members, scen: str) -> pl.DataFrame:
    return pl.concat([ev.lev(ev.mname(scen, m)) for m in members]).group_by("Cell").agg(
        [pl.col(q).mean() for q in PANEL])


def measure(name, Xw, Xh, T, Th, R, Rh, pool, cc, seed=0):
    eX = tm.rel_err(Xw, T, cc)
    eR = pl.concat([tm.rel_err(R[m], T, cc) for m in pool])
    rX = tm.resp_err(Xw, Xh, T, Th, cc)
    rR = pl.concat([tm.resp_err(R[m], Rh[m], T, Th, cc) for m in pool])
    lvl, rsp = tm.ratios(eX, eR, []), tm.ratios(rX, rR, [])
    dn, db = tm.totals(Xw, T, cc)
    rt = [tm.totals(R[m], T, cc) for m in pool]
    rows, sub = [], []
    for r in lvl.iter_rows(named=True):
        rp = rsp.filter(pl.col("q") == r["q"]).row(0, named=True)
        rows.append(dict(cand=name, seed=seed, q=r["q"], n=r["n"], x50=r["x50"], r50=r["r50"], rho50=r["rho50"],
                         rho90=r["rho90"], resp_rho50=rp["rho50"], resp_rho90=rp["rho90"], tot_stems=dn,
                         tot_biomass=db, rep_tot_stems=float(np.mean([abs(a) for a, _ in rt])),
                         rep_tot_biomass=float(np.mean([abs(b) for _, b in rt]))))
    for by in ("stratum", "zone"):
        for r in tm.ratios(eX, eR, [by]).iter_rows(named=True):
            sub.append(dict(cand=name, seed=seed, q=r["q"], by=by, group=str(r[by]), n=r["n"], rho50=r["rho50"],
                            rho90=r["rho90"]))
    return rows, sub


def main():
    t0 = time.time()
    cells = ev.dev_cells()
    T, Th = ev.lev(ev.mname("ssp370", ev.TRUTH)), ev.lev(ev.mname("historical", ev.TRUTH))
    tb = (T.filter(pl.col("n_per_patch") > 0).select("Cell")
          .vstack(Th.filter(pl.col("n_per_patch") > 0).select("Cell")).unique())
    dens = T.select("Cell", pl.col("n_per_patch").cut(tm.STRATA, labels=["<2", "2-5", "5-10", "10-20", ">20"])
                    .alias("stratum"))
    cc = (cells.join(tb, on="Cell").join(dens, on="Cell", how="left")
          .with_columns(np.cos(np.deg2rad(pl.col("lat"))).alias("area"),
                        pl.when(pl.col("lat").abs() < 23.5).then(pl.lit("tropics")).when(pl.col("lat").abs() < 50)
                        .then(pl.lit("mid")).otherwise(pl.lit("high")).alias("zone")))
    ev.log(f"scored cells: {cc.height}")
    R = {m: ev.lev(ev.mname("ssp370", m)) for m in POOL}
    Rh = {m: ev.lev(ev.mname("historical", m)) for m in POOL}
    rows, sub = [], []

    def add(*a, **k):
        r, s = measure(*a, **k)
        rows.extend(r)
        sub.extend(s)

    add("rep7", R[7], Rh[7], T, Th, R, Rh, (2, 3, 4, 6), cc)
    add("mean5", mean_of(POOL, "ssp370"), mean_of(POOL, "historical"), T, Th, R, Rh, POOL, cc)
    add("lookup", mean_of((2, 3, 4, 6), "ssp245"), mean_of((2, 3, 4, 6), "historical"), T, Th, R, Rh, POOL, cc)
    for tag, train in TRAIN_SETS.items():
        R7.TRAIN = train
        df = R7.prepare(cells)
        tr, te = df.filter(pl.col("seed").is_in(list(train))), df.filter(pl.col("seed") == ev.TRUTH)
        for sd in range(1, 6):
            A7.PARAMS["seed"] = sd
            for v in ("A7r", "A7rcb") if tag == "t4" else ("A7r",):
                p = R7.fit_seen(tr, te, v)
                pw = p.filter(pl.col("scen") == "ssp370").drop("scen")
                ph = p.filter(pl.col("scen") == "historical").drop("scen")
                add(f"{v}_{tag}", pw, ph, T, Th, R, Rh, POOL, cc, seed=sd)
            ev.log(f"{tag} seed {sd} done ({time.time() - t0:.0f}s)")
    df, sb = pl.DataFrame(rows), pl.DataFrame(sub)
    df.write_csv(OUT)
    sb.write_csv(OUT.replace(".csv", "_groups.csv"))
    pl.Config.set_tbl_rows(200)
    pl.Config.set_tbl_cols(20)
    print("\n== per candidate x quantity: mean over LightGBM seeds (sd beside rho50) ==")
    print(df.group_by(["cand", "q"]).agg(pl.col("r50").mean().alias("2nd-run err"),
                                          pl.col("rho50").mean(), pl.col("rho50").std().alias("rho50_sd"),
                                          *[pl.col(c).mean() for c in ("rho90", "resp_rho50", "resp_rho90")])
          .sort(["cand", "q"]))
    print("\n== area totals |X/T-1| vs a second run's ==")
    t = df.filter(pl.col("q") == "n_per_patch")
    print(t.group_by("cand").agg(pl.col("tot_stems").abs().mean().alias("stems"),
                                 pl.col("rep_tot_stems").mean().alias("2nd-run stems"),
                                 pl.col("tot_biomass").abs().mean().alias("biomass"),
                                 pl.col("rep_tot_biomass").mean().alias("2nd-run biomass")).sort("cand"))
    print("\n== subgroups (n >= 30 cells), mean over seeds ==")
    print(sb.filter(pl.col("n") >= 30).group_by(["cand", "by", "group", "q"])
          .agg(pl.col("rho50").mean(), pl.col("rho90").mean(), pl.col("n").first())
          .filter(pl.col("q").is_in(["n_per_patch", "agb_per_stem"]) & pl.col("cand").is_in(["A7r_t4", "A7r_t5",
                                                                                                  "rep7"]))
          .sort(["q", "by", "group", "cand"]))
    ev.log(f"wrote {OUT} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
