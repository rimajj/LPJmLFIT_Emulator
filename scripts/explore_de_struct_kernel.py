#!/usr/bin/env python3
"""explore_de_struct_kernel.py — LINE X, Germany data-driven emulator, B-STRUCT item B3: RECRUITMENT KERNEL.

The original model's own recruit-identity rule, as a proposal generator on the SH2 rule library (no learning):

  for each new sapling of a cell in establishment year Y
    channel  inheritance with probability w = 4 / (4 + n_elig)   (rl.inherit_weight; n_elig from rl.eligible on the
             year-Y climate: 20-yr tcold/twarm buffers incl. Y, the year's gdd5 and precipitation), forced to the
             background channel when the bank is empty; else background
    inherit  parent drawn from the cell seedbank with weight n_years (= uniformly over printed tree-years in
             [Y - max_age, Y - 1]); Type = the parent's; traits by rl.inherit_traits with the binary of year Y
             (Dec-2025 build: Wooddens / D95max bounded by PFT 0's interval; Feb-2026 build: own interval)
    background  Type uniform over the PFTs eligible in Y; traits uniform on the own intervals (rl.background_traits)
    then     Longevity = rl.longevity_of(SLA, Type) (the SLA corridor), beta_root = rl.getbetaroot(D95max)

API (what a rollout stepper calls)
  K = RecruitKernel()
  out = K.propose(bank, n, elig, build, rng)
      bank   dict of numpy arrays for ONE cell: Type, SLA, Wooddens, D95max, minwscal, w (multiplicity = n_years)
             (K.bank_from_frame(engine_bank_frame_of_that_cell) builds it from the SH5 / engine bank layout)
      n      number of saplings; elig bool[n_pft] for year Y; build "dec2025" | "feb2026" (rl.build_of(flag))
      rng    numpy Generator (the engine's Rand.generator(stream, year, cell) keeps chunks invariant)
      -> dict: Type, channel (1 inherit / 0 background), parent (bank row or -1), SLA, Wooddens, D95max, minwscal,
         Longevity, beta_root
  K.propose(..., force_type=k) draws a sapling CONDITIONED on being PFT k: P(inherit | k) = 4 pi_k / (4 pi_k + elig_k)
      (rl.p_inherit_given_type), parent among the type-k entries — used by the gates to compare with observed recruits
      of the same type.

GATES (truth parents = the bank rebuilt from the original model's own printed trees; per member, recruits established
2015-2034 and printed by 2044; members MPI/ACCESS ssp370 s1 = Dec-2025 build, MPI/ACCESS ssp245 s1 = Feb-2026 build)
  traits_out_share   per build: share of recruits with Wooddens / D95max outside their own PFT interval, kernel
                     (type-conditioned on each observed recruit's cell-year and Type) vs observed, pooled over PFTs:
                     |pred - obs| <= max(25 % obs, 3 SE) (the SH2 tolerance). SLA / minwscal: kernel and observed 0.
  longevity_sla      within-Type corr(SLA, Longevity) of the kernel's proposals in [-0.98, -0.66], for every Type
                     with visible recruits (Types without any are reported, not gated); the observed r and the SLA-
                     corridor residual sd (kernel vs observed) beside it
  beta_root_exact    rl.getbetaroot(D95max) == the printed beta_root of every observed recruit (max rel err <= 1e-5)
  eligibility        per-PFT eligible share of cell-years through the kernel's eligibility call == the structured
                     probe C (same basis, max |diff| <= 1e-9) and the C-faithful shares reported
  bank_vs_SH5        the rebuilt year-2015 bank (window 1965-2014) == SH5's 2014 bank.parquet: total multiplicity per
                     cell and per (cell, Type)
  REPORTED, NOT GATED (expected to miss: the >5 m recruits are a selected sample of what the kernel draws):
  per-PFT out shares, the Type mix of proposals vs visible recruits, K2 P(D95 out | Wooddens out).
STAGES  gate --member M · report · submit
"""
from __future__ import annotations

