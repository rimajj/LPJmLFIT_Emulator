# HANDOFF — Next-Session Takeover Prompt

**Read this first, then `MEMORY.md` (durable facts) and the tail of `JOURNAL.md` (narrative).**
You are continuing an in-progress build of an ESM-ready LPJmL-FIT hybrid land component:
**S** = slow ML trait/size *distribution* emulator (annual), **F** = fast physical daily biophysical
core, **E** = new surface-energy-balance + skin-temperature closure. Water & carbon conserved by
construction; energy closed in E. Frozen design in `DESIGN.md`; phased plan in `DEVELOPMENT_PLAN.md` §6.

Repo: `/p/projects/open/Jamir/esm_land_emulator` → remote `git@github-esm:rimajj/LPJmLFIT_Emulator.git`
(SSH alias `github-esm`, deploy key `~/.ssh/esm_land_emulator_deploy`; **push works with NO manual auth**).
**Workflow = MAIN-ONLY** (ADR 0013): commit + push straight to `main`; CI on push is a smoke alarm
(fix-forward), run the CI-equivalent checks locally first. `gh` authenticated. `git log --oneline -6`
for HEAD.

## Progress so far
- **Phase 0 DESIGN** — COMPLETE, frozen (`DESIGN.md`; ADRs 0001–0015).
- **Phase 1** — COMPLETE: carbon closure PASSED, water closure PASSED, and the **full-global daily F/E
  dataset generated** (all 67,420 cells × 2000–2019, **186 GB** on `/p/tmp/jamirp/esm_land_daily/daily_2000_2019_global_c0_67419_seed1/output`).
- **Phase 2** — slow-emulator GATE MET at the baseline tier (in-distribution median KS 0.023; warm+dry
  OOD is the documented equilibrium-ML limit the hybrid targets). `scripts/train_slow_emulator.py`.
- **Phase 3 (session 4) — DIFFERENTIABLE FAST CORE `F_diff` spike: DONE + MERGED to `main`**
  (squash `8dcf55b`, was PR #14; CI green on all required checks; docs deployed).
- **Phase 3 (session 5) — `F_diff` ↔ C-BINARY QUANTITATIVE VALIDATION on the prototype cell: DONE**
  (scale-up step 1). PET/radiation path validated tight (r 0.999, ratio 1.05); GPP/transp seasonal
  dynamics captured, level offsets = the documented multi-PFT/soil scale-up gaps. Committed C-binary
  gate + 2010 ReferenceTests baselines replace the self-referential pin. Suite 25,768 pass / 0 fail.
  **See `docs/phase3_fdiff_cbinary_validation.md`.**

---

## ⭐ WHAT LANDED IN SESSION 5b (on `main`) — MULTI-LAYER SOIL (scale-up step 2)

Replaced `F_diff`'s single soil bucket with a **differentiable 23-layer soil column** (`FDiff.SoilColumn`,
`FDiffStateML`, `daily_step_ml`/`rollout_daily_ml`, `hainich_soilcolumn`): fill-to-field-capacity
infiltration cascade, Jackson-1996 β root distribution (D95≈115 cm → ~93 % roots in top 1 m), per-layer
root-weighted transpiration withdrawal, top-300 mm quadratic soil evaporation. Per-layer capacities from
the C run's own `whc_nat` output (no pedotransfer port); dependency-free; water closes ~1e-12.
- **Result (Hainich, FAPAR-driven):** GPP daily correlation **0.76 → 0.93**, transpiration **0.91 → 0.96**,
  root-zone water now representable (r 0.87) — at **essentially unchanged LEVELS** (GPP 0.61, transp 1.45).
- **DECISIVE FINDING:** the transp/GPP **level** gaps are **demand-side / single-representative-individual,
  NOT soil-supply** — with realistic per-layer drying the root zone tracks the C yet transp stays ~45 %
  high & demand-limited. → the next step is now unambiguously **multi-PFT / representative-individual**.
- **AD:** ForwardDiff differentiates the layered rollout (matches FD). Enzyme-reverse through the layered
  Vector-mutation is a follow-up (single-bucket already proves Enzyme-reverse through the physics).
- Gate `test/testitems/multilayer_soil_tests.jl` + committed `references/hainich_{soilcolumn,ml_baseline_2010}.txt`.
  Report `docs/phase3_fdiff_cbinary_validation.md` §8. Full suite **25,788 pass / 0 fail**; Runic-clean.

---

