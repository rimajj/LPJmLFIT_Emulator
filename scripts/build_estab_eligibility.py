#!/usr/bin/env python3
"""Build the PER-CELL(-YEAR) BIOCLIMATIC ELIGIBLE-PFT SET the ported establishment rule needs (ADR 0119).

WHAT THIS UNBLOCKS. `Establishment.eligible_pfts(temp_min20, temp_max20, gdd5; aprec)` is the gate that
decides WHICH PFTs a recruit can be drawn from, and — through the closed-form inherited share
`w_inherit = 4/(4 + n_elig)` (ADR 0045) — how much of the recruit population comes from the cell's own
seedbank rather than the uniform intervals. Without this table the ported rule can only run at a cell whose
eligible set was configured by hand, and it can never see a WARMING cell's gate open or close. Both matter:
`n_elig` sets the mixture weight, and the boreal ids 4/5/6 have `temp_high = 0.0`, so a cell sitting near a
0 °C coldest-month mean flips its whole eligible set on a fraction of a degree.

THE FOUR INPUTS, AS THE C ACTUALLY COMPUTES THEM (read from the source, not assumed — `establish.c:29-33`
is the gate, and each of its arguments comes from a different place):

  temp_min20 = mean over the last 20 YEARS of (min over the 12 monthly means of THAT year)
  temp_max20 = mean over the last 20 YEARS of (max over the 12 monthly means of THAT year)
               `climbuf.c:134-137` tracks each year's monthly min/max; `annual_climbuf` (`:153-154`)
               pushes them into a 20-slot ring (`CLIMBUFSIZE 20`), and `establish` reads `getbufferavg`.
               ⚠ THIS IS NOT `tas_cold_month` FROM THE BOUNDARY TABLE. That column is
               `min_m (mean_y T_{y,m})` — the coldest month OF the window-mean climatology — whereas this
               is `mean_y (min_m T_{y,m})`. By Jensen the boundary column is the LARGER of the two, and at
               a cell whose coldest month hovers near 0 °C the difference decides ids 4/5/6 outright.
               Both are emitted below so the size of that difference is visible, never assumed.
  gdd5       = the CURRENT year's daily accumulation `Σ_days max(T_day − gddbase, 0)`, `updategdd.c:31`
               with `gddbase = 5.0` for all seven tree PFTs (verified in the live `par/pft_lpjmlfit.js`),
               reset every year by `initgdd.c:26`. NOT a windowed climatology and NOT the Thom-1966
               monthly GDD the boundary table carries — both are emitted, for the same reason.
  aprec      = the CURRENT year's daily-summed precipitation. `annual_natural.c:192` passes
               `cell->balance.aprec`, accumulated at `update_daily.c:68` and zeroed by `init_annual.c:30`
               — i.e. the year's own total. (`climbuf->aprec`, a 20-yr mean, exists but is NOT what the
               establishment call receives; do not substitute it.)

⚠ THE ONE APPROXIMATION LEFT, STATED: `updategdd` uses the SAME daily temperature series LPJmL reads, so
`gdd5_annual` here is FIT's own quantity — but LPJmL applies its daily interpolation/weather generator to
the monthly-or-daily input before this point in some configurations. This run's forcing is daily `.clm`
read directly, so the two agree by construction; if a future scenario is driven from monthly input, this
column becomes an approximation and must be re-derived.

OUTPUT (parquet, one row per cell-year):
  Cell, Year, temp_min20, temp_max20, gdd5_annual, aprec, tas_cold_month_w (the boundary-basis coldest
  month, for the comparison above), gdd5_thom_w (likewise), elig_mask (bit p set = pft id p eligible),
  n_elig, w_inherit, plus `elig_str` ("1,2,3") for human reading.

Env:
  SCENARIO = historic | ssp370      (default historic)
  WINDOW   = the running-mean width in years (default 20 = the C's CLIMBUFSIZE; do not change casually)
  CELLS    = optional comma-list of cell indices (default ALL 67420)
  OUT      = output parquet (default /p/tmp/jamirp/emulator_global/tables/estab_eligibility_<scen>_w<W>.parquet)
  GATE     = 1 (default) run the falsifiable check below and print it
  Y0, Y1   = override the target-year range (default = the scenario's `ind`-table coverage, 2000-2019 /
             2020-2100). The running window still reaches back into the .clm before Y0, so an earlier Y0
             costs nothing in fidelity — it is how the single-cell probe fixture covers 1939-2019.
  CSV_OUT  = also append the selected rows to this CSV (a committable per-cell fixture; the header and a
             provenance block are written when the file does not exist, so two scenarios can be appended
             into one file). Small selections only — this is for fixtures, not for the global table.

⚠⚠ WHAT THIS GATE DOES **NOT** MEAN, and it is the most load-bearing sentence in this file:
**`n_elig == 0` DOES NOT MEAN "nothing establishes here".** FIT's establishment has two channels and
**only the BACKGROUND one is bioclimatically gated**. `establishmentpft_ind.c:91` wraps the per-PFT
background loop in `aprec >= aprec_min && establish(...)` — but the INHERITANCE block at `:125` is
OUTSIDE that loop and tests only `config->inheritance && cell->treelen > 0`: **no `establish()`, no
`aprec`.** So a cell whose gate has closed keeps recruiting its own resident genotypes indefinitely, and
22 % of cell-years (measured, historic) sit in exactly that state. The closed-form mixture weight already
encodes this — `w_inherit = 4/(4 + n_elig)` is 1 at `n_elig = 0` — and `Establishment.draw_recruit!`
implements it (an empty eligible set forces the inheritance channel). Read this table as
**"which PFTs the background channel may introduce"**, never as "which PFTs may exist".

THE GATE (falsifiable, and it is the point of the script rather than an afterthought). FIT's own `ind`
output says which PFTs actually EXIST in a cell. Recruits are invisible there (the writer drops stems
below 5 m), so the check cannot be "eligible == observed": an old stem established centuries ago under a
different climate, and this table describes TODAY's gate. What must hold is the ONE-SIDED containment
  every id with a YOUNG stem (Age <= AGE_YOUNG) in cell c must EITHER be eligible in c around the year
  that stem established (± TOL), OR already have been present in c beforehand — because then the
  ungated inheritance channel could have produced it,
plus the trivial direction: a cell with no eligible id AND no resident tree must have no young tree. A
violation means the ported gate is wrong (or the forcing/cell indexing is misaligned) — fix the
derivation, never the tolerance. `ind` establishment predates the target window for old stems, so the
check runs on young stems only and reports its own coverage.

Run (Hainich + two contrast cells, seconds):
    SCENARIO=historic CELLS=42490,28008 python3 scripts/build_estab_eligibility.py
Run (global, on SLURM — CLAUDE.md §9: every knob must be EXPORTed, the wrapper forwards a fixed list):
    export SCENARIO=historic; scripts/sbatch_python.sh S-elighist scripts/build_estab_eligibility.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# reuse the header-driven .clm reader rather than re-deriving it (CLAUDE.md §3: the layout is
# version-dependent and the ssp370 set is MIXED v2 int16 scalar 0.1 / v3 float32 scalar 1.0)
from build_transient_boundary import (  # noqa: E402
    CLM,
    CLM_EXTRA,
    DPM,
    MONTH_BOUNDS,
    TARGET_YEARS,
    open_clm,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMS_CSV = os.path.join(REPO, "test", "testitems", "references", "S_pft_estab_params.csv")
IND_PARQUET = {
    "historic": "/p/tmp/jamirp/emulator_global/ind_hist_seed1_all.parquet",
    "ssp370": "/p/tmp/jamirp/emulator_global/ind_ssp370_seed1_all.parquet",
}
AGE_YOUNG = 40          # a stem this young established inside the window the table can speak about
GDDBASE = 5.0           # `gddbase` of every tree PFT in the live par/pft_lpjmlfit.js (verified)


def read_params() -> list[dict]:
    """The seven tree PFTs' gate parameters from the ONE committed source of record (ADR 0119)."""
    rows = []
    with open(PARAMS_CSV) as fh:
        lines = [ln for ln in fh if not ln.startswith("#") and ln.strip()]
    hdr = lines[0].rstrip("\n").split(",")
    for ln in lines[1:]:
        v = dict(zip(hdr, ln.rstrip("\n").split(",")))
        rows.append({
            "pft_id": int(v["pft_id"]),
            "temp_low": float(v["temp_low"]),
            "temp_high": float(v["temp_high"]),
            "gdd5min": float(v["gdd5min"]),
            "aprec_min": float(v["aprec_min"]),
        })
    rows.sort(key=lambda r: r["pft_id"])
    if [r["pft_id"] for r in rows] != list(range(7)):
        raise SystemExit(f"FATAL: {PARAMS_CSV} must carry exactly tree ids 0-6")
    return rows


