# THE TWO PER-INDIVIDUAL STRESS INTEGRALS: RESET DAY AND WATER-ONLY GATING (line S, ADR 0244).
#
# ADR 0110 Phase 2 built `water_stress_acc` / `temp_stress_acc` — the two annual integrals the ported
# mortality hazard consumes and that ADR 0049 §3 had to set to zero. Nothing exercised them: they had NO
# test and no probe, and ADR 0243 then measured that running the hazard on zeros delivers only 0.78 of the
# mortality flux LPJmL-FIT's own stand asks for. Two defects surfaced when the path was finally read
# against the C, and these assertions encode the C's SEMANTICS for both — no fitted numbers.
#
#   1. `tempstress_tree.c:29` reads the day's AIR temperature against the PFT's own `temp_stressed`
#      interval and nothing else, so the temperature integral needs no per-tree water state. It used to be
#      behind an early `return` on `wscal_ind === nothing`, i.e. silently zero without `per_tree_roots` —
#      and it is the DOMINANT of the two at the cold cells (24 stressed days/yr at boreal `c52059`).
#   2. BOTH integrals (and `pft->aphen` with them, `phenology_gsi.c:87-90`) are zeroed by the C on a FIXED
#      CALENDAR DAY — `COLDEST_DAY_NHEMISPHERE` 14 / `COLDEST_DAY_SHEMISPHERE` 195, `include/climate.h` —
#      AFTER that day's increment. The value the annual mortality call reads is therefore the accumulation
#      over days `reset+1 … 365`, NOT a calendar-year total. Measured against the C's own dumped
#      `temp_stress` over 178 (cell, year, PFT) groups, the C's window reproduces it 178/178 integer for
#      integer while a calendar year over-counts the stressed-day total by +32 %
#      (`scripts/diagnose_stress_integral_window.py`).
#
# Guardrail 4 is asserted first: with `trait_drought_mortality` off (the default) nothing accumulates.

@testitem "stress integrals: default off is inert; temperature needs no per-tree water (ADR 0244)" tags = [:validation, :fdiff] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.Allometry
    using LPJmLFITEmulator.FDiff: hainich_soilcolumn, TreePools, Individual, PhotoParams,
        TempStressParams, WaterParams, FDiffParams

    # one beech cohort (PFT id 3, `temp_stressed` = [-20, 54] °C) — the parameters come from the shipped
    # table via `pft_mort_params`, so this test cannot drift from it.
    # the 13-arg constructor: leaf, sapwood, heartwood, root, sapwood_bg, height, crownarea, nind, sla,
    # wooddens, d95max, minwscal, is_grass
    pool = TreePools{Float64}(
        0.12, 0.5, 0.4, 0.02, 0.0, 10.0, 5.0, 0.02, 0.0198, 200_000.0, 150.0, 0.05, false,
    )
    tmpl = Individual{Float64}(
        0.5, 0.0, 0.5, 0.12, 10.0, 0.0, 0.0, 0.0, 0.0, 0.02, 0.04, 0.1, 0.4, 1.0,
        PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.0198),
        TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false,
    )
    sd = Float64[]; whcs = Float64[]; rdist = Float64[]
    for ln in eachline(joinpath(@__DIR__, "references", "hainich_soilcolumn.txt"))
        s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
        x = parse.(Float64, split(s)); push!(sd, x[2]); push!(whcs, x[3]); push!(rdist, x[4])
    end
    soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)

    mkcore(lat, tdm) = LPJmLFITEmulator.FDiffFastCore(
        [pool], [tmpl], soil, lat;
        params = FDiffParams{Float64}(water = WaterParams{Float64}(trait_drought_mortality = tdm)),
    )
    # one day of the accumulator, at a chosen day-of-year. `fl` carries only what it reads; `wscal_ind =
    # nothing` IS the no-`per_tree_roots` case, which is the shipped default.
    function oneday!(fc, doy, temp; wscal_ind = nothing)
        fc.doy = doy
        return LPJmLFITEmulator._accumulate_stress!(
            fc, (; wscal_ind = wscal_ind), 1.0, temp, temp, 0.006,
        )
    end

    # ── guardrail 4: off ⇒ nothing accumulates, whatever the weather ──────────────────────────────
    off = mkcore(51.25, false)
    for d in 1:40
        oneday!(off, d, -30.0)                       # far below beech's -20 °C, i.e. every day stressed
    end
    @test all(iszero, off.temp_stress_acc)
    @test all(iszero, off.water_stress_acc)
    @test all(iszero, off.aphen_acc)

    # ── the temperature integral runs with NO per-tree water available ────────────────────────────
    on = mkcore(51.25, true)
    for d in 20:29
        oneday!(on, d, -30.0)                        # 10 stressed days, all after the day-14 reset
    end
    @test on.temp_stress_acc[1] == 10                # would have been 0 before ADR 0244
    @test iszero(on.water_stress_acc[1])             # water still needs `per_tree_roots` — unchanged
