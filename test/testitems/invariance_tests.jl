# Gate 7 — Invariance / metamorphic (ENGINEERING_STANDARDS §2, item 7).
# Known symmetries hold: `softmax_partition` is shift-invariant (adding a constant to all logits
# leaves the partition unchanged); `latent_heat` is linear in ET.
# Property-style coverage via a seeded StableRNGs loop (see conservation_closure_tests.jl for why
# Supposition `@check` is not used inside `@testitem` on the pinned versions).
@testitem "Invariance" tags=[:invariance] begin
    using LPJmLFITEmulator
    using Test
    using StableRNGs

    rng = StableRNG(717)

    # ── shift invariance of softmax + linearity of latent_heat ─────────────────
    for _ in 1:2000
        n = rand(rng, 1:24)
        v = 100 .* randn(rng, n)          # logits in a wide range
        c = 100 * randn(rng)              # arbitrary shift
        @test isapprox(softmax_partition(v), softmax_partition(v .+ c); atol=1e-9, rtol=1e-7)

        a = 100 * randn(rng)
        et = 50 * randn(rng)
        @test isapprox(latent_heat(a * et), a * latent_heat(et); rtol=1e-9, atol=1e-6)
    end

    # ── deterministic anchors ──────────────────────────────────────────────────
    v = [0.5, -1.0, 2.3, 0.0]
    @test softmax_partition(v) ≈ softmax_partition(v .+ 10.0)
    @test softmax_partition(v) ≈ softmax_partition(v .- 7.25)
    @test latent_heat(2.5) ≈ 2.5 * latent_heat(1.0)
    @test latent_heat(3.0; sublimation=true) ≈ 3.0 * latent_heat(1.0; sublimation=true)
    # Sublimation λ exceeds vaporization λ for the same ET (must not be conflated).
    @test latent_heat(1.0; sublimation=true) > latent_heat(1.0; sublimation=false)
end
