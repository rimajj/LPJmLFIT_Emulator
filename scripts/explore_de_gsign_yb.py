"""explore_de_gsign_yb.py — LINE X, Germany emulator: refit the sign head's WEATHER booster (gsign B1) with early
stopping on held-out YEARS instead of held-out cells of the same years (arm "gqsy").
(pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "gsign weather booster refit with YEAR-held-out stopping")

Every two-stage head early-stops its weather booster on the validation fold of CELLS from the training years, so the
stopping rule rewards memorising each training year's weather: one step ahead the shipped sign head's yearly skill is
corr 0.98 on weather years it trained on and 0.78 on unseen years of the same GCM (TS.md). Here B0 is kept; B1 is
refitted in a 5-fold YEAR cross-fit (fold g predicted, fold g+1 = early stopping, three trained on) -> out-of-year OOF
scores -> per-counter Platt on them (validation-fold cells, where B0 is out-of-sample too) -> final B1 on all rows
at the median best iteration.
Writes tab/models/DEV-A/gquant/gsign_yb_B1.txt + gsign_yb.json (incl. by_c Platt). Sampler: explore_de_gquant
sign_cal "y".  Usage: python explore_de_gsign_yb.py
"""

from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_gquant as gq_  # noqa: E402
import explore_de_tab_features as F  # noqa: E402
import explore_de_tab_heads as Hh  # noqa: E402

SPLIT = "DEV-A"
NGRP = 5


def main():
    import lightgbm as lgb

    t0 = time.time()
    d = Hh.mdir(SPLIT)
    meta = json.load(open(os.path.join(d, "gsign_meta.json")))
    f0, f1 = meta["features_B0"], meta["features_B1"]
    h = Hh.HEADS["gsign"]
    df = Hh.load_rows(SPLIT, "train", h["filt"], h["label"], h["max_rows"], keep=f0 + f1)
    y = df["_y"].to_numpy().astype(np.float64)
    ok = np.isfinite(y)
    df, y = df.filter(pl.Series(ok)), y[ok]
    w = df["w_ip"].to_numpy().astype(np.float64)
    b0 = lgb.Booster(model_file=os.path.join(d, "gsign_B0.txt"))
    s0 = b0.predict(F.to_matrix(df, f0), raw_score=True, num_threads=Hh.NTHREADS)
    X1 = F.to_matrix(df, f1)
    yr = df["Year"].cast(pl.Int64)
    grp = (yr.hash(11) % NGRP).cast(pl.Int8).to_numpy()
    c = np.clip(np.rint(df["c_y"].cast(pl.Float64).to_numpy()), 0, gq_.SIGNC_MAX).astype(int)
    print(f"rows {df.height}, years {yr.n_unique()}, load+B0 {time.time() - t0:.0f} s", flush=True)
    p1 = dict(Hh.P1, objective="binary", num_threads=Hh.NTHREADS)
    cat = Hh.cat_idx(f1)
    oof = np.empty_like(y)
    its = []
    for g in range(NGRP):
        te, es = grp == g, grp == (g + 1) % NGRP
        trn = ~te & ~es
        dt = lgb.Dataset(X1[trn], y[trn], weight=w[trn], init_score=s0[trn], feature_name=f1, categorical_feature=cat,
                         free_raw_data=False)
        dv = lgb.Dataset(X1[es], y[es], weight=w[es], init_score=s0[es], reference=dt)
        b = lgb.train(p1, dt, num_boost_round=h["rounds"][1], valid_sets=[dv], valid_names=["val"],
                      callbacks=[lgb.early_stopping(30, verbose=False)])
        oof[te] = s0[te] + b.predict(X1[te], raw_score=True, num_iteration=b.best_iteration)
        its.append(int(b.best_iteration))
        print(f"year fold {g}: {int(te.sum())} rows, best {b.best_iteration}, {time.time() - t0:.0f} s", flush=True)
    # Platt on the validation-fold CELLS only: there B0 is out-of-sample too (as for gqsc's fit)
    spec = json.load(open(os.path.join(F.SAMPLES, SPLIT, "split.json")))
    vf = df["fold"].to_numpy() == spec["val_fold"]
    by_c = {}
    for k in range(gq_.SIGNC_MAX + 1):
        q = (c == k) & vf
        a_, b_ = gq_._platt(oof[q], y[q], w[q] / w[q].mean())
        by_c[str(k)] = {"a": a_, "b": b_, "n": int(q.sum())}
    nfin = max(1, int(np.median(its)))
    dt = lgb.Dataset(X1, y, weight=w, init_score=s0, feature_name=f1, categorical_feature=cat, free_raw_data=False)
    bf = lgb.train(p1, dt, num_boost_round=nfin)
    gd = gq_.gdir(SPLIT, "")
    bf.save_model(os.path.join(gd, "gsign_yb_B1.txt"))

    def ll(z, q):
        return float(np.average(np.logaddexp(0, z[q]) - y[q] * z[q], weights=w[q]))

    zc = np.array([by_c[str(k)]["a"] for k in range(gq_.SIGNC_MAX + 1)])[c] * oof \
        + np.array([by_c[str(k)]["b"] for k in range(gq_.SIGNC_MAX + 1)])[c]
    out = {"features_B1": f1, "best_iters": its, "final_rounds": nfin, "shipped_b1_iters": meta["b1_best_iter"],
           "by_c": by_c, "oof_ll_raw": ll(oof, np.ones(len(y), bool)), "oof_ll_platt_c": ll(zc, np.ones(len(y), bool)),
           "oof_ll_b0_only": ll(s0, np.ones(len(y), bool)), "Y0_falsifier": bool(nfin >= 300)}
    json.dump(out, open(os.path.join(gd, "gsign_yb.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k not in ("features_B1",)}), flush=True)


if __name__ == "__main__":
    main()
