# The C-faithful POTENTIAL leaf-on water scalar (line M, ADR 0051) — `WaterParams.wscal_leafon`.
#
# `wscal_mean` is consumed TWICE: it is Component S's `water_stress` conditioning feature AND the F core's
# leaf:root allocation driver `lmtorm` (`allocation_tree.c:233`). Through ADR 0050 F_diff formed the daily
# `wscal` as the REALIZED `min(1, Σsupply·fpc / Σdemand·fpc)`, but the C's `pft->wscal`
# (`water_stressed.c:130-138`) is a POTENTIAL, phenology-INDEPENDENT index:
#     wscal = (eeq>0 && gp_stand_leafon>0 && fpc>0) ?
#             min(1, emax·wr / (eeq·ALPHAM/(1 + GM·ALPHAM/gp_stand_leafon))) : 1
# with `gp_stand_leafon` the conductance at FULL leaf cover, FPC-normalized by the PLAIN Σfpc
# (`gp_sum.c:57-67`). Three differences, all biasing the annual mean the same way: no `phen` in the
# numerator (F_diff's carried it SQUARED), no `(1−wet)` and the leaf-on conductance in the denominator,
# and `wscal = 1` (UNSTRESSED) on a no-demand day where the realized ratio degenerates to 0.
#
# These assertions encode the C's SEMANTICS, not fitted numbers: phenology-independence, the no-demand
# branch, the cap — plus the end-to-end consequence, that the annual `1 − wscal_mean` at Hainich lands
# inside the committed demo artifact's own trained `water_stress` band while the default does not. All
# fixtures are committed, so this runs on a CI runner with no cluster.

