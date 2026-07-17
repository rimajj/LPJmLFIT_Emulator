"""
    LPJmLFITEmulator

ESM-ready **hybrid** land-surface component derived from LPJmL-FIT.

Three components around **one authoritative shared state** ([`SharedState`](@ref)):

  - **S** — slow ML trait/size *distribution* emulator (annual): [`AbstractSlowEmulator`](@ref).
  - **F** — fast physical biophysical core kept from LPJmL-FIT (daily): [`AbstractFastCore`](@ref).
  - **E** — surface-energy-balance + skin-temperature closure (new; reuse Terrarium.jl):
    [`AbstractEnergyClosure`](@ref).

Water and carbon are conserved by the physical core; the energy budget is closed by
construction in E. Coupling variables (LE, H, G, T_skin, NEE, roughness) are **derived, not
co-predicted** — see [`conservation.jl`](@ref LPJmLFITEmulator) helpers.

This is the Phase-0 skeleton: types, the interface contract, and conservation helpers are
real and tested; the modelling components are stubs that grow under `DEVELOPMENT_PLAN.md` §6.
Frozen schemas: `DESIGN.md`.
"""
module LPJmLFITEmulator

# ── Shared state & constants (DESIGN.md §2) ─────────────────────────────────
include("state.jl")
# ── S↔F↔E interface contract (DESIGN.md §8) ─────────────────────────────────
include("interface.jl")
# ── Conservation-by-construction helpers (DESIGN.md §8, DEVELOPMENT_PLAN §2.2) ─
include("conservation.jl")
# ── Smooth surrogates for the non-differentiable ops (low-level lib; ADR 0014 step 5) ─
include("fdiff_smoothops.jl")
using .SmoothOps
# ── Shared allometry / diagnostics library (differentiable pure fns; ADR 0014/0015) ─
include("allometry.jl")
using .Allometry
# ── F_diff — the differentiable fast physical core (ADR 0014) ───────────────
include("fdiff.jl")
using .FDiff
# ── Component abstract types + Phase-N stubs ────────────────────────────────
include("components/slow.jl")
include("components/fast.jl")
include("components/energy.jl")
# ── Component/flux registry — source of truth for code-derived diagrams ─────
include("registry.jl")

# ── Hybrid NN-hook training API (ADR 0016; scale-up step 7b) ─────────────────
# The gradient-based online-rollout training of the learned Vcmax / λ corrections ([`FDiff.FluxHooks`])
# lives in the `FDiffTrainingExt` PACKAGE EXTENSION, so `Lux`/`Zygote`/`Optimisers` stay out of the
# (deliberately dependency-free) runtime. These are the generic-function stubs the extension adds
# methods to; calling them without the extension loaded (i.e. without `using Lux, Zygote, Optimisers`)
# raises a `MethodError`. See `ext/FDiffTrainingExt.jl` and `docs/phase3_fdiff_cbinary_validation.md` §14.
"""
    build_fdiff_nn(; targets=(:vm,), n_in=6, width=12, depth=2, corr_max=1.0, rng) -> nn

Build the learned-correction MLP(s) for the F_diff photosynthesis hooks (requires the `FDiffTrainingExt`
extension: `using Lux, Zygote, Optimisers`). Returns a container with the Lux `model`, initial
parameters `ps`, state `st`, and the feature normalizer. See the extension for the full signature.
"""
function build_fdiff_nn end

"""
    neural_vm_hook(nn, ps) -> (feat -> vm_scale)
    neural_lambda_hook(nn, ps) -> (feat -> λ_scale)

Wrap a trained network + parameters as an `FDiff.FluxHooks`-compatible callable mapping the day's driver
feature vector to a positive multiplicative Vcmax / λ correction. Requires the `FDiffTrainingExt` extension.
"""
function neural_vm_hook end
"""See [`neural_vm_hook`](@ref)."""
function neural_lambda_hook end

"""
    fdiff_gpp_loss(ps, nn, phys...; ...) -> Real

Scalar mean-squared daily-GPP loss of the hooked F_diff rollout against a target GPP trajectory, as a
function of the network parameters `ps` — the object whose gradient the online-rollout training
descends (and the gradient-correctness gate checks against finite differences). Requires the
`FDiffTrainingExt` extension.
"""
function fdiff_gpp_loss end

"""
    train_fdiff_rollout!(nn, ps, phys...; chunk, epochs, opt, ...) -> (ps, history)

Truncated-backprop-through-time (TBPTT) online-rollout training loop (finished port of NeuralCrop.jl's
`train_loop_rollout!`): sweep the daily rollout in `chunk`-day segments, take a Zygote gradient of the
segment GPP loss w.r.t. the network parameters, `Optimisers.update`, and carry the (detached) soil-water
state across segment boundaries. Requires the `FDiffTrainingExt` extension. Returns the trained
parameters and the per-epoch loss history.
"""
function train_fdiff_rollout! end

# State
export SharedState, NSOILLAYER, LASTLAYER, GPLHEAT, NHEATGRIDP, NTREEPOOLS, CLIMBUFSIZE
# Interface payloads
export SToF, SToE, FToS, FToE, EToF, EToATM, AtmForcing
# Conservation helpers
export softmax_partition, flux_then_integrate,
    carbon_budget_residual, water_budget_residual, nbp_atm, latent_heat,
    LAMBDA_VAPORIZATION, LAMBDA_SUBLIMATION
# Components
export AbstractSlowEmulator, AbstractFastCore, AbstractEnergyClosure
export FDiffFastCore, step!, annual_step!
# Registry
export COMPONENTS, FLUXES, Component, Flux
# Hybrid NN-hook training API (methods added by ext/FDiffTrainingExt.jl). `FDiff.FluxHooks` (the hook
# container) is reached via `using LPJmLFITEmulator.FDiff`, matching the other F_diff types.
export build_fdiff_nn, neural_vm_hook, neural_lambda_hook, fdiff_gpp_loss, train_fdiff_rollout!

end # module
