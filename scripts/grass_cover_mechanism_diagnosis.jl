# =============================================================================
# grass_cover_mechanism_diagnosis.jl — RE-EXAMINE the session-17 grass-overshoot
# "corrected next step" (grass cover/light competition via light.c → light_grass.c →
# fpc_grass.c) against the ACTUALLY-ACTIVE FIT code path.
#
# Session 17 (docs §22) set the next step as porting the LPJmL `light.c`/`light_grass.c`
# grass cover competition, on the premise that the C "physically kills excess grass
# leaf/root to litter" to cap understory grass. BUT the FIT config runs `"individual":true`
# (lpjmlfit.js:34), and in individual mode:
#   • annual_natural.c:117  →  `if(!config->individual) light(patch,...)`  — light()/light_grass()
#     are NOT called at all;
#   • the individual-mode cover reduction is establishmentpft_ind.c:168-176 → reduce_grass(),
#     which does ONLY `pft->fpc /= factor` (reduce_grass.c) — it does NOT kill leaf/root carbon,
#     and getfpar.c:190 computes the grass photosynthetic fapar from the grass's own LEAF CARBON
#     (`fpar_floor·(1−e^{−k·lai_g})`), NOT from `pft->fpc` — so the fpc reduction never feeds back
#     into grass NPP.
# ⇒ In the FIT config the C's grass is bounded PURELY by the light-limited carbon balance
#   (Beer–Lambert fapar saturation at the tree-set forest-floor ceiling), NOT by a hard cover cap.
#   The C's own per-patch 2008 grass leaf spans 0.01 → 215 gC/m², MONOTONIC in forest-floor light
#   (patch 3 ff=0.14→grass 0.01; patch 13 ff=0.50→grass 215) — the fingerprint of carbon-balance
#   bounding, not a cap.
#
# THE DECISIVE QUESTION this script answers empirically: does F_diff's self-driven grass already
# reproduce the C's per-patch grass-leaf spectrum (⇒ no fix needed; the §22 "×25 overshoot" was a
# setup artifact of a single median grass placed in one patch's tree environment), or does it
# genuinely overshoot at fixed light (⇒ a real carbon-balance gap to fix)?
#
# Two experiments per patch (25 Hainich patches, 2008 start structure, 2009–2019 decadal forcing):
#   Exp A — TREES FIXED at the C 2008 structure, grass self-driven 11 yr. Isolates the grass carbon
#           balance at the C's OWN forest-floor light. If Exp A grass ≈ C grass per patch, the grass
#           carbon balance is faithful.
#   Exp B — FULL self-driven (trees + grass grow), `rollout_canopy_years`. The coupled system.
#
#   run:  scripts/sbatch_train.sh is for --project=test; this needs only runtime deps, so:
#         JULIA_DEPOT_PATH=$HOME/.julia julia --project=. scripts/grass_cover_mechanism_diagnosis.jl
#         (submit off the login node via SLURM — see the trailing #SBATCH-wrapper note.)
# =============================================================================
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.Allometry
const F = FDiff
import LPJmLFITEmulator.FDiff: grass_treepools, rollout_daily_canopy, rollout_canopy_years,
    tebs_params, tebs_allocparams, hainich_soilcolumn, individual_from_pools, _patch_fpars,
    grow_individual, grow_grass_individual, grass_allocparams

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

# ── reference: 2008 start structure (agb_perm2/vegc_perm2 carry the C grass carbon) + decadal forcing
ind = readcsv(joinpath(REFDIR, "hainich_individuals_2008.csv"))
fdec = readcsv(joinpath(REFDIR, "hainich_decadal_forcing.csv"))
(sd, whcs, rdist) = readtable(joinpath(REFDIR, "hainich_soilcolumn.txt"))
soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)

fyear = Int.(round.(fcol(fdec, "year"))); syears = sort(unique(fyear))
yearly = [
    [
            DailyForcing{Float64}(
                swdown = fcol(fdec, "swdown")[i], lwnet = fcol(fdec, "lwnet")[i], temp = fcol(fdec, "temp")[i],
                precip = fcol(fdec, "precip")[i], daylength = fcol(fdec, "daylength")[i], co2 = fcol(fdec, "co2")[i],
            ) for i in findall(==(yr), fyear)
        ]
        for yr in syears
]
NY = length(syears)

vv(r, k) = parse(Float64, ind[k][r])
typ(r) = parse(Int, ind["type"][r])
patchof(r) = parse(Int, ind["patch"][r])
allpatches = sort(unique(patchof.(eachindex(ind["type"]))))

