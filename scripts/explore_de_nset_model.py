#!/usr/bin/env python3
"""explore_de_nset_model.py — LINE X, Germany data-driven emulator, track D-NSET item D1: THE NEURAL
SET MODEL.

A permutation-invariant model over each patch's trees (token MLP + pre-norm set-transformer blocks
with key-padding
masks and FiLM conditioning), a patch-level LSTM memory, and a cell climate encoder (GRU over the
previous 20 years +
y + y+1 annual climate, soil-code embedding, own-GCM 1985-2014 climatology). No lat/lon, no cell id,
no CO2, no wind.

HEADS (one step y -> y+1; everything teacher-forced in stage 1)
  G     P(G_{y+1} < 0) (Bernoulli) + a 2-component Gaussian mixture on log|G| per sign. The counter
  c_{y+1} is NOT
        learned: SH2 counter_step(c_y, G_{y+1}, Age_y).
  grow  heteroscedastic diagonal Gaussian on the standardised next-year state vector GROW_T (dln
  Height, dln agb,
        dln vegc, LAI, dln fpc, dD95, npp, transp, wscal_mean, log1p W), conditioned on G_{y+1} and
        c_{y+1}; mean =
        f(e) + B(e) dz with B rank 4 on 8 standardised climate anomalies of y+1 (auditable
        extrapolation)
  death demographic logit = logit(clip(rule hazard, 1e-6, 1-1e-6)) + g(e) (g zero-initialised); p =
  1 where
        c_{y+1} >= 5 or the hazard >= 1 (hard kill); N-free arm: no offset. Fire: patch fraction
        f = 0.001 + 0.999 sigmoid(MLP) (floor 0.001), per-tree kill s_Type f with s_Type learned
        from 1 - resist;
        p_die = 1 - (1 - p_dem)(1 - s f). Plus P(drops below the 5 m print cut) per tree.
  rcount NB (mean, dispersion) per patch of new living printed stems at y+1 (recruits + re-entries)
  rtype categorical over the 7 tree PFTs per new stem
  rtrait 4 sampled axes (ln SLA, ln Wooddens, ln D95max, minwscal; standardised per Type): mixture
  of COPY (attention
        over the patch's same-Type living stems, Gaussian diffusion with learned per-Type sd) and an
        8-component
        background Gaussian mixture; Longevity and beta_root follow from the SH2 rules
  entry Height - 5 ~ Gamma, ln Age ~ 2-component mixture, then a diagonal Gaussian on ENTRY_T given
  (Height, Age);
        counter c categorical 0-4
  grass P(LAI_{y+1} < 1e-3) + Gaussian on ln LAI_{y+1} (grass is one number per patch: agb = 23.673
  LAI exactly,
        cover = 1 - exp(-0.5 LAI) unless capped by tree cover)

`python explore_de_nset_model.py check` runs the D1 unit checks (u1-u6, see _status/D.md) and writes
_reports/r2_D1.json.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
NTYPE = 7
NC = 5  # counter classes 0..4 for a living tree
GRASS_K = 23.673
LAI_ZERO = 1e-3
TRAIT4 = ["SLA", "Wooddens", "D95max", "minwscal"]
TRAIT_LOG = [True, True, True, False]
# token raw columns (SH11 tok columns; Type first) and the derived token feature list
TOK_RAW = [
    "Type",
    "SLA",
    "Wooddens",
    "D95max",
    "minwscal",
    "Longevity",
    "beta_root",
    "Height",
    "agb",
    "vegc",
    "LAI",
    "fpc_ind",
    "D95",
    "Age",
    "c_y",
    "G_y",
    "npp",
    "transp",
    "wscal_mean",
    "W_y",
    "height_rank",
    "is_reentry_y",
    "n_live",
]
TOK_FEAT = [
    "lSLA",
    "lWD",
    "lD95max",
    "minwscal",
    "lLongevity",
    "beta_root",  # 6 traits, standardised per Type
    "Height",
    "lagb",
    "lvegc",
    "LAI",
    "lfpc",
    "D95",
    "lAge",
    "sG",
    "npp",
    "transp",
    "wscal",
    "lW",
    "relrank",
    "reentry",
]
NTRAIT6 = 6
assert len(TOK_FEAT) == 20
GROW_T = ["dlH", "dlagb", "dlvegc", "LAI1", "dlfpc", "dD95", "npp1", "transp1", "wscal1", "lW1"]
ENTRY_T = ["lagb", "lvegc_agb", "LAI", "lfpc", "D95", "npp", "transp", "wscal", "lW", "sG"]
DZ = [
    "anom_tmean_ann",
    "anom_twarm_month",
    "anom_prec_ann",
    "anom_prec_jja",
    "anom_cwb_jja",
    "anom_vpd_jja",
    "anom_dry_spell_max",
    "anom_swdown_ann",
]
FIRE_DRY = ["prec_jja", "cwb_jja", "vpd_jja", "dry_spell_max", "twarm_month", "days_gt30"]
NSOIL = 16


def slog(x):
    return np.sign(x) * np.log1p(np.abs(x))


def islog(s):
    return np.sign(s) * np.expm1(np.abs(s))


def _l(x, eps=1e-6):
    return np.log(np.maximum(np.asarray(x, np.float64), eps))


# ================================================================================================
# featurisation (numpy)
def token_raw_to_feat(R: dict) -> tuple[np.ndarray, np.ndarray]:
    """R: dict of raw arrays (TOK_RAW names, any shape). Returns (feat [..., len(TOK_FEAT)] float32
    UNstandardised,
    type int). The SAME function serves the tensors (training) and the engine state (rollout)."""
    typ = np.asarray(R["Type"]).astype(np.int64)
    nl = np.maximum(np.asarray(R["n_live"], np.float64), 1.0)
    f = [
        _l(R["SLA"]),
        _l(R["Wooddens"]),
        _l(R["D95max"]),
        R["minwscal"],
        _l(R["Longevity"]),
        R["beta_root"],
        R["Height"],
        _l(R["agb"]),
        _l(R["vegc"]),
        R["LAI"],
        _l(R["fpc_ind"], 1e-8),
        R["D95"],
        _l(R["Age"], 1.0),
        slog(np.asarray(R["G_y"], np.float64) / 10.0),
        R["npp"],
        R["transp"],
        R["wscal_mean"],
        np.log1p(np.maximum(np.asarray(R["W_y"], np.float64), 0.0)),
        (np.asarray(R["height_rank"]) - 1) / nl,
        R["is_reentry_y"],
    ]
    X = np.stack([np.asarray(v, np.float64) for v in f], -1)
    return np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32), typ


def grass_feat(fpc, lai, agb) -> np.ndarray:
    return np.stack(
        [
            np.asarray(fpc, np.float64),
            np.log(np.maximum(lai, 0.0) + LAI_ZERO),
            np.log1p(np.maximum(agb, 0.0)),
        ],
        -1,
    ).astype(np.float32)


def patch_scal(n_live, sum_fpc, sum_agb, lags=None) -> np.ndarray:
    base = [np.asarray(n_live, np.float64) / 10.0, sum_fpc, np.log1p(np.maximum(sum_agb, 0.0))]
    X = np.stack([np.asarray(v, np.float64) for v in base], -1)
    if lags is not None:  # N-set: explicit cover-loss lags 1-20 (+ availability mask)
        lg = np.asarray(lags, np.float64)
        X = np.concatenate([X, np.nan_to_num(lg, nan=0.0), np.isfinite(lg).astype(np.float64)], -1)
    return X.astype(np.float32)


def grow_targets(T: dict) -> np.ndarray:
    """T: dict with state at y and y+1 (raw). -> [..., len(GROW_T)] unstandardised; NaN where unavailable."""
    with np.errstate(divide="ignore", invalid="ignore"):
        out = [
            np.log(T["Height_y1"]) - np.log(T["Height"]),
            np.log(T["agb_y1"]) - np.log(T["agb"]),
            np.log(T["vegc_y1"]) - np.log(T["vegc"]),
            T["LAI_y1"],
            np.log(np.maximum(T["fpc_ind_y1"], 1e-8)) - np.log(np.maximum(T["fpc_ind"], 1e-8)),
            T["D95_y1"] - T["D95"],
            T["npp_y1"],
            T["transp_y1"],
            T["wscal_mean_y1"],
            np.log1p(np.maximum(T["W_y1"], 0.0)),
        ]
    return np.stack([np.asarray(v, np.float64) for v in out], -1).astype(np.float32)


def entry_targets(R: dict) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        out = [
            _l(R["agb"]),
            _l(R["vegc"]) - _l(R["agb"]),
            R["LAI"],
            _l(R["fpc_ind"], 1e-8),
            R["D95"],
            R["npp"],
            R["transp"],
            R["wscal_mean"],
            np.log1p(np.maximum(np.asarray(R["W_y"], np.float64), 0.0)),
            slog(np.asarray(R["G_y"], np.float64) / 10.0),
        ]
    return np.stack([np.asarray(v, np.float64) for v in out], -1).astype(np.float32)


def trait4(R: dict) -> np.ndarray:
    return np.stack(
        [_l(R["SLA"]), _l(R["Wooddens"]), _l(R["D95max"]), np.asarray(R["minwscal"], np.float64)],
        -1,
    ).astype(np.float32)


# ================================================================================================
# normaliser
class Norm(nn.Module):
    """Fixed (non-trainable) standardisation tables, saved with the checkpoint."""

    def __init__(self, n_tok, n_clim, n_stat, n_grow, n_entry, n_pscal):
        super().__init__()
        z = lambda *s: nn.Parameter(torch.zeros(*s), requires_grad=False)  # noqa: E731
        o = lambda *s: nn.Parameter(torch.ones(*s), requires_grad=False)  # noqa: E731
        self.tok_m, self.tok_s = z(n_tok), o(n_tok)
        self.trait_m, self.trait_s = z(NTYPE, NTRAIT6), o(NTYPE, NTRAIT6)  # per Type
        self.clim_m, self.clim_s = z(n_clim), o(n_clim)
        self.stat_m, self.stat_s = z(n_stat), o(n_stat)
        self.grow_m, self.grow_s = z(n_grow), o(n_grow)
        self.entry_m, self.entry_s = z(n_entry), o(n_entry)
        self.grass_m, self.grass_s = z(3), o(3)
        self.pscal_m, self.pscal_s = z(n_pscal), o(n_pscal)
        self.lG_m, self.lG_s = z(1), o(1)
        self.H5_m = z(1)

    def tok(self, X, typ):
        Xn = (X - self.tok_m) / self.tok_s
        t = typ.clamp(0, NTYPE - 1)
        tr6 = (X[..., :NTRAIT6] - self.trait_m[t]) / self.trait_s[t]
        return torch.cat([tr6, Xn[..., NTRAIT6:]], -1)


def fit_norm(norm: Norm, tok, typ, clim, stat, grow, entry, grass, pscal, lG):
    """Fill the tables from training arrays (numpy). Robust to NaN."""

    def ms(a):
        a = np.asarray(a, np.float64)
        m = np.nanmean(a, 0)
        s = np.nanstd(a, 0)
        return torch.tensor(np.nan_to_num(m), dtype=torch.float32), torch.tensor(
            np.where(np.isfinite(s) & (s > 1e-6), s, 1.0), dtype=torch.float32
        )

    with torch.no_grad():
        for name, arr in (
            ("tok", tok),
            ("clim", clim),
            ("stat", stat),
            ("grow", grow),
            ("entry", entry),
            ("grass", grass),
            ("pscal", pscal),
            ("lG", lG[:, None]),
        ):
            m, s = ms(arr)
            getattr(norm, f"{name}_m").copy_(m)
            getattr(norm, f"{name}_s").copy_(s)
        for k in range(NTYPE):
            sel = typ == k
            if sel.sum() > 10:
                m, s = ms(tok[sel, :NTRAIT6])
                norm.trait_m[k].copy_(m)
                norm.trait_s[k].copy_(s)
            else:
                m, s = ms(tok[:, :NTRAIT6])
                norm.trait_m[k].copy_(m)
                norm.trait_s[k].copy_(s)


# ================================================================================================
# building blocks
def mlp(i, h, o, n=2, act=nn.GELU):
    layers, d = [], i
    for _ in range(n - 1):
        layers += [nn.Linear(d, h), act()]
        d = h
    layers.append(nn.Linear(d, o))
    return nn.Sequential(*layers)


class SetBlock(nn.Module):
    """Pre-norm set-transformer block with key-padding mask and FiLM from the conditioning vector."""

    def __init__(self, d, heads, dcond):
        super().__init__()
        self.ln1 = nn.LayerNorm(d, elementwise_affine=False)
        self.ln2 = nn.LayerNorm(d, elementwise_affine=False)
        self.att = nn.MultiheadAttention(d, heads, batch_first=True)
        self.ff = mlp(d, 2 * d, d)
        self.film = nn.Linear(dcond, 4 * d)
        nn.init.zeros_(self.film.weight)
        nn.init.zeros_(self.film.bias)

    def forward(self, x, kpm, cond):
        g1, b1, g2, b2 = self.film(cond)[:, None, :].chunk(4, -1)
        h = self.ln1(x) * (1 + g1) + b1
        a, _ = self.att(h, h, h, key_padding_mask=kpm, need_weights=False)
        x = x + a
        h = self.ln2(x) * (1 + g2) + b2
        return x + self.ff(h)


class ClimEnc(nn.Module):
    def __init__(self, n_clim, n_stat, dz):
        super().__init__()
        self.inp = nn.Linear(n_clim, 64)
        self.gru = nn.GRU(64, 64, batch_first=True)
        self.soil = nn.Embedding(NSOIL, 8)
        self.out = mlp(64 + 8 + n_stat - 1, 128, dz)

    def forward(self, clim_win, stat):
        """clim_win [B, 22, n_clim] standardised (years y-20 .. y+1); stat [B, n_stat] (col 0 = soil
        code raw, the
        rest standardised)."""
        h, _ = self.gru(torch.tanh(self.inp(clim_win)))
        soil = self.soil(stat[:, 0].long().clamp(0, NSOIL - 1))
        return self.out(torch.cat([h[:, -1], soil, stat[:, 1:]], -1))


# ================================================================================================
# the model
class NSet(nn.Module):
    def __init__(
        self,
        n_tok=20,
        n_clim=54,
        n_stat=16,
        n_pscal=3,
        d=128,
        heads=4,
        blocks=3,
        dz=64,
        dh=64,
        lstm=True,
        offset=True,
        resist=None,
        clim_cols=None,
    ):
        super().__init__()
        self.cfg = dict(
            n_tok=n_tok,
            n_clim=n_clim,
            n_stat=n_stat,
            n_pscal=n_pscal,
            d=d,
            heads=heads,
            blocks=blocks,
            dz=dz,
            dh=dh,
            lstm=lstm,
            offset=offset,
        )
        self.d, self.dh, self.lstm_on, self.offset = d, dh, lstm, offset
        self.norm = Norm(n_tok, n_clim, n_stat, len(GROW_T), len(ENTRY_T), n_pscal)
        self.clim_cols = list(clim_cols) if clim_cols is not None else []
        self.dz_idx = (
            [self.clim_cols.index(c) for c in DZ] if clim_cols is not None else list(range(len(DZ)))
        )
        self.dry_idx = (
            [self.clim_cols.index(c) for c in FIRE_DRY] if clim_cols is not None else list(range(6))
        )
        self.type_emb = nn.Embedding(NTYPE + 1, 16)  # 7 = grass token
        self.c_emb = nn.Embedding(NC + 1, 8)
        self.tok_in = mlp(n_tok + 16 + 8, d, d)
        self.grass_in = mlp(3 + 16, d, d)
        dcond = dz + (dh if lstm else 0) + n_pscal
        self.blocks = nn.ModuleList([SetBlock(d, heads, dcond) for _ in range(blocks)])
        self.ln_out = nn.LayerNorm(d)
        self.pool_q = nn.Parameter(torch.randn(d) / math.sqrt(d))
        self.pool_k = nn.Linear(d, d)
        self.clim = ClimEnc(n_clim, n_stat, dz)
        if lstm:
            self.cell = nn.LSTMCell(d + n_pscal + dz, dh)
            self.h0 = mlp(2 * 8 + 2, 64, 2 * dh)
        du = d + d + (dh if lstm else 0) + dz
        self.du = du
        # G
        self.g_trunk = mlp(du, 128, 128)
        self.g_sign = nn.Linear(128, 1)
        self.g_mix = nn.Linear(128, 2 * 3 * 2)  # sign x (w, mu, logsd) x 2 comps
        # growth (conditioned on G1, c1)
        self.gr_trunk = mlp(du + 1 + 8, 128, 128)
        ng = len(GROW_T)
        self.gr_mu = nn.Linear(128, ng)
        self.gr_ls = nn.Linear(128, ng)
        self.gr_U = nn.Linear(128, ng * 4)
        self.gr_V = nn.Parameter(torch.zeros(4, len(DZ)))
        # death correction + visibility
        self.d_trunk = mlp(du + 1 + 8, 128, 1)
        nn.init.zeros_(self.d_trunk[-1].weight)
        nn.init.zeros_(self.d_trunk[-1].bias)
        if not offset:
            nn.init.constant_(self.d_trunk[-1].bias, -4.0)
        self.absent = mlp(du, 64, 1)
        nn.init.constant_(self.absent[-1].bias, -6.0)
        # fire (patch)
        dp = d + (dh if lstm else 0) + dz + 3 + n_pscal + len(FIRE_DRY)
        self.fire = mlp(dp, 64, 1)
        nn.init.constant_(self.fire[-1].bias, -6.0)
        r = np.full(NTYPE, 0.5) if resist is None else np.asarray(resist, np.float64)[:NTYPE]
        s0 = np.clip(1.0 - r, 1e-3, 1 - 1e-3)
        self.s_type = nn.Parameter(torch.tensor(np.log(s0 / (1 - s0)), dtype=torch.float32))
        # recruits
        self.r_count = mlp(dp, 128, 2)
        self.r_type = mlp(dp, 128, NTYPE)
        self.r_cond = mlp(dp + 16, 128, 128)
        K = 8
        self.K = K
        self.r_bg = nn.Linear(128, K * (1 + 2 * 4))
        self.r_copyw = nn.Linear(128 + 1, 1)
        self.r_copy_att = mlp(d + 16, 64, 1)
        self.r_copy_ls = nn.Parameter(torch.full((NTYPE, 4), -1.5))
        self.e_hage = nn.Linear(
            128 + 4, 2 + 6
        )  # gamma (log k, log rate) + age mixture (w, mu, logsd) x 2
        self.e_c = nn.Linear(128, NC)
        ne = len(ENTRY_T)
        self.e_rest = mlp(128 + 4 + 2, 128, 2 * ne)
        # grass (patch)
        self.grass = mlp(dp, 64, 3)  # logit P(LAI < 1e-3), mu, logsd of ln LAI

    # ------------------------------------------------------------------------------------------
    # trunk
    def initial_state(self, tok_raw_feat, typ, mask):
        """h0, c0 from the start roster: 8-bin histograms of ln Age and Height (shares), n_live, sum_fpc proxy."""
        B = mask.shape[0]
        if not self.lstm_on:
            return None
        lage = tok_raw_feat[..., TOK_FEAT.index("lAge")]
        hgt = tok_raw_feat[..., TOK_FEAT.index("Height")]
        m = mask.float()
        n = m.sum(-1, keepdim=True).clamp(min=1.0)

        def hist(v, lo, hi):
            b = ((v - lo) / (hi - lo) * 8).floor().clamp(0, 7).long()
            oh = F.one_hot(b, 8).to(m.dtype) * m[..., None]
            return oh.sum(-2) / n

        lfpc = tok_raw_feat[..., TOK_FEAT.index("lfpc")]
        sfpc = torch.where(mask, torch.exp(lfpc.clamp(max=0.0)), torch.zeros_like(lfpc)).sum(
            -1, keepdim=True
        )
        z = torch.cat(
            [hist(lage, 0.0, 6.0), hist(hgt, 5.0, 45.0), m.sum(-1, keepdim=True) / 10.0, sfpc], -1
        )
        hc = self.h0(z)
        h, c = hc.chunk(2, -1)
        return (torch.tanh(h), c) if B else None

    def encode(self, tokf, typ, c_y, mask, grassf, pscal, z, h):
        """tokf [B,S,Ft] standardised; typ/c_y [B,S] long; mask [B,S] bool (True = tree); grassf
        [B,3] std; pscal
        [B,Fp] std; z [B,dz]; h [B,dh] or None. Returns e [B,S,d], p [B,d]."""
        B, S, _ = tokf.shape
        x = self.tok_in(
            torch.cat(
                [tokf, self.type_emb(typ.clamp(0, NTYPE - 1)), self.c_emb(c_y.clamp(0, NC))], -1
            )
        )
        g = self.grass_in(torch.cat([grassf, self.type_emb.weight[NTYPE].expand(B, -1)], -1))[
            :, None, :
        ]
        x = torch.cat([g, x], 1)
        kpm = torch.cat([torch.zeros(B, 1, dtype=torch.bool, device=mask.device), ~mask], 1)
        cond = torch.cat([z] + ([h] if self.lstm_on else []) + [pscal], -1)
        for blk in self.blocks:
            x = blk(x, kpm, cond)
        x = self.ln_out(x)
        att = (self.pool_k(x) * self.pool_q).sum(-1) / math.sqrt(self.d)
        att = att.masked_fill(kpm, -1e9)
        w = torch.softmax(att, -1)
        p = (w[..., None] * x).sum(1)
        return x[:, 1:], p

    def advance(self, p, pscal, z, hc):
        if not self.lstm_on:
            return None
        return self.cell(torch.cat([p, pscal, z], -1), hc)

    def tree_ctx(self, e, p, h, z):
        B, S, _ = e.shape
        parts = [e, p[:, None].expand(B, S, -1)]
        if self.lstm_on:
            parts.append(h[:, None].expand(B, S, -1))
        parts.append(z[:, None].expand(B, S, -1))
        return torch.cat(parts, -1)

    def patch_ctx(self, p, h, z, grassf, pscal, dry):
        parts = [p] + ([h] if self.lstm_on else []) + [z, grassf, pscal, dry]
        return torch.cat(parts, -1)

    # ------------------------------------------------------------------------------------------
    # heads
    def g_params(self, u):
        t = self.g_trunk(u)
        logit = self.g_sign(t)[..., 0]
        mix = self.g_mix(t).view(*t.shape[:-1], 2, 3, 2)  # sign(0 pos,1 neg) x (w,mu,ls) x comp
        return logit, mix

    def g_nll(self, u, G1, gsign_ok, gmag_ok):
        """G1 raw; returns (sign nll, magnitude nll) per tree (0 where not ok)."""
        logit, mix = self.g_params(u)
        neg = (G1 < 0).float()
        nll_s = F.binary_cross_entropy_with_logits(logit, neg, reduction="none") * gsign_ok
        y = (torch.log(G1.abs().clamp(min=1e-6)) - self.norm.lG_m) / self.norm.lG_s
        sidx = neg.long()[..., None, None, None].expand(*neg.shape, 1, 3, 2)
        mp = torch.gather(mix, -3, sidx)[..., 0, :, :]
        lw = torch.log_softmax(mp[..., 0, :], -1)
        mu, ls = mp[..., 1, :], mp[..., 2, :].clamp(-5, 3)
        lp = (
            lw - 0.5 * ((y[..., None] - mu) / torch.exp(ls)) ** 2 - ls - 0.5 * math.log(2 * math.pi)
        )
        nll_m = -(torch.logsumexp(lp, -1) - torch.log(self.norm.lG_s)) * gmag_ok
        return nll_s, nll_m, logit

    def g_sample(self, u, gen):
        logit, mix = self.g_params(u)
        pn = torch.sigmoid(logit)
        neg = torch.rand(pn.shape, generator=gen, device=pn.device) < pn
        sidx = neg.long()[..., None, None, None].expand(*neg.shape, 1, 3, 2)
        mp = torch.gather(mix, -3, sidx)[..., 0, :, :]
        w = torch.softmax(mp[..., 0, :], -1)
        comp = (
            (torch.rand(w.shape[:-1], generator=gen, device=w.device)[..., None] > w.cumsum(-1))
            .sum(-1)
            .clamp(max=1)
        )
        mu = torch.gather(mp[..., 1, :], -1, comp[..., None])[..., 0]
        ls = torch.gather(mp[..., 2, :], -1, comp[..., None])[..., 0].clamp(-5, 3)
        y = mu + torch.exp(ls) * torch.randn(mu.shape, generator=gen, device=mu.device)
        mag = torch.exp(y * self.norm.lG_s + self.norm.lG_m)
        return torch.where(neg, -mag, mag), pn

    def grow_params(self, u, G1, c1, dz):
        x = torch.cat(
            [
                u,
                (torch.sign(G1) * torch.log1p(G1.abs() / 10.0))[..., None],
                self.c_emb(c1.clamp(0, NC)),
            ],
            -1,
        )
        t = self.gr_trunk(x)
        U = self.gr_U(t).view(*t.shape[:-1], len(GROW_T), 4)
        while dz.dim() < t.dim():
            dz = dz.unsqueeze(-2)
        mu = self.gr_mu(t) + (U * (dz @ self.gr_V.T)[..., None, :]).sum(-1)
        return mu, self.gr_ls(t).clamp(-6, 3), x

    def grow_nll(self, u, G1, c1, dz, Yn, ymask):
        mu, ls, _ = self.grow_params(u, G1, c1, dz)
        nll = 0.5 * ((Yn - mu) / torch.exp(ls)) ** 2 + ls + 0.5 * math.log(2 * math.pi)
        return (nll * ymask).sum(-1), ymask.sum(-1)

    def p_dem(self, u, G1, c1, hazard):
        x = torch.cat(
            [
                u,
                (torch.sign(G1) * torch.log1p(G1.abs() / 10.0))[..., None],
                self.c_emb(c1.clamp(0, NC)),
            ],
            -1,
        )
        g = self.d_trunk(x)[..., 0]
        hz = hazard.clamp(1e-6, 1 - 1e-6)
        logit = (torch.log(hz) - torch.log1p(-hz) + g) if self.offset else g
        hard = (c1 >= NC) | (hazard >= 1.0) if self.offset else (c1 >= NC)
        p = torch.where(hard, torch.ones_like(logit), torch.sigmoid(logit))
        return p, hard

    def fire_f(self, pc):
        return 0.001 + 0.999 * torch.sigmoid(self.fire(pc)[..., 0])

    def s_of(self, typ):
        return torch.sigmoid(self.s_type)[typ.clamp(0, NTYPE - 1)]

    def p_die(self, pdem, hard, s, f):
        p = 1.0 - (1.0 - pdem) * (1.0 - s * f)
        return torch.where(hard, torch.ones_like(p), p)

    # recruits ---------------------------------------------------------------------------------
    def rcount_params(self, pc):
        o = self.r_count(pc)
        return torch.exp(o[..., 0].clamp(-12, 5)), F.softplus(
            o[..., 1]
        ) + 1e-3  # mean, dispersion alpha

    @staticmethod
    def nb_nll(n, mu, alpha):
        r = 1.0 / alpha
        return -(
            torch.lgamma(n + r)
            - torch.lgamma(r)
            - torch.lgamma(n + 1)
            + r * torch.log(r / (r + mu))
            + n * torch.log(mu / (r + mu) + 1e-12)
        )

    def rec_cond(self, pc_r, rtyp):
        return self.r_cond(torch.cat([pc_r, self.type_emb(rtyp)], -1))

    def trait_nll(self, cond, rtyp, x4, e_stems, typ_stems, mask_stems, x4_stems):
        """cond [R,128]; rtyp [R]; x4 [R,4] standardised per Type; e_stems [R,S,d];
        typ_stems/mask_stems [R,S];
        x4_stems [R,S,4] standardised by the RECRUIT's type tables. Returns nll [R]."""
        R = cond.shape[0]
        K = self.K
        bg = self.r_bg(cond).view(R, K, 9)
        lw = torch.log_softmax(bg[..., 0], -1)
        mu, ls = bg[..., 1:5], bg[..., 5:9].clamp(-5, 2)
        lp_bg = lw + (
            -0.5 * ((x4[:, None] - mu) / torch.exp(ls)) ** 2 - ls - 0.5 * math.log(2 * math.pi)
        ).sum(-1)
        lp_bg = torch.logsumexp(lp_bg, -1)
        same = mask_stems & (typ_stems == rtyp[:, None])
        has = same.any(-1)
        a = self.r_copy_att(
            torch.cat([e_stems, self.type_emb(rtyp)[:, None].expand(-1, e_stems.shape[1], -1)], -1)
        )[..., 0]
        la = torch.log_softmax(a.masked_fill(~same, -1e9), -1)
        cls = self.r_copy_ls[rtyp][:, None, :]
        lp_c = la + (
            -0.5 * ((x4[:, None] - x4_stems) / torch.exp(cls)) ** 2
            - cls
            - 0.5 * math.log(2 * math.pi)
        ).sum(-1)
        lp_c = torch.logsumexp(lp_c.masked_fill(~same, -1e9), -1)
        wc = (
            torch.sigmoid(self.r_copyw(torch.cat([cond, has.float()[:, None]], -1))[..., 0])
            * has.float()
        )
        lp = torch.logaddexp(
            torch.log(wc.clamp(min=1e-12)) + lp_c, torch.log((1 - wc).clamp(min=1e-12)) + lp_bg
        )
        return -lp

    def entry_nll(self, cond, x4, H, lage, c, Yn, ymask):
        o = self.e_hage(torch.cat([cond, x4], -1))
        k = torch.exp(o[:, 0].clamp(-3, 5))
        rate = torch.exp(o[:, 1].clamp(-5, 5))
        h5 = (H - 5.0).clamp(min=1e-4)
        nll_h = -(k * torch.log(rate) - torch.lgamma(k) + (k - 1) * torch.log(h5) - rate * h5)
        lw = torch.log_softmax(o[:, 2:4], -1)
        mu, ls = o[:, 4:6], o[:, 6:8].clamp(-4, 2)
        lp = (
            lw
            - 0.5 * ((lage[:, None] - mu) / torch.exp(ls)) ** 2
            - ls
            - 0.5 * math.log(2 * math.pi)
        )
        nll_a = -torch.logsumexp(lp, -1)
        nll_c = F.cross_entropy(self.e_c(cond), c.clamp(0, NC - 1), reduction="none")
        r = self.e_rest(torch.cat([cond, x4, (H[:, None] - 15.0) / 10.0, lage[:, None] / 3.0], -1))
        mu2, ls2 = r.chunk(2, -1)
        ls2 = ls2.clamp(-6, 3)
        nll_r = (
            (0.5 * ((Yn - mu2) / torch.exp(ls2)) ** 2 + ls2 + 0.5 * math.log(2 * math.pi)) * ymask
        ).sum(-1)
        return nll_h, nll_a, nll_c, nll_r

    def grass_nll(self, pc, lai1):
        o = self.grass(pc)
        zero = (lai1 < LAI_ZERO).float()
        nll0 = F.binary_cross_entropy_with_logits(o[..., 0], zero, reduction="none")
        y = torch.log(lai1.clamp(min=LAI_ZERO))
        ls = o[..., 2].clamp(-5, 2)
        nllm = (0.5 * ((y - o[..., 1]) / torch.exp(ls)) ** 2 + ls + 0.5 * math.log(2 * math.pi)) * (
            1 - zero
        )
        return nll0 + nllm


