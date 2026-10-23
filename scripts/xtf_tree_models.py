#!/usr/bin/env python3
"""xtf_tree_models.py -- ADR 0368 experiment 2 (SEPARATE EXPERIMENT, not for the paper): does a model that sees the
whole patch predict tree deaths better than one that sees a single tree?

  train --arm P0|P1           per-tree LightGBM (P1 + hand-made patch summaries)     -> DATA/<arm>/model.txt
  train --arm ST --seed s     set transformer over the patch's trees                 -> DATA/ST_s<s>/model.pt
  predict --arm ... [--seed]  every kept tree of every leg                           -> DATA/<run>/pred.parquet
  score                       skill / calibration / 30-yr death rate / die-off capture -> DATA/score*.csv
ADR 0369 (per-tree carbon state; tables xtf/trees_v2 carry it, xtf_tree_pairs.py):
  cstrain --variant c|e|<m> --fold 0|1   the carbon-state model: per tree, next year's log leaf-carbon margin and
                              P(bad year) and P(margin < 1) from the y-1 tree + state + cell carbon (c = the
                              original's cell NPP/GPP, e = the deployed daily networks', other = carbon table suffix)
  cspredict --variant v       cross-fitted predictions (training cells by the other fold's model, others the mean)
                              -> DATA/cs_<v>.parquet
  train --arm STK|STKt|STKCe|STKc|STKe|...   set transformers with the carbon state (see ARM_STATE)

Tables: xtf_tree_pairs.py (one parquet per seed x climate model x scenario). Teacher-forced one year ahead: each year
starts from the original's own trees. Training = seed 2, the 8 training climate models x 3 scenarios, training
cells (the 15 % patch-year sample), validation = the f2 validation blocks. Test = held-out cells, seeds 2 and 3.
"""

from __future__ import annotations

import argparse
import glob
import math
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import clu_emu_maps as M  # noqa: E402
import xtf_tree_pairs as TP  # noqa: E402

DATA = "/p/projects/open/Jamir/esm_land_emulator_data/xtf/treemort"
TRAIN_GCMS = [g for g in M.GCMS if g not in M.TEST_GCMS]
TREE_F = ["Type"] + [c for c in TP.TREE_F]
PATCH_F = ["pt_n", "pt_fpc", "pt_agb", "pt_npp", "pt_hrank", "pt_fpc_taller", "pt_npp_rel"]
SLOG = ["agb", "vegc", "npp", "npp_y", "transp", "stemdiam", "barkthickness", "Age", "D95", "D95max", "Wooddens",
        "c_prev", "c_y"]
LGB = dict(objective="binary", learning_rate=0.05, num_leaves=31, min_data_in_leaf=20, feature_fraction=0.8,
           bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1, num_threads=32, seed=1)  # fmt: skip
ROUNDS = 400


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ------------------------------------------------------------------------------------------------ data
_CLIM = {}


def climate(gcm, ssp):
    """(Cell, Year) -> c_* (year y), p_* (y-1), w_* (trailing 30-yr means at y), co2, lat."""
    if (gcm, ssp) in _CLIM:
        return _CLIM[(gcm, ssp)]
    cc = M.clim_cols()
    a = pl.read_parquet(f"{M.OUT}/climate/{gcm}_{ssp}.parquet").select(["Cell", "Year"] + cc)
    cur = a.rename({c: f"c_{c}" for c in cc})
    prv = a.with_columns(pl.col("Year") + 1).rename({c: f"p_{c}" for c in cc})
    win = M.window(ssp, gcm).select(["Cell", "Year"] + cc).rename({c: f"w_{c}" for c in cc})
    co2 = M.co2_series(ssp)
    lat = M.cells().select("Cell", pl.col("lat").cast(pl.Float32))
    d = (cur.join(prv, on=["Cell", "Year"]).join(win, on=["Cell", "Year"]).join(lat, on="Cell")
         .with_columns(pl.col("Year").replace_strict(co2, return_dtype=pl.Float32).alias("co2"))
         .with_columns(pl.col(pl.Float64).cast(pl.Float32)))  # fmt: skip
    _CLIM[(gcm, ssp)] = d
    return d


CARBON = {"STCt": "true", "STCe": "emu"}  # ADR 0368 section 2b: + the year's cell carbon balance
# ADR 0369: per-tree carbon state. arm -> (state inputs, carbon-state model variant or None, cell carbon source)
STATE_PREV = ["lr_prev", "c_prev"]
STATE_TRUE = ["lr_y", "bad_y", "c_y"]
CS_OUT = ["cs_lr", "cs_bad", "cs_low"]
ARM_STATE = {"STK": (STATE_PREV, None, None), "STKt": (STATE_PREV + STATE_TRUE, None, None),
             "STKCe": (STATE_PREV, None, "emu"), "STKc": (STATE_PREV, "c", "true"),
             "STKe": (STATE_PREV, "e", "emu")}  # fmt: skip
