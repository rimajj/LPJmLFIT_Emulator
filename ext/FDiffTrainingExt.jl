# ── FDiffTrainingExt — gradient-based online-rollout training of the F_diff NN hooks (ADR 0016) ──
# Package EXTENSION (activated by `using Lux, Zygote, Optimisers`): builds the learned Vcmax / λ
# correction MLPs that plug into [`FDiff.FluxHooks`] and trains them end-to-end THROUGH the
# differentiable daily rollout against a target GPP trajectory (the LPJmL-FIT C-binary daily GPP).
# This is the finished port of NeuralCrop.jl's `train_loop_rollout!` scaffold (Yunan Lin, arXiv:2512.20177,
# CC BY-NC — patterns reused, no code copied): the same Lux-MLP + Zygote + Optimisers + truncated-
# backprop-through-time (TBPTT) rollout idiom, adapted to F_diff's tree/FIT physics and made to actually
# run (the reference's `ps_frozen`/`dailyWeather` scaffold was inconsistent).
#
# WHY REVERSE-MODE. The NN has many parameters, so reverse-mode is the right tool; and F_diff computes
# its working type `T` from its declared inputs (params/state/structure/forcing) and `convert(T, …)`s its
# state — so a ForwardDiff `Dual` injected ONLY via the NN params would hit that convert. Zygote and
# Enzyme keep the forward values `Float64` and trace the adjoint, so the hook gradient flows cleanly.
#
# TWO AD BACKENDS, TWO ROLLOUT PATHS.
#  • SINGLE-REPRESENTATIVE (`train_fdiff_rollout!`): the allocation-free `daily_step` differentiates with
#    ZYGOTE (the NeuralCrop TBPTT idiom). Its gate checks Zygote vs FiniteDifferences.
#  • MULTI-INDIVIDUAL CANOPY (`train_fdiff_canopy_rollout!`): `daily_step_canopy` MUTATES the per-layer
#    soil arrays + its `npp_ind` buffer, which Zygote cannot cross — so it differentiates with ENZYME
#    reverse (`Duplicated` params + `make_zero` shadow + `set_runtime_activity`, exactly Lux's own
#    `AutoEnzyme` path). Its gate checks Enzyme vs FiniteDifferences. This is where the learned correction
#    has the right lever (the canopy residual is Vcmax/phenology-shaped, not light-limited — docs §14/§15).
# Both cross-check the AD gradient against FiniteDifferences — the same AD-vs-FD discipline as the physics
# gradient gate. The extension activates via `using Lux, Zygote, Optimisers, Enzyme`.
module FDiffTrainingExt

using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: FluxHooks, DailyForcing, FDiffState, Structure, FDiffParams, daily_step,
    FDiffStateML, SoilColumn, Individual, daily_step_canopy
using Lux, Zygote, Optimisers, Enzyme
using Lux: Random   # stdlib Random via Lux (the dep-free parent can't declare it); RNG for Lux.setup

import LPJmLFITEmulator: build_fdiff_nn, neural_vm_hook, neural_lambda_hook, fdiff_gpp_loss,
    train_fdiff_rollout!, fdiff_canopy_gpp_loss, train_fdiff_canopy_rollout!,
    fdiff_cell_gpp_loss, train_fdiff_cell_rollout!

# ── feature normalization (fixed climatological scales → O(1) NN inputs) ─────────────────────────
# FDiff hands each hook the feature vector `[temp_°C, swdown, daylength_h, apar, w_soil, co2_ppm]`
# (FluxHooks doc). These constants z-score it to ~unit range; the exact values are not load-bearing
# (an MLP is scale-robust), only that inputs are O(1). Stored in the network container for reproducibility.
struct FeatureNorm
    μ::Vector{Float64}
    σ::Vector{Float64}
end
const _DEFAULT_NORM = FeatureNorm(
    [10.0, 120.0, 11.0, 1.0e6, 0.5, 390.0],   # temp, swdown, daylength, apar, w_soil, co2
    [10.0, 90.0, 3.0, 1.0e6, 0.3, 30.0],
)
_normalize(n::FeatureNorm, feat) = (feat .- n.μ) ./ n.σ

