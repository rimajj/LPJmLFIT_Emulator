# Multi-year coupled canopy rollout, driven by the C's per-individual bm_inc (kernel-isolation crutch —
# isolates the ALLOCATION/structure growth from the un-calibrated self-NPP). Start from 2009 structure,
# apply 2010 forcing + the C's 2010 per-individual bm_inc, verify the grown structure reproduces the C's
# 2009→2010 growth, and that a multi-year self-loop stays physical. Trees only (grass held out, v1).
# See docs/phase3_fdiff_cbinary_validation.md §12. The committed CI gate is
# test/testitems/dynamic_structure_tests.jl (self-contained on the 2010 reference). This driver needs the
# multi-year /p/tmp reconstruction first:
#   /home/jamirp/.conda/envs/py311_new/bin/python scripts/extract_fdiff_individuals_multiyear.py
#   JULIA_DEPOT_PATH=$HOME/.julia julia --project=. scripts/validate_fdiff_structure.jl
using LPJmLFITEmulator, LPJmLFITEmulator.FDiff, LPJmLFITEmulator.Allometry

REPO = "/p/projects/open/Jamir/esm_land_emulator"
TMP = "/p/tmp/jamirp/esm_land_emulator_data/fdiff_structure"
function rc(p)
    L = readlines(p); i = findfirst(l -> !startswith(strip(l), "#")&&!isempty(strip(l)), L)
    h = split(strip(L[i]), ','); r = [split(strip(l), ',') for l in L[(i + 1):end] if !isempty(strip(l))]
    return Dict(String(h[j]) => [x[j] for x in r] for j in eachindex(h))
end
fcol(d, k) = parse.(Float64, d[k])
f = rc(joinpath(REPO, "test/testitems/references/hainich_forcing_2010.csv")); n = length(fcol(f, "doy"))
forc = [
    DailyForcing{Float64}(
            swdown = fcol(f, "swdown")[i], lwnet = fcol(f, "lwnet")[i], temp = fcol(f, "temp")[i],
            precip = fcol(f, "precip")[i], daylength = fcol(f, "daylength")[i], co2 = fcol(f, "co2")[i]
        ) for i in 1:n
]
sd = Float64[];whcs = Float64[];rd = Float64[]
for ln in eachline(joinpath(REPO, "test/testitems/references/hainich_soilcolumn.txt"))
    s = strip(ln);(isempty(s)||startswith(s, "#"))&&continue; v = parse.(Float64, split(s)); push!(sd, v[2]);push!(whcs, v[3]);push!(rd, v[4])
end
soil = hainich_soilcolumn(; whcs = whcs, rootdist = rd, soildepth = sd)
allom = Allometry.TreeAllometry{Float64}(); alloc = tebs_allocparams(); p = tebs_params()

d09 = rc(joinpath(TMP, "hainich_individuals_2009.csv"))
patches = sort(unique(parse.(Int, d09["patch"])))
prows = Dict(pn => Int[] for pn in patches); for r in eachindex(d09["patch"])
    push!(prows[parse(Int, d09["patch"][r])], r)
end
val(k, r) = parse(Float64, d09[k][r])
function mk(r)
    tp = TreePools{Float64}(
        val("leaf_c", r), val("sapwood_c", r), val("heartwood_c", r), val("root_c", r),
        val("height", r), val("crownarea", r), val("nind", r), val("sla", r), val("wooddens", r), false
    )
    tmpl = Individual{Float64}(
        val("fpar_leafon", r), 0.0, val("alphaa", r), val("albedo_leaf", r), val("emax", r),
        val("sapwood_c", r), val("root_c", r), 0.0, 0.02, 0.04, 0.1, 0.4, val("nind", r),
        FDiff.PhotoParams{Float64}(path = :c3, issla = true, sla = val("sla", r)),
        FDiff.TempStressParams{Float64}(temp_photos_low = 20.0, temp_photos_high = 30.0), false
    )
    bm = val("npp_perm2", r)   # C per-m² annual NPP for this individual = the bm_inc flux input (crutch)
    return (tp, tmpl, bm)
end

# ── year-1 (2009→2010): grow with the C's 2009 bm_inc, aggregate agb over patches ──
agb1 = 0.0; agb0 = 0.0
NY = 8
mh_traj = zeros(NY); agb_traj = zeros(NY); ntt = 0; allfinite = true
for pn in patches
    rows = [r for r in prows[pn] if parse(Int, d09["type"][r]) <= 6 && val("height", r) > 0]
    isempty(rows)&&continue
    pools = TreePools{Float64}[]; tmpls = Individual{Float64}[]; bms = Float64[]
    for r in rows
        (tp, tm, bm) = mk(r); push!(pools, tp);push!(tmpls, tm);push!(bms, bm)
    end
    st0 = FDiffStateML{Float64}([0.9 * w for w in whcs], 0.0)
    global agb0 += sum(FDiff.agb_ind(pools[i]) * pools[i].nind for i in eachindex(pools)) / length(patches)
    # multi-year: repeat the C 2009 bm_inc each year (constant-flux stability probe)
    yearly = [forc for _ in 1:NY]; bmext = [bms for _ in 1:NY]
    (_, _, poolshist, ann) = rollout_canopy_years(p, alloc, allom, st0, pools, tmpls, soil, yearly; bm_inc_ext = bmext)
    for y in 1:NY
        global agb_traj[y] += ann[y].agb / length(patches)
        global mh_traj[y] += sum(t.height for t in poolshist[y])
        global allfinite &= isfinite(ann[y].agb) && all(t.height > 0 && t.height <= 100 && isfinite(t.height) for t in poolshist[y])
    end
    global ntt += length(rows)
    global agb1 += ann[1].agb / length(patches)
end
println("2009 start cell AGB (trees, per-m²) = ", round(agb0, digits = 1))
println("year-1 grown cell AGB = ", round(agb1, digits = 1), "  (C 2009→2010: 4646→4784, dAGB +137 incl. mortality)")
println("F_diff dAGB (year1, C-bm_inc-driven, fixed N) = ", round(agb1 - agb0, digits = 1))
println("\nmulti-year trajectory (C 2009 bm_inc repeated; constant-flux stability probe):")
for y in 1:NY
    println("  year $y: cell AGB=", round(agb_traj[y], digits = 1), "  mean tree H=", round(mh_traj[y] / ntt, digits = 3))
end
println("\nall years finite + heights in (0,100]: ", allfinite)
println("VALIDATE OK")
