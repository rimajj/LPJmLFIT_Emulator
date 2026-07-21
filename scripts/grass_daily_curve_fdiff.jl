# =============================================================================
# grass_daily_curve_fdiff.jl — F_diff's cell-mean DAILY grass NPP (+ GPP proxy) curve at the matched
# structure, for overlay against the C binary's NEW d_grass_gpp / d_grass_npp daily outputs.
#
# This is the F_diff counterpart to the C's daily grass GPP/NPP (built into the LPJmL-FIT source this
# session, conf.h ids 419/420). The C output is a CELL series (aggregated over the 25 patches, /npatch);
# so here F_diff runs each patch's matched structure (grass at the C's OWN 2008 leaf, trees fixed) and
# SUMS the per-day per-patch grass npp_ind over patches, /npatch → the cell-mean daily grass NPP curve.
#
# Purpose: resolve SEASON-LENGTH (fewer active days) vs AMPLITUDE (lower NPP per active day) — the two
# candidate lever classes for the §26.1 above-threshold grass-NPP level gap — by overlaying F_diff's
# daily curve on the C's OWN daily grass NPP curve for the same year.
#
# Writes a CSV: day, fdiff_cell_grass_npp  (gC/m2/day, cell-mean) for the chosen sim year.
#
#   run (SLURM): JULIA_DEPOT_PATH=$HOME/.julia \
#     /p/system/packages_rhel9/tools/julia/1.10.0/bin/julia --project=. scripts/grass_daily_curve_fdiff.jl [YEARINDEX]
#   YEARINDEX (1-based into the decadal forcing 2009..2019; default 1 = 2009).
# =============================================================================
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.Allometry
const F = FDiff
import LPJmLFITEmulator.FDiff: grass_treepools, rollout_daily_canopy, tebs_params, hainich_soilcolumn,
    individual_from_pools, _patch_fpars, PhotoParams, TempStressParams, WaterParams, FDiffParams

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
const YEARIDX = length(ARGS) >= 1 ? parse(Int, ARGS[1]) : 1
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

# structure: default the committed 2008 snapshot; ENV `GRASS_STRUCT_CSV` overrides with a per-year
# structure (the decadal validation feeds each year's OWN tree+grass structure — matched structure +
# matched forcing, the tightest test of F_diff's grass flux physics).
const STRUCT_CSV = get(ENV, "GRASS_STRUCT_CSV", joinpath(REFDIR, "hainich_individuals_2008.csv"))
ind = readcsv(STRUCT_CSV)
fdec = readcsv(joinpath(REFDIR, "hainich_decadal_forcing.csv"))
(sd, whcs, rdist) = readtable(joinpath(REFDIR, "hainich_soilcolumn.txt"))
soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)
fyear = Int.(round.(fcol(fdec, "year")))
years = sort(unique(fyear))
targyear = years[clamp(YEARIDX, 1, length(years))]
forc = [
    DailyForcing{Float64}(
            swdown = fcol(fdec, "swdown")[i], lwnet = fcol(fdec, "lwnet")[i], temp = fcol(fdec, "temp")[i],
            precip = fcol(fdec, "precip")[i], daylength = fcol(fdec, "daylength")[i], co2 = fcol(fdec, "co2")[i],
        ) for i in findall(==(targyear), fyear)
]
const NDY = length(forc)