import argparse
import glob
import json
import math
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
OUT = os.environ.get("B3_OUT", os.path.join(XDE, "struct", "kernel"))
STATUS = os.path.join(XDE, "_status", "B3.md")
REPORTS = os.path.join(XDE, "_reports")
RECR = os.path.join(XDE, "shared", "recruits", "dev")
INIT = os.path.join(XDE, "shared", "init", "dev")
PROBE_C = os.path.join(XDE, "struct", "probe_C_estab_eligibility.csv")
PY = tr.PY
LOGDIR = os.path.join(REPO, "logs")
GATE_MEMBERS = ["MPI-ESM1-2-HR_ssp370_s1_w2015", "ACCESS-CM2_ssp370_s1_w2015", "MPI-ESM1-2-HR_ssp245_s1_w2015",
                "ACCESS-CM2_ssp245_s1_w2015"]
Y_EST = (2015, 2034)
M_UNCOND = int(os.environ.get("B3_M_UNCOND", "300"))   # unconditional proposals per (cell, Y)
M_COND = int(os.environ.get("B3_M_COND", "8"))         # type-conditioned proposals per observed recruit
TRAIT_KEYS = [("SLA", "sla"), ("Wooddens", "wooddens"), ("D95max", "d95max"), ("minwscal", "minwscal")]
LON_BAND = (-0.98, -0.66)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def status(line: str):
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    with open(STATUS, "a") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} {line}\n")


# ================================================================================================ the kernel
class RecruitKernel:
    def __init__(self, P=None):
        self.P = P or rl.load_params()
        self.n_pft = self.P.n_pft

    @staticmethod
    def bank_from_frame(b: pl.DataFrame) -> dict:
        """Engine / SH5 bank rows of ONE cell -> kernel bank dict (weight = n_years)."""
        d = {k: b[k].to_numpy().astype(np.float64) for k, _ in TRAIT_KEYS}
        d["Type"] = b["Type"].to_numpy().astype(np.int64)
        d["w"] = b["n_years"].to_numpy().astype(np.float64) if "n_years" in b.columns else np.ones(b.height)
        return d

    def eligible(self, tcold20, twarm20, gdd5, prec_ann) -> np.ndarray:
        return rl.eligible(tcold20, twarm20, gdd5, prec_ann, self.P)

    def _draw_parent(self, bank, n, rng, typ=None):
        w = bank["w"] if typ is None else bank["w"] * (bank["Type"] == typ)
        cw = np.cumsum(w)
        if cw.size == 0 or cw[-1] <= 0:
            return np.full(n, -1, np.int64)
        return np.minimum(np.searchsorted(cw, rng.random(n) * cw[-1], side="right"), cw.size - 1)

    def propose(self, bank: dict, n: int, elig, build: str, rng: np.random.Generator, force_type=None) -> dict:
        P = self.P
        elig = np.asarray(elig, dtype=bool)
        n_el = int(elig.sum())
        nb = 0 if bank is None else int(bank["w"].size)
        wsum = 0.0 if nb == 0 else float(bank["w"].sum())
        if force_type is None:
            p_inh = float(rl.inherit_weight(n_el, P)) if wsum > 0 else 0.0
            if wsum <= 0 and n_el == 0:
                return {k: np.zeros(0) for k in ("Type", "channel", "parent", "SLA", "Wooddens", "D95max",
                                                 "minwscal", "Longevity", "beta_root")}
            inh = rng.random(n) < p_inh
            par = np.where(inh, self._draw_parent(bank, n, rng) if nb else -1, -1)
            el_idx = np.flatnonzero(elig)
            bg_t = el_idx[np.minimum((rng.random(n) * max(n_el, 1)).astype(np.int64), max(n_el, 1) - 1)] \
                if n_el else np.zeros(n, np.int64)
            typ = np.where(inh, bank["Type"][np.maximum(par, 0)] if nb else 0, bg_t)
        else:
            k = int(force_type)
            pi_k = float(bank["w"][bank["Type"] == k].sum() / wsum) if wsum > 0 else 0.0
            if pi_k == 0 and not elig[k]:
                return {"impossible": True}   # neither channel can make PFT k in this cell-year
            p_inh = float(rl.p_inherit_given_type(pi_k, float(elig[k]), P))   # = 1 when k is ineligible
            inh = rng.random(n) < p_inh
            par = np.where(inh, self._draw_parent(bank, n, rng, typ=k), -1)
            typ = np.full(n, k, np.int64)
        out = {"Type": typ, "channel": inh.astype(np.int8), "parent": par}
        bg = rl.background_traits(typ, rng, P)
        if nb and inh.any():
            pp = np.maximum(par, 0)
            new = rl.inherit_traits(typ, {key: bank[key][pp] for key, _ in TRAIT_KEYS}, build, rng, P)
        else:
            new = bg
        for key, _ in TRAIT_KEYS:
            out[key] = np.where(inh, new[key], bg[key])
        out["Longevity"] = rl.longevity_of(out["SLA"], typ, rng, P)
        out["beta_root"] = rl.getbetaroot(out["D95max"], P)
        return out

    def outside(self, key: str, val, typ) -> np.ndarray:
        pre = dict(TRAIT_KEYS)[key]
        t = np.asarray(typ, np.int64)
        lo, hi = self.P[f"{pre}_low"][t], self.P[f"{pre}_high"][t]
        v = np.asarray(val, np.float64)
        return (v < lo * (1 - 1e-6)) | (v > hi * (1 + 1e-6))


