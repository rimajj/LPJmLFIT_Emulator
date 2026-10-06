"""explore_de_death_pulse.py — LINE X, Germany emulator: are the original's mortality PULSE years patch clearings
(fire-like: most stems of a patch die together) or diffuse, and which of the two does a free run under-produce?
(pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "death PULSES")

Per (source, year): deaths of tree stems living at y-1 (explore_de_death_decomp's definition), split by the patch's
death fraction (clearing = >= CLEAR of its living y-1 stems die) and by y-1 height (< 10 m / >= 10 m); plus the gate
split: deaths printed at y with no living y-1 row, by printed height.

Usage:  python explore_de_death_pulse.py --arms name@<run dir>,... --gcm MPI-ESM1-2-HR --seed 2 [--tag _gqs_mpi2]
Writes /p/tmp/jamirp/X_de/shared/eval/death_pulse_<leg><tag>.csv
"""

from __future__ import annotations

import argparse
import os
import sys

import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_recruit_drift as rd  # noqa: E402

KEY = rd.KEY
CLEAR = 0.8


def per_year(D: pl.DataFrame, src: str) -> pl.DataFrame:
    D = D.filter(pl.col("Type") <= 6)
    years = sorted(D["Year"].unique().to_list())
    out = []
    prev = D.filter(pl.col("Year") == years[0])
    for y in years[1:]:
        cur = D.filter(pl.col("Year") == y)
        lp = prev.filter(pl.col("isdead") == 0).select(*KEY, h0="Height")
        dead = cur.filter(pl.col("isdead") == 1).select(*KEY, h1="Height")
        J = lp.join(dead.select(KEY).with_columns(d=pl.lit(1, pl.Int64)), on=KEY, how="left").with_columns(
            pl.col("d").fill_null(0))
        pf = J.group_by("Cell", "Patch").agg(fr=pl.col("d").mean())
        J = J.join(pf, on=["Cell", "Patch"]).with_columns(clear=pl.col("fr") >= CLEAR, small=pl.col("h0") < 10.0)
        orphan = dead.join(lp.select(KEY), on=KEY, how="anti")
        row = {"src": src, "Year": y, "n_live": J.height, "d_all": int(J["d"].sum()),
               "n_patch": pf.height, "n_clear_patch": int((pf["fr"] >= CLEAR).sum()),
               "orphan": orphan.height, "orphan_h_med": float(orphan["h1"].median()) if orphan.height else None,
               "orphan_lt6": int((orphan["h1"] < 6.0).sum())}
        for cl in (True, False):
            for sm in (True, False):
                q = J.filter((pl.col("clear") == cl) & (pl.col("small") == sm))
                k = f"{'clear' if cl else 'diff'}_{'lt10' if sm else 'ge10'}"
                row[f"d_{k}"] = int(q["d"].sum())
                row[f"n_{k}"] = q.height
        out.append(row)
        prev = cur
    return pl.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", required=True)
    ap.add_argument("--gcm", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--chunks", default="0,1")
    ap.add_argument("--leg", default="ssp370")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    chunks = [int(c) for c in a.chunks.split(",")]
    res, cells = [], None
    for arm in a.arms.split(","):
        D, c = rd.arm_frame(arm, chunks, a.leg, cells)
        cells = cells or c
        assert c == cells, f"{arm}: cell set differs"
        res.append(per_year(D, arm.split("@", 1)[0]))
        print(f"{arm.split('@', 1)[0]}: {D.height} rows", flush=True)
    T = rd.truth_frame(cells, a.leg, int(res[0]["Year"].min()) - 1, int(res[0]["Year"].max()), a.gcm, a.seed)
    res.append(per_year(T, "truth"))
    R = pl.concat(res, how="diagonal_relaxed")
    out = os.path.join(rd.XDE, "shared", "eval", f"death_pulse_{a.leg}{a.tag}.csv")
    R.write_csv(out)
    pl.Config.set_tbl_rows(400)
    pl.Config.set_tbl_cols(30)
    pl.Config.set_tbl_width_chars(260)
    print(R.select("src", "Year", "orphan", "orphan_h_med", "orphan_lt6").filter(pl.col("Year") % 5 == 0))
    V = R.with_columns(
        rate=pl.col("d_all") / pl.col("n_live"),
        clear_share=(pl.col("d_clear_lt10") + pl.col("d_clear_ge10")) / pl.col("d_all"),
        r_diff_lt10=pl.col("d_diff_lt10") / pl.col("n_diff_lt10"),
        r_diff_ge10=pl.col("d_diff_ge10") / pl.col("n_diff_ge10"),
        clear_patch_frac=pl.col("n_clear_patch") / pl.col("n_patch"))
    print(V.select("src", "Year", "rate", "clear_share", "clear_patch_frac", "r_diff_lt10", "r_diff_ge10")
          .filter(pl.col("Year") >= 2005).sort("Year", "src").with_columns(pl.col(pl.Float64).round(4)))
    print("wrote", out)


if __name__ == "__main__":
    main()
