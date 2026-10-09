#!/usr/bin/env python3
"""explore_panel_more_summary.py -- LINE X: apply ADR 0316 sec. 7's pre-registered verdict to `explore_panel_a7.py more`
(seeds 1-5, xpanel/eval/a7_more_s<k>.csv). Nothing here is tuned: the bar, the prediction and the falsifier are the ones
written before the new runs existed.

  bar       per HG case: A7r 5-seed mean >= 0.5 x ceiling_mean (mean of m1-m3, unchanged) AND > that set's lookup null
  PREDICTED `both` - `base`, mean over the five held-out models' ssp370 >= +0.02; bar on >= 12 of 13 cases (`both`)
  FALSIFIER `both` - `base` < +0.01
"""

from __future__ import annotations

import glob
import os
import sys

import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_panel_a7 as PA  # noqa: E402


def main():
    fs = sorted(glob.glob(os.path.join(PA.EVAL, "a7_more_s*.csv")))
    d = pl.concat([pl.read_csv(f, infer_schema_length=None).with_columns(pl.lit(os.path.basename(f)).alias("file"))
                   for f in fs], how="diagonal_relaxed")
    d = d.with_columns(pl.col("split").str.split(":").list.get(0).alias("set"),
                       pl.col("split").str.split(":").list.get(1).alias("g"),
                       pl.col("test_leg").str.split("_").list.last().alias("scen"))
    m = d.group_by(["set", "g", "scen", "arm"]).agg(pl.col("pass_rate").mean().alias("p"),
                                                   pl.col("pass_rate").std().alias("sd"),
                                                   pl.col("stems_ratio").mean().alias("stems"),
                                                   pl.col("agb_per_stem_ratio").mean().alias("bpt"),
                                                   pl.col("ctl_resp_n_per_patch_slope_deatt").mean().alias("ctl_slope"),
                                                   pl.len().alias("n_seeds"))
    w = m.pivot(on="arm", index=["set", "g", "scen"], values="p").with_columns(
        (0.5 * pl.col("ceiling_mean")).alias("bar"))
    w = w.with_columns(((pl.col("A7r") >= pl.col("bar")) & (pl.col("A7r") > pl.col("lookup"))).alias("passes"))
    s370 = w.filter(pl.col("scen") == "ssp370").group_by("set").agg(pl.col("A7r").mean().alias("A7r_ssp370_mean"),
                                                                     pl.len().alias("n_models"))
    # the prediction was written for the 13 cases that existed then; the two legs that landed later (MPI and UKESM
    # ssp585 of the truth run) are reported separately, never folded into the verdict
    late = pl.col("g").is_in(["mpi-esm1-2-hr", "ukesm1-0-ll"]) & (pl.col("scen") == "ssp585")
    cases = w.filter(~late).group_by("set").agg(pl.col("passes").sum().alias("bar_passed"), pl.len().alias("n_cases"))
    print("late cases (not in the verdict):")
    print(w.filter(late).select("set", "g", "scen", "A7r", "bar", "lookup", "passes"))
    out = s370.join(cases, on="set").sort("set")
    with pl.Config(tbl_rows=80, tbl_cols=14, float_precision=4, fmt_str_lengths=24):
        print(f"{len(fs)} seed files")
        print(w.sort("set", "g", "scen"))
        print(m.filter(pl.col("arm") == "A7r").select("set", "g", "scen", "p", "sd", "stems", "bpt", "ctl_slope",
                                                      "n_seeds").sort("set", "g", "scen"))
        print(out)
    b = out.filter(pl.col("set") == "base")["A7r_ssp370_mean"][0]
    bo = out.filter(pl.col("set") == "both")
    gain = bo["A7r_ssp370_mean"][0] - b
    held = gain >= 0.02 and bo["bar_passed"][0] >= 12
    print(f"VERDICT  both - base on ssp370 = {gain:+.4f}; bar passed {bo['bar_passed'][0]} of {bo['n_cases'][0]} cases "
          f"-> prediction {'HELD' if held else 'NOT held'}; falsifier (< +0.01) {'FIRED' if gain < 0.01 else 'not fired'}")
    for x in ("mod", "run"):
        r = out.filter(pl.col("set") == x)
        if r.height:
            print(f"  {x}: {r['A7r_ssp370_mean'][0] - b:+.4f}")
    out.write_csv(os.path.join(PA.EVAL, "a7_more_summary.csv"))


if __name__ == "__main__":
    main()
