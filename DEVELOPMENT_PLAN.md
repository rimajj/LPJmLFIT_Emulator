# Development Plan: ESM-Ready LPJmL-FIT Emulator / Hybrid Land Component

This plan turns the established two-timescale framing and coupling physics (handover §2) into a concrete, phased, research-backed development program, given the source-code findings (`SOURCE_FINDINGS.md`) and literature (`RESEARCH_SURVEY.md`). It makes the emulator-vs-hybrid decision explicitly, specifies the architecture and conservation placement, the data generation, the training and stability strategy, and the evaluation — all phased with checkpoints, prototype-on-one-cell first, code generalizable to many cells.

---

## 1. The decision: a phased HYBRID, with an added energy-balance closure

**Decision.** Build a **hybrid**: **emulate the slow, expensive, path-dependent individual-tree trait/size dynamics** (as per-cell distributions) with ML, **keep LPJmL-FIT's physical daily biophysical core** (photosynthesis, water balance, soil thermal — conserving by construction), and **add a new conservation-constrained surface-energy-balance + skin-temperature closure** to supply the ESM interface the model lacks. Keep full fast-core *emulation* as an optional later optimization, gated on profiling and on building a differentiable core.

### Why hybrid (justification against the alternatives)

1. **The constraint that originally forced hybrid is gone; the choice is now free, so decide on risk/benefit.** Daily flux/pool output is a config flag, not a code change (`SOURCE_FINDINGS.md` Q1). So we *could* train a full fast emulator. We choose not to (yet) for the reasons below.

2. **Conservation of water and carbon comes for free from the physical core.** Re-learning both budgets in a fast emulator and enforcing closure architecturally is extra work and risk. Although our targets are self-consistent (so hard constraints are *safe* here, unlike observation-trained hydrology — `RESEARCH_SURVEY.md` C.4), inheriting closure from physics is strictly lower-risk than asserting it in a network.

3. **Online-stability risk concentrates in the fast loop.** The strongest lesson in the field is that offline skill does not predict coupled stability and can anti-correlate with it (Brenowitz et al. 2020: better-offline NN crashed, worse-offline RF stayed stable). A physical fast core removes the most dangerous instability source from the coupled system.

4. **The fast biophysical core is not the compute bottleneck.** In FIT the cost is dominated by individual-tree bookkeeping (establishment, growth, allocation, mortality over many individuals × patches), not by the daily big-leaf biophysics. Emulating the *slow* part therefore captures the great majority of the achievable speed-up (cf. Natel et al. 2025 ~95% from emulating the carbon dynamics), while a fast emulator would add risk for marginal additional speed.

5. **Both routes need the energy-balance addition anyway**, so it is not a differentiator (`SOURCE_FINDINGS.md` Q3: no H, no T_skin, no Rn closure in the model).

6. **The slow distributional emulator is the scientific novelty and the highest-value contribution** — no published ML emulator reproduces a demographic/trait-based DGVM's *distributions* (`RESEARCH_SURVEY.md` A.4).

### When to revisit and emulate the fast core (explicit trigger)

Pursue fast-core emulation (Phase 7) only if **profiling at target scale shows the daily biophysical core dominates runtime**, or once a **differentiable re-implementation of the core exists** (Phase 6, F2) — at which point an ML fast component can be trained online through the differentiable host with conservation constraints, following NeuralGCM/DifferLand. Until then, the physical core is the safer, faster path to a working, conserving, coupled component.

### What "ESM-ready" realistically means here (scope honesty)

LPJmL-FIT is a **daily** model with **no surface energy balance**. Therefore:
- The trainable target is a **daily-coupled** land component. **Sub-daily** fluxes are produced by a physically-based **diurnal downscaling** layer (partitioning daily LE/H by the sub-daily radiation/temperature forcing), not by learning sub-daily physics we have no data for.
- The **energy balance (H, G, skin temperature) is new physics**, validated **out-of-model** against flux-tower data (FLUXNET/PLUMBER2) and physical closure — the source model provides no ground truth for it. **(But see below: don't build it from scratch — reuse Terrarium.jl's.)**
- The component returns to the atmosphere: **LE, H, G, T_skin, NEE, and roughness** — using two forcings LPJmL-FIT ignores: **wind and surface pressure**.

### Target ecosystem, framework, and reuse (see `ECOSYSTEM_AND_COUPLING.md` for the full assessment)

There is an existing **PIK/TUM-led, fully-Julia, Enzyme-differentiable ESM ecosystem** — **SpeedyWeather.jl** (atmosphere) + **Terrarium.jl** (land framework) + **Oceananigans.jl** + **NumericalEarth.jl** (coupler), plus **LPJmL-hybrid-photosynthesis → NeuralCrop** (differentiable Julia LPJmL photosynthesis, same group) — purpose-built to host hybrid ML land components, from the same institute as LPJmL. This validates the architecture below and sharpens the build:

