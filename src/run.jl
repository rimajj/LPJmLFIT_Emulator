# Coupled S+F+E run loop — the end-to-end "use the emulator" driver (DEVELOPMENT_PLAN §2.5, §6 Phase 4).
# Wires the fast physical core F (`FDiffFastCore`) and the surface-energy-balance closure E
# (`SEBEnergyClosure`) into one daily loop over a cell: F integrates the daily biophysics and hands E its
# water-limited latent heat + carbon terms ([`FToE`](@ref)); E solves ONE skin temperature, closes
# `Rn = LE + H + G` (H the residual), and returns the ESM-facing payload ([`EToATM`](@ref)) plus the
# mandatory skin-temperature feedback ([`EToF`](@ref)) that becomes F's top thermal boundary for the next
# day. Structure boundary conditions ([`SToE`](@ref)) are re-derived from F's OWN prognostic canopy (the
# slow emulator S supplies them once wired — DESIGN §8; F's self-computed structure suffices for a first
# usable run). Water & carbon are conserved by F; energy is closed by construction in E.

"""
    stand_structure_toe(fc::FDiffFastCore) -> SToE

Re-derive the structural boundary conditions Component E needs (albedo, roughness `z0`, stand LAI,
canopy height) from the fast core's CURRENT prognostic canopy (`fc.inds`/`fc.pools`). Height is the
foliar-projective-cover-weighted mean; `z0 = 0.1·height` (floored); LAI is the cover-weighted sum of
per-individual leaf-on LAI; albedo is the dynamic leaf-display-weighted stand albedo F used on its last
[`step!`](@ref) (so E's net radiation is consistent with F's water balance). This is the S→E handoff
served by F's own allometry until the slow emulator S is wired (DESIGN §8).
"""
function stand_structure_toe(fc::FDiffFastCore{T}) where {T <: AbstractFloat}
    tot_fpc = zero(T)
    h_w = zero(T)
    lai = zero(T)
    @inbounds for i in eachindex(fc.inds)
        fpc_i = convert(T, fc.inds[i].fpc)
        h_w += convert(T, fc.pools[i].height) * fpc_i
        tot_fpc += fpc_i
        lai += convert(T, fc.inds[i].lai) * fpc_i
    end
    height = tot_fpc > zero(T) ? h_w / tot_fpc : zero(T)
    z0 = max(T(0.1) * height, T(0.01))
    return SToE{T}(albedo = fc.last_albedo, z0 = z0, lai = lai, height = height)
end

"""
    stand_structure_tof(fc::FDiffFastCore) -> SToF

Re-derive the FULL structural boundary conditions ([`SToF`](@ref): `lai, height, z0, rootdepth, vcmax,
fpc, albedo`) from the fast core's current prognostic population — the S→F handoff (DESIGN §8). Generalises
[`stand_structure_toe`](@ref): `height` is the foliar-projective-cover-weighted mean; `lai` the
cover-weighted per-individual leaf-on LAI; `fpc` the (capped) stand foliar projective cover; `z0 =
0.1·height` (floored); `rootdepth` the D95 depth from the soil column's cumulative root distribution;
`albedo` the leaf-display-weighted dynamic stand albedo F used last; `vcmax` a beech proxy (no live
consumer in F v1 — F self-computes photosynthesis from its own individuals; documented). Used as `bc_f`
each year once the slow emulator S is in the loop (`run_coupled_cell(...; slow=)`), reflecting the
S-updated population.
"""
function stand_structure_tof(fc::FDiffFastCore{T}) where {T <: AbstractFloat}
    tot_fpc = zero(T)
    h_w = zero(T)
    lai = zero(T)
    @inbounds for i in eachindex(fc.inds)
        fpc_i = convert(T, fc.inds[i].fpc)
        h_w += convert(T, fc.pools[i].height) * fpc_i
        tot_fpc += fpc_i
        lai += convert(T, fc.inds[i].lai) * fpc_i
    end
    height = tot_fpc > zero(T) ? h_w / tot_fpc : zero(T)
    z0 = max(T(0.1) * height, T(0.01))
    fpc = min(tot_fpc, one(T))
    # D95 rooting depth (mm): cumulative root fraction reaching 95% down the soil column
    rootdepth = zero(T)
    cum = zero(T)
    @inbounds for l in eachindex(fc.soil.rootdist)
        cum += convert(T, fc.soil.rootdist[l])
        rootdepth += convert(T, fc.soil.soildepth[l])
        cum >= T(0.95) && break
    end
    return SToF{T}(
        lai = lai, height = height, z0 = z0, rootdepth = rootdepth,
        vcmax = T(40.0), fpc = fpc, albedo = fc.last_albedo,
    )
end

