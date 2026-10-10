#!/usr/bin/env python3
"""explore_relaxed_standard.py -- LINE X: score a saved panel arm against the RELAXED pass standard (ADR 0318).

Owner, 2026-10-10: "I think we have to relax the passing standarts a bit. as long as the dense ells are fine and the
sparse cells dont drift away completely we should go on."

PROPOSED STANDARD (line X's numbers, written BEFORE the first scoring; the owner may move them). Per test case (held-out
climate model x scenario, truth = run 4, "second run" = runs 1-3 each against run 4), all six panel quantities:
  DENSE cells (truth >= 5 trees per patch, ~80 % of tree-bearing cells):
    D1  typical-cell error (median over cells of |X - T| / |T|) <= 1.2 x a second run's
    D2  worst-10 % error (90th centile)                         <= 1.5 x a second run's
    D3  area totals of stems and of biomass                       within 5 %
  SPARSE cells (truth < 5 trees per patch) -- "does not drift away completely":
    S1  typical-cell error                                        <= 3 x a second run's
    S2  area totals of stems and of biomass                       within 25 %
  A criterion PASSES when it holds in the median over the cases AND in >= 12 of the 15 cases.
  (The no-drift-in-transient-runs clause is a separate test: it needs a year-by-year run, see ADR 0318.)
EXPECTED for the current best arm (A7rH, PRED_SET=cnt, seed 1), written before scoring: the four traits pass
D1/D2/S1; tree count is borderline on D1 (~1.2) and passes D2 (~1.4); biomass per tree passes D2 but is borderline
on D1; D3 passes (dense stems total ~3 % low); S1 fails for tree count (~3.0) and passes for the traits; S2 passes.
RESULT (2026-10-10, ADR 0318 sec. 3): as expected except S2 -- the sparse-cell STEM total is 19.5 % off (10 of 15
cases within 25 %), so it fails. Tree count D1 1.23 (6/15 cases) and biomass per tree D1 1.18 (9/15) fail on the
case count; everything else passes.
Knobs: PRED_SET (default cnt), ARM (default A7rH). Seconds on the login node. Output: eval/relaxed_<set>_<arm>.csv.
"""

import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_tolerance_measure as tm  # noqa: E402

PRED_SET, ARM = os.environ.get("PRED_SET", "cnt"), os.environ.get("ARM", "A7rH")
DENSE = 5.0
LIM = {"D1": 1.2, "D2": 1.5, "D3": 0.05, "S1": 3.0, "S2": 0.25}


def errs(X, T, cells):
    j = tm.long(T, "T").join(tm.long(X, "X"), on=["Cell", "q"]).join(cells, on="Cell")
    j = j.filter(pl.col("T").is_not_null() & (pl.col("T").abs() > 0))
    return j.with_columns(((pl.col("X") - pl.col("T")).abs() / pl.col("T").abs()).fill_null(np.inf).alias("e"))


def totals(X, T, cells):
    def tot(d):
        d = d.join(cells, on="Cell")
        return (
            float((d["area"] * d["n_per_patch"]).sum()),
            float((d["area"] * d["n_per_patch"] * d["agb_per_stem"]).sum()),
        )

    (nx, bx), (nt, bt) = tot(X), tot(T)
    return nx / nt - 1, bx / bt - 1


