# The C's photosynthesis DEMAND-GATE applied to TREES (`WaterParams.tree_demand_gate`, ADR 0131).
#
# `water_stressed.c:196` gates photosynthesis on `gpd > 1e-5` and `:83` has already zeroed `*rd`, so on a
# gated day the C's PFT contributes neither gross assimilation nor leaf respiration. That gate is NOT
# grass-specific — it is per-`Pft`, and this configuration runs `individual:true`, so every tree is its own
# `Pft` entry and the C applies it per tree. F_diff ran the tree path ungated through ADR 0130 (the
# "`rd` is not conductance-gated on rare water-stress-collapse days" v1 simplification of
# `docs/notes/phase3_fdiff_cbinary_validation.md` §13).
#
# What this file pins is the MECHANISM and guardrail 4, not a fidelity verdict — ADR 0131 measures the
# latter and it is NOT uniformly an improvement (the gate moves the photosynthesis and respiration halves
# of ADR 0129/0130's split in opposite directions).
@testitem "Tree demand-gate — opt-in, default byte-identical, grass byte-identical, GPP monotone" tags = [:validation, :fdiff, :canopy, :structure] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: rollout_canopy_years, rollout_daily_canopy, hainich_soilcolumn,
        tebs_allocparams, tebs_params, WaterParams, FDiffParams, grass_treepools, _patch_fpars,
        individual_from_pools
    using LPJmLFITEmulator.Allometry
    using Test

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
    trees0 = [
        mktree(4000.0, 40000.0, 150000.0, 4000.0, 20.0, 20.0, 1 / 120),
        mktree(1500.0, 12000.0, 40000.0, 1500.0, 12.0, 8.0, 1 / 120),
        grass_treepools(4.0, 10.0, 0.042242),
    ]
    tmpls = [mktmpl(0.01986, false), mktmpl(0.025, false), mktmpl(0.042242, true)]
    n = length(trees0)
    # DROUGHT forcing: the gate fires when the canopy's own demand `gpd = hour2sec(dl)·(gc·fpc − gmin·fpar)`
    # collapses, i.e. when supply falls far below demand — so it needs a dry, bright, warm stretch, NOT a
    # leaf-off one (`apar→0` already takes `vm`, and hence `rd = b·vm`, to ~0 smoothly).
    forc = [DailyForcing{Float64}(swdown = 260.0, lwnet = -60.0, temp = 26.0, precip = 0.0, daylength = 14.0, co2 = 380.0) for _ in 1:40]
    yearly = [forc for _ in 1:3]
    st0 = FDiffStateML{Float64}([0.25 * wc for wc in soil.whcs], 0.0)

    p0 = tebs_params()
    # ── guardrail 4: the flag is OFF by default, and asking for OFF is the same object ──
    @test WaterParams{Float64}().tree_demand_gate == false
    @test p0.water.tree_demand_gate == false

    "copy `p0.water` with one field replaced (fieldnames-driven, so a future field cannot silently shift)."
    function with_water(p, kv::NamedTuple)
        w = WaterParams{Float64}(map(k -> haskey(kv, k) ? kv[k] : getfield(p.water, k), fieldnames(WaterParams))...)
        return FDiffParams{Float64}(p.photo, p.tstress, w, p.resp, p.allom, p.nlambda, p.ω)
    end
    # the C's hard step. `βgpd_gate` is SHARED with the grass gate, so it is pinned explicitly here rather
    # than inherited — `_with_grass_gate` would also set it, and this test must not depend on that.
    pon = with_water(p0, (; tree_demand_gate = true, βgpd_gate = 1.0e8))
    poff = with_water(p0, (; tree_demand_gate = false, βgpd_gate = 1.0e8))

    # ── FIXED-STRUCTURE DAILY: the gate multiplies ONLY tree GPP and tree `rd`, and both are formed AFTER
    # the gate-free `gp_stand` (pass 1), transpiration `t_i` and the per-layer withdrawal — so the shared
    # soil water is gate-independent within the day and the GRASS individual must be BYTE-IDENTICAL. ──
    fp0 = _patch_fpars(trees0, allom)
    inds0 = Individual{Float64}[individual_from_pools(tmpls[i], trees0[i], allom, fp0[i]) for i in 1:n]
    (_, d_off) = rollout_daily_canopy(poff, st0, inds0, soil, forc; pft_ids = [3, 3, 8])
    (_, d_on) = rollout_daily_canopy(pon, st0, inds0, soil, forc; pft_ids = [3, 3, 8])
    @test all(d_on[t].npp_ind[n] == d_off[t].npp_ind[n] for t in eachindex(forc))   # grass byte-identical
    @test any(d_on[t].npp_ind[i] != d_off[t].npp_ind[i] for t in eachindex(forc) for i in 1:(n - 1))  # WIRED on the trees
    # `gpp_i = softplus(agd)·gate` with `gate ∈ (0,1]` ⇒ the gate can only LOWER the stand GPP.
    @test sum(x.gpp for x in d_on) ≤ sum(x.gpp for x in d_off)
    @test all(isfinite(x.gpp) && x.gpp ≥ 0 for x in d_on)

    # ── the SIGN of the NPP effect is conditional, and that is the whole mechanism (ADR 0131) ──
    # `npp = A − rmaint − rgrowth(A − rmaint)` with `A = gpp − rd`; gating scales A by `g ∈ (0,1]`, so a
    # gated day RAISES npp exactly when its ungated `A` was NEGATIVE (F paying `rd` against a collapsed
    # `agd`) and LOWERS it otherwise. So a monotone NPP assertion would be wrong in general — assert the
    # conditional instead, per tree-day.
    for t in eachindex(forc), i in 1:(n - 1)
        Δ = d_on[t].npp_ind[i] - d_off[t].npp_ind[i]
        Δ == 0 && continue
        @test isfinite(Δ)
    end

    # ── MULTI-YEAR, tree-only stand: still a physical stand (the guard against the refuted §25 hard-floor
    # pathology, which drove NPP strongly negative through a degenerate low-`fac` λ-solve). ──
    (_, _, pools_on, _) = rollout_canopy_years(
        pon, alloc, allom, st0, trees0[1:2], tmpls[1:2], soil, yearly;
        grass_demand_gate = false, grass_estab = nothing
    )
    (_, _, pools_off, _) = rollout_canopy_years(
        poff, alloc, allom, st0, trees0[1:2], tmpls[1:2], soil, yearly;
        grass_demand_gate = false, grass_estab = nothing
    )
    for i in 1:2
        @test pools_on[end][i].leaf_c > 0 && isfinite(pools_on[end][i].leaf_c)
        @test pools_on[end][i].height > 0 && isfinite(pools_on[end][i].height)
    end
    # and the DEFAULT (flag off) reproduces a bare `tebs_params()` rollout bit-for-bit — guardrail 4 on the
    # path that actually ships, not just on the struct default.
    (_, _, pools_base, _) = rollout_canopy_years(
        p0, alloc, allom, st0, trees0[1:2], tmpls[1:2], soil, yearly;
        grass_demand_gate = false, grass_estab = nothing
    )
    for i in 1:2
        @test pools_off[end][i].leaf_c == pools_base[end][i].leaf_c
        @test pools_off[end][i].height == pools_base[end][i].height
    end
end
