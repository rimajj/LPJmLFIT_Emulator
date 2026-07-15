---
status: "accepted"
date: 2026-07-15
deciders: "Jamir Priesner (owner)"
consulted: "DEVELOPMENT_PLAN.md §1, RESEARCH_SURVEY.md, DESIGN.md §6"
informed: "all downstream ADRs"
---

# Build a phased hybrid: emulate the slow dynamics, keep the physical core, add an energy closure

## Context and Problem Statement

LPJmL-FIT is expensive mainly because of individual-tree bookkeeping, and it lacks the surface energy
balance an ESM atmosphere needs. Should we build a **full emulator** of the whole model, a **hybrid**
(emulate the slow part, keep the physical fast part), or keep the model as-is? See
`DEVELOPMENT_PLAN.md` §1.

## Decision Drivers

- Coupled online **stability** matters more than offline skill (`RESEARCH_SURVEY.md` D.1).
- Water/carbon **conservation** should be as low-risk as possible.
- Where the compute cost — and thus the speed-up — actually lives.
- Scientific novelty and value.

## Considered Options

- **Full emulator** of the whole model (fast + slow).
- **Phased hybrid**: emulate slow trait/size dynamics (S), keep the physical daily core (F), add a
  new energy-balance closure (E). Full fast-core emulation deferred, gated on profiling / a
  differentiable core.
- **Keep LPJmL-FIT unchanged** (no ML).

## Decision Outcome

Chosen: **phased hybrid**. Conservation of water and carbon comes *for free* from the physical core;
online-stability risk concentrates in the fast loop, which a physical core removes; the fast
biophysical core is not the compute bottleneck (so emulating the slow part captures ~95 % of the
achievable speed-up, cf. Natel et al. 2025); and the slow distributional emulator is the scientific
novelty. Both routes need the energy closure anyway, so it is not a differentiator.

### Consequences

- Good: inherits conservation; removes the most dangerous instability source; highest-value novelty.
- Good: the constraint that once forced hybrid is gone (daily output is a config flag), so this is a
  free, risk-weighed choice — not a workaround.
- Bad: a two-language / two-timescale system with a non-trivial S↔F interface to maintain.
- Bad: F1 (keep the C core) understates the surgery on an MPI batch program — carried forward as a
  Phase-3 feasibility risk (`DESIGN.md` §9).

## More Information

Revisit trigger (fast-core emulation, Phase 7): only if profiling at target scale shows the daily
core dominates runtime, or once a differentiable core exists (`DEVELOPMENT_PLAN.md` §1 "When to
revisit"). Enables ADRs [0002](0002-emulate-distributions.md), [0003](0003-flux-then-integrate-carbon.md),
[0006](0006-reuse-terrarium-seb.md).
