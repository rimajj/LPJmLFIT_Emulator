# =============================================================================
# grass_carbonbalance_probe.jl — the DECISIVE per-term + matched-structure probe for the
# residual BROAD grass overshoot (docs §24 next step). SLURM 1534595 (grass_lightconductance_decomp.jl)
# pinned that the softplus GPP floor (lever A) fixes only DEEP-shade extinction; the MODERATE patches
# still overshoot ~15× (median grass leaf ~90 vs the C's ~6). Respiration/CUE and the demand/gmin terms
# were shown matched/faithful. This probe answers, apples-to-apples on the committed 2008 reference:
#
#  Q1  MATCHED-STRUCTURE overshoot: place F_diff's grass at the C's OWN 2008 equilibrium leaf (agb_perm2)
#      per patch, run one 2009 year (trees fixed at the C structure). Compare F_diff grass ANNUAL NPP vs
#      the C's npp_perm2, and F_diff grass fpar vs the C's fpar_leafon. If F_diff NPP ≫ C NPP at MATCHED
#      fpar ⇒ the overshoot is a GPP-per-absorbed-light gap (respiration is matched). If F_diff fpar ≫ C
#      fpar ⇒ a light-absorption/structure gap.
#  Q2  TERM BREAKDOWN on the brightest warm day, moderate patch: grass GPP, Rd(leaf), Rmaint, Rgrowth,
#      NPP, CUE, and the drivers λ, Vcmax, gc, gp_stand, apar — via a faithful in-script replica of
#      daily_step_canopy's two passes (validated against the kernel NPP to 1e-9).
#  Q3  GRASS-vs-TREE GPP-per-apar in the SAME patch/day: is the grass's GPP/apar anomalous vs the
#      (validated) trees'? (both use the shared kernel — a mismatch localizes a grass-specific input).
#  Q4  FAITHFUL-GRASS-PARAM effect: repeat Q1 with the C's grass params (albedo_leaf 0.23, temp_photos
#      10/30, respcoeff 1.2, cn_root 30) to quantify how much of the residual they close.
#
#   run (SLURM, off the login node — trailing #SBATCH wrapper):
#     JULIA_DEPOT_PATH=$HOME/.julia julia --project=. scripts/grass_carbonbalance_probe.jl
# =============================================================================
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.Allometry
const F = FDiff
import LPJmLFITEmulator.FDiff: autotrophic_respiration, canopy_conductance, _patch_fpars, _wet_interc,
    grass_treepools, individual_from_pools, rollout_daily_canopy, tebs_params, hainich_soilcolumn,
    ppm2bar, ppm2Pa, hour2sec, _LAMBDA_LO, _LAMBDA_HI, FDiffParams, PhotoParams, TempStressParams, RespParams,
    WaterParams, temp_stress, photosynthesis, solve_lambda, priestley_taylor_eeq, patch_albedo
import LPJmLFITEmulator.SmoothOps: softplus, smoothmin, sigmoid

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
gidxs = findall(==(yr1), fyear)
forc = [
    DailyForcing{Float64}(
            swdown = fcol(fdec, "swdown")[i], lwnet = fcol(fdec, "lwnet")[i], temp = fcol(fdec, "temp")[i],
            precip = fcol(fdec, "precip")[i], daylength = fcol(fdec, "daylength")[i], co2 = fcol(fdec, "co2")[i],
        ) for i in gidxs
]

vv(r, k) = parse(Float64, ind[k][r]); typ(r) = parse(Int, ind["type"][r]); patchof(r) = parse(Int, ind["patch"][r])
allpatches = sort(unique(patchof.(eachindex(ind["type"]))))
mkpool_t(r) = TreePools{Float64}(vv(r, "leaf_c"), vv(r, "sapwood_c"), vv(r, "heartwood_c"), vv(r, "root_c"), vv(r, "height"), vv(r, "crownarea"), vv(r, "nind"), vv(r, "sla"), vv(r, "wooddens"), false)
mktmpl_t(r) = Individual{Float64}(vv(r, "fpar_leafon"), 0.0, vv(r, "alphaa"), vv(r, "albedo_leaf"), vv(r, "emax"), vv(r, "sapwood_c"), vv(r, "root_c"), 0.0, 0.02, 0.04, 0.1, 0.4, vv(r, "nind"), PhotoParams{Float64}(; path = :c3, issla = true, sla = vv(r, "sla")), TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false)
# grass template. `faithful` ⇒ the C's Temperate-C3-grass params (albedo_leaf 0.23, temp_photos 10/30).
mktmpl_g(; faithful = false) = Individual{Float64}(
    0.03, 1.0, 0.5, faithful ? 0.23 : 0.15, 10.0, 0.0, 0.0, 0.0, 0.01, 0.15, 0.1, 0.4, 1.0,
    PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.042242),
    TempStressParams{Float64}(; temp_photos_low = faithful ? 10.0 : 20.0, temp_photos_high = 30.0), true,
)

