# Gate — GRASS-OVERSHOOT RE-DIAGNOSIS (scale-up step 11; docs/phase3_fdiff_cbinary_validation.md §22).
#
# Session 16 (§21) attributed the §20 self-driven grass-NPP overshoot (~3x) to the SHARED stand-mean
# conductance `gp_stand` "over-supplying the understory grass", and set PER-PFT/per-individual canopy
# conductance as the next step. This gate encodes the CORRECTED diagnosis (§22): that attribution is
# REFUTED — three ways, each self-contained on the committed 2010 reference (no HPC/`/p/tmp`):
#
#  1. NO PER-YEAR OVERSHOOT AT FIXED STRUCTURE. At the C's OWN grass structure (real leaf/root carbon from
#     agb/vegc via grass_treepools, so real maintenance respiration), F_diff's self-computed per-year grass
#     NPP is FAITHFUL to the C's (ind-CSV `gpp_ind` == NPP; extract_fdiff_individuals.py:26): cell total
#     ratio ~0.83 (a mild UNDERshoot). So the grass photosynthesis/respiration is fine per-year.
#  2. F_diff'S GRASS GPP ALREADY USES gp_stand (LIKE THE C); PER-PFT WOULD DE-CALIBRATE IT. On the moist
#     Hainich cell (growing-season wscal ~0.99) the grass is only mildly water-limited, so its actual
#     conductance is ~0.75*gp_stand — it uses MOST of the stand mean, exactly as the C's water_stressed.c
#     returns grass GPP from gp_stand (the per-PFT gp_pft/gc_pft feed only the PFT_GCGP diagnostic —
#     daily_natural.c:187). The grass's OWN potential gp is only ~0.14*gp_stand, so a per-PFT (own-gp)
#     conductance would change the grass GPP ~43% — a large DE-calibration AWAY from the C-faithful value; a
#     per-PFT GPP conductance is thus LESS faithful, not the fix.
#  3. THE REAL DRIVER IS A MULTI-YEAR STRUCTURAL-FEEDBACK OVER-GROWTH. Self-driven, the grass leaf grows
#     far past the C's suppressed understory value (leaf -> lai -> forest-floor fpar -> NPP feedback),
#     because F_diff lacks the C's grass COVER/LIGHT competition (light.c -> light_grass.c kills grass
#     leaf/root back to the permitted cover). That cover competition — plus the C-faithful supply-side soil
#     water sharing — is the corrected next step, NOT per-PFT conductance.

