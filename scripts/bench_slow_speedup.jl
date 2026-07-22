# P1 Step 9 / Gate-4 — measure the coupled-emulator cost of putting Component S in the loop, the honest
# way (docs/p1_s_in_loop_design.md §5). Run on a compute node (NOT the login node) for stable timings:
#   scripts/sbatch_train.sh scripts/bench_slow_speedup.jl      # or plain: julia --project=. scripts/bench_slow_speedup.jl
#
# TWO baselines, both named so the metric cannot move silently:
#   (a) OVERHEAD baseline — `slow=nothing` (fixed-N deterministic F) vs `slow=DemographicSlowEmulator`
#       over a Hainich decade. S is EXPECTED to ADD a small per-year cost here (demography on top of F) —
#       this is the ADR-0018 Option-C baseline, NOT the speed target. We report it to bound the overhead
#       and to prove S's per-year work is O(K) in the K persistent cohorts (not an explicit-N ensemble).
#   (b) SCIENTIFIC / horizon-collapse baseline — what S actually REPLACES is the LPJmL-FIT C individual-
#       based model: dozens–hundreds of EXPLICIT individuals × npatch, `-DPERMUTE` stochastic competition,
#       per-tree allocation, integrated over a MULTI-CENTURY spin-up. S collapses that to K cohorts + a
#       one-shot climate→distribution map with NO spin-up. That ratio is the real speed-up; it is measured
#       against the C binary offline (not in this script), and only AT MATCHED gate-3 panel error.
#
# This script REPORTS (writes logs/bench_slow_speedup.csv); the CI-robust structural invariant behind the
# speed-up (fixed roster of K cohorts across the whole run — no explicit-N growth) is asserted in the
# Gate-4 testitem in test/testitems/slow_demography_tests.jl.

using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
using LPJmLFITEmulator.Allometry

_mean(x) = sum(x) / length(x)
refdir = joinpath(dirname(pathof(LPJmLFITEmulator)), "..", "test", "testitems", "references")
function readcsv(path)
    lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
    hdr = split(strip(lines[1]), ',')
    rows = [split(strip(l), ',') for l in lines[2:end]]
    return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
end
ind = readcsv(joinpath(refdir, "hainich_individuals_2010.csv"))
f = readcsv(joinpath(refdir, "hainich_forcing_2010.csv"))
fc_(k) = parse.(Float64, f[k])
v(k, r) = parse(Float64, ind[k][r]);
nt(r) = parse(Int, ind["type"][r]);
n = length(fc_("doy"))
sd = Float64[]; whcs = Float64[]; rdist = Float64[]
for ln in eachline(joinpath(refdir, "hainich_soilcolumn.txt"))
    s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
    x = parse.(Float64, split(s)); push!(sd, x[2]); push!(whcs, x[3]); push!(rdist, x[4])
end
soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)
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
tair_K = fc_("temp") .+ 273.15; σ = 5.670374419e-8
year_forc = [
    AtmForcing(;
            swdown = fc_("swdown")[i], lwdown = fc_("lwnet")[i] + σ * tair_K[i]^4,
            tair = tair_K[i], qair = fc_("huss")[i], wind = 2.0, psurf = 1.0e5,
            precip = fc_("precip")[i], co2 = fc_("co2")[i]
        ) for i in 1:n
]
mkcore() = FDiffFastCore([mkp(r) for r in rows], [mkt(r) for r in rows], soil, 51.25)
mkclo() = SEBEnergyClosure(; t_soil0 = _mean(tair_K))
mkstate() = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))

NYEARS = 10
forcings = repeat(year_forc, NYEARS)
K = length(mkcore().pools)

run_none() = run_coupled_cell(mkcore(), mkclo(), mkstate(), forcings; days_per_year = n)
function run_slow()
    c = mkcore()
    return run_coupled_cell(c, mkclo(), mkstate(), forcings; slow = DemographicSlowEmulator(c), days_per_year = n)
end

# warm up (compile) both paths, then time
run_none(); run_slow()
REPS = 5
t_none = minimum(@elapsed(run_none()) for _ in 1:REPS)
t_slow = minimum(@elapsed(run_slow()) for _ in 1:REPS)
overhead_per_year_ms = (t_slow - t_none) / NYEARS * 1.0e3

println("── P1 Gate-4 overhead measurement (Hainich, $(NYEARS)-yr, best of $REPS) ──")
println("K persistent cohorts (S's per-year work is O(K))     : ", K)
println("coupled decade, slow=nothing (fixed-N F)   [s]        : ", round(t_none; digits = 4))
println("coupled decade, slow=DemographicSlowEmulator [s]      : ", round(t_slow; digits = 4))
println("S demography overhead per year               [ms]     : ", round(overhead_per_year_ms; digits = 3))
println("overhead as fraction of the fixed-N baseline          : ", round((t_slow - t_none) / t_none; digits = 4))
println()
println("Interpretation: S adds a small O(K) per-year cost on top of F (baseline (a); expected — S is not")
println("a speed-up HERE). The scientific speed-up (baseline (b)) is the collapse of the C-IBM's explicit-")
println("individual, -DPERMUTE, multi-century SPIN-UP to K=$K cohorts + a one-shot map — measured vs the C")
println("binary offline at matched gate-3 panel error, not against slow=nothing.")

logdir = joinpath(dirname(pathof(LPJmLFITEmulator)), "..", "logs")
isdir(logdir) || mkpath(logdir)
open(joinpath(logdir, "bench_slow_speedup.csv"), "w") do io
    println(io, "# P1 Gate-4 overhead (Hainich, best of $REPS reps); scientific speed-up (vs C-IBM) is offline")
    println(io, "nyears,K_cohorts,t_none_s,t_slow_s,overhead_per_year_ms,overhead_frac")
    println(io, "$NYEARS,$K,$t_none,$t_slow,$overhead_per_year_ms,$((t_slow - t_none) / t_none)")
end
println("\nwrote logs/bench_slow_speedup.csv")
