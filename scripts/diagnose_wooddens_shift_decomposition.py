#!/usr/bin/env python3
"""D2 -- decompose LPJmL-FIT's OWN historic->ssp370 wood-density shift into PFT-COMPOSITION turnover,
WITHIN-PFT selection, and the ENTRY-marginal shift. This is the KILL SWITCH for trait-dependent
mortality: it bounds, from the truth alone, how much of the shift that mechanism could ever explain.

WHY (Phase 1 of the wood-density damping plan, 2026-08-04)
----------------------------------------------------------
Component S damps FIT's mean per-cell wood-density warming shift (+2433 internal units) by ~40 %
(deployed ncond-8 arm: `Rb` = -971.5, ADR 0042 section 5). Two mechanisms are proposed, and they need
DIFFERENT fixes:

  * PFT-COMPOSITION turnover -- warming changes which PFTs occupy the cell, and their wood-density
    intervals differ. This is an ENVIRONMENTAL response a PFT-blind conditional CAN encode.
  * WITHIN-PFT selection -- FIT kills light-wood individuals preferentially inside a PFT, via
    `mortality_tree_ind.c:92` `mort_max = 10^(wdmort_1 + wdmort_2/(wooddens/1e6))` feeding
    `mort_npp`. The emulator's mortality is EXACTLY composition-preserving
    (`slow.jl:763-773` scales every cohort's `nind` by one `rho`), so it has NO channel for this.

The exact additive decomposition of the per-cell MEAN shift is

    dWbar = SUM_p (dw_p * Wbar_p^hist)      [composition]
          + SUM_p (w_p^hist * dWbar_p)      [within-PFT]
          + SUM_p (dw_p * dWbar_p)          [interaction, reported EXPLICITLY, never folded in]

with w_p the survivor share of PFT p and Wbar_p its mean wood density.

PRE-REGISTERED DECISION RULE (fixed before the numbers exist):
  within-PFT share  < 15 %  ==> trait-dependent mortality is DEAD; re-scope to composition.
  within-PFT share  > 40 %  ==> it is the right lever.
  15-40 %                   ==> that share is the UPPER BOUND on what the mechanism may claim, and
                                the bound is quoted with every later result.

THREE FREE RIDERS in the same pass, each answering a question the plan needs:
  (1) SELECTION DIFFERENTIAL. The `ind` writer emits DEAD stems too (`isdead` is a column; the copula
      filters `isdead==0` at `build_slow_runtime_table.py:346`), so selection is DIRECTLY measurable,
      no regression needed:  S = mean(Wooddens | isdead==0) - mean(Wooddens | all emitted).
      If S ~ 0 and flat, the trait-blind premise holds in the EMITTED population despite the C source,
      and the lever loses its motivation empirically rather than by argument. If S strengthens from
      the historic to the ssp block, warming acts through selection and the lever is confirmed.
  (2) TRAIT-vs-AGE GRADIENT. Traits are immutable after `new_tree`, so mean Wooddens per Age bin can
      only slope upward if mortality selects on it. This is the ID-free validation target for a
      ported mortality operator, and its youngest bin approximates the ENTRY marginal -- the
      distribution a recruit sampler must reproduce once mortality does the selecting.
  (3) SURVIVOR vs the per-PFT UNIFORM PRIOR. `new_tree.c:195-206` draws the background channel
      uniformly on a per-PFT [low, high] interval. Deviation of the survivor marginal from uniform is
      the joint footprint of selection AND of the inheritance channel
      (`establishmentpft_ind.c:122-135`, weight 4/(4+n_elig)) -- so a deviation does NOT by itself
      prove selection, and this is reported as context, not evidence.

BASIS. Committed seed1 parquets. `Type` in TREE_TYPES (imported, never re-declared -- ADR 0031), and
the survivor statistics use `isdead == 0`, matching the copula's own `stem_filt`. Cells restricted to
those with >= MINSTEM survivor stems in BOTH scenario blocks, so the numbers are comparable to the
response gate's 52 450-cell universe.

GUARDS (ADR 0036 section 5b -- polars streaming `group_by` is non-deterministic in its emitted KEY
SET at this scale: two runs over these parquets gave 99 023 397 vs 99 028 310 rows, with 12
DUPLICATED cell keys). Every aggregate here asserts `n_unique(keys) == height`; a duplicated key
would silently re-weight a mean, and the usual `dropped = before - after` guard CANNOT catch it
because duplication makes that statistic go negative. No self-joins (they AMPLIFY a duplicated key
2 -> 4).

Usage:  NCPUS=96 scripts/sbatch_python.sh S-wdshift scripts/diagnose_wooddens_shift_decomposition.py
Env:    MINSTEM (20), SEED (1), OUT (optional parquet dump dir). Age bins are fixed (AGE_EDGES).
"""

