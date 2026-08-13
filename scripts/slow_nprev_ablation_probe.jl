#!/usr/bin/env julia
# slow_nprev_ablation_probe.jl — is the count model's DEAD CLIMATE CHANNEL caused by `n_prev`?
#
# WHY (follows scripts/slow_climate_partial_dependence_probe.jl, job 1771609). That probe measured the
# shipped pooled forest and found something more specific than "it never learned climate":
#   * the climate channel is structurally WIDE OPEN — 77 440 splits on eco_diag_gdd_5 + tas_cold_month,
#     10.20 % of all splits, thresholds spanning 266.9-9743 and -45.7-28.9, i.e. the whole global range;
#   * and yet the partial dependence over that ENTIRE global range is 0.227 stems (gdd5) / 0.066
#     (tas_cold) / 0.281 (joint), against a live-channel (`n_prev`) reference of 1.278 stems and FIT's own
#     per-cell warming responses of 0.2-5.2 stems. Mean |Δ climate| over the operative per-cell warming
#     excursion: 0.057 stems = 4.4 % of the `n_prev` channel, < 10 % of FIT's own response at 9 of 12 cells.
#
# So the splits exist and carry almost no marginal effect. THE HYPOTHESIS THIS ARM TESTS:
#
#   H_nprev: `n_prev` — which is FIT's OWN previous-year count for the same (Cell, Patch), i.e. the
#            teacher-forcing leak ADR 0112 identified — already determines the target, so no other
#            feature has anything left to explain. Climate splits therefore reduce variance enough to be
#            CHOSEN at a node, but the leaf values either side of them barely differ, and the marginal
#            effect averages to ~0. Under H_nprev the climate channel is not missing from the DATA, only
#            from the FITTED FUNCTION, and removing the leak should open it.
#
#   Falsifiable prediction: neutralise `n_prev` and the climate PD amplitude RISES substantially. If it
#   stays flat, the within-cell climate signal is absent from the training target itself and no amount of
#   de-leaking will produce a response — which is a different and much more expensive problem.
#
# This is the "price the retrain OFFLINE before buying it" move (residual-diagnosis, ADR 0105): it decides
# whether de-leaking the target is worth a global retrain, for one short job instead of a campaign.
#
# ── DESIGN: ONE VARIABLE (residual-diagnosis, ADR 0126 §5) ────────────────────────────────────────────
# Two arms trained IN THIS PROCESS on the SAME rows with the SAME hyperparameters and the SAME seed:
#   CTRL  — the table as it is.
#   ABL   — column 11 (`n_prev`) overwritten with its own sample mean, i.e. a CONSTANT.
# `n_prev` is neutralised in place rather than dropped so that p, the column indices and `mtry` (=
# round(sqrt(p)) = 4) are byte-identical between arms; a constant column can still be drawn as an mtry
# candidate but can never win a split, so the ONLY thing that changes is the information it carries.
# The control is retrained here rather than compared against the shipped artifact, because the shipped
# one saw all 121 495 658 rows and this arm sees a systematic sample — comparing across that difference
# would confound the row set with the ablation.
#
# Hyperparameters are production's (scripts/run_pooled_slow_training.sh): NTREES 150, MAX_DEPTH 16,
# MIN_LEAF 20, SUBSAMPLE 200000, seed 1.
#
# ── SAMPLING ─────────────────────────────────────────────────────────────────────────────────────────
# A systematic random sample: one uniformly-drawn row from each consecutive block of STRIDE rows. This is
# sequential I/O over the 14.5 GB mmap (a 7.6M-row uniform random index set would page-fault across the
# whole file) and, unlike a fixed stride, cannot alias with the table's (cell, scenario, year, patch)
# ordering — a fixed stride of 25 would have sampled one patch index forever.
#
# ENV: TAB, DRF (only for the split-share comparison), CELLS, STRIDE, NTREES, MAX_DEPTH, MIN_LEAF,
#      SUBSAMPLE, SEED, HOLDOUT, NSWEEP, NBASE, BND, TRUTH, OUT
# Run: scripts/sbatch_julia.sh S-nprev-abl --project=. scripts/slow_nprev_ablation_probe.jl

using Printf
using Mmap

