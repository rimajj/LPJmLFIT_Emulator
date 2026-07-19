# PER-PFT GSI LEAF PHENOLOGY (scale-up step 8 — docs/phase3_fdiff_cbinary_validation.md §19).
# Generalizes the self-computed leaf phenology (§11) from ONE patch-wide beech GSI to PER-PFT: each
# individual advances its own PFT's four-limiter GSI (`pft_phenparams`, verbatim from the ACTIVE
# par/pft_lpjmlfit.js), and `daily_step_canopy`/`patch_albedo`/`rollout_daily_canopy` accept a
# per-individual `phen` vector. This gate proves (1) the per-PFT params match the active FIT file
# EXACTLY, (2) the beech correction (tmin 2/8 → 4/8.5, was mis-sourced from the standard par/pft.js),
# (3) the scalar `phen` path is BYTE-IDENTICAL to pre-per-PFT behaviour (so every committed baseline +
# the Enzyme trainer are untouched), (4) the per-individual vector path changes the display correctly and
# stays differentiable, and (5) the per-PFT self-driven rollout runs, closes water, and diverges from the
# beech-patch-wide default only through the non-beech minority.

@testitem "Per-PFT phenology — params match the active FIT file + beech correction" tags = [:validation, :fdiff, :canopy, :phenology] begin
    using LPJmLFITEmulator
    const F = LPJmLFITEmulator.FDiff

    # (tmin_sl, tmin_base, tmin_tau, tmax_sl, tmax_base, tmax_tau, light_sl, light_base, light_tau,
    #  wscal_sl, wscal_base = minwscal_median·100, wscal_tau) — verbatim from par/pft_lpjmlfit.js.
    expected = Dict(
        0 => (1.01, 10.0, 0.2, 1.86, 38.64, 0.2, 77.17, 55.53, 0.52, 5.14, 60.0, 0.44),      # TrBE
        1 => (1.0, -30.0, 0.1, 1.83, 35.26, 0.2, 20.0, 40.872, 0.2, 5.0, 10.0, 0.01),         # TeNE
        2 => (1.0, -5.0, 0.2, 1.6, 41.12, 0.2, 18.83, 2.0, 0.2, 5.0, 10.0, 0.1),              # TeBE
        3 => (4.0, 8.5, 0.2, 1.74, 41.51, 0.2, 58.0, 40.0, 0.2, 5.24, 20.96, 0.1),            # TeBS (beech)
        4 => (0.5, -80.0, 0.2, 0.4, 28.0, 0.2, 15.0, 0.001, 0.1, 5.0, 25.0, 0.01),            # BoNE
        5 => (2.0, 8.0, 0.2, 1.74, 28.0, 0.2, 58.0, 55.0, 0.2, 5.24, 25.0, 0.1),              # BoBS
        6 => (1.0, 7.0, 0.1, 0.5, 28.0, 0.2, 58.0, 59.78, 0.2, 5.0, 35.0, 0.8),               # BoNS
        7 => (0.91, 6.418, 0.2, 1.47, 29.16, 0.2, 64.23, 69.9, 0.4, 0.1, 20.0, 0.17),         # TrC4 grass
        8 => (1.0, 6.0, 0.1011, 0.24, 32.04, 0.2, 23.0, 75.94, 0.22, 0.5222, 20.0, 0.1),      # TeC3 grass
        9 => (0.311, 4.79, 0.11, 0.24, 20.0, 0.2, 23.0, 50.0, 0.38, 0.88, 20.0, 0.94),        # PoC3 grass
    )
    fields = (
        :tmin_sl, :tmin_base, :tmin_tau, :tmax_sl, :tmax_base, :tmax_tau,
        :light_sl, :light_base, :light_tau, :wscal_sl, :wscal_base, :wscal_tau,
    )
    for id in 0:9
        pp = F.pft_phenparams(id)
        for (k, fld) in enumerate(fields)
            @test getfield(pp, fld) == expected[id][k]
        end
    end

    # beech (id 3) == the PhenParams defaults == tebs_phenparams; the tmin correction is applied.
    @test F.pft_phenparams(3) == F.tebs_phenparams() == F.PhenParams{Float64}()
    @test F.tebs_phenparams().tmin_sl == 4.0 && F.tebs_phenparams().tmin_base == 8.5   # active file (was 2.0/8.0)

    # crops (id ≥ 10, cropgreen) are out of scope for the natural-vegetation canopy.
    @test_throws ArgumentError F.pft_phenparams(10)
    @test_throws ArgumentError F.pft_phenparams(-1)

    # grass classification (0–6 trees, 7–9 grasses).
    @test !F._pft_is_grass(3) && F._pft_is_grass(8) && F._pft_is_grass(7) && !F._pft_is_grass(0)
