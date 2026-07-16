# Gate 5 — Determinism (ENGINEERING_STANDARDS §2, item 5).
# Fixed StableRNGs seed ⇒ bit-identical results across runs. (Base Julia RNG streams are NOT stable
# across versions — StableRNGs.jl is required for reproducible seeded tests.)
@testitem "Determinism" tags = [:determinism] begin
    using LPJmLFITEmulator
    using Test
    using StableRNGs

    seed = 20260716

    # Same seed, two independent runs ⇒ bit-identical (== not just ≈).
    f1 = softmax_partition(randn(StableRNG(seed), 16))
    f2 = softmax_partition(randn(StableRNG(seed), 16))
    @test f1 == f2
    @test sum(f1) ≈ 1.0

    # A different seed generally yields a different partition (sanity: the seed actually matters).
    f3 = softmax_partition(randn(StableRNG(seed + 1), 16))
    @test f1 != f3
end
