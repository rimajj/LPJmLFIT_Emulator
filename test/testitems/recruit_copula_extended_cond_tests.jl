# ADR 0037/0038 — gate the EXTENDED recruit-copula conditioning path (`ncond` > 8) end to end.
#
# WHY THIS FILE EXISTS. `live_flux_cond_env` and the `COPULA_ENV_COLS` builder knob shipped together, but an
# audit of the S2 matrix found the width they exist for was never exercised anywhere: `live_flux_cond_env`
# had ZERO callers in `src`/`scripts`/`test`, and no `.rcop` had ever been trained at `ncond` = 14. So the
# whole train -> artifact -> runtime chain was untested at the only width that makes the feature meaningful,
# and its failure mode is the WORST kind:
#
#   * `DRF._leaf` reads `x[f]` inside `@inbounds`. Querying a 14-feature forest with the 8-column
#     `live_flux_cond` row was therefore an out-of-bounds HEAP READ, not a `BoundsError` — it routed the
#     traversal on whatever bytes followed `x` and returned a plausible, in-range trait.
#   * Nothing else caught it: `sample_copula!` validated only `length(axis_forests) == cop.d`, and
#     `load_copula` never compared its header `ncond` against the marginals' `nfeat`.
#
# These testitems pin the guards that close it, and the conditioning-order contract they protect. They use
# small synthetic forests (no committed artifact, no cluster data), so they are cheap and hermetic.

@testitem "Extended conditioning: a 14-column .rcop round-trips and live_flux_cond_env builds its row (ADR 0037)" tags = [:scientific] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.DRF
    using Test

    NCOND = 14                      # 4 flux + 4 boundary + 6 env — the measured S2 configuration
    NAXES = 4

    function axis_forest(seed, lo, hi; nf = NCOND)
        r = DRF.Xoshiro256pp(seed)
        m = 1200
        X = Matrix{Float64}(undef, m, nf)
        y = Vector{Float64}(undef, m)
        for i in 1:m
            for ff in 1:nf
                X[i, ff] = DRF.rand01!(r)
            end
            # depend on a column in the ENV TAIL (9) as well as a flux column (1), so a row built with the
            # wrong width or the wrong order cannot accidentally agree.
            y[i] = lo + (hi - lo) * (0.5 * X[i, 1] + 0.5 * X[i, 9])
        end
        return DRF.fit_forest(X, y; ntrees = 12, subsample = 600, mtry = 5, seed = seed, store_values = true)
    end

    axis_names = ["SLA", "Wooddens", "D95max", "minwscal"]
    # EXACTLY the production order: HEAD_COLS[1:4] + BOUNDARY_COLS + COPULA_ENV_COLS
    # (scripts/build_slow_runtime_table.py). This list IS the contract the runtime must reproduce.
    cond_cols = [
        "bm_inc_cell", "growth_eff", "water_stress", "soilmoist",
        "eco_diag_gdd_5", "tas_cold_month", "soil_depth", "co2",
        "prec_mean", "eco_diag_p_pet_ratio", "eco_diag_pet_mean", "eco_diag_vpd_mean",
        "pr_cv_monthly", "humid_mean",
    ]
    @test length(cond_cols) == NCOND

    forests = [
        axis_forest(101, 0.005, 0.07), axis_forest(102, 7.0e4, 6.5e5),
        axis_forest(103, 20.0, 1200.0), axis_forest(104, 0.025, 0.75),
    ]
    @test all(f -> f.nfeat == NCOND, forests)

    R = Matrix{Float64}(undef, NAXES, NAXES)
    for i in 1:NAXES, j in 1:NAXES
        R[i, j] = i == j ? 1.0 : 0.15
    end
    cop = DRF.GaussianCopula(R)
    x = collect(range(0.1, 0.9; length = NCOND))

    draws_before = [DRF.sample_copula!(DRF.Xoshiro256pp(s), cop, forests, x) for s in 1:20]

    dir = mktempdir()
    path = joinpath(dir, "extended.rcop")
    DRF.save_copula(path, cop, forests, axis_names, cond_cols, x)
    cop2, af2, x2, names2, cols2 = DRF.load_copula(path)

    # load_copula's NEW consistency checks accept a self-consistent artifact ...
    @test length(cols2) == NCOND
    @test cols2 == cond_cols
    @test all(f -> f.nfeat == NCOND, af2)
    @test x2 == x
    @test names2 == axis_names
    # ... and the round trip is BITWISE, as for the 8-column artifacts (guardrail 4 discipline).
    draws_after = [DRF.sample_copula!(DRF.Xoshiro256pp(s), cop2, af2, x2) for s in 1:20]
    @test draws_after == draws_before

    # THE RUNTIME SIDE. `live_flux_cond_env(env)` must build exactly `ncond` columns in `cond_cols` order:
    # feats[1:4], then s.boundary, then the env tail.
    boundary = [3346.7, -2.9, 15.3, 369.0]
    env = [935.4, 0.981, 95.6, 0.581, 0.535, 0.0076]
    feats = collect(1.0:15.0)                       # a full flux_feature_vector row (11 head + 4 boundary)
    s = (boundary = boundary,)                      # the policies read ONLY `s.boundary`
    row = live_flux_cond_env(env)(s, feats)
    @test length(row) == NCOND
    @test length(row) == 4 + length(boundary) + length(env)   # the documented arithmetic to check
    @test row[1:4] == feats[1:4]
    @test row[5:8] == boundary
    @test row[9:14] == env
    # It is queryable against the artifact (the whole point) ...
    @test isfinite(DRF.predict_quantile(af2[1], row, 0.5))
    # ... and the DEFAULT 8-column policy is now a LOUD error against it, not a silent OOB heap read.
    row8 = live_flux_cond(s, feats)
    @test length(row8) == 8
    @test_throws DimensionMismatch DRF.predict_quantile(af2[1], row8, 0.5)
    @test_throws DimensionMismatch DRF.sample_copula!(DRF.Xoshiro256pp(1), cop2, af2, row8)