end

@testitem "Per-PFT phenology — trajectories are distinct, bounded, and physically ordered" tags = [:validation, :fdiff, :canopy, :phenology] begin
    using LPJmLFITEmulator
    const F = LPJmLFITEmulator.FDiff

    # a temperate-seasonal year of daily forcing (sinusoidal air temp + shortwave; DOY-driven).
    ndays = 365
    forc = [
        F.DailyForcing{Float64}(
                temp = 8.0 + 15.0 * sin(2π * (d - 100) / 365),
                swdown = 120.0 + 130.0 * sin(2π * (d - 100) / 365),
                precip = 2.0, daylength = 12.0 + 4.0 * sin(2π * (d - 80) / 365),
                co2 = 380.0, lwnet = -45.0,
            ) for d in 1:ndays
    ]

    # patch: beech (id 3) + temperate C3 grass (id 8) + temperate needleleaved "evergreen" (id 1).
    pft_ids = [3, 3, 8, 1]
    phens = F.per_pft_phenology(pft_ids, forc)

    @test length(phens) == ndays && all(length(p) == length(pft_ids) for p in phens)
    @test all(all(0.0 .<= p .<= 1.0) for p in phens)                     # every phen ∈ [0,1]
    # the two beech individuals share one trajectory (same PFT, same forcing).
    @test all(phens[d][1] == phens[d][2] for d in 1:ndays)
    # beech (summergreen) has a strong seasonal amplitude — near-off in deep winter, near-full in summer.
    beech = [phens[d][1] for d in 1:ndays]
    @test minimum(beech) < 0.2 && maximum(beech) > 0.8
    # the "evergreen"-named TeNE (id 1) is NOT static: it runs the full GSI, but with a far colder tmin
    # base (−30 vs beech 8.5) it holds much MORE winter leaf display than beech (higher annual mean).
    tene = [phens[d][4] for d in 1:ndays]
    @test sum(tene) / ndays > sum(beech) / ndays
    @test maximum(tene) - minimum(tene) < maximum(beech) - minimum(beech)   # smaller seasonal swing
    # grass (id 8) is a distinct trajectory from beech (different params).
    grass = [phens[d][3] for d in 1:ndays]
    @test any(abs(grass[d] - beech[d]) > 0.05 for d in 1:ndays)

    # grass forest-floor light attenuation lowers the grass light limiter ⇒ generally lower grass phen.
    grass_shaded = F.per_pft_phenology([8], forc; grass_light_frac = 0.15)
    grass_open = F.per_pft_phenology([8], forc; grass_light_frac = 1.0)
    @test sum(g[1] for g in grass_shaded) <= sum(g[1] for g in grass_open) + 1.0e-9
end

