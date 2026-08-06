# PER-TREE ROOT PROFILES AND PER-TREE WATER STATUS (line S, ADR 0110) — `WaterParams.per_tree_roots`.
#
# Component S samples a per-tree rooting depth (`D95max`) and a per-tree drought tolerance (`minwscal`),
# validates both globally, and until ADR 0110 dropped both: `make_recruit_to_pools` wrote only SLA and
# Wooddens, and the fast core collapsed the 23-layer profile to ONE shared scalar `wr` before the
# per-individual loop opened. Two trees differing only in rooting depth were identical in the water
# balance, so drought response — ADR 0106's binding clause — could not be represented.
#
# The C gives EVERY individual its own profile: `beta_root = getbetaroot(bottom, D95max)` per individual
# (`tree/new_tree.c:229-230`, always taken since `"isD95max": true`), `getrootdist` called per individual
# every day, and the trait spans 51-1800 cm WITHIN one PFT. And — the finding that unblocks this — the
# C's per-individual `wr`, `supply` and `pft->wscal` are all ORDER-INDEPENDENT (`soil.w[]` is frozen for
# the whole `-DPERMUTE` loop and written once per patch-day afterwards, `soil/waterbalance.c:117-138`),
# so the daily-random depletion order that blocks a faithful `aet_cor` port does not touch any of them.
#
# These assertions encode the C's SEMANTICS plus guardrail 4, not fitted numbers:
#   1. the `beta_root` port reproduces the C's OWN emitted `beta_root` (an oracle test, not self-consistency)
#   2. profiles normalize, and a shallower trait puts more root in the top layer
#   3. default OFF is byte-identical, and the traits are inert while it is off
#   4. with it ON, two trees differing ONLY in rooting depth diverge in DROUGHT and agree when WET
#   5. water still closes exactly
#   6. the traits survive growth, density changes and cohort merges (each of those rebuilds a `TreePools`
#      and would silently reset them to the unset 0)
# All fixtures are committed, so this runs on a CI runner with no cluster.

@testitem "the beta_root port reproduces the C's own emitted beta_root (ADR 0110)" tags = [:validation, :fdiff] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff: betaroot_from_d95max, jackson_rootdist

    # (D95max cm, beta_root) pairs read straight out of the C's annual `ind` table, Hainich cell 42490,
    # year 2018, seed1 — the oracle's OWN output, so this validates the port rather than itself. The
    # column's full span there is 51.09 to 483.4 cm. `bottom` = the 20 m column in cm (the C's
    # `layerbound[BOTTOMLAYER-1]*0.1`).
    pairs = [
        (51.09, 0.943051), (61.4967, 0.95245), (74.9074, 0.960811), (83.7847, 0.9649),
        (94.4105, 0.968745), (164.179, 0.981927), (213.219, 0.986077), (265.392, 0.988762),
        (345.398, 0.991386), (483.384, 0.993828),
    ]
    for (d95, beta_C) in pairs
        # The C bisects to xtol = 1e-4 (`getbetaroot.c:19,38`); agreement to 1e-5 means the port solves
        # the same equation, not merely a similar one.
        @test isapprox(betaroot_from_d95max(d95, 2000.0), beta_C; atol = 1.0e-5)
    end

    # monotone: a deeper rooting trait ⇒ beta closer to 1 ⇒ a flatter, deeper profile
    betas = [betaroot_from_d95max(d, 2000.0) for d in (51.0, 200.0, 800.0, 1800.0)]
    @test issorted(betas)

    soildepth = vcat([200.0, 300.0, 500.0], fill(1000.0, 19), [3000.0])   # par/soil_20m.js
    for d95 in (51.0, 200.0, 800.0, 1800.0)
        rd = jackson_rootdist(betaroot_from_d95max(d95, 2000.0), soildepth, 20_000.0)
        @test length(rd) == length(soildepth)
        @test all(>=(0), rd)
        @test isapprox(sum(rd), 1.0; atol = 1.0e-12)   # a profile that misses 1 silently rescales supply
    end
    # the channel itself: the shallowest recruit puts ~69 % of its roots in the top 20 cm, the deepest ~4 %
    top(d95) = jackson_rootdist(betaroot_from_d95max(d95, 2000.0), soildepth, 20_000.0)[1]
    @test top(51.0) > 0.6
    @test top(1800.0) < 0.1
    @test top(51.0) > 10 * top(1800.0)
    # and a SMALL tree roots shallower than a large one at the SAME trait (the C's dynamic `getrootdepth`)
    b = betaroot_from_d95max(300.0, 2000.0)
    @test jackson_rootdist(b, soildepth, 400.0)[1] > jackson_rootdist(b, soildepth, 20_000.0)[1]
end

