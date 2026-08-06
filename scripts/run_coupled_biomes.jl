#!/usr/bin/env julia
# ── USE THE EMULATOR ACROSS BIOMES (line M / M1 — per-cell input provisioning) ───────────────────────
# Drives the coupled S+F+E emulator (Component F + the energy closure E) with the REAL GSWP3-W5E5 daily
# forcing of the biome-representative cells registered in `scripts/extract_biome_forcing.py`
# (boreal / temperate / mediterranean / semi-arid / tropical) and reports the emergent, climate- AND
# vegetation-driven ENERGY PARTITIONING contrast.
#
# WHAT CHANGED IN M1: every cell now runs its OWN inputs —
#   * soil column   `references/M_soilcolumn_<name>.txt`      (scripts/extract_cell_soilcolumn.py:
#       per-layer whcs from that cell's own C `whc_nat`; rootdist = the fpc-weighted mean of the cell's
#       living trees' own `getrootdist.c` profiles)
#   * canopy        `references/M_individuals_<name>_2010.csv` (scripts/extract_cell_individuals.py:
#       that cell's reconstructed representative individuals + layered-light shares)
#   * latitude/cell `references/M_cells.csv`                   (from the global run's grid.nc `cellid`)
# Previously ALL five cells reused **Hainich's** soil and **Hainich's** canopy, deliberately, to isolate
# the climate effect. Both configurations are run here, so the table shows how much of the biome contrast
# is CLIMATE and how much is VEGETATION + SOIL.
#
# ── CANOPY BASIS (ADR 0057, changed 2026-08-06): the PATCH ENSEMBLE, not the modal patch ─────────────
# Every patch of the cell's `ind` canopy is run INDEPENDENTLY (its own core, soil water and energy
# closure) and the outputs are averaged — the basis the C itself reports (`fwriteoutput.c` writes the
# 25-patch ensemble mean of every gridded variable), and the one `biome_fdiff_oracle_probe.jl` /
# `biome_resilience_probe.jl` already use. This driver used to run the single MODAL patch (most living
# trees); ADR 0053 measured that patch at 1.12–1.72× the ensemble's FPC, so every level it printed was
# systematically denser-than-the-cell. The `mod/ens` table below keeps that artifact VISIBLE rather than
# silently removing it. Structural gates asserting member-INVARIANT properties (conservation,
# determinism, boundedness) deliberately stay single-member — ADR 0057 §4.
#
# Run (SLURM, per CLAUDE.md §2):  scripts/sbatch_julia.sh M-biomes --project=. scripts/run_coupled_biomes.jl
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
using LPJmLFITEmulator.Allometry
using Statistics, Printf

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
const σ = 5.670374419e-8
const YEARS = 10

function readcsv(path)
    lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
    hdr = split(strip(lines[1]), ',')
    rows = [split(strip(l), ',') for l in lines[2:end]]
    return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
end
fcol(d, k) = parse.(Float64, d[k])

"Read a `layer soildepth_mm whcs_mm rootdist` column file into a `SoilColumn`."
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

"One patch of a reconstructed individual set → (pools, templates)."
function build_patch(ind, rows)
    v(k, r) = parse(Float64, ind[k][r])
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

"ALL patches of the cell's canopy, sorted by patch id, plus the index of the MODAL (most-trees) one."
function readcanopy_patches(path)
    ind = readcsv(path)
    v(k, r) = parse(Float64, ind[k][r])
    nt(r) = parse(Int, ind["type"][r])
    prows = Dict{Int, Vector{Int}}()
    for r in eachindex(ind["type"])
        (nt(r) <= 6 && v("height", r) > 0) && push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
    end
    pk = sort(collect(keys(prows)))
    modal = argmax([length(prows[p]) for p in pk])
    return [build_patch(ind, prows[p]) for p in pk], modal
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

"ONE patch through the coupled loop — its own core, soil water and energy closure."
function run_patch(pools, tmpls, soil, lat, forc, tairK)
    core = FDiffFastCore(deepcopy(pools), deepcopy(tmpls), soil, lat)
    clo = SEBEnergyClosure(; t_soil0 = mean(tairK))
    state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
    out = run_coupled_cell(core, clo, state, forc; days_per_year = 365)
    gs = 152:243        # a coarse common N-hemisphere growing-season window
    return (
        tskin = mean(out.t_skin) - 273.15, le = mean(out.le), h = mean(out.h), rn = mean(out.rn),
        gs_h = mean(out.h[gs]), gs_le = mean(out.le[gs]),
        res = maximum(abs, out.resid), gpp = sum(out.gpp) / (length(forc) / 365),
        ntree = length(pools),
    )
end

