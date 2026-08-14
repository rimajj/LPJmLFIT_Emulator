#!/usr/bin/env python
"""The DERIVABLE A-PRIORI GATE on the `H*` RATE arms of rung 2 (ADR 0242).

WHAT THIS IS FOR
----------------
ADR 0241 retired the learned count model from the mortality path and named its
replacement: FIT's own per-tree hazard applied as a RATE, with no target, no budget and
no account. `scripts/rung2_s_demography_harness.jl`'s `H0`/`H0h`/`H1` arms are that
operator. This script is the gate that must pass BEFORE any `H*` number is read, exactly
as `diagnose_rung2_gross_account_identity.py` is for the `G*` arms: it checks arithmetic
the arms cannot fail for an interesting reason, so that anything they DO show is not an
implementation artifact.

Three things are derivable a priori, all checked from the arm logs alone (seconds, no
dump scan, no model run):

(A) THE EXPECTED-FLUX IDENTITY. On a given roster all three rate arms remove the same
    expected density, `Sum nind*mort` -- H1 because `1 - f_i = mort_i` stem by stem, H0
    because the nind-weighted mean hazard times the total density is the same sum, H0h
    because the certain stems contribute their own `nind*1` and the weighted mean over
    the rest is taken over exactly the rest. So `kill_exp == haz_exp` row by row, to the
    last bit. It is a PER-PATCH-YEAR identity and NOT a leg-total one: the arms' stands
    diverge, so their leg-summed `haz_exp` legitimately differs (skill trap 5).

(B) THE REALIZATION. The draw is one independent Bernoulli per stem, so the realized
    removed density has mean `Sum nind*(1-f)` = `kill_exp` and variance
    `Sum nind^2*f*(1-f)` = `kill_var`, both accumulated by the harness from the `f` it
    actually used. Pooled over a leg, `z = (Sum kill_nind - Sum kill_exp)/sqrt(Sum
    kill_var)` is a standard normal under nothing but "the code drew what it said it
    would". This is EXACT for every arm, `S*` and `G*` included -- ADR 0188's
    `1.004 +- 0.009` had to hand-roll an SE from a uniform-draw assumption only `S0`
    meets, and ADR 0187 section 5f is the standing instruction to derive the sampling SE
    before choosing a tolerance.

(C) THE GATE INCIDENCE. A rate arm must enter the decision on EVERY non-empty
    patch-year: the `rho < 1` gate that left 42-46 % of `S*` patch-years with an empty
    kill list (ADR 0188, skill trap 5l) is part of the count-budget architecture and must
    not be inherited. `rho_eff` is NaN for a rate arm to say so, and a draw happens
    wherever there are stems.

AND ONE THING THAT IS NOT A GATE BUT IS THE POINT (panel D): the arm's realized removal
against FIT's own expected flux on the SAME roster, `Sum kill_nind / Sum haz_exp`. For a
rate arm this is 1.00 by construction -- panel B restated -- and for an `S*`/`G*` arm it
is ADR 0187's rate shortfall (and ADR 0240's excess) from the log, with no dump scan.
NOT a ranking: every row is on its own diverged stand (skill traps 5 and 20).

Env knobs: ROOT (default /p/tmp/jamirp/S_rung2) - ARMS (default "H0 H0h H1") - NPREV
(default predict) - SCENS (default "historic ssp370") - Z (the |z| tolerance for panel B,
default 4.0).

Run it with /home/jamirp/.conda/envs/py311_new/bin/python (the system python is too old
for `zip(..., strict=True)` and dies below the fold).
"""

import math
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# The arm-name set and the shared `ARMS` parser live in the response scorer; importing
# them is ADR 0186's rule (import the criterion's own definition) and keeps one arm
# vocabulary across every rung-2 script.
import diagnose_rung2_map_target_response as S  # noqa: E402, N812

ROOT = os.environ.get("ROOT", "/p/tmp/jamirp/S_rung2")
ARMS = tuple(S._split_arms(os.environ.get("ARMS", "H0 H0h H1")))
NPREV = os.environ.get("NPREV", "predict")
SCENS = tuple(S._split_arms(os.environ.get("SCENS", "historic ssp370")))
ZTOL = float(os.environ.get("Z", "4.0"))
#: B1, the clause that carries panel B (see `panel_b` for why z is not one).
RTOL = float(os.environ.get("RTOL", "0.02"))

