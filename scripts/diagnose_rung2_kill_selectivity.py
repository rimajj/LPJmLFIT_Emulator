#!/usr/bin/env python
"""WHICH trees the rung-2 emulator kills, against FIT's own kills -- the size/mass channel.

ADR 0186 established that the emulator kills the right NUMBER of trees and holds the wrong stand:
on the ssp370 leg at the FIT-GAIN cells the trait arms hold -2.9 % / -13.6 % the stems FIT holds
and +89 % / +91 % the biomass, with per-stem mass +63...+246 %, for all 81 years. A count
statistic provably cannot see that failure -- the count statistic is *satisfied* while the stand
is wrong -- so the remaining question is which individual trees die. This is that measurement.

================================================================================================
PRE-REGISTRATION (written before the run; do not move a threshold afterwards)
================================================================================================

THE HYPOTHESIS (falsifiable).  The learned arms spare high-mass stems that FIT removes. If true,
their kill set is biased LIGHT relative to FIT's, the spared mass compounds over the leg, and the
+90 % agb excess is a consequence of kill SELECTIVITY rather than of growth or recruitment.

REFUTED IF the arms' mass selectivity matches FIT's within the refute band below. Then the agb
excess cannot come from which-trees-die and the next rung must look at growth/recruitment. Either
outcome is a result; this probe is designed to be able to come back negative.

⚠ THE COMPARISON-BASIS PROBLEM, AND WHY THE STATISTIC IS A RATIO OF FRACTIONS.  The arms' stands
and FIT's have DIVERGED (that is ADR 0184/0185/0186's structural departure: +89...+312 % agb,
+54...+160 % age_mean). So a raw histogram of killed stems, or any comparison of absolute killed
mass, is NOT like-for-like -- it would mostly measure the stand difference already published.
Every statistic here is therefore computed WITHIN an arm's own stand and only then compared:

    kill_frac_n = (# stems killed) / (# stems present)        <- the COUNT channel (known on target)
    kill_frac_m = (agb killed)     / (agb present)            <- the MASS channel
    LAMBDA      = kill_frac_m / kill_frac_n                   <- THE BLESSED STATISTIC

LAMBDA is the mass selectivity of the kill: 1.0 means the killed stems carry exactly their
population share of biomass, > 1 means the operator removes mass-heavy stems, < 1 means it spares
them. Both factors are ratios inside the same arm's own stand at the same instant, so the level
divergence cancels to first order and what survives is the operator's preference.

⚠ THE DERIVED NULL VALUES -- written down BEFORE the read, per ADR 0184's gotcha (it is not enough
to score a null; you must derive what it MUST return for the blessed statistic, or a statistic the
null passes by construction gets quoted as skill):

    S0  (uniform thinning) -> LAMBDA = 1.00 EXACTLY, and selection differential 0.00, BY
        CONSTRUCTION: `f[i] = rho` for every tree and a tree dies iff `rand() > f[i]`
        (`rung2_s_demography_harness.jl:529-530`), a draw independent of size, so the killed stems
        are an unbiased sample of the stand's mass. S0 near 1.00 is therefore NOT evidence about
        the emulator -- it is a HARD SELF-TEST OF THIS SCORER. If S0 departs from 1.00 by more
        than S0_SELFTEST_TOL, read the scorer before reading the verdict.
    NP  (persistence null, rho = 1) -> nominates NOTHING (measured: 0 of 12 393 kills over 12 legs
        are its own), so LAMBDA is undefined on the discretionary population and NP is reported
        but not compared. This is itself the check that the discretionary restriction below works.
    REC (pure observation) -> FIT's own kills. LAMBDA_REC is the TARGET, not a null.

⚠ WHY THE POPULATION IS RESTRICTED TO DISCRETIONARY STEMS (`mort_prob < 1`) -- A BASIS ERROR THE
S0 SELF-TEST CAUGHT, NOT A THRESHOLD THAT WAS MOVED.  The first version of this probe scored every
`isdead` stem, and S0 returned LAMBDA = 0.287 against its derived 1.00. S0 is genuinely uniform,
so the fault was the statistic: the `mort`-phase `isdead` set is the arm's nomination UNION the C's
own non-negotiable kills, which the C applies whatever the arm answers (negative pools /
`isneg_tree`, bioclimatic `survive()`, `cut_year`; the harness's own header lists them). Those are
dying stems and carry almost no mass, so they drag LAMBDA down -- and their share of the kill set
is wildly arm-dependent, measured off the audit logs over the 12 cells' ssp370 legs:

        NP 100.0 %   S0 45.8 %   S0h 7.9 %   S1 8.7 %      (forced / total kills)

A statistic whose contamination runs from 8 % to 100 % across the arms being compared cannot rank
them. So the blessed population is the stems the operator actually had discretion over,
`mort_prob < 1.0`: a stem at `mort_prob >= 1` is dead by FIT's own arithmetic no matter what the
emulator says (and S0h/S1 honour precisely that set by construction), so including it scores
agreement about a foregone conclusion. The restriction is applied IDENTICALLY to every arm
including REC, so the comparison stays symmetric -- which dropping whole patch-years per arm would
NOT have been (retention would have been 68 % for S0 against 93 % for S1).

⚠ AND THE ESTIMATOR IS STRATIFIED BY PATCH-YEAR -- THE SECOND THING THE S0 SELF-TEST CAUGHT.
Restricting to discretionary stems still left S0 off its derived 1.00, and again the estimator was
at fault, for a reason that should have been derived up front: pooled over a leg,

    LAMBDA_pooled  =  <(1-rho)>_mass-weighted  /  <(1-rho)>_count-weighted   over patch-years,

which is 1 only if the thinning ratio is uncorrelated with per-stem mass ACROSS patch-years. It is
not -- the patches thinned hardest are the dense, old, heavy ones -- so the pooled statistic
carries a between-stratum term that has nothing to do with the operator's preference. The operator
draws ONCE PER PATCH-YEAR, so the patch-year is the stratum at which the null is exact. LAMBDA is
therefore the kill-weighted mean over patch-years of
`mean(mass | killed) / mean(mass | present)`, and its derived null for S0 is exactly 1.00 with no
confound. `lam_pooled` is still printed beside it, per ADR 0185's rule that the alternative basis
stays on screen rather than being quietly replaced.

Both populations are reported: the blessed statistic on discretionary stems (the OPERATOR), and
panel 5's reachability on TOTAL mortality (every `isdead` stem -- what actually drives biomass).

So the discriminating quantity is (LAMBDA_REC - LAMBDA_arm) for the two arms that carry a
mortality operator, S0h (certain kills honoured) and S1 (+ the ported trait hazard's ordering).
S1 is the one that should reproduce FIT if the ported hazard's INPUTS are right -- ADR 0183 proved
the hazard is exact as a FUNCTION (recall = precision = 1.0000, mean |dhazard| 5e-18), and named
its inputs as the remaining question. This probe reads that question.

THE PRE-REGISTERED VERDICT (median over the FIT-GAIN cells, ssp370 leg, seeds averaged):
    CONFIRMED    if (LAMBDA_REC - LAMBDA_arm) >= LAMBDA_CONFIRM for BOTH S0h and S1
    REFUTED      if |LAMBDA_REC - LAMBDA_arm| <  LAMBDA_REFUTE  for BOTH S0h and S1
    INCONCLUSIVE otherwise (and say which arm sits where)

⚠ THE REACHABILITY CLAUSE (ADR 0186 section 8 -- the clause that retired a 264-job matrix for 7 s
of compute): state the mechanism by which a fix on this channel would move the deliverable, and
MEASURE THAT MECHANISM'S CURRENT SIZE FIRST. Here the mechanism is compounding: a stand that
retains a fraction (1 - m) of its mass each year, m = kill_frac_m, ends the leg with a factor
    (1 - m_arm)^Y / (1 - m_FIT)^Y
more biomass than FIT's, Y = leg length. Panel 5 computes that factor from the measured removal
rates. If it cannot reach the OBSERVED agb excess (+90 %, i.e. 1.90), then closing this channel
completely still would not close the gap and the channel is NOT the binding constraint -- exactly
the bound that made the level anchor unreachable. That is pre-registered as MECH_MIN_COMPOUND and
is reported BEFORE the verdict, because it can void it.

⚠ TRAP 5 OF THE SKILL: in a rung-2 arm THE C GROWS THE STAND -- the emulator only decides who
dies. So any stand-derived statistic is inherited by every arm including the do-nothing null, and
cannot rank arms. LAMBDA is deliberately not such a statistic (it is a property of the kill set,
which each arm chooses), but NP is scored on it and printed in the same table anyway, per the
skill's standing requirement.

================================================================================================
BASIS AND PROVENANCE
================================================================================================

THE KILL SET.  ADR 0186's next-action planned to read the harness's `rsp_r*_y*_p*.txt` kill lists;
THOSE FILES ARE GONE from the apply dirs (only `audit_r0000.txt`, `s_arm_log.txt` and
`harness.ready` remain), which the handoff flagged as a risk to check. They are not needed. Under
ADR 0123 the rung-2 binary DEFERS its demographic kills to the end of the growth loop, so the
`mort`-phase roster still carries every stem the arm killed, flagged `isdead = 1`, on a roster
IDENTICAL in length to `grow` (verified: 17 121 `grow` records and 17 121 `mort` records, of which
940 are flagged, in the c12045 S1 ssp370 s1 dump). So the kill set, and each killed stem's own
size at the moment of the decision, are both in the one phase.

THE PROVENANCE GATE (panel 1).  Every arm leg's flagged-dead count is checked per patch-year
against the harness's OWN independently written audit log, `n_kill_applied + n_forced_dead` in
`<apply>/audit_r0000.txt`. Verified on the development leg at 2025/2025 patch-years and 940 = 940
kills. This is the ADR-0186 discipline of reproducing a published basis before adding a column to
it: the audit file was written by the harness at run time and this scorer reads a different file,
so agreement is a real cross-check rather than a tautology. REC has no harness and no audit log --
its `isdead` IS FIT's own hazard outcome -- so it is gated on coverage only, and that asymmetry is
stated in the panel rather than hidden.

⚠ `agb` HERE IS THE DUMPED-POOL SUM, NOT THE C's `agb_tree.c` QUANTITY.  Per ADR 0127 the C's own
`agb` is `(leaf + heartwood + sapwood - debt + excess)*nind - turn_litt.leaf`; `excess` and
`turn_litt` are not dumped, so this uses `(leaf_c + sapwood_c + heartwood_c - debt_c) * nind`.
The two omitted terms are small and, more to the point, they enter the numerator and denominator
of LAMBDA the same way, so a level offset in them cancels. Pools are per INDIVIDUAL (skill trap 8)
and are multiplied by `nind` exactly where the runtime does. Below-ground wood is deliberately
excluded: this is an ABOVE-ground statistic, matching the quantity ADR 0186 reported the +90 % on.

HEIGHT/AGE BINS (panel 3) are fixed by the REFERENCE arm -- REC's own pooled height quintiles per
(cell, scenario) -- and then applied unchanged to every arm. Quantile bins computed per ARM would
be a different basis per arm and the profiles would not be comparable; absolute metre bins would
not travel across biomes. `age` at `grow`/`mort` is POST-increment (skill trap 6); it is reported
as dumped and labelled, since a constant offset cancels in a selection differential.

Reads `mort`-phase T records only. ~24 GB over 12 cells x 2 legs x 11 dumps; SLURM, not the login
node. Imports its cell sets, leg spans, coverage gate and completion check from the published
scorers rather than re-deriving them (ADR 0186's re-implementation trap, skill trap 5c).

    export NPREV=predict
    scripts/sbatch_python.sh S-killsel scripts/diagnose_rung2_kill_selectivity.py

Env: NPREV (default predict here -- this question only exists on the free-running axis), ROOT,
CELLS (comma list, default all 12), OUT (optional CSV).
"""

