#!/usr/bin/env julia
# ── M3 S-SIDE — the coupled S+F+E demography/trait probe vs the C oracle, 5 biome cells ──────────────
#
# The S-side twin of `scripts/biome_fdiff_oracle_probe.jl` (ADR 0053, the F side). That one held demography
# OUT (`slow=nothing`) so a flux gap could not come from the canopy; this one puts Component S back IN and
# asks the P3 question: does the COUPLED loop reproduce the C's per-cell tree numbers and the standing
# community's trait distribution — measured against the seed1-vs-seed2 noise floor, which is the irreducible
# error no environment-conditioned emulator can beat.
#
# REFERENCE BASIS (`residual-diagnosis` §1; the four ADR-0053 checks are enforced on the reference side by
# `scripts/extract_biome_slow_oracle.py` — read that docstring, it is the authority). What matters HERE:
#
#   * COUNTS are PER-PATCH.  `s.target_history[y]` is the count DRF's prediction of `n_living` for ONE
#     (Cell, Patch, Year) — the exact quantity it was trained on — so it is compared to the C's per-patch
#     ensemble MEAN (`n_mean` in M_slow_oracle_counts.csv), never to the per-cell total (~25x larger) and
#     never to the driver's own modal patch (which the F side measured at 1.12-1.72x the ensemble).
#   * The INITIAL CANOPY is that modal patch (`readcanopy`, unchanged from the production driver on purpose
#     — STATE.md NEXT item 4 keeps the ensemble lift as its own deliberate change). So year 0 already starts
#     ABOVE the ensemble mean and that offset is reported, not hidden: `n0_modal` vs `n_mean(2010)`.
#   * TRAITS: only SLA and Wooddens reach `TreePools` (`make_recruit_to_pools` — D95max/minwscal are drawn
#     and validated but have no per-tree consumer), so only those two can be scored on a coupled community.
#     Scored nind-WEIGHTED, because the roster is merged cohorts carrying density, not individual stems.
#   * YEAR-MATCHED. Per-year rows, never a window mean: a count drifting 0.8x -> 1.7x has a 10-yr mean of 1.
#
# CONFIGURATION, stated because every number below is conditional on it:
#   * `wscal_leafon = true`  — passed EXPLICITLY (ADR 0051; the default stays `false` until line S schedules
#     the two-sided flip). Without it the coupled `water_stress` at Hainich is 0.305 vs a C truth of 0.0014.
#   * PINNED `_t8` pair (ADR 0023) — re-checked at load: `nfeat`, `colnames` vs `flux_feature_vector`, and
#     `cond_cols` vs `live_flux_cond`. A `t9` `.rcop` exists on /p/tmp but has NO matching `.drf`, so it is
#     a half-published pair and deliberately NOT adopted.
#   * These five cells ARE in the `_t8` training population ⇒ every number here is IN-SAMPLE for the count
#     DRF. Line S's held-out-CELL OOS (R^2 0.9824) is the out-of-sample statement; this probe's contribution
#     is the COUPLED closed loop, which offline scoring cannot see. A miss here is therefore a real miss.
#
# Run (CLAUDE.md §2 — never the login node; ~180 MB of artifacts, ~4.5 s just to deserialize):
#   TIME=01:00:00 scripts/sbatch_julia.sh M-slworacle --project=. scripts/biome_slow_oracle_probe.jl
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams, FDiffParams
using LPJmLFITEmulator.DRF
using Statistics, Printf

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
const σ = 5.670374419e-8
const Y0, Y1 = 2010, 2019
const NYEAR = Y1 - Y0 + 1
const ART = "/p/tmp/jamirp/emulator_global"
const T8_DRF = joinpath(ART, "drf_forest_global_pooled_w20_t8.drf")
const T8_RCOP = joinpath(ART, "recruit_copula_global_pooled_w20_t8.rcop")
const QS = (0.05, 0.25, 0.5, 0.75, 0.95)
# The `FluxDrivenSlowEmulator` default, and correct for the pinned `_t8` artifacts: it is a
# property of the ARTIFACT's training run (ADR 0103 §4), and these tables come from a
# `par/lpjparam_fit.js` with `patcharea = 225.0`. Stock LPJmL-FIT uses 100.0.
const PATCH_AREA = 225.0

# ── readers (same layout as scripts/run_coupled_biomes.jl / wscal_leafon_probe.jl) ────────────────────
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