## WHAT LANDED IN SESSION 5 (on `main`)

**Quantitative "same physics" validation of `F_diff` against the LPJmL-FIT C binary on the Hainich
prototype cell** — the handoff's Priority-1 item 1. `F_diff` driven by the cell's REAL daily `.clm`
forcing + the C binary's ACTUAL daily FAPAR (kernel isolation), compared to LPJmL-FIT's own daily
GPP/transp/PET.
- **⚠️ LOAD-BEARING CORRECTION:** the prototype cell in the **global orderA grid** (all data) is
  **`42490`** (lat 51.25/lon 10.25 = Hainich beech), **NOT `28008`** (= Sonoran desert in that grid;
  28008 is Hainich only in the repo `-DSINGLESITE` grid). Corrected in MEMORY/DESIGN/paths.yaml.
- **Results:** PET ratio 1.05 / r 0.999 (radiation path VALIDATED); GPP annual r 0.96 (within-year GS
  daily r 0.96) but level −42%; transp r 0.91–0.97 but level +40–47%. Level offsets = multi-PFT/
  representative-individual + 23-layer-soil scale-up gaps (kernel constants byte-identical ⇒ not bugs).
- **New code:** `scripts/run_fdiff_validation_cell.sh` (single-cell re-run adding daily FAPAR + NV_LAI;
  9 s), `scripts/extract_fdiff_validation_inputs.py` (`.clm` YEARCELL reader validated vs `d_prec`;
  petpar2 daylength; C-target extraction), `scripts/validate_fdiff_vs_cbinary.jl` (multi-year driver).
- **`F_diff` additions (AD-safe, regression baseline EXACT):** `Structure.alphaa`, `PhotoParams` SLA-
  Vcmax cap (`issla`), external-FAPAR drive (`daily_step`/`rollout`/new `rollout_daily` take per-day
  `fapar`), `tebs_params()`/`tebs_structure()`. λ-Newton iterate now `clamp`ed to [0.02,0.85] (fixes a
  real deep-winter NaN; `smooth_clamp` rejected — overflows the AD dual). The clamp is conditional →
  **Enzyme reverse now uses `set_runtime_activity`** (still exact vs FD; ForwardDiff unaffected).
- **Gate:** `test/testitems/cbinary_validation_tests.jl` + committed `hainich_{forcing,cbinary_targets,
  fdiff_baseline}_2010.*`. Full suite 25,768 pass / 0 fail; Runic-clean; JET/Aqua green.

---

## WHAT LANDED IN SESSION 4 (on `main`)

**Owner decision (ADR 0014): F is differentiable FROM THE START (`F_diff`)** — supersedes the old
F1-now/F2-at-Phase-6 split. The compiled LPJmL-FIT C binary is retained **only** as the
numerical-regression oracle + data generator, NOT the coupling path. S stays non-differentiable
(DRF/copula), out of the gradient loop. (Session 4 used a **branch + PR as a one-off** for the review
surface; **we are back to main-only** now.)

**Feasibility PROVEN on one cell — the gate is met:** Enzyme reverse-mode **and** ForwardDiff match
FiniteDifferences to **~1e-11** for `d(annual NPP)/dx` (x ∈ CO₂, emax, α_c3, initial soil water)
through the full 365-day daily rollout incl. the λ (ci:ca) Newton solve and the autoregressive
soil-water coupling; no NaN/Inf. Water closes ~1e-12 mm/day by construction.

New code on `main` (**runtime is dependency-free**; AD lives in `test/Project.toml`):
- `src/allometry.jl` — shared pure differentiable diagnostics (pipe-model height, **Jucker 2022**
  crown/stem — NOT Reinicke; LAI, Beer–Lambert FPC).
- `src/fdiff_smoothops.jl` — C∞ surrogates with tested `log(2)/β` deviation bounds.
- `src/fdiff.jl` (`FDiff` submodule) — C3/C4 Haxeltine & Prentice photosynthesis, λ supply/demand
  solve (fixed-graph damped Newton), Priestley–Taylor PET/ET, soil-water bucket + snow, Lloyd–Taylor
  respiration; pure `FDiff.daily_step` + `FDiff.rollout`. LPJmL-FIT C-source constants.
- Gates: `test/testitems/{allometry,smoothops,fdiff_physics,gradient_correctness,numerical_regression}_tests.jl`
  (+ baseline `test/testitems/references/fdiff_annual_totals.txt`). **Full suite 25,756 pass / 0 fail.**
