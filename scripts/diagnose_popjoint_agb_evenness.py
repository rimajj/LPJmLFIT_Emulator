#!/usr/bin/env python3
"""diagnose_popjoint_agb_evenness.py -- ADR 0363 sec. 11-12: two checks on the emulator's virtual trees.

(1) COMPUTED vs LEARNED biomass per tree. Within a tree type, ln(biomass per tree) is linear in ln height, ln wood
    density and ln SLA to ~1 % per tree (sec. 11). Coefficients are fitted on run m1's trees of canesm5 (a training
    leg in every fold: hist + three scenarios); each virtual tree's biomass is then computed from its own height,
    wood density and SLA, and the 9 quantiles of that are scored like the learned ones (ratio to the second runs).
(2) Where the FUNCTIONAL EVENNESS bias comes from. For the original's run m4 at each roster year, evenness of:
      T      its own trees
      S9     its own trees pushed through the 9-level quantile function at their own ranks (true quantiles, own
             trees as donors, all trees used once) -> the interpolation alone
      D0T    virtual trees built exactly as the emulator's (donor = the 2019 roster, drawn by type share) but with
             the TRUE quantiles, shares and tree count -> the donor + drawing step alone
      D0TU   as D0T, but no donor tree drawn twice while the type pool lasts, extra trees drawn from other types'
             donors (no replacement at all unless N exceeds the whole roster) -> is repetition the cause?
      EMU    the emulator's AQ-D0 virtual trees (as in the scored stage)
    Duplicated donor trees give near-identical virtual trees, i.e. near-zero spanning-tree branches.
Stage:
  run --g G   -> eval/popmap/diag_agb_<g>.parquet (quantiles of computed biomass, AQ-D0 trees) and
                 diag_feve_<g>.parquet (evenness per variant, plus the share of repeated donor trees)
  score       -> stdout + eval/popmap/score_diag_agb_feve.csv
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_panel_popjoint as J  # noqa: E402
import explore_panel_popmap as PM  # noqa: E402
import explore_panel_prep as PP  # noqa: E402
import fdiversity as F  # noqa: E402

OUT = PM.OUT
ALLOM_LEGS = ["hist", "canesm5_ssp126", "canesm5_ssp370", "canesm5_ssp585"]
NP = J.NP


def fit_allometry() -> dict[int, np.ndarray]:
    """Per type: least squares of ln agb on [1, ln H, ln WD, ln SLA] over run m1's canesm5 + hist trees."""
    d = pl.concat([J.roster(1, leg, None).select("Type", "Height", "agb", "Wooddens", "SLA") for leg in ALLOM_LEGS])
    d = d.filter((pl.col("agb") > 0) & (pl.col("Height") > 0) & (pl.col("Type") <= 6))
    coef = {}
    for t in range(7):
        x = d.filter(pl.col("Type") == t)
        if x.height < 100:
            continue
        X = np.column_stack([np.ones(x.height), *[np.log(x[c].to_numpy().astype(float))
                                                  for c in ("Height", "Wooddens", "SLA")]])
        coef[t] = np.linalg.lstsq(X, np.log(x["agb"].to_numpy().astype(float)), rcond=None)[0]
    return coef


def agb_from(vt: dict, coef: dict) -> np.ndarray:
    out = np.full(len(vt["Type"]), np.nan)
    for t, b in coef.items():
        k = vt["Type"] == t
        if k.any():
            X = [np.log(np.maximum(vt[c][k], 1e-9)) for c in ("Height", "Wooddens", "SLA")]
            out[k] = np.exp(b[0] + b[1] * X[0] + b[2] * X[1] + b[3] * X[2])
    return out


def draw_unique(N: int, shares: np.ndarray, types: np.ndarray, rng) -> np.ndarray:
    """Donor indices: per type N_t without replacement; a type's shortfall is filled from the unused trees of the
    others; replacement only if N exceeds the whole roster."""
    k = J.largest_remainder(N, shares)
    used = np.zeros(len(types), bool)
    idx = []
    for t in range(7):
        pool = np.flatnonzero((types == t) & ~used)
        take = rng.choice(pool, min(k[t], len(pool)), replace=False) if k[t] else np.array([], int)
        used[take] = True
        idx.append(take)
    short = N - sum(len(i) for i in idx)
    if short > 0:
        rest = np.flatnonzero(~used)
        idx.append(rng.choice(rest, min(short, len(rest)), replace=False))
        short -= min(short, len(rest))
        if short > 0:
            idx.append(rng.choice(len(types), short, replace=True))
    return np.concatenate(idx)


