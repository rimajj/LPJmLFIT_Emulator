#!/usr/bin/env python3
"""ARM D, part 1 — put the bounded Beta and the shipped copula on ONE statistic, and price each confound.

WHY THIS EXISTS (line S, arm D; ADR 0093 §5.3 → ADR 0118 decision 5)
--------------------------------------------------------------------
ADR 0093 §5.3 published: *"A bounded Beta on each PFT's own trait interval beats the shipped copula 2-3x.
Two-moment fit, no fitting procedure, median per-cell KS 0.042-0.073 vs the copula's 0.129-0.173 (400
cells/PFT with >=150 stems, historic 2019)."* ADR 0118 decision 5 flagged that it has **no committed
reproducer** and suspected it compared an oracle-moment Beta against a K-fold-by-cell OUT-OF-SAMPLE copula.

The reproducer was then found, uncommitted, at `/p/tmp/jamirp/npatch_analysis/attack/betaks.py`
(mtime 2026-08-07). Reading it shows the gap is **wider than ADR 0118 suspected — the two sides of the
"2-3x" are not the same statistic at all**, and three separate advantages are folded into one ratio:

  1. **the ESTIMATOR.** The Beta side is `scipy.stats.kstest(u, 'beta', args=(a, b))` — a ONE-SAMPLE KS
     against a Beta whose two parameters were estimated FROM THAT SAME SAMPLE. With estimated parameters the
     one-sample KS is severely optimistically biased (the Lilliefors problem): it is not a test of the family,
     it is a measure of how well two moments of a sample describe that sample. The copula side is a
     TWO-SAMPLE `ks2(pred, obs)` between an out-of-sample prediction and the truth. Arm 1 vs arm 2 below
     prices this, and arm `null_1samp_beta` gives the one-sample statistic's own noise floor: if
     0.042-0.073 sits AT that floor, the number carries no information about the Beta family.
  2. **the INFORMATION.** The Beta's two moments are the test cell's OWN observed moments; the copula has
     never seen the cell (`mod(hash(cell), 5)` folds). Arm 2 vs arm 5 prices this.
  3. **the GROUPING, and it is the confound nobody had named.** The Beta side groups per **(Cell, Type)** and
     keeps the **top 400 cells per PFT by stem count** — its own comment says "to give the Beta its best
     case". The copula's published `median_percell_KS` groups per **Cell only**, so every group is a MIXTURE
     over up to seven tree PFTs (whose intervals are in places disjoint — id 3's SLA is [0.0242, 0.0547],
     id 1's is [0.005, 0.0187]) at a >=20-stem floor over all 57 719 cells. A mixture of disjointly-supported
     marginals is a harder target for ANY single distribution. Arm 3 vs arm 4 prices this.

So this script scores a LADDER of arms on one row universe, reporting each on BOTH statistics where both are
defined, and it **gates on reproducing ADR 0093 §5.3's own numbers on ADR 0093's own basis** — the check that
makes this a reproducer rather than a redefinition. `ks2` is IMPORTED from
`plot_slow_emulator_validation.py`, the one KS definition in this repo (ADR 0031), and the copula's reference
numbers are READ from the published `metrics_traits.txt` rather than retyped.

WHAT THIS PART CANNOT ANSWER, so it is not over-claimed. Every Beta arm here takes its moments from observed
data. The deployable question — "would swapping the copula's marginal for a Beta whose moments are LEARNED on
the same conditioning and the same folds help?" — needs the learned map, and that is part 2
(`scripts/eval_slow_beta_arm.jl`, which emits `pred_<axis>.f64` into a shadow dir so the EXISTING
`score_slow_copula_ks.py` scores it with no new scorer).

Env: IND · YEAR (2019) · MINSTEM_PFT (150) · TOPCELLS (400) · MINSTEM_CELL (20) · NCELL_CELLBASIS (4000;
     0 = all, expensive) · SEED (12345) · NSIM (2000, the null simulation's replicate count) · OUT ·
     METRICS (the published metrics_traits.txt) · NOGATE=1
Run (SLURM; the `ind` scan is the cost):
     scripts/sbatch_python.sh S-armd1 scripts/score_beta_vs_copula_likeforlike.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFDIR = os.path.join(REPO, "test", "testitems", "references")
sys.path.insert(0, os.path.join(REPO, "scripts"))
from plot_slow_emulator_validation import ks2  # noqa: E402 — the ONE two-sample KS (ADR 0031)

IND = os.environ.get("IND", "/p/tmp/jamirp/emulator_global/ind_hist_seed1_all.parquet")
YEAR = int(os.environ.get("YEAR", "2019"))
MINSTEM_PFT = int(os.environ.get("MINSTEM_PFT", "150"))
TOPCELLS = int(os.environ.get("TOPCELLS", "400"))
MINSTEM_CELL = int(os.environ.get("MINSTEM_CELL", "20"))
NCELL_CELLBASIS = int(os.environ.get("NCELL_CELLBASIS", "4000"))
SEED = int(os.environ.get("SEED", "12345"))
NSIM = int(os.environ.get("NSIM", "2000"))
OUT = os.environ.get("OUT", os.path.join(REFDIR, "S_beta_vs_copula_likeforlike.csv"))
METRICS = os.environ.get(
    "METRICS", os.path.join(REPO, "figures", "emulator_validation", "pooled_t8", "metrics_traits.txt")
)
NOGATE = os.environ.get("NOGATE", "0") == "1"

AXES = ["SLA", "Wooddens", "D95max", "minwscal"]
# ADR 0093 §5.3's published per-axis medians, on its own basis — the GATE target.
ADR0093 = {"SLA": None, "Wooddens": None, "D95max": None, "minwscal": None}   # filled from the range check
ADR0093_RANGE = (0.042, 0.073)


def intervals() -> dict[str, dict[int, tuple[float, float]]]:
    """Per-(axis, PFT) trait interval from the ONE committed source of record (ADR 0119)."""
    rows = []
    with open(os.path.join(REFDIR, "S_pft_estab_params.csv")) as fh:
        lines = [ln.rstrip("\n") for ln in fh if not ln.startswith("#") and ln.strip()]
    cols = lines[0].split(",")
    for ln in lines[1:]:
        rows.append(dict(zip(cols, ln.split(","), strict=True)))
    key = {"SLA": "sla", "Wooddens": "wooddens", "D95max": "d95max", "minwscal": "minwscal"}
    out: dict[str, dict[int, tuple[float, float]]] = {}
    for ax in AXES:
        out[ax] = {
            int(r["pft_id"]): (float(r[f"{key[ax]}_low"]), float(r[f"{key[ax]}_high"])) for r in rows
        }
    return out


def beta_ab(u: np.ndarray) -> tuple[float, float]:
    """Method-of-moments Beta parameters on [0,1] — `betaks.py`'s own formula, kept identical."""
    m = float(u.mean())
    v = float(u.var(ddof=1))
    if v <= 0 or v >= m * (1 - m):
        return (np.nan, np.nan)
    k = m * (1 - m) / v - 1.0
    return (m * k, (1 - m) * k)


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta (Lentz). Pure numpy/Base — no scipy dependency here,
    because this file must run in the locked CI env too and `scipy` is not in it."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < 3e-16:
            break
    return h


