# Component-S Phase 3A Stage 1 (ADR 0047) — the PORTED LPJmL-FIT per-individual mortality hazard.
#
# `src/trait_mortality.jl` has NO call site, so nothing in the coupled loop, the DRF pipeline or the AD
# trainer can catch a wrong constant. These tests are the entire correctness gate. They check three
# different kinds of thing, and the first is the one that actually protects the port:
#
#   1. PARAMETER PROVENANCE — every field of every `PFTMortParams` row is compared against
#      `references/S_pft_mortality_params.csv`, which `scripts/build_mort_params_reference.py` generates by
#      running the SAME `cpp -P` over `$LPJROOT/par/pft_lpjmlfit.js` that LPJmL itself pipes the file
#      through. ADR 0031 is the record of what two independent copies of a physical constant cost (a stale
#      `TREE_TYPES` hid 32.5 % of survivor tree stems for months), so the Julia literals and
#      `build_slow_flux_table.py::PFT_PARAMS` both gate against that one file and nothing holds a third
#      copy. A red test here means the C changed or a literal was mistyped — regenerate and re-read, never
#      widen the tolerance.
#   2. EQUATION SHAPE — closed-form spot values of each hazard against the C expressions, plus the
#      properties the C guarantees: additivity then a single cap, per-component caps BEFORE the sum, the
#      two hard kills, the `leafarea ≤ 1e-6 ⇒ certain death` branch, the `(1+bm_inc_counter)` multiplier on
#      `mort_npp` AND `mort_water` but NOT `mort_temp`.
#   3. THE NON-SIGN-DEFINITE SELECTION (ADR 0046 §3) — the scientific claim the whole port rests on:
#      denser wood LOWERS `mort_max` but, at fixed carbon increment per leaf area, the two effects compete,
#      so a "denser wood always survives better" implementation is detectably different from this one. The
#      test pins that `mort_max` is monotone decreasing in `wooddens` at the measured 1.765 ratio AND that
#      the total hazard can be NON-monotone in `wooddens` once `greff` responds — i.e. it fails if someone
#      "simplifies" the logistic away.
#
# It also asserts the two things that make the operator safe to wire in later: `pft_mort_params` ERRORS on
# an unknown id (never defaults to beech — line M's drivers still default `pft_ids` to 3), and the module
# is type-generic and allocation-free on the hot path.

