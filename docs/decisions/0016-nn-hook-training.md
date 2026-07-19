---
status: "accepted"
date: 2026-07-17
deciders: "Jamir Priesner (owner)"
consulted: "ADR 0014 (differentiable-fast-core-first); ADR 0015 (reuse map); HANDOFF_NEXT_SESSION.md §7b; NeuralCrop.jl (Lux+Zygote NN λ/Vcmax + TBPTT rollout training scaffold, CC BY-NC); docs/phase3_fdiff_cbinary_validation.md §13"
informed: "DEVELOPMENT_PLAN.md §6; MEMORY.md; JOURNAL.md; src/fdiff.jl; src/LPJmLFITEmulator.jl; ext/FDiffTrainingExt.jl; test/testitems/nn_training_tests.jl"
---

# Hybrid learned closures in F_diff: NN λ/Vcmax **correction** hooks, trained by TBPTT online rollout, shipped as a package extension

## Context and Problem Statement

ADR 0014 made the fast core differentiable "from the start" precisely so that learned closures in F
could be trained end-to-end and gradient-based **online rollout training** (the NeuralGCM stability
lesson) becomes possible. Scale-up steps 1–7a delivered a calibrated, crutch-free `F_diff` whose
`d(GPP)/d(param)` and `d(structure)/d(bm_inc)` both match finite differences. The remaining question
is *how* to actually embed and train a learned closure — the milestone the handoff calls (b)
"gradient-based online rollout training — finish NeuralCrop's TBPTT scaffold + add Lux NN λ/Vcmax
hooks."

Three sub-questions had to be decided: **(1)** where/how the NN attaches to the physics; **(2)** what
the NN outputs (a replacement value or a correction); **(3)** where the ML dependencies (Lux, Zygote,
Optimisers) live given the runtime is deliberately dependency-free (ADR 0014), and which AD backend
trains it.

## Decision Drivers

- **The runtime must stay dependency-free** (ADR 0014): `src/fdiff.jl` is pure Base Julia; Aqua
  enforces no stale deps. A learned closure must not drag `Lux`/`Zygote` into the runtime.
- **The physics is already calibrated** (docs §13): the honest role of the NN is to close the
  *documented residual* (the inherited GPP-phenology level), not to replace working physics. An
  untrained model should degrade gracefully to the calibrated physics.
- **AD must actually flow w.r.t. the NN parameters.** `F_diff` computes its working type `T` from its
  declared inputs and `convert(T,·)`s its state, so a `ForwardDiff.Dual` injected *only* via the NN
  params hits that `convert`. Reverse-mode keeps the forward values `Float64`.
- **Reuse, don't re-derive** (ADR 0015): NeuralCrop.jl already ships the Lux-MLP + `neural_lambda`/
  `neural_vmax` + Zygote + Optimisers + TBPTT-rollout idiom — but as a *crop-only, broken* scaffold
  (`ps_frozen`/`dailyWeather` undefined). Port the pattern, finish the loop.

## Considered Options

**(1) Attachment point** — A: NN inside the physics kernel replacing the analytic Vcmax/λ; B: NN as
an *optional multiplicative correction hook* the kernel calls (identity when absent); C: post-hoc NN
correcting the model output.

**(2) Output form** — replacement value vs. multiplicative correction (`scale ≈ 1`).

**(3) Dependency home + AD** — A: Lux/Zygote as runtime deps; B: a separate `training/` sub-project;
C: a **package extension** gated on `Lux`/`Zygote`/`Optimisers`. AD: Zygote (reverse, NeuralCrop's
choice), Enzyme (reverse), or ForwardDiff (forward).

## Decision Outcome

- **(1+2) An optional multiplicative CORRECTION hook inside the kernel** (`FDiff.FluxHooks`): each of
  the two photosynthesis levers the hybrid trains — Vcmax (`vm`) and the ci:ca ratio `λ` — gains an
  optional callable `feat -> scale` (`scale ≈ 1`). `vm` scales Vcmax (propagating consistently into
  potential conductance and leaf respiration); `λ` scales the solved ci:ca ratio, re-clamped to the
  physical bracket. The default is `nothing` (pure physics — the identity fast path, so **every**
  regression baseline is byte-identical), and the final NN layer is **zero-initialized** so the
  *untrained* network is exactly the identity correction. This makes the NN a residual on the
  calibrated physics (it starts at, and can only depart from, the working model), not a replacement.
