#!/usr/bin/env python3
# =============================================================================
# extract_cell_soilcolumn.py — PER-CELL soil column for the multi-cell coupled
# S+F+E driver (line M, milestone M1: per-cell input provisioning).
#
# WHY: `run_coupled_cell` is already N-cell-agnostic, but every biome cell was
# driven with **Hainich's** soil column (`references/hainich_soilcolumn.txt`),
# which was built ad-hoc with no committed script. This is that script,
# parameterized by cell — the first piece of per-cell input provisioning.
#
# EMITS the 3-data-column layout every Julia reader parses
# (`layer soildepth_mm whcs_mm rootdist`, whitespace-separated, `#` comments):
#   <OUT>/M_soilcolumn_<name>.txt  +  <OUT>/M_soilcolumn_meta.json
#
# ── THE DERIVATION (verified against LPJmL-FIT 5.6.004 source + output) ───────
#  * `soildepth_mm` = per-layer THICKNESS, read from `depth_bnds` of the run's
#    own `whc_nat.nc`. CELL-INVARIANT in the C: `src/soil/fscansoilpar.c:36-39`
#    declares `soildepth[NSOILLAYER]` as a file-scope global filled once from
#    `par/soil_20m.js` (200,300,500,1000x19,3000 mm) — asserted here, not assumed.
#    NB `depth(layer)` in the NetCDF is the layer CENTRE, not the thickness.
#    (`newgrid.c:282` also overwrites the per-cell Pelletier soil depth with a
#    flat 20 m, so there is no per-cell depth truncation to reproduce.)
#  * `whcs_mm[l] = whc_nat[l] * soildepth_mm[l]` — exactly the C's own
#    `whcs = whc * soildepth` (`include/soil.h:222`). WHC_NAT is the
#    PATCH-ENSEMBLE MEAN whc FRACTION (`src/soil/soilpar_output.c:42`:
#    `WHC_NAT[l] += patch->soil.whc[l]/stand->npatch`), written monthly as
#    float32. `whc[l] = wfc[l]-wpwp[l]` is recomputed 2x/day/patch by the
#    organic-matter-dependent Saxton-Rawls pedotransfer (`update_daily.c:211,265`
#    -> `pedotransfer.c:109`), so whc_nat DRIFTS in the carbon-bearing top layers
#    and is run-to-run nondeterministic under `-DPERMUTE`. There is no single
#    "the" whc for a cell: we take the mean over all monthly steps, accumulated
#    in float32. A documented CHOICE, not a fact.
#  * `rootdist` — vegetation-dependent, so genuinely per cell. Two forms:
#      ROOTDIST=beta_mean (DEFAULT): the fpc-weighted mean over the cell's living
#        trees of each individual's OWN profile, ported from the C's
#        `src/lpj/getrootdist.c`:
#            num_layer_new = #{l in 0..BOTTOMLAYER-1 : rootdepth > layerbound[l]}
#                            (capped at BOTTOMLAYER-1 = 21)
#            totalroots    = 1 - beta**(layerbound[num_layer_new]/10)   [cm]
#            rootdist[l]   = (beta**top_cm - beta**bot_cm) / totalroots, l <= num_layer_new
#        i.e. the Jackson profile RENORMALIZED over the depth the roots actually
#        reach, and layer 22 (20-23 m) never holds roots (the C array is
#        `rootdist_n[LASTLAYER]`, and `getwr` sums only 0..21). `beta_root` IS the
#        C's profile parameter (`new_tree.c:230`: `getbetaroot(2000 cm, D95max)`).
#        The rooted depth is not in the 29-col schema but is EXACTLY recoverable
#        by inverting the emitted `D95` (`fwriteoutput_ind.c:104`,
#        `D95 = ln(1-0.95*(1-beta**R))/ln beta`):
#            R_cm = ln(1 - (1-beta**D95)/0.95) / ln beta = min(rootdepth/10, 2000)
#        [VERIFIED on all 5 biome cells: R >= D95 for every individual, R <= 2000 cm].
#        Weight `w_i = fpc_ind / sum(fpc_ind)`: root carbon ~ leaf carbon
#        (lmro_ratio 1.0) ~ LAI*crownarea, of which `fpc_ind` is the patch-basis
#        monotone proxy available in the frozen schema.
#        NOT ported: `getrootdist`'s permafrost redistribution of roots below
#        `soil.mean_maxthaw` into the last thawed layer (needs the C's soil thaw
#        state, which no output carries). Its sediment branch is dead here because
#        `newgrid.c:282` pins every cell's soil depth to 20 m. [TODO if the boreal
#        cell's root profile turns out to matter.]
#      ROOTDIST=d95_scalar (LEGACY, what the committed Hainich column used): one
#        community scalar D95 -> `beta = 0.05**(1/D95_cm)`, UNNORMALIZED. Kept
#        because it is the gate below, and because it is the documented v1
#        simplification. It leaks the roots below 23 m for deep profiles.
#
# ── THE CORRECTNESS GATE (`GATE=yes`, default) ────────────────────────────────
#   Re-extracting cell 42490 in `d95_scalar` mode with `D95_CM=115` from the
#   single-cell run must reproduce the committed `hainich_soilcolumn.txt`
#   BYTE-IDENTICALLY in its data rows. Three load-bearing details:
#    (a) the fixture came from the SINGLE-CELL run
#        `daily_2000_2019_fdiff_val_c42490_seed1`, NOT the 512-task global run —
#        under `-DPERMUTE` those two diverge by up to 1.6e-4 relative in layer 0;
#    (b) the time mean must accumulate in float32 (the on-disk dtype); promoting
#        to float64 first changes 5 of the 23 printed values;
#    (c) the fixture's `D95 = 115 cm` is HAND-ROUNDED with no committed
#        derivation (the uncommitted generator JSON
#        `/p/tmp/jamirp/esm_land_emulator_data/fast_core_validation/hainich_c42490_soilcolumn.json`
#        records `"D95_cm": 115.0`; no parquet statistic equals it — the tree
#        mean is 116.63 cm in 2010 and 114.24 cm over all years), so the gate
#        passes it explicitly.
#   `hainich_soilcolumn.txt` itself is NEVER rewritten: it feeds many committed
#   ReferenceTests baselines, so regenerating it is an integration point
#   (guardrail 4 / ADR 0029). The emitted per-cell columns use the SAME rule for
#   every cell, Hainich included.
#
# Usage (login node; ~2 s/cell + a ~2 s `ind` parquet scan for all cells):
#   /home/jamirp/.conda/envs/py311_new/bin/python scripts/extract_cell_soilcolumn.py
# Env: CELLS="name:idx,..." YEAR D95_CM ROOTDIST=beta_mean|d95_scalar
#      WHC_SRC=percell|global OUT GATE=yes|no EMIT=yes|no
# =============================================================================
import glob
import json
import os
import sys

