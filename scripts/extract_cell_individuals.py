#!/usr/bin/env python3
# =============================================================================
# extract_cell_individuals.py — PER-CELL representative-individual canopy for the
# multi-cell coupled S+F+E driver (line M, milestone M1: per-cell input
# provisioning). The N-cell generalization of `extract_fdiff_individuals.py`,
# which was hard-wired to Hainich (cell 42490).
#
# WHY: `run_coupled_cell` is already N-cell-agnostic, but every biome cell was
# driven with **Hainich's** canopy (`references/hainich_individuals_2010.csv`) —
# deliberately, to isolate the climate effect. To run the biomes with their OWN
# vegetation, each cell needs its own reconstructed individual set.
#
# It REUSES (does not re-derive) the reconstruction physics of
# `extract_fdiff_individuals.py`: the per-PFT parameter table, the angio/gymno
# allometry, and the `getfpar.c` port of FIT's per-PATCH vertical layered
# Beer-Lambert light model. That script stays the producer of the committed
# Hainich fixture and is not modified.
#
# EMITS (committed, small):
#   <OUT>/M_individuals_<name>_<year>.csv   — same columns as the Hainich fixture
#   <OUT>/M_cells.csv                       — the per-cell metadata table that
#       REPLACES the hard-coded `BIOMES` dict in extract_biome_forcing.py and the
#       hard-coded latitude list in run_coupled_biomes.jl / biome_coupled_tests.jl
#   <OUT>/M_individuals_meta.json
#
# PER-CELL VALIDATION (the reason to trust a cell we have never reconstructed):
#   the reconstructed cell FAPAR (= sum of per-individual `fpar_leafon` / npatch)
#   is compared against **that cell's own C daily FAPAR** from its single-cell
#   `d_fapar.nc` re-run (`scripts/run_fdiff_validation_cell.sh CELL=<idx>
#   RUNTAG=M_biome_val`). Because the reconstruction is a LEAF-ON (peak) canopy,
#   the comparison basis is the C's annual PEAK (mean of the 30 highest days of
#   the reference year) — hemisphere-agnostic, unlike the DOY 150-240 window the
#   Hainich script used (reported too, for continuity).
#
# Usage (login node; one `ind` parquet scan for all cells, ~5 s):
#   /home/jamirp/.conda/envs/py311_new/bin/python scripts/extract_cell_individuals.py
# Env: CELLS="name:idx,..." YEAR OUT
# =============================================================================
import glob
import json
import math
import os
import sys