end

@testitem "load_copula REJECTS an ncond/nfeat-inconsistent .rcop instead of drawing from it (ADR 0038)" tags = [:scientific] begin
    using LPJmLFITEmulator.DRF
    using Test

    # A minimal but valid 2-axis, 3-feature artifact.
    function tiny(seed)
        r = DRF.Xoshiro256pp(seed)
        m = 400
        X = Matrix{Float64}(undef, m, 3)
        y = Vector{Float64}(undef, m)
        for i in 1:m
            for ff in 1:3
                X[i, ff] = DRF.rand01!(r)
            end
            y[i] = X[i, 1]
        end
        return DRF.fit_forest(X, y; ntrees = 4, subsample = 200, mtry = 3, seed = seed, store_values = true)
    end
    R = [1.0 0.2; 0.2 1.0]
    cop = DRF.GaussianCopula(R)
    forests = [tiny(1), tiny(2)]                        # nfeat == 3
    dir = mktempdir()
    good = joinpath(dir, "good.rcop")
    DRF.save_copula(good, cop, forests, ["a", "b"], ["c1", "c2", "c3"], [0.1, 0.2, 0.3])
    @test length(DRF.load_copula(good)[5]) == 3          # the honest artifact loads

    # THE HALF-MIGRATED ARTIFACT: a header declaring 4 conditioning columns over marginals fit on 3. This is
    # what a partly-updated pipeline writes (env columns added to `COPULA_COND_COLS` but the forests trained
    # before the change, or vice versa) and it is the failure ADR 0023 calls silent: every draw would read
    # the forests at the wrong coordinates while still returning in-range traits. `ncond` is taken from the
    # cond_cols/x the writer is handed, so writing it is enough to reproduce.
    bad = joinpath(dir, "bad_ncond.rcop")
    DRF.save_copula(bad, cop, forests, ["a", "b"], ["c1", "c2", "c3", "c4"], [0.1, 0.2, 0.3, 0.4])
    @test_throws ErrorException DRF.load_copula(bad)

    # And the reverse skew (header narrower than the forests) must be rejected too.
    worse = joinpath(dir, "bad_ncond2.rcop")
    DRF.save_copula(worse, cop, forests, ["a", "b"], ["c1", "c2"], [0.1, 0.2])
    @test_throws ErrorException DRF.load_copula(worse)
end

