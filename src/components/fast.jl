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

Advance F by one day. The differentiable daily biophysics lives in the `FDiff` submodule
(`FDiff.daily_step_canopy`); the concrete [`FDiffFastCore`](@ref) wires it behind this interface.
The abstract fallback throws for cores that have not implemented it.
"""
step!(::AbstractFastCore, ::SharedState, ::SToF, ::AtmForcing) =
    error("Component F `step!` (SharedState adapter) is not implemented for this core — use `FDiffFastCore` or `FDiff.daily_step_canopy`.")

# ── FDiffFastCore — the concrete SharedState adapter (scale-up step 6b; docs §12) ────────────────
# Wires the differentiable multi-individual canopy (`FDiff.daily_step_canopy`) behind
# `AbstractFastCore.step!`: it reads/writes the authoritative soil water in `SharedState`, self-computes
# phenology (GSI) + `eeq` (dynamic albedo) + daylength (from latitude), and accumulates the conserved
# per-individual `bm_inc` that the ANNUAL handoff ([`annual_step!`](@ref)) allocates into the prognostic
# canopy structure (`FDiff.grow_individual`) and returns to S as [`FToS`](@ref) — the flux-then-integrate
# S↔F coupling of DESIGN §8. This closes the "SharedState adapter" scale-up item (the interface no longer
# throws) on the Hainich prototype.
#
# v1 simplifications (documented):
#   • only the per-layer soil-water Vector `SharedState.w` (mutable) is written back in place; snowpack +
#     the veg-C pools live in the core (the `SharedState` SCALAR fields are immutable — a fully-mutating
#     adapter needs those made mutable, a Phase-4 refactor);
#   • net longwave is estimated `lwnet = lwdown − σ·tair⁴` (E will refine it with the skin temperature);
#   • the FToE carbon terms `rh`/`firec`/`flux_estabc` are 0 (SOM decomposition + GlobFIRM fire are
#     separate modules, not in F_diff), and `ground_heat` is 0 (E computes G from the skin temperature);
#   • Float64 primal (the FToS/FToE payloads are `{<:AbstractFloat}`); AD through the coupled rollout uses
#     `FDiff.rollout_canopy_years` directly (proven differentiable), not this struct-boundary adapter;
#   • the representative individuals are held by the core (S supplies them); `bc::SToF`'s aggregate
#     structure fields are consistency diagnostics until S attaches the individual set (interface.jl).
using ..FDiff
using ..Allometry: TreeAllometry

"""
    FDiffFastCore{T} <: AbstractFastCore

Concrete fast core wiring `FDiff`'s differentiable multi-individual canopy behind
[`AbstractFastCore`](@ref). Holds the daily parameters (`params`), the annual allocation/turnover
parameters (`alloc`) + shared allometry (`allom`), the prognostic per-individual structure (`pools`,
`FDiff.TreePools`) with the daily-canopy templates (`tmpls`, `FDiff.Individual`), the
shared 23-layer `soil` column, the cell latitude `lat`, and the mutable within-year state (day-of-year,
GSI phenology filters, previous-day water scalar, and the annual `bm_inc`/flux accumulators). Build one
for the Hainich prototype and drive it with [`step!`](@ref) (daily) + [`annual_step!`](@ref) (year-end).
"""
mutable struct FDiffFastCore{T <: AbstractFloat} <: AbstractFastCore
    params::FDiff.FDiffParams{T}
    alloc::FDiff.AllocParams{T}
    allom::TreeAllometry{T}
    tmpls::Vector{FDiff.Individual{T}}
    pools::Vector{FDiff.TreePools{T}}
    inds::Vector{FDiff.Individual{T}}
    soil::FDiff.SoilColumn{T}
    lat::T
    phen_params::FDiff.PhenParams{T}
    doy::Int
    phen::FDiff.PhenState{T}
    water_avail::T
    snowpack::T                 # snow water equivalent (mm) — held here (SharedState.snowpack is immutable, v1)
    bm_inc_acc::Vector{T}
    gpp_acc::T
    npp_acc::T
    et_acc::T
    wscal_acc::T
    nday::Int
end

"""
    FDiffFastCore(pools, tmpls, soil, lat; params, alloc, allom, phen_params) -> FDiffFastCore

