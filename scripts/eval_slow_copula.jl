# eval_slow_copula.jl — K-fold-BY-CELL OUT-OF-SAMPLE trait-distribution predictions for the global
# recruit-trait copula (ADR 0025, Phase 4 — the REAL, cross-cell fidelity proof). Each cell's per-axis
# marginal is predicted by axis forests that NEVER trained on it (deterministic cell→fold), so the
# validation figures show genuine generalization, not in-sample fit. One OOS draw per surviving stem per
# axis (deterministic u), pooled per cell downstream.
#
# Per-axis MARGINALS are the fidelity target the figures show; the Gaussian copula only couples the axes
# (the JOINT), it does NOT change any single marginal — so independent per-axis quantile draws are the
# correct, cheaper OOS estimator here (the joint correlation is a separate, secondary check).
#
# Reads the MODE=copula table (Xc.f64 / Y_<axis>.f64 / cells.i64 / manifest_copula.txt) and writes one
# pred_<axis>.f64 (n Float64, aligned to Xc rows) per axis for scripts/plot_slow_emulator_validation.py.
#
# STRUCT axes (`nstruct`/`struct_axes` in the manifest — the OPT-IN diagnostic biomass/size axes, e.g.
# agb/Height) are evaluated here exactly like a production trait axis: same conditioning, same K-fold-BY-CELL
# split, their own pred_<axis>.f64. They are DIAGNOSTIC ONLY (they never enter the production .rcop, which
# line M pins). Both manifest keys are optional: absent ⇒ zero struct axes ⇒ this script behaves exactly as
# it did before they existed, so every pre-existing table dir keeps working unchanged.
#
#   OUT=/p/tmp/jamirp/emulator_global/slow_copula_historic KFOLDS=5 julia scripts/eval_slow_copula.jl
# ENV: OUT, KFOLDS (5), NTREES/MAX_DEPTH/MIN_LEAF/SUBSAMPLE, QRF (0; 1 = Meinshausen QRF leaf weighting,
#      ADR 0037), MTRY (0 = DRF's own sqrt(p) default), FOLD_MODE (hash|block), BLOCK_DEG (15),
#      BUFFER_DEG (0), BLOCK_SALT (0; replicates the tile->fold colouring, whose spread is the same
#      order as the effect being measured), CELL_LATLON (required by FOLD_MODE=block; see the block below).
#      Heavy (K×naxes forest fits, store_values) → SLURM.
#      EVERY new knob defaults to the pre-ADR-0040 behaviour, so an unchanged invocation writes
#      byte-identical `pred_<axis>.f64` (guardrail 4).

include(joinpath(@__DIR__, "..", "src", "drf.jl"))
using .DRF

const DATA = get(ENV, "OUT", "/p/tmp/jamirp/emulator_global/slow_copula_historic")

function read_manifest(path)
    d = Dict{String, String}()
    for line in eachline(path)
        parts = split(line, '\t')
        length(parts) == 2 && (d[parts[1]] = parts[2])
    end
    return d
end

# Struct axes are APPENDED after the production axes (see the ORDER note in main), so an axis index
# beyond `naxes` marks a DIAGNOSTIC axis. A plain function, not a loop-local, so nothing extra gets
# captured by the `Threads.@threads` closure below (JET boxed-capture trap, CLAUDE.md §2).
axis_kind(a::Int, naxes::Int) = a > naxes ? "struct" : "trait"