- **Stack: Julia-first.** Build the fast core (F2) and the coupled/online-trainable system in Julia (Enzyme.jl, Lux.jl/Flux.jl, SciML, KernelAbstractions). The slow emulator (S) may be prototyped in Python (DRF/tabular-diffusion maturity) then ported to Julia/Lux for coupling. This supersedes the package's Python-only `environment.yml`, which is kept for the S prototype.
- **Component E: reuse Terrarium.jl's `SurfaceEnergyBalance` + `ImplicitSkinTemperature` + soil thermal/hydrology** rather than building new physics — it provides the skin temperature, the consistent ground heat G, and the aerodynamic (wind/pressure) machinery the interface needs.
- **Component F: use LPJmL-hybrid-photosynthesis / NeuralCrop as the differentiable-core template** (the differentiable λ root-find via Enzyme adjoints is already worked out by the same group).
- **Component S is unchanged and remains the novelty** (neither Terrarium's PALADYN-lite single-tile vegetation nor the single-PFT photosynthesis repo emulates trait/size *distributions*); implement it as Terrarium `AbstractVegetation`/`AbstractVegetationDynamics` processes.
- **Coupling target:** offline **PLUMBER2/FLUXNET first**; then **SpeedyWeather.jl** (via Terrarium/NumericalEarth) for the online-coupled differentiable-training demonstration; **CliMA (ClimaCoupler+ClimaLand)** or **ICON/JSBACH** for an eventual *real* ESM land component. Caveat: SpeedyWeather has **no carbon cycle**, so NEE is diagnostic-only in that atmosphere. Licensing (LPJmL AGPL-3.0 ↔ EUPL-1.2 ↔ MIT) needs a written legal read before embedding code across repos.

---

## 2. Architecture

Three components around **one authoritative shared state**. Data flows respect the handover §2 rules: one copy of each state; slow→fast passes *boundary conditions* (structure), not fluxes; fast→slow passes the *conserved* carbon increment; cross-domain identities (LE = λ·ET) are derived, not co-predicted.

```
              ┌─────────────────────────────────────────────────────────────┐
   sub-daily  │  ATMOSPHERE (ESM)   SWdown, LWdown, Tair, qair, wind, psurf, │
   forcing ──►│                     precip, CO2                              │
              └───────────────┬─────────────────────────▲───────────────────┘
                              │ (daily aggregates + diurnal cycle)  │ LE, H, G, T_skin, NEE, z0
                              ▼                                     │
        ┌───────────────────────────────┐        ┌──────────────────────────────┐
        │  F: FAST physical core (DAILY) │        │  E: ENERGY-BALANCE CLOSURE   │
        │  (kept from LPJmL-FIT)         │  LE=λ·ET│  (NEW; ML-assisted physics)  │
        │  photosynthesis→GPP→NPP        ├────────►│  solve T_skin; partition     │
        │  water balance (ET, runoff,    │  A=Rn−G │  A=Rn−G into LE,H,G (hard    │
        │  drainage, interception)       │◄────────┤  closure); diurnal downscale │
        │  snow + soil thermal (enthalpy)│  g_a(z0,│  needs wind + psurf          │
        └──────┬───────────────▲────────┘  wind)  └──────────────────────────────┘
               │ NPP delivered  │ structure (LAI, height, z0,
               │ (annual bm_inc)│ rooting depth, Vcmax, FPC,
               ▼ + soil-moisture│ representative individuals)
        ┌───────────────────────┴────────┐
        │  S: SLOW distribution emulator  │   ── ONE SHARED STATE ──────────────
        │  (ML; ANNUAL step)              │   soil water w[23], snowpack,
        │  p(traits,size | drivers,state) │   soil enthalpy enth[23],
        │  + count N; allocate NPP        │   carbon pools (veg 7/tree, SOM
        │  (softmax) → pools/mortality    │   fast/slow×22, litter/PFT)
        └─────────────────────────────────┘   lives with F; S reads/writes veg C
```

### 2.1 Shared state vector (single source of truth)

From `SOURCE_FINDINGS.md` Q4. The emulator's state must match the model's so re-anchoring and validation are exact:

- **Soil water:** `w[23]` (fraction of WHC), `w_fw[23]` (free water, mm), `w_evap`, `rw_buffer`.
- **Snow:** `snowpack` (mm w.e.).
- **Soil thermal:** `enth[NHEATGRIDP]` (J/m³, fundamental; =23 only because GPLHEAT=1 — key to NHEATGRIDP) → `temp[]` derived; ice states `ice_depth/ice_fw/freeze_depth[23]`.
- **Vegetation carbon (per tree, 7 pools):** leaf, sapwood, heartwood, root, sapwood_bg, heartwood_bg, debt — represented in S as the **joint distribution over individuals** (traits × size × pools) + count N.
- **Soil/litter carbon:** SOM `pool[22]{fast,slow}`; litter per PFT (ag leaf + wood[4], agsub, bg).
- **Cell climate memory:** the 20-year running means (`Climbuf`: `atemp_mean20, mtemp20[12], mprec20[12], mpet20[12], mtemp_min20, gdd5`) — a conditioning input to S, the principal source of multi-year autocorrelation.

**Rule:** each of these exists exactly once. F owns and integrates soil water/snow/thermal and the SOM/litter pools; S owns the vegetation distribution and *allocates* into the veg carbon pools. No component keeps a private copy.

### 2.2 Component S — slow trait/size distribution emulator (ML)

- **Replaces:** FIT annual individual-tree dynamics (establishment, allocation, growth, mortality, allometry, trait sorting).
- **Unit & target:** the **per-cell distribution** over trees, `p(traits, size | ·)`, plus count `N`. Traits/size axes: height, stem diameter, crown area, wood density, SLA, leaf longevity, the 7 carbon pools, age. (The 50,000-patch prototype is a dense sample of exactly this within-cell distribution — ideal.)
- **Inputs (conditioning) — S is FLUX-DRIVEN, not climate-equilibrium ([ADR 0020](docs/decisions/0020-component-s-flux-driven.md)):** S maps *fluxes + state → demography*; the physical core F has already turned climate into fluxes, so S is conditioned on **what F delivered**, not on raw this-year climate. Three groups:
  1. **Primary dynamic drivers — annual *statistics* of the daily F outputs (not just means; extremes, timing, and stress-day counts, because mortality/establishment respond to those):** the delivered NPP increment **`bm_inc`** (per representative individual and PFT — also the conservation budget); **water stress** (annual accumulated `water_stress` + within-year peak/timing/stress-day counts); **temperature/heat stress** (annual `temp_stress` count of stress days + timing); **growth efficiency** (`bm_delta/leaf-area`, the greff driver); and **end-of-year and growing-season soil moisture** (from daily `swc`, not the annual mean). The four mortality drivers and their exact definitions are `[VERIFIED]` against `src/tree/mortality_tree_ind.c`, `waterstress_tree.c`, `tempstress_tree.c` — see `docs/slow_flux_conditioning_data_spec.md`.
  2. **Autoregressive state (S is recursive):** the **previous-year distribution summary** — moments/quantiles of height, diameter, crown area, wood density, SLA, leaf longevity, and the carbon pools — plus count `N`. Year *t* is conditioned on year *t−1*'s population, not regenerated from climate.
  3. **Slow / boundary inputs that F's fluxes do NOT encode:** the **20-year Climbuf memory**, **coldest-month temperature and growing-degree-days (gdd5)** (they govern establishment and which PFTs can be present), **CO₂** (held constant, [ADR 0004](docs/decisions/0004-constant-co2-regime.md)), **soil texture and depth**, and **stand age / time-since-disturbance**.
  - **Explicitly dropped as a primary driver:** this-year raw temperature, precipitation, radiation, and VPD. F has already transformed them into the fluxes of (1); re-feeding raw climate double-counts and re-opens the equilibrium-mapping OOD failure. Only the slow bioclimatic memory of (3) is kept, and only because it carries establishment/PFT-presence signal the fluxes do not.
- **Outputs:**
  1. New-year trait×size distribution + count N — but obtained by **advancing the previous population**, not regenerating it (see conservation below).
  2. **Derived cell-level structure for F** (never co-predicted — computed from the distribution via the model's own allometry, `SOURCE_FINDINGS.md` Q4e): LAI (and its seasonal max), canopy height, **roughness length z0** (via `src/lpj/roughnesslength.c`'s relation), rooting-depth profile, photosynthetic capacity (Vcmax proxy via SLA/trait relations), FPC, albedo.
  3. A small set of **representative individuals** (weighted sample) that F integrates photosynthesis over — this preserves the trait→flux linkage (different trees have different Vcmax/rooting) with minimal change to F's per-individual code.
- **Method (escalation ladder, from `RESEARCH_SURVEY.md` B):**
  - **Baseline:** Distributional Random Forest (DRF) mapping conditioning → conditional joint distribution as a weighted sample; sample trait×size draws that preserve trade-offs automatically. Separately, a **negative-binomial / ZINB count model** for establishment/mortality counts. Optionally decompose into per-trait marginals (QRF/NGBoost/GAMLSS) + a conditional copula.
  - **Escalate only if** the metric panel shows DRF/copula miss multimodal or nonlinear/tail dependence: **TabDiff/TabSyn** (joint/latent diffusion, best correlation fidelity) or a **conditional normalizing flow** (tractable likelihood), driver-conditioned. Keep the baseline as the benchmark.
- **Conservation (carbon, at the handoff) — flux-then-integrate, not regenerate.** A softmax over pool fractions conserves a pool *total*, but S's target is a re-sampled distribution over a *variable* count N, so partitioning a total does **not** by itself guarantee the drawn distribution carries the right carbon. Resolve this by making S predict **increments applied to the existing population**, MC-LSTM/flux-then-integrate style (`RESEARCH_SURVEY.md` C.3):
  1. S predicts, per surviving individual (or per size×trait class), a **growth increment** whose across-population sum is the allocated NPP: `Σ_i ΔC_i = f_alloc · bm_inc`, with `f_alloc, turnover, mortality-fraction` as softmax/bounded partitions of the delivered `bm_inc`. Growth of pools within an individual uses the same softmax-of-a-conserved-input trick (leaf/sapwood/heartwood/root allocation). `bm_inc` is thus **both** an S conditioning feature (§2.2 Inputs, group 1) **and** the conservation budget ([ADR 0020](docs/decisions/0020-component-s-flux-driven.md)): the same delivered flux both drives S and bounds what it may allocate.
  2. **Mortality** removes individuals (count from the count model); their carbon goes to litter/soil pools. **Establishment** adds saplings drawn from the FIT `Sapling` inheritance distribution, its carbon debited from the establishment flux `flux_estabc`. **Fire** (GlobFIRM is ON) removes carbon as `firec` to the atmosphere.
  3. The generative/DRF machinery models the *distribution of increments, establishment traits, and mortality*, so the new population is the old one advanced — carbon is conserved by construction because every carbon movement is an accounted flux. (Fallback if a full regenerate is ever used: project/rescale the drawn distribution onto the conserved total, a soft correction — inferior; prefer increments.)
  4. **Closure with fire + establishment (fire is ON — do not omit):** ecosystem `ΔC = NPP − Rh − firec + flux_estabc` (no harvest, `landuse="no"`); atmosphere-facing net flux `NBP_atm = Rh + firec − NPP − flux_estabc` (NEE = Rh − NPP is only the fire-free, establishment-free part). Carry `firec` and `flux_estabc` explicitly in S's bookkeeping and in the §5 closure residuals.
- **Autoregression:** year *t* conditioned on year *t−1* distribution + Climbuf. Guard against drift (Phase 6): multi-step rollout training, input-noise injection, periodic re-anchoring to full LPJmL-FIT (the LandSyMM/ecLand pattern).

### 2.3 Component F — fast physical biophysical core (kept)

- **Keeps (unchanged physics):** daily photosynthesis→GPP→NPP (per representative individual, preserving trait-dependence), water balance (transpiration, soil/interception evaporation, runoff, drainage), snow, soil thermal (enthalpy). Conserving water & carbon by construction.
- **Parameterized by S:** LAI, height, z0, rooting depth, Vcmax, FPC, and the representative-individual set — the slow→fast **boundary conditions** (structural states, not fluxes).
- **Delivers:** daily LE candidate (= λ·ET), water fluxes, soil-moisture/snow/thermal state updates; and at year-end the **annual NPP increment** (`bm_inc`) and mean water stress for S.
- **Implementation (differentiable-first — see [ADR 0014](docs/decisions/0014-differentiable-fast-core-first.md), which SUPERSEDES the earlier F1-now/F2-at-Phase-6 split below):**
  - **`F_diff` (from the start): the daily biophysics reimplemented in AD-friendly Julia with the SAME
    equations** (`src/fdiff.jl` + the shared `src/allometry.jl`). This is the coupling path. Non-smooth
    ops use documented smooth surrogates (`src/fdiff_smoothops.jl`); the λ (ci:ca) solve is a
    fixed-graph Newton whose gradient is verified against finite differences. **Enzyme reverse-mode +
    ForwardDiff both differentiate the full daily rollout** (spike validated, ~1e-11 vs FD), so the
    coupled S+F(+E) system is end-to-end differentiable for training/online rollout from Phase 3 on.
    Reuse map: [ADR 0015](docs/decisions/0015-reuse-map.md).
  - **The compiled LPJmL-FIT C binary (the former "F1") is retained ONLY as (i) the
    numerical-regression oracle F_diff must reproduce and (ii) the daily training-data generator (the
    186 GB dataset).** It is NOT the coupling path.
  - _Superseded plan (kept for the audit trail):_ ~~F1 (Phases 3–5) keep the C core, not
    differentiable; F2 (Phase 6, if needed) a differentiable rewrite in JAX/PyTorch.~~ Replaced by
    F_diff-first in Julia/Enzyme (ADR 0014).

### 2.4 Component E — surface-energy-balance + skin-temperature closure (NEW)

- **Purpose:** provide the ESM interface LPJmL-FIT lacks. Solve the surface energy balance for **one** skin temperature `T_skin` and partition available energy into LE/H/G — all consistent with that single `T_skin`.
- **Physics (single consistent surface temperature):** `Rn(T_skin) = SWdown(1−α) + LWdown − εσ T_skin⁴`; close `Rn(T_skin) = LE + H(T_skin) + G(T_skin)` with `H = ρ c_p g_a (T_skin − Tair)`, `g_a = g_a(wind, z0, stability)`. Solve for `T_skin` (Newton iteration). **G must be evaluated under `T_skin`, not under F's air-temperature boundary** — otherwise Rn, H and G refer to different surfaces and the balance is only bookkeeping, not physics. Therefore the **`E→F` skin-temperature feedback is mandatory, not optional**: re-solve F's soil-thermal top boundary with `T_skin` (replacing the native air-temperature Dirichlet BC), or recompute the ground-heat flux inside E under `T_skin` and pass it back so F's enthalpy update is consistent. This is the one place F's physics is modified.
- **Bridging LPJmL's water-limited ET (this is a real inconsistency — handle explicitly):** LPJmL's ET is water-/demand-limited equilibrium evaporation, not energy-balance-derived, so **LE is *not* a free variable we may softmax-partition** — it is set by water availability in F. Consequently **H is the residual** that closes the balance (`H = Rn − G − LE`). This is a *deliberate, documented exception* to the "no privileged residual" rule (§below / START_HERE §3 rule 4): we cannot invent water to satisfy a chosen energy split. Because PLUMBER2 flags sensible heat as the worst-modeled flux, **validate residual-H hard against FLUXNET** and allow a bounded ML correction (below). Do **not** also claim a softmax LE/H/G partition — the two are mutually exclusive; pick residual-H for the default.
- **Latent-heat and demand-cap reconciliation:** `LE = λ·ET`, using latent heat of **vaporization** (~2.50 MJ/kg) for liquid ET and latent heat of **sublimation** (~2.83 MJ/kg) for the snow/ice component (≈13% error if conflated; `permafrost:true`). If E must cap `LE ≤ Rn − G` in rare demand-limited cases, the capped water is **not silently dropped**: return the unused evaporative demand to F's water balance (leave the water in the soil-moisture reservoir) so water and energy stay consistent, and log when the cap binds.
- **ML role (optional, bounded):** learn a correction to `g_a` or to `T_skin`, **inside the closed balance** (dPL pattern) — the physics owns closure, the NN reshapes within it. Never let the NN break `Rn(T_skin) = LE + H + G`.
- **Diurnal downscaling (to sub-daily):** because F is daily, obtain sub-daily fluxes by driving E's balance with the **sub-daily** SWdown/LWdown/Tair/wind forcing at fixed daily-mean structure and soil state, i.e. **re-solve the energy balance per sub-daily step** rather than linearly distributing daily-mean LE/H (the latter mishandles the nonlinear `T_skin⁴` and stability terms — a Jensen-inequality bias, worst for nighttime outgoing longwave). No extra training data required; it is a physical downscaling.
- **New inputs:** **wind (GSWP3-W5E5 `sfcwind`, present) and surface pressure (`ps`, must be added)**, plus the atmosphere's downward SW/LW and near-surface T/q.
- **Validation:** out-of-model — physical closure residual ≈ 0 by construction; **LE, H, T_skin against FLUXNET/PLUMBER2** (the only ground truth for the added quantities).
- **Caution:** energy closure is a budget we *assert* (unlike inherited water/carbon), so apply the MC-LSTM lesson — only close a budget we can account for; validate against observations before trusting under coupling (`RESEARCH_SURVEY.md` C.4, D.4).

### 2.5 Fast↔slow interface contract (I/O signatures)

| Direction | Payload | Type | Conservation role |
|---|---|---|---|
| S → F (annual) | LAI, height, z0, rooting-depth profile, Vcmax, FPC, albedo, representative individuals | boundary conditions (structure) | none (structure, not flux) |
| S → E (annual) | albedo, z0, canopy structure (for Rn and g_a) | boundary conditions | none |
| F → S (annual) | NPP increment `bm_inc` (per rep. individual + PFT); **annual *statistics* of the daily fluxes** — water-stress accumulation + peak/timing/stress-day counts, `temp_stress` day-count + timing, growth efficiency, EOY + growing-season soil moisture (not just means) | conserved carbon + state | `bm_inc` is **both** an S conditioning feature **and** the conservation budget; S allocates exactly `bm_inc` (flux-then-integrate); S is flux-driven, not climate-driven ([ADR 0020](docs/decisions/0020-component-s-flux-driven.md)) |
| F → E (daily) | LE = λ·ET; GPP, NPP(Ra=GPP−NPP), Rh, firec (for NEE/NBP); ground-heat term | fluxes + state | LE derived from ET; carbon fluxes for the atmosphere flux |
| E → F (daily) | **T_skin (mandatory: top thermal BC), G(T_skin), g_a** | boundary + flux | makes F's ground heat consistent with the one surface temperature |
| E → ATM (sub-daily) | LE, H, G, T_skin, NBP_atm (Rh+firec−NPP−estab), z0 | fluxes + state | Rn(T_skin) = LE+H+G closed by construction; H is the residual |
| ATM → F/E | SWdown, LWdown, Tair, qair, **wind (sfcwind), psurf (ps)**, precip, CO₂ | forcing | — |

**Cross-domain identities enforced:** LE = λ·ET (predict ET, derive LE; vaporization vs sublimation λ; demand-cap water returned to F — §2.4); GPP–transpiration coupled via canopy conductance/WUE (inherited from F); carbon handoff via flux-then-integrate allocation of delivered NPP (§2.2); soil-moisture reservoir shared (F's transpiration draws it down, S reads it for establishment/mortality); one skin temperature shared by Rn, H, G.

---

## 3. Training-data generation

- **Enable daily output** (config-only, `SOURCE_FINDINGS.md` Q1c) for the fast-layer variables the plan needs: `transp, evap, interc, runoff, runoff_surf, runoff_lat, perc, seepage, swc(-layer), soiltemp(-layer), swe, gpp, npp, rh`. Keep the **`ind` tree table annual** (cost driver). Derive Ra = GPP − NPP, LE = λ·ET offline.
- **Extended Phase-1 F + mortality-driver outputs (flux-driven S — [ADR 0020](docs/decisions/0020-component-s-flux-driven.md)):** write out or reconstruct, per cell/year and **aligned to the annual `ind` distribution**, the F variables S is conditioned on: **`bm_inc` per individual and PFT**; the **four mortality drivers** (`mort_npp`, `mort_age`, `mort_water`, `mort_temp` plus the underlying `bm_delta`, `water_stress`, `temp_stress`, `bm_inc_counter`); and the **soil-moisture state**. These are already computed per individual (`tree->mort_*`, `tree->water_stress`, `tree->temp_stress`) and are in the restart image — the task is to add them to the annual `ind` output columns and/or reconstruct `water_stress`/`temp_stress` from the daily set (`transp, swc, gpp, npp` are already in the 186 GB daily data; the mortality-driver variables are the gap). **Confirm each definition against `mortality_tree_ind.c` and the `FToS` interface contract before training** — done and recorded in **`docs/slow_flux_conditioning_data_spec.md`** (`[VERIFIED]` against the C source).
- **Sampling design (decisive — `RESEARCH_SURVEY.md` A.1):** realistic driver **trajectories**, never factorial. Baseline climate is **GSWP3-W5E5 obsclim historical** (1901–2019), whose files are at absolute paths under `/p/projects/lpjml/input/...` referenced by `input_GSWP3-W5E5.js` (not a single root — see `config/paths.yaml`). For the **OOD/warming test you need a *separate*, realistic future/counterfactual trajectory** (e.g. an ISIMIP3b GCM-based scenario), **not** a synthetic temperature delta (a delta would be exactly the factorial/stylized perturbation the plan forbids), and — critically — **with CO₂ held constant** (see below). Locate and record this forcing as a data dependency (`config/paths.yaml:ood_forcing`); if none is available, the OOD test is limited to interpolation within historical variability and this must be stated. **CO₂ regime:** LPJmL-FIT here runs `with_nitrogen="no"`, so CO₂ fertilization is unbounded and future runs hold **CO₂ constant** to avoid carbon runaway. Therefore CO₂ is a near-constant driver in training and a fixed input in application; the emulator is only valid in that regime and must not be used to project CO₂-fertilization responses (record this as an inherited limitation). Also note LPJmL-FIT needs **specific humidity (huss)** and — for the added energy layer E — **wind (`sfcwind`, present) and surface pressure (`ps`, add it)**. Multi-cell sampling: stratify by biome; hold out cells **and** scenarios/time-periods.
- **Prototype first — reconcile the mechanism in DESIGN (do not assume it).** The prior planning phase's prototype was *~50,000 stochastic realizations of one location* (described as 10,000 replicate cells × 5 patches × 10 yr, 2001–2010, post spin-up) — a dense sample of the within-cell trait/size distribution, which is what S needs. **The current repo config does not reproduce that as-is:** `lpjmlfit.js` has `npatch:25`, and the `-DSINGLESITE` macro selects a *single* grid cell (`startgrid:28008`, Hainich, ≈51.1 N/10.4 E — which also differs from the "50.2 N, 10.7 E" in the prior notes). A `-DSINGLESITE` run therefore yields 25 patches/year for one cell, not 50,000 realizations. **Phase-0 DESIGN task:** choose one coherent generation mechanism for the large within-cell ensemble — either (a) reproduce the replicate-cell approach (an N-replicate grid of the same climate/soil → requires multi-cell MPI, *not* SINGLESITE), or (b) raise `npatch` on a single site and run more years/seeds — and make the patch-count / cell-count / coordinate agree across `DEVELOPMENT_PLAN`, `00_START_HERE`, `config/paths.yaml`, and the LPJmL config. Confirm the target coordinate. Only then generate data.
- **Datasets produced:**
  1. **Slow-emulator table (flux-driven — [ADR 0020](docs/decisions/0020-component-s-flux-driven.md)):** for each (cell, year), aligned to the annual `ind` distribution: the **flux-conditioning features** (delivered `bm_inc` per individual + PFT; the four mortality drivers — growth-efficiency `mort_npp`/`bm_delta`, age `mort_age`, water `mort_water`/`water_stress`, temperature `mort_temp`/`temp_stress` — from `src/tree/mortality_tree_ind.c`; and the soil-moisture state), the **within-year stress statistics** (extremes/timing/stress-day counts built from the daily set), the **slow/boundary inputs** (Climbuf, coldest-month T, gdd5, CO₂, soil texture/depth, stand age), the year-*t* trait×size distribution (all trees) + N, and the year-*(t−1)* summary. **This-year raw climate is deliberately NOT a feature** (ADR 0020). Buildable spec of record: **`docs/slow_flux_conditioning_data_spec.md`**.
  2. **Fast-core validation set:** daily forcing → daily fluxes + pool states (for validating F1 reproduces LPJmL, and for training F2).
  3. **Energy-closure reference:** independent FLUXNET/PLUMBER2 site data (LE, H, T_skin, Rn) — external, since LPJmL has no ground truth for E.
- **Reproducibility:** pin the exact LPJmL-FIT commit, config JS files, input `.clm` files, and RNG seeds; record spin-up length; verify `.clm` are daily and `lwnet` sign (`SOURCE_FINDINGS.md` open items).

---

## 4. Training & coupling/stability strategy

**Offline, per component first (necessary, not sufficient):**
- **S:** fit DRF (+ count model) on the slow table; run the distributional metric panel; escalate to generative only if warranted. Verify carbon-allocation conservation.
- **F1:** validate the kept physical core, driven by *true* LPJmL structure, reproduces LPJmL daily fluxes (a consistency check, since it *is* the same code). For F2, train the differentiable core to match F1 daily.
- **E:** fit/validate the closure against FLUXNET; confirm physical closure.

**Then online / coupled (the part that actually matters — `RESEARCH_SURVEY.md` D):**
- Couple S + F (+ E) and run **multi-year rollouts**; loss on aggregate trajectories (biomass, LAI, pools, annual fluxes) plus distributional terms.
- **Rollout-length curriculum** short→long (NeuralGCM: "critical"); **noise injection / input regularization** to damp unstable modes; **bounded outputs** (fraction allocations, positive transforms); **flux-then-integrate** for pools/storage (MC-LSTM style).
- With **F1 (non-differentiable):** do online *validation* + iterative correction — retrain S on coupled-generated states and **periodically re-anchor** to full LPJmL-FIT (LandSyMM/ecLand pattern). With **F2 (differentiable):** gradient-based online training through the host.
- **Drift diagnosis:** multi-year free-running runs vs LPJmL-FIT; a linear growth-rate/response-function proxy (Brenowitz 2020) if F2; climate-bias metrics; short-horizon skill vs long-run climate.

---

## 5. Evaluation

**Slow (distribution) — panel, never one metric (`RESEARCH_SURVEY.md` B.3):**
- Marginals: KS, 1-Wasserstein, per-trait CRPS.
- Joint/dependence: **energy score + variogram score** (the latter for correlation structure — energy score alone is insufficient), **Pairwise Correlation Difference**, real-vs-synthetic **detection AUC**.
- Physical/allometric checks: ∫ size·N ≈ stand biomass; self-thinning slope; trait ranges plausible; trait trade-off manifolds preserved.
- Autoregressive multi-year rollout error and drift.
- **Flux-driven-vs-climate-only OOD benchmark (the falsifiable success test for [ADR 0020](docs/decisions/0020-component-s-flux-driven.md)):** compare the new **flux-driven S** against the retained climate-only `DirectEmulator` benchmark on the **warm+dry OOD holdout** (the P2 holdout on which the climate-only baseline misses by ~32× the noise floor). At matched in-distribution error, the flux-driven S's per-axis panel error (KS / quantile-RMSE on the S-owned axes) must be **materially below** the climate-only baseline's — i.e. it closes the gap. **Report both side by side.** If the flux-driven S does not close the gap, ADR 0020 is falsified and must be revisited (raw-climate ablation, or diagnose the missing flux statistic).

**Fast (fluxes + budgets):**
- Daily flux accuracy vs LPJmL: ET components, GPP/NPP/Rh, soil moisture/temp, SWE.
- **Budget-closure residuals:** water `P = ET + runoff + drainage + ΔS(soil+snow+interception)`; carbon `Ra = GPP − NPP`, ecosystem `ΔC = NPP − Rh − firec + flux_estabc` and atmosphere-facing `NBP_atm = Rh + firec − NPP − flux_estabc` (**fire is ON — GlobFIRM — so `firec` and establishment `flux_estabc` must be in the residual; a fire-free `NEE = Rh − NPP` will not close**). Enable `firec`/`flux_estabc` outputs and check residuals ≈ 0 against LPJmL.

**Energy (added):** `Rn = LE + H + G` residual ≈ 0 (by construction); LE/H/T_skin vs FLUXNET/PLUMBER2; diurnal cycle plausibility.

**Dynamics / resilience (adopt the LPJ_resilience battery — `ECOSYSTEM_AND_COUPLING.md` §6):** offline flux RMSE is not enough; the slow emulator must reproduce the *dynamics*, not just yearly values.
- **Lag-autocorrelation of vegC/AGB as a function of climate** (the ~0.2-in-wet → ~0.75-in-dry gradient) and the **full ACF shape** — the sharpest test that the autoregressive memory timescale is right and **climate-dependent** (a single fixed AR timescale fails).
- **Variance/SD vs climate.**
- **Recovery/restoring rate** from a pool-perturbation experiment (zero/halve leaf/sapwood/heartwood/root, measure the exponential relaxation rate) — reuse `empirical_recovery_SB.py`.
- **Shuffle test (S0 vs S1):** verify the emulator's memory is *genuinely internal*, not merely inherited from autocorrelated climate inputs (an AR emulator can "cheat" this — a mandatory check).
- If LPJmL-FIT proves multistable: add **ramp/hysteresis** experiments (new; not in that repo).

**Coupled / online + OOD:**
- Multi-year free-running stability vs LPJmL-FIT (no drift/blow-up, **no spurious oscillations / "AC gap"** — the stiff carbon+population failure mode flagged in LPJ_resilience).
- **OOD stress test = warming + precipitation variability at (near-)constant CO₂** (NOT rising CO₂). LPJmL-FIT is run with constant future CO₂ because, without nitrogen limitation (`with_nitrogen="no"`), CO₂ fertilization is unbounded and vegetation carbon blows up — so rising-CO₂ trajectories are neither trained nor valid. Check physical plausibility (realistic ET response, no runaway water loss — cf. Wi & Steinschneider 2024) and that conservation holds.
- Evaluate on **held-out cells and scenarios** throughout.

---

## 6. Phases & checkpoints (prototype-on-one-cell first; code generalizable to many cells)

| Phase | Work | Checkpoint (gate to proceed) |
|---|---|---|
| **0. DESIGN** | Re-verify source findings; audit data; freeze the shared-state vector, interface contract, and I/O schemas in `DESIGN.md`. No heavy compute. | DESIGN.md complete; schemas frozen; findings reproduced. |
| **1. Data generation** | Enable daily output; run prototype-cell ensemble + a small biome-stratified multi-cell set; build data loaders. **Extended for flux-driven S ([ADR 0020](docs/decisions/0020-component-s-flux-driven.md)):** also emit/reconstruct the F + mortality-driver outputs (`bm_inc` per individual+PFT; `mort_npp`/`mort_age`/`mort_water`/`mort_temp` + `bm_delta`/`water_stress`/`temp_stress`; soil-moisture state) aligned to the annual `ind` table — see `docs/slow_flux_conditioning_data_spec.md`. | Raw LPJmL daily **water & carbon budgets close** (confirms the closure targets are real); slow table + fast set materialized; **the flux-conditioning columns (F + mortality drivers) are present, aligned to `ind`, and their definitions match `mortality_tree_ind.c`**. |
| **2. Slow emulator (offline, prototype cell)** | Train the **flux-driven** S (conditioned on F's delivered fluxes + AR state + slow bioclimatic boundary; **no this-year raw climate** — ADR 0020) via teacher forcing on LPJmL-FIT's true fluxes; DRF/copula + count model → metric panel; escalate if needed; verify carbon allocation conserves. Keep the climate-only `DirectEmulator` as the benchmark. | Distributional panel passes tolerances; allocation conserves NPP; **the flux-driven S beats the climate-only `DirectEmulator` on the warm+dry OOD holdout** (closes the ~32×-floor gap at matched in-distribution error — the ADR-0020 falsifiable success test), reported side by side. |
| **3. Hybrid integration F_diff + interface** | Drive the differentiable core `F_diff` (ADR 0014) with emulated structure + representative individuals; couple S↔F on prototype. (An **early one-cell spike** — `docs/phase3_fdiff_spike.md` — de-risked F_diff: correct Enzyme/ForwardDiff gradients through the daily rollout, water closes, allometry + surrogates tested.) | Coupled hybrid reproduces LPJmL biomass/LAI/flux **trajectories** within tolerance; budgets close. |
| **4. Energy-balance closure E** | Add surface energy balance + T_skin + diurnal downscaling; validate closure and vs FLUXNET. | Energy closes; LE/H/T_skin plausible vs flux towers. |
| **5. Multi-cell generalization** | Scale S to many cells (biome-agnostic, stratified); held-out cell/scenario evaluation. | Generalization metrics pass on held-out cells **and** scenarios. |
| **6. Online stability + OOD** | Gradient-based rollout training/validation **through `F_diff`** (differentiable from Phase 3, ADR 0014 — no longer an optional late rewrite); multi-year free runs; warming OOD (constant CO₂); resilience battery (§5). | Stable multi-year (no oscillations/AC-gap); plausible, conserving OOD behavior; resilience metrics preserved. |
| **7. (Optional) fast-core emulation + ESM packaging** | If profiling justifies / F2 exists: emulate fast core; package the ESM coupling interface (skin temp, fluxes, roughness, sub-daily). | Speed target met; interface spec validated. |

Each phase writes results and decisions to `MEMORY.md` and `JOURNAL.md`; each checkpoint is a stop-and-review before spending the next phase's compute.

---

## 7. Limitations & honest scope (carry these into every write-up)

- **Daily source model.** No sub-daily physics exists to learn; sub-daily fluxes come only from re-solving the energy balance E per sub-daily step at fixed daily structure/soil state (not from linearly distributing daily means — that biases the nonlinear T_skin⁴/stability terms). Intra-day variation of photosynthesis/soil moisture is not resolved. A truly sub-daily land component would need a different (sub-daily) training model.
- **Patch-identity caveat is live in the data-generating run.** `reservoir:true` in the transient branch of `lpjmlfit.js` *could* create reservoir stands that perturb the `(cell, patch-index)` positional key in affected cells. Confirm in DESIGN that no reservoir stand is created for the prototype/target cells (it should not be for pure natural vegetation, but verify); otherwise restrict to cells where the key is stable.
- **Sensible heat is a residual.** By construction H closes the asserted energy budget (§2.4); PLUMBER2 flags it as the hardest flux to get right, so its error is the least controlled part of the coupling interface — validate it hardest.
- **No native energy-balance ground truth.** H, G-as-flux, and T_skin do not exist in LPJmL-FIT; the added closure is validated out-of-model against flux towers, and its accuracy is bounded by that external data, not by LPJmL-FIT.
- **ET consistency.** LPJmL's water-limited equilibrium ET is not energy-balance-derived; the bridge (LE = λ·ET, H+G absorb the remainder) is pragmatic and must be validated; a demand-limited cap is needed.
- **Stochastic target.** FIT's patch ensemble is RNG-driven; the emulator reproduces the *distribution*, not any single realization — evaluate distributionally, not per-tree.
- **Extrapolation.** Pure-ML components do not extrapolate beyond the training driver envelope; OOD robustness relies on the physical core, climate-invariant input features, and conservation-by-construction (which helped generalization in FloeNet but is not guaranteed).
- **Constant-CO₂ regime (inherited from LPJmL-FIT).** With `with_nitrogen="no"`, CO₂ fertilization is unbounded, so LPJmL-FIT is run with **CO₂ held constant for the future**. The emulator inherits this: it is valid only at constant/near-historical CO₂ and **must not be used to project CO₂-fertilization responses**. Upside: this makes SpeedyWeather's lack of a carbon cycle a non-issue (CO₂ isn't a varying coupling variable; NEE is diagnostic-only). A future N-limited version (cf. NeuralCrop's N cycle) would be needed for CO₂-response projections.
- **Single-cell prototype scope.** Interfaces and metrics are proven on one cell first; multi-cell generalization is a separate, gated phase.
- **New forcings.** The ESM interface requires wind and surface pressure, which the underlying model never used — their treatment is new and only exercised in the added energy layer.
