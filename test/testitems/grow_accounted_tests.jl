# P1 Step 3 (docs/p1_s_in_loop_design.md §7) — the accounted year-end growth `grow_annual_accounted!`,
# the S-in-the-loop counterpart of `annual_step!`. It grows F's representative individuals at FIXED nind
# exactly as `annual_step!` does, but returns the grown pools + the EXACT per-cell carbon fluxes (applied
# NPP, unapplied NPP from stagnating cohorts, and litter as the branch-agnostic growth residual) so the
# slow emulator S can then apply demography and route the fluxes through a CarbonLedger. This gate asserts
# the fixed-N carbon closure `Σ Δvegc_full·nind + litter_cell == applied_bm_cell` and the applied/unapplied
# split, and that the function is pure w.r.t. `fc` (does not mutate the committed population). The
# `slow=nothing` path (`annual_step!`) is untouched — its byte-identity is covered by coupled_run_tests /
# biome_coupled_tests (unchanged).

@testitem "Accounted growth — grow_annual_accounted! fixed-N carbon closure + applied/unapplied split (Hainich)" tags = [:conservation, :coupling, :scientific] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
    using LPJmLFITEmulator.Allometry
    using Test

    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
        hdr = split(strip(lines[1]), ',')
        rows = [split(strip(l), ',') for l in lines[2:end]]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end
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
        v("height", r), v("crownarea", r), v("nind", r), v("sla", r), v("wooddens", r), false,
    )
    mkt(r) = Individual{Float64}(
        v("fpar_leafon", r), 0.0, v("alphaa", r), v("albedo_leaf", r), v("emax", r),
        v("sapwood_c", r), v("root_c", r), 0.0, 0.02, 0.04, 0.1, 0.4, v("nind", r),
        PhotoParams{Float64}(; path = :c3, issla = true, sla = v("sla", r)),
        TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false,
    )
    sd = Float64[]; whcs = Float64[]; rdist = Float64[]
    for ln in eachline(joinpath(refdir, "hainich_soilcolumn.txt"))
        s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
        x = parse.(Float64, split(s)); push!(sd, x[2]); push!(whcs, x[3]); push!(rdist, x[4])
    end
    soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)

    core = FDiffFastCore([mkp(r) for r in rows], [mkt(r) for r in rows], soil, 51.25)
    ncoh = length(core.pools)
    @test ncoh ≥ 3

    # Seed the year's accumulators: most cohorts grow (per-individual bm ≈ 500 gC), one stagnates (bm < 0).
    core.nday = 365
    core.wscal_acc = 0.9 * 365
    stag = ncoh                                   # last cohort: force a carbon deficit (stagnation)
    for i in 1:ncoh
        core.bm_inc_acc[i] = i == stag ? -8.0 * core.pools[i].nind : 500.0 * core.pools[i].nind
    end

    vfull = FDiff.vegc_full_ind
    pop_vegc(pools) = sum(vfull(pools[i]) * pools[i].nind for i in eachindex(pools))
    before_pools = copy(core.pools)               # snapshot (grow_annual_accounted! must NOT mutate fc.pools)
    cveg_before = pop_vegc(core.pools)
    scale = max(cveg_before, 1.0)

    r = grow_annual_accounted!(core)

    # purity: fc.pools untouched (the caller commits after applying S's demography)
    @test core.pools === before_pools || all(core.pools[i] == before_pools[i] for i in 1:ncoh)
    @test length(r.newpools) == ncoh

    # applied + unapplied == total delivered NPP
    @test r.applied_bm_cell + r.unapplied_bm_cell ≈ r.bm_inc_cell rtol = 1.0e-12

    # the stagnating cohort is frozen (unchanged) and routed to unapplied, not applied
    @test r.newpools[stag] == before_pools[stag]
    @test r.unapplied_bm_cell ≈ core.bm_inc_acc[stag] rtol = 1.0e-12
    @test r.unapplied_bm_cell < 0.0              # it was a deficit

    # FIXED-N CARBON CLOSURE: Δ(Σ vegc_full·nind) + litter_cell == applied_bm_cell (the flux-then-integrate identity)
    cveg_after = pop_vegc(r.newpools)
    @test (cveg_after - cveg_before) + r.litter_cell ≈ r.applied_bm_cell rtol = 1.0e-6
    @test r.litter_cell ≥ -1.0e-9 * scale        # growth creates no carbon ⇒ litter ≥ 0

    # at least one growing cohort actually grew (sanity)
    @test any(vfull(r.newpools[i]) > vfull(before_pools[i]) for i in 1:(ncoh - 1))
    @test r.growth_eff ≥ 0.0 && r.water_stress ≈ 1.0 - r.wscal_mean
end
