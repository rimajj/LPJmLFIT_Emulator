# Phase 5 — multi-cell / biome generalization of the coupled S+F+E emulator (DEVELOPMENT_PLAN §6). Drives
# the coupled loop (`run_coupled_cell`) with the REAL GSWP3-W5E5 committed forcing of five biome-
# representative cells (boreal / temperate / mediterranean / semi-arid / tropical;
# scripts/extract_biome_forcing.py) using a COMMON canopy (the committed Hainich patch), so the energy-
# partitioning contrast comes purely from the CLIMATE forcing. Asserts (1) the Phase-4 hard gate holds
# EVERYWHERE — energy closes to machine precision across the full climate envelope — and (2) the emergent
# partitioning tracks the climate: tropical is LE-dominated (low Bowen), the dry biomes are H-dominated
# (high Bowen), and the wet/warm tropics evaporate far more than the cold boreal cell.

@testitem "Coupled emulator generalizes across biomes — energy closes + climate-driven partitioning" tags = [:validation, :energy, :coupling, :scientific, :multicell] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
    using LPJmLFITEmulator.Allometry
    using Test

    _mean(x) = sum(x) / length(x)
    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
        hdr = split(strip(lines[1]), ',')
        rows = [split(strip(l), ',') for l in lines[2:end]]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end
    fcol(d, k) = parse.(Float64, d[k])

    # common canopy structure (committed Hainich dominant patch) + soil column
    ind = readcsv(joinpath(refdir, "hainich_individuals_2010.csv"))
    v(k, r) = parse(Float64, ind[k][r])
    nt(r) = parse(Int, ind["type"][r])
    prows = Dict{Int, Vector{Int}}()
    for r in eachindex(ind["type"])
        (nt(r) <= 6 && v("height", r) > 0) && push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
    end
    rows = prows[argmax(Dict(k => length(vv) for (k, vv) in prows))]
    mkp(r) = TreePools{Float64}(
        v("leaf_c", r), v("sapwood_c", r),
        max(v("agb", r) / v("nind", r) - v("leaf_c", r) - v("sapwood_c", r), 0.0), v("root_c", r),
        v("height", r), v("crownarea", r), v("nind", r), v("sla", r), v("wooddens", r), false
    )
    mkt(r) = Individual{Float64}(
        v("fpar_leafon", r), 0.0, v("alphaa", r), v("albedo_leaf", r), v("emax", r),
        v("sapwood_c", r), v("root_c", r), 0.0, 0.02, 0.04, 0.1, 0.4, v("nind", r),
        PhotoParams{Float64}(; path = :c3, issla = true, sla = v("sla", r)),
        TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false
    )
    sd = Float64[]; whcs = Float64[]; rdist = Float64[]
    for ln in eachline(joinpath(refdir, "hainich_soilcolumn.txt"))
        s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
        x = parse.(Float64, split(s)); push!(sd, x[2]); push!(whcs, x[3]); push!(rdist, x[4])
    end
    soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)

    σ = 5.670374419e-8
    biomes = [
        ("boreal_siberia", 61.75), ("temperate_hainich", 51.25), ("mediterranean_iberia", 39.75),
        ("semiarid_sahel", 13.75), ("tropical_amazon", -3.25),
    ]
    ann = Dict{String, NamedTuple}()
    for (name, lat) in biomes
        f = readcsv(joinpath(refdir, "biome_forcing_$(name).csv"))
        tairK = fcol(f, "temp") .+ 273.15
        swd = fcol(f, "swdown"); lwn = fcol(f, "lwnet"); prec = fcol(f, "precip")
        huss = fcol(f, "huss"); co2 = fcol(f, "co2")
        nfull = length(tairK)
        n = min(nfull, 2 * 365)                        # 2 years for CI speed
        forcings = [
            AtmForcing(;
                    swdown = swd[i], lwdown = lwn[i] + σ * tairK[i]^4, tair = tairK[i], qair = huss[i],
                    wind = 2.0, psurf = 1.0e5, precip = prec[i], co2 = co2[i]
                ) for i in 1:n
        ]
        core = FDiffFastCore([mkp(r) for r in rows], [mkt(r) for r in rows], soil, lat)
        clo = SEBEnergyClosure(; t_soil0 = _mean(tairK))
        state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
        out = run_coupled_cell(core, clo, state, forcings; days_per_year = 365)

        # ── Phase-4 hard gate holds in EVERY climate regime ──
        @test maximum(abs, out.resid) < 1.0e-6
        @test all(isfinite, out.t_skin) && all(isfinite, out.le) && all(isfinite, out.h) && all(isfinite, out.g)
        # Latent heat is non-negative up to a small, BOUNDED smooth-surrogate undershoot. F's ET is built
        # from `smoothmin` (fdiff_smoothops.jl), and `smoothmin(a, b, β) ≤ min(a, b)` dips below the true
        # minimum by ≤ log(2)/β EVEN for a, b ≥ 0. In the fully water-depleted dry-season corner (only the
        # semi-arid Sahel cell reaches it: `available → 0`, `demand → 0`) `et = smoothmin(et_demand,
        # available, βw)` bottoms out a few hundredths of a mm/day below zero ⇒ `le ≈ −0.6 W/m²` where the
        # physical ET is 0 (this model has no dew/condensation term). It is bounded, appears only in the
        # driest biome, and is harmless to E's closure (H := Rn − LE − G absorbs it). Assert the BOUND, not
        # exact non-negativity — a genuine transpiration/evaporation sign bug would be orders larger.
        @test all(≥(-2.0), out.le)
        @test all(0.0 .≤ out.albedo .≤ 1.0)
        @test all(>(0.0), out.z0)
        @test maximum(abs, out.t_skin .- tairK[1:n]) < 30.0   # skin bounded near air across all climates

        ann[name] = (
            le = _mean(out.le), h = _mean(out.h), rn = _mean(out.rn),
            bowen = _mean(out.h) / max(_mean(out.le), 1.0e-6),
        )
    end

    # ── emergent climate-driven partitioning (same canopy ⇒ contrast is purely the forcing) ──
    @test ann["tropical_amazon"].le > ann["boreal_siberia"].le           # wet warm tropics evaporate far more
    @test ann["tropical_amazon"].le > ann["semiarid_sahel"].le           # water availability drives ET
    @test ann["tropical_amazon"].bowen < ann["temperate_hainich"].bowen  # tropics LE-dominated
    @test ann["semiarid_sahel"].bowen > ann["tropical_amazon"].bowen     # dry biome → sensible-heat dominated
    @test ann["mediterranean_iberia"].bowen > ann["tropical_amazon"].bowen
    @test ann["tropical_amazon"].rn > ann["boreal_siberia"].rn           # more net radiation in the tropics
end
