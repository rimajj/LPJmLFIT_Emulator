#!/usr/bin/env python3
"""RUNG 0, STAGE 1 — reduce the two ground-truth seeds to the small per-cell tables a YARDSTICK needs.

WHY THIS EXISTS
---------------
`EXECUTION_PLAN.md` rung 0: *"the emulator is being scored against ONE roll of a stochastic model's dice,
and for two trait axes the dice are louder than the signal."* Fixing that needs three things, and all three
are functions of the SAME small per-cell reduction of the two seeds:

  1. a per-cell, per-quantity NOISE FLOOR (counts, stand carbon, the four trait medians), stratified by
     stem density — the `max(10 %, the model's own two-run spread)` half of ADR 0106's tolerance;
  2. the reliability `λ = Var(signal)/(Var(signal)+Var(noise))` of the single-seed RESPONSE, so a scored
     response slope can be DEATTENUATED;
  3. an AGGREGATE response metric (area-weighted), because the per-cell response is below its own noise in
     a third of cells (ADR 0093 §3d) and a per-cell single-seed response plot is mostly noise.

This script does ONLY the reduction (the expensive part: 2.55e9 stem-year rows across four parquets).
`scripts/diagnose_truth_yardstick.py` consumes its output and computes 1-3.

THE BASIS IS THE WHOLE BALLGAME — and this script emits THREE bases on purpose
------------------------------------------------------------------------------
A noise floor is only comparable to a score if BOTH are computed the same way (ADR 0030). The published
per-cell trait response slopes (ADR 0109: SLA +0.851, Wooddens +0.346, D95max +0.163, minwscal +0.689) come
from `diagnose_moisture_arm_response.py`, whose truth is the per-cell median of `Y_<axis>.f64` **pooled over
every row of a scenario** in a copula table built with `STEM_CAP=400`. So:

  * `cell_pooled`  — per-cell median pooled over ALL years and patches, UNCAPPED. The physical statistic:
                     its two-seed spread is the irreducible trajectory noise of the real forest.
  * `cell_capped`  — the same, after replicating `build_slow_runtime_table.py`'s STEM_CAP cluster
                     subsample (hash of (Cell,Patch,Year) + row index, seeded by SEED, keep the lowest
                     `CAP` ranks per cell). This is the basis the published slope was scored on, so THIS is
                     the λ that may legitimately be divided into it. It is noisier than `cell_pooled`
                     because the cap keeps whole PATCH-YEARS, so its effective sample size is patch-years,
                     not stems (the correction recorded at build_slow_runtime_table.py:432).
                     ⚠ APPROXIMATION, stated not hidden: the production cap is applied AFTER the
                     conditioning join, which drops ≤2 % of stems; here there is no join, so the retained
                     set differs from the production table's by that ≤2 %. It bounds the cap's noise
                     contribution; it does not reproduce the production row set byte-for-byte.
  * `cell_year`    — per (Cell, Year): stem count, patch count, summed biomass/vegetation carbon, and the
                     YEARLY trait medians. Feeds the count/carbon floor, the density stratification, and a
                     windowed response basis (mean of yearly medians over a 20-yr window), which is the
                     statistic a response SHOULD be scored on and is not the one that was.

WHAT COUNTS AS A TREE: `Type <= 6` (all seven tree PFTs — ADR 0031; `TREE_TYPES` is IMPORTED, never
re-declared) and `isdead == 0` (survivors), i.e. exactly `build_slow_runtime_table.py`'s `stem_filt`.

KEY-SET GUARD (load-bearing, CLAUDE.md §4): polars `collect(engine="streaming")` over these tables is NOT
deterministic in the KEY SET it emits — two runs of one `group_by` differed by 4 913 rows and DUPLICATED
keys in 12 cells (ADR 0036 §5b). Every aggregate written here asserts its own key uniqueness; a coverage
check on row counts alone cannot see it, because duplication makes the usual `dropped` statistic negative.

Usage (SLURM — this is a multi-hundred-GB scan, never run it on the login node):
    scripts/sbatch_python.sh S-yardstick scripts/build_truth_yardstick_tables.py
Env: OUT (default /p/tmp/jamirp/emulator_global/yardstick_v1)
     SCENARIOS (historic,ssp370)  SEEDS (1,2)  CAP (400, 0 disables the capped basis)
     CELLS (optional comma list, for a smoke test)
Collect: logs/S-yardstick.<jobid>.out — one `[done]` line per (scenario, seed, basis).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import polars as pl

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "python" / "src"))
from lpjmlfit_emulator import data as ind_data  # noqa: E402

TREE_TYPES = list(ind_data.TREE_TYPES)

BASE = "/p/tmp/jamirp/emulator_global"
IND = {
    "historic": f"{BASE}/ind_hist_seed{{seed}}_all.parquet",
    "ssp370": f"{BASE}/ind_ssp370_seed{{seed}}_all.parquet",
}
#: the four production recruit-trait axes (ADR 0025) plus the two diagnostic struct axes (ADR 0030's
#: `[diag]` biomass/size block) plus Age, which the age-trait gradient work needs (ADR 0049).
AXES = ["SLA", "Wooddens", "D95max", "minwscal", "Height", "Age"]

OUT = Path(os.environ.get("OUT", f"{BASE}/yardstick_v1"))
SCENARIOS = [s.strip() for s in os.environ.get("SCENARIOS", "historic,ssp370").split(",") if s.strip()]
SEEDS = [int(s) for s in os.environ.get("SEEDS", "1,2").split(",") if s.strip()]
CAP = int(os.environ.get("CAP", "400"))
CELLS = [int(c) for c in os.environ.get("CELLS", "").split(",") if c.strip()]


def _stem_filter() -> pl.Expr:
    f = pl.col("Type").is_in(TREE_TYPES) & (pl.col("isdead") == 0)
    if CELLS:
        f = f & pl.col("Cell").is_in(CELLS)
    return f


def _assert_unique(df: pl.DataFrame, keys: list[str], what: str) -> None:
    """The ADR-0036 §5b guard: a streamed group_by can DUPLICATE keys, which no row-count check sees."""
    n_uniq = df.select(keys).n_unique()
    if n_uniq != df.height:
        raise SystemExit(
            f"FATAL: {what} has {df.height} rows but only {n_uniq} unique {keys} — the streaming "
            f"group_by duplicated keys (ADR 0036 §5b). Re-run; do not use this table."
        )


def _write(df: pl.DataFrame, path: Path, keys: list[str], what: str) -> None:
    _assert_unique(df, keys, what)
    df = df.sort(keys)
    df.write_parquet(path)
    print(f"   [done] {what}: {df.height:,} rows, {df['Cell'].n_unique():,} cells -> {path.name}", flush=True)


def _median_exprs() -> list[pl.Expr]:
    return [pl.col(a).median().alias(f"{a}_med") for a in AXES]


def cell_year(scenario: str, seed: int) -> pl.DataFrame:
    """Per (Cell, Year): the count/carbon aggregates and the YEARLY trait medians."""
    return (
        pl.scan_parquet(IND[scenario].format(seed=seed))
        .filter(_stem_filter())
        .select(["Cell", "Year", "Patch", "agb", "vegc"] + AXES)
        .group_by(["Cell", "Year"])
        .agg(
            [
                pl.len().cast(pl.Int64).alias("n_stems"),
                pl.col("Patch").n_unique().cast(pl.Int32).alias("n_patch"),
                pl.col("agb").sum().alias("agb_sum"),
                pl.col("vegc").sum().alias("vegc_sum"),
            ]
            + _median_exprs()
        )
        .collect(engine="streaming")
    )


def cell_pooled(scenario: str, seed: int, cap: int) -> pl.DataFrame:
    """Per Cell: trait medians pooled over ALL years and patches. `cap>0` replicates STEM_CAP first."""
    lf = (
        pl.scan_parquet(IND[scenario].format(seed=seed))
        .filter(_stem_filter())
        .select(["Cell", "Patch", "Year"] + AXES)
    )
    if cap > 0:
        # byte-for-byte the production rank expression (build_slow_runtime_table.py:447-450): the hash is of
        # the (Cell,Patch,Year) TUPLE, so a whole patch-year shares one hash and the cap keeps whole clusters.
        lf = (
            lf.with_columns(
                (
                    pl.struct(["Cell", "Patch", "Year"]).hash(seed=seed)
                    + pl.int_range(pl.len(), dtype=pl.UInt64)
                )
                .rank("ordinal")
                .over("Cell")
                .alias("_rk")
            )
            .filter(pl.col("_rk") <= cap)
            .drop("_rk")
        )
    return (
        lf.group_by("Cell")
        .agg([pl.len().cast(pl.Int64).alias("n_stems"), pl.col("Patch").n_unique().cast(pl.Int32).alias("n_patch")]
             + _median_exprs())
        .collect(engine="streaming")
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print("=" * 100)
    print("RUNG 0 STAGE 1 — two-seed truth reduction for the yardstick")
    print("=" * 100)
    print(f"  OUT={OUT}  SCENARIOS={SCENARIOS}  SEEDS={SEEDS}  CAP={CAP}  TREE_TYPES={TREE_TYPES}")
    print(f"  CELLS={'ALL' if not CELLS else CELLS}")
    for scenario in SCENARIOS:
        for seed in SEEDS:
            src = IND[scenario].format(seed=seed)
            if not Path(src).exists():
                raise SystemExit(f"FATAL: missing ground-truth table {src}")
            print(f"\n== {scenario} seed{seed}  <- {src}", flush=True)
            t0 = time.time()
            df = cell_year(scenario, seed)
            _write(df, OUT / f"cell_year_{scenario}_seed{seed}.parquet", ["Cell", "Year"],
                   f"cell_year {scenario} seed{seed}")
            print(f"      ({time.time() - t0:.0f} s)", flush=True)

            t0 = time.time()
            df = cell_pooled(scenario, seed, 0)
            _write(df, OUT / f"cell_pooled_{scenario}_seed{seed}.parquet", ["Cell"],
                   f"cell_pooled(uncapped) {scenario} seed{seed}")
            print(f"      ({time.time() - t0:.0f} s)", flush=True)

            if CAP > 0:
                t0 = time.time()
                df = cell_pooled(scenario, seed, CAP)
                _write(df, OUT / f"cell_capped{CAP}_{scenario}_seed{seed}.parquet", ["Cell"],
                       f"cell_capped{CAP} {scenario} seed{seed}")
                print(f"      ({time.time() - t0:.0f} s)", flush=True)

    # per-scenario name so historic and ssp370 can be submitted as two concurrent jobs into ONE dir
    man_name = "manifest_yardstick_" + "_".join(SCENARIOS) + ".txt"
    (OUT / man_name).write_text(
        "\n".join(
            [
                "stage\t1 (two-seed truth reduction)",
                f"tree_types\t{' '.join(str(t) for t in TREE_TYPES)}",
                "stem_filter\tType in tree_types AND isdead == 0",
                f"axes\t{' '.join(AXES)}",
                f"scenarios\t{' '.join(SCENARIOS)}",
                f"seeds\t{' '.join(str(s) for s in SEEDS)}",
                f"cap\t{CAP}",
                f"cells\t{'ALL' if not CELLS else ','.join(str(c) for c in CELLS)}",
                "cap_caveat\tthe production cap is applied AFTER the conditioning join (<=2% of stems); "
                "this one is not, so the retained set differs by that <=2%",
                "",
            ]
        )
    )
    print(f"\nwrote {OUT / man_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
