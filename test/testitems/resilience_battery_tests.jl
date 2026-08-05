# Gate 11 — Resilience battery (ENGINEERING_STANDARDS §2 item 11; DEVELOPMENT_PLAN §5), line M / M4.
#
# Offline RMSE and even M3's year-matched levels say nothing about DYNAMICS: an emulator can hit every
# annual value and still have the wrong memory timescale, the wrong recovery rate, or a memory that is not
# its own. The battery is the three metrics that test that — autocorrelation-vs-climate, recovery rate,
# and the shuffle test — reimplemented from Bathiany et al. 2024 (doi:10.1111/gcb.17613). `LPJ_resilience`
# has NO licence, so none of its code is copied; only the published method.
#
# HOW THE WORK IS SPLIT, and why. The battery's SCIENCE needs the 180 MB pinned `_t8` pair on /p/tmp and a
# 20-year window; CI runs on GitHub runners with no cluster, so it can have neither. Same split as M3:
#   * MEASURED ON THE CLUSTER and pinned as committed fixtures —
#       references/M_resilience_reference_{cells,gradient,series}.csv  (scripts/extract_resilience_reference.py)
#       references/M_resilience_battery{,_shuffle,_longrun}.csv        (scripts/biome_resilience_probe.jl)
#   * COMPUTED HERE, every run — the ESTIMATOR (against synthetic series with a known answer) and the
#     MECHANISM (a real coupled F+E rollout on the committed 10-year forcing, perturbed and shuffled).
#     `slow = nothing` in the computed arms: they are artifact-independent by construction, so they test
#     what CI can honestly test — that the model's own carbon pools carry memory, release a perturbation,
#     and stay bounded — while the fixtures carry what only the cluster can measure.
# What the computed arms therefore do NOT claim: any statement about Component S's demographic memory.
# That is entirely in the fixtures, and ADR 0055 is where it is read.
#
# WHICH PHASE THIS IS (the live inconsistency M4 was asked to settle): `DEVELOPMENT_PLAN` §6 schedules the
# battery in **Phase 6**, while `MEMORY.md`/`STEERING_PROMPT.md` put it in **P3** and the pre-M4 scaffold
# in this file said "Phase-6 scaffold". Resolved as: it is Phase-6 WORK, pulled forward into P3 / line M
# because everything it needs — a coupled S+F+E loop over five biome cells, a C oracle for demography, and
# a 20-year forcing window — exists now, and because ADR 0054's unanchored count recursion is precisely
# the failure mode the battery detects. There is no Phase-6 scaffold left; these are the tests.

