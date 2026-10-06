#!/usr/bin/env python3
"""explore_de_gquant.py — LINE X, Germany emulator: a DISTRIBUTIONAL model of next year's growth efficiency magnitude.
(pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "a DISTRIBUTIONAL G-magnitude model")

The TAB sampler draws log|G_{y+1}| as "mean head + a residual from the pooled OOF residuals of its predicted-value
decile". Its calibration (explore_de_gpit.py) showed the right spread but a LOCATION that bends the wrong way with the
tree's previous G (median too high for middling previous G, too low for the top decile). This replaces the magnitude
model by direct LightGBM QUANTILE heads, one per sign and level, on the old magnitude heads' B0 + B1 features in one
booster. The sign model (gsign head + calibrated logit offset) is unchanged.

  quantiles   11 levels QLEV; prediction = base (weighted training quantile) + raw score; crossing repaired by sorting
  sampling    u -> linear interpolation between levels, linear extrapolation beyond the outer ones (u in [1e-4, 1-1e-4])
  PIT         the exact inverse of that piecewise-linear map (closed form; gated against the draws in explore_de_gpit)

STAGES  prep   --sign neg|pos         cache the training matrix (same rows / weights / validation fold as the A2 heads,
                                      <= MAX_ROWS per sign) to tab/models/<split>/gquant/<sign>_*.npy
        train  --sign S --level i     fit one quantile head (SLURM array: i = task id)
        submit                        prep (2 jobs) then the 22-task training array, chained
        sign                          Platt recalibration of the gsign head on its OOF -> sign_platt.json (arm "gqs")
        signc                         the same PER COUNTER c_y = 0..4 -> sign_platt_c.json (arm "gqsc")
        signc2                        per counter with a separate weather-booster scale -> sign_platt_c2.json ("gqsc2")
        calib                         conformal offsets on the validation fold -> calib.json (arm "gqc")
API     GQ.load(split); gq.attach(stepper)  -> stepper._sample_G uses the quantile model (kappa = 0 refused)
        gq.pit(X, g, p) / gq.quantiles(X, sign) / gq.sample(X, p, u_s, u_r)
        class TabALG2HSGQ  = the g2hs coupled arm with this sampler
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_sh_trans as tr  # noqa: E402
import explore_de_tab_features as F  # noqa: E402
import explore_de_tab_g2 as tg2  # noqa: E402
import explore_de_tab_heads as Hh  # noqa: E402
import explore_de_tab_probe2 as pr2  # noqa: E402
import explore_de_tab_stepper as ts  # noqa: E402

QLEV = [0.005, 0.02, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.98, 0.995]
UCLIP = 1e-4
LEVELSETS = {"11": list(range(11)), "7": [1, 3, 4, 5, 6, 7, 9], "5": [2, 4, 5, 6, 8]}
MAX_ROWS = int(os.environ.get("GQ_MAX_ROWS", "6000000"))
NTHREADS = int(os.environ.get("SLURM_CPUS_PER_TASK", "8"))
PARAMS = dict(objective="quantile", metric="quantile", learning_rate=0.1, num_leaves=63, min_data_in_leaf=1000,
              feature_fraction=0.8, bagging_fraction=0.7, bagging_freq=1, lambda_l2=1.0, max_bin=127, verbose=-1,
              seed=13)


def gdir(split, tag=None):
    d = os.path.join(Hh.mdir(split), "gquant" + (os.environ.get("GQ_TAG", "") if tag is None else tag))
    os.makedirs(d, exist_ok=True)
    return d


def features(split="DEV-A") -> list[str]:
    m = json.load(open(os.path.join(Hh.mdir(split), "gmag_pos_meta.json")))
    return list(dict.fromkeys(m["features_B0"] + m["features_B1"]))


def pinball(q: np.ndarray, y: np.ndarray, a: float) -> np.ndarray:
    d = y - q
    return np.maximum(a * d, (a - 1) * d)


# ================================================================================================ training
def prep(split, sign):
    spec = json.load(open(os.path.join(F.SAMPLES, split, "split.json")))
    h = Hh.HEADS[f"gmag_{sign}"]
    feats = features(split)
    t0 = time.time()
    df = Hh.load_rows(split, "train", h["filt"], h["label"], MAX_ROWS, keep=feats + ["G_y1", "c_y1", "Cell"])
    y = df["_y"].to_numpy().astype(np.float64)
    ok = np.isfinite(y)
    df, y = df.filter(pl.Series(ok)), y[ok]
    d = gdir(split)
    np.save(os.path.join(d, f"{sign}_X.npy"), F.to_matrix(df, feats))
    np.save(os.path.join(d, f"{sign}_y.npy"), y.astype(np.float32))
    np.save(os.path.join(d, f"{sign}_w.npy"), df["w_ip"].to_numpy().astype(np.float32))
    np.save(os.path.join(d, f"{sign}_va.npy"), df["fold"].to_numpy() == spec["val_fold"])
    np.save(os.path.join(d, f"{sign}_cell.npy"), df["Cell"].to_numpy().astype(np.int64))
    json.dump({"features": feats, "n": int(df.height), "sign": sign}, open(os.path.join(d, f"{sign}_prep.json"), "w"))
    print(f"prep {sign}: {df.height} rows, {len(feats)} features, {time.time() - t0:.0f} s", flush=True)


def wquantile(y, w, a):
    o = np.argsort(y)
    c = np.cumsum(w[o])
    return float(y[o][np.searchsorted(c, a * c[-1])])


def train(split, sign, level):
    import lightgbm as lgb

    d = gdir(split)
    a = QLEV[level]
    meta0 = json.load(open(os.path.join(d, f"{sign}_prep.json")))
    feats = meta0["features"]
    X = np.load(os.path.join(d, f"{sign}_X.npy"), mmap_mode="r")
    y = np.load(os.path.join(d, f"{sign}_y.npy")).astype(np.float64)
    w = np.load(os.path.join(d, f"{sign}_w.npy")).astype(np.float64)
    va = np.load(os.path.join(d, f"{sign}_va.npy"))
    trm = ~va
    base = wquantile(y[trm], w[trm], a)
    cat = [i for i, c in enumerate(feats) if c in F.CAT]
    t0 = time.time()
    dt = lgb.Dataset(np.asarray(X[trm]), y[trm], weight=w[trm], init_score=np.full(trm.sum(), base),
                     feature_name=feats, categorical_feature=cat, free_raw_data=True)
    dv = lgb.Dataset(np.asarray(X[va]), y[va], weight=w[va], init_score=np.full(va.sum(), base), reference=dt)
    b = lgb.train(dict(PARAMS, alpha=a, num_threads=NTHREADS), dt, num_boost_round=3000, valid_sets=[dv],
                  valid_names=["val"], callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(100)])
    nm = f"{sign}_q{level:02d}"
    b.save_model(os.path.join(d, nm + ".txt"), num_iteration=b.best_iteration)
    qv = base + b.predict(np.asarray(X[va]), raw_score=True, num_iteration=b.best_iteration)
    cover = float(np.average(y[va] <= qv, weights=w[va]))
    meta = {"sign": sign, "level": level, "alpha": a, "base": base, "best_iter": int(b.best_iteration),
            "val_pinball": float(np.average(pinball(qv, y[va], a), weights=w[va])), "val_coverage": cover,
            "n_train": int(trm.sum()), "n_val": int(va.sum()), "t_s": round(time.time() - t0), "features": feats}
    json.dump(meta, open(os.path.join(d, nm + ".json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in meta.items() if k != "features"}), flush=True)


def calib(split):
    """conformalised offsets: per sign and level c = weighted validation quantile at alpha of (y - q) -> calib.json"""
    import lightgbm as lgb

    d = gdir(split)
    out = {}
    for s in ("neg", "pos"):
        X = np.load(os.path.join(d, f"{s}_X.npy"), mmap_mode="r")
        va = np.load(os.path.join(d, f"{s}_va.npy"))
        Xv = np.asarray(X[va])
        y = np.load(os.path.join(d, f"{s}_y.npy")).astype(np.float64)[va]
        w = np.load(os.path.join(d, f"{s}_w.npy")).astype(np.float64)[va]
        Q = []
        for i in range(len(QLEV)):
            nm = os.path.join(d, f"{s}_q{i:02d}")
            b = lgb.Booster(model_file=nm + ".txt")
            Q.append(json.load(open(nm + ".json"))["base"] + b.predict(Xv, raw_score=True, num_threads=NTHREADS))
        Q = np.sort(np.column_stack(Q), axis=1)
        c = [wquantile(y - Q[:, i], w, a) for i, a in enumerate(QLEV)]
        Qc = np.sort(Q + np.asarray(c)[None, :], axis=1)
        out[s] = {"offset": c,
                  "coverage_before": [float(np.average(y <= Q[:, i], weights=w)) for i in range(len(QLEV))],
                  "coverage_after": [float(np.average(y <= Qc[:, i], weights=w)) for i in range(len(QLEV))]}
        print(s, json.dumps({k: np.round(v, 4).tolist() for k, v in out[s].items()}), flush=True)
    json.dump(out, open(os.path.join(d, "calib.json"), "w"), indent=1)


def sign_platt(split):
    """Platt recalibration of the gsign head: weighted logistic regression of the label on its raw logit (OOF = the
    split's validation fold of the training members) -> gquant/sign_platt.json {a, b}."""
    oof = pl.read_parquet(os.path.join(Hh.mdir(split), "gsign_oof.parquet"))
    s = oof["p1"].to_numpy().astype(np.float64)
    y = oof["_y"].to_numpy().astype(np.float64)
    w = oof["w_ip"].to_numpy().astype(np.float64)
    w = w / w.mean()
    th = np.array([1.0, 0.0])
    for _ in range(50):  # Newton
        z = th[0] * s + th[1]
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -40, 40)))
        g = np.array([np.sum(w * (p - y) * s), np.sum(w * (p - y))])
        h = w * p * (1 - p)
        Hm = np.array([[np.sum(h * s * s), np.sum(h * s)], [np.sum(h * s), np.sum(h)]])
        step = np.linalg.solve(Hm, g)
        th = th - step
        if np.abs(step).max() < 1e-10:
            break
    def ll(a, b):
        z = a * s + b
        return float(np.average(np.logaddexp(0, z) - y * z, weights=w))
    out = {"a": float(th[0]), "b": float(th[1]), "oof_logloss_before": ll(1.0, 0.0),
           "oof_logloss_after": ll(th[0], th[1]), "n": int(len(y))}
    json.dump(out, open(os.path.join(gdir(split), "sign_platt.json"), "w"), indent=1)
    print(json.dumps(out), flush=True)


