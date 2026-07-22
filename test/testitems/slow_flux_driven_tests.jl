# P1 Tier-1 (docs/p1_s_in_loop_design.md §7 step 8; ADR 0020/0021/0022) — the FLUX-DRIVEN Component S in
# the coupled loop. `FluxDrivenSlowEmulator` sets the demography TARGET from a trained flux-conditioned DRF
# (`src/drf.jl`, the zero-dep native-Julia forest) instead of Tier-0's constant rate, and moves the coupled
# tree density toward `target/n_prev` through the SAME carbon-conserving machinery Tier-0 uses. These
# testitems are the Tier-1 wiring gates:
#   • MECHANISM — the DRF target DRIVES the demography: a decline-predicting forest shrinks N, a
#     growth-predicting forest grows N (F alone holds tree N constant, so the change is causally S+DRF).
#   • CONSERVATION — the S↔F handoff conserves carbon to ≤ 1e-6·C_scale every year (as Tier-0, by
#     construction — the ledger/`vegc_full_ind` routing is identical).
#   • DETERMINISM — same seed ⇒ identical coupled N trajectory (the DRF predict path is deterministic).
#   • ENERGY closure preserved; all finite; opt-in (`slow=nothing` unaffected — covered in slow_demography).
# The DRF here is trained IN-TEST on synthetic (feature→target) data so the WIRING + CONSERVATION are what
# is under test; the DRF's flux-conditioning SKILL is validated separately by scripts/flux_ood_experiment.jl
# (ADR 0020, flux 2.35× climate on the warm+dry OOD holdout). Hainich (DE-Hai, cell 42490) prototype.

@testitem "Flux-driven S (DRF target) — mechanism + carbon conservation + determinism + energy closure (Hainich 42490)" tags = [:conservation, :coupling, :energy, :scientific] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
    using LPJmLFITEmulator.DRF
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

    # ── a controllable DRF: target = c · (AR feature at index 11). With every node allowed to see all
    #    features (mtry = nfeat), the forest keys cleanly on the AR column, so at runtime the demographic
    #    ratio ρ = target/n_prev ≈ c — a decline (c<1) or growth (c>1) signal we can assert on. ──
    nbound = 3                                   # baked slow-boundary tail length
    nfeat = 11 + nbound
    function ratio_forest(c; seed = 7)
        r = DRF.Xoshiro256pp(seed)
        m = 3000
        X = Matrix{Float64}(undef, m, nfeat)
        y = Vector{Float64}(undef, m)
        for i in 1:m
            for ff in 1:nfeat
                X[i, ff] = DRF.rand01!(r)
            end
            ar = 0.5 + 59.5 * DRF.rand01!(r)     # AR feature spans [0.5, 60] (covers the runtime range)
            X[i, 11] = ar
            y[i] = c * ar + 0.005 * (DRF.rand01!(r) - 0.5)
        end
        return DRF.fit_forest(X, y; ntrees = 60, subsample = 1500, max_depth = 16, min_leaf = 6, mtry = nfeat, seed = seed)
    end
    boundary = [0.3, 0.5, 0.7]

    nyears = 12
    forcings = repeat(year_forc, nyears)

    # fixed-N reference (F alone cannot move tree N)
    core_none = mkcore()
    nind0 = [p.nind for p in core_none.pools]
    out_none = run_coupled_cell(core_none, mkclo(), mkstate(), forcings; slow = nothing, days_per_year = n)
    @test [p.nind for p in core_none.pools] == nind0

    # ── DECLINE: c = 0.85 ⇒ N shrinks year over year, carbon conserves ──
    core_d = mkcore()
    cscale_d = sum(FDiff.vegc_full_ind(p) * p.nind for p in core_d.pools)
    sdn = FluxDrivenSlowEmulator(core_d, ratio_forest(0.85); boundary = boundary, n_init = 10.0, seed = 1)
    @test sdn.recruit_idx > 0
    out_d = run_coupled_cell(core_d, mkclo(), mkstate(), forcings; slow = sdn, days_per_year = n)
    @test all(isfinite, out_d.t_skin) && all(isfinite, out_d.npp) && all(isfinite, out_d.le)
    @test maximum(abs, out_d.resid) < 1.0e-6                                     # energy closes by construction
    @test length(sdn.total_n_history) == nyears
    @test length(sdn.target_history) == nyears && all(isfinite, sdn.target_history)
    @test sdn.total_n_history[end] < sdn.total_n_history[1]                      # N DECLINED (DRF drove it)
    @test issorted(sdn.total_n_history[2:end]; rev = true)                       # monotone decline after the year-0 seed
    @test maximum(abs, sdn.resid_history) ≤ 1.0e-6 * cscale_d                    # carbon conserves per year
    @test maximum(abs, sdn.resid_history) < 1.0e-6                               # absolute machine-precision floor
    @test out_d.npp != out_none.npp                                             # S changed the trajectory

    # ── GROWTH: c = 1.12 ⇒ N rises year over year, carbon still conserves ──
    core_g = mkcore()
    cscale_g = sum(FDiff.vegc_full_ind(p) * p.nind for p in core_g.pools)
    sup = FluxDrivenSlowEmulator(core_g, ratio_forest(1.12); boundary = boundary, n_init = 10.0, seed = 1)
    out_g = run_coupled_cell(core_g, mkclo(), mkstate(), forcings; slow = sup, days_per_year = n)
    @test sup.total_n_history[end] > sup.total_n_history[1]                      # N GREW (establishment fired)
    @test issorted(sup.total_n_history[2:end])                                   # monotone growth after the year-0 seed
    @test sup.ledger.estab_year ≥ 0.0
    @test maximum(abs, sup.resid_history) ≤ 1.0e-6 * cscale_g
    @test maximum(abs, sup.resid_history) < 1.0e-6

    # ── DETERMINISM: same seed ⇒ identical coupled N trajectory (DRF predict is deterministic) ──
    core_r1 = mkcore(); core_r2 = mkcore()
    s1 = FluxDrivenSlowEmulator(core_r1, ratio_forest(0.9; seed = 3); boundary = boundary, n_init = 10.0, seed = 5)
    s2 = FluxDrivenSlowEmulator(core_r2, ratio_forest(0.9; seed = 3); boundary = boundary, n_init = 10.0, seed = 5)
    run_coupled_cell(core_r1, mkclo(), mkstate(), forcings; slow = s1, days_per_year = n)
    run_coupled_cell(core_r2, mkclo(), mkstate(), forcings; slow = s2, days_per_year = n)
    @test s1.total_n_history == s2.total_n_history
    @test s1.resid_history == s2.resid_history

    # ── stand_structure_tof from the S-updated population stays finite + physically bounded ──
    bc = stand_structure_tof(core_d)
    @test all(isfinite, (bc.lai, bc.height, bc.z0, bc.rootdepth, bc.vcmax, bc.fpc, bc.albedo))
    @test 0.0 < bc.fpc ≤ 1.0 && bc.height > 0
