# START HERE — Claude Code Agent Brief: ESM-Ready LPJmL-FIT Hybrid Land Component

You are a Claude Code agent with access to (a) the **LPJmL-FIT source code** at `/home/jamirp/waldspektrum` (this repo) and (b) a **PIK HPC cluster** with CPU (Intel MPI) and GPU nodes. Your job is to **build, train, and validate an ESM-ready hybrid land-surface component derived from LPJmL-FIT**, working autonomously and safely, checkpoint by checkpoint.

This brief is self-contained. Read it fully, then read the four documents in §1 before touching heavy compute.

---

## 0. Mission in one paragraph

Build a **hybrid** land component: **emulate the slow, expensive individual-tree trait/size dynamics** of LPJmL-FIT as **per-cell distributions** (ML); **keep LPJmL-FIT's conserving daily biophysical core** (photosynthesis, water, soil thermal); and **add a conservation-constrained surface-energy-balance + skin-temperature closure** that LPJmL-FIT lacks, so the component can drive an atmosphere (return LE, H, G, skin temperature, NEE, roughness). Conservation of water/carbon comes from the physical core; the energy budget is closed by construction in the new layer. Prove it on one prototype cell first; write code that generalizes to many cells.

The emulator-vs-hybrid decision is **already made and justified** — do not re-open it unless Phase-6 profiling contradicts the assumptions (see `DEVELOPMENT_PLAN.md` §1). Your job is execution, verification, and honest reporting.

---

## 1. Required reading (in this order) — do this first

1. **`00_START_HERE.md`** (this file) — workflow, rules, first actions.
2. **`SOURCE_FINDINGS.md`** — verified answers to the feasibility questions (temporal resolution, enable-able daily outputs, forcing consumed, ET/energy scheme, state vector, carbon pools, patch identity). Two facts drive everything: **daily output is a config flag**, and **the model has no surface energy balance (no H, no skin temperature)**.
3. **`DEVELOPMENT_PLAN.md`** — the architecture (components S/F/E), conservation placement, fast↔slow interface, data generation, training/stability strategy, evaluation, and the **phased plan with checkpoints (§6)** you will follow.
4. **`RESEARCH_SURVEY.md`** — the state of the art and the concrete lessons behind the design (distribution emulation, conservation-by-construction, offline≠online stability).
5. **`ECOSYSTEM_AND_COUPLING.md`** — the target Julia ESM ecosystem (SpeedyWeather.jl + Terrarium.jl + NumericalEarth.jl + LPJmL-hybrid-photosynthesis/NeuralCrop), what to **reuse vs build**, the **coupling-target** decision, and how the plan's stack changes. **Read this before choosing the implementation stack.**

Then read the config in **`config/`** (`paths.yaml`, `hpc_slurm.yaml`, `environment.yml`) and confirm/fill the values marked `TODO`.

**Stack note:** the target ecosystem is **Julia + Enzyme AD**. Build the fast core and the coupled/online-trainable system in Julia; the slow emulator (S) may be prototyped in Python then ported. **Reuse Terrarium.jl's surface energy balance + skin temperature** (component E) rather than building it, and use **LPJmL-hybrid-photosynthesis/NeuralCrop** as the differentiable-core template. Details and the licensing caveat: `ECOSYSTEM_AND_COUPLING.md`.

---

## 2. Workflow: DESIGN.md first, compute second

**Do not launch spin-up runs, large data generation, or model training until you have written and self-reviewed `DESIGN.md`.** Cheap investigation before expensive compute.

Your first work product is **`DESIGN.md`**, containing:
- Re-verification of the two load-bearing source findings (do it yourself; cite file:line): (i) daily output works via `"timestep":"daily"` with `withdailyoutput` auto-enabling (see `src/lpj/fscanoutput.c`, `iterateyear.c`, `getmintimestep.c`, `fwriteoutput.c`); (ii) no `sensible`/`skin_temp`/`netrad`/energy-balance in core `src/`, and no LE/H/Rn in `par/outputvars.js` (ET is Priestley–Taylor equilibrium; soil temp uses air-temp Dirichlet BC).
- The **frozen shared-state vector** and the **fast↔slow interface contract** (I/O signatures), matching `DEVELOPMENT_PLAN.md` §2.1/§2.5 to the actual structs.
- The **data schema** for the slow-emulator table, fast-core validation set, and the energy-closure reference.
- The exact **LPJmL-FIT build + run recipe** you validated (see §4), and the **resolved input-data paths** (the biggest external dependency — see §4.2).
- Confirmation of the open items in `SOURCE_FINDINGS.md` ("Open items"): `.clm` are daily, `lwnet` sign, PET constants, soil-layer band counts, no reservoir-stand creation in the prototype config.

