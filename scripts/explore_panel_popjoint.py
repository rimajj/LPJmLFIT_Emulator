#!/usr/bin/env python3
"""explore_panel_popjoint.py -- ADR 0363 stages B and the scoring of A-C: the emulator's VIRTUAL TREES, the actual
rooting depth derived from them, the biodiversity indices, and every score against a second run of the original.

Virtual trees (sec. 4, the Schaake shuffle / ensemble copula coupling): per cell and year N = round(25 x the shipped
forest map's tree count per patch) trees; per tree type t, N_t = N x the emulated type share (largest remainder);
N_t trees drawn from a DONOR roster's trees of type t (all its trees if it has none of t; without replacement while
it has enough, fixed seed); each variable's value = the emulated quantile function at the donor tree's rank among
the N virtual trees (piecewise linear through the 9 levels, linear tails, clipped at 0). Donors: D0 = the run's own
2019 roster; DA = run m6's roster of the same year on the next climate model's leg of the same scenario (a training
leg). Arms combined: AQ-D0, AQ-DA, ALS-D0, ALS-DA, and the null A0-D0 (anchor quantiles + own 2019 roster).
Actual rooting depth `derived`: from each virtual tree's D95max and its previous-year height at the same height rank
(the emulated height quantiles of y-1; the run's own 2019 quantiles for 2020) through the original's formula.
Stages:
  truth  --g G      indices of the original's trees, runs m1-m5 on G's three legs, years 2020, 2030, ..., 2100
                    -> eval/popmap/idx_truth_<g>.parquet
  virtual --g G     virtual trees of run m4's test rows (same years) for the five combinations -> indices
                    (idx_emu_<g>.parquet) and quantiles of the derived rooting depth (d95der_<g>.parquet)
  score             every ADR 0363 sec. 7 measure over the five held-out models -> stdout + eval/popmap/score_*.csv
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_panel_popmap as PM  # noqa: E402
import explore_panel_prep as PP  # noqa: E402
import fdiversity as F  # noqa: E402

OUT = PM.OUT
ROSTER = "/p/projects/reformit/Jamir/esm_land_emulator_data/xpanel_rosters"
YEARLY_EVAL = os.path.join(PP.OUT, "eval", "yearly")
YEARS = list(range(2020, 2101, 10))
SCENS = ["ssp126", "ssp370", "ssp585"]
NPATCH = 25
PS = np.array(PM.PS)
QVARS = ["Height", "agb", "SLA", "Wooddens", "D95max", "minwscal", "D95", "Age"]
COMBOS = [("AQ", "D0"), ("AQ", "DA"), ("ALS", "D0"), ("ALS", "DA"), ("A0", "D0")]
DENSE = 5.0
NP = int(os.environ.get("NPROC", "16"))
DRAW = os.environ.get("VDRAW", "rep")  # rep (ADR 0363 sec. 9) | unique (sec. 12)
SFX = "" if DRAW == "rep" else f"_{DRAW}"  # virtual-stage outputs of another draw never overwrite the scored ones


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def next_gcm(g: str) -> str:
    i = PP.GCMS.index(g)
    return PP.GCMS[(i + 1) % len(PP.GCMS)]


# ------------------------------------------------------------------------------------------------ the physics
def betaroot(d95max: np.ndarray, bottom: float = 2000.0) -> np.ndarray:
    """getbetaroot.c: the beta with (1 - b^D95max) / (1 - b^bottom) = 0.95, bisection on [0, 0.9999]."""
    lo, hi = np.zeros_like(d95max), np.full_like(d95max, 0.9999)
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        f = (1 - mid**d95max) / (1 - mid**bottom) - 0.95
        lo, hi = np.where(f > 0, mid, lo), np.where(f > 0, hi, mid)  # f decreases with beta: root above mid
    return 0.5 * (lo + hi)


def actual_d95(d95max: np.ndarray, h_prev: np.ndarray, k_root: float = 0.02) -> np.ndarray:
    """fwriteoutput_ind.c:142 with getrootdepth.c's logistic root front (S = 20 m, height_0 = 0.1 m), cm."""
    S, h0 = 20.0, 0.1
    rd_cm = S / (1 + np.exp(-k_root * S * h_prev) * (S / h0 - 1)) * 100.0
    R = np.minimum(rd_cm, 2000.0)
    b = betaroot(d95max)
    return np.log(1 - 0.95 * (1 - b**R)) / np.log(b)


