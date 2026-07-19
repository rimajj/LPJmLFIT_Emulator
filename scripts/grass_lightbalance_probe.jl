# =============================================================================
# grass_lightbalance_probe.jl — pin the MECHANISM of the F_diff grass overshoot
# (grass_cover_mechanism_diagnosis.jl showed a real ×13.87 overshoot at the C's OWN fixed
# forest-floor light, with F_diff's grass nearly INSENSITIVE to shading — corr 0.57 vs the
# C's 4-orders-of-magnitude light gradient). This probe decomposes WHY.
#
# For a SHADED patch (3, ff_light≈0.14, C grass leaf 0.011) and a LIT patch (13, ff≈0.50,
# C grass leaf 215), at the C's FIXED 2008 tree structure, sweep the grass leaf carbon and
# report the one-year self-computed grass ANNUAL NPP vs the steady-state turnover requirement
# (leaf fully renews + root turns over ⇒ NPP* ≈ 1.8·leaf at the C's lmtorm≈0.8). The grass
# equilibrium is where NPP(leaf) crosses 1.8·leaf. Also report the grass's mean absorbed-PAR
# fraction (fpar, tree-attenuated) and mean cover (fpc, UN-attenuated) and annual GPP — so we
# can see whether the grass GPP tracks the tree-set forest-floor light (light-limited, as the C)
# or the un-attenuated cover (conductance-limited, the suspected F_diff failure).
#
#   run:  JULIA_DEPOT_PATH=$HOME/.julia julia --project=. scripts/grass_lightbalance_probe.jl
# =============================================================================
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.Allometry
const F = FDiff
import LPJmLFITEmulator.FDiff: grass_treepools, rollout_daily_canopy, tebs_params, tebs_allocparams,
    hainich_soilcolumn, individual_from_pools, _patch_fpars, grass_allocparams

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
readcsv(path) = begin
    lines = readlines(path)
    i = findfirst(l -> !startswith(strip(l), "#") && !isempty(strip(l)), lines)
    hdr = split(strip(lines[i]), ',')
    rows = [split(strip(l), ',') for l in lines[(i + 1):end] if !isempty(strip(l))]
    Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
end
readtable(path) = begin
    D = Float64[]; W = Float64[]; R = Float64[]
    for ln in eachline(path)
        s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
        v = parse.(Float64, split(s)); push!(D, v[2]); push!(W, v[3]); push!(R, v[4])
    end
    (D, W, R)
end
fcol(d, k) = parse.(Float64, d[k])
_mean(x) = isempty(x) ? 0.0 : sum(x) / length(x)

ind = readcsv(joinpath(REFDIR, "hainich_individuals_2008.csv"))
fdec = readcsv(joinpath(REFDIR, "hainich_decadal_forcing.csv"))
(sd, whcs, rdist) = readtable(joinpath(REFDIR, "hainich_soilcolumn.txt"))
soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)
fyear = Int.(round.(fcol(fdec, "year")))
yr1 = minimum(fyear)                       # use the first decadal year's forcing (2009)
forc = [
    DailyForcing{Float64}(
            swdown = fcol(fdec, "swdown")[i], lwnet = fcol(fdec, "lwnet")[i], temp = fcol(fdec, "temp")[i],
            precip = fcol(fdec, "precip")[i], daylength = fcol(fdec, "daylength")[i], co2 = fcol(fdec, "co2")[i],
        ) for i in findall(==(yr1), fyear)
]

vv(r, k) = parse(Float64, ind[k][r])
typ(r) = parse(Int, ind["type"][r])
patchof(r) = parse(Int, ind["patch"][r])
mkpool_t(r) = TreePools{Float64}(vv(r, "leaf_c"), vv(r, "sapwood_c"), vv(r, "heartwood_c"), vv(r, "root_c"), vv(r, "height"), vv(r, "crownarea"), vv(r, "nind"), vv(r, "sla"), vv(r, "wooddens"), false)
mktmpl_t(r) = Individual{Float64}(vv(r, "fpar_leafon"), 0.0, vv(r, "alphaa"), vv(r, "albedo_leaf"), vv(r, "emax"), vv(r, "sapwood_c"), vv(r, "root_c"), 0.0, 0.02, 0.04, 0.1, 0.4, vv(r, "nind"), FDiff.PhotoParams{Float64}(; path = :c3, issla = true, sla = vv(r, "sla")), FDiff.TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false)
mktmpl_g() = Individual{Float64}(0.03, 1.0, 0.5, 0.15, 10.0, 0.0, 0.0, 0.0, 0.01, 0.15, 0.1, 0.4, 1.0, FDiff.PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.042242), FDiff.TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), true)
allom = Allometry.TreeAllometry{Float64}(); phys = tebs_params()

