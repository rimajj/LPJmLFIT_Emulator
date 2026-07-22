# =============================================================================
# sapwood_bg_quantification_probe.jl — QUANTIFY the tree-CUE decrement of adding the C's below-ground
# root-sapwood pool `sapwood_bg` + its phen-gated maintenance, and give a GO / NO-GO on the invasive
# `TreePools`/`Individual` struct change (the sapwood_bg frontier, docs/sapwood_bg_design.md §7).
#
# QUESTION. F_diff's tree CUE (NPP/GPP) sits ~0.51 vs the C's ~0.46 (docs §13). The design hypothesis:
# F_diff omits the C's below-ground root-sapwood pool `sapwood_bg`, so it never pays that pool's
# phen-gated maintenance respiration (`npp_tree.c:51`). Adding it moves CUE DOWN toward 0.46 — but the
# decrement magnitude is UNQUANTIFIED, and an over-large pool would push CUE below the `multi_individual`
# gate floor 0.42 (`test/testitems/multi_individual_tests.jl:153`, `0.42 <= sum(np)/sum(gpp) <= 0.56`).
# GO only if the predicted CUE lands ~0.46 COMFORTABLY inside [0.42, 0.56].
#
# METHOD (reuse the VALIDATED F_diff kernels; add only the new maintenance term analytically — no src edit).
#  0. Baseline (replicate the CUE gate EXACTLY): build `Individual`s from hainich_individuals_2010.csv via
#     the gate's `mkind`, run `rollout_daily_canopy` (NO pft_ids → patch-wide beech GSI phen, whole-stand),
#     accumulate the cell-mean annual GPP + NPP → the baseline CUE the gate actually measures (~0.51).
#  1. Reconstruct `sapwood_bg_0` per TREE (type<7) from the C_LATERAL demand (allocation_tree.c:163,179-180):
#       sap_xs_area = sapwood_c / wooddens / height
#       root_sapwood_layer = Σ_l (soildepth[l]/1000)·sap_xs_area·root_sum_l·wooddens                (vertical)
#                          + (soildepth[l]/1000)·sap_xs_area·rootdist[l]·wooddens·(2π/C_LATERAL²)    (lateral)
#     with C_LATERAL=0.900 (lateral factor 2π/0.81≈7.757), root_sum_l = cumulative root fraction from layer l
#     down (decremented by rootdist[l] each layer, floored at 0), using the committed Hainich rootdist +
#     soildepth (layer thicknesses). This is the value the C SEEDS the pool at (design §4.1).
#  2. ΔRa_bg: the ADDITIONAL annual maintenance the pool would respire, integrated over the SAME phen &
#     gtemp trajectory F_diff used in step 0 — for each patch reconstruct the patch-wide beech GSI phen from
#     the rollout's own lag-1 `wscal`, and gtemp from air temp EXACTLY as `autotrophic_respiration`
#     (fdiff.jl:544-549; F_diff proxies gtemp_soil by gtemp_air — see the flag below):
#       ΔRa_bg = Σ_days respcoeff·k·gtemp_d·phen_d · (Σ_trees c_sapwood_bg,i·nind_i) / cn_sapwood   (per m²)
#  3. Predicted CUE. The design's simple subtraction (headline, CONSERVATIVE — overstates the drop):
#       CUE_new = (NPP_base − ΔRa_bg) / GPP_base
#     Refinement (growth-resp rebate): BOTH the C (`npp_tree.c:52` `(assim−mresp)·(1−r_growth)`) and F_diff
#     (`fdiff.jl:554`) apply growth respiration only to POSITIVE net carbon, so on the phen>0 (growing-season,
#     carbon-positive) days when the sapwood_bg term actually fires, the marginal NPP cost of extra
#     maintenance is (1−r_growth). So the REALISTIC decrement is (1−r_growth)·ΔRa_bg (a smaller drop).
#  4. Sensitivity: report the pool size (per-m² and as a fraction of aboveground sapwood_c) and the CUE at
#     ±30% pool (the seed-magnitude risk, design §4.2), and the ~4% post-turnover-sapwood variant (§4.5).
#
# INTERPRETATION / GO-NO-GO. GO if the predicted CUE (design formula AND its ±30% band) stays inside
# [0.42, 0.56] with margin and moves toward 0.46. NO-GO if the drop overshoots the 0.42 floor (seed too
# large → breaks the gate) or is inert (≈0 movement → the struct change buys nothing).
#
#   run (lightweight — login node OK; ~1-2 min Julia compile):
#     JULIA_DEPOT_PATH=$HOME/.julia \
#       /p/system/packages_rhel9/tools/julia/1.10.0/bin/julia --project=. scripts/sapwood_bg_quantification_probe.jl
# =============================================================================
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
import LPJmLFITEmulator.FDiff: tebs_params, tebs_phenparams, hainich_soilcolumn, rollout_daily_canopy,
    phenology_gsi_step, PhenState, PhotoParams, TempStressParams, Individual, FDiffStateML, DailyForcing

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
const C_LATERAL = 0.9                       # allocation_tree.c:113
const LATERAL_FACTOR = 2π / (C_LATERAL^2)      # ≈ 7.757 (allocation_tree.c:180: 2*M_PI/(C_LATERAL*C_LATERAL))

