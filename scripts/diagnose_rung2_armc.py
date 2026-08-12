#!/usr/bin/env python3
"""Score the rung-2 ARM C arms against the LPJmL-FIT C truth (line M; ADR 0117's option-(c) interface).

WHAT IS BEING MEASURED
----------------------
`scripts/rung2_armc_harness.jl` runs two arms of the substituted mortality interface:

    C0   f_i = rho for every tree            — the shipped uniform thinning = the NO-SELECTION NULL
    C1   f_i = (1 - mort_i)^theta            — the count target pinned, the ported hazard sets who dies

`C1 - C0` is the measurement.  ADR 0046 decomposed FIT's warming trait shift as 22.2 % composition /
51.3 % within-PFT / 26.6 % interaction, with the within-PFT part +112 % WITHIN-AGE-CLASS; traits are
immutable after `new_tree`, so a shift at fixed PFT and fixed age can only be differential survival.
This script asks whether the substituted operator reproduces that, on the two statistics ADR 0118 §3
names: the per-PFT AGE-WOODDENS GRADIENT (its SHAPE, not just its level) and the realized selection
differential.

THREE THINGS IT REFUSES TO CONFLATE
-----------------------------------
1. **A single seed is not an observable.**  The decision is a Bernoulli draw and the C's own two runs
   disagree on the sign of a per-cell trait response in 33-37 % of cells (ADR 0106).  So every arm is
   scored as a SEED ENSEMBLE and the across-seed spread is printed beside the mean.  An arm with one
   seed is reported as such and its difference from another arm is not called a result.
2. **The gradient at this cell is not the global gradient.**  `test/testitems/references/
   S_age_wooddens_gradient.csv` is FIT's gradient over all 54 020 cells; cell 42490 (Hainich) carries
   only PFT ids 1-5 and its own age structure.  The like-for-like reference is therefore the RECORDED
   baseline dump of the same cell, and the global fixture is used only for the SHAPE question (does the
   arm reproduce the sign pattern of the bin-to-bin steps, including a non-monotone PFT).
3. **Counts and traits are different questions.**  Terminal stem count is reported first and separately:
   an arm that reproduces the gradient while losing half the stand has not reproduced FIT.

USAGE
    python3 scripts/diagnose_rung2_armc.py [--recorded DIR] [--arm TAG=DIR ...] [--csv PATH]

With no `--arm`, every `/p/tmp/jamirp/M_rung2/M_r2armc_*_dump` present is scored, grouped by arm+rho.
Exit 0 always: this is a measurement, not a gate (the gate is the theta=1 identity in
`test/testitems/m_rung2_hazard_identity_tests.jl`).
"""

from __future__ import annotations

import argparse
import glob
import math
import os
import re
import sys
from collections import defaultdict

#: FIXED age-bin edges (years), identical to scripts/build_age_wooddens_gradient_reference.py::AGE_EDGES
#: and diagnose_wooddens_shift_decomposition.py. Fixed edges are what makes two populations comparable
#: bin-by-bin; quantile bins would not be.
AGE_EDGES = [10.0, 20.0, 40.0, 80.0, 160.0, 320.0]

#: Terminal year of the harness runs, and the COARSE age bins the terminal age structure is reported on.
#: The three coarse bins are chosen against the run length, not for symmetry: 20 years is exactly the
#: window, so `<20` is the cohort the arm BUILT, `20-40` is a cohort the arm carried through, and `>=40`
#: is the mature stand that was present in the shared spin-up restart. Reading them separately is what
#: separates "the arm grew the wrong trees" from "the arm destroyed the trees it was given".
LASTYEAR = 2019
COARSE_EDGES = [20.0, 40.0]


def COARSE_BIN(age: float) -> int:
    return sum(1 for e in COARSE_EDGES if age >= e)


COARSE_LABEL = ("<20 (built by the arm)", "20-40 (carried through)", ">=40 (from the restart)")

