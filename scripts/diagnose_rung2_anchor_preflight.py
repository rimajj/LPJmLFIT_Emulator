#!/usr/bin/env python3
"""diagnose_rung2_anchor_preflight.py — what ADR 0103's level anchor WOULD do in the rung-2 path.

ADR 0185 §7.2 names wiring the level anchor into the rung-2 harness as the next work, and its §7.5
pre-registers the pass criterion. This script is the step BEFORE that: it derives what the anchor
reduces to in this harness and pre-flights the answer against the arm logs already on disk, so the
design choice (which `a`, and whether the pre-registered criterion is even reachable) is made from
measurement rather than from the coupled path's single-cell Hainich sweep.

THE ALGEBRA — and it does NOT carry over unchanged from `slow.jl`.

`reconcile_demography!` forms

    r      = target / n_prev
    D_want = target / patch_area          # the map's absolute prediction, stems per m^2
    rho    = r^(1-a) * (D_want/D)^a       # D = the live roster's density

with `D = sum(nind)` over the WHOLE roster, because the coupled path feeds that same whole roster to
`flux_feature_vector`. **This harness does not**: `pools_of`'s docstring makes the feature row and
the count target the >5 m EMITTED population (the `ind` writer's cut, `fwriteoutput_ind.c:84`) while
the thinning acts on every tree. So the population `target` lives on is the emitted one, and the
anchor's `D` must be the emitted density `n_emit/patch_area` — anything else compares the map's
prediction against a count it was never trained on. Then `patch_area` CANCELS:

    D_want/D = (target/patch_area) / (n_emit/patch_area) = target / n_emit

so in this harness the anchor is exactly

    rho_eff = (target/n_prev)^(1-a) * (target/n_emit)^a        # then clamp(., 0.7, 1.3)

Two consequences that decide the experiment, both checked below rather than asserted:

  (1) **In `roster` mode the anchor is IDENTICALLY INERT.** There `n_prev := n_emit` by definition,
      so both factors are the same number and `rho_eff = rho` for every `a`. The anchor is therefore
      only meaningful on the `predict` axis ADR 0185 established — it could not have been measured
      before, which is the mechanical reason it sat unreachable rather than an oversight.

  (2) **`a` interpolates the rho conversion between the two modes, but NOT the feature row.**
      `n_prev` is also feature 3 of the row, and the anchor does not touch it, so `target` keeps its
      free-running recursion at every `a`. `a = 1` is therefore *not* a return to `roster` mode: it
      places the stand on a target a free recursion produced. That is what keeps ADR 0184's tether
      off, and it is why the separability gate can still be read after the anchor is on.

WHAT THIS SCRIPT CANNOT TELL YOU. Every number here is counterfactual on trajectories that were run
WITHOUT the anchor: once it is on, the arm kills differently, the C grows a different stand, and the
gap it is closing moves. This is a first-order sizing of sign, magnitude, clamp incidence and time
constant — NOT a prediction of the matrix. It exists to stop a 264-job run whose `a` cannot reach
its own criterion.

Env:
  ROOT     dump root                 (default /p/tmp/jamirp/S_rung2)
  ARMS     comma list                (default S0,S0h,S1,NP)
  ANCHORS  comma list of `a`         (default 0.1,0.25,0.5,1.0)
  TERMW    terminal window, years    (default 20 — the window the response statistic reads)
"""

from __future__ import annotations

import math
import os
import re
import statistics
import sys
from collections import defaultdict

ROOT = os.environ.get("ROOT", "/p/tmp/jamirp/S_rung2")
ARMS = os.environ.get("ARMS", "S0,S0h,S1,NP").split(",")
ANCHORS = [float(x) for x in os.environ.get("ANCHORS", "0.1,0.25,0.5,1.0").split(",")]
TERMW = int(os.environ.get("TERMW", "20"))

RHO_LO, RHO_HI = 0.7, 1.3
DIR_RE = re.compile(r"S_r2s_(\w+?)_c(\d+)_(REC|NP|S0h|S0|S1)_(roster|predict)_s(\d+)_apply$")