# ── network container ────────────────────────────────────────────────────────────────────────────
"""
    FDiffNN

Container for the learned-correction network: the Lux `model` (an MLP with one output per trained
target), the initial parameters `ps`, the network state `st`, the feature normalizer `norm`, the
ordered `targets` (`:vm` and/or `:λ`, mapping positionally to the model outputs), and `corr_max` (the
correction half-range: each scale is `1 + corr_max·tanh(rawᵢ) ∈ (1−corr_max, 1+corr_max)`, `=1` when
`raw=0`). The final layer is zero-initialized so the UNTRAINED network is exactly the identity
correction — training departs from the calibrated physics.
"""
struct FDiffNN{M, P, S}
    model::M
    ps::P
    st::S
    norm::FeatureNorm
    targets::Vector{Symbol}
    corr_max::Float64
end

# each scale ∈ (1−corr_max, 1+corr_max), = 1 at raw = 0 (identity when the net is zero-initialized)
_scale(raw, corr_max) = one(raw) + corr_max * tanh(raw)

function build_fdiff_nn(;
        targets = (:vm,), n_in::Int = 6, width::Int = 12, depth::Int = 2,
        activation = tanh, corr_max::Real = 1.0, norm::FeatureNorm = _DEFAULT_NORM,
        rng::Random.AbstractRNG = Random.default_rng(),
    )
    tgts = collect(Symbol.(targets))
    all(t -> t in (:vm, :λ), tgts) || throw(ArgumentError("targets must be a subset of (:vm, :λ); got $tgts"))
    n_out = length(tgts)
    zinit(rng, dims...) = zeros(Float32, dims...)      # zero final layer ⇒ untrained net = identity
    layers = Any[Dense(n_in => width, activation)]
    for _ in 1:(depth - 1)
        push!(layers, Dense(width => width, activation))
    end
    push!(layers, Dense(width => n_out; init_weight = zinit, init_bias = zinit))
    model = Chain(layers...)
    ps, st = Lux.setup(rng, model)
    # Float64 params/state to match the F_diff (double-precision) physics — avoids the mixed-precision
    # matmul fallback (Float32 weights × Float64 features) and keeps the AD path single-precision-free.
    return FDiffNN(model, Lux.f64(ps), Lux.f64(st), norm, tgts, Float64(corr_max))
end

# ── hook builders — wrap (network, params) as an FluxHooks-compatible `feat -> scale` closure ─────
function _hook(nn::FDiffNN, ps, target::Symbol)
    idx = findfirst(==(target), nn.targets)
    idx === nothing && return nothing
    model, st, norm, corr_max = nn.model, nn.st, nn.norm, nn.corr_max
    return feat -> _scale(first(model(_normalize(norm, feat), ps, st))[idx], corr_max)
end
neural_vm_hook(nn::FDiffNN, ps) = _hook(nn, ps, :vm)
neural_vm_hook(nn::FDiffNN) = neural_vm_hook(nn, nn.ps)
neural_lambda_hook(nn::FDiffNN, ps) = _hook(nn, ps, :λ)
neural_lambda_hook(nn::FDiffNN) = neural_lambda_hook(nn, nn.ps)

"Build the [`FDiff.FluxHooks`](@ref) for a network + parameter set (`nothing` for untrained targets)."
hooks_from(nn::FDiffNN, ps) = FluxHooks(vm = neural_vm_hook(nn, ps), λ = neural_lambda_hook(nn, ps))

# ── the differentiable objective: mean-squared daily-GPP loss over a day window (Zygote-safe) ─────
# A scalar-accumulating fold over `daily_step` (NO `push!`/array mutation) so Zygote/Enzyme differentiate
# it w.r.t. the network params. Carries the immutable soil-water state across days (the autoregressive
# coupling); `st0` seeds the window (for TBPTT it is the previous chunk's detached end state). Returns
# `(loss, st_end)` — loss is the mean over the window's days.
function _window_gpp_loss(
        ps, nn::FDiffNN, phys::FDiffParams, st0::FDiffState, str::Structure,
        forcings, fapars, targets, day_range
    )
    hooks = hooks_from(nn, ps)
    st = st0
    loss = zero(eltype(targets))
    ndays = 0
    for i in day_range
        fp = fapars === nothing ? nothing : fapars[i]
        (st, fl) = daily_step(phys, st, str, forcings[i]; fapar = fp, hooks = hooks)
        loss += (fl.gpp - targets[i])^2
        ndays += 1
    end
    return (loss / max(ndays, 1), st)   # max(·,1): guard an empty day_range (no-op for ndays ≥ 1)
end

