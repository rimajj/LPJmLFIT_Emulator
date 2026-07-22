# Zero-dependency distributional random forest (regression) — pure Base Julia. ADR 0021/0022.
#
# Component S (the slow demography emulator) needs a learned count/marginal model that is TRAINED
# AND RUN in native Julia (ADR 0021), dependency-light (ADR 0014: the package's runtime `[deps]`
# stays EMPTY), deterministic under a seed, and free of the CI dependency-churn risk that pulling in
# a heavy ML package (EvoTrees + Distributions/NNlib/MLJ/…) would reintroduce (cf. the Enzyme-0.13.189
# regression). ADR 0021 permits "EvoTrees.jl/DRF"; ADR 0022 refines the mechanism to this hand-rolled
# DRF so the model that is validated is the model that runs, with no new dep. EvoTrees was confirmed
# available as a fallback (2026-07-22) but deliberately not adopted.
#
# What lives here (all pure Base + a hand-rolled Xoshiro256++, matching the project convention of
# hand-rolling `mean`/`std`/Cholesky rather than adding `Statistics`/`LinearAlgebra`/`Random`):
#   * `Xoshiro256pp`      — seeded RNG (splitmix64-seeded); reproducible bootstrap + copula draws.
#   * `RegTree`/`Forest`  — a subbagged variance-reduction regression forest. Leaves store the mean
#                           (cheap) and OPTIONALLY the sample values (`store_values=true`) so the same
#                           forest also answers quantile / distributional queries (recruit traits).
#   * `fit_forest`        — subbagged (bootstrap capped at `subsample`) random forest.
#   * `predict`           — ensemble mean; `predict_quantile` — distributional draw at uniform u.
module DRF

export Xoshiro256pp, next_u64!, rand01!, rand_range!, Forest, fit_forest, predict,
    predict_quantile, feature_importance

# ── RNG: Xoshiro256++ (public domain algorithm), seeded via splitmix64 ─────────────────────────
mutable struct Xoshiro256pp
    s0::UInt64
    s1::UInt64
    s2::UInt64
    s3::UInt64
end

# splitmix64 finalizer: mix one already-incremented state word into a well-distributed UInt64.
@inline function _splitmix64_final(x::UInt64)
    z = x
    z = (z ⊻ (z >> 30)) * 0xBF58476D1CE4E5B9
    z = (z ⊻ (z >> 27)) * 0x94D049BB133111EB
    return z ⊻ (z >> 31)
end

function Xoshiro256pp(seed::Integer)
    # splitmix64-seed the four state words. Inlined (no inner mutating closure — that would box the
    # captured `x` and trip JET's type-stability gate on ≥1.11); byte-identical stream to the closure form.
    x = UInt64(seed % typemax(UInt64))
    c = 0x9E3779B97F4A7C15
    x += c; z0 = _splitmix64_final(x)
    x += c; z1 = _splitmix64_final(x)
    x += c; z2 = _splitmix64_final(x)
    x += c; z3 = _splitmix64_final(x)
    return Xoshiro256pp(z0, z1, z2, z3)
end

@inline _rotl(x::UInt64, k::Int) = (x << k) | (x >> (64 - k))

@inline function next_u64!(r::Xoshiro256pp)
    result = _rotl(r.s0 + r.s3, 23) + r.s0
    t = r.s1 << 17
    r.s2 ⊻= r.s0
    r.s3 ⊻= r.s1
    r.s1 ⊻= r.s2
    r.s0 ⊻= r.s3
    r.s2 ⊻= t
    r.s3 = _rotl(r.s3, 45)
    return result
end

"Uniform Float64 in [0, 1)."
@inline rand01!(r::Xoshiro256pp) = (next_u64!(r) >> 11) * (1.0 / (UInt64(1) << 53))

"Uniform integer in 1:n (unbiased enough for forest use)."
@inline rand_range!(r::Xoshiro256pp, n::Int) = Int(next_u64!(r) % UInt64(n)) + 1

# ── Regression tree (flat node arrays) ─────────────────────────────────────────────────────────
# A node is a leaf when `feat == 0`. Internal nodes send `X[i, feat] <= thr` left, else right.
struct RegTree
    feat::Vector{Int}
    thr::Vector{Float64}
    left::Vector{Int}
    right::Vector{Int}
    value::Vector{Float64}                 # leaf mean (defined for every node; internal = subtree mean)
    values::Vector{Vector{Float64}}        # leaf sample values if store_values, else empty vectors
end

struct Forest
    trees::Vector{RegTree}
    nfeat::Int
    store_values::Bool
    fill::Vector{Float64}                  # per-feature fill value for missing (NaN) inputs
