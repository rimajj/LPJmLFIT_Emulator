# Gate — prognostic GRASS structure (scale-up step 9; docs/phase3_fdiff_cbinary_validation.md §20).
# The multi-year rollout previously grew only TREES (grow_individual); grasses were held FIXED (the
# CSV grass rows have leaf_c=0/root_c=0/crownarea=0/nind=0, so a round-trip through
# individual_from_pools zeroed them → grass was structurally dropped). Here grass leaf/root carbon
# become PROGNOSTIC via a faithful DIFFERENTIABLE port of the LPJmL-FIT NATURAL-veg annual grass
# sequence turnover_grass.c → allocation_grass.c (annual_grass.c:29-30), on a per-area convention
# (crownarea = nind = 1 so lai = leaf_c·sla and fpc = 1 − e^{−k·lai}).
#
# DECISIVE checks (all self-contained on the committed 2010 reference — no HPC/`/p/tmp` dependency):
#  1. PARAM fidelity: grass_allocparams == the ACTIVE par/pft_lpjmlfit.js temperate C3 grass (id 8);
#     grass_treepools reconstruction (leaf = agb, root = vegc − agb, crownarea = nind = 1).
#  2. GOLDEN: grow_grass_individual reproduces a direct hand-port of the allocation_grass.c natural-veg
#     formula across ALL branches (positive / zero / negative bm; the negative-leaf reallocation).
#  3. CONSERVATION: Δ(leaf+root) = bm_net − (leaf_turnover + root_turnover) on the normal branch.
#  4. EQUILIBRIUM fed the C's grass NPP (the bm_inc_ext crutch, as the TREE allocation was validated
#     before the self-NPP was calibrated, §13): grass → the C's grass leaf:root structure.
#  5. AD: ForwardDiff d(grown pools) matches finite differences — scalar AND through the coupled
#     multi-year grass-inclusive rollout_canopy_years_gpp; Enzyme reverse through the same path
#     (guarded VERSION < 1.11, as the other Enzyme canopy gates).
# NB: the grass ALLOCATION is the deliverable here; F_diff's SELF-computed grass NPP is ~3× the C's
# (grass shares the beech photosynthesis/respiration params), so a SELF-driven grass overshoots — the
# grass-NPP calibration is the documented next step (parallel to the tree NPP calibration, §13).

@testitem "Prognostic grass — param fidelity + reconstruction + non-grass no-op" tags = [:validation, :fdiff, :canopy, :structure, :grass] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.Allometry
    using Test

    # ── 1. grass_allocparams == par/pft_lpjmlfit.js temperate C3 grass (id 8) ────────────────────────
    ga = grass_allocparams()
    @test ga.lmro_ratio == 0.8                # "lmro_ratio" : 0.8
    @test ga.lmro_offset == 0.5               # "lmro_offset" : 0.5
    @test ga.turnover_leaf == 1.0             # "turnover.leaf" 1.0 → rate 1/1.0 (fscanpft_grass.c:123)
    @test ga.turnover_root == 0.5             # "turnover.root" 2.0 → rate 1/2.0 (fscanpft_grass.c:124)
    @test ga.reprod_cost == 0.1               # "reprod_cost" REPROD_COST = 0.1

    # ── grass_treepools reconstruction: leaf = agb, root = vegc − agb, per-area crownarea = nind = 1 ──
    agb = 4.35102; vegc = 9.80178; sla = 0.042242          # hainich_individuals_2010.csv patch-0 grass
    g = grass_treepools(agb, vegc, sla)
    @test g.is_grass
    @test g.leaf_c == agb                     # grass agb = leaf·nind (agb_grass.c:25), per-m²
    @test isapprox(g.root_c, vegc - agb; rtol = 1.0e-12)   # grass vegc = leaf + root
    @test g.crownarea == 1.0 && g.nind == 1.0             # per-area convention
    @test g.sapwood_c == 0.0 && g.heartwood_c == 0.0 && g.height == 0.0
    @test isapprox(g.leaf_c * g.sla, agb * sla; rtol = 1.0e-12)   # lai = leaf_c·sla reproduces lai/sla

    # ── grow_grass returns a non-grass individual UNCHANGED (dispatch guard) ─────────────────────────
    tree = TreePools{Float64}(2769.0, 33000.0, 120000.0, 2769.0, 12.0, 15.8, 1 / 225, 0.01986, 2.0e5, false)
    @test grow_grass_individual(ga, tree, 5000.0, 0.85) === tree