"""
    fdiff_gpp_loss(ps, nn, phys, st0, str, forcings, fapars, targets, day_range) -> Real

Scalar mean-squared daily-GPP loss (gC/m²/day)² of the hooked F_diff rollout over `day_range` against
`targets`, as a function of the network parameters `ps`. This is the object the online-rollout training
descends and the gate differentiates (Zygote vs FiniteDifferences).
"""
fdiff_gpp_loss(ps, nn::FDiffNN, phys::FDiffParams, st0::FDiffState, str::Structure, forcings, fapars, targets, day_range) =
    _window_gpp_loss(ps, nn, phys, st0, str, forcings, fapars, targets, day_range)[1]

# advance the state across a window WITHOUT tracking gradients (the TBPTT truncation between chunks)
function _advance_state(ps, nn::FDiffNN, phys::FDiffParams, st0::FDiffState, str::Structure, forcings, fapars, day_range)
    hooks = hooks_from(nn, ps)
    st = st0
    for i in day_range
        fp = fapars === nothing ? nothing : fapars[i]
        (st, _) = daily_step(phys, st, str, forcings[i]; fapar = fp, hooks = hooks)
    end
    return st
end

# ── TBPTT online-rollout training loop (finished port of NeuralCrop's train_loop_rollout!) ────────
"""
    train_fdiff_rollout!(nn, phys, st0, str, forcings, targets;
                         fapars=nothing, chunk=73, epochs=30, lr=1e-2, opt=Optimisers.Adam(lr),
                         day_start=1, day_end=length(forcings), ps=deepcopy(nn.ps), verbose=false)
        -> (ps, history)

Train the learned Vcmax / λ corrections by truncated backprop through time on the daily rollout: sweep
`[day_start, day_end]` in `chunk`-day segments; for each segment take a Zygote gradient of the segment
GPP loss w.r.t. `ps`, `Optimisers.update`, then advance the (detached) soil-water state through the
segment with the updated `ps` and carry it into the next segment. `epochs` re-sweeps. Returns the best
(lowest full-window loss) parameters and the per-epoch loss `history`. `targets[i]` = the target daily
GPP for `forcings[i]`; `fapars` optionally drives APAR with the C binary's daily FAPAR (kernel isolation).
"""
function train_fdiff_rollout!(
        nn::FDiffNN, phys::FDiffParams, st0::FDiffState, str::Structure,
        forcings, targets; fapars = nothing, chunk::Int = 73, epochs::Int = 30, lr::Real = 1.0e-2,
        opt = Optimisers.Adam(lr), day_start::Int = 1, day_end::Int = length(forcings),
        ps = deepcopy(nn.ps), verbose::Bool = false
    )
    opt_state = Optimisers.setup(opt, ps)
    history = Float64[]
    best_ps = deepcopy(ps)
    best_loss = Inf
    for ep in 1:epochs
        st = st0
        day = day_start
        while day <= day_end
            dlast = min(day + chunk - 1, day_end)
            rng_days = day:dlast
            (l, gs) = Zygote.withgradient(p -> _window_gpp_loss(p, nn, phys, st, str, forcings, fapars, targets, rng_days)[1], ps)
            if isfinite(l) && gs[1] !== nothing
                opt_state, ps = Optimisers.update(opt_state, ps, gs[1])
            else
                verbose && @warn "non-finite loss/grad at epoch $ep, days $rng_days — skipping update"
            end
            # TBPTT: carry the detached end-state (recomputed with the updated ps) into the next chunk
            st = _advance_state(ps, nn, phys, st, str, forcings, fapars, rng_days)
            day = dlast + 1
        end
        # full-window loss for monitoring / best-parameter tracking (single detached forward)
        epoch_loss = _window_gpp_loss(ps, nn, phys, st0, str, forcings, fapars, targets, day_start:day_end)[1]
        push!(history, epoch_loss)
        if epoch_loss < best_loss
            best_loss = epoch_loss
            best_ps = deepcopy(ps)
        end
        verbose && println("epoch $ep  loss=$(round(epoch_loss; sigdigits = 5))")
    end
    return (best_ps, history)
end

