# eval_slow_beta_arm.jl — ARM D, part 2: the DEPLOYABLE bounded-Beta marginal, scored like-for-like
# against the shipped copula on the copula's own table, own folds, own forests and own uniforms.
#
# WHY THIS EXISTS (ADR 0093 §5.3 → ADR 0118 decision 5 → arm D)
# --------------------------------------------------------------
# ADR 0093 §5.3 claimed a bounded Beta beats the shipped copula 2-3x on per-cell KS. Part 1
# (`scripts/score_beta_vs_copula_likeforlike.py`) prices the three confounds in that ratio — the estimator
# (a one-sample KS against a Beta fitted to the same sample's own moments), the grouping (per (Cell,PFT) on
# the densest cells vs per Cell with the PFTs mixed) and the information (the test cell's own observed
# moments vs never having seen the cell). Every Beta arm there is ORACLE-moment, so none of them answers the
# only question that can change the design:
#
#     would replacing the copula's learned empirical marginal with a bounded BETA, given exactly the same
#     conditioning, the same K-fold-by-cell split and the same uniform, be better or worse?
#
# This script answers that, and it is built so the answer cannot be an artefact of a differing setup:
# it re-runs `eval_slow_copula.jl`'s own loop — same `mod(hash(cell), kfolds)` folds, same `fit_forest`
# call with `seed = a`, same `u = rand01!(Xoshiro256pp(i*131 + a))` — and derives BOTH predictions from the
# SAME fitted forest and the SAME leaf pool:
#
#   * `copula` : the pooled leaf values' empirical u-quantile        = exactly what the copula ships
#   * `beta`   : a Beta on that axis's PFT-blind trait interval, its two parameters from the SAME pool's
#                mean and variance, evaluated at the SAME u
#   * `expect` : the pooled leaf values' MEAN — i.e. predict the conditional EXPECTATION instead of drawing
#                a realisation. This is ADR 0093 §5 item 5's "determinism dividend", an EXECUTION_PLAN rung-1
#                deliverable (§3, "cheap wins to fold in and measure separately") that has never been
#                measured; it is free here because the mean is already computed for the Beta's moments. ⚠ Its
#                published value (+2.9 to +14.4 percentage points of cells inside the 10 % band) is on a
#                MEAN-based band metric; scored on the copula's own per-cell KS it is a DISTRIBUTIONAL metric,
#                where a point mass has no dispersion at all, so a large per-cell KS here is the expected
#                result and NOT a refutation of the band-metric claim. What it does settle is whether the
#                dividend can be read as a free win for the trait-DISTRIBUTION target. Report both framings.
#
# ⇒ the two differ in the MARGINAL FAMILY and in nothing else. That is not asserted, it is CHECKED, by two
# separate gates with deliberately different severities:
#
#   GATE A (FATAL, `pool_quantile_and_moments` vs `DRF.predict_quantile` on sampled rows of every fold).
#     The invariant the whole comparison rests on: my pooled reading IS the shipped estimator. If this holds,
#     the two arms come from one forest, one leaf pool and one uniform, and the family is the only difference
#     — regardless of anything outside this run.
#
#   GATE B (REPORTED, not fatal by default; `GATE_FATAL=1` to harden). The re-derived `copula` column vs the
#     table's stored `pred_<axis>.f64`. This SHOULD be bit-identical, and where it is, the arm is anchored to
#     the published artifact as well as internally consistent. ⚠ IT IS NOT ALWAYS: measured 2026-08-12, the
#     STOCK `eval_slow_copula.jl` no longer reproduces the `pred_<axis>.f64` committed in
#     `/p/tmp/jamirp/emulator_global/smoke_struct_on` (all four axes differ, worst |Δ| up to 3.0e5 gC/m3 on
#     Wooddens) even at that table's own KFOLDS=2 — while `src/drf.jl`'s default `qrf=false` numerics are
#     unchanged (the 2026-07-30/31 commits added `_check_nfeat`, the opt-in QRF estimator and `.rcop` v2, none
#     of which touch the pooled path). So a stored `pred_*.f64` on the scratch tables can be STALE with
#     respect to today's evaluator. That is exactly why arm D must not take a stored column as one arm and
#     compute the other today: the difference would carry a code change as well as the marginal family. This
#     gate exists to make that visible instead of silent, which is why it reports rather than dies.
#
# THE INTERVAL IS PFT-BLIND, DELIBERATELY, AND THAT IS NOT A HANDICAP THIS SCRIPT INVENTED. The copula's
# conditioning (`COPULA_COND_COLS` in `build_slow_runtime_table.py`) carries NO `Type` column, so the shipped
# model does not know which of the seven tree PFTs a stem is; the frozen table carries no per-row PFT id
# either. A per-PFT interval would hand the Beta information the copula never had — which is confound 3 in
# part 1. So the interval is the UNION over the seven tree PFTs of `S_pft_estab_params.csv`, and a
# `BETA_INTERVAL=empirical` variant uses the TRAINING fold's own [min,max] instead, so "the parameter
# interval was too wide" cannot explain a null result.
#
# OUTPUT: a SHADOW dir holding `pred_<axis>.f64` plus symlinks to the source table's `cells.i64`,
# `Y_<axis>.f64` and `manifest_copula.txt`, so the EXISTING `scripts/score_slow_copula_ks.py` scores it with
# no new scorer and no new KS definition (ADR 0031).
#
#   OUT=/p/tmp/jamirp/emulator_global/slow_copula_pooled_w20_t8 \
#   SHADOW=/p/tmp/jamirp/emulator_global/armd_beta_pooled_t8 \
#     julia --project=. scripts/eval_slow_beta_arm.jl
#
# ENV: OUT (the SOURCE table dir, read-only) · SHADOW (where pred_<axis>.f64 is written) · AXES (default =
#      the manifest's production axes only — the struct axes are diagnostic and cost 50 % more) ·
#      KFOLDS/NTREES/MAX_DEPTH/MIN_LEAF/SUBSAMPLE/MTRY/QRF (must match the shipped run or the GATE fails,
#      which is the point) · BETA_INTERVAL (param|empirical) · GATE_ROWS (200000; how many test rows per
#      axis are compared against the committed pred — 0 = all) · SMOKE (0; N>0 keeps only the first N rows
#      of the table for a cheap end-to-end shakedown, and then the GATE is SKIPPED because the folds change)
# Heavy (K x naxes forest fits + 2 traversals per row) → SLURM.

