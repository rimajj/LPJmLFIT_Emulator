#!/usr/bin/env julia
# ── RUNG 3 — F_diff's canopy GROWTH against the C's own, PAIRED PER STEM ──────────────────────────────
#
# EXECUTION_PLAN.md rung 3 is "F alone, on the C's own canopy", and its exit gate is *the decadal canopy
# drift is quantified and either fixed or bounded*. The drift on the table (ADR 0053/0060): over 2010-2019
# F's crown cover moves +65 % (boreal), +27 % (Hainich), −13 % (Sahel) where the C's own moves −11 / −3 /
# +25 %. Every previous measurement of it was an AGGREGATE over a decade, which cannot separate
#   (i)  a per-year growth bias that compounds, from
#   (ii) something the free-running loop manufactures out of its own accumulated state.
# Those need different fixes, and no statistic in this repo could tell them apart.
#
# WHAT IS NEW HERE: the comparison is at the level F actually computes — ONE STEM, ONE YEAR — because
# `(Cell, Patch, ID)` turns out to be a STABLE cross-year individual identity in the C's annual `ind`
# output (the gate lives in `scripts/build_biome_stem_growth_reference.py`; `Age` increments by exactly 1
# on all 10 323 pairs, `SLA`/`Wooddens` are bit-identical, and no living stem vanishes except 8 stem-years
# of threshold flicker within 0.4 m of the writer's 5 m cut). So F can be restarted from the C's own stand
# every year and each of its stems scored against ITS OWN next-year row.
#
# ARMS (all: `slow = nothing`, 25-patch ensemble = the C's own output basis, `wscal_leafon = true`)
#   REINIT   — the rung-3 arm. Year y starts from the C's roster at the end of y−1 and runs year y's
#              forcing. Soil water and the energy closure are CARRIED across years (they are F's own
#              state; only the canopy is replaced), so this isolates the canopy from accumulation.
#   FREE     — one continuous 2010-2019 run from the same 2009 roster. REINIT vs FREE IS the split
#              between (i) and (ii) above.
#
# THE YEAR ALIGNMENT IS MEASURED, NOT ASSUMED (`residual-diagnosis` §1). The `ind` row for year y is
# written at the END of year y (`annual_natural.c` runs after the daily loop), so the stand entering
# year y is the year-(y−1) roster and the physically correct pairing is
#   A:  start = roster(y−1),  forcing = year y,  target = roster(y).
# The existing kernel probe starts from roster(2010) and drives it with 2010 forcing, i.e.
#   B:  start = roster(y),    forcing = year y,  target = roster(y+1),
# which grows the stand with the weather it has already lived through. Both are run below and the paired
# per-stem error decides between them — an off-by-one in the reference basis is exactly the class of error
# that produced (and then withdrew) ADR 0053 finding 4.
#
# ⚠ TWO REFERENCE-BASIS FACTS THAT CHANGE HOW THE C COLUMNS ARE READ.
#   1. The committed `M_fdiff_oracle_biomes_annual.csv` (`fpc_tree_crown` = the C's `a_fpc`) comes from the
#      per-cell SINGLE-CELL daily re-runs, while F's initial canopy comes from the GLOBAL run's `ind`
#      table. Those are two runs of a stochastic model (ADR 0041). Measured here on daily GPP over
#      2010-2019, four of the five agree to <1.2 % (r >= 0.9989), but `tropical_amazon` differs by 6.7 %
#      with r = 0.970 — so the Amazon's year-matched structural comparison against `a_fpc` is against a
#      DIFFERENT REALISATION and its level must not be read as an F error.
#   2. `a_fpc` includes stems below 5 m; the `ind` roster F is built from cannot. That fraction is
#      TIME-VARYING (boreal 0.712 -> 0.806 over the decade), so it contaminates the DRIFT and not just the
#      level. Both problems disappear by scoring against `fpc_live`/`fpc_all` from
#      `references/M_stem_growth_reference.csv`, which are formed from the very stems F is handed.
#      `a_fpc` is still printed beside them so the substitution can never be silent (ADR 0060's rule).
#
# THE C's GROWTH-ONLY TARGET. The C's year-over-year canopy change mixes growth, mortality and 5 m
# crossers; F under `slow = nothing` has growth only. The like-for-like target is therefore
# `fpc_all(y) / fpc_live(y−1)` — all stems emitted in year y INCLUDING those flagged dead (mortality is
# applied after allocation, so they grew first) over the stand that entered the year — with the 5 m
# crossers' share `fpc_new` reported separately, never folded in.
#
# Run (CLAUDE.md §2 — never the login node):
#   TIME=02:00:00 scripts/sbatch_julia.sh M-rung3 --project=. scripts/biome_canopy_growth_probe.jl
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams, FDiffParams
using Statistics, Printf

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
const WORK = get(ENV, "M_CANOPY_DIR", "/p/tmp/jamirp/M_canopy_drift")
const INDDIR = joinpath(WORK, "individuals")
const σ = 5.670374419e-8
const Y0, Y1 = 2010, 2019
const NYEAR = Y1 - Y0 + 1
const PATCH_AREA = 225.0

# ── readers ──────────────────────────────────────────────────────────────────────────────────────────
function readcsv(path)
    lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
    hdr = split(strip(lines[1]), ',')
    rows = [split(strip(l), ',') for l in lines[2:end]]
    return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
end
fcol(d, k) = parse.(Float64, d[k])

function readsoil(path)
    sd = Float64[]; whcs = Float64[]; rdist = Float64[]
    for ln in eachline(path)
        s = strip(ln)
        (isempty(s) || startswith(s, "#")) && continue
        x = parse.(Float64, split(s))
        push!(sd, x[2]); push!(whcs, x[3]); push!(rdist, x[4])
    end
    return hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)
end

