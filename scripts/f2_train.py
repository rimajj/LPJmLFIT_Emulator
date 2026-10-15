#!/usr/bin/env python3
"""Phase A of the learned daily water-carbon model (ADR 0320): train arm A, free-run it, score it.

Reads the arrays of scripts/f2_build_daily_table.py (DATA). Writes to DATA/runs/<tag>/:
  model.pt        network + input normalisation
  annual.npz      annual totals per (member, leg, cell, year): truth, free, one-step, climatology
  summary.json    every pre-registered statistic of ADR 0320 section 5, pass flags, reports
  summary.md      the same as a table

Design (ADR 0320 section 3): one MLP (2 x 64, SiLU). Snow S, top-metre water W in [0, cap]
and a deep store D are closed by construction:
  S_t = S_{t-1} + dS,  dS = prec*f - m*S_{t-1}        (f, m in [0, 1])
  W_t = W_{t-1} + prec - dS - interc - transp - evap - runoff - deep
  overflow above cap -> runoff, deficit below 0 -> taken from deep;  D_t = D_{t-1} + deep
so prec - ET - runoff = d(S + W + D) holds every day.
Optional deep release (--deep-tau T days, ADR 0326; 0 = off): D drains into runoff at D/T per day,
as the original's deep layers drain to runoff, so the deep store cannot accumulate the split error.

Usage: python scripts/f2_train.py [--tag A] [--nsamp 40000000] [--epochs 10] [--device cuda]
"""

import argparse
import copy
import json
import math
import os
import time

import numpy as np
import polars as pl
import torch
from torch import nn

DATA = "/p/projects/open/Jamir/esm_land_emulator_data/f2"
TRAIN_LEGS = ["ctl_obs", "mpi-esm1-2-hr_ssp126", "mpi-esm1-2-hr_ssp370"]
TEST_LEGS = ["mpi-esm1-2-hr_ssp585", "ukesm1-0-ll_ssp370"]
ALL_LEGS = TRAIN_LEGS + TEST_LEGS
MEMBERS = [1, 2, 3, 4]
STAND_DIR = ""  # --stand-dir: read stand_<tag>.npy from DATA/<dir> where present (default: the original's)
NY = 81  # 2020..2100
ND = NY * 365
WARM = 365  # forcing arrays start with the 2019 warm-up year
PREC, TRANSP, EVAP, INTERC, RUNOFF, SWE, RM, PET, NPP, GPP = range(10)
TARGETS = ["dS", "interc", "transp", "evap", "runoff", "deep", "gpp", "npp"]
ANNUAL = ["gpp", "et", "npp", "runoff"]
NFORC = 12
NIN = NFORC + 3 + 4 + 12
# --co2 (ADR 0342, nitrogen-on model only): + the year's CO2 / 1000 as the LAST input column
CO2_INPUT = False
# --all-cells (ADR 0344, deployment): the held-out cells train too (validation stays 10 % of the blocks)
ALL_CELLS = False
NH, NL = 64, 2  # network width / depth (set from the command line)
NPP_HEAD = "direct"  # "ra": npp = gpp - ra, ra >= 0 (ADR 0323 arm R)
FEAT = {"tas": 0, "pr": 1, "rsds": 2, "lwnet": 3, "huss": 4}  # raw daily forcing columns of x
DROP = []  # input columns held at 0 (--drop-inputs, ADR 0327); the network then cannot use them
DEEP_TAU = 0.0  # days; > 0: deep store releases D/DEEP_TAU per day into runoff (ADR 0326)
CARBON_HEAD = "free"  # "physical": structured GPP/NPP head (ADR 0332); "free" = the trunk's
# "local": south of the equator the day-of-year input is shifted by half a year (sin, cos -> -sin,
# -cos), so it measures each hemisphere's own season, as the original's annual resets do
# (COLDEST_DAY 14 north / 195 south, lat >= 0 north); ADR 0334
SEASON_PHASE = "calendar"
# ADR 0332 limiter inputs (columns of x): 0 tas 1 log-rain 2 rsds 3 lwnet 5/6 10/30-day tas
# 7 30-day rsds 8-10 30/90/365-day log-rain 11 day length 12/13 day of year 14 sin(lat)
# 15-18 stores 19 lai 20 log-vegc 21-30 cover by plant type
STAND_COLS = list(range(19, 31))
SEASON_COLS = [11, 12, 13, 14]
PHYS_COLS = {
    "fT": [0, 5, 6],
    "fW": [15, 16, 17, 18, 1, 8, 9, 10, 3],
    "fL": [2, 7] + SEASON_COLS,
    "fS": STAND_COLS,
    "Bw": STAND_COLS,
    "Br": STAND_COLS + SEASON_COLS,
}
K_LAMBERT = 0.5  # the original's layered-canopy light extinction (getfpar.c)
R_GROWTH = 0.25  # param_lpjmlfit.js "r_growth" (npp_tree.c:52)


# ----------------------------------------------------------------------------------------------
# features
# ----------------------------------------------------------------------------------------------
def trailing_mean(x, n):
    """Mean over the last n days including today, along axis 1 (x has >= n-1 warm-up days)."""
    c = np.cumsum(x, axis=1, dtype=np.float64)
    out = np.empty_like(c)
    out[:, n:] = c[:, n:] - c[:, :-n]
    out[:, :n] = c[:, :n]
    k = np.minimum(np.arange(1, x.shape[1] + 1), n)
    return (out / k).astype(np.float32)


def daylength(lat_deg, doy):
    """Hours of daylight; lat (ncell,), doy (nday,) -> (ncell, nday)."""
    decl = -0.4093 * np.cos(2 * np.pi * (doy + 10) / 365.0)
    t = -np.tan(np.radians(lat_deg))[:, None] * np.tan(decl)[None, :]
    return (24.0 / np.pi * np.arccos(np.clip(t, -1, 1))).astype(np.float32)


