# =============================================================================
# grass_overshoot_diagnosis.jl — reproduce the SESSION-17 grass-overshoot re-diagnosis
# (docs/phase3_fdiff_cbinary_validation.md §22). Session 16 (§21) attributed the §20
# self-driven grass-NPP overshoot (~3x) to the shared stand-mean conductance `gp_stand`
# "over-supplying the understory grass" and set PER-PFT conductance as the next step.
# This script REFUTES that attribution three ways, on the committed Hainich 2010/2008
# reference (no HPC/`/p/tmp` dependency; runs against `--project=.`, runtime deps only).
#
#   run:  JULIA_DEPOT_PATH=$HOME/.julia julia --project=. scripts/grass_overshoot_diagnosis.jl
#   (submit via SLURM off the login node — a one-line `#SBATCH ... --project=. <this>` batch job;
#    verified session-17 as SLURM job 1530883, COMPLETED, all three findings asserted.)
#
# It is a SCRIPT, not a `@testitem`, deliberately: the heavy per-cell canopy-conductance
# instrumentation (finding 2) compiles the `daily_step_canopy` path and, added to the
# parallel ReTestItems pool, shifted worker scheduling enough to trip a pre-existing
# Enzyme-0.13-on-Julia-1.10-`lts` `LLVM error: Canonicalization failed` in the (unrelated)
# Enzyme-reverse canopy testitems — a known Enzyme+worker fragility, not a defect here.
# Keeping the reproduction as a standalone script keeps that compilation out of the test
# pool while remaining committed + reproducible. (Re-add as a gate once Enzyme is robust.)
#
# FINDINGS (all printed + asserted below):
#   1. NO per-year overshoot at fixed structure: at the C's OWN grass structure F_diff's
#      self-computed per-year grass NPP totals ~0.83x the C (a mild UNDERshoot).
#   2. F_diff's grass GPP already uses `gp_stand` (like the C): gc_grass ~= 0.75*gp_stand
#      (moist Hainich soil, wscal ~0.99); the grass's own gp is ~0.14*gp_stand, so a
#      per-PFT (own-gp) conductance would change the grass GPP ~43% — a DE-calibration.
#   3. The "3x" is a MULTI-YEAR structural-feedback over-growth: self-driven the grass leaf
#      grows far past the C's suppressed value (leaf -> lai -> forest-floor fpar -> NPP),
#      because F_diff lacks the C's grass cover/light competition (light.c -> light_grass.c).
# =============================================================================
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.Allometry
const F = FDiff
import LPJmLFITEmulator.FDiff: grass_treepools, rollout_daily_canopy, daily_step_canopy,
    rollout_canopy_years, tebs_params, tebs_allocparams, hainich_soilcolumn, canopy_conductance,
    photosynthesis, temp_stress, priestley_taylor_eeq, patch_albedo, ppm2Pa, ppm2bar, hour2sec,
    solve_lambda, FDiffParams, _wet_interc, _infiltrate, sigmoid, softplus, smoothmin,
    _step_pft_phen_day!, pft_phenparams, PhenState, PhenParams, _pft_is_grass, _phen_at,
    _LAMBDA_LO, _LAMBDA_HI, individual_from_pools, _patch_fpars, grow_individual, grow_grass_individual

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
_mean(x) = sum(x) / length(x)

# ── shared 2010 reference ─────────────────────────────────────────────────────────────
f2010 = readcsv(joinpath(REFDIR, "hainich_forcing_2010.csv"))
ind2010 = readcsv(joinpath(REFDIR, "hainich_individuals_2010.csv"))
(sd, whcs, rdist) = readtable(joinpath(REFDIR, "hainich_soilcolumn.txt"))
soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)
n = length(f2010["doy"])
forc2010 = [
    DailyForcing{Float64}(
            swdown = fcol(f2010, "swdown")[i], lwnet = fcol(f2010, "lwnet")[i], temp = fcol(f2010, "temp")[i],
            precip = fcol(f2010, "precip")[i], daylength = fcol(f2010, "daylength")[i], co2 = fcol(f2010, "co2")[i]
        ) for i in 1:n
]
patches = sort(unique(parse.(Int, ind2010["patch"])))
prows = Dict(p => Int[] for p in patches)
for r in eachindex(ind2010["patch"])
    push!(prows[parse(Int, ind2010["patch"][r])], r)