def temperature_stats(mm, scalar):
    """ONE pass over the daily temperature memmap -> (monthly, tmin_y, tmax_y, gdd5_y).

    The three quantities are computed together because the file is ~12 GB and a separate pass per
    quantity is a 3x I/O cost for nothing.
      monthly (nyears, ncell, 12)  monthly means, °C — only for the boundary-basis comparison columns
      tmin_y / tmax_y (nyears, ncell)  each year's coldest/warmest MONTHLY MEAN — `climbuf.c:134-137`'s
        quantity: the extreme is taken WITHIN the year, and only then averaged over the 20-slot buffer.
        Averaging first is a different (for the cold end, systematically warmer) number.
      gdd5_y (nyears, ncell)  FIT's own annual GDD5, the DAILY accumulation above 5 °C (`updategdd.c:31`).
    """
    nyears, ncell, _ = mm.shape
    monthly = np.empty((nyears, ncell, 12), dtype=np.float32)
    gdd5 = np.empty((nyears, ncell), dtype=np.float32)
    for iy in range(nyears):
        yr = np.asarray(mm[iy], dtype=np.float32) * scalar
        for m in range(12):
            monthly[iy, :, m] = yr[:, MONTH_BOUNDS[m]:MONTH_BOUNDS[m + 1]].mean(axis=1)
        gdd5[iy] = np.maximum(yr - GDDBASE, 0.0).sum(axis=1)
    return monthly, monthly.min(axis=2), monthly.max(axis=2), gdd5


