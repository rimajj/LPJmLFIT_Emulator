# =============================================================================
# validate_fdiff_canopy.jl — multi-individual / multi-PFT canopy validation of
# F_diff against the LPJmL-FIT C binary on the Hainich prototype cell (42490).
#
# Builds the cell's real per-patch canopies (25 patches, 297 individuals) from the
# reconstructed set (test/testitems/references/hainich_individuals_2010.csv), drives
# each patch canopy with the cell's real daily forcing + a phenology factor derived
# from the C binary's own daily FAPAR, shares one multi-layer soil column per patch,
# averages the daily stand fluxes over the 25 patches, and compares the cell GPP /
# transpiration LEVELS + dynamics to the C binary (which the single-representative-
# individual core under-predicted by 42 % / over-predicted by 45 %).
#
# Run (login node OK — pure Julia):
#   JULIA_DEPOT_PATH=$HOME/.julia julia --project=. scripts/validate_fdiff_canopy.jl
# =============================================================================
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams

const REF = joinpath(@__DIR__, "..", "test", "testitems", "references")
const GS_LO, GS_HI = 150, 240

function read_csv(path)
    lines = readlines(path)
    i = findfirst(l -> !startswith(strip(l), "#") && !isempty(strip(l)), lines)
    hdr = split(strip(lines[i]), ',')
    rows = [split(strip(l), ',') for l in lines[(i + 1):end] if !isempty(strip(l))]
    data = Dict{String, Vector{String}}()
    for (j, name) in enumerate(hdr)
        data[name] = [r[j] for r in rows]
    end
    return data
end
fcol(d, k) = parse.(Float64, d[k])

function read_soilcolumn(path)
    D = Float64[]; W = Float64[]; R = Float64[]
    for ln in eachline(path)
        s = strip(ln)
        (isempty(s) || startswith(s, "#")) && continue
        v = parse.(Float64, split(s))
        push!(D, v[2]); push!(W, v[3]); push!(R, v[4])
    end
    return (D, W, R)
end

_mean(x) = sum(x) / length(x)
function _corr(a, b)
    ma, mb = _mean(a), _mean(b)
    return sum((a .- ma) .* (b .- mb)) / sqrt(sum((a .- ma) .^ 2) * sum((b .- mb) .^ 2))
end

# PFT interception coefficient par->intc (par/pft.js): tropical/temperate trees (types 0–3) 0.02,
# boreal trees (4–6) 0.06, grasses (7–9) 0.01.
pft_intc(typ) = typ <= 3 ? 0.02 : (typ <= 6 ? 0.06 : 0.01)

# build one Individual from a reconstructed row (index r into the parsed columns)
function make_individual(ind, r)
    typ = parse(Int, ind["type"][r])
    sla = parse(Float64, ind["sla"][r])
    path = :c3                                     # all Hainich PFTs present are C3 (no C4 grass)
    photo = PhotoParams{Float64}(; path = path, issla = true, sla = sla)
    tstress = TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0)
    return Individual{Float64}(
        parse(Float64, ind["fpar_leafon"][r]),     # layered absorbed fraction (leafon)
        parse(Float64, ind["fpc_ind"][r]),         # projective cover
        parse(Float64, ind["alphaa"][r]),
        parse(Float64, ind["albedo_leaf"][r]),
        parse(Float64, ind["emax"][r]),
        parse(Float64, ind["sapwood_c"][r]),
        parse(Float64, ind["root_c"][r]),
        parse(Float64, ind["lai"][r]),             # leaf-on crown LAI (interception)
        pft_intc(typ),                             # PFT interception coefficient
        photo, tstress, typ >= 7,
    )
end

