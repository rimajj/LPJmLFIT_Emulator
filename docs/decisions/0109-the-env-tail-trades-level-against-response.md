# ADR 0109 — the environmental tail trades LEVEL against RESPONSE; making it transient buys the response back, and the flip criterion was mis-specified

- **Status:** accepted (line S, 2026-08-06)
- **Decision in one line:** **the transient moisture tail is NOT flipped to the default.** It stays opt-in
  (`ENV_WINDOW` unset, `live_flux_cond_env` the shipped policy), because ADR 0108 §8's pre-registered
  criterion (a) fails as written and criterion (b) was never run. **And** the arm produced a finding that is
  more important than the flip: the environmental tail itself is a **level-vs-response trade**, which was
  invisible until a response statistic existed.
- **Related:** ADR 0108 (the transient tail + the pre-registered criterion), ADR 0037/0038 (which introduced
  and recommended the tail on level evidence), ADR 0106 (the acceptance criterion; the climate-change clause
  is binding), ADR 0105 §D1 (never publish a recommendation from an arm you have labelled confounded),
  ADR 0033 (do not credit a basis or population change to conditioning).

## 1. The measurement

Job **1718904** built the 8-column base once and appended both tails to it; job **1719206** scored them.
`scripts/diagnose_moisture_arm_response.py` **checks the pairing** rather than assuming it, and here the
pairing is total: the `_t9` base `Xc.f64` is **SHA-256 bit-identical** to the shipped `_t8` base
(`fc8d619edd6cd06e…`), and `cells.i64` / `scenario.i64` / every `Y_*` match exactly. So all three arms below
are on **the same 42 227 077 rows**, and the ADR-0036 §5b streaming-key-set nondeterminism did not fire.

52 074 cells with ≥30 stems in **both** scenarios, K-fold-**by-cell** OOS. `slope` = per-cell
`D_pred = median(ssp370) − median(historic)` regressed on `D_truth` through the origin (1.0 = right amount,
0 = no response). `within 10 %` = share of cells whose historic median is within 10 % of the C's.

| axis | | **8-col** (`_t8`, what M pins) | **14-col FROZEN tail** (`_t9env`) | **14-col TRANSIENT tail** (`_t9envT`) |
|---|---|---|---|---|
| SLA | slope | +0.851 | +0.396 | **+0.752** |
| | within 10 % | 70.7 % | **74.2 %** | 73.6 % |
| Wooddens | slope | +0.346 | +0.254 | **+0.332** |
| | within 10 % | 71.4 % | **74.0 %** | 73.8 % |
| D95max | slope | +0.163 | +0.145 | **+0.172** |
| | within 10 % | 28.0 % | **33.1 %** | 32.4 % |
| minwscal | slope | +0.689 | +0.609 | **+0.706** |
| | within 10 % | 62.1 % | **66.1 %** | 65.3 % |

Sign agreement moves the same way as the slope on all four axes (static → transient: 68.4→71.6, 59.7→61.3,
56.0→57.4, 60.4→62.5 %). The mean response *magnitude* is the sharpest single number: on `Wooddens` the truth's
mean `D` is **+2406**, the frozen tail predicts **+1529**, the transient tail **+2402**.

## 2. Finding 1 — the tail buys LEVEL and costs RESPONSE, on all four axes

Going from 8 columns to 14 with a **frozen** tail *raises* the per-cell level agreement by **+3.5 / +2.6 /
+5.1 / +4.0** percentage points of cells and *lowers* the response slope on **all four** axes
(0.851→0.396, 0.346→0.254, 0.163→0.145, 0.689→0.609).

This is a coherent mechanism, not noise: six per-cell constants are a near-unique **spatial address**. They let
the marginal forests locate a cell and reproduce its present-day distribution better, while making the fit
*less* dependent on the columns that actually move with time — so the same change that improves the level
degrades the response. The `slow-drf-pipeline` skill already carries the question "is it a response, or a
spatial ADDRESS?" (ADR 0040's ablation controls); this is that question answered on the response statistic
rather than on skill.

⚠ **ADR 0037/0038 recommended this tail on level evidence** (+0.011 SLA / +0.025 Wooddens / +0.042 D95max
attainable per-cell skill, and an environment-only predictor beating the eight production columns on
`Wooddens`). Every one of those numbers stands. What was missing is that **no response statistic existed at
the time**, so a change that improved the published metric while degrading the binding one could not be seen.
That is the lesson, not a reversal: the tail was never wrong, the metric panel was incomplete.

## 3. Finding 2 — making the tail transient buys the response back at the same level