@testitem "the .rcop CARRIES its qrf estimator (format v2) and still reads v1 (ADR 0038)" tags = [:scientific] begin
    using LPJmLFITEmulator.DRF
    using Test

    # WHY: `qrf` selects a DIFFERENT conditional distribution from the same marginals. Until format v2 it
    # lived ONLY in the sidecar `_meta.txt`, so a consumer that pinned the `.rcop` PATH (which is what line
    # M's contract does) and missed the sidecar got `RecruitCopula`'s `qrf = false` default and silently
    # sampled the equal-weight conditional instead of the one the ADR-0030 gate scored — in range, no error.
    function tiny(seed)
        r = DRF.Xoshiro256pp(seed)
        m = 600
        X = Matrix{Float64}(undef, m, 3)
        y = Vector{Float64}(undef, m)
        for i in 1:m
            for ff in 1:3
                X[i, ff] = DRF.rand01!(r)
            end
            # A skewed within-leaf target, so equal-weight and QRF leaf weighting actually DISAGREE — a
            # symmetric target would make this testitem vacuously green.
            y[i] = X[i, 1]^3 + 0.05 * X[i, 2]
        end
        return DRF.fit_forest(X, y; ntrees = 6, subsample = 300, mtry = 3, seed = seed, store_values = true)
    end
    cop = DRF.GaussianCopula([1.0 0.3; 0.3 1.0])
    forests = [tiny(11), tiny(12)]
    cols = ["c1", "c2", "c3"]
    x = [0.4, 0.6, 0.5]
    dir = mktempdir()

    # v2 round-trips BOTH settings, and the flag is on the `d ncond qrf` line.
    for q in (false, true)
        p = joinpath(dir, "q_$(q).rcop")
        DRF.save_copula(p, cop, forests, ["a", "b"], cols, x; qrf = q)
        @test split(readlines(p)[1]) == ["LPJMLFIT_RCOP", "2"]
        @test split(readlines(p)[2]) == ["2", "3", q ? "1" : "0"]
        @test DRF.load_copula(p)[6] == q
    end

    # The DEFAULT is false, so every pre-ADR-0038 caller keeps writing what it wrote before.
    pdef = joinpath(dir, "default.rcop")
    DRF.save_copula(pdef, cop, forests, ["a", "b"], cols, x)
    @test DRF.load_copula(pdef)[6] == false

    # The 6th element is APPENDED: the pre-existing 5-way destructuring must still work untouched.
    c5, af5, x5, n5, cc5 = DRF.load_copula(joinpath(dir, "q_true.rcop"))
    @test n5 == ["a", "b"] && cc5 == cols && x5 == x && length(af5) == 2

    # The flag must be LOAD-BEARING, or the round-trip above proves nothing — a `qrf` that never changed a
    # draw would make this whole testitem vacuous. But it is NOT expected to differ at every row: QRF
    # weights each tree's leaf by 1/|leaf|, so wherever the leaves a row lands in happen to be equal-sized
    # the two estimators coincide exactly. (The t9 acceptance probe reports the same caveat, and on the real
    # artifact all three golden rows DO differ.) So scan a spread of rows and require that at least one
    # differs, rather than betting on one lucky row.
    rows_probe = [[a, b, c] for a in (0.1, 0.4, 0.7, 0.95) for b in (0.15, 0.5, 0.85) for c in (0.2, 0.6, 0.9)]
    ndiff_probe = count(
        DRF.sample_copula!(DRF.Xoshiro256pp(7), cop, forests, r; qrf = true) !=
            DRF.sample_copula!(DRF.Xoshiro256pp(7), cop, forests, r; qrf = false)
            for r in rows_probe
    )
    @test ndiff_probe > 0

    # v1 BACK-COMPAT on the real committed artifact: it predates the field and must read as `qrf = false`,
    # which is what it was trained with. This is the guardrail-4 check — a version bump must not orphan a
    # committed baseline or any artifact line M already pinned.
    v1 = joinpath(@__DIR__, "references", "recruit_copula_hainich.rcop")
    @test split(readlines(v1)[1]) == ["LPJMLFIT_RCOP", "1"]
    c1, af1, x1, n1, cc1, q1 = DRF.load_copula(v1)
    @test q1 == false
    @test length(cc1) == length(x1) == af1[1].nfeat
    # A hand-forged future version must be refused, not read as v2 with a shifted token stream.
    fut = joinpath(dir, "v99.rcop")
    write(fut, replace(read(joinpath(dir, "q_true.rcop"), String), "LPJMLFIT_RCOP 2" => "LPJMLFIT_RCOP 99"))
    @test_throws ErrorException DRF.load_copula(fut)
