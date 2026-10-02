#!/usr/bin/env python3
"""explore_de_tab_stepper.py — LINE X, Germany data-driven emulator, track A-TAB, item A6:
THE A-TAB ROLLOUT STEPPER (SH6 Stepper protocol) for the arms A-L, A-L+phys, A-S, A-1step, A-k0.

One step y -> y+1 for every tree of an engine chunk (explore_de_engine.RosterState), built ONLY
from carried state and the climate provider's frames (no truth-only input; the feature frame is
explore_de_tab_features.roster_raw + assemble, the path A1's audit proved equal to training):

  1 features    B0 state + B1 climate (y = the previous step's clim_y1, carried in aux_cell;
                y+1 = the provider's frame)
  2 G_{y+1}     gsign head (sign, + calibrated logit offset) and gmag_neg / gmag_pos (log|G|)
                + an empirical residual of its predicted-value decile (A2 OOF tables)
  3 counter     c_{y+1} by the original model's rule (c+1 if G < 0 else 0; reset at age 1);
                c = 5 kills
  4 growth      dlog agb, dlog vegc | G_{y+1}, c_{y+1} + per-tree AR(1) residual
                e' = rho e + sqrt(1 - rho^2) sigma(Type, agb decile) z (sigma x calibrated
                multiplier); LAI / fpc_ind / D95 closures; Height = SH2 allometry of the new agb
                x the tree's FIXED offset (aux_tree h_off)
  5 death       A-L       Bernoulli(surv head), c = 5 a certain kill; fire inside the head
                A-L+phys  the same with surv_phys (rule hazard of sampled G / c / Age as input)
                A-S       SH2 rules: hazard (mort_npp + mort_age + mort_temp; mort_water omitted:
                          A-TAB carries no water integral; measured mean mort_water 0.0014/yr vs
                          a death rate 0.049/yr), survive(), then the SH13 patch fire fraction on
                          the survivors ((1 - resist) f) — the order of explore_de_sh_oracle
  6 visibility  a living tree whose new Height < 5 m is hidden (the engine keeps it <= 30 yr and
                prints it again when it regrows); a tree dying below 5 m is removed unprinted
  7 recruits    SH13 patch recruit count (NB draw, + calibrated log offset); entry Height / Age
                (SH13 quantile heads, Gaussian copula with the per-Type rank correlation of the
                SH13 entry table); entry counter / G (SH13 joint table, Type x climate tercile);
                Type from the A5 rtype head; the four inherited traits from the A5 donor
                sampler (donors = the cell's living printed same-Type stems at y); Longevity /
                beta_root by the rules; agb, vegc, LAI, fpc_ind, D95, height offset and the
                dead-on-entry flag from a training-recruit DONOR of the same Type nearest in
                entry Height (stage `prep`; agb = inverse allometry of Height with the donor's
                offset, so Height and agb are consistent)
  8 grass       the A3 grass heads (next-year grass fpc / LAI / agb from the tree cover change)
  aux_tree: e_dagb, e_dvegc (AR residuals), h_off, is_new; aux_patch: agb_dead (fuel input of
  the SH13 fire head); aux_cell: clim_prev (the year-y climate frame). Every random number is the
  engine's counter-based Rand keyed by (Cell, Patch, Type, ID) per tree, (Cell, Patch) per patch,
  (Cell, Patch, slot) per recruit — never by chunk or scenario (common random numbers per leg).

ARMS (--stepper explore_de_tab_stepper:<Class>)
  TabAL      A-L       learned survival; calibration scalars from tab/cal/<split>.json if A7 has
                       written it, else none
  TabALphys  A-L+phys  learned survival with the rule-hazard feature (same calibration rule)
  TabAS      A-S       rule death + SH13 fire, growth heads as A-L (same calibration rule)
  TabA1step  A-1step   A-L with NO calibration ever (until A7 exists: identical to A-L)
  TabAk0     A-k0      climate-blind: kappa = 0 on every climate booster (tree heads, rtype,
                       grass, SH13 fire / recruit / entry heads) AND the direct climate channels
                       (PFT eligibility of the recruit frame, entry climate tercile, survive())
                       read the cell's frozen 1985-2014 climatology
  kwargs (JSON): split, surv ('learned' | 'phys' | 'rules'), kappa, cal (None | 'auto' | path |
  dict of CAL_KEYS), blind_direct, strict (raise on a non-finite state instead of repairing it)

STAGES  prep  [--split DEV-A]  recruit entry-donor table tab/stepper/<split>/entry_donors.npz
        check --run DIR        smoke checks: non-finite values, yearly living printed stems vs the
                               truth of the same cells, core-s per cell-year from meta_<k>.json
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys
import time

import numpy as np
import polars as pl
from scipy.special import ndtr, ndtri

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_engine as en  # noqa: E402
import explore_de_sh_patchheads as ph  # noqa: E402
import explore_de_sh_rules as rl  # noqa: E402
import explore_de_sh_trans as tr  # noqa: E402
import explore_de_tab_features as F  # noqa: E402
import explore_de_tab_heads as Hh  # noqa: E402

XDE = tr.XDE
TAB = F.TAB
STEPDIR = os.path.join(TAB, "stepper")
STATUS = os.path.join(XDE, "_status", "A6.md")
CAL_KEYS = [
    "kappa_g",
    "kappa_growth",
    "kappa_surv",
    "kappa_rec",
    "logit_off_g",
    "logit_off_surv",
    "log_off_rec",
    "ar_sigma_mult",
]
CAL_ID = {
    "kappa_g": 1.0,
    "kappa_growth": 1.0,
    "kappa_surv": 1.0,
    "kappa_rec": 1.0,
    "logit_off_g": 0.0,
    "logit_off_surv": 0.0,
    "log_off_rec": 0.0,
    "ar_sigma_mult": 1.0,
}
DONOR_K = 20  # recruit donor: one of the DONOR_K same-Type training recruits nearest in Height
STATE_F = ["Height", "agb", "vegc", "LAI", "fpc_ind", "D95", "G"]
log = tr.log

_HEADS: dict = {}


def status(msg: str):
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    with open(STATUS, "a") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} {msg}\n")
    print(msg, flush=True)


def sigmoid(s):
    return 1.0 / (1.0 + np.exp(-np.clip(s, -40, 40)))


def load_cal(cal, split):
    """-> (scalars dict, source label). cal: None (identity) | 'auto' (tab/cal/<split>.json if
    present) | path |
    dict. Unknown keys are refused (a typo must not silently become identity)."""
    src = "none"
    d = {}
    if cal == "auto":
        f = os.path.join(TAB, "cal", f"{split}.json")
        if os.path.exists(f):
            cal = f
        else:
            cal = None
    if isinstance(cal, str):
        raw = open(cal, "rb").read()
        d = json.loads(raw)
        d = d.get("scalars", d)
        src = f"{cal} sha256:{hashlib.sha256(raw).hexdigest()[:16]}"
    elif isinstance(cal, dict):
        d, src = dict(cal), "kwargs"
    bad = set(d) - set(CAL_KEYS)
    if bad:
        raise KeyError(f"unknown calibration keys {sorted(bad)}; allowed {CAL_KEYS}")
    return {**CAL_ID, **{k: float(v) for k, v in d.items()}}, src


# ================================================================================ the stepper
class TabStepper:
    needs_bank = False

    def __init__(
        self,
        split: str = "DEV-A",
        surv: str = "learned",
        kappa: float = 1.0,
        cal="auto",
        blind_direct: bool | None = None,
        strict: bool = False,
    ):
        assert surv in ("learned", "phys", "rules"), surv
        self.split, self.surv, self.kappa = split, surv, float(kappa)
        self.cal, self.cal_src = load_cal(cal, split)
        self.blind = (self.kappa == 0.0) if blind_direct is None else bool(blind_direct)
        self.strict = bool(strict)
        self.nonfinite = 0

    # ------------------------------------------------------------------------------------ init
    def init(self, state, ctx):
        if self.split not in _HEADS:
            _HEADS[self.split] = (Hh.TabHeads.load(self.split), ph.load_heads(self.split))
        self.H, self.H13 = _HEADS[self.split]
        self.P = ctx["P"]
        self.gcm, self.seed = ctx["gcm"], int(ctx["seed"])
        k = self.kappa
        c = self.cal
        self.k_g, self.k_gr, self.k_sv = (
            k * c["kappa_g"],
            k * c["kappa_growth"],
            k * c["kappa_surv"],
        )
        self.k_rt = k  # recruit Type head
        m13 = self.H13.meta
        self.k13_fire = k * float(m13["fire"]["kappa"])
        self.k13_rec = k * float(m13["recruit"]["kappa"]) * c["kappa_rec"]
        self.k13_ent = k * float(m13["entry"].get("kappa", 1.0))
        self.hmin = float(self.P.g["height_min"])
        self.cmax = int(self.P.g["bm_inc_counter_max"])
        dz = np.load(os.path.join(STEPDIR, self.split, "entry_donors.npz"))
        self.don = {k_: dz[k_] for k_ in dz.files}
        self.allom = self._allom_coef(self.H.allom)
        cells = state.cell["cells"]
        assert state.npatch > 0
        # carried hidden state of the start roster (A1 rollout conventions)
        spin = self._spinin(state, ctx)
        F.init_conventions(state, spin, int(ctx["start"]))
        t = state.tree
        typ_ok = np.isfinite(
            self.allom[np.clip(t["Type"].astype(np.int64), 0, len(self.allom) - 1), 0]
        )
        assert typ_ok.all(), f"tree Types without an allometry fit: {np.unique(t['Type'][~typ_ok])}"
        state.aux_tree = {
            "e_dagb": np.zeros(state.n, np.float32),
            "e_dvegc": np.zeros(state.n, np.float32),
            "h_off": self.H.height_offset(
                t["agb"], t["Wooddens"], t["SLA"], t["Type"], t["Height"]
            ),
            "is_new": np.asarray(state.aux_tree["is_new"], bool),
        }
        state.aux_patch = {"agb_dead": self._agb_dead_start(state, ctx)}
        mode = ctx.get("clim_mode", "actual")
        cl = en.Climate(self.gcm, ctx["traj"], self.seed, cells, mode)
        state.aux_cell = {"clim_prev": cl.year(int(ctx["start"]))}
        self.frozen = (
            en.Climate(self.gcm, ctx["traj"], self.seed, cells, "frozen_mean").year(
                int(ctx["start"])
            )
            if self.blind
            else None
        )
        log(
            f"TabStepper init: surv={self.surv} kappa={self.kappa} cal={self.cal_src} {self.cal} "
            f"blind_direct="
            f"{self.blind} trees={state.n} cells={len(cells)}"
        )

    @staticmethod
    def _allom_coef(coef: pl.DataFrame) -> np.ndarray:
        B = np.full((tr.MAX_TREE_TYPE + 1, 4), np.nan)
        for r in coef.iter_rows(named=True):
            B[int(r["Type"])] = [r["b0"], r["b_agb"], r["b_wd"], r["b_sla"]]
        return B

    def _spinin(self, state, ctx) -> np.ndarray:
        name = en.init_name(ctx["gcm"], ctx["seed"], ctx["start"], ctx["traj"])
        fs = glob.glob(
            os.path.join(XDE, "shared", "init", ctx["cellset"], name, "cb=*", "trees.parquet")
        )
        cl = state.cell["cells"].tolist()
        S = pl.concat(
            [
                pl.scan_parquet(f)
                .filter(pl.col("Cell").is_in(cl))
                .select("Cell", "Patch", "Type", "ID", "spinin")
                .collect()
                for f in fs
            ]
        )
        k = ["Cell", "Patch", "Type", "ID"]
        q = pl.DataFrame({c: state.tree[c] for c in k}).with_row_index("_i")
        J = q.join(
            S.with_columns([pl.col(c).cast(q.schema[c]) for c in k]).unique(k), on=k, how="left"
        ).sort("_i")
        return J["spinin"].fill_null(False).to_numpy().astype(bool)

    def _agb_dead_start(self, state, ctx) -> np.ndarray:
        """agb flagged dead at the start year per patch (SH4 agb_dead_y), engine patch order;
        0 if unavailable."""
        npt = len(state.cell["cells"]) * state.npatch
        mem, _, _ = tr.registry()
        start = int(ctx["start"])
        try:
            if start <= 2014:
                m = tr.historical_of(mem, ctx["gcm"], ctx["seed"])["member"]
            else:
                m = mem.filter(
                    (pl.col("gcm") == ctx["gcm"])
                    & (pl.col("scen") == ctx["traj"])
                    & (pl.col("seed") == ctx["seed"])
                    & ~pl.col("excluded")
                ).row(0, named=True)["member"]
            Pt = pl.read_parquet(
                F.patch_file(m, start), columns=["Cell", "Patch", "agb_dead_y"]
            ).filter(pl.col("Cell").is_in(state.cell["cells"].tolist()))
        except Exception as e:  # noqa: BLE001
            log(f"agb_dead at start unavailable ({e}); zeros")
            return np.zeros(npt, np.float32)
        out = np.zeros(npt, np.float32)
        ci = state.cell_index(Pt["Cell"].to_numpy())
        out[ci * state.npatch + Pt["Patch"].to_numpy().astype(np.int64)] = (
            Pt["agb_dead_y"].fill_null(0.0).to_numpy()
        )
        return out

    # ---------------------------------------------------------------------------------- pieces
    def _sample_G(self, X, u_s, u_r):
        H, k = self.H, self.k_g
        kk = "k1" if k != 0.0 else "k0"
        p = sigmoid(H.raw("gsign", X, k) + self.cal["logit_off_g"])
        neg = u_s < p
        mag = np.zeros(X.height)
        for s, msk in (("neg", neg), ("pos", ~neg)):
            if not msk.any():
                continue
            m = H.raw(f"gmag_{s}", X.filter(pl.Series(msk)), k)
            edges, res = H.resid[(s, kk)]
            d = np.searchsorted(edges, m)
            r = np.empty(len(m))
            uu = u_r[msk]
            for j in np.unique(d):
                q = d == j
                pool = res[j]
                r[q] = pool[np.minimum((uu[q] * len(pool)).astype(np.int64), len(pool) - 1)]
            mag[msk] = m + r
        return np.where(neg, -np.exp(mag), np.exp(mag)), p

    def _growth(self, X, G1, c1, e_prev, z):
        H = self.H
        Xg = H._with(X, G_y1=G1, c_y1=c1)
        out, e_new = {}, {}
        typ, agb = X["Type"].to_numpy(), X["agb"].to_numpy()
        for g in ("dagb", "dvegc"):
            mu = H.raw(g, Xg, self.k_gr)
            rho, sig = H.ar_params(g, typ, agb)
            e = (
                rho * np.nan_to_num(e_prev[g])
                + np.sqrt(1 - rho**2) * sig * self.cal["ar_sigma_mult"] * z[g]
            )
            e_new[g] = e.astype(np.float32)
            out[g] = mu + e
        return out["dagb"], out["dvegc"], e_new

    def _p_death_learned(self, X, G1, c1):
        H = self.H
        Xs = H._with(X, G_y1=G1, c_y1=c1)
        name = "surv"
        if self.surv == "phys":
            name = "surv_phys"
            Xs = H._with(
                Xs,
                h_phys=Hh.h_phys(
                    X["Type"].to_numpy(),
                    X["Wooddens"].to_numpy(),
                    X["Age"].to_numpy(),
                    G1,
                    c1,
                    X["tstress_own_y1"].to_numpy(),
                    self.P,
                ),
            )
        p = sigmoid(H.raw(name, Xs, self.k_sv) + self.cal["logit_off_surv"])
        return np.where(np.asarray(c1) >= self.cmax, 1.0, p)

    def _direct(self, clim_y1):
        return self.frozen if self.blind else clim_y1

    @staticmethod
    def _cell_rows(cells, frame, cols):
        cj = pl.DataFrame({"Cell": np.asarray(cells).astype(np.int32)}).join(
            frame.select([pl.col("Cell").cast(pl.Int32)] + [pl.col(c) for c in cols]),
            on="Cell",
            how="left",
            maintain_order="left",
        )
        return {c: cj[c].cast(pl.Float64).to_numpy() for c in cols}

    # ------------------------------------------------------------------------------------ step
    def step(self, state, ctx, year, clim_y1, flags_y1, rand):
        t = state.tree
        n = state.n
        y = int(year)
        P = self.P
        cells = state.cell["cells"]
        npatch = state.npatch
        npt = len(cells) * npatch
        pidx = state.patch_index()
        keys = (t["Cell"], t["Patch"], t["Type"], t["ID"])
        cdir = self._direct(clim_y1)
        # 1 features
        X = self.H.features(state, state.aux_cell["clim_prev"], clim_y1, self.gcm)
        # 2-3 growth efficiency + counter
        G1, _ = self._sample_G(
            X, rand.uniform("tab_gsign", y, *keys), rand.uniform("tab_gres", y, *keys)
        )
        c1 = rl.counter_step(t["c"], G1, t["Age"]).astype(np.int64)
        # 4 growth + AR + closures + allometry
        ea, ev = state.aux_tree["e_dagb"], state.aux_tree["e_dvegc"]
        z = {"dagb": rand.normal("tab_zagb", y, *keys), "dvegc": rand.normal("tab_zvegc", y, *keys)}
        da, dv, e_new = self._growth(X, G1, c1, {"dagb": ea, "dvegc": ev}, z)
        cl = self.H.closures(X, G1, c1, da, dv, self.k_gr)
        agb0 = t["agb"].astype(np.float64)
        agb1 = agb0 * np.exp(da)
        vegc1 = t["vegc"].astype(np.float64) * np.exp(dv)
        lai1 = t["LAI"].astype(np.float64) * np.exp(cl.get("dlai", 0.0))
        fpc1 = t["fpc_ind"].astype(np.float64) * np.exp(cl.get("dfpc", 0.0))
        d951 = t["D95"].astype(np.float64) * np.exp(cl.get("dd95", 0.0))
        off = state.aux_tree["h_off"]
        H1 = self.H.height(agb1, t["Wooddens"], t["SLA"], t["Type"], off).astype(np.float64)
        upd = {
            "Height": H1,
            "agb": agb1,
            "vegc": vegc1,
            "LAI": lai1,
            "fpc_ind": fpc1,
            "D95": d951,
            "Age": t["Age"] + 1,
            "c": np.minimum(c1, self.cmax),
            "G": G1,
            "W": np.zeros(n),
            "d_agb_prev": agb1 - agb0,
        }
        upd = self._finite(upd, t, y)
        H1 = upd["Height"]
        hidden1 = H1 < self.hmin
        # 5 death
        u_d = rand.uniform("tab_death", y, *keys)
        Xp = ph.patch_frame_from_state(
            state, cdir, np.zeros(n, bool), hidden1, state.aux_patch["agb_dead"], P
        )
        diag = {}
        if self.surv in ("learned", "phys"):
            pdeath = self._p_death_learned(X, G1, c1)
            dead = u_d < pdeath
            diag["exp_dead"] = float(pdeath.sum())
        else:
            dead, diag = self._rule_death(t, G1, c1, cdir, flags_y1, Xp, pidx, u_d, rand, y, keys)
        dead_hidden = dead & hidden1
        isdead = dead & ~hidden1
        # 7 recruits (the patch frame with THIS step's final deaths / hidden trees)
        live_y = ~t["hidden"] & ~t["isdead"]
        fpc_y = np.where(live_y, t["fpc_ind"].astype(np.float64), 0.0)
        sum_fpc = np.bincount(pidx, weights=fpc_y, minlength=npt)
        lost = np.bincount(pidx, weights=np.where(dead | hidden1, fpc_y, 0.0), minlength=npt)
        Xp = Xp.with_columns(
            fpc_surv_y1=pl.Series(np.maximum(sum_fpc - lost, 0.0)),
            L0=pl.Series(np.where(sum_fpc > 0, lost / np.where(sum_fpc > 0, sum_fpc, 1.0), 0.0)),
        )
        recs, aux_rec = self._recruits(state, Xp, cdir, clim_y1, flags_y1, rand, y)
        # 8 grass
        surv_vis = ~dead & ~hidden1
        fpc_next = np.bincount(pidx, weights=np.where(surv_vis, upd["fpc_ind"], 0.0), minlength=npt)
        if recs is not None and len(recs["Cell"]):
            rpi = state.cell_index(recs["Cell"]) * npatch + recs["Patch"].astype(np.int64)
            fpc_next += np.bincount(
                rpi, weights=np.where(recs["isdead"], 0.0, recs["fpc_ind"]), minlength=npt
            )
        grass = self._grass(state, Xp, sum_fpc, fpc_next, clim_y1)
        # bookkeeping
        agb_dead = np.bincount(
            pidx, weights=np.where(isdead, upd["agb"], 0.0), minlength=npt
        ).astype(np.float32)
        aux_tree = {
            "e_dagb": e_new["dagb"],
            "e_dvegc": e_new["dvegc"],
            "h_off": off,
            "is_new": np.zeros(n, bool),
        }
        self.last = {
            "year": y + 1,
            "n": n,
            "dead": int(isdead.sum()),
            "dead_hidden": int(dead_hidden.sum()),
            "hidden": int((hidden1 & ~dead).sum()),
            "recruits": 0 if recs is None else len(recs["Cell"]),
            "neg_G": float((G1 < 0).mean()) if n else 0.0,
            "c5": int((c1 >= self.cmax).sum()),
            **diag,
        }
        log(f"tab {ctx['arm']} {ctx['traj']} {y + 1}: " + json.dumps(self.last))
        return en.StepOut(
            tree=upd,
            isdead=isdead,
            hidden=hidden1 | dead_hidden,
            remove=dead_hidden,
            recruits=recs,
            grass=grass,
            aux_tree=aux_tree,
            aux_recruits=aux_rec,
            aux_patch={"agb_dead": agb_dead},
            aux_cell={"clim_prev": clim_y1},
        )

    def _finite(self, upd, t, y):
        """Non-finite next-year values: strict -> raise; else keep the year-y value, count."""
        bad_any = np.zeros(len(upd["agb"]), bool)
        for k in STATE_F:
            v = np.asarray(upd[k], np.float64)
            bad = ~np.isfinite(v) | ((v <= 0) & (k != "G"))
            if bad.any():
                bad_any |= bad
                if self.strict:
                    raise FloatingPointError(
                        f"year {y + 1}: {int(bad.sum())} non-finite/non-positive {k}"
                    )
                upd[k] = np.where(bad, t[k].astype(np.float64), v)
        if bad_any.any():
            self.nonfinite += int(bad_any.sum())
            log(
                f"WARNING {y + 1}: repaired {int(bad_any.sum())} trees with non-finite state "
                f"(total "
                f"{self.nonfinite})"
            )
        return upd

    # ------------------------------------------------------------------------------- A-S death
    def _rule_death(self, t, G1, c1, cdir, flags_y1, Xp, pidx, u_d, rand, y, keys):
        P = self.P
        typ = t["Type"].astype(np.int64)
        n = len(typ)
        cc = self._cell_rows(
            t["Cell"],
            cdir,
            [f"tstress_pft{k}" for k in range(tr.MAX_TREE_TYPE + 1)]
            + ["tcold_month_tr20", "twarm_month_tr20"],
        )
        ts = np.zeros(n)
        for k in range(tr.MAX_TREE_TYPE + 1):
            m = typ == k
            if m.any():
                ts[m] = np.nan_to_num(cc[f"tstress_pft{k}"][m])
        out = rl.mortality_step(
            typ,
            t["Wooddens"],
            t["Age"].astype(np.float64),
            t["c"].astype(np.int64),
            G1,
            np.zeros(n),
            ts,
            flags_y1["rh_on"],
            P,
        )
        dead_h = u_d < out["mort"]
        sv = rl.survive(cc["tcold_month_tr20"], cc["twarm_month_tr20"], P)[np.arange(n), typ]
        dead_s = ~dead_h & ~sv
        f = self.H13.fire_f(Xp, kappa=self.k13_fire)
        pk = rl.fire_kill_prob(typ, f[pidx], P)
        dead_f = ~dead_h & ~dead_s & (rand.uniform("tab_fire", y, *keys) < pk)
        return dead_h | dead_s | dead_f, {
            "dead_hazard": int(dead_h.sum()),
            "dead_survive": int(dead_s.sum()),
            "dead_fire": int(dead_f.sum()),
            "fire_f_mean": float(f.mean()),
        }

    # -------------------------------------------------------------------------------- recruits
    def _recruits(self, state, Xp, cdir, clim_y1, flags_y1, rand, y):
        cells = state.cell["cells"]
        npatch = state.npatch
        pcell = np.repeat(cells, npatch)
        ppat = np.tile(np.arange(npatch), len(cells))
        mu = self.H13.recruit_mean(Xp, kappa=self.k13_rec) * np.exp(self.cal["log_off_rec"])
        nrec = self.H13.recruit_draw(mu, rand.uniform("tab_nrec", y, pcell, ppat))
        tot = int(nrec.sum())
        if tot == 0:
            return None, None
        pr = np.repeat(np.arange(len(pcell)), nrec)  # patch row of each recruit
        first = np.r_[0, np.cumsum(nrec)[:-1]]
        slot = np.arange(tot) - np.repeat(first, nrec)
        rc, rp = pcell[pr], ppat[pr]
        # ------------------------- Type (A5 rtype head, one prediction per patch with recruits)
        pw = np.flatnonzero(nrec > 0)
        R = self._rtype_frame(state, Xp, pw, cdir, clim_y1)
        prob = self.H.recruit_type_probs(R, kappa=self.k_rt)
        cdf = np.cumsum(prob, axis=1)
        inv = np.full(len(pcell), -1, np.int64)
        inv[pw] = np.arange(len(pw))
        u_t = rand.uniform("tab_rtype", y, rc, rp, slot)
        k = (u_t[:, None] > cdf[inv[pr]]).sum(1)
        typ = np.asarray(F.RECR_TYPES)[np.minimum(k, len(F.RECR_TYPES) - 1)].astype(np.int64)
        # -- entry Height / Age (SH13 quantile heads, copula per Type), c / G (SH13 joint table)
        Xr = Xp[pr].with_columns(Type=pl.Series(typ.astype(np.float32)))
        z1 = rand.normal("tab_ent_h", y, rc, rp, slot)
        z2 = rand.normal("tab_ent_a", y, rc, rp, slot)
        rho = self.don["rho_HA"][typ]
        u_h, u_a = ndtr(z1), ndtr(rho * z1 + np.sqrt(1 - rho**2) * z2)
        Hn, Age = self.H13.entry_draw(Xr, u_h, u_a, kappa=self.k13_ent)
        tmean = self._cell_rows(rc, cdir, ["tmean_ann"])["tmean_ann"]
        es = self.H13.entry_sample(
            typ, self.H13.clim_tercile(tmean), rand.uniform("tab_ent_cg", y, rc, rp, slot)
        )
        # ------------- traits (A5 donor sampler; donors = the cell's living printed stems at y)
        tr_ = self._traits(state, typ, rc, rp, slot, flags_y1, rand, y)
        # ------ size state from a training-recruit donor of the same Type, nearest entry Height
        sz = self._size_donor(typ, Hn, tr_, rand.uniform("tab_don_sz", y, rc, rp, slot))
        dead = rand.uniform("tab_rdead", y, rc, rp, slot) < self.don["dead_rate"][typ]
        recs = {
            "Cell": rc,
            "Patch": rp,
            "Type": typ,
            **{k_: tr_[k_] for k_ in tr.TRAITS},
            "Height": Hn,
            "agb": sz["agb"],
            "vegc": sz["vegc"],
            "LAI": sz["LAI"],
            "fpc_ind": sz["fpc_ind"],
            "D95": sz["D95"],
            "Age": np.round(Age),
            "c": np.clip(np.nan_to_num(es["c"]), 0, self.cmax - 1),
            "G": np.nan_to_num(es["G"]),
            "W": np.zeros(tot),
            "d_agb_prev": np.full(tot, np.nan),
            "isdead": dead,
            "hidden": np.zeros(tot, bool),
        }
        aux = {
            "e_dagb": np.zeros(tot, np.float32),
            "e_dvegc": np.zeros(tot, np.float32),
            "h_off": sz["h_off"].astype(np.float32),
            "is_new": np.ones(tot, bool),
        }
        return recs, aux

    def _rtype_frame(self, state, Xp, pw, cdir, clim_y1) -> pl.DataFrame:
        """F.recruit_cols() for the patches pw (engine patch rows), from living printed stems
        at y."""
        t = state.tree
        npt = len(state.cell["cells"]) * state.npatch
        ncell = len(state.cell["cells"])
        live = ~t["hidden"] & ~t["isdead"]
        pidx = state.patch_index()
        ci = state.cell_index(t["Cell"])
        agb = np.where(live, t["agb"].astype(np.float64), 0.0)
        cols = {}
        ce_n, ce_a = {}, {}
        for k in F.RECR_TYPES:
            m = live & (t["Type"] == k)
            cols[f"pt_n_t{k}"] = np.bincount(pidx, weights=m.astype(float), minlength=npt)[pw]
            cols[f"pt_agb_t{k}"] = np.bincount(pidx, weights=np.where(m, agb, 0.0), minlength=npt)[
                pw
            ]
            ce_n[k] = np.bincount(ci, weights=m.astype(float), minlength=ncell)
            ce_a[k] = np.bincount(ci, weights=np.where(m, agb, 0.0), minlength=ncell)
        nt = sum(ce_n.values())
        at = sum(ce_a.values())
        pc = pw // state.npatch
        for k in F.RECR_TYPES:
            cols[f"ce_share_t{k}"] = (ce_n[k] / np.where(nt > 0, nt, np.nan))[pc]
            cols[f"ce_agbshare_t{k}"] = (ce_a[k] / np.where(at > 0, at, np.nan))[pc]
        for c in ["n_live_y", "sum_fpc_y", "sum_agb_y", "frac_loss_lag0"] + [
            f"grass{g}_fpc_y" for g in F.GRASS_TYPES
        ]:
            cols[c] = Xp[c].to_numpy()[pw]
        R = pl.DataFrame(cols).with_columns(
            Cell=pl.Series(Xp["Cell"].to_numpy()[pw]).cast(pl.Int16)
        )
        clim_cols = [c for c in F.RECR_CLIM]
        cf = clim_y1.select(
            pl.col("Cell").cast(pl.Int16), *[pl.col(c).alias(f"{c}_y1") for c in clim_cols]
        )
        R = R.join(cf, on="Cell", how="left", maintain_order="left")
        # eligibility from the DIRECT frame (frozen climatology in the climate-blind arm)
        el = self._cell_rows(R["Cell"].to_numpy(), cdir, F.ELIG_ABS)
        E = rl.eligible(
            el["tcold_month_tr20"], el["twarm_month_tr20"], el["gdd5"], el["prec_ann"], self.P
        )
        R = R.with_columns(
            *[pl.Series(f"elig_t{k}_y1", E[:, k].astype(np.float32)) for k in F.RECR_TYPES],
            pl.Series("n_elig_y1", E[:, : tr.MAX_TREE_TYPE + 1].sum(1).astype(np.float32)),
        )
        R = R.join(F.statics(self.gcm), on="Cell", how="left", maintain_order="left")
        return F.recruit_features(R, self.P)

    def _traits(self, state, typ, rc, rp, slot, flags_y1, rand, y):
        t = state.tree
        live = ~t["hidden"] & ~t["isdead"]
        standing = {
            "Cell": t["Cell"][live].astype(np.int32),
            "Type": t["Type"][live].astype(np.int32),
            "agb": t["agb"][live].astype(np.float64),
            **{k: t[k][live].astype(np.float64) for k, _ in Hh.TRAIT_AX},
        }
        D = Hh.prep_donors(typ, rc, standing)
        na = len(Hh.TRAIT_AX)
        U = {
            "mix": rand.uniform("tab_tr_mix", y, rc, rp, slot),
            "don": rand.uniform("tab_tr_don", y, rc, rp, slot),
            "z": np.stack([rand.normal(f"tab_tr_z{j}", y, rc, rp, slot) for j in range(na)]),
            "u": np.stack([rand.uniform(f"tab_tr_u{j}", y, rc, rp, slot) for j in range(na)]),
            "bg": np.stack([rand.uniform(f"tab_tr_bg{j}", y, rc, rp, slot) for j in range(na)]),
        }
        build = rl.build_of(np.full(len(typ), int(flags_y1["bin_feb2026"])))
        out = Hh.mix_draw(D, self.H.traits_fit, build, U, self.P)
        # Longevity: corr_corridor with the C's |e| <= 2 sigma rejection = a normal truncated
        # at +-2 sigma (drawn by inversion)
        sig = self.P["lon_sigma"][typ]
        u = rand.uniform("tab_tr_lon", y, rc, rp, slot)
        lo = ndtr(-2.0)
        e = sig * ndtri(lo + u * (1 - 2 * lo))
        out["Longevity"] = np.power(
            10.0, self.P["lon_interc"][typ] + np.log10(out["SLA"]) * self.P["lon_slope"][typ] + e
        )
        out["beta_root"] = rl.getbetaroot(out["D95max"], self.P)
        return out

    def _size_donor(self, typ, Hn, trt, u):
        """For each recruit: one of the DONOR_K training recruits of its Type nearest in entry
        Height; carries the donor's allometry offset (-> agb by inverse allometry with the
        recruit's own traits), vegc/agb, LAI,
        fpc_ind and D95/D95max."""
        d = self.don
        n = len(typ)
        out = {k: np.zeros(n) for k in ("agb", "vegc", "LAI", "fpc_ind", "D95", "h_off")}
        for ty in np.unique(typ):
            m = typ == ty
            s, e = int(d["start"][ty]), int(d["end"][ty])
            if e <= s:
                raise KeyError(f"no recruit donors for Type {ty}")
            Hs = d["H"][s:e]
            pos = np.searchsorted(Hs, Hn[m])
            lo = np.clip(pos - DONOR_K // 2, 0, max(e - s - DONOR_K, 0))
            j = s + np.minimum(lo + (u[m] * DONOR_K).astype(np.int64), e - s - 1)
            b = self.allom[ty]
            off = d["off"][j]
            lnh = np.log(Hn[m]) - off
            ln_agb = (
                lnh - b[0] - b[2] * np.log(trt["Wooddens"][m]) - b[3] * np.log(trt["SLA"][m])
            ) / b[1]
            agb = np.exp(ln_agb)
            out["agb"][m] = agb
            out["vegc"][m] = agb * np.exp(d["lvr"][j])
            out["LAI"][m] = d["LAI"][j]
            out["fpc_ind"][m] = d["fpc"][j]
            out["D95"][m] = np.minimum(d["d95r"][j] * trt["D95max"][m], trt["D95max"][m])
            out["h_off"][m] = off
        return out

    # ----------------------------------------------------------------------------------- grass
    def _grass(self, state, Xp, sum_fpc_y, fpc_next, clim_y1):
        H = self.H
        if "grass_g_fpc_y1" not in H.m:
            return None
        ring = state.patch["loss_ring"]
        G = Xp.select(
            "Cell",
            "grass8_fpc_y",
            "grass8_LAI_y",
            "grass8_agb_y",
            "sum_fpc_y",
            "n_live_y",
            "sum_agb_y",
        )
        G = G.with_columns(
            d_sum_fpc=pl.Series(fpc_next - sum_fpc_y),
            **{f"frac_loss_lag{k}": pl.Series(ring[:, k].astype(np.float64)) for k in range(3)},
        )
        cf = clim_y1.select(
            pl.col("Cell").cast(pl.Int16),
            *[pl.col(f"anom_{f}").alias(f"a_{f}_y1") for f in F.CLIM_F],
            *[pl.col(f).alias(f"{f}_y1") for f in F.ABS_Y1],
        )
        G = G.join(cf, on="Cell", how="left", maintain_order="left").join(
            F.statics(self.gcm), on="Cell", how="left", maintain_order="left"
        )
        p = H.grass(G, kappa=self.kappa)
        return {
            "grass8_fpc": np.clip(p["g_fpc_y1"], 0.0, 1.0),
            "grass8_LAI": np.maximum(p["g_LAI_y1"], 0.0),
            "grass8_agb": np.maximum(p["g_agb_y1"], 0.0),
        }


class TabAL(TabStepper):
    """A-L: learned survival; calibration from tab/cal/<split>.json when A7 has written it."""

    def __init__(self, **kw):
        super().__init__(**{"surv": "learned", "cal": "auto", **kw})


class TabALphys(TabStepper):
    def __init__(self, **kw):
        super().__init__(**{"surv": "phys", "cal": "auto", **kw})


class TabAS(TabStepper):
    def __init__(self, **kw):
        super().__init__(**{"surv": "rules", "cal": "auto", **kw})


class TabA1step(TabStepper):
    """A-1step: A-L with no free-run calibration, ever."""

    def __init__(self, **kw):
        super().__init__(**{"surv": "learned", **kw, "cal": None})


class TabAk0(TabStepper):
    """A-k0: climate-blind twin of A-L (kappa 0 on every climate booster, direct channels
    frozen)."""

    def __init__(self, **kw):
        super().__init__(**{"surv": "learned", "cal": "auto", **kw, "kappa": 0.0})


# ================================================================================= stage prep
def stage_prep(a):
    """Recruit entry-donor table: training recruits (A1 recruits/train = training members,
    folds 1-4) per Type, sorted by entry Height: allometry offset, ln(vegc/agb), LAI, fpc_ind,
    D95/D95max; per-Type dead-on-entry rate and the Height-Age normal-score correlation of the
    SH13 entry table (copula of the entry draw)."""
    fs = glob.glob(os.path.join(F.SAMPLES, a.split, "recruits", "train", "*.parquet"))
    cols = [
        "Type",
        "Height",
        "agb",
        "vegc",
        "LAI",
        "fpc_ind",
        "D95",
        "D95max",
        "Wooddens",
        "SLA",
        "isdead",
        "u_rec",
    ]
    R = pl.concat([pl.read_parquet(f, columns=cols) for f in fs]).filter(
        (pl.col("Type") <= tr.MAX_TREE_TYPE)
        & (pl.col("agb") > 0)
        & (pl.col("vegc") > 0)
        & (pl.col("LAI") > 0)
        & (pl.col("fpc_ind") > 0)
        & (pl.col("D95max") > 0)
    )
    coef = rl.load_allometry(a.split)
    nt = tr.MAX_TREE_TYPE + 1
    H, off, lvr, lai, fpc, d95r = [], [], [], [], [], []
    start, end = np.zeros(nt, np.int64), np.zeros(nt, np.int64)
    dead = np.zeros(nt)
    ntot = 0
    per = {}
    for ty in range(nt):
        g = R.filter(pl.col("Type") == ty)
        start[ty] = ntot
        if g.height == 0:
            end[ty] = ntot
            continue
        dead[ty] = float(g["isdead"].cast(pl.Float64).mean())
        if g.height > a.max_per_type:
            g = g.filter(pl.col("u_rec") < a.max_per_type / g.height)
        g = g.sort("Height")
        h = g["Height"].to_numpy().astype(np.float64)
        pred = rl.predict_height(
            g["agb"].to_numpy(),
            g["Wooddens"].to_numpy(),
            g["SLA"].to_numpy(),
            g["Type"].to_numpy(),
            coef,
        )
        o = np.log(h) - np.log(pred)
        ok = np.isfinite(o)
        g, h, o = g.filter(pl.Series(ok)), h[ok], o[ok]
        H.append(h)
        off.append(o)
        lvr.append(np.log(g["vegc"].to_numpy() / g["agb"].to_numpy()))
        lai.append(g["LAI"].to_numpy())
        fpc.append(g["fpc_ind"].to_numpy())
        d95r.append(np.minimum(g["D95"].to_numpy() / g["D95max"].to_numpy(), 1.0))
        ntot += g.height
        end[ty] = ntot
        per[ty] = {
            "n": int(g.height),
            "dead_rate": dead[ty],
            "off_sd": float(np.std(o)),
            "off_mean": float(np.mean(o)),
        }
    E = pl.read_parquet(os.path.join(ph.OUT, a.split, "entry_table.parquet"))
    rho = np.zeros(nt)
    for ty in range(nt):
        e = E.filter(pl.col("Type") == ty)
        if e.height > 50:
            zh = ndtri((e["Height"].rank().to_numpy() - 0.5) / e.height)
            za = ndtri((e["Age"].rank().to_numpy() - 0.5) / e.height)
            rho[ty] = float(np.clip(np.corrcoef(zh, za)[0, 1], -0.95, 0.95))
            per.setdefault(ty, {})["rho_HA"] = rho[ty]
    od = os.path.join(STEPDIR, a.split)
    os.makedirs(od, exist_ok=True)
    np.savez(
        os.path.join(od, "entry_donors.npz"),
        H=np.concatenate(H),
        off=np.concatenate(off),
        lvr=np.concatenate(lvr),
        LAI=np.concatenate(lai),
        fpc=np.concatenate(fpc),
        d95r=np.concatenate(d95r),
        start=start,
        end=end,
        dead_rate=dead,
        rho_HA=rho,
    )
    json.dump(
        {"split": a.split, "source": fs, "per_type": {str(k): v for k, v in per.items()}},
        open(os.path.join(od, "entry_donors.json"), "w"),
        indent=1,
        default=float,
    )
    status(f"A6 prep {a.split}: entry donors {ntot} rows; " + json.dumps(per, default=float))


# ================================================================================ stage check
def truth_counts(gcm, seed, legs, cells, y0, y1) -> pl.DataFrame:
    """Living printed tree stems per (scen, Year) on `cells` in the truth (Historical + leg)."""
    mem, _, _ = tr.registry()
    hist = tr.historical_of(mem, gcm, seed)
    out = []
    for leg in legs:
        parts = [pl.scan_parquet(hist["ind_dev_path"])]
        r = mem.filter(
            (pl.col("gcm") == gcm)
            & (pl.col("scen") == leg)
            & (pl.col("seed") == seed)
            & ~pl.col("excluded")
        )
        if r.height:
            parts.append(pl.scan_parquet(r.row(0, named=True)["ind_dev_path"]))
        d = (
            pl.concat(parts, how="diagonal")
            .filter(
                pl.col("Cell").is_in(cells)
                & (pl.col("Type") <= tr.MAX_TREE_TYPE)
                & pl.col("Year").is_between(y0, y1)
            )
            .group_by("Year")
            .agg(n_truth=(pl.col("isdead") == 0).sum(), dead_truth=(pl.col("isdead") == 1).sum())
            .collect()
        )
        out.append(d.with_columns(leg=pl.lit(leg)))
    return pl.concat(out).unique(["leg", "Year"]).sort("leg", "Year")


def stage_check(a):
    run = json.load(open(os.path.join(a.run, "run.json")))
    E = pl.scan_parquet(os.path.join(a.run, "chunk_*", "*.parquet"))
    num = [
        "Height",
        "SLA",
        "Wooddens",
        "D95max",
        "minwscal",
        "Longevity",
        "beta_root",
        "agb",
        "vegc",
        "LAI",
        "fpc_ind",
        "D95",
        "Age",
    ]
    nf = (
        E.select([(~pl.col(c).cast(pl.Float64).is_finite()).sum().alias(c) for c in num])
        .collect()
        .row(0, named=True)
    )
    nonpos = (
        E.select([(pl.col(c).cast(pl.Float64) <= 0).sum().alias(c) for c in num])
        .collect()
        .row(0, named=True)
    )
    A = (
        E.group_by("scen", "Year")
        .agg(
            n_arm=(pl.col("isdead") == 0).sum(),
            dead_arm=(pl.col("isdead") == 1).sum(),
            cells=pl.col("Cell").n_unique(),
        )
        .collect()
    )
    legs = run["legs"].split(",")
    cells = sorted(set(E.select("Cell").unique().collect()["Cell"].to_list()))
    T = truth_counts(run["gcm"], int(run["seed"]), legs, cells, run["start"], run["end"])
    rows = []
    for leg in legs:
        a_ = A.filter(pl.col("scen").is_in([leg, "Historical"]))
        rows.append(a_.with_columns(leg=pl.lit(leg)))
    J = (
        pl.concat(rows)
        .join(T, on=["leg", "Year"], how="left")
        .sort("leg", "Year")
        .with_columns(ratio=pl.col("n_arm") / pl.col("n_truth"))
    )
    metas = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(a.run, "meta_*.json")))]
    core = sum(sum(m["timing_core_s"].values()) for m in metas)
    cy = sum(m["cell_years"] for m in metas)
    step = sum(m["timing_core_s"]["step"] for m in metas)
    r = J["ratio"].drop_nulls()
    res = {
        "run": a.run,
        "cells": len(cells),
        "rows": int(A["n_arm"].sum() + A["dead_arm"].sum()),
        "nonfinite": nf,
        "nonpositive": nonpos,
        "any_nonfinite": any(v > 0 for v in nf.values()),
        "count_ratio_min": float(r.min()),
        "count_ratio_max": float(r.max()),
        "count_within_2x_every_year": bool(((r >= 0.5) & (r <= 2.0)).all()),
        "core_s_per_cell_year": core / max(cy, 1),
        "core_s_per_cell_year_step": step / max(cy, 1),
        "cell_years": cy,
        "chunks": len(metas),
        "yearly": J.select(
            "leg", "Year", "n_arm", "n_truth", "ratio", "dead_arm", "dead_truth"
        ).to_dicts(),
    }
    res["pass"] = (not res["any_nonfinite"]) and res["count_within_2x_every_year"]
    out = a.out or os.path.join(a.run, "check.json")
    json.dump(res, open(out, "w"), indent=1, default=float)
    status(
        f"A6 check {os.path.basename(a.run)}: pass={res['pass']} "
        f"nonfinite={res['any_nonfinite']} ratio "
        f"{res['count_ratio_min']:.3f}-{res['count_ratio_max']:.3f}, "
        f"{res['core_s_per_cell_year']:.3f} core-s/cell-yr"
    )
    print(json.dumps({k: v for k, v in res.items() if k != "yearly"}, indent=1, default=float))


# -------------------------------------------------------------------------------- stage report
REPORT = os.path.join(XDE, "_reports", "r2_A6.json")
SCORES = os.path.join(XDE, "shared", "eval", "scores")
EVALD = os.path.join(XDE, "shared", "eval")
WINDOWS = ["h1985", "w2015", "c2015", "PRIMARY_c2015"]


def score_rows(label: str) -> list[dict]:
    """panel106 conjunctive pass vs the same-row ceiling (cell + block scale) and primary gate of
    one scored label (explore_de_sh_eval's table logic, restricted to one label)."""
    rows = []
    d = os.path.join(SCORES, label)
    for scale, sub in (("cell", ""), ("block", "block")):
        f = os.path.join(d, sub, "summary_conjunctive.csv")
        if not os.path.exists(f):
            continue
        s = pl.read_csv(f, infer_schema_length=10000).filter(pl.col("panel") == "panel106")
        for r in s.iter_rows(named=True):
            if r["window"] not in WINDOWS:
                continue
            row = {
                "scale": scale,
                "scen": r["scen"],
                "window": r["window"],
                "n_cells": r["n_cells"],
            }
            for p in ("cal", "cal_xg"):
                v, c = r.get(f"all_pass_{p}_frac"), r.get(f"ceiling_same_all_pass_{p}_frac")
                row[f"pass_{p}"], row[f"ceiling_{p}"] = v, c
            rows.append(row)
    pg = os.path.join(d, "primary_gate.csv")
    if os.path.exists(pg):
        for r in pl.read_csv(pg, infer_schema_length=10000).iter_rows(named=True):
            rows.append(
                {
                    "scale": r["scale"],
                    "scen": r["scen"],
                    "window": "PRIMARY_" + r["window"],
                    "pass_cal_xg": r["arm_cal_xg"],
                    "ceiling_cal_xg": r["ceiling_same_cal_xg"],
                    "verdict": r["verdict"],
                }
            )
    return rows


def stage_report(a):
    rep = json.load(open(REPORT)) if os.path.exists(REPORT) else {}
    rep.update(
        {"item": "A6", "script": os.path.abspath(__file__), "updated": time.strftime("%F %T")}
    )
    smoke = {}
    for arm in ("AL", "AS", "Ak0"):
        f = os.path.join(
            XDE,
            "runs",
            f"tab_smoke_{arm}",
            "MPI-ESM1-2-HR_s1_1985-2044_ssp370_actual_r1",
            "check.json",
        )
        if os.path.exists(f):
            c = json.load(open(f))
            smoke[arm] = {
                k: c[k]
                for k in (
                    "pass",
                    "any_nonfinite",
                    "count_ratio_min",
                    "count_ratio_max",
                    "count_within_2x_every_year",
                    "core_s_per_cell_year",
                    "core_s_per_cell_year_step",
                    "cell_years",
                )
            }
    rep["smoke"] = smoke
    runs = {}
    labels = {"AL": "tabAL_ACCESS", "AS": "tabAS_ACCESS", "Ak0": "tabAk0_ACCESS"}
    base = "ACCESS-CM2_s1_1985-2044_ssp126+ssp245+ssp370_actual_r1"
    for arm, lab in labels.items():
        rd = os.path.join(XDE, "runs", f"tab{arm}", base)
        metas = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(rd, "meta_*.json")))]
        r = {"run": rd, "chunks_done": len(metas)}
        if metas:
            core = sum(sum(m["timing_core_s"].values()) for m in metas)
            cy = sum(m["cell_years"] for m in metas)
            r.update(
                core_s_per_cell_year=core / max(cy, 1),
                cell_years=cy,
                core_s_per_cell_year_step=sum(m["timing_core_s"]["step"] for m in metas) / cy,
            )
        if len(metas) == 10 and a.trajectory:
            r["trajectory"] = trajectory(rd)
        dj = os.path.join(EVALD, f"dynamics_{lab}.json")
        if os.path.exists(dj):
            r["dynamics_summary"] = json.load(open(dj))
        for cl in ("dev", "f5"):
            r[f"scores_{cl}"] = score_rows(f"{lab}_{cl}")
        runs[arm] = r
    rep["runs"] = runs
    rep["lookup"] = {cl: score_rows(f"lookup_ACCESS_{cl}") for cl in ("dev", "f5")}
    rep["lookup_noclim"] = {cl: score_rows(f"lookupnoclim_ACCESS_{cl}") for cl in ("dev", "f5")}
    json.dump(rep, open(REPORT, "w"), indent=1, default=float)
    status(f"A6 report written: {REPORT}")


