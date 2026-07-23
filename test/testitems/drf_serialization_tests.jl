# DRF serialization (P1 Tier-1 Step 4a; ADR 0014/0022). `DRF.save_forest`/`load_forest` round-trip a
# fitted forest through a pure-Base text stream (magic `LPJMLFIT_DRF`) so a PRODUCTION Component-S DRF can
# be trained offline and LOADED by the coupled app with an EMPTY runtime `[deps]`. Committed fixtures are
# text (never *.bin — git-ignored). These testitems gate:
#   • ROUND-TRIP — save→load reproduces the forest BITWISE (predictions strict `==`, both store_values modes,
#     incl. the NaN per-feature fill and the ragged leaf sample values).
#   • GUARDS — load rejects a corrupted magic and an unknown version.
#   • COMMITTED ARTIFACT — the checked-in `drf_forest_hainich.drf` (the production count DRF built by
#     scripts/train_slow_drf.jl) loads and predicts its committed golden (feature-row → value) pairs bitwise
#     (a drift alarm: a silent format or compiler change that moved predictions would fail here).

@testitem "DRF save_forest/load_forest — bitwise round-trip (both store_values modes) + guards" tags = [:unit] begin
    using LPJmLFITEmulator.DRF
    using Test

    function build(sv)
        r = DRF.Xoshiro256pp(11)
        n, p = 600, 8
        X = Matrix{Float64}(undef, n, p)
        y = Vector{Float64}(undef, n)
        for i in 1:n
            for f in 1:p
                X[i, f] = DRF.rand01!(r)
            end
            y[i] = 3.0 * X[i, 1] + sin(6 * X[i, 2]) + 2.0 * X[i, 3] * X[i, 4] + 0.05 * (DRF.rand01!(r) - 0.5)
        end
        X[3, 5] = NaN                      # exercise the per-feature NaN-fill round-trip
        forest = DRF.fit_forest(X, y; ntrees = 40, subsample = 400, max_depth = 14, min_leaf = 5, seed = 7, store_values = sv)
        return forest, X
    end

    for sv in (false, true)
        forest, X = build(sv)
        io = IOBuffer()
        DRF.save_forest(io, forest)
        f2 = DRF.load_forest(IOBuffer(String(take!(io))))

        # struct-level equality (isequal so any NaN fill compares equal)
        @test f2.nfeat == forest.nfeat
        @test f2.store_values == forest.store_values
        @test isequal(f2.fill, forest.fill)
        @test length(f2.trees) == length(forest.trees)
        for (t1, t2) in zip(forest.trees, f2.trees)
            @test t2.feat == t1.feat
            @test t2.left == t1.left
            @test t2.right == t1.right
            @test isequal(t2.thr, t1.thr)
            @test isequal(t2.value, t1.value)
            @test all(isequal(a, b) for (a, b) in zip(t2.values, t1.values))
        end

        # predictions bitwise-identical (identical bits → identical arithmetic ⇒ strict ==)
        @test DRF.predict(forest, X) == DRF.predict(f2, X)
        if sv
            for u in (0.05, 0.5, 0.95)
                q1 = [DRF.predict_quantile(forest, view(X, i, :), u) for i in 1:20]
                q2 = [DRF.predict_quantile(f2, view(X, i, :), u) for i in 1:20]
                @test q1 == q2
            end
        end

        # path round-trip
        tmp = tempname()
        DRF.save_forest(tmp, forest)
        @test DRF.predict(DRF.load_forest(tmp), X) == DRF.predict(forest, X)
        rm(tmp)
    end

    # guards: corrupted magic + unknown version both throw
    forest, _ = build(false)
    io = IOBuffer(); DRF.save_forest(io, forest); s = String(take!(io))
    @test_throws ErrorException DRF.load_forest(IOBuffer(replace(s, "LPJMLFIT_DRF" => "BOGUS_MAGIC0")))
    @test_throws ErrorException DRF.load_forest(IOBuffer(replace(s, "LPJMLFIT_DRF 1" => "LPJMLFIT_DRF 999"; count = 1)))
end

@testitem "Committed production DRF (drf_forest_hainich.drf) loads + predicts its golden pairs bitwise" tags = [:unit, :scientific] begin
    using LPJmLFITEmulator.DRF
    using Test

    refdir = joinpath(@__DIR__, "references")
    forest = DRF.load_forest(joinpath(refdir, "drf_forest_hainich.drf"))
    @test forest isa DRF.Forest

    # parse the committed meta (nfeat + golden feature-row→prediction pairs)
    nfeat = 0
    golden = Tuple{Float64, Vector{Float64}}[]
    for ln in eachline(joinpath(refdir, "drf_forest_hainich_meta.txt"))
        (isempty(strip(ln)) || startswith(strip(ln), "#")) && continue
        parts = split(ln, '\t')
        if parts[1] == "nfeat"
            nfeat = parse(Int, strip(parts[2]))
        elseif parts[1] == "golden"
            pred = parse(Float64, strip(parts[2]))
            feats = parse.(Float64, split(strip(parts[3])))
            push!(golden, (pred, feats))
        end
    end
    @test forest.nfeat == nfeat
    @test !isempty(golden)
    for (pred, feats) in golden
        @test length(feats) == nfeat
        @test DRF.predict(forest, feats) == pred          # bitwise drift alarm
    end
end
