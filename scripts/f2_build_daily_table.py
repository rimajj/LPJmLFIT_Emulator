#!/usr/bin/env python3
"""Build the phase-A arrays for the learned daily water-carbon model (ADR 0320).

For every panel member m1-m4 and every constant-CO2 leg with daily output (ctl_obs,
mpi-esm1-2-hr_ssp126/370/585, ukesm1-0-ll_ssp370) this writes, under OUT
(default /p/projects/open/Jamir/esm_land_emulator_data/f2):

  cells.parquet         Cell, block, lat, heldout (ADR 0320 section 4), biome name or ""
  forc_m<k>_<leg>.npy   (ncell, 82*365, 5) float32 tas pr rsds lwnet huss, days of 2019..2100;
                        2019 = the observed weather the original saw before 2020, for every leg
  daily_m<k>_<leg>.npy  (ncell, 81*365, 10) float32 DAILY_VARS, days of 2020..2100 (per day)
  stand_m<k>_<leg>.npy  (ncell, 82, 12) float32 lai_stand vegc fpc_stand[1..10] at the END of
                        years 2019..2100 (2019 from the same member's hist leg)
  cap_m<k>_<leg>.npy    (ncell, 82) float32 top-metre capacity sum_{l<3} whc_nat*dz (year mean)
  manifest.json         gates + the recovered ctl_obs year sequence per member

Gates (FATAL): every (cell, year, day) present; the leg's daily prec output equals the forcing
to 1e-3 mm at every cell and day (proves the forcing join and the ctl_obs year sequence).

Usage: python scripts/f2_build_daily_table.py [--members 1,2,3,4] [--legs ...]
(SLURM: ~16 cpus, ~100 GB)
"""

import argparse
import json
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
from build_transient_boundary import open_clm  # noqa: E402

PANEL = "/p/projects/open/Jamir/esm_land_emulator_data/trackD/panel"
INPUTS = "/p/tmp/jamirp/trackD/panel/inputs"
BLOCKS = os.path.join(REPO, "test/testitems/references/S_D0_panel_blocks.csv")
LEGS = [
    "ctl_obs",
    "mpi-esm1-2-hr_ssp126",
    "mpi-esm1-2-hr_ssp370",
    "mpi-esm1-2-hr_ssp585",
    "ukesm1-0-ll_ssp370",
]
FORC_VARS = ["temp", "prec", "swdown", "lwnet", "humid"]  # config keys -> tas pr rsds lwnet huss
DAILY_VARS = ["prec", "transp", "evap", "interc", "runoff", "swe", "rootmoist", "pet", "npp", "gpp"]
Y0, Y1 = 2020, 2100
NY = Y1 - Y0 + 1
DZ = {0: 200.0, 1: 300.0, 2: 500.0}


def leg_forcing_paths(leg):
    """config key -> .clm path, from the leg's own input include (what the run read)."""
    paths = {}
    with open(os.path.join(INPUTS, f"{leg}.js")) as f:
        for line in f:
            for k in FORC_VARS:
                tag = f'"{k}"'
                if line.strip().startswith(tag):
                    paths[k] = line.split('"name"')[1].split('"')[1]
    missing = [k for k in FORC_VARS if k not in paths]
    if missing:
        raise SystemExit(f"FATAL: {leg}.js lacks {missing}")
    return paths


def heldout_blocks(blocks):
    """ADR 0320 §4: the biome blocks + the lowest non-biome block of each stratum with >= 2."""
    ho = set(blocks.filter(pl.col("reason").str.starts_with("biome:"))["block"].to_list())
    for (_s,), g in blocks.group_by(["stratum"]):
        if g.height < 2:
            continue
        nb = g.filter(~pl.col("reason").str.starts_with("biome:")).sort("block")
        if nb.height:
            ho.add(int(nb["block"][0]))
    return ho


def read_years(mm, fy, scalar, years, cells):
    """(ncell, len(years)*365) float32 physical values for calendar years of a .clm memmap."""
    out = np.empty((len(cells), len(years) * 365), dtype=np.float32)
    for i, y in enumerate(years):
        out[:, i * 365 : (i + 1) * 365] = np.asarray(mm[y - fy][cells], dtype=np.float32) * scalar
    return out


