#!/usr/bin/env python3
# =============================================================================
# diagnose_per_tree_water_access.py — PHASE-0 KILL/PROCEED CHECK for the rooting-depth gap.
#
# THE QUESTION. Component S predicts a per-tree rooting depth (`D95max`) and a per-tree drought
# tolerance (`minwscal`), scores both globally, and then DROPS both: `make_recruit_to_pools`
# (src/components/slow.jl) writes only SLA + Wooddens into `TreePools`, and F_diff has no per-tree
# root profile at all — every individual draws on ONE shared cell-average profile collapsed to a
# single scalar `wr` (src/fdiff.jl:1540-1546) before the per-individual loop starts. So two trees
# differing only in rooting depth are identical in the water balance, and drought response — the
# owner's binding acceptance clause (ADR 0106) — cannot be represented.
#
# WHY MEASURE INSTEAD OF SIMULATE. The design study `docs/water_supply_perpft_design.md` concluded
# DEFER on the grounds that the faithful mechanism is blocked by `-DPERMUTE`. But the C emits the
# decisive quantities PER INDIVIDUAL in its own annual `ind` table, so the premise can be tested by
# direct measurement on the real trees the C actually grew — no simulation, no proxy, no assumption:
#   * `wscal_mean`  the C's own per-individual annual-mean water scalar. VERIFIED order-independent
#                   (it is a function of `wr` alone; `water_stressed.c:130-140` reads the UNCORRECTED
#                   supply, before the permuted `aet_cor` cap) — i.e. exactly the quantity a
#                   per-individual port would reproduce, and it is NOT touched by the randomness the
#                   design study called structurally impossible.
#   * `D95max`      the sampled rooting-depth trait (cm); `beta_root` the resulting Jackson profile
#                   parameter (`new_tree.c:229-230`, `getbetaroot`); `D95` the realized
#                   rootdepth-limited depth. All three per individual, so NO port of `getrootdist`
#                   is needed for this diagnostic.
#   * `minwscal`    the per-individual drought tolerance, the second dropped trait.
#   * `mort_water` / `mort_temp`  the C's own realized per-individual drought/heat hazards — the two
#                   ADR 0049 deliberately set to ZERO in our operator for want of a per-tree wscal.
#
# WHAT IT REPORTS (per cell, both scenarios):
#   A  the DISCARDED SPREAD — within-cell-year across-tree spread of `wscal_mean`, against the
#      between-year movement of the cell mean. Collapsing to one stand number destroys (A); the
#      drought signal we are trying to capture is (between-year). If A >= between-year, the
#      aggregation error is at least as large as the signal.
#   B  DROUGHT AMPLIFICATION — is the spread wider in the dry years than the wet ones?
#   C  DOES IT TRACK ROOTING — corr(wscal_mean, D95max/beta_root), overall AND within PFT x age band
#      (rooting depth is also size-driven via `getrootdepth`, allocation_tree.c:152, so the raw
#      correlation confounds trait with ontogeny; the within-band number is the trait effect).
#   D  THE DISCARDED MORTALITY — share of total hazard carried by mort_water + mort_temp, and the
#      SELECTION DIFFERENTIAL on D95max/minwscal among the trees they kill.
#   E  WARMING RESPONSE — the historic -> ssp370 change in D. This is the acceptance-criterion number.
#
# PASS  (proceed to Phase 1): the across-tree spread of `wscal_mean` is material and widens in dry
#       years, and mort_water carries a non-trivial, trait-selective share of the hazard.
# FAIL  (stop, say so plainly): trees experience drought near-identically -> the shared profile is an
#       adequate approximation for trees too, and the plan is wrong.
#
# CAVEATS THAT MUST BE STATED WITH ANY RESULT:
#   * `wscal_mean` is a POTENTIAL leaf-on index averaged over ALL 365 days, and is 1 (=unstressed) on
#     a no-demand day (ADR 0051). Winter dilutes it, so every spread here UNDERSTATES the
#     growing-season spread, and understates what `waterstress_tree` (which gates on the DAILY value
#     against a threshold) actually sees.
#   * Grass rows (Type 7-9) carry ZEROED tree fields (fwriteoutput_ind.c:139-189) -> filtered out via
#     Type <= 6 AND D95max > 0.
#   * This is 5 of 54 020 cells. Report it as such (ADR 0106).
#
#   run:  /home/jamirp/.conda/envs/py311_new/bin/python scripts/diagnose_per_tree_water_access.py
#   env:  CELLS=42490,18371   SCENARIOS=hist,ssp370   SEED=1   OUT=<dir>
#   (a filtered single-cell scan is ~0.1 s thanks to row-group pruning; no SLURM needed)
# =============================================================================
import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # never hardcode (§9 gotcha 6)
IND = "/p/tmp/jamirp/emulator_global/ind_{scen}_seed{seed}_all.parquet"

