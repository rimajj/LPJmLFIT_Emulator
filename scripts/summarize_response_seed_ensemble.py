#!/usr/bin/env python3
"""summarize_response_seed_ensemble.py — turn a set of `trait_mortality_arm_probe.jl
MODE=response` logs into the ONLY quotable form of a Phase-3A response number: a
seed-ensemble mean +/- SEM with n, a two-sided t and a 95 % CI (ADR 0101).

WHY (ADR 0101). The 2x2 double difference has a seed sd of 0.67-1.74x the FIT reference
shift -- the same size as the effect -- so a single-seed read is one draw from a wide
distribution, not a measurement. This script exists so that the ensemble, not the draw,
is what ever reaches an ADR or the report.

It also enforces the two PRECONDITIONS a response number is only interpretable under,
because both are silent failures that look like physics:
  * ADR 0048  -- the k-cap merge must be DORMANT (trait-destructive at 3.1-5.1x signal);
  * ADR 0101  -- HARD KILLS and count-override (shortfall) years must be ZERO. When the
    hazard overrides the DRF's count target the operator stops being a redistribution of
    a fixed count and the double difference measures something else: at Hainich the
    n_init=7 branch fires 6-7 hard kills and swings the interaction to -3.7x FIT.
A run violating either is reported and EXCLUDED from the statistics, never averaged in.

Usage:
    scripts/summarize_response_seed_ensemble.py 'logs/S-tmresp-seed*.out' [more globs...]
    CSV=out.csv scripts/summarize_response_seed_ensemble.py 'logs/S-tmresp-seed*.out'

Env: CSV (optional) -- also write the per-seed rows as a committable fixture.
     FIT_SHIFT (2432.9) -- ADR 0046 s1's per-cell median wooddens shift, the x-FIT scale.
"""

from __future__ import annotations

import glob
import os
import re
import statistics as st
import sys

FIT_SHIFT = float(os.environ.get("FIT_SHIFT", "2432.9"))

# df -> two-sided t_.975. Only the small-n rows matter here; anything larger uses 1.96.
_T975 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
    9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 22: 2.074, 24: 2.064,
    30: 2.042, 40: 2.021, 60: 2.000,
}


def t975(df: int) -> float:
    if df <= 0:
        return float("nan")
    if df in _T975:
        return _T975[df]
    ks = [k for k in _T975 if k <= df]
    return _T975[max(ks)] if ks else 1.96