def vt_from_idx(idx: np.ndarray, Q: dict, donor: dict, rng) -> dict:
    out = {"Type": donor["Type"][idx]}
    for v, q in Q.items():
        out[v] = J.qfun(q, J.ranks01(donor[v][idx], rng))
    return out


def feve_of(vt: dict, c: dict) -> float:
    X = F.standardise({t: vt[t] for t in F.TRAITS}, c)
    return F.indices(X, vt["Type"], vt["Height"])["feve"]


def _task(args):
    g, leg, year, coef = args
    c = F.load_constants()
    rng0 = np.random.default_rng(year)
    don19 = J.by_cell(J.roster(4, "hist", 2019))
    tru = J.by_cell(J.roster(4, leg, year))
    P = J.preds(g).filter((pl.col("leg") == leg) & (pl.col("Year") == year))
    tq = PM.yearly2(4, leg, [f"{v}_{pn}" for v in J.QVARS for pn in PM.PN]).filter(pl.col("Year") == year)
    tq = {int(r["Cell"]): r for r in tq.iter_rows(named=True)}
    arows, frows = [], []
    for r in P.iter_rows(named=True):
        cell = r["Cell"]
        don, tr, t9 = don19.get(cell), tru.get(cell), tq.get(cell)
        if don is None:
            continue
        N = int(round(J.NPATCH * max(r["X_n_per_patch"] or 0.0, 0.0)))
        Q = {v: np.sort(np.array([r[f"AQ_{v}_{pn}"] for pn in PM.PN], float)) for v in J.QVARS}
        if not all(np.isfinite(q).all() for q in Q.values()):
            continue
        sh = np.nan_to_num(np.array([r[f"AQ_share_{t}"] for t in range(7)], float))
        vt = J.virtual_trees(N, sh, Q, don, seed=cell * 7919 + year)
        if not vt:
            continue
        a = agb_from(vt, coef)
        if np.isfinite(a).all():
            arows.append({"leg": leg, "Cell": cell, "Year": year,
                          **{f"agbder_{pn}": float(x) for pn, x in zip(PM.PN, np.quantile(a, PM.PS), strict=True)}})
        fr = {"leg": leg, "Cell": cell, "Year": year, "anc_n_per_patch": r["anc_n_per_patch"], "EMU": feve_of(vt, c)}
        k = J.largest_remainder(N, sh if sh.sum() > 0 else np.ones(7) / 7)
        fr["rep_share_emu"] = float(sum(max(0, k[t] - int((don["Type"] == t).sum())) for t in range(7)) / max(N, 1))
        if tr is not None and t9 is not None and len(tr["Type"]) >= 3:
            fr["T"] = feve_of(tr, c)
            QT = {v: np.sort(np.array([t9[f"{v}_{pn}"] for pn in PM.PN], float)) for v in J.QVARS}
            if all(np.isfinite(q).all() for q in QT.values()):
                rng = np.random.default_rng(cell)
                fr["S9"] = feve_of(vt_from_idx(np.arange(len(tr["Type"])), QT, tr, rng), c)
                NT = len(tr["Type"])
                shT = np.bincount(tr["Type"], minlength=7) / NT
                fr["D0T"] = feve_of(J.virtual_trees(NT, shT, QT, don, seed=cell * 7919 + year), c)
                fr["D0TU"] = feve_of(vt_from_idx(draw_unique(NT, shT, don["Type"], rng0), QT, don, rng), c)
                fr["N_T"], fr["N_don"] = NT, len(don["Type"])
        frows.append(fr)
    return arows, frows


def stage_run(a) -> None:
    coef = fit_allometry()
    J.log("allometry", {t: np.round(b, 4).tolist() for t, b in coef.items()})
    tasks = [(a.g, f"{a.g}_{s}", y, coef) for s in J.SCENS for y in J.YEARS if y > 2020]
    A, Fr = [], []
    with mp.get_context("spawn").Pool(NP) as pool:
        for x, y in pool.imap_unordered(_task, tasks):
            A += x
            Fr += y
            J.log(f"  {len(A)} agb rows, {len(Fr)} evenness rows")
    pl.DataFrame(A).write_parquet(os.path.join(OUT, f"diag_agb_{a.g}.parquet"))
    pl.DataFrame(Fr).write_parquet(os.path.join(OUT, f"diag_feve_{a.g}.parquet"))