CS_CARBON = {"c": "true", "e": "emu"}  # carbon-state model variant -> cell carbon source (others: the suffix itself)


def register_daily_arm(tag):
    """ADR 0369: arms that read the cell carbon of another daily model (carbon table columns npp_<tag> ...):
    STC<tag> (= STCe with it) and STK<tag> (= STKe with it, carbon-state model variant <tag>)."""
    CARBON[f"STC{tag}"] = tag
    ARM_STATE[f"STK{tag}"] = (STATE_PREV, tag, tag)
    CS_CARBON[tag] = tag


for _t in os.environ.get("XTF_DAILY_TAGS", "").split(","):
    if _t:
        register_daily_arm(_t)


def carbon_cols(src):
    return [f"{v}_{src}{a}" for v in ("npp", "gpp") for a in ("", "_anom")] if src else []


def cell_cols(arm=None):
    cc = M.clim_cols()
    base = ["lat", "co2"] + [f"{p}_{c}" for p in ("c", "p", "w") for c in cc]
    if arm in CARBON:
        base += carbon_cols(CARBON[arm])
    if arm in ARM_STATE:
        base += carbon_cols(ARM_STATE[arm][2])
    return base


def tree_cols(arm=None):
    base = [c for c in TREE_F if c != "Type"] + (["npp_y"] if arm == "STTt" else [])
    if arm in ARM_STATE:
        base += ARM_STATE[arm][0] + (CS_OUT if ARM_STATE[arm][1] else [])
    return base


def cs_variant(arm):
    return ARM_STATE[arm][1] if arm in ARM_STATE else None


def load(seed, gcm, ssp, where=None, cs=None):
    p = f"{TP.OUT}/s{seed}_{gcm}_{ssp}.parquet"
    if not os.path.exists(p):
        return None
    d = pl.read_parquet(p)
    if where is not None:
        d = d.filter(where)
    d = d.join(climate(gcm, ssp), on=["Cell", "Year"], how="left")
    d = d.with_columns(pl.lit(seed, pl.Int32).alias("seed"), pl.lit(gcm).alias("gcm"), pl.lit(ssp).alias("ssp"))
    if os.path.exists(CARBON_P):
        c = pl.scan_parquet(CARBON_P).filter((pl.col("seed") == seed) & (pl.col("gcm") == gcm)
                                             & (pl.col("ssp") == ssp)).collect()  # fmt: skip
        d = d.join(c, on=["seed", "gcm", "ssp", "Cell", "Year"], how="left")
    if cs is not None:  # ADR 0369: the carbon-state model's cross-fitted predictions
        c = pl.scan_parquet(f"{DATA}/cs_{cs}.parquet").filter((pl.col("seed") == seed) & (pl.col("gcm") == gcm)
                                                              & (pl.col("ssp") == ssp)).collect()  # fmt: skip
        d = d.join(c, on=CS_KEYS, how="left")
    return d


CS_KEYS = ["seed", "gcm", "ssp", "Cell", "Patch", "Type", "ID", "Year"]


CARBON_P = f"{DATA}/carbon.parquet"  # xtf_tree_carbon.py


def split():
    """f2 cell split: train / validation (10 % of training blocks) / held-out."""
    c = M.cells()
    ho = c["heldout"].to_numpy()
    cells = c["Cell"].to_numpy()
    tr_cells = sorted(cells[~ho].tolist())
    val = set(tr_cells[3::10])
    return [x for x in tr_cells if x not in val], sorted(val)


def train_frame(cs=None):
    tr, va = split()
    parts = [load(2, g, s, pl.col("Cell").is_in(tr + va), cs) for g in TRAIN_GCMS for s in TP.SSPS]
    d = pl.concat([p for p in parts if p is not None])
    return d.filter(pl.col("Cell").is_in(tr)), d.filter(pl.col("Cell").is_in(va))


# ------------------------------------------------------------------------------------------------ LightGBM
def feats(arm):
    return TREE_F + cell_cols() + (PATCH_F if arm == "P1" else [])


