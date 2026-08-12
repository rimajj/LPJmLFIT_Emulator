#!/usr/bin/env julia
# ── RUNG 3 / the `keep` GAP — is F's surplus above-ground growth the C's BELOW-GROUND SAPWOOD SINK? ────
#
# THE RESIDUAL. ADR 0125 §PART 7 split F's paired per-stem growth error into "how much assimilate comes
# in" (`bmi_F/C`) and "how much of it ends up as standing above-ground biomass" (`keep = ΣΔagb / bmi`).
# At the two cells where the input is already right the RETENTION is not:
#     boreal   bmi 1.05×   keep_F 0.465 vs keep_C 0.251  = 1.85×
#     Hainich  bmi 1.24×   keep_F 0.549 vs keep_C 0.368  = 1.49×
# ADR 0126 wired the per-PFT parameters and the overshoot SURVIVED (Σ`dagb` F/C 1.45-1.48 at exactly those
# two cells), so it is not a parameter. `EXECUTION_PLAN.md` rung 3 cannot exit until it is fixed or bounded.
#
# ── THE REFERENCE BASIS (`residual-diagnosis` §1), read off the C source, not off the column names ─────
# Both sides' columns are called `agb` and `vegc` and they are NOT the same pool sets:
#   C  `agb`  = (leaf + heartwood + sapwood − debt + excess)·nind − turn_litt.leaf   [`agb_tree.c:25`,
#               `tree.h:259` `agb_tree_sum`]                                          gC/m²
#   C  `vegc` = (leaf + root + heartwood + sapwood + SAPWOOD_BG + HEARTWOOD_BG − debt + excess)·nind
#               − turn_litt.leaf − turn_litt.root + fruit  [`veg_sum_tree.c:25`, `tree.h:257`]   gC/m²
#   F  `agb_ind`  = leaf_c + sapwood_c + heartwood_c                                  gC/individual
#   F  `vegc_ind` = leaf_c + sapwood_c + heartwood_c + root_c                          gC/individual
# ⇒ the C's below-ground bucket `vegc − agb` holds root + sapwood_bg + heartwood_bg; F's holds root ONLY.
# That asymmetry is the hypothesis under test, and every number below is printed with it stated.
#
# ── THE HYPOTHESIS (falsifiable, stated before the run) ───────────────────────────────────────────────
# H: the `keep` overshoot is F's MISSING BELOW-GROUND SAPWOOD SINK. The C computes a C_LATERAL root-sapwood
#    demand from each tree's own sapwood cross-section and root profile and DEDUCTS it from `bm_inc_ind`
#    BEFORE the leaf/root/sapwood split (`allocation_tree.c:206-209` sets `tinc_ind.sapwood_bg`, `:268-271`
#    subtracts it). F's `grow_individual` carries `sapwood_bg_c` through UNCHANGED (`fdiff.jl:2460-2467`,
#    the deferred docs/notes/sapwood_bg_design.md §5.4 step), and its `sap_inc = bm_net − leaf_inc −
#    root_inc` is a RESIDUAL — so the whole undeducted demand lands in ABOVE-GROUND sapwood, which is in
#    `agb_ind`. F also skips the pool's maintenance respiration unless the pool is seeded (§8.1 landed the
#    seed + the `autotrophic_respiration` term as opt-in; the probe arms below switch it on).
#
# PREDICTIONS, each killable by one column of PART 2/PART 3:
#   P1  F's TOTAL retention `Δvegc/bmi` is much CLOSER to the C's than its above-ground `Δagb/bmi` is —
#       i.e. the SPLIT is wrong, not the total. If F's total retention is also ~1.5× the C's, the defect is
#       turnover/reproduction and this whole route is dead.
#   P2  the C's below-ground retention `Δ(vegc−agb)/bmi` exceeds F's `Δroot/bmi` by ≈ the amount F's
#       `Δagb/bmi` exceeds the C's.
#   P3  the C_LATERAL demand INCREMENT, recomputed per stem from its own state with the already-ported
#       `FDiff.reconstruct_sapwood_bg`, is ≈ `(keep_F − keep_C)·bmi_C`. This is the quantitative one: if the
#       demand is an order of magnitude too small, seeding and growing the pool cannot close the gap.
#
# ARMS (`slow = nothing`, 25-patch ensemble, alignment A = roster(y−1) + year-y forcing → roster(y)):
#   A    the published rung-3 arm — beech parameters for every tree, no `pft_ids`, `sapwood_bg_c = 0`.
#        ⚠ Its `bmi`/`keep` panel is this probe's OWN BASIS GATE: it is printed against ADR 0125's
#        published numbers and the run reports FAIL if it does not reproduce them.
#   Abg  A + the below-ground pool SEEDED (`reconstruct_sapwood_bg`). Seeding alone switches on the pool's
#        maintenance respiration (`individual_from_pools` carries `sapwood_bg_c` into `Individual`), so
#        `Abg − A` is the RESPIRATION half of the sink with no `src/` change at all.
#   P    per-cohort PFT parameters + the C's own `pft_ids` (ADR 0126) — the configuration a fix would ship
#        against, and the one that already fixes the two tropical cells' carbon input.
#   Pbg  P + the seed.
# The GROWTH half (deducting the demand from `bm_inc` before allocation) needs the `src/` change and is NOT
# in this probe — PART 3 prices it instead, so the decision to write it is made on a measurement.
#
# Run (CLAUDE.md §2 — never the login node):
#   TIME=01:00:00 scripts/sbatch_julia.sh M-sapbg --project=. scripts/biome_sapwood_bg_probe.jl
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

