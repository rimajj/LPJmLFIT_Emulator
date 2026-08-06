# Online transient bioclimatic boundary — the coupled-run "Climbuf" (ADR 0026/0027; src/climbuf.jl,
# docs/notes/online_transient_boundary_climbuf.md). Two gates:
#   • OFFLINE PARITY (the load-bearing train/inference contract, ADR 0023): the Julia `ClimBuf` must
#     reproduce `scripts/build_transient_boundary.py` — the daily→monthly reduction, the trailing-W-yr
#     window climatology, and the Thom-1966 monthly gdd5 + coldest-month boundary — from a committed Hainich
#     fixture (CI has no cluster `.clm`). The W=20 window ending 2019 reproduces the committed DRF meta
#     boundary (1863.695 / 0.2184) bit-for-method; earlier years reproduce the offline `boundary_series`.
#   • COUPLED WIRING: `run_coupled_cell(...; climbuf=)` accumulates F's daily air temperature, refreshes the
#     FluxDrivenSlowEmulator's `s.boundary` each year BEFORE `reconcile_demography!`, conserves carbon, is
#     deterministic, opt-in (default `climbuf=nothing` ⇒ `s.boundary` constant), and rejects misuse.
# Tolerances are float32-summation-order (numpy pairwise vs the ClimBuf's sequential reduction), not bitwise:
# gdd5 |Δ| < 0.5 of ~1800 (rel ~3e-4), tcm |Δ| < 1e-3 °C — orders of magnitude below any DRF split.

@testitem "Climbuf offline parity (ADR 0026/0027): reproduces build_transient_boundary.py (Hainich 42490)" tags = [:scientific] begin
    using LPJmLFITEmulator
    using Test

    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
        hdr = split(strip(lines[1]), ',')
        rows = [split(strip(l), ',') for l in lines[2:end]]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end
    monthly = readcsv(joinpath(refdir, "climbuf_hainich_monthly.csv"))
    bound = readcsv(joinpath(refdir, "climbuf_hainich_boundary_w20.csv"))
    daily = readcsv(joinpath(refdir, "climbuf_hainich_daily_2010.csv"))

    myears = parse.(Int, monthly["year"])
    monthrow(Y) = (r = findfirst(==(Y), myears); Float32[parse(Float32, monthly["T$(lpad(m, 2, '0'))"][r]) for m in 1:12])

    # ── (a) DAILY → MONTHLY: accumulate a real year's daily stream, finalize, match the offline monthly means ──
    doys = parse.(Int, daily["doy"])
    temps = parse.(Float32, daily["temp_C"])
    @test length(doys) == 365 && doys == collect(1:365)
    cb_d = ClimBuf{Float32}(; W = 20)
    for k in eachindex(doys)
        climbuf_accumulate!(cb_d, temps[k], doys[k])
    end
    Tm = climbuf_finalize_year!(cb_d)                                  # this year's 12 monthly means
    exp2010 = monthrow(2010)
    @test length(Tm) == 12
    @test maximum(abs, Tm .- exp2010) < 1.0f-2                         # sequential vs numpy-pairwise float32
    @test cb_d.filled == 1 && all(iszero, cb_d.month_cnt)              # ring got the year; accumulators reset

    # ── (b) TRAILING WINDOW: seed 1981-1999, then roll 2000-2019 and match the offline boundary_series ──
    byear = parse.(Int, bound["year"])
    bg = parse.(Float32, bound["gdd5"])
    bt = parse.(Float32, bound["tas_cold_month"])
    cb = ClimBuf{Float32}(; W = 20)
    climbuf_seed!(cb, (monthrow(Y) for Y in 1981:1999))               # spin-up: pre-run window climatology
    @test cb.filled == 19
    for (k, Y) in enumerate(2000:2019)
        climbuf_push_monthly!(cb, monthrow(Y))
        (g, t) = climbuf_gdd5_tcm(cb)
        @test byear[k] == Y
        @test abs(g - bg[k]) < 0.5                                    # gdd5 per-year == offline (rel ~3e-4)
        @test abs(t - bt[k]) < 1.0f-3                                 # coldest-month per-year == offline
    end
    @test cb.filled == 20                                             # sliding window stays capped at W
    # the W=20 window ending 2019 reproduces the committed production DRF meta boundary
    (g19, t19) = climbuf_gdd5_tcm(cb)
    @test abs(g19 - 1863.695f0) < 0.5
    @test abs(t19 - 0.2183871f0) < 1.0f-3

    # ── (c) climbuf_boundary overwrites ONLY the two time-varying axes; static tail (soil_depth, co2) passes through ──
    cb64 = ClimBuf{Float64}(; W = 20)
    for Y in 2000:2019
        climbuf_push_monthly!(cb64, Float64.(monthrow(Y)))
    end
    tmpl = [999.0, 999.0, 1.5173755884170532, 369.0]                  # [gdd5, tcm, soil_depth, co2]
    b = climbuf_boundary(cb64, tmpl)
    (g64, t64) = climbuf_gdd5_tcm(cb64)
    @test b[1] == g64 && b[2] == t64                                  # gdd5/tcm overwritten
    @test b[3] == 1.5173755884170532 && b[4] == 369.0                 # soil_depth + co2 (ADR 0004) untouched
    @test tmpl == [999.0, 999.0, 1.5173755884170532, 369.0]           # template not mutated (boundary copies)
    @test abs(g64 - 1863.695) < 0.5                                   # Float64 window matches too

    # ── (d) mechanism: a constant year, spin-up short window, and a warming stream raising the gate ──
    cb_c = ClimBuf{Float64}(; W = 20)
    climbuf_push_monthly!(cb_c, fill(10.0, 12))                       # one constant 10 °C year (1-yr window)
    (gc, tc) = climbuf_gdd5_tcm(cb_c)
    @test tc ≈ 10.0                                                   # coldest month = 10
    @test gc ≈ 5.0 * 365.0                                            # Σ max(10-5,0)·DPM = 5·Σdays = 1825
    cb_w = ClimBuf{Float64}(; W = 5)
    gs = Float64[]
    for warm in 0:4
        climbuf_push_monthly!(cb_w, fill(10.0 + warm, 12))
        push!(gs, climbuf_gdd5_tcm(cb_w)[1])
    end
    @test issorted(gs)                                               # a warming window monotonically opens the gate
    @test gs[end] > gs[1]

    # ── (e) guards: bad window / wrong-length monthly rows / empty buffer error clearly ──
    @test_throws ErrorException ClimBuf{Float64}(; W = 0)
    @test_throws ErrorException climbuf_push_monthly!(ClimBuf{Float64}(), fill(1.0, 11))
    @test_throws ErrorException climbuf_window_climatology(ClimBuf{Float64}())    # no year finalized yet