"The production driver's MODAL-patch canopy. Returns the pools/templates AND the patch's stem count, so the
 modal-vs-ensemble offset (the F side's 1.12-1.72x) is reported rather than silently carried."
function readcanopy(path)
    ind = readcsv(path)
    v(k, r) = parse(Float64, ind[k][r])
    nt(r) = parse(Int, ind["type"][r])
    prows = Dict{Int, Vector{Int}}()
    for r in eachindex(ind["type"])
        (nt(r) <= 6 && v("height", r) > 0) && push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
    end
    rows = prows[argmax(Dict(k => length(vv) for (k, vv) in prows))]
    npatch = length(prows)
    nmean = sum(length(vv) for (_, vv) in prows) / npatch
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
    return pools, tmpls, length(rows), nmean
end

"Build one patch's (pools, templates) from already-parsed `ind` rows — the body `readcanopy` uses, factored
 out so the ensemble reader below shares it exactly (ADR 0105)."
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

"ALL patches of the cell's `ind` canopy, sorted by patch id — ONE ENSEMBLE MEMBER PER PATCH. This is the
 basis the C itself reports (ADR 0053/0057) and the basis the count DRF was trained on; the modal reader
 above is kept beside it so ADR 0104's published modal numbers stay reproducible in the same run."
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

# Start from the ACTIVE calibrated set (`tebs_params`) and flip ONLY `water.wscal_leafon` — building a bare
# `FDiffParams()` would silently swap every other constant (the trap `wscal_leafon_probe.jl` documented).
function leafon_params()
    p = FDiff.tebs_params(Float64)
    w = p.water
    fns = fieldnames(typeof(w))
    nt = NamedTuple{fns}(map(f -> getfield(w, f), fns))
    w2 = typeof(w)(; merge(nt, (; wscal_leafon = true))...)
    return FDiffParams{Float64}(p.photo, p.tstress, w2, p.resp, p.allom, p.nlambda, p.ω)
end

"nind-weighted quantiles of `getter` over the LIVE tree cohorts (the roster is merged cohorts, not stems)."
function community_q(pools, getter)
    xs = Float64[]; ws = Float64[]
    for p in pools
        (p.is_grass || p.nind <= 0) && continue
        push!(xs, getter(p)); push!(ws, p.nind)
    end
    isempty(xs) && return fill(NaN, length(QS))
    ord = sortperm(xs); xs = xs[ord]; ws = ws[ord]; cw = cumsum(ws) ./ sum(ws)
    return [xs[something(findfirst(>=(q), cw), length(xs))] for q in QS]
end

# ── the C-truth tables ───────────────────────────────────────────────────────────────────────────────
const CNT = readcsv(joinpath(REFDIR, "M_slow_oracle_counts.csv"))
const TRT = readcsv(joinpath(REFDIR, "M_slow_oracle_traits.csv"))

"Per-year `col` for (name, seed) from the counts table, ordered Y0..Y1."
function cnt_series(name, seed, col)
    out = fill(NaN, NYEAR)
    for i in eachindex(CNT["name"])
        CNT["name"][i] == name || continue
        parse(Int, CNT["seed"][i]) == seed || continue
        y = parse(Int, CNT["year"][i])
        (Y0 <= y <= Y1) && (out[y - Y0 + 1] = parse(Float64, CNT[col][i]))
    end
    return out
end

"Per-year quantile vector of `axis` for (name, seed), ordered Y0..Y1 — a NYEAR-vector of 5-vectors."
function trt_series(name, seed, axis)
    out = [fill(NaN, length(QS)) for _ in 1:NYEAR]
    for i in eachindex(TRT["name"])
        (TRT["name"][i] == name && TRT["axis"][i] == axis) || continue
        parse(Int, TRT["seed"][i]) == seed || continue
        y = parse(Int, TRT["year"][i])
        (Y0 <= y <= Y1) || continue
        out[y - Y0 + 1] = [parse(Float64, TRT[string("q", lpad(round(Int, q * 100), 2, '0'))][i]) for q in QS]
    end
    return out
end

# ── artifacts: load ONCE, re-check the frozen contract before trusting either half (ADR 0023) ────────
t0 = time(); forest = DRF.load_forest(T8_DRF)
@printf("loaded %s in %.1f s — %d trees, nfeat=%d\n", basename(T8_DRF), time() - t0, length(forest.trees), forest.nfeat)
t0 = time(); cop, af, xcop, axnames, cond_cols = DRF.load_copula(T8_RCOP)
@printf(
    "loaded %s in %.1f s — axes=%s, %d cond cols, %d axis forests\n",
    basename(T8_RCOP), time() - t0, axnames, length(cond_cols), length(af)
)
@assert axnames == ["SLA", "Wooddens", "D95max", "minwscal"] "unexpected copula axes: $(axnames)"
@assert cond_cols[1:4] == ["bm_inc_cell", "growth_eff", "water_stress", "soilmoist"] "cond_cols != live_flux_cond head"
@assert all(fo -> fo.nfeat == length(cond_cols), af) "an axis forest's nfeat != length(cond_cols)"
@assert forest.nfeat == 15 "count DRF nfeat=$(forest.nfeat), expected 15 (11 head + 4 boundary)"

cells = readcsv(joinpath(REFDIR, "M_cells.csv"))
names = String.(cells["name"]); lats = fcol(cells, "lat")
n_inits = fcol(cells, "n_init"); age0s = fcol(cells, "age0")
bnds = [
    [
            parse(Float64, cells["eco_diag_gdd_5"][k]), parse(Float64, cells["tas_cold_month"][k]),
            parse(Float64, cells["soil_depth"][k]), parse(Float64, cells["co2"][k]),
        ] for k in eachindex(names)
]

# ── run: one YEAR per `run_coupled_cell` call so the community can be snapshotted annually. The call is
#    re-entrant (it rebuilds `bc_f` from `stand_structure_tof(fc)` and all state lives in the mutables), so
#    10 one-year calls are the same trajectory as one ten-year call. ───────────────────────────────────
struct CellRun
    name::String
    target::Vector{Float64}          # s.target_history — the per-patch count the DRF predicted, per year
    dens::Vector{Float64}            # Σ nind over TREE cohorts after each year's commit
    feats::Vector{Vector{Float64}}   # s.feature_history — the full 15-vector the DRF was fed, per year
    sla::Vector{Vector{Float64}}     # nind-weighted community quantiles, per year
    wd::Vector{Vector{Float64}}
    n0_modal::Int                    # stems in the modal patch the driver starts from
    n0_ens::Float64                  # mean stems per patch in the same 2010 ind file
    resid::Float64                   # max |carbon handoff residual|
    cscale::Float64                  # initial Σ vegc_full_ind·nind — the 1e-6·C_scale gate's scale
    anchor::Float64                  # ADR 0103 `anchor` this arm ran with (0 = the pre-0103 recursion)
end

# `flux_feature_vector` positions (manifest `colnames` of the pinned _t8 table, re-asserted at load):
#   1 bm_inc_cell  2 growth_eff  3 water_stress  4 soilmoist  5 hmean  6 hmax  7 agb  8 lai  9 fpc
#   10 age_mean  11 n_prev  ‖ 12-15 boundary
const I_WS, I_AGB, I_LAI, I_FPC, I_NPREV = 3, 7, 8, 9, 11

# ── ARM B — TEACHER-FORCED `n_prev` (the S-side of `fdiff-validate`'s kernel-isolation drive). ────────
# The coupled count is a RECURSION: the DRF's own prediction becomes next year's `n_prev` feature, so a
# small yearly bias compounds. In the TRAINING table `n_prev` is the C's OWN previous `n_living`
# (`build_slow_runtime_table.py:572`), never a prediction — so a free-running rollout is already off that
# basis by construction. Overwriting `s.n_prev` with the C's per-patch ensemble mean after each year puts
# the feature back on its trained basis while leaving F's canopy features exactly as they are, which splits
# the free-running error into:
#     ARM A (free) − ARM B (forced)  =  the AR-recursion amplification
#     ARM B (forced) − 1             =  what the count model does on F's own drifting canopy features
# It is a DRIVER-level intervention (`s.n_prev` is a public mutable field); nothing in `slow.jl` is touched.
#
# ── ARM C — the LEVEL ANCHOR (`anchor = a`, ADR 0103). ────────────────────────────────────────────────
# Line S shipped the anchor opt-in and default-off, and PRE-REGISTERED the criterion for flipping the
# default as a measurement on THIS harness (ADR 0103 §6 / `lines/M/STATE.md` ▶ ACTION FOR M). It is a
# different intervention from arm B and the distinction is the whole point: arm B replaces the count-space
# AR feature `s.n_prev` with the C's truth (it needs the answer to work, so it can only ever be an
# attribution arm, never a shippable model); the anchor uses NO external information — it blends the AR
# ratio with the ratio that would land the stand on the count DRF's OWN absolute prediction,
# `D_want = target/patch_area`. Arm C is therefore a candidate default; arm B is a diagnostic bound.
# `a = 0.5` is the value ADR 0103 §3b's non-monotone convergence curve selects for a 10-year horizon
# (retention 0.24 at yr 10 vs 0.62 at `a = 0.1`); `a = 0.1` is the proposed steady-state default and is run
# beside it because that is the value the flip would actually install.
function run_cell(k; teacher::Bool = false, anchor::Float64 = 0.0)
    name = names[k]
    forc, tairK = forcings_of(name)
    soil = readsoil(joinpath(REFDIR, "M_soilcolumn_$(name).txt"))
    pools, tmpls, n0_modal, n0_ens = readcanopy(joinpath(REFDIR, "M_individuals_$(name)_2010.csv"))
    core = FDiffFastCore(pools, tmpls, soil, lats[k]; params = leafon_params())
    clo = SEBEnergyClosure(; t_soil0 = mean(tairK))
    state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
    rc = RecruitCopula{Float64}(cop, af, xcop, make_recruit_to_pools(axnames), live_flux_cond)
    s = FluxDrivenSlowEmulator(
        core, forest; boundary = copy(bnds[k]), n_init = n_inits[k], age0 = age0s[k],
        seed = 1, recruit_copula = rc, anchor = anchor
    )
    # `patch_area` is left at its 225.0 m² default DELIBERATELY: ADR 0103 §4 makes it a property of the
    # ARTIFACT's training run, and the pinned `_t8` tables come from this tree's `par/lpjparam_fit.js`
    # runs, which set `patcharea = 225.0`. It is inert when `anchor == 0`.
    cscale0 = sum(FDiff.vegc_full_ind(p) * Float64(p.nind) for p in core.pools)
    ctruth = cnt_series(name, 1, "n_mean")
    cb = ClimBuf()
    slaq = Vector{Float64}[]; wdq = Vector{Float64}[]; dens = Float64[]
    for y in 1:NYEAR
        rng = ((y - 1) * 365 + 1):(y * 365)
        last(rng) <= length(forc) || break
        run_coupled_cell(
            core, clo, state, view(forc, rng); slow = s, climbuf = cb, days_per_year = 365
        )
        teacher && !isnan(ctruth[y]) && (s.n_prev = ctruth[y])
        push!(slaq, community_q(core.pools, p -> p.sla))
        push!(wdq, community_q(core.pools, p -> p.wooddens))
        push!(dens, sum(Float64(p.nind) for p in core.pools if !p.is_grass; init = 0.0))
    end
    return CellRun(
        name, copy(s.target_history), dens, copy(s.feature_history),
        slaq, wdq, n0_modal, n0_ens, maximum(abs, s.resid_history), cscale0, anchor
    )
end

runs = [run_cell(k) for k in eachindex(names)]
forced = [run_cell(k; teacher = true) for k in eachindex(names)]
anch5 = [run_cell(k; anchor = 0.5) for k in eachindex(names)]
anch25 = [run_cell(k; anchor = 0.25) for k in eachindex(names)]
anch1 = [run_cell(k; anchor = 0.1) for k in eachindex(names)]
flush(stdout)

# ── THE PATCH ENSEMBLE (ADR 0105) — the basis every arm above is MISSING. ─────────────────────────────
# Everything from here down re-runs the same arms with ONE MEMBER PER PATCH of the 2010 `ind` canopy and
# averages the members, which is:
#   (a) the basis the C reports (it simulates 25 replicate patches and writes their mean — ADR 0053), and
#   (b) the basis the count DRF was TRAINED on (one row per Cell×Patch×Year).
# The modal arms above start on the DENSEST of the 25 patches, 1.12-1.72x the ensemble mean, so every free
# arm begins ~1.6-1.9x above its own truth and part of what the anchor "fixes" there is that initialisation
# offset rather than recursion drift. ADR 0104 §5 named this the one remaining blocker on the flip and §7
# re-registered the criterion to be decided HERE. Both bases run in one process so the artifact is visible
# rather than argued about.
#
# `seed = member` (not the modal arms' fixed 1) so the members are independent realizations of the same
# cell, matching `biome_resilience_probe.jl`'s ensemble. The C's 25 patches differ by stochastic history,
# not by climate.
struct EnsRun
    name::String
    target::Vector{Float64}          # ensemble MEAN of s.target_history, per year
    dens::Vector{Float64}            # ensemble MEAN of Σ nind over tree cohorts, per year
    fpc::Vector{Float64}             # ensemble MEAN of the fpc feature the DRF was fed, per year
    dens_sd::Vector{Float64}         # between-member SD of the density — the ensemble's own spread
    n0::Float64                      # mean stems per member at t0 = the C's own per-patch mean, by identity
    resid::Float64                   # max |carbon handoff residual| over ALL members
    cscale::Float64                  # min member C_scale (the tightest 1e-6·C_scale gate in the ensemble)
    anchor::Float64
    nmemb::Int
end

function run_member(k, patches, member; anchor::Float64 = 0.0, teacher::Bool = false)
    name = names[k]
    forc, _tairK = forcings_of(name)
    soil = readsoil(joinpath(REFDIR, "M_soilcolumn_$(name).txt"))
    pools, tmpls = patches[member]
    core = FDiffFastCore(deepcopy(pools), deepcopy(tmpls), soil, lats[k]; params = leafon_params())
    clo = SEBEnergyClosure(; t_soil0 = mean(_tairK))
    state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
    rc = RecruitCopula{Float64}(cop, af, xcop, make_recruit_to_pools(axnames), live_flux_cond)
    s = FluxDrivenSlowEmulator(
        core, forest; boundary = copy(bnds[k]), n_init = n_inits[k], age0 = age0s[k],
        seed = member, recruit_copula = rc, anchor = anchor
    )
    cscale0 = sum(FDiff.vegc_full_ind(p) * Float64(p.nind) for p in core.pools)
    cb = ClimBuf()
    ctruth = cnt_series(name, 1, "n_mean")
    dens = Float64[]
    for y in 1:NYEAR
        rng = ((y - 1) * 365 + 1):(y * 365)
        last(rng) <= length(forc) || break
        run_coupled_cell(
            core, clo, state, view(forc, rng); slow = s, climbuf = cb, days_per_year = 365
        )
        teacher && !isnan(ctruth[y]) && (s.n_prev = ctruth[y])
        push!(dens, sum(Float64(p.nind) for p in core.pools if !p.is_grass; init = 0.0))
    end
    return (;
        target = copy(s.target_history), dens,
        fpc = [row[I_FPC] for row in s.feature_history],
        resid = maximum(abs, s.resid_history), cscale = cscale0,
        n0 = sum(Float64(p.nind) for p in pools) * PATCH_AREA,
    )
end

"Run every patch as its own member and average. `mean_at(y)` skips members that ended early (none do at a
 10-year horizon, but a truncated member must never be silently counted as a zero)."
