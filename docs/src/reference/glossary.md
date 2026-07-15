# Glossary

Terms, symbols, and units used across the project. Component-level types and functions are in the
[API reference](api.md); this page defines the *concepts*.

## Components & state

**S / F / E**
: The three hybrid components — **S** the slow ML trait/size *distribution* emulator (annual), **F**
  the fast physical biophysical core kept from LPJmL-FIT (daily), **E** the new surface-energy-balance
  + skin-temperature closure (daily → sub-daily). See [architecture](../explanation/architecture.md).

**Shared state**
: The one authoritative copy of every prognostic variable ([`SharedState`](@ref)). No component keeps
  a private copy; F owns soil/snow/thermal/SOM, S owns the vegetation distribution.

**DGVM**
: Dynamic Global Vegetation Model. LPJmL-FIT is a demographic, flexible-trait DGVM.

**LPJmL-FIT**
: LPJmL (5.6.004) with **F**lexible **I**ndividual **T**raits — a trait continuum sorted by
  competition, rather than fixed plant functional types.

**Patch / `npatch`**
: An independent stochastic realization of a cell's vegetation. Here `npatch = 25`; the 25 patches
  sample the within-cell trait/size distribution S targets.

**`Climbuf`**
: LPJmL's 20-year running climate memory ([`CLIMBUFSIZE`](@ref) = 20) — mean monthly/annual
  temperature and precipitation. The principal source of multi-year autocorrelation and a
  conditioning input to S.

**TPD (Trait Probability Density)**
: A community represented as a probability density over trait axes — the conceptual object S emulates.

## Carbon & water fluxes

**GPP / NPP / Rₐ / Rₕ**
: Gross / net primary production; autotrophic respiration `Ra = GPP − NPP`; heterotrophic
  respiration. Units gC/m²/day (daily) or gC/m²/yr (annual).

**`bm_inc`**
: The annual NPP increment F delivers to S — *the* conserved carbon quantity at the F → S handoff
  ([`FToS`](@ref)). S must allocate exactly this.

**`firec`**
: Fire carbon emission (GlobFIRM). Fire is **on**, so the carbon budget must include it.

**`flux_estabc`**
: Establishment carbon influx (new saplings). Carried on an annual channel in [`FToE`](@ref).

**NEE vs NBP_atm**
: `NEE = Rh − NPP` is only the fire-free, establishment-free part. The atmosphere-facing net flux is
  `NBP_atm = Rh + firec − NPP − flux_estabc` ([`nbp_atm`](@ref)). Diagnostic-only in a SpeedyWeather
  atmosphere (no carbon cycle).

**Ecosystem carbon closure**
: `ΔC = NPP − Rh − firec + flux_estabc` ([`carbon_budget_residual`](@ref)).

**Water closure**
: `P = ET + runoff + drainage + ΔS(soil+snow+interception)` ([`water_budget_residual`](@ref)).

**ET**
: Evapotranspiration = transpiration + soil/interception evaporation + snow sublimation. LPJmL's ET
  is water-/demand-limited (Priestley–Taylor equilibrium), **not** energy-balance-derived.

**WHC**
: Water-holding capacity. Soil water `w` is stored as a fraction of WHC.

## Energy balance (component E)

**Rn**
: Net radiation `Rn(T_skin) = SWdown(1−α) + LWdown − εσ T_skin⁴`.

**LE**
: Latent heat flux, `LE = λ·ET` ([`latent_heat`](@ref)); `λ` = vaporization
  ([`LAMBDA_VAPORIZATION`](@ref)) for liquid, sublimation ([`LAMBDA_SUBLIMATION`](@ref)) for ice.

**H**
: Sensible heat flux. **The one documented residual**: `H = Rn − G − LE` (LE is water-limited, not
  free). Validated hardest against flux towers.

**G**
: Ground (soil) heat flux, evaluated under the *single* `T_skin` shared by Rn/H/G.

**T_skin**
: Skin (surface) temperature, K. The mandatory top thermal boundary condition passed E → F
  ([`EToF`](@ref)), replacing LPJmL's native air-temperature Dirichlet BC.

**g_a / z0**
: Aerodynamic conductance / roughness length. `g_a` depends on wind, `z0`, and stability.

**Vcmax / LAI / FPC**
: Maximum carboxylation capacity (photosynthetic-capacity proxy); leaf area index; foliar projective
  cover — structural boundary conditions S passes to F/E ([`SToF`](@ref)), re-derived by allometry.

## Data, method & evaluation

**obsclim / GSWP3-W5E5**
: The observational-climate historical forcing (ISIMIP3a), daily, 1901–2019. The training baseline.
  See the [Historical datasheet](../model/datasheets/historical_obsclim.md).

**SSP370**
: The MPI-ESM1-2-HR high-emissions scenario (2015–2100), the realistic **OOD** warming trajectory
  (constant CO₂). See the [SSP370 datasheet](../model/datasheets/ssp370.md).

**OOD**
: Out-of-distribution — here, warming + precipitation variability at (near-)constant CO₂.

**Noise floor**
: The seed1-vs-seed2 distributional difference — the irreducible target error S is measured against.

**DRF**
: Distributional Random Forest — the S baseline (returns the full conditional joint distribution as a
  weighted sample). Escalate to tabular diffusion / conditional flows only if the metric panel demands
  it ([ADR 0005](https://github.com/rimajj/LPJmLFIT_Emulator/blob/main/docs/decisions/0005-drf-baseline-escalation.md)).

**flux-then-integrate**
: Predict conserved increments, then integrate the state ([`flux_then_integrate`](@ref)) — MC-LSTM
  style. How S advances the population instead of regenerating it.

**PLUMBER2 / FLUXNET**
: Flux-tower benchmark datasets — the *only* ground truth for the added energy quantities (LE, H,
  T_skin, Rn).

**Verification vs evaluation**
: *Verification* = the code solves the intended equations correctly (against LPJmL-FIT and closure
  residuals). *Evaluation* = the model matches independent reality (flux towers). Kept explicitly
  separate in the [model description](../model/model_description.md).
