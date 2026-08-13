#!/usr/bin/env julia
#
# diagnose_rung2_map_on_rec_stand.jl — run the LEARNED COUNT MODEL over LPJmL-FIT's OWN rung-2 roster.
#
# WHY THIS EXISTS
# ---------------
# ADR 0181 measured the count model handed FIT's own stand on the GLOBAL one-step-forced table
# (51 767 cells). ADR 0182 measured that each rung-2 arm's own stand really does warm. The pre-registered
# next action (line S STATE §B) is to close the loop: run the map on each ARM's own stand and see whether
# the count response it ASKS FOR survives into the count the stand actually reaches.
#
# For the four emulator arms that needs no new work at all — the harness already recorded `target`
# (= `DRF.predict` on that arm's own stand) at every rendezvous, in `<apply>/s_arm_log.txt`. **`REC` is
# the one arm with no such log**, because `REC` is the pure-observation path: the C runs FIT's own
# demography and the harness is never started. So FIT's own stand has no map prediction on it at these
# cells, and without one there is no like-for-like local reference for the arms' numbers — only ADR 0181's
# global figure, which is a different axis (51 767 one-step-forced cells vs 12 free-running ones).
#
# This script supplies exactly that missing column and nothing else: it replays the `grow`-phase roster out
# of the `REC` dumps and evaluates the same map on it, so `REC` gets a `target` series on the same footing
# as every emulator arm. It runs NO model — it reads dumps already on disk.
#
# THE ADR-0023 RULE, AND WHY THIS FILE IS SHORT
# ---------------------------------------------
# The feature row and the prediction are NOT assembled here. This file `include`s
# `rung2_s_demography_harness.jl` and reaches its `Tree`, `pools_of`, `flux_drivers`, `n_emitted`,
# `HEIGHT_MIN` and `boundary_series`, which then reach the shipped `EM.flux_feature_vector` and
# `DRF.predict`. That is deliberate: the whole value of the comparison is that `REC`'s row is built by the
# SAME code that built each arm's row at runtime. A re-derivation here — even a correct-looking one —
# would make the copy the thing being measured, which is the ADR-0023 train/inference-shift trap and the
# reason ADR 0183's 5e-18 hazard agreement was worth anything.
#
# WHAT IS DELIBERATELY MIRRORED FROM THE HARNESS'S RENDEZVOUS
# ----------------------------------------------------------
#   * phase `grow` and only `grow` — the rendezvous point, after this year's turnover/allocation and
#     before anyone is removed. `pre` carries uninitialised `mort_*`/`bm_delta`; `mort`/`post` are the
#     wrong state (rung2-dump-analysis skill, ADR 0123).
#   * `n_prev`, in whichever of the two modes the arms being compared against ran — set `NPREV`
#     (default `roster`, so every published number here reproduces unchanged):
#       - `roster`: `n_prev` = `n_emit`, the live stand's own count (`_arm_run1.sh:78`; it is in the
#         dump names). ⚠ That is a REAL stand count handed to the model, so a number from this mode
#         sits on ADR 0181's **CTRL** (leaked, 0.707) axis, NOT its ABL (de-leaked, 0.292) axis, and
#         per ADR 0184 the target is then pinned to the live count to ±2.3 % — REC's sign agreement in
#         this mode is the PERSISTENCE NULL's value by construction and is not skill.
#       - `predict`: `n_prev[patch]` = the model's OWN previous target, seeded at a patch's first year
#         with `n_emit` (there is no previous prediction to recurse on). This is the shipped coupled
#         recursion and mirrors `rung2_s_demography_harness.jl:479-482, 601` line for line.
#     ⚠ THE MODE MUST MATCH THE ARM DUMPS IT WILL BE READ BESIDE. A `roster` REC column placed next to
#     `predict` arms puts the reference on a tethered axis and the arms on a free one.
#   * the transient per-year boundary tail (ADR 0026), from the same
#     `boundary/boundary_<scen>_c<cell>.csv` the emulator arms were given. `REC` itself ran with NO
#     boundary series (`_arm_run1.sh:116` skips it for `REC`, since no harness starts), so this is a
#     choice made here, and it is the only choice that makes the comparison like-for-like.
#   * `patch_area = 225.0` (`param.patcharea`), `EM.TreeAllometry{Float64}()`, and the `state`/`soil`
#     pair that exists only to carry `rootzone_w` through `root_zone_soilmoist` — all exactly as
#     `rung2_s_demography_harness.jl` builds them.
#
# USAGE
#   export DUMPS=/p/tmp/jamirp/S_rung2 OUT=/p/tmp/jamirp/S_rung2_maptarget/map_on_rec_stand.csv
#   scripts/sbatch_julia.sh S-maprec --project=. scripts/diagnose_rung2_map_on_rec_stand.jl
# Emits one CSV row per (cell, scenario, year, patch). Exit 0 always: a measurement, not a gate.

