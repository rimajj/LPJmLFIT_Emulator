# DIAGNOSE THE COUNT RECURSION — line M's inbound finding (ADR 0054), measured on the S side.
#
# WHY. ADR 0054 (line M, M3's S side) measured that a free-running coupled rollout integrates a ~5 %/yr
# one-step count bias into +36-81 % over ten years, and that TEACHER-FORCING `s.n_prev` back onto the C's
# own per-patch count each year removes 59-72 % of the total coupled count error in all five biome cells.
# M correctly refused to fix it: `src/components/slow.jl` is line S's exclusive path (ADR 0029). M named
# the defect "the count recursion is unanchored". This probe asks what, precisely, is unanchored — because
# "unanchored" can mean two different things and they have different owners and different fixes:
#
#   (A) EXPOSURE BIAS. In the training table `n_prev` is the C's OWN previous `n_living`
#       (`build_slow_runtime_table.py:572`, a `shift(1)` of the truth), never a prediction. At runtime the
#       DRF consumes its own output (`slow.jl:1110`). That is a train/inference basis shift (the ADR-0023
#       class) and it can only be closed on the TRAINING side — scheduled sampling, or dropping `n_prev`
#       from the feature set. Both need a global retrain. NOT fixable from the runtime.
#
#   (B) STATE INCOHERENCE. `slow.jl:1026` CLAMPS the demographic ratio
#       `ρ = clamp(target/n_prev, 1-max_mort, 1+max_estab)` and applies the CLAMPED ρ to the roster, but
#       `slow.jl:1110` then assigns the RAW, UNCLAMPED `target` to `n_prev`. So in any year the clamp
#       binds, the AR state and the physical roster move by DIFFERENT factors, and nothing ever re-syncs
#       them: the emulator's next feature row reports a stand it does not have. The k-cap merge and the
#       ADR-0049 hazard `shortfall` are two further sites where the realized count can miss `target`.
#       This one IS S-side, and fixing it needs no retrain.
#
# (A) and (B) are not alternatives — both can be present. The point of separating them is that a fix for
# (B) must not be SOLD as a fix for (A): M's teacher-forcing arm anchors to the C truth and therefore
# removes both, so its 59-72 % is an upper bound on what (B) alone can buy, not a prediction for it.
#
# WHAT IT REPORTS
#   (a) COHERENCE — per year: `n_prev` before, the DRF `target`, the RAW ratio `target/n_prev`, the CLAMPED
#       ρ actually applied, the realized tree-density ratio, and the coherence residual
#       `realized / ρ_applied` (1.0 ⇐ the roster did what ρ asked). Plus the count of clamp-binding years
#       and the CUMULATIVE divergence `Π raw/ρ_applied` — the factor by which the AR state has drifted away
#       from the stand it claims to describe. If the clamp never binds this section is all 1.0 and defect
#       (B) is EMPTY on this configuration — which is a real possible outcome and must be reported as one.
#   (b) ANCHORING — an `n_init` sweep. A recursion with an attractor FORGETS its initial condition: run the
#       same forcing/seed from several `n_init` seeds and the trajectories converge. One without an
#       attractor carries the seed forever. This is the property that decides whether a multi-decadal or
#       online run is safe, and it is a stronger and cheaper test than a one-step bias estimate. The
#       docstring at `slow.jl:844-846` CLAIMS `n_init` "is self-corrected by the `max_*` clamp thereafter";
#       ADR 0101 §5 already measured a 4.5x-FIT swing from `n_init` 11.0 -> 7.0 over 81 yr, so that claim is
#       under suspicion and this section tests it directly.
#
# Hainich (cell 42490) only ⇒ every number here is "Hainich only" (guardrail 6). Constant repeated-2010
# forcing (the ADR-0048/0049 basis) so any drift is the RECURSION and not the forcing.
#
# Usage (SLURM — the guard blocks login-node probes, CLAUDE.md §2):
#   scripts/sbatch_julia.sh S-recanchor --project=. scripts/diagnose_count_recursion_anchor.jl
# ENV: YEARS (default 150), SEED (default 1), COPULA (default 1), K_CAP,
#      N_INIT_SWEEP (default "7,9,11,13,15"), DRF_ART/RCOP_ART + N_INIT/AGE0/BOUNDARY (artifact pair —
#      it is part of the measurement, ADR 0101 §3).

