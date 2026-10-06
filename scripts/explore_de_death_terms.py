"""explore_de_death_terms.py — LINE X, Germany emulator: which of the original's four per-tree hazards (growth
efficiency mort_npp, age, water stress, temperature stress) makes its mortality pulse years?
(pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "WHICH of the original's hazards makes the pulses")

Per year and height class (< 10 m, >= 10 m), over all tree rows printed at y (living or flagged dead): mean of
mort_npp, mort_age, mort_water, mort_temp and the `mort` column, plus the death share, and the share of "certain
kills": rows with mort == 1 whose four-term sum is < 1 (the counter >= 5 rule or the leaf_c < sapling leaf carbon
rule, mortality_tree_ind.c:134-140).
Usage:  python explore_de_death_terms.py --cells-from <run dir> --gcm MPI-ESM1-2-HR --seed 2 [--leg ssp370] [--tag mpi2]
Writes /p/tmp/jamirp/X_de/shared/eval/death_terms_<tag>.csv
"""

from __future__ import annotations

import argparse
import glob
import os

import polars as pl

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
TERMS = ["mort_npp", "mort_age", "mort_water", "mort_temp", "mort"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells-from", required=True)
    ap.add_argument("--gcm", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--leg", default="ssp370")
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    f0 = sorted(glob.glob(os.path.join(a.cells_from, "chunk_*", "y1986_*.parquet")))
    cells = sorted(pl.concat([pl.scan_parquet(f).select("Cell") for f in f0]).unique().collect()["Cell"].to_list())
    m = pl.read_parquet(os.path.join(XDE, "shared", "registry", "members.parquet")).filter(
        (pl.col("gcm") == a.gcm) & (pl.col("seed") == a.seed) & ~pl.col("excluded")
        & pl.col("scen").is_in(["Historical", a.leg]))
    lf = pl.concat([pl.scan_parquet(p).select("Year", "Cell", "Type", "Height", "isdead", *TERMS)
                    for p in m["ind_dev_path"].to_list()], how="vertical_relaxed")
    R = (lf.filter(pl.col("Cell").is_in(cells) & (pl.col("Type") <= 6) & (pl.col("Year") > 1985))
         .with_columns(hcls=pl.when(pl.col("Height") < 10.0).then(pl.lit("lt10")).otherwise(pl.lit("ge10")))
         .with_columns(sum4=pl.sum_horizontal([pl.col(t).cast(pl.Float64) for t in TERMS[:4]]))
         .with_columns(certain=(pl.col("mort") >= 0.9999) & (pl.col("sum4") < 0.9999))
         .group_by("Year", "hcls").agg(n=pl.len(), dead=pl.col("isdead").cast(pl.Float64).mean(),
                                       **{t: pl.col(t).cast(pl.Float64).mean() for t in TERMS},
                                       certain=pl.col("certain").cast(pl.Float64).mean(),
                                       dead_certain=(pl.col("certain") & (pl.col("isdead") == 1)).cast(pl.Float64)
                                       .mean(),
                                       dead_uncertain=(~pl.col("certain") & (pl.col("isdead") == 1))
                                       .cast(pl.Float64).mean())
         .sort("Year", "hcls").collect())
    out = os.path.join(XDE, "shared", "eval", f"death_terms_{a.tag}.csv")
    R.write_csv(out)
    pl.Config.set_tbl_rows(200)
    pl.Config.set_tbl_cols(20)
    pl.Config.set_tbl_width_chars(200)
    print(R.with_columns(pl.col(pl.Float64).round(5)))
    print("wrote", out, f"({len(cells)} cells)")


if __name__ == "__main__":
    main()
