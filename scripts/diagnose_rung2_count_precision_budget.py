#!/usr/bin/env python
"""
diagnose_rung2_count_precision_budget — CAN A NEXT-YEAR PER-PATCH COUNT TARGET EVER BE PRECISE
ENOUGH TO DRIVE A GROSS MORTALITY BUDGET?  An ARCHITECTURE question, answered from state already
on disk.  No model run, no LPJmL job.

ADR 0240 built ADR 0189 section 7's accounting gross-budget arm verbatim and it failed in
substance: count -72.1 %, per-stem mass +269 %, worse than the status quo's +96 %.  ADR 0188's
operative sentence -- "a mortality-only operator driven by a next-year COUNT target structurally
cannot express gross mortality flux" -- was argued from the NET-vs-GROSS identity.  This scorer
asks the quantitative version of the same question, which nothing has measured: even granting the
gross form, is the count target's PRECISION sufficient to carry a budget at all?

-- THE HYPOTHESIS UNDER TEST (stated to be REFUTED, not confirmed) -------------------------------

    H:  The budget is a DIFFERENCE of counts, so the count model's error is amplified by the ratio
        of the LEVEL to the BUDGET.  FIT's gross mortality flux is ~6 %/yr of the roster and the
        count model's per-patch-year error is ~+-24 % of the level (ADR 0185's separability
        figure), so the relative error ON THE BUDGET is ~24/6 = ~4x = ~400 % -- which is why a
        convex per-year rectification over-kills (ADR 0189 section 5.3) and why the account settled
        at 0.6x roster (ADR 0240 section 3).  Getting the budget to +-20 % would need the count
        target to ~+-1.2 % per patch-year, against an irreducible realisation floor.

-- THE ALGEBRA, WRITTEN OUT BEFORE THE RUN -------------------------------------------------------

One patch, one year y.  `N` = roster stem count at the rendezvous (`n_tree`); `M` = its EMITTED
(> 5 m) count (`n_emit`) -- the population the count model is trained and scored on, because
`n_living` (the training target, build_slow_runtime_table.py:545) is the `ind`-table count and the
`ind` writer cuts at `param.height_min` = 5 m.  `T` = the model's target; `M*` = FIT's own realized
`n_living` for that patch-year; the count-target error is

    eps  =  T - M*                                   [emitted stems]

The harness forms `rho = T / n_prev` on the EMITTED basis (:574) and applies it to the ROSTER
(:521-527), so ADR 0189 section 7's gross budget is

    B  =  (1 - T/n_prev) * N  +  Rhat                dB/dT = -N/n_prev

and with `n_prev ~ M` (the emitted level) a perturbation `eps` in the target moves the budget by

    dB  =  -eps * (N/M)                              [roster stems]

The truth the budget is trying to be is FIT's own GROSS kills `K` (roster stems).  So

    |dB| / K  =  (|eps|/M) * (N/K)  =  (|eps|/M) / (K/N)  ==  e / k

    e  ==  |eps| / M     the count-target error as a fraction of the LEVEL   (emitted basis)
    k  ==  K / N         FIT's gross kill rate as a fraction of the LEVEL    (roster basis)

⚠ THE `N/M` CANCELS EXACTLY.  The emitted-vs-roster population ratio (2.08-2.92, ADR 0188 section 6)
does NOT enter the amplification -- consistent with ADR 0188's refutation of the emitted-vs-roster
hypothesis, and the reason this statistic is not a second copy of it.

Requiring the budget within a relative tolerance `tau`:

    e_req  =  tau * k                                tau = 0.20 pre-registered

-- WHAT IS MEASURED, AND ON WHAT BASIS -----------------------------------------------------------

REFERENCE BASIS.  FIT's OWN stand: the `REC` `predict` dumps (`grow`/`mort`/`post` phases) joined
to `map_on_rec_stand_predict.csv`, the learned count model's own `target` replayed over that same
roster (`diagnose_rung2_map_on_rec_stand.jl`, ADR 0185).  Behind ADR 0185 section 5's imported
completion + coverage gate.  This is the count model's OWN basis: FIT's stand, FIT's features, the
`ind`-table training target.  It is deliberately NOT ADR 0185's +-24 % separability figure, which
is |target/n_emit - 1| on an ARM's own diverged stand and conflates the model's error with the
trajectory divergence AND with the mortality the target is supposed to express.  If the honest
number comes out far below 24 %, H is weakened at its first step -- that is the point.

P1  BASIS REPRODUCTION GATE (skill trap 5c / residual-diagnosis section 14).  FIT's own gross kill
    rate and recruitment must reproduce ADR 0188 section 4 through this scorer's own scan:
    K_all 5.651 / 5.961 %/yr and R 4.619 / 6.456 %/yr, historic / ssp370, medians over cells.
    Tolerance 0.15 pp.  A miss is a basis error and NOTHING BELOW IS TO BE READ.

P2  `e`, the count model's per-patch-year error, on FIT's own stand, three ways:
      eps_post  = T - #{post,  height > 5 m, isdead == 0}   PRIMARY: this is `n_living` exactly
                  (post-mortality, post-fire, post-establishment; recruits are age 0 and below the
                  5 m cut so they cannot enter it)
      eps_mort  = T - #{mort,  height > 5 m, isdead == 0}   the demography-only variant (ADR 0188:
                  fire flags +14.1 % more dead between the phases and is not the interface's)
      eps_next  = T - M(y+1)                                the budget-algebra variant, ADR 0189
                  section 3's `n_next = target + (R - Rhat)`
    Both columns printed side by side (ADR 0060): a basis substitution must never be silent.
    Reported as a fraction of the LEVEL (/M) and as a fraction of the GROSS FLUX (/K).

P2b THE MODE-EXACT COMPANION, and a DISCLOSURE.  ⚠ P2's algebra assumes `n_prev ~ M`, which is
    true in `roster` mode and NOT in `predict` mode, where `n_prev = T(y-1)` so `rho = T(y)/T(y-1)`
    is a ratio of two model outputs and is partly insensitive to a common LEVEL offset.  ⚠ THIS
    PANEL WAS ADDED AFTER THE TWO-CELL SMOKE TEST OF P2 HAD BEEN SEEN.  It was added for that
    algebraic reason and not because of what P2 returned; nothing in P2's numbers determines its
    outcome, and the pre-registered verdict of section D is NOT re-read on it (ADR 0104's error).
    It is reported as a corroborating instrument with its own A, and disclosed here so the record
    shows the order (ADR 0189 section 8's clause).

    The mode-exact statistic makes NO assumption about `n_prev`.  With the gross budget
    `B = (1 - rho)*N + Rhat` and `Rhat = R` (the oracle recruit, so the recruit term contributes
    nothing and the count model's error is isolated),

        B - K  =  N * [ rho_true - rho ],        rho_true  ==  1 - (K - R)/N
        |B - K| / K  =  |drho| / k                                   drho == rho - rho_true

    -- the SAME form and the SAME required precision as P2 (`|drho| <= tau*k`), because both `e`
    and `drho` are dimensionless fractions of a level.  `rho` is taken as the harness takes it,
    `clamp(target/n_prev, 0.7, 1.3)` (:574), so the clamp is inside the measurement.

P3  THE FLOORS.  `e` is a one-year-ahead prediction error of a count, so its floor is
    `sd(M* | what the predictor knows) / M`.  Two, and they are floors for different model classes:
      FLOOR-1  between-patch CV of `n_living` within (cell, year, scenario, seed) -- i.e.
               CONDITIONED ON cell, year, scenario and seed, and on NOTHING about the patch.  This
               is the floor for a predictor with cell-and-year information only.  The shipped model
               also sees per-patch stand features (hmean/hmax/agb/lai/fpc/age_mean/n_prev), so it
               can and does beat this -- printed as context, NOT as the verdict's floor.
      FLOOR-2  the DEMOGRAPHIC REALISATION floor, and a strict LOWER BOUND on the irreducible error
               of ANY learner with PERFECT state knowledge:
                   M*  =  sum_i 1[stem i survives]  +  ingrowth
               over the emitted stems at `grow`, each an independent Bernoulli draw at FIT's own
               per-stem hazard (`erand48`, mortality_tree_ind.c:120-146; the dump's `mort_prob` IS
               that probability, and the port matches it to 5e-18, ADR 0183).  Hence
                   sd(M* | state)  >=  sqrt( sum_i p_i (1 - p_i) )          p_i = min(mort_prob, 1)
               exactly, per patch-year.  It is a LOWER bound because ingrowth across the 5 m cut and
               establishment add variance this cannot see.  Certain kills (`mort_prob >= 1`)
               contribute 0, correctly -- they carry no randomness.
      FLOOR-2r the same construction on the ROSTER basis, sqrt(sum_all p(1-p)) / N, which is the
               matching floor for `drho` (whose denominator is N, not M).  Reported beside P2b.
    ⚠ FLOOR-2 IS THE VERDICT'S FLOOR.  It is the only one that binds every architecture, and using
    the larger FLOOR-1 would flatter the conclusion.  P3 asserts FLOOR-1 >= FLOOR-2; if that fails,
    say so and read the smaller.

P5  ⚠ THE QUANTISATION FLOOR — added AFTER the 12-cell run, and disclosed as such (ADR 0189
    section 8).  It is not a re-read of section D's verdict, which is unchanged; it is a SECOND and
    stronger derivation that needs no statistics at all.  A stem count is an INTEGER, so the
    smallest change either the count target or the budget can express is ONE STEM:

        FLOOR-0(count)   =  1 / M          vs  e_req  = tau * k
        FLOOR-0(budget)  =  1 / K_pyr      vs  tau               K_pyr = k * N, FIT's own gross
                                                                 kills per patch-year, in stems

    If FIT's gross mortality is of order one stem per patch-year, a +-20 % budget means being right
    to +-0.2 of a stem in a quantity whose atom is 1.  That is arithmetic, not noise, and it binds
    every instrument and every learner identically.

P4  THE REFUTATION PANEL -- three ways H could be wrong, each of which would rescue the count
    target, measured rather than argued:
      R1  `e` is far smaller than 24 %.  If `e/k <= 0.20` already, H's premise is simply false.
      R2  THE ERRORS CANCEL IN AN ACCOUNT.  The shipped `G*` arms spend from a per-patch RUNNING
          ACCOUNT (ADR 0240 section 1), so if `eps` is zero-mean and weakly autocorrelated the
          budget error over a leg falls as 1/sqrt(n_yr) and the precision requirement applies to the
          leg MEAN, not per patch-year.  Measured as the account-basis relative error
              e_acct  =  |sum_y eps_y| / sum_y K_y        per patch, over the whole leg
          against the per-year `median |eps|/K`.  THIS IS THE STRONGEST REFUTATION AVAILABLE and it
          is exactly ADR 0189 section 3's telescoping argument applied to the count error instead of
          the recruit term.
      R3  BIAS vs NOISE.  An account absorbs zero-mean noise, not a bias.  `mean(eps)/K`
          and `sd(eps)/K` are printed apart; lag-1 autocorrelation of `eps` within a patch is
          printed beside them, because an autocorrelated error does not average down at 1/sqrt(n).

-- THE PRE-REGISTERED READING (fixed BEFORE the run; ADR 0104's error is re-reading it after) ----

Let  A  ==  FLOOR2 / e_req   -- how far the required precision sits INSIDE (A <= 1) or OUTSIDE
(A > 1) the irreducible realisation floor.  Read on the ssp370 leg, median over scoreable cells.

  (a)  A <= 1        -> the required precision is INSIDE the realisation floor.  A budget-driven
                        operator is FEASIBLE; `S2` (the operator owning establishment) stays the
                        plan and this ADR is a sizing note, not a redirection.
  (b)  A > 3         -> the required precision is OUTSIDE the floor by more than 3x.  NO
                        count-target-driven operator can express gross mortality flux at patch
                        granularity, for ANY learner or architecture -- an ARCHITECTURAL finding,
                        not a tuning result.  Consequence, stated plainly: apply FIT's own per-tree
                        hazard as a RATE (already exact -- ADR 0183 |dhazard| 5e-18, and ADR 0189's
                        `perfect` arm reproduces FIT's gross AND net kills to |diff| 0.0000) and
                        RETIRE the learned count model from the mortality path.
  (c)  1 < A <= 3    -> IN BETWEEN.  Say so, and name what would break the tie.
  ⚠ AND (b) IS VOID IF R2 REFUTES IT: if `e_acct` is already within tau = 0.20, the account absorbs
    the per-patch-year error and the requirement is on the leg mean, so the per-patch-year floor is
    the wrong bar.  The verdict expression reads `e_acct` explicitly.

Usage
    export NPREV=predict
    /home/jamirp/.conda/envs/py311_new/bin/python scripts/diagnose_rung2_count_precision_budget.py
    # CELLS=12045,42490 restricts the scan (smoke test).
"""