# ═════════════════════════════════════════════════════════════════════════════════════════════
# CANOPY (multi-individual) online-rollout training — ENZYME reverse through the mutating path
# (scale-up step 7b-canopy; ADR 0016; docs §15)
# ═════════════════════════════════════════════════════════════════════════════════════════════
# The learned Vcmax / λ correction has the right lever on the COUPLED CANOPY path: there the light is
# spread across individuals so photosynthesis is Vcmax-limited (not saturated at the light-limited rate
# `je` as on the single-representative path — docs §14), and the standalone canopy carries a
# Vcmax/phenology-shaped level residual (GPP ratio ≈ 1.17). But `daily_step_canopy` MUTATES the per-layer
# soil-water arrays (`_infiltrate`/`_transpire_total`/`_soil_evap`) and its per-individual `npp_ind`
# buffer, which Zygote cannot differentiate — so this path trains with ENZYME reverse (the
# AD-through-mutation follow-up flagged since scale-up step 2). The idiom is exactly Lux's own
# `AutoEnzyme` path: the network params are the sole `Duplicated` argument (with a `make_zero` shadow);
# everything else is `Const`; the scalar loss is `Active`; `set_runtime_activity` covers the λ-solve's
# data-dependent `clamp` (the same conditional gradient_correctness_tests.jl documents). The returned
# gradient is a NamedTuple in the params' tree shape, so it drops straight into `Optimisers.update`.

# scalar-accumulating canopy GPP loss (NO per-day flux vector — Enzyme-friendly fold; carries the
# per-layer FDiffStateML across days). `phens[i]` = the fixed, physics-determined daily leaf-display
# factor (the same Const-drive discipline the single-representative loss uses for `fapars`).
function fdiff_canopy_gpp_loss(
        ps, nn::FDiffNN, phys::FDiffParams, st0::FDiffStateML, inds, soil::SoilColumn,
        forcings, phens, targets, day_range
    )
    hooks = hooks_from(nn, ps)
    st = st0
    loss = zero(eltype(targets))
    ndays = 0
    for i in day_range
        (st, fl) = daily_step_canopy(phys, inds, soil, st, forcings[i]; phen = phens[i], hooks = hooks)
        loss += (fl.gpp - targets[i])^2
        ndays += 1
    end
    return loss / max(ndays, 1)   # max(·,1): guard an empty day_range (no-op for ndays ≥ 1)
end

# advance the canopy state across a window WITHOUT tracking gradients (the TBPTT truncation between chunks)
function _advance_canopy_state(ps, nn::FDiffNN, phys::FDiffParams, st0::FDiffStateML, inds, soil::SoilColumn, forcings, phens, day_range)
    hooks = hooks_from(nn, ps)
    st = st0
    for i in day_range
        (st, _) = daily_step_canopy(phys, inds, soil, st, forcings[i]; phen = phens[i], hooks = hooks)
    end
    return st
end

# Enzyme reverse gradient of the canopy GPP loss w.r.t. the network params `ps` (Duplicated-NamedTuple
# idiom). Returns `(loss, dps)` — `dps` is the gradient in the same tree shape as `ps` (drops into
# `Optimisers.update`). A FRESH `make_zero(ps)` per call (never a reused shadow — a reused shadow would
# silently ACCUMULATE gradients across chunks). `set_runtime_activity` for the λ-solve `clamp` conditional.
function _enzyme_canopy_grad(ps, nn::FDiffNN, phys::FDiffParams, st0::FDiffStateML, inds, soil::SoilColumn, forcings, phens, targets, day_range)
    dps = Enzyme.make_zero(ps)
    RA = Enzyme.set_runtime_activity(Enzyme.ReverseWithPrimal)
    (_, loss) = Enzyme.autodiff(
        RA, Enzyme.Const(fdiff_canopy_gpp_loss), Enzyme.Active,
        Enzyme.Duplicated(ps, dps), Enzyme.Const(nn), Enzyme.Const(phys), Enzyme.Const(st0),
        Enzyme.Const(inds), Enzyme.Const(soil), Enzyme.Const(forcings), Enzyme.Const(phens),
        Enzyme.Const(targets), Enzyme.Const(day_range),
    )
    return (loss, dps)
end