# grass at a prescribed leaf carbon L (root = L/lmtorm at the lmro≈0.8 equilibrium) in a fixed tree env;
# run ONE year, return (annual grass NPP, annual grass GPP, mean fpar, mean fpc, forest-floor light)
function grass_year(trows, L; lmtorm = 0.8)
    slag = 0.042242
    root = L / lmtorm
    trees = vcat([mkpool_t(r) for r in trows], [grass_treepools(max(L, 1.0e-6), max(L + root, 2.0e-6), slag)])
    tmpls = vcat([mktmpl_t(r) for r in trows], [mktmpl_g()])
    gidx = length(trees)
    fpars = _patch_fpars(trees, allom)
    n = length(trees)
    inds = Individual{Float64}[individual_from_pools(tmpls[i], trees[i], allom, fpars[i]) for i in 1:n]
    st0 = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
    (_, days) = rollout_daily_canopy(phys, st0, inds, soil, forc)
    npp = sum(d.npp_ind[gidx] for d in days)
    # per-day grass GPP not directly exposed; approximate grass GPP via fapar record is not returned —
    # report NPP (the balance-relevant flux) + the grass fpar/fpc from the built individual.
    gi = inds[gidx]
    plai = 0.0
    for t in trees
        (t.is_grass || t.height <= 0 || t.leaf_c <= 0) && continue
        plai += t.leaf_c * t.sla * t.nind
    end
    ff = exp(-0.5 * plai)
    return (npp = npp, fpar = fpars[gidx], fpc = gi.fpc, ff = ff)
end

leafs = [0.01, 0.05, 0.2, 1.0, 3.0, 10.0, 30.0, 90.0]
npp_lowleaf = Dict{Int, Float64}()   # NPP at leaf 0.01 per patch (light-insensitivity check)
for (label, pn) in (("SHADED patch 3", 3), ("LIT patch 13", 13))
    rows = [r for r in eachindex(ind["type"]) if patchof(r) == pn]
    trows = [r for r in rows if typ(r) <= 6 && vv(r, "height") > 0]
    println("\n================ $label ================")
    r0 = grass_year(trows, 3.0)
    println("forest-floor light (leaf-on tree canopy) = ", round(r0.ff, digits = 4))
    println(rpad("grass_leaf", 12), rpad("grass_NPP", 12), rpad("turnover=1.8L", 14), rpad("NPP/turnover", 14), rpad("fpar(atten)", 13), "fpc(unatten)")
    for L in leafs
        r = grass_year(trows, L)
        turn = 1.8 * L
        L == leafs[1] && (npp_lowleaf[pn] = r.npp)
        println(
            rpad(L, 12), rpad(round(r.npp, digits = 3), 12), rpad(round(turn, digits = 3), 14),
            rpad(round(r.npp / max(turn, 1.0e-6), digits = 3), 14), rpad(round(r.fpar, digits = 5), 13), round(r.fpc, digits = 4)
        )
    end
    println(
        "  → grass is in balance where NPP/turnover crosses 1. The C's equilibrium leaf here:",
        pn == 3 ? " 0.004 (extinct, C NPP 0.005)" : " 222 (thriving, C NPP 399)"
    )
end
println("\nKEY: if F_diff grass NPP/turnover > 1 at the C's tiny equilibrium leaf in the SHADED patch,")
println("F_diff's grass is NOT light-suppressed like the C — the light-limited carbon balance is the gap.")

# ── assertions ──
# The grass NPP is NOT suppressed under deep shade: at the shaded patch's ~zero-leaf state (fapar ≈ 0,
# where the C's grass NPP ≈ 0.005) F_diff still makes several gC/m²/yr — an un-light-limited floor.
@assert npp_lowleaf[3] > 1.0 "expected an un-light-limited grass NPP floor in the shaded patch (>1), got $(npp_lowleaf[3])"
# That floor is light-INSENSITIVE: the shaded-patch and lit-patch low-leaf NPP are nearly equal, though
# the forest-floor light differs ~3.6× — the fingerprint of a GPP that does not scale with absorbed light.
@assert abs(npp_lowleaf[3] - npp_lowleaf[13]) / max(npp_lowleaf[13], 1.0e-9) < 0.25 "expected light-insensitive low-leaf NPP (shaded≈lit), got $(npp_lowleaf[3]) vs $(npp_lowleaf[13])"
println("\nASSERTED ✓  grass NPP has a light-insensitive floor (≈$(round(npp_lowleaf[3], digits = 2)) gC/m²/yr) — the light-limitation gap.")
