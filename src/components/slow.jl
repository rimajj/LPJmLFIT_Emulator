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

"Rebuild a `FDiff.TreePools` with a new `nind` (all other fields unchanged)."
_with_nind(p::FDiff.TreePools{T}, n) where {T} = FDiff.TreePools{T}(
    p.leaf_c, p.sapwood_c, p.heartwood_c, p.root_c, p.sapwood_bg_c,
    p.height, p.crownarea, convert(T, n), p.sla, p.wooddens, p.is_grass,
)

"Total live individual density Σ`nind` (indiv/m²) across the emulator's population history — the count N."
total_n(s::DemographicSlowEmulator) = isempty(s.total_n_history) ? nothing : last(s.total_n_history)

# ── Membership machinery for the flux-driven S (ADR 0024): recruit-cohort APPEND, K-cap MERGE, and the
#    ATOMIC roster rebuild that keeps every length-K `FDiffFastCore` field + `s.age` mutually consistent
#    when the cohort count changes (design risk #5). Confined to `FluxDrivenSlowEmulator` — Tier-0 stays
#    fixed-roster. All carbon routing is on `vegc_full_ind` (incl `sapwood_bg_c`); MERGE is carbon-neutral.

"""
    RecruitCopula{T}

Opt-in Gaussian-copula recruit-trait sampler for establishment. Bundles a fitted `DRF.GaussianCopula`
`cop`, the per-axis marginal forests `axis_forests` (each `store_values=true`, in the copula's axis order),
the conditioning feature row `x` the marginals were trained on, and `to_pools`, a mapping
`(traits::Vector{Float64}, sapl::FDiff.TreePools{T}, allom) -> FDiff.TreePools{T}` turning one drawn trait
vector into a recruit's per-individual pools. When a `FluxDrivenSlowEmulator` carries one, establishment
draws recruit traits from `s.rng` (deterministic) instead of using the fixed `sapl`. Production axis
artifacts + the correlation matrix are a multi-cell (P3) concern; at a single beech cell the trait axes are
near-degenerate, so the default is `nothing` (fixed sapling).
"""
struct RecruitCopula{T <: AbstractFloat}
    cop::DRF.GaussianCopula
    axis_forests::Vector{DRF.Forest}
    x::Vector{Float64}
    to_pools::Any
end

"nind-weighted mean age over the TREE cohorts (the demographic mean-age DRF feature); 0 if no living tree."
function _mean_age_weighted(ages, pools::AbstractVector{FDiff.TreePools{T}}) where {T}
    num = zero(T)
    den = zero(T)
    for i in eachindex(pools)
        pools[i].is_grass && continue
        n = convert(T, pools[i].nind)
        num += convert(T, ages[i]) * n
        den += n
    end
    return den > zero(T) ? num / den : zero(T)
end

"Index of the shortest living TREE cohort (the recruit target); 0 if none (e.g. an all-grass patch)."
function _shortest_tree_idx(pools::AbstractVector{FDiff.TreePools{T}}) where {T}
    ridx = 0
    hmin = typemax(T)
    for i in eachindex(pools)
        p = pools[i]
        if !p.is_grass && p.height > 0 && convert(T, p.height) < hmin
            hmin = convert(T, p.height)
            ridx = i
        end
    end
    return ridx
end

