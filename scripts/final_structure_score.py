#!/usr/bin/env python3
"""final_structure_score.py -- the RELAXED PASS STANDARD (ADR 0318 sec. 2) applied to the forest-structure model that
the packaged emulator actually runs: the YEAR-BY-YEAR map of ADR 0330 (scripts/explore_panel_yearly_drift.py), whose
saved predictions (xpanel/eval/yearly/preds_<g>.parquet: unseen run m4, the held-out climate model's three
scenarios, every year 2020-2100) are exactly what python/src/lpjmlfit_emulator/landemu reproduces (ADR 0340).

Every earlier relaxed-standard number (ADR 0318 sec. 3: tree count 1.23x, biomass per tree 1.18x) belongs to the
30-YEAR-WINDOW map A7rH, which the emulator does not run. Basis here, so emulator, truth and second runs are on ONE
footing: per cell, the mean over 2071-2100 of the yearly values (tree count per patch, biomass per tree, the median of
four traits). Truth = run m4; second runs = m1, m2, m3 each against m4 (ADR 0317). 15 cases = 5 held-out climate
models x 3 scenarios.

Dense cells, two definitions, both reported: `truth` (truth >= 5 trees per patch, ADR 0318's wording) and `anchor`
(the per-year anchor's 2071-2100 mean >= 5, defined before the run -- ADR 0329 showed the truth-defined split
selects on the held-out run's own outcome and makes a total look low that is not).
Criteria (ADR 0318 sec. 2): D1 typical (50th pct) error <= 1.2x a second run's, D2 worst-10 % (90th) <= 1.5x,
D3 area totals of stems and biomass within 5 %; sparse S1 typical <= 3x, S2 totals within 25 %. A criterion passes at
the median over cases AND in >= 12 of 15 cases.

WRITTEN BEFORE THE RUN (2026-10-15; ADR 0184):
  harness  run m5 (a training run, outside the second-run pool) scored as the emulator: rho50 0.9-1.1 for every
           quantity, dense and sparse -- else the basis, not the emulator, sets the numbers.
  emulator expectations: dense tree count D1 1.1-1.4 (yearly map ~ the window map, ADR 0330 plateau ~1.1 on single
           years), biomass per tree D1 1.0-1.3, traits < 1; sparse tree count S1 2.5-4 (fails, as the window map);
           dense totals within 5 % (anchor-defined), sparse stem total 10-25 %.
Output: xpanel/eval/final_structure_<dense-def>.csv and the verdict table on stdout. Seconds-to-minutes; SLURM.
SUFFIX=<s> (env) scores preds_<g><s>.parquet instead and writes final_structure_<dense-def><s>.csv (ADR 0349).
"""

from __future__ import annotations

import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_panel_prep as PP  # noqa: E402
import explore_panel_yearly_drift as YD  # noqa: E402

QS = YD.QS
LIM = {"D1": 1.2, "D2": 1.5, "D3": 0.05, "S1": 3.0, "S2": 0.25}
W0, W1 = 2071, 2100
SUFFIX = os.environ.get("SUFFIX", "")


def wmean(d: pl.DataFrame) -> pl.DataFrame:
    return (d.filter(pl.col("Year").is_between(W0, W1)).group_by("Cell")
            .agg([pl.col(q).mean() for q in QS]).with_columns(pl.col("Cell").cast(pl.Int32)))


def errs(X, T, cells):
    j = T.unpivot(index="Cell", on=QS, variable_name="q", value_name="T").join(
        X.unpivot(index="Cell", on=QS, variable_name="q", value_name="X"), on=["Cell", "q"]).join(cells, on="Cell")
    j = j.filter(pl.col("T").is_not_null() & (pl.col("T").abs() > 0))
    return j.with_columns(((pl.col("X") - pl.col("T")).abs() / pl.col("T").abs()).fill_null(np.inf).alias("e"))


def totals(X, T, cells):
    def tot(d):
        d = d.join(cells, on="Cell").fill_null(0.0)
        return float((d["area"] * d["n_per_patch"]).sum()), float((d["area"] * d["n_per_patch"]
                                                                    * d["agb_per_stem"]).sum())
    (nx, bx), (nt, bt) = tot(X), tot(T)
    return nx / nt - 1, bx / bt - 1


