# Component S — the PORTED LPJmL-FIT establishment rule (ADR 0119; owner steer 2026-08-11).
#
# WHY THIS EXISTS, in the owner's words: *"which trees are born is — apart from the inheritance
# functionality — randomly drawn from uniform distributions. why should we train on that?? what matters
# and what we have to learn is who survives the environmental filtering."* FIT's establishment is a
# PARAMETER-FILE FACT, not a distribution to be learned, so the emulator can compute it instead of
# fitting it: uniform draws on each PFT's own trait intervals (the background channel) mixed with
# inheritance from the cell's rolling top-AGB seedbank (the majority channel), at a mixture weight that
# is closed-form.
#
# WHAT IT REPLACES, and this is the defect it exists to remove (ADR 0118 §1). The shipped recruit sampler
# (`RecruitCopula`, ADR 0025) learns its marginals from FIT's `ind` output, which contains only stems
# ABOVE 5 m — i.e. SURVIVORS. Its own decision record wrote the expiry condition into the text ("if
# trait-dependent mortality is ever added, this training target must change"), and ADR 0049's operator is
# that change: a survivor-trained recruit marginal already carries the selection the mortality operator
# then adds, double-counting it by a measured +12.18 % on `Wooddens` within a cell-PFT group. The ported
# rule has no such bias by construction, because it never reads FIT's output at all.
#
# THE ONE RISK IT INTRODUCES, and it must be MEASURED, not assumed (ADR 0119 §5). The seedbank is the
# emulator's OWN biggest trees, so the recruit marginal becomes a functional of the emulator's own
# community — the feedback loop ADR 0025 §4 excluded on principle. ADR 0112-0116 measured what this model
# does when it feeds its own state back in: the count recursion's error became CLIMATE-DEPENDENT and
# manufactured ~90 % of the true signal with the wrong sign. That is why this file ships opt-in and
# default-off with a pre-registered flip criterion (ADR 0119 §6), and why the diagnostics below record
# the channel mix and seedbank state every year: an arm that cannot show which channel fired cannot be
# interpreted (the ADR-0048 lesson, repeated in ADR 0049 item 4).
#
# SOURCE OF RECORD FOR EVERY EQUATION (read these before changing a line):
#   * `$LPJROOT/src/lpj/establishmentpft_ind.c:97-140` — the two channels and their Poisson rates.
#   * `$LPJROOT/src/tree/new_tree.c:38-61`   — `draw_new_trait`, the inheritance diffusion.
#   * `$LPJROOT/src/tree/new_tree.c:120-203` — which axes each channel draws, and from whose intervals.
#   * `$LPJROOT/src/lpj/getsapling.c`        — the 50-year rolling top-AGB seedbank.
#   * `$LPJROOT/src/lpj/getmaxagb.c`         — the top-n AGB threshold (descending sort, n-th value).
#   * `$LPJROOT/src/lpj/establish.c:24-34`   — the bioclimatic eligibility gate.
# SOURCE OF RECORD FOR EVERY PARAMETER: the committed
# `test/testitems/references/S_pft_estab_params.csv`, generated from the live C parameter files by
# `scripts/build_estab_params_reference.py`. The literals in `PFT_ESTAB_PARAMS` are gated against that
# CSV row-by-row by `test/testitems/slow_establishment_tests.jl` — two consumers, ONE source (ADR 0031).
#
# ⚠ WHAT THIS PORT IS **NOT**: bit-identical to the C. FIT consumes its own per-cell RAND48 stream and a
# process-global `gasdev` pair cache, neither of which the emulator has or can reproduce, and FIT draws a
# POISSON NUMBER of discrete recruits per year where the emulator appends ONE cohort of a density the
# count model chose. So the claim this port can support is DISTRIBUTIONAL — the recruit trait marginal
# and its PFT composition — never a per-year trajectory match. Say that in any result.

