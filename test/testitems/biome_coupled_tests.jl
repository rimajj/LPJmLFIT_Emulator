# Multi-cell / biome generalization of the coupled S+F+E emulator (line M, milestone M1 — per-cell input
# provisioning). Drives the coupled loop (`run_coupled_cell`) with the REAL GSWP3-W5E5 committed forcing of
# five biome-representative cells (boreal / temperate / mediterranean / semi-arid / tropical), each now with
# ITS OWN soil column and ITS OWN reconstructed canopy:
#   references/M_cells.csv                    cell index + latitude (global run's grid.nc `cellid`)
#   references/M_soilcolumn_<name>.txt        scripts/extract_cell_soilcolumn.py
#   references/M_individuals_<name>_2010.csv  scripts/extract_cell_individuals.py
#   references/biome_forcing_<name>.csv       scripts/extract_biome_forcing.py
# Before M1 all five cells reused Hainich's soil and Hainich's canopy (deliberately, to isolate the climate
# effect). Asserts (1) the per-cell inputs are well-formed AND genuinely distinct — the regression guard
# against silently falling back to one cell's inputs, (2) the Phase-4 hard gate still holds EVERYWHERE with
# per-cell vegetation — energy closes to machine precision across the full climate envelope, and (3) the
# emergent partitioning still tracks the climate: tropical is LE-dominated (low Bowen), the dry biomes are
# H-dominated (high Bowen), and the wet/warm tropics evaporate far more than the cold boreal cell.

@testitem "Per-cell soil columns + canopies are well-formed and genuinely distinct" tags = [:validation, :coupling, :multicell] begin
    using LPJmLFITEmulator
    using Test

    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
        hdr = split(strip(lines[1]), ',')
        rows = [split(strip(l), ',') for l in lines[2:end]]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end
    function readsoil(path)
        sd = Float64[]; whcs = Float64[]; rd = Float64[]
        for ln in eachline(path)
            s = strip(ln)
            (isempty(s) || startswith(s, "#")) && continue
            x = parse.(Float64, split(s))
            push!(sd, x[2]); push!(whcs, x[3]); push!(rd, x[4])
        end
        return sd, whcs, rd
    end

    cells = readcsv(joinpath(refdir, "M_cells.csv"))
    names = String.(cells["name"])
    @test length(names) == 5
    @test Set(parse.(Int, cells["cell"])) == Set([52059, 42490, 33335, 18371, 12045])
    # latitudes come from grid.nc `cellid`, not a hand-typed list
    @test parse(Float64, cells["lat"][findfirst(==("temperate_hainich"), names)]) == 51.25
    @test parse(Float64, cells["lon"][findfirst(==("temperate_hainich"), names)]) == 10.25

    # LPJmL-FIT's cell-invariant layering (par/soil_20m.js) — the same for every cell
    soildepth_C = vcat([200.0, 300.0, 500.0], fill(1000.0, 19), [3000.0])
    whcs_all = Vector{Float64}[]; rd_all = Vector{Float64}[]
    for name in names
        sd, whcs, rd = readsoil(joinpath(refdir, "M_soilcolumn_$(name).txt"))
        @test length(sd) == LPJmLFITEmulator.NSOILLAYER
        @test sd == soildepth_C
        # a zero whcs would make F_diff's `rel = w / whcs` NaN and poison SharedState.w
        @test all(>(0.0), whcs)
        # F_diff's water supply scales LINEARLY with sum(rootdist), and `stand_structure_tof`'s
        # D95 loop never terminates below 0.95 — so the profile must be normalized. The extractor
        # normalizes exactly; the tolerance is the `%.6f` print rounding of 23 values (≤ 1.15e-5).
        @test all(≥(0.0), rd)
        @test isapprox(sum(rd), 1.0; atol = 2.0e-5)
        push!(whcs_all, whcs); push!(rd_all, rd)
    end

    # ── genuinely per-cell: every pair of cells differs in BOTH soil water and rooting ──
    for i in 1:length(names), j in (i + 1):length(names)
        @test whcs_all[i] != whcs_all[j]
        @test rd_all[i] != rd_all[j]
    end

    # ── the emergent rooting gradient (FIT's own trait distributions, not a tuned input) ──
    idx = Dict(n => k for (k, n) in enumerate(names))
    top1m(n) = sum(rd_all[idx[n]][1:3])
    @test top1m("semiarid_sahel") > top1m("temperate_hainich")   # semi-arid = shallow-rooted
    @test top1m("temperate_hainich") > top1m("tropical_amazon")  # tropical = deep-rooted
    @test top1m("mediterranean_iberia") < top1m("boreal_siberia")  # summer-dry => deeper roots
    # Hainich's plant-available water is unchanged from the committed column it was derived from
    _, whcs_ref, _ = readsoil(joinpath(refdir, "hainich_soilcolumn.txt"))
    @test whcs_all[idx["temperate_hainich"]] == whcs_ref

    # ── per-cell canopies: distinct individual sets, each with its own reconstructed light shares ──
    ninds = Int[]
    for name in names
        ind = readcsv(joinpath(refdir, "M_individuals_$(name)_2010.csv"))
        n = length(ind["type"])
        @test n > 0
        @test all(0.0 .≤ parse.(Float64, ind["fpar_leafon"]) .≤ 1.0)
        @test any(parse.(Int, ind["type"]) .≤ 6)                # at least one tree
        push!(ninds, n)
    end
    @test length(unique(ninds)) > 1                             # not one canopy copied five times
end

