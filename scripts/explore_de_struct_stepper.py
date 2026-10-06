#!/usr/bin/env python3
"""explore_de_struct_stepper.py — LINE X, Germany emulator, B-STRUCT item B5: THE STRUCT STEPPER.

An SH6 engine Stepper (`explore_de_engine.py run --stepper explore_de_struct_stepper:Struct`).
Only the climate -> growth map is learned (B1 heads). Deaths, the bad-growth counter, eligibility
and recruit-trait inheritance are the original model's own rules (SH2); the patch fire rate and
the recruit count / entry state are SH13's patch heads.

ONE STEP y -> y+1 (every present tree, printed or hidden):
 1 features   tree state at y (Type, 6 traits, Height, agb, vegc, LAI, fpc_ind, D95, Age, counter
              c), patch context of the PRINTED living trees at y (n_live, sum_fpc, sum_agb,
              height_rank, fpc_above; a hidden tree gets rank n_live + 1, fpc_above = sum_fpc),
              grass8 of the patch (engine-carried and FROZEN: no head updates grass), soil code,
              and the climate of y AND y+1 (levels + anomalies, explore_de_struct_heads
              .add_features). Never last year's npp / transp / G / W / hazards.
 2 growth     StructHeads.sample(X, z): G_{y+1} (sign classifier + sign-conditional regression),
              W_{y+1} (hurdle; 0 when rh_on = 0), then dlog agb, dlog vegc, dLAI, dlog fpc_ind,
              dlog D95 GIVEN that G. Height_{y+1} from the SH2 allometry on the new agb (types
              without a fitted allometry, 0 and 6, use the mean coefficients of the fitted types;
              they are kernel-only types in Germany). z = the per-tree latent normal score vector
              (G, W, 5 sizes) in aux_tree["z"]: AR(1) z' = rho z + sigma L e per (Type, size
              class) from B1's out-of-fold tables; rollout start and recruits: stationary draw.
 3 death      SH2 rules in the C's order: counter, mort_npp(G, c), mort_age(printed Age = age
              before the increment), mort_water(W, c, rh_on), mort_temp(tstress_pft<Type> of
              y+1), cap, c >= 5 kill, Bernoulli; bioclimatic survive() on the survivors; then fire
              on what is left with SH13's patch fraction f (the pooled-rate head). A tree that
              dies below 5 m is never emitted (the C prints only > 5 m): hidden + removed.
 4 visibility alive and Height_{y+1} < 5 m -> hidden (the engine keeps it up to 30 yr; it
              re-enters when it regrows past 5 m).
 5 recruits   count per patch from SH13(b) (NB draw, fed with THIS step's survivors' cover and
              loss); identity per cell from the B3 kernel (inheritance from the engine's seedbank
              with weight 4/(4 + n_elig), else background over the eligible PFTs; traits by
              draw_new_trait with the year's binary; Longevity by the corridor; beta_root by
              getbetaroot); entry Height and Age from SH13(c) quantile heads; entry counter c and
              G from SH13(c)'s joint table; agb from the inverse of the same allometry (so next
              year's allometric Height starts at the entry Height); vegc / LAI / fpc_ind / D95
              from a per-Type log-linear entry-size model fitted on training recruits (`entry`).
 ACCEPTANCE HOOK (B4, not built): kwargs accept="module:Class" (+ accept_kwargs,
              accept_oversample m). The class needs `load(split, **kw)` (or a constructor with
              that signature) and `weights(props: dict, ctx: dict) -> np.ndarray >= 0`; the
              stepper then proposes n*m saplings per cell and importance-resamples n. Without it
              (default) this is the B-noacc arm: the kernel's proposals are taken as they are.

ARMS (kwargs JSON)
 B-noacc  {}             the main arm until B4 exists
 B-noAR   {"ar": false}  no persistence in the latent residual: z drawn afresh every year from
                         its stationary (marginal) distribution (rho = 0, same marginal sd, same
                         innovation correlation across the 7 targets)
 B-k0     {} run with the ENGINE's `--clim frozen_mean` provider (each cell's own 1985-2014
          climatology, anomalies exactly 0, segment flags still live): the same code, a
          climate-blind provider, no stepper hack.
CALIBRATION  optional struct/cal/<split>.json (NOT created here; fit only on training members):
  {"rho_mult": {"G": a, "W": b, "size": c}, "sd_mult": {"G": ..}, "z_shift": {"G": ..}}
  rho' = clip(rho rho_mult, -0.99, 0.99); stationary sd' = sd sd_mult; sigma' = sd' sqrt(1-rho'^2);
  z_shift adds a constant to the latent before sampling (G: shifts P(G<0)). kwargs cal="none"
  ignores the file, cal="<path>" reads another. Without a file: the uncalibrated OOF tables.
DIAGNOSTICS  per chunk and year -> struct/stepper/diag/<arm>/<gcm>_s<seed>_<clim>_r<rep>/
  c<first>-<last>.json: printed living trees, deaths by channel, rule hard kills (hazard >= 1),
  c >= 1 prevalence, recruits, hidden trees, NaNs.

STAGES
  entry --split S   fit the entry-size model on the split's training recruits
                    -> struct/stepper/<S>/entry_size.json
  check --run DIR   checks of an engine run: NaN, yearly living-stem count vs truth (ratio range),
                    death rate, c >= 1 prevalence and hard-kill rate (diag files), core-s per
                    cell-year (engine meta) -> DIR/struct_check.json (+ struct_check_yearly.csv)
"""

from __future__ import annotations

import argparse
import glob
import importlib
import json
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_engine as en  # noqa: E402
import explore_de_sh_patchheads as ph  # noqa: E402
import explore_de_sh_rules as rl  # noqa: E402
import explore_de_sh_trans as tr  # noqa: E402
import explore_de_struct_heads as hd  # noqa: E402
import explore_de_struct_kernel as kn  # noqa: E402