Construct an [`FDiffFastCore`](@ref) from the prognostic per-individual structure `pools`
(`FDiff.TreePools`), the daily-canopy templates `tmpls`, the shared `soil` column, and the cell
latitude `lat` (°). Defaults use the beech (TeBS) parameter sets. The daily `FDiff.Individual`s
are (re)built from `pools` + the recomputed layered `fpar`.
"""
function FDiffFastCore(
        pools::Vector{FDiff.TreePools{T}}, tmpls::Vector{FDiff.Individual{T}}, soil::FDiff.SoilColumn{T},
        lat::Real; params = FDiff.tebs_params(T), alloc = FDiff.tebs_allocparams(T),
        allom = TreeAllometry{T}(), phen_params = FDiff.tebs_phenparams(T)
    ) where {T <: AbstractFloat}
    fpars = FDiff._patch_fpars(pools, allom)
    inds = FDiff.Individual{T}[FDiff.individual_from_pools(tmpls[i], pools[i], allom, fpars[i]) for i in eachindex(pools)]
    return FDiffFastCore{T}(
        params, alloc, allom, tmpls, pools, inds, soil, T(lat), phen_params,
        0, FDiff.PhenState{T}(), one(T), zero(T), zeros(T, length(pools)), zero(T), zero(T), zero(T), zero(T), 0,
    )
end

const _STEFAN_BOLTZMANN = 5.670374419e-8   # W/m²/K⁴

"""
    step!(fc::FDiffFastCore, state::SharedState, bc::SToF, forcing::AtmForcing) -> FToE

Advance the fast core one day: map the shared per-layer soil water (`SharedState.w`, fraction of WHC) to
the `FDiff.SoilColumn` plant-available mm, self-compute daylength / GSI phenology / dynamic-albedo
`eeq`, run one `FDiff.daily_step_canopy`, write the updated soil water back into `state.w` in place,
accumulate the conserved per-individual `bm_inc` + stand fluxes, and return the daily [`FToE`](@ref)
(`le = λ·ET` derived; `gpp`/`npp` from the canopy; SOM/fire/energy terms 0 in v1). See the type docs for
the v1 simplifications.
"""
function step!(fc::FDiffFastCore{T}, state::SharedState, bc::SToF, forcing::AtmForcing) where {T}
    fc.doy = fc.doy % 365 + 1
    whcs = fc.soil.whcs
    # SharedState soil water (fraction of WHC) → FDiff plant-available mm (top NSOILLAYER layers)
    nlay = length(whcs)
    w_mm = T[clamp(state.w[l], zero(T), one(T)) * whcs[l] for l in 1:nlay]
    st = FDiff.FDiffStateML{T}(w_mm, fc.snowpack)
    # atmospheric forcing → DailyForcing (tair K→°C; lwnet from lwdown; daylength from latitude)
    temp = T(forcing.tair) - T(273.15)
    lwnet = T(forcing.lwdown) - _STEFAN_BOLTZMANN * T(forcing.tair)^4
    dl = FDiff.petpar_daylength(fc.lat, fc.doy)
    f = FDiff.DailyForcing{T}(
        swdown = T(forcing.swdown), lwnet = lwnet, temp = temp, precip = T(forcing.precip),
        daylength = T(dl), co2 = T(forcing.co2),
    )
    # GSI phenology (self-computed; soil-temp gate ≈ air temp) → daily leaf-display factor
    (fc.phen, ph) = FDiff.phenology_gsi_step(fc.phen_params, fc.phen, temp, T(forcing.swdown), fc.water_avail, temp)
    (st′, fl) = FDiff.daily_step_canopy(fc.params, fc.inds, fc.soil, st, f; phen = ph)
    # write soil water back into the authoritative shared state (fraction of WHC), in place
    @inbounds for l in 1:nlay
        state.w[l] = st′.w[l] / whcs[l]
    end
    fc.snowpack = st′.snowpack
    fc.water_avail = fl.wscal
    # accumulate the conserved per-individual bm_inc (per-m²) + stand diagnostics
    @inbounds for i in eachindex(fc.bm_inc_acc)
        fc.bm_inc_acc[i] += fl.npp_ind[i]
    end
    et = fl.transp + fl.evap + fl.interc
    fc.gpp_acc += fl.gpp; fc.npp_acc += fl.npp; fc.et_acc += et; fc.wscal_acc += fl.wscal; fc.nday += 1
    le = et / T(86400) * T(LAMBDA_VAPORIZATION)          # mm/day → kg/m²/s → W/m² (λ·ET)
    return FToE{T}(
        le = le, gpp = fl.gpp, npp = fl.npp, rh = zero(T), firec = zero(T),
        flux_estabc = zero(T), ground_heat = zero(T),
    )
end

"""
    annual_step!(fc::FDiffFastCore, state::SharedState) -> FToS

