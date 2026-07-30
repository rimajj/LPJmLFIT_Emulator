#!/usr/bin/env julia
# ── ADR 0051 open item — F_diff's side of the boreal soil-ice test ───────────────────────────────────
# Prints the emulator's monthly climatology of the SAME quantity `scripts/boreal_soilice_diagnosis.py`
# recovers from the C: the root-zone (top 1 m, `whcs`-weighted) plant-available fraction,
# `LPJmLFITEmulator.root_zone_soilmoist(state, soil)` (`ROOT_ZONE_LAYERS = 3`). Also prints the daily
# leaf-on `wscal` climatology, so a winter collapse in the C's `w` can be tied directly to the cap that
# pins F_diff's `wscal` at 1 all year in boreal Siberia.
#
# PREDICTION (ADR 0051): F_diff's `w` stays HIGH year-round at 52059 while the C's collapses in winter.
#
# Run:  scripts/sbatch_julia.sh M-soilice-f --project=. scripts/boreal_soilice_probe.jl
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams, WaterParams, FDiffParams
using Statistics, Printf

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
const σ = 5.670374419e-8
const YEARS = 10
const MONTH_LEN = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]     # noleap 365

function readcsv(path)
    lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
    hdr = split(strip(lines[1]), ',')
    rows = [split(strip(l), ',') for l in lines[2:end]]
    return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
end
fcol(d, k) = parse.(Float64, d[k])

function readsoil(path)
    sd = Float64[]; whcs = Float64[]; rdist = Float64[]
    for ln in eachline(path)
        s = strip(ln)
        (isempty(s) || startswith(s, "#")) && continue
        x = parse.(Float64, split(s))
        push!(sd, x[2]); push!(whcs, x[3]); push!(rdist, x[4])
    end
    return hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)
end

function readcanopy(path)
    ind = readcsv(path)
    v(k, r) = parse(Float64, ind[k][r])
    prows = Dict{Int, Vector{Int}}()
    for r in eachindex(ind["type"])
        (parse(Int, ind["type"][r]) <= 6 && v("height", r) > 0) &&
            push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
    end
    rows = prows[argmax(Dict(k => length(vv) for (k, vv) in prows))]
    pools = [
        TreePools{Float64}(
                v("leaf_c", r), v("sapwood_c", r),
                max(v("agb", r) / v("nind", r) - v("leaf_c", r) - v("sapwood_c", r), 0.0), v("root_c", r),
                v("height", r), v("crownarea", r), v("nind", r), v("sla", r), v("wooddens", r), false
            ) for r in rows
    ]
    tmpls = [
        Individual{Float64}(
                v("fpar_leafon", r), 0.0, v("alphaa", r), v("albedo_leaf", r), v("emax", r),
                v("sapwood_c", r), v("root_c", r), 0.0, 0.02, 0.04, 0.1, 0.4, v("nind", r),
                PhotoParams{Float64}(; path = :c3, issla = true, sla = v("sla", r)),
                TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false
            ) for r in rows
    ]
    return pools, tmpls
end

function forcings_of(name)
    f = readcsv(joinpath(REFDIR, "biome_forcing_$(name).csv"))
    tairK = fcol(f, "temp") .+ 273.15
    swd = fcol(f, "swdown"); lwn = fcol(f, "lwnet"); prec = fcol(f, "precip")
    huss = fcol(f, "huss"); co2 = fcol(f, "co2")
    n = min(length(tairK), YEARS * 365)
    forc = [
        AtmForcing(;
                swdown = swd[i], lwdown = lwn[i] + σ * tairK[i]^4, tair = tairK[i], qair = huss[i],
                wind = 2.0, psurf = 1.0e5, precip = prec[i], co2 = co2[i]
            ) for i in 1:n
    ]
    return forc, tairK[1:n]
end

# Start from the ACTIVE calibrated set and flip ONLY `wscal_leafon` (see provision-coupled-cell §5b).
function mkparams(leafon)
    p = FDiff.tebs_params(Float64)
    w = p.water
    fns = fieldnames(typeof(w))
    nt = NamedTuple{fns}(map(f -> getfield(w, f), fns))
    w2 = typeof(w)(; merge(nt, (; wscal_leafon = leafon))...)
    return FDiffParams{Float64}(p.photo, p.tstress, w2, p.resp, p.allom, p.nlambda, p.ω)
end

"Daily root-zone plant-available fraction + daily leaf-on `wscal`, over `YEARS` years."
function daily_w_and_wscal(lat, soil, pools, tmpls, forc, tairK)
    core = FDiffFastCore(pools, tmpls, soil, lat; params = mkparams(true))
    clo = SEBEnergyClosure(; t_soil0 = mean(tairK))
    state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
    bc_f = LPJmLFITEmulator.stand_structure_tof(core)
    wz = Float64[]; ws = Float64[]
    for (i, f) in enumerate(forc)
        LPJmLFITEmulator.couple_day!(core, clo, state, bc_f, f; feedback = true)
        push!(wz, LPJmLFITEmulator.root_zone_soilmoist(state, core.soil))
        push!(ws, core.water_avail)
        i % 365 == 0 && LPJmLFITEmulator.annual_step!(core, state)
    end
    return wz, ws
end

day_month = let dm = vcat((fill(m, MONTH_LEN[m]) for m in 1:12)...)
    repeat(dm, YEARS)
end

cells = readcsv(joinpath(REFDIR, "M_cells.csv"))
names = String.(cells["name"]); lats = fcol(cells, "lat")

@printf("=== F_diff's root-zone plant-available fraction w (top 1 m), monthly climatology, %d yr ===\n", YEARS)
@printf("   root_zone_soilmoist(state, soil) — the SAME quantity boreal_soilice_diagnosis.py recovers\n")
@printf("   from the C's `rootmoist`. PREDICTION: F_diff's stays HIGH at boreal_siberia all year.\n\n")
mons = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
@printf("%-22s %s %6s %6s\n", "cell", join((@sprintf("%5s", m) for m in mons), " "), "min", "max")
wsc = Dict{String, Vector{Float64}}()
for (k, name) in enumerate(names)
    forc, tairK = forcings_of(name)
    soil = readsoil(joinpath(REFDIR, "M_soilcolumn_$(name).txt"))
    pools, tmpls = readcanopy(joinpath(REFDIR, "M_individuals_$(name)_2010.csv"))
    wz, ws = daily_w_and_wscal(lats[k], soil, pools, tmpls, forc, tairK)
    wsc[name] = ws
    clim = [mean(wz[day_month .== m]) for m in 1:12]
    @printf("%-22s %s %6.3f %6.3f\n", name, join((@sprintf("%5.3f", v) for v in clim), " "), minimum(wz), maximum(wz))
end

@printf("\n=== and the leaf-on `wscal` it produces (1.000 = fully unstressed = the cap binding) ===\n")
@printf("%-22s %s %6s\n", "cell", join((@sprintf("%5s", m) for m in mons), " "), "mean")
for name in names
    ws = wsc[name]
    clim = [mean(ws[day_month .== m]) for m in 1:12]
    @printf("%-22s %s %6.3f\n", name, join((@sprintf("%5.3f", v) for v in clim), " "), mean(ws))
end
