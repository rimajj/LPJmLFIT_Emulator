#!/usr/bin/env python3
"""explore_glob_pv.py -- LINE X, PER-VERSION RETRAINING: does the emulator METHOD work for any model version, when it is
trained on THAT version's own runs? (ADR 0315 sec. 11.)

Owner, 2026-10-09, verbatim: "of course an eulator trained on one model verison cant be used for another. it only
works for one model verision. but for any model version". So the requirement is NOT transfer across builds (what
sec. 10's GV measured) but that the same method, retrained, reaches the same skill on every build. Method here = arm
A7 / A7s (explore_glob_a7.py's LightGBM window map, fixed hyper-parameters, 5-fold spatial cross-fit). Same data amount
for every version: ONE training member.

  P1  GFDL-ESM4 builds, all four legs. Train on one member, test on another member of the SAME build.
        Feb: 2 -> 8 and 3 -> 8 (two draws = the spread from WHICH member trained); replica (ceiling, tolerance) 7.
        May: 9 -> 10 and 10 -> 9; replica = the other May member (= the training member; it is the only one).
  P2  Present-day level only, A7 (no state input exists for these windows):
        Oct-1 build (GSWP3-W5E5 1990-2019): 1 -> 3 and 2 -> 3, replica 2 / 1 (the member NOT trained on).
        Feb (GFDL historical 1985-2014): 2 -> 8 and 3 -> 8, replica 7.  The Feb analogue of the line above.
  P3  ONE run per build (Oct-6/7/8 have a single member): A7 trained on the run's own other folds, scored on its
      held-out fold, at a flat 10 % (no replica exists, so no noise-based tolerance). Same for Oct-1 members 1,2,3
      and Feb members 2,8 (historical), as the comparison.

WHAT EACH MUST RETURN, written before the run (ADR 0184): if the method is version-agnostic, (P1, P2) the pass rate
as a fraction of that build's own single-member ceiling lies within the Feb two-draw spread for every build, and (P3)
the flat-10 % pass of a single run is similar across the Oct builds and the Feb runs, given each build's own data. A
build that falls clearly outside means the method has something version-specific baked in (candidate already known:
the tropical-tree cold-stress feature tstress_pft0 uses the Feb threshold 12.5 C, the Oct builds 14 C -- ADR 0314 s4).
Output: eval/scores_PV.csv.
"""

from __future__ import annotations

import os
import sys
import time

import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_glob_a7 as a7  # noqa: E402
import explore_glob_eval as ev  # noqa: E402
import explore_glob_gv as gv  # noqa: E402

LEGS = gv.LEGS
SUMMARY = ("pass_rate", "pass_rate_flat10", "stems_ratio", "agb_per_stem_ratio", "resp_n_per_patch_slope_deatt")


def emit(rows, part, version, train, truth, leg, cand, s):
    rows.append(dict(part=part, version=version, train=str(train), truth=truth, leg=leg, candidate=cand, **s))
    ev.log(part, version, f"{train}->{truth}", leg, cand, {k: round(s[k], 4) for k in SUMMARY if s.get(k) is not None})


def main():
    t0 = time.time()
    cells = ev.dev_cells()
    clist = cells["Cell"].to_list()
    st = pl.read_parquet(os.path.join(a7.CLIM, "cell_static.parquet")).select("Cell", "lon", "soil_code")
    cw = {s: gv.clim("GFDL-ESM4", s, *ev.WIN[a7.LEGS[s]], clist) for s in LEGS}
    oc = gv.clim("GSWP3-W5E5", "obsclim", *ev.WIN["h1990"], clist)
    rows = []

    # ---- P1: GFDL builds, one training member, test a member of the same build
    for version, pairs in (("Feb", ((2, 8, 7), (3, 8, 7))), ("May", ((9, 10, 9), (10, 9, 10)))):
        for trn, tst, rep in pairs:
            tr, te = gv.rows_for((trn,), cells, cw, st), gv.rows_for((tst,), cells, cw, st)
            preds = {v: gv.fit_predict(tr, te, v) for v in ("A7", "A7s")}
            T_h, R_h = ev.lev(ev.mname("historical", tst)), ev.lev(ev.mname("historical", rep))
            for leg in LEGS:
                T_w, R_w = ev.lev(ev.mname(leg, tst)), ev.lev(ev.mname(leg, rep))
                sc = gv.tree_cells(cells, T_w, T_h)
                emit(rows, "P1", version, trn, tst, leg, "ceiling", ev.score(R_w, R_h, T_w, T_h, R_w, R_h, sc))
                for v, p in preds.items():
                    if v == "A7s" and leg == "historical":
                        continue  # its input IS the target there
                    s = ev.score(gv.pick(p, tst, leg), gv.pick(p, tst, "historical"), T_w, T_h, R_w, R_h, sc)
                    emit(rows, "P1", version, trn, tst, leg, v, s)

    # ---- P2: present-day level, A7, one training member
    def orows(seed):
        return (ev.lev(gv.oname(seed)).with_columns(pl.lit(seed).alias("seed"), pl.lit("obsclim").alias("scen"))
                .join(oc, on="Cell").join(cells, on="Cell").join(st, on="Cell"))

    def hrows(seed):
        return gv.rows_for((seed,), cells, cw, st).filter(pl.col("scen") == "historical")

    def level(s):
        return {k: x for k, x in s.items() if not k.startswith("resp_")}

    for version, build, pairs in (("Oct-1", orows, ((1, 3, 2), (2, 3, 1))), ("Feb", hrows, ((2, 8, 7), (3, 8, 7)))):
        for trn, tst, rep in pairs:
            te = build(tst)
            p = gv.fit_predict(build(trn), te, "A7").drop("seed", "scen")
            T = te.select(["Cell"] + ev.PANEL)
            Rr = build(rep).select(["Cell"] + ev.PANEL)
            sc = gv.tree_cells(cells, T)
            emit(rows, "P2", version, trn, tst, "present", "ceiling", level(ev.score(Rr, Rr, T, T, Rr, Rr, sc)))
            emit(rows, "P2", version, trn, tst, "present", "A7", level(ev.score(p, p, T, T, Rr, Rr, sc)))

    # ---- P3: one run per build, trained on its own other folds (flat 10 % only)
    singles = [(f"Oct-{b}", orows, s) for b, s in (("1", 1), ("1", 2), ("1", 3), ("6", 5), ("7", 6), ("8", 7))]
    singles += [("Feb", hrows, 2), ("Feb", hrows, 8)]
    for version, build, s in singles:
        d = build(s)
        p = gv.fit_predict(d, d, "A7").drop("seed", "scen")
        T = d.select(["Cell"] + ev.PANEL)
        sc = gv.tree_cells(cells, T)
        emit(rows, "P3", version, f"{s}(own folds)", str(s), "present", "A7", level(ev.score(p, p, T, T, T, T, sc)))

    pl.DataFrame(rows, infer_schema_length=None).write_csv(os.path.join(ev.EVAL, "scores_PV.csv"))
    ev.log(f"wrote scores_PV.csv ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