function run_ens(k; anchor::Float64 = 0.0, teacher::Bool = false)
    patches, _pk = readcanopy_patches(joinpath(REFDIR, "M_individuals_$(names[k])_2010.csv"))
    ms = [run_member(k, patches, m; anchor = anchor, teacher = teacher) for m in eachindex(patches)]
    take(f, y) = [f(m)[y] for m in ms if length(f(m)) >= y]
    ny = minimum(length(m.dens) for m in ms)
    return EnsRun(
        names[k],
        [mean(take(m -> m.target, y)) for y in 1:ny],
        [mean(take(m -> m.dens, y)) for y in 1:ny],
        [mean(take(m -> m.fpc, y)) for y in 1:ny],
        [std(take(m -> m.dens, y)) for y in 1:ny],
        mean(m.n0 for m in ms),
        maximum(m.resid for m in ms),
        minimum(m.cscale for m in ms),
        anchor, length(ms)
    )
end

@printf("\n--- running the PATCH ENSEMBLE arms (ADR 0105) ---\n"); flush(stdout)
ens_free = [run_ens(k) for k in eachindex(names)]
ens_a1 = [run_ens(k; anchor = 0.1) for k in eachindex(names)]
ens_a25 = [run_ens(k; anchor = 0.25) for k in eachindex(names)]
ens_a5 = [run_ens(k; anchor = 0.5) for k in eachindex(names)]
ens_forced = [run_ens(k; teacher = true) for k in eachindex(names)]
@printf("ensemble arms done (%d members/cell)\n", ens_free[1].nmemb); flush(stdout)

