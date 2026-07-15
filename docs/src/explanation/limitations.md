# Limitations & honest scope

> *Explanation. These are carried into **every** write-up (`DESIGN.md` §9; `DEVELOPMENT_PLAN.md` §7).
> State them; do not bury them.*

The model is trustworthy only inside a stated envelope. The limitations below are structural — they
follow from what the source model is and what data exist — not bugs to be fixed later.

## Regime & physics

- **Constant-CO₂ regime (inherited).** LPJmL-FIT here runs `with_nitrogen="no"`, so CO₂ fertilization
  is unbounded and the future runs hold **CO₂ constant** to avoid carbon runaway. The emulator is
  therefore valid only at constant / near-historical CO₂ and **must not be used to project
  CO₂-fertilization responses**. The out-of-distribution stress test is *warming + precipitation
  variability at constant CO₂*, **not** rising CO₂. Upside: SpeedyWeather's lack of a carbon cycle is
  a non-issue — `NBP_atm` is diagnostic-only. See
  [ADR 0004](https://github.com/rimajj/LPJmLFIT_Emulator/blob/main/docs/decisions/0004-constant-co2-regime.md).
- **Daily source model.** There is no sub-daily physics to learn. Sub-daily fluxes come *only* from
  re-solving the energy balance E per sub-daily step at fixed daily structure/soil state — a physical
  downscaling, not learned physics, and not a linear distribution of daily means (which would bias
  the nonlinear `T_skin⁴` and stability terms).
- **Energy balance is new physics with no in-model ground truth.** `H`, `G`-as-flux, and `T_skin` do
  not exist in LPJmL-FIT; the added closure is validated *out-of-model* against FLUXNET/PLUMBER2, and
  its accuracy is bounded by that external data. **H is the least-controlled flux** — it is the
  documented residual (see [Conservation](conservation.md)).
- **`LE = λ·ET` is a pragmatic bridge.** LPJmL's water-limited equilibrium ET is not
  energy-balance-derived; a demand-limited cap is needed, with any capped water *returned* to F's soil
  reservoir rather than silently dropped.
- **New forcings.** The ESM interface needs **wind** and **surface pressure**, which LPJmL-FIT
  ignores and which are absent from the production input config — they must be sourced separately
  (`DESIGN.md` §4.2/§7.3).

## Target, data & method

- **The target is a distribution, not a realization.** LPJmL-FIT's patch ensemble is RNG-driven;
  evaluate S *distributionally* against the seed1-vs-seed2 **noise floor** (~11 % on cell-mean AGB),
  never per-tree.
- **Noise-floor scope.** The seed pair bounds only *annual distributional* error. Daily-flux error is
  bounded against LPJmL's own daily output (no seed floor); energy error only against
  FLUXNET/PLUMBER2. The SSP370 seed-2 pair (needed for the OOD floor) is still generating — gate the
  OOD-distribution evaluation on its completion.
- **Pure ML does not extrapolate.** The sibling emulator's no-analog trait-syndrome failure (see [Why
  a hybrid?](hybrid_rationale.md)) is why OOD robustness relies on the physical core F,
  conservation-by-construction, and climate-invariant input features — not on the ML alone.
- **The CSV `ind` table lacks disaggregated pools.** Per-tree carbon (sapwood/heartwood) needs either
  allometric reconstruction (pipe model) or a RAW-format re-run; "the data already exists" holds for
  the *aggregate* (Tier-1) S only (`DESIGN.md` §3.1,
  [ADR 0011](https://github.com/rimajj/LPJmLFIT_Emulator/blob/main/docs/decisions/0011-reuse-global-ground-truth.md)).
- **Stiff carbon + population system.** An autoregressive coupled carbon/population model is
  failure-prone (oscillations, the "AC gap", blow-up). Mitigations: flux-then-integrate, bounded
  outputs, multi-step rollout, explicit slow woody-C + population states, climate-conditioned memory,
  re-anchoring; verified with the LPJ_resilience battery including the shuffle test.

## Scope & engineering risk

- **Prototype scope.** F1/E are proven on **one** cell first; **S on a small biome-stratified
  multi-cell set** (not one cell — a single cell has no across-cell climate gradient to fit;
  [ADR 0010](https://github.com/rimajj/LPJmLFIT_Emulator/blob/main/docs/decisions/0010-s-prototype-biome-stratified.md)).
  Full multi-cell generalization is a separate gated phase.
- **F1 callable-interface feasibility.** "Keep the C core, drive it with emulated structure"
  understates the surgery on an MPI batch program with global state. A Phase-3 spike must prove a
  callable per-cell daily-biophysics entry point exists (the binary's `-couple host[:port]` socket is
  a candidate) before committing to the schedule.
- **Licensing.** LPJmL is **AGPL-3.0**; Terrarium.jl / SpeedyWeather.jl are **EUPL-1.2**; NeuralCrop
  is **CC-BY-NC**. Any cross-repo code embedding needs a written legal read first — an open item, not
  yet resolved.