end

@testitem "stress integrals: the reset is the C's fixed calendar day, per hemisphere (ADR 0244)" tags = [:validation, :fdiff] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff: hainich_soilcolumn, TreePools, Individual, PhotoParams,
        TempStressParams, WaterParams, FDiffParams

    # the 13-arg constructor: leaf, sapwood, heartwood, root, sapwood_bg, height, crownarea, nind, sla,
    # wooddens, d95max, minwscal, is_grass
    pool = TreePools{Float64}(
        0.12, 0.5, 0.4, 0.02, 0.0, 10.0, 5.0, 0.02, 0.0198, 200_000.0, 150.0, 0.05, false,
    )
    tmpl = Individual{Float64}(
        0.5, 0.0, 0.5, 0.12, 10.0, 0.0, 0.0, 0.0, 0.0, 0.02, 0.04, 0.1, 0.4, 1.0,
        PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.0198),
        TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false,
    )
    sd = Float64[]; whcs = Float64[]; rdist = Float64[]
    for ln in eachline(joinpath(@__DIR__, "references", "hainich_soilcolumn.txt"))
        s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
        x = parse.(Float64, split(s)); push!(sd, x[2]); push!(whcs, x[3]); push!(rdist, x[4])
    end
    soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)

    mkcore(lat) = LPJmLFITEmulator.FDiffFastCore(
        [pool], [tmpl], soil, lat;
        params = FDiffParams{Float64}(water = WaterParams{Float64}(trait_drought_mortality = true)),
    )
    # every day of a synthetic year is stressed (-30 °C < beech's temp_low = -20), so the accumulated
    # count IS the length of the surviving window and the reset day is read off it directly.
    function fullyear(lat)
        fc = mkcore(lat)
        for d in 1:365
            fc.doy = d
            LPJmLFITEmulator._accumulate_stress!(fc, (; wscal_ind = nothing), 1.0, -30.0, -30.0, 0.006)
        end
        return fc
    end

    # NORTH: zeroed on day 14 (after that day's increment) ⇒ days 15…365 survive = 351
    @test fullyear(51.25).temp_stress_acc[1] == 365 - 14
    # SOUTH: zeroed on day 195 ⇒ days 196…365 survive = 170. A calendar-year reset would give 365 for
    # both, i.e. 2.1x the C's own value here — this assertion is the one that catches a hemisphere bug.
    @test fullyear(-3.25).temp_stress_acc[1] == 365 - 195
    # the equator belongs to the northern branch, exactly as the C's `lat >= 0.0` test does
    @test fullyear(0.0).temp_stress_acc[1] == 365 - 14

    # `aphen` clears on the same day (`phenology_gsi.c:88`), so it is the reset day's day count too
    @test fullyear(51.25).aphen_acc[1] == 365 - 14
end
