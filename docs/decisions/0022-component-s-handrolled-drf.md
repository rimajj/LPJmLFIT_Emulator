---
status: "accepted"
date: 2026-07-22
deciders: "engineering agent (standing autonomous delegation, STEERING_PROMPT / NEXT_SESSION_PROMPT); reversible by the owner or a superseding ADR"
consulted: "ADR 0014 (F_diff pure-Base; runtime [deps] EMPTY; learned closures ship as extensions), ADR 0021 (S is native Julia — 'EvoTrees.jl/DRF + Lux + hand-rolled copula'), esm-emulator-ci-and-test-ops (CI resolves deps fresh; the Enzyme-0.13.189 regression), docs/p1_s_in_loop_design.md"
informed: "P1 Tier-1 (the flux-driven S build); src/drf.jl; ext/ packaging; NEXT_SESSION_PROMPT.md; MEMORY.md; JOURNAL.md; Project.toml [weakdeps]"
---

# Component S's learned count/marginal model is a hand-rolled ZERO-DEP Julia DRF, not the EvoTrees package

> **Status note.** `accepted` 2026-07-22 under the standing autonomous delegation. It **refines the
> mechanism of ADR 0021** ("EvoTrees.jl/DRF + Lux + hand-rolled copula") by choosing, among the options
> ADR 0021 explicitly allows ("EvoTrees.jl **/DRF**"), the **hand-rolled Distributional Random Forest**.
> It leaves ADR 0021's intent (S trained AND run in native Julia; no Python at runtime; build S once) and
> ADR 0020's governing conditioning contract (S is flux-driven) unchanged. Reversible by a superseding ADR.

## Context and Problem Statement

ADR 0021 mandates a native-Julia S and names two acceptable model classes for the distributional/count
part: **EvoTrees.jl** (a maintained gradient-boosting package) **or a Julia DRF** (distributional random
forest). The choice between them is a real engineering decision because of two hard constraints this
codebase lives by:

1. **ADR 0014 — the runtime `[deps]` must stay EMPTY** and the differentiable core is pure-Base Julia.
   Learned pieces ship via the package-extension mechanism (weakdeps), and Aqua enforces no stale deps.
2. **CI resolves dependencies FRESH every run** (manifests are git-ignored). A too-wide `[compat]` silently
   absorbs upstream bumps — this is *exactly* how Enzyme 0.13.189 turned CI red with a byte-identical test
   tree (CLAUDE.md §2 / §5, memory `esm-emulator-ci-and-test-ops`). Every package added to `[weakdeps]`
   participates in that fresh resolution and must precompile on Julia 1.10-lts.

Adopting **EvoTrees** as a weakdep pulls in a substantial transitive graph (Distributions, NNlib,
MLJModelInterface, BSON, CategoricalArrays, Tables, …). Each is another surface for the Enzyme-0.13.189
failure mode to recur — a dependency bump reddening the trusted-physics CI with no change to our code. The
learned count model S needs is modest: predict a per-patch stem count (and, later, sample recruit-trait
marginals) from ~40 tabular features. That does **not** require a general GBDT framework.

EvoTrees was verified to resolve + precompile cleanly on this cluster's Julia 1.10 depot
(`[VERIFIED 2026-07-22]`, isolated probe, exit 0) — so it remains a viable fallback — but "it precompiles
today" does not neutralise the standing fresh-resolution risk.

## Decision

**Implement S's learned count/marginal model as a hand-rolled, zero-dependency Distributional Random Forest
in pure Base Julia (`src/drf.jl`).**

1. **`src/drf.jl` (`module DRF`)** — a subbagged, variance-reduction regression forest with: a hand-rolled
   **Xoshiro256++** RNG (splitmix64-seeded; no `Random` stdlib dep, matching the project convention of
   hand-rolling `mean`/`std`/Cholesky rather than adding `Statistics`/`LinearAlgebra`); leaves that store
   the mean (count) and OPTIONALLY the sample values (`store_values=true`) for empirical **quantile /
   distributional** queries (the recruit-trait marginals a Gaussian copula maps onto). Deterministic under
   a seed (per-tree RNG stream ⇒ multithreaded fit is bit-reproducible). It is **pure Base** — it can live
   in `src/` with **no addition to `[deps]` or `[weakdeps]`**, and it is the *same* code at train time and
   run time (ADR 0021's "build once", taken to its conclusion: not even a weakdep to load).
2. **Training is native Julia too** (a `scripts/*.jl` job, SLURM-run), reading the aligned table Python
   emits (ADR 0021 §2a) via a zero-dep raw-matrix payload. The fitted forest serialises to a compact
   Base-Julia format the coupled runtime reads with pure Base IO — no Parquet/JSON runtime dep.
3. **`Lux` stays out unless an NN part is proven necessary.** ADR 0021 allowed Lux "if any NN part is
   needed"; the DRF + hand-rolled Gaussian copula cover the count + recruit-trait-marginal + within-stand
   correlation structure the `DirectEmulator` used, so **no NN is introduced in P1**. If a later gate needs
   one, it ships as an extension per ADR 0014.

## Consequences

- **Zero new runtime or weak dependencies.** `[deps]` stays empty; `[weakdeps]` is untouched; Aqua stays
  clean; the trusted-physics CI keeps its current dependency-bump surface — the DRF cannot be broken by an
  upstream release. This is the decisive reason.
- **We own the model's correctness.** A hand-rolled forest is ~300 lines and must be unit-tested (RNG
  determinism, signal recovery R², monotone quantiles, refit reproducibility, missing-value handling) —
  done in `src/drf.jl`'s smoke checks and the Julia test suite. The trade is: more of our own code to trust,
  in exchange for a much smaller external-dependency risk. For this codebase (whose entire value rests on
  trusted, reproducible physics under fresh-resolving CI) that trade is worth taking.
- **`DemographicSlowEmulator` (Tier-0) is unaffected** — still dep-free. The **`FluxDrivenSlowEmulator`
  (Tier-1)** now also has no external dep, so it can live in `src/` beside Tier-0 rather than strictly in an
  extension; ADR 0021's "ships via extension" was motivated by isolating EvoTrees/Lux, which no longer
  applies. (If a future model part does need a heavy dep, revert that part to the extension pattern.)
- **EvoTrees remains a documented, verified fallback** if the hand-rolled DRF's accuracy proves inadequate
  at the P1 gate — reversible by a superseding ADR that adds it as a bounded weakdep.
- **Falsifiability is unchanged.** The ADR-0020 warm+dry OOD success test (`scripts/flux_ood_experiment.jl`)
  runs on this DRF; if flux-conditioning does not beat climate-conditioning OOD, ADR 0020 is falsified
  regardless of the model-package choice made here.
