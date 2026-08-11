#!/usr/bin/env julia
# ARM C of the rung-2 demography experiment — line M's rendezvous server for line S's option-(c)
# interface (ADR 0117): S hands back a per-individual survival factor `f_i ∈ [0,1]` keyed by the
# `(pft_id, treeidx)` pair of the roster M publishes, and M draws the Bernoulli.
#
# WHY THIS EXISTS, AND WHAT IT IS NOT
# -----------------------------------
# `scripts/rung2_replay_harness.py` serves the C its OWN recorded decision back; that measured the
# TRANSPORT (ADR 0121: the mortality half replays exactly, ratio 1.000).  This script serves a
# COMPUTED decision instead, from the ported FIT hazard in `src/trait_mortality.jl`, in the two arms
# line S specified:
#
#   C0  `f_i = ρ` for every tree — the shipped uniform ρ-thinning, i.e. the NO-SELECTION NULL.
#   C1  `f_i = (1 − mort_i)^θ`, θ bisected so `Σ nind·f_i = ρ·Σ nind` — the count target is pinned and
#       the ported hazard decides only the ORDERING of who dies.
#
# **`C1 − C0` is the measurement**: how much of FIT's trait response is differential survival.  ADR 0046
# decomposed the warming trait shift as 22.2 % composition / 51.3 % within-PFT / 26.6 % interaction, with
# the within-PFT part +112 % WITHIN-AGE-CLASS — and traits are immutable after `new_tree`, so a shift at
# fixed PFT and fixed age can only be who died.  A count-only interface cannot reach that in principle.
#
# It is NOT the production pipeline: the count target ρ does not come from the learned count model here
# (see `--rho` below).  Saying which ρ an arm ran on is mandatory when quoting it.
#
# NOTHING HERE REIMPLEMENTS S's OPERATOR.  The hazard is `TraitMortality.mortality_hazard` and the tilt is
# `LPJmLFITEmulator._hazard_tilt` — the same code the coupled `FluxDrivenSlowEmulator` calls when
# `trait_mortality = true`.  A second copy of either would be the ADR-0023 train/inference-shift trap in a
# new place: the arm would then measure this file, not the shipped operator.
#
# THE RENDEZVOUS IS THE `grow` ROSTER (ADR 0123), which is why arm C is scorable on traits at all.  The
# request file the C writes carries the post-growth, pre-kill roster, so `bm_delta`, `leafarea_real` and
# `bm_inc_counter` are THIS year's.  On the old `pre` rendezvous the one-year-stale counter inverted the
# sign of the wood-density selection differential (ratio −0.825), which is why ADR 0122 forbade scoring
# this arm.  Two consequences here: the `grow` age is POST-increment so the hazard's basis is `age − 1`,
# and a request that is not the `grow` phase is a fatal error rather than a silent basis error.
#
# WHAT THE C STILL DECIDES, and it must be disclosed with any arm-C number:
#   * establishment — this harness always answers `ESTAB_C`.  Deliberate: the recruits half has a
#     structural replay floor of 0.907 (ADR 0121), so substituting it would spend the exactness that
#     makes a mortality difference attributable.  Arm C is a MORTALITY arm.
#   * the C's non-demographic kills — a negative-pool allocation kill, `isneg_tree`, the cell-level
#     bioclimatic `survive()` and `cut_year` are flagged `hard` in the hook and are force-applied even
#     when this harness spares the tree (`n_forced_dead` in the C's own audit file).  They are physics,
#     not a demographic choice, and they are identical in construction across both arms.
#     NB the two hazard hard kills (`bm_inc_counter ≥ 5`, ghost-tree) are NOT in that set — they are the
#     interface's business, so C0 genuinely can spare them and the C counts it as `n_spared_certain`.
#
# USAGE (run in the background of the same job as the substituted lpjml; see scripts/run_rung2_armc.sh)
#     julia --project=. scripts/rung2_armc_harness.jl --arm=C1 --apply-dir=DIR [--rho=expected]
#           [--dump=DIR] [--seed=1] [--log=PATH] [--ready=PATH] [--max-idle=300]

using Printf
using Random

