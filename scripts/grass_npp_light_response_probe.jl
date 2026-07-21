# =============================================================================
# grass_npp_light_response_probe.jl — §26 follow-up #2: LOCALIZE the above-threshold grass-NPP
# LEVEL gap (aggregate 0.82× the C at matched structure, worst at intermediate/lower light).
#
# WHAT THE PRIOR FOLLOW-UP LEFT (docs §26 "Next"): the residual was scoped as a grass GPP-vs-light
# response gap needing "the C's daily GRASS GPP" — a targeted C re-run. This session first re-verified
# that scoping and found:
#   (1) LPJmL-FIT has NO per-PFT/per-individual DAILY GPP output (only annual `pft_npp` /`ind`, and
#       cell-total `d_gpp`/`d_npp` — `par/outputvars.js`). So "extract per-PFT daily GPP from the
#       single-cell output" is impossible; a "re-run" would require a C-SOURCE change + RECOMPILE.
#   (2) A full C-source audit shows the grass photosynthesis KERNEL is byte-faithful (co-limitation
#       exact `photosynthesis.c:150`; `vm`/`rd`/`adt` match), `apar` (layered forest-floor light) is
#       validated (§20), and the grass respiration params are LITERALLY beech's (grass id 8: respcoeff
#       1.2, cn_ratio.root CTON_ROOT, ratio.root 1.16 == beech id 3 in `par/pft_lpjmlfit.js`), so CUE
#       is faithful. temp/albedo were already ruled out (§26 follow-up #1).
#
# So the level gap is NOT a photosynthesis/respiration PARAMETER. The one remaining shade-dependent
# lever is the grass PHENOLOGY forest-floor light: the coupled rollout uses `grass_lf_mode = :linear`
# (`grass_lf = 1 − Σ_trees fpar·phen`), which is BRIGHTER than the FAITHFUL Lambert-Beer transmission
# `:exp` (`exp(−k·Σ plai·phen)`, `getfpar.c`) at shade. A too-bright understory keeps the grass leaf-on
# too many low-light days ⇒ it pays phen-scaled root MAINTENANCE respiration on days that make little
# GPP ⇒ NPP undershoots, and the effect GROWS with shade — exactly the observed monotone-with-shade
# F/C decline. §26 Finding 6 rejected `:exp` because `:exp`+gate drove DEEP-shade NPP negative, but it
# never checked the INTERMEDIATE/bright ABOVE-threshold patches — this probe does.
#
# Matched structure (grass at the C's OWN 2008 leaf, trees fixed, 1 yr 2009), FAITHFUL grass photo
# params (temp_photos 10/30, albedo_leaf 0.23), demand-gate ON (βgpd_gate 1e8): per-patch grass NPP
# F/C, SORTED by forest-floor light `ff`, for `:linear` vs `:exp`. Metric: does `:exp` raise the
# above-threshold (intermediate/bright) patches toward 1.0? Also reports the per-patch leaf-on-day
# fraction under each mode (the phenology-season lever).
#
#   run (SLURM, off the login node): JULIA_DEPOT_PATH=$HOME/.julia \
#     /p/system/packages_rhel9/tools/julia/1.10.0/bin/julia --project=. scripts/grass_npp_light_response_probe.jl
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
# FAITHFUL grass id 8 photo params (temp_photos 10/30, albedo_leaf 0.23; alphaa 0.5, sla 0.042242)
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
sort!(patchref, by = pr -> pr.ff)   # dimmest → brightest

