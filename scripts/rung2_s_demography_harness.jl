#!/usr/bin/env julia
# rung2_s_demography_harness.jl — RUNG 2 for LINE S: the SHIPPED Component-S demography deciding who dies
# and who establishes inside LPJmL-FIT's OWN daily physics, year after year, in a closed loop.
#
# WHY THIS EXISTS AND WHY IT IS NOT ARM C
# ---------------------------------------
# `scripts/rung2_armc_harness.jl` serves a decision from the ported FIT hazard with the count target taken
# either from that hazard itself (`RHO=expected`, which pins theta = 1) or from the recorded baseline's own
# realized thinning (`RHO=recorded`).  Neither asks the count model anything.  So arm C measured the
# ORDERING interface and left the actual deliverable — the learned demography — untested against real
# physics.  This harness closes that: rho comes from the production count DRF, evaluated on a feature row
# built from the live roster the C publishes, and the recruit traits come from the production copula.
#
# It exists because rung 1 (ADR 0174) found the count channel's warming response FAILS ON SIGN when the
# emulator runs free (+0.707 one-step -> -0.226 free-running, validity horizon ~3 yr), and because rung 1
# could not decide whether that is a property of the demography or of the OFFLINE construction it was
# measured in.  Arm A1 (ADR 0112) recursed a scalar count while holding the six roster-state features at
# FIT's values — nobody would deploy that, and its own header calls itself a strict lower bound.  Here the
# state is a real stand: every feature is read off it, so `n_prev` is the stand's own previous count instead
# of the model's previous prediction (`--n-prev=roster`, the ADR-0175 fix), and there is no scalar to drift.
#
# THE ARMS.  Report all of them; each is one substitution more than the last.
#   S0  learned count target + UNIFORM thinning + establishment left to the C   (the shipped default)
#   S1  learned count target + the trait hazard's ORDERING + establishment left to the C
#   S2  S1 + recruit traits from the production copula — NOT WIRED HERE YET; establishment stays with the
#       C in every arm below, so `nrec` is 0 by construction and no S number here is a recruit result.
# and the two controls, which are what make any of it attributable:
#   N0  no substitution at all (`MODE=none` of run_rung2_replay_arm.sh) — the transport null
#   NP  the PERSISTENCE null: rho = 1 every year, i.e. keep the stand, learn nothing.  ADR 0112 showed a
#       persistence null matches the production model on every response statistic OFFLINE; if it also does
#       so HERE then this harness has no more power than the offline basis did, and that is the first thing
#       to check before believing S0-S2.
#
# WHAT THE C STILL OWNS in every arm here: turnover, allocation, growth, fire, the non-demographic hard
# kills (negative pools, `isneg_tree`, bioclimatic `survive()`, `cut_year`), AND establishment.  So every
# number this harness produces is a MORTALITY result on a real stand; when S2 is wired, only 4 of the 7
# sampled recruit trait axes are substitutable (`emax`/`k_root`/`beta_2` stay the C's) and the recruits half
# carries a structural replay floor of 0.907 (ADR 0121).
#
# THE FEATURE ROW IS BUILT BY THE SHIPPED FUNCTION, NOT BY A COPY.  `flux_feature_vector` and
# `DRF.predict` are reached as private names off the package, exactly as the arm-C harness reaches
# `TraitMortality.mortality_hazard`.  A second copy of the row assembly would make this file the thing being
# measured (the ADR-0023 train/inference-shift trap in a new place).
#
# TWO BASES ARE LOGGED SIDE BY SIDE, DELIBERATELY (ADR 0060).  The shipped runtime recomputes
# hmean/hmax/agb/lai/fpc from its own allometry, while the TRAINING columns came off the C's own `ind`
# aggregates.  Both rows are written to the log (`runtime` vs `ctrain`), because the gap between them is a
# train/inference shift that already exists in the deployed emulator and must be measured rather than
# hidden by picking one.  The DRF is fed the RUNTIME row — that is what deployment does.
#
# THE >5 m CUT IS LOAD-BEARING.  The count model's target and its `n_prev` are trained on the `ind` table,
# whose writer emits only stems `height > 5 m` (`fwriteoutput_ind.c:84`).  The rung-2 roster carries every
# tree.  So the count features and the count target apply the same 5 m cut, while the THINNING acts on the
# whole roster.  Dropping the cut inflates `n_prev` by the sub-5 m cohort and biases rho low every year.
#
# USAGE (in the background of the same job as the substituted lpjml; see scripts/run_rung2_s_arm.sh)
#     julia --project=. scripts/rung2_s_demography_harness.jl --arm=S1 --apply-dir=DIR --cell=42490 \
#           [--drf=PATH] [--rcop=PATH] [--n-prev=roster|predict] [--seed=1] [--log=PATH] [--ready=PATH]

