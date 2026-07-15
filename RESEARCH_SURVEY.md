# Research Survey: ML/Hybrid Land-Surface Components for Coupled ESMs

State of the art (with 2024–2026 updates) for the four problems this project touches: (1) emulating DGVMs and their **distributions/structure**, (2) emulating conditional multivariate distributions (tabular/generative), (3) enforcing **conservation** in ML, and (4) achieving **stable online coupling**. Every claim is attributed. Preprints and unverified items are flagged.

The single most important cross-cutting result: **offline per-component skill does not predict — and can be anti-correlated with — coupled online stability.** Everything downstream (architecture, training, evaluation) follows from taking that seriously.

---

## Part A — Emulating DGVMs and vegetation structure

### A.1 The anchor: Natel et al. (2025), emulating LPJ-GUESS forest carbon

Natel et al. (2025), *Geosci. Model Dev.* 18, 4317–4333, doi:10.5194/gmd-18-4317-2025. Emulates the sibling individual/cohort DGVM LPJ-GUESS. Directly transferable lessons:

- **Separate models per task.** Stocks (VegC, SoilC, LitterC) and fluxes (GPP, NPP, Rh) got their own multi-output regressors; a single multi-task model was *inferior*. → Do not force one network to do everything.
- **RF vs NN trade-off.** NN extrapolated better to end-of-century warming and was more physically consistent (via SHAP); RF had lower historical bias, was better right after disturbance and for slow SoilC changes, and is more data-efficient. They suggest an ensemble.
- **Train on realistic *trajectories*, never factorial grids (key negative result).** Their first attempt used a factorial design (independent perturbations of T, P, CO₂, à la crop emulators). It **failed to generalize** to realistic CMIP6 trajectories because stylized combinations don't reproduce realistic driver *covariance*. A two-stage pretrain-on-factorial → fine-tune-on-RCP also failed (either stayed biased or suffered catastrophic forgetting). Training on physically plausible RCP trajectories, per grid cell, is what let the models learn realistic driver covariances. **LPJmL-FIT is strongly path-dependent (demography, trait sorting), so treat it like forests, not annual crops.**
- **Encode path-dependence with explicit features:** stand age / time-since-disturbance and initial pool sizes — but beware **skill inflation from initial-state leakage** (especially SoilC).
- **Operational handoff pattern.** In the LandSyMM loop the emulator advances the state but the full model periodically re-simulates and hands state back — deliberate re-anchoring to prevent free-running drift.
- **Speed-up ~95% per grid cell**; training-data generation cost excluded (one-off).
- **Biome-agnostic single global model** generalized to biome shifts better than per-PFT/per-biome emulators; validate on held-out **cells and scenarios**.

**Contrast that proves the rule:** for near-memoryless annual crops, factorial emulators *work* (Franke et al. 2020, GMD 13, 3995; CROMES v1.0, GMD 18, 5759, 2025). The difference is legacy/path-dependence — which forests and LPJmL-FIT have and crops largely don't.

### A.2 State-advancing (autoregressive) land emulators — the closest templates

- **ecLand emulator / aiLand (Wesselkamp et al. 2025, GMD 18, 921, doi:10.5194/gmd-18-921-2025).** Emulates ECMWF ecLand's **prognostic** states (soil moisture/temperature at layers, snow) **autoregressively**, as **6-hourly increments dz/dt normalized by the global std of increments** (state-increment renormalization). LSTM best for long-range/snow; XGBoost a strong all-rounder; MLP best accuracy/implementation trade-off. This is the closest published *state-advancing* land emulator. Coupling to the atmosphere is via **skin temperature**. aiLand (ECMWF/DestinE) additionally emits skin temperature + 2 m T/dewpoint and runs many years without drifting from the physical model (a free-running stability test); online coupling to AIFS is stated as ongoing, **not yet a published coupled result** (flag).
- **Low-latency Global Carbon Budget emulators (arXiv:2504.09189, 2025; NSR 2026).** Ensemble of 19 deep-learning emulators of GCB DGVMs (incl. ORCHIDEE, LPJ-wsl) predicting monthly net land sink from climate + vegetation map + **the previous 12 months of CO₂ flux** — explicit lagged-state autoregression at scale.

### A.3 Other DGVM/LSM emulators (methods worth borrowing)

