#!/usr/bin/env python
"""
diagnose_rung2_gross_budget_lag — CAN A LAGGED RECRUIT COUNT CARRY THE GROSS MORTALITY BUDGET?
The one derivation ADR 0188 section 7 requires BEFORE the instrument is built, answered from state
already on disk. No model run.

ADR 0188 established the mechanism behind ADR 0187's 3.5-4.2x mortality-rate shortfall: the
operator's budget is the NET count change (`(1-rho)*n_now`, measured 0.78-1.02 %/yr) while the
mortality flux that moves biomass is the GROSS (FIT 5.65-5.96 %/yr), because FIT replaces
4.6-6.5 %/yr of its roster by recruitment and establishment is deferred to the C (`ESTAB_C`), so
recruitment is already netted out of any next-year count target. Its section 7 pre-registered the
instrument -- budget `(n_now - target) + Rhat` instead of `(n_now - target)` -- and flagged the one
thing that can kill it:

    Rhat for the CURRENT year is NOT available at the rendezvous. The rendezvous is at the `grow`
    phase; establishment happens after `post`. So the instrument must use a LAGGED or PREDICTED
    Rhat, and "derive whether a lagged Rhat still moves the blessed statistic before writing the
    arm" (ADR 0188 section 7). If a one-year lag destroys the signal, the instrument needs the C to
    expose its own establishment count at the rendezvous -- an INTEGRATION POINT with line M's
    `rung2_apply.c`, not an S-only change.

    THE REFERENCE BASIS. FIT's OWN stand: the 24 `REC` `predict` dumps (`grow`/`mort`/`post`
    phases, ADR 0188's count identity) joined to `map_on_rec_stand_predict.csv`, which is the
    learned count model's own `target` on that same roster (`diagnose_rung2_map_on_rec_stand.jl`,
    ADR 0185). That pairing is what makes the capacity number like-for-like against FIT's own
    discretionary kill rate. Panel E repeats it on `S1`'s OWN stand off its arm logs, because the
    arms' stands have diverged (+90 % agb) and a REC-stand-only conclusion could be an artifact.
    Counts, not densities: every tree carries `nind = 1/patch_area` in `individual` mode, so
    `(1-rho)*n_now` in density equals `(1-rho)*n_tree` in stems EXACTLY -- gated in panel A.

-- WHAT IS DERIVED A PRIORI, WRITTEN DOWN BEFORE THE READ (ADR 0184's clause) --------------------

D1  THE OBSERVABLE. `age` at `grow` is POST-increment (skill trap 6) and establishment sets age 0,
    so a stem with `age == 1` at the rendezvous of year y established at the `post` phase of y-1:
        #{age == 1 at grow, year y}  ==  R(y-1)  ==  n_post(y-1) - n_grow(y-1)
    exactly, per patch. MUST BE 100 %. This is the whole reason a lagged Rhat needs no interface
    change: the harness already receives the full roster, so it can count the previous year's
    recruit cohort itself. A failure here promotes the question to an integration point with M.

D2  THE COUNT IS NOT PUT AT RISK BY THE LAG, and the argument is algebraic. With
    `K = (n_now - target) + Rhat` the realized count is
        n_next = n_now - K + R = target + (R - Rhat)
    so the count still lands on `target` whenever Rhat is right, and with Rhat = R(y-1) the
    departure over a leg TELESCOPES:  sum_y (R_y - R_{y-1}) = R_last - R_first,  i.e. BOUNDED by one
    year's recruitment however long the leg. That is the derived claim panel C measures against.
    (The current operator is the Rhat = 0 case, whose departure sum is `sum_y R_y` -- 375-520 % of
    the roster over 81 years -- which is why the count only stays near target through the C's own
    non-negotiable kills, not through the operator.)

D3  THE PANEL'S ANCHORS. The capacity statistic is
        D(Rhat) = mean_over_patch-years[ max(0, max(0, (1-rho)*n_tree + Rhat) - n_cert) ] / n_tree
    the discretionary kills the operator could still afford AFTER honouring the certain deaths
    (`f = 0` for `mort_prob >= 1`, harness :539, so they are spent out of the same budget).
      * `Rhat = 0` is the CURRENT operator and MUST reproduce ADR 0187's measured discretionary
        rate, 0.5-0.6 %/yr. Pre-registered acceptance band 0.3-0.9 %/yr. -> PASSED.
      * ⚠ A SECOND BAND WAS PRE-REGISTERED FOR THE ORACLE AND IS MIS-DERIVED. It said `Rhat = R(y)`
        must land in [1.5, 2.6] %/yr near FIT's own K_disc, from `n_now - target ~ K_all - R` =>
        `B ~ K_all` => `D ~ K_all - K_cert = K_disc`. Every step of that is a statement about
        MEANS, while `max(0, b - n_cert)` is CONVEX -- so the leg mean exceeds the difference of
        means by a Jensen gap that grows with the count model's per-patch-year error. Measured, the
        budget mean does land on FIT's gross kills (5.894 vs 5.858 %/yr, 2 cells) while D comes out
        at 4.5 %/yr, and the band "failed" for a reason that is a property of the instrument, not a
        defect of the panel. A DERIVED ANCHOR MUST BE DERIVED THROUGH THE SAME NONLINEARITY AS THE
        STATISTIC. The band is kept in the code as `ANCHOR_ORACLE_MISDERIVED`, printed, and NOT
        used as a gate; the correction below was made before any verdict was read.
      * THE CORRECTED DERIVABLE ARM is `perfect`: set `b = K_all` per patch-year (a perfect count
        target, so the count model's error is removed rather than averaged over). Then
        `max(0, K_all - n_cert) == K_disc` IDENTICALLY per patch-year, so this arm must reproduce
        FIT's own discretionary rate to rounding -- an exact identity, not a band. For the oracle
        and every lagged variant no a-priori value exists; the `perfect`-to-`oracle` gap IS the
        count model's rectified per-patch-year error, and is read as a result.
    A panel that misses `none` or `perfect` is not to be read for the lag question -- that is a
    basis error (skill traps 5f/5c: derive the arm whose answer is known, and never move a
    tolerance after the read -- disclose a mis-derivation instead, as done here).

-- THE PRE-REGISTERED VERDICT BRANCHES (thresholds from ADR 0188 section 7, not moved) -----------
    (i)  D1 exact AND D(lag1) >= 1.5 %/yr  -> THE INSTRUMENT SURVIVES THE LAG. Write the arm; the
         0188 section 7 criterion (kill rate >= 1.5 %/yr, mass removal >= 0.025, agb < +40 %)
         stands unchanged as the arm's own gate.
    (ii) D(oracle) >= 1.5 but D(lag1) < 1.5 -> THE LAG IS WHAT COSTS IT. Raise the integration
         point with line M (expose the C's establishment count at the rendezvous).
    (iii) D(oracle) < 1.5 -> THE GROSS BUDGET ITSELF IS INSUFFICIENT; ADR 0188 section 7's lever is
         smaller than derived. Report and stop -- do not write the arm.
    CAPACITY IS NECESSARY, NOT SUFFICIENT. This scorer measures what the operator could afford to
    spend, not what it would realize: the draw is stochastic and the tilt solver may still refuse.
    Say "capacity", never "rate", when quoting it.

Usage
    export NPREV=predict
    /home/jamirp/.conda/envs/py311_new/bin/python scripts/diagnose_rung2_gross_budget_lag.py
    # CELLS=12045,42490 restricts the scan (smoke test); SKIP_ARM=1 drops panel E;
    # ARM_SEED=<n> picks panel E's S1 seed (default 1).
"""

