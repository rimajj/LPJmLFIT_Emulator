#!/usr/bin/env python3
"""diagnose_hardkill_cause.py -- which HARD kill removes the trees in the original's drought die-offs? (ADR 0357)

ADR 0356 sec. 7: in the 3 291 shared die-off years of the unseen panel run (m4), 23 % of trees die by a hard kill
(`mort` = 1 with the four hazards summing below 1) against 11 % in other years. mortality_tree_ind.c:135-140 has two:
  (a) bm_inc_counter >= 5 (five years in a row of negative growth after turnover), and
  (b) the "ghost tree fix": leaf carbon below the sapling's,
      leaf_carbon_sapl = (lai_sapl * allom1 * wood_sapl^(kpr/2) * (4 sla / pi / k_latosa)^(kpr/2) / sla)^(2/(2-kpr))
      (mortality_tree_ind.c:63-65), with the TREE's own sampled sla.
The `ind` table carries neither leaf carbon nor the counter, but leaf carbon is exact from three columns:
  LAI = leaf_c * sla / crownarea (lai_tree.c:22),  fpc_ind = crownarea * nind * (1 - exp(-k * LAI)) (fpc_tree.c:28),
  nind = 1 / patcharea (225 m2, par/lpjparam_fit.js)  =>  crownarea = 225 fpc_ind / (1 - exp(-k LAI)),
  leaf_c = LAI * crownarea / sla;  k = the PFT's lightextcoeff.
Per tree r = leaf_c / leaf_carbon_sapl. If (b) is the cause, hard-killed trees have r < 1 and survivors r >= 1.
Also writes, per (leg, Cell, Year), the share of LIVING trees with r below 1.25 / 1.5 / 2 (the "near the threshold"
statistic of ADR 0357 step 2) -> xpanel/eval/near_threshold_m4.parquet, and reports how well last year's share
singles out the die-off years (AUC) beside the weather's (ADR 0355 C2: 0.87).
Parameters: cpp -P of the panel snapshot's par/pft_lpjmlfit.js (identical to $LPJROOT's, checked 2026-10-21).
~5-10 min on SLURM (15 legs x ~60 M rows, the event cells only).
"""

import os
import sys
from pathlib import Path

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import build_mort_params_reference as BM  # noqa: E402
import build_panel_bucket_stress as BK  # noqa: E402
import explore_panel_prep as PP  # noqa: E402

PANEL = "/p/projects/open/Jamir/esm_land_emulator_data/trackD/panel"
PAR = Path("/p/tmp/jamirp/trackD/cbuild/lpjml56fit_snapshot/par/pft_lpjmlfit.js")
PATCHAREA = 225.0
NEAR = (1.25, 1.5, 2.0)


def pft_table() -> pl.DataFrame:
    parsed, _ = BM.cpp_json(PAR)
    rows = []
    for i, p in enumerate(parsed["pftpar"][:7]):
        assert p["type"] == "tree", p["name"]
        rows.append(dict(Type=i, k=float(p["lightextcoeff"]), lai_sapl=float(p["lai_sapl"]),
                         allom1=float(p["allom1"]), wood_sapl=float(p["wood_sapl"]), kpr=float(p["kpr"]),
                         k_latosa=float(p["k_latosa"])))
    t = pl.DataFrame(rows).with_columns(pl.col("Type").cast(pl.Int8))
    print(t)
    return t


def with_ratio(d: pl.LazyFrame, prm: pl.DataFrame) -> pl.LazyFrame:
    d = d.join(prm.lazy(), on="Type", how="left")
    ca = PATCHAREA * pl.col("fpc_ind") / (1.0 - (-pl.col("k") * pl.col("LAI")).exp())
    leaf = pl.col("LAI") * ca / pl.col("SLA")
    h = pl.col("kpr") * 0.5
    sapl = ((pl.col("lai_sapl") * pl.col("allom1") * pl.col("wood_sapl").pow(h)
             * (4.0 * pl.col("SLA") / np.pi / pl.col("k_latosa")).pow(h) / pl.col("SLA"))
            .pow(2.0 / (2.0 - pl.col("kpr"))))
    hz = pl.col("mort_npp") + pl.col("mort_age") + pl.col("mort_water") + pl.col("mort_temp")
    cls = (pl.when(pl.col("isdead") == 0).then(pl.lit("alive"))
           .when((pl.col("mort") >= 1.0) & (hz < 1.0)).then(pl.lit("hard"))
           .when(pl.col("mort") >= 1.0).then(pl.lit("hazards>=1"))
           .otherwise(pl.lit("chance")))
    return d.with_columns((leaf / sapl).alias("r"), cls.alias("cls"))


