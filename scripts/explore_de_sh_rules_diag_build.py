#!/usr/bin/env python3
"""SH2 v3 diagnostic: Type-3 recruit out-of-interval Wooddens share by establishment year (y_est = Year - Age),
in two members that share their 1985-2014 history (MPI s1 ssp245 = Feb-2026 build from 2015, ssp370 = Dec-2025),
plus the share of living printed trees out of interval by year (the bank's raw material). Dev cells (Cell % 10)."""
import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_sh_rules as rl  # noqa: E402

P = rl.load_params()
KEY = ["Cell", "Patch", "Type", "ID", "SLA", "Wooddens"]
out = {}
for scen in ("ssp245", "ssp370"):
    fr = [rl._read_trees(m, ["Year", "Cell", "Patch", "Type", "ID", "isdead", "Age", "SLA", "Wooddens", "D95max"])
          for m in (f"MPI-ESM1-2-HR_Historical_s1_h1985", f"MPI-ESM1-2-HR_{scen}_s1_w2015")]
    a = pl.concat(fr).filter(pl.col("Type") == 3)
    lo, hi = P["wooddens_low"][3], P["wooddens_high"][3]
    a = a.with_columns(((pl.col("Wooddens") < lo * (1 - 1e-6)) | (pl.col("Wooddens") > hi * (1 + 1e-6))).alias("wd_out"))
    first = a.group_by(KEY).agg(pl.col("Year").min().alias("t_first"))
    rec = (a.join(first, on=KEY).filter((pl.col("Year") == pl.col("t_first")) & (pl.col("Year") > 1985))
           .with_columns((pl.col("Year") - pl.col("Age").cast(pl.Int32)).alias("y_est")))
    by_est = rec.group_by("y_est").agg(pl.len().alias("n"), pl.col("wd_out").mean().alias("out")).sort("y_est")
    by_vis = rec.group_by("Year").agg(pl.len().alias("n"), pl.col("wd_out").mean().alias("out")).sort("Year")
    liv = a.filter(pl.col("isdead") == 0).group_by("Year").agg(pl.col("wd_out").mean().alias("out_living")).sort("Year")
    print(scen, "recruits by y_est", by_est.filter(pl.col("n") > 2000).to_dicts(), flush=True)
    print(scen, "recruits by visible year", by_vis.to_dicts(), flush=True)
    print(scen, "living printed T3 out share by year", liv.to_dicts(), flush=True)
    out[scen] = {"by_est": by_est.to_dicts(), "by_vis": by_vis.to_dicts(), "living": liv.to_dicts()}
import json  # noqa: E402
json.dump(out, open("/p/tmp/jamirp/X_de/shared/rules/_diag/build_by_year.json", "w"), indent=1, default=float)
print("DIAG DONE", flush=True)
