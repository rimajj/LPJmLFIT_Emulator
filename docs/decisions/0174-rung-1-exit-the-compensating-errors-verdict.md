# 0174 — RUNG 1 EXIT: the score against the rung-0 floor, and the compensating-errors verdict the gate asks for — three cancelling channels are now named and sized, and the finding is that Component S's demography reproduces FIT's LEVEL and does not reproduce its RESPONSE

* Status: accepted
* Date: 2026-08-12
* Line: S (tier-3 block 0170–0189)
* Supersedes: nothing. This is the **exit statement for rung 1** of `EXECUTION_PLAN.md` §2/§3, whose gate reads
  *"rung-1 score reported **against the rung-0 noise floor**, with the compensating-errors verdict stated"* —
  the second clause had no answer anywhere in the repo. Synthesises ADR 0111 (rung 0), 0112 (teacher-forcing),
  0113–0116 (the recursion), 0118 + 0124 (arm C), 0172 (the recruit arm at five cells), 0173 (arm D). Records
  what rung 1 hands to rung 2/3/4 and what it CANNOT decide.
* Reproduce: no new computation. Every number below is a committed fixture or a cited ADR, and the two
  arithmetic operations performed here (dividing a rung-1 error by the rung-0 floor; comparing a model's
  statistic with its null's) are stated inline. Rung-0 floor:
  `test/testitems/references/S_truth_yardstick_summary.csv` (272 rows).

---

## 0. Why this ADR exists at all

Rung 1's entry and exit are defined in `EXECUTION_PLAN.md`; the exit gate has two clauses, and the repo had
satisfied only the first. Ten ADRs (0111–0116, 0118, 0124, 0172, 0173) each measured a piece, and each was
correct on its own basis, but **no document stated the verdict the gate names** — so rung 1 has been
effectively open while behaving as if it were closed, and downstream lines have been quoting individual
pieces without the synthesis. This ADR states it. It adds no measurement; the discipline it applies is
ADR 0060's (say what the reference basis is, and put the numbers side by side rather than substituting one).

---

## 1. The rung-0 floor, as the yardstick clause requires

From `S_truth_yardstick_summary.csv`, the C's own two-run spread (median relative difference between seeds,
`capped400` basis, per-patch quantities), and the reliability `λ = Var(true)/(Var(true)+Var(noise))` the
deattenuation uses:

| quantity | 2-run spread, ALL cells | 2-run spread, `<2 stems/patch` | λ (1 seed) | λ (2 seeds) |
|---|---|---|---|---|
| stems per patch | **6.77 %** | **16.63 %** | 0.908 | 0.952 |
| AGB per patch | 10.16 % | 25.29 % | 0.616 | 0.762 |
| vegC per patch | 9.45 % | 24.81 % | 0.635 | 0.777 |
| SLA median | 2.53 % | 3.83 % | 0.645 | 0.784 |
| Wooddens median | 3.84 % | 7.04 % | 0.510 | 0.676 |
| D95max median | — | — | **0.198** | 0.330 |
| minwscal median | — | — | 0.640 | 0.780 |

