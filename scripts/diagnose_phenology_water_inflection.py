#!/usr/bin/env python3
"""Price item (c1) of line M's photosynthesis shortlist: the GSI water limiter's INFLECTION basis.

WHY THIS EXISTS (`residual-diagnosis` §9 + §17 + ADR 0110's "check whether the C already EMITS it").
The handoff (`lines/M/STATE.md` §0-NEWEST step 1) names two remaining v1 simplifications in F's
otherwise-faithful `phenology_gsi_step`. This script prices the first one WITHOUT a simulation, and
its verdict decides whether a wiring change is worth building at all.

THE C's LIVE EXPRESSION (`phenology_gsi.c:63-79`, the `config->individual` branch -- and this config
runs `individual:true`, so the `else` branch is DEAD CODE here):

    if(soil->temp[0] < 10)   pft->phen_gsi.wscal = 1;          /* forced OPEN -- item (c2) */
    else                     target = 1/(1+exp(-sl*(pft->wscal*100 - pft->minwscal*100)))

  ⇒ the inflection is **`pft->minwscal`, a SAMPLED PER-STEM TRAIT**, and the par-file `wscal.base`
    that the dead `else` branch reads is inert. F's `PhenParams.wscal_base` is a per-PFT CONSTANT.

TWO SEPARABLE DEFECTS, AND THE SECOND IS NOT THE ONE THE HANDOFF NAMED. Conflating them would price
the wrong change (`residual-diagnosis` §11's "name the switch, then ask what else it controls"):

  (i) BIAS    -- is F's per-PFT constant the right CENTRE? `pft_phenparams`' docstring calls its
                 `wscal_base` "minwscal_med·100", but those medians were read off the par file's
                 interval declaration, and ADR 0047 established that a par-file `"median"` is a
                 GLOBAL DEFAULT that can lie OUTSIDE `[low,high]` -- ADR 0134 found the same shape
                 again on leaf longevity (par file 2.0 yr, realised median 0.286). So the pinned
                 constant is a claim to CHECK against the realised trait, per cell and per PFT.
  (ii) SPREAD -- even with the right centre, the C gives each stem its own threshold while F gives
                 every stem of a PFT one shared trajectory. This is the item as scoped.

THE PARAMETER ALGEBRA THAT MAKES THIS CHEAP (`residual-diagnosis` §17 step 1-2, which say to settle
the scaling and any redundancy before opening any data). The slope is per PERCENTAGE point and the
trait is a fraction, so the exponent is `sl*100*(w - m)` with `sl` ~ 5.0-5.24 for all seven tree
PFTs ⇒ ~524 per unit of water availability. The water limiter is therefore very nearly a HARD STEP
at `w = m`, with a 10-90 % transition width of only

    Δw = 2*ln(9)/(100*sl) ~ 0.0084       (0.84 percentage points of water availability)

⇒ the inflection VALUE barely matters as a value; what matters is WHICH SIDE OF IT each stem's
realised `w` sits on. So the question is not "how far apart are the two inflections?" but "does the
realised water availability fall inside the window where they disagree?", and a per-stem wiring
change can only buy anything where stems of one (cell, PFT) STRADDLE the threshold.

WHAT THIS SCRIPT MEASURES, in the units the consumer sees (the filter's steady-state target, which
enters `phen = tmin*tmax*light*wscal` multiplicatively):

  Panel 0  variability audit FIRST (ADR 0117): distinct-value count / min / max of `minwscal` per
           (cell, PFT), printing `const` rather than a spread for a degenerate column -- a scalar
           trait and an uncorrelated one produce the same degenerate output and have opposite
           implications.
  Panel A  BIAS: F's pinned `wscal_base` vs 100*realised median, per (cell, PFT).
  Panel B  SPREAD: the realised within-(cell, PFT) quantiles of `minwscal`.
  Panel C  the w-sweep. For each (cell, PFT) and each water availability `w` on a grid, the mean
           absolute filter-target difference of arm F (pinned constant) and arm M (median-corrected
           constant) against arm C (per-stem), plus the `w` at which each peaks and the WIDTH of the
           window where the difference exceeds 0.05. That window's width and location are the
           basis-free statement of what each defect can cost.
  Panel D  per-cell `CAN BIND` / `CANNOT BIND` verdict computed by the script (ADR 0104: have the
           SCRIPT compute the headline statistic), from each cell's own realised range.

⚠ THE BASIS LIMIT, STATED RATHER THAN IMPLIED. The `ind` table's `wscal_mean` is the annual mean of
a POTENTIAL leaf-on index that equals exactly 1 on a no-demand day (ADR 0051), so it OVERSTATES how
far above the threshold a stem sits during the growing season, and it is an annual mean where the
filter responds daily. Using it therefore biases every verdict here TOWARD `CANNOT BIND`. It is
reported as a locator only -- the decisive quantity is the realised DAILY `w` distribution, which
only F's own rollout carries, and Panel C's w-sweep is deliberately basis-free so that the daily
follow-up needs no re-derivation here.

Traps handled: grass rows carry zeroed tree fields so the filter is `Type <= 6` AND `D95max > 0`
(ADR 0110); the `ind` TXT/parquet dtypes are pinned; output goes to /p/tmp, never to a committed
fixture (`residual-diagnosis` §"A SCRIPT'S DEFAULT OUTPUT PATH").

Usage:  python3 scripts/diagnose_phenology_water_inflection.py
        SCENARIO=ssp370 python3 scripts/diagnose_phenology_water_inflection.py
"""

