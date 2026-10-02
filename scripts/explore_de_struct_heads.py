#!/usr/bin/env python3
"""explore_de_struct_heads.py — LINE X, Germany data-driven emulator, B-STRUCT item B1: GROWTH HEADS + OOF RESIDUALS.

Only the climate -> growth map is learned. Every other rule (counter, hazards, deaths, establishment) is the original
model's own (explore_de_sh_rules). These heads give, for one tree-year y -> y+1:

  G   growth efficiency G_{y+1} (bm_delta / leaf area; the counter's sign): classifier P(G<0) [gclf], regression of G
      on every present stem [gall, the mean], and the two sign-conditional regressions used for sampling:
      log(-G) | G<0 [gneg] and G | G>=0 [gpos]
  W   water-stress integral W_{y+1}: hurdle P(W>0) [wclf] + log W | W>0 [wreg] (W-saturated rows = lower bounds,
      excluded from wreg)
  S   size change GIVEN G_{y+1} (true G at training, the sampled G at rollout): dlog agb [dlagb], dlog vegc [dlvegc],
      LAI change [dlai], dlog fpc_ind [dlfpc], dlog D95 [dld95]. Height then comes from the rules' allometry.

INPUTS (every head): Type (categorical), the 6 traits, Height, agb, vegc, LAI, fpc_ind, D95, Age, c_y, patch n_live /
sum_fpc / sum_agb / height_rank / fpc_above, grass8 fpc/LAI/agb, soil code (categorical), and the climate of y+1 and y
(monthly temp + prec, gdd5, cwb_jja, cwb_amjjas, cwb_min3, vpd_jja, prec_jja, days_gt30, swdown_ann, lwdown_ann, the
tree Type's temperature-stress day count) each as LEVEL and as ANOMALY (= level minus the same GCM's 1985-2014 mean of
that cell, shared/climate/clim8514.parquet — the same reference SH1's anom_* columns use). EXPLICITLY NOT: npp, transp,
wscal_mean, G_y, W_y, mort_* of year y, d_agb_prev (the copy-last-year shortcut). No CO2, no wind, no lon/lat, no
cell id. Climate comes ONLY through explore_de_sh_trans.join_climate().

LightGBM, linear_tree=True (piecewise-linear leaves on the split features, so the climate response is linear inside a
leaf instead of a step), Type and soil code categorical.

SPLIT (parameter; DEV-A default): training members = SH0 splits role == "train" (MPI-ESM1-2-HR seed 1 Historical,
ssp126, ssp370), dev cells of block folds 1-4. Each head is fitted 4 times (fold k = 1..4 held out, early stopping on
fold k) -> OUT-OF-FOLD predictions on every training row, then refitted on folds 1-4 with 1.1 x the median best
iteration (the production model). Fold 5, ACCESS-CM2, MPI ssp245 and seed 2 are never trained on.

LATENT RESIDUAL. Every head's OOF residual is turned into a normal score z (Gaussian copula):
  G   u = p * (1 - F_neg(r_neg))  if G < 0,   u = p + (1 - p) * F_pos(r_pos)  if G >= 0      (p = P(G<0))
  W   u = (1 - q) * v (v ~ U(0,1), randomised)  if W == 0,   u = (1 - q) + q * F_w(r_w)  if W > 0
  S   u = F_s(r_s)
  z = Phi^-1(u). F_* = empirical OOF residual CDF per (head, Type, size class) (101-quantile tables).
Sampling inverts exactly this map, so "sign from the classifier, value from the sign-conditional regression plus
residual" is one draw of u per tree. Per (Type, size class): AR(1) z' = rho z + sigma e, sigma = sd(z) sqrt(1 - rho^2),
from consecutive-year OOF pairs of the same tree, and the correlation matrix of the innovations e across the 7 latent
targets (G, W, 5 size) -> Cholesky factor. (Re-calibrating rho/sigma by free runs is a later step, not here.)

STAGES
  sample  --split S                   training sample (u_hash stratified) with features + targets -> heads/<S>/sample/
  fit     --split S --head H          4 fold fits + refit -> heads/<S>/models/<H>.txt, oof/<H>.parquet, qtab
  ranges  --split S                   record training-target ranges (clip bounds of the regression means)
  ar      --split S                   z scores, AR(1) + innovation correlation tables -> heads/<S>/ar.parquet
  eval    --split S --member M        teacher-forced predictions on held-out rows -> heads/<S>/pred/<M>.parquet
  report  --split S                   R2 beside the copy-last and persistence nulls -> _reports/r2_B1.json
  submit  --split S [--what fit|eval|all]   SLURM jobs (array over heads / members)

PREDICT API (what a rollout stepper calls; see StructHeads)
  H = StructHeads.load("DEV-A")
  X = H.features(frame)          frame: polars, one row per tree, tree state + patch context + Cell, gcm, Type and the
                                 climate columns <lev>_y, <lev>_y1 of climate_levels() (H.climate_columns())
  m = H.predict(X)               dict of the head means (p_gneg, mu_gneg, mu_gpos, mu_gall, q_w, mu_w)
  draw = H.sample(X, z, size_class)  z [n, 7] latent normal scores -> G, W and the 5 size changes (given that G)
  z1 = H.ar_step(z, Type, size_class, normals[n, 7])   one AR(1) year of the latent
  z0 = H.residual_z(X, G, W, sizes ...) the latent of an observed transition (rollout initialisation)
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_sh_rules as rl  # noqa: E402
import explore_de_sh_trans as tr  # noqa: E402

XDE = tr.XDE
OUT = os.environ.get("B1_OUT", os.path.join(XDE, "struct", "heads"))
STATUS = os.path.join(XDE, "_status", "B1.md")
REPORTS = os.path.join(OUT, "_reports") if "B1_OUT" in os.environ else os.path.join(XDE, "_reports")
CLIM8514 = os.path.join(XDE, "shared", "climate", "clim8514.parquet")
STATIC = os.path.join(XDE, "climate", "cell_static.parquet")
PY = tr.PY
LOGDIR = os.path.join(REPO, "logs")
KEY = tr.KEY

# ------------------------------------------------------------------------------------------------ configuration
U_BASE = float(os.environ.get("B1_U_BASE", "0.03"))   # uniform training rows (every head)
U_RARE = float(os.environ.get("B1_U_RARE", "0.15"))   # G<0 and W>0 rows for gneg / wreg
U_EV_ALL = float(os.environ.get("B1_U_EV_ALL", "0.03"))  # eval rows, all dev cells (held-out members)
U_EV_F5 = float(os.environ.get("B1_U_EV_F5", "0.15"))    # eval rows, fold-5 cells (every member)
TRAIN_FOLDS = (1, 2, 3, 4)
HOLD_FOLD = 5
SIZE_EDGES = (7.0, 10.0, 15.0, 20.0)   # Height classes at y: <7, 7-10, 10-15, 15-20, >=20 m
NQ = 101
LATENT = ["G", "W", "dlagb", "dlvegc", "dlai", "dlfpc", "dld95"]
SIZE_HEADS = ["dlagb", "dlvegc", "dlai", "dlfpc", "dld95"]
HEADS = ["gclf", "gall", "gneg", "gpos", "wclf", "wreg"] + SIZE_HEADS
OOF_HEADS = ["gclf", "gneg", "gpos", "wclf", "wreg"] + SIZE_HEADS
CLASSIFIERS = {"gclf", "wclf"}

MONTHLY = [f"temp_m{m:02d}" for m in range(1, 13)] + [f"prec_m{m:02d}" for m in range(1, 13)]
ANNUAL = ["gdd5", "cwb_jja", "cwb_amjjas", "cwb_min3", "vpd_jja_eff", "prec_jja", "days_gt30", "swdown_ann",
          "lwdown_ann"]
N_PFT = 7
TSTRESS = [f"tstress_pft{k}" for k in range(N_PFT)]
STATE_NUM = ["SLA", "Wooddens", "D95max", "minwscal", "Longevity", "beta_root", "Height", "agb", "vegc", "LAI",
             "fpc_ind", "D95", "Age", "c_y", "n_live", "sum_fpc", "sum_agb", "height_rank", "fpc_above",
             "grass8_fpc", "grass8_LAI", "grass8_agb"]
CAT = ["Type", "soil_code"]
FORBIDDEN = {"npp", "transp", "wscal_mean", "G_y", "W_y", "mort_npp", "mort_age", "mort_water", "mort_temp", "mort",
             "d_agb_prev", "cenG_y", "cenW_y", "Cell", "lon", "lat", "Patch", "ID", "u_hash"}

LGB_BASE = dict(learning_rate=0.06, num_leaves=63, min_data_in_leaf=200, feature_fraction=0.8, bagging_fraction=0.8,
                bagging_freq=1, lambda_l2=1.0, linear_tree=True, linear_lambda=1.0, max_bin=255, verbose=-1,
                seed=20261002, deterministic=True, force_row_wise=True)
MAX_ROUNDS = int(os.environ.get("B1_MAX_ROUNDS", "1500"))
ES_ROUNDS = 50


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def status(line: str):
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    with open(STATUS, "a") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} {line}\n")


def sdir(split: str, *p) -> str:
    d = os.path.join(OUT, split, *p)
    os.makedirs(d if not os.path.splitext(d)[1] else os.path.dirname(d), exist_ok=True)
    return d


def nthreads() -> int:
    return int(os.environ.get("SLURM_CPUS_PER_TASK", "4"))


# ------------------------------------------------------------------------------------------------ registry / split
def split_members(split: str) -> dict:
    """Training members (role == train), and every usable member with its role, from the SH0 registry."""
    sp = pl.read_parquet(os.path.join(tr.REG, "splits.parquet")).filter(pl.col("split") == split)
    mem, _, _ = tr.registry()
    usable = set(tr.usable_members(mem))
    train = sorted(set(sp.filter(pl.col("role") == "train")["src_member"].to_list()) & usable)
    assert train, f"no training members for {split}"
    return {"train": train, "all": sorted(usable)}


def folds() -> pl.DataFrame:
    return (pl.read_parquet(os.path.join(tr.REG, "folds.parquet")).filter(pl.col("is_dev"))
            .select(pl.col("Cell").cast(pl.Int16), "fold", "block"))


def member_files(member: str) -> list[str]:
    fs = sorted(glob.glob(os.path.join(tr.TRANS, "dev", member, "cb=dev", "y*.parquet")))
    assert fs, member
    return fs


def year_of(f: str) -> int:
    return int(os.path.basename(f)[1:5])


# ------------------------------------------------------------------------------------------------ features
def climate_levels() -> list[str]:
    return MONTHLY + ANNUAL + TSTRESS


_C8: dict = {}
_SOIL: dict = {}


def clim8514() -> pl.DataFrame:
    if "c" not in _C8:
        _C8["c"] = (pl.read_parquet(CLIM8514).select(["gcm", pl.col("Cell").cast(pl.Int16)]
                                                    + [pl.col(c).alias(f"c8_{c}") for c in climate_levels()]))
    return _C8["c"]


def soil_codes() -> pl.DataFrame:
    if "s" not in _SOIL:
        _SOIL["s"] = pl.read_parquet(STATIC).select(pl.col("Cell").cast(pl.Int16), pl.col("soil_code").cast(pl.Int16))
    return _SOIL["s"]


def feature_names(with_g: bool = False) -> list[str]:
    clim = []
    for s in ("y1", "y"):
        lev = MONTHLY + ANNUAL + ["tstress"]
        clim += [f"{c}_{s}" for c in lev] + [f"a_{c}_{s}" for c in lev]
    names = CAT + STATE_NUM + clim + (["G_y1"] if with_g else [])
    assert not (set(names) & FORBIDDEN), set(names) & FORBIDDEN
    return names


def add_features(df: pl.DataFrame) -> pl.DataFrame:
    """df: tree rows with gcm, Cell, Type, state, patch context and climate <lev>_y / <lev>_y1 (from join_climate or
    the rollout provider). Adds the per-Type stress-day count, anomalies and soil code."""
    df = df.join(clim8514(), on=["gcm", "Cell"], how="left").join(soil_codes(), on="Cell", how="left")
    t = pl.col("Type").cast(pl.Int32)
    ex = []
    for s in ("y", "y1"):
        ts = pl.lit(None, pl.Float64)
        tc = pl.lit(None, pl.Float64)
        for k in range(N_PFT):
            ts = pl.when(t == k).then(pl.col(f"tstress_pft{k}_{s}").cast(pl.Float64)).otherwise(ts)
            tc = pl.when(t == k).then(pl.col(f"c8_tstress_pft{k}")).otherwise(tc)
        ex += [ts.alias(f"tstress_{s}"), (ts - tc).alias(f"a_tstress_{s}")]
        for c in MONTHLY + ANNUAL:
            ex.append((pl.col(f"{c}_{s}").cast(pl.Float64) - pl.col(f"c8_{c}")).alias(f"a_{c}_{s}"))
    df = df.with_columns(ex)
    return df.with_columns([pl.col(c).fill_null(0.0) for c in ("grass8_fpc", "grass8_LAI", "grass8_agb")
                            if c in df.columns])


def matrix(df: pl.DataFrame, names: list[str]) -> np.ndarray:
    return df.select([pl.col(c).cast(pl.Float32) for c in names]).to_numpy()


def size_class(height) -> np.ndarray:
    return np.searchsorted(np.asarray(SIZE_EDGES), np.asarray(height, dtype=np.float64), side="right").astype(np.int8)


# ------------------------------------------------------------------------------------------------ targets
def add_targets(df: pl.DataFrame) -> pl.DataFrame:
    present = pl.col("fate_y1") < 2
    f64 = pl.Float64
    g_ok = present & pl.col("cenG_y1").is_in([0, 5])
    return df.with_columns(
        present=present,
        g_ok=g_ok,
        gneg_t=pl.when(g_ok & (pl.col("G_y1") < 0)).then((-pl.col("G_y1").cast(f64)).log()),
        gpos_t=pl.when(g_ok & (pl.col("G_y1") >= 0)).then(pl.col("G_y1").cast(f64)),
        gsign_t=pl.when(present & pl.col("cenG_y1").is_in([0, 1, 2, 5]))
        .then((pl.col("G_y1") < 0).cast(f64)),
        w_ok=present & pl.col("cenW_y1").is_not_null(),
        wpos_t=pl.when(present & pl.col("cenW_y1").is_not_null()).then((pl.col("W_y1") > 0).cast(f64)),
        wreg_t=pl.when(present & (pl.col("cenW_y1") == 0) & (pl.col("W_y1") > 0)).then(pl.col("W_y1").cast(f64).log()),
        dlagb_t=pl.when(present).then((pl.col("agb_y1").cast(f64) / pl.col("agb").cast(f64)).log()),
        dlvegc_t=pl.when(present).then((pl.col("vegc_y1").cast(f64) / pl.col("vegc").cast(f64)).log()),
        dlai_t=pl.when(present).then(pl.col("LAI_y1").cast(f64) - pl.col("LAI").cast(f64)),
        dlfpc_t=pl.when(present).then((pl.col("fpc_ind_y1").cast(f64) / pl.col("fpc_ind").cast(f64)).log()),
        dld95_t=pl.when(present).then((pl.col("D95_y1").cast(f64) / pl.col("D95").cast(f64)).log()),
    )


HEAD_TARGET = {"gclf": "gsign_t", "gall": "G_y1", "gneg": "gneg_t", "gpos": "gpos_t", "wclf": "wpos_t",
               "wreg": "wreg_t", "dlagb": "dlagb_t", "dlvegc": "dlvegc_t", "dlai": "dlai_t", "dlfpc": "dlfpc_t",
               "dld95": "dld95_t"}


def head_rows(df: pl.DataFrame, head: str) -> np.ndarray:
    base = df["u_hash"].to_numpy() < U_BASE
    tgt = df[HEAD_TARGET[head]].to_numpy().astype(np.float64)
    ok = np.isfinite(tgt)
    if head == "gall":
        ok &= df["g_ok"].to_numpy()
    if head in SIZE_HEADS:
        ok &= df["g_ok"].to_numpy()   # the size heads condition on a known G_{y+1}
    if head in ("gneg", "wreg"):
        return ok & (df["u_hash"].to_numpy() < U_RARE)
    return ok & base


def uses_g(head: str) -> bool:
    return head in SIZE_HEADS


# ------------------------------------------------------------------------------------------------ sample stage
def read_member_rows(member: str, cell_filter: pl.Expr, row_filter: pl.Expr, need_prev: bool = False,
                     clim_traj: str | None = None) -> pl.DataFrame:
    """Rows of one member (all years) passing the filters, with climate of y and y+1 and features + targets.
    clim_traj: take the climate of ANOTHER trajectory of the same GCM/seed (a climate swap: same trees, other
    weather) — diagnostic only."""
    fo = folds()
    outs = []
    prev = None
    for f in member_files(member):
        lf = pl.scan_parquet(f).join(fo.lazy(), on="Cell", how="inner").filter(cell_filter & row_filter)
        d = lf.collect()
        if need_prev:
            y = year_of(f)
            pf = os.path.join(os.path.dirname(f), f"y{y - 1}.parquet")
            if prev is not None:
                d = d.join(prev, on=KEY, how="left")
            elif os.path.exists(pf):
                p_ = (pl.scan_parquet(pf).join(fo.lazy(), on="Cell", how="inner").filter(cell_filter & row_filter)
                      .select(KEY + [pl.col(c).alias(f"{c}_ym1") for c in ("vegc", "LAI", "fpc_ind", "D95")])
                      .collect())
                d = d.join(p_, on=KEY, how="left")
            else:
                d = d.with_columns([pl.lit(None, pl.Float32).alias(f"{c}_ym1") for c in ("vegc", "LAI", "fpc_ind",
                                                                                       "D95")])
            prev = d.select(KEY + [pl.col(c).alias(f"{c}_ym1") for c in ("vegc", "LAI", "fpc_ind", "D95")])
        outs.append(d)
    df = pl.concat(outs, how="vertical_relaxed")
    if clim_traj is not None:
        traj0 = df["traj"]
        df = tr.join_climate(df.with_columns(traj=pl.lit(clim_traj)), cols=climate_levels(), years=("y", "y1"))
        df = df.with_columns(traj=traj0)
    else:
        df = tr.join_climate(df, cols=climate_levels(), years=("y", "y1"))
    return add_targets(add_features(df))


def stage_sample(a):
    mm = split_members(a.split)
    od = sdir(a.split, "sample")
    rows = (pl.col("u_hash") < U_BASE) | ((pl.col("u_hash") < U_RARE) & ((pl.col("G_y1") < 0) | (pl.col("W_y1") > 0)))
    cells = pl.col("fold").is_in(list(TRAIN_FOLDS))
    parts = []
    for m in mm["train"]:
        t0 = time.time()
        d = read_member_rows(m, cells, rows)
        parts.append(d)
        log(f"{m}: {d.height} rows, {time.time() - t0:.0f} s")
    df = pl.concat(parts, how="vertical_relaxed").with_row_index("rid")
    fn = feature_names(with_g=True)
    miss = [c for c in fn if c not in df.columns]
    assert not miss, miss
    keep = (["rid", "member", "gcm", "traj", "seed", "Year", "Cell", "Patch", "ID", "u_hash", "fold", "block",
             "fate_y1", "present", "g_ok", "w_ok", "G_y1", "cenG_y1", "W_y1", "cenW_y1", "tmean_ann_y1"]
            + [v for v in HEAD_TARGET.values() if v != "G_y1"])
    df = df.join(tr.join_climate(df.select("rid", "gcm", "traj", "seed", "Cell", "Year"), cols=["tmean_ann"],
                                 years=("y1",)).select("rid", "tmean_ann_y1"), on="rid", how="left")
    cols = list(dict.fromkeys(keep + fn))
    df.select(cols).write_parquet(os.path.join(od, "train.parquet"))
    meta = {"split": a.split, "members": mm["train"], "folds": list(TRAIN_FOLDS), "rows": df.height,
            "u_base": U_BASE, "u_rare": U_RARE, "features": feature_names(), "features_size": fn,
            "per_member": df.group_by("member").len().to_dicts()}
    json.dump(meta, open(os.path.join(od, "meta.json"), "w"), indent=1)
    status(f"sample {a.split}: {df.height} rows from {mm['train']}")
    log(json.dumps({k: v for k, v in meta.items() if k not in ("features", "features_size")}))


def load_sample(split: str) -> pl.DataFrame:
    return pl.read_parquet(os.path.join(OUT, split, "sample", "train.parquet"))


# ------------------------------------------------------------------------------------------------ fit stage
def lgb_params(head: str) -> dict:
    p = dict(LGB_BASE, num_threads=nthreads())
    if head in CLASSIFIERS:
        p.update(objective="binary", metric="binary_logloss")
    else:
        p.update(objective="regression", metric="l2")
    return p


def fit_one(Xtr, ytr, Xva, yva, head, names, rounds=None):
    import lightgbm as lgb
    cat = [i for i, n in enumerate(names) if n in CAT]
    dtr = lgb.Dataset(Xtr, ytr, feature_name=names, categorical_feature=cat, free_raw_data=False)
    if rounds is not None:
        return lgb.train(lgb_params(head), dtr, num_boost_round=int(rounds))
    dva = lgb.Dataset(Xva, yva, reference=dtr, feature_name=names, categorical_feature=cat)
    return lgb.train(lgb_params(head), dtr, num_boost_round=MAX_ROUNDS, valid_sets=[dva],
                     callbacks=[lgb.early_stopping(ES_ROUNDS, verbose=False), lgb.log_evaluation(100)])


def qtable(resid: np.ndarray, typ: np.ndarray, scls: np.ndarray) -> list[dict]:
    """101-quantile tables of OOF residuals per (Type, size class), + pooled per Type (scls = -1) and global."""
    out = []
    qs = np.linspace(0, 1, NQ)

    def row(t, s, r):
        out.append({"Type": int(t), "scls": int(s), "n": int(r.size), "q": np.quantile(r, qs).tolist(),
                    "mean_exp": float(np.mean(np.exp(np.clip(r, -50, 50)))), "sd": float(r.std())})
    ok = np.isfinite(resid)
    row(-1, -1, resid[ok])
    for t in np.unique(typ[ok]):
        m = ok & (typ == t)
        row(t, -1, resid[m])
        for s in np.unique(scls[m]):
            mm = m & (scls == s)
            if mm.sum() >= 500:
                row(t, s, resid[mm])
    return out


def stage_fit(a):
    head = a.head
    df = load_sample(a.split)
    names = feature_names(with_g=uses_g(head))
    rows = head_rows(df, head)
    tgt = df[HEAD_TARGET[head]].to_numpy().astype(np.float64)
    fold = df["fold"].to_numpy()
    X = matrix(df, names)
    md = sdir(a.split, "models")
    oof = np.full(df.height, np.nan)
    best = {}
    es_folds = list(TRAIN_FOLDS) if head in OOF_HEADS else [TRAIN_FOLDS[-1]]
    pred_rows = rows | (df["u_hash"].to_numpy() < U_BASE)   # OOF on every base row (latent pairs) + the head's rows
    for k in es_folds:
        t0 = time.time()
        tr_m = rows & (fold != k)
        va_m = rows & (fold == k)
        b = fit_one(X[tr_m], tgt[tr_m], X[va_m], tgt[va_m], head, names)
        best[k] = int(b.best_iteration or b.current_iteration())
        pm = pred_rows & (fold == k)
        oof[pm] = b.predict(X[pm], num_iteration=best[k])
        log(f"{head} fold {k}: train {tr_m.sum()} valid {va_m.sum()} best {best[k]} ({time.time() - t0:.0f} s)")
    rounds = max(20, int(round(1.1 * float(np.median(list(best.values()))))))
    t0 = time.time()
    final = fit_one(X[rows], tgt[rows], None, None, head, names, rounds=rounds)
    final.save_model(os.path.join(md, f"{head}.txt"))
    log(f"{head} refit on folds {TRAIN_FOLDS}: {rows.sum()} rows, {rounds} rounds ({time.time() - t0:.0f} s)")
    od = sdir(a.split, "oof")
    pl.DataFrame({"rid": df["rid"], "oof": oof}).filter(pl.col("oof").is_not_nan()).write_parquet(
        os.path.join(od, f"{head}.parquet"))
    info = {"head": head, "target": HEAD_TARGET[head], "n_rows": int(rows.sum()), "best_iter": best, "rounds": rounds,
            "target_range": [float(np.nanmin(tgt[rows])), float(np.nanmax(tgt[rows]))],
            "features": names, "params": {k: v for k, v in lgb_params(head).items() if k != "num_threads"}}
    if head not in CLASSIFIERS:
        r = tgt - oof
        m = rows & np.isfinite(r)
        info["qtab"] = qtable(r[m], df["Type"].to_numpy()[m], size_class(df["Height"].to_numpy()[m]))
        info["oof_r2"] = float(1 - np.mean(r[m] ** 2) / np.var(tgt[m]))
    else:
        m = rows & np.isfinite(oof)
        p = np.clip(oof[m], 1e-9, 1 - 1e-9)
        y = tgt[m]
        info["oof_logloss"] = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
        info["oof_brier_skill"] = float(1 - np.mean((p - y) ** 2) / np.var(y))
    imp = final.feature_importance("gain")
    info["importance_gain"] = dict(sorted(zip(names, (imp / imp.sum()).round(5).tolist(), strict=True),
                                          key=lambda kv: -kv[1])[:40])
    json.dump(info, open(os.path.join(md, f"{head}.json"), "w"), indent=1)
    status(f"fit {a.split} {head}: best {best} rounds {rounds} "
           + (f"oof_r2 {info.get('oof_r2'):.3f}" if "oof_r2" in info else f"oof_bss {info['oof_brier_skill']:.3f}"))


def stage_ranges(a):
    """Write each regression head's training-target range into its model json (the clip bounds of StructHeads)."""
    df = load_sample(a.split)
    md = os.path.join(OUT, a.split, "models")
    for head in HEADS:
        p = os.path.join(md, f"{head}.json")
        info = json.load(open(p))
        rows = head_rows(df, head)
        tgt = df[HEAD_TARGET[head]].to_numpy().astype(np.float64)
        info["target_range"] = [float(np.nanmin(tgt[rows])), float(np.nanmax(tgt[rows]))]
        json.dump(info, open(p, "w"), indent=1)
        log(head, info["target_range"])
    status(f"ranges {a.split}: training-target ranges recorded (regression means are clipped to them)")