@testitem "Resilience battery — the lag-1 autocorrelation estimator" tags = [:resilience] begin
    using LPJmLFITEmulator
    using Test
    using StableRNGs

    # The estimator the whole battery is built on, in the SAME form as both measurement scripts
    # (scripts/extract_resilience_reference.py :: acf_rows/detrend_rows and
    # scripts/biome_resilience_probe.jl :: acf/detrend). A drift between the three would invent a gap
    # between the emulator and the C oracle out of nothing, so it is pinned here against series whose
    # answer is known analytically.
    function lag1_autocorr(x)
        n = length(x)
        μ = sum(x) / n
        num = sum((x[t] - μ) * (x[t - 1] - μ) for t in 2:n)
        den = sum((x[t] - μ)^2 for t in 1:n)
        return num / den
    end
    function detrend(x)
        n = length(x)
        t = collect(0.0:(n - 1))
        tc = t .- sum(t) / n
        slope = sum(x .* tc) / sum(tc .^ 2)
        return x .- sum(x) / n .- slope .* tc
    end

    # Deterministic (seeded) AR(1): xₜ = φ·xₜ₋₁ + εₜ.
    function ar1(rng, φ, n)
        x = zeros(n)
        for t in 2:n
            x[t] = φ * x[t - 1] + randn(rng)
        end
        return x
    end

    # Estimator recovers the AR(1) memory coefficient (large n ⇒ tight standard error).
    φ = 0.7
    x = ar1(StableRNG(20260716), φ, 100_000)
    @test isapprox(lag1_autocorr(x), φ; atol = 0.02)

    # A memoryless (white-noise) series has ~zero lag-1 autocorrelation.
    w = randn(StableRNG(11), 100_000)
    @test abs(lag1_autocorr(w)) < 0.02

    # ── METHOD CHOICE (a): DETREND FIRST. A pure linear ramp has NO memory but lag-1 AC ≈ 1, so on the
    # transient 2000-2019 window an undetrended AC measures the trend, not the memory. The detrend must
    # (i) annihilate a ramp and (ii) leave a stationary AR(1)'s coefficient essentially untouched.
    ramp = collect(0.0:1.0:19.0)
    @test lag1_autocorr(ramp) > 0.8                      # the artefact the detrend exists to remove
    @test maximum(abs, detrend(ramp)) < 1.0e-12          # ...annihilated exactly
    y = ar1(StableRNG(4242), φ, 100_000)
    @test isapprox(lag1_autocorr(detrend(y)), φ; atol = 0.02)
    # ...and it removes a ramp ADDED to real memory, recovering the underlying φ.
    @test isapprox(lag1_autocorr(detrend(y .+ 0.05 .* collect(0.0:(length(y) - 1)))), φ; atol = 0.02)

    # ── METHOD CHOICE (b): at n = 20 the estimator is biased LOW by ~(1+3φ)/n — comparable to the whole
    # wet-to-dry gradient it is meant to resolve — and the Marriott-Pope/Kendall correction
    # φ̂ = (r₁ + 1/n)/(1 − 3/n) removes most of it. Measured over 400 independent 20-point AR(1) draws.
    n = 20
    raw = Float64[]
    for s in 1:400
        push!(raw, lag1_autocorr(detrend(ar1(StableRNG(9000 + s), 0.75, n))))
    end
    mraw = sum(raw) / length(raw)
    mcorr = sum((r + 1 / n) / (1 - 3 / n) for r in raw) / length(raw)
    @test mraw < 0.75 - 0.1                        # the bias is real and large at n = 20
    @test abs(mcorr - 0.75) < abs(mraw - 0.75)      # ...and the correction shrinks it
    # Both sides of the battery use the SAME estimator on the SAME n, so the residual bias cancels in
    # every emulator-vs-C comparison — which is why the gates below are on `ac1_detr`, not `ac1_debias`.
end