using Printf
using Random

using LPJmLFITEmulator
const EM = LPJmLFITEmulator
const TM = LPJmLFITEmulator.TraitMortality
const FD = LPJmLFITEmulator.FDiff
const DRF = LPJmLFITEmulator.DRF

const REPO = normpath(joinpath(@__DIR__, ".."))
const HEIGHT_MIN = 5.0        # fwriteoutput_ind.c:84 — the `ind` writer's emission cut
const NDAYYEAR = 365          # the model calendar; the divisor the `ind` writer applies to wscal_mean

# ── arguments ─────────────────────────────────────────────────────────────────────────────────────────
function parse_args(argv)
    opts = Dict{String, String}(
        "arm" => "S1",
        "apply_dir" => "",
        "cell" => "42490",
        "drf" => joinpath(REPO, "test/testitems/references/drf_forest_hainich.drf"),
        "rcop" => joinpath(REPO, "test/testitems/references/recruit_copula_hainich.rcop"),
        "cells_csv" => joinpath(REPO, "test/testitems/references/M_cells.csv"),
        "n_prev" => "roster",
        "seed" => "1",
        "log" => "",
        "ready" => "",
        "max_idle" => "300",
        "poll" => "0.002",
    )
    for a in argv
        m = match(r"^--([a-z-_]+)=(.*)$", a)
        m === nothing && error("unrecognised argument '$a' (expected --key=value)")
        key = replace(m.captures[1], '-' => '_')
        haskey(opts, key) || error("unknown option --$(m.captures[1])")
        opts[key] = m.captures[2]
    end
    opts["arm"] in ("S0", "S1", "NP") ||
        error("--arm must be S0, S1 or NP (got '$(opts["arm"])')")
    opts["n_prev"] in ("roster", "predict") ||
        error("--n-prev must be roster or predict (got '$(opts["n_prev"])')")
    isempty(opts["apply_dir"]) && error("--apply-dir is required")
    return opts
end

# ── the per-cell slow boundary tail, off the committed registry ────────────────────────────────────────
"""
    cell_boundary(csv, cell) -> Vector{Float64}

The four-column slow bioclimatic tail (`eco_diag_gdd_5`, `tas_cold_month`, `soil_depth`, `co2`) in the
runtime order, read from `test/testitems/references/M_cells.csv` — the committed per-cell registry
`scripts/extract_cell_slow_init.py` writes, which is version-coupled to the pinned artifact.

Read, never transcribed: a second copy of a per-cell constant is ADR 0031's failure mode.
"""
function cell_boundary(csv::AbstractString, cell::Int)
    hdr = String[]
    for line in eachline(csv)
        startswith(line, "#") && continue
        if isempty(hdr)
            hdr = String.(split(strip(line), ','))
            continue
        end
        f = String.(split(strip(line), ','))
        idx(n) = findfirst(==(n), hdr)
        parse(Int, f[idx("cell")]) == cell || continue
        return Float64[
            parse(Float64, f[idx(c)]) for
                c in ("eco_diag_gdd_5", "tas_cold_month", "soil_depth", "co2")
        ]
    end
    return error("cell $cell not found in $csv")
end

# ── the roster reader ─────────────────────────────────────────────────────────────────────────────────
struct Tree
    pft_id::Int
    treeidx::Int
    nind::Float64
    height::Float64
    sla::Float64
    wooddens::Float64
    d95max::Float64
    minwscal::Float64
    crownarea::Float64
    leaf_c::Float64
    sapwood_c::Float64
    heartwood_c::Float64
    root_c::Float64
    sapwood_bg_c::Float64
    anpp::Float64
    wscal_mean::Float64
    age::Int              # the `grow` roster's POST-increment age
    fpc_c::Float64        # the C's own fpc, for the ctrain basis only — never an input to the operator
    agb_c::Float64        # the C's own agb  (leaf + sapwood + heartwood), likewise
    mort::Float64         # the ported hazard on this year's state
    hard::Symbol
end

