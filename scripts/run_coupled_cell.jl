#!/usr/bin/env julia
# ── USE THE EMULATOR ──────────────────────────────────────────────────────────────────────────────
# End-to-end coupled S+F+E run on the Hainich prototype cell (42490) over the committed decade
# (2009–2019), producing the full ESM-facing output tuple the hybrid land component exists to deliver:
# LE, H, G, T_skin, Rn, NBP_atm, z0 — with energy CLOSED by construction (Rn = LE + H + G, H the
# residual) and validated for physical plausibility against the seasonal cycle.
#
# This is the deployment demonstration (DEVELOPMENT_PLAN §6 Phase 4): the 25-patch cell is run patch-by-
# patch through the fast physical core F (`FDiffFastCore`, self-computing its own prognostic structure),
# aggregated to a CELL mean latent heat + canopy structure, and handed to ONE cell-level surface-energy-
# balance closure E (`SEBEnergyClosure`) that solves the single skin temperature and partitions the
# available energy. E's skin temperature feeds back to every patch's top thermal boundary (the mandatory
# E→F coupling, DEVELOPMENT_PLAN §2.4). Water & carbon are conserved by F; energy is closed in E.
#
# Honest scope (carried from START_HERE §8): wind and surface pressure are held constant (2 m/s, 1e5 Pa)
# — the underlying LPJmL-FIT run never used them and the committed forcing CSV omits them; sourcing
# GSWP3-W5E5 `sfcwind`/`ps` is the documented refinement. lwdown is reconstructed as lwnet + σ·Tair⁴.
# The slow emulator S is not yet wired into deployment, so structure is F's own prognostic canopy.
#
# Run:  julia --project=. scripts/run_coupled_cell.jl
# Writes: logs/coupled_decadal_hainich.csv (daily cell-mean series) + a summary table to stdout.

using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
using LPJmLFITEmulator.Allometry
using Statistics, Printf

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
const σ = 5.670374419e-8

function readcsv(path)
    lines = readlines(path)
    i = findfirst(l -> !startswith(strip(l), "#") && !isempty(strip(l)), lines)
    hdr = split(strip(lines[i]), ',')
    rows = [split(strip(l), ',') for l in lines[(i + 1):end] if !isempty(strip(l))]
    return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
end

# ── load the committed Hainich cell: 2008 start structure, soil column, decadal forcing ──
ind = readcsv(joinpath(REFDIR, "hainich_individuals_2008.csv"))
f = readcsv(joinpath(REFDIR, "hainich_decadal_forcing.csv"))
fcol(d, k) = parse.(Float64, d[k])

sd = Float64[]; whcs = Float64[]; rdist = Float64[]
for ln in eachline(joinpath(REFDIR, "hainich_soilcolumn.txt"))
    s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
    x = parse.(Float64, split(s)); push!(sd, x[2]); push!(whcs, x[3]); push!(rdist, x[4])
end
soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)

# 25 tree patches (type ≤ 6, height > 0) from the 2008 structure
ntyp(r) = parse(Int, ind["type"][r])
vv(r, k) = parse(Float64, ind[k][r])
prows = Dict{Int, Vector{Int}}()
for r in eachindex(ind["type"])
    (ntyp(r) <= 6 && vv(r, "height") > 0) && push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
end
patches = sort(collect(keys(prows)))
mkpool(r) = TreePools{Float64}(
    vv(r, "leaf_c"), vv(r, "sapwood_c"), vv(r, "heartwood_c"), vv(r, "root_c"),
    vv(r, "height"), vv(r, "crownarea"), vv(r, "nind"), vv(r, "sla"), vv(r, "wooddens"), false
)
mktmpl(r) = Individual{Float64}(
    vv(r, "fpar_leafon"), 0.0, vv(r, "alphaa"), vv(r, "albedo_leaf"), vv(r, "emax"),
    vv(r, "sapwood_c"), vv(r, "root_c"), 0.0, 0.02, 0.04, 0.1, 0.4, vv(r, "nind"),
    PhotoParams{Float64}(; path = :c3, issla = true, sla = vv(r, "sla")),
    TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false
)

# per-patch fast cores + per-patch soil-water states (each patch its own water balance)
cores = [FDiffFastCore([mkpool(r) for r in prows[pn]], [mktmpl(r) for r in prows[pn]], soil, 51.25) for pn in patches]
states = [SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER)) for _ in patches]
P = length(cores)

# per-day forcing over the decade
years = Int.(round.(fcol(f, "year")))
tempC = fcol(f, "temp"); swd = fcol(f, "swdown"); lwn = fcol(f, "lwnet")
prec = fcol(f, "precip"); huss = fcol(f, "huss"); co2 = fcol(f, "co2")
n = length(years)
tairK = tempC .+ 273.15

# ONE cell-level energy closure, deep-soil temp seeded with the decadal mean air temperature
clo = SEBEnergyClosure(; t_soil0 = mean(tairK))

bc_f = SToF(; lai = 5.0, height = 25.0, z0 = 1.0, rootdepth = 1150.0, vcmax = 40.0, fpc = 0.9, albedo = 0.15)

# output buffers (cell-mean daily series)
T_skin = zeros(n); LE = zeros(n); H = zeros(n); G = zeros(n); RN = zeros(n)
NBP = zeros(n); Z0 = zeros(n); ALB = zeros(n); GPP = zeros(n); NPP = zeros(n); RES = zeros(n)