# ── REPORT 1 — counts, year-matched, in units of the seed1-vs-seed2 noise floor ──────────────────────
@printf("\n=== M3 S-SIDE / COUNTS — coupled per-patch tree N vs the C's per-patch ensemble ===\n")
@printf("(wscal_leafon=TRUE, pinned _t8 + _t8 pooled copula, IN-SAMPLE cells, historic 2010-2019)\n\n")
@printf(
    "%-22s %7s %7s %8s %8s %8s %8s %8s %8s %8s\n",
    "cell", "n0_mod", "n0_ens", "C_2010", "C_2019", "E_2010", "E_2019", "floor", "|d|/fl", "ratio_sh"
)
for r in runs
    c1 = cnt_series(r.name, 1, "n_mean"); c2 = cnt_series(r.name, 2, "n_mean")
    ok = .!isnan.(c1) .& .!isnan.(c2)
    floor_n = mean(abs.(c1[ok] .- c2[ok]))
    e = r.target
    ny = min(length(e), NYEAR)
    d = abs.(e[1:ny] .- c1[1:ny])
    ratio = e[1:ny] ./ c1[1:ny]
    @printf(
        "%-22s %7d %7.2f %8.2f %8.2f %8.2f %8.2f %8.3f %8.1f %8s\n",
        r.name, r.n0_modal, r.n0_ens, c1[1], c1[ny], e[1], e[ny], floor_n,
        mean(d) / max(floor_n, 1.0e-12), @sprintf("%.2f>%.2f", ratio[1], ratio[ny])
    )
end
@printf("\nn0_mod/n0_ens = stems in the driver's MODAL patch vs the mean over the same file's 25 patches\n")
@printf("C_* = the C's per-patch ensemble MEAN (seed1); E_* = s.target_history (the DRF's per-patch count)\n")
@printf("floor = mean_y |seed1-seed2| of C's ensemble mean; |d|/fl = the emulator's mean |error| in floors\n")
@printf("ratio_sh = E/C in 2010 -> 2019: READ THE SHAPE, a drifting ratio has a harmless-looking mean\n")

# ── REPORT 2 — the full year-matched series, because the shape is the verdict ────────────────────────
@printf("\n=== per-year E/C ratio (coupled target / C per-patch ensemble mean) ===\n")
@printf("%-22s%s\n", "cell", join((@sprintf("%7d", y) for y in Y0:Y1)))
for r in runs
    c1 = cnt_series(r.name, 1, "n_mean")
    cellstr = join(
        (
            y <= length(r.target) ? @sprintf("%7.2f", r.target[y] / c1[y]) : @sprintf("%7s", "-")
                for y in 1:NYEAR
        )
    )
    @printf("%-22s%s\n", r.name, cellstr)
end

# ── REPORT 3 — traits: nind-weighted community medians vs the C's pooled community, in floors ────────
@printf("\n=== M3 S-SIDE / TRAITS — coupled community vs the C's standing community ===\n")
@printf("(only SLA + Wooddens reach TreePools; D95max/minwscal are drawn but have no per-tree consumer)\n\n")
@printf(
    "%-22s %-9s %9s %9s %9s %7s %8s %8s %8s\n",
    "cell", "axis", "C_q50_10", "C_q50_19", "E_q50_10", "E_q50_19", "floor", "|d|/fl", "nqrmse"
)
for r in runs
    for (ax, eq) in (("SLA", r.sla), ("Wooddens", r.wd))
        t1 = trt_series(r.name, 1, ax); t2 = trt_series(r.name, 2, ax)
        ny = min(length(eq), NYEAR)
        floor_m = mean(abs(t1[y][3] - t2[y][3]) for y in 1:ny)
        dmed = mean(abs(eq[y][3] - t1[y][3]) for y in 1:ny)
        iqr = mean(t1[y][4] - t1[y][2] for y in 1:ny)
        nq = mean(sqrt(sum((eq[y] .- t1[y]) .^ 2) / length(QS)) / iqr for y in 1:ny)
        @printf(
            "%-22s %-9s %9.4f %9.4f %9.4f %7.4f %8.4f %8.1f %8.3f\n",
            r.name, ax, t1[1][3], t1[ny][3], eq[1][3], eq[ny][3], floor_m,
            dmed / max(floor_m, 1.0e-12), nq
        )
    end
end
@printf("\nfloor = mean_y |seed1-seed2| of the C's per-year community MEDIAN; |d|/fl = coupled error in floors\n")
@printf("nqrmse = year-mean RMSE over the 5 quantiles / the C's own IQR (distribution shape, not just centre)\n")

# ── REPORT 4 — ATTRIBUTION arm B: does teacher-forcing `n_prev` back onto its trained basis kill the
#    drift? (free − forced = the AR-recursion amplification; forced − 1 = what F's canopy features do) ──
@printf("\n=== ATTRIBUTION — free-running vs `n_prev`-teacher-forced vs ANCHORED, E/C per-patch count ratio ===\n")
@printf("%-22s %-8s%s\n", "cell", "arm", join((@sprintf("%7d", y) for y in Y0:Y1)))
for k in eachindex(runs)
    c1 = cnt_series(runs[k].name, 1, "n_mean")
    for (lab, r) in (("free", runs[k]), ("forced", forced[k]), ("anch0.5", anch5[k]), ("anch0.1", anch1[k]))
        row = join(
            (
                y <= length(r.target) ? @sprintf("%7.2f", r.target[y] / c1[y]) : @sprintf("%7s", "-")
                    for y in 1:NYEAR
            )
        )
        @printf("%-22s %-8s%s\n", lab == "free" ? runs[k].name : "", lab, row)
    end
end
@printf("\n`forced` overwrites s.n_prev with the C's own per-patch ensemble mean after each year, putting\n")
@printf("that ONE feature back on the basis the training table defines it on. Everything else is identical.\n")
@printf("`anch*` uses NO external information — it blends in the ratio landing the stand on target/225 m².\n")
@printf("So `forced` is an attribution BOUND (it needs the answer); `anch*` is a shippable candidate.\n")

@printf("\n--- the same four arms as the GATE metric: mean |E-C| in seed1-vs-seed2 noise floors ---\n")
@printf(
    "%-22s %8s %8s %9s %9s %9s %8s\n",
    "cell", "floor", "free/fl", "forced/fl", "anch.5/fl", "anch.1/fl", "removed%"
)
for k in eachindex(runs)
    c1 = cnt_series(runs[k].name, 1, "n_mean"); c2 = cnt_series(runs[k].name, 2, "n_mean")
    ok = .!isnan.(c1) .& .!isnan.(c2)
    fl = mean(abs.(c1[ok] .- c2[ok]))
    ny = min(length(runs[k].target), length(forced[k].target), length(anch5[k].target), NYEAR)
    d(r) = mean(abs.(r.target[1:ny] .- c1[1:ny]))
    dfree = d(runs[k])
    @printf(
        "%-22s %8.3f %8.1f %9.1f %9.1f %9.1f %7.0f%%\n",
        runs[k].name, fl, dfree / fl, d(forced[k]) / fl, d(anch5[k]) / fl, d(anch1[k]) / fl,
        100 * (1 - d(forced[k]) / dfree)
    )
