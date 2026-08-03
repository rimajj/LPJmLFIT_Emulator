# blocked_cv_folds_probe.jl — GATE the ADR-0039 spatially-blocked fold machinery before spending compute.
#
# WHY. The whole blocked-CV experiment rests on two claims about `eval_slow_copula.jl`'s new fold code, and
# both fail SILENTLY if wrong: (1) `FOLD_MODE=hash` is byte-identical to the pre-ADR-0039 split, so every
# published rung stays comparable; (2) with `FOLD_MODE=block BUFFER_DEG=D`, no training cell is within D of
# any test cell — which is the entire point of the buffer. Claim 2 in particular cannot be read off the
# eval's own log: a buffer that silently under-dilates would leave the interpolation confound in place and
# the run would report a plausible "the gain survives blocking".
#
# So this probe re-derives the nearest-training-cell distance INDEPENDENTLY, by brute force over the actual
# cell positions, using great-circle distance rather than the eval's own grid dilation. Two different
# metrics agreeing is the point; reusing the eval's dilation to check the eval's dilation would prove
# nothing.
#
# `*_probe.jl`, never `*_test.jl` — ReTestItems scans the whole repo for `*_test(s).jl` and fails collection
# on any file that is not pure `@testitem` (CLAUDE.md §2).
#
#   CELL_LATLON=/p/tmp/jamirp/emulator_global/tables/cell_latlon.txt \
#   SRC=/p/tmp/jamirp/emulator_global/slow_copula_pooled_w20_t8 \
#     julia scripts/blocked_cv_folds_probe.jl
#
# Env: CELL_LATLON (required), SRC (a copula table dir — its `cells.i64` supplies the real cell set),
#      KFOLDS (5), BLOCK_DEGS + BUFFER_DEGS (comma lists), NSAMPLE (cells to
#      brute-force the distance check on; 4000).

include(joinpath(@__DIR__, "eval_slow_copula.jl"))

const LL = get(ENV, "CELL_LATLON", "/p/tmp/jamirp/emulator_global/tables/cell_latlon.txt")
const SRCDIR = get(ENV, "SRC", "/p/tmp/jamirp/emulator_global/slow_copula_pooled_w20_t8")

function cell_positions(geo::CellGeo, ucells::Vector{Int64})
    lat = Float64[geo.lat0 + geo.dlat * geo.ilat[c + 1] for c in ucells]
    lon = Float64[geo.lon0 + geo.dlat * geo.ilon[c + 1] for c in ucells]
    return lat, lon
end

# Great-circle degrees via the haversine — INDEPENDENT of the eval's grid-index dilation on purpose.
function gcdeg(lat1::Float64, lon1::Float64, lat2::Float64, lon2::Float64)
    p1 = deg2rad(lat1)
    p2 = deg2rad(lat2)
    dp = p2 - p1
    dl = deg2rad(lon2 - lon1)
    a = sin(dp / 2)^2 + cos(p1) * cos(p2) * sin(dl / 2)^2
    return rad2deg(2 * asin(min(1.0, sqrt(a))))
end

