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

# ── Hybrid NN-hook training API (ADR 0016; scale-up steps 7b + 7b-canopy) ────
# The gradient-based online-rollout training of the learned Vcmax / λ corrections ([`FDiff.FluxHooks`])
# lives in the `FDiffTrainingExt` PACKAGE EXTENSION, so `Lux`/`Zygote`/`Optimisers`/`Enzyme` stay out of
# the (deliberately dependency-free) runtime. These are the generic-function stubs the extension adds
# methods to; calling them without the extension loaded (i.e. without `using Lux, Zygote, Optimisers,
# Enzyme`) raises a `MethodError`. Two rollout paths: the SINGLE-REPRESENTATIVE loss/trainer
# ([`fdiff_gpp_loss`](@ref)/[`train_fdiff_rollout!`](@ref)) differentiates with **Zygote** (allocation-
# free daily_step); the multi-individual CANOPY loss/trainer ([`fdiff_canopy_gpp_loss`](@ref)/
# [`train_fdiff_canopy_rollout!`](@ref)) differentiates with **Enzyme reverse** because `daily_step_canopy`
# mutates the per-layer soil arrays (the AD-through-mutation path — item 7b-canopy). See
# `ext/FDiffTrainingExt.jl` and `docs/phase3_fdiff_cbinary_validation.md` §14–§15.
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

"""
    fdiff_canopy_gpp_loss(ps, nn, phys, st0, inds, soil, forcings, phens, targets, day_range) -> Real

Scalar mean-squared daily stand-GPP loss of the hooked **multi-individual canopy** rollout
(`FDiff.daily_step_canopy`) over `day_range` against `targets`, as a function of the network
parameters `ps`. Folded as scalar accumulators (no per-day flux vector) so it is differentiable through
the array-mutating canopy path by **Enzyme reverse** — this is where the learned Vcmax/λ correction has
the right lever (the canopy residual is Vcmax/phenology-shaped, unlike the light-limited single-
representative path). `phens[i]` is the (fixed, physics-determined) daily leaf-display factor. Requires
the `FDiffTrainingExt` extension.
"""
function fdiff_canopy_gpp_loss end

"""
    train_fdiff_canopy_rollout!(nn, phys, st0, inds, soil, forcings, phens, targets; chunk, epochs, opt, ...) -> (ps, history)

TBPTT online-rollout training of the learned canopy correction, the Enzyme-reverse counterpart of
[`train_fdiff_rollout!`](@ref) for the array-mutating `FDiff.daily_step_canopy` path (item
7b-canopy): each `chunk`-day segment takes an **Enzyme reverse** gradient of the canopy GPP loss w.r.t.
the network parameters (`Duplicated` params + `make_zero` shadow, `set_runtime_activity`), then
`Optimisers.update`s and carries the detached per-layer soil-water state across segment boundaries.
Requires the `FDiffTrainingExt` extension. Returns the best parameters and the per-epoch loss history.
"""
function train_fdiff_canopy_rollout! end

"""
    fdiff_cell_gpp_loss(ps, nn, phys, st0s, inds_all, soil, forcings, phens, targets, day_range) -> Real

Scalar mean-squared **cell-mean** daily-GPP loss over the multi-patch canopy: the cell GPP is the mean
of the per-patch `FDiff.daily_step_canopy` stand GPP, compared to the C-binary `targets`. The honest
multi-patch validation objective (item 7b-cell) — trained against the LPJmL-FIT C daily GPP on the full
25-patch Hainich cell. `st0s`/`inds_all` are per-patch vectors; `soil` is the shared column. Requires
the `FDiffTrainingExt` extension.
"""
function fdiff_cell_gpp_loss end

"""
    train_fdiff_cell_rollout!(nn, phys, st0s, inds_all, soil, forcings, phens, targets; chunk, epochs, opt, ...) -> (ps, history)

TBPTT online-rollout training of a single shared learned Vcmax/λ correction so the **cell-mean** daily
GPP matches the C-binary `targets` over the multi-patch canopy (item 7b-cell). The cell-MSE gradient is
computed by an exact per-patch decomposition (Gauss–Newton residual reweighting), so every reverse pass
is the proven single-patch `FDiff.daily_step_canopy` **Enzyme** path — no monolithic multi-patch AD
entry point. Requires the `FDiffTrainingExt` extension. Returns the best parameters and the per-epoch
loss history.
"""
function train_fdiff_cell_rollout! end

