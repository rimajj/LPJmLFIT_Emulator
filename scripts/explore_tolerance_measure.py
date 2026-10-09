#!/usr/bin/env python3
"""explore_tolerance_measure.py -- LINE X, a measure of "as close as a second run of the original" (ADR 0317).

Owner, 2026-10-09: "the goal is to be as close as a second run of the original model. it is even fine if it is worse
... I would be happy if the emulator is not more than 10% worse than a second model run of the original" (then: "maybe
the threshold should be even 20%??").

THE MEASURE (read-only, panel venue of ADR 0316, held-out climate model HG, truth = m4):
  per cell c and quantity q:   e_X(c) = |X(c) - T(c)| / |T(c)|          (X = candidate, T = the unseen run m4)
  reference = a second run:    e_R(c) for R in the replica pool {m1, m2, m3} (pooled; a candidate that IS a member is
                               scored against the pool without itself)
  ERROR RATIO at a centile k:  rho_k = P_k[e_X over cells] / P_k[e_R over cells],  k = 50 (typical cell) and 90 (the
                               bad cells -- the "all cells" clause lives here). rho = 1.0 is exactly a second run.
  The same ratio on the climate RESPONSE: d = X(scenario) - X(ctl_obs), both 2071-2100, absolute error |dX - dT|.
  Subgroups: the truth's density stratum and three latitude zones; the WORST subgroup ratio is reported.
  Area totals: sum(area * n_per_patch) and sum(area * n * agb_per_stem), |X/T - 1| next to the replicas' own.

WHAT EACH CANDIDATE MUST RETURN (written before the run, ADR 0184):
  m3 (a second run, harness check)   rho_50 and rho_90 in 0.90-1.10 on every quantity (it is a member of the population
                                     the reference is drawn from; scored against {m1, m2} only).
  mean3 (mean of m1-m3, same leg -- an ORACLE: it sees the held-out climate model's own runs)
                                     rho below 1: Gaussian argument sqrt((1 + 1/3) / 2) = 0.82; expect 0.70-0.92.
                                     This is the best a deterministic emulator can do with 3 training runs.
  lookup (mean of m1-m3 x the same scenario of the 4 OTHER climate models)   expected rho_50 > 1.2 on most quantities.
  A7r (ADR 0316, seed 1)             no prediction; ADR 0316 sec. 5 reached ~0.9 of a second run's PASS RATE in range.
  A7rcb (its climate-blind twin)     expected worse than A7r on the response ratio.

RESULT (2026-10-09, login node, ~1 min; ADR 0317): harness passes -- m3 0.88-1.18 (sd 0.05), mean3 0.82 on every
quantity. A7r: traits 0.66-0.94 (better than a second run), stems 1.43 / 2.23 (centile 50 / 90), biomass per stem
1.63 / 1.76; area totals 1.6 % / 3.2 % off vs a second run's 0.3 % / 0.8 %. Lookup null: stems 1.52, biomass 1.66.
"""

from __future__ import annotations

import os

import numpy as np
import polars as pl

D = "/p/projects/open/Jamir/esm_land_emulator_data/xpanel"
PANEL = ["n_per_patch", "agb_per_stem", "SLA_q50", "Wooddens_q50", "D95max_q50", "minwscal_q50"]
MODELS = ["gfdl-esm4", "ipsl-cm6a-lr", "mpi-esm1-2-hr", "mri-esm2-0", "ukesm1-0-ll"]
SCENS = ["ssp126", "ssp370", "ssp585"]
POOL, TRUTH = (1, 2, 3), 4
STRATA = [2.0, 5.0, 10.0, 20.0]
OUT = os.path.join(D, "eval", "tolerance_measure.csv")


def lev(m: int, leg: str, win: str = "w2071") -> pl.DataFrame | None:
    p = os.path.join(D, "levels", f"m{m}_{leg}_{win}.parquet")
    return pl.read_parquet(p).select(["Cell"] + PANEL) if os.path.exists(p) else None


def mean_of(frames: list[pl.DataFrame]) -> pl.DataFrame:
    return pl.concat(frames).group_by("Cell").agg([pl.col(q).mean() for q in PANEL])


def long(d: pl.DataFrame, name: str) -> pl.DataFrame:
    return d.unpivot(index="Cell", on=PANEL, variable_name="q", value_name=name)


