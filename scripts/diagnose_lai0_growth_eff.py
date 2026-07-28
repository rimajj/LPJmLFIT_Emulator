#!/usr/bin/env python3
"""Why does `growth_eff = applied_npp / max(lai, EPS)` blow up in the seed2 table but not seed1 — and what
does the RUNTIME do when leaf area is zero? (ADR 0031 step 2; the measurement that fixes the guard.)

## The reference basis (state it before measuring — `residual-diagnosis`)

The runtime feature this column trains is `fast.jl:369`:

    growth_eff = leaf_area > 0 ? applied_cell / leaf_area : zero(T)

i.e. the coupled loop returns **exactly 0** when the stand has no leaf area; it NEVER divides by a small
number. `scripts/build_slow_runtime_table.py` instead computed `applied_npp / max(lai, EPS)` with
`EPS = 1e-6`, so a joined `LAI_STAND == 0` becomes `applied_npp * 1e6`. That is a train/inference shift on a
primary mortality driver (ADR 0023's load-bearing rule), independent of how often it fires.

## The falsifiable hypothesis this script tests

ADR 0031 recorded the seed asymmetry as UNEXPLAINED: the seed1 production copula table has **zero** rows with
`growth_eff > 1e6` (max 31 183, mean 121.6) while the seed2 table has **204 867** (max 1.19e9, mean 264 495) —
"same lai table both times". That last clause is the tell:

  **H_seed — the asymmetry is a CROSS-SEED feature join, not a code path.** There is exactly ONE
  `cell_year_lai_hist.parquet`, and it is derived from a **seed1** C run
  (`build_laistand_lai_feature.py` → `daily_2000_2019_global_c0_67419_seed1`). Joined onto seed1 `ind` rows it
  is self-consistent: a cell-year with `LAI_STAND == 0` has no leafy trees in *that* trajectory either, so its
  `applied_npp` is ~0 and `0 / EPS = 0` hides the defect. Joined onto **seed2** `ind` rows — a different
  RAND48 trajectory (`-DPERMUTE`, CLAUDE.md §3) — a cell-year where seed2 grows a thriving stand can meet a
  seed1 `lai` of 0, and then `applied_npp * 1e6` explodes.

Predictions, all checked below (any one failing falsifies H_seed):
  P1  seed1: `lai == 0` tree-groups have `applied_npp == 0` (or none exist at all).
  P2  seed2: `lai == 0` tree-groups exist WITH `applied_npp > 0`, ~2e5 of them.
  P3  the count of `lai == 0` (Cell,Year) pairs is IDENTICAL for both seeds (one shared lai table).

If H_seed holds, the seed2 conditioning `Xc` is not merely "noisy" — it is unfixable without a seed2-derived
lai/soilmoist table, which matters for any future seed2 use of `Xc` (ADR 0030's floor reads `Y` only, so it
is unaffected either way).

## What this settles for the fix

The guard is NOT a judgement call about dropping vs flooring rows: match `fast.jl:369` (`lai > 0 ? … : 0.0`).
Reported per seed and per population so the widening to `TREE_TYPES = [0..6]` (ADR 0031 step 1) cannot hide a
change in this hazard.

Run:  TIME=01:00:00 NCPUS=32 scripts/sbatch_python.sh S-lai0 scripts/diagnose_lai0_growth_eff.py
Env:  SEEDS (default "1,2"), EPS (1e-6, the defect's divisor).
"""

import os

import polars as pl

BASE = "/p/tmp/jamirp/emulator_global"
IND = f"{BASE}/ind_hist_seed{{seed}}_all.parquet"
LAI_TBL = f"{BASE}/tables/cell_year_lai_hist.parquet"
EPS = float(os.environ.get("EPS", "1e-6"))
SEEDS = [int(s) for s in os.environ.get("SEEDS", "1,2").split(",") if s.strip()]

