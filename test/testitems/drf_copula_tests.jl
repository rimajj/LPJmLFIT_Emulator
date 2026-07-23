# Gaussian-copula recruit-trait sampler (P1 Tier-1 Step 4c; ADR 0022). The pure-Base copula machinery in
# src/drf.jl — hand-rolled Cholesky, normal CDF/inverse-CDF, and correlated-uniform → per-axis marginal
# draws (via `predict_quantile`) — that Component S will use to draw NEW recruit traits {logHeight, Age,
# SLA, Wooddens, beta_root} with the correct cross-axis correlation. These testitems gate the sampler in
# isolation (its consumer, the recruit-cohort APPEND path, lands with membership append/merge — design
# risk #5): analytic accuracy of Φ/Φ⁻¹, exact Cholesky round-trip, recovery of the target correlation
# from many draws, marginal conditioning through the DRF, and determinism under the seeded RNG.

@testitem "Copula primitives — chol_lower / norminv / normcdf accuracy + guards" tags = [:unit] begin
    using LPJmLFITEmulator.DRF
    using Test

    # normcdf vs known values
    @test DRF.normcdf(0.0) ≈ 0.5 atol = 1.0e-7
    @test DRF.normcdf(1.0) ≈ 0.8413447 atol = 1.0e-6
    @test DRF.normcdf(-1.0) ≈ 0.1586553 atol = 1.0e-6
    @test DRF.normcdf(1.959964) ≈ 0.975 atol = 1.0e-6
    @test DRF.normcdf(-2.5) ≈ 0.0062097 atol = 1.0e-6

    # norminv vs known quantiles (Acklam ~1e-9 relative)
    @test DRF.norminv(0.5) ≈ 0.0 atol = 1.0e-9
    @test DRF.norminv(0.975) ≈ 1.959964 atol = 1.0e-6
    @test DRF.norminv(0.025) ≈ -1.959964 atol = 1.0e-6
    @test DRF.norminv(0.8413447) ≈ 1.0 atol = 1.0e-5
    # Φ and Φ⁻¹ are inverse to normcdf's accuracy
    for x in (-2.3, -0.7, 0.4, 1.6)
        @test DRF.norminv(DRF.normcdf(x)) ≈ x atol = 1.0e-4
    end

    # chol_lower: exact reconstruction L·Lᵀ ≈ R and guard on non-PD
    R = [1.0 0.6 0.3; 0.6 1.0 0.2; 0.3 0.2 1.0]
    L = DRF.chol_lower(R)
    @test L * transpose(L) ≈ R atol = 1.0e-12
    @test all(L[i, j] == 0.0 for i in 1:3 for j in (i + 1):3)     # lower-triangular
    @test_throws ErrorException DRF.chol_lower([1.0 2.0; 2.0 1.0]) # indefinite ⇒ not PD
    @test_throws DimensionMismatch DRF.chol_lower([1.0 0.0 0.0; 0.0 1.0 0.0])
end