"""
    _merge_pair!(pools, ages, tmpls, pft_ids, i, j, allom)

Fold tree cohort `j` into `i` (`i<j`): `nind_m = n_i+n_j`; each of the FIVE carbon pools nind-weighted
(so `vegc_full_ind(m)·nind_m == Σ vegc_full_ind(parent)·nind_parent` to floating-point rounding —
carbon-neutral, NO ledger entry); age nind-weighted; the dominant (higher-nind) parent's `sla`/`wooddens`/
`tmpl`/`pft_id` inherited (keeps `tmpl.photo.sla` consistent with `pools.sla`); height re-derived from the
pipe model (guarded `leaf>0`) and crownarea from the Jucker allometry (both carbon-free). Deletes slot `j`
from all four roster vectors.
"""
function _merge_pair!(
        pools::Vector{FDiff.TreePools{T}}, ages::Vector{T}, tmpls, pft_ids, i::Int, j::Int, allom
    ) where {T}
    a = pools[i]
    b = pools[j]
    na = convert(T, a.nind)
    nb = convert(T, b.nind)
    nm = na + nb
    w(fa, fb) = (convert(T, fa) * na + convert(T, fb) * nb) / nm
    leaf_m = w(a.leaf_c, b.leaf_c)
    sapw_m = w(a.sapwood_c, b.sapwood_c)
    heart_m = w(a.heartwood_c, b.heartwood_c)
    root_m = w(a.root_c, b.root_c)
    sbg_m = w(a.sapwood_bg_c, b.sapwood_bg_c)
    age_m = (convert(T, ages[i]) * na + convert(T, ages[j]) * nb) / nm
    dom = na >= nb ? i : j
    sla_m = convert(T, pools[dom].sla)
    wd_m = convert(T, pools[dom].wooddens)
    tmpl_m = tmpls[dom]
    pft_m = pft_ids[dom]
    h_m = leaf_m > zero(T) ?
        convert(T, allom.k_latosa) * sapw_m / (leaf_m * sla_m * wd_m) :
        convert(T, pools[dom].height)
    crown_m = convert(T, Allometry.crown_area(allom, h_m))
    pools[i] = FDiff.TreePools{T}(leaf_m, sapw_m, heart_m, root_m, sbg_m, h_m, crown_m, nm, sla_m, wd_m, false)
    ages[i] = age_m
    tmpls[i] = tmpl_m
    pft_ids[i] = pft_m
    deleteat!(pools, j)
    deleteat!(ages, j)
    deleteat!(tmpls, j)
    deleteat!(pft_ids, j)
    return nothing
end

"""
    _apply_kcap_merge!(pools, ages, tmpls, pft_ids, k_cap, allom)

While the roster exceeds `k_cap`, merge the tree-cohort pair with the smallest `|Δheight|` (deterministic
single-pass index-order scan; strict `<` keeps the first argmin ⇒ reproducible on ties). Bounds K (the
structural speed-up invariant) with minimal size-distribution distortion. Stops if fewer than two live
tree cohorts remain.
"""
function _apply_kcap_merge!(
        pools::Vector{FDiff.TreePools{T}}, ages, tmpls, pft_ids, k_cap::Int, allom
    ) where {T}
    while length(pools) > k_cap
        bi = 0
        bj = 0
        bd = typemax(T)
        for i in eachindex(pools)
            (pools[i].is_grass || pools[i].nind <= 0) && continue
            for j in (i + 1):length(pools)
                (pools[j].is_grass || pools[j].nind <= 0) && continue
                d = abs(convert(T, pools[i].height) - convert(T, pools[j].height))
                if d < bd
                    bd = d
                    bi = i
                    bj = j
                end
            end
        end
        bi == 0 && break
        _merge_pair!(pools, ages, tmpls, pft_ids, bi, bj, allom)
    end
    return nothing
end

"""
    _commit_membership!(s, fc, pools, tmpls, pft_ids, ages)

The ATOMIC year-end roster rebuild (design risk #5). Replaces, in one shot, every length-K field of `fc`:
`pools`, `tmpls`, `pft_ids`, a REALLOCATED `bm_inc_acc = zeros(T, K′)` (never `fill!` — that keeps the old
length and the daily `bm_inc_acc[i] += npp_ind[i]` accumulation would read out of bounds), and `inds`,
rebuilt LAST from the layered `_patch_fpars` over the FULL new roster (light is cohort-coupled). Then resets
the within-year accumulators + per-PFT phenology cold-start (mirrors `annual_step!`) and sets the S-side
roster state (`s.age = ages` start-of-year; `s.recruit_idx` recomputed). Every appended/merged cohort
reuses an existing PFT id, so `pft_slot`/`pft_params`/`pft_states`/`pft_isg` (keyed by distinct PFT, not K)
need no change; a genuinely new id errors here rather than `KeyError`-ing later inside `step!`.
"""
function _commit_membership!(
        s, fc::FDiffFastCore{T}, pools::Vector{FDiff.TreePools{T}}, tmpls, pft_ids, ages::Vector{T},
    ) where {T}
    all(id -> haskey(fc.pft_slot, id), pft_ids) ||
        error("_commit_membership!: an appended/merged cohort introduced a PFT id absent from fc.pft_slot")
    fc.pools = pools
    fc.tmpls = collect(FDiff.Individual{T}, tmpls)
    fc.pft_ids = collect(Int, pft_ids)
    fc.bm_inc_acc = zeros(T, length(pools))
    fpars = FDiff._patch_fpars(pools, fc.allom)
    fc.inds = FDiff.Individual{T}[FDiff.individual_from_pools(fc.tmpls[i], pools[i], fc.allom, fpars[i]) for i in eachindex(pools)]
    fc.gpp_acc = fc.npp_acc = fc.et_acc = fc.wscal_acc = zero(T)
    fc.nday = 0
    fc.doy = 0
    fc.water_avail = one(T)
    fc.pft_states = FDiff.PhenState{T}[FDiff.PhenState{T}() for _ in eachindex(fc.pft_states)]
    fc.grass_lf = one(T)
    s.age = ages
    s.recruit_idx = _shortest_tree_idx(pools)
    return nothing
