# Component-S Phase 3A Stage 2 (ADR 0049) — the WIRED-IN trait-dependent mortality operator.
#
# Stage 1 (ADR 0047, `slow_trait_mortality_tests.jl`) gates the ported hazard's EQUATIONS and PARAMETERS
# against the C. This file gates the OPERATOR: what happens when `reconcile_demography!` uses that hazard
# to decide which cohorts die instead of thinning them all by one factor.
#
# The four things it has to prove, in order of how expensive getting them wrong would be:
#
#   1. THE DEFAULT IS INERT (guardrail 4). `trait_mortality = false` must not evaluate the hazard, must
#      record no diagnostics, and must leave the trajectory bit-identical. The committed ReferenceTests +
#      the Hainich gate cover the numeric side globally; here the point is that the flag, the counter
#      roster and the diagnostics vector are all genuinely dormant.
#   2. THE COUNT TARGET IS STILL THE DRF'S. The hazard redistributes WHICH cohorts die; if it also moved
#      HOW MANY, the DRF's 0.9824 OOS count skill would be silently overridden. The test exploits a fact
#      that makes this checkable EXACTLY rather than approximately: in the first thinning year both arms
#      start from the identical state and see the identical DRF target, so their total tree `nind` after
#      that year must agree to floating point while their per-cohort split must NOT.
#   3. THE OPERATOR ACTUALLY SELECTS. ADR 0046 §4's central measurement is that the uniform ρ-thinning is
#      composition-preserving to floating point — so the community wood-density mean is INVARIANT under
#      the control's mortality and must MOVE under the arm's. That contrast is the whole mechanism claim,
#      and it is asserted as an identity on the control side, not merely as a difference.
#   4. CARBON STILL CLOSES (guardrail 2) and the roster stays in lockstep. The operator adds a fifth
#      per-cohort roster vector (`bm_inc_counter`); design risk #5 is exactly that one of these falls out
#      of step with the others across an append/merge.
#
# It also pins `_hazard_tilt`'s two load-bearing properties — that θ = 1 recovers FIT's own hazard exactly
# (so the tilt is a reconciliation, not a replacement), and that a hard kill is never resurrected to hit
# the count target but is REPORTED as a shortfall instead.