RATE_ARMS = ("H0", "H0h", "H1")
DIR_RE = re.compile(
    r"^S_r2s_(\w+?)_c(\d+)_(REC|" + "|".join(S.ALL_ARMS) + r")_(roster|predict)_s(\d+)_apply$"
)
# The columns this gate needs. A log written before ADR 0242 simply lacks them -- say so
# loudly rather than reporting a zero (the ADR-0240 "a missing measurement must not print
# as a measured zero" rule, applied to the reader side).
NEEDED = ("haz_exp", "kill_nind", "kill_exp", "kill_var")


def read_log(path):
    """The `L` rows as dicts keyed by the `#H` header (positions never hardcoded)."""
    rows, head = [], None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#H"):
                head = line.split()[1:]
                continue
            if not line.startswith("L ") or head is None:
                continue
            parts = line.split()
            if len(parts) == len(head):
                rows.append(dict(zip(head, parts, strict=True)))
    return rows


def legs():
    """(scen, cell, arm, seed) -> arm-log path, restricted to ARMS/SCENS/NPREV."""
    out = {}
    for name in sorted(os.listdir(ROOT)):
        m = DIR_RE.match(name)
        if not m:
            continue
        scen, cell, arm, mode, seed = m.groups()
        if mode != NPREV or arm not in ARMS or scen not in SCENS:
            continue
        log = os.path.join(ROOT, name, "s_arm_log.txt")
        if os.path.isfile(log):
            out[(scen, int(cell), arm, int(seed))] = log
    return out


def panel_a(per_leg):
    print()
    print("=" * 96)
    print("(A) EXPECTED-FLUX IDENTITY  kill_exp == haz_exp, row by row, for a RATE arm")
    print("    Derivable: all three rate arms remove `Sum nind*mort` in expectation ON")
    print("    THE SAME ROSTER. Per-patch-year only -- leg totals differ because the")
    print("    stands diverge (skill trap 5).")
    hdr = f"    {'arm':>4} {'legs':>5} {'rows':>7} {'max|kill_exp-haz_exp|':>22} {'bad':>6}"
    print(hdr)
    ok = True
    for arm in RATE_ARMS:
        ks = [k for k in per_leg if k[2] == arm]
        if not ks:
            continue
        worst, bad, n = 0.0, 0, 0
        for k in ks:
            for r in per_leg[k]:
                d = abs(float(r["kill_exp"]) - float(r["haz_exp"]))
                worst = max(worst, d)
                bad += d > 1.0e-12
                n += 1
        ok &= bad == 0
        print(f"    {arm:>4} {len(ks):>5} {n:>7} {worst:>22.3e} {bad:>6}")
    print(f"    -> {'PASS' if ok else 'FAIL'}")
    return ok