def qfun(q: np.ndarray, u: np.ndarray) -> np.ndarray:
    """Quantile function through the 9 levels (q sorted), linear tails, clipped at 0."""
    x = np.interp(u, PS, q)
    lo, hi = u < PS[0], u > PS[-1]
    s0 = (q[1] - q[0]) / (PS[1] - PS[0])
    s1 = (q[-1] - q[-2]) / (PS[-1] - PS[-2])
    x[lo] = q[0] - s0 * (PS[0] - u[lo])
    x[hi] = q[-1] + s1 * (u[hi] - PS[-1])
    return np.maximum(x, 0.0)


def ranks01(v: np.ndarray, rng) -> np.ndarray:
    o = np.lexsort((rng.random(len(v)), v))
    r = np.empty(len(v))
    r[o] = np.arange(len(v))
    return (r + 0.5) / len(v)


def largest_remainder(n: int, s: np.ndarray) -> np.ndarray:
    x = n * s
    k = np.floor(x).astype(int)
    rest = n - k.sum()
    if rest > 0:
        k[np.argsort(-(x - k))[:rest]] += 1
    return k


def draw_unique(k: np.ndarray, types: np.ndarray, rng) -> tuple[np.ndarray, np.ndarray]:
    """ADR 0363 sec. 12: donor indices with NO tree drawn twice while the roster lasts. Each type t takes k[t] of its
    own donor trees; a shortfall is filled from the unused donor trees of the other types (the virtual tree keeps
    type t, its ranks come from that donor); repeats only once N exceeds the whole roster. A repeated donor gives a
    near-identical virtual tree (same rank in every variable) -- the cause of the evenness bias."""
    used = np.zeros(len(types), bool)
    idx, typ = [], []
    for t in range(7):
        pool = np.flatnonzero((types == t) & ~used)
        take = rng.choice(pool, min(k[t], len(pool)), replace=False) if k[t] else np.array([], int)
        used[take] = True
        idx.append(take)
        typ.append(np.full(len(take), t))
    got = [len(x) for x in idx]
    for t in range(7):
        short = k[t] - got[t]
        if short <= 0:
            continue
        rest = np.flatnonzero(~used)
        take = rng.choice(rest, min(short, len(rest)), replace=False)
        used[take] = True
        if short > len(take):
            take = np.concatenate([take, rng.choice(len(types), short - len(take), replace=True)])
        idx.append(take)
        typ.append(np.full(len(take), t))
    return np.concatenate(idx), np.concatenate(typ)