Two properties of this floor govern everything below. **(a) It is stratified, and the strata are not
comparable:** the `<2 stems/patch` class (6 834 cells) has 2.5× the spread of the global median on counts and
2.5× on carbon, so ADR 0106's `max(10 %, the model's own two-run spread)` is a *per-stratum* tolerance, not
one number. **(b) D95max's λ is 0.198**, i.e. ~80 % of the between-cell variance in the single-seed truth for
that axis is noise — which is why a raw response slope on it is uninterpretable and why the deattenuated
panel exists.

---

## 2. The rung-1 score against that floor

### 2a. LEVEL — inside the floor, on every axis that has one

The published global panel (ADR 0108/0111 basis, corrected in ADR 0111 §5): deattenuated per-cell response
slopes **SLA 1.28 · Wooddens 0.66 · D95max 0.73 · minwscal 1.06** (2-seed), and the count level's free-running
bias never exceeds **+0.16 stems/patch on a mean of 8.28 (< 2 %)**, flat after year 20, over 80 years
(ADR 0113 §2). Against a count floor of 6.77 % (ALL) / 16.63 % (`<2`), a < 2 % level bias is **comfortably
inside the C's own noise** — including in the worst stratum.

**⇒ On the LEVEL, rung 1 passes, and it passes by a margin.** That is a real result and it should be stated
plainly: given FIT's own per-tree fluxes, the learned demography reproduces FIT's standing stem count and
trait medians to within the reference model's own reproducibility.

### 2b. RESPONSE — outside the floor, and the failure is not a magnitude but a SIGN

The area-weighted global count response ratio is **+0.707 one-step** and **−0.226 free-running** (ADR 0113 §5,
which corrects ADR 0111 §4b's unweighted 0.691). A wrong sign is not a tolerance question; no noise floor
admits it. The decay is measured: right in every latitude band at one step (0.90–1.07), then temperate
1.07 → 0.95 (5 yr) → 0.77 (10) → 0.59 (20) → 0.45 (80), the tropics inverting (ADR 0114 §2).

**⇒ On the RESPONSE, rung 1 fails**, and the useful form of the statement is a **validity horizon**: the count
channel's response is faithful for ~3 years, indistinguishable from the one-step arm up to ~3 yr, and inverted
by 40 (ADR 0114).

### 2c. The two clauses are about DIFFERENT mechanisms, which is the whole point of the ladder

ADR 0113's central measurement is that free-running **destroys the response and leaves the level alone**. So
2a and 2b are not "mostly right with a caveat" — they are two independent verdicts, and a summary that
averages them (or reports only the level) misrepresents the component. Every rung-1 number quoted downstream
must carry which of the two it is.

---

## 3. THE COMPENSATING-ERRORS VERDICT — the clause that had no answer

**Verdict: YES. Component S's apparent skill is materially assisted by errors that cancel, and three distinct
cancelling channels are now identified, each with a measurement.** Stated in the order of how much they
inflate the published picture.

### 3a. Channel 1 — TEACHER FORCING: a memoryless null matches the model on every response statistic

All 15 features of the production count model are built from FIT's own output for that very
`(Cell, Patch, Year)`, including `n_prev` — FIT's own previous-year stem count — and K-fold **by cell** holds
out space, not time (ADR 0112). The null that predicts `n_prev` and learns nothing scores:

| statistic | production model | the null | verdict |
|---|---|---|---|
| R² | 0.9824 | 0.9622 | the model wins on **accuracy** |
| per-cell response slope | 0.958 | 0.980 | **null wins** |
| deattenuated slope | 1.006 | 1.029 | **null wins** |
| area-weighted aggregate response ratio | 0.707 | 0.685 | indistinguishable |
| regional band pattern incl. the wrong-signed tropics | reproduced | **also reproduced** | no discrimination |

**⇒ the response half of the published panel is not evidence about the demography at all.** The error that
cancels is: the feature carrying last year's truth cancels whatever the learned mapping gets wrong about how
the stand evolves. Remove it (arm A1) and the response inverts.

### 3b. Channel 2 — A RECTIFIED LOSS-SIDE ERROR that manufactures a spurious POSITIVE response

The recursion reproduces **86.7 %** of a large FIT decline but **96.2 %** of a large increase (ADR 0116 §4).
FIT's global count response is a net **loss**, so a one-sided under-following of losses does not average out —
it **rectifies** into a systematic positive drift of **+0.155 stems/patch, saturating**, which is *the same
size as FIT's entire global count response* (≈ −0.14 stems/patch, ADR 0114 §1). That drift **is** ADR 0113's
wrong-signed aggregate response, mechanistically explained.

**⇒ the compensation here is between the level and the response**: the drift is small enough to stay inside
the level tolerance (§2a) while being large enough to consume the entire response signal. A component can pass
a level gate *because* of the error that fails its response gate. This is the single most important sentence
in this ADR.

And it is why ADR 0116 §5's pre-registered arm requires decile-1 excess drift to fall **without decile 10's
magnitude rising** — an aggregate ratio alone cannot distinguish a real fix from a compensating positive bias.

### 3c. Channel 3 — A SURVIVOR-TRAINED MARGINAL that already contains the process an operator would add

The recruit copula's marginals are fitted on FIT's **survivors**, so they already carry the selection that
`trait_mortality` (arm C) proposes to add — **+12.18 % on Wooddens within a cell-PFT group, of which 0.56 does
not cancel in a response** (ADR 0118 §1/§2). The asymmetry is what makes it bite: the uniform-thinning null C0
is *unaffected*, because it is the trait-blind design the survivor marginal was matched to, so the bias lands
on the arm and not on its null — i.e. straight onto the headline `C1 − C0`. ADR 0025 §3 wrote its own expiry
condition (*"if trait-dependent mortality is ever added, this training target must change"*) and no ADR in the
0047 → 0049 → 0117 chain cited it.

**⇒ a double-counting compensation:** the learned distribution silently supplies a mechanism, so adding that
mechanism explicitly looks like an improvement while being partly a duplication.

### 3d. Two further cancellations, smaller but on the record

* **Pooling across disagreeing cells (ADR 0172 §3c).** Five cells spanning −1.9 to +3.6 ×FIT
  inverse-variance-pool to **−0.805 ×FIT with I² = 82 %**. A pooled mean over heterogeneous cells is a
  cancellation machine; ADR 0172's replacement flip condition therefore requires a **non-significant
  Cochran's Q** alongside the pooled mean, so cells cannot average to the right answer by cancelling.
* **A statistic without power reads as agreement (ADR 0113 §3, ADR 0173 §2b).** Three arms spanning R²
  0.982 → 0.962 → 0.918 and a response ratio spanning +0.707 → +0.685 → **−0.226** all score the per-cell
  deattenuated count slope between 0.976 and 1.029 — so that slope is retired as a discriminator. Independently,
  ADR 0093 §5.3's Beta figure sat **at its own one-sample statistic's noise floor** (0.0437–0.0476 against a
  simulated 0.0434–0.0475 at n = 150) and so could not have detected the misfit it was quoted as measuring.

---

## 4. What rung 1 hands upward, and what it cannot decide

**Hands to rung 2/3/4 (line M):**

1. **The response, entirely.** Rung 1 has established that the count response is a one-step property and that
   the offline component cannot carry it beyond ~3 years. Whether the *coupled* system can is rung 4's
   question and is not answerable here.
2. **The trait axes' free-running behaviour.** The trait sampler conditions on four flux columns + static
   climate + constant CO₂ — no roster state, no lagged trait — so **nothing an offline state recursion does
   can reach it** (ADR 0113 §2e). Trait free-running error is inherited from the fast core's fluxes ⇒ rung 3/4.
3. **`trait_mortality`'s flip**, whose coupled criterion M has already pre-registered (ADR 0124 §6), blocked on
   ADR 0049 item 4 — offline the operator has neither of FIT's stress integrals.
4. **`recruit_establishment`'s flip**, refused on a five-cell level effect (ADR 0172 §2) with a replacement
   response condition requiring ≥ 12 cells and a non-significant Q (ADR 0172 §5).

**Cannot decide, and must stop being described as an open S task:**

* **Arm D** — descoped, its motivating number refuted (ADR 0173).
* **The `n_elig = 0` recruit arm** — descoped offline; the persistent class is 1.4 % of runnable cells at a
  median of one stem per patch, inside the `<2 stems/patch` stratum where the C's own spread is 31.6 %
  (ADR 0172 §4). Measuring dice is not a measurement.
* **A level anchor for the global count recursion** — forbidden: ADR 0113 §2d measures no runaway and ADR 0105
  measured the anchor harmful. Any future proposal must refute ADR 0113's lead-time table first.
* **A variance-preserving or distribution-sampling count predictor** — forbidden: at lead 80 the recursion still
  carries `sd(pred)/sd(truth) = 0.904` and `corr = 0.940`, so it is not regressing to a conditional mean
  (ADR 0114 §1). Any such proposal must refute that first.

---

## 5. Decision

1. **RUNG 1 IS CLOSED**, with the two-part verdict of §2 (level: passes, inside the C's own two-run spread;
   response: fails, wrong-signed free-running, validity horizon ~3 years) and the compensating-errors verdict
   of §3 (yes — three named channels, sized).
2. **Every rung-1 number quoted anywhere must carry two labels**: *level or response*, and *one-step or
   free-running*. The four combinations have different verdicts and three of the four have been quoted
   interchangeably in this repo's own history.
3. **The compensating-errors verdict is a standing reading rule, not a historical note.** Before any future S
   arm is believed: name its null, check the null does not score the same (ADR 0112), and check whether the
   arm's advantage could be a duplication of something its training target already contains (ADR 0118).
4. **`EXECUTION_PLAN.md` needs three integration-point edits** (integrator-owned; raised in this line's STATE):
   strike rung-1 arm D (§ADR 0173); replace the superseded λ/slope pair at lines 105–106 (it prints
   Wooddens 0.63 / D95max 0.51, which are ADR 0111's **λ** values, not the deattenuated slopes — the corrected
   panel is SLA 1.28 / Wooddens 0.66 / D95max 0.73 / minwscal 1.06, and the same stale text is copied into
   three other lines' STATE files); and record rung 1's exit against this ADR.
5. **The determinism dividend's band-metric half stays OPEN and is the one genuinely unmeasured rung-1
   deliverable** (ADR 0173 §4). It is free, it is worth +2.9 to +14.4 pp of cells inside the 10 % band on
   ADR 0093's own claim, and it needs a *band* metric on per-cell aggregates rather than the per-cell KS the
   arm emitted here.

---

## 6. What is NOT claimed

* **Rung 1 closing is not the acceptance criterion.** ADR 0106 requires ≤ max(10 %, the C's own two-run
  spread) on counts **and** trait distributions **and** trait medians, on **all 54 020 tree-bearing cells**,
  in **both** scenarios, **and on the response between them** — and §2b is a failure of exactly the response
  clause, which the owner named as the binding constraint. Rung 1 closing means *the error has been
  attributed to this rung*, not that the emulator is finished. It is not.
* §3's three channels are the ones that have been *measured*. Their number is a lower bound, not a complete
  accounting, and §3d's two smaller ones are the kind that only became visible when a null was run.
* Nothing here re-opens CO₂: the emulator does not see CO₂ and must not respond to it (ADR 0004 + 0107); the
  scenario pair carries the CO₂-driven climate signal and FIT itself runs constant CO₂ for future runs on
  purpose.
* §2a's level pass is on the **one-step** basis for the trait axes and the **free-running** basis for the
  count level. Those are different bases and both are stated; they are not interchangeable.
