# Gate 4 — Rollout / autoregressive stability (ENGINEERING_STANDARDS §2, item 4).
# A synthetic bounded-storage rollout via `flux_then_integrate` stays non-negative and bounded over
# many steps (no blow-up), and — since M4 (ADR 0055) — a REAL multi-decadal coupled rollout is checked
# for the stiff carbon+population failure mode `LPJ_resilience` flags: a spurious limit cycle, an
# unbounded drift, or an "AC gap" against the LPJmL-FIT reference.
@testitem "Rollout stability" tags = [:rollout, :stability] begin
    using LPJmLFITEmulator
    using Test

    # ── REAL synthetic rollout: leaky-bucket dynamics  newₜ = max(0.9·stateₜ + input, 0) ─────────
    # Contractive (factor 0.9) with bounded forcing ⟹ converges to input/0.1, never blows up.
    nstep = 5000
    input = fill(2.0, 6)
    state = fill(50.0, 6)
    bound = maximum(input) / 0.1 * 1.5 + maximum(state)   # generous a-priori envelope

    ok_nonneg = true
    ok_finite = true
    ok_bounded = true
    for _ in 1:nstep
        increments = -0.1 .* state .+ input               # decay toward the steady state
        state = flux_then_integrate(state, increments)
        ok_nonneg &= all(≥(0.0), state)                  # clamp guarantees non-negativity
        ok_finite &= all(isfinite, state)
        ok_bounded &= all(≤(bound), state)                # bounded — no blow-up
    end
    @test ok_nonneg
    @test ok_finite
    @test ok_bounded
    # Converged near the analytic steady state input/0.1 = 20.
    @test all(s -> isapprox(s, 20.0; atol = 1.0e-6), state)
end

@testitem "Rollout stability — multi-decadal coupled rollout: no blow-up, no limit cycle, no AC gap" tags = [
    :rollout, :stability, :multicell, :scientific,
] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
    using Test

    # M4 / ADR 0055. Same CI-vs-cluster split as the resilience battery: the COMPUTED arm here is a real
    # 60-year F+E rollout with `slow = nothing` (artifact-independent, so CI can run it), and the pinned
    # fixture carries the 100-year FULL coupled S+F+E rollout that needs the /p/tmp `_t8` pair.
    # The committed forcing is one decade, so a 60-year rollout CYCLES it — which is exactly the right
    # experiment for this gate: with a periodic forcing the ONLY thing that can produce a trend or a
    # growing oscillation is the model's own dynamics.
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

    nyear = 60
    for name in ("temperate_hainich", "boreal_siberia")
        k = findfirst(==(name), names)
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
        agb = Float64[]; resid = 0.0
        for y in 1:nyear
            sy = mod1(y, nyr_forc)
            out = run_coupled_cell(
                core, clo, st, view(forc, ((sy - 1) * 365 + 1):(sy * 365)); days_per_year = 365
            )
            resid = max(resid, maximum(abs, out.resid))
            push!(agb, patch_agb(core))
        end

        @test all(isfinite, agb)
        @test all(>(0.0), agb)
        @test resid < 1.0e-6                                # energy still closes after 60 years
        # BOUNDED: no blow-up and no collapse. The band is wide on purpose — F alone with a frozen
        # roster is expected to drift (ADR 0053 measured −13.5 % to +64.5 % FPC over ten years); what
        # this gate forbids is an unbounded run, not a drift.
        @test maximum(agb) / agb[1] < 10.0
        @test minimum(agb) / agb[1] > 0.05
        # NO SPURIOUS LIMIT CYCLE. A two-year flip-flop — the stiff carbon+population failure mode
        # LPJ_resilience flags — makes essentially every first difference change sign. White noise sits
        # at 0.5; a smooth trajectory well below it. Anything approaching 1.0 is the failure.
        d = diff(agb)
        osc = count(i -> sign(d[i]) != sign(d[i - 1]), 2:length(d)) / (length(d) - 1)
        @test osc < 0.8
        # ...and the oscillation must not GROW: the second half's year-to-year amplitude cannot be
        # several times the first half's, which is what a developing instability looks like.
        h = length(d) ÷ 2
        amp1 = _mean(abs.(d[1:h])); amp2 = _mean(abs.(d[(h + 1):end]))
        @test amp2 < 5.0 * amp1 + 1.0e-9
    end

    # ── THE AC GAP, cluster-measured and pinned (ADR 0055) ───────────────────────────────────────────
    # "AC gap" = the coupled emulator's lag-1 autocorrelation minus the C oracle's, in units of the C's
    # own between-patch SD — the spread a single 20-year patch series samples from, which is the right
    # yardstick for a one-trajectory estimate. A large gap in EITHER direction is a dynamics failure:
    # too much memory is a stiff/over-damped rollout, too little is a memoryless one.
    bat = readcsv(joinpath(refdir, "M_resilience_battery.csv"))
    free = findall(i -> bat["arm"][i] == "free0", eachindex(bat["name"]))
    @test length(free) == 10                                       # 5 cells × {n, agb}
    gaps = [parse(Float64, bat["d_over_psd"][i]) for i in free]
    @test all(isfinite, gaps)
    # MEASURED (ADR 0055 §4): the deployed `free0` arm sits 0.1-0.6 between-patch SDs from the C on every
    # cell and both variables — mean 0.32, max 0.6. There is no AC gap. Bounds set ~3x above that.
    @test _mean(gaps) < 1.0
    @test maximum(gaps) < 2.0

    lr = readcsv(joinpath(refdir, "M_resilience_battery_longrun.csv"))
    @test length(lr["name"]) == 5
    # the 100-year FULL coupled rollout, on cyclic forcing: finite, bounded, and not oscillating
    @test all(s -> strip(s) == "true", lr["finite"])
    @test all(x -> 0.05 < parse(Float64, x) < 20.0, lr["min_over_init"])
    @test all(x -> 0.05 < parse(Float64, x) < 20.0, lr["max_over_init"])
    # NO limit cycle: `osc` came out 0.06-0.50, i.e. at or below the white-noise value of 0.5 everywhere,
    # nowhere near the ->1 of a two-year flip-flop.
    @test all(x -> parse(Float64, x) < 0.8, lr["osc"])
    # ⚠ WHAT THIS DOES *NOT* SAY (ADR 0055 §6, an open finding, not a passing grade): under CYCLIC
    # forcing the coupled AGB does not reach a steady state — it drifts 1.39-5.15x over the century
    # (`min_over_init` 0.30-1.00, `max_over_init` 1.91-12.45). The gate bounds that drift; it does not
    # bless it. A model at equilibrium under a periodic forcing would sit at drift ≈ 1.
    @test all(x -> 0.2 < parse(Float64, x) < 10.0, lr["drift"])
    @test all(x -> parse(Float64, x) < 1.0e-6, lr["resid"])
end