Have `DESIGN.md` reviewed (spawn a verification subagent, or self-review adversarially) before Phase 1.

---

## 3. Non-negotiable engineering rules (conservation & consistency built in from the start)

These are not optional polish; they are the reason the project can work when coupled. Retrofitting them later fails (see `RESEARCH_SURVEY.md` D.1).

1. **One authoritative shared state.** Soil moisture, snow, soil enthalpy, carbon pools exist exactly once (owned by the fast core). No component keeps a private copy. (`DEVELOPMENT_PLAN.md` §2.1.)
2. **Coupling variables are conserved and derived, not co-predicted.** The slow model **advances the existing population with increments that sum to the NPP the fast core delivered** (flux-then-integrate, not regenerate-then-hope) — carbon cannot be invented or destroyed at the handoff (`DEVELOPMENT_PLAN.md` §2.2). Latent heat is **derived** as LE = λ·ET (predict ET, derive LE; correct λ for sublimation vs vaporization), never predicted independently.
3. **Slow → fast passes boundary conditions (structure), not fluxes** (LAI, height, roughness, rooting depth, Vcmax, FPC, albedo, representative individuals).
4. **Conserve by construction, prefer partitions over residuals — with one documented exception.** Use softmax fraction-allocation of conserved inputs (NPP→pools) and flux-then-integrate (MC-LSTM style) for storage states and the tree population. Avoid privileged residual variables *where you have the freedom to*. **Exception (energy layer E):** LE is fixed by water availability (not free to choose), so H necessarily closes the energy balance as the residual — this is deliberate and must be validated hardest (PLUMBER2: H is the worst-modeled flux). Do not simultaneously claim a softmax LE/H/G partition. Soft penalties only for what can't be hard-wired.
5. **Only close a budget you can account for — with ALL its fluxes.** Water and carbon close because the targets are a self-consistent model — enforce them hard, **but fire is ON (GlobFIRM), so the carbon budget must include `firec` and establishment `flux_estabc`**: ecosystem `ΔC = NPP − Rh − firec + flux_estabc`, atmosphere `NBP_atm = Rh + firec − NPP − flux_estabc`. A fire-free `NEE = Rh − NPP` will not close and will leak carbon. The **energy** budget is *asserted* by layer E — close it only with variables you actually have, validate against flux towers, and do not force a false budget (the documented MC-LSTM failure mode).
6. **Train offline per-component, then online/coupled.** Offline skill does **not** guarantee coupled stability and can anti-correlate with it. Always finish with multi-year coupled rollouts (curriculum short→long, noise injection, bounded outputs) and re-anchoring to full LPJmL-FIT. (`DEVELOPMENT_PLAN.md` §4.)
7. **Evaluate the slow part distributionally, never per-tree.** Metric panel: KS/Wasserstein/CRPS + energy score **and variogram score** (for correlation) + PCD + detection AUC + physical/allometric checks. (`DEVELOPMENT_PLAN.md` §5.)
8. **Reproducibility is mandatory.** Pinned dependencies (`environment.yml`), fixed random seeds everywhere, everything config-driven (no hard-coded paths/magic numbers in code — use `config/`), and log the exact LPJmL-FIT commit + config + input files used for every dataset.
9. **Maintain `MEMORY.md` and `JOURNAL.md`** continuously (see §5). Another agent must be able to take over from them.
10. **Stop at every checkpoint** (`DEVELOPMENT_PLAN.md` §6) and report before spending the next phase's compute.

---

## 4. Getting LPJmL-FIT to build and run (Phase 1 prerequisite)

You will **re-run LPJmL-FIT yourself** to generate training data. The model already integrates daily; enabling daily output is a **config change, not a code change**.

