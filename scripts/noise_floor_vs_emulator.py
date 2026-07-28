#!/usr/bin/env python3
"""P3 noise-floor gate: is the Component-S emulator's per-cell skill at the IRREDUCIBLE seed1-vs-seed2 floor?

The steering P3 gate is "per-cell error vs the seed1-vs-seed2 noise floor". LPJmL-FIT is stochastic (RAND48
+ -DPERMUTE, CLAUDE.md §3): seed1 and seed2 are two equally-valid realizations of the SAME cell/climate, so
their per-cell disagreement is the IRREDUCIBLE uncertainty — no emulator conditioned on environment (not the
RNG) can beat it. This compares:
  • TRAITS — per-cell MEDIAN of each copula axis (SLA/Wooddens/D95max/minwscal): the emulator's per-cell-
    median Pearson r (vs seed1, from the copula OOS preds) vs the seed1-vs-seed2 per-cell-median r.
  • COUNTS — per-cell mean living-tree density (the emulator number comes from metrics.txt; see the CAVEAT).
It resolves the fig-10 concern: if a weak axis (Wooddens) sits AT its floor, its per-cell median is
RNG-dominated and irreducible; if the floor is far above, there is real model headroom (→ richer conditioning
or per-PFT structure, the ADR-0025 follow-on). ADR 0030 is the outcome; ADR 0031 is what it uncovered.

THE BASIS IS THE WHOLE BALLGAME (S1, 2026-07-28 — this replaces the pre-S1 single-basis version).
A floor is only comparable to the emulator if BOTH sides select the SAME stems. In the ACTIVE parameter file
(`/home/jamirp/lpjml56fit/par/pft_lpjmlfit.js`; `Type` == the 0-based `pftpar` index, `fscanpftpar.c:177`) the
PFT ids are:
    0 tropical broadleaved evergreen · 1 temperate needleleaved evergreen · 2 temperate broadleaved evergreen
    3 temperate broadleaved summergreen (Hainich beech) · 4 boreal needleleaved evergreen
    5 boreal broadleaved summergreen · 6 boreal needleleaved summergreen (larch) || 7/8/9 grass | 10-21 crops
so `Type <= 6` is exactly LPJmL-FIT's SEVEN tree PFTs, while every slow-* builder selects only
TREE_TYPES = [1,2,3,4,5] (build_slow_runtime_table.py:74, python/.../data.py:68 — note the sibling constant
python/.../features.py:50 has the full [0..6]). The emulator is therefore trained and scored on a TRUNCATED
tree population that omits the tropical evergreen and the boreal larch — see ADR 0031. That truncation, NOT
median instability, is what produced the un-interpretable pre-S1 `seed1-basis` cross-checks (SLA 0.973 but
Wooddens 0.488 / minwscal 0.092): FIT draws each trait UNIFORMLY from a PER-PFT [low, high] interval
(`new_tree.c:195-206` / `getrndinterval`), and id 0's minwscal interval [0.05, 0.75] (measured per-stem median
0.497) reaches far outside the [0.025, 0.30] span the truncated table covers at all, so the two seed1 medians
were measuring different PFT mixtures. This script therefore reports the floor on THREE bases, most-authoritative first:

  1. `copula`  — seed1 `Y_<axis>.f64` vs seed2 `Y_<axis>.f64`, both from build_slow_runtime_table.py
                 MODE=copula with IDENTICAL settings (static boundary, no STEM_CAP, same soilmoist/lai
                 coverage gate) and only SEED differing. DEFINITIVE FOR SCORING TODAY'S EMULATOR: its observed
                 values ARE seed1's Y, so floor and emulator share one stem-selection code path, byte for byte.
  2. `tree5`   — the same TRUNCATED population re-derived independently from the annual `ind` parquets
                 (`Type` in TREE_TYPES). Agreement between 1 and 2 is the cross-check that the comparison is
                 apples-to-apples (they differ only by the ≤2% conditioning-join coverage gate) — it reads
                 1.000 on all four axes.
  3. `tree7`   — `Type <= 6`, i.e. FIT's COMPLETE tree set. This is the population the emulator SHOULD cover
                 (ADR 0031), so its floor describes the real forest — but its GAP/verdict columns are NOT a
                 gap, because today's emulator is scored on a different (truncated) population. Read its
                 `seed1-basis` column as the SIZE of the truncation per axis, not as a defect of the floor.

Per basis: the per-axis Pearson/Spearman floor, the emulator r on the SAME cell set, the GAP, and the
`seed1-basis` cross-check r(parquet median, copula-table Y median) — which must be ≈1 for a basis whose GAP is
to be quoted at all.

SPLIT-HALF decomposition (free, same data): each cell's seed1 stems are split by within-cell rank parity and
the two half-medians correlated (raw, plus the Spearman-Brown full-length correction 2r/(1+r)). That isolates
the FINITE-STEM-SAMPLE component of the floor: split-half ≈ 1 while the seed floor is < 1 ⇒ the seed
disagreement is genuine trajectory divergence (a different forest, not a different sample of one forest).
The same split is applied to `pred`, which decides which CEILING is fair (below).

ATTENUATION (why the raw GAP is only a LOWER bound on the headroom): floor_r = r(seed1, seed2) is a
REALIZATION-vs-REALIZATION correlation, so it is the ceiling only for a predictor whose per-cell median is
exactly as noisy as one seed's. It is not: the emulator's median carries draw noise but NO trajectory
divergence, so it is measurably MORE stable (its split-half reliability rel_P exceeds rel_Y = floor_r). The
reachable ceiling — perfect center, dispersion left as this emulator's — is sqrt(rel_P·rel_Y), and the
de-noised center skill is r_center = emu_r / sqrt(rel_P·rel_Y). Both ceilings and the derivation are in the
ATTENUATION block; quote r_center (and 1 − r_center as the headroom) with the idealizations named there.

COUNT CAVEAT (unchanged by S1, still true): the count floor below is a per-cell TOTAL survivor-stem count
pooled over all years and patches, whereas the count emulator targets per-(Cell,Patch,Year) `n_living`. They
are not like-for-like; the count floor is reported as an order-of-magnitude reference only, on all bases.

Run (SLURM; ~2 min, dominated by the two 21.7 GB parquet scans):
  scripts/sbatch_python.sh S-noisefloor scripts/noise_floor_vs_emulator.py
Env: COPULA_DIR / COPULA2_DIR (the seed1 / seed2 copula table dirs), MINSTEM (20), SKIP_PARQUET=1 (copula
basis only — seconds), SKIP_LEGACY=1 (skip the complete-tree-set `tree7` basis).
Rebuild the seed2 table (the prerequisite for basis 1) exactly like seed1 — nothing but SEED may differ:
  MODE=copula SCENARIO=historic SEED=2 OUT=/p/tmp/jamirp/emulator_global/slow_copula_historic_seed2 \
    TIME=02:00:00 NCPUS=32 scripts/sbatch_python.sh S-copula2 scripts/build_slow_runtime_table.py
"""