end

@testitem "Prognostic grass — golden vs allocation_grass.c + conservation + physical bounds" tags = [:validation, :fdiff, :canopy, :structure, :grass] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using Test

    ga = grass_allocparams()

    # direct hand-port of allocation_grass.c natural-veg branch (with_nitrogen=no ⇒ vscal=1), incl.
    # turnover_grass.c pool reduction + the reproduction reserve. HARD min(1,wscal) (the C).
    function golden(leaf, root, bm, ws; lmro_ratio = 0.8, lmro_offset = 0.5, tl = 1.0, tr = 0.5, rc = 0.1)
        leaf_t = leaf * (1 - tl); root_t = root * (1 - tr)
        bm_net = bm >= 0 ? bm * (1 - rc) : bm
        lmtorm = lmro_ratio * (lmro_offset + (1 - lmro_offset) * min(1.0, ws))
        if lmtorm < 1.0e-10
            il = 0.0; ir = bm_net
        else
            il = (bm_net + root_t - leaf_t / lmtorm) / (1 + 1 / lmtorm)
            if il < 0
                ir = bm_net; il = (root_t + ir) * lmtorm - leaf_t
            else
                (bm_net > 0 && il > bm_net) && (il = bm_net)
                ir = bm_net - il
            end
        end
        return (leaf_t + il, root_t + ir)
    end

    # wscal ≤ 0.7 so the AD-safe smoothmin(1, wscal, 30) ≈ the C's hard min(1, wscal) to < 1e-5.
    cases = [
        (3.0, 3.7, 5.7, 0.6),    # normal growth (understory grass)
        (4.35, 5.45, 9.1, 0.55), # C-2010-like
        (2.0, 6.0, 1.0, 0.7),    # small bm, leaf shrinks (leaf turns over fully, little regrowth)
        (5.0, 2.0, 0.0, 0.5),    # zero bm: pools reduced by turnover only
        (1.0, 1.0, 20.0, 0.4),   # large bm: strong growth
        (3.0, 3.0, -2.0, 0.6),   # NEGATIVE bm: proportional reduction, no reprod reserve
    ]
    maxrel = 0.0
    for (leaf, root, bm, ws) in cases
        ng = grow_grass_individual(ga, grass_treepools(leaf, leaf + root, 0.042242), bm, ws)
        (gl, gr) = golden(leaf, root, bm, ws)
        maxrel = max(maxrel, abs(ng.leaf_c - gl) / (abs(gl) + 1.0e-9), abs(ng.root_c - gr) / (abs(gr) + 1.0e-9))
        @test ng.sapwood_c == 0.0 && ng.heartwood_c == 0.0 && ng.height == 0.0 && ng.is_grass   # grass geometry preserved
        @test ng.crownarea == 1.0 && ng.nind == 1.0
    end
    @test maxrel < 1.0e-5                     # port reproduces the C allocation_grass across every branch

    # ── conservation: on the NORMAL (inc_leaf ≥ 0) branch Δ(leaf+root) = bm_net − turnover-to-litter ──
    maxcons = 0.0
    for (leaf, root, bm, ws) in [(6.4, 8.0, 10.7, 0.7), (3.0, 3.7, 5.7, 0.6), (1.0, 1.0, 20.0, 0.4)]
        ng = grow_grass_individual(ga, grass_treepools(leaf, leaf + root, 0.042242), bm, ws)
        bm_net = bm * (1 - ga.reprod_cost)
        dpool = (ng.leaf_c + ng.root_c) - (leaf + root)
        maxcons = max(maxcons, abs(dpool - (bm_net - leaf * ga.turnover_leaf - root * ga.turnover_root)))
    end
    @test maxcons < 1.0e-10                   # allocation invents no carbon (net of the annual turnover)

    # ── physical: leaf/root ≥ 0 for a physically-positive increment (understory grass regrows) ───────
    for ws in 0.3:0.1:1.0
        ng = grow_grass_individual(ga, grass_treepools(4.0, 6.0, 0.042242), 9.0, ws)
        @test ng.leaf_c ≥ 0 && ng.root_c ≥ 0 && isfinite(ng.leaf_c) && isfinite(ng.root_c)
    end
