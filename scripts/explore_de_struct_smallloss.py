"""explore_de_struct_smallloss.py — LINE X, Germany emulator, STRUCT track: why are 5-6 m trees
lost twice as often as in the original? (pre-registration /p/tmp/jamirp/X_de/_status/SD.md, H9)

On trees printed and living at y with 5 <= Height < --hmax m, per (source, window, type group, age
group): share of these stems, bad-growth counter prevalence (c >= 1, c >= 3), share with NEGATIVE
growth efficiency at y+1, loss rate at y+1 (flagged dead, or alive but not printed), and the loss
rate split dead / exit.
  original: the SH3 transition table of the member (c_y, G_y1, fate_y1)
  arms:     StructSD dumps (G1, dead_*, hidden1) + the run's roster (c at y)
Usage:  python explore_de_struct_smallloss.py --dump "label=<dump dir>|<run dir>[,...]"
Writes /p/tmp/jamirp/X_de/shared/eval/struct_smallloss.csv
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_struct_heads as hd  # noqa: E402

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
KEY = ["Cell", "Patch", "Type", "ID"]


def groups(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        tg=pl.when(pl.col("Type") == 3)
        .then(pl.lit("beech"))
        .when(pl.col("Type").is_in([1, 2, 5]))
        .then(pl.lit("t125"))
        .otherwise(pl.lit("t046")),
        ag=pl.when(pl.col("Age") <= 15).then(pl.lit("le15")).otherwise(pl.lit("gt15")),
        win=pl.when(pl.col("Year") < 1995)
        .then(pl.lit("1985-94"))
        .when(pl.col("Year") < 2015)
        .then(pl.lit("1995-2014"))
        .otherwise(pl.lit("2015-43")),
    )


def summ(df: pl.DataFrame, src: str) -> pl.DataFrame:
    df = groups(df)
    tot = df.group_by("win").agg(N=pl.len())
    return (
        df.group_by("win", "tg", "ag")
        .agg(
            n=pl.len(),
            c_ge1=(pl.col("c") >= 1).mean(),
            c_ge3=(pl.col("c") >= 3).mean(),
            g_neg=(pl.col("gneg")).mean(),
            head_pGneg=pl.col("p_gneg").mean() if "p_gneg" in df.columns else pl.lit(None),
            loss=(pl.col("dead") | pl.col("exit")).mean(),
            dead=pl.col("dead").mean(),
            exit=pl.col("exit").mean(),
        )
        .join(tot, on="win")
        .with_columns(share=pl.col("n") / pl.col("N"), src=pl.lit(src))
        .drop("N")
    )


def truth(cells, hmax, gcm="ACCESS-CM2", seed=1) -> pl.DataFrame:
    mem = pl.read_parquet(os.path.join(XDE, "shared", "registry", "members.parquet")).filter(
        (pl.col("gcm") == gcm)
        & (pl.col("seed") == seed)
        & ~pl.col("excluded")
        & pl.col("scen").is_in(["Historical", "ssp370"])
    )
    parts = []
    for m in mem["member"].to_list():
        fs = hd.member_files(m)
        lf = pl.concat(
            [
                pl.scan_parquet(f).select(
                    "Year", "Cell", "Type", "Height", "Age", "c_y", "G_y1", "fate_y1"
                )
                for f in fs
            ],
            how="vertical_relaxed",
        )
        if "Historical" in m:
            lf = lf.filter(pl.col("Year") <= 2013)
        parts.append(lf)
    d = (
        pl.concat(parts)
        .filter(
            pl.col("Cell").is_in(cells)
            & (pl.col("Type") <= 6)
            & (pl.col("Height") < hmax)
            & (pl.col("Year") <= 2043)
        )
        .collect()
    )
    return d.select(
        "Year",
        "Type",
        "Age",
        c=pl.col("c_y"),
        gneg=(pl.col("G_y1") < 0).fill_null(False),
        dead=pl.col("fate_y1") == 1,
        exit=pl.col("fate_y1") == 2,
    )


def arm(d: str, hmax: float) -> pl.DataFrame:
    """d = '<dump dir>|<run dir>': the counter at y is the roster's emitted c at y (it includes the
    recruits' entry counter); the outcome at y+1 comes from the dump (dump Year = y+1)."""
    dd, rd = d.split("|")
    k = KEY + ["SLA", "Wooddens"]
    fs = sorted(glob.glob(os.path.join(dd, "c*", "y*.parquet")))
    D = pl.concat([pl.scan_parquet(f) for f in fs], how="vertical_relaxed").collect()
    D = D.with_columns(Year=pl.col("Year") - 1).filter(~pl.col("hidden0") & (pl.col("H0") < hmax))
    rs = sorted(glob.glob(os.path.join(rd, "chunk_*", "y*_Historical.parquet")))
    rs += sorted(glob.glob(os.path.join(rd, "chunk_*", "y*_ssp370.parquet")))
    Rt = (
        pl.concat([pl.scan_parquet(f).select(k + ["Year", "c", "isdead"]) for f in rs])
        .filter(pl.col("isdead") == 0)
        .select(k + ["Year", pl.col("c").cast(pl.Int8)])
        .collect()
    )
    D = D.join(Rt, on=k + ["Year"], how="left")
    dead = pl.col("dead_h") | pl.col("dead_s") | pl.col("dead_f")
    return D.select(
        "Year",
        "Type",
        "Age",
        c=pl.col("c").fill_null(0),
        gneg=pl.col("G1") < 0,
        p_gneg=pl.col("p_gneg"),
        dead=dead,
        exit=~dead & pl.col("hidden1"),
        c_known=pl.col("c").is_not_null(),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True)
    ap.add_argument("--ncells", type=int, default=200)
    ap.add_argument("--hmax", type=float, default=6.0)
    a = ap.parse_args()
    cells = sorted(hd.folds()["Cell"].to_list())[: a.ncells]
    out = [summ(truth(cells, a.hmax), "truth")]
    for item in a.dump.split(","):
        lab, d = item.split("=", 1)
        A = arm(d, a.hmax)
        print(lab, "rows", A.height, "c unknown share", 1 - A["c_known"].mean(), flush=True)
        out.append(summ(A.drop("c_known"), lab))
    res = pl.concat(out, how="diagonal_relaxed").sort("win", "tg", "ag", "src")
    p = os.path.join(XDE, "shared", "eval", "struct_smallloss.csv")
    res.write_csv(p)
    pl.Config.set_tbl_rows(80)
    pl.Config.set_tbl_cols(14)
    print(res.with_columns(pl.selectors.float().round(4)))
    print("wrote", p)


if __name__ == "__main__":
    main()