end

@testitem "Flux-driven S runs + conserves + stays type-stable in Float32 (SpeedyWeather-coupling type)" tags = [:conservation, :coupling, :scientific] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
    using LPJmLFITEmulator.DRF
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
    v(k, r) = parse(Float64, ind[k][r]); nt(r) = parse(Int, ind["type"][r]); f32(x) = Float32(x)
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

    # a trivial DRF (target = AR feature ⇒ ρ ≈ 1) is enough for the type-stability + conservation check
    nfeat = 11
    r = DRF.Xoshiro256pp(2)
    m = 800
    X = Matrix{Float64}(undef, m, nfeat); y = Vector{Float64}(undef, m)
    for i in 1:m
        for ff in 1:nfeat
            X[i, ff] = DRF.rand01!(r)
        end
        ar = 1.0 + 20.0 * DRF.rand01!(r); X[i, 11] = ar; y[i] = ar
    end
    forest = DRF.fit_forest(X, y; ntrees = 30, subsample = 400, mtry = nfeat, seed = 2)

    s = FluxDrivenSlowEmulator(core, forest; n_init = 8.0f0, seed = 1)
    @test s isa FluxDrivenSlowEmulator{Float32}
    grow = grow_annual_accounted!(core)
    reconcile_demography!(s, core, grow, SharedState(; w = fill(0.7f0, LPJmLFITEmulator.NSOILLAYER)))
    @test s.last_resid isa Float32
    @test isfinite(s.last_resid) && abs(s.last_resid) ≤ 1.0f-5 * cscale
    bc = stand_structure_tof(core)
    @test bc isa SToF{Float32}
    @test all(isfinite, (bc.lai, bc.height, bc.z0, bc.rootdepth, bc.vcmax, bc.fpc, bc.albedo))
end