allom = Allometry.TreeAllometry{Float64}()
phys = tebs_params()
# faithful grass respiration bundle (respcoeff 1.2, cn_root 30 — the C's shared values; F_diff default 1.0/29)
phys_gresp = FDiffParams{Float64}(;
    photo = phys.photo, tstress = phys.tstress, water = phys.water,
    resp = RespParams{Float64}(; respcoeff = 1.2, cn_root = 30.0), allom = phys.allom, nlambda = phys.nlambda, ω = phys.ω,
)

# C reference per patch: tree rows, grass equilibrium leaf (agb_perm2), grass vegc, NPP, fpar_leafon
patchref = []
for pn in allpatches
    rows = [r for r in eachindex(ind["type"]) if patchof(r) == pn]
    trows = [r for r in rows if typ(r) <= 6 && vv(r, "height") > 0]
    grows = [r for r in rows if typ(r) >= 7]
    (isempty(trows) || isempty(grows)) && continue
    cgl = sum(vv(r, "agb_perm2") for r in grows); cgv = sum(vv(r, "vegc_perm2") for r in grows)
    cnpp = sum(vv(r, "npp_perm2") for r in grows); cfpar = _mean([vv(r, "fpar_leafon") for r in grows])
    plai = sum(vv(r, "leaf_c") * vv(r, "sla") * vv(r, "nind") for r in trows)
    push!(patchref, (pn = pn, trows = trows, cgl = cgl, cgv = cgv, cnpp = cnpp, cfpar = cfpar, ff = exp(-0.5 * plai)))
end

# ── Q1/Q4: F_diff grass at the C's OWN 2008 leaf, one 2009 year, trees fixed ──
function matched_run(pr, physp; faithful = false)
    L = max(pr.cgl, 1.0e-6); root = max(pr.cgv - pr.cgl, 1.0e-6); slag = 0.042242
    trees = vcat([mkpool_t(r) for r in pr.trows], [grass_treepools(L, L + root, slag)])
    tmpls = vcat([mktmpl_t(r) for r in pr.trows], [mktmpl_g(; faithful = faithful)])
    gidx = length(trees); n = length(trees)
    fpars = _patch_fpars(trees, allom)
    inds = Individual{Float64}[individual_from_pools(tmpls[i], trees[i], allom, fpars[i]) for i in 1:n]
    st0 = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
    (_, days) = rollout_daily_canopy(physp, st0, inds, soil, forc)
    npp = sum(d.npp_ind[gidx] for d in days)
    return (npp = npp, fpar = fpars[gidx], fpc = inds[gidx].fpc, cnpp = pr.cnpp, cfpar = pr.cfpar, cgl = pr.cgl)
end

println("================ GRASS CARBON-BALANCE PROBE ================")
println("Q1 MATCHED STRUCTURE: F_diff grass at the C's OWN 2008 leaf, 1 year (2009), trees fixed.\n")
println(rpad("patch", 6), rpad("ff", 7), rpad("C_leaf", 9), rpad("C_NPP", 9), rpad("Fd_NPP", 9), rpad("NPP F/C", 9), rpad("C_fpar", 9), rpad("Fd_fpar", 9), "fpar F/C")
nppF = Float64[]; nppC = Float64[]; fparF = Float64[]; fparC = Float64[]; nppF_faith = Float64[]
for pr in patchref
    m = matched_run(pr, phys)
    mf = matched_run(pr, phys_gresp; faithful = true)
    push!(nppF, m.npp); push!(nppC, m.cnpp); push!(fparF, m.fpar); push!(fparC, m.cfpar); push!(nppF_faith, mf.npp)
    println(
        rpad(pr.pn, 6), rpad(round(pr.ff, digits = 3), 7), rpad(round(pr.cgl, digits = 3), 9),
        rpad(round(m.cnpp, digits = 3), 9), rpad(round(m.npp, digits = 3), 9),
        rpad(round(m.npp / max(m.cnpp, 1.0e-6), digits = 2), 9), rpad(round(m.cfpar, digits = 5), 9),
        rpad(round(m.fpar, digits = 5), 9), round(m.fpar / max(m.cfpar, 1.0e-9), digits = 3)
    )
