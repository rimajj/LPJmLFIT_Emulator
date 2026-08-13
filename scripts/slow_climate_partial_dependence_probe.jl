#!/usr/bin/env julia
# slow_climate_partial_dependence_probe.jl — does the trained count model have ANY learned dependence on
# its two transient climate features, and if so, over WHICH range?
#
# WHY THIS EXISTS (ADR 0178 → this probe). The frozen-climate control measured the shipped count model's
# climate response inside FIT's own physics as ~0: mean climate term +0.175 / +0.134 / −0.008 stems for
# arms S0 / S0h / S1, drift share 94–100 %, climate-vs-truth slope −0.031 … +0.044. Two hypotheses were
# left open, and they send retraining effort to opposite places. This probe separates them WITHOUT an
# LPJmL run, by interrogating the artifact those arms actually loaded.
#
# ── REFERENCE BASIS (stated before any number is read; residual-diagnosis §1) ─────────────────────────
#   artifact  : $DRF  (default = drf_forest_global_pooled_w20_t8.drf — the exact file ADR 0177/0178 ran)
#   row order : src/components/slow.jl::flux_feature_vector, 15 cols, 11 head + 4 boundary
#               1 bm_inc_cell 2 growth_eff 3 water_stress 4 soilmoist 5 hmean 6 hmax 7 agb 8 lai
#               9 fpc 10 age_mean 11 n_prev | 12 eco_diag_gdd_5 13 tas_cold_month 14 soil_depth 15 co2
#   climate   : ONLY features 12 and 13 are transient climate. 14 is per-cell constant; 15 is constant
#               369.0 by design (ADR 0004/0107 — the emulator does not see CO2; not a gap).
#   base rows : the forest's OWN training table ($TAB/X.f64), restricted to the 15 rung-2 cells. These are
#               genuine per-cell feature distributions, not synthetic rows — so "the rest of the row held
#               at realistic per-cell values" is satisfied by construction rather than by assumption.
#   excursion : the campaign's OWN per-(cell,year) boundary CSVs ($BND/boundary_{historic,ssp370}_c<C>.csv)
#               — the exact climate values the arms were fed. historic terminal (2019) → ssp370 terminal
#               (2100). Not a synthetic ±X °C: the operative warming move at that cell.
#   yardstick : FIT's own terminal-year count response at each cell ($TRUTH, the `C` rows of the campaign
#               scorer). A predicted Δ is reported as a FRACTION of it, so "flat" has units.
#
# ── THE THREE HYPOTHESES (pre-registered; the handoff listed only H1 and H2) ──────────────────────────
#   H1 NEVER LEARNED       — no splits on 12/13, or PD flat over the full training range.
#                            ⇒ the defect is the training target / feature set (ADR 0112 restart point).
#   H2 LEARNED, LOOP BLIND — PD steep over the WITHIN-CELL warming excursion.
#                            ⇒ the defect is in how the loop feeds/uses it; the artifact is fine.
#   H3 LEARNED SPATIALLY   — PD steep over the FULL (between-cell) range but flat over the within-cell
#                            excursion. The forest learned climate as a CELL IDENTIFIER (a climatology
#                            map), which is what a pooled global fit rewards, and which a free-running
#                            single cell cannot use as a response.
#                            ⇒ the defect is the training DESIGN: the between-cell gradient is not the
#                            within-cell temporal contrast. More capacity would not touch it.
#
# H3 is why this probe does not just sweep the full range. A pooled forest over 58 588 cells is *certain*
# to split hard on gdd5 — the between-cell spread of n_living vs gdd5 is enormous — and a full-range sweep
# would show a large dependence that reads as H2 while the operative response is zero. Panels A and B are
# the pooled/within-group pair the residual-diagnosis skill mandates (ADR 0118): emitted from ONE script,
# side by side, on one row universe, with a stated answer to "which panel answers the question" (B does).
#
# ── DECISIVE PANELS ──────────────────────────────────────────────────────────────────────────────────
#   0  CHANNEL LIVENESS  — split counts per feature over all trees (ADR 0171 §3). A learned model trained
#                          on a constant is blind by construction; zero splits ends the question at once.
#   A  POOLED PD         — features 12/13 swept over their full training range on pooled rows. The
#                          BETWEEN-CELL scale. Diagnostic only; NOT the response.
#   B  WITHIN-CELL PD    — per cell, the row's climate columns moved from that cell's historic terminal to
#                          its ssp370 terminal, everything else at that cell's own historic rows. THE
#                          OPERATIVE RESPONSE. Marginal (gdd5 only, tas only) and joint.
#   C  SCALE REFERENCE   — the same within-cell PD for `n_prev` (feature 11, a channel known live) moved
#                          by that cell's own observed hist→ssp mean shift. Without this, "flat" is
#                          unfalsifiable: it could mean the whole forest is flat.
#   D  LOCAL FULL-RANGE  — the full gdd5/tas range swept on THAT CELL's rows. Separates "no slope at this
#                          cell's location in feature space" from "no slope anywhere" — a cell can sit on
#                          a plateau between two splits while the global surface is steep.
#
# A verdict is printed from measured thresholds fixed here, before the run:
#   climate |Δ| < 0.10 × |FIT truth| at ≥ 2/3 of cells  ⇒ operative channel DEAD
#   with pooled amplitude > 1.0 stem                    ⇒ H3 (spatial-only)   else ⇒ H1
#   climate |Δ| > 0.50 × |FIT truth| at ≥ 1/2 of cells  ⇒ H2
#
# ENV: DRF, TAB, BND, TRUTH, CELLS, NBASE, NSWEEP, POOLED_N, OUT
# Run: scripts/sbatch_julia.sh S-clim-pd --project=. scripts/slow_climate_partial_dependence_probe.jl

