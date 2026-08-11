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
# + copula-sampled recruit traits. See `docs/notes/p1_s_in_loop_design.md`.

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
    (fc.inds, fc.rootdists) = FDiff.individuals_from_pools(
        fc.tmpls, pools, fc.allom, fpars, fc.soil; per_tree = fc.params.water.per_tree_roots,
    )   # ADR 0110

    # reset the within-year accumulators + per-PFT phenology cold-start (mirrors annual_step!)
    fill!(fc.bm_inc_acc, zero(T))
    # ADR 0110: the C resets `tree->water_stress` at the coldest day (`waterstress_tree.c:39-42`) and
    # `temp_stress`/`aphen` at the start of the vegetation period; the emulator's year boundary is the
    # one reset point it has, so all three clear here with `bm_inc_acc`.
    fill!(fc.water_stress_acc, zero(T))
    fill!(fc.temp_stress_acc, zero(T))
    fill!(fc.aphen_acc, zero(T))
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

    # ADR 0035 — root-zone, whcs-weighted (NOT the pre-0035 unweighted 23-layer mean)
    soilmoist = root_zone_soilmoist(state, fc.soil)
    return FToS{T}(
        bm_inc = grow.bm_inc_cell, water_stress = grow.water_stress, temp_stress = zero(T),
        growth_eff = grow.growth_eff, soilmoist = convert(T, soilmoist),
    )
end

"""
    ROOT_ZONE_LAYERS

Number of top soil layers that constitute the **root zone** for the `soilmoist` conditioning feature —
the C's `forrootmoist` (`include/soil.h:353`, `for(l=0;l<3;l++)`, "here defined for the first 1 m"), i.e.
the 200 + 300 + 500 mm layers of `par/soil_20m.js`. Load-bearing: the training feature is derived from the
C's `rootmoist` output, which is summed over exactly this layer set (ADR 0035).
"""
const ROOT_ZONE_LAYERS = 3

"""
    root_zone_soilmoist(state::SharedState, soil) -> Float64

The `soilmoist` conditioning feature: plant-available soil water in the **root zone** (the top
[`ROOT_ZONE_LAYERS`](@ref) layers ≈ 1 m) as a fraction of that zone's water-holding capacity, i.e. the
`whcs`-weighted mean of `state.w` — which is what `FToS.soilmoist` has always been documented to be
("root-zone soil moisture state, fraction of WHC", `interface.jl`).

**This is the runtime half of an ADR-0035 train/inference contract, so it must not drift.** The training
column is the C's own `ROOTMOIST / Σ_{l<3} whcs[l]` (`scripts/build_rootmoist_soilmoist_feature.py`), where
`ROOTMOIST = Σ_{l<3} w[l]·whcs[l]` (`update_daily.c:414`) — the same weighted mean of the same variable
over the same layers. It replaces the pre-0035 unweighted 23-layer mean `sum(state.w)/length(state.w)`,
which was matched against the C's `swc` output — a DIFFERENT QUANTITY (total water over SATURATION
capacity, `update_daily.c:411`), not merely a different time aggregation as ADR 0034 assumed.

Degenerate columns are tolerated because unit harnesses build short ones: the layer count is capped at
`length(whcs)`, and a zero-capacity root zone returns 0.
"""
function root_zone_soilmoist(state::SharedState, soil)
    whcs = soil.whcs
    nr = min(ROOT_ZONE_LAYERS, length(whcs), length(state.w))
    nr <= 0 && return 0.0
    num = 0.0; den = 0.0
    for l in 1:nr
        c = Float64(whcs[l])
        num += Float64(state.w[l]) * c
        den += c
    end
    return den > 0 ? num / den : 0.0
end

