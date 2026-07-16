# Gate — multi-layer soil water (ADR 0014 scale-up step 2; docs/phase3_fdiff_cbinary_validation.md §7).
# The differentiable 23-layer soil column (SoilColumn + FDiffStateML + daily_step_ml) validated on the
# Hainich prototype cell against the LPJmL-FIT C binary's daily soil water (d_rootmoist) + transpiration.
# It (a) makes soil water physically representable per layer, (b) SUBSTANTIALLY improves the daily
# GPP/transpiration correlation vs the single bucket (the shallow layers dry preferentially, so the
# root-weighted moisture tracks the C's dynamics), while (c) the transpiration/GPP LEVELS still sit in
# the documented single-representative-individual band (the level gaps are demand-side, not soil-supply
# — the next scale-up item). Committed one-year 2010 reference; no HPC/`/p/tmp` dependency.
@testitem "Multi-layer soil — F_diff vs LPJmL-FIT daily soil water (Hainich 42490, 2010)" tags = [:validation, :fdiff, :soil] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using Test

    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = readlines(path)
        i = findfirst(l -> !startswith(strip(l), "#") && !isempty(strip(l)), lines)
        hdr = split(strip(lines[i]), ',')
        rows = [parse.(Float64, split(strip(l), ',')) for l in lines[(i + 1):end] if !isempty(strip(l))]
        return Dict(hdr[j] => [r[j] for r in rows] for j in eachindex(hdr))
    end
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

    f = readcsv(joinpath(refdir, "hainich_forcing_2010.csv"))
    t = readcsv(joinpath(refdir, "hainich_cbinary_targets_2010.csv"))
    (soildepth, whcs, rootdist) = readtable(joinpath(refdir, "hainich_soilcolumn.txt"))
    base = readbaseline(joinpath(refdir, "hainich_ml_baseline_2010.txt"))
    n = length(f["doy"])
    @test n == 365
    @test length(whcs) == 23

    _mean(x) = sum(x) / length(x)
    _corr(a, b) = (ma = _mean(a); mb = _mean(b); sum((a .- ma) .* (b .- mb)) / sqrt(sum((a .- ma) .^ 2) * sum((b .- mb) .^ 2)))

    soil = hainich_soilcolumn(; whcs = whcs, rootdist = rootdist, soildepth = soildepth)
    @test soil.frac_evap[1] ≈ 1.0                         # top layer fully within the 300 mm evap depth
    @test isapprox(soil.frac_evap[2], 100 / 300; atol = 1.0e-6)

    forc = [
        DailyForcing{Float64}(
                swdown = f["swdown"][i], lwnet = f["lwnet"][i], temp = f["temp"][i],
                precip = f["precip"][i], daylength = f["daylength"][i], co2 = f["co2"][i],
            ) for i in 1:n
    ]
    fap = t["fapar_C"]
    st0 = FDiffStateML{Float64}([0.95 * w for w in whcs], 0.0)

    # ── per-day water closure: precip = transp + evap + runoff + Δ(Σw + snow), EXACTLY ──
    st = st0
    maxres = 0.0
    for i in 1:n
        (st′, fl) = daily_step_ml(tebs_params(), st, tebs_structure(), soil, forc[i]; fapar = fap[i])
        dW = sum(st′.w) - sum(st.w)
        res = forc[i].precip - (fl.transp + fl.evap + fl.runoff + dW + (st′.snowpack - st.snowpack))
        maxres = max(maxres, abs(res))
        st = st′
    end
    @test maxres < 1.0e-6                                  # water closes by construction

    (_, days) = rollout_daily_ml(tebs_params(), st0, tebs_structure(), soil, forc; fapars = fap)
    gpp = [x.gpp for x in days]
    tr = [x.transp for x in days]
    rm = [x.rootmoist for x in days]
    ev = [x.evap for x in days]
    gs = [i for i in 1:n if 150 <= f["doy"][i] <= 240]

    @test all(isfinite, gpp) && all(isfinite, tr) && all(isfinite, rm) && all(isfinite, ev)

    # ── soil water: per-layer column now tracks the C binary's top-1 m available water (d_rootmoist) ──
    @test _corr(rm[gs], t["rootmoist_C"][gs]) > 0.85       # r ≈ 0.97
    @test 0.4 <= _mean(rm[gs]) / _mean(t["rootmoist_C"][gs]) <= 1.2   # ratio ≈ 0.70

    # ── dynamics: GPP + transpiration daily correlation vs the C binary (improved over the bucket) ──
    @test _corr(gpp, t["gpp_C"]) > 0.95                   # annual r ≈ 0.988
    @test _corr(gpp[gs], t["gpp_C"][gs]) > 0.9           # growing-season r ≈ 0.978 (bucket was 0.961)
    @test _corr(tr[gs], t["transp_C"][gs]) > 0.9         # r ≈ 0.971
    # levels remain in the documented single-representative-individual band (demand-side gap)
    @test 0.45 <= sum(gpp) / sum(t["gpp_C"]) <= 1.5       # ≈ 0.65 (βvm-corrected)
    @test 0.5 <= sum(tr) / sum(t["transp_C"]) <= 2.0      # ≈ 1.60 (βvm-corrected)

    # ── ReferenceTests drift alarm: multi-layer annual totals on real forcing must not drift ──
    @test sum(gpp) ≈ base["gpp_annual"] rtol = 1.0e-3
    @test sum(tr) ≈ base["transp_annual"] rtol = 1.0e-3
    @test sum(ev) ≈ base["evap_annual"] rtol = 1.0e-3
    @test _mean(rm) ≈ base["rootmoist_mean"] rtol = 1.0e-3
