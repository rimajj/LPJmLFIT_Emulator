# MEMORY.md — durable state for the LPJmL-FIT hybrid land-component emulator

> **Current durable state only.** Verified facts, frozen-decision index, phase status, open TODOs.
> Environment/runbook facts live in `CLAUDE.md`; session narrative in `JOURNAL.md`; the story of any
> single change in `CHANGELOG.md`. Reshaped from a 127 KB session-log on 2026-07-22 (consolidation P0);
> the pre-consolidation copy is `docs/archive/MEMORY_2026-07-22_pre-consolidation.md` (and in git).
> Cap: ≤ 400 lines / ≤ 15k tokens — keep it that way; new narrative goes to JOURNAL, not here.
>
> Tags: **[VERIFIED]** confirmed against source/data · **[DECISION]** frozen unless reopened via ADR ·
> **[TODO]** must be resolved · **[ASSUMPTION]** believed, not confirmed.

---

## 1. What this is

Hybrid ESM-ready land component from **LPJmL-FIT** (LPJmL 5.6.004 + FIT; carbon-only, `individual=true`,
`with_nitrogen="no"`). Three components:

- **S** — slow ML emulator of the per-cell **trait/size distribution** + count N (annual). *The novelty.*
- **F / F_diff** — the fast, differentiable, conserving daily biophysical core kept from LPJmL-FIT
  (photosynthesis, water, soil thermal), reimplemented AD-friendly.
- **E** — surface-energy-balance + skin-temperature closure the ESM needs and LPJmL-FIT lacks.

Goal: run **offline** emulating LPJmL-FIT faithfully **and** run **online** coupled to SpeedyWeather.
Orders + reasoning: `STEERING_PROMPT.md`, `PROJECT_REVIEW_2026-07-22.md`. Runbook: `CLAUDE.md`.

---

## 2. Phase status (as of 2026-07-22, ~90 commits, main-only)

| Phase | State | Evidence / gate |
|---|---|---|
| **0 DESIGN** | ✅ done | schemas + interface contract frozen (`DESIGN.md`); both load-bearing findings re-verified |
| **1 Carbon+water closure** | ✅ PASSED | carbon flux identity 7.3e-5 PgC/yr, 0.6% cumulative drift; water proven by `-DSAFE` per-cell abort over all 67,420 cells × 20 yr (global cumulative \|Σprec−Σ(ET+runoff)\|/Σprec median 0.87%); 186 GB daily dataset generated |
| **2 S offline** | ✅ baseline gate met | `DirectEmulator` (LightGBM+copula), 6000 biome-stratified cells. In-distribution KS **0.023** vs **0.0049** floor; **warm+dry OOD KS ~32× floor** — the documented equilibrium-ML failure the hybrid exists to fix (not an S-escalation trigger, ADR 0005) |
| **3 F_diff** | ✅ scale-up steps 1–11 done; C-validated **Hainich only** | multi-layer soil, multi-PFT canopy, prognostic structure, self-computed calibrated NPP, NN λ/Vcmax hooks (Enzyme/Zygote gradients verified), grass faithful to ±10–15%, `sapwood_bg` pool added. Decadal (2009–2019) mean GPP ratio 1.066, interannual r=0.86, no drift |
| **4 E energy** | ✅ landed, self-contained (ADR 0017) | `SEBEnergyClosure` closes `Rn=LE+H+G` to **1.4e-14 W/m²**; H the residual; Monin–Obukhov g_a stability correction ON by default; coupled Hainich decade emergently reproduces the **2018 drought** (summer Bowen 0.89 vs ~0.2) |
| **5 Multi-cell** | 🟡 started | coupled run across 5 biomes closes energy ≤3e-14 W/m² with climate-correct partitioning; **not yet** the 6000-cell held-out evaluation or resilience battery |
| **6 Online / SpeedyWeather** | ⬜ not started | |
| **7 ESM packaging** | ⬜ not started | |

**The whole remaining project (not done):** S is **not in the coupled loop** (`components/slow.jl` `step!`
still throws; `run.jl` grows structure from F itself); E **not validated against FLUXNET/PLUMBER2**;
nothing runs multi-cell held-out; nothing runs online with SpeedyWeather; wind/psurf forcing not sourced.
Everything C-validated is **Hainich (DE-Hai) only** — single-cell is scaffolding, not evidence.

---

## 3. Verified facts — the load-bearing, durable ones

### Model / data structure
- [VERIFIED] Integration is **daily**; no sub-daily physics except the soil-heat numerical substep. Daily
  output is a **runtime config flag** (`"timestep":"daily"`), never a recompile.
- [VERIFIED] LPJmL-FIT has **no surface energy balance**: ET = Priestley–Taylor equilibrium/demand–supply;
  soil temp uses **air temp** as the top Dirichlet BC; no H, G-as-flux, T_skin, or Rn closure. All of that
  is component E (new physics), validated **out-of-model** (FLUXNET/PLUMBER2 — still to source).
