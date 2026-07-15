# Model description (GMD-style)

```@meta
CurrentModule = LPJmLFITEmulator
```

> *This is the scientific manuscript the owner reads to understand the model — structured after the
> Geoscientific Model Development (GMD) model-description convention: governing equations with
> citations, and an explicit separation of **verification** (does the code solve the equations
> correctly?) from **evaluation** (does the model match independent reality?). It is a Phase-0
> scaffold: equations and structure are frozen; numbers/figures are regenerated as the components
> land. Embedded ` ```@example ` blocks re-run on every build, so any value shown here is current.*

## 1. Purpose and scope

The model is an ESM-ready **hybrid** land-surface component derived from LPJmL-FIT
[Sakschewski2016](@cite), a demographic flexible-trait DGVM. It emulates the slow individual-tree
trait/size dynamics with ML (**S**), keeps the conserving daily biophysical core (**F**), and adds a
surface-energy-balance + skin-temperature closure the source model lacks (**E**). It targets a daily-
coupled land component that returns `LE, H, G, T_skin, NBP_atm, z0` to an atmosphere. Its validity
envelope (constant CO₂, distributional target, daily source model) is stated in
[Limitations](../explanation/limitations.md).

## 2. Governing equations

### 2.1 State and structure

Every prognostic variable lives once in [`SharedState`](@ref) (`DESIGN.md` §2). The vegetation is
represented by S as a per-cell probability density over trees — a Trait Probability Density
[Carmona2016](@cite):

```math
p(\mathbf{t}, s \mid \mathbf{x}_\text{clim}, \text{CO}_2, \text{soil}, \text{Climbuf}, \text{age}, \ldots), \qquad N \in \mathbb{Z}_{\ge 0},
```

with trait vector ``\mathbf{t}`` (SLA, wood density, leaf longevity, …), size ``s``, and count ``N``.
S derives the structural boundary conditions for F/E — LAI, height, `z0`, rooting depth, a Vcmax
proxy, FPC, albedo ([`SToF`](@ref)/[`SToE`](@ref)) — from this density via LPJmL-FIT's own allometry;
they are **not** co-predicted.

### 2.2 Slow component S — allocation is flux-then-integrate

S advances the existing population rather than regenerating it [Hoedt2021](@cite). Per surviving
individual (or size×trait class) it predicts a growth increment ``\Delta C_i`` whose sum equals the
allocated NPP delivered by F ([`FToS`](@ref)`.bm_inc`):

```math
\sum_i \Delta C_i = f_\text{alloc}\,\texttt{bm\_inc}, \qquad
(f_\text{alloc}, f_\text{turnover}, f_\text{mort}) = \operatorname{softmax}(\mathbf{z}),
```

so the partition sums to one and mass is conserved by construction [Kraft2022, Beucler2021](@cite)
([`softmax_partition`](@ref), [`flux_then_integrate`](@ref)). The within-individual leaf/sapwood/
heartwood/root split uses the same softmax-of-a-conserved-input trick.

The **baseline** conditional distribution model is a Distributional Random Forest with a
negative-binomial/ZINB count model for `N`; escalate to tabular diffusion / conditional flows only if
the metric panel (§4) demands it
([ADR 0005](https://github.com/rimajj/LPJmLFIT_Emulator/blob/main/docs/decisions/0005-drf-baseline-escalation.md)).

### 2.3 Fast core F — conserving biophysics

F is LPJmL-FIT's daily core, kept unchanged, so water and carbon close by construction. Autotrophic
respiration ``R_a = \text{GPP} - \text{NPP}``. The **ecosystem carbon closure** with fire (GlobFIRM,
on) and establishment is

```math
\Delta C = \text{NPP} - R_h - \texttt{firec} + \texttt{flux\_estabc},
```

and the atmosphere-facing net flux is
``\text{NBP}_\text{atm} = R_h + \texttt{firec} - \text{NPP} - \texttt{flux\_estabc}`` — computed by
[`carbon_budget_residual`](@ref) and [`nbp_atm`](@ref). The **water closure** is

```math
P = \text{ET} + \text{runoff} + \text{drainage} + \Delta S_{\text{soil}+\text{snow}+\text{interception}},
```

checked by [`water_budget_residual`](@ref). See [Conservation](../explanation/conservation.md).

### 2.4 Energy closure E — one skin temperature

E solves for a single skin temperature and partitions available energy, reusing Terrarium.jl's
`SurfaceEnergyBalance` + `ImplicitSkinTemperature`
([ADR 0006](https://github.com/rimajj/LPJmLFIT_Emulator/blob/main/docs/decisions/0006-reuse-terrarium-seb.md)):

```math
R_n(T_\text{skin}) = \text{SWdown}\,(1-\alpha) + \text{LWdown} - \varepsilon\sigma T_\text{skin}^4,
\qquad R_n = \text{LE} + H + G,
```

with ``H = \rho c_p g_a (T_\text{skin} - T_\text{air})`` and ``g_a = g_a(\text{wind}, z_0,
\text{stability})``. Latent heat is *derived*, ``\text{LE} = \lambda\,\text{ET}`` ([`latent_heat`](@ref)),
using vaporization ([`LAMBDA_VAPORIZATION`](@ref)) or sublimation ([`LAMBDA_SUBLIMATION`](@ref)).
Because LPJmL's ET is water-limited, **H is the residual**, ``H = R_n - G - \text{LE}`` — the one
documented privileged-residual, validated hardest against flux towers [Abramowitz2024](@cite). Any ML
correction acts on ``g_a``/``T_\text{skin}`` *inside* the closed balance; the physics owns closure
[Kochkov2024](@cite).

## 3. Verification — *does the code solve the equations correctly?*

Verification asks whether the implementation is faithful to the equations and to LPJmL-FIT, using
targets that are self-consistent by construction (no observational error). The `@testitem` gates
(ENGINEERING_STANDARDS §2) that stand in for it:

- **Conservation closure.** `|carbon residual|`, `|water residual|`, and the asserted energy budget
  ``\le`` tolerance, on a single step *and* over a full rollout (Supposition.jl over valid states).
  The carbon check must include `firec` + `flux_estabc`.
- **Determinism.** Fixed seed ⇒ identical result (StableRNGs.jl).
- **Gradient correctness.** AD vs finite differences at multiple points incl. boundaries; no NaN/Inf.
- **Type stability & shapes.** `@inferred`, across batch sizes and Float32/Float64.
- **Limiting cases.** Zero forcing ⇒ zero/steady response; closed-form toy cases.
- **F1 consistency.** The kept core, driven by *true* LPJmL structure, reproduces LPJmL daily fluxes
  (it is the same code).

!!! note "Placeholder figure — verification (regenerated on every build)"
    The block below is a live ` ```@example ` placeholder that will become the verification figure
    (closure residual vs rollout step) once the S/F step functions land. For now it exercises the real
    conservation helpers so the *mechanism* — a figure regenerated from code, never pasted — is in
    place and CI-checked.

