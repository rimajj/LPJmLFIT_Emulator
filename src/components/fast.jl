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

# ── FDiffFastCore — the concrete SharedState adapter (scale-up step 6b; docs §12, §26.4) ─────────
# Wires the differentiable multi-individual canopy (`FDiff.daily_step_canopy`) behind
# `AbstractFastCore.step!`: it reads/writes the authoritative soil water in `SharedState`, self-computes
# PER-PFT GSI phenology + `eeq` (dynamic albedo) + daylength (from latitude), and accumulates the
# conserved per-individual self-computed `bm_inc` (`fl.npp_ind` — NO C crutch; the canopy NPP is
# calibrated, docs §13) that the ANNUAL handoff ([`annual_step!`](@ref)) allocates into the prognostic
# canopy structure (trees via `FDiff.grow_individual`, grass via `FDiff.grow_grass_individual` +
# establishment) and returns to S as [`FToS`](@ref) — the flux-then-integrate S↔F coupling of DESIGN §8.
# This closes the "SharedState adapter" scale-up item (the interface no longer throws) on the Hainich
# prototype.
#
# GRASS PARITY (§26.4): the adapter mirrors the validated-faithful grass config of
# `FDiff.rollout_canopy_years` (§26.3) — the §26 photosynthesis demand-gate (grass-gated in `params`),
# per-PFT GSI phenology with the lag-1 forest-floor light `grass_lf` for understory grass, the grass
# allocation, and grass re-seeding by establishment — all **grass-only** (gated on `is_grass` / grass
# PFT ids), so a tree-only core is BYTE-IDENTICAL to the pre-§26.4 adapter, and the AD/gradient trainer
# (`FDiff.rollout_canopy_years_gpp`, a separate function that never touches this struct) is untouched.
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
[`AbstractFastCore`](@ref). Holds the daily parameters (`params`), the tree + grass annual
allocation/turnover parameters (`alloc`/`galloc`) + shared allometry (`allom`), the prognostic
per-individual structure (`pools`, `FDiff.TreePools`) with the daily-canopy templates (`tmpls`,
`FDiff.Individual`), the shared 23-layer `soil` column, the cell latitude `lat`, the grass
establishment params (`grass_estab`), the PER-PFT GSI phenology state (one filter set per DISTINCT PFT,
plus the lag-1 forest-floor light `grass_lf`), and the mutable within-year state (day-of-year,
previous-day water scalar, and the annual `bm_inc`/flux accumulators). Mirrors the validated-faithful
grass config of `FDiff.rollout_canopy_years` (§26.3): the §26 demand-gate is on (grass-gated in
`params`), grass grows with the grass allocation, grass phenology is per-PFT with the tree-attenuated
forest-floor light, and grass re-seeds by establishment — all **grass-only**, so a tree-only core is
byte-identical to the pre-§26.4 adapter. Build one for the Hainich prototype and drive it with
[`step!`](@ref) (daily) + [`annual_step!`](@ref) (year-end).
"""
mutable struct FDiffFastCore{T <: AbstractFloat} <: AbstractFastCore
    params::FDiff.FDiffParams{T}
    alloc::FDiff.AllocParams{T}
    galloc::FDiff.AllocParams{T}
    allom::TreeAllometry{T}
    tmpls::Vector{FDiff.Individual{T}}
    pools::Vector{FDiff.TreePools{T}}
    inds::Vector{FDiff.Individual{T}}
    soil::FDiff.SoilColumn{T}
    lat::T
    grass_estab::Union{Nothing, FDiff.GrassEstabParams{T}}
    # PER-PFT GSI phenology (mirrors rollout_daily_canopy): one filter set per DISTINCT PFT, indexed via
    # `pft_slot`; `pft_ids` maps each individual to its PFT; `grass_lf` is the lag-1 forest-floor light.
    pft_ids::Vector{Int}
    pft_slot::Dict{Int, Int}
    pft_params::Vector{FDiff.PhenParams{T}}
    pft_states::Vector{FDiff.PhenState{T}}
    pft_isg::Vector{Bool}
    grass_lf_mode::Symbol
    grass_lf::T
    doy::Int
    water_avail::T
    snowpack::T                 # snow water equivalent (mm) — held here (SharedState.snowpack is immutable, v1)
    bm_inc_acc::Vector{T}
    gpp_acc::T
    npp_acc::T
    et_acc::T
    wscal_acc::T
    nday::Int
    # E→F skin-temperature feedback (DEVELOPMENT_PLAN §2.4, the mandatory top thermal BC). When set (by the
    # coupled driver from Component E's solved T_skin, in °C), it REPLACES the air-temperature proxy in the
    # phenology soil-temp gate — the one place F's soil-temp-dependent physics uses the single surface
    # temperature. `NaN` (the default) ⇒ use air temperature ⇒ BYTE-IDENTICAL to the pre-feedback adapter
    # (every existing baseline + the AD trainer untouched). See [`couple_day!`](@ref).
    soiltemp_skin::T
    # Write-only diagnostic: the leaf-display-weighted DYNAMIC stand albedo F used on the last `step!`
    # (`FDiff.patch_albedo`). The coupled driver reads it so Component E's net radiation uses the SAME
    # albedo as F's water balance (consistency). Does not feed back into F ⇒ byte-identical.
    last_albedo::T
end

"""
    FDiffFastCore(pools, tmpls, soil, lat; params, alloc, galloc, allom, grass_demand_gate,
                  grass_estab, pft_ids, grass_lf_mode) -> FDiffFastCore