"""
One patch's `(pools, tmpls, ids, types, kbeers)` from already-parsed roster rows — same reconstruction as
every other M probe (`biome_fdiff_oracle_probe.jl::build_patch`), plus the C's own per-stem identity
(`ids`), the C's own PFT id per stem (`types`, the `Type` column) and its own Beer–Lambert extinction
(`kbeers`, the roster's `k_beer` column = `lightextcoeff`).

`tmpl_pft = true` builds each template with THAT stem's PFT constants (`FDiff.pft_canopy_traits` /
`pft_tempstressparams`) instead of beech's four hard-coded values (`intc` 0.02, `albedo_stem` 0.04,
`albedo_litter` 0.1, `snowcanopyfrac` 0.4) and beech's 20/30 °C photosynthesis optimum. It governs ONLY
those template constants — the rest of the per-PFT physiology travels in the `PFTPhys` bundle — which is
what lets a single-variable arm hold them at beech's while changing one bundle field.
`alphaa`, `albedo_leaf`, `emax` and `sla` are read PER STEM from the C's own output in both modes —
they are the individual's own values, not a PFT default.
"""
function build_patch(ind, rows; tmpl_pft::Bool = false)
    v(k, r) = parse(Float64, ind[k][r])
    ty(r) = parse(Int, ind["type"][r])
    pools = [
        TreePools{Float64}(
                v("leaf_c", r), v("sapwood_c", r),
                max(v("agb", r) / v("nind", r) - v("leaf_c", r) - v("sapwood_c", r), 0.0), v("root_c", r),
                v("height", r), v("crownarea", r), v("nind", r), v("sla", r), v("wooddens", r), false
            ) for r in rows
    ]
    function mktmpl(r)
        tr = tmpl_pft ? FDiff.pft_canopy_traits(ty(r)) :
            (; intc = 0.02, albedo_stem = 0.04, albedo_litter = 0.1, snowcanopyfrac = 0.4)
        ts = tmpl_pft ? FDiff.pft_tempstressparams(ty(r)) :
            TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0)
        return Individual{Float64}(
            v("fpar_leafon", r), 0.0, v("alphaa", r), v("albedo_leaf", r), v("emax", r),
            v("sapwood_c", r), v("root_c", r), 0.0, tr.intc, tr.albedo_stem, tr.albedo_litter,
            tr.snowcanopyfrac, v("nind", r),
            PhotoParams{Float64}(; path = :c3, issla = true, sla = v("sla", r)), ts, false
        )
    end
    ids = [parse(Int, ind["id"][r]) for r in rows]
    types = [ty(r) for r in rows]
    kbeers = [v("k_beer", r) for r in rows]
    return pools, [mktmpl(r) for r in rows], ids, types, kbeers
end

"All patches of one roster file, keyed by the C's own patch number (ONE ENSEMBLE MEMBER PER PATCH)."
function readcanopy_patches(path; tmpl_pft::Bool = false)
    ind = readcsv(path)
    v(k, r) = parse(Float64, ind[k][r])
    nt(r) = parse(Int, ind["type"][r])
    prows = Dict{Int, Vector{Int}}()
    for r in eachindex(ind["type"])
        (nt(r) <= 6 && v("height", r) > 0) && push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
    end
    pk = sort(collect(keys(prows)))
    return Dict(p => build_patch(ind, prows[p]; tmpl_pft = tmpl_pft) for p in pk), pk
end

"Daily `AtmForcing` for one cell, split by year: `forc[y]` is that calendar year's 365 days."
function forcings_by_year(name)
    f = readcsv(joinpath(REFDIR, "biome_forcing_$(name).csv"))
    yr = parse.(Int, f["year"])
    tairK = fcol(f, "temp") .+ 273.15
    swd = fcol(f, "swdown"); lwn = fcol(f, "lwnet"); prec = fcol(f, "precip")
    huss = fcol(f, "huss"); co2 = fcol(f, "co2")
    out = Dict{Int, Vector{AtmForcing{Float64}}}()
    for y in Y0:Y1
        idx = findall(==(y), yr)
        out[y] = [
            AtmForcing(;
                    swdown = swd[i], lwdown = lwn[i] + σ * tairK[i]^4, tair = tairK[i], qair = huss[i],
                    wind = 2.0, psurf = 1.0e5, precip = prec[i], co2 = co2[i]
                ) for i in idx
        ]
    end
    return out, mean(tairK)
end

"The C's own per-stem next-year state, keyed (name, year, patch, id)."
function read_targets()
    d = readcsv(joinpath(WORK, "M_stem_targets.csv"))
    t = Dict{NTuple{4, Any}, NTuple{5, Float64}}()
    for r in eachindex(d["name"])
        k = (String(d["name"][r]), parse(Int, d["Year"][r]), parse(Int, d["Patch"][r]), parse(Int, d["ID"][r]))
        t[k] = (
            parse(Float64, d["Height"][r]), parse(Float64, d["fpc_ind"][r]), parse(Float64, d["agb"][r]),
            parse(Float64, d["npp"][r]), parse(Float64, d["isdead"][r]),
        )
    end
    return t
end

"The committed per-(cell,year) C accounting (fpc_live / fpc_all / fpc_new / a_fpc / >5 m fraction)."
function read_stemref()
    d = readcsv(joinpath(REFDIR, "M_stem_growth_reference.csv"))
    o = Dict{Tuple{String, Int}, Dict{String, Float64}}()
    for r in eachindex(d["name"])
        k = (String(d["name"][r]), parse(Int, d["year"][r]))
        o[k] = Dict(
            c => parse(Float64, d[c][r])
                for c in (
                    "n_live", "n_dead", "n_new", "fpc_live", "fpc_all", "fpc_new", "fpc_dead",
                    "agb_live", "npp_all", "c_a_fpc", "gt5m_frac",
                )
        )
    end
    return o
end

"The committed C annual tree GPP (`d_gpp − d_grass_gpp`, gC/m²/day) — the SINGLE-CELL re-run's basis."
function read_cgpp()
    d = readcsv(joinpath(REFDIR, "M_fdiff_oracle_biomes_annual.csv"))
    return Dict(
        (String(d["name"][r]), parse(Int, d["year"][r])) => parse(Float64, d["gpp_tree"][r])
            for r in eachindex(d["name"])
    )
end

# The ACTIVE calibrated set with `wscal_leafon` explicit (ADR 0051/0059) — never a bare `FDiffParams()`.
# `respcoeff` is overridable because it is the ONE constant this probe tests as a diagnostic arm; the
# shipped default (1.0) is untouched, and nothing in `src/` changes (guardrail 4).
function mkparams(; respcoeff = nothing)
    p = FDiff.tebs_params(Float64)
    w = p.water
    fns = fieldnames(typeof(w))
    nt = NamedTuple{fns}(map(f -> getfield(w, f), fns))
    w2 = typeof(w)(; merge(nt, (; wscal_leafon = true))...)
    r = p.resp
    if respcoeff !== nothing
        rf = fieldnames(typeof(r))
        rnt = NamedTuple{rf}(map(f -> getfield(r, f), rf))
        r = typeof(r)(; merge(rnt, (; respcoeff = respcoeff))...)
    end
    return FDiffParams{Float64}(p.photo, p.tstress, w2, r, p.allom, p.nlambda, p.ω)
end

const PARAMS = mkparams()
const ALLOM = PARAMS.allom

# ── the per-PFT maintenance-respiration coefficient the C actually uses ───────────────────────────────
# `par/pft_lpjmlfit.js`, read with `cpp -P` (CLAUDE.md §3 — never by eye): the TROPICAL broadleaved
# evergreen tree (id 0) has `respcoeff = 0.2`; all six temperate/boreal trees have **1.2**. A 6× spread
# across the tree PFTs. F carries ONE scalar for every tree in every cell: `RespParams.respcoeff`
# (`fdiff.jl:298`) defaults to 1.0 and the ACTIVE calibrated set sets it to **1.2**
# (`fdiff.jl:1287`, `tebs_params`) — i.e. beech's value, correct for a temperate/boreal stand and **6×
# too high for a tropical one**. Both Sahel and Amazon are 100 % id 0 by sapwood, so F over-respires
# every stem there by 6×. Arm `R2` below substitutes the cell's own stem-weighted value; at the three
# temperate/boreal/mediterranean cells it is a no-op BY CONSTRUCTION (1.2 -> 1.2), which is also the
# check that the arm changes exactly one thing.
const PFT_RESPCOEFF = (0.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2)   # ids 0..6