@testitem "Grass re-diagnosis (1) — per-year grass NPP is FAITHFUL at the C's fixed structure" tags = [:validation, :fdiff, :canopy, :grass] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: grass_treepools, rollout_daily_canopy, tebs_params
    using Test

    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = readlines(path)
        i = findfirst(l -> !startswith(strip(l), "#") && !isempty(strip(l)), lines)
        hdr = split(strip(lines[i]), ',')
        rows = [split(strip(l), ',') for l in lines[(i + 1):end] if !isempty(strip(l))]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end
    function readtable(path)
        D = Float64[]; W = Float64[]; R = Float64[]
        for ln in eachline(path)
            s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
            v = parse.(Float64, split(s)); push!(D, v[2]); push!(W, v[3]); push!(R, v[4])
        end
        return (D, W, R)
    end
    fcol(d, k) = parse.(Float64, d[k])
    f = readcsv(joinpath(refdir, "hainich_forcing_2010.csv"))
    ind = readcsv(joinpath(refdir, "hainich_individuals_2010.csv"))
    (sd, whcs, rdist) = readtable(joinpath(refdir, "hainich_soilcolumn.txt"))
    soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)
    n = length(f["doy"])
    forc = [
        DailyForcing{Float64}(
                swdown = fcol(f, "swdown")[i], lwnet = fcol(f, "lwnet")[i], temp = fcol(f, "temp")[i],
                precip = fcol(f, "precip")[i], daylength = fcol(f, "daylength")[i], co2 = fcol(f, "co2")[i],
            ) for i in 1:n
    ]
    patches = sort(unique(parse.(Int, ind["patch"])))
    prows = Dict(p => Int[] for p in patches)
    for r in eachindex(ind["patch"])
        push!(prows[parse(Int, ind["patch"][r])], r)
    end
    vv(r, k) = parse(Float64, ind[k][r])
    pft_intc(typ) = typ <= 3 ? 0.02 : (typ <= 6 ? 0.06 : 0.01)
    function pft_albedo(typ)
        typ == 1 && return (0.04, 0.1, 0.1); typ in (2, 3) && return (0.04, 0.1, 0.4)
        typ in (4, 5) && return (0.1, 0.1, 0.15); typ == 6 && return (0.05, 0.01, 0.15); return (0.15, 0.1, 0.4)
    end
    function mkind(r)
        typ = parse(Int, ind["type"][r]); isg = typ >= 7; sla = vv(r, "sla"); (ast, alt, scf) = pft_albedo(typ)
        croot = vv(r, "root_c"); nind = vv(r, "nind"); csap = vv(r, "sapwood_c")
        if isg          # grass: real leaf/root from agb/vegc (grass_treepools) so maintenance respiration is real
            g = grass_treepools(vv(r, "agb"), vv(r, "vegc"), sla); croot = g.root_c; nind = 1.0; csap = 0.0
        end
        return Individual{Float64}(
            vv(r, "fpar_leafon"), vv(r, "fpc_ind"), vv(r, "alphaa"), vv(r, "albedo_leaf"), vv(r, "emax"),
            csap, croot, vv(r, "lai"), pft_intc(typ), ast, alt, scf, nind,
            FDiff.PhotoParams{Float64}(; path = :c3, issla = true, sla = sla),
            FDiff.TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), isg,
        )
    end

    totC = 0.0; totF = 0.0
    for pnum in patches
        rows = prows[pnum]; inds = [mkind(r) for r in rows]; pids = [parse(Int, ind["type"][r]) for r in rows]
        st0 = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
        (_, days) = rollout_daily_canopy(tebs_params(), st0, inds, soil, forc; pft_ids = pids)
        ann = zeros(length(rows))
        for d in days, i in eachindex(rows)
            ann[i] += d.npp_ind[i]
        end
        for (k, r) in enumerate(rows)
            if parse(Int, ind["type"][r]) >= 7
                totC += vv(r, "gpp_ind"); totF += ann[k]     # ind-CSV gpp_ind == C NPP
            end
        end
    end
    ratio = totF / totC
    @test isfinite(ratio) && totC > 0
    # At the C's OWN grass structure F_diff's per-year grass NPP does NOT overshoot (measured 0.83) — so the
    # §20 "3x" is NOT a per-year NPP miscalibration; the grass photosynthesis + respiration are faithful.
    @test 0.6 <= ratio <= 1.3
end

