# Gate — DECADAL (11-year) fidelity of the coupled multi-year canopy rollout (scale-up step 10;
# docs/phase3_fdiff_cbinary_validation.md §21). §18 validated the cell × multi-year objective over a
# 3-year span (2009–2011); this extends the committed real reference to a full DECADE (2009–2019) and
# asks the fidelity-horizon question: starting from the 2008 reconstructed 25-patch structure and
# self-driving for 11 years (each patch grown across years by the pipe-model allocation, kernel-isolation
# C-FAPAR phenology), does F_diff's coupled rollout stay faithful to the C's OWN per-year annual GPP — or
# does the self-driven structure drift/blow up over a decade?
#
# The reference is committed + CI-runnable (scripts/extract_fdiff_decadal.py — no C re-run, sliced from
# the single-cell daily CSV already on disk): hainich_decadal_forcing.csv (per-year daily forcing 2009–19),
# hainich_decadal_targets.csv (per-year daily C GPP + FAPAR), + the already-committed 2008 start structure.
#
# DECISIVE checks (self-contained on the committed reference):
#  1. the rollout runs the full 11 years and stays PHYSICAL — every per-year cell GPP finite, positive,
#     and bounded (no runaway self-driven growth);
#  2. LEVEL — the mean cell-mean annual-GPP ratio vs the C stays near 1 over the decade (F_diff's known
#     ~+7 % level, the inherited GPP-phenology offset of §13/§19), each year bounded;
#  3. INTERANNUAL TRACKING — the per-year F_diff annual GPP correlates with the C's own year-to-year
#     variability (the coupled rollout responds to the real forcing, not just a flat mean).
@testitem "Decadal (2009–2019) coupled multi-year rollout tracks the C annual GPP (Hainich 42490)" tags = [:validation, :fdiff, :canopy, :structure, :multiyear] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams, rollout_canopy_years_gpp
    using LPJmLFITEmulator.Allometry
    using Test

    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = readlines(path)
        i = findfirst(l -> !startswith(strip(l), "#") && !isempty(strip(l)), lines)
        hdr = split(strip(lines[i]), ',')
        rows = [split(strip(l), ',') for l in lines[(i + 1):end] if !isempty(strip(l))]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end
    fcol(d, k) = parse.(Float64, d[k])

    ind = readcsv(joinpath(refdir, "hainich_individuals_2008.csv"))
    f = readcsv(joinpath(refdir, "hainich_decadal_forcing.csv"))
    t = readcsv(joinpath(refdir, "hainich_decadal_targets.csv"))
    sd = Float64[]; whcs = Float64[]; rdist = Float64[]
    for ln in eachline(joinpath(refdir, "hainich_soilcolumn.txt"))
        s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
        vv = parse.(Float64, split(s)); push!(sd, vv[2]); push!(whcs, vv[3]); push!(rdist, vv[4])
    end
    soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)

    sim_years = sort(unique(Int.(round.(fcol(f, "year")))))
    @test length(sim_years) == 11 && sim_years == collect(2009:2019)   # the committed decadal span

    # per-year daily forcing, kernel-isolation C-FAPAR phen drive, and the C per-year annual-GPP target
    fyear = Int.(round.(fcol(f, "year"))); tyear = Int.(round.(fcol(t, "year")))
    yearly_forcings = Vector{Vector{DailyForcing{Float64}}}(); phens_by_year = Vector{Vector{Float64}}(); targets = Float64[]
    for yr in sim_years
        fi = findall(==(yr), fyear); ti = findall(==(yr), tyear)
        push!(
            yearly_forcings, [
                DailyForcing{Float64}(
                        swdown = fcol(f, "swdown")[i], lwnet = fcol(f, "lwnet")[i], temp = fcol(f, "temp")[i],
                        precip = fcol(f, "precip")[i], daylength = fcol(f, "daylength")[i], co2 = fcol(f, "co2")[i],
                    ) for i in fi
            ]
        )
        fapar = fcol(t, "fapar_C")[ti]
        push!(phens_by_year, [clamp(x / maximum(fapar), 0.0, 1.0) for x in fapar])
        push!(targets, sum(fcol(t, "gpp_C")[ti]))
    end

    # 25 patch canopies (trees, height > 0) from the 2008 start structure
    ntyp(r) = parse(Int, ind["type"][r])
    treerows = [r for r in eachindex(ind["type"]) if ntyp(r) <= 6 && parse(Float64, ind["height"][r]) > 0]
    prows = Dict{Int, Vector{Int}}()
    for r in treerows
        push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
    end
    patches = sort(collect(keys(prows)))
    @test length(patches) == 25
    vv(r, k) = parse(Float64, ind[k][r])
    mkpool(r) = TreePools{Float64}(vv(r, "leaf_c"), vv(r, "sapwood_c"), vv(r, "heartwood_c"), vv(r, "root_c"), vv(r, "height"), vv(r, "crownarea"), vv(r, "nind"), vv(r, "sla"), vv(r, "wooddens"), false)
    mktmpl(r) = Individual{Float64}(vv(r, "fpar_leafon"), 0.0, vv(r, "alphaa"), vv(r, "albedo_leaf"), vv(r, "emax"), vv(r, "sapwood_c"), vv(r, "root_c"), 0.0, 0.02, 0.04, 0.1, 0.4, vv(r, "nind"), PhotoParams{Float64}(; path = :c3, issla = true, sla = vv(r, "sla")), TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false)
    trees0_all = [[mkpool(r) for r in prows[pn]] for pn in patches]
    tmpls_all = [[mktmpl(r) for r in prows[pn]] for pn in patches]

    allom = Allometry.TreeAllometry{Float64}(); alloc = tebs_allocparams(); phys = tebs_params()
    st0 = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
    NY = length(sim_years); P = length(patches)

    # cell-mean per-year annual GPP over the decade (self-driven structure, C-FAPAR phen)
    gc = zeros(NY)
    for p in 1:P
        g = rollout_canopy_years_gpp(phys, alloc, allom, st0, trees0_all[p], tmpls_all[p], soil, yearly_forcings; phens_by_year = phens_by_year)
        gc .+= g ./ P
    end

    # ── 1. PHYSICAL — 11 finite, positive, bounded per-year cell GPP (no runaway self-driven growth) ──
    @test length(gc) == 11
    @test all(isfinite, gc) && all(gc .> 0)
    @test all(600.0 .< gc .< 2000.0)                       # physically bounded temperate-forest GPP (no blow-up)

    ratios = gc ./ targets
    # ── 2. LEVEL — mean annual-GPP ratio near 1 over the decade; each year bounded ──
    meanratio = sum(ratios) / NY
    @test 1.0 ≤ meanratio ≤ 1.12                           # F_diff's inherited ~+7 % GPP-phenology level (§13/§19)
    @test all(0.9 .< ratios .< 1.2)                        # bounded every year (no drift blow-up)

    # ── 3. INTERANNUAL TRACKING — F_diff follows the C's year-to-year variability ──
    _mean(x) = sum(x) / length(x)
    _corr(a, b) = (ma = _mean(a); mb = _mean(b); sum((a .- ma) .* (b .- mb)) / sqrt(sum((a .- ma) .^ 2) * sum((b .- mb) .^ 2)))
    r = _corr(gc, targets)
    @test r > 0.7                                          # coupled rollout responds to the real forcing (measured 0.86)
end
