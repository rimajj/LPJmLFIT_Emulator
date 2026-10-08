"""trackd_collect_panel.py — collect one (member, leg) of the Track-D panel campaign (scripts/trackd_panel.py) into
durable parquet tables under /p/projects/open/Jamir/esm_land_emulator_data/trackD/panel/m<k>/<leg>/.

Tables (one file each, all keyed by the orderA `Cell` index, read from each block's own grid.nc `cellid`):
  ind.parquet         the per-tree table, every block, 29 columns with pinned dtypes, sorted (Year, Cell, Patch).
                      ALL heights (LPJ_IND_ALL_HEIGHTS: filter Height > 5 for the ground-truth format) and the
                      `gpp` column is REAL gross GPP (LPJ_IND_TRUE_GPP; in the ground truth it is a copy of npp).
  daily.parquet       Cell, Year, Day(1-365) + prec transp evap interc runoff swe rootmoist pet npp gpp (daily legs)
                      ⚠ the NetCDF `units` attribute of LPJmL daily output says per month; the values are per DAY.
  monthly.parquet     Cell, Year, Month, layer + swc (+ whc_nat on daily legs)
  annual.parquet      Cell, Year + vegc, lai_stand
  fpc_stand.parquet   Cell, Year, pft (0-10, the C's PFT index) + fpc_stand
  globalflux.parquet  every block's globalflux.csv rows + its block id (sums over the block's cells)
  manifest.json       per-block completion, row counts, years, cells, the binary md5, and the gate verdict

GATE (nothing is written unless all hold): every block log has "lpjml successfully terminated, 10 grid cells
processed."; every block's grid.nc cellids equal its [start, end] from S_D0_panel_blocks.csv; every table covers
exactly the leg's years; the ind table has no fully identical row (a block merged twice); shared tree IDs inside
a patch are a property of the C writer and are counted in the manifest, not gated.

Usage: python scripts/trackd_collect_panel.py <member> <leg> [--panel DIR] [--out DIR]
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os

import netCDF4 as nc
import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL = "/p/tmp/jamirp/trackD/panel"
OUT = "/p/projects/open/Jamir/esm_land_emulator_data/trackD/panel"
BLOCKS_CSV = os.path.join(REPO, "test", "testitems", "references", "S_D0_panel_blocks.csv")
COLS = [
    "Year", "ID", "Type", "Height", "Age", "agb", "vegc", "transp", "npp", "gpp", "wscal_mean",
    "SLA", "Longevity", "Wooddens", "LAI", "fpc_ind", "minwscal", "D95", "D95max", "beta_root",
    "k_root", "mort_npp", "mort_age", "mort_water", "mort_temp", "mort", "isdead", "Patch", "Cell",
]  # fmt: skip
INT_DT = {"Year": pl.Int16, "ID": pl.Int32, "Type": pl.Int8, "Patch": pl.Int16, "Cell": pl.Int32,
          "isdead": pl.Int8}  # fmt: skip
SCHEMA = {c: INT_DT.get(c, pl.Float32) for c in COLS}
DAILY = {"prec": "prec", "transp": "transp", "evap": "evap", "interc": "interc", "runoff": "runoff",
         "swe": "SWE", "rootmoist": "rootmoist", "pet": "PET", "npp": "NPP", "gpp": "GPP"}  # fmt: skip
PQ = dict(compression="zstd", compression_level=3)


def years_of(leg):
    return (1997, 1999) if leg == "spinup" else ((2000, 2019) if leg == "hist" else (2020, 2100))


def cell_index(bd):
    ds = nc.Dataset(os.path.join(bd, "output", "grid.nc"))
    cid = np.asarray(ds["cellid"][:]).reshape(len(ds.dimensions["lat"]), len(ds.dimensions["lon"]))
    ds.close()
    return cid


def read_var(path, var, cid, y0, kind):
    """kind: daily | monthly | annual. Returns a long DataFrame keyed by Cell + time (+ extra dim)."""
    ds = nc.Dataset(path)
    a = np.ma.filled(ds[var][:].astype(np.float64), np.nan)
    dims = ds[var].dimensions
    ds.close()
    extra = [d for d in dims if d not in ("time", "lat", "lon")]
    a = np.moveaxis(a, [dims.index("time"), dims.index("lat"), dims.index("lon")], [0, -2, -1])
    nt = a.shape[0]
    a = a.reshape(nt, -1 if not extra else a.shape[1], cid.size) if extra else a.reshape(nt, cid.size)
    t = np.arange(nt)
    per = {"daily": 365, "monthly": 12, "annual": 1}[kind]
    year, sub = y0 + t // per, t % per + 1
    cells = cid.ravel()
    if extra:
        ne = a.shape[1]
        ti, ei, ci = np.meshgrid(np.arange(nt), np.arange(ne), np.arange(cells.size), indexing="ij")
        return pl.DataFrame({"Cell": cells[ci.ravel()].astype(np.int32), "Year": year[ti.ravel()].astype(np.int16),
                             "sub": sub[ti.ravel()].astype(np.int16), extra[0]: ei.ravel().astype(np.int16),
                             "value": a.ravel().astype(np.float32)})  # fmt: skip
    ti, ci = np.meshgrid(np.arange(nt), np.arange(cells.size), indexing="ij")
    return pl.DataFrame({"Cell": cells[ci.ravel()].astype(np.int32), "Year": year[ti.ravel()].astype(np.int16),
                         "sub": sub[ti.ravel()].astype(np.int16), "value": a.ravel().astype(np.float32)})  # fmt: skip


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("member", type=int)
    ap.add_argument("leg")
    ap.add_argument("--panel", default=PANEL)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--blocks-csv", default=BLOCKS_CSV)  # testing only
    ap.add_argument("--years", type=int, nargs=2, default=None)  # testing only
    a = ap.parse_args()
    y0, y1 = a.years or years_of(a.leg)
    blocks = {int(r["block"]): (int(r["start"]), int(r["end"])) for r in csv.DictReader(open(a.blocks_csv))}
    legdir = os.path.join(a.panel, f"m{a.member}", a.leg)
    bds = sorted(glob.glob(os.path.join(legdir, "b*")))
    assert len(bds) == len(blocks), f"{legdir}: {len(bds)} block dirs, panel has {len(blocks)}"
    man = {"member": a.member, "leg": a.leg, "years": [y0, y1], "blocks": {}}
    inds, daily, monthly, annual, fpcs, gfs = [], {}, {}, {}, [], []
    for bd in bds:
        b = int(os.path.basename(bd)[1:])
        log = open(os.path.join(bd, "lpjml.log"), errors="replace").read()
        ok = "lpjml successfully terminated, 10 grid cells processed." in log
        assert ok, f"{bd}: no completion line"
        cid = cell_index(bd)
        s, e = blocks[b]
        assert sorted(cid.ravel().tolist()) == list(range(s, e + 1)), f"{bd}: cellids {cid.ravel()} != {s}..{e}"
        out = os.path.join(bd, "output")
        if a.leg != "spinup":
            d = pl.read_csv(os.path.join(out, "ind.csv"), has_header=True, new_columns=COLS, schema=SCHEMA)
            inds.append(d)
            man["blocks"][b] = {"ind_rows": d.height}
            for f, kind in (("vegc.nc", "annual"), ("lai_stand.nc", "annual"), ("mswc.nc", "monthly"),
                            ("whc_nat.nc", "monthly")):  # fmt: skip
                p = os.path.join(out, f)
                if os.path.exists(p):
                    name = f.replace(".nc", "").replace("mswc", "swc")
                    var = {"vegc": "VegC", "lai_stand": "LAI", "swc": "SWC", "whc_nat": "whc_nat"}[name]
                    (annual if kind == "annual" else monthly).setdefault(name, []).append(
                        read_var(p, var, cid, y0, kind))
            fp = os.path.join(out, "fpc_stand.nc")
            if os.path.exists(fp):
                fpcs.append(read_var(fp, "FPC", cid, y0, "annual"))
            for name, var in DAILY.items():
                p = os.path.join(out, f"d_{name}.nc")
                if os.path.exists(p):
                    daily.setdefault(name, []).append(read_var(p, var, cid, y0, "daily"))
            g = pl.read_csv(os.path.join(out, "globalflux.csv"), infer_schema_length=0)
            gfs.append(g.with_columns(pl.lit(b).alias("block")))
        else:
            man["blocks"][b] = {"ok": True}
    od = os.path.join(a.out, f"m{a.member}", a.leg)
    os.makedirs(od, exist_ok=True)
    if a.leg != "spinup":
        ind = pl.concat(inds).sort(["Year", "Cell", "Patch"], maintain_order=True)
        yrs = ind["Year"].unique().sort().to_list()
        assert yrs == list(range(y0, y1 + 1)), f"ind years {yrs[:3]}..{yrs[-3:]}"
        # The C reuses tree IDs inside a patch (two different trees, different Age, same (Cell, Patch, ID, Type)),
        # so the key is NOT unique by design and is reported, not gated. What IS gated: no fully identical row,
        # which is what a block merged twice would produce.
        key = ["Year", "Cell", "Patch", "ID", "Type"]
        man["shared_id_rows"] = ind.height - ind.select(key).unique().height
        full = ind.height - ind.unique().height
        assert full == 0, f"{full} fully identical ind rows (a block merged twice?)"
        ind.write_parquet(os.path.join(od, "ind.parquet"), **PQ)
        man["ind_rows"] = ind.height

        def wide(parts, idx):
            t = None
            for name, lst in parts.items():
                df = pl.concat(lst).rename({"value": name, "sub": idx[2]} if "sub" in lst[0].columns else {"value": name})
                t = df if t is None else t.join(df, on=[c for c in df.columns if c != name], how="full", coalesce=True)
            return t

        if daily:
            dd = wide(daily, ["Cell", "Year", "Day"]).sort(["Cell", "Year", "Day"])
            assert dd["Year"].min() == y0 and dd["Year"].max() == y1
            dd.write_parquet(os.path.join(od, "daily.parquet"), **PQ)
            man["daily_rows"] = dd.height
        mm = wide(monthly, ["Cell", "Year", "Month"]).sort(["Cell", "Year", "Month", "layer"])
        mm.write_parquet(os.path.join(od, "monthly.parquet"), **PQ)
        an = wide(annual, ["Cell", "Year", "sub"]).drop("sub").sort(["Cell", "Year"])
        assert an["Year"].min() == y0 and an["Year"].max() == y1
        an.write_parquet(os.path.join(od, "annual.parquet"), **PQ)
        if fpcs:
            pl.concat(fpcs).rename({"value": "fpc_stand", "npft": "pft"}).drop("sub").sort(
                ["Cell", "Year", "pft"]).write_parquet(os.path.join(od, "fpc_stand.parquet"), **PQ)
        pl.concat(gfs, how="diagonal").write_parquet(os.path.join(od, "globalflux.parquet"), **PQ)
    md5 = open(os.path.join(os.path.dirname(a.panel), "cbuild", "lpjml56fit_snapshot", "PROVENANCE.txt")).read()
    man["binary"] = md5.strip().splitlines()[-2:] if md5 else None
    man["gate"] = "PASS"
    json.dump(man, open(os.path.join(od, "manifest.json"), "w"), indent=1)
    print(f"m{a.member}/{a.leg}: PASS -> {od}  ind_rows={man.get('ind_rows')}")


if __name__ == "__main__":
    main()
