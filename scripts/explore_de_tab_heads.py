#!/usr/bin/env python3
"""explore_de_tab_heads.py — LINE X, Germany data-driven emulator, design track A-TAB, items A2-A5:
the per-tree gradient-boosted transition HEADS, their held-out gates, and the cheap per-tree PREDICT API a rollout
stepper calls.

Every head is two LightGBM boosters: B0 on the state features (explore_de_tab_features.B0 + head extras), then B1
(linear_tree=True) on the climate features (B1 + Type, log_agb) fitted to B0's residual through init_score.
prediction (raw score) = B0 + kappa * B1; kappa = 0 is the climate-blind arm.

HEADS (training rows = A1's stratified sample, inverse-probability weights; early stopping on the split's
validation fold; held-out gates on A1's unweighted eval samples)
  gsign     A2  P(G_{y+1} < 0)                         present stems, G sign known (censor != npp_sat)
  gmag_neg  A2  log|G_{y+1}| given G < 0 (L2)          + empirical residuals per predicted-value decile (OOF)
  gmag_pos  A2  log|G_{y+1}| given G > 0 (L2)          counter c_{y+1} by the rule (rl.counter_step; c = 5 kills)
  dagb      A3  dlog agb  | G_{y+1}, c_{y+1} (Huber)    present stems incl. flagged dead
  dvegc     A3  dlog vegc | G_{y+1}, c_{y+1} (Huber)    + per-tree AR(1) residual, rho/sigma per (Type, agb decile)
  dlai, dfpc, dd95  A3  dlog LAI / fpc_ind / D95 | G, c, dlog agb, dlog vegc (<= 100 trees, 31 leaves)
  height    A3  rule allometry (rl.predict_height[_ext]) of the new agb + a fixed per-tree offset (no booster)
  grass     A3  next-year grass fpc / LAI / agb of the patch | tree cover change + climate (patch rows)
  surv      A4  P(flagged dead at y+1) for present stems with c_{y+1} < 5 (c = 5 = rule kill); fire inside
  surv_phys A4  same + the rule hazard of G_{y+1}, c_{y+1}, Age, own-PFT stress days as a feature
  rtype     A5  recruit Type, multiclass over the tree PFTs with recruits (cell / patch composition, climate)
  traits    A5  recruit traits: donor mixture (w: a living same-type stem of the cell, p ~ agb^a, each trait
                x (1 + s N(0,1)) with the rule's reflection and the Dec-2025 bound quirk; 1-w: uniform on the
                Type's interval); w, a, s per Type by minimum KS distance to the training recruits

OUTPUT  /p/tmp/jamirp/X_de/tab/models/<split>/<head>_B0.txt, _B1.txt, <head>_meta.json, tables (*.npz / .json)
        reports /p/tmp/jamirp/X_de/_reports/r2_A2.json ... r2_A5.json
STAGES  train --head H [H ...] | eval --item A2|A3|A4|A5 | contrast | traits | apitest | submit --what ...
PREDICT API  TabHeads.load(split) -> .features(state, clim_y, clim_y1, gcm) and .transition(...) — see the class.
CO2 and wind are never inputs; nothing Germany-specific is hard-coded beyond the PFT sets read from the data.
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
import explore_de_sh_rules as rl  # noqa: E402
import explore_de_sh_trans as tr  # noqa: E402
import explore_de_tab_features as F  # noqa: E402

XDE = tr.XDE
TAB = F.TAB
REPORTS = os.path.join(XDE, "_reports")
NTHREADS = int(os.environ.get("SLURM_CPUS_PER_TASK", "8"))
SMOKE = os.environ.get("TAB_SMOKE") == "1"

P0 = dict(learning_rate=0.08, num_leaves=127, min_data_in_leaf=200, feature_fraction=0.8, bagging_fraction=0.7,
          bagging_freq=1, lambda_l2=1.0, max_bin=127, verbose=-1, seed=7)
P1 = dict(learning_rate=0.05, num_leaves=15, min_data_in_leaf=2000, linear_tree=True, linear_lambda=1.0,
          feature_fraction=1.0, max_bin=127, verbose=-1, seed=11)
GROWTH_EXTRA = ["G_y1", "c_y1"]
CLOSURE_EXTRA = ["G_y1", "c_y1", "dlog_agb_y1", "dlog_vegc_y1"]


def present(df):
    return df.filter(pl.col("fate_y1") <= 1)


HEADS = {
    "gsign": dict(item="A2", obj="binary", extra=[], label=(pl.col("G_y1") < 0).cast(pl.Float32),
                  filt=(pl.col("fate_y1") <= 1) & (pl.col("cenG_y1") != 3), rounds=(3000, 2000), max_rows=20_000_000),
    "gmag_neg": dict(item="A2", obj="regression", extra=[], label=pl.col("G_y1").abs().log(),
                     filt=(pl.col("fate_y1") <= 1) & (pl.col("cenG_y1") == 0) & (pl.col("G_y1") < 0),
                     rounds=(3000, 2000), max_rows=20_000_000),
    "gmag_pos": dict(item="A2", obj="regression", extra=[], label=pl.col("G_y1").abs().log(),
                     filt=(pl.col("fate_y1") <= 1) & (pl.col("cenG_y1") == 0) & (pl.col("G_y1") > 0),
                     rounds=(3000, 2000), max_rows=16_000_000),
    "dagb": dict(item="A3", obj="huber", extra=GROWTH_EXTRA, label=(pl.col("agb_y1") / pl.col("agb")).log(),
                 filt=(pl.col("fate_y1") <= 1), rounds=(3000, 2000), max_rows=12_000_000),
    "dvegc": dict(item="A3", obj="huber", extra=GROWTH_EXTRA, label=(pl.col("vegc_y1") / pl.col("vegc")).log(),
                  filt=(pl.col("fate_y1") <= 1), rounds=(3000, 2000), max_rows=12_000_000),
    "dlai": dict(item="A3", obj="regression", extra=CLOSURE_EXTRA, label=(pl.col("LAI_y1") / pl.col("LAI")).log(),
                 filt=(pl.col("fate_y1") <= 1), rounds=(100, 50), small=True, max_rows=8_000_000),
    "dfpc": dict(item="A3", obj="regression", extra=CLOSURE_EXTRA,
                 label=(pl.col("fpc_ind_y1") / pl.col("fpc_ind")).log(),
                 filt=(pl.col("fate_y1") <= 1), rounds=(100, 50), small=True, max_rows=8_000_000),
    "dd95": dict(item="A3", obj="regression", extra=CLOSURE_EXTRA, label=(pl.col("D95_y1") / pl.col("D95")).log(),
                 filt=(pl.col("fate_y1") <= 1), rounds=(100, 50), small=True, max_rows=8_000_000),
    "surv": dict(item="A4", obj="binary", extra=["G_y1", "c_y1", "resist"],
                 label=(pl.col("fate_y1") == 1).cast(pl.Float32),
                 filt=(pl.col("fate_y1") <= 1) & (pl.col("c_y1") < 5), rounds=(3000, 2000), max_rows=20_000_000),
    "surv_phys": dict(item="A4", obj="binary", extra=["G_y1", "c_y1", "resist", "h_phys"],
                      label=(pl.col("fate_y1") == 1).cast(pl.Float32),
                      filt=(pl.col("fate_y1") <= 1) & (pl.col("c_y1") < 5), rounds=(3000, 2000),
                      max_rows=20_000_000),
}


def status(item: str, msg: str):
    p = os.path.join(XDE, "_status", f"{item}.md")
    line = f"- {time.strftime('%Y-%m-%d %H:%M')} {'[smoke, code path only] ' if SMOKE else ''}{msg}"
    with open(p, "a") as fh:
        fh.write(line + "\n")
    print(line, flush=True)


def mdir(split):
    d = os.path.join(TAB, "models_smoke" if os.environ.get("TAB_SMOKE") == "1" else "models", split)
    os.makedirs(d, exist_ok=True)
    return d


# ------------------------------------------------------------------------------------------------ next-state cols
def add_next(df, P=None):
    """Next-year quantities a head conditions on (true values in training; sampled ones in the rollout) + the rule
    hazard feature of the A-L+phys arm. Applied after F.assemble()."""
    P = rl.load_params() if P is None else P
    ex = []
    names = df.collect_schema().names() if isinstance(df, pl.LazyFrame) else df.columns
    if "agb_y1" in names:
        ex += [(pl.col("agb_y1") / pl.col("agb")).log().cast(pl.Float32).alias("dlog_agb_y1"),
               (pl.col("vegc_y1") / pl.col("vegc")).log().cast(pl.Float32).alias("dlog_vegc_y1")]
    df = df.with_columns(ex) if ex else df
    return df


def h_phys(typ, wooddens, age_y, G_y1, c_y1, tstress_own_y1, P=None):
    """Rule hazard of y+1 from the carried/sampled hidden state (the C's mort_npp + mort_age + mort_temp, capped
    at 1). age_y = printed Age of y = the pre-increment age of year y+1. Water stress is not carried by A-TAB."""
    P = rl.load_params() if P is None else P
    mm = rl.mort_max_of(wooddens, typ, P)
    mn = rl.mort_npp_of(np.nan_to_num(G_y1), c_y1, mm, None, P)
    ma = rl.mort_age_of(age_y, typ, P)
    mt = rl.mort_temp_of(np.nan_to_num(tstress_own_y1), typ, P)
    return np.minimum(1.0, mn + ma + mt).astype(np.float32)


def with_hphys(df: pl.DataFrame, P=None) -> pl.DataFrame:
    return df.with_columns(pl.Series("h_phys", h_phys(df["Type"].to_numpy(), df["Wooddens"].to_numpy(),
                                                      df["Age"].to_numpy(), df["G_y1"].to_numpy(),
                                                      df["c_y1"].to_numpy(), df["tstress_own_y1"].to_numpy(), P)))


# ------------------------------------------------------------------------------------------------ data loading
def sample_files(split, which):
    base = os.path.join(F.SAMPLES, split)
    if which == "train":
        return sorted(glob.glob(os.path.join(base, "train", "*", "*.parquet")))
    return sorted(glob.glob(os.path.join(base, "eval", which, "*", "*.parquet")))


BASE_KEEP = ["member", "gcm", "traj", "seed", "Year", "u_hash", "w_ip", "stratum", "fold", "agb", "vegc", "Height",
             "LAI", "fpc_ind", "D95", "Wooddens", "SLA", "Age", "c_y", "G_y", "cenG_y1", "fate_y1", "d_agb_prev",
             "tstress_own_y1", "Cell", "Patch", "Type", "ID", "sla_i", "wd_i"]


def load_rows(split, which, filt, label=None, max_rows=None, extra_cols=(), need_hphys=False,
              keep=None) -> pl.DataFrame:
    """Rows of the A1 sample (`which` = 'train' or an eval set), filtered, assembled. Training rows above
    `max_rows` are thinned on u_hash inside the rest stratum first (weights rescaled = inverse probability)."""
    files = sample_files(split, which)
    assert files, f"no A1 samples for {split}/{which}"
    lf = pl.scan_parquet(files).filter(filt)
    if max_rows is not None and which == "train":
        cnt = lf.group_by("stratum").agg(pl.len()).collect()
        n1 = int(cnt.filter(pl.col("stratum") == 1)["len"].sum())
        n0 = int(cnt.filter(pl.col("stratum") == 0)["len"].sum())
        if n0 + n1 > max_rows:
            if n1 < max_rows:  # thin the rest stratum (u_hash < REST_FRAC by construction)
                q = (max_rows - n1) / max(n0, 1)
                lf = lf.filter((pl.col("stratum") == 1) | (pl.col("u_hash") < F.REST_FRAC * q)).with_columns(
                    w_ip=pl.when(pl.col("stratum") == 1).then(pl.col("w_ip")).otherwise(pl.col("w_ip") / q))
            else:  # thin both strata by tree (u_hash is constant over a tree's life)
                q = max_rows / (n0 + n1)
                lf = lf.filter(((pl.col("stratum") == 1) & (pl.col("u_hash") < q))
                               | ((pl.col("stratum") == 0) & (pl.col("u_hash") < F.REST_FRAC * q))).with_columns(
                    w_ip=pl.col("w_ip") / q)
    lf = add_next(F.assemble(lf))
    if label is not None:
        lf = lf.with_columns(label.cast(pl.Float32).alias("_y"))
    if keep is not None:
        cols = list(dict.fromkeys(list(keep) + BASE_KEEP + list(extra_cols) + (["_y"] if label is not None else [])))
        names = lf.collect_schema().names()
        lf = lf.select([c for c in cols if c in names])
    df = lf.collect()
    if need_hphys:
        df = with_hphys(df)
    return df


def head_features(name):
    h = HEADS[name]
    return F.B0 + h["extra"], F.B1_IN


def cat_idx(cols):
    return [i for i, c in enumerate(cols) if c in F.CAT]


# ------------------------------------------------------------------------------------------------ two-stage fit
def fit_two_stage(f0, f1, X0, X1, y, w, tr_m, va_m, obj, rounds, small=False, num_class=None, extra_params=None):
    import lightgbm as lgb
    p0 = dict(P0, objective=obj, num_threads=NTHREADS)
    p1 = dict(P1, objective=obj, num_threads=NTHREADS)
    if small:
        p0.update(num_leaves=31, learning_rate=0.15)
        p1.update(learning_rate=0.1)
    if num_class:
        p0["num_class"] = p1["num_class"] = num_class
    if extra_params:
        p0.update(extra_params)
        p1.update(extra_params)
    d0 = lgb.Dataset(X0[tr_m], y[tr_m], weight=w[tr_m], feature_name=f0, categorical_feature=cat_idx(f0),
                     free_raw_data=True)
    v0 = lgb.Dataset(X0[va_m], y[va_m], weight=w[va_m], reference=d0)
    t0 = time.time()
    b0 = lgb.train(p0, d0, num_boost_round=rounds[0], valid_sets=[v0], valid_names=["val"],
                   callbacks=[lgb.early_stopping(40, verbose=False), lgb.log_evaluation(100)])
    t_b0 = time.time() - t0
    s0 = b0.predict(X0, raw_score=True, num_iteration=b0.best_iteration)
    del d0, v0
    d1 = lgb.Dataset(X1[tr_m], y[tr_m], weight=w[tr_m], init_score=_flat(s0[tr_m]), feature_name=f1,
                     categorical_feature=cat_idx(f1), free_raw_data=False)
    v1 = lgb.Dataset(X1[va_m], y[va_m], weight=w[va_m], init_score=_flat(s0[va_m]), reference=d1)
    t0 = time.time()
    b1 = lgb.train(p1, d1, num_boost_round=rounds[1], valid_sets=[v1], valid_names=["val"],
                   callbacks=[lgb.early_stopping(30, verbose=False), lgb.log_evaluation(50)])
    t_b1 = time.time() - t0
    return b0, b1, s0, {"b0_best_iter": int(b0.best_iteration), "b1_best_iter": int(b1.best_iteration),
                        "b0_val": _scores(b0), "b1_val": _scores(b1), "t_b0_s": round(t_b0), "t_b1_s": round(t_b1)}


def _flat(s):
    return s.ravel(order="F") if s.ndim == 2 else s


def _scores(b):
    try:
        return {k: float(v) for k, v in b.best_score["val"].items()}
    except Exception:
        return {}


def gains(b, names):
    g = b.feature_importance("gain")
    tot = float(g.sum()) or 1.0
    order = np.argsort(-g)
    return {names[i]: round(float(g[i]) / tot, 5) for i in order}


def save_head(split, name, b0, b1, meta):
    d = mdir(split)
    b0.save_model(os.path.join(d, f"{name}_B0.txt"), num_iteration=b0.best_iteration)
    b1.save_model(os.path.join(d, f"{name}_B1.txt"), num_iteration=b1.best_iteration)
    json.dump(meta, open(os.path.join(d, f"{name}_meta.json"), "w"), indent=1)


def train_head(split, name):
    spec = json.load(open(os.path.join(F.SAMPLES, split, "split.json")))
    h = dict(HEADS[name])
    if SMOKE:  # code-path check only: tiny sample, few rounds, separate model dir
        h.update(max_rows=300_000, rounds=(30, 10))
    f0, f1 = head_features(name)
    t0 = time.time()
    keep = [c for c in f0 + f1 if c != "h_phys"] + ["G_y1", "c_y1", "agb_y1", "vegc_y1"]
    df = load_rows(split, "train", h["filt"], h["label"], h["max_rows"], need_hphys=("h_phys" in h["extra"]),
                   keep=keep)
    y = df["_y"].to_numpy().astype(np.float64)
    ok = np.isfinite(y)
    df = df.filter(pl.Series(ok))
    y = y[ok]
    w = df["w_ip"].to_numpy().astype(np.float64)
    va = df["fold"].to_numpy() == spec["val_fold"]
    trm = ~va
    X0 = F.to_matrix(df, f0)
    X1 = F.to_matrix(df, f1)
    print(f"{name}: {df.height} rows ({trm.sum()} train / {va.sum()} val), load {time.time() - t0:.0f} s",
          flush=True)
    extra = {}
    if h["obj"] == "huber":
        med = np.median(y)
        mad = np.median(np.abs(y - med)) * 1.4826
        extra["alpha"] = float(max(1.345 * mad, 1e-4))
    b0, b1, s0, info = fit_two_stage(f0, f1, X0, X1, y, w, trm, va, h["obj"], h["rounds"], h.get("small", False),
                                     extra_params=extra)
    s1 = b1.predict(X1, raw_score=True)
    meta = {"head": name, "split": split, "objective": h["obj"], "features_B0": f0, "features_B1": f1,
            "n_rows": int(df.height), "n_train": int(trm.sum()), "n_val": int(va.sum()),
            "max_rows": h["max_rows"], "weighted_rows": float(w.sum()), "params_extra": extra, **info,
            "gain_B0": gains(b0, f0), "gain_B1": gains(b1, f1)}
    # OOF (validation fold) side tables
    oof = df.filter(pl.Series(va)).select(["member", "Year", "u_hash", "w_ip", "stratum"] + tr.KEY
                                           + ["agb", "_y"]).with_columns(
        p0=pl.Series(s0[va].astype(np.float32)), p1=pl.Series((s0[va] + s1[va]).astype(np.float32)))
    oof.write_parquet(os.path.join(mdir(split), f"{name}_oof.parquet"))
    if name.startswith("gmag"):
        meta["residuals"] = residual_table(split, name, oof)
    if name in ("dagb", "dvegc"):
        meta["ar"] = ar_table(split, name, oof)
    save_head(split, name, b0, b1, meta)
    status(h["item"], f"train {split} {name}: {df.height} rows, B0 {info['b0_best_iter']} it ({info['t_b0_s']} s) "
                      f"val {info['b0_val']}, B1 {info['b1_best_iter']} it ({info['t_b1_s']} s) val {info['b1_val']}")
    return meta


def residual_table(split, name, oof: pl.DataFrame, nd=10, cap=20000) -> dict:
    """Empirical residuals of log|G| per decile of the predicted value (OOF rows, resampled with the inverse-
    probability weights so the stored residuals are an unweighted-population sample). One table per kappa."""
    rng = np.random.default_rng(3)
    out = {}
    for k, col in (("k1", "p1"), ("k0", "p0")):
        p = oof[col].to_numpy().astype(np.float64)
        r = oof["_y"].to_numpy().astype(np.float64) - p
        w = oof["w_ip"].to_numpy().astype(np.float64)
        edges = np.quantile(p, np.linspace(0, 1, nd + 1)[1:-1])
        b = np.searchsorted(edges, p)
        res = {}
        for d in range(nd):
            m = b == d
            if not m.any():
                res[d] = np.zeros(1, np.float32)
                continue
            pi = w[m] / w[m].sum()
            res[d] = rng.choice(r[m], size=min(cap, int(m.sum())), replace=True, p=pi).astype(np.float32)
        np.savez(os.path.join(mdir(split), f"{name}_resid_{k}.npz"), edges=edges,
                 **{f"d{d}": v for d, v in res.items()})
        out[k] = {"edges": edges.tolist(), "sd_by_decile": [float(np.std(res[d])) for d in range(nd)],
                  "smear_by_decile": [float(np.mean(np.exp(res[d]))) for d in range(nd)]}
    return out


def ar_table(split, name, oof: pl.DataFrame, nd=10) -> dict:
    """Per-tree AR(1) of the growth residual from OUT-OF-FOLD residuals: the validation fold's trees with
    u_hash < REST_FRAC (complete trajectories by construction of the A1 sample). rho, sigma per (Type, agb decile)."""
    o = oof.filter(pl.col("u_hash") < F.REST_FRAC).with_columns(e=(pl.col("_y") - pl.col("p1")).cast(pl.Float64))
    nxt = o.select(["member"] + tr.KEY + [(pl.col("Year") - 1).cast(pl.Int16).alias("Year"),
                                           pl.col("e").alias("e1")])
    J = o.join(nxt, on=["member"] + tr.KEY + ["Year"], how="inner")
    types = sorted(o["Type"].unique().to_list())
    edges, rho, sig, nn = {}, {}, {}, {}
    for t in types:
        a = o.filter(pl.col("Type") == t)["agb"].to_numpy().astype(np.float64)
        ed = np.quantile(np.log(a), np.linspace(0, 1, nd + 1)[1:-1]) if len(a) > nd else np.zeros(nd - 1)
        edges[t] = ed
        ot = o.filter(pl.col("Type") == t)
        bo = np.searchsorted(ed, np.log(ot["agb"].to_numpy().astype(np.float64)))
        et = ot["e"].to_numpy()
        jt = J.filter(pl.col("Type") == t)
        bj = np.searchsorted(ed, np.log(jt["agb"].to_numpy().astype(np.float64)))
        e0, e1 = jt["e"].to_numpy(), jt["e1"].to_numpy()
        rho[t], sig[t], nn[t] = [], [], []
        for d in range(nd):
            m = bj == d
            sd = float(np.std(et[bo == d])) if (bo == d).sum() > 10 else float(np.std(et))
            r = float(np.corrcoef(e0[m], e1[m])[0, 1]) if m.sum() > 30 else float(np.corrcoef(e0, e1)[0, 1])
            rho[t].append(float(np.clip(r, -0.99, 0.99)))
            sig[t].append(sd)
            nn[t].append(int(m.sum()))
    tab = {"types": types, "edges": {str(t): edges[t].tolist() for t in types},
           "rho": {str(t): rho[t] for t in types}, "sigma": {str(t): sig[t] for t in types},
           "n_pairs": {str(t): nn[t] for t in types}, "n_pairs_total": int(J.height),
           "rho_pooled": float(np.corrcoef(J["e"].to_numpy(), J["e1"].to_numpy())[0, 1])}
    json.dump(tab, open(os.path.join(mdir(split), f"{name}_ar.json"), "w"), indent=1)
    return {k: v for k, v in tab.items() if k in ("rho_pooled", "n_pairs_total")}


# ------------------------------------------------------------------------------------------------ grass head
GRASS_STATE = ["grass8_fpc_y", "grass8_LAI_y", "grass8_agb_y", "sum_fpc_y", "n_live_y", "sum_agb_y", "d_sum_fpc",
               "frac_loss_lag0", "frac_loss_lag1", "frac_loss_lag2", "soil_code"] + [f"c85_{f}" for f in F.C85_F]
GRASS_CLIM = [f"a_{f}_y1" for f in F.CLIM_F] + [f"{f}_y1" for f in F.ABS_Y1]


def grass_frame(split, which, members, cells, frac=0.25):
    """Patch rows: next-year grass of the patch given its state at y, the tree cover change y -> y+1 (known
    after the tree step in a rollout) and the climate of y+1. Patches thinned on a (Cell, Patch) hash."""
    parts = []
    gcm_of = {}
    mem = tr.registry()[0]
    for m in members:
        gcm_of[m] = tr.member_row(mem, m)["gcm"]
        fs = sorted(glob.glob(os.path.join(F.PATCHT, F.CELLSET, m, "cb=*", "y*.parquet")))
        lf = pl.scan_parquet(fs).filter(pl.col("Cell").is_in(cells)).filter(
            ((pl.col("Cell").cast(pl.Int64) * 7919 + pl.col("Patch").cast(pl.Int64) * 104729) % 1000) < frac * 1000)
        cols = ["member", "gcm", "traj", "seed", "Year", "Cell", "Patch", "grass8_fpc_y", "grass8_LAI_y",
                "grass8_agb_y", "sum_fpc_y", "n_live_y", "sum_agb_y", "frac_loss_lag0", "frac_loss_lag1",
                "frac_loss_lag2"]
        d = lf.select(cols).collect()
        n1 = d.select("Cell", "Patch", (pl.col("Year") - 1).cast(pl.Int16).alias("Year"),
                      pl.col("grass8_fpc_y").alias("g_fpc_y1"), pl.col("grass8_LAI_y").alias("g_LAI_y1"),
                      pl.col("grass8_agb_y").alias("g_agb_y1"), pl.col("sum_fpc_y").alias("sum_fpc_y1"))
        d = d.join(n1, on=["Cell", "Patch", "Year"], how="inner")
        parts.append(d)
    D = pl.concat(parts).with_columns(d_sum_fpc=pl.col("sum_fpc_y1") - pl.col("sum_fpc_y"))
    D = tr.join_climate(D, cols=[f"anom_{f}" for f in F.CLIM_F] + F.ABS_Y1, years=("y1",), ext=True)
    D = D.with_columns(*[pl.col(f"anom_{f}_y1").alias(f"a_{f}_y1") for f in F.CLIM_F])
    D = pl.concat([D.filter(pl.col("gcm") == g).join(F.statics(g), on="Cell", how="left")
                   for g in sorted(set(gcm_of.values()))])
    return D


def train_grass(split):
    import lightgbm as lgb
    spec = json.load(open(os.path.join(F.SAMPLES, split, "split.json")))
    D = grass_frame(split, "train", spec["train"], spec["cells_train"])
    folds = pl.read_parquet(os.path.join(tr.REG, "folds.parquet")).select(pl.col("Cell").cast(pl.Int16), "fold")
    D = D.join(folds, on="Cell", how="left")
    va = D["fold"].to_numpy() == spec["val_fold"]
    X0 = F.to_matrix(D, GRASS_STATE)
    X1 = F.to_matrix(D, GRASS_CLIM + ["sum_fpc_y"])
    meta = {"head": "grass", "n_rows": D.height, "targets": {}}
    for tgt in ("g_fpc_y1", "g_LAI_y1", "g_agb_y1"):
        y = D[tgt].to_numpy().astype(np.float64)
        w = np.ones_like(y)
        b0, b1, s0, info = fit_two_stage(GRASS_STATE, GRASS_CLIM + ["sum_fpc_y"], X0, X1, y, w, ~va, va,
                                         "regression", (400, 100), small=False)
        nm = f"grass_{tgt}"
        save_head(split, nm, b0, b1, {"head": nm, "features_B0": GRASS_STATE,
                                      "features_B1": GRASS_CLIM + ["sum_fpc_y"], **info,
                                      "gain_B0": gains(b0, GRASS_STATE)})
        meta["targets"][tgt] = info
    vals = json.dumps({k: v["b0_val"] for k, v in meta["targets"].items()})
    status("A3", f"train {split} grass: {D.height} patch rows; {vals}")
    _ = lgb
    return meta


# ------------------------------------------------------------------------------------------------ recruit Type
RT_B0 = None  # set in rtype_features()


def rtype_features():
    cols = F.recruit_cols()
    clim = [c for c in cols if c.endswith("_y1") and not c.startswith("elig") and c != "n_elig_y1"]
    b0 = [c for c in cols if c not in clim]
    return b0, clim


def train_rtype(split, max_rows=3_000_000):
    spec = json.load(open(os.path.join(F.SAMPLES, split, "split.json")))
    fs = glob.glob(os.path.join(F.SAMPLES, split, "recruits", "train", "*.parquet"))
    D = pl.read_parquet(fs).filter(pl.col("Type").is_in(F.RECR_TYPES))
    if D.height > max_rows:
        D = D.filter(pl.col("u_rec") < max_rows / D.height)
    D = F.recruit_features(D)
    b0, b1 = rtype_features()
    lab = np.searchsorted(F.RECR_TYPES, D["Type"].to_numpy()).astype(np.float64)
    va = D["fold"].to_numpy() == spec["val_fold"]
    X0 = F.to_matrix(D, b0)
    X1 = F.to_matrix(D, b1)
    b0m, b1m, s0, info = fit_two_stage(b0, b1, X0, X1, lab, np.ones_like(lab), ~va, va, "multiclass", (800, 200),
                                       num_class=len(F.RECR_TYPES))
    save_head(split, "rtype", b0m, b1m, {"head": "rtype", "classes": F.RECR_TYPES, "features_B0": b0,
                                         "features_B1": b1, "n_rows": D.height, **info,
                                         "gain_B0": gains(b0m, b0), "gain_B1": gains(b1m, b1)})
    status("A5", f"train {split} rtype: {D.height} recruits, B0 {info['b0_best_iter']} it val {info['b0_val']}, "
                 f"B1 {info['b1_best_iter']} it val {info['b1_val']}")


# ================================================================================================ PREDICT API
class TabHeads:
    """The cheap per-tree predict API of A-TAB. Load once; every call is vectorised over the trees of a chunk.

        H = TabHeads.load("DEV-A", kappa=1.0)
        X = H.features(state, clim_y, clim_y1, gcm)        # polars frame, one row per state tree (hidden incl.)
        out = H.transition(X, state, rand, year)          # dict: next-year tree fields + isdead + aux updates
    The pieces transition() chains are public: p_gneg, sample_G, counter, growth (+ AR), closures, height,
    p_death, recruit_type_probs, recruit_traits, grass. kappa scales every climate booster (0 = climate-blind)."""

    def __init__(self, split, kappa=1.0, heads=None):
        import lightgbm as lgb
        self.split, self.kappa = split, float(kappa)
        self.d = mdir(split)
        self.P = rl.load_params()
        self.m = {}
        for name in heads or list(HEADS) + ["rtype", "grass_g_fpc_y1", "grass_g_LAI_y1", "grass_g_agb_y1"]:
            fb0 = os.path.join(self.d, f"{name}_B0.txt")
            if not os.path.exists(fb0):
                continue
            meta = json.load(open(os.path.join(self.d, f"{name}_meta.json")))
            self.m[name] = (lgb.Booster(model_file=fb0), lgb.Booster(model_file=os.path.join(self.d, f"{name}_B1.txt")),
                            meta)
        self.resid = {}
        for s in ("neg", "pos"):
            for k in ("k1", "k0"):
                f = os.path.join(self.d, f"gmag_{s}_resid_{k}.npz")
                if os.path.exists(f):
                    z = np.load(f)
                    self.resid[(s, k)] = (z["edges"], [z[f"d{d}"] for d in range(len(z["edges"]) + 1)])
        self.ar = {}
        for g in ("dagb", "dvegc"):
            f = os.path.join(self.d, f"{g}_ar.json")
            if os.path.exists(f):
                self.ar[g] = json.load(open(f))
        tf = os.path.join(self.d, "traits_fit.json")
        self.traits_fit = json.load(open(tf)) if os.path.exists(tf) else None
        self.allom = rl.load_allometry(split, ext=False)
        self.allom_ext = rl.load_allometry(split, ext=True)
        self.nthreads = NTHREADS

    @classmethod
    def load(cls, split="DEV-A", kappa=1.0, heads=None):
        return cls(split, kappa, heads)

    # ---------------------------------------------------------------- features
    def features(self, state, clim_y, clim_y1, gcm) -> pl.DataFrame:
        return F.assemble(F.roster_raw(state, clim_y, clim_y1, gcm), self.P)

    def raw(self, name, X: pl.DataFrame, kappa=None) -> np.ndarray:
        b0, b1, meta = self.m[name]
        k = self.kappa if kappa is None else kappa
        s = b0.predict(F.to_matrix(X, meta["features_B0"]), raw_score=True, num_threads=self.nthreads)
        if k != 0.0:
            s = s + k * b1.predict(F.to_matrix(X, meta["features_B1"]), raw_score=True, num_threads=self.nthreads)
        return s

    # ---------------------------------------------------------------- growth efficiency (A2)
    def p_gneg(self, X, kappa=None):
        return 1.0 / (1.0 + np.exp(-self.raw("gsign", X, kappa)))

    def sample_G(self, X, u_sign, u_res, kappa=None):
        """G_{y+1}: sign ~ Bernoulli(p_gneg); log|G| = magnitude head of that sign + a residual drawn (by u_res)
        from the empirical OOF residuals of its predicted-value decile."""
        k = self.kappa if kappa is None else kappa
        kk = "k1" if k != 0.0 else "k0"
        neg = u_sign < self.p_gneg(X, kappa)
        mag = np.empty(X.height)
        for s, msk in (("neg", neg), ("pos", ~neg)):
            if not msk.any():
                continue
            m = self.raw(f"gmag_{s}", X.filter(pl.Series(msk)), kappa)
            edges, res = self.resid[(s, kk)]
            d = np.searchsorted(edges, m)
            r = np.empty(len(m))
            uu = u_res[msk]
            for j in np.unique(d):
                q = d == j
                pool = res[j]
                r[q] = pool[np.minimum((uu[q] * len(pool)).astype(np.int64), len(pool) - 1)]
            mag[msk] = m + r
        return np.where(neg, -np.exp(mag), np.exp(mag))

    def expected_G(self, X, kappa=None):
        """Deterministic plug-in E[G_{y+1}] (smearing by the residual decile means of exp(r))."""
        k = self.kappa if kappa is None else kappa
        kk = "k1" if k != 0.0 else "k0"
        p = self.p_gneg(X, kappa)
        out = np.zeros(X.height)
        for s, sg in (("neg", -1.0), ("pos", 1.0)):
            m = self.raw(f"gmag_{s}", X, kappa)
            edges, res = self.resid[(s, kk)]
            sm = np.array([np.mean(np.exp(r)) for r in res])
            out += sg * (p if s == "neg" else 1 - p) * np.exp(m) * sm[np.searchsorted(edges, m)]
        return out

    @staticmethod
    def counter(c_y, G_y1, age_y):
        """The rule (mortality_tree_ind.c): c_{y+1} = c_y + 1 if G_{y+1} < 0 else 0 (reset when the pre-increment
        age is 1). age_y = printed Age of y. c_{y+1} >= 5 is a certain kill."""
        return rl.counter_step(c_y, G_y1, age_y).astype(np.int8)

    # ---------------------------------------------------------------- growth + AR residual (A3)
    def _with(self, X, **cols):
        return X.with_columns(*[pl.Series(k, np.asarray(v, np.float32)) for k, v in cols.items()])

    def growth(self, X, G_y1, c_y1, e_prev=None, z=None, kappa=None):
        """dlog agb, dlog vegc of every present stem given (sampled) G_{y+1}, c_{y+1}; with e_prev (carried AR
        residual per tree and head, dict 'dagb'/'dvegc') and z (standard normals, dict) adds
        e' = rho e + sqrt(1 - rho^2) sigma(Type, agb decile) z. Returns (dlog_agb, dlog_vegc, e_new dict)."""
        Xg = self._with(X, G_y1=G_y1, c_y1=c_y1)
        out, e_new = {}, {}
        for g in ("dagb", "dvegc"):
            mu = self.raw(g, Xg, kappa)
            if e_prev is not None and z is not None and g in self.ar:
                rho, sig = self.ar_params(g, X["Type"].to_numpy(), X["agb"].to_numpy())
                e = rho * np.nan_to_num(e_prev[g]) + np.sqrt(1 - rho ** 2) * sig * z[g]
                e_new[g] = e.astype(np.float32)
                mu = mu + e
            out[g] = mu
        return out["dagb"], out["dvegc"], e_new

    def ar_params(self, g, typ, agb):
        A = self.ar[g]
        rho = np.zeros(len(typ))
        sig = np.zeros(len(typ))
        la = np.log(np.asarray(agb, np.float64))
        for t in np.unique(typ):
            m = typ == t
            key = str(int(t)) if str(int(t)) in A["edges"] else A["types"][0].__str__()
            b = np.searchsorted(np.asarray(A["edges"][key]), la[m])
            rho[m] = np.asarray(A["rho"][key])[b]
            sig[m] = np.asarray(A["sigma"][key])[b]
        return rho, sig

    def closures(self, X, G_y1, c_y1, dlog_agb, dlog_vegc, kappa=None):
        Xc = self._with(X, G_y1=G_y1, c_y1=c_y1, dlog_agb_y1=dlog_agb, dlog_vegc_y1=dlog_vegc)
        return {g: self.raw(g, Xc, kappa) for g in ("dlai", "dfpc", "dd95") if g in self.m}

    def height_offset(self, agb, wd, sla, typ, H, lai=None, fpc=None):
        """The fixed per-tree offset ln H - ln allometry(state): compute once at the start roster / recruit entry."""
        coef = self.allom_ext if lai is not None else self.allom
        return (np.log(H) - np.log(rl.predict_height(agb, wd, sla, typ, coef, lai=lai, fpc_ind=fpc))).astype(
            np.float32)

    def height(self, agb, wd, sla, typ, offset, lai=None, fpc=None):
        coef = self.allom_ext if lai is not None else self.allom
        return (rl.predict_height(agb, wd, sla, typ, coef, lai=lai, fpc_ind=fpc) * np.exp(offset)).astype(np.float32)

    # ---------------------------------------------------------------- survival (A4)
    def p_death(self, X, G_y1, c_y1, phys=False, kappa=None):
        """P(flagged dead at y+1); c_{y+1} >= 5 -> 1 by the rule. Fire is inside the learned head."""
        Xs = self._with(X, G_y1=G_y1, c_y1=c_y1)
        name = "surv_phys" if phys else "surv"
        if phys:
            Xs = self._with(Xs, h_phys=h_phys(X["Type"].to_numpy(), X["Wooddens"].to_numpy(), X["Age"].to_numpy(),
                                              G_y1, c_y1, X["tstress_own_y1"].to_numpy(), self.P))
        p = 1.0 / (1.0 + np.exp(-self.raw(name, Xs, kappa)))
        return np.where(np.asarray(c_y1) >= self.P.g["bm_inc_counter_max"], 1.0, p)

    # ---------------------------------------------------------------- recruits (A5)
    def recruit_type_probs(self, R: pl.DataFrame, kappa=None):
        """R = recruit-slot frame with F.recruit_cols() (F.recruit_features applied); returns [n, n_types] over
        F.RECR_TYPES."""
        s = self.raw("rtype", R, kappa).reshape(R.height, -1)
        s = s - s.max(axis=1, keepdims=True)
        e = np.exp(s)
        return e / e.sum(axis=1, keepdims=True)

    def recruit_traits(self, typ, cell, standing: dict, build, rng: np.random.Generator):
        """Traits of new recruits (typ, cell arrays) from the fitted donor mixture. standing = dict of arrays over
        the cell's living printed stems (Cell, Type, agb, SLA, Wooddens, D95max, minwscal). build = 'dec2025' |
        'feb2026' (scalar or per recruit: the Dec-2025 bound quirk switch). Returns dict incl. Longevity, beta_root."""
        return sample_traits(typ, cell, standing, self.traits_fit, build, rng, self.P)

    def grass(self, Pf: pl.DataFrame, kappa=None):
        return {t: self.raw(f"grass_{t}", Pf, kappa) for t in ("g_fpc_y1", "g_LAI_y1", "g_agb_y1")
                if f"grass_{t}" in self.m}

    # ---------------------------------------------------------------- one transition (tree part)
    def transition(self, X, state, rand, year, phys=False, kappa=None, height_ext=False):
        """Tree part of a step y -> y+1 for EVERY tree of the state (hidden incl.), using the engine's Rand streams
        keyed by (Cell, Patch, Type, ID). Returns a dict with the StepOut tree fields (Height, agb, vegc, LAI,
        fpc_ind, D95, Age, c, G, d_agb_prev), 'isdead', and aux_tree updates (e_dagb, e_dvegc, is_new=False).
        Needs state.aux_tree['h_off'] (fixed height offsets) and the AR residuals e_dagb / e_dvegc (0 at start)."""
        t = state.tree
        keys = (t["Cell"], t["Patch"], t["Type"], t["ID"])
        u_s = rand.uniform("tab_gsign", year, *keys)
        u_r = rand.uniform("tab_gres", year, *keys)
        G1 = self.sample_G(X, u_s, u_r, kappa)
        c1 = self.counter(t["c"], G1, t["Age"])
        ea = state.aux_tree.get("e_dagb", np.zeros(state.n, np.float32))
        ev = state.aux_tree.get("e_dvegc", np.zeros(state.n, np.float32))
        z = {"dagb": rand.normal("tab_zagb", year, *keys), "dvegc": rand.normal("tab_zvegc", year, *keys)}
        da, dv, e_new = self.growth(X, G1, c1, {"dagb": ea, "dvegc": ev}, z, kappa)
        cl = self.closures(X, G1, c1, da, dv, kappa)
        agb1 = t["agb"] * np.exp(da)
        vegc1 = t["vegc"] * np.exp(dv)
        lai1 = t["LAI"] * np.exp(cl.get("dlai", 0.0))
        fpc1 = t["fpc_ind"] * np.exp(cl.get("dfpc", 0.0))
        d951 = t["D95"] * np.exp(cl.get("dd95", 0.0))
        off = state.aux_tree.get("h_off", np.zeros(state.n, np.float32))
        H1 = self.height(agb1, t["Wooddens"], t["SLA"], t["Type"], off, *((lai1, fpc1) if height_ext else ()))
        pd = self.p_death(X, G1, c1, phys, kappa)
        dead = rand.uniform("tab_death", year, *keys) < pd
        upd = {"Height": H1, "agb": agb1, "vegc": vegc1, "LAI": lai1, "fpc_ind": fpc1, "D95": d951,
               "Age": t["Age"] + 1, "c": c1, "G": G1, "d_agb_prev": agb1 - t["agb"]}
        aux = {"e_dagb": e_new.get("dagb", ea), "e_dvegc": e_new.get("dvegc", ev), "is_new": np.zeros(state.n, bool),
               "h_off": off}
        return {"tree": upd, "isdead": dead, "p_death": pd, "aux_tree": aux}


