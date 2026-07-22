# The falsifiable ADR-0020 experiment — is Component S better FLUX-driven than CLIMATE-driven?
#
# ADR 0020 governs that S conditions on F's DELIVERED FLUXES + AR state + the slow bioclimatic
# boundary (dropping this-year raw climate), and the climate-only DirectEmulator is the OOD benchmark.
# The falsifiable success test (docs/p1_s_in_loop_design.md risk #2): the flux-driven channel must
# GENERALISE to the warm+dry OOD holdout BETTER than the climate channel. If it does not, ADR 0020 is
# falsified for the count target.
#
# Same model class (the zero-dep native-Julia DRF, src/drf.jl), same rows + target (living-tree count
# per patch); channels differ ONLY in the feature set. To separate the ADR-0020 claim AS STATED (a
# recursive flux+state+AR S vs the non-recursive climate-only DirectEmulator) from the mechanistic
# question (do the FLUXES THEMSELVES generalise better than raw climate, holding recursion fixed?), we
# evaluate a LADDER of channels:
#
#   boundary   slow bioclimatic boundary only (gdd5/soil/eco/CO2/lat)      — the floor
#   clim       raw climate + anomalies/rolling/trend + climatology + bnd   — the DirectEmulator channel
#   clim_ar    clim + AR(prev count)                                       — climate WITH recursion
#   ar         AR(prev count) + boundary                                   — the persistence baseline
#   flux_drv   F's flux/mortality drivers + boundary (NO state, NO AR)     — fluxes ISOLATED
#   flux_st    flux_drv + this-year patch state                           — + realised structure
#   flux_full  flux_drv + state + AR + boundary                           — the S as designed (ADR 0020)
#
# Verdicts: (1) ADR-0020 as stated — flux_full beats clim OOD; (2) flux isolation — flux_drv beats clim
# OOD (the fluxes themselves carry the OOD-generalising signal, not just recursion/state).
#
# Reads the raw matrices from scripts/export_count_matrices.py (pure Base IO, no dep).
# Run via SLURM: scripts/sbatch_julia.sh ood --project=. scripts/flux_ood_experiment.jl

include(joinpath(@__DIR__, "..", "src", "drf.jl"))
using .DRF

const DATA = get(ENV, "OUT", "/p/tmp/jamirp/slow_count")

function read_manifest(path)
    d = Dict{String, String}()
    for line in eachline(path)
        parts = split(line, '\t')
        length(parts) == 2 && (d[parts[1]] = parts[2])
    end
    return d
end
parse_idx(s) = isempty(strip(s)) ? Int[] : (parse.(Int, split(strip(s))) .+ 1)  # 0-based → 1-based

mae(p, y) = sum(abs.(p .- y)) / length(y)
rmse(p, y) = sqrt(sum((p .- y) .^ 2) / length(y))
function r2(p, y)
    ȳ = sum(y) / length(y)
    ss_res = sum((p .- y) .^ 2)
    ss_tot = sum((y .- ȳ) .^ 2)
    return ss_tot > 0 ? 1 - ss_res / ss_tot : 0.0
end

function channel_matrix(Xt::Matrix{Float64}, rows::Vector{Int}, cols::Vector{Int})
    X = Matrix{Float64}(undef, length(rows), length(cols))
    @inbounds for (jj, c) in enumerate(cols), (ii, r) in enumerate(rows)
        X[ii, jj] = Xt[c, r]
    end
    return X
end

function evaluate_channel(name, Xt, cols, y, fit_rows, val_rows, ood_rows; ntrees, subsample, seed)
    isempty(cols) && return (
        name = name, p = 0, val_mae = NaN, val_rmse = NaN, val_r2 = NaN,
        ood_mae = NaN, ood_rmse = NaN, ood_r2 = NaN, fit_secs = 0.0,
    )
    Xfit = channel_matrix(Xt, fit_rows, cols)
    forest = DRF.fit_forest(
        Xfit, y[fit_rows]; ntrees = ntrees, max_depth = 16, min_leaf = 10,
        subsample = subsample, seed = seed
    )
    pval = DRF.predict(forest, channel_matrix(Xt, val_rows, cols))
    pood = DRF.predict(forest, channel_matrix(Xt, ood_rows, cols))
    return (
        name = name, p = length(cols),
        val_mae = mae(pval, y[val_rows]), val_rmse = rmse(pval, y[val_rows]), val_r2 = r2(pval, y[val_rows]),
        ood_mae = mae(pood, y[ood_rows]), ood_rmse = rmse(pood, y[ood_rows]), ood_r2 = r2(pood, y[ood_rows]),
        fit_secs = 0.0,
    )