"""
    train_fdiff_canopy_rollout!(nn, phys, st0, inds, soil, forcings, phens, targets;
                                chunk=73, epochs=30, lr=1e-2, opt=Optimisers.Adam(lr),
                                day_start=1, day_end=length(forcings), ps=deepcopy(nn.ps), verbose=false)
        -> (ps, history)

Enzyme-reverse counterpart of [`train_fdiff_rollout!`](@ref) for the array-mutating multi-individual
canopy path (item 7b-canopy). Sweeps `[day_start, day_end]` in `chunk`-day segments; per segment takes
an Enzyme reverse gradient of the canopy GPP loss w.r.t. `ps` ([`_enzyme_canopy_grad`](@ref)),
`Optimisers.update`s, then advances the (detached) per-layer soil-water state through the segment with
the updated `ps` and carries it forward (TBPTT truncation). `epochs` re-sweeps. Returns the best
(lowest full-window loss) parameters and the per-epoch loss `history`.
"""
function train_fdiff_canopy_rollout!(
        nn::FDiffNN, phys::FDiffParams, st0::FDiffStateML, inds, soil::SoilColumn,
        forcings, phens, targets; chunk::Int = 73, epochs::Int = 30, lr::Real = 1.0e-2,
        opt = Optimisers.Adam(lr), day_start::Int = 1, day_end::Int = length(forcings),
        ps = deepcopy(nn.ps), verbose::Bool = false
    )
    opt_state = Optimisers.setup(opt, ps)
    history = Float64[]
    best_ps = deepcopy(ps)
    best_loss = Inf
    for ep in 1:epochs
        st = st0
        day = day_start
        while day <= day_end
            dlast = min(day + chunk - 1, day_end)
            rng_days = day:dlast
            (l, dps) = _enzyme_canopy_grad(ps, nn, phys, st, inds, soil, forcings, phens, targets, rng_days)
            if isfinite(l)
                opt_state, ps = Optimisers.update(opt_state, ps, dps)
            else
                verbose && @warn "non-finite loss/grad at epoch $ep, days $rng_days — skipping update"
            end
            # TBPTT: carry the detached end-state (recomputed with the updated ps) into the next chunk
            st = _advance_canopy_state(ps, nn, phys, st, inds, soil, forcings, phens, rng_days)
            day = dlast + 1
        end
        epoch_loss = fdiff_canopy_gpp_loss(ps, nn, phys, st0, inds, soil, forcings, phens, targets, day_start:day_end)
        push!(history, epoch_loss)
        if epoch_loss < best_loss
            best_loss = epoch_loss
            best_ps = deepcopy(ps)
        end
        verbose && println("epoch $ep  loss=$(round(epoch_loss; sigdigits = 5))")
    end
    return (best_ps, history)
end

# ═════════════════════════════════════════════════════════════════════════════════════════════
# CELL (multi-patch) online-rollout training against the REAL LPJmL-FIT C-binary daily GPP
# (scale-up step 7b-cell; ADR 0016; docs §16)
# ═════════════════════════════════════════════════════════════════════════════════════════════
# The LPJmL-FIT C daily GPP is a CELL quantity: the mean over the cell's patches (the Hainich
# prototype is 25 patches / 297 individuals — the reconstruction in
# test/testitems/references/hainich_individuals_2010.csv). §15 trained one patch against a synthetic
# recovery target; this step trains a SINGLE shared learned correction (one MLP, feature-driven per
# individual) so the CELL-MEAN GPP `ḡ_i = (1/P)·Σ_p g_{p,i}` matches the C daily GPP — the honest
# validation objective.
#
# EXACT GRADIENT BY PER-PATCH DECOMPOSITION (Gauss–Newton residual reweighting). The cell MSE
#     L(ps) = (1/D)·Σ_i (ḡ_i − t_i)²
# is a sum of squares, so its exact gradient factors into ONE reverse pass PER PATCH with DETACHED
# residual weights:
#     ∂L/∂ps = (1/D)·Σ_i 2(ḡ_i − t_i)·∂ḡ_i/∂ps = Σ_p ∂/∂ps [ Σ_i c_i·g_{p,i}(ps) ],
#     c_i = (2/(D·P))·(ḡ_i − t_i)   (constant — evaluated at the current ps).
# The identity Σ_p ∂g_{p,i}/∂ps = P·∂ḡ_i/∂ps makes this EXACT (not an approximation): the weights are
# the true residuals at the current ps. Each per-patch pass `Σ_i c_i·g_{p,i}` is a linear functional of
# exactly the PROVEN single-patch canopy rollout (fdiff_canopy_gpp_loss's `daily_step_canopy` fold), so
# the cell gradient inherits its Enzyme-vs-FiniteDifferences correctness AND its Julia-1.10
# compilation — there is NO new monolithic multi-patch Enzyme entry point to compile. The per-patch
# gradients are summed by REUSING one `Duplicated` shadow across the patch loop: Enzyme ACCUMULATES into
# the shadow across successive `autodiff` calls (`∂/∂ps` adds), which is precisely Σ_p. The shadow is
# FRESH per cell-gradient call (never carried across chunks/epochs).

