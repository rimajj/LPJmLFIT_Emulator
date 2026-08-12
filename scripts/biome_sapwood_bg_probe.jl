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
# ── SCENARIO (ADR 0106's binding clause: "does F's growth error depend on climate?") ─────────────────
# Defaults reproduce the historic arm exactly, which is what PART 1's gate tests. To run the SAME paired
# decomposition on the warmed run (no code change, four env vars):
#   SCENARIO=ssp370 Y0=2090 Y1=2099 M_CANOPY_DIR=/p/tmp/jamirp/M_canopy_drift_ssp370 \
#   FORCING_DIR=/p/tmp/jamirp/M_canopy_drift_ssp370/forcing  scripts/sbatch_julia.sh M-sapbgssp ...
# Build those inputs with, per cell: `SCENARIO=ssp370 Y0=.. Y1=.. OUT=<dir>
# scripts/build_biome_stem_growth_reference.py`, `SCENARIO=ssp370 YEAR=<y> OUT=<dir>/individuals
# scripts/extract_cell_individuals.py` (one call per year), and `SITE=<name> OUT_DIR=<dir>/forcing
# scripts/build_hainich_response_forcing.py`. ⚠ Do NOT narrow that last script's SSP_Y0/SSP_Y1 — its
# COMMITTED `S_*_response_boundary` fixtures follow the window and a narrow one truncates line S's files.
const SCEN = get(ENV, "SCENARIO", "historic")
const Y0 = parse(Int, get(ENV, "Y0", "2010"))
const Y1 = parse(Int, get(ENV, "Y1", "2019"))
# "" ⇒ the committed per-cell historic fixture `references/biome_forcing_<name>.csv`; otherwise
# `<FORCING_DIR>/<SCENARIO>_<cell>_daily.csv` from `build_hainich_response_forcing.py`.
const FORCING_DIR = get(ENV, "FORCING_DIR", "")
const GATE_ON = (SCEN == "historic" && Y0 == 2010 && Y1 == 2019)
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
function build_patch(
        ind, rows, soil; tmpl_pft::Bool = false, seed_bg::Bool = false, seed_hold::Bool = false,
        prev_seed = nothing,
    )
    v(k, r) = parse(Float64, ind[k][r])
    ty(r) = parse(Int, ind["type"][r])
    # ADR 0132: this cohort's own sapwood turnover rate, so the "what the stem HOLDS" seed and the growth
    # step that consumes it are on the SAME rate (beech's 0.04 in arm A, the PFT's own in arm P).
    rsap(r) = tmpl_pft ? FDiff.pft_allocparams(ty(r)).turnover_sapwood : FDiff.tebs_allocparams().turnover_sapwood
    function mkpool(r)
        heart = max(v("agb", r) / v("nind", r) - v("leaf_c", r) - v("sapwood_c", r), 0.0)
        # THREE seeding conventions, and the difference between them is the whole below-ground sink
        # (ADR 0132 §5). `prev_seed` is the C-FAITHFUL one: the pool a stem carries into year y was pinned
        # by year y−1's allocation, i.e. `(1−r)·D` evaluated at the state the stem had at the START of
        # year y−1 — a DIFFERENT fixture, keyed by (patch, id). Falling back to `(1−r)·D(this year)` is
        # the steady-state approximation of the same thing (it drops the stem's own growth over that
        # year). The bare `D(this year)` — what §8.1 shipped — makes the pool and the demand shrink in
        # lockstep and the annual top-up is EXACTLY zero.
        dmd = FDiff.reconstruct_sapwood_bg(
            v("sapwood_c", r), v("height", r), v("wooddens", r), soil.rootdist, soil.soildepth
        )
        sbg = if !seed_bg
            0.0
        elseif !seed_hold
            dmd                                   # ⚠ the §8.1 convention — kept so arms Abg/Pbg reproduce ADR 0127
        else
            hold = (1 - rsap(r)) * dmd
            prev_seed === nothing ? hold : get(prev_seed, (parse(Int, ind["patch"][r]), parse(Int, ind["id"][r])), hold)
        end
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

function readcanopy_patches(
        path, soil; tmpl_pft::Bool = false, seed_bg::Bool = false, seed_hold::Bool = false, prev_seed = nothing,
    )
    ind = readcsv(path)
    v(k, r) = parse(Float64, ind[k][r])
    prows = Dict{Int, Vector{Int}}()
    for r in eachindex(ind["type"])
        (parse(Int, ind["type"][r]) <= 6 && v("height", r) > 0) &&
            push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
    end
    pk = sort(collect(keys(prows)))
    return Dict(
            p => build_patch(
                ind, prows[p], soil; tmpl_pft = tmpl_pft, seed_bg = seed_bg, seed_hold = seed_hold,
                prev_seed = prev_seed,
            ) for p in pk
        ), pk
end

"""
ADR 0132 — the C-FAITHFUL below-ground pool each stem in `path` carries INTO the following year:
`(1−turnover_sapwood) ×` the C_LATERAL demand at that stem's state, keyed by `(patch, id)`.

`allocation_tree.c:191-209` pins `sapwood_bg` to the demand computed on the POST-turnover sapwood, so a
stem entering year `y` holds the value year `y−1`'s allocation set — a function of the state it had at
the START of year `y−1`, which is a DIFFERENT fixture from the one F starts year `y` from. Seeding from
the same year's fixture drops exactly the stem's growth over that year, which is the sink itself.
"""
function prev_year_seed(path, soil; tmpl_pft::Bool = false)
    isfile(path) || return nothing
    ind = readcsv(path)
    v(k, r) = parse(Float64, ind[k][r])
    ty(r) = parse(Int, ind["type"][r])
    out = Dict{Tuple{Int, Int}, Float64}()
    for r in eachindex(ind["type"])
        (ty(r) <= 6 && v("height", r) > 0) || continue
        rs = tmpl_pft ? FDiff.pft_allocparams(ty(r)).turnover_sapwood : FDiff.tebs_allocparams().turnover_sapwood
        out[(parse(Int, ind["patch"][r]), parse(Int, ind["id"][r]))] = (1 - rs) *
            FDiff.reconstruct_sapwood_bg(
            v("sapwood_c", r), v("height", r), v("wooddens", r), soil.rootdist, soil.soildepth
        )
    end
    return out
end

"""
Daily `AtmForcing` for one cell, split by year. `FORCING_DIR = ""` reads the committed historic fixture;
otherwise the scenario's per-cell daily file, whose columns are a superset minus `daylength` (which the
coupled harness does not consume). `tair0` (the record mean) seeds the energy closure's soil temperature,
so it is taken over the WINDOW actually run, not over the file.
"""
function forcings_by_year(name, cell)
    f = isempty(FORCING_DIR) ? readcsv(joinpath(REFDIR, "biome_forcing_$(name).csv")) :
        readcsv(joinpath(FORCING_DIR, "$(SCEN)_$(cell)_daily.csv"))
    yr = parse.(Int, f["year"])
    keep = findall(y -> Y0 <= y <= Y1, yr)
    isempty(keep) && error("forcings_by_year: no rows in $Y0-$Y1 for $name (cell $cell)")
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
    return out, mean(tairK[keep])
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

