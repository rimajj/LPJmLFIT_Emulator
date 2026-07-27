#!/usr/bin/env python3
"""P3 noise-floor gate: is the Component-S emulator's per-cell skill at the IRREDUCIBLE seed1-vs-seed2 floor?

The steering P3 gate is "per-cell error vs the seed1-vs-seed2 noise floor". LPJmL-FIT is stochastic (RAND48
+ -DPERMUTE, CLAUDE.md §3): seed1 and seed2 are two equally-valid realizations of the SAME cell/climate, so
their per-cell disagreement is the IRREDUCIBLE uncertainty — no emulator conditioned on environment (not the
RNG) can beat it. This compares:
  • COUNTS  — per-cell mean living-tree density: emulator OOS per-cell r² (metrics.txt) vs seed1-vs-seed2 r².
  • TRAITS  — per-cell MEDIAN of each copula axis (SLA/Wooddens/D95max/minwscal): the emulator's per-cell-
    median Pearson r (vs seed1, from the copula OOS preds) vs the seed1-vs-seed2 per-cell-median r.
It DIRECTLY resolves the fig-10 concern: if Wooddens' emulator r≈0.52 sits at a seed1-vs-seed2 floor also
≈0.5, the "weak" axis is IRREDUCIBLE (per-cell wood-density median is RNG-dominated, not model headroom); if
the floor is ≈0.9, there is real model headroom (→ richer conditioning, ADR-0025 follow-on).

Basis (kept identical across seeds): survivor TREE stems only (Type ≤ 6, isdead == 0 — ADR-0025 survivor
marginal, matching build_slow_runtime_table.py:153); per (Cell) aggregate over all years/patches; cells with
≥ MINSTEM survivor stems in BOTH seeds. The FLOOR (seed1-parquet vs seed2-parquet) uses ONE method for both
seeds ⇒ it is clean regardless.

BASIS CAVEAT (observed 2026-07-27, characterized not hand-waved): the `seed1-basis` column cross-checks the
parquet all-years seed1 median against the copula-table Y (seed1) median. It is high for SLA (0.97) but LOW
for Wooddens (0.49) and minwscal (0.09) — NOT a coverage-gate artifact (that join drops ≤2%,
build_slow_runtime_table.py:164). The mismatch ordering tracks each trait's per-cell-median STABILITY:
minwscal is heavily clamped/discrete (fig 09 spikes 0.10/0.15/0.20/0.30) so its per-cell median flips on
tiny stem-set differences; Wooddens is year-variable. So for those two axes the emulator (copula basis) and
the floor (all-years parquet basis) are NOT apples-to-apples — read their emu-vs-floor GAP qualitatively
(floor high ⇒ learnable ⇒ headroom), not as an exact number. A basis-clean per-axis floor needs the seed2
copula table rebuilt (MODE=copula SEED=2) — a scoped follow-up. SLA/D95max are basis-clean enough to trust.

Run:  scripts/sbatch_python.sh noisefloor scripts/noise_floor_vs_emulator.py
"""

import numpy as np
import polars as pl

BASE = "/p/tmp/jamirp/emulator_global"
SEED1 = f"{BASE}/ind_hist_seed1_all.parquet"
SEED2 = f"{BASE}/ind_hist_seed2_all.parquet"
COPULA = f"{BASE}/slow_copula_historic"          # Y_<axis>.f64 / pred_<axis>.f64 / cells.i64 (seed1 OOS)
AXES = ["SLA", "Wooddens", "D95max", "minwscal"]
MINSTEM = 20                                      # match the fig-10 per-cell ≥20-stem filter


def pearson(a, b):
    return float(np.corrcoef(a, b)[0, 1]) if len(a) > 2 else float("nan")


def spearman(a, b):
    return pearson(np.argsort(np.argsort(a)), np.argsort(np.argsort(b)))