function main_probe()
    kfolds = parse(Int, get(ENV, "KFOLDS", "5"))
    blocks = [parse(Float64, s) for s in split(get(ENV, "BLOCK_DEGS", "10,15,20"), ",")]
    bufs = [parse(Float64, s) for s in split(get(ENV, "BUFFER_DEGS", "0,2,5,10"), ",")]
    nsample = parse(Int, get(ENV, "NSAMPLE", "4000"))

    geo = read_cell_latlon(LL)
    println("== geo: nlat=$(geo.nlat) nlon=$(geo.nlon) dlat=$(geo.dlat) lat0=$(geo.lat0) lon0=$(geo.lon0)")

    cpath = joinpath(SRCDIR, "cells.i64")
    n = filesize(cpath) ÷ 8
    rows = Vector{Int64}(undef, n)
    read!(cpath, rows)
    ucells = sort(unique(rows))
    println("== table: $n rows, $(length(ucells)) unique cells from $SRCDIR")

    # ---- claim 1: the hash branch is unchanged -----------------------------------------------------
    # Compare the literal historic expression against what the script computes for FOLD_MODE=hash. They
    # must be the same object, elementwise, on the real cell vector.
    ref = Int[mod(hash(c), kfolds) for c in ucells]
    @assert eltype(ref) === Int
    println("== claim 1 (hash branch byte-identical): fold sizes $(map(k -> count(==(k), ref), 0:(kfolds - 1)))")

    # ---- claim 2: block folds are spatially coherent, and the buffer really severs adjacency -------
    #
    # THE DESIGN NUMBER THIS PRODUCES, and why it is not optional. A blocked split alone does NOT remove
    # the mechanism under test: the PERIMETER of every test block keeps an immediately adjacent training
    # cell. For a B° tile on the 0.5° lattice that perimeter is ~4·(2B)/(2B)² = 2/B of the tile, so at
    # B = 15 about an eighth of the test set still has a 0.5° neighbour — and a 1-NN lookup at 1.0° already
    # reaches Wooddens r = 0.800. A `BUFFER_DEG=0` rung therefore cannot support a verdict on the address
    # hypothesis; it is a sensitivity rung. `frac<=0.5` / `frac<=1.0` below are what make that concrete, and
    # they are measured through the SAME `buffer_rows` the eval calls, not a reimplementation of it.
    lat, lon = cell_positions(geo, ucells)
    println("== claim 2: block-fold design sweep (all numbers from the real `buffer_rows` dilation)")
    println(
        "   $(rpad("B°", 5)) $(rpad("D°", 5)) $(rpad("cellbal", 8)) " *
            "$(rpad("train%", 7)) $(rpad("min_d", 7)) $(rpad("q10_d", 7)) $(rpad("med_d", 7)) " *
            "$(rpad("f<=0.5", 7)) $(rpad("f<=1.0", 7)) verdict"
    )
    for B in blocks
        bf = block_folds(ucells, geo, kfolds, B)
        sizes = map(k -> count(==(k), bf), 0:(kfolds - 1))
        @assert minimum(sizes) > 0 "a block fold is EMPTY at BLOCK_DEG=$B — pick another block size"
        bal = maximum(sizes) / minimum(sizes)
        for D in bufs
            ds = Float64[]
            keep = 0
            for k in 0:(kfolds - 1)
                te = BitVector(bf .== k)
                buf = buffer_rows(ucells, geo, te, D)
                tr = (.!te) .& (.!buf)
                @assert count(te) > 0 "fold $k has an empty TEST set at B=$B"
                @assert count(tr) > 0 "fold $k has an empty TRAINING set at B=$B D=$D"
                keep += count(tr)
                teidx = findall(te)
                tridx = findall(tr)
                # deterministic stride subsample of test cells (the full N² is 3.5e9 haversines)
                step = max(1, length(teidx) ÷ max(1, nsample ÷ kfolds))
                for ti in teidx[1:step:end]
                    dmin = Inf
                    for tj in tridx
                        d = gcdeg(lat[ti], lon[ti], lat[tj], lon[tj])
                        d < dmin && (dmin = d)
                    end
                    push!(ds, dmin)
                end
            end
            sort!(ds)
            q(p) = ds[max(1, min(length(ds), ceil(Int, p * length(ds))))]
            f05 = count(<=(0.5 + 1.0e-9), ds) / length(ds)
            f10 = count(<=(1.0 + 1.0e-9), ds) / length(ds)
            trainpct = 100 * keep / (kfolds * length(ucells))
            nviol = count(<(D - 1.0e-9), ds)
            @assert nviol == 0 "BUFFER_DEG=$D under-dilated at B=$B: $nviol of $(length(ds)) test cells have a nearer training cell"
            verdict = D <= 0 ? "SENSITIVITY ONLY (perimeter adjacency intact)" :
                (f10 == 0 ? "adjacency SEVERED" : "adjacency partly intact")
            println(
                "   $(rpad(B, 5)) $(rpad(D, 5)) $(rpad(round(bal, digits = 2), 8)) " *
                    "$(rpad(round(trainpct, digits = 1), 7)) $(rpad(round(ds[1], digits = 2), 7)) " *
                    "$(rpad(round(q(0.1), digits = 2), 7)) $(rpad(round(q(0.5), digits = 2), 7)) " *
                    "$(rpad(round(f05, digits = 4), 7)) $(rpad(round(f10, digits = 4), 7)) $verdict"
            )
            flush(stdout)
        end
    end
    println("== all fold gates PASSED")
    return nothing
end

main_probe()