# The ACTIVE calibrated set with `wscal_leafon` explicit (ADR 0051/0059) — never a bare `FDiffParams()`.
# Byte-for-byte the same construction as `biome_canopy_growth_probe.jl::mkparams`, which is what makes
# PART 1's gate against that probe's published panel a real test rather than a coincidence.
function mkparams()
    p = FDiff.tebs_params(Float64)
    w = p.water
    fns = fieldnames(typeof(w))
    nt = NamedTuple{fns}(map(f -> getfield(w, f), fns))
    w2 = typeof(w)(; merge(nt, (; wscal_leafon = true))...)
    return FDiffParams{Float64}(p.photo, p.tstress, w2, p.resp, p.allom, p.nlambda, p.ω)
end

const PARAMS = mkparams()

# ── readers (deliberately a SECOND, independent reader of the same fixtures as
# `biome_canopy_growth_probe.jl` — ADR 0060's "cross-check the corrected reference through a second
# independent reader"; PART 1's gate is what licenses it) ─────────────────────────────────────────────
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
    return FDiff.hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)
end

"""
One patch's `(pools, tmpls, ids, types)` from a roster file's rows.

`seed_bg = true` fills `TreePools.sapwood_bg_c` with the C's own C_LATERAL demand at that stem's state
(`FDiff.reconstruct_sapwood_bg`, the verbatim `allocation_tree.c:163-189` port). That single field is what
switches the pool's maintenance respiration on: `individual_from_pools` carries it into
`Individual.c_sapwood_bg` and `autotrophic_respiration` adds the phen-gated `sapwood_bg/cn_sapwood` term.
With `seed_bg = false` the 10-argument constructor leaves it 0 ⇒ byte-identical to the published arm.
"""
function build_patch(ind, rows, soil; tmpl_pft::Bool = false, seed_bg::Bool = false)
    v(k, r) = parse(Float64, ind[k][r])
    ty(r) = parse(Int, ind["type"][r])
    function mkpool(r)
        heart = max(v("agb", r) / v("nind", r) - v("leaf_c", r) - v("sapwood_c", r), 0.0)
        sbg = seed_bg ?
            FDiff.reconstruct_sapwood_bg(
                v("sapwood_c", r), v("height", r), v("wooddens", r), soil.rootdist, soil.soildepth
            ) : 0.0
        return TreePools{Float64}(
            v("leaf_c", r), v("sapwood_c", r), heart, v("root_c", r), sbg,
            v("height", r), v("crownarea", r), v("nind", r), v("sla", r), v("wooddens", r),
            0.0, 0.0, false
        )
    end
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
    return (
        [mkpool(r) for r in rows], [mktmpl(r) for r in rows],
        [parse(Int, ind["id"][r]) for r in rows], [ty(r) for r in rows],
    )
end

