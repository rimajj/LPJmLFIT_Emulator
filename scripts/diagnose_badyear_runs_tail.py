#!/usr/bin/env python3
"""diagnose_badyear_runs_tail.py -- POST-HOC companion to ADR 0356 C1 (written after C1's medians came back flat).

C1 (pre-registered) compared MEDIAN one-year tree-count changes in dry years by the run of bad years before them and
found none (-0.4 % in every bin). A die-off is a tail event, so this looks at the tail: over every scenario leg of the
panel, the mean over the five training runs (m1 m2 m3 m5 m6) of ln(n_per_patch + 1), its one-year change, and in dry
years (the daily bucket's actual/potential evaporation z < -1, ADR 0355) the 10th / 1st percentile of that change and
the share of years with a drop >= 0.15, by the run of bad years (1 / 2 / 3+) and by the drought's own size (z bins).
Dense cells only (five-run mean >= 5 trees per patch the year before). Reads xpanel/yearly + xpanel/climate_bucket;
~1 min on SLURM.
"""

import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_panel_a7 as A7  # noqa: E402
import explore_panel_yearly_drift as YD  # noqa: E402


def main():
    rows = []
    for leg in A7.ALL_SLEGS:
        ds = [d for m in YD.TRAIN_M if (d := YD.yearly(m, leg)) is not None]
        if len(ds) < 5:
            continue
        n = pl.concat(ds).group_by("Cell", "Year").agg(pl.col("n_per_patch").mean().alias("n")).sort("Cell", "Year")
        n = n.with_columns(pl.col("n").shift(1).over("Cell").alias("n_prev"),
                           ((pl.col("n") + 1).log() - (pl.col("n").shift(1).over("Cell") + 1).log()).alias("chg"))
        b = YD.bucket_anomaly(leg).select("Cell", "Year", "bkz0_bk_aetpet", "rl_aet")
        b = b.with_columns([pl.col(c).cast(n[c].dtype) for c in ("Cell", "Year")])
        rows.append(n.join(b, on=["Cell", "Year"]).filter((pl.col("n_prev") >= YD.DENSE) & pl.col("chg").is_not_null()))
    d = pl.concat(rows)
    dry = d.filter(pl.col("bkz0_bk_aetpet") < -1.0)
    print(f"dense cell-years {d.height}, dry ones {dry.height}; all years: drop>=0.15 share "
          f"{(d['chg'] <= -0.15).mean():.4f}")

    def table(g: pl.DataFrame, by: str) -> pl.DataFrame:
        return g.group_by(by).agg(pl.len().alias("n"), pl.col("chg").median().round(4).alias("p50"),
                                  pl.col("chg").quantile(0.10).round(4).alias("p10"),
                                  pl.col("chg").quantile(0.01).round(4).alias("p01"),
                                  (pl.col("chg") <= -0.15).mean().round(4).alias("share_drop15")).sort(by)

    pl.Config.set_tbl_rows(30)
    print("\n== dry years by the run of bad years (3 = 3 or more)")
    print(table(dry.with_columns(pl.col("rl_aet").clip(upper_bound=3).alias("run")), "run"))
    print("\n== dry years by the drought's own size (z of actual/potential evaporation)")
    zb = dry.with_columns(pl.col("bkz0_bk_aetpet").cut([-3.0, -2.0, -1.5], labels=["<-3", "-3..-2", "-2..-1.5",
                                                                                    "-1.5..-1"]).alias("zbin"))
    print(table(zb, "zbin"))
    print("\n== the same split by run, within z < -2 only")
    print(table(dry.filter(pl.col("bkz0_bk_aetpet") < -2.0).with_columns(
        pl.col("rl_aet").clip(upper_bound=3).alias("run")), "run"))
    q = np.quantile(dry["chg"].to_numpy(), [0.01, 0.1])
    print(f"\ndry-year change: 1st / 10th percentile {q[0]:.4f} / {q[1]:.4f}")


if __name__ == "__main__":
    main()