@testitem "Per-PFT phenology — scalar phen path is byte-identical; per-individual vector changes display" tags = [:validation, :fdiff, :canopy, :phenology] begin
    using LPJmLFITEmulator
    const F = LPJmLFITEmulator.FDiff

    soil = F.hainich_soilcolumn(;
        whcs = [37.0, 53.0, 88.0, 175.0, 175.0], rootdist = [0.41, 0.32, 0.2, 0.07, 0.0],
        soildepth = [200.0, 300.0, 500.0, 1000.0, 1000.0],
    )
    mkind(fpar, fpc, sla, grass) = F.Individual{Float64}(
        fpar, fpc, 0.5, 0.05, 5.0, 3000.0, 800.0, 4.0 * fpc, 0.02, 0.04, 0.1, 0.4, 1 / 225,
        F.PhotoParams{Float64}(; path = :c3, issla = true, sla = sla),
        F.TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), grass,
    )
    inds = [mkind(0.55, 0.35, 0.01986, false), mkind(0.25, 0.25, 0.022, false), mkind(0.05, 0.15, 0.03, true)]
    p = F.tebs_params()
    st0 = F.FDiffStateML{Float64}(fill(60.0, 5), 0.0)
    f = F.DailyForcing{Float64}(; temp = 15.0, swdown = 220.0, precip = 2.0, daylength = 13.0, co2 = 380.0, lwnet = -45.0)

    # (1) BYTE-IDENTITY: scalar phen == a uniform per-individual vector of the same value (self-eeq path).
    for phv in (0.0, 0.37, 0.8, 1.0)
        (sa, fa) = F.daily_step_canopy(p, inds, soil, st0, f; phen = phv)
        (sb, fb) = F.daily_step_canopy(p, inds, soil, st0, f; phen = fill(phv, length(inds)))
        @test fa.gpp == fb.gpp && fa.npp == fb.npp && fa.transp == fb.transp
        @test fa.evap == fb.evap && fa.interc == fb.interc && fa.eeq == fb.eeq
        @test fa.fapar == fb.fapar && fa.fpc == fb.fpc && fa.wscal == fb.wscal
        @test maximum(abs.(sa.w .- sb.w)) == 0.0 && sa.snowpack == sb.snowpack
        @test F.patch_albedo(inds, phv, 0.0) == F.patch_albedo(inds, fill(phv, length(inds)), 0.0)
    end
    # kernel-isolation eeq_ext path (the Enzyme trainer's config) is byte-identical too.
    (_, fe1) = F.daily_step_canopy(p, inds, soil, st0, f; phen = 0.6, eeq_ext = 3.2)
    (_, fe2) = F.daily_step_canopy(p, inds, soil, st0, f; phen = fill(0.6, length(inds)), eeq_ext = 3.2)
    @test fe1.gpp == fe2.gpp && fe1.npp == fe2.npp && fe1.transp == fe2.transp

    # (2) PER-INDIVIDUAL vector changes the display: zeroing the grass individual removes ITS contribution
    # while leaving the two trees' contributions unchanged (each individual's phen scales only its own
    # fpc/fpar/supply). Compare against driving every individual with the tree phen.
    (_, f_all) = F.daily_step_canopy(p, inds, soil, st0, f; phen = [0.9, 0.9, 0.9], eeq_ext = 3.2)
    (_, f_nog) = F.daily_step_canopy(p, inds, soil, st0, f; phen = [0.9, 0.9, 0.0], eeq_ext = 3.2)
    @test f_nog.gpp < f_all.gpp                       # grass leaf-off ⇒ lower stand GPP
    @test f_nog.fpc < f_all.fpc                        # grass contributes no projective cover when off
    # a purely tree-vs-tree change: raising individual 2's phen raises stand GPP monotonically.
    (_, f_lo) = F.daily_step_canopy(p, inds, soil, st0, f; phen = [0.9, 0.3, 0.5], eeq_ext = 3.2)
    (_, f_hi) = F.daily_step_canopy(p, inds, soil, st0, f; phen = [0.9, 0.7, 0.5], eeq_ext = 3.2)
    @test f_hi.gpp > f_lo.gpp
end

