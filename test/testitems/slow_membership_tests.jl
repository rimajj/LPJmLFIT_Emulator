# P1 Tier-1 v3 (ADR 0024) — DYNAMIC cohort membership for the flux-driven Component S. Establishment now
# APPENDS a real age-0 recruit cohort (copula-sampled traits if the opt-in `recruit_copula` hook is set,
# else the fixed sapling), a K-cap MERGE bounds the roster, and `s.age` is a genuine per-cohort age so
# `age_mean` is a true nind-weighted demographic mean. These testitems gate the pieces the committed
# flux/production/oracle tests do not exercise:
#   • ATOMIC REBUILD (design risk #5) — a coupled run that APPENDS and MERGES completes without a daily-loop
#     bounds error, and every length-K `FDiffFastCore` field + `s.age` stays mutually length-consistent.
#   • CONSERVATION across append (estab influx) + merge (carbon-neutral) + a seeded sapwood_bg cohort.
#   • GENUINE AGE — the age0 seed takes, never-recruited survivors age +1/yr, recruits dilute the mean.
#   • COPULA hook — opt-in establishment draws recruit traits deterministically and still conserves.
#   • Float32 type-stability of the whole append+merge(+copula) path (the existing Float32 gate hits only
#     the year-0 ρ=1 seed branch, so the membership code never ran in Float32 before).
# Hainich (DE-Hai, cell 42490) prototype — scaffolding, not multi-cell evidence.