Year-end flux-then-integrate handoff (DESIGN §8): GROW each individual's prognostic structure
(`FDiff.grow_individual`) from the accumulated per-individual `bm_inc` (÷ `nind`) at the mean
annual water scalar, rebuild the daily canopy `FDiff.Individual`s from the new pools (recomputing
the layered `fpar`), and return the conserved [`FToS`](@ref) increment for S (`bm_inc` per-m², water/temp
stress, growth efficiency, root-zone soil-moisture state). Resets the within-year accumulators + phenology.
This is the deterministic carbon allocation F owns; S owns the demography (distribution/count/mortality).
"""
function annual_step!(fc::FDiffFastCore{T}, state::SharedState) where {T}
    wscal_mean = fc.nday > 0 ? fc.wscal_acc / fc.nday : one(T)
    bm_inc_cell = sum(fc.bm_inc_acc)                      # per-m² annual NPP delivered (the conserved handoff)
    n = length(fc.pools)
    newpools = Vector{FDiff.TreePools{T}}(undef, n)
    @inbounds for i in 1:n
        tr = fc.pools[i]
        bm_ind = fc.bm_inc_acc[i] / (tr.nind + T(1.0e-12))
        newpools[i] = FDiff.grow_individual(fc.alloc, fc.allom, tr, bm_ind, wscal_mean)
    end
    fc.pools = newpools
    fpars = FDiff._patch_fpars(newpools, fc.allom)
    fc.inds = FDiff.Individual{T}[FDiff.individual_from_pools(fc.tmpls[i], newpools[i], fc.allom, fpars[i]) for i in 1:n]
    # growth efficiency ≈ bm_inc per unit leaf area (a mortality driver S conditions on)
    leaf_area = sum(FDiff.agb_ind(newpools[i]) > 0 ? newpools[i].leaf_c * newpools[i].sla * newpools[i].nind : zero(T) for i in 1:n)
    growth_eff = leaf_area > 0 ? bm_inc_cell / leaf_area : zero(T)
    soilmoist = sum(state.w) / length(state.w)
    ftos = FToS{T}(
        bm_inc = bm_inc_cell, water_stress = one(T) - wscal_mean, temp_stress = zero(T),
        growth_eff = growth_eff, soilmoist = soilmoist,
    )
    # reset within-year accumulators + phenology cold-start (v1)
    fill!(fc.bm_inc_acc, zero(T))
    fc.gpp_acc = fc.npp_acc = fc.et_acc = fc.wscal_acc = zero(T)
    fc.nday = 0; fc.doy = 0; fc.phen = FDiff.PhenState{T}(); fc.water_avail = one(T)
    return ftos
end
