#!/usr/bin/env python3
"""Score whether an online Terrarium `plant_available_water` field is INFORMATIVE or CLAMPED.

WHY THIS EXISTS (line O, O3b; ADR 0085)
---------------------------------------
O3b set out to quantify a `soilmoist` train/inference shift for Component S by comparing the
online Terrarium root-zone PAW distribution against LPJmL-FIT's live `soilmoist_ye` table.  The
30-day and 90-day runs (jobs 1706597 / 1706979) returned root-zone quantiles that agree to four
digits, which the previous handoff had pre-registered as meaning "the run has converged and the
gap is real".

It does not mean that.  This script is the check that distinguishes the two, and it needs NO
simulation -- it reads the candidate CSVs the diagnosis run already wrote.

`FieldCapacityLimitedPAW` is `W = min(max((θw − θwp)/(θfc − θwp), 0), 1)`, i.e. a quantity that is
CLIPPED at both ends.  So a layer whose water sits at or above field capacity reports exactly 1.0
and a layer at or below wilting point reports exactly 0.0, no matter how much water is actually
there.  When every layer of the root zone is at one of those two clamps, the thickness-weighted
root-zone mean can only take the `nlayer + 1` values of the cumulative-thickness ladder

    ladder[m] = (Σ of the top m layer thicknesses) / (total root-zone thickness)

-- one value per position of a sharp wetting front.  A field sitting on that ladder is a step
function of FRONT DEPTH, not a moisture distribution, and comparing its quantiles against a
continuous reference is meaningless: it is unchanged between two runs because the diagnostic is
saturated, not because a physical balance converged.

Three statistics, reported per input file:
  1. the fraction of land columns lying ON the ladder (every root-zone layer at a clamp);
  2. the number of distinct values and the mass on the top few levels;
  3. between two files, the fraction of land columns that are BIT-IDENTICAL.

Usage
-----
    python3 scripts/online_coupling/diagnose_paw_clamping.py A.csv [B.csv]

The CSVs are those written by `diagnose_soilmoist_shift.jl`
(`terrarium_soilmoist_candidates_<TAG>.csv`, columns
`paw_unweighted,paw_rootzone_1m,sat_layermean,clay,is_land`).
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import Counter

# Root-zone layer thicknesses in metres, SURFACE -> DOWN, for the O3b column geometry
# `ExponentialSpacing(N=30, Δz_min=0.05, Δz_max=2.5)` restricted to layer bottoms within 1.0 m.
# NOT hand-derived -- read out of Terrarium's own `get_spacing`, which is the authority
# (guardrail 5), with:
#   julia --project=/p/tmp/jamirp/esm_online_coupling -e 'using Terrarium; \
#     v=ExponentialSpacing(;N=30, Δz_min=0.05, Δz_max=2.5); \
#     Δz=reverse(Float64.(Terrarium.get_spacing(v))); \
#     db=[sum(@view Δz[k:end]) for k in eachindex(Δz)]; println(reverse(Δz[db .<= 1.0]))'
# The `EXPECTED_ROOTZONE_DEPTH` assertion below gates them against the depth the run itself logged
# ("root zone: 10 of 30 layers within 1.0 m (0.988 m of soil)"), so a geometry change cannot pass
# silently.
ROOTZONE_THICKNESS_M = (0.05, 0.0572, 0.0655, 0.0749, 0.0858, 0.0982, 0.112, 0.129, 0.147, 0.168)
EXPECTED_ROOTZONE_DEPTH = 0.9876
LADDER_TOL = 1.0e-5

PAW_COL = "paw_rootzone_1m"


def build_ladder(thickness: tuple[float, ...]) -> list[float]:
    """The `len(thickness) + 1` root-zone means reachable when every layer is at a clamp."""
    total = sum(thickness)
    if abs(total - EXPECTED_ROOTZONE_DEPTH) > 1.0e-3:
        raise SystemExit(
            f"root-zone thicknesses sum to {total:.4f} m but the run logged "
            f"{EXPECTED_ROOTZONE_DEPTH} m -- the column geometry changed, re-read `get_spacing`"
        )
    ladder, acc = [0.0], 0.0
    for t in thickness:
        acc += t
        ladder.append(acc / total)
    return ladder


def load(path: str) -> list[dict[str, float]]:
    with open(path) as fh:
        rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(fh)]
    if not rows or PAW_COL not in rows[0]:
        raise SystemExit(f"{path}: no `{PAW_COL}` column -- is this a pre-ADR-0035 (top-2 m) CSV?")
    return rows


def land_index(rows: list[dict[str, float]]) -> list[int]:
    return [i for i, r in enumerate(rows) if r["is_land"] > 0.5]


def report_one(tag: str, rows: list[dict[str, float]], ladder: list[float]) -> float:
    land = land_index(rows)
    on_ladder = 0
    fronts: Counter[int] = Counter()
    for i in land:
        v = rows[i][PAW_COL]
        m = min(range(len(ladder)), key=lambda j: abs(ladder[j] - v))
        if abs(ladder[m] - v) < LADDER_TOL:
            on_ladder += 1
            fronts[m] += 1
    levels = Counter(round(rows[i][PAW_COL], 6) for i in land)
    frac = on_ladder / len(land)
    sat = [rows[i]["sat_layermean"] for i in land]

    print(f"\n=== {tag} ===")
    print(f"land columns                              {len(land)}")
    print(f"distinct root-zone PAW values             {len(levels)}")
    print(f"at exactly 0.0 (root zone bone dry)       {levels[0.0]} "
          f"({100 * levels[0.0] / len(land):.1f} %)")
    top = levels.most_common(4)
    mass = sum(n for _, n in top)
    print(f"mass on the 4 commonest levels            {mass} ({100 * mass / len(land):.1f} %)  "
          + ", ".join(f"{v}:{n}" for v, n in top))
    print(f"ON the binary front ladder (|Δ|<{LADDER_TOL:g})     {on_ladder}/{len(land)} "
          f"= {100 * frac:.1f} %   <-- THE VERDICT")
    print("front depth (# wet top layers):           "
          + ", ".join(f"m={m}:{n}" for m, n in sorted(fronts.items())))
    print(f"whole-column mean saturation over land    {sum(sat) / len(sat):.6f}")
    return frac


def report_pair(rows_a: list[dict[str, float]], rows_b: list[dict[str, float]],
                tag_a: str, tag_b: str) -> None:
    land = land_index(rows_a)
    if land != land_index(rows_b):
        raise SystemExit("the two files disagree on the land mask -- different grids")
    same = sum(1 for i in land if abs(rows_a[i][PAW_COL] - rows_b[i][PAW_COL]) <= 1.0e-12)
    sat_a = sum(rows_a[i]["sat_layermean"] for i in land) / len(land)
    sat_b = sum(rows_b[i]["sat_layermean"] for i in land) / len(land)
    print(f"\n=== {tag_a} vs {tag_b} ===")
    print(f"land columns BIT-IDENTICAL in {PAW_COL}: {same}/{len(land)} "
          f"= {100 * same / len(land):.1f} %")
    print(f"whole-column mean saturation over land:    {sat_a:.6f} -> {sat_b:.6f} "
          f"({100 * (sat_b - sat_a) / sat_a:+.3f} %)")
    print(
        "\nA static field is NOT evidence of convergence when the diagnostic is clamped: a run\n"
        "whose every root-zone layer sits at field capacity or at wilting point reports the same\n"
        "PAW forever while the water underneath it is free to move."
    )


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv", nargs="+", help="terrarium_soilmoist_candidates_<TAG>.csv (1 or 2)")
    args = ap.parse_args(argv)
    if len(args.csv) > 2:
        raise SystemExit("pass one CSV, or two to also get the bit-identity comparison")

    ladder = build_ladder(ROOTZONE_THICKNESS_M)
    print("binary-front ladder (top m layers clamped to PAW=1, the rest to 0):")
    for m, x in enumerate(ladder):
        print(f"   m={m:2d}  {x:.6f}")

    loaded = [(os.path.basename(p), load(p)) for p in args.csv]
    fracs = [report_one(tag, rows, ladder) for tag, rows in loaded]
    if len(loaded) == 2:
        report_pair(loaded[0][1], loaded[1][1], loaded[0][0], loaded[1][0])

    if max(fracs) > 0.5:
        print(
            f"\nVERDICT: CLAMPED -- {100 * max(fracs):.1f} % of land columns have EVERY root-zone\n"
            "layer at a clamp, so this field carries only the depth of the infiltration front.\n"
            "It is NOT a moisture distribution and its quantiles must NOT be scored against\n"
            "LPJmL's `soilmoist_ye`, nor reported to line S as a train/inference shift (ADR 0085)."
        )
        return 1
    print(
        f"\nVERDICT: INFORMATIVE -- only {100 * max(fracs):.1f} % of land columns are fully\n"
        "clamped, so the intermediate regime is populated and a comparison is meaningful."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
