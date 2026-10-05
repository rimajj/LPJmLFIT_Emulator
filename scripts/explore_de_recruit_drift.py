"""explore_de_recruit_drift.py — LINE X, Germany emulator: why do the free runs recruit too many trees?

Read-only probe over free-run rosters already on disk (runs/<arm>/<run>/chunk_*/y*.parquet) and the original model's
own `ind` table for the same cells and years. Per (source, year) it reports, Germany-wide over the chosen cells:

  stems/patch            living printed trees per patch at y
  new/patch              trees printed at y whose (Cell, Patch, Type, ID) was not printed at y-1 (the eval's definition)
    split into           FIRST appearance of the key in the whole run so far  vs  RE-ENTRY (key printed in an earlier
                         year, absent at y-1: a tree that dropped below 5 m and came back)
  exit_hidden/patch      trees living and printed at y-1, not flagged dead, not printed at y (dropped below 5 m)
  fpc/patch, fpc/stem    sum and mean fpc_ind of living printed trees; agb/stem; lai*fpc per patch
  new_age_med, new_h_med age and height of first appearances
  surv_*                 growth of survivors (living printed at y-1 and y): relative change of summed agb / fpc, and the
                         median per-stem log agb ratio overall and for stems below / above 15 m at y-1
  dead_*                 who dies: agb / fpc lost per patch (sized at y-1), mean dying agb over mean living agb at y-1,
                         median height of the dying vs of all living at y-1

Hypotheses this separates (stated before running):
  H1  re-entry inflation: the arm's "excess recruits" are threshold flicker of its own noisy growth, not births.
      Predicts arm re-entry/patch >> truth re-entry/patch, and first-appearance/patch close to truth.
  H2  open-canopy feedback: arm stands carry less cover per stem (smaller trees), the recruit model sees an open
      canopy and over-recruits. Predicts arm fpc/patch below truth while stems/patch is above, with the gap growing.
  H3  neither: first appearances genuinely excessive at matched cover -> the recruit head itself (or its draw).

Usage:  python explore_de_recruit_drift.py [--chunks 0,1] [--leg ssp370] [--arms tabAL,tabAk0,struct_noacc] [--tag _x]
        an arm may be given as label@<run dir> (a run outside runs/<arm>/<RUN>, e.g. a counterfactual)
Writes /p/tmp/jamirp/X_de/shared/eval/recruit_drift_<leg>.csv and prints a compact table.
"""

from __future__ import annotations

import argparse
import glob
import os

import polars as pl

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
RUN = "ACCESS-CM2_s1_1985-2044_ssp126+ssp245+ssp370_actual_r1"
KEY = ["Cell", "Patch", "Type", "ID"]
COLS = ["Year", "Cell", "Patch", "Type", "ID", "isdead", "Height", "fpc_ind", "agb", "LAI", "Age"]


def arm_frame(arm: str, chunks: list[int], leg: str, cells: list[int] | None) -> tuple[pl.DataFrame, list[int]]:
    """The first arm fixes the cell set from its chunks; later arms (whose chunking may differ) read every chunk and
    keep exactly those cells."""
    fs = []
    base = arm.split("@", 1)[1] if "@" in arm else os.path.join(XDE, "runs", arm, RUN)
    for c in (chunks if cells is None else range(1000)):
        d = os.path.join(base, f"chunk_{c:03d}")
        fs += sorted(glob.glob(os.path.join(d, "*_Historical.parquet"))) + sorted(
            glob.glob(os.path.join(d, f"*_{leg}.parquet")))
    lf = pl.concat([pl.scan_parquet(f).select(COLS) for f in fs], how="vertical_relaxed")
    if cells is not None:
        lf = lf.filter(pl.col("Cell").is_in(cells))
    D = lf.collect()
    return D, sorted(D["Cell"].unique().to_list())


def truth_frame(cells: list[int], leg: str, y0: int, y1: int, gcm: str = "ACCESS-CM2", seed: int = 1) -> pl.DataFrame:
    m = pl.read_parquet(os.path.join(XDE, "shared", "registry", "members.parquet")).filter(
        (pl.col("gcm") == gcm) & (pl.col("seed") == seed) & ~pl.col("excluded")
        & pl.col("scen").is_in(["Historical", leg]))
    parts = [pl.scan_parquet(p).select(COLS) for p in m["ind_dev_path"].to_list()]
    return (pl.concat(parts, how="vertical_relaxed")
            .filter(pl.col("Cell").is_in(cells) & pl.col("Year").is_between(y0, y1)).collect())