using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
using LPJmLFITEmulator.DRF
using Printf

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
const YEARS = parse(Int, get(ENV, "YEARS", "150"))
const SEED = parse(Int, get(ENV, "SEED", "1"))
const COPULA = get(ENV, "COPULA", "1") != "0"
const K_CAP = haskey(ENV, "K_CAP") ? parse(Int, ENV["K_CAP"]) : nothing
const MAX_MORT = 0.3            # the `FluxDrivenSlowEmulator` defaults; the clamp bounds under test
const MAX_ESTAB = 0.3
_mean(x) = sum(x) / length(x)

function readcsv(path)
    lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
    hdr = split(strip(lines[1]), ',')
    rows = [split(strip(l), ',') for l in lines[2:end]]
    return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
end

# ── the shared Hainich harness, byte-for-byte `trait_mortality_arm_probe.jl`'s construction ─────────────
ind = readcsv(joinpath(REFDIR, "hainich_individuals_2010.csv"))
fcsv = readcsv(joinpath(REFDIR, "hainich_forcing_2010.csv"))
fc_(k) = parse.(Float64, fcsv[k])
v(k, r) = parse(Float64, ind[k][r])
nt(r) = parse(Int, ind["type"][r])
const NDAY = length(fc_("doy"))

sd = Float64[]; whcs = Float64[]; rdist = Float64[]
for ln in eachline(joinpath(REFDIR, "hainich_soilcolumn.txt"))
    s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
    x = parse.(Float64, split(s)); push!(sd, x[2]); push!(whcs, x[3]); push!(rdist, x[4])
end
const SOIL = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)

prows = Dict{Int, Vector{Int}}()
for r in eachindex(ind["type"])
    (nt(r) <= 6 && v("height", r) > 0) && push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
end
const ROWS = prows[argmax(Dict(k => length(vv) for (k, vv) in prows))]

# `ds` scales the INITIAL stand density only (section (c)); `ds = 1.0` is the committed fixture verbatim.
mkp(r, ds = 1.0) = TreePools{Float64}(
    v("leaf_c", r), v("sapwood_c", r),
    max(v("agb", r) / v("nind", r) - v("leaf_c", r) - v("sapwood_c", r), 0.0), v("root_c", r),
    v("height", r), v("crownarea", r), ds * v("nind", r), v("sla", r), v("wooddens", r), false,
)
mkt(r, ds = 1.0) = Individual{Float64}(
    v("fpar_leafon", r), 0.0, v("alphaa", r), v("albedo_leaf", r), v("emax", r),
    v("sapwood_c", r), v("root_c", r), 0.0, 0.02, 0.04, 0.1, 0.4, ds * v("nind", r),
    PhotoParams{Float64}(; path = :c3, issla = true, sla = v("sla", r)),
    TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false,
)
const TAIR_K = fc_("temp") .+ 273.15
const σ = 5.670374419e-8
const YEAR_FORC = [
    AtmForcing(;
            swdown = fc_("swdown")[i], lwdown = fc_("lwnet")[i] + σ * TAIR_K[i]^4,
            tair = TAIR_K[i], qair = fc_("huss")[i], wind = 2.0, psurf = 1.0e5,
            precip = fc_("precip")[i], co2 = fc_("co2")[i]
        ) for i in 1:NDAY
]
# real per-cohort PFT ids, never the beech default (`fast.jl:147`) — M integration point #1
const PFT_IDS = [nt(r) for r in ROWS]
mkcore(ds = 1.0) =
    FDiffFastCore([mkp(r, ds) for r in ROWS], [mkt(r, ds) for r in ROWS], SOIL, 51.25; pft_ids = PFT_IDS)
mkclo(t0 = _mean(TAIR_K)) = SEBEnergyClosure(; t_soil0 = t0)
mkstate() = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))

function read_meta(path)
    d = Dict{String, Any}()
    for ln in eachline(path)
        (isempty(strip(ln)) || startswith(strip(ln), "#")) && continue
        parts = split(ln, '\t')
        (length(parts) >= 2 && parts[1] != "golden") && (d[String(parts[1])] = String(strip(parts[2])))
    end
    return d
end
nums(s) = parse.(Float64, split(strip(s)))