"""
The C's own `respcoeff` for one cell, weighted by the pool that dominates maintenance respiration.

`rmaint ∝ c_sapwood/cn_sapwood + phen·c_root/cn_root` (`fdiff.jl:651`), so the honest scalar stand-in for
a per-individual coefficient is the SAPWOOD-weighted mean over the stems F is handed. Returned with the
weights so a mixed-PFT cell cannot be reported as if it had one coefficient.
"""
function cell_respcoeff(name, year)
    ind = readcsv(joinpath(INDDIR, "M_individuals_$(name)_$(year).csv"))
    v(k, r) = parse(Float64, ind[k][r])
    w = zeros(7)
    for r in eachindex(ind["type"])
        t = parse(Int, ind["type"][r])
        (t <= 6 && v("height", r) > 0) || continue
        w[t + 1] += v("sapwood_c", r) * v("nind", r)
    end
    s = sum(w)
    return s > 0 ? sum(w[i] * PFT_RESPCOEFF[i] for i in 1:7) / s : 1.0, w ./ max(s, eps())
end

patch_fpc(pools) = sum(FDiff._treepools_fpc(p, ALLOM) for p in pools if !p.is_grass; init = 0.0)
# ADR 0126: the same sum with each stem's OWN Beer–Lambert extinction (the C's `k_beer` column), which is
# the basis the C's own `fpc_ind` is on. Used by arm P only; the existing arms keep the shared 0.59 so
# their published numbers reproduce (ADR 0060: emit both, never substitute silently).
patch_fpc_k(pools, kb) = sum(
    FDiff._treepools_fpc(pools[i], ALLOM; k_beer = kb[i]) for i in eachindex(pools) if !pools[i].is_grass;
    init = 0.0
)

"""
ONE per-PFT field mixed into an otherwise-BEECH bundle, per stem — the single-variable attribution arms.

Arm P changes nine parameters at once, so it cannot say WHICH one moved a cell. Each subset takes exactly
one field from the stem's own PFT and beech's (id 3) for all the rest, so the arms are independent and
their effects are attributable:
  `:resp`     — the maintenance-respiration coefficient (0.2 tropical / 1.2 temperate+boreal)
  `:tstress`  — the photosynthesis temperature limits (`temp_photos` 15/25 boreal vs 20/30; `temp_co2`)
  `:kbeer`    — the Beer–Lambert extinction (0.45 needleleaved / 0.59 broadleaved)
  `:gmin`     — the minimum canopy conductance (0.3–1.6)
  `:alloc`    — turnover (leaf/root residence 1/2/4 yr, sapwood 25/30 yr)
  `:allom`    — the crown/height coefficients (angiosperm vs gymnosperm), `k_beer` held at beech's
  `:traits`   — the four TEMPLATE constants (`intc` 0.02 vs 0.06, `albedo_stem`, `albedo_litter`,
                `snowcanopyfrac`); the bundle stays pure beech, the caller passes `tmpl_pft = true`
  `:phen`     — NOTHING from the bundle, so the ONLY difference from arm A is that real `pft_ids` are
                passed: the per-PFT GSI **phenology**. ⚠ THIS IS THE ATTRIBUTION BASELINE, not a null arm.
                `pft_ids` already existed before ADR 0126 and arm A does not pass it (its trees all run
                beech's GSI filters), so EVERY per-PFT arm carries the phenology change too and each
                column below must be read against `:phen`, not against `A`.
⚠ These do NOT add up: the daily canopy is nonlinear, and `:allom`/`:alloc` act through the next year's
pools. Read them as attributions, not as a decomposition.
"""
function pft_phys_subset(types, which::Symbol)
    which in (:resp, :tstress, :kbeer, :gmin, :alloc, :allom, :traits, :phen) ||
        error("pft_phys_subset: unknown subset $which")
    b = FDiff.pft_phys(3)                    # beech — F's shipped configuration
    return [one_field_bundle(b, FDiff.pft_phys(t), which) for t in types]
end

"`b` (beech) with exactly one field taken from `q` (this stem's own PFT)."
function one_field_bundle(b, q, which::Symbol)
    P = FDiff.PFTPhys{Float64}
    # `:phen` and `:traits` take nothing from `q`: for `:phen` the templates are beech's too, so the only
    # difference from arm A is the per-PFT GSI phenology that real `pft_ids` switch on; `:traits` adds the
    # four per-PFT template constants on top of that (its caller passes `tmpl_pft = true`).
    which in (:traits, :phen) && return b
    which === :resp && return P(q.resp, b.alloc, b.allom, b.tstress, b.gmin)
    which === :tstress && return P(b.resp, b.alloc, b.allom, q.tstress, b.gmin)
    which === :gmin && return P(b.resp, b.alloc, b.allom, b.tstress, q.gmin)
    which === :alloc && return P(b.resp, q.alloc, b.allom, b.tstress, b.gmin)
    # `k_beer` and the crown/height coefficients share one struct in F (and in the C's `pftpar`), so the
    # two arms are separated by field-swapping inside it: `:kbeer` takes only the extinction, `:allom`
    # takes everything BUT the extinction.
    which === :kbeer && return P(b.resp, b.alloc, with_kbeer(b.allom, q.allom.k_beer), b.tstress, b.gmin)
    return P(b.resp, b.alloc, with_kbeer(q.allom, b.allom.k_beer), b.tstress, b.gmin)   # :allom
end

"A `TreeAllometry` equal to `base` with `k_beer` replaced."
function with_kbeer(base, kb)
    fns = fieldnames(typeof(base))
    nt = NamedTuple{fns}(map(f -> getfield(base, f), fns))
    return typeof(base)(; merge(nt, (; k_beer = kb))...)
end

"""
Run ONE year of F on one patch. Returns the grown pools and the year's mean tree GPP.

`state`/`clo` are passed in and mutated, so a caller can carry F's own soil water and energy state across
a year boundary while replacing the canopy — which is what makes the REINIT arm a canopy experiment
rather than a full re-initialisation experiment.

`per_pft`/`types` (ADR 0126): with `per_pft = true` the core runs each cohort's own `respcoeff`, `gmin`,
turnover, crown allometry, `k_beer` and photosynthesis temperature limits instead of beech's for every
tree. `types` must be the C's own per-stem `Type` column — passing the default ids would make every tree
a beech again and the arm a no-op.
"""
function run_one_year!(
        state, clo, pools, tmpls, soil, lat, forc; params = PARAMS, per_pft::Bool = false, types = nothing,
        subset::Symbol = :all
    )
    core = per_pft ?
        FDiffFastCore(
            pools, tmpls, soil, lat; params = params, pft_ids = types,
            per_pft_params = subset === :all ? true : pft_phys_subset(types, subset)
        ) :
        FDiffFastCore(pools, tmpls, soil, lat; params = params)
    bc_f = LPJmLFITEmulator.stand_structure_tof(core)
    fpc0 = bc_f.fpc
    gpp = 0.0; npp = 0.0
    for f in forc
        (ftoe, _, _, _) = LPJmLFITEmulator.couple_day!(core, clo, state, bc_f, f; feedback = true)
        gpp += ftoe.gpp; npp += ftoe.npp
    end
    ftos = LPJmLFITEmulator.annual_step!(core, state)
    # gpp/npp: gC/m²/day (year mean).  bm_inc: gC/m²/yr, the assimilate actually handed to allocation.
    return core.pools, fpc0, gpp / length(forc), npp / length(forc), Float64(ftos.bm_inc)
