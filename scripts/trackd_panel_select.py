"""trackd_panel_select.py — Track D0 (EXECUTION_PLAN.md rev. 2, ADR 0096): choose the fixed GLOBAL STRATIFIED
PANEL every global Track-D run and every global arm score uses.

Unit = a BLOCK of 10 consecutive orderA cells. orderA runs south -> north in latitude bands and west -> east inside
a band, so a valid block (same latitude, 0.5 deg longitude steps, no gap) is one compact 5 deg east-west strip, and
LPJmL can run it as one contiguous `startgrid`..`endgrid` range from the global restart files (CLAUDE.md §3).

Eligibility: >= 8 of the 10 cells carry trees (> 0 tree stems > 5 m in 2019, historic seed 1).
Strata: block-mean annual temperature (quintiles) x block-mean precipitation (quartiles) over eligible blocks
= 20 climate strata. Within a stratum, blocks are drawn so that no two share a 15 deg tile when avoidable (the
effective spatial sample is ~161 populated 15 deg tiles, ADR 0310). Target 5 blocks per stratum; shortfalls are
filled from the strata with the most spare tiles. The blocks containing the five biome cells the repo has analysed
since ADR 0050 (52059, 42490, 33335, 18371, 12045) are always included when a valid block contains them.

Fixed seed => reproducible. Writes test/testitems/references/S_D0_panel_blocks.csv (one row per block).
Usage:  python scripts/trackd_panel_select.py [--per-stratum 5] [--seed 20261008]
"""

from __future__ import annotations

import argparse
import os

import numpy as np
import polars as pl

