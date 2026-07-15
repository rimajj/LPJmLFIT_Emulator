# Why a hybrid?

> *Explanation. The decision is frozen and justified in `DEVELOPMENT_PLAN.md` §1 and
> [ADR 0001](https://github.com/rimajj/LPJmLFIT_Emulator/blob/main/docs/decisions/0001-phased-hybrid.md);
> this page is the reasoning, not a re-litigation.*

We build a **phased hybrid**: emulate the slow, expensive, path-dependent individual-tree trait/size
dynamics with ML (component **S**), keep LPJmL-FIT's conserving daily biophysical core (component
**F**), and add a conservation-constrained surface-energy-balance + skin-temperature closure
(component **E**). A full fast-core *emulation* is deferred, gated on profiling and on a
differentiable core existing.

## The strongest single piece of evidence: the sibling emulator's failure

A sibling project (`/p/projects/open/Jamir/emulator`, `DESIGN.md` §6) already built component **S
offline** — a LightGBM + Gaussian-copula distribution emulator — on this exact data, and its own
review recorded the honest outcome:

- ✅ **Present-day interpolation works**, near the seed noise floor (per-cell spatial pattern
  `r ≈ 0.94–0.97` across 63,119 cells; ecological trait links reproduced).
- ❌ **The SSP370 projection fails.** The future forest is in *transient disequilibrium*, which an
  **equilibrium climate → distribution mapping cannot represent even in principle**; the models drew
  73–86 % of their signal from static historical normals, so warming left the prediction unmoved.
- ⚠ **Per-cell biomass sat at a ceiling** (~1.8–2.4× the 25-patch noise floor), proven irreducible
  from sampling noise plus non-climate variance (stand age, disturbance history).

That failure is **the hybrid's mandate, with evidence**: it is exactly the missing *dynamical* layer.
F computes the true, transient-aware daily biophysics and delivers the actual `bm_inc`; S advances
the existing population by flux-then-integrate rather than regenerating an equilibrium snapshot; the
slow woody-carbon and population states are carried explicitly and conditioned on climate/state. The
equilibrium-ML route is a demonstrated dead end for the transient — so the physical core is not
optional dressing, it is the thing that makes out-of-distribution behaviour possible.

## Why keep the physics rather than emulate it too

1. **Conservation comes for free from the physical core.** Re-learning the water and carbon budgets
   in a fast emulator and then enforcing closure architecturally is extra work and risk; inheriting
   closure from physics is strictly lower-risk (see [Conservation](conservation.md)).
2. **Online-stability risk concentrates in the fast loop.** The field's central lesson is that
   offline skill does *not* predict coupled stability and can anti-correlate with it — a
   better-offline neural net crashed the coupled run in days while a worse-offline random forest
   stayed stable [Brenowitz2020](@cite). A physical fast core removes the most dangerous instability
   source from the coupled system.
3. **The fast biophysical core is not the compute bottleneck.** In LPJmL-FIT the cost is dominated by
   per-individual bookkeeping, not the daily big-leaf biophysics. Emulating the *slow* part therefore
   captures the great majority of the achievable speed-up (cf. ~95 % from emulating carbon dynamics in
   [Natel2025](@cite)), while a fast emulator would add risk for marginal extra speed.
4. **The slow distributional emulator is the novelty.** No published ML emulator reproduces a
   demographic/trait-based DGVM's *distributions*; existing land emulators emulate aggregate carbon
   [Natel2025](@cite) or scalar prognostic states [Wesselkamp2025](@cite), not trait × size spectra.

## The pattern: physics owns conservation, ML supplies bounded closures

This is the robust hybrid pattern from differentiable geoscience: a physical process model with
embedded NNs that only supply *parameters* or *bounded closures*, so conservation holds for any NN
output and physically coherent untrained diagnostics come for free [Tsai2021, Shen2023](@cite). Where
a differentiable core exists, the coupled system can be trained online through the solver over
multi-step rollouts, which is what buys decade-scale stability [Kochkov2024](@cite). Even without a
full differentiable re-implementation, the *pattern* — the network reshapes within a balance the
physics closes — is the safe way to add the energy layer E.

## When to revisit (explicit trigger)

Pursue fast-core emulation only if profiling at target scale shows the daily biophysical core
dominates runtime, or once a differentiable re-implementation exists (the NeuralCrop / LPJmL-hybrid-
photosynthesis line, `ECOSYSTEM_AND_COUPLING.md` §1) — at which point an ML fast component can be
trained online through the differentiable host with conservation constraints. Until then, the
physical core is the safer, faster path to a working, conserving, coupled component.
