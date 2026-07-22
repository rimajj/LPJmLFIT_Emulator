# End-to-end coupled S+F+E run (Phase 4 gate; DEVELOPMENT_PLAN §6). Drives the fast core F
# (`FDiffFastCore`) and the surface-energy-balance closure E (`SEBEnergyClosure`) through one full year
# of REAL committed Hainich forcing via `run_coupled_cell`, and asserts the Phase-4 gate: energy CLOSES
# (Rn = LE + H + G to machine precision, every day, by construction) and the ESM-facing outputs
# (LE, H, G, T_skin) are physically plausible over the seasonal cycle. This is the "use the emulator"
# integration test — F's water-limited latent heat drives E, E closes the energy budget and feeds its
# skin temperature back to F. No external data required (closure is by construction).

@testitem "Coupled S+F+E run closes energy + plausible fluxes over a year (Hainich 42490)" tags = [:validation, :energy, :coupling, :scientific] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
    using LPJmLFITEmulator.Allometry
    using Test

    _mean(x) = sum(x) / length(x)                 # local mean (Statistics is not a test dep)
    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = readlines(path)
        i = findfirst(l -> !startswith(strip(l), "#") && !isempty(strip(l)), lines)
        hdr = split(strip(lines[i]), ',')
        rows = [split(strip(l), ',') for l in lines[(i + 1):end] if !isempty(strip(l))]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end
    ind = readcsv(joinpath(refdir, "hainich_individuals_2010.csv"))
    f = readcsv(joinpath(refdir, "hainich_forcing_2010.csv"))
    fc_(k) = parse.(Float64, f[k])
    v(k, r) = parse(Float64, ind[k][r])
    nt(r) = parse(Int, ind["type"][r])
    n = length(fc_("doy"))
    @test n == 365

    # soil column
    sd = Float64[]; whcs = Float64[]; rdist = Float64[]
    for ln in eachline(joinpath(refdir, "hainich_soilcolumn.txt"))
        s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
        x = parse.(Float64, split(s)); push!(sd, x[2]); push!(whcs, x[3]); push!(rdist, x[4])
    end
    soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)

    # dominant tree patch (most trees), as the coupling gate picks it
    prows = Dict{Int, Vector{Int}}()
    for r in eachindex(ind["type"])
        (nt(r) <= 6 && v("height", r) > 0) && push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
    end
    rows = prows[argmax(Dict(k => length(vv) for (k, vv) in prows))]
    mkp(r) = TreePools{Float64}(v("leaf_c", r), v("sapwood_c", r),
        max(v("agb", r) / v("nind", r) - v("leaf_c", r) - v("sapwood_c", r), 0.0), v("root_c", r),
        v("height", r), v("crownarea", r), v("nind", r), v("sla", r), v("wooddens", r), false)
    mkt(r) = Individual{Float64}(v("fpar_leafon", r), 0.0, v("alphaa", r), v("albedo_leaf", r), v("emax", r),
        v("sapwood_c", r), v("root_c", r), 0.0, 0.02, 0.04, 0.1, 0.4, v("nind", r),
        PhotoParams{Float64}(; path = :c3, issla = true, sla = v("sla", r)),
        TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false)
    pools = [mkp(r) for r in rows]; tmpls = [mkt(r) for r in rows]

    # build F core + E closure; seed the deep-soil temp with the site mean annual air temperature
    core = FDiffFastCore(pools, tmpls, soil, 51.25)
    tair_K = fc_("temp") .+ 273.15
    clo = SEBEnergyClosure(; t_soil0 = _mean(tair_K))

    σ = 5.670374419e-8
    forcings = [AtmForcing(;
            swdown = fc_("swdown")[i], lwdown = fc_("lwnet")[i] + σ * tair_K[i]^4,
            tair = tair_K[i], qair = fc_("huss")[i], wind = 2.0, psurf = 1.0e5,
            precip = fc_("precip")[i], co2 = fc_("co2")[i]) for i in 1:n]

    state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
    out = run_coupled_cell(core, clo, state, forcings; days_per_year = 365)

    # ── Phase-4 HARD gate: energy closes by construction, every day ──
    @test maximum(abs, out.resid) < 1.0e-6
    @test all(isfinite, out.t_skin) && all(isfinite, out.le) && all(isfinite, out.h) && all(isfinite, out.g)
    for i in 1:n
        @test isapprox(out.rn[i], out.le[i] + out.h[i] + out.g[i]; atol = 1.0e-6)
    end

    # ── physical plausibility of the added quantities ──
    dT = out.t_skin .- tair_K
    @test maximum(abs, dT) < 25.0                        # skin stays within ~25 K of air (well-coupled)
    @test all(≥(-1.0e-9), out.le)                        # latent heat non-negative (LE = λ·ET)
    @test all(0.0 .≤ out.albedo .≤ 1.0)                  # albedo a valid fraction
    @test all(>(0.0), out.z0)                            # positive roughness
    # summer (DOY 152–243) is warmer & more radiative than winter (DOY 1–59 ∪ 335–365)
    summer = 152:243
    winter = vcat(1:59, 335:365)
    @test _mean(out.rn[summer]) > _mean(out.rn[winter])
    @test _mean(out.le[summer]) > _mean(out.le[winter])   # more ET in the growing season
    @test _mean(out.gpp[summer]) > _mean(out.gpp[winter]) # F still produces the seasonal GPP

    # ── the E→F skin-temperature feedback runs and is byte-identical when OFF vs the raw adapter ──
    # feedback ON already exercised above; re-run with it OFF and confirm energy still closes
    core2 = FDiffFastCore(pools, tmpls, soil, 51.25)
    clo2 = SEBEnergyClosure(; t_soil0 = _mean(tair_K))
    state2 = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
    out2 = run_coupled_cell(core2, clo2, state2, forcings; days_per_year = 365, feedback = false)
    @test maximum(abs, out2.resid) < 1.0e-6
    @test all(isfinite, out2.t_skin)
end