# ================================================================================================ truth data
def chain_of(member: str) -> list[str]:
    gcm, scen, s, _ = member.rsplit("_", 3)
    return [f"{gcm}_Historical_{s}_h1985", member]


def tree_years(member: str) -> pl.DataFrame:
    """Every printed tree-year (living rows + flagged-dead rows) of the member's chain, with traits: the seedbank's raw
    material (SH5 / engine semantics: printed rows incl. flagged dead). Living rows come from the transition table
    (Year = y); flagged-dead rows from the converted ind tables (rl._scan_dev, isdead == 1), which also holds the stems
    printed for the first time already flagged dead (no living row anywhere)."""
    cols = ["Cell", "Patch", "Type", "ID", "sla_i", "wd_i", "SLA", "Wooddens", "D95max", "minwscal"]
    parts = []
    chain = chain_of(member)
    for m in chain:
        lf = pl.scan_parquet(os.path.join(tr.TRANS, "dev", m, "cb=dev", "*.parquet"))
        parts.append(lf.select(cols + [pl.col("Year").cast(pl.Int16)]).collect())
    dev_cells = parts[0].select(pl.col("Cell").unique())
    for m in chain:
        dead = tr.with_key(rl._scan_dev(m).filter(pl.col("isdead") == 1)
                           .select("Cell", "Patch", "Type", "ID", "SLA", "Wooddens", "D95max", "minwscal", "Year")
                           .collect())
        dead = dead.with_columns(pl.col("Cell").cast(pl.Int16)).join(dev_cells, on="Cell", how="semi")
        parts.append(dead.select([pl.col(c).cast(parts[0][c].dtype) for c in cols + ["Year"]]))
    return pl.concat(parts).unique(subset=["Cell", "Patch", "Type", "ID", "sla_i", "wd_i", "Year"]).filter(
        pl.col("Type") <= 6)


def bank_arrays(ty: pl.DataFrame) -> dict:
    bc = ty.sort("Cell", "Year")
    out = {"kc": bc["Cell"].to_numpy().astype(np.int64) * 10000 + bc["Year"].to_numpy().astype(np.int64),
           "c_rows": {k: bc[k].to_numpy().astype(np.float64) for k, _ in TRAIT_KEYS},
           "c_type": bc["Type"].to_numpy().astype(np.int64)}
    return out


