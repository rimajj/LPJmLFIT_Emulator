# rung1_count_ratio_arm.jl — RUNG 1, ARMS R0/R1: the SAME count model trained on the YEAR-ON-YEAR RATIO.
#
# WHY (ADR 0114 §5.3a). Recursing the production count model (arm A1, ADR 0113) leaves the LEVEL alone —
# bias never exceeds +0.16 stems/patch on a mean of 8.28, saturating after ~20 years — but that residual
# lead-dependent DRIFT is the same size as LPJmL-FIT's entire global count response (≈ −0.14 stems/patch),
# and it is what inverts the warming response (ADR 0114 §2: faithful in every band at one step, wrong-signed
# by lead 40). ADR 0114 §1 already refuted the regression-to-the-mean explanation (spread 0.90 of truth's and
# correlation 0.94 still at lead 80), so the open hypothesis is:
#
#     THE DRIFT IS AN ARTEFACT OF PREDICTING A LEVEL FROM A LAGGED LEVEL.
#
# A forest that predicts `n_t` from features including `n_{t-1}` can only express the level through a
# piecewise-constant function of it; fed its own answer, any systematic curvature in that map compounds. A
# model trained on the RATIO `n_t / n_{t-1}` has the level cancelled in the target by construction, and the
# recursion becomes multiplicative: `n̂_t = r̂_t · n̂_{t-1}`. If the drift is the artefact, R1 has less of it
# than A1; if it survives, the drift is a property of the conditioning and not of the target's form.
#
# THIS ARM CHANGES EXACTLY ONE THING — the TARGET (and, necessarily, the reconstruction that inverts it).
# The feature matrix (including `n_prev`), the K-fold-by-cell rule, the forest hyper-parameters, the RNG
# seed, the chain definition and the marching loop are byte-for-byte the ones in
# `scripts/rung1_count_recursion_arm.jl`. `n_prev >= 1` and `y >= 1` on every one of the 121 495 658 rows
# (checked), so `y / n_prev` needs no epsilon and no dropped rows.
#
# TWO ARMS, BOTH WRITTEN, because R1 alone would confound "different target" with "recursion":
#   * **R0** — ratio target, TEACHER-FORCED: `n̂ = r̂ · n_prev` with LPJmL-FIT's own `n_prev`. This is the
#     control for A0 (the production one-step score) on the ratio target.
#   * **R1** — ratio target, STATE-RECURSED: `n̂_t = r̂_t · n̂_{t-1}` per (scenario, Cell, Patch) chain, with
#     the predicted count fed back into the `n_prev` FEATURE as well. This is the control for A1.
# By construction R1 == R0 at lead 1; the script ASSERTS that, which is a free end-to-end check that the
# marching loop and the teacher-forced path agree.
#
# ⚠ R1 INHERITS EVERY CAVEAT OF A1. It is a STRICT LOWER BOUND on free-running error — the six other
# roster-state features (`agb`, `lai`, `fpc`, `hmean`, `hmax`, `age_mean`) still come from LPJmL-FIT — it is
# offline, and it says nothing about the trait axes (ADR 0113 §2e).
#
# ⚠ NOTHING IS CLAMPED. A multiplicative recursion can in principle run away where an additive one cannot,
# so the predictions are written raw and the min/max is printed. Clamping here would hide exactly the
# failure mode the arm exists to measure.
#
# WHAT IT WRITES. Two `COUNT_DIR`-shaped directories, so both are scored by the ONE canonical yardstick
# beside A0, the persistence null and A1, in one process on one cell set:
#     export COUNT_DIR=<A0>,<null>,<A1>,<R0>,<R1>
#     scripts/sbatch_python.sh S-yardratio scripts/diagnose_truth_yardstick.py
#
# Usage (SLURM — the guard blocks login-node Julia probes, CLAUDE.md §2; EXPORT the knobs, sbatch_julia.sh
# forwards nothing explicitly):
#     export SRC=/p/tmp/jamirp/emulator_global/slow_count_pooled_w20_t8
#     export KEYS=/p/tmp/jamirp/emulator_global/rung1_keys_t8
#     export OUT_R0=/p/tmp/jamirp/emulator_global/rung1_count_arm_r0
#     export OUT_R1=/p/tmp/jamirp/emulator_global/rung1_count_arm_r1
#     export A1=/p/tmp/jamirp/emulator_global/rung1_count_arm_a1     # optional: side-by-side lead table
#     NCPUS=48 TIME=04:00:00 PARTITION=priority QOS=priority WARMUP=0 \
#       scripts/sbatch_julia.sh S-r1 scripts/rung1_count_ratio_arm.jl
# ENV: SRC, KEYS, OUT_R0, OUT_R1, A1, KFOLDS (5), NTREES (150), MAX_DEPTH (16), MIN_LEAF (20),
#      SUBSAMPLE (200000) — the last five MUST match the production train/eval or R0 − A0 is not the target.

