---
status: "accepted"
date: 2026-07-29
deciders: "engineering agent on line S (full autonomy per STEERING_PROMPT.md). Two decisions are recorded: (1) the GLOBAL generation is re-derived as `t8` on the ADR-0035 feature bases for historic, SSP370 and the pooled multi-regime pair, and (2) the emulator's BIOMASS and SIZE distributions are validated by APPENDED DIAGNOSTIC copula axes rather than by promoting them to production axes — because the 4-axis production `.rcop` is a frozen cross-line contract (ADR 0025) that line M pins."
consulted: "ADR 0035 (the feature bases this generation exists to carry into the global tables), ADR 0025 (the frozen 4-axis recruit-trait contract and `make_recruit_to_pools`), ADR 0026 (the pooled multi-regime + transient-boundary design), ADR 0030 (the per-cell trait gate the struct axes reuse), ADR 0031 (the complete seven-PFT tree population these tables are on), ADR 0029/CLAUDE.md section 9 (versioned artifacts, never mutate `_t7` in place), CLAUDE.md section 3 (the C's `agb` is per-m2 with nind baked in; the ind writer emits only stems above 5 m)"
informed: "lines/S/STATE.md (Status + NEXT), lines/M/STATE.md (the new artifact names to re-pin deliberately), the slow-drf-pipeline + emulator-validation-figures skills, changelog.d/S-t8-global-generation-and-biomass-validation.md"
---

# Biomass and size are validated as APPENDED DIAGNOSTIC copula axes, on the `t8` global generation

> **Status.** `accepted`. No change to any frozen contract, any serialized production artifact's schema, or
> any committed fixture. `_t7` is untouched; the new artifacts are `_t8` and line M re-pins deliberately.

## 1. The question that forced a decision

The standing ask is *"show that the global emulator reproduces LPJmL-FIT — per-cell trait distributions,
biomass, tree numbers."* Two of those three were already measured: tree numbers by the count DRF's figures
01-08, per-cell trait distributions by the copula's figures 09-11 and the ADR-0030 per-cell gate.
**Biomass and individual size were not measured at all.**

They are not a missing metric on an existing target — they are a different target. The count DRF predicts
`n_living` per patch; the copula predicts four *recruit traits* (`SLA`, `Wooddens`, `D95max`, `minwscal`).
Neither predicts stand biomass. So "is biomass matched?" needed a decision about *where* biomass enters the
model, and the obvious answer was wrong.

## 2. Why not simply add `agb`/`Height` as production copula axes

Because the 4-axis set is a **frozen cross-line contract**, not an implementation detail:

- `src/components/slow.jl::make_recruit_to_pools(axes)` maps exactly those four axes onto carbon pools
  (ADR 0025). A fifth and sixth axis in the serialized `.rcop` silently redefines that mapping.
- Line M **pins** `recruit_copula_global_pooled_w20*.rcop`. Changing what the artifact contains is a
  both-sides change requiring an integration point, for a *validation* need that has no runtime consumer.
- `agb` and `Height` are **outcomes of the dynamics**, not establishment traits drawn from a per-PFT interval.
  Sampling them from a marginal at recruitment and pushing them into pools would double-count what F's
  allocation already computes — a physics error, not just a contract violation.

So the axes are built and scored exactly like production axes, and **excluded from the artifact**. The
exclusion is structural rather than careful: `train_slow_copula.jl` reads the manifest's `axes` line, while the
struct set lives in a separate `nstruct`/`struct_axes` pair, so `axes`/`naxes` keep meaning the production
axes and no code path can carry a struct axis into `DRF.save_copula`. Verified: the smoke gate asserts the
`.rcop` meta declares no struct axis.

**They are APPENDED, never interleaved, and that is load-bearing.** `eval_slow_copula.jl` seeds each axis's
forest (`seed = a`) and its per-row draw RNG (`Xoshiro256pp(i*131 + a)`) from the axis **INDEX**. Appending
therefore leaves every production axis's index — and so its OOS prediction — bit-identical. This is guardrail 4
("opt-in, default byte-identical") and it is **measured, not asserted**: the 50-cell smoke builds the same
table with the option off and on and `cmp`s every shared file and every production `pred_<axis>.f64`.
`[VERIFIED 2026-07-29, job 1641319]` — all four production predictions byte-identical, both struct predictions
present, mismatched struct sets refused by `pool_slow_tables.py`.

## 3. How stand biomass is measured — and the cross-check that makes it quotable

Stand biomass is a **composite of the emulator's two halves, both out-of-sample**:

```
pred_stand_agb(cell) = mean_OOS(n_living)  x  mean_OOS(per-stem agb)
obs_prod(cell)       = mean(n_living)      x  mean(per-stem agb)          # the SAME functional form
true_stand(cell)     = mean over (patch,year) of the C's own per-patch sum(agb)   # X column `agb`
```