### 4.1 Build (PIK, Intel MPI)
- The repo uses `Makefile.hpc2024` (Intel `mpiicx`, netcdf, udunits, json-c; MPI enabled). Configure via `./configure.sh` (selects the PIK include file) then `make`. `LPJROOT` in `Makefile.inc` currently points at `/home/billing/LPJmLFit_global_final` — set it to this repo's path (see `config/paths.yaml`).
- Load the same modules the interactive `module list` in the job files expects (intel/impi, netcdf-c, udunits, json-c). Put the exact module lines in `config/hpc_slurm.yaml` once confirmed.
- Verify the binary: `bin/lpjml -h` and a `-DSINGLESITE` dry run.

### 4.2 Resolve input data paths (the main external dependency — do this early)
- `input_GSWP3-W5E5.js` references climate `.clm`, soil, and CO₂ files that are **not in this repo**. The paths are **absolute and heterogeneous** — the climate is under `/p/projects/lpjml/input/historical/ISIMIP3av2/obsclim/GSWP3-W5E5/{tas,pr,rsds,lwnet,huss,sfcwind}_*_1901-2019.clm`, while other inputs use different roots (`/p/projects/landuse/...`, relative `input_VERSION2/...`, `CRUDATA_...`). There is **no single `lpjml_input_root`** substitution — open `input_GSWP3-W5E5.js`, list every file it actually reads, and record each resolved path in `config/paths.yaml`. The files this FIT config genuinely needs are ~7: **tas, pr, rsds, lwnet, huss, soil, CO₂** (plus `sfcwind` which is read but unused by the physics; the many land-use/N/SPITFIRE inputs are irrelevant here). Without these, no run is possible — surface it immediately if they can't be found.
- **For the energy layer E you must additionally source surface pressure `ps`** (GSWP3-W5E5 provides it) — it is not in the current input config. Wind (`sfcwind`) is already present.
- Confirm the `.clm` are **daily** and the `lwnet` sign convention (SOURCE_FINDINGS open items).

### 4.3 Run modes (from the repo's SLURM files)
- **Prototype (single location, large stochastic ensemble):** the goal is ~50,000 stochastic realizations of the within-cell trait/size distribution at one location (the prior planning phase described this as 10,000 replicate cells × 5 patches × 10 yr, 2001–2010, post spin-up). **The current repo config does not produce that as-is:** `lpjmlfit.js` has `npatch:25` and `-DSINGLESITE` selects a *single* cell (`startgrid:28008`, Hainich ≈51.1 N/10.4 E — note this differs from the "50.2 N/10.7 E" in the prior notes). A `-DSINGLESITE` run gives 25 patches/yr for one cell, **not** 50,000 realizations. **Before generating data, reconcile the mechanism (DESIGN task):** either reproduce the replicate-cell approach (an N-replicate grid of identical climate/soil → multi-cell MPI, *not* `-DSINGLESITE`) or raise `npatch` and add years/seeds on one site; then make patch-count / cell-count / coordinate agree across the docs, `config/paths.yaml`, and `lpjmlfit.js`, and confirm the target coordinate. The single-site command is `mpirun bin/lpjml -DSPINUP -DSINGLESITE lpjmlfit.js` then `-DTRANSIENT -DSINGLESITE`. **Start by resolving this, then generate.**
- **Multi-cell:** full MPI (`--ntasks` as in `slurm_lpjmlfit.jcf`, `--qos=short`, `--exclusive`). Only after the prototype pipeline works.
- **Enable daily output** by editing the `"output"` array in `lpjmlfit.js` per `SOURCE_FINDINGS.md` Q1c (add `"timestep":"daily"` + per-day units for `transp, evap, interc, runoff, perc, swc, soiltemp, swe, gpp, npp, rh`). Keep the `ind` tree table **annual**. Never edit the source to get daily output — it isn't necessary.
- Use `config/hpc_slurm.yaml` for all SLURM settings; **do not probe the cluster interactively** for partition/walltime.

### 4.4 Sampling design (decisive)
Generate data along **realistic climate trajectories**, **not factorial** perturbations — factorial training fails for path-dependent vegetation (Natel et al. 2025; `RESEARCH_SURVEY.md` A.1). Baseline forcing is GSWP3-W5E5 obsclim historical (1901–2019). For the OOD/warming test, source a **separate, realistic future/counterfactual trajectory** (e.g. an ISIMIP3b GCM-based scenario) and record it in `config/paths.yaml:ood_forcing` — **do not** fabricate a synthetic warming delta (that is the forbidden factorial perturbation). If no future forcing is available, state that the OOD test is limited to within-historical variability. Stratify multi-cell sampling by biome; hold out cells **and** scenarios/time-periods.