end
vv(r, k) = parse(Float64, ind2010[k][r])
pft_intc(typ) = typ <= 3 ? 0.02 : (typ <= 6 ? 0.06 : 0.01)
function pft_albedo(typ)
    typ == 1 && return (0.04, 0.1, 0.1); typ in (2, 3) && return (0.04, 0.1, 0.4)
    typ in (4, 5) && return (0.1, 0.1, 0.15); typ == 6 && return (0.05, 0.01, 0.15); return (0.15, 0.1, 0.4)
end
# grass gets REAL leaf/root from agb/vegc (grass_treepools convention) so maint. respiration is real
function mkind(r)
    typ = parse(Int, ind2010["type"][r]); isg = typ >= 7; sla = vv(r, "sla"); (ast, alt, scf) = pft_albedo(typ)
    croot = vv(r, "root_c"); nind = vv(r, "nind"); csap = vv(r, "sapwood_c")
    if isg
        g = grass_treepools(vv(r, "agb"), vv(r, "vegc"), sla); croot = g.root_c; nind = 1.0; csap = 0.0
    end
    return Individual{Float64}(
        vv(r, "fpar_leafon"), vv(r, "fpc_ind"), vv(r, "alphaa"), vv(r, "albedo_leaf"), vv(r, "emax"),
        csap, croot, vv(r, "lai"), pft_intc(typ), ast, alt, scf, nind,
        FDiff.PhotoParams{Float64}(; path = :c3, issla = true, sla = sla),
        FDiff.TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), isg
    )
end

# ── FINDING 1 — per-year grass NPP is FAITHFUL at the C's fixed structure ───────────────
totC = 0.0; totF = 0.0
for pnum in patches
    rows = prows[pnum]; inds = [mkind(r) for r in rows]; pids = [parse(Int, ind2010["type"][r]) for r in rows]
    st0 = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
    (_, days) = rollout_daily_canopy(tebs_params(), st0, inds, soil, forc2010; pft_ids = pids)
    ann = zeros(length(rows))
    for d in days, i in eachindex(rows)
        ann[i] += d.npp_ind[i]
    end
    for (k, r) in enumerate(rows)
        if parse(Int, ind2010["type"][r]) >= 7
            global totC += vv(r, "gpp_ind"); global totF += ann[k]   # ind-CSV gpp_ind == C NPP (extract_fdiff_individuals.py:26)
        end
    end
end
ratio1 = totF / totC

