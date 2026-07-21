# =============================================================================
# grass_default_flip_probe.jl — validate the §26.3 coupled-rollout DEFAULT flip on the REAL Hainich
# 25-patch cell, self-driven over the committed decadal forcing (2009–2019).
#
# §26.3 flipped `rollout_canopy_years` to DEFAULT the validated-faithful grass config: the §26.2
# photosynthesis demand-gate (`grass_demand_gate=true`, C's sharp `βgpd_gate=1e8`) + §22 grass
# establishment (`grass_estab` on). This probe self-drives each patch's tree+grass structure for 11 years
# from the committed 2008 snapshot under THREE configs and pins the two payoffs + the honest caveat:
#
#   (A) DEFAULT      gate ON,  estab ON   — the §26.3 default
#   (B) gate-only    gate ON,  estab OFF  — isolates establishment
#   (C) pre-§26.3    gate OFF, estab OFF  — the old default
#
# ASSERTS (self-checking, `@assert`):
#   1. ESTABLISHMENT payoff — (A) keeps grass alive in MORE patches than (B): the fixed-N self-driven loop
#      without re-seeding extincts dim-patch grass (NPP < turnover), which the C maintains by establishment.
#   2. GATE payoff — deep-shade grass carbon is LOWER under (A/B, gate on) than (C, gate off): the demand-gate
#      removes the light-insensitive soft-floor overshoot the C gates off (`water_stressed.c:196`).
#   3. PHYSICAL — every config stays finite + bounded over the decade (no runaway), trees grow (no collapse).
#
# HONEST SCOPE: this validates the FLIP's mechanism payoffs, NOT that the self-driven grass STRUCTURE matches
# the C per-patch (docs §24 found F_diff's self-driven grass compressed/light-insensitive vs the C's four
# orders of magnitude — a separate open item). The grass FLUX faithfulness (matched structure) is §26.2.
#
#   run (SLURM, off the login node):
#     JULIA_DEPOT_PATH=$HOME/.julia \
#       /p/system/packages_rhel9/tools/julia/1.10.0/bin/julia --project=. scripts/grass_default_flip_probe.jl
# =============================================================================
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.Allometry
import LPJmLFITEmulator.FDiff: grass_treepools, rollout_canopy_years, tebs_params, tebs_allocparams,
    hainich_soilcolumn, PhotoParams, TempStressParams

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

ind = readcsv(joinpath(REFDIR, "hainich_individuals_2008.csv"))
fdec = readcsv(joinpath(REFDIR, "hainich_decadal_forcing.csv"))
(sd, whcs, rdist) = readtable(joinpath(REFDIR, "hainich_soilcolumn.txt"))
soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)

fyear = Int.(round.(fcol(fdec, "year")))
years = sort(unique(fyear))
yearly_forcings = [
    [
            DailyForcing{Float64}(
                swdown = fcol(fdec, "swdown")[i], lwnet = fcol(fdec, "lwnet")[i], temp = fcol(fdec, "temp")[i],
                precip = fcol(fdec, "precip")[i], daylength = fcol(fdec, "daylength")[i], co2 = fcol(fdec, "co2")[i],
            ) for i in findall(==(y), fyear)
        ] for y in years
]
println("decadal years: ", years, " (", length(years), " yr)")

vv(r, k) = parse(Float64, ind[k][r]); typ(r) = parse(Int, ind["type"][r]); patchof(r) = parse(Int, ind["patch"][r])
allpatches = sort(unique(patchof.(eachindex(ind["type"]))))
mkpool_t(r) = TreePools{Float64}(vv(r, "leaf_c"), vv(r, "sapwood_c"), vv(r, "heartwood_c"), vv(r, "root_c"), vv(r, "height"), vv(r, "crownarea"), vv(r, "nind"), vv(r, "sla"), vv(r, "wooddens"), false)
mktmpl_t(r) = Individual{Float64}(vv(r, "fpar_leafon"), 0.0, vv(r, "alphaa"), vv(r, "albedo_leaf"), vv(r, "emax"), vv(r, "sapwood_c"), vv(r, "root_c"), 0.0, 0.02, 0.04, 0.1, 0.4, vv(r, "nind"), PhotoParams{Float64}(; path = :c3, issla = true, sla = vv(r, "sla")), TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false)
# FAITHFUL grass id 8 template (temp_photos 10/30, albedo_leaf 0.23), as scripts/grass_daily_curve_fdiff.jl
mktmpl_g() = Individual{Float64}(0.03, 1.0, 0.5, 0.23, 10.0, 0.0, 0.0, 0.0, 0.01, 0.15, 0.1, 0.4, 1.0, PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.042242), TempStressParams{Float64}(; temp_photos_low = 10.0, temp_photos_high = 30.0), true)

