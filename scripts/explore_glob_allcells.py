#!/usr/bin/env python3
"""explore_glob_allcells.py -- the forest-structure emulator on ALL tree-bearing cells of the global venue (ADR 0315),
scored against the relaxed pass standard (ADR 0318 sec. 2). Every earlier global score used only the dev cells
(Cell % 10 == 0, ~10 % of the grid).

DATA: per-cell window levels of every non-rock cell, eval/levels_all/ (scripts/explore_glob_levels_all.py; gated
equal to eval/levels on the dev cells). Climate: climate/cell_year already covers all 67 420 cells.

ARMS (deployment setting of ADR 0316 sec. 4-5: cells seen in training, the RUN held out):
  A7r   explore_glob_a7r's anchored direct window map (per-cell anchor = mean over the training runs x training legs
        of the same cell, leave-one-leg-out; dclim; memoff; target value - anchor), LightGBM seeds 1-3.
  A7rH  A7r with a LOG target on biomass per tree ONLY: y = log((v + 1) / (anchor + 1)), prediction
        (anchor + 1) * exp(p) - 1 (ADR 0316 sec. 11, e = 1 gC per tree). Tree count and the four traits are A7r's
        models (identical by construction, so A7rH's tree count == A7r's is a harness check).
  Cells with no anchor (no trees in any training run/leg) use the direct model of the same arm (as explore_glob_a7r).
SPLITS:
  GS370  train Feb members 2,3,4,6 x historical + ssp126 + ssp245; test member 8 ssp370 (run + scenario held out).
         Anchor legs = historical, ssp126, ssp245 (explore_glob_a7r unchanged).
  GM     train members 2,3,4,6 x all four legs; test member 8, ssp126 / ssp245 / ssp370 (unseen run only).
         Anchor legs = all four training legs, leave-one-leg-out applied to every row exactly as in the code
         (so a test ssp370 row's anchor is the training runs' historical + ssp126 + ssp245 mean, the same anchor its
         training ssp370 rows were fitted with). A choice made here; there is no earlier A7r-on-GM to match.
TRAINING POPULATION: `dev` (dev cells only -- the published setting, the harness) and `all` (all non-rock cells).

SCORING (stage `score`), per split x test leg x candidate x scoring population (dev cells / all cells):
  (1) ADR 0317's measure exactly as explore_glob_tolerance.py: cells tree-bearing in the truth's leg OR its
      historical window; rho_k = P_k[|X-T|/|T|] / P_k[same for a second run], second runs = members 2,3,4,6,7
      (member 7 as a candidate is scored against 2,3,4,6).
  (2) ADR 0318 sec. 2 relaxed standard, cells tree-bearing in the truth's leg (n_per_patch > 0, as
      explore_relaxed_standard.py), dense = truth >= 5 trees per patch, sparse = below:
        D1 dense rho_50 <= 1.2   D2 dense rho_90 <= 1.5   D3 dense area totals (stems, biomass) within 5 %
        S1 sparse rho_50 <= 3    S2 sparse area totals within 25 %
      Area weight cos(lat); biomass = n_per_patch * agb_per_stem; totals signed (X/T - 1).
      Arms: ratios and totals per LightGBM seed, then the MEAN over seeds 1-3 (sd reported).
      A criterion passes at the median over the split's cases AND in >= ceil(0.8 * cases) of them (GS370: 1 case;
      GM: 3 cases, so all three).
  Nulls: rep7 (a second run), lookup (GS370: mean of runs 2,3,4,6 at ssp245; GM: at the same leg), mean5 (oracle,
  mean of runs 2,3,4,6,7 at the test leg).

WRITTEN BEFORE THE RUN (ADR 0184), 2026-10-15:
  HARNESS  (h1) A7r trained and scored on the dev cells, GS370, measure (1), mean of seeds 1-3, reproduces ADR 0317
           sec. 8 (5 seeds): tree count rho_50 1.44 and biomass per tree rho_50 1.96, each within 0.05.
           (h2) A7rH's tree count and four trait predictions are identical to A7r's (max |diff| 0).
           (h3) rep7 rho_50 / rho_90 in 0.90-1.10 on every quantity, both populations.
  PREDICTIONS for A7rH (GS370 unless named):
    P1 log target on biomass per tree helps here as on the panel: dev-cell biomass rho_50 1.96 -> 1.4-1.7.
    P2 all cells vs dev cells, same arm, measure (1): tree count rho_50 within +-0.10 of the dev value, biomass per tree
       within +-0.15 (the dev cells are a 10 % systematic sample; more cells of the same runs add little, as one more
       run added <= 0.02 in ADR 0317 sec. 8).
    P3 relaxed, all cells: about 75-80 % of tree-bearing cells dense; D1 tree count ~1.2-1.4 (fail), D1 biomass per tree
       ~1.2-1.5 (fail); D2 tree count ~1.5-2.0 (fail); traits D1/D2 pass (SLA borderline at ~1.0-1.2);
       D3 stems within 5 % (pass), D3 biomass 2-8 % (borderline); S1 tree count 3.5-6 (fail), S1 biomass 1.5-3
       (borderline), traits pass S1; S2 stems 10-30 % (borderline), biomass 5-30 %.
    P4 GM (scenario seen, only the run new) is better than GS370 on tree count and biomass per tree D1 by >= 0.05.
  FALSIFIERS: (F1) all-cells A7rH tree-count rho_50 differs from the dev-trained-dev-scored value by > 0.15 -> the
    dev cells were not a representative sample of the acceptance population; (F2) dev A7rH biomass rho_50 >= A7r's
    -> the panel's "the loss weighting is most of the biomass-per-tree failure" does not transfer to this venue.

RESULT (2026-10-15; levels job 2502519 + gate 2502590, fits 2502524-31, score 2502611; ~10 allocated core-hours):
  harness h1 HELD (tree count 1.442, biomass per tree 1.994); h2 HELD (max |diff| 0); h3 HELD (0.966-1.042).
  P1 held (dev A7rH biomass 1.557); P2 held (all vs dev: tree count 1.381 vs 1.442, biomass 1.522 vs 1.557);
  P4 held. P3: held except D2 tree count (1.25, PASSES; predicted 1.5-2.0) and S2 stems (+52 %, predicted 10-30 %).
  F1, F2 did not fire. GS370 all cells (57 726 tree-bearing, 76 % dense): fails D1 (tree count 1.24, biomass per
  tree 1.47), D2 biomass (1.505 +- 0.03), D3 biomass (+7.1 %), S1 tree count (3.79), S2 stems (+52 %); the four
  traits pass everything. GM passes every criterion in all three cases, but the lookup null (mean of the training
  runs at the same leg) is better than the arm on tree count and biomass per tree in dense and sparse cells.
  Tables: eval/allcells/verdict.csv.

Stages:  fit <split> <dev|all> <seed> [<seed> ...]   -> eval/allcells/preds/<split>_<pop>_<arm>_s<seed>.parquet
         score                                     -> eval/allcells/{tolerance,relaxed,verdict}.csv
LightGBM threads = POLARS_MAX_THREADS (which scripts/sbatch_python.sh sets to its NCPUS).
"""