@testitem "Ported FIT mortality hazard — parameter provenance against the generated C reference" tags = [:scientific, :slow] begin
    using LPJmLFITEmulator: TraitMortality
    using LPJmLFITEmulator.TraitMortality: PFT_MORT_PARAMS, pft_mort_params, K_MORT, KMORT_2,
        KMORTBG_LNF, KMORTBG_Q, BM_INC_COUNTER_MAX, NDAYYEAR
    using Test

    csv = joinpath(@__DIR__, "references", "S_pft_mortality_params.csv")
    @test isfile(csv)
    lines = [l for l in readlines(csv) if !isempty(strip(l)) && !startswith(strip(l), "#")]
    hdr = String.(split(strip(lines[1]), ','))
    # `name` holds a free-text PFT name with no comma in it (asserted), so a plain split is safe here.
    rows = [String.(split(strip(l), ',')) for l in lines[2:end]]
    @test all(length(r) == length(hdr) for r in rows)
    col(r, k) = r[findfirst(==(k), hdr)]
    num(r, k) = parse(Float64, col(r, k))

    @test length(rows) == 7                     # ids 0-6, the complete tree set (ADR 0031)
    ids = [parse(Int, col(r, "pft_id")) for r in rows]
    @test sort(ids) == collect(0:6)
    @test sort(collect(keys(PFT_MORT_PARAMS))) == sort(ids)

    # ── every per-PFT field, exactly (these are decimal literals on both sides ⇒ bitwise equality) ──
    fields = (
        :wdmort_1, :wdmort_2, :mort_water_factor, :mort_water_res, :mort_temp_factor,
        :longevity, :temp_low, :temp_high, :aphen_min,
        :lai_sapl, :allom1, :allom2, :allom3, :kpr, :k_latosa, :wood_sapl,
    )
    for r in rows
        i = parse(Int, col(r, "pft_id"))
        p = pft_mort_params(i)
        @test p.pft_id == i
        for f in fields
            @test getfield(p, f) == num(r, String(f))
        end
    end

    # ── the GLOBALS, which the CSV repeats on every row precisely so they cannot drift unnoticed ──
    for r in rows
        @test num(r, "k_mort") == K_MORT
        @test num(r, "kmort_2") == KMORT_2
        @test num(r, "kmortbg_lnf") ≈ KMORTBG_LNF rtol = 1.0e-15
        @test num(r, "kmortbg_q") == KMORTBG_Q
        @test num(r, "bm_inc_counter_max") == BM_INC_COUNTER_MAX
        @test num(r, "ndayyear") == NDAYYEAR
    end

    # ── the three rows a temperate/beech default used to get wrong, called out individually so a
    #    regression names itself instead of appearing as "some field of some PFT moved" ──
    @test pft_mort_params(5).longevity == 125.0            # NOT TREE_LONGEVITY 400 (3.2x age mortality)
    @test pft_mort_params(5).mort_water_factor == 20.0     # NOT beech's 5
    @test pft_mort_params(1).mort_water_res == 0.25        # XERIC, NOT ANGIO 0.75
    @test pft_mort_params(2).mort_water_res == 0.25        # XERIC
    @test pft_mort_params(6).aphen_min == 10.0             # larch's duplicate-key override, NOT 60
    @test all(pft_mort_params(i).aphen_min == 60.0 for i in 0:5)
    @test pft_mort_params(0).wdmort_1 == -2.458            # tropical, NOT temperate -2.465
    @test pft_mort_params(3).wdmort_1 == -2.465            # temperate (beech)
    @test all(pft_mort_params(i).temp_high == 54.0 for i in 0:6)

    # ── the lookup must ERROR, never default: a beech row silently applied to ids 0/1/2/4/5/6 is the
    #    ADR-0031 defect class, and `FDiffFastCore` still defaults `pft_ids` to 3 (M integration point) ──
    for bad in (-1, 7, 8, 9, 10, 21, 99)
        @test_throws ErrorException pft_mort_params(bad)
    end
end

