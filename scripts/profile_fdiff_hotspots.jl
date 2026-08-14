#!/usr/bin/env julia
# ── 5-pre · WHERE THE EMULATOR'S TIME GOES (line O; EXECUTION_PLAN.md §4, ADR 0093 §2) ────────────────
#
# READ-ONLY. This script measures; it changes nothing in `src/`. Line M owns `src/fdiff.jl`,
# `src/fdiff_smoothops.jl` and `src/components/fast.jl` (CLAUDE.md §9 Gap 1) and is working inside them,
# so the optimisation this profile scopes must be handed over, not landed from here.
#
# THE QUESTION. ADR 0093 measured the Julia per-individual daily step at 51x the C's (3.998e-3 vs
# 7.84e-5 core-s per individual-year) but never said WHERE that goes. Without an attribution, "37x of
# unclaimed single-core engineering" is an assertion.
#
# THREE INDEPENDENT MEASUREMENTS, because a sampling profile alone is not enough to act on:
#
#   A. SAMPLING PROFILE of the real coupled daily rollout — self time and inclusive ("children") time
#      per function, the same view `perf report --children` gives for the C, so the two are comparable.
#
#   B. THE λ-SOLVE SWEEP — the decisive one, and it needs no source edit because the iteration count is
#      a PARAMETER (`FDiffParams.nlambda`, default 25). Re-running the identical rollout at
#      nlambda ∈ {25,12,6,3,1} traces total cost against λ work directly, so the λ solve's share is
#      measured end-to-end rather than inferred from samples. The GPP each arm produces is printed
#      beside its cost, so the accuracy price of a shorter solve is visible in the same table.
#
#   C. MICROBENCHMARKS of the leaf kernels (`photosynthesis`, `solve_lambda`, `temp_stress`,
#      `priestley_taylor_eeq`, `canopy_conductance`) plus a CALL-COUNT audit of the per-individual
#      per-day path, so cost can be attributed as (calls x cost) and checked against A.
#
# ⚠ WHAT THE CALL-COUNT AUDIT FOUND, and why it reframes EXECUTION_PLAN.md §4's "5a". The plan says the
# C's λ bisection is 33.3 % of the C's runtime and proposes "a fixed-iteration or analytic λ closure"
# for the Julia core. But `solve_lambda` (src/fdiff.jl:655) is ALREADY fixed-iteration — and it is far
# more expensive than the C's bisection, for a reason the plan does not mention: it takes its Newton
# derivative by CENTRAL FINITE DIFFERENCE (`dg = (g(λ+h) - g(λ-h)) / 2h`), so every one of the 25
# iterations costs THREE `photosynthesis` evaluations, not one. That is 75 photosynthesis calls per
# individual per day, against the C's <=30. The fix is therefore not "make it fixed-iteration" (it is)
# but "stop paying 3 calls per iteration, and stop paying 25 iterations" — measured below.
#
# Run (CLAUDE.md §2 — never the login node):
#   NCPUS=2 TIME=01:00:00 scripts/sbatch_julia.sh O-profile --project=. --threads=1 \
#       scripts/profile_fdiff_hotspots.jl
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams, FDiffParams
using Profile, Statistics, Printf, LinearAlgebra

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
const σ = 5.670374419e-8
const CELL = get(ENV, "PROFILE_CELL", "temperate_hainich")
const NYEAR = parse(Int, get(ENV, "PROFILE_YEARS", "10"))
BLAS.set_num_threads(1)

# ── readers (identical layout to scripts/bench_speed_gate.jl) ─────────────────────────────────────────
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

cells = readcsv(joinpath(REFDIR, "M_cells.csv"))
k = findfirst(==(CELL), String.(cells["name"]))
k === nothing && error("cell $(CELL) not in M_cells.csv")
lat = fcol(cells, "lat")[k]

f = readcsv(joinpath(REFDIR, "biome_forcing_$(CELL).csv"))
tairK = fcol(f, "temp") .+ 273.15
n = min(length(tairK), NYEAR * 365)
forc = [
    AtmForcing(;
            swdown = fcol(f, "swdown")[i], lwdown = fcol(f, "lwnet")[i] + σ * tairK[i]^4,
            tair = tairK[i], qair = fcol(f, "huss")[i], wind = 2.0, psurf = 1.0e5,
            precip = fcol(f, "precip")[i], co2 = fcol(f, "co2")[i]
        ) for i in 1:n
]
soil = readsoil(joinpath(REFDIR, "M_soilcolumn_$(CELL).txt"))
patches = readcanopy_patches(joinpath(REFDIR, "M_individuals_$(CELL)_2010.csv"))
nyr = n ÷ 365
ntree = Float64[length(p[1]) for p in patches]

function params_nlambda(nl::Int)
    p = FDiff.tebs_params(Float64)
    w = p.water
    fns = fieldnames(typeof(w))
    nt = NamedTuple{fns}(map(f -> getfield(w, f), fns))
    w2 = typeof(w)(; merge(nt, (; wscal_leafon = true))...)
    return FDiffParams{Float64}(p.photo, p.tstress, w2, p.resp, p.allom, nl, p.ω)