from __future__ import annotations

import math
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_glob_a7 as A7  # noqa: E402
import explore_glob_a7r as R7  # noqa: E402
import explore_glob_eval as ev  # noqa: E402
import explore_glob_levels_all as LA  # noqa: E402
import explore_tolerance_measure as tm  # noqa: E402

ev.LEV = LA.OUT  # every ev.lev() in this process reads the all-cell levels (equal to eval/levels on dev cells)
OUT = os.path.join(ev.EVAL, "allcells")
PRED = os.path.join(OUT, "preds")
PANEL = ev.PANEL
TRAIN = (2, 3, 4, 6)
POOL = (2, 3, 4, 6, 7)
SEEDS = (1, 2, 3)
LOG_E = 1.0  # gC per tree, ADR 0316 sec. 11
SPLITS = {"GS370": dict(test=("ssp370",), anchor=("historical", "ssp126", "ssp245")),
          "GM": dict(test=("ssp126", "ssp245", "ssp370"), anchor=("historical", "ssp126", "ssp245", "ssp370"))}
DENSE = 5.0
LIM = {"D1": 1.2, "D2": 1.5, "D3": 0.05, "S1": 3.0, "S2": 0.25}


def cells_of(pop: str) -> pl.DataFrame:
    c = LA.all_cells()
    if pop == "dev":
        c = c.filter(pl.col("is_dev"))
    return c.select("Cell", "lat", "fold")


