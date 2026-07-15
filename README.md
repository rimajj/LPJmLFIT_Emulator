# ESM-Ready LPJmL-FIT Hybrid Land Component

[![CI](https://github.com/rimajj/LPJmLFIT_Emulator/actions/workflows/CI.yml/badge.svg)](https://github.com/rimajj/LPJmLFIT_Emulator/actions/workflows/CI.yml)
[![Docs](https://github.com/rimajj/LPJmLFIT_Emulator/actions/workflows/docs.yml/badge.svg)](https://github.com/rimajj/LPJmLFIT_Emulator/actions/workflows/docs.yml)
[![codecov](https://codecov.io/gh/rimajj/LPJmLFIT_Emulator/branch/main/graph/badge.svg)](https://codecov.io/gh/rimajj/LPJmLFIT_Emulator)
[![code style: runic](https://img.shields.io/badge/code_style-runic-000000.svg)](https://github.com/fredrikekre/Runic.jl)

> **Status:** Phase 0 (DESIGN) complete — schemas frozen, engineering scaffold in place. Modelling code grows from here under the phased plan.
> Private repo: `github.com/rimajj/LPJmLFIT_Emulator`. Badges render in the owner's authenticated view (private repo). Julia package name: `LPJmLFITEmulator`.

A **hybrid** land-surface component derived from **LPJmL-FIT** (LPJmL 5.6.004 + flexible individual traits), built to drive an Earth-System-Model atmosphere. Three components around **one authoritative shared state**:

| | Component | Timescale | What it is |
|---|---|---|---|
| **S** | Slow trait/size **distribution** emulator | annual | **ML** — emulates the per-cell distribution over trees `p(traits, size ∣ drivers, state)` + count `N`. The scientific novelty. |
| **F** | Fast physical biophysical core | daily | **Kept from LPJmL-FIT** — photosynthesis→GPP→NPP, water balance, snow, soil thermal. Conserving water & carbon *by construction*. |
| **E** | Surface-energy-balance + skin-temperature closure | daily→sub-daily | **New** (reuse Terrarium.jl) — the ESM interface LPJmL-FIT lacks: solves `T_skin`, partitions available energy into `LE / H / G`. |

Carbon and water conservation are **inherited from the physical core**; the energy budget is **closed by construction** in E. The coupling variables (LE, H, G, T_skin, NEE, roughness) are **derived, not co-predicted**.

## How to read this repository (for the owner / non-coder)

You do **not** need to read code. Everything is designed so you can understand and control the project from documentation that is **kept honest by CI** (if the code and the docs diverge, the build fails).

1. **Start with the docs site** (Documenter.jl — the single source of truth). Build locally with `julia --project=docs docs/make.jl`, then open `docs/build/index.html`. Read the **Explanation** and **Model description** sections.
2. **The science**, in order: [`DESIGN.md`](DESIGN.md) (what is frozen and why) → `docs` *Explanation* → the GMD-style *Model description*.
3. **Why any decision was made:** [`docs/decisions/`](docs/decisions/) — one **ADR** per non-trivial choice (problem → options → decision → consequences).
4. **Where a piece sits:** the **diagrams** (components S/F/E, fast↔slow coupling, data/flux flow) — curated + auto-generated-from-code so they can't silently go stale.
5. **Project state & history:** [`MEMORY.md`](MEMORY.md) (durable facts, current status) and [`JOURNAL.md`](JOURNAL.md) (running log).

## Repository layout

```
esm_land_emulator/
├── src/                 Julia package (S/F/E, shared state, interface contract, conservation helpers)
├── test/                @testitem scientific gates (conservation, gradients, rollout stability, resilience …)
├── docs/                Documenter.jl site (Diátaxis) + decisions/ (ADRs) + GMD model description
├── scripts/             gen_diagrams.jl (code/config-derived diagrams), run helpers
├── python/              slow-emulator (S) prototype (LightGBM/copula; uv + pytest + Hypothesis)
├── config/              paths.yaml, hpc_slurm.yaml, environment.yml  (config-driven; no magic numbers)
├── .github/workflows/   CI, format (Runic), docs (doctests+linkcheck), python, TagBot
├── DESIGN.md            Phase-0 frozen schemas (state vector, interface, data, run recipe)
├── DEVELOPMENT_PLAN.md  phased plan + checkpoints (§6)
├── SOURCE_FINDINGS.md · RESEARCH_SURVEY.md · ECOSYSTEM_AND_COUPLING.md
├── MEMORY.md · JOURNAL.md · ENGINEERING_STANDARDS.md
```

## Stack

**Julia-primary** (Enzyme/Lux/SciML/KernelAbstractions) for the fast core and coupled/online-trainable system; **Python** (`/home/jamirp/.conda/envs/py311_new`) only for the slow-emulator (S) prototype. Target ecosystem: SpeedyWeather.jl + Terrarium.jl + NumericalEarth.jl (see [`ECOSYSTEM_AND_COUPLING.md`](ECOSYSTEM_AND_COUPLING.md)).

## Engineering standard

Every merged PR must pass CI (tests incl. the scientific gates), formatting (Runic), and docs (doctests + linkcheck); update docs/docstrings; regenerate derived diagrams; add/undate an ADR for non-trivial decisions; and keep `CHANGELOG.md`, `MEMORY.md`, `JOURNAL.md` current. Full spec: [`ENGINEERING_STANDARDS.md`](ENGINEERING_STANDARDS.md).

## License

To be set by the owner. **Caveat:** LPJmL-FIT is **AGPL-3.0**; Terrarium.jl / SpeedyWeather.jl are **EUPL-1.2**; NeuralCrop is **CC-BY-NC**. Any cross-repo code embedding needs a written legal read first (tracked as an open ADR).