@testitem "Trait-dependent mortality (ADR 0049) — the tilt solver's own properties" tags = [:scientific, :slow] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using Test
    const S = LPJmLFITEmulator

    mk(n) = FDiff.TreePools{Float64}(10.0, 20.0, 0.0, 10.0, 0.0, 12.0, 5.0, n, 0.02, 2.0e5, false)
    pools = [mk(1.0), mk(2.0), mk(0.5)]
    haz = [0.0, 0.2, 0.5]
    n_now = sum(p.nind for p in pools)
    tot(θ) = sum(p.nind * (1 - h <= 0 ? 0.0 : (1 - h)^θ) for (p, h) in zip(pools, haz))

    # (a) the solver hits the target exactly, for a range of ρ, and the survival fraction stays in [0,1]
    for ρ in (0.999, 0.99, 0.95, 0.8, 0.7, 0.5)
        θ, sf = S._hazard_tilt(haz, pools, ρ * n_now, n_now)
        @test sf == 0.0
        @test θ ≥ 0
        @test tot(θ) ≈ ρ * n_now rtol = 1.0e-12
        @test all(0 ≤ (1 - h)^θ ≤ 1 for h in haz)
    end

    # (b) θ = 1 EXACTLY recovers FIT's own hazard. This is the property that makes the tilt a
    #     reconciliation with the DRF rather than a different mortality model: when the DRF's ρ happens to
    #     equal the hazard's own nind-weighted survival, the operator applies FIT unmodified.
    fit_total = sum(p.nind * (1 - h) for (p, h) in zip(pools, haz))
    θ1, _ = S._hazard_tilt(haz, pools, fit_total, n_now)
    @test θ1 ≈ 1.0 rtol = 1.0e-10

    # (c) MONOTONE + ORDER-PRESERVING: more required death ⇒ larger θ, and the ranking of survival never
    #     flips (the reason a linear renormalization was rejected — it distorts pairwise ratios).
    θs = [S._hazard_tilt(haz, pools, ρ * n_now, n_now)[1] for ρ in (0.95, 0.9, 0.8, 0.6)]
    @test issorted(θs)
    for θ in θs
        surv = [(1 - h)^θ for h in haz]
        @test issorted(surv; rev = true) == issorted(haz)        # haz ascending ⇒ survival descending
    end

    # (d) a HARD KILL is never resurrected to reach the count target — it is reported as a shortfall.
    #     Two of three cohorts condemned (3.0 of 3.5 density) but ρ = 0.99 wants only 0.035 removed.
    θh, sfh = S._hazard_tilt([1.0, 1.0, 0.0], pools, 0.99 * n_now, n_now)
    @test θh == 0.0                                              # spare everything not condemned
    @test sfh > 0                                                # and SAY the DRF was overridden
    @test sfh ≈ (0.99 * n_now - 0.5) / n_now rtol = 1.0e-9       # exactly the unreachable remainder

    # (e) the MIRROR unreachable case: an all-zero hazard has nothing to tilt, so no θ removes anything.
    #     The solver must terminate (the bracket is bounded, it never loops) AND report the miss — a silent
    #     0 here would read as "the count target was honoured" in the one year it could not be.
    θz, sfz = S._hazard_tilt(zeros(3), pools, 0.5 * n_now, n_now)
    @test isfinite(θz)
    @test sfz ≈ 0.5 rtol = 1.0e-9        # nothing died, so the whole 50 % the DRF wanted is missed
end

