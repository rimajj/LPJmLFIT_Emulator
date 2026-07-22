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

# ── The flux-then-integrate carbon LEDGER for the S↔F demographic handoff (P1; ADR 0018/0019) ──────
# When the slow emulator S changes the population (establishment / mortality / merge), every carbon
# movement must be an ACCOUNTED flux so nothing is created or destroyed at the handoff. `SharedState`'s
# scalar litter/veg fields are immutable in v1, so the handoff carries its OWN mutable carbon sink.
# Type-agnostic (scalars only — this file is included BEFORE `fdiff.jl`): the caller computes per-cohort
# vegetation carbon via `FDiff.vegc_full_ind` (which INCLUDES `sapwood_bg_c`; routing mortality on
# `vegc_ind` would silently leak a seeded below-ground pool). See `docs/p1_s_in_loop_design.md` §4.

"""
    CarbonLedger{T}

Mutable per-cell carbon ledger for the annual S↔F demographic handoff (ADR 0018). Holds the running
litter sink `litter_total` plus the CURRENT-YEAR flux tallies [`handoff_carbon_residual`](@ref) closes on:
`litter_year` (carbon moved vegetation→litter this year — turnover litterfall + whole-individual
mortality), `estab_year` (establishment carbon influx = `flux_estabc`), `applied_bm_year` (NPP actually
integrated into pools by F this year), and `unapplied_bm_year` (delivered-but-unapplied NPP of stagnating
cohorts — a BOUNDED DIAGNOSTIC of the fixed-N F approximation, not a closed flux). [`reset_year!`](@ref)
the tallies each year; `litter_total` accumulates (no litter decomposition in v1).
"""
mutable struct CarbonLedger{T <: AbstractFloat}
    litter_total::T
    litter_year::T
    estab_year::T
    applied_bm_year::T
    unapplied_bm_year::T
end
CarbonLedger{T}() where {T <: AbstractFloat} = CarbonLedger{T}(zero(T), zero(T), zero(T), zero(T), zero(T))
CarbonLedger() = CarbonLedger{Float64}()

"Zero the current-year flux tallies of a [`CarbonLedger`](@ref) (the running `litter_total` is kept)."
function reset_year!(l::CarbonLedger{T}) where {T}
    l.litter_year = zero(T)
    l.estab_year = zero(T)
    l.applied_bm_year = zero(T)
    l.unapplied_bm_year = zero(T)
    return l
end

"Route `c` gC/m² of carbon vegetation→litter (turnover litterfall or whole-individual mortality)."
function record_litter!(l::CarbonLedger{T}, c) where {T}
    Δ = convert(T, c)
    l.litter_total += Δ
    l.litter_year += Δ
    return l
end

"Record `c` gC/m² of establishment carbon influx (the `flux_estabc` debited for new saplings)."
record_estab!(l::CarbonLedger{T}, c) where {T} = (l.estab_year += convert(T, c); l)

"Record F's delivered NPP: `applied` gC/m² integrated into pools + `unapplied` gC/m² left on stagnating cohorts."
function record_growth!(l::CarbonLedger{T}, applied, unapplied) where {T}
    l.applied_bm_year += convert(T, applied)
    l.unapplied_bm_year += convert(T, unapplied)
    return l
end

"""
    handoff_carbon_residual(l::CarbonLedger; c_veg_delta) -> Real

The S↔F handoff carbon-closure residual (ADR 0018). With fire and heterotrophic respiration OUT of the
demographic handoff (v1), the total ecosystem carbon change `Δ(C_veg + C_litter)` must equal the external
influxes `applied_bm + flux_estabc` — mortality and turnover are internal vegetation→litter moves that
cancel. So

    residual = carbon_budget_residual(; npp = applied_bm_year, rh = 0, firec = 0,
                                        flux_estabc = estab_year, dC = c_veg_delta + litter_year)

where `c_veg_delta` is the caller-supplied change in total vegetation carbon `Σ vegc_full_ind·nind`
(gC/m²) across the year. The conservation gate asserts `|residual| ≤ 1e-6·C_scale`.
"""
function handoff_carbon_residual(l::CarbonLedger{T}; c_veg_delta) where {T}
    return carbon_budget_residual(;
        npp = l.applied_bm_year, rh = zero(T), firec = zero(T),
        flux_estabc = l.estab_year, dC = convert(T, c_veg_delta) + l.litter_year,
    )
end
