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
# ⚠⚠ ONE RUN OF MODE=response IS NOT A MEASUREMENT (ADR 0101). The 2x2 differences four SMALL-SAMPLE
# stochastic rollouts, and the seed spread of the double difference is 0.67-1.74x the FIT shift — THE SAME
# SIZE AS THE EFFECT. ADR 0100's `+1.40x` was one draw (a fair one: 0.03 from its artifact's 8-seed mean) whose
# precision was ~6x overstated, and on both GLOBAL artifacts the operator's contribution turns out to be
# indistinguishable from zero. So: run an ENSEMBLE and quote mean +/- SEM with n —
#     scripts/run_response_seed_ensemble.sh <TAGPREFIX> [NSEEDS]
#     scripts/summarize_response_seed_ensemble.py 'logs/<TAGPREFIX>*.out'
# Holding SEED common across the four corners does NOT pair them (the rosters diverge after yr 1), so
# replication is the only variance lever. ~8 seeds resolve a 1x-FIT effect; ~115 the 0.26x measured.
#
# ARM=recruit — THE RECRUIT-CHANNEL ARM (ADR 0119 §6's kill condition, pre-tested offline). Everything
# above contrasts {trait_mortality on, off}. `ARM=recruit` swaps the CONTRAST AXIS to the recruit channel
# and leaves every other part of the harness — the same count DRF, the same forcing pair, the same seed,
# the same year indices, the same `trait_mortality` setting on BOTH sides (`TRAIT_MORT`) — untouched:
#
#     control (R0) = the pinned recruit COPULA (`recruit_copula`, the shipped configuration)
#     arm     (R1) = the ported FIT establishment rule (`recruit_establishment`, ADR 0119)
#
# WHY IT IS THE SAME 2x2. ADR 0119 ships the ported rule opt-in with a pre-registered flip criterion whose
# KILL CONDITION is: if feeding the recruit marginal from the emulator's OWN community makes the error
# CLIMATE-DEPENDENT the way the count recursion did (ADR 0112-0116 — the recursion manufactures ~90 % of
# FIT's true signal with the WRONG SIGN), the flip is refused and that is the result. "Climate-dependent"
# is exactly a DOUBLE DIFFERENCE — the arm's effect under ssp370 minus its effect under historic — which is
# what the 2x2 already computes. So the kill condition needs no new harness, only this third dimension.
#
# ⚠ WHAT THIS CAN AND CANNOT SAY. It is ONE cell (Hainich, 1 of 54 020 — guardrail 6) and there is no
# per-year FIT truth trajectory to difference against here, so this is a SMOKE TEST of the kill condition,
# NEVER fidelity evidence and never the flip test itself (that is rung 2, on line M's roster harness). It
# answers one question early and cheaply: does the ported rule's contribution to the warming response
# DIVERGE between the two forcings, and in which direction relative to FIT's own +2432.9 shift?
# ⚠ AND IT INHERITS ADR 0101 IN FULL: one run is one draw. Quote mean ± SEM over a seed ensemble.
#   ARM=recruit scripts/run_response_seed_ensemble.sh S-recresp 12
#
# Usage (SLURM — the guard blocks login-node probes, CLAUDE.md §2):
#   scripts/sbatch_julia.sh S-tmort --project=. scripts/trait_mortality_arm_probe.jl
#   MODE=response scripts/sbatch_julia.sh S-tmresp --project=. scripts/trait_mortality_arm_probe.jl
#   ARM=recruit MODE=response scripts/sbatch_julia.sh S-recresp --project=. scripts/trait_mortality_arm_probe.jl
# ENV: ARM (trait_mortality | recruit; default trait_mortality ⇒ byte-identical to ADR 0049/0100/0101),
#      TRAIT_MORT (ARM=recruit only: 0|1, the mortality setting held COMMON across R0 and R1; default 0 =
#      the shipped configuration, so R0 is the emulator as it ships. ⚠ ADR 0119 §6 writes the rung-2 arm
#      under the C1 mortality arm; offline `mort_water`/`mort_temp` are zeroed (ADR 0049 item 4) and θ is
#      throttled to ~0 at this cell (ADR 0049 item 5), so run both and say which),
#      ELIG (ARM=recruit only: comma-separated eligible PFT ids for the ported rule's background channel;
#      default = the ids the FIXTURE's own roster carries, which is this cell's FIT-observed set),
#      MODE (stage2 | response; default stage2 ⇒ byte-identical to the ADR-0049 measurement),
#      YEARS (default 150 in stage2; in response mode it is CLAMPED to the fixture's year count),
#      REPORT_AT (default "1,5,10,20,50,100,150"), COPULA (default 1 — the production configuration; set 0
#      for the fixed-sapling arm), FORCING_DIR (response mode; default
#      /p/tmp/jamirp/emulator_global/S_response_forcing — build it with build_hainich_response_forcing.py),
#      SITE (a name in M_cells.csv — which CELL to run at; unset = Hainich 42490 and byte-identical to every
#      earlier run. A non-default site takes its individuals/soil/forcing from the committed M_* fixtures,
#      its transient boundary from S_response_boundary_<site>.csv, its eligible sets from
#      S_estab_eligibility_<site>.csv, and its n_init/age0/static-boundary from M_cells.csv — NOT from the
#      artifact meta, which is Hainich's. Build the two per-cell fixtures with
#      `SITE=<name> scripts/build_hainich_response_forcing.py` and `scripts/build_estab_eligibility.py`),
#      SEED (1 = ADR 0100's value, reproduces its primary to the digit), K_CAP, SCORE_WINDOW,
#      DRF_ART/RCOP_ART + N_INIT/AGE0/BOUNDARY (swap in another artifact pair — see the block below).
# THE ARTIFACT PAIR IS PART OF THE MEASUREMENT (ADR 0101 §3): the committed single-cell DEMO pair and the
# global production pairs give OPPOSITE-SIGNED baseline warming responses at this cell (-1.23x vs +0.42x),
# because cross-CELL pooling widens the `soilmoist` trained band 4.79x. Always name the pair with a number.
# stage2 reads only committed fixtures and writes nothing; response mode additionally reads the (uncommitted,
# 1.7 MB/scenario) daily forcing from FORCING_DIR — its per-year means are committed in
# `S_hainich_response_boundary.csv` so a later session can verify a rebuild without shipping the daily file.
# ONE CELL per run ⇒ always name it and say "1 of 54 020" (guardrail 6). `SITE` unset = Hainich (42490).

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
# `ARM` — WHICH AXIS THE `arm` vs `ctl` CONTRAST IS ON. `trait_mortality` (default) reproduces ADR
# 0049/0100/0101 exactly; `recruit` contrasts the pinned copula (R0, control) against the ported FIT
# establishment rule (R1, arm) with everything else held common (see the header block).
const ARM = get(ENV, "ARM", "trait_mortality")
ARM in ("trait_mortality", "recruit") || error("ARM must be trait_mortality or recruit (got $ARM)")
const RECRUIT_ARM = ARM == "recruit"
# The mortality setting held COMMON across both corners of the recruit arm — it must be identical on both
# sides or the contrast is not the recruit channel. Ignored when ARM=trait_mortality (there it IS the arm).
const TRAIT_MORT_FIXED = get(ENV, "TRAIT_MORT", "0") != "0"
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
# `SEED` — the emulator's recruit-draw seed, HELD COMMON across all four corners of the 2×2 so it can never
# be part of the arm↔control or historic↔ssp370 contrast. It was hard-coded to 1 through ADR 0100. It is an
# ENV knob because the 2×2 is a difference of small-sample stochastic rollouts (≈17 initial cohorts, a few
# tens of recruits over 81 yr), so the SAMPLING SPREAD of the double difference over seeds is the only thing
# that says whether a single-seed number is a measurement of the operator or one draw from a wide
# distribution. Run an ensemble before quoting any response number (ADR 0101).
const SEED = parse(Int, get(ENV, "SEED", "1"))
MODE in ("stage2", "response") || error("MODE must be stage2 or response (got $MODE)")
_mean(x) = sum(x) / length(x)

