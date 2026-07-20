# =============================================================================
# grass_phen_test.jl — test H2 for the residual broad grass overshoot: the coupled grass rollout
# applies the patch-wide BEECH GSI phenology to the understory grass, not the grass's OWN light-limited
# per-PFT GSI. The C (FIT `new_phenology:true`) runs per-PFT GSI: the grass light limiter is driven by
# the tree-attenuated forest-floor light (phenology_gsi.c:30-35), so a shaded understory grass is leaf-on
# far LESS ⇒ much less annual GPP. rollout_canopy_years (fdiff.jl:2153) calls rollout_daily_canopy with NO
# pft_ids ⇒ beech GSI for the grass. per_pft_phenology (§19) exists but is NOT wired into the grass rollout.
#
# grass_carbonbalance_probe.jl (SLURM 1534621) showed: at the C's OWN 2008 leaf + MATCHED fpar, F_diff
# grass NPP is 4.26× the C (median), grass GPP/apar == the validated trees', λ pinned 0.85; the overshoot
# GROWS with shade (bright patch 13 ff0.50 → F/C 0.99; dim patches → 4-5×). H2 predicts per-PFT grass
# phenology (light-limited season) collapses the overshoot, most in the shaded patches, matching the C.
#
# TEST: matched-structure per-patch (grass at the C's OWN 2008 leaf, trees fixed, 1 year 2009), compare
#   (a) BEECH phen (current rollout, phens=nothing, pft_ids=nothing)
#   (b) PER-PFT phen (pft_ids = [3 trees…, 8 grass]) — the grass's own light-limited GSI
# against the C's npp_perm2. If (b) median NPP F/C → ~1 and corr rises, H2 is the mechanism.
#
#   run (SLURM): JULIA_DEPOT_PATH=$HOME/.julia julia --project=. scripts/grass_phen_probe.jl
# =============================================================================
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.Allometry
const F = FDiff
import LPJmLFITEmulator.FDiff: grass_treepools, rollout_daily_canopy, tebs_params, hainich_soilcolumn,
    individual_from_pools, _patch_fpars, PhotoParams, TempStressParams, per_pft_phenology

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
_median(x) = (s = sort(x); n = length(s); isodd(n) ? s[(n + 1) ÷ 2] : (s[n ÷ 2] + s[n ÷ 2 + 1]) / 2)
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
mktmpl_g() = Individual{Float64}(0.03, 1.0, 0.5, 0.15, 10.0, 0.0, 0.0, 0.0, 0.01, 0.15, 0.1, 0.4, 1.0, PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.042242), TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), true)
allom = Allometry.TreeAllometry{Float64}(); phys = tebs_params()

# TREE pft id = 3 (temperate broadleaved summergreen, beech); GRASS pft id = 8 (temperate C3 grass).
function matched(pr; per_pft::Bool)
    L = max(pr.cgl, 1.0e-6); root = max(pr.cgv - pr.cgl, 1.0e-6)
    trees = vcat([mkpool_t(r) for r in pr.trows], [grass_treepools(L, L + root, 0.042242)])
    tmpls = vcat([mktmpl_t(r) for r in pr.trows], [mktmpl_g()])
    gidx = length(trees); n = length(trees)
    fpars = _patch_fpars(trees, allom)
    inds = Individual{Float64}[individual_from_pools(tmpls[i], trees[i], allom, fpars[i]) for i in 1:n]
    st0 = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
    pids = per_pft ? vcat(fill(3, length(pr.trows)), [8]) : nothing
    (_, days) = rollout_daily_canopy(phys, st0, inds, soil, forc; pft_ids = pids)
    npp = sum(d.npp_ind[gidx] for d in days)
    # mean grass leaf-display factor over the year (per-PFT grass phen) for reporting
    return (npp = npp, fpar = fpars[gidx])
end

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

println("================ GRASS PER-PFT PHENOLOGY TEST (H2) ================")
println("matched structure (grass at C's OWN 2008 leaf, trees fixed, 1 yr); beech-phen vs per-PFT grass phen vs C\n")
println(rpad("patch", 6), rpad("ff", 7), rpad("C_leaf", 9), rpad("C_NPP", 9), rpad("beech_NPP", 11), rpad("perpft_NPP", 12), rpad("beech F/C", 11), "perpft F/C")
nb = Float64[]; np = Float64[]; nc = Float64[]
for pr in patchref
    mb = matched(pr; per_pft = false); mp = matched(pr; per_pft = true)
    push!(nb, mb.npp); push!(np, mp.npp); push!(nc, pr.cnpp)
    println(
        rpad(pr.pn, 6), rpad(round(pr.ff, digits = 3), 7), rpad(round(pr.cgl, digits = 3), 9),
        rpad(round(pr.cnpp, digits = 3), 9), rpad(round(mb.npp, digits = 3), 11), rpad(round(mp.npp, digits = 3), 12),
        rpad(round(mb.npp / max(pr.cnpp, 1.0e-6), digits = 2), 11), round(mp.npp / max(pr.cnpp, 1.0e-6), digits = 2)
    )
end
println("\nSUMMARY:")
println("  BEECH phen  : median NPP F/C = ", round(_median(nb ./ max.(nc, 1.0e-6)), digits = 2), "   corr(Fd,C) = ", round(_corr(nb, nc), digits = 3))
println("  PER-PFT phen: median NPP F/C = ", round(_median(np ./ max.(nc, 1.0e-6)), digits = 2), "   corr(Fd,C) = ", round(_corr(np, nc), digits = 3))
println(
    "\nVERDICT: ", _median(np ./ max.(nc, 1.0e-6)) < 0.5 * _median(nb ./ max.(nc, 1.0e-6)) ?
        "PER-PFT PHENOLOGY collapses the overshoot ⇒ H2 CONFIRMED (the grass rollout must use per-PFT GSI)" :
        "per-PFT phenology does NOT collapse the overshoot ⇒ H2 rejected; conductance (H1) remains"
)

# ── SLURM ──
#   #!/usr/bin/env bash
#   #SBATCH --account=waldspektrum --partition=standard --qos=short --nodes=1 --ntasks=1
#   #SBATCH --cpus-per-task=4 --time=00:30:00 --output=logs/grass_phen.%j.out
#   cd /p/projects/open/Jamir/esm_land_emulator; export JULIA_DEPOT_PATH=$HOME/.julia
#   /p/system/packages_rhel9/tools/julia/1.10.0/bin/julia --project=. scripts/grass_phen_probe.jl
