# Ecosystem & Coupling Assessment: SpeedyWeather.jl, Terrarium.jl, LPJmL-hybrid-photosynthesis

Assessment of three repos the user asked about, and what they mean for this project. **Headline: they are not three unrelated tools — they are one coherent, PIK/TUM-led, fully-Julia, Enzyme-differentiable Earth-system-modeling ecosystem, purpose-built to host exactly the kind of hybrid ML land component this project is designing, and from the same institute as LPJmL.** This validates the plan's architecture and sharpens its implementation: pivot the stack to Julia, reuse Terrarium's energy balance instead of building one, use the LPJmL-hybrid-photosynthesis / NeuralCrop line as the differentiable-core template, and couple through SpeedyWeather for the online/coupled demonstration.

The ecosystem:

```
     NumericalEarth.jl  (coupler: atmosphere + ocean + sea-ice + land)
        │                     │                        │
 SpeedyWeather.jl        Oceananigans.jl          Terrarium.jl
 (atmosphere, spectral,  (ocean/numerics core,   (LAND framework: soil energy+water+C,
  Enzyme-diff, JOSS'24)   FVM, GPU, AD)            SURFACE ENERGY BALANCE + SKIN TEMP,
        │                                          modular vegetation, Enzyme-diff, GPU)
        │                                                   ▲
        └──────────── external-land coupling ───────────────┘
                     (SpeedyWeatherTerrariumExt.jl)

 LPJmL-hybrid-photosynthesis  →  NeuralCrop (arXiv 2512.20177, Dec 2025)
 (differentiable Julia LPJmL photosynthesis; NN learns λ / Vcmax; carbon-mass-balance loss)
     — same group (Boers, TUM/PIK); the differentiable-core precedent
```

All Julia, all Enzyme-AD, all GPU, EUPL-1.2 (SpeedyWeather, Terrarium) / MIT (LPJmL-hybrid-photosynthesis); LPJmL itself is AGPL-3.0.

---

## 1. LPJmL-hybrid-photosynthesis (TUM-PIK-ESM) — REUSE: yes, as the differentiable-core template

**What it is.** A Julia reimplementation of LPJmL's photosynthesis + water/temperature stress + radiation (Philipp Hess, Boers group, ~2022–2023, MIT). Same Haxeltine & Prentice (1996) co-limitation equations and standard LPJmL parameter constants as our C source. It makes the internal **λ (ci:ca ratio) solve swappable** — `solver` (differentiable Newton via `SciMLSensitivity` `SteadyStateAdjoint(autojacvec=EnzymeVJP())`), `bisection` (LPJmL's own method), `constant`, or `hybrid` (a small Flux MLP predicts λ). Stack: Flux.jl, Enzyme.jl + Zygote.jl, NonlinearSolve.jl, KernelAbstractions/CUDA (GPU). In the public repo the NN is an **offline surrogate** of the solver's λ (inputs: temperature + sunshine only), not end-to-end.

**Successor (more important): NeuralCrop** (arXiv:2512.20177, Dec 2025, same group). Fully differentiable, **end-to-end "online" training**; NNs parameterize **λ and Vcmax**; a **neural-ODE for carbon allocation**; an explicit **carbon-mass-balance constraint loss**; **two-stage training (pre-train on LPJmL output → fine-tune on FLUXNET/AmeriFlux/ICOS eddy-covariance fluxes)**; 365-day rollouts. This is essentially a sibling of what our plan proposes for the differentiable core. Code "will be available on GitHub when published" — not yet public.

**Reuse for us.**
- **Direct template for the differentiable fast core (F2).** The hardest engineering step — differentiating through the implicit λ root-find with Enzyme adjoints — is already worked out (`src/photosynthesis.jl:solve_for_λ`). Copy/study that pattern.
- **Injection-point design.** The swappable λ interface (physics-solver ↔ ML-surrogate ↔ analytic) is a clean pattern that keeps ML output physically bounded because the physics still computes the fluxes from λ. Mirrors our "NN supplies bounded closures the physics consumes" principle.
- **Parameter/equation cross-check.** `src/default_parameters.jl` gives LPJmL constants and H&P-1996 implementations to validate a differentiable rewrite against our C/FIT source.
- **Training recipe & methodology.** NeuralCrop's pre-train-on-LPJmL → fine-tune-on-FLUXNET, carbon-mass-balance loss, and rollout training map almost 1:1 onto our Phase-4/6 plans (validate E against FLUXNET; online rollout).

