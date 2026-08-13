#!/usr/bin/env julia
# ── M4 — THE RESILIENCE BATTERY: does the coupled emulator carry the RIGHT memory? ────────────────────
#
# `ENGINEERING_STANDARDS` §2 items 4 + 11 and `DEVELOPMENT_PLAN` §5. Offline RMSE and even M3's
# year-matched levels say nothing about DYNAMICS: an emulator can hit every annual value and still have
# the wrong memory timescale, the wrong recovery rate, or a memory that is not its own. This probe is the
# emulator side of that question; the C side is `scripts/extract_resilience_reference.py`, whose docstring
# carries the reference basis and the three method choices this file must mirror exactly.
#
# METHOD, mirrored from the reference extractor (a mismatch here silently invents a gap):
#   * DETREND every annual series linearly before the autocorrelation. 2000-2019 is transient (rising CO2,
#     warming) and a pure ramp has lag-1 AC 1 with no memory at all. `ac1_raw` is reported next to it.
#   * n = 20 points, so the estimator is biased LOW by ~(1+3phi)/n ~= 0.16 at phi = 0.75. Both sides use
#     the SAME estimator on the SAME window, so the bias cancels in the comparison; `debias` inverts it
#     for reading against the literature.
#   * The `patch` basis. Each of the C's ~25 patches is an independent realization of the same cell and
#     climate — so the emulator ensemble is ONE MEMBER PER PATCH of the year-2000 `ind` canopy, and the
#     C's between-patch SD of AC is the yardstick a single-trajectory estimate must be scored against.
#     This is not the `readcanopy` MODAL patch: a resilience statistic measured on the densest patch of 25
#     is not the ensemble's statistic, and here the whole point is the ensemble. (The production driver
#     `run_coupled_biomes.jl` ran that modal patch until ADR 0057 moved it onto this same basis.)
#
# WINDOW 2000-2019 — the FULL extent of the historic `ind` table, not the committed 2010-2019 decade. A
# lag-1 AC off 10 annual points has a sampling SE of ~0.32, larger than the entire wet-to-dry gradient it
# is supposed to resolve. The 20-year forcing and the year-2000 canopies are /p/tmp probe inputs built by
#   FIRSTYEAR=2000 LASTYEAR=2019 OUT=/p/tmp/jamirp/M_resilience/forcing scripts/extract_biome_forcing.py
#   YEAR=2000 OUT=/p/tmp/jamirp/M_resilience/canopy scripts/extract_cell_individuals.py
# (the widened window reproduces the committed 2010-2019 fixture BYTE-IDENTICALLY on all five cells).
#
# THE SIX ARMS. The shuffle test (`DEVELOPMENT_PLAN` §5: "verify the emulator's memory is genuinely
# internal, not merely inherited from autocorrelated climate — an AR emulator can cheat this") is only
# decisive with a control that REMOVES the emulator's own recursion, because ADR 0054 established that the
# coupled count is an unanchored AR recursion, and an unanchored AR recursion manufactures autocorrelation
# and slow recovery all by itself. So the battery runs a 3x2 design:
#
#     forcing \ demography |  free (the deployed loop)   pin (no count-space AR)   fonly (no demography)
#     ---------------------+---------------------------------------------------------------------------
#     ordered (real order) |  free0                      pin0                      fonly0
#     shuffled (years iid) |  free1                      pin1                      fonly1
#
#   `pin` resets `s.n_prev` to the cell's `n_init` after every year, so the DRF's explicit count-space AR
#   FEATURE carries nothing from one year to the next. Stated precisely, because it is not a total
#   memory-removal control: the DENSITY update is still recursive (the ratio target/n_prev is applied to
#   the standing roster), so what survives in `pin` is memory reaching the count model through F's canopy
#   features — which is exactly the term being separated out. `fonly` is `slow = nothing` — F's carbon
#   pools are the only memory left at all. Reading the rows:
#     AC(free0) - AC(free1)   memory INHERITED from the climate's own year-to-year sequencing
#     AC(free1)               internal memory under iid-in-year forcing  <- the shuffle test's headline
#     AC(free1) - AC(pin1)    what the count RECURSION contributes to that internal memory
#     AC(fonly1)              F's carbon-pool memory alone (no demography at all)
#
#   A seventh run, `anchor` (`s.n_prev` teacher-forced onto the C's own per-patch ensemble mean, ADR 0054's
#   attribution arm) is included on ordered forcing so the battery is readable next to M3's numbers. It is
#   NOT used as the shuffle-test control: forcing the emulator onto an externally measured series INJECTS
#   that series' memory, which is the opposite of removing memory.
#
# WHAT ONLY `agb` CAN BE SCORED ON: with `slow = nothing` the roster is frozen, so the `fonly` arms have a
# CONSTANT tree count and no count series exists to autocorrelate. That is a property of the control, not
# a result. Counts are therefore scored on the four arms that have demography, biomass on all six.
#
# CONFIG, stated because every number is conditional on it:
#   * `wscal_leafon = true` — passed EXPLICITLY (ADR 0051; the package default stays `false` until line S
#     schedules the two-sided flip).
#   * PINNED `_t8` pair (ADR 0023), contract re-checked at load.
#   * These five cells are IN-SAMPLE for the count DRF, so a miss is a real miss, not extrapolation.
#
# Reimplemented from Bathiany et al. 2024 (doi:10.1111/gcb.17613). `LPJ_resilience` has NO licence, so
# none of its code is copied — only the published method.
#
# Run (CLAUDE.md §2 — never the login node; ~180 MB of artifacts, ~20 min):
#   TIME=03:00:00 scripts/sbatch_julia.sh M-resil --project=. scripts/biome_resilience_probe.jl
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams, FDiffParams
using LPJmLFITEmulator.DRF
using LinearAlgebra: dot
using Printf
using Random
using Statistics

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
const PROBE = get(ENV, "PROBE_DIR", "/p/tmp/jamirp/M_resilience")
const ART = "/p/tmp/jamirp/emulator_global"
const T8_DRF = joinpath(ART, "drf_forest_global_pooled_w20_t8.drf")
const T8_RCOP = joinpath(ART, "recruit_copula_global_pooled_w20_t8.rcop")
const σ = 5.670374419e-8
const Y0, Y1 = 2000, 2019
const NY = Y1 - Y0 + 1
const MAXLAG = 5
const LONGYEARS = 100        # the long-horizon / recovery rollout, by CYCLING the 20-year forcing
const PERTURB_AT = 21        # halve the tree carbon pools at the start of this year of the long rollout
const PERTURB_FRAC = 0.5
const NLONG = 5              # members for the long rollout (stability + recovery need far fewer than AC)