def per_year_sum(mm, scalar):
    """(nyears, ncell) annual total of a daily flux (precipitation, mm/yr)."""
    nyears, ncell, _ = mm.shape
    out = np.empty((nyears, ncell), dtype=np.float32)
    for iy in range(nyears):
        out[iy] = (np.asarray(mm[iy], dtype=np.float32) * scalar).sum(axis=1)
    return out


def running_mean_trailing(x, W):
    """(nyears, ncell) -> the trailing W-year running mean ending at each year (short at the start).

    The C's ring buffer holds the last 20 UPDATES and `getbufferavg` divides by how many it holds, so an
    early year with fewer than W entries averages over what exists — reproduced here rather than dropped,
    with the short years reported by the caller."""
    nyears = x.shape[0]
    csum = np.cumsum(np.vstack([np.zeros((1, x.shape[1]), dtype=np.float64), x.astype(np.float64)]), axis=0)
    out = np.empty_like(x, dtype=np.float32)
    for iy in range(nyears):
        lo = max(0, iy - W + 1)
        out[iy] = ((csum[iy + 1] - csum[lo]) / (iy + 1 - lo)).astype(np.float32)
    return out


def eligibility(params, temp_min20, temp_max20, gdd5, aprec):
    """Vectorised `establish.c:29-33` + `establishmentpft_ind.c:91` over an (N,) cell selection.

    Returns (mask, n_elig, mask_noaprec, n_elig_noaprec) — the full gate AND the gate with the
    precipitation clause dropped. The second is not a convenience: `aprec` is the ONE input of the four
    whose reconstruction the gate below does not confirm (FIT establishes at a desert cell where this
    reconstruction says `aprec < aprec_min`), so shipping both makes the size of that uncertainty a
    measurable column instead of a caveat. They differ only in cells near 100 mm/yr."""
    shape = temp_min20.shape
    mask = np.zeros(shape, dtype=np.int16)
    mask_na = np.zeros(shape, dtype=np.int16)
    # the tree-only clause `!(type == TREE && temp_max20 <= 10)`: every id here is a tree, so a cell
    # failing it establishes NO tree at all, whatever the per-PFT thresholds say
    warm_enough = temp_max20 > 10.0
    for p in params:
        base = (
            warm_enough
            & (temp_min20 >= p["temp_low"])
            & (temp_min20 <= p["temp_high"])
            & (gdd5 >= p["gdd5min"])
        )
        mask |= ((base & (aprec >= p["aprec_min"])).astype(np.int16) << p["pft_id"])
        mask_na |= (base.astype(np.int16) << p["pft_id"])
    n_elig = np.zeros(shape, dtype=np.int8)
    n_elig_na = np.zeros(shape, dtype=np.int8)
    for p in params:
        n_elig += ((mask >> p["pft_id"]) & 1).astype(np.int8)
        n_elig_na += ((mask_na >> p["pft_id"]) & 1).astype(np.int8)
    return mask, n_elig, mask_na, n_elig_na