@testitem "Resilience battery (a) — autocorrelation vs climate, C reference + coupled miss" tags = [
    :resilience, :multicell, :scientific,
] begin
    using LPJmLFITEmulator
    using Test

    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
        hdr = split(strip(lines[1]), ',')
        rows = [split(strip(l), ',') for l in lines[2:end]]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end
    fnum(s) = isempty(strip(s)) ? NaN : parse(Float64, s)

    # ── the C reference: 52 224 cells (both seeds), 2000-2019, per-patch series, detrended ───────────
    grad = readcsv(joinpath(refdir, "M_resilience_reference_gradient.csv"))
    nbin = length(grad["bin"])
    @test nbin == 10
    ppet = fnum.(grad["p_pet_med"])
    @test issorted(ppet)                                   # bin 1 is the DRIEST decile
    @test all(>=(4000), parse.(Int, grad["ncell"]))        # each bin is a mean over thousands of cells

    # THE FINDING (ADR 0055). The '~0.2 in wet → ~0.75 in dry' gradient DEVELOPMENT_PLAN §5 quotes is NOT
    # present in this run on this basis: lag-1 AC is FLAT at 0.45-0.55 across all ten P/PET deciles, and
    # in the undetrended series it runs the other way (driest LOWEST). What IS strongly climate-graded is
    # the VARIANCE. Pinning the finding, not the quote — if a future basis or window does resolve the
    # documented gradient, this test must be updated deliberately, with the reason recorded.
    ac = fnum.(grad["n_patch_ac1_detr"])
    @test all(0.4 .< ac .< 0.6)                          # flat, and nowhere near 0.2 or 0.75
    @test maximum(ac) - minimum(ac) < 0.15                 # the whole range is smaller than the claim
    @test ac[1] < maximum(ac)                              # the DRIEST bin is not the highest-memory one
    acraw = fnum.(grad["n_patch_ac1_raw"])
    @test all(acraw .> ac)                                 # the trend inflates AC everywhere (choice (a))
    @test acraw[1] < acraw[end]                            # ...and even raw, dry is LOWER than wet
    # ...while the coefficient of variation spans nearly an order of magnitude, dry to wet.
    cv = fnum.(grad["n_patch_cv_detr"])
    @test cv[1] / cv[end] > 5.0
    @test issorted(cv[1:5]; rev = true)                    # monotone over the dry half
    # the seed1-vs-seed2 noise floor is small enough for the flatness to be a result, not noise
    @test all(fnum.(grad["n_patch_ac1_detr_floor"]) .< 0.1)

    # ── the five coupled biome cells, both seeds ─────────────────────────────────────────────────────
    cells = readcsv(joinpath(refdir, "M_resilience_reference_cells.csv"))
    names = String.(cells["name"])
    @test length(unique(names)) == 5
    for basis in ("patch", "cellmean"), var in ("n", "agb")
        idx = findall(i -> cells["basis"][i] == basis && cells["var"][i] == var, eachindex(names))
        @test length(idx) == 10                            # 5 cells x 2 seeds
        @test all(i -> isfinite(fnum(cells["ac1_detr"][i])), idx)
    end
    # the between-patch SD is what a SINGLE-trajectory estimate samples from — it must exist and be
    # substantial, because it is the yardstick the coupled miss below is expressed in
    pidx = findall(i -> cells["basis"][i] == "patch", eachindex(names))
    @test all(i -> 0.05 < fnum(cells["ac1_detr_psd"][i]) < 0.4, pidx)
    @test all(i -> isempty(strip(cells["ac1_detr_psd"][i])), findall(i -> cells["basis"][i] == "cellmean", eachindex(names)))

    # ── the COUPLED emulator against it (cluster-measured, pinned) ───────────────────────────────────
    bat = readcsv(joinpath(refdir, "M_resilience_battery.csv"))
    @test length(unique(String.(bat["name"]))) == 5
    @test Set(String.(bat["arm"])) == Set(["free0", "free1", "pin0", "pin1", "fonly0", "fonly1", "anchor0"])
    free = findall(i -> bat["arm"][i] == "free0", eachindex(bat["name"]))
    @test !isempty(free)
    @test all(i -> parse(Int, bat["nmember"][i]) >= 20, free)   # ~one member per patch of the C's 25
    # Every arm's ensemble mean must be a finite autocorrelation in (-1, 1) — a NaN here means a member
    # went constant or non-finite, which is a failure of the rollout, not of the metric.
    @test all(i -> -1.0 < fnum(bat["e_ac1"][i]) < 1.0, eachindex(bat["name"]))
    @test all(i -> fnum(bat["e_msd"][i]) > 0.0, eachindex(bat["name"]))
end

