# rcop_leaf_geometry_probe.jl — measure a SERIALIZED recruit copula's leaf geometry and the pooled-default
# leaf-weight skew, from the artifact itself.
#
# WHY THIS EXISTS (ADR 0037/0038). Two numbers that reached an ADR, a skill and a changelog were derived by
# hand from the t8 artifact and were then found to be wrong or wrong-basis:
#
#   * "a large leaf is one that stopped splitting early" — false. 99.9-100 % of leaves holding >= 2*min_leaf
#     values sit at exactly `depth == max_depth`, and 57-67 % of ALL stored values live in such a leaf. The
#     trees are cut off by the DEPTH BUDGET, not by gain exhaustion. That mattered because it made
#     `max_depth` look like a free fix for the per-cell under-dispersion (`.rcop` bytes scale as
#     `ntrees*subsample*naxes`, so depth is free) — and it is not: the single-factor rung moves
#     `sd(pred)/sd(Y1)` only 0.6775 -> 0.6796.
#   * "the largest of 60 leaves takes 17-21 % of the weight, a 10-12x over-weight" — that is roughly its
#     UPPER DECILE. Routed over real conditioning rows (this probe, 4000 rows, t8 Wooddens) the share is
#     median 11.1 % / mean 12.2 % / q90 18.9 %, i.e. 6.7x typical against QRF's 1/60 and 11.3x only in the
#     sparse-conditioning decile; across the four axes 5.8-6.7x typical / 10.5-12.2x at q90. Expect ~0.2x
#     jitter in the multiplier at NROWS <= 1000 — use >= 4000 for a figure you intend to publish.
#
# `eval_slow_copula.jl::leaf_geometry` now makes every TRAINING rung self-report its geometry. This probe is
# the complement: it reads a SERIALIZED artifact, so the claims stay re-derivable after the artifact rotates
# and for artifacts nobody has the training log for. Committed rather than kept inline because the numbers it
# produces are published (residual-diagnosis: validate the harness, then keep it).
#
# Named `*_probe.jl` deliberately — ReTestItems scans the whole repo for `*_test(s).jl` and a diagnostic
# script under that name fails the ENTIRE suite at collection (CLAUDE.md §2).
#
# Run (login node is fine — it is a parse plus one pass; seconds to ~1 min):
#   RCOP=/p/tmp/jamirp/emulator_global/recruit_copula_global_historic_t8.rcop \
#   TABLE=/p/tmp/jamirp/emulator_global/slow_copula_historic_t8 NROWS=20000 \
#     ALLOW_LOGIN_HEAVY=1 /p/system/packages_rhel9/tools/julia/1.10.0/bin/julia scripts/rcop_leaf_geometry_probe.jl
#
# ENV: RCOP (required), TABLE (optional — a MODE=copula table dir supplying real `Xc` rows for the weight
#      routing; omitted => geometry only), NROWS (20000), SEED (17).

include(joinpath(@__DIR__, "..", "src", "drf.jl"))
using .DRF

const RCOP = get(ENV, "RCOP", "")
const TABLE = get(ENV, "TABLE", "")
const NROWS = parse(Int, get(ENV, "NROWS", "20000"))
const SEED = parse(Int, get(ENV, "SEED", "17"))

q(v, p) = (s = sort(v); s[max(1, min(length(s), ceil(Int, p * length(s))))])

"Per-leaf (depth, size) for one forest, by an explicit stack walk from each tree's root."
function leaf_table(f::DRF.Forest)
    depths = Int[]
    sizes = Int[]
    tree_of = Int[]
    for (ti, t) in enumerate(f.trees)
        stack = Tuple{Int, Int}[(1, 0)]
        while !isempty(stack)
            (nid, d) = pop!(stack)
            if t.feat[nid] == 0
                push!(depths, d)
                push!(sizes, length(t.values[nid]))
                push!(tree_of, ti)
            else
                push!(stack, (t.left[nid], d + 1))
                push!(stack, (t.right[nid], d + 1))
            end
        end
    end
    return depths, sizes, tree_of
end

