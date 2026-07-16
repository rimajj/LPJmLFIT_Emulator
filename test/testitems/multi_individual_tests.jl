# Gate — multi-individual / multi-PFT canopy (ADR 0014 scale-up step 3; docs/phase3_fdiff_cbinary_validation.md §9).
# The differentiable multi-individual canopy (Individual + daily_step_canopy) replaces the single
# representative tree with the Hainich cell's real per-patch set of individuals (25 patches × 297
# reconstructed trees+grass, hainich_individuals_2010.csv), sharing one 23-layer soil column and
# distributing light by the FIT vertical layered Beer–Lambert competition. This CLOSES the GPP level
# gap the single-individual core under-predicted (annual ratio 0.57 → ≈1.06) — the primary lever of
# the multi-PFT scale-up — because the light is spread across individuals so the SLA-Vcmax cap no
# longer saturates one over-lit tree, and the canopy absorbs the true layered fraction. Transpiration
# improves too (single-individual multilayer ≈1.60 → ≈1.32) with the residual now localized to the
# demand side (interception + coupled conductance + eeq albedo — documented items 4–5). Committed
# one-year 2010 reference; no HPC/`/p/tmp` dependency.
@testitem "Multi-individual canopy — F_diff vs LPJmL-FIT daily (Hainich 42490, 2010)" tags = [:validation, :fdiff, :canopy] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using Test

    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = readlines(path)
        i = findfirst(l -> !startswith(strip(l), "#") && !isempty(strip(l)), lines)
        hdr = split(strip(lines[i]), ',')
        rows = [split(strip(l), ',') for l in lines[(i + 1):end] if !isempty(strip(l))]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end
    fcol(d, k) = parse.(Float64, d[k])
    function readtable(path)
        D = Float64[]; W = Float64[]; R = Float64[]
        for ln in eachline(path)
            s = strip(ln)
            (isempty(s) || startswith(s, "#")) && continue
            v = parse.(Float64, split(s))
            push!(D, v[2]); push!(W, v[3]); push!(R, v[4])
        end
        return (D, W, R)
    end
    function readbaseline(path)
        d = Dict{String, Float64}()
        for ln in eachline(path)
            (isempty(strip(ln)) || startswith(strip(ln), "#")) && continue
            k, v = split(strip(ln))
            d[k] = parse(Float64, v)
        end
        return d
    end
    _mean(x) = sum(x) / length(x)
    _corr(a, b) = (ma = _mean(a); mb = _mean(b); sum((a .- ma) .* (b .- mb)) / sqrt(sum((a .- ma) .^ 2) * sum((b .- mb) .^ 2)))

    f = readcsv(joinpath(refdir, "hainich_forcing_2010.csv"))
    t = readcsv(joinpath(refdir, "hainich_cbinary_targets_2010.csv"))
    ind = readcsv(joinpath(refdir, "hainich_individuals_2010.csv"))
    (soildepth, whcs, rootdist) = readtable(joinpath(refdir, "hainich_soilcolumn.txt"))
    base = readbaseline(joinpath(refdir, "hainich_canopy_baseline_2010.txt"))
    soil = hainich_soilcolumn(; whcs = whcs, rootdist = rootdist, soildepth = soildepth)
    n = length(f["doy"])
    @test n == 365
    @test length(ind["patch"]) == 297

    forc = [
        DailyForcing{Float64}(
                swdown = fcol(f, "swdown")[i], lwnet = fcol(f, "lwnet")[i], temp = fcol(f, "temp")[i],
                precip = fcol(f, "precip")[i], daylength = fcol(f, "daylength")[i], co2 = fcol(f, "co2")[i],
            ) for i in 1:n
    ]
    fapar_C = fcol(t, "fapar_C")
    phens = [clamp(x / maximum(fapar_C), 0.0, 1.0) for x in fapar_C]

    patches = sort(unique(parse.(Int, ind["patch"])))
    prows = Dict(p => Int[] for p in patches)
    for r in eachindex(ind["patch"])
        push!(prows[parse(Int, ind["patch"][r])], r)
    end
    function mkind(r)
        sla = parse(Float64, ind["sla"][r])
        return Individual{Float64}(
            parse(Float64, ind["fpar_leafon"][r]), parse(Float64, ind["fpc_ind"][r]),
            parse(Float64, ind["alphaa"][r]), parse(Float64, ind["albedo_leaf"][r]), parse(Float64, ind["emax"][r]),
            parse(Float64, ind["sapwood_c"][r]), parse(Float64, ind["root_c"][r]),
            FDiff.PhotoParams{Float64}(; path = :c3, issla = true, sla = sla),
            FDiff.TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0),
            parse(Int, ind["type"][r]) >= 7,
        )
    end

    # ── per-day water closure on one patch: precip = transp + evap + runoff + Δ(Σw + snow) ──
    inds5 = [mkind(r) for r in prows[5]]
    st = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
    maxres = 0.0
    for i in 1:n
        (st′, fl) = daily_step_canopy(tebs_params(), inds5, soil, st, forc[i]; phen = phens[i])
        dW = sum(st′.w) - sum(st.w)
        res = forc[i].precip - (fl.transp + fl.evap + fl.runoff + dW + (st′.snowpack - st.snowpack))
        maxres = max(maxres, abs(res))
        st = st′
    end
    @test maxres < 1.0e-6                                  # water closes by construction

    # ── run all 25 patches, average daily stand fluxes to the cell ──
    gpp = zeros(n); tr = zeros(n); ev = zeros(n); rm = zeros(n)
    for pnum in patches
        inds = [mkind(r) for r in prows[pnum]]
        st0 = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
        (_, days) = rollout_daily_canopy(tebs_params(), st0, inds, soil, forc; phens = phens)
        for i in 1:n
            gpp[i] += days[i].gpp / length(patches); tr[i] += days[i].transp / length(patches)
            ev[i] += days[i].evap / length(patches); rm[i] += days[i].rootmoist / length(patches)
        end
    end
    gpp_C = fcol(t, "gpp_C"); transp_C = fcol(t, "transp_C"); rootm_C = fcol(t, "rootmoist_C")
    doy = fcol(f, "doy")
    gs = [i for i in 1:n if 150 <= doy[i] <= 240]

    @test all(isfinite, gpp) && all(isfinite, tr) && all(isfinite, rm) && all(isfinite, ev)

    # ── GPP LEVEL now closed (the multi-PFT lever): annual ratio ≈ 1.06, dynamics preserved ──
    @test 0.9 <= sum(gpp) / sum(gpp_C) <= 1.25            # ≈ 1.06 (was 0.57 single-individual)
    @test _corr(gpp, gpp_C) > 0.9                          # full-year r ≈ 0.95

    # ── transpiration: improved over the single individual (≈1.60 → ≈1.32); residual = demand-side ──
    @test 1.0 <= sum(tr) / sum(transp_C) <= 1.45          # ≈ 1.32 (single-individual multilayer ≈ 1.60)
    @test _corr(tr, transp_C) > 0.9                        # full-year r ≈ 0.96

    # ── soil water tracks the C binary's root-zone water ──
    @test _corr(rm[gs], rootm_C[gs]) > 0.9                # GS r ≈ 0.97

    # ── ReferenceTests drift alarm: canopy annual totals must not drift ──
    @test sum(gpp) ≈ base["gpp_annual"] rtol = 1.0e-3
    @test sum(tr) ≈ base["transp_annual"] rtol = 1.0e-3
    @test sum(ev) ≈ base["evap_annual"] rtol = 1.0e-3
    @test _mean(rm) ≈ base["rootmoist_mean"] rtol = 1.0e-3