"""
One paired year for one patch. Returns `(grown pools, bm_inc, gpp, npp)`, all gC/m²(/yr).

⚠ `gpp_acc`/`npp_acc` MUST be read BEFORE `annual_step!` — that call zeroes them (`fast.jl:437`). They
are the canopy's OWN annual sums of `fl.gpp` / `fl.npp` (`fast.jl:346`), i.e. TREE-ONLY here: the roster
is `type <= 6` (`readcanopy_patches`) and the only grass branch is the year-END re-seed in `annual_step!`,
which this harness discards by rebuilding the core from the C's roster next year. `npp_acc == Σ npp_ind`
(`fdiff.jl:1966/1997`) ⇒ it must equal `ftos.bm_inc` to rounding; PART 5 asserts that rather than
assuming it, because the equality is what makes `cue = bm_inc/gpp` the same object on both sides.
"""
function run_one_year!(
        state, clo, pools, tmpls, soil, lat, forc; per_pft::Bool = false, types = nothing,
        params = PARAMS, grass_gate::Bool = true, bg_growth::Bool = false
    )
    core = per_pft ?
        FDiffFastCore(pools, tmpls, soil, lat; params = params, pft_ids = types, per_pft_params = true, grass_demand_gate = grass_gate, bg_growth = bg_growth) :
        FDiffFastCore(pools, tmpls, soil, lat; params = params, grass_demand_gate = grass_gate, bg_growth = bg_growth)
    bc_f = LPJmLFITEmulator.stand_structure_tof(core)
    for f in forc
        LPJmLFITEmulator.couple_day!(core, clo, state, bc_f, f; feedback = true)
    end
    (gpp_yr, npp_yr) = (Float64(core.gpp_acc), Float64(core.npp_acc))
    ftos = LPJmLFITEmulator.annual_step!(core, state)
    return core.pools, Float64(ftos.bm_inc), gpp_yr, npp_yr
end

# ── one paired stem-year ─────────────────────────────────────────────────────────────────────────────
struct Pair2
    name::String; year::Int; nind::Float64
    fa0::Float64; fa1::Float64          # F's agb_ind, start and end        (gC/individual)
    fv0::Float64; fv1::Float64          # F's vegc_ind (incl root), s/e     (gC/individual)
    fw0::Float64; fw1::Float64          # F's vegc_FULL_ind (+ the two below-ground WOOD pools), s/e
    # (ADR 0132). Identical to fv on every arm whose pool is 0 or static, so
    # every published column is untouched; on a `bg_growth` arm it is the only
    # place F's below-ground bucket carries the C_LATERAL sink.
    ca0::Float64; ca1::Float64          # the C's own agb, start and end    (gC/m²)
    cv0::Float64; cv1::Float64          # the C's own vegc, start and end   (gC/m²)
    cnpp::Float64                       # the C's own annual NPP of this stem (gC/m²/yr)
    d0::Float64; d1::Float64            # the C_LATERAL demand at F's start / end state (gC/individual)
end

const CELLS = readcsv(joinpath(REFDIR, "M_cells.csv"))
const NAMES = String.(CELLS["name"])
const LATS = fcol(CELLS, "lat")
const CELLIDS = parse.(Int, CELLS["cell"])
const TARGETS = read_targets()