Construct an [`FDiffFastCore`](@ref) from the prognostic per-individual structure `pools`
(`FDiff.TreePools`), the daily-canopy templates `tmpls`, the shared `soil` column, and the cell
latitude `lat` (°). Defaults use the beech (TeBS) parameter sets and the §26.3 validated-faithful grass
config: `grass_demand_gate=true` reconstructs `params` with the §26 photosynthesis demand-gate on at the
C's sharp step (grass-gated ⇒ tree-only cores are byte-identical); `grass_estab=grass_estabparams(T)`
enables grass re-seeding; per-PFT GSI phenology is set up from `pft_ids` (default `t.is_grass ? 8 : 3`,
the Hainich grass→temperate-C3 / tree→beech mapping — `pft_phenparams(3) === tebs_phenparams`, so id-3
trees are byte-identical to the old single-beech GSI); `grass_lf_mode` (`:linear` default, or `:exp`)
selects the forest-floor light transmission. Pass `grass_demand_gate=false` / `grass_estab=nothing` for
the pre-§26.4 gate-off, no-establishment behaviour. The daily `FDiff.Individual`s are (re)built from
`pools` + the recomputed layered `fpar`.
"""
function FDiffFastCore(
        pools::Vector{FDiff.TreePools{T}}, tmpls::Vector{FDiff.Individual{T}}, soil::FDiff.SoilColumn{T},
        lat::Real; params = FDiff.tebs_params(T), alloc = FDiff.tebs_allocparams(T),
        galloc = FDiff.grass_allocparams(T), allom = TreeAllometry{T}(), grass_demand_gate::Bool = true,
        grass_estab = FDiff.grass_estabparams(T), pft_ids = nothing, grass_lf_mode::Symbol = :linear
    ) where {T <: AbstractFloat}
    fpars = FDiff._patch_fpars(pools, allom)
    inds = FDiff.Individual{T}[FDiff.individual_from_pools(tmpls[i], pools[i], allom, fpars[i]) for i in eachindex(pools)]
    p = FDiff._with_grass_gate(params, grass_demand_gate)
    pids = pft_ids === nothing ? Int[t.is_grass ? 8 : 3 for t in tmpls] : collect(Int, pft_ids)
    uids = unique(pids)
    slot = Dict{Int, Int}(id => k for (k, id) in enumerate(uids))
    pparams = FDiff.PhenParams{T}[FDiff.pft_phenparams(id, T) for id in uids]
    pstates = FDiff.PhenState{T}[FDiff.PhenState{T}() for _ in uids]
    pisg = Bool[FDiff._pft_is_grass(id) for id in uids]
    return FDiffFastCore{T}(
        p, alloc, galloc, allom, tmpls, pools, inds, soil, T(lat), grass_estab,
        pids, slot, pparams, pstates, pisg, grass_lf_mode, one(T),
        0, one(T), zero(T), zeros(T, length(pools)), zero(T), zero(T), zero(T), zero(T), 0,
        T(NaN),                       # soiltemp_skin: NaN ⇒ use air-temp proxy (byte-identical default)
        T(0.15),                      # last_albedo: reasonable default until the first step! records it
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
    # PER-PFT GSI phenology (self-computed; soil-temp gate ≈ air temp): advance each DISTINCT PFT's filters
    # one day (a grass driven by the lag-1 forest-floor light `grass_lf·swdown`, `phenology_gsi.c:30-35`),
    # then materialize the per-individual leaf-display vector. Mirrors `rollout_daily_canopy`, carried as
    # persisted struct state because the adapter is day-by-day (not batched). `pft_phenparams(3)` is the
    # beech GSI, so an all-tree patch is byte-identical to the old single-beech scalar path.
    # E→F feedback: the phenology soil-temp GATE (4th arg) uses Component E's skin temperature when the
    # coupled driver has set it (`soiltemp_skin`, °C); otherwise the native air-temp proxy. The tmin/tmax
    # GSI filters (1st arg) stay on AIR temperature — only the soil-temp gate takes the surface temperature.
    soilt_gate = isnan(fc.soiltemp_skin) ? temp : fc.soiltemp_skin
    phen_slot = FDiff._step_pft_phen_day!(
        fc.pft_states, fc.pft_params, fc.pft_isg, temp, T(forcing.swdown), fc.water_avail, soilt_gate, fc.grass_lf,
    )
    phen_vec = T[phen_slot[fc.pft_slot[id]] for id in fc.pft_ids]
    # record the dynamic leaf-display-weighted stand albedo F uses (so E's Rn is consistent with F)
    fc.last_albedo = FDiff.patch_albedo(fc.inds, phen_vec, st.snowpack)
    (st′, fl) = FDiff.daily_step_canopy(fc.params, fc.inds, fc.soil, st, f; phen = phen_vec)
    # write soil water back into the authoritative shared state (fraction of WHC), in place
    @inbounds for l in 1:nlay
        state.w[l] = st′.w[l] / whcs[l]
    end
    fc.snowpack = st′.snowpack
    fc.water_avail = fl.wscal
    # lag-1 forest-floor light fraction for tomorrow's grass phenology (mirror rollout_daily_canopy:1715-1738)
    if fc.grass_lf_mode === :exp
        plai_phen = zero(T)
        for (ii, ind) in enumerate(fc.inds)
            ind.is_grass && continue
            lai_i = convert(T, ind.lai)
            lai_i <= zero(T) && continue
            denom = one(T) - exp(-convert(T, fc.allom.k_beer) * lai_i)
            plai_i = denom > T(1.0e-12) ? lai_i * convert(T, ind.fpc) / denom : zero(T)
            plai_phen += plai_i * FDiff._phen_at(phen_vec, ii)
        end
        fc.grass_lf = exp(-T(0.5) * plai_phen)
    else
        absorbed = zero(T)
        for (ii, ind) in enumerate(fc.inds)
            ind.is_grass || (absorbed += convert(T, ind.fpar) * FDiff._phen_at(phen_vec, ii))
        end
        fc.grass_lf = clamp(one(T) - absorbed, zero(T), one(T))
    end
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

Year-end flux-then-integrate handoff (DESIGN §8): GROW each individual's prognostic structure — trees
with the pipe-model tree allocation (`FDiff.grow_individual`), grass with the grass allocation
(`FDiff.grow_grass_individual`) — from the accumulated per-individual `bm_inc` (÷ `nind`) at the mean
annual water scalar; re-seed grass by ESTABLISHMENT when the patch FPC < 1 (`grass_estab`), rebuild the
daily canopy `FDiff.Individual`s from the new pools (recomputing the layered `fpar`), and return the
conserved [`FToS`](@ref) increment for S (`bm_inc` per-m², water/temp stress, growth efficiency,
root-zone soil-moisture state). Resets the within-year accumulators + per-PFT phenology (cold-start).
Grass allocation + establishment mirror `FDiff.rollout_canopy_years` (§26.3) and are **grass-only** — a
tree-only core is byte-identical. This is the deterministic carbon allocation F owns; S owns the
demography (distribution/count/mortality).
"""
function annual_step!(fc::FDiffFastCore{T}, state::SharedState) where {T}
    wscal_mean = fc.nday > 0 ? fc.wscal_acc / fc.nday : one(T)
    bm_inc_cell = sum(fc.bm_inc_acc)                      # per-m² annual NPP delivered (the conserved handoff)
    n = length(fc.pools)
    newpools = Vector{FDiff.TreePools{T}}(undef, n)
    @inbounds for i in 1:n
        tr = fc.pools[i]
        bm_ind = fc.bm_inc_acc[i] / (tr.nind + T(1.0e-12))
        newpools[i] = tr.is_grass ?
            FDiff.grow_grass_individual(fc.galloc, tr, bm_ind, wscal_mean) :
            FDiff.grow_individual(fc.alloc, fc.allom, tr, bm_ind, wscal_mean)
    end
    # GRASS ESTABLISHMENT (establishment_grass.c, individual mode): if the total patch FPC is below 1, each
    # grass PFT gains sapling biomass `sapl·(1−fpc_total)/n_est` (mirrors rollout_canopy_years §26.3). Off
    # when `grass_estab === nothing`; grass-specific ⇒ a no-op (n_est = 0) for a tree-only patch.
    if fc.grass_estab !== nothing
        n_est = 0
        for i in 1:n
            newpools[i].is_grass && (n_est += 1)
        end
        if n_est > 0
            fpc_total = zero(T)
            for i in 1:n
                fpc_total += FDiff._treepools_fpc(newpools[i], fc.allom)
            end
            est_pft = max(zero(T), one(T) - fpc_total) / n_est
            if est_pft > zero(T)
                for i in 1:n
                    g = newpools[i]
                    g.is_grass || continue
                    newpools[i] = FDiff.TreePools{T}(
                        g.leaf_c + convert(T, fc.grass_estab.sapl_leaf) * est_pft, g.sapwood_c, g.heartwood_c,
                        g.root_c + convert(T, fc.grass_estab.sapl_root) * est_pft, g.height, g.crownarea,
                        g.nind, g.sla, g.wooddens, g.is_grass,
                    )
                end
            end
        end
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
    # reset within-year accumulators + per-PFT phenology cold-start (mirrors rollout_canopy_years, which
    # calls rollout_daily_canopy per year without a carried phen_state)
    fill!(fc.bm_inc_acc, zero(T))
    fc.gpp_acc = fc.npp_acc = fc.et_acc = fc.wscal_acc = zero(T)
    fc.nday = 0; fc.doy = 0; fc.water_avail = one(T)
    fc.pft_states = FDiff.PhenState{T}[FDiff.PhenState{T}() for _ in eachindex(fc.pft_states)]
    fc.grass_lf = one(T)
    return ftos