# ── the estimator — a line-for-line port of extract_resilience_reference.py's. Keep them in step; the
#    synthetic AR(1) case that pins both is `resilience_battery_tests.jl`. ─────────────────────────────
"Remove the least-squares linear trend (method choice (a))."
function detrend(x)
    n = length(x)
    t = collect(0.0:(n - 1))
    tc = t .- mean(t)
    slope = dot(x, tc) / dot(tc, tc)
    return x .- mean(x) .- slope .* tc
end

"Biased (divide-by-n) sample ACF at lags 1..maxlag of the mean-removed series; NaN if constant."
function acf(x, maxlag)
    d = x .- mean(x)
    den = dot(d, d)
    den <= 0 && return fill(NaN, maxlag)
    n = length(d)
    return [dot(view(d, (k + 1):n), view(d, 1:(n - k))) / den for k in 1:maxlag]
end

"Resilience statistics of ONE annual series (method choices (a)+(b))."
function ac_stats(x)
    n = length(x)
    d = detrend(x)
    r = acf(d, MAXLAG)
    r1 = r[1]
    return (
        ac1_raw = acf(x, 1)[1], ac1 = r1,
        # Marriott-Pope / Kendall small-sample correction, inverted for phi (method choice (b))
        debias = (r1 + 1 / n) / (1 - 3 / n),
        acf = r, sd = std(d), mean = mean(x),
        cv = mean(x) > 0 ? std(d) / mean(x) : NaN,
        # tau = -1/ln(phi): the AR(1) restoring timescale the perturbation-recovery arm must reproduce
        tau = (isfinite(r1) && 0 < r1 < 1) ? -1 / log(r1) : NaN,
    )
end

"Mean over the ensemble members, ignoring the NaNs a constant member contributes."
nanmean(v) = (w = filter(isfinite, v); isempty(w) ? NaN : mean(w))
nanstd(v) = (w = filter(isfinite, v); length(w) > 1 ? std(w) : NaN)

# ── readers (same layout as scripts/biome_slow_oracle_probe.jl) ───────────────────────────────────────
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

"ALL patches of the cell's `ind` canopy, sorted by patch id — one ensemble member per patch (see the
 PATCH BASIS note in the header). Returns the per-patch (pools, templates) and the patch ids."
function readcanopy_patches(path)
    ind = readcsv(path)
    v(k, r) = parse(Float64, ind[k][r])
    nt(r) = parse(Int, ind["type"][r])
    prows = Dict{Int, Vector{Int}}()
    for r in eachindex(ind["type"])
        (nt(r) <= 6 && v("height", r) > 0) && push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
    end
    pk = sort(collect(keys(prows)))
    return [build_patch(ind, prows[p]) for p in pk], pk
end

function forcings_of(name)
    f = readcsv(joinpath(PROBE, "forcing", "biome_forcing_$(name).csv"))
    tairK = fcol(f, "temp") .+ 273.15
    swd = fcol(f, "swdown"); lwn = fcol(f, "lwnet"); prec = fcol(f, "precip")
    huss = fcol(f, "huss"); co2 = fcol(f, "co2")
    n = length(tairK)
    n == NY * 365 || error("$(name): forcing has $n days, expected $(NY * 365) — rebuild the probe input")
    forc = [
        AtmForcing(;
                swdown = swd[i], lwdown = lwn[i] + σ * tairK[i]^4, tair = tairK[i], qair = huss[i],
                wind = 2.0, psurf = 1.0e5, precip = prec[i], co2 = co2[i]
            ) for i in 1:n
    ]
    return forc, tairK
end

