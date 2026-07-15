"""
    LPJmLFITEmulator

ESM-ready **hybrid** land-surface component derived from LPJmL-FIT.

Three components around **one authoritative shared state** ([`SharedState`](@ref)):

  - **S** — slow ML trait/size *distribution* emulator (annual): [`AbstractSlowEmulator`](@ref).
  - **F** — fast physical biophysical core kept from LPJmL-FIT (daily): [`AbstractFastCore`](@ref).
  - **E** — surface-energy-balance + skin-temperature closure (new; reuse Terrarium.jl):
    [`AbstractEnergyClosure`](@ref).

Water and carbon are conserved by the physical core; the energy budget is closed by
construction in E. Coupling variables (LE, H, G, T_skin, NEE, roughness) are **derived, not
co-predicted** — see [`conservation.jl`](@ref LPJmLFITEmulator) helpers.

This is the Phase-0 skeleton: types, the interface contract, and conservation helpers are
real and tested; the modelling components are stubs that grow under `DEVELOPMENT_PLAN.md` §6.
Frozen schemas: `DESIGN.md`.
"""
module LPJmLFITEmulator

# ── Shared state & constants (DESIGN.md §2) ─────────────────────────────────
include("state.jl")
# ── S↔F↔E interface contract (DESIGN.md §8) ─────────────────────────────────
include("interface.jl")
# ── Conservation-by-construction helpers (DESIGN.md §8, DEVELOPMENT_PLAN §2.2) ─
include("conservation.jl")
# ── Component abstract types + Phase-N stubs ────────────────────────────────
include("components/slow.jl")
include("components/fast.jl")
include("components/energy.jl")
# ── Component/flux registry — source of truth for code-derived diagrams ─────
include("registry.jl")

# State
export SharedState, NSOILLAYER, LASTLAYER, GPLHEAT, NHEATGRIDP, NTREEPOOLS, CLIMBUFSIZE
# Interface payloads
export SToF, SToE, FToS, FToE, EToF, EToATM, AtmForcing
# Conservation helpers
export softmax_partition, flux_then_integrate,
    carbon_budget_residual, water_budget_residual, nbp_atm, latent_heat,
    LAMBDA_VAPORIZATION, LAMBDA_SUBLIMATION
# Components
export AbstractSlowEmulator, AbstractFastCore, AbstractEnergyClosure
# Registry
export COMPONENTS, FLUXES, Component, Flux

end # module