Frozen → transient improves the slope on **all four** axes (+0.356 / +0.079 / +0.028 / +0.097) and sign
agreement on all four, at a level cost of **0.2–0.8 percentage points** of cells (median relative error worse
by 0.0004–0.0011). On `D95max` — the worst axis against ADR 0106, and the rooting-depth trait where a moisture
climatology is most physically motivated — the transient tail has the **best slope of all three arms**.

So ADR 0108's mechanism is confirmed on its own terms: the frozen channel was carrying a cost, and unfreezing
it recovers most of it. The recovery is **not complete** — 0.752 vs the 8-column 0.851 on SLA — so the
address effect is reduced, not eliminated.

## 4. The decision: NO FLIP, and why the criterion is not being bent

ADR 0108 §8 pre-registered: flip when **(a)** the paired OOS trait scores of `_t9envT` are *not worse* than
`_t9env` on any of the four production axes, **and (b)** a coupled five-cell screen shows a non-zero
historic→ssp370 trait-median response where the C has one.

- **(a) FAILS as written.** `D95max`'s pooled OOS `nqrmse` is **0.0120** vs the control's **0.0090**, and the
  per-cell level is worse on all four axes (by 0.2–0.8 pp of cells). The margins are small, and I believe the
  response gain outweighs them — **but that belief is exactly what a pre-registered criterion exists to
  overrule** (ADR 0105 §D1). It is not re-read after seeing the numbers.
- **(b) WAS NEVER RUN.** So the flip is blocked regardless of how (a) is read. Nothing here needs adjudication.

⇒ `ENV_WINDOW` stays unset by default, `live_flux_cond_env` stays the shipped policy, and
`recruit_copula_global_pooled_w20_t9envT.rcop` (127 962 917 B, 14 conditioning columns, `env_basis
transient_w20`) is available but **not pinned**. Line M's `_t8` pin is untouched and nothing M runs changes.

## 5. Finding 3 — the criterion itself was mis-specified, and that is recorded, not retro-fixed

Criterion (a) gates on **trait scores**, i.e. level. ADR 0106 makes the **response** the binding clause. So the
criterion I registered could reject a change that improves the binding quantity because it costs 0.4 pp on the
non-binding one — which is precisely what happened. That is a defect in the criterion.

**It is not being edited.** Rewriting a criterion after seeing the arm it was written for is the ADR-0104 error
in a new costume. Instead: a **correctly specified** criterion is registered here for the *next* decision, to
be judged on a *new* arm, and the mis-specification is the finding.

**Registered now, for line S or whoever runs the coupled screen next.** Flip the transient tail to the default
when all three hold:

1. **Response, primary:** the per-cell response slope of the candidate is ≥ the incumbent's on **all four**
   production axes, and strictly greater on at least two. *(Currently satisfied: +0.356/+0.079/+0.028/+0.097.)*
2. **Level, as a guardrail with a stated band:** per-cell within-10 % share drops by **no more than 1.0
   percentage point** on any axis versus the incumbent, and pooled `nqrmse` by no more than **0.005** absolute.
   *(Currently: level −0.2…−0.8 pp ✅; `nqrmse` `D95max` +0.0030 ✅, `agb` +0.0690 ✗ — but `agb` is a
   DIAGNOSTIC struct axis, never in the `.rcop`, so it is reported and not gating. Say that out loud rather
   than quietly excluding it.)*
3. **Coupled, unmeasured:** a coupled screen shows a non-zero trait-median response where the C has one, on
   the patch **ensemble** (not the modal patch — ADR 0105 §2) and against a **matched constant-forcing
   control** re-run in the same generation and measured past the transient (ADR 0048).

Clause 3 is the whole remaining blocker, and it is the same blocker every response claim on this line has had.

## 6. Caveats, stated

- **Offline.** The conditioning is fed the C's own features and the C's own rows. ADR 0105 §5 measured the
  *coupled* residual as dominated by F's canopy diverging from the C's, so **an offline slope is an upper bound
  on what the coupled model will show.** No coupled claim is made here.
- **Level and response are measured on medians.** Per-cell KS / full-distribution agreement is not re-measured
  in this arm; `nqrmse` is a pooled-quantile statistic and the skill already records that it is not a
  substitute for pooled KS.
- **The 10 % bands are the LITERAL 10 %.** ADR 0106's stated tolerance is max(10 %, the original's own two-run
  spread in that cell), and the per-cell two-run spread is not available here (it needs the seed2 companion,
  ADR 0030). Every "within 10 %" number above is therefore a **screen**, not the acceptance verdict — and
  since the tolerance can only widen, the shares quoted are lower bounds.
- **`STEM_CAP=400`** — a patch-year cluster subsample. Fine for a per-cell median, weaker for a tail quantile.
- `D95max` at **28–33 %** of cells within 10 % is the largest measured trait-side gap against ADR 0106, on all
  three arms. The transient tail moves it a little; it does not solve it.