XDE = tr.XDE
OUT = os.path.join(XDE, "struct", "stepper")
CAL = os.path.join(XDE, "struct", "cal")
STATUS = os.path.join(XDE, "_status", "B5.md")
HEIGHT_MIN = 5.0  # the ind writer's print cut (fwriteoutput_ind.c:84, height > height_min)
SIZE_IDX = list(range(2, len(hd.LATENT)))  # latent columns of the 5 size heads
ENTRY_X = ["ln_agb", "ln_wd", "ln_sla", "ln_d95max", "ln_age"]
ENTRY_Y = ["ln_vegc", "LAI", "ln_fpc", "ln_D95"]
log = tr.log


def status(line: str):
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    with open(STATUS, "a") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} {line}\n")


# ========================================================================================== helpers
def full_allometry(split: str) -> pl.DataFrame:
    """SH2 allometry of the split with rows added for tree types without a fit (mean of the fitted
    coefficients)."""
    a = rl.load_allometry(split)
    have = set(a["Type"].to_list())
    num = ["b0", "b_agb", "b_wd", "b_sla"]
    mean = {c: float(a[c].mean()) for c in num}
    add = [{"Type": t, **mean} for t in range(tr.MAX_TREE_TYPE + 1) if t not in have]
    if add:
        a = pl.concat(
            [a.select(["Type"] + num), pl.DataFrame(add).select(["Type"] + num)],
            how="vertical_relaxed",
        )
    return a.select(["Type"] + num).sort("Type")


def agb_from_height(h, wd, sla, typ, coef: pl.DataFrame) -> np.ndarray:
    """Inverse of rl.predict_height (ln H = b0 + b_agb ln agb + b_wd ln wd + b_sla ln sla)."""
    B = np.zeros((tr.MAX_TREE_TYPE + 1, 4))
    for r in coef.iter_rows(named=True):
        B[r["Type"]] = [r["b0"], r["b_agb"], r["b_wd"], r["b_sla"]]
    b = B[np.asarray(typ, np.int64)]
    z = (
        np.log(np.asarray(h, np.float64))
        - b[:, 0]
        - b[:, 2] * np.log(np.asarray(wd, np.float64))
        - b[:, 3] * np.log(np.asarray(sla, np.float64))
    ) / b[:, 1]
    return np.exp(z)


def patch_context(state, printed: np.ndarray):
    """n_live / sum_fpc / sum_agb per patch over PRINTED living trees, and per tree height_rank
    (rank 'min',
    descending, 1 = tallest) and fpc_above (fpc of strictly taller printed stems) — the SH3
    definitions. Hidden trees:
    rank n_live + 1, fpc_above = sum_fpc."""
    t = state.tree
    n = state.n
    npt = len(state.cell["cells"]) * state.npatch
    pidx = state.patch_index()
    fpc = t["fpc_ind"].astype(np.float64)
    H = t["Height"].astype(np.float64)
    w = printed.astype(np.float64)
    n_live = np.bincount(pidx, weights=w, minlength=npt)
    sum_fpc = np.bincount(pidx, weights=fpc * w, minlength=npt)
    sum_agb = np.bincount(pidx, weights=t["agb"].astype(np.float64) * w, minlength=npt)
    rank = n_live[pidx] + 1.0
    above = sum_fpc[pidx].copy()
    idx = np.flatnonzero(printed)
    if idx.size:
        order = np.lexsort((-H[idx], pidx[idx]))
        ii = idx[order]
        po, ho, fo = pidx[ii], H[ii], fpc[ii]
        m = len(ii)
        pos = np.arange(m)
        newp = np.r_[True, po[1:] != po[:-1]]
        newt = newp | np.r_[True, ho[1:] != ho[:-1]]
        ps = np.maximum.accumulate(np.where(newp, pos, 0))
        ts = np.maximum.accumulate(np.where(newt, pos, 0))
        cum = np.cumsum(fo)
        before = lambda k: cum[k] - fo[k]  # noqa: E731  (sum of fo[:k])
        rank[ii] = (ts - ps + 1).astype(np.float64)
        above[ii] = before(ts) - before(ps)
    return {
        "n_live": n_live,
        "sum_fpc": sum_fpc,
        "sum_agb": sum_agb,
        "pidx": pidx,
        "rank": rank,
        "above": above,
        "n": n,
    }


# ================================================================================= entry-size model
class EntrySize:
    """Per-Type OLS of ln vegc, LAI, ln fpc_ind, ln D95 at entry on [1, ln agb, ln Wooddens, ln SLA,
    ln D95max,
    ln Age], with the residual covariance (multivariate-normal residual draws). Fallback 'pooled'
    for rare types."""

    def __init__(self, d: dict):
        self.d = d
        K = len(ENTRY_Y)
        self.B = np.zeros((tr.MAX_TREE_TYPE + 1, len(ENTRY_X) + 1, K))
        self.L = np.zeros((tr.MAX_TREE_TYPE + 1, K, K))
        self.lo = np.zeros((tr.MAX_TREE_TYPE + 1, K))
        self.hi = np.zeros((tr.MAX_TREE_TYPE + 1, K))
        for t in range(tr.MAX_TREE_TYPE + 1):
            r = d["types"].get(str(t), d["types"]["pooled"])
            self.B[t] = np.asarray(r["beta"])
            self.L[t] = np.linalg.cholesky(np.asarray(r["cov"]) + 1e-12 * np.eye(K))
            self.lo[t], self.hi[t] = r["y_min"], r["y_max"]

    @classmethod
    def load(cls, split: str) -> EntrySize:
        p = os.path.join(OUT, split, "entry_size.json")
        assert os.path.exists(p), (
            f"no entry-size model {p}: run `explore_de_struct_stepper.py entry --split {split}`"
        )
        return cls(json.load(open(p)))

    def draw(self, typ, agb, wd, sla, d95max, age, normals: np.ndarray) -> dict:
        t = np.asarray(typ, np.int64)
        X = np.column_stack(
            [
                np.ones(len(t)),
                np.log(agb),
                np.log(wd),
                np.log(sla),
                np.log(d95max),
                np.log(np.maximum(age, 1.0)),
            ]
        )
        mu = np.einsum("nj,njk->nk", X, self.B[t])
        y = mu + np.einsum("nkl,nl->nk", self.L[t], normals)
        y = np.clip(y, self.lo[t], self.hi[t])
        return {
            "vegc": np.exp(y[:, 0]),
            "LAI": np.maximum(y[:, 1], 1e-4),
            "fpc_ind": np.exp(y[:, 2]),
            "D95": np.exp(y[:, 3]),
        }


