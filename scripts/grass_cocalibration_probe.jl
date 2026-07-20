# =============================================================================
# grass_cocalibration_probe.jl — §26 grass-equilibrium CO-CALIBRATION probe.
#
# §25 committed the per-PFT grass phenology fix (matched-structure grass NPP 4.26× → 1.13× the C, corr
# 0.973) and named three INTERACTING faithful mechanisms F_diff still lacks, to be co-calibrated together.
# The FIRST co-calibration probe REFUTED the §25 hard-floor lever (a large grass-only `βflux` recovering
# `max(0,agd)` drove deep-shade grass NPP strongly NEGATIVE: flooring the demand `gpd→0` collapses `fac`,
# so the fixed-graph λ-solve returns a degenerate low λ that suppresses `agd` while `rd` stays normal). The
# C avoids this by GATING (`water_stressed.c:196` `if(gpd>1e-5)` skips photosynthesis ⇒ agd=0, no leaf
# resp) and scaling `mresp·phen` (`npp_grass.c`, already matched by `autotrophic_respiration`). So the three
# faithful mechanisms are now:
#   (i)   the grass photosynthesis DEMAND-GATE (`WaterParams.grass_demand_gate`) — a smooth sigmoid of the
#         pre-floor demand `gpd` that zeroes BOTH grass GPP and `rd` as demand→0 (no degenerate solve);
#   (ii)  the grass GSI light-limiter SEASON — F_diff's `:linear` `grass_lf = 1−Σ fpar·phen` proxy vs the
#         faithful `:exp` Lambert-Beer transmission `exp(−k·Σ plai·phen)` (getfpar.c);
#   (iii) grass ESTABLISHMENT / re-seeding (establishment_grass.c) — maintains the C's DIM-patch grass
#         where the light-limited NPP is below the annual turnover (else it goes extinct).
#
# This probe turns those FAITHFUL mechanisms on (they are NOT free knobs — demand-gate, :exp light and
# establishment are all verbatim C behaviour) in every combination and measures the per-patch grass
# spectrum vs the C, to find the config that reproduces the C without over/under-correcting.
#
# PART 1  matched-structure (grass at the C's OWN 2008 leaf, trees fixed, 1 yr 2009): per-patch grass NPP
#         F/C across {demand-gate off | on} × {:linear | :exp forest-floor light}, all per-PFT phen.
#         Metrics: median F/C, corr, AGGREGATE F/C (Σ_F/Σ_C = the cell carbon match), RMS log10(F/C)
#         over the carbon-bearing patches, and the deep-shade extinction count (C<1 ⇒ F should be <1 too).
# PART 2  self-driven grass equilibrium (trees FIXED at C 2008, grass grows 11 yr via grow_grass_individual)
#         × {no-estab | estab}, testing the ACTUAL _treepools_fpc + grass_estabparams increment: does
#         establishment keep the dim patches alive without exploding the bright ones? Final grass leaf F/C.
#
#   run (SLURM): JULIA_DEPOT_PATH=$HOME/.julia julia --project=. scripts/grass_cocalibration_probe.jl
# =============================================================================
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.Allometry
const F = FDiff
import LPJmLFITEmulator.FDiff: grass_treepools, rollout_daily_canopy, tebs_params, tebs_allocparams,
    hainich_soilcolumn, individual_from_pools, _patch_fpars, grow_grass_individual, grass_allocparams,
    grass_estabparams, _treepools_fpc, WaterParams, FDiffParams, PhotoParams, TempStressParams, TreePools

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
_rmslog(f, c; thr = 1.0) = (v = [log10(max(fi, 1.0e-6) / max(ci, 1.0e-6)) for (fi, ci) in zip(f, c) if ci >= thr]; isempty(v) ? 0.0 : sqrt(_mean(v .^ 2)))

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
forc = mkforc(findall(==(syears[1]), fyear))
yearly = [mkforc(findall(==(yr), fyear)) for yr in syears]

vv(r, k) = parse(Float64, ind[k][r]); typ(r) = parse(Int, ind["type"][r]); patchof(r) = parse(Int, ind["patch"][r])
allpatches = sort(unique(patchof.(eachindex(ind["type"]))))
mkpool_t(r) = TreePools{Float64}(vv(r, "leaf_c"), vv(r, "sapwood_c"), vv(r, "heartwood_c"), vv(r, "root_c"), vv(r, "height"), vv(r, "crownarea"), vv(r, "nind"), vv(r, "sla"), vv(r, "wooddens"), false)
mktmpl_t(r) = Individual{Float64}(vv(r, "fpar_leafon"), 0.0, vv(r, "alphaa"), vv(r, "albedo_leaf"), vv(r, "emax"), vv(r, "sapwood_c"), vv(r, "root_c"), 0.0, 0.02, 0.04, 0.1, 0.4, vv(r, "nind"), PhotoParams{Float64}(; path = :c3, issla = true, sla = vv(r, "sla")), TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false)
mktmpl_g() = Individual{Float64}(0.03, 1.0, 0.5, 0.15, 10.0, 0.0, 0.0, 0.0, 0.01, 0.15, 0.1, 0.4, 1.0, PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.042242), TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), true)
allom = Allometry.TreeAllometry{Float64}(); phys0 = tebs_params(); galloc = grass_allocparams()
estab = grass_estabparams()

