#!/usr/bin/env python3
# =============================================================================
# diagnose_ind_true_gpp.py — CLOSE ADR 0129's photosynthesis-vs-respiration BRACKET
# by measuring, rather than bounding, the two things the stock `ind` output hides.
#
# THE PROBLEM (line M, rung 3). F_diff's assimilate error `bmi_F/bmi_C` factorises
# exactly as `GPP_F/GPP_C · CUE_F/CUE_C`, but the C's two sides were on DIFFERENT
# populations, so the split was undetermined between 38 % and 78 % photosynthesis:
#   * the daily `d_gpp` output contains every tree, while
#   * `ind` (from which the per-stem NPP, and F's whole roster, come) emits only
#     stems above `param.height_min` = 5 m, and
#   * `ind`'s `gpp` column is not GPP at all — `daily_natural.c` accumulates NPP
#     into `pft->agpp`, so a per-stem NPP/GPP from it is exactly 1.0000.
# The product is untouched by this (both biases are the same factor, opposite
# directions), which is why every published `bmi` number stands.
#
# WHAT THIS SCORES. Runs from `scripts/run_ind_true_gpp_cells.sh`, i.e. a rebuilt C
# with `LPJ_IND_ALL_HEIGHTS=1 LPJ_IND_TRUE_GPP=1` (both inert unless set; the
# rebuild was gated at 139 decoded quantities identical, 0 differ). Per cell-year:
#
#   GATE     `Σ gpp over ALL PFT rows / npatch`  vs the run's own annual `d_gpp`.
#            These come from two different code paths over the same daily `gpp`
#            variable, so agreement is a real check on the new accumulator — and it
#            simultaneously proves the emitted roster is COMPLETE (a missing tree
#            would show up as a shortfall). Trees flagged `isdead` are INCLUDED:
#            mortality is applied after allocation, so they photosynthesised all
#            year (CLAUDE.md §3).
#   RESULT   `gpp_tree_gt5m / gpp_tree_all` = the >5 m share of TREE GPP. This is
#            the bracket's unknown. The lower end of ADR 0129's bracket assumed the
#            short stems carry NO flux (share = 1), the upper end that they carry
#            their crown share (share = the crown-cover `gt5m`).
#   RESULT   `Σ npp / Σ gpp` over the >5 m trees = the C's carbon-use efficiency on
#            exactly the population F's roster is built from ⇒ `CUE_F/CUE_C`
#            like-for-like, with no population correction left in it.
#   FREE     the tree/grass GPP split straight from the roster, needing neither a
#            `d_grass_gpp` output nor an FPC-share assumption (ADR 0053 measured
#            the latter to over-state grass's flux share 1.31-2.98x).
#
# ⚠ SINGLE-CELL BASIS (ADR 0041): these runs' rosters are not the global run's, so
# read the WITHIN-RUN ratios above and never pair a stem here with a global-parquet
# stem. The `gpp_tree` oracle these feed is itself on the single-cell basis.
#
# Usage:  /home/jamirp/.conda/envs/py311_new/bin/python scripts/diagnose_ind_true_gpp.py
# Env:    RUNTAG (default M_indgpp), Y0/Y1 (default 2000/2019), CELLS, CSV=<path>
# =============================================================================
import os
import sys

import numpy as np
import polars as pl
import xarray as xr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_biome_forcing import cells_from_env  # noqa: E402  (THE canonical registry)

RUN_ROOT = "/p/tmp/jamirp/esm_land_daily"
RUNTAG = os.environ.get("RUNTAG", "M_indgpp")
Y0 = int(os.environ.get("Y0", "2000"))
Y1 = int(os.environ.get("Y1", "2019"))
NDAYYEAR = 365
HEIGHT_MIN = 5.0                  # param.height_min — the writer's stock emission cut

# The frozen 29-column `ind` TXT schema, from the ONE place that owns it — re-declaring it
# is the ADR-0031 trap. The file's own header is asserted against it in read_ind().
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "python", "src"))
try:
    from lpjmlfit_emulator.data import IND_COLUMNS, TREE_TYPES
except ImportError:                                  # the package layout differs by checkout
    import glob
    hit = glob.glob(os.path.join(REPO, "python", "src", "*", "data.py"))
    assert hit, "cannot locate python/src/*/data.py — do not re-declare IND_COLUMNS here"
    sys.path.insert(0, os.path.dirname(os.path.dirname(hit[0])))
    mod = __import__(os.path.basename(os.path.dirname(hit[0])) + ".data", fromlist=["data"])
    IND_COLUMNS, TREE_TYPES = mod.IND_COLUMNS, mod.TREE_TYPES


def run_dir(name, cell):
    return os.path.join(RUN_ROOT, f"daily_{Y0}_{Y1}_{RUNTAG}_{name}_c{cell}_seed1")