def cell_bank(B: dict, cell: int, Y: int, max_age: int) -> dict:
    """Bank of one cell for establishment year Y: printed tree-years in [Y - max_age, Y - 1], weight 1 each
    (= n_years per tree)."""
    s = np.searchsorted(B["kc"], cell * 10000 + Y - max_age, "left")
    e = np.searchsorted(B["kc"], cell * 10000 + Y - 1, "right")
    d = {k: B["c_rows"][k][s:e] for k, _ in TRAIT_KEYS}
    d["Type"] = B["c_type"][s:e]
    d["w"] = np.ones(e - s)
    return d


def climate_est(member: str, cells: np.ndarray, years: range) -> pl.DataFrame:
    gcm, scen, s, _ = member.rsplit("_", 3)
    seed = int(s[1:])
    fr = pl.DataFrame({"Cell": np.repeat(cells, len(years)).astype(np.int16),
                       "Year": np.tile(np.array(list(years)), len(cells)).astype(np.int16)}).with_columns(
        gcm=pl.lit(gcm), traj=pl.lit(scen), seed=pl.lit(seed, pl.Int8))
    c = tr.join_climate(fr, cols=["tcold_month_tr20", "twarm_month_tr20", "gdd5", "prec_ann"], years=("y",))
    seg = pl.read_parquet(os.path.join(tr.REG, "segments.parquet")).filter(
        (pl.col("gcm") == gcm) & (pl.col("scen") == scen) & (pl.col("seed") == seed)).select(
        pl.col("Year").cast(pl.Int16), "bin_feb2026")
    return c.join(seg, on="Year", how="left")


def observed_recruits(member: str) -> pl.DataFrame:
    r = pl.read_parquet(os.path.join(RECR, member, "cb=dev", "*.parquet"))
    return r.with_columns(y_est=(pl.col("Year_entry").cast(pl.Int32) - pl.col("Age").round(0).cast(pl.Int32))
                          .cast(pl.Int16)).filter(pl.col("y_est").is_between(*Y_EST) & (pl.col("Type") <= 6))


# ================================================================================================ gate stage
def _tol(obs, n, pred, npred):
    se = math.sqrt(max(obs * (1 - obs), 0) / max(n, 1) + max(pred * (1 - pred), 0) / max(npred, 1))
    return max(0.25 * obs, 3 * se)


