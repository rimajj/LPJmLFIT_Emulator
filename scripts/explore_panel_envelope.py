#!/usr/bin/env python3
"""explore_panel_envelope.py -- LINE X: is the anchored direct map (A7r, explore_panel_a7.py `seen`) wrong mainly where
the test climate lies OUTSIDE what the same cell saw in training? A within-test-case, cell-level check of the coverage
hypothesis (the per-model reading -- the two failing test cases are the two hottest -- is confounded by everything else
that differs between climate models).

Per HG test case (held-out model g x scenario, m4, 2071-2100) and per cell: the test window's 30-yr means of tmean_ann,
twarm_month, tcold_month, prec_ann, cwb_ann vs the RANGE of the same cell's training windows (the other models' legs,
w2041 and w2071, the ctl_obs pool mean, hist 2000-2019). Cell is OUTSIDE when any of tmean/twarm/tcold is above the
training maximum or prec/cwb below the training minimum (hotter or drier than anything the cell was trained on).
Per-cell pass = the explore_glob_eval.score rule (all six quantities within max(10 %, stratum spread)), recomputed here
and checked against score()'s aggregate pass rate (harness: |diff| < 1e-12).
Statistic: pass rate of A7r and of the ceiling (m3, a second run of the original) on inside vs outside cells, pooled
over the test cases; the ratio A7r / ceiling removes "outside cells are just noisier".

WRITTEN BEFORE THE RUN (2026-10-09):
  harness   recomputed per-cell pass reproduces score()'s pass rate exactly, per test case.
  E   the A7r / ceiling ratio is lower OUTSIDE than inside by >= 0.15 (pooled) and in the same direction in >= 2/3 of the
      test cases that have >= 30 outside cells.
  Falsifier: outside ratio >= inside ratio - 0.05 -> failures are not concentrated where the climate is new, and wider
      climate coverage in training would not be the lever.
Output: xpanel/eval/envelope.csv
"""

from __future__ import annotations

import os
import sys

import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_glob_eval as ev  # noqa: E402
import explore_panel_a7 as PA  # noqa: E402
import explore_panel_prep as PP  # noqa: E402

HOT, DRY = ["tmean_ann", "twarm_month", "tcold_month"], ["prec_ann", "cwb_ann"]


def cell_pass(P, T, R, cells):
    j = ev.long(T, "T").join(ev.long(R, "R"), on=["Cell", "q"]).join(ev.long(P, "P"), on=["Cell", "q"], how="left")
    j = j.join(cells, on="Cell").join(T.select("Cell", pl.col("n_per_patch").alias("dens")), on="Cell")
    j = j.with_columns(pl.col("dens").cut(ev.STRATA, labels=["<2", "2-5", "5-10", "10-20", ">20"]).alias("stratum"),
                       ((pl.col("T") - pl.col("R")).abs() / ((pl.col("T") + pl.col("R")).abs() / 2)).alias("spread"))
    S = j.group_by(["q", "stratum"]).agg(pl.col("spread").median().alias("S"))
    j = j.join(S, on=["q", "stratum"]).with_columns(
        (pl.col("T").abs() * pl.max_horizontal(pl.lit(0.10), pl.col("S"))).alias("allowed"))
    j = j.with_columns(((pl.col("P") - pl.col("T")).abs() <= pl.col("allowed") * (1 + 1e-9)).alias("pass"))
    j = j.filter(pl.col("T").is_not_null()).with_columns(pl.col("pass").fill_null(False))
    return j.group_by("Cell").agg(pl.col("pass").all().alias("ok"))