# ── committed-CSV readers (identical to the gate + grass probe) ──────────────────────────────────
function readcsv(path)
    lines = readlines(path)
    i = findfirst(l -> !startswith(strip(l), "#") && !isempty(strip(l)), lines)
    hdr = split(strip(lines[i]), ',')
    rows = [split(strip(l), ',') for l in lines[(i + 1):end] if !isempty(strip(l))]
    return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
end
function readtable(path)             # soilcolumn: (soildepth_mm, whcs_mm, rootdist)
    D = Float64[]; W = Float64[]; R = Float64[]
    for ln in eachline(path)
        s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
        v = parse.(Float64, split(s)); push!(D, v[2]); push!(W, v[3]); push!(R, v[4])
    end
    return (D, W, R)
end
fcol(d, k) = parse.(Float64, d[k])

# ── load committed Hainich 2010 structure + forcing + soil (the CUE-gate data set) ───────────────
f = readcsv(joinpath(REFDIR, "hainich_forcing_2010.csv"))
ind = readcsv(joinpath(REFDIR, "hainich_individuals_2010.csv"))
(soildepth, whcs, rootdist) = readtable(joinpath(REFDIR, "hainich_soilcolumn.txt"))
soil = hainich_soilcolumn(; whcs = whcs, rootdist = rootdist, soildepth = soildepth)
n = length(f["doy"])
@assert n == 365 "expected 365 daily forcing rows, got $n"
@assert length(ind["patch"]) == 297 "expected 297 committed individuals, got $(length(ind["patch"]))"

forc = [
    DailyForcing{Float64}(
            swdown = fcol(f, "swdown")[i], lwnet = fcol(f, "lwnet")[i], temp = fcol(f, "temp")[i],
            precip = fcol(f, "precip")[i], daylength = fcol(f, "daylength")[i], co2 = fcol(f, "co2")[i],
        ) for i in 1:n
]

# ── build Individuals EXACTLY as multi_individual_tests.jl `mkind` (the CUE gate) ────────────────
pft_intc(typ) = typ <= 3 ? 0.02 : (typ <= 6 ? 0.06 : 0.01)
function pft_albedo(typ)
    typ == 1 && return (0.04, 0.1, 0.1)
    typ in (2, 3) && return (0.04, 0.1, 0.4)
    typ in (4, 5) && return (0.1, 0.1, 0.15)
    typ == 6 && return (0.05, 0.01, 0.15)
    return (0.15, 0.1, 0.4)
