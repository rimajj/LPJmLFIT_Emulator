"""explore_de_contin.py — LINE X, Germany emulator: what carries the year-to-year swing of a negative-growth STREAK's
continuation, P(G_{y+1} < 0 | c_y >= 1), and a sign head that reproduces it.
(pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "WHAT CARRIES truth's yearly streak continuation")

The shipped sign head (gsign, two-stage) has a weather booster B1 that sees the weather anomalies plus only Type and
log_agb, so it cannot give a tree already in a streak a weather response different from a healthy tree's; the
per-counter Platt (gqsc) fixed the counter MEANS but left the yearly continuation compressed (one-step slope 0.78-0.83
vs a noise ceiling of 0.99). Arms, all on top of the gqsc logit, cross-fitted by cell inside the training members'
validation fold (the gsign OOF rows):
  B1  logistic recalibration per counter with cell-year streak breadth (cs_start, cs_neg)
  W1  residual booster on c_y >= 1 rows: weather inputs + c_y + G_y + rel_dagb_prev + Type + log_agb
  WB  W1 + the cell-year covariates cs_start, cs_neg, cs_gmed
Stages:
  explain   -> shared/eval/contin_explain.json + contin_member_year.csv
  yearblock  W1 cross-fitted by YEAR groups -> shared/eval/contin_yearblock.json
  lowcap     year-blocked low-capacity arms L1 (logistic) / L2 (4-leaf booster) -> shared/eval/contin_lowcap.json
  fit --arm W1|WB   final residual booster on ALL fold-4 OOF rows -> tab/models/DEV-A/gquant/contin_<arm>.txt + .json
Usage:  python explore_de_contin.py explain | fit --arm W1
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_gquant as gq_  # noqa: E402
import explore_de_sh_trans as tr  # noqa: E402
import explore_de_tab_features as F  # noqa: E402
import explore_de_tab_heads as Hh  # noqa: E402

XDE = tr.XDE
SPLIT = "DEV-A"
KEYS = ["member", "Year", "Cell", "Patch", "Type", "ID", "sla_i", "wd_i"]
CS = ["cs_start", "cs_neg", "cs_gmed"]
W_FEATS = [c for c in F.B1 if c != "Type"] + ["c_y", "G_y", "rel_dagb_prev", "Type", "log_agb"]
NTHREADS = int(os.environ.get("SLURM_CPUS_PER_TASK", "8"))
LGB = dict(objective="binary", learning_rate=0.05, num_leaves=31, min_data_in_leaf=2000, feature_fraction=0.8,
           bagging_fraction=0.7, bagging_freq=1, lambda_l2=10.0, max_bin=127, verbose=-1, seed=17)
ROUNDS = 1500
NGRP = 5


def sig(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -40, 40)))


def cell_streak_feats(lf: pl.LazyFrame | pl.DataFrame, by=("Year", "Cell")):
    """cell-year streak covariates over ALL printed living trees of the cell at y (Type <= 6): share starting a
    streak (c_y == 1), share in a streak (c_y >= 1), median G_y. The rollout computes the same on its roster."""
    lf = lf.lazy() if isinstance(lf, pl.DataFrame) else lf
    c = pl.col("c_y").cast(pl.Float64).round(0)
    return (lf.filter(pl.col("Type") <= 6).group_by(list(by))
            .agg(cs_start=(c == 1).cast(pl.Float32).mean(), cs_neg=(c >= 1).cast(pl.Float32).mean(),
                 cs_gmed=pl.col("G_y").cast(pl.Float32).median()))


def trans_cell_feats(members) -> pl.DataFrame:
    out = []
    for mem in members:
        for f in sorted(glob.glob(os.path.join(tr.TRANS, "dev", mem, "cb=dev", "y*.parquet"))):
            d = cell_streak_feats(pl.scan_parquet(f).select("Year", "Cell", "Type", "c_y", "G_y")).collect()
            out.append(d.with_columns(member=pl.lit(mem)))
    D = pl.concat(out)
    assert D.select("member", "Year", "Cell").n_unique() == D.height, "duplicate cell-year keys"
    return D


def gqsc_logit(df: pl.DataFrame, p1: np.ndarray) -> np.ndarray:
    bc = json.load(open(os.path.join(gq_.gdir(SPLIT, ""), "sign_platt_c.json")))["by_c"]
    k = np.clip(np.rint(df["c_y"].cast(pl.Float64).to_numpy()), 0, gq_.SIGNC_MAX).astype(int)
    a = np.array([bc[str(i)]["a"] for i in range(gq_.SIGNC_MAX + 1)])
    b = np.array([bc[str(i)]["b"] for i in range(gq_.SIGNC_MAX + 1)])
    return a[k] * p1 + b[k]


def load(split=SPLIT) -> pl.DataFrame:
    """gsign OOF rows (training members, validation fold) with c_y in 1..4 + features + cell-year covariates."""
    t0 = time.time()
    spec = json.load(open(os.path.join(F.SAMPLES, split, "split.json")))
    oof = pl.read_parquet(os.path.join(Hh.mdir(split), "gsign_oof.parquet")).select(KEYS + ["w_ip", "_y", "p1"])
    filt = Hh.HEADS["gsign"]["filt"] & (pl.col("fold") == spec["val_fold"]) & (pl.col("c_y") >= 0.5)
    df = Hh.load_rows(split, "train", filt, None, None, keep=W_FEATS)
    df = df.select([c for c in dict.fromkeys(W_FEATS + KEYS)]).with_columns(
        *[pl.col(k).cast(oof.schema[k]) for k in KEYS])
    J = df.join(oof, on=KEYS, how="inner")
    assert J.select(KEYS).n_unique() == J.height, "duplicate tree keys after the OOF join"
    cs = trans_cell_feats(J["member"].unique().to_list()).with_columns(
        pl.col("Year").cast(J.schema["Year"]), pl.col("Cell").cast(J.schema["Cell"]))
    J = J.join(cs, on=["member", "Year", "Cell"], how="left")
    assert J["cs_start"].null_count() == 0, "cell covariates missing"
    J = J.with_columns(grp=(pl.col("Cell").cast(pl.Int64).hash(7) % NGRP).cast(pl.Int8))
    print(f"load: {J.height} rows c_y>=1 (OOF {oof.height}), {time.time() - t0:.0f} s", flush=True)
    return J


def year_table(J: pl.DataFrame, p: np.ndarray, kc=1, nmin=200) -> pl.DataFrame:
    f = J.select("member", "Year", "c_y", "w_ip", "_y").with_columns(p=pl.Series(p))
    f = f.filter(pl.col("c_y").cast(pl.Float64).round(0) == kc)
    w = pl.col("w_ip").cast(pl.Float64)
    return (f.group_by("member", "Year")
            .agg(n=pl.len(), obs=(pl.col("_y") * w).sum() / w.sum(), pred=(pl.col("p") * w).sum() / w.sum(),
                 nv=(w ** 2 * pl.col("p") * (1 - pl.col("p"))).sum() / w.sum() ** 2)
            .filter(pl.col("n") >= nmin).sort("member", "Year"))


def score(J, p, y, w, name) -> dict:
    g = year_table(J, p)
    o, m = g["obs"].to_numpy(), g["pred"].to_numpy()
    vo = o.var(ddof=1)
    z = np.log(np.clip(p, 1e-9, 1 - 1e-9) / np.clip(1 - p, 1e-9, 1))
    r = {"arm": name, "c1_slope": float(np.cov(o, m)[0, 1] / vo), "c1_corr": float(np.corrcoef(o, m)[0, 1]),
         "c1_ceiling": float(1 - g["nv"].mean() / vo), "c1_groups": g.height,
         "c1_mean_obs": float(o.mean()), "c1_mean_pred": float(m.mean()),
         "ll": float(np.average(np.logaddexp(0, z) - y * z, weights=w))}
    c = np.rint(J["c_y"].cast(pl.Float64).to_numpy())
    for k in range(1, 5):
        q = c == k
        r[f"c{k}_obs"] = float(np.average(y[q], weights=w[q]))
        r[f"c{k}_pred"] = float(np.average(p[q], weights=w[q]))
    print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}), flush=True)
    return r


def logfit_off(Z, y, w, off):
    th = np.zeros(Z.shape[1])
    for _ in range(80):
        p = sig(off + Z @ th)
        g = Z.T @ (w * (p - y))
        Hm = (Z * (w * p * (1 - p))[:, None]).T @ Z + 1e-9 * np.eye(Z.shape[1])
        step = np.linalg.solve(Hm, g)
        th -= step
        if np.abs(step).max() < 1e-10:
            break
    return th


def booster_fit(X, y, w, off, feats, Xv=None, yv=None, wv=None, offv=None, rounds=ROUNDS):
    import lightgbm as lgb

    cat = [i for i, c in enumerate(feats) if c in F.CAT]
    dt = lgb.Dataset(X, y, weight=w, init_score=off, feature_name=feats, categorical_feature=cat, free_raw_data=True)
    vs, cb = [], []
    if Xv is not None:
        vs = [lgb.Dataset(Xv, yv, weight=wv, init_score=offv, reference=dt)]
        cb = [lgb.early_stopping(100, verbose=False)]
    return lgb.train(dict(LGB, num_threads=NTHREADS), dt, rounds, valid_sets=vs, callbacks=cb)


def explain(split=SPLIT):
    J = load(split)
    y = J["_y"].to_numpy().astype(np.float64)
    w = J["w_ip"].to_numpy().astype(np.float64)
    w = w / w.mean()
    z0 = gqsc_logit(J, J["p1"].to_numpy().astype(np.float64))
    grp = J["grp"].to_numpy()
    c = np.minimum(np.rint(J["c_y"].cast(pl.Float64).to_numpy()), 4).astype(int)
    res = {"n_rows": J.height, "arms": []}
    res["arms"].append(score(J, sig(z0), y, w, "gqsc"))
    # A1 describe: year-mean covariates vs the gqsc residual at c_y = 1
    g = year_table(J, sig(z0))
    q1 = c == 1
    cov = [c_ for c_ in F.B1 if c_.startswith("a_")] + CS + ["G_y"]
    ym = (J.filter(pl.Series(q1)).group_by("member", "Year").agg(*[pl.col(v).cast(pl.Float64).mean() for v in cov]))
    A = g.join(ym, on=["member", "Year"]).with_columns(resid=pl.col("obs") - pl.col("pred"))
    A.write_csv(os.path.join(XDE, "shared", "eval", "contin_member_year.csv"))
    cr = {v: float(np.corrcoef(A["resid"].to_numpy(), A[v].to_numpy())[0, 1]) for v in cov}
    co = {v: float(np.corrcoef(A["obs"].to_numpy(), A[v].to_numpy())[0, 1]) for v in cov}
    res["A1_resid_corr"] = dict(sorted(cr.items(), key=lambda kv: -abs(kv[1])))
    res["A1_obs_corr"] = dict(sorted(co.items(), key=lambda kv: -abs(kv[1])))
    print("A1 resid corr (top 12):", json.dumps({k: round(v, 3) for k, v in list(res["A1_resid_corr"].items())[:12]}))
    print("A1 obs corr (top 12):", json.dumps({k: round(v, 3) for k, v in list(res["A1_obs_corr"].items())[:12]}))
    # B1: per-counter logistic, logit = gqsc + beta_k cs_start + gamma_k cs_neg + d_k, cross-fit by cell
    pB = np.empty_like(y)
    S = J.select("cs_start", "cs_neg").to_numpy().astype(np.float64)
    coefs = {}
    for k in range(1, 5):
        for gi in range(NGRP):
            te, trn = (c == k) & (grp == gi), (c == k) & (grp != gi)
            Z = np.column_stack([S, np.ones(len(y))])
            th = logfit_off(Z[trn], y[trn], w[trn], z0[trn])
            pB[te] = sig(z0[te] + Z[te] @ th)
        th = logfit_off(np.column_stack([S, np.ones(len(y))])[c == k], y[c == k], w[c == k], z0[c == k])
        coefs[str(k)] = {"beta_start": float(th[0]), "gamma_neg": float(th[1]), "d": float(th[2])}
    res["B1_coef_full"] = coefs
    print("B1 coef:", json.dumps(coefs))
    res["arms"].append(score(J, pB, y, w, "B1_breadth"))
    # W1 / WB: residual booster, cross-fit by cell (one held-in group is the early-stopping set)
    for arm, feats in (("W1", W_FEATS), ("WB", W_FEATS + CS)):
        X = F.to_matrix(J, feats)
        pW = np.empty_like(y)
        its = []
        for gi in range(NGRP):
            te = grp == gi
            es = grp == (gi + 1) % NGRP
            trn = ~te & ~es
            t0 = time.time()
            b = booster_fit(X[trn], y[trn], w[trn], z0[trn], feats, X[es], y[es], w[es], z0[es])
            pW[te] = sig(z0[te] + b.predict(X[te], raw_score=True))
            its.append(b.best_iteration)
            print(f"{arm} group {gi}: {b.best_iteration} it, {time.time() - t0:.0f} s", flush=True)
        r = score(J, pW, y, w, arm)
        r["iters"] = its
        if arm == "WB":
            imp = b.feature_importance("gain")
            r["gain"] = dict(sorted(zip(feats, (imp / imp.sum()).round(4).tolist(), strict=True),
                                    key=lambda kv: -kv[1])[:15])
        res["arms"].append(r)
    base = res["arms"][0]["c1_slope"]
    for r in res["arms"]:
        r["d_slope"] = r["c1_slope"] - base
    res["B1_pass"] = bool(res["arms"][1]["d_slope"] >= 0.03 and coefs["1"]["beta_start"] < 0)
    res["W1_pass"] = bool(res["arms"][2]["c1_slope"] >= 0.92 and res["arms"][2]["ll"] <= res["arms"][0]["ll"])
    res["falsifier"] = bool(max(r["d_slope"] for r in res["arms"][1:]) < 0.03)
    out = os.path.join(XDE, "shared", "eval", "contin_explain.json")
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k.endswith("pass") or k == "falsifier"}), "wrote", out)


def yearblock(split=SPLIT):
    """Y1 (TS.md amendment): the W1 booster cross-fitted by YEAR groups instead of cell groups — all cells of a
    member-year share Germany's weather, so a cell-grouped cross-fit lets the booster memorise a year's continuation."""
    J = load(split)
    y = J["_y"].to_numpy().astype(np.float64)
    w = J["w_ip"].to_numpy().astype(np.float64)
    w = w / w.mean()
    z0 = gqsc_logit(J, J["p1"].to_numpy().astype(np.float64))
    grp = (J["Year"].cast(pl.Int64).hash(11) % NGRP).cast(pl.Int8).to_numpy()
    res = {"arms": [score(J, sig(z0), y, w, "gqsc")]}
    X = F.to_matrix(J, W_FEATS)
    pW = np.empty_like(y)
    its = []
    for gi in range(NGRP):
        te, es = grp == gi, grp == (gi + 1) % NGRP
        trn = ~te & ~es
        b = booster_fit(X[trn], y[trn], w[trn], z0[trn], W_FEATS, X[es], y[es], w[es], z0[es])
        pW[te] = sig(z0[te] + b.predict(X[te], raw_score=True))
        its.append(b.best_iteration)
        print(f"W1y group {gi}: {int(te.sum())} rows, {b.best_iteration} it", flush=True)
    r = score(J, pW, y, w, "W1_yearblock")
    r["iters"] = its
    res["arms"].append(r)
    res["Y1_pass"] = bool(r["c1_slope"] >= 0.92)
    res["Y1_memorised"] = bool(r["c1_slope"] < 0.90)
    out = os.path.join(XDE, "shared", "eval", "contin_yearblock.json")
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "arms"}), "wrote", out, flush=True)


LOWCAP_X = [f"a_{v}_{s}" for v in ("cwb_amjjas", "swdown_ann", "vpd_jja", "tmean_ann") for s in ("y", "y1")]
LGB_LOW = dict(LGB, num_leaves=4, min_data_in_leaf=20000, learning_rate=0.03, lambda_l2=100.0)


def lowcap(split=SPLIT):
    """L1 / L2 (TS.md "LOW-CAPACITY streak x weather terms"): year-blocked cross-fit of a per-counter logistic on
    eight drought/energy anomalies and of a 4-leaf booster on W1's features, both on top of the gqsc logit."""
    global LGB
    J = load(split)
    y = J["_y"].to_numpy().astype(np.float64)
    w = J["w_ip"].to_numpy().astype(np.float64)
    w = w / w.mean()
    z0 = gqsc_logit(J, J["p1"].to_numpy().astype(np.float64))
    grp = (J["Year"].cast(pl.Int64).hash(11) % NGRP).cast(pl.Int8).to_numpy()
    c = np.minimum(np.rint(J["c_y"].cast(pl.Float64).to_numpy()), 4).astype(int)
    res = {"arms": [score(J, sig(z0), y, w, "gqsc")]}
    Xl = J.select(LOWCAP_X).to_numpy().astype(np.float64)
    Xl = (Xl - Xl.mean(0)) / Xl.std(0)
    Z = np.column_stack([Xl, np.ones(len(y))])
    pL = np.empty_like(y)
    for k in range(1, 5):
        for gi in range(NGRP):
            te, trn = (c == k) & (grp == gi), (c == k) & (grp != gi)
            pL[te] = sig(z0[te] + Z[te] @ logfit_off(Z[trn], y[trn], w[trn], z0[trn]))
    res["L1_coef_c1"] = dict(zip(LOWCAP_X + ["d"], logfit_off(Z[c == 1], y[c == 1], w[c == 1], z0[c == 1]).round(4)
                                 .tolist(), strict=True))
    print("L1 coef c1:", json.dumps(res["L1_coef_c1"]), flush=True)
    res["arms"].append(score(J, pL, y, w, "L1_logistic"))
    X = F.to_matrix(J, W_FEATS)
    pB = np.empty_like(y)
    its = []
    LGB, keep = LGB_LOW, LGB
    try:
        for gi in range(NGRP):
            te, es = grp == gi, grp == (gi + 1) % NGRP
            trn = ~te & ~es
            b = booster_fit(X[trn], y[trn], w[trn], z0[trn], W_FEATS, X[es], y[es], w[es], z0[es], rounds=400)
            pB[te] = sig(z0[te] + b.predict(X[te], raw_score=True))
            its.append(b.best_iteration)
    finally:
        LGB = keep
    r = score(J, pB, y, w, "L2_booster4")
    r["iters"] = its
    res["arms"].append(r)
    g0 = res["arms"][0]
    for r in res["arms"][1:]:
        r["pass"] = bool(r["c1_slope"] >= g0["c1_slope"] + 0.03 and r["ll"] < g0["ll"])
    res["falsifier"] = bool(all(abs(r["c1_slope"] - g0["c1_slope"]) <= 0.01 for r in res["arms"][1:]))
    out = os.path.join(XDE, "shared", "eval", "contin_lowcap.json")
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps({"L1": res["arms"][1]["pass"], "L2": res["arms"][2]["pass"], "falsifier": res["falsifier"]}),
          "wrote", out, flush=True)


