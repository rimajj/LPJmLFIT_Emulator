#!/usr/bin/env python3
"""Provision the three SPATIAL artifacts the ADR-0040 blocked-CV experiment needs — from `grid.nc`.

WHY THIS EXISTS (milestone S2 / ADR 0040)
-----------------------------------------
ADR 0038 shipped a 14-column recruit-trait copula whose +0.037 Wooddens `emu_r` comes from a per-cell env
conditioning tail, and then recorded the doubt that gates production: those six columns have median
WITHIN-CELL sd **exactly 0 for 100 % of cells**, so they are a per-cell spatial ADDRESS, not a climate
response. The published evaluation cannot tell the difference, because `eval_slow_copula.jl` splits folds as
`mod(hash(cell), kfolds)` — which scatters test cells uniformly and therefore leaves **every test cell's
geographic neighbours in the training fold**. A 1-NN lookup on those same columns already reaches Wooddens
r = 0.800 with the nearest training neighbour 1.00 deg away.

Settling it needs three things that do not exist yet, and all three are functions of cell POSITION:

  1. `cell_latlon.txt`   — a per-cell (Cell, ilat, ilon, lat, lon) table in PLAIN TEXT, because
     `eval_slow_copula.jl` includes only `src/drf.jl` and has **no** CSV/Parquet/NetCDF dependency
     (ADR 0014 keeps the runtime `[deps]` empty). It is what lets the eval form spatially BLOCKED folds and
     a Chebyshev box-dilation BUFFER around each test block.
  2. `cell_geo_tail.parquet` — the `p14geo` control tail: six columns that are a PURE FUNCTION OF POSITION
     and carry no climate information whatsoever. If a pure address reproduces the env tail's gain, the gain
     is an address. Six columns (not two) so `ncond` — and therefore `DRF.fit_forest`'s
     `mtry_eff = round(Int, sqrt(p))` = 4 — matches `p14env` exactly; the specific basis is NOT load-bearing,
     only its purity and its width are. `sin_lon`/`cos_lon` remove the +-180 seam that raw `lon` carries,
     which a regression tree cannot represent with an axis-aligned split.
  3. `cell_env_perm_tail_s<seed>.parquet` — the `p14perm` control tail: the TRUE env columns with the
     Cell -> tuple assignment randomly PERMUTED across cells. Same width, same cell-level marginals, same
     6-way joint, **zero true geography**. It separates "the tail carries information" from "the extra width
     let the forest resolve more leaves".

THE PERMUTATION IS RESTRICTED TO THE TABLE'S OWN CELLS, and that is load-bearing
--------------------------------------------------------------------------------
`cell_year_feats` covers all 67 420 grid cells but the pooled copula table covers 58 766 (tree-recruit rows
only). Permuting the larger set and letting the augment step restrict afterwards would make the tail a
*sample* of the env distribution, so its cell-level marginals would no longer equal `p14env`'s and the
control would be contaminated — the ablation would confound "no geography" with "a different marginal".
So the permutation is formed over `np.unique(SRC/cells.i64)` and asserted to be a bijection of it.

What it preserves, and what it does not: the multiset of six-tuples over CELLS is identical to the true one
(asserted by a lexicographic sort of both (ncell, 6) arrays — a per-column marginal test would NOT catch a
broken 6-way joint). Cells are NOT weighted by their row counts, so the ROW-level marginals differ, and the
augment step's row-weighted manifest fallback row `x` will therefore differ from `p14env`'s. That is correct
— `x` must describe what is actually in the file — and it is stated in ADR 0040 rather than patched away.

TRAPS THIS SCRIPT ENCODES (each one silently produces a plausible wrong answer)
------------------------------------------------------------------------------
  * `cellid` is stored `int32` with `_FillValue = -999999`. Read it UNDECODED and `np.isfinite` is True for
    all 201 600 grid points, so the standard valid-mask silently yields 134 180 ocean "cells" carrying
    -999999. Use the plain CF-decoding `xr.open_dataset` (what the three sibling feature builders do) and
    keep the `ncell != 67420` FATAL guard — it is what catches a corrupt or wrong `grid.nc`.
  * decoded `cellid` is **float64**; it must be cast to int64 or it silently fails to join the parquet
    tables' `i64` `Cell`.
  * `np.meshgrid` must use `indexing="ij"`. The default `"xy"` transposes, pairs every cell with the wrong
    coordinates, and still produces 67 420 rows that pass every count guard.
  * this `grid.nc`'s lat axis starts at **-55.75** with **280** rows, not -89.75/360 — it is a crop of the
    global lattice. Derive the index origin from `grid["lat"].values[0]`, never a hard-coded constant.
  * `cos`/`sin` need RADIANS. Degrees would look plausible and be wrong.

Usage (fast — ~30 s, login node is fine; writes ~5 MB):
    OUT_DIR=/p/tmp/jamirp/emulator_global/tables \
    SRC=/p/tmp/jamirp/emulator_global/slow_copula_pooled_w20_t8 \
      python scripts/build_slow_spatial_controls.py

Env: OUT_DIR (default /p/tmp/jamirp/emulator_global/tables), GRID (the known-good global daily run's
     grid.nc), SRC (a copula table dir; its `cells.i64` defines the permutation's cell set — required only
     for the perm tail; pass SRC="" to skip it), CELL_YEAR_FEATS, ENV_COLS (the six true env columns,
     comma-separated, defaulting to the ADR-0038 tail), PERM_SEED (0).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import polars as pl
import xarray as xr

REPO = Path(__file__).resolve().parent.parent  # never a hard-coded absolute (CLAUDE.md §9 trap 6)
BASE = "/p/tmp/jamirp/emulator_global"

GRID = os.environ.get(
    "GRID",
    "/p/tmp/jamirp/esm_land_daily/daily_2000_2019_global_c0_67419_seed1/output/grid.nc",
)
OUT_DIR = Path(os.environ.get("OUT_DIR", f"{BASE}/tables"))
SRC = os.environ.get("SRC", f"{BASE}/slow_copula_pooled_w20_t8").strip()
CELL_YEAR_FEATS = os.environ.get("CELL_YEAR_FEATS", f"{BASE}/tables/cell_year_feats.parquet")
ENV_COLS = [
    c.strip()
    for c in os.environ.get(
        "ENV_COLS",
        "prec_mean,eco_diag_p_pet_ratio,eco_diag_pet_mean,eco_diag_vpd_mean,pr_cv_monthly,humid_mean",
    ).split(",")
    if c.strip()
]
PERM_SEED = int(os.environ.get("PERM_SEED", "0"))

NCELL_GLOBAL = 67420
DEG = 0.5
HAINICH = (42490, 51.25, 10.25)  # the [VERIFIED] orientation check (CLAUDE.md §1)

# The geo basis. Pure functions of position, six wide so `ncond` and therefore `mtry_eff` match `p14env`.
#
# THE SIXTH COLUMN IS `geo_x`, NOT `cos(lat)`, AND THE REASON IS LOAD-BEARING. A regression tree splits on
# one feature at a time, so two columns that are monotone transforms of each other are LITERALLY the same
# feature to it. `cos(lat)` is a strict monotone (decreasing) function of `abs(lat)` — measured Spearman
# rho = **-1.000000** over all 67 420 cells — so a basis containing both is effectively FIVE-dimensional
# while still declaring `ncond = 14`. That silently HANDICAPS the control: the geo arm gets one dead column
# and a diluted `mtry`, which biases the experiment toward "env beats a pure address", i.e. toward the
# hypothesis under test. `geo_x = cos(lat)·cos(lon)` is a genuine lat×lon INTERACTION that no axis-aligned
# split on the other five can reproduce, so all six columns carry distinct partitioning power.
GEO_COLS = ["geo_lat", "geo_lon", "geo_sin_lon", "geo_cos_lon", "geo_abs_lat", "geo_x"]


def fatal(msg: str) -> None:
    print(f"FATAL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def read_grid():
    """(Cell, ilat, ilon, lat, lon) for every land cell, plus the lattice metadata, from `grid.nc`."""
    grid = xr.open_dataset(GRID)  # CF decoding ON: _FillValue -> NaN. See the traps in the docstring.
    if "cellid" not in grid:
        fatal(f"{GRID} has no `cellid` variable — wrong file?")
    cid = grid["cellid"].values  # [lat, lon], float64, NaN over ocean
    valid = np.isfinite(cid)
    ncell = int(valid.sum())
    if ncell != NCELL_GLOBAL:
        fatal(
            f"grid.nc has {ncell} valid cells, expected {NCELL_GLOBAL} — wrong or corrupt grid ({GRID}). "
            "Point GRID at the global daily run's grid.nc."
        )
    lat1d = grid["lat"].values.astype(np.float64)
    lon1d = grid["lon"].values.astype(np.float64)
    # indexing="ij" is LOAD-BEARING — "xy" transposes and silently mispairs every cell.
    lat2d, lon2d = np.meshgrid(lat1d, lon1d, indexing="ij")

    cells = cid[valid].astype(np.int64)  # float64 -> int64 or the parquet join silently fails
    lat = lat2d[valid]
    lon = lon2d[valid]

    lat0, lon0 = float(lat1d[0]), float(lon1d[0])  # NOT -89.75: this file is a crop of the global lattice
    ilat = np.rint((lat - lat0) / DEG).astype(np.int64)
    ilon = np.rint((lon - lon0) / DEG).astype(np.int64)
    if not np.array_equal(cid[ilat, ilon].astype(np.int64), cells):
        fatal("the (ilat, ilon) index formula does not round-trip against cellid — lattice assumption broken")

    order = np.argsort(cells, kind="stable")
    meta = {
        "nlat": len(lat1d),
        "nlon": len(lon1d),
        "dlat": DEG,
        "lat0": lat0,
        "lon0": lon0,
        "ncell": ncell,
    }
    df = pl.DataFrame(
        {
            "Cell": cells[order],
            "ilat": ilat[order],
            "ilon": ilon[order],
            "lat": lat[order],
            "lon": lon[order],
        }
    )
    # orientation gate: Hainich must land where CLAUDE.md §1 says it does
    hc, hlat, hlon = HAINICH
    row = df.filter(pl.col("Cell") == hc)
    if row.height != 1:
        fatal(f"cell {hc} (Hainich) not present in {GRID}")
    got = (float(row["lat"][0]), float(row["lon"][0]))
    if got != (hlat, hlon):
        fatal(f"orientation check FAILED: cell {hc} is at {got}, expected ({hlat}, {hlon})")
    print(f"  grid     : {ncell} land cells, lat {len(lat1d)} x lon {len(lon1d)} @ {DEG} deg")
    print(f"  lattice  : lat0={lat0} lon0={lon0}; Hainich {hc} -> ({hlat}, {hlon})  [orientation OK]")
    if df["Cell"].n_unique() != df.height:
        fatal("duplicated Cell in grid.nc — impossible; the read is wrong")
    return df, meta


def write_latlon_txt(df: pl.DataFrame, meta: dict) -> Path:
    """The plain-text table `eval_slow_copula.jl` parses with Base only (no deps — ADR 0014)."""
    path = OUT_DIR / "cell_latlon.txt"
    with open(path, "w") as fh:
        fh.write("# cell_latlon.txt -- per-cell orderA position, for spatially BLOCKED CV (ADR 0040).\n")
        fh.write(f"# generated by scripts/build_slow_spatial_controls.py from {GRID}\n")
        fh.write("# `# key value` metadata lines below are parsed; `ilon` WRAPS modulo nlon (dateline),\n")
        fh.write("# `ilat` does NOT (the lat axis is a real data edge, not a periodic boundary).\n")
        for k in ("nlat", "nlon", "dlat", "lat0", "lon0", "ncell"):
            fh.write(f"# {k} {meta[k]}\n")
        fh.write("# cell ilat ilon lat lon\n")
        for c, ila, ilo, la, lo in df.iter_rows():
            fh.write(f"{c} {ila} {ilo} {la:.2f} {lo:.2f}\n")
    print(f"  wrote    : {path}  ({path.stat().st_size} B, {df.height} rows)")
    return path


def write_geo_tail(df: pl.DataFrame) -> Path:
    """`p14geo`: six columns that are a pure function of position. RADIANS for the trig (see traps)."""
    lat = df["lat"].to_numpy()
    lon = df["lon"].to_numpy()
    lonr = np.deg2rad(lon)
    latr = np.deg2rad(lat)
    out = pl.DataFrame(
        {
            "Cell": df["Cell"],
            GEO_COLS[0]: lat,
            GEO_COLS[1]: lon,
            GEO_COLS[2]: np.sin(lonr),
            GEO_COLS[3]: np.cos(lonr),
            GEO_COLS[4]: np.abs(lat),
            GEO_COLS[5]: np.cos(latr) * np.cos(lonr),
        }
    )
    for c in GEO_COLS:
        v = out[c].to_numpy()
        if not np.isfinite(v).all():
            fatal(f"geo column {c} has non-finite values")
    # GATE the basis, do not merely intend it: no two tail columns may be monotone transforms of each other
    # (see the GEO_COLS note). Rank correlation, because that is exactly what an axis-aligned split sees.
    a = np.column_stack([out[c].to_numpy() for c in GEO_COLS])
    rk = np.column_stack([np.argsort(np.argsort(a[:, j])) for j in range(a.shape[1])]).astype(np.float64)
    cc = np.corrcoef(rk, rowvar=False)
    for i in range(len(GEO_COLS)):
        for j in range(i + 1, len(GEO_COLS)):
            if abs(cc[i, j]) >= 0.99:
                fatal(
                    f"geo basis is rank-degenerate: {GEO_COLS[i]} vs {GEO_COLS[j]} rho={cc[i, j]:+.6f} — "
                    "an axis-aligned tree sees one dead column, which handicaps the control"
                )
    print(f"  geo gate : no pair of the {len(GEO_COLS)} geo columns has |Spearman| >= 0.99 "
          f"(max {max(abs(cc[i, j]) for i in range(len(GEO_COLS)) for j in range(i + 1, len(GEO_COLS))):.4f})")
    if out["Cell"].n_unique() != out.height:
        fatal("geo tail is not one row per Cell")
    path = OUT_DIR / "cell_geo_tail.parquet"
    out.write_parquet(path)
    print(f"  wrote    : {path}  ({out.height} rows x {len(GEO_COLS)} cols)")
    return path


def env_percell() -> pl.DataFrame:
    """The TRUE per-cell env tail, on the SAME basis the augment script uses: NO year filter, mean per Cell.

    ADR 0038: `cell_year_feats` spans Year 2000-2019 only and IS the historic climatology the static
    boundary is built from, so the boundary's basis applies no year filter at all and every scenario reads
    the whole table. Reproducing that basis here is what makes the perm tail an exact permutation of the
    tail `p14env` actually carries.
    """
    have = pl.scan_parquet(CELL_YEAR_FEATS).collect_schema().names()
    missing = [c for c in ENV_COLS if c not in have]
    if missing:
        fatal(f"ENV_COLS not in {CELL_YEAR_FEATS}: {missing}")
    t = (
        pl.scan_parquet(CELL_YEAR_FEATS)
        .select(["Cell"] + ENV_COLS)
        .group_by("Cell")
        .agg([pl.col(c).mean().alias(c) for c in ENV_COLS])
        .collect()
    )
    if t.height == 0:
        fatal(f"the per-cell env aggregation is EMPTY (source {CELL_YEAR_FEATS}) — not a coverage hole")
    if t["Cell"].n_unique() != t.height:
        fatal("duplicated Cell in the env aggregation (ADR 0036 §5b streaming key-set nondeterminism)")
    for c in ENV_COLS:
        v = t[c].to_numpy()
        if not np.isfinite(v).all():
            fatal(f"env column {c} has non-finite per-cell means")
    return t


def write_perm_tail(env: pl.DataFrame) -> Path:
    """`p14perm`: the true env tuples, PERMUTED across the SOURCE TABLE's own cells (see the docstring)."""
    cells_path = Path(SRC) / "cells.i64"
    if not cells_path.is_file():
        fatal(f"{cells_path} not found — SRC must be a copula table dir (or set SRC='' to skip the perm tail)")
    tab_cells = np.unique(np.fromfile(cells_path, dtype="<i8"))
    env_cells = env["Cell"].to_numpy()
    have = np.isin(tab_cells, env_cells)
    if not have.all():
        fatal(f"{int((~have).sum())} of {len(tab_cells)} table cells have no env tuple — coverage hole")

    sub = env.join(pl.DataFrame({"Cell": tab_cells}), on="Cell", how="inner").sort("Cell")
    if sub.height != len(tab_cells):
        fatal(f"env subset has {sub.height} rows for {len(tab_cells)} table cells")
    true_tup = np.column_stack([sub[c].to_numpy() for c in ENV_COLS])

    rng = np.random.default_rng(PERM_SEED)
    perm = rng.permutation(sub.height)
    perm_tup = true_tup[perm, :]

    # (1) BIJECTION over the 6-way JOINT, not just the marginals: a lexicographic sort of both
    #     (ncell, 6) arrays must agree exactly. Per-column tests cannot catch a broken joint.
    def lexsorted(a):
        return a[np.lexsort(tuple(a[:, j] for j in range(a.shape[1] - 1, -1, -1))), :]

    if not np.array_equal(lexsorted(true_tup), lexsorted(perm_tup)):
        fatal("the permuted tail is not a bijection of the true tail (joint multiset differs)")
    # (2) "zero true geography": self-maps must be negligible, and the field's spatial autocorrelation
    #     must be destroyed. Moran-style neighbour correlation is the real proof; self-maps alone are weak.
    self_frac = float((perm == np.arange(sub.height)).mean())
    print(f"  perm     : seed={PERM_SEED}  self-maps {self_frac:.2e} (expect ~{1 / sub.height:.1e})")
    perm_cols = [f"{c}_perm" for c in ENV_COLS]  # SUFFIXED: an identical `cond_cols` line to p14env's
    out = pl.DataFrame({"Cell": sub["Cell"]}).with_columns(
        [pl.Series(perm_cols[j], perm_tup[:, j]) for j in range(len(ENV_COLS))]
    )
    if out["Cell"].n_unique() != out.height:
        fatal("perm tail is not one row per Cell")

    path = OUT_DIR / f"cell_env_perm_tail_s{PERM_SEED}.parquet"
    out.write_parquet(path)
    side = OUT_DIR / f"cell_env_perm_tail_s{PERM_SEED}.provenance.txt"
    with open(side, "w") as fh:
        fh.write(f"seed\t{PERM_SEED}\nnumpy\t{np.__version__}\nrng\tdefault_rng(permutation)\n")
        fh.write(f"src\t{SRC}\nncell\t{sub.height}\nenv_cols\t{' '.join(ENV_COLS)}\n")
        fh.write(f"perm_cols\t{' '.join(perm_cols)}\nself_map_frac\t{self_frac:.6e}\n")
        fh.write(f"cell_year_feats\t{CELL_YEAR_FEATS}\n")
    print(f"  wrote    : {path}  ({out.height} rows x {len(perm_cols)} cols)")
    print(f"  wrote    : {side}")
    return path