function main()
    isempty(RCOP) && error("set RCOP=<path to a .rcop>")
    println("="^104)
    println("RCOP LEAF GEOMETRY + POOLED-DEFAULT WEIGHT SKEW")
    println("="^104)
    println("   artifact : ", RCOP, "  (", round(filesize(RCOP) / 2^20, digits = 1), " MB)")
    t0 = time()
    (cop, marg, xfb, axnames, condcols) = DRF.load_copula(RCOP)
    println(
        "   loaded   : ", length(axnames), " axes, ncond=", length(condcols),
        ", ", length(marg[1].trees), " trees/axis, nfeat=", marg[1].nfeat,
        "  in ", round(time() - t0, digits = 2), " s"
    )

    println("\n-- GEOMETRY (max_depth is not stored in the artifact; the max OBSERVED leaf depth is used as a")
    println("   lower bound on it, which is exact whenever any leaf actually reached the cap) --")
    for (ai, name) in enumerate(axnames)
        f = marg[ai]
        depths, sizes, _ = leaf_table(f)
        nl = length(depths)
        maxd = maximum(depths)
        total = sum(sizes)
        big = [i for i in 1:nl if sizes[i] >= 40]          # >= 2*min_leaf at the production min_leaf=20
        atcap_big = count(i -> depths[i] == maxd, big)
        capmass = sum(sizes[i] for i in 1:nl if depths[i] == maxd; init = 0)
        es = total / nl
        es2 = sum(float(s)^2 for s in sizes) / nl
        println(
            "   ", rpad(name, 10),
            " leaves=", nl, " (", round(nl / length(f.trees), digits = 0), "/tree)",
            "  depth min/med/max=", minimum(depths), "/", q(depths, 0.5), "/", maxd
        )
        println(
            "   ", " "^10,
            " size min/med/q90/q99/max=", q(sizes, 0.0), "/", q(sizes, 0.5), "/", q(sizes, 0.9),
            "/", q(sizes, 0.99), "/", maximum(sizes)
        )
        println(
            "   ", " "^10,
            " leaves >=40 values: ", length(big), ", of those at max_depth: ", atcap_big,
            " (", round(100 * atcap_big / max(length(big), 1), digits = 1), "%)"
        )
        println(
            "   ", " "^10,
            " stored values in a depth-capped leaf: ", round(100 * capmass / total, digits = 1), "%",
            "   E[size]=", round(es, digits = 2),
            "  size-biased pool/tree=", round(es2 / es, digits = 1),
            " => draw pool ~", round(length(f.trees) * es2 / es, digits = 0)
        )
    end

    isempty(TABLE) && (println("\n   TABLE unset — skipping the weight routing."); return)

    # ---- route REAL conditioning rows and measure the largest leaf's share of the pooled default weight ----
    man = Dict{String, String}()
    for line in eachline(joinpath(TABLE, "manifest_copula.txt"))
        p = split(line, '\t')
        length(p) == 2 && (man[p[1]] = p[2])
    end
    n = parse(Int, man["n"])
    ncond = parse(Int, man["ncond"])
    ncond == marg[1].nfeat ||
        error("TABLE ncond=$ncond but the artifact's forests have nfeat=$(marg[1].nfeat) — different bases.")
    println("\n-- WEIGHT SKEW over ", NROWS, " real Xc rows from ", TABLE, " --")
    println("   Under the pooled default a value's weight is 1/sum_t|L_t(x)|, so ONE tree's share is")
    println(
        "   |L_t(x)|/sum_t|L_t(x)|; QRF gives every tree exactly 1/T = ",
        round(1 / length(marg[1].trees), digits = 5), "."
    )
    io = open(joinpath(TABLE, "Xc.f64"), "r")
    rng = DRF.Xoshiro256pp(SEED)
    row = Vector{Float64}(undef, ncond)
    for (ai, name) in enumerate(axnames)
        f = marg[ai]
        shares = Float64[]
        for _ in 1:NROWS
            i = DRF.rand_range!(rng, n)                       # 1-based row index
            seek(io, (i - 1) * ncond * 8)
            read!(io, row)
            szs = [length(t.values[DRF._leaf(t, row, f.fill)]) for t in f.trees]
            tot = sum(szs)
            tot > 0 && push!(shares, maximum(szs) / tot)
        end
        T = length(f.trees)
        println(
            "   ", rpad(name, 10),
            " max-leaf share: median=", round(q(shares, 0.5), digits = 4),
            " mean=", round(sum(shares) / length(shares), digits = 4),
            " q90=", round(q(shares, 0.9), digits = 4),
            " max=", round(maximum(shares), digits = 4),
            "  => ", round(q(shares, 0.5) * T, digits = 1), "x typical / ",
            round(q(shares, 0.9) * T, digits = 1), "x at q90 vs QRF's 1/T"
        )
    end
    close(io)
    println("\n   Read the TYPICAL (median) figure as the over-weight; quoting q90 as typical overstates it,")
    return println("   which is the error ADR 0038 corrects in ADR 0037 §3.")
end

main()
