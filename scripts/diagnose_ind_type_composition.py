#!/usr/bin/env python3
"""Which PFT `Type` ids actually carry stems in the global `ind` ground truth — and what the Component-S
training basis `TREE_TYPES = [1,2,3,4,5]` therefore DROPS.

Why this exists (S1, 2026-07-28). Two conflicting tree-PFT constants live in this repo:
  • `python/src/lpjmlfit_emulator/data.py:68`      TREE_TYPES = (1, 2, 3, 4, 5)   ← used by every slow-* builder
  • `python/src/lpjmlfit_emulator/features.py:50`  TREE_TYPES = [0, 1, 2, 3, 4, 5, 6]
The ACTIVE parameter file `/home/jamirp/lpjml56fit/par/pft_lpjmlfit.js` (`"pftpar"` array, id == 0-based array
index via `fscanpftpar.c:177`) lists SEVEN tree PFTs then three grasses:
  0 tropical broadleaved evergreen · 1 temperate needleleaved evergreen · 2 temperate broadleaved evergreen
  3 temperate broadleaved summergreen (= the Hainich beech) · 4 boreal needleleaved evergreen
  5 boreal broadleaved summergreen · 6 boreal needleleaved summergreen (larch) | 7/8/9 grass | 10-21 crops
so `[0..6]` is the tree set and `(1,2,3,4,5)` silently omits the TROPICAL evergreen (id 0) and the boreal
larch (id 6). This script measures, from the data, how much that omission actually removes: stems, cells,
cells lost ENTIRELY, and the per-axis trait shift it induces. It settles by measurement whether the slow-*
basis is a benign convention or a scope defect in the production Component-S artifacts.

Run:  scripts/sbatch_python.sh S-typecomp scripts/diagnose_ind_type_composition.py
Env:  IND (parquet path; default the seed1 historic ind), MINSTEM (20, the fig-10 per-cell filter).
"""

import os

import polars as pl

BASE = "/p/tmp/jamirp/emulator_global"
IND = os.environ.get("IND", f"{BASE}/ind_hist_seed1_all.parquet")
AXES = ["SLA", "Wooddens", "D95max", "minwscal"]
SLOW_TYPES = [1, 2, 3, 4, 5]          # data.py:68 — the slow-* / copula / count-DRF training basis
ALL_TREES = [0, 1, 2, 3, 4, 5, 6]     # features.py:50 / par/pft_lpjmlfit.js — the real tree set
MINSTEM = int(os.environ.get("MINSTEM", "20"))
NAMES = {
    0: "tropical broadleaved evergreen", 1: "temperate needleleaved evergreen",
    2: "temperate broadleaved evergreen", 3: "temperate broadleaved summergreen (beech)",
    4: "boreal needleleaved evergreen", 5: "boreal broadleaved summergreen",
    6: "boreal needleleaved summergreen (larch)", 7: "Tropical C4 grass",
    8: "Temperate C3 grass", 9: "Polar C3 grass",
}


