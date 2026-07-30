#!/usr/bin/env python3
"""Score the POOLED KS of a copula table's OOS predictions — the ADR-0030 gate's criterion 3.

WHY THIS EXISTS (milestone S2 / ADR 0038)
-----------------------------------------
ADR 0030 §4 states S2's four success criteria, and the THIRD is "**pooled KS** not degraded (<= 0.02)".
But `scripts/eval_slow_copula.jl` prints `nqrmse` (an IQR-normalized RMSE over five quantiles) and
`scripts/noise_floor_vs_emulator.py` prints neither — so a capacity/conditioning rung evaluated by those two
scripts alone has **no measurement of criterion 3 at all**. Reading `nqrmse` in its place is a basis
substitution, and ADR 0036 already records this line publishing a statistic that was not the one the
argument required. `agb` is the standing proof they are not interchangeable: `nqrmse` 0.643 vs `KS` 0.011 on
the SAME distribution, because `nqrmse` divides every quantile error by ONE IQR and `q95/IQR ~ 10`.

So this script measures the actual criterion, with the SAME `ks2` the published `metrics_traits.txt` numbers
came from (imported from `plot_slow_emulator_validation.py`, not re-implemented — ADR 0031).

It reports, per production axis:
  * `pooled_KS`            — criterion 3. Compare against the t8 baseline on the SAME axis.
  * `median_percell_KS`    — the per-cell marginal reproduction (the fig-11 statistic), for context.
  * `nqrmse` / `med_rel_q` — recomputed here so one table carries all four numbers on one row universe.

Usage (SLURM; ~20 GB peak, a few minutes per axis):
    SHADOW=/p/tmp/jamirp/emulator_global/capacity/qrf-b6x2M \
      scripts/sbatch_python.sh S-ks-qrfb6x2M scripts/score_slow_copula_ks.py

Env: SHADOW (a table dir holding cells.i64 / Y_<axis>.f64 / pred_<axis>.f64 + manifest_copula.txt),
     AXES (default = the manifest's production `axes`), MINSTEM (20, for the per-cell KS filter),
     SUBSAMPLE_KS (0 = exact on all rows; N>0 = a deterministic N-row subsample for the POOLED KS only,
     for a quick look — the headline number must be the exact one).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "scripts"))
# The ONE KS definition (hoisted to module level there precisely so this import is possible).
from plot_slow_emulator_validation import ks2  # noqa: E402

SHADOW = os.environ.get("SHADOW", "")
MINSTEM = int(os.environ.get("MINSTEM", "20"))
SUBSAMPLE_KS = int(os.environ.get("SUBSAMPLE_KS", "0"))
QS = np.array([0.05, 0.25, 0.5, 0.75, 0.95])


def read_manifest(d):
    m = {}
    for ln in Path(d, "manifest_copula.txt").read_text().splitlines():
        if "\t" in ln:
            k, v = ln.split("\t", 1)
            m[k] = v
    return m


def main():
    if not SHADOW:
        raise SystemExit("FATAL: set SHADOW to a table dir with pred_<axis>.f64")
    d = Path(SHADOW)
    man = read_manifest(d)
    axes = os.environ.get("AXES", "").split() or man["axes"].split()
    n = int(man["n"])

    cells = np.fromfile(d / "cells.i64", dtype="<i8")
    assert cells.size == n, f"cells.i64 {cells.size} != manifest n {n}"

    print("=" * 104)
    print("POOLED KS — ADR-0030 gate criterion 3 (the statistic the criterion actually names)")
    print("=" * 104)
    print(f"   table    : {d}")
    print("   capacity : ntrees/subsample/depth are NOT in the manifest — read them from the job log")
    print(f"   n={n:,}  ncond={man['ncond']}  axes={' '.join(axes)}  MINSTEM={MINSTEM}"
          f"  SUBSAMPLE_KS={SUBSAMPLE_KS or 'exact'}")

    # Sort ONCE by cell so the per-cell KS is a contiguous-slice walk, not a mask per cell
    # (the plotting script's "SORT-GROUP ONCE" trick).
    order = np.argsort(cells, kind="stable")
    cs = cells[order]
    bounds = np.searchsorted(cs, np.unique(cs), "left")
    ends = np.append(bounds[1:], cs.size)
    uniq = np.unique(cs)

    print(f"\n   {'axis':10s} {'pooled_KS':>10s} {'med_pc_KS':>10s} {'nqrmse':>8s} {'med_rel_q':>10s}"
          f" {'cells':>8s}")
    rows = {}
    for ax in axes:
        obs = np.fromfile(d / f"Y_{ax}.f64", dtype="<f8")
        prd = np.fromfile(d / f"pred_{ax}.f64", dtype="<f8")
        assert obs.size == n and prd.size == n, f"axis {ax}: length mismatch"
        assert np.isfinite(prd).all(), f"axis {ax}: non-finite predictions (an unfilled test fold?)"

        if SUBSAMPLE_KS > 0 and SUBSAMPLE_KS < n:
            rng = np.random.default_rng(20260730)
            idx = rng.choice(n, size=SUBSAMPLE_KS, replace=False)
            pooled = ks2(prd[idx], obs[idx])
        else:
            pooled = ks2(prd, obs)

        oq, pq = np.quantile(obs, QS), np.quantile(prd, QS)
        iqr = float(np.quantile(obs, 0.75) - np.quantile(obs, 0.25))
        nq = float(np.sqrt(np.mean((pq - oq) ** 2)) / iqr) if iqr > 0 else float("nan")
        with np.errstate(invalid="ignore", divide="ignore"):
            rel_q = np.abs(pq - oq) / np.where(np.abs(oq) > 0, np.abs(oq), np.nan)
        med_rel_q = float(np.nanmedian(rel_q))

        po, oo = prd[order], obs[order]
        kss = []
        for gi in range(uniq.size):
            s, e = bounds[gi], ends[gi]
            if e - s >= MINSTEM:
                kss.append(ks2(po[s:e], oo[s:e]))
        med_pc = float(np.median(kss)) if kss else float("nan")

        rows[ax] = (pooled, med_pc, nq, med_rel_q, len(kss))
        print(f"   {ax:10s} {pooled:10.4f} {med_pc:10.4f} {nq:8.4f} {med_rel_q:10.4f} {len(kss):8d}",
              flush=True)
        del obs, prd, po, oo

    # The baseline is READ from the published metrics file, never hardcoded here. A hardcoded copy is how
    # this very script first shipped the POOLED-scenario values (SLA 0.0039 / W 0.0065 / D95max 0.0020 /
    # minwscal 0.0040) mislabelled as `historic` — against which a rung that IMPROVES on all four axes reads
    # as "degraded on three". The historic and pooled generations have genuinely different baselines
    # (historic 0.0051/0.0052/0.0069/0.0115 over 52 516 cells; pooled over 57 719), so the scenario must be
    # matched, and matching it by hand is the ADR-0031 two-copies failure mode.
    scen = man.get("scenario", "")
    mt = _REPO / "figures" / "emulator_validation" / f"{scen}_t8" / "metrics_traits.txt"
    print(f"\n   t8 BASELINE for criterion 3, read from {mt}:")
    if mt.is_file():
        base = {}
        for ln in mt.read_text().splitlines():
            p = ln.split("\t")
            if len(p) > 8 and "pooled_KS" in p:
                base[p[0]] = float(p[p.index("pooled_KS") + 1])
        print(f"     {'axis':10s} {'t8 pooled_KS':>13s} {'this run':>10s} {'delta':>9s}  criterion 3")
        for ax in axes:
            if ax in base and ax in rows:
                b, v = base[ax], rows[ax][0]
                ok = "PASS (<=0.02)" + ("" if v <= b else "  [but WORSE than t8 on this axis]")
                print(f"     {ax:10s} {b:13.4f} {v:10.4f} {v - b:+9.4f}  "
                      f"{ok if v <= 0.02 else 'FAIL (>0.02)'}")
    else:
        print("     NOT FOUND — regenerate the figure set for this scenario, or compare by hand against"
              f" the {scen} generation (NOT the pooled one).")
    print("\n   criterion 3 (ADR 0030 §4) = pooled KS 'not degraded (<= 0.02)'. The numeric bound and the")
    print("   'not degraded vs t8' reading can disagree; ADR 0038 must state which one it applies.")
    print("   NOTE: pooled KS and nqrmse are DIFFERENT statistics and can disagree in MAGNITUDE (agb:")
    print("   nqrmse 0.643 vs KS 0.012, ~55x) and in DIRECTION (b12x500k D95max: nqrmse 2x worse, KS 2x")
    print("   better). Quote KS for criterion 3 — that is the statistic the criterion names.")


if __name__ == "__main__":
    main()
