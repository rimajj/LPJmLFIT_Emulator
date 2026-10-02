#!/usr/bin/env python
"""explore_de_sh_scorer_confirm_exclusion.py -- SH14: an independent confirmation, from the tree tables, that the
2071-2100 / 3071-3100 windows carry no water-stress mortality (the owner decision of 2026-10-01 excludes them).

Line X, Germany emulator exploration, round 2. Reads ONLY the columns Year, Type, isdead, mort_water of the dev-cell
tree tables (/p/tmp/jamirp/X_de/ind_dev/*.parquet, Cell % 10 == 0) -- the late windows are read solely to confirm
the exclusion. Per member-window and year: the share of living tree rows (Type <= 6, isdead == 0) with
mort_water > 0. Writes /p/tmp/jamirp/X_de/shared/scorer/sh14_exclusion_confirmation.{json,csv}.
Expected if the orchestrator's finding holds: exactly 0 in every year of every w2071 / w3071 member, > 0 in the
1985-2044 members.
"""

from __future__ import annotations

import glob
import json
import os
import sys

import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_reference as R  # noqa: E402

OUTD = f"{R.XDE}/shared/scorer"


def main() -> int:
    rows = []
    for f in sorted(glob.glob(f"{R.XDE}/ind_dev/*.parquet")):
        member = os.path.basename(f)[:-8]
        window = member.rsplit("_", 1)[1]
        y = (pl.scan_parquet(f).select(["Year", "Type", "isdead", "mort_water"])
             .filter((pl.col("Type") <= 6) & (pl.col("isdead") == 0))
             .group_by("Year").agg(pl.len().alias("n_living"),
                                   (pl.col("mort_water") > 0).sum().alias("n_mw_pos"))
             .collect().sort("Year"))
        assert y["Year"].n_unique() == y.height
        y = y.with_columns((pl.col("n_mw_pos") / pl.col("n_living")).alias("share_mw_pos"),
                           pl.lit(member).alias("member"), pl.lit(window).alias("window"))
        rows.append(y)
        print(f"{member}: years {y['Year'].min()}-{y['Year'].max()}, share mort_water>0 min "
              f"{y['share_mw_pos'].min():.4g} max {y['share_mw_pos'].max():.4g}", flush=True)
    d = pl.concat(rows)
    d.write_csv(f"{OUTD}/sh14_exclusion_confirmation.csv")
    s = d.group_by("window").agg(pl.col("member").n_unique().alias("members"), pl.len().alias("member_years"),
                                 pl.col("share_mw_pos").min().alias("min_share"),
                                 pl.col("share_mw_pos").max().alias("max_share"),
                                 (pl.col("n_mw_pos") == 0).mean().alias("frac_years_exactly_zero")).sort("window")
    late = s.filter(pl.col("window").is_in(list(R.EXCLUDED_WINDOWS)))
    early = s.filter(~pl.col("window").is_in(list(R.EXCLUDED_WINDOWS)))
    ok = bool((late["max_share"] == 0).all() and (early["frac_years_exactly_zero"] < 1).all()
              and late.height == len(R.EXCLUDED_WINDOWS))
    out = {"check": "share of living trees with mort_water > 0, dev cells (Cell % 10 == 0)",
           "confirmed_late_windows_have_no_water_stress_mortality": ok, "per_window": s.to_dicts(),
           "per_member_years_2015_2044_2071_2100": d.filter(pl.col("Year").is_in([1985, 2014, 2015, 2044, 2071,
                                                                                  2100, 3071, 3100])).to_dicts()}
    json.dump(out, open(f"{OUTD}/sh14_exclusion_confirmation.json", "w"), indent=1, default=str)
    with pl.Config(tbl_rows=50):
        print(s)
    print("EXCLUSION_CONFIRMED", ok, flush=True)
    return 0 if ok else 7


if __name__ == "__main__":
    sys.exit(main())