with_water(w; kw...) = (d = Dict(kw); WaterParams{Float64}(Any[haskey(d, f) ? d[f] : getfield(w, f) for f in fieldnames(WaterParams)]...))
rebundle(p, w) = FDiffParams{Float64}(; photo = p.photo, tstress = p.tstress, water = w, resp = p.resp, allom = p.allom, nlambda = p.nlambda, ω = p.ω)
physgate(gate::Bool, βg::Float64 = 2.0e4) = rebundle(phys0, with_water(phys0.water; grass_demand_gate = gate, βgpd_gate = βg))

# ── per-patch reference (mixed tree+grass patches only) ──
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

# ─────────────────────────────── PART 1: matched-structure per-patch grass NPP ────────────────────────
function matched_npp(pr; gate, lfmode, βg = 2.0e4)
    L = max(pr.cgl, 1.0e-6); root = max(pr.cgv - pr.cgl, 1.0e-6)
    trees = vcat([mkpool_t(r) for r in pr.trows], [grass_treepools(L, L + root, 0.042242)])
    tmpls = vcat([mktmpl_t(r) for r in pr.trows], [mktmpl_g()])
    gidx = length(trees); n = length(trees)
    fpars = _patch_fpars(trees, allom)
    inds = Individual{Float64}[individual_from_pools(tmpls[i], trees[i], allom, fpars[i]) for i in 1:n]
    st0 = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
    pids = vcat(fill(3, length(pr.trows)), [8])
    (_, days) = rollout_daily_canopy(physgate(gate, βg), st0, inds, soil, forc; pft_ids = pids, grass_lf_mode = lfmode)
    return sum(d.npp_ind[gidx] for d in days)
end

# gate SHARPNESS sweep (the C is a HARD step at gpd>1e-5): a sharp gate should touch only the days the C
# also gates (gpd≤1e-5), leaving the carbon-bearing mid/bright patches at their gate-off level.
p1cfgs = [
    (name = "gateoff-lin (§25 base)", gate = false, lf = :linear, βg = 2.0e4),
    (name = "gate2e4-lin", gate = true, lf = :linear, βg = 2.0e4),
    (name = "gate1e6-lin", gate = true, lf = :linear, βg = 1.0e6),
    (name = "gate1e8-lin", gate = true, lf = :linear, βg = 1.0e8),
    (name = "gateoff-exp", gate = false, lf = :exp, βg = 2.0e4),
    (name = "gate1e8-exp", gate = true, lf = :exp, βg = 1.0e8),
]
nc = [pr.cnpp for pr in patchref]
println("================ §26 GRASS CO-CALIBRATION — PART 1: matched-structure per-patch grass NPP ================")
println("grass at C's OWN 2008 leaf, trees fixed, 1 yr; per-PFT grass phen; F/C vs the C's npp_perm2.\n")
# per-patch detail for the two extreme configs
hdr = rpad("patch", 6) * rpad("ff", 7) * rpad("C_NPP", 9)
for c in p1cfgs
    global hdr *= rpad(split(c.name)[1], 11)
end
println(hdr)
p1res = Dict{String, Vector{Float64}}()
for c in p1cfgs
    p1res[c.name] = [matched_npp(pr; gate = c.gate, lfmode = c.lf, βg = c.βg) for pr in patchref]
end
for (i, pr) in enumerate(patchref)
    row = rpad(pr.pn, 6) * rpad(round(pr.ff, digits = 3), 7) * rpad(round(pr.cnpp, digits = 2), 9)
    for c in p1cfgs
        row *= rpad(round(p1res[c.name][i] / max(pr.cnpp, 1.0e-6), digits = 2), 11)
    end
    println(row)
end
println("\n", rpad("config", 26), rpad("medF/C", 9), rpad("corr", 8), rpad("aggF/C", 9), rpad("rmslog", 9), "shade_ok(C<1→F<1)")
for c in p1cfgs
    nf = p1res[c.name]
    shade = [(pr.cnpp < 1.0) for pr in patchref]
    okshade = count(i -> shade[i] && nf[i] < 1.0, eachindex(nf))
    nshade = count(shade)
    println(
        rpad(c.name, 26), rpad(round(_median(nf ./ max.(nc, 1.0e-6)), digits = 2), 9),
        rpad(round(_corr(nf, nc), digits = 3), 8), rpad(round(sum(nf) / sum(nc), digits = 3), 9),
        rpad(round(_rmslog(nf, nc), digits = 3), 9), "$okshade/$nshade"
    )
