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
so `Type <= 6` is exactly LPJmL-FIT's SEVEN tree PFTs. Until 2026-07-28 every slow-* builder selected only
`[1,2,3,4,5]` (a stale copy of `python/.../data.py`, which ADR 0031 corrected to the full `[0..6]` that
`python/.../features.py:50` always had), so the emulator was trained and scored on a TRUNCATED tree population
omitting the tropical evergreen and the boreal larch. Both bases are still reported here, because which one is
the same-population basis depends on WHICH TABLE you point `COPULA_DIR` at: `TREE_TYPES` below is IMPORTED, so
`same_population` follows the constant instead of a hard-coded id list. That truncation, NOT
median instability, is what produced the un-interpretable pre-S1 `seed1-basis` cross-checks (SLA 0.973 but
Wooddens 0.488 / minwscal 0.092): FIT draws each trait UNIFORMLY from a PER-PFT [low, high] interval
(`new_tree.c:195-206` / `getrndinterval`), and id 0's minwscal interval [0.05, 0.75] (measured per-stem median
0.497) reaches far outside the [0.025, 0.30] span the truncated table covers at all, so the two seed1 medians
were measuring different PFT mixtures. This script therefore reports the floor on THREE bases, most-authoritative first:

  1. `copula`  — seed1 `Y_<axis>.f64` vs seed2 `Y_<axis>.f64`, both from build_slow_runtime_table.py
                 MODE=copula with IDENTICAL settings (static boundary, no STEM_CAP, same soilmoist/lai
                 coverage gate) and only SEED differing. DEFINITIVE FOR SCORING TODAY'S EMULATOR: its observed
                 values ARE seed1's Y, so floor and emulator share one stem-selection code path, byte for byte.
  2/3. `tree7` / `tree5` — the two populations re-derived independently from the annual `ind` parquets. The
                 one matching the IMPORTED `TREE_TYPES` (post-ADR-0031: `tree7`, FIT's complete set) is the
                 SAME-population basis: agreement between it and basis 1 is the cross-check that the
                 comparison is apples-to-apples (they differ only by the ≤2% conditioning-join coverage gate)
                 and its `seed1-basis` must read ≈1.000 for its GAP to be quotable at all. The OTHER
                 (`tree5`, the pre-0031 truncated basis, kept for the before/after table) is CROSS-population:
                 its floor is a real floor for its own population, but its GAP/verdict columns are not a gap,
                 and its `seed1-basis` column reads as the SIZE of the truncation per axis.

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

STRUCT AXES (BIOMASS `agb` + SIZE `Height`) — OPT-IN, DIAGNOSTIC, AND OUTSIDE THE GATE.
When BOTH copula tables declare the same appended manifest lines `nstruct` / `struct_axes`, every block
below ALSO prints `[diag]`-labelled rows for those per-stem structural axes: the same floor / emulator r /
GAP / split-half / attenuation / between-cell-dispersion arithmetic, on exactly the same cells, so the
owner's "is the emulator's BIOMASS / SIZE distribution matched?" is answered on the very basis ADR 0030
defined for the traits (`sd(pred)/sd(Y1)` is the distribution-width half of that answer; the correlation
alone is scale-blind). They are diagnostic in the strict sense:
  • the PASS/FAIL reading of this gate — the production trait axes' GAP, r_center and the `seed1-basis`
    ≥0.99 population-consistency check — is computed from the trait axes ONLY and never sees a struct
    number, and no struct axis can change the exit code (every struct read is wrapped: a missing,
    short or unreadable struct file is REPORTED and SKIPPED, never fatal);
  • they are deliberately absent from the serialized production `.rcop` artifact (line M pins it and
    `slow.jl::make_recruit_to_pools` maps the 4 production axes onto carbon pools — ADR 0025, a frozen
    cross-line contract), so this script is the only place they are scored;
  • if the two seeds' tables declare DIFFERENT struct-axis sets (or only one declares any), the
    disagreement is printed and the struct rows are skipped — the sets are never silently intersected.
Absent `nstruct`/`struct_axes` ⇒ no struct axes ⇒ this script's output is byte-identical to its pre-struct
self, so every table dir built before struct axes existed keeps working unchanged.

Run (SLURM; ~2 min, dominated by the two 21.7 GB parquet scans):
  scripts/sbatch_python.sh S-noisefloor scripts/noise_floor_vs_emulator.py
Env: COPULA_DIR / COPULA2_DIR (the seed1 / seed2 copula table dirs), MINSTEM (20), SKIP_PARQUET=1 (copula
basis only — seconds), SKIP_LEGACY=1 (skip the CROSS-population basis, i.e. whichever of tree7/tree5 is not
the imported `TREE_TYPES`), SKIP_STRUCT=1 (suppress the diagnostic struct rows entirely). The struct rows add
NO extra parquet scan — they ride along as two more columns of the same per-cell aggregation.
Rebuild the seed2 table (the prerequisite for basis 1) exactly like seed1 — nothing but SEED may differ:
  MODE=copula SCENARIO=historic SEED=2 OUT=/p/tmp/jamirp/emulator_global/slow_copula_historic_seed2 \
    TIME=02:00:00 NCPUS=32 scripts/sbatch_python.sh S-copula2 scripts/build_slow_runtime_table.py
"""

import os
import sys
from pathlib import Path

import numpy as np
import polars as pl

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "python" / "src"))
from lpjmlfit_emulator import data as ind_data  # noqa: E402

BASE = "/p/tmp/jamirp/emulator_global"
SEED1 = f"{BASE}/ind_hist_seed1_all.parquet"
SEED2 = f"{BASE}/ind_hist_seed2_all.parquet"
# seed1 copula table: Y_<axis>.f64 (observed) + pred_<axis>.f64 (K-fold-by-cell OOS) + cells.i64
COPULA = os.environ.get("COPULA_DIR", f"{BASE}/slow_copula_historic")
# seed2 copula table: Y_<axis>.f64 + cells.i64 (same builder, SEED=2 — the definitive floor's other half)
COPULA2 = os.environ.get("COPULA2_DIR", f"{BASE}/slow_copula_historic_seed2")
AXES = ["SLA", "Wooddens", "D95max", "minwscal"]
# THE emulator's basis, IMPORTED from the one constant every builder now shares (ADR 0031) — so a future
# population change moves `same_population` here automatically instead of silently mis-labelling a basis.
TREE_TYPES = list(ind_data.TREE_TYPES)
LEGACY_TREE_TYPES = [1, 2, 3, 4, 5]  # the pre-ADR-0031 truncated basis, kept for the before/after comparison
ALL_TREE_MAX_TYPE = 6               # `Type <= 6` == FIT's COMPLETE tree set (ids 0-6); 7/8/9 are grass
MINSTEM = int(os.environ.get("MINSTEM", "20"))   # match the fig-10 per-cell ≥20-stem filter


def _read_manifest(table_dir):
    """Parse a `key\\tvalue` manifest_copula.txt; {} if absent (a pre-struct-axes table dir)."""
    p = Path(table_dir) / "manifest_copula.txt"
    if not p.is_file():
        return {}
    d = {}
    for line in p.read_text().splitlines():
        parts = line.rstrip("\n").split("\t")
        if len(parts) >= 2:
            d[parts[0]] = parts[1]
    return d


def resolve_struct_axes(dir1, dir2):
    """The DIAGNOSTIC struct axes both copula tables agree on — or [] with the reason printed.

    Never intersects a disagreement (a silently-narrowed column list is the ADR-0031 failure mode): if the
    two seeds declare different sets, or only one declares any, the sets are printed and NO struct row is
    produced. Also refuses an axis whose Y file is missing or the wrong length in either table, and an axis
    whose seed1 `pred_<axis>.f64` is absent (there would be nothing to score it against).
    """
    if os.environ.get("SKIP_STRUCT", "") not in ("", "0", "no"):
        print("== SKIP_STRUCT set — no diagnostic biomass/size rows.")
        return []
    s1 = _read_manifest(dir1).get("struct_axes", "").split()
    s2 = _read_manifest(dir2).get("struct_axes", "").split()
    if not s1 and not s2:
        return []
    if s1 != s2:
        print(f"== STRUCT AXES DISAGREE between the two tables — seed1 {s1} vs seed2 {s2}; struct rows SKIPPED "
              "(the sets are never silently intersected). Rebuild the seed2 table with the same STRUCT_AXES.")
        return []
    keep = []
    n1 = (Path(dir1) / "cells.i64").stat().st_size // 8
    n2 = (Path(dir2) / "cells.i64").stat().st_size // 8
    for a in s1:
        ok = True
        for d, n in ((dir1, n1), (dir2, n2)):
            f = Path(d) / f"Y_{a}.f64"
            if not f.is_file() or f.stat().st_size != n * 8:
                print(f"== struct axis {a!r}: {f} missing or wrong length — SKIPPED (diagnostic, never fatal)")
                ok = False
        pf = Path(dir1) / f"pred_{a}.f64"
        if ok and (not pf.is_file() or pf.stat().st_size != n1 * 8):
            print(f"== struct axis {a!r}: {pf} missing or wrong length — SKIPPED (nothing to score against)")
            ok = False
        if ok:
            keep.append(a)
    if keep:
        print(f"== DIAGNOSTIC struct axes (outside the gate, cannot change the exit code): {keep}")
    return keep


def pearson(a, b):
    return float(np.corrcoef(a, b)[0, 1]) if len(a) > 2 else float("nan")


def spearman(a, b):
    return pearson(np.argsort(np.argsort(a)), np.argsort(np.argsort(b)))


def percell_parquet(parquet, types, axes=None):
    """Per-cell survivor-tree median of each axis + survivor count, from an ind parquet (streamed).

    `types` is an explicit `Type` id list — the imported `TREE_TYPES` (FIT's complete set, the emulator's
    basis post-ADR-0031) or `LEGACY_TREE_TYPES` (the pre-0031 truncated one). Passing it explicitly is what
    keeps a floor and an emulator from being compared across two different stem populations.
    `axes` defaults to the 4 production traits; the diagnostic struct axes ride along as extra columns of
    THIS scan (they are ordinary `ind` columns), so enabling them costs no additional parquet pass.
    """
    axes = list(AXES) if axes is None else list(axes)
    filt = pl.col("Type").is_in(list(types))
    q = (
        pl.scan_parquet(parquet)
        .select(["Cell", "Type", "isdead", *axes])
        .filter(filt & (pl.col("isdead") == 0))
        .group_by("Cell")
        .agg([pl.col(a).median().alias(f"med_{a}") for a in axes] + [pl.len().alias("nstem")])
    )
    return q.collect(engine="streaming")


def percell_table(table_dir, with_pred, with_halves=False, axes=None):
    """Per-cell median of each axis from a copula TABLE dir (Y_<axis>.f64, optional pred_<axis>.f64).

    `with_halves` also returns, per axis, the two within-cell rank-parity half-medians (the split-half
    finite-sample diagnostic). Row order in the table is the builder's deterministic sort on
    (Cell, Patch, Year), so parity on the within-cell row rank splits each cell's stems into two
    interleaved halves of near-equal size.
    """
    axes = list(AXES) if axes is None else list(axes)
    cells = np.fromfile(f"{table_dir}/cells.i64", dtype="<i8")
    out = None
    for a in axes:
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
    return out.rename({f"n_{axes[0]}": "nstem"}).drop([f"n_{a}" for a in axes[1:]])


def verdict(gap):
    """Label for the RAW floor−emu gap. This gap is a LOWER BOUND on the headroom (it is the ceiling only for
    a predictor that is itself a fresh stochastic realization) — the ATTENUATION block below carries the
    verdict that counts. Hence "≥": never read a small raw gap as "nothing left to gain"."""
    if gap <= 0.05:
        return f"≥{gap:.3f} — at the third-realization floor (see ATTENUATION for the real gap)"
    return f"≥{gap:.3f} HEADROOM (lower bound)" if gap > 0.10 else f"≥{gap:.3f} (lower bound)"


def report(name, note, floor1, floor2, emu, show_basis=False, same_population=True, struct_axes=()):
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
    # The PRODUCTION trait axes decide this gate. The struct axes are printed after them, tagged `[diag]`,
    # from the same arithmetic on the same cells. They SHARE the returned dict (keyed by axis name), so the
    # isolation is by caller discipline, not by structure: every block that states a verdict iterates the trait
    # axes explicitly, and this script has no failure exit code at all, so a struct number cannot flip a
    # pass/fail. Do not add a gate here that loops the dict's keys without filtering on AXES.
    for a in list(AXES) + [s for s in struct_axes]:
        is_struct = a not in AXES
        if f"med_{a}" not in j.columns or f"p_{a}" not in j.columns:
            if is_struct:
                print(f"   {a:10s} [diag] — column absent on this basis, SKIPPED")
                continue
            raise SystemExit(f"FATAL: production axis {a} missing from the joined frame")
        m1 = j[f"med_{a}"].to_numpy()
        m2 = j[f"med_{a}_s2"].to_numpy()
        yv, pv = j[f"y_{a}"].to_numpy(), j[f"p_{a}"].to_numpy()
        floor_r, floor_rho = pearson(m1, m2), spearman(m1, m2)
        emu_r, emu_rho = pearson(yv, pv), spearman(yv, pv)
        gap = floor_r - emu_r
        if is_struct:
            v = "[diag] " + (verdict(gap) if same_population else "cross-population: NOT a gap")
        else:
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
    struct = resolve_struct_axes(COPULA, COPULA2)
    allax = list(AXES) + struct           # production FIRST, diagnostic appended — never interleaved
    e1 = percell_table(COPULA, with_pred=True, with_halves=True, axes=allax)
    print(f"   seed1 copula basis: {e1.height} cells", flush=True)
    e2 = percell_table(COPULA2, with_pred=False, axes=allax)
    print(f"   seed2 copula basis: {e2.height} cells", flush=True)

    # ---- THE TWO SEEDS MUST ACTUALLY BE TWO SEEDS -------------------------------------------------------
    # This whole gate defines the ceiling as `sqrt(rel_P * rel_Y)` with `rel_Y = floor_r`, the correlation
    # between two INDEPENDENT realizations. If the "second" realization is a copy of the first, `floor_r`
    # is 1 by construction, the ceiling goes to ~1, and every axis reports a FABRICATED headroom — with no
    # error anywhere. Nothing else here can catch that: the `seed1-basis >= 0.99` cross-check compares a
    # copula table to the parquet of the SAME seed, so it reads 1.000 and is blind to it.
    #
    # This is not hypothetical (`[VERIFIED 2026-07-31]`, ADR 0038). The ssp370 ground truth has a
    # `..._random_seed2` directory whose `ind_2020_2100.csv` is BIT-IDENTICAL to seed1's (same
    # 193,097,583,638 bytes; equal md5 on blocks at MB 0/30000/120000) because its config sets
    # `"random_seed": 2` but its `restart_filename` points at the HISTORIC *seed1* `restart_2019.lpj` —
    # under `-DFROM_RESTART` the per-cell RAND48 state is restored from that file, so the seed setting is
    # inert. (The historic pair is genuinely independent: each reads its own relative `restart_1999.lpj`,
    # and its files differ in size and content.) So "an ssp370/pooled seed2 exists" is a trap, and the
    # cost of falling into it is an invented ceiling in an accepted ADR.
    dup_axes = []
    for a in allax:
        j = e1.select(["Cell", f"y_{a}"]).join(e2.select(["Cell", f"y_{a}"]), on="Cell", how="inner",
                                               suffix="_s2")
        v1 = j[f"y_{a}"].to_numpy()
        v2 = j[f"y_{a}_s2"].to_numpy()
        if v1.size and np.array_equal(v1, v2):
            dup_axes.append(a)
    if dup_axes:
        raise SystemExit(
            f"FATAL: seed1 and seed2 per-cell medians are BIT-IDENTICAL on {dup_axes} — these are not two\n"
            f"   independent realizations, so no floor/ceiling/GAP may be quoted from them.\n"
            f"   seed1: {COPULA}\n   seed2: {COPULA2}\n"
            f"   Most likely cause: the seed2 run restarted from the SEED1 restart file, which restores the\n"
            f"   per-cell RAND48 state and makes `\"random_seed\"` inert under -DFROM_RESTART. Confirmed for\n"
            f"   the ssp370 ground truth (ADR 0038). A real seed2 needs its own spin-up/restart lineage."
        )
    # A weaker but still fatal variant: distinct floats that are nonetheless implausibly close everywhere.
    # Report rather than abort, because a genuinely tiny floor is a legitimate (if alarming) measurement.
    for a in AXES:
        j = e1.select(["Cell", f"y_{a}"]).join(e2.select(["Cell", f"y_{a}"]), on="Cell", how="inner",
                                               suffix="_s2")
        v1, v2 = j[f"y_{a}"].to_numpy(), j[f"y_{a}_s2"].to_numpy()
        if v1.size:
            same = float(np.mean(v1 == v2))
            if same > 0.5:
                print(f"   WARNING: {a}: {same:.1%} of per-cell medians are EXACTLY equal between the two "
                      f"seeds — suspect a shared restart lineage, not a real floor.")
    # the emulator side is ≥MINSTEM-filtered ONCE here, so every basis block below is scored on cells the
    # emulator itself is evaluated on (this reproduces the pre-S1 `n>=MINSTEM` filter on the copula side).
    emu = (e1.filter(pl.col("nstem") >= MINSTEM)
           .select(["Cell"] + [c for a in allax for c in (f"y_{a}", f"p_{a}")]))

    # ---- BASIS 1: the copula table itself — identical builder/gate/stem filter, only SEED differs -------
    r_cop = report(
        "copula", "seed1 Y vs seed2 Y — DEFINITIVE (same builder, same coverage gate, only SEED differs)",
        e1.select(["Cell", "nstem"] + [f"y_{a}" for a in allax]).rename({f"y_{a}": f"med_{a}" for a in allax}),
        e2.select(["Cell", "nstem"] + [f"y_{a}" for a in allax]).rename({f"y_{a}": f"med_{a}" for a in allax}),
        emu, struct_axes=struct,
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
    for a in allax:
        if a not in r_cop:
            continue
        hr = pearson(h[f"h0_{a}"].to_numpy(), h[f"h1_{a}"].to_numpy())
        sb = 2 * hr / (1 + hr)
        pr = pearson(h[f"ph0_{a}"].to_numpy(), h[f"ph1_{a}"].to_numpy())
        rel_p[a] = 2 * pr / (1 + pr)
        fr = r_cop[a][1]
        interp = ("finite-sample noise EXPLAINS the floor" if abs(sb - fr) <= 0.02 else
                  "trajectory divergence dominates (sampling explains only part)" if sb > fr else
                  "anomaly: half-split noisier than the seed disagreement — check the split")
        tag = "" if a in AXES else "[diag] "
        print(f"   {a:10s} {hr:7.3f} {sb:8.3f} | {fr:8.3f} | {tag}{interp}  [pred half_r={pr:.4f} "
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
    for a in allax:
        if a not in r_cop or a not in rel_p:
            continue
        emu_r, fr, _ = r_cop[a]
        ceil = float(np.sqrt(rel_p[a] * fr))
        gap = ceil - emu_r
        r_center = emu_r / ceil
        v = ("AT CEILING" if gap <= 0.02 else "near ceiling" if gap <= 0.05 else f"HEADROOM (+{gap:.3f})")
        if a not in AXES:
            v = "[diag] " + v
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
    for a in allax:
        v1 = j2[f"y_{a}"].to_numpy()
        v2 = j2[f"y_{a}_s2"].to_numpy()
        vp = j2[f"p_{a}"].to_numpy()
        slope = float(np.polyfit(vp, v1, 1)[0])
        print(f"   {a:10s} {v1.std():12.5g} {v2.std() / v1.std():14.4f} {vp.std() / v1.std():16.4f} "
              f"{slope:14.4f}{'' if a in AXES else '   [diag]'}")

    # ---- per-cell-median distribution shape (the discreteness caveat, quantified) -----------------------
    print("\n== per-cell-median distribution (copula basis, seed1): is the axis discrete/degenerate?")
    print(f"   {'axis':10s} {'n_unique':>9s} {'std':>12s} {'IQR':>12s} {'min':>12s} {'max':>12s}")
    for a in allax:
        v = h[f"y_{a}"].to_numpy()
        q1, q3 = np.percentile(v, [25, 75])
        print(f"   {a:10s} {len(np.unique(v)):9d} {v.std():12.5g} {q3 - q1:12.5g} {v.min():12.5g} "
              f"{v.max():12.5g}{'' if a in AXES else '   [diag]'}")

    # ---- BASIS 2/3: the parquet re-derivations (independent code path; the real cross-check) ------------
    if os.environ.get("SKIP_PARQUET", "") not in ("", "0", "no"):
        print("\n== SKIP_PARQUET set — copula basis only.")
        return 0
    # Which parquet basis is SAME-population is decided by the IMPORTED constant, never hard-coded: the
    # emulator's population is whatever `TREE_TYPES` says, so post-ADR-0031 `tree7` carries the quotable GAP
    # and `tree5` is the cross-population before/after row (pre-0031 it was the other way round).
    _emu_types = sorted(TREE_TYPES)
    bases = [(_emu_types, True, "the emulator's population, re-derived independently (its `seed1-basis` must "
                                "read ≈1.000 for the GAP below to be quotable)")]
    if sorted(LEGACY_TREE_TYPES) != _emu_types:
        bases.append((sorted(LEGACY_TREE_TYPES), False,
                      "the pre-ADR-0031 TRUNCATED population (dropped id 0 tropical evergreen + id 6 larch = "
                      "32.5% of survivor stems), kept for the before/after — its GAP is CROSS-population"))
    for types, same_population, note in bases:
        name = f"tree{len(types)}"
        if not same_population and os.environ.get("SKIP_LEGACY", "") not in ("", "0", "no"):
            continue
        note = f"parquet, Type in {types} — {note}"
        print(f"\n== scanning parquets for basis `{name}` "
              f"({'SAME' if same_population else 'CROSS'}-population)...", flush=True)
        p1 = percell_parquet(SEED1, types, axes=allax)
        p2 = percell_parquet(SEED2, types, axes=allax)
        print(f"   seed1: {p1.height} cells · seed2: {p2.height} cells", flush=True)
        report(name, note, p1, p2, emu, show_basis=True, same_population=same_population, struct_axes=struct)

    print("\n== DONE noise_floor_vs_emulator ==", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
