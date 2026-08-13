# Regenerate the committed F_diff drift baselines + the multi-individual canopy baseline after the
# βvm Vcmax-cap-smoothing fix (see docs/notes/phase3_fdiff_cbinary_validation.md §9). Prints full-precision
# annual totals for test/testitems/references/{hainich_fdiff_baseline_2010, hainich_ml_baseline_2010,
# hainich_canopy_baseline_2010}.txt and the canopy validation metrics used in the gate assertions.
#   JULIA_DEPOT_PATH=$HOME/.julia julia --project=. scripts/regen_fdiff_baselines.jl
using LPJmLFITEmulator, LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams

const REF = joinpath(@__DIR__, "..", "test", "testitems", "references")
function rc(p)
    L = readlines(p); i = findfirst(l -> !startswith(strip(l), "#") && !isempty(strip(l)), L)
    h = split(strip(L[i]), ','); r = [split(strip(l), ',') for l in L[(i + 1):end] if !isempty(strip(l))]
    return Dict(h[j] => [x[j] for x in r] for j in eachindex(h))
end
fc(d, k) = parse.(Float64, d[k])
_mean(x) = sum(x) / length(x)
_corr(a, b) = (ma = _mean(a); mb = _mean(b); sum((a .- ma) .* (b .- mb)) / sqrt(sum((a .- ma) .^ 2) * sum((b .- mb) .^ 2)))

f = rc(joinpath(REF, "hainich_forcing_2010.csv"))
t = rc(joinpath(REF, "hainich_cbinary_targets_2010.csv"))
ind = rc(joinpath(REF, "hainich_individuals_2010.csv"))
n = length(fc(f, "doy"))
forc = [
    DailyForcing{Float64}(
            swdown = fc(f, "swdown")[i], lwnet = fc(f, "lwnet")[i], temp = fc(f, "temp")[i],
            precip = fc(f, "precip")[i], daylength = fc(f, "daylength")[i], co2 = fc(f, "co2")[i]
        ) for i in 1:n
]
fap = fc(t, "fapar_C")
sd = Float64[]; whcs = Float64[]; rd = Float64[]
for ln in eachline(joinpath(REF, "hainich_soilcolumn.txt"))
    s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
    v = parse.(Float64, split(s)); push!(sd, v[2]); push!(whcs, v[3]); push!(rd, v[4])
end
soil = hainich_soilcolumn(; whcs = whcs, rootdist = rd, soildepth = sd)
gs = [i for i in 1:n if 150 <= fc(f, "doy")[i] <= 240]

# 1) single-bucket (cbinary gate)
whc = maximum(fc(t, "rootmoist_C")); w0 = clamp(fc(t, "rootmoist_C")[1] / whc, 0.0, 1.0)
(_, d1) = rollout_daily(tebs_params(), FDiffState{Float64}(w = w0, snowpack = 0.0), tebs_structure(; whc = whc), forc; fapars = fap)
println("=== hainich_fdiff_baseline_2010.txt ===")
println("gpp_annual       ", sum(x.gpp for x in d1))
println("transp_annual    ", sum(x.transp for x in d1))
println("pet_annual       ", sum(x.eeq * 1.32 for x in d1))

# 2) multilayer (multilayer gate)
st0 = FDiffStateML{Float64}([0.95 * wc for wc in whcs], 0.0)
(_, d2) = rollout_daily_ml(tebs_params(), st0, tebs_structure(), soil, forc; fapars = fap)
println("\n=== hainich_ml_baseline_2010.txt ===")
println("gpp_annual        ", sum(x.gpp for x in d2))
println("transp_annual     ", sum(x.transp for x in d2))
println("evap_annual       ", sum(x.evap for x in d2))
println("rootmoist_mean    ", _mean([x.rootmoist for x in d2]))

# 3) multi-individual canopy (new gate): 25 patches averaged
fapar_peak = maximum(fap); phens = [clamp(x / fapar_peak, 0.0, 1.0) for x in fap]
patches = sort(unique(parse.(Int, ind["patch"])))
prows = Dict(p => Int[] for p in patches)
for r in eachindex(ind["patch"])
    push!(prows[parse(Int, ind["patch"][r])], r)
end
pft_intc(typ) = typ <= 3 ? 0.02 : (typ <= 6 ? 0.06 : 0.01)
function pft_albedo(typ)                       # (albedo_stem, albedo_litter, snowcanopyfrac), par/pft.js
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
        PhotoParams{Float64}(path = :c3, issla = true, sla = sla),
        TempStressParams{Float64}(temp_photos_low = 20.0, temp_photos_high = 30.0), typ >= 7
    )