@testitem "Resilience battery (b) — recovery rate from a pool perturbation" tags = [
    :resilience, :multicell, :scientific,
] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
    using Test

    refdir = joinpath(@__DIR__, "references")
    _mean(x) = sum(x) / length(x)
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
    function readcanopy(path)
        ind = readcsv(path)
        v(k, r) = parse(Float64, ind[k][r]); nt(r) = parse(Int, ind["type"][r])
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

    patch_agb(core) = sum(
        (Float64(p.leaf_c) + Float64(p.sapwood_c) + Float64(p.heartwood_c)) * Float64(p.nind)
            for p in core.pools if !p.is_grass; init = 0.0
    )
    "Halve every tree carbon pool and re-derive height/crownarea through the model's OWN allometry, so
     the perturbed stand is self-consistent rather than tall and hollow."
    function perturb!(core, frac)
        for (i, p) in enumerate(core.pools)
            p.is_grass && continue
            lf = Float64(p.leaf_c) * frac; sw = Float64(p.sapwood_c) * frac
            h = LPJmLFITEmulator.tree_height(core.allom, sw, lf)
            core.pools[i] = TreePools{Float64}(
                lf, sw, Float64(p.heartwood_c) * frac, Float64(p.root_c) * frac,
                Float64(p.sapwood_bg_c) * frac, h, LPJmLFITEmulator.crown_area(core.allom, h),
                Float64(p.nind), Float64(p.sla), Float64(p.wooddens), false
            )
        end
    end

    # ── the COMPUTED arm: a real F+E rollout, `slow = nothing` so it needs no /p/tmp artifact ────────
    # The committed forcing is one decade, so a 30-year rollout CYCLES it. That is deliberate and it is
    # what makes the test readable: with a periodic forcing the control trajectory is periodic too, so
    # any departure of the perturbed run from it is the PERTURBATION relaxing, not climate.
    nyear, perturb_at, frac = 30, 11, 0.5
    function rollout(name, k; perturb::Bool = false)
        f = readcsv(joinpath(refdir, "biome_forcing_$(name).csv"))
        tairK = fcol(f, "temp") .+ 273.15
        swd = fcol(f, "swdown"); lwn = fcol(f, "lwnet"); prec = fcol(f, "precip")
        huss = fcol(f, "huss"); co2 = fcol(f, "co2")
        forc = [
            AtmForcing(;
                    swdown = swd[i], lwdown = lwn[i] + σ * tairK[i]^4, tair = tairK[i], qair = huss[i],
                    wind = 2.0, psurf = 1.0e5, precip = prec[i], co2 = co2[i]
                ) for i in eachindex(tairK)
        ]
        nyr_forc = length(forc) ÷ 365
        pools, tmpls = readcanopy(joinpath(refdir, "M_individuals_$(name)_2010.csv"))
        core = FDiffFastCore(pools, tmpls, readsoil(joinpath(refdir, "M_soilcolumn_$(name).txt")), lats[k])
        clo = SEBEnergyClosure(; t_soil0 = _mean(tairK))
        st = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
        out = Float64[]
        for y in 1:nyear
            (perturb && y == perturb_at) && perturb!(core, frac)
            sy = mod1(y, nyr_forc)
            run_coupled_cell(core, clo, st, view(forc, ((sy - 1) * 365 + 1):(sy * 365)); days_per_year = 365)
            push!(out, patch_agb(core))
        end
        return out
    end

    for name in ("temperate_hainich", "tropical_amazon")
        k = findfirst(==(name), names)
        ctrl = rollout(name, k)
        pert = rollout(name, k; perturb = true)
        @test all(isfinite, ctrl) && all(>(0.0), ctrl)
        @test all(isfinite, pert) && all(>(0.0), pert)
        # identical before the perturbation — the two arms are the same trajectory until it is applied
        @test ctrl[1:(perturb_at - 1)] == pert[1:(perturb_at - 1)]
        # the perturbation actually bit: half the carbon is gone at the end of the perturbed year
        d = [abs(ctrl[y] - pert[y]) / ctrl[y] for y in perturb_at:nyear]
        @test d[1] > 0.25
        # ...and it RELAXES. Measured on these two cells the departure falls to 0.42x / 0.48x of its
        # initial size over the 19 remaining years and is strictly monotone; the bounds are set from
        # that with margin, because how FAST a cell relaxes is genuinely cell-dependent (the Sahel
        # relaxes to only 0.92x in the same span, and the mediterranean cell wobbles non-monotonically).
        # What is being gated is that it relaxes AT ALL and does not oscillate: a departure that grew
        # would be an unstable equilibrium, one that never shrank an alternative state.
        @test d[end] < 0.7 * d[1]
        @test all(i -> d[i] <= d[i - 1] + 0.02 * d[1], 3:length(d))
        # a finite, positive e-folding time from the log-linear fit — the metric the fixture reports
        yy = Float64[]; ll = Float64[]
        for (i, v) in enumerate(d)
            v > 1.0e-4 || continue
            push!(yy, Float64(i - 1)); push!(ll, log(v))
        end
        @test length(yy) >= 5
        ybar = _mean(yy); lbar = _mean(ll)
        slope = sum((yy .- ybar) .* (ll .- lbar)) / sum((yy .- ybar) .^ 2)
        @test slope < 0.0
        @test 0.5 < -1 / slope < 200.0
    end

    # ── the CLUSTER-measured coupled recovery, pinned ────────────────────────────────────────────────
    # 100 years of cycled forcing, FULL coupled S+F+E, tree carbon pools halved at year 21. The measured
    # structure is four cells relaxing with an e-folding time of 47-54 yr at r² 0.60-0.73 and ONE
    # (`semiarid_sahel`) that essentially does not recover on a century: τ 602 yr at r² 0.38, i.e. not a
    # single exponential either. That asymmetry is the result (ADR 0055 §6) — so the gate pins the
    # STRUCTURE rather than an average, which would hide it.
    lr = readcsv(joinpath(refdir, "M_resilience_battery_longrun.csv"))
    @test length(lr["name"]) == 5
    @test all(s -> strip(s) == "true", lr["finite"])          # 100 years, no NaN, no non-positive AGB
    taus = parse.(Float64, lr["tau_rec"])
    r2s = parse.(Float64, lr["r2"])
    @test all(isfinite, taus)
    @test all(>(0.0), taus)                                   # every cell relaxes; none diverges
    @test count(t -> 0.0 < t < 100.0, taus) >= 4              # four recover on a decadal-to-century scale
    @test count(>(0.55), r2s) >= 4                            # ...and for those it IS ~a single exponential
    @test all(x -> parse(Float64, x) < 1.0e-6, lr["resid"])   # carbon still closes through all of it
    # THE TIMESCALE MISMATCH (ADR 0055 §6): the AC-implied AR(1) restoring time is ~2-3 yr while the
    # measured pool-perturbation recovery is ~50 yr — a ~20× gap. They are different quantities (fast
    # year-to-year fluctuation vs slow biomass regrowth), so an AC cannot be read as a recovery rate.
    bat2 = readcsv(joinpath(refdir, "M_resilience_battery.csv"))
    ftau = [
        parse(Float64, bat2["e_tau"][i]) for i in eachindex(bat2["name"])
            if bat2["arm"][i] == "free0" && bat2["var"][i] == "agb"
    ]
    @test all(t -> 0.8 < t < 8.0, ftau)          # measured 1.20-2.87 yr
    @test minimum(t for t in taus if t < 100.0) > 5.0 * maximum(ftau)
