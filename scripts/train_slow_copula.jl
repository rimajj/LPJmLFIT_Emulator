# Train + serialize the PRODUCTION Component-S recruit-trait COPULA (ADR 0025, Phase 3).
#
# Reads the per-stem copula table built by scripts/build_slow_runtime_table.py MODE=copula (Xc.f64 /
# Y_<axis>.f64 / manifest_copula.txt), fits one FLUX-CONDITIONED marginal DRF per trait axis (store_values
# =true so predict_quantile answers distributional draws), estimates the Gaussian-copula correlation from
# the LATENT NORMAL scores of the axes, and SERIALIZES the bundle with DRF.save_copula (pure-Base .rcop,
# ADR 0014). The coupled FluxDrivenSlowEmulator loads it via DRF.load_copula + make_recruit_to_pools +
# live_flux_cond (src/components/slow.jl); the conditioning order = live_flux_cond (4 flux drivers + the
# per-cell boundary tail), matching the table's COPULA_COND_COLS.
#
# WHY the surviving marginal: the emulator's mortality is trait-blind, so the community trait distribution
# equals the ESTABLISHMENT distribution — hence the axis forests are trained on FIT's SURVIVING stems
# (isdead==0, done in the table builder), so the emulated community converges to FIT's survivor marginal.
#
# Committed demo artifact (single-cell Hainich 42490, small):
#   test/testitems/references/recruit_copula_hainich.rcop       serialized copula bundle
#   test/testitems/references/recruit_copula_hainich_meta.txt   axes/cond_cols + golden (seed,x)->draw pairs
# GLOBAL: set RCOP_OUT_PATH to a SEPARATE artifact (DVC, not git) + larger NTREES/SUBSAMPLE.
# ENV: OUT (table dir), RCOP_OUT_PATH, NTREES, MAX_DEPTH, MIN_LEAF, SUBSAMPLE, QRF (0; 1 = Meinshausen
#      QRF leaf weighting, ADR 0037 — recorded as `qrf_weighting` in the meta). Heavy runs -> SLURM.

include(joinpath(@__DIR__, "..", "src", "drf.jl"))
using .DRF

const DATA = get(ENV, "OUT", "/p/tmp/jamirp/slow_copula_hainich")
const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")

function read_manifest(path)
    d = Dict{String, String}()
    for line in eachline(path)
        parts = split(line, '\t')
        length(parts) == 2 && (d[parts[1]] = parts[2])
    end
    return d
end

# Gaussian-copula correlation from the LATENT normal scores: rank each axis -> empirical CDF u=rank/(n+1) ->
# z=norminv(u); Pearson corr of the z columns (the copula-correct R, invariant to each axis's marginal).
# Guards a (near-)constant axis (std~0 -> identity row) and shrinks toward I so the Cholesky is safely PD.
function latent_corr(Ys::Vector{Vector{Float64}})
    d = length(Ys)
    n = length(Ys[1])
    Z = Matrix{Float64}(undef, n, d)
    for a in 1:d
        rk = sortperm(sortperm(Ys[a]))                 # ordinal ranks 1..n
        @inbounds for i in 1:n
            Z[i, a] = DRF.norminv(rk[i] / (n + 1))
        end
    end
    means = [sum(@view Z[:, a]) / n for a in 1:d]
    sds = [sqrt(max(sum((Z[i, a] - means[a])^2 for i in 1:n) / n, 0.0)) for a in 1:d]
    R = Matrix{Float64}(undef, d, d)
    for a in 1:d
        for b in 1:d
            if a == b
                R[a, b] = 1.0
            elseif sds[a] < 1.0e-12 || sds[b] < 1.0e-12
                R[a, b] = 0.0
            else
                cov = sum((Z[i, a] - means[a]) * (Z[i, b] - means[b]) for i in 1:n) / n
                R[a, b] = cov / (sds[a] * sds[b])
            end
        end
    end
    λ = 1.0e-6                                         # shrink off-diagonals toward I (safely-PD Cholesky)
    for a in 1:d
        for b in 1:d
            a != b && (R[a, b] *= (1 - λ))
        end
    end
    return R
end

