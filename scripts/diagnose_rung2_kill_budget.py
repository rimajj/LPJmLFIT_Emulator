#!/usr/bin/env python
"""
diagnose_rung2_kill_budget — WHY the rung-2 operator kills 3.5-4.2x too few of the trees that
carry biomass (ADR 0187 section 3), answered from the arm logs plus the REC dumps. No model run.

ADR 0187 established WHAT is wrong: not the kill set's composition (the emulator picks the right
KINDS of trees) but the RATE — FIT kills 2.1 % of stems per year on the discretionary population,
S1 0.6 %, S0h 0.5 %, and total annual mass removal 0.0306 vs 0.0178, uniformly across every height
quintile. Its promoted next action was to find the mechanism, starting from the suspicion that a
kill quota derived on the EMITTED (>5 m) population is applied to the WHOLE roster.

    THE REFERENCE BASIS. The arm's own runtime log `<apply>/s_arm_log.txt` (one row per patch-year:
    `n_tree` the full roster, `n_emit` the >5 m population, `n_prev`, `target`, `rho`, `theta`,
    `shortfall`, `n_kill`) and, for FIT's own side, the `REC` dumps' `grow`/`mort`/`post` phases.
    `predict` mode throughout, matching ADR 0185/0186/0187. `n_kill` is the arm's NOMINATION, not
    the realized kill set — the C always adds its own non-negotiable kills (skill trap 5d).

── THE THREE HYPOTHESES, PRE-REGISTERED WITH WHAT EACH MUST RETURN ──────────────────────────────

H1 — THE POPULATION MISMATCH (ADR 0187 section B's first hypothesis). Claim under test: `rho` is
     derived from `target`/`n_prev`, both on the emitted basis, while the thinning acts on every
     tree, so it "under-kills the whole roster by exactly that ratio".
     *** THIS IS REFUTED BY THE HARNESS'S OWN ALGEBRA, AND THE REFUTATION IS DERIVABLE. *** `rho`
     is applied as a per-tree survival FRACTION against the whole-roster density
     `n_now = sum(nind)` over ALL trees (`rung2_s_demography_harness.jl:521-527`,
     `_hazard_tilt(haz, tp, rho*n_now, n_now)`), not as a count quota carried over from `n_emit`.
     A fraction is scale-free: the absolute budget `(1-rho)*n_now` already scales WITH the roster.
     DERIVED A-PRIORI GATE (panel A): for the uniform arm `S0`, `f[i] = rho` for every tree, so
     E[n_kill] = sum_i (1 - f_i) = (1-rho) * n_tree exactly. If H1 were true the realized rate
     would sit a factor `n_tree/n_emit` BELOW its own implied quota. Pass band |ratio - 1| < 3 SE.
     This is the cheapest real gate available and it also validates the column reading (skill 5f).

H2 — THE `rho >= 1` GATE. The entire decision is wrapped in `if rho < 1.0` (harness :521): when
     the count model predicts the stand GROWS, the arm nominates nobody and the year's
     discretionary mortality is identically zero. FIT meanwhile kills 2.1 %/yr regardless.
     NULL, DERIVED: `NP` sets `rho = 1.0` unconditionally (harness :519), so its incidence must be
     100.0 % and its nominated kill rate exactly 0.000 — a free construction check on the reading.

H3 — THE BUDGET IS THE NET, THE FLUX IS THE GROSS. `rho ~ n_next/n_now`, so the operator's budget
     `(1-rho)*n_now` approximates `K - R` (kills minus recruits), the NET count change — while the
     mortality flux that moves biomass is the GROSS `K`. Establishment is deferred to the C
     (`ESTAB_C`; `n_recruit = 0` by construction, harness :573), so `R` arrives regardless and the
     operator is handed a net target to deliver a gross flux.
     FALSIFIABLE PREDICTION: FIT's gross kill rate minus the operator's realized nomination rate
     should be of the order of FIT's recruitment rate. Both measured here independently — `K` and
     `R` from the REC dumps by the count identity below, the budget from the arm logs. If
     `R_FIT` is ~0 the hypothesis is dead and the deficit must be sought elsewhere.

     THE COUNT IDENTITY used for FIT (no index tracking, so the `ERROR043` duplicate-key fault
     cannot corrupt it): ADR 0123 makes the binary DEFER its kills, so the `mort` roster is
     identical in LENGTH to `grow`, carries the killed stems flagged, and STILL CARRIES THEM at
     `post`. The roster therefore only GAINS between `mort` and `post`, and per patch-year
         K = #{mort records with isdead == 1}
         R = n_post - n_grow
     with `n_grow`/`n_post` plain record counts — recruits need no identity at all. `scan_rec_dump`
     GATES the retention claim per patch-year instead of trusting it; see its docstring for the
     basis error the naive `R = n_post - (n_grow - K)` caused and the tell that caught it.

── WHAT THIS SCORER DELIBERATELY DOES NOT DO ────────────────────────────────────────────────────
It does not re-derive ADR 0185 section 5's departure basis: panels that quote a departure `import`
`diagnose_rung2_map_target_response` and reuse its `Leg`, its readers and its coverage gate
(skill trap 5c — a re-implementation flipped the SIGN of the count departure once already). It
scores counts, not mass: ADR 0187 already has the mass flux, and the budget under test IS a count
budget. And it prints `NP` in every table, because in a rung-2 arm the C grows the stand so any
stand-derived statistic is inherited by the do-nothing null (skill trap 5).

Usage
    export NPREV=predict
    /home/jamirp/.conda/envs/py311_new/bin/python scripts/diagnose_rung2_kill_budget.py
    # full REC scan is ~1.9 GB / a few minutes; SKIP_REC=1 runs panels A-D only.
"""