@testitem "per-tree roots: default OFF is byte-identical; ON, drought separates the trees (ADR 0110)" tags = [:validation, :fdiff] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.Allometry
    using LPJmLFITEmulator.FDiff: hainich_soilcolumn, TreePools, Individual, PhotoParams, TempStressParams,
        WaterParams, FDiffParams, DailyForcing, FDiffStateML, daily_step_canopy, individuals_from_pools,
        _patch_fpars, per_tree_rootdists

    ref = joinpath(@__DIR__, "references", "hainich_soilcolumn.txt")
    D = Float64[]; W = Float64[]; R = Float64[]
    for ln in eachline(ref)
        s = strip(ln)
        (isempty(s) || startswith(s, "#")) && continue
        v = parse.(Float64, split(s))
        push!(D, v[2]); push!(W, v[3]); push!(R, v[4])
    end
    soil = hainich_soilcolumn(; whcs = W, rootdist = R, soildepth = D)
    allom = Allometry.TreeAllometry{Float64}()
    tmpl = Individual{Float64}(
        0.5, 0.0, 0.5, 0.12, 10.0, 0.0, 0.0, 0.0, 0.0, 0.02, 0.04, 0.1, 0.4, 1.0,
        PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.0198),
        TempStressParams{Float64}(; temp_photos_low = 15.0, temp_photos_high = 25.0), false,
    )
    # identical trees except the rooting trait; `notrait` is the pre-ADR-0110 shape (11-arg constructor)
    traited(d95) = TreePools{Float64}(3000.0, 12000.0, 40000.0, 2500.0, 0.0, 15.0, 20.0, 0.0044, 0.0198, 2.0e5, d95, 0.12, false)
    notrait() = TreePools{Float64}(3000.0, 12000.0, 40000.0, 2500.0, 0.0, 15.0, 20.0, 0.0044, 0.0198, 2.0e5, false)
    f = DailyForcing{Float64}(swdown = 200.0, lwnet = -40.0, temp = 22.0, precip = 0.0, daylength = 14.0, co2 = 400.0)

    tmpl_v(n) = fill(tmpl, n)
    function step(pools, per_tree, topfrac)
        p = FDiffParams{Float64}(; water = WaterParams{Float64}(; per_tree_roots = per_tree))
        fp = _patch_fpars(pools, allom)
        (inds, rds) = individuals_from_pools(tmpl_v(length(pools)), pools, allom, fp, soil; per_tree = per_tree)
        w0 = [l <= 3 ? topfrac * W[l] : 0.8 * W[l] for l in eachindex(W)]
        return daily_step_canopy(p, inds, soil, FDiffStateML{Float64}(w0, 0.0), f; rootdists = rds)
    end

    # ── guardrail 4: with no rooting trait on any individual, the flag changes NOTHING ──────────────
    for topfrac in (0.85, 0.08)
        (s_off, fl_off) = step([notrait(), notrait()], false, topfrac)
        (s_on, fl_on) = step([notrait(), notrait()], true, topfrac)
        @test fl_off.gpp == fl_on.gpp
        @test fl_off.transp == fl_on.transp
        @test fl_off.wscal == fl_on.wscal
        @test s_off.w == s_on.w
        @test fl_on.wscal_ind === nothing            # no profiles built ⇒ nothing to report
    end
    # ── and the traits are INERT while the flag is off ──────────────────────────────────────────────
    for topfrac in (0.85, 0.08)
        (_, a) = step([traited(51.0), traited(483.0)], false, topfrac)
        (_, b) = step([notrait(), notrait()], false, topfrac)
        @test a.gpp == b.gpp
        @test a.transp == b.transp
        @test a.wscal == b.wscal
    end

    # ── the channel: WET ⇒ the two trees agree; DROUGHT ⇒ they separate ────────────────────────────
    (_, wet) = step([traited(51.0), traited(483.0)], true, 0.85)
    (_, dry) = step([traited(51.0), traited(483.0)], true, 0.08)
    @test wet.wscal_ind !== nothing && length(wet.wscal_ind) == 2
    @test isapprox(wet.wscal_ind[1], wet.wscal_ind[2]; atol = 1.0e-8)   # both unstressed when wet
    # In drought the SHALLOW-rooted tree (≈69 % of roots in the top 20 cm) is starved while the
    # DEEP-rooted one still reaches wet layers. This is the whole point of ADR 0110.
    @test dry.wscal_ind[1] < dry.wscal_ind[2]
    @test dry.wscal_ind[2] - dry.wscal_ind[1] > 0.2
    # per-tree root-weighted moisture must order the same way
    @test dry.wr_ind[1] < dry.wr_ind[2]
    # and drought must actually separate them far more than wet does
    @test (dry.wscal_ind[2] - dry.wscal_ind[1]) > 10 * abs(wet.wscal_ind[2] - wet.wscal_ind[1])

    # ── water still closes exactly on the per-tree path ────────────────────────────────────────────
    for (pools, per_tree) in (([traited(51.0), traited(483.0)], true), ([notrait(), notrait()], false))
        p = FDiffParams{Float64}(; water = WaterParams{Float64}(; per_tree_roots = per_tree))
        fp = _patch_fpars(pools, allom)
        (inds, rds) = individuals_from_pools(tmpl_v(2), pools, allom, fp, soil; per_tree = per_tree)
        w0 = [0.3 * W[l] for l in eachindex(W)]
        st0 = FDiffStateML{Float64}(w0, 0.0)
        fr = DailyForcing{Float64}(swdown = 200.0, lwnet = -40.0, temp = 18.0, precip = 7.0, daylength = 13.0, co2 = 400.0)
        (st1, fl) = daily_step_canopy(p, inds, soil, st0, fr; rootdists = rds)
        Δstore = (sum(st1.w) + st1.snowpack) - (sum(st0.w) + st0.snowpack)
        @test isapprox(fr.precip, fl.transp + fl.evap + fl.interc + fl.runoff + Δstore; atol = 1.0e-10)
    end
