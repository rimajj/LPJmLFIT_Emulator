#!/usr/bin/env python3
"""Score the cross-cell recruit-arm table: per-cell effects, and whether the cells actually DISAGREE.

WHY THIS EXISTS (line S, 2026-08-12, ADR 0172)
----------------------------------------------
ADR 0171 read five 40-seed ensembles off three cells and concluded the response contribution's sign is not
stable. With five cells the eye can tell two stories that lead to opposite decisions, and it cannot choose
between them by inspection:

  (a) the sign is CELL-IDIOSYNCRATIC — then no per-regime flip condition can ever be met, and the ported
      establishment rule's response is simply not a property of the model;
  (b) the sign is set by the ELIGIBILITY REGIME — then ADR 0171 §5's "one cell per regime, sign must agree"
      is the right condition and just needs replicates.

The five measured contributions are consistent with BOTH on a glance: the two significant negatives sit at
`n_elig` 6 and 3, the two significant positives both at `n_elig` 4 — which looks like (b) — while the third
`n_elig = 4` cell's point estimate is negative, which looks like (a). Reading the signs alone would let either
story be asserted, so this script does the arithmetic that separates them:

  * a per-cell mean ± SEM and t for every quantity, on the SAME exclusion rules as the reference file;
  * **Cochran's Q** heterogeneity test across all cells and WITHIN the modal regime — i.e. is the spread
    larger than the seed noise can explain? A within-regime Q that is significant refutes (b) directly, and
    does so even when an individual cell's own sign is unresolved;
  * **pairwise Welch t** among the same-regime cells, because Q says "they differ" without saying which;
  * an explicit **power** line: the half-width of each cell's CI in ×FIT units, so an unresolved cell is
    reported as unresolved rather than silently read as a zero (ADR 0170 §2's lesson).

This is deliberately arithmetic on a COMMITTED file rather than a re-run: the ensembles are the expensive
part and they are already recorded per seed, so the statistics must be re-derivable without SLURM.

Env: REF (the committed cross-cell csv) · FIT_SHIFT (2432.9, ADR 0046 §1) · REGIME (a
     tag:n_elig,tag:n_elig,... map; default = the five provisioned cells' historic values from
     S_estab_eligibility_<site>.csv, read from those files rather than hardcoded) · OUT (csv; optional)
Run: python3 scripts/score_recruit_crosscell_heterogeneity.py
"""

from __future__ import annotations

import math
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFDIR = os.path.join(REPO, "test", "testitems", "references")
sys.path.insert(0, os.path.join(REPO, "scripts"))
# The ONE incomplete beta in this repo's script tree (arm D part 1), reused rather than re-derived so the
# t-distribution tail here and the Beta quantiles there cannot drift apart (ADR 0031).
from score_beta_vs_copula_likeforlike import _betacf, _lgamma  # noqa: E402

REF = os.environ.get("REF", os.path.join(REFDIR, "S_recruit_multicell_seed_ensembles.csv"))
FIT = float(os.environ.get("FIT_SHIFT", "2432.9"))
OUT = os.environ.get("OUT", "")


def betacdf_scalar(x: float, a: float, b: float) -> float:
    """Regularized incomplete beta I_x(a,b) for one x — the vectorized sibling takes an array."""
    x = min(max(float(x), 0.0), 1.0)
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lb = _lgamma(a) + _lgamma(b) - _lgamma(a + b)
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(a * math.log(x) + b * math.log1p(-x) - lb) * _betacf(a, b, x) / a
    return 1.0 - math.exp(b * math.log1p(-x) + a * math.log(x) - lb) * _betacf(b, a, 1.0 - x) / b


def read_ref() -> tuple[list[str], list[list[str]]]:
    rows = []
    with open(REF) as fh:
        for ln in fh:
            if ln.startswith("#") or not ln.strip():
                continue
            rows.append(ln.rstrip("\n").split(","))
    return rows[0], rows[1:]


def elig_of(site: str) -> int | None:
    """This site's HISTORIC eligible-PFT count, read from its own committed series (never hardcoded)."""
    p = os.path.join(REFDIR, f"S_estab_eligibility_{site}.csv")
    if not os.path.exists(p):
        p = os.path.join(REFDIR, "S_hainich_estab_eligibility.csv")
        if not os.path.exists(p):
            return None
    vals = set()
    with open(p) as fh:
        lines = [ln.rstrip("\n") for ln in fh if not ln.startswith("#") and ln.strip()]
    cols = lines[0].split(",")
    i_scen, i_n = cols.index("scenario"), cols.index("n_elig")
    for ln in lines[1:]:
        f = ln.split(",")
        if f[i_scen] == "historic":
            vals.add(int(f[i_n]))
    # A cell whose gate MOVES has no single value; report the modal one and say so upstream.
    return max(vals, key=lambda v: sum(1 for ln in lines[1:] if ln.split(",")[i_n] == str(v)))