const DRF_ART = get(ENV, "DRF_ART", joinpath(REFDIR, "drf_forest_hainich.drf"))
const RCOP_ART = get(ENV, "RCOP_ART", joinpath(REFDIR, "recruit_copula_hainich.rcop"))
drf_meta = read_meta(replace(DRF_ART, r"\.drf$" => "_meta.txt"))
forest = DRF.load_forest(DRF_ART)
cop, af, xcop, ax_names, cond_cols_art = DRF.load_copula(RCOP_ART)
function cellinit(key, envkey)
    haskey(ENV, envkey) && return parse(Float64, ENV[envkey])
    haskey(drf_meta, key) || error("$(basename(DRF_ART))'s meta has no `$key` — pass $envkey for THIS cell")
    return parse(Float64, drf_meta[key])
end
const BOUNDARY = haskey(ENV, "BOUNDARY") ? nums(ENV["BOUNDARY"]) : nums(drf_meta["boundary"])
const N_INIT = cellinit("n_init", "N_INIT")
const AGE0 = cellinit("age0", "AGE0")
const SWEEP = parse.(Float64, split(get(ENV, "N_INIT_SWEEP", "7,9,11,13,15"), ','))

treedens(core) = sum(p.nind for p in core.pools if !p.is_grass; init = 0.0)
const DENS_SWEEP = parse.(Float64, split(get(ENV, "DENS_SWEEP", "0.5,0.75,1.0,1.5,2.0"), ','))

"""
    rollout(; n_init, years) -> NamedTuple

One free-running rollout. Records, per year, the DRF `target` (== the value assigned to `s.n_prev`) and the
realized tree DENSITY after the year, so the AR state's trajectory and the roster's can be compared. The
construction is `trait_mortality_arm_probe.jl`'s, minus the operator (this defect is upstream of it and
present with the flag off — the default production configuration).
"""
function rollout(; n_init::Float64, years::Int = YEARS, dscale::Float64 = 1.0)
    core = mkcore(dscale)
    rc = COPULA ?
        RecruitCopula{Float64}(cop, af, xcop, make_recruit_to_pools(ax_names), live_flux_cond) : nothing
    s = FluxDrivenSlowEmulator(
        core, forest; boundary = BOUNDARY, n_init = n_init, age0 = AGE0, seed = SEED,
        recruit_copula = rc, k_cap = K_CAP
    )
    clo = mkclo(); state = mkstate()
    dens = Float64[treedens(core)]                       # D[0] = the initial roster
    kroster = Int[length(core.pools)]
    for _ in 1:years
        run_coupled_cell(core, clo, state, YEAR_FORC; slow = s, days_per_year = NDAY)
        push!(dens, treedens(core))
        push!(kroster, length(core.pools))
    end
    return (; s, core, dens, kroster, target = copy(s.target_history))
end

println("="^108)
println("COUNT-RECURSION ANCHOR DIAGNOSIS — line M's ADR-0054 finding, on the S side — Hainich (42490)")
println("="^108)
println("  artifact pair : ", basename(DRF_ART), "  +  ", basename(RCOP_ART))
println("  n_init=", N_INIT, "  age0=", round(AGE0, digits = 4), "  seed=", SEED, "  years=", YEARS)
println("  copula=", COPULA, "  k_cap=", K_CAP === nothing ? "production default" : string(K_CAP))
println("  clamp bounds  : ρ ∈ [", 1 - MAX_MORT, ", ", 1 + MAX_ESTAB, "]  (max_mort/max_estab defaults)")
println("  forcing       : CONSTANT repeated 2010 (ADR-0048/0049 basis) ⇒ drift is the recursion, not the climate")

# ── (a) COHERENCE ────────────────────────────────────────────────────────────────────────────────────────
r = rollout(; n_init = N_INIT)
tgt = r.target
dens = r.dens
np_before = [i == 1 ? N_INIT : tgt[i - 1] for i in eachindex(tgt)]
raw = tgt ./ np_before
# year 1 has `s.year == 0` ⇒ the code FORCES ρ = 1 regardless of the ratio (slow.jl:1023-1024)
rho_applied = [i == 1 ? 1.0 : clamp(raw[i], 1 - MAX_MORT, 1 + MAX_ESTAB) for i in eachindex(raw)]
realized = [dens[i + 1] / dens[i] for i in eachindex(tgt)]
coherence = realized ./ rho_applied              # 1.0 ⇐ the roster did exactly what ρ asked
divergence = raw ./ rho_applied                  # >1 ⇐ the AR state claims more stand than ρ delivered
bound = [i > 1 && raw[i] != rho_applied[i] for i in eachindex(raw)]