def recover_shuffle(prec_out, obs_mm, obs_fy, obs_sc, cells):
    """ctl_obs: per simulated year, the observed year 1990-2019 whose daily prec matches."""
    cand = list(range(1990, 2020))
    obs = {y: np.asarray(obs_mm[y - obs_fy][cells], dtype=np.float32) * obs_sc for y in cand}
    seq = []
    for iy in range(NY):
        o = prec_out[:, iy * 365 : (iy + 1) * 365]
        err = [float(np.abs(o - obs[y]).max()) for y in cand]
        k = int(np.argmin(err))
        if err[k] > 1e-3:
            raise SystemExit(
                f"FATAL: ctl_obs {Y0 + iy}: no observed year matches ({cand[k]} err {err[k]})"
            )
        seq.append(cand[k])
    return seq


def stand_of(legdir, years, cells, tag):
    """(ncell, len(years), 12) lai_stand, vegc, fpc_stand[1..10] at the END of each year."""
    nc = len(cells)
    an = pl.read_parquet(os.path.join(legdir, "annual.parquet")).filter(pl.col("Year").is_in(years))
    fp = (
        pl.read_parquet(os.path.join(legdir, "fpc_stand.parquet"))
        .filter(pl.col("Year").is_in(years) & (pl.col("pft") >= 1))
        .pivot(on="pft", index=["Cell", "Year"], values="fpc_stand")
    )
    j = an.join(fp, on=["Cell", "Year"], how="inner").filter(pl.col("Cell").is_in(cells.tolist()))
    j = j.sort(["Cell", "Year"])
    cols = ["lai_stand", "vegc"] + [str(p) for p in range(1, 11)]
    if j.height != nc * len(years):
        raise SystemExit(f"FATAL {tag}: stand rows {j.height} != {nc}*{len(years)} in {legdir}")
    return j.select(cols).to_numpy().reshape(nc, len(years), len(cols)).astype(np.float32)


