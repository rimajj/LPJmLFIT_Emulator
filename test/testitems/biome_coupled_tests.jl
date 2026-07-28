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
    @test length(names) ≥ 5
    # ── name -> (cell, lat, lon) ROW-WISE, not as a set. A set comparison is order-blind,
    # so a two-value typo in the BIOMES registry regenerates every fixture consistently
    # MISLABELLED (e.g. `boreal_siberia,18371,13.75`) and still passes. lat/lon come from
    # grid.nc `cellid`, so pinning them pins the identity of the cell each name refers to.
    expect = Dict(
        "boreal_siberia" => (52059, 61.75, 104.75), "temperate_hainich" => (42490, 51.25, 10.25),
        "mediterranean_iberia" => (33335, 39.75, -4.25), "semiarid_sahel" => (18371, 13.75, 4.75),
        "tropical_amazon" => (12045, -3.25, -60.25),
    )
    for (nm, (cell, lat, lon)) in expect
        k = findfirst(==(nm), names)
        @test k !== nothing
        @test parse(Int, cells["cell"][k]) == cell
        @test parse(Float64, cells["lat"][k]) == lat
        @test parse(Float64, cells["lon"][k]) == lon
    end

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
        # normalizes to 1e-9; every committed column's PRINTED sum is within 1e-6, so 2e-6 is the
        # right bound (the 1.15e-5 worst-case print rounding of 23 values never materializes, and
        # a looser bound would admit the legacy form's below-column-bottom leak).
        @test all(≥(0.0), rd)
        @test isapprox(sum(rd), 1.0; atol = 2.0e-6)
        @test rd[end] == 0.0        # layer 22 (20-23 m) never holds roots (getrootdist.c)
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

    # ── PROVENANCE PINS: which column belongs to which cell ──────────────────────────────
    # The ordering assertions above are permutation-INSENSITIVE: an adversarial sweep of all
    # 120 permutations of the five committed columns found 4 that satisfy every ordering
    # (identity, boreal<->sahel, med<->amazon, and the 4-cycle of both), so a mis-paired
    # column would ship green. Pin each cell's own plant-available water and rooting depth
    # to the value its OWN soil produced (`extract_cell_soilcolumn.py`, gate-verified), which
    # no permutation can satisfy. Tolerances are the `%.4f`/`%.6f` print resolutions.
    # Sums of the PRINTED columns (not the extractor's unrounded internals), so the
    # tolerances are the accumulated print rounding: 3 x 5e-5 and 23 x 5e-5 for whcs
    # (`%.4f`), 3 x 5e-7 for the root fraction (`%.6f`).
    pins = Dict(   # name => (top-1m whcs mm, total whcs mm, top-1m root fraction)
        "boreal_siberia" => (167.5311, 3507.0329, 0.885829),
        "temperate_hainich" => (177.2791, 4010.7629, 0.878308),
        "mediterranean_iberia" => (155.5565, 3483.9645, 0.614679),
        "semiarid_sahel" => (117.1036, 2657.4898, 0.992989),
        "tropical_amazon" => (162.8281, 3492.5362, 0.532435),
    )
    for (nm, (top1, tot, rfrac)) in pins
        k = idx[nm]
        @test sum(whcs_all[k][1:3]) ≈ top1 atol = 2.0e-4
        @test sum(whcs_all[k]) ≈ tot atol = 2.0e-3
        @test sum(rd_all[k][1:3]) ≈ rfrac atol = 2.0e-6
    end
    # Hainich's plant-available water is unchanged from the committed column it was derived from
    _, whcs_ref, _ = readsoil(joinpath(refdir, "hainich_soilcolumn.txt"))
    @test whcs_all[idx["temperate_hainich"]] == whcs_ref

    # ── per-cell canopies: distinct individual sets, each with its own reconstructed light shares ──
    ninds = Int[]
    for (k, name) in enumerate(names)
        ind = readcsv(joinpath(refdir, "M_individuals_$(name)_2010.csv"))
        n = length(ind["type"])
        @test n > 0
        @test all(0.0 .≤ parse.(Float64, ind["fpar_leafon"]) .≤ 1.0)
        @test any(parse.(Int, ind["type"]) .≤ 6)                # at least one tree
        @test n == parse(Int, cells["n_ind"][k])                # the registry matches the file
        # The reconstruction is LEAF-ON while the C's FAPAR is phenology-weighted, so the ratio
        # to the C's own annual peak is systematically > 1 — Hainich's committed value is 1.60.
        # Assert the BAND: it is the only check that the canopy reconstruction still reproduces
        # the C at all (a factor-2 light bug keeps every per-individual value inside [0,1]).
        recon = parse(Float64, cells["fapar_recon"][k])
        cpeak = parse(Float64, cells["fapar_C_peak"][k])
        @test recon ≈ sum(parse.(Float64, ind["fpar_leafon"])) / 25 atol = 1.0e-4
        @test 1.15 < recon / cpeak < 1.85
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
