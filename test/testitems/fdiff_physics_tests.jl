# F_diff physics gates (ENGINEERING_STANDARDS §2 items 1/8/5/10): water closure by construction,
# physical boundedness, limiting cases, and determinism — the "same physics" behavioural checks that
# sit alongside the numerical-regression and gradient gates (ADR 0014).

@testitem "F_diff — water closure by construction (property loop)" tags = [:fdiff, :conservation] begin
    using LPJmLFITEmulator.FDiff
    using StableRNGs
    using Test

    rng = StableRNG(20260716)
    p = FDiffParams{Float64}()
    for _ in 1:200
        str = Structure{Float64}(
            lai = 1 + 5 * rand(rng), fpc = 0.2 + 0.7 * rand(rng),
            albedo = 0.1 + 0.2 * rand(rng), phen = rand(rng), whc = 100 + 200 * rand(rng), k_beer = 0.4 + 0.2 * rand(rng)
        )
        st = FDiffState{Float64}(w = rand(rng), snowpack = 50 * rand(rng))
        # 60-day rollout over random-but-valid forcing; check per-day closure
        maxres = 0.0
        for _ in 1:60
            f = DailyForcing{Float64}(
                swdown = 50 + 300 * rand(rng), lwnet = -80 + 60 * rand(rng),
                temp = -10 + 40 * rand(rng), precip = 10 * rand(rng), daylength = 6 + 12 * rand(rng), co2 = 380.0
            )
            (st1, fl) = daily_step(p, st, str, f)
            dstore = (st1.w - st.w) * str.whc + (st1.snowpack - st.snowpack)
            res = f.precip - (fl.transp + fl.evap + fl.runoff + dstore)
            maxres = max(maxres, abs(res))
            st = st1
        end
        @test maxres < 1.0e-8               # precip = ET + runoff + Δstorage, exact to round-off
    end
end

@testitem "F_diff — physical boundedness" tags = [:fdiff, :bounds] begin
    using LPJmLFITEmulator.FDiff
    using StableRNGs
    using Test

    rng = StableRNG(1234)
    p = FDiffParams{Float64}()
    str = Structure{Float64}(lai = 4.0, fpc = 0.8, albedo = 0.15, phen = 1.0, whc = 200.0, k_beer = 0.5)
    st = FDiffState{Float64}(w = 0.5, snowpack = 0.0)
    for _ in 1:365
        f = DailyForcing{Float64}(
            swdown = 50 + 300 * rand(rng), lwnet = -80 + 60 * rand(rng),
            temp = -20 + 45 * rand(rng), precip = 12 * rand(rng), daylength = 6 + 12 * rand(rng), co2 = 380.0
        )
        (st1, fl) = daily_step(p, st, str, f)
        @test all(isfinite, (fl.gpp, fl.npp, fl.transp, fl.evap, fl.eeq, fl.runoff, fl.lambda, fl.wscal))
        @test fl.gpp ≥ -1.0e-6              # GPP ≥ 0 (softplus floor)
        @test fl.eeq ≥ -1.0e-6              # equilibrium ET ≥ 0
        @test fl.transp ≥ -1.0e-6 && fl.evap ≥ -1.0e-6 && fl.runoff ≥ -1.0e-6
        @test -0.02 ≤ st1.w ≤ 1.02          # soil water fraction bounded (smooth-clamp overshoot tiny)
        @test st1.snowpack ≥ -1.0e-6        # snow water equivalent ≥ 0
        @test 0.0 ≤ fl.lambda ≤ 1.0         # ci:ca ratio in [0,1]
        @test -1.0e-6 ≤ fl.wscal ≤ 1.0 + 1.0e-6
        st = st1
    end
end

