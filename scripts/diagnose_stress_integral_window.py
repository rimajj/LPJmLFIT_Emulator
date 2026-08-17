#!/usr/bin/env python3
"""diagnose_stress_integral_window.py — can the emulator supply FIT's heat/cold-stress day count?

ADR 0244. ADR 0243 measured that the ported mortality hazard, fed the zeros the coupled loop passes
today, delivers only 0.78 of the mortality flux FIT's own stand asks for, and that the TEMPERATURE
integral is 5.6-7.9 pp of that shortfall. This asks whether that half can be handed over EXACTLY —
no new physics, no per-tree water state — because `tempstress_tree.c` reads only the day's AIR
temperature and the PFT's own `temp_stressed` interval, and F already has both.

  src/tree/tempstress_tree.c, verbatim:
      if((temp < treepar->temp_stressed.low) || (temp > treepar->temp_stressed.high))
          tree->temp_stress += 1;
      if ((lat >= 0 && day == COLDEST_DAY_NHEMISPHERE) ||
          (lat <  0 && day == COLDEST_DAY_SHEMISPHERE))
          tree->temp_stress = 0.0;          /* 14 (N) / 195 (S), include/climate.h:20-21 */

THE POINT: the reset is a FIXED CALENDAR DAY and it fires AFTER the increment, so the value the
annual mortality call reads is NOT a calendar-year total — it is the stressed-day count over days
`reset+1 .. 365` only. `FDiffFastCore` resets its own `temp_stress_acc` with `bm_inc_acc` at the END
of the calendar year (`fast.jl:463`), i.e. it hands the hazard days `1 .. 365`. In the north
the extra days 1-14 are the coldest of the year — the days most likely to fall below `temp_low`.
In the SOUTH the two windows differ by half a year.

THE NULLS, both exact and derivable, written before the run (ADR 0243 §4.1's discipline):
  * window C (reset at day 14 N / 195 S) must reproduce the C's own dumped `temp_stress` INTEGER FOR
    INTEGER at every (cell, year, PFT) group. Anything else means this reading of the C is wrong and
    no other number here is read.
  * window F (the calendar year, F's current convention) is then the MEASURED size of F's error, and
    it can only be >= window C because it counts a superset of days.
  * a third window — reset at the first day of the phenological growing season — is NOT tested: the
    C's own comment says "start of vegetation period" but its code says a fixed day, and the code is
    the authority (guardrail 5).

BASIS
  truth   : the `T grow` records of the rung-2 `REC` `predict` dumps = LPJmL-FIT's own roster. Its
            `temp_stress` column is CONSTANT within (year, patch, PFT) — 0 of 5 724 groups vary —
            and patch-invariant, which is what a per-PFT day count must be.
  forcing : the daily air temperature the run itself read. Historic `temperature_test.clm` (v3
            float32, scalar 1.0); ssp370 `tas_..._orderA.clm` (v2 int16, scalar 0.1). Read
            header-driven with `build_transient_boundary.open_clm` (ADR 0100's mixed-version trap);
            the orderA `.clm` cell index IS the dump's cell id.
  params  : `temp_low`/`temp_high` from the committed `S_pft_mortality_params.csv` — the
            `temp_stressed` interval, NOT the establishment `temp` gate (ADR 0047's naming trap).

ENV: DUMPS (default /p/tmp/jamirp/S_rung2), CELLS (space/comma separated; default the 12 rung-2
     cells), SCENARIOS (default "historic ssp370"), SEED (default 1), OUT (a CSV; optional)
Run: TIME=00:30:00 scripts/sbatch_python.sh S-stresswin scripts/diagnose_stress_integral_window.py
Exit 0 always: a measurement, not a CI gate.
"""

from __future__ import annotations