import netCDF4 as nc
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_biome_forcing import cells_from_env  # noqa: E402  (THE canonical cell registry)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFDIR = os.path.join(REPO, "test", "testitems", "references")
RUN_ROOT = "/p/tmp/jamirp/esm_land_daily"
GLOBAL_RUN = f"{RUN_ROOT}/daily_2000_2019_global_c0_67419_seed1/output"
IND_PARQUET = "/p/tmp/jamirp/emulator_global/ind_hist_seed1_all.parquet"

SOILDEPTH_C = np.array([200.0, 300.0, 500.0] + [1000.0] * 19 + [3000.0])  # par/soil_20m.js
NLAYER = 23
D95_FRAC = 0.05          # Jackson-1996: Y(D95) = 0.95  =>  beta**D95 = 0.05
WHCS_FLOOR = 1.0e-3      # mm; a zero whcs makes F_diff's `rel = w/whcs` NaN


def cell_ij(grid_path, cell):
    """(ilat, ilon) of an orderA 0-based cell index in a run's own grid.nc."""
    with nc.Dataset(grid_path) as g:
        cid = np.asarray(g["cellid"][:])
    idx = np.argwhere(cid == cell)
    if len(idx) == 0:
        raise ValueError(f"cell {cell} not in {grid_path}")
    return int(idx[0][0]), int(idx[0][1])