- **(3) The training capability ships as a PACKAGE EXTENSION** `ext/FDiffTrainingExt.jl`, activated by
  `using Lux, Zygote, Optimisers`. The runtime hard-deps stay empty; the physics only ever *calls*
  the hook (a plain function). **Zygote** (reverse-mode) trains it — it matches NeuralCrop, keeps the
  forward values `Float64` (sidestepping the `convert(T,·)` wall a ForwardDiff dual would hit), and
  handles the immutable single-representative `daily_step`/`rollout` path cleanly. The gradient gate
  cross-checks the Zygote NN-parameter gradient against **FiniteDifferences** (the same AD-vs-FD
  discipline as the physics gradient gate, ADR 0014).
- **Training method:** the finished TBPTT online-rollout loop (`train_fdiff_rollout!`) — sweep the
  daily rollout in chunks, take a Zygote gradient of the segment GPP loss w.r.t. the NN params,
  `Optimisers.update`, and carry the detached soil-water state across chunk boundaries (the
  "truncated" in TBPTT). Target = the LPJmL-FIT C-binary daily GPP on the Hainich prototype.

### Consequences

- Good, because the runtime stays dependency-free (ADR 0014 preserved) while the hybrid-training
  capability is shipped, discoverable, and gate-tested (the extension loads in the test env).
- Good, because identity-at-init + identity-when-off means the learned closure is a *safe residual*:
  no baseline moves until the model is trained, and a bad train degrades to the calibrated physics.
- Good, because the correction form is physically bounded and interpretable (an effective-Vcmax / ci:ca
  multiplier), and the gradient is verified against finite differences.
- Bad/limitation, because **v1 lands on the single-representative `daily_step` path** (immutable,
  Zygote-clean), where the closed gap is partly the structural single-individual deficit. Applying the
  same hooks on the **coupled multi-individual canopy** path — which mutates arrays, so it needs
  **Enzyme reverse** (the documented follow-up already flagged in the handoff) — is the next step.
- Bad, because the dependency graph grows (Lux, Zygote, Optimisers) — but only as weakdeps/extension +
  test deps, never runtime; Aqua stays green.
- Neutral, because ForwardDiff-w.r.t.-NN-params is intentionally not supported by the identity-preserving
  `convert`; reverse-mode (Zygote now, Enzyme for the canopy) is the correct tool for NN parameters.

## Pros and Cons of the Options

### (1) Attachment — B: correction hook inside the kernel (chosen)

- Good, because the correction sees the true in-kernel drivers and propagates consistently downstream
  (Vcmax → conductance, λ → assimilation); identity fast path keeps the runtime untouched.
- Bad, because it threads an optional kwarg through the rollout — mitigated by a `nothing`-typed
  default that the compiler specializes away.

### (1) Attachment — A: replace the analytic kernel / C: post-hoc output correction

- A is bad: it discards the calibrated kernel and cannot degrade gracefully; C is bad: a post-hoc
  correction breaks conservation-by-construction and cannot feed the state feedback (soil water).

### (3) Dependency home — C: package extension (chosen)

- Good, because it is the idiomatic Julia way to ship an optional heavy capability with a
  dependency-free core; loads on demand; testable.
- Bad, because extensions require stub generic functions in the parent + a trigger set — minor
  boilerplate, done once.

### (3) Dependency home — A: runtime deps / B: separate sub-project

- A violates ADR 0014 (dependency-free runtime) and would fail Aqua; B (a `training/` env like `docs/`)
  keeps the capability out of the shipped package and out of the CI gate — weaker than an extension.

## Implementation status (updated)

The decision above landed in three steps (docs `phase3_fdiff_cbinary_validation.md` §14–§16):

- **§14 (step 7b)** — the hooks + the Zygote TBPTT loop (`train_fdiff_rollout!`) on the immutable
  single-representative `daily_step` path; gate-verified identity + Zygote-vs-FD gradient + recovery.
  Finding: that path's GPP residual is **light-limited**, so Vcmax is the wrong lever there.
- **§15 (step 7b-canopy)** — the hooks + an **Enzyme-reverse** TBPTT loop (`train_fdiff_canopy_rollout!`)
  on the array-mutating multi-individual `daily_step_canopy`; Enzyme gradient vs FiniteDifferences to
  1.2e-8. This closed the AD-through-mutation follow-up.
