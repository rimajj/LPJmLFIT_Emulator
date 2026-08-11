#!/usr/bin/env python3
"""Does leaving `k_root` on the C's OWN draw cost the rung-2 recruit interface anything?

Line M's rung-2 substitution hook (ADR 0120 §2) accepts a recruit as `pft_id` plus the FOUR axes Component
S's copula predicts (`SLA`, `Wooddens`, `D95max`, `minwscal`), re-derives `beta_root` and `Longevity` from
them as the C does, and leaves the remaining three sampled axes — `emax`, `k_root`, `beta_2` — on the C's
own uniform draw. M asked S whether any of those three matters. Two of them (`emax`, `beta_2`) are not
emitted anywhere, so the question is only decidable for **`k_root`**, which IS one of the 29 `ind` columns.

It is decidable, and this script decides it, because the substitution is not neutral by construction.
LPJmL-FIT establishes ~44-80 % of recruits by INHERITANCE (ADR 0045): a seedbank parent is copied and every
trait is diffused by `new_tree.c:38-61`, so all seven axes descend TOGETHER from one parent and become
correlated in the live population through shared ancestry. Substituting four axes while the other three are
redrawn uniformly severs that link for `k_root`. Whether that matters is an empirical question with two
parts, and this measures both:

  1. **COUPLING** — within PFT and within age class, is `k_root` correlated with the four substituted axes
     among survivors? If it is ~0, the C's independent draw reproduces the joint and there is nothing to fix.
     Reported beside the four axes' correlations WITH EACH OTHER, which is the only scale on which "how big
     is 0.05" can be read here.
  2. **SELECTION** — is `k_root` under selection at all? The one-year differential
     `mean(k_root | survives) - mean(k_root | all)` per PFT, the same statistic ADR 0046 used for `Wooddens`.
     An axis with no selection differential cannot carry a trait response no matter how it is sampled; one
     with a differential comparable to `Wooddens`' is a channel the interface would be dropping.

Both are computed WITHIN (PFT, age bin) — `Type` and age dominate every cross-axis correlation here
(ADR 0049's age-trait gradient), so a pooled correlation would mostly measure composition, which is not
what the recruit interface controls.

Usage (SLURM; EXPORT every knob — sbatch_python.sh forwards only a fixed list, CLAUDE.md §9):
    export IND=/p/tmp/jamirp/emulator_global/ind_hist_seed1_all.parquet
    export OUT=/p/tmp/jamirp/emulator_global/recruit_trait_axis_coupling.csv
    NCPUS=24 TIME=01:00:00 scripts/sbatch_python.sh S-axiscoup scripts/diagnose_recruit_trait_axis_coupling.py
Env: IND, OUT, AGE_EDGES (default "10,20,40,80,160,320" — ADR 0049's bins).
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import polars as pl

BASE = "/p/tmp/jamirp/emulator_global"
IND = Path(os.environ.get("IND", f"{BASE}/ind_hist_seed1_all.parquet"))
OUT = Path(os.environ.get("OUT", f"{BASE}/recruit_trait_axis_coupling.csv"))
AGE_EDGES = [float(x) for x in os.environ.get("AGE_EDGES", "10,20,40,80,160,320").split(",")]

#: the four axes the copula predicts and the hook substitutes, plus the axis in question
SUBST = ["SLA", "Wooddens", "D95max", "minwscal"]
QUERY = "k_root"
TREE_TYPES = tuple(range(7))  # ADR 0031 — all seven tree PFTs, never a truncated set

ROWS: list[dict] = []


def age_bin(age: np.ndarray) -> np.ndarray:
    return np.digitize(age, AGE_EDGES)


def wcorr_within(df: pl.DataFrame, a: str, b: str) -> tuple[float, int]:
    """Pearson r of `a` vs `b` POOLED ACROSS (PFT, age-bin) strata after centring within each stratum.

    Centring within stratum removes exactly the composition and age-gradient signal that would otherwise
    dominate; the pooled-within-stratum correlation is the quantity the recruit interface can affect.
    """
    d = df.select(["_g", a, b]).drop_nulls()
    if d.height < 100:
        return float("nan"), 0
    d = d.with_columns([(pl.col(a) - pl.col(a).mean().over("_g")).alias("_a"),
                        (pl.col(b) - pl.col(b).mean().over("_g")).alias("_b")])
    x = d["_a"].to_numpy()
    y = d["_b"].to_numpy()
    sx, sy = x.std(), y.std()
    if sx <= 0 or sy <= 0:
        return float("nan"), d.height
    return float((x * y).mean() / (sx * sy)), d.height


def main() -> int:
    cols = ["Type", "Age", "isdead", QUERY, *SUBST]
    print(f"== scanning {IND} ({IND.stat().st_size / 1e9:.1f} GB) columns={cols}", flush=True)
    lf = (pl.scan_parquet(IND)
          .select(cols)
          .filter(pl.col("Type").is_in(list(TREE_TYPES))))
    df = lf.collect(engine="streaming")
    print(f"== {df.height:,} tree rows ({(df['isdead'] == 0).sum():,} survivors)", flush=True)

    df = df.with_columns([
        (pl.col("Type").cast(pl.Int64) * 100
         + pl.Series("ab", age_bin(df["Age"].to_numpy())).cast(pl.Int64)).alias("_g")
    ])
    surv = df.filter(pl.col("isdead") == 0)

    # ---- 0. IS THE AXIS EVEN VARIABLE? ----------------------------------------------------------------
    # This runs FIRST and can settle the whole question on its own. A degenerate correlation (r == ±0.0000
    # with a nan selection differential) is the signature of a CONSTANT column, not of an uncoupled trait,
    # and the two have opposite implications — so establish variability before reading any panel below.
    print("\n--- 0. VARIABILITY AUDIT of every axis, per PFT (a constant column invalidates §1 and §2) ---")
    print(f"  {'pft':>4s} {'rows':>13s} " + " ".join(f"{a:>28s}" for a in [QUERY, *SUBST]))
    print(f"  {'':>4s} {'':>13s} " + " ".join(f"{'uniq / min / max':>28s}" for _ in [QUERY, *SUBST]))
    for t in TREE_TYPES:
        sub = df.filter(pl.col("Type") == t)
        if sub.height < 1000:
            continue
        cells = []
        for a in [QUERY, *SUBST]:
            v = sub[a].to_numpy()
            v = v[np.isfinite(v)]
            nu = int(np.unique(v).size) if v.size else 0
            cells.append(f"{nu:>6d} / {v.min():.4g} / {v.max():.4g}" if v.size else "n/a")
            ROWS.append(dict(section="variability", axis_a=a, axis_b=None, pft=t, n_unique=nu,
                             vmin=float(v.min()) if v.size else None,
                             vmax=float(v.max()) if v.size else None, n=sub.height))
        print(f"  {t:4d} {sub.height:13,d} " + " ".join(f"{c:>28s}" for c in cells))
    kv = df[QUERY].to_numpy()
    kv = kv[np.isfinite(kv)]
    mode = float(np.bincount(np.unique(kv, return_inverse=True)[1]).argmax())
    modes = np.unique(kv)[int(mode)]
    off = int((kv != modes).sum())
    print(f"\n  `{QUERY}` over ALL {kv.size:,} tree rows: {np.unique(kv).size} distinct value(s); "
          f"most common = {modes:.6g}; rows differing from it = {off:,} ({100 * off / kv.size:.6f} %)")
    ROWS.append(dict(section="variability_global", axis_a=QUERY, axis_b=None, pft=None,
                     n_unique=int(np.unique(kv).size), vmin=float(kv.min()), vmax=float(kv.max()),
                     n=int(kv.size), n_off_mode=off))
    if np.unique(kv).size > 1:
        vals, cnts = np.unique(kv, return_counts=True)
        for v, c in sorted(zip(vals, cnts), key=lambda p: -p[1])[:6]:
            print(f"      value {v:.6g}: {c:,} rows")

    print("\n--- 1. COUPLING: within-(PFT, age-bin) correlation among SURVIVORS ---")
    print("    the four substituted axes' mutual correlations are the scale to read `k_root` against")
    print(f"  {'pair':<26s} {'r':>9s} {'rows':>14s}")
    for i, a in enumerate(SUBST):
        for b in SUBST[i + 1:]:
            r, n = wcorr_within(surv, a, b)
            print(f"  {a + ' ~ ' + b:<26s} {r:+9.4f} {n:14,d}")
            ROWS.append(dict(section="coupling", axis_a=a, axis_b=b, pft=None, r=r, n=n))
    print("  " + "-" * 52)
    for a in SUBST:
        r, n = wcorr_within(surv, QUERY, a)
        print(f"  {QUERY + ' ~ ' + a:<26s} {r:+9.4f} {n:14,d}")
        ROWS.append(dict(section="coupling", axis_a=QUERY, axis_b=a, pft=None, r=r, n=n))

    print("\n--- 1b. THE SAME, PER PFT (a coupling present in only one PFT still matters there) ---")
    print(f"  {'pft':>4s} " + " ".join(f"{QUERY + '~' + a:>18s}" for a in SUBST) + f" {'rows':>13s}")
    for t in TREE_TYPES:
        sub = surv.filter(pl.col("Type") == t)
        if sub.height < 1000:
            continue
        rs = [wcorr_within(sub, QUERY, a)[0] for a in SUBST]
        print(f"  {t:4d} " + " ".join(f"{r:+18.4f}" for r in rs) + f" {sub.height:13,d}")
        for a, r in zip(SUBST, rs):
            ROWS.append(dict(section="coupling_per_pft", axis_a=QUERY, axis_b=a, pft=t, r=r,
                             n=sub.height))

    print("\n--- 2. SELECTION: one-year differential mean(trait | survives) - mean(trait | all), per PFT ---")
    print("    ADR 0046's statistic. An axis with no differential cannot carry a trait response.")
    print(f"  {'pft':>4s} {'rows':>13s} " + " ".join(f"{a:>13s}" for a in [QUERY, *SUBST]))
    for t in TREE_TYPES:
        sub = df.filter(pl.col("Type") == t)
        if sub.height < 1000:
            continue
        alive = sub.filter(pl.col("isdead") == 0)
        cells = []
        for a in [QUERY, *SUBST]:
            v = sub[a].to_numpy()
            v = v[np.isfinite(v)]
            ma, mall = alive[a].mean(), sub[a].mean()
            sd = sub[a].std()
            # A CONSTANT axis has no selection differential — it has an undefined one. Printing a ratio
            # whose denominator is ~0 manufactures a huge spurious number (this panel produced -284 for a
            # column with exactly one distinct value), so say `const` and record nothing.
            if np.unique(v).size <= 1 or not sd or sd <= 0:
                cells.append("        const")
                ROWS.append(dict(section="selection", axis_a=a, axis_b=None, pft=t, r=None,
                                 n=sub.height, constant=True))
                continue
            # report in units of the axis's own spread, so axes with different scales are comparable
            cells.append(f"{(ma - mall) / sd:+13.5f}")
            ROWS.append(dict(section="selection", axis_a=a, axis_b=None, pft=t,
                             diff_raw=(ma - mall), r=(ma - mall) / sd, n=sub.height, constant=False))
        print(f"  {t:4d} {sub.height:13,d} " + " ".join(f"{c:>13s}" for c in cells))

    pl.DataFrame(ROWS, infer_schema_length=None).write_csv(OUT)
    print(f"\nwrote {len(ROWS)} rows -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