```@example verification
using LPJmLFITEmulator

# A conserved NPP input split into pools by softmax must integrate with zero leak.
bm_inc = 850.0                       # gC/m²/yr delivered by F
frac   = softmax_partition([1.2, 0.3, -0.4, 0.1])   # leaf, sapwood, heartwood, root
pools0 = zeros(4)
pools1 = flux_then_integrate(pools0, frac .* bm_inc)

allocated  = sum(pools1) - sum(pools0)
leak       = allocated - bm_inc      # must be ~0 (mass conserved by construction)
(; allocated, bm_inc, leak, fractions_sum = sum(frac))
```

```@example verification
# Ecosystem carbon closure with fire + establishment: a self-consistent set closes to ~0.
npp, rh, firec, estab = 850.0, 300.0, 40.0, 25.0
dC  = npp - rh - firec + estab
res = carbon_budget_residual(; npp, rh, firec, flux_estabc = estab, dC)
nbp = nbp_atm(; rh, firec, npp, flux_estabc = estab)
(; dC, residual = res, NBP_atm = nbp)
```

## 4. Evaluation — *does the model match independent reality?*

Evaluation asks whether the model matches data it was **not** fit to, and is where the honest
limitations bite. Use a *panel*, never one metric (`DEVELOPMENT_PLAN.md` §5).

- **Slow (distribution).** Marginals: KS, 1-Wasserstein, per-trait CRPS [Gneiting2007](@cite). Joint
  dependence: **energy score + variogram score** [Scheuerer2015](@cite) (energy score alone is
  insensitive to correlation errors), Pairwise Correlation Difference, real-vs-synthetic detection
  AUC. Physical/allometric: ``\int s\,N \approx`` stand biomass, self-thinning slope, trait ranges.
  **Report per-cell magnitude against the seed1-vs-seed2 noise floor first**, never lead with pooled
  metrics.
- **Fast (fluxes + budgets).** Daily flux accuracy vs LPJmL (ET components, GPP/NPP/Rh, soil
  moisture/temperature, SWE); budget-closure residuals ``\approx 0``.
- **Energy (added).** `LE`, `H`, `T_skin` vs **FLUXNET / PLUMBER2** [Abramowitz2024](@cite) — the only
  ground truth for the added quantities; diurnal-cycle plausibility.
- **Dynamics / resilience** (the LPJ_resilience battery [Bathiany2024](@cite)): lag-autocorrelation of
  vegC/AGB **as a function of climate** and full ACF shape; variance vs climate; recovery rate from a
  pool-perturbation experiment; and the **shuffle test** that the emulator's memory is genuinely
  internal, not merely inherited from autocorrelated climate forcing.
- **Coupled / OOD.** Multi-year free-running stability vs LPJmL-FIT (no drift/blow-up, no "AC gap"
  [Brenowitz2020](@cite)); the OOD stress test = warming + precipitation variability at **constant
  CO₂** ([SSP370 datasheet](datasheets/ssp370.md)); evaluate on held-out cells **and** scenarios.

Contrast with autoregressive land-emulator precedent [Wesselkamp2025, Natel2025](@cite): those emulate
scalar states or aggregate carbon; reproducing trait × size *distributions* is the novelty this
evaluation must certify.

!!! note "Placeholder figure — evaluation (regenerated on every build)"
    A live ` ```@example ` placeholder for the evaluation figure (distributional metric panel vs the
    noise floor). Once the metrics module lands it will render the panel; for now it summarises the
    code-defined interface graph so the build exercises the package.

```@example evaluation
using LPJmLFITEmulator
(; components = length(COMPONENTS),
   fluxes = length(FLUXES),
   conserved_edges = count(f -> f.conserved, FLUXES))
```

## 5. Reproducibility & archival

Every result is a function of the code commit, `config/*.yaml`, the input-data version, and the RNG
seeds (see [Reproduce a result](../howto/reproduce.md)). For any paper, the exact code version is
DOI-archived on Zenodo (ENGINEERING_STANDARDS §4).

## References

```@bibliography
*
```