def fit(split: str, pop: str, seeds: list[int]):
    import lightgbm as lgb

    t0 = time.time()
    os.makedirs(PRED, exist_ok=True)
    R7.TRAIN, R7.ANCHOR_LEGS = TRAIN, SPLITS[split]["anchor"]
    A7.PARAMS["num_threads"] = int(os.environ.get("POLARS_MAX_THREADS", "16"))
    cells = cells_of(pop)
    df = R7.anchored(A7.build_rows(cells, split)).sort(["seed", "scen", "Cell"])
    tr, te = df.filter(pl.col("seed").is_in(list(TRAIN))), df.filter(pl.col("seed") == ev.TRUTH)
    assert te.select("Cell", "scen").n_unique() == te.height
    ev.log(f"{split}/{pop}: {cells.height} cells, train rows {tr.height}, test rows {te.height} "
           f"{te.group_by('scen').len().sort('scen').rows()} ({time.time() - t0:.0f}s)")
    f, f0 = R7.feats("A7r"), R7.feats("A7s-seen")
    Xte, Xte0 = te.select(f).to_numpy(), te.select(f0).to_numpy()
    for sd in seeds:
        A7.PARAMS["seed"] = sd
        outs = {a: te.select("Cell", "scen") for a in ("A7r", "A7rH")}
        for q in PANEL:
            t = tr.filter(pl.col(q).is_not_null() & pl.col(f"anc_{q}").is_not_null())
            X = t.select(f).to_numpy()
            anc = te[f"anc_{q}"].to_numpy().astype(float)
            miss = ~np.isfinite(anc)
            fb = None
            if miss.any():  # the direct model of the same arm where a cell has no anchor
                t0q = tr.filter(pl.col(q).is_not_null())
                m0 = lgb.train(A7.PARAMS, lgb.Dataset(t0q.select(f0).to_numpy(), t0q[q].to_numpy()), A7.ROUNDS)
                fb = m0.predict(Xte0[miss])
            m = lgb.train(A7.PARAMS, lgb.Dataset(X, (t[q] - t[f"anc_{q}"]).to_numpy()), A7.ROUNDS)
            p = m.predict(Xte) + anc
            if fb is not None:
                p[miss] = fb
            if q == "n_per_patch":
                p = np.maximum(p, 0.0)
            outs["A7r"] = outs["A7r"].with_columns(pl.Series(q, p))
            if q == "agb_per_stem":
                y = np.log((t[q].to_numpy() + LOG_E) / (t[f"anc_{q}"].to_numpy() + LOG_E))
                mh = lgb.train(A7.PARAMS, lgb.Dataset(X, y), A7.ROUNDS)
                ph = (anc + LOG_E) * np.exp(mh.predict(Xte)) - LOG_E
                if fb is not None:
                    ph[miss] = fb
            else:
                ph = p
            outs["A7rH"] = outs["A7rH"].with_columns(pl.Series(q, ph))
            ev.log(f"  seed {sd} {q}: {int(miss.sum())} test rows without anchor ({time.time() - t0:.0f}s)")
        for a, o in outs.items():
            o.write_parquet(os.path.join(PRED, f"{split}_{pop}_{a}_s{sd}.parquet"))
        ev.log(f"{split}/{pop} seed {sd} written ({time.time() - t0:.0f}s)")


