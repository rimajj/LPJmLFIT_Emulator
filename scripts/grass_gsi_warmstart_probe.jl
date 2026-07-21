# =============================================================================
# grass_gsi_warmstart_probe.jl — §26 follow-up #3: is the above-threshold grass-NPP LEVEL gap the
# grass GSI COLD-START?
#
# Follow-up #2 (`grass_npp_light_response_probe.jl`) localized the residual: the above-threshold grass
# NPP F/C (aggregate 0.82×, declining with shade) TRACKS the grass ACTIVE-DAY fraction (grass makes
# NPP>1e-4 on only ~0.49–0.66 of days at the productive patches, less at shade). It is NOT a
# GPP-per-active-leaf gap and NOT the forest-floor light shape (`:exp` made it WORSE). So the grass is
# leaf-on / above-threshold too FEW days.
#
# HYPOTHESIS: the matched-structure comparison runs ONE year (2009) from a COLD-START GSI
# (`rollout_daily_canopy` cold-starts `pft_states = [PhenState() …]`; the coupled multi-year rollout
# cold-starts the GSI each year — a documented v1 simplification), whereas the C WARM-starts the grass
# GSI continuously across years. A cold GSI ramps up slowly (`f += (target−f)·tau`), shortening the
# grass's effective leaf-on season ⇒ fewer active days ⇒ NPP undershoot, worse at shade (the shade-
# suppressed light limiter takes even longer to ramp from cold).
#
# TEST (zero core change): concatenate the 2009 forcing K times into ONE `rollout_daily_canopy` call —
# it cold-starts the GSI at day 1, then runs CONTINUOUSLY, so the GSI (and soil water + lag-1 grass
# light) WARM UP over the K years. Structure is fixed (the daily fold does not grow it). Compare the
# grass NPP F/C and active-day fraction in year 1 (COLD) vs year K (WARM). If year K rises toward the
# C, the cold-start is the lever — and the fix (carry the GSI state across years in the coupled
# rollout) needs NO C re-run/recompile.
#
#   run (SLURM): JULIA_DEPOT_PATH=$HOME/.julia \
#     /p/system/packages_rhel9/tools/julia/1.10.0/bin/julia --project=. scripts/grass_gsi_warmstart_probe.jl
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

ind = readcsv(joinpath(REFDIR, "hainich_individuals_2008.csv"))
fdec = readcsv(joinpath(REFDIR, "hainich_decadal_forcing.csv"))
(sd, whcs, rdist) = readtable(joinpath(REFDIR, "hainich_soilcolumn.txt"))
soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)
fyear = Int.(round.(fcol(fdec, "year"))); yr1 = minimum(fyear)
forc1 = [
    DailyForcing{Float64}(
            swdown = fcol(fdec, "swdown")[i], lwnet = fcol(fdec, "lwnet")[i], temp = fcol(fdec, "temp")[i],
            precip = fcol(fdec, "precip")[i], daylength = fcol(fdec, "daylength")[i], co2 = fcol(fdec, "co2")[i],
        ) for i in findall(==(yr1), fyear)
]
const NDY = length(forc1)
const K = 5
forcK = reduce(vcat, [forc1 for _ in 1:K])

vv(r, k) = parse(Float64, ind[k][r]); typ(r) = parse(Int, ind["type"][r]); patchof(r) = parse(Int, ind["patch"][r])
allpatches = sort(unique(patchof.(eachindex(ind["type"]))))
mkpool_t(r) = TreePools{Float64}(vv(r, "leaf_c"), vv(r, "sapwood_c"), vv(r, "heartwood_c"), vv(r, "root_c"), vv(r, "height"), vv(r, "crownarea"), vv(r, "nind"), vv(r, "sla"), vv(r, "wooddens"), false)
mktmpl_t(r) = Individual{Float64}(vv(r, "fpar_leafon"), 0.0, vv(r, "alphaa"), vv(r, "albedo_leaf"), vv(r, "emax"), vv(r, "sapwood_c"), vv(r, "root_c"), 0.0, 0.02, 0.04, 0.1, 0.4, vv(r, "nind"), PhotoParams{Float64}(; path = :c3, issla = true, sla = vv(r, "sla")), TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false)
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
    cnpp = sum(vv(r, "npp_perm2") for r in grows)
    plai = sum(vv(r, "leaf_c") * vv(r, "sla") * vv(r, "nind") for r in trows)
    push!(patchref, (pn = pn, trows = trows, cgl = cgl, cgv = cgv, cnpp = cnpp, ff = exp(-0.5 * plai)))
