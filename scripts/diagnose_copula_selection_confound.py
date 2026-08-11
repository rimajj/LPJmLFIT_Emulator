#!/usr/bin/env python3
"""Size the SELECTION already absorbed into the recruit copula's training target.

WHY THIS EXISTS — a pre-registered condition that was never checked. ADR 0025 §3 trains the recruit
copula's trait marginals on FIT's **surviving stems** (``isdead == 0``, all ages), and justifies that
choice with an explicit premise plus an explicit expiry condition, quoted verbatim:

    "Because mortality is trait-blind, the emulated community distribution equals the establishment
     distribution -- so drawing recruits from FIT's *surviving* marginal makes the community converge
     to FIT's survivor distribution by construction. (Trait-dependent mortality is a much larger,
     separate change; if ever added, this training target must change.)"

Arm C **is** that change: ADR 0117 answers line M's rung-2 interface with a per-individual survival
factor, and the operator that computes it (``trait_mortality``, ADR 0047->0049) exists precisely to make
mortality trait-DEPENDENT. No ADR in that chain (0047, 0049, 0117) cites ADR 0025, so the expiry
condition has never been evaluated. This script evaluates it.

THE CONFOUND, in one sentence. If recruits are drawn from the marginal of FIT's *survivors* -- a
distribution that already carries FIT's cumulative selection -- and a trait-selective survival rule is
then applied on top, the community receives that selection TWICE. Arm C's headline ``C1 - C0`` would
then not measure "how much of the trait response is selection"; it would measure selection applied to
an already-selected marginal, minus none. Note the asymmetry: **C0 is unaffected** (uniform thinning is
exactly the trait-blind design the survivor marginal was matched to), so the confound lands entirely on
the arm, not on its null.

FALSIFIABLE HYPOTHESIS (stated before the measurement -- residual-diagnosis skill; the alternative is a
result that can be reinterpreted after the fact):

    H0  the entry->survivor displacement is small next to the warming response the arm must resolve,
        so the double count is a rounding error and arm C may run on the shipped `_t8` copula as-is.
    H1  the displacement is comparable to or larger than that response, so arm C on the shipped copula
        is mis-specified and any C1 - C0 verdict inherits the bias.

    Decided on TWO numbers per axis, because a LEVEL bias and a RESPONSE bias are different failures
    (ADR 0115 §3: what killed the count recursion was that its error was climate-DEPENDENT, not that it
    was large):
      * ``d``          = displacement  mean(all survivors) - mean(youngest bin), per scenario;
      * ``dD``         = d(ssp370) - d(historic), the part of the displacement that does NOT cancel in a
                         response, against ``R`` = FIT's own survivor-marginal response for that axis.
    H1 holds on the LEVEL if |d| exceeds |R|; it holds on the RESPONSE -- the decision-bearing one -- if
    |dD| is an order-1 fraction of |R|.

BASIS (stated because a mis-stated basis is this line's most expensive recurring error, guardrail 6/7).
Committed ``ind`` parquets; ``Type`` in the imported ``TREE_TYPES`` (never re-declared -- ADR 0031);
survivors only (``isdead == 0``); no stem-count filter on the pooled panel. **That is byte-for-byte the
population ``build_slow_runtime_table.py::copula_table`` fits the marginals on** (its ``stem_filt`` is
the same two predicates), which is what makes the pooled column the copula's actual training target
rather than a neighbouring statistic. Three basis facts that are properties of the DATA, not choices:

  * the ``ind`` writer emits only stems ``height > 5 m`` (``fwriteoutput_ind.c:84``), so even the
    youngest bin is ALREADY post-establishment. Every displacement here is therefore a **LOWER BOUND**
    on the entry->survivor selection: whatever is filtered out below 5 m is invisible. Say "lower
    bound" wherever these numbers are quoted;
  * ``Age`` is the POST-increment year-end age (CLAUDE.md §3); bins are in emitted-``Age`` units,
    identical edges to ``build_age_wooddens_gradient_reference.py`` so the two tables are comparable
    bin-by-bin;
  * the TXT writer's ``%g`` gives 6 significant digits -- nothing below ~1e-5 relative is meaningful.

TWO AGGREGATIONS, both reported, because they answer different questions and can disagree. ``pooled``
pools every stem globally (the copula's fit is over pooled stems, so this is the training target's own
basis). ``percell`` computes the displacement WITHIN each (Cell, Type) and then averages it stem-weighted
-- which controls the composition confound, i.e. the possibility that young and old stems simply live in
different cells. A large pooled displacement with a null per-cell one would mean composition, not
selection.

SEED CONTROL. Every panel is emitted for both ground-truth members. FIT is stochastic and its two runs
disagree materially (ADR 0111), so a displacement is only real if it survives the seed swap; the summary
prints the seed spread beside each number rather than leaving the reader to assume it is zero.

Usage:
    NCPUS=96 TIME=03:00:00 scripts/sbatch_python.sh S-confound \\
        scripts/diagnose_copula_selection_confound.py
Env: SEEDS ("1,2"), SCENARIOS ("historic,ssp370"), MIN_STEMS (30, per-cell panel floor),
     OUT (CSV of the full per-(scenario,seed,pft,agebin) table).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import polars as pl

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "python" / "src"))
from lpjmlfit_emulator.data import TREE_TYPES  # noqa: E402  -- single source of truth (ADR 0031)

IND = {
    "historic": "/p/tmp/jamirp/emulator_global/ind_hist_seed{seed}_all.parquet",
    "ssp370": "/p/tmp/jamirp/emulator_global/ind_ssp370_seed{seed}_all.parquet",
}
SEEDS = [int(s) for s in os.environ.get("SEEDS", "1,2").split(",") if s.strip()]
SCENARIOS = [s.strip() for s in os.environ.get("SCENARIOS", "historic,ssp370").split(",") if s.strip()]
MIN_STEMS = int(os.environ.get("MIN_STEMS", "30"))
OUT = Path(os.environ.get("OUT", "/p/tmp/jamirp/emulator_global/copula_selection_confound.csv"))

#: The four LIVE copula axes (ADR 0025 §2). `beta_2` is compile-time dead and `k_root` is a scalar
#: 0.02 in this configuration (ADR 0117 §6), so these four are the whole recruit interface.
AXES = ["SLA", "Wooddens", "D95max", "minwscal"]

#: Identical to build_age_wooddens_gradient_reference.py::AGE_EDGES, so the two tables line up bin-by-bin.
AGE_EDGES = [10.0, 20.0, 40.0, 80.0, 160.0, 320.0]


def assert_unique(df: pl.DataFrame, keys: list[str], what: str) -> pl.DataFrame:
    """ADR 0036 §5b guard: ``collect(engine="streaming")`` is not deterministic in the KEY SET it emits
    at global scale -- whole groups appeared AND duplicated between two runs of the same aggregation.
    The usual ``rows_before - rows_after`` coverage check cannot see it, because duplication drives that
    statistic negative so a ``drop_frac`` threshold never fires. A duplicated key here would silently
    re-weight a mean."""
    nu = df.select(keys).n_unique()
    if nu != df.height:
        raise SystemExit(
            f"FATAL: {what} emitted {df.height} rows for {nu} unique {keys} "
            f"({df.height - nu} duplicated) -- polars streaming key-set nondeterminism "
            f"(ADR 0036 §5b). Re-run; do NOT interpret this output."
        )
    return df


def scan(scenario: str, seed: int) -> pl.DataFrame:
    """One (Cell, Type, agebin) row per group, carrying stem count + the four axis means.

    Projection is restricted to the eight columns actually needed so the scan reads a fraction of the
    92 GB file; the filter is the copula table builder's ``stem_filt``, verbatim.
    """
    path = IND[scenario].format(seed=seed)
    print(f"\n== scan {scenario} seed{seed}: {path}", flush=True)
    df = (
        pl.scan_parquet(path)
        .select(["Cell", "Type", "Age", "isdead", *AXES])
        .filter(pl.col("Type").is_in(TREE_TYPES) & (pl.col("isdead") == 0))
        # bin id as a SUM OF THRESHOLD INDICATORS -> a sortable integer with no join
        .with_columns(sum((pl.col("Age") >= e).cast(pl.Int32) for e in AGE_EDGES).alias("agebin"))
        .group_by(["Cell", "Type", "agebin"])
        .agg(
            pl.len().alias("n"),
            pl.col("Age").mean().alias("age_mean"),
            *[pl.col(a).cast(pl.Float64).mean().alias(f"{a}_mean") for a in AXES],
        )
        .collect(engine="streaming")
    )
    assert_unique(df, ["Cell", "Type", "agebin"], f"{scenario} seed{seed}")
    print(f"   {df.height} (Cell,Type,agebin) groups, {df['Cell'].n_unique()} cells, "
          f"{int(df['n'].sum())} stems", flush=True)
    return df


def _wmean(df: pl.DataFrame, col: str) -> float:
    """Stem-weighted mean of a per-group mean -- i.e. the mean over the underlying stems."""
    n = df["n"].cast(pl.Float64)
    return float((df[col].cast(pl.Float64) * n).sum() / n.sum())


def pooled_panel(df: pl.DataFrame) -> dict:
    """GLOBAL POOLED displacement: every stem pooled, exactly the copula's fit basis."""
    young = df.filter(pl.col("agebin") == 0)
    out = {"n_all": int(df["n"].sum()), "n_young": int(young["n"].sum())}
    for a in AXES:
        m_all = _wmean(df, f"{a}_mean")
        m_yng = _wmean(young, f"{a}_mean")
        out[f"{a}_all"] = m_all
        out[f"{a}_young"] = m_yng
        out[f"{a}_d"] = m_all - m_yng
        out[f"{a}_drel"] = (m_all - m_yng) / m_all if m_all else float("nan")
    return out


