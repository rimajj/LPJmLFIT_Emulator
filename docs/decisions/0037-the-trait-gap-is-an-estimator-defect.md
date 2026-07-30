---
status: "accepted"
date: 2026-07-30
deciders: "engineering agent on line S (full autonomy per STEERING_PROMPT.md). Three decisions are recorded: (1) milestone S2's premise is REFUTED as the primary cause — the ADR-0030 per-cell trait GAP is dominated by the ESTIMATOR, not by missing conditioning columns; (2) `DRF.predict_quantile` was not implementing the quantile-regression-forest estimator it is documented as, and that is fixed as an opt-in `qrf` weighting carried eval -> train -> `.rcop` meta -> runtime; (3) the conditioning expansion IS worth doing but is a SECOND-order lever and ships as an opt-in six-column moisture/aridity tail rather than the full 28-column set. The PRODUCTION enablement choice is deliberately DEFERRED until the QRF x capacity matrix completes."
consulted: "ADR 0030 (the per-cell trait gate, its attenuation-corrected ceiling and the dispersion ratio this ADR moves), ADR 0033 (twice-recorded warning that this line credits one change with another's effect — the reason capacity, weighting and covariates are each measured in isolation), ADR 0025 (the frozen 4-axis recruit-trait contract, `live_flux_cond` and the pluggable `cond` policy that let the conditioning extend additively), ADR 0023 (train/inference consistency — why the estimator has to travel into the artifact meta and the runtime struct), ADR 0032 (the proof that a target-band assertion cannot detect a conditioning shift, which generalizes to this weighting shift), ADR 0036 section 5b (polars streaming key-set nondeterminism — why `t9` must reuse the `t8` tables), Meinshausen 2006 (Quantile Regression Forests), CLAUDE.md section 9 (versioned artifacts; one session per line)"
informed: "lines/S/STATE.md (NEXT + the three-lever table), lines/M/STATE.md (pending — M re-pins deliberately once a production configuration is chosen; the count `.drf` is UNAFFECTED), the slow-drf-pipeline + julia-test skills, changelog.d/S-copula-gap-is-estimator-capacity.md, changelog.d/S-qrf-weighting-and-extended-conditioning.md"
---

# The per-cell trait GAP is an ESTIMATOR defect, not missing conditioning

> **Status.** `accepted`. No frozen contract, serialized artifact schema, or committed fixture changes. Every
> mechanism here is **opt-in and default byte-identical** (guardrail 4), verified rather than assumed: suite
> **107 355 pass / 0 fail / 4 broken** with the `RecruitCopula` field added, Runic clean, and the empty
> conditioning tail reproduces `live_flux_cond` exactly. `t8` is untouched. **Production enablement is
> deferred** — see section 7.

## 1. The question, and why the answer inverted the milestone

Milestone S2 was scoped, across ADR 0030/0033 and two handoffs, as: *expand `COPULA_COND_COLS` and
`live_flux_cond` in lockstep with environment / PFT-composition covariates*. The target was the Wooddens axis,
whose per-cell median reached `emu_r` 0.814 against an attenuation-corrected ceiling of 0.964, with a
between-cell dispersion ratio `sd(pred)/sd(Y1)` of only 0.678.

"Add covariates" is a hypothesis, not a diagnosis. The GAP has exactly two possible causes and only one is a
covariate problem:

* **missing information** — the conditioning genuinely does not determine a cell's trait median;
* **estimator inefficiency** — the information is present and the estimator fails to extract it.

`scripts/diagnose_copula_cond_ceiling.py` separates them by fitting a DIRECT per-cell regressor (LightGBM,
K-fold BY CELL) on per-cell covariate sets, after first reproducing the documented `emu_r`/`floor_r`/`sd_ratio`
and refusing to continue if they disagree. On `t8` historic, 52 165 cells:

| axis | copula `emu_r` | r(same 8 cond cols) | r(+28 env) | **estimator share** | covariate share |
|---|---|---|---|---|---|
| SLA | 0.881 | 0.962 | 0.973 | **+0.080** | +0.011 |
| Wooddens | 0.814 | **0.916** | 0.941 | **+0.102** | +0.025 |
| D95max | 0.791 | 0.879 | 0.922 | **+0.089** | +0.042 |
| minwscal | 0.945 | 0.977 | 0.981 | +0.032 | +0.004 |

**Wooddens reaches 0.916 from the EXISTING eight columns — already past the S2 gate's 0.889 target — and its
`sd_ratio` reaches 0.896 against a ≥0.75 target.** The conditioning was never the binding constraint.

Two honesty conditions on that table, both discharged. It is an **UPPER BOUND, not a forecast**: a direct
per-cell fit optimizes the very statistic the gate scores, on ~54k rows rather than ~198M, so it bounds
headroom and ranks covariates and is not a claimable skill number. And a per-cell time-mean of a flux driver
discards within-cell year-to-year conditioning that the copula *does* receive (it conditions per
`(Cell, Year)`), which biases the estimator share DOWN — so the run was repeated with per-cell q10/q90 flux
features (`FLUX_QUANTILES=1`, the numbers above). That variant moved the split **further** toward the
estimator (Wooddens +0.079 → +0.102, covariates +0.045 → +0.025), which is the strongest available form of the
evidence: adding information the copula already has strengthens the conclusion rather than weakening it.

## 2. Lever one — capacity. Real, bounded, and it trades against the pooled marginal

`EVAL_SUBSAMPLE`/`SUBSAMPLE` defaulted to **50 000** against ~158M training rows over ~54k cells: roughly ONE
row per cell per tree. Measured on the artifact line M pins
(`recruit_copula_global_historic_t8.rcop`): **1063 leaves per tree for 54 020 cells**, i.e. each leaf hands
~51 cells one identical conditional distribution, 47.1 values/leaf, 122 MB loading at 42 MB/s.

`scripts/diagnose_copula_capacity.sh` re-runs the K-fold OOS at a chosen capacity on an **unchanged** table and
scores the gate, so capacity is isolated from any conditioning change — deliberately, per ADR 0033.

| rung | ntrees × subsample, depth | Wooddens `emu_r` | % of GAP | `sd_ratio` | pooled `nqrmse` W / D95 |
|---|---|---|---|---|---|
| baseline = `t8` | 40 × 50 000, d14 | 0.814 | — | 0.678 | 0.013 / 0.006 |
| `b12x500k` | 12 × 500 000, d18 | 0.844 | 28 % | 0.749 | — |
| `b6x2M` | 6 × 2 000 000, d22 | **0.862** | **32 %** | **0.770** | **0.023 / 0.019** |

The baseline rung reproduced `t8`'s gate **bit-for-bit**, which is what licenses trusting the others. Every
axis improved on every rung and `minwscal` reached its ceiling — but **no rung passed all four gate criteria**.
`b6x2M` met the dispersion target and lost the pooled marginal (~2× worse), because six trees pool ~240 values
per draw instead of ~1880. `b12x500k` was *worse* per-cell than `b6x2M` despite twice the trees, so
**resolution matters more than averaging**.

Measured cost model, which decides what is shippable rather than merely better: fit ∝ `ntrees·subsample`,
predict over ~198M rows ∝ `ntrees`, and `.rcop` bytes ≈ **`10.7·ntrees·subsample·naxes`**. Resolution is not
free — the runtime must load the artifact.

## 3. Lever two — the forest was not using its own estimator

`DRF.predict_quantile` concatenated every tree's leaf values into one pool and took an **unweighted** quantile.
That gives each stored value weight `1/Σ_t|L_t(x)|`, so **a tree contributes in proportion to how large its
leaf happens to be**. A quantile-regression forest (Meinshausen 2006) is defined by the opposite — each tree
contributes `1/T`, spread evenly inside its own leaf:

```
w_i(x) = (1/T) · Σ_t 1{i ∈ L_t(x)} / |L_t(x)|
```

