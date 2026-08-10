# ADR 0113 — arm A1: making the count feed itself destroys the WARMING RESPONSE while barely touching the level or the per-cell slope; and the per-cell response slope is now measured dead as a discriminator

- **Status:** accepted (line S, 2026-08-10)
- **Rung:** `EXECUTION_PLAN.md` **rung 1**, line S — arm **A1** (flux-forced, state-recursed), the control
  ADR 0112 identified as missing. Scored on ADR 0111's yardstick, no new model runs.
- **Related:** 0112 (the forcing-basis finding and the pre-registered predictions this tests), 0111 (the
  yardstick and the one-definition rule this enforces in a second place), 0102/0054 (the count recursion
  measured single-cell/coupled — this is the global statement, and it *disagrees* with the drift narrative),
  0105 (offline is an upper bound on coupled), 0106 (the acceptance criterion).
- **Artefacts:** `scripts/rung1_count_recursion_arm.jl` (job **1747655**, 4 min on 48 cpus),
  `scripts/attach_count_table_keys.py` (job 1747642, the proven keys), `scripts/diagnose_truth_yardstick.py`
  (jobs **1747656** and **1747662** after the fix in §5), arm dir
  `/p/tmp/jamirp/emulator_global/rung1_count_arm_a1`, summary
  `/p/tmp/jamirp/emulator_global/rung1_yardstick_arms.csv`.
- **Coverage:** all **121 495 658** rows of the frozen pooled count table (100 % keyed), scored on ADR 0111's
  paired **51 767 cells**, both scenarios and the response between them.

---

## 1. What A1 is

Year *t*'s own count prediction is fed in as year *t+1*'s `n_prev`, per `(Cell, Patch)` chain of consecutive
years. Nothing else changes: the four flux features, the six other roster-state features, the static boundary,
the K-fold-by-cell split, the forest hyper-parameters and `seed = 1` are all identical to the published
evaluation, so **A1 − A0 is the recursion and nothing else**. Chains are the real ones (keys proved row-for-row,
ADR 0112 §5); median chain length **19** years, maximum **80**; ~3.3 M chains.

⚠ **A1 is a STRICT LOWER BOUND on free-running error.** In a real rollout `agb`/`lai`/`fpc`/`hmean`/`hmax`/
`age_mean` would also be the emulator's own; here they stay at LPJmL-FIT's values.

## 2. The result — three arms, one basis, one process

| statistic | A0 one-step, C-forced | A0-null persistence | **A1 state-recursed** |
|---|---|---|---|
| out-of-sample R² on `n_living` | 0.9824 | 0.9622 | **0.9182** |
| per-cell response slope vs seed 1 | 0.958 | 0.980 | **0.928** |
| deattenuated (1 seed / 2 seed) | 1.056 / **1.006** | 1.080 / **1.029** | 1.022 / **0.976** |
| **aggregate area-weighted response ratio** | **+0.707** | +0.685 | **−0.226** |
| band ratio tropical | −0.51 | −0.43 | **−3.62** |
| band ratio subtropical | +3.41 | +2.83 | **+6.50** |
| band ratio temperate | +0.93 | +0.95 | **+0.45** |
| band ratio boreal | +1.07 | +0.95 | **+0.70** |

**(a) Prediction 2 of ADR 0112 is CONFIRMED:** A1's R² (0.9182) falls well below the persistence null's
(0.9622). Feeding the model its own answer costs more accuracy than the learned model buys: run forward, it is
less accurate than a predictor that is simply handed LPJmL-FIT's own previous-year count every year and does
nothing with it.

**(b) Prediction 1 of ADR 0112 is REFUTED, and that is the sharper finding.** The per-cell response slope was
predicted to fall materially; it moved 0.958 → 0.928 raw, 1.006 → 0.976 deattenuated. Across three arms whose
actual skill spans R² 0.982 → 0.962 → 0.918 and whose global response ratio spans **+0.707 → +0.685 → −0.226**,
the deattenuated per-cell slope stays inside **0.976–1.029**. ⇒ **the per-cell deattenuated count response
slope is not a usable discriminator and is retired for counts.** ADR 0112 §3b measured that it cannot separate
the model from a null; this measures that it cannot separate a model whose global response ratio is **+0.707**
from one whose global response ratio is **−0.226**. Two independent demonstrations ⇒ a property of the
statistic, not a coincidence.

**(c) The response collapses and reverses.** The one statistic that does discriminate — the area-weighted
aggregate ratio — goes from +0.707 to **−0.226**: run forward, the emulator's global stem-count response to
warming has the **wrong sign**. Every band degrades (temperate 0.93 → 0.45, boreal 1.07 → 0.70) and the
tropical error grows sevenfold (−0.51 → −3.62). The subtropical over-response nearly doubles (+3.41 → +6.50).