using LPJmLFITEmulator
const EM = LPJmLFITEmulator
const TM = LPJmLFITEmulator.TraitMortality
const FD = LPJmLFITEmulator.FDiff

# ── arguments ─────────────────────────────────────────────────────────────────────────────────────────
function parse_args(argv)
    opts = Dict{String, String}(
        "arm" => "C1",
        "apply_dir" => "",
        "rho" => "expected",
        "dump" => "/p/tmp/jamirp/M_rung2/M_rung2rec_v5_dump",
        "seed" => "1",
        "log" => "",
        "ready" => "",
        "max_idle" => "300",
        "poll" => "0.002",
    )
    for a in argv
        m = match(r"^--([a-z-_]+)=(.*)$", a)
        m === nothing && error("unrecognised argument '$a' (expected --key=value)")
        key = replace(m.captures[1], '-' => '_')       # --apply-dir and --apply_dir are the same option
        haskey(opts, key) || error("unknown option --$(m.captures[1])")
        opts[key] = m.captures[2]
    end
    opts["arm"] in ("C0", "C1") || error("--arm must be C0 or C1 (got '$(opts["arm"])')")
    opts["rho"] in ("expected", "recorded") ||
        error("--rho must be expected or recorded (got '$(opts["rho"])')")
    isempty(opts["apply_dir"]) && error("--apply-dir is required")
    return opts
end

# ── the roster reader.  Self-describing: the '#H T' line carries the column names, so nothing here
#    hard-codes the schema (the same rule the sibling harness and the identity gate follow). ───────────
struct Tree
    pft_id::Int
    treeidx::Int
    nind::Float64
    wooddens::Float64
    sla::Float64
    age_haz::Int          # the PRE-increment age the C's own hazard used (`grow` age − 1)
    mort::Float64         # the ported hazard, this year's state
    mort_c::Float64       # the C's own `mort_prob`, for cross-checking only — NEVER an input
    hard::Symbol
end

"""
    read_request(path) -> (year, patch, Vector{Tree})

Parse one rendezvous request and compute the ported hazard for every tree on it.

The request is the `grow` phase — post-growth, pre-kill.  Anything else is a basis error, not a
recoverable one: on the old `pre` rendezvous the stale `bm_inc_counter` inverted the trait differential,
so a silently-accepted `pre` request would produce a plausible, wrong arm-C number.
"""
function read_request(path::AbstractString)
    cols = Dict{String, Int}()
    trees = Tree[]
    year = -1
    patch = -1
    for line in eachline(path)
        if startswith(line, "#H T ")
            cols = Dict(n => i for (i, n) in enumerate(split(line)[3:end]))
            continue
        end
        (isempty(line) || line[1] != 'T') && continue
        isempty(cols) && error("$path: a T record before its '#H T' header")
        f = split(line)[2:end]
        length(f) == length(cols) ||
            error("$path: T record has $(length(f)) fields, header says $(length(cols))")
        gs(n) = f[cols[n]]
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
        # `grow` is dumped AFTER annual_tree's `tree->age++`, so the hazard's basis is age − 1 (the
        # ADR-0035 age off-by-one in a new place; the identity gate makes the same subtraction).
        age_haz = gi("age") - 1
        h = TM.mortality_hazard(
            p; wooddens = gf("wooddens"), sla = gf("sla"), age = age_haz,
            bm_delta = gf("bm_delta"), leafarea = gf("leafarea_real"), leaf_c = gf("leaf_c"),
            water_stress = gf("water_stress"), temp_stress = gf("temp_stress"),
            bm_inc_counter = gi("bm_inc_counter")
        )
        push!(
            trees, Tree(
                gi("pft_id"), gi("treeidx"), gf("nind"), gf("wooddens"), gf("sla"),
                age_haz, h.total, gf("mort_prob"), h.hard_kill
            )
        )
    end
    # order the roster deterministically so the per-patch-year RNG stream maps to the same trees
    # regardless of the order the C happened to write them in
    sort!(trees, by = t -> (t.pft_id, t.treeidx))
    return year, patch, trees
end