import os

import numpy as np
import polars as pl

BASE = "/p/tmp/jamirp/emulator_global"
SEED1 = f"{BASE}/ind_hist_seed1_all.parquet"
SEED2 = f"{BASE}/ind_hist_seed2_all.parquet"
# seed1 copula table: Y_<axis>.f64 (observed) + pred_<axis>.f64 (K-fold-by-cell OOS) + cells.i64
COPULA = os.environ.get("COPULA_DIR", f"{BASE}/slow_copula_historic")
# seed2 copula table: Y_<axis>.f64 + cells.i64 (same builder, SEED=2 — the definitive floor's other half)
COPULA2 = os.environ.get("COPULA2_DIR", f"{BASE}/slow_copula_historic_seed2")
AXES = ["SLA", "Wooddens", "D95max", "minwscal"]
TREE_TYPES = [1, 2, 3, 4, 5]        # THE emulator's basis (build_slow_runtime_table.py:74)
ALL_TREE_MAX_TYPE = 6               # `Type <= 6` == FIT's COMPLETE tree set (ids 0-6); 7/8/9 are grass
MINSTEM = int(os.environ.get("MINSTEM", "20"))   # match the fig-10 per-cell ≥20-stem filter


def pearson(a, b):
    return float(np.corrcoef(a, b)[0, 1]) if len(a) > 2 else float("nan")


