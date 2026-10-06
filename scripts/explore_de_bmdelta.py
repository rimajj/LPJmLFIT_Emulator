"""explore_de_bmdelta.py — LINE X, Germany emulator: does the year-to-year negative-growth swing sit in the tree's
carbon GAIN or in its LOSSES? (pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "I7 gain vs loss")

C (annual_tree.c:30-41, mortality_tree_ind.c:66): bm_delta = bm_inc/nind - turnover_ind, where bm_inc at that point is
the year's NPP minus reproduction, cmass_excess (turnover_tree.c, a growing-season phenology integral) and debt payback,
plus last year's excess carbon. From the `ind` table alone, per individual:
  gain     npp_ind  = npp * patcharea               (npp = pft->anpp per m2, nind = 1/patcharea, new_tree.c:209)
  leafarea          = LAI * fpc_ind * patcharea / (1 - exp(-k LAI))   (fpc_tree.c:28; k 0.59 broadleaved, 0.45 needle)
  bm_delta          = G * leafarea                  (G recovered from mort_npp, explore_de_sh_rules.recover_G)
  loss     L        = npp_ind - bm_delta            (everything bm_inc loses before the sign test)
negative growth <=> npp_ind < L. Counterfactual yearly shares on the trans table (tree living at y, printed at y1):
  cf_gain = P(npp_ind_y1 < L_y)   (this year's gain, LAST year's loss)
  cf_loss = P(npp_ind_y  < L_y1)  (last year's gain, this year's loss)
whichever reproduces the yearly swing of the true share P(npp_ind_y1 < L_y1) carries it.
Usage:  python explore_de_bmdelta.py [member ...]  -> shared/eval/bmdelta_yearly.csv
"""

from __future__ import annotations

import glob
import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_gsign_info as gi  # noqa: E402

PATCHAREA = 225.0
K_BL, K_NL = 0.59, 0.45
NEEDLE = [1, 4, 6]
DEFAULT = ["MPI-ESM1-2-HR_Historical_s1_h1985", "MPI-ESM1-2-HR_ssp245_s1_w2015",
           "ACCESS-CM2_Historical_s1_h1985", "ACCESS-CM2_ssp370_s1_w2015"]


def side(s: str) -> list[pl.Expr]:
    k = pl.when(pl.col("Type").is_in(NEEDLE)).then(K_NL).otherwise(K_BL)
    lai, fpc = pl.col(f"LAI{s}").cast(pl.Float64), pl.col(f"fpc_ind{s}").cast(pl.Float64)
    la = lai * fpc * PATCHAREA / (1 - (-k * lai).exp())
    npp = pl.col(f"npp{s}").cast(pl.Float64) * PATCHAREA
    return [npp.alias(f"gain{s}"), (npp - pl.col(f"G{s if s else '_y'}").cast(pl.Float64) * la).alias(f"L{s}")]


def main():
    mems = sys.argv[1:] or DEFAULT
    c2 = gi.cells200()
    out = []
    for mem in mems:
        fs = sorted(glob.glob(os.path.join(gi.XDE, "shared", "trans", "dev", mem, "cb=dev", "y*.parquet")))
        d = (pl.concat([pl.scan_parquet(f).select("Year", "Cell", "Type", "npp", "npp_y1", "LAI", "LAI_y1",
                                                  "fpc_ind", "fpc_ind_y1", "G_y", "G_y1", "cenG_y", "cenG_y1",
                                                  "c_y1", "fate_y1") for f in fs])
             .filter(pl.col("Cell").is_in(c2) & (pl.col("Type") <= 6) & (pl.col("fate_y1") < 2))
             .collect())
        n0 = d.height
        d = d.filter((pl.col("cenG_y") == 0) & (pl.col("cenG_y1") == 0) & (pl.col("LAI") > 0) & (pl.col("LAI_y1") > 0))
        d = d.with_columns(*side(""), *side("_y1"))
        # consistency only (gain < L <=> G < 0 by construction): the counter rule must agree with the sign of G
        neg = d["c_y1"].to_numpy() >= 1
        rec = (d["gain_y1"] < d["L_y1"]).to_numpy()
        agree = float((neg == rec).mean())
        lr = (d["L_y1"] / d["gain_y1"]).to_numpy()
        print(f"{mem}: {n0} transitions, {d.height} uncensored ({d.height / n0:.3f}); "
              f"counter-vs-G-sign agreement {agree:.5f}; "
              f"L/gain median {np.nanmedian(lr):.3f}, L <= 0 share {(d['L_y1'] <= 0).mean():.4f}", flush=True)
        Y = (d.group_by("Year").agg(true=(pl.col("gain_y1") < pl.col("L_y1")).mean(),
                                    neg=(pl.col("c_y1") >= 1).mean(),
                                    cf_gain=(pl.col("gain_y1") < pl.col("L")).mean(),
                                    cf_loss=(pl.col("gain") < pl.col("L_y1")).mean(),
                                    dlog_gain=(pl.col("gain_y1").clip(1e-3) / pl.col("gain").clip(1e-3)).log().mean(),
                                    dlog_loss=(pl.col("L_y1").clip(1e-3) / pl.col("L").clip(1e-3)).log().mean())
             .sort("Year").with_columns(member=pl.lit(mem)))
        out.append(Y)
        for c in ("cf_gain", "cf_loss", "dlog_gain", "dlog_loss"):
            print(f"  yearly corr(true share, {c}) = {np.corrcoef(Y['true'], Y[c])[0, 1]:.3f}   "
                  f"sd {Y[c].std():.4f} (true sd {Y['true'].std():.4f})")
    p = os.path.join(gi.EVAL, "bmdelta_yearly.csv")
    pl.concat(out).write_csv(p)
    print("wrote", p)


if __name__ == "__main__":
    main()