def forcing_features(forc, lat):
    """forc (nc, WARM+ND, 5) tas pr rsds lwnet huss -> (nc, ND, NFORC) for days 2020..2100."""
    tas, pr, rsds, lw, hu = (forc[:, :, i] for i in range(5))
    feats = [
        tas,
        np.log1p(pr),
        rsds,
        lw,
        hu * 1000.0,
        trailing_mean(tas, 10),
        trailing_mean(tas, 30),
        trailing_mean(rsds, 30),
        np.log1p(trailing_mean(pr, 30) * 30),
        np.log1p(trailing_mean(pr, 90) * 90),
        np.log1p(trailing_mean(pr, 365) * 365),
    ]
    out = np.stack([f[:, WARM:] for f in feats], -1)
    doy = np.tile(np.arange(1, 366), NY)
    dl = daylength(lat, doy)
    return np.concatenate([out, dl[:, :, None]], -1).astype(np.float32)


def calendar_features(lat):
    doy = np.tile(np.arange(1, 366), NY)
    a = 2 * np.pi * doy / 365.0
    return np.sin(a).astype(np.float32), np.cos(a).astype(np.float32), np.sin(np.radians(lat))


def stand_features(stand):
    """stand (nc, 82, 12) -> (nc, 82, 12): lai, log1p(vegc), fpc 1..10."""
    s = stand.copy()
    s[:, :, 1] = np.log1p(np.maximum(s[:, :, 1], 0))
    return s


def hemisphere_sign(slat):
    """+1, or -1 south of the equator under SEASON_PHASE == "local" (half a year = a sign flip)."""
    if SEASON_PHASE != "local":
        return np.ones_like(slat)
    return np.where(slat < 0, -1.0, 1.0).astype(np.float32)


def assemble(ff, sinA, cosA, slat, st, cap_prev, W, S, cells, days, co2=None):
    """Input matrix for (cells[i], days[i]) given yesterday's stores W, S (1-D, per row)."""
    iy = days // 365
    capv = cap_prev[cells, iy]
    hs = hemisphere_sign(slat[cells])
    x = np.empty((len(cells), NIN), dtype=np.float32)
    x[:, :NFORC] = ff[cells, days]
    x[:, NFORC] = sinA[days] * hs
    x[:, NFORC + 1] = cosA[days] * hs
    x[:, NFORC + 2] = slat[cells]
    x[:, NFORC + 3] = W / np.maximum(capv, 1.0)
    x[:, NFORC + 4] = W / 1000.0
    x[:, NFORC + 5] = np.log1p(S)
    x[:, NFORC + 6] = capv / 1000.0
    x[:, NFORC + 7 : NFORC + 19] = st[cells, iy]
    if CO2_INPUT:  # co2[k] = year 2019 + k; day d of year 2020 + iy reads the current year's value
        x[:, NFORC + 19] = co2[iy + 1] / 1000.0
    if DROP:
        x[:, DROP] = 0.0
    return x


class MemberLeg:
    """All arrays of one (member, leg), with features precomputed."""

    def __init__(self, k, leg, lat):
        tag = f"m{k}_{leg}"
        self.k, self.leg, self.tag = k, leg, tag
        self.daily = np.load(os.path.join(DATA, f"daily_{tag}.npy"))
        forc = np.load(os.path.join(DATA, f"forc_{tag}.npy"))
        self.ff = forcing_features(forc, lat)
        sp = os.path.join(DATA, f"stand_{tag}.npy")
        if STAND_DIR and os.path.exists(os.path.join(DATA, STAND_DIR, f"stand_{tag}.npy")):
            sp = os.path.join(DATA, STAND_DIR, f"stand_{tag}.npy")  # phase B: another stand (ADR 0331)
            print(f"{tag}: stand from {sp}", flush=True)
        self.st = stand_features(np.load(sp))
        self.cap = np.load(os.path.join(DATA, f"cap_{tag}.npy"))  # index iy = year 2019+iy
        # CO2 per year 2019..2100 (ADR 0342)
        self.co2 = np.load(os.path.join(DATA, f"co2_{tag}.npy")) if CO2_INPUT else None
        self.sinA, self.cosA, self.slat = calendar_features(lat)

    def targets(self, cells, days):
        d, p = self.daily, self.daily[cells, days - 1]
        t = d[cells, days]
        dS = t[:, SWE] - p[:, SWE]
        dW = t[:, RM] - p[:, RM]
        deep = t[:, PREC] - dS - t[:, INTERC] - t[:, TRANSP] - t[:, EVAP] - t[:, RUNOFF] - dW
        y = np.stack(
            [dS, t[:, INTERC], t[:, TRANSP], t[:, EVAP], t[:, RUNOFF], deep, t[:, GPP], t[:, NPP]],
            -1,
        )
        return y.astype(np.float32), t[:, PREC], p[:, SWE], p[:, RM]

    def inputs_teacher(self, cells, days):
        p = self.daily[cells, days - 1]
        return assemble(
            self.ff,
            self.sinA,
            self.cosA,
            self.slat,
            self.st,
            self.cap,
            p[:, RM],
            p[:, SWE],
            cells,
            days,
            co2=self.co2,
        )


