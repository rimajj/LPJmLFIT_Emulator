#!/usr/bin/env python3
"""Build the COMMITTED establishment-eligibility REGIME table — and do it on both cell bases at once.

WHY THIS EXISTS (line S, 2026-08-12)
------------------------------------
ADR 0171 §4 published a regime table ("`n_elig` = 0 is 11.2 % of tree-bearing cells, median 29 stems; the
modal cell admits four") with **no committed reproducer** — exactly the defect ADR 0118 §6 recorded against
ADR 0093 §5.3's Beta-vs-copula claim, in a new place and by the same line one day later. A number that
steers the next session's cell choice has to be re-derivable, so this script emits it as a gated fixture.

It also fixes a basis question that only appears once you try to USE the table. ADR 0171 counted over the
**52 451 cells with a `Type <= 6` stem in 2010** in FIT's own `ind` output. But the response arm can only run
where the **pinned artifact pair** has a trained row, i.e. a cell present in `cell_meta.parquet` for BOTH
scenarios — and those two universes weight the `n_elig = 0` class very differently, because the class is
concentrated in sparse cells that the training table's own row filters thin out. Reporting one basis alone
misstates how prevalent the untested regime is among the cells anything can actually be measured at, so this
emits **both, side by side** (ADR 0060's lesson: add the column, never substitute it).

Third thing it adds, and it is what actually decides whether an arm at such a cell is worth running:
**PERSISTENCE**. `n_elig` moves — 16 709 of 67 420 cells change their eligible set inside 2000-2019
(ADR 0170 §3) — so a single-year snapshot conflates "this cell is in the pure-inheritance regime" with "this
cell dipped into it once". A response arm runs 81 years; the regime it samples is the persistent one.

⚠ AND THAT DISTINCTION IS EXACTLY WHAT ADR 0171 §4's TABLE TURNS ON, which is what building this found.
Its header reads "(2010, `Type <= 6`)", which reads as a 2010 snapshot on both the cell selection AND the
`n_elig` classification. It is not: the classification is the **MINIMUM over the 20 historic years**, i.e.
`n_elig = 0` there means "closed in AT LEAST ONE of 20 years", not "closed". Measured here, on the ADR's own
cell universe (52 451, reproduced exactly): min-over-window puts **5 882 cells / 11.2 %** in class 0 — the
ADR's number — while the 2010 snapshot puts **1 931 / 3.7 %** there, and only **739 cells / 1.4 %** of the
runnable set are closed in all 20 years. So the "11.2 % pure-inheritance regime" the ADR sends the next
session to measure is mostly cells that dip into the regime, and the persistent regime is ~8x rarer. Both
definitions are emitted; the gate is on the ADR's.

OUTPUT (committed): test/testitems/references/S_estab_regime_table.csv
  one row per (basis, n_elig) with cell counts, shares, and the stem-count distribution, plus a
  `persistence` section keyed on how many of the 20 historic years the gate is closed.

GATE: the `ind`-basis row for `n_elig = 0` must reproduce ADR 0171 §4's published 5 882 cells / 11.2 % /
      29 median stems, or the script fails loudly — that is the check that this reproducer reproduces the
      claim it exists to support rather than quietly redefining it.

Env: IND (the historic seed-1 `ind` parquet) · ELIG_H / ELIG_S (the two eligibility tables) ·
     META_H / META_S (the pinned artifact's per-scenario cell_meta) · YEAR (2010, ADR 0171's snapshot year) ·
     OUT · NOGATE=1 (report the gate's delta instead of dying — for investigating a legitimate basis change)
Run (SLURM — the `ind` scan is ~92 GB):
     scripts/sbatch_python.sh S-regime scripts/build_estab_regime_table.py
"""

from __future__ import annotations

import os
import sys

import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFDIR = os.path.join(REPO, "test", "testitems", "references")
G = "/p/tmp/jamirp/emulator_global"

IND = os.environ.get("IND", f"{G}/ind_hist_seed1_all.parquet")
ELIG_H = os.environ.get("ELIG_H", f"{G}/tables/estab_eligibility_historic_w20.parquet")
ELIG_S = os.environ.get("ELIG_S", f"{G}/tables/estab_eligibility_ssp370_w20.parquet")
META_H = os.environ.get("META_H", f"{G}/slow_runtime_historic_t8/cell_meta.parquet")
META_S = os.environ.get("META_S", f"{G}/slow_runtime_ssp370_t8/cell_meta.parquet")
YEAR = int(os.environ.get("YEAR", "2010"))
OUT = os.environ.get("OUT", os.path.join(REFDIR, "S_estab_regime_table.csv"))
NOGATE = os.environ.get("NOGATE", "0") == "1"

# ADR 0171 §4's published row for the untested regime, on ITS OWN basis (`ind`, 2010, Type <= 6).
ADR0171 = {"cells": 5882, "share_pct": 11.2, "median_stems": 29.0}
TREE_TYPES_MAX = 6          # CLAUDE.md §3: pftpar ids 0-6 are ALL SEVEN tree PFTs; 7-9 are grass


