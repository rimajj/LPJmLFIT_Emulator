#!/usr/bin/env python3
"""select_rung2_response_cells.py — choose (and freeze) the cell set the rung-2 WARMING-RESPONSE experiment
runs on, and emit it as a committed CSV.

WHY A SCRIPT AND NOT A HAND-PICKED LIST.  ADR 0172 §5 set the bar at >= 12 named cells, and ADR 0174
§3d requires the result to be reported per cell with Cochran's Q rather than pooled — because
heterogeneous cells CANCEL when averaged and a pooled mean can read as "no response" while half the
cells respond strongly in each direction.  A set chosen by hand invites the reasonable suspicion
that it was chosen after seeing the answer, so the rule is written down here, applied once, and
committed with its output.

THE SELECTION RULE (pre-registered; it uses NO outcome and NO arm result)

  1. ELIGIBLE = trained in BOTH scenarios in the pooled production artifact
     (`slow_count_pooled_w20_t8`, 58 588 cells; 53 607 carry rows in both).  A cell the
     pooled forest never saw in one regime cannot be asked for that regime's answer.
  2. STAND SIZE >= `--min-nliving` (default 5.0) mean living stems in BOTH scenarios.  In a
     1-3 stem stand a single tree is 30-100 % of the count, so discreteness swamps any
     response; such a cell contributes noise, not signal.  This is a property of the
     BASELINE, not of any arm.
  3. STRATIFY on present-day `eco_diag_gdd_5` (the historic per-cell climatology) into
     `--nstrata` equal-COUNT strata over the eligible set, and take the cell closest to each
     stratum's median.  Equal-count, not equal-width, so the tropics do not get 9 of 12 slots.
  4. FORCE-INCLUDE the five canonical biome cells from `test/testitems/references/M_cells.csv`,
     so every earlier five-cell result (ADR 0125/0126/0172/0176) remains directly comparable.

⚠ NOTHING HERE MAY KEY ON THE WARMING SIGNAL ITSELF.  Selecting cells by how much their climate
moves — or by how much any arm responds — would manufacture the result the experiment is supposed to
measure. Strata are cut on PRESENT-DAY climate only.

Usage:
    python3 scripts/select_rung2_response_cells.py                      # writes the committed CSV
    CHECK=1 python3 scripts/select_rung2_response_cells.py    # verify only (exit 1 on drift)
"""

from __future__ import annotations

import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "/p/tmp/jamirp/emulator_global"
POOLED = f"{BASE}/slow_count_pooled_w20_t8"
CELL_YEAR_FEATS = f"{BASE}/tables/cell_year_feats.parquet"
M_CELLS = os.path.join(REPO, "test/testitems/references/M_cells.csv")
OUT = os.path.join(REPO, "test/testitems/references/S_rung2_response_cells.csv")

MIN_NLIVING = float(os.environ.get("MIN_NLIVING", "5.0"))
NSTRATA = int(os.environ.get("NSTRATA", "10"))
SC_HISTORIC, SC_SSP370 = 0, 1     # `scenario.i64` coding, verified against the five biome cells


def pooled_cell_table() -> pl.DataFrame:
    """Per-cell mean `n_living` per scenario, from the pooled forest's OWN training arrays.

    Read from the artifact rather than recomputed from the `ind` parquet: the question is what the
    FOREST
    was trained on, and a second derivation could disagree with it (ADR 0031).
    """
    cells = np.fromfile(f"{POOLED}/cells.i64", dtype=np.int64)
    y = np.fromfile(f"{POOLED}/y.f64", dtype=np.float64)
    sc = np.fromfile(f"{POOLED}/scenario.i64", dtype=np.int64)
    if not (len(cells) == len(y) == len(sc)):
        raise SystemExit(f"FATAL: ragged pooled arrays {len(cells)}/{len(y)}/{len(sc)}")
    df = pl.DataFrame({"Cell": cells, "y": y, "sc": sc})
    agg = df.group_by(["Cell", "sc"]).agg(pl.col("y").mean().alias("nliv"), pl.len().alias("rows"))
    hist = agg.filter(pl.col("sc") == SC_HISTORIC).select(
        "Cell", pl.col("nliv").alias("nliv_hist"), pl.col("rows").alias("rows_hist")
    )
    ssp = agg.filter(pl.col("sc") == SC_SSP370).select(
        "Cell", pl.col("nliv").alias("nliv_ssp"), pl.col("rows").alias("rows_ssp")
    )
    both = hist.join(ssp, on="Cell", how="inner")
    # Sanity: the row counts must look like 25 patches x ~20 vs ~81 years, or the scenario coding is
    # flipped.
    if both["rows_ssp"].median() <= both["rows_hist"].median():
        raise SystemExit(
            "FATAL: scenario coding looks flipped — ssp370 (81 yr) should carry more rows per cell than "
            f"historic (20 yr), got medians {both['rows_ssp'].median()} vs {both['rows_hist'].median()}"
        )
    return both


