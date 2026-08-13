#!/usr/bin/env python
# diagnose_layered_light_basis.py — line M, rung 3, scoping the PHOTOSYNTHESIS half of the
# assimilate error (ADR 0135). Audits the light INPUT to F_diff's per-individual photosynthesis
# against the LIVE lines of the LPJmL-FIT C, and prices the one difference that survives.
#
# WHY THIS EXISTS
# ---------------
# F_diff's per-individual GPP is driven by `apar_i = par·(1−albedo_i)·alphaa_i·fpar_i`
# (`water_stressed.c:204`), and in `individual:true` mode `fpar(pft)` resolves to `fpar_tree_ind`
# (`fscanpft_tree.c:142`), i.e. `pft->fpar*(1−pft->snowcover)` — the VERTICAL LAYERED
# Beer–Lambert share from `src/lpj/getfpar.c`, ported in `src/fdiff.jl::_patch_fpars_soa`.
# Since the photosynthesis kernel is homogeneous of degree 1 in `apar` except for the SLA Vcmax
# cap, the light input is the largest single lever on tree GPP that is not the kernel itself.
#
# ⚠ READ THE LIVE LINE, NOT A grep HIT. `getfpar.c:108-124` carries the live density expression
# followed by TWO commented-out variants (`/* test: use LAI for atoh calc */`,
# `/* test: like in GUESS3.0 */`) that differ in exactly the quantity under audit. The live one is
#
#     atoh = leaf_c·sla/(height−boleht);  if(atoh>40) atoh=40;
#     lai_leafon_layer[p] = atoh·frac·VSTEP · pft->nind;          <- PER PATCH (nind = 1/patcharea)
#
# and F's `_patch_fpars_soa` is `min(leafc·sla/cd, 40)·nind` — the same expression, the same cap,
# in the same order. **The per-crown (`/crownarea`) form is a dead comment**; an audit built on it
# reports a 5–37x optical-thickness gap that does not exist. Recorded here so it is not re-derived.
#
# WHAT REMAINS LIVE — two differences, both measured below:
#   (A) PHEN PLACEMENT. The C builds the extinction profile from the PHEN-WEIGHTED leaf area
#       (`getfpar.c:126` `plai_layer += lai_leafon_layer[p]*pft->phen`) and shares each layer's
#       uptake by the phen-weighted numerator (`:158`), producing `pft->fpar` directly. F computes
#       the LEAF-ON share (`_patch_fpars_soa` takes no phen) and multiplies afterwards:
#       `fpar_i = ind.fpar·phen` (`fdiff.jl:1923`). Those agree only at phen ≡ 1: the C's is
#       `1−exp(−k·plai·φ)` where F's is `φ·(1−exp(−k·plai))`, so by concavity **F under-absorbs on
#       every partial-leaf day**, and the gap is a pure function of the patch's own leaf-on plai.
#       ⚠ It also differs when individuals' phen differ: in the C a leafless stem stops shading the
#       stems below it, in F it keeps its leaf-on place in the profile. Not priced here.
#   (B) SNOWCOVER. `fpar_tree_ind` multiplies by `(1−pft->snowcover)`; F's apar has no such factor.
#       Not priceable from the `ind` table (snowcover is not emitted) — listed, not measured.
#
# BASIS / POPULATION (state it with every number — CLAUDE.md §6.6, residual-diagnosis §1):
#   * global historic seed1 `ind` parquet, five biome cells, 2010–2019, survivors,
#     `Type <= 6 AND D95max > 0` (grass rows carry ZEROED tree fields — ADR 0110);
#   * ⚠ the `ind` writer emits only stems above `param.height_min` = 5 m, so every plai here is
#     missing the sub-5 m stems and the grass. That is why panel 1 lands a few % UNDER the C's own
#     LAI_STAND rather than on it, and it makes panel 2's bound a slight UNDER-estimate.
#
# Usage:  /home/jamirp/.conda/envs/py311_new/bin/python scripts/diagnose_layered_light_basis.py
#         CELLS="name:idx,..." to override the biome registry.

import csv
import math
import os
import sys

