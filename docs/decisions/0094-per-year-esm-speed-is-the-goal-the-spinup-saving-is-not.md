# ADR 0094 — per-year ESM speed IS the goal; the spin-up saving is not

* **Status:** **accepted** — owner decision, 2026-08-07. Standing; do not re-litigate.
* **Date:** 2026-08-07
* **Line:** cross-cutting / integrator (block 0090–0099)
* **Supersedes:** **ADR 0092 §"The consequence for the compute case"**, which concluded that *"the compute
  case rests almost entirely on skipping the ~1000-yr spin-up, not on per-day cost"* and instructed sessions
  never to claim "faster than LPJmL-FIT" without saying so. The instruction stands; **the conclusion is
  rejected as the project's goal.**
* **Related:** ADR 0093 (the cost measurement), ADR 0106 (the acceptance criterion — unchanged and still
  binding), ADR 0001 (the phased hybrid), ADR 0082 (online ESM-first)
* **Consumes:** `EXECUTION_PLAN.md` §0 turns this into a measurable gate.

## Context

ADR 0092 asked for the compute case and, lacking a measurement, reasoned that since the emulator still
evaluates the daily physics on every patch, the runtime-dominating term is unchanged from the C model — so the
saving must come from skipping the spin-up. ADR 0093 then measured it, and found worse: **the emulator is
3.8× SLOWER per cell-year than the C model it replaces** (1.096 vs 0.290–0.383 core-s/cell-year), because its
per-individual daily step costs **51×** the C's.

Presented with that, the owner rejected the spin-up framing outright.

## Owner instruction, verbatim (2026-08-07)

> *"teh savigns for the spin-up is boring and not my main goal. I want a fast emulator that can be run in an
> ESM without to much compute cost."*

And on the sequencing question in the same exchange, confirming the compensating-errors hypothesis
(*"1. yes sounds true."*) and delegating the rung-2 interface width (*"2. whatever you recommend to do
first."*).

## Decision

1. **Per-cell-year speed inside an ESM is a first-class deliverable**, ranked second only to fidelity.
   The goal ordering is: (1) faithful per ADR 0106 → (2) fast enough for an ESM → (3) coupled to the ESM.
2. **The spin-up saving is not a headline.** It remains a true and useful property. It is not the compute
   case, it is not what the project is optimising, and it must not be offered as the answer to "is it fast?"
3. **A speed claim without a measured end-to-end number is not a claim.** Every one names the atmosphere
   resolution it is measured against, because the required speedup differs by three orders of magnitude
   between a small spectral model and a CMIP-class 1° atmosphere.
4. **The gate** (`EXECUTION_PLAN.md` §0): ≤0.030 core-s per cell-year as the intermediate milestone (37×
   from today), ≤0.0135 as the target (81×). ⚠ Both are a **convention** — 10 % of a measured SpeedyWeather
   coupled cost — not an owner-set budget. They are the best available number and the owner may replace them;
   nothing else in the plan depends on which value is chosen.
5. **The work is re-ranked accordingly.** Closing the per-tree gap in the Julia core is **37× with zero
   fidelity risk** and therefore outranks every architectural patch-reduction scheme, which together are worth
   about 3×. This inverts what ADR 0092 implied was the central task. The patch ensemble is still worth
   cutting; it is the last 3× of a 100× problem, not the first lever.

## Consequences

* `EXECUTION_PLAN.md` rung 5 becomes a funded programme with an owner (line O), not a tidy-up.
* An **end-to-end timing harness becomes a required CI gate** (integrator to wire). None existed, which is how
  a 3.8× regression went unnoticed across ~40 sessions.
* Any document that presents the spin-up saving as the compute case is now wrong and should be corrected when
  next touched. Known instance: ADR 0092 (immutable — this record supersedes that section).
* Fidelity is **not** relaxed to buy speed. ADR 0106 is untouched: the emulator must still hit
  `max(10 %, the C's own two-run spread)` on counts, trait distributions and trait medians, on all 54 020
  tree-bearing cells, both scenarios, and the response between them.
* Nothing here licenses a CO2 response (ADR 0107, closed).
