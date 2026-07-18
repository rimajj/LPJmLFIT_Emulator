# Gate — hybrid NN-hook training machinery (ADR 0016; scale-up step 7b; docs §14).
# The gradient-based online-rollout-training milestone: a Lux MLP predicts a learned multiplicative
# Vcmax correction that plugs into F_diff (FDiff.FluxHooks) and is trained THROUGH the differentiable
# daily rollout by truncated backprop through time (TBPTT, `train_fdiff_rollout!`). Three properties:
#   (1) IDENTITY — the untrained (zero-initialized) network is EXACTLY the pure-physics rollout, and the
#       `nothing` hook reproduces the committed baseline (the hook cannot perturb the physics until it
#       is trained);
#   (2) GRADIENT CORRECTNESS — the Zygote gradient of the real-forcing rollout GPP loss w.r.t. the
#       network parameters matches FiniteDifferences (the AD-vs-FD discipline of gradient_correctness_tests.jl,
#       now w.r.t. NN params; reverse-mode, since a ForwardDiff dual injected only via the params would
#       hit F_diff's convert(T,·) — ADR 0016);
#   (3) TRAINING RECOVERS A KNOWN CORRECTION — on a well-posed light-sufficient scenario the TBPTT loop
#       drives the loss to ~0 and RECOVERS a known Vcmax correction (an identifiability/recovery proof of
#       the online-rollout-training machinery, independent of the physics being right).
# The learned closure applied where the residual is actually Vcmax/phenology-shaped is the coupled
# multi-individual canopy path (Enzyme-reverse-through-mutation) — the documented next step: on the
# single-representative path the C GPP gap is light/structure-limited (co-limitation saturates at the
# light-limited rate `je`), so a Vcmax lever cannot close it there (docs §14).
# The extension (ext/FDiffTrainingExt.jl) activates via `using Lux, Zygote, Optimisers, Enzyme` (Enzyme
# is a trigger because the sibling canopy trainer — nn_canopy_training_tests.jl — needs Enzyme reverse).
@testitem "NN-hook training — identity, gradient vs FD, recovery of a known correction" tags = [:training, :fdiff] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using Lux, Zygote, Optimisers, Enzyme, FiniteDifferences, StableRNGs
    using Random
    using Test

    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = readlines(path)
        i = findfirst(l -> !startswith(strip(l), "#") && !isempty(strip(l)), lines)
        hdr = split(strip(lines[i]), ',')
        rows = [parse.(Float64, split(strip(l), ',')) for l in lines[(i + 1):end] if !isempty(strip(l))]
        return Dict(hdr[j] => [r[j] for r in rows] for j in eachindex(hdr))
    end
    function readbaseline(path)
        d = Dict{String, Float64}()
        for ln in eachline(path)
            (isempty(strip(ln)) || startswith(strip(ln), "#")) && continue
            k, v = split(strip(ln))
            d[k] = parse(Float64, v)
        end
        return d
    end

    f = readcsv(joinpath(refdir, "hainich_forcing_2010.csv"))
    t = readcsv(joinpath(refdir, "hainich_cbinary_targets_2010.csv"))
    base = readbaseline(joinpath(refdir, "hainich_fdiff_baseline_2010.txt"))
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

    # ── (1) IDENTITY: nothing-hook == committed baseline; zero-init network == pure physics ──
    (_, days_base) = rollout_daily(phys, st0, str, forc; fapars = fap)
    gpp_base = sum(x.gpp for x in days_base)
    @test gpp_base ≈ base["gpp_annual"] rtol = 1.0e-4          # the hook machinery does not move the baseline
    nn = build_fdiff_nn(; targets = (:vm,), width = 10, depth = 2, rng = StableRNG(42))
    hooks_id = FluxHooks(vm = neural_vm_hook(nn), λ = neural_lambda_hook(nn))
    (_, days_id) = rollout_daily(phys, st0, str, forc; fapars = fap, hooks = hooks_id)
    @test sum(x.gpp for x in days_id) ≈ gpp_base rtol = 1.0e-10   # untrained (zero-init) net = identity

    # ── (2) GRADIENT CORRECTNESS: Zygote gradient w.r.t. NN params vs FiniteDifferences ──
    day_range = 150:185
    loss(ps) = fdiff_gpp_loss(ps, nn, phys, st0, str, forc, fap, gpp_C, day_range)
    @test isfinite(loss(nn.ps))
    flat, re = Optimisers.destructure(nn.ps)
    gz = Optimisers.destructure(Zygote.gradient(loss, nn.ps)[1])[1]
    @test all(isfinite, gz)
    @test any(!iszero, gz)                                        # the gradient is genuinely non-zero
    fdm = central_fdm(5, 1)
    for k in randperm(StableRNG(7), length(flat))[1:6]            # a random parameter subset (full FD is O(nparams))
        g_fd = fdm(ε -> loss(re((v = copy(flat); v[k] += ε; v))), 0.0)
        @test isapprox(gz[k], g_fd; rtol = 1.0e-4, atol = 1.0e-6)
    end

    # ── (3) TRAINING RECOVERS A KNOWN CORRECTION on a well-posed light-sufficient scenario ──
    strw = Structure{Float64}(lai = 4.0, fpc = 0.8, albedo = 0.15, phen = 1.0, whc = 200.0, k_beer = 0.5)
    forcw = [
        DailyForcing{Float64}(
                swdown = 150 + 120 * sin(2π * (d - 80) / 365), lwnet = -40.0,
                temp = 15 + 12 * sin(2π * (d - 110) / 365), precip = (d % 2 == 0 ? 8.0 : 3.0),
                daylength = 12 + 4 * sin(2π * (d - 80) / 365), co2 = 380.0,
            ) for d in 1:120
    ]
    stw = FDiffState{Float64}(w = 0.7, snowpack = 0.0)
    known = 1.3                                                   # the ground-truth Vcmax correction to recover
    (_, days_k) = rollout_daily(phys, stw, strw, forcw; hooks = FluxHooks(vm = (_ -> known)))
    tgt = [x.gpp for x in days_k]
    nn2 = build_fdiff_nn(; targets = (:vm,), width = 10, depth = 2, rng = StableRNG(9))
    loss_init = fdiff_gpp_loss(nn2.ps, nn2, phys, stw, strw, forcw, nothing, tgt, 1:120)
    (ps2, hist) = train_fdiff_rollout!(
        nn2, phys, stw, strw, forcw, tgt; chunk = 60, epochs = 15, lr = 3.0e-2, ps = deepcopy(nn2.ps),
    )
    @test hist[end] < 0.1 * loss_init                            # TBPTT drives the loss down ≥ 90 %
    hooks_tr = FluxHooks(vm = neural_vm_hook(nn2, ps2))
    (_, days_tr) = rollout_daily(phys, stw, strw, forcw; hooks = hooks_tr)
    @test isapprox(sum(x.gpp for x in days_tr), sum(tgt); rtol = 0.03)   # trained GPP matches the target
    # the recovered Vcmax correction (mean over the scenario) is close to the known value
    vmh = neural_vm_hook(nn2, ps2)
    scales = Float64[]
    let st = stw
        for i in 1:120
            par = 0.5 * 86400.0 * forcw[i].swdown
            apar = par * (1 - strw.albedo) * strw.alphaa * (strw.fpc * (1 - exp(-strw.k_beer * strw.lai)))
            push!(scales, vmh([forcw[i].temp, forcw[i].swdown, forcw[i].daylength, apar, st.w, forcw[i].co2]))
            (st, _) = daily_step(phys, st, strw, forcw[i]; hooks = hooks_tr)
        end
    end
    scale_mean = sum(scales) / length(scales)
    @test 1.15 <= scale_mean <= 1.45                            # recovered ≈ known (1.3)
end