- [VERIFIED] Forcing consumed: tas, precip, swdown, **net** longwave (`lwnet`, downward-positive), `huss`
  (→VPD, hard dependency), CO₂. **Wind is read but unused**; **surface pressure is hard-coded** `p=1e5` in
  `photosynthesis.c`. E needs **wind + psurf** as genuinely new inputs.
- [VERIFIED] **Fire is ON (GlobFIRM)** ⇒ carbon closes only with fire + establishment:
  `ΔC = NPP − Rh − firec + flux_estabc`; `NBP_atm = Rh + firec − NPP − flux_estabc`. A fire-free
  `NEE = Rh − NPP` will NOT close. Mortality drivers: water stress, temp stress, growth efficiency, age.
- [VERIFIED] **Constant-CO₂ regime** (`with_nitrogen="no"` ⇒ unbounded CO₂ fertilization ⇒ future CO₂ held
  constant). OOD test = **warming/precip at constant CO₂**, not rising CO₂. NEE is diagnostic-only, so
  SpeedyWeather's missing carbon cycle is a non-issue. **Not** valid for CO₂-fertilization projections.
- [VERIFIED] Allometry is **re-derived, not co-predicted**: height = k_latosa·Csap/(Cleaf·SLA·wooddens);
  crownarea (Jucker 2022); LAI = Cleaf·SLA/crownarea; FPC = crownarea·nind·(1−e^(−k·LAI)); AGB = leaf+heart+sap.
- [VERIFIED] **`individual=true` config skips many C paths.** `light()`/`light_grass()` (cover/light
  competition) are **never called** (`annual_natural.c:117` gates on `!individual`); active grass reduction
  is `reduce_grass` (fpc-only, no carbon killed, fires 0/25 at Hainich). Per-PFT `gp_pft`/`gc_pft` are
  diagnostic-only; GPP uses the stand mean `gp_stand`. **Always confirm a C routine actually runs here
  before porting it** (the sessions-16/17/19 waste). Active param file = `par/pft_lpjmlfit.js` (beech =
  ANGIO allometry), **not** `par/pft.js`. `-DPERMUTE` randomizes daily PFT-depletion order ⇒ the C is
  non-deterministic / order-averaged.

### Prototype cell (critical)
- [VERIFIED] **Hainich (DE-Hai) = global orderA grid 0-based index `42490`** (lat 51.25/lon 10.25; 98% beech,
  PFT type 3). **Index `28008` in the global grid is Sonoran desert** — it is Hainich only in the repo
  `-DSINGLESITE` grid. Single-cell daily re-run: `STARTGRID=ENDGRID=42490`. Byte-verified against grid.nc.

### F_diff (fast core) — what's validated vs the C oracle (Hainich)
- [VERIFIED] Gradient gate: Enzyme reverse **and** ForwardDiff match FiniteDifferences to ~1e-11 for
  d(annual NPP)/dx through the full 365-day rollout incl. the λ ci:ca Newton solve; water closes ~1e-12.
- [VERIFIED] Level gaps closed step-by-step to the C binary: multi-individual canopy closed the GPP level
  (annual ratio → ~1.06); coupled conductance↔carbon closed transpiration (→~1.02); self-computed NPP
  calibrated via two faithful `npp_tree.c` fixes (growth-resp floor `βgrowth=50`; phen-gated fine-root
  maintenance) → annual NPP +663 (C 507 in-model; CUE 0.512, C ~0.46). Residual ~+7–17% is an inherited
  GPP-phenology **level** offset, not a respiration bug; daily correlations r ≈ 0.98–0.998.
- [VERIFIED] NN-hook training (Vcmax `:vm` + λ) via the extension: Zygote (single-rep) and **Enzyme reverse
  (canopy/cell/multi-year)** gradients match FiniteDifferences (max rel err 1e-8…1e-10); recovery losses
  >96–99%. Cell GPP annual ratio 1.093 → 1.010 with `:vm,:λ`. The single-representative Vcmax lever only
  partially closes the level and degrades daily shape — the residual is **light/structure-limited**.
- [VERIFIED] Prognostic canopy: pipe-model invariant to 3e-16 over 272 trees; carbon conservation exact;
  multi-year rollout tracks C tree height (9.34 m yr-1 vs C 9.344) with no blow-up.
- [VERIFIED] **Grass thread CLOSED as faithful** (§20→§26.2 in the archive): the apparent ~2–3× grass-NPP
  overshoot was a **reference-basis artifact** — against the C's own newly-built daily grass GPP/NPP,
  aggregate ΣF/ΣC=0.95, mean per-year 0.98, CUE 0.55–0.60 matches. The fix that mattered was per-PFT grass
  **phenology** (grass was getting beech GSI), plus a photosynthesis **demand-gate** + grass
  **establishment**; these are the coupled-rollout **default** now (tree-only paths byte-identical). One
  residual remains — see §5 water-supply.

