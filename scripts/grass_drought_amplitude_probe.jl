# =============================================================================
# grass_drought_amplitude_probe.jl — DIAGNOSE the §26.2 warm/dry-year grass-NPP AMPLITUDE residual
# (2018 European drought: matched-structure F/C 1.87, ampR 1.69, season faithful actR≈1.0).
#
# QUESTION (diagnosis-first — this thread has a history of mis-attributed grass diagnoses): is the 2018
# per-active-day amplitude overshoot a REAL grass water-limitation-of-GPP sensitivity gap, or a per-year
# `ind` structure-reconstruction artifact (the fed 2018 grass leaf too high)?
#
# METHOD. For each decadal sim year 2009–2019, run F_diff's daily grass at that year's OWN C structure
# (the per-year `ind` slices on /p/tmp, as the §26.2 addendum) with the §26.3 faithful config
# (demand-gate ON, faithful grass params), and record per year:
#   • F_ann   — F_diff cell-mean grass annual NPP (gC/m²/yr)
#   • fed_leaf — cell-mean grass leaf fed to F_diff that year (Σ patch agb_perm2 / npatch) — the MATCHED
#                structure, so a per-leaf flux gap (vs a leaf artifact) is separable
#   • F_gswsc — F_diff growing-season (doy 91–273) mean stand water scalar `wscal` (did the drought
#                propagate into F_diff's water state?)
#   • C_ann   — the C's grass annual NPP (committed hainich_grass_daily_2009_2019.csv)
# then reports F/C, F_ann/fed_leaf (per-leaf flux), and the 2018-vs-normal contrast + correlations that
# CLASSIFY the residual:
#   (i) F/C tracks fed_leaf/C_ann but F_ann/fed_leaf ≈ constant across wet/dry ⇒ STRUCTURE-reconstruction;
#   (ii) F_gswsc DROPS in 2018 (drought captured) yet F_ann/fed_leaf stays high ⇒ wscal→GPP coupling too
#        weak (a WATER-limitation-of-GPP sensitivity gap on active days);
#   (iii) F_gswsc does NOT drop in 2018 ⇒ soil-water/supply gap (drought not reaching the grass water balance).
#
#   run (SLURM, off the login node):
#     JULIA_DEPOT_PATH=$HOME/.julia \
#       /p/system/packages_rhel9/tools/julia/1.10.0/bin/julia --project=. scripts/grass_drought_amplitude_probe.jl
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
fyear = Int.(round.(fcol(fdec, "year")))
fdoy = Int.(round.(fcol(fdec, "doy")))
years = sort(unique(fyear))

# C annual grass NPP per year (committed daily reference)
gcy = Int.(round.(fcol(gdaily, "year"))); gcnpp = fcol(gdaily, "c_grass_npp")
C_ann(y) = sum(gcnpp[gcy .== y])

allom = Allometry.TreeAllometry{Float64}(); phys0 = tebs_params()
with_water(w; kw...) = (d = Dict(kw); WaterParams{Float64}(Any[haskey(d, f) ? d[f] : getfield(w, f) for f in fieldnames(WaterParams)]...))
rebundle(p, w) = FDiffParams{Float64}(; photo = p.photo, tstress = p.tstress, water = w, resp = p.resp, allom = p.allom, nlambda = p.nlambda, ω = p.ω)
physg = rebundle(phys0, with_water(phys0.water; grass_demand_gate = true, βgpd_gate = 1.0e8))

mkpool_t(ind, r) = TreePools{Float64}(parse(Float64, ind["leaf_c"][r]), parse(Float64, ind["sapwood_c"][r]), parse(Float64, ind["heartwood_c"][r]), parse(Float64, ind["root_c"][r]), parse(Float64, ind["height"][r]), parse(Float64, ind["crownarea"][r]), parse(Float64, ind["nind"][r]), parse(Float64, ind["sla"][r]), parse(Float64, ind["wooddens"][r]), false)
mktmpl_t(ind, r) = Individual{Float64}(parse(Float64, ind["fpar_leafon"][r]), 0.0, parse(Float64, ind["alphaa"][r]), parse(Float64, ind["albedo_leaf"][r]), parse(Float64, ind["emax"][r]), parse(Float64, ind["sapwood_c"][r]), parse(Float64, ind["root_c"][r]), 0.0, 0.02, 0.04, 0.1, 0.4, parse(Float64, ind["nind"][r]), PhotoParams{Float64}(; path = :c3, issla = true, sla = parse(Float64, ind["sla"][r])), TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false)
mktmpl_g() = Individual{Float64}(0.03, 1.0, 0.5, 0.23, 10.0, 0.0, 0.0, 0.0, 0.01, 0.15, 0.1, 0.4, 1.0, PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.042242), TempStressParams{Float64}(; temp_photos_low = 10.0, temp_photos_high = 30.0), true)