end

# variance-reduction best split over a random feature subset, using per-feature sort + running sums.
function _best_split(
        X::Matrix{Float64}, y::Vector{Float64}, rows::Vector{Int},
        mtry::Int, min_leaf::Int, rng::Xoshiro256pp, nfeat::Int,
    )
    m = length(rows)
    # parent sums
    sy = 0.0
    @inbounds for i in rows
        sy += y[i]
    end
    parent_sse_base = sy * sy / m           # subtract from Σy² to get SSE; we maximise SSE reduction
    best_gain = 0.0
    best_feat = 0
    best_thr = 0.0
    # sample mtry distinct features
    featpool = randperm_first(rng, nfeat, mtry)
    order = Vector{Int}(undef, m)
    for f in featpool
        # sort rows by feature f (indices into `rows`)
        @inbounds for k in 1:m
            order[k] = k
        end
        sort!(order, by = k -> @inbounds(X[rows[k], f]))
        # skip constant feature
        @inbounds if X[rows[order[1]], f] == X[rows[order[m]], f]
            continue
        end
        # scan split points; left = first j rows in sorted order
        sl = 0.0
        nl = 0
        @inbounds for j in 1:(m - 1)
            ri = rows[order[j]]
            sl += y[ri]
            nl += 1
            xj = X[ri, f]
            xj1 = X[rows[order[j + 1]], f]
            (nl < min_leaf || (m - nl) < min_leaf) && continue
            xj == xj1 && continue           # no split between equal values
            nr = m - nl
            sr = sy - sl
            # SSE reduction = sl²/nl + sr²/nr − sy²/m  (maximise)
            gain = sl * sl / nl + sr * sr / nr - parent_sse_base
            if gain > best_gain
                best_gain = gain
                best_feat = f
                best_thr = 0.5 * (xj + xj1)
            end
        end
    end
    return best_feat, best_thr, best_gain
end

# first `k` of a random permutation of 1:n (partial Fisher–Yates).
function randperm_first(rng::Xoshiro256pp, n::Int, k::Int)
    k = min(k, n)
    p = collect(1:n)
    @inbounds for i in 1:k
        j = i + rand_range!(rng, n - i + 1) - 1
        p[i], p[j] = p[j], p[i]
    end
    return p[1:k]
end

function _build_tree(
        X::Matrix{Float64}, y::Vector{Float64}, rows::Vector{Int},
        rng::Xoshiro256pp, max_depth::Int, min_leaf::Int, mtry::Int,
        store_values::Bool, nfeat::Int,
    )
    feat = Int[]
    thr = Float64[]
    left = Int[]
    right = Int[]
    value = Float64[]
    values = Vector{Vector{Float64}}()

    # work stack of (rows, depth) → node id filled in as we go
    function newnode!()
        push!(feat, 0)
        push!(thr, 0.0)
        push!(left, 0)
        push!(right, 0)
        push!(value, 0.0)
        push!(values, Float64[])
        return length(feat)
    end

    root = newnode!()
    stack = Tuple{Int, Vector{Int}, Int}[(root, rows, 0)]
    while !isempty(stack)
        (nid, nrows, depth) = pop!(stack)
        m = length(nrows)
        μ = 0.0
        @inbounds for i in nrows
            μ += y[i]
        end
        μ /= m
        value[nid] = μ
        make_leaf = depth >= max_depth || m < 2 * min_leaf
        bf = 0
        bt = 0.0
        if !make_leaf
            bf, bt, gain = _best_split(X, y, nrows, mtry, min_leaf, rng, nfeat)
            make_leaf = (bf == 0 || gain <= 0.0)
        end
        if make_leaf
            if store_values
                lv = Vector{Float64}(undef, m)
                @inbounds for k in 1:m
                    lv[k] = y[nrows[k]]
                end
                values[nid] = lv
            end
            continue
        end
        # partition
        lrows = Int[]
        rrows = Int[]
        @inbounds for i in nrows
            if X[i, bf] <= bt
                push!(lrows, i)
            else
                push!(rrows, i)
            end
        end
        if isempty(lrows) || isempty(rrows)   # degenerate → leaf
            if store_values
                lv = Vector{Float64}(undef, m)
                @inbounds for k in 1:m
                    lv[k] = y[nrows[k]]
                end
                values[nid] = lv
            end
            continue
        end
        feat[nid] = bf
        thr[nid] = bt
        lid = newnode!()
        rid = newnode!()
        left[nid] = lid
        right[nid] = rid
        push!(stack, (lid, lrows, depth + 1))
        push!(stack, (rid, rrows, depth + 1))
    end
    return RegTree(feat, thr, left, right, value, values)
