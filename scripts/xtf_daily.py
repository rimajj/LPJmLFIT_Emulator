#!/usr/bin/env python3
"""xtf_daily.py -- ADR 0368 experiment 1 (SEPARATE EXPERIMENT, not for the paper): does the learned daily
water-carbon model lack long weather memory?

Arms on the clustered nitrogen-on runs (ADR 0342), everything but the network identical to the members NC_s0-4:
  B   the deployed MLP 256x3 (the existing NC_s<seed>, not retrained)
  TC  transformer, state token = B's whole input vector + ONE token of today's raw weather   (capacity control)
  TW  transformer, state token = B's inputs WITHOUT the six running means + the past 364 days of raw weather
      (14 daily tokens + 50 weekly-mean tokens)                                                  (memory arm)
ADR 0369 (same experiment family, also not for the paper):
  TP  TC + a fixed description of the place in the state token (place test)
  MR  the deployed MLP 256x3 retrained in this script (pipeline control for the M* arms)
  MP / ME / MM / MEP / MMP   MLP + place / + learned running averages (exponential bank) / + the past 12 months'
      30-day means / combinations                                                             (cheap memory)

  train --arm TC|TW --seed s        -> DATA/runs/<arm>_s<s>/model.pt
  run   --arm B|TC|TW --seed s      free runs, members 2 and 3, every leg with both -> annual.npz
  score [--arms ...]                ratios to the second run -> DATA/score.md, score.csv
  bench --arm ... --seed s          one-core cost of the daily step per cell-year

DATA = esm_land_emulator_data/xtf/daily; arrays read from f2_non (clu_emu_f2.py build).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

import numpy as np
import polars as pl
import torch
from torch import nn

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import f2_train as F  # noqa: E402

F2N = "/p/projects/open/Jamir/esm_land_emulator_data/f2_non"
OUT = "/p/projects/open/Jamir/esm_land_emulator_data/xtf/daily"
TRAIN_GCMS = ["gfdl-esm4", "mri-esm2-0", "ukesm1-0-ll", "canesm5", "cnrm-cm6-1", "cnrm-esm2-1", "ec-earth3", "miroc6"]
TEST_GCMS = ["ipsl-cm6a-lr", "mpi-esm1-2-hr"]
TRAIN_LEGS = [f"{g}_{t}" for g in TRAIN_GCMS for t in ("ssp126", "ssp370", "ssp585", "ssp370co2fix")]
WIN_COLS = [F.FEAT[k] for k in ("tas10", "tas30", "rsds30", "pr30", "pr90", "pr365")]
ND_TOK, NW_TOK = 14, 50  # TW: daily tokens t..t-13, weekly-mean tokens ending t-14-7k
NV = 4  # token variables: tas, log1p(rain), rsds, lwnet
# ADR 0369: arm -> (network, extra input groups appended to B's input vector)
ARMS = {"B": ("B", ()), "TC": ("T", ()), "TW": ("T", ()), "TP": ("T", ("place",)), "MR": ("M", ()),
        "MP": ("M", ("place",)), "ME": ("M", ("ema",)), "MM": ("M", ("mon",)), "MEP": ("M", ("ema", "place")),
        "MMP": ("M", ("mon", "place"))}  # fmt: skip
EMA_TAU = (3, 7, 15, 30, 60, 120, 240, 480)  # days
NMON = 12  # 30-day blocks of the past 360 days
PLACE_YEARS = 30  # the place description: 2020-2049 of the leg's own forcing (fixed for the whole run)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def configure():
    """The clustered members' settings (clu_emu_f2.stage_run / clu_emu_chain.sh)."""
    F.DATA, F.CO2_INPUT = F2N, True
    F.MEMBERS[:] = [2]
    F.NH, F.NL, F.NPP_HEAD, F.DEEP_TAU, F.STAND_DIR = 256, 3, "ra", 365.0, ""
    F.DROP[:] = [F.FEAT["huss"]]
    F.NIN = F.NFORC + 3 + 4 + 12 + 1


# ----------------------------------------------------------------------------------------------
# weather tokens
# ----------------------------------------------------------------------------------------------
def token_sources(forc):
    """forc (nc, T, 5) -> raw (nc, T, 4) and 7-day (nc, T, 4) un-normalised token values; index = forcing day."""
    tas, pr, rs, lw = (forc[:, :, i].astype(np.float64) for i in range(4))
    raw = np.stack([tas, np.log1p(pr), rs, lw], -1)

    def roll(x, n=7):
        c = np.cumsum(x, 1)
        o = c.copy()
        o[:, n:] = c[:, n:] - c[:, :-n]
        return o

    wk = np.stack([roll(tas) / 7, np.log1p(roll(pr)), roll(rs) / 7, roll(lw) / 7], -1)
    return raw.astype(np.float32), wk.astype(np.float32)


