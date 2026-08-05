#!/usr/bin/env python3
"""M3 S-side oracle — the C's per-cell DEMOGRAPHY + TRAIT-DISTRIBUTION reference for the 5 biome cells.

The F-side twin of this file is ``extract_biome_fdiff_oracle.py`` (ADR 0053, carbon/water/structure from the
daily NetCDF). This one builds the reference the *slow* component is scored against: how many living trees a
patch carries, and what the standing community's trait distribution looks like — straight out of the annual
``ind`` parquet, which is the very table Component S was trained on.

THE FOUR BASIS CHECKS (ADR 0053's pre-flight, applied to the S side — two of them flipped an F-side verdict).

1. TREE-ONLY. ``Type <= 6`` is FIT's complete seven tree PFTs (ADR 0031); ids 7/8/9 are grass, emitted with
   every tree field ZEROED (``fwriteoutput_ind.c:139-189``) — so a grass row does not merely add noise to a
   trait marginal, it adds a spike at exactly 0. ``TREE_TYPES`` is IMPORTED from the one canonical definition;
   never re-declare it. ``isdead == 0`` drops the stems the C killed this year.

2. PER-PATCH, NOT PER-CELL. The count target Component S learns is ``n_living`` per **(Cell, Patch, Year)**
   (``build_slow_runtime_table.py:464``), i.e. ONE patch — and the coupled driver runs ONE patch. The C emits
   **25 independent patches per cell-year**, so the like-for-like reference is the per-patch ensemble MEAN,
   and the ensemble SD is the within-cell structural spread the emulator is not asked to reproduce. Comparing
   a single coupled patch to a per-cell TOTAL would be off by ~25x; comparing it to the driver's own MODAL
   (densest) patch would flatter it by the same 1.12-1.72x the F side measured. Both numbers are emitted.

3. YEAR-MATCHED, NEVER A WINDOW MEAN. Per-year rows only. On the F side three of five cells' 10-yr-mean
   ratios were actively misleading because the canopy DRIFTS inside the window; a count that drifts from
   0.8x to 1.7x has a 10-yr mean near 1 and is not "right".

4. THE >5 m POPULATION. The ``ind`` writer emits only stems ``height > height_min = 5 m``
   (``fwriteoutput_ind.c:84``), so every number here — and every count Component S was trained on — is the
   >5 m population. That is self-consistent (target and reference are the same filter) but it means these
   counts are NOT the stand's total stem number, and a coupled roster that carries sub-5-m cohorts is on a
   different basis. Stated, not silently assumed.

NOISE FLOOR. LPJmL-FIT is stochastic (RAND48 + ``-DPERMUTE``), so seed1 and seed2 are two equally valid
realizations of the same cell and climate: their disagreement on a statistic is the IRREDUCIBLE error, and no
emulator conditioned on the environment rather than the RNG can beat it. Every statistic here is emitted for
both seeds so the consumer can form ``|seed1 - seed2|`` on exactly the statistic it is scoring.

WINDOW is 2010-2019 = the committed ``biome_forcing_<name>.csv`` the coupled probe replays, and the SCENARIO
is ``historic`` for the same reason (the ssp370 ``ind`` tables start in 2015 and the committed forcing is not
from them). So this reference cannot support a held-out-SCENARIO split; say so rather than implying one.

Collected NON-streaming on purpose: only 5 cells survive the filter, so CLAUDE.md 4's
``collect(engine="streaming")`` key-set nondeterminism does not apply — and the key set is asserted anyway,
because a duplicated key makes the usual ``drop_frac`` guard go NEGATIVE and never fire.

Run:  scripts/sbatch_python.sh M-slworacle scripts/extract_biome_slow_oracle.py
"""
import json
import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python", "src"))
from lpjmlfit_emulator.data import TREE_TYPES  # noqa: E402  the ONE canonical definition (ADR 0031)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # never hard-code (CLAUDE.md 9.6)
REFDIR = os.path.join(REPO, "test", "testitems", "references")
IND = "/p/tmp/jamirp/emulator_global/ind_hist_seed{seed}_all.parquet"
CELLS = {  # cold -> hot, the M_cells.csv order
    "boreal_siberia": 52059,
    "temperate_hainich": 42490,
    "mediterranean_iberia": 33335,
    "semiarid_sahel": 18371,
    "tropical_amazon": 12045,
}
Y0, Y1 = 2010, 2019
SEEDS = (1, 2)
QS = (0.05, 0.25, 0.50, 0.75, 0.95)
# The 4 PRODUCTION copula axes (the `.rcop` declares exactly these), then 2 DIAGNOSTIC structural axes.
# Only SLA and Wooddens reach `TreePools` (`make_recruit_to_pools`); D95max/minwscal are drawn and validated
# but have no per-tree consumer yet, so a coupled community can only be scored on the first two. Emitted
# anyway: they are what a future per-tree consumer would be scored against, and they cost nothing here.
TRAIT_AXES = ("SLA", "Wooddens", "D95max", "minwscal")
DIAG_AXES = ("Height", "agb")
ALL_AXES = TRAIT_AXES + DIAG_AXES


