"""explore_de_struct_probe.py -- line X, Germany emulator, STRUCTURED design track (architect probe).

Three cheap measurements that decide which parts of the original model's annual demography can be
APPLIED AS RULES (no learning) and which must be learned:

  A. mort_temp exactness: is the printed mort_temp == mort_temp_factor * (#days T < temp_stressed.low
     in the C's accumulator window) / 365, using the climate table's tstress_lt_m{10,15,20}?
  B. hazard decomposition: per member-window, the share of sum(mort) carried by hard kills and by
     each uncapped component (mort_npp, mort_age, mort_water, mort_temp) on the non-hard rows, and the
     same per-tree-year rates, so the ssp-minus-historic change of each channel is visible.
  C. bioclimatic establishment eligibility (establish.c): per PFT, the fraction of dev cells whose
     20-yr coldest-month / gdd5 / warmest-month buffer passes the PFT limits, per window.

Reads /p/tmp/jamirp/X_de/ind_dev/<member>.parquet (Cell % 10 == 0) and
/p/tmp/jamirp/X_de/climate/cell_year.parquet. Writes /p/tmp/jamirp/X_de/struct/probe_*.json/csv.
Run on SLURM:  scripts/sbatch_python.sh X-de-struct-probe scripts/explore_de_struct_probe.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import polars as pl

LPJROOT = os.environ.get("LPJROOT", "/home/jamirp/lpjml56fit")
DEV = "/p/tmp/jamirp/X_de/ind_dev"
CLIM = "/p/tmp/jamirp/X_de/climate/cell_year.parquet"
OUT = "/p/tmp/jamirp/X_de/struct"
ONLY_B = os.environ.get("STRUCT_ONLY_B") == "1"
MEMBERS = [
    "MPI-ESM1-2-HR_Historical_s1_h1985",
    "MPI-ESM1-2-HR_ssp370_s1_w2015",
    "MPI-ESM1-2-HR_ssp370_s1_w2071",
    "MPI-ESM1-2-HR_ssp126_s1_w2071",
    "ACCESS-CM2_Historical_s1_h1985",
    "ACCESS-CM2_ssp370_s1_w2071",
    "ACCESS-CM2_ssp126_s1_w2071",
]


def pftpar() -> list[dict]:
    s = subprocess.run(
        ["cpp", "-P", f"-I{LPJROOT}", f"{LPJROOT}/par/pft_lpjmlfit.js"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    s = re.sub(r",(\s*[}\]])", r"\1", s).strip().rstrip(",")
    return json.loads("{" + s + "}")["pftpar"]


def log(*a):
    print(*a, flush=True)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    par = pftpar()[:7]
    tlow = {i: float(p["temp_stressed"]["low"]) for i, p in enumerate(par)}
    mtf = 5.0  # MORT_TEMP_FACTOR (S_pft_mortality_params.csv)
    col_for = {-10.0: "tstress_lt_m10", -15.0: "tstress_lt_m15", -20.0: "tstress_lt_m20"}
    clim = pl.scan_parquet(CLIM)
    res_a, res_b, res_c = [], [], []
    for m in MEMBERS:
        gcm, scen, seed, win = m.rsplit("_", 3)
        path = f"{DEV}/{m}.parquet"
        if not os.path.exists(path):
            log("MISSING", path)
            continue
        cscen = "Historical" if scen == "Historical" else scen
        cy = clim.filter((pl.col("gcm") == gcm) & (pl.col("scen") == cscen)).select(
            "Cell",
            "Year",
            "tstress_lt_m10",
            "tstress_lt_m15",
            "tstress_lt_m20",
            "tcold_month_tr20",
            "twarm_month_tr20",
            "gdd5_tr20",
            "tcold_month",
            "gdd5",
        )
        t = (
            pl.scan_parquet(path)
            .filter(pl.col("Type") <= 6)
            .select("Year", "Cell", "Type", "mort_npp", "mort_age", "mort_water", "mort_temp", "mort", "isdead")
            .with_columns(
                pl.col("Year").cast(pl.Int32),
                pl.col("Cell").cast(pl.Int32),
                # float64 BEFORE any sum: polars accumulates a Float32 sum in Float32 (CLAUDE.md §4)
                pl.col("mort_npp", "mort_age", "mort_water", "mort_temp", "mort").cast(pl.Float64),
            )
        )
        if ONLY_B:
            a = None
        # ---- A: mort_temp exactness
        tj = t.join(cy, on=["Cell", "Year"], how="left")
        pred = pl.lit(0.0)
        for ty in range(7):
            lo = tlow[ty]
            if lo in col_for:
                pred = pl.when(pl.col("Type") == ty).then(mtf * pl.col(col_for[lo]).cast(pl.Float64) / 365.0).otherwise(pred)
        a = None if ONLY_B else (
            tj.with_columns(pred.alias("pred_mt"))
            .with_columns(
                (pl.col("mort_temp").cast(pl.Float64) - pl.col("pred_mt")).abs().alias("err"),
                pl.col("tstress_lt_m10").is_null().alias("noclim"),
            )
            .group_by("Type")
            .agg(
                pl.len().alias("n"),
                pl.col("noclim").sum().alias("n_noclim"),
                (pl.col("err") <= 1e-6 * pl.col("pred_mt").abs() + 2e-7).mean().alias("frac_exact"),
                pl.col("err").max().alias("max_abs_err"),
                pl.col("mort_temp").mean().alias("mean_printed"),
                pl.col("pred_mt").mean().alias("mean_pred"),
                (pl.col("mort_temp") > 0).mean().alias("frac_nonzero"),
            )
            .sort("Type")
            .collect()
        )
        if a is not None:
            for r in a.to_dicts():
                res_a.append({"member": m, **r})
            log(m, "A", a)
        # ---- B: hazard decomposition
        b = (
            t.with_columns((pl.col("mort") >= 1.0).alias("hard"))
            .group_by("Type")
            .agg(
                pl.len().alias("n"),
                pl.col("isdead").sum().alias("deaths"),
                pl.col("mort").sum().alias("sum_mort"),
                pl.col("hard").sum().alias("hard"),
                pl.col("mort_npp").filter(~pl.col("hard")).sum().alias("npp_nh"),
                pl.col("mort_age").filter(~pl.col("hard")).sum().alias("age_nh"),
                pl.col("mort_water").filter(~pl.col("hard")).sum().alias("water_nh"),
                pl.col("mort_temp").filter(~pl.col("hard")).sum().alias("temp_nh"),
                pl.col("mort").filter(~pl.col("hard")).sum().alias("mort_nh"),
                (pl.col("mort_water") > 0).sum().alias("n_water_pos"),
                pl.col("mort_water").sum().alias("water_all"),
            )
            .collect()
        )
        tot = b.select(pl.exclude("Type").sum()).to_dicts()[0]
        tot["Type"] = "all"
        for r in b.sort("Type").to_dicts() + [tot]:
            n = r["n"]
            res_b.append(
                {
                    "member": m,
                    **r,
                    "rate_death": r["deaths"] / n,
                    "rate_mort": r["sum_mort"] / n,
                    "rate_hard": r["hard"] / n,
                    "rate_npp_nh": r["npp_nh"] / n,
                    "rate_age_nh": r["age_nh"] / n,
                    "rate_water_nh": r["water_nh"] / n,
                    "rate_temp_nh": r["temp_nh"] / n,
                    "share_hard_of_mort": r["hard"] / r["sum_mort"],
                    "share_npp_of_mort": r["npp_nh"] / r["sum_mort"],
                    "share_age_of_mort": r["age_nh"] / r["sum_mort"],
                    "share_water_of_mort": r["water_nh"] / r["sum_mort"],
                    "share_temp_of_mort": r["temp_nh"] / r["sum_mort"],
                }
            )
        log(m, "B all", res_b[-1])
        # ---- C: establishment eligibility (establish.c) on the dev cells
        if ONLY_B:
            continue
        cells = t.select("Cell").unique()
        c = cy.join(cells, on="Cell", how="semi")
        yrs = {"h1985": (1985, 2014), "w2015": (2015, 2044), "w2071": (2071, 2100)}.get(win)
        if yrs is not None:
            c = c.filter(pl.col("Year").is_between(*yrs))
            exprs = []
            for i, p in enumerate(par):
                lo, hi = float(p["temp"]["low"]), float(p["temp"]["high"])
                g = float(p["gdd5min"])
                e = (
                    (pl.col("tcold_month_tr20") >= lo)
                    & (pl.col("tcold_month_tr20") <= hi)
                    & (pl.col("gdd5_tr20") >= g)
                    & (pl.col("twarm_month_tr20") > 10)
                )
                exprs.append(e.mean().alias(f"elig_{i}"))
            cc = c.select(exprs + [pl.col("tcold_month_tr20").mean().alias("tcold_tr20_mean")]).collect().to_dicts()[0]
            res_c.append({"member": m, **cc})
            log(m, "C", cc)
    if res_a:
        pl.DataFrame(res_a).write_csv(f"{OUT}/probe_A_mort_temp.csv")
    pl.DataFrame(res_b).write_csv(f"{OUT}/probe_B_hazard_decomp.csv")
    if res_c:
        pl.DataFrame(res_c).write_csv(f"{OUT}/probe_C_estab_eligibility.csv")
    json.dump({"members": MEMBERS, "tlow": tlow}, open(f"{OUT}/probe_meta.json", "w"))
    log("PROBE DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