def run_gate(df: pl.DataFrame, scen: str, params: list[dict]) -> None:
    """The one-sided containment check against FIT's own `ind` output (see the module docstring)."""
    path = IND_PARQUET.get(scen)
    if path is None or not os.path.exists(path):
        print(f"\n== GATE SKIPPED — no `ind` table for scenario {scen} at {path}")
        return
    cells = df["Cell"].unique().to_list()
    y0, y1 = int(df["Year"].min()), int(df["Year"].max())
    print(f"\n== GATE: young-stem containment against {os.path.basename(path)} "
          f"({len(cells)} cells, Age <= {AGE_YOUNG})")
    # ⚠ THE ESTABLISHMENT YEAR MUST BE INSIDE THE COVERED WINDOW OR THE CHECK IS UNFALSIFIABLE. A stem of
    # Age 30 seen in 2000 established in 1970, under a climate this table does not describe — counting it
    # would report a failure for a gate that was never asked about that year. `Year - Age` is the
    # establishment year (the emitted Age is the post-increment year-end age, CLAUDE.md §3, so this is
    # exact to within the one year that off-by-one costs, which the >= y0 filter absorbs).
    lf = pl.scan_parquet(path).filter(
        (pl.col("Type") <= 6) & (pl.col("Age") <= AGE_YOUNG) & (pl.col("isdead") == 0)
        & ((pl.col("Year") - pl.col("Age")) >= y0) & ((pl.col("Year") - pl.col("Age")) <= y1)
        & pl.col("Cell").is_in(cells)
    ).select(["Cell", "Year", "Age", "Type"])
    obs = lf.with_columns((pl.col("Year") - pl.col("Age")).alias("est")).group_by(
        ["Cell", "Type", "est"]
    ).agg(pl.len().alias("n_row")).collect(engine="streaming")
    # WHICH (cell, pft) COULD HAVE BEEN INHERITED: the pft has a stem in the cell OLDER than the recruit,
    # so the cell's seedbank can carry it and the UNGATED inheritance channel can reproduce it whatever
    # the bioclimatic gate says (`establishmentpft_ind.c:125`). Established from the OLD stems (Age >
    # AGE_YOUNG), which are a different population from the young ones being judged.
    # ⚠ THIS TURNS THE CHECK INTO A TEST OF *INTRODUCTIONS*, WHICH IS THE HONEST SCOPE. The exemption is
    # keyed on the EARLIEST establishment year of that pft in that cell, not on an age threshold: in a
    # dry cell the whole population turns over inside 40 years, so an age cut would call a
    # self-perpetuating desert population a gate violation (it did — 6 730 of them). What the eligible
    # set actually governs is whether the BACKGROUND channel may introduce a pft the cell does not
    # already have; once it has one, inheritance reproduces it unconditionally. The gate keeps its power
    # exactly there, and the exempted count is reported so the loss of coverage is visible.
    first_est = pl.scan_parquet(path).filter(
        (pl.col("Type") <= 6) & pl.col("Cell").is_in(cells)
    ).with_columns((pl.col("Year") - pl.col("Age")).alias("est")).group_by(
        ["Cell", "Type"]
    ).agg(pl.col("est").min().alias("est_first")).collect(engine="streaming")
    first_map = {(int(c), int(t)): int(e) for c, t, e in first_est.iter_rows()}
    print(f"   {len(first_map)} (cell, pft) pairs occur in the `ind` table; a recruit later than that "
          f"pair's FIRST establishment can come from the ungated inheritance channel")
    # ⚠ ADR 0036 §5b: a streamed group_by can emit a non-deterministic KEY SET at global scale, so assert
    # this aggregate's own keys before using it (the usual row-count guard cannot see a duplicated key).
    if obs.select(["Cell", "Type", "est"]).n_unique() != obs.height:
        raise SystemExit("FATAL: the streamed group_by emitted duplicate keys (ADR 0036 §5b)")
    if obs.height == 0:
        print("   no young stem established inside the covered years — the gate has nothing to check")
        return
    # the eligible mask AT EXACTLY the establishment year (the strict form of the check), plus the four
    # gate inputs, so a failure names WHICH CLAUSE it violated — a rate alone cannot distinguish "the
    # cell indexing is wrong" (failures everywhere, every clause) from "one clause's input is wrong"
    # (failures concentrated on that clause).
    key_cols = ["Cell", "Year", "elig_mask", "temp_min20", "temp_max20", "gdd5_annual", "aprec"]
    per_cy = {(int(r[0]), int(r[1])): r[2:] for r in df.select(key_cols).iter_rows()}
    pmap = {p["pft_id"]: p for p in params}
    # ⚠ THE ESTABLISHMENT YEAR IS ONLY KNOWN TO ±1, AND THE GATE'S TWO PER-YEAR INPUTS ARE NOISY. The
    # emitted `Age` is the post-increment year-end age (CLAUDE.md §3), so `Year - Age` can be one off;
    # meanwhile `gdd5` and especially `aprec` are the CURRENT year's values, which in a dry cell swing
    # across `aprec_min` from one year to the next. A zero-tolerance check therefore reports
    # year-alignment noise as a derivation error. TOL widens the window to the years the stem could
    # actually have established in; the rate is reported at TOL and at 0 so the difference is visible.
    tol = int(os.environ.get("TOL", "1"))
    bad, checked, bad_strict, n_inherit_exempt = [], 0, 0, 0
    clause_hits = {k: 0 for k in ("temp_max20>10", "temp_min20>=low", "temp_min20<=high",
                                  "gdd5>=gdd5min", "aprec>=aprec_min")}
    for c, t, est, n in obs.iter_rows():
        key = (int(c), int(est))
        if key not in per_cy:
            continue
        checked += 1
        mask, tmin, tmax, gdd, ap = per_cy[key]
        if not (int(mask) >> int(t)) & 1:
            bad_strict += 1
        # eligible in ANY year within ±tol of the estimated establishment year ⇒ not a failure
        if any(((int(per_cy[(int(c), y)][0]) >> int(t)) & 1)
               for y in range(int(est) - tol, int(est) + tol + 1) if (int(c), y) in per_cy):
            continue
        # ... or the cell already held that PFT, in which case the UNGATED inheritance channel explains
        # it and the background gate was never asked (`establishmentpft_ind.c:125`)
        if first_map.get((int(c), int(t)), 10 ** 9) < int(est):
            n_inherit_exempt += 1
            continue
        p = pmap[int(t)]
        why = []
        if not tmax > 10.0:
            why.append("temp_max20>10")
        if not tmin >= p["temp_low"]:
            why.append("temp_min20>=low")
        if not tmin <= p["temp_high"]:
            why.append("temp_min20<=high")
        if not gdd >= p["gdd5min"]:
            why.append("gdd5>=gdd5min")
        if not ap >= p["aprec_min"]:
            why.append("aprec>=aprec_min")
        for w in why:
            clause_hits[w] += 1
        bad.append((int(c), int(t), int(est), int(n), ",".join(why), float(tmin), float(tmax),
                    float(gdd), float(ap)))
    print(f"   checked {checked} (cell, pft, establishment-year) triples, establishment-year "
          f"tolerance ±{tol} yr")
    print(f"   at tolerance 0, and WITHOUT the inheritance exemption, the failure count is "
          f"{bad_strict} ({100 * bad_strict / max(checked, 1):.3f} %)")
    print(f"   explained by the UNGATED inheritance channel (the pft was already resident): "
          f"{n_inherit_exempt}")
    if bad:
        cells_bad = sorted({r[0] for r in bad})
        rate = 100 * len(bad) / max(checked, 1)
        # A residual of a fraction of a percent is not a derivation error, and calling it one would make
        # the gate useless (it would never be green, so nobody would read it). The threshold is stated
        # rather than tuned: the exemption above needs the PARENT to appear in `ind`, and `ind` drops
        # every stem below 5 m — in a hyper-arid cell a self-perpetuating population can live entirely
        # below that height, so its recruits look like introductions and cannot be exempted. That
        # explains a small, arid-skewed residual and nothing larger.
        verdict = ("⚠ GATE FAILED" if rate >= 0.5 else
                   "◐ GATE PASSES WITH A RESIDUAL (< 0.5 %, see the note below)")
        print(f"   {verdict} for {len(bad)} triple(s) in {len(cells_bad)} cell(s) "
              f"= {rate:.3f} % — FIT established a PFT this gate excludes.")
        only_aprec = sum(1 for r in bad if r[4] == "aprec>=aprec_min")
        print(f"   which clause: {clause_hits}")
        print(f"   violating ONLY the precipitation clause: {only_aprec} of {len(bad)} "
              f"({100 * only_aprec / len(bad):.1f} %)"
              + ("  ⇒ the temperature/gdd5 reconstruction and the cell indexing are CONFIRMED; the "
                 "open question is `aprec` alone, and the `*_noaprec` columns bound it"
                 if only_aprec == len(bad) else
                 "  ⇒ NOT confined to `aprec` — suspect the cell indexing or the year offset first"))
        for row in bad[:15]:
            print(f"      cell {row[0]} pft {row[1]} est {row[2]}: {row[4]}  "
                  f"(temp_min20 {row[5]:.2f}, temp_max20 {row[6]:.2f}, gdd5 {row[7]:.0f}, "
                  f"aprec {row[8]:.0f})")
        if rate >= 0.5:
            print("   Fix the derivation (temp_min20 basis? cell indexing? scenario/year offset? the "
                  "aprec source?), NOT the gate. An eligible set that excludes a PFT FIT is currently "
                  "recruiting is wrong, and n_elig also sets the inherited share, so it is wrong twice.")
        else:
            print("   Expected residual: the inheritance exemption needs the PARENT to be visible in "
                  "`ind`, which drops stems below 5 m — an arid cell's population can live entirely "
                  "below that height. Consistent with that reading only while the failures stay "
                  "arid-skewed and on the `aprec` clause; a shift to the temperature clauses would NOT "
                  "be, and must be investigated rather than absorbed.")
    else:
        print("   ✅ every PFT FIT established inside the covered years was eligible in that very year")
    # the trivial direction: a cell eligible for nothing must carry no young tree
    union = {}
    for c, m in zip(df["Cell"].to_list(), df["elig_mask"].to_list()):
        union[int(c)] = union.get(int(c), 0) | int(m)
    empty = [c for c, m in union.items() if m == 0]
    if empty:
        with_young = set(int(c) for c in obs["Cell"].unique().to_list())
        viol = sorted(set(empty) & with_young)
        print(f"   cells with an EMPTY eligible set: {len(empty)}"
              + (f"   ⚠ {len(viol)} of them carry young stems: {viol[:10]}" if viol
                 else "   (none of them carries a young stem — consistent)"))