# LEAF GEOMETRY — print it, because the capacity ladder is uninterpretable without it (ADR 0038).
#
# Every capacity rung run before 2026-07-30 changed `subsample` and `max_depth` TOGETHER (50k/d14,
# 500k/d18, 2M/d22, 8M/d26), so "resolution" could not be split into its two causes — and they have very
# different costs: `.rcop` bytes scale as `ntrees·subsample·naxes` while `max_depth` is FREE. Measuring the
# t8 artifact afterwards showed 99.9-100 % of leaves holding >= 2·min_leaf values sit exactly at
# `depth == max_depth`, and 57-67 % of ALL stored values live in such a depth-capped leaf — i.e. the trees
# were truncated by the depth budget with most of the mass still splittable. That is a property every rung
# should have reported for itself instead of being reconstructed from one serialized artifact.
#
# Cheap: one traversal per tree, only on the first fold, and it touches no prediction state.
# Plain top-level function with single-assignment locals (JET boxed-capture trap, CLAUDE.md §2).
function leaf_geometry(f::DRF.Forest, max_depth::Int)
    depths = Int[]
    sizes = Int[]
    for t in f.trees
        stack = Tuple{Int, Int}[(1, 0)]
        while !isempty(stack)
            (nid, d) = pop!(stack)
            if t.feat[nid] == 0
                push!(depths, d)
                push!(sizes, length(t.values[nid]))
            else
                push!(stack, (t.left[nid], d + 1))
                push!(stack, (t.right[nid], d + 1))
            end
        end
    end
    nl = length(depths)
    nl == 0 && return "   (no leaves?)"
    srt = sort(sizes)
    total = sum(sizes)
    capmass = sum(sizes[i] for i in 1:nl if depths[i] == max_depth; init = 0)
    ncap = count(==(max_depth), depths)
    es = total / nl
    es2 = sum(float(s)^2 for s in sizes) / nl
    q(p) = srt[max(1, min(nl, ceil(Int, p * nl)))]
    return string(
        "   geometry: leaves/tree=", round(nl / length(f.trees), digits = 0),
        "  size min/med/q90/q99/max=", srt[1], "/", q(0.5), "/", q(0.9), "/", q(0.99), "/", srt[nl],
        "\n   geometry: at max_depth=", max_depth, ": ", ncap, "/", nl, " leaves (",
        round(100 * ncap / nl, digits = 1), "%) holding ", round(100 * capmass / total, digits = 1),
        "% of stored values",
        "\n   geometry: E[size]=", round(es, digits = 2),
        "  size-biased pool/tree E[s^2]/E[s]=", round(es2 / es, digits = 1),
        "  => expected draw pool ~", round(length(f.trees) * es2 / es, digits = 0), " values",
    )
end

# ── ADR 0040: spatially BLOCKED folds and a physical training BUFFER ───────────────────────────────
#
# WHY. `mod(hash(cell), kfolds)` scatters test cells uniformly, so a test cell's geographic NEIGHBOURS stay
# in the training fold — measured on the historic t8 basis, 99.5 % of test cells have a training cell within
# 0.75° and the q99 is 0.61°, i.e. essentially every test cell has an IMMEDIATELY ADJACENT training cell.
# The six env conditioning columns of ADR 0038 are a per-cell constant whose east-neighbour correlation is
# 0.96–0.999, so under that split the evaluation cannot separate "learned an environmental response" from
# "interpolated from the adjacent cell". Blocked folds + a buffer are the only way to tell.
#
# WHAT. `FOLD_MODE=block` assigns folds to B°×B° TILES (`mod(hash(tile), kfolds)`, a packed `Int` so it
# inherits exactly the same `hash` stability caveat as the hash branch), and `BUFFER_DEG=D` then removes
# from each fold's TRAINING set every cell within D° of ANY of that fold's test cells. The buffer is a
# separate mask that never touches `te`, so every row remains in exactly one TEST fold and the coverage
# assert below keeps its meaning; a buffered cell is still trained on in the other K−1 folds.
#
# The dilation is done in GRID index space but with the longitude radius scaled by 1/cos(lat), so D is a
# PHYSICAL width rather than a lat/lon-index width (at 70°N a 5-index longitude step is only ~1.7° of great
# circle). The two passes are applied in sequence, which makes the result a conservative SUPERSET of the
# true great-circle ball — it can remove slightly more training cells than a strict ball, never fewer, so
# it cannot manufacture a false "the gain survives blocking".
struct CellGeo
    ilat::Vector{Int32}       # indexed by (cell + 1) over 0:maxcell
    ilon::Vector{Int32}
    known::BitVector
    nlat::Int
    nlon::Int
    dlat::Float64
    lat0::Float64
    lon0::Float64
end

