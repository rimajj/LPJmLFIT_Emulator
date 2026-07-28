---
status: "accepted"
date: 2026-07-28
deciders: "engineering agent on line S (full autonomy per STEERING_PROMPT.md). The measurement is a fact; the decision recorded here is to REVERSE ADR 0031's promotion of S3 and to re-baseline the S2 gate against the tree7 numbers, rather than let a conditioning change take credit for the population fix."
consulted: "the ADR-0030 gate re-run on the complete population (scripts/noise_floor_vs_emulator.py, job 1622436, chained afterok to the tree7 copula job 1622131), the K-fold-by-cell OOS trait eval (job 1622131 vs the tree5 baseline 1597648), ADR 0030 (the scoring method + the superseded headroom table), ADR 0031 (whose Consequences section made the prediction this falsifies), ADR 0025 (the copula's own composition caveat)"
informed: "lines/S/STATE.md (§Status trait table + milestones S2/S3), the emulator-validation-figures skill, line M (no artifact change — the t7 pair already published under ADR 0031), MEMORY.md"
---

# The truncated tree-PFT basis WAS the missing-composition defect: widening it improved per-cell trait skill on every axis, so the per-PFT/mixture copula (S3) goes back to being a fallback

> **Status.** `accepted`. This supersedes **ADR 0030's headroom table** (which ADR 0030 itself instructed to
> re-measure after a population change) and **falsifies the degradation prediction in ADR 0031's Consequences
> section**. No artifact, runtime or feature-contract change — this is a measurement plus a re-prioritization.

## What was predicted, and what was measured

ADR 0031 §Consequences predicted the trait fidelity would get *worse* in one specific way:

> "the tropical PFT's very different trait intervals make the pooled single-marginal copula a worse structural
> fit. This sharpens the S2-vs-S3 question rather than settling it: a per-PFT/mixture marginal (S3) is now the
> *leading* hypothesis for Wooddens, since a per-cell trait median is a composition statistic and
> `COPULA_COND_COLS` contains no composition term."

The ADR-0030 gate re-run on the complete population (job 1622436; **`seed1-basis` = 1.000 on all four axes**,
52 165 cells scored vs 36 228 before) measures the opposite. Each population is scored against its **own** floor
and attenuation-corrected ceiling, which is what makes these columns comparable across a population change
(ADR 0030 §4):

| axis | emu_r | floor (rel_Y) | ceiling | **GAP** | r_center | sd(pred)/sd(Y1) |
|---|---|---|---|---|---|---|
| SLA | 0.866 → **0.885** | 0.964 → 0.973 | 0.981 → 0.986 | +0.115 → **+0.101** | 0.883 → **0.898** | 0.946 → 0.911 |
| Wooddens | **0.567 → 0.807** | 0.694 → 0.937 | 0.794 → 0.965 | +0.226 → **+0.157** | 0.715 → **0.837** | **0.546 → 0.718** |
| D95max | 0.771 → **0.812** | 0.791 → 0.833 | 0.873 → 0.909 | +0.102 → **+0.098** | 0.883 → **0.893** | 0.732 → 0.742 |
| minwscal | **0.793 → 0.947** | 0.909 → 0.973 | 0.947 → 0.986 | +0.153 → **+0.039** | 0.838 → **0.960** | **0.736 → 0.970** |

Per-cell skill improved on **every** axis, and **most on the two that were worst**. minwscal is now *near
ceiling*. The pooled marginals improved too (K-fold OOS raw quantile RMSE 1.9–3.0× lower on all four axes — but
quote the raw numbers, not the `nqrmse` ratios, which are IQR-normalized and so partly reflect the population's
wider spread).

## Why — the mechanism, stated as the thing that was actually wrong

The "missing between-cell composition signal" diagnosis (ADR 0025's caveat, sharpened by ADR 0030's 0.55
dispersion ratio) was **largely an artifact of the truncated basis, not a structural limit of a pooled copula.**