include(joinpath(@__DIR__, "..", "src", "drf.jl"))
using .DRF

const SRC = get(ENV, "OUT", "/p/tmp/jamirp/emulator_global/slow_copula_pooled_w20_t8")
const SHADOW = get(ENV, "SHADOW", "/p/tmp/jamirp/emulator_global/armd_beta_pooled_t8")
const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
const SMOKE = parse(Int, get(ENV, "SMOKE", "0"))
const GATE_ROWS = parse(Int, get(ENV, "GATE_ROWS", "200000"))
const GATE_A_ROWS = parse(Int, get(ENV, "GATE_A_ROWS", "20000"))
const GATE_FATAL = get(ENV, "GATE_FATAL", "0") == "1"
const BETA_INTERVAL = get(ENV, "BETA_INTERVAL", "param")

function read_manifest(path)
    d = Dict{String, String}()
    for line in eachline(path)
        parts = split(line, '\t')
        length(parts) == 2 && (d[parts[1]] = parts[2])
    end
    return d
end

"""
    trait_union_intervals() -> Dict{String,Tuple{Float64,Float64}}

The PFT-BLIND trait interval per axis: the union over the seven tree PFTs of the committed
`S_pft_estab_params.csv` (ADR 0119's one source of record for FIT's own `[low, high]`). PFT-blind because
the copula is (see the header) — a per-PFT interval would be extra information, not a fairer comparison.
"""
function trait_union_intervals()
    path = joinpath(REFDIR, "S_pft_estab_params.csv")
    lines = [l for l in eachline(path) if !startswith(l, "#") && !isempty(strip(l))]
    hdr = split(lines[1], ',')
    col(name) = findfirst(==(name), hdr)
    keymap = ("SLA" => "sla", "Wooddens" => "wooddens", "D95max" => "d95max", "minwscal" => "minwscal")
    out = Dict{String, Tuple{Float64, Float64}}()
    for (ax, k) in keymap
        ilo, ihi = col("$(k)_low"), col("$(k)_high")
        (ilo === nothing || ihi === nothing) && error("$path has no $(k)_low/$(k)_high column")
        los = Float64[]
        his = Float64[]
        for l in lines[2:end]
            f = split(l, ',')
            push!(los, parse(Float64, f[ilo]))
            push!(his, parse(Float64, f[ihi]))
        end
        out[ax] = (minimum(los), maximum(his))
    end
    return out
end

