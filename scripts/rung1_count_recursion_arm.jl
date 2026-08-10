# rung1_count_recursion_arm.jl — RUNG 1, ARM A1: the FLUX-FORCED, STATE-RECURSED count arm (ADR 0112).
#
# WHY. Every published global Component-S number is a ONE-STEP TEACHER-FORCED score (ADR 0112 §1): the
# production count model is handed LPJmL-FIT's own roster and fluxes for the same patch-year, INCLUDING
# `n_prev` = FIT's own stem count for the previous year, and `eval_slow_drf.jl` predicts each row from that
# row's own features. A persistence null that copies `n_prev` and learns nothing already reaches R² 0.962 and
# a deattenuated response slope of 1.029, so the one-step basis cannot tell the emulator apart from copying.
#
# THIS ARM CHANGES EXACTLY ONE THING. Year t's own prediction is fed in as year t+1's `n_prev`, per
# (Cell, Patch) chain. Everything else — the four flux features, the six other roster-state features, the
# static boundary, the K-fold-by-cell split, the forest hyper-parameters and the RNG seed — is IDENTICAL to
# the A0 evaluation, so A1 − A0 is the recursion and nothing else. The forests are refit here with the same
# `fold = mod(hash(cell), KFOLDS)` rule and `seed = 1`, which reproduces A0's forests exactly.
#
# ⚠ A1 IS A STRICT LOWER BOUND ON FREE-RUNNING ERROR, and must be quoted as one. In a real rollout
# `agb`/`lai`/`fpc`/`hmean`/`hmax`/`age_mean` would also come from the emulator's own roster; here they stay
# at FIT's values because reproducing them needs individuals and allometry (rung 2/4, line M's harness).
#
# ⚠ THE CHAIN IS NOT INFERABLE FROM THE FROZEN TABLE. The production table predates ADR 0108 and ships no
# year or patch, and both shortcuts fail on the real data (ADR 0112 §5: equal-length blocking is wrong for
# 24.8 % of historic and 49.9 % of ssp370 cells; segmenting on `n_prev[i+1] == y[i]` silently MERGES adjacent
# patches that join on the same small integer). So the keys come from `scripts/attach_count_table_keys.py`,
# which PROVED its alignment row-for-row against `y.f64`, `X[:, n_prev]` and `cells.i64` before writing them.
# Rows carrying year = -1 are DROPPED here, never guessed.
#
# WHAT IT WRITES. A `COUNT_DIR`-shaped directory (`preds_oos.f64` + symlinked provenance + a manifest), so the
# arm is scored by the ONE canonical yardstick alongside A0 and the null, in one process, on one cell set:
#     COUNT_DIR=<A0>,<null>,<this> scripts/sbatch_python.sh S-yardarms scripts/diagnose_truth_yardstick.py
#
# WHAT IT PRINTS. The overall OOS R², and — the diagnostic the one-step basis cannot produce — the error as a
# function of LEAD TIME: for each step s along a chain, the bias and RMSE of A1 against FIT's truth next to
# A0's on the same rows. A recursion that accumulates error shows a growing spread; one that does not refutes
# ADR 0112's prediction 1.
#
# Usage (SLURM — the guard blocks login-node Julia probes, CLAUDE.md §2; EXPORT the knobs, sbatch_julia.sh
# forwards nothing explicitly):
#     export SRC=/p/tmp/jamirp/emulator_global/slow_count_pooled_w20_t8
#     export KEYS=/p/tmp/jamirp/emulator_global/rung1_keys_t8
#     export OUT=/p/tmp/jamirp/emulator_global/rung1_count_arm_a1
#     NCPUS=48 TIME=04:00:00 PARTITION=priority QOS=priority WARMUP=0 \
#       scripts/sbatch_julia.sh S-a1 scripts/rung1_count_recursion_arm.jl
# ENV: SRC, KEYS, OUT, KFOLDS (5), NTREES (150), MAX_DEPTH (16), MIN_LEAF (20), SUBSAMPLE (200000) — the last
#      five MUST match the production train/eval or A1 − A0 is not the recursion.

include(joinpath(@__DIR__, "..", "src", "drf.jl"))
using .DRF

const SRC = get(ENV, "SRC", "/p/tmp/jamirp/emulator_global/slow_count_pooled_w20_t8")
const KEYS = get(ENV, "KEYS", "/p/tmp/jamirp/emulator_global/rung1_keys_t8")
const OUT = get(ENV, "OUT", "/p/tmp/jamirp/emulator_global/rung1_count_arm_a1")

function read_manifest(path)
    d = Dict{String, String}()
    for line in eachline(path)
        parts = split(line, '\t')
        length(parts) == 2 && (d[parts[1]] = parts[2])
    end
    return d
end

