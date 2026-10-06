"""explore_de_death_decomp.py — LINE X, Germany emulator: is a free run's death deficit a too-low death RATE per
size class, or a different number of trees AT RISK in each class? (pre-registration: /p/tmp/jamirp/X_de/_status/TS.md,
"WHERE the 2016-25 death deficit sits")

A death at year y = a tree printed with isdead == 1 at y that was printed living at y-1 (explore_de_recruit_drift's
definition), classed by its y-1 height and, separately, by Type. Per decade and class: trees at risk per patch n,
death rate r = deaths / at risk. Exact decomposition of (arm - truth) deaths per patch:
    sum n_A r_A - sum n_T r_T = sum dn r_T (composition) + sum n_T dr (rate) + sum dn dr (interaction)
with n, r the decade's summed at-risk and deaths (so the identity holds on decade totals).

Usage:  python explore_de_death_decomp.py --arms name@<run dir>,... --gcm MPI-ESM1-2-HR --seed 2 [--chunks 0,1]
        [--leg ssp370] [--tag _gqs_mpi2]
Writes /p/tmp/jamirp/X_de/shared/eval/death_decomp_<leg><tag>.csv (per year x class) and _win.csv (decomposition).
"""

from __future__ import annotations

import argparse
import os
import sys

import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_recruit_drift as rd  # noqa: E402

XDE = rd.XDE
KEY = rd.KEY
HB = [10.0, 15.0, 20.0, 25.0, 30.0]
HL = ["h05-10", "h10-15", "h15-20", "h20-25", "h25-30", "h30+"]