function readcanopy_patches(path, soil; tmpl_pft::Bool = false, seed_bg::Bool = false)
    ind = readcsv(path)
    v(k, r) = parse(Float64, ind[k][r])
    prows = Dict{Int, Vector{Int}}()
    for r in eachindex(ind["type"])
        (parse(Int, ind["type"][r]) <= 6 && v("height", r) > 0) &&
            push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
    end
    pk = sort(collect(keys(prows)))
    return Dict(
            p => build_patch(ind, prows[p], soil; tmpl_pft = tmpl_pft, seed_bg = seed_bg) for p in pk
        ), pk
end

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

"""
The C's own per-stem state, keyed `(name, year, patch, id)` — `(agb, vegc, npp, isdead)`, all gC/m².

`vegc` is the addition over `biome_canopy_growth_probe.jl`'s reader and it is the whole point: `vegc − agb`
is the C's below-ground bucket (root + sapwood_bg + heartwood_bg), against which F has only `root_c`.
"""
function read_targets()
    d = readcsv(joinpath(WORK, "M_stem_targets.csv"))
    t = Dict{NTuple{4, Any}, NTuple{4, Float64}}()
    for r in eachindex(d["name"])
        k = (String(d["name"][r]), parse(Int, d["Year"][r]), parse(Int, d["Patch"][r]), parse(Int, d["ID"][r]))
        t[k] = (
            parse(Float64, d["agb"][r]), parse(Float64, d["vegc"][r]),
            parse(Float64, d["npp"][r]), parse(Float64, d["isdead"][r]),
        )
    end
    return t
end

function run_one_year!(state, clo, pools, tmpls, soil, lat, forc; per_pft::Bool = false, types = nothing)
    core = per_pft ?
        FDiffFastCore(pools, tmpls, soil, lat; params = PARAMS, pft_ids = types, per_pft_params = true) :
        FDiffFastCore(pools, tmpls, soil, lat; params = PARAMS)
    bc_f = LPJmLFITEmulator.stand_structure_tof(core)
    for f in forc
        LPJmLFITEmulator.couple_day!(core, clo, state, bc_f, f; feedback = true)
    end
    ftos = LPJmLFITEmulator.annual_step!(core, state)
    return core.pools, Float64(ftos.bm_inc)
end

# ── one paired stem-year ─────────────────────────────────────────────────────────────────────────────
struct Pair2
    name::String; year::Int; nind::Float64
    fa0::Float64; fa1::Float64          # F's agb_ind, start and end        (gC/individual)
    fv0::Float64; fv1::Float64          # F's vegc_ind (incl root), s/e     (gC/individual)
    ca0::Float64; ca1::Float64          # the C's own agb, start and end    (gC/m²)
    cv0::Float64; cv1::Float64          # the C's own vegc, start and end   (gC/m²)
    cnpp::Float64                       # the C's own annual NPP of this stem (gC/m²/yr)
    d0::Float64; d1::Float64            # the C_LATERAL demand at F's start / end state (gC/individual)
end

const CELLS = readcsv(joinpath(REFDIR, "M_cells.csv"))
const NAMES = String.(CELLS["name"])
const LATS = fcol(CELLS, "lat")
const TARGETS = read_targets()