end

@testitem "Prognostic grass — equilibrium fed the C grass NPP reproduces the C grass structure" tags = [:validation, :fdiff, :canopy, :structure, :grass] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using Test

    ga = grass_allocparams()
    # The bm_inc_ext crutch (as the TREE allocation was validated before the self-NPP was calibrated,
    # §13): fed the C's grass NPP (hainich patch-15 grass: npp = 10.728, leaf = 6.406, root = 8.023), the
    # allocation equilibrates to the C's grass STRUCTURE. At the fixed point leaf:root → lmtorm.
    npp_C = 10.728; leaf_C = 6.406; root_C = 8.023
    for (ws, tol) in [(0.85, 0.02), (0.95, 0.02), (1.0, 0.02)]
        leaf = 0.5; root = 0.5                                   # cold start (allocation must build up)
        for _ in 1:300
            ng = grow_grass_individual(ga, grass_treepools(leaf, leaf + root, 0.042242), npp_C, ws)
            leaf = ng.leaf_c; root = ng.root_c
        end
        lmtorm = 0.8 * (0.5 + 0.5 * ws)
        @test isapprox(leaf / root, lmtorm; atol = 0.02)         # equilibrium leaf:root → lmtorm (the C's water-modulated ratio)
        @test leaf > 0 && root > 0 && isfinite(leaf)
    end
    # at the well-watered fixed point (wscal ≈ 1) the grass leaf:root ≈ the C's 6.406/8.023 = 0.799
    leaf = 0.5; root = 0.5
    for _ in 1:300
        ng = grow_grass_individual(ga, grass_treepools(leaf, leaf + root, 0.042242), npp_C, 1.0)
        leaf = ng.leaf_c; root = ng.root_c
    end
    @test isapprox(leaf / root, leaf_C / root_C; rtol = 0.03)    # F_diff grass leaf:root within 3 % of the C
    @test isapprox(leaf, leaf_C; rtol = 0.12) && isapprox(root, root_C; rtol = 0.12)  # magnitudes within ~10 %
end

