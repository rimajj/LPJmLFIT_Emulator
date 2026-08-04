# Component S — the PORTED LPJmL-FIT individual tree mortality hazard (ADR 0047, Phase 3A Stage 1).
#
# WHY THIS EXISTS. ADR 0046 decomposed FIT's per-cell wood-density warming shift and found it is
# **51.3 % WITHIN-PFT, +112 % WITHIN-AGE-CLASS** selection: traits are immutable after `new_tree`, so a
# trait-mean rise at fixed age can only be differential survival, and the selection intensity itself
# responds to warming. The emulator has **zero** channel for that — `reconcile_demography!` scales every
# cohort's `nind` by ONE factor ρ, which is composition-preserving to floating point. This file is the
# mechanism that closes the gap: the faithful per-individual hazard, so a cohort's survival can depend on
# its OWN `wooddens`/`sla`/age instead of on the community mean.
#
# THIS FILE HAS NO CALL SITE (deliberate — guardrail 4, opt-in / default byte-identical). Nothing in
# `slow.jl`, `run.jl` or the coupled loop reaches it, so every committed baseline and the AD trainer are
# unchanged by its presence. Wiring it in is Stage 2, gated on the ADR-0046 §3 age–wooddens gradient.
#
# ⚠ THE TRAP THIS PORT EXISTS TO AVOID (ADR 0046 §3). "Denser wood survives better" is WRONG as a
# shortcut. Denser wood halves `mort_max` (ratio 1.765 over `wooddens` 2e5→3e5) but also grows more
# slowly, lowering `greff` and so RAISING `mort_npp` through the logistic. Net selection is a competition
# between the two and is **not sign-definite** — FIT's one-year differential
# `mean(Wooddens|live) − mean(Wooddens|all)` is NEGATIVE for PFT ids 0 and 3 and positive for 1/2/4/6, and
# its sign is what predicts each PFT's gradient SHAPE. So the whole hazard is ported, never one factor.
#
# Source of record for every equation: `$LPJROOT/src/tree/mortality_tree_ind.c` (line numbers cited per
# function), plus `waterstress_tree.c` / `tempstress_tree.c` for how the two stress integrals are
# accumulated. Source of record for every PARAMETER: the committed
# `test/testitems/references/S_pft_mortality_params.csv`, generated from the live C parameter files by
# `scripts/build_mort_params_reference.py`. The literals in [`PFT_MORT_PARAMS`] below are GATED against
# that CSV row-by-row by `test/testitems/slow_trait_mortality_tests.jl`, and
# `scripts/build_slow_flux_table.py::PFT_PARAMS` gates against the same file — three consumers, ONE
# source, no third copy (ADR 0031 is the record of what two independent copies cost).

"""
    TraitMortality

The ported LPJmL-FIT per-individual tree mortality hazard (ADR 0047) — the trait-dependent selection
operator Component S needs to reproduce FIT's within-PFT wood-density warming shift (ADR 0046).

FIT kills an individual by drawing `erand48 < mort` once per year, where the four hazards combine
**ADDITIVELY** and are then capped (`mortality_tree_ind.c:122-124`):

```
mort = min(1, mort_npp + mort_age + mort_water + mort_temp)
```

with two hard kills applied afterwards (`:128-133`) — a five-year run of negative biomass increment, and
an individual whose leaf carbon has fallen below a sapling's. Entry points (no `@ref` links: like `DRF`,
this submodule is not in the `@autodocs` set, so its members are documented in the source and via
`?LPJmLFITEmulator.TraitMortality.mortality_hazard` in the REPL): `mortality_hazard` (the whole thing,
decomposed), the four component functions `mort_npp`/`mort_age`/`mort_water`/`mort_temp`, `mort_max` (the
wood-density → maximum-mortality map that carries the trait dependence), `leaf_carbon_sapl` and
`update_bm_inc_counter`.

Parameters come from `pft_mort_params`, which **errors on an unknown PFT id** rather than falling back to
a default — a beech default silently applied to the tropical and boreal PFTs is exactly the ADR 0031
defect, and line M's drivers do not yet pass `fc.pft_ids` (they default to `is_grass ? 8 : 3`), so a
lenient lookup here would reproduce it inside the fix.

Everything is pure Base, allocation-free and type-generic (ADR 0014 keeps the runtime `[deps]` empty).
"""
module TraitMortality