def scan_seed(seed):
    """Per-(Cell,Patch,Year) living >5 m TREE stems for the 5 biome cells, 2010-2019 — one collect."""
    filt = (
        pl.col("Type").is_in(list(TREE_TYPES))
        & (pl.col("isdead") == 0)
        & pl.col("Cell").is_in(list(CELLS.values()))
        & (pl.col("Year") >= Y0)
        & (pl.col("Year") <= Y1)
    )
    cols = ["Cell", "Patch", "Year", *ALL_AXES]
    df = pl.scan_parquet(IND.format(seed=seed)).filter(filt).select(cols).collect()
    if df.height == 0:
        raise SystemExit(f"seed{seed}: no rows survived the filter — check the cell ids / window")
    return df


def counts_of(df):
    """basis check 2 — per-patch `n_living`, then the per-cell-year ENSEMBLE over patches."""
    per_patch = df.group_by(["Cell", "Patch", "Year"]).agg(pl.len().alias("n_living"))
    keys = per_patch.select(["Cell", "Patch", "Year"])
    assert keys.n_unique() == per_patch.height, "DUPLICATED (Cell,Patch,Year) key"  # CLAUDE.md 4
    return per_patch.group_by(["Cell", "Year"]).agg(
        pl.len().alias("npatch"),
        pl.col("n_living").mean().alias("n_mean"),
        pl.col("n_living").std().alias("n_sd"),
        pl.col("n_living").min().alias("n_min"),
        pl.col("n_living").max().alias("n_max"),
        pl.col("n_living").sum().alias("n_cell_total"),
    )


def traits_of(df):
    """Per-(Cell,Year) marginals of each axis, POOLED over the 25 patches (the cell's community)."""
    aggs = [pl.len().alias("n_stems")]
    for ax in ALL_AXES:
        for q in QS:
            aggs.append(pl.col(ax).quantile(q, "nearest").alias(f"{ax}__q{round(q * 100):02d}"))
        aggs.append(pl.col(ax).mean().alias(f"{ax}__mean"))
        aggs.append(pl.col(ax).std().alias(f"{ax}__sd"))
    out = df.group_by(["Cell", "Year"]).agg(aggs)
    assert out.select(["Cell", "Year"]).n_unique() == out.height, "DUPLICATED (Cell,Year) key"
    return out


