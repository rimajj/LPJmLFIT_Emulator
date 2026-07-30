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

# ── ADR 0037: the QRF (Meinshausen 2006) leaf weighting, opt-in ────────────────────────────────────
# `predict_quantile`'s default CONCATENATES every tree's leaf values and takes an unweighted quantile, so a
# value's weight is 1/Σ_t|L_t(x)| and a tree that lands x in a LARGE leaf contributes proportionally more of
# the answer. A distributional forest is defined by the opposite: each tree contributes 1/T, spread evenly
# inside its own leaf. `qrf = true` implements that. These gate (a) the weighting arithmetic against
# hand-computed values, (b) that the default is untouched, and (c) that the difference is a WEIGHTING effect
# and not the accompanying quantile-convention change.

@testitem "DRF predict_quantile — opt-in QRF leaf weighting (ADR 0037)" tags = [:unit] begin
    using LPJmLFITEmulator.DRF
    using Test

    # A hand-built 2-tree forest, each tree a single leaf, with DELIBERATELY unequal leaf sizes.
    leafonly(vals) = DRF.RegTree([0], [0.0], [0], [0], [sum(vals) / length(vals)], [vals])
    f = DRF.Forest([leafonly([1.0, 2.0]), leafonly([10.0, 20.0, 30.0, 40.0])], 1, true, [0.0])
    x = [0.0]

    # Pooled default: 6 values, equal weight 1/6 -> the 4-value leaf owns 4/6 of the mass.
    # QRF (T = 2): leaf A values weigh 1/(2·2) = 0.25 each, leaf B values 1/(2·4) = 0.125 each; total 1.0.
    #   cumulative: 1 -> 0.25, 2 -> 0.50, 10 -> 0.625, 20 -> 0.75, 30 -> 0.875, 40 -> 1.0
    for (u, want) in [
            (0.0, 1.0), (0.2, 1.0), (0.25, 1.0), (0.3, 2.0), (0.5, 2.0),
            (0.6, 10.0), (0.7, 20.0), (0.8, 30.0), (1.0, 40.0),
        ]
        @test DRF.predict_quantile(f, x, u; qrf = true) == want
    end

    # THE HEADLINE CONSEQUENCE: the median. Pooled puts it at 10 because the big leaf owns 67 % of the mass;
    # QRF gives the two trees an equal say and puts it at 2.
    @test DRF.predict_quantile(f, x, 0.5) == 10.0
    @test DRF.predict_quantile(f, x, 0.5; qrf = true) == 2.0

    # Endpoints hold under both estimators.
    @test DRF.predict_quantile(f, x, 0.0; qrf = true) == 1.0
    @test DRF.predict_quantile(f, x, 1.0; qrf = true) == 40.0

    # DEFAULT IS UNCHANGED (guardrail 4): omitting the kwarg must equal explicitly passing false, for every u.
    for u in 0.0:0.05:1.0
        @test DRF.predict_quantile(f, x, u) === DRF.predict_quantile(f, x, u; qrf = false)
    end

    # store_values guard still applies on the QRF path.
    g = DRF.fit_forest(reshape(collect(1.0:20.0), 20, 1), collect(1.0:20.0); ntrees = 2, store_values = false)
    @test_throws ErrorException DRF.predict_quantile(g, [1.0], 0.5; qrf = true)
end

@testitem "DRF QRF weighting — equal leaf sizes make the WEIGHTS agree (isolates weighting from convention)" tags = [:unit] begin
    using LPJmLFITEmulator.DRF
    using Test

    # With EQUAL leaf sizes the two estimators place identical mass on every value, so they can differ only
    # by the quantile CONVENTION (the default indexes `1 + floor(u·(n−1))`; QRF inverts the weighted CDF).
    # That residual is bounded by ONE order statistic — which is what makes the large differences seen on
    # unequal leaves attributable to the weighting rather than to the convention. On the production global
    # copula the same separation measures 0.002–0.014 % (convention) against 1.7–4.4 % (weighting).
    leafonly(vals) = DRF.RegTree([0], [0.0], [0], [0], [sum(vals) / length(vals)], [vals])
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    b = [10.0, 20.0, 30.0, 40.0, 50.0]
    f = DRF.Forest([leafonly(a), leafonly(b)], 1, true, [0.0])
    x = [0.0]
    pool = sort(vcat(a, b))
    n = length(pool)

    for u in 0.0:0.02:1.0
        qv = DRF.predict_quantile(f, x, u; qrf = true)
        pv = DRF.predict_quantile(f, x, u)
        # Both must return an actual pooled order statistic, and their RANKS may differ by at most 1.
        iq = findfirst(==(qv), pool)
        ip = findfirst(==(pv), pool)
        @test iq !== nothing && ip !== nothing
        @test abs(iq - ip) <= 1
    end

    # And with unequal sizes the ranks separate far beyond that one-step bound, i.e. the weighting bites.
    h = DRF.Forest([leafonly([1.0, 2.0]), leafonly(collect(10.0:1.0:60.0))], 1, true, [0.0])
    @test DRF.predict_quantile(h, x, 0.5) > 10.0                  # pooled: swamped by the 51-value leaf
    @test DRF.predict_quantile(h, x, 0.5; qrf = true) <= 2.0       # QRF: the 2-value tree keeps half the mass
end

@testitem "DRF sample_copula! threads the QRF option through every axis (ADR 0037)" tags = [:unit] begin
    using LPJmLFITEmulator.DRF
    using Test

    leafonly(vals) = DRF.RegTree([0], [0.0], [0], [0], [sum(vals) / length(vals)], [vals])
    # Two axes, each with unequal leaf sizes so the two estimators must disagree.
    f1 = DRF.Forest([leafonly([1.0, 2.0]), leafonly(collect(10.0:1.0:40.0))], 1, true, [0.0])
    f2 = DRF.Forest([leafonly([100.0, 200.0]), leafonly(collect(1000.0:100.0:4000.0))], 1, true, [0.0])
    cop = DRF.GaussianCopula([1.0 0.3; 0.3 1.0])
    x = [0.0]

    d_def = DRF.sample_copula!(DRF.Xoshiro256pp(11), cop, [f1, f2], x)
    d_off = DRF.sample_copula!(DRF.Xoshiro256pp(11), cop, [f1, f2], x; qrf = false)
    d_qrf = DRF.sample_copula!(DRF.Xoshiro256pp(11), cop, [f1, f2], x; qrf = true)

    @test d_def == d_off                      # default unchanged (guardrail 4)
    @test length(d_qrf) == 2
    @test all(isfinite, d_qrf)
    # Same RNG stream, so the uniforms are identical and any difference is the marginal estimator alone.
    @test d_qrf != d_def
end
