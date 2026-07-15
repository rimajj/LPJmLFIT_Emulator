---
status: "accepted"
date: 2026-07-15
deciders: "Jamir Priesner (owner)"
consulted: "ECOSYSTEM_AND_COUPLING.md §5, DEVELOPMENT_PLAN.md §1, ENGINEERING_STANDARDS.md"
informed: "ADR 0005, ADR 0006, the whole test/CI/docs stack"
---

# Julia-primary stack; Python only for the S prototype

## Context and Problem Statement

The target ESM ecosystem (SpeedyWeather.jl + Terrarium.jl + NumericalEarth.jl + NeuralCrop) is a
fully-Julia, Enzyme-differentiable stack from the same institute as LPJmL. The package's original
`environment.yml` is Python-only. Which language is primary? See `ECOSYSTEM_AND_COUPLING.md` §5.

## Decision Drivers

- End-to-end **differentiability** (Enzyme) for online/coupled training.
- Reuse of the target ecosystem (Terrarium SEB, SpeedyWeather coupling) without a cross-language
  bridge.
- Maturity of tabular/distributional ML tooling (Python-strong) for the S prototype.

## Considered Options

- **Python-primary** (PyTorch/JAX), bridge to the Julia atmosphere.
- **Julia-primary**, with Python retained only for the S baseline, then ported to Julia/Lux.
- **Pure Julia** from day one (including the S baseline).

## Decision Outcome

Chosen: **Julia-primary; Python only for the S prototype**. Build the fast core (F2) and the
coupled/online-trainable system in Julia (Enzyme.jl, Lux.jl/Flux.jl, SciML, KernelAbstractions), reuse
Terrarium/SpeedyWeather natively, and port the DRF/copula S baseline (prototyped in Python where the
tabular tooling is mature) to Julia/Lux for coupling. This supersedes the Python-only
`environment.yml` (kept for the S prototype).

### Consequences

- Good: native Enzyme AD end-to-end; direct reuse of the Julia ecosystem; no fragile Python↔Fortran/
  Julia bridge for the coupled system.
- Good: the whole engineering standard (Documenter.jl, TestItems/Aqua/JET, Runic, julia-actions) is
  Julia-first (ENGINEERING_STANDARDS §2–§4).
- Bad: two languages during Phase 2 (S prototype in Python), and a **port** step (Python → Julia/Lux)
  before coupling.
- Bad: some Julia deps are pre-1.0 (Terrarium, SpeedyWeather) — API churn.

## More Information

Julia 1.10 is the compat floor (`Project.toml`); Julia 1.10.0 is available on the cluster. Python env
is the existing `py311_new` (reuse, do not recreate; `config/hpc_slurm.yaml`). Reproducibility: commit
`Project.toml` **and** `Manifest.toml` (ENGINEERING_STANDARDS §7).