def spearman(a, b):
    return pearson(np.argsort(np.argsort(a)), np.argsort(np.argsort(b)))


def percell_parquet(parquet, tree_only):
    """Per-cell survivor-tree median of each trait + survivor count, from an ind parquet (streamed).

    `tree_only=True` → the emulator's TRUNCATED basis (`Type` in TREE_TYPES = ids 1-5); False → FIT's
    COMPLETE tree set (`Type <= 6`). See ADR 0031: the truncated one is the defect, not this filter.
    """
    filt = (pl.col("Type").is_in(TREE_TYPES) if tree_only else (pl.col("Type") <= ALL_TREE_MAX_TYPE))
    q = (
        pl.scan_parquet(parquet)
        .select(["Cell", "Type", "isdead", *AXES])
        .filter(filt & (pl.col("isdead") == 0))
        .group_by("Cell")
        .agg([pl.col(a).median().alias(f"med_{a}") for a in AXES] + [pl.len().alias("nstem")])
    )
    return q.collect(engine="streaming")


def percell_table(table_dir, with_pred, with_halves=False):
    """Per-cell median of each axis from a copula TABLE dir (Y_<axis>.f64, optional pred_<axis>.f64).

    `with_halves` also returns, per axis, the two within-cell rank-parity half-medians (the split-half
    finite-sample diagnostic). Row order in the table is the builder's deterministic sort on
    (Cell, Patch, Year), so parity on the within-cell row rank splits each cell's stems into two
    interleaved halves of near-equal size.
    """
    cells = np.fromfile(f"{table_dir}/cells.i64", dtype="<i8")
    out = None
    for a in AXES:
        cols = {"Cell": cells, "y": np.fromfile(f"{table_dir}/Y_{a}.f64", dtype="<f8")}
        if len(cols["y"]) != len(cells):
            raise SystemExit(f"FATAL: {table_dir}/Y_{a}.f64 has {len(cols['y'])} rows, cells.i64 has {len(cells)}")
        if with_pred:
            cols["p"] = np.fromfile(f"{table_dir}/pred_{a}.f64", dtype="<f8")
            if len(cols["p"]) != len(cells):
                raise SystemExit(f"FATAL: {table_dir}/pred_{a}.f64 rows != cells.i64 rows")
        df = pl.DataFrame(cols)
        aggs = [pl.col("y").median().alias(f"y_{a}"), pl.len().alias(f"n_{a}")]
        if with_pred:
            aggs.append(pl.col("p").median().alias(f"p_{a}"))
        if with_halves:
            df = df.with_columns((pl.int_range(pl.len()).over("Cell") % 2).alias("_half"))
            aggs += [
                pl.col("y").filter(pl.col("_half") == 0).median().alias(f"h0_{a}"),
                pl.col("y").filter(pl.col("_half") == 1).median().alias(f"h1_{a}"),
            ]
            if with_pred:   # the same split on the PREDICTIONS: is median(pred) per cell RNG-free?
                aggs += [
                    pl.col("p").filter(pl.col("_half") == 0).median().alias(f"ph0_{a}"),
                    pl.col("p").filter(pl.col("_half") == 1).median().alias(f"ph1_{a}"),
                ]
        d = df.group_by("Cell").agg(aggs)
        out = d if out is None else out.join(d, on="Cell", how="inner")
    # a cell's stem count is axis-independent (one row per stem, all axes present) — keep one column
    return out.rename({f"n_{AXES[0]}": "nstem"}).drop([f"n_{a}" for a in AXES[1:]])


def verdict(gap):
    if gap <= 0.05:
        return "AT FLOOR (irreducible)"
    return f"HEADROOM (+{gap:.3f})" if gap > 0.10 else f"near floor (+{gap:.3f})"


