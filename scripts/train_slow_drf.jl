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
# TWO modes (auto-detected from the manifest — global lacks the scalar `boundary`):
#   • Hainich (cell 42490) DEMO — small forest, writes the COMMITTED fixture (defaults). Login-node fast.
#       OUT=/p/tmp/jamirp/slow_runtime julia scripts/train_slow_drf.jl
#   • GLOBAL runtime-consistent DRF (many cells, real LAI_STAND + daily-swc soilmoist, C-truth demography):
#     set DRF_OUT_PATH to a SEPARATE artifact (never the committed fixture) + larger hyperparameters.
#       OUT=/p/tmp/jamirp/emulator_global/slow_runtime_hist NTREES=150 MAX_DEPTH=16 MIN_LEAF=20 \
#       SUBSAMPLE=200000 DRF_OUT_PATH=/p/tmp/jamirp/emulator_global/drf_forest_global_hist.drf \
#       julia scripts/train_slow_drf.jl        # per-cell n_init/age0/boundary stay in cell_meta.parquet
# ENV: OUT (table dir), DRF_OUT_PATH (output .drf; default = committed Hainich fixture), NTREES, MAX_DEPTH,
#      MIN_LEAF, SUBSAMPLE. Heavy/global runs go to SLURM via scripts/sbatch_julia.sh (survives disconnect).

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
    # GLOBAL mode: boundary/n_init/age0 are PER-CELL in cell_meta.parquet (the coupled driver reads that
    # sidecar), NOT manifest scalars — only the single-cell Hainich demo writes them as scalars. Their
    # ABSENCE ⇒ global multi-cell training (one pooled cell-agnostic forest; ADR 0023/0024).
    global_mode = !haskey(man, "boundary")
    boundary = haskey(man, "boundary") ? parse.(Float64, split(strip(man["boundary"]))) : Float64[]
    n_init = haskey(man, "n_init") ? parse(Float64, man["n_init"]) : NaN
    age0 = parse(Float64, get(man, "age0", "0.0"))   # stand-age seed for s.age (ADR 0024 §3)

    # X.f64 is row-major (n×p) → read into a p×n column-major buffer, transpose to n×p (rows = samples)
    Xt = Matrix{Float64}(undef, p, n)
    read!(joinpath(DATA, "X.f64"), Xt)
    X = permutedims(Xt)                       # n×p
    y = Vector{Float64}(undef, n)
    read!(joinpath(DATA, "y.f64"), y)
    @info "loaded" n p nhead nboundary = (p - nhead) target = man["target"] n_init

    # A small, committed-fixture-sized count forest (store_values=false: the count target is a mean).
    # Sized to keep the .drf comparable to the other ~200 KB text fixtures while predicting sensibly.
    # Hyperparameters are ENV-tunable: the committed Hainich demo keeps the small defaults (byte-identical);
    # the GLOBAL run (≈1.3M rows) passes a larger/deeper forest + a per-tree subsample for tractability.
    ntrees = parse(Int, get(ENV, "NTREES", "40"))
    max_depth = parse(Int, get(ENV, "MAX_DEPTH", "8"))
    min_leaf = parse(Int, get(ENV, "MIN_LEAF", "8"))
    subsample = parse(Int, get(ENV, "SUBSAMPLE", string(n)))
    forest = DRF.fit_forest(
        X, y; ntrees = ntrees, max_depth = max_depth, min_leaf = min_leaf, subsample = subsample, seed = 1, store_values = false
    )
    @info "fitted forest" ntrees = length(forest.trees) nfeat = forest.nfeat max_depth min_leaf subsample

    # Output artifact: default = the committed Hainich demo fixture; DRF_OUT_PATH overrides it so the GLOBAL
    # run writes a SEPARATE artifact and NEVER clobbers the committed single-cell test fixture.
    drf_path = get(ENV, "DRF_OUT_PATH", joinpath(REFDIR, "drf_forest_hainich.drf"))
    meta_path = replace(drf_path, r"\.drf$" => "_meta.txt")
    mkpath(dirname(drf_path))
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
    open(meta_path, "w") do io
        scope = global_mode ? "GLOBAL multi-cell ($(man["scenario"]), $(get(man, "ncells", "?")) cells)" : "Hainich cell 42490"
        println(io, "# Production Component-S count DRF ($scope) — metadata for the in-loop load test.")
        println(io, "# Built by scripts/train_slow_drf.jl from scripts/build_slow_runtime_table.py output.")
        println(io, "# Feature order = src/components/slow.jl::flux_feature_vector (11 head + boundary tail).")
        println(io, "nfeat\t", forest.nfeat)
        println(io, "nhead\t", nhead)
        println(io, "ntrees\t", length(forest.trees))
        println(io, "target\t", man["target"])
        println(io, "colnames\t", join(colnames, " "))
        if global_mode
            # per-cell n_init/age0/boundary live in the sidecar the coupled driver reads
            println(io, "cell_meta\t", get(man, "cell_meta", "cell_meta.parquet"))
            println(io, "scenario\t", man["scenario"])
        else
            println(io, "n_init\t", n_init)
            println(io, "age0\t", age0)
            println(io, "boundary\t", join((string(x) for x in boundary), " "))
        end
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