"""
One arm at one cell: the paired per-stem rows plus the per-year ensemble `bm_inc` and patch count.

`seed_bg` seeds the below-ground pool (⇒ its maintenance respiration runs); `per_pft` runs each cohort's
own PFT parameters and phenology. The demand `d0`/`d1` is ALWAYS computed, in every arm, so a `keep`
prediction and the arm that would realise it are read off the same run.
"""
function arm(k::Int; per_pft::Bool = false, seed_bg::Bool = false)
    name = NAMES[k]
    forc, tair0 = forcings_by_year(name)
    soil = readsoil(joinpath(REFDIR, "M_soilcolumn_$(name).txt"))
    rows = Pair2[]
    bmi = fill(NaN, NYEAR); npatch = zeros(Int, NYEAR)
    states = Dict{Int, Any}(); clos = Dict{Int, Any}()
    dem(t) = FDiff.reconstruct_sapwood_bg(t.sapwood_c, t.height, t.wooddens, soil.rootdist, soil.soildepth)
    for (yi, y) in enumerate(Y0:Y1)
        src = joinpath(INDDIR, "M_individuals_$(name)_$(y - 1).csv")
        (isfile(src) && haskey(forc, y)) || continue
        patches, pk = readcanopy_patches(src, soil; tmpl_pft = per_pft, seed_bg = seed_bg)
        acc = 0.0
        for p in pk
            pools, tmpls, ids, types = patches[p]
            st = get!(states, p, SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER)))
            cl = get!(clos, p, SEBEnergyClosure(; t_soil0 = tair0))
            grown, b = run_one_year!(st, cl, pools, tmpls, soil, LATS[k], forc[y]; per_pft = per_pft, types = types)
            acc += b
            for i in eachindex(ids)
                k1 = (name, y, p, ids[i]); k0 = (name, y - 1, p, ids[i])
                (haskey(TARGETS, k1) && haskey(TARGETS, k0)) || continue
                (ca1, cv1, cnpp, _) = TARGETS[k1]
                (ca0, cv0, _, _) = TARGETS[k0]
                g = grown[i]; s0 = pools[i]
                push!(
                    rows, Pair2(
                        name, y, s0.nind,
                        FDiff.agb_ind(s0), FDiff.agb_ind(g), FDiff.vegc_ind(s0), FDiff.vegc_ind(g),
                        ca0, ca1, cv0, cv1, cnpp, dem(s0), dem(g)
                    )
                )
            end
        end
        bmi[yi] = acc / length(pk); npatch[yi] = length(pk)
    end
    return (; rows, bmi, npatch, name)
end

"""
Per-YEAR, per-m² ensemble channels for one arm at one cell, plus BOTH definitions of `keep`.

⚠ TWO DEFINITIONS OF `keep` EXIST AND THEY DISAGREE (ADR 0111 §9's "keep exactly ONE definition" trap,
met head-on). `biome_canopy_growth_probe.jl::carbon_panel` — the source of ADR 0125's published panel —
forms `keep` as the **mean of the per-year ratios** and builds the C's own increment against F's
RECONSTRUCTED start state (`p.ca − p.a0`, i.e. the C's year-y `agb` minus `FDiff.agb_ind(s0)`). This
probe's natural form is the **ratio of the year means** against the C's OWN two rows (`ca1 − ca0`). Both
are computed here and both are printed: `_pub` reproduces the published definition exactly (that is what
PART 1's gate tests), `_abs` is the definition every absolute-flux statement below is on.
The two differ for two reasons, and PART 1 separates them:
  * a mean of ratios ≠ a ratio of means whenever the per-year assimilate varies (and it EXPLODES where
    the assimilate changes sign, which is arm A at the two hot cells);
  * `p.a0` is the reconstruction `max(agb/nind − leaf_c − sapwood_c, 0)` + leaf + sapwood, so wherever
    that `max` CLAMPS, `a0·nind ≠ agb_C(y−1)` and the published `keep_C` is not a pure C-side quantity.
    The clamp residual is printed as `recon` in PART 1.
"""
function panel(a)
    yy = Int[]
    bf = Float64[]; bc = Float64[]
    dagbF = Float64[]; dagbC = Float64[]; dagbC_pub = Float64[]; recon = Float64[]
    dbelF = Float64[]; dbelC = Float64[]
    dD = Float64[]; pool0 = Float64[]
    for (yi, y) in enumerate(Y0:Y1)
        isnan(a.bmi[yi]) && continue
        py = [p for p in a.rows if p.year == y]
        isempty(py) && continue
        np = a.npatch[yi]
        push!(yy, y)
        push!(bf, a.bmi[yi])
        push!(bc, sum(p.cnpp for p in py) / np)
        push!(dagbF, sum((p.fa1 - p.fa0) * p.nind for p in py) / np)
        push!(dagbC, sum(p.ca1 - p.ca0 for p in py) / np)
        push!(dagbC_pub, sum(p.ca1 - p.fa0 * p.nind for p in py) / np)
        push!(recon, sum(p.ca0 - p.fa0 * p.nind for p in py) / np)
        push!(dbelF, sum(((p.fv1 - p.fa1) - (p.fv0 - p.fa0)) * p.nind for p in py) / np)
        push!(dbelC, sum((p.cv1 - p.ca1) - (p.cv0 - p.ca0) for p in py) / np)
        push!(dD, sum((p.d1 - p.d0) * p.nind for p in py) / np)
        push!(pool0, sum(p.d0 * p.nind for p in py) / np)
    end
    m(v) = isempty(v) ? NaN : mean(v)
    return (;
        n = length(yy),
        bf = m(bf), bc = m(bc), dagbF = m(dagbF), dagbC = m(dagbC), recon = m(recon),
        dbelF = m(dbelF), dbelC = m(dbelC), dD = m(dD), pool0 = m(pool0),
        # the PUBLISHED definition: mean of the per-year ratios, C side against F's reconstructed start
        keepF_pub = m(dagbF ./ bf), keepC_pub = m(dagbC_pub ./ bc),
        # the ABSOLUTE definition: ratio of the year means, C side against the C's own two rows
        keepF_abs = m(dagbF) / m(bf), keepC_abs = m(dagbC) / m(bc),
        lossF = m(bf) - m(dagbF) - m(dbelF), lossC = m(bc) - m(dagbC) - m(dbelC),
    )
