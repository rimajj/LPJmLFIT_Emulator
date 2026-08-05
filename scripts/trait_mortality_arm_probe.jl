# PHASE 3A STAGE 2 — measure the TRAIT-DEPENDENT MORTALITY arm against a matched control (ADR 0049).
#
# WHY. ADR 0046 measured FIT's per-cell wood-density warming shift as 51.3 % WITHIN-PFT / +112 %
# WITHIN-AGE-CLASS selection, and showed the emulator has exactly ZERO channel for it: the ρ-thinning
# scales every cohort's `nind` by ONE factor, which is composition-preserving to floating point. ADR 0047
# ported FIT's per-individual hazard offline; this probe measures what happens when it is wired in
# (`FluxDrivenSlowEmulator(...; trait_mortality = true)`).
#
# THE MEASUREMENT PROTOCOL IS ADR 0048's, AND IT IS NOT OPTIONAL. Both facts that make it necessary were
# measured on this exact harness:
#
#   1. The rollout's CONSTANT-FORCING community wood density drifts −3 267 = 1.34× the FIT warming shift,
#      in the OPPOSITE direction, settling at year ~52. So an arm scored against its own year-1 value can
#      show the right sign for entirely the wrong reason. ⇒ every arm is differenced against a MATCHED
#      control re-run in THIS process (never a number inherited from a log), at matched year indices, and
#      the headline is read past year 52.
#   2. The k-cap merge is trait-destructive at 3.1–5.1× the signal but fires 0 times in 150 yr at the
#      default `k_cap`. ⇒ the arm runs at the default cap and the merge count is REPORTED, so a
#      configuration that wakes it cannot be mistaken for a hazard effect.
#
# AND: BEFORE BELIEVING A NULL, CHECK THE OPERATOR FIRED (ADR 0048's own correction, handoff item F). The
# arm prints `TraitMortDiag` — the mean hazard, the tilt θ, the hard-kill count and the number of thinning
# years — and flags a zero/empty diagnostic as "this Δ bounds nothing" rather than as a verdict.
#
# WHAT IT REPORTS
#   * the ARM vs CONTROL community `wooddens`/`sla` trajectories and their difference, in gC/m³ and as a
#     share of the ADR-0046 shift (+2432.9 median / +3808.0 mean per-cell historic→ssp370);
#   * the operator's own diagnostics — θ is the number to read first: θ ≈ 1 means FIT's hazard and the
#     DRF's count target agree on how much death this year needs, θ ≫ 1 that the DRF wants far more;
#   * the AGE–WOODDENS GRADIENT the arm produces (mean `wooddens` by cohort-age bin, `nind`-weighted, on
#     the committed `S_age_wooddens_gradient.csv` edges) against FIT's own gradient for the cell's PFTs —
#     ADR 0046 §3's ID-free acceptance target. The SIGN and SHAPE are the test, not the magnitude: a
#     ~150-year single-cell rollout cannot reproduce a gradient FIT accumulated over a full spin-up, and
#     ids 0/3's gradient is NON-monotone by construction (their one-year selection differential is
#     negative), so an operator that rises everywhere is wrong;
#   * the carbon residual per arm (the ~1e-12 handoff closure must not move — guardrail 2).
#
# Usage (SLURM — the guard blocks login-node probes, CLAUDE.md §2):
#   scripts/sbatch_julia.sh S-tmort --project=. scripts/trait_mortality_arm_probe.jl
# ENV: YEARS (default 150), REPORT_AT (default "1,5,10,20,50,100,150"), COPULA (default 1 — the
#      production configuration; set 0 for the fixed-sapling arm).
# Reads only committed fixtures; writes nothing. Hainich (cell 42490) only ⇒ say "Hainich only" (guardrail 6).

using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
using LPJmLFITEmulator.DRF

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
const YEARS = parse(Int, get(ENV, "YEARS", "150"))
const REPORT_AT = parse.(Int, split(get(ENV, "REPORT_AT", "1,5,10,20,50,100,150"), ','))
const COPULA = get(ENV, "COPULA", "1") != "0"
const FIT_SHIFT = 2432.9       # ADR 0046 §1 — FIT's per-cell MEDIAN wooddens shift historic → ssp370
_mean(x) = sum(x) / length(x)

function readcsv(path)
    lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
    hdr = split(strip(lines[1]), ',')
    rows = [split(strip(l), ',') for l in lines[2:end]]
    return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
