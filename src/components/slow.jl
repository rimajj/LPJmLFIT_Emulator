# Component S — slow trait/size DISTRIBUTION + DEMOGRAPHY emulator (annual). DEVELOPMENT_PLAN §2.2, ADR 0018.
# The scientific novelty: S owns the per-cell population — the count N, establishment, mortality, and the
# trait×size spread — while F_diff owns the conserving CARBON growth of the representative individuals
# (ADR 0018 growth-ownership split). Carbon is conserved at the S↔F handoff by advancing the EXISTING
# population and routing every carbon movement through a `CarbonLedger` (flux-then-integrate, ADR 0003).
#
# `DemographicSlowEmulator` is the concrete S wired into the coupled loop (`run_coupled_cell(...; slow=)`).
# TIER 0 (this file): a DETERMINISTIC, fixed-roster demography that proves the wiring + the 1e-6 carbon
# handoff with ZERO ML risk and an EMPTY runtime `[deps]` — the K representative cohorts are `fc.pools`
# (their carbon owned by F), and S adjusts their `nind` (mortality reduces it; recruitment mixes saplings
# into the smallest cohort when the canopy is open), so the count N and size distribution evolve while
# carbon closes by construction. TIER 1 (later, ADR 0019, `src/slow_infer.jl`) replaces the constant
# mortality/establishment rates + fixed sapling with the ported ResidualRegressor + Gaussian copula +
# Poisson/NB count models, conditioned on climate + `FToS`, and adds true membership change (append/merge)
# + copula-sampled recruit traits. See `docs/p1_s_in_loop_design.md`.

"""
    AbstractSlowEmulator

Interface for the slow ML component S. A concrete emulator (e.g. [`DemographicSlowEmulator`](@ref)) owns
the per-cell DISTRIBUTION + DEMOGRAPHY: given the delivered carbon increment + stress drivers
([`FToS`](@ref)) and the fast core's grown population, it sets the new count `N`, establishment, mortality,
and trait×size spread, and derives the structural boundary conditions ([`SToF`](@ref)/[`SToE`](@ref)) for F
and E via allometry. Carbon is conserved at the handoff by advancing the existing population, not
regenerating it (ADR 0018 / ADR 0003). The concrete coupling entry point is
[`reconcile_demography!`](@ref).
"""
abstract type AbstractSlowEmulator end

"""
    reconcile_demography!(::AbstractSlowEmulator, fc::FDiffFastCore, grow, state::SharedState) -> FToS

Apply the slow emulator's demography to the fast core's GROWN population (the year-end S↔F handoff,
ADR 0018). `grow` is the output of [`grow_annual_accounted!`](@ref) (grown pools + the exact carbon
fluxes). The concrete method mutates `fc`'s population (via S-owned count/establishment/mortality) and
returns the conserved [`FToS`](@ref); the abstract fallback errors.
"""
reconcile_demography!(::AbstractSlowEmulator, ::FDiffFastCore, grow, ::SharedState) =
    error("reconcile_demography! is not implemented for this slow emulator — use `DemographicSlowEmulator`.")

# ── DemographicSlowEmulator — the concrete Tier-0 S (ADR 0018/0019) ───────────────────────────────

"""
    DemographicSlowEmulator{T} <: AbstractSlowEmulator

Tier-0 concrete slow emulator: a DETERMINISTIC, fixed-roster demography over the fast core's K
representative cohorts (their carbon owned by F; S owns their `nind` + membership). Each year, given F's
grown pools + drivers, S applies **mortality** (per-cohort fraction `mort_bg + mort_max/(1 + k_mort·max(growth_eff,0))`,
clamped) routing the removed carbon `vegc_full_ind·Δnind` to litter, and **recruitment** (filling the open
canopy `max(1 − Σfpc, 0)` at `estab_rate` into the smallest tree cohort `recruit_idx`, mixing the fixed
`sapl` per-individual sapling pools mass-conservingly and re-deriving height from the pipe model), debiting
the sapling carbon to establishment. Every flux goes through `ledger` (a [`CarbonLedger`](@ref)); the
handoff carbon residual is self-checked into `last_resid` (the coupled Gate-2, ≤ 1e-6·C_scale). `age`
tracks per-cohort stand age; `total_n_history` records Σ`nind` per year (Gate-1: the count evolves). Empty
runtime `[deps]` (no RNG/ML in Tier-0). Build with [`DemographicSlowEmulator(fc; ...)`](@ref).
"""
mutable struct DemographicSlowEmulator{T <: AbstractFloat} <: AbstractSlowEmulator
    mort_bg::T
    mort_max::T
    k_mort::T
    estab_rate::T
    sapl::FDiff.TreePools{T}
    recruit_idx::Int
    ledger::CarbonLedger{T}
    age::Vector{T}
    last_resid::T
    total_n_history::Vector{T}
    resid_history::Vector{T}
    year::Int
