#!/usr/bin/env python3
"""Audit the C's PER-INDIVIDUAL leaf-turnover basis at the five coupled biome cells.

WHY THIS EXISTS (line M, rung 3; `residual-diagnosis` §1 + ADR 0110's "check whether the C already
EMITS it" rule). The handoff suspected F's uniform `AllocParams.is_deciduous = true` of being a
per-PFT defect at `boreal_siberia`, on the reading that the C gates its summergreen full-leaf
recycle (`turn.leaf = leaf/1.05`) on a PFT phenology TYPE. The live source says otherwise, twice:

  1. `lpjmlfit.js:53` sets `"new_phenology": true`, so `daily_natural.c:123-124` calls
     `phenology_gsi`, and the SUMMERGREEN/RAINGREEN/EVERGREEN switch in `phenology_tree.c` is
     DEAD CODE in this configuration (CLAUDE.md §3's individual-mode dead-path rule).
  2. The live daily path, `turnover_daily_tree.c:42-76`, branches on `config->individual` FIRST
     and is phenology-type-BLIND -- its own source comment says so: "now every PFT can shed
     leaves (due to dryness, heat, cold etc.)". Every tree PFT is in any case declared
     `"phenology": "summergreen"` in `par/pft_lpjmlfit.js` (id 0's `//"raingreen"` is commented
     out), so a per-PFT `is_deciduous` could not have differed even if the key were read.

So the C's gate is a RUNTIME LATCH `tree->isphen`, not a parameter, and it picks between two rates:

    isphen at year end (`turnover_tree.c:100`): turn.leaf = leaf_c / 1.05   (sheds 95.24 %)
    else: turn.leaf = the accumulated daily drip, which `turnover_daily_tree.c:63-65` builds at
      `leaf_c * turnover_leaf / NDAYYEAR` per day with
      **`turnover_leaf = 1.0 / max(pft->longevity, 1.05)`** (`:38`, the individual-mode branch)

THE FINDING THIS SCRIPT MEASURES. That `pft->longevity` is **NOT** the per-PFT `turnover.leaf`
residence time F carries in `AllocParams.turnover_leaf`. In individual mode it is a PER-INDIVIDUAL
TRAIT: `new_tree.c:215` sets `pft->longevity = corr_corridor(pft->sla, longevity.interc,
longevity.slope, longevity.sigma, seed)` -- drawn from the stem's OWN SLA through a noisy
regression corridor (the leaf-economics spectrum), which is why `par/pft_lpjmlfit.js` declares
`longevity` as `{mean, interc, slope, sigma}` and not a scalar. It is emitted per stem as the `ind`
column `Longevity`, so the whole question is a parquet scan and needs no simulation.

WHAT THIS SETTLES AND WHAT IT DOES NOT. It quantifies how far apart the two branches are, per cell
and per PFT, in the units that matter (the fraction of the leaf pool RETAINED into allocation). It
does NOT say which branch fires -- that is the latch's incidence, which needs the daily
leaf-display trajectory and lives in `scripts/leaf_shed_latch_probe.jl`. Read the two together:
this table is the per-cell SIZE of the error whose INCIDENCE the latch probe measures.

Traps handled: grass rows carry zeroed tree fields (`fwriteoutput_ind.c:139-189`) so the filter is
`Type <= 6` AND `D95max > 0` (ADR 0110); the variability audit runs FIRST and prints `const`
rather than a spread for a degenerate column (ADR 0117); `Longevity` is printed against its own
par-file `mean`, so a constant column would be visible immediately.

Run (seconds -- row-group pruning makes a single-cell filter ~0.1 s over the 22 GB table):
    conda run -n py311_new python scripts/diagnose_leaf_turnover_regime.py
"""

from __future__ import annotations

import os
import sys

import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

IND = "/p/tmp/jamirp/emulator_global/ind_hist_seed1_all.parquet"

# The five coupled biome cells (test/testitems/references/M_cells.csv), ordered cold -> hot.
CELLS: tuple[tuple[str, int], ...] = (
    ("boreal_siberia", 52059),
    ("temperate_hainich", 42490),
    ("mediterranean_iberia", 33335),
    ("semiarid_sahel", 18371),
    ("tropical_amazon", 12045),
)