def stage_score(a) -> None:
    res = []
    parts = []
    for g in PP.GCMS:
        f = os.path.join(OUT, f"diag_agb_{g}.parquet")
        if not os.path.exists(f):
            continue
        d = pl.read_parquet(f)
        p = pl.read_parquet(os.path.join(OUT, f"preds_{g}_agb.parquet")).filter(pl.col("member") == 4).select(
            "leg", "Cell", "Year", "anc_n_per_patch", *[f"AQ_agb_{pn}" for pn in PM.PN])
        d = d.join(p, on=["leg", "Cell", "Year"], how="inner")
        for s in J.SCENS:
            leg = f"{g}_{s}"
            x = d.filter(pl.col("leg") == leg)
            for m in (1, 2, 3, 4):
                x = x.join(J.truth_yearly(m, leg, [f"agb_{pn}" for pn in PM.PN]), on=["Cell", "Year"], how="left")
            parts.append(x.with_columns(pl.lit(leg).alias("case")))
    if parts:
        D = pl.concat(parts).filter(pl.col("T4_agb_p50") > 0)
        for lv in (None, "p05", "p50", "p95"):
            lvs = PM.PN if lv is None else [lv]

            def W(nm, lvs=lvs):
                return pl.sum_horizontal([(pl.col(f"{nm}_{pn}") - pl.col(f"T4_agb_{pn}")).abs() for pn in lvs]) / len(
                    lvs) / pl.col("T4_agb_p50")

            E = D.with_columns(*[W(n).alias(f"e_{k}") for k, n in (("der", "agbder"), ("AQ", "AQ_agb"),
                                                                     ("T1", "T1_agb"), ("T2", "T2_agb"),
                                                                     ("T3", "T3_agb"))])
            for grp, flt in (("dense", pl.col("anc_n_per_patch") >= J.DENSE),
                             ("sparse", (pl.col("anc_n_per_patch") < J.DENSE) & (pl.col("anc_n_per_patch") > 0))):
                for arm in ("der", "AQ"):
                    rr = J.ratio_rows(E.filter(flt), f"e_{arm}", ["e_T1", "e_T2", "e_T3"], grp)
                    res.append(J.case_summary(rr, f"agb {lv or 'all9'} {arm} {grp} (roster years)",
                                              1.2 if grp == "dense" else 3.0, 1.5 if grp == "dense" else None))
        # consistency: the learned quantiles vs the allometry applied to the same virtual trees, medians
        res.append({"what": "agb median learned / computed, dense (median over cell-years)",
                    "cases": D.height, "typ_median": float(D.filter(pl.col("anc_n_per_patch") >= J.DENSE).select(
                        (pl.col("AQ_agb_p50") / pl.col("agbder_p50")).median()).item()),
                    "worst_median": None, "n_typ_ok": None})
    fparts = [pl.read_parquet(os.path.join(OUT, f"diag_feve_{g}.parquet")) for g in PP.GCMS
              if os.path.exists(os.path.join(OUT, f"diag_feve_{g}.parquet"))]
    if fparts:
        Fd = pl.concat(fparts, how="diagonal").filter(pl.col("anc_n_per_patch") >= J.DENSE).drop_nulls(["T", "S9"])
        for v in ("T", "S9", "D0T", "D0TU", "EMU"):
            x = Fd.filter(pl.col(v).is_not_nan() & pl.col("T").is_not_nan())
            res.append({"what": f"feve {v} dense: median value | median (v - T)", "cases": x.height,
                        "typ_median": float(x[v].median()),
                        "worst_median": float((x[v] - x["T"]).median()), "n_typ_ok": None})
        res.append({"what": "share of virtual trees from repeated donor trees (EMU, dense)", "cases": Fd.height,
                    "typ_median": float(Fd["rep_share_emu"].mean()),
                    "worst_median": float((Fd["N_T"] > Fd["N_don"]).mean()), "n_typ_ok": None})
    R = pl.DataFrame(res)
    R.write_csv(os.path.join(OUT, "score_diag_agb_feve.csv"))
    with pl.Config(tbl_rows=-1, tbl_width_chars=200, fmt_str_lengths=80):
        print(R)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["run", "score"])
    ap.add_argument("--g", default="gfdl-esm4", choices=PP.GCMS)
    a = ap.parse_args()
    {"run": stage_run, "score": stage_score}[a.stage](a)
    J.log("=== DONE")


if __name__ == "__main__":
    main()