end
@printf("removed%% = the share of the free-running error the RECURSION contributes (arm B; 100%% = all of it)\n")

# ── REPORT 4b — ADR 0103 §6's PRE-REGISTERED FLIP CRITERION, evaluated clause by clause. ─────────────
# The thresholds below are written BEFORE the run (`residual-diagnosis`: a threshold you wrote is a
# hypothesis too) so this is a measurement and not a judgement call after seeing the numbers. S's clauses
# are qualitative ("each should flatten", "stay there"); these make them falsifiable:
#
#   (i)   DRIFT REMOVED in the three drifting cells. Drift factor `d = (E/C)_2019 / (E/C)_2010` — 1.00 is
#         a pure level offset with no drift, which is what "flat" means here. PASS iff |ln d| falls by
#         ≥50 % vs the free arm AND the anchored |ln d| < 0.20 (a residual drift within ±22 % over the
#         decade). Both clauses matter: a big relative cut off a huge drift is still a drifting model.
#   (ii)  THE TWO NOISE-FLOOR CELLS STAY THERE. "At the floor" is read as the gate metric mean|E−C|/floor,
#         which is 0.5 (Amazon) and 1.4 (Sahel) free. PASS iff the anchored value is ≤ 2.0 floors AND does
#         not exceed 1.5× the free value — the anchor must not buy the drifting cells at their expense.
#   (iii) CARBON CLOSES at ≤ 1e-6·C_scale in all five (the standing Gate-2 tolerance, unchanged).
#
# A clause that fails is the FINDING and goes back to S as such — ADR 0103 §6 is explicit that `a` must
# not be tuned until it passes. Both `a` values are scored; the criterion is decided on `a = 0.5` (the
# horizon-correct one), with `a = 0.1` reported because that is the value the flip would install.
const DRIFTERS = ("boreal_siberia", "mediterranean_iberia", "temperate_hainich")
const FLOORCELLS = ("tropical_amazon", "semiarid_sahel")
driftfac(r, c1, ny) = (r.target[ny] / c1[ny]) / (r.target[1] / c1[1])

@printf("\n=== ADR 0103 §6 FLIP CRITERION — pre-registered, clause by clause ===\n")
@printf("(thresholds fixed before the run; horizon = 10 yr, which ADR 0103 §3b says sees a PARTIAL effect)\n\n")
@printf(
    "%-22s %6s %8s %8s %8s %9s %9s %8s\n",
    "cell", "role", "d_free", "d_a0.5", "d_a0.1", "|lnd|drop", "fl_a0.5", "clause"
)
crit_i = Bool[]; crit_ii = Bool[]
for k in eachindex(runs)
    nm = runs[k].name
    c1 = cnt_series(nm, 1, "n_mean"); c2 = cnt_series(nm, 2, "n_mean")
    ok = .!isnan.(c1) .& .!isnan.(c2)
    fl = mean(abs.(c1[ok] .- c2[ok]))
    ny = min(length(runs[k].target), length(anch5[k].target), NYEAR)
    df = driftfac(runs[k], c1, ny); d5 = driftfac(anch5[k], c1, ny); d1 = driftfac(anch1[k], c1, ny)
    drop = 1 - abs(log(d5)) / max(abs(log(df)), 1.0e-12)
    fl5 = mean(abs.(anch5[k].target[1:ny] .- c1[1:ny])) / fl
    flfree = mean(abs.(runs[k].target[1:ny] .- c1[1:ny])) / fl
    role, pass = if nm in DRIFTERS
        p = drop >= 0.5 && abs(log(d5)) < 0.2
        push!(crit_i, p)
        ("drift", p)
    elseif nm in FLOORCELLS
        p = fl5 <= 2.0 && fl5 <= 1.5 * flfree
        push!(crit_ii, p)
        ("floor", p)
    else
        ("-", true)
    end
    @printf(
        "%-22s %6s %8.3f %8.3f %8.3f %8.0f%% %9.2f %8s\n",
        nm, role, df, d5, d1, 100 * drop, fl5, pass ? "PASS" : "FAIL"
    )
end
@printf("\nd_* = (E/C)_2019/(E/C)_2010, the DRIFT: 1.00 = a pure level offset, no drift. |lnd|drop = how\n")
@printf("much of the free arm's log-drift the anchor removes. fl_a0.5 = the gate metric in noise floors.\n")
@printf(
    "\n  (i)   drift removed in all 3 drifting cells : %s\n", all(crit_i) ? "PASS" : "FAIL"
)
@printf("  (ii)  both floor cells stay at the floor   : %s\n", all(crit_ii) ? "PASS" : "FAIL")

# ── REPORT 4c — DID THE ANCHOR ACTUALLY FIRE? (ADR 0048's failure mode: an operator that never runs
#    returns a clean null that reads as a pass.) With `a > 0` the stand is pulled toward `target/225`, so
#    `D·225/target` → 1; unanchored it is free to sit anywhere, and ADR 0103 §2 measured 1.41 at Hainich
#    under constant forcing. This is a MECHANISM check, not a skill one — it must move even if (i) fails. ─
@printf("\n=== did the anchor FIRE? stand density × patch_area / the DRF's own target, 2019 ===\n")
@printf("%-22s %10s %10s %10s %12s\n", "cell", "free", "anch0.5", "anch0.1", "carbon_ok")
for k in eachindex(runs)
    lvl(r) = (ny = min(length(r.target), length(r.dens), NYEAR); r.dens[ny] * 225.0 / r.target[ny])
    cok = all(r -> r.resid <= 1.0e-6 * r.cscale, (runs[k], forced[k], anch5[k], anch1[k]))
    @printf(
        "%-22s %10.3f %10.3f %10.3f %12s\n",
        runs[k].name, lvl(runs[k]), lvl(anch5[k]), lvl(anch1[k]), cok ? "yes" : "NO"
    )
end
@printf("\n1.00 = the stand sits exactly where its own count model says. The free arm's departure from 1 is\n")
@printf("the level error ADR 0103 §2 found at Hainich (1.41x under constant forcing) — no gate here reads it.\n")
@printf("carbon_ok = max|handoff resid| <= 1e-6*C_scale in ALL FOUR arms (criterion iii).\n")