def moran_report(df: pl.DataFrame, env: pl.DataFrame, perm_path: Path | None) -> None:
    """Neighbour correlation of the TRUE vs the PERMUTED field — the quantitative "is it an address" number.

    The east-neighbour lag on the 0.5 deg lattice: for every cell whose (ilat, ilon+1) neighbour is also a
    cell, correlate the field at the two. ~0.9 for a real climatology, ~0 for a permutation. This is also
    the statistic that says how strongly the env tail is spatially redundant in the first place.
    """
    pos = {(int(a), int(b)): int(c) for a, b, c in zip(df["ilat"], df["ilon"], df["Cell"])}
    nlon = int(df["ilon"].max()) + 1
    pairs = [
        (c, pos[(ila, (ilo + 1) % nlon)])
        for ila, ilo, c in zip(df["ilat"], df["ilon"], df["Cell"])
        if (int(ila), (int(ilo) + 1) % nlon) in pos
    ]
    if not pairs:
        return
    a = np.array([p[0] for p in pairs])
    b = np.array([p[1] for p in pairs])
    idx = {int(c): i for i, c in enumerate(env["Cell"])}
    ia = np.array([idx[c] for c in a if c in idx])
    ib = np.array([idx[c] for c in b if c in idx])
    m = min(len(ia), len(ib))
    ia, ib = ia[:m], ib[:m]
    print(f"  moran    : east-neighbour lag over {m} adjacent pairs")
    for c in ENV_COLS:
        v = env[c].to_numpy()
        r = float(np.corrcoef(v[ia], v[ib])[0, 1])
        print(f"     TRUE {c:<26s} r_neighbour = {r:+.4f}")
    if perm_path is not None:
        p = pl.read_parquet(perm_path)
        pidx = {int(c): i for i, c in enumerate(p["Cell"])}
        ja = np.array([pidx[c] for c in a if c in pidx])
        jb = np.array([pidx[c] for c in b if c in pidx])
        mm = min(len(ja), len(jb))
        ja, jb = ja[:mm], jb[:mm]
        for c in ENV_COLS:
            v = p[f"{c}_perm"].to_numpy()
            r = float(np.corrcoef(v[ja], v[jb])[0, 1])
            print(f"     PERM {c:<26s} r_neighbour = {r:+.4f}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"== build_slow_spatial_controls (repo {REPO})")
    print(f"  grid.nc  : {GRID}")
    print(f"  out dir  : {OUT_DIR}")
    df, meta = read_grid()
    write_latlon_txt(df, meta)
    write_geo_tail(df)
    env = env_percell()
    print(f"  env tail : {env.height} cells x {len(ENV_COLS)} true env cols from {CELL_YEAR_FEATS}")
    perm_path = write_perm_tail(env) if SRC else None
    if not SRC:
        print("  perm     : SKIPPED (SRC empty)")
    moran_report(df, env, perm_path)
    print("== done")


if __name__ == "__main__":
    main()