export PFTMortParams, MortHazard, pft_mort_params, mort_max, mort_npp, mort_age, mort_water, mort_temp,
    leaf_carbon_sapl, update_bm_inc_counter, mortality_hazard, survival_prob

# ── C constants that are #defines in the SOURCE, not in any parameter file ────────────────────────────
"`param.k_mort` — growth-efficiency coefficient in the `mort_npp` logistic (`par/lpjparam_fit.js`)."
const K_MORT = 0.01
"`KMORT_2` (`mortality_tree_ind.c:23`) — the logistic's pre-factor on `exp(k_mort·greff)`."
const KMORT_2 = 0.2
"`KMORTBG_LNF` = `-log(0.001)` (`mortality_tree_ind.c:25`) — background-mortality survival coefficient."
const KMORTBG_LNF = -log(0.001)
"`KMORTBG_Q` (`mortality_tree_ind.c:28`) — age-mortality shape exponent (2 ⇒ quadratic in age/longevity)."
const KMORTBG_Q = 2.0
"`BM_INC_COUNTER_MAX` (`mortality_tree_ind.c:22`) — consecutive negative-increment years ⇒ certain death."
const BM_INC_COUNTER_MAX = 5
"`NDAYYEAR` — the noleap year the two stress integrals are normalized by."
const NDAYYEAR = 365

"""
    PFTMortParams{T}

The per-PFT mortality parameters of one LPJmL-FIT tree PFT. `pft_id` is the 0-based `pftpar` index, which
IS the `ind` output's `Type` column (ids 0…6 are the complete tree set, ADR 0031).

Naming traps, all `[VERIFIED]` against the C and resolved here once:

  - `longevity` is the parameter file's JSON key **`"age"`**, not its leaf key `"longevity"` (= 2.0). PFT
    id 5 overrides it to **125**, not 400 — a 3.2× age-mortality difference.
  - `temp_low`/`temp_high` are the **`"temp_stressed"`** interval consumed by `tempstress_tree.c:29`, not
    the establishment gate `"temp"`.
  - `aphen_min` gates the water-stress accumulation (`waterstress_tree.c:31`). It is **10 for id 6**
    (larch), not the `APHEN_MIN` = 60 the other six use — the C file declares the key twice for that PFT
    and json-c's lookup takes the last.
  - the parameter file's own `mort_max` is **DEAD** (read at `mortality_tree_ind.c:87`, overwritten at
    `:92`) and is deliberately absent from this struct so nothing can consume it.

`lai_sapl`/`allom1`/`kpr`/`k_latosa`/`wood_sapl` are here for [`leaf_carbon_sapl`](@ref) (the second hard
kill), `allom2`/`allom3` for the stem diameter of the logging branch (`:139`, inert in this config:
`nlogging` is 0 under `landusetype = NATURAL`).
"""
struct PFTMortParams{T <: AbstractFloat}
    pft_id::Int
    wdmort_1::T
    wdmort_2::T
    mort_water_factor::T
    mort_water_res::T
    mort_temp_factor::T
    longevity::T
    temp_low::T
    temp_high::T
    aphen_min::T
    lai_sapl::T
    allom1::T
    allom2::T
    allom3::T
    kpr::T
    k_latosa::T
    wood_sapl::T
end