# Start from the ACTIVE calibrated set and flip ONLY `water.wscal_leafon` — a bare `FDiffParams()` would
# silently swap every other constant (the trap `wscal_leafon_probe.jl` documented).
function leafon_params()
    p = FDiff.tebs_params(Float64)
    w = p.water
    fns = fieldnames(typeof(w))
    nt = NamedTuple{fns}(map(f -> getfield(w, f), fns))
    # ⚠ `tree_demand_gate = false` explicitly: the package default flipped to `true` (ADR 0133) and this
    # probe's PUBLISHED panel is on the gate-OFF basis. Taking it by omission would silently rebase every
    # number this probe prints under a label that no longer describes it. Re-measuring on the new default
    # is a deliberate new arm, not a silent substitution.
    # ⚠ `gp_stand_leafon_basis = false` is explicit for the SAME reason, and was written BEFORE that
    # default moved rather than after — which is why the flip (ADR 0137, 2026-08-13) cost this file
    # nothing. SINCE THAT FLIP IT IS AN OPT-OUT: this probe's published panel is on the PRE-flip
    # `gp_sum` basis, which the package no longer runs by default. Say so when quoting a number from it;
    # re-measuring on the new default is a deliberate new arm, not a silent substitution.
    w2 = typeof(w)(; merge(nt, (; wscal_leafon = true, tree_demand_gate = false, gp_stand_leafon_basis = false))...)
    return FDiffParams{Float64}(p.photo, p.tstress, w2, p.resp, p.allom, p.nlambda, p.ω)
end

"Aboveground tree carbon of the patch, gC/m2 — leaf + sapwood + heartwood, nind-weighted, matching the
 C's `agb_tree` basis (`agb_tree.c:25` is already per unit ground area). Below-ground pools excluded."
function patch_agb(core)
    return sum(
        (Float64(p.leaf_c) + Float64(p.sapwood_c) + Float64(p.heartwood_c)) * Float64(p.nind)
            for p in core.pools if !p.is_grass;
        init = 0.0
    )
end

"Halve every tree cohort's carbon pools and re-derive height/crownarea through the model's OWN allometry,
 so the perturbed state is self-consistent rather than a stand of tall, hollow trees."
function perturb_pools!(core, frac)
    for (i, p) in enumerate(core.pools)
        p.is_grass && continue
        lf = Float64(p.leaf_c) * frac
        sw = Float64(p.sapwood_c) * frac
        hw = Float64(p.heartwood_c) * frac
        rt = Float64(p.root_c) * frac
        h = LPJmLFITEmulator.tree_height(core.allom, sw, lf)
        ca = LPJmLFITEmulator.crown_area(core.allom, h)
        core.pools[i] = TreePools{Float64}(
            lf, sw, hw, rt, Float64(p.sapwood_bg_c) * frac, h, ca,
            Float64(p.nind), Float64(p.sla), Float64(p.wooddens), false
        )
    end
    return nothing
end

# ── the C-truth per-year series (the ANCHOR arm's target, and the comparison basis) ───────────────────
const SER = readcsv(joinpath(REFDIR, "M_resilience_reference_series.csv"))
function c_series(name, seed, col)
    out = fill(NaN, NY)
    for i in eachindex(SER["name"])
        (SER["name"][i] == name && parse(Int, SER["seed"][i]) == seed) || continue
        y = parse(Int, SER["year"][i])
        (Y0 <= y <= Y1) && (out[y - Y0 + 1] = parse(Float64, SER[col][i]))
    end
    return out
end
const CREF = readcsv(joinpath(REFDIR, "M_resilience_reference_cells.csv"))
"The C's patch-basis (mean-over-patches) statistic and its between-patch SD, for (name, seed, var)."
function c_stat(name, seed, var, col)
    for i in eachindex(CREF["name"])
        (CREF["name"][i] == name && CREF["var"][i] == var && CREF["basis"][i] == "patch") || continue
        parse(Int, CREF["seed"][i]) == seed || continue
        return parse(Float64, CREF[col][i])
    end
    return NaN
end

# ── artifacts: load ONCE, re-check the frozen contract before trusting either half (ADR 0023) ─────────
t0 = time(); forest = DRF.load_forest(T8_DRF)
@printf("loaded %s in %.1f s — %d trees, nfeat=%d\n", basename(T8_DRF), time() - t0, length(forest.trees), forest.nfeat)
t0 = time(); cop, af, xcop, axnames, cond_cols = DRF.load_copula(T8_RCOP)
@printf("loaded %s in %.1f s — axes=%s, %d cond cols\n", basename(T8_RCOP), time() - t0, axnames, length(cond_cols))
@assert axnames == ["SLA", "Wooddens", "D95max", "minwscal"] "unexpected copula axes: $(axnames)"
@assert cond_cols[1:4] == ["bm_inc_cell", "growth_eff", "water_stress", "soilmoist"] "cond_cols != live_flux_cond head"
@assert forest.nfeat == 15 "count DRF nfeat=$(forest.nfeat), expected 15 (11 head + 4 boundary)"

const CELLS = readcsv(joinpath(REFDIR, "M_cells.csv"))
const NAMES = String.(CELLS["name"])
const LATS = fcol(CELLS, "lat")
const NINIT = fcol(CELLS, "n_init")
const AGE0 = fcol(CELLS, "age0")
const BND = [
    [
            parse(Float64, CELLS["eco_diag_gdd_5"][k]), parse(Float64, CELLS["tas_cold_month"][k]),
            parse(Float64, CELLS["soil_depth"][k]), parse(Float64, CELLS["co2"][k]),
        ] for k in eachindex(NAMES)
]