"""
    Establishment

The ported LPJmL-FIT establishment rule (ADR 0119) — where a recruit's traits come from, computed from the
C's own parameters instead of learned from the C's output.

FIT establishes trees through **two channels** every year, and the emulator reproduces both:

  * **background** — for each PFT that passes the bioclimatic gate, `poidev(k_est_inherit_bg·patcharea·
    f_sap)` recruits whose four trait axes are independent **uniform draws on that PFT's own interval**
    (`new_tree.c:196-203`, `getrndinterval` = `low + (high−low)·U`).
  * **inheritance** — `poidev(k_est_inherit·patcharea·f_sap)` recruits, each a **random member of the
    cell's rolling top-AGB seedbank** whose traits are then diffused by
    `new = old·(1 + inherit_corridor·s)`, `s` a ±5-clamped standard normal, with the PFT id inherited
    from the parent ([`draw_new_trait`](@ref LPJmLFITEmulator.Establishment.draw_new_trait)).

Both rates carry the same `f_sap(fpar_leafon_grass, alpha_r)` and both `alpha_r` are 2.0, so the light and
patch-area factors **cancel** and the inherited share of recruits is the closed form
[`w_inherit`](@ref LPJmLFITEmulator.Establishment.w_inherit)` = 4/(4 + n_elig)` (ADR 0045) — ≈44 % where
five PFTs are eligible (Hainich), ≈80 % where one is (Amazon, Sahel). Inheritance is the **majority
channel in a low-diversity cell**, which is why a pure-uniform recruit model is wrong.

Entry points: [`pft_estab_params`](@ref LPJmLFITEmulator.Establishment.pft_estab_params),
[`eligible_pfts`](@ref LPJmLFITEmulator.Establishment.eligible_pfts),
[`Seedbank`](@ref LPJmLFITEmulator.Establishment.Seedbank) +
[`seedbank_update!`](@ref LPJmLFITEmulator.Establishment.seedbank_update!), and
[`draw_recruit!`](@ref LPJmLFITEmulator.Establishment.draw_recruit!) (the whole rule, one recruit).

Everything is pure Base and allocation-light (ADR 0014 keeps the runtime `[deps]` empty). Deterministic
given a `DRF.Xoshiro256pp`.
"""
module Establishment

using ..DRF: Xoshiro256pp, rand01!, norminv

export PFTEstabParams, pft_estab_params, PFT_ESTAB_PARAMS, w_inherit, eligible_pfts,
    Seedbank, SeedbankEntry, seedbank_update!, seedbank_weight, draw_new_trait, rnd_interval,
    draw_recruit!, RecruitDraw

# ── run globals (par/lpjparam_fit.js; gated against S_pft_estab_params.csv) ────────────────────────────
"Inheritance-channel establishment rate `param.k_est_inherit` (indiv m⁻² yr⁻¹ before `f_sap`)."
const K_EST_INHERIT = 0.02
"Background-channel establishment rate `param.k_est_inherit_bg`, applied PER ELIGIBLE PFT."
const K_EST_INHERIT_BG = 0.005
"`param.alpha_r` — the `f_sap` light exponent of BOTH channels (2.0 ⇒ the factor cancels in the mixture)."
const ALPHA_R = 2.0
"`param.patcharea` (m²) — the count↔density conversion, and `nind = 1/patcharea` per individual."
const PATCHAREA = 225.0
"`param.max_age` (yr) — how long a seed stays in the seedbank (`getsapling.c:38`)."
const MAX_AGE = 50
"`param.n_max` — the seedbank width scale; `n = n_max·npatch·patcharea/100` trees enter per year."
const N_MAX = 7