end

# ─────────────────────────────── PART 2: self-driven grass equilibrium + establishment ────────────────
# trees FIXED at the C 2008 structure, grass grows 11 yr via grow_grass_individual; establishment applies
# the ACTUAL _treepools_fpc gate + grass_estabparams increment (establishment_grass.c individual mode).
function selfdriven_leaf(pr; gate, lfmode, do_estab, βg = 1.0e8)
    L = max(pr.cgl, 1.0e-4); root = max(pr.cgv - pr.cgl, 2.0e-4)
    trees = vcat([mkpool_t(r) for r in pr.trows], [grass_treepools(L, L + root, 0.042242)])
    tmpls = vcat([mktmpl_t(r) for r in pr.trows], [mktmpl_g()])
    gidx = length(trees); n = length(trees)
    st = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
    pids = vcat(fill(3, length(pr.trows)), [8])
    local last = trees[gidx].leaf_c
    for fy in yearly
        fpars = _patch_fpars(trees, allom)
        inds = Individual{Float64}[individual_from_pools(tmpls[i], trees[i], allom, fpars[i]) for i in 1:n]
        (st, days) = rollout_daily_canopy(physgate(gate, βg), st, inds, soil, fy; pft_ids = pids, grass_lf_mode = lfmode)
        bm_g = sum(d.npp_ind[gidx] for d in days)
        wsc = _mean([d.wscal for d in days])
        trees[gidx] = grow_grass_individual(galloc, trees[gidx], bm_g / (trees[gidx].nind + 1.0e-12), wsc)
        if do_estab
            fpc_total = sum(_treepools_fpc(t, allom) for t in trees)
            est = max(0.0, 1.0 - fpc_total)            # n_est = 1 (single grass PFT here)
            if est > 0.0
                g = trees[gidx]
                trees[gidx] = TreePools{Float64}(
                    g.leaf_c + estab.sapl_leaf * est, g.sapwood_c, g.heartwood_c, g.root_c + estab.sapl_root * est,
                    g.height, g.crownarea, g.nind, g.sla, g.wooddens, g.is_grass,
                )
            end
        end
        last = trees[gidx].leaf_c
    end
    return last
end

p2cfgs = [
    (name = "gateoff-lin no-estab", gate = false, lf = :linear, est = false),
    (name = "gateon-exp  no-estab", gate = true, lf = :exp, est = false),
    (name = "gateon-exp  +estab", gate = true, lf = :exp, est = true),
    (name = "gateoff-exp +estab", gate = false, lf = :exp, est = true),
]
println("\n================ PART 2: self-driven grass equilibrium (trees fixed, 11 yr) ================")
println("final grass LEAF carbon F/C vs the C's 2008 grass leaf (cgl); extinct = F<0.05·C, explode = F>5·C.\n")
cgls = [pr.cgl for pr in patchref]
println(rpad("config", 22), rpad("medLeafF/C", 12), rpad("corr", 8), rpad("#extinct", 10), rpad("#explode", 10), "aggF/C")
for c in p2cfgs
    lf = [selfdriven_leaf(pr; gate = c.gate, lfmode = c.lf, do_estab = c.est) for pr in patchref]
    ext = count(i -> lf[i] < 0.05 * max(cgls[i], 1.0e-6), eachindex(lf))
    exp = count(i -> lf[i] > 5.0 * max(cgls[i], 1.0e-6), eachindex(lf))
    println(
        rpad(c.name, 22), rpad(round(_median(lf ./ max.(cgls, 1.0e-6)), digits = 2), 12),
        rpad(round(_corr(lf, cgls), digits = 3), 8), rpad(ext, 10), rpad(exp, 10),
        round(sum(lf) / sum(cgls), digits = 3)
    )
end
println("\nDONE.")

# ── SLURM ──
#   #!/usr/bin/env bash
#   #SBATCH --account=waldspektrum --partition=standard --qos=short --nodes=1 --ntasks=1
#   #SBATCH --cpus-per-task=4 --time=00:30:00 --output=logs/grass_cocal.%j.out
#   cd /p/projects/open/Jamir/esm_land_emulator; export JULIA_DEPOT_PATH=$HOME/.julia
#   /p/system/packages_rhel9/tools/julia/1.10.0/bin/julia --project=. scripts/grass_cocalibration_probe.jl