end

"""
    fit_forest(X, y; ntrees, max_depth, min_leaf, mtry, subsample, seed, store_values) -> Forest

Fit a subbagged variance-reduction regression forest. `X` is `n×p` (rows = samples). Missing values
must be pre-filled (NaN entries are replaced by the per-feature mean of finite values). Each tree sees
a bootstrap of `min(n, subsample)` rows (subbagging controls cost at scale). Deterministic given `seed`.
`store_values=true` keeps leaf sample values so [`predict_quantile`](@ref) works (use only for small
per-target trait models — memory is ~`ntrees·subsample` floats).
"""
function fit_forest(
        X::Matrix{Float64}, y::Vector{Float64};
        ntrees::Int = 200, max_depth::Int = 16, min_leaf::Int = 5,
        mtry::Int = 0, subsample::Int = 40_000, seed::Integer = 1,
        store_values::Bool = false,
    )
    n, p = size(X)
    length(y) == n || throw(DimensionMismatch("size(X,1) != length(y)"))
    mtry <= 0 && (mtry = max(1, round(Int, sqrt(p))))
    # fill missing (NaN) with per-feature mean of finite entries
    fill = Vector{Float64}(undef, p)
    @inbounds for f in 1:p
        s = 0.0
        c = 0
        for i in 1:n
            v = X[i, f]
            if isfinite(v)
                s += v
                c += 1
            end
        end
        fill[f] = c > 0 ? s / c : 0.0
    end
    Xf = copy(X)
    @inbounds for f in 1:p, i in 1:n
        isfinite(Xf[i, f]) || (Xf[i, f] = fill[f])
    end
    ss = min(n, subsample)
    trees = Vector{RegTree}(undef, ntrees)
    # per-tree RNG stream (seed + t) ⇒ trees are independent AND the result is deterministic
    # regardless of how many threads run, so multithreading does not change the fitted forest.
    Threads.@threads for t in 1:ntrees
        rng = Xoshiro256pp(UInt64(seed) * UInt64(1_000_003) + UInt64(t))
        boot = Vector{Int}(undef, ss)
        @inbounds for k in 1:ss
            boot[k] = rand_range!(rng, n)
        end
        trees[t] = _build_tree(Xf, y, boot, rng, max_depth, min_leaf, mtry, store_values, p)
    end
    return Forest(trees, p, store_values, fill)
end

@inline function _leaf(tree::RegTree, x::AbstractVector{Float64}, fill::Vector{Float64})
    nid = 1
    @inbounds while tree.feat[nid] != 0
        f = tree.feat[nid]
        v = x[f]
        isfinite(v) || (v = fill[f])
        nid = v <= tree.thr[nid] ? tree.left[nid] : tree.right[nid]
    end
    return nid
end

"Ensemble-mean prediction for one feature row."
function predict(forest::Forest, x::AbstractVector{Float64})
    s = 0.0
    @inbounds for tree in forest.trees
        s += tree.value[_leaf(tree, x, forest.fill)]
    end
    return s / length(forest.trees)
end

"Vectorised prediction over rows of `X` (n×p)."
function predict(forest::Forest, X::AbstractMatrix{Float64})
    n = size(X, 1)
    out = Vector{Float64}(undef, n)
    @inbounds for i in 1:n
        out[i] = predict(forest, @view X[i, :])
    end
    return out
end

"""
    predict_quantile(forest, x, u) -> value

Distributional draw: pool the leaf sample values of every tree for row `x`, return the empirical
`u`-quantile (u in [0,1]). Requires `store_values=true` at fit time. Used to map a copula uniform
onto a climate/flux-conditioned marginal (recruit traits).
"""
function predict_quantile(forest::Forest, x::AbstractVector{Float64}, u::Float64)
    forest.store_values || error("predict_quantile requires fit_forest(...; store_values=true)")
    pool = Float64[]
    @inbounds for tree in forest.trees
        append!(pool, tree.values[_leaf(tree, x, forest.fill)])
    end
    isempty(pool) && return NaN
    sort!(pool)
    u = clamp(u, 0.0, 1.0)
    idx = clamp(1 + floor(Int, u * (length(pool) - 1)), 1, length(pool))
    return pool[idx]
end

"Permutation-free split-gain feature importance (count of splits per feature, tree-averaged)."
function feature_importance(forest::Forest)
    imp = zeros(Float64, forest.nfeat)
    for tree in forest.trees
        @inbounds for nid in eachindex(tree.feat)
            f = tree.feat[nid]
            f != 0 && (imp[f] += 1.0)
        end
    end
    s = sum(imp)
    return s > 0 ? imp ./ s : imp
end

end # module DRF
