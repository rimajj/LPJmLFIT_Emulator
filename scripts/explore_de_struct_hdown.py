"""explore_de_struct_hdown.py — LINE X, Germany emulator, STRUCT track: does the original model's
height follow agb DOWN? (pre-registration /p/tmp/jamirp/X_de/_status/SD.md, H2b)

On consecutive-year pairs of living printed trees (same key, Type <= 6) of the original model (and,
for comparison, of any run given with --arms label@<run dir>), split by the sign of the agb change
(dlagb < -0.01 / |dlagb| <= 0.01 / > 0.01) and the height bin at y: share with dH < -0.01 m, mean
dH, mean change of the allometric residual ln H - ln Hhat(agb) of the STRUCT stepper's allometry.

Usage:  python explore_de_struct_hdown.py [--ncells 200] [--arms label@dir,...]
Writes /p/tmp/jamirp/X_de/shared/eval/struct_hdown.csv
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_struct_stemloss as sl  # noqa: E402

KEY = ["Cell", "Patch", "Type", "ID", "SLA", "Wooddens"]


def pairs(D: pl.DataFrame, src: str, coef) -> pl.DataFrame:
    D = D.filter(pl.col("isdead") == 0)
    hh = sl.st.rl.predict_height(
        D["agb"].to_numpy(),
        D["Wooddens"].to_numpy(),
        D["SLA"].to_numpy(),
        D["Type"].to_numpy(),
        coef,
    )
    D = D.with_columns(
        res=pl.Series(np.log(D["Height"].to_numpy().astype(np.float64)) - np.log(hh))
    )
    a = D.select(KEY + ["Year", "Height", "agb", "res"])
    b = a.with_columns(pl.col("Year") - 1)
    j = a.join(b, on=KEY + ["Year"], suffix="_1").with_columns(
        dl=(pl.col("agb_1") / pl.col("agb")).log(),
        dH=pl.col("Height_1") - pl.col("Height"),
        dres=pl.col("res_1") - pl.col("res"),
    )
    j = j.with_columns(
        dlc=pl.when(pl.col("dl") < -0.01)
        .then(pl.lit("agb_down"))
        .when(pl.col("dl") > 0.01)
        .then(pl.lit("agb_up"))
        .otherwise(pl.lit("agb_flat")),
        hb=pl.col("Height")
        .cut([6.0, 10.0, 15.0], labels=["5-6", "6-10", "10-15", "ge15"])
        .cast(pl.Utf8),
    )
    return (
        j.group_by("dlc", "hb")
        .agg(
            n=pl.len(),
            share_Hdown=(pl.col("dH") < -0.01).mean(),
            dH_mean=pl.col("dH").mean(),
            dres_mean=pl.col("dres").mean(),
            dl_mean=pl.col("dl").mean(),
        )
        .with_columns(src=pl.lit(src))
        .sort("dlc", "hb")
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ncells", type=int, default=200)
    ap.add_argument("--arms", default="")
    a = ap.parse_args()
    cells = sorted(sl.st.hd.folds()["Cell"].to_list())[: a.ncells]
    coef = sl.st.full_allometry("DEV-A")
    out = [pairs(sl.truth_frame(cells, "ssp370"), "truth", coef)]
    for arm in [x for x in a.arms.split(",") if x]:
        D, _ = sl.arm_frame(arm, "ssp370", cells, a.ncells)
        out.append(pairs(D, arm.split("@")[0], coef))
    res = pl.concat(out)
    p = os.path.join(sl.XDE, "shared", "eval", "struct_hdown.csv")
    res.write_csv(p)
    pl.Config.set_tbl_rows(60)
    print(res.with_columns(pl.selectors.float().round(4)))
    print("wrote", p)


if __name__ == "__main__":
    main()
