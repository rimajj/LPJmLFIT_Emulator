#!/usr/bin/env python3
"""build_rung2_boundary_series.py — the per-(cell, scenario, YEAR) slow-boundary tail a rung-2 arm feeds
the production count model, emitted as a plain CSV the Julia harness reads.

WHY THIS EXISTS — the frozen-climate trap that makes a warming response ZERO BY CONSTRUCTION
--------------------------------------------------------------------------------------------
`scripts/rung2_s_demography_harness.jl` used to read its 4-column boundary tail ONCE, from the
per-cell registry `test/testitems/references/M_cells.csv`, and pass that same vector into every
year's feature row. That registry's value is the PRESENT-DAY CLIMATOLOGY: the per-cell 2000-2019
mean, which is why it coincides with the trailing-20-year window's final (2019) row — Hainich's
`eco_diag_gdd_5` is 1863.695 in both, and its `soil_depth` matches bit-for-bit.  (Its
`tas_cold_month` differs from the w20 2019 row by 4 float32 ulps, the CLAUDE.md §4
`group_by().mean()` Float32-accumulation trap, not a different quantity.) Under ssp370 the same
cell's growing-season warmth index runs 1967.7 (2020) -> 2573.0 (2100).  So a scenario-pair
experiment on the static tail would show the count model PRESENT-DAY climate for all 81 future
years, and the two legs would differ ONLY through the roster state.  The warming response would come
out near zero no matter how good or bad the demography is — an unfalsifiable measurement, not a null
result (guardrail 7 / the `residual-diagnosis` reference-basis rule).

The shipped runtime does NOT have this defect: `FluxDrivenSlowEmulator` carries `boundary_series`
and `reconcile_demography!` advances `s.boundary` to the year's row before building the feature row
(ADR 0026). The harness simply never used the mechanism.  This script produces that series, so the
arm and the deployed emulator condition on the SAME per-(cell,year) bioclimate — which is the
train/inference-consistency requirement of ADR 0023, not a nicety.

THE DEFINITION IS IMPORTED, NEVER RE-DERIVED
--------------------------------------------
The tail is `BOUNDARY_COLS = [eco_diag_gdd_5, tas_cold_month, soil_depth, co2]` and its values come
from `build_slow_runtime_table._boundary_source(scenario)` under `BOUNDARY_WINDOW=20` — the *same
call* the training table makes, so the arm cannot drift from the artifact it is scoring.  A second
transcription of a per-cell constant is ADR 0031's failure mode (a stale copy of `TREE_TYPES`
silently dropped 32.5 % of tree stems for months).  `co2` stays the constant 369.0: the emulator
does not see CO2 and must not respond to it (ADR 0004/0107) — holding it fixed here is faithfulness,
not a gap.

⚠ `BOUNDARY_WINDOW` is FORCED to 20 here rather than read from the environment.  The pooled
production artifact `drf_forest_global_pooled_w20_t8.drf` is named for, and was trained under, W=20;
letting the caller pick a different window would silently condition the arm on a boundary the forest
never saw.

USAGE
    python3 scripts/build_rung2_boundary_series.py --cell 42490 --scenario historic --out <path.csv>
    python3 scripts/build_rung2_boundary_series.py --cells 42490,52059 --scenario ssp370 --outdir <dir>

The CSV is `Year,eco_diag_gdd_5,tas_cold_month,soil_depth,co2`, one row per simulated year,
ascending, with a `#` provenance header.  The harness matches on the YEAR COLUMN, not on row
position, so a run whose first year is not the table's first year is still correct.
"""

from __future__ import annotations

import argparse
import os
import sys

import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# The window the pooled production forest was trained under. Set BEFORE the import so the
# module-level constants and `_boundary_source` agree with the artifact being scored.
os.environ["BOUNDARY_WINDOW"] = "20"

from build_slow_runtime_table import (  # noqa: E402  (import must follow the env pin above)
    BOUNDARY_COLS,
    CO2_CONST,
    _boundary_source,
)