# ── the parameter table. LITERALS, gated row-by-row against the committed CSV (see the file header) ───
# Regenerate the CSV with `python3 scripts/build_mort_params_reference.py`; if it moves, this table and
# `build_slow_flux_table.py::PFT_PARAMS` must move with it and the gate testitem will say so.
"""
    PFT_MORT_PARAMS

[`PFTMortParams`](@ref) for each of LPJmL-FIT's seven tree PFTs, keyed by the `ind` `Type` id. The values
are gated against `test/testitems/references/S_pft_mortality_params.csv` (the generated source of record)
by `test/testitems/slow_trait_mortality_tests.jl`. Look up through [`pft_mort_params`](@ref), which
errors on a missing id instead of defaulting.
"""
const PFT_MORT_PARAMS = Dict{Int, PFTMortParams{Float64}}(
    # id, wdmort_1, wdmort_2, mwf, mwr, mtf, longevity, t_low, t_high, aphen_min, lai_sapl,
    #     allom1, allom2, allom3, kpr, k_latosa, wood_sapl
    0 => PFTMortParams{Float64}(
        0, -2.458, 0.129, 10.0, 0.75, 5.0, 400.0, 12.5, 54.0, 60.0, 1.5,
        117.44, 28.749, 0.5633, 1.2922, 4000.0, 1.2
    ),
    1 => PFTMortParams{Float64}(
        1, -2.625, 0.236, 5.0, 0.25, 5.0, 400.0, -15.0, 54.0, 60.0, 1.5,
        101.34, 31.4093, 0.665, 1.4163, 4000.0, 1.2
    ),
    2 => PFTMortParams{Float64}(
        2, -2.625, 0.236, 10.0, 0.25, 5.0, 400.0, -10.0, 54.0, 60.0, 1.5,
        117.44, 28.749, 0.5633, 1.2922, 4000.0, 1.2
    ),
    3 => PFTMortParams{Float64}(
        3, -2.465, 0.148, 5.0, 0.75, 5.0, 400.0, -20.0, 54.0, 60.0, 1.5,
        117.44, 28.749, 0.5633, 1.2922, 4000.0, 1.2
    ),
    4 => PFTMortParams{Float64}(
        4, -2.43, 0.143, 7.5, 0.65, 5.0, 400.0, -45.0, 54.0, 60.0, 1.5,
        101.34, 31.4093, 0.665, 1.4163, 4000.0, 1.2
    ),
    5 => PFTMortParams{Float64}(
        5, -2.43, 0.143, 20.0, 0.75, 5.0, 125.0, -45.0, 54.0, 60.0, 1.5,
        117.44, 28.749, 0.5633, 1.2922, 4000.0, 1.2
    ),
    6 => PFTMortParams{Float64}(
        6, -2.43, 0.143, 5.0, 0.65, 5.0, 400.0, -70.0, 54.0, 10.0, 1.5,
        101.34, 31.4093, 0.665, 1.4163, 4000.0, 1.2
    ),
)

"""
    pft_mort_params(pft_id::Integer) -> PFTMortParams{Float64}

The mortality parameters of tree PFT `pft_id` (the `ind` `Type` id). **Errors** on an id with no row —
grass ids (7/8/9), crops (10-21), and anything out of range.

The error is the point. Applying beech's row (id 3) to another PFT is a real, measured defect class: ids
1/2 are XERIC (`mort_water_res` 0.25, not 0.75), id 5's `longevity` is 125 (not 400) and its
`mort_water_factor` 20 (not 5), and ids 1/2/4/5/6 carry non-temperate `wdmort` pairs. `fc.pft_ids` exists
(`fast.jl:94`, maintained by `slow.jl`) but line M's drivers do not yet pass it, so `FDiffFastCore`
defaults every tree to id 3 — a lenient lookup here would silently run the Amazon and the Sahel on beech
wood-density mortality (M integration point #1). Until that lands, a caller must pass a real id.
"""
function pft_mort_params(pft_id::Integer)
    p = get(PFT_MORT_PARAMS, Int(pft_id), nothing)
    p === nothing && error(
        "TraitMortality: no mortality parameters for PFT id $pft_id. Tree ids are " *
            "$(sort(collect(keys(PFT_MORT_PARAMS)))) (the `ind` `Type` column, ADR 0031); grass ids 7-9 " *
            "carry ZEROED tree fields and crops 10-21 are never emitted in this config. This is NOT a " *
            "defaultable lookup — see `pft_mort_params`'s docstring."
    )
    return p
end