# ── the Beta: method of moments, then its quantile ────────────────────────────────────────────────────────
# `lgamma`/`betainc` are not in Base and the runtime `[deps]` stays EMPTY (ADR 0014), so both are
# implemented here. Both are checked against a reference in the Python part-1 script, which matched scipy
# to 4e-15 on the same formulas.

"Lanczos log-gamma (g=7, n=9)."
function lgamma_l(x::Float64)
    g = (
        0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313,
        -176.61502916214059, 12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6,
        1.5056327351493116e-7,
    )
    x < 0.5 && return log(pi / sin(pi * x)) - lgamma_l(1.0 - x)
    z = x - 1.0
    a = g[1]
    t = z + 7.5
    for i in 2:9
        a += g[i] / (z + (i - 1))
    end
    return 0.5 * log(2pi) + (z + 0.5) * log(t) - t + log(a)
end

"Continued fraction for the incomplete beta (modified Lentz)."
function betacf(a::Float64, b::Float64, x::Float64)
    tiny = 1.0e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    abs(d) < tiny && (d = tiny)
    d = 1.0 / d
    h = d
    for m in 1:300
        m2 = 2m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        abs(d) < tiny && (d = tiny)
        c = 1.0 + aa / c
        abs(c) < tiny && (c = tiny)
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        abs(d) < tiny && (d = tiny)
        c = 1.0 + aa / c
        abs(c) < tiny && (c = tiny)
        d = 1.0 / d
        de = d * c
        h *= de
        abs(de - 1.0) < 3.0e-16 && break
    end
    return h
end

"Regularized incomplete beta I_x(a,b)."
function betacdf(x::Float64, a::Float64, b::Float64)
    x <= 0.0 && return 0.0
    x >= 1.0 && return 1.0
    lb = lgamma_l(a) + lgamma_l(b) - lgamma_l(a + b)
    return if x < (a + 1.0) / (a + b + 2.0)
        exp(a * log(x) + b * log1p(-x) - lb) * betacf(a, b, x) / a
    else
        1.0 - exp(b * log1p(-x) + a * log(x) - lb) * betacf(b, a, 1.0 - x) / b
    end
end

"Beta quantile by bisection on `betacdf` — 60 iterations is ~1e-18 on [0,1]."
function betaquant(u::Float64, a::Float64, b::Float64)
    lo, hi = 0.0, 1.0
    for _ in 1:60
        mid = 0.5 * (lo + hi)
        if betacdf(mid, a, b) < u
            lo = mid
        else
            hi = mid
        end
    end
    return 0.5 * (lo + hi)
end

"""
    pool_quantile_and_moments(forest, x, u) -> (q, mean, var, n)

ONE traversal set, TWO readings of the SAME pooled leaf-value set: the empirical `u`-quantile (identical to
`DRF.predict_quantile(forest, x, u; qrf=false)` — same pool, same endpoint convention, same index formula)
and that pool's mean/variance. Sharing the pool is what makes the two arms differ ONLY in the family, and
sharing the traversal is what makes the run affordable.
"""
function pool_quantile_and_moments(forest::DRF.Forest, x::AbstractVector{Float64}, u::Float64)
    pool = Float64[]
    @inbounds for tree in forest.trees
        append!(pool, tree.values[DRF._leaf(tree, x, forest.fill)])
    end
    n = length(pool)
    n == 0 && return (NaN, NaN, NaN, 0)
    sort!(pool)
    uu = clamp(u, 0.0, 1.0)
    idx = clamp(1 + floor(Int, uu * (n - 1)), 1, n)
    q = pool[idx]
    s = 0.0
    @inbounds for v in pool
        s += v
    end
    m = s / n
    v = 0.0
    @inbounds for z in pool
        v += (z - m)^2
    end
    return (q, m, n > 1 ? v / (n - 1) : 0.0, n)
end

"Beta draw at `u` on [lo,hi] from a pool mean/variance. Returns NaN when the moments are inadmissible."
function beta_draw(m::Float64, var::Float64, u::Float64, lo::Float64, hi::Float64)
    (isfinite(m) && isfinite(var) && hi > lo) || return NaN
    mu = clamp((m - lo) / (hi - lo), 1.0e-12, 1 - 1.0e-12)
    vz = var / (hi - lo)^2
    (vz <= 0.0 || vz >= mu * (1 - mu)) && return NaN
    k = mu * (1 - mu) / vz - 1.0
    a, b = mu * k, (1 - mu) * k
    (a > 0 && b > 0 && isfinite(a) && isfinite(b)) || return NaN
    return lo + (hi - lo) * betaquant(clamp(u, 0.0, 1.0), a, b)