"""
    couple_day!(fc::FDiffFastCore, clo::SEBEnergyClosure, state::SharedState, bc_f::SToF,
                forcing::AtmForcing; feedback::Bool=true) -> (FToE, EToATM, EToF, SToE)

Advance the coupled system one day: run F ([`step!`](@ref) → [`FToE`](@ref)), derive the structural
boundary conditions ([`stand_structure_toe`](@ref)), solve E ([`solve!`](@ref) →
[`EToATM`](@ref)/[`EToF`](@ref)), and — when `feedback` is on (the mandatory E→F top thermal BC,
DEVELOPMENT_PLAN §2.4) — hand E's skin temperature back to F (in °C) so the NEXT day's phenology
soil-temp gate uses the one surface temperature instead of the air-temperature proxy. Returns all four
handoff payloads for the day.
"""
function couple_day!(
        fc::FDiffFastCore{T}, clo::SEBEnergyClosure{T}, state::SharedState, bc_f::SToF,
        forcing::AtmForcing; feedback::Bool = true
    ) where {T <: AbstractFloat}
    ftoe = step!(fc, state, bc_f, forcing)
    bc_e = stand_structure_toe(fc)
    (atm, tof) = solve!(clo, state, ftoe, bc_e, forcing)
    if feedback
        fc.soiltemp_skin = tof.t_skin - T(273.15)     # K → °C for the phenology soil-temp gate
    end
    return (ftoe, atm, tof, bc_e)
end

"""
    run_coupled_cell(fc, clo, state, forcings; bc_f, days_per_year=365, feedback=true) -> NamedTuple

Run the full coupled S+F+E emulator over a cell for `length(forcings)` days (multiple years back-to-back;
the year-end flux-then-integrate handoff [`annual_step!`](@ref) grows the canopy every `days_per_year`).
Returns time series (one entry per day) of the ESM-facing outputs and diagnostics:

  - `t_skin` (K), `le`, `h`, `g`, `rn` (W/m²) — the closed energy partition `Rn = LE + H + G`
  - `nbp_atm` (gC/m²/day), `z0` (m), `albedo` (–)
  - `gpp`, `npp` (gC/m²/day), `le` again as the latent-heat flux
  - `resid` (W/m²) — the closure residual `Rn − (LE + H + G)`, ≈ 0 by construction (the Phase-4 gate)

`bc_f` is F's structural consistency diagnostic (defaults to a plausible mixed-forest `SToF`; F
self-computes its structure in v1). `feedback` toggles the E→F skin-temperature coupling.

Pass `slow::AbstractSlowEmulator` to put the slow demography emulator S IN THE LOOP (ADR 0018): at each
year boundary F grows carbon at fixed N with full accounting ([`grow_annual_accounted!`](@ref)), then S
applies its demography (count N, establishment, mortality) and conserves carbon at the handoff
([`reconcile_demography!`](@ref)), and F/E use the S-updated population next year (`bc_f` becomes
[`stand_structure_tof`](@ref)). Default `slow=nothing` keeps F self-growing its canopy — byte-identical to
before. Read the coupled demography diagnostics from the emulator (`slow.total_n_history`,
`slow.resid_history`).
"""
function run_coupled_cell(
        fc::FDiffFastCore{T}, clo::SEBEnergyClosure{T}, state::SharedState,
        forcings::AbstractVector{<:AtmForcing};
        bc_f::SToF = SToF(;
            lai = 5.0, height = 25.0, z0 = 1.0, rootdepth = 1150.0,
            vcmax = 40.0, fpc = 0.9, albedo = 0.15
        ),
        slow::Union{Nothing, AbstractSlowEmulator} = nothing,
        days_per_year::Int = 365, feedback::Bool = true
    ) where {T <: AbstractFloat}
    n = length(forcings)
    t_skin = Vector{T}(undef, n); le = Vector{T}(undef, n); h = Vector{T}(undef, n)
    g = Vector{T}(undef, n); rn = Vector{T}(undef, n); nbp = Vector{T}(undef, n)
    z0 = Vector{T}(undef, n); albedo = Vector{T}(undef, n); gpp = Vector{T}(undef, n)
    npp = Vector{T}(undef, n); resid = Vector{T}(undef, n)
    p = clo.params
    # with S in the loop, F's structural boundary conditions come from S's population from day 1
    if slow !== nothing
        bc_f = stand_structure_tof(fc)
    end
    for i in 1:n
        forc = forcings[i]
        (ftoe, atm, _tof, bc_e) = couple_day!(fc, clo, state, bc_f, forc; feedback = feedback)
        # net radiation at the solved skin temperature (independent recompute for the closure check)
        Rn = (one(T) - T(bc_e.albedo)) * T(forc.swdown) + p.emissivity * T(forc.lwdown) -
            p.emissivity * p.sigma * atm.t_skin^4
        t_skin[i] = atm.t_skin; le[i] = atm.le; h[i] = atm.h; g[i] = atm.g; rn[i] = Rn
        nbp[i] = atm.nbp_atm; z0[i] = atm.z0; albedo[i] = T(bc_e.albedo)
        gpp[i] = ftoe.gpp; npp[i] = ftoe.npp
        resid[i] = Rn - (atm.le + atm.h + atm.g)
        if i % days_per_year == 0
            if slow === nothing
                annual_step!(fc, state)                 # F self-grows structure (byte-identical default)
            else
                # S in the loop (ADR 0018): F grows carbon at fixed N (accounted), then S applies demography
                # (mortality/establishment) + conserves at the handoff; next year's structure comes from S.
                grow = grow_annual_accounted!(fc)
                reconcile_demography!(slow, fc, grow, state)
                bc_f = stand_structure_tof(fc)
            end
        end
    end
    return (; t_skin, le, h, g, rn, nbp_atm = nbp, z0, albedo, gpp, npp, resid)
end