@testitem "F_diff — limiting cases" tags = [:fdiff, :limits] begin
    using LPJmLFITEmulator.FDiff
    using Test

    p = FDiffParams{Float64}()
    str = Structure{Float64}(lai = 4.0, fpc = 0.8, albedo = 0.15, phen = 1.0, whc = 200.0, k_beer = 0.5)

    # no light ⇒ no equilibrium ET and no GPP. Values are bounded by the documented smooth-surrogate
    # floors, NOT exactly zero: eeq by the clamp floor log(2)/βeeq ≈ 0.14, gpp by the softplus floor
    # log(2)/βflux ≈ 0.014 (both physically negligible; see fdiff_smoothops.jl deviation bounds).
    dark = DailyForcing{Float64}(swdown = 0.0, lwnet = 0.0, temp = 15.0, precip = 2.0, daylength = 12.0, co2 = 380.0)
    (_, fl) = daily_step(p, FDiffState{Float64}(w = 0.6), str, dark)
    @test fl.eeq < 0.2                              # ≈ clamp floor log(2)/βeeq
    @test fl.gpp < 0.02                             # ≈ softplus floor log(2)/βflux

    # sub-freezing precip accumulates as snow (rain fraction ≈ 0), soil water barely changes
    cold = DailyForcing{Float64}(swdown = 50.0, lwnet = -30.0, temp = -15.0, precip = 8.0, daylength = 8.0, co2 = 380.0)
    st0 = FDiffState{Float64}(w = 0.6, snowpack = 0.0)
    (st1, flc) = daily_step(p, st0, str, cold)
    @test st1.snowpack > 7.0                        # ~all precip becomes snow
    @test flc.gpp ≈ 0.0 atol = 1.0e-1               # frozen ⇒ ~no photosynthesis

    # no leaf area ⇒ ~no GPP (APAR → 0)
    bare = Structure{Float64}(lai = 0.0, fpc = 0.0, albedo = 0.15, phen = 1.0, whc = 200.0, k_beer = 0.5)
    warm = DailyForcing{Float64}(swdown = 250.0, lwnet = -40.0, temp = 20.0, precip = 2.0, daylength = 13.0, co2 = 380.0)
    (_, flb) = daily_step(p, FDiffState{Float64}(w = 0.6), bare, warm)
    @test flb.gpp < 0.02                            # ≈ softplus floor (no leaf area ⇒ APAR → 0)
end

@testitem "F_diff — determinism & Float32" tags = [:fdiff, :determinism, :types] begin
    using LPJmLFITEmulator.FDiff
    using Test

    str = Structure{Float64}(lai = 4.0, fpc = 0.8, albedo = 0.15, phen = 1.0, whc = 200.0, k_beer = 0.5)
    forc = [
        DailyForcing{Float64}(
                swdown = 200.0, lwnet = -40.0, temp = 15.0 + 0.01d, precip = 2.0,
                daylength = 12.0, co2 = 380.0
            ) for d in 1:120
    ]
    a = rollout(FDiffParams{Float64}(), FDiffState{Float64}(w = 0.6), str, forc)[2]
    b = rollout(FDiffParams{Float64}(), FDiffState{Float64}(w = 0.6), str, forc)[2]
    @test a.npp == b.npp && a.gpp == b.gpp          # bit-for-bit reproducible

    # Float32 rollout runs and is close to Float64 (the model is type-generic)
    str32 = Structure{Float32}(lai = 4.0f0, fpc = 0.8f0, albedo = 0.15f0, phen = 1.0f0, whc = 200.0f0, k_beer = 0.5f0)
    forc32 = [
        DailyForcing{Float32}(
                swdown = 200.0f0, lwnet = -40.0f0, temp = 15.0f0 + 0.01f0 * d,
                precip = 2.0f0, daylength = 12.0f0, co2 = 380.0f0
            ) for d in 1:120
    ]
    c = rollout(FDiffParams{Float32}(), FDiffState{Float32}(w = 0.6f0), str32, forc32)[2]
    @test c.npp isa Float32
    @test isapprox(Float64(c.npp), a.npp; rtol = 1.0e-2)
end