end

@testitem "FluxDrivenSlowEmulator REJECTS a conditioning-width mismatch at CONSTRUCTION (ADR 0038)" tags = [:scientific] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
    using LPJmLFITEmulator.DRF
    using Test

    # WHY CONSTRUCTION AND NOT SAMPLE TIME: `DRF._check_nfeat` is the real guard, but for the copula it only
    # runs inside `sample_copula!`, reached only when a patch actually RECRUITS. A cell that thins every
    # year, or an all-grass patch, never draws — so a coupled run with a mis-wired copula completes
    # "successfully", conserving carbon, with zero diagnostics. The emulator constructor is the one place
    # holding BOTH the boundary and the copula, so it is the only place the width identity can be checked
    # before the run starts.
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
    cop = DRF.GaussianCopula([1.0 0.2; 0.2 1.0])
    boundary = [1200.0, -3.0, 15.0, 369.0]          # the 4-column production boundary tail
    to_pools = make_recruit_to_pools(["SLA", "Wooddens"])

    # The count DRF the emulator needs: 11 features + the boundary tail.
    countf = tinyf(3, 11 + length(boundary))

    # A minimal SYNTHETIC fast core — this testitem only exercises the emulator CONSTRUCTOR, so it needs a
    # valid `FDiffFastCore` but no forcing, no fixtures and no coupled run (the fixture-reading setup in
    # `slow_membership_tests.jl` is for the in-loop tests).
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

    # (a) MATCHED 8-column artifact with `live_flux_cond` — must construct.
    f8 = [tinyf(1, 4 + length(boundary)), tinyf(2, 4 + length(boundary))]
    rc8 = RecruitCopula{Float64}(
        cop, f8, collect(1.0:(4.0 + length(boundary))), to_pools, live_flux_cond
    )
    @test FluxDrivenSlowEmulator(fc, countf; boundary = boundary, recruit_copula = rc8) isa
        FluxDrivenSlowEmulator

    # (b) MATCHED 14-column artifact with `live_flux_cond_env` — the ADR-0038 production shape.
    env = [935.4, 0.981, 95.6, 0.581, 0.535, 0.0076]
    n14 = 4 + length(boundary) + length(env)
    f14 = [tinyf(4, n14), tinyf(5, n14)]
    rc14 = RecruitCopula{Float64}(
        cop, f14, collect(1.0:Float64(n14)), to_pools, live_flux_cond_env(env); qrf = true
    )
    e14 = FluxDrivenSlowEmulator(fc, countf; boundary = boundary, recruit_copula = rc14)
    @test e14 isa FluxDrivenSlowEmulator
    @test e14.recruit_copula.qrf                      # `qrf` survives into the emulator

    # (c) THE BUG THIS CATCHES: a 14-column artifact wired with the 8-column policy. Before ADR 0038 this
    # constructed happily and only failed if and when a patch recruited.
    rc_mixed = RecruitCopula{Float64}(
        cop, f14, collect(1.0:Float64(n14)), to_pools, live_flux_cond; qrf = true
    )
    @test_throws ErrorException FluxDrivenSlowEmulator(
        fc, countf; boundary = boundary, recruit_copula = rc_mixed
    )

    # (d) And the reverse: an 8-column artifact wired with the env policy.
    rc_mixed2 = RecruitCopula{Float64}(
        cop, f8, collect(1.0:(4.0 + length(boundary))), to_pools, live_flux_cond_env(env)
    )
    @test_throws ErrorException FluxDrivenSlowEmulator(
        fc, countf; boundary = boundary, recruit_copula = rc_mixed2
    )

    # (e) A width-legal artifact whose boundary is the wrong LENGTH is also caught, because the policy's
    # output width depends on `boundary`, not on the artifact.
    @test_throws ErrorException FluxDrivenSlowEmulator(
        fc, tinyf(6, 11 + 3); boundary = [1200.0, -3.0, 15.0], recruit_copula = rc8
    )
end