class TokenStore:
    """Normalised token sources of several legs on the device, fp16: src[i] = (2, nc, T, 4) raw / weekly."""

    def __init__(self, norm, dev):
        self.norm, self.dev, self.src = norm, dev, []

    def add(self, forc):
        raw, wk = token_sources(forc)
        mu, sd = self.norm
        raw = (raw - mu[0]) / sd[0]
        wk = (wk - mu[1]) / sd[1]
        self.src.append(torch.as_tensor(np.stack([raw, wk]), dtype=torch.float16, device=self.dev))
        return len(self.src) - 1

    def stack(self):
        self.all = torch.stack(self.src)  # (nleg, 2, nc, T, 4)
        self.src = []

    def gather(self, arm, leg, cell, day, src=None):
        """Tokens for (leg[i], cell[i], model day[i]) -> (B, L, 4); model day d = forcing day WARM + d."""
        s = self.all if src is None else src
        t = day + F.WARM
        if arm in ("TC", "TP"):
            return s[leg, 0, cell, t][:, None, :]
        jd = torch.arange(ND_TOK, device=t.device)
        jw = torch.arange(NW_TOK, device=t.device)
        a = s[leg[:, None], 0, cell[:, None], t[:, None] - jd]
        b = s[leg[:, None], 1, cell[:, None], t[:, None] - ND_TOK - 7 * jw]
        return torch.cat([a, b], 1)


def token_norm(forc):
    raw, wk = token_sources(forc)
    return (np.stack([raw.reshape(-1, NV).mean(0), wk.reshape(-1, NV).mean(0)]),
            np.stack([raw.reshape(-1, NV).std(0), wk.reshape(-1, NV).std(0)]) + 1e-6)  # fmt: skip


# ----------------------------------------------------------------------------------------------
# ADR 0369 extra inputs: place description, exponential running-mean bank, past 12 months
# ----------------------------------------------------------------------------------------------
def raw_vars(forc):
    """forc (nc, T, 5) -> (nc, T, 4) float64: tas, rain (mm/d, NOT logged), rsds, lwnet."""
    return np.stack([forc[:, :, i].astype(np.float64) for i in range(4)], -1)


def place_desc(forc):
    """(nc, 52): mean seasonal cycle (12 bins of the year) of tas, log1p(rain), rsds, lwnet over 2020-2049 +
    the SD of their daily values over the same 30 years. Fixed for the whole run."""
    v = raw_vars(forc)[:, F.WARM : F.WARM + PLACE_YEARS * 365]
    v[..., 1] = np.log1p(v[..., 1])
    nc = v.shape[0]
    mon = (np.arange(365) * 12) // 365
    cyc = v.reshape(nc, PLACE_YEARS, 365, 4).mean(1)  # (nc, 365, 4)
    m = np.stack([cyc[:, mon == j].mean(1) for j in range(12)], 1)  # (nc, 12, 4)
    return np.concatenate([m.reshape(nc, 48), v.std(1)], -1).astype(np.float32)


def ema_bank(forc):
    """(nc, T, 32): exponential running means m_t = m_(t-1) + (x_t - m_(t-1)) / tau for the four variables and
    the 8 time scales EMA_TAU; started at the mean of the warm-up year (2019). Rain enters as mm/d and is
    reported as log1p(mean). The network learns how to combine the bank (a learned running average)."""
    v = raw_vars(forc)
    nc, T, _ = v.shape
    K = len(EMA_TAU)
    tau = np.tile(np.asarray(EMA_TAU, np.float64), 4)  # column var * K + k has time scale EMA_TAU[k]
    out = np.empty((nc, T, 4 * K), np.float32)
    m = np.repeat(v[:, : F.WARM].mean(1), K, axis=1)
    for t in range(T):
        m = m + (np.repeat(v[:, t], K, axis=1) - m) / tau
        out[:, t] = m
    rain = slice(len(EMA_TAU), 2 * len(EMA_TAU))
    out[:, :, rain] = np.log1p(np.maximum(out[:, :, rain], 0))
    return out