# ── one ensemble member ────────────────────────────────────────────────────────────────────────────────
# `demog` ∈ (:free, :pin, :anchor, :none); `order` is a permutation of 1:NY repeated to fill `nyears`.
# One `run_coupled_cell` call PER YEAR: the call is re-entrant (it rebuilds `bc_f` from
# `stand_structure_tof(fc)` and all state lives in the mutables), so N one-year calls are the same
# trajectory as one N-year call, and the canopy can be snapshotted annually.
#
# ── THE LEVEL-ANCHOR ARMS (`lvl0`/`lvl1`), opt-in via `ANCHOR=<a>` in the environment (ADR 0103). ─────
# ⚠ `anchor0` above is TEACHER FORCING, a DIFFERENT intervention: it overwrites the AR feature with an
# externally measured series, which injects that series' memory and is why M4 found it degrades the AC.
# The LEVEL ANCHOR touches no feature — it blends the multiplicative roster update toward the count
# model's own absolute target, so it removes a level error without importing anything external. M4's
# caveat ("whatever S lands must be scored on the AC as well as the level") is therefore answered HERE
# and not by `anchor0`. With ANCHOR unset (or 0) this script runs the same 7 arms and writes the same
# committed fixtures, byte-for-byte — `anchor = 0` is the pre-0103 update exactly.
const ANCHOR = parse(Float64, get(ENV, "ANCHOR", "0.0"))
anc_of(tag) = (tag === :lvl0 || tag === :lvl1) ? ANCHOR : 0.0

function run_member(
        k, member, patches; demog::Symbol = :free, order = collect(1:NY),
        nyears::Int = NY, perturb_at::Int = 0, anchor::Float64 = 0.0
    )
    name = NAMES[k]
    forc, tairK = forcings_of(name)
    soil = readsoil(joinpath(REFDIR, "M_soilcolumn_$(name).txt"))
    pools, tmpls = patches[mod1(member, length(patches))]
    core = FDiffFastCore(deepcopy(pools), deepcopy(tmpls), soil, LATS[k]; params = leafon_params())
    clo = SEBEnergyClosure(; t_soil0 = mean(tairK))
    state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
    s = nothing
    if demog !== :none
        rc = RecruitCopula{Float64}(cop, af, xcop, make_recruit_to_pools(axnames), live_flux_cond)
        s = FluxDrivenSlowEmulator(
            core, forest; boundary = copy(BND[k]), n_init = NINIT[k], age0 = AGE0[k],
            seed = member, recruit_copula = rc, anchor = anchor
        )
    end
    # `run_coupled_cell` refuses a ClimBuf without a FluxDrivenSlowEmulator (it writes `s.boundary`), so
    # the `fonly` control runs without one — it has no boundary to refresh.
    cb = s === nothing ? nothing : ClimBuf()
    ctruth = c_series(name, 1, "n_mean")
    nser = fill(NaN, nyears); aser = fill(NaN, nyears); dser = fill(NaN, nyears)
    for y in 1:nyears
        y == perturb_at && perturb_pools!(core, PERTURB_FRAC)
        sy = order[mod1(y, length(order))]                 # the SOURCE year this step replays
        rng = ((sy - 1) * 365 + 1):(sy * 365)
        run_coupled_cell(core, clo, state, view(forc, rng); slow = s, climbuf = cb, days_per_year = 365)
        if s !== nothing
            demog === :pin && (s.n_prev = NINIT[k])                              # no count-space AR state
            demog === :anchor && !isnan(ctruth[sy]) && (s.n_prev = ctruth[sy])   # ADR 0054's attribution
            nser[y] = s.target_history[end]
        end
        aser[y] = patch_agb(core)
        dser[y] = sum(Float64(p.nind) for p in core.pools if !p.is_grass; init = 0.0)
    end
    resid = s === nothing ? 0.0 : maximum(abs, s.resid_history)
    return (; n = nser, agb = aser, dens = dser, resid)
end

# ── PART 1 — the 3x2 shuffle design + the anchor arm, over the 25-member patch ensemble ───────────────
# One permutation per member, SHARED across cells, so a member index means the same climate realization
# everywhere and cross-cell differences are not confounded by a different shuffle.
const ORDERED = collect(1:NY)
shuffled_for(member) = randperm(MersenneTwister(90210 + member), NY)

const BASE_ARMS = (
    (:free0, :free, false), (:free1, :free, true),
    (:pin0, :pin, false), (:pin1, :pin, true),
    (:fonly0, :none, false), (:fonly1, :none, true),
    (:anchor0, :anchor, false),
)
# `lvl0`/`lvl1` are the LEVEL ANCHOR on ordered / shuffled forcing. Both are needed: `lvl1` next to `free1`
# and `pin1` is what says whether the anchor keeps the internal memory the shuffle test is measuring.
const ARMS = ANCHOR > 0 ? (BASE_ARMS..., (:lvl0, :free, false), (:lvl1, :free, true)) : BASE_ARMS