from __future__ import annotations

import glob
import math
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ADR 0186's rule: import the definitions, never re-implement them (skill trap 5c).
from diagnose_rung2_kill_budget import RHO_HI, RHO_LO, mean, median, sd  # noqa: E402
from diagnose_rung2_map_target_response import (  # noqa: E402
    LEG,
    NPATCH,
    NPREV,
    ROOT,
    run_completed,
)

MAPCSV = os.environ.get(
    "MAPCSV", "/p/tmp/jamirp/S_rung2_maptarget/map_on_rec_stand_predict.csv"
)
SCENS = ("historic", "ssp370")
REC_RE = re.compile(r"^S_r2s_(historic|ssp370)_c(\d+)_REC_" + NPREV + r"_s(\d+)_dump$")

#: `fwriteoutput_ind.c:84` / harness :99 — the `ind` writer's emission cut, in metres.
HEIGHT_MIN = 5.0
#: the pre-registered budget tolerance of the derivation. NOT a tunable.
TAU = 0.20
#: the pre-registered verdict boundaries on A = FLOOR2 / e_req.
A_FEASIBLE = 1.0
A_ARCHITECTURAL = 3.0
#: P1's basis-reproduction anchors, from ADR 0188 section 4, in %/yr, and the tolerance in pp.
ANCHOR_K = {"historic": 5.651, "ssp370": 5.961}
ANCHOR_R = {"historic": 4.619, "ssp370": 6.456}
ANCHOR_TOL = 0.15