"""
One arm at one cell: the paired per-stem rows plus the per-year ensemble `bm_inc` and patch count.

`seed_bg` seeds the below-ground pool (⇒ its maintenance respiration runs); `per_pft` runs each cohort's
own PFT parameters and phenology. The demand `d0`/`d1` is ALWAYS computed, in every arm, so a `keep`
prediction and the arm that would realise it are read off the same run.
"""
function arm(
        k::Int; per_pft::Bool = false, seed_bg::Bool = false, params = PARAMS, grass_gate::Bool = true,
        bg_growth::Bool = false,
    )
    name = NAMES[k]
    forc, tair0 = forcings_by_year(name, CELLIDS[k])
    soil = readsoil(joinpath(REFDIR, "M_soilcolumn_$(name).txt"))
    rows = Pair2[]
    bmi = fill(NaN, NYEAR); npatch = zeros(Int, NYEAR); bgmiss = zeros(Int, NYEAR)
    gppy = fill(NaN, NYEAR); nppy = fill(NaN, NYEAR)      # F's tree GPP / NPP, ensemble mean, gC/m²/yr
    states = Dict{Int, Any}(); clos = Dict{Int, Any}()
    dem(t) = FDiff.reconstruct_sapwood_bg(t.sapwood_c, t.height, t.wooddens, soil.rootdist, soil.soildepth)
    for (yi, y) in enumerate(Y0:Y1)
        src = joinpath(INDDIR, "M_individuals_$(name)_$(y - 1).csv")
        (isfile(src) && haskey(forc, y)) || continue
        # ADR 0132: with the pool PROGNOSTIC, seed it with what the C's own stem carries into this year —
        # `(1−r)·D` at the state it had one fixture earlier. Missing rows (a stem that was below the
        # writer's 5 m cut last year) fall back to the steady-state form; `bgmiss` counts them.
        prev = bg_growth ?
            prev_year_seed(joinpath(INDDIR, "M_individuals_$(name)_$(y - 2).csv"), soil; tmpl_pft = per_pft) :
            nothing
        patches, pk = readcanopy_patches(
            src, soil; tmpl_pft = per_pft, seed_bg = seed_bg, seed_hold = bg_growth, prev_seed = prev,
        )
        bg_growth && prev === nothing && (bgmiss[yi] = 1)
        acc = 0.0; accg = 0.0; accn = 0.0
        for p in pk
            pools, tmpls, ids, types = patches[p]
            st = get!(states, p, SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER)))
            cl = get!(clos, p, SEBEnergyClosure(; t_soil0 = tair0))
            grown, b, g, n = run_one_year!(
                st, cl, pools, tmpls, soil, LATS[k], forc[y];
                per_pft = per_pft, types = types, params = params, grass_gate = grass_gate,
                bg_growth = bg_growth,
            )
            acc += b; accg += g; accn += n
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
                        FDiff.vegc_full_ind(s0), FDiff.vegc_full_ind(g),
                        ca0, ca1, cv0, cv1, cnpp, dem(s0), dem(g)
                    )
                )
            end
        end
        bmi[yi] = acc / length(pk); npatch[yi] = length(pk)
        gppy[yi] = accg / length(pk); nppy[yi] = accn / length(pk)
    end
    return (; rows, bmi, gppy, nppy, npatch, bgmiss, name)
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
    bf = Float64[]; bc = Float64[]; gf = Float64[]; nf = Float64[]
    dagbF = Float64[]; dagbC = Float64[]; dagbC_pub = Float64[]; recon = Float64[]
    dbelF = Float64[]; dbelFw = Float64[]; dbelC = Float64[]
    dD = Float64[]; pool0 = Float64[]
    for (yi, y) in enumerate(Y0:Y1)
        isnan(a.bmi[yi]) && continue
        py = [p for p in a.rows if p.year == y]
        isempty(py) && continue
        np = a.npatch[yi]
        push!(yy, y)
        push!(bf, a.bmi[yi]); push!(gf, a.gppy[yi]); push!(nf, a.nppy[yi])
        push!(bc, sum(p.cnpp for p in py) / np)
        push!(dagbF, sum((p.fa1 - p.fa0) * p.nind for p in py) / np)
        push!(dagbC, sum(p.ca1 - p.ca0 for p in py) / np)
        push!(dagbC_pub, sum(p.ca1 - p.fa0 * p.nind for p in py) / np)
        push!(recon, sum(p.ca0 - p.fa0 * p.nind for p in py) / np)
        push!(dbelF, sum(((p.fv1 - p.fa1) - (p.fv0 - p.fa0)) * p.nind for p in py) / np)
        push!(dbelFw, sum(((p.fw1 - p.fa1) - (p.fw0 - p.fa0)) * p.nind for p in py) / np)
        push!(dbelC, sum((p.cv1 - p.ca1) - (p.cv0 - p.ca0) for p in py) / np)
        push!(dD, sum((p.d1 - p.d0) * p.nind for p in py) / np)
        push!(pool0, sum(p.d0 * p.nind for p in py) / np)
    end
    m(v) = isempty(v) ? NaN : mean(v)
    return (;
        n = length(yy), years = yy, gppF_y = gf, bmiF_y = bf,
        gf = m(gf), nf = m(nf),
        bf = m(bf), bc = m(bc), dagbF = m(dagbF), dagbC = m(dagbC), recon = m(recon),
        dbelF = m(dbelF), dbelFw = m(dbelFw), dbelC = m(dbelC), dD = m(dD), pool0 = m(pool0),
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

# ── ADR 0131: the TREE photosynthesis demand-gate arms ────────────────────────────────────────────────
# `PARAMS_TG` differs from `PARAMS` in exactly ONE field, `water.tree_demand_gate`. Two sharpnesses,
# because `βgpd_gate` is SHARED with the grass gate and `FDiffFastCore(grass_demand_gate=true)` — the
# default every other arm here runs under — re-pins it to the C's hard step `1e8`:
#   Ag   grass_gate=true  ⇒ βgpd_gate pinned to 1e8 = the C's hard branch. THE FAITHFUL ARM.
#   Ags  grass_gate=false ⇒ βgpd_gate stays at the soft `2e4` default = the AD-usable sharpness.
# Passing `grass_demand_gate=false` is behaviourally free HERE and only here: this harness's roster is
# `type <= 6` (`readcanopy_patches`), so no grass individual ever enters the daily loop, and the year-end
# grass re-seed in `annual_step!` is discarded when the roster is rebuilt from the C next year. `Ags − Ag`
# therefore isolates the SHARPNESS, not the grass.
const PARAMS_TG = let
    w = PARAMS.water
    fns = fieldnames(typeof(w))
    nt = NamedTuple{fns}(map(f -> getfield(w, f), fns))
    w2 = typeof(w)(; merge(nt, (; tree_demand_gate = true))...)
    FDiffParams{Float64}(PARAMS.photo, PARAMS.tstress, w2, PARAMS.resp, PARAMS.allom, PARAMS.nlambda, PARAMS.ω)
end
armAg = [arm(k; params = PARAMS_TG) for k in eachindex(NAMES)]
@printf("arm Ag  (A + the C's tree demand-gate, HARD step beta=1e8) done\n"); flush(stdout)
armAgs = [arm(k; params = PARAMS_TG, grass_gate = false) for k in eachindex(NAMES)]
@printf("arm Ags (A + the tree demand-gate at the soft AD-usable beta=2e4) done\n"); flush(stdout)
armPg = [arm(k; per_pft = true, params = PARAMS_TG) for k in eachindex(NAMES)]
@printf("arm Pg  (P + the tree demand-gate, hard step) done\n\n"); flush(stdout)

# ── ADR 0132: the PROGNOSTIC below-ground wood arms (the deferred design §5.4 step) ───────────────────
# `bg_growth=true` runs the C's below-ground pair — the C_LATERAL top-up deducted from the assimilate
# BEFORE the leaf/root/sapwood split, and the `sapwood_bg → heartwood_bg` turnover. It also switches the
# pool's SEED from `D` to what a stem in the C actually holds, `(1−r)·D` at the state it had one fixture
# earlier. That seed change is not cosmetic: with the `D` seed the pool and the demand shrink in lockstep
# and the top-up is identically zero (ADR 0132 §5), i.e. the arm would have measured its own convention.
armAbgg = [arm(k; seed_bg = true, bg_growth = true) for k in eachindex(NAMES)]
@printf("arm Abgg (A + the pool seeded AND PROGNOSTIC) done\n"); flush(stdout)
armPbgg = [arm(k; per_pft = true, seed_bg = true, bg_growth = true) for k in eachindex(NAMES)]
@printf("arm Pbgg (P + the pool seeded AND PROGNOSTIC) done\n"); flush(stdout)
armPgbgg = [arm(k; per_pft = true, seed_bg = true, bg_growth = true, params = PARAMS_TG) for k in eachindex(NAMES)]
@printf("arm Pgbgg (P + the tree demand-gate + the prognostic pool — the most faithful arm) done\n\n"); flush(stdout)

pA = [panel(a) for a in armA]
pAbg = [panel(a) for a in armAbg]
pP = [panel(a) for a in armP]
pPbg = [panel(a) for a in armPbg]
pAg = [panel(a) for a in armAg]
pAgs = [panel(a) for a in armAgs]
pPg = [panel(a) for a in armPg]
pAbgg = [panel(a) for a in armAbgg]
pPbgg = [panel(a) for a in armPbgg]
pPgbgg = [panel(a) for a in armPgbgg]

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
if !GATE_ON
    println("SKIPPED — this run is SCENARIO=$SCEN $Y0-$Y1, not the historic 2010-2019 basis the")
    println("published panel is on. The gate is a basis check on THIS reader and it was run and")
    println("PASSED on the default configuration; re-run with no env overrides to re-arm it.")
end
for k in eachindex(NAMES)
    GATE_ON || break
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
@printf("GATE: %s   (0.5 %% relative, or 0.2 absolute on bmi / 0.0002 on keep)\n", !GATE_ON ? "N/A" : (gate_ok ? "PASS" : "FAIL"))
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

# ── PART 5 — SPLITTING THE ASSIMILATE ERROR INTO PHOTOSYNTHESIS vs RESPIRATION (ADR 0129) ────────────
# WHY: PART 2 shows the assimilate error `bmi_F − bmi_C` is 77 % of F's surplus growth at the prototype
# cell, which makes it the head of the F queue — but `bmi` is a NET flux and two very different defects
# produce the same number. The split is an exact identity with no model in it:
#
#     bmi = GPP · CUE,      CUE ≡ NPP/GPP = 1 − Ra/GPP
#     ⇒  ln(bmi_F/bmi_C) = ln(GPP_F/GPP_C) + ln(CUE_F/CUE_C)      (exactly additive)
#
# The two leads on record predict opposite columns: `docs/notes/sapwood_bg_design.md` §13 has F's tree
# CUE at 0.512 vs the C's 0.46 (a ratio of 1.11, i.e. RESPIRATION), while
# `docs/notes/phase3_fdiff_cbinary_validation.md` §11 attributes the standalone overshoot to a +17 % GSI
# PHENOLOGY level in GPP. Both were measured on the pre-ADR-0125 basis (one year, standalone canopy, no
# per-stem pairing). This is the same split on the rung-3 basis: the C's own roster restarted every year,
# the 25-patch ensemble, year-matched.
#
# ⚠ THE FOUR BASIS FACTS, all of which change how a column is read (skill `fdiff-validate`):
#  1. GRASS. F's roster is `type <= 6` and grass is only re-seeded at the year END (discarded here), so
#     F's `gpp_acc` is TREE-only. The C side is `gpp_tree = d_gpp − d_grass_gpp` (the committed fixture's
#     own basis), NOT an FPC-share correction — grass under a closed canopy is light-limited and the FPC
#     share over-states its flux share 1.31–2.98× (ADR 0053).
#  2. THE >5 m CUT, and it is the one that decides which cells can be read. The `ind` writer emits only
#     stems above 5 m, so F's stand is missing the sub-5 m trees the C's daily GPP includes, while the
#     C's NPP (from `ind`) is missing them too. ⇒ `GPP_F/GPP_C` is biased DOWN and `CUE_F/CUE_C` UP by
#     nearly the same factor, and their PRODUCT — the `bmi` ratio — is unaffected. `gt5m` below is the
#     crown-cover form of that fraction: ~0.95–1.02 at Hainich (a ≤5 % effect) but ~0.71 at boreal and
#     Sahel, where neither column is separately readable.
#  3. TWO DIFFERENT C RUNS. `gpp_tree` comes from the single-cell re-runs; the per-stem `npp` comes from
#     the GLOBAL run's `ind`. `scripts/diagnose_oracle_run_divergence.py` scores them on the variable both
#     emit: four cells agree to <1.2 % (r >= 0.9989), `tropical_amazon` differs by 6.7 %.
#  4. YEAR-MATCHED. The ratio is formed per year and averaged, and the first/last years are printed, so a
#     drift is visible instead of being hidden in a 10-yr mean (ADR 0053 basis check 3).
#
# ⚠ SCENARIO: the C's daily GPP exists only for the HISTORIC window (the single-cell re-runs, and the
# global daily dataset is 2000-2019). On an ssp370 run the C columns are `nan` and only F's own GPP/CUE
# are reported — closing that needs an ssp370 single-cell re-run carrying `d_grass_gpp`.
@printf("\n--- PART 5: IS THE ASSIMILATE ERROR PHOTOSYNTHESIS OR RESPIRATION? ---\n")

const CGPP = let
    p = joinpath(REFDIR, "M_fdiff_oracle_biomes_annual.csv")
    d = readcsv(p)
    Dict(
        (String(d["name"][r]), parse(Int, d["year"][r])) => 365.0 * parse(Float64, d["gpp_tree"][r])
            for r in eachindex(d["name"])
    )
end
const CSTEM = let
    d = readcsv(joinpath(REFDIR, "M_stem_growth_reference.csv"))
    Dict(
        (String(d["name"][r]), parse(Int, d["year"][r])) =>
            (parse(Float64, d["npp_all"][r]), parse(Float64, d["gt5m_frac"][r]))
            for r in eachindex(d["name"])
    )
end
# ── THE BRACKET-CLOSING BASIS (ADR 0130) ────────────────────────────────────────────────────────
# Basis fact 2 above left the split undetermined because the C's GPP was on ALL trees while its
# per-stem NPP was on the >5 m stems only. Both are now measured on ONE population by a rebuilt C
# with `LPJ_IND_ALL_HEIGHTS=1 LPJ_IND_TRUE_GPP=1` (opt-in, inert unless set; the rebuild gated at
# 139 decoded quantities identical, 0 differ). Two columns matter here:
#   `gpp_tree_gt5/gpp_tree_all` — the >5 m share of TREE GPP, i.e. the factor that puts the C's GPP
#      on F's own roster. The bracket's ends assumed 1.0 (short stems carry no flux) and the
#      crown-cover `gt5m` (they carry their full crown share); this is the measured value.
#   `npp_tree_gt5/gpp_tree_gt5` — the C's CUE on exactly F's population, with no correction left.
# Its own gate: the per-individual GPP sum reproduces the run's `d_gpp` to 4.4e-7 over 100
# cell-years, which also proves the emitted roster is complete.
# ⚠ Single-cell basis (ADR 0041) — as `gpp_tree` already is, so the pairing is unchanged.
const CTRUE = let
    p = joinpath(REFDIR, "M_ind_true_gpp_reference.csv")
    if isfile(p)
        d = readcsv(p)
        Dict(
            (String(d["name"][r]), parse(Int, d["year"][r])) => (
                    parse(Float64, d["gpp_tree_gt5"][r]) / parse(Float64, d["gpp_tree_all"][r]),
                    parse(Float64, d["npp_tree_gt5"][r]) / parse(Float64, d["gpp_tree_gt5"][r]),
                ) for r in eachindex(d["name"])
        )
    else
        Dict{Tuple{String, Int}, Tuple{Float64, Float64}}()
    end
end

"""
Year-matched GPP / NPP / CUE for one arm at one cell. `nothing` for a C column the window has no oracle
for (any non-historic scenario). Returns means over the years BOTH sides cover, plus the first/last F-vs-C
GPP ratio so a drift is visible (basis check 3).
"""
function cue_panel(a, c)
    gfy = Float64[]; gcy = Float64[]; nfy = Float64[]; ncy = Float64[]; g5 = Float64[]; yy = Int[]
    for (i, y) in enumerate(c.years)
        haskey(CGPP, (a.name, y)) || continue
        haskey(CSTEM, (a.name, y)) || continue
        (npp_c, gt5) = CSTEM[(a.name, y)]
        push!(yy, y); push!(gfy, c.gppF_y[i]); push!(gcy, CGPP[(a.name, y)])
        push!(nfy, c.bmiF_y[i]); push!(ncy, npp_c); push!(g5, gt5)
    end
    isempty(yy) && return nothing
    r = gfy ./ gcy
    # The corrected (bracket-closing) C basis, year-matched the same way: `sh` puts the C's GPP on
    # F's >5 m roster and `cc5` is the C's CUE on that same roster. NaN where the fixture has no
    # row for the cell-year, so the old columns stay readable on their own.
    sh = Float64[]; cc5 = Float64[]
    for y in yy
        if haskey(CTRUE, (a.name, y))
            (s, c5) = CTRUE[(a.name, y)]
            push!(sh, s); push!(cc5, c5)
        end
    end
    return (;
        n = length(yy), years = yy, gfy = gfy, gcy = gcy, r = r, g5y = g5,
        gppF = mean(gfy), gppC = mean(gcy), nppF = mean(nfy), nppC = mean(ncy),
        cueF = mean(nfy ./ gfy), cueC = mean(ncy ./ gcy),
        rgpp = mean(r), rgpp_first = r[1], rgpp_last = r[end], gt5 = mean(filter(!isnan, g5)),
        gpp_share = isempty(sh) ? NaN : mean(sh),
        gppC5 = isempty(sh) ? NaN : mean(gcy) * mean(sh),
        cueC5 = isempty(cc5) ? NaN : mean(cc5),
    )
end

"OLS slope + Pearson r of `y` on `x` (both already logged where PART 5c wants them)."
function olsfit(x, y)
    n = length(x)
    n < 3 && return (NaN, NaN)
    mx = mean(x); my = mean(y)
    sxy = sum((x .- mx) .* (y .- my)); sxx = sum((x .- mx) .^ 2); syy = sum((y .- my) .^ 2)
    return (sxx <= 0 ? NaN : sxy / sxx, (sxx <= 0 || syy <= 0) ? NaN : sxy / sqrt(sxx * syy))
end

# the self-consistency assertion that makes `cue = bm_inc/gpp` the same object on both sides
let bad = 0
    for a in armA, yi in eachindex(a.bmi)
        isnan(a.bmi[yi]) && continue
        abs(a.nppy[yi] - a.bmi[yi]) > 1.0e-6 * max(abs(a.bmi[yi]), 1.0) && (bad += 1)
    end
    @printf("npp_acc == bm_inc (Sum npp_ind) on every arm-A cell-year: %s (%d violations)\n", bad == 0 ? "ok" : "FAIL", bad)
end

@printf(
    "\n%-22s %8s %8s %7s %8s %8s %7s %7s %7s %7s %6s\n",
    "cell", "GPP_F", "GPP_C", "F/C", "NPP_F", "NPP_C", "F/C", "CUE_F", "CUE_C", "F/C", "gt5m"
)
for (tag, ps, as) in (("A", pA, armA), ("Pbg", pPbg, armPbg))
    @printf("arm %s\n", tag)
    for k in eachindex(NAMES)
        q = cue_panel(as[k], ps[k])
        if q === nothing
            @printf("%-22s %8s %8s %7s %8.1f %8s %7s %7s %7s %7s %6s\n", NAMES[k], "-", "nan", "nan", ps[k].bf, "nan", "nan", "nan", "nan", "nan", "nan")
            continue
        end
        @printf(
            "%-22s %8.1f %8.1f %7.3f %8.1f %8.1f %7.3f %7.3f %7.3f %7.3f %6.2f\n", NAMES[k],
            q.gppF, q.gppC, q.gppF / q.gppC, q.nppF, q.nppC, q.nppF / q.nppC,
            q.cueF, q.cueC, q.cueF / q.cueC, q.gt5
        )
    end
end

@printf("\n--- PART 5b: THE ADDITIVE SPLIT, ln-space (the two columns sum to the NPP error) ---\n")
@printf("%-22s %9s %9s %9s %9s %9s %9s\n", "cell", "ln(NPP)", "=ln(GPP)", "+ln(CUE)", "GPP share", "GPP r y0", "GPP r y9")
for (tag, ps, as) in (("A", pA, armA), ("Pbg", pPbg, armPbg))
    @printf("arm %s\n", tag)
    for k in eachindex(NAMES)
        q = cue_panel(as[k], ps[k])
        q === nothing && continue
        # ⚠ the split is a LOG identity, so it is UNDEFINED wherever a ratio is non-positive — which is arm A
        # at the two hot cells, whose annual assimilate is NEGATIVE (the ADR 0125 `respcoeff` defect). Print
        # `undef` rather than a number (ADR 0127's sign-changing-denominator guard, same failure mode).
        if !(q.cueF > 0 && q.cueC > 0 && q.gppF > 0 && q.gppC > 0)
            @printf(
                "%-22s %9s %9s %9s %9s %9.3f %9.3f   (NPP_F <= 0: the split is undefined)\n", NAMES[k],
                "undef", "undef", "undef", "undef", q.rgpp_first, q.rgpp_last
            )
            continue
        end
        lg = log(q.gppF / q.gppC); lc = log(q.cueF / q.cueC); ln = lg + lc
        @printf(
            "%-22s %9.4f %9.4f %9.4f %8.0f %% %9.3f %9.3f\n", NAMES[k],
            ln, lg, lc, 100 * lg / ln, q.rgpp_first, q.rgpp_last
        )
    end
end
@printf("\nGPP share = ln(GPP_F/GPP_C) / ln(NPP_F/NPP_C) — the fraction of the assimilate error that is\n")
@printf("PHOTOSYNTHESIS rather than respiration. It is meaningful only where `gt5m` is near 1 (basis fact\n")
@printf("2 above) and where the C's own two runs agree (basis fact 3, i.e. not `tropical_amazon`), and it\n")
@printf("is undefined where ln(NPP) is near 0 or the assimilate changes sign.\n")
@printf("GPP r y0/y9 = the first and last year's GPP ratio — a drift means a structural cause, a flat\n")
@printf("offset means a flux-level one (ADR 0053 basis check 3).\n")

# ── PART 5d — THE SPLIT WITH THE POPULATION MISMATCH REMOVED (ADR 0130 closes ADR 0129's bracket) ──
# PART 5b's split is undetermined because its two C columns are on different populations. The C now
# emits per-stem GROSS GPP for EVERY tree, so both sides can be put on F's own >5 m roster:
#     GPP_C(>5 m) = GPP_C(all trees) x gpp_share       CUE_C(>5 m) read directly
# The product ln(NPP) is INVARIANT to this by construction (the two corrections are the same factor
# with opposite signs) — so the `ln(NPP)` column must be unchanged from PART 5b, and that is printed
# as a check rather than asserted away. Only the SPLIT between the columns moves.
@printf("\n--- PART 5d: THE CLOSED SPLIT — both C columns on F's OWN >5 m population ---\n")
@printf(
    "%-22s %7s %8s %8s %8s %8s %9s %9s %9s\n",
    "cell", "share", "GPP F/C", "CUE_C", "CUE F/C", "ln(NPP)", "=ln(GPP)", "+ln(CUE)", "GPP share"
)
for (tag, ps, as) in (("A", pA, armA), ("Pbg", pPbg, armPbg))
    @printf("arm %s\n", tag)
    for k in eachindex(NAMES)
        q = cue_panel(as[k], ps[k])
        q === nothing && continue
        if isnan(q.gpp_share)
            @printf("%-22s %7s   (no full-stand C run for this cell/window)\n", NAMES[k], "nan")
            continue
        end
        if !(q.cueF > 0 && q.cueC5 > 0 && q.gppF > 0 && q.gppC5 > 0)
            @printf(
                "%-22s %7.4f %8s %8.4f %8s %9s %9s %9s %9s   (NPP_F <= 0: undefined)\n",
                NAMES[k], q.gpp_share, "undef", q.cueC5, "undef", "undef", "undef", "undef", "undef"
            )
            continue
        end
        lg = log(q.gppF / q.gppC5); lc = log(q.cueF / q.cueC5); ln = lg + lc
        @printf(
            "%-22s %7.4f %8.3f %8.4f %8.3f %9.4f %9.4f %9.4f %8.0f %%\n", NAMES[k],
            q.gpp_share, q.gppF / q.gppC5, q.cueC5, q.cueF / q.cueC5, ln, lg, lc, 100 * lg / ln
        )
    end
end
@printf("\n`share` = the >5 m fraction of the C's TREE GPP, measured (not assumed). ADR 0129's bracket\n")
@printf("spanned share = 1.0 (short stems carry no flux) to share = the crown-cover `gt5m`; this row is\n")
@printf("the measurement that replaces both ends. `ln(NPP)` MUST match PART 5b's — if it does not, the\n")
@printf("two fixtures are on different C runs and the whole panel is void, so check that first.\n")
@printf("⚠ A cell whose `share` is far from 1 has most of its stand below the writer's cut, so its F\n")
@printf("roster is missing that flux too — the split is now defined there, but the LEVEL is still not\n")
@printf("a like-for-like stand comparison. Read `share` beside every number in this block.\n")

# ── PART 5c — HOW MUCH OF THE SPLIT IS THE SUB-5 m POPULATION? (the dominant uncertainty, measured) ───
# PART 5's basis fact 2 says the sub-5 m stems bias `GPP_F/GPP_C` down and `CUE_F/CUE_C` up by the same
# factor. That is not a footnote at Hainich: over the decade its `gt5m` falls 0.963 -> 0.892, and pushing
# the whole 8 % through moves the GPP share of the assimilate error from 38 % to 77 %. So the bracket
# straddles the verdict, and it has to be measured rather than assumed.
#
# THE DISCRIMINATOR, and it needs no new run: `gt5m` MOVES from year to year while F's population is
# fixed by construction (the C's own >5 m roster, restarted every year). Write `s` for the sub-5 m stems'
# share of the C's tree GPP. Then
#     GPP_C(all) = GPP_C(>5 m)/(1 − s)   ⇒   ln(GPP_F/GPP_C) = ln(true ratio) + ln(1 − s).
# If the sub-5 m stems photosynthesise in proportion to their CROWN cover, `1 − s = gt5m` and regressing
# ln(GPP_F/GPP_C) on ln(gt5m) across years must give SLOPE ~ +1 (the upper bound of the bracket is the
# right one). If they are so light-suppressed that they carry no flux, `s ~ 0`, the measured ratio does
# not track `gt5m` at all and the slope is ~0 (the lower bound is right).
# ⚠ The slope is only identified where `gt5m` actually varies and where nothing else moves with it — so
# read `r` too, and treat a cell whose slope is far outside [0, 1] as evidence that a THIRD thing (F's own
# year-to-year flux error) dominates there, not as an estimate of `s`.
@printf("\n--- PART 5c: DOES THE GPP RATIO TRACK THE SUB-5 m SHARE? (arm A; slope ~1 = yes, ~0 = no) ---\n")
@printf(
    "%-22s %8s %8s %8s %9s %8s %9s %13s %8s %8s %8s %8s %8s\n",
    "cell", "gt5m y0", "gt5m y9", "slope", "r", "raw drft", "corr drft", "|corr|<|raw|", "dt slope", "dt r",
    "sd lnx", "sd lny", "SE(dt)"
)
for k in eachindex(NAMES)
    q = cue_panel(armA[k], pA[k])
    q === nothing && continue
    ok = [i for i in eachindex(q.r) if !isnan(q.g5y[i]) && q.g5y[i] > 0 && q.r[i] > 0]
    length(ok) < 3 && continue
    (sl, rr) = olsfit(log.(q.g5y[ok]), log.(q.r[ok]))
    # ⚠ BOTH series are near-monotone in time, so the fit above cannot separate "tracks gt5m" from
    # "tracks anything else that drifts over the decade". Re-fit on the LINEARLY DETRENDED series: only
    # the year-to-year wiggle is left, which nothing but a genuine common driver reproduces.
    tt = Float64.(q.years[ok])
    detr(v) = (b = olsfit(tt, v)[1]; v .- b .* (tt .- mean(tt)))
    (sl_d, rr_d) = olsfit(detr(log.(q.g5y[ok])), detr(log.(q.r[ok])))
    # ⚠ AND THE POWER OF THAT NULL, because a collapsed detrended slope has TWO readings (ADR 0174 §5.3:
    # check the statistic's own noise floor). `gt5m` is a smooth near-monotone series, so detrending
    # leaves it almost no wiggle, while the GPP ratio's residual carries every weather-year flux error.
    # SE(slope) ~ sd(resid_y)/(sd(resid_x)·sqrt(n−2)): if that is >~1 the test CANNOT tell slope 0 from
    # slope 1 and the null is uninformative, not evidence against the mechanism.
    rx = detr(log.(q.g5y[ok])); ry = detr(log.(q.r[ok]))
    sdx = std(rx); sdy = std(ry)
    se_d = sdx <= 0 ? NaN : sqrt(max(sum((ry .- sl_d .* rx) .^ 2), 0.0) / max(length(ok) - 2, 1)) /
        (sdx * sqrt(length(ok) - 1))
    # the two drifts the slope is arbitrating between: the raw ratio, and the ratio with the sub-5 m
    # population divided out (`1 − s = gt5m`). Whichever is FLATTER is the basis the level should be on.
    raw = log(q.r[ok[end]] / q.r[ok[1]])
    cor = log((q.r[ok[end]] / q.g5y[ok[end]]) / (q.r[ok[1]] / q.g5y[ok[1]]))
    @printf(
        "%-22s %8.3f %8.3f %8.2f %9.3f %8.4f %9.4f %13s %8.2f %8.3f %8.4f %8.4f %8.2f\n", NAMES[k],
        q.g5y[ok[1]], q.g5y[ok[end]], sl, rr, raw, cor, abs(cor) < abs(raw) ? "yes" : "no", sl_d, rr_d,
        sdx, sdy, se_d
    )
end
@printf("\nslope = OLS of ln(GPP_F/GPP_C) on ln(gt5m) over the window's years. `corr drft` is the decadal\n")
@printf("drift of GPP_F/(GPP_C·gt5m), i.e. of the ratio the sub-5 m stems have been divided out of.\n")
@printf("A slope near +1 WITH a corrected drift smaller than the raw one is the signature that the sub-5 m\n")
@printf("population really does carry its crown share of the flux — in which case PART 5b's GPP share is\n")
@printf("an UNDER-estimate and the upper end of the bracket is the right reading for that cell.\n")
@printf("`dt slope`/`dt r` are the same fit on the LINEARLY DETRENDED series and are the check that the\n")
@printf("raw fit is not just two monotone decadal trends meeting: a slope that survives detrending is a\n")
@printf("year-to-year coupling, one that collapses to ~0 means the raw fit was shared trend and the\n")
@printf("correction is NOT identified at that cell.\n")
@printf("sd lnx/lny = the detrended residual spreads the `dt` fit is formed from, and SE(dt) its standard\n")
@printf("error. SE(dt) >~ 1 ⇒ that null CANNOT separate slope 0 from slope 1 and says nothing either way:\n")
@printf("report the BRACKET from PART 5b, not a point estimate, for such a cell.\n")

# ── PART 6 — THE TREE PHOTOSYNTHESIS DEMAND-GATE (ADR 0131) ──────────────────────────────────────────
# WHY: ADR 0130 closed the split at ≈43-47 % photosynthesis / ≈57-53 % respiration and put the RESPIRATION
# channel at the head of the queue. The cheapest respiration lead on record is the one v1 simplification
# that is a pure faithfulness defect with no missing state behind it: `water_stressed.c:196` skips
# photosynthesis when the canopy's own demand `gpd <= 1e-5`, and `:83` has already zeroed `*rd`, so on a
# gated day the C's tree makes NEITHER gross assimilation NOR leaf respiration. F has always run the tree
# path ungated, so on those days it pays `rd = b·vm` (set from `apar`, hence NOT collapsed with the
# demand) against a collapsed `agd` plus the `βflux` softplus GPP floor.
#
# ⚠ PRE-REGISTERED PREDICTION, written before the arm ran (so the sign cannot be read after the fact):
#   (i)  the gate LOWERS F's GPP (removes the floor) and RAISES F's NPP (removes the `rd` charge)
#        ⇒ it moves the PHOTOSYNTHESIS channel TOWARD the C and the RESPIRATION channel AWAY from it;
#   (ii) the net effect on `bmi` (the product, i.e. every published number of ADR 0125/0127) is therefore
#        WORSE, not better — F's `bmi` is already 1.20-1.28× the C's;
#   (iii) it fires on DROUGHT-collapse days, not leaf-off days, so it is ~nil at `temperate_hainich` and
#        largest at `semiarid_sahel` / `mediterranean_iberia`.
# A refutation of (ii) — the gate moving `bmi_F/bmi_C` toward 1 at any cell — makes it a live lever and is
# the outcome worth having. Either way the arm PRICES a known defect instead of leaving it on a list.
@printf("\n--- PART 6: THE C's TREE DEMAND-GATE (`gpd <= 1e-5` => no agd AND no rd), ADR 0131 ---\n")
@printf(
    "%-22s %8s %8s %7s %8s %8s %7s %7s %7s %8s %8s\n",
    "cell", "GPP off", "GPP on", "d%", "NPP off", "NPP on", "d%", "CUE off", "CUE on", "bmi F/C", "-> on"
)
for (tag, off_p, off_a, on_p, on_a) in (
        ("A -> Ag  (hard step, C-faithful)", pA, armA, pAg, armAg),
        ("A -> Ags (soft beta=2e4)", pA, armA, pAgs, armAgs),
        ("P -> Pg  (hard step)", pP, armP, pPg, armPg),
    )
    @printf("%s\n", tag)
    for k in eachindex(NAMES)
        c0 = off_p[k]; c1 = on_p[k]
        q0 = cue_panel(off_a[k], c0); q1 = cue_panel(on_a[k], c1)
        cue0 = c0.gf > 0 ? c0.bf / c0.gf : NaN
        cue1 = c1.gf > 0 ? c1.bf / c1.gf : NaN
        # `bmi_F/bmi_C` is the published assimilate-error statistic; the C side is arm-independent, so the
        # two columns differ ONLY by the gate. `bc` is the C's own per-stem NPP sum (same object as PART 2).
        r0 = c0.bc != 0 ? c0.bf / c0.bc : NaN
        r1 = c1.bc != 0 ? c1.bf / c1.bc : NaN
        @printf(
            "%-22s %8.1f %8.1f %7.2f %8.1f %8.1f %7.2f %7.3f %7.3f %8.3f %8.3f\n", NAMES[k],
            c0.gf, c1.gf, 100 * (c1.gf / c0.gf - 1), c0.bf, c1.bf, 100 * (c1.bf / c0.bf - 1),
            cue0, cue1, r0, r1
        )
        (q0 === nothing || q1 === nothing) && continue
    end
end
@printf("\nHOW TO READ IT. `GPP`/`NPP` are F's OWN tree-only annual ensemble means (gC/m2/yr), so the d%%\n")
@printf("columns are the gate's effect with nothing else moving — the C side is identical in both arms.\n")
@printf("`bmi F/C` is the SAME statistic ADR 0125/0127 published; moving it AWAY from 1.0 means this\n")
@printf("faithful gate makes the head-of-queue error worse, which is a result about where the error is NOT.\n")
@printf("`Ag` vs `Ags` is the SHARPNESS control: if they agree, the sigmoid width is not doing the work and\n")
@printf("the gate is usable on the differentiable path at beta=2e4; if they disagree, only the hard step is\n")
@printf("the C and the AD-usable version is a different operator.\n")
@printf("⚠ NOT MEASURED HERE: the number of gated tree-days. The effect is reported, its incidence is not\n")
@printf("(counting it needs an accumulator inside `daily_step_canopy`, i.e. a struct on the Enzyme path).\n")

# ── PART 7 — THE PROGNOSTIC BELOW-GROUND WOOD SINK, against ADR 0127 §6's PRE-REGISTERED CRITERION ───
# ADR 0127 §6, written before this arm existed: "with `sapwood_bg` seeded *and* prognostic, the paired
# surplus `Δagb_F − Δagb_C` must fall by at least `t_nosink` at `boreal_siberia` and `temperate_hainich`
# (i.e. ≥19.9 and ≥30.9 gC/m²/yr) without any committed baseline moving while the feature is off, and the
# tree CUE must stay inside [0.42, 0.56]." Those two cells only — the mediterranean demand is contaminated
# by that cell's own 2.7× growth error and the two hot cells' arm-A assimilate is negative.
#
# ⚠ READ THE SEED ROW FIRST. `sink` is what the port actually diverts from above-ground growth, and it is
# a property of the SEED as much as of the mechanism: this harness re-initialises F from the C's own
# roster every year, so a pool seeded from the SAME year's state has already thrown away the growth the
# sink is paid on, and the top-up computes as exactly zero (ADR 0132 §5). `bg_miss` is the number of years
# whose one-fixture-earlier seed file was absent (⇒ that year fell back to the steady-state seed).
@printf("\n--- PART 7: PROGNOSTIC below-ground wood vs ADR 0127 §6's pre-registered criterion (ADR 0132) ---\n")
@printf(
    "%-22s %7s %9s %9s %9s %9s %8s %8s %7s\n",
    "cell", "arm", "surplus", "t_nosink", "belF_wood", "drop", "target", "verdict", "bg_miss"
)
const PREREG = Dict("boreal_siberia" => 19.9, "temperate_hainich" => 30.9)
for (tag, refp, newp, newa) in (
        ("A->Abgg", pA, pAbgg, armAbgg),
        ("P->Pbgg", pP, pPbgg, armPbgg),
        ("Pg->Pgbgg", pPg, pPgbgg, armPgbgg),
    )
    @printf("%s\n", tag)
    for k in eachindex(NAMES)
        r0 = refp[k]; r1 = newp[k]
        s0 = r0.dagbF - r0.dagbC
        s1 = r1.dagbF - r1.dagbC
        tgt = get(PREREG, NAMES[k], NaN)
        drop = s0 - s1
        verdict = isnan(tgt) ? "n/a" : (drop >= tgt ? "PASS" : "FAIL")
        @printf(
            "%-22s %7s %9.1f %9.1f %9.2f %9.2f %8.1f %8s %7d\n", NAMES[k], "",
            s1, r1.dbelC - r1.dbelF, r1.dbelFw - r1.dbelF, drop, tgt, verdict, sum(newa[k].bgmiss)
        )
    end
end
@printf("\nHOW TO READ IT. `surplus` = F's paired above-ground growth minus the C's own, gC/m²/yr, on the\n")
@printf("NEW arm. `t_nosink` is the same arm's remaining below-ground channel (the C's below-ground bucket\n")
@printf("minus F's). `belF_wood` is what the two below-ground WOOD pools actually absorbed this year —\n")
@printf("i.e. the mechanism's own size, independent of whether it closed the target. `drop` is how much\n")
@printf("the surplus fell against the reference arm, and `target` is ADR 0127 §6's pre-registered bar.\n")
@printf("A `drop` far below `target` with a NON-ZERO `belF_wood` means the sink is real but small; a\n")
@printf("`belF_wood` of ~0 means the SEED, not the mechanism, is what is being measured.\n")

# ── the COMMITTED table (the result, not the log) ────────────────────────────────────────────────────
# ADR 0127's numbers live here rather than only in a `logs/` file, so a later session can re-score an arm
# against them without re-deriving the basis. Regenerate by re-running this probe; the basis gate above
# is what licenses the file.
const OUTCSV = get(
    ENV, "OUT_CSV",
    joinpath(REFDIR, GATE_ON ? "M_growth_channel_decomposition.csv" : "M_growth_channel_decomposition_$(SCEN).csv")
)
open(OUTCSV, "w") do io
    println(io, "# F_diff's SURPLUS above-ground growth vs the LPJmL-FIT C oracle, decomposed EXACTLY into")
    println(io, "# three carbon channels (ADR 0127). Paired per stem by (Cell, Patch, ID), alignment A")
    println(io, "# (roster(y-1) + year-y forcing -> roster(y)), 25-patch ensemble, slow=nothing; scenario")
    println(io, "# $(SCEN), years $(Y0)-$(Y1);")
    println(io, "# means of the per-year per-m2 ensemble sums. All fluxes gC/m2/yr.")
    println(io, "#   surplus = dagb_F - dagb_C = (bmi_F - bmi_C) + (loss_C - loss_F) + (bel_C - bel_F)")
    println(io, "#             = t_input        + t_loss          + t_nosink   (exact; a carbon identity)")
    println(io, "# arms: A = beech parameters for every tree, sapwood_bg = 0 (the ADR 0125/0126 basis)")
    println(io, "#       Abg = A + the below-ground pool seeded (its maintenance respiration runs)")
    println(io, "#       P   = per-cohort PFT parameters + the C's own pft_ids (ADR 0126)")
    println(io, "#       Pbg = P + the seed  (the most faithful configuration that exists today)")
    println(io, "#       Ag  = A + the C's TREE photosynthesis demand-gate at the hard step beta=1e8 (ADR 0131)")
    println(io, "#       Ags = A + the same gate at the soft, AD-usable beta=2e4 (the sharpness control)")
    println(io, "#       Pg  = P + the gate at the hard step")
    println(io, "#       Abgg/Pbgg/Pgbgg = A/P/Pg + the below-ground pool seeded AND PROGNOSTIC (ADR 0132):")
    println(io, "#         the C_LATERAL top-up deducted from the assimilate before the leaf/root/sapwood")
    println(io, "#         split + the sapwood_bg->heartwood_bg turnover. These arms ALSO change the pool's")
    println(io, "#         SEED from D to the (1-turnover_sapwood)*D a stem in the C actually holds, taken")
    println(io, "#         one fixture earlier - with the D seed the top-up is identically zero.")
    println(io, "# keepF_pub/keepC_pub reproduce ADR 0125 PART 7's published mean-of-per-year-ratios form;")
    println(io, "# keepF_abs/keepC_abs are the ratio-of-means. They are DIFFERENT statistics - see ADR 0127.")
    println(io, "# The last six columns (ADR 0129) split the assimilate error `bmi_F/bmi_C` EXACTLY into a")
    println(io, "# photosynthesis and a respiration channel: bmi = GPP*CUE, so ln(bmi_F/bmi_C) =")
    println(io, "# ln(gpp_F/gpp_C) + ln(cue_F/cue_C). gpp_C = 365*gpp_tree from M_fdiff_oracle_biomes_annual")
    println(io, "# (d_gpp - d_grass_gpp, ALL trees); npp_C_all = M_stem_growth_reference npp_all (>5 m stems")
    println(io, "# only). ⇒ gpp_F/gpp_C is biased DOWN and cue_F/cue_C UP by the sub-5 m share; gt5m_frac is")
    println(io, "# the crown-cover form of it. `nan` where the window has no C daily-GPP oracle (any")
    println(io, "# non-historic scenario) - closing that needs an ssp370 single-cell re-run with d_grass_gpp.")
    println(io, "# scripts/biome_sapwood_bg_probe.jl")
    println(
        io,
        "arm,cell,nyear,bmi_F,bmi_C,loss_F,loss_C,bel_F,bel_C,dagb_F,dagb_C,surplus," *
            "t_input,t_loss,t_nosink,demand_pool0,demand_incr,keepF_pub,keepC_pub,keepF_abs,keepC_abs," *
            "gpp_F,gpp_C,npp_C_all,cue_F,cue_C,gt5m_frac"
    )
    for (tag, ps, as) in (
            ("A", pA, armA), ("Abg", pAbg, armAbg), ("P", pP, armP), ("Pbg", pPbg, armPbg),
            ("Ag", pAg, armAg), ("Ags", pAgs, armAgs), ("Pg", pPg, armPg),
            ("Abgg", pAbgg, armAbgg), ("Pbgg", pPbgg, armPbgg), ("Pgbgg", pPgbgg, armPgbgg),
        )
        for k in eachindex(NAMES)
            c = ps[k]
            q = cue_panel(as[k], c)
            (gF, gC, nC, cF, cC, g5) = q === nothing ?
                (c.gf, NaN, NaN, c.gf > 0 ? c.bf / c.gf : NaN, NaN, NaN) :
                (q.gppF, q.gppC, q.nppC, q.cueF, q.cueC, q.gt5)
            @printf(
                io, "%s,%s,%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.6f,%.6f,%.6f,%.6f,%.4f,%.4f,%.4f,%.6f,%.6f,%.6f\n",
                tag, NAMES[k], c.n, c.bf, c.bc, c.lossF, c.lossC, c.dbelF, c.dbelC, c.dagbF, c.dagbC,
                c.dagbF - c.dagbC, c.bf - c.bc, c.lossC - c.lossF, c.dbelC - c.dbelF,
                c.pool0, c.dD, c.keepF_pub, c.keepC_pub, c.keepF_abs, c.keepC_abs,
                gF, gC, nC, cF, cC, g5
            )
        end
    end
end
@printf("\nwrote %s\n", OUTCSV)

@printf(
    "\n=== VERDICT INPUTS: gate %s · the decomposition is PART 2 · the sink is priced in PART 3 ===\n",
    !GATE_ON ? "N/A (non-default window)" : (gate_ok ? "PASS" : "FAIL")
)
flush(stdout)