# forward-only per-day cell-mean GPP over `day_range` (NO AD) + the per-patch END states (TBPTT carry).
# `st0s`/`inds_all` are per-patch vectors; the shared `soil` is one SoilColumn. States are never mutated
# in place (daily_step_canopy returns a fresh FDiffStateML), only reassigned — so `collect` (shallow) is
# a safe working copy.
function _cell_daily_gpp(ps, nn::FDiffNN, phys::FDiffParams, st0s, inds_all, soil::SoilColumn, forcings, phens, day_range)
    hooks = hooks_from(nn, ps)
    P = length(inds_all)
    sts = collect(st0s)
    gcell = zeros(Float64, length(day_range))
    for (k, i) in enumerate(day_range)
        acc = 0.0
        for p in 1:P
            (sts[p], fl) = daily_step_canopy(phys, inds_all[p], soil, sts[p], forcings[i]; phen = phens[i], hooks = hooks)
            acc += fl.gpp
        end
        gcell[k] = acc / P
    end
    return (gcell, sts)
end

"""
    fdiff_cell_gpp_loss(ps, nn, phys, st0s, inds_all, soil, forcings, phens, targets, day_range) -> Real

Scalar mean-squared **cell-mean** daily-GPP loss over `day_range`: the cell GPP is the mean of the
per-patch stand GPP (`ḡ_i = mean_p daily_step_canopy(inds_all[p], …).gpp`), compared to the C-binary
`targets[i]`. This is the honest multi-patch validation objective (item 7b-cell); its exact gradient is
computed patch-by-patch by [`_enzyme_cell_grad`](@ref) (Gauss–Newton reweighting), and this scalar form
is what the gate cross-checks against FiniteDifferences and what the trainer monitors.
"""
function fdiff_cell_gpp_loss(ps, nn::FDiffNN, phys::FDiffParams, st0s, inds_all, soil::SoilColumn, forcings, phens, targets, day_range)
    (gcell, _) = _cell_daily_gpp(ps, nn, phys, st0s, inds_all, soil, forcings, phens, day_range)
    D = length(day_range)
    d0 = first(day_range)
    loss = zero(eltype(targets))
    for k in 1:D
        loss += (gcell[k] - targets[d0 + k - 1])^2
    end
    return loss / D
end

# per-patch LINEAR GPP functional Σ_k weights[k]·gpp_{p,k} — the Enzyme entry point for the cell
# gradient (linear in the daily GPP so, summed over patches with the detached Gauss–Newton weights, it
# reproduces ∂(cell MSE)/∂ps exactly). Structurally identical to fdiff_canopy_gpp_loss (same
# `daily_step_canopy` fold), so it compiles on the same proven Julia-1.10 Enzyme path.
function _patch_linear_gpp(ps, nn::FDiffNN, phys::FDiffParams, st0::FDiffStateML, inds, soil::SoilColumn, forcings, phens, weights, day_range)
    hooks = hooks_from(nn, ps)
    st = st0
    acc = zero(eltype(weights))
    for (k, i) in enumerate(day_range)
        (st, fl) = daily_step_canopy(phys, inds, soil, st, forcings[i]; phen = phens[i], hooks = hooks)
        acc += weights[k] * fl.gpp
    end
    return acc
end

# advance ALL patch states across a window WITHOUT tracking gradients (the TBPTT truncation between
# chunks); returns the new per-patch states vector.
function _advance_cell_states(ps, nn::FDiffNN, phys::FDiffParams, st0s, inds_all, soil::SoilColumn, forcings, phens, day_range)
    (_, sts) = _cell_daily_gpp(ps, nn, phys, st0s, inds_all, soil, forcings, phens, day_range)
    return sts
end

