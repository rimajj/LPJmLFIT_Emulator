# Model card — component S (slow distribution emulator)

> *An ML Model Card (after Mitchell et al., "Model Cards for Model Reporting") for the **only** ML
> component that is a trained model: the slow trait/size distribution emulator **S**. F is kept
> physics; E is physics with a bounded ML correction — neither is a standalone trained model, so they
> are documented in the [model description](model_description.md) instead. Phase-0 scaffold: fields
> marked TBD are filled as S is trained (Phase 2+).*

## Model details

- **Name / role.** Component **S** — emulates the per-cell distribution over trees
  `p(traits, size ∣ drivers, state)` + count `N`, and advances the population by flux-then-integrate.
- **Type.** Baseline: **Distributional Random Forest** (conditional joint distribution as a weighted
  sample) + a **negative-binomial / ZINB** count model for `N`. Escalation (only if the metric panel
  demands it): tabular diffusion (TabDiff/TabSyn) or a conditional normalizing flow
  ([ADR 0002](https://github.com/rimajj/LPJmLFIT_Emulator/blob/main/docs/decisions/0002-emulate-distributions.md),
  [ADR 0005](https://github.com/rimajj/LPJmLFIT_Emulator/blob/main/docs/decisions/0005-drf-baseline-escalation.md)).
- **Version / status.** Phase 0 — interface [`AbstractSlowEmulator`](@ref) defined; `step!` not yet
  implemented. A sibling offline emulator (LightGBM + Gaussian copula) exists and is the documented
  baseline/negative result (`DESIGN.md` §6).
- **Prototype stack.** Python (`py311_new`: LightGBM/XGBoost/copulas) for the baseline; Julia/Lux port
  for coupling ([ADR 0007](https://github.com/rimajj/LPJmLFIT_Emulator/blob/main/docs/decisions/0007-julia-primary-stack.md)).
- **License.** TBD by owner; note the AGPL/EUPL/CC-BY-NC constraints in
  [Limitations](../explanation/limitations.md).

## Intended use

- **Primary.** Advance the annual vegetation trait/size **distribution** inside the hybrid, delivering
  structural boundary conditions ([`SToF`](@ref)/[`SToE`](@ref)) to F and E, conditioned on climate/
  state and on the NPP F delivered.
- **In scope.** Constant / near-historical-CO₂ regimes; distributional prediction evaluated against
  the seed noise floor; biomes represented in the biome-stratified training set.
- **Out of scope.** Per-tree/per-individual prediction (the target is a distribution); **CO₂-
  fertilization projections** (constant-CO₂ regime,
  [ADR 0004](https://github.com/rimajj/LPJmLFIT_Emulator/blob/main/docs/decisions/0004-constant-co2-regime.md));
  extrapolation beyond the training driver envelope without the physical core F.

## Factors / conditioning inputs

Annual climate summary (T, precip, radiation, VPD from `huss`), CO₂, soil properties, the 20-year
`Climbuf` memory, the previous-year distribution summary, stand age / time-since-disturbance, the
delivered `bm_inc`, the four LPJmL-FIT mortality drivers (water, temperature, growth-efficiency, age),
and the soil-moisture state. Path-dependence is encoded explicitly, watching for initial-state skill
inflation.

## Metrics

Distributional **panel**, never a single number (`DEVELOPMENT_PLAN.md` §5): KS / 1-Wasserstein /
per-trait CRPS (marginals); **energy score + variogram score** + Pairwise Correlation Difference +
detection AUC (joint dependence); physical/allometric checks (∫ size·N ≈ biomass, self-thinning slope,
trait trade-off manifolds); autoregressive rollout error and drift; the LPJ_resilience dynamics
battery (climate-dependent autocorrelation, recovery rate, **shuffle test**). **Report per-cell
magnitude against the noise floor first.** *Current values: TBD (Phase 2).*

## Training & evaluation data

- **Training.** The slow-emulator table `(cell, year)` built from the existing annual `ind` CSV +
  climate + `Climbuf`, largely reusing the sibling project's derived parquet tables
  ([Historical datasheet](datasheets/historical_obsclim.md);
  [ADR 0011](https://github.com/rimajj/LPJmLFIT_Emulator/blob/main/docs/decisions/0011-reuse-global-ground-truth.md)).
  Realistic driver **trajectories**, never factorial; stratified by biome; held out by **cell and
  scenario**.
- **Evaluation.** Held-out cells + the SSP370 OOD trajectory ([SSP370 datasheet](datasheets/ssp370.md));
  the seed1-vs-seed2 **noise floor** as the yardstick.

## Ethical / impact considerations

A scientific model, not a decision system about people. The salient risk is **scientific
misuse/overreach**: using it outside its regime (esp. rising-CO₂ projections) would yield confidently
wrong results — hence the loud, repeated regime caveat. Conservation-by-construction and the physical
core F are the safeguards against physically implausible output under coupling.

## Caveats & recommendations

- The target is a **distribution** — never evaluate or report per-tree.
- Pure-ML S does **not** extrapolate; OOD robustness comes from F + conservation + climate-invariant
  features, not from S alone (the sibling's equilibrium-ML failure is the evidence,
  [Why a hybrid?](../explanation/hybrid_rationale.md)).
- Guard the stiff autoregressive carbon+population system against oscillations/"AC gap": bounded
  outputs, flux-then-integrate, multi-step rollout, explicit slow woody-C + population states,
  re-anchoring to full LPJmL-FIT.
- Keep the statistical DRF baseline as the benchmark any escalation must beat.
