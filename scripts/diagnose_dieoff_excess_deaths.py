#!/usr/bin/env python3
"""diagnose_dieoff_excess_deaths.py -- are the original's drought die-offs MORTALITY or FIRE? (post-hoc, ADR 0356)

In this configuration fire is on ("fire": GlobFIRM) and, after the demographic mortality, firepft -> fire_tree_ind
kills each living tree with probability (1 - resist) * fire_frac (src/tree/fire_tree_ind.c:25), fire_frac from the
year's topsoil-dryness sum (src/soil/fire_prob.c, fire_sum.c). The `ind` table carries each tree's demographic death
probability `mort` (= min(1, mort_npp + mort_age + mort_water + mort_temp), or 1 for the hard kills) and `isdead`.
So per (Cell, Year): deaths D = sum(isdead) and demographically expected deaths E = sum(min(mort, 1)) over the tree
rows (Type <= 6). Excess (D - E) / n is what the mortality routine does not explain (fire, or the hard kills if `mort`
does not carry them). Compared between ADR 0350's shared tree-count events of the unseen run (m4) and the same cells'
other years, on the 15 held-out cases. ~5 min on SLURM (reads 15 x ~60 M rows).
"""

import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_panel_prep as PP  # noqa: E402

PANEL = "/p/projects/open/Jamir/esm_land_emulator_data/trackD/panel"


def main():
    ev = (
        pl.read_parquet(os.path.join(PP.OUT, "eval", "extreme_legacy_events.parquet"))
        .filter((pl.col("q") == "tree_count") & pl.col("shared"))
        .select(
            pl.col("case").alias("leg"),
            pl.col("Cell").cast(pl.Int32),
            pl.col("year").cast(pl.Int16).alias("Year"),
            "d_T",
        )
    )
    out = []
    for leg in sorted(ev["leg"].unique().to_list()):
        f = os.path.join(PANEL, "m4", leg, "ind.parquet")
        cells = ev.filter(pl.col("leg") == leg)["Cell"].unique()
        g = (
            pl.scan_parquet(f)
            .filter((pl.col("Type") <= 6) & pl.col("Cell").is_in(cells.implode()))
            .group_by("Cell", "Year")
            .agg(
                pl.len().alias("n"),
                pl.col("isdead").cast(pl.Float64).sum().alias("D"),
                pl.col("mort").clip(0.0, 1.0).sum().alias("E"),
                (pl.col("mort") >= 1.0).sum().alias("certain"),
                # why certain: one hazard alone >= 1, the hazards' sum >= 1, or neither
                # (= a hard kill: 5 bad years in a row, or leaf carbon below a sapling's)
                ((pl.col("mort") >= 1.0) & (pl.col("mort_water") >= 1.0)).sum().alias("c_water"),
                ((pl.col("mort") >= 1.0) & (pl.col("mort_npp") >= 1.0)).sum().alias("c_npp"),
                (
                    (pl.col("mort") >= 1.0)
                    & ((pl.col("mort_npp") + pl.col("mort_age") + pl.col("mort_water") + pl.col("mort_temp")) >= 1.0)
                )
                .sum()
                .alias("c_sum"),
                (
                    (pl.col("mort") >= 1.0)
                    & ((pl.col("mort_npp") + pl.col("mort_age") + pl.col("mort_water") + pl.col("mort_temp")) < 1.0)
                )
                .sum()
                .alias("c_hard"),
            )
            .collect()
        )
        out.append(g.with_columns(pl.lit(leg).alias("leg")))
        print(f"{leg}: {g.height} cell-years", flush=True)
    d = pl.concat(out).join(ev.with_columns(pl.lit(True).alias("event")), on=["leg", "Cell", "Year"], how="left")
    d = d.with_columns(
        pl.col("event").fill_null(False),
        ((pl.col("D") - pl.col("E")) / pl.col("n")).alias("excess"),
        (pl.col("D") / pl.col("n")).alias("dead_share"),
        (pl.col("E") / pl.col("n")).alias("exp_share"),
    )
    d = d.filter(pl.col("Year").is_between(2025, 2090) & (pl.col("n") >= 25))
    pl.Config.set_tbl_cols(12)
    print("\n== per cell-year, median (and 90th centile) -- event years vs the same cells' other years")
    print(
        d.group_by("event")
        .agg(
            pl.len().alias("cell_years"),
            pl.col("dead_share").median().round(4).alias("dead_p50"),
            pl.col("exp_share").median().round(4).alias("expected_p50"),
            pl.col("excess").median().round(4).alias("excess_p50"),
            pl.col("excess").quantile(0.9).round(4).alias("excess_p90"),
            (pl.col("certain") / pl.col("n")).median().round(4).alias("certain_share_p50"),
        )
        .sort("event")
    )
    print("\n== certain kills (mort >= 1) by cause, share of the cell-year's trees, summed over cell-years")
    print(
        d.group_by("event")
        .agg(
            [
                (pl.col(c).sum() / pl.col("n").sum()).round(4).alias(c)
                for c in ("certain", "c_water", "c_npp", "c_sum", "c_hard")
            ]
        )
        .sort("event")
    )
    e = d.filter(pl.col("event"))
    sh = (e["D"] - e["E"]).sum() / e["D"].sum()
    print(f"\nevent years: share of all deaths NOT expected from the trees' own death probability: {sh:.3f}")
    o = d.filter(~pl.col("event"))
    print(f"other years: the same share: {(o['D'] - o['E']).sum() / o['D'].sum():.3f}")
    r = np.corrcoef(e["excess"].to_numpy(), e["d_T"].to_numpy())[0, 1]
    print(f"event years: corr(excess death share, the event's drop d_T) = {r:.3f}")


if __name__ == "__main__":
    main()