include(joinpath(@__DIR__, "..", "src", "drf.jl"))
using .DRF

const GLOB = "/p/tmp/jamirp/emulator_global"
const TAB = get(ENV, "TAB", joinpath(GLOB, "slow_count_pooled_w20_t8"))
const BND = get(ENV, "BND", "/p/tmp/jamirp/S_rung2/boundary")
const OUT = get(ENV, "OUT", joinpath(GLOB, "S_nprev_ablation.csv"))

const STRIDE = parse(Int, get(ENV, "STRIDE", "16"))
const NTREES = parse(Int, get(ENV, "NTREES", "150"))
const MAX_DEPTH = parse(Int, get(ENV, "MAX_DEPTH", "16"))
const MIN_LEAF = parse(Int, get(ENV, "MIN_LEAF", "20"))
const SUBSAMPLE = parse(Int, get(ENV, "SUBSAMPLE", "200000"))
const SEED = parse(Int, get(ENV, "SEED", "1"))
const HOLDOUT = parse(Float64, get(ENV, "HOLDOUT", "0.1"))
const NSWEEP = parse(Int, get(ENV, "NSWEEP", "25"))
const NBASE = parse(Int, get(ENV, "NBASE", "600"))

const F_NPREV = 11
const F_GDD = 12
const F_TCM = 13
const CLIMATE = (F_GDD, F_TCM)

read_manifest(p) = Dict(
    pp[1] => pp[2] for pp in
        (split(l, '\t') for l in eachline(p)) if length(pp) == 2
)

function terminal_boundary(cell::Int, scen::AbstractString)
    path = joinpath(BND, "boundary_$(scen)_c$(cell).csv")
    isfile(path) || return nothing
    last_row = nothing
    for line in eachline(path)
        (startswith(line, "#") || startswith(line, "Year") || isempty(strip(line))) && continue
        last_row = line
    end
    last_row === nothing && return nothing
    f = split(strip(last_row), ',')
    return (parse(Int, f[1]), parse(Float64, f[2]), parse(Float64, f[3]))
