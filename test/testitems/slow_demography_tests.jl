# P1 Steps 6+7 (docs/p1_s_in_loop_design.md §7) — Component S IN the coupled loop. The Tier-0
# `DemographicSlowEmulator` owns the per-cell population (count N, establishment, mortality; ADR 0018)
# while F_diff owns the representative individuals' CARBON growth; carbon is conserved at the S↔F handoff
# by routing every movement through a `CarbonLedger` (flux-then-integrate, ADR 0003). These testitems are
# the P1 gates:
#   • Gate-1 — S is really in the loop: `slow=DemographicSlowEmulator` runs ≥20 yr, all finite, energy
#     still closes, and the total count N CHANGES year-to-year (F alone can't move N).
#   • Gate-2 — the S↔F handoff CONSERVES carbon to ≤ 1e-6·C_scale, per year, incl. forced N-up
#     (recruitment), N-down (mortality), and a seeded below-ground `sapwood_bg_c>0` cohort.
#   • Byte-identical default — `slow=nothing` is exactly the pre-S self-growing path.
#   • `stand_structure_tof` re-derives finite, physically-bounded structural BCs from the S-updated pop.
# Hainich (DE-Hai, cell 42490) prototype; forcing repeated across years (Tier-0 demography realism is a
# documented placeholder — Tier-1 wires the ported climate/FToS-conditioned models, ADR 0019).

@testitem "Coupled S in the loop — Gate-1 (N evolves) + Gate-2 (carbon handoff) + energy closure + byte-identical default (Hainich 42490)" tags = [:conservation, :coupling, :energy, :scientific] begin
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
    ind = readcsv(joinpath(refdir, "hainich_individuals_2010.csv"))
    f = readcsv(joinpath(refdir, "hainich_forcing_2010.csv"))
    fc_(k) = parse.(Float64, f[k])
    v(k, r) = parse(Float64, ind[k][r])
    nt(r) = parse(Int, ind["type"][r])
    n = length(fc_("doy"))

    sd = Float64[]; whcs = Float64[]; rdist = Float64[]
    for ln in eachline(joinpath(refdir, "hainich_soilcolumn.txt"))
        s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
        x = parse.(Float64, split(s)); push!(sd, x[2]); push!(whcs, x[3]); push!(rdist, x[4])
    end
    soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)

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
    pools = [mkp(r) for r in rows]; tmpls = [mkt(r) for r in rows]

    tair_K = fc_("temp") .+ 273.15
    σ = 5.670374419e-8
    year_forc = [
        AtmForcing(;
                swdown = fc_("swdown")[i], lwdown = fc_("lwnet")[i] + σ * tair_K[i]^4,
                tair = tair_K[i], qair = fc_("huss")[i], wind = 2.0, psurf = 1.0e5,
                precip = fc_("precip")[i], co2 = fc_("co2")[i]
            ) for i in 1:n
    ]
    mkcore() = FDiffFastCore([mkp(r) for r in rows], [mkt(r) for r in rows], soil, 51.25)
    mkclo() = SEBEnergyClosure(; t_soil0 = _mean(tair_K))
    mkstate() = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))

    nyears = 20
    forcings = repeat(year_forc, nyears)

    # ── BYTE-IDENTICAL + DIFFERENTIAL: `slow=nothing` is the pre-S fixed-N F path. S must (a) match it on the
    #    plumbing (the default kwarg IS `nothing`) and (b) leave tree N CONSTANT — `annual_step!` never moves
    #    tree `nind` — so any N change under `slow=` is attributable to S's demography, not to F. ──
    out_default = run_coupled_cell(mkcore(), mkclo(), mkstate(), year_forc; days_per_year = n)
    out_nothing = run_coupled_cell(mkcore(), mkclo(), mkstate(), year_forc; slow = nothing, days_per_year = n)
    for k in keys(out_default)
        @test getproperty(out_default, k) == getproperty(out_nothing, k)      # default kwarg == explicit nothing (plumbing)
    end
    core_none = mkcore()
    nind0_none = [p.nind for p in core_none.pools]
    out_none = run_coupled_cell(core_none, mkclo(), mkstate(), forcings; slow = nothing, days_per_year = n)
    @test [p.nind for p in core_none.pools] == nind0_none                     # fixed-N F holds tree N constant over 20 yr

    # ── S IN THE LOOP over 20 yr (same forcing) ──
    core = mkcore()
    ncoh0 = length(core.pools)                     # K persistent cohorts at t0 (Gate-4 structural basis)
    cscale0 = sum(FDiff.vegc_full_ind(p) * p.nind for p in core.pools)         # veg-C scale for the Gate-2 tolerance (initial)
    slow = DemographicSlowEmulator(core)
    @test slow.recruit_idx > 0                    # a beech stand has a shortest-living tree cohort to recruit into
    out = run_coupled_cell(core, mkclo(), mkstate(), forcings; slow = slow, days_per_year = n)

    # everything finite; energy still closes by construction, every day
    @test all(isfinite, out.t_skin) && all(isfinite, out.le) && all(isfinite, out.h) && all(isfinite, out.g)
    @test all(isfinite, out.gpp) && all(isfinite, out.npp)
    @test maximum(abs, out.resid) < 1.0e-6
    @test out.npp != out_none.npp                                             # S changed the trajectory vs fixed-N F

    # ── Gate-1: S is in the loop ⇒ N moves year-to-year AND recruitment fires (N INCREASES in some year — F's
    #    fixed-N path above cannot move tree N at all, so this is causally S's demography, not F). ──
    @test length(slow.total_n_history) == nyears
    @test all(x -> isfinite(x) && x > 0, slow.total_n_history)
    @test slow.total_n_history[end] != slow.total_n_history[1]                 # N evolved
    @test any(>(0.0), diff(slow.total_n_history))                             # recruitment FIRED (not a monotone mortality decline)
    @test total_n(slow) == slow.total_n_history[end]

    # ── Gate-2: the S↔F handoff conserves carbon to ≤ 1e-6·C_scale, every year ──
    @test length(slow.resid_history) == nyears
    @test maximum(abs, slow.resid_history) ≤ 1.0e-6 * cscale0
    @test maximum(abs, slow.resid_history) < 1.0e-6                            # (machine precision in absolute terms too)

    # ── Gate-4 (structural basis of the speed-up): a FIXED roster of K persistent cohorts across the run ──
    # S's per-year work is O(K); it does NOT carry an explicit-N individual ensemble (the C-IBM's cost that
    # the hybrid collapses). Timing is measured off the login node by scripts/bench_slow_speedup.jl.
    @test length(core.pools) == ncoh0                                         # roster size unchanged over 20 yr (Tier-0)
    @test length(slow.age) == ncoh0                                           # S's per-cohort state stays O(K)
    @test ncoh0 ≤ 64                                                          # K small — the collapse of the C-IBM individuals

    # ── stand_structure_tof: finite, physically-bounded structural BCs from the S-updated population ──
    bc = stand_structure_tof(core)
    @test all(isfinite, (bc.lai, bc.height, bc.z0, bc.rootdepth, bc.vcmax, bc.fpc, bc.albedo))
    @test bc.lai > 0 && bc.height > 0 && bc.vcmax > 0
    @test 0.0 < bc.fpc ≤ 1.0
    @test bc.z0 ≥ 0.01
    @test 0.0 < bc.rootdepth ≤ sum(sd)                                        # D95 within the soil column
    @test 0.0 ≤ bc.albedo ≤ 1.0