def gdd5_climatology() -> pl.DataFrame:
    """Present-day per-cell `eco_diag_gdd_5` (and `tas_cold_month`), the stratification axis.

    Cast to Float64 BEFORE the mean: `cell_year_feats` stores several env columns as Float32 and
    polars
    accumulates a Float32 `mean()` in Float32 (CLAUDE.md §4), which lands ~3e-7 relative off.
    """
    return (
        pl.scan_parquet(CELL_YEAR_FEATS)
        .select(
            "Cell",
            pl.col("eco_diag_gdd_5").cast(pl.Float64),
            pl.col("tas_cold_month").cast(pl.Float64),
        )
        .group_by("Cell")
        .mean()
        .collect()
    )


def canonical_cells() -> pl.DataFrame:
    rows = []
    hdr = None
    for line in open(M_CELLS):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if hdr is None:
            hdr = line.split(",")
            continue
        f = line.split(",")
        rows.append({"Cell": int(f[hdr.index("cell")]), "name": f[hdr.index("name")]})
    return pl.DataFrame(rows)


def select() -> pl.DataFrame:
    pooled = pooled_cell_table()
    gdd = gdd5_climatology()
    canon = canonical_cells()

    elig = (
        pooled.join(gdd, on="Cell", how="inner")
        .filter((pl.col("nliv_hist") >= MIN_NLIVING) & (pl.col("nliv_ssp") >= MIN_NLIVING))
        .sort("eco_diag_gdd_5")
    )
    print(f"== eligible: {elig.height} cells (both scenarios, mean n_living >= {MIN_NLIVING} in each)")

    canon_ids = set(canon["Cell"])
    missing = [c for c in canon_ids if c not in set(elig["Cell"])]
    if missing:
        # Report rather than fail: a canonical cell below the stand-size floor is still
        # force-included for
        # continuity, but the reader must know it sits outside the eligibility rule.
        print(f"   note: canonical cell(s) {missing} are outside the eligibility filter; included anyway")

    # Equal-COUNT strata over the eligible set, excluding the forced cells so they do not consume a
    # slot.
    pool = elig.filter(~pl.col("Cell").is_in(list(canon_ids)))
    g = pool["eco_diag_gdd_5"].to_numpy()
    edges = np.quantile(g, np.linspace(0, 1, NSTRATA + 1))
    picks: list[int] = []
    for i in range(NSTRATA):
        lo, hi = edges[i], edges[i + 1]
        sel = (g >= lo) & (g <= hi) if i == NSTRATA - 1 else (g >= lo) & (g < hi)
        idx = np.flatnonzero(sel)
        if idx.size == 0:
            continue
        med = np.median(g[idx])
        pick = int(idx[np.argmin(np.abs(g[idx] - med))])
        cell = int(pool["Cell"][pick])
        if cell not in picks:
            picks.append(cell)

    chosen = sorted(canon_ids | set(picks))
    out = (
        elig.join(canon, on="Cell", how="left")
        .filter(pl.col("Cell").is_in(chosen))
        .with_columns(
            pl.col("name").fill_null(pl.format("stratum_{}", pl.col("Cell"))),
            pl.lit(True).alias("eligible"),
        )
    )
    # Force-include any canonical cell the filter dropped.
    for c in missing:
        row = (
            pooled.join(gdd, on="Cell", how="inner")
            .filter(pl.col("Cell") == c)
            .join(canon, on="Cell", how="left")
            .with_columns(pl.lit(False).alias("eligible"))
        )
        out = pl.concat([out, row.select(out.columns)], how="vertical")
    return out.sort("eco_diag_gdd_5")


def main() -> int:
    df = select()
    cols = [
        "Cell", "name", "eco_diag_gdd_5", "tas_cold_month",
        "nliv_hist", "nliv_ssp", "rows_hist", "rows_ssp", "eligible",
    ]
    df = df.select(cols)
    print(f"== selected {df.height} cells")
    for r in df.iter_rows(named=True):
        print(
            f"   {r['Cell']:6d}  {r['name']:<22s} gdd5 {r['eco_diag_gdd_5']:9.1f}  "
            f"tcm {r['tas_cold_month']:7.2f}  n_living {r['nliv_hist']:5.2f} -> {r['nliv_ssp']:5.2f}"
        )

    body = ",".join(cols) + "\n"
    for r in df.iter_rows(named=True):
        body += ",".join(repr(r[c]) if isinstance(r[c], float) else str(r[c]) for c in cols) + "\n"
    header = (
        "# The rung-2 WARMING-RESPONSE cell set (line S). Generated by\n"
        "# scripts/select_rung2_response_cells.py — see that file for the pre-registered selection rule.\n"
        "# Cell = global orderA 0-based index. gdd5/tas_cold_month = PRESENT-DAY (2000-2019) climatology,\n"
        "# the stratification axis. nliv_* = mean living stems in the pooled forest's own training rows.\n"
        f"# rule: trained in both scenarios, mean n_living >= {MIN_NLIVING} in each, {NSTRATA} equal-count\n"
        "# gdd5 strata, plus the five canonical biome cells of M_cells.csv (continuity with ADR 0125/0176).\n"
    )
    text = header + body

    if os.environ.get("CHECK"):
        if not os.path.exists(OUT):
            print(f"CHECK: {OUT} does not exist")
            return 1
        cur = open(OUT).read()
        if cur != text:
            print(f"CHECK: {OUT} differs from a fresh derivation")
            return 1
        print(f"CHECK: {OUT} is current")
        return 0

    with open(OUT, "w") as f:
        f.write(text)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
