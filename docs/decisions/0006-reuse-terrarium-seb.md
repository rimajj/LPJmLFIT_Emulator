---
status: "superseded by ADR 0017"
date: 2026-07-15
deciders: "Jamir Priesner (owner)"
consulted: "ECOSYSTEM_AND_COUPLING.md §2, DEVELOPMENT_PLAN.md §2.4, DESIGN.md §1.2/§3.4"
informed: "ADR 0007, component E"
---

> **Superseded by [ADR 0017](0017-self-contained-energy-closure.md)** (2026-07-22): the *implementation
> choice* (reuse Terrarium.jl) is superseded — component E is reimplemented self-contained (dependency-free,
> AD-friendly) because of this ADR's own flagged open AGPL↔EUPL licensing blocker + the zero-runtime-deps /
> offline-compute-node constraints, exactly as ADR 0014 did for the fast core. **The physics decisions
> below (one consistent skin temperature, H the residual, G under T_skin, the mandatory E→F feedback) are
> RETAINED.**

# Reuse Terrarium.jl's surface energy balance + skin temperature for component E

## Context and Problem Statement

LPJmL-FIT has **no** surface energy balance — no sensible heat `H`, no net-radiation closure, no skin
temperature (`DESIGN.md` §1.2). Component E must supply these. Build the physics from scratch, or
reuse an existing implementation? See `ECOSYSTEM_AND_COUPLING.md` §2.

## Decision Drivers

- Minimise new-physics build risk (the largest in the plan).
- Need **one consistent skin temperature** so `Rn`, `H`, `G` refer to the same surface.
- GPU/AD-readiness and a path to atmosphere coupling.

## Considered Options

- **Build a new SEB + skin-temperature solver** from scratch.
- **Reuse Terrarium.jl** (`SurfaceEnergyBalance` + `ImplicitSkinTemperature` + soil thermal/hydrology)
  — same PIK/TUM ecosystem as LPJmL, Enzyme-AD, GPU.
- **Reuse another LSM's SEB** (e.g. CliMA).

## Decision Outcome

Chosen: **reuse Terrarium.jl's SEB + `ImplicitSkinTemperature`**. It already implements exactly what
LPJmL-FIT lacks, provides a consistent ground-heat `G` under one skin temperature (resolving the
"different surfaces" concern), and gives the aerodynamic (wind/pressure) machinery the interface
needs — while slotting into the SpeedyWeather coupling route for free. "Greenfield" meant *absent from
LPJmL-FIT*, not build-from-scratch.

### Consequences

- Good: removes the biggest new-build risk; consistent `T_skin`/`G`; GPU + Enzyme-AD path; coupling
  route included.
- Good: the `E → F` skin-temperature feedback (mandatory top thermal BC) has a ready implementation.
- Bad: Terrarium is **v0.1.x — expect breakage**; treat as co-development, not a frozen dependency.
- Bad (open blocker): **licensing** — LPJmL AGPL-3.0 ↔ Terrarium EUPL-1.2 needs a written legal read
  before embedding code across repos (`DESIGN.md` §3.4).
- Bad: `H` remains the documented residual and the least-controlled flux — validate hardest vs
  FLUXNET/PLUMBER2.

## More Information

The ML role in E is only a **bounded** correction to `g_a`/`T_skin` inside the closed balance; the
physics owns closure. Fast-core template (F2): LPJmL-hybrid-photosynthesis / NeuralCrop
(`ECOSYSTEM_AND_COUPLING.md` §1). Coupling target: SpeedyWeather.jl for the online demo, CliMA/ICON
for a real ESM.