def train_lgb(a):
    import lightgbm as lgb

    tr, va = train_frame()
    f = feats(a.arm)
    log(f"{a.arm}: train {tr.height:,} trees, val {va.height:,}, {len(f)} inputs")
    ds = lgb.Dataset(tr.select(f).to_numpy(), tr["died"].cast(pl.Int8).to_numpy(), feature_name=f,
                     categorical_feature=["Type"], free_raw_data=True)  # fmt: skip
    dv = lgb.Dataset(va.select(f).to_numpy(), va["died"].cast(pl.Int8).to_numpy(), reference=ds)
    b = lgb.train(LGB, ds, ROUNDS, valid_sets=[dv], callbacks=[lgb.log_evaluation(50)])
    os.makedirs(f"{DATA}/{a.arm}", exist_ok=True)
    b.save_model(f"{DATA}/{a.arm}/model.txt")
    clim = tr.filter(~pl.col("patch_loss")).group_by("Type").agg(pl.col("died").mean().alias("p_clim"))
    clim.write_parquet(f"{DATA}/clim_by_type.parquet")
    log(f"saved {DATA}/{a.arm}/model.txt")


# ------------------------------------------------------------------------------------------------ set transformer
def _norm_stats(d, cols):
    x = transform(d, cols)
    return x.mean(0), x.std(0) + 1e-6


def transform(d, cols):
    x = d.select(cols).to_numpy().astype(np.float64)
    for i, c in enumerate(cols):
        if c in SLOG:
            x[:, i] = np.sign(x[:, i]) * np.log1p(np.abs(x[:, i]))
    return np.nan_to_num(x).astype(np.float32)


def patch_batches(d, tree_cols, cc, nt, nc, solo=False):
    """Sort a frame into patch-year sets: arrays in sorted order + each set's [start, end) and the original row.
    solo (arm ST1, post-hoc control of ADR 0368 section 7): every tree is a set of its own."""
    pk = ["seed", "gcm", "ssp", "Cell", "Patch", "Year"]
    d = d.with_row_index("_r").sort(pk)
    new = d.select(pl.any_horizontal([pl.col(c) != pl.col(c).shift(1) for c in pk]).fill_null(True))
    starts = np.arange(d.height) if solo else np.flatnonzero(new.to_series().to_numpy())
    ends = np.r_[starts[1:], d.height]
    X = (transform(d, tree_cols) - nt[0]) / nt[1]
    C = (transform(d, cc) - nc[0]) / nc[1]
    T = d["Type"].to_numpy().astype(np.int64)
    Y = d["died"].to_numpy().astype(np.float32)
    R = d["_r"].to_numpy()
    return X, C, T, Y, R, starts, ends


def build_set_model(nin, ncell, d=128, nl=4, nh=4, ff=256, nout=1):
    import torch
    from torch import nn

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.tree = nn.Linear(nin, d)
            self.ptype = nn.Embedding(7, d)
            self.cell = nn.Linear(ncell, d)
            self.ctx = nn.Parameter(torch.randn(d) * 0.02)
            layer = nn.TransformerEncoderLayer(d, nh, ff, dropout=0.0, activation="gelu", batch_first=True,
                                               norm_first=True)  # fmt: skip
            self.enc = nn.TransformerEncoder(layer, nl, enable_nested_tensor=False)
            self.ln = nn.LayerNorm(d)
            self.out = nn.Linear(d, nout)

        def forward(self, xt, ty, xc, pad):
            h = self.tree(xt) + self.ptype(ty)
            c = (self.cell(xc) + self.ctx)[:, None]
            h = torch.cat([c, h], 1)
            m = torch.cat([torch.zeros_like(pad[:, :1]), pad], 1)
            h = self.enc(h, src_key_padding_mask=m)
            return self.out(self.ln(h[:, 1:])).squeeze(-1)

    return Net()


def make_batch(X, C, T, Y, starts, ends, sel, dev, max_trees=128):
    import torch

    n = np.minimum(ends[sel] - starts[sel], max_trees)
    L = int(n.max())
    B = len(sel)
    idx = starts[sel][:, None] + np.arange(L)[None, :]
    valid = np.arange(L)[None, :] < n[:, None]
    idx = np.where(valid, idx, starts[sel][:, None])
    t = lambda a: torch.as_tensor(a, device=dev)  # noqa: E731
    return (t(X[idx]), t(T[idx]), t(C[starts[sel]]), t(~valid), t(Y[idx]), idx, valid, B)