import csv
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_transient_boundary import open_clm  # noqa: E402  (the header-driven reader, ADR 0100)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUMPS = os.environ.get("DUMPS", "/p/tmp/jamirp/S_rung2")
SEED = int(os.environ.get("SEED", "1"))
OUT = os.environ.get("OUT", "")
G = "/p/projects/waldspektrum/priesner/clustering/global"
FORCING = {
    "historic": f"{G}/temperature_test.clm",
    "ssp370": f"{G}/ssp370/tas_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm",
}
DEFAULT_CELLS = "12045 12235 18371 22732 22990 32628 42490 42757 42973 44048 52059 57087"
COLDEST_N, COLDEST_S = 14, 195          # include/climate.h:20-21
NDAY = 365                              # noleap


def _split(v: str) -> list[str]:
    return [t for t in re.split(r"[,\s]+", v.strip()) if t]


def pft_temp_intervals() -> dict[int, tuple[float, float]]:
    """`temp_stressed` low/high per tree PFT id, off the committed generated table."""
    path = os.path.join(REPO, "test/testitems/references/S_pft_mortality_params.csv")
    out: dict[int, tuple[float, float]] = {}
    with open(path, encoding="utf-8") as fh:
        rows = [ln for ln in fh if not ln.startswith("#")]
    rdr = csv.DictReader(rows)
    for r in rdr:
        out[int(r["pft_id"])] = (float(r["temp_low"]), float(r["temp_high"]))
    return out


def scan_dump(path: str) -> tuple[float, dict[tuple[int, int], int]]:
    """-> (lat, {(year, pft_id): temp_stress}) from the `T grow` records.

    The column offset comes off the `#H T` header, never hardcoded (dump-skill trap 1: the n-th
    NAME is
    field n+1 because field 0 is the record tag). The value is asserted CONSTANT within the group,
    which
    is both the structural check that it is a per-PFT day count and the guard that the offset is
    right.
    """
    cols: dict[str, int] = {}
    lat = float("nan")
    vals: dict[tuple[int, int], int] = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("#H T "):
                cols = {n: i for i, n in enumerate(line.split()[2:])}
                continue
            if not line.startswith("T grow"):
                continue
            f = line.split()
            if not cols:
                raise SystemExit(f"FATAL: {path} has T records before its #H T header")
            lat = float(f[cols["lat"] + 1])
            key = (int(f[cols["year"] + 1]), int(f[cols["pft_id"] + 1]))
            v = int(round(float(f[cols["temp_stress"] + 1])))
            if key in vals and vals[key] != v:
                raise SystemExit(
                    f"FATAL: {path} temp_stress varies within (year,pft) {key}: "
                    f"{vals[key]} vs {v} — either the column offset is wrong, or the "
                    "quantity is not a per-PFT day count"
                )
            vals[key] = v
    return lat, vals