def find_whc_run(cell, src):
    """Which C run's `whc_nat.nc` to read for `cell`. `percell` (default) prefers
    a SINGLE-CELL re-run of that cell — the provenance of the committed Hainich
    column — and falls back to the global run."""
    if src == "global":
        return GLOBAL_RUN
    hits = sorted(glob.glob(f"{RUN_ROOT}/daily_*_c{cell}_seed1/output/whc_nat.nc"))
    return os.path.dirname(hits[0]) if hits else GLOBAL_RUN


def read_soil_geometry_and_whc(run, cell):
    """-> (soildepth_mm[23], whc_frac[23], nstep). The time mean accumulates in
    float32 (the on-disk dtype) — load-bearing for the byte-identity gate."""
    i, j = cell_ij(os.path.join(run, "grid.nc"), cell)
    with nc.Dataset(os.path.join(run, "whc_nat.nc")) as d:
        db = np.asarray(d["depth_bnds"][:])
        sd = (db[:, 1] - db[:, 0]) * 1000.0
        w = np.asarray(d["whc_nat"][:, :, i, j])          # (nstep, nlayer) float32
    if w.shape[1] != NLAYER:
        raise ValueError(f"cell {cell}: expected {NLAYER} layers, got {w.shape[1]}")
    if not np.array_equal(sd, SOILDEPTH_C):
        raise ValueError(f"layer thicknesses {sd} != par/soil_20m.js {SOILDEPTH_C}")
    if np.any(w < -1.0e30) or not np.all(np.isfinite(w)):
        raise ValueError(f"cell {cell}: whc_nat holds the -1e32 fill (not a land cell?)")
    return sd, w.mean(axis=0), int(w.shape[0])


def layer_bounds_cm(soildepth_mm):
    bot = np.cumsum(soildepth_mm) / 10.0
    return bot - soildepth_mm / 10.0, bot


def beta_profile(soildepth_mm, beta):
    """Per-layer fraction of the Jackson-1996 profile `Y(d) = 1 - beta**d`
    (d in cm), UNNORMALIZED — matching the committed fixture (whose scalar
    beta=0.9743 makes the C's totalroots normalization a no-op: beta**2300cm
    ~ 1e-26)."""
    top, bot = layer_bounds_cm(soildepth_mm)
    return np.asarray(beta) ** top - np.asarray(beta) ** bot


def rooted_depth_cm(beta, d95_cm):
    """Invert the emitted `ind` D95 (`fwriteoutput_ind.c:104`) back to the depth
    the roots reach, `R = min(rootdepth/10, soildepth*100)` in cm. `arg <= 0`
    means D95 sits at the unlimited-depth asymptote `ln(0.05)/ln(beta)` ⇒ R = inf
    ⇒ every layer is rooted (the C's `num_layer_new` cap then applies)."""
    arg = 1.0 - (1.0 - beta ** d95_cm) / 0.95
    return np.where(arg > 0.0, np.log(np.clip(arg, 1.0e-300, None)) / np.log(beta), np.inf)


def getrootdist(soildepth_mm, beta, d95_cm):
    """Port of `src/lpj/getrootdist.c` for ONE individual -> rootdist[NSOILLAYER].

    Jackson profile renormalized over the layers the roots actually reach; layer
    BOTTOMLAYER (22) never holds roots. The permafrost `mean_maxthaw`
    redistribution is not ported (see the header).
    """
    top, bot = layer_bounds_cm(soildepth_mm)
    n = len(soildepth_mm)
    bottomlayer = n - 1                                    # C: BOTTOMLAYER = 22
    beta = min(float(beta), 0.9999)                        # getrootdist.c:27-28
    r = float(rooted_depth_cm(np.float64(beta), np.float64(d95_cm)))
    k = int(np.sum(bot[:bottomlayer] < r))                 # num_layer_new
    k = min(k, bottomlayer - 1)                            # getrootdist.c:41-42
    rd = np.zeros(n)
    totalroots = 1.0 - beta ** bot[k]
    rd[: k + 1] = (beta ** top[: k + 1] - beta ** bot[: k + 1]) / totalroots
    return rd