def only_cells():
    v = os.environ.get("CELLS", "").strip()
    return {int(x) for x in v.split(",") if x} if v else None


def lag1_autocorr(v):
    if len(v) < 4:
        return float("nan")
    m = mean(v)
    num = sum((a - m) * (b - m) for a, b in zip(v[:-1], v[1:], strict=True))
    den = sum((a - m) ** 2 for a in v)
    return num / den if den > 0 else float("nan")


# ── the one scan this whole derivation runs on ────────────────────────────────────────────────────

def scan_counts(path: str):
    """-> per_year[(year, patch)] = dict with the emitted-basis counts this scorer needs.

    Deliberately a SEPARATE scan from `scan_rec_dump` rather than an extension of it: that function
    is on the ROSTER basis (ADR 0188's count identity) and is imported here only for the P1 anchors
    it already gates.  This one carries the > 5 m cut and the per-stem hazards, which the roster
    identity has no use for.  Header offset per skill trap 1: `#H T phase ...` vs `T grow ...`, so
    name n is field n+1 — read positions off the header, never hardcode.

      m_grow   #{grow, height > HEIGHT_MIN}                 the EMITTED level M
      n_grow   #{grow}                                      the ROSTER level N
      sum_pq   sum over emitted grow stems of p(1-p), p = min(mort_prob, 1)   FLOOR-2's variance
      sum_pq_r the same over the WHOLE roster                                  FLOOR-2r's variance
      k_all    #{mort, isdead == 1}                         FIT's own gross kills (roster basis)
      m_mort   #{mort, height > HEIGHT_MIN, isdead == 0}    emitted survivors, demography only
      m_post   #{post, height > HEIGHT_MIN, isdead == 0}    == `n_living`, the training target
      n_post   #{post}                                      for R = n_post - n_grow (ADR 0188)
    """
    acc = defaultdict(lambda: dict(m_grow=0, n_grow=0, sum_pq=0.0, sum_pq_r=0.0, k_all=0,
                                   m_mort=0, m_post=0, n_post=0))
    tcols = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#H T"):
                tcols = {n: i + 1 for i, n in enumerate(line.split()[2:])}
                continue
            if not line.startswith("T "):
                continue
            if tcols is None:
                raise SystemExit(f"{path}: a T record before its '#H T' header")
            f = line.split()
            phase = f[tcols["phase"]]
            if phase == "pre":
                continue
            a = acc[(int(f[tcols["year"]]), int(f[tcols["patch"]]))]
            tall = float(f[tcols["height"]]) > HEIGHT_MIN
            if phase == "grow":
                a["n_grow"] += 1
                p = min(float(f[tcols["mort_prob"]]), 1.0)
                a["sum_pq_r"] += p * (1.0 - p)
                if tall:
                    a["m_grow"] += 1
                    a["sum_pq"] += p * (1.0 - p)
            elif phase == "mort":
                dead = int(float(f[tcols["isdead"]])) == 1
                if dead:
                    a["k_all"] += 1
                elif tall:
                    a["m_mort"] += 1
            elif phase == "post":
                a["n_post"] += 1
                if tall and int(float(f[tcols["isdead"]])) == 0:
                    a["m_post"] += 1
    return acc