def cap_of(legdir, years, cells, tag):
    """(ncell, len(years)) year-mean top-metre capacity sum_{l<3} whc_nat[l]*dz[l] in mm."""
    nc = len(cells)
    m = pl.read_parquet(os.path.join(legdir, "monthly.parquet")).filter(
        pl.col("Year").is_in(years) & (pl.col("layer") < 3) & pl.col("Cell").is_in(cells.tolist())
    )
    dz = pl.col("layer").replace_strict(DZ, return_dtype=pl.Float64)
    m = m.with_columns(w=pl.col("whc_nat") * dz)
    c = m.group_by(["Cell", "Year", "Month"]).agg(pl.col("w").sum())
    c = c.group_by(["Cell", "Year"]).agg(pl.col("w").mean()).sort(["Cell", "Year"])
    if c.height != nc * len(years):
        raise SystemExit(f"FATAL {tag}: cap rows {c.height}")
    return c["w"].to_numpy().reshape(nc, len(years)).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--members", default="1,2,3,4")
    ap.add_argument("--legs", default=",".join(LEGS))
    ap.add_argument(
        "--out", default=os.environ.get("OUT", "/p/projects/open/Jamir/esm_land_emulator_data/f2")
    )
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    blocks = pl.read_csv(BLOCKS)
    ho = heldout_blocks(blocks)
    rows = []
    for r in blocks.sort("block").iter_rows(named=True):
        biome = r["reason"].split(":", 1)[1] if r["reason"].startswith("biome:") else ""
        for c in range(r["start"], r["end"] + 1):
            rows.append(
                {
                    "Cell": c,
                    "block": r["block"],
                    "lat": r["lat"],
                    "heldout": r["block"] in ho,
                    "biome": biome,
                }
            )
    cells_df = pl.DataFrame(rows)
    cells_df.write_parquet(os.path.join(a.out, "cells.parquet"))
    cells = cells_df["Cell"].to_numpy()
    nc = len(cells)
    print(f"== {nc} cells, {len(ho)} held-out blocks: {sorted(ho)}", flush=True)

    hist_paths = leg_forcing_paths("hist")
    hist_mm = {k: open_clm(p) for k, p in hist_paths.items()}
    # 2019 warm-up weather = what the original saw (observed), the same for every leg
    f2019 = np.stack(
        [read_years(m[0], m[1], m[4], [2019], cells) for m in (hist_mm[k] for k in FORC_VARS)], -1
    )

    manifest_path = os.path.join(a.out, "manifest.json")
    manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {}
    manifest["heldout_blocks"] = sorted(int(b) for b in ho)

    for leg in a.legs.split(","):
        paths = leg_forcing_paths(leg)
        mms = {k: open_clm(p) for k, p in paths.items()}
        for k in (int(x) for x in a.members.split(",")):
            t0 = time.time()
            tag = f"m{k}_{leg}"
            d = pl.read_parquet(os.path.join(PANEL, f"m{k}", leg, "daily.parquet"))
            d = d.filter(pl.col("Cell").is_in(cells.tolist())).sort(["Cell", "Year", "Day"])
            if d.height != nc * NY * 365:
                raise SystemExit(f"FATAL {tag}: {d.height} daily rows != {nc}*{NY}*365")
            chk = d.select(pl.col("Cell").unique().sort()).to_series().to_numpy()
            if not np.array_equal(chk, np.sort(cells)):
                raise SystemExit(f"FATAL {tag}: cell set mismatch")
            # rows sort by Cell; cells.parquet must be in the same (ascending) order
            if not np.array_equal(np.sort(cells), cells):
                raise SystemExit("FATAL: cells.parquet order is not ascending Cell")
            daily = np.stack(
                [d[v].to_numpy().reshape(nc, NY * 365) for v in DAILY_VARS], -1
            ).astype(np.float32)

            # forcing 2020..2100
            if leg == "ctl_obs":
                seq = recover_shuffle(
                    daily[:, :, 0], *hist_mm["prec"][:2], hist_mm["prec"][4], cells
                )
                manifest.setdefault("ctl_obs_years", {})[f"m{k}"] = seq
                fut = np.stack(
                    [
                        read_years(m[0], m[1], m[4], seq, cells)
                        for m in (hist_mm[v] for v in FORC_VARS)
                    ],
                    -1,
                )
            else:
                fut = np.stack(
                    [
                        read_years(m[0], m[1], m[4], range(Y0, Y1 + 1), cells)
                        for m in (mms[v] for v in FORC_VARS)
                    ],
                    -1,
                )
            perr = float(np.abs(fut[:, :, 1] - daily[:, :, 0]).max())
            if perr > 1e-3:
                raise SystemExit(f"FATAL {tag}: forcing prec != output prec (max {perr})")
            forc = np.concatenate([f2019, fut], axis=1)

            # stand and capacity at END of each year 2019..2100
            hdir = os.path.join(PANEL, f"m{k}", "hist")
            ldir = os.path.join(PANEL, f"m{k}", leg)
            yrs = list(range(Y0, Y1 + 1))
            stand = np.concatenate(
                [stand_of(hdir, [2019], cells, tag), stand_of(ldir, yrs, cells, tag)], 1
            )
            cap = np.concatenate(
                [cap_of(hdir, [2019], cells, tag), cap_of(ldir, yrs, cells, tag)], 1
            )
            rm_over = float((daily[:, :, 6] / np.repeat(cap[:, 1:], 365, axis=1)).max())

            np.save(os.path.join(a.out, f"forc_{tag}.npy"), forc)
            np.save(os.path.join(a.out, f"daily_{tag}.npy"), daily)
            np.save(os.path.join(a.out, f"stand_{tag}.npy"), stand)
            np.save(os.path.join(a.out, f"cap_{tag}.npy"), cap)
            manifest.setdefault("gates", {})[tag] = {
                "prec_maxabs": perr,
                "rootmoist_over_cap_max": rm_over,
                "finite": bool(
                    np.isfinite(daily).all()
                    and np.isfinite(forc).all()
                    and np.isfinite(stand).all()
                ),
            }
            print(
                f"== {tag}: prec {perr:.2e}, rootmoist/cap {rm_over:.4f}, {time.time() - t0:.0f}s",
                flush=True,
            )
            with open(manifest_path, "w") as f:
                json.dump(manifest, f, indent=1)
    print("== DONE", flush=True)


if __name__ == "__main__":
    main()