- **CLM5 NN emulator for calibration** (Dagon et al. 2020, ASCMO 6, 223) — emulates carbon/water outputs from *parameters* (perturbed-parameter ensemble).
- **JULES sparse-GP emulator** (Baker et al. 2022, GMD 15, 1913) — variational sparse GP with built-in uncertainty; used for history matching (ruled out ~88% of parameter space). GP is the tool of choice when calibrated uncertainty matters and samples are modest.
- **ELM-FATES XGBoost surrogate** (Li et al. 2023, GMD 16, 4017) — surrogate to optimize demographic trait parameters for PFT coexistence (21%→73%). Notably emulates *summary outcomes*, **not** the size/cohort distribution.

### A.4 The gap = the project's novelty

**No published ML emulator reproduces a demographic/trait- or size-structured DGVM's actual *distributions* (cohort size spectra, trait spectra).** Existing work either optimizes parameters (Li 2023) or emulates aggregate carbon (Natel 2025) or scalar prognostic states (Wesselkamp 2025). Emulating LPJmL-FIT's **trait × size distributions** is genuinely new. Adjacent proof that it's tractable: statistical/ML prediction of tree diameter distributions from environment exists in forestry (spatial distributional regression of DBH, arXiv:2311.01893; ML DBH-percentile models, ScienceDirect S1574954125005096), and deep generative models can synthesize ecological community composition (Hirn et al. 2022, MEE 13, 1052, GAN+VAE, >99% composition accuracy).

Conceptual object to emulate: the **Trait Probability Density (TPD)** (Carmona et al. 2016 TREE 31, 382; 2019 Ecology) — a community as a probability density over trait axes. This is precisely the per-cell output the slow emulator should produce.

---

## Part B — Emulating conditional multivariate distributions (traits × size + counts)

Target: `p(traits, size | drivers, cell-state)` plus a **count** `N`. Two families: statistical distributional regression + copula (interpretable, data-efficient) vs deep conditional generative (flexible, data-hungry).

### B.1 Recommended baseline: Distributional Random Forests (DRF)

Ćevid et al. (2022), *JMLR* 23(333), arXiv:2005.14458 (R/Python `drf`). **The best off-the-shelf first choice.** One forest returns the **entire conditional joint distribution** of a multivariate response as a **weighted sample of the training data**; from it you read any functional — conditional quantiles, **conditional correlations**, moments — and sample trait×size draws that **preserve trait trade-offs automatically**. Splitting uses an MMD criterion sensitive to multivariate heterogeneity. No parametric copula assumption required.

Alternative statistical stack (equally valid, more modular):
- **Marginals:** Quantile Regression Forests (Meinshausen 2006), NGBoost (Duan et al. 2020, arXiv:1910.03225; boosts parameters of a chosen distribution), or GAMLSS distributional regression (Rigby & Stasinopoulos 2005) — the latter already used to predict DBH distributions spatially.
- **Dependence:** a **(conditional) copula** for trait trade-offs (ecoCopula, Popovic et al.; Anderson et al. 2019, Ecol. Evol. 9, 3276; conditional/vine copulas if correlations shift along climate gradients).
- **Count N:** a proper count family — **Poisson → negative binomial** for overdispersion, **zero-inflation/hurdle** if empty cells occur (Ver Hoef & Boveng 2007). Model N jointly with size structure (density feeds back on size).

### B.2 Escalation path: deep conditional generative (only if justified)

Escalate **only if** DRF/copula demonstrably miss multimodal or nonlinear/tail dependence in the trait×size joint, and there are enough training rows.

- **TabDiff** (Shi et al. 2025, ICLR; arXiv:2410.20626) — joint diffusion over continuous + categorical with feature-wise learnable noise schedules; current front-runner for mixed-type fidelity + **pairwise-correlation** preservation.
- **TabSyn** (Zhang et al. 2024, ICLR; arXiv:2310.09656) — transformer VAE → unified latent → diffusion; strong dependence fidelity, faster sampling.
- **Conditional normalizing flows** — attractive for **tractable likelihood** (calibration, likelihood-based training) and cheap conditional sampling; a driver-conditioned flow of `p(y|x)`.
- **Flow-matching successors (2025–2026)** — competitive with diffusion, often faster sampling.
- Avoid **CTGAN/GANs** as first choice (instability, mode collapse) and **TabDDPM's** separated per-type handling if dependence matters.