@printf("\n=== (a) COHERENCE — does `n_prev` track the roster it is supposed to describe? ===\n")
@printf(
    "%5s %12s %12s %10s %10s %10s %11s %11s %6s\n",
    "year", "n_prev_in", "DRF target", "raw", "ρ applied", "realized", "coherence", "divergence", "K"
)
show_years = sort(unique(vcat(1:min(12, YEARS), findall(bound), YEARS)))
for i in show_years
    @printf(
        "%5d %12.4f %12.4f %10.4f %10.4f %10.4f %11.6f %11.6f %6d%s\n",
        i, np_before[i], tgt[i], raw[i], rho_applied[i], realized[i],
        coherence[i], divergence[i], r.kroster[i + 1], bound[i] ? "  <- CLAMP BINDS" : ""
    )
end

nbound = count(bound)
cumdiv = prod(divergence)
maxincoh = maximum(abs.(coherence .- 1))
@printf("\n  clamp-binding years            : %d of %d (%.1f %%)\n", nbound, YEARS, 100 * nbound / YEARS)
@printf("  max |coherence − 1|            : %.3e   (roster vs the ρ it was handed)\n", maxincoh)
@printf("  CUMULATIVE divergence Π raw/ρ  : %.6f   (AR state ÷ roster, over %d yr)\n", cumdiv, YEARS)
@printf("  final K (roster size)          : %d  (started %d)\n", r.kroster[end], r.kroster[1])
if nbound == 0
    println("\n  ⇒ DEFECT (B) IS EMPTY ON THIS CONFIGURATION. The clamp never binds, so `n_prev = target` and the")
    println("    realized roster ratio agree every year; there is no state incoherence to fix here. Whatever")
    println("    ADR 0054 measured is then defect (A) — EXPOSURE BIAS — which is a TRAINING-side problem and")
    println("    cannot be closed from `slow.jl`. Do NOT ship a runtime 're-sync' as a fix for it.")
else
    @printf(
        "\n  ⇒ DEFECT (B) IS PRESENT: the clamp bound in %d year(s) and `n_prev` took the RAW target each\n", nbound
    )
    println("    time, so the AR state and the roster are out of step by the cumulative factor above.")
end

# ── (b) ANCHORING — does the recursion have an attractor? ────────────────────────────────────────────────
@printf("\n=== (b) ANCHORING — does the recursion FORGET its initial condition? (n_init sweep) ===\n")
println("A recursion with an attractor converges to the same trajectory from any seed. One without carries")
println("the seed forever, and then a coupled run's answer is set by its initialisation, not by its climate.")
@printf(
    "\n%10s %14s %14s %14s %14s\n",
    "n_init", "target[10]", "target[end]", "treedens[end]", "K[end]"
)
sw = Dict{Float64, Any}()
for ni in SWEEP
    rr = rollout(; n_init = ni)
    sw[ni] = rr
    @printf(
        "%10.2f %14.4f %14.4f %14.6f %14d\n",
        ni, rr.target[min(10, end)], rr.target[end], rr.dens[end], rr.kroster[end]
    )
end
tend = [sw[ni].target[end] for ni in SWEEP]
dend = [sw[ni].dens[end] for ni in SWEEP]
spread(x) = (maximum(x) - minimum(x)) / _mean(x)
@printf(
    "\n  n_init range               : %.2f … %.2f  (%.0f %% of the mean)\n",
    minimum(SWEEP), maximum(SWEEP), 100 * spread(SWEEP)
)
@printf(
    "  terminal `target` spread   : %.2f … %.2f  (%.1f %% of the mean)\n",
    minimum(tend), maximum(tend), 100 * spread(tend)
)
@printf(
    "  terminal treedens spread   : %.4f … %.4f  (%.1f %% of the mean)\n",
    minimum(dend), maximum(dend), 100 * spread(dend)
)
@printf("  RETENTION (terminal spread ÷ initial spread, on `target`) : %.4f\n", spread(tend) / spread(SWEEP))
println("\n  RETENTION ≈ 0 ⇒ the recursion has an attractor and forgets `n_init` (the `slow.jl:844-846`")
println("  docstring's claim holds).  RETENTION ≈ 1 ⇒ it is a random walk in the seed: `n_init` is a free")
println("  parameter of every coupled answer, which is exactly ADR 0101 §5's 4.5×-FIT swing seen as a")
println("  structural property rather than as an artifact quirk.")