end

# ── setup ────────────────────────────────────────────────────────────────────────────────────────────
cells = readcsv(joinpath(REFDIR, "M_cells.csv"))
names = String.(cells["name"]); lats = fcol(cells, "lat")
targets = read_targets()
sref = read_stemref()
const CGPP = read_cgpp()
cgpp(name, y) = get(CGPP, (name, y), NaN)

@printf("=== RUNG 3 — F_diff canopy GROWTH vs the C, PAIRED PER STEM, 5 cells, %d-%d ===\n", Y0, Y1)
@printf("(slow=nothing, 25-patch ensemble, wscal_leafon=true; the C side is the GLOBAL run's own `ind`)\n")
flush(stdout)

# ── the arms ─────────────────────────────────────────────────────────────────────────────────────────
# Per (cell, alignment) we accumulate:
#   pair rows  (name, year, patch, id, F_height, C_height, F_agb, C_agb, F_fpc, C_fpc, isdead)
#   per-year ensemble crown cover, F and C
struct PairRow
    name::String; year::Int; patch::Int; id::Int
    fh::Float64; ch::Float64; fa::Float64; ca::Float64; ff::Float64; cf::Float64
    h0::Float64; a0::Float64; f0::Float64
    nind::Float64        # 1/patcharea — converts the per-individual pools to per-m²
    cnpp::Float64        # the C's own annual NPP of this stem that year, gC/m²/yr (`ind.npp`)
    dead::Bool
end

"""
REINIT for one cell under one alignment.

`shift = 0` (alignment A, physically correct): year y starts from roster(y−1) and runs year y's forcing,
target roster(y).  `shift = 1` (alignment B, the existing kernel probe's convention): year y starts from
roster(y) and runs year y's forcing, target roster(y+1).
"""
function reinit_cell(k::Int; shift::Int = 0, params = PARAMS, per_pft::Bool = false, subset::Symbol = :all)
    name = names[k]
    forc, tair0 = forcings_by_year(name)
    soil = readsoil(joinpath(REFDIR, "M_soilcolumn_$(name).txt"))
    pairs = PairRow[]
    fpc_F = fill(NaN, NYEAR); fpc_F0 = fill(NaN, NYEAR); gpp_F = fill(NaN, NYEAR)
    npp_F = fill(NaN, NYEAR); bmi_F = fill(NaN, NYEAR)
    states = Dict{Int, Any}(); clos = Dict{Int, Any}()
    for (yi, y) in enumerate(Y0:Y1)
        ysrc = y - 1 + shift                       # the roster year F starts from
        ytgt = y + shift                           # the roster year it is scored against
        src = joinpath(INDDIR, "M_individuals_$(name)_$(ysrc).csv")
        (isfile(src) && haskey(forc, y)) || continue
        (ytgt <= Y1) || continue
        patches, pk = readcanopy_patches(src; tmpl_pft = per_pft && subset in (:all, :traits))
        accF = 0.0; accF0 = 0.0; accG = 0.0; accN = 0.0; accB = 0.0
        for p in pk
            pools, tmpls, ids, types, kbeers = patches[p]
            st = get!(states, p, SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER)))
            cl = get!(clos, p, SEBEnergyClosure(; t_soil0 = tair0))
            grown, fpc0, gpp, npp, bmi = run_one_year!(
                st, cl, pools, tmpls, soil, lats[k], forc[y];
                params = params, per_pft = per_pft, types = types, subset = subset
            )
            # arm P scores crown cover on each stem's OWN `k_beer` (the C's own basis); the other arms
            # keep the shared 0.59 so their published numbers reproduce unchanged. A SUBSET arm scores on
            # whichever basis IT ran on, so its crown cover is never on a different basis from its physics.
            kb_on = per_pft && subset in (:all, :kbeer)
            fpc_of(pp) = kb_on ? patch_fpc_k(pp, kbeers) : patch_fpc(pp)
            kb_i(i) = kb_on ? kbeers[i] : ALLOM.k_beer
            accF += fpc_of(grown); accF0 += fpc0; accG += gpp; accN += npp; accB += bmi
            for i in eachindex(ids)
                tk = (name, ytgt, p, ids[i])
                haskey(targets, tk) || continue    # 5 m threshold flicker only (gated in the builder)
                (ch, cfpc, cagb, cnpp, dead) = targets[tk]
                g = grown[i]; s0 = pools[i]
                push!(
                    pairs, PairRow(
                        name, y, p, ids[i], g.height, ch,
                        FDiff.agb_ind(g), cagb / s0.nind,
                        FDiff._treepools_fpc(g, ALLOM; k_beer = kb_i(i)), cfpc,
                        s0.height, FDiff.agb_ind(s0),
                        FDiff._treepools_fpc(s0, ALLOM; k_beer = kb_i(i)),
                        s0.nind, cnpp, dead == 1.0
                    )
                )
            end
        end
        np = length(pk)
        fpc_F[yi] = accF / np; fpc_F0[yi] = accF0 / np; gpp_F[yi] = accG / np
        npp_F[yi] = accN / np; bmi_F[yi] = accB / np
    end
    return (; pairs, fpc = fpc_F, fpc0 = fpc_F0, gpp = gpp_F, npp = npp_F, bm_inc = bmi_F)
end

"The continuous control: one 10-year run per patch from the 2009 roster (alignment A's start state)."
function free_cell(k::Int)
    name = names[k]
    forc, tair0 = forcings_by_year(name)
    soil = readsoil(joinpath(REFDIR, "M_soilcolumn_$(name).txt"))
    patches, pk = readcanopy_patches(joinpath(INDDIR, "M_individuals_$(name)_2009.csv"))
    fpc = fill(0.0, NYEAR); gpp = fill(0.0, NYEAR); bmi = fill(0.0, NYEAR)
    for p in pk
        pools, tmpls, _, _, _ = patches[p]
        st = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
        cl = SEBEnergyClosure(; t_soil0 = tair0)
        for (yi, y) in enumerate(Y0:Y1)
            pools, _, g, _, b = run_one_year!(st, cl, pools, tmpls, soil, lats[k], forc[y])
            fpc[yi] += patch_fpc(pools); gpp[yi] += g; bmi[yi] += b
        end
    end
    return (; fpc = fpc ./ length(pk), gpp = gpp ./ length(pk), bm_inc = bmi ./ length(pk))