# The scenario year spans the C actually simulates, from the restart files named in CLAUDE.md §1:
# historic  restart_1999.lpj -> 2000-2019 ssp370    restart_2019.lpj -> 2020-2100
SCENARIO_YEARS = {"historic": (2000, 2019), "ssp370": (2020, 2100)}


def boundary_series(scenario: str, cells: list[int]) -> pl.DataFrame:
    """Per-(cell, year) boundary tail for `cells`, in the runtime column order.

    Returns a frame with `Cell`, `Year` and the four `BOUNDARY_COLS`. Raises if the transient table
    does
    not cover every requested cell-year: a silently missing row would become a null in the feature
    vector
    and the forest would score it against a bound it never trained on.
    """
    if scenario not in SCENARIO_YEARS:
        raise SystemExit(f"FATAL: scenario must be one of {sorted(SCENARIO_YEARS)} (got '{scenario}')")
    y0, y1 = SCENARIO_YEARS[scenario]

    src, keys = _boundary_source(scenario)
    if keys != ["Cell", "Year"]:
        raise SystemExit(
            f"FATAL: expected the TRANSIENT boundary (join keys ['Cell','Year']) but got {keys}. "
            "The static branch is scenario-blind and would freeze the climate channel — see this "
            "script's header."
        )

    df = (
        src.filter(pl.col("Cell").is_in(cells) & pl.col("Year").is_between(y0, y1))
        .with_columns(pl.lit(CO2_CONST).alias("co2"))
        .select(["Cell", "Year", *BOUNDARY_COLS])
        .sort(["Cell", "Year"])
    )

    # Completeness is the gate: every cell must carry every year of its scenario.
    want = y1 - y0 + 1
    got = df.group_by("Cell").len().rename({"len": "n"})
    missing = [c for c in cells if c not in set(got["Cell"])]
    if missing:
        raise SystemExit(f"FATAL: no transient boundary rows at all for cell(s) {missing} ({scenario})")
    short = got.filter(pl.col("n") != want)
    if short.height:
        raise SystemExit(
            f"FATAL: incomplete boundary coverage for {scenario} {y0}-{y1} (want {want} yr): "
            f"{short.to_dicts()}"
        )
    nulls = df.null_count().sum_horizontal().item()
    if nulls:
        raise SystemExit(f"FATAL: {nulls} null(s) in the boundary tail — a null feature is not scoreable")
    return df


def frozen_series(scenario: str, cells: list[int]) -> pl.DataFrame:
    """The FROZEN-CLIMATE CONTROL: the target scenario's YEARS carrying present-day climate values.

    WHY THE RESPONSE EXPERIMENT IS NOT INTERPRETABLE WITHOUT THIS ARM.  The two legs of the scenario
    pair have different LENGTHS — historic is 20 years from restart_1999, ssp370 is 81 years from
    restart_2019.  So `terminal(ssp370) - terminal(historic)` mixes two things that must not be
    added together:

        (a) the genuine climate response, and
        (b) 61 extra years of free-running DRIFT.

    A demography with ZERO climate sensitivity but a steady drift posts a large "response" on that
    definition, and a demography that drifts the other way can cancel a real response to nothing.
    Neither is distinguishable from the pair alone — the same class of unfalsifiable comparison as
    the frozen-boundary trap this module exists to fix.

    This control holds (b) fixed and removes (a): same 81 years, same restart, same seeds, same leg
    length — only the climate channel is frozen at the present-day climatology.  So

        climate response = terminal(arm, ssp370 transient) - terminal(arm, ssp370 FROZEN)

    is the arm's own climate sensitivity with drift differenced out, and

        drift            = terminal(arm, ssp370 FROZEN) - terminal(arm, historic)

    is what the arm does over 81 years when the climate does not move at all.

    The frozen VALUE is the historic series' final row, which under `BOUNDARY_WINDOW=20` is the
    trailing-20-year mean over 2000-2019 — i.e. exactly the present-day climatology the committed
    per-cell registry carries, so this control is also the like-for-like counterpart of the old
    static-tail behaviour.
    """
    y0, y1 = SCENARIO_YEARS[scenario]
    hist = boundary_series("historic", cells)
    last = hist.filter(pl.col("Year") == hist["Year"].max()).drop("Year")
    years = pl.DataFrame({"Year": list(range(y0, y1 + 1))}, schema={"Year": pl.Int64})
    return last.join(years, how="cross").select(["Cell", "Year", *BOUNDARY_COLS]).sort(["Cell", "Year"])