- ADR **0014** (differentiable-fast-core-first) + **0015** (reuse map + citations); report
  `docs/phase3_fdiff_spike.md`; DEVELOPMENT_PLAN §2.3/§6 updated; CITATION.cff references.

---

## ▶️ PRIORITY 1 (live) — SCALE `F_diff` toward the coupled hybrid (`docs/phase3_fdiff_spike.md` §7)

The one-cell spike proved the AD toolchain is NOT the blocker; **session 5 quantitatively validated
`F_diff` against the C binary** (PET tight; GPP/transp dynamics captured, levels offset). The remaining
work is **physics coverage** to close the two MEASURED level gaps, in priority order:
1. ✅ **DONE (session 5) — Quantitative C-binary validation on the prototype cell.** See
   `docs/phase3_fdiff_cbinary_validation.md`; gate `test/testitems/cbinary_validation_tests.jl`.
2. ✅ **DONE (session 5b) — Multi-layer soil water (water-only v1).** 23-layer differentiable column
   (`daily_step_ml`); improved GPP/transp DYNAMICS (corr 0.76→0.93 / 0.91→0.96); root-zone water
   representable. See `docs/phase3_fdiff_cbinary_validation.md` §8; gate `multilayer_soil_tests.jl`.
   **It proved the transp/GPP LEVEL gaps are demand-side, not soil-supply** → do #3 next.
   v2 soil items (deferred): free-water percolation timescale + surface/infil-excess runoff split, the
   **23-layer enthalpy soil-thermal + permafrost** (REDO from C or reuse Terrarium.jl — ADR 0006),
   Enzyme-reverse through the layered Vector-mutation.
3. **★ NEXT — Multi-PFT + representative-individual set** (C3/C4, angio/gymno) driven by S. This is now
   the localized cause of BOTH level gaps (GPP −42%, transp +45%): one well-watered representative tree
   transpires at full atmospheric demand and concentrates all light through the SLA-Vcmax cap.
   Approach: split the canopy into PFT×size classes from the `ind` CSV (leaf/sapwood C, crown, nind,
   height per class — reconstruction recipe in the session-5 investigation), distribute light per class,
   run per-individual photosynthesis (SLA cap + co-limitation act per individual) + per-individual water
   stress, aggregate to per-m². Validate GPP/transp LEVEL recovery with the existing FAPAR/forcing
   harness (may need per-PFT FAPAR from a re-run, or a Beer–Lambert layered light split).
4. **Coupled conductance↔carbon consistency** (the measured water-use-efficiency inconsistency: high
   transp + low GPP) and **dynamic phenology-folded structure** (so full-year GPP no longer needs the
   FAPAR crutch / growing-season restriction).
5. **Full `petpar` radiation/daylength** (smoothed polar-day/night `acos` branches) — the spike (and the
   validation) supplies daylength as forcing; reproduced exactly from `petpar2.c` in the extractor.
