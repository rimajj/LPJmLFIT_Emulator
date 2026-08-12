#!/usr/bin/env python3
"""diagnose_rung2_response.py — score the rung-2 WARMING RESPONSE: does the learned demography move the
right way, and by the right amount, when the climate warms?

THE MEASUREMENT.  For every cell, both scenario legs are run under the SAME demography, and what is
scored is the CHANGE between them against FIT's own change at that cell:

    response(arm, cell) = terminal(arm, ssp370) - terminal(arm, historic)
    truth(cell)         = terminal(REC, ssp370) - terminal(REC, historic)

Per-cell baselines, never the global ground truth: ADR 0041 showed a single-cell re-run is a
different trajectory from the same cell inside the 67 420-cell run, so scoring against the global
truth would charge the decomposition difference to the arm.

WHY A RATIO OF DIFFERENCES IS REPORTED PER CELL AND NEVER POOLED AS A MEAN (ADR 0174 §3d)
------------------------------------------------------------------------------------------
Cells respond in BOTH directions — FIT itself thins under warming at most of the biome cells but the
tropical cell gains stems.  A pooled mean over heterogeneous cells CANCELS, so an emulator with a
wildly wrong per-cell response can post a pooled response ratio near 1.0 and look perfect.  This
script therefore reports the per-cell response, a weighted mean, AND **Cochran's Q** with its
I-squared, which is the statistic that says whether the per-cell ratios are consistent enough for
the mean to mean anything.

⚠ A RATIO IS UNSTABLE WHERE THE TRUTH BARELY MOVES.  `response/truth` explodes when `truth ~ 0`, and
that is a property of the cell, not of the arm.  So the headline is the ERROR-IN-VARIABLES SLOPE of
response on truth across cells (with the arm's own seed spread as the weight), and per-cell ratios
are printed only for cells whose truth exceeds `--min-truth` seed standard deviations.  Cells below
that are listed as "unresolved", never silently dropped.

USAGE
    python3 scripts/diagnose_rung2_response.py [--root /p/tmp/jamirp/S_rung2] [--csv out.csv]
    python3 scripts/diagnose_rung2_response.py --stat n_living|wooddens|age_mean
"""

from __future__ import annotations

import argparse
import glob
import math
import os
import re
import sys
from collections import defaultdict

# S_r2s_<scenario>_c<cell>_<arm>_<nprev>_s<seed>_dump
DUMP_RE = re.compile(r"^S_r2s_(historic|ssp370)_c(\d+)_(REC|NP|S0h|S0|S1)_([a-z]+)_s(\d+)_dump$")

STATS = ("n_living", "wooddens", "age_mean")

# The year each leg MUST reach. This is the completeness gate, and it is not optional: a dump from a
# job that crashed, was cancelled, or is still writing looks exactly like a finished one to a reader
# that takes `max(year)` as the terminal year — it would just report an earlier year's stand as the
# century-end answer, silently and plausibly. Same shape as the "never judge a C run from SLURM
# state" rule in CLAUDE.md §3 (those jobs always exit 0), so the run's OWN completion line is
# checked too.
TERMINAL_YEAR = {"historic": 2019, "ssp370": 2100}
RUNROOT = "/p/tmp/jamirp/esm_land_daily"


def run_completed(scen: str, cell: int, arm: str, npv: str, seed: int) -> bool:
    """True iff the C run behind this dump printed its own completion line.

    `lpjml successfully terminated, <n> grid cells processed.` is the only trustworthy signal — the
    job
    files exit 0 regardless, so a mid-run death leaves a plausible truncated dump behind a green
    job.
    """
    y0, y1 = (2020, 2100) if scen == "ssp370" else (2000, 2019)
    tag = f"S_r2s_{scen}_c{cell}_{arm}_{npv}_s{seed}"
    d = os.path.join(RUNROOT, f"daily_{y0}_{y1}_{scen}_{tag}_c{cell}_seed1")
    logs = [p for p in glob.glob(os.path.join(d, "lpjml.*.out")) if os.path.getsize(p) > 0]
    for p in logs:
        with open(p, errors="replace") as fh:
            if "successfully terminated" in fh.read():
                return True
    return False