def write_csv(df: pl.DataFrame, cell: int, scenario: str, path: str) -> None:
    sub = df.filter(pl.col("Cell") == cell).sort("Year")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        f.write("# rung-2 transient slow-boundary series (ADR 0026 treatment, BOUNDARY_WINDOW=20)\n")
        f.write(f"# cell={cell} scenario={scenario} rows={sub.height}\n")
        f.write("# built by scripts/build_rung2_boundary_series.py from\n")
        f.write("#   build_slow_runtime_table._boundary_source() — the SAME source the training table uses\n")
        f.write(f"# co2 held constant at {CO2_CONST} (ADR 0004/0107: the emulator does not see CO2)\n")
        f.write("Year," + ",".join(BOUNDARY_COLS) + "\n")
        for r in sub.iter_rows(named=True):
            vals = ",".join(repr(float(r[c])) for c in BOUNDARY_COLS)
            f.write(f"{int(r['Year'])},{vals}\n")
    print(f"wrote {path}  ({sub.height} yr, {scenario}, cell {cell})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cell", type=int, help="a single orderA cell index")
    ap.add_argument("--cells", type=str, help="comma-separated orderA cell indices")
    ap.add_argument("--scenario", required=True, choices=sorted(SCENARIO_YEARS))
    ap.add_argument("--out", type=str, help="output CSV (single --cell only)")
    ap.add_argument("--outdir", type=str, help="output dir; files named boundary_<scenario>_c<cell>.csv")
    ap.add_argument("--freeze", action="store_true",
                    help="FROZEN-CLIMATE CONTROL: the scenario's years carrying present-day climate "
                         "(see frozen_series) — the arm that separates a real response from drift")
    a = ap.parse_args()

    cells = []
    if a.cell is not None:
        cells.append(a.cell)
    if a.cells:
        cells += [int(c) for c in a.cells.split(",") if c.strip()]
    if not cells:
        raise SystemExit("FATAL: give --cell or --cells")
    cells = sorted(set(cells))

    df = frozen_series(a.scenario, cells) if a.freeze else boundary_series(a.scenario, cells)

    # Report the spread the arm will actually see — a response experiment whose driver barely moves
    # is
    # worth knowing about BEFORE 300 SLURM jobs, not after.
    rng = df.group_by("Cell").agg(
        pl.col("eco_diag_gdd_5").first().alias("gdd_first"),
        pl.col("eco_diag_gdd_5").last().alias("gdd_last"),
        pl.col("tas_cold_month").first().alias("tcm_first"),
        pl.col("tas_cold_month").last().alias("tcm_last"),
    ).sort("Cell")
    print(f"== {a.scenario}: boundary drift across the leg (first -> last year)")
    for r in rng.iter_rows(named=True):
        print(
            f"   cell {r['Cell']:6d}  gdd5 {r['gdd_first']:9.2f} -> {r['gdd_last']:9.2f}"
            f"   tas_cold {r['tcm_first']:7.3f} -> {r['tcm_last']:7.3f}"
        )

    if a.out:
        if len(cells) != 1:
            raise SystemExit("FATAL: --out takes a single --cell; use --outdir for many")
        write_csv(df, cells[0], a.scenario, a.out)
    elif a.outdir:
        for c in cells:
            write_csv(df, c, a.scenario, os.path.join(a.outdir, f"boundary_{a.scenario}{'frz' if a.freeze else ''}_c{c}.csv"))
    else:
        raise SystemExit("FATAL: give --out or --outdir")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