from __future__ import annotations

import glob
import math
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ADR 0186's rule: import the criterion's own definition rather than re-implementing it. This also
# brings the completion/coverage gate that excludes the 92 truncated legs (skill trap 2).
from diagnose_rung2_map_target_response import (  # noqa: E402
    APPLY_RE,
    LEG,
    NPATCH,
    NPREV,
    ROOT,
    _split_arms,
    run_completed,
)

#: the harness's own clamp bounds (`rung2_s_demography_harness.jl:519`)
RHO_LO, RHO_HI = 0.7, 1.3
#: H1's pass band, in units of the statistic's own sampling SE. Pre-registered BEFORE the run and
#: not moved afterwards (skill trap 5f) — the SE is derived from the between-cell spread and
#: printed beside the verdict, together with the sigma-departure.
H1_SIGMA = 3.0
#: which arms are REPORTED. Default unchanged so ADR 0188's tables reproduce; widen it for the
#: gross-budget campaign with `export ARMS="NP S0 S0h S1 G0 G0h G1"` (ADR 0240). `APPLY_RE`
#: (imported) already DISCOVERS the `G*` legs, so this is the only knob.
ARMS = tuple(_split_arms(os.environ.get("ARMS", "NP S0 S0h S1")))
SCENS = ("historic", "ssp370")
#: the gross-budget arms — the ones whose logs carry `budget`/`acct`/`rho_eff` (ADR 0240).
GROSS_ARMS = ("G0", "G0h", "G1")


def median(v):
    s = sorted(v)
    n = len(s)
    if n == 0:
        return float("nan")
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def mean(v):
    return sum(v) / len(v) if v else float("nan")


def sd(v):
    if len(v) < 2:
        return float("nan")
    m = mean(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))


def se(v):
    """The between-cell standard error. Cells are the independent unit here: patch-years inside a
    cell share a stand and a forcing, so pooling them would understate the SE (skill trap 5f)."""
    return sd(v) / math.sqrt(len(v)) if len(v) >= 2 else float("nan")


# ── the arm logs ─────────────────────────────────────────────────────────────────────────────────

class ArmLeg:
    """Per-(cell, arm, seed, scenario) budget accounting from one `s_arm_log.txt`."""

    def __init__(self):
        self.rows = 0
        self.n_tree = 0.0          # roster stems (the population the thinning acts on)
        self.n_emit = 0.0          # >5 m stems (the population rho was derived on)
        self.n_kill = 0.0          # the arm's NOMINATIONS
        self.budget_pos = 0.0      # sum max(0, 1-rho)*n_tree  — what the operator can spend
        self.budget_net = 0.0      # sum (1-rho)*n_tree        — the signed net the model predicts
        self.rho_ge1 = 0
        self.rho_lo = 0
        self.rho_hi = 0
        self.theta0 = 0            # S1: the tilt gave up (certain kills already overshot)
        self.shortfall = 0
        self.years = set()
        self.patches = set()
        # ── ADR 0240, the gross-budget columns. Present in every log written after 2026-08-13; a
        #    leg from an older log leaves `has_g` False and panel F reports it as unavailable rather
        #    than as zero (a missing measurement is not a value).
        self.has_g = False
        self.n_age1 = 0.0          # #{age == 1} — last year's recruits, EXACT (ADR 0189 §2)
        self.budget = 0.0          # sum of the spendable budget `b`
        self.budget_empty = 0      # patch-years with b <= 0: the account's own gate
        self.acct_pos = 0          # patch-years leaving a POSITIVE account (unspent budget carried)
        self.acct_neg = 0          # ... and a negative one (an overspend being repaid)
        #: n_kill histogram over patch-years — the LUMPINESS check ADR 0189 §7 asks for: FIT spreads
        #: ~6 %/yr fairly evenly, and an account that delivers the same leg mean in fewer, bigger
        #: years is a different mortality regime. Keyed by integer kill count; a few dozen keys.
        self.kill_hist = defaultdict(int)
        #: per patch, the roster count at the leg's FIRST and LAST year — the ROSTER-HORIZON column,
        #: MEASURED rather than implied (ADR 0189's `_acct` panel could only imply it).
        self.first = {}
        self.last = {}

    def add(
        self, year, patch, n_tree, n_emit, rho, theta, shortfall, n_kill,
        n_age1=None, budget=None, acct=None,
    ):
        self.rows += 1
        self.years.add(year)
        self.patches.add(patch)
        self.n_tree += n_tree
        self.n_emit += n_emit
        self.n_kill += n_kill
        self.budget_net += (1.0 - rho) * n_tree
        if rho < 1.0:
            self.budget_pos += (1.0 - rho) * n_tree
        else:
            self.rho_ge1 += 1
        if rho <= RHO_LO + 1e-9:
            self.rho_lo += 1
        if rho >= RHO_HI - 1e-9:
            self.rho_hi += 1
        if theta is not None and theta == 0.0:
            self.theta0 += 1
        if shortfall > 0.0:
            self.shortfall += 1
        self.kill_hist[int(round(n_kill))] += 1
        if patch not in self.first or year < self.first[patch][0]:
            self.first[patch] = (year, n_tree)
        if patch not in self.last or year > self.last[patch][0]:
            self.last[patch] = (year, n_tree)
        if n_age1 is not None:
            self.has_g = True
            self.n_age1 += n_age1
            if budget is not None and not math.isnan(budget):
                self.budget += budget
                if budget <= 0.0:
                    self.budget_empty += 1
            if acct is not None and not math.isnan(acct):
                if acct > 1e-12:
                    self.acct_pos += 1
                elif acct < -1e-12:
                    self.acct_neg += 1

    def roster_factor(self):
        """The arm's OWN roster over the leg: last year's stems / the first year's; 1.0 = flat.

        ⚠ This is the check that catches trading a biomass excess for a stand collapse (ADR 0189
        §6): a kill rate that clears its criterion while the roster runs to 0.1x has not fixed the
        demography. Read it beside every rate, never instead of one."""
        a = sum(v for _y, v in self.first.values())
        b = sum(v for _y, v in self.last.values())
        return b / a if a > 0 else float("nan")

    def zero_kill_share(self):
        return self.kill_hist.get(0, 0) / self.rows if self.rows else float("nan")

    def kill_top_decile(self):
        """Share of the leg's kills falling in the heaviest 10 % of patch-years (lumpiness)."""
        if not self.rows or self.n_kill <= 0:
            return float("nan")
        want = max(1, int(round(0.1 * self.rows)))
        got = tot = 0
        for k in sorted(self.kill_hist, reverse=True):
            take = min(self.kill_hist[k], want - got)
            tot += take * k
            got += take
            if got >= want:
                break
        return tot / self.n_kill

    def complete(self, scen):
        y0, y1 = LEG[scen]
        return len(self.years) == (y1 - y0 + 1) and len(self.patches) == NPATCH


