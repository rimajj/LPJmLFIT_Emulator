#!/usr/bin/env julia
# slow_stand_forced_response_probe.jl — HAND THE COUNT MODEL LPJmL-FIT'S OWN STAND AND ASK FOR THE
# WARMING RESPONSE. Does the stand->count map fail, or does the coupled loop never move the stand?
#
# WHY THIS EXISTS (ADR 0179 -> 0180 -> this). ADR 0180 established two things and left one question open:
#   * the count target is NEARLY DETERMINED by the contemporaneous stand description — with `n_prev`
#     neutralised the remaining 13 features still reach R2 0.9620 against the persistence null's 0.9623;
#   * at RUNTIME the six stand features are computed from the fast core's OWN pools, not from FIT, so that
#     is not a leak there — but it means the coupled warming response has to arrive THROUGH the stand.
# Whether that is the MAP's fault or the fast core's was left as the "one question that could redirect this
# whole effort", explicitly as a table scan. This is it.
#
# ⚠ AND IT CORRECTS A READING OF ADR 0178 THAT ADR 0180 AND THE LINE HANDOFF BOTH INHERITED. Those texts
# say "ADR 0178 measured that pathway as ~0". ADR 0178 measured something narrower. Its frozen arm freezes
# ONLY the 4 boundary columns (`build_rung2_boundary_series.py --freeze` writes
# Year,eco_diag_gdd_5,tas_cold_month,soil_depth,co2 and nothing else); the other 11 features stay LIVE on
# the C-grown roster, and the C still runs under transient ssp370 forcing. So its `climate` term is the
# DIRECT boundary-feature channel, and any response arriving through the warmed stand lands in its `drift`
# bucket by construction. The stand-mediated pathway was never isolated. That is what PANEL 3 isolates.
#
# ── REFERENCE BASIS (stated before any number is read; residual-diagnosis §1) ─────────────────────────
#   table     : $TAB = slow_count_pooled_w20_t8 — the exact table the shipped artifact was fitted on.
#               n = 121 495 658 rows, p = 15, 58 588 cells, scenarios POOLED (`scenario.i64` 0=historic
#               1=ssp370). Every feature in it is built from LPJmL-FIT's own roster/fluxes for that very
#               (Cell, Patch, Year) — so every arm here is ONE-STEP, C-FORCED (ADR 0112's first label).
#               There is NO free-running loop anywhere in this probe. That is the point.
#   response  : per cell, `mean(y | ssp370 leg) − mean(y | historic leg)` — stems per patch. This is
#               BYTE-FOR-BYTE the definition `diagnose_truth_yardstick.py::score_counts` uses, so the arms
#               below land on the same axis as the published shipped-artifact (area-weighted 0.707,
#               per-cell deattenuated 1.006) and persistence-null (0.685 / 1.029) numbers.
#   yardstick : the two ground-truth seeds via `diagnose_truth_yardstick.py` (run separately on the
#               COUNT_DIRs this probe writes). Nothing here invents its own truth.
#   OOS       : K-FOLD BY CELL. A cell's rows are predicted only by a forest that never saw that cell.
#               Same holdout geometry as every published Component-S number.
#
# ── THE HYPOTHESIS (pre-registered, with the thresholds fixed below before the run) ───────────────────
#   H_map: the stand->count map can express FIT's warming response when it is handed FIT's OWN stand —
#          i.e. the map is fine and the coupled failure is that the fast core does not move the stand.
#
#   Falsifiable prediction: with the lagged-truth shortcut REMOVED (`n_prev` neutralised in place, the
#   ADR 0180 ablation), the per-cell response slope and the area-weighted aggregate response ratio stay
#   near the shipped artifact's. If instead they collapse toward zero, the shipped artifact's apparent
#   one-step response was persistence and the map itself cannot express the response — which confirms
#   ADR 0180 §4's [ASSUMPTION] and points the work at the target/feature construction.
#
#   ⚠ THE CONTROL IS NOT OPTIONAL AND IT IS WHY THE ABLATED ARM IS THE HEADLINE (ADR 0112). The FULL
#   feature set contains `n_prev` = FIT's own previous-year count, and the persistence null already scores
#   an aggregate ratio of 0.685 against the shipped model's 0.707. So the CTRL arm HAS NO POWER on this
#   statistic by construction; it is here as a basis check (it must reproduce the shipped artifact), not
#   as evidence. ABL is the arm that can fail.
#
# ── PANELS ───────────────────────────────────────────────────────────────────────────────────────────
#   0  BASIS CHECKS      — (a) the persistence null's R2 on this sample must reproduce the published
#                          0.9622/0.9623; (b) CTRL's holdout R2 and climate split share must reproduce the
#                          shipped artifact's 0.9824 / 10.20 %. Both are read BEFORE any arm.
#   1  DOES FIT'S OWN STAND EVEN MOVE?  — per cell, the historic->ssp370 leg shift of each of the 15
#                          features in units of that cell's own within-leg sd. If FIT's stand barely moves
#                          while FIT's count moves, no stand-driven map can produce the response and the
#                          question is settled without a single forest. This panel is a pure table scan.
#   2  THE RESPONSE      — CTRL and ABL K-fold-by-cell OOS predictions written as COUNT_DIRs for
#                          `diagnose_truth_yardstick.py`. THE HEADLINE.
#   3  WHICH CHANNEL CARRIES IT — per cell, the response decomposed by moving one feature GROUP at a time
#                          from that cell's historic leg mean to its ssp370 leg mean, everything else held
#                          on that cell's own historic rows:
#                            FLUX  (1-4)   bm_inc_cell growth_eff water_stress soilmoist  <- F's daily physics
#                            STAND (5-10)  hmean hmax agb lai fpc age_mean                <- F's own pools
#                            AR    (11)    n_prev                                          <- the emulator's state
#                            CLIM  (12-13) eco_diag_gdd_5 tas_cold_month                   <- the boundary
#                          At runtime each group is computed by a DIFFERENT part of the system, so this
#                          panel says which part must carry the response — the deliverable ADR 0180 §4 asked
#                          for. `soil_depth` (14) and `co2` (15) are per-cell constants / designed-out
#                          (ADR 0004/0107) and are never moved.
#                          ⚠ ABL's AR corner must be EXACTLY 0 by construction — that is this panel's own
#                          internal check that the neutralisation is really in force at prediction time.
#
# ── NOTES ON THE DESIGN (one variable at a time; ADR 0126 §5) ─────────────────────────────────────────
#   * `n_prev` is neutralised IN PLACE (overwritten with its own sample mean) rather than dropped, so p,
#     the column indices and `mtry` = round(sqrt(15)) = 4 are identical between arms; a constant column can
#     be drawn as an mtry candidate but can never win a split (ADR 0180 §2).
#   * CTRL is RETRAINED here rather than compared against the shipped artifact, because the shipped one saw
#     all 121 495 658 rows while these arms see a systematic sample — comparing across that difference
#     would confound the row set with the ablation (ADR 0048 §4).
#   * The sample is SYSTEMATIC RANDOM (one uniformly-drawn row per consecutive block), not a fixed stride:
#     the table is sorted (Cell, Patch, Year), so a fixed stride of 25 would sample one patch index forever.
#
# ENV: TAB, OUT, PSTRIDE, TSUB, KFOLD, NTREES, MAX_DEPTH, MIN_LEAF, SUBSAMPLE, SEED, NBASE
# Run: NCPUS=16 TIME=03:00:00 scripts/sbatch_julia.sh S-standforce --project=. scripts/slow_stand_forced_response_probe.jl
#      (NCPUS, not CPUS — sbatch_julia.sh sets JULIA_NUM_THREADS from it. EXPORT every knob above.)