from __future__ import annotations

import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from diagnose_rung2_map_target_response import (  # noqa: E402
    LEG,
    NPATCH,
    _split_arms,
    median,
)
from diagnose_rung2_response import run_completed  # noqa: E402

ROOT = os.environ.get("ROOT", "/p/tmp/jamirp/S_rung2")
#: `predict` is the default HERE (unlike the published scorers, which default `roster` so their
#: numbers reproduce): in `roster` mode the map's count is tethered to the live stand (ADR 0184),
#: and ADR 0185 opened the free-running axis this question needs.
NPREV = os.environ.get("NPREV", "predict")
if NPREV not in ("roster", "predict"):
    raise SystemExit(f"NPREV must be roster or predict (got '{NPREV}')")

#: ADR 0177's cell sets, as used by ADR 0185/0186's criterion. FIT GAINS stems at these 5 -- the
#: discriminating subset, and the basis every published rung-2 verdict is stated on.
GAIN_CELLS = (12045, 22990, 32628, 42973, 44048)
ALL_CELLS = (12045, 12235, 18371, 22732, 22990, 32628, 42490, 42757, 42973, 44048, 52059, 57087)
CELLS = tuple(int(c) for c in os.environ["CELLS"].split(",")) if os.environ.get("CELLS") \
    else ALL_CELLS