"""
    read_cell_latlon(path) -> CellGeo

Parse the plain-text per-cell position table written by `scripts/build_slow_spatial_controls.py`
(`# key value` metadata lines, then `cell ilat ilon lat lon`). Plain text because this script loads only
`src/drf.jl` and has no CSV/Parquet/NetCDF dependency (ADR 0014 keeps the runtime `[deps]` empty).
"""
function read_cell_latlon(path::AbstractString)
    meta = Dict{String, Float64}()
    cs = Int[]
    ils = Int[]
    ios = Int[]
    for line in eachline(path)
        s = strip(line)
        isempty(s) && continue
        if startswith(s, "#")
            p = split(s)
            if length(p) == 3
                v = tryparse(Float64, p[3])
                v === nothing || (meta[p[2]] = v)
            end
            continue
        end
        p = split(s)
        length(p) >= 3 || error("malformed row in $path: \"$s\"")
        push!(cs, parse(Int, p[1]))
        push!(ils, parse(Int, p[2]))
        push!(ios, parse(Int, p[3]))
    end
    for k in ("nlat", "nlon", "dlat", "lat0", "lon0")
        haskey(meta, k) || error("$path is missing the `# $k <value>` metadata line")
    end
    isempty(cs) && error("$path has no data rows")
    maxcell = maximum(cs)
    ilat = zeros(Int32, maxcell + 1)
    ilon = zeros(Int32, maxcell + 1)
    known = falses(maxcell + 1)
    for j in eachindex(cs)
        c = cs[j]
        ilat[c + 1] = Int32(ils[j])
        ilon[c + 1] = Int32(ios[j])
        known[c + 1] = true
    end
    return CellGeo(
        ilat, ilon, known, round(Int, meta["nlat"]), round(Int, meta["nlon"]),
        meta["dlat"], meta["lat0"], meta["lon0"],
    )
end

"""
    block_folds(cells, geo, kfolds, block_deg) -> Vector{Int}

Fold id per ROW, assigned to the cell's `block_deg`×`block_deg` tile. Tile offsets are taken from the whole
globe (`+90` / `+180`), not from this grid's crop, so the tiling is independent of the grid file's extent.
"""
function block_folds(cells::Vector{Int64}, geo::CellGeo, kfolds::Int, block_deg::Float64, salt::Int = 0)
    ucells = unique(cells)
    miss = [c for c in ucells if !(0 <= c <= length(geo.known) - 1) || !geo.known[c + 1]]
    if !isempty(miss)
        error(
            "$(length(miss)) of $(length(ucells)) table cells are absent from CELL_LATLON " *
                "(e.g. $(first(miss, 5))). Refusing to fall back to hash folds for a subset — that would " *
                "reintroduce the very interpolation confound being tested, for an unknown set of cells."
        )
    end
    tile = Vector{Int}(undef, length(cells))
    @inbounds for j in eachindex(cells)
        c = cells[j]
        lat = geo.lat0 + geo.dlat * geo.ilat[c + 1]
        lon = geo.lon0 + geo.dlat * geo.ilon[c + 1]
        tlat = floor(Int, (lat + 90.0) / block_deg)
        tlon = floor(Int, (lon + 180.0) / block_deg)
        tile[j] = tlat * 100_000 + tlon
    end
    ntile = length(unique(tile))
    println("   FOLD_MODE=block: $ntile tiles of $(block_deg)° over $(length(ucells)) cells, salt=$salt")
    # ONE tile→fold colouring is ONE draw, and its spread is the same order as the effect being measured, so
    # the salt exists to replicate it. `salt = 0` adds nothing to the packed tile id, so the default
    # colouring is bit-identical to the unsalted one.
    return Int[mod(hash(t + salt * 7_000_003), kfolds) for t in tile]
end