# ------------------------------------------------------------------------------------------------ trait sampler
TRAIT_AX = [("SLA", "sla"), ("Wooddens", "wooddens"), ("D95max", "d95max"), ("minwscal", "minwscal")]


def trait_bounds(typ, build, P):
    """(lo, hi) per inherited trait for the reflection: own-PFT interval, except Wooddens / D95max in the Dec-2025
    build, which are bounded by the stale slot's (PFT 0's) interval (rl.inherit_traits)."""
    t = np.asarray(typ, np.int64)
    b = np.broadcast_to(np.asarray(build), t.shape)
    slot = int(P.g["stale_slot"])
    out = {}
    for k, pre in TRAIT_AX:
        lo, hi = P[f"{pre}_low"][t], P[f"{pre}_high"][t]
        if k in ("Wooddens", "D95max"):
            lo = np.where(b == "dec2025", P[f"{pre}_low"][slot], lo)
            hi = np.where(b == "dec2025", P[f"{pre}_high"][slot], hi)
        out[k] = (lo, hi)
    return out


def reflect(old, s, z, u, lo, hi):
    """rl.draw_new_trait with given normals z and uniforms u (common random numbers): new = old (1 + s clip(z, +-5)),
    reflected into [lo, hi] the C's way."""
    new = old * (1.0 + s * np.clip(z, -5.0, 5.0))
    new = np.where(new < lo, lo + (old - lo) * u, np.where(new > hi, old + (hi - old) * u, new))
    return np.where(lo == hi, old, new)