class Extras:
    """The extra input columns of one (member, leg) for an arm: at(d) -> (nc, k), take(c, d) -> (n, k)."""

    def __init__(self, kinds, forc):
        self.kinds = kinds
        self.place = place_desc(forc) if "place" in kinds else None
        self.ema = ema_bank(forc) if "ema" in kinds else None
        if "mon" in kinds:
            v = raw_vars(forc)
            v[..., 1] = np.log1p(v[..., 1])
            self.cum = np.concatenate([np.zeros_like(v[:, :1]), np.cumsum(v, 1)], 1)  # cum[:, t] = sum of days < t

    def take(self, c, d):
        t = d + F.WARM
        parts = []
        for k in self.kinds:
            if k == "place":
                parts.append(self.place[c])
            elif k == "ema":
                parts.append(self.ema[c, t])
            else:  # block j = days t-30j-29 .. t-30j
                hi = t[:, None] - 30 * np.arange(NMON)[None, :] + 1
                blk = (self.cum[c[:, None], hi] - self.cum[c[:, None], hi - 30]) / 30.0  # (n, 12, 4)
                parts.append(blk.reshape(len(c), NMON * NV).astype(np.float32))
        return np.concatenate(parts, -1) if parts else np.zeros((len(c), 0), np.float32)

    def at(self, d, nc):
        return self.take(np.arange(nc), np.full(nc, d))


def n_extra(kinds):
    return sum({"place": 52, "ema": 4 * len(EMA_TAU), "mon": NMON * NV}[k] for k in kinds)


# ----------------------------------------------------------------------------------------------
# model
# ----------------------------------------------------------------------------------------------
def head(o, prec, S_prev, ys):
    """f2_train.Net.forward's output head (npp = gpp - ra)."""
    sp = nn.functional.softplus
    f, m, i = torch.sigmoid(o[:, 0]), torch.sigmoid(o[:, 1]), torch.sigmoid(o[:, 2])
    gpp = sp(o[:, 7]) * ys[6]
    npp = gpp - sp(o[:, 8]) * ys[7]
    return torch.stack([prec * f - m * S_prev, prec * i, sp(o[:, 3]) * ys[2], sp(o[:, 4]) * ys[3],
                        sp(o[:, 5]) * ys[4], o[:, 6] * ys[5], gpp, npp], -1)  # fmt: skip


class XNet(nn.Module):
    def __init__(self, mu, sd, ysd, arm, d=128, nl=4, nh=4, ff=256):
        super().__init__()
        self.arm = arm
        self.register_buffer("mu", torch.as_tensor(mu))
        self.register_buffer("sd", torch.as_tensor(sd))
        self.register_buffer("ysd", torch.as_tensor(ysd))
        keep = torch.ones(len(mu))
        if arm == "TW":
            keep[WIN_COLS] = 0.0
        self.register_buffer("keep", keep)
        L = 1 if arm in ("TC", "TP") else ND_TOK + NW_TOK
        self.inp = nn.Linear(len(mu), d)
        self.tok = nn.Linear(NV, d)
        self.pos = nn.Parameter(torch.randn(L, d) * 0.02)
        self.state = nn.Parameter(torch.randn(d) * 0.02)
        layer = nn.TransformerEncoderLayer(d, nh, ff, dropout=0.0, activation="gelu", batch_first=True,
                                           norm_first=True)  # fmt: skip
        self.enc = nn.TransformerEncoder(layer, nl, enable_nested_tensor=False)
        self.ln = nn.LayerNorm(d)
        self.out = nn.Linear(d, 9)

    def forward(self, x, seq, prec, S_prev):
        xn = (x - self.mu) / self.sd * self.keep
        h0 = self.inp(xn) + self.state
        hs = self.tok(seq.to(h0.dtype)) + self.pos
        h = self.enc(torch.cat([h0[:, None], hs], 1))
        o = self.out(self.ln(h[:, 0])).float()
        return head(o, prec, S_prev, self.ysd)


class MNet(nn.Module):
    """ADR 0369: the deployed MLP (256 x 3, SiLU, the f2_train.Net trunk) on B's inputs + the arm's extras."""

    def __init__(self, mu, sd, ysd, arm, nh=256, nl=3):
        super().__init__()
        self.arm = arm
        self.register_buffer("mu", torch.as_tensor(mu))
        self.register_buffer("sd", torch.as_tensor(sd))
        self.register_buffer("ysd", torch.as_tensor(ysd))
        layers, n = [], len(mu)
        for _ in range(nl):
            layers += [nn.Linear(n, nh), nn.SiLU()]
            n = nh
        self.trunk = nn.Sequential(*layers, nn.Linear(n, 9))

    def forward(self, x, seq, prec, S_prev):
        return head(self.trunk((x - self.mu) / self.sd), prec, S_prev, self.ysd)


def build_net(mu, sd, ysd, arm):
    cls = MNet if ARMS[arm][0] == "M" else XNet
    return cls(mu, sd, ysd, arm)


def save(net, norm, path, extra):
    torch.save({"state": net.state_dict(), "tok_mu": norm[0], "tok_sd": norm[1], "arm": net.arm, **extra}, path)