"""
    PFTEstabParams{T}

Per-PFT establishment parameters of one LPJmL-FIT tree PFT: the four recruit trait intervals
(`sla`, `wooddens`, `d95max`, `minwscal`, each `_low`/`_high`), the inheritance diffusion width
`inherit_corridor`, and FIT's bioclimatic establishment gate (`temp_low`/`temp_high` on the 20-year mean
of the year's coldest monthly mean, `gdd5min`, `aprec_min`).

The four axes are the complete recruit-trait interface: ADR 0117 §6 verified `k_root` is a **scalar
0.02** for all seven tree PFTs in this configuration (one distinct value over 206 561 574 tree rows, the
sampled-interval form commented out at every entry), and `emax`/`beta_2` are emitted nowhere, so a
component that supplies these four and leaves the rest to the C is an identity, not an approximation.
"""
struct PFTEstabParams{T <: AbstractFloat}
    pft_id::Int
    sla_low::T
    sla_high::T
    wooddens_low::T
    wooddens_high::T
    d95max_low::T
    d95max_high::T
    minwscal_low::T
    minwscal_high::T
    inherit_corridor::T
    temp_low::T
    temp_high::T
    gdd5min::T
    aprec_min::T
end

# ── the parameter table. LITERALS, gated row-by-row against the committed CSV (see the file header) ────
"""
    PFT_ESTAB_PARAMS

[`PFTEstabParams`](@ref LPJmLFITEmulator.Establishment.PFTEstabParams) for each of LPJmL-FIT's seven tree
PFTs, keyed by the `ind` `Type` id. Gated against `test/testitems/references/S_pft_estab_params.csv` by
`test/testitems/slow_establishment_tests.jl`. Look up through
[`pft_estab_params`](@ref LPJmLFITEmulator.Establishment.pft_estab_params), which errors on a missing id.

Two structural facts here that a pooled recruit marginal cannot represent, and both are load-bearing:
the evergreen and summergreen `sla` intervals **do not overlap** (0.005–0.0187 vs 0.0242–0.0547), and the
three boreal PFTs' establishment gate has `temp_high = 0` — they are eligible only where the 20-year mean
coldest month is below freezing.
"""
const PFT_ESTAB_PARAMS = Dict{Int, PFTEstabParams{Float64}}(
    # id, sla_lo, sla_hi, wd_lo, wd_hi, d95_lo, d95_hi, mws_lo, mws_hi, corridor,
    #     temp_lo, temp_hi, gdd5min, aprec_min
    0 => PFTEstabParams{Float64}(
        0, 0.005, 0.07, 70000.0, 650000.0, 51.0, 1800.0, 0.05, 0.75, 0.1, 2.5, 1000.0, 0.0, 100.0
    ),
    1 => PFTEstabParams{Float64}(
        1, 0.005, 0.0187, 117000.0, 418500.0, 51.0, 1000.0, 0.025, 0.2, 0.1, -30.0, 1000.0, 900.0, 100.0
    ),
    2 => PFTEstabParams{Float64}(
        2, 0.005, 0.0242, 145600.0, 637000.0, 51.0, 1000.0, 0.025, 0.2, 0.1, -15.0, 1000.0, 1200.0, 100.0
    ),
    3 => PFTEstabParams{Float64}(
        3, 0.0242, 0.0547, 147870.0, 637000.0, 51.0, 500.0, 0.1, 0.15, 0.1, -30.0, 1000.0, 1200.0, 100.0
    ),
    4 => PFTEstabParams{Float64}(
        4, 0.005, 0.0187, 117000.0, 418500.0, 51.0, 500.0, 0.05, 0.3, 0.1, -80.0, 0.0, 350.0, 100.0
    ),
    5 => PFTEstabParams{Float64}(
        5, 0.0242, 0.0547, 147870.0, 418500.0, 51.0, 500.0, 0.1, 0.15, 0.1, -80.0, 0.0, 350.0, 100.0
    ),
    6 => PFTEstabParams{Float64}(
        6, 0.005, 0.07, 117000.0, 418500.0, 51.0, 300.0, 0.05, 0.15, 0.1, -80.0, 0.0, 350.0, 100.0
    ),
)