using Printf
using Mmap

include(joinpath(@__DIR__, "..", "src", "drf.jl"))
using .DRF

const GLOB = "/p/tmp/jamirp/emulator_global"
const DRFP = get(ENV, "DRF", joinpath(GLOB, "drf_forest_global_pooled_w20_t8.drf"))
const TAB = get(ENV, "TAB", joinpath(GLOB, "slow_count_pooled_w20_t8"))
const BND = get(ENV, "BND", "/p/tmp/jamirp/S_rung2/boundary")
const TRUTH = get(ENV, "TRUTH", "/p/tmp/jamirp/S_rung2/response_nliving.csv")
const OUT = get(ENV, "OUT", joinpath(GLOB, "S_climate_partial_dependence.csv"))

const NBASE = parse(Int, get(ENV, "NBASE", "600"))      # max base rows per cell for the PD average
const NSWEEP = parse(Int, get(ENV, "NSWEEP", "25"))      # sweep points across a full range
const POOLED_N = parse(Int, get(ENV, "POOLED_N", "4000"))  # pooled rows for panel A

# Feature indices in the frozen 15-column order.
const F_NPREV = 11
const F_GDD = 12
const F_TCM = 13
const CLIMATE = (F_GDD, F_TCM)

# ── pre-registered verdict thresholds ────────────────────────────────────────────────────────────────
const DEAD_FRAC = 0.1   # |Δ_climate| below this × |truth| ⇒ that cell's operative channel is dead
const LIVE_FRAC = 0.5   # above this × |truth| ⇒ that cell's channel is live
const POOLED_AMP = 1.0    # stems; pooled PD amplitude above this ⇒ the forest DID learn a climate surface

read_manifest(p) = Dict(
    pp[1] => pp[2] for pp in
        (split(l, '\t') for l in eachline(p)) if length(pp) == 2
)

