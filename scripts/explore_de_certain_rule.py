"""explore_de_certain_rule.py — LINE X, Germany emulator: which of the original's two CERTAIN-KILL rules makes its
mortality pulse years — 5 consecutive negative-growth years (bm_inc_counter >= 5) or leaf carbon below a sapling's
(the "ghost tree" rule), mortality_tree_ind.c:134-140?
(pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "WHICH certain-kill rule makes the pulses")

The counter is NOT emitted, but it is recovered exactly from mort_npp / mort_max (SH2 recover_counter, the trans
columns c_y / c_y1), so the two rules are separable for every printed dying tree.
Per print year y1 and height class at y (< 10 m, >= 10 m), over trees living at y and printed at y1 (fate_y1 < 2):
certain kills by rule, Bernoulli deaths, the negative-growth share at y1 (c_y1 >= 1), the c_y = 4 pool and the
4 -> 5 transition rate.
Usage:  python explore_de_certain_rule.py --cells-from <run dir> --gcm MPI-ESM1-2-HR --seed 2 [--leg ssp370] --tag mpi2
Writes /p/tmp/jamirp/X_de/shared/eval/certain_rule_<tag>.csv
"""

from __future__ import annotations

import argparse
import glob
import os

import polars as pl

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
PULSE = [2010, 2015, 2019, 2020, 2025, 2026, 2031, 2033, 2038, 2041]
TERMS1 = ["mort_npp_y1", "mort_age_y1", "mort_water_y1", "mort_temp_y1"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells-from", required=True)
    ap.add_argument("--gcm", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--leg", default="ssp370")
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    f0 = sorted(glob.glob(os.path.join(a.cells_from, "chunk_*", "y1986_*.parquet")))
    cells = sorted(pl.concat([pl.scan_parquet(f).select("Cell") for f in f0]).unique().collect()["Cell"].to_list())
    m = pl.read_parquet(os.path.join(XDE, "shared", "registry", "members.parquet")).filter(
        (pl.col("gcm") == a.gcm) & (pl.col("seed") == a.seed) & ~pl.col("excluded")
        & pl.col("scen").is_in(["Historical", a.leg]))
    paths = []
    for mem in m["member"].to_list():
        paths += sorted(glob.glob(os.path.join(XDE, "shared", "trans", "dev", mem, "cb=dev", "y*.parquet")))
    cols = ["Year", "Cell", "Type", "Height", "c_y", "c_y1", "fate_y1", "mort_y1", *TERMS1]
    lf = pl.concat([pl.scan_parquet(p).select(cols) for p in paths], how="vertical_relaxed")
    D = (lf.filter(pl.col("Cell").is_in(cells) & (pl.col("Type") <= 6) & (pl.col("fate_y1") < 2))
         .with_columns(y1=(pl.col("Year") + 1).cast(pl.Int32),
                       hcls=pl.when(pl.col("Height") < 10.0).then(pl.lit("lt10")).otherwise(pl.lit("ge10")),
                       sum4=pl.sum_horizontal([pl.col(t).cast(pl.Float64) for t in TERMS1]))
         .with_columns(certain=(pl.col("mort_y1") >= 0.9999) & (pl.col("sum4") < 0.9999),
                       dead=pl.col("fate_y1") == 1)
         .with_columns(cert_counter=pl.col("certain") & (pl.col("c_y1") >= 5),
                       cert_ghost=pl.col("certain") & (pl.col("c_y1") < 5))
         .collect())
    # K0 gate: every certain kill is flagged dead
    bad = D.filter(pl.col("certain") & ~pl.col("dead")).height
    print(f"K0 gate: certain rows {int(D['certain'].sum())}, of which NOT flagged dead {bad}", flush=True)
    f = lambda e: e.cast(pl.Float64).mean()  # noqa: E731
    R = (D.group_by("y1", "hcls")
         .agg(n=pl.len(), dead=f(pl.col("dead")), certain=f(pl.col("certain")),
              cert_counter=f(pl.col("cert_counter")), cert_ghost=f(pl.col("cert_ghost")),
              bern=f(pl.col("dead") & ~pl.col("certain")),
              neg_y1=f(pl.col("c_y1") >= 1), pool4_y=f(pl.col("c_y") == 4),
              pool3_y=f(pl.col("c_y") == 3),
              t45=(pl.col("c_y1") >= 5).filter(pl.col("c_y") == 4).cast(pl.Float64).mean())
         .with_columns(pulse=pl.col("y1").is_in(PULSE))
         .sort("hcls", "y1"))
    out = os.path.join(XDE, "shared", "eval", f"certain_rule_{a.tag}.csv")
    R.write_csv(out)
    pl.Config.set_tbl_rows(200)
    pl.Config.set_tbl_cols(20)
    pl.Config.set_tbl_width_chars(220)
    print(R.with_columns(pl.col(pl.Float64).round(4)))
    num = ["dead", "certain", "cert_counter", "cert_ghost", "bern", "neg_y1", "pool4_y", "pool3_y", "t45"]
    S = (R.filter(pl.col("y1") > 1986).group_by("hcls", "pulse").agg(*[pl.col(c).mean() for c in num])
         .sort("hcls", "pulse"))
    print(S.with_columns(pl.col(pl.Float64).round(4)))
    for h in ["lt10", "ge10"]:
        p = S.filter((pl.col("hcls") == h) & pl.col("pulse"))
        q = S.filter((pl.col("hcls") == h) & ~pl.col("pulse"))
        rise = p["certain"][0] - q["certain"][0]
        rc = p["cert_counter"][0] - q["cert_counter"][0]
        rg = p["cert_ghost"][0] - q["cert_ghost"][0]
        print(f"{h}: certain-kill rise {rise:.4f} = counter {rc:.4f} ({rc / rise:.0%}) + ghost {rg:.4f} "
              f"({rg / rise:.0%}); neg-growth share pulse/quiet {p['neg_y1'][0]:.4f}/{q['neg_y1'][0]:.4f} "
              f"= {p['neg_y1'][0] / q['neg_y1'][0]:.3f}")
    print("wrote", out, f"({len(cells)} cells)")


if __name__ == "__main__":
    main()
