#!/usr/bin/env python3
"""explore_de_nset_train.py — LINE X, Germany data-driven emulator, track D-NSET item D2: STAGE-1
TRAINING, held-out
scoring and the PRE-REGISTERED STAGE-2 GATE (pre-registration: /p/tmp/jamirp/X_de/_status/D.md).

  train   --arm D-main|N-free|N-set [--minutes 70]   teacher-forced one-step NLL of every head on
  the DEV-A training
          members (MPI s1 Historical + ssp126 + ssp370), dev folds 1-4; windows of L years with the
          patch LSTM run
          teacher-forced from h0 = MLP(start-roster histograms); early stopping on 5 % of training
          PATCHES
          -> /p/tmp/jamirp/X_de/nset/<arm>/model.pt
  score   --arm A   held-out PLACES (fold 5): pool A = MPI s1 Historical+ssp126+ssp370, pool B =
  ACCESS s1
          Historical+ssp370 (held-out climate model). Per-head NLL with the true and the frozen
          climate; death Brier
          vs the baseline "rule hazard + SH13 fire alone"; G-sign calibration by previous-G decile
          -> nset/<arm>/score.json
  gate    --arm A   the free-run part of the gate: reads the engine run of NsetStepper
  (explore_de_nset_stepper.py)
          and the truth; writes nset/<arm>/gate.json, appends _status/D.md, writes
          _reports/r2_D2.json
  submit  --arm A [--minutes] GPU job (partition gpu, qos gpushort): train -> score -> free run ->
  gate
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np
import polars as pl
import torch

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_nset_model as nm  # noqa: E402
import explore_de_sh_rules as rl  # noqa: E402
import explore_de_sh_tensors as st  # noqa: E402

XDE = nm.XDE
NSET = os.environ.get("NSET_ROOT", os.path.join(XDE, "nset"))
STATUS = os.path.join(XDE, "_status", "D.md")
REPORT = os.path.join(XDE, "_reports", "r2_D2.json")
PY = "/home/jamirp/.conda/envs/py311_new/bin/python"
TRAIN = os.environ.get(
    "NSET_TRAIN",
    "MPI-ESM1-2-HR_Historical_s1_h1985,MPI-ESM1-2-HR_ssp126_s1_w2015,MPI-ESM1-2-HR_ssp370_s1_w2015",
).split(",")
POOL_A = TRAIN
POOL_B = os.environ.get(
    "NSET_POOLB", "ACCESS-CM2_Historical_s1_h1985,ACCESS-CM2_ssp370_s1_w2015"
).split(",")
L_WIN = 8
HOLD_FOLD = 5


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def status(line: str):
    if "_smoke" in NSET:
        return
    with open(STATUS, "a") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} {line}\n")


def folds_of(cells: np.ndarray) -> np.ndarray:
    f = pl.read_parquet(os.path.join(XDE, "shared", "registry", "folds.parquet")).filter(
        pl.col("is_dev")
    )
    m = dict(zip(f["Cell"].to_list(), f["fold"].to_list(), strict=True))
    return np.array([m[int(c)] for c in cells])


# ================================================================================================
# member arrays
class Member:
    """Per-row model arrays of one SH11 member (RAM), plus patch/cell arrays."""

    def __init__(self, name: str, nset_lags: bool = False):
        t0 = time.time()
        D = st.load(name)
        m = D["meta"]
        self.name, self.meta = name, m
        self.cells = np.asarray(m["cells"])
        self.npatch = m["npatch"]
        self.T = len(m["years"])
        self.idx = np.asarray(D["idx"])
        tc = {c: j for j, c in enumerate(m["tok_cols"])}
        tok = np.load(
            os.path.join(st.member_dir(name), "tok.npy")
        )  # one sequential read (not 25 strided)

        def col(c):
            return np.asarray(tok[:, tc[c]]).astype(np.float64)

        typ = np.asarray(D["keys"][:, 3])
        R = {c: col(c) for c in nm.TOK_RAW if c != "Type"}
        R["Type"] = typ
        self.TF, _ = nm.token_raw_to_feat(R)
        self.typ = typ.astype(np.int64)
        self.cy = np.nan_to_num(R["c_y"]).astype(np.int64)
        self.fate = np.nan_to_num(col("fate_y1"), nan=2).astype(np.int64)
        G1 = col("G_y1")
        cen = np.nan_to_num(col("cenG_y1"), nan=3).astype(np.int64)
        pres = self.fate < 2
        self.G1 = np.nan_to_num(G1).astype(np.float32)
        self.gsign_ok = (pres & np.isfinite(G1) & np.isin(cen, [0, 1, 2, 5])).astype(np.float32)
        self.gmag_ok = (pres & np.isfinite(G1) & (cen == 0) & (np.abs(G1) > 1e-6)).astype(
            np.float32
        )
        self.c1 = np.nan_to_num(col("c_y1")).astype(np.int64)
        hz = col("mort_y1")
        self.hz = np.nan_to_num(hz).astype(np.float32)
        self.hard = np.nan_to_num(col("hard_y1")) > 0
        self.pres = pres
        T = {
            c: col(c)
            for c in [
                "Height",
                "agb",
                "vegc",
                "fpc_ind",
                "D95",
                "Height_y1",
                "agb_y1",
                "vegc_y1",
                "LAI_y1",
                "fpc_ind_y1",
                "D95_y1",
                "npp_y1",
                "transp_y1",
                "wscal_mean_y1",
                "W_y1",
            ]
        }
        Y = nm.grow_targets(T)
        cenW = np.nan_to_num(col("cenW_y1"), nan=4)
        ym = np.isfinite(Y) & pres[:, None]
        ym[:, -1] &= cenW != 4
        self.Y, self.ym = np.nan_to_num(Y).astype(np.float32), ym.astype(np.float32)
        self.Gy = R["G_y"].astype(np.float32)
        E = nm.entry_targets(R)
        self.E, self.em = np.nan_to_num(E).astype(np.float32), np.isfinite(E).astype(np.float32)
        self.isnew = col("is_new_y") > 0
        self.X4 = nm.trait4(R)
        self.H = R["Height"].astype(np.float32)
        self.lage = np.log(np.maximum(R["Age"], 1.0)).astype(np.float32)
        P = D["patch"]
        pc = {c: j for j, c in enumerate(m["patch_cols"])}
        g = lambda c: np.asarray(P[:, :, pc[c]]).astype(np.float64)  # noqa: E731
        self.grass_lai = g("grass8_LAI_y").astype(np.float32)
        self.GF = nm.grass_feat(g("grass8_fpc_y"), g("grass8_LAI_y"), g("grass8_agb_y"))
        lags = np.stack([g(f"frac_loss_lag{k}") for k in range(20)], -1) if nset_lags else None
        self.PS = nm.patch_scal(g("n_live_y"), g("sum_fpc_y"), g("sum_agb_y"), lags)
        self.clim = np.asarray(D["clim"]).astype(np.float32)
        self.clim_frozen = np.asarray(D["clim_frozen"]).astype(np.float32)
        self.stat = np.asarray(D["static"]).astype(np.float32)
        self.fold = folds_of(self.cells)
        self.years = np.asarray(m["years"])
        log(f"loaded {name}: {len(self.typ)} rows, {self.idx.shape} idx, {time.time() - t0:.0f} s")

    def patches_of_folds(self, folds) -> np.ndarray:
        cf = np.isin(self.fold, folds)
        return np.flatnonzero(np.repeat(cf, self.npatch))

    def batch(self, p: np.ndarray, t0: int, L: int, frozen: bool = False) -> dict:
        """Years t0 .. t0+L-1 (+ t0+L for next-year targets when available) of patches p."""
        T = self.T
        tt = np.arange(t0, min(t0 + L + 1, T))
        ix = self.idx[p][:, tt, :]  # [B, L', S]
        mask = ix >= 0
        r = np.where(mask, ix, 0)
        ci = p // self.npatch
        cw = np.stack([self.clim[ci, t0 + k : t0 + k + 22] for k in range(min(L, T - t0))], 1)
        if frozen:
            cw = np.broadcast_to(self.clim_frozen[ci][:, None, None, :], cw.shape).copy()
        out = {
            "mask": mask,
            "typ": self.typ[r],
            "cy": self.cy[r],
            "TF": self.TF[r],
            "G1": self.G1[r],
            "gsign_ok": self.gsign_ok[r] * mask,
            "gmag_ok": self.gmag_ok[r] * mask,
            "c1": self.c1[r],
            "hz": self.hz[r],
            "hard": self.hard[r],
            "fate": np.where(mask, self.fate[r], 3),
            "pres": self.pres[r] & mask,
            "Y": self.Y[r],
            "ym": self.ym[r] * mask[..., None],
            "E": self.E[r],
            "em": self.em[r] * mask[..., None],
            "isnew": self.isnew[r] & mask,
            "X4": self.X4[r],
            "H": self.H[r],
            "lage": self.lage[r],
            "Gy": self.Gy[r],
            "GF": self.GF[p][:, tt],
            "PS": self.PS[p][:, tt],
            "lai": self.grass_lai[p][:, tt],
            "clim": cw,
            "stat": self.stat[ci],
            "nsteps": min(L, T - t0),
            "has_next": np.array([t0 + k + 1 < T for k in range(min(L, T - t0))]),
        }
        return out


def to_dev(b: dict, dev) -> dict:
    out = {}
    for k, v in b.items():
        if isinstance(v, np.ndarray):
            t = torch.from_numpy(np.ascontiguousarray(v))
            out[k] = t.to(dev, non_blocking=True)
        else:
            out[k] = v
    return out


# ================================================================================================
# the window loss
def window(model: nm.NSet, b: dict, collect: bool = False):
    """Teacher-forced pass over a window -> {head: (sum nll, count)} [+ per-tree outputs]."""
    N = model.norm
    dev = b["mask"].device
    nst = b["nsteps"]
    B = b["mask"].shape[0]
    clim = (b["clim"] - N.clim_m) / N.clim_s
    clim = torch.nan_to_num(clim)
    stat = b["stat"].clone()
    stat[:, 1:] = torch.nan_to_num((stat[:, 1:] - N.stat_m[1:]) / N.stat_s[1:])
    z_all = model.clim(clim.reshape(B * nst, 22, -1), stat.repeat_interleave(nst, 0)).view(
        B, nst, -1
    )
    dz_all = clim[:, :, -1, model.dz_idx]
    dry_all = clim[:, :, -1, model.dry_idx]
    acc = {
        k: [torch.zeros((), device=dev), 0.0]
        for k in (
            "g_sign",
            "g_mag",
            "grow",
            "death",
            "absent",
            "rcount",
            "rtype",
            "rtrait",
            "e_height",
            "e_age",
            "e_c",
            "e_rest",
            "grass",
        )
    }
    coll = []
    hc = model.initial_state(b["TF"][:, 0], b["typ"][:, 0], b["mask"][:, 0])
    for k in range(nst):
        mask = b["mask"][:, k]
        typ = b["typ"][:, k]
        TFk = b["TF"][:, k]
        tokf = N.tok(TFk, typ)
        gf = (b["GF"][:, k] - N.grass_m) / N.grass_s
        ps = (b["PS"][:, k] - N.pscal_m) / N.pscal_s
        z = z_all[:, k]
        h = hc[0] if hc is not None else None
        e, p = model.encode(tokf, typ, b["cy"][:, k], mask, gf, ps, z, h)
        u = model.tree_ctx(e, p, h, z)
        G1 = b["G1"][:, k]
        c1 = b["c1"][:, k]
        ns, nmg, glogit = model.g_nll(u, G1, b["gsign_ok"][:, k], b["gmag_ok"][:, k])
        acc["g_sign"][0] += ns.sum()
        acc["g_sign"][1] += float(b["gsign_ok"][:, k].sum())
        acc["g_mag"][0] += nmg.sum()
        acc["g_mag"][1] += float(b["gmag_ok"][:, k].sum())
        Yn = (b["Y"][:, k] - N.grow_m) / N.grow_s
        gn, gc = model.grow_nll(u, G1, c1, dz_all[:, k], Yn, b["ym"][:, k])
        acc["grow"][0] += gn.sum()
        acc["grow"][1] += float(gc.sum())
        pc = model.patch_ctx(p, h, z, gf, ps, dry_all[:, k])
        f = model.fire_f(pc)
        pdem, hard = model.p_dem(u, G1, c1, b["hz"][:, k])
        if model.offset:  # N-free (purely learned death) does not get the rule's hard kills
            hard = hard | b["hard"][:, k]
        pdie = model.p_die(pdem, hard, model.s_of(typ), f[:, None])
        pres = b["pres"][:, k]
        dead = (b["fate"][:, k] == 1).float()
        pdc = pdie.clamp(1e-7, 1 - 1e-7)
        bce = -(dead * torch.log(pdc) + (1 - dead) * torch.log1p(-pdc))
        acc["death"][0] += (bce * pres).sum()
        acc["death"][1] += float(pres.sum())
        alog = model.absent(u)[..., 0]
        ab = (b["fate"][:, k] == 2).float()
        acc["absent"][0] += (
            torch.nn.functional.binary_cross_entropy_with_logits(alog, ab, reduction="none") * mask
        ).sum()
        acc["absent"][1] += float(mask.sum())
        if collect:
            coll.append(
                {
                    "k": k,
                    "mask": mask,
                    "pdie": pdie,
                    "pdem": pdem,
                    "hard": hard,
                    "hard_rule": (c1 >= nm.NC) | (b["hz"][:, k] >= 1.0) | b["hard"][:, k],
                    "f": f,
                    "fate": b["fate"][:, k],
                    "pres": pres,
                    "typ": typ,
                    "hz": b["hz"][:, k],
                    "gp": torch.sigmoid(glogit),
                    "Gy": b["Gy"][:, k],
                    "G1": G1,
                    "gok": b["gsign_ok"][:, k],
                }
            )
        if bool(b["has_next"][k]):
            mn = b["mask"][:, k + 1] & b["isnew"][:, k + 1]
            n_new = mn.sum(-1).float()
            mu, al = model.rcount_params(pc)
            acc["rcount"][0] += model.nb_nll(n_new, mu, al).sum()
            acc["rcount"][1] += float(B)
            if mn.any():
                bi, si = torch.nonzero(mn, as_tuple=True)
                rtyp = b["typ"][:, k + 1][bi, si].clamp(0, nm.NTYPE - 1)
                lt = model.r_type(pc[bi])
                acc["rtype"][0] += torch.nn.functional.cross_entropy(lt, rtyp, reduction="sum")
                acc["rtype"][1] += float(len(bi))
                cond = model.rec_cond(pc[bi], rtyp)
                tm, ts = N.trait_m[rtyp][:, :4], N.trait_s[rtyp][:, :4]
                x4 = (b["X4"][:, k + 1][bi, si] - tm) / ts
                x4s = (b["X4"][:, k][bi] - tm[:, None]) / ts[:, None]
                tn = model.trait_nll(cond, rtyp, x4, e[bi], typ[bi], mask[bi], x4s)
                acc["rtrait"][0] += tn.sum()
                acc["rtrait"][1] += float(len(bi))
                En = (b["E"][:, k + 1][bi, si] - N.entry_m) / N.entry_s
                nh, na, ncc, nr = model.entry_nll(
                    cond,
                    x4,
                    b["H"][:, k + 1][bi, si],
                    b["lage"][:, k + 1][bi, si],
                    b["cy"][:, k + 1][bi, si],
                    En,
                    b["em"][:, k + 1][bi, si],
                )
                for nmn, v in (("e_height", nh), ("e_age", na), ("e_c", ncc), ("e_rest", nr)):
                    acc[nmn][0] += v.sum()
                    acc[nmn][1] += float(len(bi))
            lai1 = b["lai"][:, k + 1]
            ok = torch.isfinite(lai1)
            acc["grass"][0] += (model.grass_nll(pc, torch.nan_to_num(lai1)) * ok).sum()
            acc["grass"][1] += float(ok.sum())
        hc = model.advance(p, ps, z, hc) if hc is not None else None
    return acc, coll


def total_loss(acc) -> torch.Tensor:
    return sum(v[0] / max(v[1], 1.0) for v in acc.values())


# ================================================================================================
# normaliser fit
def fit_norm(model: nm.NSet, mems: list[Member]):
    rng = np.random.default_rng(0)
    sel = [rng.choice(len(m.typ), min(len(m.typ), 2_000_000), replace=False) for m in mems]
    cat = lambda f: np.concatenate([f(m, s) for m, s in zip(mems, sel, strict=True)])  # noqa: E731
    tok = cat(lambda m, s: m.TF[s])
    typ = cat(lambda m, s: m.typ[s])
    Y = cat(lambda m, s: np.where(m.ym[s] > 0, m.Y[s], np.nan))
    E = cat(lambda m, s: np.where((m.em[s] > 0) & m.isnew[s][:, None], m.E[s], np.nan))
    lG = cat(
        lambda m, s: np.where(m.gmag_ok[s] > 0, np.log(np.maximum(np.abs(m.G1[s]), 1e-6)), np.nan)
    )
    clim = np.concatenate([m.clim.reshape(-1, m.clim.shape[-1]) for m in mems])
    stat = np.concatenate([m.stat for m in mems])
    grass = np.concatenate([m.GF.reshape(-1, 3) for m in mems])
    ps = np.concatenate([m.PS.reshape(-1, m.PS.shape[-1]) for m in mems])
    nm.fit_norm(model.norm, tok, typ, clim, stat, Y, E, grass, ps, lG)


# ================================================================================================
# train
def arm_cfg(arm: str) -> dict:
    return {
        "D-main": dict(lstm=True, offset=True),
        "N-free": dict(lstm=True, offset=False),
        "N-set": dict(lstm=False, offset=True),
    }[arm]


def build_model(arm: str, mem0: Member) -> nm.NSet:
    P = rl.load_params()
    cfg = arm_cfg(arm)
    return nm.NSet(
        n_clim=mem0.clim.shape[-1],
        n_stat=mem0.stat.shape[-1],
        n_pscal=mem0.PS.shape[-1],
        resist=P["resist"],
        clim_cols=mem0.meta["clim_cols"],
        **cfg,
    )


def stage_train(a):
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    od = os.path.join(NSET, a.arm)
    os.makedirs(od, exist_ok=True)
    nset_lags = a.arm == "N-set"
    mems = [Member(m, nset_lags) for m in TRAIN]
    rng = np.random.default_rng(1)
    tr_p, va_p = [], []
    for m in mems:
        pp = m.patches_of_folds([1, 2, 3, 4])
        # validation = 5 % of training PATCHES of whole training cells (not evidence)
        cells = np.unique(pp // m.npatch)
        vc = rng.choice(cells, max(1, len(cells) // 20), replace=False)
        isv = np.isin(pp // m.npatch, vc)
        tr_p.append(pp[~isv])
        va_p.append(pp[isv])
    model = build_model(a.arm, mems[0])
    fit_norm(model, mems)
    model = model.to(dev)
    opt = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad], lr=a.lr, weight_decay=1e-4
    )
    B = a.batch
    t_end = time.time() + a.minutes * 60
    step, best, hist = 0, np.inf, []
    vrng = np.random.default_rng(7)
    vb = [
        (mi, vrng.choice(va_p[mi], B), int(vrng.integers(0, mems[mi].T - L_WIN + 1)))
        for mi in range(len(mems))
        for _ in range(6)
    ]
    t_load = t_gpu = 0.0
    while time.time() < t_end:
        model.train()
        mi = int(rng.integers(0, len(mems)))
        m = mems[mi]
        t1 = time.time()
        p = rng.choice(tr_p[mi], B)
        t0 = int(rng.integers(0, m.T - L_WIN + 1))
        b = to_dev(m.batch(p, t0, L_WIN), dev)
        t2 = time.time()
        acc, _ = window(model, b)
        loss = total_loss(acc)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        t_load += t2 - t1
        t_gpu += time.time() - t2
        step += 1
        if step % 200 == 0 or time.time() >= t_end:
            model.eval()
            with torch.no_grad():
                tot = {}
                for mi2, pv, tv in vb:
                    accv, _ = window(model, to_dev(mems[mi2].batch(pv, tv, L_WIN), dev))
                    for k2, v in accv.items():
                        tot.setdefault(k2, [0.0, 0.0])
                        tot[k2][0] += float(v[0])
                        tot[k2][1] += v[1]
                vh = {k2: v[0] / max(v[1], 1) for k2, v in tot.items()}
                vl = sum(vh.values())
            hist.append({"step": step, "train_loss": float(loss), "val_loss": vl, "val_heads": vh})
            log(
                f"step {step} train {float(loss):.4f} val {vl:.4f} "
                f"(load {t_load:.0f}s gpu {t_gpu:.0f}s) "
                + " ".join(f"{k2}={v:.3f}" for k2, v in vh.items())
            )
            if vl < best:
                best = vl
                torch.save(
                    {
                        "state": model.state_dict(),
                        "cfg": model.cfg,
                        "arm": a.arm,
                        "clim_cols": mems[0].meta["clim_cols"],
                        "step": step,
                        "val": vl,
                    },
                    os.path.join(od, "model.pt"),
                )
    json.dump(
        {
            "arm": a.arm,
            "steps": step,
            "best_val": best,
            "history": hist,
            "batch": B,
            "L": L_WIN,
            "minutes": a.minutes,
            "load_s": t_load,
            "gpu_s": t_gpu,
            "device": str(dev),
            "train_patches": int(sum(len(x) for x in tr_p)),
            "val_patches": int(sum(len(x) for x in va_p)),
        },
        open(os.path.join(od, "train.json"), "w"),
        indent=1,
    )
    status(f"D2 train {a.arm}: {step} steps in {a.minutes} min on {dev}, best val loss {best:.4f}")


def load_model(arm: str, dev) -> nm.NSet:
    ck = torch.load(os.path.join(NSET, arm, "model.pt"), map_location="cpu", weights_only=False)
    P = rl.load_params()
    c = ck["cfg"]
    m = nm.NSet(
        n_tok=c["n_tok"],
        n_clim=c["n_clim"],
        n_stat=c["n_stat"],
        n_pscal=c["n_pscal"],
        d=c["d"],
        heads=c["heads"],
        blocks=c["blocks"],
        dz=c["dz"],
        dh=c["dh"],
        lstm=c["lstm"],
        offset=c["offset"],
        resist=P["resist"],
        clim_cols=ck["clim_cols"],
    )
    m.load_state_dict(ck["state"])
    return m.to(dev).eval()


# ================================================================================================
# score
def sh13_fire(member: str, cells: np.ndarray, npatch: int, years: np.ndarray) -> np.ndarray:
    """f_SH13 [P, T] for the member (NaN where the feature row is missing)."""
    import explore_de_sh_patchheads as ph

    H = ph.load_heads("DEV-A")
    df = pl.read_parquet(
        os.path.join(XDE, "shared", "patchheads", "_features", f"{member}.parquet")
    ).filter(pl.col("Cell").is_in(cells.tolist()))
    f = H.fire_f(H.features(df))
    out = np.full((len(cells) * npatch, len(years)), np.nan, np.float32)
    ci = np.searchsorted(cells, df["Cell"].to_numpy())
    ok = cells[np.minimum(ci, len(cells) - 1)] == df["Cell"].to_numpy()
    ti = np.searchsorted(years, df["Year"].to_numpy())
    p = ci * npatch + df["Patch"].to_numpy()
    out[p[ok], ti[ok]] = f[ok]
    return out


def score_member(model, m: Member, dev, frozen: bool, fire13=None, B=512) -> dict:
    pp = m.patches_of_folds([HOLD_FOLD])
    P = rl.load_params()
    resist = np.asarray(P["resist"], np.float64)
    tot = {}
    br = {
        "n": 0,
        "model": 0.0,
        "base": 0.0,
        "rule_only": 0.0,
        "dead": 0,
        "pred_model": 0.0,
        "pred_base": 0.0,
    }
    ncell = len(m.cells)
    cell_sse = np.zeros((ncell, 3))  # per cell: n, SSE model, SSE base (for the cell bootstrap)
    gcal = []
    with torch.no_grad():
        for i in range(0, len(pp), B):
            p = pp[i : i + B]
            b = to_dev(m.batch(p, 0, m.T, frozen=frozen), dev)
            acc, coll = window(model, b, collect=not frozen)
            for k2, v in acc.items():
                tot.setdefault(k2, [0.0, 0.0])
                tot[k2][0] += float(v[0])
                tot[k2][1] += v[1]
            if frozen:
                continue
            for c in coll:
                pres = c["pres"].cpu().numpy()
                if not pres.any():
                    continue
                k = c["k"]
                pdie = c["pdie"].cpu().numpy()[pres]
                dead = c["fate"].cpu().numpy()[pres] == 1
                typ = c["typ"].cpu().numpy()[pres]
                hz = c["hz"].cpu().numpy()[pres].astype(np.float64)
                hard = c["hard_rule"].cpu().numpy()[pres]
                f13 = np.repeat(fire13[p, k][:, None], pres.shape[1], 1)[pres].astype(np.float64)
                f13 = np.nan_to_num(f13, nan=0.001)
                base = 1 - (1 - np.minimum(hz, 1.0)) * (1 - (1 - resist[typ]) * f13)
                base = np.where(hard, 1.0, base)
                rule = np.where(hard, 1.0, np.minimum(hz, 1.0))
                br["n"] += int(pres.sum())
                br["dead"] += int(dead.sum())
                br["model"] += float(((pdie - dead) ** 2).sum())
                br["base"] += float(((base - dead) ** 2).sum())
                pc_cell = np.repeat((p // m.npatch)[:, None], pres.shape[1], 1)[pres]
                np.add.at(cell_sse, (pc_cell, 0), 1.0)
                np.add.at(cell_sse, (pc_cell, 1), (pdie - dead) ** 2)
                np.add.at(cell_sse, (pc_cell, 2), (base - dead) ** 2)
                br["rule_only"] += float(((rule - dead) ** 2).sum())
                br["pred_model"] += float(pdie.sum())
                br["pred_base"] += float(base.sum())
                gok = c["gok"].cpu().numpy() > 0
                gcal.append(
                    np.stack(
                        [
                            c["Gy"].cpu().numpy()[gok],
                            c["gp"].cpu().numpy()[gok],
                            (c["G1"].cpu().numpy()[gok] < 0).astype(np.float32),
                        ],
                        -1,
                    )
                )
    out = {
        "nll": {k2: v[0] / max(v[1], 1) for k2, v in tot.items()},
        "count": {k2: v[1] for k2, v in tot.items()},
    }
    if not frozen:
        n = max(br["n"], 1)
        out["brier"] = {
            "n": br["n"],
            "obs_rate": br["dead"] / n,
            "model": br["model"] / n,
            "base": br["base"] / n,
            "rule_only": br["rule_only"] / n,
            "pred_rate_model": br["pred_model"] / n,
            "pred_rate_base": br["pred_base"] / n,
        }
        out["cell_sse"] = cell_sse[cell_sse[:, 0] > 0].tolist()
        G = np.concatenate(gcal)
        q = np.quantile(G[:, 0], np.linspace(0, 1, 11))
        d = np.clip(np.searchsorted(q, G[:, 0], side="right") - 1, 0, 9)
        out["g_sign_calibration_by_prev_G_decile"] = [
            {
                "decile": int(j),
                "G_prev_lo": float(q[j]),
                "G_prev_hi": float(q[j + 1]),
                "n": int((d == j).sum()),
                "pred": float(G[d == j, 1].mean()),
                "obs": float(G[d == j, 2].mean()),
            }
            for j in range(10)
        ]
        out["g_sign_overall"] = {"pred": float(G[:, 1].mean()), "obs": float(G[:, 2].mean())}
    return out


def stage_score(a):
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_model(a.arm, dev)
    res = {}
    for pool, members in (("A_MPI_fold5", POOL_A), ("B_ACCESS_fold5", POOL_B)):
        res[pool] = {}
        for mn in members:
            m = Member(mn, a.arm == "N-set")
            f13 = sh13_fire(mn, m.cells, m.npatch, m.years)
            r_true = score_member(model, m, dev, False, f13)
            r_frz = score_member(model, m, dev, True)
            res[pool][mn] = {"true": r_true, "frozen": {"nll": r_frz["nll"]}}
            log(
                f"{a.arm} {mn}: brier model {r_true['brier']['model']:.6f} "
                f"base {r_true['brier']['base']:.6f} "
                f"rule {r_true['brier']['rule_only']:.6f} | nll true "
                + json.dumps({k: round(v, 4) for k, v in r_true["nll"].items()})
                + " frozen "
                + json.dumps({k: round(v, 4) for k, v in r_frz["nll"].items()})
            )
            del m
        bt = [r["true"]["brier"] for r in res[pool].values()]
        n = sum(x["n"] for x in bt)
        res[pool]["_pooled_brier"] = {
            k: sum(x[k] * x["n"] for x in bt) / n
            for k in ("model", "base", "rule_only", "obs_rate", "pred_rate_model", "pred_rate_base")
        } | {"n": n}
        # bootstrap of (model - base) Brier over (member, cell) units, resampled with replacement
        cs = np.concatenate(
            [
                np.asarray(r["true"]["cell_sse"])
                for r in res[pool].values()
                if isinstance(r, dict) and "true" in r
            ]
        )
        brs = np.random.default_rng(3)
        dif = []
        for _ in range(2000):
            j = brs.integers(0, len(cs), len(cs))
            dif.append((cs[j, 1].sum() - cs[j, 2].sum()) / cs[j, 0].sum())
        res[pool]["_pooled_brier"]["diff_model_minus_base"] = (
            cs[:, 1].sum() - cs[:, 2].sum()
        ) / cs[:, 0].sum()
        res[pool]["_pooled_brier"]["diff_ci95_cell_bootstrap"] = [
            float(np.quantile(dif, 0.025)),
            float(np.quantile(dif, 0.975)),
        ]
    pa, pb = res["A_MPI_fold5"]["_pooled_brier"], res["B_ACCESS_fold5"]["_pooled_brier"]
    res["gate_a"] = {
        "A": {"model": pa["model"], "base": pa["base"], "pass": pa["model"] <= pa["base"]},
        "B": {"model": pb["model"], "base": pb["base"], "pass": pb["model"] <= pb["base"]},
    }
    res["gate_a"]["pass"] = res["gate_a"]["A"]["pass"] and res["gate_a"]["B"]["pass"]
    json.dump(res, open(os.path.join(NSET, a.arm, "score.json"), "w"), indent=1)
    status(
        f"D2 score {a.arm}: gate (a) death Brier pool A model {pa['model']:.6f} "
        f"vs base {pa['base']:.6f}; pool B "
        f"model {pb['model']:.6f} vs base {pb['base']:.6f} -> pass={res['gate_a']['pass']}"
    )


# ================================================================================================
# gate (free run)
def gate_cells(n: int = 200) -> np.ndarray:
    f = (
        pl.read_parquet(os.path.join(XDE, "shared", "registry", "folds.parquet"))
        .filter(pl.col("is_dev") & pl.col("fold").is_in([1, 2, 3, 4]))
        .sort("Cell")
    )
    return f["Cell"].to_numpy()[:n]


def stage_gate(a):
    import explore_de_sh_trans as tr

    cells = gate_cells() if not a.cells else np.loadtxt(a.cells, dtype=np.int64)
    rd = glob_run(a.arm, a.gcm)
    E = pl.concat(
        [
            pl.read_parquet(f)
            for f in sorted(_glob(os.path.join(rd, "chunk_*", "y*_ssp370.parquet")))
        ]
    )
    emu = E.filter(pl.col("isdead") == 0).group_by("Cell", "Year").agg(n=pl.len())
    mem = f"{a.gcm}_ssp370_s1_w2015"
    tf = st.year_files(tr.TRANS, mem)
    tru = []
    for y, f in sorted(tf.items()):
        d = pl.scan_parquet(f).filter(pl.col("Cell").is_in(cells.tolist()))
        tru.append(
            d.group_by("Cell").agg(n=pl.len()).with_columns(Year=pl.lit(y, pl.Int16)).collect()
        )
        if y == max(tf):
            tru.append(
                d.filter(pl.col("fate_y1") == 0)
                .group_by("Cell")
                .agg(n=pl.len())
                .with_columns(Year=pl.lit(y + 1, pl.Int16))
                .collect()
            )
    tru = pl.concat(tru)
    J = (
        pl.DataFrame(
            {
                "Cell": np.repeat(cells, 31).astype(np.int16),
                "Year": np.tile(np.arange(2014, 2045), len(cells)).astype(np.int16),
            }
        )
        .join(tru.with_columns(pl.col("Cell").cast(pl.Int16)), on=["Cell", "Year"], how="left")
        .join(
            emu.with_columns(pl.col("Cell").cast(pl.Int16), pl.col("Year").cast(pl.Int16)),
            on=["Cell", "Year"],
            how="left",
            suffix="_emu",
        )
        .with_columns(pl.col("n").fill_null(0), pl.col("n_emu").fill_null(0))
    )
    J = J.with_columns(spp=pl.col("n") / 250.0, spp_emu=pl.col("n_emu") / 250.0)
    last = (
        J.filter(pl.col("Year").is_between(2035, 2044))
        .group_by("Cell")
        .agg(pl.col("spp").mean(), pl.col("spp_emu").mean())
    )
    last = last.with_columns(ratio=pl.col("spp_emu") / pl.col("spp"))
    ok = last.filter(pl.col("spp") > 0)
    share = float(((ok["ratio"] - 1).abs() <= 0.5).mean())
    per_year = (
        J.filter(pl.col("n") > 0)
        .with_columns(w=((pl.col("spp_emu") / pl.col("spp") - 1).abs() <= 0.5))
        .group_by("Year")
        .agg(share=pl.col("w").mean(), emu=pl.col("spp_emu").mean(), truth=pl.col("spp").mean())
        .sort("Year")
    )
    g = {
        "arm": a.arm,
        "cells": len(cells),
        "cells_with_truth_stems": ok.height,
        "share_within_50pct_2035_2044": share,
        "median_ratio_2035_2044": float(ok["ratio"].median()),
        "diag_share_within_10pct": float(((ok["ratio"] - 1).abs() <= 0.1).mean()),
        "diag_share_within_20pct": float(((ok["ratio"] - 1).abs() <= 0.2).mean()),
        "pass": share >= 0.9,
        "per_year": per_year.to_dicts(),
    }
    tag = "" if not a.tag else f"_{a.tag}"
    g["gcm"], g["cellfile"] = a.gcm, a.cells or "gate_cells (first 200 dev cells of folds 1-4)"
    json.dump(g, open(os.path.join(NSET, a.arm, f"gate_b{tag}.json"), "w"), indent=1)
    status(
        f"D2 gate (b){tag} {a.arm} {a.gcm}: free run 2014->2044 ssp370, {ok.height} cells: "
        "share within +-50 % of "
        f"truth stems/patch (2035-44 mean) = {share:.3f} "
        f"(median ratio {g['median_ratio_2035_2044']:.3f}) -> "
        f"pass={g['pass']}"
    )
    log(json.dumps({k: v for k, v in g.items() if k != "per_year"}))
    log(per_year)


def _glob(p):
    import glob

    return glob.glob(p)


def glob_run(arm: str, gcm: str = "MPI-ESM1-2-HR") -> str:
    rs = _glob(os.path.join(XDE, "runs", f"nset_{arm}", f"{gcm}_s1_2014-2044_ssp370_actual_r1"))
    assert rs, "no free run"
    return rs[0]


# ================================================================================================
# free-run trajectory diagnostic (not a gate)
def stage_traj(a):
    """Yearly cell-mean trajectories of the free runs vs the truth on the gate cells: living printed
    stems per
    patch, flagged deaths per patch, new stems per patch, mean agb and height of living stems."""
    import explore_de_sh_trans as tr

    cells = gate_cells() if not a.cells else np.loadtxt(a.cells, dtype=np.int64)
    rows = []
    mem = f"{a.gcm}_ssp370_s1_w2015"
    tf = st.year_files(tr.TRANS, mem)
    for y, f in sorted(tf.items()):
        d = (
            pl.scan_parquet(f)
            .filter(pl.col("Cell").is_in(cells.tolist()))
            .select("agb", "Height", "fate_y1", "is_new_y")
            .collect()
        )
        np_ = len(cells) * 250
        rows.append(
            {
                "src": "truth",
                "Year": y,
                "stems": d.height / np_,
                "deaths_next": float((d["fate_y1"] == 1).sum()) / np_,
                "new": float(d["is_new_y"].sum()) / np_,
                "agb": float(d["agb"].mean()),
                "height": float(d["Height"].mean()),
            }
        )
    for arm in a.arms.split(","):
        rd = os.path.join(
            XDE, "runs", f"nset_{arm}", f"{a.gcm}_s1_2014-2044_ssp370_actual_r1", "chunk_000"
        )
        prev = None
        fs = sorted(_glob(os.path.join(rd, "y*.parquet")))
        frames = {int(os.path.basename(f)[1:5]): pl.read_parquet(f) for f in fs}
        for y in sorted(frames):
            E = frames[y]
            liv = E.filter(pl.col("isdead") == 0)
            np_ = len(cells) * 250
            key = liv.select(
                pl.concat_str(["Cell", "Patch", "Type", "ID"], separator="_").alias("k")
            )["k"]
            new = 0 if prev is None else int((~key.is_in(prev)).sum())
            nxt = frames.get(y + 1)
            dn = float((nxt["isdead"] == 1).sum()) / np_ if nxt is not None else np.nan
            rows.append(
                {
                    "src": arm,
                    "Year": y,
                    "stems": liv.height / np_,
                    "deaths_next": dn,
                    "new": new / np_ if prev is not None else np.nan,
                    "agb": float(liv["agb"].mean()),
                    "height": float(liv["Height"].mean()),
                }
            )
            prev = key
    T = pl.DataFrame(rows)
    out = os.path.join(NSET, f"traj_gate_cells{'_' + a.tag if a.tag else ''}.csv")
    T.write_csv(out)
    dec = (
        T.filter(pl.col("Year") >= 2015)
        .with_columns(dec=((pl.col("Year") - 2015) // 10) * 10 + 2015)
        .group_by("src", "dec")
        .agg(pl.col("stems", "deaths_next", "new", "agb", "height").mean())
        .sort("src", "dec")
    )
    with pl.Config(tbl_rows=60, tbl_cols=10):
        log(dec)
    dec.write_csv(os.path.join(NSET, f"traj_gate_cells{'_' + a.tag if a.tag else ''}_decades.csv"))


# ================================================================================================
# report
def _pool_nll(score: dict, pool: str, which: str) -> dict:
    out = {}
    for mn, r in score[pool].items():
        if mn.startswith("_"):
            continue
        nll = r["true"]["nll"] if which == "true" else r["frozen"]["nll"]
        cnt = r["true"]["count"]
        for k, v in nll.items():
            out.setdefault(k, [0.0, 0.0])
            out[k][0] += v * cnt[k]
            out[k][1] += cnt[k]
    return {k: v[0] / max(v[1], 1) for k, v in out.items()}


def stage_report(a):
    arms = {}
    for arm in ("D-main", "N-free", "N-set", "FROZEN", "D-main-grassreplay"):
        d = os.path.join(NSET, arm)
        r = {}
        for nm_, f in (
            ("train", "train.json"),
            ("score", "score.json"),
            ("gate_b", "gate_b.json"),
            ("free_run_heldout_ACCESS_fold5", "gate_b_heldout_ACCESS_fold5.json"),
        ):
            fp = os.path.join(d, f)
            if os.path.exists(fp):
                r[nm_] = json.load(open(fp))
        if not r:
            continue
        if "train" in r:
            hist = r["train"].get("history") or [None]
            r["train"] = {k: v for k, v in r["train"].items() if k != "history"} | {
                "last": hist[-1]
            }
        if "score" in r:
            sc = r["score"]
            r["heldout"] = {
                pool: {
                    "brier": sc[pool]["_pooled_brier"],
                    "nll_true": _pool_nll(sc, pool, "true"),
                    "nll_frozen": _pool_nll(sc, pool, "frozen"),
                }
                for pool in ("A_MPI_fold5", "B_ACCESS_fold5")
            }
            for pool in r["heldout"]:
                h = r["heldout"][pool]
                h["frozen_minus_true"] = {
                    k: h["nll_frozen"][k] - h["nll_true"][k] for k in h["nll_true"]
                }
            r["gate_a"] = sc["gate_a"]
            r["g_sign_calibration"] = {
                pool: {
                    mn: v["true"]["g_sign_calibration_by_prev_G_decile"]
                    for mn, v in sc[pool].items()
                    if not mn.startswith("_")
                }
                for pool in ("A_MPI_fold5", "B_ACCESS_fold5")
            }
            del r["score"]
        rd = os.path.join(XDE, "runs", f"nset_{arm}", "MPI-ESM1-2-HR_s1_2014-2044_ssp370_actual_r1")
        mf = os.path.join(rd, "meta_000.json")
        if os.path.exists(mf):
            mt = json.load(open(mf))
            r["free_run_cost"] = {
                "core_s_per_cell_year": mt["core_s_per_cell_year"],
                "core_s_per_cell_year_step": mt["core_s_per_cell_year_step"],
                "note": "process CPU time of the engine process; the model ran on one H100 "
                "GPU, whose "
                "time is NOT in this number",
            }
        arms[arm] = r
    dm = arms.get("D-main", {})
    ga = dm.get("gate_a", {}).get("pass")
    gb = dm.get("gate_b", {}).get("pass")
    if ga and gb:
        verdict = "PASS: stage 2 may start"
    elif ga is not None and gb is not None:
        verdict = "FAIL: stage 2 NOT started (pre-registered)"
    else:
        verdict = "INCOMPLETE"
    rep = {
        "id": "D2",
        "status": "ok" if ga is not None else "incomplete",
        "stage2_gate": {"a_death_brier": ga, "b_free_run_stems": gb, "verdict": verdict},
        "arms": arms,
        "deliverables": [
            os.path.abspath(__file__),
            os.path.join(REPO, "scripts", "explore_de_nset_model.py"),
            os.path.join(REPO, "scripts", "explore_de_nset_stepper.py"),
            NSET,
            STATUS,
        ],
        "notes": [
            "gate (b) has no power: the FROZEN null (no dynamics) also passes it on 100 % of cells",
            "gate (a) passes by 2e-7 in Brier (0.001 %): with the rule hazard as offset the "
            "learned correction adds "
            "~nothing; N-free (no offset) is 0.4-0.5 % worse",
            "free runs: recruitment ~20-30 % short from the second step on; replaying the truth's "
            "grass removes it "
            "(grass-cover closure erases the hidden sub-5 m signal)",
            "trajectory tables: nset/traj_gate_cells*.csv",
        ],
    }
    json.dump(rep, open(REPORT, "w"), indent=1, default=str)
    status(f"D2 report: stage-2 gate (D-main) a={ga} b={gb} -> {verdict}")
    log(verdict)


# ================================================================================================
# submit
def stage_submit(a):
    logs = os.path.join(REPO, "logs")
    me = os.path.abspath(__file__)
    eng = os.path.join(REPO, "scripts", "explore_de_engine.py")
    cf = os.path.join(NSET, "gate_cells.txt")
    np.savetxt(cf, gate_cells(), fmt="%d")
    jcf = os.path.join(XDE, "_jobs", f"nset_{a.arm}.jcf")
    steps = a.steps.split(",")
    body = []
    if "train" in steps:
        body.append(f"{PY} {me} train --arm {a.arm} --minutes {a.minutes} --batch {a.batch}")
    if "score" in steps:
        body.append(f"{PY} {me} score --arm {a.arm}")
    if "run" in steps:
        body.append(
            f"XDE_NSET_ARM={a.arm} {PY} {eng} run --arm nset_{a.arm} --stepper "
            "explore_de_nset_stepper:NsetStepper "
            f'--kwargs \'{{"arm": "{a.arm}"}}\' --gcm MPI-ESM1-2-HR '
            f"--seed 1 --start 2014 --end 2044 --legs ssp370 --cells {cf} --chunk-size 200"
        )
    if "gate" in steps:
        body.append(f"{PY} {me} gate --arm {a.arm}")
    tens = os.path.join(REPO, "scripts", "explore_de_sh_tensors.py")
    allm = TRAIN + POOL_B
    gj = " ".join(os.path.join(st.OUT, "dev", m_, "_gates.json") for m_ in allm)
    pre = ""
    if (
        "build" in steps
    ):  # the standard partition was saturated: build SH11 on this node, 5 members at once
        pre = (
            "".join(
                f"( POLARS_MAX_THREADS=3 {PY} {tens} build --member {m_} && "
                f"POLARS_MAX_THREADS=3 {PY} {tens} "
                f"gates --member {m_} ) &\n"
                for m_ in allm
            )
            + "wait\n"
        )
    # every consumer waits for the five SH11 gate files and refuses to train unless all pass
    pre += (
        f"until [ $(ls {gj} 2>/dev/null | wc -l) -eq {len(allm)} ]; do sleep 30; done\n"
        f"{PY} -c \"import json,sys; g=[json.load(open(f))['pass'] for f in sys.argv[1:]]; "
        "print('SH11 gates', g); "
        f'sys.exit(0 if all(g) else 1)" {gj} || exit 1\n'
    )
    cmds = pre + " && \\\n".join(body)
    with open(jcf, "w") as f:
        f.write(f"""#!/bin/bash