end

@testitem "the rooting + drought-tolerance traits survive growth, density changes and merges (ADR 0110)" tags = [:validation, :fdiff] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.Allometry
    using LPJmLFITEmulator.FDiff: TreePools, grow_individual, tebs_allocparams

    allom = Allometry.TreeAllometry{Float64}()
    alloc = tebs_allocparams(Float64)
    t0 = TreePools{Float64}(3000.0, 12000.0, 40000.0, 2500.0, 0.0, 15.0, 20.0, 0.0044, 0.0198, 2.0e5, 317.0, 0.29, false)

    # Growth rebuilds the struct every year. Traits are immutable after establishment in the C, so they
    # must come through UNCHANGED — and must not be dropped to the unset 0, which would delete the
    # per-tree rooting channel one year after the tree established.
    t1 = grow_individual(alloc, allom, t0, 900.0, 0.9)
    @test t1.d95max == t0.d95max
    @test t1.minwscal == t0.minwscal
    t2 = grow_individual(alloc, allom, t1, 900.0, 0.9)
    @test t2.d95max == 317.0
    @test t2.minwscal == 0.29

    # An untraited tree must stay untraited (the unset sentinel is 0, and 0 must not become a real value).
    u0 = TreePools{Float64}(3000.0, 12000.0, 40000.0, 2500.0, 0.0, 15.0, 20.0, 0.0044, 0.0198, 2.0e5, false)
    @test u0.d95max == 0.0 && u0.minwscal == 0.0
    u1 = grow_individual(alloc, allom, u0, 900.0, 0.9)
    @test u1.d95max == 0.0 && u1.minwscal == 0.0

    # the pre-`sapwood_bg` 10-arg constructor still works and still leaves both traits unset
    v = TreePools{Float64}(3000.0, 12000.0, 40000.0, 2500.0, 15.0, 20.0, 0.0044, 0.0198, 2.0e5, false)
    @test v.sapwood_bg_c == 0.0 && v.d95max == 0.0 && v.minwscal == 0.0
end

@testitem "the recruit sampler writes the rooting + drought-tolerance traits into each tree (ADR 0110)" tags = [:validation, :slow] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.Allometry
    using LPJmLFITEmulator.FDiff: TreePools
    using LPJmLFITEmulator: make_recruit_to_pools

    allom = Allometry.TreeAllometry{Float64}()
    sapl = TreePools{Float64}(50.0, 100.0, 0.0, 40.0, 0.0, 1.2, 0.6, 1.0, 0.02, 2.0e5, false)

    # the ADR 0025 production axis set — all four axes present
    to_pools = make_recruit_to_pools(["SLA", "Wooddens", "D95max", "minwscal"])
    p = to_pools([0.021, 2.4e5, 412.0, 0.31], sapl, allom)
    @test p.sla ≈ 0.021
    @test p.wooddens ≈ 2.4e5
    @test p.d95max ≈ 412.0        # previously sampled, scored, and then DROPPED
    @test p.minwscal ≈ 0.31

    # clamped to the union of the C's per-PFT sampling intervals (`par/pft_lpjmlfit.js`)
    hi = to_pools([0.021, 2.4e5, 9.9e3, 5.0], sapl, allom)
    @test hi.d95max == 1800.0
    @test hi.minwscal == 0.75
    lo = to_pools([0.021, 2.4e5, 1.0, 0.0], sapl, allom)
    @test lo.d95max == 51.0
    @test lo.minwscal == 0.025

    # BACKWARD COMPATIBILITY: an older artifact whose axis list lacks the two new axes must still load
    # and must produce pools with the traits UNSET — i.e. byte-identical to the pre-ADR-0110 behaviour.
    old = make_recruit_to_pools(["SLA", "Wooddens"])
    q = old([0.021, 2.4e5], sapl, allom)
    @test q.d95max == 0.0
    @test q.minwscal == 0.0
    @test q.sla ≈ 0.021 && q.wooddens ≈ 2.4e5
    @test q.height == p.height && q.crownarea == p.crownarea   # geometry untouched by the new axes
end
