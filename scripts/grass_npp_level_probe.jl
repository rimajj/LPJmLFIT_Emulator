# =============================================================================
# grass_npp_level_probe.jl — §26 follow-up: close the ABOVE-threshold grass-NPP LEVEL gap.
#
# §26 (the demand-gate) EXPOSED that F_diff's faithfully-gated grass NPP is aggregate 0.83× the C at
# matched structure (median 0.48×; corr ~0.973 — the ranking is right, only the LEVEL is low on the days
# the grass IS photosynthesizing). The grass probes so far built the grass `Individual` with the BEECH
# photosynthesis params (a documented v1 simplification, §15): `temp_photos` 20/30 (the tree optimum) and
# `albedo_leaf` 0.15 — but the ACTIVE `par/pft_lpjmlfit.js` temperate C3 grass (id 8) has its OWN:
#   temp_photos {low 10, high 30}   (a LOWER optimum ⇒ RAISES NPP at cool Hainich temps)
#   albedo_leaf 0.23                 (vs 0.15 ⇒ LESS absorbed PAR ⇒ LOWERS GPP)
# (alphaa 0.5, sla 0.042242, path C3 already faithful in the probes.) The two corrections push OPPOSITE
# ways — this probe measures whether the FAITHFUL grass photosynthesis params close the 0.83× level gap.
#
# matched-structure (grass at the C's OWN 2008 leaf, trees fixed, 1 yr 2009), DEMAND-GATE ON (:linear),
# per-patch grass NPP F/C vs the C, sweeping the grass photosynthesis params:
#   beech-shared (temp 20/30, alb 0.15)  ·  faithful-temp (10/30, 0.15)  ·  faithful-alb (20/30, 0.23)  ·
#   faithful-both (10/30, 0.23).  Metric: aggregate F/C (Σ_F/Σ_C = the cell carbon match), median, corr.
#
#   run (SLURM): JULIA_DEPOT_PATH=$HOME/.julia julia --project=. scripts/grass_npp_level_probe.jl
# =============================================================================
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.Allometry
const F = FDiff
import LPJmLFITEmulator.FDiff: grass_treepools, rollout_daily_canopy, tebs_params, hainich_soilcolumn,
    individual_from_pools, _patch_fpars, PhotoParams, TempStressParams, WaterParams, FDiffParams

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
_median(x) = (s = sort(x); isempty(s) ? 0.0 : (n = length(s); isodd(n) ? s[(n + 1) ÷ 2] : (s[n ÷ 2] + s[n ÷ 2 + 1]) / 2))
_corr(a, b) = (ma = _mean(a); mb = _mean(b); d = sqrt(sum((a .- ma) .^ 2) * sum((b .- mb) .^ 2)); d < 1.0e-12 ? 0.0 : sum((a .- ma) .* (b .- mb)) / d)

ind = readcsv(joinpath(REFDIR, "hainich_individuals_2008.csv"))
fdec = readcsv(joinpath(REFDIR, "hainich_decadal_forcing.csv"))
(sd, whcs, rdist) = readtable(joinpath(REFDIR, "hainich_soilcolumn.txt"))
soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)
fyear = Int.(round.(fcol(fdec, "year"))); yr1 = minimum(fyear)
forc = [
    DailyForcing{Float64}(
            swdown = fcol(fdec, "swdown")[i], lwnet = fcol(fdec, "lwnet")[i], temp = fcol(fdec, "temp")[i],
            precip = fcol(fdec, "precip")[i], daylength = fcol(fdec, "daylength")[i], co2 = fcol(fdec, "co2")[i],
        ) for i in findall(==(yr1), fyear)
]

vv(r, k) = parse(Float64, ind[k][r]); typ(r) = parse(Int, ind["type"][r]); patchof(r) = parse(Int, ind["patch"][r])
allpatches = sort(unique(patchof.(eachindex(ind["type"]))))
mkpool_t(r) = TreePools{Float64}(vv(r, "leaf_c"), vv(r, "sapwood_c"), vv(r, "heartwood_c"), vv(r, "root_c"), vv(r, "height"), vv(r, "crownarea"), vv(r, "nind"), vv(r, "sla"), vv(r, "wooddens"), false)
mktmpl_t(r) = Individual{Float64}(vv(r, "fpar_leafon"), 0.0, vv(r, "alphaa"), vv(r, "albedo_leaf"), vv(r, "emax"), vv(r, "sapwood_c"), vv(r, "root_c"), 0.0, 0.02, 0.04, 0.1, 0.4, vv(r, "nind"), PhotoParams{Float64}(; path = :c3, issla = true, sla = vv(r, "sla")), TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false)
# grass template parameterized by the photosynthesis-temperature optimum + leaf albedo
mktmpl_g(tphl, tphh, alb) = Individual{Float64}(0.03, 1.0, 0.5, alb, 10.0, 0.0, 0.0, 0.0, 0.01, 0.15, 0.1, 0.4, 1.0, PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.042242), TempStressParams{Float64}(; temp_photos_low = tphl, temp_photos_high = tphh), true)
allom = Allometry.TreeAllometry{Float64}(); phys0 = tebs_params()

