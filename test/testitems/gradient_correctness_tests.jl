# Gate 2 — Gradient correctness (ENGINEERING_STANDARDS §2 item 2; ADR 0014 step 6).
# AD (Enzyme reverse-mode + ForwardDiff) vs FiniteDifferences.jl ground truth, of annual NPP w.r.t.
# an input/parameter through the full daily F_diff rollout, at interior operating points; asserts
# agreement to tolerance and NO NaN/Inf gradients. This is the spike's headline result: the WHOLE
# differentiable fast core is end-to-end differentiable, including the λ (ci:ca) Newton solve and the
# autoregressive soil-water coupling — which the reference repos do NOT demonstrate (they detach
# physics / adjoint only the λ residual).
@testitem "Gradient correctness — softmax invariant (cheap)" tags = [:gradient] begin
    using LPJmLFITEmulator
    using Test

    # softmax fractions sum to 1 ⟹ every Jacobian COLUMN sums to ~0 (central finite differences,
    # no external AD/FD package). Retained from the Phase-0 scaffold.
    logits = [0.4, -1.1, 2.0, 0.0, -0.3]
    h = 1.0e-6
    for j in eachindex(logits)
        lp = copy(logits); lp[j] += h
        lm = copy(logits); lm[j] -= h
        dcol = (softmax_partition(lp) .- softmax_partition(lm)) ./ (2h)
        @test isapprox(sum(dcol), 0.0; atol = 1.0e-7)
        @test all(isfinite, dcol)
    end
end

@testitem "Gradient correctness — F_diff rollout: AD vs FiniteDifferences" tags = [:gradient, :fdiff] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using ForwardDiff, FiniteDifferences, Enzyme
    using Test

    fdm = central_fdm(5, 1)

    # ── WET scenario (150 days): gradients w.r.t. a forcing (CO₂) and two parameters (emax, α_c3) ─
    str = Structure{Float64}(lai = 4.0, fpc = 0.8, albedo = 0.15, phen = 1.0, whc = 200.0, k_beer = 0.5)
    wetforc(::Type{S}; co2 = 380.0) where {S} =
        [
        DailyForcing{S}(
                swdown = 150 + 120 * sin(2π * (d - 80) / 365), lwnet = -40.0,
                temp = 15 + 12 * sin(2π * (d - 110) / 365), precip = d % 3 == 0 ? 6.0 : 0.5,
                daylength = 12 + 4 * sin(2π * (d - 80) / 365), co2 = co2
            ) for d in 1:150
    ]
    mkstr(::Type{S}) where {S} = Structure{S}(lai = 4.0, fpc = 0.8, albedo = 0.15, phen = 1.0, whc = 200.0, k_beer = 0.5)

    f_co2(x) = annual_npp(FDiffParams{Float64}(), FDiffState{Float64}(w = 0.6), str, wetforc(typeof(x); co2 = x))
    f_emax(x) = annual_npp(
        FDiffParams{typeof(x)}(; water = FDiff.WaterParams{typeof(x)}(; emax = x)),
        FDiffState{typeof(x)}(w = 0.6), mkstr(typeof(x)), wetforc(typeof(x))
    )
    f_alpha(x) = annual_npp(
        FDiffParams{typeof(x)}(; photo = FDiff.PhotoParams{typeof(x)}(; alphac3 = x)),
        FDiffState{typeof(x)}(w = 0.6), mkstr(typeof(x)), wetforc(typeof(x))
    )

    # ── DRY scenario (40 days, low precip): gradient w.r.t. the INITIAL soil water — exercises the
    #    autoregressive state coupling (initial condition propagates because water is not saturated). ─
    dryforc(::Type{S}) where {S} =
        [
        DailyForcing{S}(
                swdown = 240.0, lwnet = -50.0, temp = 22.0, precip = 0.4,
                daylength = 13.0, co2 = 380.0
            ) for d in 1:40
    ]
    f_w0(x) = annual_npp(FDiffParams{typeof(x)}(), FDiffState{typeof(x)}(w = x), mkstr(typeof(x)), dryforc(typeof(x)))

    cases = [("co2", f_co2, 380.0), ("emax", f_emax, 5.0), ("alphac3", f_alpha, 0.08), ("w0_dry", f_w0, 0.6)]

    # ── ForwardDiff vs FiniteDifferences ────────────────────────────────────────────────────────
    for (name, f, x0) in cases
        gfd = fdm(f, x0)
        gad = ForwardDiff.derivative(f, x0)
        @test isfinite(gad)
        @test isfinite(gfd)
        @test isapprox(gad, gfd; rtol = 1.0e-5, atol = 1.0e-8)
    end
    # the dry-w0 gradient must be genuinely non-zero (state coupling is really differentiated)
    @test abs(ForwardDiff.derivative(f_w0, 0.6)) > 1.0e-3

    # ── Enzyme reverse-mode vs FiniteDifferences (a forcing + a state, through the coupling) ─────
    # `set_runtime_activity`: the λ-solve now confines its Newton iterate to the physical bracket
    # [0.02, 0.85] with a `clamp` (robustness on real forcing — deep-winter low-light degeneracy would
    # otherwise diverge; see solve_lambda + cbinary_validation_tests.jl). That `clamp` is a conditional,
    # so Enzyme's *static* activity analysis is (conservatively) insufficient; runtime activity is the
    # documented mode for genuinely conditional activity. Still true reverse-mode through the full
    # physics rollout, and still exact vs finite differences.
    RA = Enzyme.set_runtime_activity(Enzyme.Reverse)
    for (name, f, x0) in (("co2", f_co2, 380.0), ("w0_dry", f_w0, 0.6))
        gfd = fdm(f, x0)
        gz = Enzyme.autodiff(RA, f, Enzyme.Active, Enzyme.Active(x0))[1][1]
        @test isfinite(gz)
        @test isapprox(gz, gfd; rtol = 1.0e-5, atol = 1.0e-8)
    end
end