def npatch_of(rd):
    """The CONFIGURED patch count, read from the run's own config (never hardcoded)."""
    with open(os.path.join(rd, "scripts_for_running_the_model", "lpjml.js")) as fh:
        for line in fh:
            if '"npatch"' in line:
                return int(line.split(":")[1].strip().rstrip(",").strip())
    raise AssertionError(f"no npatch in {rd}")


def completed(rd):
    """A C run is judged from its LOG, never from SLURM state (CLAUDE.md §3). An empty
    log is a provenance FATAL, not a verdict — so resolve the newest NON-EMPTY one."""
    import glob
    logs = [p for p in sorted(glob.glob(os.path.join(rd, "lpjml.*.out"))) if os.path.getsize(p) > 0]
    if not logs:
        return False, "no non-empty lpjml_*.out (provenance FATAL, not a physics result)"
    txt = open(logs[-1]).read()
    ok = "successfully terminated" in txt
    return ok, os.path.basename(logs[-1]) + ("" if ok else " — no completion line")


def annual_dgpp(rd):
    """Annual sums (gC/m2/yr) of the run's own daily GPP output, per year."""
    ds = xr.open_dataset(os.path.join(rd, "d_gpp.nc"), decode_times=False, mask_and_scale=True)
    dv = [v for v in ds.data_vars if v not in ("time_bnds", "lat_bnds", "lon_bnds", "NamePFT")]
    name = "GPP" if "GPP" in dv else dv[0]
    a = np.asarray(ds[name].isel(lat=0, lon=0), dtype=float)
    a = np.where(a < -1e30, np.nan, a)
    nyr = len(a) // NDAYYEAR
    assert nyr == Y1 - Y0 + 1, f"{len(a)} daily values is not {Y1 - Y0 + 1} noleap years"
    return {Y0 + i: float(np.nansum(a[i * NDAYYEAR:(i + 1) * NDAYYEAR])) for i in range(nyr)}


def read_ind(rd):
    p = os.path.join(rd, "output", f"ind_{Y0}_{Y1}.csv")
    if not os.path.exists(p):                        # the wrapper writes output/ inside the run dir
        p = os.path.join(rd, f"ind_{Y0}_{Y1}.csv")
    # The TXT `ind` file DOES carry a header (fopenoutput.c writes it once at file open) —
    # reading it with has_header=False makes every column a String and polars then panics
    # inside the aggregation rather than failing where the mistake is. Use the header, and
    # gate it against the frozen 29-column schema: that catches a writer change instead of
    # silently mis-naming columns, which is the ADR-0031 failure mode.
    # ⚠ PIN THE DTYPES. The `mort_*` columns are UNINITIALISED MEMORY for any tree that has
    # not yet been through `mortality_tree_ind` (CLAUDE.md §3) — at the top of a restarted
    # run that garbage often prints as a whole number, so type inference calls the column
    # i64 and then dies on the first real value further down the file.
    ints = {"Year", "ID", "Type", "Age", "isdead", "Patch", "Cell"}
    df = pl.read_csv(p, has_header=True, schema_overrides={
        c: (pl.Int64 if c in ints else pl.Float64) for c in IND_COLUMNS
    })
    assert tuple(df.columns) == tuple(IND_COLUMNS), (
        "the `ind` writer's header no longer matches the frozen IND_COLUMNS schema:\n"
        f"  file:   {df.columns}\n  schema: {list(IND_COLUMNS)}"
    )
    return df