@testitem "Atomic cohort membership — append + K-cap merge rebuild every roster array consistently + conserve (Hainich 42490)" tags = [:conservation, :coupling, :energy, :scientific] begin
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
    v(k, r) = parse(Float64, ind[k][r]); nt(r) = parse(Int, ind["type"][r])
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

    # growth forest: target = c·(AR feature @ index 11), so ρ ≈ c > 1 ⇒ an APPEND every year
    function growth_forest(c; seed = 7)
        r = DRF.Xoshiro256pp(seed); m = 3000; X = Matrix{Float64}(undef, m, 11); y = Vector{Float64}(undef, m)
        for i in 1:m
            for ff in 1:11
                X[i, ff] = DRF.rand01!(r)
            end
            ar = 0.5 + 59.5 * DRF.rand01!(r); X[i, 11] = ar; y[i] = c * ar
        end
        return DRF.fit_forest(X, y; ntrees = 60, subsample = 1500, max_depth = 16, min_leaf = 6, mtry = 11, seed = seed)
    end
    # growth factor kept modest so the geometric AR state n_prev≈10·c^k stays inside the forest's trained
    # [0.5,60] range over the run (else the target saturates, ρ drops below 1, and monotone growth breaks).

    K0 = length(rows)
    kcap = K0 + 2                                    # small cap ⇒ appends past year 2 force MERGES
    nyears = 12
    forcings = repeat(year_forc, nyears)

    core = mkcore()
    cscale = sum(FDiff.vegc_full_ind(p) * p.nind for p in core.pools)
    s = FluxDrivenSlowEmulator(core, growth_forest(1.12); n_init = 10.0, k_cap = kcap, age0 = 40.0, seed = 1)
    out = run_coupled_cell(core, mkclo(), mkstate(), forcings; slow = s, days_per_year = n)

    # ── ATOMIC REBUILD: the run APPENDED + MERGED without a daily-loop crash, and every roster-keyed array
    #    (pools/inds/tmpls/bm_inc_acc + s.age) is mutually length-consistent (design risk #5) ──
    K = length(core.pools)
    @test length(core.inds) == K
    @test length(core.tmpls) == K
    @test length(core.bm_inc_acc) == K
    @test length(core.pft_ids) == K
    @test length(s.age) == K
    @test K0 < K ≤ s.k_cap                           # grew via append, bounded by the K-cap merge
    @test all(isfinite, out.t_skin) && all(isfinite, out.npp) && all(isfinite, out.le)
    @test maximum(abs, out.resid) < 1.0e-6           # energy still closes across membership change

    # ── CONSERVATION survives append (estab influx) + merge (carbon-neutral) every year ──
    @test length(s.resid_history) == nyears
    @test maximum(abs, s.resid_history) ≤ 1.0e-6 * cscale
    @test maximum(abs, s.resid_history) < 1.0e-6
    @test issorted(s.total_n_history[2:end])         # append raises N; merge conserves Σnind ⇒ monotone growth
    @test s.total_n_history[end] > s.total_n_history[1]

    # ── DETERMINISM: same seed ⇒ identical trajectory AND identical final population (append/merge are rng-free) ──
    core1 = mkcore(); core2 = mkcore()
    s1 = FluxDrivenSlowEmulator(core1, growth_forest(1.12); n_init = 10.0, k_cap = kcap, age0 = 40.0, seed = 3)
    s2 = FluxDrivenSlowEmulator(core2, growth_forest(1.12); n_init = 10.0, k_cap = kcap, age0 = 40.0, seed = 3)
    run_coupled_cell(core1, mkclo(), mkstate(), forcings; slow = s1, days_per_year = n)
    run_coupled_cell(core2, mkclo(), mkstate(), forcings; slow = s2, days_per_year = n)
    @test s1.total_n_history == s2.total_n_history
    @test s1.resid_history == s2.resid_history
    @test [p.leaf_c for p in core1.pools] == [p.leaf_c for p in core2.pools]
    @test [p.height for p in core1.pools] == [p.height for p in core2.pools]

    # ── SEEDED sapwood_bg: merge/append route carbon on vegc_full_ind (incl sbg), not vegc_ind ──
    core_sbg = mkcore()
    p1 = core_sbg.pools[1]
    core_sbg.pools[1] = TreePools{Float64}(
        p1.leaf_c, p1.sapwood_c, p1.heartwood_c, p1.root_c, 60.0,   # seed a below-ground sapwood pool
        p1.height, p1.crownarea, p1.nind, p1.sla, p1.wooddens, false,
    )
    cscale_sbg = sum(FDiff.vegc_full_ind(p) * p.nind for p in core_sbg.pools)
    @test cscale_sbg > sum(FDiff.vegc_ind(p) * p.nind for p in core_sbg.pools)   # sbg present
    s_sbg = FluxDrivenSlowEmulator(core_sbg, growth_forest(1.12); n_init = 10.0, k_cap = kcap, age0 = 40.0, seed = 1)
    run_coupled_cell(core_sbg, mkclo(), mkstate(), forcings; slow = s_sbg, days_per_year = n)
    @test maximum(abs, s_sbg.resid_history) < 1.0e-6                              # no sbg routing leak
end

