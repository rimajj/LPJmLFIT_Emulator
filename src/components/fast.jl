# Component F — fast physical biophysical core (daily). DEVELOPMENT_PLAN §2.3.
# DIFFERENTIABLE-FIRST (ADR 0014): the concrete daily biophysics lives in the `FDiff` submodule
# (`src/fdiff.jl`) — a from-scratch AD-friendly reimplementation with the SAME equations, verified
# end-to-end differentiable (Enzyme/ForwardDiff vs finite differences; `docs/phase3_fdiff_spike.md`).
# The compiled LPJmL-FIT C binary is retained ONLY as the numerical-regression oracle + data
# generator, NOT the coupling path. This `AbstractFastCore` interface (which mutates the shared
# `SharedState`) is the eventual coupling surface; wiring `FDiff` behind it — mapping `FDiff`'s
# lightweight state to `SharedState`, multi-layer soil — is a documented scale-up step (spike report),
# so the abstract `step!` still throws until that adapter lands.

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

Advance F by one day. The differentiable daily biophysics is implemented in the `FDiff` submodule
(`FDiff.daily_step` / `FDiff.rollout`); this `SharedState`-mutating adapter is the coupling surface
and is not wired yet (ADR 0014; scale-up step in `docs/phase3_fdiff_spike.md`), so it throws.
"""
step!(::AbstractFastCore, ::SharedState, ::SToF, ::AtmForcing) =
    error("Component F `step!` (SharedState adapter) is not wired yet — use `FDiff.daily_step`; see docs/phase3_fdiff_spike.md.")
