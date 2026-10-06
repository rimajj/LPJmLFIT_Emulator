"""explore_de_sh_patchheads.py — LINE X, Germany data-driven emulator, shared item SH13: PATCH-LEVEL HEADS.

Three gradient-boosted heads that every rollout track (per-tree boosted, rule-based "structured") calls once per patch
and year inside the SH6 engine stepper:

  (a) FIRE      the patch fire fraction f of the y -> y+1 step. The original model kills every non-hard survivor of the
                hazard draw with probability (1 - resist[Type]) * f, with f >= 0.001 (soil/fire_prob.c floor).
                Target: SH4 fire_E_y1 (non-hard deaths minus summed non-hard hazards), whose expectation is f * D with
                D = fire_D_y1 = sum over non-hard present stems of (1 - resist) (1 - mort).
                f = 0.001 + exp(score). FIT WITHOUT CLIPPING: E is negative in ~85 % of patch-years (it is dominated by
                the Bernoulli noise of the hazard draws, variance sum m(1-m) ~ 0.35 per patch, against a fire signal
                of ~0.01), so a clipped per-patch target keeps only the positive noise (~9x the real excess, measured
                by the coordinator). We fit a Poisson (log link) model of the EXCESS OVER THE FLOOR, label
                y = E / D - 0.001 (unclipped, often negative), weight D, offset log D implied by the rate form:
                    loss = sum D (e^s - y s),  grad = D (e^s - y),  hess = D e^s
                so D e^s estimates E - 0.001 D and every leaf matches its own total excess exactly (a leaf whose
                total is negative is pushed toward the floor, step-limited by max_delta_step). Rows with D = 0 carry
                no information and are dropped. (A first version used the exact likelihood of f = 0.001 + e^s,
                whose score equation matches totals only weighted by e^s / f: it over-predicted Germany-wide fire
                excess by 9-10 % even in sample; kept as _gates_v1_floorweighted_fire.json.)
                ⚠ E also contains every death channel the rule library does not carry (negative-pool kill, the
                bioclimatic `survive` kill, the sapling leaf-carbon kill), so the learned f is "fire + unexplained
                non-hazard deaths of non-hard stems" — exactly what a stepper that applies the rule hazards and then
                this f needs, but not a pure fire rate.
  (b) RECRUIT   the number of recruits first printed (> 5 m) at y+1 per patch: Poisson mean + negative-binomial
                dispersion per predicted-mean decile (method of moments on the validation fold).
  (c) ENTRY     the entry state of a recruit: quantile heads (q05..q95) of Height - 5 m and ln Age at entry, and an
                empirical joint table of (Height, Age, c, G, cenG) at entry by Type x climate tercile.

Each head = state booster B0 (+ a constant base score) and a climate booster B1 fitted on B0's residual through
init_score (linear_tree: piecewise-linear in climate); prediction score = base + B0 + kappa * B1 (kappa = 0 is the
climate-blind head; kappa is chosen on the validation fold from a grid and stored as the default).

FEATURES (every one regenerable from the rollout state — the audit table is FEATURE_AUDIT, printed into meta.json)
  state at y     n_live_y, sum_fpc_y, sum_agb_y, patch_lai_y (sum LAI * fpc_ind of living printed stems, a proxy),
                 grass<t>_{fpc,LAI,agb}_y, agb_dead_y (agb of the stems flagged dead at y: the stepper's own previous
                 step, kept in aux_patch), cell_share_t0..6 (stem share by Type in the cell), cell_stems_per_patch
  this step      fpc_surv_y1 = sum_fpc_y - loss_y1 (fpc at y of the stems that survive the step and stay printed —
                 the stepper must decide deaths / hidden BEFORE calling the recruit head), n_eligible_pft_y1
  cover loss     relative to the recruitment year y+1: L0 = frac_loss_y1 (this step), L1 = frac_loss_lag0 (the loss
                 during year y), L2_5 = sum of lags 1..4, L6_20 = sum of lags 5..19 (NaN where no history; the
                 engine's loss_ring holds exactly lags 0..19)
  climate y+1    via explore_de_sh_trans.join_climate (THE shared join): absolute + anomaly, 20-yr means. CO2, wind,
                 lon/lat and cell ids are never inputs.

SPLIT  a parameter (registry v2 `splits`): train = role "train" members, cells is_dev & fold <= 4, early stopping on
       --val-fold (default 4; the boosters are fitted on the other three folds and NOT refitted). Scored: fold 5 of
       the training members, and every test member (role test_truth, plus role test_ref of a training GCM) on fold
       5 and on all dev cells. Nothing Germany-specific is hard-coded (members, cells, grass types, npatch, PFTs from
       the registry and tables).

OUTPUT  shared/patchheads/_features/<member>{,_recruits}.parquet   (split-independent feature tables, stage prep)
        shared/patchheads/<split>/{fire_B0,fire_B1,rec_B0,rec_B1,entry_<target>_q<qq>_B{0,1}}.txt, meta.json,
        entry_table.parquet, _gates.json                            (stages fit, gates)

PREDICT API (import this module; put wt-X/scripts on sys.path)
    H = load_heads("DEV-A")
    X = H.features(df)                 # derived columns from SH4-style columns (or patch_frame_from_state(...))
    f = H.fire_f(X)                    # patch fire fraction, >= 0.001
    mu = H.recruit_mean(X)             # expected recruits per patch at y+1
    n = H.recruit_draw(mu, u)          # NB draw by inversion of a uniform u (engine Rand.uniform)
    q = H.entry_quantiles(Xr)          # {"height_m5": (n, 7), "log_age": (n, 7)} for recruit rows (needs Type)
    h, age = H.entry_draw(Xr, u_h, u_a)
    s = H.entry_sample(typ, terc, u)   # joint empirical (Height, Age, c, G, cenG) by Type x climate tercile
    terc = H.clim_tercile(tmean_ann_y1)
    X = patch_frame_from_state(state, clim_y1, step_isdead, step_hidden, agb_dead_y)  # from an engine RosterState

STAGES  prep --member M | --all  ·  fit --split S  ·  gates --split S  ·  submit --split S (SLURM chain)  ·
        smoke (tiny end-to-end run into shared/patchheads/_smoke)
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time
import zlib

import numpy as np
import polars as pl

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)
import explore_de_sh_trans as tr  # noqa: E402

XDE = tr.XDE
REG = tr.REG
SMOKE = os.environ.get("SH13_SMOKE") == "1"
OUT = os.environ.get("SH13_OUT", os.path.join(XDE, "shared", "patchheads", "_smoke" if SMOKE else ""))
OUT = OUT.rstrip("/")
FEAT = os.path.join(OUT, "_features")
PATCH = os.path.join(XDE, "shared", "patch")
RECR = os.path.join(XDE, "shared", "recruits")
STATUS = os.path.join(XDE, "_status", "SH13.md")
REPORT = os.path.join(XDE, "_reports", "r2_SH13.json")
PY = os.environ.get("XDE_PY", "/home/jamirp/.conda/envs/py311_new/bin/python")
LOGS = os.path.join(REPO, "logs")
CELLSET = "dev"

FLOOR = 0.001  # soil/fire_prob.c: fire_frac < 0.001 or litter < minfuel -> 0.001
NLAG = 20
QLEV = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]
KAPPAS = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5]
NTHREADS = int(os.environ.get("SLURM_CPUS_PER_TASK", "4"))

FIRE_CLIM_BASE = ["prec_jja", "prec_amjjas", "twarm_month", "cwb_jja", "vpd_jja_eff", "dry_spell_max", "days_gt30"]
REC_CLIM_BASE = ["tmean_ann", "tcold_month", "twarm_month", "gdd5", "prec_ann", "prec_jja", "cwb_jja", "vpd_jja_eff",
                 "dry_spell_max", "days_gt30", "frost_days", "swdown_ann", "tcold_month_tr20", "twarm_month_tr20",
                 "gdd5_tr20"]
CLIM_COLS = sorted(set(FIRE_CLIM_BASE + REC_CLIM_BASE) | {f"anom_{c}" for c in FIRE_CLIM_BASE + REC_CLIM_BASE})
TERC_VAR = "tmean_ann_y1"


def clim_feats(base):
    return [f"{c}_y1" for c in base] + [f"anom_{c}_y1" for c in base]


FIRE_CLIM = clim_feats(FIRE_CLIM_BASE)
REC_CLIM = clim_feats(REC_CLIM_BASE)

FEATURE_AUDIT = {
    "n_live_y": "count of living printed (non-hidden) trees per patch in the roster at y",
    "sum_fpc_y": "sum fpc_ind of living printed trees at y",
    "sum_agb_y": "sum agb of living printed trees at y",
    "patch_lai_y": "sum LAI * fpc_ind of living printed trees at y (tree arrays)",
    "grass<t>_*_y": "state.patch grass<t>_{fpc,LAI,agb} (engine-carried; arm must update via StepOut.grass)",
    "agb_dead_y": "sum agb of the trees the stepper flagged dead at y in its previous step (keep in aux_patch); at the "
                  "start year read SH4 patch agb_dead_y of the start year",
    "cell_share_t<k>": "living printed stems of Type k / all living printed stems of the cell at y (tree arrays)",
    "cell_stems_per_patch": "living printed stems of the cell / npatch",
    "fpc_surv_y1": "sum_fpc_y minus fpc of trees the stepper marks dead or hidden in THIS step (decide deaths first)",
    "n_eligible_pft_y1": "explore_de_sh_rules.eligible(tcold_month_tr20, twarm_month_tr20, gdd5, prec_ann of y+1)",
    "L0": "this step's cover-loss fraction (same quantity the engine pushes into loss_ring after the step)",
    "L1": "state.patch['loss_ring'][:, 0]",
    "L2_5": "nansum(loss_ring[:, 1:5]) (NaN if all NaN)",
    "L6_20": "nansum(loss_ring[:, 5:20]) (NaN if all NaN)",
    "frac_loss_lag0": "entry head: loss_ring[:, 0] at y",
    "<clim>_y1": "engine Climate provider frame of year y+1 (same columns as climate/cell_year + cell_year_ext)",
}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def status(line: str):
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    with open(STATUS, "a") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} {line}\n")


# ================================================================================================ registry
def split_members(split: str) -> dict:
    s = pl.read_parquet(os.path.join(REG, "splits.parquet")).filter(pl.col("split") == split)
    train = sorted(s.filter(pl.col("role") == "train")["src_member"].unique().to_list())
    tgcm = set(s.filter(pl.col("role") == "train")["gcm"].unique().to_list())
    test = set(s.filter(pl.col("role") == "test_truth")["src_member"].unique().to_list())
    test |= set(s.filter((pl.col("role") == "test_ref") & pl.col("gcm").is_in(list(tgcm)))["src_member"].to_list())
    test = sorted(test - set(train))
    assert train, f"no training members for split {split}"
    return {"train": train, "test": test}


def folds() -> pl.DataFrame:
    return pl.read_parquet(os.path.join(REG, "folds.parquet")).filter(pl.col("is_dev")).select(
        pl.col("Cell").cast(pl.Int16), pl.col("fold").cast(pl.Int8))


def grass_cols(cols) -> list[str]:
    return sorted(c for c in cols if c.startswith("grass") and c.endswith("_y"))


# ================================================================================================ feature builder
def _nansum_or_nan(M: np.ndarray) -> np.ndarray:
    allnan = np.all(np.isnan(M), axis=1)
    s = np.nansum(M, axis=1)
    s[allnan] = np.nan
    return s


def derive(df: pl.DataFrame) -> pl.DataFrame:
    """SH4-style patch columns -> the derived head features (fpc_surv_y1, L0, L1, L2_5, L6_20). Accepts either the SH4
    names (loss_y1, frac_loss_y1, frac_loss_lag<k>) or an already-derived frame (then it is returned unchanged)."""
    if "L6_20" in df.columns:
        return df
    lag = np.column_stack([df[f"frac_loss_lag{k}"].cast(pl.Float64).fill_null(np.nan).to_numpy()
                           for k in range(NLAG)])
    return df.with_columns(
        fpc_surv_y1=(pl.col("sum_fpc_y").cast(pl.Float64) - pl.col("loss_y1").cast(pl.Float64)).clip(lower_bound=0.0),
        L0=pl.col("frac_loss_y1").cast(pl.Float64),
        L1=pl.Series(lag[:, 0]),
        L2_5=pl.Series(_nansum_or_nan(lag[:, 1:5])),
        L6_20=pl.Series(_nansum_or_nan(lag[:, 5:20])))


def patch_frame_from_state(state, clim_y1: pl.DataFrame, step_isdead: np.ndarray, step_hidden: np.ndarray,
                           agb_dead_y: np.ndarray | None = None, P=None) -> pl.DataFrame:
    """Build the head input frame (one row per (cell, patch), engine patch order) from an SH6 RosterState at year y.
    step_isdead / step_hidden = the stepper's own decisions for THIS step (bool per tree), so fpc_surv_y1 and L0 are the
    stepper's; agb_dead_y = per-patch agb flagged dead at y (the stepper's previous step, from aux_patch), NaN-free."""
    import explore_de_sh_rules as rl
    t = state.tree
    cells = state.cell["cells"]
    npatch = state.npatch
    npt = len(cells) * npatch
    pidx = state.patch_index()
    live = ~t["hidden"] & ~t["isdead"]
    fpc = np.where(live, t["fpc_ind"].astype(np.float64), 0.0)
    bc = lambda w: np.bincount(pidx, weights=w, minlength=npt)  # noqa: E731
    sum_fpc = bc(fpc)
    lost = bc(np.where(np.asarray(step_isdead, bool) | np.asarray(step_hidden, bool), fpc, 0.0))
    ci = state.cell_index(t["Cell"])
    ncell = np.bincount(ci, weights=live.astype(float), minlength=len(cells))
    cols = {"Cell": np.repeat(cells, npatch).astype(np.int16), "Patch": np.tile(np.arange(npatch), len(cells)),
            "n_live_y": bc(live.astype(float)), "sum_fpc_y": sum_fpc,
            "sum_agb_y": bc(np.where(live, t["agb"].astype(np.float64), 0.0)),
            "patch_lai_y": bc(np.where(live, t["LAI"].astype(np.float64) * t["fpc_ind"], 0.0)),
            "agb_dead_y": np.zeros(npt) if agb_dead_y is None else np.asarray(agb_dead_y, np.float64),
            "fpc_surv_y1": np.maximum(sum_fpc - lost, 0.0),
            "L0": np.where(sum_fpc > 0, lost / np.where(sum_fpc > 0, sum_fpc, 1.0), 0.0)}
    ring = state.patch["loss_ring"].astype(np.float64)
    cols["L1"] = ring[:, 0]
    cols["frac_loss_lag0"] = ring[:, 0]
    cols["L2_5"] = _nansum_or_nan(ring[:, 1:5])
    cols["L6_20"] = _nansum_or_nan(ring[:, 5:20])
    for k, v in state.patch.items():
        if k.startswith("grass"):
            cols[f"{k}_y" if not k.endswith("_y") else k] = v.astype(np.float64)
    for k in range(tr.MAX_TREE_TYPE + 1):
        nk = np.bincount(ci, weights=(live & (t["Type"] == k)).astype(float), minlength=len(cells))
        cols[f"cell_share_t{k}"] = np.repeat(np.where(ncell > 0, nk / np.maximum(ncell, 1), 0.0), npatch)
    cols["cell_stems_per_patch"] = np.repeat(ncell / npatch, npatch)
    X = pl.DataFrame(cols)
    cl = clim_y1.rename({c: f"{c}_y1" for c in clim_y1.columns if c != "Cell"}).with_columns(
        pl.col("Cell").cast(pl.Int16))
    X = X.join(cl, on="Cell", how="left", maintain_order="left")
    el = rl.eligible(X["tcold_month_tr20_y1"].to_numpy(), X["twarm_month_tr20_y1"].to_numpy(),
                     X["gdd5_y1"].to_numpy(), X["prec_ann_y1"].to_numpy(), P)
    return X.with_columns(n_eligible_pft_y1=pl.Series(el.sum(1).astype(np.float64)))


# ================================================================================================ stage prep
def member_files(root: str, member: str) -> dict[int, str]:
    fs = sorted(glob.glob(os.path.join(root, CELLSET, member, "cb=*", "y*.parquet")))
    return {int(os.path.basename(f)[1:5]): f for f in fs}


def trans_patch_cell(member: str, y: int, npatch: int, P, cells=None) -> tuple[pl.DataFrame, pl.DataFrame]:
    f = member_files(tr.TRANS, member)[y]
    T = pl.read_parquet(f, columns=["Cell", "Patch", "Type", "LAI", "fpc_ind", "fate_y1", "mort_y1", "hard_y1"])
    if cells is not None:
        T = T.filter(pl.col("Cell").is_in(cells))
    f64 = pl.Float64
    pres_nh = (pl.col("fate_y1") <= 1) & ~pl.col("hard_y1").fill_null(False)
    m = pl.col("mort_y1").cast(f64)
    pt = T.group_by("Cell", "Patch").agg(
        patch_lai_y=(pl.col("LAI").cast(f64) * pl.col("fpc_ind").cast(f64)).sum(),
        noise_var_y1=pl.when(pres_nh).then(m * (1.0 - m)).otherwise(0.0).sum())
    n = T.group_by("Cell").agg(_n=pl.len())
    sh = T.group_by("Cell", "Type").agg(_k=pl.len())
    ce = n.with_columns(cell_stems_per_patch=pl.col("_n").cast(f64) / npatch)
    for k in range(tr.MAX_TREE_TYPE + 1):
        ce = ce.join(sh.filter(pl.col("Type") == k).select("Cell", pl.col("_k").alias(f"_k{k}")), on="Cell",
                     how="left").with_columns((pl.col(f"_k{k}").fill_null(0).cast(f64) / pl.col("_n"))
                                              .alias(f"cell_share_t{k}")).drop(f"_k{k}")
    return pt, ce.drop("_n")


def prep_member(member: str, force: bool = False):
    import explore_de_sh_rules as rl
    os.makedirs(FEAT, exist_ok=True)
    fo = os.path.join(FEAT, f"{member}.parquet")
    fr = os.path.join(FEAT, f"{member}_recruits.parquet")
    if os.path.exists(fo) and os.path.exists(fr) and not force:
        log(f"{member}: features exist, skip")
        return
    mem = pl.read_parquet(os.path.join(REG, "members.parquet")).filter(pl.col("member") == member)
    assert mem.height == 1 and not mem["excluded"][0], f"{member} missing or excluded"
    npatch = int(mem["npatch"][0])
    P = rl.load_params()
    pf = member_files(PATCH, member)
    rf = member_files(RECR, member)
    years = sorted(pf)
    cells = None
    if SMOKE:
        years = years[:5]
        cells = [c for c in folds()["Cell"].to_list() if c % 100 == 0]
    out, outr = [], []
    t0 = time.time()
    for y in years:
        D = pl.read_parquet(pf[y])
        if cells is not None:
            D = D.filter(pl.col("Cell").is_in(cells))
        D = derive(D)
        pt, ce = trans_patch_cell(member, y, npatch, P, cells)
        D = (D.join(pt, on=["Cell", "Patch"], how="left").join(ce, on="Cell", how="left")
             .with_columns(pl.col("patch_lai_y", "noise_var_y1", "cell_stems_per_patch",
                                  *[f"cell_share_t{k}" for k in range(tr.MAX_TREE_TYPE + 1)]).fill_null(0.0)))
        keep = (["member", "gcm", "traj", "seed", "Year", "Cell", "Patch", "n_live_y", "sum_fpc_y", "sum_agb_y",
                 "fpc_dead_y", "agb_dead_y", "patch_lai_y", "fpc_surv_y1", "L0", "L1", "L2_5", "L6_20",
                 "frac_loss_lag0", "n_eligible_pft_y1", "cell_stems_per_patch"]
                + [f"cell_share_t{k}" for k in range(tr.MAX_TREE_TYPE + 1)] + grass_cols(D.columns)
                + ["fire_E_y1", "fire_D_y1", "noise_var_y1", "deaths_y1", "n_hard_y1", "hazard_sum_y1",
                   "n_recruit_y1", "n_recruit_y"])
        out.append(D.select(keep))
        if y in rf:
            R = pl.read_parquet(rf[y], columns=["member", "gcm", "traj", "seed", "Year", "Cell", "Patch", "Type",
                                                "isdead", "Height", "Age", "c", "G", "cenG", "n_live_y", "sum_fpc_y",
                                                "sum_agb_y", "frac_loss_lag0"]
                                + [c for c in pl.read_parquet_schema(rf[y]) if c.startswith("grass")])
            if cells is not None:
                R = R.filter(pl.col("Cell").is_in(cells))
            outr.append(R)
        log(f"{member} y{y}: {D.height} patch rows, {time.time() - t0:.0f} s")
    F = pl.concat(out, how="diagonal_relaxed")
    F = tr.join_climate(F, cols=CLIM_COLS, years=("y1",))
    F = F.join(folds(), on="Cell", how="left")
    f32 = [c for c, t in F.schema.items() if t == pl.Float64]
    F = F.with_columns([pl.col(c).cast(pl.Float32) for c in f32])
    assert F["fold"].null_count() == 0
    F.write_parquet(fo)
    R = pl.concat(outr, how="diagonal_relaxed")
    R = tr.join_climate(R, cols=CLIM_COLS, years=("y1",)).join(folds(), on="Cell", how="left")
    R = R.with_columns([pl.col(c).cast(pl.Float32) for c, t in R.schema.items() if t == pl.Float64])
    R.write_parquet(fr)
    log(f"{member}: wrote {F.height} patch-years, {R.height} recruits, {time.time() - t0:.0f} s")
    status(f"prep {member}: {F.height} patch-years, {R.height} recruits")


def stage_prep(a):
    ms = split_members(a.split)
    members = a.member or (ms["train"] + ms["test"])
    for m in members:
        prep_member(m, force=a.force)


# ================================================================================================ lightgbm pieces
def _lgb():
    import lightgbm as lgb
    return lgb


def fire_obj(preds, data):
    """Poisson (log link) on the EXCESS over the floor: label = E/D - 0.001 (may be negative), weight = D, so
    D e^s estimates E - 0.001 D and every leaf matches its own total of E exactly (unweighted). A leaf whose total
    excess is negative is driven toward f = 0.001, step-limited by max_delta_step."""
    y = data.get_label()
    w = data.get_weight()
    e = np.exp(np.minimum(preds, 5.0))
    return w * (e - y), np.maximum(w * e, 1e-12)


def fire_loss(score, y, w):
    """Mean Poisson loss of the excess rate y = E/D - 0.001 (weight D): sum w (e^s - y s) / sum w."""
    s = np.minimum(score, 5.0)
    return float(np.sum(w * (np.exp(s) - y * s)) / np.sum(w))


def fire_feval(preds, data):
    return "fire_pois_excess", fire_loss(preds, data.get_label(), data.get_weight()), False


def pois_dev(mu, y):
    mu = np.maximum(mu, 1e-12)
    yl = np.where(y > 0, y * np.log(np.where(y > 0, y, 1.0) / mu), 0.0)
    return float(np.mean(2.0 * (yl - (y - mu))))


def pinball(q, y, alpha):
    d = y - q
    return float(np.mean(np.maximum(alpha * d, (alpha - 1.0) * d)))


def _train(params, X, y, w, init, Xv, yv, wv, initv, rounds, es, feats, linear=False, label=""):
    lgb = _lgb()
    p = dict(params)
    p.update(num_threads=NTHREADS, verbose=-1, seed=13, deterministic=True, force_row_wise=True)
    dsp = {"linear_tree": True} if linear else {}
    if linear:
        p.update(linear_tree=True, linear_lambda=p.get("linear_lambda", 1.0))
    dtr = lgb.Dataset(X, label=y, weight=w, init_score=init, feature_name=feats, free_raw_data=False, params=dsp)
    dva = lgb.Dataset(Xv, label=yv, weight=wv, init_score=initv, reference=dtr, feature_name=feats,
                      free_raw_data=False, params=dsp)
    kw = {}
    if callable(p.get("objective")):
        kw["feval"] = fire_feval
        p["metric"] = "None"
    t0 = time.time()
    bst = lgb.train(p, dtr, num_boost_round=rounds, valid_sets=[dva], valid_names=["val"],
                    callbacks=[lgb.early_stopping(es, verbose=False), lgb.log_evaluation(100)], **kw)
    log(f"{label}: best_iter {bst.best_iteration}, {time.time() - t0:.0f} s, val {bst.best_score['val']}")
    return bst


def _np(df: pl.DataFrame, cols) -> np.ndarray:
    return df.select([pl.col(c).cast(pl.Float32) for c in cols]).to_numpy()


# ================================================================================================ stage fit
def load_feats(members, recruits=False, folds_keep=None, cols=None) -> pl.DataFrame:
    fs = [os.path.join(FEAT, f"{m}_recruits.parquet" if recruits else f"{m}.parquet") for m in members]
    for f in fs:
        assert os.path.exists(f), f"missing {f} (run prep)"
    lf = pl.concat([pl.scan_parquet(f) for f in fs], how="diagonal_relaxed")
    if folds_keep is not None:
        lf = lf.filter(pl.col("fold").is_in(folds_keep))
    if cols is not None:
        lf = lf.select(cols)
    return lf.collect()


def state_feats(cols) -> tuple[list[str], list[str], list[str]]:
    g = grass_cols(cols)
    fire = ["sum_agb_y", "sum_fpc_y", "n_live_y", "agb_dead_y", "patch_lai_y"] + g
    rec = (["n_live_y", "sum_fpc_y", "sum_agb_y", "patch_lai_y", "fpc_surv_y1", "L0", "L1", "L2_5", "L6_20",
            "n_eligible_pft_y1", "cell_stems_per_patch"] + [f"cell_share_t{k}" for k in range(tr.MAX_TREE_TYPE + 1)]
           + g)
    ent = ["Type", "n_live_y", "sum_fpc_y", "sum_agb_y", "frac_loss_lag0"] + g
    return fire, rec, ent


def stage_fit(a):
    lgb = _lgb()
    split, vf = a.split, int(a.val_fold)
    od = os.path.join(OUT, split)
    os.makedirs(od, exist_ok=True)
    ms = split_members(split)
    rounds = 40 if SMOKE else int(a.rounds)
    es = 10 if SMOKE else 50
    trf = [1, 2, 3, 4] if not SMOKE else [1, 2, 3, 4, 5]
    only_fire = getattr(a, "only", None) == "fire"
    F = load_feats(ms["train"], folds_keep=trf)
    if SMOKE:
        F = F.with_columns(fold=pl.when(pl.col("Cell") % 200 == 0).then(pl.lit(vf, pl.Int8)).otherwise(1))
    fire_s, rec_s, ent_s = state_feats(F.columns)
    log(f"fit {split}: train members {ms['train']}, {F.height} patch-years (folds {trf}), val fold {vf}")
    tr_m = (F["fold"] != vf).to_numpy()
    meta = {"split": split, "val_fold": vf, "train_members": ms["train"], "test_members": ms["test"],
            "train_folds": [k for k in trf if k != vf], "floor": FLOOR, "qlev": QLEV, "kappas": KAPPAS,
            "feature_audit": FEATURE_AUDIT, "n_train_patch_years": int(tr_m.sum()),
            "n_val_patch_years": int((~tr_m).sum())}

    # ---------------------------------------------------------------- (a) fire
    D = F["fire_D_y1"].cast(pl.Float64).to_numpy()
    E = F["fire_E_y1"].cast(pl.Float64).to_numpy()
    ok = D > 0
    mt, mv = tr_m & ok, ~tr_m & ok
    fbar = E[mt].sum() / D[mt].sum()
    base = float(np.log(max(fbar - FLOOR, 1e-5)))
    yr = np.where(ok, E / np.where(ok, D, 1.0) - FLOOR, 0.0)
    Xs = _np(F, fire_s)
    Xc = _np(F, FIRE_CLIM)
    fp = dict(objective=fire_obj, learning_rate=0.05, num_leaves=15, min_data_in_leaf=50000 if not SMOKE else 500,
              lambda_l2=1.0, max_delta_step=1.0, feature_fraction=1.0, bagging_fraction=0.7, bagging_freq=1,
              max_bin=127)
    b0 = _train(fp, Xs[mt], yr[mt], D[mt], np.full(mt.sum(), base), Xs[mv], yr[mv], D[mv], np.full(mv.sum(), base),
                rounds, es * 2, fire_s, label="fire B0")
    s0 = base + b0.predict(Xs, num_threads=NTHREADS, raw_score=True)
    fp1 = dict(fp, learning_rate=0.03, num_leaves=7, linear_lambda=10.0)
    b1 = _train(fp1, Xc[mt], yr[mt], D[mt], s0[mt], Xc[mv], yr[mv], D[mv], s0[mv], rounds, es * 2, FIRE_CLIM,
                linear=True, label="fire B1")
    s1 = b1.predict(Xc, num_threads=NTHREADS, raw_score=True)
    kl = {k: fire_loss(s0[mv] + k * s1[mv], yr[mv], D[mv]) for k in KAPPAS}
    kf = min(kl, key=kl.get)
    b0.save_model(os.path.join(od, "fire_B0.txt"))
    b1.save_model(os.path.join(od, "fire_B1.txt"))
    meta["fire"] = {"base": base, "fbar_train": fbar, "state_feats": fire_s, "clim_feats": FIRE_CLIM, "kappa": kf,
                    "val_loss_by_kappa": kl, "val_loss_const": fire_loss(np.full(mv.sum(), base), yr[mv], D[mv]),
                    "B0_iter": b0.best_iteration, "B1_iter": b1.best_iteration, "n_rows_D0_dropped": int((~ok).sum())}
    log("fire", json.dumps(meta["fire"]["val_loss_by_kappa"]), "kappa", kf)
    del Xs, Xc
    if only_fire:
        old = json.load(open(os.path.join(od, "meta.json")))
        old["fire"] = meta["fire"]
        json.dump(old, open(os.path.join(od, "meta.json"), "w"), indent=1)
        status(f"fit {split} (fire only) done: kappa {kf}, B0 {b0.best_iteration}, B1 {b1.best_iteration} iters")
        return

    # ---------------------------------------------------------------- (b) recruit count
    y = F["n_recruit_y1"].cast(pl.Float64).to_numpy()
    mbar = y[tr_m].mean()
    rbase = float(np.log(mbar))
    Xs = _np(F, rec_s)
    Xc = _np(F, REC_CLIM)
    rp = dict(objective="poisson", metric="poisson", learning_rate=0.08, num_leaves=63,
              min_data_in_leaf=2000 if not SMOKE else 50, lambda_l2=1.0, feature_fraction=0.9, bagging_fraction=0.7,
              bagging_freq=1, max_bin=255)
    trm, vam = tr_m, ~tr_m
    r0 = _train(rp, Xs[trm], y[trm], None, np.full(trm.sum(), rbase), Xs[vam], y[vam], None,
                np.full(vam.sum(), rbase), rounds, es, rec_s, label="recruit B0")
    q0 = rbase + r0.predict(Xs, num_threads=NTHREADS, raw_score=True)
    rp1 = dict(rp, learning_rate=0.05, num_leaves=15, min_data_in_leaf=20000 if not SMOKE else 50,
               linear_lambda=10.0)
    r1 = _train(rp1, Xc[trm], y[trm], None, q0[trm], Xc[vam], y[vam], None, q0[vam], rounds, es, REC_CLIM,
                linear=True, label="recruit B1")
    q1 = r1.predict(Xc, num_threads=NTHREADS, raw_score=True)
    kl = {k: pois_dev(np.exp(q0[vam] + k * q1[vam]), y[vam]) for k in KAPPAS}
    kr = min(kl, key=kl.get)
    r0.save_model(os.path.join(od, "rec_B0.txt"))
    r1.save_model(os.path.join(od, "rec_B1.txt"))
    # NB dispersion per predicted-mean decile (validation fold: rows the boosters were not fitted on)
    mu = np.exp(q0[vam] + kr * q1[vam])
    yv = y[vam]
    edges = np.quantile(mu, np.linspace(0, 1, 11)[1:-1])
    dec = np.searchsorted(edges, mu)
    alpha = []
    for d in range(10):
        m = dec == d
        al = float(np.sum((yv[m] - mu[m]) ** 2 - yv[m]) / np.sum(mu[m] ** 2))
        alpha.append(max(al, 0.0))
    meta["recruit"] = {"base": rbase, "mean_train": mbar, "state_feats": rec_s, "clim_feats": REC_CLIM, "kappa": kr,
                       "val_dev_by_kappa": kl, "val_dev_const": pois_dev(np.full(vam.sum(), mbar), yv),
                       "B0_iter": r0.best_iteration, "B1_iter": r1.best_iteration,
                       "nb_edges": edges.tolist(), "nb_alpha": alpha}
    log("recruit", json.dumps(kl), "kappa", kr, "alpha", alpha)
    del Xs, Xc, F

    # ---------------------------------------------------------------- (c) entry state
    R = load_feats(ms["train"], recruits=True, folds_keep=trf)
    if SMOKE:
        R = R.with_columns(fold=pl.when(pl.col("Cell") % 200 == 0).then(pl.lit(vf, pl.Int8)).otherwise(1))
    R = R.with_columns(height_m5=(pl.col("Height").cast(pl.Float64) - 5.0),
                       log_age=pl.col("Age").cast(pl.Float64).clip(lower_bound=1.0).log())
    terc = np.quantile(R[TERC_VAR].to_numpy(), [1 / 3, 2 / 3]).tolist()
    R = R.with_columns(terc=pl.Series(np.searchsorted(terc, R[TERC_VAR].to_numpy()).astype(np.int8)))
    rng = np.random.default_rng(13)
    # empirical joint table (all training-fold recruits; cap per Type x tercile)
    tabs = []
    for _, g in R.filter(pl.col("fold") != vf).sort("Type", "terc").group_by(["Type", "terc"], maintain_order=True):
        g = g.select("Type", "terc", "Height", "Age", "c", "G", "cenG")
        if g.height > 50000:
            g = g[np.sort(rng.choice(g.height, 50000, replace=False))]
        tabs.append(g)
    TAB = pl.concat(tabs).sort("Type", "terc", "Height")
    TAB.write_parquet(os.path.join(od, "entry_table.parquet"))
    # quantile heads
    rtr = R.filter(pl.col("fold") != vf)
    rva = R.filter(pl.col("fold") == vf)
    nmax = 1_500_000 if not SMOKE else 20000
    if rtr.height > nmax:
        rtr = rtr[np.sort(rng.choice(rtr.height, nmax, replace=False))]
    if rva.height > 300_000:
        rva = rva[np.sort(rng.choice(rva.height, 300_000, replace=False))]
    ent_c = REC_CLIM
    Xs_t, Xs_v = _np(rtr, ent_s), _np(rva, ent_s)
    Xc_t, Xc_v = _np(rtr, ent_c), _np(rva, ent_c)
    ent_meta = {"state_feats": ent_s, "clim_feats": ent_c, "terc_var": TERC_VAR, "terc_edges": terc,
                "n_train": rtr.height, "n_val": rva.height, "heads": {}}
    for tgt in ("height_m5", "log_age"):
        yt, yv = rtr[tgt].to_numpy(), rva[tgt].to_numpy()
        for q in QLEV:
            nm = f"entry_{tgt}_q{int(round(q * 100)):02d}"
            qb = float(np.quantile(yt, q))
            ep = dict(objective="quantile", alpha=q, metric="quantile", learning_rate=0.1, num_leaves=31,
                      min_data_in_leaf=500 if not SMOKE else 20, max_bin=255, feature_fraction=1.0)
            e0 = _train(ep, Xs_t, yt, None, np.full(len(yt), qb), Xs_v, yv, None, np.full(len(yv), qb),
                        min(rounds, 400), es, ent_s, label=nm + " B0")
            p0t, p0v = qb + e0.predict(Xs_t, raw_score=True), qb + e0.predict(Xs_v, raw_score=True)
            ep1 = dict(ep, learning_rate=0.05, num_leaves=7, min_data_in_leaf=5000 if not SMOKE else 20,
                       linear_lambda=10.0)
            e1 = _train(ep1, Xc_t, yt, None, p0t, Xc_v, yv, None, p0v, min(rounds, 300), es, ent_c, linear=True,
                        label=nm + " B1")
            p1v = e1.predict(Xc_v, raw_score=True)
            kl = {k: pinball(p0v + k * p1v, yv, q) for k in KAPPAS}
            e0.save_model(os.path.join(od, nm + "_B0.txt"))
            e1.save_model(os.path.join(od, nm + "_B1.txt"))
            ent_meta["heads"][nm] = {"base": qb, "kappa": min(kl, key=kl.get), "val_pinball_by_kappa": kl,
                                     "B0_iter": e0.best_iteration, "B1_iter": e1.best_iteration}
    meta["entry"] = ent_meta
    json.dump(meta, open(os.path.join(od, "meta.json"), "w"), indent=1)
    status(f"fit {split} done: fire kappa {kf}, recruit kappa {kr}, NB alpha {np.round(alpha, 3).tolist()}")
    log("fit done")
    _ = lgb


# ================================================================================================ the predict API
class PatchHeads:
    """The importable heads of one split. All predictors take a polars frame with (at least) the feature columns
    (see meta.json / FEATURE_AUDIT) and return numpy arrays; kappa=None uses the validated default."""

    def __init__(self, split: str, root: str | None = None):
        lgb = _lgb()
        self.dir = os.path.join(root or OUT, split)
        self.meta = json.load(open(os.path.join(self.dir, "meta.json")))
        ld = lambda n: lgb.Booster(model_file=os.path.join(self.dir, n + ".txt"))  # noqa: E731
        self.fire_b = (ld("fire_B0"), ld("fire_B1"))
        self.rec_b = (ld("rec_B0"), ld("rec_B1"))
        self.ent_b = {nm: (ld(nm + "_B0"), ld(nm + "_B1")) for nm in self.meta["entry"]["heads"]}
        self.table = pl.read_parquet(os.path.join(self.dir, "entry_table.parquet"))
        self._tab = {}
        # deterministic within-group row order: the entry draws index into these arrays, and an unordered
        # group_by made two runs of the same stepper differ (262 of 425 427 rows in 1986; STRUCT diagnosis SD)
        tab = self.table.sort(["Type", "terc", "Height", "Age", "c", "G", "cenG"])
        for (ty, te), g in tab.group_by(["Type", "terc"], maintain_order=True):
            self._tab[(int(ty), int(te))] = {c: g[c].to_numpy() for c in ("Height", "Age", "c", "G", "cenG")}
        self.nthreads = NTHREADS

    @staticmethod
    def features(df: pl.DataFrame) -> pl.DataFrame:
        return derive(df)

    def _score(self, b, m, df, kappa):
        k = m["kappa"] if kappa is None else kappa
        s = m["base"] + b[0].predict(_np(df, m["state_feats"]), num_threads=self.nthreads, raw_score=True)
        if k != 0:
            s = s + k * b[1].predict(_np(df, m["clim_feats"]), num_threads=self.nthreads, raw_score=True)
        return s

    def fire_f(self, df: pl.DataFrame, kappa=None) -> np.ndarray:
        """Patch fire fraction f >= 0.001 of the y -> y+1 step. Stepper: kill each non-hard hazard survivor with
        probability (1 - resist[Type]) * f."""
        return FLOOR + np.exp(np.minimum(self._score(self.fire_b, self.meta["fire"], df, kappa), 5.0))

    def recruit_mean(self, df: pl.DataFrame, kappa=None) -> np.ndarray:
        return np.exp(self._score(self.rec_b, self.meta["recruit"], df, kappa))

    def recruit_draw(self, mean: np.ndarray, u: np.ndarray) -> np.ndarray:
        """Negative-binomial draw by inversion of uniform u (dispersion alpha of the mean's decile; alpha = 0 ->
        Poisson). Var = mu + alpha mu^2."""
        from scipy import stats
        mu = np.asarray(mean, np.float64)
        u = np.clip(np.asarray(u, np.float64), 1e-12, 1 - 1e-12)
        al = np.asarray(self.meta["recruit"]["nb_alpha"])[np.searchsorted(self.meta["recruit"]["nb_edges"], mu)]
        out = np.zeros(mu.shape, np.int64)
        nb = (al > 1e-9) & (mu > 0)
        if nb.any():
            r = 1.0 / al[nb]
            out[nb] = stats.nbinom.ppf(u[nb], r, r / (r + mu[nb])).astype(np.int64)
        po = ~nb & (mu > 0)
        if po.any():
            out[po] = stats.poisson.ppf(u[po], mu[po]).astype(np.int64)
        return out

    def entry_quantiles(self, df: pl.DataFrame, kappa=None) -> dict:
        out = {}
        em = self.meta["entry"]
        for tgt in ("height_m5", "log_age"):
            cols = []
            for q in QLEV:
                nm = f"entry_{tgt}_q{int(round(q * 100)):02d}"
                m = dict(em["heads"][nm], state_feats=em["state_feats"], clim_feats=em["clim_feats"])
                cols.append(self._score(self.ent_b[nm], m, df, kappa))
            out[tgt] = np.sort(np.column_stack(cols), axis=1)
        return out

    def entry_draw(self, df: pl.DataFrame, u_h: np.ndarray, u_a: np.ndarray, kappa=None):
        """Height (m) and Age (yr) at entry by inverting the interpolated conditional quantile function (linear
        between q05..q95, linear extrapolation of the outer segments, Height >= 5, Age >= 1)."""
        Q = self.entry_quantiles(df, kappa)
        h = _qinterp(Q["height_m5"], np.asarray(u_h))
        a = _qinterp(Q["log_age"], np.asarray(u_a))
        return 5.0 + np.maximum(h, 0.0), np.maximum(np.exp(a), 1.0)

    def clim_tercile(self, x: np.ndarray) -> np.ndarray:
        return np.searchsorted(self.meta["entry"]["terc_edges"], np.asarray(x)).astype(np.int8)

    def entry_sample(self, typ: np.ndarray, terc: np.ndarray, u: np.ndarray) -> dict:
        """Joint empirical (Height, Age, c, G, cenG) at entry for each (Type, climate tercile), row index floor(u*n).
        Falls back to the same Type's other terciles (then any Type) when a cell of the table is empty."""
        typ, terc, u = np.asarray(typ).astype(int), np.asarray(terc).astype(int), np.asarray(u, np.float64)
        out = {c: np.full(len(typ), np.nan) for c in ("Height", "Age", "c", "G", "cenG")}
        for ty in np.unique(typ):
            for te in np.unique(terc):
                m = (typ == ty) & (terc == te)
                if not m.any():
                    continue
                key = (ty, te)
                if key not in self._tab:
                    alt = [k for k in self._tab if k[0] == ty] or list(self._tab)
                    key = min(alt, key=lambda k: abs(k[1] - te))
                T = self._tab[key]
                idx = np.minimum((u[m] * len(T["Height"])).astype(np.int64), len(T["Height"]) - 1)
                for c in out:
                    out[c][m] = T[c][idx]
        return out