def main():
    cells = PP.cells().select(pl.col("Cell").cast(pl.Int32), "lat").with_columns(
        np.cos(np.deg2rad(pl.col("lat"))).alias("area")).drop("lat")
    for dense_def in ("anchor", "truth"):
        rows = []
        for g in PP.GCMS:
            P = pl.read_parquet(os.path.join(YD.OUT, f"preds_{g}{SUFFIX}.parquet")).filter(pl.col("member") == YD.TRUTH)
            for s in ("ssp126", "ssp370", "ssp585"):
                leg = f"{g}_{s}"
                T = YD.yearly(YD.TRUTH, leg)
                if T is None:
                    continue
                T = wmean(T)
                Xl = P.filter(pl.col("leg") == leg)
                cand = {"emulator": wmean(Xl), "harness_m5": wmean(YD.yearly(YD.SECOND, leg))}
                anc = wmean(Xl.select("Cell", "Year", *[pl.col(f"anc_{q}").alias(q) for q in QS]))
                R = [wmean(YD.yearly(m, leg)) for m in YD.POOL]
                tb = T.filter(pl.col("n_per_patch") > 0)
                ref = tb if dense_def == "truth" else anc.join(tb.select("Cell"), on="Cell")
                for grp, sel in (("dense", ref.filter(pl.col("n_per_patch") >= YD.DENSE)),
                                 ("sparse", ref.filter(pl.col("n_per_patch") < YD.DENSE))):
                    cc = cells.join(sel.select("Cell"), on="Cell")
                    eR = pl.concat([errs(r, T, cc) for r in R])
                    b = eR.group_by("q").agg(pl.col("e").quantile(0.5).alias("r50"), pl.col("e").quantile(0.9)
                                             .alias("r90"))
                    rs = [totals(r, T, cc) for r in R]
                    for nm, X in cand.items():
                        a = errs(X, T, cc).group_by("q").agg(pl.col("e").quantile(0.5).alias("x50"),
                                                             pl.col("e").quantile(0.9).alias("x90"))
                        ts, tbio = totals(X, T, cc)
                        for r in a.join(b, on="q").iter_rows(named=True):
                            rows.append(dict(cand=nm, leg=leg, grp=grp, q=r["q"], n=cc.height,
                                             rho50=r["x50"] / r["r50"], rho90=r["x90"] / r["r90"], err50=r["x50"],
                                             rerr50=r["r50"], tot_stems=ts, tot_biomass=tbio,
                                             rep_tot_stems=float(np.median([abs(x[0]) for x in rs])),
                                             rep_tot_biomass=float(np.median([abs(x[1]) for x in rs]))))
        d = pl.DataFrame(rows)
        d.write_csv(os.path.join(PP.OUT, "eval", f"final_structure_{dense_def}{SUFFIX}.csv"))
        for nm in ("harness_m5", "emulator"):
            x = d.filter(pl.col("cand") == nm)
            ncase = x["leg"].n_unique()
            need = 12 if ncase >= 15 else int(np.ceil(0.8 * ncase))
            out = []
            for crit, col, grp in (("D1", "rho50", "dense"), ("D2", "rho90", "dense"), ("S1", "rho50", "sparse")):
                v = x.filter(pl.col("grp") == grp).group_by("q").agg(
                    pl.col(col).median().alias("median"), (pl.col(col) <= LIM[crit]).sum().alias("cases_ok"),
                    pl.col("n").median().alias("cells"))
                out += [dict(crit=crit, what=r["q"], median=r["median"], cases_ok=r["cases_ok"], cells=r["cells"])
                        for r in v.iter_rows(named=True)]
            for crit, grp in (("D3", "dense"), ("S2", "sparse")):
                y = x.filter((pl.col("grp") == grp) & (pl.col("q") == "n_per_patch"))
                for col, refc in (("tot_stems", "rep_tot_stems"), ("tot_biomass", "rep_tot_biomass")):
                    v = y[col].abs()
                    out.append(dict(crit=crit, what=f"{col} (2nd run {y[refc].median():.3f}; signed median "
                                                    f"{y[col].median():+.3f})",
                                    median=float(v.median()), cases_ok=int((v <= LIM[crit]).sum()),
                                    cells=float(y["n"].median())))
            o = pl.DataFrame(out).with_columns(
                pl.col("crit").replace_strict(LIM, return_dtype=pl.Float64).alias("limit"), pl.lit(ncase)
                .alias("cases"))
            o = o.with_columns(((pl.col("median") <= pl.col("limit")) & (pl.col("cases_ok") >= need)).alias("PASS"))
            with pl.Config(tbl_rows=60, fmt_str_lengths=70, tbl_width_chars=200, float_precision=3):
                print(f"\n== {nm}{SUFFIX}, dense defined by the {dense_def}: {ncase} cases; pass = median <= limit AND "
                      f">= {need} cases")
                print(o.sort("crit", "what"))
    print("=== DONE")


if __name__ == "__main__":
    main()