#: every arm this scorer can READ. `ARMS` (below) is what it REPORTS.
ALL_ARMS = ("REC", "NP", "S0", "S0h", "S1", "G0", "G0h", "G1", "H0", "H0h", "H1")
#: which arms are reported. Default unchanged, so ADR 0187's published panels reproduce exactly;
#: widen it for the gross-budget campaign with `export ARMS="REC NP S0 S0h S1 G0 G0h G1"` (ADR
#: 0240), which is how the criterion's own two columns -- the DISCRETIONARY kill rate `fn` (panel 2)
#: and the annual mass removal `m_arm` (panel 5) -- are obtained for a `G*` arm.
ARMS = tuple(_split_arms(os.environ.get("ARMS", "REC NP S0 S0h S1")))
for _a in ARMS:
    if _a not in ALL_ARMS:
        raise SystemExit(f"ARMS: '{_a}' is not one of {ALL_ARMS}")
#: ⚠ `REC` is FORCED IN, whatever `ARMS` says: it is FIT's own roster, i.e. the reference every
#: statistic here is formed against AND the basis of panel 3's height quintiles. Dropping it does
#: not narrow the report, it empties it -- and one exported `ARMS` is shared with the other scorers,
#: whose default lists do not name REC because they read it from a CSV instead.
if "REC" not in ARMS:
    ARMS = ("REC", *ARMS)
#: ⚠ the arms carrying a mortality operator -- the PANEL-6 VERDICT is on these, and the pair stays
#: PINNED to ADR 0187's pre-registration even when `ARMS` is widened: LAMBDA_CONFIRM/LAMBDA_REFUTE
#: were written against S0h and S1, and a verdict recomputed over arms that did not exist when the
#: thresholds were set is not the pre-registered verdict. A `G*` arm is judged by ADR 0188 §7's
#: criterion (rate, mass removal, agb departure, roster horizon), not by this one.
OPERATOR_ARMS = ("S0h", "S1")
SCENS = ("historic", "ssp370")
BLESSED_SCEN = "ssp370"

# ── pre-registered thresholds (see the header; do not move these after a run) ──────────────────
LAMBDA_CONFIRM = 0.25      # (LAMBDA_REC - LAMBDA_arm) at or above this, for BOTH operator arms
LAMBDA_REFUTE = 0.10       # |LAMBDA_REC - LAMBDA_arm| below this, for BOTH operator arms
MIN_KILLS = 200            # below this an arm leg's LAMBDA is a ratio of small numbers -> reported,
#                            not compared. NP is expected to fall here.
MECH_MIN_COMPOUND = 1.90   # the OBSERVED agb excess (+90 %, ADR 0186). If the channel's own
#                            compounded factor cannot reach this, the channel cannot be the
#                            binding constraint and the verdict is VOID-BY-REACHABILITY.
#: S0 is uniform thinning, so it is a harness self-test with a derived answer, not a measurement.
S0_SELFTEST_TOL = 0.15

DUMP_FMT = "S_r2s_{scen}_c{cell}_{arm}_" + NPREV + "_s{seed}_dump"
APPLY_FMT = "S_r2s_{scen}_c{cell}_{arm}_" + NPREV + "_s{seed}_apply"
#: ⚠ THREE seeds for a stochastic arm, not the five that were RUN -- ADR 0187's choice, kept so its
#: panels reproduce. The `G*` arms use the same three for exactly that comparability.
SEEDS = {
    "REC": (1,), "NP": (1,),
    "S0": (1, 2, 3), "S0h": (1, 2, 3), "S1": (1, 2, 3),
    "G0": (1, 2, 3), "G0h": (1, 2, 3), "G1": (1, 2, 3),
    # the ADR-0242 RATE arms, on the same three seeds for the same comparability
    "H0": (1, 2, 3), "H0h": (1, 2, 3), "H1": (1, 2, 3),
}