end

@testitem "Climbuf coupled wiring (ADR 0026/0027): drives s.boundary, conserves, deterministic, opt-in (Hainich 42490)" tags = [:conservation, :coupling, :scientific] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
    using LPJmLFITEmulator.DRF
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
    @test n == 365                                                    # the Climbuf's noleap month binning
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
    mkforc(dT) = [
        AtmForcing(;
                swdown = fc_("swdown")[i], lwdown = fc_("lwnet")[i] + σ * tair_K[i]^4,
                tair = tair_K[i] + dT, qair = fc_("huss")[i], wind = 2.0, psurf = 1.0e5,
                precip = fc_("precip")[i], co2 = fc_("co2")[i]
            ) for i in 1:n
    ]
    year_forc = mkforc(0.0)
    mkcore() = FDiffFastCore([mkp(r) for r in rows], [mkt(r) for r in rows], soil, 51.25)
    mkclo() = SEBEnergyClosure(; t_soil0 = _mean(tair_K))
    mkstate() = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))

    # a stable AR-keyed forest (mild decline): keys on feature 11 (n_prev), IGNORES the boundary tail, so the
    # demography is well-behaved regardless of the real (large) gdd5 boundary values — this testitem isolates
    # the BOUNDARY WIRING (asserted on s.boundary), not the boundary→target response (that's the ADR-0026 test).
    nbound = 4                                                        # production tail [gdd5, tcm, soil_depth, co2]
    nfeat = 11 + nbound
    function ar_forest(c; seed = 7)
        r = DRF.Xoshiro256pp(seed); m = 3000
        X = Matrix{Float64}(undef, m, nfeat); y = Vector{Float64}(undef, m)
        for i in 1:m
            for ff in 1:nfeat
                X[i, ff] = DRF.rand01!(r)
            end
            ar = 0.5 + 59.5 * DRF.rand01!(r); X[i, 11] = ar
            y[i] = c * ar + 0.005 * (DRF.rand01!(r) - 0.5)
        end
        return DRF.fit_forest(X, y; ntrees = 60, subsample = 1500, max_depth = 16, min_leaf = 6, mtry = nfeat, seed = seed)
    end
    init_bnd = [1863.695068359375, 0.21838709712028503, 1.5173755884170532, 369.0]   # DRF meta static boundary
    nyears = 6
    forcings = repeat(year_forc, nyears)

    # expected boundary once the buffer has seen the (repeated) forcing year: for an all-identical stream the
    # window climatology == that year's monthly means, so the boundary is CONSTANT and equals this reference.
    ref = ClimBuf{Float64}(; W = 20)
    for i in 1:n
        climbuf_accumulate!(ref, year_forc[i].tair - 273.15, i)
    end
    climbuf_finalize_year!(ref)
    exp_bnd = climbuf_boundary(ref, init_bnd)
    @test exp_bnd[1] != init_bnd[1]                                   # 2010 gdd5 ≠ the 2000-2019 static window

    # ── (A) OPT-IN default: climbuf=nothing leaves s.boundary at its initial (static) value (byte-identical) ──
    c0 = mkcore(); s0 = FluxDrivenSlowEmulator(c0, ar_forest(0.95); boundary = copy(init_bnd), n_init = 10.0, seed = 1)
    run_coupled_cell(c0, mkclo(), mkstate(), forcings; slow = s0, days_per_year = n)
    @test s0.boundary == init_bnd                                    # never touched without a Climbuf

    # ── (B) with a Climbuf the loop DRIVES s.boundary from the forcing (== the offline-consistent boundary) ──
    cb = ClimBuf{Float64}(; W = 20)
    c1 = mkcore(); s1 = FluxDrivenSlowEmulator(c1, ar_forest(0.95); boundary = copy(init_bnd), n_init = 10.0, seed = 1)
    cscale = sum(FDiff.vegc_full_ind(p) * p.nind for p in c1.pools)
    out1 = run_coupled_cell(c1, mkclo(), mkstate(), forcings; slow = s1, climbuf = cb, days_per_year = n)
    @test s1.boundary != init_bnd                                    # the Climbuf moved it
    @test maximum(abs, s1.boundary .- exp_bnd) < 1.0e-9              # == the offline-consistent trailing boundary
    @test s1.boundary[3] == init_bnd[3] && s1.boundary[4] == init_bnd[4]   # soil_depth + co2 preserved
    @test cb.filled == nyears                                        # one ring push per model year
    @test all(isfinite, out1.npp) && all(isfinite, out1.t_skin)
    @test maximum(abs, out1.resid) < 1.0e-6                          # energy still closes
    @test maximum(abs, s1.resid_history) ≤ 1.0e-6 * max(cscale, 1.0) # carbon conserves at the S↔F handoff
    @test length(s1.total_n_history) == nyears

    # ── (C) DETERMINISM: same seed + same Climbuf inputs ⇒ identical boundary + demography trajectory ──
    cb2 = ClimBuf{Float64}(; W = 20)
    c2 = mkcore(); s2 = FluxDrivenSlowEmulator(c2, ar_forest(0.95); boundary = copy(init_bnd), n_init = 10.0, seed = 1)
    run_coupled_cell(c2, mkclo(), mkstate(), forcings; slow = s2, climbuf = cb2, days_per_year = n)
    @test s2.boundary == s1.boundary
    @test s2.total_n_history == s1.total_n_history
    @test s2.resid_history == s1.resid_history

    # ── (D) a WARMING forcing raises the recomputed gate (final gdd5 rises vs the cold run) ──
    warm = vcat([mkforc(2.0 * (k - 1)) for k in 1:nyears]...)        # +2 K/yr ramp
    cbw = ClimBuf{Float64}(; W = 20)
    cw = mkcore(); sw = FluxDrivenSlowEmulator(cw, ar_forest(0.95); boundary = copy(init_bnd), n_init = 10.0, seed = 1)
    run_coupled_cell(cw, mkclo(), mkstate(), warm; slow = sw, climbuf = cbw, days_per_year = n)
    @test sw.boundary[1] > s1.boundary[1]                            # warmer trailing window ⇒ higher gdd5
    @test sw.boundary[2] > s1.boundary[2]                            # and a milder coldest month

    # ── (E) guards: mutually-exclusive series, Tier-0 emulator, non-365 year ──
    cse = mkcore(); sse = FluxDrivenSlowEmulator(cse, ar_forest(0.95); boundary_series = [copy(init_bnd) for _ in 1:nyears], n_init = 10.0, seed = 1)
    @test_throws ErrorException run_coupled_cell(cse, mkclo(), mkstate(), forcings; slow = sse, climbuf = ClimBuf{Float64}(), days_per_year = n)
    ct0 = mkcore(); st0 = DemographicSlowEmulator(ct0)
    @test_throws ErrorException run_coupled_cell(ct0, mkclo(), mkstate(), forcings; slow = st0, climbuf = ClimBuf{Float64}(), days_per_year = n)
    cn = mkcore(); sn = FluxDrivenSlowEmulator(cn, ar_forest(0.95); boundary = copy(init_bnd), n_init = 10.0, seed = 1)
    @test_throws ErrorException run_coupled_cell(cn, mkclo(), mkstate(), forcings; slow = sn, climbuf = ClimBuf{Float64}(), days_per_year = 364)
end
