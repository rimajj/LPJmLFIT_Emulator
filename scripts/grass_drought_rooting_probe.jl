# =============================================================================
# grass_drought_rooting_probe.jl — CONFIRM the mechanism behind the §26.2 2018 grass-NPP amplitude
# overshoot (matched-structure F/C 1.87). The amplitude + soil-memory probes established the residual is a
# GENUINE grass water-sensitivity gap on the SUPPLY side (F_diff's growing-season stand `wscal` barely drops
# in 2018 — 0.939 vs 0.976 normal — and carrying F_diff's own multi-year soil balance reproduces it exactly,
# so it is not the fresh-soil reset). Code reading (`daily_step_canopy`, src/fdiff.jl:1467-1473, 1587) shows
# `wscal` is a SINGLE STAND-LEVEL scalar built from ONE shared `soil.rootdist` (the deep D95=115cm beech β
# profile) and the FPC-weighted stand-mean conductance — grass has NO shallow-rooted, independently
# water-stressed balance; it borrows the tree-buffered stand water. This is the water-side twin of the
# documented §20/§22 shared-`gp_stand` limitation.
#
# DECISIVE TEST. Re-run F_diff's daily grass at each year's OWN C structure (as the §26.2 addendum / the
# amplitude probe) under three ROOTING profiles for the stand water balance:
#   • DEEP    — the committed stand rootdist (D95=115cm; 40.6% top-20cm, ~93% top-1m)
#   • MID     — top-50cm only (layers 0-1, renormalized): a moderately shallow profile
#   • SHALLOW — top-20cm only (layer 0): grass-like shallow rooting
# This LOCALIZES the residual to the `wr`→supply channel: if a shallower rooting makes 2018's growing-season
# `wscal` DROP HARD and pulls 2018 F/C toward (or below) 1, the residual lives on the shared root-zone-moisture
# / supply channel — a more drought-responsive `wr`/supply closes it. READ AS A LEVER, NOT the C mechanism: it
# shallows the WHOLE stand (trees too), and an adversarial C-source cross-check (docs §26.4) shows the C's grass
# is FULL-depth-rooted (same beta_root=0.8 as trees, new_grass.c:40 / pft.js:1110) — so this is NOT "what the C
# does". The true gap is the per-PFT `wscal` + the sequential competitive per-layer supply depletion (`aet_cor`,
# water_stressed.c:153-177,264-275) that F_diff collapses into one FPC-weighted stand aggregate; the proximate
# reasons the aggregate `wscal` barely moves are demand-saturation of `min(1,supply/demand)` + top-layer
# over-recharge. If a shallow rooting barely changed 2018, the effect would not even be on this channel.
#
#   run (SLURM, off the login node):
#     JULIA_DEPOT_PATH=$HOME/.julia \
#       /p/system/packages_rhel9/tools/julia/1.10.0/bin/julia --project=. scripts/grass_drought_rooting_probe.jl
# =============================================================================
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.Allometry
import LPJmLFITEmulator.FDiff: grass_treepools, rollout_daily_canopy, tebs_params, hainich_soilcolumn,
    individual_from_pools, _patch_fpars, PhotoParams, TempStressParams, WaterParams, FDiffParams, SoilColumn

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
soil_deep = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)
gdaily = readcsv(joinpath(REFDIR, "hainich_grass_daily_2009_2019.csv"))
fyear = Int.(round.(fcol(fdec, "year"))); fdoy = Int.(round.(fcol(fdec, "doy")))
years = sort(unique(fyear))
gcy = Int.(round.(fcol(gdaily, "year"))); gcnpp = fcol(gdaily, "c_grass_npp")
C_ann(y) = sum(gcnpp[gcy .== y])

# build shallow rooting variants by zeroing deeper layers of the committed rootdist and renormalizing
function reroot(soil::SoilColumn, keep::Int)
    rd = copy(soil.rootdist)
    for l in (keep + 1):length(rd)
        rd[l] = 0.0
    end
    s = sum(rd); rd ./= s
    return SoilColumn(soil.whcs, rd, soil.frac_evap, soil.soil_infil)
end
soil_mid = reroot(soil_deep, 2)      # top-50cm (layers 1-2, 0-based 0-1)
soil_shallow = reroot(soil_deep, 1)  # top-20cm (layer 0)

allom = Allometry.TreeAllometry{Float64}(); phys0 = tebs_params()
with_water(w; kw...) = (d = Dict(kw); WaterParams{Float64}(Any[haskey(d, f) ? d[f] : getfield(w, f) for f in fieldnames(WaterParams)]...))
rebundle(p, w) = FDiffParams{Float64}(; photo = p.photo, tstress = p.tstress, water = w, resp = p.resp, allom = p.allom, nlambda = p.nlambda, ω = p.ω)
physg = rebundle(phys0, with_water(phys0.water; grass_demand_gate = true, βgpd_gate = 1.0e8))