end

"""
    grow_annual_accounted!(fc::FDiffFastCore) -> NamedTuple

Year-end CARBON growth of F's representative individuals at FIXED `nind`, WITH full per-cell carbon
accounting — the S-in-the-loop counterpart of [`annual_step!`](@ref) (ADR 0018/0019). Grows each cohort
EXACTLY as `annual_step!` does (trees via `FDiff.grow_individual`, grass via `FDiff.grow_grass_individual`,
at the accumulated per-m² `bm_inc` ÷ `nind` and the mean water scalar), but instead of mutating `fc` and
re-seeding grass by establishment, it returns the grown pools + the EXACT carbon fluxes so the caller can
apply the slow emulator S's demography (establishment/mortality/merge) and route every flux through a
[`CarbonLedger`](@ref). Litter is the branch-agnostic growth residual `bm_applied − Δvegc_full` (captures
the abnormal-branch extra leaf shed exactly; see [`FDiff._turnover_litter`](@ref)); stagnating trees
(`bm_net ≤ 0` or `height ≤ 0`, frozen by `grow_individual`) contribute `applied = litter = 0` and their
delivered NPP to `unapplied_bm_cell` (a bounded diagnostic of the fixed-N approximation).

**Does not touch the `slow=nothing` path** — `annual_step!` is unchanged and byte-identical. Pure w.r.t.
`fc` (reads the within-year accumulators; the caller commits the new population + resets). Returns
`(; newpools, wscal_mean, bm_inc_cell, applied_bm_cell, unapplied_bm_cell, litter_cell, growth_eff,
water_stress)`.
"""
function grow_annual_accounted!(fc::FDiffFastCore{T}) where {T}
    wscal_mean = fc.nday > 0 ? fc.wscal_acc / fc.nday : one(T)
    bm_inc_cell = sum(fc.bm_inc_acc)
    n = length(fc.pools)
    newpools = Vector{FDiff.TreePools{T}}(undef, n)
    reprod = convert(T, fc.alloc.reprod_cost)
    applied_cell = zero(T)
    unapplied_cell = zero(T)
    litter_cell = zero(T)
    @inbounds for i in 1:n
        tr = fc.pools[i]
        bm_acc = fc.bm_inc_acc[i]
        bm_ind = bm_acc / (convert(T, tr.nind) + T(1.0e-12))
        grown = tr.is_grass ?
            FDiff.grow_grass_individual(fc.galloc, tr, bm_ind, wscal_mean) :
            FDiff.grow_individual(fc.alloc, fc.allom, tr, bm_ind, wscal_mean)
        newpools[i] = grown
        # stagnation guard (mirrors grow_individual): a deficit / zero-height TREE is frozen ⇒ nothing applied.
        bm_net = bm_ind >= zero(T) ? bm_ind * (one(T) - reprod) : bm_ind
        stagnated = !tr.is_grass && (convert(T, tr.height) <= zero(T) || bm_net <= zero(T))
        if stagnated
            unapplied_cell += bm_acc
        else
            dveg_cell = (FDiff.vegc_full_ind(grown) - FDiff.vegc_full_ind(tr)) * convert(T, tr.nind)
            applied_cell += bm_acc
            litter_cell += bm_acc - dveg_cell         # exact residual: reprod + leaf/root turnover (+ abnormal extra)
        end
    end
    # growth efficiency (a mortality driver S conditions on), on the GROWN pools
    leaf_area = sum(
        FDiff.agb_ind(newpools[i]) > 0 ? newpools[i].leaf_c * newpools[i].sla * newpools[i].nind : zero(T)
            for i in 1:n
    )
    growth_eff = leaf_area > 0 ? applied_cell / leaf_area : zero(T)
    return (;
        newpools, wscal_mean, bm_inc_cell, applied_bm_cell = applied_cell,
        unapplied_bm_cell = unapplied_cell, litter_cell, growth_eff, water_stress = one(T) - wscal_mean,
    )
end
