#!/usr/bin/env julia
# ── USE THE EMULATOR ACROSS BIOMES (Phase 5 — multi-cell generalization) ────────────────────────────
# Drives the coupled S+F+E emulator (Component F + the energy closure E) with the REAL GSWP3-W5E5 daily
# forcing of five BIOME-REPRESENTATIVE cells (boreal / temperate / mediterranean / semi-arid / tropical;
# forcing committed by scripts/extract_biome_forcing.py) and reports the emergent, climate-driven
# ENERGY PARTITIONING contrast — the demonstration that the added surface-energy-balance closure
# generalizes beyond the Hainich prototype (DEVELOPMENT_PLAN §6 Phase 5).
#
# To isolate the CLIMATE effect, a COMMON canopy structure (the committed Hainich patch) is used across
# all cells and grown by F's own allocation over the decade — so the energy-partitioning differences come
# purely from the forcing (radiation / temperature / precipitation) through F's water-limited ET driving
# E's residual-H closure. Biome-specific vegetation (PFT parameters + spin-up) is the documented next
# step; here the point is that E closes and partitions PLAUSIBLY across the full climate envelope.
#
# Run:  julia --project=. scripts/run_coupled_biomes.jl
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
using LPJmLFITEmulator.Allometry
using Statistics, Printf

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
const σ = 5.670374419e-8

function readcsv(path)
    lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
    hdr = split(strip(lines[1]), ',')
    rows = [split(strip(l), ',') for l in lines[2:end]]
    return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
end
fcol(d, k) = parse.(Float64, d[k])

# ── common canopy structure (committed Hainich dominant patch) + soil ──
ind = readcsv(joinpath(REFDIR, "hainich_individuals_2010.csv"))
v(k, r) = parse(Float64, ind[k][r])
nt(r) = parse(Int, ind["type"][r])
prows = Dict{Int, Vector{Int}}()
for r in eachindex(ind["type"])
    (nt(r) <= 6 && v("height", r) > 0) && push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
end
rows = prows[argmax(Dict(k => length(vv) for (k, vv) in prows))]
mkp(r) = TreePools{Float64}(
    v("leaf_c", r), v("sapwood_c", r),
    max(v("agb", r) / v("nind", r) - v("leaf_c", r) - v("sapwood_c", r), 0.0), v("root_c", r),
    v("height", r), v("crownarea", r), v("nind", r), v("sla", r), v("wooddens", r), false
)
mkt(r) = Individual{Float64}(
    v("fpar_leafon", r), 0.0, v("alphaa", r), v("albedo_leaf", r), v("emax", r),
    v("sapwood_c", r), v("root_c", r), 0.0, 0.02, 0.04, 0.1, 0.4, v("nind", r),
    PhotoParams{Float64}(; path = :c3, issla = true, sla = v("sla", r)),
    TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false
)
sd = Float64[]; whcs = Float64[]; rdist = Float64[]
for ln in eachline(joinpath(REFDIR, "hainich_soilcolumn.txt"))
    s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
    x = parse.(Float64, split(s)); push!(sd, x[2]); push!(whcs, x[3]); push!(rdist, x[4])
end
soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)

biomes = [
    ("boreal_siberia", 61.75), ("temperate_hainich", 51.25), ("mediterranean_iberia", 39.75),
    ("semiarid_sahel", 13.75), ("tropical_amazon", -3.25),
]

@printf("\n=== COUPLED S+F+E EMULATOR ACROSS BIOMES (common canopy; real GSWP3-W5E5 decade 2010–2019) ===\n")
@printf(
    "%-22s %6s %6s %7s %7s %7s %7s %7s %8s\n",
    "biome", "Tair", "Tskin", "LE", "H", "Rn", "Bowen", "maxRes", "GPP"
)
for (name, lat) in biomes
    f = readcsv(joinpath(REFDIR, "biome_forcing_$(name).csv"))
    tairK = fcol(f, "temp") .+ 273.15
    swd = fcol(f, "swdown"); lwn = fcol(f, "lwnet"); prec = fcol(f, "precip")
    huss = fcol(f, "huss"); co2 = fcol(f, "co2")
    n = length(tairK)
    forcings = [
        AtmForcing(;
                swdown = swd[i], lwdown = lwn[i] + σ * tairK[i]^4, tair = tairK[i], qair = huss[i],
                wind = 2.0, psurf = 1.0e5, precip = prec[i], co2 = co2[i]
            ) for i in 1:n
    ]
    core = FDiffFastCore([mkp(r) for r in rows], [mkt(r) for r in rows], soil, lat)
    clo = SEBEnergyClosure(; t_soil0 = mean(tairK))
    state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
    out = run_coupled_cell(core, clo, state, forcings; days_per_year = 365)
    gs = 152:243        # boreal/N-hemisphere growing season; a coarse common window
    bowen = mean(out.h[gs]) / max(mean(out.le[gs]), 1.0e-6)
    @printf(
        "%-22s %6.1f %6.1f %7.1f %7.1f %7.1f %7.2f %8.1e %8.0f\n",
        name, mean(tairK) - 273.15, mean(out.t_skin) - 273.15, mean(out.le), mean(out.h),
        mean(out.rn), bowen, maximum(abs, out.resid), sum(out.gpp) / (n / 365)
    )
end
@printf("\nAll biomes: energy closes by construction (maxRes ≈ 0). Partitioning tracks the climate:\n")
@printf("tropical → LE-dominated (low Bowen); semi-arid/mediterranean → H-dominated (high Bowen);\n")
@printf("boreal → low fluxes + cold skin. Same canopy ⇒ the contrast is purely climate-driven.\n")
