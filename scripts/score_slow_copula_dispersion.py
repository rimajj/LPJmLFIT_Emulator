#!/usr/bin/env python3
"""Score the SEED1-ONLY between-cell statistics of a copula table's OOS predictions — and DIFF two of them.

WHY THIS EXISTS (ADR 0038, milestone S2)
----------------------------------------
The ADR-0030 gate (`scripts/noise_floor_vs_emulator.py`) needs a **seed2** table: the attenuation-corrected
ceiling, the `%GAP` of criterion 1 and the `r_center` of criterion 4 are all defined against a second
independent realization of the same cells. A seed2 table exists for `historic` only
(`slow_copula_historic_seed2_t8`); there is **no pooled and no ssp370 seed2**. So the full gate is not
computable for the artifact line M actually pins, and the honest options are (a) build a pooled seed2, or
(b) score the statistics that need seed1 ALONE and say plainly which criteria remain unmeasured.

This script is (b). Two of the four criteria live entirely in seed1:
  * `emu_r`  = Pearson r of the per-cell MEDIAN of the OOS prediction against the per-cell median of the
    observed `Y` (seed1). Only the FLOOR/ceiling it is compared against needs seed2.
  * `sd_ratio` = `sd(pred)/sd(Y1)` over per-cell medians = criterion 2, the under-dispersion axis the whole
    milestone is about. `noise_floor_vs_emulator.py` computes it on the seed1-INNER-JOIN-seed2 cell set, so
    the number here is on a slightly WIDER cell basis and is therefore NOT interchangeable with the
    published historic figures. It IS a valid controlled comparison between two prediction sets scored HERE
    on the identical basis — which is the point: pass `PRED_A` and `PRED_B` and read the DELTA.

The per-cell reduction is IMPORTED from `noise_floor_vs_emulator.percell_table`, not reimplemented, so this
cannot drift from the gate's own definition of "per-cell median".

Usage (a controlled A/B on the same row universe):
    TABLE=/p/tmp/jamirp/emulator_global/slow_copula_pooled_w20_t8 \
    PRED_A=/p/tmp/jamirp/emulator_global/slow_copula_pooled_w20_t8 LABEL_A=pooled-t8 \
    PRED_B=/p/tmp/jamirp/emulator_global/capacity/pooled-env-qrf-b6x2M LABEL_B=pooled-env-qrf-b6x2M \
      python scripts/score_slow_copula_dispersion.py

Env: TABLE (the dir holding Y_*.f64 + cells.i64; defaults to PRED_A), PRED_A (required, a dir holding
     pred_*.f64 AND Y_*/cells — symlinks are fine), PRED_B (optional second prediction set),
     LABEL_A / LABEL_B (display names), MINSTEM (20, matching the gate), AXES (space-separated; defaults
     to the table manifest's `axes`).

NOT computable here, by construction — do not let its absence read as a pass:
     criterion 1 (`%GAP` to the attenuation-corrected ceiling) and criterion 4 (`r_center`).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from noise_floor_vs_emulator import percell_table  # noqa: E402  (path shim must precede the import)

PRED_A = os.environ.get("PRED_A", "")
PRED_B = os.environ.get("PRED_B", "")
TABLE = os.environ.get("TABLE", "") or PRED_A
LABEL_A = os.environ.get("LABEL_A", "A")
LABEL_B = os.environ.get("LABEL_B", "B")
MINSTEM = int(os.environ.get("MINSTEM", "20"))


def read_manifest(d):
    m = {}
    for ln in Path(d, "manifest_copula.txt").read_text().splitlines():
        if "\t" in ln:
            k, v = ln.split("\t", 1)
            m[k] = v
    return m


def spearman(a, b):
    ra = pl.Series(a).rank().to_numpy()
    rb = pl.Series(b).rank().to_numpy()
    return float(np.corrcoef(ra, rb)[0, 1])


def score(pred_dir, axes, label):
    """Per-cell-median stats for ONE prediction set, on the >=MINSTEM seed1 cell basis."""
    h = percell_table(pred_dir, with_pred=True, axes=axes)
    ncell_all = h.height
    # `percell_table` aliases the per-axis count to `n_<axis>` internally but emits a single collapsed
    # `nstem` column (all axes share one row set), so filter on that. Assert rather than guess, so a future
    # change to that helper surfaces here instead of silently disabling the >=MINSTEM gate.
    if "nstem" not in h.columns:
        raise SystemExit(f"FATAL: no `nstem` column from percell_table; got {h.columns}")
    h = h.filter(pl.col("nstem") >= MINSTEM)
    rows = {}
    for a in axes:
        y = h[f"y_{a}"].to_numpy()
        p = h[f"p_{a}"].to_numpy()
        ok = np.isfinite(y) & np.isfinite(p)
        y, p = y[ok], p[ok]
        rows[a] = {
            "emu_r": float(np.corrcoef(p, y)[0, 1]),
            "emu_rho": spearman(p, y),
            "sd_y": float(y.std()),
            "sd_ratio": float(p.std() / y.std()),
            "slope": float(np.polyfit(p, y, 1)[0]),
            "n": int(ok.sum()),
        }
    print(f"\n-- {label}: {pred_dir}")
    print(f"   cells: {ncell_all:,} in the table, {h.height:,} with >= {MINSTEM} stems")
    print(f"   {'axis':10s} {'emu_r':>8s} {'emu_rho':>8s} {'sd(Y1)':>12s} {'sd_ratio':>9s} {'slope':>8s}")
    for a in axes:
        r = rows[a]
        print(f"   {a:10s} {r['emu_r']:8.4f} {r['emu_rho']:8.4f} {r['sd_y']:12.5g} "
              f"{r['sd_ratio']:9.4f} {r['slope']:8.4f}")
    return rows


def main():
    if not PRED_A:
        raise SystemExit("FATAL: PRED_A is required (a dir holding pred_*.f64 + Y_*.f64 + cells.i64).")
    man = read_manifest(TABLE)
    axes = os.environ.get("AXES", "").split() or man["axes"].split()

    print("=" * 100)
    print("SEED1-ONLY between-cell dispersion + per-cell-median skill (ADR 0038)")
    print("=" * 100)
    print(f"   table    : {TABLE}")
    print(f"   scenario : {man.get('scenario', '?')}   n={int(man['n']):,}  ncond={man.get('ncond', '?')}")
    print(f"   axes     : {axes}   MINSTEM={MINSTEM}")
    print("   NOTE: sd_ratio here is on the seed1 >=MINSTEM basis, NOT the gate's seed1-INNER-seed2 basis,")
    print("         so it is not interchangeable with the published historic figures. A/B deltas measured")
    print("         HERE on one basis are valid; cross-basis absolute comparisons are not.")

    ra = score(PRED_A, axes, LABEL_A)
    if not PRED_B:
        print("\n   (no PRED_B — nothing to diff)")
    else:
        rb = score(PRED_B, axes, LABEL_B)
        print(f"\n-- DELTA ({LABEL_B} minus {LABEL_A}) — the controlled comparison")
        print(f"   {'axis':10s} {'d emu_r':>9s} {'d sd_ratio':>11s} {'d slope':>9s}   criterion-2 (sd_ratio >= 0.75)")
        for a in axes:
            d_r = rb[a]["emu_r"] - ra[a]["emu_r"]
            d_sd = rb[a]["sd_ratio"] - ra[a]["sd_ratio"]
            d_sl = rb[a]["slope"] - ra[a]["slope"]
            verdict = ""
            if a == "Wooddens":
                verdict = (f"{LABEL_A} {'PASS' if ra[a]['sd_ratio'] >= 0.75 else 'FAIL'}"
                           f" -> {LABEL_B} {'PASS' if rb[a]['sd_ratio'] >= 0.75 else 'FAIL'}")
            print(f"   {a:10s} {d_r:+9.4f} {d_sd:+11.4f} {d_sl:+9.4f}   {verdict}")

    print("\n   NOT MEASURED HERE (needs a seed2 realization of these cells, which does not exist for")
    print("   pooled/ssp370): criterion 1's %GAP to the attenuation-corrected ceiling, and criterion 4's")
    print("   r_center. Their absence is NOT a pass — see ADR 0038's open TODOs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