def _lgamma(x: float) -> float:
    """Lanczos log-gamma (g=7, n=9) — enough for the incomplete beta's normalizer."""
    g = [0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313,
         -176.61502916214059, 12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6,
         1.5056327351493116e-7]
    if x < 0.5:
        return np.log(np.pi / np.sin(np.pi * x)) - _lgamma(1.0 - x)
    x -= 1.0
    a = g[0]
    t = x + 7.5
    for i in range(1, 9):
        a += g[i] / (x + i)
    return 0.5 * np.log(2 * np.pi) + (x + 0.5) * np.log(t) - t + np.log(a)


def betacdf(x: np.ndarray, a: float, b: float) -> np.ndarray:
    """Regularized incomplete beta I_x(a,b), vectorized over x."""
    out = np.empty_like(x, dtype=float)
    lbeta = _lgamma(a) + _lgamma(b) - _lgamma(a + b)
    for i, xi in enumerate(x):
        xi = min(max(float(xi), 0.0), 1.0)
        if xi <= 0.0:
            out[i] = 0.0
        elif xi >= 1.0:
            out[i] = 1.0
        else:
            front = np.exp(a * np.log(xi) + b * np.log(1.0 - xi) - lbeta)
            out[i] = front * _betacf(a, b, xi) / a if xi < (a + 1.0) / (a + b + 2.0) \
                else 1.0 - np.exp(b * np.log(1.0 - xi) + a * np.log(xi) - lbeta) * _betacf(b, a, 1.0 - xi) / b
    return out