from __future__ import annotations

import os
import sys

import polars as pl

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "python", "src"))
from lpjmlfit_emulator.data import TREE_TYPES  # noqa: E402  -- single source of truth (ADR 0031)

IND = {
    "historic": "/p/tmp/jamirp/emulator_global/ind_hist_seed{seed}_all.parquet",
    "ssp370": "/p/tmp/jamirp/emulator_global/ind_ssp370_seed{seed}_all.parquet",
}
MINSTEM = int(os.environ.get("MINSTEM", "20"))
SEED = int(os.environ.get("SEED", "1"))
OUT = os.environ.get("OUT", "").strip()
AX = "Wooddens"
# Fixed Age bin edges (years). The emitted population is stems > 5 m, so the first bin is already
# post-establishment; its mean is the closest observable proxy for the ENTRY marginal.
AGE_EDGES = [10.0, 20.0, 40.0, 80.0, 160.0, 320.0]


def assert_unique(df: pl.DataFrame, keys: list[str], what: str) -> pl.DataFrame:
    """ADR 0036 section 5b guard. A duplicated key silently re-weights every mean downstream."""
    nu = df.select(keys).n_unique()
    if nu != df.height:
        raise SystemExit(
            f"FATAL: {what} emitted {df.height} rows for {nu} unique {keys} "
            f"({df.height - nu} duplicated) -- polars streaming key-set nondeterminism "
            f"(ADR 0036 section 5b). Re-run; do NOT interpret this output."
        )
    return df


