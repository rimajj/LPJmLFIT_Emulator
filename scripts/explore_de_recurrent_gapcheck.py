"""Line X, Germany emulator design panel (recurrent-memory architect): two cheap data checks.

1. GAP SURVIVORS: are trees alive at the end of 2044 identifiable in 2071 (the 2045-2070 segment has no tree
   table but the runs chain restart_2044 -> 2045-2070 -> restart_2070 -> 2071-2100)? Join the last year of w2015
   with the first year of w2071 on the trait key (Cell, Patch, Type, ID, SLA, Wooddens) and check Age(2071) ==
   Age(2044) + 27 and the four other traits bit-identical. If it holds, every 27-year survival + growth of a
   2044 tree is a supervision target ACROSS the gap.
2. GAP CELL OUTPUTS: dims/time axis of the gridded annual 2045-2070 outputs (agb, vegc, litc, fpc,
   height_mass) so cell-level supervision of the gap can be designed.

Usage: explore_de_recurrent_gapcheck.py [member ...]   (default: three members). Writes JSON to
/p/tmp/jamirp/X_de/recurrent/gapcheck.json.
"""

import json
import os
import sys

import numpy as np
import polars as pl

DEV = "/p/tmp/jamirp/X_de/ind_dev"
OUT = "/p/tmp/jamirp/X_de/recurrent"
RUNS = "/p/projects/waldspektrum/data/LPJmLFIT/productionruns_jamir"
KEY = ["Cell", "Patch", "Type", "ID", "SLAi", "WDi"]


def load_year(member, win, year):
    df = (
        pl.scan_parquet(f"{DEV}/{member}_{win}.parquet")
        .filter((pl.col("Year") == year) & (pl.col("Type") <= 6))
        .collect()
    )
    return df.with_columns(
        SLAi=(pl.col("SLA").cast(pl.Float64) * 1e9).round().cast(pl.Int64),
        WDi=(pl.col("Wooddens").cast(pl.Float64) * 10).round().cast(pl.Int64),
    )


def gap_pair(member):
    a = load_year(member, "w2015", 2044)
    b = load_year(member, "w2071", 2071)
    alive_a = a.filter(pl.col("isdead") == 0)
    res = {"member": member, "n_live_2044": alive_a.height, "n_rows_2071": b.height}
    for nm, d in (("2044", alive_a), ("2071", b)):
        res[f"dup_traitkey_{nm}"] = d.height - d.select(KEY).n_unique()
    j = alive_a.join(b, on=KEY, how="inner", suffix="_b")
    res["n_matched"] = j.height
    res["frac_2044_live_matched"] = j.height / max(1, alive_a.height)
    dage = (j["Age_b"] - j["Age"]).to_numpy()
    res["age_diff_eq_27"] = float(np.mean(np.isclose(dage, 27.0))) if j.height else None
    res["age_diff_hist"] = {
        str(k): int(v) for k, v in zip(*np.unique(np.round(dage, 3), return_counts=True), strict=True)
    } if j.height and len(np.unique(np.round(dage, 3))) < 30 else "many"
    for t in ("D95max", "minwscal", "Longevity", "beta_root"):
        res[f"{t}_identical"] = float((j[t] == j[f"{t}_b"]).mean()) if j.height else None
    # 2071 trees old enough to have been alive in 2044 (Age_2071 >= 27 + entry age ~5) that did NOT match
    old = b.filter(pl.col("Age") >= 40)
    oj = old.join(alive_a.select(KEY), on=KEY, how="anti")
    res["n_2071_age_ge40"] = old.height
    res["n_2071_age_ge40_unmatched"] = oj.height
    # 2044 living stems that survived 27 yr: by height class at 2044
    m = alive_a.join(b.select(KEY).with_columns(pl.lit(1).alias("seen")), on=KEY, how="left")
    m = m.with_columns(pl.col("seen").fill_null(0))
    res["survive27_by_height"] = (
        m.with_columns(hb=(pl.col("Height") // 5 * 5))
        .group_by("hb").agg(pl.len().alias("n"), pl.col("seen").mean().alias("p27"))
        .sort("hb").to_dicts()
    )
    g = j.with_columns(dagb=pl.col("agb_b") - pl.col("agb"), dh=pl.col("Height_b") - pl.col("Height"))
    res["matched_dagb_q"] = [float(x) for x in np.quantile(g["dagb"].to_numpy(), [0.05, 0.5, 0.95])]
    res["matched_dheight_q"] = [float(x) for x in np.quantile(g["dh"].to_numpy(), [0.05, 0.5, 0.95])]
    return res


def nc_dims(gcm, scen, seed):
    import netCDF4

    out = {}
    d = f"{RUNS}/{gcm}/{scen}/random_seed_{seed}/output"
    for v in ("agb", "vegc", "litc", "soilc", "fpc", "height_mass"):
        p = f"{d}/{v}_2070.nc"
        if not os.path.exists(p):
            out[v] = "missing"
            continue
        with netCDF4.Dataset(p) as ds:
            info = {k: len(x) for k, x in ds.dimensions.items()}
            vars_ = {k: (x.dimensions, getattr(x, "units", "")) for k, x in ds.variables.items()}
            t = None
            if "time" in ds.variables:
                tv = ds.variables["time"]
                t = [float(tv[0]), float(tv[-1]), getattr(tv, "units", "")]
            out[v] = {"dims": info, "vars": {k: [list(a), b] for k, (a, b) in vars_.items()}, "time": t}
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    members = sys.argv[1:] or [
        "MPI-ESM1-2-HR_ssp370_s1",
        "ACCESS-CM2_ssp126_s2",
        "ACCESS-CM2_ssp245_s1",
    ]
    res = {"gap_pairs": [], "nc": None}
    for m in members:
        r = gap_pair(m)
        print(json.dumps(r)[:2000], flush=True)
        res["gap_pairs"].append(r)
    res["nc"] = nc_dims("MPI-ESM1-2-HR", "ssp370", 1)
    print(json.dumps(res["nc"])[:3000], flush=True)
    with open(f"{OUT}/gapcheck.json", "w") as f:
        json.dump(res, f, indent=1, default=str)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