# ----------------------------------------------------------------------------------------------
# model
# ----------------------------------------------------------------------------------------------
class Net(nn.Module):
    def __init__(self, mu, sd, ysd, nh=64, nl=2):
        super().__init__()
        self.register_buffer("mu", torch.as_tensor(mu))
        self.register_buffer("sd", torch.as_tensor(sd))
        self.register_buffer("ysd", torch.as_tensor(ysd))
        layers, n = [], NIN
        for _ in range(nl):
            layers += [nn.Linear(n, nh), nn.SiLU()]
            n = nh
        self.trunk = nn.Sequential(*layers, nn.Linear(n, 9))
        self.npp_ra = NPP_HEAD == "ra"
        self.phys = CARBON_HEAD == "physical"
        if self.phys:  # ADR 0332: each limiter / biomass term a small network of its own inputs
            self.sub = nn.ModuleDict(
                {
                    k: nn.Sequential(
                        nn.Linear(len(c), 64),
                        nn.SiLU(),
                        nn.Linear(64, 64),
                        nn.SiLU(),
                        nn.Linear(64, 1),
                    )
                    for k, c in PHYS_COLS.items()
                }
            )
            self.log_eps = nn.Parameter(torch.zeros(()))  # set from the data in train()
            # leaf dark respiration share 0.3 * sigmoid(p_cd), starts at 0.1; the root term's
            # temperature is a blend sigmoid(p_mix) of today's and the 30-day air temperature
            self.p_cd = nn.Parameter(torch.tensor(-0.693))
            self.p_mix = nn.Parameter(torch.zeros(()))

    def carbon(self, x, xn):
        """ADR 0332: GPP = eps * rsds * (1 - exp(-k LAI)) * fT fW fL fS; NPP as npp_tree.c:52."""
        sub = {k: self.sub[k](xn[:, c]).squeeze(1) for k, c in PHYS_COLS.items()}
        sig, sp = torch.sigmoid, nn.functional.softplus
        rsds = torch.clamp(x[:, 2], min=0.0) / 100.0
        fapar = 1.0 - torch.exp(-K_LAMBERT * torch.clamp(x[:, 19], min=0.0))
        lim = sig(sub["fT"]) * sig(sub["fW"]) * sig(sub["fL"]) * sig(sub["fS"])
        gpp = torch.exp(self.log_eps) * rsds * fapar * lim

        def g(t):  # temp_response.c:33
            tc = torch.clamp(t, min=-40.0)
            return torch.where(
                t >= -40.0, torch.exp(308.56 * (1.0 / 56.02 - 1.0 / (tc + 46.02))), 0.0 * t
            )

        w = sig(self.p_mix)
        t_root = w * x[:, 0] + (1 - w) * x[:, 6]
        rm = self.ysd[7] * (sp(sub["Bw"]) * g(x[:, 0]) + sp(sub["Br"]) * g(t_root))
        a = (1.0 - 0.3 * sig(self.p_cd)) * gpp - rm
        return gpp, a - R_GROWTH * torch.relu(a)

    def forward(self, x, prec, S_prev):
        xn = (x - self.mu) / self.sd
        o = self.trunk(xn)
        sp = nn.functional.softplus
        f, m, i = torch.sigmoid(o[:, 0]), torch.sigmoid(o[:, 1]), torch.sigmoid(o[:, 2])
        ys = self.ysd
        if self.phys:
            gpp, npp = self.carbon(x, xn)
        else:
            gpp = sp(o[:, 7]) * ys[6]
            npp = gpp - sp(o[:, 8]) * ys[7] if self.npp_ra else o[:, 8] * ys[7]
        return torch.stack(
            [
                prec * f - m * S_prev,
                prec * i,
                sp(o[:, 3]) * ys[2],
                sp(o[:, 4]) * ys[3],
                sp(o[:, 5]) * ys[4],
                o[:, 6] * ys[5],
                gpp,
                npp,
            ],
            -1,
        )


class Ensemble(nn.Module):
    """ADR 0322 arm A2E: the mean of several networks' daily outputs (same inputs, one bucket)."""

    def __init__(self, nets):
        super().__init__()
        self.nets = nn.ModuleList(nets)

    def forward(self, x, prec, S_prev):
        return torch.stack([n(x, prec, S_prev) for n in self.nets]).mean(0)


def load_net(path, dev):
    ck = torch.load(path, map_location=dev, weights_only=True)
    return Net(*(ck[k].cpu().numpy() for k in ("mu", "sd", "ysd")), NH, NL).to(dev), ck


def bucket_step(y, prec, W, S, D, cap):
    """Apply the closed bucket (y columns = TARGETS). Returns new W, S, D, corrected fluxes."""
    dS, interc, transp, evap, runoff, deep = (y[:, j] for j in range(6))
    S2 = S + dS
    W2 = W + prec - dS - interc - transp - evap - runoff - deep
    over = np.maximum(W2 - cap, 0.0)
    under = np.maximum(-W2, 0.0)
    W2 = W2 - over + under
    runoff = runoff + over
    deep = deep - under
    D2 = D + deep
    if DEEP_TAU > 0:
        release = D2 / DEEP_TAU
        D2 = D2 - release
        runoff = runoff + release
    return W2, S2, D2, runoff, deep, over, under


# ----------------------------------------------------------------------------------------------
def split_cells(cells_df):
    ho = cells_df["heldout"].to_numpy()
    if ALL_CELLS:
        ho = np.zeros_like(ho)
    blocks = cells_df["block"].to_numpy()
    train_blocks = sorted(set(blocks[~ho].tolist()))
    val_blocks = set(train_blocks[3::10])  # 10 % of training blocks, never a held-out one
    val = np.isin(blocks, list(val_blocks))
    return np.where(~ho & ~val)[0], np.where(val)[0], np.where(ho)[0]


def sample_rows(ml, cell_idx, n, rng):
    cells = rng.choice(cell_idx, n)
    days = rng.integers(1, ND, n)
    x = ml.inputs_teacher(cells, days)
    y, prec, S_prev, _ = ml.targets(cells, days)
    return x, y, prec, S_prev


