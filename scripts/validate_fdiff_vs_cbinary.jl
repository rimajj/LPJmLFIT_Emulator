# =============================================================================
# validate_fdiff_vs_cbinary.jl — quantitative "same physics" validation of the
# differentiable fast core F_diff against the LPJmL-FIT C binary on the Hainich
# prototype cell (global orderA grid index 42490), driven by the cell's REAL
# daily forcing + the C binary's ACTUAL daily FAPAR (kernel-isolation drive).
#
# Reads the full 2000-2019 daily CSV produced by scripts/extract_fdiff_validation_inputs.py
# (on /p/tmp), runs F_diff with the TeBS beech parameter set, and reports the
# agreement for PET (eeq*1.32), growing-season GPP, and transpiration. Writes a
# metrics JSON to artifacts/metrics/. The committed CI gate is the year-2010
# subset (test/testitems/cbinary_validation_tests.jl); this driver is the broader
# multi-year analysis behind docs/phase3_fdiff_cbinary_validation.md.
#
# Run (login node OK — pure Julia, no HPC):
#   JULIA_DEPOT_PATH=$HOME/.julia julia --project=. scripts/validate_fdiff_vs_cbinary.jl
# =============================================================================
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff

const DATA = "/p/tmp/jamirp/esm_land_emulator_data/fast_core_validation/hainich_c42490_daily_2000_2019.csv"
const OUT = joinpath(@__DIR__, "..", "artifacts", "metrics", "phase3_fdiff_cbinary_validation.json")
const GS_LO, GS_HI = 150, 240          # peak growing-season DOY window (phen≈1 → nulls phenology)

# ── tiny dependency-free CSV reader ──────────────────────────────────────────
function read_csv(path)
    lines = readlines(path)
    i = findfirst(l -> !startswith(strip(l), "#") && !isempty(strip(l)), lines)
    hdr = split(strip(lines[i]), ',')
    rows = [parse.(Float64, split(strip(l), ',')) for l in lines[(i + 1):end] if !isempty(strip(l))]
    data = Dict{String, Vector{Float64}}()
    for (j, name) in enumerate(hdr)
        data[name] = [r[j] for r in rows]
    end
    return data
end

# ── metrics ──────────────────────────────────────────────────────────────────
_mean(x) = isempty(x) ? NaN : sum(x) / length(x)
function _corr(a, b)
    ma, mb = _mean(a), _mean(b)
    num = sum((a .- ma) .* (b .- mb))
    den = sqrt(sum((a .- ma) .^ 2) * sum((b .- mb) .^ 2))
    return den == 0 ? NaN : num / den
end
_rmse(a, b) = sqrt(_mean((a .- b) .^ 2))
_bias(a, b) = _mean(a .- b)                       # model − truth
function _nmbe(a, b)                               # normalized mean bias (model vs truth)
    mb = _mean(b)
    return mb == 0 ? NaN : _mean(a .- b) / mb
end
metrics(a, b) = (
    n = length(a), mean_model = _mean(a), mean_truth = _mean(b),
    bias = _bias(a, b), nmbe = _nmbe(a, b), rmse = _rmse(a, b), corr = _corr(a, b),
    ratio = _mean(a) / _mean(b),
)