def panel_b(per_leg):
    """Realized vs implied removal, with BOTH the pre-registered pooled z and the corrected test.

    ⚠ THE POOLED WITHIN-LEG z IS NOT A STANDARD NORMAL, AND THIS IS NOT A DEFECT IN THE ARM.
    The numerator is a martingale (E[kill_nind | history] = kill_exp exactly, row by row), so it
    is zero-mean -- but the denominator `sqrt(Sum kill_var)` is RANDOM and NEGATIVELY correlated
    with it through the trajectory: a leg that happens to kill more than implied carries a
    smaller stand afterwards, hence smaller later `kill_var`, hence a smaller denominator. A
    positive residual is amplified and a negative one damped, so E[z] > 0 with no bias anywhere
    in the draw. Measured: pooled |z| up to 4.47 against the pre-registered 4.0, per-leg z at
    mean +0.50 with sd 0.992, and the effect GROWS down the leg (+1.02 in the first decade of an
    ssp370 leg, +3.95 in the seventh) -- the signature of feedback, not of arithmetic.
    `scripts/diagnose_rung2_rate_draw_replay.jl` settles it on frozen rosters: replaying the
    harness's own seed reproduces the logged `n_kill` at **2025 of 2025 patch-years, 0
    differing**, and 400 Monte-Carlo redraws of those same fixed rosters land at **-0.0585 %**
    of the implied total, z = -0.83 -- the draw is unbiased.

    So the clause below is kept, printed, and NOT moved (ADR 0187's rule), and the gate is
    carried by two statistics that the feedback does not distort:

      B1  the pooled RATIO realized/implied, tolerance |ratio - 1| < RTOL (default 2 %). An
          implementation error shows up here as percent, not as fractions of a percent, and a
          ratio is not distorted by the normalizer. THIS is the gate clause.

    The per-leg z mean and sd are printed as DIAGNOSTICS. A first version gated on sd(z_leg)
    being within 0.25 of 1, on the reasoning that a mean shift should leave the variance alone;
    measured, it runs 0.74-1.27 across arms, lowest for the arm whose stand collapses. That
    clause was WRONG for the same reason the pooled z is: under feedback the self-normalized
    statistic's SECOND moment is not derivable either, so gating on it would repeat exactly the
    mistake ADR 0187 section 5f warns about. It is reported, not gated, and this paragraph is
    the disclosure that both additions came after the pooled z was first read.
    """
    print()
    print("=" * 96)
    print("(B) REALIZATION  z = (realized - implied)/sd, pooled per arm x leg")
    print("    Exact for EVERY arm: the harness accumulates the mean AND the variance")
    print("    from the `f` it actually used. ⚠ The POOLED z is NOT a standard normal --")
    print("    its denominator is correlated with its own numerator through the")
    print("    trajectory feedback, so E[z] > 0 with an unbiased draw (see the")
    print("    docstring and diagnose_rung2_rate_draw_replay.jl). B1, the RATIO, is the gate.")
    print(
        f"    {'arm':>4} {'scen':>9} {'legs':>5} {'realized':>11} {'implied':>11}"
        f" {'ratio':>7} {'sd':>8} {'z':>7} {'z_leg':>7} {'sd_z':>6}"
    )
    ok = True
    ok_pre = True
    for arm in ARMS:
        for scen in SCENS:
            ks = [k for k in per_leg if k[2] == arm and k[0] == scen]
            if not ks:
                continue
            real = exp = var = 0.0
            for k in ks:
                for r in per_leg[k]:
                    real += float(r["kill_nind"])
                    exp += float(r["kill_exp"])
                    var += float(r["kill_var"])
            sd = math.sqrt(var)
            z = (real - exp) / sd if sd > 0 else float("nan")
            ratio = real / exp if exp > 0 else float("nan")
            legz = []
            for k in ks:
                lr = sum(float(r["kill_nind"]) for r in per_leg[k])
                le = sum(float(r["kill_exp"]) for r in per_leg[k])
                lv = sum(float(r["kill_var"]) for r in per_leg[k])
                if lv > 0:
                    legz.append((lr - le) / math.sqrt(lv))
            zsd = statistics.pstdev(legz) if len(legz) > 1 else float("nan")
            zmu = statistics.fmean(legz) if legz else float("nan")
            ok_pre &= not abs(z) > ZTOL
            ok &= not abs(ratio - 1.0) > RTOL
            print(
                f"    {arm:>4} {scen:>9} {len(ks):>5} {real:>11.4f} {exp:>11.4f}"
                f" {ratio:>7.4f} {sd:>8.4f} {z:>7.2f} {zmu:>7.2f} {zsd:>6.2f}"
            )
    print(f"    pre-registered clause |z| < {ZTOL}: {'PASS' if ok_pre else 'FAIL'}"
          " (kept and printed, NOT moved -- see the docstring)")
    print(f"    -> {'PASS' if ok else 'FAIL'}  B1 |ratio-1| < {RTOL} is the GATE.")
    print("    `z_leg`/`sd_z` are DIAGNOSTICS, not clauses: their null distribution is not")
    print("    derivable under the feedback either, so gating on them would repeat the very")
    print("    mistake ADR 0187 section 5f warns about. The exact check is the frozen-roster")
    print("    replay in scripts/diagnose_rung2_rate_draw_replay.jl.")
    return ok