A per-cell trait median is a composition statistic because FIT draws traits from per-PFT `[low, high]` intervals
(`new_tree.c:195-206`). Dropping ids 0 and 6 removed **the two PFTs whose composition is most predictable from
environment**: the tropical broadleaved evergreen occupies a climatically distinctive region (hot, wet,
frost-free — the only tree PFT whose establishment gate is unconditionally open there) and the larch the
extreme-continental Siberian zone. What remained was ids 1–5 competing in overlapping temperate/boreal envelopes,
where per-cell composition is genuinely weakly determined by the boundary features the copula conditions on. So
the truncation did not merely shrink the sample — **it selected precisely the sub-population where the
conditioning has least to say**, and the resulting low skill was read as evidence that a pooled marginal cannot
represent composition.

The corollary is the general lesson: **a fidelity metric measured on a silently biased sub-population can
misdiagnose the model class.** Two prior conclusions were drawn from that biased basis and are now withdrawn —
ADR 0030's "the copula regresses cells toward the global mean: missing between-cell composition signal", and
ADR 0031's promotion of S3.

## Decision

1. **S3 (per-PFT / mixture copula) returns to being a FALLBACK, not the leading hypothesis** — reversing
   ADR 0031. On the complete population the pooled marginal reaches `r_center` 0.837 (Wooddens) and 0.960
   (minwscal) with **no structural change**. Revisit S3 only if S2's conditioning stalls below ~0.75 dispersion
   on Wooddens.
2. **Re-baseline the S2 gate against the `tree7` numbers before starting S2.** S1b already closed **30 %** of
   the Wooddens GAP (0.226 → 0.157, gate target 50 %) and lifted `sd(pred)/sd(Y1)` 0.546 → **0.718** (target
   ≥0.75) *without touching the conditioning*. Measuring S2 against the old tree5 baseline would credit the
   conditioning change with the population fix. The honest remaining S2 target is the last ~20 % of the Wooddens
   GAP.
3. **Wooddens remains the only axis with material headroom** (+0.157, dispersion 0.718). minwscal (+0.039),
   D95max (+0.098) and SLA (+0.101) are at or near their attenuation-corrected ceilings with `r_center` ≈
   0.89–0.96; do not spend S2 effort on them, and treat any "improvement" there as noise unless it exceeds the
   0.01 `r_center` guard.
4. **ADR 0030's headroom table is superseded by the table above**, as ADR 0030 §3 required. Its *method* stands
   unchanged and is what made this comparison possible: same-population floor, `seed1-basis ≥ 0.99` gate,
   `√(rel_P·rel_Y)` ceiling, and dispersion reported alongside correlation.
5. **Every trait number published before 2026-07-28 is labelled with its population** (ids 1–5, 36 228 cells
   scored) rather than silently restated — the same rule ADR 0031 §5 set for the count numbers.

## Consequences

- **S2's scope shrinks and its gate gets harder to game.** One axis, ~20 % of a GAP, measured from a re-based
  starting point. That is a more honest and much smaller target than ADR 0031 implied.
- **No artifact or contract change.** The `t7` pair published under ADR 0031 is the artifact this was measured
  on; line M's pin is unaffected by this ADR.
- **The `tree5` cross-population row is retained as a control, not a result.** Its `seed1-basis` reads
  0.976 / 0.556 / 0.814 / **0.174**, so `noise_floor_vs_emulator.py`'s own ≥0.99 guard refuses it. Keeping it in
  the report is what makes the truncation's size visible instead of inferred.
- **A methodological warning for future population changes:** re-run the ADR-0030 gate *and* re-baseline any
  open milestone gate in the same pass. A population change moves floors, ceilings and metric normalizers at
  once, so a milestone gate written against the old basis silently changes difficulty.

## Alternatives considered

- **Keep S3 as the leading hypothesis anyway** (Wooddens still under-disperses at 0.718). Rejected as
  premature: the cheap environmental-conditioning route (S2) has not been tried on the corrected population, and
  the single strongest argument for S3 — the 0.55 dispersion ratio — was an artifact of the basis. Reach for
  per-PFT structure after conditioning fails, not before.
- **Declare the trait work finished.** Rejected: Wooddens' +0.157 GAP and 0.718 dispersion are real headroom on
  an axis that feeds dynamics (SLA and Wooddens are the two axes the coupled loop actually consumes).
- **Leave the S2 gate on its tree5 baseline.** Rejected — that is the "credit the wrong change" failure mode this
  ADR exists to prevent.
