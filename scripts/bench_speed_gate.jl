#!/usr/bin/env julia
# ── 5-pre · THE END-TO-END SPEED GATE, JULIA ARM (line O; EXECUTION_PLAN.md §4, ADR 0093/0094) ────────
#
# Reports **core-seconds per cell-year** for the shipped coupled emulator at the PRODUCTION patch
# configuration, on named cells and named years, so the number can be compared with the LPJmL-FIT C
# binary measured on the SAME cells and years by `scripts/bench_speed_gate_c.sh`.
#
# WHY THIS EXISTS. Per-year ESM speed is goal #2 (ADR 0094). The only speed measurement the project has
# is ADR 0093's single session (1.096 core-s/cell-yr vs the C's 0.290-0.383), produced by a throwaway
# script on /p/tmp that no longer matches the shipping API. Nothing in CI measures speed, which is how a
# 3.8x regression survived ~40 sessions. This script is the reproducible replacement.
#
# ⚠ THREE THINGS THE ADR-0093 HARNESS GOT WRONG OR LEFT OUT — fixed here, and each changes the number:
#
#   1. **It printed "TOTAL coupled S+F+E" but ran NO Component S.** `bench_emulator.jl` calls
#      `run_coupled_cell(core, clo, state, forc)` with `slow` left at its `nothing` default, so the
#      annual demography, the count DRF and the recruit copula were never in the loop. Arm `FE` below
#      reproduces exactly that configuration (so ADR 0093's number is checkable); arm `SFE` is the
#      production coupled model the plan's gate is actually about.
#   2. **It timed 1 patch at a time and multiplied by 25.** That is right for cost but it must be said,
#      because the C's 25 patches share one soil column and one cell (the emulator's do not — 5b).
#   3. **It never reported the per-INDIVIDUAL normalisation on both sides.** The C carries ~149
#      individuals per patch at Hainich; the emulator's roster is built from the `ind` writer's >5 m
#      stems (~10.9 per patch). So a cell-year ratio compares two different amounts of work. Both
#      normalisations are printed here and BOTH must be quoted together.
#
# BASIS, stated because every number is conditional on it:
#   * cells      — the five registered biome cells (`references/M_cells.csv`); Hainich (orderA 42490,
#                  51.25N/10.25E) is the headline because it is the cell the C arm and ADR 0093 use.
#   * years      — 2010-2019 (10), the span of `biome_forcing_<name>.csv`.
#   * patches    — 25, one independent ensemble member per patch of the cell's 2010 `ind` canopy
#                  (ADR 0057/0105 — the basis the C itself reports).
#   * cores      — ONE. Run with `--threads=1`: `DRF.predict` and `fit_forest` use `Threads.@threads`,
#                  so a multi-threaded run reports a smaller WALL time for the same core-seconds.
#   * artifacts  — the pinned `_t8` DRF + recruit copula (ADR 0023), as `biome_slow_oracle_probe.jl`.
#   * F params   — `wscal_leafon = true` (ADR 0051) and the package defaults for everything else.
#                  Physics options change the cost; they are printed with the result.
#
# Timing method: every arm is compiled once on a throwaway warm-up cell, then `GC.gc()`, then timed.
# The DRF/copula deserialisation (~5 s, once per process) is EXCLUDED from every arm — it is a
# start-up cost, not a per-cell-year cost — and reported separately.
#
# Run (CLAUDE.md §2 — never the login node; the `slurm-guard` hook enforces it):
#   NCPUS=2 TIME=01:00:00 scripts/sbatch_julia.sh O-speedgate --project=. --threads=1 \
#       scripts/bench_speed_gate.jl
# Optional env: BENCH_YEARS (default 10), BENCH_CELLS (comma-separated names, default all five),
#               BENCH_REPS (default 1; >1 takes the MINIMUM over repeats, the standard noise-robust
#               choice for a timing benchmark on a shared machine).
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams, FDiffParams
using LPJmLFITEmulator.DRF
using Statistics, Printf, LinearAlgebra

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
const LOGDIR = joinpath(@__DIR__, "..", "logs")
const σ = 5.670374419e-8
const ART = "/p/tmp/jamirp/emulator_global"
const T8_DRF = joinpath(ART, "drf_forest_global_pooled_w20_t8.drf")
const T8_RCOP = joinpath(ART, "recruit_copula_global_pooled_w20_t8.rcop")
const PATCH_AREA = 225.0
const NYEAR = parse(Int, get(ENV, "BENCH_YEARS", "10"))
const NREP = parse(Int, get(ENV, "BENCH_REPS", "1"))