def read_map_csv(path):
    """-> {(cell, scen, seed, year, patch): (n_tree, n_emit, n_prev, target)}."""
    out = {}
    cols = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split(",")
            if cols is None:
                cols = {n: i for i, n in enumerate(f)}
                continue
            out[(int(f[cols["cell"]]), f[cols["scenario"]], int(f[cols["seed"]]),
                 int(f[cols["year"]]), int(f[cols["patch"]]))] = (
                float(f[cols["n_tree"]]), float(f[cols["n_emit"]]),
                float(f[cols["n_prev"]]), float(f[cols["target"]])
            )
    return out


def collect():
    """-> {(cell, scen, seed): per_year}, plus the NAMED exclusions (skill trap 2)."""
    keep = only_cells()
    got, excluded = {}, []
    for d in sorted(glob.glob(os.path.join(ROOT, "S_r2s_*_REC_*_dump"))):
        m = REC_RE.match(os.path.basename(d))
        if not m:
            continue
        scen, cell, seed = m.group(1), int(m.group(2)), int(m.group(3))
        if keep is not None and cell not in keep:
            continue
        f = os.path.join(d, "roster_rank0000.txt")
        if not os.path.exists(f):
            excluded.append((cell, scen, seed, "no roster_rank0000.txt"))
            continue
        if not run_completed(scen, cell, "REC", NPREV, seed):
            excluded.append((cell, scen, seed, "C run has no completion line"))
            continue
        py = scan_counts(f)
        y0, y1 = LEG[scen]
        years = {y for (y, _p) in py}
        patches = {p for (_y, p) in py}
        if len(years) != (y1 - y0 + 1) or len(patches) != NPATCH:
            excluded.append((cell, scen, seed,
                             f"incomplete: {len(years)} yr x {len(patches)} patches"))
            continue
        got[(cell, scen, seed)] = py
        print(f"    REC {scen:8s} c{cell:<6d} s{seed}  {len(py):6d} patch-years", flush=True)
    return got, excluded


# ── the per-leg statistic ────────────────────────────────────────────────────────────────────────

