"""ADR 0343 sec. 3 measures from clu_non/eval/response_maps.csv: per arm, the median over the 8 test legs
(MPI/IPSL x ssp370/585 x CO2 rising/fixed) of the per-cell RMSE ratio to the second run, on the held-out cells
and on all cells, plus the median per-cell slope / r and the sec. 4 decision.

usage: python scripts/summarize_clu_arms.py [response_maps.csv] [baseline arm, default main2]
"""

import sys

import polars as pl

DEFAULT = "/p/projects/open/Jamir/esm_land_emulator_data/clu_non/eval/response_maps.csv"
CSV = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
BASE = sys.argv[2] if len(sys.argv) > 2 else "main2"
QS = ["lai_stand", "fpc_tree", "vegc", "fpc_grass"]


def main():
    d = pl.read_csv(CSV).filter((pl.col("ssp") != "ssp126") & pl.col("q").is_in(QS))
    s = d.group_by("cand", "q", "cells").agg(
        pl.len().alias("legs"), pl.col("rmse_ratio").median().alias("err"), pl.col("slope").median().alias("slope"),
        pl.col("r").median().alias("r"))
    w = s.pivot(on="cells", index=["cand", "q"], values=["err", "slope", "r"]).sort("q", "cand")
    with pl.Config(tbl_rows=200, tbl_width_chars=220, float_precision=3, tbl_cols=20):
        print(w)
    b = {(r["q"], r["cells"]): r["err"] for r in s.filter(pl.col("cand") == BASE).iter_rows(named=True)}
    print(f"\ndecision (ADR 0343 sec. 4) vs {BASE}:")
    for arm in sorted(set(s["cand"]) - {BASE, "second", "persist", "main", "wrong"}):
        e = {(r["q"], r["cells"]): r["err"] for r in s.filter(pl.col("cand") == arm).iter_rows(named=True)}
        dl = e[("lai_stand", "heldout_cells")] / b[("lai_stand", "heldout_cells")] - 1
        dt = e[("fpc_tree", "heldout_cells")] / b[("fpc_tree", "heldout_cells")] - 1
        all_ok = all(e[(q, "all")] - b[(q, "all")] <= 0.05 for q in ("lai_stand", "fpc_tree", "vegc"))
        veg_ok = e[("vegc", "heldout_cells")] - b[("vegc", "heldout_cells")] <= 0.05
        helps = dl <= -0.15 and dt <= -0.15 and all_ok and veg_ok
        print(f"  {arm:10s} held-out leaf area {dl:+.1%}  tree cover {dt:+.1%}  all-cell ok {all_ok}  "
              f"veg-carbon ok {veg_ok}  -> {'HELPS' if helps else 'does not help'}")


if __name__ == "__main__":
    main()