def load(path, dev):
    ck = torch.load(path, map_location=dev, weights_only=False)
    st = ck["state"]
    net = build_net(*(st[k].cpu().numpy() for k in ("mu", "sd", "ysd")), ck["arm"]).to(dev)
    net.load_state_dict(st)
    return net.eval(), (ck["tok_mu"], ck["tok_sd"])


# ----------------------------------------------------------------------------------------------
# train
# ----------------------------------------------------------------------------------------------
def stage_train(a):
    configure()
    torch.manual_seed(a.seed)
    dev = torch.device("cuda")
    torch.backends.cuda.matmul.allow_tf32 = True
    out = f"{OUT}/runs/{a.arm}_s{a.seed}"
    os.makedirs(out, exist_ok=True)
    cells = pl.read_parquet(f"{F2N}/cells.parquet")
    lat = cells["lat"].to_numpy().astype(np.float32)
    tr, va, ho = F.split_cells(cells)
    log(f"arm {a.arm} seed {a.seed}: cells train {len(tr)} val {len(va)} held-out {len(ho)}")
    rng = np.random.default_rng(a.seed)
    legs = TRAIN_LEGS[: a.nlegs] if a.nlegs else TRAIN_LEGS  # --nlegs: smoke tests only
    per = a.nsamp // len(legs)
    norm = token_norm(np.load(f"{F2N}/forc_m2_{TRAIN_LEGS[0]}.npy"))
    kind, kinds = ARMS[a.arm]
    store = TokenStore(norm, dev) if kind == "T" else None
    parts, vparts = [], []
    for li, leg in enumerate(legs):
        ml = F.MemberLeg(2, leg, lat)
        forc = np.load(f"{F2N}/forc_m2_{leg}.npy")
        if store is not None:
            store.add(forc)
        ex = Extras(kinds, forc)
        for idx, n, dst in ((tr, per, parts), (va, max(per // 10, 1000), vparts)):
            c = rng.choice(idx, n)
            d = rng.integers(1, F.ND, n)
            x = np.concatenate([ml.inputs_teacher(c, d), ex.take(c, d)], -1)
            y, prec, S_prev, _ = ml.targets(c, d)
            dst.append((x, y, prec, S_prev, np.full(n, li), c, d))
        del ml, ex, forc
        log(f"{leg}: sampled")
    if store is not None:
        store.stack()
    gather = (lambda li, c, d: store.gather(a.arm, li, c, d)) if store is not None else (lambda li, c, d: None)
    mlp = kind == "M"  # the MLP arms train exactly as f2_train.train: fp32, no gradient clipping
    cat = lambda ps, i: np.concatenate([p[i] for p in ps])  # noqa: E731
    X, Y = cat(parts, 0), cat(parts, 1)
    mu, sd, ysd = X.mean(0), X.std(0) + 1e-6, Y.std(0) + 1e-6
    T = [torch.as_tensor(cat(parts, i), device=dev) for i in range(7)]
    V = [torch.as_tensor(cat(vparts, i), device=dev) for i in range(7)]
    del parts, vparts, X, Y
    net = build_net(mu.astype(np.float32), sd.astype(np.float32), ysd.astype(np.float32), a.arm).to(dev)
    log(f"parameters {sum(p.numel() for p in net.parameters()):,}  rows {len(T[0]):,}")
    w = 1.0 / torch.as_tensor(ysd, device=dev) ** 2
    opt = torch.optim.Adam(net.parameters(), lr=a.lr)
    nb = math.ceil(len(T[0]) / a.batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, a.lr, total_steps=a.epochs * nb)
    best, best_state = float("inf"), None
    for ep in range(a.epochs):
        t0 = time.time()
        net.train()
        perm = torch.randperm(len(T[0]), device=dev)
        tot = 0.0
        for b in range(nb):
            ix = perm[b * a.batch : (b + 1) * a.batch]
            x, y, pr, S, li, c, d = (t[ix] for t in T)
            seq = gather(li, c, d)
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=not mlp):
                pred = net(x, seq, pr, S)
            loss = (((pred.float() - y) ** 2) * w).mean()
            opt.zero_grad(set_to_none=True)
            loss.backward()
            if not mlp:
                torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
            sched.step()
            tot += loss.item()
        net.eval()
        with torch.no_grad():
            vl, per_t = 0.0, torch.zeros(len(F.TARGETS), device=dev)
            for b in range(0, len(V[0]), 8192):
                x, y, pr, S, li, c, d = (t[b : b + 8192] for t in V)
                e = ((net(x, gather(li, c, d), pr, S) - y) ** 2) * w
                per_t += e.sum(0)
                vl += e.mean(1).sum().item()
            vl /= len(V[0])
            per_t = (per_t / len(V[0])).cpu().numpy()
        log(f"epoch {ep}: train {tot / nb:.4f} val {vl:.4f} per-target "
            f"{dict(zip(F.TARGETS, np.round(per_t, 4).tolist(), strict=True))} {time.time() - t0:.0f}s")  # fmt: skip
        if vl < best - 1e-5:
            best = vl
            best_state = {k: v.detach().clone() for k, v in net.state_dict().items()}
    net.load_state_dict(best_state)
    save(net, norm, f"{out}/model.pt", {"val": best, "args": vars(a)})
    log(f"saved {out}/model.pt (best val {best:.4f})")


# ----------------------------------------------------------------------------------------------
# free runs
# ----------------------------------------------------------------------------------------------
def score_legs():
    legs = []
    for g in TRAIN_GCMS + TEST_GCMS:
        for t in ("ssp126", "ssp370", "ssp585", "ssp370co2fix", "ssp585co2fix"):
            leg = f"{g}_{t}"
            if all(os.path.exists(f"{F2N}/daily_m{k}_{leg}.npy") for k in (2, 3)):
                legs.append(leg)
    return legs


def run_free(step, ml):
    """f2_train.run_free with a step function step(x, prec, S, d) -> y (nc, 8)."""
    nc = ml.daily.shape[0]
    cells = np.arange(nc)
    W = ml.daily[:, 0, F.RM].astype(np.float64)
    S = ml.daily[:, 0, F.SWE].astype(np.float64)
    D = np.zeros(nc)
    out = {k: np.zeros((nc, F.ND), np.float32) for k in F.ANNUAL}
    for d in range(1, F.ND):
        x = F.assemble(ml.ff, ml.sinA, ml.cosA, ml.slat, ml.st, ml.cap, W.astype(np.float32),
                       S.astype(np.float32), cells, np.full(nc, d), co2=ml.co2)  # fmt: skip
        prec = ml.daily[:, d, F.PREC].astype(np.float32)
        y = step(x, prec, S.astype(np.float32), d).astype(np.float64)
        W, S, D, runoff, *_ = F.bucket_step(y, prec, W, S, D, ml.cap[:, d // 365].astype(np.float64))
        out["gpp"][:, d], out["npp"][:, d] = y[:, 6], y[:, 7]
        out["et"][:, d] = y[:, 1] + y[:, 2] + y[:, 3]
        out["runoff"][:, d] = runoff
    t0 = ml.daily[:, 0]
    out["gpp"][:, 0], out["npp"][:, 0] = t0[:, F.GPP], t0[:, F.NPP]
    out["et"][:, 0] = t0[:, F.INTERC] + t0[:, F.TRANSP] + t0[:, F.EVAP]
    out["runoff"][:, 0] = t0[:, F.RUNOFF]
    return F.annualise(out)


def make_step(a, dev, nc):
    if a.arm == "B":
        net, ck = F.load_net(f"{F2N}/runs/NC_s{a.seed}/model.pt", dev)
        net.load_state_dict(ck)
        net.eval()

        def step(x, prec, S, d, src=None):
            return F.predict(net, x, prec, S, dev)

        return step, None
    net, norm = load(f"{OUT}/runs/{a.arm}_s{a.seed}/model.pt", dev)
    store = TokenStore(norm, dev) if ARMS[a.arm][0] == "T" else None
    zero = torch.zeros(nc, dtype=torch.long, device=dev)
    cells = torch.arange(nc, device=dev)

    @torch.no_grad()
    def step(x, prec, S, d, src=None):
        if step.ex is not None:  # ADR 0369 extras: a callable (online state, bench) or an Extras (free runs)
            x = np.concatenate([x, step.ex(d) if callable(step.ex) else step.ex.at(d, nc)], -1)
        seq = None
        if store is not None:
            seq = store.gather(a.arm, zero, cells, torch.full((nc,), d, device=dev), src=step.src)
        t = lambda v: torch.as_tensor(v, device=dev)  # noqa: E731
        return net(t(x), seq, t(prec), t(S)).cpu().numpy()

    step.ex = None
    return step, store


def stage_run(a):
    configure()
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.backends.cuda.matmul.allow_tf32 = False  # free runs in full fp32
    cells = pl.read_parquet(f"{F2N}/cells.parquet")
    lat = cells["lat"].to_numpy().astype(np.float32)
    out = f"{OUT}/runs/{a.arm}_s{a.seed}"
    os.makedirs(out, exist_ok=True)
    ap = f"{out}/annual.npz"
    ann = dict(np.load(ap)) if os.path.exists(ap) else {}
    step, store = make_step(a, dev, cells.height)
    for leg in [lg for lg in score_legs() if not a.legs or lg in a.legs.split(",")]:
        for k in (2, 3):
            if f"free__m{k}__{leg}__gpp" in ann:
                continue
            t0 = time.time()
            ml = F.MemberLeg(k, leg, lat)
            forc = np.load(f"{F2N}/forc_m{k}_{leg}.npy")
            if store is not None:
                store.src = []
                store.add(forc)
                store.stack()
                step.src = store.all
            if ARMS[a.arm][1]:
                step.ex = Extras(ARMS[a.arm][1], forc)
            fr = run_free(step, ml)
            tr = F.truth_annual(ml)
            for v in F.ANNUAL:
                ann[f"free__m{k}__{leg}__{v}"], ann[f"truth__m{k}__{leg}__{v}"] = fr[v], tr[v]
            np.savez(ap, **ann)
            log(f"{a.arm}_s{a.seed} m{k} {leg}: {time.time() - t0:.0f}s")
    log(f"annual -> {ap}")


# ----------------------------------------------------------------------------------------------
# score
# ----------------------------------------------------------------------------------------------
EARLY, LATE, ALL = slice(1, 31), slice(51, 81), slice(1, 81)
PAIRS = ((2, 3), (3, 2))  # (scored member k, second run j)


def _rel(a, b):
    """|a / b - 1| with nan where |b| is ~0 (a near-zero runoff cell cannot blow up a median)."""
    return np.abs(a / np.where(np.abs(b) > 1e-6, b, np.nan) - 1)


def stats(T, E, mask):
    """T, E: dict k -> (nc, NY); ratio of the emulator's error to the second run's, pooled over members."""
    o = {}
    md, pc = np.nanmedian, np.nanpercentile
    for name, sl in (("early", EARLY), ("late", LATE)):
        eE = np.concatenate([_rel(E[k][mask, sl].mean(1), T[k][mask, sl].mean(1)) for k, _ in PAIRS])
        eR = np.concatenate([_rel(T[j][mask, sl].mean(1), T[k][mask, sl].mean(1)) for k, j in PAIRS])
        o[f"30y_{name}_p50"] = md(eE) / md(eR)
        o[f"30y_{name}_p90"] = pc(eE, 90) / pc(eR, 90)
    dec = []
    for d0 in range(1, 81, 10):
        sl = slice(d0, d0 + 10)
        nk = {k: np.where(np.abs(T[k][mask, ALL].mean(1)) > 1e-6, np.abs(T[k][mask, ALL].mean(1)), np.nan)[:, None]
              for k, _ in PAIRS}
        eE = np.concatenate([(np.abs(E[k][mask, sl] - T[k][mask, sl]) / nk[k]).ravel() for k, _ in PAIRS])
        eR = np.concatenate([(np.abs(T[j][mask, sl] - T[k][mask, sl]) / nk[k]).ravel() for k, j in PAIRS])
        dec.append(md(eE) / md(eR))
    o["year_p50"] = float(np.mean(dec))
    o["drift"] = np.mean(dec[-2:]) / np.mean(dec[:2])
    d = lambda x: x[mask, LATE].mean(1) - x[mask, EARLY].mean(1)  # noqa: E731
    rE = np.concatenate([np.abs(d(E[k]) - d(T[k])) for k, _ in PAIRS])
    rR = np.concatenate([np.abs(d(T[j]) - d(T[k])) for k, j in PAIRS])
    o["response_p50"] = md(rE) / md(rR)
    return o


def stage_score(a):
    cells = pl.read_parquet(f"{F2N}/cells.parquet")
    ho = cells["heldout"].to_numpy()
    w = np.cos(np.radians(cells["lat"].to_numpy()))
    runs = sorted(r for r in os.listdir(f"{OUT}/runs") if os.path.exists(f"{OUT}/runs/{r}/annual.npz"))
    rows = []
    for r in runs:
        z = np.load(f"{OUT}/runs/{r}/annual.npz")
        arm, seed = r.rsplit("_s", 1)
        legs = sorted({k.split("__")[2] for k in z.files if k.startswith("free__m3__")})
        # ADR 0368 section 1 scores the 3 rising-CO2 scenarios; the CO2-fixed legs (2 held-out models) are reported
        # as their own group and never enter the decision (amendment written before the score ran)
        std = [lg for lg in legs if "co2fix" not in lg]
        for grp, gl, cm, lp in (("heldout x heldout-GCM", TEST_GCMS, ho, std),
                                ("heldout x train-GCM", TRAIN_GCMS, ho, std),
                                ("train cells x all", TRAIN_GCMS + TEST_GCMS, ~ho, std),
                                ("heldout x heldout-GCM co2fix (extra)", TEST_GCMS, ho,
                                 [lg for lg in legs if "co2fix" in lg])):  # fmt: skip
            gl_legs = [lg for lg in lp if lg.rsplit("_", 1)[0] in gl]
            if not gl_legs:
                continue
            for v in F.ANNUAL:
                acc = []
                for lg in gl_legs:
                    T = {k: z[f"truth__m{k}__{lg}__{v}"].astype(np.float64) for k in (2, 3)}
                    E = {k: z[f"free__m{k}__{lg}__{v}"].astype(np.float64) for k in (2, 3)}
                    gpp = (z[f"truth__m2__{lg}__gpp"][:, ALL].mean(1) + z[f"truth__m3__{lg}__gpp"][:, ALL].mean(1)) / 2
                    mask = cm & (gpp >= 50)
                    s = stats(T, E, mask)
                    tot = np.mean([abs((w[mask] * E[k][mask, ALL].mean(1)).sum()
                                       / (w[mask] * T[k][mask, ALL].mean(1)).sum() - 1) for k, _ in PAIRS])
                    s["total_err"] = tot
                    acc.append(s)
                row = {"arm": arm, "seed": int(seed), "group": grp, "flux": v, "nlegs": len(gl_legs)}
                row.update({k: float(np.median([s[k] for s in acc])) for k in acc[0]})
                rows.append(row)
    df = pl.DataFrame(rows)
    df.write_csv(f"{OUT}/score.csv")
    stat_cols = ["30y_early_p50", "30y_late_p50", "30y_late_p90", "year_p50", "drift", "response_p50", "total_err"]
    summ = (df.group_by(["group", "flux", "arm"])
            .agg([pl.col(c).mean().alias(c) for c in stat_cols]
                 + [(pl.col(c).max() - pl.col(c).min()).alias(f"{c}_spread") for c in stat_cols]
                 + [pl.len().alias("nseeds")])
            .sort("group", "flux", "arm"))  # fmt: skip
    summ.write_csv(f"{OUT}/score_summary.csv")
    with pl.Config(tbl_rows=200, tbl_cols=30, tbl_width_chars=300, float_precision=3):
        print(summ.select(["group", "flux", "arm", "nseeds"] + stat_cols
                          + ["year_p50_spread", "30y_late_p50_spread"]))  # fmt: skip
    decide(summ)


def decide(summ):
    """ADR 0368 section 1 decision, held-out cells x held-out climate models."""
    g = summ.filter(pl.col("group") == "heldout x heldout-GCM")
    if g.is_empty():
        return
    get = lambda arm, flux, c: g.filter((pl.col("arm") == arm) & (pl.col("flux") == flux))[c].to_list()  # noqa: E731
    res = {}
    for cmp_, (a1, a0) in (("memory (TW vs TC)", ("TW", "TC")), ("capacity (TC vs B)", ("TC", "B"))):
        wins = []
        for flux in ("npp", "et", "runoff"):
            try:
                s_y = get("B", flux, "year_p50_spread")[0]
                s_l = get("B", flux, "30y_late_p50_spread")[0]
                s_d = get("B", flux, "drift_spread")[0]
                y1, y0 = get(a1, flux, "year_p50")[0], get(a0, flux, "year_p50")[0]
                l1, l0 = get(a1, flux, "30y_late_p50")[0], get(a0, flux, "30y_late_p50")[0]
                d1, d0 = get(a1, flux, "drift")[0], get(a0, flux, "drift")[0]
            except IndexError:
                continue
            # "drift not worse": distance from no drift (ratio 1), so an error that shrinks is not counted as worse
            if (y0 - y1 > s_y) and (l0 - l1 > s_l) and (abs(d1 - 1) - abs(d0 - 1) <= s_d):
                wins.append(flux)
        res[cmp_] = f"{'HELPS' if len(wins) >= 2 else 'no measurable gain'} (wins: {wins or 'none'})"
    print(json.dumps(res, indent=1))


class OnlineExtras:
    """The extras carried as a running state, updated once a day from that day's weather (bench, ADR 0369):
    the exponential bank (32 numbers), a 360-day ring of the four variables for the 12 30-day blocks, the fixed
    place description. Called in day order d = 1, 2, ... (model day d = forcing day WARM + d)."""

    def __init__(self, kinds, forc):
        self.kinds = kinds
        self.v = raw_vars(forc)
        self.place = place_desc(forc) if "place" in kinds else None
        K = len(EMA_TAU)
        self.tau = np.tile(np.asarray(EMA_TAU, np.float64), 4)
        self.m = np.repeat(self.v[:, : F.WARM].mean(1), K, axis=1)
        for t in range(F.WARM + 1):  # history up to forcing day WARM (= model day 0)
            self.m = self.m + (np.repeat(self.v[:, t], K, axis=1) - self.m) / self.tau
        lv = self.v.copy()
        lv[..., 1] = np.log1p(lv[..., 1])
        self.lv = lv
        # ring of the last 361 days (slot = day mod 361) + the 12 running 30-day block sums (block j = days
        # t-30j-29 .. t-30j); each day every block gains one day and loses one: 2 x 12 x 4 additions per cell
        t0 = F.WARM
        self.ring = np.zeros((lv.shape[0], 361, NV))
        for t in range(t0 - 360, t0 + 1):
            self.ring[:, t % 361] = lv[:, t]
        self.bs = np.stack([lv[:, t0 - 30 * j - 29 : t0 - 30 * j + 1].sum(1) for j in range(NMON)], 1)
        self.jj = 30 * np.arange(NMON)
        self.t = t0

    def __call__(self, d):
        self.t += 1
        assert self.t == F.WARM + d
        today = self.v[:, self.t]
        parts = []
        if "ema" in self.kinds:
            self.m = self.m + (np.repeat(today, len(EMA_TAU), axis=1) - self.m) / self.tau
        if "mon" in self.kinds:
            self.ring[:, self.t % 361] = self.lv[:, self.t]
            self.bs += self.ring[:, (self.t - self.jj) % 361] - self.ring[:, (self.t - self.jj - 30) % 361]
        for k in self.kinds:
            if k == "place":
                parts.append(self.place)
            elif k == "ema":
                e = self.m.astype(np.float32).copy()
                r = slice(len(EMA_TAU), 2 * len(EMA_TAU))
                e[:, r] = np.log1p(np.maximum(e[:, r], 0))
                parts.append(e)
            else:  # block j (newest first) = mean of days t-30j-29 .. t-30j
                parts.append((self.bs / 30.0).reshape(len(self.bs), -1))
        return np.concatenate(parts, -1).astype(np.float32)


# ----------------------------------------------------------------------------------------------
def stage_bench(a):
    """One core: network + bucket for all 674 cells over 365 days, per cell-year (the gather included)."""
    configure()
    torch.set_num_threads(1)
    dev = torch.device("cpu")
    cells = pl.read_parquet(f"{F2N}/cells.parquet")
    lat = cells["lat"].to_numpy().astype(np.float32)
    leg = "ipsl-cm6a-lr_ssp370"
    ml = F.MemberLeg(2, leg, lat)
    step, store = make_step(a, dev, cells.height)
    forc = np.load(f"{F2N}/forc_m2_{leg}.npy")
    if store is not None:
        store.add(forc)
        store.stack()
        step.src = store.all.float()
    nc = cells.height
    kinds = ARMS[a.arm][1] if a.arm in ARMS else ()
    if kinds:  # the extras' own daily update (online, as an ESM would carry it), checked against the free-run arrays
        on = OnlineExtras(kinds, forc)
        ref = Extras(kinds, forc)
        for d in range(1, 40):
            assert np.allclose(on(d), ref.at(d, nc), rtol=1e-4, atol=1e-4), f"online extras differ on day {d}"
        step.ex = OnlineExtras(kinds, forc)
    W = ml.daily[:, 0, F.RM].astype(np.float32)
    S = ml.daily[:, 0, F.SWE].astype(np.float32)
    x = F.assemble(ml.ff, ml.sinA, ml.cosA, ml.slat, ml.st, ml.cap, W, S, np.arange(nc), np.full(nc, 1), co2=ml.co2)
    prec = ml.daily[:, 1, F.PREC].astype(np.float32)
    times = []
    for _ in range(3):
        if kinds:  # set-up (warm-up year, place description) once per run, outside the timed loop
            step.ex = OnlineExtras(kinds, forc)
        t0 = time.perf_counter()
        for d in range(1, 366):
            step(x, prec, S, d)
        times.append((time.perf_counter() - t0) / nc)
    log(f"{a.arm}_s{a.seed}: {np.median(times):.3e} core-s per cell-year (network + token gather, one core)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["train", "run", "score", "bench"])
    ap.add_argument("--arm", default="TW", choices=list(ARMS))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--nsamp", type=int, default=40_000_000)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch", type=int, default=16384)
    ap.add_argument("--lr", type=float, default=3e-3)
    ap.add_argument("--nlegs", type=int, default=0, help="smoke test: first n training legs only")
    ap.add_argument("--legs", default="", help="run: only these legs (comma list; smoke tests)")
    a = ap.parse_args()
    {"train": stage_train, "run": stage_run, "score": stage_score, "bench": stage_bench}[a.stage](a)
    log("=== DONE")


if __name__ == "__main__":
    main()