@testitem "Ported FIT mortality hazard — each component matches its C expression" tags = [:scientific, :slow] begin
    using LPJmLFITEmulator.TraitMortality
    using LPJmLFITEmulator.TraitMortality: K_MORT, KMORT_2, KMORTBG_LNF, KMORTBG_Q, BM_INC_COUNTER_MAX,
        NDAYYEAR
    using Test

    p = pft_mort_params(3)      # beech, the cell every single-cell gate is on

    # ── mort_max = 10^(wdmort_1 + wdmort_2/(wooddens/1e6))   (mortality_tree_ind.c:92) ──
    for wd in (7.0e4, 1.4787e5, 2.0e5, 3.0e5, 6.37e5)
        @test mort_max(p, wd) ≈ 10.0^(p.wdmort_1 + p.wdmort_2 / (wd / 1.0e6)) rtol = 1.0e-14
    end

    # ── mort_npp = min(1, mort_max/(1+KMORT_2*exp(k_mort*greff))*(1+counter)); 1 if leafarea ≤ 1e-6 ──
    wd, bm, la = 2.0e5, 250.0, 12.0
    mm = mort_max(p, wd)
    want = mm / (1 + KMORT_2 * exp(K_MORT * bm / la))
    @test mort_npp(p, wd, bm, la) ≈ want rtol = 1.0e-14
    @test mort_npp(p, wd, bm, la; bm_inc_counter = 2) ≈ min(1.0, 3 * want) rtol = 1.0e-14
    @test mort_npp(p, wd, bm, 1.0e-6) == 1.0            # the `>` boundary is exclusive (:95)
    @test mort_npp(p, wd, bm, 0.0) == 1.0
    @test mort_npp(p, wd, bm, 2.0e-6) < 1.0
    # a huge negative increment saturates the logistic at mort_max, not above it: as greff → −∞ the
    # denominator → 1, so mort_npp → mort_max. That ceiling is what bounds the trait channel.
    @test mort_npp(p, wd, -1.0e6, la) ≈ min(1.0, mm) rtol = 1.0e-9
    @test mort_npp(p, wd, 1.0e6, la) < 1.0e-9          # and → 0 as greff → +∞
    # the per-component cap fires BEFORE the sum, so mort_npp is always in [0, 1]
    @test 0 <= mort_npp(p, wd, bm, la; bm_inc_counter = 4) <= 1.0

    # ── mort_age = min(1, KMORTBG_LNF*(KMORTBG_Q+1)/L*(age/L)^KMORTBG_Q)   (mort_min(), :40-44) ──
    for age in (0.0, 1.0, 42.0, 200.0, 400.0, 4000.0)
        want_a = min(1.0, KMORTBG_LNF * (KMORTBG_Q + 1) / p.longevity * (age / p.longevity)^KMORTBG_Q)
        @test mort_age(p, age) ≈ want_a rtol = 1.0e-14
    end
    @test mort_age(p, 0.0) == 0.0
    @test mort_age(p, 1.0e6) == 1.0                     # the cap (:110-111)
    # id 5's shorter longevity means MORE age mortality at the same age — the 3.2x parameter error's effect
    @test mort_age(pft_mort_params(5), 100.0) > mort_age(pft_mort_params(3), 100.0)
    @test mort_age(pft_mort_params(5), 100.0) / mort_age(pft_mort_params(3), 100.0) ≈ (400 / 125)^3 rtol = 1.0e-12

    # ── mort_water = min(1, factor*water_stress/365*(1+counter))   (:113-115) — counter MULTIPLIES ──
    @test mort_water(p, 10.0) ≈ p.mort_water_factor * 10.0 / NDAYYEAR rtol = 1.0e-14
    @test mort_water(p, 10.0; bm_inc_counter = 3) ≈ 4 * p.mort_water_factor * 10.0 / NDAYYEAR rtol = 1.0e-14
    @test mort_water(p, 1.0e6) == 1.0
    @test mort_water(p, 0.0) == 0.0

    # ── mort_temp = min(1, factor*temp_stress/365)   (:117-119) — NO counter multiplier ──
    @test mort_temp(p, 30.0) ≈ p.mort_temp_factor * 30.0 / NDAYYEAR rtol = 1.0e-14
    @test mort_temp(p, 1000.0) == 1.0
    @test mort_temp(p, 0.0) == 0.0

    # ── leaf_carbon_sapl   (:63-65) ──
    for sla in (0.005, 0.01986, 0.0547)
        h = p.kpr / 2
        want_l = (p.lai_sapl * p.allom1 * p.wood_sapl^h * (4 * sla / pi / p.k_latosa)^h / sla)^(2 / (2 - p.kpr))
        @test leaf_carbon_sapl(p, sla) ≈ want_l rtol = 1.0e-13
    end
    @test leaf_carbon_sapl(p, 0.01986) > 0

    # ── the bm_inc_counter recursion   (:71-81): reset at PRE-increment age 1, else ±1 on sign ──
    @test update_bm_inc_counter(4, 1, -5.0) == 1        # age==1 resets to 0 first, then increments
    @test update_bm_inc_counter(4, 1, 5.0) == 0
    @test update_bm_inc_counter(0, 50, -5.0) == 1
    @test update_bm_inc_counter(3, 50, -5.0) == 4
    @test update_bm_inc_counter(3, 50, 0.0) == 0        # `bm_delta < 0` is strict
    @test update_bm_inc_counter(3, 50, 5.0) == 0
end

