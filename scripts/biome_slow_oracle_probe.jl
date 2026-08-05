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
#     — STATE.md item 3 keeps the ensemble lift as its own deliberate change). So year 0 already starts
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
function run_cell(k; teacher::Bool = false)
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
        seed = 1, recruit_copula = rc
    )
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
        slaq, wdq, n0_modal, n0_ens, maximum(abs, s.resid_history)
    )
end

runs = [run_cell(k) for k in eachindex(names)]
forced = [run_cell(k; teacher = true) for k in eachindex(names)]

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
@printf("\n=== ATTRIBUTION — free-running vs `n_prev`-teacher-forced, E/C per-patch count ratio ===\n")
@printf("%-22s %-8s%s\n", "cell", "arm", join((@sprintf("%7d", y) for y in Y0:Y1)))
for k in eachindex(runs)
    c1 = cnt_series(runs[k].name, 1, "n_mean")
    for (lab, r) in (("free", runs[k]), ("forced", forced[k]))
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

@printf("\n--- the same two arms as the GATE metric: mean |E-C| in seed1-vs-seed2 noise floors ---\n")
@printf("%-22s %10s %10s %10s %10s\n", "cell", "floor", "free/fl", "forced/fl", "removed%")
for k in eachindex(runs)
    c1 = cnt_series(runs[k].name, 1, "n_mean"); c2 = cnt_series(runs[k].name, 2, "n_mean")
    ok = .!isnan.(c1) .& .!isnan.(c2)
    fl = mean(abs.(c1[ok] .- c2[ok]))
    ny = min(length(runs[k].target), length(forced[k].target), NYEAR)
    dfree = mean(abs.(runs[k].target[1:ny] .- c1[1:ny]))
    dforc = mean(abs.(forced[k].target[1:ny] .- c1[1:ny]))
    @printf(
        "%-22s %10.3f %10.1f %10.1f %9.0f%%\n",
        runs[k].name, fl, dfree / fl, dforc / fl, 100 * (1 - dforc / dfree)
    )
end
@printf("removed%% = the share of the free-running error the recursion contributes (100%% = all of it)\n")

# ── REPORT 5 — is the count drift INHERITED from the canopy? F's own canopy features vs the C's, both
#    as a ratio to their 2010 value, next to the count ratio. Same-direction motion = inheritance. ─────
@printf("\n=== IS THE DRIFT INHERITED? 2019/2010 ratio of each quantity to its own 2010 value ===\n")
@printf(
    "%-22s %9s %9s %9s %9s %9s %9s\n",
    "cell", "F_fpc", "C_fpc", "F_lai", "C_lai", "F_agb", "E/C_cnt"
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
    cfp = c_ann(r.name, "fpc_tree"); cla = c_ann(r.name, "lai_stand_total")
    c1 = cnt_series(r.name, 1, "n_mean")
    @printf(
        "%-22s %9.2f %9.2f %9.2f %9.2f %9.2f %9.2f\n",
        r.name, f[ny][I_FPC] / f[1][I_FPC], cfp[ny] / cfp[1], f[ny][I_LAI] / f[1][I_LAI],
        cla[ny] / cla[1], f[ny][I_AGB] / f[1][I_AGB],
        (r.target[ny] / c1[ny]) / (r.target[1] / c1[1])
    )
end
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
@printf("\nDONE — the verdict is REPORT 1's |d|/fl and REPORT 2's shape, read with REPORTS 4-5's attribution.\n")
