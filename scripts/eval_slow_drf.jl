# eval_slow_drf.jl — K-fold-BY-CELL cross-validated OUT-OF-SAMPLE predictions for the global Component-S
# count DRF, so validation figures show genuine generalization (each cell predicted by a forest that never
# saw it) rather than in-sample fit. Reads the runtime-consistent table built by build_slow_runtime_table.py
# (X.f64 / y.f64 / cells.i64 / manifest.txt) and writes preds_oos.f64 (per-row OOS prediction, aligned to X
# rows) into the same dir for scripts/plot_slow_emulator_validation.py to map.
#
#   OUT=/p/tmp/jamirp/emulator_global/slow_runtime_historic KFOLDS=5 julia scripts/eval_slow_drf.jl
# ENV: OUT (table dir), KFOLDS (5), NTREES/MAX_DEPTH/MIN_LEAF/SUBSAMPLE (must match the production train).
# Heavy (K forest fits) → run via scripts/sbatch_julia.sh (DRF is zero-dep pure-Base; no --project needed).

include(joinpath(@__DIR__, "..", "src", "drf.jl"))
using .DRF

const DATA = get(ENV, "OUT", "/p/tmp/jamirp/emulator_global/slow_runtime_historic")

function read_manifest(path)
    d = Dict{String, String}()
    for line in eachline(path)
        parts = split(line, '\t')
        length(parts) == 2 && (d[parts[1]] = parts[2])
    end
    return d
end

r2score(yt, pt) = (ss = sum((pt .- yt) .^ 2); st = sum((yt .- sum(yt) / length(yt)) .^ 2); st > 0 ? 1 - ss / st : 0.0)

function main()
    man = read_manifest(joinpath(DATA, "manifest.txt"))
    n = parse(Int, man["n"])
    p = parse(Int, man["p"])
    cells_path = joinpath(DATA, "cells.i64")
    isfile(cells_path) || error("cells.i64 not found in $DATA — rebuild the table with the updated builder (emits cells.i64).")

    Xt = Matrix{Float64}(undef, p, n)
    read!(joinpath(DATA, "X.f64"), Xt)
    X = permutedims(Xt)                       # n×p
    y = Vector{Float64}(undef, n)
    read!(joinpath(DATA, "y.f64"), y)
    cells = Vector{Int64}(undef, n)
    read!(cells_path, cells)

    kfolds = parse(Int, get(ENV, "KFOLDS", "5"))
    ntrees = parse(Int, get(ENV, "NTREES", "150"))
    max_depth = parse(Int, get(ENV, "MAX_DEPTH", "16"))
    min_leaf = parse(Int, get(ENV, "MIN_LEAF", "20"))
    subsample = parse(Int, get(ENV, "SUBSAMPLE", "200000"))
    @info "loaded" n p ncells = length(unique(cells)) kfolds ntrees max_depth min_leaf subsample

    fold = Int[mod(hash(c), kfolds) for c in cells]     # deterministic cell→fold (each cell in ONE test fold)
    preds = Vector{Float64}(undef, n)
    fill!(preds, NaN)
    for k in 0:(kfolds - 1)
        te = fold .== k
        tr = .!te
        ntr = count(tr)
        nte = count(te)
        f = DRF.fit_forest(
            X[tr, :], y[tr]; ntrees = ntrees, max_depth = max_depth, min_leaf = min_leaf,
            subsample = min(subsample, ntr), seed = 1, store_values = false,
        )
        preds[te] = DRF.predict(f, X[te, :])
        println("== fold $k/$(kfolds - 1): test_rows=$nte  fold OOS R²=", round(r2score(y[te], preds[te]), digits = 4))
    end
    @assert !any(isnan, preds) "some rows never assigned to a test fold"

    open(joinpath(DATA, "preds_oos.f64"), "w") do io
        write(io, preds)
    end
    println(
        "== OOS ($kfolds-fold-by-cell) R² = ", round(r2score(y, preds), digits = 4),
        "  RMSE = ", round(sqrt(sum((preds .- y) .^ 2) / n), digits = 3),
        "  → wrote preds_oos.f64 ($n rows)"
    )
    return nothing
end

main()
