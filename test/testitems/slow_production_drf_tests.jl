# P1 Tier-1 Step 4a (ADR 0020/0021/0022) — the PRODUCTION Component-S DRF, LOADED FROM DISK, in the coupled
# loop. This closes the gap that the Tier-1 wiring test (slow_flux_driven_tests.jl) used an in-test DRF: here
# the coupled `FluxDrivenSlowEmulator` is built from the COMMITTED, serialized production forest
# `references/drf_forest_hainich.drf` (trained by scripts/train_slow_drf.jl on the runtime-consistent Hainich
# table from scripts/build_slow_runtime_table.py — features in the exact flux_feature_vector order). The gate:
#   • LOAD — DRF.load_forest reads the committed artifact; its nfeat matches the baked boundary + 11 head.
#   • RUNTIME-CONSISTENCY (ADR 0023) — the rows the forest is actually fed (`s.feature_history`) are compared
#     COLUMN-BY-COLUMN against the trained per-feature band in the artifact meta. This replaces the old
#     "predicted counts inside the training band" check, which could not fail: a DRF prediction is a convex
#     combination of training leaf means, so it stays in the target band however out-of-domain its input is
#     (ADR 0032 — that is how a two-order-of-magnitude proxy-basis shift stayed invisible). The target band
#     is still asserted, now from the meta's own y-band, but as an ARTIFACT-INTEGRITY invariant.
#   • MECHANISM — the loaded DRF DRIVES the demography (tree N moves; F alone holds it fixed).
#   • CONSERVATION — the S↔F handoff conserves carbon ≤ 1e-6·C_scale every year (ledger, by construction).
#   • ENERGY closes; DETERMINISM under seed; all finite. Hainich (DE-Hai, cell 42490) DEMONSTRATION artifact
#     (the global runtime-consistent DRF is the Phase-2 SLURM follow-up).