#SBATCH --job-name=X-nset-{a.arm}
#SBATCH --account=waldspektrum
#SBATCH --partition=gpu
#SBATCH --qos={a.qos}
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=300G
#SBATCH --time={a.walltime}
#SBATCH --output={logs}/X-nset-{a.arm}.%j.out
export POLARS_MAX_THREADS=16 OMP_NUM_THREADS=16 PYTHONUNBUFFERED=1
nvidia-smi --query-gpu=name,memory.total --format=csv
cd {REPO}/scripts
{cmds}
echo "=== JOB DONE exit=$? ==="
""")
    dep = ["--dependency", f"afterok:{a.after}"] if a.after else []
    jid = subprocess.check_output(["sbatch", "--parsable", *dep, jcf], text=True).strip()
    log(f"submitted {jid}")
    status(f"submitted {a.arm} job {jid} ({a.steps}, {a.minutes} min training)")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["train", "score", "gate", "submit", "report", "traj"])
    ap.add_argument("--arms", default="D-main,N-free,N-set,FROZEN")
    ap.add_argument("--gcm", default="MPI-ESM1-2-HR")
    ap.add_argument("--cells", default="")
    ap.add_argument("--tag", default="")
    ap.add_argument("--arm", default="D-main")
    ap.add_argument("--minutes", type=float, default=70)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--steps", default="train,score,run,gate")
    ap.add_argument("--walltime", default="04:00:00")
    ap.add_argument("--after", default="")
    ap.add_argument("--qos", default="gpushort")
    a = ap.parse_args(argv)
    {
        "train": stage_train,
        "score": stage_score,
        "gate": stage_gate,
        "submit": stage_submit,
        "report": stage_report,
        "traj": stage_traj,
    }[a.stage](a)


if __name__ == "__main__":
    main()