def ks_1samp_beta(x: np.ndarray, lo: float, hi: float) -> float:
    """`betaks.py`'s statistic: ONE-SAMPLE KS of the sample against a Beta fitted to its OWN moments."""
    u = np.clip((x - lo) / (hi - lo), 1e-9, 1 - 1e-9)
    a, b = beta_ab(u)
    if not np.isfinite(a):
        return np.nan
    us = np.sort(u)
    n = us.size
    cdf = betacdf(us, a, b)
    d1 = np.max(np.arange(1, n + 1) / n - cdf)
    d2 = np.max(cdf - np.arange(0, n) / n)
    return float(max(d1, d2))


def betaquant(u: np.ndarray, a: float, b: float) -> np.ndarray:
    """Beta quantile by bisection on `betacdf` — 60 iters is ~1e-18 on [0,1]."""
    lo = np.zeros_like(u, dtype=float)
    hi = np.ones_like(u, dtype=float)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        c = betacdf(mid, a, b)
        up = c < u
        lo = np.where(up, mid, lo)
        hi = np.where(up, hi, mid)
    return 0.5 * (lo + hi)


def ks_2samp_beta(x: np.ndarray, lo: float, hi: float, rng: np.random.Generator) -> tuple[float, float]:
    """The copula's OWN statistic, applied to the Beta. Returns (oracle_moments, split_half_floor).

    Split the group in half: fit the Beta's two moments on half A, DRAW an equal-size predicted sample from
    it, and score `ks2(pred, half_B)` — the same two-sample distance the published copula number is. The
    floor is `ks2(half_A, half_B)`, i.e. what the statistic reads when the "prediction" is a second draw of
    the truth itself. Without that floor a two-sample KS of 0.06 is uninterpretable.
    """
    n = x.size
    if n < 2 * 8:
        return (np.nan, np.nan)
    idx = rng.permutation(n)
    A, B = x[idx[: n // 2]], x[idx[n // 2:]]
    uA = np.clip((A - lo) / (hi - lo), 1e-9, 1 - 1e-9)
    a, b = beta_ab(uA)
    if not np.isfinite(a):
        return (np.nan, float(ks2(A, B)))
    pred = lo + (hi - lo) * betaquant(rng.random(B.size), a, b)
    return (float(ks2(pred, B)), float(ks2(A, B)))


def null_1samp(rng: np.random.Generator, n: int, a: float, b: float, nsim: int) -> float:
    """The one-sample statistic's OWN noise floor: data that genuinely IS Beta, parameters re-estimated."""
    d = np.empty(nsim)
    for i in range(nsim):
        x = rng.beta(a, b, size=n)
        d[i] = ks_1samp_beta(x, 0.0, 1.0)
    return float(np.median(d))


def published_copula() -> dict[str, float]:
    """The copula's median per-cell KS, READ from the published metrics file (never retyped)."""
    out: dict[str, float] = {}
    if not os.path.exists(METRICS):
        print(f"   ⚠ {METRICS} absent — the copula reference column will be empty")
        return out
    for ln in open(METRICS):
        p = ln.split()          # the file is TAB-separated key/value pairs after the axis name
        if not p or p[0] not in AXES:
            continue
        for j, tok in enumerate(p[:-1]):
            if tok == "median_percell_KS":
                out[p[0]] = float(p[j + 1])
    if set(out) != set(AXES):
        raise SystemExit(f"FATAL: {METRICS} yielded median_percell_KS for {sorted(out)}, expected {AXES}")
    return out


def main() -> int:
    rng = np.random.default_rng(SEED)
    IV = intervals()
    print(f"== ind={IND}  YEAR={YEAR}")
    df = (
        pl.scan_parquet(IND)
        .filter((pl.col("Year") == YEAR) & (pl.col("Type") <= 6) & (pl.col("isdead") == 0))
        .select(["Cell", "Type"] + AXES)
        .collect(engine="streaming")
    )
    print(f"== {df.height:,} surviving tree stems in {YEAR}")

    rows: list[dict] = []

    # ── ARM 1 + 2 + 3: ADR 0093's own basis — per (Cell, Type), top-N densest cells per PFT ───────────
    print(f"\n-- ADR 0093 §5.3's basis: per (Cell,Type), >={MINSTEM_PFT} stems, top {TOPCELLS} cells per PFT")
    for ax in AXES:
        k1_all, k2o_all, k2f_all = [], [], []
        for t in range(7):
            s = df.filter(pl.col("Type") == t)
            if not s.height:
                continue
            cnt = s.group_by("Cell").len().filter(pl.col("len") >= MINSTEM_PFT).sort("len", descending=True)
            cells = cnt["Cell"].to_list()[:TOPCELLS] if TOPCELLS > 0 else cnt["Cell"].to_list()
            if len(cells) < 20:
                continue
            lo, hi = IV[ax][t]
            sub = s.filter(pl.col("Cell").is_in(cells)).select("Cell", ax)
            for _, g in sub.group_by("Cell"):
                x = g[ax].to_numpy().astype(float)
                k1_all.append(ks_1samp_beta(x, lo, hi))
                o, f = ks_2samp_beta(x, lo, hi, rng)
                k2o_all.append(o)
                k2f_all.append(f)
        med = lambda v: float(np.nanmedian(np.asarray(v, dtype=float))) if v else float("nan")  # noqa: E731
        rows += [
            dict(arm="1_beta_1samp_oracle_perpft", statistic="KS_1samp_est_params", grouping="cell_x_pft",
                 axis=ax, value=round(med(k1_all), 4), n_groups=len(k1_all)),
            dict(arm="2_beta_2samp_oracle_perpft", statistic="KS_2samp", grouping="cell_x_pft",
                 axis=ax, value=round(med(k2o_all), 4), n_groups=len(k2o_all)),
            dict(arm="3_splithalf_floor_perpft", statistic="KS_2samp", grouping="cell_x_pft",
                 axis=ax, value=round(med(k2f_all), 4), n_groups=len(k2f_all)),
        ]
        print(f"   {ax:10s} 1samp(oracle,perPFT)={med(k1_all):.4f}   "
              f"2samp(oracle,perPFT)={med(k2o_all):.4f}   2samp floor={med(k2f_all):.4f}   "
              f"groups={len(k1_all)}")

    # ── ARM 4 + 5: the COPULA's grouping — per Cell only, PFTs MIXED, >=20 stems ──────────────────────
    print(f"\n-- the copula's basis: per Cell only (PFTs MIXED), >={MINSTEM_CELL} stems"
          f"{f', {NCELL_CELLBASIS} sampled cells' if NCELL_CELLBASIS else ''}")
    cnt = df.group_by("Cell").len().filter(pl.col("len") >= MINSTEM_CELL)
    cells = cnt["Cell"].to_list()
    if NCELL_CELLBASIS and len(cells) > NCELL_CELLBASIS:
        pick = rng.choice(len(cells), size=NCELL_CELLBASIS, replace=False)
        cells = [cells[i] for i in sorted(pick)]
    sub = df.filter(pl.col("Cell").is_in(cells))
    print(f"   {len(cells):,} cells of {cnt.height:,} eligible")
    for ax in AXES:
        # PFT-blind interval = the UNION over the seven tree PFTs, which is all a PFT-blind model has
        lo = min(v[0] for v in IV[ax].values())
        hi = max(v[1] for v in IV[ax].values())
        k2o, k2f = [], []
        for _, g in sub.select("Cell", ax).group_by("Cell"):
            x = g[ax].to_numpy().astype(float)
            o, f = ks_2samp_beta(x, lo, hi, rng)
            k2o.append(o)
            k2f.append(f)
        med = lambda v: float(np.nanmedian(np.asarray(v, dtype=float))) if v else float("nan")  # noqa: E731
        rows += [
            dict(arm="4_beta_2samp_oracle_percell", statistic="KS_2samp", grouping="cell_only_pft_mixed",
                 axis=ax, value=round(med(k2o), 4), n_groups=len(k2o)),
            dict(arm="5_splithalf_floor_percell", statistic="KS_2samp", grouping="cell_only_pft_mixed",
                 axis=ax, value=round(med(k2f), 4), n_groups=len(k2f)),
        ]
        print(f"   {ax:10s} interval=[{lo:g}, {hi:g}]  2samp(oracle,PFT-blind)={med(k2o):.4f}   "
              f"2samp floor={med(k2f):.4f}")

    # ── ARM 6: the one-sample statistic's OWN noise floor ─────────────────────────────────────────────
    print(f"\n-- the ONE-SAMPLE statistic's noise floor (data that IS Beta, params re-estimated, "
          f"{NSIM} sims)")
    for n in (150, 400, 1000):
        for (a, b, lab) in ((2.0, 2.0, "symmetric"), (1.2, 4.0, "skewed"), (0.8, 0.9, "U-ish")):
            v = null_1samp(rng, n, a, b, NSIM)
            rows.append(dict(arm="6_null_1samp_beta", statistic="KS_1samp_est_params",
                             grouping=f"n={n}_{lab}", axis="-", value=round(v, 4), n_groups=NSIM))
            print(f"   n={n:5d} Beta({a},{b}) {lab:10s} median KS = {v:.4f}")

    # ── the copula's published numbers, read not retyped ─────────────────────────────────────────────
    pub = published_copula()
    for ax, v in pub.items():
        rows.append(dict(arm="7_copula_published", statistic="KS_2samp", grouping="cell_only_pft_mixed",
                         axis=ax, value=round(v, 4), n_groups=0))
    if pub:
        print("\n-- the shipped copula, from the published metrics file: "
              + "  ".join(f"{a}={v:.4f}" for a, v in pub.items()))

    # ── THE GATE ─────────────────────────────────────────────────────────────────────────────────────
    a1 = [r["value"] for r in rows if r["arm"] == "1_beta_1samp_oracle_perpft"]
    lo_g, hi_g = ADR0093_RANGE
    inside = [v for v in a1 if lo_g - 0.012 <= v <= hi_g + 0.012]
    print(f"\n== GATE vs ADR 0093 §5.3 (its own one-sample statistic + basis): per-axis medians "
          f"{[round(v, 4) for v in a1]} against the published range {lo_g}-{hi_g}")
    if len(inside) == len(a1):
        print("   GATE PASS — the published Beta number is reproduced on its own basis.")
    elif NOGATE:
        print("   ⚠ GATE FAIL but NOGATE=1 — state the delta with any number derived from this run.")
    else:
        raise SystemExit(
            "FATAL: arm 1 does NOT reproduce ADR 0093 §5.3's 0.042-0.073 on ADR 0093's own basis. Find the "
            "remaining definitional difference before publishing any correction (NOGATE=1 to see it all)."
        )

    hdr = [
        "# ARM D part 1 — the bounded Beta and the shipped copula on ONE statistic. GENERATED.",
        "#   regenerate: scripts/sbatch_python.sh S-armd1 scripts/score_beta_vs_copula_likeforlike.py",
        "# The reproducer ADR 0093 §5.3 never had (ADR 0118 decision 5). Read the arms as a LADDER; each",
        "# neighbouring pair prices exactly one of the three confounds folded into the published '2-3x':",
        "#   1 vs 2  the ESTIMATOR — a one-sample KS against a Beta fitted to the SAME sample's moments",
        "#           (optimistically biased with estimated parameters) vs the two-sample KS the copula",
        "#           number actually is. Arm 6 is that one-sample statistic's own noise floor.",
        "#   2 vs 4  the GROUPING — per (Cell,PFT) on the densest cells vs per Cell with the PFTs MIXED,",
        "#           which is what the published copula median_percell_KS groups on. A mixture over",
        "#           partly-DISJOINT per-PFT intervals is a harder target for any single distribution.",
        "#   3, 5    the two-sample FLOOR on each grouping: ks2(half A, half B) of the truth against",
        "#           itself. A two-sample KS is uninterpretable without it.",
        "#   4 vs 7  the INFORMATION — a Beta given the test cell's OWN observed moments vs the shipped",
        "#           copula, which has never seen the cell. Arm 7 is read from the published metrics file.",
        "# EVERY Beta arm here is ORACLE-moment. The deployable question needs a LEARNED moment map on the",
        "# same folds — that is part 2, scripts/eval_slow_beta_arm.jl, scored by score_slow_copula_ks.py.",
    ]
    cols = ["arm", "statistic", "grouping", "axis", "value", "n_groups"]
    with open(OUT, "w") as fh:
        fh.write("\n".join(hdr) + "\n" + ",".join(cols) + "\n")
        for r in rows:
            fh.write(",".join(str(r[c]) for c in cols) + "\n")
    print(f"== wrote {os.path.relpath(OUT, REPO)}  ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