@testitem "Coupled emulator generalizes across biomes with PER-CELL inputs — energy closes + climate-driven partitioning" tags = [:validation, :energy, :coupling, :scientific, :multicell] begin
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

    function readsoil(path)
        sd = Float64[]; whcs = Float64[]; rd = Float64[]
        for ln in eachline(path)
            s = strip(ln)
            (isempty(s) || startswith(s, "#")) && continue
            x = parse.(Float64, split(s))
            push!(sd, x[2]); push!(whcs, x[3]); push!(rd, x[4])
        end
        return hainich_soilcolumn(; whcs = whcs, rootdist = rd, soildepth = sd)
    end

    "Dominant patch (most living trees) of a reconstructed individual set → (pools, templates)."
    function readcanopy(path)
        ind = readcsv(path)
        v(k, r) = parse(Float64, ind[k][r])
        nt(r) = parse(Int, ind["type"][r])
        prows = Dict{Int, Vector{Int}}()
        for r in eachindex(ind["type"])
            (nt(r) <= 6 && v("height", r) > 0) && push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
        end
        rows = prows[argmax(Dict(k => length(vv) for (k, vv) in prows))]
        pools = [
            TreePools{Float64}(
                    v("leaf_c", r), v("sapwood_c", r),
                    max(v("agb", r) / v("nind", r) - v("leaf_c", r) - v("sapwood_c", r), 0.0), v("root_c", r),
                    v("height", r), v("crownarea", r), v("nind", r), v("sla", r), v("wooddens", r), false
                ) for r in rows
        ]
        tmpls = [
            Individual{Float64}(
                    v("fpar_leafon", r), 0.0, v("alphaa", r), v("albedo_leaf", r), v("emax", r),
                    v("sapwood_c", r), v("root_c", r), 0.0, 0.02, 0.04, 0.1, 0.4, v("nind", r),
                    PhotoParams{Float64}(; path = :c3, issla = true, sla = v("sla", r)),
                    TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false
                ) for r in rows
        ]
        return pools, tmpls
    end

    σ = 5.670374419e-8
    cells = readcsv(joinpath(refdir, "M_cells.csv"))
    names = String.(cells["name"]); lats = fcol(cells, "lat")

    ann = Dict{String, NamedTuple}()
    for (k, name) in enumerate(names)
        f = readcsv(joinpath(refdir, "biome_forcing_$(name).csv"))
        tairK = fcol(f, "temp") .+ 273.15
        swd = fcol(f, "swdown"); lwn = fcol(f, "lwnet"); prec = fcol(f, "precip")
        huss = fcol(f, "huss"); co2 = fcol(f, "co2")
        n = min(length(tairK), 2 * 365)                # 2 years for CI speed
        forcings = [
            AtmForcing(;
                    swdown = swd[i], lwdown = lwn[i] + σ * tairK[i]^4, tair = tairK[i], qair = huss[i],
                    wind = 2.0, psurf = 1.0e5, precip = prec[i], co2 = co2[i]
                ) for i in 1:n
        ]
        soil = readsoil(joinpath(refdir, "M_soilcolumn_$(name).txt"))
        pools, tmpls = readcanopy(joinpath(refdir, "M_individuals_$(name)_2010.csv"))
        core = FDiffFastCore(pools, tmpls, soil, lats[k])
        clo = SEBEnergyClosure(; t_soil0 = _mean(tairK))
        state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
        out = run_coupled_cell(core, clo, state, forcings; days_per_year = 365)

        # ── the Phase-4 hard gate holds in EVERY climate regime, now with per-cell vegetation ──
        @test maximum(abs, out.resid) < 1.0e-6
        @test all(isfinite, out.t_skin) && all(isfinite, out.le) && all(isfinite, out.h) && all(isfinite, out.g)
        # Latent heat is non-negative up to a small, BOUNDED smooth-surrogate undershoot. F's ET is built
        # from `smoothmin` (fdiff_smoothops.jl), and `smoothmin(a, b, β) ≤ min(a, b)` dips below the true
        # minimum by ≤ log(2)/β EVEN for a, b ≥ 0. In a fully water-depleted dry-season corner
        # (`available → 0`, `demand → 0`) `et = smoothmin(et_demand, available, βw)` bottoms out a few
        # hundredths of a mm/day below zero ⇒ `le ≈ −0.6 W/m²` where the physical ET is 0 (this model has
        # no dew/condensation term). It is bounded and harmless to E's closure (H := Rn − LE − G absorbs
        # it). Assert the BOUND, not exact non-negativity — a genuine sign bug would be orders larger.
        @test all(≥(-2.0), out.le)
        @test all(0.0 .≤ out.albedo .≤ 1.0)
        @test all(>(0.0), out.z0)
        @test maximum(abs, out.t_skin .- tairK[1:n]) < 30.0   # skin bounded near air across all climates

        ann[name] = (
            le = _mean(out.le), h = _mean(out.h), rn = _mean(out.rn),
            bowen = _mean(out.h) / max(_mean(out.le), 1.0e-6),
        )
    end

    # ── emergent climate-driven partitioning, now with each cell's own vegetation + soil ──
    @test ann["tropical_amazon"].le > ann["boreal_siberia"].le           # wet warm tropics evaporate far more
    @test ann["tropical_amazon"].le > ann["semiarid_sahel"].le           # water availability drives ET
    @test ann["tropical_amazon"].bowen < ann["temperate_hainich"].bowen  # tropics LE-dominated
    @test ann["semiarid_sahel"].bowen > ann["tropical_amazon"].bowen     # dry biome → sensible-heat dominated
    @test ann["mediterranean_iberia"].bowen > ann["tropical_amazon"].bowen
    @test ann["tropical_amazon"].rn > ann["boreal_siberia"].rn           # more net radiation in the tropics
end
