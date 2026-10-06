"""explore_de_struct_sddump.py — LINE X, Germany emulator, STRUCT track: read the per-tree step
dumps of explore_de_struct_sd.StructSD (pre-registration /p/tmp/jamirp/X_de/_status/SD.md, H2, H4,
H5).

Per (arm, year y+1), over the dumped trees (every tree in the state at y: printed + hidden):
  n_printed              printed living trees at y (hidden0 = False)
  exit                   printed at y, alive and below 5 m at y+1 (hidden1)    -> per patch
  reentry                hidden at y, alive and >= 5 m at y+1                 -> per patch
  hidden_pool            hidden trees at y                                    -> per patch
  dHneg / dlagb_neg      share of printed survivors with H1 < H0 - 0.01 / agb1 < agb0
  exit_*                 among exits: share with agb1 < agb0, with G < 0, median H0, median Age,
                         share with Age <= 15 (recent entrants: entry age ~12), share of type 3
  zG_mean / zdlagb_mean  mean latent of printed survivors (selection on the persistent latent)
  first_step_snap        (first dumped year only) printed trees whose H1 < 5 although agb1 >= agb0
Usage:  python explore_de_struct_sddump.py --dump label=<dump dir>[,label=<dir>...] [--tag _x]
Writes /p/tmp/jamirp/X_de/shared/eval/struct_sddump<tag>.csv
"""

from __future__ import annotations

import argparse
import glob
import os

import polars as pl

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
NPATCH = 250


def one(label: str, d: str) -> pl.DataFrame:
    fs = sorted(glob.glob(os.path.join(d, "c*", "y*.parquet")))
    D = pl.concat([pl.scan_parquet(f) for f in fs], how="vertical_relaxed")
    ncell = D.select(pl.col("Cell").n_unique()).collect().item()
    npt = ncell * NPATCH
    alive = ~(pl.col("dead_h") | pl.col("dead_s") | pl.col("dead_f"))
    pr = ~pl.col("hidden0")
    ex = pr & alive & pl.col("hidden1")
    sv = pr & alive & ~pl.col("hidden1")
    agbdn = pl.col("agb1") < pl.col("agb0")
    out = (
        D.group_by("Year")
        .agg(
            n_printed=pr.sum(),
            exit_pp=ex.sum() / npt,
            reentry_pp=(pl.col("hidden0") & alive & ~pl.col("hidden1")).sum() / npt,
            hidden_pool_pp=pl.col("hidden0").sum() / npt,
            dead_hidden_pp=(pl.col("hidden0") & ~alive).sum() / npt,
            dHneg=((pl.col("H1") < pl.col("H0") - 0.01) & pr & alive).sum() / (pr & alive).sum(),
            dlagb_neg=(agbdn & pr & alive).sum() / (pr & alive).sum(),
            exit_agb_down=(ex & agbdn).sum() / ex.sum(),
            exit_G_neg=(ex & (pl.col("G1") < 0)).sum() / ex.sum(),
            exit_H0_med=pl.col("H0").filter(ex).median(),
            exit_Age_med=pl.col("Age").filter(ex).median(),
            exit_age_le15=(ex & (pl.col("Age") <= 15)).sum() / ex.sum(),
            exit_type3=(ex & (pl.col("Type") == 3)).sum() / ex.sum(),
            printed_type3=(pr & (pl.col("Type") == 3)).sum() / pr.sum(),
            exit_rate_type3=(ex & (pl.col("Type") == 3)).sum() / (pr & (pl.col("Type") == 3)).sum(),
            exit_rate_rare=(ex & pl.col("Type").is_in([0, 4, 6])).sum()
            / (pr & pl.col("Type").is_in([0, 4, 6])).sum(),
            exit_rate_H0_lt6=(ex & (pl.col("H0") < 6)).sum() / (pr & (pl.col("H0") < 6)).sum(),
            share_H0_lt6=(pr & (pl.col("H0") < 6)).sum() / pr.sum(),
            snap_up_exits=(ex & ~agbdn).sum() / npt,
            zG_mean=pl.col("zG").filter(sv).mean(),
            zdlagb_mean=pl.col("zdlagb").filter(sv).mean(),
            G_neg_printed=((pl.col("G1") < 0) & pr).sum() / pr.sum(),
        )
        .with_columns(arm=pl.lit(label))
        .sort("Year")
        .collect()
    )
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    parts = []
    for item in a.dump.split(","):
        lab, d = item.split("=", 1)
        parts.append(one(lab, d))
    Out = pl.concat(parts, how="diagonal_relaxed")
    p = os.path.join(XDE, "shared", "eval", f"struct_sddump{a.tag}.csv")
    Out.write_csv(p)
    pl.Config.set_tbl_cols(30)
    pl.Config.set_tbl_rows(200)
    W = (
        Out.with_columns(win=((pl.col("Year") - 1986) // 10 * 10 + 1986))
        .group_by("arm", "win")
        .agg(pl.exclude("Year").mean())
        .sort("arm", "win")
        .with_columns(pl.selectors.float().round(4))
    )
    print(Out.filter(pl.col("Year") <= 1988).with_columns(pl.selectors.float().round(4)))
    print(W)
    print("wrote", p)


if __name__ == "__main__":
    main()
