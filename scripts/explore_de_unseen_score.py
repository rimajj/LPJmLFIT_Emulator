"""explore_de_unseen_score.py — LINE X, Germany emulator: score coupled runs on the pre-registered UNSEEN-WEATHER
rule, so members with different weather years are comparable.
(pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "the HONEST BASELINE: coupled gqsc on UNSEEN weather years")

Pulse years come from each member's OWN truth: among print years 2016..2044, the 8 with the highest truth < 10 m
certain-kill share (streak csv, hcls lt10, column `certain`); the other 21 are quiet. Reports per member:
< 10 m certain kills pulse / quiet emu/truth - 1, their yearly corr 2016-44, and the C3 stand bars from the
recruit-drift table (deaths 2016-25, biomass per stem per decade 1996-2025, stems 2026-35).
Usage:  python explore_de_unseen_score.py label:streak_tag:drift_csv:arm [...]
  e.g.  mpi2:gqsc_mpi2:recruit_drift_ssp370_gqsc_mpi2.csv:tabAL_g2hsgqsc
"""

from __future__ import annotations

import os
import sys

import numpy as np
import polars as pl

EVAL = os.path.join(os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de"), "shared", "eval")
NPULSE = 8


def score(label: str, tag: str, drift: str, arm: str) -> dict:
    S = pl.read_csv(os.path.join(EVAL, f"streak_{tag}.csv")).filter(
        (pl.col("hcls") == "lt10") & pl.col("y1").is_between(2016, 2044))
    W = S.pivot(on="src", index="y1", values="certain").sort("y1")
    assert W.height == 29, W.height
    pulse = W.sort("truth", descending=True).head(NPULSE)["y1"].to_list()
    W = W.with_columns(pulse=pl.col("y1").is_in(pulse))
    agg = W.group_by("pulse").agg(pl.col("emu").mean(), pl.col("truth").mean())
    pu = agg.filter(pl.col("pulse")).row(0, named=True)
    qu = agg.filter(~pl.col("pulse")).row(0, named=True)
    out = dict(member=label, pulse_years=" ".join(map(str, sorted(pulse))),
               pulse_rel=pu["emu"] / pu["truth"] - 1, quiet_rel=qu["emu"] / qu["truth"] - 1,
               certain_corr=float(np.corrcoef(W["emu"].to_numpy(), W["truth"].to_numpy())[0, 1]))
    D = pl.read_csv(os.path.join(EVAL, drift)).filter(pl.col("src").is_in(["truth", arm]))

    def rel(col: str, lo: int, hi: int) -> float:
        m = D.filter(pl.col("Year").is_between(lo, hi)).group_by("src").agg(pl.col(col).mean())
        v = dict(zip(m["src"].to_list(), m[col].to_list(), strict=True))
        return v[arm] / v["truth"] - 1

    out["deaths_2016_25"] = rel("dead_pp", 2016, 2025)
    for lo in (1996, 2006, 2016):
        out[f"agb_stem_{lo}_{lo + 9}"] = rel("agb_per_stem", lo, lo + 9)
    out["stems_2026_35"] = rel("stems_pp", 2026, 2035)
    out["stems_2036_44"] = rel("stems_pp", 2036, 2044)
    return out


def main():
    rows = [score(*spec.split(":")) for spec in sys.argv[1:]]
    R = pl.DataFrame(rows)
    pl.Config.set_tbl_cols(20)
    pl.Config.set_tbl_width_chars(250)
    pl.Config.set_fmt_str_lengths(60)
    print(R.with_columns(pl.col(pl.Float64).round(3)))
    out = os.path.join(EVAL, "unseen_score.csv")
    R.write_csv(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