# `par/pft_lpjmlfit.js` `longevity.mean` per tree PFT id -- the value the non-individual branch
# (`new_tree.c:234`) uses, and the centre of the corridor the individual branch draws from.
LONGEVITY_MEAN = {0: 1.6, 1: 2.0, 2: 2.0, 3: 2.0, 4: 2.0, 5: 2.0, 6: 2.0}

# F's shipped `AllocParams.turnover_leaf` basis: the per-PFT `turnover.leaf` RESIDENCE in years,
# from test/testitems/references/M_pft_fdiff_params.csv (ADR 0126). Carried here only to show it
# is a DIFFERENT quantity from `longevity` -- the C ignores it for trees in individual mode.
TURNOVER_LEAF_YR = {0: 2.0, 1: 4.0, 2: 1.0, 3: 1.0, 4: 4.0, 5: 1.0, 6: 1.0}

DECID_DIV = 1.05  # `turnover_tree.c:102` / F's `AllocParams.deciduous_leaf_div`

RULE = "=" * 100


def retained_shed() -> float:
    """Leaf fraction RETAINED into allocation on the latched (full-recycle) branch."""
    return 1.0 - 1.0 / DECID_DIV


def retained_drip(longevity: float) -> float:
    """Leaf fraction retained on the daily-drip branch: 1 - 1/max(longevity, 1.05)."""
    return 1.0 - 1.0 / max(longevity, DECID_DIV)


def load(cell: int) -> pl.DataFrame:
    lf = pl.scan_parquet(IND)
    cols = ("Year", "Patch", "ID", "Type", "SLA", "Longevity", "isdead")
    return (
        lf.filter((pl.col("Cell") == cell) & (pl.col("Type") <= 6) & (pl.col("D95max") > 0))
        .select(*cols)
        .collect()
    )


def panel_variability(frames: dict[str, pl.DataFrame]) -> None:
    """ADR 0117: the variability audit is the FIRST panel, never a footnote."""
    print(RULE)
    print("PANEL 1 -- VARIABILITY AUDIT of the `ind` column `Longevity` (leaf longevity, yr)")
    print("  A degenerate column and a genuinely uncoupled one look identical downstream; this")
    print("  settles which. `par_mean` is the par-file `longevity.mean` the C would use if it")
    print("  were NOT in individual mode.")
    print(RULE)
    print(
        f"{'cell':<22}{'pft':>4}{'stem_yr':>9}{'ndist':>7}{'min':>8}{'max':>8}"
        f"{'median':>8}{'par_mean':>9}  verdict"
    )
    for name, df in frames.items():
        for pft in sorted(df["Type"].unique().to_list()):
            s = df.filter(pl.col("Type") == pft)["Longevity"]
            nd = s.n_unique()
            lo, hi, med = s.min(), s.max(), s.median()
            pm = LONGEVITY_MEAN.get(pft, float("nan"))
            verdict = "const" if nd == 1 else f"sampled ({hi / lo:.2f}x spread)"
            print(
                f"{name:<22}{pft:>4}{s.len():>9}{nd:>7}{lo:>8.3f}{hi:>8.3f}"
                f"{med:>8.3f}{pm:>9.2f}  {verdict}"
            )
    print()