include(joinpath(@__DIR__, "..", "src", "drf.jl"))
using .DRF

const SRC = get(ENV, "SRC", "/p/tmp/jamirp/emulator_global/slow_count_pooled_w20_t8")
const KEYS = get(ENV, "KEYS", "/p/tmp/jamirp/emulator_global/rung1_keys_t8")
const OUT_R0 = get(ENV, "OUT_R0", "/p/tmp/jamirp/emulator_global/rung1_count_arm_r0")
const OUT_R1 = get(ENV, "OUT_R1", "/p/tmp/jamirp/emulator_global/rung1_count_arm_r1")
const A1DIR = get(ENV, "A1", "/p/tmp/jamirp/emulator_global/rung1_count_arm_a1")

function read_manifest(path)
    d = Dict{String, String}()
    for line in eachline(path)
        parts = split(line, '\t')
        length(parts) == 2 && (d[parts[1]] = parts[2])
    end
    return d
end

r2score(yt, pt) = (ss = sum((pt .- yt) .^ 2); m = sum(yt) / length(yt); st = sum((yt .- m) .^ 2); st > 0 ? 1 - ss / st : 0.0)

read_vec(path, T, n) = (v = Vector{T}(undef, n); read!(path, v); v)

"""
Chains of consecutive years within one (scenario, Cell, Patch), as contiguous runs of `ord`.

IDENTICAL to `scripts/rung1_count_recursion_arm.jl::build_chains` — same break rule, same
decreasing-length sort — so a difference between R1 and A1 is the target and nothing else.
"""
function build_chains(ord, scen, cells, patches, years)
    starts = Int[]
    lens = Int[]
    n = length(ord)
    n == 0 && return starts, lens
    s = 1
    @inbounds for i in 2:n
        a, b = ord[i - 1], ord[i]
        newchain = scen[b] != scen[a] || cells[b] != cells[a] || patches[b] != patches[a] ||
            years[b] != years[a] + 1
        if newchain
            push!(starts, s)
            push!(lens, i - s)
            s = i
        end
    end
    push!(starts, s)
    push!(lens, n - s + 1)
    perm = sortperm(lens; rev = true)
    return starts[perm], lens[perm]
end

function write_arm(dir, preds, man, src, scen_file, extra)
    mkpath(dir)
    open(joinpath(dir, "preds_oos.f64"), "w") do io
        write(io, preds)
    end
    for fn in ["cells.i64", "y.f64", scen_file]
        dst = joinpath(dir, fn)
        (islink(dst) || isfile(dst)) && rm(dst)
        symlink(abspath(joinpath(src, fn)), dst)
    end
    open(joinpath(dir, "manifest.txt"), "w") do io
        for (k, v) in man
            println(io, "$k\t$v")
        end
        for (k, v) in extra
            println(io, "$k\t$v")
        end
    end
    return nothing
end

