---
status: "accepted"
date: 2026-07-16
deciders: "Jamir Priesner (owner)"
consulted: "DEVELOPMENT_PLAN.md §2.3/§6; ECOSYSTEM_AND_COUPLING.md §1/§6; ADR 0006 (reuse Terrarium SEB); ADR 0007 (Julia-primary stack); the LPJmL-hybrid-photosynthesis + NeuralCrop.jl reference repos"
informed: "DEVELOPMENT_PLAN.md §2.3/§6 (updated), ADR 0015 (reuse map), MEMORY.md, JOURNAL.md, src/components/fast.jl"
---

# The fast core F is differentiable from the start (F_diff), not F1-now / F2-later

## Context and Problem Statement

`DEVELOPMENT_PLAN.md` §2.3 sequenced the fast biophysical core F in two implementations: **F1**
(keep the compiled LPJmL-FIT C core, drive it via an interface, Phases 3–5, *not differentiable*)
and **F2** (a differentiable rewrite, Phase 6, *optional / "if needed"*). End-to-end
differentiability was thus deferred to the last, optional phase.

The owner reassessed this after the Phase-1/2 gates passed and after `ECOSYSTEM_AND_COUPLING.md`
established that the whole target stack (SpeedyWeather.jl + Terrarium.jl + the
LPJmL-hybrid-photosynthesis / NeuralCrop.jl line) is a **fully-Julia, Enzyme-differentiable**
ecosystem, from the same institute as LPJmL, purpose-built to host exactly this hybrid land
component. **Should F be built differentiable from the start, or is F1-then-optional-F2 still right?**

## Decision Drivers

- **End-to-end differentiability is the *point* of this stack, and it is a *training* tool, not a
  run-time requirement.** The model runs fine without it. Gradients are needed to (a) *train* any
  learned closures embedded in F/E against data, and (b) do gradient-based **online coupled
  training** for stability (the NeuralGCM lesson: rollout gradients through the host are what damp
  the unstable coupled modes). Deferring differentiability to Phase 6 defers the capability the
  architecture exists to enable.
- **Rework risk.** Standing up F1 as the coupling path and then re-implementing F2 later means
  writing the daily biophysics twice and re-validating the coupling twice. Building F_diff once,
  with the C binary as the oracle, avoids the double build.
- **A head start now exists.** The reference repos (see ADR 0015) supply the differentiable λ
  root-find (LPJmL-hybrid-photosynthesis), and the C3/C4 photosynthesis, Priestley–Taylor PET,
  respiration, soil-C, neural-ODE + rollout/TBPTT machinery (NeuralCrop.jl). The differentiable
  core moved from "design it from scratch" to "adapt same-group reference code for FIT trees."
- **The hard parts must be de-risked early, not discovered at Phase 6.** Reverse-mode AD (Enzyme)
  through an implicit λ-solve, and smooth surrogates for the non-smooth ops (min/max supply–demand,
  clamps, regime switches), are the real unknowns. A one-cell spike surfaces them now.
- **S does not need to be differentiable** (see below) — narrowing the differentiable surface to
  F (then E) keeps the scope tractable.

## Considered Options

- **Option A — Keep F1-now / F2-at-Phase-6** (the original §2.3 plan).
- **Option B — F differentiable from the start (F_diff)**; retain the compiled LPJmL-FIT C binary
  **only** as a validation oracle + training-data generator, not as the coupling path.
- **Option C — Never differentiable**; couple the C binary permanently and train S offline with
  periodic re-anchoring (LandSyMM/ecLand pattern), abandoning gradient-based online training.

## Decision Outcome

Chosen option: **B — F is differentiable-first ("F_diff")**, because it is the only option that
unlocks the stack's defining capability (end-to-end gradients for training and online-coupled
stability) without paying to build the daily biophysics twice, and because the same-group
reference repos make it feasible now. **This ADR supersedes the F1-then-F2-at-Phase-6 sequencing
in `DEVELOPMENT_PLAN.md` §2.3/§6.**

De-risking discipline: **before scaling, an early spike on ONE cell** demonstrates a correct
gradient of a simple output (e.g. annual NPP, or a daily flux) w.r.t. an input/parameter, through
the full daily rollout, matching finite differences — and reports the non-smoothness issues
actually hit and an effort estimate for covering all of F.

Roles clarified:

