# Gate — hybrid NN-hook training on the MULTI-INDIVIDUAL CANOPY path (ADR 0016; scale-up step
# 7b-canopy; docs §15). This is the milestone the single-representative gate (nn_training_tests.jl)
# set up as NEXT: apply the learned Vcmax/λ correction where the residual is actually Vcmax/phenology-
# shaped — the coupled canopy path, where the light is spread across individuals so photosynthesis is
# Vcmax-limited (not saturated at the light-limited rate `je` as on the single-representative path,
# docs §14). `daily_step_canopy` MUTATES the per-layer soil-water arrays and its per-individual
# `npp_ind` buffer, which Zygote cannot differentiate — so this path trains with ENZYME REVERSE (the
# AD-through-mutation follow-up flagged since scale-up step 2). Three properties, mirroring the
# single-representative gate but on the mutating canopy path and w.r.t. Enzyme:
#   (1) IDENTITY — the untrained (zero-initialized) network reproduces the pure-physics CANOPY rollout,
#       and the `nothing` hook is byte-identical (the hook cannot perturb the physics until trained ⇒
#       every committed canopy baseline in multi_individual_tests.jl is unmoved);
#   (2) GRADIENT CORRECTNESS — the ENZYME reverse gradient of the canopy GPP loss w.r.t. the network
#       parameters matches FiniteDifferences (the AD-vs-FD discipline of gradient_correctness_tests.jl,
#       now w.r.t. NN params, through the array-mutating multi-individual canopy path; `Duplicated`
#       params + `make_zero` shadow + `set_runtime_activity` — exactly Lux's own `AutoEnzyme` path);
#   (3) TRAINING RECOVERS A KNOWN CORRECTION — on a light-sufficient multi-individual canopy the TBPTT
#       loop (`train_fdiff_canopy_rollout!`) drives the loss to ~0 and RECOVERS a known Vcmax correction
#       (an identifiability/recovery proof of the Enzyme online-rollout-training machinery).
# Fully self-contained (a small inline canopy: 4 individuals, a 5-layer soil column, a 40-day forcing);
# no HPC/reference-file dependency. The extension activates via `using Lux, Zygote, Optimisers, Enzyme`.
@testitem "NN canopy training — identity, Enzyme gradient vs FD, recovery of a known correction" tags = [:training, :fdiff, :canopy] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: daily_step_canopy, rollout_daily_canopy, hainich_soilcolumn
    using Lux, Zygote, Optimisers, Enzyme, FiniteDifferences, StableRNGs
    using Random
    using Test

    # ── small self-contained multi-individual canopy ──────────────────────────────────────────────
    soil = hainich_soilcolumn(;
        whcs = [37.0, 53.0, 88.0, 175.0, 175.0], rootdist = [0.41, 0.32, 0.2, 0.07, 0.0],
        soildepth = [200.0, 300.0, 500.0, 1000.0, 1000.0],
    )
    mkind(fpar, fpc, sla, alphaa) = Individual{Float64}(
        fpar, fpc, alphaa, 0.05, 5.0, 3000.0, 800.0, 4.0 * fpc, 0.02, 0.04, 0.1, 0.4, 1 / 225,
        FDiff.PhotoParams{Float64}(; path = :c3, issla = true, sla = sla),
        FDiff.TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false,
    )
    inds = [
        mkind(0.55, 0.35, 0.01986, 0.5), mkind(0.25, 0.25, 0.022, 0.5),
        mkind(0.12, 0.2, 0.025, 0.5), mkind(0.04, 0.1, 0.03, 0.5),
    ]
    ndays = 40
    forc = [
        DailyForcing{Float64}(
                swdown = 220.0, lwnet = -45.0, temp = 19.0, precip = (d % 4 == 0 ? 8.0 : 0.3),
                daylength = 14.0, co2 = 380.0,
            ) for d in 1:ndays
    ]
    st0 = FDiffStateML{Float64}([0.7 * wc for wc in soil.whcs], 0.0)
    phys = tebs_params()
    phens = fill(1.0, ndays)                 # fixed (physics-determined) leaf-on drive
    day_range = 1:ndays

    # ── (1) IDENTITY: zero-init network == pure-physics canopy rollout ──
    (_, days_base) = rollout_daily_canopy(phys, st0, inds, soil, forc; phens = phens)
    gpp_base = sum(x.gpp for x in days_base)
    nn = build_fdiff_nn(; targets = (:vm,), width = 10, depth = 2, rng = StableRNG(42))
    hooks_id = FluxHooks(vm = neural_vm_hook(nn), λ = neural_lambda_hook(nn))
    (_, days_id) = rollout_daily_canopy(phys, st0, inds, soil, forc; phens = phens, hooks = hooks_id)
    @test sum(x.gpp for x in days_id) ≈ gpp_base rtol = 1.0e-10   # untrained (zero-init) net = identity

    # ── (2)+(3) require ENZYME REVERSE through the array-mutating canopy path. Enzyme 0.13 hits an
    # internal LLVM compiler error on Julia ≥ 1.11 (upstream EnzymeAD/Enzyme.jl) for this complex
    # mutating path — the simpler single-bucket Enzyme gate (gradient_correctness_tests.jl) is fine on
    # 1.11. The canopy Enzyme trainer is VERIFIED on Julia 1.10 (lts — the project's supported version,
    # Project.toml compat `julia = "1.10"`) to max rel err 1.2e-8. Guarded so CI's forward-compat 1.11
    # `test (1)` job stays green; docs §15.
    if VERSION < v"1.11"
        # ── (2) GRADIENT CORRECTNESS: Enzyme reverse gradient w.r.t. NN params vs FiniteDifferences ──
        # target trajectory from a KNOWN vm=1.2 correction (so the loss/gradient are genuinely non-zero)
        tgt = Float64[]
        let st = st0
            for i in 1:ndays
                (st, fl) = daily_step_canopy(phys, inds, soil, st, forc[i]; phen = 1.0, hooks = FluxHooks(vm = (_ -> 1.2)))
                push!(tgt, fl.gpp)
            end
        end
        # perturb the final (zero-init) layer so the HIDDEN-layer gradients are also non-zero (exercise the
        # full backward path, not only the readout weights)
        flat0, re0 = Optimisers.destructure(nn.ps)
        ps = re0(flat0 .+ 0.05 .* randn(StableRNG(3), length(flat0)))
        loss(p) = fdiff_canopy_gpp_loss(p, nn, phys, st0, inds, soil, forc, phens, tgt, day_range)
        @test isfinite(loss(ps))
        dps = Enzyme.make_zero(ps)
        RA = Enzyme.set_runtime_activity(Enzyme.ReverseWithPrimal)
        (_, lval) = Enzyme.autodiff(
            RA, Enzyme.Const(fdiff_canopy_gpp_loss), Enzyme.Active,
            Enzyme.Duplicated(ps, dps), Enzyme.Const(nn), Enzyme.Const(phys), Enzyme.Const(st0),
            Enzyme.Const(inds), Enzyme.Const(soil), Enzyme.Const(forc), Enzyme.Const(phens),
            Enzyme.Const(tgt), Enzyme.Const(day_range),
        )
        @test lval ≈ loss(ps) rtol = 1.0e-8                          # Enzyme primal matches the direct loss
        gz = Optimisers.destructure(dps)[1]
        flat, re = Optimisers.destructure(ps)
        @test all(isfinite, gz)
        @test any(!iszero, gz)                                       # the gradient is genuinely non-zero
        fdm = central_fdm(5, 1)
        for k in randperm(StableRNG(7), length(flat))[1:8]           # a random parameter subset (full FD is O(nparams))
            g_fd = fdm(ε -> loss(re((v = copy(flat); v[k] += ε; v))), 0.0)
            @test isapprox(gz[k], g_fd; rtol = 1.0e-4, atol = 1.0e-6)
        end

        # ── (3) TRAINING RECOVERS A KNOWN CORRECTION on the multi-individual canopy ──
        nn2 = build_fdiff_nn(; targets = (:vm,), width = 10, depth = 2, rng = StableRNG(9))
        loss_init = fdiff_canopy_gpp_loss(nn2.ps, nn2, phys, st0, inds, soil, forc, phens, tgt, day_range)
        (ps2, hist) = train_fdiff_canopy_rollout!(
            nn2, phys, st0, inds, soil, forc, phens, tgt; chunk = 40, epochs = 25, lr = 3.0e-2, ps = deepcopy(nn2.ps),
        )
        @test hist[end] < 0.1 * loss_init                            # Enzyme TBPTT drives the loss down ≥ 90 %
        hooks_tr = FluxHooks(vm = neural_vm_hook(nn2, ps2))
        (_, days_tr) = rollout_daily_canopy(phys, st0, inds, soil, forc; phens = phens, hooks = hooks_tr)
        @test isapprox(sum(x.gpp for x in days_tr), sum(tgt); rtol = 0.03)   # trained canopy GPP matches the target
        # the recovered Vcmax correction (mean over the light-sufficient top individual) is close to the known value
        vmh = neural_vm_hook(nn2, ps2)
        scales = Float64[]
        let st = st0
            for i in 1:ndays
                par = 0.5 * 86400.0 * forc[i].swdown
                apar = par * (1 - inds[1].albedo_leaf) * inds[1].alphaa * inds[1].fpar
                wr = sum(soil.rootdist[l] * st.w[l] / soil.whcs[l] for l in eachindex(st.w))
                push!(scales, vmh([forc[i].temp, forc[i].swdown, forc[i].daylength, apar, wr, forc[i].co2]))
                (st, _) = daily_step_canopy(phys, inds, soil, st, forc[i]; phen = 1.0, hooks = hooks_tr)
            end
        end
        scale_mean = sum(scales) / length(scales)
        @test 1.08 <= scale_mean <= 1.32                            # recovered ≈ known (1.2); ≈1.18 (understory je-limits bias it low)
    else
        @info "NN canopy training: Enzyme-reverse gradient + training checks skipped on Julia " *
            "$(VERSION) (Enzyme 0.13 internal compiler error on ≥ 1.11); verified on 1.10-lts (docs §15)."
    end