def read_log(path):
    """The `L` rows as dicts, keyed by the `#H` header (which names the L tag as field 0)."""
    rows = []
    with open(path) as fh:
        head = None
        for line in fh:
            if line.startswith("#H"):
                head = line.split()[1:]
                continue
            if not line.startswith("L ") or head is None:
                continue
            parts = line.split()
            if len(parts) != len(head):
                continue
            rows.append(dict(zip(head, parts, strict=True)))
    return rows


def legs():
    """(scenario, cell, arm, mode, seed) -> arm-log path, for every apply dir that has one."""
    out = {}
    for name in sorted(os.listdir(ROOT)):
        m = DIR_RE.match(name)
        if not m:
            continue
        scen, cell, arm, mode, seed = m.groups()
        log = os.path.join(ROOT, name, "s_arm_log.txt")
        if os.path.isfile(log):
            out[(scen, int(cell), arm, mode, int(seed))] = log
    return out


def rho_eff(target, nprev, nemit, a):
    """The harness form of ADR 0103's geometric blend, before the clamp."""
    r = target / (nprev + 1.0e-12)
    if a <= 0.0 or nemit <= 0.0 or target <= 0.0:
        return r
    return r ** (1.0 - a) * (target / nemit) ** a


def q(xs, p):
    if not xs:
        return float("nan")
    s = sorted(xs)
    return s[min(len(s) - 1, max(0, int(round(p * (len(s) - 1)))))]


def panel_inertness(found):
    print("=" * 96)
    print("(1) INERTNESS IN `roster` MODE — n_prev vs n_emit over every roster-mode row.")
    print("    If these are the same number then rho_eff = rho for EVERY a, by algebra, and the")
    print("    anchor is measurable only on the `predict` axis.")
    ident, total, worst = 0, 0, 0.0
    for key, log in found.items():
        if key[3] != "roster" or key[2] == "REC":
            continue
        for row in read_log(log):
            ne, npv = float(row["n_emit"]), float(row["n_prev"])
            total += 1
            d = abs(ne - npv)
            worst = max(worst, d)
            if d == 0.0:
                ident += 1
    if total:
        pct = 100.0 * ident / total
        print(f"    rows {total} · bit-identical {ident} ({pct:.2f} %) · max |diff| {worst:g}")
    else:
        print("    no roster-mode rows on disk")


