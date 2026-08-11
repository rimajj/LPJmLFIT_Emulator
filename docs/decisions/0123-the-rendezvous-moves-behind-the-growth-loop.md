# ADR 0123 — The rung-2 rendezvous moves behind the growth loop; the lag is gone and arm C is scorable on traits

- **Status:** accepted
- **Date:** 2026-08-11
- **Line:** M (multi-cell coupled S+F+E; ADR block 0120–0139)
- **Supersedes / amends:** amends ADR 0120 (the substitution hook's call site) and ADR 0122 §4 (which
  pre-registered that arm C must not be scored on the trait question from the *then-current* rendezvous —
  that restriction is now **lifted**, by fixing the rendezvous rather than by reinterpreting it).
- **Related:** ADR 0061 (the observation hook), ADR 0121 (the three-phase dump + the corrected replay
  floor), ADR 0041 (a subset re-run is not a per-cell replica), ADR 0046 (the warming shift is within-PFT
  selection), ADR 0117 (S's option (c) reply), ADR 0118 (the copula-selection confound).

## 1. Context

ADR 0122 measured a defect in the rung-2 interface that had nothing to do with the ported hazard and
everything to do with *where the C asks the question*. The rendezvous — `rung2_apply_begin_patch` — sat at
the **top** of the annual demography block, but the C's own hazard runs later, inside `annual_tree` →
`mortality_tree_ind`, after `turnover_tree` and `allocation_tree`. So the roster the interface published
carried **last year's** `bm_delta`, `leafarea_real` and `bm_inc_counter`.

Per-tree *ordering* mostly survived that (per-patch-year Spearman ρ vs the C's own `mort_prob`: median
0.900, p05 0.467). The *trait statistic* did not. The one-year wood-density selection differential —
hazard-weighted mean minus the stand mean, the ID-free quantity ADR 0046 fingerprinted and ADR 0049's flip
criterion is written on — came out at the **wrong sign**: ratio **−0.825** against the C. Attribution was
unambiguous: lagging only `bm_delta`/`leafarea_real` is harmless (+1.001), lagging only `bm_inc_counter`
reproduces the inversion (−0.567). The counter **multiplies** `mort_npp` and `mort_water` by
`(1+counter)` and is updated from **this** year's growth sign, so misdating it re-weights exactly the trees
the differential measures.

ADR 0122 §4 therefore pre-registered that **arm C could not be scored on traits**, and named the fix: move
the rendezvous behind the growth loop.

## 2. Decision

**Move the rendezvous behind the growth loop, and move the kill with it.**

Per patch-year the C now:

1. dumps `pre` (start-of-year state, unchanged) and opens an empty verdict table;
2. runs the growth loop exactly as before — `turnover_tree`, `allocation_tree`, `mortality_tree_ind`
   including its `erand48` draw — but `annual_tree` **reports every tree alive** and hands its verdict
   (`c_isdead`, plus a `hard` flag for the kills the C's own state cannot un-make) to `rung2_apply_note`;
3. dumps the new **`grow`** phase — the complete current-year roster, before anyone has been taken out of
   it — and opens the rendezvous on exactly that state;
4. runs a **kill pass** over the roster, applying each final verdict with its `litter_update` and its
   `mort_tree` counter;
5. continues unchanged: `mort` dump → fire → establishment → `post` dump.

The kill has to move with the rendezvous: a tree the external demography spares must not already be in the
litter. Deferring only the *decision* is not available.

**The deferral is shared by BOTH hooks** (`rung2_defer_mortality()` is true when either `LPJ_RUNG2_DIR` or
`LPJ_RUNG2_APPLY_DIR` is set). That is the load-bearing part of the design and §4 explains why.

Interface changes: `rung2_apply_isdead` now takes only the `Pft` and looks its verdict up;
`rung2_apply_reset_patch` and `rung2_apply_note` are new; the request file carries the `grow` roster
instead of the `pre` one; the roster key table grew from a fixed 1024-entry array (which silently stopped
recording duplicates past the cap) to a dynamic one. Patch: `patches/lpjmlfit_rung2_hook_v5.patch`
(supersedes v4, which is kept for the provenance of the binaries ADR 0122 gated).

## 3. The result — the lag is gone, exactly

`scripts/diagnose_rung2_hazard_identity.jl` now prints **both** rendezvous bases from the same dump, so
the fix is visible rather than asserted. Cell 42490, 25 patches, 2000–2019, re-recorded baseline
`/p/tmp/jamirp/M_rung2/M_rung2rec_v5_dump`:

| rendezvous basis | records usable / skipped | Spearman ρ vs the C's `mort_prob` (p05 / median / min) | wood-density selection differential | ratio to the C |
|---|---|---|---|---|
| `pre` — the OLD rendezvous | 9 009 / 942 | 0.467 / 0.900 / −0.200 | −14 591 | **−0.825 ⚠ opposite sign** |
| **`grow` — the LIVE rendezvous** | **9 951 / 0** | **1.000 / 1.000 / 1.000** | **+34 045** | **+1.000** |

Two things beyond the headline:

- **The skip disappears.** The lagged basis had to drop 942 of 9 951 records because a tree in its first
  year has no previous `mortality_tree_ind` call and the lagged columns are uninitialised memory
  (ADR 0120). At `grow` every column is this year's, so every record is usable — the youngest cohort,
  which is exactly where selection is strongest, stops being invisible.
- **The θ = 1 identity gate still passes exactly** on the re-recorded dump: 9 951 records, 0 exceedances,
  max relative Δ 1.7e-15 on `mortality_hazard.total`, both hard-kill classes correct (175
  `bm_inc_counter ≥ 5`, 195 ghost-tree). The CI fixture
  `test/testitems/references/M_rung2_hazard_identity.csv` was regenerated on the new basis (82 of 333
  records moved, header unchanged) so the committed C truth and the current binary stay reproducible from
  each other.

⇒ **ADR 0122 §4's restriction is lifted. Arm C is now scorable on the trait question**, subject to the two
conditions ADR 0118 §3 pre-registered (print θ beside the result; test the per-PFT gradient *shape*
against `references/S_age_wooddens_gradient.csv`, not just the level).

## 4. The cost, measured — and why the null control is still exact

The reordering is **mathematically inert**: the litter pools it feeds are pure sums; `litter->avg_fbd` is
an exact incremental carbon-weighted mean (each `update_fbd_tree` re-weights by the pool total *after* its
own addition), so its value once every contribution is in does not depend on order; nothing between the
loop and the kill pass reads either (`fire_prob`, `firepft` and the FPC/output blocks all run afterwards);
and `litter_update_tree` mutates only the dying tree's own pools, which no other tree's turnover or
allocation reads.

Mathematically inert is not bit-identical — floating-point addition is not associative. **Measured**, same
config, same cell, `--ntasks=1`, deferred path vs stock in-loop path:

| what | value |
|---|---|
| first year in which anything differs at all | **2003** (2000–2002 bit-identical) |
| size of that first difference | 1.1e-7 absolute on a daily NPP of −0.081 (≈1.4e-6 relative, in a float32 output) |
| first year the demography differs | 2004, by **one stem** (332 vs 333) |
| years of 20 whose stem count differs | **3** (2004, 2015, 2017), always by exactly one stem |
| terminal (2019) stem count | **229 = 229, identical** |
| total stem-years | 5 963 vs 5 966 — **0.05 %** |

For scale: the smallest noise floor documented for this model is the bootstrap CV at the production
`npatch=25` (11.3 % on `vegc`), and the C's own two-run spread reaches 29 % in low-density cells. A 0.05 %
stem-year difference is more than two orders of magnitude below that.

**Why the deferral is shared by both hooks.** If only the substitution hook deferred, the recorded baseline
(observation hook only) and every replayed arm would sit on *different* code paths, and the difference
between them would be charged to the arm. Sharing it means the recorded baseline and the arms are the same
path, and the null control is exact **by construction** rather than by luck. Verified:

- `MODE=none` (rendezvous active for all 500 patch-years, both halves deferred) vs the re-recorded
  baseline: **identical in every initialised column over 40 161 tree records**, and
  `diagnose_rung2_cellstate_equality.py` reports **no divergence in all 2 000 patch-years** — the per-cell
  random stream, the seedbank checksums and the live tree count all agree.
- Rebuild equality with **both** env vars unset, against the previous build's matched single-cell run:
  **139 decoded quantities identical, 0 differ**, `globalflux` and `ind` byte-for-byte. The stock model is
  untouched.

**Disclosure that must ride with every rung-2 number from here on:** the C the rung-2 harness runs applies
its demographic kills at the end of the growth loop instead of inside it. That moves the C's *own* answer
by 0.05 % of stem-years at Hainich over 20 years. It is not a difference between arms — every arm and the
baseline share it — but it is a difference from stock LPJmL-FIT, and a rung-2 result is on that path.

## 5. Consequences

- `scripts/rung2_replay_harness.py` learns the `grow` phase, asserts the `grow` roster is the `pre` roster
  (growth adds and removes nobody, which is what keeps a `K` line unambiguous under either), and **fails
  loudly** on a dump that predates the move rather than replaying a stale roster.
- **Any dump recorded before this change is unusable as a replay basis** and the harness says so. The
  current baseline is `/p/tmp/jamirp/M_rung2/M_rung2rec_v5_dump`; `M_rung2rec_v4b_dump` is superseded.
- **The replay floors are UNCHANGED by the move**, which is a result in itself. All four arms were re-run
  on the v5 basis: `none` **1.000**, `kills` **1.000 exact** (identical in every initialised column and in
  all 2 000 cell-state patch-years, no year differs), `recruits` **0.907**, `both` **1.367** — ADR 0121's
  numbers to three decimals. So the floors are a property of *what the wire format substitutes* (4 of 7
  trait axes; the C's Poisson and inheritance draws skipped), not of where the rendezvous sits.
- Generalisable, and it is the third time this shape has bitten this interface: **an interface's value is
  set by WHERE it is placed in the host's control flow, not by what it carries.** ADR 0121 found a kill
  list that named the wrong authors' deaths; this one found a roster published at the wrong instant. Both
  passed every schema and null-control check. The check that catches this class is to recompute the host's
  own answer from what the interface publishes and require ρ = 1 — not to verify that the fields are
  present and finite.