# ------------------------------------------------------------------------------------------------- scoring
def mean_of(members, scen):
    return pl.concat([ev.lev(ev.mname(scen, m)) for m in members]).group_by("Cell").agg(
        [pl.col(q).mean() for q in PANEL])


def totals_signed(X, T, cc):
    def tot(d):
        d = d.select("Cell", "n_per_patch", "agb_per_stem").join(cc.select("Cell", "area"), on="Cell",
                                                                 how="right").fill_null(0.0)
        return (float((d["area"] * d["n_per_patch"]).sum()),
                float((d["area"] * d["n_per_patch"] * d["agb_per_stem"]).sum()))

    (nx, bx), (nt, bt) = tot(X), tot(T)
    return nx / nt - 1, bx / bt - 1


def score_one(X, Xh, T, Th, R, Rh, pool, cc_tol, cc_rel):
    """One candidate on one leg and one scoring population -> (tolerance rows, relaxed rows)."""
    tol, rel = [], []
    eX, eR = tm.rel_err(X, T, cc_tol), pl.concat([tm.rel_err(R[m], T, cc_tol) for m in pool])
    rX = tm.resp_err(X, Xh, T, Th, cc_tol)
    rR = pl.concat([tm.resp_err(R[m], Rh[m], T, Th, cc_tol) for m in pool])
    lv, rs = tm.ratios(eX, eR, []), tm.ratios(rX, rR, [])
    dn, db = totals_signed(X, T, cc_tol)
    for r in lv.iter_rows(named=True):
        rp = rs.filter(pl.col("q") == r["q"]).row(0, named=True)
        tol.append(dict(q=r["q"], n=r["n"], rho50=r["rho50"], rho90=r["rho90"], resp_rho50=rp["rho50"],
                        resp_rho90=rp["rho90"], tot_stems=dn, tot_biomass=db))
    for grp in ("dense", "sparse"):
        cg = cc_rel.filter(pl.col("grp") == grp)
        eX, eR = tm.rel_err(X, T, cg), pl.concat([tm.rel_err(R[m], T, cg) for m in pool])
        lv = tm.ratios(eX, eR, [])
        ts, tb = totals_signed(X, T, cg)
        rt = [totals_signed(R[m], T, cg) for m in pool]
        for r in lv.iter_rows(named=True):
            rel.append(dict(grp=grp, q=r["q"], n_cells=cg.height, rho50=r["rho50"], rho90=r["rho90"],
                            err50=r["x50"], rerr50=r["r50"], tot_stems=ts, tot_biomass=tb,
                            rep_tot_stems=float(np.median([abs(a) for a, _ in rt])),
                            rep_tot_biomass=float(np.median([abs(b) for _, b in rt]))))
    return tol, rel


