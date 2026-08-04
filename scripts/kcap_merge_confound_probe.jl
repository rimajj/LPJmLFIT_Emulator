# Measure the K-CAP MERGE TRAIT CONFOUND, and the emulator's establishment relaxation timescale — the
# zero-new-physics pre-flight ADR 0046 §4 requires BEFORE any trait-dependent-mortality operator is wired
# into `slow.jl` (line S handoff item D).
#
# WHY. ADR 0046 established that FIT's wood-density warming shift is 51.3 % WITHIN-PFT selection, and that
# the emulator has exactly zero channel for it: the ρ-thinning at `slow.jl:763-773` scales every cohort's
# `nind` by ONE factor, which is composition-preserving to floating point. Two operators DO move the
# community trait mean, and both sit directly in the path of the planned fix:
#
#   1. `_merge_pair!` (`slow.jl:441-445`) conserves carbon by `nind` weight but inherits the DOMINANT
#      parent's `sla`/`wooddens` outright. It is therefore trait-NON-conservative: a k-cap merge can move
#      the community wood-density mean with no mortality, no establishment and no physics. If that motion
#      is comparable to the +2432.9 (median) / +3808.0 (mean) shift a ported hazard must explain, then any
#      before/after measurement of the hazard is confounded by the roster bound, and the merge must be
#      fixed FIRST, separately, with its own ADR.
#   2. Appended copula recruits carry no age–trait covariance (that is the gap the hazard closes).
#
# WHAT IT MEASURES. Rollouts of the committed Hainich harness — {copula OFF, copula ON} × {k_cap =
# default (= max(2K, 40)), k_cap = TIGHT, k_cap = typemax(Int) = merge DISABLED} — advanced ONE year at a
# time so the community state is read at every year boundary. Everything else is byte-identical between
# arms (fixtures, cohort selection, forcing, seed, year count), so the ONLY difference is whether the merge
# ran. Reports per arm-pair: the `nind`-weighted community `wooddens` (and `sla`) trajectory, the roster
# length, the cumulative merge count, and Δ(community wooddens) vs the merge-disabled arm — in gC/m³ and as
# a fraction of the ADR-0046 shift the fix has to explain.
#
# ⚠ THE DEFAULT ARM ALONE CANNOT ANSWER THE QUESTION, which is why the TIGHT arm exists. `k_cap` defaults
# to `max(2·K_initial, 40)`, and the roster grows by at most ONE cohort per establishment year, so at
# Hainich (K = 17) the merge cannot fire before ~year 23 of *sustained* establishment — and establishment
# fires in only ~12 of 150 years. A default-vs-disabled Δ of exactly 0 therefore measures NOTHING about
# the operator; it only says the operator never ran. `K_CAP_TIGHT` (default 20, just above the initial
# roster) forces it to run, so the reported Δ is a real bound on the trait distortion per merge — the
# number a denser global cell, or a future tighter cap, would inherit.
#
# It also reports the community trait DRIFT under CONSTANT forcing (the same year repeated). That drift is
# a pure artifact of the emulator's own recruit channel — no climate signal is present — so anything
# comparable to the +2432.9 FIT warming shift is a spurious baseline motion any before/after response
# measurement has to subtract.
#
# It also reports the ESTABLISHMENT RELAXATION TIMESCALE from `s.target_history`: the emulator's own
# per-year recruit fraction e = max(ρ−1, 0) (establishment only fires when ρ > 1 — `slow.jl:763-790`), and
# τ = −1/ln(1−e), the analytic bound on how fast a trait perturbation is diluted out of the roster by
# recruitment alone. τ bounds the SECOND damping in the rollout (relaxation), distinct from the placement
# error ADR 0044 §2 measured.
#
# Usage (SLURM — the guard blocks login-node probes, CLAUDE.md §2):
#   scripts/sbatch_julia.sh S-kcap --project=. scripts/kcap_merge_confound_probe.jl
# ENV: YEARS (default 150), REPORT_AT (comma-separated years to tabulate, default "1,5,10,20,50,100,150"),
#      K_CAP_TIGHT (default 20 — the cap that forces the merge to fire; must exceed the live grass cohorts).
# Reads only committed fixtures; writes nothing. Hainich (cell 42490) only.