def parse(path: str) -> dict | None:
    """One log -> its four corners, the three response numbers and both preconditions."""
    s = open(path).read()
    if "exit=0" not in s[-300:]:
        return None

    def num(pat, cast=float):
        m = re.search(pat, s)
        return cast(m.group(1)) if m else None

    # the (b) 2x2 table. Both rows are "<label> <ctl> <arm> <delta>"; (b) precedes the
    # section-(d) table that reuses the same two labels, and re.search takes the first.
    row = r"{}\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)"
    mh, ms = re.search(row.format("historic"), s), re.search(row.format("ssp370"), s)
    if not (mh and ms):
        return None
    merges = re.findall(r"k-cap merges \(k_cap = [^)]*\): (.*)", s)
    nmerge = sum(int(x) for x in re.findall(r"\b(\d+)\b", merges[-1])) if merges else None
    # The three response numbers in gC/m3, DERIVED from the four corners rather than
    # scraped: the log's own `R_ctl = ...x` lines are already divided by FIT_SHIFT, and
    # re-scaling a x-FIT number is the unit bug this comment exists to prevent. Deriving
    # them also makes the parse self-checking against the log's printed x-FIT values.
    r_ctl = float(ms.group(1)) - float(mh.group(1))
    r_arm = float(ms.group(2)) - float(mh.group(2))
    inter = float(ms.group(3)) - float(mh.group(3))
    for got, pat, name in ((r_ctl, r"R_ctl \(.*?\) = (-?[\d.]+)", "R_ctl"),
                           (r_arm, r"R_arm \(.*?\) = (-?[\d.]+)", "R_arm"),
                           (inter, r"INTERACTION.*?= (-?[\d.]+)", "interaction")):
        want = num(pat)
        # the log prints 4 decimals of a x-FIT ratio, so allow one unit in that last place
        if want is not None and abs(got / FIT_SHIFT - want) > 5.0e-4:
            raise SystemExit(
                f"{path}: {name} derived from the 2x2 corners ({got / FIT_SHIFT:.4f}x) "
                f"disagrees with the log's printed {want:.4f}x — the (b) table parse is "
                f"wrong, or FIT_SHIFT ({FIT_SHIFT}) is not the log's reference scale"
            )
    return {
        "log": os.path.basename(path),
        "seed": num(r"\bseed=(\d+)", int),
        "drf": num(r"artifacts: drf=(\S+)", str),
        "n_init": num(r"n_init=([\d.]+)"),
        "age0": num(r"age0=([\d.]+)"),
        "score_window": num(r"SCORE_WINDOW=(\d+)", int),
        "wd_ctl_hist": float(mh.group(1)), "wd_arm_hist": float(mh.group(2)),
        "d_hist": float(mh.group(3)),
        "wd_ctl_ssp": float(ms.group(1)), "wd_arm_ssp": float(ms.group(2)),
        "d_ssp": float(ms.group(3)),
        "R_ctl": r_ctl, "R_arm": r_arm, "interaction": inter,
        # ARM=recruit runs with TRAIT_MORT=0 print NO trait-mortality diagnostics at all, because the
        # operator is off on BOTH sides of that contrast. Absent is 0 there, not unknown — but only
        # because `arm` says which contrast this log is; never default a missing precondition to 0
        # without that check (a truncated trait_mortality log would then read as clean).
        "arm": num(r"(?m)^ARM=(\S+)", str) or "trait_mortality",
        "hard_kills": num(r"hard kills \(cumulative\):\s+(\d+)", int),
        "shortfall_years": len(re.findall(r"max rel\. shortfall", s)),
        "n_merge": nmerge,
        "bnd_live": num(r"BOUNDARY-CHANNEL LIVENESS.*?= ([\d.e+-]+)"),
        # ARM=recruit preconditions (ADR 0119): the rule must have DRAWN, and the seedbank must have
        # FILLED — an empty bank means every draw came from the static uniform channel, which cannot
        # respond to climate at all, so such a run is inert by construction and bounds nothing.
        "estab_draws": num(r"arm \(R1\) establishment draws:\s+(\d+)", int),
        "inherit_pct": num(r"inherited / background:\s+\d+ / \d+ = ([\d.]+)"),
        "sb_weight": num(r"seedbank at the final draw:\s+\d+ entries, ([\d.e+-]+)"),
        "d_drawn_wd": num(r"Δ\(mean drawn wooddens\), ssp370 − historic = (-?[\d.]+)"),
    }


def usable(r: dict) -> bool:
    """The preconditions a response number is only interpretable under, per arm."""
    if r["shortfall_years"] or r["n_merge"] not in (0, None):
        return False
    if r["arm"] == "recruit":
        # the trait-mortality lines are legitimately absent (TRAIT_MORT=0) OR present (TRAIT_MORT=1)
        if r["hard_kills"] not in (0, None):
            return False
        # ADR 0119: no draw => the rule never ran; empty seedbank => only the static uniform channel ran
        return bool(r["estab_draws"]) and bool(r["sb_weight"])
    return r["hard_kills"] == 0