def train_st(a):
    import torch

    torch.manual_seed(a.seed)
    rng = np.random.default_rng(a.seed)
    dev = torch.device("cuda")
    tr, va = train_frame(cs_variant(a.arm))
    tc, cc = tree_cols(a.arm), cell_cols(a.arm)
    nt, nc = _norm_stats(tr, tc), _norm_stats(tr, cc)
    solo = a.arm == "ST1"
    miss = tr.select([pl.col(c).null_count() for c in tc + cc]).to_numpy().sum()
    assert miss <= 1e-5 * tr.height, f"{miss} missing input values (carbon table / npp_y not built?)"
    Xt, Ct, Tt, Yt, _, st, en = patch_batches(tr, tc, cc, nt, nc, solo)
    Xv, Cv, Tv, Yv, _, sv, ev = patch_batches(va, tc, cc, nt, nc, solo)
    big = int(((en - st) > 128).sum())
    log(f"{a.arm} s{a.seed}: train {len(st):,} patch-years / {len(Xt):,} trees, val {len(sv):,}; "
        f"patch-years with > 128 trees (only the first 128 scored): {big}")  # fmt: skip
    net = build_set_model(len(tc), len(cc)).to(dev)
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=0.01)
    size = en - st
    order = np.argsort(size, kind="stable")
    nb = math.ceil(len(st) / a.batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, a.lr, total_steps=a.epochs * nb)
    bce = torch.nn.functional.binary_cross_entropy_with_logits
    best, best_state = float("inf"), None
    for ep in range(a.epochs):
        t0 = time.time()
        net.train()
        chunks = [order[i : i + a.batch] for i in range(0, len(order), a.batch)]  # similar sizes per batch
        rng.shuffle(chunks)
        tot = 0.0
        for sel in chunks:
            xt, ty, xc, pad, y, _, _, _ = make_batch(Xt, Ct, Tt, Yt, st, en, sel, dev)
            with torch.autocast("cuda", dtype=torch.bfloat16):
                lo = net(xt, ty, xc, pad)
            loss = bce(lo.float()[~pad], y[~pad])
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
            sched.step()
            tot += loss.item()
        vl = eval_ll(net, Xv, Cv, Tv, Yv, sv, ev, dev)
        log(f"epoch {ep}: train {tot / len(chunks):.5f} val log loss {vl:.5f} {time.time() - t0:.0f}s")
        if vl < best:
            best = vl
            best_state = {k: v.detach().clone() for k, v in net.state_dict().items()}
    net.load_state_dict(best_state)
    os.makedirs(f"{DATA}/{a.arm}_s{a.seed}", exist_ok=True)
    torch.save({"state": net.state_dict(), "nt": nt, "nc": nc, "tc": tc, "cc": cc, "val": best, "solo": solo},
               f"{DATA}/{a.arm}_s{a.seed}/model.pt")  # fmt: skip
    log(f"saved {a.arm}_s{a.seed} (best val log loss {best:.5f})")


def st_predict(net, X, C, T, starts, ends, dev, batch=2048):
    import torch

    p = np.zeros(len(X), np.float32)
    order = np.argsort(ends - starts, kind="stable")
    net.eval()
    with torch.no_grad():
        for i in range(0, len(order), batch):
            sel = order[i : i + batch]
            xt, ty, xc, pad, _, idx, valid, _ = make_batch(X, C, T, np.zeros(len(X), np.float32), starts, ends,
                                                           sel, dev)  # fmt: skip
            q = torch.sigmoid(net(xt, ty, xc, pad).float()).cpu().numpy()
            p[idx[valid]] = q[valid]
            for s, e in zip(starts[sel], ends[sel], strict=True):  # trees beyond 128: the patch's mean
                if e - s > 128:
                    p[s + 128 : e] = p[s : s + 128].mean()
    return p


def eval_ll(net, X, C, T, Y, starts, ends, dev):
    p = np.clip(st_predict(net, X, C, T, starts, ends, dev), 1e-6, 1 - 1e-6)
    return float(-np.mean(Y * np.log(p) + (1 - Y) * np.log(1 - p)))


# ------------------------------------------------------------------------------------------------ carbon state
def cs_cols(v):
    """Inputs of the carbon-state model variant v: the tree at y-1 + its state, the cell inputs + cell carbon."""
    return [c for c in TREE_F if c != "Type"] + STATE_PREV, cell_cols() + carbon_cols(CS_CARBON[v])


def cs_targets(d):
    """(n, 3): log margin at y, bad year (c_y > 0), margin < 1; NaN where not recovered (masked in the loss)."""
    lr = d["lr_y"].to_numpy().astype(np.float32)
    bad = d["bad_y"].to_numpy().astype(np.float32)
    low = np.where(np.isfinite(lr), (lr < 0).astype(np.float32), np.nan).astype(np.float32)
    return np.stack([lr, bad, low], -1)