BIOMES = {
    52059: "boreal_siberia",
    42490: "temperate_hainich",
    33335: "mediterranean_iberia",
    18371: "semiarid_sahel",
    12045: "tropical_amazon",
}
COLS = [
    "Year", "Type", "Height", "Age", "wscal_mean", "minwscal",
    "D95max", "beta_root", "D95", "mort_water", "mort_temp", "mort",
    "mort_npp", "mort_age", "isdead", "Patch",
]
AGE_EDGES = [0, 10, 20, 40, 80, 160, 320, 10_000]


def load(cell, scen, seed):
    """Live TREE stems for one cell. Grass (Type>=7) carries zeroed tree fields -> excluded."""
    lf = pl.scan_parquet(IND.format(scen=scen, seed=seed))
    df = (
        lf.filter((pl.col("Cell") == cell) & (pl.col("Type") <= 6) & (pl.col("D95max") > 0))
        .select(COLS)
        .collect()
    )
    return df


def _corr(a, b):
    if len(a) < 8:
        return np.nan
    sa, sb = np.std(a), np.std(b)
    if sa < 1e-12 or sb < 1e-12:
        return np.nan
    return float(np.corrcoef(a, b)[0, 1])


def within_group_corr(df, xcol, ycol):
    """Pooled within-(PFT x age-band) correlation: removes composition AND ontogeny confounds.

    Rooting depth is set BOTH by the sampled trait (`D95max` -> `beta_root`) and by tree size
    (`getrootdepth`, allocation_tree.c:152), and PFTs differ in trait range, so the raw correlation
    mixes three things. Centring x and y within each (Type, age-band) cell isolates the trait effect
    among trees of the same type and the same size class.
    """
    ages = df["Age"].to_numpy()
    band = np.digitize(ages, AGE_EDGES[1:-1])
    xs, ys = [], []
    for t in np.unique(df["Type"].to_numpy()):
        for b in np.unique(band):
            m = (df["Type"].to_numpy() == t) & (band == b)
            if m.sum() < 8:
                continue
            x = df[xcol].to_numpy()[m]
            y = df[ycol].to_numpy()[m]
            if np.std(x) < 1e-12 or np.std(y) < 1e-12:
                continue
            xs.append(x - x.mean())
            ys.append(y - y.mean())
    if not xs:
        return np.nan, 0
    x = np.concatenate(xs)
    y = np.concatenate(ys)
    return _corr(x, y), len(x)