def donor_index(st_group_start, st_group_end, cumw, u):
    """Pick a donor per recruit within its group, p ~ weight, by inversion on the global cumulative weights."""
    lo = np.where(st_group_start > 0, cumw[np.maximum(st_group_start - 1, 0)], 0.0)
    hi = cumw[st_group_end - 1]
    tgt = lo + u * (hi - lo)
    idx = np.searchsorted(cumw, tgt, side="right")
    return np.clip(idx, st_group_start, st_group_end - 1)


def standing_groups(st: pl.DataFrame, gkeys):
    st = st.sort(gkeys)
    g = st.select(gkeys).with_row_index("_i").group_by(gkeys, maintain_order=True).agg(
        s=pl.col("_i").min(), e=pl.col("_i").max() + 1)
    return st, g


def prep_donors(typ, cell, standing, recruit_year=None) -> dict:
    """Group the standing stems by (Cell, Type[, Year]) once and locate each recruit's donor group. standing:
    dict/frame with Cell, Type, agb, the 4 traits (+ Year when recruit_year is given)."""
    typ = np.asarray(typ, np.int64)
    S = pl.DataFrame(standing) if isinstance(standing, dict) else standing
    gk = ["Cell", "Type"] + (["Year"] if recruit_year is not None else [])
    S, G = standing_groups(S.select(gk + ["agb"] + [k for k, _ in TRAIT_AX]), gk)
    R = pl.DataFrame({"Cell": np.asarray(cell).astype(np.int32), "Type": typ.astype(np.int32)}
                     | ({"Year": np.asarray(recruit_year).astype(np.int32)} if recruit_year is not None else {})
                     ).with_row_index("_r")
    R = R.join(G.with_columns(*[pl.col(c).cast(pl.Int32) for c in gk]), on=gk, how="left").sort("_r")
    return {"typ": typ, "has": R["s"].is_not_null().to_numpy(), "s": R["s"].fill_null(0).to_numpy().astype(np.int64),
            "e": R["e"].fill_null(1).to_numpy().astype(np.int64), "agb": S["agb"].to_numpy().astype(np.float64),
            "tr": {k: S[k].to_numpy().astype(np.float64) for k, _ in TRAIT_AX}, "cw": {}}


