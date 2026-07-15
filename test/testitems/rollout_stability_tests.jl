# Gate 4 — Rollout / autoregressive stability (ENGINEERING_STANDARDS §2, item 4).
# A synthetic bounded-storage rollout via `flux_then_integrate` stays non-negative and bounded over
# many steps (no blow-up). The real "no spurious oscillation / AC-gap vs LPJmL reference" test — the
# stiff carbon+population failure mode from LPJ_resilience — lands in Phase 6 (DEVELOPMENT_PLAN §5).
@testitem "Rollout stability" tags=[:rollout, :stability] begin
    using LPJmLFITEmulator
    using Test

    # ── REAL synthetic rollout: leaky-bucket dynamics  newₜ = max(0.9·stateₜ + input, 0) ─────────
    # Contractive (factor 0.9) with bounded forcing ⟹ converges to input/0.1, never blows up.
    nstep = 5000
    input = fill(2.0, 6)
    state = fill(50.0, 6)
    bound = maximum(input) / 0.1 * 1.5 + maximum(state)   # generous a-priori envelope

    ok_nonneg = true
    ok_finite = true
    ok_bounded = true
    for _ in 1:nstep
        increments = -0.1 .* state .+ input               # decay toward the steady state
        state      = flux_then_integrate(state, increments)
        ok_nonneg  &= all(≥(0.0), state)                  # clamp guarantees non-negativity
        ok_finite  &= all(isfinite, state)
        ok_bounded &= all(≤(bound), state)                # bounded — no blow-up
    end
    @test ok_nonneg
    @test ok_finite
    @test ok_bounded
    # Converged near the analytic steady state input/0.1 = 20.
    @test all(s -> isapprox(s, 20.0; atol = 1e-6), state)

    # ── Phase-6 scaffold: no AC-gap / oscillation vs an LPJmL reference trajectory ───────────────
    # Long-horizon rollout vs a saved LPJmL reference: bounded drift, no spurious limit cycle /
    # "AC gap" in the stiff carbon+population system (DEVELOPMENT_PLAN §5 / LPJ_resilience).
    @test_skip false  # AC-gap / oscillation battery vs reference — arrives with the components.
end