@testitem "Grass re-diagnosis (2) — grass GPP uses gp_stand (like the C); per-PFT conductance is not the fix" tags = [:validation, :fdiff, :canopy, :grass] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: canopy_conductance, photosynthesis, temp_stress,
        priestley_taylor_eeq, patch_albedo, ppm2Pa, ppm2bar, hour2sec, solve_lambda, FDiffParams,
        _wet_interc, _infiltrate, softplus, smoothmin, tebs_params, daily_step_canopy, _step_pft_phen_day!,
        pft_phenparams, PhenState, PhenParams, _pft_is_grass, _phen_at, _LAMBDA_LO, _LAMBDA_HI
    using Test

    # This mirrors daily_step_canopy's pass-1 (build gp_stand) and pass-2 (per-individual GPP + conductance)
    # to measure, for the understory grass, the ACTUAL conductance it receives (gc_grass) relative to the
    # stand mean (gp_stand), and the grass GPP recomputed with a per-PFT (own-gp) conductance. Agent-verified
    # faithful to the source arithmetic; used ONLY to measure the diagnostic ratios below.
    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = readlines(path); i = findfirst(l -> !startswith(strip(l), "#") && !isempty(strip(l)), lines)
        hdr = split(strip(lines[i]), ','); rows = [split(strip(l), ',') for l in lines[(i + 1):end] if !isempty(strip(l))]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end
    function readtable(path)
        D = Float64[]; W = Float64[]; R = Float64[]
        for ln in eachline(path)
            s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
            v = parse.(Float64, split(s)); push!(D, v[2]); push!(W, v[3]); push!(R, v[4])
        end
        return (D, W, R)
    end
    fcol(d, k) = parse.(Float64, d[k])
    f = readcsv(joinpath(refdir, "hainich_forcing_2010.csv"))
    ind = readcsv(joinpath(refdir, "hainich_individuals_2010.csv"))
    (sd, whcs, rdist) = readtable(joinpath(refdir, "hainich_soilcolumn.txt"))
    soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)
    n = length(f["doy"])
    forc = [
        DailyForcing{Float64}(
                swdown = fcol(f, "swdown")[i], lwnet = fcol(f, "lwnet")[i], temp = fcol(f, "temp")[i],
                precip = fcol(f, "precip")[i], daylength = fcol(f, "daylength")[i], co2 = fcol(f, "co2")[i],
            ) for i in 1:n
    ]
    patches = sort(unique(parse.(Int, ind["patch"])))
    prows = Dict(p => Int[] for p in patches)
    for r in eachindex(ind["patch"])
        push!(prows[parse(Int, ind["patch"][r])], r)
    end
    vv(r, k) = parse(Float64, ind[k][r])
    pft_intc(typ) = typ <= 3 ? 0.02 : (typ <= 6 ? 0.06 : 0.01)
    function pft_albedo(typ)
        typ == 1 && return (0.04, 0.1, 0.1); typ in (2, 3) && return (0.04, 0.1, 0.4)
        typ in (4, 5) && return (0.1, 0.1, 0.15); typ == 6 && return (0.05, 0.01, 0.15); return (0.15, 0.1, 0.4)
    end
    function mkind(r)
        typ = parse(Int, ind["type"][r]); isg = typ >= 7; sla = vv(r, "sla"); (ast, alt, scf) = pft_albedo(typ)
        Individual{Float64}(
            vv(r, "fpar_leafon"), vv(r, "fpc_ind"), vv(r, "alphaa"), vv(r, "albedo_leaf"), vv(r, "emax"),
            vv(r, "sapwood_c"), vv(r, "root_c"), vv(r, "lai"), pft_intc(typ), ast, alt, scf, vv(r, "nind"),
            FDiff.PhotoParams{Float64}(; path = :c3, issla = true, sla = sla),
            FDiff.TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), isg,
        )
    end

    p = tebs_params(); w = p.water
    ratios_gc = Float64[]; ratios_gpp = Float64[]; ratios_own = Float64[]
    for pnum in patches
        rows = prows[pnum]; inds = [mkind(r) for r in rows]; pids = [parse(Int, ind["type"][r]) for r in rows]
        uids = unique(pids); slot = Dict(id => k for (k, id) in enumerate(uids))
        pp = PhenParams{Float64}[pft_phenparams(id, Float64) for id in uids]
        ps = PhenState{Float64}[PhenState{Float64}() for _ in uids]; isg = Bool[_pft_is_grass(id) for id in uids]
        # the REAL state is evolved by daily_step_canopy (full transpiration withdrawal + soil evap → the true,
        # only-mildly-drying moist-Hainich soil trajectory); the read-only instrumented pass below measures
        # gp_stand + the grass gc/GPP from that same day's state (its infiltration → wr replicates daily_step_canopy).
        st = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0); wav = 1.0; glf = 1.0
        for fdc in forc
            phslot = _step_pft_phen_day!(ps, pp, isg, fdc.temp, fdc.swdown, wav, fdc.temp, glf)
            phen = Float64[phslot[slot[id]] for id in pids]
            beta = patch_albedo(inds, phen, st.snowpack)
            eeq = priestley_taylor_eeq(w, fdc.swdown, fdc.lwnet, fdc.temp, fdc.daylength, beta)
            frac_rain = FDiff.sigmoid(w.βsnow * (fdc.temp - w.tsnow)); rain = frac_rain * fdc.precip
            snowfall = (1 - frac_rain) * fdc.precip
            melt = smoothmin(w.melt_factor * softplus(fdc.temp - w.tsnow, w.βmelt), st.snowpack + snowfall, w.βmelt)
            interc = 0.0
            for (ii, iv) in enumerate(inds)
                (_, ic) = _wet_interc(iv.intc, iv.lai, _phen_at(phen, ii), iv.fpc, eeq, rain, w.α_PT); interc += ic
            end
            interc = smoothmin(interc, rain, w.βw); infil = rain + melt - interc
            (w1, _) = _infiltrate(st.w, soil.whcs, infil, w.βw)
            wr = 0.0; for l in eachindex(w1)
                wr += soil.rootdist[l] * (w1[l] / soil.whcs[l])
            end
            par = 0.5 * w.dayseconds * fdc.swdown; co2_Pa = ppm2Pa(fdc.co2); dl = fdc.daylength
            condfac = ppm2bar(fdc.co2) * (1 - w.lambda_opt) * hour2sec(dl)
            gp_acc = 0.0; fpc_tot = 0.0; gp_own = zeros(length(inds))
            for (ii, iv) in enumerate(inds)
                phi = _phen_at(phen, ii); fpc_i = iv.fpc * phi
                apar_gp = par * (1 - iv.albedo_leaf) * iv.alphaa * fpc_i
                tsi = temp_stress(iv.tstress, fdc.temp, dl)
                (_, _, _, adtmm) = photosynthesis(iv.photo, w.lambda_opt, tsi, co2_Pa, fdc.temp, apar_gp, dl; comp_vm = true)
                gp_i = 1.6 * adtmm / condfac + w.gmin * fpc_i; gp_own[ii] = gp_i; gp_acc += gp_i; fpc_tot += fpc_i
            end
            gp_stand = fpc_tot > 1.0e-20 ? gp_acc / fpc_tot : 0.0
            for (ii, iv) in enumerate(inds)
                (iv.is_grass && _phen_at(phen, ii) > 0.3 && gp_stand > 1.0e-6) || continue
                phi = _phen_at(phen, ii); fpc_i = iv.fpc * phi; fpar_i = iv.fpar * phi
                apar = par * (1 - iv.albedo_leaf) * iv.alphaa * fpar_i
                tsi = temp_stress(iv.tstress, fdc.temp, dl)
                (_, _, vm, _) = photosynthesis(iv.photo, w.lambda_opt, tsi, co2_Pa, fdc.temp, apar, dl; comp_vm = true)
                supply_i = iv.emax * wr * phi
                (wet_i, _) = _wet_interc(iv.intc, iv.lai, phi, iv.fpc, eeq, rain, w.α_PT); wet_dem = smoothmin(wet_i, 0.99, w.βw)
                function grass_gpp(gp_pot)
                    (gc, _) = canopy_conductance(w, eeq, gp_pot, supply_i; wet = wet_dem)
                    gpd = softplus(hour2sec(dl) * (gc * fpc_i - w.gmin * fpar_i), w.βflux)
                    fac = gpd / 1.6 * ppm2bar(fdc.co2)
                    p_i = FDiffParams{Float64}(iv.photo, iv.tstress, w, p.resp, p.allom, p.nlambda, p.ω)
                    λ = clamp(solve_lambda(p_i, fac, tsi, co2_Pa, fdc.temp, apar, dl, vm), _LAMBDA_LO, _LAMBDA_HI)
                    (agd, _, _, _) = photosynthesis(iv.photo, λ, tsi, co2_Pa, fdc.temp, apar, dl; comp_vm = false, vm = vm)
                    (gc, softplus(agd, w.βflux))
                end
                (gc_stand, gpp_stand) = grass_gpp(gp_stand)
                (_, gpp_pp) = grass_gpp(gp_own[ii])      # per-PFT: cap at the grass's OWN potential gp
                push!(ratios_gc, gc_stand / gp_stand); push!(ratios_own, gp_own[ii] / gp_stand)
                gpp_stand > 1.0e-9 && push!(ratios_gpp, abs(gpp_pp - gpp_stand) / gpp_stand)
            end
            # advance the REAL state (full transpiration withdrawal + soil evap) and carry the water-phenology
            # feedback, so the soil water follows the true physics (moist Hainich soil, wscal ~0.99).
            (st, fl) = daily_step_canopy(p, inds, soil, st, fdc; phen = phen)
            wav = fl.wscal
            absorbed = 0.0
            for (ii, iv) in enumerate(inds)
                iv.is_grass || (absorbed += iv.fpar * _phen_at(phen, ii))
            end
            glf = clamp(1 - absorbed, 0.0, 1.0)
        end
    end
    _mean(x) = sum(x) / length(x)
    @test !isempty(ratios_gc)
    # F_diff's grass GPP uses the STAND-MEAN conductance (measured mean gc/gp_stand ~0.75 — the moist Hainich
    # soil, growing-season wscal ~0.99, keeps it only mildly water-limited), EXACTLY as the C's water_stressed.c
    # returns grass GPP from gp_stand. So F_diff already matches the C here; it is NOT under-supplying, and (by
    # testitem 1) the resulting grass NPP is faithful. The grass's OWN potential gp is only ~0.14·gp_stand.
    @test _mean(ratios_gc) > 0.5                         # grass uses (most of) the stand mean, like the C
    @test _mean(ratios_own) < 0.25                       # the grass's own gp is a small fraction of the stand mean
    # recomputing grass GPP with a PER-PFT (own-gp) conductance instead of gp_stand changes it SUBSTANTIALLY
    # (measured mean ~0.43) — a large de-calibration AWAY from the C-faithful gp_stand value. So per-PFT
    # conductance is the WRONG fix: the C uses gp_stand (finding 1), the grass NPP is already faithful
    # (testitem 1), and per-PFT would cut the grass GPP and degrade the validated tree GPP too.
    @test _mean(ratios_gpp) > 0.2