Caveats from 2025 surveys (arXiv:2502.17119; arXiv:2504.16506; systematic assessment arXiv:2402.06806): simple/statistical methods are repeatedly competitive; **diffusion can memorize on small data**. Keep the statistical baseline as the benchmark to beat.

### B.3 Distributional evaluation — use a *panel*, never one metric

- **Marginals:** Kolmogorov–Smirnov, 1-Wasserstein, per-variable **CRPS** (Gneiting & Raftery 2007).
- **Joint fidelity:** **energy distance/score** — but **only weakly sensitive to correlation errors**; do **not** certify dependence with it alone.
- **Correlation-aware:** the **variogram score** (Scheuerer & Hamill 2015, MWR 143, 1321) *is* sensitive to correlation structure — pair it with the energy score. Plus explicit **Pairwise Correlation Difference (PCD)**.
- **Detection test:** train a classifier to distinguish real vs synthetic draws; AUC→0.5 is good.
- **Physical/allometric conservation checks:** ∫ size·N ≈ stand biomass; trait ranges plausible; self-thinning slope respected. (Multivariate proper scoring for high-dimensional joints is an active area — ASCMO 11, 23, 2025; report several.)

---

## Part C — Enforcing conservation in ML

### C.1 Architectural vs loss-based (the Beucler result)

Beucler et al. (2021), *Phys. Rev. Lett.* 126, 098302, arXiv:1909.00912. Three networks emulating subgrid convection: unconstrained, **loss-constrained** (soft penalty), **architecture-constrained** (fixed conservation layers). Findings to copy:

- **Mechanism:** write constraints as a linear system `C·[x; y] = 0`; linearize nonlinear analytic constraints via "conversion layers"; the trainable network outputs only the free components and computes the rest as **exact residuals** by solving the system. The loss is on the reconstructed full vector, so gradients backprop through the fixed constraint layers.
- Hard constraints hit **machine-precision closure** at only ~2% MSE cost; **soft penalties give no per-sample guarantee** and impose an accuracy-vs-constraint trade-off.
- **In-architecture residual beats post-hoc correction** (the network sees residual-output data during training).
- **Residual-field bias:** whichever variable is forced to "absorb" the residual carries a localized error spike. → Prefer **fraction/partition** forms over a privileged residual variable.
- **Critical nuance:** hard conservation **≠ generalization**. Beucler et al. (2024, *Science Advances* 10, eadj7250) show the remedy for warmer-climate extrapolation is **climate-invariant input features** (relative humidity, plume buoyancy) — orthogonal to conservation.

### C.2 The safest hard constraint: partition a conserved input via softmax