def cs_forward(net, X, C, T, starts, ends, dev, batch=2048):
    import torch

    out = np.zeros((len(X), 3), np.float32)
    order = np.argsort(ends - starts, kind="stable")
    net.eval()
    with torch.no_grad():
        for i in range(0, len(order), batch):
            sel = order[i : i + batch]
            xt, ty, xc, pad, _, idx, valid, _ = make_batch(X, C, T, np.zeros(len(X), np.float32), starts, ends,
                                                           sel, dev)  # fmt: skip
            o = net(xt, ty, xc, pad).float().cpu().numpy()
            out[idx[valid]] = o[valid]
    return out


def train_cs(a):
    import torch

    torch.manual_seed(a.seed + 10 * a.fold)
    rng = np.random.default_rng(a.seed + 10 * a.fold)
    dev = torch.device("cuda")
    tr_cells, _ = split()
    fold = tr_cells[a.fold :: 2]
    tr, va = train_frame()
    tr = tr.filter(pl.col("Cell").is_in(fold))
    tc, cc = cs_cols(a.variant)
    nt, nc = _norm_stats(tr, tc), _norm_stats(tr, cc)
    Xt, Ct, Tt, _, Rt, st, en = patch_batches(tr, tc, cc, nt, nc)
    Xv, Cv, Tv, _, Rv, sv, ev = patch_batches(va, tc, cc, nt, nc)
    Yt, Yv = cs_targets(tr)[Rt], cs_targets(va)[Rv]
    ymu, ysd = float(np.nanmean(Yt[:, 0])), float(np.nanstd(Yt[:, 0]))
    Yt[:, 0], Yv[:, 0] = (Yt[:, 0] - ymu) / ysd, (Yv[:, 0] - ymu) / ysd
    log(f"CS {a.variant} fold {a.fold}: train {len(st):,} patch-years / {len(Xt):,} trees ({len(fold)} cells), "
        f"val {len(sv):,}; recovered targets {np.isfinite(Yt).mean(0).round(5).tolist()}; "
        f"base rates bad {np.nanmean(Yt[:, 1]):.4f} low {np.nanmean(Yt[:, 2]):.4f}")  # fmt: skip
    net = build_set_model(len(tc), len(cc), nout=3).to(dev)
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=0.01)
    order = np.argsort(en - st, kind="stable")
    nb = math.ceil(len(st) / a.batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, a.lr, total_steps=a.epochs * nb)
    bce = torch.nn.functional.binary_cross_entropy_with_logits

    def loss_fn(o, y, keep):
        m = keep[..., None] & torch.isfinite(y)
        yz = torch.nan_to_num(y)
        l0 = ((o[..., 0] - yz[..., 0]) ** 2)[m[..., 0]].mean()
        l1 = bce(o[..., 1][m[..., 1]], yz[..., 1][m[..., 1]])
        l2 = bce(o[..., 2][m[..., 2]], yz[..., 2][m[..., 2]])
        return l0 + l1 + l2, (l0.item(), l1.item(), l2.item())

    best, best_state = float("inf"), None
    for ep in range(a.epochs):
        t0 = time.time()
        net.train()
        chunks = [order[i : i + a.batch] for i in range(0, len(order), a.batch)]
        rng.shuffle(chunks)
        tot = 0.0
        for sel in chunks:
            xt, ty, xc, pad, y, _, _, _ = make_batch(Xt, Ct, Tt, Yt, st, en, sel, dev)
            with torch.autocast("cuda", dtype=torch.bfloat16):
                o = net(xt, ty, xc, pad)
            loss, _ = loss_fn(o.float(), y, ~pad)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
            sched.step()
            tot += loss.item()
        o = torch.as_tensor(cs_forward(net, Xv, Cv, Tv, sv, ev, dev))
        vl, parts = loss_fn(o, torch.as_tensor(Yv), torch.ones(len(Yv), dtype=torch.bool))
        log(f"epoch {ep}: train {tot / len(chunks):.5f} val {vl.item():.5f} (margin mse {parts[0]:.4f}, bad-year "
            f"log loss {parts[1]:.4f}, margin<1 log loss {parts[2]:.4f}) {time.time() - t0:.0f}s")  # fmt: skip
        if vl.item() < best:
            best = vl.item()
            best_state = {k: v.detach().clone() for k, v in net.state_dict().items()}
    net.load_state_dict(best_state)
    out = f"{DATA}/CS_{a.variant}_f{a.fold}"
    os.makedirs(out, exist_ok=True)
    torch.save({"state": net.state_dict(), "nt": nt, "nc": nc, "tc": tc, "cc": cc, "ymu": ymu, "ysd": ysd,
                "val": best, "fold_cells": fold}, f"{out}/model.pt")  # fmt: skip
    log(f"saved {out} (best val {best:.5f})")