@testitem "Trait-dependent mortality (ADR 0049) — operator: DRF count preserved, composition NOT (Hainich 42490)" tags = [:conservation, :coupling, :scientific, :slow] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
    using LPJmLFITEmulator.DRF
    using Test

    _mean(x) = sum(x) / length(x)
    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
        hdr = split(strip(lines[1]), ',')
        rows = [split(strip(l), ',') for l in lines[2:end]]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end
    ind = readcsv(joinpath(refdir, "hainich_individuals_2010.csv"))
    f = readcsv(joinpath(refdir, "hainich_forcing_2010.csv"))
    fc_(k) = parse.(Float64, f[k])
    v(k, r) = parse(Float64, ind[k][r])
    nt(r) = parse(Int, ind["type"][r])
    nday = length(fc_("doy"))

    sd = Float64[]; whcs = Float64[]; rdist = Float64[]
    for ln in eachline(joinpath(refdir, "hainich_soilcolumn.txt"))
        s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
        x = parse.(Float64, split(s)); push!(sd, x[2]); push!(whcs, x[3]); push!(rdist, x[4])
    end
    soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)

    prows = Dict{Int, Vector{Int}}()
    for r in eachindex(ind["type"])
        (nt(r) <= 6 && v("height", r) > 0) && push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
    end
    rows = prows[argmax(Dict(k => length(vv) for (k, vv) in prows))]
    mkp(r) = TreePools{Float64}(
        v("leaf_c", r), v("sapwood_c", r),
        max(v("agb", r) / v("nind", r) - v("leaf_c", r) - v("sapwood_c", r), 0.0), v("root_c", r),
        v("height", r), v("crownarea", r), v("nind", r), v("sla", r), v("wooddens", r), false,
    )
    mkt(r) = Individual{Float64}(
        v("fpar_leafon", r), 0.0, v("alphaa", r), v("albedo_leaf", r), v("emax", r),
        v("sapwood_c", r), v("root_c", r), 0.0, 0.02, 0.04, 0.1, 0.4, v("nind", r),
        PhotoParams{Float64}(; path = :c3, issla = true, sla = v("sla", r)),
        TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false,
    )
    tair_K = fc_("temp") .+ 273.15
    σ = 5.670374419e-8
    year_forc = [
        AtmForcing(;
                swdown = fc_("swdown")[i], lwdown = fc_("lwnet")[i] + σ * tair_K[i]^4,
                tair = tair_K[i], qair = fc_("huss")[i], wind = 2.0, psurf = 1.0e5,
                precip = fc_("precip")[i], co2 = fc_("co2")[i]
            ) for i in 1:nday
    ]
    # REAL per-PFT ids from the fixture's own `type` column — `FDiffFastCore` would otherwise default every
    # tree to beech (`fast.jl:147`), and the hazard's parameters are genuinely per-PFT (ADR 0031).
    pft_ids = [nt(r) for r in rows]
    @test length(unique(pft_ids)) > 1                    # the test is only meaningful on a mixed patch
    mkcore() = FDiffFastCore([mkp(r) for r in rows], [mkt(r) for r in rows], soil, 51.25; pft_ids = pft_ids)
    mkclo() = SEBEnergyClosure(; t_soil0 = _mean(tair_K))
    mkstate() = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))

    # a controllable DRF keyed on the AR feature (column 11) ⇒ ρ ≈ c; c < 1 forces THINNING every year.
    nbound = 3
    nfeat = 11 + nbound
    function ratio_forest(c; seed = 7)
        r = DRF.Xoshiro256pp(seed)
        m = 3000
        X = Matrix{Float64}(undef, m, nfeat); y = Vector{Float64}(undef, m)
        for i in 1:m
            for ff in 1:nfeat
                X[i, ff] = DRF.rand01!(r)
            end
            ar = 0.5 + 59.5 * DRF.rand01!(r)
            X[i, 11] = ar
            y[i] = c * ar + 0.005 * (DRF.rand01!(r) - 0.5)
        end
        return DRF.fit_forest(X, y; ntrees = 60, subsample = 1500, max_depth = 16, min_leaf = 6, mtry = nfeat, seed = seed)
    end
    boundary = [0.3, 0.5, 0.7]
    forest = ratio_forest(0.85)

    "nind-weighted community mean over LIVE TREE cohorts."
    function cmean(pools, g)
        num = 0.0; den = 0.0
        for p in pools
            (p.is_grass || p.nind <= 0) && continue
            num += p.nind * g(p); den += p.nind
        end
        return den > 0 ? num / den : NaN
    end
    ntree(pools) = sum(p.nind for p in pools if !p.is_grass; init = 0.0)

    # ── run TWO years in each arm. Year 1 forces ρ = 1 (the AR seed), so year 2 is the FIRST thinning
    #    year — and because both arms enter it from the identical state with the identical forest, they
    #    see the identical ρ. That makes the count claim an EXACT comparison, not a statistical one. ──
    forcings = repeat(year_forc, 2)
    ctl_core = mkcore()
    ctl = FluxDrivenSlowEmulator(ctl_core, forest; boundary = boundary, n_init = 10.0, seed = 1)
    arm_core = mkcore()
    arm = FluxDrivenSlowEmulator(
        arm_core, forest; boundary = boundary, n_init = 10.0, seed = 1, trait_mortality = true
    )
    wd0 = cmean(mkcore().pools, p -> p.wooddens)
    run_coupled_cell(ctl_core, mkclo(), mkstate(), forcings; slow = ctl, days_per_year = nday)
    run_coupled_cell(arm_core, mkclo(), mkstate(), forcings; slow = arm, days_per_year = nday)

    # (1) THE DEFAULT IS INERT: the control never evaluated the hazard.
    @test isempty(trait_mortality_diag(ctl))
    @test isempty(ctl.mort_diag)
    @test all(==(0), ctl.bm_inc_counter)                 # never advanced

    # (2) THE OPERATOR FIRED — asserted before anything is inferred from a difference (ADR 0048's own
    #     correction: a null from an operator that never ran bounds nothing).
    dg = trait_mortality_diag(arm)
    @test length(dg) == 2
    @test any(d -> d.thinned, dg)                        # ρ < 1 at least once ⇒ the operator reshaped
    thin = dg[findfirst(d -> d.thinned, dg)]
    @test isfinite(thin.theta) && thin.theta > 0         # a real tilt was solved for
    @test 0 < thin.hazard_mean < 1                       # FIT's hazard is non-degenerate on this patch
    @test all(d -> d.shortfall == 0, dg)                 # the DRF count target was honoured every year

    # (3) THE COUNT TARGET IS STILL THE DRF'S — identical total, in the year both arms share a ρ.
    @test ntree(arm_core.pools) ≈ ntree(ctl_core.pools) rtol = 1.0e-10
    @test arm.target_history ≈ ctl.target_history rtol = 1.0e-10

    # (4) BUT THE COMPOSITION MOVED. The uniform thinning is composition-preserving to floating point
    #     (ADR 0046 §4) — assert that as an IDENTITY on the control, so the arm's move cannot be dismissed
    #     as numerical noise. (The control's mean can still drift from `wd0` via ESTABLISHMENT; with
    #     ρ < 1 every year no recruit is appended, so it must be exactly invariant here.)
    @test cmean(ctl_core.pools, p -> p.wooddens) ≈ wd0 rtol = 1.0e-12
    @test !isapprox(cmean(arm_core.pools, p -> p.wooddens), wd0; rtol = 1.0e-8)
    # per-cohort: the control scaled every cohort by ONE factor, the arm did not
    ctl_frac = [p.nind for p in ctl_core.pools if !p.is_grass]
    arm_frac = [p.nind for p in arm_core.pools if !p.is_grass]
    @test length(ctl_frac) == length(arm_frac)
    @test !all(isapprox.(ctl_frac, arm_frac; rtol = 1.0e-10))
    # and the spread of per-cohort survival ratios is what "uniform" versus "selective" means
    ratios = arm_frac ./ ctl_frac
    @test maximum(ratios) - minimum(ratios) > 1.0e-6

    # (5) CARBON STILL CLOSES (guardrail 2) and the roster is in lockstep.
    cscale = sum(FDiff.vegc_full_ind(p) * p.nind for p in mkcore().pools)
    @test maximum(abs, arm.resid_history) ≤ 1.0e-6 * cscale
    @test maximum(abs, arm.resid_history) < 1.0e-6
    @test length(arm.bm_inc_counter) == length(arm_core.pools) == length(arm.age)

    # (6) DETERMINISM: the operator introduces no new stochasticity.
    c2 = mkcore()
    a2 = FluxDrivenSlowEmulator(c2, forest; boundary = boundary, n_init = 10.0, seed = 1, trait_mortality = true)
    run_coupled_cell(c2, mkclo(), mkstate(), forcings; slow = a2, days_per_year = nday)
    @test a2.total_n_history == arm.total_n_history
    # `isequal`, not `==`: a non-thinning year records θ = NaN by design, and NaN != NaN
    @test all(isequal(x, y) for (x, y) in zip((d.theta for d in trait_mortality_diag(a2)), (d.theta for d in dg)))

    # (7) A NON-TREE PFT id ERRORS rather than silently running the wrong PFT's hazard. `pft_mort_params`
    #     refuses grass ids 7-9; the operator must therefore refuse a mis-wired roster at the call site,
    #     which is the ADR-0031 defect class (M integration point #1 defaults every tree to beech).
    bad_core = FDiffFastCore(
        [mkp(r) for r in rows], [mkt(r) for r in rows], soil, 51.25;
        pft_ids = fill(7, length(rows))                  # grass id on tree cohorts — impossible, must throw
    )
    bad = FluxDrivenSlowEmulator(
        bad_core, forest; boundary = boundary, n_init = 10.0, seed = 1, trait_mortality = true
    )
    @test_throws ErrorException run_coupled_cell(
        bad_core, mkclo(), mkstate(), forcings; slow = bad, days_per_year = nday
    )

    # (8) the roster survives ESTABLISHMENT with the operator on (ρ > 1 appends a cohort; the counter
    #     vector must grow with `age`/`pools`, or design risk #5 has reopened).
    gcore = mkcore()
    gs = FluxDrivenSlowEmulator(
        gcore, ratio_forest(1.12); boundary = boundary, n_init = 10.0, seed = 1, trait_mortality = true
    )
    run_coupled_cell(gcore, mkclo(), mkstate(), repeat(year_forc, 3); slow = gs, days_per_year = nday)
    @test length(gcore.pools) > length(rows)             # a recruit really was appended
    @test length(gs.bm_inc_counter) == length(gcore.pools) == length(gs.age)
    @test maximum(abs, gs.resid_history) < 1.0e-6

    # (9) Float32 (the SpeedyWeather-coupling element type) runs, conserves and selects. Built from the
    #     fixture directly rather than converted from the Float64 structs — the same positional
    #     constructors `mkp`/`mkt` use, so no field name is assumed.
    v32(k, r) = Float32(v(k, r))
    p32 = [
        TreePools{Float32}(
                v32("leaf_c", r), v32("sapwood_c", r),
                Float32(max(v("agb", r) / v("nind", r) - v("leaf_c", r) - v("sapwood_c", r), 0.0)),
                v32("root_c", r), v32("height", r), v32("crownarea", r), v32("nind", r),
                v32("sla", r), v32("wooddens", r), false,
            ) for r in rows
    ]
    t32 = [
        Individual{Float32}(
                v32("fpar_leafon", r), 0.0f0, v32("alphaa", r), v32("albedo_leaf", r), v32("emax", r),
                v32("sapwood_c", r), v32("root_c", r), 0.0f0, 0.02f0, 0.04f0, 0.1f0, 0.4f0, v32("nind", r),
                PhotoParams{Float32}(; path = :c3, issla = true, sla = v32("sla", r)),
                TempStressParams{Float32}(; temp_photos_low = 20.0f0, temp_photos_high = 30.0f0), false,
            ) for r in rows
    ]
    soil32 = hainich_soilcolumn(
        Float32; whcs = Float32.(whcs), rootdist = Float32.(rdist), soildepth = Float32.(sd)
    )
    # Driven exactly as the existing Float32 gate drives it (`slow_flux_driven_tests.jl:149`): prime the
    # within-year accumulators by hand and call the handoff directly, so the Float32 check is about the
    # OPERATOR's type stability and not about a second forcing construction.
    c32 = FDiffFastCore(p32, t32, soil32, 51.25f0; pft_ids = pft_ids)
    c32.nday = 365
    c32.wscal_acc = 0.9f0 * 365
    for i in eachindex(c32.pools)
        c32.bm_inc_acc[i] = 400.0f0 * c32.pools[i].nind
    end
    cscale32 = sum(FDiff.vegc_full_ind(p) * p.nind for p in c32.pools)
    s32 = FluxDrivenSlowEmulator(
        c32, forest; boundary = boundary, n_init = 10.0f0, seed = 1, trait_mortality = true
    )
    @test s32 isa FluxDrivenSlowEmulator{Float32}
    g32 = grow_annual_accounted!(c32)
    reconcile_demography!(s32, c32, g32, SharedState(; w = fill(0.7f0, LPJmLFITEmulator.NSOILLAYER)))
    @test s32.last_resid isa Float32
    @test isfinite(s32.last_resid) && abs(s32.last_resid) ≤ 1.0f-5 * cscale32
    @test all(p -> isfinite(p.nind) && p.nind ≥ 0, c32.pools)
    d32 = trait_mortality_diag(s32)
    @test length(d32) == 1                               # the operator ran in Float32 …
    @test d32[1].hazard_mean isa Float64                 # … and the diagnostic is type-stable Float64
    @test 0 ≤ d32[1].hazard_mean < 1
end