r2score(yt, pt) = (ss = sum((pt .- yt) .^ 2); m = sum(yt) / length(yt); st = sum((yt .- m) .^ 2); st > 0 ? 1 - ss / st : 0.0)

read_vec(path, T, n) = (v = Vector{T}(undef, n); read!(path, v); v)

"""
Chains of consecutive years within one (scenario, Cell, Patch), as contiguous runs of `ord`.

`ord` must already be sorted by (scenario, Cell, Patch, Year). Returns `(starts, lens)` as positions INTO
`ord`, sorted by DECREASING length so that the set of chains still alive at step `s` is a prefix `1:na(s)` —
which is what makes the marching loop below a handful of batched predictions instead of a per-row loop.
"""
function build_chains(ord, scen, cells, patches, years)
    starts = Int[]
    lens = Int[]
    n = length(ord)
    n == 0 && return starts, lens
    s = 1
    @inbounds for i in 2:n
        a, b = ord[i - 1], ord[i]
        newchain = scen[b] != scen[a] || cells[b] != cells[a] || patches[b] != patches[a] ||
            years[b] != years[a] + 1
        if newchain
            push!(starts, s)
            push!(lens, i - s)
            s = i
        end
    end
    push!(starts, s)
    push!(lens, n - s + 1)
    perm = sortperm(lens; rev = true)
    return starts[perm], lens[perm]
end