end
sort!(patchref, by = pr -> pr.ff)

# per-year grass NPP + active-day fraction over the K-year continuous (warming) rollout
function warmup(pr)
    L = max(pr.cgl, 1.0e-6); root = max(pr.cgv - pr.cgl, 1.0e-6)
    trees = vcat([mkpool_t(r) for r in pr.trows], [grass_treepools(L, L + root, 0.042242)])
    tmpls = vcat([mktmpl_t(r) for r in pr.trows], [mktmpl_g()])
    gidx = length(trees); n = length(trees)
    fpars = _patch_fpars(trees, allom)
    inds = Individual{Float64}[individual_from_pools(tmpls[i], trees[i], allom, fpars[i]) for i in 1:n]
    st0 = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
    pids = vcat(fill(3, length(pr.trows)), [8])
    (_, days) = rollout_daily_canopy(physg, st0, inds, soil, forcK; pft_ids = pids, grass_lf_mode = :linear)
    npp = zeros(K); act = zeros(K)
    for y in 1:K
        rng = ((y - 1) * NDY + 1):(y * NDY)
        npp[y] = sum(days[d].npp_ind[gidx] for d in rng)
        act[y] = count(d -> days[d].npp_ind[gidx] > 1.0e-4, rng) / NDY
    end
    return (npp = npp, act = act)
end

println("========= §26 FOLLOW-UP #3 — grass GSI COLD-START vs WARM-START (", K, "-yr continuous spin-up, matched structure) =========")
println("per-patch grass NPP F/C: year 1 (COLD GSI) vs year ", K, " (WARM); + active-day fraction. sorted by ff.\n")
println(rpad("patch", 7), rpad("ff", 7), rpad("Cnpp", 8), rpad("F/C y1", 9), rpad("F/C y", 9), rpad("act y1", 8), rpad("act y", 8))
y1 = Float64[]; yK = Float64[]; nc = Float64[]
for pr in patchref
    w = warmup(pr)
    push!(y1, w.npp[1]); push!(yK, w.npp[K]); push!(nc, pr.cnpp)
    println(
        rpad(pr.pn, 7), rpad(round(pr.ff, digits = 3), 7), rpad(round(pr.cnpp, digits = 1), 8),
        rpad(round(w.npp[1] / max(pr.cnpp, 1.0e-6), digits = 2), 9),
        rpad(round(w.npp[K] / max(pr.cnpp, 1.0e-6), digits = 2), 9),
        rpad(round(w.act[1], digits = 2), 8), rpad(round(w.act[K], digits = 2), 8),
    )
end
nhalf = length(patchref) ÷ 2
bright = (length(patchref) - nhalf + 1):length(patchref)
println("\nSUMMARY:")
println(
    "  year 1 (COLD): aggF/C=", round(sum(y1) / sum(nc), digits = 3), "  medF/C=", round(_median(y1 ./ max.(nc, 1.0e-6)), digits = 3),
    "  brightest-half aggF/C=", round(sum(y1[bright]) / sum(nc[bright]), digits = 3)
)
println(
    "  year ", K, " (WARM): aggF/C=", round(sum(yK) / sum(nc), digits = 3), "  medF/C=", round(_median(yK ./ max.(nc, 1.0e-6)), digits = 3),
    "  brightest-half aggF/C=", round(sum(yK[bright]) / sum(nc[bright]), digits = 3)
)
println("\n=> if year-", K, " (warm) aggF/C > year-1 (cold), the GSI cold-start shortens the grass season (the lever).")
println("DONE.")

# ── SLURM ──
#   #!/usr/bin/env bash
#   #SBATCH --account=waldspektrum --partition=standard --qos=short --nodes=1 --ntasks=1
#   #SBATCH --cpus-per-task=4 --time=00:30:00 --output=logs/grass_gsi_warmstart.%j.out
#   cd /p/projects/open/Jamir/esm_land_emulator; export JULIA_DEPOT_PATH=$HOME/.julia
#   /p/system/packages_rhel9/tools/julia/1.10.0/bin/julia --project=. scripts/grass_gsi_warmstart_probe.jl