### E (energy) — Hainich + 5-biome, no observational validation yet
- [VERIFIED] Closure to machine precision (13,824 cases; ForwardDiff-vs-FD; Float32); demo daily 1.4e-14,
  biome ≤3e-14 W/m²; Monin–Obukhov aerodynamic identity ~3e-11. Emergent climate-correct Bowen ordering
  (tropical LE-dominated ~0.10; semi-arid/mediterranean H-dominated; boreal low-flux; 2018 drought 0.89).
- [ASSUMPTION] LE/H/T_skin are physically plausible but **invented quantities validated only out-of-model**;
  the FLUXNET/PLUMBER2 validation (P2) has **not** happened. `g_a` had been neutral-only until the stability
  correction landed.

### S (slow) — offline only
- [VERIFIED] Sibling offline S emulator at `/p/projects/open/Jamir/emulator`. Published noise floor
  {Height 0.020, agb 0.113, npp 0.062, LAI 0.025} — ~11% cell-mean agb noise floor is the yardstick.
  PFT types 0–6 = trees, 7–9 = grass. S is **not differentiable** and stays out of the gradient loop (ADR 0014).

---

## 4. Frozen decisions — index to the ADRs (`docs/decisions/`)

ADRs are immutable once accepted; supersede, don't edit. Full index: `docs/decisions/README.md`.

| ADR | Decision | Status |
|---|---|---|
| 0001 | Phased hybrid (emulate S, keep F, add E) | accepted |
| 0002 | Emulate the **distribution** + count N, never per-tree | accepted |
| 0003 | **Flux-then-integrate** carbon conservation (fire + establishment in the budget) | accepted |
| 0004 | Constant-CO₂ regime | accepted |
| 0005 | DRF/copula baseline for S + escalation ladder (no generative escalation triggered) | accepted |
| 0006 | Reuse Terrarium SEB for E | **superseded by 0017** |
| 0007 | Julia-primary stack (Python only for the S prototype) | accepted |
| 0008 | Documentation-only (Documenter.jl) | accepted |
| 0009 | SSH deploy-key auth from HPC | accepted |
| 0010 | S prototype = biome-stratified multi-cell (F/E single-cell) | accepted |
| 0011 | Reuse existing global annual ground truth; daily re-run is the gap | accepted |
| 0012 | Canonicalize component S here; port the sibling once, then abandon | accepted |
| 0013 | **Main-only** workflow (no branches/PRs/branch-protection) | accepted |
| 0014 | **F_diff differentiable from the start**; C binary = oracle + data generator only | accepted |
| 0015 | Reuse map for F_diff (TAKE/REDO/SKIP + citations) | accepted |
| 0016 | Learned closures in F_diff: NN λ/Vcmax hooks, TBPTT training, shipped as an extension | accepted |
| 0017 | Component E **self-contained** (reimplement SEB physics; no Terrarium runtime dep) | accepted |
| 0018 | **Growth-ownership split**: F_diff owns representative-individual carbon growth; S owns the distribution + demography | accepted (agent decision, delegated; reversible by a later ADR) |
| 0019 | **Component S: port inference (not call Python); wrap the machinery (not port DirectEmulator wholesale)** — P1 architecture | accepted |

**Reuse posture (steering reversal):** reuse is now the **default**; reimplementation must be justified in
an ADR. Targets: Terrarium (coupling substrate for P4, SEB cross-check), LPJmL-hybrid-photosynthesis
(differentiable-λ, MIT, done), NeuralCrop (methodology; **CC-BY-NC — code is a blocker**, method-only or
get permission), LPJ_resilience (no license — ask). [TODO] the **EUPL↔AGPL↔MIT licensing read** is still
unresolved and ADR 0017's premise rests on it.

---

## 5. Open TODOs / frontier (priority per `STEERING_PROMPT.md`)