# ── REPORT 5 — is the count drift INHERITED from the canopy? F's own canopy features vs the C's, both
#    as a ratio to their 2010 value, next to the count ratio. Same-direction motion = inheritance. ─────
#    ⚠ `C_fpc` is the CROWN-cover output `a_fpc` (`fpc_tree_crown`), which is the quantity F's `fpc`
#    feature actually is (ADR 0060). `C_fpcBL` is the leaf-area Beer-Lambert `a_fpc_stand` this report
#    used before 2026-08-06 — kept visible because ADR 0105's canopy-drift attribution was read off it.
@printf("\n=== IS THE DRIFT INHERITED? 2019/2010 ratio of each quantity to its own 2010 value ===\n")
@printf(
    "%-22s %9s %9s %9s %9s %9s %9s %9s\n",
    "cell", "F_fpc", "C_fpc", "C_fpcBL", "F_lai", "C_lai", "F_agb", "E/C_cnt"
)
cfpc = readcsv(joinpath(REFDIR, "M_fdiff_oracle_biomes_annual.csv"))
function c_ann(name, col)
    out = fill(NaN, NYEAR)
    for i in eachindex(cfpc["name"])
        cfpc["name"][i] == name || continue
        y = parse(Int, cfpc["year"][i])
        (Y0 <= y <= Y1) && (out[y - Y0 + 1] = parse(Float64, cfpc[col][i]))
    end
    return out
end
for r in runs
    ny = min(length(r.feats), NYEAR)
    f = r.feats
    cfp = c_ann(r.name, "fpc_tree_crown"); cbl = c_ann(r.name, "fpc_tree")
    cla = c_ann(r.name, "lai_stand_total")
    c1 = cnt_series(r.name, 1, "n_mean")
    @printf(
        "%-22s %9.2f %9.2f %9.2f %9.2f %9.2f %9.2f %9.2f\n",
        r.name, f[ny][I_FPC] / f[1][I_FPC], cfp[ny] / cfp[1], cbl[ny] / cbl[1],
        f[ny][I_LAI] / f[1][I_LAI],
        cla[ny] / cla[1], f[ny][I_AGB] / f[1][I_AGB],
        (r.target[ny] / c1[ny]) / (r.target[1] / c1[1])
    )
end
# ── REPORT 5b — WHY the anchor does not remove the drift, and what it does to the Sahel. ─────────────
# The anchor pins the ROSTER to the count DRF's absolute target; it cannot pin the TARGET, which the DRF
# re-predicts each year from F's canopy features. So it closes a feedback loop that the pure AR ratio only
# transmitted in relative terms: density → fpc/lai/agb → target → density. Two competing readings of the
# Sahel's anchored collapse (E/C 1.19 → 0.33), and this report separates them:
#   H1 FEEDBACK — anchoring cuts density, the cut lowers `fpc`, the lower `fpc` lowers the target, repeat.
#      Signature: the anchored arm's OWN `fpc`/`agb` fall faster than the free arm's, monotonically.
#   H2 INITIAL-CANOPY ARTEFACT — the driver starts from the MODAL patch, which at the Sahel is 22 stems vs
#      an 11.28-stem ensemble mean (1.95×, the largest offset of the five). The anchor's first act is then
#      a one-time thinning of nearly half the stand, and what follows is recovery, not instability.
#      Signature: `fpc` steps down early and then FLATTENS, with the target following rather than leading.
# H1 and H2 make opposite predictions about the shape, which is why the per-year series is printed and not
# a start/end ratio. (`residual-diagnosis`: state the falsifiable alternative before reading the numbers.)
@printf("\n=== WHY — per-year fpc and count target, free vs anch0.5 (H1 feedback vs H2 initial-canopy) ===\n")
for k in eachindex(runs)
    c1 = cnt_series(runs[k].name, 1, "n_mean")
    @printf("%-22s %-14s%s\n", runs[k].name, "", join((@sprintf("%7d", y) for y in Y0:Y1)))
    for (lab, r) in (("free", runs[k]), ("anch0.5", anch5[k]))
        ny = min(length(r.feats), NYEAR)
        for (qlab, qv) in (
                ("fpc", [r.feats[y][I_FPC] for y in 1:ny]),
                ("target", r.target[1:ny]),
                ("E/C", [r.target[y] / c1[y] for y in 1:ny]),
            )
            @printf(
                "%-22s %-8s %-5s%s\n", "", lab, qlab,
                join((@sprintf("%7.3f", v) for v in qv))
            )
        end
    end
end
@printf("\nH1 (feedback) predicts the anchored `fpc` falls faster than the free one and keeps falling;\n")
@printf("H2 (modal-patch artefact) predicts an early step down that then FLATTENS. Read the shape.\n")

@printf("\nF_* = the coupled canopy features the DRF was actually fed (s.feature_history); C_* = the C's own\n")
@printf("same quantity from the ADR-0053 annual oracle (C_lai is all-PFT — a bound, not a match target).\n")
@printf("E/C_cnt = how much the count ratio itself moved over the window (1.00 = no drift, only a level).\n")

# ── REPORT 6 — the closure + configuration invariants that make the above readable at all ────────────
@printf("\n=== invariants ===\n")
for r in runs
    @printf(
        "%-22s  max|carbon handoff resid| = %.3e   mean water_stress = %.4f   tree density %.4f -> %.4f\n",
        r.name, r.resid, mean(row[I_WS] for row in r.feats), r.dens[1], r.dens[end]
    )
end
@printf("\n--- criterion (iii): the carbon handoff closes in EVERY arm, per cell (resid / 1e-6*C_scale) ---\n")
@printf("%-22s %10s %9s %9s %9s %9s\n", "cell", "C_scale", "free", "forced", "anch0.5", "anch0.1")
for k in eachindex(runs)
    q(r) = r.resid / (1.0e-6 * r.cscale)
    @printf(
        "%-22s %10.3e %9.2e %9.2e %9.2e %9.2e\n",
        runs[k].name, runs[k].cscale, q(runs[k]), q(forced[k]), q(anch5[k]), q(anch1[k])
    )
end
@printf("< 1.0 everywhere = criterion (iii) holds (the standing Gate-2 tolerance, ADR 0018).\n")

# ── THE STAND ITSELF (line S, ADR 0104) — the criterion above is scored on the WRONG QUANTITY. ───────
# `target_history` is the count model's PREDICTION. The anchor does not act on it: `slow.jl:1066-1070`
# multiplies the ROSTER (`dtree`), and `target` appears only as the thing aimed at. So the criterion moves
# only through a second-order feedback (a moved stand moves the canopy features the model is fed next year)
# which has its own sign per cell — while the first-order question the anchor was built to answer is "is the
# stand at the right DENSITY?". That is this table.
# Basis: the C's per-patch ensemble mean `n_mean` ÷ `patch_area` = the same stems/m² the roster carries.
# Score: `mean_y |ln(density/truth)|` — symmetric, so an overshoot is penalised exactly as hard as the
# over-density it replaced, which is what makes "did it help?" answerable rather than arguable.
# ⚠ CONFOUND, stated because it inflates every free-running ratio here: the driver starts from the MODAL
# patch, 1.12-1.72x denser than the ensemble mean the DRF was trained on (M's STATE item 2), so part of what
# the anchor "fixes" is that initialisation offset, not drift, and the measured benefit is an UPPER bound.
# Separating them needs the ensemble driver — M's pending change, and the one remaining blocker on the flip.
@printf("\n=== THE STAND ITSELF (ADR 0104): density / (C per-patch mean / patch_area) ===\n")
@printf("(1.00 = the stand is at the right absolute level; this is the quantity the anchor acts on)\n\n")
@printf("%-22s %9s %9s %9s %9s\n", "cell", "free_19", "a0.1_19", "a0.25_19", "a0.5_19")
const ARMS_A = (("a=0.1", anch1), ("a=0.25", anch25), ("a=0.5", anch5))
scores = Dict{String, Vector{Float64}}("free" => Float64[])
for (lab, _) in ARMS_A
    scores[lab] = Float64[]