def trajectory(rd: str) -> list[dict]:
    """Germany-dev yearly living printed stems and flagged-dead stems, arm vs truth (per leg)."""
    run = json.load(open(os.path.join(rd, "run.json")))
    E = pl.scan_parquet(os.path.join(rd, "chunk_*", "*.parquet"))
    A = (
        E.group_by("scen", "Year")
        .agg(n_arm=(pl.col("isdead") == 0).sum(), dead_arm=(pl.col("isdead") == 1).sum())
        .collect()
    )
    legs = run["legs"].split(",")
    cells = [
        int(x) for x in open(os.path.join(XDE, "shared", "scorer", "cells_dev.txt")).read().split()
    ]
    T = truth_counts(run["gcm"], int(run["seed"]), legs, cells, run["start"], run["end"])
    out = []
    for leg in legs:
        a_ = A.filter(pl.col("scen").is_in([leg, "Historical"])).with_columns(leg=pl.lit(leg))
        out.append(a_)
    J = pl.concat(out).join(T, on=["leg", "Year"], how="left").sort("leg", "Year")
    return J.select("leg", "Year", "n_arm", "n_truth", "dead_arm", "dead_truth").to_dicts()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["prep", "check", "report"])
    ap.add_argument("--split", default="DEV-A")
    ap.add_argument("--max-per-type", type=int, default=200_000)
    ap.add_argument("--run")
    ap.add_argument("--out")
    ap.add_argument("--trajectory", action="store_true")
    a = ap.parse_args(argv)
    {"prep": stage_prep, "check": stage_check, "report": stage_report}[a.stage](a)


if __name__ == "__main__":
    main()
