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
# MODE=response — PHASE 3A STAGE 3, THE RESPONSE ARM (ADR 0100). Everything above measures a LEVEL change
# under CONSTANT forcing. FIT's +2432.9 is a BETWEEN-SCENARIO difference, so the Phase-3A question needs a
# 2x2 — {trait_mortality on, off} x {historic forcing, ssp370 forcing} — with all four rollouts advanced in
# THIS process at matched year indices, and the DOUBLE difference read as the operator's contribution to the
# warming response:
#
#     R_ctl = wd(ctl, ssp370) - wd(ctl, historic)     the pre-0049 emulator's own warming response
#     R_arm = wd(arm, ssp370) - wd(arm, historic)     with the hazard wired in
#     interaction = R_arm - R_ctl = Δ_ssp - Δ_hist    <- the number Phase 3A exists to produce
#
# The forcing is REAL: both scenarios come from the same .clm sources the two LPJmL-FIT ground-truth runs
# used (`scripts/build_hainich_response_forcing.py`, gated against `hainich_forcing_2010.csv` and
# `climbuf_hainich_boundary_w20.csv`), so the contrast is the analogue of FIT's — INCLUDING its confounds:
# the scenarios are different data sources (reanalysis vs MPI-ESM1-2-HR) and their mean CO2 differs by
# ~66 ppm. Both are printed here and must be quoted with any response number.
#
# Usage (SLURM — the guard blocks login-node probes, CLAUDE.md §2):
#   scripts/sbatch_julia.sh S-tmort --project=. scripts/trait_mortality_arm_probe.jl
#   MODE=response scripts/sbatch_julia.sh S-tmresp --project=. scripts/trait_mortality_arm_probe.jl
# ENV: MODE (stage2 | response; default stage2 ⇒ byte-identical to the ADR-0049 measurement),
#      YEARS (default 150 in stage2; in response mode it is CLAMPED to the fixture's year count),
#      REPORT_AT (default "1,5,10,20,50,100,150"), COPULA (default 1 — the production configuration; set 0
#      for the fixed-sapling arm), FORCING_DIR (response mode; default
#      /p/tmp/jamirp/emulator_global/S_response_forcing — build it with build_hainich_response_forcing.py).
# stage2 reads only committed fixtures and writes nothing; response mode additionally reads the (uncommitted,
# 1.7 MB/scenario) daily forcing from FORCING_DIR — its per-year means are committed in
# `S_hainich_response_boundary.csv` so a later session can verify a rebuild without shipping the daily file.
# Hainich (cell 42490) only ⇒ say "Hainich only" (guardrail 6).

using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
using LPJmLFITEmulator.DRF

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
const MODE = get(ENV, "MODE", "stage2")
const REPORT_AT = parse.(
    Int,
    split(get(ENV, "REPORT_AT", MODE == "response" ? "1,5,10,20,40,60,81" : "1,5,10,20,50,100,150"), ',')
)
const COPULA = get(ENV, "COPULA", "1") != "0"
const FIT_SHIFT = 2432.9       # ADR 0046 §1 — FIT's per-cell MEDIAN wooddens shift historic → ssp370
const FORCING_DIR = get(ENV, "FORCING_DIR", "/p/tmp/jamirp/emulator_global/S_response_forcing")
# `K_CAP` — the roster cap. UNSET means the production default (`max(2K, 40)` = 40 here), which ADR 0048
# measured as DORMANT over 150 constant-forcing years but which the response arm's real forcing WAKES (it
# appends more recruits): the first ADR-0100 run merged 8-9 times per arm. The merge is trait-destructive at
# 3.1-5.1x the signal (ADR 0048), so the primary response run raises the cap until the merge count is 0 and
# the default-cap run becomes the sensitivity check. The merge count is printed for every arm either way.
const K_CAP = haskey(ENV, "K_CAP") ? parse(Int, ENV["K_CAP"]) : nothing
# `SCORE_WINDOW` — headline = the mean over the LAST this-many years, not the terminal year. With real
# interannual forcing a single-year read swings by more than the signal (measured: the interaction moves
# -1070 -> +3132 -> +239 -> +2492 across report years), and FIT's own +2432.9 is a run MEAN, not a snapshot.
const SCORE_WINDOW = parse(Int, get(ENV, "SCORE_WINDOW", "20"))
MODE in ("stage2", "response") || error("MODE must be stage2 or response (got $MODE)")
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
mkclo(t0 = _mean(TAIR_K)) = SEBEnergyClosure(; t_soil0 = t0)
mkstate() = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))