def main():
    name_of = {v: k for k, v in CELLS.items()}
    cnt, trt, meta_rows = {}, {}, {}
    for seed in SEEDS:
        df = scan_seed(seed)
        cnt[seed] = counts_of(df).sort(["Cell", "Year"])
        trt[seed] = traits_of(df).sort(["Cell", "Year"])
        meta_rows[seed] = {
            "path": IND.format(seed=seed),
            "bytes": os.path.getsize(IND.format(seed=seed)),
            "stems_selected": df.height,
            "cells": sorted(df["Cell"].unique().to_list()),
            "years": [int(df["Year"].min()), int(df["Year"].max())],
        }
        print(
            f"== seed{seed}: {df.height} living tree stems, {cnt[seed].height} cell-years, "
            f"{trt[seed]['n_stems'].sum()} pooled for traits"
        )
        missing = set(CELLS.values()) - set(df["Cell"].unique().to_list())
        if missing:
            raise SystemExit(f"seed{seed}: cells absent from the ind table: {sorted(missing)}")

    # ── counts CSV — per cell-year, per seed, with the ensemble spread AND the modal patch ───────────────
    crows = []
    for seed in SEEDS:
        for r in cnt[seed].iter_rows(named=True):
            crows.append(
                {
                    "name": name_of[r["Cell"]], "cell": r["Cell"], "year": r["Year"], "seed": seed,
                    "npatch": r["npatch"], "n_mean": r["n_mean"], "n_sd": r["n_sd"],
                    "n_min": r["n_min"], "n_max": r["n_max"], "n_cell_total": r["n_cell_total"],
                }
            )
    ccols = ["name", "cell", "year", "seed", "npatch", "n_mean", "n_sd", "n_min", "n_max", "n_cell_total"]
    cout = os.path.join(REFDIR, "M_slow_oracle_counts.csv")
    with open(cout, "w") as f:
        f.write(
            f"# The C oracle's per-PATCH living-tree COUNT for the 5 coupled biome cells, {Y0}-{Y1},\n"
            f"# historic, both seeds. Population = Type<=6 (ADR 0031), isdead==0, and the ind writer's own\n"
            f"# height>5 m filter (fwriteoutput_ind.c:84) — the SAME population Component S's `n_living`\n"
            f"# target is defined on. n_mean/n_sd/n_min/n_max are over the cell's `npatch` INDEPENDENT\n"
            f"# patches; n_mean is the like-for-like reference for a single coupled patch, n_cell_total is\n"
            f"# NOT (it is ~25x larger). seed1-vs-seed2 on the same statistic IS the noise floor.\n"
            f"# Emitted by scripts/extract_biome_slow_oracle.py — see that docstring for the full basis.\n"
        )
        f.write(",".join(ccols) + "\n")
        for r in crows:
            f.write(
                ",".join(
                    str(r[c]) if c in ("name", "cell", "year", "seed", "npatch", "n_min", "n_max", "n_cell_total")
                    else f"{r[c]:.6f}"
                    for c in ccols
                )
                + "\n"
            )
    print(f"wrote {cout}  ({len(crows)} rows)")

    # ── traits CSV — long format, one row per (cell, year, seed, axis) ───────────────────────────────────
    tcols = ["name", "cell", "year", "seed", "axis", "n_stems", *[f"q{round(q * 100):02d}" for q in QS],
             "mean", "sd"]
    trows = []
    for seed in SEEDS:
        for r in trt[seed].iter_rows(named=True):
            for ax in ALL_AXES:
                trows.append(
                    {
                        "name": name_of[r["Cell"]], "cell": r["Cell"], "year": r["Year"], "seed": seed,
                        "axis": ax, "n_stems": r["n_stems"],
                        **{f"q{round(q * 100):02d}": r[f"{ax}__q{round(q * 100):02d}"] for q in QS},
                        "mean": r[f"{ax}__mean"], "sd": r[f"{ax}__sd"],
                    }
                )
    tout = os.path.join(REFDIR, "M_slow_oracle_traits.csv")
    with open(tout, "w") as f:
        f.write(
            f"# The C oracle's standing-community TRAIT marginals for the 5 coupled biome cells, {Y0}-{Y1},\n"
            f"# historic, both seeds. Same population as M_slow_oracle_counts.csv, POOLED over the cell's\n"
            f"# patches (a per-patch marginal is too thin: ~4-11 stems). SLA/Wooddens/D95max/minwscal are\n"
            f"# the 4 production copula axes; Height/agb are DIAGNOSTIC structural axes (not in the .rcop).\n"
            f"# Only SLA and Wooddens reach TreePools (make_recruit_to_pools), so only those two can be\n"
            f"# scored against a COUPLED community today. seed1-vs-seed2 on the same statistic = the floor.\n"
            f"# Emitted by scripts/extract_biome_slow_oracle.py — see that docstring for the full basis.\n"
        )
        f.write(",".join(tcols) + "\n")
        for r in trows:
            f.write(
                ",".join(
                    str(r[c]) if c in ("name", "cell", "year", "seed", "axis", "n_stems") else f"{r[c]:.6f}"
                    for c in tcols
                )
                + "\n"
            )
    print(f"wrote {tout}  ({len(trows)} rows)")

    # ── the NOISE FLOOR, printed so the consumer sees the scale before it scores anything ────────────────
    print(f"\n=== seed1-vs-seed2 NOISE FLOOR, per-year statistics, {Y0}-{Y1} ===")
    print(f"{'cell':<22} {'n_mean(s1)':>11} {'n_mean(s2)':>11} {'floor_n':>8} {'floor_n%':>9} {'ens_sd':>8}")
    floors = {}
    for name, cell in CELLS.items():
        a = cnt[1].filter(pl.col("Cell") == cell).sort("Year")
        b = cnt[2].filter(pl.col("Cell") == cell).sort("Year")
        j = a.join(b, on="Year", how="inner", suffix="_2")
        fl = float((j["n_mean"] - j["n_mean_2"]).abs().mean())
        m1 = float(a["n_mean"].mean())
        floors[name] = {"count_abs": fl, "count_pct": 100 * fl / m1, "ens_sd": float(a["n_sd"].mean())}
        print(
            f"{name:<22} {m1:11.3f} {float(b['n_mean'].mean()):11.3f} {fl:8.3f} "
            f"{100 * fl / m1:8.2f}% {float(a['n_sd'].mean()):8.3f}"
        )
    print("floor_n = mean_over_years |seed1 - seed2| of the per-patch ensemble mean; ens_sd = within-cell")
    print("          between-patch sd (the spread ONE coupled patch samples, not an error the emulator owns)")

    print(f"\n=== trait-median noise floor (q50), {Y0}-{Y1} ===")
    hdr = f"{'cell':<22} " + " ".join(f"{ax:>10}" for ax in ALL_AXES)
    print(hdr)
    for name, cell in CELLS.items():
        cellsfl = {}
        parts = []
        for ax in ALL_AXES:
            a = trt[1].filter(pl.col("Cell") == cell).sort("Year")[f"{ax}__q50"].to_numpy()
            b = trt[2].filter(pl.col("Cell") == cell).sort("Year")[f"{ax}__q50"].to_numpy()
            iqr = float(
                np.mean(
                    trt[1].filter(pl.col("Cell") == cell)[f"{ax}__q75"].to_numpy()
                    - trt[1].filter(pl.col("Cell") == cell)[f"{ax}__q25"].to_numpy()
                )
            )
            fl = float(np.mean(np.abs(a - b)))
            cellsfl[ax] = {"median_abs": fl, "iqr": iqr, "median_in_iqr": (fl / iqr) if iqr > 0 else float("nan")}
            parts.append(f"{fl:10.4f}")
        floors[name]["traits"] = cellsfl
        print(f"{name:<22} " + " ".join(parts))
    print("(absolute |seed1-seed2| of the per-year pooled community MEDIAN; each axis's IQR is in the meta)")

    meta = {
        "purpose": "M3 S-side — the C's per-cell demography + trait-distribution reference (line M)",
        "scenario": "historic",
        "window": [Y0, Y1],
        "seeds": list(SEEDS),
        "tree_types": list(TREE_TYPES),
        "filters": "Type in TREE_TYPES (ADR 0031) AND isdead==0; the ind writer adds height>5 m",
        "count_basis": "n_living per (Cell,Patch,Year); the cell-year reference is the mean over patches",
        "trait_basis": "per-stem marginals pooled over the cell's patches, per year",
        "production_axes": list(TRAIT_AXES),
        "diagnostic_axes": list(DIAG_AXES),
        "coupled_consumable_axes": ["SLA", "Wooddens"],
        "held_out": "these 5 cells ARE in the pinned _t8 training population — in-sample; no scenario split",
        "sources": meta_rows,
        "noise_floor": floors,
    }
    mout = os.path.join(REFDIR, "M_slow_oracle_meta.json")
    with open(mout, "w") as f:
        json.dump(meta, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"\nwrote {mout}")


if __name__ == "__main__":
    main()
