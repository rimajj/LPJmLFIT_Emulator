# Gate — dynamic (prognostic within-year) canopy structure (ADR 0014 scale-up step 6;
# docs/phase3_fdiff_cbinary_validation.md §12). The multi-individual canopy (step 3) fixed each
# individual's structure at its year-END value; here the per-individual carbon pools become PROGNOSTIC:
# they accumulate the daily bm_inc (= Σ daily NPP) and, at the annual boundary, GROW via a faithful
# DIFFERENTIABLE port of the LPJmL-FIT year-end sequence turnover_tree.c → allocation_tree.c →
# allometry_tree.c (annual_tree.c:29-30). This is the flux-then-integrate S↔F carbon handoff (DESIGN §8):
# F delivers the conserved bm_inc, the pipe-model allocation partitions it into leaf/sapwood/heartwood/
# root subject to the leaf-area:sapwood-area (k_latosa) + leaf:root (lmtorm) + Jucker crown/height
# allometry, then height/crownarea/LAI/FPC are re-derived by growing structure.
#
# DECISIVE checks (all self-contained on the committed 2010 reference — no HPC/`/p/tmp` dependency):
#  1. the pipe-model INVARIANT holds after allocation (leaf ≈ k_latosa·sapwood/(wooddens·H·sla)) —
#     proves the differentiable allocation solve reproduces the C's allometric constraint;
#  2. carbon CONSERVATION: Δ(pools) = bm_net − turnover-to-litter (allocation invents no carbon);
#  3. GROWTH direction: bm_inc>0 ⇒ agb/height increase;
#  4. AD: d(height)/d(bm_inc) and d(sapwood)/d(bm_inc) match finite differences (ForwardDiff);
#  5. MULTI-YEAR coupled rollout (rollout_canopy_years) is now FULLY SELF-DRIVEN (no bm_inc crutch): the
#     self-computed canopy NPP feeds the allocation, and the structure stays physical + grows across years.
# NB: F_diff's SELF-computed canopy NPP is now CALIBRATED (docs §13) — the growth-resp max(0,·) floor was
# sharpened (RespParams.βgrowth) + the fine-root maintenance is phen-gated (npp_tree.c:51-52), taking
# annual self-NPP from −25 to +663 gC/m²/yr; the bm_inc crutch is removed. Self-NPP magnitude is gated in
# multi_individual_tests.jl; here we confirm the self-driven coupled loop grows structure without blow-up.
@testitem "Dynamic canopy structure — differentiable allocation (Hainich 42490, 2010)" tags = [:validation, :fdiff, :canopy, :structure] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.Allometry
    using Test

    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = readlines(path)
        i = findfirst(l -> !startswith(strip(l), "#") && !isempty(strip(l)), lines)
        hdr = split(strip(lines[i]), ',')
        rows = [split(strip(l), ',') for l in lines[(i + 1):end] if !isempty(strip(l))]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end
    ind = readcsv(joinpath(refdir, "hainich_individuals_2010.csv"))
    v(k, r) = parse(Float64, ind[k][r])
    ntyp(r) = parse(Int, ind["type"][r])

    allom = Allometry.TreeAllometry{Float64}()          # angiosperm beech (par/pft_lpjmlfit.js ANGIO)
    alloc = tebs_allocparams()

    # build per-tree TreePools + the per-individual C bm_inc from the committed reference:
    #   heartwood_c = agb_perm2/nind − leaf_c − sapwood_c  (agb = (leaf+sap+heart)·nind, agb_tree.c:25)
    #   bm_inc_ind  = npp_ind/nind  (npp_ind = per-m² annual NPP; /nind → per-individual, allocation_tree.c:236)
    treerows = [r for r in eachindex(ind["type"]) if ntyp(r) <= 6 && v("height", r) > 0]
    function pools(r)
        nind = v("nind", r); leaf = v("leaf_c", r); sap = v("sapwood_c", r)
        heart = max(v("agb", r) / nind - leaf - sap, 0.0)
        return TreePools{Float64}(
            leaf, sap, heart, v("root_c", r), v("height", r), v("crownarea", r),
            nind, v("sla", r), v("wooddens", r), false
        )
    end
    bm_incs = [v("npp_ind", r) / v("nind", r) for r in treerows]   # per-individual annual bm_inc (gC)
    trees = [pools(r) for r in treerows]
    @test length(trees) > 200

    # ── 1. pipe-model invariant + 3. growth direction + 2. conservation ──
    maxrel = 0.0; nup = 0; maxcons = 0.0
    for (tr, bm) in zip(trees, bm_incs)
        ng = grow_individual(alloc, allom, tr, bm, 0.85)
        if ng.height > 0 && ng.sapwood_c > 0
            leaf_pred = allom.k_latosa * ng.sapwood_c / (ng.wooddens * ng.height * ng.sla)
            maxrel = max(maxrel, abs(leaf_pred - ng.leaf_c) / (ng.leaf_c + 1.0e-9))
        end
        (bm > 0 && agb_ind(ng) > agb_ind(tr)) && (nup += 1)
        # conservation: Δvegc = bm_net − turnover-to-litter (leaf recycle + root turnover; sapwood→heartwood internal)
        bm_net = bm * (1 - alloc.reprod_cost)
        turn_leaf = tr.leaf_c / alloc.deciduous_leaf_div
        turn_root = tr.root_c * alloc.turnover_root
        dveg = vegc_ind(ng) - vegc_ind(tr)
        maxcons = max(maxcons, abs(dveg - (bm_net - turn_leaf - turn_root)))
    end
    @test maxrel < 1.0e-8                    # pipe-model relation holds to ~machine precision after allocation
    @test maxcons < 1.0e-6                   # carbon conserved by the allocation (net of turnover)
    @test nup / length(trees) > 0.9          # bm_inc>0 grows aboveground biomass

    # ── 5. multi-year COUPLED rollout — FULLY SELF-DRIVEN (self-computed NPP, no crutch): stable + grows ──
    f = readcsv(joinpath(refdir, "hainich_forcing_2010.csv"))
    fc(k) = parse.(Float64, f[k])
    n = length(fc("doy"))
    forc = [
        DailyForcing{Float64}(
                swdown = fc("swdown")[i], lwnet = fc("lwnet")[i], temp = fc("temp")[i],
                precip = fc("precip")[i], daylength = fc("daylength")[i], co2 = fc("co2")[i]
            ) for i in 1:n
    ]
    sd = Float64[]; whcs = Float64[]; rdist = Float64[]
    for ln in eachline(joinpath(refdir, "hainich_soilcolumn.txt"))
        s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
        vv = parse.(Float64, split(s)); push!(sd, vv[2]); push!(whcs, vv[3]); push!(rdist, vv[4])
    end
    soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)
    # one patch's trees + templates (patch with the most trees)
    prows = Dict{Int, Vector{Int}}()
    for r in treerows
        push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
    end
    pbig = argmax(Dict(k => length(vv) for (k, vv) in prows))
    rows = prows[pbig]
    tmpl(r) = Individual{Float64}(
        v("fpar_leafon", r), 0.0, v("alphaa", r), v("albedo_leaf", r), v("emax", r), v("sapwood_c", r), v("root_c", r),
        0.0, 0.02, 0.04, 0.1, 0.4, v("nind", r),
        FDiff.PhotoParams{Float64}(; path = :c3, issla = true, sla = v("sla", r)),
        FDiff.TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false,
    )
    pool0 = [pools(r) for r in rows]
    tmpls = [tmpl(r) for r in rows]
    NY = 5
    st0 = FDiffStateML{Float64}([0.9 * w for w in whcs], 0.0)
    (_, _, poolshist, annual) = rollout_canopy_years(
        tebs_params(), alloc, allom, st0, pool0, tmpls, soil, [forc for _ in 1:NY]     # no bm_inc_ext ⇒ self-driven
    )
    @test length(annual) == NY
    # self-computed NPP is delivered as the conserved bm_inc each year (positive, physical)
    @test all(isfinite(a.npp) && a.npp > 0 for a in annual)
    # physical + smoothly growing structure across years (no blow-up, heights bounded, monotone AGB)
    for y in 1:NY
        @test isfinite(annual[y].agb) && annual[y].agb > 0
        @test all(0 < t.height <= allom.height_max && isfinite(t.height) for t in poolshist[y])
        @test all(t.sapwood_c > 0 && t.heartwood_c >= 0 && t.leaf_c > 0 for t in poolshist[y])
    end
    @test annual[NY].agb > annual[1].agb                  # cumulative growth from the self-computed NPP
    # mean-height growth rate is gradual + physical (not a jump)
    h1 = sum(t.height for t in poolshist[1]) / length(pool0)
    h5 = sum(t.height for t in poolshist[NY]) / length(pool0)
    @test 0 < (h5 - h1) < 5.0                             # a few years of beech height growth, not a blow-up