end

function main()
    ntrees = parse(Int, get(ENV, "NTREES", "200"))
    subsample = parse(Int, get(ENV, "SUBSAMPLE", "30000"))
    seed = parse(Int, get(ENV, "SEED", "1"))
    valfrac = parse(Float64, get(ENV, "VALFRAC", "0.15"))

    man = read_manifest(joinpath(DATA, "manifest.txt"))
    n = parse(Int, man["n"])
    p = parse(Int, man["p"])
    colnames = String.(split(strip(man["colnames"])))
    boundary_idx = parse_idx(man["boundary_idx"])
    clim_all_idx = parse_idx(man["clim_idx"])            # raw climate + boundary
    boundset = Set(boundary_idx)
    clim_raw_idx = [i for i in clim_all_idx if !(i in boundset)]   # raw climate only
    colidx(pref) = [i for (i, c) in enumerate(colnames) if startswith(c, pref)]
    fluxdrv_idx = colidx("flux_")
    state_idx = colidx("state_")
    ar_idx = colidx("ar_")

    # channel ladder (each a Vector of 1-based feature column indices)
    U(v...) = unique(vcat(v...))
    channels = [
        ("boundary", boundary_idx),
        ("clim", clim_all_idx),
        ("clim_ar", U(clim_all_idx, ar_idx)),
        ("ar", U(ar_idx, boundary_idx)),
        ("flux_drv", U(fluxdrv_idx, boundary_idx)),
        ("flux_st", U(fluxdrv_idx, state_idx, boundary_idx)),
        ("flux_full", U(fluxdrv_idx, state_idx, ar_idx, boundary_idx)),
    ]
    @info "manifest" n p n_boundary = length(boundary_idx) n_clim_raw = length(clim_raw_idx) n_fluxdrv = length(fluxdrv_idx) n_state = length(state_idx) n_ar = length(ar_idx)

    Xt = Matrix{Float64}(undef, p, n)
    read!(joinpath(DATA, "X.f64"), Xt)
    y = Vector{Float64}(undef, n); read!(joinpath(DATA, "y.f64"), y)
    ho = Vector{UInt8}(undef, n); read!(joinpath(DATA, "holdout.u8"), ho)
    cell = Vector{Int32}(undef, n); read!(joinpath(DATA, "cell.i32"), cell)

    train_rows = findall(==(0x00), ho)
    ood_rows = findall(==(0x01), ho)
    train_cells = sort(unique(cell[train_rows]))
    rng = DRF.Xoshiro256pp(UInt64(seed) * 7 + 11)
    perm = DRF.randperm_first(rng, length(train_cells), length(train_cells))
    nval = max(1, round(Int, valfrac * length(train_cells)))
    val_cellset = Set(train_cells[perm[1:nval]])
    val_rows = [r for r in train_rows if cell[r] in val_cellset]
    fit_rows = [r for r in train_rows if !(cell[r] in val_cellset)]

    ȳf = sum(y[fit_rows]) / length(fit_rows)
    base_val = mae(fill(ȳf, length(val_rows)), y[val_rows])
    base_ood = mae(fill(ȳf, length(ood_rows)), y[ood_rows])
    @info "split" n_fit = length(fit_rows) n_val = length(val_rows) n_ood = length(ood_rows) mean_count = round(ȳf, digits = 2)

    results = [
        evaluate_channel(
                nm, Xt, cols, y, fit_rows, val_rows, ood_rows;
                ntrees = ntrees, subsample = subsample, seed = seed
            ) for (nm, cols) in channels
    ]
    byname = Dict(r.name => r for r in results)

    # skill vs naive on each split (1 - model/naive); OOD skill relative to the constant predictor
    sk(m, base) = 1 - m / base

    println("\n================= ADR-0020 FLUX-vs-CLIMATE OOD LADDER =================")
    println("target = living-tree count / patch;  mean(count) ≈ $(round(ȳf, digits = 2))")
    println("naive global-mean MAE:  val=$(round(base_val, digits = 3))  ood=$(round(base_ood, digits = 3))")
    println(
        rpad("channel", 11), rpad("p", 4), rpad("val_MAE", 9), rpad("val_R²", 8),
        rpad("ood_MAE", 9), rpad("ood_R²", 9), rpad("ood_skill", 10)
    )
    for r in results
        r.p == 0 && continue
        println(
            rpad(r.name, 11), rpad(r.p, 4),
            rpad(round(r.val_mae, digits = 3), 9), rpad(round(r.val_r2, digits = 3), 8),
            rpad(round(r.ood_mae, digits = 3), 9), rpad(round(r.ood_r2, digits = 3), 9),
            rpad(round(sk(r.ood_mae, base_ood), digits = 3), 10)
        )
    end

    clim = byname["clim"]; ffull = byname["flux_full"]; fdrv = byname["flux_drv"]
    # ADR 0020 falsifiable criterion: the flux-driven S beats the climate-only baseline on OOD.
    adr0020_as_stated = ffull.ood_mae < clim.ood_mae
    flux_isolated = fdrv.ood_mae < clim.ood_mae     # fluxes themselves generalise better than raw climate
    println("\nVERDICT (ADR-0020 falsifiable test — flux-driven S beats climate-only baseline on warm+dry OOD):")
    println("  as-stated  flux_full ood_MAE=$(round(ffull.ood_mae, digits = 3)) < clim ood_MAE=$(round(clim.ood_mae, digits = 3)) ? $(adr0020_as_stated)  (skill ×$(round(clim.ood_mae / ffull.ood_mae, digits = 2)))")
    println("  isolated   flux_drv  ood_MAE=$(round(fdrv.ood_mae, digits = 3)) < clim ood_MAE=$(round(clim.ood_mae, digits = 3)) ? $(flux_isolated)  (skill ×$(round(clim.ood_mae / fdrv.ood_mae, digits = 2)))")
    println("  ⇒ ADR-0020 SUPPORTED: $(adr0020_as_stated && flux_isolated)")
    println("=======================================================================\n")

    open(joinpath(DATA, "ood_verdict_seed$(seed).json"), "w") do io
        j(x) = isnan(x) ? "null" : round(x, digits = 6)
        println(io, "{")
        println(io, "  \"seed\": $seed, \"ntrees\": $ntrees, \"subsample\": $subsample,")
        println(io, "  \"n_fit\": $(length(fit_rows)), \"n_val\": $(length(val_rows)), \"n_ood\": $(length(ood_rows)),")
        println(io, "  \"mean_count\": $(j(ȳf)), \"base_val_mae\": $(j(base_val)), \"base_ood_mae\": $(j(base_ood)),")
        println(io, "  \"channels\": {")
        for (k, r) in enumerate(results)
            comma = k < length(results) ? "," : ""
            println(io, "    \"$(r.name)\": {\"p\": $(r.p), \"val_mae\": $(j(r.val_mae)), \"val_r2\": $(j(r.val_r2)), \"ood_mae\": $(j(r.ood_mae)), \"ood_r2\": $(j(r.ood_r2))}$comma")
        end
        println(io, "  },")
        println(io, "  \"adr0020_as_stated\": $adr0020_as_stated,")
        println(io, "  \"flux_isolated\": $flux_isolated,")
        println(io, "  \"adr0020_supported\": $(adr0020_as_stated && flux_isolated)")
        println(io, "}")
    end
    @info "wrote verdict" supported = (adr0020_as_stated && flux_isolated)
    return adr0020_as_stated && flux_isolated
end

main()
