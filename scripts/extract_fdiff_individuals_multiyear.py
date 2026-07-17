#!/usr/bin/env python3
# =============================================================================
# extract_fdiff_individuals_multiyear.py — before/after canopy-structure sets
# for the F_diff DYNAMIC (prognostic within-year) structure validation
# (Phase-3 scale-up step 6) on the Hainich prototype cell (global orderA grid
# index 42490).
#
# The multi-individual canopy (scale-up step 3) fixed each individual's
# structure at its YEAR-END value for the whole year. Step 6 makes the
# per-individual carbon pools PROGNOSTIC: they accumulate the daily bm_inc
# (= Σ daily NPP) and, at the annual boundary, GROW via the LPJmL-FIT
# turnover+allocation+allometry step (a faithful, differentiable port of
# turnover_tree.c / allocation_tree.c / allometry_tree.c).
#
# To validate that growth against the C binary we need a BEFORE state and an
# AFTER state connected by one year's bm_inc: start from year Y-1's structure,
# run F_diff over year Y, allocate the accumulated bm_inc, and compare the grown
# structure to year Y's actual C structure. This script reconstructs the
# per-individual pools (incl. HEARTWOOD, needed for the woody-growth check) and
# the cell aggregates for a span of years, reusing the step-3 reconstruction.
#
# Units (verified against LPJmL-FIT source /home/jamirp/lpjml56fit v5.6.004):
#  - ind-CSV npp/gpp = pft->anpp = per-m2 (patch-basis) annual NPP             [fwriteoutput_ind.c:92,147; npp_tree.c:53-54]
#  - ind-CSV agb/vegc = per-m2 (patch-basis): agb = (leaf+sapwood+heartwood)*nind  [agb_tree.c:25, tree.h:249]
#  - reconstructed leaf_c/sapwood_c/root_c = per-INDIVIDUAL (gC/tree, pipe model)
#  => heartwood_ind = agb_perm2/nind - leaf_ind - sapwood_ind
#  => per-individual annual bm_inc target = npp_perm2 / nind
#
# Run (login node OK):
#   /home/jamirp/.conda/envs/py311_new/bin/python scripts/extract_fdiff_individuals_multiyear.py
# Writes year-tagged per-individual CSVs + a compact committed validation
# reference (test/testitems/references/hainich_structure_growth_2009_2010.txt).
# =============================================================================
import json
import math
import os

import polars as pl

CELL = 42490
YEARS = [2008, 2009, 2010, 2011]
IND_PARQUET = "/p/tmp/jamirp/emulator_global/ind_hist_seed1_all.parquet"
REFDIR = os.path.join(os.path.dirname(__file__), "..", "test", "testitems", "references")
OUT_TMP = "/p/tmp/jamirp/esm_land_emulator_data/fdiff_structure"
NPATCH = 25
VSTEP = 2.0
K_LAMBERT = 0.5
CROWNLENGTH = 0.3334
EPS = 1e-6

# per-PFT allometry (par/pft_lpjmlfit.js ANGIO/GYMNO — the ACTIVE FIT file)
ANGIO = dict(allom1=117.44, allom2=28.749, allom3=0.5633, kpr=1.2922, crownarea_max=225.0, k_beer=0.59)
GYMNO = dict(allom1=101.34, allom2=31.4093, allom3=0.665, kpr=1.4163, crownarea_max=225.0, k_beer=0.45)
# id -> (name, alphaa, albedo_leaf, gymno?, emax)
PFT = {
    0: ("tropical broadleaved evergreen", 0.60, 0.15, False, 10.0),
    1: ("temperate needleleaved evergreen", 0.575, 0.12, True, 10.0),
    2: ("temperate broadleaved evergreen", 0.575, 0.15, False, 10.0),
    3: ("temperate broadleaved summergreen", 0.55, 0.15, False, 10.0),
    4: ("boreal needleleaved evergreen", 0.45, 0.12, True, 10.0),
    5: ("boreal broadleaved summergreen", 0.40, 0.15, False, 10.0),
    6: ("boreal needleleaved summergreen", 0.45, 0.12, True, 10.0),
    7: ("polar C3 grass", 0.50, 0.15, False, 5.0),
    8: ("temperate C3 grass", 0.50, 0.15, False, 5.0),
    9: ("tropical C4 grass", 0.40, 0.15, False, 7.0),
}


def allom(pid):
    return GYMNO if PFT.get(pid, PFT[3])[3] else ANGIO


def crown_area(pid, H):
    a = allom(pid)
    if H <= 0:
        return 0.0
    ca = a["allom1"] * (H / a["allom2"]) ** (a["kpr"] / a["allom3"])
    return min(ca, a["crownarea_max"])