end
for k in eachindex(runs)
    c1 = cnt_series(runs[k].name, 1, "n_mean")
    ny = min(length(runs[k].dens), NYEAR)
    dtruth = [c1[y] / PATCH_AREA for y in 1:ny]
    rf = [runs[k].dens[y] / dtruth[y] for y in 1:ny]
    push!(scores["free"], mean(abs.(log.(rf))))
    terms = Float64[]
    for (lab, arm) in ARMS_A
        ra = [arm[k].dens[y] / dtruth[y] for y in 1:ny]
        push!(scores[lab], mean(abs.(log.(ra))))
        push!(terms, ra[ny])
    end
    @printf("%-22s %9.2f %9.2f %9.2f %9.2f\n", runs[k].name, rf[ny], terms[1], terms[2], terms[3])
end
@printf("\n--- score = year-mean |ln(density/truth)|; lower is better, 0 is perfect ---\n")
@printf("%-22s %9s %9s %9s %9s %9s\n", "cell", "free", "a=0.1", "a=0.25", "a=0.5", "all better?")
for k in eachindex(runs)
    f = scores["free"][k]
    @printf(
        "%-22s %9.3f %9.3f %9.3f %9.3f %9s\n", runs[k].name, f,
        scores["a=0.1"][k], scores["a=0.25"][k], scores["a=0.5"][k],
        all(scores[l][k] < f for (l, _) in ARMS_A) ? "yes" : "NO"
    )
end
@printf(
    "%-22s %9.3f %9.3f %9.3f %9.3f\n", "MEAN", mean(scores["free"]),
    mean(scores["a=0.1"]), mean(scores["a=0.25"]), mean(scores["a=0.5"])
)
@printf("\nA cell marked NO is one the anchor made WORSE on the quantity it acts on — the failure this table\n")
@printf("exists to expose, and the one the prediction-based criterion above cannot distinguish from a\n")
@printf("second-order feedback. ADR 0104 §3: all five improve at all three settings, and `a = 0.25` is the\n")
@printf("best mean whose worst cell is still an improvement (0.5 overshoots semiarid_sahel).\n")
@printf("\nDONE — the verdict is REPORT 1's |d|/fl and REPORT 2's shape, read with REPORTS 4-5's attribution.\n")
flush(stdout)

# ── REPORT 8 (line S, ADR 0105) — ADR 0104 §7's RE-REGISTERED CRITERION, ON THE PATCH ENSEMBLE. ──────
# This is the measurement ADR 0104 §5 deferred and named as the ONE remaining blocker on the flip. Every
# number above is on the modal patch; every number below is on the 25-patch ensemble, which removes the
# initialisation confound by construction — the ensemble's own t0 stem count IS the C's per-patch mean.
#
# The thresholds are ADR 0104 §7's, written there BEFORE this run, and — the rule this line earned on
# 2026-08-06 — each has been checked against the update equation first: the anchor writes `r`, which
# multiplies the roster `dtree`, so every clause below is a function of the ROSTER DENSITY (clause 1),
# of the carbon handoff the roster change must not break (clause 3a), or of the canopy feature the moved
# roster produces (clause 3b). None of them scores `target_history`, which the anchor never writes.
#
#   CLAUSE 1  the stand score `mean_y |ln(density/truth)|` improves in ALL FIVE cells, AND the Sahel guard:
#             for any cell whose TERMINAL ratio crosses from over- (free > 1) to under-shoot (anch < 1),
#             the undershoot it creates must be no larger than the log improvement it delivers,
#             |ln r_anch| <= |ln r_free| - |ln r_anch|. At `a = 0.5` on the modal basis Sahel went 1.55 ->
#             0.33, which this guard is written to catch.
#   CLAUSE 2  the memory clause — NOT scored here. It lives in `biome_resilience_probe.jl` (e), which is
#             already ensemble-driven; run it with ANCHOR=0.25.
#   CLAUSE 3a carbon closes at <= 1e-6 * C_scale in every member of every cell.
#   CLAUSE 3b STABILITY (adopted from ADR 0056): no cell's anchored per-year `fpc` shows a monotone
#             collapse — read as monotone non-increasing across the whole window AND ending below half
#             its first year. Sahel's anchored `fpc` 0.281 -> 0.057 on the modal basis is the shape this
#             clause exists to reject.
#   CLAUSE 4  deliberately absent: the 100-year biomass drift is REPORTED (probe (f)) and not gated, because
#             that drift is in F's carbon pools, which the anchor does not touch (ADR 0104 §7(4)).
const ENS_ARMS = (("a=0.1", ens_a1), ("a=0.25", ens_a25), ("a=0.5", ens_a5))
@printf("\n\n=== REPORT 8 (ADR 0105) — THE CRITERION ON THE PATCH ENSEMBLE (%d members/cell) ===\n", ens_free[1].nmemb)
@printf("(the modal-patch confound of ADR 0104 §5 is removed by construction: the ensemble's t0 stem count\n")
@printf(" IS the C's per-patch mean — the `n0_ens` vs `C_2010` column below is that identity as a check)\n\n")
@printf("%-22s %8s %8s %8s %8s %9s %9s %9s\n", "cell", "n0_ens", "C_2010", "free_19", "a0.1_19", "a0.25_19", "a0.5_19", "sd/mean")
ens_scores = Dict{String, Vector{Float64}}("free" => Float64[])
ens_term = Dict{String, Vector{Float64}}("free" => Float64[])
for (lab, _) in ENS_ARMS
    ens_scores[lab] = Float64[]; ens_term[lab] = Float64[]
end
for k in eachindex(ens_free)
    c1 = cnt_series(names[k], 1, "n_mean")
    ny = min(length(ens_free[k].dens), NYEAR)
    dtruth = [c1[y] / PATCH_AREA for y in 1:ny]
    rf = [ens_free[k].dens[y] / dtruth[y] for y in 1:ny]
    push!(ens_scores["free"], mean(abs.(log.(rf)))); push!(ens_term["free"], rf[ny])
    terms = Float64[]
    for (lab, arm) in ENS_ARMS
        ra = [arm[k].dens[y] / dtruth[y] for y in 1:ny]
        push!(ens_scores[lab], mean(abs.(log.(ra)))); push!(ens_term[lab], ra[ny])
        push!(terms, ra[ny])
    end
    @printf(
        "%-22s %8.2f %8.2f %8.2f %8.2f %9.2f %9.2f %9.2f\n",
        names[k], ens_free[k].n0, c1[1], rf[ny], terms[1], terms[2], terms[3],
        ens_free[k].dens_sd[ny] / ens_free[k].dens[ny]
    )