"""
    pft_estab_params(pft_id::Integer) -> PFTEstabParams{Float64}

The establishment parameters of tree PFT `pft_id` (the `ind` `Type` id). **Errors** on an id with no row
— grass (7-9), crops (10-21), anything out of range — for the same reason
`TraitMortality.pft_mort_params` does: the intervals differ so much between PFTs that a silent beech
default is a measurable defect, not a rounding one (id 3's `sla` interval does not even intersect id 1's).
"""
function pft_estab_params(pft_id::Integer)
    p = get(PFT_ESTAB_PARAMS, Int(pft_id), nothing)
    p === nothing && error(
        "Establishment: no establishment parameters for PFT id $pft_id. Tree ids are " *
            "$(sort(collect(keys(PFT_ESTAB_PARAMS)))) (the `ind` `Type` column, ADR 0031); grass ids 7-9 " *
            "carry ZEROED tree fields and crops 10-21 are never emitted in this config. This is NOT a " *
            "defaultable lookup."
    )
    return p
end

"""
    w_inherit(n_elig::Integer) -> Float64

The share of recruits that come from the INHERITANCE channel, `k_est_inherit / (k_est_inherit +
n_elig·k_est_inherit_bg) = 4/(4 + n_elig)` (ADR 0045). `n_elig` is the number of PFTs passing the
bioclimatic gate; `n_elig == 0` ⇒ 1.0 (only the inheritance channel can fire).

This is EXACT, not fitted: both channels' Poisson rates carry the same `f_sap(fpar_leafon_grass, alpha_r)`
and the same `param.patcharea`, and every `alpha_r` in the parameter file is 2.0, so both factors cancel
in the ratio (asserted by `scripts/build_estab_params_reference.py`). ≈0.444 at Hainich (5 eligible),
0.8 in a single-PFT cell — inheritance is the **majority** channel in a low-diversity cell.
"""
function w_inherit(n_elig::Integer)
    n = Int(n_elig)
    n <= 0 && return 1.0
    return K_EST_INHERIT / (K_EST_INHERIT + n * K_EST_INHERIT_BG)
end

"""
    eligible_pfts(temp_min20, temp_max20, gdd5; aprec = Inf, ids = 0:6) -> Vector{Int}

The PFT ids that pass FIT's bioclimatic establishment gate, ported from `establish.c:29-33` +
`establishmentpft_ind.c:88`:

```
temp_min20 ∈ [temp_low, temp_high]  AND  gdd5 ≥ gdd5min  AND  temp_max20 > 10  AND  aprec ≥ aprec_min
```

`temp_min20` / `temp_max20` are 20-year running means of the year's **coldest / warmest monthly mean**
(`climbuf.c:134-137` accumulates them from monthly means, `:153-154` pushes them into the 20-slot buffer)
— i.e. exactly what [`ClimBuf`](@ref)'s trailing monthly window can produce. The `temp_max20 > 10` term
is the tree-only clause `!(type == TREE && temp_max20 <= 10)`; every id here is a tree.

⚠ TWO STATED APPROXIMATIONS, both because the C reads state the emulator does not carry:
  * FIT tests `cell->gdd[p]`, the CURRENT year's daily accumulation above `gddbase` (5 °C for every tree
    PFT, so it is a GDD5), while the emulator's `gdd5` comes from the trailing-window MONTHLY climatology
    (Thom-1966, `climbuf_gdd5_tcm`). Same quantity, smoother basis.
  * `aprec` defaults to `Inf` (the 100 mm minimum treated as satisfied). Pass the cell's annual
    precipitation to close it. Only cells drier than 100 mm/yr are affected, and they carry no trees.
"""
function eligible_pfts(
        temp_min20::Real, temp_max20::Real, gdd5::Real; aprec::Real = Inf, ids = 0:6
    )
    out = Int[]
    temp_max20 > 10 || return out                      # the tree clause: no tree establishes at all
    for id in ids
        p = pft_estab_params(id)
        temp_min20 >= p.temp_low || continue
        temp_min20 <= p.temp_high || continue
        gdd5 >= p.gdd5min || continue
        aprec >= p.aprec_min || continue
        push!(out, Int(id))
    end
    return out