end

function main()
    man = read_manifest(joinpath(SRC, "manifest_copula.txt"))
    n_full = parse(Int, man["n"])
    ncond = parse(Int, man["ncond"])
    naxes = parse(Int, man["naxes"])
    prod_axes = Symbol.(split(strip(man["axes"])))
    axes_env = get(ENV, "AXES", "")
    axes = isempty(axes_env) ? prod_axes : Symbol.(split(axes_env))
    all(a -> a in prod_axes, axes) ||
        error("AXES=$axes contains a non-production axis; this arm is defined on $(prod_axes)")
    kfolds = parse(Int, get(ENV, "KFOLDS", "5"))
    ntrees = parse(Int, get(ENV, "NTREES", "40"))
    max_depth = parse(Int, get(ENV, "MAX_DEPTH", "14"))
    min_leaf = parse(Int, get(ENV, "MIN_LEAF", "20"))
    subsample = parse(Int, get(ENV, "SUBSAMPLE", "50000"))
    mtry = parse(Int, get(ENV, "MTRY", "0"))
    qrf = get(ENV, "QRF", "0") == "1"
    qrf && error(
        "QRF=1 is not supported here: the Beta arm reads the UNWEIGHTED pool, so a QRF copula " *
            "column would not be the same pool and the family comparison would be confounded."
    )

    n = SMOKE > 0 ? min(SMOKE, n_full) : n_full
    println("== source table $SRC")
    println("   n=$(n_full)  ncond=$ncond  naxes=$naxes  axes=$(prod_axes)  scenario=$(get(man, "scenario", "?"))")
    smoke_note = SMOKE > 0 ? "  ⚠ SMOKE — GATE B is skipped (the folds change with n)" : ""
    println("   this run: axes=$axes  n=$n" * smoke_note)
    println("   kfolds=$kfolds ntrees=$ntrees max_depth=$max_depth min_leaf=$min_leaf subsample=$subsample mtry=$mtry")
    println("   BETA_INTERVAL=$BETA_INTERVAL")
    flush(stdout)

    # Xc is stored row-major n x ncond — read as ncond x n then permutedims, exactly as eval_slow_copula.jl.
    Xc = let raw = Array{Float64}(undef, ncond, n_full)
        read!(joinpath(SRC, "Xc.f64"), raw)
        # `[1:n, :]` on a full-size read is a needless 2.7 GB copy at global scale, so only slice in SMOKE.
        n == n_full ? permutedims(raw) : permutedims(raw)[1:n, :]
    end
    cells = let c = Vector{Int64}(undef, n_full)
        read!(joinpath(SRC, "cells.i64"), c)
        c[1:n]
    end
    Ys = Dict{Symbol, Vector{Float64}}()
    ref = Dict{Symbol, Vector{Float64}}()
    for ax in axes
        y = Vector{Float64}(undef, n_full)
        read!(joinpath(SRC, "Y_$(ax).f64"), y)
        Ys[ax] = y[1:n]
        p = joinpath(SRC, "pred_$(ax).f64")
        if isfile(p)
            r = Vector{Float64}(undef, n_full)
            read!(p, r)
            ref[ax] = r[1:n]
        end
    end
    println(
        "== read Xc ($(size(Xc))), cells, and $(length(axes)) target column(s); "
            * "$(length(ref)) committed pred column(s) available for the GATE"
    )
    flush(stdout)

    IV = trait_union_intervals()
    for ax in axes
        lo, hi = IV[String(ax)]
        out = count(v -> v < lo || v > hi, Ys[ax])
        println(
            "   interval $(rpad(String(ax), 10)) param=[$lo, $hi]  observed=[$(minimum(Ys[ax])), "
                * "$(maximum(Ys[ax]))]  outside=$out ($(round(100 * out / n, digits = 4)) %)"
        )
    end
    flush(stdout)

    fold = Int[mod(hash(c), kfolds) for c in cells]      # the SAME expression as eval_slow_copula.jl:330
    nfold_gateA = Ref(0)
    preds_beta = Dict(ax => fill(NaN, n) for ax in axes)
    preds_cop = Dict(ax => fill(NaN, n) for ax in axes)
    preds_exp = Dict(ax => fill(NaN, n) for ax in axes)
    nbad = Dict(ax => 0 for ax in axes)

    for k in 0:(kfolds - 1)
        te = fold .== k
        tr = .!te
        ntr, nte = count(tr), count(te)
        ntr > 0 && nte > 0 || error("fold $k is degenerate: ntr=$ntr nte=$nte")
        teidx = findall(te)
        Xtr = Xc[tr, :]
        for (ai, ax) in enumerate(axes)
            a = findfirst(==(ax), prod_axes)          # the SEED must be the axis's PRODUCTION index
            f = DRF.fit_forest(
                Xtr, Ys[ax][tr]; ntrees = ntrees, max_depth = max_depth, min_leaf = min_leaf,
                mtry = mtry, subsample = min(subsample, ntr), seed = a, store_values = true,
            )
            lo, hi = if BETA_INTERVAL == "empirical"
                ytr = Ys[ax][tr]
                (minimum(ytr), maximum(ytr))
            else
                IV[String(ax)]
            end
            pb = preds_beta[ax]
            pc = preds_cop[ax]
            pe = preds_exp[ax]
            let a = a, f = f, ti = teidx, pb = pb, pc = pc, pe = pe, lo = lo, hi = hi
                Threads.@threads for i in ti
                    u = DRF.rand01!(DRF.Xoshiro256pp(i * 131 + a))
                    q, m, v, _ = pool_quantile_and_moments(f, (@view Xc[i, :]), u)
                    @inbounds pc[i] = q
                    @inbounds pb[i] = beta_draw(m, v, u, lo, hi)
                    @inbounds pe[i] = m        # the determinism-dividend arm: the conditional EXPECTATION
                end
            end
            # ── GATE A (FATAL) — my pooled reading IS `DRF.predict_quantile`, on THIS fold's own forest.
            # The whole family-isolation argument rests on this one identity, so it is checked against the
            # shipped function on real rows rather than argued from the source.
            let nchk = min(GATE_A_ROWS, nte), sti = max(1, nte ÷ max(1, nchk))
                worst = 0.0
                nd = 0
                nc = 0
                @inbounds for j in 1:sti:nte
                    i = teidx[j]
                    nc += 1
                    u = DRF.rand01!(DRF.Xoshiro256pp(i * 131 + a))
                    d = abs(pc[i] - DRF.predict_quantile(f, (@view Xc[i, :]), u; qrf = false))
                    if d > 0
                        nd += 1
                        worst = max(worst, d)
                    end
                end
                nd == 0 || error(
                    "GATE A FAIL (fold $k, axis $ax): the pooled quantile read by " *
                        "`pool_quantile_and_moments` differs from `DRF.predict_quantile` on $nd of $nc " *
                        "checked rows (worst |Δ| = $worst). The two arms would then differ in the " *
                        "ESTIMATOR as well as the family, which is the confound this arm exists to remove."
                )
                nfold_gateA[] += nc
            end
            nb = count(isnan, pb[teidx])
            nbad[ax] += nb
            println(
                "   fold $k axis $(rpad(String(ax), 10)) (prod idx $a) done — "
                    * "$nb inadmissible-moment row(s) of $nte"
            )
            flush(stdout)
        end
        println(
            "== fold $k/$(kfolds - 1): test_rows=$nte train_rows=$ntr "
                * "test_cells=$(length(unique(cells[te])))"
        )
        flush(stdout)
    end

    # ── THE GATE: the re-derived copula column must reproduce the committed pred_<axis>.f64 EXACTLY ────
    println(
        "\n== GATE A PASS — `pool_quantile_and_moments` reproduced `DRF.predict_quantile` on "
            * "$(nfold_gateA[]) sampled row(s) across every fold and axis ⇒ the two arms share one forest, "
            * "one leaf pool and one uniform, so they differ in the marginal FAMILY and nothing else."
    )
    if SMOKE == 0 && !isempty(ref)
        sev = GATE_FATAL ? "FATAL" : "not fatal, see this script's header"
        println("\n== GATE B ($sev) — the re-derived copula column vs the table's STORED pred_<axis>.f64")
        ngate = GATE_ROWS == 0 ? n : min(GATE_ROWS, n)
        step = max(1, n ÷ ngate)
        allok = true
        for ax in axes
            haskey(ref, ax) || continue
            worst = 0.0
            nd = 0
            checked = 0
            @inbounds for i in 1:step:n
                checked += 1
                d = abs(preds_cop[ax][i] - ref[ax][i])
                if d > 0
                    nd += 1
                    worst = max(worst, d)
                end
            end
            ok = nd == 0
            allok &= ok
            verdict = ok ? "BIT-IDENTICAL" : "$nd differ, worst |Δ| = $worst"
            println("   $(rpad(String(ax), 10)) checked $checked row(s) (stride $step): " * verdict)
        end
        if allok
            println(
                "   GATE B PASS ⇒ this run's copula column IS the stored one, so the arm is anchored to "
                    * "the published artifact as well as internally consistent."
            )
        else
            msg = "GATE B: this run's copula column is NOT the table's stored one. Either a " *
                "hyperparameter differs (check KFOLDS/NTREES/MAX_DEPTH/MIN_LEAF/SUBSAMPLE/MTRY/QRF against " *
                "the job log that produced $SRC) or the stored column is STALE with respect to today's " *
                "evaluator — measured to be the case for the smoke tables (see the header). The " *
                "family comparison in THIS run is unaffected (GATE A covers it); what is lost is the " *
                "anchor to the published artifact, so say so with any number quoted from this run."
            GATE_FATAL ? error(msg) : println("   ⚠ " * msg)
        end
    end

    # ── write the shadow dirs the EXISTING scorer consumes ────────────────────────────────────────────
    # Three arms, three dirs, ONE set of forests: `<SHADOW>` = the Beta, `<SHADOW>_expect` = the conditional
    # expectation (the determinism dividend), `<SHADOW>_copula` = this run's own re-derived copula column,
    # which is what the other two must be compared against when GATE B reports a stale stored column.
    for (tag, preds) in (("_expect", preds_exp), ("_copula", preds_cop))
        d = SHADOW * tag
        mkpath(d)
        for ax in axes
            open(joinpath(d, "pred_\$(ax).f64"), "w") do io
                write(io, preds[ax])
            end
        end
        for f in ("cells.i64", "manifest_copula.txt")
            dst = joinpath(d, f)
            (isfile(dst) || islink(dst)) && rm(dst)
            symlink(joinpath(SRC, f), dst)
        end
        for ax in axes
            dst = joinpath(d, "Y_\$(ax).f64")
            (isfile(dst) || islink(dst)) && rm(dst)
            symlink(joinpath(SRC, "Y_\$(ax).f64"), dst)
        end
        println("== wrote arm $(tag[2:end]) to $d  ($(length(axes)) axes, $n rows each)")
    end

    mkpath(SHADOW)
    for ax in axes
        nb = nbad[ax]
        if nb > 0
            # score_slow_copula_ks.py asserts every pred is finite, and it is right to: a NaN would
            # silently drop rows from one arm only. Fall back to the copula's own value on those rows and
            # SAY SO in the count — a Beta that cannot be formed is a property of the arm, not a licence
            # to compare different row sets.
            for i in 1:n
                isnan(preds_beta[ax][i]) && (preds_beta[ax][i] = preds_cop[ax][i])
            end
        end
        open(joinpath(SHADOW, "pred_$(ax).f64"), "w") do io
            write(io, preds_beta[ax])
        end
        println(
            "== wrote $(joinpath(SHADOW, "pred_$(ax).f64"))  "
                * "($n rows; $nb row(s) fell back to the copula value = $(round(100 * nb / n, digits = 4)) %)"
        )
    end
    for f in ("cells.i64", "manifest_copula.txt")
        dst = joinpath(SHADOW, f)
        (isfile(dst) || islink(dst)) && rm(dst)
        symlink(joinpath(SRC, f), dst)
    end
    for ax in axes
        dst = joinpath(SHADOW, "Y_$(ax).f64")
        (isfile(dst) || islink(dst)) && rm(dst)
        symlink(joinpath(SRC, "Y_$(ax).f64"), dst)
    end
    println("== symlinked cells.i64 / manifest_copula.txt / Y_<axis>.f64 from the source table")
    println(
        "\nNEXT — score all THREE arms with the existing scorer, AXES=\"$(join(String.(axes), ' '))\":\n"
            * "   SHADOW=$SHADOW          scripts/sbatch_python.sh S-ks-beta   scripts/score_slow_copula_ks.py\n"
            * "   SHADOW=$(SHADOW)_expect scripts/sbatch_python.sh S-ks-expect scripts/score_slow_copula_ks.py\n"
            * "   SHADOW=$(SHADOW)_copula scripts/sbatch_python.sh S-ks-cop    scripts/score_slow_copula_ks.py"
    )
    return nothing
end

if abspath(PROGRAM_FILE) == @__FILE__
    main()
end