def stage_entry(a):
    mm = hd.split_members(a.split)
    fo = hd.folds().filter(pl.col("fold").is_in(list(hd.TRAIN_FOLDS)))
    parts = []
    for m in mm["train"]:
        fs = os.path.join(kn.RECR, m, "cb=dev", "*.parquet")
        parts.append(
            pl.scan_parquet(fs)
            .filter(pl.col("Type") <= tr.MAX_TREE_TYPE)
            .join(fo.lazy(), on="Cell", how="semi")
            .select(
                "Type",
                "Height",
                "agb",
                "vegc",
                "LAI",
                "fpc_ind",
                "D95",
                "Age",
                "Wooddens",
                "SLA",
                "D95max",
            )
            .collect()
        )
    R = pl.concat(parts).with_columns(
        [
            pl.col(c).cast(pl.Float64)
            for c in (
                "Height",
                "agb",
                "vegc",
                "LAI",
                "fpc_ind",
                "D95",
                "Age",
                "Wooddens",
                "SLA",
                "D95max",
            )
        ]
    )
    R = R.filter(
        (pl.col("agb") > 0)
        & (pl.col("vegc") > 0)
        & (pl.col("fpc_ind") > 0)
        & (pl.col("D95") > 0)
        & (pl.col("Age") >= 1)
    )
    coef = full_allometry(a.split)
    R = R.with_columns(
        ln_agb=pl.col("agb").log(),
        ln_wd=pl.col("Wooddens").log(),
        ln_sla=pl.col("SLA").log(),
        ln_d95max=pl.col("D95max").log(),
        ln_age=pl.col("Age").log(),
        ln_vegc=pl.col("vegc").log(),
        ln_fpc=pl.col("fpc_ind").log(),
        ln_D95=pl.col("D95").log(),
    )
    agb_inv = agb_from_height(
        R["Height"].to_numpy(),
        R["Wooddens"].to_numpy(),
        R["SLA"].to_numpy(),
        R["Type"].to_numpy(),
        coef,
    )
    lr = np.log(agb_inv) - R["ln_agb"].to_numpy()
    out = {
        "split": a.split,
        "members": mm["train"],
        "n": R.height,
        "x": ENTRY_X,
        "y": ENTRY_Y,
        "types": {},
        "allometry_inverse_log_agb_err": {"mean": float(lr.mean()), "sd": float(lr.std())},
    }

    def fit(g):
        X = np.column_stack([np.ones(g.height)] + [g[c].to_numpy() for c in ENTRY_X])
        Y = np.column_stack([g[c].to_numpy() for c in ENTRY_Y])
        beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
        res = Y - X @ beta
        r2 = 1 - res.var(0) / Y.var(0)
        return {
            "n": g.height,
            "beta": beta.tolist(),
            "cov": np.cov(res.T).tolist(),
            "r2": r2.tolist(),
            "y_min": np.quantile(Y, 0.001, axis=0).tolist(),
            "y_max": np.quantile(Y, 0.999, axis=0).tolist(),
        }

    out["types"]["pooled"] = fit(R)
    for (t,), g in R.group_by(["Type"]):
        if g.height >= 2000:
            out["types"][str(int(t))] = fit(g)
    od = os.path.join(OUT, a.split)
    os.makedirs(od, exist_ok=True)
    json.dump(out, open(os.path.join(od, "entry_size.json"), "w"), indent=1)
    log(json.dumps({k: (v["n"], [round(x, 3) for x in v["r2"]]) for k, v in out["types"].items()}))
    status(
        f"entry {a.split}: entry-size model on {R.height} training recruits; "
        "per-type R2 (ln vegc, LAI, ln fpc, "
        f"ln D95) "
        + "; ".join(f"{k}: {[round(x, 2) for x in v['r2']]}" for k, v in out["types"].items())
        + f"; inverse-allometry ln agb error mean {lr.mean():.3f} sd {lr.std():.3f}"
    )