def effective_d95_cm(soildepth_mm, rootdist):
    """Depth (cm) at which the emitted cumulative profile reaches 95 %, linearly
    interpolated inside the crossing layer — the diagnostic counterpart of the
    scalar D95, and what `stand_structure_tof` (src/run.jl) will read back."""
    top, bot = layer_bounds_cm(soildepth_mm)
    cum = np.cumsum(rootdist)
    l = int(np.searchsorted(cum, 0.95))
    if l >= len(cum):
        return float(bot[-1])
    prev = cum[l - 1] if l > 0 else 0.0
    f = (0.95 - prev) / max(rootdist[l], 1.0e-300)
    return float(top[l] + f * (bot[l] - top[l]))


def read_ind_roots(cells, year):
    """Per-cell living-TREE root data for `year` from the annual `ind` parquet.

    Tree test = `D95max > 0` (grass rows always carry D95max==0, Height==0,
    beta_root==0.8, D95==13.4251 cm). `Type` ids differ by biome, so a
    type-number test is NOT portable: 42490 has {1,2,3,4,5,8} but 18371/12045
    have {0,7}.
    """
    import polars as pl
    ids = [c for _, c in cells]
    df = (
        pl.scan_parquet(IND_PARQUET)
        .filter(
            pl.col("Cell").is_in(ids) & (pl.col("Year") == year)
            & (pl.col("isdead") == 0) & (pl.col("D95max") > 0)
        )
        .select(["Cell", "D95", "D95max", "beta_root", "fpc_ind", "agb"])
        .collect()
    )
    out = {}
    for cell in ids:
        s = df.filter(pl.col("Cell") == cell)
        if s.height == 0:
            continue
        out[cell] = dict(
            n_trees=s.height,
            beta=np.asarray(s["beta_root"], dtype=np.float64),
            fpc=np.asarray(s["fpc_ind"], dtype=np.float64),
            d95=np.asarray(s["D95"], dtype=np.float64),
            d95max=np.asarray(s["D95max"], dtype=np.float64),
        )
    return out


def build_rootdist(soildepth_mm, mode, roots, d95_override):
    """-> (rootdist[23], provenance string, diagnostics dict)."""
    if mode == "d95_scalar":
        d95 = float(d95_override) if d95_override else float(np.mean(roots["d95"]))
        beta = D95_FRAC ** (1.0 / d95)
        src = (
            f"scalar D95={d95:.4g}cm (override), beta={beta:.6f}" if d95_override else
            f"scalar D95={d95:.4g}cm = mean D95 over {roots['n_trees']} living trees, beta={beta:.6f}"
        )
        return beta_profile(soildepth_mm, beta), src, dict(d95_scalar_cm=d95, beta_scalar=beta)
    if mode != "beta_mean":
        raise ValueError(f"unknown ROOTDIST={mode!r}")
    b, w, d95 = roots["beta"], roots["fpc"], roots["d95"]
    wsum = w.sum()
    w = (w / wsum) if wsum > 0 else np.full_like(w, 1.0 / len(w))
    prof = np.stack([getrootdist(soildepth_mm, b[i], d95[i]) for i in range(len(b))])
    rd = (w[:, None] * prof).sum(axis=0)
    r = rooted_depth_cm(b, d95)
    src = (
        f"fpc-weighted mean of {roots['n_trees']} living trees' own getrootdist.c profiles "
        f"(mean beta_root {b.mean():.6f}, median rooted depth {np.median(r[np.isfinite(r)]):.0f} cm)"
    )
    diag = dict(
        beta_mean=float(b.mean()), beta_fpcw=float((w * b).sum()),
        d95_tree_mean_cm=float(d95.mean()), d95_tree_median_cm=float(np.median(d95)),
        d95max_tree_mean_cm=float(roots["d95max"].mean()),
        rooted_depth_median_cm=float(np.median(r[np.isfinite(r)])),
        n_rootdepth_unlimited=int(np.sum(~np.isfinite(r))), fpc_sum=float(wsum),
    )
    return rd, src, diag