function main()
    man = read_manifest(joinpath(SRC, "manifest.txt"))
    n = parse(Int, man["n"])
    p = parse(Int, man["p"])
    colnames = split(man["colnames"], ' ')
    jn = findfirst(==("n_prev"), colnames)
    jn === nothing && error("no `n_prev` column in $SRC — this arm has nothing to recurse")
    scen_file = get(man, "scenario_tag", "scenario.i64")

    println("== SRC=$SRC  n=$n  p=$p  n_prev is column $jn")
    Xt = Matrix{Float64}(undef, p, n)
    read!(joinpath(SRC, "X.f64"), Xt)
    X = permutedims(Xt)                       # n×p, row-major access for predict
    Xt = Matrix{Float64}(undef, 0, 0)         # release the transpose before the fold copies
    GC.gc()
    y = read_vec(joinpath(SRC, "y.f64"), Float64, n)
    cells = read_vec(joinpath(SRC, "cells.i64"), Int64, n)
    scen = read_vec(joinpath(SRC, scen_file), Int64, n)
    years = read_vec(joinpath(KEYS, "years.i64"), Int64, n)
    patches = read_vec(joinpath(KEYS, "patches.i64"), Int64, n)

    nkeyed = count(>=(0), years)
    println("== keys from $KEYS: $nkeyed/$n rows keyed ($(round(100 * nkeyed / n, digits = 4)) %)")
    nkeyed == 0 && error("no keyed rows — run scripts/attach_count_table_keys.py first")
    maximum(patches) < 64 || error("Patch index >= 64 breaks the composite sort key below")

    # THE TARGET. `n_prev >= 1` and `y >= 1` on every row of this table, so the ratio is exact — assert it
    # rather than trust the note, because a future table with a zero would silently produce Inf here.
    npmin = minimum(@view X[:, jn])
    ymin = minimum(y)
    println("== target check: min(n_prev)=$npmin  min(y)=$ymin")
    (npmin > 0 && ymin > 0) || error("ratio target needs n_prev>0 and y>0 (got $npmin / $ymin)")
    ratio = similar(y)
    @inbounds for i in 1:n
        ratio[i] = y[i] / X[i, jn]
    end
    println(
        "== ratio target: mean=$(round(sum(ratio) / n, digits = 5))  " *
            "min=$(minimum(ratio))  max=$(maximum(ratio))"
    )

    a0path = joinpath(SRC, "preds_oos.f64")
    a0 = isfile(a0path) ? read_vec(a0path, Float64, n) : Float64[]
    a1path = joinpath(A1DIR, "preds_oos.f64")
    a1 = isfile(a1path) ? read_vec(a1path, Float64, n) : Float64[]
    println("== controls: A0 $(isempty(a0) ? "MISSING" : "loaded")   A1 $(isempty(a1) ? "MISSING" : "loaded")")

    kfolds = parse(Int, get(ENV, "KFOLDS", "5"))
    ntrees = parse(Int, get(ENV, "NTREES", "150"))
    max_depth = parse(Int, get(ENV, "MAX_DEPTH", "16"))
    min_leaf = parse(Int, get(ENV, "MIN_LEAF", "20"))
    subsample = parse(Int, get(ENV, "SUBSAMPLE", "200000"))
    println(
        "== KFOLDS=$kfolds NTREES=$ntrees MAX_DEPTH=$max_depth MIN_LEAF=$min_leaf SUBSAMPLE=$subsample "
            * "(must equal the production train/eval)"
    )
    flush(stdout)

    fold = Int[mod(hash(c), kfolds) for c in cells]      # IDENTICAL rule to eval_slow_drf.jl
    r0 = fill(NaN, n)
    r1 = fill(NaN, n)
    maxstep = 0
    step_n = Int[]
    step_se = Float64[]                                   # R1
    step_bias = Float64[]
    step_se1 = Float64[]                                  # A1, same rows
    step_bias1 = Float64[]
    step_se0 = Float64[]                                  # A0, same rows
    step_bias0 = Float64[]

    for k in 0:(kfolds - 1)
        te = (fold .== k) .& (years .>= 0)
        tr = (fold .!= k)                                 # train on ALL other cells' rows, as A0 does
        ntr = count(tr)
        f = DRF.fit_forest(
            X[tr, :], ratio[tr]; ntrees = ntrees, max_depth = max_depth, min_leaf = min_leaf,
            subsample = min(subsample, ntr), seed = 1, store_values = false,
        )
        rows = findall(te)

        # --- R0: teacher-forced. Predict the ratio on FIT's own features and multiply back the true n_prev.
        # The rows are gathered into a dense copy rather than passed as a strided view: `predict` indexes
        # row-by-row and a view-of-a-view costs more than the one-off 3 GB copy.
        Xte = X[rows, :]
        r̂0 = DRF.predict(f, Xte)
        Xte = Matrix{Float64}(undef, 0, 0)
        @inbounds for (i, r) in enumerate(rows)
            r0[r] = r̂0[i] * X[r, jn]
        end
        r̂0 = Float64[]
        GC.gc()

        # --- R1: recursed. Same chain machinery as A1.
        key = [((scen[r] * 67421 + cells[r]) * 64 + patches[r]) * 4096 + years[r] for r in rows]
        ord = rows[sortperm(key)]
        key = Int64[]
        starts, lens = build_chains(ord, scen, cells, patches, years)
        nch = length(lens)
        L = isempty(lens) ? 0 : lens[1]
        maxstep = max(maxstep, L)
        while length(step_n) < maxstep
            push!(step_n, 0); push!(step_se, 0.0); push!(step_bias, 0.0)
            push!(step_se1, 0.0); push!(step_bias1, 0.0)
            push!(step_se0, 0.0); push!(step_bias0, 0.0)
        end
        println(
            "== fold $k: test_rows=$(length(rows))  chains=$nch  max_len=$L  " *
                "median_len=$(isempty(lens) ? 0 : lens[cld(nch, 2)])"
        )
        flush(stdout)

        prevcount = Vector{Float64}(undef, nch)
        buf = Matrix{Float64}(undef, nch, p)              # reused; only the first na rows are used per step
        for s in 1:L
            na = searchsortedlast(lens, s; rev = true)    # chains with lens >= s are the prefix 1:na
            na == 0 && break
            @inbounds for c in 1:na
                r = ord[starts[c] + s - 1]
                for j in 1:p
                    buf[c, j] = X[r, j]
                end
                if s > 1
                    buf[c, jn] = prevcount[c]             # <-- THE ARM: our own answer, not FIT's
                end
            end
            r̂ = DRF.predict(f, @view buf[1:na, :])
            @inbounds for c in 1:na
                r = ord[starts[c] + s - 1]
                nhat = r̂[c] * buf[c, jn]                  # multiplicative reconstruction
                r1[r] = nhat
                prevcount[c] = nhat
                d = nhat - y[r]
                step_se[s] += d * d
                step_bias[s] += d
                step_n[s] += 1
                if !isempty(a1)
                    d1 = a1[r] - y[r]
                    step_se1[s] += d1 * d1
                    step_bias1[s] += d1
                end
                if !isempty(a0)
                    d0 = a0[r] - y[r]
                    step_se0[s] += d0 * d0
                    step_bias0[s] += d0
                end
            end
        end
        println(
            "   fold $k done: R0 R²=$(round(r2score(y[rows], r0[rows]), digits = 4))  " *
                "R1 R²=$(round(r2score(y[rows], r1[rows]), digits = 4))"
        )
        flush(stdout)
    end

    ok = .!isnan.(r1)
    nok = count(ok)
    # FREE END-TO-END CHECK: the marching loop's first step uses FIT's own n_prev, so it must reproduce the
    # teacher-forced path exactly. A mismatch means the two code paths disagree and nothing below is safe.
    # The FIRST year of each (scenario, Cell, Patch) series is necessarily a chain start, found here by a
    # min-year reduction that never looks at `build_chains` — an independent recomputation, and a strict
    # SUBSET of the chain starts (a mid-series year gap makes another one), so it cannot fail spuriously.
    lead1 = Int[]
    let firstyear = Dict{Int64, Int64}()
        seriesof(i) = (scen[i] * 67421 + cells[i]) * 64 + patches[i]
        for i in 1:n
            years[i] < 0 && continue
            k = seriesof(i)
            firstyear[k] = min(get(firstyear, k, typemax(Int64)), years[i])
        end
        for i in 1:n
            years[i] < 0 && continue
            years[i] == firstyear[seriesof(i)] && push!(lead1, i)
        end
        println(
            "\n== lead-1 gate: $(length(lead1)) first-year rows over $(length(firstyear)) " *
                "(scenario,Cell,Patch) series"
        )
    end
    worst = 0.0
    for i in lead1
        isnan(r1[i]) && continue
        worst = max(worst, abs(r1[i] - r0[i]))
    end
    println(
        "== lead-1 gate: max |R1 - R0| over first-year rows = $worst  " *
            (
            worst < 1.0e-9 ? "OK (the recursion reproduces the teacher-forced path where it is given FIT's count)" :
                "MISMATCH — the marching loop and the teacher-forced path disagree; STOP"
        )
    )
    worst < 1.0e-9 || error("lead-1 gate failed (max |R1-R0| = $worst)")

    println("\n== R0 (ratio target, teacher-forced) OOS R² = $(round(r2score(y[ok], r0[ok]), digits = 6)) on $nok rows")
    println("== R1 (ratio target, state-recursed) OOS R² = $(round(r2score(y[ok], r1[ok]), digits = 6)) on the SAME rows")
    if !isempty(a0)
        println("== A0 (level target, teacher-forced) OOS R² = $(round(r2score(y[ok], a0[ok]), digits = 6)) on the SAME rows")
    end
    if !isempty(a1)
        println("== A1 (level target, state-recursed) OOS R² = $(round(r2score(y[ok], a1[ok]), digits = 6)) on the SAME rows")
    end
    println(
        "== R1 prediction range: min=$(round(minimum(r1[ok]), digits = 4)) " *
            "max=$(round(maximum(r1[ok]), digits = 4))   (nothing is clamped)"
    )

    println("\n--- ERROR VS LEAD TIME (years since the chain was last given FIT's own count) ---")
    println("    step         rows      R1 bias      R1 RMSE      A1 bias      A1 RMSE      A0 bias      A0 RMSE")
    for s in 1:maxstep
        step_n[s] == 0 && continue
        (s <= 12 || s % 10 == 0 || s == maxstep) || continue
        m = step_n[s]
        println(
            "  ", lpad(s, 6), lpad(m, 13), "  ",
            lpad(round(step_bias[s] / m, digits = 4), 11), "  ",
            lpad(round(sqrt(step_se[s] / m), digits = 4), 11), "  ",
            lpad(round(step_bias1[s] / m, digits = 4), 11), "  ",
            lpad(round(sqrt(step_se1[s] / m), digits = 4), 11), "  ",
            lpad(round(step_bias0[s] / m, digits = 4), 11), "  ",
            lpad(round(sqrt(step_se0[s] / m), digits = 4), 11)
        )
    end

    write_arm(
        OUT_R0, r0, man, SRC, scen_file, [
            "arm" => "R0 ratio target (n_t/n_{t-1}), TEACHER-FORCED (ADR 0114 §5.3a)",
            "arm_source" => SRC, "keys" => KEYS, "target_form" => "ratio", "recursed_features" => "(none)",
            "predicted_rows" => string(count(!isnan, r0)),
        ]
    )
    write_arm(
        OUT_R1, r1, man, SRC, scen_file, [
            "arm" => "R1 ratio target (n_t/n_{t-1}), STATE-RECURSED (ADR 0114 §5.3a)",
            "arm_source" => SRC, "keys" => KEYS, "target_form" => "ratio",
            "recursed_features" => "n_prev",
            "held_at_truth" => "bm_inc_cell growth_eff water_stress soilmoist hmean hmax agb lai fpc age_mean",
            "note" => "STRICT LOWER BOUND on free-running error — the six other roster-state features " *
                "still come from LPJmL-FIT",
            "predicted_rows" => string(nok),
        ]
    )
    println("\n== wrote $OUT_R0 and $OUT_R1 ($nok of $n rows predicted)")
    return nothing
end

main()