end
function mkind(r)
    sla = parse(Float64, ind["sla"][r]); typ = parse(Int, ind["type"][r])
    (ast, alt, scf) = pft_albedo(typ)
    return Individual{Float64}(
        parse(Float64, ind["fpar_leafon"][r]), parse(Float64, ind["fpc_ind"][r]),
        parse(Float64, ind["alphaa"][r]), parse(Float64, ind["albedo_leaf"][r]), parse(Float64, ind["emax"][r]),
        parse(Float64, ind["sapwood_c"][r]), parse(Float64, ind["root_c"][r]),
        parse(Float64, ind["lai"][r]), pft_intc(typ), ast, alt, scf, parse(Float64, ind["nind"][r]),
        PhotoParams{Float64}(; path = :c3, issla = true, sla = sla),
        TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0),
        typ >= 7,
    )
end

patches = sort(unique(parse.(Int, ind["patch"])))
prows = Dict(p => Int[] for p in patches)
for r in eachindex(ind["patch"])
    push!(prows[parse(Int, ind["patch"][r])], r)
end
npatch = length(patches)

# ── the C_LATERAL below-ground sapwood demand (allocation_tree.c:163-189) ────────────────────────
# root_sapwood_layer at the given sap_xs_area = the value the C seeds `sapwood_bg` at (design §4.1).
function sapwood_bg_demand(sapwood_c, height, wooddens)
    (height <= 0 || wooddens <= 0) && return 0.0
    sap_xs_area = sapwood_c / wooddens / height
    sap_xs_area < 0 && (sap_xs_area = 0.0)                # allocation_tree.c:170-171
    root_sum = sum(rootdist)                              # allocation_tree.c:165-167 (Σ rootdist_n)
    rsl = 0.0
    for l in eachindex(rootdist)
        dz = soildepth[l] / 1000                          # mm → m (layer thickness)
        rsl += dz * sap_xs_area * root_sum * wooddens                       # vertical (line 179)
        rsl += dz * sap_xs_area * rootdist[l] * wooddens * LATERAL_FACTOR    # lateral  (line 180)
        root_sum -= rootdist[l]                            # line 186
        root_sum < 0 && (root_sum = 0.0)                   # line 187-188
    end
    return rsl
end

# ── gtemp EXACTLY as autotrophic_respiration (fdiff.jl:544-545); F_diff proxies gtemp_soil by gtemp_air ──
resp = tebs_params().resp        # respcoeff=1.2, k=0.0548, cn_sapwood=330, cn_root=30, e0, temp_response, r_growth=0.25
pp = tebs_phenparams()           # beech GSI (the gate's patch-wide phenology)
sig(x) = 1 / (1 + exp(-x))
gtemp_of(temp) = sig(10 * (temp + 40)) * exp(resp.e0 * (1 / (resp.temp_response + 10) - 1 / (temp + resp.temp_response)))
gtemp = [gtemp_of(forc[i].temp) for i in 1:n]