using Printf
using Mmap

include(joinpath(@__DIR__, "..", "src", "drf.jl"))
using .DRF

const GLOB = "/p/tmp/jamirp/emulator_global"
const TAB = get(ENV, "TAB", joinpath(GLOB, "slow_count_pooled_w20_t8"))
const OUT = get(ENV, "OUT", joinpath(GLOB, "S_stand_forced_response"))

const PSTRIDE = parse(Int, get(ENV, "PSTRIDE", "4"))     # master sample: 1 row per PSTRIDE-row block
const TSUB = parse(Int, get(ENV, "TSUB", "4"))           # train on every TSUB-th master row
const KFOLD = parse(Int, get(ENV, "KFOLD", "5"))
const NTREES = parse(Int, get(ENV, "NTREES", "150"))
const MAX_DEPTH = parse(Int, get(ENV, "MAX_DEPTH", "16"))
const MIN_LEAF = parse(Int, get(ENV, "MIN_LEAF", "20"))
const SUBSAMPLE = parse(Int, get(ENV, "SUBSAMPLE", "200000"))
const SEED = parse(Int, get(ENV, "SEED", "1"))
const NBASE = parse(Int, get(ENV, "NBASE", "25"))

const F_NPREV = 11
const GROUPS = (
    ("FLUX", 1:4),
    ("STAND", 5:10),
    ("AR", 11:11),
    ("CLIM", 12:13),
)

