# eval_slow_copula.jl — K-fold-BY-CELL OUT-OF-SAMPLE trait-distribution predictions for the global
# recruit-trait copula (ADR 0025, Phase 4 — the REAL, cross-cell fidelity proof). Each cell's per-axis
# marginal is predicted by axis forests that NEVER trained on it (deterministic cell→fold), so the
# validation figures show genuine generalization, not in-sample fit. One OOS draw per surviving stem per
# axis (deterministic u), pooled per cell downstream.
#
# Per-axis MARGINALS are the fidelity target the figures show; the Gaussian copula only couples the axes
# (the JOINT), it does NOT change any single marginal — so independent per-axis quantile draws are the
# correct, cheaper OOS estimator here (the joint correlation is a separate, secondary check).
#
# Reads the MODE=copula table (Xc.f64 / Y_<axis>.f64 / cells.i64 / manifest_copula.txt) and writes one
# pred_<axis>.f64 (n Float64, aligned to Xc rows) per axis for scripts/plot_slow_emulator_validation.py.
#
#   OUT=/p/tmp/jamirp/emulator_global/slow_copula_historic KFOLDS=5 julia scripts/eval_slow_copula.jl
# ENV: OUT, KFOLDS (5), NTREES/MAX_DEPTH/MIN_LEAF/SUBSAMPLE. Heavy (K×naxes forest fits, store_values) → SLURM.

include(joinpath(@__DIR__, "..", "src", "drf.jl"))
using .DRF

const DATA = get(ENV, "OUT", "/p/tmp/jamirp/emulator_global/slow_copula_historic")

function read_manifest(path)
    d = Dict{String, String}()
    for line in eachline(path)
        parts = split(line, '\t')
        length(parts) == 2 && (d[parts[1]] = parts[2])
    end
    return d
end

function main()
    man = read_manifest(joinpath(DATA, "manifest_copula.txt"))
    n = parse(Int, man["n"])
    ncond = parse(Int, man["ncond"])
    naxes = parse(Int, man["naxes"])
    axes = String.(split(strip(man["axes"])))
    cells_path = joinpath(DATA, "cells.i64")
    isfile(cells_path) || error("cells.i64 not found in $DATA (rebuild with MODE=copula).")

    Xt = Matrix{Float64}(undef, ncond, n)      # Xc.f64 row-major n×ncond
    read!(joinpath(DATA, "Xc.f64"), Xt)
    Xc = permutedims(Xt)
    Ys = Vector{Vector{Float64}}(undef, naxes)
    for (a, ax) in enumerate(axes)
        y = Vector{Float64}(undef, n)
        read!(joinpath(DATA, "Y_$(ax).f64"), y)
        Ys[a] = y
    end
    cells = Vector{Int64}(undef, n)
    read!(cells_path, cells)

    kfolds = parse(Int, get(ENV, "KFOLDS", "5"))
    ntrees = parse(Int, get(ENV, "NTREES", "40"))
    max_depth = parse(Int, get(ENV, "MAX_DEPTH", "14"))
    min_leaf = parse(Int, get(ENV, "MIN_LEAF", "20"))
    subsample = parse(Int, get(ENV, "SUBSAMPLE", "50000"))
    @info "loaded copula table" n ncond naxes axes ncells = length(unique(cells)) kfolds

    fold = Int[mod(hash(c), kfolds) for c in cells]        # each cell in exactly ONE test fold
    preds = [fill(NaN, n) for _ in 1:naxes]
    for k in 0:(kfolds - 1)
        te = fold .== k
        tr = .!te
        ntr = count(tr)
        nte = count(te)
        teidx = findall(te)
        Xtr = Xc[tr, :]
        for (a, ax) in enumerate(axes)
            f = DRF.fit_forest(
                Xtr, Ys[a][tr]; ntrees = ntrees, max_depth = max_depth, min_leaf = min_leaf,
                subsample = min(subsample, ntr), seed = a, store_values = true,
            )
            # The OOS quantile draw per (row, axis) is the eval's dominant cost (~naxes·kfolds·n forest
            # traversals — millions at global scale). PARALLELISE across JULIA_NUM_THREADS: each test row
            # writes a distinct `pa[i]` (no race), and its RNG is seeded per (row, axis) so the result is
            # bit-identical to the serial loop regardless of thread count / schedule. `let` binds
            # single-assignment locals so the `@threads` closure does not box the reassigned `a`/`f`/`teidx`
            # (JET boxed-capture trap, CLAUDE.md §2).
            pa = preds[a]
            let a = a, f = f, pa = pa, ti = teidx
                Threads.@threads for i in ti
                    u = DRF.rand01!(DRF.Xoshiro256pp(i * 131 + a))
                    @inbounds pa[i] = DRF.predict_quantile(f, (@view Xc[i, :]), u)
                end
            end
            println("   axis $(rpad(String(ax), 10)) done (fold $k)"); flush(stdout)
        end
        println("== fold $k/$(kfolds - 1): test_rows=$nte train_rows=$ntr"); flush(stdout)
    end
    for a in 1:naxes
        @assert !any(isnan, preds[a]) "axis $(axes[a]): some rows never in a test fold"
        open(joinpath(DATA, "pred_$(axes[a]).f64"), "w") do io
            write(io, preds[a])
        end
    end

    # pooled per-axis OOS quantile-match (a headline number; the per-cell figures are the real story)
    qs = (0.05, 0.25, 0.5, 0.75, 0.95)
    qof(v) = (s = sort(v); [s[clamp(round(Int, q * length(s)), 1, length(s))] for q in qs])
    for (a, ax) in enumerate(axes)
        pq = qof(preds[a])
        oq = qof(Ys[a])
        iqr = oq[4] - oq[2]
        nq = iqr > 0 ? sqrt(sum((pq .- oq) .^ 2) / length(qs)) / iqr : NaN
        println(
            "== $(rpad(ax, 10)) pooled OOS: pred_q=", round.(pq, sigdigits = 4),
            " obs_q=", round.(oq, sigdigits = 4), " nqrmse=", round(nq, digits = 3)
        )
    end
    println("== wrote pred_<axis>.f64 for $(axes) ($n rows, $kfolds-fold-by-cell)")
    return nothing
end

main()
