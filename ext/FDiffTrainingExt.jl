# ── FDiffTrainingExt — gradient-based online-rollout training of the F_diff NN hooks (ADR 0016) ──
# Package EXTENSION (activated by `using Lux, Zygote, Optimisers`): builds the learned Vcmax / λ
# correction MLPs that plug into [`FDiff.FluxHooks`] and trains them end-to-end THROUGH the
# differentiable daily rollout against a target GPP trajectory (the LPJmL-FIT C-binary daily GPP).
# This is the finished port of NeuralCrop.jl's `train_loop_rollout!` scaffold (Yunan Lin, arXiv:2512.20177,
# CC BY-NC — patterns reused, no code copied): the same Lux-MLP + Zygote + Optimisers + truncated-
# backprop-through-time (TBPTT) rollout idiom, adapted to F_diff's tree/FIT physics and made to actually
# run (the reference's `ps_frozen`/`dailyWeather` scaffold was inconsistent).
#
# WHY REVERSE-MODE (Zygote). The NN has many parameters, so reverse-mode is the right tool; and F_diff
# computes its working type `T` from its declared inputs (params/state/structure/forcing) and
# `convert(T, …)`s its state — so a ForwardDiff `Dual` injected ONLY via the NN params would hit that
# convert. Zygote (and Enzyme) keep the forward values `Float64` and trace the adjoint, so the hook
# gradient flows cleanly. The gate cross-checks the Zygote gradient against FiniteDifferences (and, when
# it cooperates, Enzyme reverse) — the same AD-vs-FD discipline as the physics gradient gate.
module FDiffTrainingExt

using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: FluxHooks, DailyForcing, FDiffState, Structure, FDiffParams, daily_step
using Lux, Zygote, Optimisers
using Lux: Random   # stdlib Random via Lux (the dep-free parent can't declare it); RNG for Lux.setup

import LPJmLFITEmulator: build_fdiff_nn, neural_vm_hook, neural_lambda_hook, fdiff_gpp_loss, train_fdiff_rollout!

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

end # module FDiffTrainingExt