with_water(w; kw...) = (d = Dict(kw); WaterParams{Float64}(Any[haskey(d, f) ? d[f] : getfield(w, f) for f in fieldnames(WaterParams)]...))
rebundle(p, w) = FDiffParams{Float64}(; photo = p.photo, tstress = p.tstress, water = w, resp = p.resp, allom = p.allom, nlambda = p.nlambda, ω = p.ω)
physgate(gate::Bool) = rebundle(phys0, with_water(phys0.water; grass_demand_gate = gate, βgpd_gate = 1.0e8))

patchref = []
for pn in allpatches
    rows = [r for r in eachindex(ind["type"]) if patchof(r) == pn]
    trows = [r for r in rows if typ(r) <= 6 && vv(r, "height") > 0]
    grows = [r for r in rows if typ(r) >= 7]
    (isempty(trows) || isempty(grows)) && continue
    cgl = sum(vv(r, "agb_perm2") for r in grows); cgv = sum(vv(r, "vegc_perm2") for r in grows)
    cnpp = sum(vv(r, "npp_perm2") for r in grows)
    plai = sum(vv(r, "leaf_c") * vv(r, "sla") * vv(r, "nind") for r in trows)
    push!(patchref, (pn = pn, trows = trows, cgl = cgl, cgv = cgv, cnpp = cnpp, ff = exp(-0.5 * plai)))
end

function matched_npp(pr; gate, tphl, tphh, alb)
    L = max(pr.cgl, 1.0e-6); root = max(pr.cgv - pr.cgl, 1.0e-6)
    trees = vcat([mkpool_t(r) for r in pr.trows], [grass_treepools(L, L + root, 0.042242)])
    tmpls = vcat([mktmpl_t(r) for r in pr.trows], [mktmpl_g(tphl, tphh, alb)])
    gidx = length(trees); n = length(trees)
    fpars = _patch_fpars(trees, allom)
    inds = Individual{Float64}[individual_from_pools(tmpls[i], trees[i], allom, fpars[i]) for i in 1:n]
    st0 = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
    pids = vcat(fill(3, length(pr.trows)), [8])
    (_, days) = rollout_daily_canopy(physgate(gate), st0, inds, soil, forc; pft_ids = pids, grass_lf_mode = :linear)
    return sum(d.npp_ind[gidx] for d in days)
end

cfgs = [
    (name = "beech-shared (t20/30 a0.15)", tphl = 20.0, tphh = 30.0, alb = 0.15),
    (name = "faithful-temp (t10/30 a0.15)", tphl = 10.0, tphh = 30.0, alb = 0.15),
    (name = "faithful-alb  (t20/30 a0.23)", tphl = 20.0, tphh = 30.0, alb = 0.23),
    (name = "faithful-both (t10/30 a0.23)", tphl = 10.0, tphh = 30.0, alb = 0.23),
]
nc = [pr.cnpp for pr in patchref]
println("========= §26 FOLLOW-UP — grass-NPP LEVEL gap: faithful grass photosynthesis params (demand-gate ON) =========")
println("matched structure (grass at C's OWN 2008 leaf, trees fixed, 1 yr); demand-gate ON; F/C vs the C's npp_perm2.\n")
for gate in (false, true)
    println("---- demand-gate = ", gate, " ----")
    println(rpad("grass params", 30), rpad("medF/C", 9), rpad("corr", 8), rpad("aggF/C", 9), "bright-patch F/C (13/24/20/6)")
    for c in cfgs
        nf = [matched_npp(pr; gate = gate, tphl = c.tphl, tphh = c.tphh, alb = c.alb) for pr in patchref]
        byp = Dict(pr.pn => nf[i] / max(pr.cnpp, 1.0e-6) for (i, pr) in enumerate(patchref))
        bright = join([string(round(get(byp, p, NaN), digits = 2)) for p in (13, 24, 20, 6)], "/")
        println(
            rpad(c.name, 30), rpad(round(_median(nf ./ max.(nc, 1.0e-6)), digits = 2), 9),
            rpad(round(_corr(nf, nc), digits = 3), 8), rpad(round(sum(nf) / sum(nc), digits = 3), 9), bright
        )
    end
end
println("\nDONE.")

# ── SLURM ──
#   #!/usr/bin/env bash
#   #SBATCH --account=waldspektrum --partition=standard --qos=short --nodes=1 --ntasks=1
#   #SBATCH --cpus-per-task=4 --time=00:30:00 --output=logs/grass_npp_level.%j.out
#   cd /p/projects/open/Jamir/esm_land_emulator; export JULIA_DEPOT_PATH=$HOME/.julia
#   /p/system/packages_rhel9/tools/julia/1.10.0/bin/julia --project=. scripts/grass_npp_level_probe.jl