def read_terminal(path: str, want_year: int) -> dict:
    """Terminal-year stand statistics from one roster dump.

    Reads the `mort` phase — the demographic verdict is settled there, while a `post`-phase `isdead` also
    carries FIRE's victims, which the interface does not own (ADR 0121).  Survivors only.

    `n_living` counts stems above the `ind` writer's 5 m emission cut, because that is the population the
    count model's target was trained on (fwriteoutput_ind.c:84); the thinning acts on the whole roster but
    the SCORE must be on the trained population or the arm is graded against a different quantity.

    PERFORMANCE, and it is the difference between 40 minutes and 40 seconds.  The campaign's dumps total
    ~40 GB and only the FINAL year's `mort` records are scored, so splitting all 51 fields of every line
    wastes ~99 % of the work.  `want_year` is known from the scenario, so a cheap substring test rejects
    almost every line before any parsing.  The year is still re-read from the parsed field afterwards, so a
    spurious substring match (the token appearing in some other column) cannot be counted — the fast path
    only decides what to SKIP, never what to accept.

    Returns {} if the dump carries no `mort` survivors in `want_year`; the caller treats that as incomplete.
    """
    cols = None
    tok = f" {want_year} "
    alive_by_patch: dict[int, int] = defaultdict(int)
    wd_num = wd_den = age_num = age_den = 0.0
    have_grow = False
    with open(path) as fh:
        for line in fh:
            if line[0] != "T":
                if line.startswith("#H T "):
                    cols = {n: i for i, n in enumerate(line.split()[2:])}
                continue
            if not have_grow and " grow " in line:
                have_grow = True
            if tok not in line:                      # cheap reject: not the terminal year
                continue
            if cols is None:
                sys.exit(f"FATAL: {path}: a T record before its '#H T' header")
            f = line.split()[1:]
            if f[cols["phase"]] != "mort" or int(f[cols["year"]]) != want_year:
                continue
            if int(f[cols["isdead"]]):
                continue
            if float(f[cols["height"]]) <= 5.0:      # the `ind` writer's emission cut
                continue
            nind = float(f[cols["nind"]])
            alive_by_patch[int(f[cols["patch"]])] += 1
            wd_num += nind * float(f[cols["wooddens"]])
            age_num += nind * float(f[cols["age"]])
            wd_den += nind
            age_den += nind
    if not have_grow:
        sys.exit(
            f"FATAL: {path} has no `grow` dump phase — it predates the ADR-0123 rendezvous move and its "
            "roster is a year stale. Re-record it."
        )
    if not alive_by_patch:
        return {}
    npatch = len(alive_by_patch)
    return {
        "year": want_year,
        "n_living": sum(alive_by_patch.values()) / npatch,   # patch-ensemble MEAN stems
        "wooddens": wd_num / wd_den if wd_den else float("nan"),
        "age_mean": age_num / age_den if age_den else float("nan"),
        "npatch": npatch,
    }


def mean_sd(v):
    n = len(v)
    if n == 0:
        return float("nan"), float("nan")
    m = sum(v) / n
    if n == 1:
        return m, 0.0
    return m, math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1))


