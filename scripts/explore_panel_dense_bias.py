#!/usr/bin/env python3
"""explore_panel_dense_bias.py -- WHERE does the structure emulator's dense-cell tree-count deficit come from?
(STATE NEXT item 4; ADR 0316 sec. 13: A7rH's dense-cell area total is LOW in all 15 held-out-model cases, -0.5 to
-5.1 %, a second run within 0.5 %). Read-only; reads the saved `cnt` predictions (seed 1) and the level tables.

DECOMPOSITION (tree count, area-weighted total over a cell set, as a fraction of the truth total):
  T  = m4 (the unseen run) on the held-out leg, 2071-2100
  P  = A7rH's prediction
  A  = the per-cell ANCHOR A7rH starts from: mean over the training runs (m1,m2,m3,m5,m6) x training legs (the other 9
       climate models x 3 scenarios + ctl_obs), 2071-2100 -- recomputed here, identical in definition to `anchored()`
  O  = the ORACLE expected value: mean of the training runs on the SAME held-out leg (what a perfect learned shift
       would add to A; it never reaches the emulator)
  P - T = (A - O)            the true climate shift the anchor lacks, with sign flipped
        + (P - A)            the learned shift
        + (O - T)            the unseen run's own deviation (noise + member offset + truth-selection)
  => SHIFT ERROR = P - O = (P - A) - (O - A): learned shift minus true shift.
CELL SETS: `dense_T` = truth >= 5 trees per patch (ADR 0316 sec. 13's set; selected on the truth, so every candidate
inherits a regression-to-the-mean deficit -- the second run too); `dense_O` = oracle >= 5 (selected without the truth).

WRITTEN BEFORE THE RUN (2026-10-12) -- what each reading predicts:
  H-shift   (the learned climate shift is too small/shrunk):  P - O < -1 % on dense_O in >= 10 of 15 cases, growing with
            warming (median ssp585 more negative than ssp126); ctl_obs (a training leg, no extrapolation) |P - O| < 1 %.
  H-anchor  (the anchor itself is low and the shift does not fix it): A - O < -1 % on dense_O AND P - A ~ 0.
  H-member  (m4 is a denser run than the training runs): O - T < -1 % on dense_O in most cases, ALSO on ctl_obs, and
            m4's 2000-2019 dense total above the training runs' by about the same amount; the second runs show the
            same sign.
  H-select  (the deficit is the truth selection): on dense_O the deficit shrinks to within the second run's spread.
  Harness: A7rH's dense_T total reproduces explore_panel_abs_err.py's 15 numbers (-0.5 to -5.1 %).
Outputs: printed tables; xpanel/eval/dense_bias_s<SEED>.csv, dense_bias_calib_s<SEED>.csv. Knob SEED (default 1).
RESULT 2026-10-12 (ADR 0329): harness exact (dense_T -0.46 ... -5.06 %). None of H-shift / H-anchor / H-member as
written: the unseen run's own deviation is small (O - T within 1 %, m4's 2000-2019 dense total +0.4 %); no growth with
warming. H-select in a form not anticipated: the deficit is selection on the HELD-OUT LEG'S OWN OUTCOME (truth or
oracle), not on the truth's noise -- with dense defined by the ANCHOR (known before the run) the total is
-3.7 ... +1.5 %, 8 low / 7 high, median 0.0 % (all five seeds alike). The learned shift carries 0.27-0.49 of each
cell's true shift on the held-out models (0.79 on the training control); the oracle shift is 96 % signal;
true-on-learned 1.06-1.17 -> unexplained per-cell response, not a bias.
"""

import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_panel_prep as PP  # noqa: E402
import explore_tolerance_measure as tm  # noqa: E402

PRED_SET, ARM = os.environ.get("PRED_SET", "cnt"), os.environ.get("ARM", "A7rH")
SEED = os.environ.get("SEED", "1")  # LightGBM seed of the saved predictions
TRAIN_M = (1, 2, 3, 5, 6)  # the `both` / `cnt` training runs
ALL_SLEGS = PP.SLEGS + PP.NEW_SLEGS
Q = "n_per_patch"
D = tm.D


def lev(m, leg, win="w2071"):
    f = os.path.join(D, "levels", f"m{m}_{leg}_{win}.parquet")
    return pl.read_parquet(f).select("Cell", Q) if os.path.exists(f) else None


def mean_of(frames):
    frames = [f for f in frames if f is not None]
    return pl.concat(frames).group_by("Cell").agg(pl.col(Q).mean()), len(frames)


cells = (
    pl.read_parquet(os.path.join(D, "cells.parquet"))
    .select("Cell", "lat")
    .with_columns(np.cos(np.deg2rad(pl.col("lat"))).alias("w"))
)


def tot(j, col, ref="T"):
    return float((j["w"] * j[col]).sum() / (j["w"] * j[ref]).sum() - 1) * 100


