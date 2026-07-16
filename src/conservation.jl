# Conservation-by-construction helpers (DESIGN.md §8; DEVELOPMENT_PLAN §2.2; RESEARCH_SURVEY C).
# These are REAL, tested functions (the §2 scientific gates exercise them). Prefer partitions over
# residuals; the ONE documented residual is sensible heat H in the energy layer (LE is water-limited).

"Latent heat of vaporization of water, J/kg (liquid ET). DESIGN.md §2.4."
const LAMBDA_VAPORIZATION = 2.5e6
"Latent heat of sublimation, J/kg (snow/ice ET). ≈13% larger than vaporization — do not conflate."
const LAMBDA_SUBLIMATION = 2.83e6

"""
    softmax_partition(logits) -> fractions

Map real `logits` to non-negative `fractions` that **sum to 1** (softmax). The safe hard mass
constraint: multiply a conserved input (NPP, available energy) by these to split it without
inventing or destroying the total (Kraft et al. 2022; Harder et al. 2024). Numerically stabilised
by subtracting the max.

```jldoctest
julia> using LPJmLFITEmulator

julia> f = softmax_partition([0.0, 0.0, 0.0]);

julia> (sum(f), length(f))
(1.0, 3)
```
"""
function softmax_partition(logits::AbstractVector{<:Real})
    m = maximum(logits)
    e = exp.(logits .- m)
    return e ./ sum(e)
end

"""
    flux_then_integrate(state, increments) -> new_state

Advance a storage/pool vector by conserved `increments` (MC-LSTM / flux-then-integrate style):
`new_state = state + increments`, then clamp to non-negativity. Carbon/mass is only moved, never
created — the increments are what a conserved input was partitioned into. DEVELOPMENT_PLAN §2.2.
"""
function flux_then_integrate(state::AbstractVector{T}, increments::AbstractVector{T}) where {T <: Real}
    length(state) == length(increments) ||
        throw(DimensionMismatch("state and increments must match"))
    return max.(state .+ increments, zero(T))
end

"""
    carbon_budget_residual(; npp, rh, firec, flux_estabc, dC) -> residual

Ecosystem carbon closure with **fire ON (GlobFIRM)** and establishment (DESIGN.md §3.2):

    ΔC = NPP − Rh − firec + flux_estabc      ⟹   residual = ΔC − (NPP − Rh − firec + flux_estabc)

A fire-free `NEE = Rh − NPP` will NOT close. The conservation test asserts `|residual| ≤ tol`.
"""
carbon_budget_residual(; npp, rh, firec, flux_estabc, dC) =
    dC - (npp - rh - firec + flux_estabc)

"""
    nbp_atm(; rh, firec, npp, flux_estabc) -> flux

Atmosphere-facing net biome production the land hands the atmosphere:

    NBP_atm = Rh + firec − NPP − flux_estabc

(Biological NEE = Rh − NPP is only the fire-free, establishment-free part.) DESIGN.md §3.2/§8.
"""
nbp_atm(; rh, firec, npp, flux_estabc) = rh + firec - npp - flux_estabc

"""
    water_budget_residual(; prec, et, runoff, drainage, dstorage) -> residual

Water closure (DESIGN.md §3.3/§7): `P = ET + runoff + drainage + ΔStorage(soil+snow+interception)`.
`residual = prec − (et + runoff + drainage + dstorage)`; the test asserts `|residual| ≤ tol`.
"""
water_budget_residual(; prec, et, runoff, drainage, dstorage) =
    prec - (et + runoff + drainage + dstorage)

"""
    latent_heat(et; sublimation=false) -> LE

Derive latent heat from evapotranspiration: `LE = λ·ET`. Uses λ of **vaporization** for liquid ET
and of **sublimation** for the snow/ice component (`sublimation=true`) — never predicted
independently (DESIGN.md §2.4). `et` in kg/m²/s ⇒ `LE` in W/m².
"""
latent_heat(et::Real; sublimation::Bool = false) =
    et * (sublimation ? LAMBDA_SUBLIMATION : LAMBDA_VAPORIZATION)