from __future__ import annotations

import math
import os
import sys

import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

from extract_biome_forcing import BIOMES  # noqa: E402  (repo-root path set above)

IND = {
    "historic": "/p/tmp/jamirp/emulator_global/ind_hist_seed1_all.parquet",
    "ssp370": "/p/tmp/jamirp/emulator_global/ind_ssp370_seed1_all.parquet",
}

# F's shipped per-PFT water-limiter parameters, verbatim from `FDiff.pft_phenparams`
# (src/fdiff.jl:1524-1548): id -> (wscal_sl, wscal_base). Trees are ids 0-6.
F_WSCAL = {
    0: (5.14, 60.0),
    1: (5.0, 10.0),
    2: (5.0, 10.0),
    3: (5.24, 20.96),
    4: (5.0, 25.0),
    5: (5.24, 25.0),
    6: (5.0, 35.0),
}

# The par-file `wscal.base` values, which the DEAD non-individual branch would read. Carried only so
# the audit can say whether F's pinned constant came from the par file or from a realised median.
PAR_BASE = {0: 4.997, 1: 0.5, 2: 0.5, 3: 20.96, 4: 20.96, 5: 20.96, 6: 2.344}

MIN_STEMS = 30          # coverage floor for a within-group panel (ADR 0118)
SEP_THRESHOLD = 0.05    # "the arms disagree" cut on the filter target, in filter units
W_GRID = [i / 200.0 for i in range(201)]


def sigmoid(x: float) -> float:
    """The C's `1/(1+exp(-x))`, overflow-guarded exactly as `FDiff.stable_sigmoid` is."""
    if x >= 0.0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def target(sl: float, w: float, base_pct: float) -> float:
    """The water filter's steady-state target: `1/(1+exp(-sl*(100*w - base_pct)))`."""
    return sigmoid(sl * (100.0 * w - base_pct))


def window_width(sl: float, ms: list[float], base_pct: float, thr: float) -> tuple[float, float]:
    """Width and centre of the `w` window where arm(base_pct) differs from per-stem by > `thr`."""
    hits = [
        w for w in W_GRID
        if abs(sum(target(sl, w, 100.0 * m) for m in ms) / len(ms) - target(sl, w, base_pct)) > thr
    ]
    if not hits:
        return (0.0, float("nan"))
    return (max(hits) - min(hits), 0.5 * (max(hits) + min(hits)))


def peak(sl: float, ms: list[float], base_pct: float) -> tuple[float, float]:
    """Max over `w` of |arm(base_pct) - per-stem mean|, and the `w` where it is attained."""
    best = (-1.0, float("nan"))
    for w in W_GRID:
        d = abs(sum(target(sl, w, 100.0 * m) for m in ms) / len(ms) - target(sl, w, base_pct))
        if d > best[0]:
            best = (d, w)
    return best