end

"One patch through the F core for `nyr` years. Returns (elapsed_s, Σ GPP) — cost AND answer, so a
 cheaper λ solve cannot be sold without showing what it did to the flux."
function run_patch(pools, tmpls, pars)
    core = FDiffFastCore(deepcopy(pools), deepcopy(tmpls), soil, lat; params = pars)
    state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
    gpp = 0.0
    for y in 1:nyr
        bc = stand_structure_tof(core)
        for i in ((y - 1) * 365 + 1):(y * 365)
            out = step!(core, state, bc, forc[i])
            gpp += out.gpp
        end
        annual_step!(core, state)
    end
    return gpp
end

run_all(pars) = sum(run_patch(p..., pars) for p in patches)

githead = try
    strip(read(`git -C $(joinpath(@__DIR__, "..")) rev-parse --short HEAD`, String))
catch
    "unknown"
end
println("="^100)
@printf(
    "FDIFF HOT SPOTS — commit %s · julia %s · %d thread(s)\n", githead, VERSION, Threads.nthreads()
)
@printf(
    "cell %s (orderA %s, lat %.2f) · %d patches · %d yr · %.2f stems/patch (mean), %d total stem-years\n",
    CELL, cells["cell"][k], lat, length(patches), nyr, mean(ntree), round(Int, sum(ntree) * nyr)
)
println("="^100)

# ── A. SAMPLING PROFILE ──────────────────────────────────────────────────────────────────────────────
p25 = params_nlambda(25)
run_all(p25)                                    # compile
GC.gc()
t_base = @elapsed (gpp_base = run_all(p25))
@printf(
    "\nbaseline (nlambda=25): %.3f core-s for the whole 25-patch cell x %d yr  = %.4f core-s/cell-yr\n",
    t_base, nyr, t_base / nyr
)

Profile.clear()
Profile.init(; n = 30_000_000, delay = 0.0002)
@profile run_all(p25)

println("\n── A1. SELF time (Profile's own flat view; `count` is samples, share is of total) ───────────")
Profile.print(; format = :flat, sortedby = :count, mincount = 20, noisefloor = 0.0, C = false)

# Inclusive ("children") view, built from the raw backtrace stream so it is directly comparable with
# `perf report --children` on the C side. `include_meta = false` strips the per-sample thread/task
# metadata words that would otherwise be parsed as instruction pointers. A function is counted ONCE
# per sample it appears in, so recursion cannot inflate a share above 100 %.
println("\n── A2. INCLUSIVE time (the `perf --children` view, comparable with the C profile), top 25 ───")
try
    data = Profile.fetch(; include_meta = false)
    lidict = Profile.getdict(data)
    inclc = Dict{Symbol, Int}()
    nsample = 0
    stack = Set{Symbol}()
    for ip in data
        if ip == 0                              # end of one backtrace
            nsample += 1
            for fn in stack
                inclc[fn] = get(inclc, fn, 0) + 1
            end
            empty!(stack)
            continue
        end
        frames = get(lidict, ip, nothing)
        frames === nothing && continue
        for fr in (frames isa AbstractVector ? frames : [frames])
            fr.from_c && continue
            push!(stack, fr.func)
        end
    end
    tot = max(nsample, 1)
    @printf("  (%d samples)\n%6s  %s\n", tot, "share", "function")
    for (kk, v) in sort(collect(inclc); by = last, rev = true)[1:min(25, length(inclc))]
        @printf("%5.1f%%  %s\n", 100v / tot, string(kk))
    end
catch e
    println("  inclusive view unavailable: ", e)
end

# ── B. THE λ-SOLVE SWEEP — cost AND flux vs the iteration count ──────────────────────────────────────
println("\n── B. λ-SOLVE SWEEP (`FDiffParams.nlambda`; no source change, it is a parameter) ────────────")
@printf(
    "%8s | %10s %14s | %10s | %12s %10s\n",
    "nlambda", "core-s", "core-s/cell-yr", "vs n=25", "Σ GPP", "ΔGPP"
)
println("-"^100)
sweep = Tuple{Int, Float64, Float64}[]
for nl in (25, 12, 6, 3, 2, 1)
    pars = params_nlambda(nl)
    run_all(pars)                               # compile this specialisation
    GC.gc()
    local g
    t = @elapsed (g = run_all(pars))
    push!(sweep, (nl, t, g))
    @printf(
        "%8d | %10.3f %14.4f | %9.2fx | %12.4g %9.3f%%\n",
        nl, t, t / nyr, t_base / t, g, 100 * (g - gpp_base) / gpp_base
    )
    flush(stdout)
end
t1 = sweep[end][2]
@printf("\n  λ-solve share of total runtime  = %.1f%%\n", 100 * (t_base - t1) / t_base)
println("    (= 1 - t[nlambda=1]/t[nlambda=25]; nlambda=1 still pays one 3-evaluation Newton step,")
println("     so this is a LOWER bound on what the λ path costs.)")
per_iter = (t_base - t1) / 24
@printf("  marginal cost of ONE Newton iteration = %.4f core-s per cell-year\n", per_iter / nyr)
println("    (each iteration = 3 photosynthesis calls, because the derivative is a central difference.)")