def panel_c(per_leg):
    print()
    print("=" * 96)
    print("(C) GATE INCIDENCE  a rate arm must decide on EVERY non-empty patch-year")
    print("    The `rho < 1` gate belongs to the count-budget architecture (ADR 0188,")
    print("    trap 5l) and must not be inherited: `rho_eff` is NaN and a draw happens")
    print("    wherever there are stems.")
    print(
        f"    {'arm':>4} {'rows':>7} {'empty':>7} {'no-draw':>8} {'rho NaN':>8}"
        f" {'zero-kill':>10}"
    )
    ok = True
    for arm in ARMS:
        ks = [k for k in per_leg if k[2] == arm]
        if not ks:
            continue
        n = empty = nodraw = nanrho = zerokill = 0
        for k in ks:
            for r in per_leg[k]:
                n += 1
                ntree = float(r["n_tree"])
                empty += ntree == 0
                drew = float(r["kill_var"]) > 0.0 or float(r["kill_exp"]) > 0.0
                nodraw += ntree > 0 and not drew
                nanrho += math.isnan(float(r["rho_eff"]))
                zerokill += float(r["n_kill"]) == 0
        if arm in RATE_ARMS:
            ok &= nodraw == 0 and nanrho == n
        pct = 100.0 * zerokill / max(n, 1)
        print(
            f"    {arm:>4} {n:>7} {empty:>7} {nodraw:>8} {nanrho:>8} {pct:>9.1f}%"
        )
    print(f"    -> {'PASS' if ok else 'FAIL'}")
    return ok


def panel_d(per_leg):
    print()
    print("=" * 96)
    print("(D) DELIVERED FLUX  realized / haz_exp -- the arm's removal against FIT's own")
    print("    expected mortality ON THE ARM'S OWN ROSTER. 1.00 by construction for a")
    print("    rate arm; for an S*/G* arm it is ADR 0187's rate shortfall from the log.")
    print("    NOT a ranking: every row is a different, diverged stand (traps 5 and 20).")
    print(
        f"    {'arm':>4} {'scen':>9} {'legs':>5} {'realized':>11} {'haz_exp':>11}"
        f" {'delivered':>10}"
    )
    for arm in ARMS:
        for scen in SCENS:
            ks = [k for k in per_leg if k[2] == arm and k[0] == scen]
            if not ks:
                continue
            real = hz = 0.0
            for k in ks:
                for r in per_leg[k]:
                    real += float(r["kill_nind"])
                    hz += float(r["haz_exp"])
            dl = real / hz if hz > 0 else float("nan")
            print(
                f"    {arm:>4} {scen:>9} {len(ks):>5} {real:>11.4f} {hz:>11.4f}"
                f" {dl:>10.4f}"
            )


def main():
    print("=" * 96)
    print("RUNG-2 RATE ARMS -- the derivable a-priori gate (ADR 0242)")
    print(f"  ROOT={ROOT}  NPREV={NPREV}  ARMS={' '.join(ARMS)}")
    print(f"  SCENS={' '.join(SCENS)}  |z| tolerance {ZTOL}")
    found = legs()
    if not found:
        raise SystemExit(f"no arm logs under {ROOT} for arms {ARMS} in mode {NPREV}")
    print(f"  legs on disk: {len(found)}")

    stale, per_leg = [], {}
    for key, path in sorted(found.items()):
        rows = read_log(path)
        if not rows or any(c not in rows[0] for c in NEEDED):
            stale.append(key)
            continue
        per_leg[key] = rows

    if stale:
        print()
        print(f"  {len(stale)} leg(s) predate the ADR-0242 columns; EXCLUDED, not zeroed:")
        for k in stale[:8]:
            print(f"    {k}")
        if len(stale) > 8:
            print(f"    ... and {len(stale) - 8} more")
    if not per_leg:
        raise SystemExit("every leg predates the gate's columns -- re-run the arms")

    ok = panel_a(per_leg)
    ok = panel_b(per_leg) and ok
    ok = panel_c(per_leg) and ok
    panel_d(per_leg)

    print()
    print("=" * 96)
    print(f"VERDICT: {'PASS' if ok else 'FAIL'} -- A, B and C are the gate; D is information.")
    print("This gates the ARITHMETIC, not coverage: a truncated leg still satisfies it.")
    print("Run scripts/check_rung2_campaign_coverage.py before reading a campaign result.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