end

# ── the two draw primitives ───────────────────────────────────────────────────────────────────────────

"""
    rnd_interval(rng, low, high) -> Float64

FIT's `getrndinterval` (`include/numeric.h:59`): `low + (high − low)·U`, one uniform per call. This is the
BACKGROUND channel's draw on every axis — the "everything is everywhere" recruit.
"""
@inline rnd_interval(rng::Xoshiro256pp, low::Real, high::Real) =
    Float64(low) + (Float64(high) - Float64(low)) * rand01!(rng)

"""
    draw_new_trait(rng, old, low, high, corridor) -> Float64

FIT's inheritance diffusion, `new_tree.c:38-61`, ported exactly:

```
s = clamp(gasdev, −5, +5)
low == high            ⇒ return old                    # no interval given
new = old·(1 + corridor·s)
new < low              ⇒ new = low + (old − low)·U     # redraw UNIFORMLY between the bound and the parent
new > high             ⇒ new = old + (high − old)·U
```

⚠ **The boundary rule is NOT a reflection** (an earlier summary in this repo called it one). A violating
draw is replaced by a uniform draw on the interval **between the parent and the bound it crossed**, which
is a strictly INWARD move: it can never leave `[low, high]`, and it biases the offspring toward the parent
rather than mirroring the overshoot. Getting this wrong changes the stationary shape of the inherited
marginal near an interval edge — which is precisely where the boreal `minwscal` and `d95max` intervals
live (id 6: `[0.05, 0.15]`, `[51, 300]`).

`corridor` is the per-PFT `inherit_corridor` (0.1 for all seven). The normal is drawn as
`norminv(rand01!(rng))`, one uniform per call — distributionally the C's `gasdev` but NOT its stream (the
C's has a process-global pair cache; see the file header on why this port is distributional).
"""
function draw_new_trait(rng::Xoshiro256pp, old::Real, low::Real, high::Real, corridor::Real)
    lo = Float64(low)
    hi = Float64(high)
    o = Float64(old)
    s = clamp(norminv(rand01!(rng)), -5.0, 5.0)
    lo == hi && return o
    new = o * (1.0 + Float64(corridor) * s)
    if new < lo
        new = lo + (o - lo) * rand01!(rng)
    elseif new > hi
        new = o + (hi - o) * rand01!(rng)
    end
    return new
end

# ── the seedbank ──────────────────────────────────────────────────────────────────────────────────────

"""
    SeedbankEntry{T}

One seed in the rolling seedbank: the parent's PFT id, the `year` it was added, the number of individuals
it stands for (`weight`), and the parent's four trait values. FIT stores one entry per qualifying
individual per year; the emulator's roster is COHORTS, so one entry carries a cohort's individual count
and inheritance samples entries **in proportion to `weight`** — the same uniform-over-individual-years
draw FIT makes with `erand48(seed)·treelen`.

A trait may be `NaN`, meaning **the parent carried no value on that axis** — the emulator's `TreePools`
uses 0 as the UNSET sentinel for `d95max`/`minwscal` (ADR 0110), and every roster reconstructed from the
`ind` output before that ADR has them unset.
[`draw_recruit!`](@ref LPJmLFITEmulator.Establishment.draw_recruit!) then draws that ONE axis from the
uniform background channel instead of diffusing a value that does not exist. Finite values are clamped
into the parent PFT's interval on insertion, because
[`draw_new_trait`](@ref LPJmLFITEmulator.Establishment.draw_new_trait)'s inward-redraw rule keeps a child
inside `[low, high]` only if the PARENT is inside it — an invariant FIT gets for free (every parent was
itself drawn on that interval) and the emulator does not.
"""
struct SeedbankEntry{T <: AbstractFloat}
    pft_id::Int
    year::Int
    weight::T
    sla::T
    wooddens::T
    d95max::T
    minwscal::T