def main():
    cells = pl.read_parquet(os.path.join(tm.D, "cells.parquet")).select("Cell", "lat")
    cells = cells.with_columns(np.cos(np.deg2rad(pl.col("lat"))).alias("area")).drop("lat")
    rows = []
    for g in tm.MODELS:
        f = os.path.join(tm.D, "eval", "preds_seen", "s1", f"{PRED_SET}_{g}_{ARM}.parquet")
        if not os.path.exists(f):
            print(f"missing {f}")
            continue
        P = pl.read_parquet(f)
        for s in tm.SCENS:
            leg = f"{g}_{s}"
            T = tm.lev(tm.TRUTH, leg)
            R = [tm.lev(m, leg) for m in tm.POOL]
            if T is None or any(r is None for r in R):
                continue
            X = P.filter(pl.col("leg") == leg).drop("leg")
            tb = T.filter(pl.col("n_per_patch") > 0)
            for grp, sel in (
                ("dense", tb.filter(pl.col("n_per_patch") >= DENSE)),
                ("sparse", tb.filter(pl.col("n_per_patch") < DENSE)),
            ):
                cc = cells.join(sel.select("Cell"), on="Cell")
                eX = errs(X, T, cc)
                eR = pl.concat([errs(r, T, cc) for r in R])
                a = eX.group_by("q").agg(pl.col("e").quantile(0.5).alias("x50"), pl.col("e").quantile(0.9).alias("x90"))
                b = eR.group_by("q").agg(pl.col("e").quantile(0.5).alias("r50"), pl.col("e").quantile(0.9).alias("r90"))
                ts, tbio = totals(X, T, cc)
                rs = [totals(r, T, cc) for r in R]
                for r in a.join(b, on="q").iter_rows(named=True):
                    rows.append(
                        dict(
                            leg=leg,
                            scen=s,
                            grp=grp,
                            q=r["q"],
                            n=cc.height,
                            rho50=r["x50"] / r["r50"],
                            rho90=r["x90"] / r["r90"],
                            err50=r["x50"],
                            rerr50=r["r50"],
                            tot_stems=ts,
                            tot_biomass=tbio,
                            rep_tot_stems=float(np.median([abs(x[0]) for x in rs])),
                            rep_tot_biomass=float(np.median([abs(x[1]) for x in rs])),
                        )
                    )
    d = pl.DataFrame(rows)
    os.makedirs(os.path.join(tm.D, "eval"), exist_ok=True)
    d.write_csv(os.path.join(tm.D, "eval", f"relaxed_{PRED_SET}_{ARM}.csv"))
    ncase = d["leg"].n_unique()
    need = 12 if ncase >= 15 else int(np.ceil(0.8 * ncase))

    def verdict(col, grp, lim, absval=False):
        x = d.filter(pl.col("grp") == grp)
        x = x.group_by("leg", "q").agg(pl.col(col).first().abs() if absval else pl.col(col).first())
        return x.group_by("q").agg(pl.col(col).median().alias("median"), (pl.col(col) <= lim).sum().alias("cases_ok"))

    out = []
    for crit, col, grp in (("D1", "rho50", "dense"), ("D2", "rho90", "dense"), ("S1", "rho50", "sparse")):
        v = verdict(col, grp, LIM[crit])
        out += [
            dict(crit=crit, what=r["q"], median=r["median"], cases_ok=r["cases_ok"]) for r in v.iter_rows(named=True)
        ]
    for crit, grp in (("D3", "dense"), ("S2", "sparse")):
        x = d.filter((pl.col("grp") == grp) & (pl.col("q") == "n_per_patch"))
        for col, ref in (("tot_stems", "rep_tot_stems"), ("tot_biomass", "rep_tot_biomass")):
            v = x[col].abs()
            out.append(
                dict(
                    crit=crit,
                    what=f"{col} (second run {x[ref].median():.3f})",
                    median=float(v.median()),
                    cases_ok=int((v <= LIM[crit]).sum()),
                )
            )
    o = pl.DataFrame(out).with_columns(
        pl.col("crit").replace_strict(LIM, return_dtype=pl.Float64).alias("limit"), pl.lit(ncase).alias("cases")
    )
    o = o.with_columns(((pl.col("median") <= pl.col("limit")) & (pl.col("cases_ok") >= need)).alias("PASS"))
    with pl.Config(tbl_rows=60, fmt_str_lengths=50, tbl_width_chars=160):
        print(f"{PRED_SET}/{ARM}: {ncase} cases, a criterion passes at median <= limit AND >= {need} cases")
        print(o.sort("crit", "what"))
    print("signed dense-cell totals per case (stems, biomass):")
    print(
        d.filter((pl.col("grp") == "dense") & (pl.col("q") == "n_per_patch")).select(
            "leg", (pl.col("tot_stems") * 100).round(2), (pl.col("tot_biomass") * 100).round(2)
        )
    )


if __name__ == "__main__":
    main()