def stage_cspredict(a):
    """Cross-fitted predictions for every row any death arm reads -> DATA/cs_<variant>.parquet."""
    import torch

    dev = torch.device("cuda")
    tr_cells, va_cells = split()
    nets, cks = [], []
    for f in (0, 1):
        ck = torch.load(f"{DATA}/CS_{a.variant}_f{f}/model.pt", map_location=dev, weights_only=False)
        net = build_set_model(len(ck["tc"]), len(ck["cc"]), nout=3).to(dev)
        net.load_state_dict(ck["state"])
        nets.append(net)
        cks.append(ck)
    fold_of = {c: f for f in (0, 1) for c in cks[f]["fold_cells"]}
    out, ev = [], []
    for s in (2, 3):
        for g in M.GCMS:
            for t in TP.SSPS:
                d = load(s, g, t)
                if d is None:
                    continue
                d = d.filter(pl.col("heldout") | (pl.col("Cell").is_in(tr_cells + va_cells)
                                                  & pl.lit(s == 2 and g in TRAIN_GCMS)))  # fmt: skip
                o = []
                for net, ck in zip(nets, cks, strict=True):
                    X, C, T, _, R, st, en = patch_batches(d, ck["tc"], ck["cc"], ck["nt"], ck["nc"])
                    q = np.empty((d.height, 3), np.float32)
                    q[R] = cs_forward(net, X, C, T, st, en, dev)
                    o.append(q)
                f = np.array([fold_of.get(c, -1) for c in d["Cell"].to_list()])
                q = np.where((f == 0)[:, None], o[1], np.where((f == 1)[:, None], o[0], (o[0] + o[1]) / 2))
                sig = lambda z: 1 / (1 + np.exp(-z))  # noqa: E731
                lr = cks[0]["ymu"] + cks[0]["ysd"] * q[:, 0]  # both folds share the target scaling closely
                res = d.select(CS_KEYS + ["heldout", "lr_y", "bad_y"]).with_columns(
                    pl.Series("cs_lr", lr.astype(np.float32)), pl.Series("cs_bad", sig(q[:, 1]).astype(np.float32)),
                    pl.Series("cs_low", sig(q[:, 2]).astype(np.float32)))  # fmt: skip
                ev.append(res.filter(pl.col("heldout") & pl.lit(g in M.TEST_GCMS)))
                out.append(res.drop("heldout", "lr_y", "bad_y"))
                log(f"CS {a.variant}: {s} {g} {t}")
    pl.concat(out).write_parquet(f"{DATA}/cs_{a.variant}.parquet")
    e = pl.concat(ev).drop_nulls(["lr_y", "bad_y"])
    y, p = e["bad_y"].to_numpy(), np.clip(e["cs_bad"].to_numpy(), 1e-6, 1 - 1e-6)
    base = np.full_like(p, y.mean())
    print(f"CS {a.variant}, held-out cells x held-out models: r(log margin) = "
          f"{np.corrcoef(e['lr_y'].to_numpy(), e['cs_lr'].to_numpy())[0, 1]:.3f}; bad-year log loss {ll(y, p):.4f} "
          f"vs base rate {ll(y, base):.4f} (rate {y.mean():.4f})", flush=True)  # fmt: skip


# ------------------------------------------------------------------------------------------------ predict
def pred_frames(cs=None):
    """Held-out cells of every leg (both seeds) + the training cells of the training legs (in-sample)."""
    tr, _ = split()
    for s in (2, 3):
        for g in M.GCMS:
            for t in TP.SSPS:
                d = load(s, g, t, cs=cs)
                if d is None:
                    continue
                keep = pl.col("heldout") | (pl.col("Cell").is_in(tr) & pl.lit(s == 2 and g in TRAIN_GCMS))
                yield d.filter(keep)