end

"""
    Seedbank{T}(; max_age = MAX_AGE, n_top = 15)

The rolling top-AGB seedbank inheritance draws from, ported from `getsapling.c`.

Each year, seeds `max_age` years old or older are dropped, then the cell's largest trees by above-ground
biomass are appended — `n_top` individuals' worth, where FIT uses
`n = n_max·npatch·patcharea/100` with C integer truncation (7·1·225/100 → **15** for a single patch,
393 for its 25-patch ensemble). It is an accumulation of individual-YEARS, **not a set of distinct
trees**: a tree that stays dominant for 30 years contributes 30 draws, so the seedbank is weighted toward
persistently dominant genotypes. That is FIT's behaviour, not an artefact — `getsapling.c` appends
unconditionally every year with no de-duplication.

Two stated departures from the C, both because the emulator's roster is not FIT's:
  * FIT ranks INDIVIDUALS; the emulator ranks COHORTS by per-individual AGB and admits whole cohorts
    until `n_top` individuals are accounted for, capping the crossing cohort's weight at the remainder —
    so the yearly weight admitted equals FIT's count exactly, while the trait resolution is the roster's.
  * FIT calls `getsapling` BEFORE the year's turnover/allocation/mortality; the emulator updates it from
    the already-grown pools of the same year. Traits are immutable after establishment, so this can only
    change WHICH trees rank top, never what a given tree contributes.
"""
mutable struct Seedbank{T <: AbstractFloat}
    entries::Vector{SeedbankEntry{T}}
    max_age::Int
    n_top::Int
end
function Seedbank{T}(; max_age::Integer = MAX_AGE, n_top::Integer = default_n_top()) where {T <: AbstractFloat}
    return Seedbank{T}(SeedbankEntry{T}[], Int(max_age), Int(n_top))
end
Seedbank(; kwargs...) = Seedbank{Float64}(; kwargs...)

"""
    default_n_top(npatch = 1, patch_area = PATCHAREA) -> Int

FIT's yearly seedbank width, `trunc(n_max·npatch·patcharea/100)` (`getsapling.c:65` passes this as the
`int n` of `getmaxagb`, so the C truncates). 15 for one 225 m² patch; 393 for the 25-patch ensemble the
ground truth runs.
"""
default_n_top(npatch::Integer = 1, patch_area::Real = PATCHAREA) =
    max(1, Int(trunc(N_MAX * Int(npatch) * Float64(patch_area) / 100.0)))

"Total individual-year weight currently in the seedbank (FIT's `treelen`, in individuals)."
seedbank_weight(sb::Seedbank{T}) where {T} = sum(e.weight for e in sb.entries; init = zero(T))

"""
    _seed_trait(T, v, low, high) -> T

Sanitise one parent trait on insertion: a non-finite or non-positive value (the `TreePools` UNSET
sentinel 0) becomes `NaN` — "this parent has no value on this axis" — and a finite value is clamped into
the parent PFT's interval so [`draw_new_trait`](@ref
LPJmLFITEmulator.Establishment.draw_new_trait)'s inward redraw keeps the child in range.

⚠ The clamp is a GUARD, not physics: in FIT every parent was itself drawn on this interval, so it can
never fire. Here it can — a roster reconstructed from the `ind` output carries `d95max`/`minwscal` unset,
and F_diff's growth does not constrain a trait at all. If it fires on `sla`/`wooddens` in a real arm,
something upstream has put a tree outside its own PFT's parameter range; that is worth investigating
rather than absorbing.
"""
@inline function _seed_trait(::Type{T}, v, low, high) where {T <: AbstractFloat}
    x = Float64(v)
    (isfinite(x) && x > 0) || return T(NaN)
    return convert(T, clamp(x, Float64(low), Float64(high)))
end