end

reinitA = [reinit_cell(k; shift = 0) for k in eachindex(names)]
@printf("REINIT alignment A done\n"); flush(stdout)
reinitB = [reinit_cell(k; shift = 1) for k in eachindex(names)]
@printf("REINIT alignment B done\n"); flush(stdout)
# arm R2 — the ONLY change is the C's own per-cell `respcoeff` (a diagnostic arm, not a code change).
const RESPC = [cell_respcoeff(names[k], 2009) for k in eachindex(names)]
reinitR2 = [reinit_cell(k; shift = 0, params = mkparams(; respcoeff = RESPC[k][1])) for k in eachindex(names)]
@printf("REINIT arm R2 (C's own respcoeff) done\n"); flush(stdout)
# arm P — the CODE CHANGE R2 was the diagnostic for: every cohort runs its own PFT's parameters
# (`per_pft_params=true` + the C's own `Type` per stem). ADR 0126; scored against its pre-registered
# criterion in PART 9.
reinitP = [reinit_cell(k; shift = 0, per_pft = true) for k in eachindex(names)]
@printf("REINIT arm P (per-cohort PFT parameters) done\n"); flush(stdout)
# the SINGLE-VARIABLE attribution arms: arm P changes nine parameters at once, so on its own it cannot say
# which one moved a cell. Each of these takes exactly ONE per-PFT field and beech's for everything else.
const SUBSETS = (:phen, :resp, :tstress, :kbeer, :gmin, :alloc, :allom, :traits)
reinitS = Dict{Symbol, Vector{Any}}()
for sub in SUBSETS
    reinitS[sub] = [reinit_cell(k; shift = 0, per_pft = true, subset = sub) for k in eachindex(names)]
    @printf("REINIT subset arm %-8s done\n", sub); flush(stdout)
end
freearm = [free_cell(k) for k in eachindex(names)]
@printf("FREE arm done\n\n"); flush(stdout)

# ── PART 1 — the basis gate: does the RECONSTRUCTION reproduce the stems it was handed? ───────────────
# F's crown cover BEFORE any physics, over the C's own crown-cover sum for exactly those stems. 1.00 =
# the reconstruction is faithful and everything below is growth (ADR 0060's t=0 check, now per YEAR).
@printf("--- PART 1: BASIS GATE — F's t=0 crown cover / the C's own `fpc_live` of the SAME stems ---\n")
@printf("%-22s%s\n", "cell", join((@sprintf("%7d", y) for y in Y0:Y1)))
for k in eachindex(names)
    f0 = reinitA[k].fpc0
    r = [
        (haskey(sref, (names[k], y - 1)) && !isnan(f0[y - Y0 + 1])) ?
            f0[y - Y0 + 1] / sref[(names[k], y - 1)]["fpc_live"] : NaN for y in Y0:Y1
    ]
    @printf("%-22s%s\n", names[k], join((@sprintf("%7.3f", v) for v in r)))
end
@printf("1.00 = faithful. This is the reconstruction only; no F physics has run.\n")

# ── PART 2 — WHICH YEAR ALIGNMENT IS RIGHT? Measured, not assumed. ───────────────────────────────────
@printf("\n--- PART 2: YEAR ALIGNMENT — median |relative error| of the paired per-stem ANNUAL INCREMENT ---\n")
@printf("    A = roster(y-1) + year-y forcing -> roster(y)   [the `ind` row is written at the END of y]\n")
@printf("    B = roster(y)   + year-y forcing -> roster(y+1) [the existing kernel probe's convention]\n")
@printf("%-22s %10s %10s %10s %10s %8s\n", "cell", "A_dagb", "B_dagb", "A_dheight", "B_dheight", "n_pairs")
function med_relerr(pairs, f_new, f_old, c_new, c_old)
    e = Float64[]
    for p in pairs
        dC = c_new(p) - c_old(p)
        abs(dC) > 1.0e-9 || continue
        push!(e, abs((f_new(p) - f_old(p)) - dC) / abs(dC))
    end
    return isempty(e) ? NaN : median(e)
end
for k in eachindex(names)
    pa = reinitA[k].pairs; pb = reinitB[k].pairs
    @printf(
        "%-22s %10.3f %10.3f %10.3f %10.3f %8d\n", names[k],
        med_relerr(pa, p -> p.fa, p -> p.a0, p -> p.ca, p -> p.a0),
        med_relerr(pb, p -> p.fa, p -> p.a0, p -> p.ca, p -> p.a0),
        med_relerr(pa, p -> p.fh, p -> p.h0, p -> p.ch, p -> p.h0),
        med_relerr(pb, p -> p.fh, p -> p.h0, p -> p.ch, p -> p.h0), length(pa)
    )
end
@printf("The smaller column IS the correct alignment. Everything below uses A.\n")

# ── PART 3 — the paired per-year growth error, per cell and year ─────────────────────────────────────
# `dagb_F/dagb_C` is the ratio of SUMMED per-stem biomass increments over the patch ensemble (a level
# statistic on the quantity F predicts); `med` is the median per-stem ratio (robust, size-blind).
@printf("\n--- PART 3: PAIRED ANNUAL GROWTH, alignment A. Σ increments over all stems, F / C ---\n")
@printf("    A MULTIPLIER, not a ratio of increments, wherever the C's own increment can be near zero:\n")
@printf("    `Fx`/`Cx` are (end / start) of the SAME stems, so a denominator cannot vanish (ADR 0111 §9).\n")
@printf(
    "%-22s %6s %6s %9s %9s %8s %8s %8s %8s %7s\n",
    "cell", "year", "n", "dagb_F/C", "med_stem", "F_agbx", "C_agbx", "F_fpcx", "C_fpcx", "negC"
)
growth_ratio = Dict{String, Vector{Float64}}()
for k in eachindex(names)
    pairs = reinitA[k].pairs
    growth_ratio[names[k]] = Float64[]
    for y in Y0:Y1
        py = [p for p in pairs if p.year == y]
        isempty(py) && continue
        a0 = sum(p.a0 for p in py); f0 = sum(p.f0 for p in py)
        dF = sum(p.fa - p.a0 for p in py); dC = sum(p.ca - p.a0 for p in py)
        ms = median([(p.fa - p.a0) / (p.ca - p.a0) for p in py if abs(p.ca - p.a0) > 1.0e-9])
        push!(growth_ratio[names[k]], dF / dC)
        @printf(
            "%-22s %6d %6d %9.3f %9.3f %8.4f %8.4f %8.4f %8.4f %7d\n", y == Y0 ? names[k] : "", y,
            length(py), dF / dC, ms,
            sum(p.fa for p in py) / a0, sum(p.ca for p in py) / a0,
            sum(p.ff for p in py) / f0, sum(p.cf for p in py) / f0,
            count(p -> p.ca < p.a0, py)
        )
    end
end
@printf("`negC` = stems the C SHRANK over the year; where it is large the per-stem MEDIAN ratio is the\n")
@printf("misleading statistic and the summed one is readable. `*x` columns: 1.02 = the stand's biomass\n")
@printf("(crown cover) grew 2 %% that year — F's against the C's, on exactly the same individuals.\n")

