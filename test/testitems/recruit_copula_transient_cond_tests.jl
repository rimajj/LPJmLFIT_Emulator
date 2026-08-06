# ADR 0108 — gate the TRANSIENT extended recruit-copula conditioning (`live_flux_cond_env_series`).
#
# WHY THIS FILE EXISTS. With the ADR-0037 tail the six moisture descriptors are per-cell CONSTANTS, so the
# slow moisture climate FIT's establishment gates key on cannot reach the sampled marginal at all. (It does NOT
# follow that the emulator has no trait response: that tail is 6 of 14 columns and the rest are transient — the
# measured per-cell scenario response on the shipped generation has slope +0.85 on SLA and +0.16 on D95max,
# ADR 0108 §1.) `live_flux_cond_env_series` is the runtime half of opening the frozen channel; the training
# half is `ENV_WINDOW` in `scripts/build_slow_runtime_table.py`.
#
# Its failure mode is the worst kind (ADR 0023, and the reason the ADR-0038 constructor probe exists at all):
# a static-tail artifact and a transient-tail artifact have the SAME `ncond` and the SAME `cond_cols`, so the
# construction-time width check passes for EITHER policy paired with EITHER artifact. Nothing in the widths,
# the format, or a completed coupled run distinguishes them — only the manifest's `env_basis` line does. So
# what has to be pinned here is not the width (ADR 0038 already covers that) but the SEMANTICS: that the tail
# advances with the simulation year, that it advances in lockstep with `boundary_series` rather than one year
# apart, and that a constant series reproduces the static policy exactly.
#
# Hermetic: small synthetic forests, no committed artifact, no cluster data.

@testitem "Transient conditioning: live_flux_cond_env_series advances the tail by year (ADR 0108)" tags = [:scientific] begin
    using LPJmLFITEmulator
    using Test

    boundary = [3346.7, -2.9, 15.3, 369.0]
    feats = collect(1.0:15.0)                       # a full flux_feature_vector row (11 head + 4 boundary)
    # Three years of a DRYING tail (vpd rising, p_pet falling) — the shape the transient tables carry.
    series = [
        [935.4, 0.981, 95.6, 0.581, 0.535, 0.0076],
        [921.0, 0.952, 97.9, 0.604, 0.541, 0.0074],
        [902.7, 0.918, 101.2, 0.633, 0.549, 0.0071],
    ]
    pol = live_flux_cond_env_series(series)

    # The policy reads ONLY `s.boundary` and `s.year`, so a NamedTuple is a faithful stub — and it is the SAME
    # stub shape the constructor's width probe uses, deliberately.
    for (yr, want) in ((0, series[1]), (1, series[2]), (2, series[3]))
        row = pol((boundary = boundary, year = yr), feats)
        @test length(row) == 4 + length(boundary) + length(series[1])
        @test row[1:4] == feats[1:4]
        @test row[5:8] == boundary
        @test row[9:14] == want
    end
    # POST-SERIES years CLAMP to the last row (the boundary_series rule, so a run longer than the forcing
    # holds the final climate instead of erroring or wrapping around to the present day).
    for yr in (3, 4, 97)
        @test pol((boundary = boundary, year = yr), feats)[9:14] == series[end]
    end

    # A CONSTANT series must reproduce `live_flux_cond_env` exactly — the guardrail-4 statement that the new
    # policy is a strict generalisation and cannot perturb a static-tail configuration.
    env = series[1]
    const_pol = live_flux_cond_env_series([copy(env) for _ in 1:5])
    static_pol = live_flux_cond_env(env)
    for yr in 0:6
        s = (boundary = boundary, year = yr)
        @test const_pol(s, feats) == static_pol(s, feats)
    end

    # Rows are COPIED in, so mutating the caller's series afterwards cannot silently re-condition a run
    # mid-flight (these vectors come from a per-cell CSV/parquet read that a driver may well reuse).
    mut = [[1.0, 2.0], [3.0, 4.0]]
    pol2 = live_flux_cond_env_series(mut)
    mut[1][1] = 99.0
    @test pol2((boundary = Float64[], year = 0), feats)[5:6] == [1.0, 2.0]

    # Malformed input fails LOUD at construction, not at the first recruiting patch.
    @test_throws ErrorException live_flux_cond_env_series(Vector{Float64}[])
    @test_throws ErrorException live_flux_cond_env_series([[1.0, 2.0], [3.0]])
end