end

@testitem "Multi-layer soil — differentiable (ForwardDiff through the layered rollout)" tags = [:gradient, :fdiff, :soil] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using ForwardDiff, FiniteDifferences
    using Test

    # small column + short rollout so the AD check is fast; confirms the layered infiltration cascade
    # + per-layer root uptake + soil evaporation are ForwardDiff-differentiable and match finite diffs.
    whcs = [37.0, 53.0, 88.0, 175.0, 175.0]
    rootdist = [0.41, 0.32, 0.2, 0.07, 0.0]
    soildepth = [200.0, 300.0, 500.0, 1000.0, 1000.0]
    mkforc(::Type{S}) where {S} = [
        DailyForcing{S}(swdown = 210.0, lwnet = -45.0, temp = 19.0, precip = (d % 4 == 0 ? 8.0 : 0.3), daylength = 14.0, co2 = 380.0)
            for d in 1:45
    ]
    function ann_gpp(x)                                    # differentiate annual GPP w.r.t. α_c3
        T = typeof(x)
        p = FDiffParams{T}(;
            photo = FDiff.PhotoParams{T}(issla = true, sla = 0.01986, alphac3 = x),
            tstress = FDiff.TempStressParams{T}(temp_photos_low = 20.0, temp_photos_high = 30.0),
            water = FDiff.WaterParams{T}(emax = 10.0, gmin = 1.0),
        )
        soil = hainich_soilcolumn(T; whcs = whcs, rootdist = rootdist, soildepth = soildepth)
        st0 = FDiffStateML{T}(T[0.6 * w for w in whcs], zero(T))
        (_, days) = rollout_daily_ml(p, st0, tebs_structure(T), soil, mkforc(T))
        return sum(d.gpp for d in days)
    end
    fdm = central_fdm(5, 1)
    gfd = fdm(ann_gpp, 0.08)
    gad = ForwardDiff.derivative(ann_gpp, 0.08)
    @test isfinite(gad) && isfinite(gfd)
    @test isapprox(gad, gfd; rtol = 1.0e-4, atol = 1.0e-6)
    @test abs(gad) > 1.0                                   # genuinely non-zero (GPP responds to α_c3)
end
