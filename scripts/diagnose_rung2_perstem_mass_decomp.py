#!/usr/bin/env python
"""
diagnose_rung2_perstem_mass_decomp — IS THE ARMS' PER-STEM MASS EXCESS PRESENT AT MATCHED AGE AND
MATCHED HEIGHT, OR IS IT A COMPOSITION EFFECT OF A THINNED STAND?  ADR 0240 section 8 / line S
STATE section B step 1, pre-registered.  A dumps-only scan; no model run.

ADR 0186 established that the emulator's defect is PER-STEM MASS, not count.  ADR 0240's gross-
budget arm made it worse (`S1` +96 %, `G1` +269 %) while its total biomass landed on FIT's.  In a
rung-2 arm THE C DOES THE GROWING (dump-skill trap 5) -- F never runs -- so a per-stem mass excess
cannot be a growth-code error.  It is either (a) LPJmL-FIT's own physics responding correctly to a
thinned stand (fewer trees -> less competition -> bigger trees), in which case it is DOWNSTREAM of
the stand-structure error and the lever is structure, or (b) present even at matched age and
matched height, in which case the arms' individual trees really are heavier than FIT's own trees of
the same age and size, and that is a DISCLOSURE about the substitution rather than an operator
defect.

-- THE PRE-REGISTERED READING (STATE section B step 1; thresholds fixed BEFORE this run) ---------

    share  ==  dPER_matched / dPER_unmatched         on the age-matched basis, ssp370, FIT-gain
                                                     cells, median over cells

    share <  0.25   -> the excess is a STRUCTURE consequence; step 2 (an operator owning
                       establishment) is the right lever.
    share >  0.60   -> the trees really ARE heavier at the same age; the question moves to what the
                       C's growth is doing on a thinned stand -- a disclosure about the
                       substitution, not a defect to fix in the operator.
    0.25 <= share <= 0.60 -> in between; say so and name what breaks the tie.

    REPORT THE WHOLE PROFILE BY HEIGHT QUINTILE, NOT A SUMMARY (ADR 0187's shape-vs-level rule): a
    COMPOSITION effect moves the stem SHARES between bins while leaving the per-bin mean mass
    alone; a real per-stem effect LIFTS the per-bin means.  A single matched number cannot tell
    those apart, and the two imply different work.

-- THE REFERENCE BASIS ---------------------------------------------------------------------------

POPULATION.  The `grow`-phase roster at the TERMINAL YEAR (2100 for ssp370, 2019 for historic),
restricted to `height > 5 m` -- the `ind` writer's emission cut, and EXACTLY the population behind
the arm log's `n_emit` and `agb_rt` (harness :528).  That is the population ADR 0240's `dPER` is
formed on, which is what makes this decomposition like-for-like rather than a second definition.

PER-STEM MASS.  `w = leaf_c + sapwood_c + heartwood_c - debt_c`, all per INDIVIDUAL (dump-skill
trap 8).  ⚠ This is an APPROXIMATION of the C's own `agb` (`agb_tree.c:25`): it omits `excess` and
`turn_litt.leaf`, neither of which the hook emits.  It is therefore GATED, not assumed -- panel 0
requires the dump-derived `dPER` to reproduce ADR 0240 section 3's published +269 % / +96 % within
`GATE_DPER` before any matched number is read.  A miss is a basis error (residual-diagnosis
section 14: reproduce the published table before adding a column to it).

MATCHING.  Bins are FIT's OWN terminal-stand quantiles at that cell (dump-skill trap 5d: the
reference arm's stand is the binning basis).  The matched mean is a direct standardisation,

    w_A^matched  =  sum_b  pi_R(b) * wbar_A(b)          pi_R = FIT's own stem share in bin b

so it answers "what would the arm's mean per-stem mass be if its stems were distributed over age
(or height) the way FIT's are?".  ⚠ BINS THE ARM DOES NOT OCCUPY CANNOT BE MATCHED.  `pi_R` is
renormalised over the covered bins and the COVERED SHARE IS PRINTED: if the arm has no stems in
FIT's small-tree bins, that missing share IS the structure effect and reporting a matched number
without it would hide the finding inside its own denominator.

Usage
    export NPREV=predict
    /home/jamirp/.conda/envs/py311_new/bin/python scripts/diagnose_rung2_perstem_mass_decomp.py
    # CELLS=12045,42490 restricts the scan; ARMS_B="S1 G1"; SEEDS=1 for a fast smoke test;
    # SCEN=ssp370 (default; `historic` also works).
"""