def read_fixture(path):
    sd, whcs, rd = [], [], []
    for ln in open(path):
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        x = [float(t) for t in s.split()]
        sd.append(x[1]); whcs.append(x[2]); rd.append(x[3])
    return np.array(sd), np.array(whcs), np.array(rd)


def fmt_rows(soildepth, whcs, rootdist):
    """The committed print contract: layer `%d` (0-based), `%.1f`, `%.4f`,
    `%.6f`, single-space separated. EXACTLY 4 numeric fields per data row — the
    Julia readers `parse.(Float64, split(s))` the whole row, so a 5th column or
    any non-numeric token fails the whole suite at collection."""
    return [f"{l} {soildepth[l]:.1f} {whcs[l]:.4f} {rootdist[l]:.6f}" for l in range(len(soildepth))]


def build(name, cell, year, mode, roots, d95_override, whc_src):
    run = find_whc_run(cell, whc_src)
    sd, frac, nstep = read_soil_geometry_and_whc(run, cell)
    whcs = np.asarray(frac, dtype=np.float64) * sd
    if np.any(whcs <= WHCS_FLOOR):
        raise ValueError(f"cell {cell}: whcs {whcs} <= {WHCS_FLOOR} — would NaN F_diff's rel = w/whcs")
    rootdist, rsrc, diag = build_rootdist(sd, mode, roots, d95_override)
    # F_diff's water supply scales LINEARLY with sum(rootdist) (src/fdiff.jl:846,928)
    # and `stand_structure_tof` (src/run.jl:65) never terminates its D95 loop below
    # 0.95 — so a profile that does not sum to 1 is silently, physically wrong.
    # `beta_mean` sums to 1 by construction; the legacy `d95_scalar` form leaks the
    # tail below the column bottom, so it is only tolerance-checked.
    tol = 1.0e-9 if mode == "beta_mean" else 1.0e-6
    if abs(rootdist.sum() - 1.0) > tol:
        raise ValueError(f"cell {cell}: rootdist ({mode}) sums to {rootdist.sum()!r}, not 1")
    return dict(
        name=name, cell=cell, year=year, run=run, nstep=nstep, mode=mode,
        soildepth=sd, whcs=whcs, whc_frac=np.asarray(frac, dtype=np.float64),
        rootdist=rootdist, root_src=rsrc, diag=diag,
        d95_eff_cm=effective_d95_cm(sd, rootdist),
    )


def write_column(col, out_dir):
    path = os.path.join(out_dir, f"M_soilcolumn_{col['name']}.txt")
    with open(path, "w") as f:
        f.write(f"# {col['name']} (global orderA cell {col['cell']}) soil column for the multi-cell coupled S+F+E driver.\n")
        f.write(f"# {NLAYER} layers. soildepth_mm = per-layer thickness (LPJmL-FIT par/soil_20m.js; cell-invariant in the C).\n")
        f.write(f"# whcs_mm = whc_nat (patch-mean fraction, mean of {col['nstep']} monthly steps) x soildepth, from\n")
        f.write(f"#   {col['run']}\n")
        f.write(f"# rootdist = {col['root_src']}; effective D95 = {col['d95_eff_cm']:.1f} cm,\n")
        f.write(f"#   {col['rootdist'][:3].sum() * 100:.1f}% of roots in the top 1 m ({col['year']} canopy).\n")
        f.write(f"# top-1m plant-available = {col['whcs'][:3].sum():.4f} mm; total = {col['whcs'].sum():.4f} mm. scripts/extract_cell_soilcolumn.py\n")
        f.write("# layer soildepth_mm whcs_mm rootdist\n")
        f.write("\n".join(fmt_rows(col["soildepth"], col["whcs"], col["rootdist"])) + "\n")
    return path