def stage_gate(a):
    K = RecruitKernel()
    P = K.P
    max_age = int(P.g["max_age"])
    for member in a.member:
        t0 = time.time()
        rl.assert_usable(member)
        ty = tree_years(member)
        B = bank_arrays(ty)
        log(f"{member}: {ty.height} printed tree-years ({time.time() - t0:.0f} s)")
        rec = observed_recruits(member)
        cells = np.unique(ty["Cell"].to_numpy())
        years = range(Y_EST[0], Y_EST[1] + 1)
        cl = climate_est(member, cells, years)
        el = K.eligible(cl["tcold_month_tr20_y"].to_numpy(), cl["twarm_month_tr20_y"].to_numpy(),
                        cl["gdd5_y"].to_numpy(), cl["prec_ann_y"].to_numpy())
        ckey = cl["Cell"].to_numpy().astype(np.int64) * 10000 + cl["Year"].to_numpy().astype(np.int64)
        ELIG = dict(zip(ckey.tolist(), el, strict=True))
        BUILD = dict(zip(ckey.tolist(), rl.build_of(cl["bin_feb2026"].to_numpy()), strict=True))
        res = {"member": member, "n_tree_years": ty.height, "n_recruits_used": rec.height,
               "build_share": {b: float(np.mean(np.array(list(BUILD.values())) == b)) for b in ("dec2025", "feb2026")}}
        # ---------------- (1) unconditional proposals per (cell, Y)
        rng = np.random.default_rng(20261002)
        props = []
        for c in cells:
            for Y in years:
                k = int(c) * 10000 + Y
                bank = cell_bank(B, int(c), Y, max_age)
                o = K.propose(bank, M_UNCOND, ELIG[k], BUILD[k], rng)
                if len(o["Type"]):
                    props.append(pl.DataFrame({"Cell": np.full(len(o["Type"]), c, np.int16),
                                               "y_est": np.full(len(o["Type"]), Y, np.int16),
                                               "n_elig": np.full(len(o["Type"]), int(ELIG[k].sum()), np.int8),
                                               **{kk: o[kk] for kk in ("Type", "channel", "SLA", "Wooddens", "D95max",
                                                                         "minwscal", "Longevity", "beta_root")}}))
        PR = pl.concat(props)
        log(f"{member}: {PR.height} unconditional proposals ({time.time() - t0:.0f} s)")
        pt = PR["Type"].to_numpy()
        res["proposals"] = {"n": PR.height, "share_inherit": float(PR["channel"].mean()),
                            "mean_inherit_weight_expected": float(np.mean(rl.inherit_weight(PR["n_elig"].to_numpy(),
                                                                                            P))),
                            "type_mix": {int(t): float(np.mean(pt == t)) for t in np.unique(pt)},
                            "out_share_raw": {k: float(K.outside(k, PR[k].to_numpy(), pt).mean())
                                              for k, _ in TRAIT_KEYS}}
        ot = rec["Type"].to_numpy()
        res["visible_type_mix"] = {int(t): float(np.mean(ot == t)) for t in np.unique(ot)}
        # Longevity-SLA correlation within Type
        lon = {}
        for t in np.unique(pt):
            mp = pt == t
            mo = ot == t
            if mp.sum() < 1000:
                continue
            rk = float(np.corrcoef(PR["SLA"].to_numpy()[mp], PR["Longevity"].to_numpy()[mp])[0, 1])
            ro = (float(np.corrcoef(rec["SLA"].to_numpy()[mo], rec["Longevity"].to_numpy()[mo])[0, 1])
                  if mo.sum() >= 200 else None)
            zk = rl.longevity_z(PR["Longevity"].to_numpy()[mp], PR["SLA"].to_numpy()[mp], pt[mp], P)
            zo = rl.longevity_z(rec["Longevity"].to_numpy()[mo], rec["SLA"].to_numpy()[mo], ot[mo], P) \
                if mo.sum() >= 200 else None
            lon[int(t)] = {"kernel_r": rk, "observed_r": ro, "n_kernel": int(mp.sum()), "n_obs": int(mo.sum()),
                           "kernel_corridor_z_sd": float(zk.std()),
                           "observed_corridor_z_sd": float(zo.std()) if zo is not None else None,
                           "observed_corridor_z_mean": float(zo.mean()) if zo is not None else None,
                           "gated": ro is not None,
                           "pass": bool(LON_BAND[0] <= rk <= LON_BAND[1]) if ro is not None else None}
        res["longevity_sla"] = lon
        # beta_root exactness on the observed recruits
        br = rl.getbetaroot(rec["D95max"].to_numpy(), P)
        bo = rec["beta_root"].to_numpy().astype(np.float64)
        rel = np.abs(br - bo) / np.maximum(np.abs(bo), 1e-12)
        res["beta_root"] = {"n": int(bo.size), "max_rel_err": float(rel.max()), "share_rel_le_1e-5": float(
            np.mean(rel <= 1e-5)), "pass": bool(np.quantile(rel, 0.999) <= 1e-5)}
        # longevity corridor bounds on observed (|z| <= 2 by construction)
        z = rl.longevity_z(rec["Longevity"].to_numpy(), rec["SLA"].to_numpy(), ot, P)
        res["longevity_z_observed_max_abs"] = float(np.nanmax(np.abs(z)))
        # ---------------- (2) type-conditioned proposals per observed recruit
        rec = rec.sort("Cell", "y_est", "Type")
        rc, ry, rt = (rec["Cell"].to_numpy().astype(np.int64), rec["y_est"].to_numpy().astype(np.int64),
                      rec["Type"].to_numpy().astype(np.int64))
        pred = {k: np.full(rec.height, np.nan) for k in ("Wooddens", "D95max", "SLA", "minwscal", "joint", "pinh")}
        grp = np.flatnonzero(np.r_[True, (np.diff(rc) != 0) | (np.diff(ry) != 0) | (np.diff(rt) != 0)])
        ends = np.r_[grp[1:], rec.height]
        for s, e in zip(grp, ends, strict=True):
            c, Y, t = int(rc[s]), int(ry[s]), int(rt[s])
            k = c * 10000 + Y
            if k not in ELIG:
                continue
            bank = cell_bank(B, c, Y, max_age)
            n = (e - s) * M_COND
            o = K.propose(bank, n, ELIG[k], BUILD[k], rng, force_type=t)
            if o.get("impossible"):
                continue
            ow = K.outside("Wooddens", o["Wooddens"], o["Type"])
            od = K.outside("D95max", o["D95max"], o["Type"])
            pred["Wooddens"][s:e] = ow.mean()
            pred["D95max"][s:e] = od.mean()
            pred["joint"][s:e] = (ow & od).mean()
            pred["SLA"][s:e] = K.outside("SLA", o["SLA"], o["Type"]).mean()
            pred["minwscal"][s:e] = K.outside("minwscal", o["minwscal"], o["Type"]).mean()
            pred["pinh"][s:e] = o["channel"].mean()
        obs = {k: K.outside(k, rec[k].to_numpy(), rt) for k, _ in TRAIT_KEYS}
        bld = np.array([BUILD.get(int(c) * 10000 + int(y), "") for c, y in zip(rc, ry, strict=True)])
        ok = np.isfinite(pred["Wooddens"])
        rows = []
        for b in ("dec2025", "feb2026"):
            for t in [None] + sorted(np.unique(rt).tolist()):
                m = ok & (bld == b) & ((rt == t) if t is not None else True)
                n = int(m.sum())
                if n < 200:
                    continue
                d = {"build": b, "Type": -1 if t is None else int(t), "n": n, "mean_p_inherit": float(
                    pred["pinh"][m].mean())}
                for k in ("Wooddens", "D95max", "SLA", "minwscal"):
                    ob, pr = float(obs[k][m].mean()), float(pred[k][m].mean())
                    tol = _tol(ob, n, pr, n * M_COND)
                    d[k] = {"obs": ob, "pred": pr, "tol": tol, "pass": bool(abs(pr - ob) <= tol),
                            "ratio_obs_pred": ob / pr if pr > 0 else None}
                wo = m & obs["Wooddens"]
                if wo.sum() >= 50:
                    den = float(pred["Wooddens"][m].sum())
                    d["K2_P_d95out_given_wdout"] = {"obs": float(obs["D95max"][wo].mean()), "n": int(wo.sum()),
                                                    "pred": float(pred["joint"][m].sum()) / den if den > 0 else None}
                rows.append(d)
        res["traits_out_share"] = rows
        res["coverage_conditioned"] = float(ok.mean())
        # ---------------- bank vs SH5 (window [1965, 2014] = establishment year 2015)
        gcm, scen, s_, _ = member.rsplit("_", 3)
        sh5 = os.path.join(INIT, f"{gcm}_Historical_{s_}_2014", "cb=dev", "bank.parquet")
        if os.path.exists(sh5):
            b5 = pl.read_parquet(sh5).group_by("Cell", "Type").agg(w5=pl.col("n_years").cast(pl.Int64).sum())
            mine = (ty.filter(pl.col("Year").is_between(2015 - max_age, 2014)).group_by("Cell", "Type")
                    .agg(wm=pl.len().cast(pl.Int64)))
            j = b5.join(mine, on=["Cell", "Type"], how="full", coalesce=True).fill_null(0)
            res["bank_vs_SH5_2014"] = {"groups": j.height, "groups_differ": int((j["w5"] != j["wm"]).sum()),
                                       "total_SH5": int(j["w5"].sum()), "total_rebuilt": int(j["wm"].sum()),
                                       "pass": bool((j["w5"] == j["wm"]).all())}
        od = os.path.join(OUT, member)
        os.makedirs(od, exist_ok=True)
        json.dump(res, open(os.path.join(od, "gate.json"), "w"), indent=1)
        PR.filter(pl.col("Cell") % 50 == 0).write_parquet(os.path.join(od, "proposals_sample.parquet"))
        status(f"gate {member}: {PR.height} proposals, {rec.height} recruits, {time.time() - t0:.0f} s")