class LegStats:
    """Kill-selectivity accumulators for one (cell, scen, arm, seed) leg.

    Everything is a running sum: the 24 GB never lands in memory at once.
    """

    __slots__ = ("n_all", "n_kill", "m_all", "m_kill", "h_sum", "h_sq", "hk_sum", "a_sum",
                 "a_sq", "ak_sum", "m_sq", "mk_sum", "per_year", "kills_by_py", "years",
                 "patches_term", "bin_all", "bin_kill", "nrows", "per_py")

    def __init__(self):
        self.n_all = 0
        self.n_kill = 0
        self.m_all = 0.0
        self.m_kill = 0.0
        self.h_sum = 0.0
        self.h_sq = 0.0
        self.hk_sum = 0.0
        self.a_sum = 0.0
        self.a_sq = 0.0
        self.ak_sum = 0.0
        self.m_sq = 0.0
        self.mk_sum = 0.0
        # per-year (mass present, mass killed) for the compounding panel
        self.per_year = defaultdict(lambda: [0.0, 0.0, 0, 0])
        # per-(year, patch) [mass all, n all, mass killed, n killed] -- the STRATUM of the
        # stratified LAMBDA below. The operator's draw is uniform *within* a patch-year, not
        # across them, so this is the level the derived null is exact at.
        self.per_py = defaultdict(lambda: [0.0, 0, 0.0, 0])
        self.kills_by_py = defaultdict(int)   # (year, patch) -> flagged dead, for the audit gate
        self.years = set()
        self.patches_term = set()
        self.bin_all = [0] * 5
        self.bin_kill = [0] * 5
        self.nrows = 0

    def add(self, year, patch, height, age, mass, dead, hbin):
        self.nrows += 1
        self.years.add(year)
        self.n_all += 1
        self.m_all += mass
        self.h_sum += height
        self.h_sq += height * height
        self.a_sum += age
        self.a_sq += age * age
        self.m_sq += mass * mass
        py = self.per_year[year]
        py[0] += mass
        py[2] += 1
        st = self.per_py[(year, patch)]
        st[0] += mass
        st[1] += 1
        self.bin_all[hbin] += 1
        if dead:
            self.n_kill += 1
            self.m_kill += mass
            self.hk_sum += height
            self.ak_sum += age
            self.mk_sum += mass
            py[1] += mass
            py[3] += 1
            st[2] += mass
            st[3] += 1
            self.kills_by_py[(year, patch)] += 1
            self.bin_kill[hbin] += 1

    def complete(self, scen):
        """Every year of the leg seen, and all 25 patches present at the terminal year.

        Same shape as the published scorer's `Leg.complete` -- a truncated dump looks exactly like
        a short one (skill trap 2: 92 of 510 legs are incomplete).
        """
        y0, y1 = LEG[scen]
        return self.years == set(range(y0, y1 + 1)) and len(self.patches_term) == NPATCH

    @property
    def kill_frac_n(self):
        return self.n_kill / self.n_all if self.n_all else float("nan")

    @property
    def kill_frac_m(self):
        return self.m_kill / self.m_all if self.m_all > 0 else float("nan")

    @property
    def lam_pooled(self):
        """Mass selectivity pooled over the whole leg -- REPORTED, not blessed.

        ⚠ This estimator is NOT 1.0 for a uniform operator. Pooling gives
        LAMBDA = <(1-rho)>_mass / <(1-rho)>_count over patch-years, which equals 1 only if the
        thinning ratio is uncorrelated with per-stem mass ACROSS patch-years. It is not: patches
        thinned hardest are the dense old ones. That between-stratum term is what made the S0
        self-test miss on the pooled statistic; it is a property of the estimator, not of the arm.
        """
        fn, fm = self.kill_frac_n, self.kill_frac_m
        return fm / fn if fn and fn > 0 else float("nan")

    @property
    def lam(self):
        """THE BLESSED STATISTIC: mass selectivity, STRATIFIED BY PATCH-YEAR.

        Within one patch-year the operator draws once, so mean(mass | killed)/mean(mass | present)
        has expectation EXACTLY 1 under a size-independent draw. Averaging that per-stratum ratio
        over patch-years, weighted by kills, therefore has a derived null of 1.00 for S0 with no
        between-stratum confound -- which is what makes the self-test a real gate on this scorer.
        """
        num, den = self._strata()
        return num / den if den else float("nan")

    def _strata(self):
        num = den = 0.0
        for m_all, n_all, m_kill, n_kill in self.per_py.values():
            if n_kill == 0 or n_all == 0 or m_all <= 0:
                continue
            num += n_kill * ((m_kill / n_kill) / (m_all / n_all))
            den += n_kill
        return num, den

    @property
    def lam_se(self):
        """Sampling standard error of `lam`, so the S0 self-test can be read against its own noise.

        Most strata hold ONE kill, and per-stem mass inside a patch is strongly right-skewed, so a
        single-cell LAMBDA carries a standard error of order CV/sqrt(n_kill) -- around 0.09 at 260
        kills. Reporting it is what makes S0_SELFTEST_TOL interpretable instead of arbitrary; the
        tolerance itself is NOT adjusted from what was pre-registered.
        """
        num, den = self._strata()
        if den <= 1:
            return float("nan")
        mean = num / den
        vw = sw = sw2 = 0.0
        for m_all, n_all, m_kill, n_kill in self.per_py.values():
            if n_kill == 0 or n_all == 0 or m_all <= 0:
                continue
            r = (m_kill / n_kill) / (m_all / n_all)
            vw += n_kill * (r - mean) ** 2
            sw += n_kill
            sw2 += n_kill * n_kill
        if sw <= 0 or vw <= 0:
            return float("nan")
        return math.sqrt((vw / sw) * (sw2 / (sw * sw)))

    def seldiff(self, which):
        """Standardized selection differential (mean_killed - mean_all) / sd_all."""
        if self.n_kill == 0 or self.n_all < 2:
            return float("nan")
        s, sq, ks = {
            "height": (self.h_sum, self.h_sq, self.hk_sum),
            "age": (self.a_sum, self.a_sq, self.ak_sum),
            "agb": (self.m_all, self.m_sq, self.mk_sum),
        }[which]
        mean_all = s / self.n_all
        var = sq / self.n_all - mean_all * mean_all
        if var <= 0:
            return float("nan")
        return (ks / self.n_kill - mean_all) / math.sqrt(var)

    @property
    def annual_removal(self):
        """Mean over years of (mass killed / mass present) -- the compounding rate."""
        r = [k / t for t, k, _, _ in self.per_year.values() if t > 0]
        return sum(r) / len(r) if r else float("nan")