from __future__ import annotations

import glob
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from diagnose_rung2_kill_budget import mean, median  # noqa: E402
from diagnose_rung2_map_target_response import (  # noqa: E402
    NLIVING,
    NPATCH,
    NPREV,
    ROOT,
    TERMINAL_YEAR,
    read_nliving,
    run_completed,
)

HEIGHT_MIN = 5.0
SCEN = os.environ.get("SCEN", "ssp370")
ARMS_B = tuple(os.environ.get("ARMS_B", "S1 G1").replace(",", " ").split())
SEEDS = tuple(int(x) for x in os.environ.get("SEEDS", "1 2 3 4 5").replace(",", " ").split())
NBIN = int(os.environ.get("NBIN", "5"))
#: ADR 0240 §3's published per-stem mass departures, and the tolerance panel 0 gates on.
PUB_DPER = {"S1": 0.96, "G1": 2.69}
GATE_DPER = 0.60
#: STATE §B step 1's pre-registered boundaries on `share = dPER_matched / dPER`.
SHARE_STRUCTURE = 0.25
SHARE_REAL = 0.60

DUMP_RE = re.compile(r"^S_r2s_(\w+?)_c(\d+)_(REC|S0|S0h|S1|G0|G0h|G1)_" + NPREV + r"_s(\d+)_dump$")


def only_cells():
    v = os.environ.get("CELLS", "").strip()
    return {int(x) for x in v.split(",") if x} if v else None


def quantile_edges(vals, nbin):
    """-> the nbin-1 interior cut points of `vals`, as plain order statistics."""
    v = sorted(vals)
    n = len(v)
    return [v[max(0, min(n - 1, int(round(i * n / nbin))))] for i in range(1, nbin)]


def bin_of(x, edges):
    b = 0
    while b < len(edges) and x >= edges[b]:
        b += 1
    return b


def scan_terminal(path: str, year: int):
    """-> [(patch, age, height, w)] for the `grow` roster of `year`, height > 5 m.

    Prefilters on the year token before splitting (81x fewer splits on an ssp370 leg); the token
    test is a SUPERSET filter -- an integer field such as `treeidx` can carry the same token -- and
    the exact field is confirmed after the split, so the prefilter can only cost time, never rows.
    """
    tok = f" {year} "
    out = []
    tcols = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#H T"):
                tcols = {n: i + 1 for i, n in enumerate(line.split()[2:])}
                continue
            if not line.startswith("T grow "):
                continue
            if tok not in line:
                continue
            if tcols is None:
                raise SystemExit(f"{path}: a T record before its '#H T' header")
            f = line.split()
            if int(f[tcols["year"]]) != year:
                continue
            h = float(f[tcols["height"]])
            if h <= HEIGHT_MIN:
                continue
            w = (float(f[tcols["leaf_c"]]) + float(f[tcols["sapwood_c"]])
                 + float(f[tcols["heartwood_c"]]) - float(f[tcols["debt_c"]]))
            out.append((int(f[tcols["patch"]]), float(f[tcols["age"]]), h, w))
    return out


def collect():
    """-> {(cell, arm, seed): [stems]} at the terminal year, plus the NAMED exclusions."""
    keep = only_cells()
    year = TERMINAL_YEAR[SCEN]
    got, excluded = {}, []
    for d in sorted(glob.glob(os.path.join(ROOT, f"S_r2s_{SCEN}_*_dump"))):
        m = DUMP_RE.match(os.path.basename(d))
        if not m or m.group(1) != SCEN:
            continue
        cell, arm, seed = int(m.group(2)), m.group(3), int(m.group(4))
        if arm != "REC" and (arm not in ARMS_B or seed not in SEEDS):
            continue
        if arm == "REC" and seed != 1:
            continue
        if keep is not None and cell not in keep:
            continue
        f = os.path.join(d, "roster_rank0000.txt")
        if not os.path.exists(f) or not run_completed(SCEN, cell, arm, NPREV, seed):
            excluded.append((cell, arm, seed, "missing dump or no C completion line"))
            continue
        stems = scan_terminal(f, year)
        patches = {p for p, _a, _h, _w in stems}
        if not stems:
            excluded.append((cell, arm, seed, f"no emitted stems at {year}"))
            continue
        got[(cell, arm, seed)] = stems
        print(f"    {arm:4s} c{cell:<6d} s{seed}  {len(stems):6d} stems in "
              f"{len(patches)}/{NPATCH} patches", flush=True)
    return got, excluded