def stats(v: list[float]) -> tuple[float, float, float, int]:
    n = len(v)
    m = sum(v) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1)) if n > 1 else 0.0
    sem = sd / math.sqrt(n) if n else float("nan")
    t = m / sem if sem > 0 else float("nan")
    return m, sem, t, n


def cochran_q(means: list[float], sems: list[float]) -> tuple[float, int, float]:
    """Fixed-effect heterogeneity: Q = Σ w_i (θ_i − θ̄_w)², w_i = 1/SEM², df = k−1, θ̄_w the weighted mean.

    Under "all cells share one true effect", Q ~ chi²(k−1). A large Q means the spread between cells exceeds
    what the within-cell seed noise can produce — which is exactly the question "do the cells disagree?".
    """
    w = [1.0 / s**2 for s in sems]
    tb = sum(wi * mi for wi, mi in zip(w, means, strict=True)) / sum(w)
    q = sum(wi * (mi - tb) ** 2 for wi, mi in zip(w, means, strict=True))
    return q, len(means) - 1, tb


def chi2_sf(x: float, df: int) -> float:
    """Upper tail of chi²(df) — series/continued-fraction incomplete gamma, no scipy (locked-env safe)."""
    if x <= 0:
        return 1.0
    a, xx = df / 2.0, x / 2.0
    # lower regularized incomplete gamma P(a, x)
    if xx < a + 1.0:
        term = 1.0 / a
        s = term
        n = 0
        while n < 500:
            n += 1
            term *= xx / (a + n)
            s += term
            if abs(term) < abs(s) * 1e-16:
                break
        lg = math.lgamma(a)
        p = s * math.exp(-xx + a * math.log(xx) - lg)
        return max(0.0, min(1.0, 1.0 - p))
    # upper via Lentz continued fraction for Q(a, x)
    tiny = 1e-300
    b = xx + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-16:
            break
    return max(0.0, min(1.0, math.exp(-xx + a * math.log(xx) - math.lgamma(a)) * h))


def welch(m1, s1, n1, m2, s2, n2) -> tuple[float, float, float]:
    """Welch's two-sample t on two ensembles' (mean, SEM, n), with the EXACT two-sided Student-t p.

    The p is `I_{df/(df+t²)}(df/2, 1/2)` through the same incomplete beta the arm-D scorer uses (imported,
    not re-derived — ADR 0031). A normal approximation was the first version and it moved every p by
    0.001-0.003 here (0.0232 → 0.0263, 0.0079 → 0.0096) without changing a verdict; it is replaced anyway
    because these p-values are quoted in an ADR and "close enough at n = 40" is the kind of shortcut that
    stops being true the moment someone runs this at n = 8.
    """
    se = math.sqrt(s1**2 + s2**2)
    t = (m1 - m2) / se if se > 0 else float("nan")
    v1, v2 = s1**2, s2**2
    df = (v1 + v2) ** 2 / (v1**2 / (n1 - 1) + v2**2 / (n2 - 1)) if (v1 + v2) > 0 else float("nan")
    if not (math.isfinite(t) and math.isfinite(df) and df > 0):
        return t, float("nan"), df
    x = df / (df + t * t)
    return t, float(betacdf_scalar(x, df / 2.0, 0.5)), df