- **Softmax water partition** (Kraft et al. 2022, HESS 26, 1579): an embedded NN emits logits → softmax → coefficients that sum to 1 and multiply the conserved water input → mass conserved by construction. **Direct analogue for splitting available energy into LE/H/G and NPP into carbon pools.**
- **Constraint layers** (Harder et al. 2024, JMLR 25, arXiv:2208.05424): additive/multiplicative/**softmax** renormalization appended to any backbone enforces a sum constraint (softmax also guarantees positivity); hard beat soft and was more stable across CNN/GAN/RNN.

### C.3 Predict fluxes/budget tendencies, then integrate the state

- **MC-LSTM** (Hoedt et al. 2021, ICML, arXiv:2101.05186): the LSTM cell *is* a vector of mass stores; **mass inputs** (the conserved quantity) are separated from **auxiliary inputs** (drivers); gates are normalized (input gate softmax, redistribution matrix column-stochastic) so mass is only split/moved/removed, never created. Unobserved sinks go to a designated "trash" outflow. Conservation is exact.
- **Flux/budget prediction improves generalization** (FloeNet, Gregory & Bushuk et al. 2026, arXiv:2603.12449 — *preprint*): predict **budget tendencies** and reconstruct the prognostic state as their time-integral (overwriting the state each step, with non-negativity); mass conserved to roundoff, and it **generalized across climates** (pre-industrial, 1%/yr CO₂) better than a non-conservative baseline. Also natively outputs coupling variables (skin temperature). This is the crucial counter-nuance to Beucler's OOD caveat: **conservation via *budget/flux* prediction (not residual redistribution on full states) did help cross-climate generalization.** The *form* of the constraint matters.
- **Predict fluxes not tendencies** for conservation + stability at reduced precision (Yuval, O'Gorman & Hill 2021, GRL 48, e2020GL091363).

### C.4 When hard mass constraints HURT (essential caveat — and why it mostly doesn't bite us)

From the same hydrology group that builds MC-LSTMs:

- **Frame et al. (2023), *Hydrol. Process.* 37(3), e14847:** enforcing closure (MC-LSTM) **degraded streamflow skill vs an unconstrained LSTM**, because the LSTM can absorb spatiotemporally variable **input/target data biases** that strict per-timestep closure forbids.
- **Frame et al. (2022), HESS 26, 3377:** mass-constrained model underperformed on out-of-sample **extreme** peak flows.
- **Beven (2020), Hydrol. Process. 34, 3608:** if observations don't themselves close mass/energy, enforcing closure need not help.
- **Relaxation recovers skill** (Wang et al. 2025, WRR, MCR-LSTM) where unobserved gains/losses are large; **but constraints help extrapolation** — an unconstrained LSTM produced implausible −20–25% water losses under warming, fixed by mass + PET/ET constraints (Wi & Steinschneider 2024, HESS 28, 479).

**Why this caveat is largely neutralized for us:** the Frame/Beven failure mode arises when the *observed* budget doesn't close (biased forcings, unobserved fluxes). **Our training targets are a self-consistent numerical model (LPJmL-FIT) whose simulated water and carbon budgets close by construction.** So hard water/carbon conservation is *appropriate and safe* here in a way it often isn't for observation-trained hydrology models. The caveat *does* re-apply to the **added energy balance**, whose budget we are asserting (not inheriting) — so treat energy-closure enforcement more carefully, and only close the budget with variables we can actually account for (the documented MC-LSTM "unobserved flux" failure mode).

### C.5 Soft vs hard vs runtime-redistribution — summary

| Strategy | Guarantee | Accuracy | Risk |
|---|---|---|---|
| Soft loss penalty | none per-sample | trade-off; can destabilize | no closure guarantee |
| **Hard architectural** (residual/null-space; MC-LSTM; softmax fractions; flux-then-integrate) | exact | ~2% MSE cost, often neutral-to-positive | residual-field bias (avoid via fractions); can hurt if targets aren't closed (not our case for water/C) |
| Runtime residual redistribution / post-hoc fixer | exact at inference | worse than in-arch | localized bias; unseen in training |

Reviews: Willard et al. 2022 (ACM Comput. Surv. 55(4), 66); Kashinath et al. 2021 (Phil. Trans. R. Soc. A 379, 20200093).

---

## Part D — Hybrid physics-ML and stable online coupling

### D.1 Offline skill ≠ online stability (the central lesson)

- **Smoking gun (Brenowitz et al. 2020, NeurIPS CCAI, arXiv:2011.03081):** an NN moist-physics emulator **beat a random forest offline**, yet online the **NN-coupled run crashed in 7 days while the RF-coupled run stayed stable**. Offline skill can be anti-correlated with online stability across model classes.
- **Origin of rollout training (Brenowitz & Bretherton 2018, GRL 45, 6289; 2019, JAMES 11, 2728):** single-timestep loss gave coupled instability; minimizing error over **multiple timesteps** was required.
- **Best diagnostic (Brenowitz et al. 2020, JAS 77, 4357):** compute the NN's **linearized response functions**, couple to gravity-wave dynamics, read off unstable-mode growth rates; **time-to-failure tracks the offline-predicted growth rate.** Fixes: **remove destabilizing inputs**; **input regularization / noise injection**.
- **Why RF is stable (Yuval & O'Gorman 2020, Nat. Commun. 11, 3295):** bounded outputs (averages of training samples) can't produce unphysical values.
- **Optimizer/architecture matter (Ott et al. 2020, Sci. Program. 2020, 8888811).**

### D.2 How differentiability + rollout training buy stability — NeuralGCM

Kochkov et al. (2024), *Nature* 632, 1060, doi:10.1038/s41586-024-07744-y. Differentiable dynamical core + learned physics, **trained online end-to-end through the solver over multi-step rollouts**; stable for **decades**. Template techniques:
- **Rollout-length curriculum**, gradually increased (6 h → 5 d) — described as "critical."
- **Short rollouts (3-day) suffice for years-to-decades stability.**
- Encoder/decoder with learned corrections to avoid initialization shock; **CRPS** loss + learned-correlation Gaussian random fields for calibrated stochastic ensembles.

### D.3 The robust hybrid pattern: physics owns conservation, NN supplies parameters/closures

This is the pattern to adopt. Differentiable process model `P(θ, x)` with embedded NNs that only supply **parameters or bounded closures** — the NN never touches the balance equations, so conservation holds for any NN output, and physically-coherent untrained diagnostics come for free.

- **Differentiable parameter learning / dPL** (Tsai et al. 2021, Nat. Commun. 12, 5988): NN maps attributes/forcings → physical parameters; whole pipeline trained end-to-end against observations; beats calibration, matches it with ~12.5% of the data, generalizes to ungauged basins and untrained variables.
- **δHBV** (Feng et al. 2022, WRR, e2022WR032404; 2023, HESS 27, 2357; δHBV 2.0, Song et al. 2025, WRR): HBV backbone + embedded NNs approaches LSTM streamflow skill *and* emits mass-consistent untrained variables (ET, baseflow, snowpack); stronger structural constraints → better extrapolation under data scarcity.
- **Framing review** (Shen et al. 2023, Nat. Rev. Earth Environ. 4, 552): under data scarcity, differentiable/physics-constrained models beat pure ML on dynamics and trends.
- **Ecosystem/land transplants (2023–2026):** differentiable FATES photosynthesis (Aboelyazeed et al. 2023, Biogeosciences 20, 2671); **DifferLand** — NN water-stress inside the physics, trained jointly against ET/GPP/resp/LAI across FLUXNET (Fang & Gentine 2024, JAMES, e2024MS004308; global scale-up Fang et al. 2026, Nat. Commun.); **JAX-CanVeg** — differentiable LSM in JAX with a hybrid Ball–Berry stomatal NN (Jiang et al. 2025, WRR, e2024WR038116).

**Implication for us:** if the fast biophysical core is re-implemented in a differentiable framework (JAX/PyTorch), the slow-emulator + energy-balance closure can be trained *through* it online, with conservation guaranteed by the physics. Even without a full re-implementation, the pattern — NN supplies bounded closures the physics consumes — is the safe way to add the energy balance.

### D.4 Coupled ML land components + the PLUMBER2 motivation

- **WRF-UNN** (Meyer et al. 2022, JAMES 14, e2021MS002744): an NN urban land model (trained on a 22-model ensemble mean) coupled **online into WRF** via a TFLite Fortran binding; **stable and more accurate** than the physical scheme. Caveat: did **not** enforce/assess surface-energy-balance closure — flagged as a prerequisite for climate use. (Also: training on a multi-model mean bakes in the mean's biases.)
- **Hybrid-JSBACH4** (ElGhawi et al. 2025, JAMES, e2025MS005102): ICON-ESM land component made hybrid by replacing photosynthesis/transpiration params (gs, Vcmax, Jmax) with NNs **called each timestep through a Python–Fortran bridge**. The clearest 2025 precedent for our hybrid (evaluated at FLUXNET sites; full global coupled runs not yet confirmed — flag).
- **PLUMBER2** (Best et al. 2015, JHM 16, 1425; Abramowitz et al. 2024, Biogeosciences 21, 5517): across ~170 flux sites, **simple out-of-sample empirical models (even linear regression) beat mechanistic land models on turbulent fluxes**, gap largest for sensible heat — strong motivation for an ML land component. **Caveat:** the benchmarks win partly *because* they ignore state memory and energy-balance closure; a coupled component that must conserve energy and carry realistic state has a harder task. Treat PLUMBER2 as an information-content ceiling, not a free lunch. (Encouragingly, ESM-embedded land models outperformed standalone ecosystem models.)

### D.5 Stability techniques catalogue (to build in)

Multi-step **rollout / online training** through a differentiable host; **rollout curriculum** short→long; **noise injection / input regularization**; **bounded outputs** (positive-definite transforms, fraction allocation); **predict fluxes not tendencies**; **state/increment renormalization** (dz/dt scaled by global std); **climate-invariant input features** for OOD; **remove destabilizing inputs**; treat **optimizer/architecture** as stability levers; **diagnose drift** with a linear growth-rate proxy + multi-year free-running runs vs the physical model + climate-bias metrics.

---

## Consolidated design implications

1. **Emulate the *distribution*, not individuals** (TPD-style trait×size density + count N). This is well-posed and the project's novelty.
2. **DRF or moments+copula baseline first; escalate to TabDiff/TabSyn/CNF only if the dependence structure demands it.** Keep the baseline as the benchmark.
3. **Generate training data along realistic driver trajectories** (scenario/ESM ensembles), stratified by biome, held out by cell *and* scenario. **No factorial grids.**
4. **Encode path-dependence explicitly** (previous-year patch/cell state + the 20-year `Climbuf` climate memory + stand age), watching for initial-state skill inflation.
5. **Conserve water and carbon by construction** — safe here because the targets are a self-consistent model, **provided ALL model fluxes are accounted** (fire `firec` and establishment `flux_estabc` are active — omitting them makes the budget fail to close, the Frame/Beven failure mode). Use **flux-then-integrate** by advancing the tree population with increments that sum to delivered NPP (not regenerating the distribution), and **fraction/partition** allocation (softmax of a conserved input into pools). Avoid privileged residual variables — except in the energy layer, where LE is water-limited (not free) so H must close as the residual (validate it hardest).
6. **Add the missing energy balance as a conservation-constrained closure** (partition available energy into LE/H/G; predict skin temperature) — but treat *energy* closure more cautiously than water/carbon (assert only a budget you can account for).
7. **Prefer the hybrid "physics owns conservation, NN supplies closures" pattern**; make the fast core differentiable if feasible so the coupled pair can be trained online.
8. **Train for coupled stability, not just offline skill:** multi-step rollout with a short→long curriculum, noise injection, bounded outputs; validate with free-running multi-year runs and a growth-rate drift proxy.
9. **Evaluate with a panel** (distributional metrics incl. variogram score; flux accuracy; budget-closure residuals; OOD/warming stress tests), never a single metric.
10. **Design the coupling interface from day one** (skin temperature + LE/H/G + NEE + roughness), and note the two new required forcings (wind, surface pressure) that LPJmL-FIT ignores.

---

## References (grouped; DOIs/arXiv)

**DGVM / land emulation**
Natel et al. 2025, GMD 18, 4317, doi:10.5194/gmd-18-4317-2025 · Franke et al. 2020, GMD 13, 3995, doi:10.5194/gmd-13-3995-2020 · CROMES v1.0, GMD 18, 5759, 2025 · Dagon et al. 2020, ASCMO 6, 223, doi:10.5194/ascmo-6-223-2020 · Baker et al. 2022, GMD 15, 1913, doi:10.5194/gmd-15-1913-2022 · Wesselkamp et al. 2025, GMD 18, 921, doi:10.5194/gmd-18-921-2025 · Low-latency GCB emulators, arXiv:2504.09189 · Li et al. 2023, GMD 16, 4017, doi:10.5194/gmd-16-4017-2023 · Eckes-Shephard et al. 2025, New Phytol., doi:10.1111/nph.70643 · Sakschewski et al. 2016 (LPJmL-FIT), Nat. Clim. Change 6, 1032, doi:10.1038/nclimate2879

**Distributional / tabular generative + metrics + ecology**
Ćevid et al. 2022 (DRF), JMLR 23(333), arXiv:2005.14458 · Meinshausen 2006 (QRF), JMLR 7, 983 · Duan et al. 2020 (NGBoost), arXiv:1910.03225 · Rigby & Stasinopoulos 2005 (GAMLSS), doi:10.1111/j.1467-9876.2005.00510.x · Shi et al. 2025 (TabDiff), arXiv:2410.20626 · Zhang et al. 2024 (TabSyn), arXiv:2310.09656 · Kotelnikov et al. 2023 (TabDDPM), arXiv:2209.15421 · Xu et al. 2019 (CTGAN/TVAE), arXiv:1907.00503 · surveys arXiv:2502.17119, arXiv:2504.16506, arXiv:2402.06806 · Ver Hoef & Boveng 2007, Ecology 88, 2766, doi:10.1890/07-0043.1 · Gneiting & Raftery 2007, JASA 102, 359, doi:10.1198/016214506000001437 · Scheuerer & Hamill 2015 (variogram score), MWR 143, 1321, doi:10.1175/MWR-D-14-00269.1 · Carmona et al. 2016 (TPD), TREE 31, 382, doi:10.1016/j.tree.2016.02.003 · Carmona et al. 2019, Ecology, doi:10.1002/ecy.2876 · Anderson et al. 2019, Ecol. Evol. 9, 3276, doi:10.1002/ece3.4948 · Hirn et al. 2022, MEE 13, 1052, doi:10.1111/2041-210X.13827 · DBH distributional regression arXiv:2311.01893

**Conservation in ML**
Beucler et al. 2021, PRL 126, 098302, arXiv:1909.00912 · Beucler et al. 2024, Sci. Adv. 10, eadj7250, doi:10.1126/sciadv.adj7250 · Hoedt et al. 2021 (MC-LSTM), arXiv:2101.05186 · Frame et al. 2023, Hydrol. Process. 37(3), e14847, doi:10.1002/hyp.14847 · Frame et al. 2022, HESS 26, 3377, doi:10.5194/hess-26-3377-2022 · Beven 2020, Hydrol. Process. 34, 3608, doi:10.1002/hyp.13805 · Wang et al. 2025 (MCR-LSTM), WRR, doi:10.1029/2024WR039131 · Wi & Steinschneider 2024, HESS 28, 479, doi:10.5194/hess-28-479-2024 · Kraft et al. 2022, HESS 26, 1579, doi:10.5194/hess-26-1579-2022 · Harder et al. 2024, JMLR 25, arXiv:2208.05424 · Gregory & Bushuk et al. 2026 (FloeNet, preprint), arXiv:2603.12449 · Yuval, O'Gorman & Hill 2021, GRL 48, e2020GL091363, doi:10.1029/2020GL091363 · Willard et al. 2022, ACM Comput. Surv. 55(4), 66, doi:10.1145/3514228

**Online coupling / hybrid / differentiable land**
Brenowitz & Bretherton 2018, GRL 45, 6289, doi:10.1029/2018GL078510 · Brenowitz et al. 2020, JAS 77, 4357, doi:10.1175/JAS-D-20-0082.1 · Brenowitz et al. 2020, arXiv:2011.03081 · Yuval & O'Gorman 2020, Nat. Commun. 11, 3295, doi:10.1038/s41467-020-17142-3 · Ott et al. 2020, Sci. Program. 2020, 8888811, doi:10.1155/2020/8888811 · Kochkov et al. 2024 (NeuralGCM), Nature 632, 1060, doi:10.1038/s41586-024-07744-y · Yu et al. 2023 (ClimSim), arXiv:2306.08754 · Hu et al. 2025 (hybrid E3SM-MMF), JAMES, doi:10.1029/2024MS004618 · Tsai et al. 2021 (dPL), Nat. Commun. 12, 5988, doi:10.1038/s41467-021-26107-z · Feng et al. 2022 (δHBV), WRR, doi:10.1029/2022WR032404 · Feng et al. 2023, HESS 27, 2357, doi:10.5194/hess-27-2357-2023 · Shen et al. 2023, Nat. Rev. Earth Environ. 4, 552, doi:10.1038/s43017-023-00450-9 · Aboelyazeed et al. 2023, Biogeosciences 20, 2671, doi:10.5194/bg-20-2671-2023 · Fang & Gentine 2024 (DifferLand), JAMES, doi:10.1029/2024MS004308 · Jiang et al. 2025 (JAX-CanVeg), WRR, doi:10.1029/2024WR038116 · Meyer et al. 2022 (WRF-UNN), JAMES 14, e2021MS002744, doi:10.1029/2021MS002744 · ElGhawi et al. 2025 (Hybrid-JSBACH4), JAMES, doi:10.1029/2025MS005102 · Best et al. 2015 (PLUMBER), JHM 16, 1425, doi:10.1175/JHM-D-14-0158.1 · Abramowitz et al. 2024 (PLUMBER2), Biogeosciences 21, 5517, doi:10.5194/bg-21-5517-2024

**Flags:** FloeNet (arXiv:2603.12449) and Fang et al. 2026 are very recent; FloeNet is a non-peer-reviewed preprint. aiLand online coupling to AIFS is design intent, not a published coupled result. "Constrained Carbon Partitioning" (GCB 2026) and an evaporative-fraction LSTM (EGUsphere 2025) were noted but their author lists/numbers are unverified. Venue corrections vs the handover: Yuval, O'Gorman & Hill 2021 is **GRL**; the strict-mass-conservation Frame paper is **2023, Hydrol. Process. 37(3), e14847**.
