#!/usr/bin/env julia
# diagnose_rung2_rate_draw_replay.jl — is the RATE arms' draw biased, or is the STATISTIC that says so?
#
# WHY THIS EXISTS.  ADR 0242's derivable gate (scripts/diagnose_rung2_rate_flux_identity.py) has three
# panels.  A and C pass exactly.  Panel B — the realized removed density against the arm's own implied
# mean, standardized by the exact variance the harness logs — comes out at |z| up to 4.47 against a
# pre-registered 4.0, with the realized total 0.6 % ABOVE the implied one and the per-leg z distribution
# at mean +0.50, sd 0.992.  A unit sd says the variance formula is right; a shifted mean says something
# is.  Two candidate explanations, and they call for completely different responses:
#
#   (H-draw)  THE DRAW IS BIASED.  Then the arms are wrong and nothing else in ADR 0242 may be read.
#   (H-stat)  THE STATISTIC IS BIASED.  `z` divides by sqrt(sum kill_var), and that denominator is
#             RANDOM and NEGATIVELY correlated with its own numerator: a leg that happens to kill more
#             than implied has a SMALLER stand afterwards, hence smaller later `kill_var`, hence a
#             smaller denominator — so a positive residual is amplified and a negative one damped, and
#             E[z] > 0 even when the residual is exactly zero-mean.  A self-normalized martingale, not a
#             standard normal.  The tell would be that the effect GROWS with how long the feedback has
#             had to act, which is what the by-decade decomposition shows (z +1.02 in the first decade of
#             the ssp370 leg, +3.95 and +3.87 in the seventh and eighth).
#
# THE EXPERIMENT THAT SEPARATES THEM: FREEZE THE FEEDBACK.  Take one leg's rosters exactly as the C
# published them (the `grow` phase of its dump), and re-run ONLY the draw on them, many times, with
# different RNG seeds.  The rosters are then FIXED input, so `sum (1 - f)` is a CONSTANT and the
# Monte-Carlo mean of the realized kill count is an unbiased estimate of the draw's own expectation with
# no feedback anywhere.  If that mean sits on `sum (1 - f)`, H-draw is refuted and H-stat is what is
# left; if it sits above it, the draw is biased and the arm is wrong.
#
# It also re-validates the log: replaying with the harness's OWN per-patch-year seed
# (`Xoshiro(hash((seed, year, patch)))`, trees sorted by `(pft_id, treeidx)`) must reproduce the logged
# `n_kill` for every row — which simultaneously re-proves the ported hazard against FIT's own
# `mort_prob` column, since the dump's value is what this script draws on (ADR 0183 measured
# |dhazard| 5e-18; here it must agree to the last kill).
#
# ⚠ The roster the harness actually saw is the REQUEST file, which is deleted after being served.  The
# dump's `grow` phase is the same state at the same point (that is what the rendezvous is), and the
# check that this identification is right IS the row-by-row `n_kill` reproduction below — if the two
# rosters differed anywhere, the replay could not land on the logged count.
#
# Usage:
#   julia --project=. scripts/diagnose_rung2_rate_draw_replay.jl \
#       --dump=/p/tmp/jamirp/S_rung2/S_r2s_ssp370_c42490_H1_predict_s1_dump \
#       --log=/p/tmp/jamirp/S_rung2/S_r2s_ssp370_c42490_H1_predict_s1_apply/s_arm_log.txt \
#       --seed=1 [--arm=H1] [--reps=400]

using Printf
using Random
using Statistics

function parse_args(argv)
    opts = Dict("dump" => "", "log" => "", "seed" => "1", "arm" => "H1", "reps" => "400")
    for a in argv
        m = match(r"^--([a-z_]+)=(.*)$", a)
        m === nothing && error("unrecognised argument '$a'")
        haskey(opts, m.captures[1]) || error("unknown option --$(m.captures[1])")
        opts[m.captures[1]] = m.captures[2]
    end
    (isempty(opts["dump"]) || isempty(opts["log"])) && error("--dump and --log are required")
    opts["arm"] in ("H0", "H0h", "H1") || error("--arm must be H0, H0h or H1")
    return opts
end