**Caveats.** It is **standard LPJmL v5, single C3 PFT** — not FIT's flexible-trait continuum (our slow emulator S remains the novel part it does not address). Stale stack (Julia 1.8; deprecated CUDAKernels/KernelGradients) — expect a port to a current Lux.jl + Enzyme + KernelAbstractions stack. No conservation guarantees in the public repo (that's NeuralCrop). **Action: engage the group (same institution) and track/collaborate on NeuralCrop rather than re-deriving the differentiable core from scratch.**

---

## 2. Terrarium.jl (NumericalEarth / PIK FutureLab-AI + TUM) — REUSE: yes, high value; it supplies the physics LPJmL-FIT lacks

**What it is.** "A framework for building next-generation differentiable and GPU-accelerated land and ecosystem models in Julia … developed alongside SpeedyWeather.jl and Oceananigans.jl as the land component of a new … Earth System Model." Built on Oceananigans.jl (FVM numerics, `Field`s, grids, `Simulation`/`OutputWriters`), device-agnostic via KernelAbstractions, Enzyme-AD-oriented (Reactant/XLA). Led by Groenke (CryoGrid.jl), Gelbrecht (SpeedyWeather/ML), Badri — **PIK + TUM, same institute as LPJmL**. v0.1.3, actively developed, EUPL-1.2, but "not production-ready — expect breakage."

**The decisive point for us — it already implements what LPJmL-FIT lacks:**
- **A surface energy balance** (`SurfaceEnergyBalance`: closes Rnet + H + LE − G = 0) with a **prognostic skin temperature** (`ImplicitSkinTemperature`, Newton solve, fixed 5-iteration budget for GPU), bulk-aerodynamic turbulent fluxes, radiative partitioning, albedo — i.e. **our component E already exists here, GPU/AD-ready.**
- Two-phase (freezing) soil **thermal** conduction and Richards-equation **hydrology** (Brooks–Corey / van Genuchten / SURFEX) — more complete than LPJmL's, and providing the ground-heat flux G consistently.
- A modular **vegetation** stack of `Abstract*` process interfaces (`AbstractPhotosynthesis`, `AbstractStomatalConductance`, `AbstractAutotrophicRespiration`, `AbstractPhenology`, `AbstractVegetationCarbonDynamics`, `AbstractVegetationDynamics`, `AbstractRootDistribution`, `AbstractPlantAvailableWater`) — currently PALADYN-derived (also PIK), single-tile, simpler than LPJmL-FIT.
- A documented **coupling API** (indirect via shared variable names; direct via passing processes) and a `PrescribedAtmosphere` forcing interface (reads air T, pressure, humidity, wind, rain/snow, SW↓, LW↓, CO₂ — e.g. ERA5-Land). Global runs via `ColumnRingGrid` on a SpeedyWeather RingGrid (built for SpeedyWeather coupling).