mkpool_t(r) = TreePools{Float64}(vv(r, "leaf_c"), vv(r, "sapwood_c"), vv(r, "heartwood_c"), vv(r, "root_c"), vv(r, "height"), vv(r, "crownarea"), vv(r, "nind"), vv(r, "sla"), vv(r, "wooddens"), false)
mktmpl_t(r) = Individual{Float64}(vv(r, "fpar_leafon"), 0.0, vv(r, "alphaa"), vv(r, "albedo_leaf"), vv(r, "emax"), vv(r, "sapwood_c"), vv(r, "root_c"), 0.0, 0.02, 0.04, 0.1, 0.4, vv(r, "nind"), FDiff.PhotoParams{Float64}(; path = :c3, issla = true, sla = vv(r, "sla")), FDiff.TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false)
mktmpl_g() = Individual{Float64}(0.03, 1.0, 0.5, 0.15, 10.0, 0.0, 0.0, 0.0, 0.01, 0.15, 0.1, 0.4, 1.0, FDiff.PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.042242), FDiff.TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), true)

allom = Allometry.TreeAllometry{Float64}(); alloc = tebs_allocparams(); phys = tebs_params(); galloc = grass_allocparams()

# grass leaf-on forest-floor light from the FIXED C tree structure (a diagnostic proxy: exp(-k·plai_tree))
ff_light(trees) = begin
    fp = _patch_fpars(trees, allom)
    # recover forest-floor transmission: for a lone grass added, fpar_grass = ff·(1−e^{−k·lai_g}); instead
    # compute directly from tree plai. reuse _patch_fpars by appending a tiny grass probe.
    plai = 0.0
    for t in trees
        (t.is_grass || t.height <= 0 || t.leaf_c <= 0) && continue
        plai += t.leaf_c * t.sla * t.nind
    end
    exp(-0.5 * plai)
end

# Exp A — trees FIXED, grass self-driven. Custom multi-year loop (grow only the grass individual).
function exp_A(trees0, tmpls, gidx)
    trees = collect(trees0)
    st = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
    n = length(trees)
    leaf_traj = Float64[]; npp_traj = Float64[]
    for forc in yearly
        fpars = _patch_fpars(trees, allom)
        inds = Individual{Float64}[individual_from_pools(tmpls[i], trees[i], allom, fpars[i]) for i in 1:n]
        (st, days) = rollout_daily_canopy(phys, st, inds, soil, forc)
        bm_g = 0.0; for d in days
            bm_g += d.npp_ind[gidx]
        end
        g = trees[gidx]
        trees[gidx] = grow_grass_individual(galloc, g, bm_g / (g.nind + 1.0e-12), _mean([d.wscal for d in days]))
        push!(leaf_traj, trees[gidx].leaf_c); push!(npp_traj, bm_g)
    end
    return (leaf_traj, npp_traj)
end

# Exp B — full self-driven (trees + grass grow)
function exp_B(trees0, tmpls, gidx)
    st0 = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
    (_, _, pools_by_year, _) = rollout_canopy_years(phys, alloc, allom, st0, trees0, tmpls, soil, yearly)
    return [py[gidx].leaf_c for py in pools_by_year]
end

println("================ GRASS COVER-MECHANISM RE-DIAGNOSIS ================")
println("FIT config = individual:true ⇒ light()/light_grass() NOT called (annual_natural.c:117);")
println("individual-mode cover reduction = reduce_grass (fpc-only, no carbon killed, not fed to GPP).")
println("So the C's grass is bounded by the LIGHT-LIMITED CARBON BALANCE alone. Testing whether")
println("F_diff already reproduces the C's per-patch grass-leaf spectrum.\n")
println(
    rpad("patch", 6), rpad("ntree", 6), rpad("ff_light", 9), rpad("C_grass_leaf", 13),
    rpad("expA_final", 11), rpad("expB_final", 11), rpad("A/C", 8), "B/C"
)