GLOBAL = "/p/projects/waldspektrum/priesner/clustering/global"
FEATS = "/p/tmp/jamirp/emulator_global/tables/cell_year_feats.parquet"
IND = "/p/tmp/jamirp/emulator_global/ind_hist_seed1_all.parquet"
BIOME_CELLS = {
    52059: "boreal_siberia",
    42490: "temperate_hainich",
    33335: "mediterranean_iberia",
    18371: "semiarid_sahel",
    12045: "tropical_amazon",
}
NCELL = 67420
B = 10
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def grid():
    raw = open(os.path.join(GLOBAL, "soil_code_test.grid.clm"), "rb").read()
    a = np.frombuffer(raw[51 : 51 + NCELL * 8], dtype="<f4").reshape(NCELL, 2)
    return a[:, 0].astype(float), a[:, 1].astype(float)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-stratum", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20261008)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    lon, lat = grid()
    clim = (
        pl.scan_parquet(FEATS)
        .select("Cell", "Year", "temp_mean", "prec_mean")
        .filter(pl.col("Year").is_between(2000, 2019))
        .group_by("Cell")
        .agg(
            pl.col("temp_mean").cast(pl.Float64).mean().alias("mat"),
            pl.col("prec_mean").cast(pl.Float64).mean().alias("map"),
        )
        .collect()
        .sort("Cell")
    )
    assert clim.select(pl.col("Cell").n_unique()).item() == clim.height
    mat = np.full(NCELL, np.nan)
    mapp = np.full(NCELL, np.nan)
    mat[clim["Cell"].to_numpy()] = clim["mat"].to_numpy()
    mapp[clim["Cell"].to_numpy()] = clim["map"].to_numpy()
    stems = (
        pl.scan_parquet(IND)
        .filter((pl.col("Year") == 2019) & (pl.col("Type") <= 6))
        .group_by("Cell")
        .agg(pl.len().alias("n"))
        .collect()
    )
    assert stems.select(pl.col("Cell").n_unique()).item() == stems.height
    tree = np.zeros(NCELL)
    tree[stems["Cell"].to_numpy()] = stems["n"].to_numpy() / 25.0  # stems > 5 m per patch
    print(f"tree-bearing cells (2019, seed 1): {(tree > 0).sum()}")

    # candidate blocks: same latitude, consecutive 0.5 deg steps, >= 8 tree-bearing, climate known
    cand = []
    for s in range(NCELL - B + 1):
        e = s + B
        if not np.all(lat[s:e] == lat[s]) or not np.allclose(np.diff(lon[s:e]), 0.5):
            continue
        if (tree[s:e] > 0).sum() < 8 or np.isnan(mat[s:e]).any():
            continue
        cand.append(s)
    cand = np.array(cand)
    print(f"candidate block starts: {len(cand)}")
    bm = np.array([mat[s : s + B].mean() for s in cand])
    bp = np.array([mapp[s : s + B].mean() for s in cand])
    tq = np.quantile(bm, [0.2, 0.4, 0.6, 0.8])
    pq = np.quantile(bp, [0.25, 0.5, 0.75])
    st = np.digitize(bm, tq) * 4 + np.digitize(bp, pq)
    clon = np.array([lon[s : s + B].mean() for s in cand])
    tile = (np.floor((lat[cand] + 90) / 15) * 24 + np.floor((clon + 180) / 15)).astype(int)

    chosen, used = [], np.zeros(NCELL, bool)

    def take(i, why):
        s = int(cand[i])
        if used[s : s + B].any():
            return False
        used[s : s + B] = True
        chosen.append((i, why))
        return True

    # forced: the biome-cell blocks (the candidate whose block is centred closest on the cell)
    for c, name in BIOME_CELLS.items():
        hits = [i for i, s in enumerate(cand) if s <= c < s + B]
        if hits:
            take(min(hits, key=lambda i: abs(cand[i] + B / 2 - c)), f"biome:{name}")
        else:
            print(f"  note: no valid block contains biome cell {c} ({name})")
    # stratified draw: distinct tiles within a stratum, and tiles no chosen block uses yet are preferred, so the
    # panel spreads over as many independent 15 deg tiles as the strata allow. Strata are visited round-robin
    # (one block per stratum per pass) so early strata cannot exhaust the unused tiles.
    order = rng.permutation(len(cand))
    by_k = {k: [i for i in order if st[i] == k] for k in range(20)}
    have = {k: sum(1 for i, _ in chosen if st[i] == k) for k in range(20)}
    tiles = {k: {tile[i] for i, _ in chosen if st[i] == k} for k in range(20)}
    for _ in range(a.per_stratum):
        for k in range(20):
            if have[k] >= a.per_stratum:
                continue
            gused = {tile[i] for i, _ in chosen}
            pool = [
                i
                for i in by_k[k]
                if tile[i] not in tiles[k] and not used[cand[i] : cand[i] + B].any()
            ]
            pool.sort(
                key=lambda i: tile[i] in gused
            )  # stable: unused tiles first, random order within
            for i in pool:
                if take(i, f"stratum:{k}"):
                    have[k] += 1
                    tiles[k].add(tile[i])
                    break
    spare = {k: [i for i in by_k[k] if tile[i] not in tiles[k]] for k in range(20)}
    target = 20 * a.per_stratum + len(BIOME_CELLS)
    for k in sorted(spare, key=lambda k: -len(spare[k])):
        for i in spare[k]:
            if len(chosen) >= target:
                break
            if take(i, f"fill:{k}"):
                break
    rows = []
    for i, why in sorted(chosen, key=lambda t: cand[t[0]]):
        s = int(cand[i])
        rows.append(
            {
                "block": len(rows),
                "start": s,
                "end": s + B - 1,
                "lat": float(lat[s]),
                "lon_w": float(lon[s]),
                "lon_e": float(lon[s + B - 1]),
                "mat_c": round(float(bm[i]), 3),
                "map": round(float(bp[i]), 4),
                "stems_per_patch": round(float(tree[s : s + B].mean()), 3),
                "n_tree_cells": int((tree[s : s + B] > 0).sum()),
                "stratum": int(st[i]),
                "tile15": int(tile[i]),
                "reason": why,
            }
        )
    df = pl.DataFrame(rows)
    out = os.path.join(REPO, "test", "testitems", "references", "S_D0_panel_blocks.csv")
    df.write_csv(out)
    print(df.group_by("stratum").len().sort("stratum"))
    print(
        f"blocks {df.height}  cells {df.height * B}  distinct 15deg tiles {df['tile15'].n_unique()}  -> {out}"
    )


if __name__ == "__main__":
    main()