def main() -> int:
    scen = os.environ.get("SCENARIO", "historic")
    path = IND[scen]
    print(f"# phenology water-limiter INFLECTION basis audit -- scenario={scen}")
    print(f"# ind table: {path}")
    print(f"# 10-90 % transition width at sl=5.24: {2 * math.log(9) / (100 * 5.24):.5f} in w units")
    print()

    groups: dict[tuple[str, int], list[float]] = {}
    wmeans: dict[tuple[str, int], list[float]] = {}
    for name, cell in BIOMES.items():
        df = (
            pl.scan_parquet(path)
            .filter(
                (pl.col("Cell") == cell)
                & (pl.col("Type") <= 6)
                & (pl.col("D95max") > 0)
                & (pl.col("isdead") == 0)
            )
            .select(["Type", "minwscal", "wscal_mean"])
            .collect()
        )
        for pid in sorted(df["Type"].unique().to_list()):
            sub = df.filter(pl.col("Type") == pid)
            groups[(name, pid)] = sub["minwscal"].to_list()
            wmeans[(name, pid)] = sub["wscal_mean"].to_list()

    # ── Panel 0 — variability audit FIRST (ADR 0117) ──────────────────────────────────────────
    print("## Panel 0 — VARIABILITY AUDIT of the realised per-stem `minwscal` (ADR 0117)")
    print(f"{'cell':<22}{'pft':>4}{'n':>8}{'ndistinct':>11}{'min':>9}{'max':>9}  verdict")
    for (name, pid), ms in sorted(groups.items()):
        nd = len(set(ms))
        verdict = "const" if nd == 1 else "sampled"
        print(
            f"{name:<22}{pid:>4}{len(ms):>8}{nd:>11}"
            f"{min(ms):>9.4f}{max(ms):>9.4f}  {verdict}"
        )
    print()

    # ── Panel A — BIAS: is F's pinned constant the realised centre? ───────────────────────────
    print("## Panel A — BIAS: F's pinned `wscal_base` vs 100 x the REALISED median `minwscal`")
    print("##   (par_base = the par-file value the DEAD non-individual branch reads)")
    print(f"{'cell':<22}{'pft':>4}{'F_base':>9}{'realised':>10}{'par_base':>10}{'F-real':>9}")
    for (name, pid), ms in sorted(groups.items()):
        if pid not in F_WSCAL:
            continue
        med = 100.0 * sorted(ms)[len(ms) // 2]
        fb = F_WSCAL[pid][1]
        print(
            f"{name:<22}{pid:>4}{fb:>9.2f}{med:>10.2f}"
            f"{PAR_BASE[pid]:>10.3f}{fb - med:>9.2f}"
        )
    print()

    # ── Panel B — SPREAD within (cell, PFT) ───────────────────────────────────────────────────
    print("## Panel B — SPREAD of the realised per-stem inflection within (cell, PFT), in % units")
    print(f"{'cell':<22}{'pft':>4}{'q10':>8}{'q50':>8}{'q90':>8}{'q90-q10':>9}{'sd':>8}")
    for (name, pid), ms in sorted(groups.items()):
        s = sorted(100.0 * m for m in ms)
        n = len(s)
        q10, q50, q90 = s[int(0.1 * n)], s[n // 2], s[min(int(0.9 * n), n - 1)]
        mu = sum(s) / n
        sd = math.sqrt(sum((x - mu) ** 2 for x in s) / n)
        print(f"{name:<22}{pid:>4}{q10:>8.2f}{q50:>8.2f}{q90:>8.2f}{q90 - q10:>9.2f}{sd:>8.2f}")
    print()

    # ── Panel C — the basis-free w-sweep, in filter-output units ──────────────────────────────
    print("## Panel C — w-SWEEP: max |arm - per-stem| filter-target difference, and the window")
    print("##   arm F = F's pinned constant; arm M = the median-corrected constant.")
    print("##   `win` = width in w units of the region where the difference exceeds "
          f"{SEP_THRESHOLD}; `at` = its centre.")
    print(
        f"{'cell':<22}{'pft':>4}{'n':>7}"
        f"{'peakF':>8}{'w@F':>7}{'winF':>7}{'atF':>7}"
        f"{'peakM':>8}{'w@M':>7}{'winM':>7}{'atM':>7}"
    )
    rows = []
    for (name, pid), ms in sorted(groups.items()):
        if pid not in F_WSCAL or len(ms) < MIN_STEMS:
            continue
        sl, fb = F_WSCAL[pid]
        med_pct = 100.0 * sorted(ms)[len(ms) // 2]
        pf, wf = peak(sl, ms, fb)
        pm, wm = peak(sl, ms, med_pct)
        winf, atf = window_width(sl, ms, fb, SEP_THRESHOLD)
        winm, atm = window_width(sl, ms, med_pct, SEP_THRESHOLD)
        print(
            f"{name:<22}{pid:>4}{len(ms):>7}"
            f"{pf:>8.3f}{wf:>7.3f}{winf:>7.3f}{atf:>7.3f}"
            f"{pm:>8.3f}{wm:>7.3f}{winm:>7.3f}{atm:>7.3f}"
        )
        rows.append((name, pid, len(ms), pf, wf, winf, atf, pm, wm, winm, atm, med_pct, sl, fb))
    print()

    # ── Panel D — per-cell verdict, computed here (ADR 0104) ──────────────────────────────────
    print("## Panel D — VERDICT per cell. `CAN BIND` needs a window of non-zero width AND the")
    print("##   realised water availability reaching into it. `wscal_mean` is an ANNUAL MEAN of a")
    print("##   POTENTIAL index that is exactly 1 on a no-demand day (ADR 0051), so it OVERSTATES")
    print("##   `w` and every verdict below is biased TOWARD `CANNOT BIND` -- an upper-bound-free")
    print("##   locator, not the daily measurement.")
    print(
        f"{'cell':<22}{'pft':>4}{'w_q10':>8}{'w_q50':>8}"
        f"{'winF':>7}{'atF':>7}  verdict(F){'':>4}  verdict(M)"
    )
    for (name, pid, n, pf, _wf, winf, atf, pm, _wm, winm, atm, _med, _sl, _fb) in rows:
        ws = sorted(wmeans[(name, pid)])
        wq10, wq50 = ws[int(0.1 * n)], ws[n // 2]
        vf = _verdict(winf, atf, wq10, wq50, pf)
        vm = _verdict(winm, atm, wq10, wq50, pm)
        print(
            f"{name:<22}{pid:>4}{wq10:>8.4f}{wq50:>8.4f}"
            f"{winf:>7.3f}{atf:>7.3f}  {vf:<14}  {vm}"
        )
    print()

    # ── Panel E — the SATURATION / STRADDLE audit, which is what actually decides this ─────────
    print("## Panel E — SATURATION vs STRADDLE, evaluated at each group's own realised water")
    print("##   availability. Because the transition band is only ~0.008 wide in `w`, the filter")
    print("##   is almost always SATURATED -- pinned at 1 (open) or 0 (closed) -- and in a")
    print("##   saturated regime the inflection VALUE is inert: neither defect can matter. What")
    print("##   matters is a STRADDLE: the two inflections landing on OPPOSITE sides, which turns")
    print("##   a parameter error into a binary difference in leaf display.")
    print("##   `sig_F` uses F's pinned constant, `sig_C` the realised median, both at `w_q50`.")
    print(f"{'cell':<22}{'pft':>4}{'w_q50':>8}{'m_F':>7}{'m_C':>7}"
          f"{'sig_F':>8}{'sig_C':>8}{'|diff|':>8}  regime")
    straddles = []
    for (name, pid, n, _pf, _wf, _winf, _atf, _pm, _wm, _winm, _atm, med, sl, fb) in rows:
        ws = sorted(wmeans[(name, pid)])
        wq50 = ws[n // 2]
        sf = target(sl, wq50, fb)
        sc = target(sl, wq50, med)
        d = abs(sf - sc)
        if d > 0.5:
            regime = "STRADDLE — binary difference"
            straddles.append((name, pid, sf, sc))
        elif min(sf, sc) > 0.99:
            regime = "saturated OPEN — inert"
        elif max(sf, sc) < 0.01:
            regime = "saturated CLOSED — inert"
        else:
            regime = "in transition"
        print(
            f"{name:<22}{pid:>4}{wq50:>8.4f}{fb:>7.2f}{med:>7.2f}"
            f"{sf:>8.4f}{sc:>8.4f}{d:>8.4f}  {regime}"
        )
    print()
    if straddles:
        print("## ⇒ STRADDLE FOUND — this is the finding, not the spread:")
        for (name, pid, sf, sc) in straddles:
            print(f"##   {name} PFT {pid}: F's water filter reads {sf:.4f} where the C's reads "
                  f"{sc:.4f}.")
        print("##   ⚠ And `wscal_mean` OVERSTATES `w` (it is 1 on a no-demand day, ADR 0051), so")
        print("##   the realised growing-season `w` sits LOWER than the value used above -- which")
        print("##   pushes the C's filter further CLOSED and makes the straddle wider, not")
        print("##   narrower. The direction of this finding is therefore robust to that basis")
        print("##   limit; only its exact size is not.")
    else:
        print("## ⇒ no straddle at any group: the inflection is inert at every cell measured.")
    print()
    print("# Reminder: the water filter is FORCED OPEN below 10 degC soil temperature")
    print("# (`phenology_gsi.c:67`), so item (c2) bounds how many days this term is live at all.")
    return 0


def _verdict(win: float, at: float, wq10: float, wq50: float, pk: float) -> str:
    """`CAN BIND` / `CANNOT BIND` from the window's width and where the realised `w` sits."""
    if win <= 0.0 or pk <= SEP_THRESHOLD:
        return "CANNOT BIND"
    lo, hi = at - 0.5 * win, at + 0.5 * win
    if wq10 > hi:
        return "CANNOT BIND"      # even the driest decile sits above the disagreement window
    if wq50 < lo:
        return "CANNOT BIND"      # the whole population sits below it -- both arms read ~0
    return "CAN BIND"


if __name__ == "__main__":
    raise SystemExit(main())