function readcsv(path)
    lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
    hdr = split(strip(lines[1]), ',')
    rows = [split(strip(l), ',') for l in lines[2:end]]
    return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
end

# ── `SITE` — WHICH CELL THE HARNESS RUNS AT (added 2026-08-12, ADR 0171) ─────────────────────────────────
# Everything above and below was Hainich-only, and ADR 0170's own handoff named "run it at MORE CELLS, not
# more seeds" as the next step: the acceptance criterion (ADR 0106) is all 54 020 cells, and a one-cell
# result cannot distinguish a property of the operator from a property of Hainich. The per-cell fixtures
# line M already committed for the coupled driver (`M_individuals_*`, `M_soilcolumn_*`, `biome_forcing_*`,
# `M_cells.csv`) make a second cell a configuration change rather than a provisioning project.
#
# ⚠ THE DEFAULT IS BYTE-IDENTICAL AND MUST STAY SO (guardrail 4). `SITE` unset resolves to EXACTLY the file
# names, lat and fixtures every ADR-0049/0100/0101/0170 run used — the Hainich pair, not the `M_*` twin of
# it — so this refactor cannot move a published number. A `SITE=<name>` run reads the `M_*` fixtures for that
# cell and its own `S_response_boundary_<name>.csv` / `S_estab_eligibility_<name>.csv`.
const SITE = get(ENV, "SITE", "")
const DEFAULT_SITE = isempty(SITE)
"`(cell, lat)` and the per-site fixture paths; the default branch is the historical Hainich configuration."
function site_config()
    DEFAULT_SITE && return (
        cell = 42490, lat = 51.25, name = "temperate_hainich",
        ind = "hainich_individuals_2010.csv", forc = "hainich_forcing_2010.csv",
        soil = "hainich_soilcolumn.txt", bnd = "S_hainich_response_boundary.csv",
        elig = "S_hainich_estab_eligibility.csv",
    )
    d = readcsv(joinpath(REFDIR, "M_cells.csv"))
    i = findfirst(==(SITE), String.(d["name"]))
    i === nothing && error("SITE=$SITE is not a name in M_cells.csv ($(join(unique(d["name"]), ", ")))")
    return (
        cell = parse(Int, d["cell"][i]), lat = parse(Float64, d["lat"][i]), name = SITE,
        ind = "M_individuals_$(SITE)_2010.csv", forc = "biome_forcing_$SITE.csv",
        soil = "M_soilcolumn_$SITE.txt", bnd = "S_response_boundary_$SITE.csv",
        elig = "S_estab_eligibility_$SITE.csv",
    )
end
const SC = site_config()
const CELL = SC.cell
# The per-cell count/age seeds a GLOBAL artifact keeps in its `cell_meta.parquet` sidecar are committed for
# the five biome cells in `M_cells.csv` (line M's `extract_cell_slow_init.py`), so a non-default site does
# not need `N_INIT`/`AGE0` passed by hand. ⚠ At a non-default site the ARTIFACT META is NOT consulted for
# them: the committed demo meta carries HAINICH's values, and silently initialising another cell's forest on
# Hainich's stem count is exactly the "someone else's forest" error the artifact block below warns about.
function mcells_init(key)
    d = readcsv(joinpath(REFDIR, "M_cells.csv"))
    i = findfirst(==(SC.name), String.(d["name"]))
    return i === nothing ? nothing : parse(Float64, d[key][i])
end

# ── the shared single-cell harness, byte-for-byte `kcap_merge_confound_probe.jl`'s construction ─────────
ind = readcsv(joinpath(REFDIR, SC.ind))
fcsv = readcsv(joinpath(REFDIR, SC.forc))
# The Hainich fixture is ONE year with no `year` column; the per-biome fixtures carry 2010-2019, so the
# stage-2 constant-forcing year is selected explicitly. Both are the same columns and units.
if haskey(fcsv, "year")
    rows2010 = [j for j in eachindex(fcsv["year"]) if fcsv["year"][j] == "2010"]
    length(rows2010) == 365 || error("$(SC.forc) has $(length(rows2010)) rows for 2010, expected 365")
    fcsv = Dict(k => v[rows2010] for (k, v) in fcsv)
end
fc_(k) = parse.(Float64, fcsv[k])
v(k, r) = parse(Float64, ind[k][r])
nt(r) = parse(Int, ind["type"][r])
const NDAY = length(fc_("doy"))

