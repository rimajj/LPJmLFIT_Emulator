# diagnose_boundary_axes.jl — WHY does the transient boundary help Wooddens/D95max but hurt SLA/minwscal in
# the copula scenario-holdout (ADR 0027 open caveat)? Reads a POOLED copula table (Xc / Y_<axis> /
# scenario.i64 / manifest_copula.txt) and reports, per axis:
#   (H1) BETWEEN-REGIME marginal shift = KS(Y|historic, Y|ssp370): how much the trait DISTRIBUTION itself
#        differs between regimes. Hypothesis: Wooddens/D95max shift MORE than SLA/minwscal.
#   (H2) BOUNDARY vs FLUX feature importance of a forest fit on the full conditioning: does the copula's
#        marginal for this axis actually USE the boundary (gdd5/tas_cold)? Hypothesis: high for Wooddens/
#        D95max, low for SLA/minwscal.
# Read together: an axis whose distribution is regime-INVARIANT and that barely uses the boundary is one where
# the transient (regime-shifting, out-of-range-extrapolating) boundary can only add noise on a held-out regime
# — explaining the mixed ablation.
#
#   OUT=/p/tmp/jamirp/emulator_global/slow_copula_pooled_w20 julia scripts/diagnose_boundary_axes.jl

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

function ks2(a::AbstractVector{Float64}, b::AbstractVector{Float64})
    sa = sort(a); sb = sort(b); na = length(sa); nb = length(sb)
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
        d = max(d, abs((i - 1) / na - (j - 1) / nb))
    end
    return d
end

function main()
    man = read_manifest(joinpath(DATA, "manifest_copula.txt"))
    n = parse(Int, man["n"])
    ncond = parse(Int, man["ncond"])
    axes = split(man["axes"])
    cond = split(man["cond_cols"])
    tags = haskey(man, "pooled_scenarios") ? split(man["pooled_scenarios"]) : ["s0", "s1"]

    Xct = Matrix{Float64}(undef, ncond, n)
    read!(joinpath(DATA, "Xc.f64"), Xct)
    Xc = permutedims(Xct)
    scen = Vector{Int64}(undef, n)
    read!(joinpath(DATA, "scenario.i64"), scen)
    h = scen .== 0
    s = scen .== 1

    # boundary vs flux column groups (cond order = 4 flux drivers, then gdd5/tas_cold/soil_depth/co2)
    isbound(c) = c in ("eco_diag_gdd_5", "tas_cold_month", "soil_depth", "co2")
    bcols = findall(isbound, cond)
    fcols = findall(!isbound, cond)
    subsample = parse(Int, get(ENV, "SUBSAMPLE", "50000"))
    @info "loaded" n ncond axes cond n_hist = count(h) n_ssp = count(s)
    println("cond cols: ", join(string.(1:ncond, "=", cond), "  "))
    println(
        rpad("axis", 11), rpad("between-regime KS (H1)", 24), rpad("boundary imp (H2)", 20),
        rpad("flux imp", 12), "top-3 features"
    )

    for (ai, ax) in enumerate(axes)
        Y = Vector{Float64}(undef, n)
        read!(joinpath(DATA, "Y_$(ax).f64"), Y)
        brks = ks2(Y[h], Y[s])                                   # H1: how much the marginal shifts by regime
        f = DRF.fit_forest(
            Xc, Y; ntrees = 60, max_depth = 14, min_leaf = 20,
            subsample = min(subsample, n), seed = ai,
        )
        imp = DRF.feature_importance(f)                          # H2: split-count importance per cond col
        bimp = sum(imp[bcols]); fimp = sum(imp[fcols])
        top = sort(collect(1:ncond); by = k -> -imp[k])[1:3]
        topstr = join(("$(cond[k])=$(round(imp[k], digits = 3))" for k in top), ", ")
        println(
            rpad(ax, 11), rpad(round(brks, digits = 4), 24), rpad(round(bimp, digits = 4), 20),
            rpad(round(fimp, digits = 4), 12), topstr
        )
    end
    println("\n(H1 large + H2 boundary-imp large ⇒ boundary is genuine regime signal for that axis → transient helps;")
    println(" H1 small + H2 boundary-imp small ⇒ regime-invariant, boundary near-noise → transient adds OOS noise.)")
    return nothing
end

main()