# ── (c) THE LEVEL ANCHOR — the decisive test ─────────────────────────────────────────────────────────────
# Section (b) separates two things that (a) cannot: the AR state `n_prev` and the PHYSICAL roster density
# the coupled model actually carries. `ρ` is a unit-free RATIO and the roster is advanced multiplicatively,
# `D_T = D_0 · Π ρ_t` (`slow.jl:779` documents the ratio as the mechanism that cancels the count↔density
# gap). So nothing in the loop ever states what D's ABSOLUTE level should be — the DRF's absolute count
# skill (R² 0.982) is used only through its year-on-year ratio and its level is discarded by construction.
#
# The test: scale the INITIAL stand density by a factor and hold everything else fixed. If a level anchor
# exists, the stand relaxes back and the terminal ratio → 1. If RETENTION ≈ 1, the coupled stand's level is
# set by its initialisation, permanently, and no amount of climate information will correct it. This is not
# the same claim as (b) — (b) perturbs the AR SEED, this perturbs the STATE — and it is the one that decides
# whether a multi-decadal or online run is safe.
@printf("\n=== (c) LEVEL ANCHOR — perturb the INITIAL DENSITY; does the stand relax back? ===\n")
@printf(
    "\n%10s %14s %14s %14s %14s %12s\n",
    "D0 scale", "treedens[50]", "treedens[100]", "treedens[end]", "÷ unperturbed", "K[end]"
)
dsw = Dict{Float64, Any}()
for ds in DENS_SWEEP
    dsw[ds] = rollout(; n_init = N_INIT, dscale = ds)
end
# `global` is load-bearing: a bare assignment inside a top-level `for` binds a LOCAL (Julia soft scope),
# which left `base === nothing` and killed this section with a MethodError on the first run.
base = get(dsw, 1.0, nothing)
for ds in DENS_SWEEP
    rr = dsw[ds]
    @printf(
        "%10.2f %14.6f %14.6f %14.6f %14.4f %12d\n",
        ds, rr.dens[min(51, end)], rr.dens[min(101, end)], rr.dens[end],
        base === nothing ? NaN : rr.dens[end] / base.dens[end], rr.kroster[end]
    )
end
ratio_in = maximum(DENS_SWEEP) / minimum(DENS_SWEEP)
dfin = [dsw[ds].dens[end] for ds in DENS_SWEEP]
ratio_out = maximum(dfin) / minimum(dfin)
@printf("\n  initial density ratio (max÷min) : %.4f\n", ratio_in)
@printf("  terminal density ratio (max÷min) : %.4f\n", ratio_out)
@printf(
    "  RETENTION (log-ratio out ÷ in)   : %.4f   <- 1.0 = NO level anchor, 0.0 = fully self-correcting\n",
    log(ratio_out) / log(ratio_in)
)
println("\n  Retention vs horizon — a restoring force would show as a DECAY toward 0:")
for h in sort(unique(vcat([10, 25, 50, 100, 150, 200, 250], YEARS)))
    h > YEARS && continue
    dh = [dsw[ds].dens[h + 1] for ds in DENS_SWEEP]
    @printf(
        "    retention at year %3d : %.4f   (spread %.4f×)\n", h,
        log(maximum(dh) / minimum(dh)) / log(ratio_in), maximum(dh) / minimum(dh)
    )
end
println("\n  A retention that does NOT decay with horizon is a random walk in the level: there is no restoring")
println("  force, so the error a coupled run starts with (or accumulates) is never removed. That is the")
println("  precise content of line M's \"the count recursion is unanchored\" (ADR 0054), and it explains why")
println("  teacher-forcing `n_prev` onto the C truth recovers only 59-72 % of the coupled count error rather")
println("  than all of it: teacher-forcing repairs the RATIO each year, but nothing repairs the LEVEL.")

println("\n", "="^108)
println("Hainich only (guardrail 6). Constant forcing. Artifact pair named above — it is part of the number.")
println("="^108)
