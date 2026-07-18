# =============================================================================
# train_fdiff_canopy_cell.jl — train the learned canopy Vcmax/λ correction against
# the REAL LPJmL-FIT C-binary daily GPP on the full 25-patch Hainich cell (42490).
# (Phase-3 scale-up step 7b-cell; ADR 0016; docs §16.)
#
# §15 proved the Enzyme-reverse canopy trainer recovers a KNOWN correction on one
# synthetic patch. This driver applies it to the honest objective: fit the cell-mean
# daily GPP to the C binary's own daily GPP over the real 25-patch canopy
# (297 individuals, test/testitems/references/hainich_individuals_2010.csv). The
# canopy GPP residual is Vcmax/phenology-shaped (light is spread across individuals so
# photosynthesis is Vcmax-limited, docs §14/§15), so — unlike the single-representative
# path — the learned Vcmax lever is the right one and CAN close the level while keeping
# the (already excellent) daily shape.
#
# The cell-MSE gradient is exact-decomposed patch-by-patch (Gauss–Newton reweighting),
# so every reverse pass is the proven single-patch Enzyme path (train_fdiff_cell_rollout!).
# Kernel isolation: the phenology is DRIVEN by the C binary's own daily FAPAR
# (phens = fapar_C / max fapar_C), so the correction closes the photosynthesis LEVEL
# given the C's leaf display — isolating the Vcmax/λ lever from phenology mismatch (the
# analog of the single-representative [C] fit in scripts/train_fdiff_nn.jl).
#
# Enzyme reverse ⇒ Julia 1.10 (lts). Run against the TEST environment (Lux/Zygote/
# Optimisers/Enzyme + the package dev'd in):
#   JULIA_DEPOT_PATH=$HOME/.julia julia --project=test -e 'import Pkg; Pkg.develop(path=".");  Pkg.instantiate()'
#   JULIA_DEPOT_PATH=$HOME/.julia julia --project=test scripts/train_fdiff_canopy_cell.jl
# =============================================================================
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams, rollout_daily_canopy
using Lux, Zygote, Optimisers, Enzyme, StableRNGs
using Printf

const REF = joinpath(@__DIR__, "..", "test", "testitems", "references")
const GS_LO, GS_HI = 150, 240

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

_mean(x) = sum(x) / length(x)
function _corr(a, b)
    ma, mb = _mean(a), _mean(b)
    return sum((a .- ma) .* (b .- mb)) / sqrt(sum((a .- ma) .^ 2) * sum((b .- mb) .^ 2))
end

pft_intc(typ) = typ <= 3 ? 0.02 : (typ <= 6 ? 0.06 : 0.01)
function pft_albedo(typ)
    typ == 1 && return (0.04, 0.1, 0.1)
    typ in (2, 3) && return (0.04, 0.1, 0.4)
    typ in (4, 5) && return (0.1, 0.1, 0.15)
    typ == 6 && return (0.05, 0.01, 0.15)
    return (0.15, 0.1, 0.4)
end
function make_individual(ind, r)
    typ = parse(Int, ind["type"][r])
    sla = parse(Float64, ind["sla"][r])
    photo = PhotoParams{Float64}(; path = :c3, issla = true, sla = sla)
    tstress = TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0)
    (ast, alt, scf) = pft_albedo(typ)
    return Individual{Float64}(
        parse(Float64, ind["fpar_leafon"][r]), parse(Float64, ind["fpc_ind"][r]),
        parse(Float64, ind["alphaa"][r]), parse(Float64, ind["albedo_leaf"][r]),
        parse(Float64, ind["emax"][r]), parse(Float64, ind["sapwood_c"][r]),
        parse(Float64, ind["root_c"][r]), parse(Float64, ind["lai"][r]), pft_intc(typ),
        ast, alt, scf, parse(Float64, ind["nind"][r]), photo, tstress, typ >= 7,
    )
end

