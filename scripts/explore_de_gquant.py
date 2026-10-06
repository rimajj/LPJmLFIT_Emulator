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
import explore_de_tab_features as F  # noqa: E402
import explore_de_tab_g2 as tg2  # noqa: E402
import explore_de_tab_heads as Hh  # noqa: E402
import explore_de_tab_stepper as ts  # noqa: E402

QLEV = [0.005, 0.02, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.98, 0.995]
UCLIP = 1e-4
MAX_ROWS = int(os.environ.get("GQ_MAX_ROWS", "6000000"))
NTHREADS = int(os.environ.get("SLURM_CPUS_PER_TASK", "8"))
PARAMS = dict(objective="quantile", metric="quantile", learning_rate=0.1, num_leaves=63, min_data_in_leaf=1000,
              feature_fraction=0.8, bagging_fraction=0.7, bagging_freq=1, lambda_l2=1.0, max_bin=127, verbose=-1,
              seed=13)


def gdir(split):
    d = os.path.join(Hh.mdir(split), "gquant" + os.environ.get("GQ_TAG", ""))
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
    df = Hh.load_rows(split, "train", h["filt"], h["label"], MAX_ROWS, keep=feats + ["G_y1", "c_y1"])
    y = df["_y"].to_numpy().astype(np.float64)
    ok = np.isfinite(y)
    df, y = df.filter(pl.Series(ok)), y[ok]
    d = gdir(split)
    np.save(os.path.join(d, f"{sign}_X.npy"), F.to_matrix(df, feats))
    np.save(os.path.join(d, f"{sign}_y.npy"), y.astype(np.float32))
    np.save(os.path.join(d, f"{sign}_w.npy"), df["w_ip"].to_numpy().astype(np.float32))
    np.save(os.path.join(d, f"{sign}_va.npy"), df["fold"].to_numpy() == spec["val_fold"])
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


# ================================================================================================ the sampler
class GQ:
    def __init__(self, split="DEV-A", conformal=False):
        import lightgbm as lgb

        d = gdir(split)
        self.d = d
        self.b, self.base = {}, {}
        for s in ("neg", "pos"):
            self.b[s], self.base[s] = [], []
            for i in range(len(QLEV)):
                nm = os.path.join(d, f"{s}_q{i:02d}")
                self.b[s].append(lgb.Booster(model_file=nm + ".txt"))
                m = json.load(open(nm + ".json"))
                self.base[s].append(m["base"])
                self.feats = m["features"]
        self.lv = np.asarray(QLEV)
        self.nthreads = NTHREADS
        self.off = {s: np.zeros(len(QLEV)) for s in ("neg", "pos")}
        if conformal:
            cj = json.load(open(os.path.join(d, "calib.json")))
            self.off = {s: np.asarray(cj[s]["offset"]) for s in ("neg", "pos")}

    @classmethod
    def load(cls, split="DEV-A", conformal=False):
        return cls(split, conformal)

    def quantiles(self, X: pl.DataFrame, sign: str) -> np.ndarray:
        M = F.to_matrix(X, self.feats)
        Q = np.column_stack([b0 + b.predict(M, raw_score=True, num_threads=self.nthreads)
                             for b, b0 in zip(self.b[sign], self.base[sign], strict=True)])
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

    def attach(self, st, sign_cal=False):
        """route st._sample_G through this model. sign_cal: the gsign logit is Platt-recalibrated (a s + b, from
        sign_platt.json) instead of + logit_off_g."""
        if st.k_g == 0.0:
            raise ValueError("the quantile G sampler has no climate-blind (kappa = 0) variant")
        gq = self
        if sign_cal:
            pc = json.load(open(os.path.join(self.d, "sign_platt.json")))
            a_, b_ = pc["a"], pc["b"]
        else:
            a_, b_ = 1.0, st.cal["logit_off_g"]

        def _p_neg(X):
            return ts.sigmoid(a_ * st.H.raw("gsign", X, st.k_g) + b_)

        def _sample_G(X, u_s, u_r):
            p = _p_neg(X)
            return gq.sample(X, p, u_s, u_r), p

        st._p_neg = _p_neg

        st._sample_G = _sample_G
        st.gq = gq
        return st


_GQ: dict = {}


def load(split="DEV-A", conformal=False) -> GQ:
    if (split, conformal) not in _GQ:
        _GQ[(split, conformal)] = GQ(split, conformal)
    return _GQ[(split, conformal)]


class TabALG2HSGQ(tg2.TabALG2HS):
    """the g2hs coupled arm with the quantile G-magnitude sampler."""

    def init(self, state, ctx):
        super().init(state, ctx)
        load(self.split).attach(self)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["prep", "train", "calib", "bench", "sign", "submit"])
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
    elif a.stage == "bench":
        bench(a.split)
    else:
        submit(a.split)


if __name__ == "__main__":
    main()