def yearly(D: pl.DataFrame, npatch: int, src: str) -> pl.DataFrame:
    D = D.filter(pl.col("Type") <= 6)
    ncell = D["Cell"].n_unique()
    npt = ncell * npatch
    years = sorted(D["Year"].unique().to_list())
    seen = D.filter(pl.col("Year") == years[0]).select(KEY).unique()
    prev = D.filter(pl.col("Year") == years[0])
    out = []
    for y in years[1:]:
        cur = D.filter(pl.col("Year") == y)
        new = cur.join(prev.select(KEY), on=KEY, how="anti")
        first = new.join(seen, on=KEY, how="anti")
        live_prev = prev.filter(pl.col("isdead") == 0)
        exit_h = live_prev.join(cur.select(KEY), on=KEY, how="anti")
        live = cur.filter(pl.col("isdead") == 0)
        # survivor growth: trees living at y-1 and printed living at y (same key)
        sv = live_prev.select(*KEY, a0="agb", f0="fpc_ind", h0="Height").join(
            live.select(*KEY, a1="agb", f1="fpc_ind"), on=KEY, how="inner")
        lr = (sv["a1"] / sv["a0"]).log()
        small = sv["h0"] < 15.0
        # who dies: trees flagged dead at y, sized at their y-1 (living) value
        dy = cur.filter(pl.col("isdead") == 1).select(KEY).join(
            live_prev.select(*KEY, "agb", "fpc_ind", "Height"), on=KEY, how="inner")
        mean_agb_prev = float(live_prev["agb"].mean())
        out.append({
            "src": src, "Year": y,
            "stems_pp": live.height / npt,
            "new_pp": new.height / npt,
            "first_pp": first.height / npt,
            "reentry_pp": (new.height - first.height) / npt,
            "exit_hidden_pp": exit_h.height / npt,
            "dead_pp": cur.filter(pl.col("isdead") == 1).height / npt,
            "fpc_pp": float(live["fpc_ind"].sum()) / npt,
            "fpc_per_stem": float(live["fpc_ind"].mean()) if live.height else None,
            "agb_per_stem": float(live["agb"].mean()) if live.height else None,
            "laifpc_pp": float((live["LAI"] * live["fpc_ind"]).sum()) / npt,
            "surv_dagb_sum": float(sv["a1"].sum() / sv["a0"].sum() - 1.0),
            "surv_dfpc_sum": float(sv["f1"].sum() / sv["f0"].sum() - 1.0),
            "surv_dlnagb_med": float(lr.median()),
            "surv_dlnagb_med_lt15m": float(lr.filter(small).median()),
            "surv_dlnagb_med_ge15m": float(lr.filter(~small).median()),
            "dead_agb_pp": float(dy["agb"].sum()) / npt,
            "dead_fpc_pp": float(dy["fpc_ind"].sum()) / npt,
            "dead_agb_rel": float(dy["agb"].mean()) / mean_agb_prev if dy.height else None,
            "dead_h_med": float(dy["Height"].median()) if dy.height else None,
            "live_h_med_prev": float(live_prev["Height"].median()),
            "stand_agb_pp": float(live["agb"].sum()) / npt,
            "first_age_med": float(first["Age"].median()) if first.height else None,
            "first_h_med": float(first["Height"].median()) if first.height else None,
        })
        seen = pl.concat([seen, first.select(KEY)])
        prev = cur
    return pl.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", default="0,1")
    ap.add_argument("--leg", default="ssp370")
    ap.add_argument("--arms", default="tabAL,tabAk0,struct_noacc")
    ap.add_argument("--npatch", type=int, default=250)
    ap.add_argument("--tag", default="", help="suffix of the output csv")
    ap.add_argument("--gcm", default="ACCESS-CM2", help="the truth member (must match the arms' runs)")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    chunks = [int(c) for c in a.chunks.split(",")]
    res, cells = [], None
    for arm in a.arms.split(","):
        D, c = arm_frame(arm, chunks, a.leg, cells)
        cells = cells or c
        assert c == cells, f"{arm}: cell set differs"
        print(f"{arm}: {D.height} rows, {len(c)} cells, min printed height {D['Height'].min():.3f}", flush=True)
        res.append(yearly(D, a.npatch, arm.split("@", 1)[0]))
    T = truth_frame(cells, a.leg, int(res[0]["Year"].min()) - 1, int(res[0]["Year"].max()), a.gcm, a.seed)
    print(f"truth: {T.height} rows", flush=True)
    res.append(yearly(T, a.npatch, "truth"))
    R = pl.concat(res, how="diagonal_relaxed")
    out = os.path.join(XDE, "shared", "eval", f"recruit_drift_{a.leg}{a.tag}.csv")
    R.write_csv(out)
    pl.Config.set_tbl_rows(200)
    pl.Config.set_tbl_cols(20)
    pl.Config.set_tbl_width_chars(250)
    W = (R.with_columns(win=(pl.col("Year") - 1986) // 10)
         .group_by("src", "win").agg(pl.col("Year").min().alias("y0"), pl.exclude("Year", "src").mean())
         .sort("win", "src"))
    print(W.drop("win").with_columns(pl.exclude("src", "y0").round(4)))
    print("wrote", out)


if __name__ == "__main__":
    main()