@testitem "Transient conditioning: the env tail and boundary_series are read at the SAME year (ADR 0108)" tags = [:scientific] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
    using LPJmLFITEmulator.DRF
    using Test

    # WHY THIS IS SEPARATE FROM THE STUB TEST ABOVE: an off-by-one between the two series is invisible in
    # every width and format check, produces a completed run, and would condition each year's recruits on the
    # NEXT year's moisture while the count model saw this year's temperature. `reconcile_demography!` advances
    # `s.boundary` from `boundary_series` at `clamp(s.year + 1, 1, end)` and calls `rc.cond(s, feats)` in the
    # same invocation, before `s.year += 1` — so the two must use identical indexing. This drives the REAL
    # struct (not a stub) by stepping `s.year`, which exercises that indexing without needing forcing data.
    function tinyf(seed, nfeat)
        r = DRF.Xoshiro256pp(seed)
        m = 400
        X = Matrix{Float64}(undef, m, nfeat)
        y = Vector{Float64}(undef, m)
        for i in 1:m
            for ff in 1:nfeat
                X[i, ff] = DRF.rand01!(r)
            end
            y[i] = X[i, 1]
        end
        return DRF.fit_forest(X, y; ntrees = 3, subsample = 200, seed = seed, store_values = true)
    end

    nb = 4
    nenv = 6
    ncond = 4 + nb + nenv
    cop = DRF.GaussianCopula([1.0 0.2; 0.2 1.0])
    to_pools = make_recruit_to_pools(["SLA", "Wooddens"])
    f14 = [tinyf(21, ncond), tinyf(22, ncond)]

    # Boundary and env series with the SAME number of years and per-year-distinguishable values, so an
    # off-by-one in either one shows up as a mismatch between them.
    nyr = 5
    bser = [[3000.0 + 100.0 * k, -5.0 + 0.5 * k, 15.3, 369.0] for k in 0:(nyr - 1)]
    eser = [[900.0 + k, 0.9 + 0.01 * k, 95.0 + k, 0.5 + 0.01 * k, 0.53, 0.007] for k in 0:(nyr - 1)]

    rc = RecruitCopula{Float64}(
        cop, f14, collect(1.0:Float64(ncond)), to_pools, live_flux_cond_env_series(eser)
    )

    pool = TreePools{Float64}(15.0, 30.0, 5.0, 15.0, 0.0, 12.0, 0.5, 0.1, 0.02, 2.0e5, false)
    tmpl = Individual{Float64}(
        0.6, 0.0, 0.5, 0.15, 5.0, 30.0, 15.0, 0.0, 0.02, 0.04, 0.1, 0.4, 0.1,
        PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.02),
        TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false,
    )
    soil = hainich_soilcolumn(;
        whcs = fill(0.15, LPJmLFITEmulator.NSOILLAYER),
        rootdist = fill(1.0 / LPJmLFITEmulator.NSOILLAYER, LPJmLFITEmulator.NSOILLAYER),
        soildepth = fill(200.0, LPJmLFITEmulator.NSOILLAYER),
    )
    fc = FDiffFastCore([pool], [tmpl], soil, 51.25)
    countf = tinyf(23, 11 + nb)

    # The width probe must ACCEPT a series policy — it stubs `year = 0`, so a policy that reads `s.year`
    # is probed at its first row rather than throwing on a missing field.
    s = FluxDrivenSlowEmulator(
        fc, countf; boundary_series = bser, recruit_copula = rc, n_init = 4.0
    )
    @test s isa FluxDrivenSlowEmulator
    @test s.boundary == bser[1]              # seeded from the series' first row (ADR 0026)

    feats = collect(1.0:Float64(11 + nb))
    for yr in 0:(nyr + 1)
        s.year = yr
        # Reproduce reconcile_demography!'s own boundary advance, then build the conditioning row the same
        # way the recruit path does.
        s.boundary = bser[clamp(s.year + 1, 1, length(bser))]
        row = rc.cond(s, feats)
        k = clamp(yr + 1, 1, nyr)
        @test length(row) == ncond
        @test row[5:8] == bser[k]            # boundary from year k ...
        @test row[9:14] == eser[k]           # ... and the env tail from the SAME k, never k±1
    end

    # And the mis-pairing the widths cannot catch: a transient-tail artifact wired with the STATIC policy
    # constructs fine (identical width) — which is exactly why `env_basis` is the contract and not the width.
    rc_static = RecruitCopula{Float64}(
        cop, f14, collect(1.0:Float64(ncond)), to_pools, live_flux_cond_env(eser[1])
    )
    @test FluxDrivenSlowEmulator(
        fc, countf; boundary_series = bser, recruit_copula = rc_static
    ) isa FluxDrivenSlowEmulator
    # It is legal to construct and WRONG to run: from year 2 on it conditions on the first year's moisture.
    s2 = FluxDrivenSlowEmulator(fc, countf; boundary_series = bser, recruit_copula = rc_static)
    s2.year = 3
    s2.boundary = bser[4]
    @test rc_static.cond(s2, feats)[9:14] == eser[1]     # frozen — the defect ADR 0108 removes
    @test rc.cond(s2, feats)[9:14] == eser[4]            # the transient policy tracks the year
end