REC_DEFAULT = "/p/tmp/jamirp/M_rung2/M_rung2rec_v5_dump"
#: The dump-naming conventions this scorer can group into arm+variant/seed on its own.  Arm C (line M,
#: ADR 0124) and the line-S arm (ADR 0175) write the same roster-dump schema from different harnesses,
#: so the SCORING is shared and only the discovery differs.  ⚠ Each arm family has its own recorded
#: baseline and they are NOT interchangeable — arm C's is a v5 dump, the S arm's is v6 — so pass
#: `--glob` plus the matching `--recorded` rather than scoring both families in one table.
ARM_GLOBS = (
    ("/p/tmp/jamirp/M_rung2/M_r2armc_*_dump", r"M_r2armc_(C[01])_([a-z]+)_s(\d+)_dump$"),
    ("/p/tmp/jamirp/S_rung2/S_r2s_*_dump", r"S_r2s_(S0h|S0|S1|NP)_([a-z]+)_s(\d+)_dump$"),
)
GLOBAL_FIXTURE = "test/testitems/references/S_age_wooddens_gradient.csv"


def agebin(age: float) -> int:
    return sum(1 for e in AGE_EDGES if age >= e)


def bin_label(b: int) -> str:
    lo = 0.0 if b == 0 else AGE_EDGES[b - 1]
    hi = AGE_EDGES[b] if b < len(AGE_EDGES) else float("inf")
    return f"{lo:g}-{hi:g}"


