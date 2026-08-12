#!/usr/bin/env python3
# =============================================================================
# diagnose_c_assimilate_noise.py — THE ORACLE's OWN TWO-RUN SPREAD on the quantity
# rung 3 scores F against, in BOTH scenarios.
#
# WHY. `EXECUTION_PLAN.md` §5 rule 2 and `residual-diagnosis` §5: every fidelity
# number must carry the target's own noise floor for that quantity and stratum,
# because LPJmL-FIT is stochastic and at the production npatch=25 its own answer is
# already outside the 10 % band for several quantities. Rung 3's target is the
# per-cell annual TREE ASSIMILATE (the `ind` table's `npp` column = `pft->anpp`,
# summed over the cell's tree stems and divided by the CONFIGURED 25 patches), and
# no floor for it existed — so "F's assimilate is 1.20x the C's" and, worse, "F
# reproduces 8 % of the C's warming change" had nothing to be significant against.
#
# WHAT IT DOES. Reads seed1 and seed2 of the same scenario's `ind` table over one
# window, forms that statistic per (cell, year) on ONE population definition, and
# reports the two-seed spread per cell-year and on the 10-year mean. Run it for
# both scenarios and the response floor follows: the seed spread on the
# BETWEEN-WINDOW change is what a claimed response has to beat.
#
# ⚠ POPULATION. `Type <= 6` and `D95max > 0` (grass rows have their tree fields
# zeroed, ADR 0110), living AND dead stems — mortality is applied after allocation,
# so a stem that dies this year still assimilated (ADR 0125). Divided by the
# CONFIGURED npatch = 25, never the occupied count (ADR 0111 §4). This is the same
# quantity as the probe's `bmi_C` but NOT the same rows: the probe restricts to the
# stems it could PAIR across two years. Stated rather than reconciled — a floor on
# the unpaired population is the conservative one.
#
# Usage:
#   SCENARIO=historic Y0=2010 Y1=2019 python3 scripts/diagnose_c_assimilate_noise.py
#   SCENARIO=ssp370   Y0=2090 Y1=2099 python3 scripts/diagnose_c_assimilate_noise.py
#   SCENARIO=historic Y0=2010 Y1=2019 SCENARIO_B=ssp370 Y0B=2090 Y1B=2099 \\
#     python3 scripts/diagnose_c_assimilate_noise.py     # + the RESPONSE floor
# =============================================================================
import os
import sys

import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_biome_forcing import cells_from_env  # noqa: E402  (THE canonical cell registry)

NPATCH = 25
SEEDS = {
    "historic": (
        "/p/tmp/jamirp/emulator_global/ind_hist_seed1_all.parquet",
        "/p/tmp/jamirp/emulator_global/ind_hist_seed2_all.parquet",
    ),
    "ssp370": (
        "/p/tmp/jamirp/emulator_global/ind_ssp370_seed1_all.parquet",
        "/p/tmp/jamirp/emulator_global/ind_ssp370_seed2_all.parquet",
    ),
}


def per_cell_year(path, ids, y0, y1):
    """-> {(cell, year): assimilate in gC/m2/yr} on the documented population."""
    df = (
        pl.scan_parquet(path)
        .filter(
            (pl.col("Cell").is_in(ids))
            & (pl.col("Year").is_between(y0, y1))
            & (pl.col("Type") <= 6)
            & (pl.col("D95max") > 0)
        )
        .group_by(["Cell", "Year"])
        .agg(pl.col("npp").sum().alias("npp"))
        .collect()
    )
    # ADR 0036 §5b: assert the key set rather than trusting a row count.
    assert df.select(["Cell", "Year"]).n_unique() == df.height, "duplicated (Cell, Year) key"
    return {(r["Cell"], r["Year"]): r["npp"] / NPATCH for r in df.iter_rows(named=True)}