def score():
    t0 = time.time()
    allc = LA.all_cells().with_columns(np.cos(np.deg2rad(pl.col("lat"))).alias("area"))
    tol_rows, rel_rows = [], []
    for split, cfg in SPLITS.items():
        for leg in cfg["test"]:
            T, Th = ev.lev(ev.mname(leg, ev.TRUTH)), ev.lev(ev.mname("historical", ev.TRUTH))
            R = {m: ev.lev(ev.mname(leg, m)) for m in POOL}
            Rh = {m: ev.lev(ev.mname("historical", m)) for m in POOL}
            tb = (T.filter(pl.col("n_per_patch") > 0).select("Cell")
                  .vstack(Th.filter(pl.col("n_per_patch") > 0).select("Cell")).unique())
            rel_c = T.filter(pl.col("n_per_patch") > 0).select(
                "Cell", pl.when(pl.col("n_per_patch") >= DENSE).then(pl.lit("dense")).otherwise(pl.lit("sparse"))
                .alias("grp"))
            look = mean_of(TRAIN, "ssp245" if split == "GS370" else leg)
            cands = {"rep7": [(0, R[7], Rh[7], (2, 3, 4, 6))],
                     "lookup": [(0, look, mean_of(TRAIN, "historical"), POOL)],
                     "mean5": [(0, mean_of(POOL, leg), mean_of(POOL, "historical"), POOL)]}
            for pop in ("dev", "all"):
                for arm in ("A7r", "A7rH"):
                    lst = []
                    for sd in SEEDS:
                        f = os.path.join(PRED, f"{split}_{pop}_{arm}_s{sd}.parquet")
                        if not os.path.exists(f):
                            continue
                        p = pl.read_parquet(f)
                        lst.append((sd, p.filter(pl.col("scen") == leg).drop("scen"),
                                    p.filter(pl.col("scen") == "historical").drop("scen"), POOL))
                    if lst:
                        cands[f"{arm}[{pop}]"] = lst
            for scope in ("dev", "all"):
                cs = allc.filter(pl.col("is_dev")) if scope == "dev" else allc
                cc_tol = cs.join(tb, on="Cell")
                cc_rel = cs.join(rel_c, on="Cell")
                for name, lst in cands.items():
                    if name.endswith("[dev]") and scope == "all":
                        continue  # a dev-trained arm has no predictions outside the dev cells
                    for sd, X, Xh, pool in lst:
                        a, b = score_one(X, Xh, T, Th, R, Rh, pool, cc_tol, cc_rel)
                        key = dict(split=split, leg=leg, scope=scope, cand=name, seed=sd)
                        tol_rows += [{**key, **r} for r in a]
                        rel_rows += [{**key, **r} for r in b]
            ev.log(f"scored {split} {leg} ({time.time() - t0:.0f}s)")
    tol, rel = pl.DataFrame(tol_rows), pl.DataFrame(rel_rows)
    tol.write_csv(os.path.join(OUT, "tolerance.csv"))
    rel.write_csv(os.path.join(OUT, "relaxed.csv"))
    report(tol, rel)
    ev.log(f"wrote {OUT}/tolerance.csv, relaxed.csv, verdict.csv ({time.time() - t0:.0f}s)")


