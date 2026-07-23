# P1 Tier-1 Step 4b — the Gate-3 ORACLE test (docs/p1_s_in_loop_design.md §6, risk #3). The coupled
# flux-driven Component S (production DRF loaded from disk) is compared to the LPJmL-FIT C GROUND TRUTH
# trait/size distribution at Hainich (cell 42490), extracted by scripts/build_slow_oracle_reference.py to
# the committed references/hainich_slow_oracle_{traits,counts}.csv.
#
# HONEST FRAMING (carried from the design doc + the residual-diagnosis discipline): this is a RECURSIVE
# coupled S (advancing its own AR count + re-growing carbon each year) vs the NON-RECURSIVE C truth (a
# 25-patch IBM), Hainich-ONLY. It is a distributional DRIFT ALARM, not a parity gate. The S-owned trait
# axes {SLA, Wooddens, beta_root} are fixed-cohort in v1 (the copula recruit sampler is built — src/drf.jl
# — but its consumer, recruit-cohort APPEND, is a later step), so the meaningful v1 oracle axes are the
# SIZE distribution (Height; F-grown, S-shaped) and the COUNT magnitude. The tolerance is set to the
# measured margin (~0.31 IQR-normalized quantile-RMSE this session) with cushion; a real drift would trip it.

@testitem "Gate-3 oracle — coupled flux-driven S size distribution vs LPJmL-FIT C truth (Hainich 42490)" tags = [:scientific, :coupling] begin
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
    tair_K = fc_("temp") .+ 273.15; σ = 5.670374419e-8
    year_forc = [
        AtmForcing(;
                swdown = fc_("swdown")[i], lwdown = fc_("lwnet")[i] + σ * tair_K[i]^4,
                tair = tair_K[i], qair = fc_("huss")[i], wind = 2.0, psurf = 1.0e5,
                precip = fc_("precip")[i], co2 = fc_("co2")[i]
            ) for i in 1:n
    ]

    forest = DRF.load_forest(joinpath(refdir, "drf_forest_hainich.drf"))
    boundary = Float64[]; n_init = 1.0; age0 = 0.0
    for ln in eachline(joinpath(refdir, "drf_forest_hainich_meta.txt"))
        (isempty(strip(ln)) || startswith(strip(ln), "#")) && continue
        parts = split(ln, '\t')
        parts[1] == "boundary" && (boundary = parse.(Float64, split(strip(parts[2]))))
        parts[1] == "n_init" && (n_init = parse(Float64, strip(parts[2])))
        parts[1] == "age0" && (age0 = parse(Float64, strip(parts[2])))
    end
    # age0 meta must be present (ADR 0024 §3): a dropped/renamed line leaves age0=0 (the pre-0024 degenerate
    # seed) → s.age seeded at 0 → the coupled run drifts into the OOD age band, silently. Fail loudly instead.
    @test age0 > 0.0

    # coupled decadal-scale run driven by the loaded production DRF (age0 seed keeps age_mean in-band, ADR 0024)
    core = FDiffFastCore([mkp(r) for r in rows], [mkt(r) for r in rows], soil, 51.25)
    s = FluxDrivenSlowEmulator(core, forest; boundary = boundary, n_init = n_init, age0 = age0, seed = 1)
    forcings = repeat(year_forc, 20)
    run_coupled_cell(
        core, SEBEnergyClosure(; t_soil0 = _mean(tair_K)),
        SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER)), forcings; slow = s, days_per_year = n
    )

    # nind-weighted Height quantiles from the coupled S-shaped population. REFERENCE-BASIS ALIGNMENT
    # (residual-diagnosis): the C `ind` output — hence hainich_slow_oracle_traits.csv — EXCLUDES sub-5m
    # saplings (fixture note; the C-truth Height q05 = 5.21 m). Since ADR 0024 establishment APPENDS genuine
    # ~1 m recruit cohorts, we must compare on the SAME basis and count only cohorts at/above the C output
    # floor (≥5 m); recruits enter this window once F grows them past 5 m, exactly as the C writer reports them.
    h_ind_floor = 5.0
    hs = Float64[]; ws = Float64[]
    for p in core.pools
        (!p.is_grass && p.height ≥ h_ind_floor) || continue
        push!(hs, p.height); push!(ws, p.nind)
    end
    @test !isempty(hs)                                     # established cohorts populate the ≥5 m window
    ord = sortperm(hs); hs = hs[ord]; ws = ws[ord]; cw = cumsum(ws) ./ sum(ws)
    wq(q) = hs[findfirst(>=(q), cw)]
    qs = (0.05, 0.25, 0.5, 0.75, 0.95)
    coupled_h = [wq(q) for q in qs]

    # committed C-truth Height quantiles
    tr = readcsv(joinpath(refdir, "hainich_slow_oracle_traits.csv"))
    hi = findfirst(==("Height"), tr["axis"])
    truth_h = [parse(Float64, tr[string("q", lpad(round(Int, q * 100), 2, '0'))][hi]) for q in qs]
    truth_iqr = truth_h[4] - truth_h[2]                    # q75 - q25

    # IQR-normalized quantile-RMSE — the drift-alarm metric
    nqrmse = sqrt(sum((coupled_h .- truth_h) .^ 2) / length(qs)) / truth_iqr
    @info "Gate-3 oracle (Hainich Height distribution)" coupled = round.(coupled_h, digits = 2) truth = round.(truth_h, digits = 2) nqrmse = round(nqrmse, digits = 3)

    @test truth_iqr > 0
    @test all(isfinite, coupled_h)
    # RE-MEASURED under ADR 0024 (residual-diagnosis): with genuine ~1 m recruits (APPEND), a true per-cohort
    # age, and the DRF retrained on mean(Age−1), the coupled Height distribution drifts a bit further from the
    # C's non-recursive pooled distribution — nqrmse ≈ 0.39 on the ≥5 m C-`ind` basis (was ~0.31 with the old
    # mix+counter). This is the honest recursive-vs-non-recursive DRIFT (median ratio ≈1.25, count ratio ≈0.67
    # BOTH well in-band), NOT a fidelity regression. The alarm sits at 0.45 (≈15 % over the re-measured
    # baseline) so it still trips on a REAL drift; a future increase toward 0.45 is a signal to diagnose, not
    # to widen further. Hainich-only.
    @test nqrmse ≤ 0.45
    @test 0.6 ≤ coupled_h[3] / truth_h[3] ≤ 1.6            # median Height within a factor (measured ≈1.25)

    # COUNT magnitude sanity — the DRF's settled count vs the C-truth per-patch beech count
    cnt = readcsv(joinpath(refdir, "hainich_slow_oracle_counts.csv"))
    truth_npatch = _mean(parse.(Float64, cnt["N_beech_per_patch_mean"]))
    coupled_target = _mean(s.target_history[(end - 4):end])   # settled DRF count target
    @test 0.25 ≤ coupled_target / truth_npatch ≤ 4.0
end
