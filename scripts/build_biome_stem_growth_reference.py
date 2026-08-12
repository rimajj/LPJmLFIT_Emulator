#!/usr/bin/env python3
# =============================================================================
# build_biome_stem_growth_reference.py — the C-side PAIRED per-stem growth target
# for rung 3 (line M; EXECUTION_PLAN.md "Rung 3 — F alone, on the C's own canopy").
#
# WHY THIS EXISTS. Rung 3 asks whether F_diff's decadal canopy drift (crown cover
# +27 % to +65 % over 2010-2019 where the C's is flat, ADR 0053/0060) is the
# accumulation of a per-year growth bias or something the free-running loop
# manufactures. Answering it needs a comparison at the level F actually computes —
# ONE STEM, ONE YEAR — and until now every F-vs-C structural number in this repo
# was an aggregate, because nothing had established that individuals can be
# followed across years.
#
# THEY CAN. `(Cell, Patch, ID)` is a STABLE per-individual identity in the annual
# `ind` output. Verified on all five biome cells over 2010-2019 (10 323 pairs):
#   * `Age` increments by EXACTLY 1 on every pair (no exceptions),
#   * `SLA` and `Wooddens` are BIT-IDENTICAL across the pair — which is the
#     independent check, because traits are immutable after `new_tree`
#     (ADR 0046), so an identity that shuffled stems would break it,
#   * no stem emitted with `isdead == 1` is ever seen again, and
#   * essentially no living stem vanishes: 8 stem-years of 13 152 (0.06 %), ALL of
#     them within 0.4 m of the writer's 5 m emission threshold — they dipped back
#     under it and stopped being written (one is emitted again two years later).
#     So the year-(y+1) roster is {year-y survivors, grown} + the stems that newly
#     crossed 5 m, up to that flicker.
# That last fact is what makes the pairing COMPLETE rather than a subsample, and
# the gate below is on the vanished stems' HEIGHT, not on their count — a stem
# vanishing well above 5 m would mean the identity itself is broken.
#
# THE BASIS THIS FIXES (`residual-diagnosis` §1). The C's own year-over-year
# canopy change mixes GROWTH with MORTALITY and with recruits crossing 5 m, while
# F under `slow = nothing` has growth only. Comparing the two directly scores F's
# physics against the C's demography. The paired table below removes that by
# construction:
#   * the target for a stem is ITS OWN year-(y+1) row, INCLUDING when that row has
#     `isdead == 1` — mortality is applied AFTER allocation in `annual_natural.c`
#     (the hazard loop at :73 runs before the FPC output accumulation at :256),
#     so a stem that dies in year y+1 still grew through year y+1 first, and
#     dropping it would bias the C's mean growth UPWARD (mortality selects on low
#     growth efficiency) and make F look better than it is;
#   * recruits are reported as their own channel (`fpc_new`), never mixed into a
#     growth ratio.
#
# EMITS
#   <OUT>/M_stem_targets.csv                     — per-stem, per-year raw C state (big, /p/tmp)
#   test/testitems/references/M_stem_growth_reference.csv  — the per-(cell,year) summary (committed)
#
# THE COMMITTED SUMMARY CARRIES ITS OWN BASIS GATE: `fpc_live` (the patch-mean sum
# of `fpc_ind` over living >5 m stems) against the C's own `a_fpc` from
# `M_fdiff_oracle_biomes_annual.csv`. Their ratio IS the ">5 m fraction" of
# ADR 0060 — the part of the C's crown cover F cannot contain because the writer
# never emitted it. Every F-vs-C crown-cover ratio must be read against that
# column, not against 1.0.
#
# Usage (login node, ~30 s — one row-group-pruned scan of the 22 GB parquet):
#   /home/jamirp/.conda/envs/py311_new/bin/python scripts/build_biome_stem_growth_reference.py
# Env: CELLS="name:idx,..."  Y0 Y1  OUT
# =============================================================================
import os
import sys

