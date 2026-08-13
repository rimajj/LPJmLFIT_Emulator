# 0180 — de-leaking `n_prev` multiplies the count model's climate response by 2.8× and still leaves it 7× short; the count is near-determined by the contemporaneous stand description

* Status: accepted
* Date: 2026-08-13
* Line: S (tier-3 block 0170–0189)
* **Tests the mechanism ADR 0179 §4 named as a hypothesis and deliberately did not act on.** Confirms it
  partially, and refutes the strong form. Withdraws nothing.
* Scope: 2 forests trained in one process on 7 593 478 systematically sampled rows of
  `slow_count_pooled_w20_t8`, production hyperparameters (150 trees, depth 16, min_leaf 20, subsample
  200 000, seed 1). 15 rung-2 cells, 12 with a FIT truth response.
* Probe: `scripts/slow_nprev_ablation_probe.jl` (job 1771616, 4 min). Output:
  `/p/tmp/jamirp/emulator_global/S_nprev_ablation.csv`.

---

## 1. The question

ADR 0179 measured the shipped count model's climate channel as structurally open (77 440 splits, 10.20 % of
all splits) and empirically flat (0.28 stems over the entire global range; 3.8 % of FIT's own warming response
over the operative per-cell excursion). It named a mechanism as a **hypothesis**: `n_prev` is FIT's own
previous-year count for the same `(Cell, Patch)` — the teacher-forcing leak of ADR 0112 — the persistence null
already scores R² 0.9622 on this target, and a target that is nearly determined before climate is consulted
leaves climate nothing to explain. ADR 0179 explicitly declined to promise that removing it would help.

This is that measurement, run before any global retrain is bought — the "price the retrain offline" rule
(ADR 0105).

## 2. Design: one variable

Two arms, trained **in the same process, on the same rows, with the same seed and hyperparameters**:

* **CTRL** — the table as it is.
* **ABL** — column 11 (`n_prev`) overwritten with its own sample mean, i.e. a constant.

`n_prev` is *neutralised in place rather than dropped* so that `p`, the column indices and `mtry`
(= `round(sqrt(p))` = 4) are identical between arms. A constant column can still be drawn as an mtry
candidate but can never win a split, so the only thing that changes is the information it carries. This is
the ADR 0126 §5 rule: name the switch, then ask what else the switch controls. Dropping the column would have
changed the candidate-draw arithmetic as well — as it happens `round(sqrt(14))` is also 4, but the
in-place form makes that a non-question instead of a coincidence to check.

The control is **retrained here rather than compared against the shipped artifact**, because the shipped one
saw all 121 495 658 rows while this arm sees a systematic sample; comparing across that difference would
confound the row set with the ablation (ADR 0048 §4: difference every arm against a matched control re-run in
the same generation).

**Two basis checks passed before any arm was read**, per `residual-diagnosis` §3:

* the sample reproduces the published persistence-null skill — **R² 0.9623** here against ADR 0112's
  **0.9622** on the full table;
* **CTRL reproduces the shipped artifact**: climate split share 10.10 % (shipped 10.20 %), holdout R² 0.9801
  (shipped OOS 0.9824), mean |Δ climate| 0.0836 stems (shipped 0.0676). So the retrained control is a
  faithful stand-in and the contrast is attributable to the ablation.

## 3. Result

| | CTRL | ABL | ABL/CTRL |
|---|---|---|---|
| holdout R² | 0.9801 | 0.9620 | 0.98 |
| holdout RMSE (stems) | 0.8284 | 1.1455 | 1.38 |
| split share `n_prev` | 10.77 % | 0.00 % | — |
| split share climate | 10.10 % | 9.87 % | 0.98 |
| pooled full-range PD amplitude, gdd5 | 0.5590 | 1.3192 | **2.36** |
| pooled full-range PD amplitude, joint | 0.5033 | 0.9363 | **1.86** |
| **mean |Δ climate|, operative excursion** | **0.0836** | **0.2381** | **2.85** |
| … as a fraction of FIT's own response | **4.7 %** | **13.5 %** | |
| sign agreement with FIT | 7 / 12 | 8 / 12 | |

Mean |FIT truth response| over the 12 scored cells is 1.7698 stems (script-computed, not read off a table —
ADR 0104).

**The effect is not a single draw.** Paired per cell on identical rows and seed, ABL's |Δ climate| exceeds
CTRL's at **13 of 15 cells**, median ratio **2.44** (range 0.42–5.12). The two exceptions (12235, 22732) are
the cells where CTRL's Δ was already at ±0.001–0.006 stems, i.e. below anything this probe resolves.

**The split share barely moves — 10.10 % → 9.87 % — while the effect nearly triples.** That is the direct
mechanistic confirmation of ADR 0179's reading: the climate splits were always there, and `n_prev` was
*muting* them. Removing it does not make the forest look at climate more often; it makes the leaf values
either side of the existing climate splits differentiate.

