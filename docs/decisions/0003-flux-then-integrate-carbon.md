---
status: "accepted"
date: 2026-07-15
deciders: "Jamir Priesner (owner)"
consulted: "DEVELOPMENT_PLAN.md §2.2, RESEARCH_SURVEY.md C, DESIGN.md §3.2/§8"
informed: "the conservation @testitem gates"
---

# Conserve carbon by flux-then-integrate, with fire and establishment in the budget

## Context and Problem Statement

S must not invent or destroy carbon at the F → S handoff. But S's target is a *re-sampled
distribution* over a *variable* count `N`, so merely partitioning a pool total does not guarantee the
drawn distribution carries the right carbon. How is carbon conserved? See `DEVELOPMENT_PLAN.md` §2.2
and `RESEARCH_SURVEY.md` C.

## Decision Drivers

- Hard architectural constraints beat soft penalties (per-sample guarantee; Beucler et al. 2021).
- Avoid a privileged residual variable where we have the freedom to (residual-field bias).
- **All** active model fluxes must be accounted, or the budget fails to close (the Frame/Beven
  failure mode).

## Considered Options

- **Regenerate** the distribution each year, then rescale onto the conserved total (soft correction).
- **Flux-then-integrate**: predict increments applied to the *existing* population, summing to the
  delivered NPP (MC-LSTM style; Hoedt et al. 2021), with softmax partitions of the conserved input.
- **Soft loss penalty** on the carbon residual.

## Decision Outcome

Chosen: **flux-then-integrate with softmax partitions, fire and establishment included**. S predicts
per-individual/class growth increments with `Σ ΔC_i = f_alloc · bm_inc`; mortality moves carbon to
litter/soil, establishment adds saplings debited from `flux_estabc`, fire removes `firec`. Every
carbon movement is an accounted flux ⇒ conservation by construction. The budget is
`ΔC = NPP − Rh − firec + flux_estabc` and `NBP_atm = Rh + firec − NPP − flux_estabc`; a fire-free
`NEE = Rh − NPP` will **not** close (`DESIGN.md` §3.2).

### Consequences

- Good: machine-precision closure at ~2 % accuracy cost; no privileged carbon residual; helps
  cross-climate generalization (flux/budget prediction, cf. FloeNet).
- Good: the primitives are real and tested — [`softmax_partition`](../../src/conservation.jl),
  [`flux_then_integrate`](../../src/conservation.jl), `carbon_budget_residual`, `nbp_atm`.
- Bad: `firec` and `flux_estabc` must be carried explicitly through the interface ([`FToE`](../../src/interface.jl)
  puts `flux_estabc` on an annual channel) — more plumbing.
- Bad: the stiff autoregressive carbon+population system can still oscillate/blow up; needs bounded
  outputs, multi-step rollout, and re-anchoring (a separate mitigation, not solved by conservation
  alone).

## More Information

Safe here because the targets are a self-consistent numerical model whose budgets close — unlike
observation-trained hydrology, where strict closure can hurt (`RESEARCH_SURVEY.md` C.4). The
**energy** budget is the deliberate exception (H as residual) — see the model description and
[ADR 0006](0006-reuse-terrarium-seb.md). Verified by the conservation `@testitem` gates
(ENGINEERING_STANDARDS §2, gate 1).