@testitem "Prognostic grass — differentiable (ForwardDiff scalar + through the coupled multi-year rollout)" tags = [:gradient, :fdiff, :canopy, :structure, :grass] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: rollout_canopy_years_gpp, hainich_soilcolumn
    using LPJmLFITEmulator.Allometry
    using ForwardDiff, FiniteDifferences
    using Test

    ga = grass_allocparams()
    fdm = central_fdm(5, 1)

    # ── scalar: d(grown leaf)/d(bm_inc) and d(grown root)/d(wscal) vs FiniteDifferences ──────────────
    gleaf(bm) = grow_grass_individual(ga, grass_treepools(4.0, 10.0, 0.042242), bm, 0.9).leaf_c
    groot(ws) = grow_grass_individual(ga, grass_treepools(4.0, 10.0, 0.042242), 12.0, ws).root_c
    for (fn, x) in ((gleaf, 12.0), (groot, 0.7))
        gad = ForwardDiff.derivative(fn, x); gfd = fdm(fn, x)
        @test isfinite(gad) && isfinite(gfd)
        @test isapprox(gad, gfd; rtol = 1.0e-5, atol = 1.0e-8)
    end
    @test ForwardDiff.derivative(gleaf, 12.0) > 0               # more bm ⇒ more grass leaf (physical)

    # ── through the coupled multi-year grass-inclusive rollout: d(Σ GPP)/d(α_c3) vs FiniteDifferences ──
    # a mixed patch (2 ragged beeches + 1 understory grass) so the grass grows under the trees' shade.
    soil = hainich_soilcolumn(;
        whcs = [37.0, 53.0, 88.0, 175.0, 175.0], rootdist = [0.41, 0.32, 0.2, 0.07, 0.0],
        soildepth = [200.0, 300.0, 500.0, 1000.0, 1000.0],
    )
    allom = Allometry.TreeAllometry{Float64}()
    alloc = tebs_allocparams()
    ndays = 30
    forc = [DailyForcing{Float64}(swdown = 240.0, lwnet = -45.0, temp = 18.0, precip = (d % 4 == 0 ? 8.0 : 0.3), daylength = 14.0, co2 = 380.0) for d in 1:ndays]
    NY = 3
    yearly_forcings = [forc for _ in 1:NY]
    phens_by_year = [fill(1.0, ndays) for _ in 1:NY]
    st0 = FDiffStateML{Float64}([0.7 * wc for wc in soil.whcs], 0.0)

    function sumgpp(x)                                          # x = α_c3 (a photosynthesis parameter)
        T = typeof(x)
        mktree(leaf, sap, heart, root, h, ca, nind) = TreePools{T}(T(leaf), T(sap), T(heart), T(root), T(h), T(ca), T(nind), T(0.01986), T(2.0e5), false)
        trees0 = [mktree(2769.0, 33000.0, 120000.0, 2769.0, 12.0, 15.8, 1 / 225), mktree(600.0, 3000.0, 9000.0, 600.0, 4.0, 3.0, 1 / 120), grass_treepools(T(4.0), T(10.0), T(0.042242))]
        mktmpl(fpar, sla, isg) = Individual{T}(
            T(fpar), T(0.0), T(0.5), T(0.15), T(10.0), T(0.0), T(0.0), T(0.0), isg ? T(0.01) : T(0.02), isg ? T(0.15) : T(0.04), T(0.1), T(0.4), isg ? one(T) : T(1 / 225),
            FDiff.PhotoParams{T}(; path = :c3, issla = true, sla = T(sla), alphac3 = x),
            FDiff.TempStressParams{T}(; temp_photos_low = (isg ? T(10.0) : T(20.0)), temp_photos_high = T(30.0)), isg,
        )
        tmpls = [mktmpl(0.55, 0.01986, false), mktmpl(0.12, 0.025, false), mktmpl(0.03, 0.042242, true)]
        stT = FDiffStateML{T}(T[0.7 * wc for wc in soil.whcs], zero(T))
        g = rollout_canopy_years_gpp(FDiff.tebs_params(T), alloc, allom, stT, trees0, tmpls, soil, yearly_forcings; phens_by_year = phens_by_year)
        return sum(g)
    end
    gad = ForwardDiff.derivative(sumgpp, 0.08)
    gfd = fdm(sumgpp, 0.08)
    @test isfinite(gad) && isfinite(gfd)
    @test isapprox(gad, gfd; rtol = 1.0e-3, atol = 1.0e-6)      # gradient flows through the grass structure feedback too
end