**The precondition was tested before any code was written**, because the two estimators coincide exactly when
all leaves are the same size and the fix would then be inert. Over the `t8` Wooddens marginal's 70 854 leaves
the sizes run min 20 / median 26 / q90 55 / q99 371 / **max 4016**, coefficient of variation **2.01**. Per
query point the largest of 60 leaves holds ~1400–1750 values against a median leaf's ~35, so that ONE leaf took
**17–21 %** of the prediction weight where QRF gives it **1.7 %** — a **10–12× over-weighting**.

**The bias has a direction, and that is why it mattered rather than being untidy.** A large leaf is one that
stopped splitting early, so it spans a wide region of conditioning space and its value distribution
approximates the GLOBAL marginal. Over-weighting it drags every cell's conditional toward that marginal: an
attenuation mechanism. It also explains the otherwise puzzling ladder result in section 2 — **more trees never
improved dispersion**, because more trees means more chances to land in one dominating big leaf.

**Why the published metrics never caught it.** Because the prediction is a *mixture* over leaves, it reproduces
the global marginal beautifully (pooled `nqrmse` 0.013, pooled KS 0.0065) while the per-cell conditional stays
under-resolved (`sd_ratio` 0.678, slope `Y1~pred` **1.20**, the textbook attenuation signature; `sd(Y2)/sd(Y1)`
≈ 1.00 on every axis, so the under-dispersion is the emulator's and not the target's). **Pooled-marginal
metrics — `nqrmse`, pooled KS, `median_rel_q_err` — are STRUCTURALLY BLIND to a badly under-resolved
conditional**, and those are what the validation figure set reports. This is the same shape as ADR 0032's
finding that a target-band assertion cannot detect a conditioning shift: both fail because a DRF prediction is
a convex combination of training leaf values and therefore stays in range however wrong its coordinates or
weights are.

**The confound was separated rather than assumed away.** Switching to QRF also switches the quantile
CONVENTION (the default indexes `1 + floor(u·(n−1))`; a weighted ECDF must be inverted). Scoring an
equal-weight inverse-CDF variant on the same pooled values attributes **0.002–0.014 %** to the convention
against the weighting's **1.67–4.43 %** — a 315–1507× ratio, i.e. a ≤1-rank shift out of 5 000–16 500 pooled
values. Without that check the whole result would have rested on a plausible story, which is the ADR-0036
lesson.

**Scope.** `DRF.predict` was ALREADY correct (it averages leaf means at `1/T`), so this is a
distributional-path-only defect: **the count DRF is unaffected and every count number stands** (OOS R² 0.9826,
per-cell-mean 0.9988). Line M's pinned count `.drf` needs nothing.

## 4. Why the fix is opt-in, and why it had to travel four places

`qrf = false` remains the default so every committed artifact, golden draw pair and reference baseline is
bitwise unchanged (guardrail 4). But an estimator knob on the evaluation script *alone* would have created a
new ADR-0023 shift: an artifact could be **scored** under one estimator and **served** under another. So it
lands in four places together:

1. `QRF` on `scripts/eval_slow_copula.jl` (the OOS numbers);
2. `QRF` on `scripts/train_slow_copula.jl` (the fitted artifact's golden pairs);
3. a **`qrf_weighting 0|1`** line in the `.rcop` meta, so the artifact *declares* what produced its numbers;
4. a **`qrf` field on `RecruitCopula`**, passed by `reconcile_demography!` to `sample_copula!`, defaulted in
   both legacy constructors (4-arg and 5-arg, verified) so line M's call sites stay byte-identical.

The failure this prevents is silent, for the reason in section 3.

## 5. Lever three — extended conditioning: six columns, not twenty-eight

The covariate gain is real and physically motivated: the boundary tail carries `eco_diag_gdd_5`,
`tas_cold_month`, `soil_depth`, `co2` — one temperature axis and one soil axis, and **no moisture or
precipitation climatology at all** — while FIT's establishment gates are temperature AND moisture. On Wooddens
an environment-only predictor (0.910) even BEATS the eight production columns (0.893).

**But the full 28-column set is the wrong implementation of a correct idea.** It would take `Xc` from 12.6 GB
to ~57 GB and push `mtry = round(√p)` from 3-of-8 to 6-of-36, diluting the informative columns among
correlated climate ones — plausibly *costing* skill. Ranking compact subsets (`ENV_SETS`) instead:

| axis | moist2 | moist4 | **moist6** | moist6+lat | all 28 |
|---|---|---|---|---|---|
| Wooddens | +0.009 | +0.013 | **+0.018** | +0.020 | +0.025 |
| D95max | +0.008 | +0.013 | **+0.027** | +0.029 | +0.042 |
| SLA | +0.003 | +0.006 | **+0.007** | +0.008 | +0.011 |
| minwscal | +0.001 | +0.002 | +0.003 | +0.003 | +0.004 |

Six columns — `prec_mean, eco_diag_p_pet_ratio, eco_diag_pet_mean, eco_diag_vpd_mean, pr_cv_monthly,
humid_mean` — capture **64–72 %** of the full gain at `ncond` 14 and `mtry` 4-of-15. Adding `lat` buys +0.002.

**It ships additively, not as a contract change.** An earlier framing of S2 treated this as necessarily a
both-sides lockstep landing because the boundary tail is *shared* with the count DRF, so extending it would
change `forest.nfeat` on both models and the `cell_meta.parquet` schema. That is avoidable:
`RecruitCopula.cond` is already a pluggable policy (ADR 0025), so `live_flux_cond_env(env)` appends a
conditioning-only tail with **no struct change, no `.rcop` format change, `live_flux_cond` itself untouched,
and the count DRF's boundary tail left alone**. The training counterpart is `COPULA_ENV_COLS`. Both default to
an empty tail that reproduces the current eight columns exactly. The `.rcop`'s `cond_cols` line is the
train/inference contract, and a mismatch fails silently.

## 6. What was rejected

* **Expanding the conditioning as the primary fix** — measured as the smallest of the three levers (~4× smaller
  than the estimator terms) and the most plumbing. Kept, but demoted and separately attributed.
* **Adding all 28 environmental columns** — section 5: storage and `mtry` dilution.
* **Making QRF the default** — it would move every committed golden pair and reference baseline in the same
  change that introduces it, destroying the ability to attribute any subsequent gate movement.
* **Trading trees for resolution at a fixed artifact budget as the production answer** — `b6x2M` and
  `b12x500k` show it buys per-cell dispersion by degrading the pooled marginal.
* **Re-running the orchestrator to build `t9`** — it rebuilds the training table, and ADR 0036 §5b established
  that polars streaming is non-deterministic in its emitted KEY SET, so a rebuild risks a different row set.
  `t9` must reuse the `t8` tables and re-run only the train step.

## 7. Consequences, and what is deliberately still open

* **S2 is NOT closed and its gate is NOT met.** Capacity alone closes ~⅓ of the Wooddens GAP; no configuration
  measured so far satisfies all four criteria (`emu_r`, `sd_ratio`, pooled marginal intact, no `r_center`
  regression). The QRF × capacity matrix is in flight (jobs 1644614 QRF at baseline, 1644615 QRF × `b6x2M`,
  1644120 `b24x500k`, 1644436 `b40x500k`).
* **The production enablement decision is DEFERRED to a follow-up ADR**, on purpose. Recording "which lever we
  shipped" before the matrix completes is precisely the ADR-0033 failure this line has now made twice. All
  three levers are implemented, individually switchable, and separately measurable — that is this ADR's
  deliverable, not a chosen configuration.
* **No integration point with M is open yet.** The count `.drf` is unaffected; the copula changes are all
  opt-in and default-identical, so M's pinned artifacts keep working untouched. M re-pins deliberately only
  once a `t9` artifact exists.
* **A measurement lesson to carry forward:** judge this emulator's conditional fidelity on `sd(pred)/sd(Y1)`
  and the `Y1~pred` slope, never on pooled marginals alone.