# ── the `grow` rosters, straight out of the dump ───────────────────────────────────────────────────────
# Positions come off the `#H T` header, and name n lives at field n+1 because field 0 is the `T` tag
# (the dump skill's trap 1 — it fails silently between two columns of the same type).
"(year, patch) => (nind, mort_prob) per tree, sorted by (pft_id, treeidx) as the harness sorts."
function grow_rosters(dumpdir::AbstractString)
    path = joinpath(dumpdir, "roster_rank0000.txt")
    isfile(path) || error("no roster_rank0000.txt under $dumpdir")
    cols = Dict{String, Int}()
    out = Dict{Tuple{Int, Int}, Vector{Tuple{Int, Int, Float64, Float64}}}()
    for line in eachline(path)
        if startswith(line, "#H T ")
            cols = Dict(n => i + 1 for (i, n) in enumerate(split(line)[3:end]))
            continue
        end
        startswith(line, "T ") || continue
        isempty(cols) && error("a T record before its '#H T' header")
        f = split(line)
        f[cols["phase"]] == "grow" || continue
        key = (parse(Int, f[cols["year"]]), parse(Int, f[cols["patch"]]))
        v = get!(out, key, Tuple{Int, Int, Float64, Float64}[])
        push!(
            v, (
                parse(Int, f[cols["pft_id"]]), parse(Int, f[cols["treeidx"]]),
                parse(Float64, f[cols["nind"]]), parse(Float64, f[cols["mort_prob"]]),
            )
        )
    end
    for v in values(out)
        sort!(v, by = t -> (t[1], t[2]))
    end
    return out
end

"The logged `n_kill` / `kill_exp` per (year, patch)."
function logged(path::AbstractString)
    head = String[]
    out = Dict{Tuple{Int, Int}, Tuple{Int, Float64}}()
    for line in eachline(path)
        if startswith(line, "#H")
            head = split(line)[2:end]
            continue
        end
        startswith(line, "L ") || continue
        # ⚠ The `#H` line is `#H L year patch …`, so `head` KEEPS the `L` tag as its first entry and the
        # data row must be split WHOLE (tag included) for the two to line up — dropping the tag from one
        # side and not the other makes every row fail the width check and the reader returns EMPTY, which
        # reads exactly like "the log has no rows for this leg". Same family as the dump's header-to-field
        # offset (skill trap 1), one level up.
        f = split(line)
        length(f) == length(head) || continue
        g(n) = f[findfirst(==(n), head)]
        haskey(out, (parse(Int, g("year")), parse(Int, g("patch")))) &&
            error("two log rows for one patch-year")
        out[(parse(Int, g("year")), parse(Int, g("patch")))] =
            (parse(Int, g("n_kill")), parse(Float64, g("kill_exp")))
    end
    return out
end

"The arm's survival fractions on one roster — the same three branches as the harness."
function survival(arm::AbstractString, roster)
    nind = [t[3] for t in roster]
    haz = [t[4] for t in roster]
    n = sum(nind)
    if arm == "H1"
        return [1.0 - h for h in haz]
    elseif arm == "H0"
        h̄ = n <= 0 ? 0.0 : sum(nind[i] * haz[i] for i in eachindex(roster)) / n
        return fill(1.0 - h̄, length(roster))
    else
        cert = [h >= 1.0 for h in haz]
        nfree = sum(nind[i] for i in eachindex(roster) if !cert[i]; init = 0.0)
        hs = sum(nind[i] * haz[i] for i in eachindex(roster) if !cert[i]; init = 0.0)
        h̄d = nfree <= 0 ? 0.0 : hs / nfree
        return [cert[i] ? 0.0 : 1.0 - h̄d for i in eachindex(roster)]
    end
end