def stage_eligibility(a):
    """Probe C reproduced through the kernel's eligibility call, on probe C's basis and the C-faithful one."""
    K = RecruitKernel()
    pc = pl.read_csv(PROBE_C)
    ex = rl.excluded_members()
    rows, md = [], 0.0
    folds = pl.read_parquet(os.path.join(tr.REG, "folds.parquet")).filter(pl.col("is_dev"))
    cells = folds["Cell"].to_numpy()
    for r in pc.iter_rows(named=True):
        m = r["member"]
        if m in ex:
            continue
        gcm, scen, s, win = m.rsplit("_", 3)
        yrs = {"h1985": range(1985, 2015), "w2015": range(2015, 2045)}[win]
        fr = pl.DataFrame({"Cell": np.repeat(cells, len(yrs)).astype(np.int16),
                           "Year": np.tile(np.array(list(yrs)), len(cells)).astype(np.int16)}).with_columns(
            gcm=pl.lit(gcm), traj=pl.lit(scen), seed=pl.lit(int(s[1:]), pl.Int8))
        c = tr.join_climate(fr, cols=["tcold_month_tr20", "twarm_month_tr20", "gdd5", "gdd5_tr20", "prec_ann"],
                            years=("y",))
        e_probe = K.eligible(c["tcold_month_tr20_y"].to_numpy(), c["twarm_month_tr20_y"].to_numpy(),
                             c["gdd5_tr20_y"].to_numpy(), np.full(c.height, 1e9))
        e_c = K.eligible(c["tcold_month_tr20_y"].to_numpy(), c["twarm_month_tr20_y"].to_numpy(),
                         c["gdd5_y"].to_numpy(), c["prec_ann_y"].to_numpy())
        row = {"member": m, "n_cell_years": c.height, "mean_n_eligible_faithful": float(e_c.sum(1).mean()),
               "mean_inherit_weight_faithful": float(rl.inherit_weight(e_c.sum(1), K.P).mean())}
        for k in range(K.n_pft):
            row[f"elig_{k}_probeC"] = float(r[f"elig_{k}"])
            row[f"elig_{k}_kernel_probe_basis"] = float(e_probe[:, k].mean())
            row[f"elig_{k}_kernel_faithful"] = float(e_c[:, k].mean())
            md = max(md, abs(row[f"elig_{k}_kernel_probe_basis"] - row[f"elig_{k}_probeC"]))
        rows.append(row)
    out = {"rows": rows, "max_abs_diff_vs_probeC": md, "pass": bool(md <= 1e-9)}
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(os.path.join(OUT, "eligibility.json"), "w"), indent=1)
    status(f"eligibility: max |kernel - probe C| = {md:.2e} over {len(rows)} usable members")