## 4. The sharper finding: the count is near-determined by the stand, not only by `n_prev`

**Without `n_prev` at all, holdout R² is 0.9620 — statistically indistinguishable from the persistence null's
0.9623.** The remaining 13 features reconstruct the count essentially as well as FIT's own lagged answer does.
That is not a small observation: it means removing the AR state does not de-leak the target, because six of the
head features (`hmean`, `hmax`, `agb`, `lai`, `fpc`, `age_mean`) are a description of the **same year's stand**,
and a stand of a given above-ground biomass, cover, height and age contains a nearly determined number of
stems above the 5 m emission cut. The count is close to an allometric consequence of the stand.

**Two things follow, and they must not be conflated.**

* **At training time this is a leak**, and it bounds what any conditioning feature can be fitted to carry:
  3.77 % of the target's variance is left for all 13 non-`n_prev` features to share once `n_prev` is known.
  This is why climate's fitted effect is small, and why de-leaking one feature recovers only a factor of ~3.
* **At runtime it is NOT a leak**, and this is the part that decides where the work goes. Those six features
  are computed from the emulator's *own* grown pools (`flux_feature_vector`, ADR 0023), not from FIT. So the
  ABL forest is a legitimate free-running model, and its 2.85× larger climate channel is a real candidate
  improvement rather than an artifact of a diagnostic. But it also means the coupled loop's warming response
  has to arrive **through F moving the stand** — the count model's own climate features are a small
  correction on top of a stand-to-count map. ADR 0178 measured that pathway as ~0.

⇒ [ASSUMPTION, falsifiable] The count model is conditioned on a near-sufficient description of its own answer,
so no reweighting of its existing feature set can produce FIT's warming response magnitude. Closing the
response requires either a target/feature construction in which climate is not residual to the stand, or the
response arriving through F's physics. The falsifier is a retrain on a target that is *not* a level given the
stand — and ADR 0115 already measured the obvious version of that (predict the increment) as making every
statistic worse, so the reformulation needs designing, not guessing.

## 5. Decision

1. **The pre-registered verdict is `H_nprev PARTIAL` and it is reported as such.** De-leaking `n_prev` is a
   real, paired, reproducible **2.85×** on the operative climate channel, taking it from 4.7 % to 13.5 % of
   FIT's own warming response, at a cost of 0.018 in R² (0.9801 → 0.9620). It is **not** a fix: ~7× short, and
   sign agreement moves only 7/12 → 8/12.
2. **Do not buy a global retrain on the strength of this alone.** A 2.85× on a channel that is 4.7 % of the
   target is not worth a two-artifact global regeneration by itself, and the sign result says the direction
   failure ADR 0177 found would survive it. Record the factor; do not promise the fix. (This is the
   ADR 0105 rule — a measured localisation is not a licence to recommend a value.)
3. **The next lever is the target construction, not the feature weighting**, per §4. That is the ADR 0112
   restart ADR 0178 §B2a pre-registered, now with a price attached to the cheapest version of it.
4. **No flag flips, no default changes, no artifact regeneration** in this ADR. Both arms are diagnostic
   forests written to `/p/tmp`; nothing shipped moved, and the two committed probes are new files.

## 6. Limitations, stated

* **One seed, one sample.** The 2.85× aggregate is a single fit pair; the paired 13/15 per-cell result is what
  carries it, not the aggregate (ADR 0101 §5). A seed sweep was not run — it would sharpen the factor, and the
  factor is not the number the decision turns on.
* **Sub-sampled table.** 7.6M of 121.5M rows (systematic random: one uniformly drawn row per block of 16,
  which is sequential I/O and cannot alias with the table's `(cell, scenario, year, patch)` ordering the way a
  fixed stride of 25 would). CTRL's agreement with the shipped artifact is the evidence this is adequate.
* **A partial dependence is a property of the fitted function**, not of a coupled trajectory. It is not a
  substitute for ADR 0178's arms; the value here is that two independent methods agree.
* **`co2` is not a gap** (ADR 0004/0107, standing). It has 0 splits by design.
* The three cells with no FIT truth (23318, 33335, 46336) are the ones ADR 0177 §C lost to the `ERROR043`
  duplicate-roster-key crash in the C hook — a known open interface defect owned by line M, not a new one.

* Related: ADR 0179 (the flat-channel measurement this tests the mechanism of), ADR 0178 (the frozen-climate
  control), ADR 0112 (the teacher-forcing critique and the persistence null), ADR 0115 (increment-target
  reformulation, already measured as worse), ADR 0023 (runtime/training conditioning consistency),
  ADR 0126 §5 (one-variable arms), ADR 0105 (price a retrain offline; no recommendation from a confounded arm).
