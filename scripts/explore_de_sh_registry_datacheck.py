#!/usr/bin/env python3
"""SH0 data-consistency check (SLURM): does the registry's rh_on flag agree with the TRUTH's own behaviour?

For every dev member-window (ind_dev), per Year: living tree rows (Type <= 6, isdead == 0) and how many of them
carry mort_water > 0. Joined to segments.parquet's rh_on for that (gcm, src_scen, seed, Year). Expectation
[SOURCE getvpd.c / waterstress_tree.c]: rh_on == 0 => water-stress mortality is EXACTLY 0 for every living tree.

Also a blind-year-map diagnostic: lag-1 autocorrelation of the dev-cell mean annual temperature and precipitation
over the baseline 1985-2014 per GCM (Historical), which an i.i.d. year resample sets to ~0 by construction.

Writes <registry>/datacheck_mortwater.parquet, <registry>/_datacheck.json.
"""

from __future__ import annotations

import json
import os
import sys

import polars as pl

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
REG = f"{XDE}/shared/registry"
DEV_MOD = int(os.environ.get("SH0_DEV_MOD", "10"))


def log(*a):
    print(*a, flush=True)


def main():
    mem = pl.read_parquet(f"{REG}/members.parquet")
    seg = pl.read_parquet(f"{REG}/segments.parquet")
    out = []
    for r in mem.sort("member").iter_rows(named=True):
        d = (
            pl.scan_parquet(r["ind_dev_path"])
            .filter((pl.col("Type") <= 6) & (pl.col("isdead") == 0))
            .group_by("Year")
            .agg(
                pl.len().alias("n_live"),
                (pl.col("mort_water") > 0).sum().alias("n_mw_pos"),
                pl.col("mort_water").cast(pl.Float64).max().alias("mw_max"),
            )
            .collect()
        )
        assert d["Year"].n_unique() == d.height
        d = d.with_columns(
            pl.lit(r["member"]).alias("member"),
            pl.lit(r["gcm"]).alias("gcm"),
            pl.lit(r["scen"]).alias("src_scen"),
            pl.lit(r["seed"]).cast(pl.Int32).alias("seed"),
            pl.lit(r["win"]).alias("win"),
            pl.col("Year").cast(pl.Int32),
        )
        out.append(d)
        log(
            r["member"],
            d.height,
            "years; mw>0 share range",
            float((d["n_mw_pos"] / d["n_live"]).min()),
            float((d["n_mw_pos"] / d["n_live"]).max()),
        )
    t = pl.concat(out, how="vertical_relaxed")
    flags = seg.select("gcm", "src_scen", "seed", "Year", "rh_on").unique()
    assert flags.select("gcm", "src_scen", "seed", "Year").n_unique() == flags.height
    t = t.join(flags, on=["gcm", "src_scen", "seed", "Year"], how="left")
    t.write_parquet(f"{REG}/datacheck_mortwater.parquet")
    nomatch = t["rh_on"].null_count()
    off = t.filter(pl.col("rh_on") == 0)
    on = t.filter(pl.col("rh_on") == 1).with_columns(
        (pl.col("n_mw_pos") / pl.col("n_live")).alias("share")
    )
    res = {
        "basis": f"ind_dev (Cell % {DEV_MOD} == 0), living tree rows, every member-window and year",
        "rows_without_flag": nomatch,
        "rh_off_member_years": off.height,
        "rh_off_trees_with_mort_water_pos": int(off["n_mw_pos"].sum()),
        "rh_off_mw_max": float(off["mw_max"].max()) if off.height else None,
        "rh_on_member_years": on.height,
        "rh_on_years_with_zero_mw_pos": int((on["n_mw_pos"] == 0).sum()),
        "rh_on_share_mw_pos_by_win": on.group_by("win")
        .agg(
            pl.col("share").min().alias("min"),
            pl.col("share").median().alias("median"),
            pl.col("share").max().alias("max"),
        )
        .sort("win")
        .to_dicts(),
    }
    # owner decision 2026-10-01: confirm the exclusion on the truth itself -- the share of living trees with
    # mort_water > 0 at the first and last year of each ssp window, and whether every EXCLUDED year (registry
    # segments.excluded) has exactly zero (read only to confirm the exclusion).
    ex = seg.select("gcm", "src_scen", "seed", "Year", "excluded").unique()
    assert ex.select("gcm", "src_scen", "seed", "Year").n_unique() == ex.height
    t2 = t.join(ex, on=["gcm", "src_scen", "seed", "Year"], how="left").with_columns(
        (pl.col("n_mw_pos") / pl.col("n_live")).alias("share")
    )
    sel = (
        t2.filter(
            (pl.col("src_scen") != "Historical") & pl.col("Year").is_in([2015, 2044, 2071, 2100])
        )
        .group_by("Year")
        .agg(
            pl.len().alias("member_years"),
            pl.col("share").min().alias("min"),
            pl.col("share").max().alias("max"),
        )
        .sort("Year")
    )
    res["owner_check_share_mw_pos_ssp_by_year"] = sel.to_dicts()
    res["excluded_member_years"] = int(t2["excluded"].sum())
    res["excluded_trees_with_mort_water_pos"] = int(t2.filter(pl.col("excluded"))["n_mw_pos"].sum())
    res["clean_member_years"] = int((~t2["excluded"]).sum())
    res["clean_member_years_with_zero_mw_pos"] = int(
        t2.filter(~pl.col("excluded") & (pl.col("n_mw_pos") == 0)).height
    )
    res["pass"] = bool(
        nomatch == 0
        and res["rh_off_trees_with_mort_water_pos"] == 0
        and off.height > 0
        and t2["excluded"].null_count() == 0
        and res["excluded_trees_with_mort_water_pos"] == 0
        and res["clean_member_years_with_zero_mw_pos"] == 0
    )
    # blind-map diagnostic: dev-cell mean annual climate, lag-1 autocorrelation over 1985-2014 (Historical)
    cy = (
        pl.scan_parquet(f"{XDE}/climate/cell_year.parquet")
        .filter(
            (pl.col("scen") == "Historical")
            & pl.col("Year").is_between(1985, 2014)
            & (pl.col("Cell") % DEV_MOD == 0)
        )
        .group_by("gcm", "Year")
        .agg(
            pl.col("tmean_ann").cast(pl.Float64).mean(), pl.col("prec_ann").cast(pl.Float64).mean()
        )
        .collect()
        .sort(["gcm", "Year"])
    )
    ac = {}
    for g in cy["gcm"].unique().sort().to_list():
        s = cy.filter(pl.col("gcm") == g)
        ac[g] = {
            v: float(pl.DataFrame({"a": s[v][:-1], "b": s[v][1:]}).select(pl.corr("a", "b")).item())
            for v in ("tmean_ann", "prec_ann")
        }
        ac[g]["n_years"] = s.height
    res["baseline_lag1_autocorr_devmean"] = ac
    json.dump(res, open(f"{REG}/_datacheck.json", "w"), indent=1)
    log(json.dumps(res, indent=1))
    log("DATACHECK", "PASS" if res["pass"] else "FAIL")
    sys.exit(0 if res["pass"] else 1)


if __name__ == "__main__":
    main()