end

# Gate — CELL (multi-patch) NN-hook training against the honest cell-mean GPP objective (ADR 0016;
# scale-up step 7b-cell; docs §16). The LPJmL-FIT C daily GPP is a CELL quantity (the mean over the
# cell's patches), so the learned correction is trained so the CELL-MEAN GPP matches the C — the
# objective the full-Hainich driver `scripts/train_fdiff_canopy_cell.jl` runs against the real 25-patch
# reconstruction. The cell-MSE gradient is computed by an EXACT per-patch decomposition (Gauss–Newton
# residual reweighting: ∂L/∂ps = Σ_p ∂/∂ps Σ_i c_i·g_{p,i}, c_i = (2/(D·P))(ḡ_i−t_i) detached), so every
# reverse pass is the proven single-patch `daily_step_canopy` Enzyme path and the cell gradient inherits
# its correctness — verified here against FiniteDifferences on the FULL multi-patch cell MSE. This gate
# also exercises BOTH levers (`targets = (:vm, :λ)`). Self-contained (3 ragged patches, a 5-layer soil
# column, a 30-day forcing); Enzyme parts guarded to Julia < 1.11 (docs §15).
@testitem "NN cell (multi-patch) training — identity, cell gradient vs FD (Gauss–Newton), recovery, vm+λ levers" tags = [:training, :fdiff, :canopy] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: daily_step_canopy, rollout_daily_canopy, hainich_soilcolumn
    using Lux, Zygote, Optimisers, Enzyme, FiniteDifferences, StableRNGs
    using Random
    using Test

    soil = hainich_soilcolumn(;
        whcs = [37.0, 53.0, 88.0, 175.0, 175.0], rootdist = [0.41, 0.32, 0.2, 0.07, 0.0],
        soildepth = [200.0, 300.0, 500.0, 1000.0, 1000.0],
    )
    mkind(fpar, fpc, sla, alphaa) = Individual{Float64}(
        fpar, fpc, alphaa, 0.05, 5.0, 3000.0, 800.0, 4.0 * fpc, 0.02, 0.04, 0.1, 0.4, 1 / 225,
        FDiff.PhotoParams{Float64}(; path = :c3, issla = true, sla = sla),
        FDiff.TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false,
    )
    # 3 patches with DIFFERENT individual counts (ragged, like the real 25-patch cell)
    inds_all = [
        [mkind(0.55, 0.35, 0.01986, 0.5), mkind(0.25, 0.25, 0.022, 0.5), mkind(0.12, 0.2, 0.025, 0.5)],
        [mkind(0.6, 0.4, 0.02, 0.5), mkind(0.15, 0.15, 0.026, 0.5)],
        [mkind(0.5, 0.3, 0.019, 0.5), mkind(0.3, 0.22, 0.023, 0.5), mkind(0.1, 0.12, 0.028, 0.5), mkind(0.05, 0.08, 0.03, 0.5)],
    ]
    P = length(inds_all)
    ndays = 30
    forc = [
        DailyForcing{Float64}(
                swdown = 220.0, lwnet = -45.0, temp = 19.0, precip = (d % 4 == 0 ? 8.0 : 0.3),
                daylength = 14.0, co2 = 380.0,
            ) for d in 1:ndays
    ]
    st0s = [FDiffStateML{Float64}([0.7 * wc for wc in soil.whcs], 0.0) for _ in 1:P]
    phys = tebs_params()
    phens = fill(1.0, ndays)
    day_range = 1:ndays

    # ── (1) IDENTITY (both vm + λ hooks): zero-init cell rollout == pure-physics cell rollout ──
    cellgpp(hooks) = sum(sum(x.gpp for x in rollout_daily_canopy(phys, st0s[p], inds_all[p], soil, forc; phens = phens, hooks = hooks)[2]) for p in 1:P) / P
    gpp_base = cellgpp(FluxHooks())
    nn = build_fdiff_nn(; targets = (:vm, :λ), width = 10, depth = 2, rng = StableRNG(42))
    hooks_id = FluxHooks(vm = neural_vm_hook(nn), λ = neural_lambda_hook(nn))
    @test cellgpp(hooks_id) ≈ gpp_base rtol = 1.0e-10       # untrained (zero-init) net = identity, both levers

    if VERSION < v"1.11"
        ext = Base.get_extension(LPJmLFITEmulator, :FDiffTrainingExt)
        @test ext !== nothing                               # extension loaded (Lux/Zygote/Optimisers/Enzyme)

        # target from a KNOWN vm=1.15, λ=1.05 correction (so loss/gradient are genuinely non-zero)
        tgt = zeros(ndays)
        for p in 1:P
            stp = st0s[p]
            for i in 1:ndays
                (stp, fl) = daily_step_canopy(phys, inds_all[p], soil, stp, forc[i]; phen = 1.0, hooks = FluxHooks(vm = (_ -> 1.15), λ = (_ -> 1.05)))
                tgt[i] += fl.gpp / P
            end
        end
        # perturb the zero-init net so the hidden-layer gradients are non-zero too
        flat0, re0 = Optimisers.destructure(nn.ps)
        ps = re0(flat0 .+ 0.05 .* randn(StableRNG(3), length(flat0)))
        lossf(p) = fdiff_cell_gpp_loss(p, nn, phys, st0s, inds_all, soil, forc, phens, tgt, day_range)
        @test isfinite(lossf(ps))

        # ── (2) CELL GRADIENT (Gauss–Newton per-patch decomposition) vs FiniteDifferences ──
        (lval, dps) = ext._enzyme_cell_grad(ps, nn, phys, st0s, inds_all, soil, forc, phens, tgt, day_range)
        @test lval ≈ lossf(ps) rtol = 1.0e-8                # the decomposed primal equals the direct cell MSE
        gz = Optimisers.destructure(dps)[1]
        flat, re = Optimisers.destructure(ps)
        @test all(isfinite, gz)
        @test any(!iszero, gz)
        fdm = central_fdm(5, 1)
        for k in randperm(StableRNG(7), length(flat))[1:8]  # random parameter subset (full FD is O(nparams))
            g_fd = fdm(ε -> lossf(re((v = copy(flat); v[k] += ε; v))), 0.0)
            @test isapprox(gz[k], g_fd; rtol = 1.0e-4, atol = 1.0e-6)
        end

        # ── (3) TRAINING RECOVERS THE KNOWN CORRECTION on the multi-patch cell ──
        nn2 = build_fdiff_nn(; targets = (:vm, :λ), width = 10, depth = 2, rng = StableRNG(9))
        loss_init = fdiff_cell_gpp_loss(nn2.ps, nn2, phys, st0s, inds_all, soil, forc, phens, tgt, day_range)
        (ps2, hist) = train_fdiff_cell_rollout!(
            nn2, phys, st0s, inds_all, soil, forc, phens, tgt; chunk = 30, epochs = 25, lr = 3.0e-2, ps = deepcopy(nn2.ps),
        )
        @test hist[end] < 0.1 * loss_init                   # Enzyme TBPTT drives the cell loss down ≥ 90 %
        hooks_tr = FluxHooks(vm = neural_vm_hook(nn2, ps2), λ = neural_lambda_hook(nn2, ps2))
        @test isapprox(cellgpp(hooks_tr), sum(tgt); rtol = 0.03)   # trained cell GPP matches the target
    else
        @info "NN cell training: Enzyme-reverse gradient + training checks skipped on Julia " *
            "$(VERSION) (Enzyme 0.13 internal compiler error on ≥ 1.11); verified on 1.10-lts (docs §16)."
    end
end