def panel_reachability():
    """Is the departure the anchor acts on a COUNT departure — and does the target point at FIT?

    The anchor's ONLY lever is to place the live count on the map's `target`. It can therefore
    close a level departure if and only if `target` is nearer FIT's own count than the live count
    already is. If the map, reading a displaced stand, predicts a count displaced by the same
    amount, anchoring drives the stand onto a wrong number and the departure survives. That is
    arithmetic over data already on disk — it does not need the matrix.

    ⚠ THE BASIS IS IMPORTED, NOT RE-DERIVED. ADR 0185 §7.5's criterion ("agb departure below
    +40 %") is written against `diagnose_rung2_map_target_response.py`'s definition: a PATCH-MEAN
    at the SINGLE terminal year, arm averaged over seeds, then the MEDIAN over cells, behind that
    script's coverage gate. A 20-yr window, a mean over cells, or a mean of per-patch ratios all
    give materially different numbers on the same data (measured: S1 ssp370 n_emit +37 % against
    the ADR's −2.9 %), so a panel that speaks to the criterion must reuse the scorer's own `Leg`
    rather than re-implement it — the ADR 0060 reference-basis rule.
    """
    os.environ.setdefault("NPREV", "predict")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import diagnose_rung2_map_target_response as S  # noqa: N812  (the shipped scorer, imported)

    print("=" * 96)
    print("(4) IS THE DEPARTURE A *COUNT* DEPARTURE, AND DOES THE TARGET POINT AT FIT?")
    print(f"    basis: IMPORTED from {os.path.basename(S.__file__)} — patch-mean at the terminal")
    print(f"    year, seeds averaged, median over cells, its coverage gate. NPREV={S.NPREV}.")
    print()
    print("      dN     = (arm n_emit − REC n_emit)/REC   the COUNT departure the anchor acts on")
    print("      dAGB   = (arm agb    − REC agb   )/REC   the level ADR 0185 §7.5 gates at +40 %")
    print("      dTGT   = (arm target − REC n_emit)/REC   where the anchor would DRIVE the count")
    print("      dAGBr  = (1+dAGB)/(1+dTGT) − 1           the agb departure that SURVIVES a")
    print("               perfect anchor, if agb followed the count proportionally — the most")
    print("               generous bound there is, since the anchor cannot touch per-stem mass.")

    legs = {}
    for name in sorted(os.listdir(S.ROOT)):
        m = S.APPLY_RE.match(name)
        if not m:
            continue
        scen, cell, arm, seed = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        path = os.path.join(S.ROOT, name, "s_arm_log.txt")
        if not os.path.isfile(path):
            continue
        if not S.run_completed(scen, cell, arm, S.NPREV, seed):
            continue
        leg = S.read_arm_log(path, scen)
        if leg.complete(scen):
            legs[(cell, arm, seed, scen)] = leg
    for (cell, scen), leg in S.read_rec_csv(S.RECCSV).items():
        if leg.complete(scen):
            legs[(cell, "REC", 1, scen)] = leg

    nliving = S.read_nliving(S.NLIVING)
    gain = sorted(c for c, v in nliving.items() if v > 0)
    thin = sorted(c for c, v in nliving.items() if v <= 0)
    iagb = S.STAND_FEATS.index("agb")

    for cs, lbl in ((gain, "FIT-GAIN"), (thin, "FIT-THIN")):
        cs = [c for c in cs if any(k[0] == c for k in legs)]
        print()
        print(f"    --- {lbl} cells ({len(cs)}) ---")
        print(f"    {'arm':<5} {'leg':<9} {'dN':>9} {'dAGB':>9} {'dTGT':>9} {'dAGBr':>9}  <40%?")
        for arm in S.ARMS:
            for scen in ("historic", "ssp370"):
                dn, da, dt, dr = [], [], [], []
                for c in cs:
                    r = [v for (cc, ar, _s, sc), v in legs.items()
                         if cc == c and ar == "REC" and sc == scen]
                    aa = [v for (cc, ar, _s, sc), v in legs.items()
                          if cc == c and ar == arm and sc == scen]
                    if not r or not aa:
                        continue
                    rn, ra = r[0].N, r[0].stand[iagb]
                    an = sum(x.N for x in aa) / len(aa)
                    ag = sum(x.stand[iagb] for x in aa) / len(aa)
                    tg = sum(x.T for x in aa) / len(aa)
                    if not rn or not ra:
                        continue
                    dn.append((an - rn) / abs(rn))
                    da.append((ag - ra) / abs(ra))
                    dt.append((tg - rn) / abs(rn))
                    dr.append((1.0 + da[-1]) / (1.0 + dt[-1]) - 1.0 if dt[-1] != -1.0 else nan())
                if not dn:
                    continue
                mr = S.median(dr)
                print(
                    f"    {arm:<5} {scen:<9} {S.median(dn):>+8.1%} {S.median(da):>+8.1%} "
                    f"{S.median(dt):>+8.1%} {mr:>+8.1%}  {'yes' if mr < 0.40 else 'NO'}"
                )
    print()


def nan():
    return float("nan")