end

# ── the shared Hainich harness, byte-for-byte `kcap_merge_confound_probe.jl`'s construction ─────────────
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

# ⚠ THE ONE CONSTRUCTION DIFFERENCE FROM EVERY EARLIER PROBE, AND IT IS LOAD-BEARING. `FDiffFastCore`
# defaults `pft_ids` to `is_grass ? 8 : 3` — i.e. BEECH for every tree (`fast.jl:147`) — and line M's
# drivers do not pass it either (M integration point #1). The ported hazard's parameters are per-PFT and
# genuinely different (ids 1/2 are XERIC with `mort_water_res` 0.25, id 5's longevity is 125 not 400, the
# `wdmort` pair differs by biome), so running the arm on the default would silently evaluate FIT's
# temperate-beech hazard for the four other PFTs in this patch. `TraitMortality.pft_mort_params` errors
# rather than defaulting, but only for an id OUTSIDE 0-6 — a wrong-but-valid id 3 would pass silently.
# So the ids come from the fixture's own `type` column, here, explicitly.
const PFT_IDS = [nt(r) for r in ROWS]
mkcore() = FDiffFastCore([mkp(r) for r in ROWS], [mkt(r) for r in ROWS], SOIL, 51.25; pft_ids = PFT_IDS)
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

# ── the FIT gradient fixture (ADR 0046 §3 / ADR 0049): the acceptance target's edges + FIT's own slopes ──
const AGE_EDGES = [10.0, 20.0, 40.0, 80.0, 160.0, 320.0]
"FIT's own mean survivor `Wooddens` per (pft, agebin), from the committed fixture; `nothing` if absent."
function fit_gradient()
    path = joinpath(REFDIR, "S_age_wooddens_gradient.csv")
    isfile(path) || return nothing
    d = readcsv(path)
    out = Dict{Tuple{Int, Int}, Float64}()
    for r in eachindex(d["scenario"])
        d["scenario"][r] == "historic" || continue
        out[(parse(Int, d["pft_id"][r]), parse(Int, d["agebin"][r]))] = parse(Float64, d["wooddens_mean"][r])
    end
    return out
end

agebin(age) = sum(age >= e for e in AGE_EDGES)

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
    rollout(; trait_mortality, years) -> NamedTuple