@testitem "Ported FIT mortality hazard — additive combination, caps and the two hard kills" tags = [:scientific, :slow] begin
    using LPJmLFITEmulator.TraitMortality
    using LPJmLFITEmulator.TraitMortality: BM_INC_COUNTER_MAX
    using Test

    p = pft_mort_params(3)
    base = (
        wooddens = 2.0e5, sla = 0.01986, age = 60.0, bm_delta = 250.0, leafarea = 12.0,
        leaf_c = 5000.0, water_stress = 3.0, temp_stress = 4.0,
    )
    h = mortality_hazard(p; base...)

    # ADDITIVE, then ONE cap (:122-124) — not multiplicative, not a max
    @test h.total ≈ min(1.0, h.npp + h.age + h.water + h.temp) rtol = 1.0e-15
    @test h.hard_kill === :none
    @test 0 < h.total < 1
    @test survival_prob(h) ≈ 1 - h.total rtol = 1.0e-15
    # the decomposition must equal the standalone components (no hidden re-scaling)
    @test h.npp ≈ mort_npp(p, base.wooddens, base.bm_delta, base.leafarea) rtol = 1.0e-15
    @test h.age ≈ mort_age(p, base.age) rtol = 1.0e-15
    @test h.water ≈ mort_water(p, base.water_stress) rtol = 1.0e-15
    @test h.temp ≈ mort_temp(p, base.temp_stress) rtol = 1.0e-15

    # the SUM cap: four large-but-sub-unit components must clamp to exactly 1, not overflow
    hbig = mortality_hazard(
        p; base..., age = 390.0, water_stress = 60.0, temp_stress = 60.0, bm_delta = -400.0
    )
    @test hbig.total == 1.0
    @test hbig.npp + hbig.age + hbig.water + hbig.temp > 1.0
    @test all(0 .<= (hbig.npp, hbig.age, hbig.water, hbig.temp) .<= 1)

    # HARD KILL 1 — bm_inc_counter ≥ 5 (:128-129), and it dominates an otherwise tiny hazard
    hk = mortality_hazard(p; base..., bm_inc_counter = BM_INC_COUNTER_MAX)
    @test hk.hard_kill === :bm_inc_counter
    @test hk.total == 1.0
    @test survival_prob(hk) == 0.0
    @test mortality_hazard(p; base..., bm_inc_counter = BM_INC_COUNTER_MAX - 1).hard_kill !== :bm_inc_counter

    # HARD KILL 2 — leaf_c below a sapling's (:132-133, the "ghost tree fix")
    lcs = leaf_carbon_sapl(p, base.sla)
    hg = mortality_hazard(p; base..., leaf_c = 0.5 * lcs)
    @test hg.hard_kill === :ghost_tree
    @test hg.total == 1.0
    @test mortality_hazard(p; base..., leaf_c = 1.5 * lcs).hard_kill === :none
    # the counter kill is checked FIRST in the C, so it wins when both apply
    @test mortality_hazard(
        p; base..., leaf_c = 0.5 * lcs, bm_inc_counter = BM_INC_COUNTER_MAX
    ).hard_kill === :bm_inc_counter

    # every tree PFT produces a finite, bounded hazard on its OWN wooddens interval
    for i in 0:6
        pi_ = pft_mort_params(i)
        for wd in (1.0e5, 2.0e5, 6.0e5)
            hi = mortality_hazard(pi_; base..., wooddens = wd)
            @test isfinite(hi.total) && 0 <= hi.total <= 1
        end
    end

    # type genericity + inferability: Float32 in ⇒ Float32 out, concretely inferred (no Any leak into a
    # future call site inside the coupled loop, where an unstable return would show up as a JET flag)
    h32 = mortality_hazard(
        p; wooddens = 2.0f5, sla = 0.01986f0, age = 60.0f0, bm_delta = 250.0f0, leafarea = 12.0f0,
        leaf_c = 5000.0f0, water_stress = 3.0f0, temp_stress = 4.0f0
    )
    @test h32 isa MortHazard{Float32}
    @test h32.total ≈ Float32(h.total) rtol = 1.0f-5
    @test @inferred(
        mortality_hazard(
            p; wooddens = 2.0e5, sla = 0.01986, age = 60.0, bm_delta = 250.0, leafarea = 12.0,
            leaf_c = 5000.0, water_stress = 3.0, temp_stress = 4.0
        )
    ) isa MortHazard{Float64}
    @test @inferred(mort_max(p, 2.0e5)) isa Float64
    @test @inferred(mort_age(p, 60.0)) isa Float64
end