# ── PART 4 — does the decadal drift EQUAL the compounded per-year error? ─────────────────────────────
# This is the rung-3 verdict. `Π F/C` compounds the annual crown-cover growth ratios of the REINIT arm
# (each year restarted on the C's own stand ⇒ pure per-year physics). `FREE 19/10` is the same cell's
# continuous run. If they agree, the drift IS the per-year bias compounding and the fix is in F's annual
# allocation; if FREE is larger, the free-running loop is amplifying it out of its own state.
@printf("\n--- PART 4: THE VERDICT — compounded per-year growth error vs the free-running decadal drift ---\n")
@printf(
    "%-22s %10s %10s %10s %10s %10s %9s\n",
    "cell", "F/C_yrly", "REINIT_c", "C_growth", "FREE_c", "C_live", "a_fpc"
)
for k in eachindex(names)
    name = names[k]
    fF = reinitA[k].fpc; fF0 = reinitA[k].fpc0
    freefpc = freearm[k].fpc
    # F's own per-year crown multiplier under REINIT (grown / the stand it was handed), compounded
    mult = [fF[i] / fF0[i] for i in 1:NYEAR if !isnan(fF[i]) && fF0[i] > 0]
    # the C's own growth-only crown multiplier: all of year y's stems (incl. this year's dead) over the
    # stand that entered the year, with the 5 m crossers removed — the like-for-like target.
    cmult = Float64[]
    for y in Y0:Y1
        (haskey(sref, (name, y)) && haskey(sref, (name, y - 1))) || continue
        push!(cmult, (sref[(name, y)]["fpc_all"] - sref[(name, y)]["fpc_new"]) / sref[(name, y - 1)]["fpc_live"])
    end
    # the year-median of the annual Σ-increment ratio — a PRODUCT of ratios of increments has no
    # meaning (it is not a compounding law), so it is deliberately not formed.
    pig = median(growth_ratio[name])
    @printf(
        "%-22s %10.3f %10.3f %10.3f %10.3f %10.3f %9.3f\n", name, pig, prod(mult), prod(cmult),
        freefpc[end] / freefpc[1],
        sref[(name, Y1)]["fpc_live"] / sref[(name, Y0)]["fpc_live"],
        sref[(name, Y1)]["c_a_fpc"] / sref[(name, Y0)]["c_a_fpc"]
    )
end
@printf("\nF/C_yrly = the YEAR-MEDIAN of (Σ F stem biomass increment / Σ C stem biomass increment).\n")
@printf("REINIT_c = Π_y (F's crown cover after year y / the C stand it was handed) — growth only, 10 yr.\n")
@printf("C_growth = Π_y (the C's own growth-only crown multiplier, 5 m crossers removed).\n")
@printf("FREE_c   = the continuous arm's 2019/2010 crown cover — growth AND accumulation.\n")
@printf("C_live   = the C's own 2019/2010 crown cover of >5 m stems (the SAME population as F).\n")
@printf("a_fpc    = the C's `a_fpc` 2019/2010 from the SINGLE-CELL re-run — a different population AND a\n")
@printf("           different realisation; printed only so the substitution stays visible (ADR 0041/0060).\n")
@printf("REINIT_c/C_growth ~ FREE_c/C_live  =>  the drift is compounded per-year physics.\n")
@printf("FREE_c/C_live much larger          =>  the free-running loop amplifies out of its own state.\n")

# ── PART 5 — where in the size distribution the error lives ──────────────────────────────────────────
@printf("\n--- PART 5: the paired growth error by STARTING HEIGHT class (alignment A, pooled years) ---\n")
@printf("%-22s %14s %10s %10s %10s\n", "cell", "height class", "n", "dagb_F/C", "dh_F/C")
const HCLASS = ((0.0, 8.0), (8.0, 15.0), (15.0, 25.0), (25.0, 1.0e9))
for k in eachindex(names)
    pairs = reinitA[k].pairs
    for (lo, hi) in HCLASS
        py = [p for p in pairs if lo <= p.h0 < hi]
        isempty(py) && continue
        dF = sum(p.fa - p.a0 for p in py); dC = sum(p.ca - p.a0 for p in py)
        dFh = sum(p.fh - p.h0 for p in py); dCh = sum(p.ch - p.h0 for p in py)
        @printf(
            "%-22s %14s %10d %10.3f %10.3f\n", (lo == 0.0 ? names[k] : ""),
            hi > 1.0e8 ? ">25 m" : @sprintf("%.0f-%.0f m", lo, hi), length(py),
            abs(dC) > 1.0e-9 ? dF / dC : NaN, abs(dCh) > 1.0e-9 ? dFh / dCh : NaN
        )
    end
end

# ── PART 6 — GPP, the flux the growth is made of, on the same two arms ───────────────────────────────
@printf("\n--- PART 6: annual mean tree GPP (gC/m2/day), REINIT vs FREE — is the flux drifting too? ---\n")
@printf("%-22s %-8s%s\n", "cell", "arm", join((@sprintf("%7d", y) for y in Y0:Y1)))
for k in eachindex(names)
    @printf("%-22s %-8s%s\n", names[k], "reinit", join((@sprintf("%7.3f", v) for v in reinitA[k].gpp)))
    @printf("%-22s %-8s%s\n", "", "free", join((@sprintf("%7.3f", v) for v in freearm[k].gpp)))
    @printf("%-22s %-8s%s\n", "", "C", join((@sprintf("%7.3f", cgpp(names[k], y)) for y in Y0:Y1)))
end
@printf("\nREINIT's GPP is F's flux on the C's OWN stand each year, so it carries no structural drift.\n")
@printf("FREE − REINIT is what the canopy accumulation adds to the flux. ⚠ the C row is `d_gpp −\n")
@printf("d_grass_gpp` from the SINGLE-CELL re-run (a different population AND, at the Amazon, a\n")
@printf("different realisation — PART 4's `a_fpc` caveat applies to it too).\n")