Advance the Hainich coupled harness `years` years, ONE year per `run_coupled_cell` call (equivalent to one
long call: the driver re-derives `bc_f = stand_structure_tof(fc)` at both the start of a call and each year
end). ARM and CONTROL differ in EXACTLY the `trait_mortality` flag — same fixtures, same cohorts, same
forcing, same seed, same year count, same default `k_cap` — so the difference is the operator and nothing
else. `n_merge` is exact (the roster grows by at most one appended recruit per year).
"""
function rollout(; trait_mortality::Bool, years::Int)
    core = mkcore()
    rc = COPULA ?
        RecruitCopula{Float64}(cop, af, xcop, make_recruit_to_pools(ax_names), live_flux_cond) : nothing
    s = FluxDrivenSlowEmulator(
        core, forest; boundary = BOUNDARY, n_init = N_INIT, age0 = AGE0, seed = 1,
        recruit_copula = rc, trait_mortality = trait_mortality
    )
    clo = mkclo(); state = mkstate()
    wd = Float64[]; sla = Float64[]; ktraj = Int[]; nmerge = Int[]; ntree = Float64[]
    cum_merge = 0
    for _ in 1:years
        kprev = length(core.pools)
        run_coupled_cell(core, clo, state, YEAR_FORC; slow = s, days_per_year = NDAY)
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

println("="^108)
println("PHASE 3A STAGE 2 — trait-dependent mortality ARM vs MATCHED CONTROL — Hainich (42490), $YEARS yr")
println("="^108)
println("copula: ", COPULA ? "ON (production)" : "OFF (fixed sapling)")
println("initial roster K = ", length(ROWS), "  pft ids = ", sort(unique(PFT_IDS)))
println("initial community wooddens = ", round(community_mean([mkp(r) for r in ROWS], p -> p.wooddens), digits = 2))
println("reference scale (ADR 0046 §1): FIT per-cell wooddens shift = +2432.9 (median) / +3808.0 (mean)")
println(
    "\nBOTH arms are run HERE, in this process, at matched year indices (ADR 0048): the constant-forcing\n" *
        "control drifts 1.34× the FIT shift on its own, so only the DIFFERENCE is interpretable, and only\n" *
        "past its ~52-yr relaxation."
)

ctl = rollout(; trait_mortality = false, years = YEARS)
arm = rollout(; trait_mortality = true, years = YEARS)

# ── 0. DID THE OPERATOR FIRE? (ADR 0048's own correction — check before reading any Δ) ─────────────────
println("\n", "-"^108)
println("0. DID THE OPERATOR FIRE?  (a Δ from an operator that never ran bounds NOTHING)")
println("-"^108)
dg = trait_mortality_diag(arm.s)
println("  control diagnostics recorded: ", length(trait_mortality_diag(ctl.s)), " (MUST be 0 — the flag is off)")
println("  arm diagnostics recorded:     ", length(dg), " of $YEARS yr")
const FIRED = !isempty(dg) && any(d -> d.thinned, dg)
if isempty(dg)
    println("  ⚠ THE OPERATOR NEVER RAN — every Δ below is a NON-MEASUREMENT.")
else
    nthin = count(d -> d.thinned, dg)
    θs = [d.theta for d in dg if d.thinned && isfinite(d.theta)]
    hk = sum(d.hard_kills for d in dg)
    sf = [d.shortfall for d in dg if d.shortfall > 0]
    println("  thinning years (ρ < 1):       ", nthin, " of ", length(dg), "  ⇒ the operator reshaped ", nthin, " yr")
    println(
        "  mean FIT hazard over trees:   ", round(_mean([d.hazard_mean for d in dg]), sigdigits = 5),
        "   (min ", round(minimum(d.hazard_mean for d in dg), sigdigits = 4),
        ", max ", round(maximum(d.hazard_mean for d in dg), sigdigits = 4), ")"
    )
    if !isempty(θs)
        q(v, p) = sort(v)[clamp(1 + round(Int, p * (length(v) - 1)), 1, length(v))]
        println(
            "  tilt θ:  mean ", round(_mean(θs), sigdigits = 5), "  q10 ", round(q(θs, 0.1), sigdigits = 4),
            "  MEDIAN ", round(q(θs, 0.5), sigdigits = 4), "  q90 ", round(q(θs, 0.9), sigdigits = 4),
            "  max ", round(maximum(θs), sigdigits = 4)
        )
        println(
            "     θ ≈ 1 ⇒ FIT's hazard and the DRF's count target agree; θ > 1 ⇒ the DRF wants MORE death\n" *
                "     than FIT's hazard produces at this cell; θ ≈ 0 ⇒ the DRF wants essentially NONE, so the\n" *
                "     operator has almost nothing to redistribute that year (the duty-cycle question below)."
        )
        println(
            "  years with θ > 0.5 (the operator selects at ≥ half FIT's rate): ", count(>(0.5), θs),
            " of ", length(θs), " thinning yr = ", round(100 * count(>(0.5), θs) / length(θs), digits = 1), " %"
        )
        # ── THE DUTY-CYCLE / GROSS-vs-NET DIAGNOSTIC. This is the number that explains θ's shape, and it
        #    is a property of the EMULATOR's demography, not of the ported hazard. FIT kills 2.8–6.2 % of
        #    stems per year and replaces them by establishment at a similar rate — a stationary count with
        #    LARGE GROSS turnover. The emulator's ρ expresses only the NET change, and mortality and
        #    establishment are mutually exclusive branches within a year, so its gross turnover IS |ρ−1|.
        #    Selection intensity scales with GROSS deaths, so if |ρ−1| ≪ the FIT hazard the operator is
        #    throttled by the count channel however faithful the hazard is. ──
        th = arm.s.target_history
        rel = [abs(th[t] / th[t - 1] - 1) for t in 2:length(th)]
        println(
            "\n  GROSS vs NET TURNOVER (why θ looks like that — a property of the emulator, not the hazard):\n" *
                "    FIT's ported hazard on this patch: mean ",
            round(100 * _mean([d.hazard_mean for d in dg]), digits = 3), " % of stems/yr\n" *
                "    the DRF's demanded |ρ−1|:           mean ", round(100 * _mean(rel), digits = 4),
            " %/yr  (median ", round(100 * q(rel, 0.5), digits = 4), " %/yr)\n" *
                "    ratio hazard : |ρ−1| = ",
            round(_mean([d.hazard_mean for d in dg]) / max(_mean(rel), 1.0e-30), digits = 1),
            "×  ⇒ the count channel, not the hazard, bounds the selection this operator can express.\n" *
                "    FIT's own dead_frac is 2.8–6.2 %/yr (ADR 0046 §3) with a near-stationary count, i.e. its\n" *
                "    deaths and recruits CO-OCCUR every year. The emulator's ρ<1 XOR ρ>1 branches cannot.\n" *
                "    This does not invalidate the arm below — it bounds it, and it names the next lever."
        )
    end
    println("  hard kills (cumulative):      ", hk)
    println(
        "  years the hazard OVERRODE the DRF count (shortfall > 0): ", length(sf),
        isempty(sf) ? "  ⇒ the count target was honoured every year" :
            "  ⚠ max rel. shortfall " * string(round(maximum(sf), sigdigits = 3))
    )
    println(
        "  cumulative k-cap merges — arm ", arm.nmerge[end], " / control ", ctl.nmerge[end],
        arm.nmerge[end] + ctl.nmerge[end] == 0 ?
            "  (dormant, as ADR 0048 measured ⇒ the merge confound is absent)" :
            "  ⚠ THE MERGE FIRED — ADR 0048 measures it at 3.1–5.1× the signal; re-run kcap_merge_confound_probe.jl"
    )
end

# ── 1. the controlled response ──────────────────────────────────────────────────────────────────────────
println("\n", "-"^108)
println("1. COMMUNITY WOOD DENSITY — arm vs matched constant-forcing control")
println("-"^108)
println(
    "  ", rpad("yr", 5), rpad("K_arm", 7), rpad("K_ctl", 7), rpad("wd_arm", 12), rpad("wd_ctl", 12),
    rpad("Δwd", 11), rpad("|Δ|/2432.9", 12), rpad("Δsla", 12), "Σnind arm/ctl"
)
for y in REPORT_AT
    y <= YEARS || continue
    d = arm.wd[y] - ctl.wd[y]
    println(
        "  ", rpad(y, 5), rpad(arm.ktraj[y], 7), rpad(ctl.ktraj[y], 7),
        rpad(round(arm.wd[y], digits = 2), 12), rpad(round(ctl.wd[y], digits = 2), 12),
        rpad(round(d, digits = 2), 11), rpad(round(abs(d) / FIT_SHIFT, digits = 4), 12),
        rpad(round(arm.sla[y] - ctl.sla[y], sigdigits = 4), 12),
        round(arm.ntree[y] / ctl.ntree[y], sigdigits = 8)
    )
end
const DMAX = argmax(abs.(arm.wd .- ctl.wd))
println(
    "\n  worst |Δwd| = ", round(abs(arm.wd[DMAX] - ctl.wd[DMAX]), digits = 3), " at yr ", DMAX,
    " (= ", round(abs(arm.wd[DMAX] - ctl.wd[DMAX]) / FIT_SHIFT * 100, digits = 2), " % of the FIT shift)"
)
const YSCORE = min(YEARS, max(52, YEARS))       # score PAST the ~52-yr relaxation (ADR 0048)
println(
    "  SCORED at yr ", YSCORE, " (past the control's ~52-yr relaxation): Δwd = ",
    round(arm.wd[YSCORE] - ctl.wd[YSCORE], digits = 2), " = ",
    round((arm.wd[YSCORE] - ctl.wd[YSCORE]) / FIT_SHIFT, digits = 4), "× the FIT shift"
)
println(
    "  Σnind (tree) at yr $YEARS: arm ", round(arm.ntree[end], sigdigits = 10), " vs control ",
    round(ctl.ntree[end], sigdigits = 10), " (rel ",
    round((arm.ntree[end] - ctl.ntree[end]) / ctl.ntree[end], sigdigits = 3), ")"
)
println(
    "     ⚠ this is NOT a count-target violation: the DRF target is hit EXACTLY every year (θ solves for\n" *
        "     it), but the reshaped roster changes the stand aggregates the DRF conditions on (lai / fpc /\n" *
        "     age_mean / n_living), so the TRAJECTORY of targets diverges from year 2 — the same feedback\n" *
        "     ADR 0048 §2 documents for the merge. A per-year identity check is in the testitem."
)
println(
    "\n  carbon residual (guardrail 2, must not move): arm max|resid| = ",
    maximum(abs, arm.s.resid_history), "  control ", maximum(abs, ctl.s.resid_history)
)

# ── 2. the ACCEPTANCE TARGET — the age–wooddens gradient ────────────────────────────────────────────────
println("\n", "-"^108)
println("2. THE ACCEPTANCE TARGET (ADR 0046 §3) — age–wooddens gradient the ARM produces")
println("-"^108)
"Per-agebin nind-weighted mean wooddens of a roster; `ages` are the emulator's per-cohort ages."
function gradient_of(core, s)
    num = Dict{Int, Float64}(); den = Dict{Int, Float64}()
    for i in eachindex(core.pools)
        p = core.pools[i]
        (p.is_grass || p.nind <= 0) && continue
        b = agebin(s.age[i])
        num[b] = get(num, b, 0.0) + p.nind * p.wooddens
        den[b] = get(den, b, 0.0) + p.nind
    end
    return Dict(b => num[b] / den[b] for b in keys(num)), den
end
garm, narm = gradient_of(arm.core, arm.s)
gctl, nctl = gradient_of(ctl.core, ctl.s)
fitg = fit_gradient()
println("  cohort ages after $YEARS yr span bins ", sort(collect(keys(garm))), " (edges $AGE_EDGES)")
println(
    "  ", rpad("bin", 5), rpad("age range", 14), rpad("wd_arm", 12), rpad("wd_ctl", 12), rpad("Δ", 11),
    rpad("Σnind_arm", 12), "FIT (per-PFT, this cell's ids)"
)
for b in sort(collect(union(keys(garm), keys(gctl))))
    lo = b == 0 ? 0.0 : AGE_EDGES[b]
    hi = b < length(AGE_EDGES) ? AGE_EDGES[b + 1] : Inf
    fitcol = if fitg === nothing
        "fixture absent — build it first"
    else
        vals = [(id, get(fitg, (id, b), NaN)) for id in sort(unique(PFT_IDS))]
        join(["$(id):$(isnan(x) ? "-" : string(round(Int, x)))" for (id, x) in vals], " ")
    end
    println(
        "  ", rpad(b, 5), rpad("[$lo, $hi)", 14),
        rpad(haskey(garm, b) ? round(garm[b], digits = 1) : "-", 12),
        rpad(haskey(gctl, b) ? round(gctl[b], digits = 1) : "-", 12),
        rpad(haskey(garm, b) && haskey(gctl, b) ? round(garm[b] - gctl[b], digits = 2) : "-", 11),
        rpad(round(get(narm, b, 0.0), sigdigits = 4), 12), fitcol
    )
end
println(
    "\n  HOW TO READ THIS. The control's gradient is the emulator's PRE-0049 baseline: it is not flat\n" *
        "  (recruits enter with copula-drawn traits, so bins differ), but it carries NO age–trait\n" *
        "  covariance from selection — that is the ADR 0046 §4 claim. The arm's Δ across bins is the\n" *
        "  operator's contribution. FIT's own column is the target's SHAPE, per PFT; a single 150-yr cell\n" *
        "  rollout cannot reproduce its MAGNITUDE (FIT accumulated it over a full spin-up on a 25-patch\n" *
        "  ensemble), and ids 0/3 are non-monotone by construction. Judge sign and monotonicity."
)

println("\n", "="^108)
println("VERDICT")
println("="^108)
if !FIRED
    println("  NON-MEASUREMENT — the operator did not thin in any year. Fix that before reading anything above.")
else
    d = arm.wd[YSCORE] - ctl.wd[YSCORE]
    println(
        "  controlled Δ(community wooddens) at yr ", YSCORE, " = ", round(d, digits = 2), " gC/m³ = ",
        round(d / FIT_SHIFT, digits = 4), "× the FIT warming shift (same sign as FIT: ", d > 0, ")"
    )
    println(
        "  This is a MECHANISM check on ONE cell (Hainich, guardrail 6), NOT the ADR-0044 response gate.\n" *
            "  The P1 threshold is ΔRr ≥ +0.036 on the global gate and is measured elsewhere; nothing here\n" *
            "  may be quoted as 'reducing the damping' (ADR 0044 — the residual is PLACEMENT, not shrinkage)."
    )
end
println("="^108)