end

@testitem "S↔F demographic handoff conserves carbon on forced N-up / N-down / seeded sapwood_bg years (Hainich 42490)" tags = [:conservation, :coupling, :scientific] begin
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

    # a fresh Hainich dominant-tree core each scenario; optionally seed one cohort's sapwood_bg_c
    function mkcore(; seed_sbg = 0.0)
        pools = [mkp(r) for r in rows]
        if seed_sbg > 0
            p = pools[1]
            pools[1] = TreePools{Float64}(
                p.leaf_c, p.sapwood_c, p.heartwood_c, p.root_c, seed_sbg,   # sapwood_bg_c > 0
                p.height, p.crownarea, p.nind, p.sla, p.wooddens, p.is_grass,
            )
        end
        return FDiffFastCore(pools, [mkt(r) for r in rows], soil, 51.25)
    end
    totn(c) = sum(p.nind for p in c.pools)
    cvegfull(c) = sum(FDiff.vegc_full_ind(p) * p.nind for p in c.pools)

    # drive one accounted growth + demography year with the given rates. `stag_idx>0` forces that cohort into
    # a carbon DEFICIT (stagnation). Returns the residual + C_scale + N before/after + the ledger tallies.
    function run_year(core; mort_bg, mort_max, estab_rate, bm_ind = 500.0, stag_idx = 0)
        core.nday = 365
        core.wscal_acc = 0.9 * 365
        for i in eachindex(core.pools)
            core.bm_inc_acc[i] = (i == stag_idx ? -8.0 : bm_ind) * core.pools[i].nind
        end
        cscale = cvegfull(core)
        n_before = totn(core)
        s = DemographicSlowEmulator(core; mort_bg = mort_bg, mort_max = mort_max, estab_rate = estab_rate)
        grow = grow_annual_accounted!(core)
        state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
        reconcile_demography!(s, core, grow, state)
        return (
            resid = s.last_resid, cscale = cscale, n_before = n_before, n_after = totn(core),
            unapplied = s.ledger.unapplied_bm_year, litter = s.ledger.litter_year, estab = s.ledger.estab_year,
        )
    end

    # ── N-UP: strong recruitment, weak mortality ⇒ N increases; carbon still conserves ──
    up = run_year(mkcore(); mort_bg = 0.005, mort_max = 0.005, estab_rate = 0.5)
    @test up.n_after > up.n_before
    @test up.estab > 0.0                                                       # establishment carbon actually flowed
    @test abs(up.resid) ≤ 1.0e-6 * up.cscale

    # ── N-DOWN: strong mortality, no recruitment ⇒ N decreases; mortality carbon → litter conserves ──
    down = run_year(mkcore(); mort_bg = 0.2, mort_max = 0.3, estab_rate = 0.0)
    @test down.n_after < down.n_before
    @test down.estab == 0.0                                                    # recruitment off ⇒ no establishment flux
    @test abs(down.resid) ≤ 1.0e-6 * down.cscale

    # ── STAGNATION in the handoff: a deficit cohort is frozen ⇒ its NPP → the bounded `unapplied` diagnostic
    #    (NOT applied, NOT litter); the residual must still close with a stagnating cohort present. ──
    core_st = mkcore()
    stag = run_year(core_st; mort_bg = 0.02, mort_max = 0.02, estab_rate = 0.05, stag_idx = length(core_st.pools))
    @test stag.unapplied < 0.0                                                 # the deficit cohort's negative NPP was parked
    @test abs(stag.resid) ≤ 1.0e-6 * stag.cscale

    # ── seeded below-ground sapwood_bg_c > 0: routing mortality on vegc_full (not vegc) must not leak it. The
    #    leak the design calls load-bearing is ≈ sapwood_bg·Δnind (tenths of gC) — so also assert the ABSOLUTE
    #    machine-precision floor, which a vegc_ind-based mortality routing would violate. ──
    core_sbg = mkcore(seed_sbg = 60.0)
    @test FDiff.vegc_full_ind(core_sbg.pools[1]) > FDiff.vegc_ind(core_sbg.pools[1])   # sbg actually present
    sbg = run_year(core_sbg; mort_bg = 0.05, mort_max = 0.1, estab_rate = 0.1)
    @test abs(sbg.resid) ≤ 1.0e-6 * sbg.cscale
    @test abs(sbg.resid) < 1.0e-6                                              # absolute floor: catches a sapwood_bg leak