from __future__ import annotations

import glob
import math
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ADR 0186's rule: import the definitions, do not re-implement them (skill trap 5c). `scan_rec_dump`
# carries ADR 0188's gated count identity and now also the two columns this derivation needs.
from diagnose_rung2_kill_budget import (  # noqa: E402
    RHO_HI,
    RHO_LO,
    mean,
    median,
    scan_rec_dump,
    sd,
    se,
)
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
#: ADR 0188 section 7's pre-registered discretionary-kill-rate threshold, in %/yr.
CRIT_RATE = 1.5
#: the two derived anchors of D3, as (lo, hi) in %/yr. Fixed before the run.
ANCHOR_CURRENT = (0.3, 0.9)
#: D3's FIRST oracle band, MIS-DERIVED (linear identity against a convex statistic) and retained
#: only so the record shows what was written before the run and why it was replaced. See the header.
ANCHOR_ORACLE_MISDERIVED = (1.5, 2.6)
#: the corrected derivable anchor's tolerance, in percentage points: with `b = K_all` per patch-year
#: `max(0, K_all - n_cert)` IS `K_disc` identically, so the `perfect` arm must reproduce FIT's own
#: discretionary rate to rounding. Any excess is stems certain at `grow` yet not flagged at `mort`.
ANCHOR_PERFECT_TOL = 0.02
#: the Rhat variants. `lag1` is the OPERATIONAL one -- `n_age1`, what the harness can see itself.
VARIANTS = ("none", "lag1", "mean5", "expand", "oracle")
#: budget columns = the Rhat variants plus `perfect`, which is not an Rhat at all but the
#: PERFECT-TARGET oracle `b = K_all`: it isolates the panel's own arithmetic from the count model's
#: per-patch-year error, and its answer is known exactly in advance.
BUDGETS = VARIANTS + ("perfect", "lag1_sm5", "oracle_sm5", "lag1_acct", "oracle_acct")

REC_RE = re.compile(r"^S_r2s_(historic|ssp370)_c(\d+)_REC_" + NPREV + r"_s(\d+)_dump$")
ARM_RE = re.compile(r"^S_r2s_(historic|ssp370)_c(\d+)_(S0|S0h|S1)_" + NPREV + r"_s(\d+)_dump$")


#: panel E scans one seed by default -- S1's dumps are ~48 MB each and the panel is a check that
#: the FIT-stand conclusion is not an artifact, not a seed-averaged number. Override with ARM_SEED.
ARM_SEED = int(os.environ.get("ARM_SEED", "1"))