def percell(parquet):
    """Per-cell survivor-tree median of each trait + survivor count, from an ind parquet (streamed)."""
    q = (
        pl.scan_parquet(parquet)
        .select(["Cell", "Type", "isdead", *AXES])
        .filter((pl.col("Type") <= 6) & (pl.col("isdead") == 0))
        .group_by("Cell")
        .agg(
            [pl.col(a).median().alias(f"med_{a}") for a in AXES]
            + [pl.len().alias("nstem")]
        )
    )
    return q.collect(streaming=True)


def main():
    print("== computing per-cell survivor-tree trait medians (seed1)...", flush=True)
    s1 = percell(SEED1)
    print(f"   seed1: {s1.height} cells", flush=True)
    print("== computing per-cell survivor-tree trait medians (seed2)...", flush=True)
    s2 = percell(SEED2)
    print(f"   seed2: {s2.height} cells", flush=True)

    j = s1.join(s2, on="Cell", suffix="_s2")
    j = j.filter((pl.col("nstem") >= MINSTEM) & (pl.col("nstem_s2") >= MINSTEM))
    print(f"== {j.height} cells with ≥{MINSTEM} survivor stems in BOTH seeds", flush=True)

    # emulator per-cell median (seed1 Y = observed) + emulator OOS prediction, keyed by copula cells.i64
    ccells = np.fromfile(f"{COPULA}/cells.i64", dtype="<i8")
    emu = {}   # axis -> DataFrame(Cell, y_med, pred_med)
    for a in AXES:
        y = np.fromfile(f"{COPULA}/Y_{a}.f64", dtype="<f8")
        p = np.fromfile(f"{COPULA}/pred_{a}.f64", dtype="<f8")
        d = (
            pl.DataFrame({"Cell": ccells, "y": y, "p": p})
            .group_by("Cell")
            .agg(pl.col("y").median().alias(f"y_{a}"), pl.col("p").median().alias(f"p_{a}"), pl.len().alias("n"))
            .filter(pl.col("n") >= MINSTEM)
            .drop("n")
        )
        emu[a] = d

    print("\n== TRAIT per-cell-median skill: EMULATOR (vs seed1) vs NOISE FLOOR (seed1 vs seed2) ==")
    print(f"{'axis':10s} {'emu_r':>7s} {'emu_ρ':>7s} | {'floor_r':>8s} {'floor_ρ':>8s} | {'seed1-basis':>11s} | verdict")
    for a in AXES:
        jj = j.join(emu[a], on="Cell", how="inner")
        m1 = jj[f"med_{a}"].to_numpy()          # seed1 parquet median
        m2 = jj[f"med_{a}_s2"].to_numpy()       # seed2 parquet median
        yv = jj[f"y_{a}"].to_numpy()            # emulator observed (copula Y, seed1)
        pv = jj[f"p_{a}"].to_numpy()            # emulator prediction
        floor_r = pearson(m1, m2); floor_rho = spearman(m1, m2)
        emu_r = pearson(yv, pv); emu_rho = spearman(yv, pv)
        basis = pearson(m1, yv)                 # do the two seed1 definitions agree? (≈1 ⇒ clean comparison)
        gap = floor_r - emu_r
        verdict = ("AT FLOOR (irreducible)" if gap <= 0.05 else
                   f"HEADROOM (+{gap:.2f} to floor)" if gap > 0.10 else "near floor")
        print(f"{a:10s} {emu_r:7.3f} {emu_rho:7.3f} | {floor_r:8.3f} {floor_rho:8.3f} | {basis:11.3f} | {verdict}  (n={len(m1)})")

    # COUNTS: per-cell survivor-tree count noise floor (emulator per-cell-mean r² = 0.9994 from metrics.txt)
    c1 = j["nstem"].to_numpy(); c2 = j["nstem_s2"].to_numpy()
    print(f"\n== COUNT per-cell survivor-stem noise floor: seed1-vs-seed2 r={pearson(c1, c2):.4f} "
          f"(r²={pearson(c1, c2) ** 2:.4f}) ρ={spearman(c1, c2):.4f}")
    print("   (emulator count per-cell-mean r²=0.9994 / per-row r²=0.9852 from figures/.../historic/metrics.txt)")
    print("\n== DONE noise_floor_vs_emulator ==", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