end
println("\nSUMMARY Q1: median NPP F/C = ", round(_median(nppF ./ max.(nppC, 1.0e-6)), digits = 2),
    "  median fpar F/C = ", round(_median(fparF ./ max.(fparC, 1.0e-9)), digits = 3),
    "  corr(Fd_NPP,C_NPP) = ", round(_corr(nppF, nppC), digits = 3))
println("Q4 FAITHFUL grass params (albedo .23, tphotos 10/30, respcoeff 1.2, cn 30): median NPP F/C = ",
    round(_median(nppF_faith ./ max.(nppC, 1.0e-6)), digits = 2))

# ── Q2/Q3: single-day term breakdown at the moderate patch, brightest warm day ──
ffmed = _median([pr.ff for pr in patchref])
modpr = patchref[argmin([abs(pr.ff - ffmed) for pr in patchref])]
swd = [f.swdown for f in forc]; tp = [f.temp for f in forc]
warm = [i for i in eachindex(forc) if tp[i] >= 15.0]; warm = isempty(warm) ? collect(eachindex(forc)) : warm
di = warm[argmax(swd[warm])]; f = forc[di]
w = phys.water
w1 = [0.9 * wc for wc in whcs]; rel1 = w1 ./ whcs
wr = sum(soil.rootdist[l] * rel1[l] for l in eachindex(rel1)); phen = 1.0

# faithful daily fluxes for ONE individual, given the reconstructed gp_stand (mirrors daily_step_canopy pass 2)
function ind_terms(g, gp_stand, par, co2_Pa, dl, condfac, eeq, rain, respp)
    fpc_i = g.fpc * phen; fpar_i = g.fpar * phen
    apar = par * (1.0 - g.albedo_leaf) * g.alphaa * fpar_i
    tsi = temp_stress(g.tstress, f.temp, dl)
    (_, _, vm, _) = photosynthesis(g.photo, w.lambda_opt, tsi, co2_Pa, f.temp, apar, dl; comp_vm = true, vm_scale = 1.0)
    supply_i = g.emax * wr * phen
    (wet_i, _) = _wet_interc(g.intc, g.lai, phen, g.fpc, eeq, rain, w.α_PT)
    wet_dem = smoothmin(wet_i, 0.99, w.βw)
    (gc, demand) = canopy_conductance(w, eeq, gp_stand, supply_i; wet = wet_dem)
    gpd = softplus(hour2sec(dl) * (gc * fpc_i - w.gmin * fpar_i), w.βflux)
    fac = gpd / 1.6 * ppm2bar(f.co2)
    p_i = FDiffParams{Float64}(g.photo, g.tstress, w, respp, phys.allom, phys.nlambda, phys.ω)
    λ = clamp(solve_lambda(p_i, fac, tsi, co2_Pa, f.temp, apar, dl, vm), _LAMBDA_LO, _LAMBDA_HI)
    (agd, rd, _, _) = photosynthesis(g.photo, λ, tsi, co2_Pa, f.temp, apar, dl; comp_vm = false, vm = vm)
    gpp = softplus(agd, w.βflux)
    c_sap = g.is_grass ? 0.0 : g.c_sapwood * g.nind; c_root = g.c_root * g.nind
    (npp, ra) = autotrophic_respiration(respp, f.temp, gpp, rd, c_sap, c_root; phen = phen)
    return (; apar, vm, λ, gc, gpp, rd, npp, ra, gpp_per_apar = apar > 0 ? gpp / apar : 0.0, fpar = g.fpar)
end

function breakdown(pr; faithful = false, respp = phys.resp)
    L = max(pr.cgl, 1.0e-6); root = max(pr.cgv - pr.cgl, 1.0e-6)
    trees = vcat([mkpool_t(r) for r in pr.trows], [grass_treepools(L, L + root, 0.042242)])
    tmpls = vcat([mktmpl_t(r) for r in pr.trows], [mktmpl_g(; faithful = faithful)])
    gidx = length(trees); n = length(trees)
    fpars = _patch_fpars(trees, allom)
    inds = Individual{Float64}[individual_from_pools(tmpls[i], trees[i], allom, fpars[i]) for i in 1:n]
    beta = patch_albedo(inds, phen, 0.0)
    eeq = priestley_taylor_eeq(w, f.swdown, f.lwnet, f.temp, f.daylength, beta)
    rain = sigmoid(w.βsnow * (f.temp - w.tsnow)) * f.precip
    par = 0.5 * w.dayseconds * f.swdown; co2_Pa = ppm2Pa(f.co2); dl = f.daylength
    condfac = ppm2bar(f.co2) * (1.0 - w.lambda_opt) * hour2sec(dl)
    gp_acc = 0.0; fpc_tot = 0.0
    for g0 in inds
        fpc_i = g0.fpc * phen
        apar_gp = par * (1.0 - g0.albedo_leaf) * g0.alphaa * fpc_i
        tsi = temp_stress(g0.tstress, f.temp, dl)
        (_, _, _, adtmm_gp) = photosynthesis(g0.photo, w.lambda_opt, tsi, co2_Pa, f.temp, apar_gp, dl; comp_vm = true, vm_scale = 1.0)
        gp_acc += 1.6 * adtmm_gp / condfac + w.gmin * fpc_i; fpc_tot += fpc_i
    end
    gp_stand = fpc_tot > 1.0e-20 ? gp_acc / fpc_tot : 0.0
    gt = ind_terms(inds[gidx], gp_stand, par, co2_Pa, dl, condfac, eeq, rain, respp)
    # trees' GPP-per-apar for comparison (validated kernel)
    tt = [ind_terms(inds[i], gp_stand, par, co2_Pa, dl, condfac, eeq, rain, respp) for i in 1:(gidx - 1)]
    return (gp_stand = gp_stand, grass = gt, trees = tt)