def only_cells():
    v = os.environ.get("CELLS", "").strip()
    return {int(x) for x in v.split(",") if x} if v else None


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = mean(xs), mean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else float("nan")


def rmse(xs, ys):
    n = len(xs)
    if n == 0:
        return float("nan")
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(xs, ys, strict=True)) / n)


# ── the per-patch-year table this whole derivation runs on ────────────────────────────────────────

class Row:
    """One patch-year of FIT's own stand (or an arm's), with every Rhat variant attached.

    `rhat` holds the recruit estimate each variant would have had AT THE RENDEZVOUS:
      none    0.0            -- the current operator
      lag1    n_age1(y)      -- last year's recruit cohort, counted off the roster in hand (D1)
      mean5   mean of n_age1 over the last <=5 rendezvous of this patch
      expand  mean of n_age1 over every previous rendezvous of this patch
      oracle  R(y)           -- THIS year's recruits; NOT available at decision time, the bound
    """

    __slots__ = ("year", "patch", "n_tree", "n_cert", "k_all", "k_disc", "r_true", "rho", "rhat")

    def __init__(self, year, patch, n_tree, n_cert, k_all, k_disc, r_true):
        self.year = year
        self.patch = patch
        self.n_tree = n_tree
        self.n_cert = n_cert
        self.k_all = k_all
        self.k_disc = k_disc
        self.r_true = r_true
        self.rho = float("nan")
        self.rhat = {}


def build_rows(per_year):
    """-> {patch: [Row, ...]} in year order, with the lag/running Rhat variants filled in.

    The running means are formed from `n_age1`, i.e. from realized past recruitment as the harness
    would have observed it -- never from `r_true`, which is the quantity being predicted.
    """
    by_patch = defaultdict(list)
    for (year, patch), v in sorted(per_year.items()):
        ng, ka, kd, rr, _ok, _fire, ncert, nage1 = v
        row = Row(year, patch, ng, ncert, ka, kd, rr)
        row.rhat["none"] = 0.0
        row.rhat["lag1"] = float(nage1)
        row.rhat["oracle"] = float(rr)
        by_patch[patch].append(row)
    for rows in by_patch.values():
        hist = []
        for r in rows:
            r.rhat["mean5"] = mean(hist[-5:]) if hist else r.rhat["lag1"]
            r.rhat["expand"] = mean(hist) if hist else r.rhat["lag1"]
            hist.append(r.rhat["lag1"])
    return by_patch


def read_map_csv(path):
    """-> {(cell, scen, seed, year, patch): (n_tree, n_prev, target)} from the REC-stand replay."""
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
                float(f[cols["n_tree"]]), float(f[cols["n_prev"]]), float(f[cols["target"]])
            )
    return out


def read_arm_rho(path):
    """-> {(year, patch): (n_tree, rho)} off one `s_arm_log.txt` (its own `#H L` header, trap 1)."""
    out = {}
    cols = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#H L"):
                cols = {n: i + 1 for i, n in enumerate(line.split()[2:])}
                continue
            if not line.startswith("L ") or cols is None:
                continue
            f = line.split()
            out[(int(f[cols["year"]]), int(f[cols["patch"]]))] = (
                float(f[cols["n_tree"]]), float(f[cols["rho"]])
            )
    return out


def collect(regex, want_arm=None):
    """-> {(cell, scen, arm, seed): {patch: [Row]}}, plus the named exclusions (skill trap 2)."""
    keep = only_cells()
    got, excluded = {}, []
    for d in sorted(glob.glob(os.path.join(ROOT, "S_r2s_*_dump"))):
        m = regex.match(os.path.basename(d))
        if not m:
            continue
        if want_arm is None:
            scen, cell, seed, arm = m.group(1), int(m.group(2)), int(m.group(3)), "REC"
        else:
            scen, cell, arm, seed = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
            if arm != want_arm or seed != ARM_SEED:
                continue
        if keep is not None and cell not in keep:
            continue
        f = os.path.join(d, "roster_rank0000.txt")
        if not os.path.exists(f):
            excluded.append((cell, arm, scen, seed, "no roster_rank0000.txt"))
            continue
        if not run_completed(scen, cell, arm, NPREV, seed):
            excluded.append((cell, arm, scen, seed, "C run has no completion line"))
            continue
        py = scan_rec_dump(f)
        y0, y1 = LEG[scen]
        years = {y for (y, _p) in py}
        patches = {p for (_y, p) in py}
        if len(years) != (y1 - y0 + 1) or len(patches) != NPATCH:
            excluded.append(
                (cell, arm, scen, seed, f"incomplete: {len(years)} yr x {len(patches)} patches")
            )
            continue
        got[(cell, scen, arm, seed)] = build_rows(py)
        print(f"    {arm:4s} {scen:8s} c{cell:<6d} s{seed}  {len(py):6d} patch-years", flush=True)
    return got, excluded


# ── the statistic ────────────────────────────────────────────────────────────────────────────────

#: the field order `capacity` returns, so callers index by name rather than by position.
CAP = ("disc", "empty", "budget", "total", "net", "ncert")