- **§16 (step 7b-cell)** — training against the **real C-binary daily GPP** on the full 25-patch cell
  (`fdiff_cell_gpp_loss` / `train_fdiff_cell_rollout!`). The C daily GPP is the cell-mean over patches, so
  the cell-MSE gradient is computed by an **exact per-patch Gauss–Newton decomposition** (`∂L/∂ps =
  Σ_p ∂/∂ps Σ_i c_i·g_{p,i}`, `c_i` the detached residual) — every reverse pass is the proven single-patch
  Enzyme path, so no monolithic multi-patch AD entry point is compiled. The learned Vcmax/λ correction
  closes the canopy GPP level (1.093 → 1.023 `:vm`, → 1.010 `:vm,:λ`) while the daily correlation improves
  — the canopy residual is Vcmax-shaped, confirming §14's prediction that this is the right path/lever. The
  λ lever is now exercised (both heads trained).
- **§17 (step 7b-multiyear)** — training **through the multi-year structure/allocation feedback**. This
  closes open follow-up (a) below. The `EnzymeNoTypeError` was NOT the cause (a) predicted (an untyped
  temporary in `_patch_fpars`/`_solve_leaf_inc` — both differentiate cleanly in isolation, Enzyme =
  FiniteDifferences to 1e-9); it is a **struct-in-memory** failure: storing `grow_individual`'s branchy
  struct output into a `Vector{TreePools}` and field-scattering it copies the struct's trailing
  `is_grass::Bool` + padding as `Anything` in an 80-byte `memcpy` ⇒ Enzyme cannot deduce the copy's type.
  The fix (a reusable technique, see the updated follow-ups) is **struct-of-arrays**: carry the
  differentiated multi-year state as plain `Vector{Float64}` field arrays, never a `Vector{TreePools}` in
  the differentiated region. `_patch_fpars` is split into an Enzyme-typeable SoA core `_patch_fpars_soa`
  (+ a byte-identical `Vector{TreePools}` wrapper, max|Δ| = 0.0), and a new `rollout_canopy_years_gpp` runs
  the multi-year coupled rollout in SoA form (per-year stand GPP). Enzyme reverse through the full SoA
  structure → daily rollout → grow → next-year chain matches FiniteDifferences to **<1e-9** (network-param
  gradient; ~1e-11 on a scalar hook; ForwardDiff too). Trainer `fdiff_multiyear_gpp_loss` /
  `train_fdiff_multiyear_rollout!`; gate multi-year testitem (identity Δ=0; recovery loss 16.2 → 0.12,
  99.3 %, trained GPP within 0.28 % of a known vm=1.15/λ=1.05 target). Single-patch entry point; the
  cell-multi-year objective is the next extension.

**Open follow-ups** (updated). (a) ✅ **DONE (§17, step 7b-multiyear)** — the multi-year objective through
the structure/allocation feedback is now Enzyme-differentiable (<1e-9 vs FD). The predicted culprit was
wrong: not an untyped temporary in `_patch_fpars`/`_solve_leaf_inc` but a `Vector{TreePools}` field-scatter
whose struct `memcpy` reads the trailing `is_grass::Bool` + padding as `Anything`. **Reusable technique
recorded: to make a mutating, branchy struct path Enzyme-typeable, carry the differentiated state as
struct-of-arrays (`Vector{Float64}` per field) rather than a `Vector{struct}`** — no struct memcpy, no
padding, every carried value concretely typed; the same discipline applies to `Union{Nothing,Vector}` phis
(materialize to a concrete type up front) and to two-field state structs carried around a loop (carry the
fields, not the struct). `Enzyme.API.maxtypeoffset!`/`maxtypedepth!` (size limits) and `looseTypeAnalysis!`
(returns a WRONG gradient) are NOT correct workarounds — the only correct fix is to remove the untypeable
value. (b) the **cell-multi-year objective** — §16's exact per-patch Gauss–Newton decomposition, each patch
grown across years (every reverse pass = the proven single-patch `rollout_canopy_years_gpp` Enzyme path).
(c) lifting the `VERSION < v"1.11"` guard once Enzyme compiles the mutating canopy reverse pass on Julia
≥ 1.11.
