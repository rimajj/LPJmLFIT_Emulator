#!/usr/bin/env julia
# ── THE PATCH-ENSEMBLE BASIS FOR THE 5-BIOME COUPLED DRIVER (line M, ADR 0057) ───────────────────────
# Measures the per-cell coupled F+E signatures on BOTH canopy bases, so the deliberate baseline
# regeneration in `test/testitems/biome_coupled_tests.jl` (item 2's pinned LE/GPP) is a MEASUREMENT and
# not a re-record of whatever the new code happens to print:
#
#   ens  = every patch of the cell's `ind` canopy run INDEPENDENTLY, outputs averaged — the C's own
#          output basis (`fwriteoutput.c` reports the 25-patch ensemble mean), and the basis
#          `biome_fdiff_oracle_probe.jl` / `biome_resilience_probe.jl` already use.
#   mod  = the single MODAL patch (most living trees) the production driver used until now, which
#          ADR 0053 measured at 1.12-1.72x the ensemble's FPC.
#
# Everything else is byte-identical to the CI gate it feeds: 2 years, DEFAULT params (so
# `wscal_leafon = false` — these are fingerprint pins, not science numbers), `slow = nothing`,
# `SEBEnergyClosure(t_soil0 = mean(tair))`, `w = 0.7`.
#
# Also reports the wall-clock cost per basis, which is what decides whether the CI gate can afford the
# ensemble at all, and the minimum pairwise LE separation, which is the property that makes the pins a
# driver-level fallback detector rather than five independent smoke checks.
#
# `TWO_LAYER=1` swaps E's ground-heat scheme to the opt-in two-layer prognostic soil column (ADR 0074).
# That is the OTHER change scheduled to move these same pins, so it re-measures them through this same
# harness instead of a second script (`export` it — SLURM's --export=ALL carries it, a bare prefix on the
# wrapper does not reach the job).
#
# Run (SLURM, per CLAUDE.md §2):
#   scripts/sbatch_julia.sh M-enspin --project=. scripts/biome_ensemble_pin_probe.jl
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
using LPJmLFITEmulator.Allometry
using Statistics, Printf

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
const σ = 5.670374419e-8
const YEARS = 2            # == the CI gate's horizon
const TWO_LAYER = get(ENV, "TWO_LAYER", "0") == "1"    # ADR 0074's opt-in ground-heat column
mkclo(t0) = SEBEnergyClosure(;
    t_soil0 = t0, params = SEBParams{Float64}(; enable_two_layer = TWO_LAYER)
)

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

"ALL patches, sorted by patch id, plus the index of the modal (most-trees) one."
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

"One patch through the coupled loop, exactly as the CI gate drives it."
function run_patch(pools, tmpls, soil, lat, forc, tairK)
    core = FDiffFastCore(deepcopy(pools), deepcopy(tmpls), soil, lat)
    clo = mkclo(mean(tairK))
    state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
    out = run_coupled_cell(core, clo, state, forc; days_per_year = 365)
    return (
        le = mean(out.le), h = mean(out.h), rn = mean(out.rn), gpp = mean(out.gpp),
        tskin = mean(out.t_skin) - 273.15, res = maximum(abs, out.resid),
        lemin = minimum(out.le), fpc = LPJmLFITEmulator.stand_structure_tof(core).fpc,
    )
end

cells = readcsv(joinpath(REFDIR, "M_cells.csv"))
names = String.(cells["name"]); lats = fcol(cells, "lat")

@printf("=== PATCH-ENSEMBLE vs MODAL-PATCH coupled signatures — 5 biome cells, %d yr, DEFAULT params ===\n", YEARS)
@printf("(slow=nothing; wscal_leafon=false = the package default, because these feed a CI FINGERPRINT)\n")
@printf("ground heat: %s\n\n", TWO_LAYER ? "TWO-LAYER prognostic column (ADR 0074, enable_two_layer=true)" : "default single conductance vs the 30-day air EWMA")
@printf(
    "%-22s %6s %10s %10s %7s %10s %10s %7s %9s %8s %8s\n",
    "cell", "npatch", "LE_ens", "LE_mod", "mod/ens", "GPP_ens", "GPP_mod", "mod/ens", "maxRes", "minLE", "t_ens[s]"
)
ens = Dict{String, NamedTuple}(); mod = Dict{String, NamedTuple}()
for (k, name) in enumerate(names)
    forc, tairK = forcings_of(name)
    soil = readsoil(joinpath(REFDIR, "M_soilcolumn_$(name).txt"))
    patches, modal = readcanopy_patches(joinpath(REFDIR, "M_individuals_$(name)_2010.csv"))
    t0 = time()
    runs = [run_patch(p, t, soil, lats[k], forc, tairK) for (p, t) in patches]
    dt = time() - t0
    e = (
        le = mean(r.le for r in runs), h = mean(r.h for r in runs), rn = mean(r.rn for r in runs),
        gpp = mean(r.gpp for r in runs), tskin = mean(r.tskin for r in runs),
        res = maximum(r.res for r in runs), lemin = minimum(r.lemin for r in runs),
        fpc = mean(r.fpc for r in runs), npatch = length(runs), secs = dt,
    )
    ens[name] = e
    mod[name] = runs[modal]
    @printf(
        "%-22s %6d %10.6g %10.6g %7.3f %10.6g %10.6g %7.3f %9.1e %8.2f %8.1f\n",
        name, e.npatch, e.le, mod[name].le, mod[name].le / e.le,
        e.gpp, mod[name].gpp, mod[name].gpp / e.gpp, e.res, e.lemin, dt
    )
    flush(stdout)      # Julia block-buffers stdout to a file (CLAUDE.md §9)
end

@printf("\n--- PIN BLOCK for test/testitems/biome_coupled_tests.jl (ensemble basis) ---\n")
for name in names
    @printf("        \"%s\" => (%.6g, %.6g),\n", name, ens[name].le, ens[name].gpp)
end

@printf("\n--- the pins must stay mutually distinguishable at the gate's tolerances ---\n")
les = [ens[n].le for n in names]; gpps = [ens[n].gpp for n in names]
sep(v) = minimum(abs(v[i] - v[j]) / max(v[i], v[j]) for i in eachindex(v) for j in (i + 1):length(v))
@printf("min pairwise LE separation  = %.4f  (gate rtol 0.02)\n", sep(les))
@printf("min pairwise GPP separation = %.4f  (gate rtol 0.03)\n", sep(gpps))

@printf("\n--- ensemble vs modal, the whole diagnostic row ---\n")
@printf("%-22s %8s %8s %8s %8s %8s %8s %8s %8s\n", "cell", "Tsk_ens", "Tsk_mod", "H_ens", "H_mod", "Rn_ens", "Rn_mod", "fpc_ens", "fpc_mod")
for name in names
    e = ens[name]; m = mod[name]
    @printf(
        "%-22s %8.3f %8.3f %8.3f %8.3f %8.3f %8.3f %8.4f %8.4f\n",
        name, e.tskin, m.tskin, e.h, m.h, e.rn, m.rn, e.fpc, m.fpc
    )
end

@printf("\ntotal ensemble wall-clock = %.1f s over %d patch-runs\n", sum(ens[n].secs for n in names), sum(ens[n].npatch for n in names))
@printf("(the modal-patch gate ran 5 patch-runs; the ratio is what the CI gate pays for the C's basis)\n")