end

@testitem "S↔F demographic handoff runs + conserves + stays type-stable in Float32 (SpeedyWeather-coupling type)" tags = [:conservation, :coupling, :scientific] begin
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
    v(k, r) = parse(Float64, ind[k][r]); nt(r) = parse(Int, ind["type"][r])
    f32(x) = Float32(x)
    prows = Dict{Int, Vector{Int}}()
    for r in eachindex(ind["type"])
        (nt(r) <= 6 && v("height", r) > 0) && push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
    end
    rows = prows[argmax(Dict(k => length(vv) for (k, vv) in prows))]
    mkp(r) = TreePools{Float32}(
        f32(v("leaf_c", r)), f32(v("sapwood_c", r)),
        f32(max(v("agb", r) / v("nind", r) - v("leaf_c", r) - v("sapwood_c", r), 0.0)), f32(v("root_c", r)),
        f32(v("height", r)), f32(v("crownarea", r)), f32(v("nind", r)), f32(v("sla", r)), f32(v("wooddens", r)), false,
    )
    mkt(r) = Individual{Float32}(
        f32(v("fpar_leafon", r)), 0.0f0, f32(v("alphaa", r)), f32(v("albedo_leaf", r)), f32(v("emax", r)),
        f32(v("sapwood_c", r)), f32(v("root_c", r)), 0.0f0, 0.02f0, 0.04f0, 0.1f0, 0.4f0, f32(v("nind", r)),
        PhotoParams{Float32}(; path = :c3, issla = true, sla = f32(v("sla", r))),
        TempStressParams{Float32}(; temp_photos_low = 20.0f0, temp_photos_high = 30.0f0), false,
    )
    sd = Float32[]; whcs = Float32[]; rdist = Float32[]
    for ln in eachline(joinpath(refdir, "hainich_soilcolumn.txt"))
        s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
        x = parse.(Float64, split(s)); push!(sd, f32(x[2])); push!(whcs, f32(x[3])); push!(rdist, f32(x[4]))
    end
    soil = hainich_soilcolumn(Float32; whcs = whcs, rootdist = rdist, soildepth = sd)

    core = FDiffFastCore([mkp(r) for r in rows], [mkt(r) for r in rows], soil, 51.25)
    @test core.pools[1].leaf_c isa Float32
    core.nday = 365; core.wscal_acc = 0.9f0 * 365
    for i in eachindex(core.pools)
        core.bm_inc_acc[i] = 400.0f0 * core.pools[i].nind
    end
    cscale = sum(FDiff.vegc_full_ind(p) * p.nind for p in core.pools)
    s = DemographicSlowEmulator(core; estab_rate = 0.1f0)
    @test s isa DemographicSlowEmulator{Float32}
    grow = grow_annual_accounted!(core)
    reconcile_demography!(s, core, grow, SharedState(; w = fill(0.7f0, LPJmLFITEmulator.NSOILLAYER)))
    @test s.last_resid isa Float32
    # Float32 rounding floor of the conservation cancellation is ~eps(Float32)·cscale ≈ 2e-4 for this stand;
    # 1e-5·cscale (~165× that) is non-flaky yet still catches a gross accounting/type error.
    @test isfinite(s.last_resid) && abs(s.last_resid) ≤ 1.0f-5 * cscale
    bc = stand_structure_tof(core)
    @test bc isa SToF{Float32}
    @test all(isfinite, (bc.lai, bc.height, bc.z0, bc.rootdepth, bc.vcmax, bc.fpc, bc.albedo))
end