"""
    mort_max(p::PFTMortParams, wooddens) -> Real

The wood-density-dependent maximum mortality rate, `10^(wdmort_1 + wdmort_2/(wooddens/1e6))`
(`mortality_tree_ind.c:92`). `wooddens` is in the `ind` output's units (gC/m³, e.g. 2e5).

**This is the entire trait channel of the hazard, and it is only half the story.** It is monotonically
DECREASING in `wooddens` (over 2e5 → 3e5 the ratio is 1.765 for beech), so on its own it says "denser
wood survives better" — but denser wood also grows more slowly, which lowers `greff` and RAISES
[`mort_npp`](@ref) through the logistic. ADR 0046 §3 measures the net differential as negative for ids 0
and 3. Never use this factor as a standalone selection argument.

Note the parameter file's own `mort_max` is read at `:87` and unconditionally overwritten here at `:92`;
it is dead code and is not carried in [`PFTMortParams`](@ref).
"""
mort_max(p::PFTMortParams, wooddens::Real) =
    exp10(p.wdmort_1 + p.wdmort_2 / (wooddens / oftype(float(wooddens), 1.0e6)))

"""
    mort_npp(p::PFTMortParams, wooddens, bm_delta, leafarea; bm_inc_counter=0) -> Real

Growth-efficiency mortality (`mortality_tree_ind.c:95-101`):

```
greff    = bm_delta / leafarea                                  # leafarea = leaf_c_ind · sla  (:67)
mort_npp = min(1, mort_max/(1 + KMORT_2·exp(k_mort·greff)) · (1 + bm_inc_counter))
```

and **`1` (certain death) when `leafarea ≤ 1e-6`** (`:95`/`:98`), i.e. an individual with essentially no
leaf area dies regardless of everything else.

`bm_delta = bm_inc.carbon/nind − turnover_ind` is the per-individual biomass increment NET of turnover
(`:66`/`:70`) — not NPP. `bm_inc_counter` is the run of consecutive years with `bm_delta < 0`
([`update_bm_inc_counter`](@ref)); it MULTIPLIES the hazard, which is why a declining individual's death
rate escalates before the hard kill at 5 fires.
"""
function mort_npp(
        p::PFTMortParams, wooddens::Real, bm_delta::Real, leafarea::Real;
        bm_inc_counter::Integer = 0
    )
    T = float(promote_type(typeof(wooddens), typeof(bm_delta), typeof(leafarea)))
    leafarea > T(1.0e-6) || return one(T)
    mm = T(mort_max(p, wooddens))
    greff = T(bm_delta) / T(leafarea)
    m = mm / (one(T) + T(KMORT_2) * exp(T(K_MORT) * greff)) * (one(T) + T(bm_inc_counter))
    return min(one(T), m)
end

"""
    mort_age(p::PFTMortParams, age) -> Real

Age (background) mortality, `mort_min()` at `mortality_tree_ind.c:40-44` capped at `:110-111`:

```
mort_age = min(1, KMORTBG_LNF·(KMORTBG_Q+1)/L · (age/L)^KMORTBG_Q)      # L = p.longevity
```

⚠ `age` is the **PRE-increment** age. `annual_tree.c:46` does `tree->age++` AFTER
`mortality_tree_ind()`, so the `Age` in the `ind` output is one MORE than the age that produced that
row's `mort_age`. Recomputing from the emitted `Age` matches to only ~1.4e-4; from `Age − 1` it matches
to ~5e-8 (CLAUDE.md §3). Pass `Age − 1`.
"""
function mort_age(p::PFTMortParams, age::Real)
    T = float(promote_type(typeof(age), typeof(p.longevity)))
    L = T(p.longevity)
    return min(one(T), T(KMORTBG_LNF) * (T(KMORTBG_Q) + one(T)) / L * (T(age) / L)^T(KMORTBG_Q))
end