- **[P1 UNBLOCKED] ADR 0018** documents the growth-ownership contract; engineering proceeds on it (the owner's own §4 recommendation), owner holds the formal `accepted` stamp.
- **[TODO] P1 (ACTIVE) — put S in the coupled loop** (the novelty). Design of record + 10-step plan:
  **`docs/p1_s_in_loop_design.md`** (decisions: ADR 0018 split + ADR 0019 port-not-call). Approach:
  `DemographicSlowEmulator` (persistent K cohorts; S owns count N + establishment/mortality + trait spread;
  F owns carbon growth), two tiers (Tier-0 constant models prove wiring + 1e-6 conservation; Tier-1 ports
  ResidualRegressor+copula+NB to pure Julia `src/slow_infer.jl`), opt-in behind `run_coupled_cell(...; slow=)`.
  Conserve at the S↔F handoff to ~1e-6 (litter as the exact growth residual), match the offline-S panel on
  S-owned axes, and **measure the speed-up vs the deterministic-F baseline**. Progress: Step 1 (carbon
  accounting foundation — `vegc_full_ind` + `_turnover_litter` + `fdiff_litter_closure_tests.jl`) done.
- **[TODO] P2 — validate E against observations** (parallel to P1): source FLUXNET/PLUMBER2 DE-Hai + real
  `sfcwind`/`ps`; validate LE/H/T_skin within PLUMBER2 bands; add a `g_a` stability correction (partly
  landed). Real wind needs a **cross-grid remap** (raw GSWP3 `.clm` are a different int16 re-ordered grid —
  raw cell 42490 ≠ Hainich); sublimation λ split pending.
- **[TODO] P3 — multi-cell generalization**: coupled S+F+E on the 6000-cell biome-stratified set; held-out
  **cells and scenarios**; the LPJ_resilience battery (shuffle test + climate-dependent ACF). Error vs the
  seed1-vs-seed2 noise floor. Also: biome-calibrated PFT params + spin-up.
- **[TODO] P4 — online coupling with SpeedyWeather** via Terrarium `Abstract*` processes + the
  `SpeedyWeatherTerrariumExt` interface; rollout curriculum + noise injection; multi-year free run; OOD
  warming at constant CO₂. Contact Terrarium/SpeedyWeather authors.
- **[TODO] P5 — reuse + licensing reconciliation** (new ADR; get the written licensing read).
- **[TODO] P6 — nitrogen limitation** (research track) — **do not start before the owner's "(c)" discussion.**

### Deferred / known issues (fidelity refinements of an already-in-band core — not blockers)
- **[TODO, DEFERRED] Per-PFT competitive grass water-supply** (§26.4): the 2018 grass drought-amplitude
  residual is a genuine water-supply gap — `daily_step_canopy` runs one stand-level FPC-weighted `wscal`
  (tree-dominated, saturates near 1) with no competitive per-layer depletion, vs C's per-PFT `wscal` +
  sequential `aet_cor` cap. **Deferred behind the `FluxHooks` learned lever** because `-DPERMUTE` makes a
  faithful port non-differentiable/non-deterministic and per-PFT `wscal` is half-degenerate
  (`EMAX_ANGIO=EMAX_GRASS=10`, shared `beta_root=0.8`). Design: `docs/water_supply_perpft_design.md`.
- **[TODO] `sapwood_bg` prognostic growth**: the below-ground root-sapwood pool is added but **static-seeded**
  (opt-in, default byte-identical; in-model CUE 0.512→0.497). Finishing it (C_LATERAL pool growth +
  carbon-debt loan in `grow_individual`, the Enzyme SoA thread, flip the seed on + regenerate the CUE ~0.497
  and coupled/decadal baselines) closes only ~40–50% of the 0.51→0.46 CUE gap. Design: `docs/sapwood_bg_design.md`.
- **[TODO] Lift the Enzyme pin / 1.11 canopy guard** when a fixed Enzyme ships (still blocked upstream on
  0.13.187 / Julia 1.11.7; a 0.14 migration is higher-risk).
- **[TODO] Owner actions**: ratify ADR 0018; the licensing read; the "(c)" N-track discussion; close stray
  Dependabot PRs; the `eval`-filename allow decision.

---

## 6. Pointers (don't duplicate here)

- **Environment / build / test / C-binary / CI runbook** → `CLAUDE.md` (+ `config/paths.yaml` for paths,
  `config/hpc_slurm.yaml` for SLURM). Skills in `.claude/skills/` automate the mechanical loops.
- **Source map** (`src/` + `ext/`) → `CLAUDE.md` §7. In brief: `fdiff.jl` = the differentiable daily core
  + canopy rollout + allocation/growth (`grow_individual`, `rollout_canopy_years`; `annual_step!` lives in
  `components/fast.jl`); `conservation.jl` = softmax/flux-then-integrate/budget residuals; `interface.jl` =
  the S↔F↔E I/O contract; `run.jl` = the coupled loop; `components/slow.jl` = S (stub, P1 fills it);
  `components/energy.jl` = `SEBEnergyClosure`; `ext/FDiffTrainingExt.jl` = the NN-hook trainers.
- **Deep dives**: `docs/phase1_p3b_water_closure.md`, `docs/phase2_slow_emulator.md`,
  `docs/phase3_fdiff_cbinary_validation.md`, `docs/sapwood_bg_design.md`, `docs/water_supply_perpft_design.md`.
- **Session narrative** → `JOURNAL.md` (append-only). **Change log** → `CHANGELOG.md` (newest on top).
- **Archived pre-consolidation docs** → `docs/archive/` (also in git history).
