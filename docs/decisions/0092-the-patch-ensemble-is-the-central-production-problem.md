# ADR 0092 — the patch ensemble is THE central production problem, and the compute case is unmeasured

* **Status:** **OPEN — problem statement, strategy to be decided WITH the owner.** This record exists to
  frame the question and stop it being rediscovered; it deliberately does **not** pick an answer.
* **Date:** 2026-08-07
* **Line:** cross-cutting / integrator (block 0090–0099)
* **Owner instruction (2026-08-07), verbatim:** *"this is a major gap in the whole strategy of the whole
  emulator project. make sure to document that as THE major thing to solve. in the next session i want to
  talk about a strategy how we solve that. computing 25 patches for testing and validating is fine — but we
  have to find a strategy for production mode. Maybe we can get the same results with 25 representative
  patches as a 500 patch run? anyway... whether we use less patches or representative/averaged one we will
  see, but that is the central task and challenge!"*
* **Related:** ADR 0053 (measured the modal-patch artifact), ADR 0057 (the coupled driver moved to the patch
  ensemble), ADR 0002 (the emulator predicts *distributions*), ADR 0001 (the phased hybrid)
* **Supersedes nothing.** It reframes a cost assumption that has been implicit since Phase 0.

## Context — the question the owner asked, and why it lands

LPJmL-FIT runs many **replicate patches** per cell because it is a *stochastic gap model*: it seeds random
individuals and lets environmental filtering decide who survives. One patch cannot represent that
distribution, so the model runs an ensemble and reports the mean.

**Component S's entire purpose is to predict the outcome of that filtering directly.** So the owner's
question is the right one:

> if we predict exactly that, why are we running the full X patches again, instead of running the cohorts
> that exist *on average* on those X patches?

The emulator does **not** re-run the filtering — S predicts the survivors. But the coupled driver still
evaluates the **daily physics on every patch** (ADR 0057 moved it there deliberately, and correctly, for
the reasons in §2). That means the term that dominates runtime is **unchanged from the original model**.

### The consequence for the compute case, stated plainly

| Where | Saving |
|---|---|
| Daily physics (the bulk of runtime) | **None today.** Same equations, same patches, same individuals, same 365 days — and F_diff is Julia written for differentiability against a mature MPI C code, so per-patch-day it is plausibly *slower*. |
| Spin-up | **Large.** LPJmL-FIT needs ~1000 simulated years to equilibrate before a transient; the emulator predicts that state. On a 1000-yr-spin-up + 100-yr-transient budget that removes ~90 % of the work. |
| Annual demography | Real but minor — a learned-model evaluation replaces establishment/mortality, but it is a once-a-year step against 365 days of physics. |

⇒ **The emulator's compute argument currently rests almost entirely on skipping spin-up, not on being
cheaper per simulated day.** That is defensible for validation and completely inadequate for production:
25 patches × 54 020 cells is already heavy, and the planned **500-patch** training regeneration makes the
per-cell physics cost 20× worse. A globally coupled online run at 500 patches/cell is not affordable.

**This is not currently written down anywhere as a blocker, and it is one.** The other frontier items
(P2/P3/P4) are fidelity or coverage problems; this one decides whether a production configuration exists at
all.

## Why the patches are there today (what any solution must not break)

A solution cannot simply delete the ensemble. Three distinct jobs are being done, and only the first is
about the filtering:

1. **Filtering — already NOT a reason.** S predicts the survivors; the emulator does not need patches to
   discover them. This is the part the owner correctly identified as redundant.
2. **Comparison basis.** Every gridded number LPJmL-FIT reports is a patch-ensemble mean. Scoring against it
   requires averaging the same way. ADR 0053/0057 measured what happens otherwise: the single **modal**
   patch (densest) carried FPC **1.12–1.72×** and GPP up to **1.33×** the ensemble mean — *selection* bias,
   not sampling noise, so more patches would not have fixed it.
3. **Nonlinearity — the fundamental obstacle.** `mean(f(state)) ≠ f(mean(state))`. Light absorption is
   exponential in leaf area; water stress saturates through a `min`. ADR 0057 recorded a concrete case where
   a *denser* patch produced **slightly less** carbon because its GPP was water-limited, so extra leaf area
   bought nothing. A naive collapse-then-simulate is therefore biased by construction, in a
   cell-dependent direction.
4. **Within-patch structure.** Suppression is a *within-patch* relationship. Averaging patches into one
   stand creates a canopy in which the mean dominant and the mean suppressed tree coexist and compete —
   a configuration that occurred in no patch.

## The option space (to be decided, not decided here)

- **(a) Fewer patches.** Ask how many replicates the *ensemble mean* actually needs — the owner's "same
  results with 25 as with 500". Cheap to test, bounded payoff (20× at best), preserves every mechanism.
- **(b) Representative / stratified patches.** Choose or weight a small set spanning the cell's successional
  states rather than sampling uniformly — importance sampling over gap stages.
- **(c) An effective stand + a correction.** Run the physics once on a collapsed stand and correct the
  nonlinearity bias (learned or analytic). Largest payoff, largest risk, and it must answer §2.3 and §2.4
  head-on.
- **(d) Hybrid.** Ensemble in validation mode, a cheaper production mode with a measured, disclosed bias.

**Nothing here is ruled out and nothing is preferred yet — that discussion is the next session's agenda.**

## What must be measured before choosing (none of this exists yet)

1. **The end-to-end compute comparison has never been made.** There is no timing of a like-for-like run,
   emulator versus original. `scripts/bench_slow_speedup.jl` times the *slow component* — the part that was
   already cheap. Until this exists, the compute case is an argument, not a result.
2. **The convergence curve of the ensemble mean vs patch count** (option a) — on the 500-patch runs, per
   biome. This is the cheapest decisive experiment and should come first.
3. **The collapse bias** (option c): `mean(f(patches)) − f(mean(patches))` per cell, per flux, per season.
   The nearest existing number (modal-vs-ensemble) answers a *different* question and must not be
   substituted for it.
4. **Whether the bias is stable enough to correct** — if it moves with climate, a correction fitted on
   present-day conditions fails exactly where the project's acceptance criterion bites (under warming).

## Consequences

* **This is the top cross-line frontier item.** Recorded in `MEMORY.md` §5 and `STEERING_PROMPT.md` so every
  line sees it regardless of which file it starts from.
* **Validation practice does not change.** Running every patch stays correct for testing and validation —
  the owner explicitly endorsed this. What is missing is a *production* configuration.
* **It sharpens the 500-patch regeneration.** The cohort roster's k-cap merge is dormant at the default cap
  but carries a latent defect of **3.1–5.1× the signal** (ADR 0048); a larger population makes the roster
  longer and is exactly the condition that would wake it. Any patch strategy that scales the population must
  re-check that first.
* **It is prior to P4 (online coupling).** An online global run inherits whatever production configuration
  this decides, so deciding late means rework in line O.
* **Honest disclosure obligation:** until this is settled, no claim that the emulator is "faster than
  LPJmL-FIT" should be made without stating that the saving is the spin-up and that the per-day physics cost
  is unchanged.

## Deliberately not decided

The strategy. The owner has asked to discuss it directly next session, and picking one here — particularly
the tempting (c) — would prejudge a choice whose risk profile depends on how bad the collapse bias turns out
to be. The correct next action is experiment 1 and 2 above, which are cheap and inform the discussion
without committing to anything.
