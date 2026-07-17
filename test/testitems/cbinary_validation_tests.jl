# Gate — quantitative C-binary validation (ADR 0014 scale-up step 1; docs/phase3_fdiff_cbinary_validation.md).
# Replaces the "F_diff pinned against ITSELF" note in numerical_regression_tests.jl with a real
# "same physics" cross-check: F_diff, driven by the Hainich prototype cell's REAL daily .clm forcing
# and the LPJmL-FIT C binary's ACTUAL daily FAPAR (kernel-isolation drive), is compared to the C
# binary's own daily GPP / transpiration / PET for the same cell+year (committed one-year reference
# extracted by scripts/extract_fdiff_validation_inputs.py from the single-cell re-run of
# run_fdiff_validation_cell.sh). Cell 42490 = Hainich DE-Hai (global orderA grid; NOT 28008 = desert).
#
# The tolerances are HONEST to the current F_diff scope (one representative individual, fixed canopy
# structure, single soil bucket): the radiation/PET path matches near-exactly, the GPP/transpiration
# SEASONAL DYNAMICS are captured (high correlation) while their LEVELS sit inside a documented band
# (the multi-PFT/representative-individual + 23-layer-soil scale-up gaps — NOT kernel bugs; the
# photosynthesis constants are byte-identical to the C source).
@testitem "C-binary validation — F_diff vs LPJmL-FIT daily (Hainich 42490, 2010)" tags = [:validation, :fdiff] begin
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
    base = readbaseline(joinpath(refdir, "hainich_fdiff_baseline_2010.txt"))
    n = length(f["doy"])
    @test n == 365

    _mean(x) = sum(x) / length(x)
    _corr(a, b) = (ma = _mean(a); mb = _mean(b); sum((a .- ma) .* (b .- mb)) / sqrt(sum((a .- ma) .^ 2) * sum((b .- mb) .^ 2)))

    # ── drive F_diff with REAL forcing + the C binary's ACTUAL daily FAPAR (TeBS beech params) ──
    whc = maximum(t["rootmoist_C"])                     # root-zone available-water capacity, mm
    forc = [
        DailyForcing{Float64}(
                swdown = f["swdown"][i], lwnet = f["lwnet"][i], temp = f["temp"][i],
                precip = f["precip"][i], daylength = f["daylength"][i], co2 = f["co2"][i],
            ) for i in 1:n
    ]
    fap = t["fapar_C"]
    w0 = clamp(t["rootmoist_C"][1] / whc, 0.0, 1.0)
    (_, days) = rollout_daily(
        tebs_params(), FDiffState{Float64}(w = w0, snowpack = 0.0),
        tebs_structure(; whc = whc), forc; fapars = fap
    )
    gpp = [x.gpp for x in days]
    transp = [x.transp for x in days]
    pet = [x.eeq * 1.32 for x in days]                  # F_diff eeq → PET (LPJmL PRIESTLEY_TAYLOR = 1.32)
    gs = [i for i in 1:n if 150 <= f["doy"][i] <= 240]  # peak growing-season window (phen ≈ 1)

    # ── robustness: no NaN/Inf (the deep-winter degenerate λ regime is bracket-clamped) ──
    @test all(isfinite, gpp) && all(isfinite, transp) && all(isfinite, pet)

    # ── PET / radiation + Priestley–Taylor path: QUANTITATIVELY validated against the C binary ──
    @test 0.9 <= _mean(pet[gs]) / _mean(t["pet_C"][gs]) <= 1.15   # ratio ≈ 1.06
    @test _corr(pet, t["pet_C"]) > 0.99                            # r ≈ 0.9999

    # ── GPP: SEASONAL DYNAMICS captured (correlation); LEVEL inside the documented scale-up band ──
    @test _corr(gpp, t["gpp_C"]) > 0.92                            # annual r ≈ 0.986
    @test _corr(gpp[gs], t["gpp_C"][gs]) > 0.85                    # growing-season r ≈ 0.961
    @test 0.45 <= sum(gpp) / sum(t["gpp_C"]) <= 1.5                # ratio ≈ 0.64 (single-individual, βvm+βadt)

    # ── transpiration: timing captured; level inside the single-bucket soil-water confound band ──
    @test _corr(transp[gs], t["transp_C"][gs]) > 0.85             # r ≈ 0.97
    @test 0.5 <= sum(transp) / sum(t["transp_C"]) <= 2.0          # ratio ≈ 1.47 (βadt floor fix; §10)

    # ── ReferenceTests drift alarm: F_diff's OWN annual totals on the real forcing must not drift ──
    @test sum(gpp) ≈ base["gpp_annual"] rtol = 1.0e-4
    @test sum(transp) ≈ base["transp_annual"] rtol = 1.0e-4
    @test sum(pet) ≈ base["pet_annual"] rtol = 1.0e-4
end