# ── PART 7 — WHERE THE ERROR ENTERS: assimilate IN vs biomass OUT ────────────────────────────────────
# The decisive attribution, and it needs no new run. F's per-year growth error (PART 3) can enter at
# exactly two places, and they need different fixes:
#   (a) TOO MUCH ASSIMILATE — F's NPP into allocation is wrong (photosynthesis, or autotrophic
#       respiration, which is where a temperature-dependent error would live), or
#   (b) THE RIGHT ASSIMILATE, THE WRONG PLACE — F's allocation/turnover converts a correct NPP into the
#       wrong biomass increment.
# The C emits per-stem annual NPP in the `ind` table (`pft->anpp`; note the writer's `gpp` column is
# also NPP — the agpp+=npp bug, CLAUDE.md §3), summed here over exactly the stems F was handed. F's
# `FToS.bm_inc` is the same quantity by construction: the annual per-m² assimilate handed to allocation.
# So `bm_inc_F/C` isolates (a) and `dagb / bm_inc` (the fraction of the year's assimilate that ends up
# as standing above-ground biomass) isolates (b), on BOTH sides.
@printf("\n--- PART 7: ASSIMILATE IN vs BIOMASS OUT — where does the growth error enter? ---\n")
@printf(
    "%-22s %10s %10s %9s %10s %10s %9s\n",
    "cell", "bmi_F", "bmi_C", "bmi_F/C", "keep_F", "keep_C", "keep_F/C"
)
function carbon_panel(arm, k)
    name = names[k]
    pairs = arm.pairs
    bf = Float64[]; bc = Float64[]; kf = Float64[]; kc = Float64[]
    for (yi, y) in enumerate(Y0:Y1)
        py = [p for p in pairs if p.year == y]
        (isempty(py) || isnan(arm.bm_inc[yi])) && continue
        # the C's tree NPP over the SAME stems, per m² — the `ind` npp column is a per-m² cohort
        # quantity exactly like its `agb` (both are `pft->` totals at `nind = 1/patcharea`), which is
        # why the reconstruction divides `agb` by `nind` to get a per-individual pool.
        np = length(readcanopy_patches(joinpath(INDDIR, "M_individuals_$(name)_$(y - 1).csv"))[2])
        cnpp = sum(p.cnpp for p in py) / np
        dF = sum((p.fa - p.a0) * p.nind for p in py) / np
        dC = sum((p.ca - p.a0) * p.nind for p in py) / np
        push!(bf, arm.bm_inc[yi]); push!(bc, cnpp)
        push!(kf, dF / arm.bm_inc[yi]); push!(kc, dC / cnpp)
    end
    return (; bf = mean(bf), bc = mean(bc), kf = mean(kf), kc = mean(kc))
end
for k in eachindex(names)
    c = carbon_panel(reinitA[k], k)
    @printf(
        "%-22s %10.1f %10.1f %9.3f %10.3f %10.3f %9.3f\n", names[k],
        c.bf, c.bc, c.bf / c.bc, c.kf, c.kc, c.kf / c.kc
    )
end
@printf("\nbmi_* = annual assimilate handed to allocation, gC/m2/yr (F: `FToS.bm_inc`; C: Σ per-stem `npp`\n")
@printf("        over the same stems). `bmi_F/C` ~ 1 => F's carbon INPUT is right and the error is in\n")
@printf("        allocation/turnover; far from 1 => the error is upstream, in photosynthesis or Ra.\n")
@printf("keep_* = Σ(above-ground biomass increment) / that year's assimilate — the fraction retained as\n")
@printf("        standing AGB. `keep_F/C` is the allocation/turnover half of the error, with the input\n")
@printf("        difference divided out.\n")


# ── PART 8 — THE CANDIDATE CAUSE, TESTED AS AN ARM (no code change) ──────────────────────────────────
# `respcoeff` is the maintenance-respiration coefficient, and it is PER-PFT in the C: 0.2 for the
# tropical broadleaved evergreen tree, 1.2 for all six temperate/boreal trees. F carries ONE scalar
# (1.2, beech's) for every tree in every cell. Prediction, made before this table was produced: at the
# two cells whose stems are id 0 (Sahel, Amazon) F over-respires by 6× and its NPP should go NEGATIVE,
# while the three temperate/boreal cells already have the right coefficient and must not move at all.
# Arm R2 substitutes the cell's own sapwood-weighted coefficient and changes NOTHING else.
@printf("\n--- PART 8: ARM R2 — the C's own per-cell `respcoeff` substituted, everything else identical ---\n")
@printf(
    "%-22s %8s %9s %9s %9s %9s %9s %9s\n",
    "cell", "respc", "bmi_F", "bmi_F_R2", "bmi_C", "F/C", "R2/C", "dagb_R2/C"
)
for k in eachindex(names)
    cA = carbon_panel(reinitA[k], k)
    c2 = carbon_panel(reinitR2[k], k)
    dr = median(
        [
            (
                    py = [p for p in reinitR2[k].pairs if p.year == y];
                    isempty(py) ? NaN : sum(p.fa - p.a0 for p in py) / sum(p.ca - p.a0 for p in py)
                ) for y in Y0:Y1
        ]
    )
    @printf(
        "%-22s %8.3f %9.1f %9.1f %9.1f %9.3f %9.3f %9.3f\n", names[k], RESPC[k][1],
        cA.bf, c2.bf, cA.bc, cA.bf / cA.bc, c2.bf / cA.bc, dr
    )
end
@printf("\nrespc = the cell's sapwood-weighted mean of the C's per-PFT `respcoeff`. F uses ONE value for\n")
@printf("every tree everywhere: 1.2, the ACTIVE calibrated set's (`tebs_params`, fdiff.jl:1287) — beech's.\n")
@printf("So R2 is a NO-OP at the three temperate/boreal/mediterranean cells, which is the arm's control.\n")
@printf("PFT sapwood shares per cell (ids 0..6), so a mixed cell is not read as if it had one value:\n")
for k in eachindex(names)
    @printf("%-22s %s\n", names[k], join((@sprintf("%6.3f", v) for v in RESPC[k][2])))
end
@printf("\n⚠ R2 is a DIAGNOSTIC ARM, not a proposed default: one scalar cannot represent a mixed-PFT cell,\n")
@printf("and the real fix is per-cohort PFT parameters in `FDiffFastCore` (which needs `fc.pft_ids` —\n")
@printf("already the standing requirement for `trait_mortality`, STATE item 3 / M5). That fix is arm P.\n")

# ── PART 9 — ARM P: THE CODE CHANGE, SCORED AGAINST ITS PRE-REGISTERED CRITERION ─────────────────────
# ADR 0126 wires per-cohort PFT parameters through `FDiffFastCore` (`per_pft_params=true` + the C's own
# `Type` per stem): each cohort runs its own `respcoeff` (0.2 tropical / 1.2 temperate+boreal), `gmin`
# (0.3-1.6), turnover (leaf/root residence 1/2/4 yr, sapwood 25/30 yr), crown allometry (angiosperm vs
# gymnosperm) and Beer-Lambert `k_beer` (0.45 needleleaved / 0.59 broadleaved), and its own photosynthesis
# temperature optimum (15/25 °C boreal vs 20/30). Beech is unchanged BY CONSTRUCTION, so Hainich — 99.4 %
# id 3 by sapwood — is this arm's own control that it changes only what it should.
#
# THE CRITERION, written into ADR 0125 §7.3 BEFORE this arm was run and quoted here verbatim so it cannot
# be re-read after the fact:
#     pass = `bmi_F/C` lands in [0.8, 1.25] at all five cells AND the paired Σ`dagb` F/C moves toward 1
#            at all five, with NO committed baseline moving while the feature is off.
# The third clause is checked by the test suite, not here (the feature is off by default and a beech-only
# stand is byte-identical — `test/testitems/per_pft_params_tests.jl`).
@printf("\n--- PART 9: ARM P — per-cohort PFT parameters (ADR 0126), vs the PRE-REGISTERED criterion ---\n")
@printf(
    "%-22s %9s %9s %9s %8s %8s %10s %10s %8s\n",
    "cell", "bmi_A", "bmi_P", "bmi_C", "A/C", "P/C", "dagb_A/C", "dagb_P/C", "verdict"
)
function dagb_ratio(arm)
    return median(
        [
            (
                    py = [p for p in arm.pairs if p.year == y];
                    isempty(py) ? NaN : sum(p.fa - p.a0 for p in py) / sum(p.ca - p.a0 for p in py)
                ) for y in Y0:Y1
        ]
    )