def read_arm_log(path: str) -> ArmLeg:
    """Columns come from the file's own `#H L` header. Name n is field n+1 — the record's field 0
    is the `L` tag (skill trap 1: the offset fails SILENTLY between two float columns)."""
    leg = ArmLeg()
    cols = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#H L"):
                cols = {n: i + 1 for i, n in enumerate(line.split()[2:])}
                continue
            if not line.startswith("L "):
                continue
            if cols is None:
                raise SystemExit(f"{path}: an L record before its '#H L' header")
            f = line.split()
            th = f[cols["theta"]]
            # The ADR-0240 columns are APPENDED, and every reader here takes positions off the
            # header, so an older log simply has no `n_age1` key and the leg stays non-`has_g`.
            def _opt(name, f=f, cols=cols):
                return float(f[cols[name]]) if name in cols else None
            leg.add(
                int(f[cols["year"]]),
                int(f[cols["patch"]]),
                float(f[cols["n_tree"]]),
                float(f[cols["n_emit"]]),
                float(f[cols["rho"]]),
                None if th == "NaN" else float(th),
                float(f[cols["shortfall"]]),
                float(f[cols["n_kill"]]),
                _opt("n_age1"), _opt("budget"), _opt("acct"),
            )
    return leg


def collect_arms():
    """-> {(cell, arm, scen, seed): ArmLeg}, plus the excluded list. Reuses the completion gate."""
    got, excluded = {}, []
    for d in sorted(glob.glob(os.path.join(ROOT, "S_r2s_*_apply"))):
        m = APPLY_RE.match(os.path.basename(d))
        if not m:
            continue
        scen, cell, arm, seed = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        if scen not in SCENS:
            continue
        log = os.path.join(d, "s_arm_log.txt")
        if not os.path.exists(log):
            excluded.append((cell, arm, scen, seed, "no s_arm_log.txt"))
            continue
        if not run_completed(scen, cell, arm, NPREV, seed):
            excluded.append((cell, arm, scen, seed, "C run has no completion line"))
            continue
        leg = read_arm_log(log)
        if not leg.complete(scen):
            excluded.append(
                (cell, arm, scen, seed,
                 f"incomplete: {len(leg.years)} yr x {len(leg.patches)} patches")
            )
            continue
        got[(cell, arm, scen, seed)] = leg
    return got, excluded


# ── FIT's own side, from the REC dumps ───────────────────────────────────────────────────────────

REC_RE = re.compile(r"^S_r2s_(historic|ssp370)_c(\d+)_REC_" + NPREV + r"_s(\d+)_dump$")