@printf("\n=== running the battery: %d cells x %d arms x <=25 members x %d years ===\n", length(NAMES), length(ARMS), NY)
results = Dict{Tuple{String, Symbol}, Any}()
patchsets = Dict{String, Any}()
for (k, name) in enumerate(NAMES)
    ps, pk = readcanopy_patches(joinpath(PROBE, "canopy", "M_individuals_$(name)_2000.csv"))
    patchsets[name] = ps
    @printf("%-22s %d patches in the year-%d canopy\n", name, length(ps), Y0)
    for (tag, demog, shuf) in ARMS
        t = time()
        runs = [
            run_member(
                    k, m, ps; demog = demog, anchor = anc_of(tag),
                    order = shuf ? shuffled_for(m) : ORDERED
                ) for m in 1:length(ps)
        ]
        results[(name, tag)] = runs
        @printf("    %-8s %5.1f s   max|carbon resid| = %.2e\n", tag, time() - t, maximum(r.resid for r in runs))
        flush(stdout)   # Julia block-buffers stdout to a file; without this the log is empty until exit
    end
end

# ── PART 2 — (a) AC-vs-climate: the emulator's lag-1 AC against the C's, in between-patch SDs ─────────
@printf("\n=== (a) LAG-1 AUTOCORRELATION vs the C oracle — patch basis, detrended, %d-%d ===\n", Y0, Y1)
@printf("(the emulator ensemble is one member per patch of the year-%d canopy; C = seed1)\n\n", Y0)
@printf(
    "%-22s %-4s %-8s %8s %8s %8s %8s %8s %8s\n",
    "cell", "var", "arm", "E_ac1", "E_msd", "C_ac1", "C_psd", "|d|/psd", "E_tau"
)
acrows = []
for name in NAMES, var in (:n, :agb)
    for (tag, demog, _) in ARMS
        (var === :n && demog === :none) && continue     # a frozen roster has no count series (header)
        st = [ac_stats(getfield(r, var)) for r in results[(name, tag)]]
        e_ac1 = nanmean([x.ac1 for x in st]); e_msd = nanstd([x.ac1 for x in st])
        c_ac1 = c_stat(name, 1, String(var), "ac1_detr")
        c_psd = c_stat(name, 1, String(var), "ac1_detr_psd")
        push!(
            acrows, (
                name = name, var = String(var), arm = String(tag), e_ac1 = e_ac1, e_msd = e_msd,
                e_raw = nanmean([x.ac1_raw for x in st]), e_debias = nanmean([x.debias for x in st]),
                e_tau = nanmean([x.tau for x in st]), e_cv = nanmean([x.cv for x in st]),
                e_mean = nanmean([x.mean for x in st]), c_ac1 = c_ac1, c_psd = c_psd,
                nmember = length(st),
            )
        )
        @printf(
            "%-22s %-4s %-8s %8.3f %8.3f %8.3f %8.3f %8.1f %8.2f\n",
            name, String(var), String(tag), e_ac1, e_msd, c_ac1, c_psd, abs(e_ac1 - c_ac1) / c_psd, nanmean([x.tau for x in st])
        )
    end
end
@printf("\nE_msd = the SD of ac1 ACROSS members = the emulator's own between-patch spread; C_psd is the C's.\n")
@printf("|d|/psd is the miss in units of the C's between-patch SD — the spread a single 20-year patch\n")
@printf("series samples from, which is the right yardstick for a one-trajectory estimate.\n")

# ── PART 3 — (c) THE SHUFFLE TEST + the memory decomposition ──────────────────────────────────────────
@printf("\n=== (c) SHUFFLE TEST — is the memory INTERNAL or inherited from autocorrelated climate? ===\n\n")
@printf(
    "%-22s %-4s %8s %8s %8s %8s %8s %8s %9s\n",
    "cell", "var", "free0", "free1", "pin1", "fonly1", "inherit", "recursion", "C_ac1"
)
shufrows = []
acget(name, var, tag) = (
    i = findfirst(r -> r.name == name && r.var == String(var) && r.arm == String(tag), acrows);
    i === nothing ? NaN : acrows[i].e_ac1
)
for name in NAMES, var in (:n, :agb)
    f0 = acget(name, var, :free0); f1 = acget(name, var, :free1)
    p1 = acget(name, var, :pin1); o1 = var === :n ? NaN : acget(name, var, :fonly1)
    c1 = c_stat(name, 1, String(var), "ac1_detr")
    push!(
        shufrows, (
            name = name, var = String(var), free0 = f0, free1 = f1, pin1 = p1, fonly1 = o1,
            inherited = f0 - f1, recursion = f1 - p1, c_ac1 = c1,
        )
    )
    @printf(
        "%-22s %-4s %8.3f %8.3f %8.3f %8.3f %8.3f %9.3f %9.3f\n",
        name, String(var), f0, f1, p1, o1, f0 - f1, f1 - p1, c1
    )
end
@printf("\ninherit = AC(ordered) - AC(shuffled): memory inherited from the climate's year-to-year sequencing.\n")
@printf("recursion = AC(free,shuffled) - AC(pin,shuffled): what the unanchored count AR adds by itself.\n")
@printf("PASS for 'the memory is internal' = free1 stays high after the forcing's own sequencing is\n")
@printf("destroyed. PASS for 'it is not merely the AR recursion' = pin1 (and fonly1) stay high too.\n")