import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_biome_forcing import cells_from_env  # noqa: E402  (THE canonical cell registry)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFDIR = os.path.join(REPO, "test", "testitems", "references")
# The scenario's `ind` table. DEFAULT = the historic seed1 run, the basis every committed
# fixture here was built from, so a bare re-run stays byte-identical. `SCENARIO=ssp370` (or an
# explicit `IND_PARQUET`) builds the same paired target set on the warmed run — which is what
# answers ADR 0106's binding clause "does F's growth error depend on climate?".
# ⚠ With a non-default table also redirect `OUT`; the committed summary below takes a scenario
# suffix so a warmed run cannot overwrite the historic reference.
_SCEN = {
    "historic": "/p/tmp/jamirp/emulator_global/ind_hist_seed1_all.parquet",
    "ssp370": "/p/tmp/jamirp/emulator_global/ind_ssp370_seed1_all.parquet",
}
SCENARIO = os.environ.get("SCENARIO", "historic")
IND_PARQUET = os.environ.get("IND_PARQUET", _SCEN.get(SCENARIO, _SCEN["historic"]))
NPATCH = 25                       # the CONFIGURED patch count (ADR 0111 §4: never the OCCUPIED one)

COLS = ["Cell", "Patch", "Year", "ID", "Type", "Age", "Height", "LAI", "SLA", "Wooddens",
        "fpc_ind", "agb", "vegc", "npp", "gpp", "isdead"]


def read_annual_oracle():
    """The committed C annual series, keyed (name, year) -> a_fpc crown cover."""
    out = {}
    path = os.path.join(REFDIR, "M_fdiff_oracle_biomes_annual.csv")
    if not os.path.exists(path):
        return out
    hdr = None
    for ln in open(path):
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        f = s.split(",")
        if hdr is None:
            hdr = f
            continue
        r = dict(zip(hdr, f))
        out[(r["name"], int(r["year"]))] = float(r["fpc_tree_crown"])
    return out