def scan_rec_dump(path: str):
    """FIT's gross kills and recruits per patch-year by a count identity, with its own gate.

    Returns per_year[(year, patch)] = (n_grow, K_all, K_disc, R, retained_ok, fire, n_cert, n_age1).
    Indices 0-5 are the original ADR-0188 set and are NOT renumbered; 6-7 were appended for ADR
    0189's feasibility derivation (`diagnose_rung2_gross_budget_lag.py`) and are read by name there:
        n_cert = stems at `grow` with `mort_prob >= 1`, the non-negotiable deaths every arm honours
                 (`t.mort >= 1.0`, harness :539; the port and FIT's own hazard agree to 5e-18 and
                 pick the identical certain set at recall = precision = 1.0000, ADR 0183)
        n_age1 = stems at `grow` with `age == 1`. `age` at `grow` is POST-increment (skill trap 6)
                 and establishment sets age 0, so this is LAST year's recruit cohort, observable at
                 the rendezvous itself with no interface change. ADR 0189 panel A gates it against
                 `R(y-1)`.
    `K_disc` restricts to `mort_prob < 1`, the population the operator had discretion over — the
    raw `isdead` set is the arm's nomination UNION the C's forced kills and is contaminated 8-100 %
    arm-dependently (skill trap 5d). For `REC` the arm nominates nothing, so `K_all` IS FIT's own
    total, which is what makes REC the like-for-like reference.

    ⚠ THE RECRUIT IDENTITY, AND THE BASIS ERROR IT COST. The obvious form
    `R = n_post - (n_grow - K_all)` assumes the killed stems are GONE from the `post` roster. They
    are NOT: ADR 0123 makes the binary DEFER its demographic kills to the end of the growth loop,
    so a stem flagged `isdead` at `mort` is still a record at `post`. The roster therefore only ever
    GAINS between the two phases, and the identity is simply

        R = n_post - n_grow

    The wrong form inflates R by exactly `K_all` — it put FIT's recruitment at 10.5-12.6 %/yr and
    its net roster growth at +4.6 to +6.5 %/yr sustained over 81 years, which would have made the
    roster explode by orders of magnitude. IMPLAUSIBILITY OF A LEVEL IS THE TELL; every ratio
    between arms would have looked perfectly sane.

    THE LICENSING CONDITION IS `n_post >= n_grow` (no stem removed) — MEASURED AT 30 300 OF 30 300
    PATCH-YEARS. It is deliberately NOT `dead@post == dead@mort`: a first version required that too
    and reported a 13.2 % "violation" rate that is not a violation at all. FIRE flags additional
    stems dead between the two phases (ADR 0121) — measured one-directional, `dead@post >=
    dead@mort` in 8100 of 8100 patch-years and never below, adding 33 % more dead flags on top of
    the demographic kills. Fire is not the demography interface's to own, so `K_all` is read at
    `mort` and the fire excess is reported separately rather than folded into FIT's mortality.
    A GATE THAT IS STRICTER THAN ITS OWN IDENTITY MANUFACTURES DOUBT ABOUT A SOUND NUMBER.
    """
    n_grow = defaultdict(int)
    n_post = defaultdict(int)
    k_all = defaultdict(int)
    k_disc = defaultdict(int)
    d_post = defaultdict(int)
    n_cert = defaultdict(int)
    n_age1 = defaultdict(int)
    tcols = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#H T"):
                # "#H T phase lon lat ..." -> record "T grow ...", so name n is field n+1
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
            key = (int(f[tcols["year"]]), int(f[tcols["patch"]]))
            if phase == "grow":
                n_grow[key] += 1
                if float(f[tcols["mort_prob"]]) >= 1.0:
                    n_cert[key] += 1
                if int(float(f[tcols["age"]])) == 1:
                    n_age1[key] += 1
            elif phase == "post":
                n_post[key] += 1
                if int(float(f[tcols["isdead"]])) == 1:
                    d_post[key] += 1
            elif phase == "mort":
                if int(float(f[tcols["isdead"]])) == 1:
                    k_all[key] += 1
                    if float(f[tcols["mort_prob"]]) < 1.0:
                        k_disc[key] += 1
    per_year = {}
    for key, ng in n_grow.items():
        if key not in n_post:
            continue
        ka = k_all.get(key, 0)
        # THE gate on the deferred-kill assumption: no stem may be REMOVED between `mort` and
        # `post`, which is exactly what licenses `R = n_post - n_grow`. Extra dead FLAGS are fire
        # (ADR 0121) and are counted separately, not treated as a violation.
        retained_ok = n_post[key] >= ng
        fire = max(0, d_post.get(key, 0) - ka)
        per_year[key] = (
            ng, ka, k_disc.get(key, 0), n_post[key] - ng, retained_ok, fire,
            n_cert.get(key, 0), n_age1.get(key, 0),
        )
    return per_year


def collect_rec():
    """-> {(cell, scen): {(year, patch): (n_grow, K_all, K_disc, R)}}"""
    got = {}
    for d in sorted(glob.glob(os.path.join(ROOT, "S_r2s_*_REC_*_dump"))):
        m = REC_RE.match(os.path.basename(d))
        if not m:
            continue
        scen, cell = m.group(1), int(m.group(2))
        f = os.path.join(d, "roster_rank0000.txt")
        if not os.path.exists(f):
            continue
        py = scan_rec_dump(f)
        if py:
            got[(cell, scen)] = py
        print(f"    REC {scen:8s} c{cell:<6d} {len(py):6d} patch-years", flush=True)
    return got