end

@testitem "Grass re-diagnosis (3) — self-driven grass over-grows without cover competition (the corrected next step)" tags = [:validation, :fdiff, :canopy, :grass, :structure] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: grass_treepools, tebs_allocparams, tebs_params, rollout_canopy_years, hainich_soilcolumn
    using LPJmLFITEmulator.Allometry
    using Test

    soil = hainich_soilcolumn(;
        whcs = [37.0, 53.0, 88.0, 175.0, 175.0], rootdist = [0.41, 0.32, 0.2, 0.07, 0.0],
        soildepth = [200.0, 300.0, 500.0, 1000.0, 1000.0],
    )
    allom = Allometry.TreeAllometry{Float64}(); alloc = tebs_allocparams(); phys = tebs_params()
    mktree(leaf, sap, heart, root, h, ca, nind) = TreePools{Float64}(leaf, sap, heart, root, h, ca, nind, 0.01986, 2.0e5, false)
    mktmpl(fpar, sla, isg) = Individual{Float64}(
        fpar, 0.0, isg ? 0.5 : 0.55, isg ? 0.23 : 0.15, 10.0, 0.0, 0.0, 0.0, isg ? 0.01 : 0.02, isg ? 0.15 : 0.04, 0.1, 0.4, isg ? 1.0 : 1 / 225,
        FDiff.PhotoParams{Float64}(; path = :c3, issla = true, sla = sla),
        FDiff.TempStressParams{Float64}(; temp_photos_low = (isg ? 10.0 : 20.0), temp_photos_high = 30.0), isg,
    )
    # a tree + an understory grass started at the C's suppressed value (leaf 6.4). Self-driven, WITHOUT the
    # C's grass cover/light competition (light.c → light_grass.c), the leaf→lai→forest-floor-fpar→NPP
    # positive feedback grows the grass leaf far past the C's understory value.
    trees0 = [mktree(2769.0, 33000.0, 120000.0, 2769.0, 12.0, 15.8, 1 / 225), grass_treepools(6.406, 6.406 + 8.023, 0.042242)]
    tmpls = [mktmpl(0.4, 0.01986, false), mktmpl(0.03, 0.042242, true)]
    gidx = 2; ndays = 40
    forc = [DailyForcing{Float64}(swdown = 250.0, lwnet = -45.0, temp = 17.0, precip = (d % 4 == 0 ? 8.0 : 0.4), daylength = 14.0, co2 = 380.0) for d in 1:ndays]
    st0 = FDiffStateML{Float64}([0.7 * wc for wc in soil.whcs], 0.0)
    (_, _, pools_by_year, _) = rollout_canopy_years(phys, alloc, allom, st0, trees0, tmpls, soil, [forc for _ in 1:8])
    leaf0 = trees0[gidx].leaf_c; leafN = pools_by_year[end][gidx].leaf_c
    @test isfinite(leafN) && leafN > 0
    # over-grows well past the start (the missing suppression is grass cover/light competition, NOT per-PFT
    # conductance) — the corrected roadmap item. (A sparse well-lit patch shows the over-growth most clearly.)
    @test leafN > 2.0 * leaf0
end
