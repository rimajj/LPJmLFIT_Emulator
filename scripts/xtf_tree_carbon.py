#!/usr/bin/env python3
"""xtf_tree_carbon.py -- ADR 0368 section 2b (SEPARATE EXPERIMENT): the year's cell carbon balance as an input to the
tree-death models, from the original (bound) and from the emulator's own free-running daily model (deployable).

Reads xtf/daily/runs/B_s<0..4>/annual.npz (free runs of the deployed clustered daily network NC_s0-4 on members 2
and 3 of every leg with a second run, xtf_daily.py run --arm B). Writes xtf/treemort/carbon.parquet:
  seed (= member), gcm, ssp, Cell, Year 2021..2100,
  {npp,gpp}_{true,emu}       the year's annual total (emu = mean of the five networks' free runs)
  {npp,gpp}_{true,emu}_anom  minus the mean of the previous 5 years (fewer at the start of the run), divided by the
                             cell's 2021-2100 mean |value| (>= 10 gC m-2 yr-1)

ADR 0369: `xtf_tree_carbon.py <arm> <seeds> <tag>` (e.g. `MEP 0,1,2 mep`) writes the same for another daily arm
(mean of its seeds' free runs) as xtf/treemort/carbon_<tag>.parquet with columns {npp,gpp}_<tag>[_anom] only;
xtf_tree_models.py joins it for the arms registered with XTF_DAILY_TAGS=<tag>.
"""

import os
import sys

import numpy as np
import polars as pl

RUNS = "/p/projects/open/Jamir/esm_land_emulator_data/xtf/daily/runs"
OUT = "/p/projects/open/Jamir/esm_land_emulator_data/xtf/treemort/carbon.parquet"
SSPS = ("ssp126", "ssp370", "ssp585")


def anom(x):
    """x (nc, 81 years 2020..2100) -> (nc, 80) for 2021..2100."""
    out = np.empty((x.shape[0], 80))
    for j in range(1, 81):
        out[:, j - 1] = x[:, j] - x[:, max(0, j - 5) : j].mean(1)
    return out / np.maximum(np.abs(x[:, 1:]).mean(1, keepdims=True), 10.0)


def main():
    if len(sys.argv) > 1:
        return other(sys.argv[1], [int(x) for x in sys.argv[2].split(",")], sys.argv[3])
    zs = [np.load(f"{RUNS}/B_s{i}/annual.npz") for i in range(5)]
    legs = sorted({k.split("__")[2] for k in zs[0].files})
    rows = []
    for leg in legs:
        gcm, ssp = leg.rsplit("_", 1)
        if ssp not in SSPS:
            continue
        for k in (2, 3):
            cols = {}
            for v in ("npp", "gpp"):
                t = zs[0][f"truth__m{k}__{leg}__{v}"].astype(np.float64)
                e = np.mean([z[f"free__m{k}__{leg}__{v}"] for z in zs], 0).astype(np.float64)
                cols[f"{v}_true"], cols[f"{v}_emu"] = t[:, 1:], e[:, 1:]
                cols[f"{v}_true_anom"], cols[f"{v}_emu_anom"] = anom(t), anom(e)
            nc = t.shape[0]
            rows.append(pl.DataFrame({
                "seed": np.full(nc * 80, k, np.int32), "gcm": [gcm] * (nc * 80), "ssp": [ssp] * (nc * 80),
                "Cell": np.repeat(np.arange(nc, dtype=np.int32), 80),
                "Year": np.tile(np.arange(2021, 2101, dtype=np.int32), nc),
                **{c: a.reshape(-1).astype(np.float32) for c, a in cols.items()}}))  # fmt: skip
    d = pl.concat(rows)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    d.write_parquet(OUT)
    r = np.corrcoef(d["npp_true_anom"].to_numpy(), d["npp_emu_anom"].to_numpy())[0, 1]
    print(f"{d.height:,} cell-years, {len(rows)} member-legs; NPP anomaly r(true, emulated) = {r:.3f}")




def other(arm, seeds, tag):
    zs = [np.load(f"{RUNS}/{arm}_s{i}/annual.npz") for i in seeds]
    legs = sorted({k.split("__")[2] for k in zs[0].files if k.startswith("free__")})
    rows, rr = [], []
    for leg in legs:
        gcm, ssp = leg.rsplit("_", 1)
        if ssp not in SSPS:
            continue
        for k in (2, 3):
            cols = {}
            for v in ("npp", "gpp"):
                e = np.mean([z[f"free__m{k}__{leg}__{v}"] for z in zs], 0).astype(np.float64)
                cols[f"{v}_{tag}"], cols[f"{v}_{tag}_anom"] = e[:, 1:], anom(e)
            t = zs[0][f"truth__m{k}__{leg}__npp"].astype(np.float64)
            rr.append((anom(t).ravel(), cols[f"npp_{tag}_anom"].ravel()))
            nc = e.shape[0]
            rows.append(pl.DataFrame({
                "seed": np.full(nc * 80, k, np.int32), "gcm": [gcm] * (nc * 80), "ssp": [ssp] * (nc * 80),
                "Cell": np.repeat(np.arange(nc, dtype=np.int32), 80),
                "Year": np.tile(np.arange(2021, 2101, dtype=np.int32), nc),
                **{c: a.reshape(-1).astype(np.float32) for c, a in cols.items()}}))  # fmt: skip
    d = pl.concat(rows)
    out = OUT.replace("carbon.parquet", f"carbon_{tag}.parquet")
    d.write_parquet(out)
    a, b = np.concatenate([x for x, _ in rr]), np.concatenate([y for _, y in rr])
    print(f"{out}: {d.height:,} cell-years, {len(rows)} member-legs; NPP anomaly r(true, {arm}) = "
          f"{np.corrcoef(a, b)[0, 1]:.3f}")


if __name__ == "__main__":
    main()