# ── FINDING 2 — grass GPP uses gp_stand; per-PFT would DE-calibrate it ───────────────────
# mirror daily_step_canopy pass-1 (gp_stand) + pass-2 grass gc/GPP; advance the REAL state
# with daily_step_canopy so the (moist) soil trajectory is exact.
p = tebs_params(); w = p.water
ratios_gc = Float64[]; ratios_own = Float64[]; ratios_gpp = Float64[]
for pnum in patches
    rows = prows[pnum]; inds = [mkind(r) for r in rows]; pids = [parse(Int, ind2010["type"][r]) for r in rows]
    uids = unique(pids); slot = Dict(id => k for (k, id) in enumerate(uids))
    pp = PhenParams{Float64}[pft_phenparams(id, Float64) for id in uids]
    ps = PhenState{Float64}[PhenState{Float64}() for _ in uids]; isg = Bool[_pft_is_grass(id) for id in uids]
    st = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0); wav = 1.0; glf = 1.0
    for fdc in forc2010
        phslot = _step_pft_phen_day!(ps, pp, isg, fdc.temp, fdc.swdown, wav, fdc.temp, glf)
        phen = Float64[phslot[slot[id]] for id in pids]
        beta = patch_albedo(inds, phen, st.snowpack)
        eeq = priestley_taylor_eeq(w, fdc.swdown, fdc.lwnet, fdc.temp, fdc.daylength, beta)
        frac_rain = sigmoid(w.βsnow * (fdc.temp - w.tsnow)); rain = frac_rain * fdc.precip
        snowfall = (1 - frac_rain) * fdc.precip
        melt = smoothmin(w.melt_factor * softplus(fdc.temp - w.tsnow, w.βmelt), st.snowpack + snowfall, w.βmelt)
        interc = 0.0
        for (ii, iv) in enumerate(inds)
            (_, ic) = _wet_interc(iv.intc, iv.lai, _phen_at(phen, ii), iv.fpc, eeq, rain, w.α_PT); interc += ic
        end
        interc = smoothmin(interc, rain, w.βw); infil = rain + melt - interc
        (w1, _) = _infiltrate(st.w, soil.whcs, infil, w.βw)
        wr = 0.0; for l in eachindex(w1)
            wr += soil.rootdist[l] * (w1[l] / soil.whcs[l])
        end
        par = 0.5 * w.dayseconds * fdc.swdown; co2_Pa = ppm2Pa(fdc.co2); dl = fdc.daylength
        condfac = ppm2bar(fdc.co2) * (1 - w.lambda_opt) * hour2sec(dl)
        gp_acc = 0.0; fpc_tot = 0.0; gp_own = zeros(length(inds))
        for (ii, iv) in enumerate(inds)
            phi = _phen_at(phen, ii); fpc_i = iv.fpc * phi
            apar_gp = par * (1 - iv.albedo_leaf) * iv.alphaa * fpc_i
            tsi = temp_stress(iv.tstress, fdc.temp, dl)
            (_, _, _, adtmm) = photosynthesis(iv.photo, w.lambda_opt, tsi, co2_Pa, fdc.temp, apar_gp, dl; comp_vm = true)
            gp_i = 1.6 * adtmm / condfac + w.gmin * fpc_i; gp_own[ii] = gp_i; gp_acc += gp_i; fpc_tot += fpc_i
        end
        gp_stand = fpc_tot > 1.0e-20 ? gp_acc / fpc_tot : 0.0
        for (ii, iv) in enumerate(inds)
            (iv.is_grass && _phen_at(phen, ii) > 0.3 && gp_stand > 1.0e-6) || continue
            phi = _phen_at(phen, ii); fpc_i = iv.fpc * phi; fpar_i = iv.fpar * phi
            apar = par * (1 - iv.albedo_leaf) * iv.alphaa * fpar_i
            tsi = temp_stress(iv.tstress, fdc.temp, dl)
            (_, _, vm, _) = photosynthesis(iv.photo, w.lambda_opt, tsi, co2_Pa, fdc.temp, apar, dl; comp_vm = true)
            supply_i = iv.emax * wr * phi
            (wet_i, _) = _wet_interc(iv.intc, iv.lai, phi, iv.fpc, eeq, rain, w.α_PT); wet_dem = smoothmin(wet_i, 0.99, w.βw)
            grass_gpp = function (gp_pot)
                (gc, _) = canopy_conductance(w, eeq, gp_pot, supply_i; wet = wet_dem)
                gpd = softplus(hour2sec(dl) * (gc * fpc_i - w.gmin * fpar_i), w.βflux)
                fac = gpd / 1.6 * ppm2bar(fdc.co2)
                p_i = FDiffParams{Float64}(iv.photo, iv.tstress, w, p.resp, p.allom, p.nlambda, p.ω)
                λ = clamp(solve_lambda(p_i, fac, tsi, co2_Pa, fdc.temp, apar, dl, vm), _LAMBDA_LO, _LAMBDA_HI)
                (agd, _, _, _) = photosynthesis(iv.photo, λ, tsi, co2_Pa, fdc.temp, apar, dl; comp_vm = false, vm = vm)
                return (gc, softplus(agd, w.βflux))
            end
            (gcs, gps) = grass_gpp(gp_stand); (_, gpp) = grass_gpp(gp_own[ii])
            push!(ratios_gc, gcs / gp_stand); push!(ratios_own, gp_own[ii] / gp_stand)
            gps > 1.0e-9 && push!(ratios_gpp, abs(gpp - gps) / gps)
        end
        (st, fl) = daily_step_canopy(p, inds, soil, st, fdc; phen = phen); wav = fl.wscal
        absorbed = 0.0; for (ii, iv) in enumerate(inds)
            iv.is_grass || (absorbed += iv.fpar * _phen_at(phen, ii))
        end
        glf = clamp(1 - absorbed, 0.0, 1.0)
    end
end
mean_gc = _mean(ratios_gc); mean_own = _mean(ratios_own); mean_pp = _mean(ratios_gpp)