**(d) But the LEVEL does not blow up — the recursion is stable.** Error against FIT as a function of lead time
(years since the chain was last handed FIT's own count; step 1 is identical to A0 by construction):

| lead (yr) | 1 | 2 | 5 | 12 | 20 | 40 | 80 |
|---|---|---|---|---|---|---|---|
| A1 RMSE (stems/patch) | 0.596 | 0.806 | 1.109 | 1.413 | 1.520 | 1.640 | **1.717** |
| A0 RMSE, same rows | 0.596 | 0.617 | 0.641 | 0.686 | 0.703 | 0.717 | 0.735 |
| A1 bias | −0.014 | −0.016 | −0.029 | +0.041 | +0.155 | +0.131 | +0.082 |

RMSE grows 2.4× in the first dozen years and then **saturates**; the bias stays under **+0.16 stems/patch** on
a mean of 8.28 (**< 2 %**) and does not grow after year 20. ⇒ **the free-running count is bounded and
essentially unbiased in the mean; what it loses is the between-cell and between-scenario *information*.** This
contradicts the natural reading of ADR 0102/0054 ("the count recursion drifts, it needs a level anchor") at
global scale: on 51 767 cells × 25 patches there is no level runaway to anchor. That is consistent with
ADR 0105, which found the level defect 4× smaller on the patch ensemble and the anchor actively harmful.

**(e) Prediction 3 of ADR 0112 is VACUOUS as posed, and the reason matters.** It said the trait panel would
move less than the count panel between A0 and A1. It moves **not at all** — the copula's conditioning is four
flux columns plus static climate and constant CO₂, with **no roster-state and no lagged-trait input**, so a
state recursion cannot reach it. ⇒ **an offline S-only arm cannot measure recursion damage to the trait axes at
all.** The trait axes' free-running error is inherited entirely from the fast core's flux error, which makes it
rung 3/4 work (line M), not rung 1's. Rung 1 can still score arms C and D on the trait axes, but only on the
**one-step, C-forced** basis, and every such verdict must say so.

## 3. What this means for the acceptance criterion

ADR 0106 requires counts, trait distributions and trait medians within 10 % (or the reference model's own
two-run spread), *especially under climate change*, on all 54 020 cells. On counts:

- **the level is fine** even free-running (bias < 2 %, saturating), so the count *level* is not the blocker;
- **the response is the blocker, and it is worse than any published number suggested** — sign-flipped globally
  once the count feeds itself, against a target of 1.0;
- and because A1 is a **lower bound**, the coupled model can only be worse (ADR 0105 §5).

## 4. Decision

1. **For counts, the primary response statistic is the area-weighted aggregate ratio and its latitude bands.**
   The per-cell deattenuated slope is reported as a secondary *with the null beside it*, or not at all. It is
   never used to support a claim about the emulator's response.
2. **Every count-response claim is stated with its forcing label** (ADR 0112 §4a). "+0.707" is a one-step number;
   "−0.226" is the state-recursed one; free-running is unmeasured and can only be worse than −0.226.
3. **`trait_mortality`'s pre-registered flip criterion (ADR 0109 / rung 1) keeps its Wooddens-response
   statistic but must be decided on the ONE-STEP trait basis**, because §2e shows a state recursion cannot
   reach the trait conditioning. The criterion text is not re-read or weakened — only its basis is now named,
   which ADR 0112 §4b had left ambiguous when it said "decided against A1".
4. **Do not build a "level anchor" for the global count recursion.** §2d measures no runaway to anchor, and
   ADR 0105 already measured the anchor harmful on the patch ensemble. If a future arm shows a level runaway,
   it must show it on this lead-time table first.

## 5. A second aggregate-ratio definition was still live, and it changed a number by 4×

ADR 0111 §5b closed the two-definitions trap on the trait side ("keep exactly ONE definition, area-weighted").
The **count** path still recorded and printed the *unweighted* `mean(D_pred)/mean(D_truth)` as its
`aggregate_response_ratio`. On A0 the two nearly agree (0.691 unweighted vs 0.71 area-weighted) so nothing was
visibly wrong for months; **on A1 they disagree by a factor of four — −0.93 unweighted vs −0.23
area-weighted** — because an unweighted mean-ratio is dominated by cells whose own denominator is near zero.
Fixed: `score_counts` now computes and prints the area-weighted GLOBAL band ratio, the same quantity as the
trait path, and `n/d` below S/N 3.

⚠ **Two records carry the mislabelled number, and both are corrected here rather than edited** (guardrail 1 —
an accepted ADR is superseded, never rewritten):
- **ADR 0111 §4b**'s "area-mean **0.691×**" is the *unweighted* number mislabelled as area-weighted; the
  area-weighted value is **0.707**. The conclusion it supported — counts get the per-cell pattern right and
  under-shoot the total — is unchanged.
- **ADR 0112 §3**'s row "aggregate area-weighted response ratio | 0.691 | 0.536" is the *unweighted* pair. The
  area-weighted pair is **0.707** (production) and **0.685** (null). This makes ADR 0112 §3d *stronger*, not
  weaker: on the one definition that survives, the null and the production model are **0.685 vs 0.707** — the
  gap the learned model opens on the aggregate response is far narrower than the unweighted numbers suggested,
  so "the model recovers about a third of the null's shortfall" should read "the model is 2 pp of ratio better
  than the null". The discriminating power of the aggregate ratio is demonstrated by **A1** (−0.226), not by
  the model-vs-null gap.

## 6. What A1 does not settle

- It is offline and a lower bound; it says nothing about the coupled model beyond bounding it from above.
- It recurses **one** feature. A full roster rollout (all seven state features) is line M's harness, and it may
  behave differently — in particular `age_mean` feeding itself is a second recursion with its own dynamics.
- The saturating RMSE could be the model regressing toward a conditional mean rather than tracking the truth;
  the diagnostic that would separate those is the *variance* of A1's prediction against FIT's, per lead time,
  which is not in this run.