def main():
    cells = cells_from_env()
    rows = []
    for name, cell in cells:
        rd = run_dir(name, cell)
        if not os.path.isdir(rd):
            print(f"[skip] {name}: no run at {rd}")
            continue
        ok, why = completed(rd)
        if not ok:
            print(f"[FAIL] {name}: {why}")
            continue
        npatch = npatch_of(rd)
        dgpp = annual_dgpp(os.path.join(rd, "output"))
        df = read_ind(rd)

        istree = pl.col("Type").is_in(list(TREE_TYPES))
        tall = istree & (pl.col("Height") > HEIGHT_MIN)          # the writer's stock population
        agg = (
            df.group_by("Year")
            .agg(
                gpp_all=pl.col("gpp").sum() / npatch,
                gpp_tree_all=pl.col("gpp").filter(istree).sum() / npatch,
                gpp_tree_gt5=pl.col("gpp").filter(tall).sum() / npatch,
                gpp_grass=pl.col("gpp").filter(~istree).sum() / npatch,
                npp_tree_all=pl.col("npp").filter(istree).sum() / npatch,
                npp_tree_gt5=pl.col("npp").filter(tall).sum() / npatch,
                n_tree_all=istree.sum(),
                n_tree_gt5=tall.sum(),
                hmin=pl.col("Height").filter(istree).min(),
            )
            .sort("Year")
        )
        for r in agg.iter_rows(named=True):
            y = r["Year"]
            if y not in dgpp:
                continue
            rows.append(dict(name=name, cell=cell, npatch=npatch, year=y, d_gpp=dgpp[y], **r))

    if not rows:
        print("nothing to score")
        return 1

    # ---- THE GATE: the roster's own GPP must reproduce the stand-level daily output ----
    print("\n=== GATE: Sum of per-individual gpp over ALL PFTs  vs  the run's own annual d_gpp ===")
    print("(two independent code paths over the same daily `gpp`; also proves the roster is\n"
          " complete)")
    print(f"{'cell':22s} {'yr':>4s} {'ind_all':>10s} {'d_gpp':>10s} {'ratio':>8s} {'rel err':>9s}")
    worst = 0.0
    worst_at = ""
    for r in rows:
        rel = abs(r["gpp_all"] - r["d_gpp"]) / r["d_gpp"] if r["d_gpp"] else float("nan")
        if rel > worst:
            worst, worst_at = rel, f"{r['name']} {r['year']}"
        if r["year"] in (Y0, Y1):                    # keep the table readable
            print(f"{r['name']:22s} {r['year']:4d} {r['gpp_all']:10.3f} {r['d_gpp']:10.3f} "
                  f"{r['gpp_all'] / r['d_gpp']:8.5f} {rel:9.2e}")
    print(f"\nworst relative disagreement: {worst:.3e} at {worst_at}  "
          f"({len(rows)} cell-years)")
    # The `ind` TXT writer uses %g = 6 significant digits, and the sum is over hundreds
    # of stems, so the floor is ~1e-5 relative and a tolerance below it is meaningless.
    gate = worst < 2e-5
    print(f"GATE: {'PASS' if gate else 'FAIL'} (tolerance 2e-5, the writer's own %g "
          f"6-significant-digit floor)")

    # ---- THE RESULT: the >5 m share of tree GPP, and CUE on each population ----
    print("\n=== RESULT: what the 5 m writer cut actually hides ===")
    print(f"{'cell':22s} {'gpp>5m/gpp_all':>15s} {'CUE>5m':>8s} {'CUE_all':>8s} "
          f"{'grass/tot':>10s} {'n>5m/n_all':>11s} {'h_min':>6s}")
    per_cell = {}
    for name, _ in cells:
        rs = [r for r in rows if r["name"] == name]
        if not rs:
            continue
        share = sum(r["gpp_tree_gt5"] for r in rs) / sum(r["gpp_tree_all"] for r in rs)
        cue5 = sum(r["npp_tree_gt5"] for r in rs) / sum(r["gpp_tree_gt5"] for r in rs)
        cuea = sum(r["npp_tree_all"] for r in rs) / sum(r["gpp_tree_all"] for r in rs)
        grass = sum(r["gpp_grass"] for r in rs) / sum(r["gpp_all"] for r in rs)
        nfrac = sum(r["n_tree_gt5"] for r in rs) / sum(r["n_tree_all"] for r in rs)
        hmin = min(r["hmin"] for r in rs)
        per_cell[name] = dict(share=share, cue5=cue5, cuea=cuea, grass=grass,
                              nfrac=nfrac, hmin=hmin)
        print(f"{name:22s} {share:15.4f} {cue5:8.4f} {cuea:8.4f} {grass:10.4f} "
              f"{nfrac:11.3f} {hmin:6.2f}")

    print("\nREADING IT. `gpp>5m/gpp_all` is the factor ADR 0129's bracket was open over: it\n"
          "is what must MULTIPLY the C's GPP to put it on F's >5 m roster. 1.000 would mean the\n"
          "short trees carry no flux (the bracket's 38 %-photosynthesis end); the crown-cover\n"
          "`gt5m` would mean\n"
          "they carry their full crown share (the 78 % end). `CUE>5m` is the C's carbon-use\n"
          "efficiency on F's own population — use THAT as CUE_C, not the all-tree value.")

    out = os.environ.get("CSV")
    if out:
        with open(out, "w") as fh:
            fh.write("# diagnose_ind_true_gpp.py — the C's per-stem GPP on the FULL stand\n")
            fh.write("# (LPJ_IND_ALL_HEIGHTS=1 LPJ_IND_TRUE_GPP=1; single-cell re-runs,\n")
            fh.write("# ADR 0041 basis). gpp_*/npp_* are gC/m2/yr, patch-ensemble means\n")
            fh.write("# (sum over stems / npatch). `_gt5` = stems above the writer's 5 m cut;\n")
            fh.write("# `_all` = every tree incl. below it.\n")
            keys = ["name", "cell", "npatch", "year", "d_gpp", "gpp_all", "gpp_tree_all",
                    "gpp_tree_gt5", "gpp_grass", "npp_tree_all", "npp_tree_gt5",
                    "n_tree_all", "n_tree_gt5", "hmin"]
            fh.write(",".join(keys) + "\n")
            for r in rows:
                fh.write(",".join(f"{r[k]:.6g}" if isinstance(r[k], float) else str(r[k])
                                  for k in keys) + "\n")
        print(f"\nwrote {out}")
    return 0 if gate else 1


if __name__ == "__main__":
    sys.exit(main())
