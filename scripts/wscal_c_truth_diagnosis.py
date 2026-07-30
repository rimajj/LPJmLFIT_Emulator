#!/usr/bin/env python3
"""ADR 0051 — the C's OWN ``water_stress`` for the 5 coupled biome cells (the reference basis).

The coupled-loop residual (ADR 0034 §1) was reported against the *Hainich demo artifact's* trained band
alone. This derives the reference directly, per cell and per year, exactly as the Component-S training
table does (``build_slow_runtime_table.py:424,436``)::

    water_stress = 1 - mean_over_living_tree_stems(ind.wscal_mean)     per (Cell, Patch, Year)

where the C emits ``wscal_mean = pft->wscal_mean / NDAYYEAR`` (``fwriteoutput_ind.c:119``) accumulated
every day from ``water_stressed.c:140``. So this table IS what the runtime column has to reproduce, for
all five biomes and not just the one cell that had a committed artifact.

Only 5 cells survive the filter, so the aggregate is collected NON-streaming on purpose — CLAUDE.md §4's
``collect(engine="streaming")`` key-set nondeterminism does not apply, and the key set is asserted anyway.

Run:  scripts/sbatch_python.sh M-wsctruth scripts/wscal_c_truth_diagnosis.py
"""
import os
import sys

import polars as pl

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python", "src"))
from lpjmlfit_emulator.data import TREE_TYPES  # noqa: E402  the ONE canonical definition (ADR 0031)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # never hard-code (CLAUDE.md §9.6)
IND = "/p/tmp/jamirp/emulator_global/ind_hist_seed{seed}_all.parquet"
CELLS = {52059: "boreal_siberia", 42490: "temperate_hainich", 33335: "mediterranean_iberia",
         18371: "semiarid_sahel", 12045: "tropical_amazon"}
YEARS = range(2010, 2020)   # the committed biome forcing window the coupled probe runs on

# What the coupled loop produced, straight from logs/M-wscal.1644166.out (PART 2, mean over the 10 years).
RUNTIME = {  # cell -> (default, wscal_leafon=True)
    "boreal_siberia": (0.6640, 0.0000), "temperate_hainich": (0.3050, 0.0034),
    "mediterranean_iberia": (0.2579, 0.1748), "semiarid_sahel": (0.9830, 0.4379),
    "tropical_amazon": (0.0054, 0.0000),
}


def c_truth(seed):
    filt = (pl.col("Type").is_in(list(TREE_TYPES)) & (pl.col("isdead") == 0)
            & pl.col("Cell").is_in(list(CELLS)) & pl.col("Year").is_in(list(YEARS)))
    df = (pl.scan_parquet(IND.format(seed=seed)).filter(filt)
          .group_by(["Cell", "Patch", "Year"])
          .agg(pl.col("wscal_mean").mean().alias("_ws"), pl.len().alias("n"))
          .collect())
    # CLAUDE.md §4: assert our OWN key set — a duplicated key makes the usual drop-count guard go negative.
    keys = df.select(["Cell", "Patch", "Year"])
    assert keys.n_unique() == df.height, f"seed{seed}: DUPLICATED (Cell,Patch,Year) key"
    return df.with_columns((1.0 - pl.col("_ws")).alias("water_stress"))


def main():
    t1 = c_truth(1)
    t2 = c_truth(2)
    print(f"== C truth rows: seed1 {t1.height}, seed2 {t2.height} "
          f"(cells {t1['Cell'].n_unique()}/{len(CELLS)}, years {t1['Year'].n_unique()})")

    print("\n=== the C's OWN `water_stress` (1 - mean ind.wscal_mean), 2010-2019, vs the coupled runtime ===")
    print(f"{'cell':<22} {'C_mean':>8} {'C_min':>8} {'C_max':>8} {'floor':>7} "
          f"{'F_dflt':>8} {'F_leafon':>9} {'|d|dflt':>8} {'|d|lo':>7} {'x_floor':>8}")
    for cell, name in CELLS.items():
        a = t1.filter(pl.col("Cell") == cell)
        b = t2.filter(pl.col("Cell") == cell)
        if a.height == 0:
            print(f"{name:<22} {'-- absent from the ind table --':>60}")
            continue
        # per-year cell mean over patches, then the stats over years
        ya = a.group_by("Year").agg(pl.col("water_stress").mean()).sort("Year")
        yb = b.group_by("Year").agg(pl.col("water_stress").mean()).sort("Year")
        cm = ya["water_stress"].mean()
        # seed1-vs-seed2 NOISE FLOOR on the same statistic — the honest scale for any error (STATE.md M3.2)
        j = ya.join(yb, on="Year", how="inner", suffix="_2")
        floor = (j["water_stress"] - j["water_stress_2"]).abs().mean() if j.height else float("nan")
        fd, fl = RUNTIME[name]
        dd, dl = abs(fd - cm), abs(fl - cm)
        print(f"{name:<22} {cm:8.4f} {ya['water_stress'].min():8.4f} {ya['water_stress'].max():8.4f} "
              f"{floor:7.4f} {fd:8.4f} {fl:9.4f} {dd:8.4f} {dl:7.4f} "
              f"{(dl / floor if floor and floor == floor and floor > 0 else float('nan')):8.1f}")

    print("\nfloor    = mean |seed1 - seed2| of the same per-year cell statistic (the C's own RNG spread)")
    print("|d|dflt  = |F_diff default - C|      |d|lo = |F_diff wscal_leafon - C|")
    print("x_floor  = |d|lo in units of the noise floor (how much of the gap survives the fix)")


if __name__ == "__main__":
    main()