@testitem "Gaussian copula — recovers the target correlation + is deterministic" tags = [:unit] begin
    using LPJmLFITEmulator.DRF
    using Test

    # hand-rolled Pearson correlation (no Statistics dep)
    function corr(A)                       # A is M×d
        M, d = size(A)
        μ = [sum(@view A[:, j]) / M for j in 1:d]
        C = zeros(d, d)
        for a in 1:d, b in 1:d
            s = 0.0
            for i in 1:M
                s += (A[i, a] - μ[a]) * (A[i, b] - μ[b])
            end
            C[a, b] = s / (M - 1)
        end
        R = similar(C)
        for a in 1:d, b in 1:d
            R[a, b] = C[a, b] / sqrt(C[a, a] * C[b, b])
        end
        return R
    end

    R = [1.0 0.6 0.3; 0.6 1.0 0.2; 0.3 0.2 1.0]
    cop = GaussianCopula(R)
    @test cop.d == 3

    # draw many correlated uniforms; transform back to normal scores; empirical corr ≈ R
    M = 40_000
    Z = Matrix{Float64}(undef, M, 3)
    rng = DRF.Xoshiro256pp(20260723)
    for i in 1:M
        u = DRF.copula_uniforms!(rng, cop)
        @test all(0.0 .< u .< 1.0)
        for j in 1:3
            Z[i, j] = DRF.norminv(u[j])
        end
    end
    Rhat = corr(Z)
    for a in 1:3, b in 1:3
        @test Rhat[a, b] ≈ R[a, b] atol = 0.03
    end

    # determinism: same seed ⇒ identical uniform stream
    r1 = DRF.Xoshiro256pp(7); r2 = DRF.Xoshiro256pp(7)
    @test DRF.copula_uniforms!(r1, cop) == DRF.copula_uniforms!(r2, cop)
    # independent copula (identity R) ⇒ ~uncorrelated
    id = GaussianCopula([1.0 0.0; 0.0 1.0])
    Zi = Matrix{Float64}(undef, M, 2)
    ri = DRF.Xoshiro256pp(99)
    for i in 1:M
        u = DRF.copula_uniforms!(ri, id)
        Zi[i, 1] = DRF.norminv(u[1]); Zi[i, 2] = DRF.norminv(u[2])
    end
    @test abs(corr(Zi)[1, 2]) < 0.03
end

@testitem "sample_copula! — flux-conditioned marginals through predict_quantile + induced correlation" tags = [:unit] begin
    using LPJmLFITEmulator.DRF
    using Test

    # three per-axis DRFs with store_values=true; each axis marginal centered on a feature-driven mean so
    # predict_quantile returns a conditioned empirical value.
    function axis_forest(seed, scale)
        r = DRF.Xoshiro256pp(seed)
        n, p = 1500, 3
        X = Matrix{Float64}(undef, n, p); y = Vector{Float64}(undef, n)
        for i in 1:n
            for f in 1:p
                X[i, f] = DRF.rand01!(r)
            end
            y[i] = scale * X[i, 1] + 0.2 * (DRF.rand01!(r) - 0.5)   # marginal keys on feature 1
        end
        return DRF.fit_forest(X, y; ntrees = 40, subsample = 800, max_depth = 12, min_leaf = 8, mtry = p, seed = seed, store_values = true)
    end
    axes = (axis_forest(1, 1.0), axis_forest(2, 5.0), axis_forest(3, 20.0))
    x = [0.7, 0.3, 0.5]                     # fixed flux/boundary feature row

    # determinism
    r1 = DRF.Xoshiro256pp(3); r2 = DRF.Xoshiro256pp(3)
    cop = GaussianCopula([1.0 0.7 0.4; 0.7 1.0 0.5; 0.4 0.5 1.0])
    @test DRF.sample_copula!(r1, cop, axes, x) == DRF.sample_copula!(r2, cop, axes, x)

    # each drawn axis lands inside its conditioned marginal support (predict_quantile range at x)
    lo = [DRF.predict_quantile(axes[j], x, 0.0) for j in 1:3]
    hi = [DRF.predict_quantile(axes[j], x, 1.0) for j in 1:3]
    rng = DRF.Xoshiro256pp(42)
    M = 6000
    D = Matrix{Float64}(undef, M, 3)
    for i in 1:M
        t = DRF.sample_copula!(rng, cop, axes, x)
        for j in 1:3
            @test lo[j] - 1.0e-9 ≤ t[j] ≤ hi[j] + 1.0e-9
        end
        D[i, :] = t
    end
    # positive copula correlation ⇒ positive rank-ish correlation in the drawn traits
    function pear(a, b)
        M = length(a); μa = sum(a) / M; μb = sum(b) / M
        c = sum((a[i] - μa) * (b[i] - μb) for i in 1:M)
        va = sum((a[i] - μa)^2 for i in 1:M); vb = sum((b[i] - μb)^2 for i in 1:M)
        return c / sqrt(va * vb)
    end
    @test pear(D[:, 1], D[:, 2]) > 0.3
    @test pear(D[:, 1], D[:, 3]) > 0.15

    # dimension guard
    @test_throws DimensionMismatch DRF.sample_copula!(DRF.Xoshiro256pp(1), cop, (axes[1], axes[2]), x)
end