"""
    read_request(path) -> (year, patch, trees, rootzone_w)

Parse one rendezvous request: the `grow`-phase roster plus the `P` record's root-zone soil moisture.

`grow` is mandatory. On the pre-ADR-0123 `pre` rendezvous the roster's `bm_inc_counter` was a year stale,
which INVERTED the sign of the wood-density selection differential (ADR 0122/0123) — so a silently accepted
`pre` request would yield a plausible, wrong answer. `rootzone_w` is mandatory too: without it the
`soilmoist` feature would have to be proxied, and it is one of the four flux drivers (ADR 0035).
"""
function read_request(path::AbstractString)
    tcols = Dict{String, Int}()
    pcols = Dict{String, Int}()
    trees = Tree[]
    year = -1
    patch = -1
    rzw = NaN
    for line in eachline(path)
        if startswith(line, "#H T ")
            tcols = Dict(n => i for (i, n) in enumerate(split(line)[3:end]))
            continue
        elseif startswith(line, "#H P ")
            pcols = Dict(n => i for (i, n) in enumerate(split(line)[3:end]))
            continue
        end
        isempty(line) && continue
        if line[1] == 'P'
            isempty(pcols) && error("$path: a P record before its '#H P' header")
            f = split(line)[2:end]
            f[pcols["phase"]] == "grow" || continue
            haskey(pcols, "rootzone_w") || error(
                "$path has no `rootzone_w` column: this binary predates the v6 hook " *
                    "(patches/lpjmlfit_rung2_hook_v6.patch). The `soilmoist` flux driver cannot be built " *
                    "from the roster without it, and proxying it is the ADR-0035 trap. Refusing to serve."
            )
            rzw = parse(Float64, f[pcols["rootzone_w"]])
            continue
        end
        line[1] == 'T' || continue
        isempty(tcols) && error("$path: a T record before its '#H T' header")
        f = split(line)[2:end]
        gs(n) = f[tcols[n]]
        gf(n) = parse(Float64, gs(n))
        gi(n) = parse(Int, gs(n))
        gs("phase") == "grow" || error(
            "$path: rendezvous phase is '$(gs("phase"))', not 'grow'. This binary predates the " *
                "rendezvous move behind the growth loop (ADR 0123); its roster is a year stale in " *
                "bm_inc_counter, which INVERTS the trait selection differential. Refusing to serve it."
        )
        year = gi("year")
        patch = gi("patch")
        p = TM.pft_mort_params(gi("pft_id"))
        h = TM.mortality_hazard(
            p; wooddens = gf("wooddens"), sla = gf("sla"), age = gi("age") - 1,
            bm_delta = gf("bm_delta"), leafarea = gf("leafarea_real"), leaf_c = gf("leaf_c"),
            water_stress = gf("water_stress"), temp_stress = gf("temp_stress"),
            bm_inc_counter = gi("bm_inc_counter")
        )
        push!(
            trees, Tree(
                gi("pft_id"), gi("treeidx"), gf("nind"), gf("height"), gf("sla"), gf("wooddens"),
                gf("D95max"), gf("minwscal"), gf("crownarea"), gf("leaf_c"), gf("sapwood_c"),
                gf("heartwood_c"), gf("root_c"), gf("sapwood_bg_c"), gf("anpp"), gf("wscal_mean"),
                gi("age"), gf("fpc"),
                gf("leaf_c") + gf("sapwood_c") + gf("heartwood_c") - gf("debt_c"),
                h.total, h.hard_kill
            )
        )
    end
    isnan(rzw) && error("$path: no `grow`-phase P record, so no rootzone_w")
    sort!(trees, by = t -> (t.pft_id, t.treeidx))
    return year, patch, trees, rzw
end

# ── the emulator-facing view of the roster ────────────────────────────────────────────────────────────
"""
    pools_of(trees) -> Vector{FDiff.TreePools}

A `FDiff.TreePools` per tree, so the shipped feature assembly can be called on the real stand.

⚠ **Call this on the EMITTED (>5 m) subset when building the feature row.** Every one of the six state
columns in the training table is an aggregate over the `ind` table's rows, and that writer emits only stems
above 5 m (`fwriteoutput_ind.c:84`) — so a row built on the C's FULL roster is on a different population
than the forest was trained on. Measured at Hainich: including the sub-5 m cohort halves `age_mean` (31.9
against 74.5 at 2019, a persistent factor of ~1.9), because saplings are young and the runtime mean is
nind-weighted. `agb` happens to survive (5224 vs 5211, 0.25 %) since young stems carry little carbon, which
is exactly why this is the kind of error that shows up in one feature and not its neighbours.

The thinning still acts on the WHOLE roster — the C owns every tree, and a sub-5 m stem can still be killed.
Only the feature row and the count target are on the emitted population.
"""
pools_of(trees::Vector{Tree}) = [
    FD.TreePools{Float64}(
            t.leaf_c, t.sapwood_c, t.heartwood_c, t.root_c, t.sapwood_bg_c,
            t.height, t.crownarea, t.nind, t.sla, t.wooddens, t.d95max, t.minwscal, false
        ) for t in trees
]