def main():
    cw = PA.climate_windows()
    cells_all = PP.cells().select("Cell", "lat")
    pdir = os.path.join(PA.EVAL, "preds_seen", "s1")
    rows, percell = [], []
    for g in PP.GCMS:
        train_legs = [lg for lg in PP.SLEGS if not lg.startswith(g)] + ["ctl_obs", "hist"]
        tr = cw.filter(pl.col("leg").is_in(train_legs))
        rng = tr.group_by("Cell").agg([pl.col(c).max().alias(f"max_{c}") for c in HOT]
                                      + [pl.col(c).min().alias(f"min_{c}") for c in DRY])
        P_all = pl.read_parquet(os.path.join(pdir, f"HG_{g}_A7r.parquet"))
        for s in PP.SCENS:
            leg = f"{g}_{s}"
            T_w, R_w = PA.lev(PA.TRUTH, leg, "w2071"), PA.lev(PA.REPLICA, leg, "w2071")
            T_h = PA.lev(PA.TRUTH, "hist", "h2000")
            if T_w is None or R_w is None:
                continue
            tb = (T_w.filter(pl.col("n_per_patch") > 0).select("Cell")
                  .vstack(T_h.filter(pl.col("n_per_patch") > 0).select("Cell")).unique())
            sc = cells_all.join(tb, on="Cell").filter(pl.col("Cell").is_in(list(set(T_w["Cell"]) & set(R_w["Cell"]))))
            P = P_all.filter(pl.col("leg") == leg).drop("leg").filter(pl.col("Cell").is_in(sc["Cell"]))
            agg = ev.score(P, T_h, T_w, T_h, R_w, PA.lev(PA.REPLICA, "hist", "h2000"), sc)["pass_rate"]
            cp = cell_pass(P, T_w, R_w, sc).rename({"ok": "ok_arm"})
            assert abs(float(cp["ok_arm"].mean()) - agg) < 1e-12, (leg, float(cp["ok_arm"].mean()), agg)
            cc = cell_pass(R_w, T_w, R_w, sc).rename({"ok": "ok_ceil"})
            te = cw.filter((pl.col("leg") == leg) & (pl.col("win") == "w2071")).join(rng, on="Cell")
            out = pl.any_horizontal([pl.col(c) > pl.col(f"max_{c}") for c in HOT]
                                    + [pl.col(c) < pl.col(f"min_{c}") for c in DRY])
            te = te.with_columns(out.alias("outside"),
                                 (pl.col("tmean_ann") - pl.col("max_tmean_ann")).alias("t_excess"))
            d = cp.join(cc, on="Cell").join(te.select("Cell", "outside", "t_excess"), on="Cell")
            percell.append(d.with_columns(pl.lit(leg).alias("test_leg")))
            for side in (False, True):
                x = d.filter(pl.col("outside") == side)
                rows.append(dict(test_leg=leg, outside=side, n=x.height,
                                 arm=float(x["ok_arm"].mean()) if x.height else None,
                                 ceiling=float(x["ok_ceil"].mean()) if x.height else None))
    r = pl.DataFrame(rows).with_columns((pl.col("arm") / pl.col("ceiling")).alias("ratio"))
    pc = pl.concat(percell)
    pooled = pc.group_by("outside").agg(pl.len().alias("n"), pl.col("ok_arm").mean().alias("arm"),
                                        pl.col("ok_ceil").mean().alias("ceiling")).with_columns(
        (pl.col("arm") / pl.col("ceiling")).alias("ratio")).sort("outside")
    r.write_csv(os.path.join(PA.EVAL, "envelope.csv"))
    pc.write_parquet(os.path.join(PA.EVAL, "envelope_cells.parquet"))
    with pl.Config(tbl_rows=60, float_precision=3):
        print("harness: per-cell pass reproduces score() on every test case (asserted)")
        print(r.sort("test_leg", "outside"))
        print("POOLED"); print(pooled)
        w = r.pivot(on="outside", index="test_leg", values="ratio").rename({"false": "inside", "true": "outside"})
        n = r.filter(pl.col("outside")).select("test_leg", pl.col("n").alias("n_out"))
        w = w.join(n, on="test_leg").filter(pl.col("n_out") >= 30)
        print(w.with_columns((pl.col("outside") < pl.col("inside")).alias("lower_outside")))


if __name__ == "__main__":
    main()