def _qinterp(Q: np.ndarray, u: np.ndarray) -> np.ndarray:
    lv = np.asarray(QLEV)
    u = np.clip(u, 1e-6, 1 - 1e-6)
    j = np.clip(np.searchsorted(lv, u) - 1, 0, len(lv) - 2)
    x0, x1 = lv[j], lv[j + 1]
    r = np.take_along_axis(Q, j[:, None], 1)[:, 0]
    s = np.take_along_axis(Q, (j + 1)[:, None], 1)[:, 0]
    return r + (s - r) * (u - x0) / (x1 - x0)


_HEADS: dict = {}


def load_heads(split: str = "DEV-A", root: str | None = None) -> PatchHeads:
    key = (split, root)
    if key not in _HEADS:
        _HEADS[key] = PatchHeads(split, root)
    return _HEADS[key]


# ================================================================================================ stage gates
def _corr(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _ceiling(obs, noise_var) -> dict:
    """Best correlation ANY predictor can reach with a noisy observed series: sqrt(Var(signal) / Var(obs)), with
    Var(signal) = Var(obs) - mean(noise variance) (noise = the hazard-draw Bernoulli variance sum m(1-m))."""
    vo = float(np.var(obs, ddof=1))
    vn = float(np.mean(noise_var))
    vs = max(vo - vn, 0.0)
    return {"var_obs": vo, "mean_noise_var": vn, "ceiling_corr": float(np.sqrt(vs / vo)) if vo > 0 else float("nan")}


def globalflux_fire(member: str) -> pl.DataFrame | None:
    m = pl.read_parquet(os.path.join(REG, "members.parquet")).filter(pl.col("member") == member).row(0, named=True)
    d = os.path.dirname(m["src_csv"])
    suf = os.path.basename(m["src_csv"])[len("ind_"):]
    f = os.path.join(d, f"globalflux_{suf}")
    if not os.path.exists(f):
        return None
    g = pl.read_csv(f, skip_rows_after_header=1)
    return g.select(pl.col("Year").cast(pl.Int32).alias("Y1"), pl.col("fire").cast(pl.Float64).alias("gf_fire"),
                    pl.col("LitC").cast(pl.Float64).alias("gf_litc"))


def calib_deciles(pred, obs, nbin=10) -> dict:
    edges = np.quantile(pred, np.linspace(0, 1, nbin + 1)[1:-1])
    d = np.searchsorted(edges, pred)
    rows, ok = [], True
    for k in range(nbin):
        m = d == k
        if not m.any():
            continue
        pm, om = float(pred[m].mean()), float(obs[m].mean())
        se = float(obs[m].std(ddof=1) / np.sqrt(m.sum())) if m.sum() > 1 else float("nan")
        tol = max(0.1 * abs(pm), 2 * se)
        good = abs(om - pm) <= tol
        ok &= good
        rows.append({"decile": k + 1, "n": int(m.sum()), "pred_mean": pm, "obs_mean": om, "obs_se": se,
                     "pass": bool(good)})
    return {"pass": bool(ok), "rule": "|obs - pred| <= max(10 % of pred, 2 SE of obs) in every decile", "rows": rows}


def score_member(H: PatchHeads, member: str, fold5_only: bool) -> dict:
    """Predictions + every per-row array the gates need, for one member (fold 5, or all dev cells)."""
    F = load_feats([member], folds_keep=[5] if fold5_only else None)
    X = F
    out = {"member": member, "cells": "fold5" if fold5_only else "all_dev", "n_rows": F.height,
           "n_cells": int(F["Cell"].n_unique())}
    f = H.fire_f(X)
    f0 = H.fire_f(X, kappa=0.0)
    mu = H.recruit_mean(X)
    mu0 = H.recruit_mean(X, kappa=0.0)
    S = F.select("member", "Year", "Cell", "fire_E_y1", "fire_D_y1", "noise_var_y1", "n_recruit_y1", "n_recruit_y",
                 "fpc_dead_y", "sum_fpc_y", "sum_agb_y").with_columns(
        f=pl.Series(f), f0=pl.Series(f0), mu=pl.Series(mu), mu0=pl.Series(mu0))
    return {"meta": out, "S": S}


def fire_metrics(S: pl.DataFrame, fbar: float, gf: dict | None) -> dict:
    D = S["fire_D_y1"].cast(pl.Float64).to_numpy()
    E = S["fire_E_y1"].cast(pl.Float64).to_numpy()
    f = S["f"].to_numpy()
    ok = D > 0
    yr = np.where(ok, E / np.where(ok, D, 1.0) - FLOOR, 0.0)
    loss = lambda ff: fire_loss(np.log(np.maximum(ff[ok] - FLOOR, 1e-12)), yr[ok], D[ok])  # noqa: E731
    Y = (S.with_columns(pE=pl.col("f") * pl.col("fire_D_y1"), pE0=pl.col("f0") * pl.col("fire_D_y1"),
                        nE=pl.lit(fbar) * pl.col("fire_D_y1").cast(pl.Float64), fA=pl.col("f") * pl.col("sum_agb_y"))
         .group_by("member", "Year").agg(pl.col("fire_E_y1").cast(pl.Float64).sum().alias("E"),
                                         pl.col("pE").sum(), pl.col("pE0").sum(), pl.col("nE").sum(),
                                         pl.col("fA").sum(), pl.col("f").mean().alias("fmean"),
                                         pl.col("fire_D_y1").cast(pl.Float64).sum().alias("D"),
                                         pl.col("noise_var_y1").cast(pl.Float64).sum().alias("V"))
         .sort("member", "Year"))
    out = {"n_patch_years": int(len(D)), "n_member_years": Y.height,
           "total_obs_E": float(E.sum()), "total_pred_fD": float((f * D).sum()),
           "total_ratio_pred_over_obs": float((f * D).sum() / E.sum()) if E.sum() != 0 else float("nan"),
           "yearly_ratio_pred_over_obs_quantiles": np.quantile(Y["pE"].to_numpy() / np.where(
               Y["E"].to_numpy() != 0, Y["E"].to_numpy(), np.nan), [0.1, 0.5, 0.9]).tolist(),
           "mean_f_pred": float(f.mean()), "obs_sumE_over_sumD": float(E.sum() / D.sum()),
           "yearly_corr_model": _corr(Y["pE"], Y["E"]), "yearly_corr_climate_blind": _corr(Y["pE0"], Y["E"]),
           "yearly_corr_null_constant_f": _corr(Y["nE"], Y["E"]),
           "noise_ceiling": _ceiling(Y["E"].to_numpy(), Y["V"].to_numpy()),
           "loss_model": loss(f), "loss_climate_blind": loss(S["f0"].to_numpy()),
           "loss_null_constant_f": loss(np.full(len(f), fbar))}
    out["loss_gain_vs_null"] = out["loss_null_constant_f"] - out["loss_model"]
    C = (S.with_columns(pE=pl.col("f") * pl.col("fire_D_y1")).group_by("Cell")
         .agg(pl.col("fire_E_y1").cast(pl.Float64).sum().alias("E"), pl.col("pE").sum(),
              pl.col("fire_D_y1").cast(pl.Float64).sum().alias("D"),
              pl.col("noise_var_y1").cast(pl.Float64).sum().alias("V")))
    fo = (C["E"] / C["D"]).to_numpy()
    out["spatial_cell_corr_model"] = _corr(C["pE"] / C["D"], fo)
    out["spatial_noise_ceiling"] = _ceiling(fo, (C["V"] / C["D"] ** 2).to_numpy())
    out["spatial_n_cells"] = C.height
    out["calibration"] = calib_deciles((f * D)[ok], E[ok])
    if gf is not None:
        G = Y.with_columns(Y1=(pl.col("Year").cast(pl.Int32) + 1)).join(gf, on=["member", "Y1"], how="inner")
        out["globalflux"] = {"n_years": G.height, "basis": "Germany-wide fire carbon flux of the original run "
                             "(globalflux 'fire', all ~9067 cells) vs dev-cell sums of the same year",
                             "corr_obs_E": _corr(G["E"], G["gf_fire"]),
                             "corr_pred_fD": _corr(G["pE"], G["gf_fire"]),
                             "corr_pred_mean_f": _corr(G["fmean"], G["gf_fire"]),
                             "corr_pred_f_x_agb": _corr(G["fA"], G["gf_fire"]),
                             "corr_pred_mean_f_vs_fire_over_litc": _corr(G["fmean"], G["gf_fire"] / G["gf_litc"]),
                             "corr_null_constant_f": _corr(G["nE"], G["gf_fire"])}
    return out, Y


def release_rows(S: pl.DataFrame) -> pl.DataFrame:
    tot = pl.col("sum_fpc_y").cast(pl.Float64) + pl.col("fpc_dead_y").cast(pl.Float64)
    return S.filter((pl.col("fpc_dead_y") >= 0.5 * tot) & (tot > 0.3) & pl.col("n_recruit_y").is_not_null())


def recruit_metrics(H: PatchHeads, S: pl.DataFrame, mbar: float, draw_seed: int) -> dict:
    y = S["n_recruit_y1"].cast(pl.Float64).to_numpy()
    mu = S["mu"].to_numpy()
    cm = S.group_by("member", "Cell").agg(pl.col("n_recruit_y1").cast(pl.Float64).mean().alias("_cm"))
    S2 = S.join(cm, on=["member", "Cell"], how="left", maintain_order="left")
    cmean = S2["_cm"].to_numpy()
    prev = S["n_recruit_y"].cast(pl.Float64).to_numpy()
    hp = ~np.isnan(prev)
    out = {"n_patch_years": int(len(y)), "obs_mean": float(y.mean()), "pred_mean": float(mu.mean()),
           "dev_model": pois_dev(mu, y), "dev_climate_blind": pois_dev(S["mu0"].to_numpy(), y),
           "dev_null_constant": pois_dev(np.full(len(y), mbar), y),
           "dev_null_cell_mean_oracle": pois_dev(cmean, y),
           "dev_null_persistence_floor0.01_rows_with_prev": pois_dev(np.maximum(prev[hp], 0.01), y[hp]),
           "dev_model_rows_with_prev": pois_dev(mu[hp], y[hp]),
           "mse_model": float(np.mean((y - mu) ** 2)), "mse_null_constant": float(np.mean((y - mbar) ** 2)),
           "mse_null_cell_mean_oracle": float(np.mean((y - cmean) ** 2)),
           "mse_null_persistence_rows_with_prev": float(np.mean((y[hp] - prev[hp]) ** 2)),
           "mse_model_rows_with_prev": float(np.mean((y[hp] - mu[hp]) ** 2))}
    # release after a >= 50 % one-year cover loss
    Rr = release_rows(S2)
    den = float(Rr["n_recruit_y"].cast(pl.Float64).mean()) if Rr.height else float("nan")
    tru = float(Rr["n_recruit_y1"].cast(pl.Float64).mean()) / den if Rr.height else float("nan")
    pr = float(Rr["mu"].mean()) / den if Rr.height else float("nan")
    out["release"] = {"n_event_patch_years": Rr.height, "mean_n_recruit_y": den,
                      "mean_n_recruit_y1_truth": float(Rr["n_recruit_y1"].cast(pl.Float64).mean()),
                      "mean_mu_y1_model": float(Rr["mu"].mean()), "truth_ratio": tru, "model_ratio": pr,
                      "model_ratio_climate_blind": float(Rr["mu0"].mean()) / den if Rr.height else float("nan"),
                      "null_cell_mean_ratio": float(Rr["_cm"].mean()) / den if Rr.height else float("nan"),
                      "null_persistence_ratio": 1.0,
                      "model_over_truth": pr / tru, "pass_within_10pct_of_truth": bool(abs(pr / tru - 1) <= 0.10),
                      "judge_band": [3.6, 4.1], "model_in_judge_band": bool(3.6 <= pr <= 4.1),
                      "truth_in_judge_band": bool(3.6 <= tru <= 4.1)}
    # cell-year totals from draws
    u = np.random.default_rng(draw_seed).random(len(mu))
    n = H.recruit_draw(mu, u)
    CY = S.select("member", "Year", "Cell", "n_recruit_y1").with_columns(draw=pl.Series(n)).group_by(
        "member", "Year", "Cell").agg(pl.col("draw").sum(), pl.col("n_recruit_y1").sum().alias("obs"))
    out["cellyear_totals"] = {"n_cell_years": CY.height, "n_zero_draw": int((CY["draw"] == 0).sum()),
                              "min_draw": int(CY["draw"].min()), "min_obs": int(CY["obs"].min()),
                              "n_zero_obs": int((CY["obs"] == 0).sum()),
                              "pass": bool((CY["draw"] == 0).sum() == 0)}
    out["draw_dispersion"] = {"obs_var_over_mean": float(y.var() / y.mean()),
                              "draw_var_over_mean": float(n.var() / max(n.mean(), 1e-12)),
                              "draw_mean": float(n.mean())}
    out["calibration"] = calib_deciles(mu, y)
    Y = S.group_by("member", "Year").agg(pl.col("mu").sum(), pl.col("n_recruit_y1").sum())
    out["yearly_total_corr"] = _corr(Y["mu"], Y["n_recruit_y1"])
    return out


def entry_metrics(H: PatchHeads, members, fold5_only: bool) -> dict:
    R = load_feats(members, recruits=True, folds_keep=[5] if fold5_only else None)
    if R.height > 400_000:
        R = R[np.sort(np.random.default_rng(5).choice(R.height, 400_000, replace=False))]
    Q = H.entry_quantiles(R)
    Q0 = H.entry_quantiles(R, kappa=0.0)
    tab = H.table
    out = {"n_recruits": R.height}
    y = {"height_m5": (R["Height"].cast(pl.Float64) - 5.0).to_numpy(),
         "log_age": np.log(np.maximum(R["Age"].cast(pl.Float64).to_numpy(), 1.0))}
    typ = R["Type"].to_numpy()
    tab_y = {"height_m5": tab["Height"].to_numpy() - 5.0, "log_age": np.log(np.maximum(tab["Age"].to_numpy(), 1.0))}
    ttyp = tab["Type"].to_numpy()
    for tgt in y:
        null = np.zeros((len(typ), len(QLEV)))
        for t in np.unique(typ):
            src = tab_y[tgt][ttyp == t] if (ttyp == t).any() else tab_y[tgt]
            null[typ == t] = np.quantile(src, QLEV)
        pb = {f"q{int(q * 100):02d}": {"model": pinball(Q[tgt][:, i], y[tgt], q),
                                       "climate_blind": pinball(Q0[tgt][:, i], y[tgt], q),
                                       "null_per_type": pinball(null[:, i], y[tgt], q)}
              for i, q in enumerate(QLEV)}
        out[tgt] = {"pinball": pb,
                    "mean_pinball_model": float(np.mean([v["model"] for v in pb.values()])),
                    "mean_pinball_null_per_type": float(np.mean([v["null_per_type"] for v in pb.values()])),
                    "coverage_q05_q95": float(np.mean((y[tgt] >= Q[tgt][:, 0]) & (y[tgt] <= Q[tgt][:, -1]))),
                    "coverage_q25_q75": float(np.mean((y[tgt] >= Q[tgt][:, 2]) & (y[tgt] <= Q[tgt][:, 4]))),
                    "obs_median": float(np.median(y[tgt])), "pred_median_mean": float(np.mean(Q[tgt][:, 3]))}
    # empirical table: sampled vs observed medians by Type x tercile
    terc = H.clim_tercile(R[TERC_VAR].to_numpy())
    smp = H.entry_sample(typ, terc, np.random.default_rng(7).random(len(typ)))
    rows = []
    for t in np.unique(typ):
        for te in range(3):
            m = (typ == t) & (terc == te)
            if m.sum() < 50:
                continue
            rows.append({"Type": int(t), "terc": te, "n": int(m.sum()),
                         "obs_med_height": float(np.median(R["Height"].to_numpy()[m])),
                         "smp_med_height": float(np.nanmedian(smp["Height"][m])),
                         "obs_med_age": float(np.median(R["Age"].to_numpy()[m])),
                         "smp_med_age": float(np.nanmedian(smp["Age"][m])),
                         "obs_mean_c": float(np.mean(R["c"].to_numpy()[m])),
                         "smp_mean_c": float(np.nanmean(smp["c"][m]))})
    out["table_by_type_tercile"] = rows
    return out


def stage_gates(a):
    split = a.split
    H = load_heads(split)
    meta = H.meta
    ms = split_members(split)
    fbar = meta["fire"]["fbar_train"]
    mbar = meta["recruit"]["mean_train"]
    res = {"split": split, "train_members": ms["train"], "test_members": ms["test"],
           "basis_note": "train members scored on fold-5 dev cells (never fitted); test members on fold 5 and on all "
                         "dev cells. 'all_dev' of a TRAIN member includes fitted cells (in-sample).",
           "fire": {}, "recruit": {}, "entry": {}}
    gfl = []
    for m in ms["train"] + ms["test"]:
        g = globalflux_fire(m)
        if g is not None:
            gfl.append(g.with_columns(member=pl.lit(m)))
    GF = pl.concat(gfl) if gfl else None
    res["globalflux_used"] = GF is not None
    groups = [("train_fold5", ms["train"], True), ("train_alldev_insample", ms["train"], False)]
    groups += [(f"test_{m}_fold5", [m], True) for m in ms["test"]]
    groups += [(f"test_{m}_alldev", [m], False) for m in ms["test"]]
    groups += [("test_pooled_alldev", ms["test"], False)]
    cache = {}
    for name, members, f5 in groups:
        t0 = time.time()
        Ss = []
        for m in members:
            k = (m, f5)
            if k not in cache:
                cache[k] = score_member(H, m, f5)["S"]
            Ss.append(cache[k])
        S = pl.concat(Ss)
        fm, _ = fire_metrics(S, fbar, GF)
        res["fire"][name] = fm
        if not name.startswith("train_alldev"):
            res["recruit"][name] = recruit_metrics(H, S, mbar, draw_seed=zlib.crc32(name.encode()))
        log(f"gates {name}: {S.height} rows, {time.time() - t0:.0f} s; fire corr {fm['yearly_corr_model']:.3f} "
            f"(ceiling {fm['noise_ceiling']['ceiling_corr']:.3f})")
        if len(cache) > 6:
            cache.pop(next(iter(cache)))
    res["entry"]["train_fold5"] = entry_metrics(H, ms["train"], True)
    res["entry"]["test_pooled_alldev"] = entry_metrics(H, ms["test"], False)
    # ------------------------------------------------------------- the four gates
    ft = res["fire"]["train_fold5"]
    rt = res["recruit"]["train_fold5"]
    gates = {
        "G1_fire_yearly_corr_ge_0.9_train_fold5": {
            "value": ft["yearly_corr_model"], "pass": bool(ft["yearly_corr_model"] >= 0.9),
            "noise_ceiling": ft["noise_ceiling"]["ceiling_corr"],
            "feasible": bool(ft["noise_ceiling"]["ceiling_corr"] >= 0.9),
            "in_sample_all_dev": res["fire"]["train_alldev_insample"]["yearly_corr_model"],
            "in_sample_all_dev_ceiling": res["fire"]["train_alldev_insample"]["noise_ceiling"]["ceiling_corr"],
            "globalflux": res["fire"]["train_alldev_insample"].get("globalflux"),
            "total_ratio_pred_over_obs": ft["total_ratio_pred_over_obs"]},
        "G2_release_within_10pct_of_truth_train_fold5": {
            "model_ratio": rt["release"]["model_ratio"], "truth_ratio": rt["release"]["truth_ratio"],
            "pass": rt["release"]["pass_within_10pct_of_truth"], "judge_band": [3.6, 4.1],
            "model_in_judge_band": rt["release"]["model_in_judge_band"],
            "truth_in_judge_band": rt["release"]["truth_in_judge_band"]},
        "G3_cellyear_recruit_totals_never_0": {
            k: res["recruit"][k]["cellyear_totals"] for k in res["recruit"]},
        "G4_decile_calibration_train_fold5": {"fire": ft["calibration"]["pass"],
                                              "recruit": rt["calibration"]["pass"]},
    }
    gates["G3_cellyear_recruit_totals_never_0"]["pass"] = all(
        v["pass"] for k, v in gates["G3_cellyear_recruit_totals_never_0"].items() if isinstance(v, dict))
    gates["G4_decile_calibration_train_fold5"]["pass"] = bool(ft["calibration"]["pass"] and rt["calibration"]["pass"])
    gates["G2_release_test_members"] = {k: {"model_ratio": v["release"]["model_ratio"],
                                            "truth_ratio": v["release"]["truth_ratio"],
                                            "pass": v["release"]["pass_within_10pct_of_truth"]}
                                        for k, v in res["recruit"].items() if k.startswith("test_")}
    gates["G4_calibration_test_members"] = {k: {"fire": res["fire"][k]["calibration"]["pass"],
                                                "recruit": res["recruit"][k]["calibration"]["pass"]}
                                            for k in res["recruit"] if k.startswith("test_")}
    res["gates"] = gates
    json.dump(res, open(os.path.join(OUT, split, "_gates.json"), "w"), indent=1, default=float)
    summ = {k: v.get("pass") for k, v in gates.items() if isinstance(v, dict) and "pass" in v}
    status(f"gates {split}: {summ}")
    if not SMOKE:
        os.makedirs(os.path.dirname(REPORT), exist_ok=True)
        rep = {"item": "SH13", "split": split, "script": os.path.join(SCRIPTS, os.path.basename(__file__)),
               "out_dir": os.path.join(OUT, split), "gates_file": os.path.join(OUT, split, "_gates.json"),
               "gates_summary": summ, "fire_kappa": meta["fire"]["kappa"], "recruit_kappa": meta["recruit"]["kappa"],
               "nb_alpha": meta["recruit"]["nb_alpha"], "gates": gates,
               "fire_train_fold5": {k: v for k, v in ft.items() if k != "calibration"},
               "recruit_train_fold5": {k: v for k, v in rt.items() if k != "calibration"},
               "entry": res["entry"]}
        json.dump(rep, open(REPORT, "w"), indent=1, default=float)
    print(json.dumps(summ, indent=1))


# ================================================================================================ submit / smoke
def _jcf(name, body, cpus, time_, dep=None, array=None):
    jobs = os.path.join(XDE, "_jobs")
    os.makedirs(jobs, exist_ok=True)
    os.makedirs(LOGS, exist_ok=True)
    f = os.path.join(jobs, f"SH13_{name}.jcf")
    lines = ["#!/bin/bash", f"#SBATCH --job-name=X-de-SH13-{name}", "#SBATCH --account=waldspektrum",
             "#SBATCH --partition=priority", "#SBATCH --qos=priority", f"#SBATCH --cpus-per-task={cpus}",
             f"#SBATCH --time={time_}",
             f"#SBATCH --output={LOGS}/X-de-SH13-{name}.%A_%a.out" if array else
             f"#SBATCH --output={LOGS}/X-de-SH13-{name}.%j.out"]
    if dep:
        lines.append(f"#SBATCH --dependency=afterok:{dep}")
    if array:
        lines.append(f"#SBATCH --array={array}")
    lines += ["set -eu", f"export POLARS_MAX_THREADS={cpus}", body, 'echo "=== JOB DONE exit=$? ==="']
    open(f, "w").write("\n".join(lines) + "\n")
    jid = subprocess.run(["sbatch", "--parsable", f], capture_output=True, text=True, check=True).stdout.strip()
    return jid.split(";")[0]


def stage_submit(a):
    me = os.path.join(SCRIPTS, os.path.basename(__file__))
    ms = split_members(a.split)
    members = ms["train"] + ms["test"]
    env = "SH13_SMOKE=1 " if SMOKE else ""
    dep = None
    if not a.skip_prep:
        tl = os.path.join(XDE, "_jobs", "SH13_prep_members.txt")
        os.makedirs(os.path.dirname(tl), exist_ok=True)
        open(tl, "w").write("\n".join(members) + "\n")
        body = (f'M=$(sed -n "$((SLURM_ARRAY_TASK_ID+1))p" {tl})\n'
                f"{env}{PY} {me} prep --split {a.split} --member $M")
        dep = _jcf("prep", body, 8, "01:30:00", array=f"0-{len(members) - 1}")
    jf = None
    if not a.skip_fit:
        jf = _jcf("fit", f"{env}{PY} {me} fit --split {a.split} --val-fold {a.val_fold} --rounds {a.rounds}"
                  + (f" --only {a.only}" if a.only else ""), 16,
                  "04:00:00", dep=dep)
    jg = _jcf("gates", f"{env}{PY} {me} gates --split {a.split}", 16, "02:00:00", dep=jf or dep)
    status(f"submitted split {a.split}: prep {dep}, fit {jf}, gates {jg} (smoke={SMOKE})")
    print(dep, jf, jg)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="stage", required=True)
    for s in ("prep", "fit", "gates", "submit"):
        p = sub.add_parser(s)
        p.add_argument("--split", default="DEV-A")
        p.add_argument("--member", nargs="*")
        p.add_argument("--force", action="store_true")
        p.add_argument("--val-fold", default=4, type=int)
        p.add_argument("--rounds", default=1500, type=int)
        p.add_argument("--skip-prep", action="store_true")
        p.add_argument("--skip-fit", action="store_true")
        p.add_argument("--only", choices=["fire"], default=None, help="fit: refit only the fire head")
    a = ap.parse_args(argv)
    {"prep": stage_prep, "fit": stage_fit, "gates": stage_gates, "submit": stage_submit}[a.stage](a)


if __name__ == "__main__":
    main()
