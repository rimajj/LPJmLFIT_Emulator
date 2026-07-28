#!/usr/bin/env python3
"""diagnose_patch_lai_reconstruction.py — PROVE that a PER-PATCH stand LAI is reconstructable from the
29-column `ind` output, and MEASURE the two things that separate it from the C's gridded `LAI_STAND`.

WHY (milestone S1d / ADR 0035 — the SPATIAL half of the runtime<->training basis fix):
  The runtime feeds Component S a SINGLE-PATCH stand LAI (`slow.jl::flux_feature_vector`:
  `lai = sum(leaf_c*sla*nind)` over the one coupled patch), but the training table joined the C's
  patch-ensemble CELL-MEAN `LAI_STAND` (`build_laistand_lai_feature.py`) onto per-PATCH rows — a spatial
  aggregation mismatch measured at ~1.4x (ADR 0034). Every OTHER patch-state column in the same training
  row (`hmean`, `hmax`, `agb`, `fpc`, `age_mean`, `n_living`) is a per-PATCH sum over the emitted stems, so
  `lai` was the odd one out — and it is also the `growth_eff` DIVISOR, a primary mortality driver.

  The `slow-drf-pipeline` skill recorded "per-patch LAI is NOT reconstructable from ind (no leaf_c/nind)".
  That is true LITERALLY and false in EFFECT — the two emitted columns `LAI` (the individual's within-crown
  LAI) and `fpc_ind` (the individual's FPC) between them carry the missing crown area:

      C, fpc_tree.c:28      fpc_ind = crownarea * nind * (1 - exp(-k_pft * lai_ind))
      C, new_tree.c:209     nind    = 1 / param.patcharea            (individual = true)
      C, lai_tree.c:18      lai_ind = leaf_c * sla / crownarea       (= the emitted `LAI` column)
      C, fwriteoutput.c:714 LAI_STAND += (leaf_c * sla) / npatch / patcharea   (trees, isdead==0)

  =>  leaf_c*sla/patcharea = lai_ind * crownarea/patcharea
                           = lai_ind * fpc_ind / (1 - exp(-k_pft * lai_ind))

  so the PER-PATCH stand LAI is exactly

      stand_lai(patch) = SUM_stems  LAI_i * fpc_ind_i / (1 - exp(-k_i * LAI_i))            (*)

  and `patcharea` CANCELS (it never has to be known). `k_i` is the PER-PFT Lambert-Beer coefficient
  (`getpftpar(pft, lightextcoeff)`), NOT one global constant: 0.59 broadleaf / 0.45 needleleaf.

THREE CHECKS, in the order that makes the verdict readable:

  CHECK 1 (DECISIVE — is (*) exact?).  Per STEM, invert `fpc_ind` for the crown area and compare against
    the C's OWN height allometry (`allometry_tree.c:53,57`):
        crownarea_from_fpc = patcharea * fpc_ind / (1 - exp(-k*LAI))
        crownarea_allom    = min(allom1 * (Height/allom2)^(kpr/allom3), crownarea_max)
    These share no algebra, so agreement validates the inversion itself, independently of any population
    or aggregation difference. This is the check that gates the S1d spatial fix.

  CHECK 2 (CONTEXT — why (*) does NOT equal LAI_STAND, and by how much).  The `ind` writer emits a stem
    only `if(tree->height > param.height_min)` = 5 m (`fwriteoutput_ind.c:84`), while `LAI_STAND` sums ALL
    living trees. So (*) is the **>5 m** per-patch stand LAI and must read BELOW the cell-mean LAI_STAND by
    the sapling share. That share is a property of the C run, not an error — but it is the reason a naive
    "reconstruction == LAI_STAND" test fails, and it must be reported, not tuned away. Crucially, EVERY
    other column in the training row is on that same >5 m per-patch population, which is exactly why (*)
    is the internally consistent choice.

  CHECK 3 (the quantity S1d is actually about).  The patch-to-patch spread of (*) within a cell-year — the
    width the trained `lai` band gains by going per-patch, and therefore whether the coupled single-patch
    runtime value can sit inside it at all.

Env:
  SCENARIO   historic | ssp370                        (default historic)
  SEED       ind parquet seed                         (default 1)
  CELLS      "name:idx,..." else the BIOMES registry  (extract_biome_forcing.cells_from_env)
  NPATCH     patches per cell                         (default 25, lpjmlfit.js:41)
  TOL        max |relative error| accepted in CHECK 1 (default 1e-4; see the precision floor below)

PRECISION FLOOR (why TOL is 1e-4 and not 0):
  `printind` writes the TXT `ind` table with `%g` = SIX significant digits (`fwriteoutput_ind.c:27`), so
  every input to CHECK 1 arrives pre-rounded at ~1e-6 relative. The inversion amplifies that: `Height`
  enters the allometry through a `^(kpr/allom3)` power (exponent ~2.3 for ANGIO, ~2.1 GYMNO) and `LAI`
  enters the `1-exp(-k*LAI)` denominator. A measured median of ~1e-8 with a p99 tail at ~1e-5 is that
  round-off and nothing else — a real formula/constant error (a wrong `k`, a wrong allometry family) is a
  PERCENT-level bias in the median, which 1e-4 still catches by three orders of magnitude.
Usage (light — a handful of cells, projection+predicate pushdown; login node is fine):
  /home/jamirp/.conda/envs/py311_new/bin/python scripts/diagnose_patch_lai_reconstruction.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "python", "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_slow_runtime_table import K_LIGHTEXT, patch_stand_lai_expr  # noqa: E402
from extract_biome_forcing import cells_from_env  # noqa: E402
from lpjmlfit_emulator.data import TREE_TYPES  # noqa: E402  (ADR 0031 — the ONE stem-population constant)

BASE = "/p/tmp/jamirp/emulator_global"
IND = {
    "historic": f"{BASE}/ind_hist_seed{{seed}}_all.parquet",
    "ssp370": f"{BASE}/ind_ssp370_seed{{seed}}_all.parquet",
}
LAI_TBL = {"historic": f"{BASE}/tables/cell_year_lai_hist.parquet",
           "ssp370": f"{BASE}/tables/cell_year_lai_ssp.parquet"}

PATCHAREA = 225.0     # par/lpjparam_fit.js:17 (only CHECK 1 needs it; (*) itself is patcharea-free)
CROWNAREA_MAX = 225.0  # par/pft_lpjmlfit.js:40 CA_MAX

#: Per-PFT CROWN allometry from `par/pft_lpjmlfit.js`, keyed by the 0-based `Type` = pftpar index
#: (CLAUDE.md §3). ANGIO ids {0,2,3,5} / GYMNO ids {1,4,6}; macros ALLOM*_ANGIO/GYMNO + KPR_* (Jucker 2022).
#: Used ONLY by CHECK 1 — the independent side of the comparison. The light-extinction coefficients and the
#: reconstruction itself are IMPORTED from build_slow_runtime_table (one definition, ADR 0031's lesson).
_ANGIO = dict(allom1=117.44, allom2=28.7490, allom3=0.5633, kpr=1.2922)
_GYMNO = dict(allom1=101.34, allom2=31.4093, allom3=0.6650, kpr=1.4163)
PFT_ALLOM = {0: _ANGIO, 1: _GYMNO, 2: _ANGIO, 3: _ANGIO, 4: _GYMNO, 5: _ANGIO, 6: _GYMNO}
assert set(PFT_ALLOM) == set(K_LIGHTEXT), "crown-allometry and light-extinction PFT sets disagree"


def _crownarea_allom_expr() -> pl.Expr:
    """`allometry_tree.c:53,57` — min(allom1*(H/allom2)^(kpr/allom3), crownarea_max), per-PFT params."""
    a1 = pl.col("Type").replace_strict({t: p["allom1"] for t, p in PFT_ALLOM.items()}, return_dtype=pl.Float64)
    a2 = pl.col("Type").replace_strict({t: p["allom2"] for t, p in PFT_ALLOM.items()}, return_dtype=pl.Float64)
    a3 = pl.col("Type").replace_strict({t: p["allom3"] for t, p in PFT_ALLOM.items()}, return_dtype=pl.Float64)
    kp = pl.col("Type").replace_strict({t: p["kpr"] for t, p in PFT_ALLOM.items()}, return_dtype=pl.Float64)
    return pl.min_horizontal(a1 * (pl.col("Height") / a2).pow(kp / a3), pl.lit(CROWNAREA_MAX))


def main() -> int:
    scenario = os.environ.get("SCENARIO", "historic")
    seed = int(os.environ.get("SEED", "1"))
    npatch = int(os.environ.get("NPATCH", "25"))
    tol = float(os.environ.get("TOL", "1e-4"))
    named = cells_from_env()
    cells = [c for _, c in named]
    print(f"scenario={scenario} seed={seed} npatch={npatch} tol={tol:g}")
    print(f"cells: {', '.join(f'{n}={c}' for n, c in named)}")

    stems = (
        pl.scan_parquet(IND[scenario].format(seed=seed))
        .filter(pl.col("Type").is_in(TREE_TYPES) & (pl.col("isdead") == 0) & pl.col("Cell").is_in(cells))
        .select(["Cell", "Patch", "Year", "Type", "Height", "LAI", "fpc_ind"])
        .with_columns(
            patch_stand_lai_expr().alias("_stem_lai"),
            _crownarea_allom_expr().alias("ca_allom"),
        )
        .with_columns(
            pl.when(pl.col("LAI") > 0.0)
            .then(PATCHAREA * pl.col("fpc_ind")
                  / (1.0 - (-pl.col("Type").replace_strict(K_LIGHTEXT, return_dtype=pl.Float64)
                            * pl.col("LAI")).exp()))
            .otherwise(None)
            .alias("ca_fpc")
        )
        .collect(engine="streaming")
    )
    print(f"== {stems.height} living tree stems (>{5.0:g} m, the ind writer's height_min)")

    # ── CHECK 1 — DECISIVE: does inverting fpc_ind give back the C's own allometric crown area? ──
    ca = stems.drop_nulls("ca_fpc")
    rel = ((ca["ca_fpc"] - ca["ca_allom"]) / ca["ca_allom"]).to_numpy()
    # a crown pinned at CA_MAX carries no information (both sides are the cap), so report it separately
    at_cap = int((ca["ca_allom"] >= CROWNAREA_MAX - 1e-9).sum())
    worst_ca = float(np.max(np.abs(rel))) if rel.size else float("nan")
    print(f"\n== CHECK 1  crown area: fpc-inverted vs Height allometry ({ca.height} stems, "
          f"{at_cap} at CA_MAX)")
    print(f"   median rel err {np.median(rel):+.3e}   mean {np.mean(rel):+.3e}   "
          f"p99 |rel| {np.percentile(np.abs(rel), 99):.3e}   max |rel| {worst_ca:.3e}")
    check1 = np.isfinite(worst_ca) and worst_ca <= tol

    # ── CHECK 2 — the >5 m share: (*) averaged back over patches vs the C's all-trees LAI_STAND ──
    per_patch = (
        stems.group_by(["Cell", "Patch", "Year"]).agg(pl.col("_stem_lai").sum().alias("lai_patch"))
    )
    recon = (
        per_patch.group_by(["Cell", "Year"])
        .agg(pl.col("lai_patch").sum().alias("_sum"),
             pl.len().alias("n_patch_present"),
             pl.col("lai_patch").mean().alias("lai_patch_mean"),
             pl.col("lai_patch").std().alias("lai_patch_sd"),
             pl.col("lai_patch").min().alias("lai_patch_min"),
             pl.col("lai_patch").max().alias("lai_patch_max"))
        .with_columns((pl.col("_sum") / npatch).alias("lai_recon"))   # C divides by ALL npatch patches
    )
    truth = pl.read_parquet(LAI_TBL[scenario]).select(["Cell", "Year", "lai"]).rename({"lai": "lai_c"})
    cmp = recon.join(truth, on=["Cell", "Year"], how="inner").sort(["Cell", "Year"])
    if cmp.height == 0:
        print("FATAL: no overlapping (Cell,Year) between the reconstruction and the C LAI_STAND table",
              file=sys.stderr)
        return 2
    cmp = cmp.with_columns(
        (pl.col("lai_recon") / pl.max_horizontal(pl.col("lai_c"), pl.lit(1e-12))).alias("share_gt5m")
    )
    print(f"\n== CHECK 2  >5 m share = (*) cell-mean / C LAI_STAND   ({cmp.height} cell-years)")
    print(f"{'cell':>7} {'n':>3} {'lai_C':>8} {'recon':>8} {'share':>7} | "
          f"{'patch mean':>10} {'sd':>7} {'min':>7} {'max':>7} {'max/mean':>9}")
    for cell in sorted({c for _, c in named}):
        sub = cmp.filter(pl.col("Cell") == cell)
        if sub.height == 0:
            print(f"{cell:>7}  (absent from one of the two tables)")
            continue
        print(f"{cell:>7} {sub.height:>3} {sub['lai_c'].mean():>8.4f} {sub['lai_recon'].mean():>8.4f} "
              f"{sub['share_gt5m'].mean():>7.4f} | {sub['lai_patch_mean'].mean():>10.4f} "
              f"{sub['lai_patch_sd'].mean():>7.4f} {sub['lai_patch_min'].mean():>7.4f} "
              f"{sub['lai_patch_max'].mean():>7.4f} "
              f"{(sub['lai_patch_max'] / sub['lai_patch_mean']).mean():>9.4f}")

    # ── CHECK 3 — the band width the per-patch basis buys, vs the cell-mean basis it replaces ──
    print("\n== CHECK 3  per-patch band vs cell-mean band (the S1d point)")
    for cell in sorted({c for _, c in named}):
        pp = per_patch.filter(pl.col("Cell") == cell)["lai_patch"]
        cm = cmp.filter(pl.col("Cell") == cell)["lai_c"]
        if pp.len() == 0 or cm.len() == 0:
            continue
        print(f"{cell:>7}  per-patch [{pp.min():.3f}, {pp.max():.3f}] (width {pp.max() - pp.min():.3f})   "
              f"cell-mean [{cm.min():.3f}, {cm.max():.3f}] (width {cm.max() - cm.min():.3f})   "
              f"widening {((pp.max() - pp.min()) / max(cm.max() - cm.min(), 1e-12)):.1f}x")

    print(f"\nCHECK 1 (the gate): worst |rel err| {worst_ca:.3e} vs tol {tol:g} -> "
          f"{'PASS' if check1 else 'FAIL'}")
    if not check1:
        print("FAIL: inverting fpc_ind does NOT reproduce the C's allometric crown area — formula (*) is "
              "wrong or a per-PFT constant is. Do not build the S1d spatial fix on it.", file=sys.stderr)
        return 1
    print("PASS: (*) is exact for every emitted stem. The gap to LAI_STAND in CHECK 2 is the >5 m "
          "height_min truncation (a property of the C's ind writer), not a formula error.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