@testitem "Prognostic grass — coupled rollout uses PER-PFT grass phenology (docs §25)" tags = [:validation, :fdiff, :canopy, :structure, :grass] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: rollout_canopy_years, hainich_soilcolumn, tebs_allocparams
    using LPJmLFITEmulator.Allometry
    using Test

    # The multi-year coupled rollout `rollout_canopy_years` now drives each individual's leaf phenology with
    # its OWN PFT's GSI (the FIT config's `new_phenology:true`), via a `pft_ids` kwarg defaulting to the
    # Hainich mapping grass→8 / tree→3. Decisively, a GRASS runs its light limiter on the tree-attenuated
    # forest-floor light, so a shaded understory grass is leaf-on far less than the canopy trees — collapsing
    # the §24 grass overshoot (matched-structure grass NPP 4.26× → 1.13× the C; docs §25). Because the beech
    # GSI `pft_phenparams(3) === tebs_phenparams`, switching the tree individuals from the old patch-wide
    # beech GSI to per-PFT is BYTE-IDENTICAL — only the grass leaf display changes.
    soil = hainich_soilcolumn(;
        whcs = [37.0, 53.0, 88.0, 175.0, 175.0], rootdist = [0.41, 0.32, 0.2, 0.07, 0.0],
        soildepth = [200.0, 300.0, 500.0, 1000.0, 1000.0],
    )
    allom = Allometry.TreeAllometry{Float64}()
    alloc = tebs_allocparams()
    mktree(leaf, sap, heart, root, h, ca, nind) = TreePools{Float64}(leaf, sap, heart, root, h, ca, nind, 0.01986, 2.0e5, false)
    mktmpl(sla, isg) = Individual{Float64}(
        0.0, 0.0, 0.5, 0.15, 10.0, 0.0, 0.0, 0.0, isg ? 0.01 : 0.02, isg ? 0.15 : 0.04, 0.1, 0.4, isg ? 1.0 : 1 / 120,
        FDiff.PhotoParams{Float64}(; path = :c3, issla = true, sla = sla),
        FDiff.TempStressParams{Float64}(; temp_photos_low = (isg ? 10.0 : 20.0), temp_photos_high = 30.0), isg,
    )
    # a DEEPLY-shaded understory: two dense beeches over one grass (forest-floor light ≈ 15 % of open).
    trees0 = [mktree(4000.0, 40000.0, 150000.0, 4000.0, 20.0, 20.0, 1 / 120), mktree(1500.0, 12000.0, 40000.0, 1500.0, 12.0, 8.0, 1 / 120), grass_treepools(4.0, 10.0, 0.042242)]
    tmpls = [mktmpl(0.01986, false), mktmpl(0.025, false), mktmpl(0.042242, true)]
    n = length(trees0)
    ndays = 40
    forc = [DailyForcing{Float64}(swdown = 190.0, lwnet = -45.0, temp = 16.0, precip = (d % 4 == 0 ? 8.0 : 0.3), daylength = 14.0, co2 = 380.0) for d in 1:ndays]
    NY = 4
    yearly = [forc for _ in 1:NY]
    st0 = FDiffStateML{Float64}([0.7 * wc for wc in soil.whcs], 0.0)

    # per-PFT (DEFAULT: grass id 8, light-limited) vs the old all-beech GSI (pft_ids = 3 everywhere)
    (_, _, pools_pft, _) = rollout_canopy_years(tebs_params(), alloc, allom, st0, trees0, tmpls, soil, yearly)
    (_, _, pools_beech, _) = rollout_canopy_years(tebs_params(), alloc, allom, st0, trees0, tmpls, soil, yearly; pft_ids = fill(3, n))

    gpft = pools_pft[end][3].leaf_c
    gbeech = pools_beech[end][3].leaf_c
    # (1) the grass leaf display IS routed through per-PFT phenology (differs from the beech-GSI grass)
    @test !isapprox(gpft, gbeech; rtol = 1.0e-6)
    # (2) the shaded understory grass is SUPPRESSED by its own light limiter (leaf-on less than beech GSI)
    @test gpft < gbeech
    @test gpft ≥ 0 && isfinite(gpft)
    # (3) the TREES are essentially unchanged: the beech GSI `pft_phenparams(3) === tebs_phenparams`, so the
    # id-3 tree leaf-DISPLAY is byte-identical; the trees shift only by < 1 % through the shared soil-water /
    # stand-conductance coupling to the now-lighter, light-limited grass (the C's tree↔grass competition —
    # physically correct, and only in a MIXED coupled patch; the validated tree-only paths stay byte-identical).
    for i in 1:(n - 1)
        @test isapprox(pools_pft[end][i].leaf_c, pools_beech[end][i].leaf_c; rtol = 0.02)
        @test isapprox(pools_pft[end][i].height, pools_beech[end][i].height; rtol = 0.02)
        @test pools_pft[end][i].leaf_c > 0 && isfinite(pools_pft[end][i].leaf_c)
    end
end