"""
    mort_water(p::PFTMortParams, water_stress; bm_inc_counter=0) -> Real

Water-stress mortality (`mortality_tree_ind.c:113-115`):

```
mort_water = min(1, mort_water_factor · water_stress / NDAYYEAR · (1 + bm_inc_counter))
```

`water_stress` is the C's own ANNUAL INTEGRAL, accumulated daily by `waterstress_tree.c:31-42` only on
days that pass three gates (`aphen > aphen_min`, `soil.temp[0] > 10`,
`wscal < mort_water_res − minwscal`) as `phen · (vpd/1000) · ((mort_water_res − minwscal) − wscal)`, and
reset to 0 on the coldest day of the year. So `mort_water_res` and `minwscal` enter the hazard only
THROUGH that accumulator — they are not free parameters of this function, which is why the port takes the
integral rather than recomputing it. The `(1 + bm_inc_counter)` multiplier is easy to miss and is present.
"""
function mort_water(p::PFTMortParams, water_stress::Real; bm_inc_counter::Integer = 0)
    T = float(promote_type(typeof(water_stress), typeof(p.mort_water_factor)))
    m = T(p.mort_water_factor) * T(water_stress) / T(NDAYYEAR) * (one(T) + T(bm_inc_counter))
    return min(one(T), m)
end

"""
    mort_temp(p::PFTMortParams, temp_stress) -> Real

Temperature-stress mortality (`mortality_tree_ind.c:117-119`):

```
mort_temp = min(1, mort_temp_factor · temp_stress / NDAYYEAR)
```

`temp_stress` is an integer DAY COUNT — `tempstress_tree.c:29-30` increments it by 1 for each day whose
temperature falls outside `[temp_low, temp_high]`, and resets it at the start of the vegetation period.
Unlike [`mort_water`](@ref) it carries **no** `bm_inc_counter` multiplier.
"""
function mort_temp(p::PFTMortParams, temp_stress::Real)
    T = float(promote_type(typeof(temp_stress), typeof(p.mort_temp_factor)))
    return min(one(T), T(p.mort_temp_factor) * T(temp_stress) / T(NDAYYEAR))
end

"""
    leaf_carbon_sapl(p::PFTMortParams, sla) -> Real

The leaf carbon of a sapling of this PFT at specific leaf area `sla`
(`mortality_tree_ind.c:63-65`):

```
leaf_carbon_sapl = ( lai_sapl·allom1·wood_sapl^(kpr/2)·(4·sla/π/k_latosa)^(kpr/2) / sla )^(2/(2−kpr))
```

It is the threshold of the second hard kill: an individual whose per-individual leaf carbon has fallen
below a sapling's is removed outright (`:132-133`, the "ghost tree fix"). Note it depends on `sla`, so it
is **trait-dependent too** — a second, weaker selection channel alongside [`mort_max`](@ref).
"""
function leaf_carbon_sapl(p::PFTMortParams, sla::Real)
    T = float(promote_type(typeof(sla), typeof(p.kpr)))
    s = T(sla)
    h = T(p.kpr) / T(2)
    base = T(p.lai_sapl) * T(p.allom1) * T(p.wood_sapl)^h * (T(4) * s / T(pi) / T(p.k_latosa))^h / s
    return base^(T(2) / (T(2) - T(p.kpr)))
end

"""
    update_bm_inc_counter(counter::Integer, age, bm_delta) -> Int

Advance FIT's consecutive-negative-increment counter (`mortality_tree_ind.c:71-81`): reset to 0 when the
PRE-increment `age == 1`, then increment on `bm_delta < 0` and reset to 0 otherwise.

The counter is genuine per-individual STATE — it multiplies [`mort_npp`](@ref) and [`mort_water`](@ref),
and reaching `BM_INC_COUNTER_MAX` = 5 is a certain kill. ⚠ It is **not recoverable** from the annual `ind`
output (`bm_inc_counter` is one of the commented-out RAW-only columns), so a training table cannot carry
it; a rollout must evolve it itself, starting from 0.
"""
function update_bm_inc_counter(counter::Integer, age::Real, bm_delta::Real)
    c = age == 1 ? 0 : Int(counter)
    return bm_delta < 0 ? c + 1 : 0
end