def panel_retention(frames: dict[str, pl.DataFrame]) -> None:
    """The gap between the C's two branches, in the units the allocation actually sees."""
    print(RULE)
    print("PANEL 2 -- LEAF FRACTION RETAINED INTO ALLOCATION: the C's two branches vs F_diff")
    print("  F runs the LATCHED branch unconditionally for every tree every year, so `F_ret` is")
    print("  constant. `drip_ret` is the C's other branch on each stem's OWN sampled Longevity.")
    print("  `excess_shed` = drip_ret - F_ret = the leaf fraction F sheds that the C would KEEP")
    print("  in a year the latch does NOT fire. UPPER BOUND until the incidence is known")
    print("  (scripts/leaf_shed_latch_probe.jl). `F_wrong_par` is what F's turnover_leaf would")
    print("  give if the non-latched branch were ever wired to the per-PFT residence instead.")
    print()
    print("  ** `frac_gt` is the DECISIVE column: the fraction of stems with Longevity > 1.05 yr.")
    print("  The C's own drip rate is 1/max(longevity, 1.05), so it is CAPPED at 0.9524/yr -- the")
    print("  latched branch's exact rate. Wherever longevity <= 1.05 the C's two branches are the")
    print("  SAME NUMBER, F's unconditional recycle is exactly right, and the latch cannot matter")
    print("  however often it fires. `frac_gt = 0` closes the question for that cell x PFT. **")
    print(RULE)
    fret = retained_shed()
    print(
        f"{'cell':<22}{'pft':>4}{'stems':>8}{'frac_gt':>9}{'F_ret':>8}{'drip_ret':>10}"
        f"{'excess_shed':>13}{'turn_yr':>9}{'F_wrong_par':>13}"
    )
    for name, df in frames.items():
        tot = df.height
        cell_excess = 0.0
        for pft in sorted(df["Type"].unique().to_list()):
            s = df.filter(pl.col("Type") == pft)
            dret = float(
                s.select(
                    pl.col("Longevity")
                    .map_elements(retained_drip, return_dtype=pl.Float64)
                    .mean()
                ).item()
            )
            fgt = float(s.select((pl.col("Longevity") > DECID_DIV).mean()).item())
            tl = TURNOVER_LEAF_YR.get(pft, float("nan"))
            cell_excess += (dret - fret) * s.height / tot
            print(
                f"{name:<22}{pft:>4}{s.height:>8}{fgt:>9.3f}{fret:>8.4f}{dret:>10.4f}"
                f"{dret - fret:>13.4f}{tl:>9.1f}{retained_drip(tl):>13.4f}"
            )
        verdict = "CANNOT BIND" if abs(cell_excess) < 5.0e-3 else "CAN BIND"
        print(f"{'  -> ' + name + ' stem-weighted':<44}{cell_excess:>26.4f}  {verdict}")
    print()


def panel_sla_coupling(frames: dict[str, pl.DataFrame]) -> None:
    """`new_tree.c:215` draws Longevity FROM SLA -- confirm the corridor is real, per cell x PFT."""
    print(RULE)
    print("PANEL 3 -- IS `Longevity` REALLY DRAWN FROM THE STEM'S OWN SLA?")
    print("  (new_tree.c:215 corr_corridor). A strong negative SLA~Longevity correlation is the")
    print("  leaf-economics corridor the C samples. Formed WITHIN (cell, PFT) so it cannot be a")
    print("  composition artefact (ADR 0118); `n/d` where a column is degenerate or n < 30.")
    print(RULE)
    print(f"{'cell':<22}{'pft':>4}{'stems':>8}{'r(SLA,Longevity)':>19}")
    for name, df in frames.items():
        for pft in sorted(df["Type"].unique().to_list()):
            s = df.filter(pl.col("Type") == pft)
            degenerate = s["Longevity"].n_unique() == 1 or s["SLA"].n_unique() == 1
            if s.height < 30 or degenerate:
                print(f"{name:<22}{pft:>4}{s.height:>8}{'n/d':>19}")
                continue
            r = float(s.select(pl.corr("SLA", "Longevity")).item())
            print(f"{name:<22}{pft:>4}{s.height:>8}{r:>19.4f}")
    print()


def main() -> int:
    if not os.path.exists(IND):
        print(f"FATAL: {IND} not found", file=sys.stderr)
        return 2
    print(f"repo   {REPO}")
    print(f"source {IND}")
    frames: dict[str, pl.DataFrame] = {}
    for name, cell in CELLS:
        df = load(cell)
        if df.height == 0:
            print(f"FATAL: no tree rows for {name} (cell {cell})", file=sys.stderr)
            return 2
        frames[name] = df
        print(
            f"loaded {name:<22} cell {cell:>6}  {df.height:>8} tree stem-years  "
            f"{df['Year'].min()}-{df['Year'].max()}  {df['Type'].n_unique()} PFTs"
        )
    print()
    panel_variability(frames)
    panel_retention(frames)
    panel_sla_coupling(frames)
    print(RULE)
    print("READ WITH scripts/leaf_shed_latch_probe.jl: this table is the SIZE of the per-cell")
    print("error, that probe is its INCIDENCE. Neither is a result on its own.")
    print(RULE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
