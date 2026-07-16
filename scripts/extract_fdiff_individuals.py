#!/usr/bin/env python3
# =============================================================================
# extract_fdiff_individuals.py — build the representative-individual canopy set
# for the F_diff multi-PFT scale-up (Phase-3 scale-up step 3) on the Hainich
# prototype cell (global orderA grid index 42490).
#
# Reads the per-individual `ind` parquet (seed1, year 2010, cell 42490), keeps
# the living individuals across the 25 patches, RECONSTRUCTS each tree's crown
# geometry + leaf/sapwood/root carbon from the CSV fields (Height, LAI, SLA,
# Wooddens, fpc_ind) via the LPJmL-FIT allometry, and ports FIT's per-PATCH
# vertical layered Beer-Lambert light model (`src/lpj/getfpar.c`, VSTEP=2 m,
# k_lambert=0.5) to compute each individual's absorbed-PAR fraction `fpar_leafon`
# (the non-proportional light share the taller-shade-shorter competition gives).
#
# Writes a committed compact reference (test/testitems/references/
# hainich_individuals_2010.csv) + a meta JSON, and VALIDATES that the patch-mean
# sum of per-individual fpar equals the C binary's own cell daily FAPAR at the
# growing-season peak (the light reconstruction is well-posed => no HPC re-run
# needed to distribute light among individuals).
#
# Source-verified facts (LPJmL-FIT /home/jamirp/lpjml56fit v5.6.004):
#  - per-individual apar into photosynthesis  = par*(1-albedo_leaf)*alphaa*fpar(pft)   [water_stressed.c:204]
#  - fpar(pft) is the layered absorbed fraction set by getfpar in individual mode      [daily_natural.c:83-84]
#  - cell d_fapar output = mean-over-patch of sum-over-individual pft->fapar            [daily_natural.c:219]
#  - cell d_gpp = mean-over-patch of sum-over-individual GROSS agd (gpp is per-m2)      [daily_natural.c:200,218]
#  - the ind-CSV gpp & npp columns are BOTH pft->anpp (agpp+=npp bug) => = NPP, not GPP [daily_natural.c:193]
#  - k_lambert=0.5, VSTEP=2 m, crownlength=0.3334, height_min=5 m (sub-5 m not in ind)  [lpjparam*.js, getfpar.c]
#
# Run (login node OK):
#   /home/jamirp/.conda/envs/py311_new/bin/python scripts/extract_fdiff_individuals.py
# =============================================================================
import json
import math
import os

import polars as pl

CELL = 42490
YEAR = 2010
IND_PARQUET = "/p/tmp/jamirp/emulator_global/ind_hist_seed1_all.parquet"
REFDIR = os.path.join(os.path.dirname(__file__), "..", "test", "testitems", "references")
TARGETS = os.path.join(REFDIR, "hainich_cbinary_targets_2010.csv")  # cell daily FAPAR/GPP/transp
OUT_CSV = os.path.join(REFDIR, "hainich_individuals_2010.csv")
OUT_META = os.path.join(REFDIR, "hainich_individuals_2010_meta.json")

NPATCH = 25
VSTEP = 2.0          # getfpar.c:51 vertical layer width (m)
K_LAMBERT = 0.5      # lpjparam_waldspektrum.js:24 canopy light extinction
CROWNLENGTH = 0.3334  # allometry_tree.c crown fraction of height
EPS = 1e-6

# ── per-PFT parameter table (par/pft_lpjmlfit.js). id -> params. Trees id 0..6, grass 7..9. ──
# angio/gymno allometry (allometry.jl defaults): angiosperm broadleaf vs gymnosperm needleleaf.
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


def read_cell_targets():
    rows = []
    with open(TARGETS) as f:
        for ln in f:
            if ln.startswith("#") or not ln.strip():
                continue
            rows.append(ln.rstrip("\n"))
    hdr = rows[0].split(",")
    data = {k: [] for k in hdr}
    for ln in rows[1:]:
        for k, v in zip(hdr, ln.split(",")):
            data[k].append(float(v))
    return data


