"""explore_de_death_certain_dump.py — LINE X, Germany emulator: how often does a coupled free run's own certain-kill
rule fire (bad-growth counter c1 >= cmax => p_death = 1), per year and height class? Compare with the original's
certain kills (explore_de_death_terms.py, column `certain`).

Reads a probe dump (<dump>/<traj>/y<Y>_c<first cell>.parquet; one row per printed living tree at Y with its drawn
transition to Y+1). Usage:  python explore_de_death_certain_dump.py --dump <dir> --tag gqs_mpi2 [--cmax 5]
Writes /p/tmp/jamirp/X_de/shared/eval/death_certain_<tag>.csv  (year = Y+1, the year the death is printed)
"""

from __future__ import annotations

import argparse
import glob
import os

import polars as pl

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--cmax", type=int, default=5)
    a = ap.parse_args()
    fs = sorted(glob.glob(os.path.join(a.dump, "*", "*.parquet")))
    R = (pl.concat([pl.scan_parquet(f).select("Year", "Type", "Height", "c1", "p_death", "G1") for f in fs])
         .filter(pl.col("Type") <= 6)
         .with_columns(hcls=pl.when(pl.col("Height") < 10.0).then(pl.lit("lt10")).otherwise(pl.lit("ge10")),
                       year=pl.col("Year") + 1)
         .group_by("year", "hcls").agg(n=pl.len(), certain=(pl.col("c1") >= a.cmax).cast(pl.Float64).mean(),
                                       p1=(pl.col("p_death") >= 0.9999).cast(pl.Float64).mean(),
                                       p_death=pl.col("p_death").cast(pl.Float64).mean(),
                                       gneg=(pl.col("G1") < 0).cast(pl.Float64).mean())
         .sort("year", "hcls").collect())
    out = os.path.join(XDE, "shared", "eval", f"death_certain_{a.tag}.csv")
    R.write_csv(out)
    pl.Config.set_tbl_rows(200)
    print(R.with_columns(pl.col(pl.Float64).round(4)))
    print("wrote", out)


if __name__ == "__main__":
    main()