**Reuse for us (this reshapes the plan's Component E and F choices).**
- **Adopt Terrarium's SEB + skin temperature + soil thermal/hydrology as the physical substrate.** Our plan's "add a new surface-energy-balance closure (E)" becomes "**reuse Terrarium's SEB/skin-temperature**," eliminating the biggest new-physics build. It also supplies a consistent G (fixing the plan's D2 concern — one skin temperature for Rn/H/G).
- **Implement the LPJmL-FIT-derived hybrid vegetation as Terrarium `Abstract*` processes.** The slow trait-distribution emulator S maps onto `AbstractVegetationDynamics`/`AbstractVegetation`; the fast photosynthesis onto `AbstractPhotosynthesis`/`AbstractStomatalConductance`. Indirect coupling (share `leaf_area_index`, `gross_primary_production`, `plant_available_water`, `carbon_vegetation`, `ground_temperature`) lets us integrate incrementally and test in isolation.
- **Inherit grid/GPU/AD/coupling infrastructure** (`ColumnRingGrid`, Oceananigans I/O, Enzyme path) — and the SpeedyWeather coupling route for free.

**Caveats.** v0.1.x, breaks often — treat as a co-development/learn target, not a frozen dependency yet. Full-model AD is aspirational (validated for soil heat conduction so far). Live atmosphere coupling is roadmap (only prescribed forcing today). Vegetation is single-tile PALADYN-lite — Terrarium *hosts* our vegetation science, it does not replace it. **License: EUPL-1.2 (copyleft) vs LPJmL AGPL-3.0 — likely compatible (EUPL lists AGPLv3 as compatible) but get a written legal read before embedding code.**

---

## 3. SpeedyWeather.jl (Klöwer, Gelbrecht et al.) — COUPLING TARGET: yes, for the methodology/online demonstration

**What it is.** A pure-Julia spectral atmospheric GCM of **intermediate complexity** ("research playground"), a modern reinvention of SPEEDY. Model hierarchy (barotropic → shallow-water → primitive dry/wet); spectral transform + sigma coordinate; convection, large-scale condensation, single-band SW/LW radiation, boundary layer, bulk surface fluxes. JOSS 2024 (Klöwer et al., doi:10.21105/joss.06323). EUPL-1.2, actively developed (v0.21, mid-2026), Float32/GPU, and being made **end-to-end differentiable with Enzyme** (DJ4Earth, Moses et al. 2026 JAMES; EGU26 abstract by Gelbrecht/Klöwer/Groenke/Boers).

**Why it fits (best-aligned for a coupled-differentiable demo):**
- **A documented external-land-model interface already exists** — `SpeedyWeather.LandModel(spectral_grid, external_model)` wraps any external land model, with a working template in `ext/SpeedyWeatherTerrariumExt.jl` (push atmospheric forcings → sub-cycle the land integrator → copy outputs back).
- **Prescribed-flux coupling hooks** (`PrescribedLandHeatFlux`, `PrescribedLandHumidityFlux`) inject the land's sensible/latent heat directly as atmospheric tendencies — so our emulator's LE/H drive the atmosphere.
- **Exchange variables ≈ our interface contract:** atmosphere→land gives SW↓/LW↓, air T, humidity, wind, surface pressure, precip (and a CO₂ slot); land→atmosphere accepts LE, H, ground heat, and skin temperature. This matches the plan's §2.5 table closely.
- **Enzyme end-to-end differentiability** (validated gradients, checkpointing) — the prerequisite for online/coupled gradient-based training (the plan's Phase 6 / F2).
- **Same ecosystem:** shares RingGrids + Enzyme toolchain with Terrarium; same PIK/TUM group as LPJmL. Our LPJmL-FIT-derived component slots into a stack built to receive it.

**Limitations (why it is a prototype atmosphere, not a "real ESM"):**
- **No carbon cycle / no prognostic atmospheric CO₂.** CO₂ is a global scalar, not yet radiatively active; there is **no atmospheric carbon budget, so NEE from our land has no feedback path** (carry NEE as a diagnostic only). True carbon-climate feedback needs CliMA or ICON.
- **Skin temperature** is currently the top-soil-layer temperature (explicit TODOs for a proper skin-T); **roughness** is a field but the default drag ignores it — both low-effort wiring, not blockers.
- Intermediate-complexity physics (single-band radiation, SPEEDY-heritage convection); pre-1.0 API churn; GPU and long-trajectory AD still maturing (run coarse, e.g. T31–T85, for tractable differentiable coupling).

---

## 4. Coupling-target decision

| Target | Lang / AD | Land coupling | Carbon | Effort | Best for |
|---|---|---|---|---|---|
| **SpeedyWeather.jl** | Julia / **Enzyme end-to-end (WIP)** | **Documented external-land wrapper + prescribed-flux hooks; vars ≈ our list** | **None** (NEE has no feedback) | **Low–med** | **Methodology / online-coupled differentiable demo** |
| **CliMA (ClimaCoupler + ClimaLand + ClimaAtmos)** | Julia / not end-to-end AD (calibrate via EnsembleKalmanProcesses) | **Most mature Julia land coupling** (water/energy/momentum/carbon); ClimaLand has soil CO₂, canopy, snow | **Yes** | Med | **Eventual real Julia ESM** (train offline / EKI, not online AD) |
| **ICON-ESM / JSBACH** | Fortran / not differentiable | Real ESM; HYBRID-JSBACH4 embeds NN GPP/transpiration (pretrained offline) | Yes | High | Closest analog to a **production ESM land component** |
| **NeuralGCM** | Python/JAX, diff | **No prognostic land** (prescribed SST + learned surface embedding) | No land | High (cross-lang) | **Inspiration only** |
| **Offline PLUMBER2 / FLUXNET** | any (land alone) | none (no atmosphere) | Yes (flux data) | **Lowest** | **Do first, always** — validate fluxes with zero coupling risk |

**Recommendation.**
- **Do offline PLUMBER2/FLUXNET validation first** (already the plan's Phase 4 for E) — no coupling, no atmosphere gradients, validates LE/H/T_skin/NEE.
- **Couple to SpeedyWeather.jl (via Terrarium / NumericalEarth.jl) for the online/coupled stability + differentiable-training demonstration** (plan Phase 6). It is the top pick for that purpose and matches the ecosystem.
- **For an eventual real ESM land component, target CliMA** (mature Julia land coupling with carbon; calibrate offline / via EnsembleKalmanProcesses since it is not end-to-end differentiable) **or ICON/JSBACH** (Fortran, non-differentiable, closest to production, HYBRID-JSBACH4 precedent). Treat **NeuralGCM as inspiration only** (no land model, JAX/Python).

---

## 5. Does the current plan fit? Yes — architecture unchanged; implementation sharpened

The plan's core design is **validated** by this ecosystem (hybrid: emulate slow trait/size distributions; keep a conserving fast biophysical core; add an energy-balance + skin-temperature closure; conserve by construction; offline-then-online/rollout training with a differentiable host). The changes are to the *stack and build-vs-reuse*, not the architecture:

1. **Framework: pivot to Julia-first.** The target ecosystem is Julia + Enzyme AD end-to-end. Recommendation: build the **fast core (F2) and the coupled/online-trainable component in Julia** (Enzyme.jl, Lux.jl/Flux.jl, SciML, KernelAbstractions). The **slow distributional emulator (S)** can still be prototyped in Python (DRF, tabular diffusion are Python-mature) and then ported to Julia (Lux.jl) for the coupled system — or built in Julia from the start. This supersedes the package's default Python/PyTorch(+JAX) `environment.yml` (kept only for the S prototype).
2. **Component E (energy balance): reuse Terrarium's `SurfaceEnergyBalance` + `ImplicitSkinTemperature` + soil thermal/hydrology** instead of building new physics. This resolves the plan's D2 (one consistent skin temperature for Rn/H/G) and removes the largest new-build risk. It also gives the ground-heat flux G and the aerodynamic (wind/pressure) machinery our exchange interface needs.
3. **Component F (fast core): use LPJmL-hybrid-photosynthesis / NeuralCrop as the differentiable-core template.** F1 (keep the C core) is still used for **fast training-data generation and validation**; the differentiable F2 target is Julia with a head-start from the same group's code.
4. **Component S (slow trait/size distribution emulator): unchanged — this is the novelty.** Neither Terrarium (PALADYN-lite, single-tile) nor LPJmL-hybrid-photosynthesis (single C3 PFT) emulates individual/trait distributions. S is implemented as Terrarium `AbstractVegetation`/`AbstractVegetationDynamics` processes, providing structure (LAI, height, z0, rooting depth, Vcmax, FPC) to Terrarium's SEB and photosynthesis, and allocating delivered NPP via flux-then-integrate (conservation as designed).
5. **Coupling / online training: concrete now.** "Online coupled rollout training" = couple S+F(+Terrarium SEB) to **SpeedyWeather** through the external-land interface, differentiate with **Enzyme**, use a short→long rollout curriculum (the plan's §4). Offline PLUMBER2/FLUXNET first.
6. **Carbon-feedback caveat:** SpeedyWeather has no atmospheric carbon budget, so NEE is diagnostic-only in the prototype atmosphere; real carbon-climate feedback needs CliMA/ICON.
7. **Licensing:** LPJmL AGPL-3.0, LPJmL-hybrid-photosynthesis MIT, Terrarium/SpeedyWeather EUPL-1.2. Combining is likely workable (EUPL lists AGPLv3 as compatible) but **get a written legal read before embedding code across these.**

### Revised phase mapping (delta to `DEVELOPMENT_PLAN.md` §6)

- **Phase 0 DESIGN** — add: confirm the Julia-stack decision; study Terrarium's SEB/skin-temp + coupling API and the LPJmL-hybrid-photosynthesis differentiable-λ pattern; open contact with the Terrarium/SpeedyWeather authors (same institute); start the EUPL↔AGPL license review.
- **Phase 1 Data gen** — unchanged (C LPJmL-FIT, daily output).
- **Phase 2 Slow emulator (offline)** — unchanged; Python prototype acceptable; plan the Julia/Lux port.
- **Phase 3 Hybrid integration** — implement S + fast photosynthesis as Terrarium `Abstract*` processes; use Terrarium soil/hydrology as the shared state.
- **Phase 4 Energy balance** — **reuse Terrarium SEB + skin temperature** (don't build); validate against FLUXNET/PLUMBER2 (offline).
- **Phase 5 Multi-cell** — use `ColumnRingGrid`.
- **Phase 6 Online + OOD** — couple to **SpeedyWeather** via the external-land interface; Enzyme rollout training; multi-year free runs + warming OOD.
- **Phase 7 Real-ESM packaging** — target CliMA (offline/EKI calibration) or ICON as the production path; SpeedyWeather remains the differentiable-methodology platform.

### Immediate recommended actions
1. **Talk to the Terrarium.jl / SpeedyWeather.jl authors** (Groenke, Gelbrecht, Badri; Klöwer) — same PIK/TUM ecosystem, actively seeking collaborators; this is a co-development opportunity, not just a dependency.
2. **Track NeuralCrop** (arXiv:2512.20177) and request code / collaboration — it is the differentiable-LPJmL-core sibling of this project.
3. **Get a written EUPL-1.2 ↔ AGPL-3.0 licensing read** before embedding code across repos.
4. **Prototype**: implement one LPJmL-FIT process behind a Terrarium `Abstract*` interface, indirectly coupled, validated against a Terrarium `LandModel` run with ERA5-Land forcing; and reproduce the differentiable-λ solve from LPJmL-hybrid-photosynthesis.

---

## 6. Update — NeuralCrop.jl is public; LPJ_resilience; and the constant-CO₂ constraint

**NeuralCrop.jl** (https://github.com/yunan-l/NeuralCrop.jl) — the code for arXiv:2512.20177, author **Yunan Lin** (Boers group; co-authors incl. the PIK LPJmL developers Müller & Heinke). It is a **differentiable, GPU (KernelAbstractions), Julia 1.10** reimplementation of LPJmL trained end-to-end via **Zygote** (Enzyme is listed but unused), with **Lux.jl** NNs and **neural-ODEs** (custom differentiable Euler). NN-parameterized: **λ (ci:ca), Vcmax, storage-carbon allocation (NODE), litter/soil C&N turnover (NODE), soil-moisture residual (NODE)**. Training = **pretrain on LPJmL output → fine-tune on eddy-covariance fluxes (FLUXNET2015/CH4, AmeriFlux, ICOS)**, 365-day rollout (TBPTT), ~82× speedup. Conservation is **soft** (architectural residual-pool closure + a mass-balance loss described in the paper).

Reuse verdict — **authoritative reference + parts bin, not a drop-in fast core:**
- **Crop-only.** Wheat/rice/maize/soybean; **no trees, no FIT individuals, no allometry/establishment/mortality/light competition.** Representing FIT trees is the big build it does not provide.
- It encodes **LPJmL**, not LPJmL-FIT equations.
- The **public training/loss code is a scaffold, not turnkey** (signature mismatches; no trained weights; empty test suite; no spin-up); the hybrid path won't run as-shipped.
- **License CC BY-NC 4.0 (NonCommercial)** — a real blocker for building on the code; contact the author for a code-appropriate relicense/permission.
- **Directly reusable:** the differentiable LPJ **C3/C4 photosynthesis with NN λ/Vcmax** (generic to vegetation, trees included), the **MLP/NODE + differentiable-Euler infrastructure**, `KernelAbstractions` launch wrappers, input **normalization**, the **batched rollout training loop**, and the "detach physics via `Zygote.ignore()`, differentiate only NN outputs" idiom. Take the **two-stage pretrain→fine-tune + mass-balance-loss methodology** wholesale.
→ Net: it moves the differentiable-core (F2) from "design it" to "adapt a same-group reference implementation for FIT trees," reusing its photosynthesis + NODE + rollout machinery. Combined with **LPJmL-hybrid-photosynthesis** (the differentiable λ-solve precedent) and the not-yet-public tree work, this is a strong head start — but the tree/FIT/individual layer and hard conservation are still ours to build.

**LPJ_resilience** (https://github.com/TUM-PIK-ESM/LPJ_resilience) — code for **Bathiany, Nian, Drüke & Boers (2024), *Global Change Biology* 30(12):e17613** (resilience indicators of tropical forests in LPJmL). Python + CDO; analyses **standard LPJmL** (not FIT) but resolves per-individual pools, population density, and per-PFT traits. Two things we take from it:
- **An evaluation battery for the emulator's *dynamics*** (add to `DEVELOPMENT_PLAN.md` §5): lag-autocorrelation of vegC/AGB as a function of climate (the observed/simulated ~0.2-wet → ~0.75-dry gradient), full ACF shape, variance/SD, **recovery/restoring rate from a pool-perturbation experiment**, and crucially a **shuffle test (S0 vs S1)** that verifies the emulator's memory is *genuinely internal* and not merely inherited from autocorrelated climate forcing (an autoregressive emulator can "cheat" this). If LPJmL-FIT is multistable, add ramp/hysteresis experiments (not in this repo).
- **A design warning.** The finding: LPJmL forest memory comes from **slow woody-carbon accumulation (sapwood+heartwood) + climate-dependent population turnover** with a **state/climate-dependent relaxation timescale** — so the slow emulator must carry sapwood/heartwood C and population density explicitly and condition its memory on climate/state (a single fixed AR timescale will fail). The repo's own code comments warn the coupled carbon+population system is **stiff and prone to spurious oscillations / an "AC gap" / blow-up** when the balance is approximated — the exact autoregressive failure mode to guard against (multi-step rollout training, bounded outputs, flux-then-integrate, re-anchoring). License: **none** (all rights reserved) — contact authors before reusing code.

**The constant-CO₂ constraint (user-confirmed, important).** LPJmL-FIT here runs with **`with_nitrogen="no"`**, and is run with **CO₂ held constant for the future** because, without nitrogen limitation, CO₂ fertilization is unbounded and vegetation carbon "blows up" as CO₂ rises. Consequences for the plan:
- **The SpeedyWeather no-carbon-coupling limitation is a non-issue** for now — CO₂ isn't a varying coupling variable anyway; carry NEE as a diagnostic.
- **The OOD/warming test is warming + precipitation variability at (near-)constant CO₂**, *not* a rising-CO₂ trajectory. This aligns with the LPJ_resilience precip×temperature experiments and its climate-dependent-memory result.
- **Inherited limitation:** the emulator is only valid in the constant/near-historical-CO₂ regime it is trained on; it must **not** be used to project CO₂-fertilization responses. State this in every write-up. (NeuralCrop, by contrast, *has* an N cycle — a possible future route if N-limited CO₂ response is ever needed.)

## Sources
- NeuralCrop.jl: https://github.com/yunan-l/NeuralCrop.jl ; paper arXiv:2512.20177 (https://arxiv.org/abs/2512.20177)
- LPJ_resilience: https://github.com/TUM-PIK-ESM/LPJ_resilience ; Bathiany et al. 2024, GCB 30(12):e17613, doi:10.1111/gcb.17613
- LPJmL-hybrid-photosynthesis: https://github.com/TUM-PIK-ESM/LPJmL-hybrid-photosynthesis (README, `src/photosynthesis.jl`, `src/water_stressed.jl`, `src/neural_network.jl`, `src/default_parameters.jl`, `Project.toml`); NeuralCrop arXiv:2512.20177 (https://arxiv.org/abs/2512.20177); group pubs https://www.asg.ed.tum.de/en/esm/publications/
- Terrarium.jl: https://github.com/NumericalEarth/Terrarium.jl ; docs https://numericalearth.github.io/Terrarium.jl/dev/ (numerical_core, core_interfaces, coupling_processes, models/land_model, processes/surface_energy/{surface_energy_balance,skin_temperature}, processes/atmosphere/atmosphere, processes/vegetation/vegetation, running/reactant); org https://github.com/orgs/NumericalEarth/repositories (NumericalEarth.jl coupler)
- SpeedyWeather.jl: https://github.com/SpeedyWeather/SpeedyWeather.jl ; docs https://speedyweather.github.io/SpeedyWeatherDocumentation/stable/ (land, surface_fluxes, differentiability); `ext/SpeedyWeatherTerrariumExt.jl`, `src/parameterizations/surface_fluxes/heat.jl`; JOSS Klöwer et al. 2024 doi:10.21105/joss.06323
- Coupling alternatives: NeuralGCM (Kochkov et al. 2024, Nature, doi:10.1038/s41586-024-07744-y); CliMA ClimaCoupler.jl / ClimaLand.jl / EnsembleKalmanProcesses.jl (github.com/CliMA); HYBRID-JSBACH4 (ElGhawi et al. 2025, JAMES, doi:10.1029/2025MS005102); DJ4Earth (Moses et al. 2026, JAMES, doi:10.1029/2025MS005615); PLUMBER2 (Ukkola et al. 2022, ESSD 14, 449)