"""
    buffer_rows(cells, geo, te, buffer_deg) -> BitVector

Rows whose cell lies within `buffer_deg` of ANY test cell but is NOT itself a test cell — the rows to drop
from THIS fold's training set. Latitude is clipped (the grid's lat edges are real data edges); longitude
WRAPS modulo `nlon` (the ±180 seam is a periodic boundary, not an edge).
"""
function buffer_rows(cells::Vector{Int64}, geo::CellGeo, te::BitVector, buffer_deg::Float64)
    n = length(cells)
    rad = round(Int, buffer_deg / geo.dlat)
    rad <= 0 && return falses(n)
    nlat, nlon = geo.nlat, geo.nlon
    g = falses(nlat, nlon)
    @inbounds for j in 1:n
        if te[j]
            c = cells[j]
            g[geo.ilat[c + 1] + 1, geo.ilon[c + 1] + 1] = true
        end
    end
    # pass 1 — longitude, radius scaled by 1/cos(lat) so `buffer_deg` is a physical width; wraps mod nlon
    g1 = falses(nlat, nlon)
    @inbounds for i in 1:nlat
        latdeg = geo.lat0 + geo.dlat * (i - 1)
        cl = max(cos(deg2rad(latdeg)), 1.0e-3)
        ri = min(ceil(Int, rad / cl), nlon ÷ 2)
        for j in 1:nlon
            if g[i, j]
                for dj in (-ri):ri
                    g1[i, mod(j - 1 + dj, nlon) + 1] = true
                end
            end
        end
    end
    # pass 2 — latitude, uniform radius, CLIPPED at the grid's real data edges
    g2 = falses(nlat, nlon)
    @inbounds for i in 1:nlat, j in 1:nlon
        if g1[i, j]
            for di in max(1, i - rad):min(nlat, i + rad)
                g2[di, j] = true
            end
        end
    end
    buf = falses(n)
    @inbounds for j in 1:n
        if !te[j]
            c = cells[j]
            buf[j] = g2[geo.ilat[c + 1] + 1, geo.ilon[c + 1] + 1]
        end
    end
    return buf
end