def percell_panel(df: pl.DataFrame) -> dict:
    """WITHIN-(Cell,Type) displacement, then averaged across groups weighted by YOUNG-stem count.

    Controls the composition confound: if young and old stems merely live in different cells, the
    pooled displacement is large and this one is not.

    ⚠ The ``n_young >= MIN_STEMS`` floor makes this a BIASED SUBSAMPLE of cells (those rich in young
    stems), so its ``mean(all)`` -- and hence its own warming response ``R`` -- is a different number
    from the pooled panel's, and can even carry a different SIGN. Ratios are therefore formed against
    THIS panel's own ``R``, never against the pooled one; keeping exactly one ratio definition per
    panel is the ADR 0111 §5b rule.
    """
    n_all = df.group_by(["Cell", "Type"]).agg(
        pl.col("n").sum().alias("n_tot"),
        *[((pl.col(f"{a}_mean") * pl.col("n")).sum() / pl.col("n").sum()).alias(f"{a}_all")
          for a in AXES],
    )
    yng = (df.filter(pl.col("agebin") == 0)
             .select(["Cell", "Type", "n", *[f"{a}_mean" for a in AXES]])
             .rename({"n": "n_yng", **{f"{a}_mean": f"{a}_yng" for a in AXES}}))
    j = n_all.join(yng, on=["Cell", "Type"], how="inner").filter(pl.col("n_yng") >= MIN_STEMS)
    out = {"n_groups": j.height, "n_cells": j["Cell"].n_unique() if j.height else 0}
    if not j.height:
        return out | {f"{a}_d": float("nan") for a in AXES}
    w = j["n_yng"].cast(pl.Float64)
    for a in AXES:
        d = (j[f"{a}_all"] - j[f"{a}_yng"]).cast(pl.Float64)
        out[f"{a}_d"] = float((d * w).sum() / w.sum())
        out[f"{a}_all"] = float((j[f"{a}_all"].cast(pl.Float64) * w).sum() / w.sum())
        out[f"{a}_young"] = float((j[f"{a}_yng"].cast(pl.Float64) * w).sum() / w.sum())
        out[f"{a}_drel"] = out[f"{a}_d"] / out[f"{a}_all"] if out[f"{a}_all"] else float("nan")
    return out