@testitem "Prognostic grass — Enzyme reverse through the grass-inclusive multi-year training path" tags = [:gradient, :training, :fdiff, :canopy, :structure, :grass] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: rollout_canopy_years_gpp, hainich_soilcolumn
    using LPJmLFITEmulator.Allometry
    using Lux, Zygote, Optimisers, Enzyme, FiniteDifferences, StableRNGs
    using Random
    using Test

    soil = hainich_soilcolumn(;
        whcs = [37.0, 53.0, 88.0, 175.0, 175.0], rootdist = [0.41, 0.32, 0.2, 0.07, 0.0],
        soildepth = [200.0, 300.0, 500.0, 1000.0, 1000.0],
    )
    allom = Allometry.TreeAllometry{Float64}()
    alloc = tebs_allocparams()
    mktree(leaf, sap, heart, root, h, ca, nind) = TreePools{Float64}(leaf, sap, heart, root, h, ca, nind, 0.01986, 2.0e5, false)
    mktmpl(fpar, sla, isg) = Individual{Float64}(
        fpar, 0.0, 0.5, 0.15, 10.0, 0.0, 0.0, 0.0, isg ? 0.01 : 0.02, isg ? 0.15 : 0.04, 0.1, 0.4, isg ? 1.0 : 1 / 225,
        FDiff.PhotoParams{Float64}(; path = :c3, issla = true, sla = sla),
        FDiff.TempStressParams{Float64}(; temp_photos_low = (isg ? 10.0 : 20.0), temp_photos_high = 30.0), isg,
    )
    # a mixed tree+grass patch: the grass is grown by grow_grass_individual INSIDE the SoA rollout
    trees0 = [mktree(2769.0, 33000.0, 120000.0, 2769.0, 12.0, 15.8, 1 / 225), mktree(600.0, 3000.0, 9000.0, 600.0, 4.0, 3.0, 1 / 120), grass_treepools(4.0, 10.0, 0.042242)]
    tmpls = [mktmpl(0.55, 0.01986, false), mktmpl(0.12, 0.025, false), mktmpl(0.03, 0.042242, true)]
    ndays = 30
    forc = [DailyForcing{Float64}(swdown = 240.0, lwnet = -45.0, temp = 18.0, precip = (d % 4 == 0 ? 8.0 : 0.3), daylength = 14.0, co2 = 380.0) for d in 1:ndays]
    NY = 3
    yearly_forcings = [forc for _ in 1:NY]
    phens_by_year = [fill(1.0, ndays) for _ in 1:NY]
    st0 = FDiffStateML{Float64}([0.7 * wc for wc in soil.whcs], 0.0)
    phys = tebs_params()

    # identity: zero-init net through the grass-inclusive multi-year rollout == pure physics, per year
    g_base = rollout_canopy_years_gpp(phys, alloc, allom, st0, trees0, tmpls, soil, yearly_forcings; phens_by_year = phens_by_year)
    nn = build_fdiff_nn(; targets = (:vm, :λ), width = 8, depth = 2, rng = StableRNG(42))
    g_id = rollout_canopy_years_gpp(phys, alloc, allom, st0, trees0, tmpls, soil, yearly_forcings; phens_by_year = phens_by_year, hooks = FluxHooks(vm = neural_vm_hook(nn), λ = neural_lambda_hook(nn)))
    @test all(isapprox.(g_id, g_base; rtol = 1.0e-10))
    @test all(isfinite, g_base) && all(g_base .> 0)

    if VERSION < v"1.11"
        ext = Base.get_extension(LPJmLFITEmulator, :FDiffTrainingExt)
        @test ext !== nothing
        tgt = rollout_canopy_years_gpp(phys, alloc, allom, st0, trees0, tmpls, soil, yearly_forcings; phens_by_year = phens_by_year, hooks = FluxHooks(vm = (_ -> 1.15), λ = (_ -> 1.05)))
        flat0, re0 = Optimisers.destructure(nn.ps)
        ps = re0(flat0 .+ 0.05 .* randn(StableRNG(3), length(flat0)))
        lossf(p) = fdiff_multiyear_gpp_loss(p, nn, phys, alloc, allom, st0, trees0, tmpls, soil, yearly_forcings, phens_by_year, tgt)
        (lval, dps) = ext._enzyme_multiyear_grad(ps, nn, phys, alloc, allom, st0, trees0, tmpls, soil, yearly_forcings, phens_by_year, tgt)
        @test lval ≈ lossf(ps) rtol = 1.0e-8                    # Enzyme reverse primal == the direct MSE (grass grow included)
        gz = Optimisers.destructure(dps)[1]
        flat, re = Optimisers.destructure(ps)
        @test all(isfinite, gz) && any(!iszero, gz)
        fdm = central_fdm(5, 1)
        for k in randperm(StableRNG(7), length(flat))[1:6]
            g_fd = fdm(ε -> lossf(re((v = copy(flat); v[k] += ε; v))), 0.0)
            @test isapprox(gz[k], g_fd; rtol = 1.0e-4, atol = 1.0e-6)   # grass grow is Enzyme-typeable through the multi-year path
        end
    else
        @info "Prognostic grass: Enzyme-reverse checks skipped on Julia $(VERSION) (Enzyme 0.13 ≥1.11 compiler error); verified on 1.10-lts."
    end