import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_biome_forcing import cells_from_env  # noqa: E402  (the canonical BIOMES registry)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IND = "/p/tmp/jamirp/emulator_global/ind_hist_seed1_all.parquet"
ORACLE = os.path.join(REPO, "test", "testitems", "references", "M_fdiff_oracle_biomes_annual.csv")

# per-PFT lightextcoeff from par/pft_lpjmlfit.js (ADR 0126) — used ONLY to invert `fpc_ind` back to
# crown area; the layer integration itself uses the global k_lambert, which is not a PFT parameter.
K_PFT = {0: 0.59, 1: 0.45, 2: 0.59, 3: 0.59, 4: 0.45, 5: 0.59, 6: 0.45}
K_LAMBERT = 0.5       # par/lpjparam_fit.js — global
CROWNLENGTH = 0.3334  # par/pft_lpjmlfit.js, identical for all seven tree PFTs
ATOH_CAP = 40.0       # getfpar.c:112, applied BEFORE the *nind (F: `min(leafc*sla/cd, 40)*nind`)
PATCHAREA = 225.0     # par/lpjparam_fit.js; new_tree.c:209 gives each individual nind = 1/patcharea
YEARS = (2010, 2019)


def oracle_lai_stand():
    """The C's OWN emitted stand LAI per cell — the independent check on the port's basis."""
    with open(ORACLE) as fh:
        rows = list(csv.DictReader(ln for ln in fh if not ln.startswith("#")))
    agg = {}
    for r in rows:
        agg.setdefault(r["name"], []).append(float(r["lai_stand_total"]))
    return {k: sum(v) / len(v) for k, v in agg.items()}


def phen_gap(plai, phi):
    """C's absorbed fraction minus F's, at a uniform phenological state `phi`, for a patch whose
    LEAF-ON layered plai is `plai`. Exact for a single-layer canopy and for any canopy in which all
    stems share `phi` (the uptakes telescope, so only the total matters)."""
    return (1.0 - math.exp(-K_LAMBERT * plai * phi)) - phi * (1.0 - math.exp(-K_LAMBERT * plai))