# ------------------------------------------------------------------------------------------------ the heads object
class StructHeads:
    """Loaded production heads + residual tables + AR(1) tables of one split. Cheap per-tree calls (numpy in/out)."""

    def __init__(self, split: str):
        import lightgbm as lgb
        md = os.path.join(OUT, split, "models")
        self.split = split
        self.models, self.info = {}, {}
        for h in HEADS:
            p = os.path.join(md, f"{h}.txt")
            if os.path.exists(p):
                self.models[h] = lgb.Booster(model_file=p)
                self.info[h] = json.load(open(os.path.join(md, f"{h}.json")))
        self.names = feature_names(False)
        self.names_g = feature_names(True)
        self.q = {h: self._qarr(self.info[h]["qtab"]) for h in self.info if "qtab" in self.info[h]}
        arp = os.path.join(OUT, split, "ar.parquet")
        self.ar = self._ar_arrays(pl.read_parquet(arp)) if os.path.exists(arp) else None

    @classmethod
    def load(cls, split: str = "DEV-A") -> StructHeads:
        return cls(split)

    @staticmethod
    def climate_columns() -> list[str]:
        return [f"{c}_{s}" for s in ("y", "y1") for c in climate_levels()]

    @staticmethod
    def _qarr(tab):
        """-> Q[Type + 1, scls + 1, NQ] with fallbacks (missing (Type, scls) -> Type pooled -> global)."""
        Q = np.full((N_PFT + 1, len(SIZE_EDGES) + 2, NQ), np.nan)
        g = [r for r in tab if r["Type"] == -1][0]["q"]
        Q[:] = np.asarray(g)
        for r in tab:
            if r["Type"] >= 0 and r["scls"] == -1:
                Q[r["Type"] + 1, :] = np.asarray(r["q"])
        for r in tab:
            if r["Type"] >= 0 and r["scls"] >= 0:
                Q[r["Type"] + 1, r["scls"] + 1] = np.asarray(r["q"])
        return Q

    @staticmethod
    def _ar_arrays(ar: pl.DataFrame):
        nT, nS, K = N_PFT + 1, len(SIZE_EDGES) + 2, len(LATENT)
        rho = np.zeros((nT, nS, K))
        sig = np.ones((nT, nS, K))
        L = np.tile(np.eye(K), (nT, nS, 1, 1))
        for r in ar.sort("level").iter_rows(named=True):   # level 0 = global, 1 = Type, 2 = Type x scls
            ti = slice(None) if r["Type"] < 0 else r["Type"] + 1
            si = slice(None) if r["scls"] < 0 else r["scls"] + 1
            rho[ti, si] = np.asarray(r["rho"])
            sig[ti, si] = np.asarray(r["sigma"])
            L[ti, si] = np.asarray(r["chol"]).reshape(K, K)
        return {"rho": rho, "sigma": sig, "L": L}

    # ---- features
    def features(self, frame: pl.DataFrame) -> pl.DataFrame:
        return add_features(frame)

    def X(self, feat: pl.DataFrame, g=None) -> np.ndarray:
        if g is None:
            return matrix(feat, self.names)
        return np.column_stack([matrix(feat, self.names), np.asarray(g, dtype=np.float32)])

    # ---- means (regression means clipped to the head's training-target range: the linear leaves extrapolate, and
    # unclipped log-scale heads reached exp(28) on held-out climate)
    def _pred(self, h, X):
        v = self.models[h].predict(X)
        rg = self.info[h].get("target_range")
        if rg is not None and h not in CLASSIFIERS:
            v = np.clip(v, rg[0], rg[1])
        return v

    def predict(self, X: np.ndarray) -> dict:
        out = {}
        for h, k in (("gclf", "p_gneg"), ("gneg", "mu_gneg"), ("gpos", "mu_gpos"), ("gall", "mu_gall"),
                     ("wclf", "q_w"), ("wreg", "mu_w")):
            if h in self.models:
                out[k] = self._pred(h, X)
        return out

    def predict_size(self, X: np.ndarray, G: np.ndarray) -> dict:
        Xg = np.column_stack([X, np.asarray(G, dtype=np.float32)])
        return {h: self._pred(h, Xg) for h in SIZE_HEADS if h in self.models}

    # ---- quantile maps
    def _qf(self, head, typ, scls, u):
        """Residual quantile Q_head(u | Type, scls) by linear interpolation in the 101-point table."""
        Q = self.q[head][np.asarray(typ, np.int64) + 1, np.asarray(scls, np.int64) + 1]
        x = np.clip(np.asarray(u, np.float64), 0.0, 1.0) * (NQ - 1)
        i = np.minimum(np.floor(x).astype(np.int64), NQ - 2)
        w = x - i
        ar = np.arange(len(x))
        return Q[ar, i] * (1 - w) + Q[ar, i + 1] * w

    def _cdf(self, head, typ, scls, r):
        """Empirical residual CDF F_head(r | Type, scls), vectorised over the (few) distinct (Type, scls) groups."""
        ti = np.asarray(typ, np.int64) + 1
        si = np.asarray(scls, np.int64) + 1
        r = np.asarray(r, np.float64)
        grid = np.linspace(0, 1, NQ)
        out = np.full(r.shape, np.nan)
        key = ti * 100 + si
        for k in np.unique(key):
            m = key == k
            q_ = self.q[head][k // 100, k % 100]
            out[m] = np.interp(r[m], q_, grid)
        return out

    # ---- sampling
    def sample(self, X: np.ndarray, z: np.ndarray, typ, scls) -> dict:
        """z [n, 7] latent normal scores (LATENT order) -> G, W, size changes (given that G) and the derived new
        agb / vegc / LAI / fpc_ind / D95 multipliers. Pure function of (X, z)."""
        from scipy.special import ndtr
        u = ndtr(z)
        m = self.predict(X)
        p = m["p_gneg"]
        uG = u[:, 0]
        neg = uG < p
        un = np.where(neg, 1.0 - uG / np.maximum(p, 1e-12), 0.5)      # lower u -> more negative G
        up = np.where(neg, 0.5, (uG - p) / np.maximum(1 - p, 1e-12))
        Gn = -np.exp(m["mu_gneg"] + self._qf("gneg", typ, scls, un))
        Gp = np.maximum(0.0, m["mu_gpos"] + self._qf("gpos", typ, scls, up))
        G = np.where(neg, Gn, Gp)
        q = m["q_w"]
        uW = u[:, 1]
        wpos = uW > 1.0 - q
        uw = np.where(wpos, (uW - (1.0 - q)) / np.maximum(q, 1e-12), 0.5)
        W = np.where(wpos, np.exp(m["mu_w"] + self._qf("wreg", typ, scls, uw)), 0.0)
        sz = self.predict_size(X, G)
        out = {"G": G, "W": W, "p_gneg": p, "q_w": q}
        for j, h in enumerate(SIZE_HEADS):
            out[h] = sz[h] + self._qf(h, typ, scls, u[:, 2 + j])
        return out

    def ar_step(self, z: np.ndarray, typ, scls, normals: np.ndarray) -> np.ndarray:
        ti = np.asarray(typ, np.int64) + 1
        si = np.asarray(scls, np.int64) + 1
        rho, sig, L = self.ar["rho"][ti, si], self.ar["sigma"][ti, si], self.ar["L"][ti, si]
        e = np.einsum("nij,nj->ni", L, normals)
        return rho * z + sig * e

    def stationary(self, typ, scls, normals: np.ndarray) -> np.ndarray:
        """A draw from the stationary latent distribution (recruits, a 1985 start)."""
        ti = np.asarray(typ, np.int64) + 1
        si = np.asarray(scls, np.int64) + 1
        rho, sig, L = self.ar["rho"][ti, si], self.ar["sigma"][ti, si], self.ar["L"][ti, si]
        sd = sig / np.sqrt(np.maximum(1 - rho ** 2, 1e-6))
        return sd * np.einsum("nij,nj->ni", L, normals)

    def residual_z(self, X, typ, scls, G, W, sizes: dict, rng=None) -> np.ndarray:
        """Latent normal scores of an observed transition (inverse of sample). sizes: head -> observed target.
        NaN where the target is undefined (e.g. censored G)."""
        from scipy.special import ndtri
        rng = rng or np.random.default_rng(0)
        m = self.predict(X)
        p, q = m["p_gneg"], m["q_w"]
        G = np.asarray(G, np.float64)
        neg = G < 0
        rn = np.where(neg, np.log(np.where(neg, -G, 1.0)) - m["mu_gneg"], 0.0)
        rp = np.where(neg, 0.0, G - m["mu_gpos"])
        Fn = self._cdf("gneg", typ, scls, rn)
        Fp = self._cdf("gpos", typ, scls, rp)
        uG = np.where(neg, p * (1.0 - Fn), p + (1.0 - p) * Fp)
        uG = np.where(np.isfinite(G), uG, np.nan)
        W = np.asarray(W, np.float64)
        rw = np.where(W > 0, np.log(np.where(W > 0, W, 1.0)) - m["mu_w"], 0.0)
        Fw = self._cdf("wreg", typ, scls, rw)
        uW = np.where(W > 0, (1.0 - q) + q * Fw, (1.0 - q) * rng.random(len(W)))
        uW = np.where(np.isfinite(W), uW, np.nan)
        cols = [uG, uW]
        sz = self.predict_size(X, np.where(np.isfinite(G), G, 0.0))
        for h in SIZE_HEADS:
            cols.append(self._cdf(h, typ, scls, np.asarray(sizes[h], np.float64) - sz[h]))
        u = np.clip(np.column_stack(cols), 1e-4, 1 - 1e-4)
        return ndtri(u)


# ------------------------------------------------------------------------------------------------ AR stage
def _z_from_oof(df: pl.DataFrame, split: str) -> pl.DataFrame:
    """Normal scores of every base training row from the OOF predictions (same map as StructHeads.residual_z)."""
    from scipy.special import ndtri
    H = StructHeads.__new__(StructHeads)
    H.info = {h: json.load(open(os.path.join(OUT, split, "models", f"{h}.json"))) for h in OOF_HEADS}
    H.q = {h: StructHeads._qarr(H.info[h]["qtab"]) for h in H.info if "qtab" in H.info[h]}
    o = df.select("rid")
    for h in OOF_HEADS:
        o = o.join(pl.read_parquet(os.path.join(OUT, split, "oof", f"{h}.parquet")).rename({"oof": h}), on="rid",
                   how="left")
    d = df.join(o, on="rid", how="left")
    typ = d["Type"].to_numpy().astype(np.int64)
    scl = size_class(d["Height"].to_numpy())
    G = np.where(d["g_ok"].to_numpy(), d["G_y1"].to_numpy().astype(np.float64), np.nan)
    p = d["gclf"].to_numpy()
    neg = G < 0
    rn = np.where(neg, np.log(np.where(neg, -G, 1.0)) - d["gneg"].to_numpy(), 0.0)
    rp = np.where(neg, 0.0, G - d["gpos"].to_numpy())
    Fn = H._cdf("gneg", typ, scl, rn)
    Fp = H._cdf("gpos", typ, scl, rp)
    uG = np.where(np.isfinite(G), np.where(neg, p * (1 - Fn), p + (1 - p) * Fp), np.nan)
    W = np.where(d["w_ok"].to_numpy() & (d["cenW_y1"].to_numpy() == 0), d["W_y1"].to_numpy().astype(np.float64),
                 np.nan)
    q = d["wclf"].to_numpy()
    rw = np.where(W > 0, np.log(np.where(W > 0, W, 1.0)) - d["wreg"].to_numpy(), 0.0)
    Fw = H._cdf("wreg", typ, scl, rw)
    rng = np.random.default_rng(7)
    uW = np.where(np.isfinite(W), np.where(W > 0, (1 - q) + q * Fw, (1 - q) * rng.random(len(W))), np.nan)
    cols = {"zG": uG, "zW": uW}
    for h in SIZE_HEADS:
        r = d[HEAD_TARGET[h]].to_numpy().astype(np.float64) - d[h].to_numpy()
        r = np.where(np.isfinite(G), r, np.nan)
        cols[f"z{h}"] = H._cdf(h, typ, scl, np.where(np.isfinite(r), r, 0.0))
        cols[f"z{h}"] = np.where(np.isfinite(r), cols[f"z{h}"], np.nan)
    z = {k: ndtri(np.clip(v, 1e-4, 1 - 1e-4)) for k, v in cols.items()}
    return d.select("rid", "member", "Cell", "Patch", "Type", "ID", "Year", "fold", "Height").with_columns(
        scls=pl.Series(scl), **{k: pl.Series(v) for k, v in z.items()})


def ar_fit(Z0: np.ndarray, Z1: np.ndarray) -> dict:
    K = Z0.shape[1]
    rho, sd = np.zeros(K), np.ones(K)
    for j in range(K):
        m = np.isfinite(Z0[:, j]) & np.isfinite(Z1[:, j])
        if m.sum() > 50:
            rho[j] = float(np.corrcoef(Z0[m, j], Z1[m, j])[0, 1])
            sd[j] = float(np.nanstd(Z1[:, j]))
    rho = np.clip(rho, -0.99, 0.99)
    E = Z1 - rho * Z0
    ok = np.all(np.isfinite(E), axis=1)
    C = np.corrcoef(E[ok].T) if ok.sum() > 50 else np.eye(K)
    C = np.where(np.isfinite(C), C, 0.0)
    np.fill_diagonal(C, 1.0)
    w, V = np.linalg.eigh(C)
    C = (V * np.maximum(w, 1e-6)) @ V.T
    d_ = np.sqrt(np.diag(C))
    C = C / np.outer(d_, d_)
    return {"rho": rho.tolist(), "sigma": (sd * np.sqrt(1 - rho ** 2)).tolist(), "sd_z": sd.tolist(),
            "chol": np.linalg.cholesky(C).ravel().tolist(), "corr": C.ravel().tolist(), "n_pairs": int(ok.sum())}


def bvn_cdf(h, k, rho):
    """Bivariate standard normal P(X < h, Y < k; rho), vectorised (Owen's T form)."""
    from scipy.special import ndtr, owens_t
    h = np.asarray(h, np.float64)
    k = np.asarray(k, np.float64)
    s = np.sqrt(max(1 - rho * rho, 1e-12))
    hs = np.where(h == 0, 1e-12, h)
    ks = np.where(k == 0, 1e-12, k)
    t = 0.5 * (ndtr(h) + ndtr(k)) - owens_t(hs, (k - rho * h) / (hs * s)) - owens_t(ks, (h - rho * k) / (ks * s))
    return t - np.where(h * k < 0, 0.5, 0.0)


def hurdle_rho(q0, q1, pos0, pos1) -> float:
    """Latent correlation of the W hurdle: W>0 <=> z > Phi^-1(1 - q). The randomised normal score of a W == 0 row
    carries no information, so the AR(1) rho of W is estimated by maximum likelihood on the pair's joint zero / non-zero
    outcome (a tetrachoric correlation with per-row thresholds), grid 0..0.99."""
    from scipy.special import ndtri
    a0 = ndtri(np.clip(1 - q0, 1e-6, 1 - 1e-6))
    a1 = ndtri(np.clip(1 - q1, 1e-6, 1 - 1e-6))
    best, br = -np.inf, 0.0
    for r in np.linspace(0.0, 0.99, 100):
        p00 = np.clip(bvn_cdf(a0, a1, r), 1e-12, 1)
        p0_ = np.clip(1 - q0, 1e-12, 1)
        p_0 = np.clip(1 - q1, 1e-12, 1)
        p01 = np.clip(p0_ - p00, 1e-12, 1)
        p10 = np.clip(p_0 - p00, 1e-12, 1)
        p11 = np.clip(1 - p0_ - p_0 + p00, 1e-12, 1)
        ll = np.sum(np.where(pos0, np.where(pos1, np.log(p11), np.log(p10)), np.where(pos1, np.log(p01),
                                                                                       np.log(p00))))
        if ll > best:
            best, br = ll, float(r)
    return br


def stage_ar(a):
    df = load_sample(a.split)
    base = df.filter(pl.col("u_hash") < U_BASE)
    Z = _z_from_oof(base, a.split)
    q = pl.read_parquet(os.path.join(OUT, a.split, "oof", "wclf.parquet")).rename({"oof": "qW"})
    Z = Z.join(q, on="rid", how="left").join(base.select("rid", pl.col("wpos_t").alias("posW")), on="rid", how="left")
    zc = [f"z{k}" for k in LATENT]
    nxt = Z.select(["member", "Cell", "Patch", "Type", "ID", pl.col("Year") - 1] + [pl.col(c).alias(c + "_n")
                                                                                   for c in zc + ["qW", "posW"]])
    pr = Z.join(nxt, on=["member", "Cell", "Patch", "Type", "ID", "Year"], how="inner")
    Z.write_parquet(os.path.join(sdir(a.split), "oof_z.parquet"))
    rows = []
    for lev, grp in ((0, []), (1, ["Type"]), (2, ["Type", "scls"])):
        for key, g in (pr.group_by(grp) if grp else [((None,), pr)]):
            if g.height < 2000:
                continue
            f = ar_fit(g.select(zc).to_numpy(), g.select([c + "_n" for c in zc]).to_numpy())
            hw = g.filter(pl.col("qW").is_not_null() & pl.col("qW_n").is_not_null() & pl.col("posW").is_not_null()
                          & pl.col("posW_n").is_not_null())
            if hw.height > 2000:   # W: tetrachoric rho replaces the (uninformative) randomised-score correlation
                hw = hw.sample(min(hw.height, 200_000), seed=3)
                rw = hurdle_rho(hw["qW"].to_numpy(), hw["qW_n"].to_numpy(), hw["posW"].to_numpy() > 0.5,
                                hw["posW_n"].to_numpy() > 0.5)
                j = LATENT.index("W")
                f["rho_W_randomised_score"] = f["rho"][j]
                f["rho"][j] = rw
                f["sigma"][j] = f["sd_z"][j] * float(np.sqrt(1 - rw ** 2))
            k = dict(zip(grp, key if isinstance(key, tuple) else (key,), strict=False)) if grp else {}
            rows.append({"level": lev, "Type": int(k.get("Type", -1)), "scls": int(k.get("scls", -1)), **f})
    ar = pl.DataFrame(rows)
    ar.write_parquet(os.path.join(sdir(a.split), "ar.parquet"))
    summ = ar.filter(pl.col("level") <= 1).select("level", "Type", "n_pairs", "rho", "sd_z").to_dicts()
    json.dump({"pairs": pr.height, "tables": summ, "latent": LATENT}, open(os.path.join(sdir(a.split), "ar.json"), "w"),
              indent=1)
    status(f"ar {a.split}: {pr.height} OOF pairs, {ar.height} tables; global rho "
           + ", ".join(f"{k}={r:.2f}" for k, r in zip(LATENT, rows[0]["rho"], strict=True)))


# ------------------------------------------------------------------------------------------------ eval stage
def eval_filter(member: str, split: str) -> pl.Expr:
    mm = split_members(split)
    f5 = (pl.col("fold") == HOLD_FOLD) & (pl.col("u_hash") < U_EV_F5)
    if member in mm["train"]:
        return f5
    return f5 | (pl.col("u_hash") < U_EV_ALL)


def stage_eval(a):
    H = StructHeads.load(a.split)
    od = sdir(a.split, "pred")
    for member in a.member:
        t0 = time.time()
        rl.assert_usable(member)
        df = read_member_rows(member, pl.lit(True), eval_filter(member, a.split), need_prev=True)
        df = df.join(tr.join_climate(df.select("gcm", "traj", "seed", "Cell", "Year").unique(), cols=["tmean_ann"],
                                     years=("y1",)).select("gcm", "traj", "seed", "Cell", "Year", "tmean_ann_y1"),
                     on=["gcm", "traj", "seed", "Cell", "Year"], how="left", maintain_order="left")
        X = H.X(df)
        m = H.predict(X)
        g_true = np.where(df["g_ok"].to_numpy(), df["G_y1"].to_numpy().astype(np.float64), np.nan)
        tf = H.predict_size(X, np.where(np.isfinite(g_true), g_true, 0.0))
        ch = H.predict_size(X, m["mu_gall"])
        keep = (["member", "gcm", "traj", "seed", "Year", "Cell", "Patch", "Type", "ID", "u_hash", "fold", "fate_y1",
                 "present", "g_ok", "w_ok", "G_y1", "cenG_y1", "G_y", "cenG_y", "W_y1", "cenW_y1", "W_y", "cenW_y",
                 "c_y", "c_y1", "Height", "Height_y1", "agb", "agb_y1", "vegc", "vegc_y1", "LAI", "LAI_y1",
                 "fpc_ind", "fpc_ind_y1", "D95", "D95_y1", "d_agb_prev", "SLA", "Wooddens", "tmean_ann_y1"]
                + [f"{c}_ym1" for c in ("vegc", "LAI", "fpc_ind", "D95")]
                + [v for v in HEAD_TARGET.values() if v != "G_y1"])
        out = df.select(keep).with_columns(**{k: pl.Series(v) for k, v in m.items()},
                                           **{f"tf_{h}": pl.Series(v) for h, v in tf.items()},
                                           **{f"ch_{h}": pl.Series(v) for h, v in ch.items()})
        out.write_parquet(os.path.join(od, f"{member}.parquet"))
        log(f"eval {member}: {out.height} rows ({time.time() - t0:.0f} s)")
        status(f"eval {a.split} {member}: {out.height} rows")


# ------------------------------------------------------------------------------------------------ report stage
def r2(y, yhat) -> float:
    m = np.isfinite(y) & np.isfinite(yhat)
    if m.sum() < 30:
        return float("nan")
    return float(1 - np.mean((y[m] - yhat[m]) ** 2) / np.var(y[m]))


def corr2(a, b) -> float:
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 30:
        return float("nan")
    return float(np.corrcoef(a[m], b[m])[0, 1] ** 2)


def auc(y, s) -> float:
    from scipy.stats import rankdata
    m = np.isfinite(y) & np.isfinite(s)
    y, s = y[m], s[m]
    n1 = y.sum()
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    rk = rankdata(s)
    return float((rk[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def smear(split: str, head: str) -> float:
    info = json.load(open(os.path.join(OUT, split, "models", f"{head}.json")))
    return [r for r in info["qtab"] if r["Type"] == -1][0]["mean_exp"]


def score_frame(d: pl.DataFrame, split: str) -> dict:
    """Teacher-forced skill on one evaluation set beside the two nulls, on identical rows."""
    f = lambda c: d[c].to_numpy().astype(np.float64)  # noqa: E731
    out = {"rows": d.height}
    g_ok = d["g_ok"].to_numpy() & d["cenG_y"].is_in([0, 5]).to_numpy()
    G1, G0 = f("G_y1"), f("G_y")
    # G level (mean head) + nulls; and the sign
    m = g_ok & np.isfinite(G0)
    out["G"] = {"n": int(m.sum()), "model_r2": r2(G1[m], f("mu_gall")[m]), "persistence_r2": corr2(G0[m], G1[m]),
                "copy_r2": r2(G1[m], G0[m])}
    s_ok = d["gsign_t"].is_not_null().to_numpy() & d["cenG_y"].is_in([0, 1, 2, 5]).to_numpy()
    ys = f("gsign_t")
    p = f("p_gneg")
    out["G_sign"] = {"n": int(s_ok.sum()), "share_neg": float(np.nanmean(ys[s_ok])),
                     "model_auc": auc(ys[s_ok], p[s_ok]),
                     "model_brier_skill": float(1 - np.mean((p[s_ok] - ys[s_ok]) ** 2) / np.var(ys[s_ok])),
                     "copy_sign_accuracy": float(np.mean((G0[s_ok] < 0) == (ys[s_ok] == 1))),
                     "model_sign_accuracy": float(np.mean((p[s_ok] > 0.5) == (ys[s_ok] == 1))),
                     "copy_brier_skill": float(1 - np.mean(((G0[s_ok] < 0) - ys[s_ok]) ** 2) / np.var(ys[s_ok]))}
    # W
    w_ok = d["w_ok"].to_numpy() & (f("cenW_y1") == 0) & (f("cenW_y") == 0)
    W1, W0 = f("W_y1"), f("W_y")
    EW = f("q_w") * np.exp(f("mu_w")) * smear(split, "wreg")
    out["W"] = {"n": int(w_ok.sum()), "share_pos": float(np.mean(W1[w_ok] > 0)),
                "model_r2": r2(W1[w_ok], EW[w_ok]), "persistence_r2": corr2(W0[w_ok], W1[w_ok]),
                "copy_r2": r2(W1[w_ok], W0[w_ok]),
                "model_auc_pos": auc((W1[w_ok] > 0).astype(float), f("q_w")[w_ok]),
                "copy_auc_pos": auc((W1[w_ok] > 0).astype(float), W0[w_ok])}
    # size changes: teacher-forced (true G) and chained (predicted mean G), beside the nulls
    agb, agb1, dprev = f("agb"), f("agb_y1"), f("d_agb_prev")
    prev = {"dlagb": np.log(agb / (agb - dprev)), "dlvegc": np.log(f("vegc") / f("vegc_ym1")),
            "dlai": f("LAI") - f("LAI_ym1"), "dlfpc": np.log(f("fpc_ind") / f("fpc_ind_ym1")),
            "dld95": np.log(f("D95") / f("D95_ym1"))}
    sz_ok = d["g_ok"].to_numpy()
    for h in SIZE_HEADS:
        y = f(HEAD_TARGET[h])
        pv = prev[h]
        m = sz_ok & np.isfinite(y) & np.isfinite(pv)
        out[h] = {"n_all": int((sz_ok & np.isfinite(y)).sum()), "n": int(m.sum()),
                  "model_tf_r2_all": r2(y[sz_ok], f(f"tf_{h}")[sz_ok]),
                  "model_tf_r2": r2(y[m], f(f"tf_{h}")[m]), "model_chain_r2": r2(y[m], f(f"ch_{h}")[m]),
                  "persistence_r2": corr2(pv[m], y[m]), "copy_r2": r2(y[m], pv[m])}
    # the round-1 basis: absolute agb change
    m = sz_ok & np.isfinite(dprev) & np.isfinite(agb1)
    d1 = agb1 - agb
    out["d_agb"] = {"n": int(m.sum()), "model_tf_r2": r2(d1[m], (agb * np.expm1(f("tf_dlagb")))[m]),
                    "model_chain_r2": r2(d1[m], (agb * np.expm1(f("ch_dlagb")))[m]),
                    "persistence_r2": corr2(dprev[m], d1[m]), "copy_r2": r2(d1[m], dprev[m]),
                    "stationary_copy_bound": float(2 * np.sqrt(corr2(dprev[m], d1[m])) - 1)}
    # Height from the rules' allometry on the predicted agb (chained)
    coef = rl.load_allometry(split)
    hm = sz_ok & np.isfinite(f("Height_y1"))
    agb_hat = agb * np.exp(f("ch_dlagb"))
    Hhat = rl.predict_height(agb_hat[hm], f("Wooddens")[hm], f("SLA")[hm], d["Type"].to_numpy()[hm], coef)
    H1, H0 = f("Height_y1")[hm], f("Height")[hm]
    out["dHeight"] = {"n": int(hm.sum()), "model_chain_allometry_r2": r2(H1 - H0, Hhat - H0),
                      "note": "allometry from predicted agb; height CHANGE R2 (round 1 persistence 0.09-0.41)"}
    return out


def stage_report(a):
    mm = split_members(a.split)
    pdir = os.path.join(OUT, a.split, "pred")
    sets = {}
    for f in sorted(glob.glob(os.path.join(pdir, "*.parquet"))):
        member = os.path.basename(f)[:-8]
        d = pl.read_parquet(f)
        is_train = member in mm["train"]
        if is_train:
            sets[f"{member}|fold5"] = d.filter(pl.col("fold") == HOLD_FOLD)
        else:
            sets[f"{member}|all_dev"] = d.filter(pl.col("u_hash") < U_EV_ALL)
            sets[f"{member}|fold5"] = d.filter((pl.col("fold") == HOLD_FOLD) & (pl.col("u_hash") < U_EV_F5))
    res = {k: score_frame(v, a.split) for k, v in sets.items()}
    fit = {h: {k: v for k, v in json.load(open(p)).items() if k in ("n_rows", "best_iter", "rounds", "oof_r2",
                                                                       "oof_brier_skill", "importance_gain")}
           for h in HEADS if os.path.exists(p := os.path.join(OUT, a.split, "models", f"{h}.json"))}
    arj = os.path.join(OUT, a.split, "ar.json")
    rep = {"item": "B1", "split": a.split, "train_members": mm["train"], "train_folds": list(TRAIN_FOLDS),
           "basis": "teacher-forced: true tree state at y, true climate of y and y+1; size heads given TRUE G_{y+1} "
                    "(tf) or the predicted mean G (chain). Nulls on the same rows (stems present at y-1, y, y+1).",
           "null_definitions": {"persistence": "corr(x_prev, x_next)^2 (fitted line)",
                                "copy": "1 - mean((x_next - x_prev)^2)/var(x_next) (not refitted)",
                                "preregistered": "copy <= 2 sqrt(persistence) - 1 <= persistence; equality iff "
                                                 "stationary; round-1 d agb persistence 0.82-0.95, copy 0.70-0.91"},
           "sets": res, "fit": fit, "ar": json.load(open(arj)) if os.path.exists(arj) else None}
    os.makedirs(REPORTS, exist_ok=True)
    json.dump(rep, open(os.path.join(REPORTS, f"r2_B1_{a.split}.json" if a.split != "DEV-A" else "r2_B1.json"), "w"),
              indent=1)
    for k, v in res.items():
        log(k, {t: {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v[t].items()
                    if kk in ("model_r2", "model_tf_r2", "model_chain_r2", "persistence_r2", "copy_r2", "model_auc")}
                for t in ("G", "G_sign", "W", "dlagb", "d_agb", "dlai")})
    status(f"report {a.split}: {len(res)} evaluation sets -> _reports/r2_B1.json")


# ------------------------------------------------------------------------------------------------ SLURM
def jcf(name, cmd, cpus=16, time_="03:00:00", array=None, dep=None, part="standard", qos="short"):
    os.makedirs(LOGDIR, exist_ok=True)
    jd = os.path.join(XDE, "_jobs")
    os.makedirs(jd, exist_ok=True)
    p = os.path.join(jd, f"{name}.jcf")
    lines = ["#!/bin/bash", f"#SBATCH --job-name={name}", "#SBATCH --account=waldspektrum",
             f"#SBATCH --partition={part}", f"#SBATCH --qos={qos}", f"#SBATCH --cpus-per-task={cpus}",
             f"#SBATCH --time={time_}",
             f"#SBATCH --output={LOGDIR}/{name}.%A" + ("_%a" if array else "") + ".out"]
    if array:
        lines.append(f"#SBATCH --array={array}")
    if dep:
        lines.append(f"#SBATCH --dependency={dep}")
    lines += ["set -eu", f"cd {REPO}", "export PYTHONUNBUFFERED=1", cmd, 'echo "=== JOB DONE exit=$? ==="']
    open(p, "w").write("\n".join(lines) + "\n")
    out = subprocess.run(["sbatch", "--parsable", p], capture_output=True, text=True, check=True).stdout.strip()
    jid = out.split(";")[0]
    status(f"submitted {name} job {jid}" + (f" array {array}" if array else "") + (f" dep {dep}" if dep else ""))
    return jid


def stage_submit(a):
    me = os.path.abspath(__file__)
    S = a.split
    dep = a.dep
    if a.what in ("sample", "all"):
        dep = "afterok:" + jcf(f"X-de-B1-sample-{S}", f"{PY} {me} sample --split {S}", cpus=16, time_="01:30:00")
    if a.what in ("fit", "all"):
        heads = " ".join(HEADS)
        cmd = (f"H=({heads}); {PY} {me} fit --split {S} --head ${{H[$SLURM_ARRAY_TASK_ID]}}")
        dep = "afterok:" + jcf(f"X-de-B1-fit-{S}", cmd, cpus=16, time_="06:00:00", array=f"0-{len(HEADS) - 1}",
                               dep=dep)
        dep = "afterok:" + jcf(f"X-de-B1-ar-{S}", f"{PY} {me} ar --split {S}", cpus=8, time_="01:00:00", dep=dep)
    if a.what in ("eval", "all"):
        mem = split_members(S)["all"]
        ms = " ".join(mem)
        cmd = f"M=({ms}); {PY} {me} eval --split {S} --member ${{M[$SLURM_ARRAY_TASK_ID]}}"
        dep = "afterok:" + jcf(f"X-de-B1-eval-{S}", cmd, cpus=16, time_="03:00:00", array=f"0-{len(mem) - 1}",
                               dep=dep)
    if a.what in ("eval", "report", "all"):
        jcf(f"X-de-B1-report-{S}", f"{PY} {me} report --split {S}", cpus=8, time_="01:00:00", dep=dep)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["sample", "fit", "ranges", "ar", "eval", "report", "submit"])
    ap.add_argument("--split", default="DEV-A")
    ap.add_argument("--head", choices=HEADS)
    ap.add_argument("--member", nargs="*")
    ap.add_argument("--what", default="all", choices=["sample", "fit", "eval", "report", "all"])
    ap.add_argument("--dep", default=None)
    a = ap.parse_args(argv)
    {"sample": stage_sample, "fit": stage_fit, "ranges": stage_ranges, "ar": stage_ar, "eval": stage_eval,
     "report": stage_report, "submit": stage_submit}[a.stage](a)


if __name__ == "__main__":
    main()