"""
    fdiff_multiyear_gpp_loss(ps, nn, phys, alloc, allom, st0, trees0, tmpls, soil, yearly_forcings, phens_by_year, targets_by_year) -> Real

Scalar mean-squared **per-year annual stand-GPP** loss of the hooked multi-year coupled canopy rollout
(`FDiff.rollout_canopy_years_gpp`) against `targets_by_year` (one annual GPP target per year), as a
function of the network parameters `ps`. Differentiated by **Enzyme reverse** THROUGH the annual
structure/allocation feedback (the trees regrow via `FDiff.grow_individual` between years and the light is
recomputed from the grown heights) — the struct-of-arrays multi-year kernel is what makes that reverse
pass typeable (item 7b-multiyear). `trees0`/`tmpls` are the patch's per-individual pools + `Individual`
templates; `phens_by_year[yr]` is the (fixed, physics-determined) daily leaf-display vector for year `yr`.
Requires the `FDiffTrainingExt` extension.
"""
function fdiff_multiyear_gpp_loss end

"""
    train_fdiff_multiyear_rollout!(nn, phys, alloc, allom, st0, trees0, tmpls, soil, yearly_forcings, phens_by_year, targets_by_year; epochs, lr, opt, ...) -> (ps, history)

Online-rollout training of the learned Vcmax/λ correction so the per-year annual stand GPP matches
`targets_by_year` over a multi-year coupled canopy rollout — the Enzyme-reverse counterpart of
`train_fdiff_canopy_rollout!` for the multi-year **structure-feedback** objective (item 7b-multiyear).
Each epoch takes ONE **Enzyme reverse** gradient of the FULL multi-year GPP loss w.r.t. the network
parameters and one `Optimisers.update` — the whole multi-year rollout is a single differentiated unit (no
per-chunk TBPTT: the annual structure/allocation feedback must stay inside the differentiated unit).
Requires the `FDiffTrainingExt` extension. Returns the best parameters and the per-epoch loss history.
"""
function train_fdiff_multiyear_rollout! end

"""
    fdiff_cell_multiyear_gpp_loss(ps, nn, phys, alloc, allom, st0, trees0_all, tmpls_all, soil, yearly_forcings, phens_by_year, targets_by_year) -> Real

Scalar mean-squared **cell-mean per-year annual-GPP** loss over a multi-year coupled canopy rollout: the
cell GPP each year is the mean of the per-patch stand GPP (`Ḡ_y = mean_p rollout_canopy_years_gpp(trees0_all[p], …)[y]`),
compared to the C-binary per-year annual `targets_by_year`. This composes the §16 CELL objective (one
shared correction fit so the cell-mean matches the C) with the §17 MULTI-YEAR structure-feedback path (each
patch grown across years). `trees0_all`/`tmpls_all` are per-patch vectors of per-individual pools +
`Individual` templates; the shared `st0`/`soil`/`yearly_forcings`/`phens_by_year` are the cell drivers. Its
exact gradient is computed patch-by-patch (Gauss–Newton reweighting) by the extension's
`_enzyme_cell_multiyear_grad`, so every reverse pass is the proven single-patch multi-year
`FDiff.rollout_canopy_years_gpp` Enzyme path. This scalar form is what the gate cross-checks against
FiniteDifferences and what the trainer monitors. Requires the `FDiffTrainingExt` extension.
"""
function fdiff_cell_multiyear_gpp_loss end

"""
    train_fdiff_cell_multiyear_rollout!(nn, phys, alloc, allom, st0, trees0_all, tmpls_all, soil, yearly_forcings, phens_by_year, targets_by_year; epochs, lr, opt, ...) -> (ps, history)

Train a single shared learned Vcmax/λ correction so the **cell-mean per-year** annual GPP matches the
C-binary `targets_by_year` over a multi-year coupled canopy rollout of the multi-patch cell — the
CELL × MULTI-YEAR objective (item 7b-cell-multiyear), composing the §16 cell decomposition with the §17
multi-year structure feedback. Each epoch takes ONE Enzyme-reverse gradient of the cell MSE, decomposed
patch-by-patch (Gauss–Newton reweighting, so every reverse pass is the proven single-patch multi-year
`FDiff.rollout_canopy_years_gpp` path — no monolithic multi-patch AD), and one `Optimisers.update`; the
whole multi-year rollout is a single differentiated unit per patch (no per-chunk TBPTT — the annual
structure feedback must stay inside the differentiated unit). Requires the `FDiffTrainingExt` extension.
Returns the best parameters and the per-epoch loss history.
"""
function train_fdiff_cell_multiyear_rollout! end

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
export build_fdiff_nn, neural_vm_hook, neural_lambda_hook, fdiff_gpp_loss, train_fdiff_rollout!,
    fdiff_canopy_gpp_loss, train_fdiff_canopy_rollout!, fdiff_cell_gpp_loss, train_fdiff_cell_rollout!,
    fdiff_multiyear_gpp_loss, train_fdiff_multiyear_rollout!,
    fdiff_cell_multiyear_gpp_loss, train_fdiff_cell_multiyear_rollout!

end # module