def report(name, note, floor1, floor2, emu, show_basis=False, same_population=True):
    """One basis block: per-axis floor (floor1 vs floor2), the emulator r on the SAME cells, and the gap.

    `floor1`/`floor2` carry per-cell medians (`med_<axis>`) + `nstem` of the two seeds under THIS basis; `emu`
    carries the emulator's observed (`y_<axis>`) + predicted (`p_<axis>`) per-cell medians (copula basis, already
    ≥MINSTEM-filtered). `show_basis=True` adds the cross-check r(this basis's seed1 median, copula-table Y
    median) — it must be ≈1 for the basis to be comparable with the emulator at all.
    """
    j = (floor1.filter(pl.col("nstem") >= MINSTEM)
         .join(floor2.filter(pl.col("nstem") >= MINSTEM), on="Cell", suffix="_s2")
         .join(emu, on="Cell", how="inner"))
    print(f"\n== BASIS `{name}` — {note}")
    print(f"   {j.height} cells (≥{MINSTEM} survivor stems in BOTH seeds, present in the emulator OOS set)")
    hdr = f"   {'axis':10s} {'emu_r':>7s} {'emu_ρ':>7s} | {'floor_r':>8s} {'floor_ρ':>8s} | {'GAP':>7s} | verdict"
    if show_basis:
        hdr += "   [seed1-basis]"
    print(hdr)
    rows = {}
    for a in AXES:
        m1 = j[f"med_{a}"].to_numpy()
        m2 = j[f"med_{a}_s2"].to_numpy()
        yv, pv = j[f"y_{a}"].to_numpy(), j[f"p_{a}"].to_numpy()
        floor_r, floor_rho = pearson(m1, m2), spearman(m1, m2)
        emu_r, emu_rho = pearson(yv, pv), spearman(yv, pv)
        gap = floor_r - emu_r
        v = verdict(gap) if same_population else "— cross-population: NOT a gap (see ADR 0031)"
        line = (f"   {a:10s} {emu_r:7.3f} {emu_rho:7.3f} | {floor_r:8.3f} {floor_rho:8.3f} | "
                f"{gap:7.3f} | {v}")
        if show_basis:
            line += f"   {pearson(m1, yv):11.3f}"
        print(line)
        rows[a] = (emu_r, floor_r, gap)
    c1, c2 = j["nstem"].to_numpy(), j["nstem_s2"].to_numpy()
    print(f"   COUNT (per-cell TOTAL survivor stems, all years/patches — NOT the emulator's per-(Cell,Patch,"
          f"Year) target): floor r={pearson(c1, c2):.4f} (r²={pearson(c1, c2) ** 2:.4f}) ρ={spearman(c1, c2):.4f}")
    return rows