# ── ρ from the recorded baseline, for the arm that has to exercise the tilt at θ ≠ 1 ───────────────────
"""
    recorded_rho(dir) -> Dict{(year,patch) => ρ}

The nind-weighted REALIZED survival fraction of the recorded baseline run, read off the `mort` dump phase
(`isdead` there is the demographic verdict; fire runs later and also sets `isdead`, which is why the
sibling harness reads kills from `mort` and not `post` — ADR 0121).

Realized, not expected, is the point: it differs from the hazard's own mean by the C's Bernoulli draw, so
θ comes out scattered around 1 and the bisection is exercised live instead of being pinned to 1 by
construction.
"""
function recorded_rho(dir::AbstractString)
    files = sort(filter(f -> occursin(r"^roster_rank\d+\.txt$", f), readdir(dir)))
    isempty(files) && error("no roster_rank*.txt under $dir")
    alive = Dict{Tuple{Int, Int}, Float64}()
    total = Dict{Tuple{Int, Int}, Float64}()
    seen_grow = false
    for fn in files
        cols = Dict{String, Int}()
        for line in eachline(joinpath(dir, fn))
            if startswith(line, "#H T ")
                cols = Dict(n => i for (i, n) in enumerate(split(line)[3:end]))
                continue
            end
            (isempty(line) || line[1] != 'T') && continue
            f = split(line)[2:end]
            f[cols["phase"]] == "grow" && (seen_grow = true)
            f[cols["phase"]] == "mort" || continue
            k = (parse(Int, f[cols["year"]]), parse(Int, f[cols["patch"]]))
            nind = parse(Float64, f[cols["nind"]])
            total[k] = get(total, k, 0.0) + nind
            parse(Int, f[cols["isdead"]]) == 0 && (alive[k] = get(alive, k, 0.0) + nind)
        end
    end
    seen_grow || error(
        "$dir has no `grow` dump phase: it predates the rendezvous move (ADR 0123) and cannot be a " *
            "reference basis for the current binary. Re-record it (MODE=record scripts/run_rung2_replay_arm.sh)."
    )
    return Dict(k => get(alive, k, 0.0) / v for (k, v) in total if v > 0)
end

# ── the decision ──────────────────────────────────────────────────────────────────────────────────────
"""
    decide(arm, trees, ρ, rng) -> (kills, θ, shortfall, n_target)

C0 hands every tree the same `f_i = ρ`; C1 hands it `(1 − mort_i)^θ` with θ from S's own
`_hazard_tilt`.  The Bernoulli draw is on this side of the interface (ADR 0117 item 1) — which is what
makes a seed ensemble a re-run of the harness rather than of the count model.

`_hazard_tilt` is called with real `FDiff.TreePools`, not a local copy of its arithmetic: it reads only
`is_grass` and `nind` from them, and reusing the shipped solver is the whole reason the θ printed beside
an arm-C result is the θ the coupled emulator would use.
"""
function decide(arm::String, trees::Vector{Tree}, ρ::Float64, rng)
    n_now = sum(t.nind for t in trees; init = 0.0)
    n_target = ρ * n_now
    θ = NaN
    shortfall = 0.0
    f = Vector{Float64}(undef, length(trees))
    if arm == "C0"
        fill!(f, clamp(ρ, 0.0, 1.0))
    else
        haz = [t.mort for t in trees]
        pools = [
            FD.TreePools{Float64}(
                    1.0, 1.0, 1.0, 1.0, 0.0, 1.0, 1.0, t.nind, t.sla, t.wooddens, false
                ) for t in trees
        ]
        if !isempty(trees)
            θ, shortfall = EM._hazard_tilt(haz, pools, n_target, n_now)
            for i in eachindex(trees)
                w = 1.0 - haz[i]
                f[i] = w <= 0.0 ? 0.0 : w^θ
            end
        end
    end
    kills = Tuple{Int, Int}[]
    dead_wd = 0.0
    dead_n = 0.0
    for i in eachindex(trees)
        if rand(rng) > f[i]
            push!(kills, (trees[i].pft_id, trees[i].treeidx))
            dead_wd += trees[i].nind * trees[i].wooddens
            dead_n += trees[i].nind
        end
    end
    return kills, θ, shortfall, n_target, dead_n > 0 ? dead_wd / dead_n : NaN
end

