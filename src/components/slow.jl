# Component S — slow trait/size DISTRIBUTION emulator (annual). DEVELOPMENT_PLAN §2.2.
# The scientific novelty: emulate the per-cell distribution p(traits,size | drivers,state) + count N,
# and advance the population by flux-then-integrate (allocate exactly the NPP F delivered).

"""
    AbstractSlowEmulator

Interface for the slow ML component S. A concrete emulator maps conditioning (annual climate summary,
CO₂, soil, previous-year distribution summary, 20-yr `Climbuf` memory, stand age, the delivered
`bm_inc`, and the four mortality drivers) to the new-year trait×size distribution + count `N`, then
derives structural boundary conditions ([`SToF`](@ref)/[`SToE`](@ref)) for F and E via the model's own
allometry. Carbon is conserved at the handoff by advancing the existing population, not regenerating it.

Baseline method: Distributional Random Forest + a negative-binomial/ZINB count model (escalate to
tabular diffusion / conditional normalizing flow only if the metric panel demands it).
"""
abstract type AbstractSlowEmulator end

"""
    step!(::AbstractSlowEmulator, state::SharedState, drivers::FToS) -> (SToF, SToE)

Advance S by one year, mutating the vegetation carbon in `state`, and return the structural
boundary conditions for F and E. **Not implemented in Phase 0** (grows in Phase 2/3).
"""
step!(::AbstractSlowEmulator, ::SharedState, ::FToS) =
    error("Component S `step!` is not implemented yet — see DEVELOPMENT_PLAN.md §6 Phase 2.")