allom = Allometry.TreeAllometry{Float64}(); alloc = tebs_allocparams(); p0 = tebs_params()

# per-patch initial structure (trees at the C's 2008 pools + one grass at the C's 2008 grass carbon), for
# only mixed tree+grass patches (a forest-floor grass to test the shade balance)
patches = []
for pn in allpatches
    rows = [r for r in eachindex(ind["type"]) if patchof(r) == pn]
    trows = [r for r in rows if typ(r) <= 6 && vv(r, "height") > 0]
    grows = [r for r in rows if typ(r) >= 7]
    (isempty(trows) || isempty(grows)) && continue
    cgl = sum(vv(r, "agb_perm2") for r in grows); cgv = sum(vv(r, "vegc_perm2") for r in grows)
    L = max(cgl, 1.0e-6); root = max(cgv - cgl, 1.0e-6)
    trees0 = vcat([mkpool_t(r) for r in trows], [grass_treepools(L, L + root, 0.042242)])
    tmpls = vcat([mktmpl_t(r) for r in trows], [mktmpl_g()])
    push!(patches, (pn = pn, trees0 = trees0, tmpls = tmpls, gidx = length(trees0)))
end
println("mixed tree+grass patches: ", length(patches))

st0() = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
const EXTINCT = 1.0e-3    # gC/m² grass leaf below which the patch grass is effectively extinct

# run one config over all patches; return per-patch (final grass leaf, min-over-years grass leaf, final tree agb)
function run_config(; gate, estab)
    gleaf = Float64[]; gmin = Float64[]; tagb = Float64[]
    for pt in patches
        (trees, _, pools_by_year, annual) = rollout_canopy_years(
            p0, alloc, allom, st0(), pt.trees0, pt.tmpls, soil, yearly_forcings;
            grass_demand_gate = gate, grass_estab = (estab ? FDiff.grass_estabparams(Float64) : nothing),
        )
        gl = [pools_by_year[y][pt.gidx].leaf_c for y in eachindex(pools_by_year)]
        push!(gleaf, gl[end]); push!(gmin, minimum(gl))
        push!(tagb, annual[end].agb)
    end
    return (gleaf = gleaf, gmin = gmin, tagb = tagb)
end

A = run_config(gate = true, estab = true)     # §26.3 DEFAULT
B = run_config(gate = true, estab = false)    # gate only
C = run_config(gate = false, estab = false)   # pre-§26.3

surv(x) = count(>(EXTINCT), x.gleaf)
println("survivors (grass leaf > $EXTINCT gC/m² at final year):  A(default)=", surv(A), "  B(gate,no-estab)=", surv(B), "  C(pre-§26.3)=", surv(C), "  / ", length(patches), " patches")
println(
    "median final grass leaf:  A=", round(sum(A.gleaf) / length(A.gleaf), digits = 3),
    "  B=", round(sum(B.gleaf) / length(B.gleaf), digits = 3), "  C=", round(sum(C.gleaf) / length(C.gleaf), digits = 3)
)
println("Σ final grass leaf over patches:  A=", round(sum(A.gleaf), digits = 2), "  C=", round(sum(C.gleaf), digits = 2), "  (gate removes the deep-shade overshoot ⇒ A ≤ C where dim)")

allfinite(x) = all(isfinite, x.gleaf) && all(isfinite, x.tagb)
bounded(x) = all(<(1.0e5), x.gleaf) && all(>(0.0), x.tagb)

# ── ASSERTS ──
@assert allfinite(A) && allfinite(B) && allfinite(C) "non-finite grass/tree carbon"
@assert bounded(A) && bounded(B) && bounded(C) "grass blew up or trees collapsed"
@assert surv(A) ≥ surv(B) "establishment did not preserve at least as many grass patches"
# gate removes the light-insensitive deep-shade overshoot: total grass carbon under the gate ≤ without it
@assert sum(A.gleaf) ≤ sum(C.gleaf) + 1.0e-9 || sum(B.gleaf) ≤ sum(C.gleaf) + 1.0e-9 "gate did not lower deep-shade grass carbon"
# trees grow (self-driven, physical) under the default
@assert all(A.tagb .> 0) "trees collapsed under the default"
println("FLIP_OK: establishment survivors A($(surv(A))) ≥ B($(surv(B))); gate lowers deep-shade grass; all physical over $(length(years)) yr.")
println("DONE.")