# ── MODE=response: the two REAL scenario forcings + their ADR-0026 transient boundaries ─────────────────
"""
    load_scenario(scen) -> Vector{Vector{AtmForcing}}

Per-year day vectors for `scen` ∈ {"historic", "ssp370"} from `FORCING_DIR/<scen>_42490_daily.csv`
(`scripts/build_hainich_response_forcing.py`, itself gated against the committed 2010 forcing fixture). Years
are returned in file order; every year must carry exactly `NDAY` days so the two scenarios are differenced at
matched year indices.
"""
function load_scenario(scen)
    path = joinpath(FORCING_DIR, "$(scen)_42490_daily.csv")
    isfile(path) || error(
        "MODE=response needs $path — build it first:\n" *
            "    python3 scripts/build_hainich_response_forcing.py\n" *
            "(the daily forcing is deliberately NOT committed; its per-year means are, in " *
            "S_hainich_response_boundary.csv)"
    )
    d = readcsv(path)
    yrs = parse.(Int, d["year"])
    out = Vector{Vector{AtmForcing{Float64}}}()
    for Y in unique(yrs)
        idx = findall(==(Y), yrs)
        length(idx) == NDAY || error("$path year $Y has $(length(idx)) days, expected $NDAY")
        tk = [parse(Float64, d["temp"][i]) + 273.15 for i in idx]
        push!(
            out, [
                AtmForcing(;
                        swdown = parse(Float64, d["swdown"][idx[j]]),
                        lwdown = parse(Float64, d["lwnet"][idx[j]]) + σ * tk[j]^4,
                        tair = tk[j], qair = parse(Float64, d["huss"][idx[j]]), wind = 2.0, psurf = 1.0e5,
                        precip = parse(Float64, d["precip"][idx[j]]), co2 = parse(Float64, d["co2"][idx[j]])
                    ) for j in eachindex(idx)
            ]
        )
    end
    return out
end

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

# ── the response arm's per-scenario TRANSIENT boundary (ADR 0026) ────────────────────────────────────────
# Only the two TIME-VARYING axes move (`gdd5`, `tas_cold_month`); `soil_depth` and the boundary tail's `co2`
# stay at the artifact's own values, because the artifact was TRAINED on those (ADR 0004 pins the co2 tail at
# 369 — it is a conditioning feature, NOT the forcing co2 the daily file carries, which does vary).
"Per-year `boundary_series` rows for `scen`, from the committed `S_hainich_response_boundary.csv`."
function scenario_boundary(scen)
    d = readcsv(joinpath(REFDIR, "S_hainich_response_boundary.csv"))
    rows = [i for i in eachindex(d["scenario"]) if d["scenario"][i] == scen]
    isempty(rows) && error("S_hainich_response_boundary.csv has no scenario=$scen rows")
    return [
        vcat(
                [parse(Float64, d["gdd5"][i]), parse(Float64, d["tas_cold_month"][i])],
                BOUNDARY[3:end]
            ) for i in rows
    ]
end

const RESP_SCEN = ("historic", "ssp370")
const RESP_FORC = MODE == "response" ? Dict(s => load_scenario(s) for s in RESP_SCEN) : nothing
const RESP_BND = MODE == "response" ? Dict(s => scenario_boundary(s) for s in RESP_SCEN) : nothing
"Year count: in response mode the fixture's own (both scenarios must match), clamped by `YEARS` if set."
function resolve_years()
    MODE == "response" || return parse(Int, get(ENV, "YEARS", "150"))
    for s in RESP_SCEN
        length(RESP_BND[s]) == length(RESP_FORC[s]) || error(
            "$s: boundary has $(length(RESP_BND[s])) yr but forcing has $(length(RESP_FORC[s])) yr"
        )
    end
    ny = minimum(length(RESP_FORC[s]) for s in RESP_SCEN)
    return min(parse(Int, get(ENV, "YEARS", string(ny))), ny)