def stage_predict(a):
    name = a.arm if a.arm in ("P0", "P1", "ORACLE") else f"{a.arm}_s{a.seed}"
    os.makedirs(f"{DATA}/{name}", exist_ok=True)
    out = []
    if a.arm == "ORACLE":  # the original's own probability as a "prediction": the ceiling of every score
        for d in pred_frames():
            out.append(d.select(KEYS_OUT).with_columns(pl.col("oracle").fill_null(1.0).alias("p")))
    elif a.arm in ("P0", "P1"):
        import lightgbm as lgb

        b = lgb.Booster(model_file=f"{DATA}/{a.arm}/model.txt")
        for d in pred_frames():
            p = b.predict(d.select(feats(a.arm)).to_numpy(), num_threads=32)
            out.append(d.select(KEYS_OUT).with_columns(pl.Series("p", p.astype(np.float32))))
            log(f"{name}: {d['seed'][0]} {d['gcm'][0]} {d['ssp'][0]}")
    else:
        import torch

        dev = torch.device("cuda")
        ck = torch.load(f"{DATA}/{name}/model.pt", map_location=dev, weights_only=False)
        net = build_set_model(len(ck["tc"]), len(ck["cc"])).to(dev)
        net.load_state_dict(ck["state"])
        for d in pred_frames(cs_variant(a.arm)):
            X, C, T, _, R, st, en = patch_batches(d, ck["tc"], ck["cc"], ck["nt"], ck["nc"], ck.get("solo", False))
            p = np.empty(d.height, np.float32)
            p[R] = st_predict(net, X, C, T, st, en, dev)
            out.append(d.select(KEYS_OUT).with_columns(pl.Series("p", p)))
            log(f"{name}: {d['seed'][0]} {d['gcm'][0]} {d['ssp'][0]}")
    pl.concat(out).write_parquet(f"{DATA}/{name}/pred.parquet")


KEYS_OUT = ["seed", "gcm", "ssp", "Cell", "Patch", "Year", "Type", "heldout", "died", "patch_loss", "oracle"]


# ------------------------------------------------------------------------------------------------ score
def ll(y, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def dieoff_capture(rt, rp):
    """rt, rp: (ncell, nyear) true / predicted death rate of one member; events on the truth (ADR 0368 §2)."""
    med = np.nanmedian(rt, 1, keepdims=True)
    mad = np.nanmedian(np.abs(rt - med), 1, keepdims=True)
    ev = (rt > med + 3 * mad) & (rt >= 0.05)
    ev[:, :5] = False
    num = den = 0.0
    for i, j in zip(*np.nonzero(ev), strict=True):
        num += rp[i, j] - np.nanmean(rp[i, j - 5 : j])
        den += rt[i, j] - np.nanmean(rt[i, j - 5 : j])
    return num / den if den > 0 else np.nan, int(ev.sum())


def stage_score(_a):
    clim = pl.read_parquet(f"{DATA}/clim_by_type.parquet")
    runs = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(f"{DATA}/*/pred.parquet"))
    tr, _ = split()
    rows = []
    for r in runs:
        d = pl.read_parquet(f"{DATA}/{r}/pred.parquet").join(clim, on="Type", how="left")
        d = d.with_columns(pl.when(pl.col("gcm").is_in(M.TEST_GCMS)).then(pl.lit("heldout-GCM"))
                           .otherwise(pl.lit("train-GCM")).alias("gg"))  # fmt: skip
        for grp, f in (("heldout x heldout-GCM", pl.col("heldout") & (pl.col("gg") == "heldout-GCM")),
                       ("heldout x train-GCM", pl.col("heldout") & (pl.col("gg") == "train-GCM")),
                       ("train cells (in-sample)", ~pl.col("heldout"))):  # fmt: skip
            x = d.filter(f)
            if x.is_empty():
                continue
            n = x.filter(~pl.col("patch_loss") & pl.col("oracle").is_not_null())
            y, p = n["died"].cast(pl.Float64).to_numpy(), n["p"].to_numpy().astype(np.float64)
            l_arm, l_clim, l_or = ll(y, p), ll(y, n["p_clim"].to_numpy()), ll(y, n["oracle"].to_numpy())
            pl_ = x.filter(pl.col("patch_loss"))
            row = dict(run=r, group=grp, trees=n.height, ll=l_arm, ll_clim=l_clim, ll_oracle=l_or,
                       skill=(l_clim - l_arm) / (l_clim - l_or), brier=float(np.mean((p - y) ** 2)),
                       calib=float(p.sum() / max(y.sum(), 1)),
                       ll_patch_loss=(ll(np.ones(pl_.height), pl_["p"].to_numpy())
                                      if pl_.height else np.nan))  # fmt: skip
            if grp != "train cells (in-sample)":
                row.update(cell_scores(x))
            rows.append(row)
        log(f"scored {r}")
    df = pl.DataFrame(rows)
    df.write_csv(f"{DATA}/score.csv")
    with pl.Config(tbl_rows=100, tbl_cols=20, tbl_width_chars=260, float_precision=4):
        print(df)
    decide(df)