def fmt(x: float) -> str:
    return f"{x:12.5g}"


def main() -> None:
    print("=" * 100)
    print("SELECTION ABSORBED INTO THE RECRUIT COPULA'S TRAINING TARGET (ADR 0025 §3's expiry condition)")
    print(f"axes={AXES}  seeds={SEEDS}  scenarios={SCENARIOS}  MIN_STEMS={MIN_STEMS}")
    print("=" * 100)

    raw: list[pl.DataFrame] = []
    pooled: dict[tuple[str, int], dict] = {}
    percell: dict[tuple[str, int], dict] = {}
    for sc in SCENARIOS:
        for sd in SEEDS:
            df = scan(sc, sd)
            raw.append(df.with_columns(pl.lit(sc).alias("scenario"), pl.lit(sd).alias("seed")))
            pooled[(sc, sd)] = pooled_panel(df)
            percell[(sc, sd)] = percell_panel(df)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    full = pl.concat(raw, how="vertical")
    # collapse to (scenario, seed, Type, agebin) for a committable-size artifact; the per-cell panel is
    # already reduced above, and the per-(Cell,Type,agebin) table is ~2.6M rows of little further use.
    (full.group_by(["scenario", "seed", "Type", "agebin"])
         .agg(pl.col("n").sum().alias("n"),
              *[((pl.col(f"{a}_mean") * pl.col("n")).sum() / pl.col("n").sum()).alias(f"{a}_mean")
                for a in [*AXES]],
              ((pl.col("age_mean") * pl.col("n")).sum() / pl.col("n").sum()).alias("age_mean"))
         .sort(["scenario", "seed", "Type", "agebin"])
         .write_csv(OUT))
    print(f"\n== wrote {OUT}")

    for label, panel in (("POOLED (the copula's own fit basis)", pooled),
                         (f"PER-(Cell,Type), n_young>={MIN_STEMS} (composition-controlled)", percell)):
        print("\n" + "=" * 100)
        print(f"PANEL: {label}")
        print("=" * 100)
        for sc in SCENARIOS:
            for sd in SEEDS:
                p = panel[(sc, sd)]
                cov = (f"n_groups={p.get('n_groups')} cells={p.get('n_cells')}"
                       if "n_groups" in p else f"stems={p.get('n_all')} young={p.get('n_young')}")
                print(f"\n-- {sc} seed{sd}  ({cov})")
                print(f"   {'axis':<10}{'mean(all)':>14}{'mean(young)':>14}"
                      f"{'d = all-young':>16}{'d / mean(all)':>16}")
                for a in AXES:
                    if f"{a}_d" not in p:
                        continue
                    print(f"   {a:<10}{fmt(p.get(f'{a}_all', float('nan')))}"
                          f"{fmt(p.get(f'{a}_young', float('nan')))}"
                          f"{fmt(p[f'{a}_d']):>16}{p.get(f'{a}_drel', float('nan')):>15.2%}")

        # ---- the decision panel: displacement vs FIT's own response, and the part that does not cancel
        if len(SCENARIOS) == 2 and "historic" in SCENARIOS and "ssp370" in SCENARIOS:
            print(f"\n-- DECISION PANEL [{label}] -- displacement against FIT's own warming response")
            print("   R  = mean(all|ssp370) - mean(all|historic)   FIT's survivor-marginal response,")
            print("                                                i.e. what the copula is trained to carry")
            print("   d  = displacement (entry->survivor selection already in the training target)")
            print("   dD = d(ssp370) - d(historic)                 the part that does NOT cancel in R")
            for sd in SEEDS:
                h, s = panel[("historic", sd)], panel[("ssp370", sd)]
                print(f"\n   seed{sd}")
                print(f"   {'axis':<10}{'R':>14}{'d(hist)':>14}{'d(ssp)':>14}"
                      f"{'dD':>14}{'|d/R|':>10}{'|dD/R|':>10}")
                for a in AXES:
                    if f"{a}_d" not in h or f"{a}_all" not in h:
                        continue
                    R = s[f"{a}_all"] - h[f"{a}_all"]
                    dh, ds = h[f"{a}_d"], s[f"{a}_d"]
                    dD = ds - dh
                    r1 = abs(dh / R) if R else float("inf")
                    r2 = abs(dD / R) if R else float("inf")
                    print(f"   {a:<10}{fmt(R)}{fmt(dh)}{fmt(ds)}{fmt(dD)}"
                          f"{r1:>10.2f}{r2:>10.2f}")

    print("\n" + "=" * 100)
    print("READING IT: |d/R| >> 1 means the training target carries far more selection than the whole")
    print("warming signal (a LEVEL confound). |dD/R| of order 1 means the confound does not cancel in a")
    print("response and therefore lands on arm C's headline number. Both are LOWER BOUNDS -- the `ind`")
    print("writer drops every stem below 5 m, so selection before that height is invisible here.")
    print("=" * 100)


if __name__ == "__main__":
    main()