- **F_diff** is the coupling path: the daily *continuous* biophysics (photosynthesis→GPP→NPP, the λ
  supply/demand solve, PET/ET, water balance, snow, soil thermal, respiration), reimplemented in
  differentiable Julia with the **same equations** — only the implementation becomes AD-friendly.
- **The compiled LPJmL-FIT C binary (former "F1") is retained ONLY as (i) the numerical-regression
  oracle** F_diff must reproduce (ReferenceTests, see `src/`), **and (ii) the daily training-data
  generator** (the 186 GB dataset already produced). It is **not** the coupling path.
- **S stays on its current non-differentiable tree/copula (DRF/LightGBM) baseline** (ADR 0002,
  0005). It trains separately and is **not** in the gradient loop: the discrete/stochastic
  demography (allocation, growth, turnover, establishment, mortality, the trait/size distribution +
  count N) is emulated by ML and is *not* reimplemented as differentiable physics. The only
  deterministic S↔F handoff kept exact/differentiable is applying the allocated fractions so the
  delivered NPP is conserved (flux-then-integrate, ADR 0003).
- **E (later, Phase 4)** reuses Terrarium.jl's already-differentiable `SurfaceEnergyBalance` +
  `ImplicitSkinTemperature` (ADR 0006). Not part of this spike.

### Consequences

- Good, because the coupled S + F(+E) system becomes end-to-end differentiable early, enabling
  learned-closure training and gradient-based online rollout training (coupled stability).
- Good, because the daily biophysics is implemented **once** (F_diff), with the C binary as an
  independent oracle — a stronger correctness check than "F1 is the same code."
- Good, because it reuses same-group reference code (ADR 0015) rather than re-deriving.
- Bad/risk, because **reverse-mode AD through the implicit λ-solve is genuinely hard**; mitigated
  by the implicit-function/adjoint approach (not differentiating through bisection iterations) and
  quantified by the spike.
- Bad/risk, because **non-smooth ops require smooth surrogates**, each an approximation; mitigated
  by documenting every surrogate and adding a test bounding its deviation from the exact op.
- Bad, because the dependency graph grows (Enzyme, Lux, SciML/OrdinaryDiffEq, SciMLSensitivity,
  KernelAbstractions, FiniteDifferences); Aqua's stale-dep check keeps it honest.
- Neutral, because the "same physics" requirement is enforced mechanically as CI gates from the
  start (numerical regression vs the C binary; gradient correctness vs finite differences).

## Pros and Cons of the Options

### Option A — F1-now / F2-at-Phase-6

- Good, because F1 is fast to stand up and conservation is guaranteed (it *is* LPJmL).
- Good, because it defers the hard AD work.
- Bad, because it defers the stack's defining capability (differentiability) to an *optional* last
  phase, and risks it never being reached.
- Bad, because it implements the daily biophysics twice and re-validates coupling twice.

### Option B — F_diff from the start (chosen)

- Good, because differentiability is available for training from Phase 3 onward; single build.
- Good, because the reference repos make it feasible now.
- Bad, because the AD-hardness (λ-solve, non-smooth ops) is paid up front — but that is exactly
  what a scoped one-cell spike exists to de-risk before scaling.

### Option C — Never differentiable

- Good, because it is the least engineering effort.
- Bad, because it forecloses gradient-based online training — the mechanism `RESEARCH_SURVEY.md` D
  and NeuralGCM identify as what actually stabilizes coupled hybrid models. Rejected.

## More Information

- Reuse shopping list and citations: **ADR 0015 (reuse map)**.
- Superseded planning text: `DEVELOPMENT_PLAN.md` §2.3 (F1/F2 split) and §6 (Phase 6 "optional F2")
  are updated to describe F_diff-first with the C binary as oracle/generator.
- Validated by: the one-cell spike (gradient-correctness gate — Enzyme/AD vs FiniteDifferences
  through the daily rollout, no NaN/Inf; numerical-regression gate — F_diff reproduces the C
  binary's daily outputs on the prototype cell to tolerance). See
  `test/testitems/gradient_correctness_tests.jl` and `test/testitems/numerical_regression_tests.jl`.
- Revisit if: Enzyme cannot be made to differentiate the coupled daily rollout at acceptable
  cost/robustness on this platform (the spike is the go/no-go); then fall back to Option A for the
  coupling path while keeping F_diff as a research track.
- ADRs are immutable once accepted — supersede rather than edit.