def read_dump(path: str):
    """Stream one roster dump into the per-survivor statistics this script needs.

    Reads the `mort` phase, which is where the demographic verdict is settled: `isdead` there is the
    demography's own answer, while a `post`-phase `isdead` also contains FIRE's victims (fire runs after
    the decision point and also sets the flag — the mistake ADR 0121 had to correct).  Survivors only
    (`isdead == 0`), matching the reference builder.

    Self-describing: the '#H T' line carries the column names.
    """
    cols = None
    # gradient accumulators: (pft_id, agebin) -> [n, sum_age, sum_wd, sum_sla]
    grad: dict[tuple[int, int], list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    # terminal-year roster: year -> alive stem count (all patches)
    alive: dict[int, int] = defaultdict(int)
    # terminal-year AGE STRUCTURE: bin -> alive stem count, and the survivor identities per coarse bin.
    # Reported because it turned out to be the null arm's largest departure: an operator can honour the
    # count target every single patch-year and still hand back a young stand where FIT has a mature one,
    # and no count statistic sees it.
    term_bins: dict[int, int] = defaultdict(int)
    term_ids: dict[int, set] = defaultdict(set)
    # the one-year selection differential, hazard-free: mean wooddens of the DEAD minus the stand mean,
    # nind-weighted over every patch-year.  This is what the arm actually did, not what it intended.
    d_num = d_den = s_num = s_den = 0.0
    have_grow = False
    for line in open(path):
        if line.startswith("#H T "):
            cols = {n: i for i, n in enumerate(line.split()[2:])}
            continue
        if not line or line[0] != "T":
            continue
        if cols is None:
            sys.exit(f"FATAL: {path}: a T record before its '#H T' header")
        f = line.split()[1:]
        ph = f[cols["phase"]]
        if ph == "grow":
            have_grow = True
        if ph != "mort":
            continue
        isdead = int(f[cols["isdead"]])
        year = int(f[cols["year"]])
        nind = float(f[cols["nind"]])
        wd = float(f[cols["wooddens"]])
        if isdead:
            d_num += nind * wd
            d_den += nind
        else:
            alive[year] += 1
            age = float(f[cols["age"]])
            g = grad[(int(f[cols["pft_id"]]), agebin(age))]
            g[0] += 1
            g[1] += age
            g[2] += wd
            g[3] += float(f[cols["sla"]])
            if year == LASTYEAR:
                b = COARSE_BIN(age)
                term_bins[b] += 1
                term_ids[b].add(
                    (int(f[cols["patch"]]), int(f[cols["pft_id"]]), int(f[cols["treeidx"]]))
                )
        s_num += nind * wd
        s_den += nind
    if not have_grow:
        sys.exit(
            f"FATAL: {path} has no `grow` dump phase — it predates the rendezvous move behind the "
            "growth loop (ADR 0123) and its roster is a year stale in bm_inc_counter. Re-record it."
        )
    sel = (d_num / d_den - s_num / s_den) if d_den > 0 and s_den > 0 else float("nan")
    return {
        "grad": grad, "alive": dict(alive), "sel_diff": sel, "n_dead": d_den,
        "term_bins": dict(term_bins), "term_ids": dict(term_ids),
    }


def read_harness_log(dump_dir: str):
    """theta / rho / shortfall statistics from the harness's own per-patch-year log.

    The log lives in the APPLY dir beside the dump; `theta` is NaN for C0 by construction (there is no
    tilt to solve), which is why it is reported as "n/a" rather than 0.
    """
    apply_dir = dump_dir[: -len("_dump")] + "_apply"
    path = next(
        (
            p
            for p in (
                os.path.join(apply_dir, n) for n in ("armc_log.txt", "s_arm_log.txt")
            )
            if os.path.exists(p)
        ),
        None,
    )
    if path is None:
        return None
    thetas, rhos, sf, dr = [], [], [], []
    n_kill = n_tree = 0
    col = None
    for line in open(path):
        if line.startswith("#H L "):
            # PARSE THE HEADER, never the position.  The two harnesses that write this file do NOT
            # share a column order — arm C's row 4 is `rho` while the S arm's row 4 is `n_emit` — so a
            # positional reader silently scores one arm on another's columns.  That is the same class
            # of basis bug as the three the S arm's first run exposed (ADR 0175); the `#H L` line is
            # written by both harnesses precisely so it never has to be guessed.  The data rows lead
            # with the literal "L", so a name's field index is its header position + 1.
            col = {n: i + 1 for i, n in enumerate(line.split()[2:])}
            continue
        if not line.startswith("L "):
            continue
        if col is None:
            sys.exit(f"FATAL: {path}: an L record before its '#H L' header")
        f = line.split()
        rhos.append(float(f[col["rho"]]))
        th = float(f[col["theta"]])
        if not math.isnan(th):
            thetas.append(th)
        sf.append(float(f[col["shortfall"]]))
        n_kill += int(f[col["n_kill"]])
        n_tree += int(f[col["n_tree"]])
        # `sel_diff` is arm C's own per-patch-year drawn selection differential; the S arm's log does
        # not carry it (its differential is recomputed from the dump instead), so it stays empty.
        if "sel_diff" in col:
            d = float(f[col["sel_diff"]])
            if not math.isnan(d):
                dr.append(d)
    return {"theta": thetas, "rho": rhos, "shortfall": sf, "n_kill": n_kill, "sel_drawn": dr}


def read_audit(dump_dir: str):
    """The C's OWN accounting of the rendezvous: what its hazard wanted vs what was applied.

    `n_kill_c` is the number of deaths the C's own `mortality_tree_ind` chose on the SAME roster the
    harness was shown, so `n_kill_applied` vs `n_kill_c` is a free, live check that a theta=1 arm is
    reproducing FIT rather than merely agreeing with it in the mean.  `n_forced_dead` is the C's
    non-negotiable kills (negative pools, `isneg_tree`, the bioclimatic `survive()`, `cut_year`) — the
    part of mortality the interface does NOT own, and it must be disclosed with any arm number.
    `n_spared_certain` counts trees the arm kept alive that the C was certain of.
    """
    apply_dir = dump_dir[: -len("_dump")] + "_apply"
    path = os.path.join(apply_dir, "audit_r0000.txt")
    if not os.path.exists(path):
        return None
    tot = dict(n_pre=0, n_kill_c=0, n_kill_applied=0, n_forced_dead=0, n_spared_certain=0)
    for line in open(path):
        if not line.startswith("A "):
            continue
        f = line.split()
        tot["n_pre"] += int(f[3])
        tot["n_kill_c"] += int(f[4])
        tot["n_kill_applied"] += int(f[5])
        tot["n_forced_dead"] += int(f[6])
        tot["n_spared_certain"] += int(f[7])
    return tot


def read_global_fixture(repo: str):
    """FIT's global per-PFT age-wooddens gradient (historic block), for the SHAPE comparison only."""
    path = os.path.join(repo, GLOBAL_FIXTURE)
    if not os.path.exists(path):
        return None
    out: dict[int, dict[int, float]] = defaultdict(dict)
    hdr = None
    for line in open(path):
        if line.startswith("#"):
            continue
        f = line.rstrip("\n").split(",")
        if hdr is None:
            hdr = {n: i for i, n in enumerate(f)}
            continue
        if f[hdr["scenario"]] != "historic":
            continue
        out[int(f[hdr["pft_id"]])][int(f[hdr["agebin"]])] = float(f[hdr["wooddens_mean"]])
    return out


def spearman(x, y):
    n = len(x)
    if n < 3:
        return float("nan")

    def rank(v):
        order = sorted(range(n), key=lambda i: v[i])
        rk = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                rk[order[k]] = avg
            i = j + 1
        return rk

    rx, ry = rank(x), rank(y)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return float("nan") if den == 0 else num / den


def gradient_table(grad, min_n: int = 30):
    """(pft_id -> {agebin: mean wooddens}) for bins with enough stems to mean anything."""
    out: dict[int, dict[int, float]] = defaultdict(dict)
    for (pid, b), (n, _sa, swd, _ss) in grad.items():
        if n >= min_n:
            out[pid][b] = swd / n
    return out


def gradient_span(tab: dict[int, float]):
    """The gradient's LEVEL summary: youngest populated bin -> oldest populated bin."""
    if len(tab) < 2:
        return float("nan")
    bs = sorted(tab)
    return tab[bs[-1]] - tab[bs[0]]


def mean_sd(v):
    if not v:
        return float("nan"), float("nan")
    m = sum(v) / len(v)
    if len(v) < 2:
        return m, float("nan")
    return m, math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))


