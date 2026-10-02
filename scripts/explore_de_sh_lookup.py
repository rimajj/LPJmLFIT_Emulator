#!/usr/bin/env python3
"""explore_de_sh_lookup.py — LINE X, Germany data-driven emulator, shared item SH7: the LOOKUP arms.

The owner's "most naive emulator ... like a look up table" (2026-09-30), built honestly: nothing is learned. Every
tree is matched to its k = 16 nearest observed transitions in the TRAINING members' per-tree table (SH3) and copies
ONE of them (drawn uniformly with the engine's counter-based random numbers): its fate, its relative change of agb
and vegc, its change of LAI, fpc_ind and D95, and its next-year growth efficiency G; the bad-growth counter then
follows the original model's rule (c = 5 kills) and Height the SH2 allometry. Every patch is matched to its nearest
observed patch-year (SH4) and copies that patch's recruits: their Type, entry size/age/counter/G and their traits as
an OFFSET from the source cell's same-Type standing median, added to this cell's own same-Type median (training
median of the Type if the cell has none; clipped to the Type's training range).

Matching keys (z-scored on the bank):
  tree   log agb, Height, Age, Wooddens, SLA, G_y, fpc_above, patch sum_fpc, patch n_live
         + climate of y+1: anom_tmean_ann, anom_prec_jja, anom_cwb_jja, anom_gdd5 and absolute tmean_ann
         bank partitioned by (Type, c_y); at most --bank-rows per partition chosen by u_hash
  patch  survivors' fpc (sum_fpc_y x (1 - loss of y+1)), loss of y+1, sum of the losses of y..y-3, of y-4..y-18,
         n_live, the cell's beech share + the same climate keys
Variants: LOOKUP (main), LOOKUP-noclim (climate keys dropped: kwargs {"noclim": true}), LOOKUP-verbatim (recruit
traits copied as they are: {"verbatim": true}, a diagnostic).
Simplification (stated): a tree the copy sends below the 5 m print cut is removed, not kept hidden — re-entries of
shrunken trees (0.3-1 % of new stems, SH4) are therefore not produced; patches that copy a recruit count include only
true recruits.

STAGES  bank --split DEV-A [--bank-rows 300000]   build the banks from the split's training members, dev folds 1-4
        gate --split DEV-A                          teacher-forced one-step death and recruit rates on fold-5 dev cells
                                                    of the training-GCM members vs truth (pre-registered: within 5 %)
Stepper: explore_de_sh_lookup:Lookup (kwargs: split, noclim, verbatim, k).
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
import time

import numpy as np
import polars as pl
from scipy.spatial import cKDTree

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_engine as en  # noqa: E402
import explore_de_sh_patch as sp  # noqa: E402
import explore_de_sh_rules as rl  # noqa: E402
import explore_de_sh_trans as tr  # noqa: E402

XDE = tr.XDE
OUT = os.path.join(XDE, "shared", "lookup")
CLIM_KEYS = ["anom_tmean_ann", "anom_prec_jja", "anom_cwb_jja", "anom_gdd5", "tmean_ann"]
TREE_STATE_KEYS = ["log_agb", "Height", "Age", "Wooddens", "SLA", "G_y", "fpc_above", "sum_fpc", "n_live"]
PATCH_STATE_KEYS = ["fpc_surv", "loss_now", "loss_2_5", "loss_6_20", "n_live_y", "beech_share"]
TREE_TARGETS = ["fate_y1", "dlog_agb", "dlog_vegc", "dLAI", "dfpc", "dD95", "G_y1"]
REC_FIELDS = ["Type", "Height", "Age", "agb", "vegc", "LAI", "fpc_ind", "D95", "c", "G", "isdead"] + tr.TRAITS
STD_TRAITS = sp.STD_TRAITS
log = tr.log


def training_members(split: str) -> list[str]:
    s = pl.read_parquet(os.path.join(tr.REG, "splits.parquet")).filter(
        (pl.col("split") == split) & (pl.col("role") == "train"))
    return sorted(set(s["src_member"].to_list() if "src_member" in s.columns else s["member"].to_list()))


def train_cells(split: str) -> list[int]:
    f = pl.read_parquet(os.path.join(tr.REG, "folds.parquet")).filter(pl.col("is_dev") & (pl.col("fold") <= 4))
    return f["Cell"].to_list()


# ------------------------------------------------------------------------------------------------ bank
def stage_bank(a):
    t0 = time.time()
    mem, _, _ = tr.registry()
    members = training_members(a.split)
    cells = train_cells(a.split)
    log(f"bank {a.split}: members {members}, {len(cells)} training cells")
    cols = ["gcm", "traj", "seed", "Year", "Cell", "Patch", "Type", "c_y", "u_hash", "agb", "Height", "Age",
            "Wooddens", "SLA", "G_y", "fpc_above", "sum_fpc", "n_live", "fate_y1", "agb_y1", "vegc", "vegc_y1",
            "LAI", "LAI_y1", "fpc_ind", "fpc_ind_y1", "D95", "D95_y1", "G_y1", "cenG_y1"]
    frames = []
    for m in members:
        # every c >= 1 row (rare partitions) + a 10 % u_hash sample of c = 0 (each partition later keeps at most
        # --bank-rows rows by u_hash, so the sample stays uniform)
        lf = pl.scan_parquet(os.path.join(tr.TRANS, "dev", m, "cb=dev", "*.parquet")).filter(
            pl.col("Cell").is_in(cells) & ((pl.col("c_y") >= 1) | (pl.col("u_hash") < a.c0_frac))).select(cols)
        frames.append(lf)
    T = pl.concat(frames).collect()
    log(f"  tree rows {T.height}")
    T = tr.join_climate(T, cols=[c for c in CLIM_KEYS], years=("y1",), ext=True)
    T = T.with_columns(log_agb=pl.col("agb").cast(pl.Float64).log(),
                       dlog_agb=(pl.col("agb_y1").cast(pl.Float64) / pl.col("agb").cast(pl.Float64)).log(),
                       dlog_vegc=(pl.col("vegc_y1").cast(pl.Float64) / pl.col("vegc").cast(pl.Float64)).log(),
                       dLAI=pl.col("LAI_y1") - pl.col("LAI"), dfpc=pl.col("fpc_ind_y1") - pl.col("fpc_ind"),
                       dD95=pl.col("D95_y1") - pl.col("D95"))
    # censored next-year G (mort_npp printed >= 1): keep the row (its fate is real), G' = the row's G (no info)
    T = T.with_columns(G_y1=pl.when(pl.col("G_y1").is_finite()).then(pl.col("G_y1")).otherwise(pl.col("G_y")))
    T = T.with_columns([pl.col(c).fill_null(0.0) for c in ["dlog_agb", "dlog_vegc", "dLAI", "dfpc", "dD95"]])
    os.makedirs(os.path.join(OUT, a.split), exist_ok=True)
    meta = {"split": a.split, "members": members, "n_cells": len(cells), "tree_rows": T.height, "partitions": {}}
    for noclim in (False, True):
        keys = TREE_STATE_KEYS + ([] if noclim else [f"{c}_y1" for c in CLIM_KEYS])
        banks = {}
        for (typ, c), g in T.group_by(["Type", pl.col("c_y").clip(0, 5)]):
            if g.height > a.bank_rows:
                g = g.sort("u_hash").head(a.bank_rows)
            X = g.select(keys).cast(pl.Float64).to_numpy()
            ok = np.isfinite(X).all(1)
            X, g = X[ok], g.filter(pl.Series(ok))
            mu, sd = X.mean(0), X.std(0) + 1e-9
            banks[(int(typ), int(c))] = {"tree": cKDTree((X - mu) / sd, leafsize=32), "mu": mu, "sd": sd,
                                         "Y": g.select(TREE_TARGETS).cast(pl.Float64).to_numpy()}
            meta["partitions"][f"{typ}_{c}_{'noclim' if noclim else 'clim'}"] = int(g.height)
        # per-Type fallback (any counter)
        for typ, g in T.group_by("Type"):
            typ = int(typ[0]) if isinstance(typ, tuple) else int(typ)
            g = g.sort("u_hash").head(a.bank_rows)
            X = g.select(keys).cast(pl.Float64).to_numpy()
            ok = np.isfinite(X).all(1)
            X, g = X[ok], g.filter(pl.Series(ok))
            mu, sd = X.mean(0), X.std(0) + 1e-9
            banks[(typ, -1)] = {"tree": cKDTree((X - mu) / sd, leafsize=32), "mu": mu, "sd": sd,
                                "Y": g.select(TREE_TARGETS).cast(pl.Float64).to_numpy()}
        with open(os.path.join(OUT, a.split, f"tree_bank_{'noclim' if noclim else 'clim'}.pkl"), "wb") as f:
            pickle.dump({"keys": keys, "banks": banks}, f, protocol=5)
    del T
    # ---- patch bank (+ its recruits)
    Ps, Rs = [], []
    for m in members:
        Ps.append(pl.scan_parquet(os.path.join(sp.PATCH, "dev", m, "cb=dev", "*.parquet")).filter(
            pl.col("Cell").is_in(cells)).collect())
        Rs.append(pl.scan_parquet(os.path.join(sp.RECR, "dev", m, "cb=dev", "*.parquet")).filter(
            pl.col("Cell").is_in(cells)).collect())
    Pt = pl.concat(Ps, how="diagonal_relaxed")
    Rt = pl.concat(Rs, how="diagonal_relaxed")
    beech = (pl.concat([pl.scan_parquet(os.path.join(tr.TRANS, "dev", m, "cb=dev", "*.parquet"))
                        .filter(pl.col("Cell").is_in(cells)).group_by("member", "Cell", "Year")
                        .agg(beech_share=pl.col("cell_share_t3").first()).collect() for m in members]))
    Pt = patch_features_truth(Pt).join(beech, on=["member", "Cell", "Year"], how="left").with_columns(
        pl.col("beech_share").fill_null(0.0))
    Pt = tr.join_climate(Pt.with_columns(pl.col("seed").cast(pl.Int8)), cols=CLIM_KEYS, years=("y1",), ext=True)
    Pt = Pt.with_row_index("_pid")
    # deterministic subsample of patch-years
    Pt = Pt.with_columns(_h=pl.struct("member", "Cell", "Patch", "Year").hash(11))
    if Pt.height > a.bank_rows * 2:
        Pt = Pt.sort("_h").head(a.bank_rows * 2)
    Rt = Rt.join(Pt.select("member", "Cell", "Patch", "Year", "_pid"), on=["member", "Cell", "Patch", "Year"],
                 how="inner").sort("_pid")
    rec_ptr = Rt.group_by("_pid").agg(pl.len().alias("n")).sort("_pid")
    pid_to_rows = {}
    starts = np.r_[0, np.cumsum(rec_ptr["n"].to_numpy())]
    for i, p in enumerate(rec_ptr["_pid"].to_numpy()):
        pid_to_rows[int(p)] = (int(starts[i]), int(starts[i + 1]))
    std_cols = [f"std_{t}_median" for t in STD_TRAITS]
    R = {c: Rt[c].cast(pl.Float64).to_numpy() for c in REC_FIELDS + std_cols if c in Rt.columns}
    R["isdead"] = Rt["isdead"].to_numpy().astype(bool)
    for noclim in (False, True):
        keys = PATCH_STATE_KEYS + ([] if noclim else [f"{c}_y1" for c in CLIM_KEYS])
        X = Pt.select(keys).cast(pl.Float64).fill_null(0.0).to_numpy()
        mu, sd = X.mean(0), X.std(0) + 1e-9
        # (patch bank tree built below)
        pids = Pt["_pid"].to_numpy()
        rr = np.array([pid_to_rows.get(int(p), (0, 0)) for p in pids], dtype=np.int64)
        with open(os.path.join(OUT, a.split, f"patch_bank_{'noclim' if noclim else 'clim'}.pkl"), "wb") as f:
            pickle.dump({"keys": keys, "tree": cKDTree((X - mu) / sd, leafsize=32), "mu": mu, "sd": sd,
                         "rec_range": rr, "R": R}, f, protocol=5)
    # training medians and ranges per Type (fallback + clipping)
    tm = Rt.group_by("Type").agg(**{f"{t}_med": pl.col(t).cast(pl.Float64).median() for t in STD_TRAITS},
                                 **{f"{t}_lo": pl.col(t).cast(pl.Float64).min() for t in STD_TRAITS},
                                 **{f"{t}_hi": pl.col(t).cast(pl.Float64).max() for t in STD_TRAITS})
    tm.write_parquet(os.path.join(OUT, a.split, "type_trait_stats.parquet"))
    meta.update({"patch_rows": Pt.height, "recruit_rows": Rt.height, "seconds": time.time() - t0})
    json.dump(meta, open(os.path.join(OUT, a.split, "meta.json"), "w"), indent=1)
    log(json.dumps({k: v for k, v in meta.items() if k != "partitions"}))


def patch_features_truth(Pt: pl.DataFrame) -> pl.DataFrame:
    s25 = pl.sum_horizontal([pl.col(f"frac_loss_lag{k}").fill_null(0.0) for k in range(0, 4)])
    s620 = pl.sum_horizontal([pl.col(f"frac_loss_lag{k}").fill_null(0.0) for k in range(4, 19)])
    return Pt.with_columns(fpc_surv=pl.col("sum_fpc_y") * (1 - pl.col("frac_loss_y1")),
                           loss_now=pl.col("frac_loss_y1"), loss_2_5=s25, loss_6_20=s620)


# ------------------------------------------------------------------------------------------------ stepper
class Lookup:
    needs_bank = False

    def __init__(self, split: str = "DEV-A", noclim: bool = False, verbatim: bool = False, k: int = 16,
                 eps: float = 1.0, workers: int | None = None):
        """eps: approximate neighbour search (scipy cKDTree: every returned neighbour is within (1 + eps) of the
        true k-th distance; measured 94 % overlap with the exact 16 at eps = 1, 12x faster). workers: query threads
        (default: POLARS_MAX_THREADS, 1 under the timing harness)."""
        self.split, self.noclim, self.verbatim, self.k = split, noclim, verbatim, int(k)
        self.eps = float(eps)
        self.workers = int(workers or os.environ.get("POLARS_MAX_THREADS", "1"))

    def init(self, state, ctx):
        tag = "noclim" if self.noclim else "clim"
        with open(os.path.join(OUT, self.split, f"tree_bank_{tag}.pkl"), "rb") as f:
            self.tb = pickle.load(f)
        with open(os.path.join(OUT, self.split, f"patch_bank_{tag}.pkl"), "rb") as f:
            self.pb = pickle.load(f)
        self.tstats = pl.read_parquet(os.path.join(OUT, self.split, "type_trait_stats.parquet"))
        self.allom = rl.load_allometry(self.split)
        self.P = ctx["P"]
        # hidden trees are not used by this arm: drop them from the start state
        state.tree["hidden"][:] = False

    def _clim(self, cells, clim_y1):
        cj = pl.DataFrame({"Cell": cells.astype(np.int32)}).join(
            clim_y1.with_columns(pl.col("Cell").cast(pl.Int32)), on="Cell", how="left")
        return np.column_stack([cj[c].cast(pl.Float64).fill_null(0.0).to_numpy() for c in CLIM_KEYS])

    def step(self, state, ctx, year, clim_y1, flags_y1, rand):
        t = state.tree
        n = state.n
        y = year
        cells = state.cell["cells"]
        npatch = state.npatch
        pidx = state.patch_index()
        npat = len(cells) * npatch
        fpc = t["fpc_ind"].astype(np.float64)
        agb = t["agb"].astype(np.float64)
        sum_fpc = np.bincount(pidx, weights=fpc, minlength=npat)
        n_live = np.bincount(pidx, minlength=npat).astype(np.float64)
        # fpc of strictly taller stems in the patch
        order = np.lexsort((-t["Height"].astype(np.float64), pidx))
        cs = np.zeros(n)
        po, fo, ho = pidx[order], fpc[order], t["Height"][order]
        cum = np.cumsum(fo)
        first = np.r_[True, po[1:] != po[:-1]]
        base = np.maximum.accumulate(np.where(first, np.arange(n), 0))
        ex = cum - fo - np.where(base > 0, cum[base - 1], 0.0) * (base > 0)
        # ties: equal heights share the same "taller" sum (take the minimum within the tie group)
        tie_grp = np.cumsum(np.r_[True, (po[1:] != po[:-1]) | (ho[1:] != ho[:-1])])
        ex = pl.DataFrame({"g": tie_grp, "e": ex}).with_columns(pl.col("e").min().over("g"))["e"].to_numpy()
        cs[order] = ex
        ci = state.cell_index(t["Cell"])
        C = self._clim(cells, clim_y1)
        Xs = np.column_stack([np.log(np.maximum(agb, 1e-6)), t["Height"], t["Age"], t["Wooddens"], t["SLA"], t["G"],
                              cs, sum_fpc[pidx], n_live[pidx]])
        X = Xs if self.noclim else np.column_stack([Xs, C[ci]])
        cc = np.clip(t["c"].astype(np.int64), 0, 5)
        Y = np.zeros((n, len(TREE_TARGETS)))
        u = rand.uniform("lookup_pick", y, t["Cell"], t["Patch"], t["Type"], t["ID"])
        for typ in np.unique(t["Type"]):
            for c in np.unique(cc[t["Type"] == typ]):
                m = (t["Type"] == typ) & (cc == c)
                b = self.tb["banks"].get((int(typ), int(c))) or self.tb["banks"].get((int(typ), -1))
                if b is None:
                    raise KeyError(f"no lookup bank for Type {typ}")
                kk = min(self.k, b["Y"].shape[0])
                _, nb = b["tree"].query((X[m] - b["mu"]) / b["sd"], k=kk, eps=self.eps, workers=self.workers)
                nb = nb.reshape(m.sum(), kk)
                pick = nb[np.arange(m.sum()), np.minimum((u[m] * kk).astype(np.int64), kk - 1)]
                Y[m] = b["Y"][pick]
        fate = Y[:, 0].astype(np.int64)
        G1 = Y[:, 6]
        age_pre = t["Age"].astype(np.float64)
        c1 = rl.counter_step(t["c"].astype(np.int64), G1, age_pre)
        dead = (fate == 1) | (c1 >= 5)
        gone = (fate == 2) & ~dead
        agb1 = agb * np.exp(Y[:, 1])
        upd = {"agb": agb1, "vegc": t["vegc"] * np.exp(Y[:, 2]), "LAI": np.maximum(t["LAI"] + Y[:, 3], 1e-4),
               "fpc_ind": np.maximum(t["fpc_ind"] + Y[:, 4], 1e-6), "D95": np.maximum(t["D95"] + Y[:, 5], 1.0),
               "G": G1, "c": np.minimum(c1, 5), "Age": t["Age"] + 1, "d_agb_prev": agb1 - agb}
        upd["Height"] = rl.predict_height(agb1, t["Wooddens"], t["SLA"], t["Type"], self.allom)
        # ---- recruits: patch lookup
        lost = np.bincount(pidx, weights=np.where(dead | gone, fpc, 0.0), minlength=npat)
        loss_now = np.where(sum_fpc > 0, lost / np.where(sum_fpc > 0, sum_fpc, 1), 0.0)
        ring = np.nan_to_num(state.patch["loss_ring"].astype(np.float64))
        beech = np.bincount(ci, weights=(t["Type"] == 3).astype(float), minlength=len(cells)) / np.maximum(
            np.bincount(ci, minlength=len(cells)), 1)
        pc = np.repeat(np.arange(len(cells)), npatch)
        Xp = np.column_stack([sum_fpc - lost, loss_now, ring[:, 0:4].sum(1), ring[:, 4:19].sum(1), n_live,
                              beech[pc]])
        if not self.noclim:
            Xp = np.column_stack([Xp, C[pc]])
        pb = self.pb
        kk = self.k
        _, nb = pb["tree"].query((Xp - pb["mu"]) / pb["sd"], k=kk, eps=self.eps, workers=self.workers)
        pcell, ppat = cells[pc], np.tile(np.arange(npatch), len(cells))
        up = rand.uniform("lookup_patch", y, pcell, ppat)
        pick = nb[np.arange(npat), np.minimum((up * kk).astype(np.int64), kk - 1)]
        rr = pb["rec_range"][pick]
        cnt = rr[:, 1] - rr[:, 0]
        src = np.concatenate([np.arange(a, b) for a, b in rr if b > a]) if cnt.sum() else np.zeros(0, np.int64)
        R = pb["R"]
        recs = {"Cell": np.repeat(pcell, cnt), "Patch": np.repeat(ppat, cnt)}
        for f in REC_FIELDS:
            recs[f] = R[f][src]
        if not self.verbatim and len(src):
            recs = self._offset_traits(recs, R, src, state)
        recs["W"] = np.zeros(len(src))
        recs["d_agb_prev"] = np.zeros(len(src))
        recs["c"] = np.clip(recs["c"], 0, 5)
        if len(src):
            recs["beta_root"] = rl.getbetaroot(recs["D95max"], self.P)
        self.last = {"year": y + 1, "dead": int(dead.sum()), "gone": int(gone.sum()), "recruits": int(len(src)),
                     "n": n}
        return en.StepOut(tree=upd, isdead=dead, hidden=np.zeros(n, bool), remove=gone, recruits=recs)

    def _offset_traits(self, recs, R, src, state):
        """trait = this cell's same-Type standing median + (recruit trait - source cell's same-Type median)."""
        t = state.tree
        S = pl.DataFrame({"Cell": t["Cell"], "Type": t["Type"], **{k: t[k] for k in STD_TRAITS}}).group_by(
            "Cell", "Type").agg(**{f"m_{k}": pl.col(k).cast(pl.Float64).median() for k in STD_TRAITS})
        q = pl.DataFrame({"Cell": recs["Cell"].astype(np.int16), "Type": recs["Type"].astype(np.int8)}).with_row_index(
            "_i").join(S.with_columns(pl.col("Cell").cast(pl.Int16), pl.col("Type").cast(pl.Int8)),
                       on=["Cell", "Type"], how="left").join(
            self.tstats.with_columns(pl.col("Type").cast(pl.Int8)), on="Type", how="left").sort("_i")
        for k in STD_TRAITS:
            own = q[f"m_{k}"].fill_null(q[f"{k}_med"]).to_numpy()
            srcm = R.get(f"std_{k}_median")
            off = recs[k] - (np.nan_to_num(srcm[src], nan=np.nan) if srcm is not None else 0.0)
            v = np.where(np.isfinite(off), own + off, recs[k])
            recs[k] = np.clip(v, q[f"{k}_lo"].to_numpy(), q[f"{k}_hi"].to_numpy())
        return recs


# ------------------------------------------------------------------------------------------------ gate
def stage_gate(a):
    """Teacher-forced one-step death and recruit rates on fold-5 dev cells of the training members vs truth."""
    P = rl.load_params()
    members = training_members(a.split)
    f5 = pl.read_parquet(os.path.join(tr.REG, "folds.parquet")).filter(pl.col("is_dev") & (pl.col("fold") == 5))
    cells = np.sort(f5["Cell"].to_numpy())
    res = {}
    L = Lookup(a.split)
    loaded = False
    for m in members:
        row = tr.member_row(tr.registry()[0], m)
        g = json.load(open(os.path.join(tr.TRANS, "dev", m, "cb=dev", "_gates.json")))
        ys = g["out_years"][:: max(1, len(g["out_years"]) // 6)]
        out = []
        for y in ys:
            init = f"{row['gcm']}_Historical_s{row['seed']}_1985"  # only for the RosterState container layout
            st = en.load_init(init, "dev", cells)
            T = pl.read_parquet(os.path.join(tr.TRANS, "dev", m, "cb=dev", f"y{y}.parquet")).filter(
                pl.col("Cell").is_in(cells.tolist())).sort("Cell", "Patch", "Type", "ID")
            st.tree = en._typed({c: T[c].to_numpy() for c in ["Cell", "Patch", "Type", "ID"] + tr.TRAITS
                                 + ["Height", "agb", "vegc", "LAI", "fpc_ind", "D95", "Age"]}
                                | {"c": T["c_y"].to_numpy(), "G": T["G_y"].fill_null(0.0).to_numpy(),
                                   "isdead": np.zeros(T.height, bool), "hidden": np.zeros(T.height, bool)})
            Pt = pl.read_parquet(os.path.join(sp.PATCH, "dev", m, "cb=dev", f"y{y}.parquet")).filter(
                pl.col("Cell").is_in(cells.tolist())).sort("Cell", "Patch")
            st.patch["loss_ring"] = np.column_stack([Pt[f"frac_loss_lag{k}"].fill_null(np.nan).to_numpy()
                                                     for k in range(en.NLAG)]).astype(np.float32)
            clim = en.Climate(row["gcm"], row["scen"], int(row["seed"]), cells).year(y + 1)
            if not loaded:
                L.init(st, {"P": P})
                loaded = True
            o = L.step(st, {}, y, clim, {"rh_on": 1}, en.Rand("lookup_gate", 1, row["gcm"]))
            out.append({"Year": y, "n": T.height, "truth_dead": int((T["fate_y1"] == 1).sum()),
                        "lookup_dead": int(o.isdead.sum()),
                        "truth_recruits": int(Pt["n_recruit_y1"].sum()), "lookup_recruits": len(o.recruits["Cell"])})
            log(f"{m} {y}: {out[-1]}")
        d = pl.DataFrame(out)
        tdr, ldr = d["truth_dead"].sum() / d["n"].sum(), d["lookup_dead"].sum() / d["n"].sum()
        trr, lrr = d["truth_recruits"].sum() / d["n"].sum(), d["lookup_recruits"].sum() / d["n"].sum()
        res[m] = {"years": ys, "truth_death_rate": tdr, "lookup_death_rate": ldr, "death_ratio": ldr / tdr,
                  "truth_recruit_rate": trr, "lookup_recruit_rate": lrr, "recruit_ratio": lrr / trr,
                  "pass": abs(ldr / tdr - 1) <= 0.05 and abs(lrr / trr - 1) <= 0.05}
    res["all_pass"] = all(v["pass"] for v in res.values() if isinstance(v, dict))
    json.dump(res, open(os.path.join(OUT, a.split, "_gate.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["bank", "gate"])
    ap.add_argument("--split", default="DEV-A")
    ap.add_argument("--bank-rows", type=int, default=300_000)
    ap.add_argument("--c0-frac", type=float, default=0.1)
    a = ap.parse_args(argv)
    {"bank": stage_bank, "gate": stage_gate}[a.stage](a)


if __name__ == "__main__":
    main()