def capacity(rows, variant):
    """D3's capacity for one leg -> dict over CAP, all rates as a fraction of roster per year.

    `max(0, ...)` twice, per patch-year, because that is where the operator draws (skill trap 5e):
    the budget cannot be negative, and the certain deaths are spent out of the same budget first.

        b     = max(0, (1-rho)*n_tree + Rhat)        the budget the operator may spend
        disc  = max(0, b - n_cert)                   what is left for the discretionary channel
        total = 0            if b <= 0               ⚠ THE GATE: with a non-positive budget the
                                                     arm nominates NOBODY -- and because the kill
                                                     list IS the whole answer, the certain deaths
                                                     are SPARED too (harness :521 and its own
                                                     comment; ADR 0188 section 3 measured that
                                                     branch at 42-46 % of patch-years). The C's
                                                     own hard kills still land and are NOT
                                                     modelled here, so `total` under-counts on a
                                                     gated year -- stated, not hidden.
              = max(b, n_cert) otherwise             once the gate is open a certain death cannot
                                                     be un-killed, so a short budget still costs
                                                     n_cert
        net   = R - total                            the implied roster count change

    ⚠ `disc` is CONVEX in `b`, so its leg mean is NOT `mean(b) - mean(n_cert)`. That is exactly the
    error the first version of D3's oracle anchor made (see the `perfect` variant).

    TWO SUFFIXES, BOTH POST-HOC DESIGN PROBES added after the first full read and labelled as such
    -- neither is a gate and no threshold is attached to either:
      `_sm5`  smooths the WHOLE budget over the last <=5 rendezvous of that patch before rectifying
              it, rather than smoothing only Rhat.
      `_acct` does not rectify per patch-year at all: it accrues the SIGNED budget increment into a
              running account and spends what the account holds, so a year the count model says
              "grow" REPAYS an earlier overspend instead of being clipped to zero. This is the
              formulation the convexity argument points at -- rectification is what makes an
              unbiased-but-noisy budget over-kill, and an account has no rectification in it.
    """
    n = 0
    tot = dict.fromkeys(CAP, 0.0)
    tot_tree = 0.0
    empty = 0
    for rs in rows.values():
        base = variant
        for suf in ("_sm5", "_acct"):
            if base.endswith(suf):
                base = base[: -len(suf)]
        raw = [
            float(r.k_all) if base == "perfect"
            else (1.0 - r.rho) * r.n_tree + r.rhat[base]
            for r in rs
        ]
        if variant.endswith("_sm5"):
            raw = [mean(raw[max(0, i - 4):i + 1]) for i in range(len(raw))]
        # (budget, total) per patch-year: the account variant needs the years IN ORDER, which is
        # what `build_rows` guarantees.
        spend = []
        if variant.endswith("_acct"):
            acct = 0.0
            for i, r in enumerate(rs):
                acct += raw[i]
                b = max(0.0, min(acct, r.n_tree))
                t = 0.0 if b <= 0.0 else max(b, float(r.n_cert))
                acct -= t          # a forced overshoot is charged, so it suppresses later kills
                spend.append((b, t))
        else:
            for i, r in enumerate(rs):
                b = max(0.0, raw[i])
                spend.append((b, 0.0 if b <= 0.0 else max(b, float(r.n_cert))))
        for i, r in enumerate(rs):
            n += 1
            tot_tree += r.n_tree
            if math.isnan(r.rho):
                continue
            b, t = spend[i]
            tot["budget"] += b
            if b <= 0.0:
                empty += 1
            tot["disc"] += max(0.0, b - r.n_cert)
            tot["total"] += t
            tot["net"] += r.r_true - t
            tot["ncert"] += float(r.n_cert)
    if tot_tree <= 0 or n == 0:
        return dict.fromkeys(CAP, float("nan"))
    out = {k: tot[k] / tot_tree for k in CAP}
    out["empty"] = empty / n
    return out


def rate(rows, field):
    num = sum(getattr(r, field) for rs in rows.values() for r in rs)
    den = sum(r.n_tree for rs in rows.values() for r in rs)
    return num / den if den else float("nan")


def per_cell_median(legs, scen, fn):
    """Seeds averaged within a cell, then the median over cells (ADR 0185 section 5's shape)."""
    by_cell = defaultdict(list)
    for (cell, s, _a, _seed), rows in legs.items():
        if s == scen:
            by_cell[cell].append(fn(rows))
    vals = [mean(v) for v in by_cell.values()]
    return median(vals), se(vals), len(vals)