end

# ── run the arms ─────────────────────────────────────────────────────────────────────────────────────
@printf("=== THE `keep` GAP — is F's surplus above-ground growth the C's BELOW-GROUND SAPWOOD SINK? ===\n")
@printf("(rung 3; 5 cells, %d-%d, alignment A, slow=nothing, 25-patch ensemble)\n\n", Y0, Y1)
flush(stdout)

armA = [arm(k) for k in eachindex(NAMES)]
@printf("arm A   (published basis: beech everywhere, sapwood_bg = 0) done\n"); flush(stdout)
armAbg = [arm(k; seed_bg = true) for k in eachindex(NAMES)]
@printf("arm Abg (A + the below-ground pool seeded => its maintenance respiration runs) done\n"); flush(stdout)
armP = [arm(k; per_pft = true) for k in eachindex(NAMES)]
@printf("arm P   (per-cohort PFT parameters + the C's own pft_ids, ADR 0126) done\n"); flush(stdout)
armPbg = [arm(k; per_pft = true, seed_bg = true) for k in eachindex(NAMES)]
@printf("arm Pbg (P + the seed) done\n\n"); flush(stdout)

pA = [panel(a) for a in armA]
pAbg = [panel(a) for a in armAbg]
pP = [panel(a) for a in armP]
pPbg = [panel(a) for a in armPbg]

# ── PART 1 — THE BASIS GATE ──────────────────────────────────────────────────────────────────────────
# This probe reads the same fixtures as `biome_canopy_growth_probe.jl` through its OWN readers, so before
# any new number is interpreted it must reproduce the published panel it extends (`residual-diagnosis` §3:
# if the harness cannot reproduce a number you already trust, fix the harness first). The gate is on the
# PUBLISHED definition; the `_abs` columns beside it are what the rest of this probe uses, and the two
# being different is a finding about the published number, not a defect in this reader.
const PUB = Dict(          # ADR 0125 §PART 7, arm A: (bmi_F, bmi_C, keep_F, keep_C)
    "boreal_siberia" => (198.0, 188.8, 0.465, 0.251),
    "temperate_hainich" => (606.0, 489.0, 0.549, 0.368),
    "mediterranean_iberia" => (644.2, 236.2, 0.602, 0.269),
    "semiarid_sahel" => (-83.8, 183.2, 0.35, 0.493),
    "tropical_amazon" => (-223.2, 1072.5, 0.143, 0.347),
)
@printf("--- PART 1: BASIS GATE — arm A against ADR 0125's published panel (published definition) ---\n")
@printf(
    "%-22s %8s %8s %8s %8s %9s %9s %9s %9s %8s %5s\n",
    "cell", "bmi_F", "pub", "bmi_C", "pub", "keepF_pub", "pub", "keepC_pub", "pub", "recon", "gate"
)
gate_ok = true
for k in eachindex(NAMES)
    c = pA[k]
    (pbf, pbc, pkf, pkc) = PUB[NAMES[k]]
    ok = all(
        abs(x - y) <= max(0.005 * abs(y), 0.2) for
            (x, y) in ((c.bf, pbf), (c.bc, pbc), (1000 * c.keepF_pub, 1000 * pkf), (1000 * c.keepC_pub, 1000 * pkc))
    )
    global gate_ok &= ok
    @printf(
        "%-22s %8.1f %8.1f %8.1f %8.1f %9.3f %9.3f %9.3f %9.3f %8.2f %5s\n",
        NAMES[k], c.bf, pbf, c.bc, pbc, c.keepF_pub, pkf, c.keepC_pub, pkc, c.recon, ok ? "ok" : "FAIL"
    )
