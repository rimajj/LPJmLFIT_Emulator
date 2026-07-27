# Phase 1 (ADR 0025) — serialization + canonical recruit mapping for the recruit-trait Gaussian copula.
# The copula MACHINERY (GaussianCopula/sample_copula!/predict_quantile) and the opt-in establishment hook
# already exist + are gated by `slow_membership_tests.jl`; these testitems gate the two NEW pieces that let a
# PRODUCTION copula bundle be committed as a text artifact and loaded at runtime:
#   • DRF.save_copula / DRF.load_copula — a `.rcop` text round-trip that reproduces a `sample_copula!` draw
#     BITWISE (the same discipline as the `.drf` forest round-trip), walking several embedded axis forests in
#     one token stream via the closure-free `_parse_forest` (JET-safe).
#   • make_recruit_to_pools(axis_names) — rebuilds the (unserialized) `to_pools` mapping from the axis names:
#     overwrites only SLA/Wooddens (the F_diff-consumed axes), keeps the sapl's carbon UNCHANGED (⇒ the
#     establishment debit is independent of the draw ⇒ conservation unaffected), re-derives height/crown.

@testitem "Recruit copula .rcop serialization round-trips sample_copula! bitwise (ADR 0025)" tags = [:scientific] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.DRF
    using Test

    # a per-axis flux-conditioned marginal DRF (store_values=true) whose target is lo..hi keyed on feature 1
    function axis_forest(seed, lo, hi; nf = 3)
        r = DRF.Xoshiro256pp(seed)
        m = 1500
        X = Matrix{Float64}(undef, m, nf)
        y = Vector{Float64}(undef, m)
        for i in 1:m
            for ff in 1:nf
                X[i, ff] = DRF.rand01!(r)
            end
            y[i] = lo + (hi - lo) * X[i, 1]
        end
        return DRF.fit_forest(X, y; ntrees = 25, subsample = 800, mtry = nf, seed = seed, store_values = true)
    end

    R = [1.0 0.4 0.1; 0.4 1.0 -0.2; 0.1 -0.2 1.0]     # 3-axis correlation → factored to a Cholesky L
    cop = DRF.GaussianCopula(R)
    axis_forests = [axis_forest(11, 0.005, 0.07), axis_forest(12, 7.0e4, 6.5e5), axis_forest(13, 0.05, 0.75)]
    axis_names = ["SLA", "Wooddens", "minwscal"]
    cond_cols = ["bm_inc_cell", "growth_eff", "water_stress"]
    x = [0.31, 0.52, 0.18]

    draws_before = [DRF.sample_copula!(DRF.Xoshiro256pp(s), cop, axis_forests, x) for s in 1:25]

    dir = mktempdir()
    path = joinpath(dir, "recruit_copula.rcop")
    ret = DRF.save_copula(path, cop, axis_forests, axis_names, cond_cols, x)
    @test ret == path                                # path-returning contract
    cop2, af2, x2, names2, cols2 = DRF.load_copula(path)

    @test names2 == axis_names                       # header fields round-trip exactly
    @test cols2 == cond_cols
    @test x2 == x
    @test cop2.d == cop.d
    @test cop2.L == cop.L                            # Cholesky serialized DIRECTLY (no re-factor)

    draws_after = [DRF.sample_copula!(DRF.Xoshiro256pp(s), cop2, af2, x2) for s in 1:25]
    @test draws_before == draws_after                # BITWISE round-trip of the full correlated draw

    # IO round-trip (the io methods, not just path) is byte-identical too
    buf = IOBuffer()
    DRF.save_copula(buf, cop, axis_forests, axis_names, cond_cols, x)
    seekstart(buf)
    cop3, af3, _, names3, _ = DRF.load_copula(buf)
    @test names3 == axis_names
    @test [DRF.sample_copula!(DRF.Xoshiro256pp(s), cop3, af3, x) for s in 1:5] ==
        [DRF.sample_copula!(DRF.Xoshiro256pp(s), cop, axis_forests, x) for s in 1:5]

    # bad magic errors
    badpath = joinpath(dir, "bad.rcop")
    open(io -> println(io, "NOT_A_COPULA 1"), badpath, "w")
    @test_throws ErrorException DRF.load_copula(badpath)
end

@testitem "make_recruit_to_pools maps a draw onto a recruit: SLA/Wooddens overwritten, carbon preserved (ADR 0025)" tags = [:scientific] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.Allometry
    using Test

    allom = TreeAllometry{Float64}()
    # a fixed sapling with ALL five carbon pools populated (incl heartwood + below-ground sapwood)
    sapl = TreePools{Float64}(15.0, 30.0, 5.0, 15.0, 8.0, 2.0, 0.5, 1.0, 0.02, 2.0e5, false)

    # axis order is DELIBERATELY not {SLA,Wooddens,...} — the mapping must locate them BY NAME
    to_pools = make_recruit_to_pools(["minwscal", "SLA", "Wooddens"])
    traits = [0.4, 0.035, 3.0e5]                     # minwscal, SLA, Wooddens
    rec = to_pools(traits, sapl, allom)

    @test rec isa TreePools{Float64}
    @test rec.sla == 0.035                           # SLA overwritten from the draw (by name, index 2)
    @test rec.wooddens == 3.0e5                      # Wooddens overwritten from the draw (by name, index 3)
    @test !rec.is_grass
    @test rec.nind == 1.0                            # placeholder; the establishment path sets nind = dn

    # every carbon pool is inherited UNCHANGED from sapl ⇒ vegc (the establishment debit) is draw-independent
    @test rec.leaf_c == sapl.leaf_c
    @test rec.sapwood_c == sapl.sapwood_c
    @test rec.heartwood_c == sapl.heartwood_c
    @test rec.root_c == sapl.root_c
    @test rec.sapwood_bg_c == sapl.sapwood_bg_c
    @test FDiff.vegc_full_ind(rec) == FDiff.vegc_full_ind(sapl)

    # height re-derived from the pipe model with the DRAWN traits; crown from the Jucker allometry
    h_expect = allom.k_latosa * sapl.sapwood_c / (sapl.leaf_c * 0.035 * 3.0e5)
    @test rec.height ≈ h_expect
    @test rec.crownarea ≈ Allometry.crown_area(allom, h_expect)

    # clamps guard pathological tail draws (SLA/Wooddens forced back into support)
    rec_hi = to_pools([0.4, 999.0, 9.9e9], sapl, allom)
    @test 1.0e-3 ≤ rec_hi.sla ≤ 0.1
    @test 5.0e4 ≤ rec_hi.wooddens ≤ 7.0e5

    # Float32 type-stability (the SpeedyWeather coupling type)
    sapl32 = TreePools{Float32}(15.0f0, 30.0f0, 5.0f0, 15.0f0, 8.0f0, 2.0f0, 0.5f0, 1.0f0, 0.02f0, 2.0f5, false)
    rec32 = to_pools([0.4, 0.035, 3.0e5], sapl32, TreeAllometry{Float32}())
    @test rec32 isa TreePools{Float32}
    @test rec32.sla isa Float32

    # missing a required axis ⇒ error
    @test_throws ErrorException make_recruit_to_pools(["SLA", "minwscal"])       # no Wooddens
    @test_throws ErrorException make_recruit_to_pools(["Wooddens", "D95max"])    # no SLA
end
