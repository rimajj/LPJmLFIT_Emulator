# Gate 10 — Limiting-case sanity (ENGINEERING_STANDARDS §2, item 10).
# Zero forcing ⇒ zero/steady response; closed-form toy cases; unimplemented Phase-N component
# stubs throw (their documented Phase-0 contract).
@testitem "Limiting cases" tags = [:limits] begin
    using LPJmLFITEmulator
    using Test

    # Zero increments ⇒ flux_then_integrate returns the (clamped) input state unchanged.
    s = [0.0, 3.0, 7.5, 100.0]
    @test flux_then_integrate(s, zeros(length(s))) == s
    # Negative state clamps to zero even with a zero increment.
    @test flux_then_integrate([-2.0, 4.0], [0.0, 0.0]) == [0.0, 4.0]

    # All-zero fluxes with ΔC = 0 ⟹ residual is exactly 0.
    @test carbon_budget_residual(; npp = 0.0, rh = 0.0, firec = 0.0, flux_estabc = 0.0, dC = 0.0) == 0.0
    # All-zero water fluxes ⟹ residual is exactly 0.
    @test water_budget_residual(; prec = 0.0, et = 0.0, runoff = 0.0, drainage = 0.0, dstorage = 0.0) == 0.0

    # Zero ET ⇒ zero latent heat (both phases).
    @test latent_heat(0.0) == 0.0
    @test latent_heat(0.0; sublimation = true) == 0.0

    # Equal logits ⇒ uniform partition.
    @test softmax_partition(zeros(5)) ≈ fill(1 / 5, 5)

    # ── Component stubs are unimplemented in Phase 0 and MUST throw (documented contract) ─────────
    struct _StubSlow <: AbstractSlowEmulator end
    struct _StubFast <: AbstractFastCore end
    struct _StubEnergy <: AbstractEnergyClosure end

    st = SharedState{Float64}()
    fts = FToS{Float64}(; bm_inc = 0.0, water_stress = 0.0, temp_stress = 0.0, growth_eff = 0.0, soilmoist = 0.0)
    stf = SToF{Float64}(; lai = 1.0, height = 1.0, z0 = 0.1, rootdepth = 500.0, vcmax = 30.0, fpc = 0.5, albedo = 0.15)
    ste = SToE{Float64}(; albedo = 0.15, z0 = 0.1, lai = 1.0, height = 1.0)
    ftoe = FToE{Float64}(; le = 0.0, gpp = 0.0, npp = 0.0, rh = 0.0, firec = 0.0, flux_estabc = 0.0, ground_heat = 0.0)
    forcing = AtmForcing{Float64}(; swdown = 200.0, lwdown = 300.0, tair = 288.0, qair = 0.01, wind = 2.0, psurf = 1.0e5, precip = 0.0, co2 = 400.0)

    @test_throws ErrorException LPJmLFITEmulator.step!(_StubSlow(), st, fts)
    @test_throws ErrorException LPJmLFITEmulator.step!(_StubFast(), st, stf, forcing)
    @test_throws ErrorException LPJmLFITEmulator.solve!(_StubEnergy(), st, ftoe, ste, forcing)
end