end
@printf("GATE: %s   (0.5 %% relative, or 0.2 absolute on bmi / 0.0002 on keep)\n", gate_ok ? "PASS" : "FAIL")
@printf("recon = the mean per-year gap between the C's OWN start `agb` and F's RECONSTRUCTED start,\n")
@printf("        gC/m². Non-zero ⇒ the `max(agb/nind − leaf − sapwood, 0)` heartwood clamp binds and the\n")
@printf("        published `keep_C` is not a pure C-side quantity.\n")

@printf("\n--- PART 1b: THE TWO DEFINITIONS OF `keep`, side by side (never substitute one silently) ---\n")
@printf(
    "%-22s %9s %9s %9s %9s %9s %9s\n",
    "cell", "keepF_pub", "keepF_abs", "keepC_pub", "keepC_abs", "F pub/abs", "C pub/abs"
)
for k in eachindex(NAMES)
    c = pA[k]
    @printf(
        "%-22s %9.3f %9.3f %9.3f %9.3f %9.3f %9.3f\n", NAMES[k],
        c.keepF_pub, c.keepF_abs, c.keepC_pub, c.keepC_abs,
        c.keepF_pub / c.keepF_abs, c.keepC_pub / c.keepC_abs
    )
end
@printf("_pub = mean of the per-year ratios (the published form). _abs = ratio of the year means.\n")
@printf("They diverge most where the per-year assimilate changes SIGN — a mean of ratios is undefined as\n")
@printf("a retained FRACTION there. Everything below is on `_abs`, in absolute gC/m²/yr.\n")

# ── PART 2 — THE EXACT THREE-CHANNEL DECOMPOSITION (this is the result) ──────────────────────────────
# The carbon identity holds on BOTH sides by construction, with no model in it:
#     Δagb = assimilate − loss − Δbelow
# where `loss` is everything that left the plant (reproduction reserve + leaf/root litter + the C's debt
# payback) and `Δbelow` is the below-ground bucket. Differencing the two sides gives an EXACT, additive
# attribution of F's surplus above-ground growth:
#     Δagb_F − Δagb_C  =  (bmi_F − bmi_C)  −  (loss_F − loss_C)  −  (Δbel_F − Δbel_C)
# ⚠ `Δbelow` is NOT the same pool set on the two sides — C: root + sapwood_bg + heartwood_bg; F: root
# only — which is exactly the hypothesis under test, so the third term is where a missing sink appears.
@printf("\n--- PART 2: THE EXACT DECOMPOSITION OF F's SURPLUS ABOVE-GROUND GROWTH, gC/m²/yr ---\n")
@printf(
    "%-22s %8s %8s %8s %8s %7s %7s %9s %9s %9s %9s\n",
    "cell", "bmi_F", "bmi_C", "loss_F", "loss_C", "bel_F", "bel_C", "surplus", "=input", "+lower", "+nosink"
)
for k in eachindex(NAMES)
    c = pA[k]
    surplus = c.dagbF - c.dagbC
    t_in = c.bf - c.bc
    t_loss = -(c.lossF - c.lossC)
    t_bel = -(c.dbelF - c.dbelC)
    @printf(
        "%-22s %8.1f %8.1f %8.1f %8.1f %7.1f %7.1f %9.1f %9.1f %9.1f %9.1f\n", NAMES[k],
        c.bf, c.bc, c.lossF, c.lossC, c.dbelF, c.dbelC, surplus, t_in, t_loss, t_bel
    )