# ── pre-registered verdict thresholds (fixed HERE, before the run) ───────────────────────────────────
const PASS_AGG = 0.5      # ABL area-weighted aggregate response ratio at or above this ...
const PASS_SLOPE = 0.7    # ... AND per-cell slope at or above this  => H_map SUPPORTED
const FAIL_AGG = 0.2      # ABL aggregate ratio at or below this ...
const FAIL_SLOPE = 0.3    # ... OR per-cell slope at or below this   => H_map REFUTED

read_manifest(p) = Dict(
    pp[1] => pp[2] for pp in
        (split(l, '\t') for l in eachline(p)) if length(pp) == 2
)

# deterministic cell -> fold, independent of cell ordering (a contiguous block split would confound the
# fold with geography; the table is sorted by Cell)
@inline foldof(cell::Int, k::Int) = Int((UInt64(cell) * 0x9E3779B97F4A7C15) >> 33 % UInt64(k)) + 1

function write_count_dir(dir, cells, scen, y, pred, man, note)
    mkpath(dir)
    write(joinpath(dir, "cells.i64"), cells)
    write(joinpath(dir, "scenario.i64"), scen)
    write(joinpath(dir, "y.f64"), y)
    write(joinpath(dir, "preds_oos.f64"), pred)
    open(joinpath(dir, "manifest.txt"), "w") do io
        println(io, "n\t", length(y))
        println(io, "p\t", man["p"])
        println(io, "colnames\t", man["colnames"])
        println(io, "target\t", man["target"])
        println(io, "scenario\tpooled")
        println(io, "pooled_scenarios\t", get(man, "pooled_scenarios", "historic ssp370"))
        println(io, "scenario_tag\tscenario.i64")
        println(io, "source_table\t", basename(TAB))
        println(io, "arm\t", note)
    end
    return nothing
end