def main() -> int:
    if NPREV != "predict":
        print(f"  NOTE: NPREV={NPREV}. ADR 0185-0188 are all on `predict`.")
    print("=" * 100)
    print("  RUNG-2 GROSS BUDGET — can a LAGGED recruit count carry it? (ADR 0188 section 7's")
    print("  one required derivation, before the arm is written)")
    print(f"  mode NPREV={NPREV}   root {ROOT}")
    print(f"  map    {MAPCSV}")
    print("=" * 100)

    print("\n  scanning the REC dumps (FIT's own stand) ...", flush=True)
    legs, excluded = collect(REC_RE)
    if not legs:
        print("  no REC dumps passed the gate — nothing to derive.")
        return 1
    if excluded:
        print(f"  {len(excluded)} leg(s) EXCLUDED (named, skill trap 2):")
        for cell, arm, scen, seed, why in excluded:
            print(f"      c{cell:<6d} {arm:4s} {scen:9s} s{seed}  {why}")

    # attach rho from the REC-stand replay, and gate the count/density equivalence on the way
    if not os.path.exists(MAPCSV):
        print(f"\n  FATAL: {MAPCSV} not found — rho on FIT's own stand comes from")
        print("  scripts/diagnose_rung2_map_on_rec_stand.jl (ADR 0185). Run it with NPREV=predict.")
        return 1
    mp = read_map_csv(MAPCSV)
    matched = missing = ntree_mismatch = 0
    for (cell, scen, _arm, seed), rows in legs.items():
        for rs in rows.values():
            for r in rs:
                v = mp.get((cell, scen, seed, r.year, r.patch))
                if v is None:
                    missing += 1
                    continue
                n_tree_csv, n_prev, target = v
                if int(n_tree_csv) != r.n_tree:
                    ntree_mismatch += 1
                r.rho = min(RHO_HI, max(RHO_LO, target / (n_prev + 1e-12)))
                matched += 1
    print(f"\n  rho joined on {matched} patch-years ({missing} unmatched, "
          f"{ntree_mismatch} with n_tree != the dump's grow-roster count)")
    print("  THE JOIN GATE: the replay's `n_tree` is the same roster this scan counted, so a")
    print("  nonzero mismatch means the two are not the same patch-years — read nothing below it.")

    # ── PANEL A — D1: is last year's recruit count observable at the rendezvous? ─────────────────
    print("\n" + "-" * 100)
    print("  PANEL A — D1: #{age == 1 at grow, year y} == R(y-1)?  (must be EXACT)")
    print("-" * 100)
    print("    `age` at `grow` is post-increment and establishment sets age 0, so the age-1 cohort")
    print("    IS last year's recruits — countable off the roster the harness already holds. If")
    print("    this is exact, a lagged Rhat needs NO interface change and no integration point.\n")
    ok = bad = 0
    worst = []
    for (cell, scen, _arm, _seed), rows in legs.items():
        for patch, rs in rows.items():
            for i in range(1, len(rs)):
                if rs[i].rhat["lag1"] == rs[i - 1].r_true:
                    ok += 1
                else:
                    bad += 1
                    if len(worst) < 8:
                        worst.append(
                            f"c{cell} {scen} p{patch} y{rs[i].year}: "
                            f"age1={rs[i].rhat['lag1']:.0f} vs R(y-1)={rs[i - 1].r_true:.0f}"
                        )
    tot = ok + bad
    print(f"    {ok} of {tot} patch-years agree ({100 * ok / tot:.3f} %)"
          f"  -> D1 {'HOLDS EXACTLY' if bad == 0 else 'FAILS'}")
    for w in worst:
        print(f"      {w}")
    print("    (a leg's FIRST year is excluded: its age-1 cohort refers to the year BEFORE the")
    print("     leg — a usable Rhat at runtime, with no R(y-1) in this table to check it against.)")

    # ── PANEL B — how predictable is recruitment, and does it carry the warming signal? ──────────
    print("\n" + "-" * 100)
    print("  PANEL B — recruitment's own statistics: is a one-year lag informative at all?")
    print("-" * 100)
    print(f"    {'leg':<9} {'cells':>5} {'R %/yr':>8} {'R/patch-yr':>11} {'sd':>7} {'zero%':>7}"
          f" {'lag-1 r':>8} {'within':>7} {'r(lag1)':>8} {'r(mean5)':>9} {'r(expand)':>10}"
          f" {'RMSE lag1':>10}")
    fitr = {}
    for scen in SCENS:
        rs_all = [r for (c, s, _a, _sd), rows in legs.items() if s == scen
                  for rl in rows.values() for r in rl]
        if not rs_all:
            continue
        rr, _e, _n = per_cell_median(legs, scen, lambda rows: rate(rows, "r_true"))
        fitr[scen] = rr
        rt = [r.r_true for r in rs_all]
        zero = sum(1 for x in rt if x == 0) / len(rt)
        # lag-1 autocorrelation, formed WITHIN a patch (never across a patch boundary). TWO
        # versions: the POOLED one carries every patch's own mean level, so persistent
        # between-patch differences in recruitment inflate it and it must NOT be read as
        # year-to-year predictability; the DEMEANED one subtracts each patch's own mean and is
        # the temporal part alone.
        xs, ys, dxs, dys = [], [], [], []
        for (_c, s, _a, _sd), rows in legs.items():
            if s != scen:
                continue
            for rl in rows.values():
                pm = mean([r.r_true for r in rl])
                for i in range(1, len(rl)):
                    xs.append(rl[i - 1].r_true)
                    ys.append(rl[i].r_true)
                    dxs.append(rl[i - 1].r_true - pm)
                    dys.append(rl[i].r_true - pm)
        skill = {v: pearson([r.rhat[v] for r in rs_all], rt) for v in ("lag1", "mean5", "expand")}
        print(f"    {scen:<9} {len(set(c for (c, s, _a, _sd) in legs if s == scen)):>5d}"
              f" {100 * rr:>7.3f}% {mean(rt):>11.4f} {sd(rt):>7.3f} {100 * zero:>6.1f}%"
              f" {pearson(xs, ys):>8.3f} {pearson(dxs, dys):>7.3f}"
              f" {skill['lag1']:>8.3f} {skill['mean5']:>9.3f}"
              f" {skill['expand']:>10.3f} {rmse([r.rhat['lag1'] for r in rs_all], rt):>10.3f}")
    if len(fitr) == 2:
        print(f"\n    THE LEG CONTRAST: FIT's own recruitment rises "
              f"{100 * fitr['historic']:.3f} -> {100 * fitr['ssp370']:.3f} %/yr "
              f"({100 * (fitr['ssp370'] / fitr['historic'] - 1):+.1f} %).")
        print("    So the recruit term is itself climate-responsive: handing it to the operator")
        print("    hands over a budget that RISES under warming, one year late.")
    print("\n    `lag-1 r` pools patches, so it carries each patch's own persistent recruitment")
    print("    LEVEL; `within` demeans by patch and is the year-to-year part alone. The gap")
    print("    between them is the point: a lagged Rhat mostly recovers the patch's LEVEL, and")
    print("    exactly what a budget needs — do not quote the pooled value as temporal skill.")
    print("\n    A low per-patch-year correlation is EXPECTED and not disqualifying: R is a")
    print("    small integer (a patch holds ~4-11 stems), so its per-year value is near-Poisson.")
    print("    What the budget needs is the right MEAN and a bounded cumulative error (C and D).")

    # ── PANEL C — D2: does the lag put the count at risk? ───────────────────────────────────────
    print("\n" + "-" * 100)
    print("  PANEL C — D2: the count departure sum(R - Rhat) over a leg, per patch")
    print("-" * 100)
    print("    DERIVED: n_next = target + (R - Rhat), so with Rhat = R(y-1) the departure")
    print("    TELESCOPES to R_last - R_first — bounded by ONE year's recruitment however long the")
    print("    leg. With Rhat = 0 (the current operator) it is sum_y R_y, growing with the leg.")
    print(f"\n    {'leg':<9} {'variant':<8} {'|sum(R-Rhat)| stems':>19} {'as % of roster':>15}"
          f" {'derived bound':>14}")
    for scen in SCENS:
        for v in VARIANTS:
            tot, bound, den = [], [], []
            for (_c, s, _a, _sd), rows in legs.items():
                if s != scen:
                    continue
                for rl in rows.values():
                    tot.append(abs(sum(r.r_true - r.rhat[v] for r in rl)))
                    bound.append(max(r.r_true for r in rl))
                    den.append(mean([r.n_tree for r in rl]))
            if not tot:
                continue
            pct = 100 * mean(tot) / mean(den) if mean(den) else float("nan")
            bd = f"{mean(bound):>14.2f}" if v == "lag1" else " " * 14
            print(f"    {scen:<9} {v:<8} {mean(tot):>19.2f} {pct:>14.1f}% {bd}")
    print("\n    `derived bound` is printed for `lag1` only, where D2 predicts it: mean per-patch")
    print("    max annual recruitment. The measured |sum| must sit AT OR BELOW it.")

    # ── PANEL D — the blessed capacity, with its two derived anchors ─────────────────────────────
    print("\n" + "-" * 100)
    print("  PANEL D — THE CAPACITY: discretionary kills the operator could afford, by Rhat")
    print("-" * 100)
    print("    D(Rhat) = mean max(0, max(0,(1-rho)*n_tree + Rhat) - n_cert) / n_tree, per patch-yr")
    print("    on FIT's OWN stand. Compare against FIT's own K_disc in the same table.")
    print("    `total` = mean max(budget, n_cert): the operator cannot un-kill a certain death,")
    print("    so a short budget still loses n_cert. `net` = FIT's R minus that — the implied")
    print("    count change, whose LEVEL must be checked against the horizon (skill trap 5g).\n")
    print(f"    {'leg':<9} {'variant':<10} {'budget':>8} {'D %/yr':>8} {'SE':>6} {'empty':>7}"
          f" {'total':>7} {'net':>7} {'x leg':>7} {'K_all':>7} {'K_disc':>7} {'K_cert':>7}"
          f" {'>=1.5?':>7}")
    dvals = {}
    for scen in SCENS:
        y0, y1 = LEG[scen]
        nyr = y1 - y0 + 1
        ka = per_cell_median(legs, scen, lambda rows: rate(rows, "k_all"))[0]
        kd, _e, _n = per_cell_median(legs, scen, lambda rows: rate(rows, "k_disc"))
        kc, _e2, _n2 = per_cell_median(
            legs, scen, lambda rows: rate(rows, "k_all") - rate(rows, "k_disc")
        )
        for v in BUDGETS:
            d, dse, ncell = per_cell_median(legs, scen, lambda rows, v=v: capacity(rows, v)["disc"])
            em = per_cell_median(legs, scen, lambda rows, v=v: capacity(rows, v)["empty"])[0]
            bg = per_cell_median(legs, scen, lambda rows, v=v: capacity(rows, v)["budget"])[0]
            tt = per_cell_median(legs, scen, lambda rows, v=v: capacity(rows, v)["total"])[0]
            nn = per_cell_median(legs, scen, lambda rows, v=v: capacity(rows, v)["net"])[0]
            dvals[(scen, v)] = (100 * d, 100 * dse, ncell)
            print(f"    {scen:<9} {v:<10} {100 * bg:>7.3f}% {100 * d:>7.3f}% {100 * dse:>5.3f}"
                  f" {100 * em:>6.1f}% {100 * tt:>6.3f}% {100 * nn:>6.3f}%"
                  f" {math.exp(nn * nyr):>7.2f} {100 * ka:>6.3f}% {100 * kd:>6.3f}%"
                  f" {100 * kc:>6.3f}%"
                  f" {'YES' if 100 * d >= CRIT_RATE else 'no':>7}")
    print("\n    `empty` is the instrument's analogue of the `rho >= 1` gate that leaves 42-46 %")
    print("    of patch-years with no kill list at all (ADR 0188 section 3): under the gross")
    print("    budget the gate is `budget <= 0`, and the R term should collapse its incidence.")
    print("    `x leg` = exp(net * years): what the roster would do over the leg at that net rate.")
    print("    `K_all`/`K_disc`/`K_cert` are the stand's OWN realized kills, so the `none` row's")
    print("    `total` is checkable against `K_all`, and `perfect`'s must equal it by design.")

    print("\n    THE DERIVED ANCHORS (D3) — the values written down before the run, and the one")
    print("    correction, disclosed:")
    verdict_ok = True
    for scen in SCENS:
        if (scen, "none") not in dvals:
            continue
        d = dvals[(scen, "none")][0]
        lo, hi = ANCHOR_CURRENT
        hit = lo <= d <= hi
        verdict_ok &= hit
        print(f"      {scen:9s} none    {d:6.3f} %/yr  in [{lo}, {hi}]"
              f"  -> {'PASS' if hit else 'FAIL'}"
              f"   (the CURRENT operator, must reproduce ADR 0187's 0.5-0.6 %/yr)")
    print("\n      ⚠ D3's ORACLE band [1.5, 2.6] IS MIS-DERIVED AND IS NOT USED AS A GATE. It was")
    print("      obtained from a LINEAR identity — `mean(b) - mean(n_cert)` with `b ~ K_all` —")
    print("      while the statistic contains `max(0, b - n_cert)`, CONVEX, so its leg mean")
    print("      exceeds the difference of the means by a Jensen gap that grows with the count")
    print("      model's per-patch-year error. The band is retained here only so the record shows")
    print("      what was written before the run. A DERIVED ANCHOR MUST BE DERIVED THROUGH THE")
    print("      SAME NONLINEARITY AS THE STATISTIC. The replacement is exact, not a band:")
    print("\n      `perfect` (b = K_all per patch-year) => max(0, K_all - n_cert) == K_disc")
    print("      IDENTICALLY, so it must reproduce FIT's own discretionary rate to rounding:")
    for scen in SCENS:
        if (scen, "perfect") not in dvals:
            continue
        d = dvals[(scen, "perfect")][0]
        kd = 100 * per_cell_median(legs, scen, lambda rows: rate(rows, "k_disc"))[0]
        hit = abs(d - kd) <= ANCHOR_PERFECT_TOL
        verdict_ok &= hit
        print(f"      {scen:9s} perfect {d:6.3f} %/yr  vs FIT K_disc {kd:6.3f}"
              f"  (|diff| {abs(d - kd):.4f} <= {ANCHOR_PERFECT_TOL})"
              f"  -> {'PASS' if hit else 'FAIL'}")
    print("\n      For the ORACLE and every lagged variant the expected value is NOT derivable a")
    print("      priori: it depends on the count model's own per-patch-year error, which is what")
    print("      the Jensen gap between `perfect` and `oracle` MEASURES. Read that gap as data.")
    if not verdict_ok:
        print("\n    *** AN ANCHOR FAILED — this is a BASIS error, not a result about the lag. Do")
        print("    *** not read the verdict below; fix the panel first (skill trap 5c/5f).")

    # ── the verdict ─────────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 100)
    print("  VERDICT (ADR 0188 section 7's pre-registered branches; ssp370 leg)")
    print("=" * 100)
    d_lag = dvals.get(("ssp370", "lag1"), (float("nan"),))[0]
    d_or = dvals.get(("ssp370", "oracle"), (float("nan"),))[0]
    print(f"    D1 (age-1 observability)  : {'EXACT' if bad == 0 else 'FAILS'}")
    print(f"    D(lag1)                   : {d_lag:.3f} %/yr   (threshold {CRIT_RATE})")
    print(f"    D(oracle, unavailable)    : {d_or:.3f} %/yr")
    if not verdict_ok:
        print("    -> NO VERDICT: a derived anchor failed, so the capacity column is not trusted.")
    elif bad != 0:
        print("    -> (ii) THE OBSERVABLE IS NOT EXACT: the lagged recruit count is not")
        print("       from the roster alone. RAISE THE INTEGRATION POINT with line M.")
    elif d_lag >= CRIT_RATE:
        print("    -> (i) THE INSTRUMENT SURVIVES THE LAG. Write the arm; ADR 0188 section 7's")
        print("       criterion stands unchanged as its gate. Capacity is NECESSARY, not")
        print("       SUFFICIENT — the arm must still be run and scored.")
    elif d_or >= CRIT_RATE:
        print("    -> (ii) THE LAG IS WHAT COSTS IT: the oracle clears the threshold, the lagged")
        print("       estimate does not. RAISE THE INTEGRATION POINT with line M (expose the C's")
        print("       own establishment count at the rendezvous).")
    else:
        print("    -> (iii) THE GROSS BUDGET ITSELF IS INSUFFICIENT. ADR 0188 section 7's lever is")
        print("       smaller than derived. Do not write the arm.")

    if os.environ.get("SKIP_ARM"):
        print("\n  SKIP_ARM set — panel E (the same capacity on S1's OWN stand) not run.")
        return 0

    # ── PANEL E — the same statistic on S1's own (diverged) stand ────────────────────────────────
    print("\n" + "-" * 100)
    print("  PANEL E — the capacity on S1's OWN stand, not FIT's (the arms diverged +90 % agb)")
    print("-" * 100)
    print("    rho comes from S1's own `s_arm_log.txt`; R and n_cert from its own dumps. A")
    print("    conclusion that only holds on FIT's stand would be an artifact of the reference.")
    print(f"    ONE SEED ONLY (ARM_SEED={ARM_SEED}) — this is a basis check, not a seed average.")
    arms, arm_excl = collect(ARM_RE, want_arm="S1")
    if not arms:
        print("    no S1 dumps passed the gate.")
        return 0
    for cell, arm, scen, seed, why in arm_excl[:8]:
        print(f"      excluded c{cell:<6d} {arm:4s} {scen:9s} s{seed}  {why}")
    joined = 0
    for (cell, scen, arm, seed), rows in arms.items():
        log = os.path.join(
            ROOT, f"S_r2s_{scen}_c{cell}_{arm}_{NPREV}_s{seed}_apply", "s_arm_log.txt"
        )
        if not os.path.exists(log):
            continue
        rho = read_arm_rho(log)
        for rs in rows.values():
            for r in rs:
                v = rho.get((r.year, r.patch))
                if v is not None:
                    r.rho = v[1]
                    joined += 1
    print(f"\n    rho joined on {joined} S1 patch-years")
    print(f"    {'leg':<9} {'variant':<10} {'budget':>8} {'D %/yr':>8} {'SE':>6} {'empty':>7}"
          f" {'total':>7} {'net':>7} {'x leg':>7} {'K_all':>7} {'K_disc':>7} {'K_cert':>7}")
    for scen in SCENS:
        y0, y1 = LEG[scen]
        nyr = y1 - y0 + 1
        ka = per_cell_median(arms, scen, lambda rows: rate(rows, "k_all"))[0]
        kd, _e, _n = per_cell_median(arms, scen, lambda rows: rate(rows, "k_disc"))
        kc, _e2, _n2 = per_cell_median(
            arms, scen, lambda rows: rate(rows, "k_all") - rate(rows, "k_disc")
        )
        for v in BUDGETS:
            d, dse, _nc = per_cell_median(arms, scen, lambda rows, v=v: capacity(rows, v)["disc"])
            em = per_cell_median(arms, scen, lambda rows, v=v: capacity(rows, v)["empty"])[0]
            bg = per_cell_median(arms, scen, lambda rows, v=v: capacity(rows, v)["budget"])[0]
            tt = per_cell_median(arms, scen, lambda rows, v=v: capacity(rows, v)["total"])[0]
            nn = per_cell_median(arms, scen, lambda rows, v=v: capacity(rows, v)["net"])[0]
            if math.isnan(d):
                continue
            print(f"    {scen:<9} {v:<10} {100 * bg:>7.3f}% {100 * d:>7.3f}% {100 * dse:>5.3f}"
                  f" {100 * em:>6.1f}% {100 * tt:>6.3f}% {100 * nn:>6.3f}%"
                  f" {math.exp(nn * nyr):>7.2f} {100 * ka:>6.3f}% {100 * kd:>6.3f}%"
                  f" {100 * kc:>6.3f}%")
    print("\n    ⚠ S1's `k_disc` here is the C's flagged-dead set restricted to `mort_prob < 1` on")
    print("    S1's OWN stand, i.e. its realized discretionary kills — the same quantity ADR 0187")
    print("    measured at 0.6 %/yr. It is NOT a reference; FIT's is (panel D).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
