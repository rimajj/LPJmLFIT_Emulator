# Component E — surface-energy-balance + skin-temperature closure (new). DEVELOPMENT_PLAN §2.4.
# The ESM interface LPJmL-FIT lacks. Reuse Terrarium.jl's SurfaceEnergyBalance + ImplicitSkinTemperature
# (ECOSYSTEM_AND_COUPLING.md). Physics owns closure; any ML only reshapes g_a/T_skin WITHIN the balance.

"""
    AbstractEnergyClosure

Interface for the energy closure E. Solves one skin temperature `T_skin` from
`Rn(T_skin) = SWdown(1−α) + LWdown − εσT_skin⁴` and closes `Rn = LE + H + G` with
`H = ρ c_p g_a (T_skin − Tair)`. **LE is fixed by water availability** (from F), so **H is the
residual** — a documented, deliberate exception to "no privileged residual" (validate hardest vs
FLUXNET). Returns [`EToATM`](@ref) for the atmosphere and [`EToF`](@ref) (the mandatory skin-T
feedback) so F's ground heat is consistent with the one surface temperature.
"""
abstract type AbstractEnergyClosure end

"""
    solve!(::AbstractEnergyClosure, state::SharedState, from_f::FToE, bc::SToE, forcing::AtmForcing)
        -> (EToATM, EToF)

Solve the surface energy balance for `T_skin` and partition available energy. **Not implemented in
Phase 0** — reuse Terrarium.jl; see DEVELOPMENT_PLAN.md §6 Phase 4. Requires the NEW forcings `wind`
and `psurf`.
"""
solve!(::AbstractEnergyClosure, ::SharedState, ::FToE, ::SToE, ::AtmForcing) =
    error("Component E `solve!` is not implemented yet — see DEVELOPMENT_PLAN.md §6 Phase 4.")