# The campaign's boundary CSV: last data row = the leg's terminal year. Returns (year, gdd5, tas_cold).
function terminal_boundary(cell::Int, scen::AbstractString)
    path = joinpath(BND, "boundary_$(scen)_c$(cell).csv")
    isfile(path) || return nothing
    last_row = nothing
    for line in eachline(path)
        startswith(line, "#") && continue
        startswith(line, "Year") && continue
        isempty(strip(line)) && continue
        last_row = line
    end
    last_row === nothing && return nothing
    f = split(strip(last_row), ',')
    return (parse(Int, f[1]), parse(Float64, f[2]), parse(Float64, f[3]))
end

# FIT's own terminal count response per cell (the scorer's `C` rows via the `truth` column).
function fit_truth(path)
    d = Dict{Int, Float64}()
    isfile(path) || return d
    hdr = nothing
    for line in eachline(path)
        if hdr === nothing
            hdr = split(strip(line), ',')
            continue
        end
        f = split(strip(line), ',')
        length(f) == length(hdr) || continue
        c = parse(Int, f[findfirst(==("cell"), hdr)])
        d[c] = parse(Float64, f[findfirst(==("truth"), hdr)])
    end
    return d
end

# Mean forest prediction over `base` rows with features `idx` overridden to `vals`.
function pd_mean(forest, base::Vector{Vector{Float64}}, idx, vals)
    s = 0.0
    x = Vector{Float64}(undef, length(base[1]))
    @inbounds for row in base
        copyto!(x, row)
        for (i, v) in zip(idx, vals)
            x[i] = v
        end
        s += DRF.predict(forest, x)
    end
    return s / length(base)
end