end
@printf("\n--- CLAUSE 1: score = year-mean |ln(density/truth)|, ensemble mean density; lower is better ---\n")
@printf("%-22s %9s %9s %9s %9s %11s\n", "cell", "free", "a=0.1", "a=0.25", "a=0.5", "all better?")
for k in eachindex(ens_free)
    f = ens_scores["free"][k]
    @printf(
        "%-22s %9.3f %9.3f %9.3f %9.3f %11s\n", names[k], f,
        ens_scores["a=0.1"][k], ens_scores["a=0.25"][k], ens_scores["a=0.5"][k],
        all(ens_scores[l][k] < f for (l, _) in ENS_ARMS) ? "yes" : "NO"
    )
end
@printf(
    "%-22s %9.3f %9.3f %9.3f %9.3f\n", "MEAN", mean(ens_scores["free"]),
    mean(ens_scores["a=0.1"]), mean(ens_scores["a=0.25"]), mean(ens_scores["a=0.5"])
)

# ── the clause-by-clause verdict, computed in-script (the method rule: the script prints the headline) ──
"CLAUSE 1 for one arm: every cell's score improves, and the over->under crossing guard holds everywhere."
function clause1(lab)
    impr = all(ens_scores[lab][k] < ens_scores["free"][k] for k in eachindex(ens_free))
    guard = true; worst = ""
    for k in eachindex(ens_free)
        rfree = ens_term["free"][k]; ranch = ens_term[lab][k]
        (rfree > 1 && ranch < 1) || continue
        la = abs(log(ranch)); lf = abs(log(rfree))
        (la <= lf - la) || (guard = false; worst = names[k])
    end
    return impr, guard, worst
end
cq(r) = r.resid / (1.0e-6 * r.cscale)
const C3A = all(
    cq(a[k]) <= 1.0 for a in (ens_free, ens_a1, ens_a25, ens_a5) for k in eachindex(ens_free)
)
@printf("\n--- CLAUSE 3a: carbon handoff, WORST member of the ensemble (resid / 1e-6*C_scale) ---\n")
@printf("%-22s %10s %10s %10s %10s\n", "cell", "free", "a=0.1", "a=0.25", "a=0.5")
for k in eachindex(ens_free)
    @printf(
        "%-22s %10.2e %10.2e %10.2e %10.2e\n", names[k],
        cq(ens_free[k]), cq(ens_a1[k]), cq(ens_a25[k]), cq(ens_a5[k])
    )
end
@printf("< 1.0 everywhere = clause 3a holds (Gate-2 tolerance, ADR 0018), scored on the WORST member: %s\n", C3A ? "PASS" : "FAIL")

"CLAUSE 3b: a monotone non-increasing `fpc` that ends below half its first year is the runaway shape."
function collapsed(arm)
    f = arm.fpc
    length(f) >= 3 || return false
    return all(f[y + 1] <= f[y] for y in 1:(length(f) - 1)) && f[end] < 0.5 * f[1]
end
@printf("\n--- CLAUSE 3b: per-year `fpc` of the ANCHORED arms — monotone collapse? ---\n")
@printf("%-22s %-8s%s\n", "cell", "arm", join((@sprintf("%7d", y) for y in Y0:Y1)))
for k in eachindex(ens_free)
    for (lab, arm) in (("free", ens_free), ENS_ARMS...)
        @printf(
            "%-22s %-8s%s  %s\n", lab == "free" ? names[k] : "", lab,
            join((@sprintf("%7.3f", v) for v in arm[k].fpc)),
            collapsed(arm[k]) ? "COLLAPSE" : ""
        )
    end
end

@printf("\n=== ADR 0104 §7 VERDICT ON THE ENSEMBLE, per candidate `a` ===\n")
@printf("%-8s %-14s %-16s %-12s %-12s %s\n", "a", "clause1 score", "clause1 guard", "clause3a", "clause3b", "OVERALL (1+3)")
for (lab, arm) in ENS_ARMS
    impr, guard, worst = clause1(lab)
    c3b = !any(collapsed(arm[k]) for k in eachindex(arm))
    @printf(
        "%-8s %-14s %-16s %-12s %-12s %s\n", lab,
        impr ? "PASS" : "FAIL", guard ? "PASS" : "FAIL ($worst)",
        C3A ? "PASS" : "FAIL", c3b ? "PASS" : "FAIL",
        (impr && guard && C3A && c3b) ? "PASS" : "FAIL"
    )
end
# ── REPORT 9 (ADR 0105) — WHERE THE REMAINING ERROR LIVES, on the ensemble basis. ────────────────────
# With the initialisation confound gone, the free-running level error is small enough that the question
# changes from "how do we anchor it" to "what is left, and whose is it". Three arms answer it:
#   FREE     — the deployed loop.
#   FORCED   — `s.n_prev` overwritten each year with the C's own per-patch mean. It puts the ONE count-space
#              AR feature back on its trained basis and leaves F's canopy features exactly as they are, so
#              free − forced is the count RECURSION's contribution and forced − 1 is what the count model
#              does when fed F's own (drifting) canopy. It needs the answer to work ⇒ a bound, not a model.
#   OFFLINE  — the AR(1) prediction from the training table alone (`scripts/exposure_bias_probe.jl`):
#              e_10 = b(1-g^10)/(1-g) with b the one-step bias on the trained basis and g = ∂pred/∂n_prev.
# If FREE ≈ OFFLINE the coupled error IS the exposure bias and a retrain is the fix. If FORCED ≈ FREE the
# recursion contributes nothing and the error is in the FEATURES F hands the count model — a coupling
# question, not a training one. The three are printed together because only the comparison decides it.
@printf("\n\n=== REPORT 9 (ADR 0105) — free vs `n_prev`-FORCED, ensemble basis, terminal density/truth ===\n\n")
@printf("%-22s %10s %10s %12s %12s\n", "cell", "free_19", "forced_19", "free-forced", "score_forced")
for k in eachindex(ens_free)
    c1 = cnt_series(names[k], 1, "n_mean")
    ny = min(length(ens_free[k].dens), length(ens_forced[k].dens), NYEAR)
    dtruth = [c1[y] / PATCH_AREA for y in 1:ny]
    rf = [ens_free[k].dens[y] / dtruth[y] for y in 1:ny]
    rt = [ens_forced[k].dens[y] / dtruth[y] for y in 1:ny]
    @printf(
        "%-22s %10.3f %10.3f %12.3f %12.3f\n",
        names[k], rf[ny], rt[ny], rf[ny] - rt[ny], mean(abs.(log.(rt)))
    )
end
@printf("\nfree-forced ~ 0 => the count-space AR recursion contributes ~nothing to the level error on this\n")
@printf("basis, and what remains is what the count model does on F's own canopy features. Compare\n")
@printf("`score_forced` with CLAUSE 1's `free` column: a forced arm that is no better is the same statement.\n")

@printf("\nCLAUSE 2 (memory) is NOT in this table — it is scored by scripts/biome_resilience_probe.jl (e),\n")
@printf("which is already ensemble-driven. Run it with ANCHOR=0.25 and read its own PASS/FAIL line.\n")
@printf("The flip needs clauses 1, 2 AND 3 to pass at the SAME `a`.\n")
flush(stdout)