# ── C. LEAF-KERNEL MICROBENCHMARKS + the call-count audit ────────────────────────────────────────────
println("\n── C. LEAF KERNELS (cost of one call) and the per-individual-per-day CALL COUNT ─────────────")
ph = PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.02)
ts0 = FDiff.temp_stress(TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), 20.0, 12.0)
co2Pa = 40.0; apar0 = 8.0e6; dl = 12.0
# ⚠ Everything the kernel does NOT vary over must be built OUTSIDE the timed closure, and the result
# must be accumulated so the compiler cannot delete the call. The first version of this block built
# `params_nlambda(1)` inside the loop and reported `nlambda=1` as SLOWER than `nlambda=25` — a physically
# impossible result that is the tell for exactly this mistake. Treat these as indicative only: a kernel
# called through a closure is not inlined the way it is inside `daily_step_canopy`, so the absolute ns
# figures run high. The SWEEP in section B, not this block, is the load-bearing attribution.
const P1 = params_nlambda(1)
const P25 = p25
const TSP = TempStressParams{Float64}()
vm0 = FDiff.photosynthesis(ph, 0.7, ts0, co2Pa, 20.0, apar0, dl; comp_vm = true)[3]
function timeit(f, reps)
    f(0.7); GC.gc()
    acc = 0.0
    t = @elapsed (
        for i in 1:reps
            acc += f(0.7 + 1.0e-12i)
        end
    )
    acc == 12345.0 && println(" ")     # opaque use of `acc`, so the loop cannot be optimised away
    return t / reps
end
t_photo = timeit(λ -> FDiff.photosynthesis(ph, λ, ts0, co2Pa, 20.0, apar0, dl; comp_vm = true)[4], 200_000)
t_photo_nv = timeit(
    λ -> FDiff.photosynthesis(ph, λ, ts0, co2Pa, 20.0, apar0, dl; comp_vm = false, vm = vm0)[4], 200_000
)
t_lam25 = timeit(λ -> FDiff.solve_lambda(P25, 1.0e-4λ, ts0, co2Pa, 20.0, apar0, dl, vm0), 20_000)
t_lam1 = timeit(λ -> FDiff.solve_lambda(P1, 1.0e-4λ, ts0, co2Pa, 20.0, apar0, dl, vm0), 200_000)
t_tstr = timeit(λ -> FDiff.temp_stress(TSP, 20.0λ, dl), 500_000)
t_eeq = timeit(λ -> FDiff.priestley_taylor_eeq(P25.water, 200.0λ, -50.0, 20.0, dl, 0.15), 500_000)

@printf("  photosynthesis (comp_vm=true )   %8.1f ns\n", 1.0e9t_photo)
@printf("  photosynthesis (comp_vm=false)   %8.1f ns   <- the call the λ solve makes\n", 1.0e9t_photo_nv)
@printf(
    "  solve_lambda   (nlambda=25   )   %8.1f ns   = %.1f x the comp_vm=false call\n",
    1.0e9t_lam25, t_lam25 / t_photo_nv
)
@printf(
    "  solve_lambda   (nlambda=1    )   %8.1f ns   = %.1f x  (one iteration = 3 evaluations)\n",
    1.0e9t_lam1, t_lam1 / t_photo_nv
)
@printf("  temp_stress                      %8.1f ns\n", 1.0e9t_tstr)
@printf("  priestley_taylor_eeq             %8.1f ns\n", 1.0e9t_eeq)

println(
    """
    CALL COUNT per individual per day, read off `daily_step_canopy` (src/fdiff.jl):
      :1947  photosynthesis(comp_vm=true )   gp / conductance path                          1
      :1956  photosynthesis(comp_vm=true )   layered low-light share (conditional)         0-1
      :1994  photosynthesis(comp_vm=true )   vm for the λ solve                              1
      :2029  solve_lambda -> 25 Newton iterations x 3 evaluations (central difference)      75
      :2034  photosynthesis(comp_vm=false)   final assimilation at the solved λ               1
                                                                                     -------
                                                          TOTAL  78-79 photosynthesis calls
    The C does <=30 (`water_stressed.c:207`, one call per bisection step). So the Julia core pays
    ~2.6x the C's photosynthesis CALLS on top of whatever each call costs."""
)

ind_days = sum(ntree) * nyr * 365
@printf(
    "\n  order-of-magnitude check: %.0f individual-days x 78 calls x %.1f ns = %.2f core-s vs the\n",
    ind_days, 1.0e9t_photo_nv, ind_days * 78 * t_photo_nv
)
@printf("  measured %.2f core-s (ratio %.2f).\n", t_base, ind_days * 78 * t_photo_nv / t_base)
println("  A ratio above 1 is EXPECTED and is not a contradiction: the closure-called kernel above is")
println("  not inlined the way it is inside `daily_step_canopy`. Read it as `the right order`, nothing")
println("  more — section B is the attribution that carries weight.")
println("\n=== PROFILE DONE ===")