"""
    seedbank_update!(sb, year, agb_ind, weights, pft_ids, traits) -> Int

Advance the seedbank by one year and return the number of entries appended.

`agb_ind[i]` is cohort `i`'s **per-individual** above-ground biomass — `leaf_c + sapwood_c +
heartwood_c` (`include/tree.h:249` `agb_tree_sum`; root and below-ground sapwood are excluded, and the
`debt`/`excess_carbon`/`turn_litt` corrections of `agb_tree` have no emulator counterpart).
`weights[i]` is the cohort's individual count (`nind·patch_area`), `pft_ids[i]` its PFT id, and
`traits[i]` its `(sla, wooddens, d95max, minwscal)`. Cohorts with `weights[i] ≤ 0`, a non-tree id, or a
non-finite AGB are skipped.

Ranking is by per-individual AGB **descending**, admitting whole cohorts until `sb.n_top` individuals are
accounted for and capping the crossing cohort at the remainder — see [`Seedbank`](@ref
LPJmLFITEmulator.Establishment.Seedbank) for why that matches FIT's count and where it does not match its
resolution. Pruning happens FIRST (`getsapling.c:36-48`: `year − entry.year ≥ max_age` is dropped), so a
seedbank whose parents all died out empties on its own after `max_age` years.
"""
function seedbank_update!(
        sb::Seedbank{T}, year::Integer, agb_ind::AbstractVector, weights::AbstractVector,
        pft_ids::AbstractVector, traits::AbstractVector,
    ) where {T <: AbstractFloat}
    y = Int(year)
    # prune: seeds at least `max_age` years old (getsapling.c:38 uses `>=`)
    filter!(e -> (y - e.year) < sb.max_age, sb.entries)
    n = length(agb_ind)
    (n == length(weights) == length(pft_ids) == length(traits)) || error(
        "seedbank_update!: agb_ind/weights/pft_ids/traits must have equal length " *
            "(got $(n), $(length(weights)), $(length(pft_ids)), $(length(traits)))"
    )
    # eligible cohorts, ranked by per-individual AGB descending (getmaxagb.c's `compare` + threshold)
    idx = Int[]
    for i in 1:n
        w = Float64(weights[i])
        a = Float64(agb_ind[i])
        (w > 0 && isfinite(a) && a > 0 && haskey(PFT_ESTAB_PARAMS, Int(pft_ids[i]))) || continue
        push!(idx, i)
    end
    isempty(idx) && return 0
    sort!(idx; by = i -> -Float64(agb_ind[i]))
    remaining = T(sb.n_top)
    added = 0
    for i in idx
        remaining > zero(T) || break
        w = min(convert(T, weights[i]), remaining)
        w > zero(T) || continue
        tr = traits[i]
        p = pft_estab_params(Int(pft_ids[i]))
        push!(
            sb.entries,
            SeedbankEntry{T}(
                Int(pft_ids[i]), y, w,
                _seed_trait(T, tr[1], p.sla_low, p.sla_high),
                _seed_trait(T, tr[2], p.wooddens_low, p.wooddens_high),
                _seed_trait(T, tr[3], p.d95max_low, p.d95max_high),
                _seed_trait(T, tr[4], p.minwscal_low, p.minwscal_high),
            ),
        )
        remaining -= w
        added += 1
    end
    return added
end

# ── the rule ──────────────────────────────────────────────────────────────────────────────────────────

"""
    RecruitDraw

One drawn recruit: its `pft_id`, the four trait values, and `inherited` — `true` if it came from the
seedbank, `false` if from the uniform background channel. `inherited` is the diagnostic that makes an arm
interpretable: the two channels have different marginals, and the mixture weight is a function of the
cell's eligible-PFT count, so a result quoted without the realised channel mix cannot be read (ADR 0119
§6 pre-registers it as a reported quantity).
"""
struct RecruitDraw{T <: AbstractFloat}
    pft_id::Int
    sla::T
    wooddens::T
    d95max::T
    minwscal::T
    inherited::Bool
end