def yearly_classes(D: pl.DataFrame, src: str) -> pl.DataFrame:
    D = D.filter(pl.col("Type") <= 6)
    years = sorted(D["Year"].unique().to_list())
    out = []
    prev = D.filter(pl.col("Year") == years[0])
    for y in years[1:]:
        cur = D.filter(pl.col("Year") == y)
        lp = prev.filter(pl.col("isdead") == 0).with_columns(
            hc=pl.col("Height").cut(HB, labels=HL).cast(pl.Utf8), tc=pl.format("T{}", pl.col("Type")))
        dead = cur.filter(pl.col("isdead") == 1).select(KEY).with_columns(d=pl.lit(1, pl.Int64))
        J = lp.select(*KEY, "hc", "tc").join(dead, on=KEY, how="left").with_columns(pl.col("d").fill_null(0))
        for by in ("hc", "tc"):
            g = J.group_by(by).agg(n=pl.len(), d=pl.col("d").sum()).rename({by: "cls"})
            out.append(g.with_columns(src=pl.lit(src), Year=pl.lit(y), split=pl.lit(by)))
        prev = cur
    return pl.concat(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", required=True)
    ap.add_argument("--gcm", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--chunks", default="0,1")
    ap.add_argument("--leg", default="ssp370")
    ap.add_argument("--npatch", type=int, default=250)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    chunks = [int(c) for c in a.chunks.split(",")]
    res, cells, dpp = [], None, {}
    for arm in a.arms.split(","):
        D, c = rd.arm_frame(arm, chunks, a.leg, cells)
        cells = cells or c
        assert c == cells, f"{arm}: cell set differs"
        name = arm.split("@", 1)[0]
        res.append(yearly_classes(D, name))
        dpp[name] = D.filter((pl.col("Type") <= 6) & (pl.col("isdead") == 1)).group_by("Year").len()
        print(f"{name}: {D.height} rows, {len(c)} cells", flush=True)
    y0, y1 = int(res[0]["Year"].min()) - 1, int(res[0]["Year"].max())
    T = rd.truth_frame(cells, a.leg, y0, y1, a.gcm, a.seed)
    res.append(yearly_classes(T, "truth"))
    dpp["truth"] = T.filter((pl.col("Type") <= 6) & (pl.col("isdead") == 1)).group_by("Year").len()
    R = pl.concat(res)
    npt = len(cells) * a.npatch
    # D0 gate: deaths matched to a living y-1 row == every printed death (no death without a living predecessor)
    worst = 0
    for s, g in dpp.items():
        m = (R.filter((pl.col("src") == s) & (pl.col("split") == "hc")).group_by("Year").agg(pl.col("d").sum())
             .join(g, on="Year", how="inner"))
        worst = max(worst, int((m["d"] - m["len"]).abs().max()))
    print(f"GATE D0 deaths matched to a living predecessor vs all printed deaths: worst |diff| {worst} per year",
          flush=True)
    out = os.path.join(XDE, "shared", "eval", f"death_decomp_{a.leg}{a.tag}")
    R.write_csv(out + ".csv")
    W = (R.with_columns(win=pl.format("{}-{}", 1986 + (pl.col("Year") - 1986) // 10 * 10,
                                      1995 + (pl.col("Year") - 1986) // 10 * 10))
         .group_by("src", "split", "win", "cls").agg(pl.col("n").sum(), pl.col("d").sum(),
                                                     ny=pl.col("Year").n_unique()))
    Tt = W.filter(pl.col("src") == "truth").select("split", "win", "cls", nT="n", dT="d", nyT="ny")
    rows = []
    for s in [x for x in W["src"].unique().to_list() if x != "truth"]:
        X = (W.filter(pl.col("src") == s).join(Tt, on=["split", "win", "cls"], how="full", coalesce=True)
             .with_columns(pl.col("n", "d", "nT", "dT").fill_null(0)))
        X = X.with_columns(ny=pl.max_horizontal(pl.col("ny").fill_null(0), pl.col("nyT").fill_null(0)))
        X = X.with_columns(
            nA=pl.col("n") / (npt * pl.col("ny")), nTp=pl.col("nT") / (npt * pl.col("ny")),
            rA=pl.when(pl.col("n") > 0).then(pl.col("d") / pl.col("n")).otherwise(0.0),
            rT=pl.when(pl.col("nT") > 0).then(pl.col("dT") / pl.col("nT")).otherwise(0.0))
        X = X.with_columns(comp=(pl.col("nA") - pl.col("nTp")) * pl.col("rT"),
                           rate=pl.col("nTp") * (pl.col("rA") - pl.col("rT")),
                           inter=(pl.col("nA") - pl.col("nTp")) * (pl.col("rA") - pl.col("rT")),
                           deadA=pl.col("nA") * pl.col("rA"), deadT=pl.col("nTp") * pl.col("rT"))
        rows.append(X.with_columns(src=pl.lit(s)).select("src", "split", "win", "cls", "nA", "nTp", "rA", "rT",
                                                         "deadA", "deadT", "comp", "rate", "inter"))
    Z = pl.concat(rows).sort("src", "split", "win", "cls")
    Z.write_csv(out + "_win.csv")
    pl.Config.set_tbl_rows(400)
    pl.Config.set_tbl_cols(20)
    pl.Config.set_tbl_width_chars(250)
    for s in Z["src"].unique().sort().to_list():
        for sp in ("hc", "tc"):
            Q = Z.filter((pl.col("src") == s) & (pl.col("split") == sp))
            tot = Q.group_by("win").agg(pl.col("deadA", "deadT", "comp", "rate", "inter").sum()).sort("win")
            print(f"\n== {s} by {sp}: decade totals per patch-year (deficit = deadA - deadT)")
            print(tot.with_columns(rel=(pl.col("deadA") / pl.col("deadT") - 1) * 100).with_columns(
                pl.exclude("win").round(5)))
            print(Q.select("win", "cls", "nA", "nTp", "rA", "rT", "comp", "rate", "inter").with_columns(
                pl.exclude("win", "cls").round(5)))
    print("wrote", out + "{.csv,_win.csv}")


if __name__ == "__main__":
    main()