# ====================================================================================== the stepper
class Struct:
    needs_bank = True

    def __init__(
        self,
        split: str = "DEV-A",
        ar: bool = True,
        cal: str | None = None,
        accept: str | None = None,
        accept_kwargs: dict | None = None,
        accept_oversample: int = 4,
        kappa_fire=None,
        kappa_rec=None,
        diag: bool = True,
    ):
        self.split, self.use_ar, self.cal_spec = split, bool(ar), cal
        self.accept_spec, self.accept_kwargs = accept, accept_kwargs or {}
        self.accept_m = int(accept_oversample)
        self.kappa_fire, self.kappa_rec = kappa_fire, kappa_rec
        self.diag_on = bool(diag)

    # ---------------------------------------------------------------- init
    def init(self, state, ctx):
        self.P = ctx["P"]
        self.H = hd.StructHeads.load(self.split)
        assert self.H.ar is not None, "B1 AR tables missing"
        self.PH = ph.load_heads(self.split)
        self.K = kn.RecruitKernel(self.P)
        self.allom = full_allometry(self.split)
        self.entry = EntrySize.load(self.split)
        self.gcm, self.seed = ctx["gcm"], int(ctx["seed"])
        self.cal = self._load_cal()
        self._apply_ar_settings()
        self.acceptor = None
        if self.accept_spec:
            mod, cls = self.accept_spec.split(":")
            C = getattr(importlib.import_module(mod), cls)
            self.acceptor = (
                C.load(self.split, **self.accept_kwargs)
                if hasattr(C, "load")
                else C(self.split, **self.accept_kwargs)
            )
        self._clim_obj: dict = {}
        self._clim: dict = {}
        cells = state.cell["cells"]
        t = state.tree
        # latent at the rollout start: stationary draw (spec: a 1985 start; other starts would use
        # the truth's
        # one-step residual of the last transition — not implemented, stationary there too, stated)
        typ = t["Type"].astype(np.int64)
        r0 = en.Rand(
            ctx["arm"], ctx["rep"], self.gcm
        )  # the engine's own counter-based stream (chunk-invariant)
        e = self._normals_rand(
            r0, "struct_z0", ctx["start"], t["Cell"], t["Patch"], t["Type"], t["ID"]
        )
        state.aux_tree["z"] = self._stationary(typ, hd.size_class(t["Height"]), e).astype(
            np.float64
        )
        # fuel input of the fire head: agb flagged dead at the start year (SH4 patch table of the
        # start member)
        npt = len(cells) * state.npatch
        agb_dead = np.zeros(npt)
        mem, _, _ = tr.registry()
        try:
            row = tr.historical_of(mem, self.gcm, self.seed) if ctx["start"] <= 2014 else None
            if row is not None:
                f = os.path.join(
                    ph.PATCH, "dev", row["member"], "cb=dev", f"y{ctx['start']}.parquet"
                )
                if os.path.exists(f):
                    Pt = pl.read_parquet(f, columns=["Cell", "Patch", "agb_dead_y"]).filter(
                        pl.col("Cell").is_in(cells.tolist())
                    )
                    ci = np.searchsorted(cells, Pt["Cell"].to_numpy())
                    agb_dead[ci * state.npatch + Pt["Patch"].to_numpy()] = (
                        Pt["agb_dead_y"].fill_null(0.0).to_numpy()
                    )
        except Exception as ex:  # noqa: BLE001 — the fire input defaults to 0, stated in the diag
            log(f"agb_dead_y at start not read: {ex}")
        state.aux_patch["agb_dead"] = agb_dead
        self.diag = {
            "arm": ctx["arm"],
            "gcm": self.gcm,
            "seed": self.seed,
            "rep": ctx["rep"],
            "clim_mode": ctx["clim_mode"],
            "split": self.split,
            "ar": self.use_ar,
            "cal": self.cal,
            "acceptance": self.accept_spec,
            "cells": [int(cells[0]), int(cells[-1])],
            "n_cells": len(cells),
            "start_agb_dead_sum": float(agb_dead.sum()),
            "years": [],
        }
        dd = os.path.join(
            OUT,
            "diag",
            ctx["arm"],
            f"{self.gcm}_s{self.seed}_{ctx['clim_mode'].replace(':', '')}_r{ctx['rep']}",
        )
        os.makedirs(dd, exist_ok=True)
        self.diag_path = os.path.join(dd, f"c{int(cells[0])}-{int(cells[-1])}.json")

    def _load_cal(self) -> dict | None:
        if self.cal_spec == "none":
            return None
        p = self.cal_spec or os.path.join(CAL, f"{self.split}.json")
        if os.path.exists(p):
            return {"path": p, **json.load(open(p))}
        return None

    def _apply_ar_settings(self):
        ar = {k: v.copy() for k, v in self.H.ar.items()}
        rho, sig = ar["rho"], ar["sigma"]
        sd = sig / np.sqrt(np.maximum(1 - rho**2, 1e-6))
        groups = {"G": [0], "W": [1], "size": SIZE_IDX}
        self.z_shift = np.zeros(len(hd.LATENT))
        if self.cal:
            for g, cols in groups.items():
                rho[..., cols] = np.clip(
                    rho[..., cols] * float(self.cal.get("rho_mult", {}).get(g, 1.0)), -0.99, 0.99
                )
                sd[..., cols] = sd[..., cols] * float(self.cal.get("sd_mult", {}).get(g, 1.0))
                self.z_shift[cols] = float(self.cal.get("z_shift", {}).get(g, 0.0))
        if not self.use_ar:
            rho[:] = 0.0
        ar["rho"], ar["sd"] = rho, sd
        ar["sigma"] = sd * np.sqrt(1 - rho**2)
        self.ar = ar

    def _stationary(self, typ, scls, e):
        ti, si = np.asarray(typ, np.int64) + 1, np.asarray(scls, np.int64) + 1
        return self.ar["sd"][ti, si] * np.einsum("nij,nj->ni", self.ar["L"][ti, si], e)

    def _ar_step(self, z, typ, scls, e):
        ti, si = np.asarray(typ, np.int64) + 1, np.asarray(scls, np.int64) + 1
        return self.ar["rho"][ti, si] * z + self.ar["sigma"][ti, si] * np.einsum(
            "nij,nj->ni", self.ar["L"][ti, si], e
        )

    @staticmethod
    def _normals_rand(rand, stream, year, *keys):
        return np.column_stack(
            [rand.normal(f"{stream}{j}", year, *keys) for j in range(len(hd.LATENT))]
        )

    # ------------------------------------------------- climate of year y (the heads need y and y+1)
    def _clim_year(self, ctx, year, cells):
        key = (ctx["traj"], int(year))
        if key not in self._clim:
            ck = ctx["traj"]
            if ck not in self._clim_obj:
                self._clim_obj[ck] = en.Climate(self.gcm, ck, self.seed, cells, ctx["clim_mode"])
            self._clim[key] = self._clim_obj[ck].year(int(year))
        return self._clim[key]

    def _keep_clim(self, ctx, year, frame):
        self._clim[(ctx["traj"], int(year))] = frame
        for k in [k for k in self._clim if k[1] < int(year) - 1 and k[1] != 2014]:
            self._clim.pop(k)

    # ---------------------------------------------------------------- the step
    def step(self, state, ctx, year, clim_y1, flags_y1, rand):
        t = state.tree
        n = state.n
        y, y1 = int(year), int(year) + 1
        cells = state.cell["cells"]
        npatch = state.npatch
        npt = len(cells) * npatch
        ci = state.cell_index(t["Cell"])
        typ = t["Type"].astype(np.int64)
        keys = (t["Cell"], t["Patch"], t["Type"], t["ID"])
        hidden0 = t["hidden"].astype(bool)
        printed = ~hidden0
        rh_on = int(flags_y1["rh_on"])
        cy = self._clim_year(ctx, y, cells)
        self._keep_clim(ctx, y1, clim_y1)
        assert np.array_equal(cy["Cell"].to_numpy(), cells) and np.array_equal(
            clim_y1["Cell"].to_numpy(), cells
        )

        # ---- 1 features
        pc = patch_context(state, printed)
        pidx = pc["pidx"]
        fr = {
            "_ri": np.arange(n),
            "Cell": t["Cell"].astype(np.int16),
            "Type": t["Type"].astype(np.int8),
        }
        for c in tr.TRAITS + ["Height", "agb", "vegc", "LAI", "fpc_ind", "D95", "Age"]:
            fr[c] = t[c]
        fr["c_y"] = t["c"].astype(np.int8)
        fr["n_live"], fr["sum_fpc"], fr["sum_agb"] = (
            pc["n_live"][pidx],
            pc["sum_fpc"][pidx],
            pc["sum_agb"][pidx],
        )
        fr["height_rank"], fr["fpc_above"] = pc["rank"], pc["above"]
        for g in ("fpc", "LAI", "agb"):
            v = state.patch.get(f"grass8_{g}")
            fr[f"grass8_{g}"] = (
                np.nan_to_num(v[pidx].astype(np.float64)) if v is not None else np.zeros(n)
            )
        lev = hd.climate_levels()
        for suf, cf in (("y", cy), ("y1", clim_y1)):
            M = cf.select([pl.col(c).cast(pl.Float64) for c in lev]).to_numpy()
            for j, c in enumerate(lev):
                fr[f"{c}_{suf}"] = M[ci, j]
        # add_features joins on (gcm, Cell): restore the tree order explicitly (a polars join need
        # not keep it)
        feat = self.H.features(pl.DataFrame(fr).with_columns(gcm=pl.lit(self.gcm))).sort("_ri")
        assert feat.height == n
        X = self.H.X(feat)
        scls = hd.size_class(t["Height"])

        # ---- 2 growth
        z = state.aux_tree["z"]
        d = self.H.sample(X, z + self.z_shift, typ, scls)
        G1 = d["G"]
        W1 = d["W"] * (rh_on != 0)
        agb = t["agb"].astype(np.float64)
        agb1 = agb * np.exp(d["dlagb"])
        vegc1 = t["vegc"].astype(np.float64) * np.exp(d["dlvegc"])
        lai1 = np.maximum(t["LAI"].astype(np.float64) + d["dlai"], 1e-4)
        fpc1 = t["fpc_ind"].astype(np.float64) * np.exp(d["dlfpc"])
        d951 = t["D95"].astype(np.float64) * np.exp(d["dld95"])
        h1 = self._height_next(t, agb, agb1, typ)

        # ---- 3 death (SH2 rules, C order) + survive + fire
        C1 = clim_y1.select(
            [pl.col(f"tstress_pft{k}").cast(pl.Float64) for k in range(self.P.n_pft)]
        ).to_numpy()
        ts = np.nan_to_num(C1[ci, typ])
        age_pre = t["Age"].astype(np.float64)
        mo = rl.mortality_step(
            typ, t["Wooddens"], age_pre, t["c"].astype(np.int64), G1, W1, ts, rh_on, self.P
        )
        dead_h = rand.uniform("struct_hazard", y, *keys) < mo["mort"]
        tc = clim_y1["tcold_month_tr20"].cast(pl.Float64).to_numpy()
        tw = clim_y1["twarm_month_tr20"].cast(pl.Float64).to_numpy()
        sv = rl.survive(tc, tw, self.P)[ci, typ]
        dead_s = ~dead_h & ~sv
        Xp0 = ph.patch_frame_from_state(
            state,
            clim_y1,
            dead_h | dead_s,
            np.zeros(n, bool),
            state.aux_patch.get("agb_dead"),
            self.P,
        )
        f = self.PH.fire_f(Xp0, kappa=self.kappa_fire)
        dead_f = (
            ~dead_h
            & ~dead_s
            & (rand.uniform("struct_fire", y, *keys) < rl.fire_kill_prob(typ, f[pidx], self.P))
        )
        dead = dead_h | dead_s | dead_f
        small = h1 < HEIGHT_MIN
        hidden1 = ~dead & small
        quiet_dead = dead & small  # dies below the print cut: never emitted, removed
        isdead_out = dead & ~small
        hidden_out = hidden1 | quiet_dead
        remove = quiet_dead

        # ---- 5 recruits: count (SH13 b) with this step's survivors, identity (B3 kernel),
        # entry state (SH13 c)
        Xp1 = ph.patch_frame_from_state(
            state, clim_y1, dead, hidden1, state.aux_patch.get("agb_dead"), self.P
        )
        mu = self.PH.recruit_mean(Xp1, kappa=self.kappa_rec)
        pcell = np.repeat(cells, npatch)
        ppat = np.tile(np.arange(npatch), len(cells))
        nrec = self.PH.recruit_draw(mu, rand.uniform("struct_nrec", y, pcell, ppat))
        R, zr = self._recruits(state, ctx, y1, clim_y1, flags_y1, rand, Xp1, nrec, pcell, ppat)

        # ---- latent of next year
        e = self._normals_rand(rand, "struct_e", y, *keys)
        z1 = self._ar_step(z, typ, hd.size_class(h1), e)

        # ---- bookkeeping
        agb_dead = np.bincount(pidx, weights=np.where(isdead_out, agb1, 0.0), minlength=npt)
        upd = {
            "agb": agb1,
            "vegc": vegc1,
            "LAI": lai1,
            "fpc_ind": fpc1,
            "D95": d951,
            "Height": h1,
            "Age": t["Age"] + 1,
            "c": np.minimum(mo["c"], 5),
            "G": G1,
            "W": W1,
            "d_agb_prev": agb1 - agb,
            "mort_npp": mo["mort_npp"],
            "mort_age": mo["mort_age"],
            "mort_water": mo["mort_water"],
            "mort_temp": mo["mort_temp"],
            "mort": mo["mort"],
        }
        if self.diag_on:
            nanc = {k: int(np.sum(~np.isfinite(np.asarray(v, np.float64)))) for k, v in upd.items()}
            live_next = ~dead & ~hidden1
            c_ge1 = np.minimum(mo["c"], 5) >= 1
            nr = len(R["Cell"]) if R else 0
            self.diag["years"].append(
                {
                    "scen": "Historical" if y1 <= 2014 else ctx["traj"],
                    "Year": y1,
                    "n_state": int(n),
                    "n_printed_living_y": int(printed.sum()),
                    "dead": int(dead.sum()),
                    "dead_printed": int((dead & printed).sum()),
                    "dead_hazard": int((dead_h & printed).sum()),
                    "hard_kill": int((dead_h & printed & (mo["mort"] >= 1)).sum()),
                    "c5_kill": int((dead_h & printed & (mo["c"] >= 5)).sum()),
                    "dead_survive": int((dead_s & printed).sum()),
                    "dead_fire": int((dead_f & printed).sum()),
                    "quiet_dead": int(quiet_dead.sum()),
                    "new_hidden": int((hidden1 & printed).sum()),
                    "reentered": int((~small & hidden0 & ~dead).sum()),
                    "living_printed_y1_old": int((live_next).sum()),
                    "c_ge1_living_y1_old": int((live_next & c_ge1).sum()),
                    "recruits": int(nr),
                    "recruit_mean_sum": float(mu.sum()),
                    "fire_f_mean": float(f.mean()),
                    "share_G_neg": float((G1[printed] < 0).mean()) if printed.any() else None,
                    "share_W_pos": float((W1[printed] > 0).mean()) if printed.any() else None,
                    "nan": {k: v for k, v in nanc.items() if v},
                    "rec_nan": int(
                        sum(
                            int(np.sum(~np.isfinite(np.asarray(R[k], np.float64))))
                            for k in ("Height", "agb", "vegc", "LAI", "fpc_ind", "D95", "Age")
                            + tuple(tr.TRAITS)
                        )
                        if nr
                        else 0
                    ),
                }
            )
            json.dump(self.diag, open(self.diag_path, "w"), indent=0, default=float)
        state.aux_patch["agb_dead"] = agb_dead
        self._hook(y, t, keys, hidden0, z, d, agb1, h1, dead_h, dead_s, dead_f, hidden1, mo, R)
        return en.StepOut(
            tree=upd,
            isdead=isdead_out,
            hidden=hidden_out,
            remove=remove,
            recruits=R,
            aux_tree={"z": z1},
            aux_recruits={"z": zr},
            aux_patch=state.aux_patch,
        )

    # ------------------------------------------------- overridable pieces (diagnostic subclasses)
    def _height_next(self, t, agb, agb1, typ):
        """Height of year y+1: the SH2 allometry of the new agb (the B5 closure)."""
        return rl.predict_height(agb1, t["Wooddens"], t["SLA"], typ, self.allom)

    def _hook(self, y, t, keys, hidden0, z, d, agb1, h1, dead_h, dead_s, dead_f, hidden1, mo, R):
        """No-op; a probe subclass dumps the step's internals here."""
        return None

    # ---------------------------------------------------------------- recruits
    def _recruits(self, state, ctx, y1, clim_y1, flags_y1, rand, Xp1, nrec, pcell, ppat):
        cells = state.cell["cells"]
        npatch = state.npatch
        tot = np.bincount(
            np.repeat(np.arange(len(cells)), npatch), weights=nrec, minlength=len(cells)
        ).astype(int)
        if tot.sum() == 0:
            return None, None
        el = self.K.eligible(
            clim_y1["tcold_month_tr20"].cast(pl.Float64).to_numpy(),
            clim_y1["twarm_month_tr20"].cast(pl.Float64).to_numpy(),
            clim_y1["gdd5"].cast(pl.Float64).to_numpy(),
            clim_y1["prec_ann"].cast(pl.Float64).to_numpy(),
        )
        build = str(rl.build_of(np.array([flags_y1["bin_feb2026"]]))[0])
        B = state.cell["bank"]
        bc = B["Cell"].to_numpy()
        barr = {k: B[k].to_numpy().astype(np.float64) for k, _ in kn.TRAIT_KEYS}
        btyp = B["Type"].to_numpy().astype(np.int64)
        bw = B["n_years"].to_numpy().astype(np.float64)
        out = {k: [] for k in ("Cell", "Patch", "Type") + tuple(tr.TRAITS)}
        unif, norm = [], []
        for i in np.flatnonzero(tot):
            c = int(cells[i])
            n_c = int(tot[i])
            rng = rand.generator("struct_kernel", y1, c)
            s, e_ = np.searchsorted(bc, c, "left"), np.searchsorted(bc, c, "right")
            bank = {k: v[s:e_] for k, v in barr.items()}
            bank["Type"], bank["w"] = btyp[s:e_], bw[s:e_]
            if self.acceptor is None:
                pr = self.K.propose(bank, n_c, el[i], build, rng)
            else:
                pr = self.K.propose(bank, n_c * self.accept_m, el[i], build, rng)
                if len(pr["Type"]):
                    w = np.asarray(
                        self.acceptor.weights(pr, {"Cell": c, "Year": y1, "clim_y1": clim_y1[i]}),
                        np.float64,
                    )
                    w = w / w.sum() if w.sum() > 0 else np.full(len(w), 1.0 / len(w))
                    pick = rng.choice(len(w), size=n_c, replace=True, p=w)
                    pr = {
                        k: (v[pick] if hasattr(v, "__len__") and len(v) == len(w) else v)
                        for k, v in pr.items()
                    }
            m = len(pr["Type"])
            if m == 0:
                continue
            pp = np.repeat(np.arange(npatch), nrec[i * npatch : (i + 1) * npatch])[:m]
            out["Cell"].append(np.full(m, c))
            out["Patch"].append(pp)
            out["Type"].append(np.asarray(pr["Type"], np.int64))
            for k in tr.TRAITS:
                out[k].append(np.asarray(pr[k], np.float64))
            unif.append(rng.random((m, 3)))
            norm.append(rng.standard_normal((m, len(ENTRY_Y) + len(hd.LATENT))))
        if not out["Cell"]:
            return None, None
        R = {k: np.concatenate(v) for k, v in out.items()}
        U, Nn = np.concatenate(unif), np.concatenate(norm)
        m = len(R["Cell"])
        rp = state.cell_index(R["Cell"]) * npatch + R["Patch"]
        Xr = Xp1.select(pl.all().gather(rp)).with_columns(
            Type=pl.Series(R["Type"].astype(np.float64))
        )
        h, age = self.PH.entry_draw(Xr, U[:, 0], U[:, 1], kappa=self.kappa_rec)
        js = self.PH.entry_sample(
            R["Type"], self.PH.clim_tercile(Xr["tmean_ann_y1"].to_numpy()), U[:, 2]
        )
        age = np.round(age)
        agb = agb_from_height(h, R["Wooddens"], R["SLA"], R["Type"], self.allom)
        sz = self.entry.draw(
            R["Type"], agb, R["Wooddens"], R["SLA"], R["D95max"], age, Nn[:, : len(ENTRY_Y)]
        )
        R.update(
            Height=h,
            Age=age,
            agb=agb,
            **sz,
            c=np.clip(np.nan_to_num(js["c"]), 0, 4).astype(np.int8),
            G=np.nan_to_num(js["G"]),
            W=np.zeros(m),
            d_agb_prev=np.zeros(m),
            isdead=np.zeros(m, bool),
            hidden=np.zeros(m, bool),
        )
        zr = self._stationary(R["Type"], hd.size_class(h), Nn[:, len(ENTRY_Y) :])
        return R, zr