def layered_light(trees):
    """Port of getfpar.c: per-PATCH vertical layered Beer-Lambert light."""
    if not trees:
        return 1.0
    for t in trees:
        t["fpar_leafon"] = 0.0
        cd = max(t["height"] - t["boleht"], EPS)
        t["atoh"] = min(t["leaf_c"] * t["sla"] / cd, 40.0)
    height_veg = max(t["height"] for t in trees)
    toplayer = int(height_veg / VSTEP - EPS)
    plai_leafon = 0.0
    fpar_bottom = 1.0
    for layer in range(toplayer, -1, -1):
        lowbound = layer * VSTEP
        highbound = lowbound + VSTEP
        fpar_top = fpar_bottom
        plai_layer = 0.0
        for t in trees:
            la = 0.0
            if t["height"] > lowbound and t["boleht"] < highbound and (t["height"] - t["boleht"]) > EPS:
                frac = 1.0
                if t["height"] < highbound:
                    frac -= (highbound - t["height"]) / VSTEP
                if t["boleht"] > lowbound:
                    frac -= (t["boleht"] - lowbound) / VSTEP
                la = t["atoh"] * frac * VSTEP * t["nind"]
            t["_la_layer"] = la
            plai_layer += la
        plai_leafon += plai_layer
        fpar_bottom = math.exp(-K_LAMBERT * plai_leafon)
        uptake = fpar_top - fpar_bottom
        if plai_layer > EPS:
            for t in trees:
                t["fpar_leafon"] += uptake * t["_la_layer"] / plai_layer
    return fpar_bottom


def reconstruct_year(df, year):
    """Reconstruct per-individual pools + layered light for one year. Returns
    (records, cell_aggregates)."""
    ydf = df.filter(pl.col("Year") == year)
    recs = []
    patches = sorted(ydf["Patch"].unique().to_list())
    for pnum in patches:
        pdf = ydf.filter(pl.col("Patch") == pnum)
        trees, grasses = [], []
        for r in pdf.iter_rows(named=True):
            pid = int(r["Type"])
            name, alphaa, albedo, is_gymno, emax = PFT.get(pid, PFT[3])
            a = allom(pid)
            H, LAI, SLA, rho = float(r["Height"]), float(r["LAI"]), float(r["SLA"]), float(r["Wooddens"])
            fpc = float(r["fpc_ind"])
            agb_perm2, vegc_perm2 = float(r["agb"]), float(r["vegc"])
            rec = dict(patch=int(pnum), type=pid, year=year, height=H, lai=LAI, sla=SLA, wooddens=rho,
                       fpc_ind=fpc, alphaa=alphaa, albedo_leaf=albedo, k_beer=a["k_beer"], emax=emax,
                       agb_perm2=agb_perm2, vegc_perm2=vegc_perm2, npp_perm2=float(r["npp"]))
            if pid <= 6 and H > 0:
                ca = crown_area(pid, H)
                leaf_c = LAI * ca / SLA if SLA > 0 and ca > 0 else 0.0
                denom = ca * (1.0 - math.exp(-a["k_beer"] * LAI)) if (ca > 0 and LAI > 0) else 0.0
                nind = fpc / denom if denom > EPS else 0.0
                c_sap = H * leaf_c * SLA * rho / 4000.0 if leaf_c > 0 else 0.0
                c_root = leaf_c  # lmro_ratio 1.0 (angio): fine-root ~ leaf carbon
                # heartwood per-individual from the C's per-m2 agb: agb = (leaf+sap+heart)*nind
                agb_ind = agb_perm2 / nind if nind > EPS else 0.0
                c_heart = max(agb_ind - leaf_c - c_sap, 0.0)
                boleht = (1.0 - CROWNLENGTH) * H
                bm_inc_ind = float(r["npp"]) / nind if nind > EPS else 0.0  # per-individual annual bm_inc
                rec.update(crownarea=ca, nind=nind, leaf_c=leaf_c, sapwood_c=c_sap, heartwood_c=c_heart,
                           root_c=c_root, boleht=boleht, agb_ind=agb_ind, bm_inc_ind=bm_inc_ind)
                trees.append(rec)
            else:
                rec.update(crownarea=0.0, nind=0.0, leaf_c=0.0, sapwood_c=0.0, heartwood_c=0.0,
                           root_c=0.0, boleht=0.0, agb_ind=0.0, bm_inc_ind=0.0)
                grasses.append(rec)
        fpar_ff = layered_light(trees)
        for g in grasses:
            g["fpar_leafon"] = fpar_ff * (1.0 - math.exp(-g["k_beer"] * g["lai"])) if g["lai"] > 0 else 0.0
        recs.extend(trees)
        recs.extend(grasses)
    # cell aggregates (per-m2, mean over patches): agb/vegc are already per-m2 in the CSV
    agb_cell = sum(r["agb_perm2"] for r in recs) / NPATCH
    vegc_cell = sum(r["vegc_perm2"] for r in recs) / NPATCH
    npp_cell = sum(r["npp_perm2"] for r in recs) / NPATCH
    n_trees = sum(1 for r in recs if r["type"] <= 6)
    tree_h = [r["height"] for r in recs if r["type"] <= 6]
    return recs, dict(year=year, agb_cell=agb_cell, vegc_cell=vegc_cell, npp_cell=npp_cell,
                      n_trees=n_trees, n_indiv=len(recs), mean_tree_height=sum(tree_h) / max(len(tree_h), 1))