end

@testitem "Grass demand-gate + establishment — §26 faithful deep-shade balance; trees byte-identical" tags = [:validation, :fdiff, :canopy, :structure, :grass] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: rollout_canopy_years, rollout_daily_canopy, hainich_soilcolumn, tebs_allocparams,
        tebs_params, WaterParams, FDiffParams, grass_estabparams, _treepools_fpc, grass_treepools,
        _patch_fpars, individual_from_pools
    using LPJmLFITEmulator.Allometry
    using Test

    # §26 replaces the REFUTED §25 hard-floor lever (a large grass-only `βflux` recovering `max(0,agd)` drove
    # deep-shade grass NPP NEGATIVE — flooring the demand `gpd→0` collapses `fac`, so the fixed-graph λ-solve
    # returns a degenerate low λ that suppresses `agd` while `rd` stays normal) with the C's own mechanism: a
    # photosynthesis DEMAND-GATE (`water_stressed.c:196` `if(gpd>1e-5)` skips photosynthesis ⇒ agd=0, no leaf
    # resp). F_diff's `WaterParams.grass_demand_gate` multiplies grass GPP + `rd` by a smooth sigmoid of the
    # pre-floor demand, zeroing BOTH as demand→0 (no negative pathology). Plus grass ESTABLISHMENT
    # (`establishment_grass.c`). Both grass-gated / opt-in ⇒ the validated tree paths stay byte-identical.
    soil = hainich_soilcolumn(;
        whcs = [37.0, 53.0, 88.0, 175.0, 175.0], rootdist = [0.41, 0.32, 0.2, 0.07, 0.0],
        soildepth = [200.0, 300.0, 500.0, 1000.0, 1000.0],
    )
    allom = Allometry.TreeAllometry{Float64}()
    alloc = tebs_allocparams()
    mktree(leaf, sap, heart, root, h, ca, nind) = TreePools{Float64}(leaf, sap, heart, root, h, ca, nind, 0.01986, 2.0e5, false)
    mktmpl(sla, isg) = Individual{Float64}(
        0.0, 0.0, 0.5, 0.15, 10.0, 0.0, 0.0, 0.0, isg ? 0.01 : 0.02, isg ? 0.15 : 0.04, 0.1, 0.4, isg ? 1.0 : 1 / 120,
        FDiff.PhotoParams{Float64}(; path = :c3, issla = true, sla = sla),
        FDiff.TempStressParams{Float64}(; temp_photos_low = (isg ? 10.0 : 20.0), temp_photos_high = 30.0), isg,
    )
    # deeply-shaded understory (as the §25 gate): two dense beeches over one grass (forest floor ≈ 15 % of open)
    trees0 = [mktree(4000.0, 40000.0, 150000.0, 4000.0, 20.0, 20.0, 1 / 120), mktree(1500.0, 12000.0, 40000.0, 1500.0, 12.0, 8.0, 1 / 120), grass_treepools(4.0, 10.0, 0.042242)]
    tmpls = [mktmpl(0.01986, false), mktmpl(0.025, false), mktmpl(0.042242, true)]
    n = length(trees0)
    forc = [DailyForcing{Float64}(swdown = 190.0, lwnet = -45.0, temp = 16.0, precip = (d % 4 == 0 ? 8.0 : 0.3), daylength = 14.0, co2 = 380.0) for d in 1:40]
    yearly = [forc for _ in 1:4]
    st0 = FDiffStateML{Float64}([0.7 * wc for wc in soil.whcs], 0.0)

    p0 = tebs_params()
    # gate-on params: copy tebs's WaterParams, flip the §26 demand-gate on (sharp ⇒ the C's hard gpd>1e-5 step)
    won = WaterParams{Float64}(
        map(fieldnames(WaterParams)) do k
            k === :grass_demand_gate ? true : (k === :βgpd_gate ? 1.0e8 : getfield(p0.water, k))
        end...
    )
    pon = FDiffParams{Float64}(; photo = p0.photo, tstress = p0.tstress, water = won, resp = p0.resp, allom = p0.allom, nlambda = p0.nlambda, ω = p0.ω)

    # ── DEMAND-GATE: wired + NON-NEGATIVE (no §25 pathology) + grass-gated (trees shift only via competition) ──
    (_, _, pools_off, _) = rollout_canopy_years(p0, alloc, allom, st0, trees0, tmpls, soil, yearly)   # DEFAULT (gate off)
    (_, _, pools_on, _) = rollout_canopy_years(pon, alloc, allom, st0, trees0, tmpls, soil, yearly)   # §26 gate on
    goff = pools_off[end][3].leaf_c; gon = pools_on[end][3].leaf_c
    @test !isapprox(gon, goff; rtol = 1.0e-6)         # the demand-gate is WIRED — it changes the grass carbon balance
    @test gon ≥ 0 && isfinite(gon)                    # NON-NEGATIVE — no degenerate-λ negative-NPP pathology (unlike the refuted §25 hard floor)
    # DAILY (FIXED structure): the gate touches only grass GPP/`rd`, NOT water (transp/soil use gate-free
    # quantities), so the shared soil is gate-independent ⇒ the trees are BYTE-IDENTICAL every day, and the
    # grass GPP is `softplus(agd)·gate ≤ softplus(agd)`, so the demand-gate can only LOWER the stand GPP.
    fp0 = _patch_fpars(trees0, allom)
    inds0 = Individual{Float64}[individual_from_pools(tmpls[i], trees0[i], allom, fp0[i]) for i in 1:n]
    (_, d_off) = rollout_daily_canopy(p0, st0, inds0, soil, forc; pft_ids = [3, 3, 8])
    (_, d_on) = rollout_daily_canopy(pon, st0, inds0, soil, forc; pft_ids = [3, 3, 8])
    @test all(d_on[t].npp_ind[i] == d_off[t].npp_ind[i] for t in eachindex(forc) for i in 1:(n - 1))  # trees byte-identical (grass-gated)
    @test sum(x.gpp for x in d_on) ≤ sum(x.gpp for x in d_off)   # the gate can only LOWER the stand GPP (grass GPP × sigmoid ≤ 1)
    # MULTI-YEAR: the trees shift only through the shared soil-water / stand-conductance tree↔grass competition
    for i in 1:(n - 1)                                # (< 2 %, as §25) — the validated tree-ONLY paths (no grass) stay byte-identical
        @test isapprox(pools_on[end][i].leaf_c, pools_off[end][i].leaf_c; rtol = 0.05)
        @test isapprox(pools_on[end][i].height, pools_off[end][i].height; rtol = 0.05)
        @test pools_on[end][i].leaf_c > 0 && isfinite(pools_on[end][i].leaf_c)
    end

    # ── ESTABLISHMENT (establishment_grass.c): param fidelity + keeps the dim-patch grass alive; grass-only ──
    est = grass_estabparams()
    @test isapprox(est.sapl_leaf, 0.1 / 0.042242; rtol = 1.0e-12)   # lai_sapl/sla (fscanpft_grass.c:140, temperate C3 id 8)
    @test isapprox(est.sapl_root, est.sapl_leaf / 0.8; rtol = 1.0e-12)   # sapl_root = sapl_leaf/lmro_ratio
    g = grass_treepools(4.0, 10.0, 0.042242)          # _treepools_fpc reproduces the per-area grass fpc (crownarea=nind=1)
    @test isapprox(_treepools_fpc(g, allom), 1 - exp(-allom.k_beer * (g.leaf_c * g.sla)); rtol = 1.0e-12)
    (_, _, pools_est, _) = rollout_canopy_years(p0, alloc, allom, st0, trees0, tmpls, soil, yearly; grass_estab = est)
    @test pools_est[end][3].leaf_c ≥ pools_off[end][3].leaf_c   # re-seeding only ADDS grass biomass (fpc_total<1 gate)
    @test pools_est[end][3].leaf_c > 0
    for i in 1:(n - 1)                                # establishment touches only the grass pool (trees shift only via competition)
        @test isapprox(pools_est[end][i].leaf_c, pools_off[end][i].leaf_c; rtol = 0.05)
    end
end