def leg_stats(py, tgt, cell, scen, seed):
    """Everything P2-P4 need for one (cell, scenario, seed) leg."""
    keys = sorted(py)
    # per-patch-year rows that have BOTH a dump and a replayed target
    rows = []
    for (y, p) in keys:
        a = py[(y, p)]
        t = tgt.get((cell, scen, seed, y, p))
        if t is None or a["m_grow"] == 0:
            continue
        m_next = py.get((y + 1, p), {}).get("m_grow")
        rows.append(dict(
            year=y, patch=p, target=t[3], n_tree=a["n_grow"], m=a["m_grow"],
            m_post=a["m_post"], m_mort=a["m_mort"], m_next=m_next,
            k=a["k_all"], r=a["n_post"] - a["n_grow"], sum_pq=a["sum_pq"],
            sum_pq_r=a["sum_pq_r"], n_prev=t[2],
        ))
    if not rows:
        return None

    # ---- P1 anchors: FIT's own gross kills and recruits, %/yr of the roster ----
    k_rate = 100.0 * sum(r["k"] for r in rows) / sum(r["n_tree"] for r in rows)
    r_rate = 100.0 * sum(r["r"] for r in rows) / sum(r["n_tree"] for r in rows)
    # `k` for the derivation is the LEVEL-normalised gross flux (roster basis), a fraction
    kbar = k_rate / 100.0

    # ---- P2: the count-target error, three bases ----
    out = dict(cell=cell, scen=scen, seed=seed, n_py=len(rows),
               k_rate=k_rate, r_rate=r_rate, kbar=kbar,
               m_mean=mean([r["m"] for r in rows]),
               n_mean=mean([r["n_tree"] for r in rows]))
    for name, key in (("post", "m_post"), ("mort", "m_mort"), ("next", "m_next")):
        sub = [r for r in rows if r[key] is not None]
        if not sub:
            continue
        eps = [r["target"] - r[key] for r in sub]
        rel = [abs(e) / r["m"] for e, r in zip(eps, sub, strict=True)]
        out[f"e_{name}"] = median(rel)
        out[f"e_{name}_mean"] = mean(rel)
        out[f"bias_{name}"] = mean([e / r["m"] for e, r in zip(eps, sub, strict=True)])
        out[f"sd_{name}"] = sd([e / r["m"] for e, r in zip(eps, sub, strict=True)])
        # per-patch-year budget error, as a fraction of THAT patch-year's own gross flux
        pyk = [abs(e) * r["n_tree"] / r["m"] / r["k"]
               for e, r in zip(eps, sub, strict=True) if r["k"] > 0]
        out[f"ek_{name}"] = median(pyk) if pyk else float("nan")
        # ---- P4/R2: the ACCOUNT basis -- signed error summed over the leg, per patch ----
        cum_e = defaultdict(float)
        cum_k = defaultdict(float)
        cum_bud = defaultdict(float)
        for e, r in zip(eps, sub, strict=True):
            cum_e[r["patch"]] += e * r["n_tree"] / r["m"]   # in roster stems
            cum_k[r["patch"]] += r["k"]
            cum_bud[r["patch"]] += 1.0
        acct = [abs(cum_e[p]) / cum_k[p] for p in cum_e if cum_k[p] > 0]
        out[f"eacct_{name}"] = median(acct) if acct else float("nan")
        # ---- P4/R3: lag-1 autocorrelation of eps within a patch ----
        by_patch = defaultdict(list)
        for e, r in zip(eps, sub, strict=True):
            by_patch[r["patch"]].append((r["year"], e / r["m"]))
        acs = [lag1_autocorr([e for _y, e in sorted(v)]) for v in by_patch.values()]
        acs = [a for a in acs if a == a]
        out[f"ac1_{name}"] = median(acs) if acs else float("nan")

    # ---- P2b: the MODE-EXACT rho-basis budget error ----
    drho, dr_w = [], []
    for r in rows:
        if r["n_prev"] <= 0 or r["n_tree"] <= 0:
            continue
        rho = min(max(r["target"] / r["n_prev"], RHO_LO), RHO_HI)
        rho_true = 1.0 - (r["k"] - r["r"]) / r["n_tree"]
        drho.append(abs(rho - rho_true))
        dr_w.append((r["patch"], r["year"], (rho - rho_true) * r["n_tree"], r["k"]))
    out["drho"] = median(drho) if drho else float("nan")
    pyk = [abs(d[2]) / d[3] for d in dr_w if d[3] > 0]
    out["drho_k"] = median(pyk) if pyk else float("nan")
    ce, ck = defaultdict(float), defaultdict(float)
    for pch, _y, dstems, kk in dr_w:
        ce[pch] += dstems
        ck[pch] += kk
    acct = [abs(ce[p]) / ck[p] for p in ce if ck[p] > 0]
    out["drho_acct"] = median(acct) if acct else float("nan")

    # ---- P3 FLOOR-1: between-patch CV of `n_living` within (cell, year) ----
    by_year = defaultdict(list)
    for r in rows:
        by_year[r["year"]].append(r["m_post"])
    cvs = []
    for _y, v in by_year.items():
        if len(v) >= 5 and mean(v) > 0:
            cvs.append(sd(v) / mean(v))
    out["floor1"] = median(cvs) if cvs else float("nan")

    # ---- P3 FLOOR-2: the demographic realisation floor, per patch-year ----
    f2 = [math.sqrt(r["sum_pq"]) / r["m"] for r in rows]
    out["floor2"] = median(f2)
    out["floor2_mean"] = mean(f2)
    out["floor2r"] = median([math.sqrt(r["sum_pq_r"]) / r["n_tree"] for r in rows])
    return out