**What `basis_ratio` measures — corrected after an adversarial audit of this ADR's first draft.** The draft
claimed `mean(N) x mean(A)` differs from `mean(N x A)` by a negative within-cell covariance of stem count and
mean stem size. **That is algebraically false**, and four independent audit lenses caught it. The per-cell
per-stem mean is **stem-weighted** (one table row per stem, so `mean` = total agb / total stems), not the mean
of per-patch means. Writing `R` for the cell's row count:

```
obs_prod = [ (1/R) Σ_r N_r ] · [ Σ_s a_s / Σ_r N_r ] = (1/R) Σ_r Σ_{s∈r} a_s = (1/R) Σ_r stand_agb_r
```

The `Σ_r N_r` factors cancel: the product is `true_stand` **exactly**, and no covariance term survives.

So `basis_ratio` is a **ROW-UNIVERSE CONSISTENCY CHECK** between the count table and the copula table — *do
the emulator's two halves describe the same rows?* — which is a real and useful thing to measure, and not a
statistical correction. It departs from 1 only when the two tables cover different (Cell,Patch,Year) rows:
the count table drops each scenario's first year (it needs the AR state `n_prev`) while the copula table keeps
it; any conditioning-join coverage difference; and under `STEM_CAP` the cluster subsample (below).

`[VERIFIED 2026-07-29]` **`basis_ratio = 0.992`** on the uncapped historic basis — the two tables' row
universes agree to 0.8 %, essentially all of it the dropped first year (1/20 of a 20-year run would be 5 % if
biomass were flat in time; it is not, the first year is the lowest-biomass one). Fig 12's right panel is that
check and sits on the 1:1 line. The gate now also requires the **spread** to be tight (p10 ≥ 0.8, p90 ≤ 1.25)
and reports the fraction of cells more than 10 % off, because a median-only band hides per-cell disagreement.