rows, calib = [], []
for g in tm.MODELS:
    p = pl.read_parquet(os.path.join(D, "eval", "preds_seen", f"s{SEED}", f"{PRED_SET}_{g}_{ARM}.parquet"))
    legs = [lg for lg in ALL_SLEGS if not lg.startswith(g + "_")] + ["ctl_obs"]
    A, nA = mean_of([lev(m, lg) for m in TRAIN_M for lg in legs])
    Th = lev(4, "hist", "h2000")
    Oh, _ = mean_of([lev(m, "hist", "h2000") for m in TRAIN_M])
    for leg in [*(f"{g}_{s}" for s in tm.SCENS), "ctl_obs"]:
        T = lev(4, leg)
        Om, nO = mean_of([lev(m, leg) for m in TRAIN_M])
        S2 = pl.concat([lev(m, leg) for m in TRAIN_M]).group_by("Cell").agg((pl.col(Q).var() / pl.len()).alias("nv"))
        X = p.filter(pl.col("leg") == leg).select("Cell", pl.col(Q).alias("P"))
        j = (
            T.rename({Q: "T"})
            .join(X, on="Cell")
            .join(A.rename({Q: "A"}), on="Cell")
            .join(Om.rename({Q: "O"}), on="Cell")
            .join(S2, on="Cell")
            .join(Th.rename({Q: "Th"}), on="Cell")
            .join(Oh.rename({Q: "Oh"}), on="Cell")
            .join(cells, on="Cell")
        )
        for m in (1, 2, 3):
            j = j.join(lev(m, leg).rename({Q: f"R{m}"}), on="Cell", how="left")
        sets = [("dense_T", pl.col("T") >= 5), ("dense_O", pl.col("O") >= 5), ("dense_A", pl.col("A") >= 5),
                ("all", pl.col("T") > 0)]
        for cs, sel in sets:
            k = j.filter(sel)
            r = dict(gcm=g, leg=leg, scen=leg.rsplit("_", 1)[-1], set=cs, n=k.height, nA=nA, nO=nO)
            r["P-T"] = tot(k, "P")
            r["A-T"] = tot(k, "A")
            r["O-T"] = tot(k, "O")
            r["P-O"] = tot(k, "P", "O")  # shift error, as % of the oracle total
            r["learned P-A"] = (float((k["w"] * (k["P"] - k["A"])).sum() / (k["w"] * k["O"]).sum())) * 100
            r["true O-A"] = (float((k["w"] * (k["O"] - k["A"])).sum() / (k["w"] * k["O"]).sum())) * 100
            r["hist m4-train"] = tot(k, "Th", "Oh")
            r["2nd run R-T"] = float(np.mean([tot(k, f"R{m}") for m in (1, 2, 3)]))
            rows.append(r)
        # per-cell calibration (on the oracle, so the truth's noise is out): how much of each cell's true shift O - A
        # the learned shift P - A carries (weighted LS slope through the origin), and P / O by oracle-density class
        k = j.filter(pl.col("O") > 0)
        dt, dl, w = (k["O"] - k["A"]).to_numpy(), (k["P"] - k["A"]).to_numpy(), k["w"].to_numpy()
        c = dict(gcm=g, leg=leg, scen=leg.rsplit("_", 1)[-1])
        c["shift_slope"] = float((w * dt * dl).sum() / (w * dt * dt).sum())
        # share of the oracle's per-cell shift variance that is signal (1 - the 5-run mean's own noise variance / total)
        c["reliability"] = float(1 - (w * k["nv"].to_numpy()).sum() / (w * dt * dt).sum())
        # the reverse regression: true shift on learned shift (1 = calibrated; > 1 = the learned shift under-reaches)
        c["true_on_learned"] = float((w * dt * dl).sum() / (w * dl * dl).sum())
        for lab, lo, hi in [("<2", 0, 2), ("2-5", 2, 5), ("5-10", 5, 10), ("10-20", 10, 20), (">=20", 20, 1e9)]:
            kk = k.filter((pl.col("O") >= lo) & (pl.col("O") < hi))
            c[f"P/O {lab}"] = tot(kk, "P", "O") if kk.height else None
        calib.append(c)

df = pl.DataFrame(rows)
df.write_csv(os.path.join(D, "eval", f"dense_bias_s{SEED}.csv"))
pl.Config.set_tbl_rows(80)
pl.Config.set_tbl_cols(16)
pl.Config.set_tbl_width_chars(220)
num = ["P-T", "A-T", "O-T", "P-O", "learned P-A", "true O-A", "hist m4-train", "2nd run R-T"]
for cs in ("dense_T", "dense_O", "dense_A", "all"):
    print(f"\n== cell set {cs}: area totals, % (per case)")
    print(df.filter(pl.col("set") == cs).select("leg", "n", *[pl.col(c).round(2) for c in num]))
    print(
        df.filter(pl.col("set") == cs)
        .group_by("scen")
        .agg([pl.col(c).median().round(2) for c in num] + [(pl.col("P-O") < -1).sum().alias("#P-O<-1")])
        .sort("scen")
    )
cal = pl.DataFrame(calib)
cal.write_csv(os.path.join(D, "eval", f"dense_bias_calib_s{SEED}.csv"))
cc = [c for c in cal.columns if c.startswith("P/O") or c in ("shift_slope", "reliability", "true_on_learned")]
print("\n== per-cell calibration against the oracle: shift_slope = share of each cell's true shift the learned shift")
print("   carries (1 = all); P/O <class> = prediction vs oracle total in that oracle-density class, %")
print(cal.select("leg", *[pl.col(c).round(2) for c in cc]))
print(cal.group_by("scen").agg([pl.col(c).median().round(2) for c in cc]).sort("scen"))