# ── main loop ─────────────────────────────────────────────────────────────────────────────────────────
const REQ_RE = r"req_r(\d+)_y(\d+)_p(\d+)\.ready$"

function main(argv)
    opts = parse_args(argv)
    arm = opts["arm"]
    apply_dir = opts["apply_dir"]
    seed = parse(Int, opts["seed"])
    max_idle = parse(Float64, opts["max_idle"])
    poll = parse(Float64, opts["poll"])
    mkpath(apply_dir)
    log_path = isempty(opts["log"]) ? joinpath(apply_dir, "armc_log.txt") : opts["log"]

    rho_tab = opts["rho"] == "recorded" ? recorded_rho(opts["dump"]) : Dict{Tuple{Int, Int}, Float64}()

    println("rung-2 ARM $arm harness")
    println("  operator  : src/trait_mortality.jl + LPJmLFITEmulator._hazard_tilt (line S, ADR 0047→0049/0117)")
    println("  rho source: ", opts["rho"], opts["rho"] == "recorded" ? "  ($(length(rho_tab)) patch-years)" : "")
    println("  seed      : ", seed)
    println("  apply dir : ", apply_dir)
    println("  log       : ", log_path)
    flush(stdout)

    log = open(log_path, "w")
    println(
        log,
        "#H L year patch n_tree rho rho_c n_target theta shortfall n_kill n_hard_haz " *
            "mean_haz wd_stand wd_dead sel_diff"
    )
    # `ready` lets the job wait for this process instead of racing it: Julia's load time is seconds and
    # the C fails the whole run if no answer arrives within LPJ_RUNG2_APPLY_TIMEOUT.
    isempty(opts["ready"]) || close(open(opts["ready"], "w"))

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
            year, patch, trees = read_request(req_txt)
            ρ = if opts["rho"] == "recorded"
                get(rho_tab, (year, patch)) do
                    error("no recorded rho for year $year patch $patch")
                end
            else
                # the operator's OWN expected survival: ρ = Σ nind(1−mort_i)/Σ nind.  This reads no
                # decision of the C's — only the state the rendezvous publishes, which is rung 2's
                # premise.  It pins θ to 1 analytically, so this arm doubles as a LIVE end-to-end
                # identity check of hazard + tilt + rendezvous; `rho_c` logs the same quantity built
                # from the C's own mort_prob, and the two must agree to solver precision.
                n = sum(t.nind for t in trees; init = 0.0)
                n > 0 ? sum(t.nind * (1 - t.mort) for t in trees) / n : 1.0
            end
            ρ_c = let n = sum(t.nind for t in trees; init = 0.0)
                n > 0 ? sum(t.nind * (1 - t.mort_c) for t in trees) / n : NaN
            end
            rng = Xoshiro(hash((seed, year, patch)))
            kills, θ, shortfall, n_target, wd_dead = decide(arm, trees, ρ, rng)

            base = joinpath(apply_dir, @sprintf("rsp_r%04d_y%05d_p%03d", rank, year, patch))
            open(base * ".txt", "w") do fh
                println(fh, "# arm $arm decision, year $year patch $patch (rho=$(opts["rho"]), seed=$seed)")
                for (pft_id, treeidx) in kills
                    println(fh, "K $pft_id $treeidx")
                end
                println(fh, "ESTAB_C")     # who establishes stays with the C — arm C is a MORTALITY arm
                println(fh, "END")
            end
            close(open(base * ".ready", "w"))

            n_now = sum(t.nind for t in trees; init = 0.0)
            wd_stand = n_now > 0 ? sum(t.nind * t.wooddens for t in trees) / n_now : NaN
            mean_haz = isempty(trees) ? NaN : sum(t.nind * t.mort for t in trees) / n_now
            n_hard = count(t -> t.hard !== :none, trees)
            @printf(
                log, "L %d %d %d %.17g %.17g %.17g %.17g %.17g %d %d %.17g %.17g %.17g %.17g\n",
                year, patch, length(trees), ρ, ρ_c, n_target, θ, shortfall, length(kills), n_hard,
                mean_haz, wd_stand, wd_dead, wd_dead - wd_stand
            )
            flush(log)
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
