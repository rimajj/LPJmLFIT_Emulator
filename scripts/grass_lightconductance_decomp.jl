# =============================================================================
# grass_lightconductance_decomp.jl — PIN THE LEVER for the F_diff grass overshoot
# (docs §24 corrected next step: a light-limited grass carbon balance). Sessions 17/19
# diagnosed a REAL grass overshoot with F_diff's grass insensitive to shading (median
# Exp A/C ×13.9, cross-patch corr 0.57) driven by an under-light-limited grass NPP with a
# ~2.9 gC/m²/yr LIGHT-INSENSITIVE floor. This script DECOMPOSES the mechanism, isolating
# each candidate lever ONE AT A TIME on the committed Hainich reference, so the fix targets
# the RIGHT term before any physics change to the (validated, byte-identical) tree kernel.
#
# LEVERS (from the C source /home/jamirp/lpjml56fit + the F_diff kernel daily_step_canopy):
#   A  the GPP non-negativity softplus floor  gpp_i = softplus(agd, w.βflux)  (fdiff.jl:1533).
#      βflux=50 ⇒ softplus(0,50)=log(2)/50=0.0139 gC/m²/day injected even at ~zero absorbed
#      light. The C uses a HARD max(0,agd) (water_stressed.c:259, photosynthesis.c:166) — NO
#      soft floor. Toggle: raise βflux (1e6 ≈ hard relu, floor ≤ 7e-7 gC/day). Grass-only in
#      effect because softplus(agd,β)≈agd whenever agd≫1/β and trees run at agd=O(1-10) gC/day
#      (VERIFIED here via tree-NPP invariance).
#   B  grass gmin 0.8 vs stand 0.3/1.0  (the -gmin·fpar_i term at :1518, +gmin·fpc_i at :1493).
#      C source: under shade every gmin-bearing term is scaled by a fraction that → 0, so gmin
#      cannot create/remove the floor. Expected NON-decisive (and it co-perturbs trees).
#   C  attenuate the demand gc·fpc_i by fpar_i for the grass (:1518). C source water_stressed.c:194
#      uses gc·pft->fpc − gmin·fpar(pft) — un-attenuated fpc on the gc term — i.e. F_diff is
#      ALREADY FAITHFUL here; lever C would make F_diff LESS faithful. Tested to quantify/confirm
#      it is not the (sole) lever.
#
# TWO MEASUREMENTS PER CONFIG (comparable to the committed probes):
#   FLOOR — grass leaf held at L=0.01 gC/m², one 2009-forcing year at the C's fixed 2008 tree
#           structure, shaded patch 3 & lit patch 13; Σ grass npp_ind. floor_ratio=|sh-lit|/lit.
#   CORR  — Exp A across 25 patches (trees FIXED at C 2008, grass self-driven 11 decadal years);
#           corr(grass leaf, C grass leaf) + median A/C.
#
#   run (off the login node via SLURM — trailing #SBATCH wrapper):
#     JULIA_DEPOT_PATH=$HOME/.julia julia --project=. scripts/grass_lightconductance_decomp.jl
# =============================================================================
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.Allometry
const F = FDiff
import LPJmLFITEmulator.FDiff: grass_treepools, rollout_daily_canopy, tebs_params,
    tebs_allocparams, hainich_soilcolumn, individual_from_pools, _patch_fpars,
    grow_grass_individual, grass_allocparams, WaterParams, FDiffParams, PhotoParams,
    TempStressParams

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

# ── reference: 2008 start structure + decadal forcing (same loads as the committed probes) ──
ind = readcsv(joinpath(REFDIR, "hainich_individuals_2008.csv"))
fdec = readcsv(joinpath(REFDIR, "hainich_decadal_forcing.csv"))
(sd, whcs, rdist) = readtable(joinpath(REFDIR, "hainich_soilcolumn.txt"))
soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)

fyear = Int.(round.(fcol(fdec, "year"))); syears = sort(unique(fyear))
mkforc(idxs) = [
    DailyForcing{Float64}(
            swdown = fcol(fdec, "swdown")[i], lwnet = fcol(fdec, "lwnet")[i], temp = fcol(fdec, "temp")[i],
            precip = fcol(fdec, "precip")[i], daylength = fcol(fdec, "daylength")[i], co2 = fcol(fdec, "co2")[i],
        ) for i in idxs
]
forc = mkforc(findall(==(syears[1]), fyear))                    # first year (2009), for the floor
yearly = [mkforc(findall(==(yr), fyear)) for yr in syears]      # all 11 years, for Exp A

