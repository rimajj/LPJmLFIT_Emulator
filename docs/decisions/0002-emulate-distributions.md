---
status: "accepted"
date: 2026-07-15
deciders: "Jamir Priesner (owner)"
consulted: "DEVELOPMENT_PLAN.md §2.2, RESEARCH_SURVEY.md A.4/B, DESIGN.md §2.4"
informed: "ADR 0003, ADR 0005"
---

# Emulate the per-cell trait/size distribution, not individual trees

## Context and Problem Statement

LPJmL-FIT simulates many individual trees per patch as a stochastic ensemble. What is the correct
*target object* for component S — individual trees, or the distribution they form? See
`DEVELOPMENT_PLAN.md` §2.2 and `RESEARCH_SURVEY.md` A.4.

## Decision Drivers

- The model's own output is a **stochastic (RNG-driven) patch ensemble** — a single realization is not
  meaningful to reproduce.
- Well-posedness of the learning target.
- Scientific novelty.

## Considered Options

- **Emulate individual trees** (per-tree trajectories).
- **Emulate summary scalars only** (e.g. aggregate VegC), like most DGVM emulators.
- **Emulate the per-cell distribution** `p(traits, size ∣ drivers, state)` + count `N` (a Trait
  Probability Density), advanced autoregressively.

## Decision Outcome

Chosen: **emulate the distribution + count `N`**. The patch ensemble is RNG-driven, so per-tree
prediction is neither well-posed nor useful; the well-posed target is the distribution. No published
ML emulator reproduces a demographic/trait-based DGVM's *distributions*, so this is also the project's
novelty (`RESEARCH_SURVEY.md` A.4).

### Consequences

- Good: a well-posed target; evaluable against the seed1-vs-seed2 **noise floor**.
- Good: preserves trait trade-off manifolds (via distributional methods), which per-scalar emulation
  loses.
- Bad: requires a **distributional metric panel** (never a single metric) and careful conservation at
  the handoff (a variable count `N` complicates a naive softmax — resolved in
  [ADR 0003](0003-flux-then-integrate-carbon.md)).
- Bad: **must never be evaluated or reported per-tree** — a standing caveat.

## More Information

Method choice for the distribution: [ADR 0005](0005-drf-baseline-escalation.md). Evaluation panel:
`DEVELOPMENT_PLAN.md` §5.