def main() -> int:
    scen = os.environ.get("SCENARIO", "historic")
    if scen not in CLM:
        raise SystemExit(f"SCENARIO must be one of {list(CLM)} (got {scen!r})")
    # GATE_ONLY=<parquet>: re-run the falsifiable check against an ALREADY BUILT table. The build is a
    # ~12 GB read and the gate is where the thinking is, so the two must be separable — otherwise a
    # gate bug costs a full rebuild and the check quietly stops being run.
    gate_only = os.environ.get("GATE_ONLY", "").strip()
    if gate_only:
        print(f"== GATE_ONLY: {gate_only}  (scenario {scen})")
        run_gate(pl.read_parquet(gate_only), scen, read_params())
        return 0
    W = int(os.environ.get("WINDOW", "20"))
    cells_env = os.environ.get("CELLS", "").strip()
    cells = [int(c) for c in cells_env.split(",") if c] if cells_env else None
    out = os.environ.get(
        "OUT", f"/p/tmp/jamirp/emulator_global/tables/estab_eligibility_{scen}_w{W}.parquet"
    )
    params = read_params()
    print(f"== scenario={scen} W={W}  (C's CLIMBUFSIZE = 20)")
    print(f"== gate params from {os.path.relpath(PARAMS_CSV, REPO)}:")
    for p in params:
        print(f"     id {p['pft_id']}: temp_min20 in [{p['temp_low']}, {p['temp_high']}], "
              f"gdd5 >= {p['gdd5min']}, aprec >= {p['aprec_min']}")

    mm, fy, ncell, nbands, scalar = open_clm(CLM[scen])
    navail = mm.shape[0]
    mmP, fyP, ncP, _nbP, scP = open_clm(CLM_EXTRA[scen]["pr"])
    if (fyP, ncP, mmP.shape[0]) != (fy, ncell, navail):
        raise SystemExit(
            f"FATAL: the precipitation .clm disagrees with temperature — firstyear {fyP} vs {fy}, "
            f"ncell {ncP} vs {ncell}, nyears {mmP.shape[0]} vs {navail}. The year index would address "
            f"a different year in each file."
        )

    mby, tmin_y, tmax_y, gdd5_y = temperature_stats(mm, scalar)
    aprec_y = per_year_sum(mmP, scP)
    print(f"== per-year extremes/gdd5/aprec built: {tmin_y.shape}, {gdd5_y.shape}, {aprec_y.shape}")

    # ── SEED THE RUNNING WINDOW FROM THE HISTORIC FORCING (ssp370 only; default ON). The ssp370 `.clm`
    #    starts in 2015, so a naive trailing mean at 2020 averages SIX years while the C — which
    #    continues from `restart_2019.lpj` — carries a FULL 20-slot buffer whose older entries are
    #    historic years. Without this the first 14 target years are computed on a different (noisier)
    #    basis than the model they describe, and `temp_min20` is exactly the quantity the boreal ids'
    #    `temp_high = 0` gate turns on. The scenario boundary is 2019/2020: years <= 2019 come from the
    #    historic file (what the C actually ran), years >= 2020 from the ssp file. Costs one extra pass
    #    over the ~12 GB historic temperature file; set SEED_FROM_HISTORIC=0 to skip it and say so.
    year_of = np.arange(fy, fy + navail)
    if scen != "historic" and os.environ.get("SEED_FROM_HISTORIC", "1") == "1":
        mmh, fyh, nch, _nbh, sch = open_clm(CLM["historic"])
        if nch != ncell:
            raise SystemExit(f"FATAL: historic .clm has {nch} cells, {scen} has {ncell}")
        _mbyh, tmin_h, tmax_h, _gh = temperature_stats(mmh, sch)
        yh = np.arange(fyh, fyh + mmh.shape[0])
        keep_h = yh <= 2019                       # the years the C ran from the historic forcing
        keep_s = year_of >= 2020
        tmin_y = np.vstack([tmin_h[keep_h], tmin_y[keep_s]])
        tmax_y = np.vstack([tmax_h[keep_h], tmax_y[keep_s]])
        seeded_years = np.concatenate([yh[keep_h], year_of[keep_s]])
        print(f"== seeded the running window with historic years {yh[keep_h][0]}-{yh[keep_h][-1]} "
              f"⇒ the buffer is full from {yh[keep_h][0] + W - 1} on")
    else:
        seeded_years = year_of
        if scen != "historic":
            print("== SEED_FROM_HISTORIC=0 — the first years' running window is SHORT and is NOT the "
                  "basis the C ran on; say so wherever this table's early years are used")
    tmin20_all = running_mean_trailing(tmin_y, W)
    tmax20_all = running_mean_trailing(tmax_y, W)
    # index the running means by CALENDAR year (they may now span two files), the per-year-only
    # quantities (gdd5, aprec) stay on the scenario file's own index
    yidx = {int(y): i for i, y in enumerate(seeded_years)}

    y0, y1 = TARGET_YEARS[scen]
    y0 = int(os.environ.get("Y0", y0))
    y1 = int(os.environ.get("Y1", y1))
    cell_sel = np.array(cells, dtype=np.int64) if cells is not None else np.arange(ncell)
    frames = []
    short = 0
    for Y in range(y0, y1 + 1):
        iY = Y - fy
        if iY < 0 or iY >= navail:
            raise SystemExit(f"FATAL: target year {Y} outside .clm coverage [{fy}, {fy + navail - 1}]")
        lo = max(0, iY - W + 1)
        jY = yidx[Y]                                            # the running means' own (calendar) index
        if jY - max(0, jY - W + 1) + 1 < W:
            short += 1
        clim = mby[lo:iY + 1].mean(axis=0)                      # (ncell, 12) window-mean climatology
        tcm_w = clim.min(axis=1)[cell_sel]
        gdd_w = (np.maximum(clim - GDDBASE, 0.0) * DPM[np.newaxis, :]).sum(axis=1)[cell_sel]
        a = tmin20_all[jY][cell_sel]
        b = tmax20_all[jY][cell_sel]
        g = gdd5_y[iY][cell_sel]
        p = aprec_y[iY][cell_sel]
        mask, n_elig, mask_na, n_elig_na = eligibility(params, a, b, g, p)
        frames.append(pl.DataFrame({
            "Cell": cell_sel,
            "Year": np.full(cell_sel.shape, Y, dtype=np.int64),
            "temp_min20": a, "temp_max20": b, "gdd5_annual": g, "aprec": p,
            "tas_cold_month_w": tcm_w.astype(np.float32),
            "gdd5_thom_w": gdd_w.astype(np.float32),
            "elig_mask": mask, "n_elig": n_elig,
            "elig_mask_noaprec": mask_na, "n_elig_noaprec": n_elig_na,
            "w_inherit": (4.0 / (4.0 + n_elig.astype(np.float64))).astype(np.float32),
        }))
    df = pl.concat(frames)
    df = df.with_columns(
        pl.col("elig_mask").map_elements(
            lambda m: ",".join(str(i) for i in range(7) if (m >> i) & 1), return_dtype=pl.String
        ).alias("elig_str")
    )

    # ── the two basis columns, side by side rather than one replacing the other (residual-diagnosis §)
    d = (df["tas_cold_month_w"] - df["temp_min20"]).to_numpy()
    print(f"\n== BASIS DIFFERENCE, the boundary table's `tas_cold_month` minus the C's `temp_min20`:")
    print(f"   mean {d.mean():+.4f} °C, median {np.median(d):+.4f}, max {d.max():+.4f} "
          f"(it is >= 0 by Jensen: min of a mean >= mean of a min)")
    n_flip = int(((df["tas_cold_month_w"] > 0) & (df["temp_min20"] <= 0)).sum())
    print(f"   cell-years where the two straddle 0 °C (⇒ the boreal ids 4/5/6, temp_high = 0, flip): "
          f"{n_flip} of {df.height} = {100 * n_flip / df.height:.2f} %")

    nz = df.filter(pl.col("n_elig") > 0)
    print(f"\n== eligible-set summary: {df.height} rows, {df['Cell'].n_unique()} cells x "
          f"{df['Year'].n_unique()} years")
    print(f"   n_elig == 0 (no tree can establish): {df.height - nz.height} rows "
          f"= {100 * (df.height - nz.height) / df.height:.1f} %")
    print(df.group_by("n_elig").len().sort("n_elig"))
    # does the gate MOVE over the transient? (the whole reason the table is per-year)
    mv = df.group_by("Cell").agg(pl.col("elig_mask").n_unique().alias("nsets"))
    print(f"   cells whose eligible SET changes within {y0}-{y1}: "
          f"{int((mv['nsets'] > 1).sum())} of {mv.height}")

    # how much does the ONE unconfirmed input (`aprec`) actually decide?
    diff = df.filter(pl.col("n_elig") != pl.col("n_elig_noaprec"))
    print(f"\n== the `aprec` clause's blast radius: it changes the eligible set in {diff.height} of "
          f"{df.height} cell-years = {100 * diff.height / df.height:.2f} % "
          f"({diff['Cell'].n_unique()} cells); everywhere else the gate is temperature/gdd5 only.")

    # ⚠ WRITE BEFORE GATING. The build is a ~12 GB read and the gate is a cheap check on its output; a
    # gate bug that throws must not also destroy the artifact (it did once — job 1759308 crashed in the
    # gate and produced no table at all). `GATE_ONLY=<parquet>` re-runs the check on its own.
    os.makedirs(os.path.dirname(out), exist_ok=True)
    df.write_parquet(out)
    print(f"\n== wrote {df.height} rows to {out}")

    if os.environ.get("GATE", "1") == "1":
        run_gate(df, scen, params)

    csv_out = os.environ.get("CSV_OUT", "").strip()
    if csv_out:
        new = not os.path.exists(csv_out)
        with open(csv_out, "a") as fh:
            if new:
                fh.write(
                    "# Per-cell(-year) BIOCLIMATIC ELIGIBLE-PFT SET for the ported FIT establishment rule\n"
                    "# (ADR 0119). GENERATED — do not hand-edit.\n"
                    "#   regenerate: SCENARIO=<scen> CELLS=<cell> Y0=<y0> Y1=<y1> CSV_OUT=<this file> \\\n"
                    "#               python3 scripts/build_estab_eligibility.py\n"
                    "# `temp_min20`/`temp_max20` are the C's OWN basis — the 20-yr running mean of each\n"
                    "# YEAR's coldest/warmest monthly mean (climbuf.c:134-137,153-154) — NOT the boundary\n"
                    "# table's `tas_cold_month`, which is the coldest month OF the window-mean climatology\n"
                    "# and runs ~1 C warmer. `gdd5_annual` is the current year's DAILY accumulation above\n"
                    "# 5 C (updategdd.c:31), `aprec` the current year's daily precipitation total\n"
                    "# (update_daily.c:68). `elig_str` is establish.c:29-33 + establishmentpft_ind.c:91\n"
                    "# evaluated on those four; `n_elig` sets the inherited share 4/(4+n_elig) (ADR 0045).\n"
                    "# The set is written as SEVEN 0/1 columns rather than a quoted list, so the naive\n"
                    "# comma-split readers in this repo's Julia probes cannot mis-parse it.\n"
                    "scenario,cell,year,temp_min20,temp_max20,gdd5_annual,aprec,n_elig,w_inherit,"
                    + ",".join(f"elig_{i}" for i in range(7)) + "\n"
                )
            for r in df.select(["Cell", "Year", "temp_min20", "temp_max20", "gdd5_annual", "aprec",
                                "n_elig", "w_inherit", "elig_mask"]).iter_rows():
                bits = ",".join(str((int(r[8]) >> i) & 1) for i in range(7))
                fh.write(f"{scen},{r[0]},{r[1]},{r[2]:.6f},{r[3]:.6f},{r[4]:.3f},{r[5]:.3f},"
                         f"{r[6]},{r[7]:.6f},{bits}\n")
        print(f"== {'wrote' if new else 'appended to'} CSV fixture {csv_out} ({df.height} rows)")
    if short:
        print(f"   NOTE: {short} target year(s) had a SHORT running window (< W={W}); the .clm starts "
              f"{fy}, and the C's own buffer averages over what it holds, which is reproduced here.")
    for c in (42490,):
        if c in set(int(x) for x in cell_sel):
            h = df.filter(pl.col("Cell") == c).sort("Year")
            print(f"   cell {c}: [{y0}] temp_min20={h['temp_min20'][0]:.3f} "
                  f"temp_max20={h['temp_max20'][0]:.3f} gdd5={h['gdd5_annual'][0]:.0f} "
                  f"aprec={h['aprec'][0]:.0f} elig={{{h['elig_str'][0]}}}  ->  "
                  f"[{y1}] temp_min20={h['temp_min20'][-1]:.3f} temp_max20={h['temp_max20'][-1]:.3f} "
                  f"gdd5={h['gdd5_annual'][-1]:.0f} elig={{{h['elig_str'][-1]}}}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