# ── panels ───────────────────────────────────────────────────────────────────────────────────────

def ratio(num: str, den: str):
    """An accessor for `per_cell`: the ratio of two `ArmLeg` fields, NaN on a zero denominator."""
    return lambda g: (getattr(g, num) / getattr(g, den)) if getattr(g, den) else float("nan")


def per_cell(legs, arm, scen, fn):
    """Seeds averaged within a cell, then the per-cell values (ADR 0185 section 5's shape)."""
    by_cell = defaultdict(list)
    for (cell, a, s, _seed), leg in legs.items():
        if a == arm and s == scen:
            by_cell[cell].append(fn(leg))
    return {c: mean(v) for c, v in by_cell.items()}


def main() -> int:
    if NPREV != "predict":
        print(f"  NOTE: NPREV={NPREV}. ADR 0185-0187 are all on `predict`; "
              f"set NPREV=predict to reproduce them.")
    print("=" * 100)
    print("  RUNG-2 KILL BUDGET — why the operator kills too few of the biomass-bearing trees")
    print(f"  mode NPREV={NPREV}   ARMS={list(ARMS)}   root {ROOT}")
    print("=" * 100)

    legs, excluded = collect_arms()
    cells = sorted({c for (c, _a, _s, _sd) in legs})
    print(f"\n  {len(legs)} leg(s) passed the completion+coverage gate over {len(cells)} cells")
    if excluded:
        print(f"  {len(excluded)} leg(s) EXCLUDED (named, per skill trap 2):")
        for cell, arm, scen, seed, why in excluded[:12]:
            print(f"      c{cell:<6d} {arm:4s} {scen:9s} s{seed}  {why}")
        if len(excluded) > 12:
            print(f"      ... and {len(excluded) - 12} more")

    # ── PANEL A — H1's derived a-priori gate ────────────────────────────────────────────────────
    print("\n" + "-" * 100)
    print("  PANEL A — H1: is the quota under-spent by the roster/emitted population ratio?")
    print("-" * 100)
    print("    DERIVED A PRIORI: for the uniform arm S0, f[i] = rho for every tree, so the")
    print("    nominated kill rate must EQUAL its own implied quota (1-rho) on the ROSTER basis.")
    print("    H1 predicts a realized/implied ratio near 1/(n_tree/n_emit); the harness algebra")
    print("    predicts 1.00. Both cannot hold.\n")
    print(f"    {'arm':<5} {'leg':<9} {'n_tree/n_emit':>14} {'realized%':>10}"
          f" {'implied%':>10} {'ratio':>8} {'SE':>7} {'sigma':>7}")
    h1 = {}
    for arm in ARMS:
        for scen in SCENS:
            pr = per_cell(legs, arm, scen, ratio("n_tree", "n_emit"))
            rz = per_cell(legs, arm, scen, ratio("n_kill", "n_tree"))
            im = per_cell(legs, arm, scen, ratio("budget_pos", "n_tree"))
            if not pr:
                continue
            cs = sorted(set(rz) & set(im))
            ratios = [rz[c] / im[c] for c in cs if im[c] > 0]
            r, s_, n = median(ratios), se(ratios), len(ratios)
            sig = abs(r - 1.0) / s_ if s_ and not math.isnan(s_) and s_ > 0 else float("nan")
            print(f"    {arm:<5} {scen:<9} {median(list(pr.values())):>14.3f}"
                  f" {100 * median(list(rz.values())):>10.3f}"
                  f" {100 * median(list(im.values())):>10.3f}"
                  f" {r:>8.3f} {s_:>7.3f} {sig:>7.2f}")
            h1[(arm, scen)] = (r, s_, sig, n)
    print("\n    THE GATE (S0, the derivable arm — it is the only one whose answer is known):")
    for scen in SCENS:
        if ("S0", scen) not in h1:
            continue
        r, s_, sig, n = h1[("S0", scen)]
        pr = median(list(per_cell(legs, "S0", scen, ratio("n_tree", "n_emit")).values()))
        ok = (not math.isnan(sig)) and sig < H1_SIGMA
        print(f"      {scen:9s} ratio {r:.3f} +- {s_:.3f} ({sig:.2f} sigma, n={n} cells)"
              f"  -> {'PASS: quota fully spent, scale-free' if ok else 'FAIL'}")
        print(f"                 H1 would need {1 / pr:.3f}; measured is {r:.3f}"
              f"  -> H1 {'REFUTED' if ok else 'not refuted'}")

    # ── PANEL B — the clamp ─────────────────────────────────────────────────────────────────────
    print("\n" + "-" * 100)
    print("  PANEL B — is the rho clamp [0.7, 1.3] binding? (the handoff's stated assumption)")
    print("-" * 100)
    print(f"    {'arm':<5} {'leg':<9} {'rho<=0.7':>10} {'rho>=1.3':>10}")
    for arm in ARMS:
        for scen in SCENS:
            lo = per_cell(legs, arm, scen, ratio("rho_lo", "rows"))
            hi = per_cell(legs, arm, scen, ratio("rho_hi", "rows"))
            if not lo:
                continue
            print(f"    {arm:<5} {scen:<9} {100 * median(list(lo.values())):>9.2f}%"
                  f" {100 * median(list(hi.values())):>9.2f}%")
    print("\n    The LOW bound could cap the kill rate: rho >= 0.7 caps thinning at")
    print("    30 %/yr of the roster, far above the 2.1 %/yr FIT needs. Read its incidence above.")

    # ── PANEL C — H2, the rho >= 1 gate ─────────────────────────────────────────────────────────
    print("\n" + "-" * 100)
    print("  PANEL C — H2: how often does the operator nominate NOBODY because rho >= 1?")
    print("-" * 100)
    print("    `if rho < 1.0` (harness :521) gates the WHOLE decision. NULL, derived: NP sets")
    print("    rho = 1.0 unconditionally, so it must read 100.0 % with a 0.000 % kill rate.\n")
    print(f"    {'arm':<5} {'leg':<9} {'rho>=1 share':>13} {'SE':>7} {'nominated%/yr':>14}"
          f" {'theta==0':>9} {'shortfall>0':>12}")
    for arm in ARMS:
        for scen in SCENS:
            g1 = per_cell(legs, arm, scen, ratio("rho_ge1", "rows"))
            kr = per_cell(legs, arm, scen, ratio("n_kill", "n_tree"))
            t0 = per_cell(legs, arm, scen, ratio("theta0", "rows"))
            sf = per_cell(legs, arm, scen, ratio("shortfall", "rows"))
            if not g1:
                continue
            v = list(g1.values())
            print(f"    {arm:<5} {scen:<9} {100 * median(v):>12.1f}% {se(v):>7.4f}"
                  f" {100 * median(list(kr.values())):>14.3f}"
                  f" {100 * median(list(t0.values())):>8.1f}%"
                  f" {100 * median(list(sf.values())):>11.1f}%")
    print("\n    theta == 0 is the tilt solver REPORTING that it gave up: the certain kills alone")
    print("    already reached the count target, so every non-condemned tree is spared")
    print("    (`_hazard_tilt`, slow.jl:929-933). It is a logged override of the count model.")
    print("    NOTE S0h reaches the SAME state through `c = clamp(rho*n_now/n_free, 0, 1)` hitting")
    print("    1.0, but its `shortfall` column tests a DIFFERENT condition (rho*n_now < n_cert)")
    print("    and so reports 0 % — its starvation is real but unlogged. Do not read S0h's 0 % as")
    print("    'no override'.")

    # ── PANEL D — the budget vs the nominations ─────────────────────────────────────────────────
    print("\n" + "-" * 100)
    print("  PANEL D — the count-implied budget vs what is actually nominated")
    print("-" * 100)
    print(f"    {'arm':<5} {'leg':<9} {'budget+ %/yr':>13} {'budget_net %/yr':>16}"
          f" {'nominated %/yr':>15} {'nom/budget+':>12}")
    for arm in ARMS:
        for scen in SCENS:
            bp = per_cell(legs, arm, scen, ratio("budget_pos", "n_tree"))
            bn = per_cell(legs, arm, scen, ratio("budget_net", "n_tree"))
            kr = per_cell(legs, arm, scen, ratio("n_kill", "n_tree"))
            if not bp:
                continue
            cs = sorted(set(kr) & set(bp))
            rat = median([kr[c] / bp[c] for c in cs if bp[c] > 0])
            print(f"    {arm:<5} {scen:<9} {100 * median(list(bp.values())):>13.3f}"
                  f" {100 * median(list(bn.values())):>16.3f}"
                  f" {100 * median(list(kr.values())):>15.3f} {rat:>12.2f}")
    print("\n    `budget+` = sum max(0,1-rho)*n_tree / sum n_tree — what the operator may spend.")
    print("    `budget_net` = the SIGNED net count change the count model predicts (H3's term).")
    print("    A nom/budget+ well ABOVE 1 means the nominations are dominated by stems the arm has")
    print("    no discretion over (certain kills, f = 0), i.e. the budget is already overdrawn.")

    if os.environ.get("SKIP_REC"):
        print("\n  SKIP_REC set — panel E (FIT's gross kills and recruits) not run.")
        # Panel F still runs: it is arm-logs-only, so SKIP_REC (which skips the 1.9 GB REC dump
        # scan) must not suppress it. It is handed an EMPTY `fit` and says so.
        panel_f(legs, {})
        return 0

    # ── PANEL E — H3, gross vs net on FIT's own roster ──────────────────────────────────────────
    print("\n" + "-" * 100)
    print("  PANEL E — H3: FIT's GROSS mortality vs the NET the count model can express")
    print("-" * 100)
    print("    scanning the REC dumps (FIT's own roster, ~1.9 GB) ...", flush=True)
    rec = collect_rec()
    if not rec:
        print("    no REC dumps found — panel E cannot run.")
        panel_f(legs, {})
        return 0
    bad = sum(1 for py in rec.values() for v in py.values() if not v[4])
    tot = sum(len(py) for py in rec.values())
    fire = sum(v[5] for py in rec.values() for v in py.values())
    kdem = sum(v[1] for py in rec.values() for v in py.values())
    print(f"\n    DEFERRED-KILL GATE: {tot - bad} of {tot} patch-years remove NO stem between")
    print(f"    `mort` and `post` ({100 * bad / tot:.2f} % violations) — this, and only this,")
    print("    licenses `R = n_post - n_grow`. See `scan_rec_dump`'s docstring for the basis")
    print("    error the naive form caused and why the gate is not stricter than its identity.")
    print(f"    FIRE (ADR 0121, not the demography interface's to own) flags {fire} further stems")
    print(f"    dead at `post`, {100 * fire / kdem:.1f} % on top of the {kdem} demographic kills;")
    print("    `K_all` is read at `mort` and excludes them.")
    print(f"\n    {'leg':<9} {'cells':>6} {'K_all %/yr':>11} {'K_disc %/yr':>12}"
          f" {'K_cert %/yr':>12} {'R %/yr':>9} {'net=R-K %/yr':>13}")
    fit = {}
    for scen in SCENS:
        ka, kd, kc, rr, nt = {}, {}, {}, {}, {}
        for (cell, s), py in rec.items():
            if s != scen:
                continue
            ng = sum(v[0] for v in py.values())
            if ng == 0:
                continue
            ka[cell] = sum(v[1] for v in py.values()) / ng
            kd[cell] = sum(v[2] for v in py.values()) / ng
            kc[cell] = ka[cell] - kd[cell]
            rr[cell] = sum(v[3] for v in py.values()) / ng
            nt[cell] = rr[cell] - ka[cell]
        if not ka:
            continue
        fit[scen] = (ka, kd, kc, rr, nt)
        print(f"    {scen:<9} {len(ka):>6d} {100 * median(list(ka.values())):>11.3f}"
              f" {100 * median(list(kd.values())):>12.3f}"
              f" {100 * median(list(kc.values())):>12.3f}"
              f" {100 * median(list(rr.values())):>9.3f}"
              f" {100 * median(list(nt.values())):>13.3f}")
    print("\n    K_all  = every stem the C flagged dead    (FIT nominates alone in REC)")
    print("    K_disc = restricted to mort_prob < 1, the discretionary population")
    print("    K_cert = K_all - K_disc, the non-negotiable deaths every arm honours")
    print("    R      = n_post - n_grow, the recruits (the dead are still carried at `post`)")
    print("    net    = R - K_all, FIT's own roster count change")

    print("\n    THE H3 CLOSURE — the operator's budget is the NET; the flux it must")
    print("    produce is the GROSS. Every column is % of roster per year, same basis.")
    print(f"    {'arm':<5} {'leg':<9} {'FIT gross K':>12} {'FIT R':>8} {'FIT net':>8}"
          f" {'budget+':>8} {'FIT K_cert':>11} {'overdraw':>9} {'gross/budget':>13}")
    for arm in ("S0", "S0h", "S1"):
        for scen in SCENS:
            if scen not in fit:
                continue
            ka, _kd, kc, rr, nt = fit[scen]
            bp = per_cell(legs, arm, scen, ratio("budget_pos", "n_tree"))
            cs = sorted(set(ka) & set(bp))
            if not cs:
                continue
            print(f"    {arm:<5} {scen:<9} {100 * median([ka[c] for c in cs]):>12.3f}"
                  f" {100 * median([rr[c] for c in cs]):>8.3f}"
                  f" {100 * median([nt[c] for c in cs]):>8.3f}"
                  f" {100 * median([bp[c] for c in cs]):>8.3f}"
                  f" {100 * median([kc[c] for c in cs]):>11.3f}"
                  f" {median([kc[c] / bp[c] for c in cs if bp[c] > 0]):>8.2f}x"
                  f" {median([ka[c] / bp[c] for c in cs if bp[c] > 0]):>12.2f}x")
    print("\n    `budget+` = the operator's spendable budget, sum max(0,1-rho)*n_tree / n_tree.")
    print("    `overdraw` = FIT K_cert / budget+ — how far the NON-NEGOTIABLE deaths alone exceed")
    print("    the whole budget. Above 1 the discretionary channel is starved before it is")
    print("    even reached,")
    print("    which is what theta == 0 reports in panel C.")
    print("    `gross/budget` = FIT K_all / budget+ — the size of the mechanism.")
    print("\n    H3's prediction was `FIT gross K - nominated ~ FIT R`. Read FIT R against the gap")
    print("    between `FIT gross K` and `budget+`: if R were ~0 the budget would equal the gross")
    print("    flux and H3 would be dead.")

    panel_f(legs, fit)
    return 0