def rel_err(X: pl.DataFrame, T: pl.DataFrame, cells: pl.DataFrame) -> pl.DataFrame:
    j = long(T, "T").join(long(X, "X"), on=["Cell", "q"], how="left").join(cells, on="Cell")
    j = j.filter(pl.col("T").is_not_null() & (pl.col("T").abs() > 0))
    return j.with_columns(((pl.col("X") - pl.col("T")).abs() / pl.col("T").abs()).fill_null(np.inf).alias("e"))


def resp_err(Xs, Xc, Ts, Tc, cells) -> pl.DataFrame:
    dX = long(Xs, "Xs").join(long(Xc, "Xc"), on=["Cell", "q"])
    dT = long(Ts, "Ts").join(long(Tc, "Tc"), on=["Cell", "q"])
    j = dT.join(dX, on=["Cell", "q"], how="left").join(cells, on="Cell")
    j = j.filter(pl.col("Ts").is_not_null() & pl.col("Tc").is_not_null())
    return j.with_columns(((pl.col("Xs") - pl.col("Xc")) - (pl.col("Ts") - pl.col("Tc"))).abs()
                          .fill_null(np.inf).alias("e"))


def ratios(eX: pl.DataFrame, eR: pl.DataFrame, by: list[str]) -> pl.DataFrame:
    a = eX.group_by(["q", *by]).agg(pl.col("e").quantile(0.5).alias("x50"), pl.col("e").quantile(0.9).alias("x90"),
                                     pl.len().alias("n"))
    b = eR.group_by(["q", *by]).agg(pl.col("e").quantile(0.5).alias("r50"), pl.col("e").quantile(0.9).alias("r90"))
    return a.join(b, on=["q", *by]).with_columns((pl.col("x50") / pl.col("r50")).alias("rho50"),
                                                 (pl.col("x90") / pl.col("r90")).alias("rho90"))


def totals(X: pl.DataFrame, T: pl.DataFrame, cells: pl.DataFrame) -> tuple[float, float]:
    def tot(d):
        d = d.join(cells.select("Cell", "area"), on="Cell").fill_null(0.0)
        return (float((d["area"] * d["n_per_patch"]).sum()),
                float((d["area"] * d["n_per_patch"] * d["agb_per_stem"]).sum()))
    (nx, bx), (nt, bt) = tot(X), tot(T)
    return nx / nt - 1, bx / bt - 1