# ── PART 4 — (b) RECOVERY RATE + (d) LONG-HORIZON STABILITY / AC-GAP ──────────────────────────────────
@printf("\n=== (b)+(d) %d-year cycled rollout: pool-perturbation recovery and long-horizon stability ===\n", LONGYEARS)
@printf("(the 20-year forcing is CYCLED; the perturbation halves every tree carbon pool at year %d)\n\n", PERTURB_AT)
@printf(
    "%-22s %8s %8s %9s %9s %9s %8s %8s %8s\n",
    "cell", "tau_rec", "r2", "drift", "min/init", "max/init", "ac1_l50", "osc", "resid"
)
longrows = []
for (k, name) in enumerate(NAMES)
    ps = patchsets[name]
    nm = min(NLONG, length(ps))
    ctrl = [run_member(k, m, ps; demog = :free, nyears = LONGYEARS) for m in 1:nm]
    pert = [run_member(k, m, ps; demog = :free, nyears = LONGYEARS, perturb_at = PERTURB_AT) for m in 1:nm]
    # RECOVERY: the perturbed run's DEPARTURE from its own control, relaxing back toward 0. Fitting
    # log|delta| against the year is the e-folding time; a positive tau means it recovers at all.
    taus = Float64[]; r2s = Float64[]
    for m in 1:nm
        c = ctrl[m].agb; p = pert[m].agb
        yy = Float64[]; ll = Float64[]
        for y in PERTURB_AT:LONGYEARS
            d = abs(c[y] - p[y]) / max(c[y], 1.0e-12)
            (d > 1.0e-4 && isfinite(d)) || continue      # below 1e-4 the departure is numerical noise
            push!(yy, Float64(y - PERTURB_AT)); push!(ll, log(d))
        end
        if length(yy) >= 5
            ybar = mean(yy); lbar = mean(ll)
            sl = dot(yy .- ybar, ll .- lbar) / dot(yy .- ybar, yy .- ybar)
            pred = lbar .+ sl .* (yy .- ybar)
            ss = sum((ll .- lbar) .^ 2)
            push!(taus, sl < 0 ? -1 / sl : NaN)
            push!(r2s, ss > 0 ? 1 - sum((ll .- pred) .^ 2) / ss : NaN)
        end
    end
    # STABILITY: bounds relative to the initial state, net drift, the AC of the last 50 years, and an
    # oscillation index = the fraction of years whose first difference flips sign (0.5 = white noise,
    # -> 1 = a two-year flip-flop, the stiff carbon+population failure mode LPJ_resilience flags).
    a = ctrl[1].agb
    dif = diff(a)
    osc = count(i -> sign(dif[i]) != sign(dif[i - 1]), 2:length(dif)) / (length(dif) - 1)
    l50 = ac_stats(a[(LONGYEARS - 49):LONGYEARS])
    row = (
        name = name, tau_rec = nanmean(taus), r2 = nanmean(r2s),
        drift = mean(a[(LONGYEARS - 19):LONGYEARS]) / mean(a[1:20]),
        minrel = minimum(a) / a[1], maxrel = maximum(a) / a[1],
        ac1_last50 = l50.ac1, osc = osc, finite = all(isfinite, a) && all(>(0.0), a),
        resid = maximum(r.resid for r in ctrl), nmember = nm,
        ncount_end = ctrl[1].dens[end], ncount_init = ctrl[1].dens[1],
    )
    push!(longrows, row)
    @printf(
        "%-22s %8.2f %8.3f %9.3f %9.3f %9.3f %8.3f %8.3f %8.1e\n",
        name, row.tau_rec, row.r2, row.drift, row.minrel, row.maxrel, row.ac1_last50, osc, row.resid
    )
end
@printf("\ntau_rec = e-folding years of the perturbed run's departure from its own control (agb); r2 is the\n")
@printf("log-linear fit quality — a low r2 means the relaxation is NOT a single exponential. drift =\n")
@printf("mean(last 20 yr)/mean(first 20 yr) of a CYCLED forcing, so 1.00 is the no-drift answer.\n")
@printf("osc = fraction of years whose first difference flips sign (0.5 = white noise, ->1 = flip-flop).\n")