end
# final config for the committed canopy baseline: STANDALONE (crutch-free) — self-computed GSI leaf
# phenology + self-computed dynamic-albedo eeq (§11). No phens/eeqs C-output drives.
#
# TWO ARMS, deliberately (step 3 of the default-flip procedure, `julia-test` skill): the tree
# photosynthesis demand-gate default flipped to ON in ADR 0133, so this block prints the ensemble on the
# package default AND on the explicit pre-0133 opt-out. The opt-out arm must reproduce the CURRENTLY
# COMMITTED `hainich_canopy_baseline_2010.txt` to its printed precision — that is what makes the new
# numbers a measured basis change rather than a re-record of whatever the new code emits.
#
# The THIRD arm, `gps = false`, was prepared IN ADVANCE of the `gp_stand_leafon_basis` flip and is now
# the live control for it (ADR 0137, 2026-08-13): the default has moved to `true`, so `a_gps0` must
# reproduce the PRE-FLIP committed `hainich_canopy_baseline_2010.txt` to its printed precision while
# `a_def` prints the new numbers. That reproduction in the SAME run is what makes this a measured basis
# change rather than a re-record of whatever the new code emits. Adding the opt-out only AFTER a flip is
# useless, because by then there is nothing left to reproduce — which is why it was written first.
# ⚠ `a_off` states `gps = true` explicitly: it means "the pre-0133 DEMAND GATE on the CURRENT basis", so
# it isolates one flag. Taking the new basis by omission would have made it a two-flag arm under a
# one-flag label (ADR 0133 §6 / ADR 0137).
function canopy_arm(gate; gps = nothing)
    p = tebs_params()
    if gate !== nothing || gps !== nothing
        w = p.water
        fns = fieldnames(typeof(w))
        nt = NamedTuple{fns}(map(f -> getfield(w, f), fns))
        kv = NamedTuple()
        gate === nothing || (kv = merge(kv, (; tree_demand_gate = gate)))
        gps === nothing || (kv = merge(kv, (; gp_stand_leafon_basis = gps)))
        w2 = typeof(w)(; merge(nt, kv)...)
        p = FDiffParams{Float64}(p.photo, p.tstress, w2, p.resp, p.allom, p.nlambda, p.ω)
    end
    gpp = zeros(n); tr = zeros(n); ev = zeros(n); ic = zeros(n); rm = zeros(n); fa = zeros(n)
    for pnum in patches
        inds = [mkind(r) for r in prows[pnum]]
        st = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
        (_, dd) = rollout_daily_canopy(p, st, inds, soil, forc)
        for i in 1:n
            gpp[i] += dd[i].gpp / length(patches); tr[i] += dd[i].transp / length(patches)
            ev[i] += dd[i].evap / length(patches); ic[i] += dd[i].interc / length(patches)
            rm[i] += dd[i].rootmoist / length(patches); fa[i] += dd[i].fapar / length(patches)
        end
    end
    return (gpp = gpp, tr = tr, ev = ev, ic = ic, rm = rm, fa = fa)
end
a_def = canopy_arm(nothing)                    # the package default = what the gate now runs
a_off = canopy_arm(false; gps = true)          # the pre-0133 demand-gate opt-out, on the CURRENT basis
a_gps0 = canopy_arm(nothing; gps = false)      # the pre-ADR-0137 gp_sum basis — must reproduce the committed file
gpp = a_def.gpp; tr = a_def.tr; ev = a_def.ev; ic = a_def.ic; rm = a_def.rm; fa = a_def.fa
println("\n=== hainich_canopy_baseline_2010.txt (PACKAGE DEFAULT — tree demand-gate ON, ADR 0133) ===")
println("gpp_annual        ", sum(gpp))
println("transp_annual     ", sum(tr))
println("evap_annual       ", sum(ev))
println("interc_annual     ", sum(ic))
println("rootmoist_mean    ", _mean(rm))
println("\n=== CONTROL ARM: tree_demand_gate = false (must reproduce the PRE-FLIP committed file) ===")
println("gpp_annual        ", sum(a_off.gpp))
println("transp_annual     ", sum(a_off.tr))
println("evap_annual       ", sum(a_off.ev))
println("interc_annual     ", sum(a_off.ic))
println("rootmoist_mean    ", _mean(a_off.rm))
println("\n=== CONTROL ARM: gp_stand_leafon_basis = false (must reproduce the PRE-ADR-0137 committed file) ===")
println("gpp_annual        ", sum(a_gps0.gpp))
println("transp_annual     ", sum(a_gps0.tr))
println("evap_annual       ", sum(a_gps0.ev))
println("interc_annual     ", sum(a_gps0.ic))
println("rootmoist_mean    ", _mean(a_gps0.rm))
println(
    "  (the default has moved (ADR 0137), so this arm must now reproduce the file committed BEFORE the ",
    "flip — it is no longer bitwise `a_def`, and that DIFFERENCE is what proves the opt-out is live)"
)
println("  bitwise == a_def: ", sum(a_gps0.gpp) === sum(gpp) && _mean(a_gps0.rm) === _mean(rm), "  (must now be false)")
println("\n=== gate effect on the committed quantities (default / off) ===")
for (k, x, y) in (
        ("gpp_annual", sum(gpp), sum(a_off.gpp)), ("transp_annual", sum(tr), sum(a_off.tr)),
        ("evap_annual", sum(ev), sum(a_off.ev)), ("interc_annual", sum(ic), sum(a_off.ic)),
        ("rootmoist_mean", _mean(rm), _mean(a_off.rm)),
    )
    println(rpad(k, 18), " ", x, "   ratio ", x / y)
end
gC = fc(t, "gpp_C"); trC = fc(t, "transp_C"); rmC = fc(t, "rootmoist_C")
println("\n=== canopy gate metrics ===")
println("GPP annual ratio  = ", sum(gpp) / sum(gC))
println("GPP fullyear r    = ", _corr(gpp, gC))
println("GPP GS r          = ", _corr(gpp[gs], gC[gs]))
println("transp annual rat = ", sum(tr) / sum(trC))
println("transp fullyear r = ", _corr(tr, trC))
println("transp GS r       = ", _corr(tr[gs], trC[gs]))
println("rootmoist GS r    = ", _corr(rm[gs], rmC[gs]))
println("rootmoist GS rat  = ", _mean(rm[gs]) / _mean(rmC[gs]))