# One thread is the definition of a core-second here. Refuse to report a misleading number.
if Threads.nthreads() != 1
    @warn "running with $(Threads.nthreads()) threads — DRF.predict is threaded, so the SFE arm's " *
        "wall time will UNDERSTATE its core-seconds. Re-run with `--threads=1`."
end
BLAS.set_num_threads(1)

# ── readers (same layout as scripts/biome_slow_oracle_probe.jl — deliberately duplicated, not shared,
#    so the benchmark cannot be silently changed by an edit to a probe) ────────────────────────────────
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

"ALL patches of a cell's 2010 `ind` canopy — one ensemble member per patch (ADR 0057)."
function readcanopy_patches(path)
    ind = readcsv(path)
    v(k, r) = parse(Float64, ind[k][r])
    nt(r) = parse(Int, ind["type"][r])
    prows = Dict{Int, Vector{Int}}()
    for r in eachindex(ind["type"])
        (nt(r) <= 6 && v("height", r) > 0) && push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
    end
    pk = sort(collect(keys(prows)))
    return [build_patch(ind, prows[p]) for p in pk]
end

function forcings_of(name)
    f = readcsv(joinpath(REFDIR, "biome_forcing_$(name).csv"))
    tairK = fcol(f, "temp") .+ 273.15
    swd = fcol(f, "swdown"); lwn = fcol(f, "lwnet"); prec = fcol(f, "precip")
    huss = fcol(f, "huss"); co2 = fcol(f, "co2")
    n = min(length(tairK), NYEAR * 365)
    forc = [
        AtmForcing(;
                swdown = swd[i], lwdown = lwn[i] + σ * tairK[i]^4, tair = tairK[i], qair = huss[i],
                wind = 2.0, psurf = 1.0e5, precip = prec[i], co2 = co2[i]
            ) for i in 1:n
    ]
    return forc, tairK[1:n]
end

"The ACTIVE calibrated F parameter set with only `wscal_leafon` flipped (ADR 0051) — never a bare
 `FDiffParams()`, which would silently swap every other constant."
function leafon_params()
    p = FDiff.tebs_params(Float64)
    w = p.water
    fns = fieldnames(typeof(w))
    nt = NamedTuple{fns}(map(f -> getfield(w, f), fns))
    w2 = typeof(w)(; merge(nt, (; wscal_leafon = true))...)
    return FDiffParams{Float64}(p.photo, p.tstress, w2, p.resp, p.allom, p.nlambda, p.ω)
end

# ── artifacts (start-up cost, timed but EXCLUDED from every per-cell-year number) ─────────────────────
t_art = @elapsed begin
    forest = DRF.load_forest(T8_DRF)
    cop, af, xcop, axnames, cond_cols = DRF.load_copula(T8_RCOP)
end
@assert forest.nfeat == 15 "count DRF nfeat=$(forest.nfeat), expected 15"
@assert axnames == ["SLA", "Wooddens", "D95max", "minwscal"] "unexpected copula axes: $(axnames)"

cells = readcsv(joinpath(REFDIR, "M_cells.csv"))
allnames = String.(cells["name"])
lats = fcol(cells, "lat")
n_inits = fcol(cells, "n_init")
age0s = fcol(cells, "age0")
cellids = haskey(cells, "cell") ? cells["cell"] : fill("?", length(allnames))
bnds = [
    [
            parse(Float64, cells["eco_diag_gdd_5"][k]), parse(Float64, cells["tas_cold_month"][k]),
            parse(Float64, cells["soil_depth"][k]), parse(Float64, cells["co2"][k]),
        ] for k in eachindex(allnames)
]
want = get(ENV, "BENCH_CELLS", "")
sel = isempty(want) ? collect(eachindex(allnames)) :
    [findfirst(==(strip(s)), allnames) for s in split(want, ',')]
any(isnothing, sel) && error("BENCH_CELLS names not in M_cells.csv: $(want) (have $(allnames))")

# ── the three arms ───────────────────────────────────────────────────────────────────────────────────
# Each runs ONE patch member for NYEAR years and returns (elapsed_s, n_cohort_years) so the per-tree
# normalisation counts the roster the run ACTUALLY carried (S adds and removes cohorts every year).