def matched(ref, arm, idx, nbin):
    """Direct standardisation of the arm's per-stem mass onto FIT's own bin distribution.

    `idx` picks the matching axis out of a stem tuple (1 = age, 2 = height).
    -> (w_ref, w_arm, w_arm_matched, covered_share, per-bin table).
    """
    edges = quantile_edges([s[idx] for s in ref], nbin)
    rb = defaultdict(list)
    ab = defaultdict(list)
    for s in ref:
        rb[bin_of(s[idx], edges)].append(s[3])
    for s in arm:
        ab[bin_of(s[idx], edges)].append(s[3])
    n_ref = len(ref)
    covered = sum(len(rb[b]) for b in rb if ab.get(b))
    if covered == 0:
        return None
    num = sum((len(rb[b]) / covered) * mean(ab[b]) for b in rb if ab.get(b))
    table = []
    for b in sorted(set(rb) | set(ab)):
        table.append((b,
                      len(rb.get(b, [])) / n_ref if n_ref else float("nan"),
                      len(ab.get(b, [])) / len(arm) if arm else float("nan"),
                      mean(rb[b]) if rb.get(b) else float("nan"),
                      mean(ab[b]) if ab.get(b) else float("nan")))
    return mean([s[3] for s in ref]), mean([s[3] for s in arm]), num, covered / n_ref, table