end

println("\nQ2/Q3 TERM BREAKDOWN — moderate patch ", modpr.pn, " (ff=", round(modpr.ff, digits = 3), "), brightest warm day (T=",
    round(f.temp, digits = 1), " sw=", round(f.swdown, digits = 1), " dl=", round(f.daylength, digits = 2), " wr=", round(wr, digits = 3), ")")
b = breakdown(modpr)
g = b.grass
println("  gp_stand = ", round(b.gp_stand, digits = 4), " mm/s")
println("  GRASS: apar=", round(g.apar, digits = 2), " Vcmax=", round(g.vm, digits = 3), " λ=", round(g.λ, digits = 4),
    " gc=", round(g.gc, digits = 4), " | GPP=", round(g.gpp, digits = 4), " Rd=", round(g.rd, digits = 4),
    " NPP=", round(g.npp, digits = 4), " CUE=", round(g.npp / max(g.gpp, 1.0e-9), digits = 3), " GPP/apar=", round(g.gpp_per_apar, sigdigits = 4))
println("  TREES GPP/apar (validated kernel): ", [round(t.gpp_per_apar, sigdigits = 4) for t in b.trees], "  grass GPP/apar=", round(g.gpp_per_apar, sigdigits = 4))
println("  TREES λ: ", [round(t.λ, digits = 3) for t in b.trees], "  grass λ=", round(g.λ, digits = 4))
bf = breakdown(modpr; faithful = true, respp = phys_gresp.resp).grass
println("  FAITHFUL grass (albedo .23, tphotos 10/30, respcoeff 1.2): apar=", round(bf.apar, digits = 2), " Vcmax=", round(bf.vm, digits = 3),
    " λ=", round(bf.λ, digits = 4), " GPP=", round(bf.gpp, digits = 4), " NPP=", round(bf.npp, digits = 4), " CUE=", round(bf.npp / max(bf.gpp, 1.0e-9), digits = 3))

println("\n================ VERDICT ================")
mnf = _median(nppF ./ max.(nppC, 1.0e-6)); mff = _median(fparF ./ max.(fparC, 1.0e-9))
println("Q1: F_diff grass NPP is ", round(mnf, digits = 2), "× the C at MATCHED 2008 leaf; fpar F/C = ", round(mff, digits = 3),
    mff < 1.3 ? " (fpar MATCHED ⇒ overshoot is GPP-per-light, not absorption)" : " (fpar HIGH ⇒ light-absorption gap)")
println("Q3: grass GPP/apar vs trees' — ", abs(g.gpp_per_apar - _mean([t.gpp_per_apar for t in b.trees])) / max(_mean([t.gpp_per_apar for t in b.trees]), 1e-9) < 0.25 ?
    "SIMILAR (kernel consistent ⇒ C-grass genuinely lower, a grass-specific physics F_diff lacks)" : "ANOMALOUS (grass-specific input inflates GPP)")

# ── SLURM (run off the login node): submit as a one-task batch job ──
#   #!/usr/bin/env bash
#   #SBATCH --account=waldspektrum --partition=standard --qos=short --nodes=1 --ntasks=1
#   #SBATCH --cpus-per-task=4 --time=00:30:00 --output=logs/grass_cbal.%j.out
#   cd /p/projects/open/Jamir/esm_land_emulator; export JULIA_DEPOT_PATH=$HOME/.julia
#   /p/system/packages_rhel9/tools/julia/1.10.0/bin/julia --project=. scripts/grass_carbonbalance_probe.jl