function main()
    d = read_csv(DATA)
    n = length(d["doy"])
    years = unique(Int.(d["year"]))
    whc_mm = maximum(d["rootmoist_C"])            # root-zone available-water capacity (mm)

    # forcing + boundary
    forc = [
        DailyForcing{Float64}(
                swdown = d["swdown"][i], lwnet = d["lwnet"][i], temp = d["temp"][i],
                precip = d["precip"][i], daylength = d["daylength"][i], co2 = d["co2"][i],
            ) for i in 1:n
    ]
    fapars = d["fapar_C"]
    p = tebs_params()
    str = tebs_structure(; whc = whc_mm)
    w0 = clamp(d["rootmoist_C"][1] / whc_mm, 0.0, 1.0)
    st0 = FDiffState{Float64}(; w = w0, snowpack = d["swe_C"][1])

    (_, days) = rollout_daily(p, st0, str, forc; fapars = fapars)
    gpp = [x.gpp for x in days]
    transp = [x.transp for x in days]
    pet = [x.eeq * 1.32 for x in days]            # F_diff eeq → PET (LPJmL PRIESTLEY_TAYLOR=1.32)
    wmm = Float64[]                                # F_diff bucket in absolute mm
    let stt = st0
        for i in 1:n
            (stt, _) = daily_step(p, stt, str, forc[i]; fapar = fapars[i])
            push!(wmm, stt.w * whc_mm)
        end
    end

    gs = [i for i in 1:n if GS_LO <= d["doy"][i] <= GS_HI]   # growing-season mask
    res = Dict{String, Any}()
    res["cell"] = 42490; res["whc_mm"] = whc_mm; res["years"] = years
    res["pet_annual"] = metrics(pet, d["pet_C"])
    res["pet_growing"] = metrics(pet[gs], d["pet_C"][gs])
    res["gpp_growing"] = metrics(gpp[gs], d["gpp_C"][gs])
    res["gpp_annual"] = metrics(gpp, d["gpp_C"])
    res["transp_growing"] = metrics(transp[gs], d["transp_C"][gs])
    res["transp_annual"] = metrics(transp, d["transp_C"])
    res["rootmoist_growing"] = metrics(wmm[gs], d["rootmoist_C"][gs])

    # per-year annual totals
    yr = Int.(d["year"])
    ann(v) = [sum(v[yr .== y]) for y in years]
    res["annual_gpp_model"] = ann(gpp); res["annual_gpp_truth"] = ann(d["gpp_C"])
    res["annual_transp_model"] = ann(transp); res["annual_transp_truth"] = ann(d["transp_C"])
    res["annual_pet_model"] = ann(pet); res["annual_pet_truth"] = ann(d["pet_C"])

    # ── report ──
    println("F_diff ↔ LPJmL-FIT C-binary validation — Hainich cell 42490 (2000-2019)")
    println("  whc (root-zone available water) = ", round(whc_mm, digits = 1), " mm; FAPAR-driven, TeBS params\n")
    fmt(m) = string(
        "mean model/truth=", round(m.mean_model, digits = 3), "/", round(m.mean_truth, digits = 3),
        "  ratio=", round(m.ratio, digits = 3), "  NMBE=", round(100 * m.nmbe, digits = 1), "%",
        "  RMSE=", round(m.rmse, digits = 3), "  r=", round(m.corr, digits = 4)
    )
    println("PET  (daily mm, annual)     : ", fmt(res["pet_annual"]))
    println("PET  (daily mm, DOY150-240) : ", fmt(res["pet_growing"]))
    println("GPP  (daily gC/m2,150-240)  : ", fmt(res["gpp_growing"]))
    println("GPP  (daily gC/m2, annual)  : ", fmt(res["gpp_annual"]))
    println("Tran (daily mm, 150-240)    : ", fmt(res["transp_growing"]))
    println("Tran (daily mm, annual)     : ", fmt(res["transp_annual"]))
    println("Root moisture (mm,150-240)  : ", fmt(res["rootmoist_growing"]))
    println("\nAnnual GPP model vs truth (gC/m2/yr):")
    for (k, y) in enumerate(years)
        println(
            "  ", y, "  model=", round(res["annual_gpp_model"][k], digits = 1),
            "  truth=", round(res["annual_gpp_truth"][k], digits = 1),
            "  ratio=", round(res["annual_gpp_model"][k] / res["annual_gpp_truth"][k], digits = 3)
        )
    end

    # ── write JSON (manual, dependency-free) ──
    mkpath(dirname(OUT))
    jval(x) = x isa AbstractString ? string('"', x, '"') :
        x isa Bool ? string(x) :
        x isa Integer ? string(x) :
        x isa Real ? (isfinite(x) ? string(x) : "null") :
        x isa NamedTuple ? string("{", join([string('"', k, "\":", jval(getfield(x, k))) for k in keys(x)], ","), "}") :
        x isa AbstractVector ? string("[", join(jval.(x), ","), "]") :
        string('"', x, '"')
    open(OUT, "w") do io
        println(io, "{")
        ks = collect(keys(res))
        for (i, k) in enumerate(ks)
            print(io, "  \"", k, "\": ", jval(res[k]))
            println(io, i < length(ks) ? "," : "")
        end
        println(io, "}")
    end
    return println("\nwrote ", OUT)
end

main()