"Rebuild a `FDiff.TreePools` with a new `nind` (all other fields unchanged)."
_with_nind(p::FDiff.TreePools{T}, n) where {T} = FDiff.TreePools{T}(
    p.leaf_c, p.sapwood_c, p.heartwood_c, p.root_c, p.sapwood_bg_c,
    p.height, p.crownarea, convert(T, n), p.sla, p.wooddens,
    p.d95max, p.minwscal,                     # ADR 0110 — a density change must not reset the traits
    p.is_grass,
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
a fallback conditioning row `x`, `to_pools` (a mapping
`(traits::Vector{Float64}, sapl::FDiff.TreePools{T}, allom) -> FDiff.TreePools{T}` turning one drawn trait
vector into a recruit's per-individual pools; see [`make_recruit_to_pools`](@ref)), and `cond`, the
CONDITIONING POLICY `(s, feats) -> AbstractVector{Float64}` that builds the row the axis marginals are keyed
on each year from the live DRF feature vector (ADR 0025). When a `FluxDrivenSlowEmulator` carries one,
establishment draws recruit traits from `s.rng` (deterministic) instead of using the fixed `sapl`.

The 4-argument constructor `RecruitCopula{T}(cop, axis_forests, x, to_pools)` defaults `cond` to a STATIC
policy that returns the baked `x` every year (the pre-ADR-0025 behaviour ⇒ existing gates byte-identical);
production copulas pass [`live_flux_cond`](@ref) so recruit traits track the cell's climate/flux year to
year. Production axis artifacts + the correlation matrix are a multi-cell concern; at a single beech cell
the trait axes are near-degenerate, so the emulator default is `nothing` (fixed sapling).
"""
struct RecruitCopula{T <: AbstractFloat}
    cop::DRF.GaussianCopula
    axis_forests::Vector{DRF.Forest}
    x::Vector{Float64}
    to_pools::Any
    cond::Any
    qrf::Bool
end

# ADR 0037: `qrf` selects the marginal estimator used at establishment — `false` (DEFAULT) the historical
# equal-weight pooling of every tree's leaf values, `true` the Meinshausen quantile-regression-forest
# weighting (see `DRF.predict_quantile`). It MUST match the estimator the artifact's published skill numbers
# and golden draw pairs were produced under (`scripts/train_slow_copula.jl` writes `qrf_weighting` into the
# `.rcop` meta for exactly this reason) — otherwise the runtime samples a different conditional distribution
# than was evaluated, which is the ADR-0023 train/inference shift and is SILENT: the draws stay in range.
# Defaulted in EVERY constructor so all pre-ADR-0037 call sites (including line M's) are byte-identical.
function RecruitCopula{T}(
        cop::DRF.GaussianCopula, axis_forests::Vector{DRF.Forest}, x::Vector{Float64}, to_pools, cond;
        qrf::Bool = false,
    ) where {T <: AbstractFloat}
    return RecruitCopula{T}(cop, axis_forests, x, to_pools, cond, qrf)
end

"Static conditioning policy: ignore `(s, feats)` and return the baked row `x` (the pre-ADR-0025 behaviour)."
_static_cond(x::Vector{Float64}) = (_s, _feats) -> x

# Backward-compatible 4-arg constructor: STATIC conditioning on `x` (feats ignored) ⇒ every pre-ADR-0025
# `RecruitCopula` (incl. the committed copula gates) is byte-identical. Production passes `live_flux_cond`.
function RecruitCopula{T}(
        cop::DRF.GaussianCopula, axis_forests::Vector{DRF.Forest}, x::Vector{Float64}, to_pools;
        qrf::Bool = false,
    ) where {T <: AbstractFloat}
    return RecruitCopula{T}(cop, axis_forests, x, to_pools, _static_cond(x), qrf)
end

"""
    live_flux_cond(s, feats) -> Vector{Float64}

The production recruit-copula conditioning policy (ADR 0025): condition the axis marginals on climate/flux +
bioclimate ONLY — the four `FToS` flux drivers `feats[1:4]` (`bm_inc_cell, growth_eff, water_stress,
soilmoist`) followed by the per-cell `s.boundary` tail — and DELIBERATELY exclude the six this-year
patch-state aggregates + `n_prev` (`feats[5:11]`). Establishment traits respond to the ENVIRONMENT, not to
the stand's own recursive state (which would be a feedback loop, and is the emergent quantity S predicts
rather than conditions on). This subset + ORDER is the copula's feature-order contract: the axis forests
(`scripts/train_slow_copula.jl`) MUST be trained on exactly `[bm_inc_cell, growth_eff, water_stress,
soilmoist, <boundary…>]`. `feats` is always `Float64` (the DRF channel), so the returned row is too.
"""
live_flux_cond(s, feats::AbstractVector) = vcat(Vector{Float64}(feats[1:4]), s.boundary)

"""
    live_flux_cond_env(env) -> (s, feats) -> Vector{Float64}

ADR 0037 — the EXTENDED recruit-copula conditioning policy: exactly [`live_flux_cond`](@ref)'s row
(`feats[1:4]` + `s.boundary`) with a per-cell ENVIRONMENTAL tail `env` APPENDED.

Why it exists. The boundary tail carries `eco_diag_gdd_5`, `tas_cold_month`, `soil_depth`, `co2` — i.e. a
temperature and a soil axis and **no moisture or precipitation climatology at all** — while FIT's
establishment gates are temperature AND moisture. Measured on the `t8` global generation, adding the wider
climate descriptors lifts the attainable per-cell trait skill by +0.011 (SLA) / +0.025 (Wooddens) /
+0.042 (D95max), and on Wooddens an environment-only predictor (0.910) BEATS the eight production
conditioning columns (0.893).

Why it is a FACTORY rather than a new field. `RecruitCopula.cond` is already a pluggable policy
`(s, feats) -> AbstractVector{Float64}` (ADR 0025), so extending the conditioning needs NO change to any
struct, to the `.rcop` format, or to `live_flux_cond` itself — every existing construction stays
byte-identical (guardrail 4) and line M's pinned artifacts keep working untouched. The extended
conditioning arrives only when a caller deliberately passes this policy together with a `.rcop` whose
`cond_cols` declare the same columns in the same order.

LOAD-BEARING: `env` MUST be the same columns, in the same order and on the same basis, as the tail of
`COPULA_COND_COLS` that the `.rcop` was trained on (`scripts/build_slow_runtime_table.py`, env knob
`COPULA_ENV_COLS`; the artifact's `cond_cols` line is the contract). A mismatch is the ADR-0023
train/inference shift, and it is SILENT — the marginal forests would simply be read at the wrong
coordinates while still returning in-range traits. Check `length(env) + 4 + length(s.boundary)` against the
`.rcop`'s `ncond` before trusting a coupled run.
"""
function live_flux_cond_env(env::AbstractVector{<:Real})
    envv = Vector{Float64}(env)
    return (s, feats) -> vcat(Vector{Float64}(feats[1:4]), s.boundary, envv)
end

"""
    live_flux_cond_env_series(env_series) -> (s, feats) -> Vector{Float64}

ADR 0108 — the **TRANSIENT** extended recruit-copula conditioning policy: exactly
[`live_flux_cond_env`](@ref)'s row, but the environmental tail advances **per simulation year** instead of
being one frozen vector. `env_series` is a per-year `Vector` of tails (each the same length), indexed
`s.year + 1` and clamped so post-series years reuse the last row — the SAME indexing
[`FluxDrivenSlowEmulator`](@ref)'s `boundary_series` uses, and evaluated in the same year: the boundary
advance and `rc.cond(s, feats)` both run before `s.year += 1`, so the two tails are always read at the same
year.

Why it exists. `live_flux_cond_env(env)` closes over a constant, so with the ADR-0037 tail the six moisture
descriptors — the SLOW, 20-year-window moisture climate FIT's establishment gates key on — are frozen at a
cell's present-day values, and that channel carries nothing under a changing climate. ⚠ It does NOT follow
that the emulator has no trait response: the frozen tail is 6 of 14 columns, and `water_stress`/`soilmoist`
(per-cell-year flux drivers) plus the transient boundary pair are the other channel. Measured on the shipped
`_t8` generation (52 074 cells, K-fold-by-cell OOS), the per-cell response `median(ssp370) − median(historic)`
already regresses on the C truth's own response with slope **+0.85** (SLA) / **+0.35** (Wooddens) / **+0.16**
(D95max) / **+0.69** (minwscal) — partial, axis-dependent, and worst on the rooting-depth trait. So this
policy is there to open the frozen channel and be MEASURED against those slopes, not to move a response off
zero. The tables it consumes carry a real signal (global mean VPD +20.4 %, PET +4.9 %, humidity +19.9 %,
2019→2100), and the acceptance criterion is a climate-change criterion (ADR 0106).

LOAD-BEARING, and it fails SILENTLY in a way the width probe CANNOT catch (ADR 0023). A static-tail and a
transient-tail artifact have the **same `ncond`** and the **same `cond_cols`**, so
`FluxDrivenSlowEmulator`'s conditioning-width check passes for either policy paired with either artifact.
Pairing them wrong reads the marginal forests at systematically wrong coordinates while still returning
in-range traits. The artifact's manifest `env_basis` line is the only discriminator: `transient_w<W>` needs
THIS policy, `static_cell_mean` needs [`live_flux_cond_env`](@ref).

Each row must be the same columns in the same order as the tail of the artifact's `cond_cols`
(`scripts/build_slow_runtime_table.py`, knobs `COPULA_ENV_COLS` + `ENV_WINDOW`), and row `k` must be that
cell's tail for the artifact's `firstyear + k - 1`.
"""
function live_flux_cond_env_series(env_series::AbstractVector)
    ser = [collect(Float64, row) for row in env_series]
    isempty(ser) && error("live_flux_cond_env_series: env_series must be non-empty")
    w = length(ser[1])
    all(length(r) == w for r in ser) ||
        error("live_flux_cond_env_series: every env_series row must have the same length (first is $w)")
    return (s, feats) -> vcat(
        Vector{Float64}(feats[1:4]), s.boundary, ser[clamp(s.year + 1, 1, length(ser))]
    )
end

"""
    make_recruit_to_pools(axis_names) -> to_pools

Build the canonical `RecruitCopula.to_pools` mapping for a production copula bundle (the function is NOT
serialized — `DRF.load_copula` returns `axis_names`, and this reconstructs the mapping from them).
The returned `to_pools(traits, sapl, allom)` overwrites only the two trait axes that F_diff actually consumes
— `SLA`→`sla`, `Wooddens`→`wooddens` (located by name in `axis_names`, so axis ORDER is irrelevant) — keeps
every carbon pool of the fixed `sapl` UNCHANGED (so the establishment carbon debit is independent of the
draw ⇒ conservation is unaffected), and re-derives height from the pipe model + crownarea from the Jucker
allometry (matching `_merge_pair!`). Other axes (e.g. `D95max`, `minwscal`) are sampled + validated but have
no per-tree consumer yet, so they do not enter `TreePools`. Errors if `SLA`/`Wooddens` are absent.
"""
function make_recruit_to_pools(axis_names::AbstractVector{<:AbstractString})
    isla = findfirst(==("SLA"), axis_names)
    iwd = findfirst(==("Wooddens"), axis_names)
    (isla === nothing || iwd === nothing) &&
        error("make_recruit_to_pools: axes must include \"SLA\" and \"Wooddens\"; got $(axis_names)")
    i_sla = Int(isla)                                # single-assignment Int captures (JET-safe, type-stable)
    i_wd = Int(iwd)
    # ADR 0110: `D95max` (rooting depth, cm) and `minwscal` (drought tolerance) now HAVE per-tree consumers
    # — a per-individual root profile feeding a per-individual water status, and that individual's own
    # drought-death threshold. Both are located BY NAME and both are OPTIONAL: an artifact whose axis list
    # lacks them yields index 0 ⇒ the trait is left UNSET (0) on `TreePools` ⇒ that individual keeps the
    # shared cell profile and carries no threshold, i.e. exactly the pre-0110 behaviour. So an older `.rcop`
    # still loads and still produces byte-identical pools. Single-assignment Ints (JET-safe, as above).
    i_d95 = (j = findfirst(==("D95max"), axis_names); j === nothing ? 0 : Int(j))
    i_mws = (j = findfirst(==("minwscal"), axis_names); j === nothing ? 0 : Int(j))
    function to_pools(traits, sapl::FDiff.TreePools{T}, allom) where {T <: AbstractFloat}
        # 0 (axis absent) stays 0 — the UNSET sentinel — and must NOT be clamped up, so the two optional
        # axes are passed through `_recruit_pools`'s `unset` path rather than clamped here.
        return _recruit_pools(
            traits[i_sla], traits[i_wd],
            i_d95 == 0 ? nothing : traits[i_d95], i_mws == 0 ? nothing : traits[i_mws],
            sapl, allom,
        )
    end
    return to_pools
end

"""
    _recruit_pools(sla, wooddens, d95max, minwscal, sapl::FDiff.TreePools{T}, allom) -> FDiff.TreePools{T}

Build a recruit's per-individual pools from four drawn trait values — the ONE place a sampled recruit
becomes a `TreePools`, shared by the copula sampler ([`make_recruit_to_pools`](@ref)) and by the ported
FIT establishment rule ([`RecruitEstablishment`](@ref)). Two samplers landing on two slightly different
pool constructions would make their arms incomparable for a reason that has nothing to do with the
samplers, so there is exactly one code path.

Every carbon pool of the fixed `sapl` is kept UNCHANGED (so the establishment carbon debit is independent
of the draw ⇒ conservation is unaffected); height is re-derived from the pipe model and crown area from
the Jucker allometry (matching `_merge_pair!`). `sla`/`wooddens` are clamped to the union of the C's
per-PFT sampling intervals, `d95max` to `[51, 1800]` cm and `minwscal` to `[0.025, 0.75]` — a value
outside those is a sampler tail, not physics. Passing `nothing` for either optional axis leaves it at the
UNSET sentinel 0 (that individual keeps the shared cell root profile and carries no drought threshold,
i.e. the pre-ADR-0110 behaviour).
"""
function _recruit_pools(
        sla, wooddens, d95max, minwscal, sapl::FDiff.TreePools{T}, allom
    ) where {T <: AbstractFloat}
    sla_n = clamp(convert(T, sla), convert(T, 1.0e-3), convert(T, 0.1))
    wd_n = clamp(convert(T, wooddens), convert(T, 5.0e4), convert(T, 7.0e5))
    d95_n = d95max === nothing ? zero(T) :
        clamp(convert(T, d95max), convert(T, 51.0), convert(T, 1800.0))
    mws_n = minwscal === nothing ? zero(T) :
        clamp(convert(T, minwscal), convert(T, 0.025), convert(T, 0.75))
    leaf = convert(T, sapl.leaf_c)
    sapw = convert(T, sapl.sapwood_c)
    h = leaf > zero(T) ?
        convert(T, allom.k_latosa) * sapw / (leaf * sla_n * wd_n) :
        convert(T, sapl.height)
    crown = convert(T, Allometry.crown_area(allom, h))
    return FDiff.TreePools{T}(
        leaf, sapw, convert(T, sapl.heartwood_c), convert(T, sapl.root_c),
        convert(T, sapl.sapwood_bg_c), h, crown, one(T), sla_n, wd_n, d95_n, mws_n, false,
    )
end

"""
    EstabDiag

One year's ported-establishment diagnostics (ADR 0119): the simulation `year`, whether a recruit was drawn
at all (`drew`), the drawn recruit's `pft_id`, whether it came from the seedbank (`inherited`), the number
of bioclimatically eligible PFTs (`n_elig`) and the inherited share that implied (`w_inherit`), and the
seedbank's size in entries (`sb_entries`) and individual-years (`sb_weight`).

**Read `sb_weight` and `inherited` before interpreting any arm run with this operator.** The ported rule
has two channels with different marginals, mixed at a weight that depends on the cell's eligible-PFT
count, and the inheritance channel cannot fire at all until the seedbank has filled. An arm whose
seedbank stayed empty measured the uniform background channel and nothing else — the same class of null
that ADR 0048 had to correct once already, and the reason `trait_mortality` records `theta`.
"""
struct EstabDiag
    year::Int
    drew::Bool
    pft_id::Int
    inherited::Bool
    n_elig::Int
    w_inherit::Float64
    sb_entries::Int
    sb_weight::Float64
end

"""
    RecruitEstablishment{T}(; seedbank = Establishment.Seedbank{T}(), eligible = 0:6, set_pft_id = false)

Opt-in **ported FIT establishment rule** for recruit traits (ADR 0119) — the alternative to
[`RecruitCopula`](@ref) that computes the recruit marginal from the C's parameters instead of learning it
from the C's output. Pass it as `FluxDrivenSlowEmulator(...; recruit_establishment = ...)`; the default
`nothing` leaves every code path byte-identical.

WHY IT IS NOT A COPULA VARIANT. The copula's marginals are fit on FIT's `ind` output, which holds only
stems above 5 m — survivors — so they already carry the trait selection ADR 0049's mortality operator
adds, double-counting it by a measured +12.18 % on `Wooddens` within a cell-PFT group (ADR 0118 §1-2).
This rule reads no FIT output at all: uniform draws on each PFT's own intervals, mixed with inheritance
from the emulator's own top-AGB seedbank at the closed-form weight `4/(4 + n_elig)` (ADR 0045). See
`Establishment` for the ported equations and their C line numbers.

Fields:
  * `seedbank` — the rolling top-AGB `Establishment.Seedbank`, updated from the emulator's OWN roster
    every year by `reconcile_demography!` (before thinning, matching FIT's `getsapling` before
    `annual_stand`). Starts EMPTY, so the first years draw from the background channel only; seed it by
    calling `Establishment.seedbank_update!` yourself if an arm needs a warm bank at year 0.
  * `eligible` — the bioclimatic eligibility policy: either a fixed collection of PFT ids, or a callable
    `s -> ids` evaluated each year (e.g. from a `ClimBuf`'s 20-year window via
    `Establishment.eligible_pfts`). A fixed set is the honest default for a single cell whose eligible set
    is climatologically stable; a callable is what opens the gate under warming.
  * `set_pft_id` — `false` (default) keeps the recruit cohort's PFT id and canopy template from the
    shortest-tree cohort, as the copula path does, and records the drawn id in the diagnostics only.
    `true` writes the DRAWN id into `fc.pft_ids`, which changes the recruit's phenology and (with
    `trait_mortality`) its mortality parameters — but NOT its `FDiff.Individual` template, which still
    carries the donor cohort's per-PFT physiology (`alphaa`, `emax`, `intc`, albedos, `photo`,
    `tstress`). ⚠ So `true` produces a deliberately INCONSISTENT individual until a per-PFT template
    registry exists; it is here to be measured, not to be switched on by default. That registry is the
    integration point with line M (`fc.tmpls` is built by M's drivers).
    ⚠ It is also BOUNDED BY THE FAST CORE: `_commit_membership!` refuses a cohort whose PFT id is absent
    from `fc.pft_slot` (the per-PFT phenology registry, built once at `FDiffFastCore` construction), so
    with `set_pft_id = true` every eligible id must already be in the roster. The
    `FluxDrivenSlowEmulator` constructor checks that up front for a fixed eligible set rather than letting
    it fail mid-run.
  * `diag` — per-year [`EstabDiag`](@ref) records. Empty ⇒ the operator never drew, which is how a probe
    proves the rule fired before interpreting a trajectory.
"""
mutable struct RecruitEstablishment{T <: AbstractFloat}
    seedbank::Establishment.Seedbank{T}
    eligible::Any
    set_pft_id::Bool
    diag::Vector{EstabDiag}
end
function RecruitEstablishment{T}(;
        seedbank::Establishment.Seedbank{T} = Establishment.Seedbank{T}(),
        eligible = 0:6, set_pft_id::Bool = false,
    ) where {T <: AbstractFloat}
    # A FIXED eligible set is checked here, at construction: `Establishment.pft_estab_params` would
    # otherwise error the first time the background channel happened to pick the bad id, which — because
    # the channel is a Bernoulli draw on `w_inherit` — may be many years into a run or never. A callable
    # policy is checked when it is applied (same error, first offending year).
    if !(eligible isa Function)
        ids = collect(Int, eligible)
        for id in ids
            Establishment.pft_estab_params(id)      # errors on grass/crop/out-of-range
        end
        isempty(ids) && isempty(seedbank.entries) && error(
            "RecruitEstablishment: `eligible` is empty and the seedbank is empty — neither channel can " *
                "produce a recruit. Pass the cell's eligible PFT ids (`Establishment.eligible_pfts`), or " *
                "a callable policy if the gate should move with the climate."
        )
    end
    return RecruitEstablishment{T}(seedbank, eligible, set_pft_id, EstabDiag[])
end
RecruitEstablishment(; kwargs...) = RecruitEstablishment{Float64}(; kwargs...)

"The eligible PFT ids this year: a fixed collection is returned as-is, a callable is applied to `s`."
_estab_eligible(re::RecruitEstablishment, s) =
    re.eligible isa Function ? collect(Int, re.eligible(s)) : collect(Int, re.eligible)

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
    _merge_pair!(pools, ages, tmpls, pft_ids, i, j, allom; counters=nothing)

Fold tree cohort `j` into `i` (`i<j`): `nind_m = n_i+n_j`; each of the FIVE carbon pools nind-weighted
(so `vegc_full_ind(m)·nind_m == Σ vegc_full_ind(parent)·nind_parent` to floating-point rounding —
carbon-neutral, NO ledger entry); age nind-weighted; the dominant (higher-nind) parent's `sla`/`wooddens`/
`tmpl`/`pft_id` inherited (keeps `tmpl.photo.sla` consistent with `pools.sla`); height re-derived from the
pipe model (guarded `leaf>0`) and crownarea from the Jucker allometry (both carbon-free). Deletes slot `j`
from all four roster vectors.
`counters` (ADR 0049, default `nothing` ⇒ every pre-0049 call is byte-identical) is the optional
per-cohort `bm_inc_counter` roster vector, kept in lockstep: the merged cohort inherits the DOMINANT
parent's counter — the same rule the traits already follow, because the counter is a property of the same
individual whose `sla`/`wooddens` are inherited. The merge is trait-DESTRUCTIVE at 3.1–5.1× the Phase-3A
signal when it fires and never fires at the default `k_cap` (ADR 0048); carrying one more field through it
does not change that verdict.
"""
function _merge_pair!(
        pools::Vector{FDiff.TreePools{T}}, ages::Vector{T}, tmpls, pft_ids, i::Int, j::Int, allom;
        counters::Union{Nothing, Vector{Int}} = nothing,
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
    # ADR 0110: the rooting-depth and drought-tolerance traits take the DOMINANT parent's values, exactly
    # as `sla`/`wooddens` do. Without this the merge would silently reset both to the 11-arg constructor's
    # UNSET 0 at every K-cap merge — i.e. quietly delete the per-tree rooting channel from the surviving
    # cohort. (This is why the merge is called out in ADR 0110 §5 step 1.)
    d95_m = convert(T, pools[dom].d95max)
    mws_m = convert(T, pools[dom].minwscal)
    tmpl_m = tmpls[dom]
    pft_m = pft_ids[dom]
    h_m = leaf_m > zero(T) ?
        convert(T, allom.k_latosa) * sapw_m / (leaf_m * sla_m * wd_m) :
        convert(T, pools[dom].height)
    crown_m = convert(T, Allometry.crown_area(allom, h_m))
    pools[i] = FDiff.TreePools{T}(
        leaf_m, sapw_m, heart_m, root_m, sbg_m, h_m, crown_m, nm, sla_m, wd_m, d95_m, mws_m, false,
    )
    ages[i] = age_m
    tmpls[i] = tmpl_m
    pft_ids[i] = pft_m
    if counters !== nothing
        counters[i] = counters[dom]
    end
    deleteat!(pools, j)
    deleteat!(ages, j)
    deleteat!(tmpls, j)
    deleteat!(pft_ids, j)
    counters === nothing || deleteat!(counters, j)
    return nothing
end

"""
    _apply_kcap_merge!(pools, ages, tmpls, pft_ids, k_cap, allom; counters=nothing)

While the roster exceeds `k_cap`, merge the tree-cohort pair with the smallest `|Δheight|` (deterministic
single-pass index-order scan; strict `<` keeps the first argmin ⇒ reproducible on ties). Bounds K (the
structural speed-up invariant) with minimal size-distribution distortion. Stops if fewer than two live
tree cohorts remain. `counters` is forwarded to [`_merge_pair!`](@ref) (ADR 0049; default `nothing`).
"""
function _apply_kcap_merge!(
        pools::Vector{FDiff.TreePools{T}}, ages, tmpls, pft_ids, k_cap::Int, allom;
        counters::Union{Nothing, Vector{Int}} = nothing,
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
        _merge_pair!(pools, ages, tmpls, pft_ids, bi, bj, allom; counters = counters)
    end
    return nothing
end

# ── TRAIT-DEPENDENT MORTALITY (Phase 3A Stage 2, ADR 0049) ───────────────────────────────────────────
# The opt-in operator that gives Component S a within-PFT selection channel. Everything below is reached
# ONLY from `reconcile_demography!` when `s.trait_mortality === true`; the default construction never
# touches it, so every committed baseline stays byte-identical (guardrail 4).

"""
    TraitMortDiag

One year of the trait-mortality operator's own diagnostics (ADR 0049). Recorded in
`FluxDrivenSlowEmulator.mort_diag`; never feeds the dynamics.

It exists because of a measured failure mode, not for tidiness: ADR 0048's first attempt reported a clean
null that meant nothing, because the operator under test had never actually fired. `hazard_mean`,
`theta` and `thinned` make "did it run, and how hard" an OBSERVABLE rather than an inference from a
trajectory. Read them before believing any before/after Δ.

  - `hazard_mean` — `nind`-weighted mean of FIT's own one-year hazard `mort` over the live tree cohorts,
    BEFORE the count constraint is imposed. This is the ported physics; `theta` is the reconciliation.
  - `theta` — the proportional-hazards tilt applied to hit the DRF's count target (`NaN` in a year with no
    thinning). `θ ≈ 1` means FIT's hazard and the DRF's count target agree; `θ > 1` that the DRF wants MORE
    death than the hazard produces, `θ < 1` less. It is the single most informative number the operator
    emits — it says how far the ported physics is from the trained count skill, on this cell, this year.
  - `hard_kills` — tree cohorts whose hazard was exactly 1 (a 5-year negative-increment run, or leaf carbon
    below a sapling's). These die in full at any `θ > 0`, which is faithful but is also the one way the
    operator can refuse the DRF's count target — see `shortfall`.
  - `shortfall` — relative count MISS `|achieved − target| / n_tree` in a year where NO tilt could reach the
    DRF's target (`0` in a normal year): either the hard kills alone remove more density than `ρ` allows, or
    the hazard is zero on every cohort so there is nothing to tilt. Non-zero means the hazard overrode the
    count target for that year; if it is ever routinely non-zero the arm is no longer "the DRF sets the
    count", and the ADR's central claim fails. It is reported, never silently absorbed.
"""
struct TraitMortDiag
    year::Int
    hazard_mean::Float64
    theta::Float64
    hard_kills::Int
    thinned::Bool
    shortfall::Float64
end

"""
    _cohort_bm_delta(fc, grow, i, reprod) -> Real

FIT's per-individual `bm_delta` (`mortality_tree_ind.c:66`, `= bm_inc.carbon/nind − turnover_ind`) for
cohort `i`, reconstructed from what the fast core actually accounted. It is the numerator of `greff`, so
it carries the SECOND half of the trait channel (denser wood grows more slowly ⇒ lower `greff` ⇒ HIGHER
`mort_npp`, opposing the `mort_max` advantage — ADR 0046 §3).

Derivation, from `grow_annual_accounted!`'s own identity rather than a re-implementation of it: the
delivered per-individual increment is `bm_ind = fc.bm_inc_acc[i]/nind` (still live and index-aligned with
`fc.pools` at the `reconcile_demography!` call site — `_commit_membership!` is what reallocates it), and
for a GROWING cohort the F core routes `bm_ind·(1−reprod) − Δvegc_ind` to litter, which is exactly
`turnover_ind`. Hence

```
bm_delta = bm_ind − turnover_ind = Δvegc_ind + reprod·bm_ind          (growing)
bm_delta = bm_ind                                                     (STAGNATED)
```

The stagnation branch is not a special case bolted on: `grow_individual` FREEZES a tree with
`bm_net ≤ 0` or `height ≤ 0`, so it applies no turnover and `Δvegc_ind` is 0 — the individual's whole
deficit IS `bm_ind`, and reporting `Δvegc_ind + reprod·bm_ind` there would understate it by 10×, turning a
dying tree's escalating hazard into a mild one. The predicate mirrors `grow_annual_accounted!`'s
`stagnated` exactly (`fast.jl:360-362`); if that test ever changes, this must change with it.

⚠ Residual known inexactness, stated rather than hidden: for the abnormal-allocation branch the F core's
litter also carries extra shed leaf (`FDiff._turnover_litter`), which this attributes to `turnover_ind`.
That is turnover-LIKE but is not FIT's `turnover_tree` product, so `bm_delta` is slightly low (hazard
slightly high) for a cohort in that branch. It is a per-cohort effect of the same sign in every arm, so
it does not confound a controlled before/after difference (ADR 0048), and it is bounded by the litter the
branch reports.
"""
function _cohort_bm_delta(fc::FDiffFastCore{T}, grow, i::Int, reprod::T) where {T}
    old = fc.pools[i]
    new = grow.newpools[i]
    nind = convert(T, old.nind)
    bm_ind = convert(T, fc.bm_inc_acc[i]) / (nind + T(1.0e-12))
    bm_net = bm_ind >= zero(T) ? bm_ind * (one(T) - reprod) : bm_ind
    stagnated = convert(T, old.height) <= zero(T) || bm_net <= zero(T)
    stagnated && return bm_ind
    dveg_ind = FDiff.vegc_full_ind(new) - FDiff.vegc_full_ind(old)
    return dveg_ind + reprod * bm_ind
end

"""
    _trait_hazards!(haz, counters, s, fc, grow, pools, pft_ids) -> (hazard_mean, hard_kills)

Evaluate FIT's ported per-individual hazard (`TraitMortality.mortality_hazard`) for every live TREE cohort
and advance each cohort's `bm_inc_counter`. Fills `haz[i]` with the one-year death probability (`0` for
grass and dead slots) and returns the `nind`-weighted mean over trees plus the number of hard kills.

This runs EVERY year the operator is enabled, thinning or not, because `bm_inc_counter` is genuine
per-individual state whose recursion (`mortality_tree_ind.c:71-81`) has no gap in it — a counter advanced
only in thinning years would drift out of step with FIT's and would reset the escalation the hard kill at
5 depends on. It is **not recoverable** from the annual `ind` output (a commented-out RAW-only column), so
the rollout evolves it itself from 0; a fresh emulator therefore under-hazards its declining cohorts for
the first few years, which is a spin-up property of the arm, not of the hazard.

WHAT THIS FEEDS THE PORTED HAZARD, AND WHAT IT DELIBERATELY DOES NOT (ADR 0049 §3 — read before scoring):

  - `wooddens`/`sla` per cohort, `age = s.age[i]` (the START-of-year age, which IS the C's pre-increment
    `tree->age`: `s.age` is incremented after the commit, `annual_tree.c:46` after the mortality call),
    `leafarea = leaf_c·sla` and `leaf_c` from the GROWN pools (the C evaluates them post-allocation), and
    `bm_delta` from [`_cohort_bm_delta`](@ref).
  - `water_stress = 0` and `temp_stress = 0`, so `mort_water` and `mort_temp` are IDENTICALLY ZERO. This is
    a stated limitation, not an oversight. FIT's `tree->water_stress` is a gated daily integral of
    `phen·(vpd/1000)·((mort_water_res − minwscal) − wscal)` (`waterstress_tree.c:31-42`) and its
    `temp_stress` an integer count of days outside `temp_stressed` (`tempstress_tree.c:29`); the emulator
    has NEITHER on that basis — `grow.water_stress` is `1 − wscal_mean`, a bounded [0,1] annual mean of a
    different quantity on a different scale (ADR 0051 is the record of how expensive confusing those two
    already was). Feeding it into a ported equation as though it were FIT's integral is the ADR-0023
    train/inference shift with extra steps. The cost is bounded and known: `mort_temp` is not
    trait-dependent at all, and `mort_water`'s only per-cohort variation is the per-PFT
    `mort_water_factor` — i.e. a BETWEEN-PFT composition effect, not the within-PFT channel ADR 0046
    measured as the lever. Both hazards' contribution to the LEVEL is absorbed by the tilt `θ` below.

`pft_mort_params` errors on a non-tree id rather than defaulting to beech, so a caller that has not wired
`fc.pft_ids` fails loudly here (ADR 0031's defect class, M integration point #1) instead of silently
running the Amazon on temperate wood-density mortality.
"""
function _trait_hazards!(
        haz::Vector{T}, counters::Vector{Int}, s, fc::FDiffFastCore{T}, grow,
        pools::Vector{FDiff.TreePools{T}}, pft_ids,
    ) where {T}
    reprod = convert(T, fc.alloc.reprod_cost)
    num = zero(T)
    den = zero(T)
    hard = 0
    @inbounds for i in eachindex(pools)
        haz[i] = zero(T)
        p = pools[i]
        # only the ORIGINAL roster has a bm_inc_acc slot / an old cohort: an appended recruit is age 0 and
        # is not subject to this year's mortality in either branch (it did not exist during the year).
        (p.is_grass || p.nind <= 0 || i > length(fc.pools)) && continue
        prm = TraitMortality.pft_mort_params(pft_ids[i])
        bm_delta = _cohort_bm_delta(fc, grow, i, reprod)
        age = convert(T, s.age[i])
        counters[i] = TraitMortality.update_bm_inc_counter(counters[i], age, bm_delta)
        # ADR 0110 Phase 2: the two hazards ADR 0049 §3 set to ZERO are now fed their OWN integrals when
        # `trait_drought_mortality` is on — `water_stress` is the C's `waterstress_tree.c` annual sum built
        # from THIS individual's own daily `wscal` against ITS OWN `minwscal`, and `temp_stress` its own
        # day count outside `[temp_low, temp_high]`. Off ⇒ both are zero and the hazard is unchanged.
        # NB these are read from `fc`, whose accumulators are index-aligned with `fc.pools` at this call
        # site (the same invariant `_cohort_bm_delta` relies on — `_commit_membership!` reallocates them).
        (ws_i, ts_i) = if fc.params.water.trait_drought_mortality && i <= length(fc.water_stress_acc)
            (convert(T, fc.water_stress_acc[i]), convert(T, fc.temp_stress_acc[i]))
        else
            (zero(T), zero(T))
        end
        h = TraitMortality.mortality_hazard(
            prm; wooddens = convert(T, p.wooddens), sla = convert(T, p.sla), age = age,
            bm_delta = bm_delta, leafarea = convert(T, p.leaf_c) * convert(T, p.sla),
            leaf_c = convert(T, p.leaf_c), water_stress = ws_i, temp_stress = ts_i,
            bm_inc_counter = counters[i],
        )
        haz[i] = convert(T, h.total)
        h.hard_kill === :none || (hard += 1)
        n = convert(T, p.nind)
        num += n * haz[i]
        den += n
    end
    return (den > zero(T) ? num / den : zero(T)), hard
end

"""
    _hazard_tilt(haz, pools, n_target, n_now) -> (theta, shortfall)

Solve for the PROPORTIONAL-HAZARDS TILT `θ ≥ 0` such that applying survival `f_i = (1 − mort_i)^θ` to
every live tree cohort reproduces the DRF's count target exactly:

```
Σ_i nind_i · (1 − mort_i)^θ  =  n_target                (n_target = ρ · n_now)
```

WHY A TILT AND NOT A RENORMALIZATION — this is the load-bearing modelling choice of ADR 0049.

The count target must stay the DRF's: it carries 0.9824 OOS R² and the hazard's job is to redistribute
*which* cohorts die, not to override how many. The naive way to impose that is a linear rescale
`f_i = λ·(1 − mort_i)`, which needs a clamp (it can hand a cohort `f_i > 1`, i.e. mortality that
*creates* individuals) and, worse, is not a hazard at all — it distorts the ratio between two cohorts'
survival by a different amount for every pair. The tilt is the textbook alternative and is exactly
FIT's own object scaled: `f_i = exp(−θ·H_i)` where `H_i = −ln(1 − mort_i)` is the cumulative hazard, so
`θ` multiplies the HAZARD RATE. It is bounded in `[0,1]` by construction, monotone in `mort_i`,
order-preserving, and it recovers FIT exactly at `θ = 1` — which is a testable statement, not a hope: a
year in which the DRF's `ρ` happens to equal the hazard's own survival returns `θ = 1` to solver
precision.

`Σ(θ)` is continuous and strictly decreasing wherever any `0 < mort_i < 1`, so a plain bisection on
`[0, θ_hi]` is exact and deterministic (no dependence on cohort ORDER — a real trap in this file, where
`-DPERMUTE`-style order sensitivity is the C's known non-determinism). Hard-killed cohorts
(`mort_i = 1`) have `f_i = 0` for every `θ > 0`, faithfully — which is the one way the operator can fail
to reach the target: if the hard kills alone remove more than `1 − ρ` of the density, no `θ` suffices.
That case returns `θ = 0` (spare everything the hazard has not condemned) and reports the residual as
`shortfall`, the relative count MISS `|achieved − n_target| / n_now`. It is a reported override of the DRF,
never a silent one — and it is reported at BOTH ends: the mirror case is a hazard that is identically zero
on every cohort (nothing to tilt), where no `θ` can remove anything at all. Both are "the count target was
unreachable given the hazard", which is exactly the situation a Stage-2 arm must not absorb quietly.
"""
function _hazard_tilt(
        haz::Vector{T}, pools::Vector{FDiff.TreePools{T}}, n_target::T, n_now::T
    ) where {T}
    # Σ nind·(1−mort)^θ over live tree cohorts
    function total(θ::T)
        acc = zero(T)
        @inbounds for i in eachindex(pools)
            p = pools[i]
            (p.is_grass || p.nind <= 0) && continue
            w = one(T) - haz[i]
            acc += convert(T, p.nind) * (w <= zero(T) ? zero(T) : w^θ)
        end
        return acc
    end
    # θ = 0 spares every cohort the hazard has not CONDEMNED (mort == 1 ⇒ 0^0 is excluded above)
    hi_total = total(zero(T))
    if hi_total <= n_target
        # the hard kills alone already overshoot the target — report, do not resurrect
        return zero(T), abs(n_target - hi_total) / (n_now + T(1.0e-12))
    end
    lo = zero(T)                      # total(lo) ≥ n_target
    hi = one(T)
    for _ in 1:200                    # grow the bracket until total(hi) ≤ n_target (finite: Σ → hard-kill floor)
        total(hi) <= n_target && break
        hi *= T(2)
    end
    if total(hi) > n_target
        # No θ removes enough — the hazard is (near) zero on every cohort, so there is nothing to tilt.
        # Bounded, so this never loops; and it REPORTS, because a silent 0 here would read as "the count
        # target was honoured" in exactly the year the operator could not honour it.
        return hi, abs(total(hi) - n_target) / (n_now + T(1.0e-12))
    end
    for _ in 1:200                    # bisection to machine precision in θ
        mid = (lo + hi) / T(2)
        (mid == lo || mid == hi) && break
        total(mid) > n_target ? (lo = mid) : (hi = mid)
    end
    return (lo + hi) / T(2), zero(T)
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

`counters` (ADR 0049; default `nothing` ⇒ every pre-0049 call is byte-identical) commits the per-cohort
`bm_inc_counter` roster in the same shot, so it cannot fall out of step with `s.age` and `fc.pools` — the
whole reason this function exists as one atomic operation (design risk #5).
"""
function _commit_membership!(
        s, fc::FDiffFastCore{T}, pools::Vector{FDiff.TreePools{T}}, tmpls, pft_ids, ages::Vector{T};
        counters::Union{Nothing, Vector{Int}} = nothing,
    ) where {T}
    all(id -> haskey(fc.pft_slot, id), pft_ids) ||
        error("_commit_membership!: an appended/merged cohort introduced a PFT id absent from fc.pft_slot")
    fc.pools = pools
    fc.tmpls = collect(FDiff.Individual{T}, tmpls)
    fc.pft_ids = collect(Int, pft_ids)
    fc.bm_inc_acc = zeros(T, length(pools))
    # ADR 0110: the stress accumulators are per-individual and MUST be reallocated with the roster,
    # never `fill!`ed — a stale length makes the daily `water_stress_acc[i] +=` read out of bounds.
    fc.water_stress_acc = zeros(T, length(pools))
    fc.temp_stress_acc = zeros(T, length(pools))
    fc.aphen_acc = zeros(T, length(pools))
    fpars = FDiff._patch_fpars(pools, fc.allom)
    (fc.inds, fc.rootdists) = FDiff.individuals_from_pools(
        fc.tmpls, pools, fc.allom, fpars, fc.soil; per_tree = fc.params.water.per_tree_roots,
    )   # ADR 0110
    fc.gpp_acc = fc.npp_acc = fc.et_acc = fc.wscal_acc = zero(T)
    fc.nday = 0
    fc.doy = 0
    fc.water_avail = one(T)
    fc.pft_states = FDiff.PhenState{T}[FDiff.PhenState{T}() for _ in eachindex(fc.pft_states)]
    fc.grass_lf = one(T)
    s.age = ages
    counters === nothing || (s.bm_inc_counter = counters)
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

`feature_history` records the exact `flux_feature_vector` row handed to the forest each year (15 `Float64`s
per year, diagnostic only — it never feeds the dynamics). It exists so RUNTIME-CONSISTENCY (ADR 0023) is
*observable*: a DRF prediction is a convex combination of training leaf means, so it can never leave the
trained target band no matter how out-of-domain its input is, and a target-band assertion therefore cannot
detect a conditioning-basis mismatch. Comparing these rows against the `feat_min`/`feat_max` band in the
artifact meta can (ADR 0032 / milestone S1c).
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
    feature_history::Vector{Vector{Float64}}
    year::Int
    rng::DRF.Xoshiro256pp
    k_cap::Int
    recruit_copula::Union{Nothing, RecruitCopula{T}}
    boundary_series::Union{Nothing, Vector{Vector{Float64}}}
    # ── trait-dependent mortality (ADR 0049); `false`/empty ⇒ pre-0049 behaviour byte-for-byte ──
    trait_mortality::Bool
    bm_inc_counter::Vector{Int}
    mort_diag::Vector{TraitMortDiag}
    # ── LEVEL ANCHOR (ADR 0103); `anchor = 0` ⇒ pre-0103 behaviour byte-for-byte ──
    anchor::T
    patch_area::T
    # ── PORTED FIT ESTABLISHMENT (ADR 0119); `nothing` ⇒ pre-0119 behaviour byte-for-byte ──
    recruit_establishment::Union{Nothing, RecruitEstablishment{T}}
end

"""
    FluxDrivenSlowEmulator(fc::FDiffFastCore{T}, forest::DRF.Forest; boundary=Float64[],
                           max_mort=0.3, max_estab=0.3, n_init=1.0, sapl=nothing, seed=1,
                           age0=0, k_cap=nothing, recruit_copula=nothing, trait_mortality=false)

Construct the Tier-1 flux-driven slow emulator for a fast core: the K cohorts are `fc.pools`;
`recruit_idx` is the shortest living TREE cohort; `sapl` defaults to a small beech sapling (as Tier-0);
`boundary` is the baked per-cell slow bioclimatic feature tail appended to the flux/state/AR features (its
length + 11 must equal `forest.nfeat`); `n_init` seeds the count-space AR state (year 0 forces the
demographic-change ratio to 1, so `n_init` only sets the year-0 feature and is self-corrected by the
`max_*` clamp thereafter). `age0` (a scalar stand age or a per-cohort vector) seeds `s.age` so the runtime
`age_mean` feature starts inside the DRF's trained age band (ADR 0024 §3 — a scalar 0, the default,
reproduces the pre-0024 zero-init; the coupled app reads `age0` from the DRF meta). `k_cap` bounds the
cohort roster (default `max(2·K, 40)`); `recruit_copula` (default `nothing`) opts establishment into
copula-sampled recruit traits.

`boundary_series` (default `nothing`; ADR 0026) opts into a **TRANSIENT** time-varying boundary: a per-year
`Vector` of boundary rows (each the same length as `boundary`) that `reconcile_demography!` advances into
`s.boundary` by simulation year (`s.year`, 1-based into the series, clamped so post-series years reuse the
last row) BEFORE building the feature row — so both the count-DRF features and the copula's `live_flux_cond`
conditioning track the year's bioclimate (a warming cell's establishment gate shifts instead of freezing at
the climatological mean; refines ADR 0020's time-constant boundary). Default `nothing` leaves `s.boundary`
constant every year ⇒ byte-identical to the pre-0026 static boundary. If `boundary` is empty and a
`boundary_series` is given, `boundary` is seeded from its first row. Deterministic given `seed`.

`trait_mortality` (default `false`; ADR 0049) opts the **ρ-thinning** into the ported FIT per-individual
hazard: instead of scaling every tree cohort's `nind` by one composition-preserving factor, each cohort's
share of the year's deaths is set by its OWN `TraitMortality.mortality_hazard` (wood density, growth
efficiency, age), tilted to land exactly on the DRF's count target. `false` leaves every code path,
committed baseline and AD gate byte-identical — the hazard is not even evaluated. Requires real
`fc.pft_ids` (`TraitMortality.pft_mort_params` errors rather than defaulting to beech). Read
[`_trait_hazards!`](@ref) for what is and is NOT fed to the hazard before scoring an arm with it.

`anchor` (default `0`; ADR 0103) opts the demographic update into a **LEVEL ANCHOR**. With `anchor = 0` the
stand is advanced by the pure AR ratio `target/n_prev`, so it evolves as `D_T = D_0·Πρ_t` and the DRF's
*absolute* count skill never reaches it: measured at Hainich, a 4× perturbation of the initial density is
still **4.21× after 300 identical-forcing years** (retention 1.036, a non-zero asymptote — no restoring
force), and the stand settles **1.41× denser** than its own count model's target. `anchor > 0` geometrically
blends in the ratio that would place the stand on the DRF's absolute target,
`ρ_eff = (target/n_prev)^(1−a)·(D_want/D)^a` with `D_want = target/patch_area`, giving exponential relaxation
toward the target with a time constant of roughly `1/anchor` years (`anchor = 1` places it outright). `0`
leaves every code path, committed baseline and AD gate byte-identical — the branch is not evaluated.

`recruit_establishment` (default `nothing`; ADR 0119) opts the recruit trait draw into the **ported FIT
establishment rule** instead of a learned marginal — uniform draws on each PFT's own parameter-file
intervals mixed with inheritance from the emulator's own rolling top-AGB seedbank at the closed-form
weight `4/(4 + n_elig)`. It is **mutually exclusive with `recruit_copula`** (both set the same marginal,
from bases that differ by a measured +12.18 % on `Wooddens`; the constructor errors rather than pick).
`nothing` leaves every code path, committed baseline and AD gate byte-identical — the rule is not even
evaluated. See [`RecruitEstablishment`](@ref) for the fields and what must be read before interpreting an
arm run with it.

`patch_area` (default `225.0` m²) is the count↔density conversion: the count DRF is trained on stems **per
patch** while the roster carries stems **per m²**. 225 m² (15×15) is `param.patcharea` in
`par/lpjparam_fit.js`, the value the training runs used, and `new_tree.c:209` gives every individual
`nind = 1/patcharea`. **It is a property of the artifact's training run** — if a future artifact is built
from a run with a different `patcharea`, pass it here, or the anchor will pull the stand to the wrong level.
It is unused when `anchor == 0` **and** `recruit_establishment === nothing`. ⚠ ADR 0119 gave it a second
consumer: the ported establishment rule needs each cohort's INDIVIDUAL COUNT to rank the seedbank and to
weight inheritance, and that is `nind·patch_area`. So with the ported rule on, a wrong `patch_area` scales
the seedbank's admitted weight (its yearly width `n_top` is set independently, from `param.n_max`), and it
is no longer a field only the anchor reads.
"""
function FluxDrivenSlowEmulator(
        fc::FDiffFastCore{T}, forest::DRF.Forest; boundary::AbstractVector{<:Real} = Float64[],
        max_mort = T(0.3), max_estab = T(0.3), n_init = one(T),
        sapl::Union{Nothing, FDiff.TreePools{T}} = nothing, seed::Integer = 1,
        age0::Union{Real, AbstractVector} = 0, k_cap::Union{Nothing, Integer} = nothing,
        recruit_copula::Union{Nothing, RecruitCopula{T}} = nothing,
        boundary_series::Union{Nothing, AbstractVector} = nothing,
        trait_mortality::Bool = false, anchor = zero(T), patch_area = T(225.0),
        recruit_establishment::Union{Nothing, RecruitEstablishment{T}} = nothing,
    ) where {T <: AbstractFloat}
    zero(T) <= anchor <= one(T) || error("anchor must be in [0, 1] (got $anchor)")
    # The two recruit samplers answer the SAME question from opposite bases (learned-from-survivors vs
    # ported-from-parameters), so holding both would make the arm's recruit marginal depend on an
    # undocumented precedence rule. Refuse instead — this is the ADR-0023 shift class, and it is silent.
    (recruit_copula !== nothing && recruit_establishment !== nothing) && error(
        "recruit_copula and recruit_establishment are mutually exclusive: both set the recruit trait " *
            "marginal, from bases that differ by a measured +12.18 % on Wooddens (ADR 0118 §2). Pick one."
    )
    # With `set_pft_id = true` the drawn id reaches `fc.pft_ids`, and `_commit_membership!` refuses an id
    # absent from `fc.pft_slot` (built once, at `FDiffFastCore` construction). Check a FIXED eligible set
    # here so the run fails at construction rather than in whichever later year the background channel
    # first happens to draw the missing id (ADR 0119; the same class of never-reached-path hazard the
    # copula width probe exists for).
    let re0 = recruit_establishment
        if re0 !== nothing && re0.set_pft_id && !(re0.eligible isa Function)
            missing_ids = [id for id in collect(Int, re0.eligible) if !haskey(fc.pft_slot, id)]
            isempty(missing_ids) || error(
                "recruit_establishment has set_pft_id = true with eligible ids $(missing_ids) absent " *
                    "from the fast core's per-PFT registry (fc.pft_slot has " *
                    "$(sort(collect(keys(fc.pft_slot))))). A recruit carrying one of those would be " *
                    "rejected by _commit_membership!. Either restrict `eligible` to the roster's own " *
                    "ids, or leave set_pft_id = false (the drawn id is still recorded in the diagnostics)."
            )
        end
    end
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
    # TRANSIENT boundary (ADR 0026): normalise the opt-in per-year series to `Vector{Vector{Float64}}`; seed
    # the year-0 `boundary` from its first row if `boundary` was omitted; every row must match `boundary`'s
    # length (the `+11 == forest.nfeat` tail invariant is checked once, on `bnd`, downstream by the readers).
    # `bnd`/`bser` are SINGLE-ASSIGNMENT (never reassigned) so the `all(... for r in bser)` generator closure
    # does not box them — JET 0.11.6's boxed-capture trap (CLAUDE.md §2).
    bser = boundary_series === nothing ? nothing : [collect(Float64, row) for row in boundary_series]
    (bser !== nothing && isempty(bser)) && error("boundary_series must be non-empty when provided")
    bnd0 = collect(Float64, boundary)
    bnd = (bser !== nothing && isempty(bnd0)) ? copy(bser[1]) : bnd0
    if bser !== nothing
        all(length(r) == length(bnd) for r in bser) ||
            error("every boundary_series row must have length $(length(bnd)) (== length(boundary))")
    end
    # CONDITIONING-WIDTH PROBE (ADR 0038). `DRF._check_nfeat` is the real guard, but for the copula it only
    # fires inside `sample_copula!` — reached only when a patch actually RECRUITS (`ρ > 1 && recruit_idx > 0`
    # and `dn > 0`). A cell that thins every year, or an all-grass patch, never draws, so a coupled run with
    # a mis-wired copula can complete "successfully" and conserve carbon with zero diagnostics. That is the
    # ADR-0023 shift hiding behind a code path a test may never reach.
    # This is the one place that holds BOTH the boundary and the copula, so it is the only place the identity
    # `length(cond(s, feats)) == nfeat` can be checked before the run starts. Every shipped policy reads only
    # `s.boundary`, `s.year` (the ADR-0108 transient tail) and `feats[1:4]`, so a NamedTuple stub carrying
    # those two fields is a faithful probe — `year = 0` is the state a freshly constructed emulator is in, so
    # a series policy is probed at exactly its first row. One call, no effect on any correctly-sized
    # construction ⇒ guardrail 4 holds.
    rc = recruit_copula
    if rc !== nothing && !isempty(rc.axis_forests)
        nfeat = rc.axis_forests[1].nfeat
        probe = rc.cond((boundary = bnd, year = 0), zeros(Float64, 11 + length(bnd)))
        length(probe) == nfeat || error(
            "recruit copula conditioning width mismatch: the policy built $(length(probe)) columns but the " *
                "artifact's marginals were fit on $nfeat. With a $(length(bnd))-column boundary, " *
                "`live_flux_cond` yields $(4 + length(bnd)); a wider artifact needs " *
                "`live_flux_cond_env(env)` with length(env) == $(nfeat - 4 - length(bnd)). " *
                "See the artifact's `cond_cols` — it is the contract (ADR 0023/0038)."
        )
    end
    return FluxDrivenSlowEmulator{T}(
        forest, bnd, convert(T, n_init), T(max_mort), T(max_estab),
        sap, ridx, CarbonLedger{T}(), age_init, zero(T), T[], T[], T[], Vector{Float64}[], 0,
        DRF.Xoshiro256pp(seed), kcap, recruit_copula, bser,
        trait_mortality, zeros(Int, length(fc.pools)), TraitMortDiag[],
        T(anchor), T(patch_area), recruit_establishment,
    )
end

"""
    flux_feature_vector(s::FluxDrivenSlowEmulator, grow, pools, state, allom, soil) -> Vector{Float64}

Assemble the DRF feature row (fixed order): the four `FToS`-consistent flux drivers (bm_inc, growth_eff,
water_stress, soilmoist), the six this-year patch-state aggregates from the grown tree pools (fpc-weighted
mean height, max height, stand AGB, stand LAI, capped FPC, mean cohort age), the recursive AR state
`n_prev`, then the baked slow-boundary tail. The training table must use this SAME order (ADR 0020 §6:
S is conditioned at runtime on the channel it was trained on).

`soil` is the fast core's `FDiff.SoilColumn`; only its `whcs` is read, by
[`root_zone_soilmoist`](@ref) (ADR 0035 — the root-zone, `whcs`-weighted basis that the training column
is derived on). It became a parameter in ADR 0035: the pre-0035 `soilmoist` was an unweighted mean over
all 23 layers and needed no soil geometry.

Everything here is a YEAR-END STATE except the three annual integrals F delivers in `grow`
(`bm_inc_cell`, `growth_eff`, `water_stress`) — that split is deliberate and is why `soilmoist` is read as
an instantaneous state rather than accumulated over the year (ADR 0035 §4).
"""
function flux_feature_vector(
        s::FluxDrivenSlowEmulator{T}, grow, pools, state, allom, soil
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
    # ADR 0035 — root-zone, whcs-weighted (NOT the pre-0035 unweighted 23-layer mean)
    soilmoist = root_zone_soilmoist(state, soil)
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
    # ADR 0049 — the per-cohort `bm_inc_counter` roster, resized if a previous year's construction predates
    # it (a `nothing`-counter Tier-0/pre-0049 emulator keeps an empty vector and never reaches the operator).
    counters = if s.trait_mortality
        c = copy(s.bm_inc_counter)
        length(c) == length(fc.pools) || (c = zeros(Int, length(fc.pools)))
        c
    else
        Int[]
    end

    # ── TRANSIENT boundary (ADR 0026): if a per-year series is set, advance `s.boundary` to THIS year's row
    #    (1-based index `s.year+1`, clamped so post-series years reuse the last row) BEFORE building `feats`,
    #    so both the count-DRF feature row and the copula's `live_flux_cond` conditioning see the year's
    #    bioclimate. `s.boundary` is a `Vector{Float64}` field; the readers re-vcat it fresh each call, so
    #    the reassignment propagates. Default (no series) leaves it constant ⇒ byte-identical to pre-0026. ──
    bs = s.boundary_series                          # bind first, THEN narrow (a struct-field `!== nothing`
    if bs !== nothing                               # guard doesn't refine a re-read field; the local does)
        s.boundary = bs[clamp(s.year + 1, 1, length(bs))]
    end

    # ── PORTED ESTABLISHMENT (ADR 0119), opt-in: refresh the rolling top-AGB seedbank from THIS patch's
    #    own roster, BEFORE the year's thinning and establishment. That is FIT's order — `getsapling`
    #    runs in `update_annual.c:77`, ahead of `annual_stand` → mortality → `establishmentpft_ind` — so
    #    a recruit drawn below can inherit from a parent that dies later the same year, exactly as in the
    #    C. AGB is the C's `agb_tree_sum` = leaf + sapwood + heartwood per individual (`tree.h:249`);
    #    root and below-ground sapwood are excluded. Nothing here runs when the hook is off. ──
    re = s.recruit_establishment
    if re !== nothing
        ntr = length(pools)
        agb_ind = Vector{T}(undef, ntr)
        wts = Vector{T}(undef, ntr)
        trs = Vector{NTuple{4, T}}(undef, ntr)
        for i in 1:ntr
            p = pools[i]
            agb_ind[i] = p.is_grass ? zero(T) :
                convert(T, p.leaf_c) + convert(T, p.sapwood_c) + convert(T, p.heartwood_c)
            wts[i] = p.is_grass ? zero(T) : convert(T, p.nind) * s.patch_area
            trs[i] = (
                convert(T, p.sla), convert(T, p.wooddens),
                convert(T, p.d95max), convert(T, p.minwscal),
            )
        end
        Establishment.seedbank_update!(re.seedbank, s.year, agb_ind, wts, pft_ids, trs)
    end

    # ── DRF TARGET → demographic-change ratio ρ (unit-free; count↔density cancels) ──
    feats = flux_feature_vector(s, grow, pools, state, fc.allom, fc.soil)
    push!(s.feature_history, feats)                # diagnostic-only record of the row the forest was fed
    target = DRF.predict(s.forest, feats)

    dtree = sum(convert(T, pools[i].nind) for i in eachindex(pools) if !pools[i].is_grass; init = zero(T))

    ρ = if s.year == 0
        one(T)                                     # year 0: no change (seed the recursive AR state)
    else
        r = convert(T, target) / (s.n_prev + T(1.0e-12))
        # ── LEVEL ANCHOR (ADR 0103), opt-in. `anchor == 0` skips this branch entirely ⇒ every committed
        #    baseline byte-identical. WHY IT EXISTS: `r` is a pure RATIO, so the roster evolves as
        #    `D_T = D_0·Πρ_t` and the DRF's ABSOLUTE count skill never reaches the stand — measured, a 4×
        #    perturbation of the initial density is still 4.21× after 300 identical-forcing years
        #    (retention 1.036, converging to a NON-ZERO asymptote). There is no restoring force.
        #    The conversion the ratio formulation was thought to avoid needing is a documented CONSTANT,
        #    not missing data: `par/lpjparam_fit.js` sets `patcharea = 225.0` m² (15×15 m) and
        #    `new_tree.c:209` gives every individual `nind = 1/patcharea`, so the training target (stems
        #    PER PATCH) maps to the roster's density (stems per m²) by an exact ÷`patch_area`.
        #    HOW: a GEOMETRIC blend of the AR ratio and the ratio that would land the stand on the DRF's
        #    absolute target, `ρ_eff = r^(1−a)·(D_want/D)^a`. `a = 0` ⇒ `r` (today); `a = 1` ⇒ the stand is
        #    placed on `D_want` outright; `0 < a < 1` ⇒ exponential relaxation with time constant ≈ 1/a yr.
        #    A geometric (not arithmetic) blend keeps the update multiplicative and strictly positive, so
        #    the carbon routing below is untouched and the clamp still bounds the year's demographic change.
        a = s.anchor
        if a > zero(T) && dtree > zero(T) && s.patch_area > zero(T)
            d_want = convert(T, target) / s.patch_area
            d_want > zero(T) && (r = r^(one(T) - a) * (d_want / dtree)^a)
        end
        clamp(r, one(T) - s.max_mort, one(T) + s.max_estab)
    end

    # ── TRAIT-DEPENDENT MORTALITY (ADR 0049), opt-in. The hazard is evaluated EVERY year the operator is
    #    on — not only in thinning years — because `bm_inc_counter` is a per-individual recursion with no
    #    gaps (`_trait_hazards!`). `haz` is empty and nothing below runs when the flag is off. ──
    haz = s.trait_mortality ? zeros(T, length(pools)) : T[]
    hazard_mean = zero(T)
    hard_kills = 0
    if s.trait_mortality
        hazard_mean, hard_kills = _trait_hazards!(haz, counters, s, fc, grow, pools, pft_ids)
    end
    θ = T(NaN)
    shortfall = zero(T)

    if ρ < one(T)
        if s.trait_mortality
            # ── TRAIT-DEPENDENT MORTALITY: the same total death, redistributed by each cohort's OWN
            #    hazard. `f_i = (1 − mort_i)^θ` with θ from `_hazard_tilt`, so Σ nind lands on the DRF's
            #    target (its 0.9824 OOS count skill is NOT overridden) while WHICH cohorts die is FIT's
            #    physics. Carbon routing is byte-for-byte the uniform branch's — the only difference is
            #    the per-cohort fraction — so the ~1e-12 handoff closure is structurally unchanged. ──
            n_target = ρ * dtree
            θ, shortfall = _hazard_tilt(haz, pools, n_target, dtree)
            for i in eachindex(pools)
                p = pools[i]
                (p.is_grass || p.nind <= 0) && continue
                w = one(T) - haz[i]
                f = w <= zero(T) ? zero(T) : w^θ
                dn = convert(T, p.nind) * (one(T) - f)
                dn <= 0 && continue
                record_litter!(s.ledger, FDiff.vegc_full_ind(p) * dn)
                pools[i] = _with_nind(p, convert(T, p.nind) - dn)
            end
        else
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
        end
    elseif ρ > one(T) && s.recruit_idx > 0
        # ── ESTABLISHMENT: APPEND a real age-0 recruit cohort of (ρ−1)·D density (ADR 0024). The recruit's
        #    per-individual pools are the fixed `sapl`, or a copula draw if the opt-in hook is set. The whole
        #    cohort's veg C is an establishment influx (0 contribution to cveg_start, no growth accounted). ──
        dn = (ρ - one(T)) * dtree
        if dn > 0
            recruit_pft = fc.pft_ids[s.recruit_idx]
            recruit_ind = if re !== nothing
                # ── PORTED FIT ESTABLISHMENT (ADR 0119): the recruit's traits come from the C's own
                #    parameters — uniform on the drawn PFT's intervals, or inherited from the seedbank
                #    refreshed above and diffused by `new_tree.c`'s corridor rule — never from a marginal
                #    learned on FIT's survivors (which is what double-counts selection, ADR 0118 §1). ──
                elig = _estab_eligible(re, s)
                d = Establishment.draw_recruit!(s.rng, re.seedbank, elig)
                push!(
                    re.diag,
                    EstabDiag(
                        s.year, true, d.pft_id, d.inherited, length(elig),
                        Establishment.w_inherit(length(elig)), length(re.seedbank.entries),
                        Float64(Establishment.seedbank_weight(re.seedbank)),
                    ),
                )
                # `set_pft_id` writes the DRAWN id into the roster; the canopy template still comes from
                # the donor cohort either way (see `RecruitEstablishment` — deliberately measured, not on).
                re.set_pft_id && (recruit_pft = d.pft_id)
                _recruit_pools(d.sla, d.wooddens, d.d95max, d.minwscal, s.sapl, fc.allom)::FDiff.TreePools{T}
            elseif s.recruit_copula === nothing
                s.sapl
            else
                rc = s.recruit_copula
                # condition the axis marginals on the LIVE feature row via the copula's policy (ADR 0025):
                # `live_flux_cond` reads climate/flux + boundary; the default static policy returns `rc.x`.
                xcond = rc.cond(s, feats)
                traits = DRF.sample_copula!(s.rng, rc.cop, rc.axis_forests, xcond; qrf = rc.qrf)
                rc.to_pools(traits, s.sapl, fc.allom)::FDiff.TreePools{T}
            end
            recruit = _with_nind(recruit_ind, dn)
            push!(pools, recruit)
            push!(tmpls, fc.tmpls[s.recruit_idx])
            push!(pft_ids, recruit_pft)
            push!(ages, zero(T))
            # a recruit starts with a clean counter (`mortality_tree_ind.c:72` resets it at age 1 anyway)
            s.trait_mortality && push!(counters, 0)
            record_estab!(s.ledger, FDiff.vegc_full_ind(recruit) * dn)
        end
    end

    # ── K-cap MERGE: bound the roster (carbon-neutral; no ledger entry) ──
    kc = s.trait_mortality ? counters : nothing
    _apply_kcap_merge!(pools, ages, tmpls, pft_ids, s.k_cap, fc.allom; counters = kc)

    # ── ATOMIC roster rebuild: replaces every length-K fc field + s.age in lockstep (design risk #5) ──
    _commit_membership!(s, fc, pools, tmpls, pft_ids, ages; counters = kc)

    cveg_end = sum(FDiff.vegc_full_ind(pools[i]) * convert(T, pools[i].nind) for i in eachindex(pools))
    s.last_resid = handoff_carbon_residual(s.ledger; c_veg_delta = cveg_end - cveg_start)
    s.n_prev = convert(T, target)                   # recursive count-space AR update
    s.year += 1
    s.age .+= one(T)
    push!(s.total_n_history, sum(convert(T, p.nind) for p in pools))
    push!(s.resid_history, s.last_resid)
    push!(s.target_history, convert(T, target))
    # ADR 0049 — record BEFORE believing any before/after Δ: a null from an operator that never fired is
    # the exact error ADR 0048 had to correct once already (handoff item F).
    s.trait_mortality && push!(
        s.mort_diag,
        TraitMortDiag(
            s.year, Float64(hazard_mean), Float64(θ), hard_kills, ρ < one(T), Float64(shortfall)
        )
    )

    # ADR 0035 — root-zone, whcs-weighted (NOT the pre-0035 unweighted 23-layer mean)
    soilmoist = root_zone_soilmoist(state, fc.soil)
    return FToS{T}(
        bm_inc = grow.bm_inc_cell, water_stress = grow.water_stress, temp_stress = zero(T),
        growth_eff = grow.growth_eff, soilmoist = convert(T, soilmoist),
    )
end

"The DRF demographic targets predicted per year (count-space) — the recursive AR trajectory."
target_history(s::FluxDrivenSlowEmulator) = s.target_history

"""
    trait_mortality_diag(s::FluxDrivenSlowEmulator) -> Vector{TraitMortDiag}

The per-year trait-mortality diagnostics (ADR 0049) — EMPTY when the operator is off, which is how a probe
proves the operator fired before interpreting a trajectory. See [`TraitMortDiag`](@ref) for the fields and
why `theta` is the number to read first.
"""
trait_mortality_diag(s::FluxDrivenSlowEmulator) = s.mort_diag

"""
    establishment_diag(s::FluxDrivenSlowEmulator) -> Vector{EstabDiag}

The per-year ported-establishment diagnostics (ADR 0119) — EMPTY when the rule is off, and also empty when
it is on but the patch never recruited (`ρ ≤ 1` every year, or an all-grass patch), which is exactly the
case a before/after Δ must not be read through. See [`EstabDiag`](@ref) for the two fields to read first
(`sb_weight` and `inherited`: the inheritance channel cannot fire until the seedbank has filled, and the
two channels have different marginals).
"""
establishment_diag(s::FluxDrivenSlowEmulator) =
    s.recruit_establishment === nothing ? EstabDiag[] : s.recruit_establishment.diag