def main():
    cells = pl.read_parquet(os.path.join(D, "cells.parquet")).select("Cell", "lat")
    cells = cells.with_columns(
        np.cos(np.deg2rad(pl.col("lat"))).alias("area"),
        pl.when(pl.col("lat").abs() < 23.5).then(pl.lit("tropics")).when(pl.col("lat").abs() < 50)
        .then(pl.lit("mid")).otherwise(pl.lit("high")).alias("zone"))
    rows, sub = [], []
    for g in MODELS:
        preds = {a: pl.read_parquet(os.path.join(D, "eval", "preds_seen", "s1", f"HG_{g}_{a}.parquet"))
                 for a in ("A7r", "A7rcb")}
        for s in SCENS:
            leg = f"{g}_{s}"
            T, Tc = lev(TRUTH, leg), lev(TRUTH, "ctl_obs")
            R = {m: lev(m, leg) for m in POOL}
            if T is None or any(v is None for v in R.values()):
                print(f"skip {leg}: truth or a replica missing")
                continue
            Rc = {m: lev(m, "ctl_obs") for m in POOL}
            dens = T.select("Cell", pl.col("n_per_patch").cut(STRATA, labels=["<2", "2-5", "5-10", "10-20", ">20"])
                            .alias("stratum"))
            treec = T.filter(pl.col("n_per_patch") > 0).select("Cell")
            cc = cells.join(treec, on="Cell").join(dens, on="Cell")
            other = [f"{h}_{s}" for h in MODELS if h != g]
            lk = mean_of([x for m in POOL for h in other if (x := lev(m, h)) is not None])
            lk_c = mean_of(list(Rc.values()))
            cand = {"A7r": (preds["A7r"].filter(pl.col("leg") == leg).drop("leg"),
                            preds["A7r"].filter(pl.col("leg") == "ctl_obs").drop("leg"), POOL),
                    "A7rcb": (preds["A7rcb"].filter(pl.col("leg") == leg).drop("leg"),
                              preds["A7rcb"].filter(pl.col("leg") == "ctl_obs").drop("leg"), POOL),
                    "lookup": (lk, lk_c, POOL),
                    "mean3": (mean_of(list(R.values())), lk_c, POOL),
                    "m3": (R[3], Rc[3], (1, 2))}
            for name, (Xw, Xc, pool) in cand.items():
                eX = rel_err(Xw, T, cc)
                eR = pl.concat([rel_err(R[m], T, cc) for m in pool])
                rX = resp_err(Xw, Xc, T, Tc, cc)
                rR = pl.concat([resp_err(R[m], Rc[m], T, Tc, cc) for m in pool])
                lvl, rsp = ratios(eX, eR, []), ratios(rX, rR, [])
                dn, db = totals(Xw, T, cc)
                rt = [totals(R[m], T, cc) for m in pool]
                for r in lvl.iter_rows(named=True):
                    rp = rsp.filter(pl.col("q") == r["q"]).row(0, named=True)
                    rows.append(dict(model=g, scen=s, cand=name, q=r["q"], n=r["n"], x50=r["x50"], r50=r["r50"],
                                     rho50=r["rho50"], rho90=r["rho90"], resp_rho50=rp["rho50"],
                                     resp_rho90=rp["rho90"], tot_stems=dn, tot_biomass=db,
                                     rep_tot_stems=float(np.mean([abs(a) for a, _ in rt])),
                                     rep_tot_biomass=float(np.mean([abs(b) for _, b in rt]))))
                for by in ("stratum", "zone"):
                    for r in ratios(eX, eR, [by]).iter_rows(named=True):
                        sub.append(dict(model=g, scen=s, cand=name, q=r["q"], by=by, group=str(r[by]), n=r["n"],
                                        rho50=r["rho50"], rho90=r["rho90"]))
    df, sb = pl.DataFrame(rows), pl.DataFrame(sub)
    df.write_csv(OUT)
    sb.write_csv(OUT.replace(".csv", "_groups.csv"))
    pl.Config.set_tbl_rows(200)
    pl.Config.set_tbl_cols(20)
    print("\n== median over the 13-15 test cases, per candidate x quantity ==")
    print(df.group_by(["cand", "q"]).agg(pl.len().alias("cases"), pl.col("r50").median().alias("2nd-run err"),
                                          *[pl.col(c).median() for c in ("rho50", "rho90", "resp_rho50", "resp_rho90")])
          .sort(["cand", "q"]))
    print("\n== per candidate: worst quantity, then share of (case, quantity) at or under 1.10 / 1.20 ==")
    w = df.with_columns(pl.max_horizontal("rho50", "rho90", "resp_rho50", "resp_rho90").alias("worst"))
    print(w.group_by("cand").agg(pl.len().alias("case_q"),
                                 *[(pl.col(c) <= t).mean().alias(f"{c}<={t}") for c in ("rho50", "rho90", "worst")
                                   for t in (1.1, 1.2)]).sort("cand"))
    print("\n== area totals |X/T-1| (median over cases) vs a second run's ==")
    t = df.filter(pl.col("q") == "n_per_patch")
    print(t.group_by("cand").agg(pl.col("tot_stems").abs().median().alias("stems"),
                                 pl.col("rep_tot_stems").median().alias("2nd-run stems"),
                                 pl.col("tot_biomass").abs().median().alias("biomass"),
                                 pl.col("rep_tot_biomass").median().alias("2nd-run biomass")).sort("cand"))
    print("\n== subgroups (n >= 30 cells): median over cases of rho50 / rho90, worst group per candidate ==")
    g = (sb.filter(pl.col("n") >= 30).group_by(["cand", "by", "group"])
         .agg(pl.col("rho50").median(), pl.col("rho90").median(), pl.col("n").median()))
    print(g.sort(["cand", "by", "group"]))
    print("\n== A7r per test case (median over quantities), the ones that matter for the threshold ==")
    print(df.filter(pl.col("cand") == "A7r").group_by(["model", "scen"])
          .agg(pl.col("rho50").median(), pl.col("rho50").max().alias("rho50_max"),
               pl.col("rho90").max().alias("rho90_max"), pl.col("resp_rho50").max().alias("resp50_max"))
          .sort(["model", "scen"]))


if __name__ == "__main__":
    main()