cleaf = Float64[]; aleaf = Float64[]; bleaf = Float64[]; aratio = Float64[]; bratio = Float64[]
for pn in allpatches
    rows = [r for r in eachindex(ind["type"]) if patchof(r) == pn]
    trows = [r for r in rows if typ(r) <= 6 && vv(r, "height") > 0]
    grows = [r for r in rows if typ(r) >= 7]
    isempty(trows) && continue
    # the C grass carbon for this patch (agb_perm2 = grass leaf; vegc_perm2 = leaf+root). sum over grass rows.
    cgl = sum(vv(r, "agb_perm2") for r in grows; init = 0.0)
    cgv = sum(vv(r, "vegc_perm2") for r in grows; init = 0.0)
    slag = isempty(grows) ? 0.042242 : vv(grows[1], "sla")
    trees0 = vcat([mkpool_t(r) for r in trows], [grass_treepools(max(cgl, 1.0e-4), max(cgv, 2.0e-4), slag)])
    tmpls = vcat([mktmpl_t(r) for r in trows], [mktmpl_g()])
    gidx = length(trees0)
    ffl = ff_light(trees0)
    (la, na) = exp_A(trees0, tmpls, gidx)
    lb = exp_B(trees0, tmpls, gidx)
    af = la[end]; bf = lb[end]
    push!(cleaf, cgl); push!(aleaf, af); push!(bleaf, bf)
    push!(aratio, af / max(cgl, 1.0e-3)); push!(bratio, bf / max(cgl, 1.0e-3))
    println(
        rpad(pn, 6), rpad(length(trows), 6), rpad(round(ffl, digits = 4), 9),
        rpad(round(cgl, digits = 3), 13), rpad(round(af, digits = 2), 11), rpad(round(bf, digits = 2), 11),
        rpad(round(af / max(cgl, 1.0e-3), digits = 2), 8), round(bf / max(cgl, 1.0e-3), digits = 2)
    )
end

println("\n---- SUMMARY (25 patches) ----")
println("C grass leaf   : median ", round(_median(cleaf), digits = 2), "  range [", round(minimum(cleaf), digits = 3), ", ", round(maximum(cleaf), digits = 1), "]")
println("Exp A (fixed T): median ", round(_median(aleaf), digits = 2), "  range [", round(minimum(aleaf), digits = 3), ", ", round(maximum(aleaf), digits = 1), "]")
println("Exp B (self-dr): median ", round(_median(bleaf), digits = 2), "  range [", round(minimum(bleaf), digits = 3), ", ", round(maximum(bleaf), digits = 1), "]")
println("Exp A / C ratio: median ", round(_median(aratio), digits = 2), "  (per-patch grass carbon-balance fidelity at the C's own light)")
println("Exp B / C ratio: median ", round(_median(bratio), digits = 2), "  (coupled self-driven fidelity)")
# correlation of the per-patch grass-leaf spectrum (does F_diff track the C's light gradient?)
_corr(a, b) = (ma = _mean(a); mb = _mean(b); d = sqrt(sum((a .- ma) .^ 2) * sum((b .- mb) .^ 2)); d < 1.0e-12 ? 0.0 : sum((a .- ma) .* (b .- mb)) / d)
println("corr(Exp A, C) across patches = ", round(_corr(aleaf, cleaf), digits = 3))
println("corr(Exp B, C) across patches = ", round(_corr(bleaf, cleaf), digits = 3))
println("===================================================================")

# ── assertions (self-checking reproduction, as scripts/grass_overshoot_diagnosis.jl) ──
# FINDING A: the overshoot is REAL and large even with trees FIXED at the C's structure (so the
# forest-floor light is identical to the C's) — NOT a setup artifact and NOT a tree-growth artifact.
@assert _median(aratio) > 5.0 "expected a large fixed-light grass overshoot (median Exp A/C > 5), got $(_median(aratio))"
# FINDING B: F_diff's grass does NOT track the C's forest-floor-light gradient — its per-patch grass
# leaf is compressed while the C's spans ~4 orders of magnitude (weak cross-patch correlation).
@assert _corr(aleaf, cleaf) < 0.75 "expected weak light-gradient tracking (corr < 0.75), got $(_corr(aleaf, cleaf))"
# FINDING C: in the most-shaded patches the C's grass is (near-)extinct while F_diff's grass thrives —
# the overshoot ratio is huge there (the light-limited carbon balance the C has, F_diff lacks).
@assert maximum(aratio) > 100.0 "expected ≥1 shaded patch with a >100× overshoot, got max $(maximum(aratio))"
println("ALL FINDINGS REPRODUCED + ASSERTED ✓  (real light-limited-carbon-balance overshoot, NOT a cover-cap gap)")

# ── SLURM (run off the login node): submit as a one-task batch job ──
#   #!/usr/bin/env bash
#   #SBATCH --account=waldspektrum --partition=standard --qos=short --nodes=1 --ntasks=1
#   #SBATCH --cpus-per-task=4 --time=00:40:00 --output=logs/grass_mech.%j.out
#   cd <repo>; export JULIA_DEPOT_PATH=$HOME/.julia
#   /p/system/packages_rhel9/tools/julia/1.10.0/bin/julia --project=. scripts/grass_cover_mechanism_diagnosis.jl
