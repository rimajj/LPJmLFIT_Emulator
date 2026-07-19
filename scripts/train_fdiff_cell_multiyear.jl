# =============================================================================
# train_fdiff_cell_multiyear.jl — train the learned canopy Vcmax/λ correction so
# the CELL-mean PER-YEAR annual GPP matches the LPJmL-FIT C binary's OWN per-year
# annual GPP, over the full 25-patch Hainich cell (42490), with EVERY patch grown
# across years THROUGH the structure/allocation feedback.
# (Phase-3 scale-up step 7b-cell-multiyear; ADR 0016; docs §18.)
#
# This is the composition of the two proven objectives:
#   • §16 (train_fdiff_canopy_cell.jl): the C GPP is a CELL-mean over the 25 patches,
#     so ONE shared learned correction is fit so the cell-mean matches the C, and the
#     cell-MSE gradient factors patch-by-patch (Gauss–Newton reweighting) — but with
#     the canopy STRUCTURE frozen at its 2010 value.
#   • §17 (train_fdiff_multiyear.jl): per-year annual GPP THROUGH the annual pipe-model
#     allocation (`grow_individual` regrows the pools between years) — but on ONE patch
#     against a DEMO target (2010 repeated).
# Here the objective is the cell-mean PER-YEAR annual GPP over SIM_YEARS vs the C's own
# per-year annual GPP, each of the 25 patches grown across years. Every reverse pass is
# the proven single-patch multi-year `rollout_canopy_years_gpp` Enzyme path (no
# monolithic multi-patch AD): train_fdiff_cell_multiyear_rollout!.
#
# REAL multi-year reference (committed, scripts/extract_fdiff_cell_multiyear.py):
#   * hainich_individuals_2008.csv     — start-year 25-patch reconstructed structure
#   * hainich_multiyear_forcing.csv    — per-year daily .clm forcing (2009/2010/2011)
#   * hainich_multiyear_targets.csv    — per-year daily C GPP + FAPAR (cell-mean)
# Start-of-year convention (dynamic-structure validation §12): the rollout starts from
# 2008's reconstructed structure and simulates the SUBSEQUENT years, so the structure
# entering each sim year is F_diff's own grown structure (the C annual-GPP trajectory is
# the target for that self-driven growth). Kernel isolation: the per-year daily leaf
# display is DRIVEN by that year's C FAPAR (phens = fapar_C / peak), isolating the
# Vcmax/λ level lever from phenology mismatch (the analog of §16 across years).
#
# Enzyme reverse ⇒ Julia 1.10 (lts). Run against the TEST environment (Lux/Zygote/
# Optimisers/Enzyme + the package dev'd in):
#   JULIA_DEPOT_PATH=$HOME/.julia julia --project=test -e 'import Pkg; Pkg.develop(path=".");  Pkg.instantiate()'
#   JULIA_DEPOT_PATH=$HOME/.julia julia --project=test scripts/train_fdiff_cell_multiyear.jl
# =============================================================================
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams, rollout_canopy_years_gpp
using LPJmLFITEmulator.Allometry
using Lux, Zygote, Optimisers, Enzyme, StableRNGs
using Printf

const REF = joinpath(@__DIR__, "..", "test", "testitems", "references")
const SIM_YEARS = [2009, 2010, 2011]

function read_csv(path)
    lines = readlines(path)
    i = findfirst(l -> !startswith(strip(l), "#") && !isempty(strip(l)), lines)
    hdr = split(strip(lines[i]), ',')
    rows = [split(strip(l), ',') for l in lines[(i + 1):end] if !isempty(strip(l))]
    data = Dict{String, Vector{String}}()
    for (j, name) in enumerate(hdr)
        data[name] = [r[j] for r in rows]
    end
    return data
end
fcol(d, k) = parse.(Float64, d[k])

function read_soilcolumn(path)
    D = Float64[]; W = Float64[]; R = Float64[]
    for ln in eachline(path)
        s = strip(ln)
        (isempty(s) || startswith(s, "#")) && continue
        v = parse.(Float64, split(s))
        push!(D, v[2]); push!(W, v[3]); push!(R, v[4])
    end
    return (D, W, R)