# ── report ───────────────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 100)
    print("diagnose_rung2_count_precision_budget — CAN A COUNT TARGET CARRY A GROSS MORTALITY "
          "BUDGET?")
    print(f"  mode NPREV={NPREV}   root={ROOT}")
    print(f"  map replay = {MAPCSV}")
    print(f"  tau = {TAU} (pre-registered budget tolerance)   verdict boundaries on "
          f"A = FLOOR2/e_req: feasible <= {A_FEASIBLE}, architectural > {A_ARCHITECTURAL}")
    print("=" * 100)
    if NPREV != "predict":
        print("  ⚠ NPREV is not `predict`. The map replay CSV is the predict one; a roster-mode "
              "read would\n    put the reference on a tethered axis (skill trap: the mode knob "
              "must reach every script).")

    tgt = read_map_csv(MAPCSV)
    print(f"\n  map replay rows: {len(tgt)}")
    print("\n  -- dumps --", flush=True)
    got, excluded = collect()
    if excluded:
        print("\n  EXCLUDED (named, skill trap 2):")
        for e in excluded:
            print(f"    c{e[0]} {e[1]} s{e[2]}: {e[3]}")
    if not got:
        raise SystemExit("no scoreable REC legs")

    legs = []
    for (cell, scen, seed), py in sorted(got.items()):
        s = leg_stats(py, tgt, cell, scen, seed)
        if s is not None:
            legs.append(s)

    # ---------------- P1 ----------------
    print("\n" + "=" * 100)
    print("P1  BASIS REPRODUCTION GATE — FIT's own gross kills and recruits vs ADR 0188 §4")
    print("=" * 100)
    print(f"  {'leg':>9} | {'K_all %/yr':>10} {'anchor':>8} {'d':>7} | "
          f"{'R %/yr':>8} {'anchor':>8} {'d':>7} | verdict")
    gate_ok = True
    for scen in SCENS:
        sub = [x for x in legs if x["scen"] == scen]
        if not sub:
            continue
        k = median([x["k_rate"] for x in sub])
        r = median([x["r_rate"] for x in sub])
        dk, dr = k - ANCHOR_K[scen], r - ANCHOR_R[scen]
        ok = abs(dk) <= ANCHOR_TOL and abs(dr) <= ANCHOR_TOL
        gate_ok = gate_ok and ok
        print(f"  {scen:>9} | {k:10.3f} {ANCHOR_K[scen]:8.3f} {dk:+7.3f} | "
              f"{r:8.3f} {ANCHOR_R[scen]:8.3f} {dr:+7.3f} | {'PASS' if ok else 'FAIL'}")
    print(f"  tolerance {ANCHOR_TOL} pp on both.  "
          + ("⇒ the basis reproduces; read on." if gate_ok
             else "⇒ ⚠ BASIS ERROR — DO NOT READ BELOW."))

    # ---------------- P2 ----------------
    print("\n" + "=" * 100)
    print("P2  THE COUNT MODEL'S PER-PATCH-YEAR ERROR, on FIT's own stand")
    print("    e = median |target - truth| / M   (M = emitted > 5 m level).  Three truths, side by")
    print("    side (ADR 0060): `post` = `n_living`, the TRAINING target and the primary basis.")
    print("=" * 100)
    for scen in SCENS:
        sub = [x for x in legs if x["scen"] == scen]
        if not sub:
            continue
        print(f"\n  -- {scen} ({len(sub)} legs) --")
        print(f"  {'cell':>7} {'M':>6} {'N':>6} {'k %/yr':>7} | "
              f"{'e_post':>7} {'e_mort':>7} {'e_next':>7} | {'e/k post':>9} {'e/k next':>9}")
        for x in sorted(sub, key=lambda z: z["cell"]):
            print(f"  {x['cell']:>7} {x['m_mean']:6.2f} {x['n_mean']:6.2f} {x['k_rate']:7.3f} | "
                  f"{x.get('e_post', float('nan')):7.4f} {x.get('e_mort', float('nan')):7.4f} "
                  f"{x.get('e_next', float('nan')):7.4f} | "
                  f"{x.get('e_post', float('nan')) / x['kbar']:9.2f} "
                  f"{x.get('e_next', float('nan')) / x['kbar']:9.2f}")
        ep = median([x["e_post"] for x in sub if "e_post" in x])
        en = median([x["e_next"] for x in sub if "e_next" in x])
        kb = median([x["kbar"] for x in sub])
        print(f"  {'MEDIAN':>7} {median([x['m_mean'] for x in sub]):6.2f} "
              f"{median([x['n_mean'] for x in sub]):6.2f} {100 * kb:7.3f} | "
              f"{ep:7.4f} {median([x['e_mort'] for x in sub if 'e_mort' in x]):7.4f} "
              f"{en:7.4f} | {ep / kb:9.2f} {en / kb:9.2f}")
        print(f"  ⇒ {scen}: the count target is off by {100 * ep:.1f} % OF THE LEVEL, which is "
              f"{ep / kb:.2f}x = {100 * ep / kb:.0f} % OF THE GROSS FLUX ({100 * kb:.2f} %/yr).")

    # ---------------- P2b ----------------
    print("\n" + "=" * 100)
    print("P2b THE MODE-EXACT COMPANION — drho = rho - rho_true, rho_true = 1 - (K-R)/N")
    print("    NO assumption about `n_prev`. Added AFTER P2's smoke test, for an algebra reason;")
    print("    section D's pre-registered verdict is NOT re-read on it (see the header).")
    print("=" * 100)
    print(f"  {'leg':>9} | {'|drho|':>8} {'FLOOR-2r':>9} | {'|drho|/k':>9} "
          f"{'acct':>8} | {'e/k (P2)':>9}")
    for scen in SCENS:
        sub = [x for x in legs if x["scen"] == scen]
        if not sub:
            continue
        kb = median([x["kbar"] for x in sub])
        print(f"  {scen:>9} | {median([x['drho'] for x in sub]):8.4f} "
              f"{median([x['floor2r'] for x in sub]):9.4f} | "
              f"{median([x['drho_k'] for x in sub]):9.2f} "
              f"{median([x['drho_acct'] for x in sub]):8.2f} | "
              f"{median([x['e_post'] for x in sub]) / kb:9.2f}")
    print("\n  `rho` is taken as the harness takes it: clamp(target/n_prev, "
          f"{RHO_LO}, {RHO_HI}) — the clamp is inside")
    print("    the measurement. `acct` is the leg-summed signed error over the leg-summed kills.")
    print("  Required: |drho| <= tau*k, the SAME bar as P2's e_req.")

    # ---------------- P3 ----------------
    print("\n" + "=" * 100)
    print("P3  THE FLOORS — what any predictor of a per-patch count is up against")
    print("=" * 100)
    print(f"  {'leg':>9} | {'FLOOR-1 (cell+yr)':>18} | {'FLOOR-2 (realisation)':>22} | "
          f"{'F1 >= F2':>9}")
    floors = {}
    for scen in SCENS:
        sub = [x for x in legs if x["scen"] == scen]
        if not sub:
            continue
        f1 = median([x["floor1"] for x in sub])
        f2 = median([x["floor2"] for x in sub])
        floors[scen] = (f1, f2)
        print(f"  {scen:>9} | {f1:18.4f} | {f2:22.4f} | {'yes' if f1 >= f2 else '⚠ NO':>9}")
    print("\n  FLOOR-1 is CONDITIONED ON (cell, year, scenario, seed) and on nothing about the")
    print("    patch — the floor for a cell-and-year-conditioned predictor.  The shipped")
    print("    model also sees per-patch stand features, so it beats this; it is context, not")
    print("    the verdict's bar.")
    print("  FLOOR-2 is CONDITIONED ON THE FULL PER-STEM STATE — sqrt(sum p(1-p)) / M over FIT's")
    print("    own per-stem hazards at `grow`.  It is a strict LOWER BOUND on the irreducible")
    print("    error of ANY learner: ingrowth across the 5 m cut and establishment add variance")
    print("    it cannot see.")

    # ---------------- P4 ----------------
    print("\n" + "=" * 100)
    print("P4  THE REFUTATION PANEL — three ways H could be wrong")
    print("=" * 100)
    print(f"  {'leg':>9} | {'R1 e/k':>8} | {'R2 e_acct':>10} {'per-yr e/k':>11} {'gain':>7} | "
          f"{'R3 bias/k':>10} {'sd/k':>8} {'ac1':>7}")
    for scen in SCENS:
        sub = [x for x in legs if x["scen"] == scen]
        if not sub:
            continue
        kb = median([x["kbar"] for x in sub])
        ek = median([x["ek_post"] for x in sub if "ek_post" in x])
        ea = median([x["eacct_post"] for x in sub if "eacct_post" in x])
        bias = median([x["bias_post"] for x in sub if "bias_post" in x]) / kb
        sdk = median([x["sd_post"] for x in sub if "sd_post" in x]) / kb
        ac1 = median([x["ac1_post"] for x in sub if "ac1_post" in x])
        gain = ek / ea if ea > 0 else float("inf")
        print(f"  {scen:>9} | {median([x['e_post'] for x in sub]) / kb:8.2f} | "
              f"{ea:10.3f} {ek:11.3f} {gain:7.2f} | {bias:+10.3f} {sdk:8.2f} {ac1:+7.3f}")
    print("\n  R1  `e/k` is the per-patch-year relative budget error implied by the count model.")
    print("  R2  `e_acct` = |sum_y eps_y| / sum_y K_y per patch over the WHOLE leg — what a")
    print("      running account (the `G*` form, ADR 0240 §1) carries.  `gain` = the per-year")
    print("      e/k divided by it: how much the account absorbs.  A zero-mean, uncorrelated error")
    print("      would give gain ~ sqrt(n_yr).")
    print("  R3  an account absorbs NOISE, not a BIAS.  `bias/k` is the systematic part;")
    print("      `ac1` is the within-patch lag-1 autocorrelation of eps — an autocorrelated error")
    print("      does not average down at 1/sqrt(n).")

    # ---------------- P5 ----------------
    print("\n" + "=" * 100)
    print("P5  THE QUANTISATION FLOOR — a stem count is an INTEGER (added after the run; header)")
    print("=" * 100)
    print(f"  {'leg':>9} | {'M':>6} {'K/patch-yr':>11} | {'1/M':>8} {'e_req':>8} {'x':>7} | "
          f"{'1/K':>8} {'tau':>6} {'x':>7}")
    for scen in SCENS:
        sub = [x for x in legs if x["scen"] == scen]
        if not sub:
            continue
        kb = median([x["kbar"] for x in sub])
        m = median([x["m_mean"] for x in sub])
        n = median([x["n_mean"] for x in sub])
        kpy = kb * n
        e_req = TAU * kb
        print(f"  {scen:>9} | {m:6.2f} {kpy:11.3f} | {1 / m:8.4f} {e_req:8.4f} "
              f"{(1 / m) / e_req:7.2f} | {1 / kpy:8.4f} {TAU:6.2f} {(1 / kpy) / TAU:7.2f}")
    print("\n  `x` = how many times the atom exceeds the tolerance. Both columns are pure")
    print("  arithmetic off measured levels: no learner, no architecture and no amount of data")
    print("  changes them, because the quantity being predicted cannot take a fractional value.")

    # ---------------- the derivation and the verdict ----------------
    print("\n" + "=" * 100)
    print("D   THE REQUIRED PRECISION, and the pre-registered verdict")
    print("=" * 100)
    print("    |dB|/K = (|eps|/M) / (K/N) = e / k     (the N/M population ratio cancels EXACTLY)")
    print(f"    e_req  = tau * k,   tau = {TAU}")
    for scen in SCENS:
        sub = [x for x in legs if x["scen"] == scen]
        if not sub or scen not in floors:
            continue
        kb = median([x["kbar"] for x in sub])
        e = median([x["e_post"] for x in sub])
        f1, f2 = floors[scen]
        e_req = TAU * kb
        a2 = f2 / e_req
        a1 = f1 / e_req
        ea = median([x["eacct_post"] for x in sub if "eacct_post" in x])
        print(f"\n  -- {scen} --")
        print(f"    (1) measured e            = {e:.4f}  ({100 * e:.2f} % of the LEVEL) "
              f"= {e / kb:.2f}x the GROSS FLUX")
        print(f"    (2) FLOOR-2 (irreducible) = {f2:.4f}   [FLOOR-1, cell+yr: {f1:.4f}]")
        print(f"    (3) e_req = {TAU} * {kb:.5f} = {e_req:.5f}  ({100 * e_req:.3f} % per patch-yr)")
        print(f"    (4) ratio (3)/(2)         = {e_req / f2:.4f}      "
              f"⇒ A = (2)/(3) = {a2:.2f}x   [vs FLOOR-1: A1 = {a1:.1f}x]")
        if ea <= TAU:
            verdict = ("REFUTED BY R2 — the running account already holds the budget within tau, "
                       "so the\n          per-patch-year floor is the wrong bar.")
        elif a2 <= A_FEASIBLE:
            verdict = ("FEASIBLE — the required precision is INSIDE the realisation floor. "
                       "`S2` stays the plan.")
        elif a2 > A_ARCHITECTURAL:
            verdict = ("ARCHITECTURAL — the required precision is OUTSIDE the irreducible "
                       f"realisation floor\n          by {a2:.1f}x. NO count-target-driven "
                       "operator can express gross mortality flux at\n          patch "
                       "granularity, for ANY "
                       "learner or architecture. Apply FIT's own per-tree hazard\n          as a "
                       "RATE and retire the learned count model from the mortality path.")
        else:
            verdict = (f"IN BETWEEN (A = {a2:.2f}x, between {A_FEASIBLE} and {A_ARCHITECTURAL}) — "
                       "name what breaks the tie.")
        print(f"    VERDICT: {verdict}")
        d_med = median([x["drho"] for x in sub])
        f2r = median([x["floor2r"] for x in sub])
        print(f"    P2b corroboration (mode-exact, not the pre-registered read): |drho| = "
              f"{d_med:.4f} = {d_med / kb:.2f}x the flux;")
        print(f"      its own floor FLOOR-2r = {f2r:.4f} ⇒ A_rho = {f2r / e_req:.2f}x")
        print(f"    (R2 check: e_acct = {ea:.3f} vs tau = {TAU} ⇒ "
              f"{'account SUFFICES' if ea <= TAU else 'account does NOT suffice'})")
    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