@testitem "wscal_leafon reproduces the C's POTENTIAL leaf-on water scalar (ADR 0051)" tags = [:validation, :fdiff] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: WaterParams, PhotoParams, TempStressParams
    using Test

    # ── (0) the OPT-IN guarantee (guardrail 4): default off, so every committed baseline is untouched ──
    @test WaterParams{Float64}().wscal_leafon === false

    w_lo = WaterParams{Float64}(; wscal_leafon = true)

    ind(fpc; emax = 10.0) = FDiff.Individual{Float64}(
        0.5, fpc, 0.5, 0.1, emax, 100.0, 50.0, 0.0, 2.0, 0.02, 0.04, 0.1, 0.4, 0.02,
        PhotoParams{Float64}(; path = :c3, issla = true, sla = 20.0),
        TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false,
    )
    inds = [ind(0.4), ind(0.3; emax = 12.9)]

    # ── (1) the C's `else wscal = 1` branch — a no-demand day is UNSTRESSED, not maximally stressed ──
    # This is the branch the realized ratio scored as ~0 (`supply/(demand+1e-9)` with supply → 0 faster).
    @test FDiff._wscal_leafon(w_lo, inds, 0.0, 0.5, 3.0, 0.7) == 1.0        # eeq = 0
    @test FDiff._wscal_leafon(w_lo, inds, 4.0, 0.5, 0.0, 0.7) == 1.0        # gp_stand_leafon = 0
    @test FDiff._wscal_leafon(w_lo, inds, 4.0, 0.5, 3.0, 0.0) == 1.0        # no canopy at all

    # ── (2) it is a RATIO capped at 1, and it falls monotonically as the soil dries ──
    dry = FDiff._wscal_leafon(w_lo, inds, 6.0, 0.02, 3.0, 0.7)
    mid = FDiff._wscal_leafon(w_lo, inds, 6.0, 0.1, 3.0, 0.7)
    wet = FDiff._wscal_leafon(w_lo, inds, 6.0, 0.9, 3.0, 0.7)
    @test 0.0 < dry < mid < wet ≤ 1.0
    @test wet ≈ 1.0 rtol = 1.0e-6                       # ample supply ⇒ the `min(...,1)` cap binds

    # ── (3) PHENOLOGY-INDEPENDENCE — the property that distinguishes the two definitions. The C's wscal
    #        has no `phen`, so scaling leaf display must NOT move it; the realized ratio collapses. ──
    nlay = LPJmLFITEmulator.NSOILLAYER
    soil = hainich_soilcolumn(;
        whcs = fill(50.0, nlay), rootdist = fill(1 / nlay, nlay), soildepth = fill(500.0, nlay),
    )
    pools = [FDiff.TreePools{Float64}(120.0, 900.0, 3000.0, 260.0, 22.0, 12.0, 0.02, 20.0, 2.0e5, false)]
    tmpls = [ind(0.0)]
    forc = FDiff.DailyForcing(; swdown = 220.0, lwnet = -55.0, temp = 18.0, precip = 1.5, daylength = 14.0, co2 = 369.0)
    # A DRY column on purpose: at `w = 0.6` BOTH definitions sit on the `min(…,1)` cap (supply ≫ demand) and
    # are indistinguishable — the contrast below can only be measured where the ratio is off the cap.
    st = FDiff.FDiffStateML{Float64}(fill(0.05, length(soil.whcs)) .* soil.whcs, 0.0)

    function wscal_at(phen, leafon)
        p = FDiff.tebs_params(Float64)
        wp = p.water
        fns = fieldnames(typeof(wp))
        nt = NamedTuple{fns}(map(f -> getfield(wp, f), fns))
        p2 = FDiff.FDiffParams{Float64}(
            p.photo, p.tstress, typeof(wp)(; merge(nt, (; wscal_leafon = leafon))...),
            p.resp, p.allom, p.nlambda, p.ω,
        )
        core = FDiffFastCore(pools, tmpls, soil, 51.25; params = p2)
        (_, fl) = FDiff.daily_step_canopy(p2, core.inds, soil, st, forc; phen = [phen])
        return fl.wscal
    end

    full_lo, half_lo = wscal_at(1.0, true), wscal_at(0.5, true)
    full_df, half_df = wscal_at(1.0, false), wscal_at(0.5, false)
    # Both definitions are OFF the cap here, so the sensitivities are measurable and comparable.
    @test 0.0 < full_lo < 1.0 && 0.0 < full_df < 1.0
    sens_lo = abs(full_lo - half_lo) / full_lo
    sens_df = abs(full_df - half_df) / full_df
    # The C's form is phen-independent up to a SECOND-ORDER path only: leaf display moves the canopy
    # albedo, which moves `eeq`, which moves the leaf-on demand. That residual is ~0.8 % here and is
    # legitimate (the C's `eeq` is albedo-dependent too), so the honest assertion is the CONTRAST —
    # halving leaf display barely moves the C's index and collapses the realized ratio (~62 %).
    @test sens_lo < 0.03
    @test sens_df > 0.4
    @test sens_df > 10 * sens_lo

    # ── the no-demand branch, at phen EXACTLY 0 — the C gates on `Σ gp_leafon·phen < 1e-20`, which only
    #    a genuinely leafless canopy reaches. At phen = 1e-8 the C still evaluates the ratio, so the C's
    #    index must stay at its leaf-on value there — a second, sharper phen-independence check. ──
    @test wscal_at(0.0, true) == 1.0                  # UNSTRESSED, per `water_stressed.c:137`
    @test abs(wscal_at(1.0e-8, true) - full_lo) / full_lo < 0.03
    @test wscal_at(0.0, false) < 1.0e-3               # the realized ratio: maximal stress instead
    @test wscal_at(1.0e-8, false) < 1.0e-3

    # ── (4) the assertions above CAN fail, i.e. the flag is genuinely wired (residual-diagnosis §3e) ──
    @test !(full_lo ≈ full_df)
end

