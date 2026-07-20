# =============================================================================
# grass_fapar_faithfulness_check.jl — ADVERSARIAL check of §24 Finding 4's premise
# ("F_diff's grass absorbed-PAR reproduces the C's recorded fpar_leafon per patch, so the
# forest-floor light / grass light ABSORPTION is faithful and the overshoot is a per-absorbed-light
# NPP gap, NOT a forest-floor-light error"). §24 verified this only at patch 15 (the §20 5-s.f.
# match). This checks ALL 25 patches: build the C's OWN 2010 per-patch structure (trees + grass at
# the C's agb/vegc), recompute F_diff's layered `_patch_fpars` grass fapar, and compare to the C's
# recorded `fpar_leafon`. If F_diff's grass fapar SYSTEMATICALLY EXCEEDS the C's, Finding 4 is REFUTED
# (the overshoot would then be a forest-floor-light / over-absorption error, not a carbon-balance gap).
#
#   run:  JULIA_DEPOT_PATH=$HOME/.julia julia --project=. scripts/grass_fapar_faithfulness_check.jl
# =============================================================================
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.Allometry
const F = FDiff
import LPJmLFITEmulator.FDiff: grass_treepools, _patch_fpars

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
readcsv(path) = begin
    lines = readlines(path)
    i = findfirst(l -> !startswith(strip(l), "#") && !isempty(strip(l)), lines)
    hdr = split(strip(lines[i]), ',')
    rows = [split(strip(l), ',') for l in lines[(i + 1):end] if !isempty(strip(l))]
    Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
end
_mean(x) = isempty(x) ? 0.0 : sum(x) / length(x)
_median(x) = (s = sort(x); isempty(s) ? 0.0 : (n = length(s); isodd(n) ? s[(n + 1) ÷ 2] : (s[n ÷ 2] + s[n ÷ 2 + 1]) / 2))

ind = readcsv(joinpath(REFDIR, "hainich_individuals_2010.csv"))
vv(r, k) = parse(Float64, ind[k][r])
typ(r) = parse(Int, ind["type"][r])
patchof(r) = parse(Int, ind["patch"][r])
allom = Allometry.TreeAllometry{Float64}()

mkpool_t(r) = TreePools{Float64}(vv(r, "leaf_c"), vv(r, "sapwood_c"), 0.0, vv(r, "root_c"), vv(r, "height"), vv(r, "crownarea"), vv(r, "nind"), vv(r, "sla"), vv(r, "wooddens"), false)

println("Comparing F_diff `_patch_fpars` grass fapar (at the C's OWN 2010 structure) to the C's recorded fpar_leafon.")
println(rpad("patch", 6), rpad("C_grass_lai", 12), rpad("Fdiff_fapar", 13), rpad("C_fpar_leafon", 15), "Fdiff/C")
ratios = Float64[]
for pn in sort(unique(patchof.(eachindex(ind["type"]))))
    rows = [r for r in eachindex(ind["type"]) if patchof(r) == pn]
    trows = [r for r in rows if typ(r) <= 6 && vv(r, "height") > 0]
    grows = [r for r in rows if typ(r) >= 7]
    isempty(grows) && continue
    gr = grows[1]
    cgl = vv(gr, "agb"); cgv = vv(gr, "vegc"); slag = vv(gr, "sla")
    cfpar = vv(gr, "fpar_leafon"); clai = vv(gr, "lai")
    trees = vcat([mkpool_t(r) for r in trows], [grass_treepools(cgl, cgv, slag)])
    fpars = _patch_fpars(trees, allom)
    ff = fpars[end]
    (cfpar > 1.0e-6) || continue
    push!(ratios, ff / cfpar)
    println(
        rpad(pn, 6), rpad(round(clai, digits = 4), 12), rpad(round(ff, digits = 6), 13),
        rpad(round(cfpar, digits = 6), 15), round(ff / cfpar, digits = 3)
    )
end
println(
    "\nFdiff/C grass-fapar ratio across patches: median ", round(_median(ratios), digits = 4),
    "  mean ", round(_mean(ratios), digits = 4), "  range [", round(minimum(ratios), digits = 3), ", ", round(maximum(ratios), digits = 3), "]"
)
# Finding 4 holds if F_diff's grass fapar ≈ the C's (ratio ≈ 1) — i.e. the light ABSORPTION is faithful and
# the overshoot is a per-absorbed-light NPP gap, NOT an over-absorption / forest-floor-light error.
if 0.9 <= _median(ratios) <= 1.1
    println("✓ §24 Finding 4 CONFIRMED: F_diff grass fapar reproduces the C's per patch (median within 10%) — the")
    println("  forest-floor light + grass absorption are faithful; the overshoot is a per-absorbed-light NPP gap.")
else
    println(
        "✗ §24 Finding 4 CHALLENGED: F_diff grass fapar departs from the C's (median ratio ",
        round(_median(ratios), digits = 3), ") — the light path may be the (co-)culprit; re-examine."
    )
end
@assert 0.85 <= _median(ratios) <= 1.15 "grass-fapar faithfulness: median Fdiff/C ratio $(_median(ratios)) outside [0.85,1.15]"
