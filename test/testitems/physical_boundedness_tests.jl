# Gate 8 — Physical boundedness (ENGINEERING_STANDARDS §2, item 8).
# `softmax_partition` outputs are non-negative and sum to 1 (mass-conserving allocation, fractions
# in [0,1]); `flux_then_integrate` outputs are non-negative regardless of increment sign.
# Property-style coverage via a seeded StableRNGs loop (see conservation_closure_tests.jl for why
# Supposition `@check` is not used inside `@testitem` on the pinned versions).
@testitem "Physical boundedness" tags = [:boundedness] begin
    using LPJmLFITEmulator
    using Test
    using StableRNGs

    rng = StableRNG(808)

    for _ in 1:3000
        # softmax: fractions ≥ 0, ≤ 1, and Σ = 1
        n = rand(rng, 1:32)
        f = softmax_partition(100 .* randn(rng, n))
        @test all(≥(0.0), f)
        @test all(≤(1.0 + 1.0e-12), f)
        @test isapprox(sum(f), 1.0; atol = 1.0e-10)

        # flux_then_integrate: storage stays ≥ 0 for ARBITRARY (signed) increments
        m = rand(rng, 1:16)
        out = flux_then_integrate(1000 .* rand(rng, m), 2000 .* rand(rng, m) .- 1000)
        @test all(≥(0.0), out)
    end

    # ── deterministic anchors ──────────────────────────────────────────────────
    @test all(≥(0.0), softmax_partition([-50.0, 0.0, 50.0]))
    @test sum(softmax_partition([1.0, 2.0, 3.0, 4.0, 5.0])) ≈ 1.0
    @test flux_then_integrate([1.0, 2.0], [-5.0, -5.0]) == [0.0, 0.0]   # clamped at zero
end