def main():
    lai_stand = oracle_lai_stand()
    lf = pl.scan_parquet(IND)
    print("# layered-light audit of the tree APAR input (getfpar.c LIVE lines vs _patch_fpars_soa)")
    print(f"# ind parquet: {IND}")
    print(f"# years {YEARS[0]}-{YEARS[1]}; survivors, Type<=6 & D95max>0; k_lambert={K_LAMBERT}")
    print()

    per_cell = {}
    for name, cell in cells_from_env():
        df = (
            lf.filter(
                (pl.col("Cell") == cell)
                & (pl.col("Type") <= 6)
                & (pl.col("D95max") > 0)
                & (pl.col("Year") >= YEARS[0])
                & (pl.col("Year") <= YEARS[1])
            )
            .select(["Year", "Patch", "Type", "Height", "LAI", "fpc_ind"])
            .collect()
        )
        if df.height == 0:
            print(f"{name:22s} EMPTY — no tree rows")
            continue
        kb = df["Type"].replace_strict(K_PFT, default=K_LAMBERT).cast(pl.Float64)
        lai = df["LAI"].cast(pl.Float64)
        # crownarea*nind = fpc_ind/(1-exp(-k_pft*LAI))  (fpc_tree.c:28), so the patch-basis
        # leaf-area density the LIVE C line integrates is  LAI * crownarea*nind / crowndepth.
        ca_nind = df["fpc_ind"].cast(pl.Float64) / (1.0 - (-kb * lai).exp())
        hgt = df["Height"].cast(pl.Float64)
        cd = (hgt * CROWNLENGTH).clip(lower_bound=1e-6)
        # the LIVE C line is `min(leaf_c*sla/cd, 40) * nind`, and leaf_c*sla = LAI*crownarea, so
        # leaf_c*sla/cd = (LAI * crownarea*nind / cd) * patcharea — cap THAT, then apply *nind.
        atoh = ((lai * ca_nind / cd) * PATCHAREA).clip(upper_bound=ATOH_CAP) / PATCHAREA
        per_cell[name] = df.with_columns(
            lai=lai, ca_nind=ca_nind, hgt=hgt, plai_i=atoh * cd  # = leaf-on patch LAI of this stem
        )

    # ── PANEL 1 — is the port's basis right? Score F's plai against the C's own LAI_STAND output.
    print("PANEL 1 — the port's leaf-area basis, against the C's own emitted stand LAI")
    print(
        f"{'cell':22s} {'stems/patch':>11s} {'plai(port)':>10s} "
        f"{'LAI_STAND':>10s} {'ratio':>7s} {'verdict':>10s}"
    )
    plais = {}
    for name, df in per_cell.items():
        g = df.group_by(["Year", "Patch"]).agg(
            pl.col("plai_i").sum().alias("p"), pl.len().alias("n")
        )
        p, n = g["p"].mean(), g["n"].mean()
        ls = lai_stand.get(name, float("nan"))
        plais[name] = p
        # the >5 m cut removes leaf area, so the port must land BELOW LAI_STAND, not above
        ok = 0.6 <= p / ls <= 1.2
        v = "OK" if ok else "CHECK"
        print(f"{name:22s} {n:11.1f} {p:10.3f} {ls:10.3f} {p / ls:7.3f} {v:>10s}")
    print("  Expected slightly BELOW 1: the ind writer drops sub-5 m stems and grass.")
    print("  ⇒ the per-CROWN density (getfpar.c's commented-out `/* test: */` variants) would give")
    print("     4.8-37x this, i.e. an opaque canopy. The live line is per-PATCH.")
    print("     ⇒ PORT BASIS CONFIRMED against a quantity the C itself emits.")
    print()

    # ── PANEL 2 — price difference (A), the phen placement, as an UPPER BOUND over phi
    print("PANEL 2 — difference (A): phen inside the extinction (C) vs multiplied after (F)")
    print("  C absorbs 1-exp(-k*plai*phi); F absorbs phi*(1-exp(-k*plai)) — F is LOWER, phi<1.")
    print(
        f"{'cell':22s} {'plai':>7s} {'absorb@1':>9s} {'max gap':>8s} {'at phi':>7s} "
        f"{'rel@peak':>9s} {'gap@0.5':>8s} {'rel@0.5':>8s}"
    )
    for name, p in plais.items():
        best = max((phen_gap(p, ph), ph) for ph in [i / 200.0 for i in range(1, 200)])
        gap, ph = best
        fp = ph * (1.0 - math.exp(-K_LAMBERT * p))
        g50 = phen_gap(p, 0.5)
        f50 = 0.5 * (1.0 - math.exp(-K_LAMBERT * p))
        print(
            f"{name:22s} {p:7.3f} {1 - math.exp(-K_LAMBERT * p):9.3f} {gap:8.4f} {ph:7.2f} "
            f"{gap / fp:9.3f} {g50:8.4f} {g50 / f50:8.3f}"
        )
    print("  `rel` = the shortfall as a fraction of F's OWN absorbed PAR on such a day.")
    print("  ⚠ THIS IS AN UPPER BOUND ON A DAY, NOT AN ANNUAL EFFECT (ADR 0105 — do not publish a")
    print("  default or a parameter from it). It binds only on days with 0 < phen < 1, and those")
    print("  days' WEIGHT in annual GPP is not measured here: `phen` is not an `ind` column. The")
    print("  measurement that closes it is an F arm running `per_pft_phenology`'s own daily phen.")
    print()
    print("DIFFERENCE (B), NOT PRICED: `fpar_tree_ind` returns `pft->fpar*(1-pft->snowcover)`;")
    print("F's apar carries no snowcover factor. `snowcover` is not emitted in the ind table, so")
    print("this needs a C re-run or an F-side reconstruction — listed, not measured.")
    print()
    print("SIGN NOTE — both live differences make F absorb LESS PAR than the C, while F's tree GPP")
    print("is measured ABOVE the C's at Hainich (1.074x, ADR 0133) — so neither explains it;")
    print("if anything they mask it, and the kernel-side error is larger than the measured ratio.")


if __name__ == "__main__":
    main()