vv(r, k) = parse(Float64, ind[k][r]); typ(r) = parse(Int, ind["type"][r]); patchof(r) = parse(Int, ind["patch"][r])
allpatches = sort(unique(patchof.(eachindex(ind["type"]))))
mkpool_t(r) = TreePools{Float64}(vv(r, "leaf_c"), vv(r, "sapwood_c"), vv(r, "heartwood_c"), vv(r, "root_c"), vv(r, "height"), vv(r, "crownarea"), vv(r, "nind"), vv(r, "sla"), vv(r, "wooddens"), false)
mktmpl_t(r) = Individual{Float64}(vv(r, "fpar_leafon"), 0.0, vv(r, "alphaa"), vv(r, "albedo_leaf"), vv(r, "emax"), vv(r, "sapwood_c"), vv(r, "root_c"), 0.0, 0.02, 0.04, 0.1, 0.4, vv(r, "nind"), PhotoParams{Float64}(; path = :c3, issla = true, sla = vv(r, "sla")), TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false)
# FAITHFUL grass id 8 photo params (temp_photos 10/30, albedo_leaf 0.23)
mktmpl_g() = Individual{Float64}(0.03, 1.0, 0.5, 0.23, 10.0, 0.0, 0.0, 0.0, 0.01, 0.15, 0.1, 0.4, 1.0, PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.042242), TempStressParams{Float64}(; temp_photos_low = 10.0, temp_photos_high = 30.0), true)
allom = Allometry.TreeAllometry{Float64}(); phys0 = tebs_params()
with_water(w; kw...) = (d = Dict(kw); WaterParams{Float64}(Any[haskey(d, f) ? d[f] : getfield(w, f) for f in fieldnames(WaterParams)]...))
rebundle(p, w) = FDiffParams{Float64}(; photo = p.photo, tstress = p.tstress, water = w, resp = p.resp, allom = p.allom, nlambda = p.nlambda, ω = p.ω)
physg = rebundle(phys0, with_water(phys0.water; grass_demand_gate = true, βgpd_gate = 1.0e8))

patchref = []
for pn in allpatches
    rows = [r for r in eachindex(ind["type"]) if patchof(r) == pn]
    trows = [r for r in rows if typ(r) <= 6 && vv(r, "height") > 0]
    grows = [r for r in rows if typ(r) >= 7]
    (isempty(trows) || isempty(grows)) && continue
    cgl = sum(vv(r, "agb_perm2") for r in grows); cgv = sum(vv(r, "vegc_perm2") for r in grows)
    push!(patchref, (pn = pn, trows = trows, cgl = cgl, cgv = cgv))
end
const NPATCH = 25   # the C cell has 25 patches; d_grass_npp is /npatch weighted

# per-day grass npp_ind for one patch
function patch_daily_grass_npp(pr)
    L = max(pr.cgl, 1.0e-6); root = max(pr.cgv - pr.cgl, 1.0e-6)
    trees = vcat([mkpool_t(r) for r in pr.trows], [grass_treepools(L, L + root, 0.042242)])
    tmpls = vcat([mktmpl_t(r) for r in pr.trows], [mktmpl_g()])
    gidx = length(trees); n = length(trees)
    fpars = _patch_fpars(trees, allom)
    inds = Individual{Float64}[individual_from_pools(tmpls[i], trees[i], allom, fpars[i]) for i in 1:n]
    st0 = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
    pids = vcat(fill(3, length(pr.trows)), [8])
    (_, days) = rollout_daily_canopy(physg, st0, inds, soil, forc; pft_ids = pids, grass_lf_mode = :linear)
    return [days[d].npp_ind[gidx] for d in 1:NDY]
end

cell = zeros(Float64, NDY)
for pr in patchref
    dp = patch_daily_grass_npp(pr)
    cell .+= dp ./ NPATCH      # cell-mean (/npatch), matching the C's d_grass_npp aggregation
end

out = joinpath(@__DIR__, "..", "logs", "fdiff_grass_daily_npp_$(targyear).csv")
open(out, "w") do io
    println(io, "# F_diff cell-mean daily grass NPP (matched structure, faithful params, demand-gate ON), sim year ", targyear)
    println(io, "day,fdiff_cell_grass_npp")
    for d in 1:NDY
        println(io, d, ",", round(cell[d], digits = 6))
    end
end
act = count(>(1.0e-4), cell) / NDY
println(
    "year ", targyear, ": F_diff cell-mean grass NPP annual = ", round(sum(cell), digits = 2),
    " gC/m2/yr; active-day frac = ", round(act, digits = 3), "; wrote ", out
)
println("DONE.")