end

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
    println("== slow_nprev_ablation_probe — does neutralising `n_prev` open the climate channel?")
    println("   table  : ", TAB)
    println("   arms   : CTRL (table as-is) vs ABL (n_prev := constant); one variable, same rows/seed")
    @printf(
        "   hyper  : ntrees=%d max_depth=%d min_leaf=%d subsample=%d seed=%d stride=%d\n",
        NTREES, MAX_DEPTH, MIN_LEAF, SUBSAMPLE, SEED, STRIDE
    )
    flush(stdout)

    man = read_manifest(joinpath(TAB, "manifest.txt"))
    n = parse(Int, man["n"]); p = parse(Int, man["p"])
    colnames = String.(split(strip(man["colnames"])))
    @assert colnames[F_NPREV] == "n_prev"
    @assert colnames[F_GDD] == "eco_diag_gdd_5"
    @assert colnames[F_TCM] == "tas_cold_month"
    scens = String.(split(strip(get(man, "pooled_scenarios", "historic ssp370"))))
    hist_code = findfirst(==("historic"), scens) - 1
    ssp_code = findfirst(==("ssp370"), scens) - 1

    # ── systematic random sample of rows ─────────────────────────────────────────────────────────────
    print("   sampling rows (stride $STRIDE, one random row per block) ... "); flush(stdout)
    t0 = time()
    rng = DRF.Xoshiro256pp(SEED)
    nblk = n ÷ STRIDE
    idx = Vector{Int}(undef, nblk)
    @inbounds for b in 1:nblk
        idx[b] = (b - 1) * STRIDE + DRF.rand_range!(rng, STRIDE)
    end
    Xt = open(io -> Mmap.mmap(io, Matrix{Float64}, (p, n)), joinpath(TAB, "X.f64"))
    yall = open(io -> Mmap.mmap(io, Vector{Float64}, n), joinpath(TAB, "y.f64"))
    m = length(idx)
    X = Matrix{Float64}(undef, m, p)
    y = Vector{Float64}(undef, m)
    @inbounds for (k, i) in enumerate(idx)
        for f in 1:p
            X[k, f] = Xt[f, i]
        end
        y[k] = yall[i]
    end
    @printf("%d rows in %.1f s\n", m, time() - t0)
    flush(stdout)

    # holdout split (last HOLDOUT fraction of the sampled index order — the sample is already spread
    # uniformly over the file, so a tail slice is not a spatial block)
    ntr = round(Int, m * (1 - HOLDOUT))
    tr = 1:ntr
    te = (ntr + 1):m
    @printf("   train %d rows / holdout %d rows\n", length(tr), length(te))

    # ── the variance ceiling any other feature can act on ────────────────────────────────────────────
    ybar = sum(y) / m
    sst = sum((v - ybar)^2 for v in y)
    # persistence null: predict y by n_prev directly (ADR 0112's null, in-sample here — it needs no fit)
    ssr_np = sum((y[i] - X[i, F_NPREV])^2 for i in 1:m)
    @printf("\n   target n_living: mean %.4f  sd %.4f\n", ybar, sqrt(sst / (m - 1)))
    @printf(
        "   persistence null (y ~= n_prev, no fit): R2 = %.4f  ⇒ at most %.2f%% of the target's\n",
        1 - ssr_np / sst, 100 * ssr_np / sst
    )
    println("     variance is left for EVERY other feature (climate included) to share.")
    flush(stdout)

    # ── probe cells + their operative warming excursions ─────────────────────────────────────────────
    cells_env = get(ENV, "CELLS", "")
    want = isempty(cells_env) ? Int[] : parse.(Int, split(cells_env, ','))
    if isempty(want)
        for f in readdir(BND)
            mm = match(r"^boundary_historic_c(\d+)\.csv$", f)
            mm !== nothing && push!(want, parse(Int, mm.captures[1]))
        end
        sort!(want)
    end
    cellv = open(io -> Mmap.mmap(io, Vector{Int64}, n), joinpath(TAB, "cells.i64"))
    scenv = open(io -> Mmap.mmap(io, Vector{Int64}, n), joinpath(TAB, "scenario.i64"))
    wantset = Set(want)
    hrows = Dict{Int, Vector{Int}}()
    @inbounds for i in 1:n
        c = Int(cellv[i])
        (c in wantset && Int(scenv[i]) == hist_code) || continue
        push!(get!(hrows, c, Int[]), i)
    end
    getrow(i) = Vector{Float64}(@view Xt[:, i])

    gdd_lo, gdd_hi, tcm_lo, tcm_hi = Inf, -Inf, Inf, -Inf
    @inbounds for k in 1:m
        g = X[k, F_GDD]; t = X[k, F_TCM]
        gdd_lo = min(gdd_lo, g); gdd_hi = max(gdd_hi, g)
        tcm_lo = min(tcm_lo, t); tcm_hi = max(tcm_hi, t)
    end
    @printf(
        "   sweep range (sampled rows): gdd5 [%.1f, %.1f]  tas_cold [%.2f, %.2f]\n",
        gdd_lo, gdd_hi, tcm_lo, tcm_hi
    )

    # pooled PD base: a slice of the holdout rows
    pstride = max(1, length(te) ÷ 4000)
    pooled = [Vector{Float64}(@view X[i, :]) for i in te[1:pstride:end]]
    @printf("   pooled PD base: %d holdout rows\n", length(pooled))
    flush(stdout)

    results = Dict{String, Any}()
    recs = []

    for arm in ("CTRL", "ABL")
        println("\n", "="^92)
        println("== ARM $arm")
        Xa = copy(X)
        if arm == "ABL"
            npbar = sum(@view X[:, F_NPREV]) / m
            @inbounds for i in 1:m
                Xa[i, F_NPREV] = npbar
            end
            @printf(
                "   n_prev neutralised to the constant %.6f (was sd %.4f)\n", npbar,
                sqrt(sum((X[i, F_NPREV] - npbar)^2 for i in 1:m) / (m - 1))
            )
        end

        print("   fitting $NTREES trees ... "); flush(stdout)
        t0 = time()
        forest = DRF.fit_forest(
            Xa[tr, :], y[tr]; ntrees = NTREES, max_depth = MAX_DEPTH,
            min_leaf = MIN_LEAF, subsample = SUBSAMPLE, seed = SEED
        )
        @printf("%.1f s\n", time() - t0)
        flush(stdout)

        # holdout skill
        ss = 0.0
        yte_bar = sum(y[i] for i in te) / length(te)
        sst_te = sum((y[i] - yte_bar)^2 for i in te)
        xrow = Vector{Float64}(undef, p)
        @inbounds for i in te
            for f in 1:p
                xrow[f] = Xa[i, f]
            end
            ss += (y[i] - DRF.predict(forest, xrow))^2
        end
        r2 = 1 - ss / sst_te
        @printf("   holdout R2 = %.4f   RMSE = %.4f stems\n", r2, sqrt(ss / length(te)))

        # split shares
        nsplit = zeros(Int, p)
        for tree in forest.trees, nid in eachindex(tree.feat)
            f = tree.feat[nid]
            f != 0 && (nsplit[f] += 1)
        end
        tot = sum(nsplit)
        @printf(
            "   split share: n_prev %.2f%%   gdd5 %.2f%%   tas_cold %.2f%%   (climate %.2f%%)\n",
            100 * nsplit[F_NPREV] / tot, 100 * nsplit[F_GDD] / tot, 100 * nsplit[F_TCM] / tot,
            100 * (nsplit[F_GDD] + nsplit[F_TCM]) / tot
        )

        # pooled full-range climate PD (the between-cell scale)
        gv = range(gdd_lo, gdd_hi; length = NSWEEP)
        tv = range(tcm_lo, tcm_hi; length = NSWEEP)
        pd_g = [pd_mean(forest, pooled, (F_GDD,), (v,)) for v in gv]
        pd_t = [pd_mean(forest, pooled, (F_TCM,), (v,)) for v in tv]
        pd_j = [pd_mean(forest, pooled, CLIMATE, (gv[k], tv[k])) for k in 1:NSWEEP]
        amp_g = maximum(pd_g) - minimum(pd_g)
        amp_t = maximum(pd_t) - minimum(pd_t)
        amp_j = maximum(pd_j) - minimum(pd_j)
        @printf(
            "   POOLED full-range PD amplitude: gdd5 %.4f  tas_cold %.4f  joint %.4f stems\n",
            amp_g, amp_t, amp_j
        )
        @printf(
            "     gdd5 curve %.3f -> %.3f ;  joint %.3f -> %.3f\n",
            first(pd_g), last(pd_g), first(pd_j), last(pd_j)
        )
        flush(stdout)

        # per-cell operative warming excursion
        println("   per-cell operative climate Δ (hist terminal -> ssp370 terminal):")
        tot_abs = 0.0; ncell = 0
        for c in want
            hr = get(hrows, c, Int[])
            isempty(hr) && continue
            bh = terminal_boundary(c, "historic"); bs = terminal_boundary(c, "ssp370")
            (bh === nothing || bs === nothing) && continue
            st = max(1, length(hr) ÷ NBASE)
            base = [getrow(hr[i]) for i in 1:st:length(hr)]
            if arm == "ABL"   # the arm's own basis: the constant it was trained with
                npbar = sum(@view X[:, F_NPREV]) / m
                for row in base
                    row[F_NPREV] = npbar
                end
            end
            ph = pd_mean(forest, base, CLIMATE, (bh[2], bh[3]))
            ps = pd_mean(forest, base, CLIMATE, (bs[2], bs[3]))
            dj = ps - ph
            tot_abs += abs(dj); ncell += 1
            @printf("     cell %-7d  %.4f -> %.4f   Δ %+.4f\n", c, ph, ps, dj)
            push!(recs, (arm = arm, cell = c, pred_h = ph, pred_s = ps, d_joint = dj))
        end
        mean_abs = ncell == 0 ? NaN : tot_abs / ncell
        @printf("   mean |Δ climate| over %d cells: %.4f stems\n", ncell, mean_abs)

        results[arm] = (
            r2 = r2, amp_g = amp_g, amp_t = amp_t, amp_j = amp_j,
            mean_abs = mean_abs, share_np = 100 * nsplit[F_NPREV] / tot,
            share_clim = 100 * (nsplit[F_GDD] + nsplit[F_TCM]) / tot,
        )
        flush(stdout)
    end

    # ── verdict ──────────────────────────────────────────────────────────────────────────────────────
    c = results["CTRL"]; a = results["ABL"]
    println("\n", "="^92)
    println("== COMPARISON")
    @printf("   %-34s %12s %12s %10s\n", "", "CTRL", "ABL", "ABL/CTRL")
    @printf("   %-34s %12.4f %12.4f %10.2f\n", "holdout R2", c.r2, a.r2, a.r2 / c.r2)
    @printf(
        "   %-34s %12.2f %12.2f %10.2f\n", "split share n_prev (%)", c.share_np, a.share_np,
        c.share_np == 0 ? NaN : a.share_np / c.share_np
    )
    @printf(
        "   %-34s %12.2f %12.2f %10.2f\n", "split share climate (%)", c.share_clim, a.share_clim,
        c.share_clim == 0 ? NaN : a.share_clim / c.share_clim
    )
    @printf(
        "   %-34s %12.4f %12.4f %10.2f\n", "pooled PD amplitude gdd5", c.amp_g, a.amp_g,
        c.amp_g == 0 ? NaN : a.amp_g / c.amp_g
    )
    @printf(
        "   %-34s %12.4f %12.4f %10.2f\n", "pooled PD amplitude joint", c.amp_j, a.amp_j,
        c.amp_j == 0 ? NaN : a.amp_j / c.amp_j
    )
    @printf(
        "   %-34s %12.4f %12.4f %10.2f\n", "mean |Δ climate| (operative)", c.mean_abs, a.mean_abs,
        c.mean_abs == 0 ? NaN : a.mean_abs / c.mean_abs
    )

    ratio = c.mean_abs == 0 ? Inf : a.mean_abs / c.mean_abs
    verdict = if ratio >= 3.0
        "H_nprev SUPPORTED — neutralising the teacher-forcing leak multiplies the operative climate " *
            @sprintf("response by %.1fx", ratio) * ". The within-cell climate signal IS in the training " *
            "data; `n_prev` was absorbing it. De-leaking the target is the retraining lever."
    elseif ratio >= 1.5
        "H_nprev PARTIAL — the climate response rises " * @sprintf("%.1fx", ratio) * " but not " *
            "decisively. `n_prev` absorbs some of the channel; de-leaking alone will not deliver FIT's " *
            "response magnitudes. Report the factor, do not promise the fix."
    else
        "H_nprev REFUTED — removing the leak does NOT open the channel " *
            @sprintf("(%.2fx)", ratio) * ". The within-cell climate response is absent from the TRAINING " *
            "TARGET as constructed, not merely masked by `n_prev`. A de-leaked retrain would not fix the " *
            "warming response; the feature set / target construction is the defect."
    end
    println("\n== VERDICT (threshold fixed in this file before the run)")
    println("   ", verdict)

    open(OUT, "w") do io
        println(io, "# n_prev ablation: does removing the teacher-forcing leak open the climate channel?")
        println(io, "# probe scripts/slow_nprev_ablation_probe.jl · table ", basename(TAB))
        println(io, "# CTRL = table as-is; ABL = n_prev overwritten with a constant. Same rows, seed,")
        println(io, "#   hyperparameters (ntrees=$NTREES depth=$MAX_DEPTH min_leaf=$MIN_LEAF sub=$SUBSAMPLE).")
        println(io, "# VERDICT: ", verdict)
        println(io, "arm,cell,pred_h,pred_s,d_joint")
        for r in recs
            @printf(io, "%s,%d,%.6f,%.6f,%.6f\n", r.arm, r.cell, r.pred_h, r.pred_s, r.d_joint)
        end
        println(io, "# arm,r2,amp_gdd5,amp_tas,amp_joint,mean_abs_climate,share_nprev,share_climate")
        for (k, v) in (("CTRL", c), ("ABL", a))
            @printf(
                io, "# %s,%.6f,%.6f,%.6f,%.6f,%.6f,%.4f,%.4f\n",
                k, v.r2, v.amp_g, v.amp_t, v.amp_j, v.mean_abs, v.share_np, v.share_clim
            )
        end
    end
    println("\n   wrote ", OUT)
    return 0
end

exit(main())