# ================================================================================================
# D1 unit checks
def unit_checks() -> dict:
    import explore_de_sh_rules as rl

    torch.manual_seed(0)
    np.random.seed(0)
    P = rl.load_params()
    m = NSet(resist=P["resist"]).double().eval()
    # perturb the zero-initialised layers so the checks are not trivially satisfied
    with torch.no_grad():
        for prm in m.parameters():
            if prm.requires_grad:
                prm.add_(0.05 * torch.randn_like(prm))
    B, S = 6, 40
    nt = torch.tensor([12, 3, 0, 40, 7, 1])
    mask = torch.arange(S)[None, :] < nt[:, None]
    tokf = torch.randn(B, S, len(TOK_FEAT), dtype=torch.float64)
    typ = torch.randint(0, NTYPE, (B, S))
    cy = torch.randint(0, NC, (B, S))
    grassf = torch.randn(B, 3, dtype=torch.float64)
    pscal = torch.randn(B, 3, dtype=torch.float64)
    clim = torch.randn(B, 22, 54, dtype=torch.float64)
    stat = torch.cat(
        [torch.randint(0, NSOIL, (B, 1)).double(), torch.randn(B, 15, dtype=torch.float64)], -1
    )
    res = {}

    def run(tokf, typ, cy, mask):
        z = m.clim(clim, stat)
        hc = m.initial_state(tokf, typ, mask)
        e, p = m.encode(tokf, typ, cy, mask, grassf, pscal, z, hc[0])
        u = m.tree_ctx(e, p, hc[0], z)
        lg, mix = m.g_params(u)
        dz = clim[:, -1, :8]
        mu, ls, _ = m.grow_params(u, 10 * tokf[..., 0], cy, dz)
        pc = m.patch_ctx(p, hc[0], z, grassf, pscal, clim[:, -1, :6])
        f = m.fire_f(pc)
        return {"tree": torch.cat([lg[..., None], mu], -1), "patch": torch.cat([p, f[:, None]], -1)}

    with torch.no_grad():
        base = run(tokf, typ, cy, mask)
        # u1 permutation of the living slots of every patch
        perm_err = 0.0
        tokf2, typ2, cy2 = tokf.clone(), typ.clone(), cy.clone()
        perms = []
        for b in range(B):
            n = int(nt[b])
            pr = torch.randperm(n)
            perms.append(pr)
            tokf2[b, :n] = tokf[b, pr]
            typ2[b, :n] = typ[b, pr]
            cy2[b, :n] = cy[b, pr]
        out = run(tokf2, typ2, cy2, mask)
        for b in range(B):
            n = int(nt[b])
            perm_err = max(
                perm_err,
                float((out["tree"][b, :n] - base["tree"][b, perms[b]]).abs().max()) if n else 0.0,
            )
        perm_err = max(perm_err, float((out["patch"] - base["patch"]).abs().max()))
        res["u1_permutation_invariance"] = {"max_abs": perm_err, "pass": perm_err <= 1e-6}
        # u2 garbage in padded slots
        tokf3, typ3, cy3 = tokf.clone(), typ.clone(), cy.clone()
        tokf3[~mask] = 1e3 * torch.randn(int((~mask).sum()), len(TOK_FEAT), dtype=torch.float64)
        typ3[~mask] = torch.randint(0, NTYPE, (int((~mask).sum()),))
        cy3[~mask] = torch.randint(0, NC, (int((~mask).sum()),))
        out = run(tokf3, typ3, cy3, mask)
        dtree = torch.where(
            mask[..., None], (out["tree"] - base["tree"]).abs(), torch.zeros_like(out["tree"])
        )
        e2 = max(float((out["patch"] - base["patch"]).abs().max()), float(dtree.max()))
        res["u2_mask_padding_inert"] = {"max_abs": e2, "pass": e2 <= 1e-6}
        # u3 empty patch finite
        fin = bool(torch.isfinite(base["patch"][2]).all())
        res["u3_empty_patch_finite"] = {"pass": fin}
    # u4 counter rule in the sampler path (rule function itself)
    rng = np.random.default_rng(1)
    c_prev = rng.integers(0, 5, 10000)
    G = rng.normal(0, 30, 10000)
    age = rng.integers(1, 300, 10000).astype(float)
    c_rule = rl.counter_step(c_prev, G, age)
    c_mine = counter_next(c_prev, G, age)
    res["u4_counter_rule_exact"] = {
        "mismatch": int((c_rule != c_mine).sum()),
        "pass": bool(np.array_equal(c_rule, c_mine)),
    }
    # u5 hazard cap
    with torch.no_grad():
        u = torch.randn(1000, m.du, dtype=torch.float64)
        G1 = torch.randn(1000, dtype=torch.float64) * 30
        c1 = torch.randint(0, 7, (1000,))
        hz = torch.rand(1000, dtype=torch.float64)
        hz[:100] = 1.0
        hz[100:200] = 0.0
        p, hard = m.p_dem(u, G1, c1, hz)
        ok_hard = bool(torch.all(p[(c1 >= 5) | (hz >= 1)] == 1.0))
        ok_range = bool(torch.all((p >= 0) & (p <= 1)))
        # with g = 0 the offset reproduces the clipped hazard exactly
        m0 = NSet(resist=P["resist"]).double().eval()
        p0, _ = m0.p_dem(u[:, : m0.du], G1, torch.zeros_like(c1), hz)
        exp = hz.clamp(1e-6, 1 - 1e-6)
        exp = torch.where(hz >= 1, torch.ones_like(exp), exp)
        err0 = float((p0 - exp).abs().max())
    res["u5_hazard_cap"] = {
        "hard_is_one": ok_hard,
        "in_range": ok_range,
        "g0_equals_clipped_hazard_maxabs": err0,
        "pass": ok_hard and ok_range and err0 <= 1e-9,
    }
    # u6 fire floor
    with torch.no_grad():
        pcd = m.patch_ctx(
            torch.zeros(1, m.d, dtype=torch.float64),
            torch.zeros(1, m.dh, dtype=torch.float64),
            torch.zeros(1, 64, dtype=torch.float64),
            torch.zeros(1, 3, dtype=torch.float64),
            torch.zeros(1, 3, dtype=torch.float64),
            torch.zeros(1, 6, dtype=torch.float64),
        ).shape[-1]
        X = torch.cat(
            [
                1e4 * torch.randn(500, pcd, dtype=torch.float64),
                -1e4 * torch.ones(1, pcd, dtype=torch.float64),
                1e4 * torch.ones(1, pcd, dtype=torch.float64),
            ]
        )
        f = m.fire_f(X)
        res["u6_fire_floor"] = {
            "min_f": float(f.min()),
            "max_f": float(f.max()),
            "pass": bool((f >= 0.001).all() and (f <= 1.0).all()),
        }
    res["n_params"] = int(sum(p.numel() for p in m.parameters() if p.requires_grad))
    res["pass"] = all(v["pass"] for v in res.values() if isinstance(v, dict))
    return res


