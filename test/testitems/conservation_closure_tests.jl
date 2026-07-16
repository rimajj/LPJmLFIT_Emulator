# Gate 1 — Conservation closure (ENGINEERING_STANDARDS §2, item 1).
# Water & carbon (incl. fire `firec` + establishment `flux_estabc`) close to tolerance on a SINGLE
# step AND over a short synthetic ROLLOUT (folding `flux_then_integrate`). Property-style coverage via
# a seeded StableRNGs loop over valid random states + deterministic anchors + nbp_atm sign/identity.
#
# NB: uses a StableRNGs loop rather than Supposition `@check`, because Supposition's `SuppositionReport`
# testset is not transferable across ReTestItems workers on the pinned versions (Supposition v0.3.5:
# "type SuppositionReport has no field results"). Reinstate `@check` once that compat is resolved.
@testitem "Conservation closure" tags = [:conservation] begin
    using LPJmLFITEmulator
    using Test
    using StableRNGs

    tol = 1.0e-9
    rng = StableRNG(20260716)

    # ── property loop over valid random states ─────────────────────────────────
    for _ in 1:2000
        v = 1000 .* rand(rng, 7)                 # non-negative fluxes in [0, 1000]
        npp, rh, firec, estab, et, runoff, drainage = v
        dstorage = 2000 * rand(rng) - 1000        # storage delta in [-1000, 1000]

        # carbon: consistent budget dC = NPP − Rh − firec + estab ⟹ residual ≡ 0
        dC = npp - rh - firec + estab
        @test abs(carbon_budget_residual(; npp, rh, firec, flux_estabc = estab, dC)) <= tol
        # water: prec = ET + runoff + drainage + ΔStorage ⟹ residual ≡ 0
        prec = et + runoff + drainage + dstorage
        @test abs(water_budget_residual(; prec, et, runoff, drainage, dstorage)) <= tol
    end

    # ── deterministic anchors ──────────────────────────────────────────────────
    @test carbon_budget_residual(; npp = 10.0, rh = 3.0, firec = 1.0, flux_estabc = 0.5, dC = 6.5) ≈ 0.0 atol = tol
    @test water_budget_residual(; prec = 10.0, et = 4.0, runoff = 3.0, drainage = 2.0, dstorage = 1.0) ≈ 0.0 atol = tol

    # ── nbp_atm sign + identity ────────────────────────────────────────────────
    # Land is an atmospheric SOURCE (nbp_atm > 0) when Rh+firec exceed NPP+establishment.
    @test nbp_atm(; rh = 5.0, firec = 2.0, npp = 1.0, flux_estabc = 0.5) > 0
    @test nbp_atm(; rh = 1.0, firec = 0.0, npp = 8.0, flux_estabc = 0.5) < 0
    # Identity: NBP_atm ≡ the carbon residual evaluated at ΔC = 0.
    @test nbp_atm(; rh = 5.0, firec = 2.0, npp = 1.0, flux_estabc = 0.5) ≈
        carbon_budget_residual(; npp = 1.0, rh = 5.0, firec = 2.0, flux_estabc = 0.5, dC = 0.0)

    # ── short synthetic rollout (fold flux_then_integrate) ─────────────────────
    # Each year, partition a conserved annual input across 4 pools via softmax and add it. Because
    # input ≥ 0 and softmax fractions ≥ 0, the non-negativity clamp never fires, so Σpools grows by
    # exactly Σinputs — mass is moved, never created/destroyed.
    for _ in 1:500
        pools = zeros(Float64, 4)
        logits = [0.3, -0.1, 0.7, -0.5]
        inputs = 1000 .* rand(rng, 5)
        total_in = 0.0
        for inp in inputs
            pools = flux_then_integrate(pools, inp .* softmax_partition(logits))
            total_in += inp
        end
        @test sum(pools) ≈ total_in atol = 1.0e-6 * max(1.0, total_in)
        @test all(pools .>= 0)
    end
end
