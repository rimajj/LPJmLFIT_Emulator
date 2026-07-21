# =============================================================================
# grass_drought_soilmemory_probe.jl — RESOLVE the confound in grass_drought_amplitude_probe.jl: does the
# 2018 grass-NPP amplitude overshoot survive when F_diff runs its OWN multi-year soil-water balance (soil
# carried across years) at the C's structure, instead of resetting the soil to 0.9·WHC every year?
#
# The matched-structure amplitude probe found the 2018 F/C 1.87 is a WATER-response effect (leaf-artifact
# ruled out; F's growing-season wscal barely dropped, 0.939 vs 0.976 wet-year) — but it reset the soil to
# 0.9·WHC EACH YEAR, so F_diff never saw the CUMULATIVE drought (it started 2018 artificially wet). This
# probe feeds the SAME per-year C structure but CARRIES the per-patch soil column across 2009→2019 (F_diff's
# own continuous water balance). If 2018's wscal now drops hard and F/C → ~1, the residual was the
# fresh-soil setup; if 2018 STILL over-produces, it is a genuine grass water-sensitivity gap.
#
#   run (SLURM): JULIA_DEPOT_PATH=$HOME/.julia \
#     /p/system/packages_rhel9/tools/julia/1.10.0/bin/julia --project=. scripts/grass_drought_soilmemory_probe.jl
# =============================================================================
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.Allometry
import LPJmLFITEmulator.FDiff: grass_treepools, rollout_daily_canopy, tebs_params, hainich_soilcolumn,
    individual_from_pools, _patch_fpars, PhotoParams, TempStressParams, WaterParams, FDiffParams

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
const STRUCTDIR = "/p/tmp/jamirp/esm_land_emulator_data/fdiff_grass_decadal_struct"
const NPATCH = 25
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

fdec = readcsv(joinpath(REFDIR, "hainich_decadal_forcing.csv"))
(sd, whcs, rdist) = readtable(joinpath(REFDIR, "hainich_soilcolumn.txt"))
soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)
gdaily = readcsv(joinpath(REFDIR, "hainich_grass_daily_2009_2019.csv"))
fyear = Int.(round.(fcol(fdec, "year"))); fdoy = Int.(round.(fcol(fdec, "doy")))
years = sort(unique(fyear))
gcy = Int.(round.(fcol(gdaily, "year"))); gcnpp = fcol(gdaily, "c_grass_npp")
C_ann(y) = sum(gcnpp[gcy .== y])

allom = Allometry.TreeAllometry{Float64}(); phys0 = tebs_params()
with_water(w; kw...) = (d = Dict(kw); WaterParams{Float64}(Any[haskey(d, f) ? d[f] : getfield(w, f) for f in fieldnames(WaterParams)]...))
rebundle(p, w) = FDiffParams{Float64}(; photo = p.photo, tstress = p.tstress, water = w, resp = p.resp, allom = p.allom, nlambda = p.nlambda, ω = p.ω)
physg = rebundle(phys0, with_water(phys0.water; grass_demand_gate = true, βgpd_gate = 1.0e8))

mkpool_t(ind, r) = TreePools{Float64}(parse(Float64, ind["leaf_c"][r]), parse(Float64, ind["sapwood_c"][r]), parse(Float64, ind["heartwood_c"][r]), parse(Float64, ind["root_c"][r]), parse(Float64, ind["height"][r]), parse(Float64, ind["crownarea"][r]), parse(Float64, ind["nind"][r]), parse(Float64, ind["sla"][r]), parse(Float64, ind["wooddens"][r]), false)
mktmpl_t(ind, r) = Individual{Float64}(parse(Float64, ind["fpar_leafon"][r]), 0.0, parse(Float64, ind["alphaa"][r]), parse(Float64, ind["albedo_leaf"][r]), parse(Float64, ind["emax"][r]), parse(Float64, ind["sapwood_c"][r]), parse(Float64, ind["root_c"][r]), 0.0, 0.02, 0.04, 0.1, 0.4, parse(Float64, ind["nind"][r]), PhotoParams{Float64}(; path = :c3, issla = true, sla = parse(Float64, ind["sla"][r])), TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false)
mktmpl_g() = Individual{Float64}(0.03, 1.0, 0.5, 0.23, 10.0, 0.0, 0.0, 0.0, 0.01, 0.15, 0.1, 0.4, 1.0, PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.042242), TempStressParams{Float64}(; temp_photos_low = 10.0, temp_photos_high = 30.0), true)