def virtual_trees(N: int, shares: np.ndarray, Q: dict[str, np.ndarray], donor: dict[str, np.ndarray],
                  seed: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    if N <= 0 or len(donor["Type"]) == 0:
        return {}
    k = largest_remainder(N, shares if shares.sum() > 0 else np.bincount(donor["Type"], minlength=7) / len(
        donor["Type"]))
    if DRAW == "unique":
        idx, typ = draw_unique(k, donor["Type"], rng)
    else:  # the scored ADR 0363 sec. 9 draw: repeats a donor tree once a type's pool is used up
        idx, typ = [], []
        for t in range(7):
            if k[t] == 0:
                continue
            pool = np.flatnonzero(donor["Type"] == t)
            if len(pool) == 0:
                pool = np.arange(len(donor["Type"]))
            idx.append(rng.choice(pool, k[t], replace=k[t] > len(pool)))
            typ.append(np.full(k[t], t))
        idx, typ = np.concatenate(idx), np.concatenate(typ)
    out = {"Type": typ}
    for v, q in Q.items():
        out[v] = qfun(q, ranks01(donor[v][idx], rng))
    out["_hrank"] = ranks01(donor["Height"][idx], rng)
    return out


# ------------------------------------------------------------------------------------------------ inputs
def roster(m: int, leg: str, year: int | None) -> pl.DataFrame:
    d = pl.read_parquet(os.path.join(ROSTER, f"m{m}_{leg}.parquet"))
    return d if year is None else d.filter(pl.col("Year") == year)


def by_cell(d: pl.DataFrame) -> dict[int, dict[str, np.ndarray]]:
    out = {}
    cols = ["Type", "Height", *QVARS[1:]]
    for (c,), x in d.group_by(["Cell"]):
        out[int(c)] = {k: x[k].to_numpy().astype(int if k == "Type" else float) for k in cols}
    return out


def preds(g: str) -> pl.DataFrame:
    """Run m4's test rows: the shipped tree count + every group's predictions, wide."""
    p = pl.read_parquet(os.path.join(YEARLY_EVAL, f"preds_{g}_statedep_fx.parquet")).filter(pl.col("member") == 4)
    p = p.select("leg", "Cell", "Year", "anc_n_per_patch", pl.col("n_per_patch").alias("X_n_per_patch"))
    for grp in [*QVARS, "shares"]:
        x = pl.read_parquet(os.path.join(OUT, f"preds_{g}_{grp}.parquet")).filter(pl.col("member") == 4)
        p = p.join(x.drop("member", "anc_n_per_patch"), on=["leg", "Cell", "Year"], how="left")
    return p


# ------------------------------------------------------------------------------------------------ stages
def _truth_task(args):
    m, leg, year = args
    c = F.load_constants()
    d = roster(m, leg, year)
    rows = []
    for (cell,), x in d.group_by(["Cell"]):
        X = F.standardise({t: x[t].to_numpy().astype(float) for t in F.TRAITS}, c)
        r = F.indices(X, x["Type"].to_numpy(), x["Height"].to_numpy().astype(float))
        rows.append({"member": m, "leg": leg, "Cell": int(cell), "Year": year, **r})
    return rows


def stage_truth(a) -> None:
    tasks = [(m, f"{a.g}_{s}", y) for m in (1, 2, 3, 4, 5) for s in SCENS for y in YEARS]
    with mp.get_context("spawn").Pool(NP) as pool:
        rows = [r for part in pool.imap_unordered(_truth_task, tasks) for r in part]
    out = pl.DataFrame(rows)
    out.write_parquet(os.path.join(OUT, f"idx_truth_{a.g}.parquet"))
    log(f"truth {a.g}: {out.height} cell-years")


def _virtual_task(args):
    """One (leg, year). Runs in a SPAWNED worker (a forked one deadlocks on polars' thread pool), so it loads its
    own inputs."""
    g, leg, year = args
    c = F.load_constants()
    scen = leg.rsplit("_", 1)[1]
    donors = {"D0": by_cell(roster(4, "hist", 2019)), "DA": by_cell(roster(6, f"{next_gcm(g)}_{scen}", year))}
    Pall = preds(g).filter((pl.col("leg") == leg) & pl.col("Year").is_in([year - 1, year]))
    P = Pall.filter(pl.col("Year") == year)
    if os.environ.get("CELL_LIMIT"):  # smoke test only
        P = P.head(int(os.environ["CELL_LIMIT"]))
    Pp = Pall.filter(pl.col("Year") == year - 1) if year > 2020 else None
    h19 = pl.read_parquet(os.path.join(PM.YEARLY2, "m4_hist.parquet")).filter(pl.col("Year") == 2019)
    prev = {}
    for arm in ("AQ", "ALS", "A0"):
        if Pp is None:
            src = h19
            cols = [f"Height_{pn}" for pn in PM.PN]
        else:
            src = Pp
            cols = [f"{'anc' if arm == 'A0' else arm}_Height_{pn}" for pn in PM.PN]
        prev[arm] = {int(r[0]): np.sort(np.array(r[1:], float)) for r in src.select("Cell", *cols).iter_rows()}
    rows, drows = [], []
    for r in P.iter_rows(named=True):
        cell = r["Cell"]
        N = int(round(NPATCH * max(r["X_n_per_patch"] or 0.0, 0.0)))
        for arm, dn in COMBOS:
            don = donors[dn].get(cell)
            if don is None:
                continue
            pre = "anc" if arm == "A0" else arm
            Q, ok = {}, True
            for v in QVARS:
                q = np.array([r[f"{pre}_{v}_{pn}"] for pn in PM.PN], dtype=float)
                if not np.isfinite(q).all():
                    ok = False
                    break
                Q[v] = np.sort(q)
            if not ok:
                continue
            sh = (np.array([r[f"anc_share_{t}"] for t in range(7)], float) if arm == "A0"
                  else np.array([r[f"AQ_share_{t}"] for t in range(7)], float))
            sh = np.nan_to_num(sh)
            vt = virtual_trees(N, sh, Q, don, seed=cell * 7919 + year)
            if not vt:
                continue
            hp = prev[arm].get(cell)
            if hp is not None and np.isfinite(hp).all():
                d95d = actual_d95(vt["D95max"], qfun(hp, vt["_hrank"]))
                qd = np.quantile(d95d, PS)
                drows.append({"leg": leg, "Cell": cell, "Year": year, "arm": arm, "donor": dn,
                              **{f"D95der_{pn}": float(x) for pn, x in zip(PM.PN, qd, strict=True)}})
            X = F.standardise({t: vt[t] for t in F.TRAITS}, c)
            ix = F.indices(X, vt["Type"], vt["Height"])
            rows.append({"leg": leg, "Cell": cell, "Year": year, "arm": arm, "donor": dn, **ix})
    return rows, drows


def stage_virtual(a) -> None:
    tasks = [(a.g, f"{a.g}_{s}", y) for s in SCENS for y in YEARS]
    rows, drows = [], []
    with mp.get_context("spawn").Pool(NP) as pool:
        for r, d in pool.imap_unordered(_virtual_task, tasks):
            rows += r
            drows += d
            log(f"  {len(rows)} virtual communities")
    pl.DataFrame(rows).write_parquet(os.path.join(OUT, f"idx_emu_{a.g}{SFX}.parquet"))
    pl.DataFrame(drows).write_parquet(os.path.join(OUT, f"d95der_{a.g}{SFX}.parquet"))
    log(f"virtual {a.g}: {len(rows)} communities, {len(drows)} derived rooting-depth rows")


# ------------------------------------------------------------------------------------------------ scoring
def truth_yearly(m: int, leg: str, qs: list[str]) -> pl.DataFrame:
    d = PM.yearly2(m, leg, qs)
    return d.drop("member", "leg").rename({q: f"T{m}_{q}" for q in qs})


def ratio_rows(d: pl.DataFrame, err_x: str, err_r: list[str], grp: str, keys=("case", "Year")) -> pl.DataFrame:
    """per (case, year): typical = median_X / median_R(pooled), worst = 90th_X / 90th_R."""
    long_r = pl.concat([d.select(*keys, pl.col(c).alias("e")) for c in err_r])
    a = d.group_by(*keys).agg(pl.col(err_x).median().alias("mx"), pl.col(err_x).quantile(0.9).alias("px"))
    b = long_r.group_by(*keys).agg(pl.col("e").median().alias("mr"), pl.col("e").quantile(0.9).alias("pr"))
    return a.join(b, on=list(keys)).with_columns((pl.col("mx") / pl.col("mr")).alias("typ"),
                                                (pl.col("px") / pl.col("pr")).alias("worst"),
                                                pl.lit(grp).alias("grp"))


def case_summary(r: pl.DataFrame, label: str, bar_typ: float, bar_worst: float | None) -> dict:
    c = r.group_by("case").agg(pl.col("typ").mean(), pl.col("worst").mean())
    out = {"what": label, "cases": c.height, "typ_median": float(c["typ"].median()),
           "worst_median": float(c["worst"].median()),
           "n_typ_ok": int((c["typ"] <= bar_typ).sum())}
    if bar_worst is not None:
        out["n_worst_ok"] = int((c["worst"] <= bar_worst).sum())
    return out


def stage_score(a) -> None:
    res = []
    # ---- A: distributions (every year 2021-2100), per variable and arm
    for v in QVARS:
        qs = [f"{v}_{pn}" for pn in PM.PN]
        parts = []
        for g in PP.GCMS:
            f = os.path.join(OUT, f"preds_{g}_{v}.parquet")
            if not os.path.exists(f):
                continue
            P = pl.read_parquet(f).filter(pl.col("member") == 4).drop("member")
            for s in SCENS:
                leg = f"{g}_{s}"
                d = P.filter(pl.col("leg") == leg)
                for m in (1, 2, 3, 4, 5):
                    d = d.join(truth_yearly(m, leg, qs), on=["Cell", "Year"], how="left")
                parts.append(d.with_columns(pl.lit(leg).alias("case")))
        if not parts:
            continue
        D = pl.concat(parts).filter(pl.col("Year") > 2020)
        den = pl.col(f"T4_{v}_p50").abs()
        D = D.filter(den > 0)

        def W(pre, lv=None, D=D, v=v, den=den):
            lvs = PM.PN if lv is None else [lv]
            return (pl.sum_horizontal([(pl.col(f"{pre}_{v}_{pn}") - pl.col(f"T4_{v}_{pn}")).abs() for pn in lvs])
                    / len(lvs) / den)

        for lv in (None, "p05", "p50", "p95"):
            E = D.with_columns(*[W(p, lv).alias(f"e_{p}") for p in ("AQ", "ALS", "anc", "T5", "T1", "T2", "T3")])
            for grp, flt in (("dense", pl.col("anc_n_per_patch") >= DENSE),
                             ("sparse", (pl.col("anc_n_per_patch") < DENSE) & (pl.col("anc_n_per_patch") > 0))):
                Eg = E.filter(flt)
                for arm in ("AQ", "ALS", "anc", "T5"):
                    rr = ratio_rows(Eg, f"e_{arm}", ["e_T1", "e_T2", "e_T3"], grp)
                    s = case_summary(rr, f"{v} {lv or 'all9'} {arm} {grp}", 1.2 if grp == "dense" else 3.0,
                                     1.5 if grp == "dense" else None)
                    res.append(s)
        log(f"scored {v}")
    # ---- derived rooting depth vs learned (roster years)
    dparts = []
    for g in PP.GCMS:
        f = os.path.join(OUT, f"d95der_{g}{SFX}.parquet")
        if os.path.exists(f):
            dparts.append(pl.read_parquet(f))
    if dparts:
        Dd = pl.concat(dparts).filter(pl.col("Year") > 2020)
        for arm in ("AQ", "ALS"):
            for dn in ("D0", "DA"):
                x = Dd.filter((pl.col("arm") == arm) & (pl.col("donor") == dn))
                parts = []
                for leg in x["leg"].unique().to_list():
                    d = x.filter(pl.col("leg") == leg)
                    for m in (1, 2, 3, 4):
                        d = d.join(truth_yearly(m, leg, [f"D95_{pn}" for pn in PM.PN]), on=["Cell", "Year"],
                                   how="left")
                    g = leg.rsplit("_", 1)[0]
                    pa = pl.read_parquet(os.path.join(OUT, f"preds_{g}_D95.parquet")).filter(
                        (pl.col("member") == 4) & (pl.col("leg") == leg)).select("Cell", "Year", "anc_n_per_patch",
                                                                                 *[f"{arm}_D95_{pn}" for pn in PM.PN])
                    parts.append(d.join(pa, on=["Cell", "Year"], how="left").with_columns(pl.lit(leg).alias("case")))
                E = pl.concat(parts).filter((pl.col("anc_n_per_patch") >= DENSE) & (pl.col("T4_D95_p50") > 0))

                def Wd(pre, E=E, arm=arm):
                    nm = "D95der" if pre == "der" else f"{arm}_D95" if pre == "learned" else f"{pre}_D95"
                    return pl.sum_horizontal([(pl.col(f"{nm}_{pn}") - pl.col(f"T4_D95_{pn}")).abs()
                                              for pn in PM.PN]) / 9 / pl.col("T4_D95_p50")

                E = E.with_columns(*[Wd(p).alias(f"e_{p}") for p in ("der", "learned", "T1", "T2", "T3")])
                for which in ("der", "learned"):
                    rr = ratio_rows(E, f"e_{which}", ["e_T1", "e_T2", "e_T3"], "dense")
                    res.append(case_summary(rr, f"D95 rooting depth {which} {arm}-{dn} dense (roster years)", 1.2, 1.5))
    # ---- indices
    ip, tp = [], []
    for g in PP.GCMS:
        fe, ft = os.path.join(OUT, f"idx_emu_{g}{SFX}.parquet"), os.path.join(OUT, f"idx_truth_{g}.parquet")
        if os.path.exists(fe) and os.path.exists(ft):
            ip.append(pl.read_parquet(fe))
            tp.append(pl.read_parquet(ft))
    if ip:
        IE, IT = pl.concat(ip), pl.concat(tp)
        dense = pl.concat([pl.read_parquet(os.path.join(OUT, f"preds_{g}_Height.parquet")).filter(
            pl.col("member") == 4).select("leg", "Cell", "Year", "anc_n_per_patch") for g in PP.GCMS
            if os.path.exists(os.path.join(OUT, f"preds_{g}_Height.parquet"))])
        T = IT.pivot(on="member", index=["leg", "Cell", "Year"], values=F.INDICES[:-1])
        for ix in F.INDICES[:-1]:
            tcols = {m: f"{ix}_{m}" for m in (1, 2, 3, 4, 5)}
            for arm, dn in COMBOS:
                x = IE.filter((pl.col("arm") == arm) & (pl.col("donor") == dn)).select("leg", "Cell", "Year",
                                                                                     pl.col(ix).alias("X"))
                j = (x.join(T.select("leg", "Cell", "Year", *tcols.values()), on=["leg", "Cell", "Year"])
                     .join(dense, on=["leg", "Cell", "Year"]).filter(pl.col("anc_n_per_patch") >= DENSE)
                     .filter(pl.col("Year") > 2020).with_columns(pl.col("leg").alias("case")))
                t4 = pl.col(tcols[4])
                j = j.with_columns((pl.col("X") - t4).abs().alias("eX"),
                                   *[(pl.col(tcols[m]) - t4).abs().alias(f"e{m}") for m in (1, 2, 3, 5)])
                j = j.drop_nulls(["eX", "e1", "e2", "e3"]).filter(pl.col("eX").is_not_nan())
                rr = ratio_rows(j, "eX", ["e1", "e2", "e3"], "dense")
                res.append(case_summary(rr, f"index {ix} {arm}-{dn} dense", 1.5, None))
                if arm == "AQ" and dn == "D0":
                    rr = ratio_rows(j, "e5", ["e1", "e2", "e3"], "dense")
                    res.append(case_summary(rr, f"index {ix} harness dense", 1.5, None))
        log("scored indices")
    # ---- C: mortality
    mp = []
    for g in PP.GCMS:
        f = os.path.join(OUT, f"preds_{g}_mort.parquet")
        if not os.path.exists(f):
            continue
        P = pl.read_parquet(f).filter(pl.col("member") == 4).drop("member")
        fn = os.path.join(OUT, f"preds_{g}_mortn.parquet")
        if os.path.exists(fn):  # ADR 0363 sec. 8: the NPP upper-bound arm
            N = pl.read_parquet(fn).filter(pl.col("member") == 4).select("leg", "Cell", "Year", "^BMN_.*$")
            P = P.join(N, on=["leg", "Cell", "Year"], how="left")
        for s in SCENS:
            leg = f"{g}_{s}"
            d = P.filter(pl.col("leg") == leg)
            for m in (1, 2, 3, 4, 5):
                d = d.join(truth_yearly(m, leg, PM.MORT), on=["Cell", "Year"], how="left")
                y = pl.read_parquet(os.path.join(PM.YEARLY2, f"m{m}_{leg}.parquet")).select(
                    "Cell", "Year", (pl.col("n_living") + pl.col("n_dead")).alias(f"risk{m}"))
                d = d.join(y, on=["Cell", "Year"], how="left")
            mp.append(d.with_columns(pl.lit(leg).alias("case")))
    if mp:
        M = pl.concat(mp).filter(pl.col("Year") > 2020)
        w = PP.cells().select("Cell", np.cos(np.deg2rad(pl.col("lat"))).alias("w"))
        M = M.join(w, on="Cell")
        marms = ["BM", "BMW", *(["BMN"] if "BMN_death_rate" in M.columns else []), "anc", "T5"]
        for q in PM.MORT:
            for arm in marms:
                xs = f"{arm}_{q}"
                E = M.filter((pl.col("anc_n_per_patch") >= DENSE) & pl.col(f"T4_{q}").is_not_null()).with_columns(
                    (pl.col(xs) - pl.col(f"T4_{q}")).abs().alias("eX"),
                    *[(pl.col(f"T{m}_{q}") - pl.col(f"T4_{q}")).abs().alias(f"e{m}") for m in (1, 2, 3)])
                rr = ratio_rows(E.drop_nulls(["eX", "e1", "e2", "e3"]), "eX", ["e1", "e2", "e3"], "dense")
                res.append(case_summary(rr, f"mortality {q} yearly {arm} dense", 1.5, None))
                # 30-year mean 2071-2100
                L = E.filter(pl.col("Year") >= 2071).group_by("case", "Cell").agg(
                    *[pl.col(c).mean() for c in (xs, f"T4_{q}", "T1_" + q, "T2_" + q, "T3_" + q)])
                L = L.with_columns((pl.col(xs) - pl.col(f"T4_{q}")).abs().alias("eX"),
                                   *[(pl.col(f"T{m}_{q}") - pl.col(f"T4_{q}")).abs().alias(f"e{m}")
                                     for m in (1, 2, 3)], pl.lit(2085).alias("Year"))
                rr = ratio_rows(L.drop_nulls(["eX", "e1", "e2", "e3"]), "eX", ["e1", "e2", "e3"], "dense")
                res.append(case_summary(rr, f"mortality {q} 30-yr mean 2071-2100 {arm} dense", 1.2, None))
                # area-weighted total deaths per year, signed, at the truth's at-risk count
                if q == "death_rate":
                    tot = E.group_by("case", "Year").agg(
                        (pl.col("w") * pl.col(xs) * pl.col("risk4")).sum().alias("X"),
                        (pl.col("w") * pl.col(f"T4_{q}") * pl.col("risk4")).sum().alias("T"))
                    rel = tot.with_columns((pl.col("X") / pl.col("T") - 1).alias("r")).group_by("case").agg(
                        pl.col("r").mean())
                    res.append({"what": f"mortality total deaths {arm} dense (signed, mean over years)",
                                "cases": rel.height, "typ_median": float(rel["r"].median()),
                                "worst_median": float(rel["r"].abs().max()), "n_typ_ok": int((rel["r"].abs() <= 0.05)
                                                                                           .sum())})
        # die-off capture: shared tree-count events of ADR 0350
        ev = pl.read_parquet(os.path.join(PP.OUT, "eval", "extreme_legacy_events.parquet")).filter(
            (pl.col("q") == "tree_count") & pl.col("shared"))
        for q in ("death_rate", "excess_rate"):
            cols = {k: f"{k}_{q}" for k in marms if k != "T5"} | {f"T{m}": f"T{m}_{q}" for m in (1, 2, 3, 4, 5)}
            tl = M.select("case", "Cell", "Year", *cols.values())
            pre = tl.with_columns(pl.col("Year").alias("y"))
            rows = []
            for e in ev.select("case", "Cell", "year").iter_rows():
                rows.append({"case": e[0], "Cell": e[1], "year": e[2]})
            E = pl.DataFrame(rows)
            at = E.join(tl, left_on=["case", "Cell", "year"], right_on=["case", "Cell", "Year"], how="left")
            base = (E.join(pre, on=["case", "Cell"], how="left")
                    .filter((pl.col("y") >= pl.col("year") - 5) & (pl.col("y") <= pl.col("year") - 1))
                    .group_by("case", "Cell", "year").agg(*[pl.col(c).mean().alias(f"b_{c}") for c in cols.values()]))
            j = at.join(base, on=["case", "Cell", "year"], how="inner")
            dT = (j[cols["T4"]] - j[f"b_{cols['T4']}"]).to_numpy()
            for k, c in cols.items():
                if k == "T4":
                    continue
                dX = (j[c] - j[f"b_{c}"]).to_numpy()
                ok = np.isfinite(dX) & np.isfinite(dT)
                res.append({"what": f"die-off capture {q} {k} ({int(ok.sum())} shared events)", "cases": int(ok.sum()),
                            "typ_median": float(dX[ok].sum() / dT[ok].sum()),
                            "worst_median": float(np.median(dX[ok] / np.where(dT[ok] != 0, dT[ok], np.nan))),
                            "n_typ_ok": int(np.mean(dT[ok]) * 1e4)})
        log("scored mortality")
    R = pl.DataFrame(res)
    R.write_csv(os.path.join(OUT, f"score_popmap{SFX}.csv"))
    with pl.Config(tbl_rows=-1, tbl_width_chars=200, fmt_str_lengths=80):
        print(R)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["truth", "virtual", "score"])
    ap.add_argument("--g", default="gfdl-esm4", choices=PP.GCMS)
    a = ap.parse_args()
    {"truth": stage_truth, "virtual": stage_virtual, "score": stage_score}[a.stage](a)
    log("=== DONE")


if __name__ == "__main__":
    main()