end

# ── FluxDrivenSlowEmulator — the Tier-1 FLUX-DRIVEN S (ADR 0020 / 0021 / 0022 / 0024) ───────────────
# The scientific step past Tier-0: the demography TARGET is set by a trained, FLUX-CONDITIONED model (the
# zero-dependency native-Julia DRF, `src/drf.jl`, ADR 0022) instead of a constant physical rate. Each year
# S builds a flux feature vector from F's delivered fluxes (`FToS`-consistent: bm_inc / growth_eff /
# water_stress / soilmoist) + this-year patch STATE (height / agb / lai / fpc / age from the grown pools) +
# the recursive AR state `n_prev` + a baked slow bioclimatic boundary, and the DRF predicts the demographic
# target. The coupled tree DENSITY is then moved toward `target / n_prev` — a UNIT-FREE ratio, so the
# count↔density gap between the training table (per-patch counts) and the coupled state (cohort densities)
# cancels — through the SAME carbon-conserving mortality/establishment machinery Tier-0 uses, so the S↔F
# handoff conserves carbon BY CONSTRUCTION (the ledger + `vegc_full_ind` routing are identical). ADR 0020's
# premise — flux-conditioning generalises to warm+dry OOD far better than climate-conditioning — is
# validated offline (`scripts/flux_ood_experiment.jl`: flux 2.35× climate OOD). TREE-only demography
# (grass stays F-side, design risk #8). As of ADR 0024 the roster is DYNAMIC: establishment APPENDS a real
# age-0 recruit cohort (copula-sampled traits if the opt-in `recruit_copula` hook is set, else the fixed
# `sapl`), a K-cap MERGE bounds the cohort count, and `age` is a genuine per-cohort age — so `age_mean` is a
# true nind-weighted demographic mean (the DRF is retrained on it; closes the ADR-0023 §3 counter trap).

"""
    FluxDrivenSlowEmulator{T} <: AbstractSlowEmulator

Tier-1 concrete slow emulator whose demography target is a trained flux-conditioned `DRF` forest (the
zero-dependency native-Julia distributional random forest in `src/drf.jl`) rather than a constant rate.
Holds the `forest`, the baked per-cell slow-boundary feature tail (`boundary`), the recursive count-space
AR state `n_prev`, per-year mortality/establishment caps (`max_mort`/`max_estab`, bounding the demographic
change so a mis-scaled prediction cannot blow up the stand), the fixed recruit sapling pools (`sapl`, the
shortest-tree cohort `recruit_idx`), the carbon `ledger`, per-cohort `age`, and a seeded `Random`-free
`DRF.Xoshiro256pp` `rng`. Carbon conserves at the handoff exactly as Tier-0 (`last_resid` ≤ 1e-6·C_scale).
Build with [`FluxDrivenSlowEmulator`](@ref)`(fc, forest; boundary, ...)`; wire via
`run_coupled_cell(...; slow=)`.
"""
mutable struct FluxDrivenSlowEmulator{T <: AbstractFloat} <: AbstractSlowEmulator
    forest::DRF.Forest
    boundary::Vector{Float64}
    n_prev::T
    max_mort::T
    max_estab::T
    sapl::FDiff.TreePools{T}
    recruit_idx::Int
    ledger::CarbonLedger{T}
    age::Vector{T}
    last_resid::T
    total_n_history::Vector{T}
    resid_history::Vector{T}
    target_history::Vector{T}
    year::Int
    rng::DRF.Xoshiro256pp
    k_cap::Int
    recruit_copula::Union{Nothing, RecruitCopula{T}}
end