vv(r, k) = parse(Float64, ind[k][r])
typ(r) = parse(Int, ind["type"][r])
patchof(r) = parse(Int, ind["patch"][r])
allpatches = sort(unique(patchof.(eachindex(ind["type"]))))

mkpool_t(r) = TreePools{Float64}(vv(r, "leaf_c"), vv(r, "sapwood_c"), vv(r, "heartwood_c"), vv(r, "root_c"), vv(r, "height"), vv(r, "crownarea"), vv(r, "nind"), vv(r, "sla"), vv(r, "wooddens"), false)
mktmpl_t(r) = Individual{Float64}(vv(r, "fpar_leafon"), 0.0, vv(r, "alphaa"), vv(r, "albedo_leaf"), vv(r, "emax"), vv(r, "sapwood_c"), vv(r, "root_c"), 0.0, 0.02, 0.04, 0.1, 0.4, vv(r, "nind"), PhotoParams{Float64}(; path = :c3, issla = true, sla = vv(r, "sla")), TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false)
mktmpl_g() = Individual{Float64}(0.03, 1.0, 0.5, 0.15, 10.0, 0.0, 0.0, 0.0, 0.01, 0.15, 0.1, 0.4, 1.0, PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.042242), TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), true)

allom = Allometry.TreeAllometry{Float64}(); galloc = grass_allocparams(); phys0 = tebs_params()

# ── src-free lever helpers ──────────────────────────────────────────────────────────────────
# (A/B) whole-stand WaterParams override via the @kwdef-preserved positional inner ctor.
function with_water(w::WaterParams{Float64}; kw...)
    d = Dict(kw)
    vals = Any[haskey(d, f) ? d[f] : getfield(w, f) for f in fieldnames(WaterParams)]
    return WaterParams{Float64}(vals...)
end
rebundle(p::FDiffParams{Float64}, w::WaterParams{Float64}) =
    FDiffParams{Float64}(; photo = p.photo, tstress = p.tstress, water = w, resp = p.resp, allom = p.allom, nlambda = p.nlambda, ω = p.ω)
# (C) grass-only monkey-patch: copy the grass Individual with fpc := fpar (all 16 fields, positional ctor).
function grass_fpc_to_fpar(g::Individual{Float64})
    return Individual{Float64}(g.fpar, g.fpar, g.alphaa, g.albedo_leaf, g.emax, g.c_sapwood, g.c_root, g.lai, g.intc, g.albedo_stem, g.albedo_litter, g.snowcanopyfrac, g.nind, g.photo, g.tstress, g.is_grass)
end

# ── config: named lever toggles off B0 ──
struct Cfg
    name::String
    βflux::Float64
    gmin::Float64
    demand_fpar::Bool     # grass fpc := fpar (lever C)
end
physof(c::Cfg) = rebundle(phys0, with_water(phys0.water; βflux = c.βflux, gmin = c.gmin))
GMIN0 = phys0.water.gmin       # running baseline gmin (tebs_params sets 1.0)
BF0 = phys0.water.βflux        # running baseline βflux (50)

# ── FLOOR: grass leaf held at L, one year, at the fixed C tree structure of one patch.
#    returns (grass_npp, tree_npp_total, fpar, fpc). ──
function floor_run(c::Cfg, trows, L; lmtorm = 0.8)
    slag = 0.042242
    root = L / lmtorm
    trees = vcat([mkpool_t(r) for r in trows], [grass_treepools(max(L, 1.0e-6), max(L + root, 2.0e-6), slag)])
    tmpls = vcat([mktmpl_t(r) for r in trows], [mktmpl_g()])
    gidx = length(trees)
    fpars = _patch_fpars(trees, allom)
    n = length(trees)
    inds = Individual{Float64}[individual_from_pools(tmpls[i], trees[i], allom, fpars[i]) for i in 1:n]
    c.demand_fpar && (inds[gidx] = grass_fpc_to_fpar(inds[gidx]))
    st0 = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
    (_, days) = rollout_daily_canopy(physof(c), st0, inds, soil, forc)
    gnpp = sum(d.npp_ind[gidx] for d in days)
    tnpp = sum(sum(@view d.npp_ind[1:(gidx - 1)]) for d in days)
    return (npp = gnpp, tnpp = tnpp, fpar = fpars[gidx], fpc = inds[gidx].fpc)
end