end
@printf("\nsurplus = Δagb_F − Δagb_C, the quantity `keep_F/keep_C` was a ratio-form of.\n")
@printf("=input  = bmi_F − bmi_C          (the ASSIMILATE error — ADR 0126's own item, not a new defect)\n")
@printf("+lower  = loss_C − loss_F        (F sheds too LITTLE to litter/reproduction — an allocation defect)\n")
@printf("+nosink = bel_C − bel_F          (the BELOW-GROUND sink F does not have — the new channel)\n")
@printf("The three add to `surplus` EXACTLY (a carbon identity, no model). A large `=input` column means\n")
@printf("the `keep` ratio was re-expressing the assimilate error, NOT an independent allocation defect:\n")
@printf("F's litter fluxes are POOL-driven (leaf/root shed) while its assimilate is not, so a too-large\n")
@printf("`bmi` raises the retained FRACTION even with a perfectly faithful allocation.\n")

# ── PART 3 — PRICING THE MISSING SINK ────────────────────────────────────────────────────────────────
# `bel_C` is measured, but the `ind` table cannot split it into root vs below-ground wood. The model side
# can: the C's below-ground WOOD (sapwood_bg + heartwood_bg together) grows by exactly the year's
# C_LATERAL top-up `tinc_sapwood_bg` — the turnover that moves sapwood_bg into heartwood_bg is internal to
# the bucket. So `dD`, the demand increment recomputed per stem from its own state with the already-ported
# `FDiff.reconstruct_sapwood_bg`, is the model's prediction of `bel_C − Δroot_C`, and Δroot is ~0 in a
# stand at steady state (leaf and fine-root residence are 1-4 yr, so both pools are replaced, not grown).
@printf("\n--- PART 3: THE C_LATERAL DEMAND vs the measured below-ground sink ---\n")
@printf(
    "%-22s %9s %8s %9s %9s %9s %11s\n",
    "cell", "pool0", "%agb0", "dD", "bel_C", "dD/bel_C", "nosink/surp"
)
for k in eachindex(NAMES)
    c = pA[k]
    a0 = sum(p.fa0 * p.nind for p in armA[k].rows if p.year == Y0) / max(armA[k].npatch[1], 1)
    @printf(
        "%-22s %9.1f %8.1f %9.2f %9.2f %9.3f %11.3f\n", NAMES[k],
        c.pool0, 100 * c.pool0 / max(a0, eps()), c.dD, c.dbelC, c.dD / c.dbelC,
        (c.dbelC - c.dbelF) / (c.dagbF - c.dagbC)
    )
end
@printf("\npool0 = the reconstructed below-ground sapwood pool of the stand F is handed, gC/m² (the design\n")
@printf("        note's 22.7 %% of above-ground sapwood at Hainich is the published cross-check).\n")
@printf("dD    = the demand INCREMENT over one year at F's OWN growth, gC/m²/yr. It is an OVER-estimate\n")
@printf("        wherever F grows too fast, and it is computed on the CELL-MEAN root profile while the C\n")
@printf("        uses each individual's own `beta_root` — both stated rather than corrected.\n")
@printf("dD/bel_C ~ 1 ⇒ the C's whole below-ground sink IS the C_LATERAL wood pool and a port would\n")
@printf("        reproduce it. nosink/surp = the share of F's surplus that channel could remove.\n")

# ── PART 4 — THE RESPIRATION HALF, MEASURED (arms Abg / Pbg) ─────────────────────────────────────────
@printf("\n--- PART 4: SEEDING THE POOL — the maintenance-respiration half, no `src/` change ---\n")
@printf(
    "%-22s %9s %9s %8s %9s %9s %8s %9s\n",
    "cell", "bmi_A", "bmi_Abg", "d%", "bmi_P", "bmi_Pbg", "d%", "bmi_C"
)
for k in eachindex(NAMES)
    a = pA[k]; ab = pAbg[k]; p = pP[k]; pb = pPbg[k]
    @printf(
        "%-22s %9.1f %9.1f %8.2f %9.1f %9.1f %8.2f %9.1f\n", NAMES[k],
        a.bf, ab.bf, 100 * (ab.bf - a.bf) / abs(a.bf), p.bf, pb.bf, 100 * (pb.bf - p.bf) / abs(p.bf), a.bc
    )