"""
    FluxDrivenSlowEmulator(fc::FDiffFastCore{T}, forest::DRF.Forest; boundary=Float64[],
                           max_mort=0.3, max_estab=0.3, n_init=1.0, sapl=nothing, seed=1,
                           age0=0, k_cap=nothing, recruit_copula=nothing)

Construct the Tier-1 flux-driven slow emulator for a fast core: the K cohorts are `fc.pools`;
`recruit_idx` is the shortest living TREE cohort; `sapl` defaults to a small beech sapling (as Tier-0);
`boundary` is the baked per-cell slow bioclimatic feature tail appended to the flux/state/AR features (its
length + 11 must equal `forest.nfeat`); `n_init` seeds the count-space AR state (year 0 forces the
demographic-change ratio to 1, so `n_init` only sets the year-0 feature and is self-corrected by the
`max_*` clamp thereafter). `age0` (a scalar stand age or a per-cohort vector) seeds `s.age` so the runtime
`age_mean` feature starts inside the DRF's trained age band (ADR 0024 §3 — a scalar 0, the default,
reproduces the pre-0024 zero-init; the coupled app reads `age0` from the DRF meta). `k_cap` bounds the
cohort roster (default `max(2·K, 40)`); `recruit_copula` (default `nothing`) opts establishment into
copula-sampled recruit traits. Deterministic given `seed`.
"""
function FluxDrivenSlowEmulator(
        fc::FDiffFastCore{T}, forest::DRF.Forest; boundary::AbstractVector{<:Real} = Float64[],
        max_mort = T(0.3), max_estab = T(0.3), n_init = one(T),
        sapl::Union{Nothing, FDiff.TreePools{T}} = nothing, seed::Integer = 1,
        age0::Union{Real, AbstractVector} = 0, k_cap::Union{Nothing, Integer} = nothing,
        recruit_copula::Union{Nothing, RecruitCopula{T}} = nothing,
    ) where {T <: AbstractFloat}
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
    age_init = age0 isa Real ? fill(T(age0), length(fc.pools)) : collect(T, age0)
    length(age_init) == length(fc.pools) ||
        error("age0 vector length ($(length(age_init))) must equal the number of cohorts ($(length(fc.pools)))")
    kcap = k_cap === nothing ? max(2 * length(fc.pools), 40) : Int(k_cap)
    return FluxDrivenSlowEmulator{T}(
        forest, collect(Float64, boundary), convert(T, n_init), T(max_mort), T(max_estab),
        sap, ridx, CarbonLedger{T}(), age_init, zero(T), T[], T[], T[], 0,
        DRF.Xoshiro256pp(seed), kcap, recruit_copula,
    )
end

"""
    flux_feature_vector(s::FluxDrivenSlowEmulator, grow, pools, state, allom) -> Vector{Float64}

Assemble the DRF feature row (fixed order): the four `FToS`-consistent flux drivers (bm_inc, growth_eff,
water_stress, soilmoist), the six this-year patch-state aggregates from the grown tree pools (fpc-weighted
mean height, max height, stand AGB, stand LAI, capped FPC, mean cohort age), the recursive AR state
`n_prev`, then the baked slow-boundary tail. The training table must use this SAME order (ADR 0020 §6:
S is conditioned at runtime on the channel it was trained on).
"""
function flux_feature_vector(
        s::FluxDrivenSlowEmulator{T}, grow, pools, state, allom
    ) where {T <: AbstractFloat}
    fpc = zero(T); hw = zero(T); lai = zero(T); agb = zero(T)
    for p in pools
        p.is_grass && continue
        fp = FDiff._treepools_fpc(p, allom)
        fpc += fp
        hw += convert(T, p.height) * fp
        lai += convert(T, p.leaf_c) * convert(T, p.sla) * convert(T, p.nind)
        agb += FDiff.agb_ind(p) * convert(T, p.nind)
    end
    hmean = fpc > 0 ? hw / fpc : zero(T)
    hmax = zero(T)
    for p in pools
        (!p.is_grass && convert(T, p.height) > hmax) && (hmax = convert(T, p.height))
    end
    age_mean = _mean_age_weighted(s.age, pools)   # nind-weighted tree-only demographic mean age (ADR 0024)
    soilmoist = sum(state.w) / length(state.w)
    head = Float64[
        grow.bm_inc_cell, grow.growth_eff, grow.water_stress, soilmoist,
        hmean, hmax, agb, lai, min(fpc, one(T)), age_mean, s.n_prev,
    ]
    return length(s.boundary) == 0 ? head : vcat(head, s.boundary)
end