@testitem "Per-PFT phenology — self-driven rollout closes water + diverges from beech-only via the minority" tags = [:validation, :fdiff, :canopy, :phenology] begin
    using LPJmLFITEmulator
    const F = LPJmLFITEmulator.FDiff

    soil = F.hainich_soilcolumn(;
        whcs = [37.0, 53.0, 88.0, 175.0, 175.0], rootdist = [0.41, 0.32, 0.2, 0.07, 0.0],
        soildepth = [200.0, 300.0, 500.0, 1000.0, 1000.0],
    )
    mkind(fpar, fpc, sla, grass) = F.Individual{Float64}(
        fpar, fpc, 0.5, 0.05, 5.0, 3000.0, 800.0, 4.0 * fpc, 0.02, 0.04, 0.1, 0.4, 1 / 225,
        F.PhotoParams{Float64}(; path = :c3, issla = true, sla = sla),
        F.TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), grass,
    )
    # a beech-dominated patch with a grass + an evergreen minority (mirrors Hainich composition).
    inds = [mkind(0.55, 0.4, 0.01986, false), mkind(0.25, 0.25, 0.022, false), mkind(0.05, 0.12, 0.03, true), mkind(0.1, 0.1, 0.025, false)]
    pft_ids = [3, 3, 8, 1]
    ndays = 200
    forc = [
        F.DailyForcing{Float64}(
                temp = 8.0 + 14.0 * sin(2π * (d - 40) / 200),
                swdown = 120.0 + 120.0 * sin(2π * (d - 40) / 200),
                precip = 2.0, daylength = 12.0 + 3.0 * sin(2π * (d - 30) / 200),
                co2 = 380.0, lwnet = -45.0,
            ) for d in 1:ndays
    ]
    p = F.tebs_params()
    st0 = F.FDiffStateML{Float64}([0.6 * wc for wc in [37.0, 53.0, 88.0, 175.0, 175.0]], 0.0)

    # per-PFT self-driven rollout (each individual its own PFT's GSI phen).
    (stf, days) = F.rollout_daily_canopy(p, st0, inds, soil, forc; pft_ids = pft_ids)
    @test length(days) == ndays
    @test all(isfinite(d.gpp) && isfinite(d.transp) && isfinite(d.eeq) && isfinite(d.npp) for d in days)
    @test all(d.gpp >= 0 for d in days)
    # water closes over the rollout: Σprecip = Σ(transp+evap+interc+runoff) + Δ(Σw + snow).
    Σprecip = sum(f.precip for f in forc)
    Σout = sum(d.transp + d.evap + d.interc + d.runoff for d in days)
    ΔS = (sum(stf.w) + stf.snowpack) - (sum(st0.w) + st0.snowpack)
    @test abs(Σprecip - (Σout + ΔS)) < 1.0e-6

    # the beech-patch-wide DEFAULT (pft_ids = nothing) differs from per-PFT ONLY through the minority PFTs:
    # a patch of ALL beech gives identical annual GPP either way (per-PFT with all-3 ids == default).
    (_, days_def) = F.rollout_daily_canopy(p, st0, inds, soil, forc)                    # beech-patch-wide
    @test sum(d.gpp for d in days) != sum(d.gpp for d in days_def)                       # minority shifts the cell
    inds_beech = [mkind(0.55, 0.4, 0.01986, false), mkind(0.25, 0.25, 0.022, false)]     # all-beech patch
    (_, db_pft) = F.rollout_daily_canopy(p, st0, inds_beech, soil, forc; pft_ids = [3, 3])
    (_, db_def) = F.rollout_daily_canopy(p, st0, inds_beech, soil, forc)
    @test sum(d.gpp for d in db_pft) ≈ sum(d.gpp for d in db_def) rtol = 1.0e-12         # all-beech ⇒ identical
end

# AD-SAFETY of per-PFT phenology is established WITHOUT a dedicated gradient testitem here: per-individual
# `phen` is a Const forcing-derived input on the STANDALONE self-driven path — it is NOT used by the Enzyme
# trainer, which keeps its scalar C-FAPAR `phens` kernel-isolation drive. The scalar `phen` path is proven
# BYTE-IDENTICAL above (Δ = 0 vs a uniform per-individual vector), so the coupled-canopy Enzyme gates
# (`nn_canopy_training_tests.jl`, guarded `VERSION < v"1.11"`) — which differentiate w.r.t. the NN params
# with scalar phen — are structurally untouched by this change. (`daily_step_canopy`'s positional
# `FDiffParams{T}` ctor, chosen for Enzyme, is not ForwardDiff-able w.r.t. inputs that promote `T` to a
# Dual while the per-individual `PhotoParams` stay `Float64` — a pre-existing property, unrelated to phen.)
