# eval_slow_copula_scenario_holdout.jl — HOLD-OUT-BY-SCENARIO for the recruit-trait COPULA (ADR 0026 §5,
# the DECISIVE test of whether the transient boundary earns its keep on TRAITS). Reads a POOLED copula table
# (pool_slow_tables.py: Xc.f64 / Y_<axis>.f64 / cells.i64 / scenario.i64 / manifest_copula.txt). For each
# held-out scenario s: fit the per-axis marginal forests on every stem NOT in s (the OTHER regime) and draw
# the OOS quantile for every stem in s — i.e. train the trait model on one climate regime, predict the
# UNSEEN regime's trait distribution. Reports, per direction + per axis: pooled quantile-nqrmse + pooled
# two-sample KS (pred vs FIT-observed marginal). Run this on BOTH the transient-boundary pooled table and the
# static-boundary pooled table: if TRANSIENT materially beats STATIC on the held-out regime, the boundary
# earns its keep on establishment/traits (the count scenario-holdout showed the FLUX drivers already carry
# counts, so the boundary's payoff, if any, must appear HERE).
#
#   OUT=/p/tmp/jamirp/emulator_global/slow_copula_pooled_w20 julia scripts/eval_slow_copula_scenario_holdout.jl
# ENV: OUT (pooled copula dir), NTREES/MAX_DEPTH/MIN_LEAF/SUBSAMPLE (match eval_slow_copula.jl). Threaded
# (JULIA_NUM_THREADS) predict loop, bit-identical to serial. Heavy → scripts/sbatch_julia.sh.

include(joinpath(@__DIR__, "..", "src", "drf.jl"))
using .DRF

const DATA = get(ENV, "OUT", "/p/tmp/jamirp/emulator_global/slow_copula_pooled_w20")

function read_manifest(path)
    d = Dict{String, String}()
    for line in eachline(path)
        parts = split(line, '\t')
        length(parts) == 2 && (d[parts[1]] = parts[2])
    end
    return d
end

qof(v, qs) = (s = sort(v); [s[clamp(round(Int, q * length(s)), 1, length(s))] for q in qs])

"Two-sample Kolmogorov–Smirnov statistic (max |ECDF_a − ECDF_b|) — sort-merge, O((n+m)log)."
function ks2(a::AbstractVector{Float64}, b::AbstractVector{Float64})
    sa = sort(a); sb = sort(b)
    na = length(sa); nb = length(sb)
    (na == 0 || nb == 0) && return NaN
    i = 1; j = 1; d = 0.0
    while i <= na && j <= nb
        va = sa[i]; vb = sb[j]
        if va <= vb
            v = va
            while i <= na && sa[i] == v
                i += 1
            end
        end
        if vb <= va
            v = vb
            while j <= nb && sb[j] == v
                j += 1
            end
        end
        d = max(d, abs((i - 1) / na - (j - 1) / nb))   # |ECDF_a − ECDF_b| at the just-consumed value
    end
    return d
end

function main()
    man = read_manifest(joinpath(DATA, "manifest_copula.txt"))
    n = parse(Int, man["n"])
    ncond = parse(Int, man["ncond"])
    axes = split(man["axes"])
    naxes = length(axes)
    sc_path = joinpath(DATA, "scenario.i64")
    isfile(sc_path) || error("scenario.i64 not found in $DATA — needs a POOLED copula table (pool_slow_tables.py).")
    tags = haskey(man, "pooled_scenarios") ? split(man["pooled_scenarios"]) : String[]

    Xct = Matrix{Float64}(undef, ncond, n)
    read!(joinpath(DATA, "Xc.f64"), Xct)
    Xc = permutedims(Xct)                       # n×ncond
    Ys = [Vector{Float64}(undef, n) for _ in 1:naxes]
    for a in 1:naxes
        read!(joinpath(DATA, "Y_$(axes[a]).f64"), Ys[a])
    end
    scen = Vector{Int64}(undef, n)
    read!(sc_path, scen)

    ntrees = parse(Int, get(ENV, "NTREES", "40"))
    max_depth = parse(Int, get(ENV, "MAX_DEPTH", "14"))
    min_leaf = parse(Int, get(ENV, "MIN_LEAF", "20"))
    subsample = parse(Int, get(ENV, "SUBSAMPLE", "50000"))
    sids = sort(unique(scen))
    name(s) = (s + 1 <= length(tags)) ? tags[s + 1] : "scenario$s"
    qs = (0.05, 0.25, 0.5, 0.75, 0.95)
    @info "loaded pooled copula table" n ncond naxes tags nthreads = Threads.nthreads()

    println("== COPULA HOLD-OUT-BY-SCENARIO (train the trait model on the other regime, test the held-out one) ==")
    for s in sids
        te = scen .== s
        tr = .!te
        (count(te) == 0 || count(tr) == 0) && continue
        teidx = findall(te)
        Xtr = Xc[tr, :]
        println("-- held out $(name(s)): test_stems=$(count(te))  train_stems=$(count(tr)) --")
        for a in 1:naxes
            f = DRF.fit_forest(
                Xtr, Ys[a][tr]; ntrees = ntrees, max_depth = max_depth, min_leaf = min_leaf,
                subsample = min(subsample, count(tr)), seed = a, store_values = true,
            )
            pred = Vector{Float64}(undef, length(teidx))
            let a = a, f = f, ti = teidx, pr = pred
                Threads.@threads for q in eachindex(ti)
                    i = ti[q]
                    u = DRF.rand01!(DRF.Xoshiro256pp(i * 131 + a))
                    @inbounds pr[q] = DRF.predict_quantile(f, (@view Xc[i, :]), u)
                end
            end
            obs = Ys[a][te]
            pq = qof(pred, qs); oq = qof(obs, qs)
            iqr = oq[4] - oq[2]
            nq = iqr > 0 ? sqrt(sum((pq .- oq) .^ 2) / length(qs)) / iqr : NaN
            ks = ks2(pred, obs)
            println(
                "   $(rpad(axes[a], 10)) nqrmse=", round(nq, digits = 3), "  KS=", round(ks, digits = 4),
                "  pred_q50=", round(pq[3], sigdigits = 4), " obs_q50=", round(oq[3], sigdigits = 4)
            )
        end
    end
    return nothing
end

main()