# ====================================================================================== check stage
def truth_living_counts(
    gcm: str, seed: int, legs: list[str], cells: list[int], y0: int, y1: int
) -> pl.DataFrame:
    mem, _, _ = tr.registry()
    hist = tr.historical_of(mem, gcm, seed)
    out = []
    for leg in legs:
        parts = [pl.scan_parquet(hist["ind_dev_path"]).filter(pl.col("Year") <= 2014)]
        if leg != "Historical":
            r = mem.filter(
                (pl.col("gcm") == gcm)
                & (pl.col("scen") == leg)
                & (pl.col("seed") == seed)
                & ~pl.col("excluded")
            ).row(0, named=True)
            parts.append(pl.scan_parquet(r["ind_dev_path"]).filter(pl.col("Year") > 2014))
        lf = pl.concat(
            [p.select("Year", "Cell", "Type", "isdead") for p in parts], how="vertical_relaxed"
        ).filter(
            pl.col("Cell").is_in(cells)
            & (pl.col("Type") <= tr.MAX_TREE_TYPE)
            & pl.col("Year").is_between(y0, y1)
        )
        d = (
            lf.group_by("Year")
            .agg(
                truth_living=(pl.col("isdead") == 0).sum(), truth_dead=(pl.col("isdead") == 1).sum()
            )
            .collect()
        )
        out.append(d.with_columns(scen=pl.lit(leg)))
    return pl.concat(out)


