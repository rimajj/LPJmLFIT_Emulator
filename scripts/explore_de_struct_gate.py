"""explore_de_struct_gate.py — LINE X, Germany emulator, STRUCT track: row-for-row gate of a
re-run against a stored free run (pre-registration /p/tmp/jamirp/X_de/_status/SD.md).

For every (scen, Year) of the re-run (Historical + the given leg) and exactly the re-run's cells:
  n_ref, n_new         emitted rows of the stored run and of the re-run
  only_ref, only_new   rows present in one roster only, compared on the FULL emitted state (Year,
                       Cell, Patch, Type, ID, isdead, Height, the 6 traits, agb, vegc, LAI, fpc_ind,
                       D95, Age, c; floats compared bit-exactly as float32)
  key_only_ref/_new    the same on the key (Cell, Patch, Type, ID, SLA, Wooddens) only
  dead_only_ref/_new   flagged-dead keys present in one run only
A re-run of the SAME arm passes when every count is 0 in every year. A counterfactual arm that
changes only the height closure must agree on the dead keys and on agb in its FIRST stepped year
(mortality and growth draws do not read height in that step): see dead_only_* / agb_neq_shared.

Usage:  python explore_de_struct_gate.py --new <run dir> [--ref <stored run dir>] [--leg ssp370]
Writes <new run dir>/gate_vs_stored.csv and prints PASS/FAIL.
"""

from __future__ import annotations

import argparse
import glob
import os

import polars as pl

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
REF = os.path.join(
    XDE, "runs", "struct_noacc", "ACCESS-CM2_s1_1985-2044_ssp126+ssp245+ssp370_actual_r1"
)
COLS = [
    "Year",
    "Cell",
    "Patch",
    "Type",
    "ID",
    "isdead",
    "Height",
    "SLA",
    "Wooddens",
    "D95max",
    "minwscal",
    "Longevity",
    "beta_root",
    "agb",
    "vegc",
    "LAI",
    "fpc_ind",
    "D95",
    "Age",
    "c",
]
PKEY = ["Cell", "Patch", "Type", "ID", "SLA", "Wooddens"]


def frame(run: str, leg: str, cells=None) -> pl.DataFrame:
    fs = []
    for d in sorted(glob.glob(os.path.join(run, "chunk_*"))):
        fs += sorted(glob.glob(os.path.join(d, "*_Historical.parquet")))
        fs += sorted(glob.glob(os.path.join(d, f"*_{leg}.parquet")))
    lf = pl.concat([pl.scan_parquet(f).select(COLS) for f in fs], how="vertical_relaxed")
    if cells is not None:
        lf = lf.filter(pl.col("Cell").is_in(cells))
    return lf.collect()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", required=True)
    ap.add_argument("--ref", default=REF)
    ap.add_argument("--leg", default="ssp370")
    a = ap.parse_args()
    N = frame(a.new, a.leg)
    cells = sorted(N["Cell"].unique().to_list())
    R = frame(a.ref, a.leg, cells)
    rows = []
    for (y,), n in N.group_by(["Year"], maintain_order=True):
        r = R.filter(pl.col("Year") == y)
        dn, dr = n.filter(pl.col("isdead") == 1), r.filter(pl.col("isdead") == 1)
        jn = r.select(PKEY + ["agb"]).join(n.select(PKEY + ["agb"]), on=PKEY, how="inner")
        rows.append(
            {
                "Year": y,
                "n_ref": r.height,
                "n_new": n.height,
                "only_ref": r.join(n, on=COLS, how="anti", join_nulls=True).height,
                "only_new": n.join(r, on=COLS, how="anti", join_nulls=True).height,
                "key_only_ref": r.join(n, on=PKEY, how="anti").height,
                "key_only_new": n.join(r, on=PKEY, how="anti").height,
                "dead_only_ref": dr.join(dn, on=PKEY, how="anti").height,
                "dead_only_new": dn.join(dr, on=PKEY, how="anti").height,
                "agb_neq_shared": int((jn["agb"] != jn["agb_right"]).sum()),
            }
        )
    G = pl.DataFrame(rows).sort("Year")
    G.write_csv(os.path.join(a.new, "gate_vs_stored.csv"))
    bad = G.filter((pl.col("only_ref") + pl.col("only_new")) > 0)
    pl.Config.set_tbl_rows(70)
    print(G.head(8))
    print(
        f"cells {len(cells)} ({cells[0]}..{cells[-1]}), years {G.height}, years with any row "
        f"difference: {bad.height}"
    )
    if bad.height:
        print("first differing year:", int(bad["Year"].min()))
        print(G.filter(pl.col("Year") == bad["Year"].min()))
    print("GATE", "PASS" if bad.height == 0 else "FAIL (expected for a counterfactual arm)")


if __name__ == "__main__":
    main()