end

# per-individual prognostic pools from the C reconstruction (heartwood_c is reconstructed directly by
# extract_fdiff_individuals_multiyear.py: heart = agb/nind − leaf − sap; per dynamic_structure_tests.jl)
function make_treepools(ind, r)
    val(k) = parse(Float64, ind[k][r])
    return TreePools{Float64}(
        val("leaf_c"), val("sapwood_c"), val("heartwood_c"), val("root_c"),
        val("height"), val("crownarea"), val("nind"), val("sla"), val("wooddens"), false,
    )
end
# daily-Individual template (fpar/fpc/lai/sapwood/root are placeholders — `individual_from_pools`
# recomputes them from the grown pools each year; validate_fdiff_structure.jl idiom)
function make_template(ind, r)
    val(k) = parse(Float64, ind[k][r])
    return Individual{Float64}(
        val("fpar_leafon"), 0.0, val("alphaa"), val("albedo_leaf"), val("emax"), val("sapwood_c"),
        val("root_c"), 0.0, 0.02, 0.04, 0.1, 0.4, val("nind"),
        PhotoParams{Float64}(; path = :c3, issla = true, sla = val("sla")),
        TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false,
    )
end

# cell-mean per-year annual GPP for a set of hooks (identity by default) over all patches
function cell_gpp_years(phys, alloc, allom, st0, trees0_all, tmpls_all, soil, yearly_forcings, phens_by_year; hooks = FluxHooks())
    P = length(trees0_all); NY = length(yearly_forcings)
    gc = zeros(NY)
    for p in 1:P
        g = rollout_canopy_years_gpp(phys, alloc, allom, st0, trees0_all[p], tmpls_all[p], soil, yearly_forcings; phens_by_year = phens_by_year, hooks = hooks)
        gc .+= g ./ P
    end
    return gc
end

