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
# (albedo_stem, albedo_litter, snowcanopyfrac) by PFT id (par/pft.js) — dynamic patch albedo
function pft_albedo(typ)
    typ == 1 && return (0.04, 0.1, 0.1)
    typ in (2, 3) && return (0.04, 0.1, 0.4)
    typ in (4, 5) && return (0.1, 0.1, 0.15)
    typ == 6 && return (0.05, 0.01, 0.15)
    return (0.15, 0.1, 0.4)                        # grasses / default
end

# build one Individual from a reconstructed row (index r into the parsed columns)
function make_individual(ind, r)
    typ = parse(Int, ind["type"][r])
    sla = parse(Float64, ind["sla"][r])
    path = :c3                                     # all Hainich PFTs present are C3 (no C4 grass)
    photo = PhotoParams{Float64}(; path = path, issla = true, sla = sla)
    tstress = TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0)
    (ast, alt, scf) = pft_albedo(typ)
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
        ast, alt, scf,                             # PFT albedo constants (dynamic patch albedo)
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
    # group individuals by patch
    patches = sort(unique(parse.(Int, ind["patch"])))
    patch_rows = Dict(p => Int[] for p in patches)
    for r in eachindex(ind["patch"])
        push!(patch_rows[parse(Int, ind["patch"][r])], r)
    end

    p = tebs_params()
    gpp_C = fcol(t, "gpp_C"); transp_C = fcol(t, "transp_C"); rootm_C = fcol(t, "rootmoist_C")
    interc_C = fcol(t, "interc_C"); pet_C = fcol(t, "pet_C"); fapar_C = fcol(t, "fapar_C")
    gs = [i for i in 1:n if GS_LO <= doy[i] <= GS_HI]
    # C-binary drives (kernel isolation, §9/§10) — used only for the crutch-vs-standalone comparison
    phens_C = [clamp(x / maximum(fapar_C), 0.0, 1.0) for x in fapar_C]
    eeqs_C = [x / 1.32 for x in pet_C]                  # C's own eeq (embeds the daily albedo_patch)

    # average daily stand fluxes over the 25 patches. Default (phens=eeqs=nothing) is STANDALONE:
    # F_diff self-computes the GSI phenology + dynamic-albedo eeq (§11).
    function run_cell(; phens = nothing, eeqs = nothing)
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

    crut = run_cell(phens = phens_C, eeqs = eeqs_C)     # both C-output crutches (§9/§10 config)
    st = run_cell()                                     # STANDALONE: self GSI phen + self dynamic-albedo eeq

    # self-computed GSI phenology (no fapar_C drive) + self-computed eeq (no pet_C drive)
    pp = tebs_phenparams(); ps = FDiff.PhenState{Float64}(); wav = 1.0; phen_self = zeros(n)
    for i in 1:n
        (ps, ph) = FDiff.phenology_gsi_step(pp, ps, forc[i].temp, forc[i].swdown, wav, forc[i].temp)
        phen_self[i] = ph
    end
    inds1 = [make_individual(ind, r) for r in patch_rows[patches[1]]]
    eeq_self = [FDiff.priestley_taylor_eeq(FDiff.WaterParams{Float64}(), fcol(f, "swdown")[i], fcol(f, "lwnet")[i],
            fcol(f, "temp")[i], fcol(f, "daylength")[i], FDiff.patch_albedo(inds1, phen_self[i], 0.0)) for i in 1:n]
    dl_self = [petpar_daylength(51.25, d) for d in 1:n]

    println("F_diff STANDALONE (crutch-free) canopy ↔ LPJmL-FIT C-binary — Hainich 42490, 2010 (§11)")
    println("  ", length(patches), " patches, ", length(ind["patch"]), " individuals")
    println("  F_diff now self-computes BOTH the GSI leaf phenology AND the dynamic-albedo eeq\n")

    println("── crutch removal proofs (self-computed vs the C output each replaced) ──")
    println("  GSI phen  vs C d_fapar      r = ", round(_corr(phen_self, fapar_C), digits = 4),
        "  (mean ", round(_mean(phen_self), digits = 3), " vs proxy ", round(_mean(phens_C), digits = 3), ")")
    println("  eeq·1.32  vs C d_pet        r = ", round(_corr(eeq_self, eeqs_C), digits = 4),
        "  annual ", round(sum(1.32 .* eeq_self), digits = 1), " vs ", round(sum(pet_C), digits = 1),
        " (ratio ", round(sum(1.32 .* eeq_self) / sum(pet_C), digits = 3), "; fixed-0.15 was 807/1.068)")
    println("  daylength vs petpar2 forc   max|Δ| = ", round(maximum(abs.(dl_self .- fcol(f, "daylength"))), digits = 6), " h")

    println("\n── annual ratios (model/C): crutch (phen_C+eeq_C)  →  standalone (self+self) ──")
    println("  GPP     = ", round(sum(crut.gpp) / sum(gpp_C), digits = 3), "  →  ", round(sum(st.gpp) / sum(gpp_C), digits = 3))
    println("  transp  = ", round(sum(crut.transp) / sum(transp_C), digits = 3), "  →  ", round(sum(st.transp) / sum(transp_C), digits = 3))
    println("  interc  = ", round(sum(crut.interc) / sum(interc_C), digits = 3), "  →  ", round(sum(st.interc) / sum(interc_C), digits = 3),
        "   (", round(sum(st.interc), digits = 1), " vs C ", round(sum(interc_C), digits = 1), " mm)")

    println("\n── standalone growing season (DOY 150–240) daily ──")
    fmtline(name, x, y) = println(
        rpad(name, 26), "model/truth=", round(_mean(x), digits = 3), "/", round(_mean(y), digits = 3),
        "  ratio=", round(_mean(x) / _mean(y), digits = 3), "  r=", round(_corr(x, y), digits = 4)
    )
    fmtline("GPP (gC/m2/day)", st.gpp[gs], gpp_C[gs])
    fmtline("transp (mm/day)", st.transp[gs], transp_C[gs])
    fmtline("rootmoist (mm)", st.rootm[gs], rootm_C[gs])
    println("\n── standalone full-year daily correlation ──")
    println("GPP r    = ", round(_corr(st.gpp, gpp_C), digits = 4))
    println("transp r = ", round(_corr(st.transp, transp_C), digits = 4))
    return nothing
end

main()