import netCDF4 as nc
import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_biome_forcing import cells_from_env  # noqa: E402  (THE canonical cell registry)
from extract_fdiff_individuals import (  # noqa: E402  (reuse the reconstruction physics)
    CROWNLENGTH,
    EPS,
    K_LAMBERT,
    NPATCH,
    PFT,
    VSTEP,
    allom,
    crown_area,
    layered_light,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFDIR = os.path.join(REPO, "test", "testitems", "references")
RUN_ROOT = "/p/tmp/jamirp/esm_land_daily"
GRID = f"{RUN_ROOT}/daily_2000_2019_global_c0_67419_seed1/output/grid.nc"
IND_PARQUET = "/p/tmp/jamirp/emulator_global/ind_hist_seed1_all.parquet"
NDAYYEAR = 365
FIRSTYEAR = 2000          # the daily re-runs start at the 1999 restart
PEAK_DAYS = 30            # leaf-on comparison basis: mean of the N highest days

COLS = [
    "patch", "type", "height", "lai", "sla", "wooddens", "fpc_ind", "crownarea", "nind",
    "leaf_c", "sapwood_c", "root_c", "boleht", "fpar_leafon", "alphaa", "albedo_leaf",
    "k_beer", "emax", "beta_root", "d95", "agb", "vegc", "gpp_ind", "transp_ind", "npp_ind",
    # APPENDED 2026-08-12 (line M, rung 3) — the C's own per-individual identity and age.
    # `(Cell, Patch, ID)` is a STABLE identity ACROSS YEARS in the `ind` output: matched over
    # 2010-2019 at all five biome cells, `Age` increments by exactly 1 on every one of 10 323
    # pairs, `SLA`/`Wooddens` are bit-identical (traits are immutable after `new_tree`), and no
    # stem emitted with `isdead == 1` ever reappears. That is what makes a PAIRED per-stem
    # F-vs-C growth comparison possible (ADR 0125). Appended LAST so every pre-existing value in
    # the committed 2010 fixtures stays byte-identical (guardrail 4).
    "id", "age",
]


def cell_latlon(cell):
    """orderA 0-based cell index -> (lat, lon) via the global run's grid.nc
    `cellid[lat, lon]` (the authoritative map; never assume a raster order)."""
    with nc.Dataset(GRID) as d:
        cid = np.asarray(d["cellid"][:])
        lat = ((np.asarray(d["lat_bnds"][:, 0]) + np.asarray(d["lat_bnds"][:, 1])) / 2)
        lon = ((np.asarray(d["lon_bnds"][:, 0]) + np.asarray(d["lon_bnds"][:, 1])) / 2)
    idx = np.argwhere(cid == cell)
    if len(idx) == 0:
        raise ValueError(f"cell {cell} not found in {GRID}")
    i, j = idx[0]
    return float(lat[i]), float(lon[j])


def c_fapar(cell, year):
    """(peak, gs_window, annual_max) cell FAPAR for `year` from the cell's own
    single-cell `d_fapar.nc` re-run, or `None` if that run does not exist."""
    hits = sorted(glob.glob(f"{RUN_ROOT}/daily_*_c{cell}_seed1/output/d_fapar.nc"))
    if not hits:
        return None
    with nc.Dataset(hits[0]) as d:
        v = [k for k in d.variables if k not in ("time", "time_bnds", "lat", "lon", "lat_bnds", "lon_bnds")][0]
        a = np.asarray(d[v][:, 0, 0], dtype=np.float64)
    off = (year - FIRSTYEAR) * NDAYYEAR
    if off + NDAYYEAR > len(a):
        return None
    y = a[off:off + NDAYYEAR]
    y = np.where(y < -1.0e30, np.nan, y)                    # LPJmL missing value -1e32
    return dict(
        run=os.path.basename(os.path.dirname(os.path.dirname(hits[0]))),
        peak=float(np.mean(np.sort(y)[-PEAK_DAYS:])),
        gs150_240=float(np.nanmean(y[149:240])),
        annmax=float(np.nanmax(y)),
    )


def merge_rows(path, hdr, rows):
    """`rows` updated into the existing CSV's rows (keyed by `name`), order preserved:
    previously-registered cells first, new ones appended. Keeps a subset `CELLS=` run
    from truncating the shared registry.

    Returns `(header, rows)` — the header is the file's OWN header extended with any
    column this script produces that the file did not have.

    ⚠ WHY IT RETURNS A HEADER (line M, 2026-08-12). `M_cells.csv` is written by TWO
    scripts: this one owns the first ten columns, and `extract_cell_slow_init.py`
    APPENDS six more (`n_init`, `age0`, and the four-column slow boundary — the pinned
    Component-S per-cell seed). The previous version dropped every row whose field
    count differed from its own `hdr`, so re-running this script over the live registry
    silently discarded all six of those columns and with them the artifact pin. The
    merge now preserves any column it does not own.
    """
    if not os.path.exists(path):
        return hdr, rows
    new = {r["name"]: r for r in rows}
    file_hdr, out, seen = None, [], set()
    for ln in open(path):
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        f = s.split(",")
        if file_hdr is None:                       # the first non-comment line IS the header
            file_hdr = f
            continue
        if len(f) != len(file_hdr):
            continue
        old = dict(zip(file_hdr, f))
        name = old["name"]
        seen.add(name)
        out.append({**old, **new[name]} if name in new else old)
    if file_hdr is None:
        return hdr, rows
    hdr_out = file_hdr + [c for c in hdr if c not in file_hdr]
    return hdr_out, out + [r for r in rows if r["name"] not in seen]


def merge_rows_json(path, cells):
    """Same merge for the meta JSON's `cells` list."""
    if not os.path.exists(path):
        return cells
    try:
        old = json.load(open(path)).get("cells", [])
    except (ValueError, OSError):
        return cells
    names = {c["name"] for c in cells}
    return [c for c in old if c.get("name") not in names] + cells


def reconstruct(pdf_rows):
    """Per-patch reconstruction + layered light. `pdf_rows` = the living
    individuals of ONE patch as dicts. Returns their records."""
    trees, grasses = [], []
    for r in pdf_rows:
        pid = int(r["Type"])
        name, alphaa, albedo, is_gymno, emax = PFT.get(pid, PFT[3])
        a = allom(pid)
        H, LAI, SLA = float(r["Height"]), float(r["LAI"]), float(r["SLA"])
        rho, fpc = float(r["Wooddens"]), float(r["fpc_ind"])
        rec = dict(
            patch=int(r["Patch"]), type=pid, height=H, lai=LAI, sla=SLA, wooddens=rho,
            fpc_ind=fpc, alphaa=alphaa, albedo_leaf=albedo, k_beer=a["k_beer"], emax=emax,
            beta_root=float(r["beta_root"]), d95=float(r["D95"]), agb=float(r["agb"]),
            vegc=float(r["vegc"]), gpp_ind=float(r["gpp"]), transp_ind=float(r["transp"]),
            npp_ind=float(r["npp"]), id=int(r["ID"]), age=int(r["Age"]),
        )
        if pid <= 6 and H > 0:                                   # tree
            ca = crown_area(pid, H)
            leaf_c = LAI * ca / SLA if SLA > 0 and ca > 0 else 0.0
            denom = ca * (1.0 - math.exp(-a["k_beer"] * LAI)) if (ca > 0 and LAI > 0) else 0.0
            nind = fpc / denom if denom > EPS else 0.0           # fpc_tree inversion
            c_sap = H * leaf_c * SLA * rho / 4000.0 if leaf_c > 0 else 0.0
            rec.update(crownarea=ca, nind=nind, leaf_c=leaf_c, sapwood_c=c_sap,
                       root_c=leaf_c, boleht=(1.0 - CROWNLENGTH) * H)
            trees.append(rec)
        else:                                                    # grass
            rec.update(crownarea=0.0, nind=0.0, leaf_c=0.0, sapwood_c=0.0, root_c=0.0, boleht=0.0)
            grasses.append(rec)
    fpar_ff = layered_light(trees)
    for g in grasses:
        g["fpar_leafon"] = fpar_ff * (1.0 - math.exp(-g["k_beer"] * g["lai"])) if g["lai"] > 0 else 0.0
    return trees + grasses


def write_csv(path, name, cell, year, recs, cf, fapar_recon):
    with open(path, "w") as f:
        f.write(f"# {name} (global orderA cell {cell}) representative-individual canopy set, seed1 year {year}.\n")
        f.write(f"# {len(recs)} living individuals across {NPATCH} patches (sub-5m saplings are not in the ind output).\n")
        f.write("# Per-individual crown/leaf/sapwood reconstructed from the annual ind table via LPJmL-FIT allometry;\n")
        f.write(f"# fpar_leafon = per-PATCH vertical layered Beer-Lambert light share (getfpar.c port, k_lambert={K_LAMBERT}, VSTEP={VSTEP}m).\n")
        f.write(f"# cell FAPAR(leafon) = sum(fpar_leafon)/{NPATCH} = {fapar_recon:.4f}")
        if cf:
            f.write(f"; C peak(top-{PEAK_DAYS}d of {year}) = {cf['peak']:.4f}, ratio {fapar_recon / cf['peak']:.3f}")
        f.write("\n# gpp_ind/npp_ind = ind-table NPP (agpp+=npp bug); transp_ind = annual transpiration (mm/yr).\n")
        f.write("# scripts/extract_cell_individuals.py\n")
        f.write(",".join(COLS) + "\n")
        for r in recs:
            f.write(",".join(f"{r[c]:.6g}" if isinstance(r[c], float) else str(r[c]) for c in COLS) + "\n")


def main():
    cells = cells_from_env()
    year = int(os.environ.get("YEAR", "2010"))
    out_dir = os.environ.get("OUT", REFDIR)
    os.makedirs(out_dir, exist_ok=True)

    ids = [c for _, c in cells]
    df = (
        pl.scan_parquet(IND_PARQUET)
        .filter((pl.col("Cell").is_in(ids)) & (pl.col("Year") == year) & (pl.col("isdead") == 0))
        .select(["Cell", "Type", "Patch", "Height", "LAI", "SLA", "Wooddens", "agb", "vegc",
                 "fpc_ind", "beta_root", "D95", "gpp", "transp", "npp", "ID", "Age"])
        .collect()
    )
    print(f"== ind parquet: {df.height} living individuals over {len(ids)} cells, year {year}")
    print(f"{'name':24s} {'cell':>6s} {'lat':>7s} {'lon':>8s} {'nind':>5s} {'ntree':>6s} "
          f"{'ngrass':>6s} {'FAPARrec':>9s} {'FAPAR_C':>8s} {'ratio':>6s}  C run")

    rows, meta = [], []
    for name, cell in cells:
        cdf = df.filter(pl.col("Cell") == cell)
        if cdf.height == 0:
            print(f"{name:24s} {cell:6d}  SKIPPED — no living individuals in {year}")
            continue
        recs = []
        for pnum in sorted(cdf["Patch"].unique().to_list()):
            recs.extend(reconstruct(list(cdf.filter(pl.col("Patch") == pnum).iter_rows(named=True))))
        fapar_recon = sum(r["fpar_leafon"] for r in recs) / NPATCH
        tree_fpar = sum(r["fpar_leafon"] for r in recs if r["type"] <= 6) / NPATCH
        ntree = sum(1 for r in recs if r["type"] <= 6)
        lat, lon = cell_latlon(cell)
        cf = c_fapar(cell, year)
        path = os.path.join(out_dir, f"M_individuals_{name}_{year}.csv")
        write_csv(path, name, cell, year, recs, cf, fapar_recon)
        ratio = (fapar_recon / cf["peak"]) if cf else float("nan")
        print(f"{name:24s} {cell:6d} {lat:7.2f} {lon:8.2f} {len(recs):5d} {ntree:6d} "
              f"{len(recs) - ntree:6d} {fapar_recon:9.4f} "
              f"{(cf['peak'] if cf else float('nan')):8.4f} {ratio:6.3f}  {cf['run'] if cf else '-'}")
        rows.append(dict(
            name=name, cell=cell, lat=lat, lon=lon, npatch=NPATCH, n_ind=len(recs),
            n_trees=ntree, n_grass=len(recs) - ntree, fapar_recon=fapar_recon,
            fapar_C_peak=(cf["peak"] if cf else float("nan")),
        ))
        meta.append(dict(
            **rows[-1], tree_fpar=tree_fpar, grass_fpar=fapar_recon - tree_fpar,
            fapar_ratio=ratio, fapar_C_gs150_240=(cf["gs150_240"] if cf else None),
            fapar_C_annmax=(cf["annmax"] if cf else None), c_run=(cf["run"] if cf else None),
            file=os.path.basename(path),
            pft_type_counts={str(int(t)): int(cdf.filter(pl.col("Type") == t).height)
                             for t in sorted(cdf["Type"].unique().to_list())},
        ))

    # the per-cell metadata table that replaces every hard-coded cell/lat list.
    # MERGE, never truncate: a subset run (`CELLS="one_cell:123"` — the documented way to
    # re-extract a single cell) must not reduce the shared registry to one row, since
    # M_cells.csv is what biome_coupled_tests.jl and run_coupled_biomes.jl enumerate.
    mcells = os.path.join(out_dir, "M_cells.csv")
    hdr = ["name", "cell", "lat", "lon", "npatch", "n_ind", "n_trees", "n_grass", "fapar_recon", "fapar_C_peak"]
    own_comments = ("# Per-cell metadata", "# 0-based index", "# fapar_recon =", "# scripts/extract_cell_individuals.py")
    foreign_comments = [
        ln.rstrip("\n") for ln in (open(mcells) if os.path.exists(mcells) else [])
        if ln.startswith("#") and not ln.startswith(own_comments)
    ]
    hdr, rows = merge_rows(mcells, hdr, rows)
    meta = merge_rows_json(os.path.join(out_dir, "M_individuals_meta.json"), meta)
    with open(mcells, "w") as f:
        f.write("# Per-cell metadata for the multi-cell coupled S+F+E driver (line M, M1). Cell = global orderA\n")
        f.write("# 0-based index; lat/lon from the global run's grid.nc `cellid`. Ordered cold->hot.\n")
        f.write("# fapar_recon = reconstructed leaf-on cell FAPAR; fapar_C_peak = the C's own top-30-day mean.\n")
        f.write("# scripts/extract_cell_individuals.py\n")
        for c in foreign_comments:                 # another script's provenance lines, kept verbatim
            f.write(c + "\n")
        f.write(",".join(hdr) + "\n")
        for r in rows:
            # a cell registered for the first time has no value for a column another script owns
            f.write(",".join(
                f"{r[k]:.6g}" if isinstance(r.get(k), float) else str(r.get(k, "")) for k in hdr
            ) + "\n")
    with open(os.path.join(out_dir, "M_individuals_meta.json"), "w") as f:
        json.dump(dict(year=year, ind_parquet=IND_PARQUET, peak_days=PEAK_DAYS, cells=meta), f, indent=2)
    print(f"\nwrote {mcells} + M_individuals_meta.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