function main()
    man = read_manifest(joinpath(DATA, "manifest_copula.txt"))
    n = parse(Int, man["n"])
    ncond = parse(Int, man["ncond"])
    naxes = parse(Int, man["naxes"])
    prod_axes = String.(split(strip(man["axes"])))
    # `nstruct`/`struct_axes` are OPT-IN and OPTIONAL: absent ⇒ 0/empty, i.e. production-axes-only, which is
    # byte-identical to the pre-struct-axes behaviour on every table dir built before they existed.
    nstruct = haskey(man, "nstruct") ? parse(Int, strip(man["nstruct"])) : 0
    struct_axes = haskey(man, "struct_axes") ? String.(split(strip(man["struct_axes"]))) : String[]
    # ORDER IS LOAD-BEARING — production axes FIRST, struct axes APPENDED, never interleaved or reordered.
    # Both the per-axis forest seed (`seed = a`) and the per-row draw RNG (`Xoshiro256pp(i * 131 + a)`) are
    # functions of the axis INDEX `a`, so appending keeps every production axis's index — and therefore its
    # OOS prediction — BIT-IDENTICAL (guardrail 4: opt-in, default byte-identical). Any permutation of this
    # vector silently moves the production predictions.
    all_axes = vcat(prod_axes, struct_axes)
    nall = naxes + nstruct
    @assert length(struct_axes) == nstruct "struct_axes/nstruct mismatch: $(length(struct_axes)) names vs $nstruct"
    @assert length(all_axes) == nall "axes/naxes+nstruct mismatch: $(length(all_axes)) names vs $nall"
    cells_path = joinpath(DATA, "cells.i64")
    isfile(cells_path) || error("cells.i64 not found in $DATA (rebuild with MODE=copula).")

    Xt = Matrix{Float64}(undef, ncond, n)      # Xc.f64 row-major n×ncond
    read!(joinpath(DATA, "Xc.f64"), Xt)
    Xc = permutedims(Xt)
    Ys = Vector{Vector{Float64}}(undef, nall)
    for (a, ax) in enumerate(all_axes)
        ypath = joinpath(DATA, "Y_$(ax).f64")
        isfile(ypath) || error(
            "Y_$(ax).f64 not found in $DATA — axis \"$ax\" ($(axis_kind(a, naxes))) is declared in " *
                "manifest_copula.txt but its column was not written (rebuild the table with MODE=copula)."
        )
        y = Vector{Float64}(undef, n)
        read!(ypath, y)
        Ys[a] = y
    end
    cells = Vector{Int64}(undef, n)
    read!(cells_path, cells)

    kfolds = parse(Int, get(ENV, "KFOLDS", "5"))
    ntrees = parse(Int, get(ENV, "NTREES", "40"))
    max_depth = parse(Int, get(ENV, "MAX_DEPTH", "14"))
    min_leaf = parse(Int, get(ENV, "MIN_LEAF", "20"))
    subsample = parse(Int, get(ENV, "SUBSAMPLE", "50000"))
    # ADR 0037: QRF=1 selects the Meinshausen quantile-regression-forest weighting in
    # DRF.predict_quantile (each tree contributes 1/T, spread inside ITS leaf) instead of the
    # default equal-weight concatenation of all leaf values, which over-weights whichever tree
    # happened to land x in a LARGE leaf. Default 0 => this script stays byte-identical.
    qrf = get(ENV, "QRF", "0") == "1"
    # ADR 0040. `MTRY=0` (the default) leaves `DRF.fit_forest`'s own `mtry::Int = 0` sentinel in place, so
    # this script stays byte-identical. It is exposed because `mtry_eff = round(Int, sqrt(p))` is 3 at
    # ncond 8 but 4 at ncond 14 — so an ncond-8-vs-14 comparison silently varies mtry too, and forcing
    # MTRY=4 on the narrow table is what makes the conditioning lever a matched pair (ADR 0033's lesson).
    mtry = parse(Int, get(ENV, "MTRY", "0"))
    fold_mode = get(ENV, "FOLD_MODE", "hash")
    block_deg = parse(Float64, get(ENV, "BLOCK_DEG", "15"))
    buffer_deg = parse(Float64, get(ENV, "BUFFER_DEG", "0"))
    block_salt = parse(Int, get(ENV, "BLOCK_SALT", "0"))
    cell_latlon = get(ENV, "CELL_LATLON", "")
    fold_mode in ("hash", "block") || error("FOLD_MODE must be `hash` or `block`, got \"$fold_mode\"")
    @info "loaded copula table" n ncond naxes prod_axes nstruct struct_axes ncells = length(unique(cells)) kfolds fold_mode block_deg buffer_deg block_salt mtry

    # `hash` reproduces the historic split EXACTLY (same expression, same order, same element type) so every
    # published rung stays comparable; `block` is the ADR-0040 spatial split. See the CellGeo block above.
    fold = if fold_mode == "block"
        isempty(cell_latlon) && error("FOLD_MODE=block requires CELL_LATLON (build_slow_spatial_controls.py)")
        block_folds(cells, read_cell_latlon(cell_latlon), kfolds, block_deg, block_salt)
    else
        Int[mod(hash(c), kfolds) for c in cells]        # each cell in exactly ONE test fold
    end
    geo = (fold_mode == "block" && buffer_deg > 0) ? read_cell_latlon(cell_latlon) : nothing
    fmn, fmx = extrema(fold)
    (0 <= fmn && fmx < kfolds) || error("fold ids out of range: [$fmn, $fmx] for kfolds=$kfolds")
    preds = [fill(NaN, n) for _ in 1:nall]
    for k in 0:(kfolds - 1)
        te = fold .== k
        # The BUFFER enters ONLY here, as a separate mask: `te` stays a partition of all rows, so every row
        # is still in exactly one TEST fold and the coverage assert below keeps its meaning. With
        # buffer_deg == 0 this is `falses(n)` and `tr` is bit-identical to `.!te`.
        buf = geo === nothing ? falses(n) : buffer_rows(cells, geo, te, buffer_deg)
        tr = (.!te) .& (.!buf)
        ntr = count(tr)
        nte = count(te)
        nbuf = count(buf)
        # Distinct messages: an empty TRAINING fold makes every leaf empty, `predict_quantile` returns NaN,
        # and the coverage assert below then fires with a message blaming fold coverage instead
        # (the slow-drf-pipeline FOLD TRAP, reached by a second route).
        ntr > 0 || error("fold $k has an EMPTY TRAINING set (nbuf=$nbuf) — BUFFER_DEG=$buffer_deg is too wide")
        nte > 0 || error("fold $k has an EMPTY TEST set — check BLOCK_DEG/KFOLDS")
        ntr < subsample && @warn "fold $k: train_rows < SUBSAMPLE — this rung's capacity is NOT matched" ntr subsample
        teidx = findall(te)
        Xtr = Xc[tr, :]
        for (a, ax) in enumerate(all_axes)
            f = DRF.fit_forest(
                Xtr, Ys[a][tr]; ntrees = ntrees, max_depth = max_depth, min_leaf = min_leaf,
                mtry = mtry, subsample = min(subsample, ntr), seed = a, store_values = true,
            )
            # The OOS quantile draw per (row, axis) is the eval's dominant cost (~naxes·kfolds·n forest
            # traversals — millions at global scale). PARALLELISE across JULIA_NUM_THREADS: each test row
            # writes a distinct `pa[i]` (no race), and its RNG is seeded per (row, axis) so the result is
            # bit-identical to the serial loop regardless of thread count / schedule. `let` binds
            # single-assignment locals so the `@threads` closure does not box the reassigned `a`/`f`/`teidx`
            # (JET boxed-capture trap, CLAUDE.md §2).
            # Report the fitted geometry ONCE (first fold) per axis — see `leaf_geometry`.
            k == 0 && println(leaf_geometry(f, max_depth))
            pa = preds[a]
            let a = a, f = f, pa = pa, ti = teidx, qrf = qrf
                Threads.@threads for i in ti
                    u = DRF.rand01!(DRF.Xoshiro256pp(i * 131 + a))
                    @inbounds pa[i] = DRF.predict_quantile(f, (@view Xc[i, :]), u; qrf = qrf)
                end
            end
            println("   axis $(rpad(String(ax), 10)) [$(axis_kind(a, naxes))] done (fold $k)"); flush(stdout)
        end
        println(
            "== fold $k/$(kfolds - 1): test_rows=$nte train_rows=$ntr buffered_rows=$nbuf " *
                "test_cells=$(length(unique(cells[te]))) train_cells=$(length(unique(cells[tr])))"
        ); flush(stdout)
    end
    for a in 1:nall
        @assert !any(isnan, preds[a]) "axis $(all_axes[a]): some rows never in a test fold"
        open(joinpath(DATA, "pred_$(all_axes[a]).f64"), "w") do io
            write(io, preds[a])
        end
    end

    # pooled per-axis OOS quantile-match (a headline number; the per-cell figures are the real story)
    qs = (0.05, 0.25, 0.5, 0.75, 0.95)
    qof(v) = (s = sort(v); [s[clamp(round(Int, q * length(s)), 1, length(s))] for q in qs])
    for (a, ax) in enumerate(all_axes)
        pq = qof(preds[a])
        oq = qof(Ys[a])
        iqr = oq[4] - oq[2]
        nq = iqr > 0 ? sqrt(sum((pq .- oq) .^ 2) / length(qs)) / iqr : NaN
        println(
            "== $(rpad(ax, 10)) [$(axis_kind(a, naxes))] pooled OOS: pred_q=", round.(pq, sigdigits = 4),
            " obs_q=", round.(oq, sigdigits = 4), " nqrmse=", round(nq, digits = 3)
        )
    end
    println(
        "== wrote pred_<axis>.f64 for $(all_axes) ($n rows, $kfolds-fold-by-cell; ",
        "$naxes production trait + $nstruct struct/diagnostic axes)"
    )
    return nothing
end

# Run only when invoked as a script, so `scripts/blocked_cv_folds_probe.jl` can `include` this file and
# exercise `block_folds`/`buffer_rows` directly without triggering a 22 GB table read. The driver always
# invokes it as `julia scripts/eval_slow_copula.jl`, so this is byte-identical in production.
if abspath(PROGRAM_FILE) == @__FILE__
    main()
end