@testitem "Genuine per-cohort age — age0 seed + survivor aging + recruit-diluted spread (ADR 0024)" tags = [:coupling, :scientific] begin
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
    v(k, r) = parse(Float64, ind[k][r]); nt(r) = parse(Int, ind["type"][r])
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
    function forest_c(c; nf = 11, seed = 7)
        r = DRF.Xoshiro256pp(seed); m = 3000; X = Matrix{Float64}(undef, m, nf); y = Vector{Float64}(undef, m)
        for i in 1:m
            for ff in 1:nf
                X[i, ff] = DRF.rand01!(r)
            end
            ar = 0.5 + 59.5 * DRF.rand01!(r); X[i, 11] = ar; y[i] = c * ar
        end
        return DRF.fit_forest(X, y; ntrees = 60, subsample = 1500, max_depth = 16, min_leaf = 6, mtry = nf, seed = seed)
    end

    # age0 seed takes at construction (a scalar → uniform per-cohort seed)
    core0 = mkcore()
    s0 = FluxDrivenSlowEmulator(core0, forest_c(1.0); n_init = 10.0, age0 = 50.0, seed = 1)
    @test all(a -> isapprox(a, 50.0), s0.age)
    @test length(s0.age) == length(core0.pools)

    # DECLINE forest (ρ<1 ⇒ thin only, NO append/merge): every survivor ages +1/yr, so after N years
    # each cohort age == age0 + N (the sole-increment invariant; s.age .+= 1 is the only ager)
    N = 8
    core_d = mkcore()
    s_d = FluxDrivenSlowEmulator(core_d, forest_c(0.9); n_init = 10.0, age0 = 50.0, seed = 1)
    run_coupled_cell(core_d, mkclo(), mkstate(), repeat(year_forc, N); slow = s_d, days_per_year = n)
    @test length(core_d.pools) == length(rows)                    # no membership change on a pure decline
    @test all(a -> isapprox(a, 50.0 + N), s_d.age)                # survivors aged exactly N years

    # GROWTH forest (ρ>1 ⇒ APPEND age-0 recruits): the age vector develops genuine spread (young recruits
    # vs old survivors) — impossible under the old uniform elapsed-year counter
    core_g = mkcore()
    s_g = FluxDrivenSlowEmulator(core_g, forest_c(1.12); n_init = 10.0, k_cap = length(rows) + 4, age0 = 50.0, seed = 1)
    run_coupled_cell(core_g, mkclo(), mkstate(), repeat(year_forc, N); slow = s_g, days_per_year = n)
    @test minimum(s_g.age) < maximum(s_g.age)                     # genuine per-cohort age structure
    @test minimum(s_g.age) ≥ 1.0                                  # newest recruit: appended at 0, +1 at year end
    @test maximum(s_g.age) ≤ 50.0 + N                             # oldest survivor bounded by age0 + N
end