end
pass_bmi = true; pass_dagb = true
for k in eachindex(names)
    cA = carbon_panel(reinitA[k], k)
    cP = carbon_panel(reinitP[k], k)
    rA = cA.bf / cA.bc; rP = cP.bf / cA.bc
    dA = dagb_ratio(reinitA[k]); dP = dagb_ratio(reinitP[k])
    ok_b = 0.8 <= rP <= 1.25
    ok_d = abs(dP - 1) <= abs(dA - 1) + 1.0e-12
    global pass_bmi &= ok_b
    global pass_dagb &= ok_d
    @printf(
        "%-22s %9.1f %9.1f %9.1f %8.3f %8.3f %10.3f %10.3f %8s\n", names[k],
        cA.bf, cP.bf, cA.bc, rA, rP, dA, dP, (ok_b ? "" : "bmi!") * (ok_d ? "" : "dagb!")
    )
end
@printf(
    "\nPRE-REGISTERED VERDICT: bmi_P/C in [0.8,1.25] at all five = %s;  Σdagb moved toward 1 at all five = %s\n",
    pass_bmi ? "PASS" : "FAIL", pass_dagb ? "PASS" : "FAIL"
)
@printf("=> ADR 0125 §7.3 criterion: %s\n", (pass_bmi && pass_dagb) ? "PASS" : "FAIL")
@printf("A = the shipped single beech set (the published rung-3 arm); P = per-cohort PFT parameters.\n")
@printf("`bmi_C` is the C's own Σ per-stem NPP over the SAME stems and is identical in both arms.\n")
@printf("⚠ Hainich is 99.4 %% beech by sapwood, so P ≡ A there by construction — an unmoved Hainich row is\n")
@printf("this arm's control, NOT evidence that the change does nothing.\n")

# Per-cell PFT composition + which of the two arms' crown covers is on which Beer-Lambert basis, so a
# mixed cell is never read as if it had one parameter set (the R2 arm's lesson, PART 8).
@printf("\n--- PART 9b: what P actually changed at each cell (sapwood-weighted over ids 0..6) ---\n")
@printf("%-22s %8s %8s %8s %8s %8s\n", "cell", "respc", "k_beer", "gmin", "t_phot_hi", "turn_root")
for k in eachindex(names)
    w = RESPC[k][2]                                   # sapwood shares over ids 0..6
    wm(f) = sum(w[i] * f(i - 1) for i in 1:7)
    @printf(
        "%-22s %8.3f %8.3f %8.3f %8.1f %8.3f\n", names[k],
        wm(i -> FDiff.pft_respparams(i).respcoeff), wm(i -> FDiff.pft_allometry(i).k_beer),
        wm(i -> FDiff.pft_canopy_traits(i).gmin),
        wm(i -> FDiff.pft_tempstressparams(i).temp_photos_high),
        wm(i -> FDiff.pft_allocparams(i).turnover_root)
    )
end
@printf("F's single shipped set, for comparison: respc 1.200  k_beer 0.590  gmin 1.000  t_phot_hi 30.0  turn_root 1.000\n")
@printf("⚠ arm P's crown cover is computed with each stem's OWN `k_beer` (the C's own basis, the roster's\n")
@printf("`k_beer` column); arms A/B/R2 keep the shared 0.590 so their published numbers reproduce.\n")

# ── PART 9c — WHICH PARAMETER DID IT? The single-variable attribution arms ────────────────────────────
# Arm P moves nine parameters at once. Where it improves a cell that is fine; where it makes one WORSE the
# only useful question is which parameter, and a nine-variable arm cannot answer it. Each arm below takes
# exactly ONE per-PFT field from the stem's own PFT and beech's for all the rest. ⚠ They do NOT sum to P:
# the daily canopy is nonlinear and `:alloc`/`:allom` act through the next year's pools. Read them as
# attributions of SIGN and rough size, never as a decomposition.
@printf("\n--- PART 9c: SINGLE-VARIABLE ATTRIBUTION — bmi_F/C per arm (A = the shipped beech set) ---\n")
@printf("%-22s %7s", "cell", "A")
for sub in SUBSETS
    @printf(" %8s", sub)
end
@printf(" %8s\n", "P(all)")
for k in eachindex(names)
    cA = carbon_panel(reinitA[k], k)
    @printf("%-22s %7.3f", names[k], cA.bf / cA.bc)
    for sub in SUBSETS
        @printf(" %8.3f", carbon_panel(reinitS[sub][k], k).bf / cA.bc)
    end
    @printf(" %8.3f\n", carbon_panel(reinitP[k], k).bf / cA.bc)
end
@printf("\n--- and the same arms on the paired per-stem growth, Σdagb F/C (year-median) ---\n")
@printf("%-22s %7s", "cell", "A")
for sub in SUBSETS
    @printf(" %8s", sub)
end
@printf(" %8s\n", "P(all)")
for k in eachindex(names)
    @printf("%-22s %7.3f", names[k], dagb_ratio(reinitA[k]))
    for sub in SUBSETS
        @printf(" %8.3f", dagb_ratio(reinitS[sub][k]))
    end
    @printf(" %8.3f\n", dagb_ratio(reinitP[k]))
end
@printf("\n⚠ READ EVERY COLUMN AGAINST `phen`, NOT AGAINST `A`. Arm A does not pass `pft_ids` at all, so all of\n")
@printf("its trees run BEECH's GSI phenology; every per-PFT arm passes the real ids and therefore carries the\n")
@printf("per-PFT phenology as well. `phen` is that change ALONE (bundle and templates all beech), i.e. the\n")
@printf("baseline each one-field arm should be differenced against. `pft_ids` predates ADR 0126 — the\n")
@printf("phenology column is a gap arm A had, not something the per-PFT parameters introduced.\n")
@printf("A column EQUAL to `phen` means that parameter is beech's at that cell already (the arm's own\n")
@printf("control). 1.000 is the target. `resp` = respcoeff · `tstress` = temp_photos/temp_co2 · `kbeer` =\n")
@printf("the Beer-Lambert extinction · `gmin` = min canopy conductance · `alloc` = turnover · `allom` = the\n")
@printf("crown/height coefficients · `traits` = intc/albedo_stem/albedo_litter/snowcanopyfrac.\n")

@printf("\nDONE — the verdict is PART 9 + 9c (the change and which parameter did what), read with PART 7/8\n")
@printf("(why), PART 2's alignment and PART 1's gate.\n")
