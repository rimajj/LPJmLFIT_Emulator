#!/usr/bin/env python
"""
diagnose_rung2_gross_account_identity — the DERIVABLE A-PRIORI GATE on the gross-budget arms
(`G0`/`G0h`/`G1`, ADR 0240). Seconds per leg, arm logs only, no dump scan, no model run.

WHY A DERIVABLE GATE AND NOT A PLAUSIBILITY CHECK. ADR 0187 §A and skill traps 5d/5f: an arm whose
answer is known exactly in advance is the cheapest real check on a new instrument, and it has
already caught two independent basis errors in this investigation. The gross-budget arm has TWO such
answers, and they test different things:

1. THE ACCOUNT IDENTITY, row by row. The harness's arithmetic is closed-form, so every logged value
   is reproducible from the previous row of the SAME patch:

       a_i       = acct_{i-1} + (1 - rho_i) * n_tree_i + n_age1_i      (acct_{-1} = 0 per patch)
       budget_i  = clamp(a_i, 0, n_tree_i)
       rho_eff_i = 1 - budget_i / n_tree_i        (1.0 on an empty roster)
       acct_i    = a_i - n_kill_i                 (the charge is what was REALIZED)

   Chained on the LOGGED `acct`, not on the recomputed one, so an error cannot hide behind its own
   propagation. Any mismatch is a defect in the harness, not a property of the stand.

2. `G0`'s SPEND RATIO. `G0` draws uniformly at `f = rho_eff` over the whole roster, so
   `E[n_kill] = (1 - rho_eff) * n_tree = budget` EXACTLY. Its realized `n_kill / budget` must
   therefore sit at 1 within the draw's own sampling error, and it is the one arm for which that is
   true: `G0h`/`G1` set `f = 0` on the certain deaths, which cannot be un-killed, so a short budget
   still costs `n_cert` and their ratio is legitimately ABOVE 1 (measured 1.05-1.14). Reading their
   overshoot as a bug is the error this panel exists to prevent.

WHAT IT DOES NOT TEST. Whether the budget is the right SIZE — that is ADR 0188 §7's criterion,
scored by `diagnose_rung2_kill_selectivity.py` (rate, mass removal) and
`diagnose_rung2_anchor_preflight.py` (the departure). This file only certifies that the arm spends
what its own definition says.

Env
    ARMS    comma or space list      (default "G0 G0h G1")
    CELLS   comma list               (default ADR 0187's 12 scoreable cells)
    SEEDS   comma list               (default 1,2,3,4,5)
    SCENS   comma or space list      (default "historic ssp370")
    NPREV   roster | predict         (default predict)
    TOL     absolute tolerance       (default 1e-9 — the log prints full Float64 `repr`)

Usage
    /home/jamirp/.conda/envs/py311_new/bin/python scripts/diagnose_rung2_gross_account_identity.py
"""

from __future__ import annotations

import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from diagnose_rung2_map_target_response import ROOT, _split_arms  # noqa: E402

ARMS = _split_arms(os.environ.get("ARMS", "G0 G0h G1"))
SCENS = _split_arms(os.environ.get("SCENS", "historic ssp370"))
SEEDS = [int(x) for x in _split_arms(os.environ.get("SEEDS", "1,2,3,4,5"))]
DEFAULT_CELLS = (12045, 12235, 18371, 22732, 22990, 32628, 42490, 42757, 42973, 44048, 52059, 57087)
CELLS = [int(x) for x in _split_arms(os.environ["CELLS"])] if os.environ.get("CELLS") \
    else list(DEFAULT_CELLS)
NPREV = os.environ.get("NPREV", "predict")
TOL = float(os.environ.get("TOL", "1e-9"))
#: `G0` is the uniform arm, so it is the one whose spend ratio is derivable (see the header).
UNIFORM_ARM = "G0"
#: pre-registered band on that ratio. The draw is one Bernoulli per stem per patch-year, so over a
#: whole leg (>= 12 500 stem-draws) its SE is well under a per cent; 0.02 is loose on purpose.
SPEND_TOL = 0.02


def read_log(path):
    cols, rows = None, []
    with open(path) as fh:
        for line in fh:
            if line.startswith("#H L"):
                cols = {n: i + 1 for i, n in enumerate(line.split()[2:])}
                continue
            if not line.startswith("L ") or cols is None:
                continue
            f = line.split()
            rows.append({n: f[i] for n, i in cols.items()})
    return cols, rows