end

@testitem "Dynamic canopy structure — differentiable (ForwardDiff through the annual allocation)" tags = [:gradient, :fdiff, :canopy, :structure] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.Allometry
    using ForwardDiff, FiniteDifferences
    using Test

    allom = Allometry.TreeAllometry{Float64}()
    alloc = tebs_allocparams()
    # a representative beech tree AT pipe-model equilibrium (leaf ≈ k_latosa·sapwood/(wooddens·H·sla)) so a
    # generous bm_inc lands in the NORMAL (growing) allocation branch — as opposed to the abnormal branch,
    # where the C's allocation holds height fixed and only reshuffles sapwood↔heartwood (d(height)/d(bm)=0).
    mktree(::Type{S}) where {S} = TreePools{S}(
        S(2769.0), S(33000.0), S(120000.0), S(2769.0), S(12.0), S(15.8), S(1 / 225), S(0.01986), S(2.0e5), false,
    )
    bm_eval = 15000.0                                    # comfortably exceeds leaf_min+root_min ⇒ normal branch
    # differentiate the grown height / sapwood w.r.t. the delivered annual bm_inc (the flux-then-integrate input)
    gh(bm) = grow_individual(alloc, allom, mktree(typeof(bm)), bm, 0.85).height
    gs(bm) = grow_individual(alloc, allom, mktree(typeof(bm)), bm, 0.85).sapwood_c
    fdm = central_fdm(5, 1)
    for (name, f) in (("height", gh), ("sapwood", gs))
        gad = ForwardDiff.derivative(f, bm_eval)
        gfd = fdm(f, bm_eval)
        @test isfinite(gad) && isfinite(gfd)
        @test isapprox(gad, gfd; rtol = 1.0e-4, atol = 1.0e-8)
    end
    # a genuinely non-zero, physical response: more bm_inc ⇒ taller + more sapwood
    @test ForwardDiff.derivative(gh, bm_eval) > 0
    @test ForwardDiff.derivative(gs, bm_eval) > 0

    # differentiate w.r.t. the photosynthesis parameter α_c3 through a coupled daily-year + allocation:
    # one year of the multi-individual daily canopy → bm_inc → grow_individual, all ForwardDiff-tracked
    # (the daily fpar is fixed within the year, as in daily_step_canopy).
    whcs = [37.0, 53.0, 88.0, 175.0, 175.0]
    rootdist = [0.41, 0.32, 0.2, 0.07, 0.0]
    soildepth = [200.0, 300.0, 500.0, 1000.0, 1000.0]
    mkforc(::Type{S}) where {S} = [
        DailyForcing{S}(swdown = 220.0, lwnet = -45.0, temp = 19.0, precip = (d % 4 == 0 ? 8.0 : 0.3), daylength = 14.0, co2 = 380.0)
            for d in 1:40
    ]
    function grown_height(x)                              # x = α_c3
        T = typeof(x)
        ind = Individual{T}(
            T(0.35), T(0.18), T(0.55), T(0.15), T(10.0), T(33000.0), T(1500.0), T(4.0), T(0.02), T(0.04), T(0.1), T(0.4), T(1 / 225),
            FDiff.PhotoParams{T}(; path = :c3, issla = true, sla = T(0.01986), alphac3 = x),
            FDiff.TempStressParams{T}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false,
        )
        soil = hainich_soilcolumn(T; whcs = whcs, rootdist = rootdist, soildepth = soildepth)
        st0 = FDiffStateML{T}(T[0.7 * w for w in whcs], zero(T))
        (_, days) = rollout_daily_canopy(FDiff.tebs_params(T), st0, [ind], soil, mkforc(T))
        bm = sum(d.npp_ind[1] for d in days) / T(1 / 225)   # per-individual bm_inc from the daily rollout
        return grow_individual(alloc, Allometry.TreeAllometry{T}(), mktree(T), bm, 0.85).height
    end
    gad = ForwardDiff.derivative(grown_height, 0.08)
    gfd = fdm(grown_height, 0.08)
    @test isfinite(gad) && isfinite(gfd)
    @test isapprox(gad, gfd; rtol = 1.0e-3, atol = 1.0e-6)   # gradient flows daily-flux → bm_inc → allocation → structure
end
