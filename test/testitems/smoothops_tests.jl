# Smooth-surrogate deviation bounds (ADR 0014 step 5 / ENGINEERING_STANDARDS §2 item 7). Each C∞
# surrogate replaces a non-differentiable op in F_diff; its deviation from the EXACT op must be
# bounded and the bound tested, so the "same physics" claim is quantified, not asserted. The bounds:
#   softplus/smoothmax0 vs max(x,0):  0 ≤ err ≤ log(2)/β
#   smoothmin vs min, smoothmax vs max: 0 ≤ |err| ≤ log(2)/β
#   smooth_clamp vs clamp:            |err| ≤ 2·log(2)/β
#   sqrt_floor vs sqrt(max(x,0)):     |err| ≤ √ε   (for x ≥ 0)
@testitem "SmoothOps — deviation bounds from exact ops" tags = [:smoothops, :unit] begin
    using LPJmLFITEmulator.SmoothOps
    using Test

    ln2 = log(2.0)
    xs = collect(-5.0:0.25:5.0)

    # softplus / smoothmax0 vs max(x, 0)
    for β in (1.0, 5.0, 20.0, 50.0)
        for x in xs
            err = softplus(x, β) - max(x, 0.0)
            @test 0 ≤ err ≤ ln2 / β + 1.0e-9
            @test isfinite(softplus(x, β))
        end
        @test maximum(softplus(x, β) - max(x, 0.0) for x in xs) ≤ ln2 / β + 1.0e-9
    end

    # smoothmin vs min, smoothmax vs max
    for β in (1.0, 5.0, 30.0)
        for a in xs, b in (-2.0, 0.0, 1.5, 4.0)
            @test 0 ≤ min(a, b) - smoothmin(a, b, β) ≤ ln2 / β + 1.0e-9
            @test 0 ≤ smoothmax(a, b, β) - max(a, b) ≤ ln2 / β + 1.0e-9
        end
    end

    # smoothmin handles +Inf (a dropped argument) — used for the conductance cap when not water-limited
    @test smoothmin(Inf, 3.0, 1.0) ≈ 3.0 atol = 1.0e-9
    @test isfinite(smoothmin(Inf, 3.0, 1.0))

    # smooth_clamp vs hard clamp: |err| ≤ 2 log(2)/β
    for β in (5.0, 20.0)
        for x in -3.0:0.1:4.0
            @test abs(smooth_clamp(x, 0.0, 1.0, β) - clamp(x, 0.0, 1.0)) ≤ 2 * ln2 / β + 1.0e-9
        end
    end

    # sqrt_floor vs sqrt(max(x,0)) for x ≥ 0: |err| ≤ √ε
    ε = 1.0e-9
    for x in 0.0:0.3:9.0
        @test abs(sqrt_floor(x, ε) - sqrt(x)) ≤ sqrt(ε) + 1.0e-12
    end
    @test isfinite(sqrt_floor(0.0, ε))          # differentiable at 0 (no 1/√0)

    # sigmoid basics
    @test sigmoid(0.0) == 0.5
    @test sigmoid(-1000.0) ≈ 0.0 atol = 1.0e-12
    @test sigmoid(1000.0) ≈ 1.0 atol = 1.0e-12
end

# The crown-area cap surrogate (Allometry.crown_area_smooth) must track the exact cap within log(2)/β.
@testitem "SmoothOps — allometry crown-area cap surrogate" tags = [:smoothops, :allometry] begin
    using LPJmLFITEmulator.Allometry
    using Test

    p = TreeAllometry{Float64}()
    β = 0.5
    for H in (1.0, 5.0, 20.0, 60.0, 90.0, 120.0)   # spans below and above the 225 m² cap
        exact = crown_area(p, H)
        smooth = crown_area_smooth(p, H; β = β)
        @test 0 ≤ exact - smooth ≤ log(2.0) / β + 1.0e-9
    end
end