"Arm SFE — the production coupled model: F + E + Component S (count DRF, recruit copula, ClimBuf)."
function run_member_sfe(k, pools, tmpls, soil, forc, tairK, member)
    core = FDiffFastCore(deepcopy(pools), deepcopy(tmpls), soil, lats[k]; params = leafon_params())
    clo = SEBEnergyClosure(; t_soil0 = mean(tairK))
    state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
    rc = RecruitCopula{Float64}(cop, af, xcop, make_recruit_to_pools(axnames), live_flux_cond)
    s = FluxDrivenSlowEmulator(
        core, forest; boundary = copy(bnds[k]), n_init = n_inits[k], age0 = age0s[k],
        seed = member, recruit_copula = rc
    )
    cb = ClimBuf()
    ncy = 0
    for y in 1:NYEAR
        rng = ((y - 1) * 365 + 1):(y * 365)
        last(rng) <= length(forc) || break
        ncy += count(p -> !p.is_grass, core.pools)
        run_coupled_cell(core, clo, state, view(forc, rng); slow = s, climbuf = cb, days_per_year = 365)
    end
    return ncy
end

"Arm FE — F + E, NO Component S. This is EXACTLY the configuration ADR 0093 measured at 1.096."
function run_member_fe(k, pools, tmpls, soil, forc, tairK, member)
    core = FDiffFastCore(deepcopy(pools), deepcopy(tmpls), soil, lats[k]; params = leafon_params())
    clo = SEBEnergyClosure(; t_soil0 = mean(tairK))
    state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
    ncy = 0
    for y in 1:NYEAR
        rng = ((y - 1) * 365 + 1):(y * 365)
        last(rng) <= length(forc) || break
        ncy += count(p -> !p.is_grass, core.pools)
        run_coupled_cell(core, clo, state, view(forc, rng); days_per_year = 365)
    end
    return ncy
end

"Arm F — the fast core alone (daily `step!` + annual `annual_step!`), no energy closure, no S.
 Isolates what the energy closure costs."
function run_member_f(k, pools, tmpls, soil, forc, _tairK, member)
    core = FDiffFastCore(deepcopy(pools), deepcopy(tmpls), soil, lats[k]; params = leafon_params())
    state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
    ncy = 0
    for y in 1:NYEAR
        rng = ((y - 1) * 365 + 1):(y * 365)
        last(rng) <= length(forc) || break
        ncy += count(p -> !p.is_grass, core.pools)
        bc = stand_structure_tof(core)
        for i in rng
            step!(core, state, bc, forc[i])
        end
        annual_step!(core, state)
    end
    return ncy
end

const ARMS = [("SFE", run_member_sfe), ("FE", run_member_fe), ("F", run_member_f)]

struct CellResult
    name::String
    cellid::String
    npatch::Int
    ntree0::Float64          # mean stems per patch in the 2010 `ind` canopy
    nyear::Int
    t::Dict{String, Float64}       # arm -> best total core-s over the whole cell (all patches)
    ncy::Dict{String, Int}         # arm -> cohort-years actually carried (summed over patches)
    tper::Dict{String, Vector{Float64}}   # arm -> per-patch core-s (for the fixed/per-tree regression)
end

function bench_cell(k)
    name = allnames[k]
    forc, tairK = forcings_of(name)
    soil = readsoil(joinpath(REFDIR, "M_soilcolumn_$(name).txt"))
    patches = readcanopy_patches(joinpath(REFDIR, "M_individuals_$(name)_2010.csv"))
    nyr = min(NYEAR, length(forc) ÷ 365)
    tbest = Dict{String, Float64}(); ncys = Dict{String, Int}(); tpp = Dict{String, Vector{Float64}}()
    for (arm, f) in ARMS
        f(k, patches[1]..., soil, forc, tairK, 1)          # compile
        GC.gc()
        best = Inf; bestper = Float64[]; ncy = 0
        for _ in 1:NREP
            per = Float64[]; nc = 0
            for (m, p) in enumerate(patches)
                local n_m
                dt = @elapsed (n_m = f(k, p..., soil, forc, tairK, m))
                push!(per, dt); nc += n_m
            end
            s = sum(per)
            if s < best
                best = s; bestper = per; ncy = nc
            end
        end
        tbest[arm] = best; ncys[arm] = ncy; tpp[arm] = bestper
        @printf(
            "  %-4s %-24s  %7.3f core-s   (%d patches x %d yr)\n", arm, name, best, length(patches), nyr
        )
        flush(stdout)
    end
    ntree0 = mean(Float64[length(p[1]) for p in patches])
    return CellResult(name, string(cellids[k]), length(patches), ntree0, nyr, tbest, ncys, tpp)