function main()
    man = read_manifest(joinpath(DATA, "manifest_copula.txt"))
    n = parse(Int, man["n"])
    ncond = parse(Int, man["ncond"])
    naxes = parse(Int, man["naxes"])
    cond_cols = String.(split(strip(man["cond_cols"])))
    axes = String.(split(strip(man["axes"])))
    @assert length(cond_cols) == ncond "cond_cols/ncond mismatch"
    @assert length(axes) == naxes "axes/naxes mismatch"
    x = haskey(man, "x") ? parse.(Float64, split(strip(man["x"]))) : fill(0.0, ncond)

    Xt = Matrix{Float64}(undef, ncond, n)              # Xc.f64 is row-major n×ncond
    read!(joinpath(DATA, "Xc.f64"), Xt)
    Xc = permutedims(Xt)                               # n×ncond (rows = stems)
    Ys = Vector{Vector{Float64}}(undef, naxes)
    for (a, ax) in enumerate(axes)
        y = Vector{Float64}(undef, n)
        read!(joinpath(DATA, "Y_$(ax).f64"), y)
        Ys[a] = y
    end
    @info "loaded copula table" n ncond naxes axes

    ntrees = parse(Int, get(ENV, "NTREES", "20"))
    max_depth = parse(Int, get(ENV, "MAX_DEPTH", "12"))
    min_leaf = parse(Int, get(ENV, "MIN_LEAF", "8"))
    subsample = parse(Int, get(ENV, "SUBSAMPLE", string(min(n, 300))))
    # ADR 0037. Default 0 ⇒ this script and the committed Hainich demo `.rcop` stay byte-identical.
    qrf = get(ENV, "QRF", "0") == "1"

    axis_forests = DRF.Forest[]
    for (a, ax) in enumerate(axes)
        f = DRF.fit_forest(
            Xc, Ys[a]; ntrees = ntrees, max_depth = max_depth, min_leaf = min_leaf,
            subsample = subsample, seed = a, store_values = true
        )
        push!(axis_forests, f)
        @info "axis forest" ax ntrees = length(f.trees) nfeat = f.nfeat
    end

    R = latent_corr(Ys)
    cop = DRF.GaussianCopula(R)                        # factors R -> Cholesky L (errors if not PD)
    @info "latent-normal copula correlation" R = round.(R, digits = 3)

    rcop_path = get(ENV, "RCOP_OUT_PATH", joinpath(REFDIR, "recruit_copula_hainich.rcop"))
    meta_path = replace(rcop_path, r"\.rcop$" => "_meta.txt")
    mkpath(dirname(rcop_path))
    DRF.save_copula(rcop_path, cop, axis_forests, axes, cond_cols, x)
    sz = filesize(rcop_path)
    @info "serialized copula" rcop_path bytes = sz

    # round-trip self-check (bitwise on this machine)
    cop2, af2, x2, names2, cols2 = DRF.load_copula(rcop_path)
    @assert names2 == axes && cols2 == cond_cols && x2 == x "header round-trip mismatch"
    for s in 1:10
        d1 = DRF.sample_copula!(DRF.Xoshiro256pp(s), cop, axis_forests, x)
        d2 = DRF.sample_copula!(DRF.Xoshiro256pp(s), cop2, af2, x2)
        @assert d1 == d2 "copula draw round-trip changed at seed $s"
    end

    # golden (seed,x)->draw pairs for the committed drift-alarm load test (keyed on the fallback row x)
    open(meta_path, "w") do io
        scope = occursin("hainich", lowercase(rcop_path)) ? "Hainich cell 42490 (single-cell DEMO)" :
            "GLOBAL ($(get(man, "scenario", "?")), $(get(man, "ncells", "?")) cells)"
        println(io, "# Production Component-S recruit-trait copula ($scope) — metadata for the load test.")
        println(io, "# Built by scripts/train_slow_copula.jl from scripts/build_slow_runtime_table.py MODE=copula.")
        # WHICH runtime policy reproduces this artifact's conditioning row. Hard-coding `live_flux_cond`
        # here was correct only while every artifact was 8-wide; a 14-column .rcop (ADR 0038's production
        # config) is built by `live_flux_cond_env`, and a meta that names the 8-column policy invites
        # exactly the silent train/inference shift ADR 0023 warns about. Derive it from `ncond` instead:
        # `live_flux_cond` emits 4 flux drivers + the 4-column boundary tail, so anything wider carries an
        # env tail. `cond_cols` below is the authoritative contract either way.
        nboundary = 4
        policy = ncond == 4 + nboundary ?
            "live_flux_cond (4 flux drivers + the $(nboundary)-column boundary tail)" :
            "live_flux_cond_env(env) with length(env) == $(ncond - 4 - nboundary) " *
            "(4 flux drivers + the $(nboundary)-column boundary tail + the env tail)"
        println(io, "# Conditioning order = src/components/slow.jl::", policy, ".")
        println(io, "naxes\t", naxes)
        println(io, "ncond\t", ncond)
        println(io, "axes\t", join(axes, " "))
        println(io, "cond_cols\t", join(cond_cols, " "))
        # ADR 0037 — WHICH MARGINAL ESTIMATOR this artifact was built and scored under. The runtime must
        # construct its RecruitCopula with the same value (`qrf=`) or it samples a different conditional
        # distribution than was evaluated (ADR 0023, and it fails silently: the draws stay in range).
        println(io, "qrf_weighting\t", qrf ? 1 : 0)
        println(io, "scenario\t", get(man, "scenario", "?"))
        println(io, "x\t", join((string(v) for v in x), " "))
        for s in (1, 7, 42)
            dr = DRF.sample_copula!(DRF.Xoshiro256pp(s), cop, axis_forests, x; qrf = qrf)
            println(io, "golden\t", s, "\t", join((string(v) for v in dr), " "))
        end
    end
    @info "wrote copula meta + golden pairs"

    println("== copula: $naxes axes $(axes), $ncond cond, .rcop=$(sz) bytes")
    # marginal sanity (not asserted): the drawn spread vs the training spread at the fallback row x
    for (a, ax) in enumerate(axes)
        draws = [DRF.sample_copula!(DRF.Xoshiro256pp(1000 + s), cop, axis_forests, x; qrf = qrf)[a] for s in 1:2000]
        yt = Ys[a]
        μd = sum(draws) / length(draws)
        μt = sum(yt) / length(yt)
        println("   $(rpad(ax, 10)) draw mean=$(round(μd, sigdigits = 4))  train mean=$(round(μt, sigdigits = 4))")
    end
    return nothing
end

main()