# pre-load each year's structure + forcing
struct_of = Dict(y => readcsv(joinpath(STRUCTDIR, "hainich_individuals_$(y).csv")) for y in years)
forc_of = Dict(
    y => [
            DailyForcing{Float64}(
                swdown = fcol(fdec, "swdown")[i], lwnet = fcol(fdec, "lwnet")[i], temp = fcol(fdec, "temp")[i],
                precip = fcol(fdec, "precip")[i], daylength = fcol(fdec, "daylength")[i], co2 = fcol(fdec, "co2")[i],
            ) for i in findall(==(y), fyear)
        ] for y in years
)
gsdays_of = Dict(y => [d for (d, i) in enumerate(findall(==(y), fyear)) if 91 <= fdoy[i] <= 273] for y in years)
patchlist(ind) = begin
    typ(r) = parse(Int, ind["type"][r]); patchof(r) = parse(Int, ind["patch"][r])
    out = []
    for pn in sort(unique(patchof.(eachindex(ind["type"]))))
        rows = [r for r in eachindex(ind["type"]) if patchof(r) == pn]
        trows = [r for r in rows if typ(r) <= 6 && parse(Float64, ind["height"][r]) > 0]
        grows = [r for r in rows if typ(r) >= 7]
        (isempty(trows) || isempty(grows)) && continue
        push!(out, (pn = pn, trows = trows, grows = grows))
    end
    out
end
# patch numbers present in ALL years (so the soil-carry chain is well-defined per patch)
common = intersect([Set(p.pn for p in patchlist(struct_of[y])) for y in years]...)

# CARRIED-SOIL run: for each common patch, chain years carrying `st`; collect per-(patch,year) grass NPP + GS wscal
Fnpp = Dict(y => 0.0 for y in years); Wsc = Dict(y => 0.0 for y in years); Wn = Dict(y => 0 for y in years)
for pn in common
    st = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)     # carried across years for THIS patch
    for y in years
        ind = struct_of[y]
        pl = patchlist(ind); pr = pl[findfirst(p -> p.pn == pn, pl)]
        cgl = sum(parse(Float64, ind["agb_perm2"][r]) for r in pr.grows)
        cgv = sum(parse(Float64, ind["vegc_perm2"][r]) for r in pr.grows)
        L = max(cgl, 1.0e-6); root = max(cgv - cgl, 1.0e-6)
        trees = vcat([mkpool_t(ind, r) for r in pr.trows], [grass_treepools(L, L + root, 0.042242)])
        tmpls = vcat([mktmpl_t(ind, r) for r in pr.trows], [mktmpl_g()])
        gidx = length(trees); n = length(trees)
        fpars = _patch_fpars(trees, allom)
        inds = Individual{Float64}[individual_from_pools(tmpls[i], trees[i], allom, fpars[i]) for i in 1:n]
        pids = vcat(fill(3, length(pr.trows)), [8])
        (st, days) = rollout_daily_canopy(physg, st, inds, soil, forc_of[y]; pft_ids = pids, grass_lf_mode = :linear)
        Fnpp[y] += sum(days[d].npp_ind[gidx] for d in eachindex(days)) / NPATCH
        for d in gsdays_of[y]
            Wsc[y] += days[d].wscal; Wn[y] += 1
        end
    end
end

println("(carried soil; ", length(common), " patches common to all years)")
println("year   C_ann   F_ann    F/C   F_GSwscal")
for y in years
    println(
        rpad(y, 6), lpad(round(C_ann(y), digits = 1), 7), lpad(round(Fnpp[y], digits = 1), 8),
        lpad(round(Fnpp[y] / C_ann(y), digits = 2), 7), lpad(round(Wsc[y] / max(Wn[y], 1), digits = 3), 10)
    )
end
fc2018 = Fnpp[2018] / C_ann(2018)
wsc2018 = Wsc[2018] / max(Wn[2018], 1)
wetwsc = sum(Wsc[y] / max(Wn[y], 1) for y in (2010, 2013, 2017)) / 3
println("\n=== soil-memory verdict ===")
println("2018 F/C (carried soil) = ", round(fc2018, digits = 2), "   [matched-structure fresh-soil probe: 1.87]")
println(
    "2018 F_GSwscal (carried) = ", round(wsc2018, digits = 3), "  vs wet-year mean ", round(wetwsc, digits = 3),
    "   [fresh-soil: 0.939 vs 0.976]"
)
if wsc2018 < 0.85 * wetwsc && fc2018 < 1.4
    println("  → the fresh-soil SETUP drove most of the 2018 overshoot: carrying F_diff's own soil balance captures the drought (wscal drops hard, F/C→~1). The residual is largely a matched-structure-probe artifact, not a grass physics gap.")
elseif fc2018 > 1.5
    println("  → GENUINE grass water-sensitivity gap: even with F_diff's own multi-year soil balance, 2018 grass over-produces — the drought does not suppress the grass enough.")
else
    println("  → PARTIAL: carried soil reduces but does not eliminate the 2018 overshoot — inspect the wscal drop + table.")
end
println("DONE.")