# ── per-patch: baseline rollout (reuse the kernel) + reconstruct phen & ΔRa_bg ───────────────────
function accumulate_cell()
    cell_gpp = 0.0; cell_npp = 0.0; cell_dRa = 0.0
    cell_bg_perm2 = 0.0; cell_sap_perm2 = 0.0
    sumgtphen_acc = 0.0            # cell-mean Σ_d gtemp_d·phen_d (diagnostic of the effective integrator)
    ntree = 0
    for p in patches
        rows = prows[p]
        inds = [mkind(r) for r in rows]
        st0 = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
        (_, days) = rollout_daily_canopy(tebs_params(), st0, inds, soil, forc)   # NO pft_ids → EXACTLY the gate
        gpp_p = sum(days[i].gpp for i in 1:n)
        npp_p = sum(days[i].npp for i in 1:n)

        # reproduce the patch-wide beech phen the rollout used: same GSI, lag-1 stand wscal (fdiff.jl:1709,1714)
        ps = PhenState{Float64}(); wav = 1.0
        sumgtphen = 0.0
        phen = zeros(n)
        for i in 1:n
            (ps, ph) = phenology_gsi_step(pp, ps, forc[i].temp, forc[i].swdown, wav, forc[i].temp)
            phen[i] = ph
            sumgtphen += gtemp[i] * ph
            wav = days[i].wscal
        end

        # patch below-ground sapwood (per m², patch basis) + aboveground sapwood (per m²)
        bg_perm2 = 0.0; sap_perm2 = 0.0
        for r in rows
            typ = parse(Int, ind["type"][r]); typ >= 7 && continue       # trees only (grass has no sapwood_bg)
            h = parse(Float64, ind["height"][r]); wd = parse(Float64, ind["wooddens"][r])
            sc = parse(Float64, ind["sapwood_c"][r]); ni = parse(Float64, ind["nind"][r])
            bg_perm2 += sapwood_bg_demand(sc, h, wd) * ni
            sap_perm2 += sc * ni
            ntree += 1
        end

        # ΔRa_bg (per m², annual): the phen-gated sapwood_bg maintenance the pool would add (npp_tree.c:51 form)
        dRa_p = 0.0
        for i in 1:n
            dRa_p += resp.respcoeff * resp.k * gtemp[i] * phen[i] * bg_perm2 / resp.cn_sapwood
        end

        cell_gpp += gpp_p / npatch
        cell_npp += npp_p / npatch
        cell_dRa += dRa_p / npatch
        cell_bg_perm2 += bg_perm2 / npatch
        cell_sap_perm2 += sap_perm2 / npatch
        sumgtphen_acc += sumgtphen / npatch
    end
    return (cell_gpp, cell_npp, cell_dRa, cell_bg_perm2, cell_sap_perm2, sumgtphen_acc, ntree / npatch)
end

println("running $npatch patches × $n days (baseline rollout, reusing rollout_daily_canopy) …")
(cell_gpp, cell_npp, cell_dRa, cell_bg_perm2, cell_sap_perm2, sumgtphen_acc, ntree_avg) = accumulate_cell()

# ── predictions ──────────────────────────────────────────────────────────────────────────────────
r_growth = resp.r_growth
CUE_base = cell_npp / cell_gpp
frac = cell_dRa / cell_gpp                                   # ΔRa_bg / GPP
CUE_design = (cell_npp - cell_dRa) / cell_gpp                # design formula (conservative)
CUE_real = (cell_npp - (1 - r_growth) * cell_dRa) / cell_gpp  # growth-resp-adjusted (realistic)
# ±30% pool sensitivity, on the (conservative) design formula — the floor-break risk lever
CUE_lo = (cell_npp - 1.3 * cell_dRa) / cell_gpp              # +30% pool → biggest drop
CUE_hi = (cell_npp - 0.7 * cell_dRa) / cell_gpp              # −30% pool → smallest drop
# post-turnover sapwood (×0.96) variant (§4.5): pool & ΔRa_bg scale by 0.96
CUE_design_pt = (cell_npp - 0.96 * cell_dRa) / cell_gpp
bg_frac_sap = cell_bg_perm2 / cell_sap_perm2