def fit(arm, split=SPLIT):
    """final residual booster on ALL fold-4 OOF c_y >= 1 rows (rounds = the cross-fit's median best iteration)."""
    J = load(split)
    ex = json.load(open(os.path.join(XDE, "shared", "eval", "contin_explain.json")))
    its = [r for r in ex["arms"] if r["arm"] == arm][0]["iters"]
    feats = W_FEATS + (CS if arm == "WB" else [])
    y = J["_y"].to_numpy().astype(np.float64)
    w = J["w_ip"].to_numpy().astype(np.float64)
    w = w / w.mean()
    z0 = gqsc_logit(J, J["p1"].to_numpy().astype(np.float64))
    b = booster_fit(F.to_matrix(J, feats), y, w, z0, feats, rounds=int(np.median(its)))
    d = gq_.gdir(split, "")
    b.save_model(os.path.join(d, f"contin_{arm}.txt"))
    json.dump({"arm": arm, "features": feats, "rounds": int(np.median(its)), "n": J.height, "base": "gqsc"},
              open(os.path.join(d, f"contin_{arm}.json"), "w"), indent=1)
    print("saved", os.path.join(d, f"contin_{arm}.txt"), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["explain", "yearblock", "lowcap", "fit"])
    ap.add_argument("--arm", default="W1")
    a = ap.parse_args()
    if a.stage == "explain":
        explain()
    elif a.stage == "yearblock":
        yearblock()
    elif a.stage == "lowcap":
        lowcap()
    else:
        fit(a.arm)


if __name__ == "__main__":
    main()