def main() -> int:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--recorded", default=REC_DEFAULT, help="the RECORDED baseline dump (C truth, same cell)")
    ap.add_argument("--arm", action="append", default=[], help="TAG=DUMPDIR (repeatable); default: glob")
    ap.add_argument(
        "--glob", action="append", default=[],
        help="substring selecting which arm FAMILY to auto-discover (e.g. S_rung2); default: all",
    )
    ap.add_argument("--csv", default="", help="write the per-arm gradient table here")
    args = ap.parse_args()

    def dumpfile(d):
        fs = sorted(glob.glob(os.path.join(d, "roster_rank*.txt")))
        if not fs:
            sys.exit(f"FATAL: no roster_rank*.txt under {d}")
        if len(fs) > 1:
            sys.exit(f"FATAL: {d} holds {len(fs)} rank files; this cell ran on one task")
        return fs[0]

    print("rung-2 ARM C — substituted mortality vs the LPJmL-FIT C truth")
    print("  cell 42490 (Hainich), 25 patches, 2000-2019, ONE cell of 54 020")
    print("  establishment stays with the C in every arm (the recruits half has a 0.907 replay floor)")
    print("  recorded baseline:", args.recorded)
    print()

    rec = read_dump(dumpfile(args.recorded))

    # collect the arms, grouped as arm+rho -> {seed: dump dir}
    arms: dict[str, dict[int, str]] = defaultdict(dict)
    if args.arm:
        for spec in args.arm:
            tag, _, d = spec.partition("=")
            arms[tag][0] = d
    else:
        families = [
            (g, rx) for g, rx in ARM_GLOBS if not args.glob or any(s in g for s in args.glob)
        ]
        for g, rx in families:
            for d in sorted(glob.glob(g)):
                m = re.search(rx, os.path.basename(d))
                if m is None:
                    continue
                arms[f"{m.group(1)}/{m.group(2)}"][int(m.group(3))] = d
    if not arms:
        sys.exit(f"FATAL: no arm dumps matched {[g for g, _ in ARM_GLOBS]}")

    results: dict[str, dict] = {}
    for tag in sorted(arms):
        seeds = arms[tag]
        per_seed = {s: read_dump(dumpfile(d)) for s, d in sorted(seeds.items())}
        logs = {s: read_harness_log(d) for s, d in sorted(seeds.items())}
        audits = {s: read_audit(d) for s, d in sorted(seeds.items())}
        results[tag] = {"dumps": per_seed, "logs": logs, "audits": audits, "seeds": sorted(seeds)}

    rec_terminal = rec["alive"].get(max(rec["alive"]), 0)
    print("=" * 100)
    print("1. COUNTS — terminal stems in 2019 (survivors, all 25 patches).  Traits are meaningless if")
    print("   the stand is not there; this is reported first and separately.")
    print(f"   the C itself (recorded): {rec_terminal}")
    print()
    print(f"   {'arm':14s} {'seeds':>5s} {'terminal stems (per seed)':38s} {'mean':>8s} {'sd':>7s} {'ratio to C':>11s}")
    for tag in sorted(results):
        r = results[tag]
        vals = [float(r["dumps"][s]["alive"].get(max(r["dumps"][s]["alive"]), 0)) for s in r["seeds"]]
        m, sd = mean_sd(vals)
        per = " ".join(f"{int(v)}" for v in vals)
        print(
            f"   {tag:14s} {len(vals):5d} {per:38s} {m:8.1f} "
            f"{('n/a' if math.isnan(sd) else f'{sd:7.1f}'):>7s} {m / rec_terminal:11.3f}"
        )
    print()

    print("=" * 100)
    print(f"1b. AGE STRUCTURE in {LASTYEAR} — the statistic no count target sees.  An operator can honour")
    print("    the count target in every single patch-year and still hand back a young stand where FIT")
    print("    has a mature one.  `shared` is how many of the C's OWN survivors the arm still holds by")
    print("    identity (patch, pft_id, treeidx) — a trait gradient built on a stand of different trees")
    print("    is not the same measurement as one built on the same trees.")
    print()
    hdr = "    " + f"{'arm':14s} {'seed':>4s} " + " ".join(f"{lbl:>26s}" for lbl in COARSE_LABEL)
    print(hdr)
    rc = rec["term_bins"]
    ri = rec["term_ids"]
    print(
        "    " + f"{'the C itself':14s} {'-':>4s} "
        + " ".join(f"{rc.get(b, 0):>26d}" for b in range(len(COARSE_EDGES) + 1))
    )
    for tag in sorted(results):
        for s in results[tag]["seeds"]:
            d = results[tag]["dumps"][s]
            cells = []
            for b in range(len(COARSE_EDGES) + 1):
                n = d["term_bins"].get(b, 0)
                sh = len(d["term_ids"].get(b, set()) & ri.get(b, set()))
                cells.append(f"{n:5d} (shared {sh:4d}/{rc.get(b, 0):4d})")
            print("    " + f"{tag:14s} {s:4d} " + " ".join(f"{c:>26s}" for c in cells))
    print()

    print("=" * 100)
    print("2. THE INTERFACE, LIVE — the C's own audit of each rendezvous (summed over 500 patch-years).")
    print("   `kill_c` is what the C's own mortality_tree_ind chose on the SAME roster the arm was shown,")
    print("   so kill_applied/kill_c is a live check that a theta=1 arm reproduces FIT rather than merely")
    print("   matching it in the mean.  `forced` = the C's non-negotiable kills (negative pools,")
    print("   isneg_tree, the bioclimatic survive(), cut_year) — mortality the interface does NOT own.")
    print()
    print(f"   {'arm':14s} {'seed':>4s} {'n_pre':>7s} {'kill_c':>7s} {'applied':>8s} {'app/kill_c':>10s} {'forced':>7s} {'spared_certain':>15s}")
    for tag in sorted(results):
        for s in results[tag]["seeds"]:
            a = results[tag]["audits"][s]
            if a is None:
                continue
            ratio = a["n_kill_applied"] / a["n_kill_c"] if a["n_kill_c"] else float("nan")
            print(
                f"   {tag:14s} {s:4d} {a['n_pre']:7d} {a['n_kill_c']:7d} {a['n_kill_applied']:8d} "
                f"{ratio:10.3f} {a['n_forced_dead']:7d} {a['n_spared_certain']:15d}"
            )
    print()

    print("=" * 100)
    print("3. THE TILT — theta beside the result, as ADR 0117 item 6.i requires.  theta = 1 means FIT's")
    print("   own hazard and the count target agree; theta -> 0 means the count target left the selection")
    print("   no room, and a null C1 - C0 then says nothing about selection.  `shortfall` is the relative")
    print("   count MISS in a patch-year where no theta could reach the target (hard kills alone overshoot).")
    print()
    print(f"   {'arm':14s} {'seed':>4s} {'theta med':>10s} {'theta p05':>10s} {'theta p95':>10s} {'theta>0.5':>10s} {'shortfall>0':>12s}")
    for tag in sorted(results):
        for s in results[tag]["seeds"]:
            lg = results[tag]["logs"][s]
            if lg is None:
                continue
            th = sorted(lg["theta"])
            nsf = sum(1 for x in lg["shortfall"] if x > 0)
            if not th:
                print(f"   {tag:14s} {s:4d} {'n/a (C0 has no tilt to solve)':>44s} {nsf:12d}")
                continue

            def q(f):
                return th[min(max(int(round(f * (len(th) - 1))), 0), len(th) - 1)]

            print(
                f"   {tag:14s} {s:4d} {q(0.5):10.4f} {q(0.05):10.4f} {q(0.95):10.4f} "
                f"{sum(1 for x in th if x > 0.5):10d} {nsf:12d}"
            )
    print()

    print("=" * 100)
    print("4. SELECTION, REALIZED — mean wood density of the trees that DIED minus the stand mean")
    print("   (gC/m3, nind-weighted over every patch-year).  Positive = denser wood dies more, the sign")
    print("   of ADR 0046 §3.  This is what the arm DID, not what its hazard intended.")
    print()
    print(f"   the C itself (recorded): {rec['sel_diff']:+9.1f}")
    print(f"   {'arm':14s} {'seeds':>5s} {'mean':>10s} {'sd':>9s} {'ratio to C':>11s}")
    for tag in sorted(results):
        r = results[tag]
        vals = [r["dumps"][s]["sel_diff"] for s in r["seeds"] if not math.isnan(r["dumps"][s]["sel_diff"])]
        m, sd = mean_sd(vals)
        print(
            f"   {tag:14s} {len(vals):5d} {m:10.1f} "
            f"{('n/a' if math.isnan(sd) else f'{sd:9.1f}'):>9s} {m / rec['sel_diff']:11.3f}"
        )
    print()

    print("=" * 100)
    print("5. THE AGE-WOODDENS GRADIENT — the ID-free acceptance target (ADR 0046 §3 / ADR 0118 §3).")
    print("   Per PFT, mean survivor wood density by age bin, pooled over all seeds and all 20 years.")
    print("   SHAPE is scored two ways: Spearman rho of the bin means against the same PFT's bins in the")
    print("   recorded baseline of THIS cell (the like-for-like reference), and against FIT's GLOBAL")
    print("   fixture (a different population - 54 020 cells - so only its shape is comparable).")
    print()
    rec_tab = gradient_table(rec["grad"])
    glob_tab = read_global_fixture(repo) or {}
    csv = open(args.csv, "w") if args.csv else None
    if csv:
        print("arm,pft_id,agebin,age_lo,age_hi,n,wooddens_mean", file=csv)
        for pid in sorted({k[0] for k in rec["grad"]}):
            for b in range(len(AGE_EDGES) + 1):
                g = rec["grad"].get((pid, b))
                if g and g[0] > 0:
                    lo = 0.0 if b == 0 else AGE_EDGES[b - 1]
                    hi = AGE_EDGES[b] if b < len(AGE_EDGES) else float("inf")
                    print(f"recorded,{pid},{b},{lo:g},{hi:g},{int(g[0])},{g[2] / g[0]:.17g}", file=csv)

    for tag in sorted(results):
        r = results[tag]
        pooled: dict[tuple[int, int], list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
        for s in r["seeds"]:
            for k, v in r["dumps"][s]["grad"].items():
                for i in range(4):
                    pooled[k][i] += v[i]
        tab = gradient_table(pooled, min_n=30 * len(r["seeds"]))
        print(f"   --- {tag}  ({len(r['seeds'])} seed(s) pooled)")
        print(
            f"       {'pft':>3s} {'bins':>4s} " + " ".join(f"{bin_label(b):>10s}" for b in range(len(AGE_EDGES) + 1))
            + f" {'span':>9s} {'rho(cell)':>9s} {'rho(glob)':>9s}"
        )
        for pid in sorted(tab):
            row = tab[pid]
            cells = " ".join(f"{row[b]:10.0f}" if b in row else f"{'-':>10s}" for b in range(len(AGE_EDGES) + 1))
            common = sorted(set(row) & set(rec_tab.get(pid, {})))
            rho_c = spearman([row[b] for b in common], [rec_tab[pid][b] for b in common]) if len(common) >= 3 else float("nan")
            gcommon = sorted(set(row) & set(glob_tab.get(pid, {})))
            rho_g = spearman([row[b] for b in gcommon], [glob_tab[pid][b] for b in gcommon]) if len(gcommon) >= 3 else float("nan")
            print(
                f"       {pid:3d} {len(row):4d} {cells} {gradient_span(row):9.0f} "
                f"{rho_c:9.3f} {rho_g:9.3f}"
            )
            if csv:
                for b in sorted(row):
                    n = pooled[(pid, b)][0]
                    lo = 0.0 if b == 0 else AGE_EDGES[b - 1]
                    hi = AGE_EDGES[b] if b < len(AGE_EDGES) else float("inf")
                    print(f"{tag},{pid},{b},{lo:g},{hi:g},{int(n)},{row[b]:.17g}", file=csv)
        print()

    print("   --- the C itself (recorded baseline, same cell)")
    print(
        f"       {'pft':>3s} {'bins':>4s} " + " ".join(f"{bin_label(b):>10s}" for b in range(len(AGE_EDGES) + 1))
        + f" {'span':>9s} {'rho(glob)':>9s}"
    )
    for pid in sorted(rec_tab):
        row = rec_tab[pid]
        cells = " ".join(f"{row[b]:10.0f}" if b in row else f"{'-':>10s}" for b in range(len(AGE_EDGES) + 1))
        gcommon = sorted(set(row) & set(glob_tab.get(pid, {})))
        rho_g = spearman([row[b] for b in gcommon], [glob_tab[pid][b] for b in gcommon]) if len(gcommon) >= 3 else float("nan")
        print(f"       {pid:3d} {len(row):4d} {cells} {gradient_span(row):9.0f} {rho_g:9.3f}")
    if csv:
        csv.close()
        print()
        print("   gradient table written:", args.csv)
    print()
    print("SCOPE, mandatory with any number above: ONE cell of 54 020; establishment deferred to the C;")
    print("the C binary DEFERS its demographic kills under either rung-2 env var, a reorder worth 0.05 %")
    print("of stem-years over 20 yr (ADR 0123) — two orders of magnitude below this model's smallest")
    print("noise floor (11.3 % bootstrap CV on vegc at npatch=25), but a departure from stock LPJmL-FIT.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