def main():
    os.makedirs(OUT_TMP, exist_ok=True)
    os.makedirs(REFDIR, exist_ok=True)
    lf = pl.scan_parquet(IND_PARQUET)
    df = (
        lf.filter((pl.col("Cell") == CELL) & (pl.col("Year").is_in(YEARS)) & (pl.col("isdead") == 0))
        .select(["Type", "Patch", "Year", "Height", "LAI", "SLA", "Wooddens", "agb", "vegc", "fpc_ind", "npp"])
        .collect()
    )
    cols = ["patch", "type", "year", "height", "lai", "sla", "wooddens", "fpc_ind", "crownarea", "nind",
            "leaf_c", "sapwood_c", "heartwood_c", "root_c", "boleht", "agb_ind", "bm_inc_ind", "fpar_leafon",
            "alphaa", "albedo_leaf", "k_beer", "emax", "agb_perm2", "vegc_perm2", "npp_perm2"]
    aggs = []
    for year in YEARS:
        recs, agg = reconstruct_year(df, year)
        aggs.append(agg)
        out = os.path.join(OUT_TMP, f"hainich_individuals_{year}.csv")
        with open(out, "w") as f:
            f.write(f"# Hainich cell {CELL} seed1 year {year}: {len(recs)} living individuals, "
                    f"per-individual pools incl. heartwood. See extract_fdiff_individuals_multiyear.py.\n")
            f.write(",".join(cols) + "\n")
            for r in recs:
                f.write(",".join(f"{r.get(c, 0):.6g}" if isinstance(r.get(c, 0), float) else str(r.get(c, 0))
                                 for c in cols) + "\n")
        print(f"  {year}: agb_cell={agg['agb_cell']:.1f} vegc_cell={agg['vegc_cell']:.1f} "
              f"npp_cell={agg['npp_cell']:.2f} n_trees={agg['n_trees']} mean_H={agg['mean_tree_height']:.2f} -> {out}")

    # cell-aggregate growth reference (committed, compact — CI-runnable, no /p/tmp dependency)
    ref = os.path.join(REFDIR, "hainich_structure_growth.txt")
    with open(ref, "w") as f:
        f.write("# Hainich cell 42490 cell-aggregate carbon (per-m2, mean over 25 patches) by year, from the\n")
        f.write("# seed1 ind output. Validation target for the F_diff DYNAMIC (prognostic) canopy structure\n")
        f.write("# (scale-up step 6): starting from year Y-1 structure + running year Y forcing, F_diff's\n")
        f.write("# allocated bm_inc must reproduce the C's agb/vegc INCREMENT (dAGB = agb[Y]-agb[Y-1]).\n")
        f.write("# year  agb_cell  vegc_cell  npp_cell  n_trees  mean_tree_height  (gC/m2, gC/m2, gC/m2/yr, -, m)\n")
        for a in aggs:
            f.write(f"{a['year']}  {a['agb_cell']:.4f}  {a['vegc_cell']:.4f}  {a['npp_cell']:.4f}  "
                    f"{a['n_trees']}  {a['mean_tree_height']:.4f}\n")
    print(f"\nwrote {ref}")
    # deltas
    for i in range(1, len(aggs)):
        p, c = aggs[i - 1], aggs[i]
        print(f"  d{c['year']}: dAGB={c['agb_cell'] - p['agb_cell']:+.2f}  dVEGC={c['vegc_cell'] - p['vegc_cell']:+.2f}  "
              f"npp={c['npp_cell']:.2f} gC/m2/yr (turnover+mortality account for npp - dVEGC)")


if __name__ == "__main__":
    main()
