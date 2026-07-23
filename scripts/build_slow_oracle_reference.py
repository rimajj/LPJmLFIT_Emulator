#!/usr/bin/env python3
"""Extract the Hainich (global-grid cell 42490) ground-truth S-owned marginal distribution.

This is the Gate-3 ORACLE reference (docs/p1_s_in_loop_design.md §6, risk #3): the LPJmL-FIT C
ground-truth trait/size DISTRIBUTION + living count the coupled flux-driven Component S is compared
against at Hainich. The axes S owns are the count N (living tree stems / patch), the size axes
{Height, Age}, and the trait axes {SLA, Wooddens, beta_root}. In individual=true each ``ind`` row is
one living stem, so N = row count (no nind column exists — CLAUDE.md §3).

Writes two compact, committed text references (all fixtures are text, never *.bin):
  test/testitems/references/hainich_slow_oracle_counts.csv   count trajectory 2000-2019
  test/testitems/references/hainich_slow_oracle_traits.csv   pooled living-beech trait/size quantiles

Reads the frozen annual ``ind`` parquet with a single-cell predicate-pushdown scan (no C re-run, no
186 GB daily read). Deterministic. Run inside the py311_new conda env.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import polars as pl

CELL = 42490
TREE_TYPES = [1, 2, 3, 4, 5]
BEECH = 3
IND_PARQUET = "/p/tmp/jamirp/emulator_global/ind_hist_seed{seed}_all.parquet"
REFDIR = Path(__file__).resolve().parents[1] / "test" / "testitems" / "references"
QUANTILES = [0.05, 0.25, 0.50, 0.75, 0.95]


def main() -> int:
    seed = int(os.environ.get("SEED", "1"))
    lf = pl.scan_parquet(IND_PARQUET.format(seed=seed))
    living = (
        lf.filter((pl.col("Cell") == CELL) & pl.col("Type").is_in(TREE_TYPES) & (pl.col("isdead") == 0))
        .select(["Year", "Patch", "Type", "Height", "Age", "SLA", "Wooddens", "beta_root", "agb", "LAI"])
        .collect()
    )
    print(f"== cell {CELL}: {living.height} living-tree rows, "
          f"years {living['Year'].min()}-{living['Year'].max()}, "
          f"patches {living['Patch'].min()}-{living['Patch'].max()}")

    # ---- count trajectory per year (all trees + beech) --------------------------------
    beech = living.filter(pl.col("Type") == BEECH)
    rows = []
    for y in sorted(living["Year"].unique().to_list()):
        ly = living.filter(pl.col("Year") == y)
        by = beech.filter(pl.col("Year") == y)
        # per-patch beech count that year
        per_patch = (by.group_by("Patch").agg(pl.len().alias("n")))["n"].to_numpy()
        npatch = int(ly["Patch"].n_unique())
        rows.append({
            "Year": int(y),
            "n_living_alltree": int(ly.height),
            "n_living_beech": int(by.height),
            "npatch": npatch,
            "N_beech_per_patch_mean": float(per_patch.mean()) if per_patch.size else 0.0,
            "N_beech_per_patch_p50": float(np.median(per_patch)) if per_patch.size else 0.0,
            "N_beech_per_patch_max": float(per_patch.max()) if per_patch.size else 0.0,
        })
    counts = pl.DataFrame(rows)
    counts_path = REFDIR / "hainich_slow_oracle_counts.csv"
    with open(counts_path, "w") as f:
        f.write("# Hainich (global-grid cell 42490) LPJmL-FIT ground-truth living-tree COUNT trajectory,\n")
        f.write(f"# seed{seed}, historical 2000-2019. N = living ind rows (individual=true; each row = 1 stem).\n")
        f.write("# Gate-3 oracle reference for the coupled flux-driven Component S (docs/p1_s_in_loop_design.md 6).\n")
        f.write(counts.write_csv())
    print(f"== wrote {counts_path} ({counts.height} years)")

    # ---- pooled living-beech trait/size marginals (all years) -------------------------
    axes = ["Height", "Age", "SLA", "Wooddens", "beta_root"]
    trows = []
    for ax in axes:
        col = beech[ax].to_numpy().astype("float64")
        col = col[np.isfinite(col)]
        rec = {"axis": ax, "n": int(col.size), "mean": float(col.mean()), "std": float(col.std())}
        for q in QUANTILES:
            rec[f"q{int(q * 100):02d}"] = float(np.quantile(col, q))
        trows.append(rec)
    traits = pl.DataFrame(trows)
    traits_path = REFDIR / "hainich_slow_oracle_traits.csv"
    with open(traits_path, "w") as f:
        f.write("# Hainich (cell 42490) LPJmL-FIT ground-truth living-BEECH (Type=3) S-owned marginal\n")
        f.write(f"# distribution, seed{seed}, pooled over historical 2000-2019. Axes S owns: size {{Height,Age}},\n")
        f.write("# traits {SLA,Wooddens,beta_root}. Quantiles q05..q95. Gate-3 oracle reference.\n")
        f.write(traits.write_csv())
    print(f"== wrote {traits_path}")
    print(traits)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