end

# ── run ──────────────────────────────────────────────────────────────────────────────────────────────
githead = try
    strip(read(`git -C $(joinpath(@__DIR__, "..")) rev-parse --short HEAD`, String))
catch
    "unknown"
end
println("="^100)
@printf("SPEED GATE — Julia arm · commit %s · julia %s · %d thread(s)\n", githead, VERSION, Threads.nthreads())
@printf(
    "artifacts: %s + %s  (deserialised in %.1f s — EXCLUDED from every rate below)\n",
    basename(T8_DRF), basename(T8_RCOP), t_art
)
@printf("years=%d  reps=%d  patch basis = the cell's own 2010 `ind` ensemble\n", NYEAR, NREP)
println("="^100)

results = CellResult[]
for k in sel
    push!(results, bench_cell(k))
end

# ── report ───────────────────────────────────────────────────────────────────────────────────────────
println()
println("core-SECONDS PER CELL-YEAR (1 core; the whole patch ensemble is one cell)")
@printf(
    "%-24s %6s %5s %7s | %10s %10s %10s | %8s\n",
    "cell", "cellid", "npat", "stems/p", "S+F+E", "F+E", "F only", "S share"
)
println("-"^100)
for r in results
    cy = r.nyear
    a, b, c = r.t["SFE"] / cy, r.t["FE"] / cy, r.t["F"] / cy
    @printf(
        "%-24s %6s %5d %7.2f | %10.4f %10.4f %10.4f | %7.1f%%\n",
        r.name, r.cellid, r.npatch, r.ntree0, a, b, c, 100 * (a - b) / a
    )
end
println()
println("core-SECONDS PER PATCH-YEAR, and per COHORT-year (the emulator's per-individual unit)")
@printf("%-24s | %10s %10s | %12s %12s\n", "cell", "SFE/patch-yr", "FE/patch-yr", "SFE/cohort-yr", "FE/cohort-yr")
println("-"^100)
for r in results
    py = r.npatch * r.nyear
    @printf(
        "%-24s | %10.5f %10.5f | %12.3e %12.3e\n",
        r.name, r.t["SFE"] / py, r.t["FE"] / py, r.t["SFE"] / r.ncy["SFE"], r.t["FE"] / r.ncy["FE"]
    )
end
println()
println("FIXED vs PER-COHORT split — least squares  cost_patch = a + b*ntree0  over the 25 members")
for r in results
    patches = readcanopy_patches(joinpath(REFDIR, "M_individuals_$(r.name)_2010.csv"))
    ntree = Float64[length(p[1]) for p in patches]
    for arm in ("SFE", "FE")
        y = r.tper[arm]
        X = hcat(ones(length(y)), ntree)
        c = X \ y
        @printf(
            "  %-4s %-24s a=%.5f core-s  b=%.5f core-s/cohort  (fixed = %.1f%% at %.1f cohorts)\n",
            arm, r.name, c[1], c[2], 100 * c[1] / (c[1] + c[2] * mean(ntree)), mean(ntree)
        )
    end
end

# ── machine-readable output (logs/ is gitignored; the CI gate reads this file) ────────────────────────
mkpath(LOGDIR)
out = joinpath(LOGDIR, "bench_speed_gate.csv")
open(out, "w") do io
    println(io, "# LPJmL-FIT emulator speed gate — Julia arm")
    println(io, "# commit=$(githead) julia=$(VERSION) threads=$(Threads.nthreads()) reps=$(NREP)")
    println(io, "# artifacts=$(basename(T8_DRF)),$(basename(T8_RCOP)) artifact_load_s=$(round(t_art, digits = 2))")
    println(io, "cell,cellid,npatch,stems_per_patch,years,arm,total_core_s,core_s_per_cell_year,core_s_per_patch_year,cohort_years,core_s_per_cohort_year")
    for r in results, arm in ("SFE", "FE", "F")
        @printf(
            io, "%s,%s,%d,%.4f,%d,%s,%.6f,%.6f,%.8f,%d,%.6e\n",
            r.name, r.cellid, r.npatch, r.ntree0, r.nyear, arm,
            r.t[arm], r.t[arm] / r.nyear, r.t[arm] / (r.npatch * r.nyear),
            r.ncy[arm], r.t[arm] / r.ncy[arm]
        )
    end
end
println("\nwrote $(out)")
println("=== BENCH DONE ===")