end

"""
    DemographicSlowEmulator(fc::FDiffFastCore{T}; mort_bg=0.01, mort_max=0.03, k_mort=0.02,
                            estab_rate=0.02, sapl=<small beech sapling>) -> DemographicSlowEmulator

Construct the Tier-0 slow emulator for a fast core: the K cohorts are `fc.pools`; `recruit_idx` is the
shortest living TREE cohort (0 ⇒ recruitment off, e.g. an all-grass patch); `sapl` defaults to a small
beech sapling (`leaf 15, sapwood 30, root 15 gC/individual`, height from the pipe model). The rate
defaults give a mild, stable demography on the Hainich prototype (documented Tier-0 placeholders; Tier-1
replaces them with the ported climate/FToS-conditioned models, ADR 0019).
"""
function DemographicSlowEmulator(
        fc::FDiffFastCore{T}; mort_bg = T(0.01), mort_max = T(0.03), k_mort = T(0.02),
        estab_rate = T(0.02), sapl::Union{Nothing, FDiff.TreePools{T}} = nothing,
    ) where {T <: AbstractFloat}
    # recruit cohort = shortest living tree (smallest height, not grass); 0 if none
    ridx = 0
    hmin = typemax(T)
    for (i, p) in enumerate(fc.pools)
        if !p.is_grass && p.height > 0 && p.height < hmin
            hmin = p.height
            ridx = i
        end
    end
    sap = if sapl !== nothing
        sapl
    else
        sla = ridx > 0 ? fc.pools[ridx].sla : T(0.02)
        wd = ridx > 0 ? fc.pools[ridx].wooddens : T(2.0e5)
        leaf = T(15.0); sapw = T(30.0); root = T(15.0)
        h = leaf > 0 ? convert(T, fc.allom.k_latosa) * sapw / (leaf * sla * wd) : T(1.0)
        FDiff.TreePools{T}(leaf, sapw, zero(T), root, zero(T), h, T(0.5), one(T), sla, wd, false)
    end
    return DemographicSlowEmulator{T}(
        mort_bg, mort_max, k_mort, estab_rate, sap, ridx, CarbonLedger{T}(),
        zeros(T, length(fc.pools)), zero(T), T[], T[], 0,
    )
end