include(joinpath(@__DIR__, "rung2_s_demography_harness.jl"))

const DUMPS = get(ENV, "DUMPS", "/p/tmp/jamirp/S_rung2")
const OUTCSV = get(
    ENV, "OUT", "/p/tmp/jamirp/S_rung2_maptarget/map_on_rec_stand.csv"
)
const DRFPATH = get(
    ENV, "DRF", "/p/tmp/jamirp/emulator_global/drf_forest_global_pooled_w20_t8.drf"
)
const BDIR = get(ENV, "BOUNDARY_DIR", joinpath(DUMPS, "boundary"))
const PATCH_AREA = 225.0
const NPREV = get(ENV, "NPREV", "roster")
NPREV in ("roster", "predict") || error("NPREV must be roster or predict (got '$NPREV')")
const REC_RE = Regex("^S_r2s_(historic|ssp370)_c(\\d+)_REC_" * NPREV * "_s(\\d+)_dump\$")

"""
    grow_blocks(path) -> channel-like iteration via a callback

Stream one dump and hand every `grow`-phase patch-year to `cb(year, patch, trees, rootzone_w)`.

Records are grouped `(year, patch)` then by phase, and every phase block opens with its own `P <phase>`
line (verified on the dumps), so a `P` line is the block delimiter: it flushes whatever `grow` block was
open, and a `P grow` line opens a new one carrying that block's `rootzone_w`. Cheap `startswith` rejects
keep the three unwanted phases from ever being split — they are 3/4 of the file.

`rootzone_w` is MANDATORY: it is the `soilmoist` flux driver (ADR 0035) and proxying it is the documented
trap, so a dump whose `P` header lacks the column (a pre-v6 hook) is an error, not a fallback.
"""
function grow_blocks(cb, path::AbstractString)
    tcols = Dict{String, Int}()
    pcols = Dict{String, Int}()
    trees = Tree[]
    year = -1
    patch = -1
    rzw = NaN
    open_block = false
    nflushed = 0

    flush_block = function ()
        if open_block
            cb(year, patch, trees, rzw)
            nflushed += 1
        end
        open_block = false
        trees = Tree[]
        return
    end

    for line in eachline(path)
        if startswith(line, "#H T ")
            tcols = Dict(n => i for (i, n) in enumerate(split(line)[3:end]))
            continue
        elseif startswith(line, "#H P ")
            pcols = Dict(n => i for (i, n) in enumerate(split(line)[3:end]))
            haskey(pcols, "rootzone_w") || error(
                "$path has no `rootzone_w` column: this dump predates the v6 hook. The `soilmoist` " *
                    "flux driver cannot be built from the roster without it and proxying it is the " *
                    "ADR-0035 trap. Refusing to score it."
            )
            continue
        end
        isempty(line) && continue

        if startswith(line, "P ")
            flush_block()
            startswith(line, "P grow ") || continue
            isempty(pcols) && error("$path: a P record before its '#H P' header")
            f = split(line)[2:end]
            year = parse(Int, f[pcols["year"]])
            patch = parse(Int, f[pcols["patch"]])
            rzw = parse(Float64, f[pcols["rootzone_w"]])
            open_block = true
            continue
        end

        startswith(line, "T grow ") || continue
        open_block || error(
            "$path: a `T grow` record outside any `P grow` block at year $year patch $patch — the " *
                "dump's record grouping is not what this reader assumes; do not trust a partial scan."
        )
        isempty(tcols) && error("$path: a T record before its '#H T' header")
        f = split(line)[2:end]
        gf(n) = parse(Float64, f[tcols[n]])
        gi(n) = parse(Int, f[tcols[n]])
        leaf = gf("leaf_c")
        sap = gf("sapwood_c")
        heart = gf("heartwood_c")
        push!(
            trees,
            Tree(
                gi("pft_id"), gi("treeidx"), gf("nind"), gf("height"), gf("sla"), gf("wooddens"),
                gf("D95max"), gf("minwscal"), gf("crownarea"), leaf, sap, heart, gf("root_c"),
                gf("sapwood_bg_c"), gf("anpp"), gf("wscal_mean"), gi("age"), gf("fpc"),
                leaf + sap + heart,
                # `mort`/`hard` drive the KILL decision only. Nothing here kills anybody — this script
                # evaluates the count model, it does not run a demography — so they are not read, and
                # they are set to a neutral value rather than to a recomputed hazard that would look
                # like an input to a result it never touches.
                0.0, :none,
            )
        )
    end
    flush_block()
    return nflushed
end

