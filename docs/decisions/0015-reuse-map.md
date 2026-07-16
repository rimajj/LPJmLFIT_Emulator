---
status: "accepted"
date: 2026-07-16
deciders: "Jamir Priesner (owner)"
consulted: "ADR 0014 (differentiable fast core first); ECOSYSTEM_AND_COUPLING.md §1/§6; the reference repos LPJmL-hybrid-photosynthesis, NeuralCrop.jl, Terrarium.jl; the LPJmL-FIT C source"
informed: "CITATION.cff, docs bibliography, source-file headers (src/allometry.jl, src/fdiff.jl), MEMORY.md, JOURNAL.md"
---

# Reuse map for the differentiable fast core (what to TAKE / REDO / SKIP, and the citations)

## Context and Problem Statement

ADR 0014 builds the fast core F differentiable from the start (`F_diff`) by **reusing the reference
repos** rather than re-deriving the physics. This ADR records the concrete shopping list — what is
taken from which repo, what is redone from the LPJmL-FIT C source, what is skipped — and the
citation/attribution obligations. It is the audit trail for "where did each piece of F_diff come
from?" (ENGINEERING_STANDARDS §4: ADRs are the primary artifact for auditing AI-built code.)

Reuse is for **research use with attribution**; no license "clearing" is required to use these as
references and port equations, but the attributions below are mandatory and the licensing note
(bottom) flags what a future public/commercial **redistribution** would need.

## Decision Drivers

- Faithful "same physics" (ADR 0014): the LPJmL-FIT C binary is the oracle, so C-source constants win
  over any divergent reference-repo values.
- Minimise re-derivation; maximise reuse of the same-institute differentiable-programming machinery.
- Keep attribution correct and auditable per source file.

## Decision Outcome

Adopt the following **reuse map**. Source-file headers, `CITATION.cff`, and the docs bibliography
carry the citations; the port specs (session artifacts) hold the line-level extraction.

### TAKE from **LPJmL-hybrid-photosynthesis** (TUM-PIK-ESM; **MIT**) — primary photosynthesis reference
- The **differentiable λ (ci:ca) root-find**: the residual `g(λ)=fac·(1−λ)−adtmm(λ)=0` (Eqn 18,
  Haxeltine & Prentice 1996) and its **implicit/adjoint** differentiation
  (`SteadyStateAdjoint(autojacvec=EnzymeVJP())` over `NewtonRaphson(autodiff=false)`) — the pattern,
  not verbatim (see "Divergences" for what F_diff does instead in the spike).
- The **C3/C4 coupled photosynthesis kernel** and its LPJmL parameter constants (`photosynthesis.jl`,
  `default_parameters.jl`).
- Repo: `github.com/TUM-PIK-ESM/LPJmL-hybrid-photosynthesis`.

### TAKE from **NeuralCrop.jl** (Yunan Lin, Boers group; **CC-BY-NC**) — shared LPJmL physics + DP machinery
- Differentiable **C3/C4 photosynthesis with NN-parameterizable λ/Vcmax hooks**.
- **Priestley–Taylor PET**, transpiration/evaporation/interception, temperature stress, respiration
  (Lloyd–Taylor `gtemp`) — `radiation.jl`, `transpiration.jl`, `evaporation.jl`, `respiration.jl`.
- **Soil carbon (fast/slow) + litter turnover + soil-water** as neural-ODEs.
- The **neural-ODE + custom differentiable Euler solver**, the **rollout / TBPTT** training loop,
  KernelAbstractions GPU wrappers, input normalization, and the **"detach physics with
  `Zygote.ignore` / differentiate only NN outputs"** idiom.
- The **two-stage training recipe** (pretrain on LPJmL output → fine-tune on FLUXNET fluxes).
- **NOTE (verified this session):** the public **training/loss DRIVER is a scaffold** — the loss,
  daily-driver, and loop have mutually-inconsistent signatures and reference undefined variables
  (`ps_frozen`, `dailyWeather`); it will not run as written. The **physics kernels and patterns port
  cleanly**; the training loop must be finished/fixed. AD backend actually used is **Zygote** (Enzyme
  is a declared-but-unused dep).
- Repo: `github.com/yunan-l/NeuralCrop.jl`; paper **arXiv:2512.20177**.