def main():
    print(f"== ind parquet: {IND}", flush=True)

    # ---- per-Type census over ALL rows (survivor + dead, so the isdead split is visible) ----------------
    census = (
        pl.scan_parquet(IND).select(["Cell", "Type", "isdead", *AXES])
        .group_by(["Type", "isdead"])
        .agg([pl.len().alias("rows"), pl.col("Cell").n_unique().alias("cells")]
             + [pl.col(a).median().alias(f"med_{a}") for a in AXES])
        .collect(engine="streaming")
        .sort(["Type", "isdead"])
    )
    print("\n== per-Type census (all rows; one row = one stem-year) ==")
    print(f"{'Type':>4s} {'isdead':>6s} {'rows':>14s} {'cells':>7s} " +
          " ".join(f"{'med_' + a:>13s}" for a in AXES) + "   name")
    for r in census.iter_rows(named=True):
        print(f"{r['Type']:>4d} {r['isdead']:>6d} {r['rows']:>14d} {r['cells']:>7d} " +
              " ".join(f"{r['med_' + a]:13.5g}" if r["med_" + a] is not None else f"{'None':>13s}" for a in AXES) +
              f"   {NAMES.get(r['Type'], '?')}")

    surv = census.filter(pl.col("isdead") == 0)
    tot_tree = surv.filter(pl.col("Type").is_in(ALL_TREES))["rows"].sum()
    kept = surv.filter(pl.col("Type").is_in(SLOW_TYPES))["rows"].sum()
    dropped = tot_tree - kept
    print(f"\n== SURVIVOR TREE stems: {tot_tree} total (ids {ALL_TREES}) · {kept} kept by the slow-* basis "
          f"{SLOW_TYPES} · {dropped} DROPPED ({dropped / max(tot_tree, 1):.4f})")
    for t in (0, 6):
        row = surv.filter(pl.col("Type") == t)
        if row.height:
            n = row["rows"][0]
            print(f"   id {t} ({NAMES[t]}): {n} survivor stems = {n / max(tot_tree, 1):.4f} of all tree stems, "
                  f"{row['cells'][0]} cells")

    # ---- per-cell: which cells does the slow-* basis lose entirely, and how biased are the ones it keeps -
    per_cell = (
        pl.scan_parquet(IND).select(["Cell", "Type", "isdead"])
        .filter((pl.col("isdead") == 0) & pl.col("Type").is_in(ALL_TREES))
        .group_by("Cell").agg(
            pl.len().alias("n_all"),
            pl.col("Type").is_in(SLOW_TYPES).sum().alias("n_slow"),
            (pl.col("Type") == 0).sum().alias("n_t0"),
            (pl.col("Type") == 6).sum().alias("n_t6"),
        )
        .collect(engine="streaming")
    )
    n_cells = per_cell.height
    lost = per_cell.filter(pl.col("n_slow") == 0)
    lost20 = per_cell.filter((pl.col("n_slow") < MINSTEM) & (pl.col("n_all") >= MINSTEM))
    print(f"\n== per-cell effect of the slow-* basis ==")
    print(f"   cells with ≥1 survivor tree stem (ids {ALL_TREES}): {n_cells}")
    print(f"   cells with ZERO stems of ids {SLOW_TYPES} ⇒ INVISIBLE to Component S: {lost.height} "
          f"({lost.height / max(n_cells, 1):.4f})")
    print(f"   cells that pass the ≥{MINSTEM}-stem filter on all trees but FAIL it on the slow-* subset: "
          f"{lost20.height}")
    frac = per_cell.with_columns((pl.col("n_slow") / pl.col("n_all")).alias("f"))
    q = frac["f"].quantile
    print(f"   retained-stem FRACTION per cell (n_slow/n_all): median {frac['f'].median():.4f} · "
          f"q05 {q(0.05):.4f} · q25 {q(0.25):.4f} · q75 {q(0.75):.4f}")
    heavy = frac.filter(pl.col("f") < 0.5)
    print(f"   cells where the slow-* basis keeps <50% of the tree stems: {heavy.height} "
          f"({heavy.height / max(n_cells, 1):.4f})")

    # ---- the trait-median shift the omission induces, on cells BOTH bases retain -----------------------
    print(f"\n== per-cell trait-median SHIFT induced by the omission (cells with ≥{MINSTEM} stems on BOTH "
          f"bases) ==")
    base = pl.scan_parquet(IND).select(["Cell", "Type", "isdead", *AXES]).filter(pl.col("isdead") == 0)
    m_all = (base.filter(pl.col("Type").is_in(ALL_TREES)).group_by("Cell")
             .agg([pl.col(a).median().alias(f"all_{a}") for a in AXES] + [pl.len().alias("n_all")])
             .collect(engine="streaming"))
    m_slow = (base.filter(pl.col("Type").is_in(SLOW_TYPES)).group_by("Cell")
              .agg([pl.col(a).median().alias(f"slow_{a}") for a in AXES] + [pl.len().alias("n_slow")])
              .collect(engine="streaming"))
    j = (m_all.join(m_slow, on="Cell", how="inner")
         .filter((pl.col("n_all") >= MINSTEM) & (pl.col("n_slow") >= MINSTEM)))
    print(f"   {j.height} cells compared")
    print(f"   {'axis':10s} {'r(all,slow)':>11s} {'median|rel Δ|':>14s} {'q95|rel Δ|':>11s} "
          f"{'sd(all)/sd(slow)':>17s}")
    for a in AXES:
        va, vs = j[f"all_{a}"], j[f"slow_{a}"]
        rel = ((va - vs).abs() / va.abs().clip(1e-12)).to_numpy()
        import numpy as np
        r = float(np.corrcoef(va.to_numpy(), vs.to_numpy())[0, 1])
        print(f"   {a:10s} {r:11.4f} {np.median(rel):14.4f} {np.quantile(rel, 0.95):11.4f} "
              f"{va.std() / max(vs.std(), 1e-12):17.4f}")

    print("\n== DONE diagnose_ind_type_composition ==", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