def main():
    cells = cells_from_env()
    y0 = int(os.environ.get("Y0", "2009"))
    y1 = int(os.environ.get("Y1", "2019"))
    out_dir = os.environ.get("OUT", "/p/tmp/jamirp/M_canopy_drift")
    os.makedirs(out_dir, exist_ok=True)
    ids = [c for _, c in cells]
    name_of = {c: n for n, c in cells}

    df = (
        pl.scan_parquet(IND_PARQUET)
        .filter((pl.col("Cell").is_in(ids)) & (pl.col("Year").is_between(y0, y1)) & (pl.col("Type") <= 6))
        .select(COLS)
        .collect()
        .sort(["Cell", "Year", "Patch", "ID"])
    )
    # ADR 0036 §5b: assert the key set rather than trusting a row count.
    assert df.select(["Cell", "Patch", "Year", "ID"]).n_unique() == df.height, \
        "(Cell,Patch,Year,ID) is not unique — the identity assumption is broken"
    print(f"== {df.height} tree stem-years over {len(ids)} cells, {y0}-{y1}")

    tgt = os.path.join(out_dir, "M_stem_targets.csv")
    df.with_columns(pl.col("Cell").replace_strict(name_of).alias("name")).write_csv(tgt)
    print(f"wrote {tgt}")

    ann = read_annual_oracle()
    summ = []
    for name, cell in cells:
        c = df.filter(pl.col("Cell") == cell)
        prev_live = None
        for y in range(y0, y1 + 1):
            yr = c.filter(pl.col("Year") == y)
            live = yr.filter(pl.col("isdead") == 0)
            key = set(zip(yr["Patch"].to_list(), yr["ID"].to_list()))
            new = key - prev_live if prev_live is not None else set()
            newmask = pl.struct(["Patch", "ID"]).map_elements(
                lambda s: (s["Patch"], s["ID"]) in new, return_dtype=pl.Boolean
            )
            fpc_new = yr.filter(newmask)["fpc_ind"].sum() / NPATCH if new else 0.0
            # `vanished` = a stem that was living last year and is not emitted this year. It must be
            # THRESHOLD FLICKER, not a broken identity: the writer emits only stems above 5 m
            # (`fwriteoutput_ind.c:84`), so a stem sitting just over it can drop back under and stop
            # being written (one of them is emitted again two years later). The gate below is on the
            # vanished stems' HEIGHT, not on their count.
            van = (prev_live - key) if prev_live is not None else set()
            vanished = len(van)
            van_h = 0.0
            if van:
                pv = c.filter(pl.col("Year") == y - 1)
                van_h = max(
                    h for p, i, h in zip(pv["Patch"].to_list(), pv["ID"].to_list(), pv["Height"].to_list())
                    if (p, i) in van
                )
            c_fpc = ann.get((name, y), float("nan"))
            fpc_live = live["fpc_ind"].sum() / NPATCH
            summ.append(dict(
                name=name, cell=cell, year=y,
                n_live=live.height, n_dead=yr.height - live.height, n_new=len(new),
                n_vanished=vanished, vanished_max_height=van_h,
                fpc_live=fpc_live,
                fpc_all=yr["fpc_ind"].sum() / NPATCH,
                fpc_new=fpc_new,
                fpc_dead=yr.filter(pl.col("isdead") == 1)["fpc_ind"].sum() / NPATCH,
                agb_live=live["agb"].sum() / NPATCH,
                npp_all=yr["npp"].sum() / NPATCH,
                c_a_fpc=c_fpc,
                gt5m_frac=fpc_live / c_fpc if c_fpc == c_fpc and c_fpc > 0 else float("nan"),
            ))
            prev_live = set(zip(live["Patch"].to_list(), live["ID"].to_list()))

    nvan = sum(r["n_vanished"] for r in summ)
    hvan = max((r["vanished_max_height"] for r in summ), default=0.0)
    assert hvan < 5.5, (
        f"a stem {hvan:.2f} m tall vanished between years — that is too far above the writer's 5 m "
        "emission threshold to be flicker, so the (Cell,Patch,ID) identity does NOT hold"
    )
    print(f"== identity gate: {nvan} vanished stem-years of {df.height}, tallest {hvan:.3f} m "
          f"(threshold flicker at the writer's 5 m cut) — PASS")

    hdr = list(summ[0].keys())
    # The committed summary is the HISTORIC reference. A scenario run writes its own file
    # rather than overwriting it: a fixture silently rebuilt on a different forcing is the
    # ADR 0032 stale-fixture trap in its worst form, because nothing in the file would say
    # which climate it is on.
    suffix = "" if SCENARIO == "historic" else f"_{SCENARIO}"
    path = os.path.join(REFDIR, f"M_stem_growth_reference{suffix}.csv")
    with open(path, "w") as f:
        f.write("# M_stem_growth_reference.csv — per-(cell,year) accounting of LPJmL-FIT's own tree stems at the\n")
        f.write(f"# five biome cells (seed1 {SCENARIO}), built for rung 3. `(Cell,Patch,ID)` is a\n")
        f.write("# stable cross-year individual identity: essentially every living stem of year y-1 is\n")
        f.write("# present in year y, so year y's roster = {y-1 survivors, grown} + n_new stems that\n")
        f.write("# newly crossed the writer's 5 m emission threshold. The only exception is\n")
        f.write("# THRESHOLD FLICKER:\n")
        f.write("# n_vanished stems dropped back under 5 m and stopped being emitted (all under 5.4 m, 8\n")
        f.write("# stem-years in 13 152 — one of them is emitted again two years later).\n")
        f.write("# fpc_* are patch means (sum of `fpc_ind` / 25 configured patches) of the CROWN-cover form\n")
        f.write("# a_fpc (`fpc_tree.c:28`), not the leaf-area a_fpc_stand (ADR 0060).\n")
        f.write("#   fpc_live = living stems (the stand entering the next year)  <- F's initial condition\n")
        f.write("#   fpc_all  = living + this year's dead (mortality is applied AFTER allocation, so a dead\n")
        f.write("#              stem still grew this year)                        <- F's growth-only target\n")
        f.write("#   fpc_new  = the part of fpc_all held by stems not present last year (5 m crossers)\n")
        f.write("# gt5m_frac = fpc_live / the C's own a_fpc output for the same year. It is < 1 because the\n")
        f.write("# `ind` writer emits only stems above 5 m. READ EVERY F-vs-C CROWN RATIO AGAINST THIS.\n")
        f.write("# scripts/build_biome_stem_growth_reference.py\n")
        f.write(",".join(hdr) + "\n")
        for r in summ:
            f.write(",".join(f"{r[k]:.6g}" if isinstance(r[k], float) else str(r[k]) for k in hdr) + "\n")
    print(f"wrote {path}  ({len(summ)} rows)")

    print(f"\n{'cell':24s} {'yr':>4s} {'n_live':>6s} {'n_dead':>6s} {'n_new':>5s} "
          f"{'fpc_live':>8s} {'fpc_all':>8s} {'fpc_new':>8s} {'a_fpc':>7s} {'>5m':>6s}")
    for r in summ:
        print(f"{r['name']:24s} {r['year']:4d} {r['n_live']:6d} {r['n_dead']:6d} {r['n_new']:5d} "
              f"{r['fpc_live']:8.4f} {r['fpc_all']:8.4f} {r['fpc_new']:8.4f} {r['c_a_fpc']:7.4f} "
              f"{r['gt5m_frac']:6.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
