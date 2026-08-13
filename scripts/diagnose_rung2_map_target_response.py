#!/usr/bin/env python3
"""diagnose_rung2_map_target_response.py — CLOSE THE LOOP between ADR 0181 and ADR 0177.

THE QUESTION (line S STATE section B, pre-registered)
-----------------------------------------------------
Three measured numbers did not fit together:

  * ADR 0181 — handed FIT's OWN stand, the learned count model converts a warming stand into a
  warming
    count at slope 0.994, and delivers a real (if attenuated) share of FIT's global warming
    response.
  * ADR 0182 — each rung-2 arm's OWN stand really does warm, aligned with FIT's (cosine 0.97-0.99
  where
    FIT's stand moves substantially).
  * ADR 0177 — yet the arms' realised count response is indistinguishable from a do-nothing null ON
    DIRECTION, and gets the sign wrong at 4 of the 5 cells where FIT GAINS stems.

If the map converts a warming stand faithfully, and the arm's stand warms, the arm's count should
carry a
response. This script separates the two halves of that sentence by measuring, per cell and per
arm, both:

    ASK(arm, cell) = the response of the count the MAP ASKED FOR   (`target`, i.e. DRF.predict)
    GOT(arm, cell) = the response of the count the STAND REACHED   (`n_emit`, the grown roster)

ASK and GOT differ by exactly one thing: the substitution OPERATOR that turns a count target into
a set of
dead trees. So `ASK` large with `GOT` small localises the loss in the operator; `ASK` small
localises it in
the stand/conditioning handed to the map. That is the decomposition the handoff asked for, and it
needs no
model run: the harness already recorded `target` at every rendezvous.

WHERE EVERY NUMBER COMES FROM (reference basis, stated before any number is read)
--------------------------------------------------------------------------------
`target`/`n_emit`/`rho` for the four emulator arms
    `/p/tmp/jamirp/S_rung2/S_r2s_<scen>_c<cell>_<arm>_roster_s<seed>_apply/s_arm_log.txt` —
    written BY
    `scripts/rung2_s_demography_harness.jl` AT RUNTIME. This is the arm's own prediction on its
    own stand,
    produced by the shipped `flux_feature_vector` + `DRF.predict`; nothing is recomputed here.
`target`/`n_emit` for `REC` (= LPJmL-FIT's own roster)
    `REC` is the pure-observation arm, so no harness ran and there is no log. The missing column is
    supplied by `scripts/diagnose_rung2_map_on_rec_stand.jl`, which replays the `grow` roster out
    of the
    `REC` dumps through the SAME shipped functions. Its reader is gated: at year 2000 no arm has
    yet killed
    anything, so its `target` must equal the live harness log's to the last digit -- verified
    BIT-IDENTICAL
    (6.819800183403388 at cell 12045 patch 0), which is what licenses using it as the reference.
FIT's truth, and the cell split
    `/p/tmp/jamirp/S_rung2/response_nliving.csv` (ADR 0177's own output, `n_living` at the `mort`
    phase).
    The thin/gain split is taken from THERE and not recomputed, so the reconciliation lands on
    exactly
    ADR 0177's cell sets: FIT THINS at 7 cells, GAINS at 5 ({12045, 22990, 32628, 42973, 44048}).
    This script's own `grow`-phase `n_emit` response is reported beside it as a basis cross-check.

⚠ WHICH `--n-prev` MODE IS BEING SCORED -- SET `NPREV`, AND READ THE SEPARABILITY GATE FIRST
--------------------------------------------------------------------------------------------
`NPREV` (default `roster`) selects which matrix of dumps this reads; it is in the dump names. The
two modes do not answer the same question and are not interchangeable:

  `roster`  -- `n_prev` is the LIVE stand count. ADR 0184 measured `target`/`n_emit` =
               1.00 +- 2.3 %, i.e. the map's target IS the stand's own count: ASK and GOT
               share an input and every statistic below is DEGENERATE. A persistence null
               passes the basis check at 12/12 by construction. All 767 dumps written before
               2026-08-13 are this mode.
  `predict` -- the shipped coupled recursion `n_prev[patch] = target`, in which the two decouple to
               +-24 % (+-28 % late century) and the ASK-vs-GOT question is answerable.

The SEPARABILITY GATE below (median |`target`/`n_emit` - 1| > 0.10, ADR 0184 section 10.4) is
printed before any response statistic and suppresses the verdict for any arm that fails it. Do NOT
substitute |rho-1| for it: rho sits near 1 in both modes (section 10.3).

⚠ THE `n_prev` BASIS -- A CORRECTION TO THE HANDOFF'S PRE-REGISTERED READING
---------------------------------------------------------------------------
In `roster` mode (`_arm_run1.sh:78`),
the model is handed a REAL stand count each year. That is a lagged-truth input, i.e. ADR 0181's
**CTRL**
(leaked) configuration, whose aggregate response ratio is **0.707** -- NOT its de-leaked **ABL**
arm at
0.292. The handoff pre-registered "approximately 0.292" as the comparison; on basis grounds that
is the
wrong anchor and 0.707 is the right one. Both are quoted below and neither is used as a threshold,
for the
further reason in the next paragraph.

⚠ AND THE ADR-0181 AGGREGATE IS NOT AVAILABLE ON THIS AXIS AT ALL
-----------------------------------------------------------------
0.707/0.292 are area-weighted aggregates over 51 767 cells of a ONE-STEP, C-FORCED table. Here
there are 12
FREE-RUNNING cells. Worse, ADR 0177 section 4 forbids the pooled slope as a summary on this axis
(I-squared
93-99 %: "the per-cell table is the result"), and section 5 records that the legs have different
lengths (20
vs 81 years) so a leg difference carries 61 years of drift. So the blessed statistic here is ADR
0177's
robust one -- the SIGN pattern on the discriminating subset -- and the pooled slopes are printed
with that
caveat attached. Quoting a number from this script as "the emulator delivers X of FIT's response"
is the
error ADR 0181 section 7.3 and ADR 0177 section 4 both warn about.

PRE-REGISTERED VERDICT (fixed here before the run; a threshold is not a verdict)
-------------------------------------------------------------------------------
BLESSED STATISTIC
    sign agreement against FIT on the **5 cells where FIT GAINS stems** -- the subset where every
    arm AND
    the null fail (1/5, ADR 0177 section 3), i.e. the subset that actually discriminates. Reported
    for
    `ASK` and for `GOT`, per arm, plus for `REC` as the reference.
      ASK_gain(a) = # of the 5 gain cells where ASK(a, cell) > 0
      GOT_gain(a) = # of the 5 gain cells where GOT(a, cell) > 0
BASIS CHECK -- evaluated FIRST; if it fails, NO verdict branch is printed
    ASK_gain(REC) >= 4  -- the map, handed FIT's own stand, must itself see FIT's gains. If it
    does not,
    this 12-cell axis has no power to attribute anything and the honest output is that null.
THEN, over the three learned arms S0/S0h/S1 (NP is the do-nothing null, reported never blessed):
    OPERATOR-LIMITED  : min ASK_gain >= 4 and max GOT_gain <= 2
                        (the map asks for the gain on the arm's own stand; the operator does not
                        deliver)
    CONDITIONING-LIMITED : max ASK_gain <= 2
                        (the map does not ask for the gain once the stand is the arm's own)
    otherwise         : PARTIAL -- print no branch, print what would settle it.
The verdict expression reads exactly `ask_gain_rec`, `ask_gain_arms` and `got_gain_arms` and
nothing else.

SECONDARY, REPORTED, NEVER BLESSED
    (a) the per-cell ASK/GOT/truth table -- per ADR 0177 section 4 this IS the result;
    (b) the pooled through-origin slopes, with I-squared, on ADR 0177's own definition;
    (c) the OPERATOR REACH: the fraction of patch-years with rho >= 1 (the map asks for growth,
    and the
        harness then kills nobody and overrides FIT's own hazard to spare everyone -- its own
        comment says
        so) and the fraction at the rho clamp. This is what makes the operator branch mechanistic
        rather
        than inferred: the operator is THIN-ONLY and establishment always defers to the C
        (`ESTAB_C`, so `n_recruit == 0` by construction), so a "grow" ask has no channel to add a
        stem.
    (d) the `ssp370frz` leg, which freezes ONLY the 4 boundary columns the emulator sees, giving the
        DIRECT-boundary share of the ASK (ADR 0178 as narrowed by ADR 0181 section 6 -- it is not a
        frozen-climate control for the stand, because the C still runs transient forcing).

USAGE
    export ROOT=/p/tmp/jamirp/S_rung2 RECCSV=/p/tmp/jamirp/S_rung2_maptarget/map_on_rec_stand.csv
    python3 scripts/diagnose_rung2_map_target_response.py [--csv out.csv]
Exit 0 always: a measurement, not a gate.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# ADR 0124 -- reuse ADR 0177's own completion gate rather than re-deriving it. `run_completed`
# checks the
# C run's OWN `lpjml successfully terminated` line, which is the only trustworthy signal (the job
# files
# exit 0 regardless), and `diagnose_rung2_response` is import-safe (`if __name__ == "__main__"`).
from diagnose_rung2_response import cochran_q, mean_sd, run_completed  # noqa: E402

ROOT = os.environ.get("ROOT", "/p/tmp/jamirp/S_rung2")
RECCSV = os.environ.get(
    "RECCSV", "/p/tmp/jamirp/S_rung2_maptarget/map_on_rec_stand.csv"
)
NLIVING = os.environ.get("NLIVING", os.path.join(ROOT, "response_nliving.csv"))

#: WHICH `--n-prev` MODE'S DUMPS TO SCORE. This is not cosmetic: in `roster` mode the map is handed
#: the LIVE stem count, so its target and the stand's own count are the same quantity to +-2.3 % and
#: every ASK-vs-GOT statistic below is degenerate (ADR 0184 sections 4-5). `predict` is the shipped
#: coupled recursion (`n_prev[patch] = target`), in which they decouple to +-24 % and the question
#: answerable. The default stays `roster` so ADR 0184's published numbers reproduce unchanged.
NPREV = os.environ.get("NPREV", "roster")
if NPREV not in ("roster", "predict"):
    raise SystemExit(f"NPREV must be roster or predict (got '{NPREV}')")

def _split_arms(v):
    """Split an arm list on commas OR whitespace, so one exported `ARMS` serves every scorer."""
    return [a for a in re.split(r"[,\s]+", v.strip()) if a]


#: EVERY arm name the directory layout can carry — the regex alternation only, so a `G*` leg is
#: DISCOVERABLE. Longest-first: `S0h` must precede `S0` or the alternation matches the prefix and
#: the `h` lands in the mode token. Kept separate from `ARMS` so widening what can be READ never
#: widens what is REPORTED.
ALL_ARMS = ("NP", "S0h", "S0", "S1", "G0h", "G0", "G1")
APPLY_RE = re.compile(
    r"^S_r2s_(historic|ssp370frz|ssp370)_c(\d+)_(" + "|".join(ALL_ARMS) + r")_"
    + NPREV + r"_s(\d+)_apply$"
)
#: which arms the TABLES report. Default unchanged, so every published number reproduces; widen it
#: for the gross-budget campaign with e.g. `export ARMS="NP S0 S0h S1 G0 G0h G1"` (ADR 0240).
ARMS = tuple(_split_arms(os.environ.get("ARMS", "NP S0 S0h S1")))
for _a in ARMS:
    if _a not in (*ALL_ARMS, "REC"):
        raise SystemExit(f"ARMS: '{_a}' is not one of {(*ALL_ARMS, 'REC')}")
#: `REC` is ACCEPTED in the env value and then DROPPED here: it has no `_apply` directory (it runs
#: no harness), so this scorer reads it from `RECCSV` and adds it unconditionally. One exported
#: `ARMS` is shared with `kill_selectivity`, where REC is MANDATORY — rejecting it would make the
#: two knobs incompatible, and keeping it would look for apply dirs that cannot exist.
ARMS = tuple(a for a in ARMS if a != "REC")
#: ⚠ the BLESSED statistic's arm set stays PINNED to ADR 0185's pre-registered triple even when
#: `ARMS` is widened. A verdict taken over arms that did not exist when the threshold was written is
#: not the pre-registered verdict ("a pre-registered threshold is not a pre-registered verdict"), so
#: `G*` campaign gets the descriptive tables here and is JUDGED by its own criterion (ADR 0188 §7 /
#: 0189 §7) in the kill-rate and departure scorers. Override deliberately with `LEARNED_ARMS`.
LEARNED = tuple(_split_arms(os.environ.get("LEARNED_ARMS", "S0 S0h S1")))
TERMINAL_YEAR = {"historic": 2019, "ssp370": 2100, "ssp370frz": 2100}
LEG = {"historic": (2000, 2019), "ssp370": (2020, 2100), "ssp370frz": (2020, 2100)}
NPATCH = 25
#: the six stand features of `flux_feature_vector` (its columns 5-10). The arm log names them
#: `*_rt` (the RUNTIME basis, i.e. `feats[5..10]`); the map-on-REC CSV names them plainly. The `*_c`
#: columns beside them in the arm log are the TRAINING basis and are deliberately not read here.
STAND_FEATS = ("hmean", "hmax", "agb", "lai", "fpc", "age_mean")
ARMLOG_STAND = tuple(n + "_rt" for n in ("hmean", "hmax", "agb", "lai", "fpc", "age"))
#: terminal WINDOW (a stability check on the single terminal year, which is what ADR 0177 used)
WINDOW = {"historic": (2000, 2019), "ssp370": (2081, 2100), "ssp370frz": (2081, 2100)}
#: the drift control of ADR 0182: two halves of the historic leg, same forcing, no warming excursion
DRIFT_A = (2000, 2009)
DRIFT_B = (2010, 2019)

# ── pre-registered thresholds (see the header; do not move these after a run)
# ─────────────────────────
BASIS_MIN_REC = 4          # ASK_gain(REC) must be >= this for any verdict to be printed
#: THE SEPARABILITY GATE (ADR 0184 section 10.4), reported BEFORE anything else. Median
#: |`target`/`n_emit` - 1| must exceed this or the arm's sign counts are uninterpretable: the
#: map's count state has not decoupled from the live stand. Deliberately NOT |rho-1|: rho is a
#: year-on-year ratio of two smooth tree-ensemble outputs, near 1 in BOTH modes (0.024 roster
#: -> 0.037 predict), so pre-registering on it would have killed this experiment (0184 10.3).
SEPARABILITY_MIN = 0.10
OPERATOR_ASK_MIN = 4       # min ASK_gain over the learned arms
OPERATOR_GOT_MAX = 2       # max GOT_gain over the learned arms
CONDITIONING_ASK_MAX = 2   # max ASK_gain over the learned arms


class Leg:
    """The per-(cell, arm, seed, scenario) summary of one leg."""

    __slots__ = ("target_term", "n_term", "target_win", "n_win", "npatch_term",
                 "rho_ge1", "rho_lo", "rho_hi", "nrows", "drift_a", "drift_b", "stand_term",
                 "tether", "tether_win")

    def __init__(self):
        self.target_term = []
        self.n_term = []
        self.target_win = []
        self.n_win = []
        self.npatch_term = 0
        self.rho_ge1 = 0
        self.rho_lo = 0
        self.rho_hi = 0
        self.nrows = 0
        self.drift_a = []
        self.drift_b = []
        #: the six stand features at the terminal year, summed over patches (see `stand`)
        self.stand_term = [0.0] * len(STAND_FEATS)
        #: `target`/`n_emit` per patch-year — the separability metric of ADR 0184 section 10.4, over
        #: the whole leg and over its terminal window. Empty patches (`n_emit == 0`) contribute
        #: nothing: the ratio is undefined there, and they are a real all-zero stand row, not a gap.
        self.tether = []
        self.tether_win = []

    def add(self, year, target, n_emit, rho, scen, stand=None):
        self.nrows += 1
        if stand is not None and year == TERMINAL_YEAR[scen]:
            for i, v in enumerate(stand):
                self.stand_term[i] += v
        if rho is not None:
            if rho >= 1.0:
                self.rho_ge1 += 1
            if rho <= 0.7001:
                self.rho_lo += 1
            if rho >= 1.2999:
                self.rho_hi += 1
        if year == TERMINAL_YEAR[scen]:
            self.target_term.append(target)
            self.n_term.append(n_emit)
            self.npatch_term += 1
        w0, w1 = WINDOW[scen]
        if n_emit:
            self.tether.append(target / n_emit)
            if w0 <= year <= w1:
                self.tether_win.append(target / n_emit)
        if w0 <= year <= w1:
            self.target_win.append(target)
            self.n_win.append(n_emit)
        if scen == "historic":
            if DRIFT_A[0] <= year <= DRIFT_A[1]:
                self.drift_a.append(n_emit)
            elif DRIFT_B[0] <= year <= DRIFT_B[1]:
                self.drift_b.append(n_emit)

    def complete(self, scen):
        """Every patch present at the terminal year, and the leg's full year span seen.

        The coverage gate is NOT optional: `ERROR043 duplicate roster key` killed 82 of 510
        runs and cell 22732 hangs, and a truncated log looks exactly like a short one
        (rung2-dump-analysis skill).
        """
        y0, y1 = LEG[scen]
        return self.npatch_term == NPATCH and self.nrows == (y1 - y0 + 1) * NPATCH

    @property
    def T(self):
        return sum(self.target_term) / len(self.target_term) if self.target_term else float("nan")

    @property
    def N(self):
        return sum(self.n_term) / len(self.n_term) if self.n_term else float("nan")

    @property
    def stand(self):
        """The six stand features at the terminal year, patch-mean."""
        n = self.npatch_term or 1
        return [v / n for v in self.stand_term]

    @property
    def Tw(self):
        return sum(self.target_win) / len(self.target_win) if self.target_win else float("nan")

    @property
    def Nw(self):
        return sum(self.n_win) / len(self.n_win) if self.n_win else float("nan")


def read_arm_log(path: str, scen: str) -> Leg:
    """Parse one `s_arm_log.txt`. Columns are taken from its own `#H L` header, never hardcoded."""
    leg = Leg()
    cols = {}
    with open(path) as fh:
        for line in fh:
            if line.startswith("#H L"):
                # "#H L year patch ..." -> a record is "L 2000 0 ...", so name n is field n+1.
                cols = {n: i + 1 for i, n in enumerate(line.split()[2:])}
                continue
            if not line.startswith("L "):
                continue
            if not cols:
                raise SystemExit(f"{path}: an L record before its '#H L' header")
            f = line.split()
            leg.add(
                int(f[cols["year"]]),
                float(f[cols["target"]]),
                float(f[cols["n_emit"]]),
                float(f[cols["rho"]]),
                scen,
                [float(f[cols[n]]) for n in ARMLOG_STAND],
            )
    return leg


def read_rec_csv(path: str) -> dict:
    """-> {(cell, scen): Leg} from the map-on-REC-stand CSV. `rho` does not exist for REC."""
    got = {}
    if not os.path.exists(path):
        raise SystemExit(
            f"no map-on-REC-stand CSV at {path}. Build it first:\n"
            f"  scripts/diagnose_rung2_map_on_rec_stand.jl  (see its header)"
        )
    with open(path) as fh:
        cols = None
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split(",")
            if cols is None:
                cols = {n: i for i, n in enumerate(f)}
                continue
            cell = int(f[cols["cell"]])
            scen = f[cols["scenario"]]
            key = (cell, scen)
            if key not in got:
                got[key] = Leg()
            got[key].add(
                int(f[cols["year"]]),
                float(f[cols["target"]]),
                float(f[cols["n_emit"]]),
                None,
                scen,
                [float(f[cols[n]]) for n in STAND_FEATS],
            )
    return got


def read_nliving(path: str) -> dict:
    """-> {cell: truth} from ADR 0177's own output, so the thin/gain split is not recomputed."""
    truth = {}
    if not os.path.exists(path):
        return truth
    with open(path) as fh:
        cols = None
        for line in fh:
            f = line.rstrip("\n").split(",")
            if cols is None:
                cols = {n: i for i, n in enumerate(f)}
                continue
            truth[int(f[cols["cell"]])] = float(f[cols["truth"]])
    return truth