def stage_report(a):
    gates = {}
    for f in sorted(glob.glob(os.path.join(OUT, "*", "gate.json"))):
        g = json.load(open(f))
        gates[g["member"]] = g
    ep = os.path.join(OUT, "eligibility.json")
    el = json.load(open(ep)) if os.path.exists(ep) else None
    summ = {}
    for m, g in gates.items():
        pooled = [r for r in g["traits_out_share"] if r["Type"] == -1]
        summ[m] = {"pooled_out_share": {r["build"]: {k: {kk: r[k][kk] for kk in ("obs", "pred", "pass")}
                                                     for k in ("Wooddens", "D95max", "SLA", "minwscal")}
                                        for r in pooled},
                   "per_type_pass": {f"{r['build']}_T{r['Type']}": {k: r[k]["pass"] for k in ("Wooddens", "D95max")}
                                     for r in g["traits_out_share"] if r["Type"] >= 0},
                   "longevity_sla": g["longevity_sla"], "beta_root_pass": g["beta_root"]["pass"],
                   "bank_vs_SH5": g.get("bank_vs_SH5_2014"), "share_inherit": g["proposals"]["share_inherit"],
                   "proposal_type_mix": g["proposals"]["type_mix"], "visible_type_mix": g["visible_type_mix"]}
    gate_pass = {
        "traits_out_share_pooled": all(r[k]["pass"] for g in gates.values() for r in g["traits_out_share"]
                                       if r["Type"] == -1 for k in ("Wooddens", "D95max", "SLA", "minwscal")),
        "longevity_sla": all(v["pass"] for g in gates.values() for v in g["longevity_sla"].values() if v["gated"]),
        "beta_root_exact": all(g["beta_root"]["pass"] for g in gates.values()),
        "eligibility_vs_probeC": bool(el and el["pass"]),
        "bank_vs_SH5": all((g.get("bank_vs_SH5_2014") or {}).get("pass", False) for g in gates.values())}
    rep = {"item": "B3", "basis": f"recruits established {Y_EST[0]}-{Y_EST[1]} and printed by 2044 on the 907 dev "
                                  "cells; truth parents = printed tree-years of the same chain",
           "gate_pass": gate_pass, "summary": summ, "eligibility": el, "members": list(gates)}
    os.makedirs(REPORTS, exist_ok=True)
    json.dump(rep, open(os.path.join(REPORTS, "r2_B3.json"), "w"), indent=1)
    log(json.dumps(gate_pass))
    status(f"report: {gate_pass}")


