# Train + serialize the PRODUCTION Component-S count DRF (P1 Tier-1 Step 4a).
#
# Reads the runtime-consistent training payload built by scripts/build_slow_runtime_table.py (X.f64 /
# y.f64 / manifest.txt — feature columns in the EXACT src/components/slow.jl::flux_feature_vector order,
# 11 head + baked boundary tail; target = n_living per patch), fits the zero-dependency native-Julia DRF
# (src/drf.jl, ADR 0022), and SERIALIZES it with DRF.save_forest (pure-Base text, ADR 0014). The coupled
# FluxDrivenSlowEmulator loads this exact artifact at runtime (closing the gap that the in-loop test used
# an in-test DRF).
#
# Writes two COMMITTED text artifacts (never *.bin — that pattern is git-ignored):
#   test/testitems/references/drf_forest_hainich.drf        the serialized DRF.Forest
#   test/testitems/references/drf_forest_hainich_meta.txt   nfeat/nhead/boundary/n_init/colnames + golden
#                                                           (feature-row → prediction) pairs the load test asserts
#
# Hainich (cell 42490) DEMONSTRATION artifact — small forest, committed. The GLOBAL runtime-consistent
# DRF (many cells, C LAI_STAND + daily swc for the two proxy channels, C-truth demography target) is the
# Phase-2 SLURM follow-up. Run on the login node (fast, single cell) or via scripts/sbatch_julia.sh.
#   OUT=/p/tmp/jamirp/slow_runtime julia --project=. scripts/train_slow_drf.jl

include(joinpath(@__DIR__, "..", "src", "drf.jl"))
using .DRF

const DATA = get(ENV, "OUT", "/p/tmp/jamirp/slow_runtime")
const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")

function read_manifest(path)
    d = Dict{String, String}()
    for line in eachline(path)
        parts = split(line, '\t')
        length(parts) == 2 && (d[parts[1]] = parts[2])
    end
    return d
end

function main()
    man = read_manifest(joinpath(DATA, "manifest.txt"))
    n = parse(Int, man["n"])
    p = parse(Int, man["p"])
    nhead = parse(Int, man["nhead"])
    colnames = String.(split(strip(man["colnames"])))
    boundary = parse.(Float64, split(strip(man["boundary"])))
    n_init = parse(Float64, man["n_init"])

    # X.f64 is row-major (n×p) → read into a p×n column-major buffer, transpose to n×p (rows = samples)
    Xt = Matrix{Float64}(undef, p, n)
    read!(joinpath(DATA, "X.f64"), Xt)
    X = permutedims(Xt)                       # n×p
    y = Vector{Float64}(undef, n)
    read!(joinpath(DATA, "y.f64"), y)
    @info "loaded" n p nhead nboundary = (p - nhead) target = man["target"] n_init

    # A small, committed-fixture-sized count forest (store_values=false: the count target is a mean).
    # Sized to keep the .drf comparable to the other ~200 KB text fixtures while predicting sensibly.
    ntrees = parse(Int, get(ENV, "NTREES", "40"))
    forest = DRF.fit_forest(
        X, y; ntrees = ntrees, max_depth = 8, min_leaf = 8, subsample = n, seed = 1, store_values = false
    )
    @info "fitted forest" ntrees = length(forest.trees) nfeat = forest.nfeat

    mkpath(REFDIR)
    drf_path = joinpath(REFDIR, "drf_forest_hainich.drf")
    DRF.save_forest(drf_path, forest)
    sz = filesize(drf_path)
    @info "serialized" drf_path bytes = sz

    # round-trip self-check (must be bitwise on this machine)
    f2 = DRF.load_forest(drf_path)
    pfull = DRF.predict(forest, X)
    p2 = DRF.predict(f2, X)
    @assert pfull == p2 "save/load round-trip changed predictions!"

    # golden (feature-row → prediction) pairs for the committed drift-alarm load test
    golden_rows = unique(clamp.([1, n ÷ 4, n ÷ 2, 3 * n ÷ 4, n], 1, n))
    open(joinpath(REFDIR, "drf_forest_hainich_meta.txt"), "w") do io
        println(io, "# Production Component-S count DRF (Hainich cell 42490) — metadata for the in-loop load test.")
        println(io, "# Built by scripts/train_slow_drf.jl from scripts/build_slow_runtime_table.py output.")
        println(io, "# Feature order = src/components/slow.jl::flux_feature_vector (11 head + boundary tail).")
        println(io, "nfeat\t", forest.nfeat)
        println(io, "nhead\t", nhead)
        println(io, "ntrees\t", length(forest.trees))
        println(io, "n_init\t", n_init)
        println(io, "target\t", man["target"])
        println(io, "colnames\t", join(colnames, " "))
        println(io, "boundary\t", join((string(x) for x in boundary), " "))
        # golden pairs: <pred> <feat1..featp>  (the load test asserts predict(loaded, feats) == pred bitwise)
        for r in golden_rows
            feats = X[r, :]
            println(io, "golden\t", string(pfull[r]), "\t", join((string(x) for x in feats), " "))
        end
    end
    @info "wrote meta + golden pairs" ngolden = length(golden_rows)

    # quick skill sanity (not asserted): in-sample R² of the count model
    ȳ = sum(y) / n
    ss_res = sum((pfull .- y) .^ 2)
    ss_tot = sum((y .- ȳ) .^ 2)
    r2 = ss_tot > 0 ? 1 - ss_res / ss_tot : 0.0
    println("== count DRF in-sample R² = ", round(r2, digits = 4), "  (n=$n, ntrees=$(length(forest.trees)), .drf=$(sz) bytes)")
    return nothing
end

main()
