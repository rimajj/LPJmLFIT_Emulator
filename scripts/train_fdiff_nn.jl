# =============================================================================
# train_fdiff_nn.jl — gradient-based ONLINE ROLLOUT TRAINING of an F_diff NN hook
# (Phase-3 scale-up step 7b; ADR 0016; docs/phase3_fdiff_cbinary_validation.md §14).
#
# End-to-end demonstration of the hybrid-training machinery: a small Lux MLP predicts a
# learned multiplicative Vcmax correction (FDiff.FluxHooks), plugged into the
# differentiable daily rollout and trained by truncated backprop through time (TBPTT,
# `train_fdiff_rollout!`). The untrained (zero-initialized) network is EXACTLY the
# identity correction, so training departs from the calibrated physics. Three parts:
#   [A] identity — the untrained network reproduces the pure-physics rollout;
#   [B] recovery — on a well-posed light-sufficient scenario the loop drives the loss to
#       ~0 and RECOVERS a known Vcmax correction (the machinery proof);
#   [C] application — fitting the LPJmL-FIT C daily GPP on the single-representative path
#       only PARTIALLY closes the level gap (0.64 → ~0.79), because that gap is
#       light/structure-limited (co-limitation saturates at the light-limited rate), NOT
#       Vcmax-shaped — which is exactly why the multi-individual CANOPY path closed GPP in
#       step 3. The learned Vcmax/λ correction belongs on the canopy path (Enzyme-reverse-
#       through-mutation), the documented next step.
#
# Runs on the login node (pure Julia; Zygote reverse-mode). Needs Lux/Zygote/Optimisers,
# so run against the TEST environment (which declares them + the package):
#   JULIA_DEPOT_PATH=$HOME/.julia julia --project=test -e 'import Pkg; Pkg.instantiate()'
#   JULIA_DEPOT_PATH=$HOME/.julia julia --project=test scripts/train_fdiff_nn.jl
# =============================================================================
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using Lux, Zygote, Optimisers, Enzyme, StableRNGs   # Enzyme: extension trigger (canopy trainer uses it)
using Printf

const REF = joinpath(@__DIR__, "..", "test", "testitems", "references")

function readcsv(path)
    lines = readlines(path)
    i = findfirst(l -> !startswith(strip(l), "#") && !isempty(strip(l)), lines)
    hdr = split(strip(lines[i]), ',')
    rows = [parse.(Float64, split(strip(l), ',')) for l in lines[(i + 1):end] if !isempty(strip(l))]
    return Dict(hdr[j] => [r[j] for r in rows] for j in eachindex(hdr))
end

_mean(x) = sum(x) / length(x)
function _corr(a, b)
    ma = _mean(a); mb = _mean(b)
    return sum((a .- ma) .* (b .- mb)) / sqrt(sum((a .- ma) .^ 2) * sum((b .- mb) .^ 2))
end