# run the matched-structure grass NPP for one patch + forest-floor mode; return (annual NPP, leaf-on frac)
function matched(pr; mode::Symbol)
    L = max(pr.cgl, 1.0e-6); root = max(pr.cgv - pr.cgl, 1.0e-6)
    trees = vcat([mkpool_t(r) for r in pr.trows], [grass_treepools(L, L + root, 0.042242)])
    tmpls = vcat([mktmpl_t(r) for r in pr.trows], [mktmpl_g()])
    gidx = length(trees); n = length(trees)
    fpars = _patch_fpars(trees, allom)
    inds = Individual{Float64}[individual_from_pools(tmpls[i], trees[i], allom, fpars[i]) for i in 1:n]
    st0 = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
    pids = vcat(fill(3, length(pr.trows)), [8])
    (_, days) = rollout_daily_canopy(physg, st0, inds, soil, forc; pft_ids = pids, grass_lf_mode = mode)
    npp = sum(d.npp_ind[gidx] for d in days)
    # active-day fraction: grass makes appreciable NPP (proxy for leaf-on & above-gate)
    act = count(d -> d.npp_ind[gidx] > 1.0e-4, days) / length(days)
    return (npp = npp, act = act)
end

println("========= §26 FOLLOW-UP #2 — grass-NPP light response: :linear vs FAITHFUL :exp forest-floor light =========")
println("matched structure (grass at C's 2008 leaf, trees fixed, 1 yr 2009); FAITHFUL grass photo params; demand-gate ON.")
println("per-patch grass NPP F/C, SORTED by forest-floor light ff (dim→bright). act = fraction of days grass NPP>1e-4.\n")
println(rpad("patch", 7), rpad("ff", 8), rpad("C npp", 9), rpad("F/C :lin", 10), rpad("act:lin", 9), rpad("F/C :exp", 10), rpad("act:exp", 9))
lin = Float64[]; exp_ = Float64[]; nc = Float64[]
for pr in patchref
    ml = matched(pr; mode = :linear); me = matched(pr; mode = :exp)
    push!(lin, ml.npp); push!(exp_, me.npp); push!(nc, pr.cnpp)
    fcl = ml.npp / max(pr.cnpp, 1.0e-6); fce = me.npp / max(pr.cnpp, 1.0e-6)
    println(
        rpad(pr.pn, 7), rpad(round(pr.ff, digits = 3), 8), rpad(round(pr.cnpp, digits = 2), 9),
        rpad(round(fcl, digits = 2), 10), rpad(round(ml.act, digits = 2), 9),
        rpad(round(fce, digits = 2), 10), rpad(round(me.act, digits = 2), 9),
    )
end
println()
println("SUMMARY (aggregate Σ_F/Σ_C · median F/C · corr):")
println("  :linear  aggF/C=", round(sum(lin) / sum(nc), digits = 3), "  medF/C=", round(_median(lin ./ max.(nc, 1.0e-6)), digits = 3), "  corr=", round(_corr(lin, nc), digits = 3))
println("  :exp     aggF/C=", round(sum(exp_) / sum(nc), digits = 3), "  medF/C=", round(_median(exp_ ./ max.(nc, 1.0e-6)), digits = 3), "  corr=", round(_corr(exp_, nc), digits = 3))
# does :exp raise the above-threshold (brightest half) patches toward 1.0?
nhalf = length(patchref) ÷ 2
bright = (length(patchref) - nhalf + 1):length(patchref)
println(
    "  brightest-half (above-threshold) aggregate F/C: :linear=", round(sum(lin[bright]) / sum(nc[bright]), digits = 3),
    "  :exp=", round(sum(exp_[bright]) / sum(nc[bright]), digits = 3)
)
println("  (# patches with :exp NPP < 0 [deep-shade negatives, §26 F6]: ", count(<(0), exp_), ")")
println("\nDONE.")

# ── SLURM ──
#   #!/usr/bin/env bash
#   #SBATCH --account=waldspektrum --partition=standard --qos=short --nodes=1 --ntasks=1
#   #SBATCH --cpus-per-task=4 --time=00:30:00 --output=logs/grass_light_response.%j.out
#   cd /p/projects/open/Jamir/esm_land_emulator; export JULIA_DEPOT_PATH=$HOME/.julia
#   /p/system/packages_rhel9/tools/julia/1.10.0/bin/julia --project=. scripts/grass_npp_light_response_probe.jl