"""
    flux_drivers(trees) -> (bm_inc_cell, growth_eff, water_stress)

The three annual integrals, on the SAME definitions `scripts/build_slow_runtime_table.py` used for the
training columns, restricted to the emitted (>5 m) stem population:

  bm_inc_cell  = sum(npp)                                      (`anpp`, the `ind` table's `npp`)
  growth_eff   = lai > 0 ? sum(npp | npp>0 & height>0) / lai : 0
  water_stress = 1 - mean(wscal_mean)                           (unweighted mean over stems)

`lai` here is the same `sum(leaf_c*sla*nind)` the runtime forms, which is algebraically identical to the
training table's per-patch reconstruction `sum(LAI*fpc_ind/(1-exp(-k*LAI)))` (ADR 0035): `fpc_ind` divided
by its own saturation factor is `crownarea*nind`, and `LAI*crownarea = leaf_c*sla`. So the two bases agree
here exactly, which is why only this one is formed.
"""
function flux_drivers(trees::Vector{Tree})
    emitted = [t for t in trees if t.height > HEIGHT_MIN]
    isempty(emitted) && return (0.0, 0.0, 0.0)
    bm_inc = sum(t.anpp for t in emitted)
    applied = sum((t.anpp > 0 && t.height > 0) ? t.anpp : 0.0 for t in emitted)
    lai = sum(t.leaf_c * t.sla * t.nind for t in emitted)
    ge = lai > 0 ? applied / lai : 0.0
    # ⚠ THE DUMP'S `wscal_mean` IS THE RAW DAILY ACCUMULATOR, NOT the `ind` table's column.
    # `water_stressed.c:140` adds to `pft->wscal_mean` every day and `fwriteoutput_ind.c:119` divides by
    # NDAYYEAR on the way out; the rung-2 hook writes the struct field directly, so it arrives ~365x too
    # large.  Undivided it gives `water_stress = 1 - 365 = -364` on an unstressed year, which is how this
    # was caught — but a reader that silently accepted it would feed the count model a feature 365x outside
    # its training range.  Divide here, once, at the boundary.
    ws = 1.0 - sum(t.wscal_mean for t in emitted) / (length(emitted) * NDAYYEAR)
    return (bm_inc, ge, ws)
end

"""
    ctrain_state(trees) -> (hmean, hmax, agb, lai, fpc, age_mean)

The same six state columns on the C's OWN aggregates over the emitted (>5 m) stems — the TRAINING basis,
logged beside the runtime row so the gap between them is measured rather than assumed away (ADR 0060).

Two of these are only approximately the training column, and the approximation is stated rather than
hidden:

* **`agb`.** The `ind` column is `agb_tree` = `(agb_tree_sum(ind) − debt + excess_carbon)·nind −
  turn_litt.leaf.carbon` (`src/tree/agb_tree.c:25`), i.e. **already per m²** — so the training table's
  `sum(agb)` and the runtime's `agb_ind·nind` are the SAME basis and there is no scale mismatch. But
  `excess_carbon` and `turn_litt` are not dumped, so this reconstruction is
  `(leaf + sapwood + heartwood − debt)·nind` and will sit slightly above the true column.
* **`age_mean`.** The training column is `(Age − 1).mean()` over the patch's `ind` rows: **unweighted, and
  over emitted stems only**. The runtime's is `_mean_age_weighted`: **nind-weighted, over every cohort**.
  Those are different definitions, not different roundings, and this pair is the way to size the difference.
"""
function ctrain_state(trees::Vector{Tree})
    emitted = [t for t in trees if t.height > HEIGHT_MIN]
    isempty(emitted) && return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    fpcsum = sum(t.fpc_c for t in emitted)
    hmean = fpcsum > 0 ? sum(t.height * t.fpc_c for t in emitted) / fpcsum : 0.0
    hmax = maximum(t.height for t in emitted)
    agb = sum(t.agb_c * t.nind for t in emitted)
    lai = sum(t.leaf_c * t.sla * t.nind for t in emitted)
    age = sum(t.age - 1 for t in emitted) / length(emitted)
    return (hmean, hmax, agb, lai, min(fpcsum, 1.0), age)