# ── report ─────────────────────────────────────────────────────────────────────────────────────
println()
println("================ sapwood_bg QUANTIFICATION PROBE — Hainich 42490, 2010 ================")
println("individuals            : $(length(ind["patch"])) across $npatch patches ($(round(ntree_avg, digits = 1)) trees/patch)")
println()
println("--- baseline flux (F_diff kernel, whole-stand, cell-mean; = the CUE gate basis) ---")
println("  GPP_base             : $(round(cell_gpp, digits = 1)) gC/m²/yr")
println("  NPP_base             : $(round(cell_npp, digits = 1)) gC/m²/yr")
println("  CUE_base = NPP/GPP   : $(round(CUE_base, digits = 4))   (design §13 quotes ~0.51)")
println()
println("--- reconstructed sapwood_bg pool (C_LATERAL demand, allocation_tree.c:163-189) ---")
println("  Σ sapwood_bg (bg)    : $(round(cell_bg_perm2, digits = 1)) gC/m²   (cell-mean, per-m² patch basis)")
println("  Σ sapwood_c  (ag)    : $(round(cell_sap_perm2, digits = 1)) gC/m²")
println("  bg / ag sapwood      : $(round(bg_frac_sap, digits = 3))   (lateral factor 2π/0.81 = $(round(LATERAL_FACTOR, digits = 3)))")
println("  Σ_d gtemp·phen (yr)  : $(round(sumgtphen_acc, digits = 1))   (cell-mean effective maintenance integrator)")
println()
println("--- additional phen-gated maintenance (npp_tree.c:51 sapwood_bg term) ---")
println("  ΔRa_bg               : $(round(cell_dRa, digits = 2)) gC/m²/yr")
println("  ΔRa_bg / GPP         : $(round(frac, digits = 4))")
println()
println("--- predicted CUE ---")
println("  CUE_new (design, ΔNPP = ΔRa_bg)            : $(round(CUE_design, digits = 4))   [headline, conservative]")
println("  CUE_new (growth-resp adj, ΔNPP=(1-rg)ΔRa) : $(round(CUE_real, digits = 4))   [realistic; rg=$(r_growth)]")
println("  CUE_new (post-turnover sapwood ×0.96)      : $(round(CUE_design_pt, digits = 4))")
println("  distance of CUE_new(design) to C's 0.46    : $(round(CUE_design - 0.46, digits = 4))")
println()
println("--- ±30% seed-magnitude sensitivity (on the conservative design formula) ---")
println("  +30% pool → CUE_new  : $(round(CUE_lo, digits = 4))")
println("  −30% pool → CUE_new  : $(round(CUE_hi, digits = 4))")
println()

# ── self-checking GO / NO-GO ─────────────────────────────────────────────────────────────────────
const GATE_LO = 0.42
const GATE_HI = 0.56
in_band(x) = GATE_LO <= x <= GATE_HI
moves_down = CUE_design < CUE_base
inert = frac < 0.005                                   # <0.5% of GPP ⇒ pool buys essentially nothing
overshoot = CUE_lo < GATE_LO                            # even the +30% worst case breaks the floor?
# GO requires: baseline in band, the drop is non-trivial, and BOTH the design CUE and its ±30% band stay in [0.42,0.56]
go = in_band(CUE_base) && moves_down && !inert && in_band(CUE_design) && in_band(CUE_lo) && in_band(CUE_hi)

println("================ DECISION ================")
println("  baseline CUE in [$(GATE_LO),$(GATE_HI)] : $(in_band(CUE_base))")
println("  moves toward 0.46 (down)         : $moves_down")
println("  non-inert (ΔRa/GPP ≥ 0.5%)       : $(!inert)")
println("  design CUE_new in-band           : $(in_band(CUE_design))")
println("  +30% worst-case in-band          : $(in_band(CUE_lo))  (overshoot floor: $overshoot)")
println("  −30% best-case  in-band          : $(in_band(CUE_hi))")
if go
    println("\n  >>> GO <<<  — adding sapwood_bg lowers CUE from $(round(CUE_base, digits = 3)) to ~$(round(CUE_real, digits = 3))–$(round(CUE_design, digits = 3)),")
    println("       toward the C's 0.46, and stays inside [$(GATE_LO),$(GATE_HI)] even at ±30% pool. The invasive")
    println("       struct change (docs §5) is justified; seed the pool from this C_LATERAL demand.")
else
    println("\n  >>> NO-GO / REVISIT <<< — predicted CUE fails a gate check above (overshoot below 0.42, inert,")
    println("       or baseline out of band). Revisit the seed/gate strategy before any src/ edit (docs §4.2).")
end
println("\nnote: gtemp_soil is proxied by gtemp_air (F_diff has no soil-thermal model, fdiff.jl:548); the C's")
println("      damped/lagged soil temperature would shift the true C decrement, but this predicts F_diff's CUE.")
println("      rootdist is the committed fixed Hainich column (design §4.4 simplification, not per-tree getrootdist).")
println("DONE.")