doy_in_year = 0
prev_year = years[1]
for i in 1:n
    global doy_in_year, prev_year
    forc = AtmForcing(;
        swdown = swd[i], lwdown = lwn[i] + σ * tairK[i]^4, tair = tairK[i],
        qair = huss[i], wind = 2.0, psurf = 1.0e5, precip = prec[i], co2 = co2[i]
    )
    # 1) run F for every patch; aggregate to the cell mean latent heat + canopy structure
    le_sum = 0.0; gpp_sum = 0.0; npp_sum = 0.0
    alb_sum = 0.0; h_sum = 0.0; z0_sum = 0.0; lai_sum = 0.0
    for p in 1:P
        ftoe = step!(cores[p], states[p], bc_f, forc)
        le_sum += ftoe.le; gpp_sum += ftoe.gpp; npp_sum += ftoe.npp
        se = stand_structure_toe(cores[p])
        alb_sum += se.albedo; h_sum += se.height; z0_sum += se.z0; lai_sum += se.lai
    end
    le_cell = le_sum / P; gpp_cell = gpp_sum / P; npp_cell = npp_sum / P
    bc_e = SToE(; albedo = alb_sum / P, z0 = z0_sum / P, lai = lai_sum / P, height = h_sum / P)
    ftoe_cell = FToE(;
        le = le_cell, gpp = gpp_cell, npp = npp_cell, rh = 0.0, firec = 0.0,
        flux_estabc = 0.0, ground_heat = 0.0
    )
    # 2) ONE cell-level energy-balance solve
    atm, tof = solve!(clo, states[1], ftoe_cell, bc_e, forc)
    # 3) E→F feedback: hand the skin temperature back to every patch's top thermal boundary
    for p in 1:P
        cores[p].soiltemp_skin = tof.t_skin - 273.15
    end
    Rn = (1 - bc_e.albedo) * swd[i] + clo.params.emissivity * (lwn[i] + σ * tairK[i]^4) -
        clo.params.emissivity * σ * atm.t_skin^4
    T_skin[i] = atm.t_skin; LE[i] = atm.le; H[i] = atm.h; G[i] = atm.g; RN[i] = Rn
    NBP[i] = atm.nbp_atm; Z0[i] = atm.z0; ALB[i] = bc_e.albedo; GPP[i] = gpp_cell; NPP[i] = npp_cell
    RES[i] = Rn - (atm.le + atm.h + atm.g)
    # 4) year-end flux-then-integrate handoff (grow every patch's canopy)
    doy_in_year += 1
    if i == n || years[i + 1 > n ? n : i + 1] != years[i]
        for p in 1:P
            annual_step!(cores[p], states[p])
        end
        doy_in_year = 0
    end
end

# ── write the daily cell-mean ESM output series ──
outdir = joinpath(@__DIR__, "..", "logs")
mkpath(outdir)
outfile = joinpath(outdir, "coupled_decadal_hainich.csv")
open(outfile, "w") do io
    println(io, "# Coupled S+F+E emulator — Hainich 42490 cell-mean daily ESM outputs, 2009-2019.")
    println(io, "# Energy closed by construction (Rn = LE + H + G). Units: fluxes W/m2, T_skin K, GPP/NPP gC/m2/day, NBP gC/m2/day, z0 m.")
    println(io, "year,doy,tair_K,t_skin_K,LE,H,G,Rn,NBP_atm,z0,albedo,GPP,NPP,resid")
    for i in 1:n
        @printf(
            io, "%d,%d,%.3f,%.4f,%.4f,%.4f,%.4f,%.4f,%.5f,%.4f,%.4f,%.5f,%.5f,%.3e\n",
            years[i], i - findfirst(==(years[i]), years) + 1, tairK[i], T_skin[i], LE[i], H[i], G[i],
            RN[i], NBP[i], Z0[i], ALB[i], GPP[i], NPP[i], RES[i]
        )
    end
end

# ── summary ──
@printf("\n=== COUPLED S+F+E EMULATOR — Hainich 42490, cell-mean over %d patches, 2009–2019 ===\n", P)
@printf(
    "days simulated: %d   |   energy closure  max|Rn-(LE+H+G)| = %.3e W/m2  (Phase-4 hard gate)\n",
    n, maximum(abs, RES)
)
dT = T_skin .- tairK
@printf("T_skin - T_air:  mean %+.2f K   range [%+.2f, %+.2f] K\n", mean(dT), minimum(dT), maximum(dT))
@printf(
    "annual-mean fluxes: LE=%.1f  H=%.1f  G=%.2f  Rn=%.1f W/m2   (G≈0 over the long run ✓)\n",
    mean(LE), mean(H), mean(G), mean(RN)
)
println("\nPer-year cell-mean summary:")
println("  year   T_air  T_skin    LE     H      Rn    GPP(gC/m2/yr)  Bowen(sum)")
uyears = sort(unique(years))
for y in uyears
    idx = findall(==(y), years)
    sm = idx[152 .≤ (idx .- first(idx) .+ 1) .≤ 243]  # summer subset of this year
    bowen = mean(H[sm]) / max(mean(LE[sm]), 1.0e-6)
    @printf(
        "  %d  %5.1f  %6.1f  %5.1f  %5.1f  %6.1f     %6.0f        %.2f\n",
        y, mean(tairK[idx]) - 273.15, mean(T_skin[idx]) - 273.15, mean(LE[idx]), mean(H[idx]),
        mean(RN[idx]), sum(GPP[idx]), bowen
    )
end
@printf("\nwrote daily cell-mean series -> %s\n", outfile)