function main()
    println("="^100)
    println("== slow_stand_forced_response_probe — drive the count model with FIT's OWN stand")
    println("   table : ", TAB)
    println("   out   : ", OUT)
    @printf(
        "   design: K=%d folds BY CELL · master stride %d · train every %d-th master row\n",
        KFOLD, PSTRIDE, TSUB
    )
    @printf(
        "   hyper : ntrees=%d depth=%d min_leaf=%d subsample=%d seed=%d · threads=%d\n",
        NTREES, MAX_DEPTH, MIN_LEAF, SUBSAMPLE, SEED, Threads.nthreads()
    )
    flush(stdout)

    man = read_manifest(joinpath(TAB, "manifest.txt"))
    n = parse(Int, man["n"])
    p = parse(Int, man["p"])
    colnames = String.(split(strip(man["colnames"])))
    @assert length(colnames) == p
    @assert colnames[F_NPREV] == "n_prev"
    @assert colnames[12] == "eco_diag_gdd_5"
    @assert colnames[13] == "tas_cold_month"

    # ── master systematic random sample ──────────────────────────────────────────────────────────────
    print("   sampling master rows ... ")
    flush(stdout)
    t0 = time()
    rng = DRF.Xoshiro256pp(SEED)
    nblk = n ÷ PSTRIDE
    idx = Vector{Int}(undef, nblk)
    @inbounds for b in 1:nblk
        idx[b] = (b - 1) * PSTRIDE + DRF.rand_range!(rng, PSTRIDE)
    end
    Xt = open(io -> Mmap.mmap(io, Matrix{Float64}, (p, n)), joinpath(TAB, "X.f64"))
    yall = open(io -> Mmap.mmap(io, Vector{Float64}, n), joinpath(TAB, "y.f64"))
    call = open(io -> Mmap.mmap(io, Vector{Int64}, n), joinpath(TAB, "cells.i64"))
    sall = open(io -> Mmap.mmap(io, Vector{Int64}, n), joinpath(TAB, "scenario.i64"))

    m = nblk
    X = Matrix{Float64}(undef, m, p)
    y = Vector{Float64}(undef, m)
    cm = Vector{Int64}(undef, m)
    sm = Vector{Int64}(undef, m)
    @inbounds for (k, i) in enumerate(idx)
        for f in 1:p
            X[k, f] = Xt[f, i]
        end
        y[k] = yall[i]
        cm[k] = call[i]
        sm[k] = sall[i]
    end
    @printf("%d rows in %.1f s (%.2f GB)\n", m, time() - t0, m * p * 8 / 2^30)
    flush(stdout)

    ybar = sum(y) / m
    sst = sum((v - ybar)^2 for v in y)
    npbar = sum(@view X[:, F_NPREV]) / m

    # ── PANEL 0a — the persistence null on THIS sample (must reproduce the published 0.9622/0.9623) ──
    ssr_np = sum((y[i] - X[i, F_NPREV])^2 for i in 1:m)
    r2_null = 1 - ssr_np / sst
    println("\n", "-"^100)
    println("-- PANEL 0a  BASIS CHECK: the persistence null (y ~ n_prev, no fit) on this sample")
    @printf("   target n_living: mean %.4f  sd %.4f   |   n_prev mean %.6f\n", ybar, sqrt(sst / (m - 1)), npbar)
    @printf(
        "   persistence-null R2 = %.4f   (published: 0.9622 full table / 0.9623 ADR 0180 sample)  %s\n",
        r2_null, abs(r2_null - 0.9622) < 0.005 ? "OK" : "⚠ OFF-BASIS — stop and check the table"
    )
    flush(stdout)

    # ── per-cell, per-scenario accumulators (one pass; feeds panels 1 and 3) ─────────────────────────
    cell_ids = sort!(collect(Set(Int.(cm))))
    cidx = Dict(c => i for (i, c) in enumerate(cell_ids))
    nc = length(cell_ids)
    cnt = zeros(Int, nc, 2)
    fsum = zeros(Float64, nc, 2, p)
    fsq = zeros(Float64, nc, 2, p)
    ysum = zeros(Float64, nc, 2)
    basrows = [Int[] for _ in 1:nc]
    @inbounds for k in 1:m
        ci = cidx[Int(cm[k])]
        si = Int(sm[k]) + 1
        cnt[ci, si] += 1
        ysum[ci, si] += y[k]
        for f in 1:p
            v = X[k, f]
            fsum[ci, si, f] += v
            fsq[ci, si, f] += v * v
        end
        if si == 1 && length(basrows[ci]) < NBASE
            push!(basrows[ci], k)
        end
    end
    @printf("   cells in sample: %d   (table declares %s)\n", nc, get(man, "ncells", "?"))

    # cells usable for the per-cell panels: both legs present with enough rows for a leg mean
    usable = [ci for ci in 1:nc if cnt[ci, 1] >= 10 && cnt[ci, 2] >= 10 && !isempty(basrows[ci])]
    @printf("   cells with >=10 rows in BOTH legs: %d\n", length(usable))
    if isempty(usable)
        println("\n   FATAL: no cell has >=10 sampled rows in BOTH legs — PSTRIDE=$PSTRIDE is too coarse")
        println("   for a per-cell leg mean (a per-cell response cannot be formed). Lower PSTRIDE.")
        println("   This is a CONFIGURATION error, not a result: nothing about the model was measured.")
        return 2
    end
    flush(stdout)

    # ── PANEL 1 — does FIT's OWN stand move between the legs? ────────────────────────────────────────
    println("\n", "-"^100)
    println("-- PANEL 1  DOES FIT'S OWN STAND MOVE?  historic->ssp370 leg shift of each feature,")
    println("            in units of that cell's own WITHIN-LEG sd. Pure table scan, no model.")
    println("            (A map driven by the stand cannot produce a response the stand does not carry.)")
    @printf(
        "   %-16s %10s %12s %12s %12s %10s\n",
        "feature", "group", "med |Δ|", "med |Δ|/sd", "p90 |Δ|/sd", "frac>0.5sd"
    )
    grpof = fill("const", p)
    for (gname, gr) in GROUPS, f in gr
        grpof[f] = gname
    end
    dz_all = zeros(Float64, length(usable), p)
    for f in 1:p
        dabs = Float64[]
        dz = Float64[]
        for (j, ci) in enumerate(usable)
            mh = fsum[ci, 1, f] / cnt[ci, 1]
            ms = fsum[ci, 2, f] / cnt[ci, 2]
            vh = max(0.0, fsq[ci, 1, f] / cnt[ci, 1] - mh * mh)
            vs = max(0.0, fsq[ci, 2, f] / cnt[ci, 2] - ms * ms)
            sd = sqrt(0.5 * (vh + vs))
            d = ms - mh
            push!(dabs, abs(d))
            z = sd > 0 ? abs(d) / sd : 0.0
            push!(dz, z)
            dz_all[j, f] = z
        end
        sort!(dabs)
        sort!(dz)
        nu = length(dz)
        @printf(
            "   %-16s %10s %12.5g %12.3f %12.3f %10.3f\n",
            colnames[f], grpof[f], dabs[(nu + 1) ÷ 2], dz[(nu + 1) ÷ 2],
            dz[max(1, round(Int, 0.9 * nu))], count(>(0.5), dz) / nu
        )
    end
    # the target's own move, on the same rows, for scale
    dy = [ysum[ci, 2] / cnt[ci, 2] - ysum[ci, 1] / cnt[ci, 1] for ci in usable]
    sdy = Float64[]
    for ci in usable
        mh = ysum[ci, 1] / cnt[ci, 1]
        push!(sdy, mh)
    end
    ady = sort(abs.(dy))
    @printf(
        "   %-16s %10s %12.5g %12s %12s %10s   <- the TARGET's own leg shift (stems/patch)\n",
        "n_living(y)", "target", ady[(length(ady) + 1) ÷ 2], "-", "-", "-"
    )
    @printf(
        "   global mean target response %+.5f stems/patch over %d cells (FIT's own, seed1, this sample)\n",
        sum(dy) / length(dy), length(dy)
    )
    flush(stdout)

    # ── PANEL 2 — K-fold-by-cell OOS predictions for CTRL and ABL ───────────────────────────────────
    println("\n", "-"^100)
    println("-- PANEL 2  THE RESPONSE: K-fold-by-cell OOS predictions, CTRL (as-is) vs ABL (n_prev const)")
    pred_ctrl = fill(NaN, m)
    pred_abl = fill(NaN, m)
    fold_of_row = Vector{Int}(undef, m)
    @inbounds for k in 1:m
        fold_of_row[k] = foldof(Int(cm[k]), KFOLD)
    end
    forests_ctrl = Vector{Any}(undef, KFOLD)
    forests_abl = Vector{Any}(undef, KFOLD)
    r2s = Dict("CTRL" => Float64[], "ABL" => Float64[])
    shares = Dict("CTRL" => zeros(Float64, p), "ABL" => zeros(Float64, p))

    for k in 1:KFOLD
        trrows = Int[]
        terows = Int[]
        @inbounds for i in 1:m
            if fold_of_row[i] == k
                push!(terows, i)
            elseif i % TSUB == 0
                push!(trrows, i)
            end
        end
        @printf("   fold %d/%d: train %d rows · score %d rows ... ", k, KFOLD, length(trrows), length(terows))
        flush(stdout)
        t1 = time()
        Xtr = X[trrows, :]
        ytr = y[trrows]
        Xte = X[terows, :]
        for arm in ("CTRL", "ABL")
            Xa = Xtr
            Xb = Xte
            if arm == "ABL"
                Xa = copy(Xtr)
                Xb = copy(Xte)
                @inbounds for i in axes(Xa, 1)
                    Xa[i, F_NPREV] = npbar
                end
                @inbounds for i in axes(Xb, 1)
                    Xb[i, F_NPREV] = npbar
                end
            end
            fo = DRF.fit_forest(
                Xa, ytr; ntrees = NTREES, max_depth = MAX_DEPTH,
                min_leaf = MIN_LEAF, subsample = SUBSAMPLE, seed = SEED
            )
            pv = DRF.predict(fo, Xb)
            if arm == "CTRL"
                forests_ctrl[k] = fo
                @inbounds for (j, i) in enumerate(terows)
                    pred_ctrl[i] = pv[j]
                end
            else
                forests_abl[k] = fo
                @inbounds for (j, i) in enumerate(terows)
                    pred_abl[i] = pv[j]
                end
            end
            yte = y[terows]
            yb = sum(yte) / length(yte)
            ss = sum((yte[j] - pv[j])^2 for j in eachindex(yte))
            push!(r2s[arm], 1 - ss / sum((v - yb)^2 for v in yte))
            ns = zeros(Int, p)
            for tree in fo.trees, nid in eachindex(tree.feat)
                f = tree.feat[nid]
                f != 0 && (ns[f] += 1)
            end
            tot = sum(ns)
            for f in 1:p
                shares[arm][f] += 100 * ns[f] / tot / KFOLD
            end
        end
        @printf("%.1f s\n", time() - t1)
        flush(stdout)
    end

    @assert all(isfinite, pred_ctrl) "some rows were never scored — the fold map is not a partition"
    @assert all(isfinite, pred_abl)

    println("\n-- PANEL 0b  BASIS CHECK: CTRL must reproduce the SHIPPED artifact")
    @printf(
        "   CTRL OOS R2 (mean over folds) %.4f   (shipped OOS 0.9824)  %s\n",
        sum(r2s["CTRL"]) / KFOLD, abs(sum(r2s["CTRL"]) / KFOLD - 0.9824) < 0.01 ? "OK" : "⚠ CHECK"
    )
    cs_c = shares["CTRL"][12] + shares["CTRL"][13]
    cs_a = shares["ABL"][12] + shares["ABL"][13]
    @printf(
        "   CTRL climate split share %.2f %%   (shipped 10.20 %%)  %s\n",
        cs_c, abs(cs_c - 10.2) < 1.5 ? "OK" : "⚠ CHECK"
    )
    @printf(
        "   ABL  OOS R2 %.4f   climate split share %.2f %%   n_prev share %.2f %% (must be 0.00)\n",
        sum(r2s["ABL"]) / KFOLD, cs_a, shares["ABL"][F_NPREV]
    )
    println("   per-feature split share (CTRL | ABL):")
    for f in 1:p
        @printf(
            "     %-16s %6.2f %% | %6.2f %%%s\n", colnames[f], shares["CTRL"][f], shares["ABL"][f],
            shares["CTRL"][f] == 0 ? "   <- NO SPLITS (channel closed by construction)" : ""
        )
    end
    flush(stdout)

    mkpath(OUT)
    write_count_dir(joinpath(OUT, "ctrl"), cm, sm, y, pred_ctrl, man, "CTRL (table as-is, K-fold by cell)")
    write_count_dir(joinpath(OUT, "abl"), cm, sm, y, pred_abl, man, "ABL (n_prev := constant, K-fold by cell)")
    println("\n   wrote COUNT_DIRs: ", joinpath(OUT, "ctrl"), "  and  ", joinpath(OUT, "abl"))
    println("   score them with (THIS is where the binding statistic comes from — see the verdict):")
    println(
        "     export COUNT_DIR=", TAB, ",", GLOB, "/rung1_count_null_persistence,",
        joinpath(OUT, "ctrl"), ",", joinpath(OUT, "abl")
    )
    println("     export OUT_SUMMARY=", joinpath(OUT, "yardstick_summary.csv"), "   # ⚠ NOT optional")
    println("     scripts/sbatch_python.sh S-standforce-score scripts/diagnose_truth_yardstick.py")
    println("   ⚠ OUT_SUMMARY MUST be redirected from a line worktree: its default is the COMMITTED")
    println("     shared fixture test/testitems/references/S_truth_yardstick_summary.csv, and a")
    println("     COUNT_DIR-only run DROPS every trait row from it — silently regenerating a shared")
    println("     baseline, which is an integration point (CLAUDE.md §9), not a side effect.")

    # in-probe per-cell slope, so the verdict does not depend on a second job
    dpc = Float64[]
    dpa = Float64[]
    dyv = Float64[]
    pc_h = zeros(Float64, nc)
    pc_s = zeros(Float64, nc)
    pa_h = zeros(Float64, nc)
    pa_s = zeros(Float64, nc)
    @inbounds for k in 1:m
        ci = cidx[Int(cm[k])]
        if Int(sm[k]) == 0
            pc_h[ci] += pred_ctrl[k]
            pa_h[ci] += pred_abl[k]
        else
            pc_s[ci] += pred_ctrl[k]
            pa_s[ci] += pred_abl[k]
        end
    end
    for ci in usable
        push!(dyv, ysum[ci, 2] / cnt[ci, 2] - ysum[ci, 1] / cnt[ci, 1])
        push!(dpc, pc_s[ci] / cnt[ci, 2] - pc_h[ci] / cnt[ci, 1])
        push!(dpa, pa_s[ci] / cnt[ci, 2] - pa_h[ci] / cnt[ci, 1])
    end
    sl(dp, dt) = sum(dp .* dt) / sum(dt .* dt)
    slope_c = sl(dpc, dyv)
    slope_a = sl(dpa, dyv)
    # unweighted global mean ratio is NOT the blessed aggregate (ADR 0111 §5b) — the area-weighted one
    # comes from diagnose_truth_yardstick.py. This is the through-origin per-cell slope only.
    println("\n-- PANEL 2 (in-probe, per-cell through-origin slope vs the TABLE's own seed1 response)")
    @printf("   cells scored %d\n", length(dyv))
    @printf("   CTRL slope %.4f   ABL slope %.4f   ABL/CTRL %.3f\n", slope_c, slope_a, slope_a / slope_c)
    @printf(
        "   mean |truth Δ| %.4f   mean |CTRL Δ| %.4f   mean |ABL Δ| %.4f stems/patch\n",
        sum(abs, dyv) / length(dyv), sum(abs, dpc) / length(dpc), sum(abs, dpa) / length(dpa)
    )
    @printf(
        "   sign agreement with FIT: CTRL %.3f   ABL %.3f\n",
        count(j -> sign(dpc[j]) == sign(dyv[j]), eachindex(dyv)) / length(dyv),
        count(j -> sign(dpa[j]) == sign(dyv[j]), eachindex(dyv)) / length(dyv)
    )
    flush(stdout)

    # ── PANEL 3 — which feature GROUP carries the response ──────────────────────────────────────────
    println("\n", "-"^100)
    println("-- PANEL 3  WHICH CHANNEL CARRIES IT: move ONE group from the cell's historic leg mean to")
    println("            its ssp370 leg mean, everything else on that cell's own historic rows.")
    println("            At runtime FLUX and STAND come from the fast core, CLIM from the boundary,")
    println("            AR from the emulator's own state — so this says which part must carry it.")
    gnames = [g[1] for g in GROUPS]
    push!(gnames, "ALL")
    res = Dict(a => Dict(g => Float64[] for g in gnames) for a in ("CTRL", "ABL"))
    xrow = [Vector{Float64}(undef, p) for _ in 1:Threads.nthreads()]
    for ci in usable
        c = cell_ids[ci]
        kf = foldof(c, KFOLD)
        base = basrows[ci]
        for arm in ("CTRL", "ABL")
            fo = arm == "CTRL" ? forests_ctrl[kf] : forests_abl[kf]
            function ev(mask)
                s = 0.0
                x = xrow[1]
                for r in base
                    @inbounds for f in 1:p
                        x[f] = mask[f] ? fsum[ci, 2, f] / cnt[ci, 2] : X[r, f]
                    end
                    arm == "ABL" && (x[F_NPREV] = npbar)
                    s += DRF.predict(fo, x)
                end
                return s / length(base)
            end
            b0 = ev(falses(p))
            for (gname, gr) in GROUPS
                mk = falses(p)
                mk[gr] .= true
                push!(res[arm][gname], ev(mk) - b0)
            end
            mkall = falses(p)
            for (_, gr) in GROUPS
                mkall[gr] .= true
            end
            push!(res[arm]["ALL"], ev(mkall) - b0)
        end
    end
    truth_bar = sum(abs, dyv) / length(dyv)
    @printf("\n   mean |FIT's own response| over these cells: %.4f stems/patch\n", truth_bar)
    @printf(
        "   %-6s %-8s %12s %12s %12s %10s\n", "arm", "group", "mean Δ", "mean |Δ|",
        "|Δ| / truth", "slope"
    )
    for arm in ("CTRL", "ABL"), g in gnames
        v = res[arm][g]
        @printf(
            "   %-6s %-8s %12.5f %12.5f %12.3f %10.4f\n", arm, g,
            sum(v) / length(v), sum(abs, v) / length(v), (sum(abs, v) / length(v)) / truth_bar,
            sl(v, dyv)
        )
    end
    ar_abl = sum(abs, res["ABL"]["AR"]) / length(res["ABL"]["AR"])
    @printf(
        "\n   internal check — ABL's AR corner must be EXACTLY 0 (n_prev is constant there): %.3e  %s\n",
        ar_abl, ar_abl == 0.0 ? "OK" : "⚠ the neutralisation is NOT in force at prediction time"
    )
    flush(stdout)

    # ── VERDICT ─────────────────────────────────────────────────────────────────────────────────────
    println("\n", "="^100)
    println("== VERDICT — PENDING BY DESIGN. This script CANNOT decide H_map.")
    println()
    println("   ⚠ THE PER-CELL SLOPE ABOVE HAS NO POWER AND IS NOT THE VERDICT STATISTIC (ADR 0112).")
    println("     The persistence null — a model that copies FIT's previous-year answer and learns")
    println("     nothing — scores a deattenuated per-cell count slope of 1.029 on this very axis, so a")
    println("     slope near 1 is what EVERY arm returns and it discriminates nothing. It is printed as a")
    println("     diagnostic only. (The first version of this file keyed its verdict on it and therefore")
    println("     printed `H_map SUPPORTED` for an arm the binding statistic scores as PARTIAL.)")
    println()
    @printf(
        "   The BINDING statistic is the AREA-WEIGHTED aggregate response ratio (ADR 0111 §5b, the ONE\n" *
            "   blessed definition), from diagnose_truth_yardstick.py on the COUNT_DIRs written above.\n" *
            "   Pre-registered thresholds, fixed in this file before the run, read on the ABL arm:\n" *
            "     aggregate >= %.2f AND per-cell slope >= %.2f   => H_map SUPPORTED\n" *
            "     aggregate <= %.2f OR  per-cell slope <= %.2f   => H_map REFUTED\n" *
            "     otherwise                                      => H_map PARTIAL\n",
        PASS_AGG, PASS_SLOPE, FAIL_AGG, FAIL_SLOPE
    )
    @printf(
        "   This run's ABL per-cell slope is %.4f (CTRL %.4f). Reference values on the same axis:\n" *
            "     shipped artifact 0.707 aggregate / 1.006 deattenuated · persistence null 0.685 / 1.029.\n",
        slope_a, slope_c
    )
    println("   Run the scoring job, then record the verdict against those thresholds in the ADR.")

    open(joinpath(OUT, "summary.csv"), "w") do io
        println(io, "# slow_stand_forced_response_probe · table ", basename(TAB))
        println(io, "# VERDICT: PENDING — the binding statistic is the area-weighted aggregate response")
        println(io, "#   ratio from diagnose_truth_yardstick.py on the ctrl/ and abl/ COUNT_DIRs beside")
        println(io, "#   this file. The per-cell slope below has NO POWER (ADR 0112) and is diagnostic.")
        println(io, "arm,group,mean_d,mean_abs_d,frac_of_truth,slope_vs_truth")
        for arm in ("CTRL", "ABL"), g in gnames
            v = res[arm][g]
            @printf(
                io, "%s,%s,%.6f,%.6f,%.6f,%.6f\n", arm, g, sum(v) / length(v),
                sum(abs, v) / length(v), (sum(abs, v) / length(v)) / truth_bar, sl(v, dyv)
            )
        end
        println(io, "# arm,oos_r2,climate_split_share,nprev_split_share,percell_slope")
        @printf(io, "# CTRL,%.6f,%.4f,%.4f,%.6f\n", sum(r2s["CTRL"]) / KFOLD, cs_c, shares["CTRL"][F_NPREV], slope_c)
        @printf(io, "# ABL,%.6f,%.4f,%.4f,%.6f\n", sum(r2s["ABL"]) / KFOLD, cs_a, shares["ABL"][F_NPREV], slope_a)
        @printf(io, "# persistence_null_r2,%.6f\n", r2_null)
        println(io, "# feature,group,med_abs_leg_shift_over_sd")
        for f in 1:p
            v = sort([dz_all[j, f] for j in axes(dz_all, 1)])
            @printf(io, "# %s,%s,%.6f\n", colnames[f], grpof[f], v[(length(v) + 1) ÷ 2])
        end
    end
    println("\n   wrote ", joinpath(OUT, "summary.csv"))
    return 0
end

exit(main())
