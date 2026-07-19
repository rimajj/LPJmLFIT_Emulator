# =============================================================================
# train_fdiff_multiyear.jl — train the learned Vcmax/λ correction against a
# MULTI-YEAR annual-GPP trajectory on a SINGLE Hainich patch, differentiating
# THROUGH the annual structure/allocation feedback.
# (Phase-3 scale-up step 7b-multiyear; ADR 0016; docs §17.)
#
# §15/§16 trained the correction against DAILY GPP with the canopy STRUCTURE held
# fixed for the year. This driver closes the outer loop: the objective is the
# per-year annual stand GPP over several years, and the gradient flows THROUGH the
# annual pipe-model allocation (`grow_individual` regrows the pools between years,
# the layered light is recomputed from the grown heights). The multi-year kernel
# `rollout_canopy_years_gpp` carries the evolving pool state as struct-of-arrays
# (plain Float64 vectors, not a `Vector{TreePools}` field-scatter) so Enzyme reverse
# can differentiate the whole multi-year chain (docs §17).
#
# SINGLE PATCH (the largest Hainich patch, reconstructed from
# test/testitems/references/hainich_individuals_2010.csv). The CELL multi-year
# objective (per-patch Gauss–Newton decomposition of the cell-mean annual GPP, as
# train_fdiff_cell_rollout! does within a year) is the noted next extension.
#
# Kernel isolation: the per-year daily leaf display is DRIVEN by the C binary's own
# daily FAPAR (phens = fapar_C / max fapar_C), so the correction closes the annual
# photosynthesis LEVEL given the C's leaf display — isolating the Vcmax/λ lever from
# phenology mismatch (the analog of the §16 cell fit).
#
# --- DEMO SCAFFOLD / TODOs (this driver has no committed multi-year reference yet) ---
#   * MULTI-YEAR FORCING: reuse the committed 2010 forcing repeated for NY years.
#     TODO: real per-year forcing comes from the multi-year reconstruction
#     (scripts/extract_fdiff_individuals_multiyear.py → /p/tmp .../fdiff_structure/
#     hainich_forcing_<year>.csv), the same source validate_fdiff_structure.jl uses.
#   * PER-YEAR ANNUAL-GPP TARGETS: from the C binary's own annual GPP. TODO: the
#     committed reference only has 2010 daily GPP; for the demo we repeat the 2010
#     annual value for every year. Replace with the real per-year C annual GPP
#     trajectory (and note the single-patch stand GPP vs the C's CELL-mean annual
#     GPP is a level mismatch — cell-multi-year targets are the next extension).
#
# Enzyme reverse ⇒ Julia 1.10 (lts). Run against the TEST environment (Lux/Zygote/
# Optimisers/Enzyme + the package dev'd in):
#   JULIA_DEPOT_PATH=$HOME/.julia julia --project=test -e 'import Pkg; Pkg.develop(path=".");  Pkg.instantiate()'
#   JULIA_DEPOT_PATH=$HOME/.julia julia --project=test scripts/train_fdiff_multiyear.jl
# =============================================================================
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams, rollout_canopy_years_gpp
using LPJmLFITEmulator.Allometry
using Lux, Zygote, Optimisers, Enzyme, StableRNGs
using Printf

const REF = joinpath(@__DIR__, "..", "test", "testitems", "references")
const NY = 5                       # demo: number of years (2010 forcing/target repeated — see TODOs)

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