def gate():
    """Reproduce the committed Hainich column byte-identically — the correctness
    proof that must pass before any other cell's column is trusted."""
    ref = os.path.join(REFDIR, "hainich_soilcolumn.txt")
    sd_r, whcs_r, rd_r = read_fixture(ref)
    col = build("gate_hainich", 42490, 2010, "d95_scalar", None, "115", "percell")
    dsd = float(np.max(np.abs(col["soildepth"] - sd_r)))
    dw = float(np.max(np.abs(col["whcs"] - whcs_r)))
    dr = float(np.max(np.abs(col["rootdist"] - rd_r)))
    rows_ref = [ln.strip() for ln in open(ref) if ln.strip() and not ln.startswith("#")]
    identical = rows_ref == fmt_rows(col["soildepth"], col["whcs"], col["rootdist"])
    ok = (dsd == 0.0) and (dw < 1.0e-4) and (dr < 1.0e-6) and identical
    print("== GATE: re-extract cell 42490 (d95_scalar, D95=115) vs committed hainich_soilcolumn.txt")
    print(f"   whc source           : {col['run']}")
    print(f"   max|d soildepth_mm|  : {dsd:.3e}   (exact match required)")
    print(f"   max|d whcs_mm|       : {dw:.3e} mm (tol 1e-4 = the %.4f print resolution)")
    print(f"   max|d rootdist|      : {dr:.3e}    (tol 1e-6 = the %.6f print resolution)")
    print(f"   all 23 printed data rows byte-identical: {identical}")
    print(f"   => GATE {'PASS' if ok else 'FAIL'}")
    return ok


def main():
    cells = cells_from_env()
    year = int(os.environ.get("YEAR", "2010"))
    out_dir = os.environ.get("OUT", REFDIR)
    whc_src = os.environ.get("WHC_SRC", "percell")
    mode = os.environ.get("ROOTDIST", "beta_mean")
    d95_override = os.environ.get("D95_CM", "").strip()

    if os.environ.get("GATE", "yes") == "yes" and not gate():
        print("FATAL: gate failed — do not trust any other cell's column", file=sys.stderr)
        return 2
    if os.environ.get("EMIT", "yes") != "yes":
        return 0

    roots = read_ind_roots(cells, year)
    os.makedirs(out_dir, exist_ok=True)
    print(f"\n== {len(cells)} per-cell soil columns (ROOTDIST={mode}, year {year}) -> {out_dir}")
    print(f"{'name':24s} {'cell':>6s} {'ntree':>6s} {'D95eff':>7s} {'top1m%':>7s} {'top1m_mm':>9s} {'total_mm':>9s} {'nstep':>6s}  whc run")
    rows = []
    for name, cell in cells:
        if cell not in roots:
            print(f"{name:24s} {cell:6d}  SKIPPED — no living trees in {year}")
            continue
        col = build(name, cell, year, mode, roots[cell], d95_override, whc_src)
        path = write_column(col, out_dir)
        print(
            f"{name:24s} {cell:6d} {roots[cell]['n_trees']:6d} {col['d95_eff_cm']:7.1f} "
            f"{col['rootdist'][:3].sum() * 100:7.1f} {col['whcs'][:3].sum():9.4f} "
            f"{col['whcs'].sum():9.2f} {col['nstep']:6d}  {os.path.basename(os.path.dirname(col['run']))}"
        )
        rows.append(dict(
            name=name, cell=cell, n_trees=roots[cell]["n_trees"], rootdist_mode=mode,
            d95_eff_cm=col["d95_eff_cm"], rootfrac_top1m=float(col["rootdist"][:3].sum()),
            whcs_top1m_mm=float(col["whcs"][:3].sum()), whcs_total_mm=float(col["whcs"].sum()),
            whc_frac_layer0=float(col["whc_frac"][0]), nstep=col["nstep"],
            whc_run=col["run"], file=os.path.basename(path), **col["diag"],
        ))
    meta = os.path.join(out_dir, "M_soilcolumn_meta.json")
    with open(meta, "w") as f:
        json.dump(dict(year=year, rootdist_mode=mode, whc_src=whc_src,
                       ind_parquet=IND_PARQUET, cells=rows), f, indent=2)
    print(f"wrote {meta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