def train(args, mls, tr, va, dev, log):
    rng = np.random.default_rng(args.seed)
    per = args.nsamp // len(mls)
    parts, vparts = [], []
    for ml in mls:
        parts.append(sample_rows(ml, tr, per, rng))
        vparts.append(sample_rows(ml, va, max(per // 10, 1000), rng))
    X, Y, P, S = (np.concatenate([p[i] for p in parts]) for i in range(4))
    Xv, Yv, Pv, Sv = (np.concatenate([p[i] for p in vparts]) for i in range(4))
    mu, sd = X.mean(0), X.std(0) + 1e-6
    ysd = Y.std(0) + 1e-6
    log(f"train rows {len(X):,}  val rows {len(Xv):,}  target sd {np.round(ysd, 3).tolist()}")
    net = Net(
        mu.astype(np.float32),
        sd.astype(np.float32),
        ysd.astype(np.float32),
        args.hidden,
        args.layers,
    ).to(dev)
    if net.phys:  # start the light-use efficiency where four limiters at 0.5 give the mean GPP
        lai = np.clip(X[:, 19], 0, None)
        apar = np.clip(X[:, 2], 0, None) / 100.0 * (1.0 - np.exp(-K_LAMBERT * lai))
        eps0 = float(Y[:, 6].mean() / max(apar.mean(), 1e-9) * 16.0)
        net.log_eps.data.fill_(math.log(eps0))
        log(f"physical carbon head: eps0 {eps0:.4g}")
    tX, tY, tP, tS = (torch.as_tensor(a, device=dev) for a in (X, Y, P, S))
    vX, vY, vP, vS = (torch.as_tensor(a, device=dev) for a in (Xv, Yv, Pv, Sv))
    w = 1.0 / torch.as_tensor(ysd, device=dev) ** 2
    opt = torch.optim.Adam(net.parameters(), lr=args.lr)
    nb = math.ceil(len(X) / args.batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, args.lr, total_steps=args.epochs * nb)
    best, best_state, bad = float("inf"), None, 0
    for ep in range(args.epochs):
        t0 = time.time()
        perm = torch.randperm(len(X), device=dev)
        net.train()
        tot = 0.0
        for b in range(nb):
            ix = perm[b * args.batch : (b + 1) * args.batch]
            pred = net(tX[ix], tP[ix], tS[ix])
            loss = (((pred - tY[ix]) ** 2) * w).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            tot += loss.item()
        net.eval()
        with torch.no_grad():
            vl = 0.0
            per_t = torch.zeros(len(TARGETS), device=dev)
            for b in range(0, len(Xv), 262144):
                pv = net(vX[b : b + 262144], vP[b : b + 262144], vS[b : b + 262144])
                e = ((pv - vY[b : b + 262144]) ** 2) * w
                per_t += e.sum(0)
                vl += e.mean(1).sum().item()
            vl /= len(Xv)
            per_t = (per_t / len(Xv)).cpu().numpy()
        log(
            f"epoch {ep}: train {tot / nb:.4f} val {vl:.4f} per-target "
            f"{dict(zip(TARGETS, np.round(per_t, 4).tolist(), strict=True))} "
            f"{time.time() - t0:.0f}s"
        )
        if vl < best - 1e-5:
            best, bad = vl, 0
            best_state = {k: v.detach().clone() for k, v in net.state_dict().items()}
        else:
            bad += 1
            if args.patience and bad >= args.patience:  # 0 = never stop (ADR 0336)
                break
    net.load_state_dict(best_state)
    return net


# ----------------------------------------------------------------------------------------------
# rollouts
# ----------------------------------------------------------------------------------------------
@torch.no_grad()
def predict(net, x, prec, S, dev):
    return (
        net(
            torch.as_tensor(x, device=dev),
            torch.as_tensor(prec, device=dev),
            torch.as_tensor(S, device=dev),
        )
        .cpu()
        .numpy()
    )


def annualise(daily_cols):
    """dict name -> (nc, ND) daily -> (nc, NY) annual sums."""
    return {k: v.reshape(v.shape[0], NY, 365).sum(-1) for k, v in daily_cols.items()}


def run_free(net, ml, dev):
    nc = ml.daily.shape[0]
    cells = np.arange(nc)
    W = ml.daily[:, 0, RM].astype(np.float64)
    S = ml.daily[:, 0, SWE].astype(np.float64)
    D = np.zeros(nc)
    out = {k: np.zeros((nc, ND), np.float32) for k in ("gpp", "et", "npp", "runoff", "W")}
    over_t = np.zeros((nc, NY))
    under_t = np.zeros((nc, NY))
    for d in range(1, ND):
        days = np.full(nc, d)
        x = assemble(
            ml.ff, ml.sinA, ml.cosA, ml.slat, ml.st, ml.cap, W.astype(np.float32),
            S.astype(np.float32), cells, days, co2=ml.co2,
        )  # fmt: skip
        prec = ml.daily[:, d, PREC].astype(np.float32)
        y = predict(net, x, prec, S.astype(np.float32), dev).astype(np.float64)
        cap = ml.cap[:, d // 365].astype(np.float64)
        W, S, D, runoff, _deep, over, under = bucket_step(y, prec, W, S, D, cap)
        out["gpp"][:, d] = y[:, 6]
        out["npp"][:, d] = y[:, 7]
        out["et"][:, d] = y[:, 1] + y[:, 2] + y[:, 3]
        out["runoff"][:, d] = runoff
        out["W"][:, d] = W
        over_t[:, d // 365] += over
        under_t[:, d // 365] += under
    # day 0 (Jan 1 2020) is the initial state; copy truth so year 2020 is complete (never scored)
    t0 = ml.daily[:, 0]
    out["gpp"][:, 0], out["npp"][:, 0] = t0[:, GPP], t0[:, NPP]
    out["et"][:, 0] = t0[:, INTERC] + t0[:, TRANSP] + t0[:, EVAP]
    out["runoff"][:, 0] = t0[:, RUNOFF]
    w_err = np.abs(out["W"][:, 1:] - ml.daily[:, 1:, RM]).mean(1)
    t = ml.daily
    d_true = (  # the original's deep-store change over the run, by water balance
        t[:, 1:, PREC].sum(1, dtype=np.float64)
        - t[:, 1:, [INTERC, TRANSP, EVAP, RUNOFF]].sum((1, 2), dtype=np.float64)
        - (t[:, -1, SWE] - t[:, 0, SWE]) - (t[:, -1, RM] - t[:, 0, RM])
    )  # fmt: skip
    ann = annualise({k: out[k] for k in ANNUAL})
    return ann, {"over": over_t, "under": under_t, "D_end": D, "D_true": d_true, "W_mae": w_err,
                 "runoff_min": float(out["runoff"][:, 1:].min())}  # fmt: skip


def run_onestep(net, ml, dev):
    nc = ml.daily.shape[0]
    out = {k: np.zeros((nc, ND), np.float32) for k in ANNUAL}
    t0 = ml.daily[:, 0]
    out["gpp"][:, 0], out["npp"][:, 0] = t0[:, GPP], t0[:, NPP]
    out["et"][:, 0] = t0[:, INTERC] + t0[:, TRANSP] + t0[:, EVAP]
    out["runoff"][:, 0] = t0[:, RUNOFF]
    for c0 in range(0, nc, 50):
        cs = np.arange(c0, min(c0 + 50, nc))
        cells = np.repeat(cs, ND - 1)
        days = np.tile(np.arange(1, ND), len(cs))
        x = ml.inputs_teacher(cells, days)
        _, prec, S_prev, _ = ml.targets(cells, days)
        y = predict(net, x, prec, S_prev, dev)
        y = y.reshape(len(cs), ND - 1, len(TARGETS))
        out["gpp"][cs, 1:] = y[:, :, 6]
        out["npp"][cs, 1:] = y[:, :, 7]
        out["et"][cs, 1:] = y[:, :, 1] + y[:, :, 2] + y[:, :, 3]
        out["runoff"][cs, 1:] = y[:, :, 4]
    return annualise(out)


def truth_annual(ml):
    d = ml.daily
    return annualise(
        {
            "gpp": d[:, :, GPP],
            "et": d[:, :, INTERC] + d[:, :, TRANSP] + d[:, :, EVAP],
            "npp": d[:, :, NPP],
            "runoff": d[:, :, RUNOFF],
        }
    )


def bench_speed(net, ml, reps=3):
    """S1: one core, batch = all panel cells, incremental trailing windows, network + bucket."""
    torch.set_num_threads(1)
    netc = copy.deepcopy(net).cpu().eval()
    nc = ml.daily.shape[0]
    forc = np.load(os.path.join(DATA, f"forc_{ml.tag}.npy"))
    lat_s = ml.slat
    hs = hemisphere_sign(lat_s)
    times = []
    for _ in range(reps):
        buf = {n: np.array(forc[:, WARM - n : WARM, j]) for n, j in ((10, 0), (30, 0), (30, 2))}
        pbuf = np.array(forc[:, :WARM, 1])
        sums = {
            "t10": buf[10].sum(1), "t30": forc[:, WARM - 30 : WARM, 0].sum(1),
            "r30": forc[:, WARM - 30 : WARM, 2].sum(1), "p30": pbuf[:, -30:].sum(1),
            "p90": pbuf[:, -90:].sum(1), "p365": pbuf.sum(1),
        }  # fmt: skip
        t10b = forc[:, WARM - 10 : WARM, 0].copy()
        t30b = forc[:, WARM - 30 : WARM, 0].copy()
        r30b = forc[:, WARM - 30 : WARM, 2].copy()
        W = ml.daily[:, 0, RM].astype(np.float32)
        S = ml.daily[:, 0, SWE].astype(np.float32)
        D = np.zeros(nc, np.float32)
        st = ml.st[:, 1]
        cap = ml.cap[:, 1]
        x = np.empty((nc, NIN), np.float32)
        t0 = time.perf_counter()
        with torch.no_grad():
            for d in range(365):
                f = forc[:, WARM + d]
                tas, pr = f[:, 0], f[:, 1]
                i10, i30, i365 = d % 10, d % 30, d % 365
                sums["t10"] += tas - t10b[:, i10]
                t10b[:, i10] = tas
                sums["t30"] += tas - t30b[:, i30]
                t30b[:, i30] = tas
                sums["r30"] += f[:, 2] - r30b[:, i30]
                r30b[:, i30] = f[:, 2]
                old = pbuf[:, i365]
                sums["p365"] += pr - old
                sums["p90"] += pr - pbuf[:, (i365 - 90) % 365]
                sums["p30"] += pr - pbuf[:, (i365 - 30) % 365]
                pbuf[:, i365] = pr
                x[:, 0], x[:, 1], x[:, 2], x[:, 3], x[:, 4] = (
                    tas,
                    np.log1p(pr),
                    f[:, 2],
                    f[:, 3],
                    f[:, 4],
                )
                x[:, 5], x[:, 6], x[:, 7] = sums["t10"] / 10, sums["t30"] / 30, sums["r30"] / 30
                x[:, 8], x[:, 9] = np.log1p(sums["p30"]), np.log1p(sums["p90"])
                x[:, 10] = np.log1p(sums["p365"])
                x[:, 11] = ml.ff[:, d, 11]  # day length: a per-cell table in deployment
                x[:, NFORC], x[:, NFORC + 1] = ml.sinA[d] * hs, ml.cosA[d] * hs
                x[:, NFORC + 2] = lat_s
                x[:, NFORC + 3] = W / np.maximum(cap, 1.0)
                x[:, NFORC + 4] = W / 1000.0
                x[:, NFORC + 5] = np.log1p(S)
                x[:, NFORC + 6] = cap / 1000.0
                x[:, NFORC + 7 : NFORC + 19] = st
                if CO2_INPUT:
                    x[:, NFORC + 19] = ml.co2[1] / 1000.0
                if DROP:
                    x[:, DROP] = 0.0
                y = netc(torch.from_numpy(x), torch.from_numpy(pr), torch.from_numpy(S)).numpy()
                W, S, D, *_ = bucket_step(y, pr, W, S, D, cap)
        times.append((time.perf_counter() - t0) / nc)
    torch.set_num_threads(os.cpu_count() or 1)
    return float(np.median(times))


# ----------------------------------------------------------------------------------------------
# scoring (ADR 0320 section 5)
# ----------------------------------------------------------------------------------------------
def score(ann, cells_df):
    """ann[(kind, leg)] -> (4 members, nc, NY, 4 vars). Returns the summary dict."""
    ho = cells_df["heldout"].to_numpy()
    lat = cells_df["lat"].to_numpy()
    biome = cells_df["biome"].to_numpy()
    # the biome cell itself, not its whole block
    biome_cell = {
        "tropical_amazon": 12045, "semiarid_sahel": 18371, "mediterranean_iberia": 33335,
        "temperate_hainich": 42490, "boreal_siberia": 52059,
    }  # fmt: skip
    cellid = cells_df["Cell"].to_numpy()
    bidx = {b: int(np.where(cellid == c)[0][0]) for b, c in biome_cell.items()}
    assert all(biome[i] == b for b, i in bidx.items())
    sl = slice(1, NY)  # 2021..2100
    early, late = slice(1, 31), slice(51, 81)  # 2021-2050, 2071-2100
    wts = np.cos(np.radians(lat))
    V = {v: j for j, v in enumerate(ANNUAL)}
    S = {"L1": {}, "L2": {}, "L3": {}, "R1": {}, "reports": {}}

    def cellmean(a):  # (4, nc, NY, nv) -> (nc, nv) 4-member mean of the 2021-2100 mean
        return a[:, :, sl].mean(2).mean(0)

    for kind in ("free", "onestep", "clim"):
        for leg in ALL_LEGS:
            t, e = ann[("truth", leg)], ann[(kind, leg)]
            tm, em = cellmean(t), cellmean(e)
            rel = em / np.where(np.abs(tm) > 1e-9, tm, np.nan) - 1
            spread = (t[:, :, sl].mean(2).std(0, ddof=1)) / np.abs(tm)
            mask = ho & (tm[:, V["gpp"]] >= 50)
            for v in ("gpp", "et", "npp"):
                j = V[v]
                S["L2"][f"{kind}|{leg}|{v}"] = {
                    "median_abs_rel_err": float(np.nanmedian(np.abs(rel[mask, j]))),
                    "n_cells": int(mask.sum()),
                    "member_spread_median": float(np.nanmedian(spread[mask, j])),
                }
                tot = float((wts[ho] * tm[ho, j]).sum())
                S["L3"][f"{kind}|{leg}|{v}"] = {
                    "rel_err_total": float((wts[ho] * em[ho, j]).sum() / tot - 1),
                }
                if leg == "mpi-esm1-2-hr_ssp370":
                    S["L1"][f"{kind}|{v}"] = {
                        b: {
                            "rel_err": float(rel[i, j]),
                            "member_spread": float(spread[i, j]),
                        }
                        for b, i in bidx.items()
                    }
            # response
            dT = t[:, :, late].mean(2) - t[:, :, early].mean(2)  # (4, nc, nv)
            dE = (e[:, :, late].mean(2) - e[:, :, early].mean(2)).mean(0)
            j = V["gpp"]
            S["R1"][f"{kind}|{leg}"] = {
                b: {
                    "emu": float(dE[i, j]),
                    "orig_min": float(dT[:, i, j].min()),
                    "orig_max": float(dT[:, i, j].max()),
                    "inside": bool(dT[:, i, j].min() <= dE[i, j] <= dT[:, i, j].max()),
                    "band_excludes_zero": bool(dT[:, i, j].min() > 0 or dT[:, i, j].max() < 0),
                }
                for b, i in bidx.items()
            }
            # per-cell response agreement (ADR 0321 section 3.1: a ratio of net area sums is
            # ill-conditioned here because tropical losses cancel boreal gains)
            if kind != "clim":
                mk = ho & (cellmean(t)[:, j] >= 50)
                x, yv = dT[:, mk, j].mean(0), dE[mk, j]
                S["reports"][f"response_per_cell|{kind}|{leg}|gpp"] = {
                    "r": float(np.corrcoef(x, yv)[0, 1]),
                    "slope": float(np.polyfit(x, yv, 1)[0]),
                    "rmse": float(np.sqrt(np.mean((yv - x) ** 2))),
                    "member_se_median": float(np.median(dT[:, mk, j].std(0, ddof=1) / 2)),
                    "net_over_abs": float((wts[mk] * x).sum() / (wts[mk] * np.abs(x)).sum()),
                }
    # pass flags (free run only)
    f = "free"
    l1 = all(
        sum(abs(S["L1"][f"{f}|{v}"][b]["rel_err"]) <= 0.05 for b in bidx) >= 4
        for v in ("gpp", "et", "npp")
    )
    l2 = all(
        S["L2"][f"{f}|{leg}|{v}"]["median_abs_rel_err"] <= 0.05
        for leg in ALL_LEGS
        for v in ("gpp", "et", "npp")
    )
    l3 = all(
        abs(S["L3"][f"{f}|{leg}|{v}"]["rel_err_total"]) <= 0.05
        for leg in ALL_LEGS
        for v in ("gpp", "et", "npp")
    )
    r1 = sum(S["R1"][f"{f}|mpi-esm1-2-hr_ssp370"][b]["inside"] for b in bidx) >= 4
    S["pass"] = {"L1": l1, "L2": l2, "L3": l3, "R1": r1}
    return S


def to_markdown(S, s1):
    L = ["| statistic | leg | var | free run | one-step | climatology null | original's spread |"]
    L.append("|---|---|---|---|---|---|---|")
    for leg in ALL_LEGS:
        for v in ("gpp", "et", "npp"):
            r = [
                S["L2"][f"{k}|{leg}|{v}"]["median_abs_rel_err"] for k in ("free", "onestep", "clim")
            ]
            sp = S["L2"][f"free|{leg}|{v}"]["member_spread_median"]
            L.append(f"| L2 median abs rel err | {leg} | {v} | " + " | ".join(f"{x:.3f}" for x in r)
                     + f" | {sp:.3f} |")  # fmt: skip
    for leg in ALL_LEGS:
        for v in ("gpp", "et", "npp"):
            r = [S["L3"][f"{k}|{leg}|{v}"]["rel_err_total"] for k in ("free", "onestep", "clim")]
            L.append(
                f"| L3 total rel err | {leg} | {v} | " + " | ".join(f"{x:+.3f}" for x in r) + " | |"
            )
    L.append("")
    L.append("| L1 biome cell, mpi ssp370 | var | free | one-step | clim | spread |")
    L.append("|---|---|---|---|---|---|")
    for v in ("gpp", "et", "npp"):
        for b, rr in S["L1"][f"free|{v}"].items():
            o = S["L1"][f"onestep|{v}"][b]["rel_err"]
            c = S["L1"][f"clim|{v}"][b]["rel_err"]
            L.append(
                f"| {b} | {v} | {rr['rel_err']:+.3f} | {o:+.3f} | {c:+.3f} | "
                f"{rr['member_spread']:.3f} |"
            )
    L.append("")
    L.append(
        "| R1 GPP change (2071-2100 minus 2021-2050) | leg | emulator | original min..max "
        "| inside | band excludes 0 |"
    )
    L.append("|---|---|---|---|---|---|")
    for leg in ALL_LEGS:
        for b, r in S["R1"][f"free|{leg}"].items():
            band = f"{r['orig_min']:+.1f} .. {r['orig_max']:+.1f}"
            L.append(
                f"| {b} | {leg} | {r['emu']:+.1f} | {band} | {r['inside']} | "
                f"{r['band_excludes_zero']} |"
            )
    L.append("")
    L.append(f"S1 cost: {s1:.2e} core-s per cell-year (bar 0.01)")
    L.append(f"pass flags: {S['pass']}")
    return "\n".join(L)


def main():
    global NH, NL, NPP_HEAD, DEEP_TAU, STAND_DIR, CARBON_HEAD, SEASON_PHASE
    global DATA, CO2_INPUT, NIN, ALL_CELLS
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="A")
    ap.add_argument("--nsamp", type=int, default=40_000_000)
    ap.add_argument("--epochs", type=int, default=10)
    # 0 = train every epoch: the one-cycle schedule spans all epochs, and stopping on a mid-cycle
    # validation bump (old default 2) kept un-annealed members in 7 ensembles (ADR 0336)
    ap.add_argument("--patience", type=int, default=0)
    ap.add_argument("--batch", type=int, default=16384)
    ap.add_argument("--lr", type=float, default=3e-3)
    ap.add_argument("--hidden", type=int, default=64)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--npp-head", dest="npp_head", choices=["direct", "ra"], default="direct")
    ap.add_argument(
        "--ensemble", default="", help="comma-separated run tags to average (no training)"
    )
    ap.add_argument("--layers", type=int, default=2)
    ap.add_argument("--drop-inputs", dest="drop_inputs", default="",
                    help="raw forcing inputs to remove, e.g. huss (ADR 0327)")  # fmt: skip
    ap.add_argument("--train-legs", dest="train_legs", default=",".join(TRAIN_LEGS))
    ap.add_argument("--test-legs", dest="test_legs", default=",".join(TEST_LEGS),
                    help="legs only free-run and scored (ADR 0328); "
                    "none = hold none out (ADR 0335)")  # fmt: skip
    ap.add_argument("--train-only", dest="train_only", action="store_true",
                    help="save model.pt and stop (ensemble members; no free runs)")  # fmt: skip
    ap.add_argument("--deep-tau", dest="deep_tau", type=float, default=0.0,
                    help="days; > 0 drains the deep store into runoff (ADR 0326)")  # fmt: skip
    ap.add_argument("--stand-dir", dest="stand_dir", default="",
                    help="subdir of DATA whose stand_<tag>.npy replace the original's (phase B, ADR 0331)")  # fmt: skip
    ap.add_argument("--carbon-head", dest="carbon_head", default="free",
                    choices=["free", "physical"], help="structured GPP/NPP, ADR 0332")  # fmt: skip
    ap.add_argument("--season-phase", dest="season_phase", choices=["calendar", "local"],
                    default="calendar", help="local: hemisphere-local day of year, ADR 0334")  # fmt: skip
    ap.add_argument("--data-dir", dest="data_dir", default=DATA,
                    help="array directory (ADR 0342: f2_non)")  # fmt: skip
    ap.add_argument("--members", default=",".join(map(str, MEMBERS)),
                    help="runs of the original, e.g. 2")  # fmt: skip
    ap.add_argument("--co2", action="store_true",
                    help="the year's CO2 as an input (ADR 0342; co2_<tag>.npy)")  # fmt: skip
    ap.add_argument("--all-cells", dest="all_cells", action="store_true",
                    help="no held-out cells: a deployment model (ADR 0344)")  # fmt: skip
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    a = ap.parse_args()
    DATA, CO2_INPUT, ALL_CELLS = a.data_dir, a.co2, a.all_cells
    MEMBERS[:] = [int(k) for k in a.members.split(",")]
    if CO2_INPUT:
        NIN = NFORC + 3 + 4 + 12 + 1
    NH, NL, NPP_HEAD, DEEP_TAU, STAND_DIR = a.hidden, a.layers, a.npp_head, a.deep_tau, a.stand_dir
    CARBON_HEAD, SEASON_PHASE = a.carbon_head, a.season_phase
    DROP[:] = [FEAT[v] for v in a.drop_inputs.split(",") if v]
    TRAIN_LEGS[:] = a.train_legs.split(",")
    TEST_LEGS[:] = [x for x in a.test_legs.split(",") if x and x != "none"]
    ALL_LEGS[:] = TRAIN_LEGS + TEST_LEGS
    out = os.path.join(DATA, "runs", a.tag)
    os.makedirs(out, exist_ok=True)
    logf = open(os.path.join(out, "log.txt"), "a")

    def log(msg):
        print(msg, flush=True)
        logf.write(msg + "\n")
        logf.flush()

    json.dump({"train": TRAIN_LEGS, "test": TEST_LEGS}, open(os.path.join(out, "legs.json"), "w"))
    torch.manual_seed(a.seed)
    dev = torch.device(a.device)
    log(f"== f2_train tag={a.tag} device={dev} args={vars(a)}")
    cells_df = pl.read_parquet(os.path.join(DATA, "cells.parquet"))
    lat = cells_df["lat"].to_numpy().astype(np.float32)
    tr, va, te = split_cells(cells_df)
    log(f"cells: train {len(tr)} val {len(va)} held-out {len(te)}")

    mpath = os.path.join(out, "model.pt")
    if a.ensemble:
        nets = []
        for t in a.ensemble.split(","):
            n, ck = load_net(os.path.join(DATA, "runs", t, "model.pt"), dev)
            n.load_state_dict(ck)
            nets.append(n.eval())
        net = Ensemble(nets).to(dev)
        log(f"ensemble of {len(nets)}: {a.ensemble}")
    elif os.path.exists(mpath):
        net, ck = load_net(mpath, dev)
        net.load_state_dict(ck)
        log("loaded existing model")
    else:
        mls = [MemberLeg(k, leg, lat) for leg in TRAIN_LEGS for k in MEMBERS]
        net = train(a, mls, tr, va, dev, log)
        torch.save(net.state_dict(), mpath)
        del mls
    if a.train_only:
        log("== DONE (train only)")
        return
    net.eval()

    ann, diag = {}, {}
    for leg in ALL_LEGS:
        acc = {k: [] for k in ("truth", "free", "onestep", "clim")}
        for k in MEMBERS:
            t0 = time.time()
            ml = MemberLeg(k, leg, lat)
            tr_a = truth_annual(ml)
            fr_a, dg = run_free(net, ml, dev)
            os_a = run_onestep(net, ml, dev)
            ctl = MemberLeg(k, "ctl_obs", lat) if leg != "ctl_obs" else ml
            ctl_a = truth_annual(ctl)
            clim = {v: np.repeat(ctl_a[v][:, 1:].mean(1, keepdims=True), NY, 1) for v in ANNUAL}
            for kind, d in (("truth", tr_a), ("free", fr_a), ("onestep", os_a), ("clim", clim)):
                acc[kind].append(np.stack([d[v] for v in ANNUAL], -1))
            diag[f"m{k}|{leg}"] = {
                "overflow_mm_per_yr_median": float(np.median(dg["over"][:, 1:].mean(1))),
                "deficit_mm_per_yr_median": float(np.median(dg["under"][:, 1:].mean(1))),
                "deficit_mm_per_yr_max": float(dg["under"][:, 1:].mean(1).max()),
                "D_end_abs_median_mm": float(np.median(np.abs(dg["D_end"]))),
                "D_true_abs_median_mm": float(np.median(np.abs(dg["D_true"]))),
                "D_end_abs_p90_mm": float(np.quantile(np.abs(dg["D_end"]), 0.9)),
                "D_true_abs_p90_mm": float(np.quantile(np.abs(dg["D_true"]), 0.9)),
                "runoff_daily_min_mm": dg["runoff_min"],
                "W_mae_median_mm": float(np.median(dg["W_mae"])),
            }
            log(
                f"{ml.tag}: free run + one-step done {time.time() - t0:.0f}s  {diag[f'm{k}|{leg}']}"
            )
            del ml, ctl
        for kind in acc:
            ann[(kind, leg)] = np.stack(acc[kind])
    np.savez_compressed(
        os.path.join(out, "annual.npz"), **{f"{k}__{leg}": v for (k, leg), v in ann.items()}
    )
    S = score(ann, cells_df)
    s1 = bench_speed(net, MemberLeg(1, "mpi-esm1-2-hr_ssp370", lat))
    S["S1_core_s_per_cell_year"] = s1
    S["pass"]["S1"] = s1 <= 0.01
    S["pass"]["ALL"] = all(S["pass"].values())
    S["bucket_diagnostics"] = diag
    json.dump(S, open(os.path.join(out, "summary.json"), "w"), indent=1)
    md = to_markdown(S, s1)
    open(os.path.join(out, "summary.md"), "w").write(md)
    log(md)
    log("== DONE")


if __name__ == "__main__":
    main()