function main()
    println("== slow_climate_partial_dependence_probe — does the count model see climate at all?")
    println("   artifact : ", DRFP)
    println("   table    : ", TAB)
    println("   boundary : ", BND)
    flush(stdout)

    man = read_manifest(joinpath(TAB, "manifest.txt"))
    n = parse(Int, man["n"]); p = parse(Int, man["p"])
    colnames = String.(split(strip(man["colnames"])))
    scens = String.(split(strip(get(man, "pooled_scenarios", "historic ssp370"))))
    @assert colnames[F_GDD] == "eco_diag_gdd_5" "feature $F_GDD is $(colnames[F_GDD]), not eco_diag_gdd_5"
    @assert colnames[F_TCM] == "tas_cold_month" "feature $F_TCM is $(colnames[F_TCM]), not tas_cold_month"
    @assert colnames[F_NPREV] == "n_prev" "feature $F_NPREV is $(colnames[F_NPREV]), not n_prev"
    println("   rows=$n feats=$p scenarios=$scens")

    print("   loading forest ... "); flush(stdout)
    t0 = time()
    forest = open(DRF.load_forest, DRFP)
    @printf("%d trees in %.1f s\n", length(forest.trees), time() - t0)
    @assert forest.nfeat == p "forest nfeat=$(forest.nfeat) but table p=$p"
    flush(stdout)

    # ── PANEL 0 — CHANNEL LIVENESS (ADR 0171 §3): can the consumer see the input at all? ─────────────
    println("\n== PANEL 0 — channel liveness: split counts per feature over $(length(forest.trees)) trees")
    nsplit = zeros(Int, p)
    thrmin = fill(Inf, p); thrmax = fill(-Inf, p)
    for tree in forest.trees, nid in eachindex(tree.feat)
        f = tree.feat[nid]
        f == 0 && continue
        nsplit[f] += 1
        thrmin[f] = min(thrmin[f], tree.thr[nid])
        thrmax[f] = max(thrmax[f], tree.thr[nid])
    end
    tot = sum(nsplit)
    println("   feat  name                 nsplit    share   thr_min      thr_max")
    for j in 1:p
        mark = j in CLIMATE ? " <== CLIMATE" : (j == F_NPREV ? " <== AR state" : "")
        if nsplit[j] == 0
            @printf(
                "   %4d  %-18s %8d   %6.2f%%   %-12s %-12s%s\n",
                j, colnames[j], 0, 0.0, "NO SPLITS", "NO SPLITS", mark
            )
        else
            @printf(
                "   %4d  %-18s %8d   %6.2f%%   %-12.4g %-12.4g%s\n",
                j, colnames[j], nsplit[j], 100 * nsplit[j] / tot, thrmin[j], thrmax[j], mark
            )
        end
    end
    clim_splits = nsplit[F_GDD] + nsplit[F_TCM]
    if clim_splits == 0
        println("\n   ⇒ ZERO splits on both climate features. The channel is DEAD BY CONSTRUCTION:")
        println("     no input on features $F_GDD/$F_TCM can change this forest's output. VERDICT = H1.")
    else
        @printf(
            "\n   ⇒ %d split(s) on the climate features (%.2f%% of all splits) — the channel is\n",
            clim_splits, 100 * clim_splits / tot
        )
        println("     structurally OPEN, so a flat response is NOT explained by \"no splits\". Continue.")
    end
    flush(stdout)

    # ── row indices for the probe cells, per scenario ────────────────────────────────────────────────
    cells_env = get(ENV, "CELLS", "")
    want = isempty(cells_env) ? Int[] : parse.(Int, split(cells_env, ','))
    print("\n   scanning cells.i64 / scenario.i64 ... "); flush(stdout)
    t0 = time()
    cellv = open(io -> Mmap.mmap(io, Vector{Int64}, n), joinpath(TAB, "cells.i64"))
    scenv = open(io -> Mmap.mmap(io, Vector{Int64}, n), joinpath(TAB, "scenario.i64"))
    if isempty(want)   # default: the rung-2 response cell set, taken from the boundary dir that ran
        for f in readdir(BND)
            m = match(r"^boundary_historic_c(\d+)\.csv$", f)
            m !== nothing && push!(want, parse(Int, m.captures[1]))
        end
        sort!(want)
    end
    wantset = Set(want)
    rows = Dict{Tuple{Int, Int}, Vector{Int}}()   # (cell, scen_code) -> row indices
    @inbounds for i in 1:n
        c = Int(cellv[i])
        c in wantset || continue
        push!(get!(rows, (c, Int(scenv[i])), Int[]), i)
    end
    @printf("%.1f s, %d cell(s)\n", time() - t0, length(want))

    # scenario.i64 indexes `pooled_scenarios`; assert it rather than assume (historic legs are 19 yr,
    # ssp370 legs 81 yr, so the historic row count per cell MUST be the smaller one).
    hist_code = findfirst(==("historic"), scens) - 1
    ssp_code = findfirst(==("ssp370"), scens) - 1
    nh = sum(length(get(rows, (c, hist_code), Int[])) for c in want)
    ns = sum(length(get(rows, (c, ssp_code), Int[])) for c in want)
    println("   scenario codes: historic=$hist_code ($nh rows), ssp370=$ssp_code ($ns rows)")
    @assert nh < ns "scenario code check FAILED: historic ($nh rows) should have FEWER rows than " *
        "ssp370 ($ns) — the 19-yr vs 81-yr legs. The codes are mislabelled; every panel " *
        "below would be inverted."

    Xt = open(io -> Mmap.mmap(io, Matrix{Float64}, (p, n)), joinpath(TAB, "X.f64"))
    getrow(i) = Vector{Float64}(@view Xt[:, i])

    # feature bands over the probe cells' own training rows (the sweep range for panels A and D)
    gdd_lo, gdd_hi = Inf, -Inf
    tcm_lo, tcm_hi = Inf, -Inf
    allrows = Int[]
    for v in values(rows), i in v
        push!(allrows, i)
    end
    for i in allrows
        g = Xt[F_GDD, i]; t = Xt[F_TCM, i]
        gdd_lo = min(gdd_lo, g); gdd_hi = max(gdd_hi, g)
        tcm_lo = min(tcm_lo, t); tcm_hi = max(tcm_hi, t)
    end
    @printf(
        "   sweep range over these cells' own rows: gdd5 [%.1f, %.1f]  tas_cold [%.2f, %.2f]\n",
        gdd_lo, gdd_hi, tcm_lo, tcm_hi
    )
    flush(stdout)

    # ── PANEL A — POOLED (between-cell) PD. Diagnostic scale only, NOT the response. ─────────────────
    println("\n== PANEL A — POOLED partial dependence (BETWEEN-CELL scale; not the warming response)")
    rng = DRF.Xoshiro256pp(20260813)
    stride = max(1, length(allrows) ÷ POOLED_N)
    pooled = [getrow(allrows[i]) for i in 1:stride:length(allrows)]
    println("   base = $(length(pooled)) pooled rows over all probe cells and both scenarios")
    pooled_amp = Dict{Int, Float64}()
    for (fi, lo, hi) in ((F_GDD, gdd_lo, gdd_hi), (F_TCM, tcm_lo, tcm_hi))
        vals = range(lo, hi; length = NSWEEP)
        pds = [pd_mean(forest, pooled, (fi,), (v,)) for v in vals]
        pooled_amp[fi] = maximum(pds) - minimum(pds)
        @printf(
            "   %-16s PD %.3f -> %.3f stems  (amplitude %.3f)\n",
            colnames[fi], first(pds), last(pds), pooled_amp[fi]
        )
        for k in 1:NSWEEP
            @printf("        %-16s = %10.2f  ->  %8.4f\n", colnames[fi], vals[k], pds[k])
        end
    end
    joint_amp = let
        gv = range(gdd_lo, gdd_hi; length = NSWEEP)
        tv = range(tcm_lo, tcm_hi; length = NSWEEP)
        pds = [pd_mean(forest, pooled, CLIMATE, (gv[k], tv[k])) for k in 1:NSWEEP]
        @printf(
            "   %-16s PD %.3f -> %.3f stems  (amplitude %.3f)\n",
            "JOINT (both)", first(pds), last(pds), maximum(pds) - minimum(pds)
        )
        maximum(pds) - minimum(pds)
    end
    pooled_max = max(pooled_amp[F_GDD], pooled_amp[F_TCM], joint_amp)
    flush(stdout)

    # ── PANELS B / C / D — per cell ──────────────────────────────────────────────────────────────────
    truth = fit_truth(TRUTH)
    println("\n== PANELS B/C/D — per cell. B is THE OPERATIVE RESPONSE; A and D are context.")
    println("   B: climate cols moved hist-terminal -> ssp370-terminal on that cell's own historic rows.")
    println("   C: n_prev moved by that cell's own observed hist->ssp mean shift (a channel known live).")
    println("   D: the full gdd5/tas range swept on THAT cell's rows (is it on a local plateau?).")

    recs = []
    for c in want
        hr = get(rows, (c, hist_code), Int[])
        isempty(hr) && (println("   cell $c: no historic training rows — skipped"); continue)
        bh = terminal_boundary(c, "historic")
        bs = terminal_boundary(c, "ssp370")
        if bh === nothing || bs === nothing
            println("   cell $c: missing a boundary CSV leg — skipped")
            continue
        end
        st = max(1, length(hr) ÷ NBASE)
        base = [getrow(hr[i]) for i in 1:st:length(hr)]

        # B — the operative warming move, marginal and joint
        p_h = pd_mean(forest, base, CLIMATE, (bh[2], bh[3]))
        p_s = pd_mean(forest, base, CLIMATE, (bs[2], bs[3]))
        p_g = pd_mean(forest, base, CLIMATE, (bs[2], bh[3]))   # gdd5 only
        p_t = pd_mean(forest, base, CLIMATE, (bh[2], bs[3]))   # tas_cold only
        d_j = p_s - p_h
        d_g = p_g - p_h
        d_t = p_t - p_h

        # C — scale reference: n_prev moved by its own observed hist->ssp mean shift at this cell
        sr = get(rows, (c, ssp_code), Int[])
        npv_h = sum(Xt[F_NPREV, i] for i in hr) / length(hr)
        npv_s = isempty(sr) ? npv_h : sum(Xt[F_NPREV, i] for i in sr) / length(sr)
        p_n0 = pd_mean(forest, base, (F_NPREV,), (npv_h,))
        p_n1 = pd_mean(forest, base, (F_NPREV,), (npv_s,))
        d_n = p_n1 - p_n0

        # D — local full-range amplitude on this cell's own rows
        gv = range(gdd_lo, gdd_hi; length = NSWEEP)
        tv = range(tcm_lo, tcm_hi; length = NSWEEP)
        loc = [pd_mean(forest, base, CLIMATE, (gv[k], tv[k])) for k in 1:NSWEEP]
        d_loc = maximum(loc) - minimum(loc)

        tr = get(truth, c, NaN)
        frac = isnan(tr) || tr == 0 ? NaN : d_j / tr
        push!(
            recs, (
                cell = c, nbase = length(base), yr_h = bh[1], yr_s = bs[1],
                gdd_h = bh[2], gdd_s = bs[2], tcm_h = bh[3], tcm_s = bs[3],
                pred_h = p_h, pred_s = p_s, d_gdd = d_g, d_tcm = d_t, d_joint = d_j,
                npv_h = npv_h, npv_s = npv_s, d_nprev = d_n, d_localrange = d_loc,
                truth = tr, frac_of_truth = frac,
            )
        )

        @printf("\n   cell %d  (base %d rows, %d -> %d)\n", c, length(base), bh[1], bs[1])
        @printf(
            "     climate move : gdd5 %8.1f -> %8.1f (%+7.1f)   tas_cold %6.2f -> %6.2f (%+5.2f)\n",
            bh[2], bs[2], bs[2] - bh[2], bh[3], bs[3], bs[3] - bh[3]
        )
        @printf(
            "     B predicted  : %.4f -> %.4f stems   Δjoint %+.4f  (gdd5 %+.4f, tas %+.4f)\n",
            p_h, p_s, d_j, d_g, d_t
        )
        @printf(
            "     C n_prev ref : %.3f -> %.3f          Δ      %+.4f  <== a LIVE channel, same units\n",
            npv_h, npv_s, d_n
        )
        @printf("     D local range: amplitude %+.4f over the full gdd5/tas sweep at this cell\n", d_loc)
        if isnan(tr)
            @printf("     FIT truth    : (absent from %s)\n", basename(TRUTH))
        else
            @printf(
                "     FIT truth    : %+.3f stems  ⇒  climate Δ is %.1f%% of FIT's own response\n",
                tr, 100 * frac
            )
        end
        flush(stdout)
    end

    isempty(recs) && (println("\nFATAL: no cell produced a record."); return 1)

    # ── summary + pre-registered verdict ─────────────────────────────────────────────────────────────
    println("\n== SUMMARY (B vs C: is the climate channel small compared with a live one?)")
    println("   cell     Δclimate   Δn_prev   |Δclim|/|Δnprev|   FIT truth   Δclim/truth   Δlocalrange")
    for r in recs
        ratio = r.d_nprev == 0 ? NaN : abs(r.d_joint) / abs(r.d_nprev)
        @printf(
            "   %-8d %+9.4f %+9.4f %17.4f %11.3f %13s %13.4f\n",
            r.cell, r.d_joint, r.d_nprev, ratio, r.truth,
            isnan(r.frac_of_truth) ? "n/a" : @sprintf("%+.3f", r.frac_of_truth), r.d_localrange
        )
    end

    scored = [r for r in recs if !isnan(r.frac_of_truth)]
    ndead = count(r -> abs(r.frac_of_truth) < DEAD_FRAC, scored)
    nlive = count(r -> abs(r.frac_of_truth) > LIVE_FRAC, scored)
    mean_abs_clim = sum(abs(r.d_joint) for r in recs) / length(recs)
    mean_abs_npv = sum(abs(r.d_nprev) for r in recs) / length(recs)
    mean_loc = sum(r.d_localrange for r in recs) / length(recs)

    @printf("\n   scored cells                : %d\n", length(scored))
    @printf("   mean |Δ climate|            : %.4f stems\n", mean_abs_clim)
    @printf(
        "   mean |Δ n_prev| (live ref)  : %.4f stems   ratio climate/n_prev = %.4f\n",
        mean_abs_npv, mean_abs_npv == 0 ? NaN : mean_abs_clim / mean_abs_npv
    )
    @printf("   mean local full-range ampl. : %.4f stems\n", mean_loc)
    @printf("   pooled full-range amplitude : %.4f stems (panel A max)\n", pooled_max)
    @printf("   cells with |Δclim| < %.2f x truth : %d / %d\n", DEAD_FRAC, ndead, length(scored))
    @printf("   cells with |Δclim| > %.2f x truth : %d / %d\n", LIVE_FRAC, nlive, length(scored))

    println("\n== VERDICT (thresholds fixed in this file before the run)")
    verdict = if clim_splits == 0
        "H1 — the forest has NO splits on either climate feature; the channel is dead by construction."
    elseif nlive >= length(scored) / 2
        "H2 — the artifact HAS a within-cell climate response of the right order; the free-running " *
            "loop is not expressing it. Look at the loop, not the training."
    elseif ndead >= 2 * length(scored) / 3
        if pooled_max > POOLED_AMP
            "H3 — the forest learned a LARGE climate surface BETWEEN cells (pooled amplitude " *
                @sprintf("%.2f", pooled_max) * " stems) but is FLAT over the within-cell warming " *
                "excursion. It learned climate as a cell identifier, not as a response. The defect is " *
                "the training DESIGN: the between-cell gradient is not the within-cell temporal contrast."
        else
            "H1 — flat within cells AND flat over the full range; the training target / feature set " *
                "is the defect."
        end
    else
        "MIXED — neither threshold is met at the pre-registered majority. Report the per-cell table; " *
            "do not collapse it to one hypothesis."
    end
    println("   ", verdict)

    open(OUT, "w") do io
        println(io, "# Component-S count model: partial dependence on the two transient climate features.")
        println(io, "# probe scripts/slow_climate_partial_dependence_probe.jl · artifact ", basename(DRFP))
        println(io, "# table ", basename(TAB), " · boundary ", BND)
        println(io, "# d_joint = predicted Δ stems when ONLY gdd5+tas_cold move from that cell's historic")
        println(io, "#   terminal to its ssp370 terminal, averaged over that cell's own historic rows.")
        println(io, "# d_nprev = the same for n_prev over its own observed hist->ssp shift (live-channel ref).")
        println(io, "# d_localrange = amplitude over the FULL gdd5/tas sweep at this cell (local plateau test).")
        println(io, "# truth = FIT's own terminal count response. VERDICT: ", verdict)
        println(
            io, "cell,nbase,yr_h,yr_s,gdd_h,gdd_s,tcm_h,tcm_s,pred_h,pred_s,",
            "d_gdd,d_tcm,d_joint,npv_h,npv_s,d_nprev,d_localrange,truth,frac_of_truth"
        )
        for r in recs
            @printf(
                io, "%d,%d,%d,%d,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f\n",
                r.cell, r.nbase, r.yr_h, r.yr_s, r.gdd_h, r.gdd_s, r.tcm_h, r.tcm_s,
                r.pred_h, r.pred_s, r.d_gdd, r.d_tcm, r.d_joint,
                r.npv_h, r.npv_s, r.d_nprev, r.d_localrange, r.truth, r.frac_of_truth
            )
        end
    end
    println("\n   wrote ", OUT)
    return 0
end

exit(main())