**The lesson is the one this project keeps relearning:** a plausible statistical story ("of course a product of
means differs from a mean of products") survived writing, review and a figure caption because it *sounds*
right. Do the algebra on the estimator you actually implemented, not on the one the story describes.

Two further honesty rules are wired into the output rather than left to the reader:

- **Both a linear and a log10 per-cell R2 are reported.** Stand AGB spans 3+ decades across cells, so a linear
  R2 is dominated by the highest-biomass cells and is nearly blind to the semi-arid and boreal tail that is
  most of the land area.
- **For a heavy-tailed axis, read KS, not `nqrmse`.** Per-stem `agb` reads `nqrmse ~ 0.68` while its `KS ~ 0.011`
  and the two histograms are visually indistinguishable: `nqrmse = RMSE(q05..q95)/IQR` is dominated by its q95
  term when `q95/IQR` is of order 10. The panel title now says this itself. Same family as ADR 0031's lesson
  that a scale-free metric can move because its scale moved.

## 4. A caption that overclaimed, corrected in the same change

Figure 06 (the count histogram) was captioned *"the distributional check the count DRF exists to pass"*. That
is wrong: `eval_slow_drf.jl` scores the count DRF with `DRF.predict`, a **conditional mean** — a convex
combination of training leaf means — not a quantile draw the way `eval_slow_copula.jl` does. A predicted count
histogram is therefore narrower than the observed one **by construction**, and reading that narrowing as a
distributional miss (or as a pass) is meaningless. Both the panel and the report now state it. The
distributional claims in this report are the copula's, which do draw per stem.

This is also why **no per-cell count-KS figure was added** even though it would have been symmetric with the
trait figure 11: a conditional mean cannot be scored against an observed within-cell spread.

## 5. The `t8` generation

`t8` re-derives every GLOBAL table and artifact on the ADR-0035 bases (`soilmoist` = root-zone year-end
plant-available fraction of WHC via `build_rootmoist_soilmoist_feature.py`; `lai` = the per-patch in-row
reconstruction). `_t7`'s published OOS numbers remain valid as *offline* measurements, but a coupled global run
would inherit the retired bases, so line M needs a clean pin. **`_t7` is not mutated** (ADR 0029).

Count half `[VERIFIED 2026-07-29]` — the widened seven-PFT population is intact and the skill is unchanged by
the basis move:

| | historic | ssp370 | pooled (w20 transient) |
|---|---|---|---|
| rows / cells | 22 467 348 / 53 699 | 99 023 397 / 58 496 | 121 495 658 / 58 588 |
| in-sample R2 | 0.9827 | 0.9825 | 0.9824 |
| K-fold-by-cell OOS R2 / RMSE | **0.9826 / 0.689** | **0.9823 / 0.698** | **0.9824 / 0.697** |
| held-out-CELL test R2 | — | — | 0.9824 (5 744 test cells) |
| hold-out-by-SCENARIO R2 | 0.982 (held out historic) | 0.9818 (held out ssp370) | — |
| per-cell-mean R2 / bias | 0.9988 / 0.0027 | — | — |

The unseen-regime gap stays flat (holdout-by-scenario within 0.0006 of the by-cell baseline), i.e. one pooled
environment-conditioned emulator generalizes across the historic and SSP370 climate regimes — ADR 0026's goal,
now on the ADR-0035 bases.

Artifacts (DVC on `/p/tmp/jamirp/emulator_global/`, never git): `drf_forest_global_{historic,ssp370,pooled_w20}_t8.drf`
(+ `_meta.txt`), `recruit_copula_global_{historic,ssp370,pooled_w20}_t8.rcop` (+ `_meta.txt`), tables
`slow_{runtime,count,copula}_*_t8/`, and the ADR-0030 companion `slow_copula_historic_seed2_t8`
(197 802 377 stems / 54 058 cells — the same census as `_t7`, confirming the population did not move; only the
conditioning did). All three count DRFs load-verify at `nfeat == 15`, 150 trees.

## 5b. A silent data-integrity defect the audit found in the SAME generation

An adversarial audit of this generation found, and I then reproduced directly from the artifacts, that
**`collect(engine="streaming")` on the builder's per-patch-year aggregate is not deterministic in the KEY SET
it emits** at global scale — not merely in float summation order, which is all the module docstring warned
about. Two runs of the ssp370 count build over the same `ind` parquet produced **99 023 397** and
**99 028 310** rows: 141 of 58 496 cells differ, the static build is short by **4 913 rows net**, and **12
cells came out with EXTRA rows** (duplicated keys). Historic is unaffected (its two t8 tables agree exactly).
The affected cells are contiguous (2579-2586 …), consistent with a partition-boundary artifact.

Nothing caught it, and the reason is structural: the builder's two coverage gates watch only the FEATURE
joins, and their `dropped = h0 - height` statistic goes **negative** under duplication, so a `drop_frac > 0.02`
test can never fire. The AR self-join then *amplified* the damage — a key present twice on both sides yields
four rows.

Fixed in this change, in the order that matters:
1. **A hard key-set invariant** on the aggregate (`n_unique(Cell,Patch,Year) == height`), and a second one
   after the joins, so this class of corruption fails loud instead of shipping.
2. **The AR self-join is replaced by a window shift** (`shift(1).over([Cell,Patch])` plus a year-contiguity
   filter), which is equivalent whenever keys are unique and removes the amplification path entirely. Gated
   by rebuilding the historic table and comparing it against the shipped one (`y`/`cells` byte-identical;
   `X` within the documented streaming-sum jitter).

**Scope of the impact, stated plainly.** ~5e-5 of rows, so the published R² digits are unaffected. The
**pooled** artifacts — the pair line M pins, and the "one model across both regimes" claim — are built on
`slow_count_ssp370_w20_t8`, the table that matches the `ind` parquet's own truth, so they are clean. The
affected artifact is the **per-scenario** `drf_forest_global_ssp370_t8.drf` and its OOS number. The real cost
is reproducibility, not accuracy: a versioned artifact that cannot be re-derived row-for-row undercuts the
ADR-0029 discipline that line M pins an artifact and must be able to rebuild it.

## 6. Consequences

- **Line M must re-pin deliberately.** The `_t8` pair is the clean one; `_t7` stays readable. Do not re-point
  M's pinned path from line S (ADR 0029).
- **The biomass/size numbers are OFFLINE, table-vs-table.** They score the learned mapping fed LPJmL-FIT's own
  annual drivers. They say nothing about a recursive coupled trajectory, which can drift for reasons no number
  here exposes. State that wherever they are quoted.
- **`STEM_CAP` is a patch-year CLUSTER subsample, not a per-stem one** — also corrected by the audit, and the
  builder's own comment said "random subsample" for months. The rank it caps on is a hash of
  **(Cell,Patch,Year)**, identical for every stem in a patch-year, and the `+ int_range` tiebreak spans only
  `0..n` while hashes span the full u64 — so it keeps whole patch-years. Consequences: the effective sample
  size of a capped table is **patch-years, not stems**, so per-cell statistics are noisier than the stem count
  suggests; and a capped per-cell mean must never be described as an unbiased per-stem mean.
- **The biomass composite is therefore REFUSED for the pooled pair**, and that is a correctness stop rather
  than caution: the pooled count table is ~81 % ssp370 rows (22.5 M + 99.0 M) while the pooled copula table at
  `STEM_CAP=400` is ~53 % ssp370 stems (19.9 M + 22.3 M), so a per-cell mean of each factor weights the two
  climate regimes differently and their product is not any cell's stand biomass in either regime. Per-scenario
  figure sets are unaffected. Lifting this needs `Year`/`scenario` alignment between the two tables — a table
  schema change (emit `Year` in the copula table), deliberately not done inside this milestone.
- **`STEM_CAP` is now recorded in the copula manifest** (`stem_cap`). It was not, so a consumer could not tell
  a capped table from an uncapped one at all.
- **The struct axes cannot change the ADR-0030 gate's verdict or exit code.** They are computed on the same
  cells and printed `[diag]`, and every struct read is wrapped so a missing or short file is reported and
  skipped. If the two seeds' tables declare different struct sets the rows are skipped, never intersected —
  a silently-narrowed column list is precisely the ADR-0031 failure mode.
- **If a future change needs biomass in the runtime**, this ADR is the wrong basis for it: that is an S4/S6-class
  physics decision about what S owns, and it must go through the ADR-0025 contract with line M, not through a
  diagnostic axis.