@testitem "Copula recruit-trait hook — opt-in establishment draws deterministically + conserves (ADR 0024)" tags = [:conservation, :coupling, :scientific] begin
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
    v(k, r) = parse(Float64, ind[k][r]); nt(r) = parse(Int, ind["type"][r])
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
    function growth_forest(c; seed = 7)
        r = DRF.Xoshiro256pp(seed); m = 3000; X = Matrix{Float64}(undef, m, 11); y = Vector{Float64}(undef, m)
        for i in 1:m
            for ff in 1:11
                X[i, ff] = DRF.rand01!(r)
            end
            ar = 0.5 + 59.5 * DRF.rand01!(r); X[i, 11] = ar; y[i] = c * ar
        end
        return DRF.fit_forest(X, y; ntrees = 60, subsample = 1500, max_depth = 16, min_leaf = 6, mtry = 11, seed = seed)
    end

    # a per-axis flux-conditioned marginal DRF (store_values=true) keying on feature 1 over [lo,hi]
    function axis_forest(seed, lo, hi; nf = 2)
        r = DRF.Xoshiro256pp(seed); m = 2000; X = Matrix{Float64}(undef, m, nf); y = Vector{Float64}(undef, m)
        for i in 1:m
            for ff in 1:nf
                X[i, ff] = DRF.rand01!(r)
            end
            y[i] = lo + (hi - lo) * X[i, 1]
        end
        return DRF.fit_forest(X, y; ntrees = 40, subsample = 1000, mtry = nf, seed = seed, store_values = true)
    end
    # map one drawn trait vector {size_factor, sla} → a recruit's per-individual pools (nind set on append)
    function recruit_from_traits(traits, sapl::FDiff.TreePools{T}, allom) where {T}
        fscale = clamp(T(traits[1]), T(0.3), T(3.0))
        sla_n = clamp(T(traits[2]), T(0.015), T(0.05))
        leaf = sapl.leaf_c * fscale; sapw = sapl.sapwood_c * fscale; root = sapl.root_c * fscale
        h = leaf > 0 ? T(allom.k_latosa) * sapw / (leaf * sla_n * sapl.wooddens) : sapl.height
        return FDiff.TreePools{T}(leaf, sapw, zero(T), root, zero(T), h, sapl.crownarea, one(T), sla_n, sapl.wooddens, false)
    end
    mkcopula() = RecruitCopula{Float64}(
        DRF.GaussianCopula([1.0 0.3; 0.3 1.0]),
        [axis_forest(11, 0.6, 2.4), axis_forest(12, 0.02, 0.04)],
        [0.5, 0.5],
        recruit_from_traits,
    )

    forcings = repeat(year_forc, 10)
    kcap = length(rows) + 3

    # ── WITH the copula hook: establishment draws recruit traits from s.rng ──
    core_c = mkcore()
    cscale = sum(FDiff.vegc_full_ind(p) * p.nind for p in core_c.pools)
    s_c = FluxDrivenSlowEmulator(core_c, growth_forest(1.12); n_init = 10.0, k_cap = kcap, age0 = 40.0, seed = 1, recruit_copula = mkcopula())
    run_coupled_cell(core_c, mkclo(), mkstate(), forcings; slow = s_c, days_per_year = n)
    @test length(core_c.pools) > length(rows)                    # recruits appended
    @test maximum(abs, s_c.resid_history) < 1.0e-6               # copula recruits still conserve (estab debit)
    @test maximum(abs, s_c.resid_history) ≤ 1.0e-6 * cscale
    @test all(isfinite, p.height for p in core_c.pools)

    # ── DETERMINISM: same seed + same copula ⇒ identical draws ⇒ identical population ──
    core_c2 = mkcore()
    s_c2 = FluxDrivenSlowEmulator(core_c2, growth_forest(1.12); n_init = 10.0, k_cap = kcap, age0 = 40.0, seed = 1, recruit_copula = mkcopula())
    run_coupled_cell(core_c2, mkclo(), mkstate(), forcings; slow = s_c2, days_per_year = n)
    @test s_c.total_n_history == s_c2.total_n_history
    @test [p.leaf_c for p in core_c.pools] == [p.leaf_c for p in core_c2.pools]

    # ── the hook is LIVE: copula recruits carry different carbon than the fixed sapling, so the coupled
    #    population veg-C differs from a run without the hook (same seed, same everything else) ──
    core_nc = mkcore()
    s_nc = FluxDrivenSlowEmulator(core_nc, growth_forest(1.12); n_init = 10.0, k_cap = kcap, age0 = 40.0, seed = 1)
    run_coupled_cell(core_nc, mkclo(), mkstate(), forcings; slow = s_nc, days_per_year = n)
    cveg_c = sum(FDiff.vegc_full_ind(p) * p.nind for p in core_c.pools)
    cveg_nc = sum(FDiff.vegc_full_ind(p) * p.nind for p in core_nc.pools)
    @test cveg_c != cveg_nc
end