@testitem "Production DRF loaded from disk drives the coupled Hainich loop (mechanism + conservation + determinism)" tags = [:conservation, :coupling, :energy, :scientific] begin
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

    # ── load the COMMITTED production DRF + its baked boundary / n_init / trained bands from the meta ──
    forest = DRF.load_forest(joinpath(refdir, "drf_forest_hainich.drf"))
    boundary = Float64[]; n_init = 1.0; age0 = 0.0
    colnames = String[]; feat_min = Float64[]; feat_max = Float64[]; y_min = NaN; y_max = NaN
    for ln in eachline(joinpath(refdir, "drf_forest_hainich_meta.txt"))
        (isempty(strip(ln)) || startswith(strip(ln), "#")) && continue
        parts = split(ln, '\t')
        parts[1] == "boundary" && (boundary = parse.(Float64, split(strip(parts[2]))))
        parts[1] == "n_init" && (n_init = parse(Float64, strip(parts[2])))
        parts[1] == "age0" && (age0 = parse(Float64, strip(parts[2])))
        parts[1] == "colnames" && (colnames = String.(split(strip(parts[2]))))
        parts[1] == "feat_min" && (feat_min = parse.(Float64, split(strip(parts[2]))))
        parts[1] == "feat_max" && (feat_max = parse.(Float64, split(strip(parts[2]))))
        parts[1] == "y_min" && (y_min = parse(Float64, strip(parts[2])))
        parts[1] == "y_max" && (y_max = parse(Float64, strip(parts[2])))
    end
    @test length(colnames) == forest.nfeat
    @test length(feat_min) == forest.nfeat && length(feat_max) == forest.nfeat
    @test isfinite(y_min) && isfinite(y_max) && y_min < y_max
    @test forest isa DRF.Forest
    @test length(boundary) + 11 == forest.nfeat        # 11 head + baked boundary tail
    # ADR 0024 §3: age0 seeds s.age so the runtime age_mean starts INSIDE the DRF's trained mean-age band.
    # A missing meta/wire-up would leave age0=0 (the pre-0024 degenerate seed) → silent train/inference OOD.
    @test age0 > 0.0

    nyears = 12
    forcings = repeat(year_forc, nyears)

    # fixed-N reference: F alone cannot move tree N
    core_none = mkcore()
    nind0 = [p.nind for p in core_none.pools]
    out_none = run_coupled_cell(core_none, mkclo(), mkstate(), forcings; slow = nothing, days_per_year = n)
    @test [p.nind for p in core_none.pools] == nind0

    # ── coupled run driven by the LOADED production DRF ──
    core = mkcore()
    cscale = sum(FDiff.vegc_full_ind(p) * p.nind for p in core.pools)
    s = FluxDrivenSlowEmulator(core, forest; boundary = boundary, n_init = n_init, age0 = age0, seed = 1)
    @test s.recruit_idx > 0
    @test all(a -> isapprox(a, age0), s.age)           # age0 seed took (ADR 0024 §3)
    out = run_coupled_cell(core, mkclo(), mkstate(), forcings; slow = s, days_per_year = n)

    @test all(isfinite, out.t_skin) && all(isfinite, out.npp) && all(isfinite, out.le)
    @test maximum(abs, out.resid) < 1.0e-6                       # energy closes by construction
    @test length(s.target_history) == nyears && all(isfinite, s.target_history)

    # TARGET BAND — a STRUCTURAL invariant, deliberately NOT a runtime-consistency check (ADR 0032 / S1c).
    # A DRF prediction is a convex combination of training leaf means, so it cannot leave [y_min, y_max]
    # whatever it is fed. Asserting it therefore proves the ARTIFACT is intact (a corrupted forest or a
    # feature-count mismatch would break it) and proves nothing about conditioning. Bounding it at the
    # meta's own y-band instead of the old hand-picked 0.5..40 cushion makes that explicit: the old bound
    # could not fail, which is why a two-order-of-magnitude proxy-basis shift survived every green gate for
    # five days. The check that CAN see a shift is the feature-band one below.
    @test all(t -> y_min ≤ t ≤ y_max, s.target_history)     # measured 12.28..13.64 on y ∈ [3, 19]

    # RUNTIME-vs-TRAINED FEATURE BAND — the real ADR-0023 train/inference-consistency gate. `feature_history`
    # is the exact row handed to the forest each year; compare it column-by-column with the artifact's trained
    # band, in units of band width so the measure is scale-free.
    #
    # MEASURED 2026-07-28 (S1c, ADR 0034), and this is a KNOWN, DOCUMENTED residual shift, not a pass:
    #   water_stress  runtime 0.323..0.331  vs trained [0, 0.043]    → 6.6× band width  (F_diff vs the C)
    #   soilmoist     runtime 0.792..0.999  vs trained [0.842, 0.867] → 5.1×  (year-end instant vs annual mean)
    #   lai           runtime 3.63..5.17    vs trained [2.76, 3.37]   → 2.9×  (one patch vs the cell mean)
    #   fpc           runtime  ..0.784      vs trained [0.155, 0.741] → 0.03× (marginal; below the 0.5 cut)
    # Every other column, INCLUDING the two that ADR 0032's regeneration moved into band (`bm_inc_cell`,
    # `growth_eff`), is inside. So this asserts the shift is exactly where it is known to be: a NEW column
    # drifting out, or these growing, trips it. Tighten the set as ADR 0034's three causes are closed.
    exc = [
        begin
                w = feat_max[j] - feat_min[j]
                scale = w > 0 ? w : max(abs(feat_min[j]), 1.0e-12)
                rmin = minimum(f[j] for f in s.feature_history)
                rmax = maximum(f[j] for f in s.feature_history)
                max(feat_min[j] - rmin, rmax - feat_max[j], 0.0) / scale
            end for j in eachindex(colnames)
    ]
    @test length(s.feature_history) == nyears
    @test all(isfinite, exc)
    @info "runtime-vs-trained feature band (excursion in band widths; 0 = inside)" pairs = [
        colnames[j] => round(exc[j], digits = 3) for j in eachindex(colnames) if exc[j] > 0
    ]
    @test Set(colnames[j] for j in eachindex(colnames) if exc[j] > 0.5) ==
        Set(["water_stress", "soilmoist", "lai"])
    @test maximum(exc) ≤ 10.0                                              # measured worst 6.64
    @test exc[findfirst(==("bm_inc_cell"), colnames)] == 0.0                # ADR 0032's fix, held
    @test exc[findfirst(==("growth_eff"), colnames)] == 0.0                 # (was ~8× on the proxy basis)

    # MECHANISM: the loaded DRF moved tree N (F alone held it fixed above)
    @test s.total_n_history[end] != s.total_n_history[1]
    @test out.npp != out_none.npp

    # CONSERVATION: S↔F handoff conserves carbon every year
    @test maximum(abs, s.resid_history) ≤ 1.0e-6 * cscale
    @test maximum(abs, s.resid_history) < 1.0e-6

    # DETERMINISM: same seed ⇒ identical coupled trajectory
    core2 = mkcore()
    s2 = FluxDrivenSlowEmulator(core2, DRF.load_forest(joinpath(refdir, "drf_forest_hainich.drf")); boundary = boundary, n_init = n_init, age0 = age0, seed = 1)
    run_coupled_cell(core2, mkclo(), mkstate(), forcings; slow = s2, days_per_year = n)
    @test s.total_n_history == s2.total_n_history
    @test s.target_history == s2.target_history
end