# ── FINDING 3 — self-driven grass over-grows without cover competition ───────────────────
ind2008 = readcsv(joinpath(REFDIR, "hainich_individuals_2008.csv"))
fdec = readcsv(joinpath(REFDIR, "hainich_decadal_forcing.csv"))
fyear = Int.(round.(fcol(fdec, "year"))); syears = sort(unique(fyear))
yearly = [
    [
            DailyForcing{Float64}(
                swdown = fcol(fdec, "swdown")[i], lwnet = fcol(fdec, "lwnet")[i], temp = fcol(fdec, "temp")[i],
                precip = fcol(fdec, "precip")[i], daylength = fcol(fdec, "daylength")[i], co2 = fcol(fdec, "co2")[i]
            ) for i in findall(==(yr), fyear)
        ]
        for yr in syears
]
vv8(r, k) = parse(Float64, ind2008[k][r])
p0 = [r for r in eachindex(ind2008["type"]) if parse(Int, ind2008["patch"][r]) == 0 && parse(Int, ind2008["type"][r]) <= 6 && vv8(r, "height") > 0]
mkpool(r) = TreePools{Float64}(vv8(r, "leaf_c"), vv8(r, "sapwood_c"), vv8(r, "heartwood_c"), vv8(r, "root_c"), vv8(r, "height"), vv8(r, "crownarea"), vv8(r, "nind"), vv8(r, "sla"), vv8(r, "wooddens"), false)
mktmpl_t(r) = Individual{Float64}(vv8(r, "fpar_leafon"), 0.0, vv8(r, "alphaa"), vv8(r, "albedo_leaf"), vv8(r, "emax"), vv8(r, "sapwood_c"), vv8(r, "root_c"), 0.0, 0.02, 0.04, 0.1, 0.4, vv8(r, "nind"), FDiff.PhotoParams{Float64}(; path = :c3, issla = true, sla = vv8(r, "sla")), FDiff.TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false)
mktmpl_g() = Individual{Float64}(0.03, 1.0, 0.5, 0.15, 10.0, 0.0, 0.0, 0.0, 0.01, 0.15, 0.1, 0.4, 1.0, FDiff.PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.042242), FDiff.TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), true)
allom = Allometry.TreeAllometry{Float64}(); alloc = tebs_allocparams(); phys = tebs_params()
trees0 = vcat([mkpool(r) for r in p0], [grass_treepools(6.406, 6.406 + 8.023, 0.042242)])
tmpls = vcat([mktmpl_t(r) for r in p0], [mktmpl_g()])
gidx = length(trees0)
st0 = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
(_, _, pools_by_year, _) = rollout_canopy_years(phys, alloc, allom, st0, trees0, tmpls, soil, yearly)
leaf0 = trees0[gidx].leaf_c; leafN = pools_by_year[end][gidx].leaf_c
growth = leafN / leaf0

# ── report + assert ─────────────────────────────────────────────────────────────────────
println("==================== GRASS-OVERSHOOT RE-DIAGNOSIS (§22) ====================")
println("FINDING 1 — per-year grass NPP at the C's fixed structure:")
println("   total F_diff grass NPP / C grass NPP = ", round(ratio1, digits = 3), "   (faithful; a mild UNDERshoot — NOT a 3x overshoot)")
println("FINDING 2 — grass GPP uses the STAND MEAN (like the C):")
println("   mean gc_grass / gp_stand          = ", round(mean_gc, digits = 3), "   (grass uses most of the stand mean; moist soil)")
println("   mean gp_grass_own / gp_stand      = ", round(mean_own, digits = 3), "   (the grass's own potential gp is small)")
println("   mean |gpp_perPFT - gpp| / gpp     = ", round(mean_pp, digits = 3), "   (per-PFT conductance would DE-calibrate the grass GPP)")
println("FINDING 3 — self-driven grass over-grows without cover competition:")
println("   grass leaf ", round(leaf0, digits = 2), " -> ", round(leafN, digits = 2), " over ", length(syears), " yr  (x", round(growth, digits = 1), ")")
println("============================================================================")

@assert 0.6 <= ratio1 <= 1.3 "FINDING 1 failed: grass NPP ratio $(ratio1) outside [0.6,1.3]"
@assert mean_gc > 0.5 "FINDING 2 failed: grass uses gp_stand — mean gc/gp_stand=$(mean_gc) should be > 0.5"
@assert mean_own < 0.25 "FINDING 2 failed: grass own gp fraction $(mean_own) should be < 0.25"
@assert mean_pp > 0.2 "FINDING 2 failed: per-PFT delta $(mean_pp) should be > 0.2 (a real de-calibration)"
@assert growth > 2.0 "FINDING 3 failed: self-driven grass leaf growth x$(growth) should be > 2"
println("ALL THREE FINDINGS REPRODUCED + ASSERTED ✓")