mkpool_t(ind, r) = TreePools{Float64}(parse(Float64, ind["leaf_c"][r]), parse(Float64, ind["sapwood_c"][r]), parse(Float64, ind["heartwood_c"][r]), parse(Float64, ind["root_c"][r]), parse(Float64, ind["height"][r]), parse(Float64, ind["crownarea"][r]), parse(Float64, ind["nind"][r]), parse(Float64, ind["sla"][r]), parse(Float64, ind["wooddens"][r]), false)
mktmpl_t(ind, r) = Individual{Float64}(parse(Float64, ind["fpar_leafon"][r]), 0.0, parse(Float64, ind["alphaa"][r]), parse(Float64, ind["albedo_leaf"][r]), parse(Float64, ind["emax"][r]), parse(Float64, ind["sapwood_c"][r]), parse(Float64, ind["root_c"][r]), 0.0, 0.02, 0.04, 0.1, 0.4, parse(Float64, ind["nind"][r]), PhotoParams{Float64}(; path = :c3, issla = true, sla = parse(Float64, ind["sla"][r])), TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false)
mktmpl_g() = Individual{Float64}(0.03, 1.0, 0.5, 0.23, 10.0, 0.0, 0.0, 0.0, 0.01, 0.15, 0.1, 0.4, 1.0, PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.042242), TempStressParams{Float64}(; temp_photos_low = 10.0, temp_photos_high = 30.0), true)

# run one year at a given soil column: return (F_ann grass NPP cell-mean, GS-mean wscal)
function run_year(y, soil)
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
    cellnpp = 0.0; wsc_acc = 0.0; wsc_n = 0
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
        st0 = FDiffStateML{Float64}([0.9 * wc for wc in soil.whcs], 0.0)
        pids = vcat(fill(3, length(trows)), [8])
        (_, days) = rollout_daily_canopy(physg, st0, inds, soil, forc; pft_ids = pids, grass_lf_mode = :linear)
        cellnpp += sum(days[d].npp_ind[gidx] for d in eachindex(forc)) / NPATCH
        for d in gs
            wsc_acc += days[d].wscal; wsc_n += 1
        end
    end
    return (cellnpp, wsc_acc / max(wsc_n, 1))
end

configs = [("DEEP (D95=115cm)", soil_deep), ("MID (top-50cm)", soil_mid), ("SHALLOW (top-20cm)", soil_shallow)]
wetyrs = (2010, 2013, 2017)
println("rooting profile          2018 F/C   2018 GSwscal   wet-yr GSwscal   Δwscal(2018-wet)   2018 F_ann")
summary = NamedTuple[]
for (name, soil) in configs
    fc2018 = 0.0; wsc2018 = 0.0; fann2018 = 0.0; wetw = 0.0
    for y in years
        (fann, wsc) = run_year(y, soil)
        if y == 2018
            fann2018 = fann; fc2018 = fann / C_ann(2018); wsc2018 = wsc
        end
        if y in wetyrs
            wetw += wsc / length(wetyrs)
        end
    end
    push!(summary, (name = name, fc = fc2018, w18 = wsc2018, wwet = wetw, dw = wsc2018 - wetw, fann = fann2018))
    println(
        rpad(name, 24), lpad(round(fc2018, digits = 2), 8), lpad(round(wsc2018, digits = 3), 14),
        lpad(round(wetw, digits = 3), 16), lpad(round(wsc2018 - wetw, digits = 3), 18), lpad(round(fann2018, digits = 1), 12)
    )
end

deep = summary[1]; shallow = summary[3]
println("\n=== rooting-channel verdict ===")
println("DEEP    2018 F/C = ", round(deep.fc, digits = 2), ",  Δwscal(2018-wet) = ", round(deep.dw, digits = 3))
println("SHALLOW 2018 F/C = ", round(shallow.fc, digits = 2), ",  Δwscal(2018-wet) = ", round(shallow.dw, digits = 3))
if shallow.dw < 2.0 * deep.dw - 0.02 && shallow.fc < deep.fc - 0.2
    println(
        "  → CHANNEL LOCALIZED: a shallower (top-weighted) stand rooting makes the 2018 drought register (wscal",
        " drops far harder) and pulls 2018 F/C down toward the C — so the residual lives on the shared",
        " `wr`/supply channel. NOTE (docs §26.4): this is a LEVER, not the C mechanism — the C's grass is",
        " full-depth-rooted (beta_root=0.8, same as trees). The true gap is the per-PFT `wscal` + the sequential",
        " competitive per-layer supply depletion (aet_cor) F_diff collapses into one FPC-weighted stand",
        " aggregate; proximate causes are demand-saturation of min(1,supply/demand) + top-layer over-recharge."
    )
elseif shallow.fc >= deep.fc - 0.05
    println(
        "  → NOT this channel: shallow rooting barely changes 2018 F/C. The under-response is elsewhere",
        " (per-PFT wscal aggregation, or demand-saturation). Inspect the table."
    )
else
    println(
        "  → PARTIAL: shallow rooting reduces but does not close the 2018 overshoot — the `wr`/supply channel",
        " is one contributor among others (per-PFT wscal aggregation, competitive depletion)."
    )
end
println("DONE.")
