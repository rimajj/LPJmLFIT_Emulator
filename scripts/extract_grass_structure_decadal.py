#!/usr/bin/env python
# =============================================================================
# extract_grass_structure_decadal.py — dump the C's PER-YEAR (2009-2019) per-patch tree+grass structure
# for the Hainich cell, in the `hainich_individuals_*.csv` format, so F_diff can be run at each year's OWN
# structure (not held at 2008) for the DEFINITIVE matched-structure + matched-forcing grass validation.
#
# Reuses reconstruct_year() from extract_fdiff_individuals_multiyear.py (same reconstruction the committed
# 2008/2010 references use). Writes to /p/tmp (intermediate, not committed).
#
#   run (SLURM): /home/jamirp/.conda/envs/py311_new/bin/python scripts/extract_grass_structure_decadal.py
# =============================================================================
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polars as pl
import extract_fdiff_individuals_multiyear as ex

COLS = ["patch", "type", "year", "height", "lai", "sla", "wooddens", "fpc_ind", "crownarea", "nind",
        "leaf_c", "sapwood_c", "heartwood_c", "root_c", "boleht", "agb_ind", "bm_inc_ind", "fpar_leafon",
        "alphaa", "albedo_leaf", "k_beer", "emax", "agb_perm2", "vegc_perm2", "npp_perm2"]
YEARS = list(range(2009, 2020))
OUT = "/p/tmp/jamirp/esm_land_emulator_data/fdiff_grass_decadal_struct"
os.makedirs(OUT, exist_ok=True)


def main():
    lf = pl.scan_parquet(ex.IND_PARQUET)
    df = (
        lf.filter((pl.col("Cell") == ex.CELL) & (pl.col("Year").is_in(YEARS)) & (pl.col("isdead") == 0))
        .select(["Type", "Patch", "Year", "Height", "LAI", "SLA", "Wooddens", "agb", "vegc", "fpc_ind", "npp"])
        .collect()
    )
    for y in YEARS:
        recs, agg = ex.reconstruct_year(df, y)
        out = os.path.join(OUT, f"hainich_individuals_{y}.csv")
        with open(out, "w") as f:
            f.write(f"# Hainich cell {ex.CELL} seed1 year {y}: per-individual tree+grass structure (decadal validation)\n")
            f.write(",".join(COLS) + "\n")
            for r in recs:
                f.write(",".join(f"{r.get(c, 0):.6g}" if isinstance(r.get(c, 0), float) else str(r.get(c, 0)) for c in COLS) + "\n")
        ng = sum(1 for r in recs if int(r["type"]) >= 7)
        print(f"  {y}: {len(recs)} individuals ({ng} grass rows), grass npp_cell={agg.get('npp_cell', float('nan')):.2f} -> {out}")
    print("DONE.")


if __name__ == "__main__":
    main()