def rec_height_edges(path):
    """REC's pooled height quintile edges for one (cell, scen) -- the COMMON bin basis.

    Bins fixed by the reference arm and then applied unchanged to every arm; per-arm quantiles
    would give each arm its own basis and the profiles would not be comparable.
    """
    hs = []
    idx = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#H T"):
                idx = {n: i for i, n in enumerate(line.split()[1:])}
                continue
            if line[0] != "T":
                continue
            f = line.split()
            if f[idx["phase"]] != "mort":
                continue
            hs.append(float(f[idx["height"]]))
    if len(hs) < 100:
        return None
    hs.sort()
    return [hs[int(q * (len(hs) - 1))] for q in (0.2, 0.4, 0.6, 0.8)]


def read_leg(path, scen, edges):
    """Accumulate one dump's `mort`-phase T records into (all stems, discretionary stems).

    `discretionary` = `mort_prob < 1`: the stems the operator actually chose over. See the header
    for why the blessed statistic is on that population and not on every `isdead` stem.
    Columns come from the file's own `#H T` header, never hardcoded (skill trap 1).
    """
    st = LegStats()
    disc = LegStats()
    y1 = LEG[scen][1]
    idx = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#H T"):
                # header "#H T phase ..." vs record "T grow ..." -> name n is field n+1 (trap 1).
                idx = {n: i for i, n in enumerate(line.split()[1:])}
                continue
            if line[0] != "T":
                continue
            if idx is None:
                raise SystemExit(f"{path}: a T record before its '#H T' header")
            f = line.split()
            if f[idx["phase"]] != "mort":
                continue
            year = int(f[idx["year"]])
            patch = int(f[idx["patch"]])
            nind = float(f[idx["nind"]])
            # per-INDIVIDUAL pools (skill trap 8) * nind, above-ground set only (ADR 0127)
            mass = nind * (
                float(f[idx["leaf_c"]]) + float(f[idx["sapwood_c"]])
                + float(f[idx["heartwood_c"]]) - float(f[idx["debt_c"]])
            )
            height = float(f[idx["height"]])
            hbin = 0
            while hbin < 4 and height > edges[hbin]:
                hbin += 1
            dead = f[idx["isdead"]] == "1"
            age = float(f[idx["age"]])
            st.add(year, patch, height, age, mass, dead, hbin)
            if float(f[idx["mort_prob"]]) < 1.0:
                disc.add(year, patch, height, age, mass, dead, hbin)
            if year == y1:
                st.patches_term.add(patch)
                disc.patches_term.add(patch)
    return st, disc


def audit_kills(path):
    """`n_kill_applied + n_forced_dead` per (year, patch) from the harness's own audit log."""
    out = {}
    idx = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#H"):
                idx = {n: i + 1 for i, n in enumerate(line.split()[2:])}
                continue
            if not line.startswith("A "):
                continue
            f = line.split()
            out[(int(f[idx["year"]]), int(f[idx["patch"]]))] = (
                int(f[idx["n_kill_applied"]]) + int(f[idx["n_forced_dead"]])
            )
    return out


def fmt(v, w=7, p=3):
    return f"{v:>{w}.{p}f}" if v == v else " " * (w - 3) + "nan"