def check_leg(path):
    """-> (nrows, mismatches, worst |diff|, empty share, spend ratio); a str/None if ungateable."""
    cols, rows = read_log(path)
    if not rows:
        return None
    if "n_age1" not in cols:
        return "pre-0240 log (no `n_age1` column) — nothing to gate"
    by_patch = defaultdict(list)
    for r in rows:
        by_patch[int(r["patch"])].append(r)
    for rs in by_patch.values():
        rs.sort(key=lambda r: int(r["year"]))
    bad, worst = defaultdict(int), defaultdict(float)
    empty = 0
    nk = nb = 0.0
    for rs in by_patch.values():
        prev = 0.0
        for r in rs:
            n_tree = float(r["n_tree"])
            a = prev + (1.0 - float(r["rho"])) * n_tree + float(r["n_age1"])
            b = min(max(a, 0.0), n_tree)
            want = {
                "budget": b,
                "rho_eff": 1.0 - b / n_tree if n_tree > 0 else 1.0,
                "acct": a - float(r["n_kill"]),
            }
            for name, w in want.items():
                d = abs(float(r[name]) - w)
                worst[name] = max(worst[name], d)
                if d > TOL:
                    bad[name] += 1
            if b <= 0.0:
                empty += 1
            nk += float(r["n_kill"])
            nb += b
            prev = float(r["acct"])          # chain on the LOGGED value
    sp = nk / nb if nb > 0 else float("nan")
    return len(rows), dict(bad), dict(worst), empty / len(rows), sp


def main() -> int:
    print("=" * 100)
    print("  RUNG-2 GROSS-BUDGET ACCOUNT IDENTITY — the derivable a-priori gate (ADR 0240)")
    print(f"  mode NPREV={NPREV}  arms={ARMS}  seeds={SEEDS}  cells={len(CELLS)}  tol={TOL:g}")
    print("=" * 100)
    legs = nrows = 0
    failed, missing = [], []
    spend = defaultdict(list)
    worst_all = defaultdict(float)
    for scen in SCENS:
        for cell in CELLS:
            for arm in ARMS:
                for seed in SEEDS:
                    p = os.path.join(
                        ROOT, f"S_r2s_{scen}_c{cell}_{arm}_{NPREV}_s{seed}_apply", "s_arm_log.txt"
                    )
                    if not os.path.isfile(p):
                        missing.append((scen, cell, arm, seed))
                        continue
                    res = check_leg(p)
                    if res is None or isinstance(res, str):
                        missing.append((scen, cell, arm, seed))
                        continue
                    n, bad, worst, _emp, sp = res
                    legs += 1
                    nrows += n
                    for k, v in worst.items():
                        worst_all[k] = max(worst_all[k], v)
                    if bad:
                        failed.append((scen, cell, arm, seed, n, bad))
                    if arm == UNIFORM_ARM and not math.isnan(sp):
                        spend[scen].append(sp)

    print(f"\n  (1) THE ACCOUNT IDENTITY, row by row over {nrows} patch-years in {legs} leg(s)")
    for k in ("budget", "rho_eff", "acct"):
        print(f"        {k:8s} max |logged - derived| = {worst_all.get(k, 0.0):.3e}")
    if failed:
        print(f"      FAIL — {len(failed)} leg(s) disagree:")
        for scen, cell, arm, seed, n, bad in failed[:20]:
            print(f"        {scen:<9} c{cell:<6d} {arm:<4} s{seed}  {n} rows  {bad}")
    else:
        print("      PASS — every logged budget, rho_eff and account is reproduced exactly.")
    if missing:
        print(f"      {len(missing)} leg(s) had no gateable log (named, skill trap 2):")
        for scen, cell, arm, seed in missing[:20]:
            print(f"        {scen:<9} c{cell:<6d} {arm:<4} s{seed}")
        if len(missing) > 20:
            print(f"        ... and {len(missing) - 20} more")

    print(f"\n  (2) `{UNIFORM_ARM}`'s SPEND RATIO — derived answer 1.000, band ±{SPEND_TOL:g}")
    ok2 = True
    for scen in SCENS:
        v = spend.get(scen, [])
        if not v:
            print(f"        {scen:<9} no leg")
            continue
        m = sum(v) / len(v)
        hit = abs(m - 1.0) <= SPEND_TOL
        ok2 = ok2 and hit
        print(f"        {scen:<9} mean over {len(v):2d} legs = {m:.4f}"
              f"   {'PASS' if hit else 'FAIL'}   (min {min(v):.4f}, max {max(v):.4f})")
    print("      A ratio ABOVE 1 for `G0h`/`G1` is CORRECT, not a defect: their certain deaths")
    print("      have f = 0 and cannot be un-killed, so a short budget still costs n_cert and the")
    print("      account repays it later. Only the UNIFORM arm has a derivable answer here.")
    return 0 if (not failed and ok2) else 1


if __name__ == "__main__":
    raise SystemExit(main())