def main():
    print("=" * 100)
    print("diagnose_rung2_perstem_mass_decomp — IS THE PER-STEM MASS EXCESS THERE AT MATCHED "
          "AGE/HEIGHT?")
    print(f"  scenario={SCEN}  terminal year={TERMINAL_YEAR[SCEN]}  NPREV={NPREV}  "
          f"arms={ARMS_B}  seeds={SEEDS}  nbin={NBIN}")
    print(f"  pre-registered: share < {SHARE_STRUCTURE} STRUCTURE · "
          f"share > {SHARE_REAL} REAL · between = tie to be named")
    print("=" * 100)
    print("\n  -- dumps --", flush=True)
    got, excluded = collect()
    if excluded:
        print("\n  EXCLUDED (named, dump-skill trap 2):")
        for e in excluded:
            print(f"    c{e[0]} {e[1]} s{e[2]}: {e[3]}")
    if not got:
        raise SystemExit("no scoreable legs")

    nliving = read_nliving(NLIVING)
    cells = sorted({c for (c, _a, _s) in got})
    gain = [c for c in cells if nliving.get(c, 0.0) > 0]
    print(f"\n  cells scanned: {len(cells)}   FIT-GAIN subset ({len(gain)}): {gain}")

    # pool seeds per (cell, arm)
    pooled = defaultdict(list)
    for (c, a, _s), v in got.items():
        pooled[(c, a)].extend(v)

    # ---------------- panel 0: the basis gate ----------------
    print("\n" + "=" * 100)
    print("P0  BASIS GATE — the dump-derived dPER must reproduce ADR 0240 §3's published value")
    print("    dPER = mean per-stem mass (arm) / mean per-stem mass (REC) - 1, FIT-gain cells,")
    print("    median over cells. w = leaf_c + sapwood_c + heartwood_c - debt_c (see the header).")
    print("=" * 100)
    print(f"  {'arm':<5} {'dPER (dumps)':>13} {'published':>10} {'|d|':>8}  verdict")
    dper = {}
    gate_ok = True
    for arm in ARMS_B:
        v = []
        for c in gain:
            r, a = pooled.get((c, "REC")), pooled.get((c, arm))
            if not r or not a:
                continue
            wr = mean([s[3] for s in r])
            if wr:
                v.append(mean([s[3] for s in a]) / wr - 1.0)
        if not v:
            continue
        dper[arm] = median(v)
        pub = PUB_DPER.get(arm, float("nan"))
        d = abs(dper[arm] - pub)
        ok = d <= GATE_DPER
        gate_ok = gate_ok and ok
        print(f"  {arm:<5} {dper[arm]:>+13.1%} {pub:>+10.1%} {d:>8.2f}  "
              f"{'PASS' if ok else 'FAIL'}")
    print(f"  tolerance |d| <= {GATE_DPER} (the dump `w` omits `excess` and `turn_litt.leaf`).")
    print("  " + ("⇒ the basis reproduces; read on."
                  if gate_ok else "⇒ ⚠ BASIS ERROR — the matched numbers below are not on "
                                  "ADR 0240's basis."))

    # ---------------- panels 1-2: the matched decomposition ----------------
    for axis, idx in (("AGE", 1), ("HEIGHT", 2)):
        print("\n" + "=" * 100)
        print(f"P1{'a' if idx == 1 else 'b'}  MATCHED-{axis} DECOMPOSITION "
              f"({NBIN} bins on FIT's own terminal stand at each cell)")
        print("=" * 100)
        print(f"  {'arm':<5} {'cell':>7} {'w_REC':>9} {'w_arm':>9} {'w_match':>9} | "
              f"{'dPER':>8} {'dPER_m':>8} {'share':>7} | {'covered':>8}")
        for arm in ARMS_B:
            shares, cov = [], []
            for c in gain:
                r, a = pooled.get((c, "REC")), pooled.get((c, arm))
                if not r or not a:
                    continue
                res = matched(r, a, idx, NBIN)
                if res is None:
                    continue
                wr, wa, wm, cvd, _tab = res
                if not wr:
                    continue
                dp, dm = wa / wr - 1.0, wm / wr - 1.0
                sh = dm / dp if dp else float("nan")
                shares.append(sh)
                cov.append(cvd)
                print(f"  {arm:<5} {c:>7} {wr:9.0f} {wa:9.0f} {wm:9.0f} | "
                      f"{dp:>+8.1%} {dm:>+8.1%} {sh:>7.3f} | {cvd:>8.1%}")
            if shares:
                print(f"  {arm:<5} {'MEDIAN':>7} {'':9} {'':9} {'':9} | "
                      f"{dper.get(arm, float('nan')):>+8.1%} {'':8} "
                      f"{median(shares):>7.3f} | {median(cov):>8.1%}")
                s = median(shares)
                verd = ("STRUCTURE consequence" if s < SHARE_STRUCTURE
                        else "REAL per-stem effect (a disclosure, not an operator defect)"
                        if s > SHARE_REAL else "IN BETWEEN — name the tie-breaker")
                print(f"        ⇒ {arm} matched-{axis.lower()} share = {s:.3f}  ⇒ {verd}")

    # ---------------- panel 3: the full height-quintile profile ----------------
    print("\n" + "=" * 100)
    print("P2  THE FULL PROFILE BY HEIGHT QUINTILE OF FIT's OWN TERMINAL STAND (ADR 0187's rule)")
    print("    A COMPOSITION effect moves the stem SHARES and leaves the per-bin mean mass alone;")
    print("    a real per-stem effect LIFTS the per-bin means. `ratio` = arm mean / REC mean.")
    print("=" * 100)
    for arm in ARMS_B:
        print(f"\n  --- {arm} vs REC, FIT-gain cells, per-cell profiles then the median row ---")
        print(f"  {'q':>2} | {'REC share':>10} {'arm share':>10} | {'REC w':>10} {'arm w':>10} "
              f"{'ratio':>7}")
        acc = defaultdict(lambda: defaultdict(list))
        for c in gain:
            r, a = pooled.get((c, "REC")), pooled.get((c, arm))
            if not r or not a:
                continue
            res = matched(r, a, 2, NBIN)
            if res is None:
                continue
            for b, rs, as_, rw, aw in res[4]:
                acc[b]["rs"].append(rs)
                acc[b]["as"].append(as_)
                if rw == rw:
                    acc[b]["rw"].append(rw)
                if aw == aw:
                    acc[b]["aw"].append(aw)
                if rw == rw and aw == aw and rw:
                    acc[b]["ratio"].append(aw / rw)
        for b in sorted(acc):
            g = acc[b]
            print(f"  {b + 1:>2} | {median(g['rs']) if g['rs'] else float('nan'):>10.3f} "
                  f"{median(g['as']) if g['as'] else float('nan'):>10.3f} | "
                  f"{median(g['rw']) if g['rw'] else float('nan'):>10.0f} "
                  f"{median(g['aw']) if g['aw'] else float('nan'):>10.0f} "
                  f"{median(g['ratio']) if g['ratio'] else float('nan'):>7.2f}")
    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