# ── PART 4b — THE LEVEL ANCHOR (ADR 0103): does it fix the level WITHOUT costing the memory? ─────────
# Only runs when ANCHOR>0. Two questions, and they are separate:
#   MEMORY  — lvl1 vs free1/pin1 on shuffled forcing. If the anchor were destroying internal memory the
#             way teacher forcing does, lvl1 would collapse toward pin1. It must not.
#   LEVEL   — the 100-year CYCLED rollout's `drift` (mean of last 20 yr / mean of first 20 yr). The
#             forcing repeats, so the honest answer is 1.00; the unanchored loop's departure from 1.00
#             is the drift the anchor exists to remove.
if ANCHOR > 0
    @printf("\n=== (e) LEVEL ANCHOR a=%.2f — memory kept? (shuffled forcing, lag-1 AC) ===\n\n", ANCHOR)
    @printf(
        "%-22s %-4s %8s %8s %8s %8s %9s %9s\n",
        "cell", "var", "free1", "pin1", "lvl1", "C_ac1", "lvl-free", "lvl-pin"
    )
    for name in NAMES, var in (:n, :agb)
        f1 = acget(name, var, :free1); p1 = acget(name, var, :pin1); l1 = acget(name, var, :lvl1)
        c1 = c_stat(name, 1, String(var), "ac1_detr")
        @printf(
            "%-22s %-4s %8.3f %8.3f %8.3f %8.3f %9.3f %9.3f\n",
            name, String(var), f1, p1, l1, c1, l1 - f1, l1 - p1
        )
    end
    # The headline. `lvl-free` alone cannot decide this: the free arm is NOT the truth, and it happens to
    # sit ABOVE the C's AC in almost every pair, so a change that lowers the AC moves TOWARD the oracle
    # even though it shows as a negative `lvl-free`. The decidable statistic is the distance to the C.
    efree = Float64[]; epin = Float64[]; elvl = Float64[]
    for name in NAMES, var in (:n, :agb)
        c1 = c_stat(name, 1, String(var), "ac1_detr")
        push!(efree, abs(acget(name, var, :free1) - c1))
        push!(epin, abs(acget(name, var, :pin1) - c1))
        push!(elvl, abs(acget(name, var, :lvl1) - c1))
    end
    @printf(
        "\nMEAN |AC - C_AC| over the %d cell-variable pairs:  free1 %.4f   pin1 %.4f   lvl1 %.4f\n",
        length(efree), mean(efree), mean(epin), mean(elvl)
    )
    @printf(
        "anchored CLOSER to the oracle in %d of %d pairs; mean error %s\n",
        count(elvl .< efree), length(efree), mean(elvl) < mean(efree) ? "IMPROVED" : "WORSENED"
    )
    # ADR 0104 §7 CLAUSE 2, evaluated in-script so the verdict is the machine's and not the reader's
    # (the `residual-diagnosis` rule this line earned on 2026-08-06). Two parts, both stated against the
    # ORACLE and not against the free arm: the mean must not get worse, and no SINGLE pair may move away
    # from the C by more than 0.05. The per-pair part is the new one — §6's run only checked the mean.
    c2_pair_tol = 0.05
    c2_mean = mean(elvl) <= mean(efree)
    c2_worst, c2_which = findmax(elvl .- efree)
    c2_pair = c2_worst <= c2_pair_tol
    @printf(
        "\n--- ADR 0104 §7 CLAUSE 2 (memory) ---\n  mean |AC-C| no worse than free : %s (%.4f vs %.4f)\n",
        c2_mean ? "PASS" : "FAIL", mean(elvl), mean(efree)
    )
    @printf(
        "  no pair moves away from C by >%.2f : %s (worst +%.4f, pair %d of %d)\n  CLAUSE 2: %s\n",
        c2_pair_tol, c2_pair ? "PASS" : "FAIL", c2_worst, c2_which, length(elvl),
        (c2_mean && c2_pair) ? "PASS" : "FAIL"
    )
    @printf("\nlvl-free ~ 0 => the anchor left the internal memory alone. lvl-pin >> 0 => it did NOT collapse\n")
    @printf("to the no-recursion control. A LARGE NEGATIVE lvl-free is the failure mode to look for: it would\n")
    @printf("mean the anchor bought its level fix by flattening the emulator's own year-to-year dynamics.\n")

    @printf("\n=== (f) LEVEL ANCHOR a=%.2f — %d-year CYCLED drift (honest answer = 1.00) ===\n\n", ANCHOR, LONGYEARS)
    @printf(
        "%-22s %9s %9s %9s %9s %9s %9s %10s\n",
        "cell", "drift_fr", "drift_an", "ac50_fr", "ac50_an", "osc_fr", "osc_an", "resid_an"
    )
    for (k, name) in enumerate(NAMES)
        ps = patchsets[name]
        actrl = [
            run_member(k, m, ps; demog = :free, nyears = LONGYEARS, anchor = ANCHOR)
                for m in 1:min(NLONG, length(ps))
        ]
        aa = actrl[1].agb
        adif = diff(aa)
        aosc = count(i -> sign(adif[i]) != sign(adif[i - 1]), 2:length(adif)) / (length(adif) - 1)
        i = findfirst(r -> r.name == name, longrows)
        fr = longrows[i]
        @printf(
            "%-22s %9.3f %9.3f %9.3f %9.3f %9.3f %9.3f %10.1e\n",
            name, fr.drift, mean(aa[(LONGYEARS - 19):LONGYEARS]) / mean(aa[1:20]),
            fr.ac1_last50, ac_stats(aa[(LONGYEARS - 49):LONGYEARS]).ac1, fr.osc, aosc,
            maximum(r.resid for r in actrl)
        )
        flush(stdout)
    end
    @printf("\ndrift_an closer to 1.00 than drift_fr = the anchor removed long-horizon level drift under a\n")
    @printf("forcing that itself has none. ac50/osc are the guard against buying that with dead dynamics.\n")
    @printf("resid_an is the carbon-handoff closure in the anchored arm — it must stay at the free arm's level.\n")
end