def cochran_q(effects, variances):
    """Cochran's Q over per-cell effects, with I-squared.

    Q ~ chi2(k-1) under the null that every cell shares ONE common effect. A large Q says the
    per-cell
    responses are heterogeneous, i.e. the weighted mean is not a summary of anything and the
    per-cell
    table is the result. I2 is the share of total variation that is real heterogeneity rather than
    noise.
    """
    pairs = [(e, v) for e, v in zip(effects, variances, strict=True) if v > 0 and math.isfinite(e) and math.isfinite(v)]
    if len(pairs) < 2:
        return float("nan"), float("nan"), float("nan"), 0
    w = [1.0 / v for _, v in pairs]
    sw = sum(w)
    mbar = sum(wi * e for wi, (e, _) in zip(w, pairs, strict=True)) / sw
    q = sum(wi * (e - mbar) ** 2 for wi, (e, _) in zip(w, pairs, strict=True))
    k = len(pairs)
    i2 = max(0.0, (q - (k - 1)) / q) * 100.0 if q > 0 else 0.0
    return q, k - 1, i2, k


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/p/tmp/jamirp/S_rung2")
    ap.add_argument("--stat", default="n_living", choices=STATS)
    ap.add_argument("--min-truth", type=float, default=1.0,
                    help="report a per-cell ratio only where |truth| exceeds this many seed SDs")
    ap.add_argument("--csv", default="")
    a = ap.parse_args()

    # (cell, arm, scenario) -> list of per-seed terminal stats
    got: dict[tuple[int, str, str], list[dict]] = defaultdict(list)
    incomplete: list[tuple[str, str]] = []
    for d in sorted(glob.glob(os.path.join(a.root, "S_r2s_*_dump"))):
        m = DUMP_RE.match(os.path.basename(d))
        if not m:
            continue
        scen, cell, arm, _npv, seed = m.group(1), int(m.group(2)), m.group(3), m.group(4), int(m.group(5))
        rank = os.path.join(d, "roster_rank0000.txt")
        if not os.path.exists(rank):
            incomplete.append((os.path.basename(d), "no roster file"))
            continue
        if not run_completed(scen, cell, arm, _npv, seed):
            incomplete.append((os.path.basename(d), "no `successfully terminated` in the run log"))
            continue
        t = read_terminal(rank, TERMINAL_YEAR[scen])
        if not t:
            incomplete.append(
                (os.path.basename(d), f"no `mort` survivors in the terminal year {TERMINAL_YEAR[scen]}")
            )
            continue
        t["seed"] = seed
        got[(cell, arm, scen)].append(t)

    cells = sorted({c for c, _, _ in got})
    arms = [x for x in ("NP", "S0", "S0h", "S1") if any(k[1] == x for k in got)]
    print(f"== {len(cells)} cell(s), arms present: {arms}, statistic: {a.stat}")
    # Never silent about what was dropped: a coverage hole that is not reported reads as "all cells
    # agree".
    if incomplete:
        print(f"== {len(incomplete)} dump(s) EXCLUDED as incomplete/unfinished:")
        for name, why in incomplete[:20]:
            print(f"     {name}: {why}")
        if len(incomplete) > 20:
            print(f"     ... and {len(incomplete) - 20} more")

    rows = []
    print(f"\n{'cell':>7} {'arm':>4} {'hist':>9} {'ssp':>9} {'response':>9} {'truth':>9} {'ratio':>8} {'seeds':>5}")
    per_arm: dict[str, list[tuple[int, float, float, float]]] = defaultdict(list)
    for cell in cells:
        rec_h = got.get((cell, "REC", "historic"), [])
        rec_s = got.get((cell, "REC", "ssp370"), [])
        if not rec_h or not rec_s:
            print(f"{cell:>7}  -- missing REC baseline (hist={len(rec_h)} ssp={len(rec_s)}), cell skipped")
            continue
        truth = rec_s[0][a.stat] - rec_h[0][a.stat]
        # FIT's own two levels are printed as a row, not just their difference: a response ratio is
        # meaningless without knowing whether the baseline moved at all, and an arm that is far off in
        # LEVEL in both legs can still post a plausible-looking DIFFERENCE (ADR 0127's `keep`-ratio trap
        # in a new place).
        print(
            f"{cell:>7} {'C':>4} {rec_h[0][a.stat]:9.3f} {rec_s[0][a.stat]:9.3f} {truth:9.3f} "
            f"{truth:9.3f} {1.0:8.3f} {'--':>5}"
        )
        for arm in arms:
            hs = got.get((cell, arm, "historic"), [])
            ss = got.get((cell, arm, "ssp370"), [])
            if not hs or not ss:
                continue
            # Pair by seed where possible; the response is a difference of two independent runs, so
            # the
            # seed pairing is what keeps the arm's own draw noise from entering twice.
            byseed_h = {x["seed"]: x[a.stat] for x in hs}
            byseed_s = {x["seed"]: x[a.stat] for x in ss}
            common = sorted(set(byseed_h) & set(byseed_s))
            resp = [byseed_s[s] - byseed_h[s] for s in common]
            if not resp:
                continue
            m, sd = mean_sd(resp)
            ratio = m / truth if truth != 0 else float("nan")
            print(
                f"{cell:>7} {arm:>4} {sum(byseed_h[s] for s in common)/len(common):9.3f} "
                f"{sum(byseed_s[s] for s in common)/len(common):9.3f} {m:9.3f} {truth:9.3f} "
                f"{ratio:8.3f} {len(common):5d}"
            )
            per_arm[arm].append((cell, m, sd, truth))
            rows.append((cell, arm, m, sd, truth, ratio, len(common)))

    print("\n== per-arm summary")
    print("   The SLOPE is the headline: response regressed on truth across cells, through the origin,")
    print("   weighted by the arm's own seed variance. 1.0 = the right response; 0.0 = no response at all;")
    print("   negative = the response has the WRONG SIGN. Cochran's Q tests whether the cells agree.")
    for arm in arms:
        data = per_arm[arm]
        if len(data) < 2:
            continue
        # Weighted through-origin slope of response on truth; weights = 1/seed-variance (floored so
        # a
        # zero-spread arm does not get infinite weight).
        var = [max(sd * sd, 1e-9) for _, _, sd, _ in data]
        num = sum((t * r) / v for (_, r, _, t), v in zip(data, var, strict=True))
        den = sum((t * t) / v for (_, _, _, t), v in zip(data, var, strict=True))
        slope = num / den if den > 0 else float("nan")
        se = math.sqrt(1.0 / den) if den > 0 else float("nan")

        resolved = [(c, r, sd, t) for (c, r, sd, t) in data if abs(t) > a.min_truth * max(sd, 1e-9)]
        ratios = [r / t for _, r, _, t in resolved if t != 0]
        rvars = [max(sd * sd, 1e-9) / (t * t) for _, _, sd, t in resolved if t != 0]
        q, dfree, i2, k = cochran_q(ratios, rvars)
        rm, rsd = mean_sd(ratios)
        # Sign agreement is the crudest and most honest statement: how often does the arm even move
        # the
        # same way as FIT at the same cell?
        agree = sum(1 for _, r, _, t in data if r * t > 0)
        print(
            f"   {arm:>4}  slope {slope:7.3f} +- {se:.3f}   per-cell ratio mean {rm:7.3f} (sd {rsd:.3f}, "
            f"n={len(ratios)})   Q {q:8.2f} df {dfree} I2 {i2:5.1f}%   sign agrees {agree}/{len(data)}"
        )
        if len(data) - len(resolved):
            print(f"          ({len(data) - len(resolved)} cell(s) unresolved: |truth| below "
                  f"{a.min_truth} seed SD — listed above, excluded from the ratio only)")

    if a.csv:
        with open(a.csv, "w") as f:
            f.write("cell,arm,response_mean,response_sd,truth,ratio,nseed,stat\n")
            for r in rows:
                f.write(",".join(str(x) for x in r) + f",{a.stat}\n")
        print(f"\nwrote {a.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