sd = Float64[]; whcs = Float64[]; rdist = Float64[]
for ln in eachline(joinpath(REFDIR, SC.soil))
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
# ── the ported rule's BIOCLIMATIC ELIGIBLE SET (ARM=recruit only) ────────────────────────────────────────
# `Establishment.eligible_pfts` derives this from 20-yr running temperature means and gdd5, which this
# single-cell harness does not carry as a per-year series. The honest stand-in for ONE cell whose eligible
# set is climatologically stable is the set FIT itself established here — the fixture roster's own ids
# (Hainich: 1-5; the Sahel/Amazon would be {0,7}). It is a FIXED set, so `w_inherit = 4/(4+n_elig)` is
# constant through the run, which also means this probe CANNOT see a warming cell's gate open or close —
# that needs the per-cell(-year) eligibility table, and it is the next task, not this one. Say so.
"""
    eligibility_series() -> Union{Nothing, Dict{String, Vector{Vector{Int}}}}

Per-scenario, per-year eligible PFT sets from the committed per-site eligibility fixture (`SC.elig`)
(`scripts/build_estab_eligibility.py`), in the file's year order. `nothing` if the fixture is absent.

THIS IS WHY THE TABLE WAS BUILT. FIT's gate is `establish.c:29-33` on the 20-year running mean of each
year's coldest monthly mean, and at this cell that mean CROSSES 0 °C under ssp370 — the boreal ids 4/5/6
have `temp_high = 0`, so the eligible set goes {1,2,3,4,5,6} → {1,2,3} partway through the scenario. That
changes `w_inherit = 4/(4 + n_elig)` from 0.400 to 0.571, i.e. the warming closes the background channel
down and hands MORE of the recruit population to the cell's own seedbank. A fixed set cannot represent it,
and it is exactly the feedback the kill condition is about, so the response arm must not use one.
"""
function eligibility_series()
    path = joinpath(REFDIR, SC.elig)
    isfile(path) || return nothing
    d = readcsv(path)
    out = Dict{String, Vector{Vector{Int}}}()
    for i in eachindex(d["scenario"])
        # FILTER ON THE CELL, even though each fixture is written per site. `build_estab_eligibility.py`'s
        # `CSV_OUT` APPENDS every selected cell to one file, so a multi-cell selection (which is how these
        # were built — one 12 GB .clm read serving two sites) yields a file whose rows interleave cells. A
        # reader that only groups by scenario would then build a year series of twice the length in cell
        # order and silently mis-align every year of the run against the gate.
        parse(Int, d["cell"][i]) == CELL || continue
        ids = [p for p in 0:6 if d["elig_$p"][i] == "1"]
        push!(get!(out, String(d["scenario"][i]), Vector{Int}[]), ids)
    end
    return out
end
const ELIG_SERIES = eligibility_series()
# `ELIG` — the FALLBACK fixed set, used when the per-year fixture is absent, in stage2 (constant forcing
# ⇒ a constant gate), or when the env knob is given explicitly. Default = the fixture's first historic
# year, which is the cell's own FIT-derived set; the fixture roster's ids are a poor stand-in (this
# patch carries only {2,3}, while FIT's gate at this cell admits six PFTs).
const ELIG = if haskey(ENV, "ELIG")
    parse.(Int, split(ENV["ELIG"], ','))
elseif ELIG_SERIES !== nothing && haskey(ELIG_SERIES, "historic")
    ELIG_SERIES["historic"][1]
else
    sort(unique(PFT_IDS))
end
const W_INHERIT = 4 / (4 + length(ELIG))       # ADR 0045's closed form, = Establishment.w_inherit(n_elig)
# Use the per-year series only in response mode, only when the fixture covers the scenario, and only if
# the fixed set was not pinned by hand — so `ELIG=...` remains an exact override for a sensitivity run.
const ELIG_PERYEAR = RECRUIT_ARM && MODE == "response" && !haskey(ENV, "ELIG") && ELIG_SERIES !== nothing

"The eligibility policy passed to `RecruitEstablishment` for `scen`: a per-year callable, or the fixed set."
function elig_policy(scen)
    (ELIG_PERYEAR && haskey(ELIG_SERIES, scen)) || return ELIG
    ser = ELIG_SERIES[scen]
    # `s.year` counts COMPLETED years, and `reconcile_demography!` reads the policy before incrementing
    # it — the same 1-based `clamp(s.year + 1, ...)` indexing the transient boundary uses, so the gate
    # and the boundary always describe the same simulation year.
    return s -> ser[clamp(s.year + 1, 1, length(ser))]
end
mkcore() = FDiffFastCore([mkp(r) for r in ROWS], [mkt(r) for r in ROWS], SOIL, SC.lat; pft_ids = PFT_IDS)
mkclo(t0 = _mean(TAIR_K)) = SEBEnergyClosure(; t_soil0 = t0)
mkstate() = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))