def main() -> int:
    cells = [int(c) for c in _split(os.environ.get("CELLS", DEFAULT_CELLS))]
    scens = _split(os.environ.get("SCENARIOS", "historic ssp370"))
    intervals = pft_temp_intervals()
    print("=" * 104)
    print("CAN THE EMULATOR SUPPLY FIT'S HEAT/COLD-STRESS DAY COUNT EXACTLY?   (ADR 0244)")
    print("  window C = the C's own (reset day 14 N / 195 S, AFTER the increment)")
    print("            -> the DERIVED null: it must match the dumps exactly")
    print("  window F = the calendar year (`fast.jl`'s current reset)")
    print("            -> the MEASURED size of F's convention error")
    print(f"  cells={len(cells)} scenarios={scens} seed={SEED}")
    print("=" * 104)

    rows: list[list] = []
    for scen in scens:
        mm, firstyear, ncell, nbands, scalar = open_clm(FORCING[scen])
        if nbands != NDAY:
            raise SystemExit(f"FATAL: {FORCING[scen]} nbands={nbands}, expected {NDAY} (noleap)")
        tot_c = tot_f = ngroup = 0
        bad_c = bad_f = 0
        sum_c = sum_f = sum_t = 0
        maxdiff_f = 0
        print(f"\n{'-' * 104}\n-- {scen} leg\n")
        print(f"   {'cell':>8} {'lat':>7} {'groups':>7} {'meanC':>8} {'meanF':>8} {'meanTRUE':>9} "
              f"{'C exact':>9} {'F exact':>9} {'max|F-T|':>9}")
        for cell in cells:
            d = f"{DUMPS}/S_r2s_{scen}_c{cell}_REC_predict_s{SEED}_dump/roster_rank0000.txt"
            if not os.path.isfile(d):
                print(f"   {cell:>8}  (no dump — skipped)")
                continue
            lat, truth = scan_dump(d)
            reset = COLDEST_N if lat >= 0.0 else COLDEST_S
            years = sorted({y for (y, _) in truth})
            # per-year daily temperature for this cell, °C = raw·scalar
            temp = {}
            for y in years:
                iy = y - firstyear
                if iy < 0 or iy >= mm.shape[0]:
                    continue
                temp[y] = np.asarray(mm[iy, cell, :], dtype=np.float64) * scalar
            c_ex = f_ex = n = 0
            s_c = s_f = s_t = 0
            mx = 0
            for (y, pft), tv in sorted(truth.items()):
                if y not in temp or pft not in intervals:
                    continue
                lo, hi = intervals[pft]
                stressed = (temp[y] < lo) | (temp[y] > hi)
                # window C: the counter is zeroed ON the reset day, so what survives to the annual
                # mortality call is days reset+1 .. 365 (1-based days -> 0-based index reset..364)
                cw = int(stressed[reset:].sum())
                fw = int(stressed.sum())
                n += 1
                s_c += cw
                s_f += fw
                s_t += tv
                c_ex += int(cw == tv)
                f_ex += int(fw == tv)
                mx = max(mx, abs(fw - tv))
                rows.append([scen, cell, lat, y, pft, tv, cw, fw])
            if n == 0:
                continue
            print(f"   {cell:>8} {lat:>7.2f} {n:>7d} {s_c / n:>8.2f} {s_f / n:>8.2f} "
                  f"{s_t / n:>9.2f} "
                  f"{c_ex / n:>9.4f} {f_ex / n:>9.4f} {mx:>9d}")
            ngroup += n
            tot_c += c_ex
            tot_f += f_ex
            bad_c += n - c_ex
            bad_f += n - f_ex
            sum_c += s_c
            sum_f += s_f
            sum_t += s_t
            maxdiff_f = max(maxdiff_f, mx)
        if ngroup == 0:
            print("   (no scoreable groups)")
            continue
        print(f"\n   POOLED {ngroup} (cell,year,PFT) groups")
        print(f"     window C exact: {tot_c}/{ngroup} = {tot_c / ngroup:.6f} ({bad_c} bad)")
        print(f"     window F exact: {tot_f}/{ngroup} = {tot_f / ngroup:.6f} ({bad_f} bad), "
              f"max |F - truth| = {maxdiff_f} days")
        print(f"     mean days: truth {sum_t / ngroup:.3f} · C {sum_c / ngroup:.3f} · "
              f"F {sum_f / ngroup:.3f}")
        if sum_t > 0:
            over = 100 * (sum_f - sum_t) / sum_t
            print(f"     F over-counts the C's own integral by {over:+.2f} % "
                  "of the total stressed-day count")
        verdict = (
            "EXACT — the emulator can supply this integral with no new physics: same forcing, same "
            "interval, same window"
            if bad_c == 0
            else f"NOT EXACT ({bad_c} groups) — this reading of tempstress_tree.c is wrong, STOP"
        )
        print(f"     NULL 1 [window C]: {verdict}")
        fverd = "identical to C here" if bad_f == 0 else "WRONG WINDOW"
        print(f"     MEASURED [window F]: {fverd} — "
              f"{bad_f} of {ngroup} groups differ")

    if OUT and rows:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(
                ["scenario", "cell", "lat", "year", "pft_id", "truth", "window_c", "window_f"]
            )
            w.writerows(rows)
        print(f"\nwrote {len(rows)} rows -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
