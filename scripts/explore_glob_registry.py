#!/usr/bin/env python3
"""explore_glob_registry.py -- LINE X, the shared registry for M. Billing's global runs (ADR 0313/0314): the
global counterpart of explore_de_sh_registry.py (Germany SH0), much smaller because these runs have no segment
breaks, no recycled climate and one humidity setting throughout.

Writes ONLY under /p/projects/open/Jamir/esm_land_emulator_data/billing_global/registry/:
  members.parquet  one row per converted member-window: gcm, scen, seed, window, years, build (from the run's own
                   lpjml.*.out), ind_layout (stock 29 columns, or the Oct-2026 builds' 30: + Height_max, stemdiam,
                   barkthickness, mort_fire; - wscal_mean, beta_root, k_root), run_dir, ind / ind_dev paths,
                   conversion_ok.
  folds.parquet    Cell -> lon, lat, rock, block (5 x 5 degree tile), fold 1..K, is_dev (Cell % 10 == 0),
                   tree_bearing (any tree row, Type <= 6, in the member-2 historical or ssp370 table).
                   Folds: blocks sorted by a SHA-256 hash of the block id, then greedily given to the fold with the
                   fewest tree-bearing cells -> deterministic, independent of numpy's RNG.
  splits.parquet   role of each member-window in each PRE-REGISTERED global split (see SPLITS below).
  _gates.json

Usage: python scripts/explore_glob_registry.py build | check
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import sys

import numpy as np
import polars as pl

DATA = "/p/projects/open/Jamir/esm_land_emulator_data/billing_global"
OUT = os.path.join(DATA, "registry")
SRC = "/p/projects/pbscience/billing/LPJmLFIT/global"
GRID = "/p/projects/biodiversity/input_VERSION2/grid.bin"
SOIL_RAW = "/p/projects/biodiversity/input_VERSION2/soil_new_67420.bin"
NCELL = 67420
K = 5
BLOCK_DEG = 5.0
WIN_YEARS = {"h1985": (1985, 2014), "w2071": (2071, 2100), "h1990": (1990, 2019)}

# Pre-registered splits (written BEFORE any arm is scored on this set). Roles: train / val / test / ignore.
# Spatial K-fold by block is crossed with every split by the consumer (train on folds != k, score fold k).
FEB = (2, 3, 4, 6, 7, 8)
MAY = (9, 10)
SPLITS = {
    # held-out MEMBER, same build, every scenario: the noise-only test (the ceiling's twin)
    "GM": lambda r: ("test" if r["seed"] == 8 else "val" if r["seed"] == 7 else "train")
    if r["gcm"] == "GFDL-ESM4" and r["seed"] in FEB else "ignore",
    # held-out SCENARIO + member: extrapolation in warming (ssp370 is the warmest leg; train sees hist/126/245)
    "GS370": lambda r: ("test" if r["scen"] == "ssp370" and r["seed"] == 8
                        else "ignore" if r["scen"] == "ssp370" or r["seed"] == 8
                        else "val" if r["seed"] == 7 else "train")
    if r["gcm"] == "GFDL-ESM4" and r["seed"] in FEB else "ignore",
    # held-out SCENARIO, interpolation: ssp245 between 126 and 370
    "GS245": lambda r: ("test" if r["scen"] == "ssp245" and r["seed"] == 8
                        else "ignore" if r["scen"] == "ssp245" or r["seed"] == 8
                        else "val" if r["seed"] == 7 else "train")
    if r["gcm"] == "GFDL-ESM4" and r["seed"] in FEB else "ignore",
    # MODEL-VERSION transfer (owner: "the emulator needs to work with every model version"): train Feb build,
    # test the May build (same forcing) and the Oct builds (different forcing too)
    "GV": lambda r: ("train" if r["seed"] in FEB[:-1] else "val") if r["gcm"] == "GFDL-ESM4" and r["seed"] in FEB
    else "test",
}


def log(*a):
    print(*a, flush=True)


def run_dir(gcm, scen, seed):
    if gcm == "GSWP3-W5E5":
        return f"{SRC}/reanalysis/r1_{seed}"
    return f"{SRC}/GCM/{scen}/{gcm}/r1_{seed}"


def build_of(d):
    """Build date of the LAST lpjml.<job>.out in the run dir that finished; all logs listed for provenance."""
    rows = []
    for p in glob.glob(os.path.join(d, "lpjml.*.out")):
        txt = open(p, errors="replace").read()
        m = re.search(r"lpjml C Version (\S+) \(([A-Za-z]{3} +\d+ \d{4})\)", txt)
        ok = re.search(r"lpjml successfully terminated, (\d+) grid cells processed", txt)
        rows.append(dict(job=int(re.search(r"lpjml\.(\d+)\.out$", p).group(1)),
                         build=re.sub(r" +", " ", m.group(2)) if m else None, ok=bool(ok),
                         ncell=int(ok.group(1)) if ok else None))
    rows.sort(key=lambda r: r["job"])
    fin = [r for r in rows if r["ok"]]
    return (fin[-1]["build"] if fin else None), rows


def grid():
    with open(GRID, "rb") as f:
        raw = f.read(43)
    scalar = np.frombuffer(raw[39:43], dtype="<f4")[0]
    a = np.fromfile(GRID, dtype="<i2", offset=43).reshape(NCELL, 2).astype(np.float64) * scalar
    return a[:, 0], a[:, 1]


def members() -> pl.DataFrame:
    g = pl.read_csv(os.path.join(DATA, "ind", "_gates.csv"), infer_schema_length=0)
    out = []
    for r in g.iter_rows(named=True):
        seed = int(r["seed"])
        d = run_dir(r["gcm"], r["scen"], seed)
        b, logs = build_of(d)
        y0, y1 = WIN_YEARS[r["window"]]
        out.append(dict(member=r["member"], gcm=r["gcm"], scen=r["scen"], seed=seed, window=r["window"],
                        year0=y0, year1=y1, build=b,
                        ind_layout="oct2026_30col" if r["gcm"] == "GSWP3-W5E5" else "stock_29col",
                        n_logs=len(logs), logs=json.dumps(logs), run_dir=d,
                        ind_path=os.path.join(DATA, "ind", r["gcm"], r["scen"], f"s{seed}", r["window"]),
                        ind_dev_path=os.path.join(DATA, "ind_dev", f"{r['member']}.parquet"),
                        conversion_ok=r["conversion_ok"] == "true"))
    return pl.DataFrame(out).sort(["gcm", "scen", "seed"])


def tree_bearing(m: pl.DataFrame) -> np.ndarray:
    tb = np.zeros(NCELL, dtype=bool)
    for scen in ("historical", "ssp370"):
        p = m.filter((pl.col("gcm") == "GFDL-ESM4") & (pl.col("scen") == scen) & (pl.col("seed") == 2))["ind_path"]
        cells = (pl.scan_parquet(os.path.join(p[0], "**", "*.parquet")).filter(pl.col("Type") <= 6)
                 .select(pl.col("Cell").unique()).collect()["Cell"].to_numpy())
        tb[cells] = True
    return tb


def folds(tb: np.ndarray) -> pl.DataFrame:
    lon, lat = grid()
    bx = np.floor((lon + 180.0) / BLOCK_DEG).astype(np.int32)
    by = np.floor((lat + 90.0) / BLOCK_DEG).astype(np.int32)
    block = by * 1000 + bx
    soil = np.fromfile(SOIL_RAW, dtype=np.uint8)
    df = pl.DataFrame({"Cell": np.arange(NCELL, dtype=np.int32), "lon": lon, "lat": lat, "rock": soil == 13,
                       "block": block, "is_dev": np.arange(NCELL) % 10 == 0, "tree_bearing": tb})
    w = df.group_by("block").agg(pl.col("tree_bearing").sum().alias("ntb"))
    w = w.with_columns(pl.col("block").map_elements(
        lambda b: hashlib.sha256(f"glob-block-{b}".encode()).hexdigest(), return_dtype=pl.String).alias("h"))
    w = w.sort(["ntb", "h"], descending=[True, False])  # largest first, hash breaks ties
    load = [0] * K
    fold = {}
    for b, n in zip(w["block"].to_list(), w["ntb"].to_list(), strict=True):
        k = int(np.argmin(load))
        fold[b] = k + 1
        load[k] += n
    return df.with_columns(pl.col("block").replace_strict(fold, return_dtype=pl.Int8).alias("fold")).sort("Cell")


def splits(m: pl.DataFrame) -> pl.DataFrame:
    rows = []
    for r in m.iter_rows(named=True):
        for s, f in SPLITS.items():
            rows.append(dict(split=s, member=r["member"], gcm=r["gcm"], scen=r["scen"], seed=r["seed"],
                             window=r["window"], build=r["build"], role=f(r)))
    return pl.DataFrame(rows)


def build_all():
    m = members()
    f = folds(tree_bearing(m))
    s = splits(m)
    return m, f, s


def gates(m, f, s):
    g = []
    g.append(("38_member_windows_all_converted", m.height == 38 and bool(m["conversion_ok"].all()),
              f"{m.height} rows, conversion_ok {int(m['conversion_ok'].sum())}"))
    g.append(("every_member_has_a_build", m["build"].null_count() == 0,
              str(m.group_by("build").agg(pl.len()).sort("build").rows())))
    pair = (m.filter(pl.col("gcm") == "GFDL-ESM4").group_by("seed").agg(pl.col("build").n_unique().alias("nb")))
    g.append(("hist_and_ssp_legs_same_build_per_member", bool((pair["nb"] == 1).all()), str(pair.sort("seed").rows())))
    fl = f.filter(pl.col("tree_bearing")).group_by("fold").agg(pl.len().alias("n"), pl.col("is_dev").sum().alias("dev"))
    g.append(("folds_balanced_tree_bearing", bool(fl["n"].max() <= 1.05 * fl["n"].min()),
              str(fl.sort("fold").rows())))
    g.append(("no_rock_cell_tree_bearing", int((f["rock"] & f["tree_bearing"]).sum()) == 0,
              f"{int(f['tree_bearing'].sum())} tree-bearing cells, rock {int(f['rock'].sum())}"))
    roles = s.group_by(["split", "role"]).agg(pl.len()).sort(["split", "role"]).rows()
    g.append(("every_split_has_train_and_test", all(
        any(r[0] == sp and r[1] == x for r in roles) for sp in SPLITS for x in ("train", "test")), str(roles)))
    return [dict(name=n, pass_=bool(p), detail=d) for n, p, d in g]


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    m, f, s = build_all()
    if cmd == "check":
        for name, df in (("members", m), ("folds", f), ("splits", s)):
            disk = pl.read_parquet(os.path.join(OUT, f"{name}.parquet"))
            assert disk.equals(df), f"{name} differs from disk"
        log("check: rebuilt registry frame-equal to disk")
        return
    os.makedirs(OUT, exist_ok=True)
    m.write_parquet(os.path.join(OUT, "members.parquet"))
    f.write_parquet(os.path.join(OUT, "folds.parquet"))
    s.write_parquet(os.path.join(OUT, "splits.parquet"))
    g = gates(m, f, s)
    with open(os.path.join(OUT, "_gates.json"), "w") as fh:
        json.dump(dict(all_pass=all(x["pass_"] for x in g),
                       gates=[{"name": x["name"], "pass": x["pass_"], "detail": x["detail"]} for x in g]), fh, indent=1)
    for x in g:
        log(("PASS " if x["pass_"] else "FAIL ") + x["name"] + " :: " + x["detail"][:600])


if __name__ == "__main__":
    main()