function main()
    man = read_manifest(joinpath(SRC, "manifest.txt"))
    n = parse(Int, man["n"])
    p = parse(Int, man["p"])
    colnames = split(man["colnames"], ' ')
    jn = findfirst(==("n_prev"), colnames)
    jn === nothing && error("no `n_prev` column in $SRC — this arm has nothing to recurse")
    scen_file = get(man, "scenario_tag", "scenario.i64")

    println("== SRC=$SRC  n=$n  p=$p  n_prev is column $jn")
    Xt = Matrix{Float64}(undef, p, n)
    read!(joinpath(SRC, "X.f64"), Xt)
    X = permutedims(Xt)                       # n×p, row-major access for predict
    Xt = Matrix{Float64}(undef, 0, 0)         # release the transpose before the fold copies
    GC.gc()
    y = read_vec(joinpath(SRC, "y.f64"), Float64, n)
    cells = read_vec(joinpath(SRC, "cells.i64"), Int64, n)
    scen = read_vec(joinpath(SRC, scen_file), Int64, n)
    years = read_vec(joinpath(KEYS, "years.i64"), Int64, n)
    patches = read_vec(joinpath(KEYS, "patches.i64"), Int64, n)

    nkeyed = count(>=(0), years)
    println("== keys from $KEYS: $nkeyed/$n rows keyed ($(round(100 * nkeyed / n, digits = 4)) %)")
    nkeyed == 0 && error("no keyed rows — run scripts/attach_count_table_keys.py first")
    maximum(patches) < 64 || error("Patch index >= 64 breaks the composite sort key below")

    a0path = joinpath(SRC, "preds_oos.f64")
    a0 = isfile(a0path) ? read_vec(a0path, Float64, n) : Float64[]

    kfolds = parse(Int, get(ENV, "KFOLDS", "5"))
    ntrees = parse(Int, get(ENV, "NTREES", "150"))
    max_depth = parse(Int, get(ENV, "MAX_DEPTH", "16"))
    min_leaf = parse(Int, get(ENV, "MIN_LEAF", "20"))
    subsample = parse(Int, get(ENV, "SUBSAMPLE", "200000"))
    println(
        "== KFOLDS=$kfolds NTREES=$ntrees MAX_DEPTH=$max_depth MIN_LEAF=$min_leaf SUBSAMPLE=$subsample "
            * "(must equal the production train/eval)"
    )
    flush(stdout)

    fold = Int[mod(hash(c), kfolds) for c in cells]      # IDENTICAL rule to eval_slow_drf.jl
    preds = fill(NaN, n)
    # lead-time diagnostics, accumulated over all folds
    maxstep = 0
    step_n = Int[]
    step_se = Float64[]
    step_bias = Float64[]
    step_se0 = Float64[]      # the same rows, scored for A0 — the one-step arm's error at the same lead time
    step_bias0 = Float64[]

    for k in 0:(kfolds - 1)
        te = (fold .== k) .& (years .>= 0)
        tr = (fold .!= k)                                 # train on ALL other cells' rows, as A0 does
        ntr = count(tr)
        f = DRF.fit_forest(
            X[tr, :], y[tr]; ntrees = ntrees, max_depth = max_depth, min_leaf = min_leaf,
            subsample = min(subsample, ntr), seed = 1, store_values = false,
        )
        rows = findall(te)
        # sort by (scenario, Cell, Patch, Year) so chains are contiguous runs — one composite Int64 key
        # instead of 24M tuples (same order, a fraction of the memory)
        key = [((scen[r] * 67421 + cells[r]) * 64 + patches[r]) * 4096 + years[r] for r in rows]
        ord = rows[sortperm(key)]
        key = Int64[]
        starts, lens = build_chains(ord, scen, cells, patches, years)
        nch = length(lens)
        L = isempty(lens) ? 0 : lens[1]
        maxstep = max(maxstep, L)
        while length(step_n) < maxstep
            push!(step_n, 0); push!(step_se, 0.0); push!(step_bias, 0.0)
            push!(step_se0, 0.0); push!(step_bias0, 0.0)
        end
        println(
            "== fold $k: test_rows=$(length(rows))  chains=$nch  max_len=$L  " *
                "median_len=$(isempty(lens) ? 0 : lens[cld(nch, 2)])"
        )
        flush(stdout)

        prevpred = Vector{Float64}(undef, nch)
        buf = Matrix{Float64}(undef, nch, p)              # reused; only the first na rows are used per step
        for s in 1:L
            na = searchsortedlast(lens, s; rev = true)    # chains with lens >= s are the prefix 1:na
            na == 0 && break
            @inbounds for c in 1:na
                r = ord[starts[c] + s - 1]
                for j in 1:p
                    buf[c, j] = X[r, j]
                end
                if s > 1
                    buf[c, jn] = prevpred[c]              # <-- THE ARM: our own answer, not FIT's
                end
            end
            ŷ = DRF.predict(f, @view buf[1:na, :])
            @inbounds for c in 1:na
                r = ord[starts[c] + s - 1]
                preds[r] = ŷ[c]
                prevpred[c] = ŷ[c]
                d = ŷ[c] - y[r]
                step_se[s] += d * d
                step_bias[s] += d
                step_n[s] += 1
                if !isempty(a0)
                    d0 = a0[r] - y[r]
                    step_se0[s] += d0 * d0
                    step_bias0[s] += d0
                end
            end
        end
        keyedfold = count(te)
        done = count(!isnan, preds)
        println(
            "   fold $k done: $keyedfold keyed test rows, $done predicted so far; " *
                "fold R²=$(round(r2score(y[rows], preds[rows]), digits = 4))"
        )
        flush(stdout)
    end

    ok = .!isnan.(preds)
    nok = count(ok)
    println(
        "\n== A1 (flux-forced, state-recursed) OOS R² = $(round(r2score(y[ok], preds[ok]), digits = 6)) " *
            "on $nok rows"
    )
    if !isempty(a0)
        println(
            "== A0 (one-step, C-forced)      OOS R² = $(round(r2score(y[ok], a0[ok]), digits = 6)) " *
                "on the SAME rows"
        )
        println("\n--- ERROR VS LEAD TIME (years since the chain was last given FIT's own count) ---")
        println("    step         rows      A1 bias      A1 RMSE      A0 bias      A0 RMSE")
        for s in 1:maxstep
            step_n[s] == 0 && continue
            (s <= 12 || s % 10 == 0 || s == maxstep) || continue
            m = step_n[s]
            println(
                "  ", lpad(s, 6), lpad(m, 13), "  ",
                lpad(round(step_bias[s] / m, digits = 4), 11), "  ",
                lpad(round(sqrt(step_se[s] / m), digits = 4), 11), "  ",
                lpad(round(step_bias0[s] / m, digits = 4), 11), "  ",
                lpad(round(sqrt(step_se0[s] / m), digits = 4), 11)
            )
        end
    end

    mkpath(OUT)
    open(joinpath(OUT, "preds_oos.f64"), "w") do io
        write(io, preds)
    end
    for fn in ["cells.i64", "y.f64", scen_file]
        dst = joinpath(OUT, fn)
        (islink(dst) || isfile(dst)) && rm(dst)
        symlink(abspath(joinpath(SRC, fn)), dst)
    end
    open(joinpath(OUT, "manifest.txt"), "w") do io
        for (k, v) in man
            println(io, "$k\t$v")
        end
        println(io, "arm\tA1 flux-forced, state-recursed (ADR 0112)")
        println(io, "arm_source\t$SRC")
        println(io, "keys\t$KEYS")
        println(io, "recursed_features\tn_prev")
        println(io, "held_at_truth\tbm_inc_cell growth_eff water_stress soilmoist hmean hmax agb lai fpc age_mean")
        println(
            io, "note\tSTRICT LOWER BOUND on free-running error — the six other roster-state features " *
                "still come from LPJmL-FIT"
        )
        println(io, "predicted_rows\t$nok")
    end
    println("\n== wrote $OUT/preds_oos.f64 ($nok of $n rows predicted; unkeyed rows carry NaN)")
    return nothing
end

main()