end
@printf("\n--- the four arms' SURPLUS above-ground growth, gC/m²/yr (0 = F grows the C's own increment) ---\n")
@printf(
    "%-22s %9s %9s %9s %9s %9s\n",
    "cell", "surp_A", "surp_Abg", "surp_P", "surp_Pbg", "dagb_C"
)
for k in eachindex(NAMES)
    a = pA[k]; ab = pAbg[k]; p = pP[k]; pb = pPbg[k]
    @printf(
        "%-22s %9.1f %9.1f %9.1f %9.1f %9.1f\n", NAMES[k],
        a.dagbF - a.dagbC, ab.dagbF - ab.dagbC, p.dagbF - p.dagbC, pb.dagbF - pb.dagbC, a.dagbC
    )
end
@printf("\nSeeding pays the pool's MAINTENANCE only; it does not GROW the pool, so it lowers the assimilate\n")
@printf("without moving the destination of what is left. It therefore closes the `=input` channel a little\n")
@printf("and the `+nosink` channel not at all — the growth deduction is the half PART 3 prices.\n")

# ── the COMMITTED table (the result, not the log) ────────────────────────────────────────────────────
# ADR 0127's numbers live here rather than only in a `logs/` file, so a later session can re-score an arm
# against them without re-deriving the basis. Regenerate by re-running this probe; the basis gate above
# is what licenses the file.
const OUTCSV = get(ENV, "OUT_CSV", joinpath(REFDIR, "M_growth_channel_decomposition.csv"))
open(OUTCSV, "w") do io
    println(io, "# F_diff's SURPLUS above-ground growth vs the LPJmL-FIT C oracle, decomposed EXACTLY into")
    println(io, "# three carbon channels (ADR 0127). Paired per stem by (Cell, Patch, ID), alignment A")
    println(io, "# (roster(y-1) + year-y forcing -> roster(y)), 25-patch ensemble, slow=nothing, 2010-2019")
    println(io, "# means of the per-year per-m2 ensemble sums. All fluxes gC/m2/yr.")
    println(io, "#   surplus = dagb_F - dagb_C = (bmi_F - bmi_C) + (loss_C - loss_F) + (bel_C - bel_F)")
    println(io, "#             = t_input        + t_loss          + t_nosink   (exact; a carbon identity)")
    println(io, "# arms: A = beech parameters for every tree, sapwood_bg = 0 (the ADR 0125/0126 basis)")
    println(io, "#       Abg = A + the below-ground pool seeded (its maintenance respiration runs)")
    println(io, "#       P   = per-cohort PFT parameters + the C's own pft_ids (ADR 0126)")
    println(io, "#       Pbg = P + the seed  (the most faithful configuration that exists today)")
    println(io, "# keepF_pub/keepC_pub reproduce ADR 0125 PART 7's published mean-of-per-year-ratios form;")
    println(io, "# keepF_abs/keepC_abs are the ratio-of-means. They are DIFFERENT statistics - see ADR 0127.")
    println(io, "# scripts/biome_sapwood_bg_probe.jl")
    println(
        io,
        "arm,cell,nyear,bmi_F,bmi_C,loss_F,loss_C,bel_F,bel_C,dagb_F,dagb_C,surplus," *
            "t_input,t_loss,t_nosink,demand_pool0,demand_incr,keepF_pub,keepC_pub,keepF_abs,keepC_abs"
    )
    for (tag, ps) in (("A", pA), ("Abg", pAbg), ("P", pP), ("Pbg", pPbg))
        for k in eachindex(NAMES)
            c = ps[k]
            @printf(
                io, "%s,%s,%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.6f,%.6f,%.6f,%.6f\n",
                tag, NAMES[k], c.n, c.bf, c.bc, c.lossF, c.lossC, c.dbelF, c.dbelC, c.dagbF, c.dagbC,
                c.dagbF - c.dagbC, c.bf - c.bc, c.lossC - c.lossF, c.dbelC - c.dbelF,
                c.pool0, c.dD, c.keepF_pub, c.keepC_pub, c.keepF_abs, c.keepC_abs
            )
        end
    end
end
@printf("\nwrote %s\n", OUTCSV)

@printf(
    "\n=== VERDICT INPUTS: gate %s · the decomposition is PART 2 · the sink is priced in PART 3 ===\n",
    gate_ok ? "PASS" : "FAIL"
)
flush(stdout)