def main():
    scen = os.environ.get("SCENARIO", "historic")
    y0 = int(os.environ.get("Y0", "2010"))
    y1 = int(os.environ.get("Y1", "2019"))
    if scen not in SEEDS:
        raise SystemExit(f"FATAL: SCENARIO={scen} not in {sorted(SEEDS)}")
    cells = cells_from_env()
    ids = [c for _, c in cells]
    p1, p2 = SEEDS[scen]
    a = per_cell_year(p1, ids, y0, y1)
    b = per_cell_year(p2, ids, y0, y1)

    print(f"== {scen} {y0}-{y1}: the C's OWN two-seed spread on per-cell annual tree assimilate")
    print(f"== population: Type<=6 & D95max>0, living AND dead, / npatch={NPATCH} (configured)")
    print(f"{'cell':24s} {'seed1_mean':>10s} {'seed2_mean':>10s} {'mean |rel|':>10s} "
          f"{'max |rel|':>9s} {'10yr-mean rel':>13s} {'n_yr':>4s}")
    for name, cell in cells:
        rel, m1, m2, n = [], 0.0, 0.0, 0
        for y in range(y0, y1 + 1):
            v1, v2 = a.get((cell, y)), b.get((cell, y))
            if v1 is None or v2 is None:
                continue
            mid = 0.5 * (v1 + v2)
            if abs(mid) > 1e-9:
                rel.append(abs(v1 - v2) / abs(mid))
            m1 += v1
            m2 += v2
            n += 1
        if n == 0:
            print(f"{name:24s} {'-':>10s} {'-':>10s} {'-':>10s} {'-':>9s} {'-':>13s} {0:4d}")
            continue
        m1 /= n
        m2 /= n
        wm = abs(m1 - m2) / abs(0.5 * (m1 + m2)) if abs(m1 + m2) > 1e-9 else float("nan")
        print(f"{name:24s} {m1:10.1f} {m2:10.1f} "
              f"{(sum(rel) / len(rel) if rel else float('nan')):10.3f} "
              f"{(max(rel) if rel else float('nan')):9.3f} {wm:13.3f} {n:4d}")
    print("\n`mean |rel|` is the per-cell-YEAR floor; `10yr-mean rel` is the climatology floor")
    print("(a 10-year mean averages ~sqrt(10) of the noise away — ADR 0111 §5: NAME THE BASIS).")
    print("Any F-vs-C assimilate claim must be quoted against the matching column.")

    # ── the RESPONSE floor: the same two seeds' BETWEEN-WINDOW change ────────────────────────────
    # A level spread does NOT bound a response claim. The response is a paired difference WITHIN a
    # seed, so its floor is the spread of that difference ACROSS seeds — which can be far tighter
    # than the level spread (a seed that runs warm in both windows cancels) or far looser.
    scen_b = os.environ.get("SCENARIO_B", "")
    if scen_b:
        y0b, y1b = int(os.environ["Y0B"]), int(os.environ["Y1B"])
        if scen_b not in SEEDS:
            raise SystemExit(f"FATAL: SCENARIO_B={scen_b} not in {sorted(SEEDS)}")
        q1, q2 = SEEDS[scen_b]
        c = per_cell_year(q1, ids, y0b, y1b)
        d = per_cell_year(q2, ids, y0b, y1b)
        print(f"\n== RESPONSE floor: {scen} {y0}-{y1} -> {scen_b} {y0b}-{y1b}, per seed")
        print(f"{'cell':24s} {'d_seed1':>9s} {'d_seed2':>9s} {'mean':>9s} {'spread':>9s} "
              f"{'|spread/mean|':>13s}")
        for name, cell in cells:
            def mean_of(tbl, ya, yb, cl=cell):
                v = [tbl[(cl, y)] for y in range(ya, yb + 1) if (cl, y) in tbl]
                return sum(v) / len(v) if v else float("nan")
            d1 = mean_of(c, y0b, y1b) - mean_of(a, y0, y1)
            d2 = mean_of(d, y0b, y1b) - mean_of(b, y0, y1)
            mu = 0.5 * (d1 + d2)
            sp = abs(d1 - d2)
            print(f"{name:24s} {d1:9.1f} {d2:9.1f} {mu:9.1f} {sp:9.1f} "
                  f"{(sp / abs(mu) if abs(mu) > 1e-9 else float('nan')):13.3f}")
        print("\nA claimed response is only readable where |spread/mean| is small: the two")
        print("seeds must agree on the SIZE, not just the sign, of the change the emulator")
        print("is asked to reproduce.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
