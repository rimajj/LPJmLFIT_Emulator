"""explore_de_streak.py — LINE X, Germany emulator: negative-growth STREAK dynamics of the original vs a coupled free
run. The original's mortality pulses are certain kills by the 5-bad-years counter rule (mortality_tree_ind.c:134), and
what pulses is the pool of trees already at counter 4 (certain_rule_<tag>.csv) — so compare when streaks START and how
long they PERSIST.
(pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "STREAK dynamics truth vs coupled gqs")

Truth: trans dev rows (c_y -> c_y1, trees living at y and printed at y1). Emulator: a probe dump (c_y -> c1, one row
per printed living tree at Y with its drawn transition to Y+1). Per print year y1 and height class at y:
start = P(c1 = 1 | c_y = 0), p1..p4 = P(c1 = k+1 | c_y = k), pool shares c_y = k, certain = P(c1 >= 5).
Usage:  python explore_de_streak.py --dump <dir> --gcm MPI-ESM1-2-HR --seed 2 [--leg ssp370] --tag gqs_mpi2
Writes /p/tmp/jamirp/X_de/shared/eval/streak_<tag>.csv
"""

from __future__ import annotations

import argparse
import glob
import os

import polars as pl

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")


def stats(lf: pl.LazyFrame, src: str) -> pl.DataFrame:
    f = lambda e: e.cast(pl.Float64).mean()  # noqa: E731
    agg = dict(n=pl.len(), start=(pl.col("c1") == 1).filter(pl.col("c0") == 0).cast(pl.Float64).mean(),
               neg=f(pl.col("c1") >= 1), certain=f(pl.col("c1") >= 5))
    for k in range(1, 5):
        agg[f"p{k}"] = (pl.col("c1") == k + 1).filter(pl.col("c0") == k).cast(pl.Float64).mean()
        agg[f"pool{k}"] = f(pl.col("c0") == k)
    return (lf.with_columns(hcls=pl.when(pl.col("Height") < 10.0).then(pl.lit("lt10")).otherwise(pl.lit("ge10")))
            .group_by("y1", "hcls").agg(**agg).with_columns(src=pl.lit(src)).collect())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True)
    ap.add_argument("--gcm", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--leg", default="ssp370")
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    fs = sorted(glob.glob(os.path.join(a.dump, "*", "*.parquet")))
    emu = (pl.concat([pl.scan_parquet(f).select("Cell", "Year", "Type", "Height", "c_y", "c1") for f in fs])
           .filter(pl.col("Type") <= 6)
           .select(pl.col("Cell"), (pl.col("Year") + 1).cast(pl.Int32).alias("y1"), "Height",
                   pl.col("c_y").round(0).cast(pl.Int8).alias("c0"), pl.col("c1").cast(pl.Int8)))
    cells = emu.select("Cell").unique().collect()["Cell"].to_list()
    m = pl.read_parquet(os.path.join(XDE, "shared", "registry", "members.parquet")).filter(
        (pl.col("gcm") == a.gcm) & (pl.col("seed") == a.seed) & ~pl.col("excluded")
        & pl.col("scen").is_in(["Historical", a.leg]))
    paths = []
    for mem in m["member"].to_list():
        paths += sorted(glob.glob(os.path.join(XDE, "shared", "trans", "dev", mem, "cb=dev", "y*.parquet")))
    tru = (pl.concat([pl.scan_parquet(p).select("Year", "Cell", "Type", "Height", "c_y", "c_y1", "fate_y1")
                      for p in paths], how="vertical_relaxed")
           .filter(pl.col("Cell").is_in(cells) & (pl.col("Type") <= 6) & (pl.col("fate_y1") < 2))
           .select((pl.col("Year") + 1).cast(pl.Int32).alias("y1"), "Height",
                   pl.col("c_y").cast(pl.Int8).alias("c0"), pl.col("c_y1").cast(pl.Int8).alias("c1")))
    R = pl.concat([stats(tru, "truth"), stats(emu, "emu")]).sort("hcls", "y1", "src")
    R = R.filter(pl.col("y1") > 1986)
    out = os.path.join(XDE, "shared", "eval", f"streak_{a.tag}.csv")
    R.write_csv(out)
    pl.Config.set_tbl_rows(300)
    pl.Config.set_tbl_cols(20)
    pl.Config.set_tbl_width_chars(220)
    num = ["start", "p1", "p2", "p3", "p4", "pool1", "pool2", "pool3", "pool4", "neg", "certain"]
    print(f"{len(cells)} cells")
    for h in ["lt10", "ge10"]:
        W = R.filter(pl.col("hcls") == h).pivot(on="src", index="y1", values=["start", "pool4", "certain", "p4"])
        print(h)
        print(W.with_columns(pl.col(pl.Float64).round(4)))
        S = (R.filter(pl.col("hcls") == h).group_by("src")
             .agg(*[pl.col(c).mean().alias(c) for c in num], *[pl.col(c).std().alias(c + "_sd") for c in
                                                               ["start", "neg", "pool4", "certain"]]))
        print(S.with_columns(pl.col(pl.Float64).round(4)))
        t = R.filter((pl.col("hcls") == h) & (pl.col("src") == "truth")).sort("y1")
        for lag in range(0, 7):
            x = t["start"].to_list()
            y = t["certain"].to_list()
            if lag:
                x, y = x[:-lag], y[lag:]
            print(f"  truth corr(start at y1, certain at y1+{lag}) = "
                  f"{pl.DataFrame({'x': x, 'y': y}).select(pl.corr('x', 'y')).item():.3f}")
        e = R.filter((pl.col("hcls") == h) & (pl.col("src") == "emu")).sort("y1")
        j = t.join(e, on="y1", suffix="_e")
        for c in ["start", "pool4", "certain", "neg"]:
            print(f"  yearly corr truth vs emu, {c}: {j.select(pl.corr(c, c + '_e')).item():.3f}")
    print("wrote", out)


if __name__ == "__main__":
    main()