@testitem "Membership + copula stay type-stable + conserving in Float32 (SpeedyWeather-coupling type)" tags = [:conservation, :coupling, :scientific] begin
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
    v(k, r) = parse(Float64, ind[k][r]); nt(r) = parse(Int, ind["type"][r]); f32(x) = Float32(x)
    n = length(fc_("doy"))
    sd = Float32[]; whcs = Float32[]; rdist = Float32[]
    for ln in eachline(joinpath(refdir, "hainich_soilcolumn.txt"))
        s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
        x = parse.(Float64, split(s)); push!(sd, f32(x[2])); push!(whcs, f32(x[3])); push!(rdist, f32(x[4]))
    end
    soil = hainich_soilcolumn(Float32; whcs = whcs, rootdist = rdist, soildepth = sd)
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
    tair_K = f32.(fc_("temp") .+ 273.15)
    σ = 5.670374419f-8
    year_forc = [
        AtmForcing(;
                swdown = f32(fc_("swdown")[i]), lwdown = f32(fc_("lwnet")[i]) + σ * tair_K[i]^4,
                tair = tair_K[i], qair = f32(fc_("huss")[i]), wind = 2.0f0, psurf = 1.0f5,
                precip = f32(fc_("precip")[i]), co2 = f32(fc_("co2")[i])
            ) for i in 1:n
    ]
    mkcore() = FDiffFastCore([mkp(r) for r in rows], [mkt(r) for r in rows], soil, 51.25)
    # closure + state MUST be {Float32} too: run_coupled_cell dispatches on a shared T across (fc, clo)
    # (run.jl), and the plain SEBEnergyClosure(;)/SharedState(;) constructors default to {Float64}. This
    # is the first test to drive the FULL coupled loop in Float32 (the sibling Float32 tests use
    # reconcile_demography! only), so end-to-end Float32 dispatch is exercised here for the first time.
    mkclo() = SEBEnergyClosure{Float32}(; t_soil0 = _mean(tair_K))
    mkstate() = SharedState{Float32}(; w = fill(0.7f0, LPJmLFITEmulator.NSOILLAYER))
    function growth_forest(c; seed = 7)
        r = DRF.Xoshiro256pp(seed); m = 3000; X = Matrix{Float64}(undef, m, 11); y = Vector{Float64}(undef, m)
        for i in 1:m
            for ff in 1:11
                X[i, ff] = DRF.rand01!(r)
            end
            ar = 0.5 + 59.5 * DRF.rand01!(r); X[i, 11] = ar; y[i] = c * ar
        end
        return DRF.fit_forest(X, y; ntrees = 60, subsample = 1500, max_depth = 16, min_leaf = 6, mtry = 11, seed = seed)
    end
    function axis_forest(seed, lo, hi; nf = 2)
        r = DRF.Xoshiro256pp(seed); m = 2000; X = Matrix{Float64}(undef, m, nf); y = Vector{Float64}(undef, m)
        for i in 1:m
            for ff in 1:nf
                X[i, ff] = DRF.rand01!(r)
            end
            y[i] = lo + (hi - lo) * X[i, 1]
        end
        return DRF.fit_forest(X, y; ntrees = 40, subsample = 1000, mtry = nf, seed = seed, store_values = true)
    end
    function recruit_from_traits(traits, sapl::FDiff.TreePools{T}, allom) where {T}
        fscale = clamp(T(traits[1]), T(0.3), T(3.0)); sla_n = clamp(T(traits[2]), T(0.015), T(0.05))
        leaf = sapl.leaf_c * fscale; sapw = sapl.sapwood_c * fscale; root = sapl.root_c * fscale
        h = leaf > 0 ? T(allom.k_latosa) * sapw / (leaf * sla_n * sapl.wooddens) : sapl.height
        return FDiff.TreePools{T}(leaf, sapw, zero(T), root, zero(T), h, sapl.crownarea, one(T), sla_n, sapl.wooddens, false)
    end

    core = mkcore()
    @test core.pools[1].leaf_c isa Float32
    cscale = sum(FDiff.vegc_full_ind(p) * p.nind for p in core.pools)
    rc = RecruitCopula{Float32}(
        DRF.GaussianCopula([1.0 0.3; 0.3 1.0]),
        [axis_forest(11, 0.6f0, 2.4f0), axis_forest(12, 0.02f0, 0.04f0)],
        [0.5, 0.5],
        recruit_from_traits,
    )
    s = FluxDrivenSlowEmulator(core, growth_forest(1.12); n_init = 10.0f0, k_cap = length(rows) + 3, age0 = 40.0f0, seed = 1, recruit_copula = rc)
    @test s isa FluxDrivenSlowEmulator{Float32}
    run_coupled_cell(core, mkclo(), mkstate(), repeat(year_forc, 10); slow = s, days_per_year = n)

    # append + merge + copula preserved Float32 throughout
    @test core.pools[end].leaf_c isa Float32
    @test core.pools[end].height isa Float32
    @test s.age isa Vector{Float32}
    @test s.last_resid isa Float32
    @test length(core.pools) > length(rows)                      # appended
    @test length(core.pools) == length(core.inds) == length(core.tmpls) == length(core.bm_inc_acc) == length(s.age)
    @test maximum(abs, s.resid_history) ≤ 1.0f-5 * cscale         # Float32 conservation floor
end