# per-individual prognostic pools from the C reconstruction (heartwood from the per-m² agb:
# agb = (leaf+sap+heart)·nind, agb_tree.c:25 ⇒ heart = agb/nind − leaf − sap; dynamic_structure_tests.jl)
function make_treepools(ind, r)
    val(k) = parse(Float64, ind[k][r])
    nind = val("nind"); leaf = val("leaf_c"); sap = val("sapwood_c")
    heart = max(val("agb") / nind - leaf - sap, 0.0)
    return TreePools{Float64}(
        leaf, sap, heart, val("root_c"), val("height"), val("crownarea"),
        nind, val("sla"), val("wooddens"), false,
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

function main()
    ind = read_csv(joinpath(REF, "hainich_individuals_2010.csv"))
    f = read_csv(joinpath(REF, "hainich_forcing_2010.csv"))
    t = read_csv(joinpath(REF, "hainich_cbinary_targets_2010.csv"))
    (soildepth, whcs, rootdist) = read_soilcolumn(joinpath(REF, "hainich_soilcolumn.txt"))
    soil = hainich_soilcolumn(; whcs = whcs, rootdist = rootdist, soildepth = soildepth)

    doy = fcol(f, "doy"); n = length(doy)
    forc = [
        DailyForcing{Float64}(
                swdown = fcol(f, "swdown")[i], lwnet = fcol(f, "lwnet")[i], temp = fcol(f, "temp")[i],
                precip = fcol(f, "precip")[i], daylength = fcol(f, "daylength")[i], co2 = fcol(f, "co2")[i],
            ) for i in 1:n
    ]
    gpp_C = fcol(t, "gpp_C"); fapar_C = fcol(t, "fapar_C")
    phens_C = [clamp(x / maximum(fapar_C), 0.0, 1.0) for x in fapar_C]   # kernel-isolation phenology drive

    # ── single patch: the largest Hainich patch (trees only, height > 0) ──
    ntyp(r) = parse(Int, ind["type"][r])
    treerows = [r for r in eachindex(ind["type"]) if ntyp(r) <= 6 && parse(Float64, ind["height"][r]) > 0]
    prows = Dict{Int, Vector{Int}}()
    for r in treerows
        push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
    end
    pbig = argmax(Dict(k => length(v) for (k, v) in prows))
    rows = prows[pbig]
    trees0 = [make_treepools(ind, r) for r in rows]
    tmpls = [make_template(ind, r) for r in rows]

    allom = Allometry.TreeAllometry{Float64}()
    alloc = tebs_allocparams()
    phys = tebs_params()
    st0 = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)

    # multi-year drivers (2010 repeated — see TODOs): forcing, phenology, and the annual-GPP targets
    yearly_forcings = [forc for _ in 1:NY]
    phens_by_year = [phens_C for _ in 1:NY]
    annual_gpp_C = sum(gpp_C)                       # 2010 annual GPP (C binary, cell-mean daily summed)
    targets_by_year = fill(annual_gpp_C, NY)        # TODO: real per-year C annual GPP trajectory

    @printf(
        "Hainich patch %d — %d trees; C 2010 annual GPP target = %.1f gC/m²/yr (repeated NY=%d, demo)\n\n",
        pbig, length(rows), annual_gpp_C, NY,
    )

    # baseline (untrained = identity) per-year annual stand GPP under the kernel-isolation phenology drive
    g0 = rollout_canopy_years_gpp(phys, alloc, allom, st0, trees0, tmpls, soil, yearly_forcings; phens_by_year = phens_by_year)
    println("baseline (identity, phen=fapar_C drive) — per-year stand GPP vs target:")
    for y in 1:NY
        @printf("  year %d: GPP %.1f  target %.1f  ratio %.3f\n", y, g0[y], targets_by_year[y], g0[y] / targets_by_year[y])
    end

    function fit(targets; verbose = false)
        nn = build_fdiff_nn(; targets = targets, width = 12, depth = 2, corr_max = 0.6, rng = StableRNG(2026))
        (ps, hist) = train_fdiff_multiyear_rollout!(
            nn, phys, alloc, allom, st0, trees0, tmpls, soil, yearly_forcings, phens_by_year, targets_by_year;
            epochs = 20, lr = 2.0e-2, ps = deepcopy(nn.ps), verbose = verbose,
        )
        vmh = (:vm in targets) ? neural_vm_hook(nn, ps) : nothing
        λh = (:λ in targets) ? neural_lambda_hook(nn, ps) : nothing
        g = rollout_canopy_years_gpp(phys, alloc, allom, st0, trees0, tmpls, soil, yearly_forcings; phens_by_year = phens_by_year, hooks = FluxHooks(vm = vmh, λ = λh))
        return (g = g, hist = hist)
    end

    println("\n── train (:vm,) — Vcmax lever, per-year annual GPP vs C annual GPP (full-year forcing) ──")
    rvm = fit((:vm,); verbose = true)
    @printf("  loss %.4g → %.4g\n", rvm.hist[1], rvm.hist[end])
    for y in 1:NY
        @printf(
            "  year %d: GPP %.1f → %.1f  (ratio %.3f → %.3f, target %.1f)\n",
            y, g0[y], rvm.g[y], g0[y] / targets_by_year[y], rvm.g[y] / targets_by_year[y], targets_by_year[y]
        )
    end

    println("\n── train (:vm, :λ) — both levers ──")
    rvl = fit((:vm, :λ); verbose = true)
    @printf("  loss %.4g → %.4g\n", rvl.hist[1], rvl.hist[end])
    for y in 1:NY
        @printf(
            "  year %d: GPP %.1f → %.1f  (ratio %.3f → %.3f, target %.1f)\n",
            y, g0[y], rvl.g[y], g0[y] / targets_by_year[y], rvl.g[y] / targets_by_year[y], targets_by_year[y]
        )
    end

    println("\nThe learned correction closes the ANNUAL GPP LEVEL against the C target THROUGH the multi-year")
    println("structure/allocation feedback — the multi-year extension of the coupled-canopy lever (docs §17,")
    println("ADR 0016). Replace the repeated-2010 forcing/targets with the real multi-year reference (TODOs).")
    return nothing
end

main()