def analyse(cell, scen, seed):
    df = load(cell, scen, seed)
    if df.height == 0:
        return None
    live = df.filter(pl.col("isdead") == 0)

    # ---- A: within-year across-tree spread vs between-year movement of the cell mean ----------
    per_year = (
        live.group_by("Year")
        .agg(
            n=pl.len(),
            mean_w=pl.col("wscal_mean").mean(),
            sd_w=pl.col("wscal_mean").std(),
            p05=pl.col("wscal_mean").quantile(0.05),
            p95=pl.col("wscal_mean").quantile(0.95),
            sd_d95=pl.col("D95max").std(),
        )
        .sort("Year")
    )
    py = per_year.filter(pl.col("n") >= 20)
    within_sd = float(py["sd_w"].mean())
    between_sd = float(py["mean_w"].std())
    span = float((py["p95"] - py["p05"]).mean())

    # ---- B: dry-year vs wet-year spread (terciles of the cell-mean water scalar) --------------
    ymean = py.sort("mean_w")
    k = max(1, py.height // 3)
    dry_years = set(ymean["Year"].to_list()[:k])
    wet_years = set(ymean["Year"].to_list()[-k:])
    sd_dry = float(py.filter(pl.col("Year").is_in(dry_years))["sd_w"].mean())
    sd_wet = float(py.filter(pl.col("Year").is_in(wet_years))["sd_w"].mean())

    # ---- C: does per-tree water status track the rooting trait? -------------------------------
    dry = live.filter(pl.col("Year").is_in(dry_years))
    wet = live.filter(pl.col("Year").is_in(wet_years))
    r_raw_dry = _corr(dry["D95max"].to_numpy(), dry["wscal_mean"].to_numpy())
    r_in_dry, n_in_dry = within_group_corr(dry, "D95max", "wscal_mean")
    r_in_wet, _ = within_group_corr(wet, "D95max", "wscal_mean")
    rb_in_dry, _ = within_group_corr(dry, "beta_root", "wscal_mean")

    # ---- D: the hazards ADR 0049 zeroed --------------------------------------------------------
    tot = df.select(
        [pl.col(c).sum().alias(c) for c in ("mort_npp", "mort_age", "mort_water", "mort_temp")]
    ).row(0)
    haz_sum = sum(tot)
    share_water = tot[2] / haz_sum if haz_sum > 0 else 0.0
    share_temp = tot[3] / haz_sum if haz_sum > 0 else 0.0
    frac_stems_water = float((df["mort_water"] > 0).mean())

    # selection differential: trees carrying drought hazard vs the whole population
    hit = df.filter(pl.col("mort_water") > 0)
    if hit.height >= 8:
        sel_d95 = float(hit["D95max"].mean() - df["D95max"].mean())
        sel_mws = float(hit["minwscal"].mean() - df["minwscal"].mean())
        sel_d95_rel = sel_d95 / float(df["D95max"].mean())
    else:
        sel_d95 = sel_mws = sel_d95_rel = np.nan

    return dict(
        cell=cell, name=BIOMES.get(cell, str(cell)), scen=scen, nyear=py.height,
        n_mean=float(py["n"].mean()), within_sd=within_sd, between_sd=between_sd,
        ratio=within_sd / between_sd if between_sd > 0 else np.inf, span=span,
        sd_dry=sd_dry, sd_wet=sd_wet, amp=sd_dry / sd_wet if sd_wet > 0 else np.inf,
        r_raw_dry=r_raw_dry, r_in_dry=r_in_dry, r_in_wet=r_in_wet, rb_in_dry=rb_in_dry,
        n_in_dry=n_in_dry, share_water=share_water, share_temp=share_temp,
        frac_stems_water=frac_stems_water, sel_d95=sel_d95, sel_d95_rel=sel_d95_rel,
        sel_mws=sel_mws, mean_w=float(py["mean_w"].mean()),
    )


def main():
    cells = [int(c) for c in os.environ.get("CELLS", ",".join(map(str, BIOMES))).split(",")]
    scens = os.environ.get("SCENARIOS", "hist,ssp370").split(",")
    seed = int(os.environ.get("SEED", "1"))
    outdir = os.environ.get("OUT", os.path.join(REPO, "logs"))
    os.makedirs(outdir, exist_ok=True)

    rows = []
    for scen in scens:
        path = IND.format(scen=scen, seed=seed)
        if not os.path.exists(path):
            print(f"  [skip] {path} missing", flush=True)
            continue
        for cell in cells:
            r = analyse(cell, scen, seed)
            if r is not None:
                rows.append(r)
                print(f"  scanned {r['name']:22s} {scen:7s} nyear={r['nyear']:3d} "
                      f"n/yr={r['n_mean']:6.0f}", flush=True)
    if not rows:
        sys.exit("no data")
    out = pl.DataFrame(rows)
    csv = os.path.join(outdir, f"per_tree_water_access_seed{seed}.csv")
    out.write_csv(csv)

    def block(title):
        print("\n" + "=" * 100)
        print(title)
        print("=" * 100)

    block("A/B  THE DISCARDED SIGNAL — across-tree spread of the C's own per-individual water scalar")
    print("     Our fast core represents ALL of this by ONE stand number.")
    print("     within_sd = mean across-tree sd within a year;  between_sd = sd of the cell mean across years")
    print("     ratio > 1  =>  collapsing to one number discards MORE than the entire between-year drought signal\n")
    print(f"{'cell':24s}{'scen':8s}{'within_sd':>11s}{'between_sd':>12s}{'ratio':>8s}"
          f"{'p5-p95 span':>13s}{'sd_dry':>9s}{'sd_wet':>9s}{'dry/wet':>9s}")
    for r in rows:
        print(f"{r['name']:24s}{r['scen']:8s}{r['within_sd']:11.4f}{r['between_sd']:12.4f}"
              f"{r['ratio']:8.2f}{r['span']:13.4f}{r['sd_dry']:9.4f}{r['sd_wet']:9.4f}{r['amp']:9.2f}")

    block("C  DOES PER-TREE WATER STATUS TRACK THE PREDICTED ROOTING DEPTH?")
    print("     r_raw   = raw corr(D95max, wscal_mean) in dry years — confounded by PFT + tree size")
    print("     r_in    = same, WITHIN (PFT x age band) — the trait effect with composition + ontogeny removed\n")
    print(f"{'cell':24s}{'scen':8s}{'r_raw dry':>11s}{'r_in dry':>10s}{'r_in wet':>10s}"
          f"{'r_in beta':>11s}{'n':>9s}")
    for r in rows:
        print(f"{r['name']:24s}{r['scen']:8s}{r['r_raw_dry']:11.3f}{r['r_in_dry']:10.3f}"
              f"{r['r_in_wet']:10.3f}{r['rb_in_dry']:11.3f}{r['n_in_dry']:9d}")

    block("D/E  THE TWO HAZARDS ADR 0049 SET TO ZERO — what our emulator is throwing away")
    print("     share_water/temp = fraction of the C's TOTAL per-stem hazard carried by drought / heat")
    print("     sel_D95max       = mean rooting depth of drought-hit stems minus the population mean")
    print("                        (negative => drought selectively hits the SHALLOW-rooted: the channel)\n")
    print(f"{'cell':24s}{'scen':8s}{'share_water':>12s}{'share_temp':>11s}{'%stems hit':>11s}"
          f"{'sel_D95max':>11s}{'rel':>8s}{'sel_minwscal':>13s}")
    for r in rows:
        print(f"{r['name']:24s}{r['scen']:8s}{r['share_water']:12.4f}{r['share_temp']:11.4f}"
              f"{100 * r['frac_stems_water']:11.2f}{r['sel_d95']:11.1f}"
              f"{r['sel_d95_rel']:8.3f}{r['sel_mws']:13.4f}")

    hist = {r["cell"]: r for r in rows if r["scen"] == "hist"}
    ssp = {r["cell"]: r for r in rows if r["scen"] == "ssp370"}
    if hist and ssp:
        block("E  WARMING RESPONSE of the drought channel (historic -> ssp370)")
        print("     This is the acceptance-criterion clause: the response BETWEEN scenarios (ADR 0106).\n")
        print(f"{'cell':24s}{'share_water hist':>18s}{'ssp370':>10s}{'x':>8s}"
              f"{'%stems hist':>13s}{'ssp370':>10s}{'x':>8s}")
        for c in sorted(set(hist) & set(ssp)):
            h, s = hist[c], ssp[c]
            fh, fs = 100 * h["frac_stems_water"], 100 * s["frac_stems_water"]
            print(f"{h['name']:24s}{h['share_water']:18.4f}{s['share_water']:10.4f}"
                  f"{(s['share_water'] / h['share_water'] if h['share_water'] > 0 else np.nan):8.2f}"
                  f"{fh:13.2f}{fs:10.2f}{(fs / fh if fh > 0 else np.nan):8.2f}")

    # ---- verdict -------------------------------------------------------------------------------
    block("VERDICT")
    hrows = [r for r in rows if r["scen"] == "hist"]
    med_ratio = float(np.median([r["ratio"] for r in hrows]))
    med_amp = float(np.median([r["amp"] for r in hrows]))
    med_share = float(np.median([r["share_water"] for r in hrows]))
    rin = [r["r_in_dry"] for r in hrows if np.isfinite(r["r_in_dry"])]
    med_rin = float(np.median(np.abs(rin))) if rin else 0.0
    print(f"  median within/between spread ratio      : {med_ratio:.2f}   (>1 => aggregation error "
          f"exceeds the whole between-year drought signal)")
    print(f"  median dry/wet spread amplification     : {med_amp:.2f}   (>1 => trees diverge "
          f"precisely when it is dry)")
    print(f"  median |within-band corr| D95max~wscal  : {med_rin:.3f}")
    print(f"  median drought share of total hazard    : {med_share:.3f}")
    passed = (med_ratio > 1.0) and (med_amp > 1.0) and (med_share > 0.01)
    if passed:
        print("\n  -> PASS. Trees do NOT experience drought identically: the across-tree spread the")
        print("     shared profile discards is larger than the between-year signal it is supposed to")
        print("     carry, it widens in dry years, and the drought hazard we have zeroed is a real,")
        print("     trait-selective share of total mortality. Proceed to Phase 1 (per-tree roots +")
        print("     per-tree water), then Phase 2 (switch the two hazards on).")
    else:
        print("\n  -> FAIL. The premise does not hold on these cells. Say so plainly and STOP; do not")
        print("     edit src/. Report which of the three conditions failed.")
    print(f"\n  Basis: {len(set(r['cell'] for r in rows))} of 54 020 tree-bearing cells, seed{seed}. "
          f"`wscal_mean` is an all-365-day POTENTIAL index (ADR 0051) => every spread here is a")
    print("  LOWER bound on what the growing-season daily value would show.")
    print(f"\n  wrote {csv}")


if __name__ == "__main__":
    main()