@testitem "wscal_leafon puts Hainich's annual water_stress inside the C-trained band (ADR 0051)" tags = [
    :validation, :coupling, :multicell,
] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: WaterParams, PhotoParams, TempStressParams
    using Test
    _mean(x) = sum(x) / length(x)          # `Statistics` is not in the test env (sibling convention)

    refdir = joinpath(@__DIR__, "references")
    σ = 5.670374419e-8

    function readcsv(path)
        lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
        hdr = split(strip(lines[1]), ',')
        rows = [split(strip(l), ',') for l in lines[2:end]]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end
    fcol(d, k) = parse.(Float64, d[k])

    # the trained `water_stress` band the demo artifact itself carries (ADR 0034 §2 shipped feat_min/max)
    lo = hi = NaN
    cn = String[]
    for ln in eachline(joinpath(refdir, "drf_forest_hainich_meta.txt"))
        p = split(ln, '\t')
        length(p) < 2 && continue
        p[1] == "colnames" && (cn = String.(split(strip(p[2]))))
        p[1] == "feat_min" && (lo = parse.(Float64, split(strip(p[2])))[3])
        p[1] == "feat_max" && (hi = parse.(Float64, split(strip(p[2])))[3])
    end
    @test cn[3] == "water_stress"          # the band we read really is this column
    @test 0.0 ≤ lo < hi < 0.1              # Hainich is essentially UNSTRESSED in the C

    ind = readcsv(joinpath(refdir, "M_individuals_temperate_hainich_2010.csv"))
    v(k, r) = parse(Float64, ind[k][r])
    prows = Dict{Int, Vector{Int}}()
    for r in eachindex(ind["type"])
        (parse(Int, ind["type"][r]) <= 6 && v("height", r) > 0) &&
            push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
    end
    rows = prows[argmax(Dict(k => length(vv) for (k, vv) in prows))]
    pools = [
        FDiff.TreePools{Float64}(
                v("leaf_c", r), v("sapwood_c", r),
                max(v("agb", r) / v("nind", r) - v("leaf_c", r) - v("sapwood_c", r), 0.0), v("root_c", r),
                v("height", r), v("crownarea", r), v("nind", r), v("sla", r), v("wooddens", r), false
            ) for r in rows
    ]
    tmpls = [
        FDiff.Individual{Float64}(
                v("fpar_leafon", r), 0.0, v("alphaa", r), v("albedo_leaf", r), v("emax", r),
                v("sapwood_c", r), v("root_c", r), 0.0, 0.02, 0.04, 0.1, 0.4, v("nind", r),
                PhotoParams{Float64}(; path = :c3, issla = true, sla = v("sla", r)),
                TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false
            ) for r in rows
    ]

    sd = Float64[]; whcs = Float64[]; rdist = Float64[]
    for ln in eachline(joinpath(refdir, "M_soilcolumn_temperate_hainich.txt"))
        s = strip(ln)
        (isempty(s) || startswith(s, "#")) && continue
        x = parse.(Float64, split(s))
        push!(sd, x[2]); push!(whcs, x[3]); push!(rdist, x[4])
    end
    soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)

    f = readcsv(joinpath(refdir, "biome_forcing_temperate_hainich.csv"))
    tairK = fcol(f, "temp") .+ 273.15
    swd = fcol(f, "swdown"); lwn = fcol(f, "lwnet"); prec = fcol(f, "precip")
    huss = fcol(f, "huss"); co2 = fcol(f, "co2")
    nday = min(length(tairK), 3 * 365)          # 3 years is enough for the annual mean; keeps CI cheap
    forc = [
        AtmForcing(;
                swdown = swd[i], lwdown = lwn[i] + σ * tairK[i]^4, tair = tairK[i], qair = huss[i],
                wind = 2.0, psurf = 1.0e5, precip = prec[i], co2 = co2[i]
            ) for i in 1:nday
    ]

    "Annual `water_stress = 1 − wscal_mean` for each year, straight off the fast core's own accumulator."
    function annual_water_stress(leafon)
        p = FDiff.tebs_params(Float64)
        wp = p.water
        fns = fieldnames(typeof(wp))
        nt = NamedTuple{fns}(map(fn -> getfield(wp, fn), fns))
        p2 = FDiff.FDiffParams{Float64}(
            p.photo, p.tstress, typeof(wp)(; merge(nt, (; wscal_leafon = leafon))...),
            p.resp, p.allom, p.nlambda, p.ω,
        )
        core = FDiffFastCore(pools, tmpls, soil, 51.25; params = p2)
        clo = SEBEnergyClosure(; t_soil0 = _mean(tairK))
        state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
        bc_f = LPJmLFITEmulator.stand_structure_tof(core)
        ws = Float64[]
        for (i, fr) in enumerate(forc)
            LPJmLFITEmulator.couple_day!(core, clo, state, bc_f, fr; feedback = true)
            if i % 365 == 0
                push!(ws, 1.0 - core.wscal_acc / core.nday)
                LPJmLFITEmulator.annual_step!(core, state)
            end
        end
        return ws
    end

    ws_lo = annual_water_stress(true)
    ws_df = annual_water_stress(false)
    @test length(ws_lo) == 3 && length(ws_df) == 3

    # THE GATE: the C-faithful definition lands inside the C's own trained band for this cell...
    @test all(x -> lo - 1.0e-12 ≤ x ≤ hi, ws_lo)
    # ...and the realized-ratio default does NOT — it exceeds the band by MANY band widths (ADR 0034 §1).
    @test all(>(hi + 5 * (hi - lo)), ws_df)
end