def crn(n, rng) -> dict:
    """The per-recruit random numbers of one draw (reusable across parameter values = common random numbers)."""
    return {"mix": rng.random(n), "don": rng.random(n), "z": rng.standard_normal((len(TRAIT_AX), n)),
            "u": rng.random((len(TRAIT_AX), n)), "bg": rng.random((len(TRAIT_AX), n))}


def mix_draw(D, fit, build, U, P) -> dict:
    typ = D["typ"]
    n = len(typ)
    w = np.array([fit[str(t)]["w"] if str(t) in fit else 0.0 for t in typ])
    a = np.array([fit[str(t)]["a"] if str(t) in fit else 0.0 for t in typ])
    sc = np.array([fit[str(t)]["s"] if str(t) in fit else 0.1 for t in typ])
    out = {k: np.zeros(n) for k, _ in TRAIT_AX}
    use_d = D["has"] & (U["mix"] < w)
    for av in (np.unique(a[use_d]) if use_d.any() else []):
        m = use_d & (a == av)
        if av not in D["cw"]:
            D["cw"][av] = np.cumsum(np.power(D["agb"], av))
        di = donor_index(D["s"][m], D["e"][m], D["cw"][av], U["don"][m])
        bnd = trait_bounds(typ[m], np.asarray(build)[m] if np.ndim(build) else build, P)
        for j, (k, _) in enumerate(TRAIT_AX):
            lo, hi = bnd[k]
            out[k][m] = reflect(D["tr"][k][di], sc[m], U["z"][j, m], U["u"][j, m], lo, hi)
    bg = ~use_d
    for j, (k, pre) in enumerate(TRAIT_AX):
        lo, hi = P[f"{pre}_low"][typ[bg]], P[f"{pre}_high"][typ[bg]]
        out[k][bg] = lo + (hi - lo) * U["bg"][j, bg]
    out["donor"] = use_d
    return out


