# Gate 3 — Numerical regression (ENGINEERING_STANDARDS §2, item 3).
# ReferenceTests.@test_reference baselines against saved artifacts catch silent numerical drift
# after refactors. The real baselines (fixed-input outputs, reference trajectories) arrive WITH
# the components (Phase 3+, DEVELOPMENT_PLAN §6). Scaffolded here with one closed-form anchor now.
@testitem "Numerical regression" tags=[:regression] begin
    using LPJmLFITEmulator
    using Test
    using ReferenceTests   # provides @test_reference; used by the Phase-3+ baselines below

    # ── REAL closed-form reference values for fixed inputs (no baseline file needed yet) ─────────
    @test softmax_partition([0.0, 0.0, 0.0]) ≈ fill(1 / 3, 3)
    # softmax(log.(w)) == w ./ sum(w): logits = log([1,2,3]) ⟹ fractions = [1,2,3]/6 exactly.
    @test softmax_partition(log.([1.0, 2.0, 3.0])) ≈ [1.0, 2.0, 3.0] ./ 6

    # ── Phase-3+ scaffold: saved-baseline regression via ReferenceTests ──────────────────────────
    # When the components produce trajectories/fields, pin them against committed baselines, e.g.:
    #   @test_reference "references/softmax_fixed.jls" softmax_partition(fixed_logits)
    #   @test_reference "references/rollout_trajectory.txt" run_reference_rollout()
    @test_skip false  # @test_reference numerical baselines — arrive with the components.
end