end

@testitem "Resilience battery (c) — the shuffle test: internal vs inherited memory" tags = [
    :resilience, :multicell, :scientific,
] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
    using Test

    refdir = joinpath(@__DIR__, "references")
    _mean(x) = sum(x) / length(x)
    function readcsv(path)
        lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
        hdr = split(strip(lines[1]), ',')
        rows = [split(strip(l), ',') for l in lines[2:end]]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end
    fcol(d, k) = parse.(Float64, d[k])
    fnum(s) = isempty(strip(s)) ? NaN : parse(Float64, s)
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
    function readcanopy(path)
        ind = readcsv(path)
        v(k, r) = parse(Float64, ind[k][r]); nt(r) = parse(Int, ind["type"][r])
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
    function detrend(x)
        n = length(x); t = collect(0.0:(n - 1)); tc = t .- sum(t) / n
        return x .- sum(x) / n .- (sum(x .* tc) / sum(tc .^ 2)) .* tc
    end
    function ac1(x)
        d = detrend(x); n = length(d)
        return sum(d[t] * d[t - 1] for t in 2:n) / sum(abs2, d)
    end

    σ = 5.670374419e-8
    cells = readcsv(joinpath(refdir, "M_cells.csv"))
    names = String.(cells["name"]); lats = fcol(cells, "lat")

    patch_agb(core) = sum(
        (Float64(p.leaf_c) + Float64(p.sapwood_c) + Float64(p.heartwood_c)) * Float64(p.nind)
            for p in core.pools if !p.is_grass; init = 0.0
    )

    # ── the COMPUTED shuffle test on F's own carbon pools (`slow = nothing`, artifact-independent) ───
    # S0 replays the committed decade in its real order, cycled to 30 years; S1 replays the SAME ten
    # years in a fixed shuffled order. If the state's autocorrelation collapsed under S1 the memory
    # would be inherited from the climate's sequencing; if it survives, the memory is INTERNAL. This
    # arm can only speak for F's pools — Component S's demographic memory is in the fixture below,
    # because the count model needs the /p/tmp pin CI has no cluster for.
    nyear = 30
    order1 = [4, 9, 1, 7, 3, 10, 6, 2, 8, 5]        # a fixed permutation: the test must be deterministic
    @test sort(order1) == collect(1:10)
    function rollout(name, k, order)
        f = readcsv(joinpath(refdir, "biome_forcing_$(name).csv"))
        tairK = fcol(f, "temp") .+ 273.15
        swd = fcol(f, "swdown"); lwn = fcol(f, "lwnet"); prec = fcol(f, "precip")
        huss = fcol(f, "huss"); co2 = fcol(f, "co2")
        forc = [
            AtmForcing(;
                    swdown = swd[i], lwdown = lwn[i] + σ * tairK[i]^4, tair = tairK[i], qair = huss[i],
                    wind = 2.0, psurf = 1.0e5, precip = prec[i], co2 = co2[i]
                ) for i in eachindex(tairK)
        ]
        pools, tmpls = readcanopy(joinpath(refdir, "M_individuals_$(name)_2010.csv"))
        core = FDiffFastCore(pools, tmpls, readsoil(joinpath(refdir, "M_soilcolumn_$(name).txt")), lats[k])
        clo = SEBEnergyClosure(; t_soil0 = _mean(tairK))
        st = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
        out = Float64[]
        for y in 1:nyear
            sy = order[mod1(y, length(order))]
            run_coupled_cell(core, clo, st, view(forc, ((sy - 1) * 365 + 1):(sy * 365)); days_per_year = 365)
            push!(out, patch_agb(core))
        end
        return out
    end

    for name in ("temperate_hainich", "tropical_amazon")
        k = findfirst(==(name), names)
        s0 = rollout(name, k, collect(1:10))
        s1 = rollout(name, k, order1)
        @test all(isfinite, s0) && all(isfinite, s1)
        @test s0 != s1                                   # the shuffle genuinely changed the trajectory
        # THE SHUFFLE TEST: destroying the forcing's own year-to-year sequencing must NOT collapse the
        # state's autocorrelation — F's carbon pools are a real internal store with a multi-year
        # turnover time, and that memory belongs to the model, not to the climate.
        @test ac1(s1) > 0.5
        # ...and the two are close, i.e. very little of the memory was inherited in the first place.
        @test abs(ac1(s0) - ac1(s1)) < 0.4
        # the control that makes the test non-vacuous: the shuffled FORCING itself supplies no positive
        # memory, so a model with no internal store would score at or below 0 here, not >0.5. One-sided
        # on purpose — a shuffled-then-cycled sequence can be strongly NEGATIVELY autocorrelated
        # (measured −0.49 at Hainich), which is not memory the state could inherit.
        f = readcsv(joinpath(refdir, "biome_forcing_$(name).csv"))
        annual_t = [_mean(fcol(f, "temp")[((y - 1) * 365 + 1):(y * 365)]) for y in 1:10]
        @test ac1([annual_t[order1[mod1(y, 10)]] for y in 1:nyear]) < 0.4
    end

    # ── the CLUSTER-measured coupled decomposition, pinned (ADR 0055) ────────────────────────────────
    sh = readcsv(joinpath(refdir, "M_resilience_battery_shuffle.csv"))
    @test length(sh["name"]) == 10                       # 5 cells x {n, agb}
    @test Set(String.(sh["var"])) == Set(["n", "agb"])
    # a frozen roster has no count series, so `fonly1` is NaN for var=n by construction, not by failure
    nrows = findall(i -> sh["var"][i] == "n", eachindex(sh["name"]))
    arows = findall(i -> sh["var"][i] == "agb", eachindex(sh["name"]))
    @test all(i -> isnan(fnum(sh["fonly1"][i])), nrows)
    @test all(i -> isfinite(fnum(sh["fonly1"][i])), arows)
    for i in eachindex(sh["name"])
        @test isfinite(fnum(sh["free0"][i])) && isfinite(fnum(sh["free1"][i]))
        @test isfinite(fnum(sh["pin1"][i]))
        # The decomposition is an identity, not two independent numbers. `atol` is 3e-6, not 0: the
        # fixture prints `%.6f`, so each of the three operands is independently rounded to 1e-6 and the
        # identity can only close to a few ulps of THAT. A tighter tolerance tests the print format.
        @test isapprox(
            fnum(sh["inherited"][i]), fnum(sh["free0"][i]) - fnum(sh["free1"][i]); atol = 3.0e-6
        )
        @test isapprox(
            fnum(sh["recursion"][i]), fnum(sh["free1"][i]) - fnum(sh["pin1"][i]); atol = 3.0e-6
        )
    end
    # THE COUPLED VERDICT (measured, ADR 0055 §5): memory survives the shuffle in every cell and on both
    # variables ⇒ INTERNAL. `free1` came out 0.460-0.653; the bound is set below that with margin.
    @test all(i -> fnum(sh["free1"][i]) > 0.3, eachindex(sh["name"]))
    # ...and almost none of it was inherited in the first place: destroying the climate's own year-to-year
    # sequencing moves the AC by at most 0.15 in either direction (measured −0.146 … +0.077).
    @test all(i -> abs(fnum(sh["inherited"][i])) < 0.25, eachindex(sh["name"]))
    # F's carbon pools alone (no demography at all) already carry most of it — 0.454-0.691 measured.
    @test all(i -> fnum(sh["fonly1"][i]) > 0.3, arows)
    # ...and it is not merely the DRF's explicit count-space AR feature: pinning `s.n_prev` to a constant
    # leaves substantial memory behind. (ADR 0054 showed the recursion is real and compounds; this shows
    # it is not the whole story, which is what makes the shuffle test non-cheatable here.) `pin` is not a
    # total memory-removal control — the DENSITY update stays recursive — so what it leaves is memory
    # reaching the count model through F's canopy features, which is precisely the term being separated.
    @test all(i -> fnum(sh["pin1"][i]) > 0.25, eachindex(sh["name"]))
    # ...and the recursion contributes essentially NOTHING to the autocorrelation: |free1 − pin1|
    # is ≤ 0.14 everywhere. ADR 0054's unanchored AR drives the count LEVEL drift, not the memory
    # timescale — which is why the shuffle test needed the control to be able to say so.
    @test all(i -> abs(fnum(sh["recursion"][i])) < 0.25, eachindex(sh["name"]))
end