def tree_cells(year: int) -> pl.DataFrame:
    """Per-cell stem count over `Type <= 6` in ONE year — ADR 0171 §4's own 'tree-bearing' definition.

    Counts ALL emitted stems (not only survivors): the `ind` writer already drops stems below 5 m
    (CLAUDE.md §3), and `isdead` rows are that year's casualties, which are part of the standing
    population the regime table is describing.
    """
    return (
        pl.scan_parquet(IND)
        .filter((pl.col("Year") == year) & (pl.col("Type") <= TREE_TYPES_MAX))
        .group_by("Cell")
        .agg(pl.len().alias("stems"))
        .collect(engine="streaming")
        # ⚠ CLAUDE.md §4: streaming group_by is NOT deterministic in its KEY SET at global scale —
        # assert our own key set rather than trusting a row-count delta (which duplication makes negative).
    )


def main() -> int:
    print(f"== YEAR={YEAR}  ind={IND}")
    tc = tree_cells(YEAR)
    assert tc.select("Cell").n_unique() == tc.height, (
        f"FATAL: streamed group_by emitted duplicated cell keys ({tc.height} rows, "
        f"{tc.select('Cell').n_unique()} unique) — CLAUDE.md §4's polars streaming trap. Re-run."
    )
    print(f"== basis A (ind, Type<={TREE_TYPES_MAX}, {YEAR}): {tc.height:,} tree-bearing cells, "
          f"{tc['stems'].sum():,} stems")

    mh = pl.read_parquet(META_H, columns=["Cell", "n_init"])
    ms = pl.read_parquet(META_S, columns=["Cell"])
    art = mh.join(ms, on="Cell", how="inner")
    print(f"== basis B (pinned t8 cell_meta, BOTH scenarios): {art.height:,} runnable cells")

    eh = pl.read_parquet(ELIG_H, columns=["Cell", "Year", "n_elig"])
    es = pl.read_parquet(ELIG_S, columns=["Cell", "Year", "n_elig"])
    # TWO classifications of the same cell, deliberately side by side (see the header):
    #   `minwin` = min over the historic window — ADR 0171 §4's actual basis; class 0 = "closed in >= 1 yr"
    #   `snap`   = the YEAR snapshot — what the ADR's header reads as; class 0 = "closed in that year"
    snap = eh.filter(pl.col("Year") == YEAR).select("Cell", "n_elig")
    minwin = eh.group_by("Cell").agg(pl.col("n_elig").min().alias("n_elig"))
    hy0, hy1 = eh["Year"].min(), eh["Year"].max()
    nyr = hy1 - hy0 + 1
    print(f"== eligibility: historic {hy0}-{hy1} ({nyr} yr), ssp370 {es['Year'].min()}-{es['Year'].max()}")

    # per-cell persistence over the historic window + whether the gate ever opens under ssp370
    per = (
        eh.group_by("Cell")
        .agg((pl.col("n_elig") == 0).sum().alias("n_closed_hist"))
        .join(es.group_by("Cell").agg(pl.col("n_elig").max().alias("ssp_max_elig")), on="Cell", how="left")
    )

    rows: list[dict] = []

    def emit_regime(section: str, basis: str, cls: pl.DataFrame, cells: pl.DataFrame,
                    stemcol: str, per_patch: bool) -> None:
        d = cells.join(cls, on="Cell", how="inner")
        tot = d.height
        mine = []
        for k in range(0, 8):
            sub = d.filter(pl.col("n_elig") == k)
            if not sub.height:
                continue
            med = float(sub[stemcol].median())
            r = dict(
                section=section, basis=basis, key=f"n_elig={k}", cells=sub.height,
                share_pct=round(100 * sub.height / tot, 2),
                median_stems_per_cell=round(med * 25 if per_patch else med, 1),
                median_stems_per_patch=round(med if per_patch else med / 25, 3),
                w_inherit=round(4 / (4 + k), 4),
            )
            rows.append(r)
            mine.append(r)
        print(f"\n-- {section.upper()} on basis {basis} ({tot:,} cells)")
        for r in mine:
            print(f"   {r['key']:9s} {r['cells']:6d} cells {r['share_pct']:5.1f} %  "
                  f"median {r['median_stems_per_cell']:7.1f} stems/cell  w_inherit={r['w_inherit']}")

    # ADR 0171 §4's basis first — it is the one the GATE is on.
    emit_regime("regime_minwin", "ind_treebearing", minwin, tc, "stems", per_patch=False)
    emit_regime("regime_minwin", "t8_runnable", minwin, art, "n_init", per_patch=True)
    emit_regime("regime_snapshot", "ind_treebearing", snap, tc, "stems", per_patch=False)
    emit_regime("regime_snapshot", "t8_runnable", snap, art, "n_init", per_patch=True)

    # PERSISTENCE — on the runnable basis, because that is the one an arm is chosen from
    d = art.join(per, on="Cell", how="inner")
    tot = d.height
    bands = [(nyr, nyr, f"closed all {nyr} yr"), (nyr // 2, nyr - 1, f"closed {nyr // 2}-{nyr - 1} yr"),
             (1, nyr // 2 - 1, f"closed 1-{nyr // 2 - 1} yr"), (0, 0, "never closed")]
    print(f"\n-- PERSISTENCE of a CLOSED gate over the {nyr} historic years, basis t8_runnable ({tot:,})")
    for lo, hi, lab in bands:
        sub = d.filter((pl.col("n_closed_hist") >= lo) & (pl.col("n_closed_hist") <= hi))
        if not sub.height:
            continue
        med = float(sub["n_init"].median())
        opens = int(sub.filter(pl.col("ssp_max_elig") > 0).height)
        rows.append(
            dict(section="persistence", basis="t8_runnable", key=lab, cells=sub.height,
                 share_pct=round(100 * sub.height / tot, 2),
                 median_stems_per_cell=round(med * 25, 1), median_stems_per_patch=round(med, 3),
                 w_inherit=f"opens_under_ssp370={opens}")
        )
        print(f"   {lab:18s} {sub.height:6d} cells {100 * sub.height / tot:5.1f} %  "
              f"median {med * 25:6.1f} stems/cell  gate opens under ssp370 in {opens}")

    # ── THE GATE ─────────────────────────────────────────────────────────────────────────────────────
    a0 = next(r for r in rows if r["section"] == "regime_minwin" and r["basis"] == "ind_treebearing"
              and r["key"] == "n_elig=0")
    dc = a0["cells"] - ADR0171["cells"]
    dsh = a0["share_pct"] - ADR0171["share_pct"]
    dst = a0["median_stems_per_cell"] - ADR0171["median_stems"]
    print(f"\n== GATE vs ADR 0171 §4 (its own `ind` basis): cells {a0['cells']} vs {ADR0171['cells']} "
          f"(Δ{dc:+d}) · share {a0['share_pct']} vs {ADR0171['share_pct']} % (Δ{dsh:+.2f}) · "
          f"median stems {a0['median_stems_per_cell']} vs {ADR0171['median_stems']} (Δ{dst:+.1f})")
    ok = abs(dc) <= 1 and abs(dsh) <= 0.15 and abs(dst) <= 1.0
    if ok:
        print("   GATE PASS — the published regime table is reproduced on its own basis.")
    elif NOGATE:
        print("   ⚠ GATE FAIL but NOGATE=1 — reporting the delta and continuing. State it with any number.")
    else:
        raise SystemExit(
            "FATAL: this reproducer does NOT reproduce ADR 0171 §4 on ADR 0171's own basis. Either the "
            "definition differs (find it before publishing a correction) or the ADR's number is wrong. "
            "Re-run with NOGATE=1 to see the whole table alongside the delta."
        )

    hdr = [
        "# ESTABLISHMENT-ELIGIBILITY REGIME TABLE — GENERATED, do not hand-edit.",
        f"#   regenerate: scripts/sbatch_python.sh S-regime scripts/build_estab_regime_table.py   (YEAR={YEAR})",
        "# The reproducer ADR 0171 §4 did not have. TWO classifications x TWO cell bases, side by side.",
        "# ⚠ THE CLASSIFICATION IS THE THING ADR 0171 §4 GETS READ WRONG. Its header says '(2010, Type<=6)'",
        "#   but its n_elig is the MIN over the 20 historic years (`regime_minwin`) — so its `n_elig = 0`",
        "#   class means 'the gate is closed in AT LEAST ONE of 20 years', not 'this cell is in the",
        "#   pure-inheritance regime'. `regime_snapshot` is the single-year reading; the `persistence`",
        "#   section below is what actually separates the two. Quote the classification with the share.",
        "# The two cell bases:",
        "#   basis `ind_treebearing` = cells with a Type<=6 stem in the snapshot year of FIT's own `ind`",
        "#                             output — ADR 0171 §4's basis, and the one its numbers are gated on;",
        "#   basis `t8_runnable`     = cells the PINNED pooled_w20_t8 artifact pair has a trained row for in",
        "#                             BOTH scenarios (cell_meta.parquet) — the only cells an arm can run at.",
        "# They disagree on how prevalent the untested n_elig=0 regime is, because that class is concentrated",
        "# in sparse cells the training table's row filters thin out. Quote the basis with the share.",
        "# `median_stems_per_cell` on basis t8_runnable is n_init x 25 patches (n_init is PER PATCH).",
        "# The `persistence` section is on basis t8_runnable: n_elig MOVES (ADR 0170 §3), so a snapshot",
        "# conflates 'this cell is in the pure-inheritance regime' with 'it dipped into it once'. A response",
        "# arm runs 81 years, so the regime it samples is the persistent one.",
        "# `w_inherit` = 4/(4+n_elig) (ADR 0045); in the persistence section the column instead reports how",
        "# many of those cells have their gate OPEN in at least one ssp370 year.",
    ]
    cols = ["section", "basis", "key", "cells", "share_pct", "median_stems_per_cell",
            "median_stems_per_patch", "w_inherit"]
    with open(OUT, "w") as fh:
        fh.write("\n".join(hdr) + "\n" + ",".join(cols) + "\n")
        for r in rows:
            fh.write(",".join(str(r[c]) for c in cols) + "\n")
    print(f"\n== wrote {os.path.relpath(OUT, REPO)}  ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