def report(rows: list[dict], label: str) -> None:
    ok = [r for r in rows if usable(r)]
    bad = [r for r in rows if not usable(r)]
    arms = sorted({r["arm"] for r in rows})
    print(f"\n=== {label} ===")
    if len(arms) > 1:
        print(f"  ⚠ MIXED ARMS in one ensemble {arms} — these are NOT replicates of one"
              " measurement; split the globs.")
    print(f"  arm = {arms[0] if len(arms) == 1 else arms}")
    print(f"  n = {len(ok)} usable of {len(rows)} logs"
          + (f"   EXCLUDED {len(bad)}: " +
             ", ".join(f"seed {r['seed']} (hk={r['hard_kills']}, "
                       f"shortfall={r['shortfall_years']}, merge={r['n_merge']}, "
                       f"draws={r['estab_draws']}, sb={r['sb_weight']})"
                       for r in bad) if bad else ""))
    if not ok:
        print("  ⚠ nothing usable — every run violated a precondition; this bounds NOTHING")
        return
    art = sorted({r["drf"] for r in ok})
    ini = sorted({(r["n_init"], r["age0"]) for r in ok})
    print(f"  artifact {art}   n_init/age0 {ini}   window {sorted({r['score_window'] for r in ok})}")
    if len(art) > 1 or len(ini) > 1:
        print("  ⚠ MIXED artifacts or initial conditions in one ensemble — these are NOT"
              " replicates of the same measurement; split the globs.")
    hdr = ("quantity", "mean", "sd", "sem", "t", "95% CI", "unit")
    print("  {:<26}{:>10}{:>10}{:>9}{:>7}  {:<20}{}".format(*hdr))
    df = len(ok) - 1
    quantities = [
        ("d_hist", "level effect, historic", 1.0, "gC/m3"),
        ("d_ssp", "level effect, ssp370", 1.0, "gC/m3"),
        ("R_ctl", "baseline warming resp.", FIT_SHIFT, "xFIT"),
        ("R_arm", "arm warming response", FIT_SHIFT, "xFIT"),
        ("interaction", "OPERATOR's contribution", FIT_SHIFT, "xFIT"),
    ]
    if arms == ["recruit"]:
        # the sampler's OWN scenario response, upstream of growth and mortality (the probe's (d2) panel):
        # the mechanism the kill condition is about, and the one quantity here that is not a stand outcome
        quantities += [("d_drawn_wd", "drawn-marginal response", FIT_SHIFT, "xFIT"),
                       ("inherit_pct", "inherited share, historic", 1.0, "%")]
    for key, name, scale, unit in quantities:
        if any(r.get(key) is None for r in ok):
            print(f"  {name:<26}{'(absent from at least one log — not summarised)':>10}")
            continue
        v = [r[key] / scale for r in ok]
        m = st.mean(v)
        sd = st.stdev(v) if len(v) > 1 else 0.0
        sem = sd / len(v) ** 0.5 if len(v) > 1 else 0.0
        h = t975(df) * sem
        tv = m / sem if sem > 0 else float("nan")
        print(f"  {name:<26}{m:>10.3f}{sd:>10.3f}{sem:>9.3f}{tv:>7.2f}  "
              f"[{m - h:+.3f}, {m + h:+.3f}]".ljust(72) + unit)
    print("  reading: a CI that straddles 0 means this ensemble CANNOT distinguish the"
          " channel from inert.")


def main() -> int:
    globs = sys.argv[1:]
    if not globs:
        print(__doc__)
        return 2
    allrows: list[dict] = []
    for g in globs:
        rows = [r for r in (parse(f) for f in sorted(glob.glob(g))) if r]
        if not rows:
            print(f"\n=== {g} ===\n  no complete logs matched (a running or failed job "
                  f"has no 'exit=0' tail)")
            continue
        rows.sort(key=lambda r: (r["seed"] or 0))
        report(rows, g)
        allrows += rows
    out = os.environ.get("CSV")
    if out and allrows:
        cols = ["log", "arm", "drf", "seed", "n_init", "age0", "score_window", "wd_ctl_hist",
                "wd_arm_hist", "d_hist", "wd_ctl_ssp", "wd_arm_ssp", "d_ssp", "R_ctl",
                "R_arm", "interaction", "hard_kills", "shortfall_years", "n_merge",
                "bnd_live", "estab_draws", "inherit_pct", "sb_weight", "d_drawn_wd"]
        with open(out, "w") as fh:
            fh.write("# Phase-3A response 2x2, PER SEED (ADR 0101). Hainich cell 42490 only.\n")
            fh.write("# R_ctl/R_arm/interaction are gC/m3; divide by 2432.9 for xFIT (ADR 0046 s1).\n")
            fh.write("# Rows with hard_kills>0, shortfall_years>0 or n_merge>0 are NOT usable\n")
            fh.write("# (ADR 0048/0101 preconditions) and are excluded from every statistic.\n")
            fh.write(",".join(cols) + "\n")
            for r in allrows:
                fh.write(",".join("" if r.get(c) is None else str(r[c]) for c in cols) + "\n")
        print(f"\nwrote {out}  ({len(allrows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