def panel_trajectory():
    """Was the count departure LARGE EARLIER, so that an anchor acting all along would have

    prevented the mass from accumulating? This is the one alternative that would rescue the
    anchor's case, and it is the difference between "the count channel is saturated" and "the
    count channel was open and we read it after it closed". Same imported basis as panel (4)
    (patch-mean per year, seeds averaged, median over cells, the scorer's coverage gate), but
    resolved in TIME instead of collapsed onto the terminal year.
    """
    os.environ.setdefault("NPREV", "predict")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import diagnose_rung2_map_target_response as S  # noqa: N812

    print("=" * 96)
    print("(5) THE DEPARTURE TRAJECTORY — was the COUNT channel ever open on the ssp370 leg?")
    print("    If dN is large early and ~0 late, an anchor acting throughout would have stopped")
    print("    the mass accumulating, and panel (4)'s terminal read understates it. If dN is")
    print("    small THROUGHOUT while dAGB grows, the count channel was never the lever.")
    print("    Median over the FIT-gain cells of the per-year patch-mean ratio, arm vs REC.")

    iagb = S.STAND_FEATS.index("agb")
    rec_yr, arm_yr = {}, {}
    for name in sorted(os.listdir(S.ROOT)):
        m = S.APPLY_RE.match(name)
        if not m:
            continue
        scen, cell, arm, seed = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        if scen != "ssp370":
            continue
        path = os.path.join(S.ROOT, name, "s_arm_log.txt")
        if not os.path.isfile(path) or not S.run_completed(scen, cell, arm, S.NPREV, seed):
            continue
        if not S.read_arm_log(path, scen).complete(scen):
            continue
        acc = defaultdict(lambda: [0.0, 0.0, 0.0, 0])
        with open(path) as fh:
            cols = {}
            for line in fh:
                if line.startswith("#H L"):
                    cols = {n: i + 1 for i, n in enumerate(line.split()[2:])}
                    continue
                if not line.startswith("L ") or not cols:
                    continue
                f = line.split()
                y = int(f[cols["year"]])
                a = acc[y]
                a[0] += float(f[cols["n_emit"]])
                a[1] += float(f[cols["agb_rt"]])
                a[2] += float(f[cols["target"]])
                a[3] += 1
        for y, a in acc.items():
            arm_yr.setdefault((arm, cell, y), []).append((a[0] / a[3], a[1] / a[3], a[2] / a[3]))

    with open(S.RECCSV) as fh:
        cols = None
        acc = defaultdict(lambda: [0.0, 0.0, 0])
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split(",")
            if cols is None:
                cols = {n: i for i, n in enumerate(f)}
                continue
            if f[cols["scenario"]] != "ssp370":
                continue
            k = (int(f[cols["cell"]]), int(f[cols["year"]]))
            acc[k][0] += float(f[cols["n_emit"]])
            acc[k][1] += float(f[cols[S.STAND_FEATS[iagb]]])
            acc[k][2] += 1
    for k, a in acc.items():
        rec_yr[k] = (a[0] / a[2], a[1] / a[2])

    nliving = S.read_nliving(S.NLIVING)
    gain = [c for c, v in nliving.items() if v > 0]
    years = [2020, 2030, 2040, 2050, 2060, 2070, 2080, 2090, 2100]
    print()
    hd = f"    {'arm':<5} {'stat':<6}" + "".join(f"{y:>8}" for y in years)
    for arm in S.ARMS:
        print()
        print(hd if arm == S.ARMS[0] else "")
        for stat in ("dN", "dAGB", "dTGT"):
            row = f"    {arm:<5} {stat:<6}"
            for y in years:
                vals = []
                for c in gain:
                    r = rec_yr.get((c, y))
                    v = arm_yr.get((arm, c, y))
                    if not r or not v or not r[0] or not r[1]:
                        continue
                    n = sum(x[0] for x in v) / len(v)
                    g = sum(x[1] for x in v) / len(v)
                    t = sum(x[2] for x in v) / len(v)
                    vals.append(
                        (n - r[0]) / abs(r[0]) if stat == "dN"
                        else (g - r[1]) / abs(r[1]) if stat == "dAGB"
                        else (t - r[0]) / abs(r[0])
                    )
                row += f"{S.median(vals):>+8.0%}" if vals else f"{'--':>8}"
            print(row)
    print()


