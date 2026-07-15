# Gate 2 — Gradient correctness (ENGINEERING_STANDARDS §2, item 2).
# The full battery — AD (Enzyme/Zygote) vs FiniteDifferences.jl ground truth at multiple points
# incl. boundaries, asserting no NaN/Inf gradients — lands with the differentiable core
# (Phase 6, DEVELOPMENT_PLAN §6). Scaffolded here; one cheap, dep-free finite-difference invariant
# is checked now.
@testitem "Gradient correctness" tags=[:gradient] begin
    using LPJmLFITEmulator
    using Test

    # ── REAL cheap check ────────────────────────────────────────────────────────
    # softmax fractions sum to 1 ⟹ every Jacobian COLUMN sums to ~0:
    #   ∂/∂logitⱼ Σᵢ softmaxᵢ(logits) = ∂/∂logitⱼ (1) = 0   for every j.
    # Central finite differences, no external AD/FD package required.
    logits = [0.4, -1.1, 2.0, 0.0, -0.3]
    h = 1e-6
    for j in eachindex(logits)
        lp = copy(logits); lp[j] += h
        lm = copy(logits); lm[j] -= h
        dcol = (softmax_partition(lp) .- softmax_partition(lm)) ./ (2h)   # ∂f/∂logitⱼ
        @test isapprox(sum(dcol), 0.0; atol = 1e-7)   # column sums to ~0 (partition constraint)
        @test all(isfinite, dcol)                      # no NaN/Inf gradients
    end

    # ── Phase-6 scaffold: AD vs FiniteDifferences on the differentiable core ─────
    # DifferentiationInterfaceTest.jl / ChainRulesTestUtils.jl with FiniteDifferences.jl ground
    # truth: compare AD gradients of the F2 core at interior AND boundary points; assert agreement
    # to tolerance and no NaN/Inf. Arrives with the differentiable core (Phase 6).
    @test_skip false  # AD-vs-FD gradient battery — differentiable core not implemented yet.
end