function reconcile_demography!(
        s::DemographicSlowEmulator{T}, fc::FDiffFastCore{T}, grow, state::SharedState
    ) where {T <: AbstractFloat}
    # C_veg at the START of the year (fc.pools is still the OLD, pre-growth population — grow_annual_accounted!
    # does not mutate fc), so the handoff residual closes over the WHOLE year (growth + demography).
    cveg_start = sum(FDiff.vegc_full_ind(fc.pools[i]) * convert(T, fc.pools[i].nind) for i in eachindex(fc.pools))

    reset_year!(s.ledger)
    record_growth!(s.ledger, grow.applied_bm_cell, grow.unapplied_bm_cell)
    record_litter!(s.ledger, grow.litter_cell)

    pools = collect(grow.newpools)                 # grown at OLD nind (mutable working copy)
    ge = max(grow.growth_eff, zero(T))

    # ── MORTALITY (S's demography): reduce nind, carbon vegc_full·Δnind → litter ──
    # TREE-ONLY in Tier-0: grass demography stays F-side (design risk #8 — grass ownership is a Tier-1
    # decision), so grass cohorts pass through S unchanged (F still grows their carbon; a tree-only patch
    # like Hainich is unaffected). Skipping grass here also keeps the coupled path from applying tree-style
    # mortality rates to grass.
    for i in eachindex(pools)
        p = pools[i]
        p.is_grass && continue
        p.nind <= 0 && continue
        m = clamp(s.mort_bg + s.mort_max / (one(T) + s.k_mort * ge), zero(T), T(0.5))
        dn = convert(T, p.nind) * m
        dn <= 0 && continue
        record_litter!(s.ledger, FDiff.vegc_full_ind(p) * dn)
        pools[i] = _with_nind(p, convert(T, p.nind) - dn)
    end

    # ── RECRUITMENT / ESTABLISHMENT (S's demography): fill the open canopy into the smallest tree cohort ──
    if s.recruit_idx > 0 && s.estab_rate > 0
        fpc_total = sum(FDiff._treepools_fpc(pools[i], fc.allom) for i in eachindex(pools))
        gap = max(one(T) - fpc_total, zero(T))
        dn = s.estab_rate * gap
        if dn > 0
            r = s.recruit_idx
            old = pools[r]
            sap = s.sapl
            n_new = convert(T, old.nind) + dn
            mix(fo, fs) = (convert(T, fo) * convert(T, old.nind) + convert(T, fs) * dn) / n_new
            leaf_n = mix(old.leaf_c, sap.leaf_c)
            sapw_n = mix(old.sapwood_c, sap.sapwood_c)
            heart_n = mix(old.heartwood_c, sap.heartwood_c)
            root_n = mix(old.root_c, sap.root_c)
            sbg_n = mix(old.sapwood_bg_c, sap.sapwood_bg_c)
            crown_n = mix(old.crownarea, sap.crownarea)
            # re-derive height from the pipe model (NOT mass-averaged — the design rule); guard leaf>0
            h_n = leaf_n > 0 ?
                convert(T, fc.allom.k_latosa) * sapw_n / (leaf_n * convert(T, old.sla) * convert(T, old.wooddens)) :
                convert(T, old.height)
            pools[r] = FDiff.TreePools{T}(
                leaf_n, sapw_n, heart_n, root_n, sbg_n, h_n, crown_n, n_new,
                convert(T, old.sla), convert(T, old.wooddens), false,
            )
            record_estab!(s.ledger, FDiff.vegc_full_ind(sap) * dn)
        end
    end

    # ── COMMIT the new population into the fast core (fixed roster ⇒ arrays keep their size) + rebuild inds ──
    fc.pools = pools
    fpars = FDiff._patch_fpars(pools, fc.allom)
    fc.inds = FDiff.Individual{T}[FDiff.individual_from_pools(fc.tmpls[i], pools[i], fc.allom, fpars[i]) for i in eachindex(pools)]

    # reset the within-year accumulators + per-PFT phenology cold-start (mirrors annual_step!)
    fill!(fc.bm_inc_acc, zero(T))
    fc.gpp_acc = fc.npp_acc = fc.et_acc = fc.wscal_acc = zero(T)
    fc.nday = 0
    fc.doy = 0
    fc.water_avail = one(T)
    fc.pft_states = FDiff.PhenState{T}[FDiff.PhenState{T}() for _ in eachindex(fc.pft_states)]
    fc.grass_lf = one(T)

    # self-check: the S↔F handoff carbon residual over the whole year (coupled Gate-2)
    cveg_end = sum(FDiff.vegc_full_ind(pools[i]) * convert(T, pools[i].nind) for i in eachindex(pools))
    s.last_resid = handoff_carbon_residual(s.ledger; c_veg_delta = cveg_end - cveg_start)
    s.year += 1
    s.age .+= one(T)
    push!(s.total_n_history, sum(convert(T, p.nind) for p in pools))
    push!(s.resid_history, s.last_resid)

    soilmoist = sum(state.w) / length(state.w)
    return FToS{T}(
        bm_inc = grow.bm_inc_cell, water_stress = grow.water_stress, temp_stress = zero(T),
        growth_eff = grow.growth_eff, soilmoist = convert(T, soilmoist),
    )
end

"Rebuild a [`FDiff.TreePools`](@ref) with a new `nind` (all other fields unchanged)."
_with_nind(p::FDiff.TreePools{T}, n) where {T} = FDiff.TreePools{T}(
    p.leaf_c, p.sapwood_c, p.heartwood_c, p.root_c, p.sapwood_bg_c,
    p.height, p.crownarea, convert(T, n), p.sla, p.wooddens, p.is_grass,
)

"Total live individual density Σ`nind` (indiv/m²) across the emulator's population history — the count N."
total_n(s::DemographicSlowEmulator) = isempty(s.total_n_history) ? nothing : last(s.total_n_history)