end
const YEARS = resolve_years()

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
    rollout(; trait_mortality, years, forcing = nothing, boundary_series = nothing, t_soil0 = _mean(TAIR_K))
        -> NamedTuple

Advance the Hainich coupled harness `years` years, ONE year per `run_coupled_cell` call (equivalent to one
long call: the driver re-derives `bc_f = stand_structure_tof(fc)` at both the start of a call and each year
end). ARM and CONTROL differ in EXACTLY the `trait_mortality` flag — same fixtures, same cohorts, same
forcing, same seed, same year count, same default `k_cap` — so the difference is the operator and nothing
else. `n_merge` is exact (the roster grows by at most one appended recruit per year).

`forcing = nothing` repeats the committed 2010 year (the ADR-0048/0049 constant-forcing case); a
`Vector{Vector{AtmForcing}}` advances one entry per simulation year (MODE=response). `boundary_series` is
passed straight through to the emulator (ADR 0026 — `nothing` keeps `s.boundary` static every year).
`t_soil0` is held COMMON across the response arms on purpose, so the only difference between two scenarios
is the forcing itself and not also a soil-temperature initial condition.
"""
function rollout(;
        trait_mortality::Bool, years::Int, forcing = nothing, boundary_series = nothing,
        t_soil0::Float64 = _mean(TAIR_K)
    )
    core = mkcore()
    rc = COPULA ?
        RecruitCopula{Float64}(cop, af, xcop, make_recruit_to_pools(ax_names), live_flux_cond) : nothing
    s = FluxDrivenSlowEmulator(
        core, forest; boundary = BOUNDARY, n_init = N_INIT, age0 = AGE0, seed = 1,
        recruit_copula = rc, trait_mortality = trait_mortality, boundary_series = boundary_series,
        k_cap = K_CAP
    )
    clo = mkclo(t_soil0); state = mkstate()
    wd = Float64[]; sla = Float64[]; ktraj = Int[]; nmerge = Int[]; ntree = Float64[]; agb = Float64[]
    cum_merge = 0
    for y in 1:years
        kprev = length(core.pools)
        yf = forcing === nothing ? YEAR_FORC : forcing[y]
        run_coupled_cell(core, clo, state, yf; slow = s, days_per_year = NDAY)
        appended = length(s.target_history) >= 2 &&
            s.target_history[end] > s.target_history[end - 1] ? 1 : 0
        cum_merge += max(kprev + appended - length(core.pools), 0)
        push!(wd, community_mean(core.pools, p -> p.wooddens))
        push!(sla, community_mean(core.pools, p -> p.sla))
        push!(ktraj, length(core.pools)); push!(nmerge, cum_merge)
        push!(ntree, sum(p.nind for p in core.pools if !p.is_grass; init = 0.0))
        push!(
            agb, sum(
                p.nind * (p.leaf_c + p.sapwood_c + p.heartwood_c) for p in core.pools if !p.is_grass;
                init = 0.0
            )
        )
    end
    return (; s, core, wd, sla, ktraj, nmerge, ntree, agb)
end

const RESPONSE = MODE == "response"
# In response mode the primary (ctl, arm) pair is run on the HISTORIC forcing, so sections 0-2 below read as
# the ADR-0049 measurement transposed onto real historic years; the ssp370 pair and the double difference are
# section 3. In stage2 mode nothing changes: the pair is the constant repeated-2010 forcing.
const BASE_LABEL = RESPONSE ? "historic-forcing" : "constant-forcing"
const T_SOIL0 = RESPONSE ? _mean([f.tair for f in RESP_FORC["historic"][1]]) : _mean(TAIR_K)

println("="^108)
println(
    RESPONSE ?
        "PHASE 3A STAGE 3 — the RESPONSE arm: {trait_mortality on,off} x {historic, ssp370} — Hainich (42490), $YEARS yr" :
        "PHASE 3A STAGE 2 — trait-dependent mortality ARM vs MATCHED CONTROL — Hainich (42490), $YEARS yr"
)
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
if RESPONSE
    for s in RESP_SCEN
        b = RESP_BND[s]
        println(
            "  $s: $(length(RESP_FORC[s])) yr forcing, mean tair ",
            round(_mean([f.tair for y in RESP_FORC[s] for f in y]) - 273.15, digits = 3), " °C, ",
            "boundary gdd5 ", round(b[1][1], digits = 1), " → ", round(b[end][1], digits = 1),
            ", tas_cold_month ", round(b[1][2], digits = 3), " → ", round(b[end][2], digits = 3)
        )
    end
    println("  shared soil-temperature init t_soil0 = ", round(T_SOIL0, digits = 3), " K (both scenarios)")
end

_roll(tm, scen) = RESPONSE ?
    rollout(;
        trait_mortality = tm, years = YEARS, forcing = RESP_FORC[scen],
        boundary_series = RESP_BND[scen], t_soil0 = T_SOIL0
    ) :
    rollout(; trait_mortality = tm, years = YEARS)

ctl = _roll(false, "historic")
arm = _roll(true, "historic")

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
println("1. COMMUNITY WOOD DENSITY — arm vs matched $BASE_LABEL control")
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

# ── 3. MODE=response — THE 2x2 AND ITS DOUBLE DIFFERENCE (ADR 0100) ─────────────────────────────────────
if RESPONSE
    println("\n", "-"^108)
    println("3. THE RESPONSE ARM — {trait_mortality on, off} × {historic, ssp370}, all four in this process")
    println("-"^108)
    ctl_s = _roll(false, "ssp370")
    arm_s = _roll(true, "ssp370")

    # (a) is the BOUNDARY channel even live? The committed demo artifacts were trained with `eco_diag_gdd_5`
    #     and `tas_cold_month` CONSTANT (drf `feat_min == feat_max` on both, `.rcop`'s `x` likewise), so a
    #     forest can carry no split on them and the copula no conditional variation — the transient boundary
    #     should be EXACTLY inert. That is measured here rather than asserted, because if it were NOT inert
    #     the response below would be partly an out-of-band extrapolation (the ADR-0034 trap).
    ctl_s_static = rollout(;
        trait_mortality = false, years = YEARS, forcing = RESP_FORC["ssp370"],
        boundary_series = nothing, t_soil0 = T_SOIL0
    )
    bnd_live = maximum(abs, ctl_s.wd .- ctl_s_static.wd)
    println(
        "  (a) BOUNDARY-CHANNEL LIVENESS: max |Δwd| between transient and static boundary, same forcing = ",
        bnd_live,
        bnd_live == 0.0 ?
            "\n      ⇒ EXACTLY INERT, as the artifact's metadata predicts (both boundary axes are constant in\n" *
            "      training, so no split and no conditional variation exists on them). The response below is\n" *
            "      therefore carried ENTIRELY by the flux/state head, which IS trained over a real range —\n" *
            "      good, because it means nothing here is a boundary extrapolation. It also means this cell's\n" *
            "      demo artifact cannot express a boundary-mediated response AT ALL (a per-cell-artifact\n" *
            "      limitation, not a mechanism limitation: the global pooled_w20 DRFs train on a live boundary)." :
            "\n      ⚠ NOT inert — the transient boundary moves the prediction, so part of the response below is\n" *
            "      an out-of-band extrapolation on a column that was constant in training (ADR 0034). Report it."
    )

    # (b) the four corners and the double difference. THE HEADLINE IS A WINDOW MEAN, NOT THE TERMINAL YEAR:
    #     FIT's +2432.9 is a run mean, and with real interannual forcing the year-to-year interaction swings
    #     by more than the signal (measured: -1070 → +3132 → +239 → +2492 across report years).
    WIN = max(YEARS - SCORE_WINDOW + 1, 1):YEARS
    wmean(a) = _mean(a.wd[WIN])
    println(
        "\n  (b) THE 2×2 — community nind-weighted wooddens (gC/m³), MEAN over yr $(first(WIN))-$(last(WIN))" *
            " (SCORE_WINDOW=$SCORE_WINDOW)"
    )
    println("      ", rpad("", 14), rpad("ctl (off)", 14), rpad("arm (on)", 14), "Δ = arm − ctl")
    for (lbl, c, a) in (("historic", ctl, arm), ("ssp370", ctl_s, arm_s))
        println(
            "      ", rpad(lbl, 14), rpad(round(wmean(c), digits = 2), 14),
            rpad(round(wmean(a), digits = 2), 14), round(wmean(a) - wmean(c), digits = 2)
        )
    end
    R_ctl = wmean(ctl_s) - wmean(ctl)
    R_arm = wmean(arm_s) - wmean(arm)
    D_h = wmean(arm) - wmean(ctl)
    D_s = wmean(arm_s) - wmean(ctl_s)
    println(
        "      ", rpad("R = ssp−hist", 14), rpad(round(R_ctl, digits = 2), 14), rpad(round(R_arm, digits = 2), 14),
        "interaction = ", round(R_arm - R_ctl, digits = 2)
    )
    println(
        "      terminal-year reads, for comparison: Δ_hist ", round(arm.wd[YEARS] - ctl.wd[YEARS], digits = 1),
        " / Δ_ssp ", round(arm_s.wd[YEARS] - ctl_s.wd[YEARS], digits = 1), " / interaction ",
        round((arm_s.wd[YEARS] - ctl_s.wd[YEARS]) - (arm.wd[YEARS] - ctl.wd[YEARS]), digits = 1)
    )
    println(
        "\n      as a share of FIT's +$FIT_SHIFT per-cell warming shift (ADR 0046 §1):\n" *
            "        R_ctl (pre-0049 emulator's own warming response) = ", round(R_ctl / FIT_SHIFT, digits = 4), "×\n" *
            "        R_arm (with the hazard wired in)                 = ", round(R_arm / FIT_SHIFT, digits = 4), "×\n" *
            "        INTERACTION R_arm − R_ctl = Δ_ssp − Δ_hist       = ", round((R_arm - R_ctl) / FIT_SHIFT, digits = 4),
        "×   ⇐ the operator's contribution TO THE RESPONSE"
    )
    println(
        "      identity check (must be ~0): (R_arm−R_ctl) − (Δ_ssp−Δ_hist) = ",
        (R_arm - R_ctl) - (D_s - D_h)
    )

    # (c) trajectory of the interaction — a response should GROW, a level offset should not
    println("\n  (c) TRAJECTORY (does the interaction accumulate, or is it a level offset?)")
    println(
        "      ", rpad("yr", 5), rpad("R_ctl", 11), rpad("R_arm", 11), rpad("interact", 11),
        rpad("/FIT", 9), rpad("Δ_hist", 11), rpad("Δ_ssp", 11), rpad("agb_h ratio", 12), "agb_s ratio"
    )
    for y in REPORT_AT
        y <= YEARS || continue
        rc = ctl_s.wd[y] - ctl.wd[y]; ra = arm_s.wd[y] - arm.wd[y]
        println(
            "      ", rpad(y, 5), rpad(round(rc, digits = 2), 11), rpad(round(ra, digits = 2), 11),
            rpad(round(ra - rc, digits = 2), 11), rpad(round((ra - rc) / FIT_SHIFT, digits = 3), 9),
            rpad(round(arm.wd[y] - ctl.wd[y], digits = 2), 11),
            rpad(round(arm_s.wd[y] - ctl_s.wd[y], digits = 2), 11),
            rpad(round(arm.agb[y] / ctl.agb[y], sigdigits = 6), 12), round(arm_s.agb[y] / ctl_s.agb[y], sigdigits = 6)
        )
    end

    # (d) did the operator's DUTY CYCLE change under warming? ADR 0049 §5's throttle is the count channel, so
    #     the honest question is whether a warming climate makes the DRF demand more net death (higher θ) or
    #     not — that is what decides whether the response can be larger than the level effect.
    println("\n  (d) THE OPERATOR'S DUTY CYCLE, historic vs ssp370 (ADR 0049 §5's throttle)")
    q(v, p) = isempty(v) ? NaN : sort(v)[clamp(1 + round(Int, p * (length(v) - 1)), 1, length(v))]
    println(
        "      ", rpad("arm", 12), rpad("thin yr", 10), rpad("hazard %/yr", 14), rpad("|ρ−1| %/yr", 14),
        rpad("θ median", 12), rpad("θ mean", 12), "θ>0.5"
    )
    for (lbl, a) in (("historic", arm), ("ssp370", arm_s))
        dd = trait_mortality_diag(a.s)
        θ = [d.theta for d in dd if d.thinned && isfinite(d.theta)]
        th = a.s.target_history
        rel = [abs(th[t] / th[t - 1] - 1) for t in 2:length(th)]
        println(
            "      ", rpad(lbl, 12), rpad(count(d -> d.thinned, dd), 10),
            rpad(round(100 * _mean([d.hazard_mean for d in dd]), digits = 3), 14),
            rpad(round(100 * _mean(rel), digits = 4), 14),
            rpad(round(q(θ, 0.5), sigdigits = 4), 12), rpad(round(_mean(θ), sigdigits = 4), 12),
            string(count(>(0.5), θ), " / ", length(θ), " = ", round(100 * count(>(0.5), θ) / max(length(θ), 1), digits = 1), " %")
        )
    end
    println(
        "\n      carbon residual (guardrail 2): ",
        join(
            [
                "$l " * string(maximum(abs, a.s.resid_history)) for (l, a) in
                    (("ctl/hist", ctl), ("arm/hist", arm), ("ctl/ssp", ctl_s), ("arm/ssp", arm_s))
            ], "  "
        )
    )
    # (e) IS THE WARMING RESPONSE A CONDITIONAL RESPONSE, OR AN EXTRAPOLATION? The control's R is carried
    #     ENTIRELY by the recruit channel (ρ-thinning is composition-preserving and the merge is dormant), and
    #     the `.rcop` was fit on the HISTORIC scenario alone (`scenario historic` in its meta). So the sign of
    #     R_ctl means two very different things depending on whether the ssp370 conditioning values are INSIDE
    #     the trained band or outside it. The band is the DRF meta's `feat_min`/`feat_max` — the same training
    #     generation and, per the S1c basis-agreement gate, the same basis on all shared columns.
    println("\n  (e) TRAINED-BAND EXCURSION of the runtime features (ADR 0034's diagnostic, per scenario)")
    fmin = nums(drf_meta["feat_min"]); fmax = nums(drf_meta["feat_max"])
    cn = split(strip(drf_meta["colnames"]))
    ncond = 4        # the copula's live conditioning subset = feats[1:4] (`live_flux_cond`, ADR 0025)
    # The excursion is reported PER SCENARIO, because the discriminating question is not "is the runtime out of
    # band" (the S1d answer for `water_stress` is already yes, and it is line M's) but "does the SSP370 arm go
    # further out than the historic one" — that is what makes R_ctl an extrapolation rather than a conditional.
    println(
        "      ", rpad("feature", 16), rpad("trained band", 24), rpad("historic range", 24),
        rpad("ssp370 range", 24), rpad("exc_hist", 10), rpad("exc_ssp", 10), "ssp/hist"
    )
    for j in eachindex(cn)
        w = fmax[j] - fmin[j]
        cols = String[]
        e = Dict{String, Float64}()
        for (lbl, a) in (("historic", ctl), ("ssp370", ctl_s))
            vals = [f[j] for f in a.s.feature_history]
            lo, hi = minimum(vals), maximum(vals)
            push!(cols, "[$(round(lo, sigdigits = 4)), $(round(hi, sigdigits = 4))]")
            e[lbl] = w > 0 ? max(fmin[j] - lo, hi - fmax[j], 0.0) / w : (hi - lo == 0 ? 0.0 : Inf)
        end
        ratio = e["historic"] > 0 ? round(e["ssp370"] / e["historic"], digits = 2) :
            (e["ssp370"] > 0 ? Inf : 0.0)
        println(
            "      ", rpad(cn[j], 16),
            rpad("[$(round(fmin[j], sigdigits = 4)), $(round(fmax[j], sigdigits = 4))]", 24),
            rpad(cols[1], 24), rpad(cols[2], 24),
            rpad(round(e["historic"], digits = 3), 10), rpad(round(e["ssp370"], digits = 3), 10),
            rpad(ratio, 8), j <= ncond ? " [copula cond]" : ""
        )
    end
    println(
        "      Read the first four rows (the recruit copula's conditioning subset) and the `ssp/hist` column.\n" *
            "      An excursion that GROWS under ssp370 means the recruit traits driving R_ctl are an\n" *
            "      EXTRAPOLATION on a copula fit on the historic scenario alone (fix = retrain on the pooled\n" *
            "      historic+ssp370 table, an artifact version bump); a ratio near 1 with both in band means\n" *
            "      R_ctl is the artifact's genuine conditional response and its sign is a CONDITIONING-SET\n" *
            "      problem (milestone S2). NOTE the two boundary rows report `Inf` because their trained band\n" *
            "      has ZERO width — which is the same fact as (a)'s measured inertness, from the other side: a\n" *
            "      constant training column is infinitely out of band AND carries no split, so it cannot act."
    )

    nm = [a.nmerge[end] for a in (ctl, arm, ctl_s, arm_s)]
    println(
        "      k-cap merges (k_cap = ", K_CAP === nothing ? "production default" : string(K_CAP), "): ",
        join(["$l $n" for (l, n) in zip(("ctl/hist", "arm/hist", "ctl/ssp", "arm/ssp"), nm)], "  "),
        sum(nm) == 0 ?
            "\n      ⇒ DORMANT — the ADR-0048 merge confound is absent, as it was for the Stage-2 arm." :
            "\n      ⚠ THE MERGE FIRED. ADR 0048 measures it as trait-destructive at 3.1-5.1× the signal, and it\n" *
            "      fires an UNEQUAL number of times per scenario, so it contaminates the SCENARIO contrast even\n" *
            "      though it is balanced across the operator contrast. Re-run with a raised K_CAP until this is 0\n" *
            "      and treat THAT as the primary; this run is the default-cap sensitivity check."
    )
end

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
    if RESPONSE
        println(
            "\n  RESPONSE (the Stage-3 headline, Hainich only):\n" *
                "    the pre-0049 emulator's own warming response  R_ctl = ", round(R_ctl, digits = 2),
            " gC/m³ = ", round(R_ctl / FIT_SHIFT, digits = 4), "× FIT\n" *
                "    with the trait hazard wired in                R_arm = ", round(R_arm, digits = 2),
            " gC/m³ = ", round(R_arm / FIT_SHIFT, digits = 4), "× FIT\n" *
                "    THE OPERATOR'S CONTRIBUTION TO THE RESPONSE         = ", round(R_arm - R_ctl, digits = 2),
            " gC/m³ = ", round((R_arm - R_ctl) / FIT_SHIFT, digits = 4), "× FIT"
        )
        println(
            "  Forcing contrast behind it (build_hainich_response_forcing.py prints the full table): the two\n" *
                "  scenarios are DIFFERENT DATA SOURCES (reanalysis vs MPI-ESM1-2-HR) and their mean CO2 differs by\n" *
                "  ~+66 ppm. Both are FIT's own configuration — which is what makes this the analogue of FIT's\n" *
                "  +$FIT_SHIFT — but neither confound may be dropped when the number is quoted, and this is ONE cell."
        )
    end
end
println("="^108)
