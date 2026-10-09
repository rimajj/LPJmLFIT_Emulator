#!/usr/bin/env python3
"""explore_glob_tab_gmag.py -- LINE X, ADR 0315 sec. 16.3: is the A-TAB growth-efficiency model wrong ONE STEP AHEAD
on the held-out member under a warm climate, or right one step and wrong only in the free run?

Teacher-forced (true state at y, true climate): on A1's unweighted held-out rows (u_hash < 0.02) of member 8 (SCEN set:
ssp126/245/370 2071-2099; SEED2 set: Historical 1985-2013) and member 7, per member-window: the observed vs predicted
share of bad-growth years (G_{y+1} < 0) and mean log|G_{y+1}| per sign, with the climate booster on (k1) and off (k0).
The same statistic on the training members' late windows is printed as the in-sample reference.

Expected (written before the run): if the free-run collapse is the magnitude model over-reacting to warm anomalies,
k1's mean log G for positive years falls BELOW the observed one on the late windows (by more than on Historical) and
k0 sits closer; if k1 is unbiased one step, the collapse is a free-run (state-feedback) effect, not a head bias.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_tab_heads as Hh  # noqa: E402


def main():
    H = Hh.TabHeads.load("DEV-A", heads=["gsign", "gmag_neg", "gmag_pos"])
    keep = None
    rows = []
    for s in ("SCEN", "SEED2", "train"):
        filt = (pl.col("fate_y1") <= 1) & (pl.col("cenG_y1") != 3)
        if s == "train":  # both strata, thinned by tree; means weighted by the inverse inclusion probability
            filt = filt & (pl.col("u_hash") < 0.02)
        df = Hh.load_rows("DEV-A", s, filt, keep=keep)
        if "w_ip" not in df.columns:
            df = df.with_columns(w_ip=pl.lit(1.0))
        for m in sorted(df["member"].unique().to_list()):
            d = df.filter(pl.col("member") == m)
            w = d["w_ip"].to_numpy().astype(np.float64)
            y = (d["G_y1"].to_numpy() < 0).astype(float)
            r = dict(set=s, member=m, n=d.height, neg_obs=float(np.average(y, weights=w)),
                     neg_k1=float(np.average(H.p_gneg(d, 1.0), weights=w)),
                     neg_k0=float(np.average(H.p_gneg(d, 0.0), weights=w)))
            dd = d.filter(pl.col("cenG_y1") == 0)
            for sg, nm in (("neg", "gmag_neg"), ("pos", "gmag_pos")):
                x = dd.filter((pl.col("G_y1") < 0) if sg == "neg" else (pl.col("G_y1") > 0))
                yy = np.log(np.abs(x["G_y1"].to_numpy().astype(np.float64)))
                wx = x["w_ip"].to_numpy().astype(np.float64)
                r[f"lg{sg}_obs"] = float(np.average(yy, weights=wx))
                r[f"lg{sg}_k1"] = float(np.average(H.raw(nm, x, 1.0), weights=wx))
                r[f"lg{sg}_k0"] = float(np.average(H.raw(nm, x, 0.0), weights=wx))
            rows.append(r)
            print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}, flush=True)
    out = pl.DataFrame(rows)
    out.write_csv("/p/projects/open/Jamir/esm_land_emulator_data/billing_global/eval/tab_gmag_onestep.csv")
    print(out)


if __name__ == "__main__":
    main()