def panel_percapita():
    """WHERE the excess mass sits: in more stems, or in bigger stems?

    `agb` and `n_emit` are both patch-means on the same emitted population, so `agb/n_emit` is
    the mean above-ground biomass PER STEM and the departure decomposes exactly:

        (1 + dAGB) = (1 + dN) * (1 + dAGBperstem)

    A count anchor can only move the first factor. This panel prints the second beside it, with
    the height and age departures that have to corroborate it — if the excess really is per-stem
    mass then `hmean`/`hmax`/`age_mean` must depart in the same direction, and if they do not,
    the reading is wrong and the arithmetic is hiding something.
    """
    os.environ.setdefault("NPREV", "predict")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import diagnose_rung2_map_target_response as S  # noqa: N812

    print("=" * 96)
    print("(6) IS THE EXCESS MASS IN MORE STEMS OR IN BIGGER STEMS?")
    print("    (1+dAGB) = (1+dN)*(1+dPER), so dPER is what the count anchor provably cannot")
    print("    reach. hmean/hmax/age must move with dPER or the decomposition is not physical.")
    print()
    print(f"    {'arm':<5} {'leg':<9} {'dN':>8} {'dAGB':>9} {'dPER':>9} "
          f"{'hmean':>8} {'hmax':>8} {'age':>8}")

    legs = {}
    for name in sorted(os.listdir(S.ROOT)):
        m = S.APPLY_RE.match(name)
        if not m:
            continue
        scen, cell, arm, seed = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        path = os.path.join(S.ROOT, name, "s_arm_log.txt")
        if not os.path.isfile(path) or not S.run_completed(scen, cell, arm, S.NPREV, seed):
            continue
        leg = S.read_arm_log(path, scen)
        if leg.complete(scen):
            legs[(cell, arm, seed, scen)] = leg
    for (cell, scen), leg in S.read_rec_csv(S.RECCSV).items():
        if leg.complete(scen):
            legs[(cell, "REC", 1, scen)] = leg

    nliving = S.read_nliving(S.NLIVING)
    gain = [c for c, v in nliving.items() if v > 0]
    idx = {n: S.STAND_FEATS.index(n) for n in ("agb", "hmean", "hmax", "age_mean")}

    for arm in S.ARMS:
        for scen in ("historic", "ssp370"):
            got = defaultdict(list)
            for c in gain:
                r = [v for (cc, ar, _s, sc), v in legs.items()
                     if cc == c and ar == "REC" and sc == scen]
                aa = [v for (cc, ar, _s, sc), v in legs.items()
                      if cc == c and ar == arm and sc == scen]
                if not r or not aa or not r[0].N:
                    continue
                rn = r[0].N
                an = sum(x.N for x in aa) / len(aa)
                got["dN"].append((an - rn) / abs(rn))
                for nm, i in idx.items():
                    rv = r[0].stand[i]
                    av = sum(x.stand[i] for x in aa) / len(aa)
                    if rv:
                        got[nm].append((av - rv) / abs(rv))
                if r[0].stand[idx["agb"]] and rn and an:
                    rp = r[0].stand[idx["agb"]] / rn
                    ap = (sum(x.stand[idx["agb"]] for x in aa) / len(aa)) / an
                    got["dPER"].append((ap - rp) / abs(rp))
            if not got["dN"]:
                continue
            print(
                f"    {arm:<5} {scen:<9} {S.median(got['dN']):>+7.1%} "
                f"{S.median(got['agb']):>+8.1%} {S.median(got['dPER']):>+8.1%} "
                f"{S.median(got['hmean']):>+7.1%} {S.median(got['hmax']):>+7.1%} "
                f"{S.median(got['age_mean']):>+7.1%}"
            )
    print()