# ── CORR: Exp A (trees fixed, grass self-driven 11 yr) for one patch → final grass leaf. ──
function expA_leaf(c::Cfg, trees0, tmpls, gidx)
    physp = physof(c)
    trees = collect(trees0)
    st = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
    n = length(trees)
    local last_leaf = trees[gidx].leaf_c
    for fy in yearly
        fpars = _patch_fpars(trees, allom)
        inds = Individual{Float64}[individual_from_pools(tmpls[i], trees[i], allom, fpars[i]) for i in 1:n]
        c.demand_fpar && (inds[gidx] = grass_fpc_to_fpar(inds[gidx]))
        (st, days) = rollout_daily_canopy(physp, st, inds, soil, fy)
        bm_g = sum(d.npp_ind[gidx] for d in days)
        g = trees[gidx]
        trees[gidx] = grow_grass_individual(galloc, g, bm_g / (g.nind + 1.0e-12), _mean([d.wscal for d in days]))
        last_leaf = trees[gidx].leaf_c
    end
    return last_leaf
end

# precompute per-patch tree rows + C grass leaf (shared across configs)
patchdata = []
for pn in allpatches
    rows = [r for r in eachindex(ind["type"]) if patchof(r) == pn]
    trows = [r for r in rows if typ(r) <= 6 && vv(r, "height") > 0]
    grows = [r for r in rows if typ(r) >= 7]
    isempty(trows) && continue
    cgl = sum(vv(r, "agb_perm2") for r in grows; init = 0.0)
    cgv = sum(vv(r, "vegc_perm2") for r in grows; init = 0.0)
    slag = isempty(grows) ? 0.042242 : vv(grows[1], "sla")
    trees0 = vcat([mkpool_t(r) for r in trows], [grass_treepools(max(cgl, 1.0e-4), max(cgv, 2.0e-4), slag)])
    tmpls = vcat([mktmpl_t(r) for r in trows], [mktmpl_g()])
    push!(patchdata, (pn = pn, trows = trows, trees0 = trees0, tmpls = tmpls, gidx = length(trees0), cgl = cgl))
end
p3 = first(pd for pd in patchdata if pd.pn == 3).trows
p13 = first(pd for pd in patchdata if pd.pn == 13).trows

# ── run a config: floor (shaded+lit) + Exp A corr/median across 25 patches ──
function run_cfg(c::Cfg)
    fs = floor_run(c, p3, 0.01); fl = floor_run(c, p13, 0.01)
    aleaf = Float64[]; cleaf = Float64[]; aratio = Float64[]
    for pd in patchdata
        af = expA_leaf(c, pd.trees0, pd.tmpls, pd.gidx)
        push!(aleaf, af); push!(cleaf, pd.cgl); push!(aratio, af / max(pd.cgl, 1.0e-3))
    end
    return (
        floor_sh = fs.npp, floor_lit = fl.npp,
        floor_ratio = abs(fs.npp - fl.npp) / max(fl.npp, 1.0e-9),
        tnpp_sh = fs.tnpp, corr = _corr(aleaf, cleaf), medAC = _median(aratio),
        aleaf = aleaf, cleaf = cleaf,
    )
end

println("================ GRASS LIGHT- vs CONDUCTANCE-LIMITATION DECOMPOSITION ================")
println("baseline (running): βflux=", BF0, "  gmin=", GMIN0, "  demand term = gc·fpc (faithful to water_stressed.c:194)")
println("floor = grass NPP (gC/m²/yr) at leaf 0.01 (≈zero light); corr/medA-C = Exp A (trees fixed) vs C, 25 patches\n")

configs = [
    Cfg("B0", BF0, GMIN0, false),
    Cfg("A:βflux=1e3", 1.0e3, GMIN0, false),
    Cfg("A:βflux=1e6", 1.0e6, GMIN0, false),
    Cfg("B:gmin=0.3", BF0, 0.3, false),
    Cfg("B:gmin=0.8", BF0, 0.8, false),
    Cfg("C:demand→fpar", BF0, GMIN0, true),
    Cfg("A+C", 1.0e6, GMIN0, true),
]