def main() -> int:
    print("=" * 96)
    print("RUNG 2 -- WHICH TREES DIE: the mass selectivity of the kill set, arm vs FIT")
    print(f"mode NPREV={NPREV}   cells={len(CELLS)}   root={ROOT}")
    print("=" * 96)
    print(__doc__.split("PRE-REGISTRATION")[0].strip())
    print()

    legs = {}
    dlegs = {}          # the same legs restricted to discretionary stems (`mort_prob < 1`)
    excluded = []
    audit_ok = audit_bad = 0
    audit_detail = []

    for scen in SCENS:
        for cell in CELLS:
            recp = os.path.join(ROOT, DUMP_FMT.format(scen=scen, cell=cell, arm="REC", seed=1),
                                "roster_rank0000.txt")
            if not os.path.exists(recp):
                excluded.append((scen, cell, "REC", 1, "no REC dump -> no bin basis"))
                continue
            edges = rec_height_edges(recp)
            if edges is None:
                excluded.append((scen, cell, "REC", 1, "REC dump too small for quintiles"))
                continue
            for arm in ARMS:
                for seed in SEEDS[arm]:
                    tag = (scen, cell, arm, seed)
                    dp = os.path.join(ROOT, DUMP_FMT.format(scen=scen, cell=cell, arm=arm,
                                                            seed=seed), "roster_rank0000.txt")
                    if not os.path.exists(dp):
                        excluded.append((*tag, "no dump"))
                        continue
                    if arm != "REC" and not run_completed(scen, cell, arm, NPREV, seed):
                        excluded.append((*tag, "C run has no completion line"))
                        continue
                    st, disc = read_leg(dp, scen, edges)
                    if not st.complete(scen):
                        excluded.append((*tag, f"coverage: {len(st.years)} yr, "
                                               f"{len(st.patches_term)} patches at terminal"))
                        continue
                    # provenance gate: the harness's own audit log (REC has none -- see header)
                    ap = os.path.join(ROOT, APPLY_FMT.format(scen=scen, cell=cell, arm=arm,
                                                             seed=seed), "audit_r0000.txt")
                    if arm != "REC" and os.path.exists(ap):
                        exp = audit_kills(ap)
                        bad = sum(1 for k, v in exp.items() if st.kills_by_py.get(k, 0) != v)
                        if bad:
                            audit_bad += 1
                            audit_detail.append((tag, bad, len(exp)))
                            excluded.append((*tag, f"AUDIT MISMATCH in {bad}/{len(exp)} py"))
                            continue
                        audit_ok += 1
                    legs[tag] = st
                    dlegs[tag] = disc

    # ── panel 1: provenance + coverage ─────────────────────────────────────────────────────────
    print("-" * 96)
    print("PANEL 1 -- PROVENANCE AND COVERAGE GATE")
    print("-" * 96)
    # The scorer names its OWN mode and arm set: the sbatch wrappers forward a FIXED list of env
    # names and echo only that list, so an `export`ed knob shows as an EMPTY `env:` line in the job
    # log even when it did propagate (ADR 0188). Never read the mode off the wrapper.
    print(f"  mode NPREV={NPREV}   ARMS={list(ARMS)}   cells={len(CELLS)}")
    print(f"  legs scored               : {len(legs)}")
    print(f"  audit cross-check PASSED  : {audit_ok}   (flagged-dead count == "
          f"n_kill_applied + n_forced_dead, per patch-year)")
    print(f"  audit cross-check FAILED  : {audit_bad}")
    for tag, bad, tot in audit_detail[:10]:
        print(f"      {tag}: {bad}/{tot} patch-years disagree")
    print("  NOTE: REC has no harness and no audit log -- its `isdead` IS FIT's own hazard")
    print("        outcome, so it is gated on coverage only. Stated, not hidden.")
    if excluded:
        print(f"  {len(excluded)} leg(s) EXCLUDED:")
        for e in excluded[:20]:
            print(f"      {e[0]:9s} c{e[1]} {e[2]:4s} s{e[3]}: {e[4]}")
        if len(excluded) > 20:
            print(f"      ... and {len(excluded) - 20} more")
    if not legs:
        print("\n  NO VERDICT -- nothing survived the gate.")
        return 1

    def arm_mean(scen, cell, arm, fn, src=None):
        """Seed-averaged statistic for one (scen, cell, arm), or nan.

        `src` selects the population: `legs` = every stem, `dlegs` = discretionary stems only.
        """
        src = legs if src is None else src
        v = [fn(src[(scen, cell, arm, s)]) for s in SEEDS[arm] if (scen, cell, arm, s) in src]
        v = [x for x in v if x == x]
        return sum(v) / len(v) if v else float("nan")

    def med_arm(scen, cells, arm, fn, src=None):
        return median([arm_mean(scen, c, arm, fn, src) for c in cells])

    # ── panel 2: the blessed statistic ─────────────────────────────────────────────────────────
    for scen in SCENS:
        cells = [c for c in CELLS if (scen, c, "REC", 1) in legs]
        if not cells:
            continue
        print()
        print("-" * 96)
        print(f"PANEL 2 -- mass selectivity LAMBDA = kill_frac_m / kill_frac_n  [{scen}]")
        print("  LAMBDA > 1: the operator removes mass-heavy stems.  < 1: it spares them.")
        print("  LAM_strat = BLESSED: stratified by patch-year, derived null 1.00 for S0.")
        print("  LAM_pool  = the same thing POOLED over the leg -- carries a between-patch-year")
        print("              term and is NOT 1.00 for a uniform operator. Shown, not blessed.")
        print("  fn = kill_frac_n on that population.  Population: mort_prob < 1 (discretionary).")
        print("-" * 96)
        print(f"  {'cell':>6} | " + " | ".join(f"{a:>16}" for a in ARMS))
        print(f"  {'':>6} | " + " | ".join(f"{'strat  pool  fn':>16}" for _ in ARMS))
        print("  " + "-" * 88)
        gcells = [c for c in cells if c in GAIN_CELLS]
        for cell in cells:
            row = f"  {cell:>6} |"
            for arm in ARMS:
                ld = arm_mean(scen, cell, arm, lambda s: s.lam, dlegs)
                la = arm_mean(scen, cell, arm, lambda s: s.lam_pooled, dlegs)
                fn = arm_mean(scen, cell, arm, lambda s: s.kill_frac_n, dlegs)
                row += f"{fmt(ld, 6, 2)}{fmt(la, 6, 2)}{fmt(fn, 6, 3)} |"
            print(row + ("  <- FIT GAINS" if cell in GAIN_CELLS else ""))
        print("  " + "-" * 88)
        for lbl, cs in (("FIT-GAIN cells", gcells), ("all scored cells", cells)):
            if not cs:
                continue
            row = f"  {'median':>6} |"
            for arm in ARMS:
                ld = med_arm(scen, cs, arm, lambda s: s.lam, dlegs)
                la = med_arm(scen, cs, arm, lambda s: s.lam_pooled, dlegs)
                fn = med_arm(scen, cs, arm, lambda s: s.kill_frac_n, dlegs)
                row += f"{fmt(ld, 6, 2)}{fmt(la, 6, 2)}{fmt(fn, 6, 3)} |"
            print(row + f"  <- {lbl} (n={len(cs)})")
        tk = {a: sum(legs[k].n_kill for k in legs if k[0] == scen and k[2] == a) for a in ARMS}
        td = {a: sum(dlegs[k].n_kill for k in dlegs if k[0] == scen and k[2] == a) for a in ARMS}
        print("  kills scored (disc/all): "
              + "  ".join(f"{a}={td[a]}/{tk[a]}" for a in ARMS)
              + f"   (MIN_KILLS per leg = {MIN_KILLS})")
        print("  NP's disc count SHOULD be ~0 -- it nominates nothing, so a non-trivial value")
        print("  there would mean the discretionary restriction is not isolating the operator.")

    # ── panel 3: size-conditional mortality rate ───────────────────────────────────────────────
    print()
    print("-" * 96)
    print(f"PANEL 3 -- SIZE-CONDITIONAL MORTALITY RATE P(die | height bin)  [{BLESSED_SCEN}]")
    print("  bins = REC's own pooled height quintiles per cell (the reference arm fixes the basis)")
    print("  occupancy printed beside each rate: a rate on a handful of stems is not a signal")
    print("-" * 96)
    gcells = [c for c in CELLS if (BLESSED_SCEN, c, "REC", 1) in legs and c in GAIN_CELLS]
    print(f"  {'arm':>5} | " + " | ".join(f"Q{i + 1}: rate   n" for i in range(5)))
    print("  " + "-" * 88)
    for arm in ARMS:
        cells_a = [c for c in gcells if any((BLESSED_SCEN, c, arm, s) in legs for s in SEEDS[arm])]
        if not cells_a:
            continue
        row = f"  {arm:>5} |"
        for b in range(5):
            rates, occ = [], []
            for c in cells_a:
                for s in SEEDS[arm]:
                    st = dlegs.get((BLESSED_SCEN, c, arm, s))
                    if st and st.bin_all[b]:
                        rates.append(st.bin_kill[b] / st.bin_all[b])
                        occ.append(st.bin_all[b])
            r = median(rates) if rates else float("nan")
            n = int(sum(occ) / len(occ)) if occ else 0
            row += f"{fmt(r, 8, 4)} {n:>5} |"
        print(row)
    print("  Q1 = shortest quintile of FIT's stand ... Q5 = tallest")

    # ── panel 4: selection differentials ───────────────────────────────────────────────────────
    print()
    print("-" * 96)
    print(f"PANEL 4 -- STANDARDIZED SELECTION DIFFERENTIAL (mean_killed - mean_all)/sd_all"
          f"  [{BLESSED_SCEN}, FIT-GAIN cells]")
    print("  level-free and robust to the known stand divergence. DERIVED: S0 -> 0.00 (uniform).")
    print("  age is POST-increment as dumped (skill trap 6); a constant offset cancels here.")
    print("-" * 96)
    print(f"  {'arm':>5} | {'height':>9} | {'age':>9} | {'agb':>9}")
    print("  " + "-" * 44)
    for arm in ARMS:
        vals = [med_arm(BLESSED_SCEN, gcells, arm, lambda s, w=w: s.seldiff(w), dlegs)
                for w in ("height", "age", "agb")]
        print(f"  {arm:>5} | {fmt(vals[0], 9, 3)} | {fmt(vals[1], 9, 3)} | {fmt(vals[2], 9, 3)}")

    # ── panel 5: THE REACHABILITY CLAUSE (ADR 0186 section 8) ──────────────────────────────────
    print()
    print("-" * 96)
    print("PANEL 5 -- REACHABILITY: can this channel even reach the observed +90 % agb excess?")
    print("  mechanism: a stand retaining (1-m) of its mass per year ends the leg at")
    print("  (1-m_arm)^Y / (1-m_FIT)^Y times FIT's biomass.  Y = leg length, m = annual mass")
    print("  removal fraction.  MEASURED FIRST, per ADR 0186 section 8 -- it can VOID the verdict.")
    print("-" * 96)
    y0, y1 = LEG[BLESSED_SCEN]
    ylen = y1 - y0 + 1
    m_fit = median([arm_mean(BLESSED_SCEN, c, "REC", lambda s: s.annual_removal) for c in gcells])
    print(f"  leg {BLESSED_SCEN} = {ylen} yr;  FIT annual mass removal m_FIT = {m_fit:.5f}")
    print(f"  {'arm':>5} | {'m_arm':>9} | {'m_FIT-m_arm':>12} | {'compounded factor':>18}")
    print("  " + "-" * 56)
    reach = {}
    for arm in ARMS:
        m = median([arm_mean(BLESSED_SCEN, c, arm, lambda s: s.annual_removal) for c in gcells])
        if m != m and m_fit != m_fit:
            continue
        fac = ((1 - m) / (1 - m_fit)) ** ylen if 0 <= m < 1 and 0 <= m_fit < 1 else float("nan")
        reach[arm] = fac
        print(f"  {arm:>5} | {fmt(m, 9, 5)} | {fmt(m_fit - m, 12, 5)} | {fmt(fac, 18, 3)}")
    op_reach = [reach.get(a, float("nan")) for a in OPERATOR_ARMS]
    op_reach = [x for x in op_reach if x == x]
    max_reach = max(op_reach) if op_reach else float("nan")
    print()
    print(f"  max compounded factor over operator arms {OPERATOR_ARMS}:"
          f" {fmt(max_reach, 6, 3)}")
    print(f"  pre-registered MECH_MIN_COMPOUND (observed excess): {MECH_MIN_COMPOUND:.3f}")
    reachable = max_reach == max_reach and max_reach >= MECH_MIN_COMPOUND
    if reachable:
        print("  => THE CHANNEL CAN REACH IT. A fix here is capable of closing the observed gap.")
    else:
        print("  => THE CHANNEL CANNOT REACH IT ON ITS OWN. Even closing the kill-selectivity gap")
        print("     completely leaves the observed agb excess mostly unexplained -- the same")
        print("     reachability bound that retired the level anchor (ADR 0186). The panel-6")
        print("     verdict below is therefore reported as a DIAGNOSIS, not as a fix target.")

    # ── panel 6: the pre-registered verdict ────────────────────────────────────────────────────
    print()
    print("=" * 96)
    print(f"PANEL 6 -- THE PRE-REGISTERED VERDICT  [{BLESSED_SCEN}, median over FIT-GAIN cells]")
    print("=" * 96)
    print("  population: DISCRETIONARY stems (mort_prob < 1), stratified by patch-year")
    lam_rec = med_arm(BLESSED_SCEN, gcells, "REC", lambda s: s.lam, dlegs)
    print(f"  LAMBDA_REC (FIT's own mass selectivity) = {fmt(lam_rec, 6, 3)}")
    lam_s0 = med_arm(BLESSED_SCEN, gcells, "S0", lambda s: s.lam, dlegs)
    se_s0 = med_arm(BLESSED_SCEN, gcells, "S0", lambda s: s.lam_se, dlegs)
    nleg_s0 = sum(1 for c in gcells for s in SEEDS["S0"] if (BLESSED_SCEN, c, "S0", s) in dlegs)
    se_pool = se_s0 / math.sqrt(nleg_s0) if se_s0 == se_s0 and nleg_s0 else float("nan")
    ok_self = lam_s0 == lam_s0 and abs(lam_s0 - 1.0) <= S0_SELFTEST_TOL
    print(f"  S0 self-test: LAMBDA_S0 = {fmt(lam_s0, 6, 3)} vs the DERIVED 1.000 "
          f"(tol {S0_SELFTEST_TOL}) -> {'PASS' if ok_self else 'FAIL -- SUSPECT THE SCORER'}")
    print(f"    per-leg SE {fmt(se_s0, 6, 3)} over {nleg_s0} S0 legs -> SE of the pooled estimate "
          f"{fmt(se_pool, 6, 3)}")
    if se_pool == se_pool and se_pool > 0:
        print(f"    departure from 1.000 in units of that SE: "
              f"{fmt(abs(lam_s0 - 1.0) / se_pool, 6, 2)} sigma")
    print("    (the tolerance was pre-registered WITHOUT deriving this SE -- read both. A miss")
    print("     inside ~2 sigma is sampling noise; a miss far outside it is a scorer defect.)")
    print()
    gaps = {}
    for arm in OPERATOR_ARMS:
        lam = med_arm(BLESSED_SCEN, gcells, arm, lambda s: s.lam, dlegs)
        gaps[arm] = lam_rec - lam
        print(f"  {arm:>4}: LAMBDA = {fmt(lam, 6, 3)}   "
              f"LAMBDA_REC - LAMBDA = {fmt(gaps[arm], 7, 3)}")
    g = [v for v in gaps.values() if v == v]
    print()
    if len(g) < len(OPERATOR_ARMS):
        verdict = "NO VERDICT -- an operator arm has no scoreable value"
    elif all(v >= LAMBDA_CONFIRM for v in g):
        verdict = ("CONFIRMED -- the operator arms spare mass FIT removes. Kill selectivity IS a "
                   "real channel of the stand departure.")
    elif all(abs(v) < LAMBDA_REFUTE for v in g):
        verdict = ("REFUTED -- the arms' mass selectivity matches FIT's. The agb excess does NOT "
                   "come from which trees die; look at growth/recruitment next.")
    else:
        verdict = ("INCONCLUSIVE -- the arms straddle the bands; see the per-arm gaps above.")
    print(f"  thresholds: CONFIRM >= {LAMBDA_CONFIRM}   REFUTE < {LAMBDA_REFUTE} (both arms)")
    print(f"  VERDICT: {verdict}")
    if not reachable:
        print()
        print("  ⚠ VOID-BY-REACHABILITY QUALIFIER: panel 5 shows this channel cannot on its own")
        print("    reach the observed agb excess, so the verdict above describes a real property")
        print("    of the operator but must NOT be quoted as the fix that closes the deliverable.")
    if not ok_self:
        print()
        print("  ⚠ THE S0 SELF-TEST FAILED. A derived-a-priori value came out wrong, so read the")
        print("    scorer before reading the verdict.")

    out = os.environ.get("OUT")
    if out:
        with open(out, "w") as fh:
            fh.write("scen,cell,arm,seed,n_all,n_kill,m_all,m_kill,kill_frac_n,kill_frac_m,"
                     "lambda,sd_height,sd_age,sd_agb,annual_removal\n")
            for (scen, cell, arm, seed), s in sorted(legs.items()):
                fh.write(f"{scen},{cell},{arm},{seed},{s.n_all},{s.n_kill},{s.m_all:.6g},"
                         f"{s.m_kill:.6g},{s.kill_frac_n:.6g},{s.kill_frac_m:.6g},{s.lam:.6g},"
                         f"{s.seldiff('height'):.6g},{s.seldiff('age'):.6g},"
                         f"{s.seldiff('agb'):.6g},{s.annual_removal:.6g}\n")
        print(f"\n  wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