def report(tol: pl.DataFrame, rel: pl.DataFrame):
    pl.Config.set_tbl_rows(400)
    pl.Config.set_tbl_cols(30)
    pl.Config.set_tbl_width_chars(250)
    pl.Config.set_float_precision(3)
    k = ["split", "leg", "scope", "cand", "q"]
    print("\n== ADR 0317 measure (cells tree-bearing in either window), mean over seeds ==")
    print(tol.group_by(k).agg(pl.col("n").first(), pl.col("rho50").mean(), pl.col("rho50").std().alias("sd50"),
                              pl.col("rho90").mean(), pl.col("resp_rho50").mean(), pl.col("tot_stems").mean(),
                              pl.col("tot_biomass").mean()).sort(k))
    # harness checks
    h = tol.filter((pl.col("split") == "GS370") & (pl.col("scope") == "dev") & (pl.col("cand") == "A7r[dev]"))
    hv = {q: float(h.filter(pl.col("q") == q)["rho50"].mean()) for q in ("n_per_patch", "agb_per_stem")}
    ok1 = abs(hv["n_per_patch"] - 1.44) <= 0.05 and abs(hv["agb_per_stem"] - 1.96) <= 0.05
    print(f"HARNESS h1 dev A7r GS370: tree count rho50 {hv['n_per_patch']:.3f} (1.44), biomass per tree "
          f"{hv['agb_per_stem']:.3f} (1.96): {'PASS' if ok1 else 'FAIL'}")
    h2 = 0.0
    for split in SPLITS:
        for pop in ("dev", "all"):
            for sd in SEEDS:
                fa, fb = (os.path.join(PRED, f"{split}_{pop}_{a}_s{sd}.parquet") for a in ("A7r", "A7rH"))
                if os.path.exists(fa) and os.path.exists(fb):
                    a, b = pl.read_parquet(fa), pl.read_parquet(fb)
                    for q in PANEL:
                        if q != "agb_per_stem":
                            h2 = max(h2, float(np.nanmax(np.abs(a[q].to_numpy() - b[q].to_numpy()))))
    print(f"HARNESS h2 A7rH tree count + traits == A7r's: max |diff| {h2:.3g} ({'PASS' if h2 == 0 else 'FAIL'})")
    r7 = tol.filter(pl.col("cand") == "rep7")
    print(f"HARNESS h3 rep7 rho50 range {r7['rho50'].min():.3f}-{r7['rho50'].max():.3f}, rho90 "
          f"{r7['rho90'].min():.3f}-{r7['rho90'].max():.3f}")
    # relaxed: seed means per case, then verdict over cases
    kk = ["split", "leg", "scope", "cand", "grp", "q"]
    m = rel.group_by(kk).agg(pl.col("n_cells").first(), pl.col("rho50").mean(), pl.col("rho50").std().alias("sd50"),
                             pl.col("rho90").mean(), pl.col("tot_stems").mean(), pl.col("tot_biomass").mean(),
                             pl.col("rep_tot_stems").first(), pl.col("rep_tot_biomass").first()).sort(kk)
    print("\n== relaxed standard per case (seed means) ==")
    print(m)
    ver = []
    for (split, scope, cand), g in m.group_by(["split", "scope", "cand"], maintain_order=True):
        ncase = g["leg"].n_unique()
        need = math.ceil(0.8 * ncase)
        for crit, col, grp in (("D1", "rho50", "dense"), ("D2", "rho90", "dense"), ("S1", "rho50", "sparse")):
            for q in PANEL:
                v = g.filter((pl.col("grp") == grp) & (pl.col("q") == q))[col].to_numpy()
                ver.append(dict(split=split, scope=scope, cand=cand, crit=crit, what=q, value=float(np.median(v)),
                                cases_ok=int((v <= LIM[crit]).sum()), cases=ncase,
                                PASS=bool(np.median(v) <= LIM[crit] and (v <= LIM[crit]).sum() >= need)))
        for crit, grp in (("D3", "dense"), ("S2", "sparse")):
            x = g.filter((pl.col("grp") == grp) & (pl.col("q") == "n_per_patch"))
            for col in ("tot_stems", "tot_biomass"):
                v = x[col].to_numpy()
                a = np.abs(v)
                ver.append(dict(split=split, scope=scope, cand=cand, crit=crit, what=col,
                                value=float(v[np.argsort(a)[len(a) // 2]]) if len(a) else float("nan"),
                                cases_ok=int((a <= LIM[crit]).sum()), cases=ncase,
                                PASS=bool(np.median(a) <= LIM[crit] and (a <= LIM[crit]).sum() >= need)))
    vd = pl.DataFrame(ver)
    vd.write_csv(os.path.join(OUT, "verdict.csv"))
    print("\n== verdict (value = median over cases of the seed-mean; totals signed X/T-1) ==")
    print(vd.sort(["split", "cand", "crit", "what", "scope"]))
    ncell = (m.filter((pl.col("cand") == "rep7") & (pl.col("q") == "n_per_patch"))
             .select("split", "leg", "scope", "grp", "n_cells").sort("split", "leg", "scope", "grp"))
    print("\n== tree-bearing cells scored (relaxed basis: truth leg n_per_patch > 0) ==")
    print(ncell)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    st = sys.argv[1]
    if st == "fit":
        fit(sys.argv[2], sys.argv[3], [int(x) for x in sys.argv[4:]] or list(SEEDS))
    elif st == "score":
        score()
    ev.log("=== DONE")