# ── PART 5 — write the committed fixture ──────────────────────────────────────────────────────────────
# ⚠ When the opt-in level-anchor arms are on, the battery carries EXTRA rows, so writing them into the
# committed fixtures would silently move line M's baselines from line S's worktree. Redirect to scratch.
const FIXDIR = ANCHOR > 0 ? get(ENV, "FIXDIR", "/p/tmp/jamirp/S_anchor_resilience") : REFDIR
ANCHOR > 0 && mkpath(FIXDIR)
ANCHOR > 0 && @printf("\n[level-anchor arms ON] fixtures redirected to %s — committed baselines untouched\n", FIXDIR)
acout = joinpath(FIXDIR, "M_resilience_battery.csv")
open(acout, "w") do io
    println(io, "# The COUPLED emulator's resilience battery vs the C oracle, 5 biome cells, $(Y0)-$(Y1),")
    println(io, "# historic, pinned _t8 + wscal_leafon=true. One row per (cell, variable, ARM); the arms are")
    println(io, "# the 3x2 shuffle design + the ADR-0054 anchor arm — see scripts/biome_resilience_probe.jl.")
    println(io, "# E_* are means over the ensemble (ONE MEMBER PER PATCH of the year-$(Y0) canopy) and e_msd")
    println(io, "# is their SD; C_ac1/C_psd are the C's patch-basis mean and between-patch SD from")
    println(io, "# M_resilience_reference_cells.csv (seed1). Series are DETRENDED before every AC and both")
    println(io, "# sides use the identical n=$(NY) estimator, so its small-sample bias cancels in E-vs-C.")
    println(io, "# `n` is the count DRF's per-patch prediction; `agb` is leaf+sapwood+heartwood, nind-weighted.")
    println(io, "name,var,arm,nmember,e_ac1,e_msd,e_ac1_raw,e_debias,e_tau,e_cv,e_mean,c_ac1,c_psd,d_over_psd")
    for r in acrows
        @printf(
            io, "%s,%s,%s,%d,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f\n",
            r.name, r.var, r.arm, r.nmember, r.e_ac1, r.e_msd, r.e_raw, r.e_debias, r.e_tau, r.e_cv,
            r.e_mean, r.c_ac1, r.c_psd, abs(r.e_ac1 - r.c_ac1) / r.c_psd
        )
    end
end
@printf("\nwrote %s (%d rows)\n", acout, length(acrows))

lout = joinpath(FIXDIR, "M_resilience_battery_longrun.csv")
open(lout, "w") do io
    println(io, "# The COUPLED emulator's $(LONGYEARS)-year CYCLED-forcing rollout: pool-perturbation recovery")
    println(io, "# (halve every tree carbon pool at year $(PERTURB_AT), frac=$(PERTURB_FRAC)) and long-horizon")
    println(io, "# stability. tau_rec = e-folding years of the perturbed run's departure from its own control")
    println(io, "# in agb; r2 = the log-linear fit quality. drift = mean(last 20)/mean(first 20) — the forcing")
    println(io, "# is cyclic, so 1.00 is the no-drift answer. osc = fraction of years whose first difference")
    println(io, "# flips sign (0.5 = white noise, ->1 = the two-year flip-flop LPJ_resilience flags).")
    println(io, "# Emitted by scripts/biome_resilience_probe.jl.")
    println(io, "name,nmember,tau_rec,r2,drift,min_over_init,max_over_init,ac1_last50,osc,finite,resid,n_init,n_end")
    for r in longrows
        @printf(
            io, "%s,%d,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%s,%.3e,%.6f,%.6f\n",
            r.name, r.nmember, r.tau_rec, r.r2, r.drift, r.minrel, r.maxrel, r.ac1_last50, r.osc,
            r.finite, r.resid, r.ncount_init, r.ncount_end
        )
    end
end
@printf("wrote %s (%d rows)\n", lout, length(longrows))

sout = joinpath(FIXDIR, "M_resilience_battery_shuffle.csv")
open(sout, "w") do io
    println(io, "# The SHUFFLE TEST (DEVELOPMENT_PLAN §5) decomposed. free0/free1 = the deployed coupled loop")
    println(io, "# on ordered / year-shuffled forcing; pin1 = the same with `s.n_prev` reset to n_init every")
    println(io, "# year, so the DRF's explicit count-space AR FEATURE carries nothing (not a total memory")
    println(io, "# removal — the density update stays recursive); fonly1 = slow=nothing (F's carbon pools are")
    println(io, "# the only memory left at all). inherited = free0-free1 is memory taken from the climate's own")
    println(io, "# sequencing; recursion = free1-pin1 is what the unanchored count AR (ADR 0054) adds alone.")
    println(io, "# A frozen roster has no count series, so fonly1 is NaN for var=n — a property of the")
    println(io, "# control, not a result. Emitted by scripts/biome_resilience_probe.jl.")
    println(io, "name,var,free0,free1,pin1,fonly1,inherited,recursion,c_ac1")
    for r in shufrows
        @printf(
            io, "%s,%s,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f\n",
            r.name, r.var, r.free0, r.free1, r.pin1, r.fonly1, r.inherited, r.recursion, r.c_ac1
        )
    end
end
@printf("wrote %s (%d rows)\n", sout, length(shufrows))
@printf("\nDONE — the verdicts are PART 2's |d|/psd (is the memory the RIGHT size), PART 3's free1 vs pin1\n")
@printf("(is it internal, and is it more than the AR recursion), and PART 4's drift/osc/tau_rec.\n")