### REDO from the **LPJmL-FIT C source** (AGPL-3.0; `/home/jamirp/lpjml56fit`, v5.6.004) — crops are useless here
- The **allometry/diagnostics library** (`src/allometry.jl`): tree height (**pipe model / La:Sa**,
  NOT `allom2·D^allom3`), crown area + stem diameter (**Jucker et al. 2022**, NOT Reinicke —
  `reinickerp` is `#define`d but UNUSED in the fork), `LAI=leafC·SLA/crownarea`, FPC (Beer–Lambert),
  bark thickness. From `allometry_tree.c`/`lai_tree.c`/`fpc_tree.c`.
- The **canonical photosynthesis + water-balance + PET constants** that F_diff must reproduce
  (`photosynthesis.c`, `water_stressed.c`, `petpar.c`): θ=0.7, ALPHAM=1.391, GM=3.26, α_PT=1.32,
  α_c3=0.08, etc. — these **override** any divergent reference-repo values (NeuralCrop's crop θ=0.9,
  ALPHAM=1.485 are NOT used).
- The **advanced soil THERMAL scheme** (23-layer enthalpy + permafrost) is a scale-up REDO — or reuse
  Terrarium.jl's differentiable soil thermal (ADR 0006). NeuralCrop's 5-layer bucket is too coarse.
  (The spike uses a single-bucket soil-water + degree-day snow; multi-layer thermal is deferred.)

### REUSE later from **Terrarium.jl** (NumericalEarth; **EUPL-1.2**) — component E (Phase 4)
- `SurfaceEnergyBalance` + `ImplicitSkinTemperature` (already differentiable) — ADR 0006. Not in the
  F_diff spike.

### SKIP entirely
- Crop phenology (sowing/harvest/PHU/vernalization), management (fertilizer/tillage), and the
  **NITROGEN cycle** (config runs `with_nitrogen="no"` — the reason for the constant-CO₂ regime, ADR 0004).

### Divergences the spike deliberately made (recorded for audit)
- **λ solve:** the spike uses a **fixed-graph damped Newton** (finite-difference `g'`, no
  data-dependent branch) instead of `SteadyStateAdjoint`+`EnzymeVJP`. Reason: it is dependency-free,
  and both ForwardDiff and **Enzyme reverse-mode** differentiate it correctly (matching finite
  differences to ~1e-11) end-to-end through the rollout, which the adjoint path did not need to be
  imported for. The SteadyStateAdjoint route is retained as the **scale-up** option (avoids the
  solver-path memory blow-up the reference notes for large grids). See `docs/phase3_fdiff_spike.md`.
- **273.15 K everywhere.** The hybrid repo ships a **272.15-vs-273.15 K bug** in its `degCtoK`/
  `KtodegC` helpers (`unit_conversion.jl:20-32`); F_diff uses 273.15 exactly (unit test guards it).
- **Two Priestley–Taylor coefficients** (1.32 soil/PET, 1.391 transpiration), per the C source.

### Consequences

- Good, because every ported piece has a cited origin and a documented divergence — fully auditable.
- Good, because using C-source constants as authoritative keeps the "same physics" claim honest.
- Bad/obligation, because **attribution is mandatory** in source headers, `CITATION.cff`, and the docs
  bibliography (done for the spike's files).
- Risk (licensing), because **NeuralCrop is CC-BY-NC** and **LPJmL is AGPL-3.0**: research use with
  attribution is fine, but any **commercial use or code redistribution** of derived work needs a
  written legal read (CC-BY-NC forbids commercial; AGPL is strong copyleft; Terrarium/SpeedyWeather
  EUPL-1.2). This is unchanged from the standing TODO in MEMORY.md and is NOT triggered by
  research-use porting.

## More Information

- Depends on / implements: **ADR 0014** (differentiable fast core first).
- Line-level extraction: the session port specs (photosynthesis kernel, λ solve, C allometry,
  C photosynthesis/water, NeuralCrop PET/ET/respiration, AD/rollout machinery, Terrarium SEB).
- Citations rendered in: `src/allometry.jl` + `src/fdiff.jl` headers, `CITATION.cff`,
  `docs/phase3_fdiff_spike.md` bibliography.
- ADRs are immutable once accepted — supersede rather than edit.