def cell_scores(x):
    """Cell-year death rates (all trees of held-out cells are kept): 30-yr rate vs the second run; die-off capture."""
    cy = x.group_by(["seed", "gcm", "ssp", "Cell", "Year"]).agg(
        pl.col("died").mean().alias("rt"), pl.col("p").mean().alias("rp"), pl.len().alias("n"))
    dense = (cy.filter(pl.col("Year") == 2021).group_by(["seed", "gcm", "ssp", "Cell"])
             .agg((pl.col("n").first() / 25 >= 5).alias("dense")))  # fmt: skip
    cy = cy.join(dense, on=["seed", "gcm", "ssp", "Cell"], how="left")
    eE, eR, caps, nev = [], [], [], 0
    for _, sub in cy.group_by(["gcm", "ssp"]):
        late = sub.filter(pl.col("Year").is_between(2071, 2100) & pl.col("dense").fill_null(False))
        w = late.group_by(["seed", "Cell"]).agg(pl.col("rt").mean(), pl.col("rp").mean())
        p2, p3 = w.filter(pl.col("seed") == 2), w.filter(pl.col("seed") == 3)
        both = p2.join(p3, on="Cell", suffix="_3")
        for k, j in (("", "_3"), ("_3", "")):
            t = both[f"rt{k}"].to_numpy()
            eE.append(np.abs(both[f"rp{k}"].to_numpy() / t - 1))
            eR.append(np.abs(both[f"rt{j}"].to_numpy() / t - 1))
        for sd in (2, 3):
            m = sub.filter(pl.col("seed") == sd)
            if m.is_empty():
                continue
            yrs = [str(y) for y in range(2021, 2101)]
            piv = {v: m.pivot(on="Year", index="Cell", values=v).sort("Cell") for v in ("rt", "rp")}
            arr = {v: piv[v].select([pl.col(y) if y in piv[v].columns else pl.lit(None).alias(y) for y in yrs])
                   .to_numpy().astype(np.float64) for v in piv}  # fmt: skip
            c, e = dieoff_capture(arr["rt"], arr["rp"])
            caps.append((c, e))
            nev += e
    eE, eR = np.concatenate(eE), np.concatenate(eR)
    cw = [c * e for c, e in caps if np.isfinite(c)]
    return dict(rate30_ratio=float(np.nanmedian(eE) / np.nanmedian(eR)),
                dieoff_capture=float(np.sum(cw) / max(sum(e for c, e in caps if np.isfinite(c)), 1)),
                n_events=nev)  # fmt: skip


def decide(df):
    g = df.filter(pl.col("group") == "heldout x heldout-GCM")
    if g.is_empty():
        return
    v = lambda r, c: g.filter(pl.col("run") == r)[c].to_list()  # noqa: E731
    st = [r for r in g["run"].to_list() if r.startswith("ST_s")]
    try:
        p0, p1 = v("P0", "skill")[0], v("P1", "skill")[0]
    except IndexError:
        return
    print(f"neighbours matter (P1 - P0 skill >= 0.05): {p1 - p0:+.4f} -> {'YES' if p1 - p0 >= 0.05 else 'no'}")
    if st:
        sk = [v(r, "skill")[0] for r in st]
        cap = [v(r, "dieoff_capture")[0] for r in st]
        r30 = [v(r, "rate30_ratio")[0] for r in st]
        ok = (np.mean(sk) - p1 >= 0.05 and np.mean(sk) - p1 > max(sk) - min(sk)
              and np.mean(cap) - v("P1", "dieoff_capture")[0] >= 0.05
              and np.mean(r30) <= 1.10 * v("P1", "rate30_ratio")[0])  # fmt: skip
        print(f"ST seed-mean skill {np.mean(sk):.4f} (spread {max(sk) - min(sk):.4f}) vs P1 {p1:.4f}; die-off "
              f"capture {np.mean(cap):.3f} vs {v('P1', 'dieoff_capture')[0]:.3f}; 30-yr rate {np.mean(r30):.3f} vs "
              f"{v('P1', 'rate30_ratio')[0]:.3f} -> {'WORTH PURSUING' if ok else 'stop'}")  # fmt: skip


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["train", "predict", "score", "cstrain", "cspredict"])
    ap.add_argument("--arm", default="P0")
    ap.add_argument("--variant", default="e")
    ap.add_argument("--fold", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch", type=int, default=512)
    ap.add_argument("--lr", type=float, default=1e-3)
    a = ap.parse_args()
    if a.stage == "train":
        (train_lgb if a.arm in ("P0", "P1") else train_st)(a)  # ST1 = ST with one tree per set
    elif a.stage == "cstrain":
        train_cs(a)
    elif a.stage == "cspredict":
        stage_cspredict(a)
    else:
        {"predict": stage_predict, "score": stage_score}[a.stage](a)
    log("=== DONE")


if __name__ == "__main__":
    main()