def counter_next(c_prev, G, age_pre):
    """Sampler-side counter update (must equal SH2 counter_step exactly; unit check u4)."""
    c = np.where(np.asarray(age_pre, np.float64) == 1, 0, np.asarray(c_prev, np.int64))
    return np.where(np.asarray(G, np.float64) < 0, c + 1, 0).astype(np.int64)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        t0 = time.time()
        r = unit_checks()
        r["seconds"] = round(time.time() - t0, 1)
        r["torch"] = torch.__version__
        print(json.dumps(r, indent=1), flush=True)
        rep = os.path.join(XDE, "_reports", "r2_D1.json")
        json.dump(
            {
                "id": "D1",
                "status": "ok" if r["pass"] else "fail",
                "unit_checks": r,
                "deliverables": [os.path.abspath(__file__)],
            },
            open(rep, "w"),
            indent=1,
        )
        with open(os.path.join(XDE, "_status", "D.md"), "a") as fh:
            fh.write(
                f"- {time.strftime('%Y-%m-%d %H:%M')} D1 unit checks pass={r['pass']} "
                + json.dumps({k: v.get("pass") for k, v in r.items() if isinstance(v, dict)})
                + f" (perm max abs {r['u1_permutation_invariance']['max_abs']:.2e}, mask "
                f"{r['u2_mask_padding_inert']['max_abs']:.2e}, params {r['n_params']})\n"
            )