6. **`SharedState` adapter** so `FDiff` sits behind `AbstractFastCore.step!` (currently throws) → then
   **S↔F coupling** (flux-then-integrate `bm_inc`) on the prototype, and **gradient-based online
   rollout training** (finish NeuralCrop's TBPTT scaffold; add Lux NN λ/Vcmax hooks).
7. **λ-solve at scale:** swap the fixed-graph Newton for `SteadyStateAdjoint`/`ImplicitDifferentiation`
   if memory/perf needs it (the hybrid repo notes the adjoint's memory blow-up on large grids). NB: the
   Newton iterate is now `clamp`ed to the physical bracket (robustness); Enzyme reverse uses
   `set_runtime_activity` because of that conditional.

**Keep the runtime dependency-free** where possible; Aqua checks stale deps. Add Lux/KernelAbstractions/
SciMLSensitivity/OrdinaryDiffEq only WHEN the feature that uses them lands.

---

## KEY VERIFIED FACTS (session 4 — reuse freely)
- **GitHub HTTPS is BLOCKED on the login node; SSH works.** Clone public repos via `git@github.com:…`.
  The 3 reference repos are at **`/p/tmp/jamirp/esm_reference_repos`** (LPJmL-hybrid-photosynthesis,
  NeuralCrop.jl, Terrarium.jl). Julia pkg servers are reachable.
- **AD stack:** `Enzyme` (0.13), `ForwardDiff` (1), `FiniteDifferences` (0.12) in `test/Project.toml`
  and warmed in `~/.julia`. `ForwardDiff.Dual <: Real` but **NOT `<: AbstractFloat`** → parameterize
  AD-path structs `{T<:Real}`. Mixed-type AD needs a promoted working-type + `convert`-coerced state.
  `@kwdef` with parametric-`{T}` defaults makes the zero-arg constructor throw (JET catches it) →
  use explicit constructors (see `FDiff.FDiffParams`, `state.jl`).
- **Reference specifics:** hybrid-photosynthesis differentiates λ via `SteadyStateAdjoint`+`EnzymeVJP`
  (implicit; never through bisection). NeuralCrop uses Zygote + **detaches physics** (`Zygote.ignore`)
  and its **training driver is a broken scaffold** (inconsistent signatures / undefined `ps_frozen`,
  `dailyWeather`) — physics kernels port, the training loop must be finished. Hybrid repo ships a
  **272.15-vs-273.15 K bug** (use 273.15). Two Priestley–Taylor coeffs: **1.32** soil/PET, **1.391**
  transpirative demand. FIT allometry = pipe-model height + Jucker 2022 (reinickerp unused).

## Environment facts (verified this project)
- **Julia 1.10.0:** `/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia`;
  `JULIA_DEPOT_PATH=$HOME/.julia julia --project=. -e 'import Pkg; Pkg.test()'` → 25,756 pass / 0 fail.
  Runic (format gate): `pip`-free — `Pkg.add(name="Runic",version="1")` in a temp env, `Runic.main(["--check", files])`.
  Docs build locally: `DOCS_LINKCHECK=false julia --project=docs docs/make.jl` (linkcheck guarded so
  it can be skipped on the HPC's restricted egress; CI leaves it on).
- **LPJmL-FIT:** `/home/jamirp/lpjml56fit` (v5.6.004, binary built). Modules (this binary): `module
  purge` then `intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 openssl/3.6.0 netcdf-c curl/8.4.0
  expat/2.5.0` (login default's json-c/0.17 → libjson-c.so.5 FAILS; needs .so.4 from 0.13.1).
- **Ground truth:** `/p/projects/waldspektrum/priesner/clustering/global` (67,420 cells; Historical
  obsclim 2000–2019 seed1+seed2; SSP370 2020–2100; `restart_1999.lpj` = spinup end). `config/paths.yaml`.
- **Python (S):** `/home/jamirp/.conda/envs/py311_new` (3.11.9). **`gh`:** `/home/jamirp/tools/gh-cli/gh_2.49.0_linux_amd64/bin/gh` (authenticated).
- **Regrid/CLM tools:** `/p/projects/biodiversity/bloh/git/master_bsq/bin/` (getcellindex/cutclm/regridclm/…).
- **libcurl noise:** `curl_easy_setopt:48` warnings during Julia Pkg ops are a benign login-node quirk; ignore.

## Re-running LPJmL daily (tooling proven, reuse for the C-binary validation)
`scripts/run_daily_subset.sh` (params `STARTGRID ENDGRID FIRSTYEAR LASTYEAR NTASKS TIME EXCLUSIVE
RUNTAG SUBMIT RANDOM_SEED`) generates the config from the EXACT production sections, runs a `lpjcheck`
pre-flight, and submits. Verify closure with (dask-lazy) `scripts/water_closure_check.py <run_dir>`.
**Never run on the login node.** Restart a contiguous cell subset via integer 0-based `startgrid`/
`endgrid`; daily output = `"timestep":"daily"` inside each output entry's `"file"` object; water
balance enforced ANNUALLY by `-DSAFE` `check_fluxes.c` (≤1.5 mm/yr, aborts otherwise). `swc` is
FRACTIONAL saturation (no `wsats` output → absolute mm needs wsats). See `docs/phase1_p3b_water_closure.md`.

## Housekeeping
- **Dependabot:** `.github/dependabot.yml` tamed (monthly + grouped); open PRs = 0.
- **Signing:** commits are `G`-signed locally but show "Unverified" on GitHub (cosmetic; repo going
  public later — declined). Do not chase.

## Commit history on `main` (recent)
`8dcf55b` feat(fdiff) F_diff spike (#14 squash) · `bcb3ecb` feat(phase2) gate met · `0324cc1`
feat(phase2) driver · `da12c88` feat(phase1) global daily dataset · `b3924c9` feat(phase1) water
closure · `5bc93ef` docs(ADR 0013 main-only).