def panel_f(legs, fit):
    """PANEL F — the GROSS-BUDGET arms: what they spend, and what it costs the stand (ADR 0240).

    This is the panel ADR 0189 §7 asks for beside every kill rate, and it is deliberately not just a
    rate table:

    * `rate` is the arm's NOMINATION rate (`n_kill`/`n_tree`), the same quantity panel B reports —
      not the discretionary rate the criterion is written on, which needs `mort_prob` per stem, so
      lives in `diagnose_rung2_kill_selectivity.py`. Named `nominated` here for exactly that reason.
    * `roster` is the ROSTER-HORIZON column and it is MEASURED (the arm's own first-to-last-year
      stem count), not implied from a leg mean. A rate that clears its criterion while this runs
      to 0.1x has traded a biomass excess for a stand collapse (ADR 0189 §6, skill trap 5k).
    * `empty` is the account's own gate — patch-years the arm answered with an EMPTY kill list. For
      an `S*` arm the equivalent gate is `rho >= 1` (panel C), printed in the same column so the two
      regimes are comparable. The account is EXPECTED to raise it (40-61 % vs 21.8 % for the naive
      lagged form) and the two lumpiness columns are what makes that visible rather than hidden.
    * `spend` = realized nominations / budget. Above 1 the certain deaths overshot the budget (they
      cannot be un-killed); the account then charges the overshoot and suppresses later kills, which
      is the whole point of the accounting form and shows up as a raised `empty`.

    ⚠ FIT's own row is the like-for-like reference for `nominated`? NO — FIT nominates nothing, its
    numbers come from the dumps (panel E), and its gross/certain/discretionary rates are printed
    there. Do not read an arm's `nominated` against FIT's gross K without that panel open: an arm's
    nomination excludes the C's own hard kills (skill trap 5d).
    """
    gross = [a for a in ARMS if a in GROSS_ARMS]
    print("\n" + "=" * 100)
    print("  PANEL F — the GROSS-BUDGET (`G*`) arms: rate, the roster horizon, and lumpiness")
    print("=" * 100)
    if not gross:
        print(f"    no `G*` arm in ARMS={list(ARMS)} — nothing to report. Widen it with")
        print('    `export ARMS="NP S0 S0h S1 G0 G0h G1"` once the ADR-0240 campaign has run.')
        return
    have = [a for a in gross if any(k[1] == a for k in legs)]
    if not have:
        print(f"    ARMS names {gross} but no leg of any of them passed the coverage gate.")
        return

    print(f"    {'arm':<5} {'leg':<9} {'nominated':>10} {'empty':>7} {'zero-kill':>10}"
          f" {'top-decile':>11} {'roster':>8} {'spend':>7} {'R_hat':>7} {'cells':>6}")
    for arm in [a for a in ARMS if a in ("S0", "S0h", "S1") or a in GROSS_ARMS]:
        for scen in SCENS:
            ks = [k for k in legs if k[1] == arm and k[2] == scen]
            if not ks:
                continue
            isg = arm in GROSS_ARMS
            nom = per_cell(legs, arm, scen, ratio("n_kill", "n_tree"))
            rho1 = per_cell(
                legs, arm, scen, lambda g: g.rho_ge1 / g.rows if g.rows else float("nan")
            )
            emp = per_cell(
                legs, arm, scen,
                lambda g: (g.budget_empty / g.rows if g.has_g and g.rows else float("nan")),
            ) if isg else rho1
            zer = per_cell(legs, arm, scen, lambda g: g.zero_kill_share())
            top = per_cell(legs, arm, scen, lambda g: g.kill_top_decile())
            ros = per_cell(legs, arm, scen, lambda g: g.roster_factor())
            spd = per_cell(
                legs, arm, scen,
                lambda g: (g.n_kill / g.budget if g.has_g and g.budget > 0 else float("nan")),
            )
            rht = per_cell(legs, arm, scen, ratio("n_age1", "n_tree"))
            cs = sorted(nom)
            print(f"    {arm:<5} {scen:<9} {100 * median(list(nom.values())):>9.3f}%"
                  f" {median(list(emp.values())):>7.3f}"
                  f" {median(list(zer.values())):>10.3f}"
                  f" {median(list(top.values())):>11.3f}"
                  f" {median(list(ros.values())):>7.3f}x"
                  f" {median(list(spd.values())):>7.3f}"
                  f" {100 * median(list(rht.values())):>6.2f}%"
                  f" {len(cs):>6}")
    print("\n    `nominated` = the arm's own kill nominations / roster, %/yr (NOT the")
    print("    discretionary rate the ADR-0188 §7 criterion is written on — that one is in")
    print("    diagnose_rung2_kill_selectivity.py, which needs per-stem `mort_prob`).")
    print("    `empty` = share of patch-years answered with an EMPTY kill list: `budget <= 0` for")
    print("    a `G*` arm, `rho >= 1` for an `S*` one. `zero-kill` is its realized version.")
    print("    `top-decile` = share of the leg's kills in its heaviest 10 % of patch-years — the")
    print("    LUMPINESS caveat against the accounting form: FIT spreads ~6 %/yr fairly evenly.")
    print("    `roster` = measured last-year/first-year stems. Read it as a GATE, not a")
    print("    diagnostic: a rate that clears 1.5 %/yr at roster 0.1x is a FAIL (ADR 0189 §7a).")
    print("    `spend` = nominations / budget; > 1 means certain deaths overshot and the account")
    print("    is repaying. `R_hat` = the `age == 1` recruit count the budget is built on, %/yr —")
    print("    EXACT, not modelled (ADR 0189 §2), and printed for the `S*` arms too, where it is")
    print("    the budget term they do NOT have.")
    if fit:
        print("\n    FIT's own rates are panel E's (gross K, K_cert, K_disc, R, net) — an arm's")
        print("    `nominated` is not comparable to FIT's gross K without it (skill trap 5d).")


if __name__ == "__main__":
    raise SystemExit(main())