"""
    MortHazard{T}

The decomposed result of [`mortality_hazard`](@ref): the four additive components as FIT computes and
individually caps them, their capped sum `total`, and the reason for a hard kill.

`hard_kill` is `:none`, `:bm_inc_counter` (a 5-year run of negative increment, `mortality_tree_ind.c:128`)
or `:ghost_tree` (leaf carbon below a sapling's, `:132`). When it is not `:none`, `total == 1`.

Keep the decomposition, do not collapse it: ADR 0046 §3's whole point is that the trait dependence enters
through `npp` in a direction that can OPPOSE the `mort_max` factor, so a validation harness has to read
the parts, not just the sum.
"""
struct MortHazard{T <: AbstractFloat}
    npp::T
    age::T
    water::T
    temp::T
    total::T
    hard_kill::Symbol
end

"""
    mortality_hazard(p::PFTMortParams; wooddens, sla, age, bm_delta, leafarea, leaf_c,
                     water_stress, temp_stress, bm_inc_counter=0) -> MortHazard

The complete LPJmL-FIT per-individual annual mortality probability, faithful to
`mortality_tree_ind.c:89-133`:

```
mort = min(1, mort_npp + mort_age + mort_water + mort_temp)        # ADDITIVE, each part capped first
if bm_inc_counter ≥ 5                     -> mort = 1              # :128
if leaf_c < leaf_carbon_sapl(sla)         -> mort = 1              # :132
```

`age` is the **PRE-increment** age (emitted `Age − 1`; see [`mort_age`](@ref)). `leafarea` is the
individual's realized leaf area `leaf_c·sla` (`:67`), `leaf_c` its per-individual leaf carbon, and
`water_stress`/`temp_stress` the two annual stress integrals ([`mort_water`](@ref)/[`mort_temp`](@ref)).

TWO THINGS THIS IS NOT, both load-bearing for anyone scoring it against FIT:

 1. **It is not the whole death process.** FIT applies the returned probability as a per-individual
    `erand48` Bernoulli draw (`:145`) — so a faithful rollout is stochastic, and `1 − total` is an
    EXPECTED survival ([`survival_prob`](@ref)), not a deterministic one. Two further kills sit outside
    this function: `isneg_tree` (any negative pool, or `nind`/`fpc` underflow — `:148`) and the
    cell-level bioclimatic `survive()` (`annual_tree.c:42`, 20-yr buffered `temp_min`/`temp_range` vs the
    PFT's `"temp"` gate), which removes the whole PFT from the cell and is NOT trait-dependent.
 2. **The logging branch is inert here** (`:141`, `param.logging_mort`): this config runs
    `landusetype = NATURAL` with `landuse:"no"`, so `patch->nlogging` is 0 and the branch never executes
    (CLAUDE.md §3 — confirm a C path runs in `individual=true` before porting it). It is deliberately
    absent.
"""
function mortality_hazard(
        p::PFTMortParams;
        wooddens::Real, sla::Real, age::Real, bm_delta::Real, leafarea::Real, leaf_c::Real,
        water_stress::Real, temp_stress::Real, bm_inc_counter::Integer = 0
    )
    T = float(
        promote_type(
            typeof(wooddens), typeof(sla), typeof(age), typeof(bm_delta), typeof(leafarea),
            typeof(leaf_c), typeof(water_stress), typeof(temp_stress)
        )
    )
    mn = T(mort_npp(p, wooddens, bm_delta, leafarea; bm_inc_counter = bm_inc_counter))
    ma = T(mort_age(p, age))
    mw = T(mort_water(p, water_stress; bm_inc_counter = bm_inc_counter))
    mt = T(mort_temp(p, temp_stress))
    summed = min(one(T), mn + ma + mw + mt)
    kill = if bm_inc_counter >= BM_INC_COUNTER_MAX
        :bm_inc_counter
    elseif leaf_c < T(leaf_carbon_sapl(p, sla))
        :ghost_tree
    else
        :none
    end
    total = kill === :none ? summed : one(T)
    return MortHazard{T}(mn, ma, mw, mt, total, kill)
end

"""
    survival_prob(h::MortHazard) -> Real

`1 − h.total` — the EXPECTED one-year survival probability of the individual. FIT realizes it as a
Bernoulli draw per individual, so this is the mean of that draw, not a deterministic survival.
"""
survival_prob(h::MortHazard) = one(h.total) - h.total

end # module TraitMortality