end

"Stems per patch on the count model's own basis: the >5 m population, `Σ nind · patch_area`."
n_emitted(trees::Vector{Tree}, patch_area::Float64) =
    sum(t.nind for t in trees if t.height > HEIGHT_MIN; init = 0.0) * patch_area

# ── main loop ─────────────────────────────────────────────────────────────────────────────────────────
const REQ_RE = r"req_r(\d+)_y(\d+)_p(\d+)\.ready$"

function main(argv)
    opts = parse_args(argv)
    arm = opts["arm"]
    apply_dir = opts["apply_dir"]
    seed = parse(Int, opts["seed"])
    cell = parse(Int, opts["cell"])
    max_idle = parse(Float64, opts["max_idle"])
    poll = parse(Float64, opts["poll"])
    patch_area = 225.0                                  # param.patcharea, par/lpjparam_fit.js
    mkpath(apply_dir)
    log_path = isempty(opts["log"]) ? joinpath(apply_dir, "s_arm_log.txt") : opts["log"]

    forest = DRF.load_forest(opts["drf"])
    boundary = cell_boundary(opts["cells_csv"], cell)
    allom = EM.TreeAllometry{Float64}()   # the shipped default; the roster's own crown areas are the C's

    println("rung-2 LINE-S demography harness, arm $arm")
    println("  count model : ", opts["drf"], "  (", forest.nfeat, " features)")
    println("  recruits    : left to the C (ESTAB_C) in every arm here")
    println("  boundary    : cell $cell -> ", boundary)
    println(
        "  n_prev      : ", opts["n_prev"], opts["n_prev"] == "roster" ?
            "  (the stand's own previous count — ADR 0175)" : "  (the model's own previous prediction)"
    )
    println("  seed        : ", seed)
    println("  apply dir   : ", apply_dir)
    flush(stdout)

    forest.nfeat == 11 + length(boundary) || error(
        "artifact/boundary width mismatch: the forest wants $(forest.nfeat) features but 11 head + " *
            "$(length(boundary)) boundary columns give $(11 + length(boundary)). The boundary tail is " *
            "part of the pinned artifact's contract (ADR 0020 §6)."
    )

    log = open(log_path, "w")
    println(
        log,
        "#H L year patch n_tree n_emit n_prev target rho theta shortfall n_kill n_recruit " *
            "bm_inc growth_eff water_stress soilmoist " *
            "hmean_rt hmax_rt agb_rt lai_rt fpc_rt age_rt " *
            "hmean_c hmax_c agb_c lai_c fpc_c age_c"
    )
    isempty(opts["ready"]) || close(open(opts["ready"], "w"))

    # `n_prev` per patch, carried across years.  In `roster` mode it is overwritten from the live stand
    # every year and this dictionary is only a fallback for the FIRST year of each patch, where there is no
    # previous roster; in `predict` mode it is the shipped recursion and this IS the state.
    n_prev = Dict{Int, Float64}()

    served = Set{String}()
    last_seen = time()
    nserved = 0
    while time() - last_seen < max_idle
        hits = 0
        for ready in sort(filter(f -> occursin(REQ_RE, f), readdir(apply_dir; join = true)))
            (ready in served) && continue
            m = match(REQ_RE, basename(ready))
            rank = parse(Int, m.captures[1])
            req_txt = ready[1:(end - length(".ready"))] * ".txt"
            isfile(req_txt) || continue
            year, patch, trees, rzw = read_request(req_txt)

            # the FULL roster (what the thinning acts on) and the EMITTED subset (what the count model was
            # trained on) are deliberately separate — see `pools_of`
            pools = pools_of(trees)
            emitted = [t for t in trees if t.height > HEIGHT_MIN]
            pools_emit = pools_of(emitted)
            n_emit = n_emitted(trees, patch_area)
            bm_inc, ge, ws = flux_drivers(trees)

            # `n_prev`: the stand's own previous count (the fix), or the model's previous prediction (the
            # shipped recursion).  The first year of a patch has no previous roster either way, so it seeds
            # from the live stand — a one-step start, identical in both modes, and it is the ONLY year in
            # which `predict` mode is not the recursion.
            npv = if opts["n_prev"] == "roster"
                n_emit
            else
                get(n_prev, patch, n_emit)
            end

            # ── the RUNTIME feature row, assembled by the SHIPPED function on the real stand.  `state`/
            #    `soil` exist only to carry `soilmoist` through `root_zone_soilmoist`, which reads
            #    `state.w` weighted by `soil.whcs` over the top 3 layers — equal weights on a constant `w`
            #    return that `w` exactly, so the feature equals the C's own root-zone fraction. ──
            state = EM.SharedState{Float64}(w = fill(rzw, EM.NSOILLAYER))
            soil = FD.SoilColumn{Float64}(
                fill(1.0, 3), fill(1 / 3, 3), fill(1 / 3, 3), 0.0, fill(1000.0, 3)
            )
            grow = (bm_inc_cell = bm_inc, growth_eff = ge, water_stress = ws)
            ages = Float64[t.age - 1 for t in emitted]
            feats = EM.flux_feature_vector(boundary, ages, npv, grow, pools_emit, state, allom, soil)
            target = DRF.predict(forest, feats)

            ρ = arm == "NP" ? 1.0 : clamp(target / (npv + 1.0e-12), 0.7, 1.3)

            # ── the decision ──
            kills = Tuple{Int, Int}[]
            θ = NaN
            shortfall = 0.0
            rng = Xoshiro(hash((seed, year, patch)))
            if ρ < 1.0 && !isempty(trees)
                nind = [t.nind for t in trees]
                n_now = sum(nind)
                f = Vector{Float64}(undef, length(trees))
                if arm == "S0" || arm == "NP"
                    fill!(f, ρ)                                   # the shipped uniform thinning
                else
                    haz = [t.mort for t in trees]
                    tp = [
                        FD.TreePools{Float64}(
                                1.0, 1.0, 1.0, 1.0, 0.0, 1.0, 1.0, t.nind, t.sla, t.wooddens, false
                            ) for t in trees
                    ]
                    θ, shortfall = EM._hazard_tilt(haz, tp, ρ * n_now, n_now)
                    for i in eachindex(trees)
                        w = 1.0 - haz[i]
                        f[i] = w <= 0.0 ? 0.0 : w^θ
                    end
                end
                for i in eachindex(trees)
                    rand(rng) > f[i] && push!(kills, (trees[i].pft_id, trees[i].treeidx))
                end
            end

            # ── the answer ──
            # The kill list IS the mortality answer, including when it is empty: with rho >= 1 the count
            # model says the stand grows, so S kills nobody and the C's own hazard is overridden to spare
            # everyone.  `MORT_C` is deliberately never served — deferring mortality back to the C would
            # make this not an S arm.  Establishment always defers (`ESTAB_C`), so `n_recruit` is 0 by
            # construction and this harness cannot be quoted on recruits.
            nrec = 0
            base = joinpath(apply_dir, @sprintf("rsp_r%04d_y%05d_p%03d", rank, year, patch))
            open(base * ".txt", "w") do fh
                println(fh, "# arm $arm, year $year patch $patch (n_prev=$(opts["n_prev"]), seed=$seed)")
                for (pft_id, treeidx) in kills
                    println(fh, "K $pft_id $treeidx")
                end
                println(fh, "ESTAB_C")
                println(fh, "END")
            end
            close(open(base * ".ready", "w"))

            hm, hx, ab, la, fp, ag = feats[5], feats[6], feats[7], feats[8], feats[9], feats[10]
            chm, chx, cab, cla, cfp, cag = ctrain_state(trees)
            # Written as a joined line, NOT a `@printf`: the row is 27 fields wide and `@printf` needs its
            # format as ONE string literal, so a concatenated format is a load-time `ArgumentError` — and
            # `Meta.parseall` does NOT catch it, because macro expansion happens after parsing. A
            # parse-check is not a load-check for this file.
            fields = Any[
                year, patch, length(trees), n_emit, npv, target, ρ, θ, shortfall,
                length(kills), nrec,
                bm_inc, ge, ws, rzw, hm, hx, ab, la, fp, ag,
                chm, chx, cab, cla, cfp, cag,
            ]
            println(
                log,
                "L " * join((v isa Integer ? string(v) : repr(Float64(v)) for v in fields), " ")
            )
            flush(log)
            n_prev[patch] = target
            push!(served, ready)
            hits += 1
            nserved += 1
        end
        if hits > 0
            last_seen = time()
        else
            sleep(poll)
        end
    end
    close(log)
    @printf("harness: served %d patch-years, log -> %s\n", nserved, log_path)
    flush(stdout)
    return 0
end

exit(main(ARGS))