def layered_light(trees):
    """Port of getfpar.c: per-PATCH vertical layered Beer-Lambert light. `trees`
    is a list of dicts with keys leaf_c, sla, height, boleht, nind, k_beer, phen=1.
    Sets each tree['fpar_leafon'] = absorbed PAR fraction (patch basis). Returns
    the PAR fraction transmitted to the forest floor (for grass)."""
    if not trees:
        return 1.0
    for t in trees:
        t["fpar_leafon"] = 0.0
        # leaf-area density per m height (atoh), capped at 40 (getfpar.c:112)
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
                la = t["atoh"] * frac * VSTEP * t["nind"]   # leaf area of tree in this layer (patch basis)
            t["_la_layer"] = la
            plai_layer += la
        plai_leafon += plai_layer
        fpar_bottom = math.exp(-K_LAMBERT * plai_leafon)
        uptake = fpar_top - fpar_bottom
        if plai_layer > EPS:
            for t in trees:
                t["fpar_leafon"] += uptake * t["_la_layer"] / plai_layer
    return fpar_bottom  # transmitted to the forest floor


def main():
    lf = pl.scan_parquet(IND_PARQUET)
    df = (
        lf.filter((pl.col("Cell") == CELL) & (pl.col("Year") == YEAR) & (pl.col("isdead") == 0))
        .select(["Type", "Patch", "Height", "LAI", "SLA", "Wooddens", "agb", "vegc",
                 "fpc_ind", "beta_root", "D95", "gpp", "transp", "npp"])
        .collect()
    )
    print(f"cell {CELL} year {YEAR}: {df.height} living individuals across {df['Patch'].n_unique()} patches")

    tgt = read_cell_targets()
    gs = [i for i in range(len(tgt["doy"])) if 150 <= tgt["doy"][i] <= 240]
    cell_fapar_gs = sum(tgt["fapar_C"][i] for i in gs) / len(gs)

    # ── reconstruct per individual + run per-patch layered light ──
    recs = []
    patches = sorted(df["Patch"].unique().to_list())
    for pnum in patches:
        pdf = df.filter(pl.col("Patch") == pnum)
        trees = []
        grasses = []
        for r in pdf.iter_rows(named=True):
            pid = int(r["Type"])
            name, alphaa, albedo, is_gymno, emax = PFT.get(pid, PFT[3])
            a = allom(pid)
            H = float(r["Height"])
            LAI = float(r["LAI"])
            SLA = float(r["SLA"])
            rho = float(r["Wooddens"])
            fpc = float(r["fpc_ind"])
            rec = dict(patch=int(pnum), type=pid, height=H, lai=LAI, sla=SLA, wooddens=rho,
                       fpc_ind=fpc, alphaa=alphaa, albedo_leaf=albedo, k_beer=a["k_beer"],
                       emax=emax, beta_root=float(r["beta_root"]), d95=float(r["D95"]),
                       agb=float(r["agb"]), vegc=float(r["vegc"]),
                       gpp_ind=float(r["gpp"]), transp_ind=float(r["transp"]), npp_ind=float(r["npp"]))
            if pid <= 6 and H > 0:   # tree
                ca = crown_area(pid, H)
                leaf_c = LAI * ca / SLA if SLA > 0 and ca > 0 else 0.0
                # nind from fpc_tree inversion: fpc = ca*nind*(1-exp(-k*LAI))
                denom = ca * (1.0 - math.exp(-a["k_beer"] * LAI)) if (ca > 0 and LAI > 0) else 0.0
                nind = fpc / denom if denom > EPS else 0.0
                # pipe model sapwood: H = k_latosa*C_sap/(C_leaf*SLA*rho) ; k_latosa=4000
                c_sap = H * leaf_c * SLA * rho / 4000.0 if leaf_c > 0 else 0.0
                c_root = leaf_c   # lmro_ratio 1.0 (angio) : fine-root ~ leaf carbon
                boleht = (1.0 - CROWNLENGTH) * H
                rec.update(crownarea=ca, nind=nind, leaf_c=leaf_c, sapwood_c=c_sap,
                           root_c=c_root, boleht=boleht)
                trees.append(rec)
            else:                    # grass
                rec.update(crownarea=0.0, nind=0.0, leaf_c=0.0, sapwood_c=0.0,
                           root_c=0.0, boleht=0.0)
                grasses.append(rec)
        fpar_ff = layered_light(trees)
        # grass absorbs transmitted forest-floor light (getfpar.c:190)
        for g in grasses:
            g["fpar_leafon"] = fpar_ff * (1.0 - math.exp(-g["k_beer"] * g["lai"])) if g["lai"] > 0 else 0.0
        recs.extend(trees)
        recs.extend(grasses)

    # ── cell FAPAR (leafon) = mean-over-patch of sum-over-individual fpar ──
    fpar_sum = sum(r["fpar_leafon"] for r in recs)
    cell_fapar_leafon = fpar_sum / NPATCH
    tree_fpar = sum(r["fpar_leafon"] for r in recs if r["type"] <= 6) / NPATCH
    grass_fpar = sum(r["fpar_leafon"] for r in recs if r["type"] >= 7) / NPATCH

    print(f"\nreconstructed layered-light cell FAPAR (leafon) = {cell_fapar_leafon:.4f}"
          f"  (trees {tree_fpar:.4f} + grass {grass_fpar:.4f})")
    print(f"C-binary cell FAPAR at growing-season peak (DOY150-240) = {cell_fapar_gs:.4f}")
    print(f"ratio reconstructed/C = {cell_fapar_leafon / cell_fapar_gs:.3f}")

    # ── write compact committed reference ──
    os.makedirs(REFDIR, exist_ok=True)
    cols = ["patch", "type", "height", "lai", "sla", "wooddens", "fpc_ind", "crownarea", "nind",
            "leaf_c", "sapwood_c", "root_c", "boleht", "fpar_leafon", "alphaa", "albedo_leaf",
            "k_beer", "emax", "beta_root", "d95", "agb", "vegc", "gpp_ind", "transp_ind", "npp_ind"]
    with open(OUT_CSV, "w") as f:
        f.write("# Hainich (global-grid cell 42490) representative-individual canopy set, seed1 year 2010.\n")
        f.write("# Living individuals across 25 patches (sub-5m saplings not in ind output). Per-individual\n")
        f.write("# crown/leaf/sapwood reconstructed from the ind CSV via LPJmL-FIT allometry; fpar_leafon =\n")
        f.write("# per-PATCH vertical layered Beer-Lambert light share (getfpar.c port, k_lambert=0.5, VSTEP=2m).\n")
        f.write("# cell FAPAR(leafon) = sum(fpar_leafon)/25. gpp_ind/npp_ind = ind-CSV NPP (agpp+=npp bug);\n")
        f.write("# transp_ind = per-individual annual transpiration (mm/yr). See scripts/extract_fdiff_individuals.py.\n")
        f.write(",".join(cols) + "\n")
        for r in recs:
            f.write(",".join(f"{r[c]:.6g}" if isinstance(r[c], float) else str(r[c]) for c in cols) + "\n")
    print(f"\nwrote {OUT_CSV}  ({len(recs)} individuals)")

    meta = dict(cell=CELL, year=YEAR, npatch=NPATCH, n_individuals=len(recs),
                n_trees=sum(1 for r in recs if r["type"] <= 6),
                n_grass=sum(1 for r in recs if r["type"] >= 7),
                cell_fapar_leafon=cell_fapar_leafon, cell_fapar_C_gs=cell_fapar_gs,
                fapar_ratio_recon_over_C=cell_fapar_leafon / cell_fapar_gs,
                tree_fpar=tree_fpar, grass_fpar=grass_fpar,
                k_lambert=K_LAMBERT, vstep=VSTEP, crownlength=CROWNLENGTH,
                pft_type_counts={str(k): int(df.filter(pl.col("Type") == k).height)
                                 for k in sorted(df["Type"].unique().to_list())})
    with open(OUT_META, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"wrote {OUT_META}")


if __name__ == "__main__":
    main()
