# ADR 0096 — the program becomes parallel method arms on one yardstick, with response-identifying data first

* **Status:** **accepted** — owner instruction, 2026-10-08.
* **Date:** 2026-10-08
* **Line:** cross-cutting / integrator (block 0090–0099)
* **Supersedes:** **ADR 0093's error-attribution ladder as the ORDER OF WORK** (`EXECUTION_PLAN.md` revision 1,
  2026-08-07, `git show a0f2cbba:EXECUTION_PLAN.md`). The ladder's findings and its isolation principle stand;
  only the sequencing is replaced. Also supersedes **ADR 0093 §4's "the patch cut is LAST"** speed ordering, which
  ADR 0086's measurement had already inverted without the plan being updated.
* **Unchanged and still binding:** ADR 0094 (speed is goal #2), ADR 0106 (the acceptance criterion), ADR 0107
  (no CO2 response).
* **Basis:** `docs/review_comparison.md` (this project vs 115 studies of the systematic review at
  `~/dgvm-review-corpus/`, with quotes and line numbers), and the project's own records cited below.
* **Consumes:** `EXECUTION_PLAN.md` revision 2 is the executable form.

## Owner instruction, verbatim (2026-10-08)

> *"based on the findings of this project so far and the findings in the review, update this projects plan. the
> goal stays the same, upate the plan on how to get there if necessary. try all promising methods"*

Preceded the same day by the owner's request for the comparison (`docs/review_comparison.md`), and by the
standing Germany instruction (2026-10-01): *"I want you to try out all the most promising designs in parallel"*.

## Context — what the ladder established (2026-08-07 → 2026-10-07)

* **Rung 1 (ADR 0174):** the learned demography passes on level and fails the response **on sign** when free
  running (+0.707 → −0.226), by rectification (ADR 0113–0116). One-step R² 0.982 against a persistence null of
  0.962.
* **Rung 2 (ADR 0175–0189, 0240–0245):** a count target cannot carry a gross mortality budget (ADR 0241); the
  original's per-tree hazard applied as a rate meets the criterion as a ceiling (ADR 0242); on the emulator's own
  inputs it delivers 0.78 of the mortality flux (ADR 0243).
* **Rung 3 (ADR 0125–0139):** the re-implemented physics grows 1.6–4× too fast at three of five cells; its GPP
  warming response is 8 % of the original's at Hainich and the wrong sign at the Sahel (ADR 0128); the shortlist
  of photosynthesis causes is exhausted (ADR 0139).
* **Rung 5:** the emulator is 4.62× slower than the original (ADR 0084); no speed change landed; at ~500 patches
  the original costs 7.06 core-s per cell-year, 99.9 % of it the patch ensemble, while atmosphere-facing fluxes
  converge within 1.7–6.6 % at one patch (ADR 0086); the original's demography is 0.4–1.1 % of its runtime
  (ADR 0312).
* **Line X (ADR 0310–0312, Germany build):** the warming response is confounded with place (76.4 % of a cell's
  warming is predictable from its baseline climate; ~161 effective tiles); in Germany the usable years carry
  almost no scenario contrast; a cell-level LSTM holds 0.79–0.91 of held-out cells on an unseen climate model,
  per-tree boosted trees 0.34–0.46, nearly matched by their climate-blind twin.

## Context — what the literature adds (`docs/review_comparison.md`)

* A tree ensemble trained one step ahead drifts; networks trained on their own rollouts do not (R00067:
  "XGB specifically drifts at long lead times", L1225; R00593: stable 4-yr free run after a 4 → 8-step rollout
  curriculum). Fitting on the free-running trajectory (R00661 L997-1002) and a signed zero-sum loss (R01133
  L556-562) are the demography-emulator precedents. **None was tried here.**
* Present-day fidelity does not imply the warming response (R00289); stylised factorial training does not
  transfer to real scenarios (R00430 L1096-1100); realistic-pattern contrasts partly separate response from
  place (R00013/R01025).
* Large speed-ups come from learning the expensive step or solver (R02497, R00568, R00067), not from
  re-implementing it; a re-implementation need not be slower than the original (R00975).
* Learned rates with host-kept pools is the conservation consensus (R00342, R00278, R00532); a learned memory
  replacing a pool loses the budget (R00755).
* None of the 7 full emulators tests out-of-distribution climate or runs coupled; no published emulator
  covers tree-count/trait distributions — this project's target has no precedent, so no single published
  design can be adopted wholesale.

## Decision

1. **Data that identify the response come first, and in parallel with everything else** (Track D): a
   constant-climate control of the original; a 3rd and 4th independent member with daily outputs; a fixed
   ~1 000-cell global stratified panel; a transient climate-contrast ensemble built from **real** change
   patterns (swapped between climate models, scaled ×0.5 / ×1.5, ×1.5 and one climate model held out); and —
   pending the owner's yes — the Germany 2071–2100 re-run with the humidity setting corrected.
2. **One yardstick for every method** (Track Y): level, deattenuated response against the control, free-run
   stability incl. a within-training-period free run, speed, conservation — always beside persistence, the
   lookup null, the climate-blind twin, the frozen-climate control and the other-member ceiling.
3. **All promising methods run as arms** — annual: hybrid-with-the-original's-physics with mortality as a rate
   (A1), rollout-trained recurrent model (A2), dataset aggregation on the model's own free-run states (A3),
   free-run calibration / signed zero-sum loss (A4), the neural set model (A5), the per-tree NPP + loss model
   (A6), a direct non-recursive map as the benchmark (A7), probabilistic state transitions (A8); daily: the
   re-implemented physics made fast (F1), a learned daily water–carbon model with an explicit soil-water state
   (F2), few-patch fluxes (F3).
4. **Arms are dropped only at pre-registered decision points** (`EXECUTION_PLAN.md` §8); thresholds may be
   tightened before a run, never loosened.
5. **Patch reduction for the fluxes is a first-class speed lever**, ranked behind only the per-tree daily step.
6. **Coupling readiness gets its own gates**: a 300-year recycled-climate stability gate, a complete coupling
   interface (incl. soil respiration and fire), an equilibrium initialiser, and an online self-test before any
   online science.
7. **Open-ended fidelity hunts in the re-implemented physics pause until the daily-method decision point**,
   because a learned daily model may replace that path; F1 still must preserve fidelity.

## Consequences

* Lines S, M, E, O and X each receive an assignment block at the top of their `## NEXT` (written with this
  ADR). Lines S/M/E/O had been inactive since 2026-08-17/19.
* Compute added by Track D (derived): ~6 core-h per member for the control on the panel, ~80 per extra member,
  ~100 for the contrast ensemble at 25 patches; ~10⁴ core-h for the Germany re-run if approved.
* The global acceptance test is unchanged; no arm is called done on Germany, the panel or five cells.
* `~/.claude/CLAUDE.md` still states the old ordering ("the patch ensemble is the LAST lever"); the owner was
  told, and that file is the owner's to change.

## What is NOT decided here

* Which method wins — that is what the decision points are for.
* The Germany 2071–2100 re-run (owner decision, 2026-10-01).
* Any change to the acceptance criterion, the speed allowances or the CO2 rule.