# Enzyme reverse gradient of the cell MSE w.r.t. `ps`, by the per-patch decomposition. Returns
# `(loss, dps)`. ONE shadow `dps` is reused across the patch loop so Enzyme accumulates Σ_p; it is fresh
# per call (never carried across chunks). `set_runtime_activity` for the λ-solve `clamp` conditional.
function _enzyme_cell_grad(ps, nn::FDiffNN, phys::FDiffParams, st0s, inds_all, soil::SoilColumn, forcings, phens, targets, day_range)
    (gcell, _) = _cell_daily_gpp(ps, nn, phys, st0s, inds_all, soil, forcings, phens, day_range)
    D = length(day_range)
    P = length(inds_all)
    d0 = first(day_range)
    loss = zero(eltype(targets))
    weights = Vector{Float64}(undef, D)
    for k in 1:D
        r = gcell[k] - targets[d0 + k - 1]
        loss += r^2
        weights[k] = (2.0 / (D * P)) * r            # detached Gauss–Newton residual weight
    end
    loss /= D
    dps = Enzyme.make_zero(ps)                       # ONE shadow — Enzyme accumulates Σ_p across the loop
    RA = Enzyme.set_runtime_activity(Enzyme.ReverseWithPrimal)
    for p in 1:P
        Enzyme.autodiff(
            RA, Enzyme.Const(_patch_linear_gpp), Enzyme.Active,
            Enzyme.Duplicated(ps, dps), Enzyme.Const(nn), Enzyme.Const(phys), Enzyme.Const(st0s[p]),
            Enzyme.Const(inds_all[p]), Enzyme.Const(soil), Enzyme.Const(forcings), Enzyme.Const(phens),
            Enzyme.Const(weights), Enzyme.Const(day_range),
        )
    end
    return (loss, dps)
end

"""
    train_fdiff_cell_rollout!(nn, phys, st0s, inds_all, soil, forcings, phens, targets;
                              chunk=73, epochs=30, lr=1e-2, opt=Optimisers.Adam(lr),
                              day_start=1, day_end=length(forcings), ps=deepcopy(nn.ps), verbose=false)
        -> (ps, history)

Train a single shared learned Vcmax/λ correction so the **cell-mean** daily GPP matches the C-binary
`targets` over the multi-patch canopy (`st0s`/`inds_all` are per-patch vectors, `soil` shared) — the
Enzyme-reverse TBPTT counterpart of [`train_fdiff_canopy_rollout!`](@ref) for the full cell (item
7b-cell). Each `chunk`-day segment: forward all patches for the cell residual, take the Enzyme
per-patch-decomposed gradient of the cell MSE ([`_enzyme_cell_grad`](@ref)), `Optimisers.update`, then
advance every patch's (detached) soil-water state through the segment with the updated `ps` and carry it
forward (TBPTT truncation). `epochs` re-sweeps. Returns the best (lowest full-window loss) parameters and
the per-epoch loss `history`.
"""
function train_fdiff_cell_rollout!(
        nn::FDiffNN, phys::FDiffParams, st0s, inds_all, soil::SoilColumn,
        forcings, phens, targets; chunk::Int = 73, epochs::Int = 30, lr::Real = 1.0e-2,
        opt = Optimisers.Adam(lr), day_start::Int = 1, day_end::Int = length(forcings),
        ps = deepcopy(nn.ps), verbose::Bool = false
    )
    opt_state = Optimisers.setup(opt, ps)
    history = Float64[]
    best_ps = deepcopy(ps)
    best_loss = Inf
    for ep in 1:epochs
        sts = collect(st0s)
        day = day_start
        while day <= day_end
            dlast = min(day + chunk - 1, day_end)
            rng_days = day:dlast
            (l, dps) = _enzyme_cell_grad(ps, nn, phys, sts, inds_all, soil, forcings, phens, targets, rng_days)
            if isfinite(l)
                opt_state, ps = Optimisers.update(opt_state, ps, dps)
            else
                verbose && @warn "non-finite loss at epoch $ep, days $rng_days — skipping update"
            end
            # TBPTT: carry the detached per-patch end-states (recomputed with the updated ps) forward
            sts = _advance_cell_states(ps, nn, phys, sts, inds_all, soil, forcings, phens, rng_days)
            day = dlast + 1
        end
        epoch_loss = fdiff_cell_gpp_loss(ps, nn, phys, st0s, inds_all, soil, forcings, phens, targets, day_start:day_end)
        push!(history, epoch_loss)
        if epoch_loss < best_loss
            best_loss = epoch_loss
            best_ps = deepcopy(ps)
        end
        verbose && println("epoch $ep  loss=$(round(epoch_loss; sigdigits = 5))")
    end
    return (best_ps, history)
end

end # module FDiffTrainingExt