def main():
    found = legs()
    if not found:
        print(f"no arm logs under {ROOT}", file=sys.stderr)
        return 2

    panel_inertness(found)

    print()
    print("=" * 96)
    print(f"(2) THE LEVEL GAP `target/n_emit` ON THE `predict` AXIS (terminal {TERMW} yr).")
    print("    < 1 ⇒ the map wants FEWER stems than the stand carries ⇒ the anchor thins HARDER.")
    print("    This is where ADR 0185's +89..+312 % agb departure has to show up if the anchor is")
    print("    to act on it at all.")
    print()
    hdr = f"    {'arm':<5} {'leg':<9} {'legs':>5} {'rows':>7} {'med':>9} {'p05':>8} {'p95':>8}"
    print(hdr + f" {'<1':>7}")

    gaps = defaultdict(list)
    ratios = defaultdict(list)
    binds = defaultdict(lambda: [0, 0])
    legcount = defaultdict(set)
    for (scen, cell, arm, mode, seed), log in sorted(found.items()):
        if mode != "predict" or arm not in ARMS:
            continue
        rows = read_log(log)
        if not rows:
            continue
        years = sorted({int(r["year"]) for r in rows})
        cut = years[-1] - TERMW + 1
        legcount[(arm, scen)].add((cell, seed))
        for row in rows:
            if int(row["year"]) < cut:
                continue
            ne, npv, tg = float(row["n_emit"]), float(row["n_prev"]), float(row["target"])
            if ne <= 0.0 or tg <= 0.0:
                continue
            gaps[(arm, scen)].append(tg / ne)
            r0 = max(RHO_LO, min(RHO_HI, rho_eff(tg, npv, ne, 0.0)))
            for a in ANCHORS:
                raw = rho_eff(tg, npv, ne, a)
                ra = max(RHO_LO, min(RHO_HI, raw))
                ratios[(arm, scen, a)].append(ra / r0 if r0 > 0 else float("nan"))
                binds[(arm, scen, a)][1] += 1
                if raw < RHO_LO or raw > RHO_HI:
                    binds[(arm, scen, a)][0] += 1

    for arm in ARMS:
        for scen in ("historic", "ssp370"):
            g = gaps[(arm, scen)]
            if not g:
                continue
            below = 100.0 * sum(1 for x in g if x < 1.0) / len(g)
            print(
                f"    {arm:<5} {scen:<9} {len(legcount[(arm, scen)]):>5} {len(g):>7} "
                f"{statistics.median(g):>9.4f} {q(g, 0.05):>8.4f} {q(g, 0.95):>8.4f} {below:>6.1f}%"
            )

    print()
    print("=" * 96)
    print("(3) THE PER-YEAR PUSH AND ITS TIME CONSTANT, per anchor setting.")
    print("    push  = median rho_eff/rho_0, the EXTRA thinning the anchor asks for each year")
    print(f"    clamp = share of rows where rho_eff leaves [{RHO_LO}, {RHO_HI}] and is clipped")
    print("    yrs   = log(gap)/log(push), the years that push needs to close the median gap.")
    print("            ⚠ first-order only — the gap closes as the stand moves, so this OVERSTATES")
    print("            the time. Read it against the leg length (historic 20 yr, ssp370 81 yr).")
    print()
    print(f"    {'arm':<5} {'leg':<9} {'a':>5} {'push':>8} {'clamp':>8} {'yrs':>8}")
    for arm in ARMS:
        for scen in ("historic", "ssp370"):
            if not gaps[(arm, scen)]:
                continue
            gmed = statistics.median(gaps[(arm, scen)])
            for a in ANCHORS:
                rr = [x for x in ratios[(arm, scen, a)] if math.isfinite(x)]
                if not rr:
                    continue
                push = statistics.median(rr)
                nb, nt = binds[(arm, scen, a)]
                yrs = float("nan")
                if 0.0 < push < 1.0 and 0.0 < gmed < 1.0:
                    yrs = math.log(gmed) / math.log(push)
                print(
                    f"    {arm:<5} {scen:<9} {a:>5.2f} {push:>8.4f} "
                    f"{100.0 * nb / nt:>7.1f}% {yrs:>8.1f}"
                )
        print()

    panel_reachability()
    panel_trajectory()
    panel_percapita()

    print("=" * 96)
    print("READ THIS BEFORE PICKING `a`:")
    print("  * A push at or above 1.0000 means the anchor does NOT thin harder on these")
    print("    trajectories. ADR 0185 §7.5's criterion would then be unreachable by wiring alone.")
    print("  * A clamp share near 100 % means `a` is no longer the dial — the [0.7,1.3] bound is,")
    print("    and every setting above the binding one behaves alike. Prefer the SMALLEST `a`")
    print("    that saturates.")
    print("  * `yrs` above the leg length means the historic leg cannot be level-corrected in")
    print("    time, so the two legs would be asymmetrically anchored. The blessed statistic is a")
    print("    DIFFERENCE OF LEG MEANS, so an asymmetric correction MANUFACTURES a response.")
    print("    Both legs must converge, or the verdict is void before it is read.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
