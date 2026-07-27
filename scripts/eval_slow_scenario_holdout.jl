# eval_slow_scenario_holdout.jl — HOLD-OUT-BY-SCENARIO generalization of the pooled Component-S count DRF
# (ADR 0026 §5, the honest UNSEEN-REGIME proof). Reads the POOLED table (pool_slow_tables.py: X.f64 / y.f64 /
# scenario.i64 / manifest.txt with `pooled_scenarios`). For each held-out scenario s: FIT a forest on every
# row NOT in s and PREDICT the rows in s — i.e. train on the other regime(s), test the regime the model never
# saw. Reports per-direction count R²/RMSE + a POOLED held-out-by-cell baseline for context. This is the test
# that a pooled + TRANSIENT-boundary model interpolates to an unseen regime; a static-boundary model cannot
# carry the warming signal, so it is expected to lose on the held-out scenario's warmed tail.
#
#   OUT=/p/tmp/jamirp/emulator_global/slow_count_pooled_w20 julia scripts/eval_slow_scenario_holdout.jl
# ENV: OUT (pooled table dir), NTREES/MAX_DEPTH/MIN_LEAF/SUBSAMPLE (match the production train), KFOLDS (5,
# for the by-cell baseline). Heavy (one forest fit per scenario) → scripts/sbatch_julia.sh (DRF is zero-dep).

include(joinpath(@__DIR__, "..", "src", "drf.jl"))
using .DRF

const DATA = get(ENV, "OUT", "/p/tmp/jamirp/emulator_global/slow_count_pooled_w20")

function read_manifest(path)
    d = Dict{String, String}()
    for line in eachline(path)
        parts = split(line, '\t')
        length(parts) == 2 && (d[parts[1]] = parts[2])
    end
    return d
end

r2score(yt, pt) = (ss = sum((pt .- yt) .^ 2); st = sum((yt .- sum(yt) / length(yt)) .^ 2); st > 0 ? 1 - ss / st : 0.0)
rmse(yt, pt) = sqrt(sum((pt .- yt) .^ 2) / length(yt))

function main()
    man = read_manifest(joinpath(DATA, "manifest.txt"))
    n = parse(Int, man["n"])
    p = parse(Int, man["p"])
    sc_path = joinpath(DATA, "scenario.i64")
    isfile(sc_path) || error("scenario.i64 not found in $DATA — this eval needs a POOLED table (pool_slow_tables.py).")
    tags = haskey(man, "pooled_scenarios") ? split(man["pooled_scenarios"]) : String[]

    Xt = Matrix{Float64}(undef, p, n)
    read!(joinpath(DATA, "X.f64"), Xt)
    X = permutedims(Xt)                       # n×p
    y = Vector{Float64}(undef, n)
    read!(joinpath(DATA, "y.f64"), y)
    scen = Vector{Int64}(undef, n)
    read!(sc_path, scen)
    cells = Vector{Int64}(undef, n)
    read!(joinpath(DATA, "cells.i64"), cells)

    ntrees = parse(Int, get(ENV, "NTREES", "150"))
    max_depth = parse(Int, get(ENV, "MAX_DEPTH", "16"))
    min_leaf = parse(Int, get(ENV, "MIN_LEAF", "20"))
    subsample = parse(Int, get(ENV, "SUBSAMPLE", "200000"))
    kfolds = parse(Int, get(ENV, "KFOLDS", "5"))
    sids = sort(unique(scen))
    name(s) = (s + 1 <= length(tags)) ? tags[s + 1] : "scenario$s"
    @info "loaded pooled table" n p nscenarios = length(sids) ncells = length(unique(cells)) tags

    # ── HOLD-OUT-BY-SCENARIO: train on NOT-s, test on s (the unseen-regime proof) ──
    println("== HOLD-OUT-BY-SCENARIO (train on the other regime(s), test the held-out one) ==")
    for s in sids
        te = scen .== s
        tr = .!te
        (count(te) == 0 || count(tr) == 0) && continue
        f = DRF.fit_forest(
            X[tr, :], y[tr]; ntrees = ntrees, max_depth = max_depth, min_leaf = min_leaf,
            subsample = min(subsample, count(tr)), seed = 1, store_values = false,
        )
        pt = DRF.predict(f, X[te, :])
        println(
            "   held out $(rpad(name(s), 12)) test_rows=$(count(te))  R²=", round(r2score(y[te], pt), digits = 4),
            "  RMSE=", round(rmse(y[te], pt), digits = 3),
            "  (trained on $(count(tr)) rows from the other regime(s))"
        )
    end

    # ── POOLED held-out-BY-CELL baseline (train on all scenarios, hold cells out) for context ──
    println("== POOLED held-out-BY-CELL baseline ($kfolds-fold; trains on ALL scenarios) ==")
    if length(unique(cells)) < kfolds
        println("   (skipped — by-cell CV needs ≥ $kfolds cells; got $(length(unique(cells))))")
        return nothing
    end
    fold = Int[mod(hash(c), kfolds) for c in cells]
    preds = fill(NaN, n)
    for k in 0:(kfolds - 1)
        te = fold .== k
        tr = .!te
        (count(tr) == 0 || count(te) == 0) && continue   # a fold with no train/test cells: leave NaN, skip
        f = DRF.fit_forest(
            X[tr, :], y[tr]; ntrees = ntrees, max_depth = max_depth, min_leaf = min_leaf,
            subsample = min(subsample, count(tr)), seed = 1, store_values = false,
        )
        preds[te] = DRF.predict(f, X[te, :])
    end
    done = .!isnan.(preds)
    println(
        "   pooled by-cell OOS R²=", round(r2score(y[done], preds[done]), digits = 4),
        "  RMSE=", round(rmse(y[done], preds[done]), digits = 3), "  (over $(count(done))/$n rows)"
    )
    # per-scenario slice of the pooled by-cell predictions (does the pooled model serve each regime well?)
    for s in sids
        m = (scen .== s) .& done
        count(m) > 0 && println("     └ ", rpad(name(s), 12), " slice R²=", round(r2score(y[m], preds[m]), digits = 4))
    end
    return nothing
end

main()