function main(argv)
    opts = parse_args(argv)
    seed = parse(Int, opts["seed"])
    reps = parse(Int, opts["reps"])
    arm = opts["arm"]

    println("="^96)
    println("RATE-ARM DRAW REPLAY — is the draw biased, or is panel B's statistic? (ADR 0242)")
    println("  dump : ", opts["dump"])
    println("  log  : ", opts["log"])
    @printf("  arm %s   harness seed %d   Monte-Carlo reps %d\n", arm, seed, reps)
    flush(stdout)

    rosters = grow_rosters(opts["dump"])
    lg = logged(opts["log"])
    keys_common = sort([k for k in keys(rosters) if haskey(lg, k)])
    @printf(
        "  patch-years: dump %d · log %d · in both %d\n",
        length(rosters), length(lg), length(keys_common)
    )
    isempty(keys_common) && error("no patch-year is in both the dump and the log")

    # ── (1) reproduce the log exactly, which is also the identification check ──
    nrep, ndiff, worst_exp = 0, 0, 0.0
    tot_log, tot_replay, tot_exp = 0, 0, 0.0
    for k in keys_common
        r = rosters[k]
        f = survival(arm, r)
        rng = Xoshiro(hash((seed, k[1], k[2])))
        nk = 0
        for i in eachindex(r)
            rand(rng) > f[i] && (nk += 1)
        end
        e = sum(r[i][3] * (1.0 - f[i]) for i in eachindex(r); init = 0.0)
        nrep += 1
        ndiff += nk != lg[k][1]
        worst_exp = max(worst_exp, abs(e - lg[k][2]))
        tot_log += lg[k][1]
        tot_replay += nk
        tot_exp += e
    end
    println()
    println("(1) REPLAY vs THE LOG — the identification check. The dump's `grow` roster must BE the")
    println("    roster the harness was served, and the ported hazard must BE FIT's `mort_prob`, or")
    println("    the replayed kill count cannot land on the logged one.")
    @printf(
        "    rows %d · n_kill differing %d · max |kill_exp replayed - logged| %.3e\n",
        nrep, ndiff, worst_exp
    )
    @printf("    total kills: logged %d · replayed %d\n", tot_log, tot_replay)
    ok1 = ndiff == 0 && worst_exp < 1.0e-12
    println("    -> ", ok1 ? "PASS" : "FAIL")

    # ── (2) FREEZE THE FEEDBACK: re-draw the same fixed rosters many times ──
    # The rosters are now constant input, so `sum (1 - f)` is a CONSTANT and the Monte-Carlo mean of the
    # realized count estimates the draw's own expectation with no trajectory feedback anywhere. This is
    # the panel that separates the two hypotheses.
    exp_count = 0.0
    var_count = 0.0
    for k in keys_common
        r = rosters[k]
        f = survival(arm, r)
        for i in eachindex(r)
            exp_count += 1.0 - f[i]
            var_count += f[i] * (1.0 - f[i])
        end
    end
    counts = Vector{Float64}(undef, reps)
    for rep in 1:reps
        # A rep-dependent seed, so every rep is an independent stream over the SAME rosters. Never
        # `Random.seed!` the global RNG — the point is that only the draw varies.
        c = 0
        for k in keys_common
            r = rosters[k]
            f = survival(arm, r)
            rng = Xoshiro(hash((rep, seed, k[1], k[2], 0x9e3779b9)))
            for i in eachindex(r)
                rand(rng) > f[i] && (c += 1)
            end
        end
        counts[rep] = c
    end
    mc = mean(counts)
    se = std(counts) / sqrt(reps)
    println()
    println("(2) FROZEN-FEEDBACK MONTE CARLO — the same rosters, only the draw varies.")
    @printf("    implied count sum(1-f)        %12.3f\n", exp_count)
    @printf("    per-draw sd sqrt(sum f(1-f))  %12.3f\n", sqrt(var_count))
    @printf("    Monte-Carlo mean over %4d reps %11.3f  (SE %.3f)\n", reps, mc, se)
    @printf(
        "    bias  %+.3f counts = %+.4f %% of the implied total, z = %+.2f\n",
        mc - exp_count, 100 * (mc - exp_count) / exp_count, (mc - exp_count) / se
    )
    @printf(
        "    the harness's own realized count on these rosters: %d (z = %+.2f on one draw)\n",
        tot_replay, (tot_replay - exp_count) / sqrt(var_count)
    )
    ok2 = abs(mc - exp_count) < 4 * se
    println("    -> ", ok2 ? "THE DRAW IS UNBIASED (H-draw REFUTED)" : "THE DRAW IS BIASED (H-draw HOLDS)")

    println()
    println("="^96)
    if ok1 && ok2
        println("VERDICT: the draw is unbiased on frozen rosters and the log reproduces exactly, so")
        println("panel B's positive z is a property of the SELF-NORMALIZED statistic (H-stat), not of")
        println("the operator. Read panel B's RATIO, and test the residual across LEGS (which are")
        println("independent) rather than pooling a within-leg self-normalized sum.")
    end
    return (ok1 && ok2) ? 0 : 1
end

if abspath(PROGRAM_FILE) == @__FILE__
    exit(main(ARGS))
end