results = Dict{String, Any}()
b0tnpp = Ref(0.0)
verdict(r) = (r.floor_sh < 0.5 && r.corr > 0.90) ? "COLLAPSES" : ((r.floor_sh < 1.5 || r.corr > 0.75) ? "PARTIAL" : "NO-EFFECT")
println(rpad("config", 16), rpad("floor_sh", 10), rpad("floor_lit", 10), rpad("ratio", 8), rpad("corrA", 8), rpad("medA/C", 9), rpad("treeNPPΔ", 11), "verdict")
for c in configs
    r = run_cfg(c)
    results[c.name] = r
    c.name == "B0" && (b0tnpp[] = r.tnpp_sh)
    tΔ = abs(r.tnpp_sh - b0tnpp[]) / max(abs(b0tnpp[]), 1.0e-12)
    println(
        rpad(c.name, 16), rpad(round(r.floor_sh, digits = 3), 10), rpad(round(r.floor_lit, digits = 3), 10),
        rpad(round(r.floor_ratio, digits = 3), 8), rpad(round(r.corr, digits = 3), 8),
        rpad(round(r.medAC, digits = 2), 9), rpad(round(tΔ, sigdigits = 2), 11), verdict(r)
    )
end

# per-patch Exp A leaf for B0 vs A:βflux=1e6 (shaded→extinct, lit→thriving is the C's fingerprint)
rA = results["A:βflux=1e6"]; rB0 = results["B0"]
println("\n---- per-patch Exp A grass leaf: does lever A recover the C's light gradient? ----")
println(rpad("patch", 7), rpad("C_leaf", 11), rpad("B0_leaf", 11), rpad("leverA_leaf", 13))
for (k, pd) in enumerate(patchdata)
    println(rpad(pd.pn, 7), rpad(round(pd.cgl, digits = 3), 11), rpad(round(rB0.aleaf[k], digits = 2), 11), round(rA.aleaf[k], digits = 2))
end

println("\n================ VERDICT ================")
decisive = [c.name for c in configs if results[c.name].floor_sh < 0.5 && results[c.name].corr > 0.90]
println("decisive lever(s) (floor_sh<0.5 & corrA>0.90): ", isempty(decisive) ? "NONE ALONE" : join(decisive, ", "))
tΔA = abs(rA.tnpp_sh - rB0.tnpp_sh) / max(abs(rB0.tnpp_sh), 1.0e-12)
println("lever A grass-only check: |treeNPP(1e6)−treeNPP(50)|/treeNPP(50) = ", round(tΔA, sigdigits = 3))

# ── assertions ──
# (1) B0 reproduces the committed diagnosis (regression gate; committed floor≈2.94, corr≈0.566, medA/C≈13.87).
@assert 2.3 < rB0.floor_sh < 3.6 "B0 floor should reproduce ≈2.94, got $(rB0.floor_sh)"
@assert 0.40 < rB0.corr < 0.72 "B0 corr should reproduce ≈0.566, got $(rB0.corr)"
@assert rB0.medAC > 5.0 "B0 median Exp A/C should reproduce >5 (≈13.87), got $(rB0.medAC)"
# (2) LEVER A (hard GPP floor, βflux=1e6) COLLAPSES the light-insensitive floor.
@assert rA.floor_sh < 0.5 "lever A should collapse the shaded low-light floor (<0.5), got $(rA.floor_sh)"
# (3) LEVER A is grass-only (trees byte-safe: softplus saturates, tree NPP invariant).
@assert tΔA < 1.0e-3 "lever A must leave tree NPP invariant (grass-only), got Δ=$(tΔA)"
# (4) LEVER B (gmin) does NOT collapse the floor (confirms non-decisive).
@assert results["B:gmin=0.8"].floor_sh > 1.5 "lever B (gmin=0.8) should NOT collapse the floor, got $(results["B:gmin=0.8"].floor_sh)"
println("\nASSERTED ✓  lever A (hard GPP floor) collapses the light-insensitive floor and is grass-only;")
println("            lever B (gmin) does not — the softplus GPP floor (fdiff.jl:1533) is the pinned lever.")
println("            corr(lever A) = ", round(rA.corr, digits = 3), " (from B0 ", round(rB0.corr, digits = 3), ") — ",
    rA.corr > 0.90 ? "SUFFICIENT ALONE" : "improved; residual = grass-param fidelity (respcoeff/temp_photos/albedo/turnover)")

# ── SLURM (run off the login node): submit as a one-task batch job ──
#   #!/usr/bin/env bash
#   #SBATCH --account=waldspektrum --partition=standard --qos=short --nodes=1 --ntasks=1
#   #SBATCH --cpus-per-task=4 --time=00:40:00 --output=logs/grass_decomp.%j.out
#   cd /p/projects/open/Jamir/esm_land_emulator; export JULIA_DEPOT_PATH=$HOME/.julia
#   /p/system/packages_rhel9/tools/julia/1.10.0/bin/julia --project=. scripts/grass_lightconductance_decomp.jl