"""
    draw_recruit!(rng, sb::Seedbank{T}, eligible::AbstractVector{<:Integer}) -> RecruitDraw{T}

Draw ONE recruit by FIT's establishment rule: with probability
[`w_inherit`](@ref LPJmLFITEmulator.Establishment.w_inherit)`(length(eligible))` from the **inheritance**
channel (a seedbank entry chosen uniformly over individual-years, each axis then diffused by
[`draw_new_trait`](@ref LPJmLFITEmulator.Establishment.draw_new_trait) on the PARENT's intervals), else
from the **background** channel (a uniformly chosen eligible PFT, each axis
[`rnd_interval`](@ref LPJmLFITEmulator.Establishment.rnd_interval) on ITS intervals).

An empty seedbank forces the background channel (`establishmentpft_ind.c:122` requires
`cell->treelen > 0`); an empty `eligible` set forces inheritance; both empty is an error, because a patch
that can establish nothing should not have been asked for a recruit.

⚠ The Bernoulli-on-`w_inherit` mapping is where the port meets the emulator's architecture: FIT draws a
Poisson COUNT from each channel and the emulator appends ONE cohort per year, so this reproduces the
recruit population's channel MIX in expectation, not the year's joint counts. It is exact for the
marginal composition and it is the quantity ADR 0119's criterion is written on.
"""
function draw_recruit!(
        rng::Xoshiro256pp, sb::Seedbank{T}, eligible::AbstractVector{<:Integer}
    ) where {T <: AbstractFloat}
    n_elig = length(eligible)
    tot = seedbank_weight(sb)
    (n_elig == 0 && tot <= zero(T)) && error(
        "draw_recruit!: no eligible PFT and an empty seedbank — nothing can establish here. Do not " *
            "call the ported establishment rule for a patch whose bioclimatic gate admits no tree."
    )
    inherit = if tot <= zero(T)
        false
    elseif n_elig == 0
        true
    else
        rand01!(rng) < w_inherit(n_elig)
    end
    if inherit
        # uniform over individual-YEARS (FIT: `erand48(seed)*treelen` over a list of individual entries)
        u = rand01!(rng) * Float64(tot)
        acc = 0.0
        e = sb.entries[end]
        for cand in sb.entries
            acc += Float64(cand.weight)
            if u < acc
                e = cand
                break
            end
        end
        p = pft_estab_params(e.pft_id)
        c = p.inherit_corridor
        # A `NaN` parent axis means the parent carried no value there (the `TreePools` UNSET sentinel; see
        # `SeedbankEntry`) ⇒ that ONE axis falls back to the uniform interval draw. Diffusing a
        # non-existent parent value would put the child outside its own PFT's interval, because
        # `draw_new_trait`'s inward redraw is only inward relative to the parent.
        inh(v, lo, hi) = isnan(Float64(v)) ? rnd_interval(rng, lo, hi) : draw_new_trait(rng, v, lo, hi, c)
        return RecruitDraw{T}(
            e.pft_id,
            convert(T, inh(e.sla, p.sla_low, p.sla_high)),
            convert(T, inh(e.wooddens, p.wooddens_low, p.wooddens_high)),
            convert(T, inh(e.d95max, p.d95max_low, p.d95max_high)),
            convert(T, inh(e.minwscal, p.minwscal_low, p.minwscal_high)),
            true,
        )
    end
    id = Int(eligible[min(n_elig, 1 + Int(floor(rand01!(rng) * n_elig)))])
    p = pft_estab_params(id)
    return RecruitDraw{T}(
        id,
        convert(T, rnd_interval(rng, p.sla_low, p.sla_high)),
        convert(T, rnd_interval(rng, p.wooddens_low, p.wooddens_high)),
        convert(T, rnd_interval(rng, p.d95max_low, p.d95max_high)),
        convert(T, rnd_interval(rng, p.minwscal_low, p.minwscal_high)),
        false,
    )
end

end # module Establishment
