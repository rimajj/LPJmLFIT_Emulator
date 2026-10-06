"""explore_de_struct_entry.py — LINE X, Germany emulator, STRUCT track: what do STRUCT's recruits
look like when they first appear, beside the original's? (SD.md, H10/H12 context; read-only)

First appearances (key not printed in any earlier year of the run; years 1986-2044) of a run's
rosters and of the original's `ind` table, same cells: type shares and, per type group, medians of
Height, Age, agb, the entry-size ratios (vegc/agb, LAI, fpc_ind/agb, D95), SLA, Wooddens, and the
share with counter c >= 1 (runs only; the original's `ind` has no counter).
Usage:  python explore_de_struct_entry.py --arms label@<run dir>[,...] [--ncells 200]
Writes /p/tmp/jamirp/X_de/shared/eval/struct_entry.csv
"""

from __future__ import annotations

import argparse
import os
import sys

import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_struct_stemloss as sl  # noqa: E402

K = ["Cell", "Patch", "Type", "ID", "SLA", "Wooddens"]
COLS = sl.COLS + ["vegc", "LAI", "fpc_ind", "D95", "Age"]


def first(D: pl.DataFrame, src: str) -> pl.DataFrame:
    F = (
        D.sort(K + ["Year"])
        .group_by(K, maintain_order=True)
        .agg(pl.all().first())
        .filter(pl.col("Year") > 1985)
    )
    F = F.with_columns(
        tg=pl.when(pl.col("Type") == 3)
        .then(pl.lit("beech"))
        .when(pl.col("Type").is_in([1, 2, 5]))
        .then(pl.lit("t125"))
        .otherwise(pl.lit("t046"))
    )
    n = F.height
    agg = [
        pl.len().alias("n"),
        *[
            pl.col(c).median().alias(f"{c}_med")
            for c in ("Height", "Age", "agb", "LAI", "D95", "SLA", "Wooddens")
        ],
        (pl.col("vegc") / pl.col("agb")).median().alias("vegc_agb_med"),
        (pl.col("fpc_ind") / pl.col("agb")).median().alias("fpc_agb_med"),
    ]
    if "c" in F.columns:
        agg.append((pl.col("c") >= 1).mean().alias("c_ge1"))
    return F.group_by("tg").agg(agg).with_columns(share=pl.col("n") / n, src=pl.lit(src)).sort("tg")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", required=True)
    ap.add_argument("--ncells", type=int, default=200)
    a = ap.parse_args()
    sl.COLS = COLS + ["c"]
    cells = sorted(sl.st.hd.folds()["Cell"].to_list())[: a.ncells]
    out = []
    for arm in a.arms.split(","):
        D, _ = sl.arm_frame(arm, "ssp370", cells, a.ncells)
        out.append(first(D, arm.split("@")[0]))
    sl.COLS = COLS
    out.append(first(sl.truth_frame(cells, "ssp370"), "truth"))
    res = pl.concat(out, how="diagonal_relaxed").sort("tg", "src")
    p = os.path.join(sl.XDE, "shared", "eval", "struct_entry.csv")
    res.write_csv(p)
    pl.Config.set_tbl_cols(20)
    pl.Config.set_tbl_width_chars(250)
    print(res.with_columns(pl.selectors.float().round(4)))
    print("wrote", p)


if __name__ == "__main__":
    main()