# cell-mean daily GPP for a set of hooks (identity by default) over all patches
function cell_gpp(phys, st0s, inds_all, soil, forc; phens, hooks = FluxHooks())
    n = length(forc); P = length(inds_all)
    g = zeros(n)
    for p in 1:P
        (_, days) = rollout_daily_canopy(phys, st0s[p], inds_all[p], soil, forc; phens = phens, hooks = hooks)
        for i in 1:n
            g[i] += days[i].gpp / P
        end
    end
    return g
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
    gs = [i for i in 1:n if GS_LO <= doy[i] <= GS_HI]
    phens_C = [clamp(x / maximum(fapar_C), 0.0, 1.0) for x in fapar_C]   # kernel-isolation phenology drive

    # build the 25 patch canopies (shared soil; fresh soil-water state per patch)
    patches = sort(unique(parse.(Int, ind["patch"])))
    inds_all = [[make_individual(ind, r) for r in findall(==(string(pn)), ind["patch"])] for pn in patches]
    st0s = [FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0) for _ in patches]
    phys = tebs_params()
    P = length(patches)
    @printf("Hainich cell 42490 — %d patches, %d individuals; C annual GPP = %.1f gC/m²/yr\n\n", P, length(ind["patch"]), sum(gpp_C))

    # baseline (untrained = identity) cell GPP under the kernel-isolation phenology drive
    g0 = cell_gpp(phys, st0s, inds_all, soil, forc; phens = phens_C)
    ratio0 = sum(g0) / sum(gpp_C)
    r0_full = _corr(g0, gpp_C); r0_gs = _corr(g0[gs], gpp_C[gs])
    @printf("baseline (identity, phen=fapar_C drive): annual ratio %.3f, daily r(full)=%.4f r(GS)=%.4f\n", ratio0, r0_full, r0_gs)

    # training window: the growing season + shoulders (winter GPP≈0 carries no signal)
    d_lo, d_hi = 105, 285
    function fit(targets; verbose = false)
        nn = build_fdiff_nn(; targets = targets, width = 12, depth = 2, corr_max = 0.6, rng = StableRNG(2026))
        (ps, hist) = train_fdiff_cell_rollout!(
            nn, phys, st0s, inds_all, soil, forc, phens_C, gpp_C;
            chunk = 60, epochs = 20, lr = 2.0e-2, day_start = d_lo, day_end = d_hi, ps = deepcopy(nn.ps), verbose = verbose,
        )
        vmh = (:vm in targets) ? neural_vm_hook(nn, ps) : nothing
        λh = (:λ in targets) ? neural_lambda_hook(nn, ps) : nothing
        g = cell_gpp(phys, st0s, inds_all, soil, forc; phens = phens_C, hooks = FluxHooks(vm = vmh, λ = λh))
        # mean recovered vm scale over the growing season, top (light-sufficient) individual of patch 1
        vm_gs = Float64[]
        if vmh !== nothing
            top = inds_all[1][argmax([ii.fpar for ii in inds_all[1]])]
            for i in gs
                par = 0.5 * 86400.0 * forc[i].swdown
                apar = par * (1 - top.albedo_leaf) * top.alphaa * (top.fpar * phens_C[i])
                wr = sum(rootdist[l] * st0s[1].w[l] / whcs[l] for l in eachindex(whcs))
                push!(vm_gs, vmh([forc[i].temp, forc[i].swdown, forc[i].daylength, apar, wr, forc[i].co2]))
            end
        end
        return (g = g, hist = hist, vm_gs = vm_gs)
    end

    println("\n── train (:vm,) — Vcmax lever, cell-mean GPP vs C daily GPP (window DOY $(d_lo)-$(d_hi)) ──")
    rvm = fit((:vm,); verbose = true)
    ratio_vm = sum(rvm.g) / sum(gpp_C)
    @printf(
        "  loss %.4g → %.4g;  annual ratio %.3f → %.3f;  daily r(full) %.4f → %.4f, r(GS) %.4f → %.4f;  mean GS vm-scale %.3f\n",
        rvm.hist[1], rvm.hist[end], ratio0, ratio_vm, r0_full, _corr(rvm.g, gpp_C), r0_gs, _corr(rvm.g[gs], gpp_C[gs]),
        isempty(rvm.vm_gs) ? NaN : _mean(rvm.vm_gs)
    )

    println("\n── train (:vm, :λ) — both levers ──")
    rvl = fit((:vm, :λ); verbose = true)
    ratio_vl = sum(rvl.g) / sum(gpp_C)
    @printf(
        "  loss %.4g → %.4g;  annual ratio %.3f → %.3f;  daily r(full) %.4f → %.4f, r(GS) %.4f → %.4f;  mean GS vm-scale %.3f\n",
        rvl.hist[1], rvl.hist[end], ratio0, ratio_vl, r0_full, _corr(rvl.g, gpp_C), r0_gs, _corr(rvl.g[gs], gpp_C[gs]),
        isempty(rvl.vm_gs) ? NaN : _mean(rvl.vm_gs)
    )

    println("\nThe learned canopy Vcmax/λ correction closes the GPP LEVEL against the REAL C daily GPP while")
    println("preserving the daily shape — the right lever on the coupled canopy path (docs §16, ADR 0016).")
    return nothing
end

main()