# ── MODE=response: the two REAL scenario forcings + their ADR-0026 transient boundaries ─────────────────
"""
    load_scenario(scen) -> Vector{Vector{AtmForcing}}

Per-year day vectors for `scen` ∈ {"historic", "ssp370"} from `FORCING_DIR/<scen>_<CELL>_daily.csv`
(`scripts/build_hainich_response_forcing.py`, itself gated against the committed 2010 forcing fixture). Years
are returned in file order; every year must carry exactly `NDAY` days so the two scenarios are differenced at
matched year indices.
"""
function load_scenario(scen)
    path = joinpath(FORCING_DIR, "$(scen)_$(CELL)_daily.csv")
    isfile(path) || error(
        "MODE=response needs $path — build it first:\n" *
            "    python3 scripts/build_hainich_response_forcing.py\n" *
            "(the daily forcing is deliberately NOT committed; its per-year means are, in " *
            "$(SC.bnd))"
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

# ── the artifact pair, overridable (ADR 0101) ────────────────────────────────────────────────────────────
# Default = the committed Hainich DEMO pair. `DRF_ART`/`RCOP_ART` swap in another pair — e.g. the GLOBAL
# `*_pooled_w20_t8` artifacts, which are trained on historic AND ssp370 and so have `soilmoist` in band where
# the demo's historic-only copula does not (ADR 0100 §5). A global meta has no per-cell `boundary`/`n_init`/
# `age0` (they live in its `cell_meta.parquet` sidecar), so those come from `BOUNDARY`/`N_INIT`/`AGE0` when the
# meta lacks them — pass the values for THIS cell or the run is initialised on someone else's forest.
const DRF_ART = get(ENV, "DRF_ART", joinpath(REFDIR, "drf_forest_hainich.drf"))
const RCOP_ART = get(ENV, "RCOP_ART", joinpath(REFDIR, "recruit_copula_hainich.rcop"))
drf_meta = read_meta(replace(DRF_ART, r"\.drf$" => "_meta.txt"))
forest = DRF.load_forest(DRF_ART)
cop, af, xcop, ax_names, cond_cols_art = DRF.load_copula(RCOP_ART)
"""
Per-cell scalar: ENV first, then — at a NON-DEFAULT `SITE` — that site's committed `M_cells.csv` row, then
the artifact meta (which only a per-cell artifact carries).

⚠ THE PRECEDENCE IS DELIBERATE AND ORDER-SENSITIVE. At the default site the order is the historical one
(ENV → meta), so the committed demo pair keeps initialising the run exactly as it always did. At any other
site the meta is consulted only AFTER `M_cells.csv`, because the committed demo meta carries **Hainich's**
`n_init`/`age0` and would silently start another cell's forest on Hainich's stem count — the failure the
error message below has warned about since ADR 0101 without being able to prevent it.
"""
function cellinit(key, envkey)
    haskey(ENV, envkey) && return parse(Float64, ENV[envkey])
    if !DEFAULT_SITE
        v = mcells_init(key == "n_init" ? "n_init" : "age0")
        v === nothing || return v
    end
    haskey(drf_meta, key) || error(
        "$(basename(DRF_ART))'s meta has no `$key` (a GLOBAL artifact keeps it in cell_meta.parquet) — " *
            "pass $envkey for THIS cell, or the run starts on the wrong forest"
    )
    return parse(Float64, drf_meta[key])
end
# The 4-column static boundary tail. At a non-default site the artifact meta's `boundary` is Hainich's, so —
# same reasoning as `cellinit` — the site's own committed `M_cells.csv` row supplies it, in the frozen
# `flux_feature_vector` tail order (gdd5, tas_cold_month, soil_depth, co2). In response mode rows 1:2 are
# then overwritten per year from the transient fixture, so only rows 3:4 (soil_depth, co2) survive into the
# run; they are per-cell and per-artifact respectively, which is exactly why they must not be Hainich's.
function mcells_boundary()
    d = readcsv(joinpath(REFDIR, "M_cells.csv"))
    i = findfirst(==(SC.name), String.(d["name"]))
    i === nothing && return nothing
    return [parse(Float64, d[k][i]) for k in ("eco_diag_gdd_5", "tas_cold_month", "soil_depth", "co2")]
end
function site_boundary()
    haskey(ENV, "BOUNDARY") && return nums(ENV["BOUNDARY"])
    if !DEFAULT_SITE
        v = mcells_boundary()
        v === nothing || return v
    end
    # At the default site the artifact meta keeps its historical precedence, so a demo-pair run is unchanged;
    # `M_cells.csv` is the LAST resort rather than an error, which is what lets the GLOBAL pooled pair run at
    # Hainich without a hand-passed BOUNDARY. It is the same cell's own committed row either way, and the
    # value used is echoed in the artifact line below, so the substitution is never silent.
    if !haskey(drf_meta, "boundary")
        v = mcells_boundary()
        v === nothing && error(
            "$(basename(DRF_ART)) has no `boundary` in its meta and $(SC.name) is not in M_cells.csv — " *
                "pass BOUNDARY=\"gdd5 tcm soil_depth co2\""
        )
        println("   NOTE: $(basename(DRF_ART)) has no `boundary` in its meta ⇒ taking it from M_cells.csv")
        return v
    end
    return nums(drf_meta["boundary"])
end
const BOUNDARY = site_boundary()
const N_INIT = cellinit("n_init", "N_INIT")
const AGE0 = cellinit("age0", "AGE0")

# ── the response arm's per-scenario TRANSIENT boundary (ADR 0026) ────────────────────────────────────────
# Only the two TIME-VARYING axes move (`gdd5`, `tas_cold_month`); `soil_depth` and the boundary tail's `co2`
# stay at the artifact's own values, because the artifact was TRAINED on those (ADR 0004 pins the co2 tail at
# 369 — it is a conditioning feature, NOT the forcing co2 the daily file carries, which does vary).
"Per-year `boundary_series` rows for `scen`, from the committed per-site boundary fixture (`SC.bnd`)."
function scenario_boundary(scen)
    # `BND_FIXTURE` — read the transient boundary from another file (an absolute path, or a name under
    # `references/`). It exists to make a BASIS comparison runnable: ADR 0171 corrected the ssp370 lead-in in
    # this fixture, and the only honest way to state what that changed is to run the same arm on both files.
    # It is also the knob to use for any future sensitivity on the conditioning basis — do NOT hand-edit the
    # committed fixture to run one.
    bndfile = get(ENV, "BND_FIXTURE", SC.bnd)
    d = readcsv(isabspath(bndfile) ? bndfile : joinpath(REFDIR, bndfile))
    rows = [i for i in eachindex(d["scenario"]) if d["scenario"][i] == scen]
    isempty(rows) && error("$bndfile has no scenario=$scen rows")
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
    rollout(; arm_on, years, forcing = nothing, boundary_series = nothing, t_soil0 = _mean(TAIR_K))
        -> NamedTuple

Advance the Hainich coupled harness `years` years, ONE year per `run_coupled_cell` call (equivalent to one
long call: the driver re-derives `bc_f = stand_structure_tof(fc)` at both the start of a call and each year
end). ARM and CONTROL differ in EXACTLY ONE configuration flag — same fixtures, same cohorts, same forcing,
same seed, same year count, same default `k_cap` — so the difference is that flag and nothing else.
`n_merge` is exact (the roster grows by at most one appended recruit per year).

Which flag depends on `ARM`:
  * `ARM=trait_mortality` (default) — `arm_on` IS `trait_mortality`; the recruit channel is the copula on
    both sides (`COPULA`). Byte-identical to the ADR-0049/0100/0101 measurement.
  * `ARM=recruit` — `arm_on` swaps the recruit channel: `false` = the pinned copula (R0), `true` = the
    ported FIT establishment rule (R1, a FRESH `RecruitEstablishment` per rollout so its seedbank and
    diagnostics never leak between corners). `trait_mortality` is then `TRAIT_MORT_FIXED` on BOTH sides.

`forcing = nothing` repeats the committed 2010 year (the ADR-0048/0049 constant-forcing case); a
`Vector{Vector{AtmForcing}}` advances one entry per simulation year (MODE=response). `boundary_series` is
passed straight through to the emulator (ADR 0026 — `nothing` keeps `s.boundary` static every year).
`t_soil0` is held COMMON across the response arms on purpose, so the only difference between two scenarios
is the forcing itself and not also a soil-temperature initial condition.
"""
function rollout(;
        arm_on::Bool, years::Int, forcing = nothing, boundary_series = nothing,
        t_soil0::Float64 = _mean(TAIR_K), scen::String = "historic"
    )
    core = mkcore()
    use_estab = RECRUIT_ARM && arm_on
    tmort = RECRUIT_ARM ? TRAIT_MORT_FIXED : arm_on
    # the two recruit channels are MUTUALLY EXCLUSIVE in the constructor (ADR 0119) — exactly one is set
    rc = (COPULA && !use_estab) ?
        RecruitCopula{Float64}(cop, af, xcop, make_recruit_to_pools(ax_names), live_flux_cond) : nothing
    re = use_estab ? RecruitEstablishment{Float64}(; eligible = elig_policy(scen)) : nothing
    s = FluxDrivenSlowEmulator(
        core, forest; boundary = BOUNDARY, n_init = N_INIT, age0 = AGE0, seed = SEED,
        recruit_copula = rc, recruit_establishment = re, trait_mortality = tmort,
        boundary_series = boundary_series, k_cap = K_CAP
    )
    clo = mkclo(t_soil0); state = mkstate()
    wd = Float64[]; sla = Float64[]; ktraj = Int[]; nmerge = Int[]; ntree = Float64[]; agb = Float64[]
    # the two ADR-0110 axes are recorded too: the recruit channel sets all FOUR trait axes, so an arm that
    # only ever reports `wooddens` would miss three quarters of what it changed. They are 0 on any cohort
    # rebuilt from the `ind` fixture (the UNSET sentinel), so read them as RECRUIT-cohort diagnostics.
    d95 = Float64[]; mws = Float64[]
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
        push!(d95, community_mean(core.pools, p -> p.d95max))
        push!(mws, community_mean(core.pools, p -> p.minwscal))
        push!(ktraj, length(core.pools)); push!(nmerge, cum_merge)
        push!(ntree, sum(p.nind for p in core.pools if !p.is_grass; init = 0.0))
        push!(
            agb, sum(
                p.nind * (p.leaf_c + p.sapwood_c + p.heartwood_c) for p in core.pools if !p.is_grass;
                init = 0.0
            )
        )
    end
    return (; s, core, wd, sla, d95, mws, ktraj, nmerge, ntree, agb)
end

const RESPONSE = MODE == "response"
# In response mode the primary (ctl, arm) pair is run on the HISTORIC forcing, so sections 0-2 below read as
# the ADR-0049 measurement transposed onto real historic years; the ssp370 pair and the double difference are
# section 3. In stage2 mode nothing changes: the pair is the constant repeated-2010 forcing.
const BASE_LABEL = RESPONSE ? "historic-forcing" : "constant-forcing"
const T_SOIL0 = RESPONSE ? _mean([f.tair for f in RESP_FORC["historic"][1]]) : _mean(TAIR_K)

# The three row labels of the response panel. Kept as constants, not inlined: the summarizer parses
# `R_ctl (...) = ` and `R_arm (...) = `, so the two must stay one printed token apart from their numbers.
const CTL_LABEL = RECRUIT_ARM ? "R0 — the shipped copula recruit channel" :
    "pre-0049 emulator's own warming response"
const ARM_LABEL = RECRUIT_ARM ? "R1 — the ported FIT establishment rule" :
    "with the trait hazard wired in"
const DIFF_LABEL = RECRUIT_ARM ? "R1 − R0, THE RECRUIT CHANNEL'S CONTRIBUTION" :
    "THE OPERATOR'S CONTRIBUTION TO THE RESPONSE"
const AXIS_LABEL = RECRUIT_ARM ?
    "recruit channel {R0 = pinned copula, R1 = ported FIT establishment}" :
    "{trait_mortality on, off}"
println("="^108)
println(
    RESPONSE ?
        "THE RESPONSE 2×2: $AXIS_LABEL × {historic, ssp370} — $(SC.name) ($CELL), $YEARS yr" :
        "ARM vs MATCHED CONTROL on $AXIS_LABEL — $(SC.name) ($CELL), $YEARS yr"
)
println("="^108)
println("ARM=", ARM, RECRUIT_ARM ? "   (ADR 0119 §6's kill condition, pre-tested offline — 1 of 54 020)" : "")
if RECRUIT_ARM
    println(
        "  control (R0) = recruit_copula ", COPULA ? "ON" : "OFF (fixed sapling — NOT the shipped R0)",
        "   arm (R1) = recruit_establishment",
        "\n  trait_mortality held COMMON on both sides = ", TRAIT_MORT_FIXED
    )
    if ELIG_PERYEAR
        for s in ("historic", "ssp370")
            haskey(ELIG_SERIES, s) || continue
            ser = ELIG_SERIES[s]
            uq = unique(ser)
            println(
                "  eligible set, $s: PER-YEAR from $(SC.elig), $(length(ser)) yr, ",
                length(uq), " distinct set(s) ",
                join(["{" * join(u, ",") * "}×" * string(count(==(u), ser)) for u in uq], " "),
                "  ⇒ w_inherit ", join(sort(unique([round(4 / (4 + length(u)), digits = 4) for u in uq])), " → ")
            )
        end
    else
        println(
            "  eligible set: FIXED ", ELIG, " (w_inherit = 4/(4+", length(ELIG), ") = ",
            round(W_INHERIT, digits = 4), ")",
            haskey(ENV, "ELIG") ? "  [pinned by ELIG]" :
                "  ⚠ no per-year fixture ⇒ this run cannot see the gate open or close under warming"
        )
    end
end
println("copula: ", COPULA ? "ON (production)" : "OFF (fixed sapling)")
println(
    "artifacts: drf=", basename(DRF_ART), " (scenario ", get(drf_meta, "scenario", "?"), ", ",
    get(drf_meta, "ntrees", "?"), " trees)  rcop=", basename(RCOP_ART),
    "\n           n_init=", N_INIT, "  age0=", round(AGE0, digits = 4), "  seed=", SEED,
    "  boundary=", BOUNDARY,
    "\n           copula cond_cols=", join(cond_cols_art, " ")
)
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

_roll(on, scen) = RESPONSE ?
    rollout(;
        arm_on = on, years = YEARS, forcing = RESP_FORC[scen],
        boundary_series = RESP_BND[scen], t_soil0 = T_SOIL0, scen = scen
    ) :
    rollout(; arm_on = on, years = YEARS)

ctl = _roll(false, "historic")
arm = _roll(true, "historic")

# ── 0. DID THE OPERATOR FIRE? (ADR 0048's own correction — check before reading any Δ) ─────────────────
println("\n", "-"^108)
println("0. DID THE OPERATOR FIRE?  (a Δ from an operator that never ran bounds NOTHING)")
println("-"^108)
dg = trait_mortality_diag(arm.s)
# ── ARM=recruit: the ported rule's OWN fire check (ADR 0119's `EstabDiag` — read `sb_weight` and the
#    inherited share FIRST). An establishment rule that only ever drew from the uniform background channel
#    measured half the rule: inheritance is 44 % of recruits in a mixed cell (ADR 0045) and it is the ONLY
#    channel that can feed the community back into the recruit marginal — i.e. the only channel the kill
#    condition is about. A run with an empty seedbank bounds NOTHING about the feedback risk. ──
const ED_ARM = RECRUIT_ARM ? establishment_diag(arm.s) : EstabDiag[]
const ED_CTL = RECRUIT_ARM ? establishment_diag(ctl.s) : EstabDiag[]
if RECRUIT_ARM
    ninh = count(d -> d.inherited, ED_ARM)
    println("  control (R0) establishment draws: ", length(ED_CTL), " (MUST be 0 — R0 is the copula)")
    println(
        "  arm (R1) establishment draws:     ", length(ED_ARM), " of $YEARS yr",
        isempty(ED_ARM) ? "" :
            "\n  inherited / background:           $ninh / $(length(ED_ARM)) = " *
            string(round(100 * ninh / length(ED_ARM), digits = 1)) * " %  (expected " *
            string(round(100 * _mean([d.w_inherit for d in ED_ARM]), digits = 1)) *
            " % = the mean of the years' own 4/(4+n_elig); a LARGE shortfall means the seedbank was " *
            "still filling)" *
            "\n  n_elig over the drawn years:      " *
            join(["$(k):$(count(d -> d.n_elig == k, ED_ARM))" for k in sort(unique(d.n_elig for d in ED_ARM))], " ") *
            "\n  seedbank at the final draw:       " * string(ED_ARM[end].sb_entries) *
            " entries, " * string(round(ED_ARM[end].sb_weight, sigdigits = 6)) *
            " individual-years  ⇒ the feedback channel " *
            (ED_ARM[end].sb_weight > 0 ? "IS live" : "NEVER filled — this run bounds nothing") *
            "\n  drawn PFT ids (count):            " *
            join(["$id:$(count(d -> d.pft_id == id, ED_ARM))" for id in sort(unique(d.pft_id for d in ED_ARM))], " ")
    )
end
if !RECRUIT_ARM
    println("  control diagnostics recorded: ", length(trait_mortality_diag(ctl.s)), " (MUST be 0 — the flag is off)")
    println("  arm diagnostics recorded:     ", length(dg), " of $YEARS yr")
end
const FIRED = RECRUIT_ARM ? any(d -> d.drew, ED_ARM) : (!isempty(dg) && any(d -> d.thinned, dg))
if isempty(dg)
    RECRUIT_ARM || println("  ⚠ THE OPERATOR NEVER RAN — every Δ below is a NON-MEASUREMENT.")
    RECRUIT_ARM && !FIRED &&
        println("  ⚠ THE PORTED RULE NEVER DREW A RECRUIT — every Δ below is a NON-MEASUREMENT.")
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
RECRUIT_ARM && println(
    "  (R0 = pinned copula is the `ctl` column, R1 = ported FIT establishment is the `arm` column.)"
)
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
if RECRUIT_ARM
    # THE OTHER THREE AXES. The recruit channel draws all four, and `wooddens` alone is the mortality
    # arm's axis, not this one's. `d95max`/`minwscal` are 0 on every cohort rebuilt from the `ind` fixture
    # (the ADR-0110 UNSET sentinel), so their community mean rises from 0 purely as recruits accumulate —
    # a LEVEL that is not comparable to FIT's, but a DIFFERENCE between R0 and R1 that is.
    println("\n  ALL FOUR RECRUIT AXES (community nind-weighted means; d95max/minwscal start at the UNSET 0)")
    println(
        "  ", rpad("yr", 5), rpad("sla_arm", 12), rpad("sla_ctl", 12), rpad("d95_arm", 11),
        rpad("d95_ctl", 11), rpad("mws_arm", 11), rpad("mws_ctl", 11)
    )
    for y in REPORT_AT
        y <= YEARS || continue
        println(
            "  ", rpad(y, 5), rpad(round(arm.sla[y], sigdigits = 5), 12),
            rpad(round(ctl.sla[y], sigdigits = 5), 12), rpad(round(arm.d95[y], digits = 3), 11),
            rpad(round(ctl.d95[y], digits = 3), 11), rpad(round(arm.mws[y], digits = 5), 11),
            rpad(round(ctl.mws[y], digits = 5), 11)
        )
    end
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
RECRUIT_ARM && println(
    "  ⚠ ON THE RECRUIT ARM THIS PANEL IS DESCRIPTIVE, NOT THE ACCEPTANCE TARGET. ADR 0046 §3's gradient is\n" *
        "  a SELECTION fingerprint, and the contrast here changes what recruits are BORN with, not who dies.\n" *
        "  A Δ across bins here is the two samplers' marginals differing (that is the point of ADR 0118 §1),\n" *
        "  and only the youngest bins can differ at all — the older bins hold the same inherited fixture\n" *
        "  cohorts in both arms."
)

# ── 3. MODE=response — THE 2x2 AND ITS DOUBLE DIFFERENCE (ADR 0100) ─────────────────────────────────────
if RESPONSE
    println("\n", "-"^108)
    println("3. THE RESPONSE ARM — $AXIS_LABEL × {historic, ssp370}, all four in this process")
    println("-"^108)
    ctl_s = _roll(false, "ssp370")
    arm_s = _roll(true, "ssp370")

    # (a) is the BOUNDARY channel even live? The committed demo artifacts were trained with `eco_diag_gdd_5`
    #     and `tas_cold_month` CONSTANT (drf `feat_min == feat_max` on both, `.rcop`'s `x` likewise), so a
    #     forest can carry no split on them and the copula no conditional variation — the transient boundary
    #     should be EXACTLY inert. That is measured here rather than asserted, because if it were NOT inert
    #     the response below would be partly an out-of-band extrapolation (the ADR-0034 trap).
    ctl_s_static = rollout(;
        arm_on = false, years = YEARS, forcing = RESP_FORC["ssp370"],
        boundary_series = nothing, t_soil0 = T_SOIL0, scen = "ssp370"
    )
    bnd_live = maximum(abs, ctl_s.wd .- ctl_s_static.wd)
    # ⚠ "not inert" is NOT the same as "extrapolating", and conflating them mis-reports a GOOD artifact as a
    #   broken one (it did, for the pooled artifact, before this branch existed). A live boundary channel is
    #   only a problem if the runtime boundary is also OUT of the trained band — so classify on both facts.
    fmin_b = nums(drf_meta["feat_min"]); fmax_b = nums(drf_meta["feat_max"])
    bnd_cols = (length(fmin_b) - length(BOUNDARY) + 1):length(fmin_b)
    bnd_zero_width = all(j -> fmax_b[j] == fmin_b[j], bnd_cols)
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
            bnd_zero_width ?
            "\n      ⚠ NOT inert, AND the boundary columns have ZERO-WIDTH trained bands — so the transient\n" *
            "      boundary is moving the prediction on a column the artifact never saw vary. That IS the\n" *
            "      ADR-0034 extrapolation, and the response below is partly an artefact of it. Report it." :
            "\n      ⇒ LIVE and IN BAND — the artifact was trained on a VARYING boundary (see (e): the two\n" *
            "      boundary rows have a real trained range and 0.0 excursion), so the transient boundary is\n" *
            "      doing the job ADR 0026 built it for rather than extrapolating. This is the desirable state,\n" *
            "      not a warning: this artifact CAN express a boundary-mediated response where the per-cell\n" *
            "      demo artifact (which reads exactly 0.0 here) structurally cannot."
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
    println(
        "      ", rpad("", 14), rpad(RECRUIT_ARM ? "ctl (R0 cop)" : "ctl (off)", 14),
        rpad(RECRUIT_ARM ? "arm (R1 port)" : "arm (on)", 14), "Δ = arm − ctl"
    )
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
            "        R_ctl (", rpad(CTL_LABEL, 42), ") = ", round(R_ctl / FIT_SHIFT, digits = 4), "×\n" *
            "        R_arm (", rpad(ARM_LABEL, 42), ") = ", round(R_arm / FIT_SHIFT, digits = 4), "×\n" *
            "        INTERACTION R_arm − R_ctl = Δ_ssp − Δ_hist       = ", round((R_arm - R_ctl) / FIT_SHIFT, digits = 4),
        "×   ⇐ the ", RECRUIT_ARM ? "recruit channel's" : "operator's", " contribution TO THE RESPONSE"
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
    q(v, p) = isempty(v) ? NaN : sort(v)[clamp(1 + round(Int, p * (length(v) - 1)), 1, length(v))]
    if !RECRUIT_ARM || TRAIT_MORT_FIXED
        println("\n  (d) THE OPERATOR'S DUTY CYCLE, historic vs ssp370 (ADR 0049 §5's throttle)")
        println(
            "      ", rpad("arm", 12), rpad("thin yr", 10), rpad("hazard %/yr", 14), rpad("|ρ−1| %/yr", 14),
            rpad("θ median", 12), rpad("θ mean", 12), "θ>0.5"
        )
        for (lbl, a) in (("historic", arm), ("ssp370", arm_s))
            dd = trait_mortality_diag(a.s)
            θ = [d.theta for d in dd if d.thinned && isfinite(d.theta)]
            # distinct names from section 0's globals: `th = ...` in this soft scope would otherwise warn
            th_a = a.s.target_history
            rel_a = [abs(th_a[t] / th_a[t - 1] - 1) for t in 2:length(th_a)]
            println(
                "      ", rpad(lbl, 12), rpad(count(d -> d.thinned, dd), 10),
                rpad(round(100 * _mean([d.hazard_mean for d in dd]), digits = 3), 14),
                rpad(round(100 * _mean(rel_a), digits = 4), 14),
                rpad(round(q(θ, 0.5), sigdigits = 4), 12), rpad(round(_mean(θ), sigdigits = 4), 12),
                string(count(>(0.5), θ), " / ", length(θ), " = ", round(100 * count(>(0.5), θ) / max(length(θ), 1), digits = 1), " %")
            )
        end
    else
        println(
            "\n  (d) the trait-mortality duty cycle is not printed: the operator is OFF on both sides of this\n" *
                "      contrast (TRAIT_MORT=0). ADR 0119 §6 writes the rung-2 arm under the C1 mortality arm, so\n" *
                "      run TRAIT_MORT=1 as well and say which configuration a number came from."
        )
    end
    # (d2) THE RECRUIT CHANNEL'S OWN MECHANISM PANEL — the kill condition's actual subject.
    #      The ported rule's marginal is a FUNCTIONAL OF THE EMULATOR'S OWN COMMUNITY through the seedbank,
    #      so the question "did the error become climate-dependent" is, mechanically: does the DRAWN
    #      marginal move DIFFERENTLY under the two forcings? That is a double difference on the sampler
    #      itself, upstream of growth and mortality, so it separates the sampler's drift from the stand's.
    #      ⚠ Read `inherited %` first — with an empty or thin seedbank the two scenarios draw from the SAME
    #      static uniform intervals and the panel is inert BY CONSTRUCTION, not by measurement.
    if RECRUIT_ARM
        println("\n  (d2) THE DRAWN RECRUIT MARGINAL (arm only; R0's copula draws are not recorded per year)")
        println(
            "      ", rpad("scenario", 12), rpad("draws", 8), rpad("inherit %", 11), rpad("sb_weight", 12),
            rpad("wooddens", 12), rpad("sla", 11), rpad("d95max", 11), "minwscal"
        )
        eds = Dict{String, Vector{EstabDiag}}()
        for (lbl, a) in (("historic", arm), ("ssp370", arm_s))
            dd = establishment_diag(a.s)
            eds[lbl] = dd
            println(
                "      ", rpad(lbl, 12), rpad(length(dd), 8),
                rpad(isempty(dd) ? "-" : round(100 * count(d -> d.inherited, dd) / length(dd), digits = 1), 11),
                rpad(isempty(dd) ? "-" : round(dd[end].sb_weight, sigdigits = 6), 12),
                rpad(isempty(dd) ? "-" : round(_mean([d.wooddens for d in dd]), digits = 1), 12),
                rpad(isempty(dd) ? "-" : round(_mean([d.sla for d in dd]), sigdigits = 5), 11),
                rpad(isempty(dd) ? "-" : round(_mean([d.d95max for d in dd]), digits = 2), 11),
                isempty(dd) ? "-" : round(_mean([d.minwscal for d in dd]), digits = 5)
            )
        end
        if !isempty(eds["historic"]) && !isempty(eds["ssp370"])
            dwd = _mean([d.wooddens for d in eds["ssp370"]]) - _mean([d.wooddens for d in eds["historic"]])
            inh_h = 100 * count(d -> d.inherited, eds["historic"]) / length(eds["historic"])
            inh_s = 100 * count(d -> d.inherited, eds["ssp370"]) / length(eds["ssp370"])
            println(
                "      Δ(mean drawn wooddens), ssp370 − historic = ", round(dwd, digits = 1),
                " gC/m³ = ", round(dwd / FIT_SHIFT, digits = 4), "× FIT\n" *
                    "      Δ(inherited share) = ", round(inh_s - inh_h, digits = 1), " pp",
                "\n      ⇒ the SAMPLER's own scenario response. It can be non-zero ONLY through the seedbank" *
                    "\n        (the uniform channel's intervals are static parameters), so a non-zero value here IS" *
                    "\n        the feedback loop, measured. Zero with a live seedbank means the community moved but" *
                    "\n        the recruit marginal did not follow — read it against the (b) table's Δ, not alone." *
                    "\n      ⚠ It is also a MIXTURE difference: a shift in the inherited share moves the mean even" *
                    "\n        with both channels' own marginals unchanged. Both columns are printed for that reason."
            )
        end
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
    fmin = fmin_b; fmax = fmax_b        # already read in (a), which classifies the boundary rows on them
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
            "      problem (milestone S2)." *
            (
            bnd_zero_width ?
                "\n      NOTE the two boundary rows report `Inf` because their trained band has ZERO\n" *
                "      width — the same fact as (a)'s measured inertness seen from the other side: a constant\n" *
                "      training column is infinitely out of band AND carries no split, so it cannot act. An\n" *
                "      excursion ranking MUST special-case this or it ranks the one harmless channel top." :
                "\n      The boundary rows carry a REAL trained range here (this artifact saw the boundary vary),\n" *
                "      so their excursion is a genuine number and (a) reports the channel live — contrast the\n" *
                "      per-cell demo pair, whose zero-width boundary reads `Inf` and 0.0 respectively."
        )
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
    println(
        RECRUIT_ARM ?
            "  NON-MEASUREMENT — the ported rule never drew a recruit. Fix that before reading anything above." :
            "  NON-MEASUREMENT — the operator did not thin in any year. Fix that before reading anything above."
    )
else
    d = arm.wd[YSCORE] - ctl.wd[YSCORE]
    println(
        "  controlled Δ(community wooddens) at yr ", YSCORE, " = ", round(d, digits = 2), " gC/m³ = ",
        round(d / FIT_SHIFT, digits = 4), "× the FIT warming shift (same sign as FIT: ", d > 0, ")"
    )
    println(
        "  This is a MECHANISM check on ONE cell ($(SC.name)/$CELL, 1 of 54 020 — guardrail 6), NOT the " *
            "ADR-0044 response gate.\n" *
            "  The P1 threshold is ΔRr ≥ +0.036 on the global gate and is measured elsewhere; nothing here\n" *
            "  may be quoted as 'reducing the damping' (ADR 0044 — the residual is PLACEMENT, not shrinkage)."
    )
    if RESPONSE
        println(
            "\n  RESPONSE (the headline, $(SC.name)/$CELL only — 1 of 54 020):\n" *
                "    ", rpad(CTL_LABEL, 44), " R_ctl = ", round(R_ctl, digits = 2),
            " gC/m³ = ", round(R_ctl / FIT_SHIFT, digits = 4), "× FIT\n" *
                "    ", rpad(ARM_LABEL, 44), " R_arm = ", round(R_arm, digits = 2),
            " gC/m³ = ", round(R_arm / FIT_SHIFT, digits = 4), "× FIT\n" *
                "    ", rpad(DIFF_LABEL, 44), "       = ", round(R_arm - R_ctl, digits = 2),
            " gC/m³ = ", round((R_arm - R_ctl) / FIT_SHIFT, digits = 4), "× FIT"
        )
        RECRUIT_ARM && println(
            "\n  ⚠ HOW THIS MAY AND MAY NOT BE READ (ADR 0119 §6, pre-registered before the run):\n" *
                "    * it is ONE cell, 1 of 54 020, and ONE seed — quote the seed ensemble, never this line;\n" *
                "    * it is NOT the flip test. The flip is decided on line M's rung-2 roster harness, where the\n" *
                "      roster comes back from the C each year. This is a cheap early read of the KILL condition;\n" *
                "    * the kill condition fires on a recruit channel whose error becomes CLIMATE-DEPENDENT — i.e.\n" *
                "      a large |R1 − R0| that moves the response AWAY from FIT's own +$FIT_SHIFT, or a (d2) sampler\n" *
                "      response that is large and wrong-signed. A small interaction is NOT a pass on its own: read\n" *
                "      (d2)'s inherited share first, because an unfilled seedbank makes the whole panel inert."
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