"""
    score_dump(forest, allom, path, bseries) -> Vector{NTuple}

Every `grow` patch-year of one dump put through the shipped feature assembly and the forest.
"""
function score_dump(forest, allom, path::AbstractString, bseries)
    out = Vector{Any}()
    byears = sort(collect(keys(bseries)))
    # `n_prev` per patch, carried across years — the state of the shipped recursion. Unused in
    # `roster` mode, where the live stand overwrites it every year (harness lines 448-451).
    n_prev = Dict{Int, Float64}()
    grow_blocks(path) do year, patch, trees, rzw
        emitted = [t for t in trees if t.height > HEIGHT_MIN]
        pools_emit = pools_of(emitted)
        n_emit = n_emitted(trees, PATCH_AREA)
        bm_inc, ge, ws = flux_drivers(trees)
        # `roster`: the live stand's own count. `predict`: the model's own previous target, seeded at
        # a patch's first year with `n_emit` because there is no previous prediction to recurse on —
        # which is the one year in which `predict` mode is NOT the recursion (harness lines 475-482).
        npv = NPREV == "roster" ? n_emit : get(n_prev, patch, n_emit)
        state = EM.SharedState{Float64}(w = fill(rzw, EM.NSOILLAYER))
        soil = FD.SoilColumn{Float64}(
            fill(1.0, 3), fill(1 / 3, 3), fill(1 / 3, 3), 0.0, fill(1000.0, 3)
        )
        grow = (bm_inc_cell = bm_inc, growth_eff = ge, water_stress = ws)
        ages = Float64[t.age - 1 for t in emitted]
        # ADR 0026 clamp, mirroring `reconcile_demography!` and the harness: a year outside the series
        # reuses the nearest end row.
        byear = bseries[clamp(year, first(byears), last(byears))]
        feats = EM.flux_feature_vector(byear, ages, npv, grow, pools_emit, state, allom, soil)
        target = DRF.predict(forest, feats)
        n_prev[patch] = target
        push!(
            out,
            (
                year, patch, length(trees), n_emit, npv, target,
                bm_inc, ge, ws, feats[4],
                feats[5], feats[6], feats[7], feats[8], feats[9], feats[10],
            )
        )
    end
    return out
end

function score_all(argv)
    forest = DRF.load_forest(DRFPATH)
    allom = EM.TreeAllometry{Float64}()
    mkpath(dirname(OUTCSV))
    dumps = sort([d for d in readdir(DUMPS) if match(REC_RE, d) !== nothing])
    isempty(dumps) && error("no REC dumps matched under $DUMPS")
    println("map-on-REC-stand: $(length(dumps)) REC dump(s) under $DUMPS")
    println("  forest   : $DRFPATH  (nfeat=$(forest.nfeat))")
    println("  boundary : $BDIR")
    println("  out      : $OUTCSV")
    println(
        "  n_prev   : $NPREV", NPREV == "roster" ?
            "  (the live stand count — TETHERED, ADR 0184)" :
            "  (the model's own previous target — the shipped recursion)"
    )
    flush(stdout)

    open(OUTCSV, "w") do io
        println(io, "# map-on-REC-stand: the learned count model over LPJmL-FIT's OWN rung-2 roster.")
        println(io, "# built by scripts/diagnose_rung2_map_on_rec_stand.jl from the `grow` phase")
        println(
            io,
            NPREV == "roster" ?
                "# n_prev basis = roster (leaked) => ADR 0181 CTRL axis, NOT its de-leaked 0.292." :
                "# n_prev basis = predict (the shipped recursion; free-running, ADR 0184)."
        )
        println(io, "# forest=$DRFPATH")
        println(
            io,
            "cell,scenario,seed,year,patch,n_tree,n_emit,n_prev,target," *
                "bm_inc,growth_eff,water_stress,soilmoist,hmean,hmax,agb,lai,fpc,age_mean"
        )
        for d in dumps
            m = match(REC_RE, d)
            scen, cell, seed = m.captures[1], parse(Int, m.captures[2]), parse(Int, m.captures[3])
            rank = joinpath(DUMPS, d, "roster_rank0000.txt")
            if !isfile(rank)
                println("  SKIP $d — no roster_rank0000.txt")
                continue
            end
            bcsv = joinpath(BDIR, "boundary_$(scen)_c$(cell).csv")
            if !isfile(bcsv)
                println("  SKIP $d — no boundary series at $bcsv")
                continue
            end
            bseries = boundary_series(bcsv)
            forest.nfeat == 11 + length(first(values(bseries))) || error(
                "artifact/boundary width mismatch at $d: forest wants $(forest.nfeat) features, " *
                    "11 head + $(length(first(values(bseries)))) boundary columns given."
            )
            t0 = time()
            rows = score_dump(forest, allom, rank, bseries)
            for r in rows
                println(io, "$cell,$scen,$seed," * join(r, ","))
            end
            @printf(
                "  %-52s %6d patch-years  %6.1f s\n", d, length(rows), time() - t0
            )
            flush(stdout)
            flush(io)
        end
    end
    println("done -> $OUTCSV")
    flush(stdout)
    return 0
end

if abspath(PROGRAM_FILE) == @__FILE__
    exit(score_all(ARGS))
end