def stage_submit(a):
    me = os.path.abspath(__file__)
    jd = os.path.join(XDE, "_jobs")
    os.makedirs(jd, exist_ok=True)
    ms = " ".join(GATE_MEMBERS)
    p = os.path.join(jd, "X-de-B3-gate.jcf")
    open(p, "w").write("\n".join([
        "#!/bin/bash", "#SBATCH --job-name=X-de-B3-gate", "#SBATCH --account=waldspektrum",
        "#SBATCH --partition=standard", "#SBATCH --qos=short", "#SBATCH --cpus-per-task=16",
        "#SBATCH --time=03:00:00", f"#SBATCH --array=0-{len(GATE_MEMBERS) - 1}",
        f"#SBATCH --output={LOGDIR}/X-de-B3-gate.%A_%a.out", "set -eu", f"cd {REPO}", "export PYTHONUNBUFFERED=1",
        f"M=({ms})", f"{PY} {me} gate --member ${{M[$SLURM_ARRAY_TASK_ID]}}",
        "if [ $SLURM_ARRAY_TASK_ID -eq 0 ]; then " + f"{PY} {me} eligibility; fi", 'echo "=== JOB DONE ==="']) + "\n")
    jid = subprocess.run(["sbatch", "--parsable", p], capture_output=True, text=True, check=True).stdout.strip()
    p2 = os.path.join(jd, "X-de-B3-report.jcf")
    open(p2, "w").write("\n".join([
        "#!/bin/bash", "#SBATCH --job-name=X-de-B3-report", "#SBATCH --account=waldspektrum",
        "#SBATCH --partition=standard", "#SBATCH --qos=short", "#SBATCH --cpus-per-task=2",
        "#SBATCH --time=00:20:00", f"#SBATCH --dependency=afterany:{jid}",
        f"#SBATCH --output={LOGDIR}/X-de-B3-report.%j.out", "set -eu", f"cd {REPO}",
        f"{PY} {me} report"]) + "\n")
    jid2 = subprocess.run(["sbatch", "--parsable", p2], capture_output=True, text=True, check=True).stdout.strip()
    status(f"submitted gate array {jid} (logs/X-de-B3-gate.{jid}_<k>.out), report {jid2} afterany")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["gate", "eligibility", "report", "submit"])
    ap.add_argument("--member", nargs="*", default=GATE_MEMBERS)
    a = ap.parse_args(argv)
    {"gate": stage_gate, "eligibility": stage_eligibility, "report": stage_report, "submit": stage_submit}[a.stage](a)


if __name__ == "__main__":
    main()