def median(v):
    w = sorted(v)
    n = len(w)
    if n == 0:
        return float("nan")
    return w[n // 2] if n % 2 else 0.5 * (w[n // 2 - 1] + w[n // 2])


def slope_of(data):
    """ADR 0177's headline: weighted through-origin slope of response on truth, + Cochran's Q."""
    if len(data) < 2:
        return float("nan"), float("nan"), float("nan"), float("nan"), 0
    var = [max(sd * sd, 1e-9) for _, _, sd, _ in data]
    num = sum((t * r) / v for (_, r, _, t), v in zip(data, var, strict=True))
    den = sum((t * t) / v for (_, _, _, t), v in zip(data, var, strict=True))
    slope = num / den if den > 0 else float("nan")
    se = math.sqrt(1.0 / den) if den > 0 else float("nan")
    ratios = [r / t for _, r, _, t in data if t != 0]
    rvars = [max(sd * sd, 1e-9) / (t * t) for _, _, sd, t in data if t != 0]
    _q, _df, i2, _k = cochran_q(ratios, rvars)
    return slope, se, i2, *(mean_sd(ratios)[:1]), len(ratios)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="")
    a = ap.parse_args()

    # ── stage 1: read every arm log, gated
    # ────────────────────────────────────────────────────────────
    legs: dict[tuple[int, str, int, str], Leg] = {}
    excluded: list[tuple[str, str]] = []
    for name in sorted(os.listdir(ROOT)):
        m = APPLY_RE.match(name)
        if not m:
            continue
        scen, cell, arm, seed = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        if arm not in ARMS:      # discoverable but not reported — see ALL_ARMS
            continue
        path = os.path.join(ROOT, name, "s_arm_log.txt")
        if not os.path.isfile(path):
            excluded.append((name, "no s_arm_log.txt"))
            continue
        if not run_completed(scen, cell, arm, NPREV, seed):
            excluded.append((name, "no `successfully terminated` in the run log"))
            continue
        leg = read_arm_log(path, scen)
        if not leg.complete(scen):
            y0, y1 = LEG[scen]
            excluded.append(
                (name, f"incomplete: {leg.nrows} rows, {leg.npatch_term}/{NPATCH} patches at "
                       f"{TERMINAL_YEAR[scen]} (want {(y1 - y0 + 1) * NPATCH})")
            )
            continue
        legs[(cell, arm, seed, scen)] = leg

    # ── REC, the reference arm
    # ────────────────────────────────────────────────────────────────────────
    rec = read_rec_csv(RECCSV)
    for (cell, scen), leg in sorted(rec.items()):
        if leg.complete(scen):
            legs[(cell, "REC", 1, scen)] = leg
        else:
            excluded.append(
                (f"REC c{cell} {scen}", f"incomplete: {leg.nrows} rows, "
                       f"{leg.npatch_term}/{NPATCH} patches at {TERMINAL_YEAR[scen]}")
            )

    nliving = read_nliving(NLIVING)

    print("=" * 108)
    print("MAP-ON-ARM-STAND vs REALISED COUNT — closing the ADR 0181 / ADR 0177 loop")
    print("=" * 108)
    print(f"  arm logs : {ROOT}")
    print(f"  REC map  : {RECCSV}")
    if NPREV == "roster":
        print(
            "  n_prev basis: ROSTER (a real stand count) => ADR 0181 CTRL axis (0.707), NOT ABL "
            "(0.292)."
        )
        print(
            "  ⚠ ROSTER MODE IS DEGENERATE FOR ANY RESPONSE CLAIM (ADR 0184): the map gets the "
            "live"
        )
        print(
            "    stem count, so ASK and GOT share an input and their agreement is not an operator "
            "result."
        )
    else:
        print("  n_prev basis: PREDICT — the shipped coupled recursion `n_prev[patch] = target`.")
        print(
            "    The map's count state is free-running, so ASK and GOT are separable (gate below)."
        )
    print(f"\n  {len(excluded)} leg(s) EXCLUDED by the coverage/completion gate:")
    for nm, why in excluded[:12]:
        print(f"     {nm}: {why}")
    if len(excluded) > 12:
        print(f"     ... and {len(excluded) - 12} more")

    # ── stage 1b: THE SEPARABILITY GATE, reported before any response statistic
    # ────────────────────
    # ADR 0184 section 10.4 fixes this as the FIRST thing read. An arm whose map target is pinned to
    # the live stand count cannot be scored for a response no matter what its sign counts say.
    print("\n" + "=" * 108)
    print("SEPARABILITY GATE (pre-registered, ADR 0184 section 10.4) — read this BEFORE any sign "
          "count")
    print("=" * 108)
    print("  median |target/n_emit - 1| per arm and leg. It must exceed "
          f"{SEPARABILITY_MIN:.2f} or that arm's")
    print("  sign counts are uninterpretable. NOT |rho-1| (section 10.3: rho is near 1 in both "
          "modes).")
    print(f"  {'arm':>5} {'leg':>9} | {'median|t/n-1|':>14} {'median t/n':>11} "
          f"{'in[.95,1.05]':>13} {'p05-p95':>15} {'n':>7}")
    separable: dict[str, bool] = {}
    strict: dict[str, bool] = {}
    for arm in ("REC", *ARMS):
        for scen in ("historic", "ssp370"):
            pool = [
                r for (c, ar, _s, sc), leg in legs.items() if ar == arm and sc == scen
                for r in (leg.tether_win if scen == "ssp370" else leg.tether)
            ]
            if not pool:
                continue
            dev = median([abs(r - 1.0) for r in pool])
            srt = sorted(pool)
            p05 = srt[int(0.05 * (len(srt) - 1))]
            p95 = srt[int(0.95 * (len(srt) - 1))]
            near = sum(1 for r in pool if 0.95 <= r <= 1.05) / len(pool)
            flag = "" if dev > SEPARABILITY_MIN else "   <== TETHERED, not scoreable"
            print(f"  {arm:>5} {scen:>9} | {dev:14.4f} {median(pool):11.4f} {near:12.1%} "
                  f"{p05:7.3f}-{p95:7.3f} {len(pool):7d}{flag}")
            if scen == "ssp370":
                separable[arm] = dev > SEPARABILITY_MIN
            else:
                strict[arm] = dev > SEPARABILITY_MIN
    print("  (the ssp370 row is the terminal 2081-2100 window; historic is its whole leg)")
    # WHICH LEG THE VERDICT KEYS ON, and why — a reading fixed by derivation, not by which leg
    # happened to pass. The blessed statistic is a DIFFERENCE of leg means, and what has to be
    # separable is ASK-vs-GOT *within that difference*:
    #     Resp(ASK) - Resp(GOT) = (ASK_ssp - GOT_ssp) - (ASK_hist - GOT_hist)
    # A tethered BASELINE leg makes the second bracket ~0, which DELETES a term from the contrast
    # rather than collapsing it; the contrast is then carried entirely by the ssp370 leg. Degeneracy
    # needs BOTH legs tethered — which is exactly the `roster` case this gate is built to refuse.
    # The strict per-leg reading is printed beside it so the weaker leg is never hidden.
    print(
        "\n  VERDICT KEYS ON THE ssp370 LEG. The blessed statistic is a difference of leg means, "
        "so a\n  tethered BASELINE leg removes the term (ASK_hist - GOT_hist) from the ASK-vs-GOT "
        "contrast\n  rather than collapsing it; degeneracy needs BOTH legs tethered (the `roster` "
        "case)."
    )
    strict_fail = [a for a in ("REC", *ARMS) if a in strict and not strict[a]]
    if strict_fail:
        print(
            f"  ⚠ UNDER THE STRICT PER-LEG READING OF THE PRE-REGISTRATION the historic leg FAILS "
            f"for {strict_fail},\n    and there would be NO VERDICT. That reading is not used, for "
            f"the reason above; it is\n    reported because the choice was made AFTER seeing the "
            f"numbers. The historic leg is 20 years\n    against ssp370's 81, so the recursion has "
            f"a quarter of the time to leave its `n_emit` seed."
        )

    # ── stage 2: per-cell ASK / GOT, seed-paired
    # ──────────────────────────────────────────────────────
    cells = sorted({c for (c, _, _, _) in legs})

    def resp(cell, arm, field, scen_s="ssp370"):
        """Seed-paired response (ssp370 leg - historic leg) of `field`; -> (mean, sd, nseed)."""
        def pick(sc_want):
            return {
                s: v for (c, ar, s, sc), v in legs.items()
                if c == cell and ar == arm and sc == sc_want
            }

        hs = pick("historic")
        ss = pick(scen_s)
        common = sorted(set(hs) & set(ss))
        vals = [getattr(ss[s], field) - getattr(hs[s], field) for s in common]
        if not vals:
            return float("nan"), float("nan"), 0
        m, sd = mean_sd(vals)
        return m, sd, len(common)

    scoreable = [
        c for c in cells
        if resp(c, "REC", "N")[2] > 0 and any(resp(c, ar, "N")[2] > 0 for ar in ARMS)
    ]

    # THE CELL SPLIT comes from ADR 0177's own output, not from this script (see the header).
    thin = [c for c in scoreable if nliving.get(c, 0.0) < 0]
    gain = [c for c in scoreable if nliving.get(c, 0.0) > 0]
    print(f"\n  {len(scoreable)} scoreable cell(s). FIT THINS at {len(thin)}: {thin}")
    print(f"                          FIT GAINS at {len(gain)}: {gain}")
    missing = [c for c in scoreable if c not in nliving]
    if missing:
        print(
            f"  ⚠ {len(missing)} cell(s) absent from {NLIVING}, excluded from the "
            f"split: {missing}"
        )

    # basis cross-check: this script's `grow`-phase n_emit response vs ADR 0177's `mort`-phase
    # n_living
    print("\n-- BASIS CROSS-CHECK: FIT's own count response, two phases, same cells")
    print(
        "   (they are different quantities -- `grow` is pre-thinning, `mort` post-hazard -- so "
        "this is"
    )
    print("    a sign/scale agreement check, not an identity)")
    agree = 0
    for c in scoreable:
        mine, _, _ = resp(c, "REC", "N")
        theirs = nliving.get(c, float("nan"))
        ok = (mine * theirs > 0) if theirs == theirs else False
        agree += ok
        print(f"   cell {c:>6}  grow/n_emit {mine:+8.3f}   mort/n_living {theirs:+8.3f}   "
              f"{'sign OK' if ok else 'SIGN DIFFERS'}")
    print(f"   sign agreement {agree}/{len(scoreable)}")

    # ── stage 3: the per-cell table — ADR 0177 section 4: THIS is the result
    # ───────────────────────────
    print("\n" + "=" * 108)
    print(
        "PER-CELL: ASK = response of the count the MAP ASKED FOR   GOT = response of the count "
        "REACHED"
    )
    print("=" * 108)
    hdr = f"  {'cell':>6} {'FIT':>8} |"
    for arm in ("REC", *ARMS):
        hdr += f" {arm + ':ASK':>10} {arm + ':GOT':>10} |"
    print(hdr)
    csv_rows = ["cell,group,fit_truth,arm,ask,ask_sd,got,got_sd,nseed"]
    for c in scoreable:
        grp = "gain" if c in gain else ("thin" if c in thin else "?")
        line = f"  {c:>6} {nliving.get(c, float('nan')):+8.3f} |"
        for arm in ("REC", *ARMS):
            ask, asd, ns = resp(c, arm, "T")
            got, gsd, _ = resp(c, arm, "N")
            line += f" {ask:+10.3f} {got:+10.3f} |"
            if ns:
                csv_rows.append(
                    f"{c},{grp},{nliving.get(c, float('nan'))},{arm},{ask},{asd},{got},{gsd},{ns}"
                )
        print(line)

    # ── stage 4: THE BLESSED STATISTIC — sign agreement on the FIT-GAIN cells
    # ─────────────────────────
    print("\n" + "=" * 108)
    print(
        "BLESSED: sign agreement vs FIT, on the 5 cells where FIT GAINS stems (the discriminating "
        "set)"
    )
    print("=" * 108)
    print(f"  {'arm':>5} | {'ASK gain':>9} {'GOT gain':>9} | {'ASK thin':>9} {'GOT thin':>9} |"
          f" {'ASK all':>8} {'GOT all':>8}")
    sign = {}
    for arm in ("REC", *ARMS):
        row = {}
        for grp, cs in (("gain", gain), ("thin", thin), ("all", scoreable)):
            na = sum(1 for c in cs if resp(c, arm, "T")[0] * nliving.get(c, 0.0) > 0)
            ng = sum(1 for c in cs if resp(c, arm, "N")[0] * nliving.get(c, 0.0) > 0)
            row[grp] = (na, ng, len(cs))
        sign[arm] = row
        print(f"  {arm:>5} | {row['gain'][0]:>4}/{row['gain'][2]:<4} {row['gain'][1]:>4}/"
              f"{row['gain'][2]:<4} | {row['thin'][0]:>4}/{row['thin'][2]:<4} "
              f"{row['thin'][1]:>4}/{row['thin'][2]:<4} | {row['all'][0]:>3}/{row['all'][2]:<4} "
              f"{row['all'][1]:>3}/{row['all'][2]:<4}")

    # ── stage 5: OPERATOR REACH — what the operator can even do with the ask
    # ──────────────────────────
    print("\n" + "=" * 108)
    print(
        "OPERATOR REACH: the harness is THIN-ONLY. rho >= 1 => it kills nobody AND overrides FIT's "
        "own"
    )
    print("hazard to spare everyone; establishment defers to the C (ESTAB_C, n_recruit == 0).")
    print("So a 'grow' ask has NO channel to add a stem. Fractions of patch-years:")
    print("=" * 108)
    print(
        f"  {'arm':>5} {'scen':>10} {'cells':>6} | {'rho>=1':>8} {'rho<=0.70':>10} "
        f"{'rho>=1.30':>10}"
    )
    for arm in ARMS:
        for scen in ("historic", "ssp370", "ssp370frz"):
            for _grp, cs, lbl in (("gain", gain, "GAIN"), ("thin", thin, "THIN")):
                tot = ge1 = lo = hi = 0
                for c in cs:
                    for (cc, ar, _s, sc), leg in legs.items():
                        if cc == c and ar == arm and sc == scen:
                            tot += leg.nrows
                            ge1 += leg.rho_ge1
                            lo += leg.rho_lo
                            hi += leg.rho_hi
                if tot:
                    print(f"  {arm:>5} {scen:>10} {lbl:>6} | {100 * ge1 / tot:7.1f}% "
                          f"{100 * lo / tot:9.1f}% {100 * hi / tot:9.1f}%")


    # ── stage 5b: WHY the conditioning differs — the arm's stand LEVEL vs FIT's ──────────────
    print("\n" + "=" * 108)
    print("STAND-LEVEL DEPARTURE — the mechanism behind a conditioning-limited verdict.")
    print("ADR 0182 measured the arm's stand SHIFT (a z-score, aligned with FIT's). The map,")
    print("though, is a nonlinear function of the stand's LEVEL, so an arm whose stand has")
    print("drifted to a different level is evaluated somewhere FIT's stand never goes -- and")
    print("the response it reads off there need not even share a sign. That is the LEVEL/SHIFT")
    print("distinction, and it is")
    print("the ADR-0127 `keep`-ratio trap in a new place: a correct ratio over a wrong level.")
    print("Median over cells of (arm - REC) / |REC|, at the terminal year of each leg:")
    print("=" * 108)
    for cs, lbl in ((gain, "FIT-GAIN"), (thin, "FIT-THIN")):
        print(f"\n  -- {lbl} cells ({len(cs)})")
        head = f"  {'arm':>5} {'leg':>9} | {'n_emit':>9} |"
        for nm in STAND_FEATS:
            head += f" {nm:>8}"
        print(head)
        for arm in ARMS:
            for scen in ("historic", "ssp370"):
                dn, df = [], [[] for _ in STAND_FEATS]
                for c in cs:
                    r = [v for (cc, ar, _s, sc), v in legs.items()
                         if cc == c and ar == "REC" and sc == scen]
                    aa = [v for (cc, ar, _s, sc), v in legs.items()
                          if cc == c and ar == arm and sc == scen]
                    if not r or not aa:
                        continue
                    rn = r[0].N
                    an = sum(x.N for x in aa) / len(aa)
                    if rn:
                        dn.append((an - rn) / abs(rn))
                    rs, as_ = r[0].stand, [
                        sum(x.stand[i] for x in aa) / len(aa) for i in range(len(STAND_FEATS))
                    ]
                    for i in range(len(STAND_FEATS)):
                        if rs[i]:
                            df[i].append((as_[i] - rs[i]) / abs(rs[i]))
                if not dn:
                    continue
                line = f"  {arm:>5} {scen:>9} | {median(dn):+8.1%} |"
                for i in range(len(STAND_FEATS)):
                    line += f" {median(df[i]):+7.1%}" if df[i] else f" {'--':>7}"
                print(line)

    # ── stage 6: pooled slopes, WITH the ADR 0177 caveat
    # ─────────────────────────────────────────────
    print("\n" + "=" * 108)
    print(
        "POOLED SLOPES — reported, NEVER a summary. ADR 0177 section 4: I-squared 93-99 % on this "
        "axis,"
    )
    print("so there is no common effect to estimate and the per-cell table above IS the result.")
    print("=" * 108)
    print(f"  {'arm':>5} | {'ASK slope':>18} {'I2':>6} | {'GOT slope':>18} {'I2':>6}")
    for arm in ("REC", *ARMS):
        dat_a, dat_g = [], []
        for c in scoreable:
            t = nliving.get(c, float("nan"))
            if t != t or t == 0:
                continue
            ask, asd, ns = resp(c, arm, "T")
            got, gsd, _ = resp(c, arm, "N")
            if ns:
                dat_a.append((c, ask, asd, t))
                dat_g.append((c, got, gsd, t))
        sa, sea, i2a, _, _ = slope_of(dat_a)
        sg, seg, i2g, _, _ = slope_of(dat_g)
        print(f"  {arm:>5} | {sa:9.3f} +- {sea:6.3f} {i2a:5.1f}% | "
              f"{sg:9.3f} +- {seg:6.3f} {i2g:5.1f}%")

    # ── stage 7: the drift control, and the frozen-boundary leg
    # ──────────────────────────────────────
    print("\n" + "=" * 108)
    print("CONTROLS")
    print("=" * 108)
    print(
        "  (a) DRIFT (ADR 0182's declared control): the same statistic between the two HALVES of "
        "the"
    )
    print(
        "      historic leg, where both FIT and the arm run under the same forcing. Reported as a "
        "rate"
    )
    print(
        "      per decade beside the warming rate over 8.1 decades. A drift rate of the same size "
        "means"
    )
    print("      the leg difference is not a response to the forcing (ADR 0177 section 5).")
    print(f"      {'arm':>5} {'drift/decade':>14} {'warming/decade':>16}  (n_emit, gain)")
    for arm in ("REC", *ARMS):
        dr, wr, n = [], [], 0
        for c in gain:
            for (cc, ar, _s, sc), leg in legs.items():
                if cc == c and ar == arm and sc == "historic" and leg.drift_a and leg.drift_b:
                    dr.append(
                        sum(leg.drift_b) / len(leg.drift_b) - sum(leg.drift_a) / len(leg.drift_a)
                    )
                    n += 1
            m, _, ns = resp(c, arm, "N")
            if ns:
                wr.append(m / 8.1)
        if dr and wr:
            print(f"      {arm:>5} {sum(dr) / len(dr):+14.4f} {sum(wr) / len(wr):+16.4f}")
    print(
        "\n  (b) FROZEN BOUNDARY (`ssp370frz`) — freezes ONLY the 4 boundary columns the emulator "
        "sees,"
    )
    print("      so it is the DIRECT-boundary share of the ASK, not a frozen-climate")
    print("      control for the stand (the C still runs transient forcing; ADR 0181")
    print("      section 6 narrowing ADR 0178).")
    print(
        f"      {'arm':>5} {'ASK direct':>12} {'ASK total':>12} {'direct share':>13}  (FIT-gain "
        f"cells)"
    )
    for arm in ARMS:
        tot, direct = [], []
        for c in gain:
            at, _, n1 = resp(c, arm, "T", "ssp370")
            af, _, n2 = resp(c, arm, "T", "ssp370frz")
            if n1 and n2:
                tot.append(at)
                direct.append(at - af)
        if tot:
            mt = sum(tot) / len(tot)
            md = sum(direct) / len(direct)
            sh = md / mt if mt != 0 else float("nan")
            print(f"      {arm:>5} {md:+12.4f} {mt:+12.4f} {sh:+13.3f}")

    # ── stage 8: the verdict, keyed ONLY on the blessed statistic
    # ────────────────────────────────────
    ask_gain_rec = sign["REC"]["gain"][0]
    ask_gain_arms = [sign[a]["gain"][0] for a in LEARNED if a in sign]
    got_gain_arms = [sign[a]["gain"][1] for a in LEARNED if a in sign]
    ngain = len(gain)

    print("\n" + "=" * 108)
    print("PRE-REGISTERED VERDICT")
    print("=" * 108)
    print(f"  blessed inputs: ask_gain_rec={ask_gain_rec}/{ngain}  "
          f"ask_gain_arms={ask_gain_arms}  got_gain_arms={got_gain_arms}   (S0, S0h, S1)")
    print("  separability : " + "  ".join(
        f"{a}={'PASS' if separable.get(a) else 'TETHERED'}" for a in ("REC", *ARMS)
    ))
    print(
        "  ⚠ REC's ask_gain is the PERSISTENCE NULL's value, not skill, whenever REC is TETHERED: "
        "with target == n_prev == the live count it reproduces FIT's direction by construction."
    )
    tethered = [a for a in LEARNED if a in sign and not separable.get(a)]
    if not ask_gain_arms:
        print("  NO VERDICT — no learned arm survived the coverage gate.")
    elif tethered:
        print(f"  NO VERDICT — the separability gate FAILED for {tethered}.")
        print("     Their map target has not decoupled from the live stand count, so ASK and GOT")
        print("     share an input and the sign counts above are an artifact of that sharing, not")
        print("     an operator result (ADR 0184 sections 4-5). Re-run those arms with")
        print("     `--n-prev=predict` before reading any branch.")
    elif ask_gain_rec < BASIS_MIN_REC:
        print(f"  BASIS CHECK FAILED: ask_gain_rec={ask_gain_rec} < {BASIS_MIN_REC}.")
        print("  ⇒ NO VERDICT BRANCH IS PRINTED. The map, handed FIT'S OWN stand, does")
        print("     not itself see")
        print(
            "     FIT's gains at these cells, so this 12-cell axis cannot attribute the arms' "
            "failure"
        )
        print("     to either the operator or the conditioning. That is the finding.")
        print(
            "     What would settle it: the gain cells are a 5-cell subset of a 12-cell set chosen "
            "for"
        )
        print("     biome spread, not for response power. Either (i) score the ASK on the GLOBAL")
        print(
            "     one-step-forced table where ADR 0181 already has 51 767 cells and the gain/thin "
            "split"
        )
        print(
            "     is resolvable, or (ii) enlarge the rung-2 cell set toward the cells that carry "
            "FIT's"
        )
        print("     area-weighted gain, which needs the ERROR043 duplicate-key fault fixed first.")
    elif min(ask_gain_arms) >= OPERATOR_ASK_MIN and max(got_gain_arms) <= OPERATOR_GOT_MAX:
        print("  ⇒ OPERATOR-LIMITED. The map asks for FIT's gain on the arm's OWN stand, and the")
        print(
            "     substitution operator does not deliver it. The operator is thin-only (stage 5), "
            "so"
        )
        print("     this is mechanistic, not inferential: the work is the operator, not the map.")
    elif max(ask_gain_arms) <= CONDITIONING_ASK_MAX:
        print(
            "  ⇒ CONDITIONING-LIMITED. Handed the arm's own stand the map stops asking for the "
            "gain,"
        )
        print(
            "     even though it asks for it on FIT's stand. The work is the stand handed to the "
            "map."
        )
    else:
        print(
            "  ⇒ PARTIAL — no branch. The blessed counts fall between the pre-registered "
            "thresholds."
        )
        print(f"     What would settle it: ASK_gain >= {OPERATOR_ASK_MIN} at every arm with")
        print(f"     GOT_gain <= {OPERATOR_GOT_MAX} would be operator-limited; ASK_gain <= "
              f"{CONDITIONING_ASK_MAX} would be conditioning-limited.")

    if a.csv:
        with open(a.csv, "w") as fh:
            fh.write("\n".join(csv_rows) + "\n")
        print(f"\nwrote {len(csv_rows) - 1} rows -> {a.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
