# Component F — fast physical biophysical core kept from LPJmL-FIT (daily). DEVELOPMENT_PLAN §2.3.
# F1 (Phases 3-5): keep the LPJmL-FIT C core, driven via a callable interface (feasibility spike first —
#   the binary exposes `-couple host[:port]`, a candidate path). F2 (Phase 6): differentiable rewrite.

"""
    AbstractFastCore

Interface for the fast physical core F. Given structural boundary conditions from S ([`SToF`](@ref))
and atmospheric forcing ([`AtmForcing`](@ref)), F integrates the daily biophysics (photosynthesis→GPP→NPP,
water balance, snow, soil thermal), mutating the shared soil water / snow / thermal / SOM state, and
returns the daily flux payload for E ([`FToE`](@ref)); at year-end it returns the conserved annual
increment for S ([`FToS`](@ref)). Conserving water & carbon by construction (inherited from LPJmL-FIT).
"""
abstract type AbstractFastCore end

"""
    step!(::AbstractFastCore, state::SharedState, bc::SToF, forcing::AtmForcing) -> FToE

Advance F by one day. **Not implemented in Phase 0** — F1 wraps the LPJmL-FIT C core
(`/home/jamirp/lpjml56fit`); see DEVELOPMENT_PLAN.md §6 Phase 3.
"""
step!(::AbstractFastCore, ::SharedState, ::SToF, ::AtmForcing) =
    error("Component F `step!` is not implemented yet — see DEVELOPMENT_PLAN.md §6 Phase 3.")