def sample_traits(typ, cell, standing, fit, build, rng, P, recruit_year=None):
    """Mixture sampler (A-H9): weight w a donor = a living printed same-Type stem of the recruit's cell drawn with
    p ~ agb^a, each trait x (1 + s N(0,1)) reflected by the rule (Dec-2025 bound quirk when build == 'dec2025');
    weight 1 - w (and every recruit without a same-Type stem in its cell): uniform on the Type's interval.
    Longevity and beta_root follow by the rules (rl.longevity_of, rl.getbetaroot)."""
    D = prep_donors(typ, cell, standing, recruit_year)
    out = mix_draw(D, fit, build, crn(len(D["typ"]), rng), P)
    out["Longevity"] = rl.longevity_of(out["SLA"], D["typ"], rng, P)
    out["beta_root"] = rl.getbetaroot(out["D95max"], P)
    return out


# ------------------------------------------------------------------------------------------------ submit
def submit(what, args, cpus=16, part="priority", hours=4, extra=""):
    logs = os.path.join(REPO, "logs")
    os.makedirs(logs, exist_ok=True)
    jd = os.path.join(TAB, "_jobs")
    os.makedirs(jd, exist_ok=True)
    qos = "priority" if part == "priority" else "short"
    js = os.path.join(jd, f"A_{what}.sh")
    body = (f"#!/bin/bash\n#SBATCH --account=waldspektrum --partition={part} --qos={qos}\n"
            f"#SBATCH --cpus-per-task={cpus} --time={hours:02d}:00:00 {extra}\n"
            f"#SBATCH --job-name=X-de-{what} --output={logs}/X-de-{what}.%j.out\n"
            f"export POLARS_MAX_THREADS={cpus}\n{F.PY} {os.path.abspath(__file__)} {args}\n")
    open(js, "w").write(body)
    out = os.popen(f"sbatch {js}").read().strip()
    print(out, js, flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["train", "eval", "contrast", "traits", "apitest", "submit"])
    ap.add_argument("--split", default="DEV-A")
    ap.add_argument("--head", nargs="*", default=[])
    ap.add_argument("--item", default=None)
    ap.add_argument("--what", default=None)
    ap.add_argument("--args", default="")
    ap.add_argument("--cpus", type=int, default=16)
    ap.add_argument("--part", default="priority")
    ap.add_argument("--hours", type=int, default=4)
    ap.add_argument("--dep", default="")
    a = ap.parse_args()
    if a.stage == "train":
        for h in a.head:
            if h == "grass":
                train_grass(a.split)
            elif h == "rtype":
                train_rtype(a.split)
            else:
                train_head(a.split, h)
    elif a.stage == "eval":
        import explore_de_tab_eval as ev
        ev.run(a.split, a.item)
    elif a.stage == "contrast":
        import explore_de_tab_eval as ev
        ev.contrast(a.split)
    elif a.stage == "traits":
        import explore_de_tab_eval as ev
        ev.traits(a.split)
    elif a.stage == "apitest":
        import explore_de_tab_eval as ev
        ev.apitest(a.split)
    elif a.stage == "submit":
        extra = f"--dependency={a.dep}" if a.dep else ""
        submit(a.what, a.args, a.cpus, a.part, a.hours, extra)


if __name__ == "__main__":
    main()