end

@testitem "Multi-individual canopy — differentiable (ForwardDiff through the per-individual loop)" tags = [:gradient, :fdiff, :canopy] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using ForwardDiff, FiniteDifferences
    using Test

    # small canopy (a few individuals) + short rollout so the AD check is fast; confirms the
    # per-individual photosynthesis + stand-conductance aggregation + shared-soil transpiration are
    # ForwardDiff-differentiable and match finite differences.
    whcs = [37.0, 53.0, 88.0, 175.0, 175.0]
    rootdist = [0.41, 0.32, 0.2, 0.07, 0.0]
    soildepth = [200.0, 300.0, 500.0, 1000.0, 1000.0]
    # (fpar, fpc, alphaa, albedo, emax, c_sap, c_root, sla) for 4 individuals of decreasing dominance
    specs = [
        (0.35, 0.18, 0.55, 0.15, 10.0, 3.0e5, 1.0e4, 0.01986),
        (0.12, 0.1, 0.55, 0.15, 10.0, 5.0e4, 3.0e3, 0.02),
        (0.04, 0.05, 0.55, 0.15, 10.0, 1.0e4, 1.0e3, 0.025),
        (0.02, 0.04, 0.5, 0.15, 5.0, 0.0, 5.0e2, 0.042),
    ]
    mkforc(::Type{S}) where {S} = [
        DailyForcing{S}(swdown = 220.0, lwnet = -45.0, temp = 19.0, precip = (d % 4 == 0 ? 8.0 : 0.3), daylength = 14.0, co2 = 380.0)
            for d in 1:40
    ]
    function ann_gpp(x)                                    # differentiate annual canopy GPP w.r.t. α_c3
        T = typeof(x)
        inds = Individual{T}[]
        for (fp, fc, aa, al, em, cs, cr, sla) in specs
            push!(
                inds, Individual{T}(
                    T(fp), T(fc), T(aa), T(al), T(em), T(cs), T(cr),
                    FDiff.PhotoParams{T}(; path = :c3, issla = true, sla = T(sla), alphac3 = x),
                    FDiff.TempStressParams{T}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false
                )
            )
        end
        soil = hainich_soilcolumn(T; whcs = whcs, rootdist = rootdist, soildepth = soildepth)
        st0 = FDiffStateML{T}(T[0.7 * w for w in whcs], zero(T))
        (_, days) = rollout_daily_canopy(FDiff.tebs_params(T), st0, inds, soil, mkforc(T))
        return sum(d.gpp for d in days)
    end
    fdm = central_fdm(5, 1)
    gfd = fdm(ann_gpp, 0.08)
    gad = ForwardDiff.derivative(ann_gpp, 0.08)
    @test isfinite(gad) && isfinite(gfd)
    @test isapprox(gad, gfd; rtol = 1.0e-4, atol = 1.0e-6)
    @test abs(gad) > 1.0                                   # genuinely non-zero (canopy GPP responds to α_c3)
end