# run one year: return (F_ann grass NPP cell-mean, cell-mean fed grass leaf, GS-mean wscal cell-mean)
function run_year(y)
    ind = readcsv(joinpath(STRUCTDIR, "hainich_individuals_$(y).csv"))
    typ(r) = parse(Int, ind["type"][r]); patchof(r) = parse(Int, ind["patch"][r])
    idx = findall(==(y), fyear)
    forc = [
        DailyForcing{Float64}(
                swdown = fcol(fdec, "swdown")[i], lwnet = fcol(fdec, "lwnet")[i], temp = fcol(fdec, "temp")[i],
                precip = fcol(fdec, "precip")[i], daylength = fcol(fdec, "daylength")[i], co2 = fcol(fdec, "co2")[i],
            ) for i in idx
    ]
    gs = [d for d in eachindex(idx) if 91 <= fdoy[idx[d]] <= 273]
    allpatches = sort(unique(patchof.(eachindex(ind["type"]))))
    cellnpp = zeros(Float64, length(forc)); fedleaf = 0.0; wsc_acc = 0.0; wsc_n = 0
    for pn in allpatches
        rows = [r for r in eachindex(ind["type"]) if patchof(r) == pn]
        trows = [r for r in rows if typ(r) <= 6 && parse(Float64, ind["height"][r]) > 0]
        grows = [r for r in rows if typ(r) >= 7]
        (isempty(trows) || isempty(grows)) && continue
        cgl = sum(parse(Float64, ind["agb_perm2"][r]) for r in grows)
        cgv = sum(parse(Float64, ind["vegc_perm2"][r]) for r in grows)
        L = max(cgl, 1.0e-6); root = max(cgv - cgl, 1.0e-6)
        trees = vcat([mkpool_t(ind, r) for r in trows], [grass_treepools(L, L + root, 0.042242)])
        tmpls = vcat([mktmpl_t(ind, r) for r in trows], [mktmpl_g()])
        gidx = length(trees); n = length(trees)
        fpars = _patch_fpars(trees, allom)
        inds = Individual{Float64}[individual_from_pools(tmpls[i], trees[i], allom, fpars[i]) for i in 1:n]
        st0 = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
        pids = vcat(fill(3, length(trows)), [8])
        (_, days) = rollout_daily_canopy(physg, st0, inds, soil, forc; pft_ids = pids, grass_lf_mode = :linear)
        for d in eachindex(forc)
            cellnpp[d] += days[d].npp_ind[gidx] / NPATCH
        end
        fedleaf += L / NPATCH
        for d in gs
            wsc_acc += days[d].wscal; wsc_n += 1
        end
    end
    return (sum(cellnpp), fedleaf, wsc_acc / max(wsc_n, 1))
end

println("year   C_ann   F_ann    F/C   fed_leaf  F/leaf   C/leaf  F_GSwscal")
rows = NamedTuple[]
for y in years
    (fann, fed, wsc) = run_year(y)
    cann = C_ann(y)
    push!(rows, (y = y, cann = cann, fann = fann, fc = fann / cann, fed = fed, fpl = fann / fed, cpl = cann / fed, wsc = wsc))
    println(
        rpad(y, 6), lpad(round(cann, digits = 1), 7), lpad(round(fann, digits = 1), 8), lpad(round(fann / cann, digits = 2), 7),
        lpad(round(fed, digits = 2), 10), lpad(round(fann / fed, digits = 3), 8), lpad(round(cann / fed, digits = 3), 8), lpad(round(wsc, digits = 3), 10)
    )
end

cor(a, b) = begin
    ma = sum(a) / length(a); mb = sum(b) / length(b)
    num = sum((a .- ma) .* (b .- mb)); den = sqrt(sum((a .- ma) .^ 2) * sum((b .- mb) .^ 2))
    den > 0 ? num / den : 0.0
end
fc = [r.fc for r in rows]; fed = [r.fed for r in rows]; wsc = [r.wsc for r in rows]; fpl = [r.fpl for r in rows]; cpl = [r.cpl for r in rows]
y2018 = rows[findfirst(r -> r.y == 2018, rows)]
wet = [r for r in rows if r.y in (2010, 2017, 2013)]      # high-precip normal years
wetwsc = sum(r.wsc for r in wet) / length(wet); wetfpl = sum(r.fpl for r in wet) / length(wet)
println("\n=== attribution ===")
println("corr(F/C, fed_leaf)                 = ", round(cor(fc, fed), digits = 3), "  (→ structure/leaf if high)")
println("corr(F/C, -F_GSwscal)               = ", round(cor(fc, -wsc), digits = 3), "  (→ water-coupling if high: dry yr, high F/C)")
println(
    "2018 F_GSwscal = ", round(y2018.wsc, digits = 3), "  vs wet-year mean = ", round(wetwsc, digits = 3),
    "  (drought captured in F's water state if 2018 << wet)"
)
println(
    "2018 F/leaf    = ", round(y2018.fpl, digits = 3), "  vs wet-year mean = ", round(wetfpl, digits = 3),
    "  (per-leaf flux; if 2018 ≈ wet ⇒ F does NOT suppress per-leaf GPP in drought)"
)
println("2018 C/leaf    = ", round(y2018.cpl, digits = 3), "  (the C DOES suppress per-leaf grass NPP in the drought)")
println("\nCLASSIFICATION:")
if y2018.wsc < 0.9 * wetwsc && y2018.fpl > 1.15 * y2018.cpl
    println("  → WATER-limitation-of-GPP sensitivity gap: F's wscal drops (drought captured) but per-leaf grass NPP stays high vs the C.")
elseif y2018.wsc >= 0.9 * wetwsc
    println("  → SOIL-WATER/SUPPLY gap: F's growing-season wscal barely drops in 2018 — the drought is not reaching the grass water balance.")
else
    println("  → INCONCLUSIVE / mixed — inspect the table (per-leaf flux vs the C, and the wscal drop).")
end
println("DONE.")
