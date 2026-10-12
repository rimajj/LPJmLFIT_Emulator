#!/usr/bin/env python3
"""explore_panel_lin_response.py -- does a PER-CELL LINEAR CLIMATE RESPONSE carry the shift the structure emulator
misses? (STATE NEXT item 4, after explore_panel_dense_bias.py.) No learning; seconds-to-a-minute on the login node.

Background (explore_panel_dense_bias.py, 2026-10-12): A7rH's dense-cell deficit is NOT the unseen run's own deviation
(-0.2 % when cells are picked without the truth) but its learned climate shift: against the oracle O (mean of the
training runs on the SAME held-out leg) the learned shift carries only 27-49 % of each cell's true shift on the held-out
climate models (79 % on the training control), and the prediction is compressed across cells -- sparse cells high,
cells above 10 trees per patch 2.5-6 % low, above 20 about 20 % low.

THE PROBE: for each held-out model g, each cell, window 2071-2100: ordinary least squares of the cell's tree count on
the leg climate over the training rows (runs m1,m2,m3,m5,m6 x the other 9 models' 3 scenarios + ctl_obs; the same rows
the anchor averages), predicted at the held-out leg's climate. Through the means, so its prediction at the anchor
legs' mean climate IS the anchor: L - A = b . (x_leg - x_anchor). Predictor sets: T = tmean_ann; TW = tmean_ann +
cwb_ann; TP = tmean_ann + prec_ann. Scored like the decomposition: shift_slope (share of the oracle's per-cell shift
carried), P/O by oracle-density class, dense-cell (oracle >= 5) area total vs the oracle and vs the truth.

WRITTEN BEFORE THE RUN (2026-10-12): if per-cell response information is what the learned shift lacks, the best linear
set carries >= 0.6 of the oracle shift (median over the 15 held-out cases; A7rH 0.27-0.49) and its dense-cell total vs
the oracle is within 1.5 % in >= 10 of 15 cases (A7rH: 4 of 15). If it carries < 0.4, a per-cell linear response is
NOT the missing information and the sensitivity-feature arm (ADR 0316 sec. 12) is not worth a run.
RESULT 2026-10-12 (ADR 0329): FALSIFIER FIRED -- median share of the true shift carried T 0.13 / TW 0.34 / TP 0.35
(A7rH 0.29); dense total within 1.5 % of the oracle in 6 / 5 / 3 of 15 cases (A7rH 7). The linear set shows the same
pattern by oracle-density class as A7rH. Sensitivity-feature arm not run. (Correction to the header: A7rH is within
1.5 % in 7 of 15, not 4 -- the 4 counted the cases NOT below -1 %.)
"""

import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_panel_a7 as A7  # noqa: E402
import explore_tolerance_measure as tm  # noqa: E402

Q = "n_per_patch"
TRAIN_M = (1, 2, 3, 5, 6)
SETS = {"T": ["tmean_ann"], "TW": ["tmean_ann", "cwb_ann"], "TP": ["tmean_ann", "prec_ann"]}
D = tm.D

df = A7.build_rows().filter(pl.col("win") == "w2071")
w_of = df.group_by("Cell").agg(pl.col("lat").first()).with_columns(np.cos(np.deg2rad(pl.col("lat"))).alias("w"))
P_all = {
    g: pl.read_parquet(os.path.join(D, "eval", "preds_seen", "s1", f"cnt_{g}_A7rH.parquet")) for g in tm.MODELS
}


def lin_pred(tr: pl.DataFrame, te: pl.DataFrame, xs: list[str]) -> pl.DataFrame:
    """Per-cell OLS of Q on xs over tr's rows, evaluated at te's (one row per cell) climate."""
    out = []
    te_i = {c: r for c, r in zip(te["Cell"].to_list(), te.select(xs).to_numpy(), strict=True)}
    for (cell,), grp in tr.group_by(["Cell"]):
        if cell not in te_i:
            continue
        X = grp.select(xs).to_numpy()
        y = grp[Q].to_numpy()
        xm, ym = X.mean(0), y.mean()
        Xc = X - xm
        b = np.linalg.lstsq(Xc, y - ym, rcond=None)[0]
        out.append((cell, ym, ym + float((te_i[cell] - xm) @ b)))
    return pl.DataFrame(out, schema=["Cell", "A", "L"], orient="row")


def tot(k, col, ref):
    return float((k["w"] * k[col]).sum() / (k["w"] * k[ref]).sum() - 1) * 100


rows = []
for g in tm.MODELS:
    legs = [lg for lg in A7.ALL_SLEGS if A7.gcm_of(lg) != g] + ["ctl_obs"]
    tr = df.filter(pl.col("member").is_in(TRAIN_M) & pl.col("leg").is_in(legs) & pl.col(Q).is_not_null())
    for s in tm.SCENS:
        leg = f"{g}_{s}"
        te = df.filter((pl.col("member") == 4) & (pl.col("leg") == leg))
        Om = (
            df.filter(pl.col("member").is_in(TRAIN_M) & (pl.col("leg") == leg))
            .group_by("Cell")
            .agg(pl.col(Q).mean().alias("O"))
        )
        base = (
            te.select("Cell", pl.col(Q).alias("T"))
            .join(Om, on="Cell")
            .join(P_all[g].filter(pl.col("leg") == leg).select("Cell", pl.col(Q).alias("P")), on="Cell")
            .join(w_of.select("Cell", "w"), on="Cell")
        )
        for nm, xs in SETS.items():
            L = lin_pred(tr, te, xs)
            k = base.join(L, on="Cell").with_columns(pl.col("L").clip(lower_bound=0.0)).filter(pl.col("O") > 0)
            dt = (k["O"] - k["A"]).to_numpy()
            ww = k["w"].to_numpy()
            r = dict(leg=leg, scen=s, set=nm)
            for who in ("P", "L"):
                dl = (k[who] - k["A"]).to_numpy()
                r[f"slope {who}"] = float((ww * dt * dl).sum() / (ww * dt * dt).sum())
                kd = k.filter(pl.col("O") >= 5)
                r[f"dense {who}-O"] = tot(kd, who, "O")
                r[f"dense {who}-T"] = tot(kd, who, "T")
                for lab, lo, hi in [("<2", 0, 2), ("10-20", 10, 20), (">=20", 20, 1e9)]:
                    kk = k.filter((pl.col("O") >= lo) & (pl.col("O") < hi))
                    r[f"{who}/O {lab}"] = tot(kk, who, "O") if kk.height else None
            rows.append(r)
    print("done", g, flush=True)

res = pl.DataFrame(rows)
res.write_csv(os.path.join(D, "eval", "lin_response.csv"))
pl.Config.set_tbl_rows(60)
pl.Config.set_tbl_cols(20)
pl.Config.set_tbl_width_chars(250)
num = [c for c in res.columns if c not in ("leg", "scen", "set")]
print(res.select("leg", "set", *[pl.col(c).round(2) for c in num]))
print(
    res.group_by("set", "scen")
    .agg(
        [pl.col(c).median().round(2) for c in num]
        + [(pl.col("dense L-O").abs() <= 1.5).sum().alias("#|L-O|<=1.5"),
           (pl.col("dense P-O").abs() <= 1.5).sum().alias("#|P-O|<=1.5")]
    )
    .sort("set", "scen")
)
print(res.group_by("set").agg(pl.col("slope L").median(), pl.col("slope P").median(),
                              (pl.col("dense L-O").abs() <= 1.5).sum(), (pl.col("dense P-O").abs() <= 1.5).sum()))