POPULATIONS = {
    "tree5 (data.py, the truncated production basis)": [1, 2, 3, 4, 5],
    "tree7 (features.py / pft_lpjmlfit.js, ADR 0031)": [0, 1, 2, 3, 4, 5, 6],
}


def main():
    lai = pl.read_parquet(LAI_TBL).select(["Cell", "Year", "lai"])
    n_lai = lai.height
    n_lai0 = int(lai.filter(pl.col("lai") == 0.0).height)
    print(f"== lai table {LAI_TBL}\n   {n_lai} (Cell,Year) rows, {lai['Cell'].n_unique()} cells; "
          f"lai==0 in {n_lai0} ({n_lai0 / n_lai:.4f}); min={lai['lai'].min():.6g} max={lai['lai'].max():.6g}")
    print("   NOTE this table is SEED1-derived (build_laistand_lai_feature.py RUN_DIR=..._seed1) — "
          "P3 holds by construction: it is the same table for every seed.", flush=True)

    for seed in SEEDS:
        path = IND.format(seed=seed)
        print(f"\n{'=' * 100}\n== seed{seed}: {path}", flush=True)
        for label, types in POPULATIONS.items():
            # per-(Cell,Patch,Year) tree aggregate, exactly as build_slow_runtime_table.py forms it
            agg = (
                pl.scan_parquet(path)
                .filter(pl.col("Type").is_in(types) & (pl.col("isdead") == 0))
                .group_by(["Cell", "Patch", "Year"])
                .agg(
                    pl.len().alias("n_living"),
                    pl.col("npp").sum().alias("bm_inc_cell"),
                    pl.col("npp").filter((pl.col("npp") > 0) & (pl.col("Height") > 0))
                    .sum().alias("applied_npp"),
                )
                .collect(engine="streaming")
                .join(lai, on=["Cell", "Year"], how="inner")
                .with_columns(pl.col("applied_npp").fill_null(0.0))
            )
            n = agg.height
            z = agg.filter(pl.col("lai") == 0.0)
            zpos = z.filter(pl.col("applied_npp") > 0.0)
            ge_eps = (pl.col("applied_npp") / pl.max_horizontal(pl.col("lai"), pl.lit(EPS)))
            ge_rt = pl.when(pl.col("lai") > 0.0).then(pl.col("applied_npp") / pl.col("lai")).otherwise(0.0)
            g = agg.select(ge_eps.alias("eps"), ge_rt.alias("runtime"))

            print(f"\n-- population {label}: types={types}")
            print(f"   {n} (Cell,Patch,Year) tree groups, {agg['Cell'].n_unique()} cells")
            print(f"   lai==0 groups                  : {z.height} ({z.height / max(n, 1):.5f}) "
                  f"in {z['Cell'].n_unique() if z.height else 0} cells")
            print(f"   ... of those, applied_npp > 0  : {zpos.height} "
                  f"({zpos.height / max(z.height, 1):.5f} of the lai==0 groups)")
            if zpos.height:
                print(f"   ... applied_npp there          : min={zpos['applied_npp'].min():.6g} "
                      f"max={zpos['applied_npp'].max():.6g} mean={zpos['applied_npp'].mean():.6g}")
                print(f"   ... n_living there             : min={zpos['n_living'].min()} "
                      f"max={zpos['n_living'].max()} median={zpos['n_living'].median()}")
            for rule in ("eps", "runtime"):
                c = g[rule]
                print(f"   growth_eff [{rule:7s}]           : max={c.max():14.6g} mean={c.mean():14.6g} "
                      f"median={c.median():10.6g}  rows>1e6={int((c > 1e6).sum())}")
            print(f"   VERDICT P{1 if seed == 1 else 2}: lai==0 groups with positive applied npp = "
                  f"{zpos.height} ⇒ {'CLEAN under the EPS rule (0/EPS=0)' if zpos.height == 0 else 'BLOWS UP under the EPS rule'}",
                  flush=True)
    print("\n== DONE diagnose_lai0_growth_eff ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
