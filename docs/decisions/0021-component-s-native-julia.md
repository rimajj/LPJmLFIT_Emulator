---
status: "accepted"
date: 2026-07-22
deciders: "Jamir Priesner (owner) — decision authority delegated to the engineering agent; this refinement issued directly by the owner"
consulted: "ADR 0007 (Julia-primary stack), ADR 0014 (F_diff pure-Base; learned closures ship as extensions), ADR 0018 (S is non-differentiable, outside the AD loop), ADR 0019 (port inference / wrap machinery), ADR 0020 (S is flux-driven); DEVELOPMENT_PLAN §2.2; docs/p1_s_in_loop_design.md; python/src/lpjmlfit_emulator/baseline.py (DirectEmulator)"
informed: "P1 Tier-1 (the flux-driven S build); src/slow_infer.jl (obsoleted); scripts/export_slow_hainich.py (rescoped); NEXT_SESSION_PROMPT.md; MEMORY.md; JOURNAL.md"
---

# Component S is trained and run in NATIVE JULIA; Python is confined to the training table + the OOD benchmark

> **Status note.** `accepted` 2026-07-22, issued by the owner as a direct refinement of the S plan and
> recorded here under the standing delegation. It **supersedes the mechanism of ADR 0019** ("train in Python
> / LightGBM, then *port inference* to pure-Base Julia via a GBDT text-walk"). It keeps ADR 0019's intent
> (no Python at runtime; empty runtime `[deps]` for the differentiable core) and ADR 0020's governing
> conditioning contract (S is flux-driven) unchanged. Reversible only by a superseding ADR.

## Context and Problem Statement

ADR 0019 chose to keep S *training* in Python (LightGBM + a hand-rolled copula + Poisson/NB) and **port the
inference** to pure-Base Julia (`src/slow_infer.jl`: a GBDT text-walk + `Φ`/`Φ⁻¹` + Cholesky), so the
coupled model needs no Python at runtime. That plan has a hidden cost the owner has now ruled out: it builds
the production model **twice** — once in Python (the trained artifact) and once in Julia (the ported
inference walker) — with a fragile ~1e-6 parity contract between them (categorical splits, missing-value
default direction, float32-vs-64 thresholds, LightGBM version drift). It also anchors S to a Python training
stack that must be re-ported every time the model changes.

Since S is **non-differentiable and lives outside the AD loop** (ADR 0018) and the whole stack is
**Julia-primary** (ADR 0007) with a pure-Julia coupled rollout (SpeedyWeather/Terrarium), there is a native
option that removes the double build entirely: **train and run S in Julia.**

## Decision

**Build the flux-driven S (ADR 0020) as a single, native-Julia component. Do not build the production S
twice.**

1. **The trained, coupled S is native Julia.** Distributional / count model: **EvoTrees.jl** (gradient-boosted
   trees, pure Julia, quantile + count objectives) or a Julia Distributional-Random-Forest; any NN parts:
   **Lux**; copula / quantile sampling: **hand-rolled Julia** (the Gaussian-copula Cholesky + inverse-CDF
   the design already specified for the Julia side, on `Random.Xoshiro`). It must be **dependency-light and
   callable inside the SpeedyWeather/Terrarium rollout with NO Python at runtime.**
2. **Python is confined to two throwaway/offline roles only:** (a) **build and align the training table** —
   the F-flux + mortality-driver features (ADR 0020) against the `ind` trait/size distribution
   (`docs/slow_flux_conditioning_data_spec.md`); (b) **run the climate-only `DirectEmulator` as the OOD
   benchmark** (the ADR-0020 falsifiable success test). A quick Python prototype of the new flux features for
   research iteration is allowed but is **throwaway** — port the chosen design to Julia **before the P1
   gate**. No `src/slow_infer.jl` Python-inference port; no committed Python-model artifact that the Julia
   side must reproduce bit-for-bit.
3. **Deps / packaging (honors ADR 0014).** EvoTrees.jl and Lux are pure-Julia and available from the
   Julia pkg-server (offline-compute-node safe — no GitHub egress needed). The differentiable core `src/`
   (F_diff, the coupled loop, the `AbstractSlowEmulator` interface, and the dep-free Tier-0
   `DemographicSlowEmulator`) stays **pure-Base with empty runtime `[deps]`**. The native-Julia **learned**
   S ships via the **package-extension mechanism** (weakdeps EvoTrees / Lux), exactly as the learned F_diff
   closures ship in `ext/FDiffTrainingExt.jl` — so Aqua stays clean and the ML deps load only when present
   (they will be, in the coupling app's environment). *Reversible:* a later ADR may promote EvoTrees to a
   bounded direct runtime dep if the extension pattern proves awkward for the coupled rollout.

## Consequences

- **Obsoletes** the planned `src/slow_infer.jl` (GBDT text-walk / `Φ`-`Φ⁻¹` / Python-parity fixture) and
  **rescopes** `scripts/export_slow_hainich.py` from "export a model artifact to port" to "export the
  aligned **training table** + the DirectEmulator OOD predictions." The P1 design-doc Steps 4/5/8 are
  re-scoped accordingly (native training in Julia, not a port).
- The Tier-0 `DemographicSlowEmulator` (dep-free, physical-rate, already in the loop and conserving) is
  **unchanged** — it remains the wiring + conservation scaffold; the native-Julia learned model plugs into
  the same `AbstractSlowEmulator` / `reconcile_demography!` interface, supplying the count + recruit-trait
  predictions that Tier-0 currently draws from constant/physical rates.
- **Single source of truth, no parity contract.** The model that is validated (Gate-3 panel + oracle) is
  the same model that runs coupled — no LightGBM↔Julia drift risk.
- The P1 gate now requires the **native-Julia** flux-driven S (not a Python model) to beat the climate-only
  `DirectEmulator` on the warm+dry OOD holdout (ADR 0020's falsifiable test).

## Relationship to prior ADRs

- **Supersedes the *mechanism* of ADR 0019** (port Python inference → native Julia training+inference);
  keeps ADR 0019's *intent* (no Python at runtime; core stays dep-free).
- **Consistent with ADR 0007** (Julia-primary), **ADR 0014** (empty core `[deps]`; learned parts in an
  extension), **ADR 0018** (S non-differentiable, outside the AD loop — EvoTrees need not be
  differentiable), and **ADR 0020** (the flux-driven conditioning contract is unchanged; only the
  implementation language/toolchain is fixed here).