@testitem "Ported FIT mortality hazard — wood-density selection is NOT sign-definite (ADR 0046 §3)" tags = [:scientific, :slow] begin
    using LPJmLFITEmulator.TraitMortality
    using Test

    p = pft_mort_params(3)

    # `mort_max` alone says "denser wood survives better": strictly decreasing, and the ADR-0046 ratio
    # over the 2e5 → 3e5 interval is 1.765. That number is the reason a `mort_max`-only port looks right.
    @test mort_max(p, 3.0e5) < mort_max(p, 2.0e5)
    @test mort_max(p, 2.0e5) / mort_max(p, 3.0e5) ≈ 1.765 rtol = 5.0e-3
    wds = 1.0e5:2.0e4:6.0e5
    @test all(diff([mort_max(p, w) for w in wds]) .< 0)

    # BUT `mort_max` enters only THROUGH the growth-efficiency logistic, and `greff` is the other
    # argument. So the ranking of two individuals by hazard depends on BOTH, and the density advantage is
    # a FINITE factor that a greff difference can overturn. That is the whole content of ADR 0046 §3's
    # "not sign-definite", and it is testable without inventing a greff(wooddens) relation — which would
    # only be asserting a toy model of the growth side. What is asserted instead:
    #
    #   (a) the density advantage is exactly the mort_max ratio (1.765 over 2e5 → 3e5), because the
    #       logistic factorizes: mort_npp = mort_max(wd) · f(greff);
    #   (b) therefore the crossover is the greff at which f(greff_light)/f(greff_dense) = 1.765, a FINITE
    #       greff — solved numerically below;
    #   (c) that crossover greff lies INSIDE FIT's measured `growth_eff` distribution (global mean 146.7,
    #       max 31 183 on the seed1 t7 table — CLAUDE.md §3), so the flip is reachable in the real model,
    #       not a mathematical curiosity.
    fixed = (
        sla = 0.01986, age = 60.0, leafarea = 12.0, leaf_c = 5000.0,
        water_stress = 3.0, temp_stress = 4.0,
    )
    npp_of(wd, greff) = mort_npp(p, wd, greff * fixed.leafarea, fixed.leafarea)

    # (a) the logistic factorizes out of the trait dependence, exactly
    for greff in (-50.0, 0.0, 20.0, 200.0, 2000.0)
        @test npp_of(2.0e5, greff) / npp_of(3.0e5, greff) ≈ mort_max(p, 2.0e5) / mort_max(p, 3.0e5) rtol = 1.0e-12
    end

    # (b) solve for the crossover: greff_light such that the LIGHT tree's hazard equals the DENSE tree's
    #     at greff_dense = 0. Bisection on a strictly decreasing function ⇒ unique root.
    gdense = 0.0
    target = npp_of(3.0e5, gdense)
    @test npp_of(2.0e5, 0.0) > target                # at equal greff the dense tree is safer
    glo, ghi = 0.0, 1.0e4
    @test npp_of(2.0e5, ghi) < target                # ...and at high greff the light tree is safer
    for _ in 1:200
        gmid = (glo + ghi) / 2
        npp_of(2.0e5, gmid) > target ? (glo = gmid) : (ghi = gmid)
    end
    gcross = (glo + ghi) / 2
    @test npp_of(2.0e5, gcross) ≈ target rtol = 1.0e-8
    # (c) the crossover sits at a growth efficiency FIT routinely realizes (mean 146.7, max 31 183)
    @test 100 < gcross < 1000
    @test gcross < 31183

    # and the flip is real at in-range greff values on BOTH sides of it
    @test npp_of(2.0e5, 200.0) < npp_of(3.0e5, 50.0)      # dense-but-slow dies FASTER: sign flipped
    @test npp_of(2.0e5, 50.0) > npp_of(3.0e5, 50.0)       # at equal greff, dense wins: sign restored

    # the competition must be visible in the DECOMPOSITION, not hidden: `npp` is the only component that
    # moves with wooddens, and it carries the whole trait signal
    h2 = mortality_hazard(p; fixed..., wooddens = 2.0e5, bm_delta = 250.0)
    h3 = mortality_hazard(p; fixed..., wooddens = 3.0e5, bm_delta = 250.0)
    @test h2.age == h3.age && h2.water == h3.water && h2.temp == h3.temp
    @test h3.npp < h2.npp

    # `sla` is a SECOND, weaker trait channel — through the ghost-tree threshold, which rises with sla
    @test leaf_carbon_sapl(p, 0.05) < leaf_carbon_sapl(p, 0.005)
    @test mortality_hazard(p; fixed..., wooddens = 2.0e5, bm_delta = 250.0, leaf_c = 1.0).hard_kill ===
        :ghost_tree

    # per-PFT `wdmort` pairs really do separate the PFTs at the same wood density (the ADR-0031 point)
    mm = [mort_max(pft_mort_params(i), 2.0e5) for i in 0:6]
    @test length(unique(round.(mm, sigdigits = 6))) >= 3
    @test mort_max(pft_mort_params(0), 2.0e5) != mort_max(pft_mort_params(3), 2.0e5)
end