function main()
    ind = read_csv(joinpath(REF, "hainich_individuals_2008.csv"))
    f = read_csv(joinpath(REF, "hainich_multiyear_forcing.csv"))
    t = read_csv(joinpath(REF, "hainich_multiyear_targets.csv"))
    (soildepth, whcs, rootdist) = read_soilcolumn(joinpath(REF, "hainich_soilcolumn.txt"))
    soil = hainich_soilcolumn(; whcs = whcs, rootdist = rootdist, soildepth = soildepth)

    # per-year forcing, kernel-isolation phenology drive, and cell annual-GPP target
    fyear = parse.(Int, f["year"]); tyear = parse.(Int, t["year"])
    yearly_forcings = Vector{Vector{DailyForcing{Float64}}}()
    phens_by_year = Vector{Vector{Float64}}()
    targets_by_year = Float64[]
    for yr in SIM_YEARS
        fi = findall(==(yr), fyear); ti = findall(==(yr), tyear)
        forc = [
            DailyForcing{Float64}(
                    swdown = fcol(f, "swdown")[i], lwnet = fcol(f, "lwnet")[i], temp = fcol(f, "temp")[i],
                    precip = fcol(f, "precip")[i], daylength = fcol(f, "daylength")[i], co2 = fcol(f, "co2")[i],
                ) for i in fi
        ]
        fapar = fcol(t, "fapar_C")[ti]
        push!(yearly_forcings, forc)
        push!(phens_by_year, [clamp(x / maximum(fapar), 0.0, 1.0) for x in fapar])
        push!(targets_by_year, sum(fcol(t, "gpp_C")[ti]))
    end

    # build the 25 patch canopies (trees only, height > 0) from the 2008 start structure
    ntyp(r) = parse(Int, ind["type"][r])
    treerows = [r for r in eachindex(ind["type"]) if ntyp(r) <= 6 && parse(Float64, ind["height"][r]) > 0]
    prows = Dict{Int, Vector{Int}}()
    for r in treerows
        push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
    end
    patches = sort(collect(keys(prows)))
    trees0_all = [[make_treepools(ind, r) for r in prows[pn]] for pn in patches]
    tmpls_all = [[make_template(ind, r) for r in prows[pn]] for pn in patches]

    allom = Allometry.TreeAllometry{Float64}()
    alloc = tebs_allocparams()
    phys = tebs_params()
    st0 = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
    P = length(patches); NY = length(SIM_YEARS)

    @printf(
        "Hainich cell 42490 — %d patches, %d trees (2008 start structure); sim years %s\n",
        P, sum(length(v) for v in trees0_all), string(SIM_YEARS),
    )
    @printf("C per-year annual GPP target (cell-mean): %s gC/m²/yr\n\n", string(round.(targets_by_year; digits = 1)))

    # baseline (untrained = identity) cell-mean per-year annual GPP under the kernel-isolation phen drive
    g0 = cell_gpp_years(phys, alloc, allom, st0, trees0_all, tmpls_all, soil, yearly_forcings, phens_by_year)
    println("baseline (identity, phen=fapar_C drive) — cell-mean per-year GPP vs C target:")
    for y in 1:NY
        @printf("  %d: GPP %.1f  target %.1f  ratio %.3f\n", SIM_YEARS[y], g0[y], targets_by_year[y], g0[y] / targets_by_year[y])
    end

    function fit(targets; verbose = false)
        nn = build_fdiff_nn(; targets = targets, width = 12, depth = 2, corr_max = 0.6, rng = StableRNG(2026))
        (ps, hist) = train_fdiff_cell_multiyear_rollout!(
            nn, phys, alloc, allom, st0, trees0_all, tmpls_all, soil, yearly_forcings, phens_by_year, targets_by_year;
            epochs = 20, lr = 2.0e-2, ps = deepcopy(nn.ps), verbose = verbose,
        )
        vmh = (:vm in targets) ? neural_vm_hook(nn, ps) : nothing
        λh = (:λ in targets) ? neural_lambda_hook(nn, ps) : nothing
        g = cell_gpp_years(phys, alloc, allom, st0, trees0_all, tmpls_all, soil, yearly_forcings, phens_by_year; hooks = FluxHooks(vm = vmh, λ = λh))
        return (g = g, hist = hist)
    end

    println("\n── train (:vm,) — Vcmax lever, cell-mean per-year annual GPP vs C annual GPP ──")
    rvm = fit((:vm,); verbose = true)
    @printf("  loss %.4g → %.4g\n", rvm.hist[1], rvm.hist[end])
    for y in 1:NY
        @printf(
            "  %d: GPP %.1f → %.1f  (ratio %.3f → %.3f, target %.1f)\n",
            SIM_YEARS[y], g0[y], rvm.g[y], g0[y] / targets_by_year[y], rvm.g[y] / targets_by_year[y], targets_by_year[y]
        )
    end

    println("\n── train (:vm, :λ) — both levers ──")
    rvl = fit((:vm, :λ); verbose = true)
    @printf("  loss %.4g → %.4g\n", rvl.hist[1], rvl.hist[end])
    for y in 1:NY
        @printf(
            "  %d: GPP %.1f → %.1f  (ratio %.3f → %.3f, target %.1f)\n",
            SIM_YEARS[y], g0[y], rvl.g[y], g0[y] / targets_by_year[y], rvl.g[y] / targets_by_year[y], targets_by_year[y]
        )
    end

    @printf(
        "\ncell-mean annual-GPP ratio (mean over years): baseline %.3f → %.3f (:vm) → %.3f (:vm,:λ)\n",
        sum(g0 ./ targets_by_year) / NY, sum(rvm.g ./ targets_by_year) / NY, sum(rvl.g ./ targets_by_year) / NY,
    )
    println("The learned canopy Vcmax/λ correction closes the ANNUAL GPP LEVEL against the REAL C per-year")
    println("annual GPP THROUGH the multi-year structure/allocation feedback, over the full 25-patch cell")
    println("(docs §18, ADR 0016) — the cell × multi-year extension of §16 (cell) and §17 (multi-year).")
    return nothing
end

main()