def stage_check(a):
    run = json.load(open(os.path.join(a.run, "run.json")))
    E = pl.scan_parquet(os.path.join(a.run, "chunk_*", "y*.parquet"))
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
    nan = (
        E.select([(~pl.col(c).cast(pl.Float64).is_finite()).sum().alias(c) for c in num])
        .collect()
        .row(0, named=True)
    )
    A = (
        E.filter(pl.col("Type") <= tr.MAX_TREE_TYPE)
        .group_by("scen", "Year")
        .agg(
            arm_living=(pl.col("isdead") == 0).sum(),
            arm_dead=(pl.col("isdead") == 1).sum(),
            arm_c_ge1=((pl.col("isdead") == 0) & (pl.col("c") >= 1)).sum(),
        )
        .collect()
    )
    cells = sorted(
        {
            int(c)
            for f in glob.glob(os.path.join(a.run, "meta_*.json"))
            for c in json.load(open(f))["cells"]
        }
    )
    legs = run["legs"].split(",")
    T = truth_living_counts(
        run["gcm"], int(run["seed"]), legs, cells, int(run["start"]), int(run["end"])
    )
    rows = []
    for leg in legs:
        a_ = A.filter(pl.col("scen").is_in([leg, "Historical"])).drop("scen")
        rows.append(
            a_.join(
                T.filter(pl.col("scen") == leg).drop("scen"), on="Year", how="left"
            ).with_columns(scen=pl.lit(leg))
        )
    J = (
        pl.concat(rows)
        .sort("scen", "Year")
        .with_columns(
            ratio=pl.col("arm_living") / pl.col("truth_living"),
            arm_c_ge1_prev=pl.col("arm_c_ge1") / pl.col("arm_living"),
        )
    )
    # yearly death rate (flagged dead at y / living at y-1), arm and truth
    J = J.with_columns(
        arm_death_rate=pl.col("arm_dead") / pl.col("arm_living").shift(1).over("scen"),
        truth_death_rate=pl.col("truth_dead") / pl.col("truth_living").shift(1).over("scen"),
    )
    J.write_csv(os.path.join(a.run, "struct_check_yearly.csv"))
    metas = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(a.run, "meta_*.json")))]
    tot = {k: sum(m["timing_core_s"][k] for m in metas) for k in metas[0]["timing_core_s"]}
    ncy = sum(m["cell_years"] for m in metas)
    dg = sorted(
        glob.glob(
            os.path.join(
                OUT,
                "diag",
                run["arm"],
                f"{run['gcm']}_s{run['seed']}_{run['clim'].replace(':', '')}_r{run['rep']}",
                "*.json",
            )
        )
    )
    cy = set(cells)
    D = []
    for f in dg:
        d = json.load(open(f))
        if not (set(range(d["cells"][0], d["cells"][1] + 1)) & cy):
            continue
        D += d["years"]
    Dd = pl.DataFrame(D) if D else None
    summ = {
        "run": a.run,
        "n_cells": len(cells),
        "nan_emitted": {k: v for k, v in nan.items()},
        "any_nan": any(v > 0 for v in nan.values()),
        "count_ratio_min": float(J["ratio"].min()),
        "count_ratio_max": float(J["ratio"].max()),
        "within_2x_every_year": bool((J["ratio"] >= 0.5).all() and (J["ratio"] <= 2.0).all()),
        "count_ratio_last_year": {
            r["scen"]: r["ratio"]
            for r in J.filter(pl.col("Year") == J["Year"].max()).iter_rows(named=True)
        },
        "arm_c_ge1_prev_mean": float(J["arm_c_ge1_prev"].mean()),
        "arm_death_rate_mean": float(J["arm_death_rate"].drop_nulls().mean()),
        "truth_death_rate_mean": float(J["truth_death_rate"].drop_nulls().mean()),
        "core_s": tot,
        "cell_years": ncy,
        "core_s_per_cell_year": sum(tot.values()) / max(ncy, 1),
        "core_s_per_cell_year_step": tot["step"] / max(ncy, 1),
        "diag_files": len(dg),
    }
    if Dd is not None and Dd.height:
        s = Dd.select(
            pl.col("hard_kill").sum(),
            pl.col("c5_kill").sum(),
            pl.col("n_printed_living_y").sum(),
            pl.col("dead_printed").sum(),
            pl.col("dead_fire").sum(),
            pl.col("dead_survive").sum(),
            pl.col("c_ge1_living_y1_old").sum(),
            pl.col("living_printed_y1_old").sum(),
            pl.col("recruits").sum(),
            pl.col("quiet_dead").sum(),
            pl.col("new_hidden").sum(),
            pl.col("reentered").sum(),
        ).row(0, named=True)
        npl = max(s["n_printed_living_y"], 1)
        summ["diag"] = {
            "hard_kill_rate_per_tree_yr": s["hard_kill"] / npl,
            "c5_kill_rate": s["c5_kill"] / npl,
            "death_rate_printed": s["dead_printed"] / npl,
            "fire_death_rate": s["dead_fire"] / npl,
            "survive_death_rate": s["dead_survive"] / npl,
            "c_ge1_prevalence_surviving_old_trees": s["c_ge1_living_y1_old"]
            / max(s["living_printed_y1_old"], 1),
            "recruits_per_tree_yr": s["recruits"] / npl,
            "quiet_dead": s["quiet_dead"],
            "new_hidden_per_tree_yr": s["new_hidden"] / npl,
            "reentered": s["reentered"],
            "share_G_neg_mean": float(Dd["share_G_neg"].drop_nulls().mean()),
            "share_W_pos_mean": float(Dd["share_W_pos"].drop_nulls().mean()),
            "fire_f_mean": float(Dd["fire_f_mean"].mean()),
            "nan_years": int(sum(1 for r in D if r["nan"] or r["rec_nan"])),
        }
    json.dump(summ, open(os.path.join(a.run, "struct_check.json"), "w"), indent=1, default=float)
    print(json.dumps(summ, indent=1, default=float))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["entry", "check"])
    ap.add_argument("--split", default="DEV-A")
    ap.add_argument("--run")
    a = ap.parse_args(argv)
    {"entry": stage_entry, "check": stage_check}[a.stage](a)


if __name__ == "__main__":
    main()