def main():
    print(f"== copula table (seed1, observed+OOS pred): {COPULA}")
    print(f"== copula table (seed2, the floor's other half): {COPULA2}")
    e1 = percell_table(COPULA, with_pred=True, with_halves=True)
    print(f"   seed1 copula basis: {e1.height} cells", flush=True)
    e2 = percell_table(COPULA2, with_pred=False)
    print(f"   seed2 copula basis: {e2.height} cells", flush=True)
    # the emulator side is ≥MINSTEM-filtered ONCE here, so every basis block below is scored on cells the
    # emulator itself is evaluated on (this reproduces the pre-S1 `n>=MINSTEM` filter on the copula side).
    emu = (e1.filter(pl.col("nstem") >= MINSTEM)
           .select(["Cell"] + [c for a in AXES for c in (f"y_{a}", f"p_{a}")]))

    # ---- BASIS 1: the copula table itself — identical builder/gate/stem filter, only SEED differs -------
    r_cop = report(
        "copula", "seed1 Y vs seed2 Y — DEFINITIVE (same builder, same coverage gate, only SEED differs)",
        e1.select(["Cell", "nstem"] + [f"y_{a}" for a in AXES]).rename({f"y_{a}": f"med_{a}" for a in AXES}),
        e2.select(["Cell", "nstem"] + [f"y_{a}" for a in AXES]).rename({f"y_{a}": f"med_{a}" for a in AXES}),
        emu,
    )

    # ---- SPLIT-HALF: how much of the floor's shortfall is finite-stem sampling vs trajectory divergence --
    # Scored on the SAME cells as BASIS 1 (both seeds ≥MINSTEM) so half_r and floor_r are directly comparable.
    # `SB_full` = the Spearman-Brown full-length correction 2r/(1+r) — the reliability a FULL-stem-count median
    # would have if the ONLY noise source were the finite stem sample. Read it against floor_r:
    #   SB_full ≈ floor_r  ⇒ the seed-to-seed disagreement IS finite-sample noise (nothing else to explain).
    #   SB_full ≫ floor_r  ⇒ sampling is negligible; the two seeds grew genuinely DIFFERENT forests.
    # Caveats: the halves are stratified by construction (parity over a (Cell,Patch,Year)-sorted list, so both
    # halves span the same years/patches), and Spearman-Brown is classical-parallel-test theory applied to a
    # median — so SB_full is an OPTIMISTIC (upper) estimate of full-length reliability. That biases the read
    # toward "trajectory divergence", so treat a SB_full ≈ floor_r verdict as the robust one.
    print("\n== SPLIT-HALF (seed1 only, within-cell rank parity): isolates the FINITE-SAMPLE component")
    print(f"   {'axis':10s} {'half_r':>7s} {'SB_full':>8s} | {'floor_r':>8s} | interpretation")
    h = (e1.filter(pl.col("nstem") >= MINSTEM)
         .join(e2.filter(pl.col("nstem") >= MINSTEM).select("Cell"), on="Cell", how="inner"))
    rel_p = {}
    for a in AXES:
        hr = pearson(h[f"h0_{a}"].to_numpy(), h[f"h1_{a}"].to_numpy())
        sb = 2 * hr / (1 + hr)
        pr = pearson(h[f"ph0_{a}"].to_numpy(), h[f"ph1_{a}"].to_numpy())
        rel_p[a] = 2 * pr / (1 + pr)
        fr = r_cop[a][1]
        interp = ("finite-sample noise EXPLAINS the floor" if abs(sb - fr) <= 0.02 else
                  "trajectory divergence dominates (sampling explains only part)" if sb > fr else
                  "anomaly: half-split noisier than the seed disagreement — check the split")
        print(f"   {a:10s} {hr:7.3f} {sb:8.3f} | {fr:8.3f} | {interp}  [pred half_r={pr:.4f} "
              f"SB={rel_p[a]:.4f}]")

    # ---- ATTENUATION: the ceiling this emulator can actually reach, and its de-noised center skill ---------
    # `floor_r` is a REALIZATION-vs-REALIZATION correlation, so quoting it as "the ceiling" is only right for a
    # predictor whose per-cell statistic is exactly as noisy as one seed's. Classical attenuation, with a
    # per-cell median written as truth m = μ(env) + δ(RNG realization) and prediction p = ν(env) + ε(draw RNG):
    #     emu_r = r(p, m) = r(ν, μ) · √rel_P · √rel_Y
    #   rel_Y = reliability of ONE seed's median as a measure of μ = the two seeds' correlation = floor_r
    #           (two seeds are parallel forms — that IS the classical reliability coefficient).
    #   rel_P = reliability of the emulator's median as a measure of ν = its OWN split-half SB above (its only
    #           noise source is the draw RNG / the within-cell x-mixture, the same structure as Y's split-half).
    # ⇒ CEILING (perfect center ν=μ, dispersion left exactly as this emulator's) = √(rel_P · rel_Y), and the
    #   de-noised center skill is r_center = emu_r / √(rel_P · rel_Y), with 1 − r_center the real headroom.
    # Sanity: a TRUTH-LIKE sampler (rel_P = rel_Y) has ceiling = floor_r; a NOISELESS predictor (rel_P = 1) has
    # ceiling = √floor_r. rel_P > rel_Y here (the emulator's median is MORE stable than one seed's, because it
    # carries no trajectory divergence), so the ceiling sits between floor_r and √floor_r — and a raw
    # `floor_r − emu_r` gap therefore UNDERSTATES the headroom on every axis.
    # Idealizations to name when quoting: equal per-seed variance, δ ⟂ ε ⟂ μ, homoscedastic across cells,
    # linear (Pearson) association, and SB (classical parallel-test theory) applied to a median.
    print("\n== ATTENUATION-CORRECTED headroom — the ceiling this emulator can actually reach")
    print(f"   {'axis':10s} {'emu_r':>7s} {'rel_Y':>7s} {'rel_P':>7s} | {'ceiling':>8s} {'GAP':>7s} | "
          f"{'r_center':>8s} {'headroom':>8s} | verdict")
    for a in AXES:
        emu_r, fr, _ = r_cop[a]
        ceil = float(np.sqrt(rel_p[a] * fr))
        gap = ceil - emu_r
        r_center = emu_r / ceil
        v = ("AT CEILING" if gap <= 0.02 else "near ceiling" if gap <= 0.05 else f"HEADROOM (+{gap:.3f})")
        print(f"   {a:10s} {emu_r:7.3f} {fr:7.3f} {rel_p[a]:7.3f} | {ceil:8.3f} {gap:7.3f} | "
              f"{r_center:8.3f} {1 - r_center:8.3f} | {v}")
    print("   (rel_P > rel_Y ⇒ the emulator's per-cell median is MORE stable than one seed's — it carries no "
          "trajectory\n    divergence — so the raw floor_r − emu_r gap above is a LOWER bound on the headroom.)")

    # ---- BETWEEN-CELL DISPERSION: does the emulator differentiate cells as much as the truth does? --------
    # A correlation says nothing about scale. A second REALIZATION has the same between-cell spread as the
    # first (sd ratio ≈ 1) — that is the reference. If the emulator's per-cell medians are systematically
    # LESS spread out, it is regressing cells toward the global mean, i.e. the conditioning does not separate
    # cells enough. `slope` = OLS slope of truth-on-prediction; > 1 is the same statement in regression form.
    print("\n== BETWEEN-CELL DISPERSION of per-cell medians (correlation is scale-blind; this is not)")
    print(f"   {'axis':10s} {'sd(Y_seed1)':>12s} {'sd(Y2)/sd(Y1)':>14s} {'sd(pred)/sd(Y1)':>16s} "
          f"{'slope Y1~pred':>14s}")
    j2 = (e1.filter(pl.col("nstem") >= MINSTEM)
          .join(e2.filter(pl.col("nstem") >= MINSTEM), on="Cell", how="inner", suffix="_s2"))
    for a in AXES:
        v1 = j2[f"y_{a}"].to_numpy()
        v2 = j2[f"y_{a}_s2"].to_numpy()
        vp = j2[f"p_{a}"].to_numpy()
        slope = float(np.polyfit(vp, v1, 1)[0])
        print(f"   {a:10s} {v1.std():12.5g} {v2.std() / v1.std():14.4f} {vp.std() / v1.std():16.4f} "
              f"{slope:14.4f}")

    # ---- per-cell-median distribution shape (the discreteness caveat, quantified) -----------------------
    print("\n== per-cell-median distribution (copula basis, seed1): is the axis discrete/degenerate?")
    print(f"   {'axis':10s} {'n_unique':>9s} {'std':>12s} {'IQR':>12s} {'min':>12s} {'max':>12s}")
    for a in AXES:
        v = h[f"y_{a}"].to_numpy()
        q1, q3 = np.percentile(v, [25, 75])
        print(f"   {a:10s} {len(np.unique(v)):9d} {v.std():12.5g} {q3 - q1:12.5g} {v.min():12.5g} {v.max():12.5g}")

    # ---- BASIS 2/3: the parquet re-derivations (independent code path; the real cross-check) ------------
    if os.environ.get("SKIP_PARQUET", "") not in ("", "0", "no"):
        print("\n== SKIP_PARQUET set — copula basis only.")
        return 0
    for tree_only, name, note in (
        (True, "tree5", f"parquet, Type in TREE_TYPES={TREE_TYPES} — the emulator's TRUNCATED population, "
                        f"re-derived independently (its `seed1-basis` must read ≈1.000)"),
        (False, "tree7", f"parquet, Type <= {ALL_TREE_MAX_TYPE} — FIT's COMPLETE tree set (ids 0-6; grass is "
                         f"7/8/9). The population the emulator SHOULD cover (ADR 0031): its floor is the real "
                         f"forest's, but its GAP is cross-population. `seed1-basis` = the truncation's size."),
    ):
        if not tree_only and os.environ.get("SKIP_LEGACY", "") not in ("", "0", "no"):
            continue
        print(f"\n== scanning parquets for basis `{name}`...", flush=True)
        p1 = percell_parquet(SEED1, tree_only)
        p2 = percell_parquet(SEED2, tree_only)
        print(f"   seed1: {p1.height} cells · seed2: {p2.height} cells", flush=True)
        report(name, note, p1, p2, emu, show_basis=True, same_population=tree_only)

    print("\n== DONE noise_floor_vs_emulator ==", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