---

## 5. MEMORY.md and JOURNAL.md (handoff discipline)

- **`MEMORY.md`** — the durable handoff file. Keep it current: verified facts, frozen decisions, resolved config values (paths, modules, input-data root), open questions, per-phase status, and known limitations. Pre-seeded for you; update it as facts are established. Another agent should be able to resume from it alone.
- **`JOURNAL.md`** — append-only running log: what you did, commands run, results, checkpoint outcomes, dead ends. Timestamp entries. This is your narrative audit trail.

Update both at least at every checkpoint and whenever a fact or decision changes.

---

## 6. Phased plan & checkpoints (follow `DEVELOPMENT_PLAN.md` §6)

0. **DESIGN** — investigate, freeze schemas, write `DESIGN.md`. Gate: DESIGN reviewed.
1. **Data generation** — build + daily-output prototype run (+ small multi-cell). Gate: raw water/carbon budgets close.
2. **Slow emulator (offline, prototype cell)** — DRF + count baseline → metric panel; escalate only if needed. Gate: distributional panel passes; allocation conserves.
3. **Hybrid integration (F1) + interface** — drive kept core with emulated structure/representative individuals. Gate: coupled hybrid reproduces LPJmL trajectories; budgets close.
4. **Energy-balance closure (E)** — surface energy balance + skin temp + diurnal downscaling; validate vs FLUXNET. Gate: energy closes; LE/H/T_skin plausible.
5. **Multi-cell generalization** — biome-stratified; held-out cells+scenarios. Gate: generalization metrics pass.
6. **Online stability + OOD** — (optional differentiable core F2) rollout training/validation; multi-year free runs; warming OOD. Gate: stable + plausible OOD.
7. **(Optional) fast-core emulation + ESM packaging** — only if profiling justifies / F2 exists.

**Do not skip the checkpoints.** Each is a stop-and-report.

---

## 7. First actions (concrete)

1. Read the four docs in §1 and the `config/` files.
2. Set up the Python env from `config/environment.yml`; verify GPU is visible on a GPU node.
3. Verify the LPJmL-FIT build (§4.1) and **locate the input datasets** (§4.2) — surface blockers immediately.
4. Re-verify the two load-bearing source findings yourself (§2) and reproduce the daily-output config on a **tiny** single-site run.
5. Write `DESIGN.md` (§2); freeze the state vector, interface contract, and data schema.
6. Update `MEMORY.md` + `JOURNAL.md`; then stop at the DESIGN checkpoint and report.

---

## 8. Limitations to keep visible (state them in every report)

- LPJmL-FIT is **daily**; sub-daily fluxes come only from physically-based diurnal downscaling — a truly sub-daily component would need a different training model.
- The **energy balance is new physics with no in-model ground truth**; validate it out-of-model (FLUXNET/PLUMBER2). Its accuracy is bounded by that external data.
- LPJmL's ET is water-limited equilibrium evaporation, not energy-balance-derived; the LE = λ·ET bridge is pragmatic and must be validated (with a demand-limited cap).
- The target is a **distribution** (RNG-driven patch ensemble), not a single realization — evaluate distributionally.
- Pure-ML components **do not extrapolate** beyond the training envelope; OOD robustness relies on the physical core, conservation-by-construction, and climate-invariant input features.
- **Constant CO₂.** LPJmL-FIT runs `with_nitrogen="no"`, so CO₂ fertilization is unbounded and future CO₂ is held constant. Train/apply at constant CO₂; **OOD test = warming/precip at constant CO₂, not rising CO₂**; the emulator must not be used for CO₂-fertilization projections. (Bonus: this makes SpeedyWeather's lack of a carbon cycle a non-issue — carry NEE as a diagnostic.)
- **Evaluate dynamics, not just yearly values** — use the LPJ_resilience battery (autocorrelation-vs-climate, recovery rate, shuffle test); the coupled carbon+population system is stiff and an autoregressive emulator can oscillate/drift or fake its memory. See `ECOSYSTEM_AND_COUPLING.md` §6 and `DEVELOPMENT_PLAN.md` §5.
- The ESM interface needs **wind and surface pressure**, which LPJmL-FIT never used — their handling is new and only exercised in the energy layer.

Work carefully, verify your own claims against the source and the data, and keep the handoff files current. Good luck.