"""
The cell = the PATCH-ENSEMBLE MEAN over every patch of its canopy (the C's own output basis; see the
CANOPY BASIS note in the header). Bowen is formed from the ensemble-mean H and LE, not as a mean of
per-patch Bowen ratios — a ratio of means is what a gridded H/LE comparison actually is, and the mean of
ratios diverges wherever a single patch's growing-season LE approaches zero.
"""
function run_cell(patches, modal, soil, lat, forc, tairK)
    runs = [run_patch(p, t, soil, lat, forc, tairK) for (p, t) in patches]
    agg(f) = mean(f(r) for r in runs)
    ens = (
        tskin = agg(r -> r.tskin), le = agg(r -> r.le), h = agg(r -> r.h), rn = agg(r -> r.rn),
        bowen = agg(r -> r.gs_h) / max(agg(r -> r.gs_le), 1.0e-6),
        res = maximum(r.res for r in runs), gpp = agg(r -> r.gpp),
        ntree = agg(r -> r.ntree), npatch = length(runs),
    )
    m = runs[modal]
    return ens, (; m..., bowen = m.gs_h / max(m.gs_le, 1.0e-6), npatch = 1)
end

# ── the per-cell registry + the legacy common-Hainich inputs ──
cells = readcsv(joinpath(REFDIR, "M_cells.csv"))
names = String.(cells["name"]); lats = fcol(cells, "lat"); ids = fcol(cells, "cell")
common_soil = readsoil(joinpath(REFDIR, "hainich_soilcolumn.txt"))
common_patches, common_modal = readcanopy_patches(joinpath(REFDIR, "hainich_individuals_2010.csv"))

@printf("\n=== COUPLED S+F+E EMULATOR ACROSS BIOMES — PER-CELL soil + canopy (real GSWP3-W5E5, %d yr) ===\n", YEARS)
@printf("Canopy basis: the %d-patch ENSEMBLE MEAN (the C's own output basis, ADR 0057).\n", 25)
@printf(
    "%-22s %5s %6s %6s %7s %7s %7s %7s %8s %6s %6s %8s\n",
    "biome", "lat", "Tair", "Tskin", "LE", "H", "Rn", "Bowen", "maxRes", "npat", "ntree", "GPP"
)
percell = Dict{String, NamedTuple}(); legacy = Dict{String, NamedTuple}(); modal = Dict{String, NamedTuple}()
for (k, name) in enumerate(names)
    forc, tairK = forcings_of(name)
    soil = readsoil(joinpath(REFDIR, "M_soilcolumn_$(name).txt"))
    patches, mi = readcanopy_patches(joinpath(REFDIR, "M_individuals_$(name)_2010.csv"))
    r, m = run_cell(patches, mi, soil, lats[k], forc, tairK)
    percell[name] = r
    modal[name] = m
    legacy[name] = first(run_cell(common_patches, common_modal, common_soil, lats[k], forc, tairK))
    @printf(
        "%-22s %5.1f %6.1f %6.1f %7.1f %7.1f %7.1f %7.2f %8.1e %6d %6.1f %8.0f\n",
        name, lats[k], mean(tairK) - 273.15, r.tskin, r.le, r.h, r.rn, r.bowen, r.res,
        r.npatch, r.ntree, r.gpp
    )
    flush(stdout)      # Julia block-buffers stdout to a file (CLAUDE.md §9)
end

@printf("\n=== the SIZE of the OLD modal-patch basis (what this driver reported before ADR 0057) ===\n")
@printf("%-22s %7s %7s %7s %8s %8s %7s\n", "biome", "LE_ens", "LE_mod", "mod/ens", "GPP_ens", "GPP_mod", "mod/ens")
for name in names
    e = percell[name]; m = modal[name]
    @printf(
        "%-22s %7.1f %7.1f %7.3f %8.0f %8.0f %7.3f\n",
        name, e.le, m.le, m.le / e.le, e.gpp, m.gpp, m.gpp / e.gpp
    )
end
@printf("The modal patch is the DENSEST one (most living trees), so it reads high — ADR 0053 measured\n")
@printf("1.12–1.72× the ensemble FPC. Nothing here is a model change; it is the basis the numbers are on.\n")

@printf("\n=== the SAME cells under the LEGACY common Hainich canopy + Hainich soil (climate only) ===\n")
@printf("%-22s %7s %7s %7s %8s %8s %8s\n", "biome", "LE", "H", "Bowen", "GPP", "dLE", "dBowen")
for name in names
    l = legacy[name]; p = percell[name]
    @printf(
        "%-22s %7.1f %7.1f %7.2f %8.0f %+8.1f %+8.2f\n",
        name, l.le, l.h, l.bowen, l.gpp, p.le - l.le, p.bowen - l.bowen
    )
end

@printf("\nEnergy closes by construction in every cell and both configurations (maxRes ~ 0).\n")
@printf("Partitioning still tracks the climate — tropical LE-dominated, dry biomes H-dominated — but each\n")
@printf("cell now carries ITS OWN rooting depth / plant-available water / canopy, so the dLE column is the\n")
@printf("VEGETATION+SOIL contribution that the common-canopy design could not show.\n")