function main()
    ind = read_csv(joinpath(REF, "hainich_individuals_2010.csv"))
    f = read_csv(joinpath(REF, "hainich_forcing_2010.csv"))
    t = read_csv(joinpath(REF, "hainich_cbinary_targets_2010.csv"))
    (soildepth, whcs, rootdist) = read_soilcolumn(joinpath(REF, "hainich_soilcolumn.txt"))
    soil = hainich_soilcolumn(; whcs = whcs, rootdist = rootdist, soildepth = soildepth)

    doy = fcol(f, "doy"); n = length(doy)
    forc = [
        DailyForcing{Float64}(
                swdown = fcol(f, "swdown")[i], lwnet = fcol(f, "lwnet")[i], temp = fcol(f, "temp")[i],
                precip = fcol(f, "precip")[i], daylength = fcol(f, "daylength")[i], co2 = fcol(f, "co2")[i],
            ) for i in 1:n
    ]
    # phenology factor from the C binary's own daily FAPAR (self-normalized to leaf-on peak)
    fapar_C = fcol(t, "fapar_C")
    fapar_peak = maximum(fapar_C)
    phens = [clamp(x / fapar_peak, 0.0, 1.0) for x in fapar_C]

    # group individuals by patch
    patches = sort(unique(parse.(Int, ind["patch"])))
    patch_rows = Dict(p => Int[] for p in patches)
    for r in eachindex(ind["patch"])
        push!(patch_rows[parse(Int, ind["patch"][r])], r)
    end

    p = tebs_params()
    gpp_C = fcol(t, "gpp_C"); transp_C = fcol(t, "transp_C"); rootm_C = fcol(t, "rootmoist_C")
    interc_C = fcol(t, "interc_C"); pet_C = fcol(t, "pet_C")
    gs = [i for i in 1:n if GS_LO <= doy[i] <= GS_HI]
    eeqs_C = [x / 1.32 for x in pet_C]                  # C's own eeq (embeds the daily albedo_patch)

    # average daily stand fluxes over the 25 patches, for a given eeq drive
    function run_cell(; eeqs = nothing)
        gpp = zeros(n); transp = zeros(n); evap = zeros(n); interc = zeros(n); rootm = zeros(n); fapar = zeros(n)
        for pnum in patches
            inds = [make_individual(ind, r) for r in patch_rows[pnum]]
            st0 = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
            (_, days) = rollout_daily_canopy(p, st0, inds, soil, forc; phens = phens, eeqs = eeqs)
            for i in 1:n
                gpp[i] += days[i].gpp / length(patches); transp[i] += days[i].transp / length(patches)
                evap[i] += days[i].evap / length(patches); interc[i] += days[i].interc / length(patches)
                rootm[i] += days[i].rootmoist / length(patches); fapar[i] += days[i].fapar / length(patches)
            end
        end
        return (; gpp, transp, evap, interc, rootm, fapar)
    end

    a = run_cell()                                     # interception ON, fixed-albedo eeq
    b = run_cell(eeqs = eeqs_C)                         # interception ON + C-albedo eeq (pet_C drive)

    println("F_diff MULTI-INDIVIDUAL canopy ↔ LPJmL-FIT C-binary — Hainich 42490, 2010")
    println("  ", length(patches), " patches, ", length(ind["patch"]), " individuals; phenology from C d_fapar")
    println("  interception (wet-canopy) now ON; eeq drive shown both fixed-albedo and C-pet_C\n")

    println("── annual transpiration ratio (model/C) — the demand-side residual ──")
    println("  prior session (no interception, fixed albedo)      = 1.319")
    println("  + interception, fixed-albedo eeq                    = ", round(sum(a.transp) / sum(transp_C), digits = 3))
    println("  + interception + C-albedo eeq (pet_C drive)         = ", round(sum(b.transp) / sum(transp_C), digits = 3))
    println("\n── annual GPP ratio (model/C) ──")
    println(
        "  fixed-albedo eeq  = ", round(sum(a.gpp) / sum(gpp_C), digits = 3),
        "   C-albedo eeq = ", round(sum(b.gpp) / sum(gpp_C), digits = 3)
    )
    println("\n── interception flux (annual mm) ──")
    println(
        "  F_diff = ", round(sum(a.interc), digits = 1), "   C interc = ", round(sum(interc_C), digits = 1),
        "   r = ", round(_corr(a.interc, interc_C), digits = 3)
    )
    println("\n── PET check: F_diff eeq·1.32 (fixed albedo) vs C pet_C ──")
    eeq_fd = [FDiff.priestley_taylor_eeq(FDiff.WaterParams{Float64}(), fcol(f, "swdown")[i], fcol(f, "lwnet")[i], fcol(f, "temp")[i], fcol(f, "daylength")[i], 0.15) for i in 1:n]
    println(
        "  F_diff PET = ", round(sum(1.32 .* eeq_fd), digits = 1), "   C PET = ", round(sum(pet_C), digits = 1),
        "   ratio = ", round(sum(1.32 .* eeq_fd) / sum(pet_C), digits = 3)
    )

    println("\n── final (interception + C-albedo eeq): growing season (DOY 150–240) daily ──")
    fmtline(name, x, y) = println(
        rpad(name, 26), "model/truth=", round(_mean(x), digits = 3), "/", round(_mean(y), digits = 3),
        "  ratio=", round(_mean(x) / _mean(y), digits = 3), "  r=", round(_corr(x, y), digits = 4)
    )
    fmtline("GPP (gC/m2/day)", b.gpp[gs], gpp_C[gs])
    fmtline("transp (mm/day)", b.transp[gs], transp_C[gs])
    fmtline("rootmoist (mm)", b.rootm[gs], rootm_C[gs])
    println("\n── final full-year daily correlation ──")
    println("GPP r    = ", round(_corr(b.gpp, gpp_C), digits = 4))
    println("transp r = ", round(_corr(b.transp, transp_C), digits = 4))
    return nothing
end

main()