def census(scenario: str) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Per-(Cell, Type) survivor census, per-(Cell) survivor summary, and the selection differential."""
    path = IND[scenario].format(seed=SEED)
    print(f"\n== {scenario}: scanning {path}", flush=True)
    tree = pl.col("Type").is_in(TREE_TYPES)
    lf = pl.scan_parquet(path).filter(tree)

    # (a) survivor census per (Cell, Type): the composition/within-PFT decomposition inputs.
    surv = (
        lf.filter(pl.col("isdead") == 0)
        .group_by(["Cell", "Type"])
        .agg(
            pl.len().alias("n"),
            pl.col(AX).mean().alias("wmean"),
            pl.col(AX).median().alias("wmed"),
            pl.col(AX).std().alias("wsd"),
            pl.col("Age").mean().alias("agemean"),
        )
        .collect(engine="streaming")
    )
    assert_unique(surv, ["Cell", "Type"], f"{scenario} survivor census")
    print(f"   survivor (Cell,Type) rows = {surv.height:,}   cells = {surv['Cell'].n_unique():,}"
          f"   stems = {surv['n'].sum():,}", flush=True)

    # (b) per-cell survivor summary -- the basis the +2433 is quoted on (per-cell MEDIANS).
    cellsum = (
        lf.filter(pl.col("isdead") == 0)
        .group_by("Cell")
        .agg(
            pl.len().alias("n"),
            pl.col(AX).mean().alias("wmean"),
            pl.col(AX).median().alias("wmed"),
        )
        .collect(engine="streaming")
    )
    assert_unique(cellsum, ["Cell"], f"{scenario} per-cell survivor summary")

    # (c) selection differential per (Cell, Type): survivors vs ALL emitted stems, same rows.
    #     `mean_all` includes isdead==1, so S > 0 means the dead are lighter-wooded than average.
    sel = (
        lf.group_by(["Cell", "Type"])
        .agg(
            pl.len().alias("n_all"),
            pl.col(AX).mean().alias("w_all"),
            (pl.col("isdead") == 1).sum().alias("n_dead"),
            pl.col(AX).filter(pl.col("isdead") == 1).mean().alias("w_dead"),
            pl.col(AX).filter(pl.col("isdead") == 0).mean().alias("w_live"),
            pl.col("mort").mean().alias("mort_mean"),
            pl.col("mort_npp").mean().alias("mort_npp_mean"),
            pl.col("mort_water").mean().alias("mort_water_mean"),
            pl.col("mort_temp").mean().alias("mort_temp_mean"),
            pl.col("mort_age").mean().alias("mort_age_mean"),
        )
        .collect(engine="streaming")
    )
    assert_unique(sel, ["Cell", "Type"], f"{scenario} selection differential")
    return surv, cellsum, sel


def age_gradient(scenario: str) -> pl.DataFrame:
    """Free rider (2): mean survivor Wooddens by Age decile, per PFT. Traits are immutable after
    establishment, so an upward slope can ONLY come from selection."""
    path = IND[scenario].format(seed=SEED)
    return assert_unique(
        (
            pl.scan_parquet(path)
            .filter(pl.col("Type").is_in(TREE_TYPES) & (pl.col("isdead") == 0))
            # FIXED Age bins, not quantile bins: a global `rank().over("Type")` over ~1e9 rows will
            # not stream (it materialises a full ordering per PFT). Fixed edges also make the two
            # scenario blocks directly comparable bin-by-bin, which quantile bins would not be.
            # Built as a sum of threshold indicators so the bin id is a sortable INTEGER.
            .with_columns(
                sum((pl.col("Age") >= e).cast(pl.Int32) for e in AGE_EDGES).alias("agebin")
            )
            .group_by(["Type", "agebin"])
            .agg(
                pl.len().alias("n"),
                pl.col("Age").mean().alias("age"),
                pl.col(AX).mean().alias("wmean"),
                pl.col(AX).median().alias("wmed"),
            )
            .collect(engine="streaming")
        ),
        ["Type", "agebin"],
        f"{scenario} age gradient",
    )


def main() -> int:
    print("=" * 104)
    print("D2 -- three-way decomposition of FIT's OWN wood-density warming shift")
    print(f"     TREE_TYPES={TREE_TYPES}  MINSTEM={MINSTEM}  SEED={SEED}  axis={AX}")
    print("=" * 104)

    surv_h, cell_h, sel_h = census("historic")
    surv_s, cell_s, sel_s = census("ssp370")

    # ---- common universe: >= MINSTEM survivor stems in BOTH blocks
    keep = (
        cell_h.filter(pl.col("n") >= MINSTEM).select("Cell")
        .join(cell_s.filter(pl.col("n") >= MINSTEM).select("Cell"), on="Cell", how="inner")
    )
    print(f"\n== common universe: {keep.height:,} cells with >= {MINSTEM} survivor stems in BOTH blocks")

    ch = cell_h.join(keep, on="Cell", how="inner").sort("Cell")
    cs = cell_s.join(keep, on="Cell", how="inner").sort("Cell")
    j = ch.join(cs, on="Cell", how="inner", suffix="_s")
    d_mean = (j["wmean_s"] - j["wmean"]).mean()
    d_med = (j["wmed_s"] - j["wmed"]).mean()
    print(f"   mean over cells of the per-cell MEAN   shift = {d_mean:+.1f}")
    print(f"   mean over cells of the per-cell MEDIAN shift = {d_med:+.1f}   "
          f"<-- the basis ADR 0042 section 5's +2432.9 is on")
    print("   (the decomposition below is exact for MEANS only; a median does not decompose additively,")
    print("    so both are reported and the share is quoted on the MEAN basis)")

    # ---- the exact additive decomposition, per cell then averaged over cells
    sh = surv_h.join(keep, on="Cell", how="inner")
    ss = surv_s.join(keep, on="Cell", how="inner")
    tot_h = sh.group_by("Cell").agg(pl.col("n").sum().alias("N"))
    tot_s = ss.group_by("Cell").agg(pl.col("n").sum().alias("N"))
    sh = sh.join(tot_h, on="Cell").with_columns((pl.col("n") / pl.col("N")).alias("w"))
    ss = ss.join(tot_s, on="Cell").with_columns((pl.col("n") / pl.col("N")).alias("w"))

    # OUTER join on (Cell, Type): a PFT present in only one block is a pure composition event and
    # must contribute, with a zero share on the missing side -- an inner join would DELETE exactly
    # the extinction/colonisation signal the composition term is meant to capture.
    m = sh.select(["Cell", "Type", "w", "wmean"]).join(
        ss.select(["Cell", "Type", "w", "wmean"]),
        on=["Cell", "Type"], how="full", suffix="_s", coalesce=True,
    )
    m = m.with_columns(
        pl.col("w").fill_null(0.0),
        pl.col("w_s").fill_null(0.0),
        # A PFT absent in a block has no mean; use the OTHER block's mean so `dW_p` is 0 for it and
        # the whole effect lands in the composition term where it belongs.
        pl.coalesce(["wmean", "wmean_s"]).alias("wmean_f"),
        pl.coalesce(["wmean_s", "wmean"]).alias("wmean_s_f"),
    ).with_columns(
        (pl.col("w_s") - pl.col("w")).alias("dw"),
        (pl.col("wmean_s_f") - pl.col("wmean_f")).alias("dW"),
    )
    terms = m.group_by("Cell").agg(
        (pl.col("dw") * pl.col("wmean_f")).sum().alias("comp"),
        (pl.col("w") * pl.col("dW")).sum().alias("within"),
        (pl.col("dw") * pl.col("dW")).sum().alias("inter"),
    )
    assert_unique(terms, ["Cell"], "decomposition terms")
    tc, tw, ti = terms["comp"].mean(), terms["within"].mean(), terms["inter"].mean()
    tot = tc + tw + ti
    print("\n" + "=" * 104)
    print("DECOMPOSITION of the per-cell MEAN shift (averaged over the common universe)")
    print("=" * 104)
    print(f"   composition  SUM dw_p * Wbar_p^hist  = {tc:+10.1f}   {100 * tc / tot:+7.1f} %")
    print(f"   within-PFT   SUM w_p^hist * dWbar_p  = {tw:+10.1f}   {100 * tw / tot:+7.1f} %")
    print(f"   interaction  SUM dw_p * dWbar_p      = {ti:+10.1f}   {100 * ti / tot:+7.1f} %")
    print(f"   SUM                                  = {tot:+10.1f}")
    print(f"   closure check vs direct mean shift    = {d_mean:+10.1f}   "
          f"(residual {tot - d_mean:+.3g}; must be ~0 or the decomposition is wrong)")
    share = 100 * tw / tot if tot != 0 else float("nan")
    print("\n   PRE-REGISTERED VERDICT")
    if share < 15:
        v = ("within-PFT share < 15 %  ==>  TRAIT-DEPENDENT MORTALITY IS DEAD. "
             "Re-scope to PFT composition.")
    elif share > 40:
        v = ("within-PFT share > 40 %  ==>  trait-dependent mortality IS the right lever.")
    else:
        v = (f"within-PFT share in 15-40 %  ==>  the lever is BOUNDED ABOVE by {share:.1f} % of the "
             f"shift. Quote that bound with every later result.")
    print(f"   within-PFT share = {share:.1f} %  ==>  {v}")

    # ---- free rider (1): selection differential, per block, per PFT
    print("\n" + "=" * 104)
    print("SELECTION DIFFERENTIAL  S = mean(Wooddens | live) - mean(Wooddens | all emitted)")
    print("=" * 104)
    print(f"   {'Type':>5s} {'blk':>4s} {'n_all':>14s} {'dead_frac':>10s} {'w_live':>10s} "
          f"{'w_dead':>10s} {'S':>9s} {'mort':>8s} {'m_npp':>8s} {'m_wat':>8s} {'m_tmp':>8s}")
    sel_rows = {}
    for tag, sel in (("hist", sel_h), ("ssp", sel_s)):
        s = sel.join(keep, on="Cell", how="inner")
        g = s.group_by("Type").agg(
            pl.col("n_all").sum().alias("n_all"),
            (pl.col("n_dead").sum() / pl.col("n_all").sum()).alias("dead_frac"),
            # stem-weighted means: a plain mean of per-cell means would weight a 20-stem cell like a
            # 20 000-stem one, which is not the population statistic being claimed.
            ((pl.col("w_live") * (pl.col("n_all") - pl.col("n_dead"))).sum()
             / (pl.col("n_all") - pl.col("n_dead")).sum()).alias("w_live"),
            ((pl.col("w_dead").fill_null(0.0) * pl.col("n_dead")).sum()
             / pl.col("n_dead").sum()).alias("w_dead"),
            ((pl.col("w_all") * pl.col("n_all")).sum() / pl.col("n_all").sum()).alias("w_all"),
            ((pl.col("mort_mean") * pl.col("n_all")).sum() / pl.col("n_all").sum()).alias("mort"),
            ((pl.col("mort_npp_mean") * pl.col("n_all")).sum() / pl.col("n_all").sum()).alias("m_npp"),
            ((pl.col("mort_water_mean") * pl.col("n_all")).sum() / pl.col("n_all").sum()).alias("m_wat"),
            ((pl.col("mort_temp_mean") * pl.col("n_all")).sum() / pl.col("n_all").sum()).alias("m_tmp"),
        ).sort("Type")
        for r in g.iter_rows(named=True):
            S = r["w_live"] - r["w_all"]
            sel_rows[(r["Type"], tag)] = S
            print(f"   {r['Type']:>5d} {tag:>4s} {r['n_all']:>14,d} {r['dead_frac']:>10.4f} "
                  f"{r['w_live']:>10.1f} {r['w_dead']:>10.1f} {S:>+9.2f} {r['mort']:>8.4f} "
                  f"{r['m_npp']:>8.4f} {r['m_wat']:>8.4f} {r['m_tmp']:>8.4f}")
    print(f"\n   {'Type':>5s} {'S_hist':>10s} {'S_ssp':>10s} {'dS':>10s}   "
          f"<-- dS > 0 means warming STRENGTHENS wood-density selection")
    for t in sorted({k[0] for k in sel_rows}):
        a, b = sel_rows.get((t, "hist")), sel_rows.get((t, "ssp"))
        if a is not None and b is not None:
            print(f"   {t:>5d} {a:>+10.2f} {b:>+10.2f} {b - a:>+10.2f}")
    print("\n   S ~ 0 and flat  ==> the trait-blind premise holds in the EMITTED population and the")
    print("   lever loses its motivation empirically. S != 0 and strengthening ==> lever confirmed.")
    print("   NOTE `mort_*` are C outputs and can NEVER be emulator features -- diagnosis only.")

    # ---- free rider (2): trait-vs-age gradient
    print("\n" + "=" * 104)
    print("TRAIT-vs-AGE GRADIENT (survivors). Traits are immutable after establishment, so an upward")
    print("slope can ONLY come from selection. The youngest bin approximates the ENTRY marginal.")
    print("=" * 104)
    nbin = len(AGE_EDGES) + 1
    labels = ["<10"] + [f">={int(e)}" for e in AGE_EDGES]
    ag_by_tag = {}
    for tag, sc in (("hist", "historic"), ("ssp", "ssp370")):
        ag = age_gradient(sc)
        ag_by_tag[tag] = ag
        print(f"\n-- {tag}   (mean Wooddens by Age bin; bins {labels})")
        print(f"   {'Type':>5s} " + " ".join(f"{lb:>9s}" for lb in labels)
              + f" {'d(last-1st)':>12s} {'slope/yr':>10s}")
        for t in sorted(ag["Type"].unique().to_list()):
            r = ag.filter(pl.col("Type") == t).sort("agebin")
            have = dict(zip(r["agebin"].to_list(), zip(r["wmean"].to_list(), r["age"].to_list())))
            cells_txt, first, last = [], None, None
            for b in range(nbin):
                if b in have:
                    w, agev = have[b]
                    cells_txt.append(f"{w:9.0f}")
                    if first is None:
                        first = (w, agev)
                    last = (w, agev)
                else:
                    cells_txt.append(f"{'-':>9s}")
            if first is not None and last is not None and last[1] != first[1]:
                dw = last[0] - first[0]
                slope = dw / (last[1] - first[1])
            else:
                dw, slope = float("nan"), float("nan")
            print(f"   {t:>5d} " + " ".join(cells_txt) + f" {dw:>+12.0f} {slope:>10.3f}")
        print("   An upward gradient is the fingerprint of wood-density selection and is the")
        print("   ID-free validation target for a ported mortality operator.")

    # ---- WITHIN-PFT decomposition over AGE CLASSES.
    # The gradient above is steep (~+140k over a lifespan), so the within-PFT mean can move with ZERO
    # change in selection or in the entry marginal, purely because the AGE DISTRIBUTION slid along it.
    # That is a third mechanism, and it is exactly separable:
    #     dWbar_p = SUM_a da_a * W_a^hist   [age-structure shift along the existing gradient]
    #             + SUM_a a_a^hist * dW_a   [trait shift WITHIN an age class = selection/entry change]
    #             + SUM_a da_a * dW_a       [interaction]
    # Both terms require trait-dependent mortality to exist in the emulator: term 1 needs the GRADIENT
    # (which only cumulative differential survival can create), term 2 needs the selection intensity to
    # respond. But they imply different validation targets, so they are reported separately.
    print("\n" + "=" * 104)
    print("WITHIN-PFT shift decomposed over AGE CLASSES (stem-weighted, global)")
    print("=" * 104)
    h, s = ag_by_tag["hist"], ag_by_tag["ssp"]
    print(f"   {'Type':>5s} {'dWbar_p':>10s} {'age-struct':>11s} {'%':>7s} {'within-age':>11s} {'%':>7s} "
          f"{'interact':>10s} {'%':>7s} {'meanAge_h':>10s} {'meanAge_s':>10s}")
    tot_as = tot_wa = tot_ia = 0.0
    for t in sorted(set(h["Type"].to_list()) & set(s["Type"].to_list())):
        rh = h.filter(pl.col("Type") == t).sort("agebin")
        rs = s.filter(pl.col("Type") == t).sort("agebin")
        bh = {b: (n, w) for b, n, w in zip(rh["agebin"], rh["n"], rh["wmean"])}
        bs = {b: (n, w) for b, n, w in zip(rs["agebin"], rs["n"], rs["wmean"])}
        allb = sorted(set(bh) | set(bs))
        Nh = sum(bh.get(b, (0, 0.0))[0] for b in allb)
        Ns = sum(bs.get(b, (0, 0.0))[0] for b in allb)
        if Nh == 0 or Ns == 0:
            continue
        as_t = wa_t = ia_t = 0.0
        for b in allb:
            nh, wh = bh.get(b, (0, None))
            ns, ws = bs.get(b, (0, None))
            # An age class empty in one block is a pure age-structure event: give it the other block's
            # trait mean so dW_a is 0 and the whole effect lands in the age-structure term.
            wh_f = wh if wh is not None else ws
            ws_f = ws if ws is not None else wh
            da = ns / Ns - nh / Nh
            dW = ws_f - wh_f
            as_t += da * wh_f
            wa_t += (nh / Nh) * dW
            ia_t += da * dW
        d_tot = as_t + wa_t + ia_t
        mah = sum(bh.get(b, (0, 0))[0] * (rh.filter(pl.col("agebin") == b)["age"][0] if b in bh else 0)
                  for b in allb) / Nh
        mas = sum(bs.get(b, (0, 0))[0] * (rs.filter(pl.col("agebin") == b)["age"][0] if b in bs else 0)
                  for b in allb) / Ns
        tot_as += as_t
        tot_wa += wa_t
        tot_ia += ia_t
        p = (lambda x: 100 * x / d_tot if d_tot != 0 else float("nan"))
        print(f"   {t:>5d} {d_tot:>+10.1f} {as_t:>+11.1f} {p(as_t):>+7.1f} {wa_t:>+11.1f} "
              f"{p(wa_t):>+7.1f} {ia_t:>+10.1f} {p(ia_t):>+7.1f} {mah:>10.1f} {mas:>10.1f}")
    gt = tot_as + tot_wa + tot_ia
    print(f"   {'ALL':>5s} {gt:>+10.1f} {tot_as:>+11.1f} {100 * tot_as / gt:>+7.1f} "
          f"{tot_wa:>+11.1f} {100 * tot_wa / gt:>+7.1f} {tot_ia:>+10.1f} {100 * tot_ia / gt:>+7.1f}")
    print("\n   age-struct dominant ==> the warming signal rides the EXISTING age-trait gradient; the")
    print("   emulator needs that gradient to exist at all (it has none: uniform thinning + copula")
    print("   recruits give zero age-trait covariance), and its `age_mean` feature then carries the")
    print("   response. within-age dominant ==> the SELECTION INTENSITY itself responds to warming.")
    print("   Either way the required mechanism is trait-dependent mortality; the targets differ.")
    print("   CAVEAT: this is stem-weighted and GLOBAL, so it is not commensurable with the per-cell")
    print("   +1951.7 within-PFT term above; read the SHARES, not the absolute values.")

    if OUT:
        os.makedirs(OUT, exist_ok=True)
        terms.write_parquet(os.path.join(OUT, "wd_shift_terms.parquet"))
        surv_h.write_parquet(os.path.join(OUT, "surv_hist.parquet"))
        surv_s.write_parquet(os.path.join(OUT, "surv_ssp.parquet"))
        sel_h.write_parquet(os.path.join(OUT, "sel_hist.parquet"))
        sel_s.write_parquet(os.path.join(OUT, "sel_ssp.parquet"))
        print(f"\n== wrote per-cell terms + censuses to {OUT}")

    print("\n" + "=" * 104)
    print("DONE")
    print("=" * 104)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