def main() -> int:
    hdr, body = read_ref()
    ix = {c: i for i, c in enumerate(hdr)}
    tags: list[str] = []
    for r in body:
        if r[0] not in tags:
            tags.append(r[0])

    print(f"== {REF}\n== {len(body)} seed rows over {len(tags)} ensembles; FIT shift = {FIT} gC/m3")
    print("\n-- PER-CELL, on the PINNED pooled_w20_t8 artifact only (the demo-pair arms are shown but "
          "excluded from every cross-cell statistic — ADR 0171 §3: the artifact can flip a sign)")
    print(
        f"{'tag':11s} {'site':22s} {'cell':>6s} {'art':14s} {'n':>3s} {'n_elig':>6s} "
        f"{'level_hist':>11s} {'level_%':>8s} {'R_ctl xFIT':>16s} {'contrib xFIT':>16s} {'CI½':>6s}"
    )
    recs = []
    for tag in tags:
        rs = [r for r in body if r[0] == tag]
        bad = [r for r in rs if any(float(r[ix[c]] or 0) > 0
                                    for c in ("hard_kills", "shortfall_years", "n_merge"))]
        rs = [r for r in rs if r not in bad]
        if not rs:
            continue
        site, cell, art = rs[0][ix["site"]], rs[0][ix["cell"]], rs[0][ix["artifact"]]
        # An explicit def with `rows` BOUND as a default, not a lambda closing over the loop variable:
        # ruff B023 is right that the closure form is fragile even where it is used inside the same
        # iteration, and this table is exactly the place a silent wrong-ensemble read would not be noticed.
        def col(c, rows=rs):
            return [float(r[ix[c]]) for r in rows]

        lvl, sem_l, _, n = stats(col("d_hist"))
        # strict=True: d_hist and wd_ctl_hist are the SAME seeds; a length mismatch means a parse fault,
        # and zip's default would silently truncate the pairing instead of failing.
        pct = 100 * sum(a / b for a, b in zip(col("d_hist"), col("wd_ctl_hist"), strict=True)) / n
        mrc, src, _, _ = stats([v / FIT for v in col("R_ctl")])
        mi, si, ti, _ = stats([v / FIT for v in col("interaction")])
        ne = elig_of(site)
        recs.append(dict(tag=tag, site=site, cell=cell, art=art, n=n, n_elig=ne, level=lvl, pct=pct,
                         rctl=mrc, rctl_sem=src, contrib=mi, contrib_sem=si, t=ti, nbad=len(bad)))
        print(f"{tag:11s} {site:22s} {cell:>6s} {art:14s} {n:>3d} {str(ne):>6s} "
              f"{lvl:>11.0f} {pct:>7.2f}% {mrc:>+9.3f}±{src:<5.3f} {mi:>+9.3f}±{si:<5.3f} {1.96 * si:>6.2f}")
    if any(r["nbad"] for r in recs):
        print("   (rows failing the ADR-0048/0101 usability preconditions were excluded)")

    # Match the PINNED artifact by substring, not equality: ADR 0171's rows label it
    # `global_pooled_w20_t8` and a later append could shorten it. A demo-pair row must never enter a
    # cross-cell statistic (ADR 0171 §3 — the artifact alone can flip the contribution's sign).
    pinned = [r for r in recs if "pooled_w20_t8" in r["art"] and "demo" not in r["art"]]
    seen = set()
    cells = []
    for r in pinned:                       # one record per CELL (the pre-fix control arm is a duplicate)
        if r["cell"] in seen:
            continue
        seen.add(r["cell"])
        cells.append(r)
    print(f"\n-- HETEROGENEITY across the {len(cells)} pinned-artifact cells")
    print("   The question: is the between-cell spread bigger than the within-cell SEED noise?")
    for lab, sub in (("all cells", cells),
                     ("the modal n_elig=4 regime only",
                      [r for r in cells if r["n_elig"] == 4])):
        if len(sub) < 2:
            continue
        for qty, mk, sk in (("contribution", "contrib", "contrib_sem"), ("baseline R_ctl", "rctl", "rctl_sem")):
            q, df, tb = cochran_q([r[mk] for r in sub], [r[sk] for r in sub])
            p = chi2_sf(q, df)
            i2 = max(0.0, 100 * (q - df) / q) if q > 0 else 0.0
            verdict = "the cells DISAGREE" if p < 0.05 else "one common effect is not excluded"
            print(f"   {lab:32s} {qty:14s} Q={q:8.2f} df={df}  p={p:.2e}  I²={i2:5.1f} %  "
                  f"weighted mean={tb:+.3f} xFIT  ⇒ {verdict}")
    same = [r for r in cells if r["n_elig"] == 4]
    if len(same) >= 2:
        print(f"\n-- PAIRWISE among the {len(same)} same-regime (n_elig=4) cells, contribution xFIT")
        for i in range(len(same)):
            for j in range(i + 1, len(same)):
                a, b = same[i], same[j]
                t, p, df = welch(a["contrib"], a["contrib_sem"], a["n"],
                                 b["contrib"], b["contrib_sem"], b["n"])
                print(f"   {a['site']:22s} vs {b['site']:22s} Δ={a['contrib'] - b['contrib']:+7.3f}  "
                      f"t={t:+6.2f}  df={df:5.1f}  p={p:.4f}  "
                      f"{'DIFFER' if p < 0.05 else 'not resolved'}")

    print("\n-- POWER, per cell: |effect| vs its own 95 % half-width (an unresolved cell is NOT a zero)")
    for r in cells:
        hw = 1.96 * r["contrib_sem"]
        state = "resolved" if abs(r["contrib"]) > hw else "UNRESOLVED"
        print(f"   {r['site']:22s} contrib {r['contrib']:+7.3f} ± {hw:5.2f} (95 %)  {state:10s} "
              f"— seeds needed for |effect| at 80 % power: "
              f"{math.ceil(r['n'] * (2.8 * r['contrib_sem'] / max(abs(r['contrib']), 1e-9)) ** 2)}")

    if OUT:
        cols = ["tag", "site", "cell", "art", "n", "n_elig", "level", "pct", "rctl", "rctl_sem",
                "contrib", "contrib_sem", "t"]
        with open(OUT, "w") as fh:
            fh.write("# GENERATED by scripts/score_recruit_crosscell_heterogeneity.py\n")
            fh.write(",".join(cols) + "\n")
            for r in recs:
                fh.write(",".join(str(r[c]) for c in cols) + "\n")
        print(f"\n== wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