function main()
    f = readcsv(joinpath(REF, "hainich_forcing_2010.csv"))
    t = readcsv(joinpath(REF, "hainich_cbinary_targets_2010.csv"))
    n = length(f["doy"])
    whc = maximum(t["rootmoist_C"])
    forc = [
        DailyForcing{Float64}(
                swdown = f["swdown"][i], lwnet = f["lwnet"][i], temp = f["temp"][i],
                precip = f["precip"][i], daylength = f["daylength"][i], co2 = f["co2"][i],
            ) for i in 1:n
    ]
    fap = t["fapar_C"]
    gpp_C = t["gpp_C"]
    w0 = clamp(t["rootmoist_C"][1] / whc, 0.0, 1.0)
    phys = tebs_params()
    st0 = FDiffState{Float64}(w = w0, snowpack = 0.0)
    str = tebs_structure(; whc = whc)

    # ── [A] identity: the untrained (zero-init) network reproduces the pure-physics rollout ──
    (_, d0) = rollout_daily(phys, st0, str, forc; fapars = fap)
    gpp0 = sum(x.gpp for x in d0)
    nn = build_fdiff_nn(; targets = (:vm,), width = 12, depth = 2, rng = StableRNG(2026))
    (_, did) = rollout_daily(phys, st0, str, forc; fapars = fap, hooks = FluxHooks(vm = neural_vm_hook(nn)))
    @printf(
        "[A] identity      : untrained-net GPP = %.2f, pure-physics GPP = %.2f  (Δ = %.2e)\n",
        sum(x.gpp for x in did), gpp0, abs(sum(x.gpp for x in did) - gpp0)
    )

    # ── [B] recovery: train the loop to recover a KNOWN Vcmax correction (machinery proof) ──
    strw = Structure{Float64}(lai = 4.0, fpc = 0.8, albedo = 0.15, phen = 1.0, whc = 200.0, k_beer = 0.5)
    forcw = [
        DailyForcing{Float64}(
                swdown = 150 + 120 * sin(2π * (d - 80) / 365), lwnet = -40.0,
                temp = 15 + 12 * sin(2π * (d - 110) / 365), precip = (d % 2 == 0 ? 8.0 : 3.0),
                daylength = 12 + 4 * sin(2π * (d - 80) / 365), co2 = 380.0,
            ) for d in 1:120
    ]
    stw = FDiffState{Float64}(w = 0.7, snowpack = 0.0)
    known = 1.3
    (_, dk) = rollout_daily(phys, stw, strw, forcw; hooks = FluxHooks(vm = (_ -> known)))
    tgt = [x.gpp for x in dk]
    nn_r = build_fdiff_nn(; targets = (:vm,), width = 10, depth = 2, rng = StableRNG(9))
    li = fdiff_gpp_loss(nn_r.ps, nn_r, phys, stw, strw, forcw, nothing, tgt, 1:120)
    (ps_r, hist_r) = train_fdiff_rollout!(nn_r, phys, stw, strw, forcw, tgt; chunk = 60, epochs = 20, lr = 3.0e-2, ps = deepcopy(nn_r.ps))
    vmh = neural_vm_hook(nn_r, ps_r)
    scales = Float64[]
    let st = stw
        for i in 1:120
            par = 0.5 * 86400.0 * forcw[i].swdown
            apar = par * (1 - strw.albedo) * strw.alphaa * (strw.fpc * (1 - exp(-strw.k_beer * strw.lai)))
            push!(scales, vmh([forcw[i].temp, forcw[i].swdown, forcw[i].daylength, apar, st.w, forcw[i].co2]))
            (st, _) = daily_step(phys, st, strw, forcw[i]; hooks = FluxHooks(vm = vmh))
        end
    end
    @printf(
        "[B] recovery      : loss %.4g → %.3g (%.1f%% down); recovered Vcmax scale = %.3f (known %.2f)\n",
        li, hist_r[end], 100 * (1 - hist_r[end] / li), _mean(scales), known
    )

    # ── [C] application: fit the C daily GPP on the single-representative path (partial closure) ──
    gs = [i for i in 1:n if 150 <= f["doy"][i] <= 240]
    ratio0 = gpp0 / sum(gpp_C)
    nn_c = build_fdiff_nn(; targets = (:vm,), width = 12, depth = 2, rng = StableRNG(7))
    (ps_c, _) = train_fdiff_rollout!(
        nn_c, phys, st0, str, forc, gpp_C; fapars = fap,
        chunk = 70, epochs = 40, lr = 2.0e-2, day_start = 105, day_end = 275, ps = deepcopy(nn_c.ps),
    )
    (_, dc) = rollout_daily(phys, st0, str, forc; fapars = fap, hooks = FluxHooks(vm = neural_vm_hook(nn_c, ps_c)))
    ratio_c = sum(x.gpp for x in dc) / sum(gpp_C)
    @printf(
        "[C] C-GPP fit     : annual ratio %.3f → %.3f (target 1); GS daily r %.3f → %.3f\n",
        ratio0, ratio_c, _corr([d0[i].gpp for i in gs], [gpp_C[i] for i in gs]),
        _corr([dc[i].gpp for i in gs], [gpp_C[i] for i in gs])
    )
    println("    (partial closure — the single-representative gap is light/structure-limited, not")
    println("     Vcmax-shaped; the learned correction belongs on the canopy path — docs §14, ADR 0016)")
    return nothing
end

main()