def _platt(s, y, w):
    """weighted Newton fit of the label on a s + b -> (a, b)."""
    th = np.array([1.0, 0.0])
    for _ in range(50):
        p = 1.0 / (1.0 + np.exp(-np.clip(th[0] * s + th[1], -40, 40)))
        g = np.array([np.sum(w * (p - y) * s), np.sum(w * (p - y))])
        h = w * p * (1 - p)
        step = np.linalg.solve(np.array([[np.sum(h * s * s), np.sum(h * s)], [np.sum(h * s), np.sum(h)]]), g)
        th = th - step
        if np.abs(step).max() < 1e-10:
            break
    return float(th[0]), float(th[1])


SIGNC_MAX = 4  # counter groups 0..SIGNC_MAX (the C's BM_INC_COUNTER_MAX - 1: a c_y = 5 tree is already dead)


def sign_platt_c(split):
    """PER-COUNTER Platt recalibration of the gsign head (arm "gqsc"; TS.md "per-counter sign recalibration"): the
    pooled Platt of sign_platt corrects the pooled calibration only, while the head under-predicts the continuation
    of a negative-growth streak (c_y >= 1) and over-predicts its start (c_y = 0). Same OOF rows; c_y joined from the
    trans table on the full tree key -> gquant/sign_platt_c.json {"by_c": {k: {a, b}}, gates}."""
    keys = ["member", "Year", "Cell", "Patch", "Type", "ID", "sla_i", "wd_i"]
    oof = pl.read_parquet(os.path.join(Hh.mdir(split), "gsign_oof.parquet"))
    parts = []
    for mem in oof["member"].unique().to_list():
        o = oof.filter(pl.col("member") == mem)
        t = (pl.scan_parquet(os.path.join(tr.TRANS, "dev", mem, "cb=dev", "y*.parquet"))
             .select(*[pl.col(k).cast(o.schema[k]) for k in keys[1:]], "c_y")
             .join(o.lazy().select(keys[1:]), on=keys[1:], how="semi").collect())
        parts.append(o.join(t, on=keys[1:], how="left"))
    J = pl.concat(parts)
    found = float(J["c_y"].is_not_null().mean())
    extra = J.height - oof.height
    print(f"join: {J.height} rows ({extra} extra from duplicate keys), c_y found {found:.5f}", flush=True)
    J = J.filter(pl.col("c_y").is_not_null())
    s = J["p1"].to_numpy().astype(np.float64)
    y = J["_y"].to_numpy().astype(np.float64)
    w = J["w_ip"].to_numpy().astype(np.float64)
    w = w / w.mean()
    c = np.minimum(np.rint(J["c_y"].cast(pl.Float64).to_numpy()), SIGNC_MAX).astype(int)
    pc = json.load(open(os.path.join(gdir(split), "sign_platt.json")))

    def sig(z):
        return 1.0 / (1.0 + np.exp(-np.clip(z, -40, 40)))

    def ll(z, q):
        return float(np.average(np.logaddexp(0, z) - y[q] * z, weights=w[q]))

    z_pool = pc["a"] * s + pc["b"]
    by_c, z_new = {}, np.empty_like(s)
    for k in range(SIGNC_MAX + 1):
        q = c == k
        a_, b_ = _platt(s[q], y[q], w[q])
        z_new[q] = a_ * s[q] + b_
        by_c[str(k)] = {"a": a_, "b": b_, "n": int(q.sum()), "obs": float(np.average(y[q], weights=w[q])),
                        "pred_pooled": float(np.average(sig(z_pool[q]), weights=w[q])),
                        "pred_after": float(np.average(sig(z_new[q]), weights=w[q])),
                        "ll_pooled": ll(z_pool[q], q), "ll_after": ll(z_new[q], q)}
        print(k, json.dumps({kk: round(v, 5) if isinstance(v, float) else v for kk, v in by_c[str(k)].items()}),
              flush=True)
    allq = np.ones(len(s), bool)
    out = {"by_c": by_c, "join_found": found, "join_extra_rows": extra,
           "ll_pooled": ll(z_pool, allq), "ll_after": ll(z_new, allq),
           "C0_c1_under": by_c["1"]["pred_pooled"] < by_c["1"]["obs"],
           "C0_c0_over": by_c["0"]["pred_pooled"] > by_c["0"]["obs"],
           "C1_max_abs_after": max(abs(v["pred_after"] - v["obs"]) for v in by_c.values())}
    json.dump(out, open(os.path.join(gdir(split), "sign_platt_c.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "by_c"}), flush=True)


def _logfit(Z, y, w):
    """weighted Newton logistic regression of y on the columns of Z (no implicit intercept) -> coefficients."""
    th = np.zeros(Z.shape[1])
    th[:-1] = 1.0
    for _ in range(60):
        p = 1.0 / (1.0 + np.exp(-np.clip(Z @ th, -40, 40)))
        g = Z.T @ (w * (p - y))
        Hm = (Z * (w * p * (1 - p))[:, None]).T @ Z
        step = np.linalg.solve(Hm, g)
        th = th - step
        if np.abs(step).max() < 1e-10:
            break
    return th


def sign_platt_c2(split):
    """PER-COUNTER Platt with a SEPARATE scale for the weather booster (arm "gqsc2"; TS.md "per-counter CLIMATE scale"):
    logit = a0_k * B0 + a1_k * B1 + b_k, B0 = OOF p0 (kappa 0), B1 = p1 - p0, per c_y = 0..SIGNC_MAX. Gate G0: the
    yearly (member-year) slope of predicted vs observed continuation at c_y = 1, for the pooled Platt, gqsc and this
    fit -> gquant/sign_platt_c2.json."""
    keys = ["Year", "Cell", "Patch", "Type", "ID", "sla_i", "wd_i"]
    oof = pl.read_parquet(os.path.join(Hh.mdir(split), "gsign_oof.parquet"))
    parts = []
    for mem in oof["member"].unique().to_list():
        o = oof.filter(pl.col("member") == mem)
        t = (pl.scan_parquet(os.path.join(tr.TRANS, "dev", mem, "cb=dev", "y*.parquet"))
             .select(*[pl.col(k).cast(o.schema[k]) for k in keys], "c_y")
             .join(o.lazy().select(keys), on=keys, how="semi").collect())
        parts.append(o.join(t, on=keys, how="left"))
    J = pl.concat(parts).filter(pl.col("c_y").is_not_null())
    s0 = J["p0"].to_numpy().astype(np.float64)
    s1 = J["p1"].to_numpy().astype(np.float64)
    y = J["_y"].to_numpy().astype(np.float64)
    w = J["w_ip"].to_numpy().astype(np.float64)
    w = w / w.mean()
    c = np.minimum(np.rint(J["c_y"].cast(pl.Float64).to_numpy()), SIGNC_MAX).astype(int)
    pc = json.load(open(os.path.join(gdir(split), "sign_platt.json")))
    bc = json.load(open(os.path.join(gdir(split), "sign_platt_c.json")))["by_c"]

    def sig(z):
        return 1.0 / (1.0 + np.exp(-np.clip(z, -40, 40)))

    z = {"pooled": pc["a"] * s1 + pc["b"],
         "gqsc": np.array([bc[str(k)]["a"] for k in range(SIGNC_MAX + 1)])[c] * s1
         + np.array([bc[str(k)]["b"] for k in range(SIGNC_MAX + 1)])[c],
         "gqsc2": np.empty_like(s1)}
    by_c = {}
    for k in range(SIGNC_MAX + 1):
        q = c == k
        th = _logfit(np.column_stack([s0[q], s1[q] - s0[q], np.ones(q.sum())]), y[q], w[q])
        z["gqsc2"][q] = th[0] * s0[q] + th[1] * (s1[q] - s0[q]) + th[2]
        by_c[str(k)] = {"a0": float(th[0]), "a1": float(th[1]), "b": float(th[2]), "n": int(q.sum())}
    out = {"by_c": by_c}
    q1 = c == 1
    for nm, zz in z.items():
        f = pl.DataFrame({"member": J["member"].to_numpy()[q1], "Year": J["Year"].to_numpy()[q1],
                          "w": w[q1], "y": y[q1], "p": sig(zz[q1])})
        g = (f.group_by("member", "Year").agg(n=pl.len(), obs=(pl.col("y") * pl.col("w")).sum() / pl.col("w").sum(),
                                              pred=(pl.col("p") * pl.col("w")).sum() / pl.col("w").sum())
             .filter(pl.col("n") >= 200))
        slope = g.select(pl.cov("obs", "pred") / pl.col("obs").var()).item()
        corr = g.select(pl.corr("obs", "pred")).item()
        ll = float(np.average(np.logaddexp(0, zz) - y * zz, weights=w))
        out[nm] = {"c1_year_slope": slope, "c1_year_corr": corr, "c1_groups": g.height, "ll": ll}
        print(nm, json.dumps(out[nm]), flush=True)
    for k, v in by_c.items():
        print(k, json.dumps(v), f"a1/a0 {v['a1'] / v['a0']:.3f}", flush=True)
    json.dump(out, open(os.path.join(gdir(split), "sign_platt_c2.json"), "w"), indent=1)


def bench(split, n=200_000, threads=1):
    """predict cost per tree of the magnitude step: old (mean head B0 + B1 of one sign) vs this model (11 heads),
    single thread, on cached training rows."""
    d = gdir(split)
    feats = json.load(open(os.path.join(d, "pos_prep.json")))["features"]
    X = pl.DataFrame(np.asarray(np.load(os.path.join(d, "pos_X.npy"), mmap_mode="r")[:n]), schema=feats, orient="row")
    H = Hh.TabHeads.load(split, heads=["gmag_pos"])
    H.nthreads = threads
    g = GQ(split)
    g.nthreads = threads
    out = {}
    for lab, f in (("old_mean_head", lambda: H.raw("gmag_pos", X, 1.0)),
                   ("quantile_11", lambda: g.quantiles(X, "pos"))):
        f()
        t0 = time.perf_counter()
        f()
        out[lab] = (time.perf_counter() - t0) / n * 1e6
    print(json.dumps({"us_per_tree": {k: round(v, 2) for k, v in out.items()}, "threads": threads, "n": n}), flush=True)


def submit(split, hours=6):
    logs = os.path.join(REPO, "logs")
    jd = os.path.join(F.TAB, "_jobs")
    os.makedirs(jd, exist_ok=True)
    me = os.path.abspath(__file__)
    head = ("#!/bin/bash\n#SBATCH --account=waldspektrum --partition=standard --qos=short\n"
            "#SBATCH --cpus-per-task={c} --time={h:02d}:00:00\n#SBATCH --job-name={n} --output={o}\n{x}"
            "set -eu\nexport POLARS_MAX_THREADS={c} OMP_NUM_THREADS={c}\n")
    jids = []
    for s in ("neg", "pos"):
        js = os.path.join(jd, f"gq_prep_{s}.jcf")
        open(js, "w").write(head.format(c=16, h=3, n=f"X-de-gq-prep-{s}", o=f"{logs}/X-de-gq-prep-{s}.%j.out", x="")
                            + f"{F.PY} -u {me} prep --split {split} --sign {s}\necho '=== JOB DONE ==='\n")
        jids.append(os.popen(f"sbatch --parsable {js}").read().strip())
    for k, s in enumerate(("neg", "pos")):
        js = os.path.join(jd, f"gq_train_{s}.jcf")
        open(js, "w").write(
            head.format(c=16, h=hours, n=f"X-de-gq-{s}", o=f"{logs}/X-de-gq-{s}.%A_%a.out",
                        x=f"#SBATCH --array=0-{len(QLEV) - 1} --dependency=afterok:{jids[k]}\n")
            + f"{F.PY} -u {me} train --split {split} --sign {s} --level $SLURM_ARRAY_TASK_ID\n"
            + "echo '=== JOB DONE ==='\n")
        print(os.popen(f"sbatch --parsable {js}").read().strip(), js, flush=True)
    print("prep jobs", jids, flush=True)


# ================================================================================================ residual heads ("rq")
RTAG = "_res"
RPARAMS = dict(PARAMS, num_leaves=31, min_data_in_leaf=500)


def mean_head(H, sign: str, M: np.ndarray, feats: list[str]) -> np.ndarray:
    """the shipped L2 magnitude head (B0 + B1 at kappa 1) on a feature matrix in `feats` order."""
    return H.raw(f"gmag_{sign}", pl.DataFrame(M, schema=feats, orient="row"), 1.0)


def cell_slice(cell: np.ndarray) -> np.ndarray:
    """deterministic 0..4 slice by cell (Knuth multiplicative hash): 0 = held out, 1 = early stopping, 2-4 = train."""
    return ((cell.astype(np.uint64) * np.uint64(2654435761)) % np.uint64(2**32)) % np.uint64(5)


def rprep(split, sign):
    """re-cache the training rows WITH Cell into gquant_res/, gate them against the cached gquant/ rows, and store
    the mean head on the validation-fold rows (the only rows on which it is out of sample)."""
    os.environ["GQ_TAG"] = RTAG
    prep(split, sign)
    d0, d = gdir(split, ""), gdir(split, RTAG)
    for nm in ("y", "va", "w"):
        a, b = np.load(os.path.join(d0, f"{sign}_{nm}.npy")), np.load(os.path.join(d, f"{sign}_{nm}.npy"))
        assert a.shape == b.shape and np.array_equal(a, b), f"re-prep differs from the cache in {nm}"
    va = np.load(os.path.join(d, f"{sign}_va.npy"))
    idx = np.flatnonzero(va)
    feats = json.load(open(os.path.join(d, f"{sign}_prep.json")))["features"]
    X = np.asarray(np.load(os.path.join(d, f"{sign}_X.npy"), mmap_mode="r")[idx], dtype=np.float64)
    H = Hh.TabHeads.load(split, heads=[f"gmag_{sign}"])
    np.save(os.path.join(d, f"{sign}_vidx.npy"), idx)
    np.save(os.path.join(d, f"{sign}_m.npy"), mean_head(H, sign, X, feats))
    cs = cell_slice(np.load(os.path.join(d, f"{sign}_cell.npy"))[idx])
    print(f"rprep {sign}: gate OK (y, va, w identical); {idx.size} validation rows, "
          f"{len(np.unique(np.load(os.path.join(d, f'{sign}_cell.npy'))[idx]))} cells, slices "
          f"{np.bincount(cs.astype(np.int64), minlength=5).tolist()}", flush=True)


def rtrain(split, sign, level):
    import lightgbm as lgb

    d = gdir(split, RTAG)
    a = QLEV[level]
    feats = json.load(open(os.path.join(d, f"{sign}_prep.json")))["features"]
    idx = np.load(os.path.join(d, f"{sign}_vidx.npy"))
    X = np.asarray(np.load(os.path.join(d, f"{sign}_X.npy"), mmap_mode="r")[idx])
    y = np.load(os.path.join(d, f"{sign}_y.npy"))[idx].astype(np.float64)
    w = np.load(os.path.join(d, f"{sign}_w.npy"))[idx].astype(np.float64)
    m = np.load(os.path.join(d, f"{sign}_m.npy"))
    cs = cell_slice(np.load(os.path.join(d, f"{sign}_cell.npy"))[idx])
    trm, esm = cs >= 2, cs == 1
    base = wquantile(y[trm] - m[trm], w[trm], a)
    cat = [i for i, c in enumerate(feats) if c in F.CAT]
    t0 = time.time()
    dt = lgb.Dataset(X[trm], y[trm], weight=w[trm], init_score=m[trm] + base, feature_name=feats,
                     categorical_feature=cat, free_raw_data=True)
    dv = lgb.Dataset(X[esm], y[esm], weight=w[esm], init_score=m[esm] + base, reference=dt)
    b = lgb.train(dict(RPARAMS, alpha=a, num_threads=NTHREADS), dt, num_boost_round=1000, valid_sets=[dv],
                  valid_names=["es"], callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(100)])
    nm = f"{sign}_q{level:02d}"
    b.save_model(os.path.join(d, nm + ".txt"), num_iteration=b.best_iteration)
    meta = {"sign": sign, "level": level, "alpha": a, "base": base, "init": "mean_head",
            "best_iter": int(b.best_iteration), "n_train": int(trm.sum()), "n_es": int(esm.sum()),
            "t_s": round(time.time() - t0), "features": feats}
    json.dump(meta, open(os.path.join(d, nm + ".json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in meta.items() if k != "features"}), flush=True)


def rcompare(split, ntime=20_000):
    """rq vs gq on the held-out cells (slice 0) of the validation fold -> gquant_res/rq_compare.json"""
    d = gdir(split, RTAG)
    gq, rq = GQ(split, tag=""), GQ(split, tag=RTAG)
    qa = np.asarray(QLEV)
    res = {}
    for s in ("neg", "pos"):
        idx = np.load(os.path.join(d, f"{s}_vidx.npy"))
        ho = cell_slice(np.load(os.path.join(d, f"{s}_cell.npy"))[idx]) == 0
        X = np.asarray(np.load(os.path.join(d, f"{s}_X.npy"), mmap_mode="r")[idx[ho]], dtype=np.float64)
        y = np.load(os.path.join(d, f"{s}_y.npy"))[idx[ho]].astype(np.float64)
        w = np.load(os.path.join(d, f"{s}_w.npy"))[idx[ho]].astype(np.float64)
        for lab, g in (("gq", gq), ("rq", rq)):
            Q = g.quantiles_m(X, s)
            pin = float(np.mean([np.average(pinball(Q[:, i], y, a), weights=w) for i, a in enumerate(qa)]))
            cov = [float(np.average(y <= Q[:, i], weights=w)) for i in range(len(qa))]
            g.nthreads = 1
            g.quantiles_m(X[:200], s)
            t1 = time.perf_counter()
            g.quantiles_m(X[:ntime], s)
            us = (time.perf_counter() - t1) / min(ntime, len(y)) * 1e6
            g.nthreads = NTHREADS
            res[f"{s}_{lab}"] = {"pinball": pin, "coverage": cov, "worst_cov_err": float(np.max(np.abs(
                np.asarray(cov) - qa))), "us_per_tree_1thr": us, "n": int(len(y)),
                "crossing_share": float((np.diff(np.column_stack([b0 + b.predict(X[:20000], raw_score=True)
                                                                  for b, b0 in zip(g.b[s], g.base[s], strict=True)]),
                                                 axis=1) < 0).any(1).mean())}
            print(lab, s, json.dumps({k: v for k, v in res[f"{s}_{lab}"].items() if k != "coverage"}), flush=True)
    v = {}
    for s in ("neg", "pos"):
        g_, r_ = res[f"{s}_gq"], res[f"{s}_rq"]
        v[s] = {"pin_ratio": r_["pinball"] / g_["pinball"], "cov_excess": r_["worst_cov_err"] - g_["worst_cov_err"],
                "cost_ratio": r_["us_per_tree_1thr"] / g_["us_per_tree_1thr"]}
    ok = all(x["pin_ratio"] <= 1.005 and x["cov_excess"] <= 0.005 and x["cost_ratio"] <= 0.25 for x in v.values())
    out = {"rows": res, "verdict": v, "pass": ok,
           "rule": "pin_ratio <= 1.005, cov_excess <= 0.005, cost_ratio <= 0.25, both signs (TS.md, arm rq)"}
    json.dump(out, open(os.path.join(d, "rq_compare.json"), "w"), indent=1)
    print("VERDICT", json.dumps(v), "PASS" if ok else "FAIL", flush=True)


def rsubmit(split):
    logs = os.path.join(REPO, "logs")
    jd = os.path.join(F.TAB, "_jobs")
    me = os.path.abspath(__file__)
    head = ("#!/bin/bash\n#SBATCH --account=waldspektrum --partition=standard --qos=short\n"
            "#SBATCH --cpus-per-task={c} --time={h:02d}:00:00\n#SBATCH --job-name={n} --output={o}\n{x}"
            "set -eu\nexport POLARS_MAX_THREADS={c} OMP_NUM_THREADS={c} SLURM_CPUS_PER_TASK={c}\n")
    pj = []
    for s in ("neg", "pos"):
        js = os.path.join(jd, f"rq_prep_{s}.jcf")
        open(js, "w").write(head.format(c=16, h=2, n=f"X-de-rq-prep-{s}", o=f"{logs}/X-de-rq-prep-{s}.%j.out", x="")
                            + f"{F.PY} -u {me} rprep --split {split} --sign {s}\necho '=== JOB DONE ==='\n")
        pj.append(os.popen(f"sbatch --parsable {js}").read().strip())
    tj = []
    for k, s in enumerate(("neg", "pos")):
        js = os.path.join(jd, f"rq_train_{s}.jcf")
        open(js, "w").write(
            head.format(c=8, h=4, n=f"X-de-rq-{s}", o=f"{logs}/X-de-rq-{s}.%A_%a.out",
                        x=f"#SBATCH --array=0-{len(QLEV) - 1} --dependency=afterok:{pj[k]}\n")
            + f"{F.PY} -u {me} rtrain --split {split} --sign {s} --level $SLURM_ARRAY_TASK_ID\n"
            + "echo '=== JOB DONE ==='\n")
        tj.append(os.popen(f"sbatch --parsable {js}").read().strip())
    js = os.path.join(jd, "rq_compare.jcf")
    open(js, "w").write(head.format(c=16, h=2, n="X-de-rq-cmp", o=f"{logs}/X-de-rq-cmp.%j.out",
                                    x=f"#SBATCH --dependency=afterok:{tj[0]}:{tj[1]}\n")
                        + f"{F.PY} -u {me} rcompare --split {split}\necho '=== JOB DONE ==='\n")
    cj = os.popen(f"sbatch --parsable {js}").read().strip()
    print("rq jobs: prep", pj, "train", tj, "compare", cj, flush=True)


# =============================================================================================== distilled heads ("dq")
DTAG = "_dist"
DMAX = int(os.environ.get("DQ_MAX_ROWS", "3000000"))
DPARAMS = dict(objective="regression", metric="l2", learning_rate=0.1, num_leaves=31, min_data_in_leaf=500,
               feature_fraction=0.8, bagging_fraction=0.7, bagging_freq=1, lambda_l2=1.0, max_bin=127, verbose=-1,
               seed=13)
GAP_EPS = 1e-3


def dtarget(Q: np.ndarray, j: int) -> np.ndarray:
    """student head j: 0 = the teacher's median (level 5); j >= 1 = log(gap + eps) between sorted levels j-1 and j."""
    return Q[:, 5] if j == 0 else np.log(Q[:, j] - Q[:, j - 1] + GAP_EPS)


def dprep(split, sign):
    """teacher (gq, sorted) quantiles on gq's training rows (<= DMAX) and on the early-stopping cells of the
    validation fold -> gquant_dist/"""
    d0, dr, d = gdir(split, ""), gdir(split, RTAG), gdir(split, DTAG)
    va = np.load(os.path.join(d0, f"{sign}_va.npy"))
    tr_idx = np.flatnonzero(~va)
    if tr_idx.size > DMAX:
        tr_idx = np.sort(np.random.default_rng(11).choice(tr_idx, DMAX, replace=False))
    vidx = np.load(os.path.join(dr, f"{sign}_vidx.npy"))
    cs = cell_slice(np.load(os.path.join(dr, f"{sign}_cell.npy"))[vidx])
    es_idx = vidx[cs == 1]
    g = GQ(split, tag="")
    Xm = np.load(os.path.join(d0, f"{sign}_X.npy"), mmap_mode="r")
    for nm, idx in (("t", tr_idx), ("e", es_idx)):
        t0 = time.time()
        Q = np.vstack([g.quantiles_m(np.asarray(Xm[idx[i:i + 500_000]], dtype=np.float64), sign)
                       for i in range(0, idx.size, 500_000)])
        np.save(os.path.join(d, f"{sign}_{nm}idx.npy"), idx)
        np.save(os.path.join(d, f"{sign}_Q{nm}.npy"), Q.astype(np.float32))
        print(f"dprep {sign} {nm}: {idx.size} rows, teacher {time.time() - t0:.0f} s", flush=True)


def dtrain(split, sign, j):
    import lightgbm as lgb

    d0, d = gdir(split, ""), gdir(split, DTAG)
    feats = json.load(open(os.path.join(d0, f"{sign}_prep.json")))["features"]
    Xm = np.load(os.path.join(d0, f"{sign}_X.npy"), mmap_mode="r")
    w = np.load(os.path.join(d0, f"{sign}_w.npy")).astype(np.float64)
    ti, ei = np.load(os.path.join(d, f"{sign}_tidx.npy")), np.load(os.path.join(d, f"{sign}_eidx.npy"))
    yt = dtarget(np.load(os.path.join(d, f"{sign}_Qt.npy")).astype(np.float64), j)
    ye = dtarget(np.load(os.path.join(d, f"{sign}_Qe.npy")).astype(np.float64), j)
    cat = [i for i, c in enumerate(feats) if c in F.CAT]
    t0 = time.time()
    dt = lgb.Dataset(np.asarray(Xm[ti]), yt, weight=w[ti], feature_name=feats, categorical_feature=cat,
                     free_raw_data=True)
    dv = lgb.Dataset(np.asarray(Xm[ei]), ye, weight=w[ei], reference=dt)
    b = lgb.train(dict(DPARAMS, num_threads=NTHREADS), dt, num_boost_round=1000, valid_sets=[dv], valid_names=["es"],
                  callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(100)])
    nm = f"{sign}_d{j:02d}"
    b.save_model(os.path.join(d, nm + ".txt"), num_iteration=b.best_iteration)
    pe = b.predict(np.asarray(Xm[ei]), num_iteration=b.best_iteration)
    meta = {"sign": sign, "head": j, "init": "distil", "best_iter": int(b.best_iteration),
            "es_mae": float(np.average(np.abs(pe - ye), weights=w[ei])), "n_train": int(ti.size),
            "t_s": round(time.time() - t0), "features": feats}
    json.dump(meta, open(os.path.join(d, nm + ".json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in meta.items() if k != "features"}), flush=True)


def dcompare(split, ntime=20_000):
    """dq vs gq on the held-out cells (slice 0) of the validation fold, against the TRUE y -> gquant_dist/"""
    dr, d0 = gdir(split, RTAG), gdir(split, "")
    gq, dq = GQ(split, tag=""), DQ(split)
    qa = np.asarray(QLEV)
    res = {}
    for s in ("neg", "pos"):
        idx = np.load(os.path.join(dr, f"{s}_vidx.npy"))
        idx = idx[cell_slice(np.load(os.path.join(dr, f"{s}_cell.npy"))[idx]) == 0]
        X = np.asarray(np.load(os.path.join(d0, f"{s}_X.npy"), mmap_mode="r")[idx], dtype=np.float64)
        y = np.load(os.path.join(d0, f"{s}_y.npy"))[idx].astype(np.float64)
        w = np.load(os.path.join(d0, f"{s}_w.npy"))[idx].astype(np.float64)
        Qs = {}
        for lab, g in (("gq", gq), ("dq", dq)):
            Q = Qs[lab] = g.quantiles_m(X, s)
            pin = float(np.mean([np.average(pinball(Q[:, i], y, a), weights=w) for i, a in enumerate(qa)]))
            cov = [float(np.average(y <= Q[:, i], weights=w)) for i in range(len(qa))]
            g.nthreads = 1
            g.quantiles_m(X[:200], s)
            t1 = time.perf_counter()
            g.quantiles_m(X[:ntime], s)
            us = (time.perf_counter() - t1) / min(ntime, len(y)) * 1e6
            g.nthreads = NTHREADS
            res[f"{s}_{lab}"] = {"pinball": pin, "coverage": cov, "worst_cov_err": float(np.max(np.abs(
                np.asarray(cov) - qa))), "us_per_tree_1thr": us, "n": int(len(y))}
            print(lab, s, json.dumps({k: v for k, v in res[f"{s}_{lab}"].items() if k != "coverage"}), flush=True)
        res[f"{s}_student_teacher_mae"] = np.average(np.abs(Qs["dq"] - Qs["gq"]), axis=0, weights=w).tolist()
        print("student-teacher MAE by level", s, np.round(res[f"{s}_student_teacher_mae"], 4).tolist(), flush=True)
    v = {s: {"pin_ratio": res[f"{s}_dq"]["pinball"] / res[f"{s}_gq"]["pinball"],
             "cov_excess": res[f"{s}_dq"]["worst_cov_err"] - res[f"{s}_gq"]["worst_cov_err"],
             "cost_ratio": res[f"{s}_dq"]["us_per_tree_1thr"] / res[f"{s}_gq"]["us_per_tree_1thr"]}
         for s in ("neg", "pos")}
    ok = all(x["pin_ratio"] <= 1.005 and x["cov_excess"] <= 0.005 and x["cost_ratio"] <= 0.25 for x in v.values())
    json.dump({"rows": res, "verdict": v, "pass": ok}, open(os.path.join(gdir(split, DTAG), "dq_compare.json"), "w"),
              indent=1)
    print("VERDICT", json.dumps(v), "PASS" if ok else "FAIL", flush=True)


def dsubmit(split):
    logs = os.path.join(REPO, "logs")
    jd = os.path.join(F.TAB, "_jobs")
    me = os.path.abspath(__file__)
    head = ("#!/bin/bash\n#SBATCH --account=waldspektrum --partition=priority --qos=priority\n"
            "#SBATCH --cpus-per-task={c} --time={h:02d}:00:00\n#SBATCH --job-name={n} --output={o}\n{x}"
            "set -eu\nexport POLARS_MAX_THREADS={c} OMP_NUM_THREADS={c} SLURM_CPUS_PER_TASK={c}\n")
    pj = []
    for s in ("neg", "pos"):
        js = os.path.join(jd, f"dq_prep_{s}.jcf")
        open(js, "w").write(head.format(c=32, h=2, n=f"X-de-dq-prep-{s}", o=f"{logs}/X-de-dq-prep-{s}.%j.out", x="")
                            + f"{F.PY} -u {me} dprep --split {split} --sign {s}\necho '=== JOB DONE ==='\n")
        pj.append(os.popen(f"sbatch --parsable {js}").read().strip())
    tj = []
    for k, s in enumerate(("neg", "pos")):
        js = os.path.join(jd, f"dq_train_{s}.jcf")
        open(js, "w").write(
            head.format(c=8, h=4, n=f"X-de-dq-{s}", o=f"{logs}/X-de-dq-{s}.%A_%a.out",
                        x=f"#SBATCH --array=0-{len(QLEV) - 1} --dependency=afterok:{pj[k]}\n")
            + f"{F.PY} -u {me} dtrain --split {split} --sign {s} --level $SLURM_ARRAY_TASK_ID\n"
            + "echo '=== JOB DONE ==='\n")
        tj.append(os.popen(f"sbatch --parsable {js}").read().strip())
    js = os.path.join(jd, "dq_compare.jcf")
    open(js, "w").write(head.format(c=16, h=2, n="X-de-dq-cmp", o=f"{logs}/X-de-dq-cmp.%j.out",
                                    x=f"#SBATCH --dependency=afterok:{tj[0]}:{tj[1]}\n")
                        + f"{F.PY} -u {me} dcompare --split {split}\necho '=== JOB DONE ==='\n")
    print("dq jobs: prep", pj, "train", tj, "compare", os.popen(f"sbatch --parsable {js}").read().strip(), flush=True)


# ================================================================================================ the sampler
class GQ:
    def __init__(self, split="DEV-A", conformal=False, niter=None, levels=None, tag=None):
        """niter: predict with each head's first niter trees only (None = all; env GQ_NITER); levels: name in
        LEVELSETS or None = all 11 (env GQ_LEVELS) — the shrunk sampler of the "shrink" stage."""
        import lightgbm as lgb

        if niter is None and os.environ.get("GQ_NITER"):
            niter = int(os.environ["GQ_NITER"])
        if levels is None:
            levels = os.environ.get("GQ_LEVELS") or "11"
        keep = LEVELSETS[str(levels)]
        d = gdir(split, tag)
        self.d = d
        self.niter, self.levels = niter, str(levels)
        self.H = None
        self.b, self.base = {}, {}
        for s in ("neg", "pos"):
            self.b[s], self.base[s] = [], []
            for i in keep:
                nm = os.path.join(d, f"{s}_q{i:02d}")
                self.b[s].append(lgb.Booster(model_file=nm + ".txt"))
                m = json.load(open(nm + ".json"))
                self.base[s].append(m["base"])
                self.feats = m["features"]
                if m.get("init") == "mean_head" and self.H is None:
                    self.H = Hh.TabHeads.load(split, heads=["gmag_neg", "gmag_pos"])
        self.lv = np.asarray(QLEV)[keep]
        self.nthreads = NTHREADS
        self.off = {s: np.zeros(len(keep)) for s in ("neg", "pos")}
        if conformal:
            cj = json.load(open(os.path.join(d, "calib.json")))
            self.off = {s: np.asarray(cj[s]["offset"])[keep] for s in ("neg", "pos")}

    @classmethod
    def load(cls, split="DEV-A", conformal=False):
        return cls(split, conformal)

    def view(self, niter=None, levels="11") -> GQ:
        """a shallow copy predicting with the first niter trees of the heads in LEVELSETS[levels] (subset of self)."""
        import copy

        v = copy.copy(self)
        pos = [list(np.asarray(QLEV)[LEVELSETS[self.levels]]).index(QLEV[i]) for i in LEVELSETS[str(levels)]]
        v.b = {s: [self.b[s][j] for j in pos] for s in self.b}
        v.base = {s: [self.base[s][j] for j in pos] for s in self.base}
        v.off = {s: self.off[s][pos] for s in self.off}
        v.lv = self.lv[pos]
        v.niter, v.levels = niter, str(levels)
        return v

    def quantiles(self, X: pl.DataFrame, sign: str) -> np.ndarray:
        return self.quantiles_m(F.to_matrix(X, self.feats), sign)

    def quantiles_m(self, M: np.ndarray, sign: str) -> np.ndarray:
        Q = np.column_stack([b0 + b.predict(M, raw_score=True, num_threads=self.nthreads, num_iteration=self.niter)
                             for b, b0 in zip(self.b[sign], self.base[sign], strict=True)])
        if self.H is not None:  # residual heads ("rq"): add the L2 mean head at kappa 1
            self.H.nthreads = self.nthreads
            Q = Q + mean_head(self.H, sign, M, self.feats)[:, None]
        return np.sort(np.sort(Q, axis=1) + self.off[sign][None, :], axis=1)

    def inv(self, Q: np.ndarray, u: np.ndarray) -> np.ndarray:
        lv = self.lv
        u = np.clip(u, UCLIP, 1 - UCLIP)
        j = np.clip(np.searchsorted(lv, u) - 1, 0, len(lv) - 2)
        r = np.take_along_axis(Q, j[:, None], 1)[:, 0]
        s = np.take_along_axis(Q, (j + 1)[:, None], 1)[:, 0]
        return r + (s - r) * (u - lv[j]) / (lv[j + 1] - lv[j])

    def cdf(self, Q: np.ndarray, x: np.ndarray) -> np.ndarray:
        """exact inverse of inv() (u clipped the same way)."""
        lv = self.lv
        k = (Q <= x[:, None]).sum(1)
        j = np.clip(k - 1, 0, len(lv) - 2)
        r = np.take_along_axis(Q, j[:, None], 1)[:, 0]
        s = np.take_along_axis(Q, (j + 1)[:, None], 1)[:, 0]
        u = lv[j] + (x - r) * (lv[j + 1] - lv[j]) / np.maximum(s - r, 1e-12)
        return np.clip(u, UCLIP, 1 - UCLIP)

    def sample(self, X: pl.DataFrame, p: np.ndarray, u_s: np.ndarray, u_r: np.ndarray) -> np.ndarray:
        neg = u_s < p
        mag = np.zeros(X.height)
        for s, msk in (("neg", neg), ("pos", ~neg)):
            if msk.any():
                mag[msk] = self.inv(self.quantiles(X.filter(pl.Series(msk)), s), u_r[msk])
        return np.where(neg, -np.exp(mag), np.exp(mag))

    def pit(self, X: pl.DataFrame, g: np.ndarray, p: np.ndarray) -> np.ndarray:
        out = np.full(len(g), np.nan)
        for s in ("neg", "pos"):
            msk = (g < 0) if s == "neg" else (g > 0)
            if msk.any():
                c = self.cdf(self.quantiles(X.filter(pl.Series(msk)), s), np.log(np.abs(g[msk])))
                out[msk] = p[msk] * (1.0 - c) if s == "neg" else p[msk] + (1.0 - p[msk]) * c
        return out

    def pinball_pair(self, st, X: pl.DataFrame, g: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """mean pinball loss of log|g| over QLEV, conditional on the true sign: (this model, the old pooled sampler)."""
        H, k = st.H, st.k_g
        kk = "k1" if k != 0.0 else "k0"
        new, old = np.full(len(g), np.nan), np.full(len(g), np.nan)
        for s in ("neg", "pos"):
            msk = (g < 0) if s == "neg" else (g > 0)
            if not msk.any():
                continue
            Xs = X.filter(pl.Series(msk))
            y = np.log(np.abs(g[msk]))
            Qn = self.quantiles(Xs, s)
            m = H.raw(f"gmag_{s}", Xs, k)
            edges, res = H.resid[(s, kk)]
            qtab = np.array([np.quantile(r, self.lv) for r in res])
            Qo = m[:, None] + qtab[np.searchsorted(edges, m)]
            new[msk] = np.mean([pinball(Qn[:, i], y, a) for i, a in enumerate(self.lv)], axis=0)
            old[msk] = np.mean([pinball(Qo[:, i], y, a) for i, a in enumerate(self.lv)], axis=0)
        return new, old

    def sampler(self, st, sign_cal=False):
        """-> (p_neg(X), sample_G(X, u_s, u_r) -> (G, p)) closures over the stepper st. sign_cal: the gsign logit is
        Platt-recalibrated (a s + b, from sign_platt.json) instead of + logit_off_g."""
        if st.k_g == 0.0:
            raise ValueError("the quantile G sampler has no climate-blind (kappa = 0) variant")
        gq = self
        if sign_cal == "c2":  # per-counter Platt with a separate weather-booster scale (arm "gqsc2")
            bc2 = json.load(open(os.path.join(gdir(st.split), "sign_platt_c2.json")))["by_c"]
            a0c = np.array([bc2[str(k)]["a0"] for k in range(SIGNC_MAX + 1)])
            a1c = np.array([bc2[str(k)]["a1"] for k in range(SIGNC_MAX + 1)])
            b2c = np.array([bc2[str(k)]["b"] for k in range(SIGNC_MAX + 1)])

            def _p_neg(X):
                k = np.clip(np.rint(X["c_y"].cast(pl.Float64).to_numpy()), 0, SIGNC_MAX).astype(int)
                s0 = st.H.raw("gsign", X, 0.0)
                s1 = st.H.raw("gsign", X, st.k_g) - s0
                return ts.sigmoid(a0c[k] * s0 + a1c[k] * s1 + b2c[k])
        elif sign_cal in ("k", "kb"):  # gqsc + a streak-continuation residual booster on c_y >= 1 (explore_de_contin)
            import lightgbm as lgb

            bc = json.load(open(os.path.join(gdir(st.split), "sign_platt_c.json")))["by_c"]
            ac = np.array([bc[str(k)]["a"] for k in range(SIGNC_MAX + 1)])
            bcv = np.array([bc[str(k)]["b"] for k in range(SIGNC_MAX + 1)])
            arm = {"k": "W1", "kb": "WB"}[sign_cal]
            km = json.load(open(os.path.join(gdir(st.split), f"contin_{arm}.json")))
            kbst = lgb.Booster(model_file=os.path.join(gdir(st.split), f"contin_{arm}.txt"))

            def _p_neg(X):
                k = np.clip(np.rint(X["c_y"].cast(pl.Float64).to_numpy()), 0, SIGNC_MAX).astype(int)
                z = ac[k] * st.H.raw("gsign", X, st.k_g) + bcv[k]
                q = k >= 1
                if q.any():
                    if "cs_start" in km["features"] and "cs_start" not in X.columns:
                        # the cell-year covariates must count PRINTED LIVING trees (the rollout frame carries
                        # hidden and dead rows); only the one-step scorer, which attaches them, supports WB yet
                        raise NotImplementedError("arm WB needs cs_* columns attached by the caller")
                    z[q] += kbst.predict(F.to_matrix(X.filter(pl.Series(q)), km["features"]), raw_score=True)
                return ts.sigmoid(z)
        elif sign_cal == "c":  # per-counter Platt (arm "gqsc", sign_platt_c.json)
            bc = json.load(open(os.path.join(gdir(st.split), "sign_platt_c.json")))["by_c"]
            ac = np.array([bc[str(k)]["a"] for k in range(SIGNC_MAX + 1)])
            bcv = np.array([bc[str(k)]["b"] for k in range(SIGNC_MAX + 1)])

            def _p_neg(X):
                k = np.clip(np.rint(X["c_y"].cast(pl.Float64).to_numpy()), 0, SIGNC_MAX).astype(int)
                return ts.sigmoid(ac[k] * st.H.raw("gsign", X, st.k_g) + bcv[k])
        else:
            if sign_cal:
                pc = json.load(open(os.path.join(gdir(st.split), "sign_platt.json")))
                a_, b_ = pc["a"], pc["b"]
            else:
                a_, b_ = 1.0, st.cal["logit_off_g"]

            def _p_neg(X):
                return ts.sigmoid(a_ * st.H.raw("gsign", X, st.k_g) + b_)

        def _sample_G(X, u_s, u_r):
            p = _p_neg(X)
            return gq.sample(X, p, u_s, u_r), p

        return _p_neg, _sample_G

    def attach(self, st, sign_cal=False):
        """route st._sample_G through this model (instance attributes; for the one-step / chain scorers)."""
        st._p_neg, st._sample_G = self.sampler(st, sign_cal)
        st.gq = self
        return st


class DQ:
    """the distilled student: same sampling interface as GQ (inv / cdf / sample / pit come from GQ)."""

    def __init__(self, split="DEV-A"):
        import lightgbm as lgb

        d = gdir(split, DTAG)
        self.b = {s: [lgb.Booster(model_file=os.path.join(d, f"{s}_d{j:02d}.txt")) for j in range(len(QLEV))]
                  for s in ("neg", "pos")}
        self.feats = json.load(open(os.path.join(d, "pos_d00.json")))["features"]
        self.lv = np.asarray(QLEV)
        self.nthreads = NTHREADS

    inv, cdf, sample, pit, sampler, attach = GQ.inv, GQ.cdf, GQ.sample, GQ.pit, GQ.sampler, GQ.attach

    def quantiles(self, X: pl.DataFrame, sign: str) -> np.ndarray:
        return self.quantiles_m(F.to_matrix(X, self.feats), sign)

    def quantiles_m(self, M: np.ndarray, sign: str) -> np.ndarray:
        P = [b.predict(M, num_threads=self.nthreads) for b in self.b[sign]]
        gap = [np.maximum(np.exp(p) - GAP_EPS, 0.0) for p in P[1:]]  # gap[i] between levels i and i+1
        Q = np.empty((M.shape[0], len(QLEV)))
        Q[:, 5] = P[0]
        for i in range(6, len(QLEV)):
            Q[:, i] = Q[:, i - 1] + gap[i - 1]
        for i in range(4, -1, -1):
            Q[:, i] = Q[:, i + 1] - gap[i]
        return Q


_GQ: dict = {}


def load(split="DEV-A", conformal=False) -> GQ:
    key = (split, conformal, os.environ.get("GQ_NITER"), os.environ.get("GQ_LEVELS"))
    if key not in _GQ:
        _GQ[key] = GQ(split, conformal)
    return _GQ[key]


def shrink(split, nval=300_000, ntime=20_000):
    """truncation x level-subset scan on the validation fold (pre-registration: TS.md "SHRINKING the quantile G
    model"): mean pinball over all 11 QLEV, worst |coverage - alpha|, single-thread predict cost -> gq_shrink.json"""
    d = gdir(split)
    g = GQ(split)
    qa = np.asarray(QLEV)
    rows = []
    for s in ("neg", "pos"):
        va = np.load(os.path.join(d, f"{s}_va.npy"))
        idx = np.flatnonzero(va)
        idx = np.sort(np.random.default_rng(7).choice(idx, min(nval, idx.size), replace=False))
        X = np.asarray(np.load(os.path.join(d, f"{s}_X.npy"), mmap_mode="r")[idx], dtype=np.float64)
        y = np.load(os.path.join(d, f"{s}_y.npy"))[idx].astype(np.float64)
        w = np.load(os.path.join(d, f"{s}_w.npy"))[idx].astype(np.float64)
        for lev in ("11", "7", "5"):
            for k in (50, 100, 200, 400, 800, 1500, None):
                v = g.view(k, lev)
                t0 = time.time()
                Q = v.quantiles_m(X, s)
                Qa = np.column_stack([v.inv(Q, np.full(len(y), a)) for a in qa])
                pin = float(np.mean([np.average(pinball(Qa[:, i], y, a), weights=w) for i, a in enumerate(qa)]))
                cov = [float(np.average(y <= Qa[:, i], weights=w)) for i in range(len(qa))]
                v.nthreads = 1
                Xt = X[:ntime]
                v.quantiles_m(Xt[:200], s)
                t1 = time.perf_counter()
                v.quantiles_m(Xt, s)
                us = (time.perf_counter() - t1) / len(Xt) * 1e6
                r = {"sign": s, "levels": lev, "niter": k or 0, "pinball": pin,
                     "worst_cov_err": float(np.max(np.abs(np.asarray(cov) - qa))), "us_per_tree_1thr": us,
                     "n": int(len(y)), "t_eval_s": round(time.time() - t0, 1)}
                rows.append(r)
                print(json.dumps(r), flush=True)
    full = {s: next(r for r in rows if r["sign"] == s and r["levels"] == "11" and r["niter"] == 0)
            for s in ("neg", "pos")}
    for r in rows:
        f = full[r["sign"]]
        r["pin_ratio"] = r["pinball"] / f["pinball"]
        r["cov_excess"] = r["worst_cov_err"] - f["worst_cov_err"]
    ok = {}
    for lev in ("11", "7", "5"):
        for k in (50, 100, 200, 400, 800, 1500, 0):
            rr = [r for r in rows if r["levels"] == lev and r["niter"] == k]
            ok[(lev, k)] = (all(r["pin_ratio"] <= 1.005 and r["cov_excess"] <= 0.005 for r in rr),
                            sum(r["us_per_tree_1thr"] for r in rr) / 2)
    passing = sorted((c, key) for key, (p, c) in ok.items() if p)
    sel = {"levels": passing[0][1][0], "niter": passing[0][1][1], "us_per_tree": passing[0][0]} if passing else None
    out = {"rows": rows, "selected": sel, "rule": "pin_ratio <= 1.005 and cov_excess <= 0.005 for both signs"}
    json.dump(out, open(os.path.join(d, "gq_shrink.json"), "w"), indent=1)
    print("SELECTED", json.dumps(sel), flush=True)


class TabALG2HSGQ(tg2.TabALG2HS):
    """the g2hs coupled arm with the quantile G-magnitude sampler. kwargs gq_sign_cal (Platt sign, arm "gqs"; default
    on), gq_conformal (validation-fold offsets, arm "gqc"; default off). _sample_G is a METHOD (not an instance
    attribute) so a probe mixin placed before this class in the MRO still wraps it."""

    def __init__(self, gq_sign_cal: bool | str = True, gq_conformal: bool = False, **kw):
        super().__init__(**kw)
        # "c" = per-counter Platt (arm "gqsc"); env GQ_SIGN_CAL=c selects it without a new stepper class
        gq_sign_cal = os.environ.get("GQ_SIGN_CAL", gq_sign_cal)
        self.gq_sign_cal = gq_sign_cal if gq_sign_cal in ("c", "c2", "k", "kb") else bool(gq_sign_cal)
        self.gq_conformal = bool(gq_conformal)

    def init(self, state, ctx):
        super().init(state, ctx)
        self.gq = load(self.split, conformal=self.gq_conformal)
        self._gq_p, self._gq_sample = self.gq.sampler(self, self.gq_sign_cal)
        tr.log(f"TabALG2HSGQ: quantile G sampler, sign_cal={self.gq_sign_cal} conformal={self.gq_conformal}")

    def _sample_G(self, X, u_s, u_r):
        return self._gq_sample(X, u_s, u_r)


class TabALG2HSGQProbe(pr2._DumpMixin, TabALG2HSGQ):
    """the same with the per-tree dump of explore_de_tab_probe2 (same columns, same layout)."""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["prep", "train", "calib", "bench", "sign", "signc", "signc2", "submit", "shrink",
                                      "rprep", "rtrain", "rcompare", "rsubmit", "dprep", "dtrain", "dcompare",
                                      "dsubmit"])
    ap.add_argument("--split", default="DEV-A")
    ap.add_argument("--sign", choices=["neg", "pos"])
    ap.add_argument("--level", type=int)
    a = ap.parse_args()
    if a.stage == "prep":
        prep(a.split, a.sign)
    elif a.stage == "train":
        train(a.split, a.sign, a.level)
    elif a.stage == "calib":
        calib(a.split)
    elif a.stage == "sign":
        sign_platt(a.split)
    elif a.stage == "signc":
        sign_platt_c(a.split)
    elif a.stage == "signc2":
        sign_platt_c2(a.split)
    elif a.stage == "bench":
        bench(a.split)
    elif a.stage == "shrink":
        shrink(a.split)
    elif a.stage == "rprep":
        rprep(a.split, a.sign)
    elif a.stage == "rtrain":
        rtrain(a.split, a.sign, a.level)
    elif a.stage == "rcompare":
        rcompare(a.split)
    elif a.stage == "rsubmit":
        rsubmit(a.split)
    elif a.stage == "dprep":
        dprep(a.split, a.sign)
    elif a.stage == "dtrain":
        dtrain(a.split, a.sign, a.level)
    elif a.stage == "dcompare":
        dcompare(a.split)
    elif a.stage == "dsubmit":
        dsubmit(a.split)
    else:
        submit(a.split)


if __name__ == "__main__":
    main()