function reconcile_demography!(
        s::FluxDrivenSlowEmulator{T}, fc::FDiffFastCore{T}, grow, state::SharedState
    ) where {T <: AbstractFloat}
    cveg_start = sum(FDiff.vegc_full_ind(fc.pools[i]) * convert(T, fc.pools[i].nind) for i in eachindex(fc.pools))

    reset_year!(s.ledger)
    record_growth!(s.ledger, grow.applied_bm_cell, grow.unapplied_bm_cell)
    record_litter!(s.ledger, grow.litter_cell)

    pools = collect(grow.newpools)                 # grown at OLD nind (mutable working copy)
    tmpls = copy(fc.tmpls)                          # length-K working roster (rebuilt atomically on commit)
    pft_ids = copy(fc.pft_ids)
    ages = copy(s.age)                              # start-of-year per-cohort ages (incremented after commit)

    # ── DRF TARGET → demographic-change ratio ρ (unit-free; count↔density cancels) ──
    feats = flux_feature_vector(s, grow, pools, state, fc.allom)
    target = DRF.predict(s.forest, feats)
    ρ = if s.year == 0
        one(T)                                     # year 0: no change (seed the recursive AR state)
    else
        clamp(convert(T, target) / (s.n_prev + T(1.0e-12)), one(T) - s.max_mort, one(T) + s.max_estab)
    end

    dtree = sum(convert(T, pools[i].nind) for i in eachindex(pools) if !pools[i].is_grass; init = zero(T))

    if ρ < one(T)
        # ── MORTALITY: uniform proportional thinning of tree cohorts; carbon vegc_full·Δnind → litter ──
        mfrac = one(T) - ρ
        for i in eachindex(pools)
            p = pools[i]
            (p.is_grass || p.nind <= 0) && continue
            dn = convert(T, p.nind) * mfrac
            dn <= 0 && continue
            record_litter!(s.ledger, FDiff.vegc_full_ind(p) * dn)
            pools[i] = _with_nind(p, convert(T, p.nind) - dn)
        end
    elseif ρ > one(T) && s.recruit_idx > 0
        # ── ESTABLISHMENT: APPEND a real age-0 recruit cohort of (ρ−1)·D density (ADR 0024). The recruit's
        #    per-individual pools are the fixed `sapl`, or a copula draw if the opt-in hook is set. The whole
        #    cohort's veg C is an establishment influx (0 contribution to cveg_start, no growth accounted). ──
        dn = (ρ - one(T)) * dtree
        if dn > 0
            recruit_ind = if s.recruit_copula === nothing
                s.sapl
            else
                rc = s.recruit_copula
                traits = DRF.sample_copula!(s.rng, rc.cop, rc.axis_forests, rc.x)
                rc.to_pools(traits, s.sapl, fc.allom)::FDiff.TreePools{T}
            end
            recruit = _with_nind(recruit_ind, dn)
            push!(pools, recruit)
            push!(tmpls, fc.tmpls[s.recruit_idx])
            push!(pft_ids, fc.pft_ids[s.recruit_idx])
            push!(ages, zero(T))
            record_estab!(s.ledger, FDiff.vegc_full_ind(recruit) * dn)
        end
    end

    # ── K-cap MERGE: bound the roster (carbon-neutral; no ledger entry) ──
    _apply_kcap_merge!(pools, ages, tmpls, pft_ids, s.k_cap, fc.allom)

    # ── ATOMIC roster rebuild: replaces every length-K fc field + s.age in lockstep (design risk #5) ──
    _commit_membership!(s, fc, pools, tmpls, pft_ids, ages)

    cveg_end = sum(FDiff.vegc_full_ind(pools[i]) * convert(T, pools[i].nind) for i in eachindex(pools))
    s.last_resid = handoff_carbon_residual(s.ledger; c_veg_delta = cveg_end - cveg_start)
    s.n_prev = convert(T, target)                   # recursive count-space AR update
    s.year += 1
    s.age .+= one(T)
    push!(s.total_n_history, sum(convert(T, p.nind) for p in pools))
    push!(s.resid_history, s.last_resid)
    push!(s.target_history, convert(T, target))

    soilmoist = sum(state.w) / length(state.w)
    return FToS{T}(
        bm_inc = grow.bm_inc_cell, water_stress = grow.water_stress, temp_stress = zero(T),
        growth_eff = grow.growth_eff, soilmoist = convert(T, soilmoist),
    )
end

"The DRF demographic targets predicted per year (count-space) — the recursive AR trajectory."
target_history(s::FluxDrivenSlowEmulator) = s.target_history