def main():
    prm = pft_table()
    ev = pl.read_parquet(os.path.join(PP.OUT, "eval", "extreme_legacy_events.parquet")).filter(
        (pl.col("q") == "tree_count") & pl.col("shared")).select(
        pl.col("case").alias("leg"), pl.col("Cell").cast(pl.Int32), pl.col("year").cast(pl.Int16).alias("Year"))
    cls_rows, near = [], []
    for leg in sorted(ev["leg"].unique().to_list()):
        cells = ev.filter(pl.col("leg") == leg)["Cell"].unique()
        evl = ev.filter(pl.col("leg") == leg).with_columns(pl.lit(True).alias("event"))
        lf = with_ratio(pl.scan_parquet(os.path.join(PANEL, "m4", leg, "ind.parquet")).filter(
            (pl.col("Type") <= 6) & pl.col("Cell").is_in(cells.implode())), prm)
        lf = lf.join(evl.lazy(), on=["Cell", "Year"], how="left").with_columns(pl.col("event").fill_null(False))
        c = lf.filter(pl.col("Year").is_between(2025, 2090)).group_by("event", "cls").agg(
            pl.len().alias("n"), (pl.col("r") < 1.0).sum().alias("below"), pl.col("r").median().alias("r_p50"),
            pl.col("r").is_nan().sum().alias("nan")).collect()
        cls_rows.append(c)
        nr = lf.filter(pl.col("cls") == "alive").group_by("Cell", "Year").agg(
            pl.len().alias("n_alive"), *[(pl.col("r") < x).mean().alias(f"near{x}") for x in NEAR]).collect()
        near.append(nr.with_columns(pl.lit(leg).alias("leg")))
        print(f"{leg}: {c['n'].sum()} tree rows", flush=True)
    C = pl.concat(cls_rows).group_by("event", "cls").agg(
        pl.col("n").sum(), pl.col("below").sum(), pl.col("nan").sum(), pl.col("r_p50").median())
    C = C.with_columns((pl.col("below") / pl.col("n")).round(4).alias("share_r_below_1")).sort("event", "cls")
    pl.Config.set_tbl_rows(20)
    print("\n== per death class: share of trees with leaf carbon below the sapling's (r < 1)")
    print(C)
    N = pl.concat(near)
    N.write_parquet(os.path.join(PP.OUT, "eval", "near_threshold_m4.parquet"))
    # step 2 preview: does LAST year's near-threshold share single out the die-off years?
    N = N.sort("leg", "Cell", "Year").with_columns(
        [pl.col(f"near{x}").shift(1).over("leg", "Cell").alias(f"prev{x}") for x in NEAR])
    J = N.join(ev.with_columns(pl.lit(True).alias("event")), on=["leg", "Cell", "Year"], how="left").with_columns(
        pl.col("event").fill_null(False)).filter(pl.col("Year").is_between(2025, 2090) & (pl.col("n_alive") >= 25))
    for x in NEAR:
        e = J.filter(pl.col("event"))[f"prev{x}"].drop_nulls().to_numpy()
        o = J.filter(~pl.col("event"))[f"prev{x}"].drop_nulls().to_numpy()
        print(f"last year's share of living trees with r < {x}: event years median {np.median(e):.4f}, other years "
              f"{np.median(o):.4f}, AUC {BK.auc(e, o):.3f}")


if __name__ == "__main__":
    main()