using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
using LPJmLFITEmulator.DRF

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
const YEARS = parse(Int, get(ENV, "YEARS", "150"))
const REPORT_AT = parse.(Int, split(get(ENV, "REPORT_AT", "1,5,10,20,50,100,150"), ','))
const K_CAP_TIGHT = parse(Int, get(ENV, "K_CAP_TIGHT", "20"))
_mean(x) = sum(x) / length(x)

function readcsv(path)
    lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
    hdr = split(strip(lines[1]), ',')
    rows = [split(strip(l), ',') for l in lines[2:end]]
    return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
end

# ── the shared Hainich harness, byte-for-byte `measure_hainich_gate_bands_probe.jl`'s construction ──────
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

mkp(r) = TreePools{Float64}(
    v("leaf_c", r), v("sapwood_c", r),
    max(v("agb", r) / v("nind", r) - v("leaf_c", r) - v("sapwood_c", r), 0.0), v("root_c", r),
    v("height", r), v("crownarea", r), v("nind", r), v("sla", r), v("wooddens", r), false,
)
mkt(r) = Individual{Float64}(
    v("fpar_leafon", r), 0.0, v("alphaa", r), v("albedo_leaf", r), v("emax", r),
    v("sapwood_c", r), v("root_c", r), 0.0, 0.02, 0.04, 0.1, 0.4, v("nind", r),
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
mkcore() = FDiffFastCore([mkp(r) for r in ROWS], [mkt(r) for r in ROWS], SOIL, 51.25)
mkclo() = SEBEnergyClosure(; t_soil0 = _mean(TAIR_K))
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

drf_meta = read_meta(joinpath(REFDIR, "drf_forest_hainich_meta.txt"))
forest = DRF.load_forest(joinpath(REFDIR, "drf_forest_hainich.drf"))
cop, af, xcop, ax_names, _cond_cols = DRF.load_copula(joinpath(REFDIR, "recruit_copula_hainich.rcop"))
const BOUNDARY = nums(drf_meta["boundary"])
const N_INIT = parse(Float64, drf_meta["n_init"])
const AGE0 = parse(Float64, drf_meta["age0"])

# ── the community statistics the merge can move ─────────────────────────────────────────────────────────
"`nind`-weighted community mean of `getter` over the LIVE TREE cohorts (grass carries zeroed traits)."
function community_mean(pools, getter)
    num = 0.0; den = 0.0
    for p in pools
        (p.is_grass || p.nind <= 0) && continue
        num += p.nind * getter(p); den += p.nind
    end
    return den > 0 ? num / den : NaN
end

"""
    rollout(; copula, k_cap, years) -> NamedTuple

Advance the Hainich coupled harness `years` years ONE year per `run_coupled_cell` call (equivalent to one
long call: the driver re-derives `bc_f = stand_structure_tof(fc)` at both the start of a call and each
year end), recording the community trait means, roster length and cumulative merge count every year.
`n_merge` is exact: the roster grows by at most one appended recruit cohort per year, so
`merges_this_year = K_prev + appended − K_now`, and `appended` is recoverable from ρ > 1.
"""
function rollout(; copula::Bool, k_cap::Union{Nothing, Int}, years::Int)
    core = mkcore()
    rc = copula ?
        RecruitCopula{Float64}(cop, af, xcop, make_recruit_to_pools(ax_names), live_flux_cond) : nothing
    s = FluxDrivenSlowEmulator(
        core, forest; boundary = BOUNDARY, n_init = N_INIT, age0 = AGE0, seed = 1,
        recruit_copula = rc, k_cap = k_cap
    )
    clo = mkclo(); state = mkstate()
    wd = Float64[]; sla = Float64[]; ktraj = Int[]; nmerge = Int[]; ntree = Float64[]
    cum_merge = 0
    for _ in 1:years
        kprev = length(core.pools)
        run_coupled_cell(core, clo, state, YEAR_FORC; slow = s, days_per_year = NDAY)
        # appended recruits: establishment fires only when ρ > 1, and appends exactly ONE cohort
        appended = length(s.target_history) >= 2 &&
            s.target_history[end] > s.target_history[end - 1] ? 1 : 0
        cum_merge += max(kprev + appended - length(core.pools), 0)
        push!(wd, community_mean(core.pools, p -> p.wooddens))
        push!(sla, community_mean(core.pools, p -> p.sla))
        push!(ktraj, length(core.pools)); push!(nmerge, cum_merge)
        push!(ntree, sum(p.nind for p in core.pools if !p.is_grass; init = 0.0))
    end
    return (; s, core, wd, sla, ktraj, nmerge, ntree)
end

println("="^104)
println("K-CAP MERGE TRAIT CONFOUND — Hainich (cell 42490), $YEARS yr, committed demo artifacts")
println("="^104)
println("initial roster K = ", length(ROWS), "  ⇒ default k_cap = max(2K, 40) = ", max(2 * length(ROWS), 40))
println("initial community wooddens = ", round(community_mean([mkp(r) for r in ROWS], p -> p.wooddens), digits = 2))
println("reference scale (ADR 0046 §1): FIT per-cell wooddens shift historic→ssp370 = +2432.9 (median) / +3808.0 (mean)")

const ARMS = (
    (label = "copula OFF", copula = false),
    (label = "copula ON ", copula = true),
)

const FIT_SHIFT = 2432.9    # ADR 0046 §1: FIT's per-cell MEDIAN wooddens shift historic → ssp370
const SHARES = Dict{String, Float64}()   # arm label => worst |Δwd| / FIT_SHIFT over the run
const DRIFTS = Dict{String, Float64}()   # arm label => constant-forcing drift of community wooddens

for arm in ARMS
    println("\n", "-"^104)
    println("[$(arm.label)]  merge variants vs the merge-DISABLED reference (k_cap = typemax(Int))")
    println("-"^104)
    ref = rollout(; copula = arm.copula, k_cap = typemax(Int), years = YEARS)
    variants = (
        ("default k_cap=$(max(2 * length(ROWS), 40))", nothing),
        ("TIGHT   k_cap=$K_CAP_TIGHT", K_CAP_TIGHT),
    )
    for (vlabel, kc) in variants
        run = rollout(; copula = arm.copula, k_cap = kc, years = YEARS)
        key = "$(strip(arm.label)) / $(strip(vlabel))"
        println("\n  ", vlabel)
        println(
            "  ", rpad("yr", 5), rpad("K", 5), rpad("K_ref", 7), rpad("merges", 8),
            rpad("wd", 12), rpad("wd_ref", 12), rpad("Δwd", 11), rpad("|Δ|/2432.9", 12), "Δsla"
        )
        for y in REPORT_AT
            y <= YEARS || continue
            d = run.wd[y] - ref.wd[y]
            println(
                "  ", rpad(y, 5), rpad(run.ktraj[y], 5), rpad(ref.ktraj[y], 7), rpad(run.nmerge[y], 8),
                rpad(round(run.wd[y], digits = 2), 12), rpad(round(ref.wd[y], digits = 2), 12),
                rpad(round(d, digits = 2), 11), rpad(round(abs(d) / FIT_SHIFT, digits = 4), 12),
                round(run.sla[y] - ref.sla[y], sigdigits = 4)
            )
        end
        dmax = argmax(abs.(run.wd .- ref.wd))
        worst = abs(run.wd[dmax] - ref.wd[dmax])
        SHARES[key] = worst / FIT_SHIFT
        println(
            "  worst |Δwd| = ", round(worst, digits = 3), " at yr ", dmax,
            "  (= ", round(worst / FIT_SHIFT * 100, digits = 3), " % of the FIT median shift)",
            run.nmerge[end] == 0 ? "   ⚠ NO MERGE EVER FIRED — this Δ bounds nothing" : ""
        )
        println("  total merges over $YEARS yr: ", run.nmerge[end])
        # ⚠ Σnind is NOT expected to match the reference arm. `_merge_pair!` conserves Σnind WITHIN the
        # call (gated by slow_membership_tests.jl), but the merged roster changes the stand aggregates the
        # DRF is conditioned on (lai/fpc/age_mean/n_living), so the COUNT TARGET diverges from the next
        # year onward. Any difference below is that feedback, not a conservation violation — and it is
        # itself worth reading, because it says the roster bound perturbs the demography, not just the
        # trait bookkeeping.
        println(
            "  Σnind (tree) at yr $YEARS: ", round(run.ntree[end], sigdigits = 10), " vs ref ",
            round(ref.ntree[end], sigdigits = 10), "  (rel ",
            round((run.ntree[end] - ref.ntree[end]) / ref.ntree[end], sigdigits = 3),
            ") — trajectory feedback through the DRF features, NOT non-conservation"
        )
        fm = findfirst(>(0), run.nmerge)
        fm === nothing || println(
            "  first merge at yr ", fm, ";  Δwd there = ", round(run.wd[fm] - ref.wd[fm], digits = 3)
        )
        println("  max|carbon resid|: ", maximum(abs, run.s.resid_history), " (ref ", maximum(abs, ref.s.resid_history), ")")
    end

    # ── the CONSTANT-FORCING baseline drift, and the recruitment relaxation timescale ──
    drift = ref.wd[end] - ref.wd[1]
    DRIFTS[strip(arm.label)] = drift
    println(
        "\n  CONSTANT-FORCING drift of community wooddens (merge-disabled ref, yr 1 → $YEARS): ",
        round(drift, digits = 2), "  = ", round(abs(drift) / FIT_SHIFT, digits = 3),
        "× the FIT warming shift, with NO climate signal present"
    )
    # how long the relaxation takes: the first year the trajectory is within 1 gC/m³ of its final value
    settle = findfirst(y -> abs(ref.wd[y] - ref.wd[end]) < 1.0, eachindex(ref.wd))
    println(
        "  the drift SETTLES at yr ", settle === nothing ? ">$YEARS" : settle,
        " (first year within 1 gC/m³ of the final value) — compare against the 80-yr historic→ssp370 window"
    )
    th = ref.s.target_history
    es = Float64[]
    for t in 2:length(th)
        ρ = th[t] / th[t - 1]
        ρ > 1 && push!(es, ρ - 1)
    end
    if isempty(es)
        println("  establishment NEVER fired (ρ ≤ 1 every year) ⇒ no recruitment channel, τ = Inf")
    else
        ebar = _mean(es)
        println(
            "  establishment fired in ", length(es), " of ", length(th) - 1, " yr;  mean e (firing yr) = ",
            round(ebar, sigdigits = 4), "  (max ", round(maximum(es), sigdigits = 4),
            ");  run-mean e = ", round(sum(es) / (length(th) - 1), sigdigits = 4)
        )
        eall = sum(es) / (length(th) - 1)
        println(
            "  ⇒ τ = −1/ln(1−e) = ", round(-1 / log(1 - ebar), digits = 2), " yr (firing-year e) / ",
            round(-1 / log(1 - eall), digits = 2),
            " yr (run-mean e)   — the recruitment-dilution bound on the rollout's relaxation damping"
        )
    end
end

println("\n", "="^104)
println("VERDICT")
println("="^104)
for k in sort(collect(keys(SHARES)))
    println("  ", rpad(k, 44), "worst |Δwd| = ", round(SHARES[k] * 100, digits = 3), " % of the FIT shift")
end
println("  < ~5 %  ⇒ the merge is NOT a material confound; measure the hazard against the default arm.")
println("  ≥ ~5 %  ⇒ FIX `_merge_pair!`'s dominant-parent trait inheritance FIRST, separately, own ADR.")
println("  A row whose merge count is 0 is a NON-MEASUREMENT — read the TIGHT row for the real bound.")
println("\n  Constant-forcing baseline drift (no climate signal), as a multiple of the FIT warming shift:")
for k in sort(collect(keys(DRIFTS)))
    println(
        "  ", rpad(k, 44), round(DRIFTS[k], digits = 2), "  = ",
        round(abs(DRIFTS[k]) / FIT_SHIFT, digits = 3), "×"
    )
end
println("="^104)
