# MEMORY.md — SHARED durable state for the LPJmL-FIT hybrid land-component emulator

> ⚠ **2026-10-10 (ADR 0319): the parallel work lines are RETIRED — one developer, one branch (`main`).** Current
> state + the NEXT handoff live in the root **`STATE.md`**; narrative in the root `JOURNAL.md`. Where the header
> below speaks of lines, per-line files or integrator-only restructuring, read it as history; this file is now
> simply the cross-cutting `[VERIFIED]` fact store, edited by the one developer.

> **Shared, cross-cutting durable state only** (ADR 0029) — the facts and status every work line needs: what
> this is, the `[VERIFIED]` facts, the load-bearing constraints, and the cross-line frontier.
> **Any line may APPEND a cross-cutting `[VERIFIED]` fact here**; *restructuring* this file (the
> `consolidate-memory` reshape) is **integrator-only**, because it is a destructive in-place rewrite that can
> silently auto-merge away another line's edit.
> **Per-line state lives in `lines/<X>/STATE.md`** — see the router below. Environment/runbook facts live in
> `CLAUDE.md` (+ §9 for the parallel-line protocol); per-line narrative in `lines/<X>/JOURNAL.md`; the story
> of one change in a `changelog.d/<X>-*.md` fragment.
> Reshaped 2026-07-22, 2026-07-27, 2026-07-28 (split per-line state out; ADR 0028/0029) and **2026-09-02**
> (folded the superseded speed headline, deduplicated licensing, retired the stale phase/frontier tables,
> added line X). Pre-consolidation copies: `docs/archive/MEMORY_2026-07-{22,27}_pre-consolidation.md`,
> `docs/archive/MEMORY_2026-09-02_pre-consolidation.md` (and in git).
> Cap: ≤ 400 lines / ≤ 15k tokens — keep it that way; narrative goes to a line JOURNAL, not here.
> ⚠ **The 2026-09-02 reshape landed at 539 lines / ≈12.2k tokens — inside the token cap, ~130 lines over the
> line cap.** Everything removable without losing a fact has been removed (prose tightened; the method
> *procedures* now point at `residual-diagnosis` / `plumber2-reference` / `CLAUDE.md` §3 instead of being
> restated). The remaining bulk is ~50 distinct `[VERIFIED]` bullets in §3, so closing the last gap means
> **dropping facts or splitting the file** — a decision for the next integrator, not a wordsmithing pass.
> Token cost is what onboarding actually pays, and that is the cap being met.
>
> Tags: **[VERIFIED]** confirmed against source/data · **[DECISION]** frozen unless reopened via ADR ·
> **[TODO]** must be resolved · **[ASSUMPTION]** believed, not confirmed.

---

## 0. Router — which line am I, and where do I continue?

> ⛳ **THE ORDER OF WORK IS `EXECUTION_PLAN.md` REVISION 2** (owner instruction 2026-10-08; ADR 0096, which
> replaces the 2026-08-07 error-attribution ladder as the order of work — its findings stand, plan §11). The project
> runs **all promising methods in parallel as arms on one yardstick**, with **response-identifying data first**:
> Track D (constant-climate control, extra members, a ~1000-cell panel, a real-pattern climate-contrast ensemble),
> Track Y (one scorer + nulls), Track A (8 annual-demography arms), Track F (3 daily-flux arms), Track C (coupling
> + 300-yr stability gate), Track U (calibration). Arms are dropped only at pre-registered decision points (§8).
> One variable per arm; never a coupled score without the isolated ones beside it. Basis: `docs/review_comparison.md`.
> The plan is **integrator-owned** (a line raises a change as an integration point, it does not edit it).

Work runs as **5 parallel lines**, one long-lived branch + git worktree each (ADR 0028/0029). A session's line
is the branch in the worktree it was launched from; the `SessionStart` hook prints it plus that line's
`## NEXT` action. **Continue from your line's STATE.md, not from this file.**

| Line | Branch · worktree | Scope | State (start here) |
|---|---|---|---|
| **S** | `line/S` · `/p/projects/open/Jamir/wt-S` | Component-S science — the learned demography/traits; rungs 0–2 | [`lines/S/STATE.md`](lines/S/STATE.md) |
| **M** | `line/M` · `/p/projects/open/Jamir/wt-M` | Multi-cell coupled S+F+E; the F core + coupling seam; rungs 3–4 | [`lines/M/STATE.md`](lines/M/STATE.md) |
| **E** | `line/E` · `/p/projects/open/Jamir/wt-E` | Component E vs observations (PLUMBER2/FLUXNET); off the critical path | [`lines/E/STATE.md`](lines/E/STATE.md) |
| **O** | `line/O` · `/p/projects/open/Jamir/wt-O` | Online coupling (Terrarium/SpeedyWeather) + **rung 5, speed** | [`lines/O/STATE.md`](lines/O/STATE.md) |
| **X** | `line/X` · `/p/projects/open/Jamir/wt-X` | **Project direction & exploration** (created 2026-08-19 on owner instruction) — explores and records; **never implements, never writes into another line's state or into this file** | [`lines/X/STATE.md`](lines/X/STATE.md) |

`main` (this directory) is the **integration** worktree: merges, `changelog.d` collation, shared-file
reconciliation, `Project.toml` deps, `EXECUTION_PLAN.md`, and cross-cutting ADRs. Ownership map + the frozen
cross-line contracts: **ADR 0029**. Protocol/mechanics: **`CLAUDE.md` §9** + the `repo-commit` skill.

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

## 2. Where the project stands (2026-09-02)

**Current order of work = `EXECUTION_PLAN.md` revision 2 (2026-10-08, ADR 0096): parallel method arms on one
yardstick, data first.** The ladder's record, as of its last edit (2026-08-12): rung 0 and **rung 1 are CLOSED** (ADR 0174 — the isolated learned demography passes on LEVEL and
**fails on the SIGN of the warming response**), rung 2 is line S's by owner steer, rungs 3–4 line M, rung 5
(speed) line O. The phase numbers P0–P7 used in the older docs come from `DEVELOPMENT_PLAN.md`; where the two
disagree about *priority*, `EXECUTION_PLAN.md` wins.

| Component | State | The evidence that backs it |
|---|---|---|
| **Carbon + water closure** | ✅ passed | carbon flux identity 7.3e-5 PgC/yr, 0.6 % cumulative drift; water proven by `-DSAFE` per-cell abort over all 67 420 cells × 20 yr (global cumulative \|Σprec−Σ(ET+runoff)\|/Σprec median 0.87 %); 186 GB daily dataset generated |
| **S offline** | ✅ global | native-Julia count DRF + recruit copula, K-fold-BY-CELL OOS over 45 009 cells (**superseded population** — see the `TREE_TYPES` fact in §3). Counts **at the two-run noise floor** (per-cell-mean r² 0.9994); held-out-BY-SCENARIO R² 0.9847; trait pooled marginals KS 0.004–0.015. Per-cell trait **medians have model headroom** (§5) |
| **F_diff** | ✅ scale-up done; **C-validated Hainich only** | multi-layer soil, multi-PFT canopy, prognostic structure, self-computed calibrated NPP, NN λ/Vcmax hooks (Enzyme/Zygote gradients verified), grass faithful to ±10–15 %. Decadal (2009–2019) mean GPP ratio 1.066, interannual r 0.86, no drift |
| **E energy** | ✅ landed + **tower-validated**; nocturnal H diagnosed | `SEBEnergyClosure` closes `Rn=LE+H+G` to 1.4e-14 W/m²; 4 PLUMBER2 sites, 498k half-hours (ADR 0072); the night failure is the ground-heat **timescale**, `λ_g ≈ 1.0` not 7.0 (ADR 0073) |
| **Coupled multi-cell** | 🟡 5 biome cells, S wired | the coupled loop runs S+F+E and conserves carbon ~1e-12 gC; rung-4 attribution not done; the resilience battery is stubs |
| **Online / SpeedyWeather** | ⬜ not started | environment builds and runs (skill `online-coupling-env`); no coupled science |
| **Speed (goal #2)** | 🔴 **4.62× SLOWER than the C** | committed harness, §3 |

**The two `[VERIFIED]` global results that anchor everything** (don't re-derive):

- **ADR 0020's falsifiable test PASSED:** flux-conditioning beats climate-only **2.35×** on the warm+dry OOD
  holdout (ood R² 0.76 vs −0.16, `scripts/flux_ood_experiment.jl`). The climate-only `DirectEmulator` is
  retained ONLY as this benchmark.
- **The global offline S generalizes across cells** (K-fold-BY-CELL, real features): counts per-cell-mean
  **r² 0.9994 — at the seed1-vs-seed2 noise floor**; pooled+transient held-out-BY-SCENARIO **R² 0.9847** (an
  unseen climate regime). Artifacts `*_pooled_w20.{drf,rcop}` on `/p/tmp` (DVC); the committed `.drf`/`.rcop`
  are the Hainich demo.

**Still true across all lines:** F_diff and the coupled loop are **C-validated on Hainich only** — say
"Hainich only" wherever a result is single-cell; the global evidence is the *offline* S. And no milestone may
be called done on a five-cell result (ADR 0106, §4).

---

## 3. Verified facts — the load-bearing, durable, cross-cutting ones

### Model / data structure

- [VERIFIED] Integration is **daily**; no sub-daily physics except the soil-heat numerical substep. Daily
  output is a **runtime config flag** (`"timestep":"daily"`), never a recompile.
- [VERIFIED] LPJmL-FIT has **no surface energy balance**: ET = Priestley–Taylor equilibrium/demand–supply;
  soil temp uses **air temp** as the top Dirichlet BC; no H, G-as-flux, T_skin or Rn closure. All of that is
  component E (new physics), validated **out-of-model** against PLUMBER2 towers (ADR 0070/0072).
- [VERIFIED] Forcing consumed: tas, precip, swdown, **net** longwave (`lwnet`, downward-positive), `huss`
  (→VPD, hard dependency), CO₂. **Wind is read but unused**; **surface pressure is hard-coded** `p=1e5` in
  `photosynthesis.c`. E needs **wind + psurf** as genuinely new inputs (sourced — see E below).
- [VERIFIED] **Fire is ON (GlobFIRM)** ⇒ carbon closes only with fire + establishment:
  `ΔC = NPP − Rh − firec + flux_estabc`; `NBP_atm = Rh + firec − NPP − flux_estabc`. A fire-free
  `NEE = Rh − NPP` will NOT close. Mortality drivers: water stress, temp stress, growth efficiency, age.
- [VERIFIED] **Constant-CO₂ regime** (`with_nitrogen="no"` ⇒ unbounded CO₂ fertilization ⇒ future CO₂ held
  constant). OOD test = **warming/precip at constant CO₂**, not rising CO₂. NEE is diagnostic-only, so
  SpeedyWeather's missing carbon cycle is a non-issue. **Not** valid for CO₂-fertilization projections.
- [VERIFIED] Allometry is **re-derived, not co-predicted**: height = k_latosa·Csap/(Cleaf·SLA·wooddens);
  crownarea (Jucker 2022); LAI = Cleaf·SLA/crownarea; FPC = crownarea·nind·(1−e^(−k·LAI)); AGB = leaf+heart+sap.
- [VERIFIED] **`individual=true` config skips many C paths.** `light()`/`light_grass()` (cover/light
  competition) are **never called** (`annual_natural.c:117` gates on `!individual`); active grass reduction is
  `reduce_grass` (fpc-only, no carbon killed, fires 0/25 at Hainich). Per-PFT `gp_pft`/`gc_pft` are
  diagnostic-only; GPP uses the stand mean `gp_stand`. **Always confirm a C routine actually runs here before
  porting it** (the sessions-16/17/19 waste). Active param file = `par/pft_lpjmlfit.js` (beech = ANGIO
  allometry), **not** `par/pft.js`. `-DPERMUTE` randomizes daily PFT-depletion order ⇒ the C is
  non-deterministic / order-averaged. ⚠ The rule extends to **commented-out** expressions: the C source
  carries dead `/* test: */` branches that `grep` lands in (ADR 0135, CLAUDE.md §3).
- [VERIFIED] **Prototype cell: Hainich (DE-Hai) = global orderA 0-based index `42490`** (lat 51.25 / lon
  10.25; 98 % beech, PFT type 3). ⚠ **`28008` is Hainich in a DIFFERENT grid** and orderA `[28008]` is
  Sonoran desert — the two 67 420-cell coordinate files disagree on ordering and their paired soil files are
  **not** interchangeable row-for-row, so pairing orderA indices with the wrong grid shifts every cell
  silently (ADR 0083; both files and the rule in CLAUDE.md §1).
- [VERIFIED] **The per-cell soil column is READ from the C, not ported** (ADR 0050; skill
  `provision-coupled-cell`; mechanism + line thicknesses in CLAUDE.md §3). Layer thicknesses are a C
  **global** and every cell runs at 20 m — the per-cell Pelletier `soildepth` input is discarded — so
  plant-available mm = `whc_nat[l] × soildepth[l]`, where `whc_nat` is the patch-ensemble-mean **fraction**.
  It is **monthly, time-varying** and **`-DPERMUTE`-nondeterministic between runs** (1.6e-4 relative in layer
  0, global vs single-cell) ⇒ it is a provenance-bearing input, not a constant. Rooting: `beta_root` /
  `D95max` / `D95` are three different `ind` columns (all cm) and the tree test is **`D95max > 0`**, never a
  `Type` number — ids differ by biome.

### F_diff (fast core) — what is validated vs the C oracle (Hainich)

- [VERIFIED] **Gradient + conservation gate:** Enzyme reverse **and** ForwardDiff match FiniteDifferences to
  ~1e-11 for d(annual NPP)/dx through the full 365-day rollout incl. the λ ci:ca Newton solve; water closes
  ~1e-12; the prognostic canopy's pipe-model invariant holds to 3e-16 over 272 trees with exact carbon
  conservation, and a multi-year rollout tracks C tree height (9.34 vs 9.344 m) with no blow-up.
- [VERIFIED] **Level gaps were closed step-by-step against the C** (multi-individual canopy → GPP ratio
  ~1.06; coupled conductance↔carbon → transpiration ~1.02; two faithful `npp_tree.c` fixes → in-model CUE
  0.512 vs the C's ~0.46). Residual ~+7–17 % is an inherited GPP-phenology **level** offset, not a
  respiration bug; daily r ≈ 0.98–0.998. ⚠ **Read `GPP_F/GPP_C` as a LOWER BOUND on F's photosynthesis
  error** — three independent terms make F absorb less light or run a smaller Vcmax than the C (ADR
  0135/0136: `phen` placement, a missing `(1−snowcover)` factor, and the C's λ-bisection Vcmax basis).
- [VERIFIED] **The learned-closure hooks train and recover** (Vcmax `:vm` + λ, via the extension): Zygote and
  Enzyme-reverse gradients match FiniteDifferences to 1e-8…1e-10, recovery losses >96–99 %, cell GPP ratio
  1.093 → 1.010 with `:vm,:λ`. But the single-representative Vcmax lever only partially closes the level and
  degrades daily shape ⇒ the residual is **light/structure-limited**, not a parameter.
- [VERIFIED] **Grass thread CLOSED as faithful**: the apparent ~2–3× grass-NPP overshoot was a
  **reference-basis artifact** — against the C's own newly-built daily grass GPP/NPP, aggregate ΣF/ΣC 0.95,
  mean per-year 0.98, CUE 0.55–0.60 matches. The fix that mattered was per-PFT grass **phenology** (grass was
  getting beech GSI), plus a photosynthesis **demand-gate** + grass **establishment**; these are the
  coupled-rollout **default** now (tree-only paths byte-identical). One residual remains — §5 water-supply.
- ⚠ [VERIFIED 2026-08-12, ADR 0125/0126] **F runs BEECH's phenology and beech's parameters for every tree
  unless you pass `pft_ids` / `per_pft_params`** — true of every five-cell F number predating ADR 0126, and
  worth more than most single parameters (the Sahel's annual-assimilate ratio moves +1.01). The per-PFT table
  is committed and gated; nine parameters differ materially (`respcoeff` alone spans 6×). ⚠ **They do not all
  improve fidelity** — they fix the tropics and make boreal/mediterranean *worse*, because the earlier
  agreement came from two wrong parameters of opposite sign ⇒ quote them as an opt-in arm, never as "the fix".
  ⇒ **before attributing an F-vs-C gap to physics, check whether the parameter is per-PFT and F is using
  beech's.**

### Cost, speed and the patch ensemble (goal #2 — ADR 0093 answered ADR 0092; ADR 0084 corrected the numbers)

- ⚠ [VERIFIED 2026-08-14, ADR 0084] **THE EMULATOR IS 4.62× SLOWER PER CELL-YEAR THAN THE C IT REPLACES** —
  at cell 42490, npatch 25, 1 core: C **0.2666** core-s/cell-yr (marginal), emulator **1.1169** at F+E and
  **1.2329** at full S+F+E. **Quote 1.2329 and 4.62×.** ADR 0093's `1.096 / 3.8×` is **retired as a
  headline** — it was reproduced within 1.9 % but printed "coupled S+F+E" while running **no** Component S,
  and divided the C's whole-process wall time by cell-years instead of taking the marginal rate. Component S
  costs 5–22 % of the coupled run (9.4 % at Hainich), E costs 0.9 %, **the fast core is 99 %**. Harness:
  `scripts/bench_speed_gate.jl` · `scripts/bench_speed_gate_c.sh` · `scripts/profile_fdiff_hotspots.jl`
  (skill `speed-gate`). **Price every speed proposal against the JULIA cost model, never the C's** — four
  candidate architectures looked good against the C and are slower than the existing code at 8 patches.
- [VERIFIED 2026-08-07/14] **Where the cost is.** Julia: the **per-individual daily step is 51×** the C's
  (3.998e-3 vs 7.84e-5 core-s/ind-yr) while its per-patch fixed cost is only **0.066×** ⇒ the ~100× needed
  decomposes as **≈37× ordinary single-core engineering + ≈3× fewer patches**, so **the patch ensemble is the
  LAST lever, not the first**. **83 % of emulator runtime is the λ solve**, and not for the reason the plan
  assumed: `solve_lambda` (`src/fdiff.jl:655`) **is already fixed-iteration**, but takes its Newton derivative
  by **central finite difference** (`:673`) ⇒ **78–79 `photosynthesis` calls per individual per day** against
  the C's ≤30. Sweeping `nlambda` (no source change) gives **4.10× at nlambda=3 for −0.03 % on GPP**; a
  further **26.5 %** is three temperature-only `q10^` powers recomputed on every call (`:558/559/561`).
  ⚠ GPP is **non-monotone in `nlambda`** (±2.1 %, parity-like) ⇒ "25 iterations" is **not** evidence of
  convergence. C side: **72–86 %** is per-individual-per-day photosynthesis, the λ bisection alone **33.3 %**.
- [VERIFIED 2026-08-07] **Offline production is NOT cost-constrained** — the whole 2-seed × 2-scenario ground
  truth was 35 000 core-h (17 h on 2048 cores). The compute case exists only for **online** coupling.
- [VERIFIED 2026-08-07] **npatch is a NUMERICAL parameter**: 50 vs 25 (8 553 cells) moves every cell-mean by
  **<0.15 %**, and cost is exactly linear in npatch. But **the 25 patches are not 25 samples** — the
  cell-level seedbank (`getsapling.c`, `cell->treelist`) couples the TRAIT pool: n_eff 12.9 (n_trees), 8.2
  (Wooddens), 5.2 (SLA), 4.8 (D95max). The control that proves the channel: median **Height** — same stems,
  same patches, **not inherited** — has n_eff ≈ 25. Cutting 25→8 patches costs sd ×1.15–1.43.
- ⚠ [VERIFIED 2026-08-07] **AT npatch=25 THE C'S OWN ANSWER IS OUTSIDE THE 10 % BAND** for several acceptance
  quantities: bootstrap CV vegc **11.3 %**, Height median 11.3 %, minwscal median 11.0 %, **D95max median
  22.7 %** (Amazon, 50 000 patches). Production two-seed medians: n_trees 7.6 %, D95max 11.6 %; in the
  <2 stems/patch stratum (7 964 cells) 31.6 % / 42.7 %. **ADR 0106's `max(10 %, the model's own two-run
  spread)` clause is load-bearing, not decorative.**
- ⚠ [VERIFIED 2026-08-07] **THE TRAIT RESPONSE IS NOT A PER-CELL OBSERVABLE.** hist 2019 → ssp370 2099, the
  two seeds disagree on the **SIGN** in 33.2 / 36.7 / 34.4 % of cells (Wooddens / D95max / minwscal; S/N
  1.25 / 0.92 / 1.68), while the AREA-MEAN vegc response is −11.28 % against 0.055 % noise ⇒ score the
  response on a **multi-seed mean** and/or in aggregate. **Deattenuating for target noise re-points the
  diagnosis: TWO broken axes, not four** — SLA 0.851→**1.08** and minwscal 0.689→**0.99** are already right;
  only Wooddens (0.63) and D95max (0.51) are broken, exactly the two ADR 0046/0049 attribute to within-PFT
  differential survival. **Two more reference seeds = 35 000 core-h ≈ 17 h**, the best compute buy identified.
- [VERIFIED 2026-08-07] **REFUTED patch-reduction routes — do not re-propose** (numbers in ADR 0093 §4): one
  big patch (recruitment ∝ `exp(−LAI)`; merging 25×225 m² costs **−81.3 %** recruitment) · structural
  stratification/quadrature (VRF 1.00–1.13 for trait medians) · time-averaging (anomaly e-folding 32–41 yr) ·
  a smooth trait density with no individuals (`bm_inc_counter` is trait-correlated; factorising it out
  **flips the selection sign in PFTs 1/2/3/5**) · a roster ensemble without daily physics (3 of 4 hazards
  need per-tree daily `wscal`).
- [VERIFIED 2026-08-07] **SURVIVED, and cheap:** **share the soil column, never the canopy** — between-patch
  CV of patch-mean `wscal` is median **0.0126** / p90 0.0667 (41 587 cells) while mean-field light error is
  **−31 % at 5 m / −47 % at 20 m**; that asymmetry is what removes the Amdahl floor. **Trait-dependent
  mortality is nearly free** — keeping `mort_max(wooddens)` per-individual holds the Wooddens selection
  differential at 0.98–1.06 across all seven PFTs even with growth efficiency collapsed to a patch mean
  (`src/trait_mortality.jl`, wired, **default OFF**). A **bounded Beta on each PFT's own trait interval**
  beats the shipped copula 2–3× on per-cell KS (0.042–0.073 vs 0.129–0.173), two moments, no fitting. **The
  determinism dividend is free**: predicting the ensemble expectation rather than drawing a realisation is
  worth **+2.9 to +14.4 pp** of cells inside the 10 % band.
- **📌 STANDING ASK TO THE INTEGRATOR — wire the speed gate as a REQUIRED CI check (ADR 0084 §6).** No gate
  has ever watched performance, which is how a 3.8× regression survived ~40 sessions. **Trigger: the next
  merge to `main` that touches `src/**`.** Design constraints, because the obvious form does not work: a
  GitHub runner is not the cluster, so the gate must threshold a **ratio measured inside the same job** (e.g.
  arm F at `nlambda=25` vs `nlambda=1`), not an absolute core-s figure; and the pinned `_t8` artifacts
  (180 MB on `/p/tmp`) are unreachable from a runner ⇒ the CI arm must be **F or F+E**, never S+F+E. Until it
  lands the gate is manual and ADR 0084's table is its baseline.

### Method rules for scoring — the cross-line results; the *procedures* are in the skills

⚠ **The `residual-diagnosis` skill is the working document for all of this** (2 278 lines, ~40 named traps,
each keyed to the ADR that paid for it) — **invoke it before chasing any residual** instead of re-deriving.
It carries: same-name-≠-same-quantity (ADR 0035) · measure-the-baseline-before-arguing-from-code-structure
(0108) · a reference basis has more than one axis (0105) · a metric a null also passes has no power, and
*derive* what the null must return **before** the run (0112/0184) · basis errors sort into ratio-vs-level
(0060) · is the target noisier than the residual (0093) · the degenerate-denominator guard (0031/0032). Two
live elsewhere: the **upstream-parameter relaxation-number** check — `dt·(Σ conductances)/(thickness · heat
capacity)` at *our* step, because an adopted `z1 = 0.2 m` gives 1.125 at the daily step and turns the flux
into a day-to-day difference of its driver — plus the rule that a diagnosed flux belongs to the **start** of
the step, are in `plumber2-reference` (ADR 0074); the C-side accumulator/dead-code traps are in `CLAUDE.md`
§3. Kept here are only the results those rules produced, and the two with no other home:

- ⚠ [VERIFIED 2026-08-06, ADR 0105] **An attribution arm inherits every basis error of the harness it runs
  in.** ADR 0054's headline (teacher-forcing `n_prev` removes 59–72 % of coupled count error) was measured on
  the driver's **modal** patch against the count model's own *prediction*; re-measured on the **25-patch
  ensemble** against the C's truth, teacher forcing is **WORSE in all five cells**. **The METHOD survives,
  the verdict does not** — free-running, `n_prev` is the model's own previous target, so its absolute level
  **cancels** and only the year-on-year change reaches the stand; that cancellation is *protective*, which is
  why re-introducing the level (teacher forcing, or the ADR-0103 anchor) makes the stand worse.
- [VERIFIED] **Never score a free-running rollout without also running the TEACHER-FORCED arm** — a free
  rollout is off the training basis by construction and **integrates** any one-step bias, and it confounds
  resilience metrics (an unanchored recursion manufactures autocorrelation and slow recovery). Ready-made:
  `scripts/biome_slow_oracle_probe.jl::run_cell(k; teacher=true)`. Measured: the coupled **exposure bias is
  EMPTY** offline (one-step bias −0.0014 stems/patch/yr held-out-cell OOS on counts of ~10; AR gain 0.562 ⇒ a
  **bounded** 2.28× amplification) ⇒ the residual is F's canopy diverging from the C's, not S's training.
- [VERIFIED 2026-08-05] **The noise floor is the only honest scale, and watch its denominator** — report the
  absolute error next to the ratio: Sahel SLA reads **7.9 floors** but is a 4.6 % error (floor 0.0002), while
  the Amazon count floor is **29 % of the mean** because the cell carries only 4.7 trees per patch.
- [VERIFIED 2026-07-28, ADR 0030] **How to score a stochastic-truth emulator.** A seed1-vs-seed2 per-cell
  correlation is a *realization-vs-realization* r, NOT a predictor ceiling: with `m = μ(env)+δ(RNG)` and a
  prediction of reliability `rel_P`, the reachable ceiling is `√(rel_P·rel_Y)` and `r_center = emu_r/ceiling`.
  Always also report `sd(pred)/sd(truth)` — a correlation is scale-blind, and the copula reproduces only 0.55
  of the true between-cell Wooddens spread. Split-half separates finite-sample noise from trajectory
  divergence.
- ⚠ [VERIFIED 2026-08-11, ADR 0121] **A NULL CONTROL VALIDATES THE TRANSPORT, NOT THE PAYLOAD.** A
  substitution experiment's null (machinery active, every decision handed straight back to the model)
  reproduced a 20-year run exactly and was still blind to the defect that made the arm's numbers wrong 1.37×,
  because the null path **never serves the payload**. ⇒ **green null + diverging arm ⇒ suspect what you are
  FEEDING the interface before you suspect the interface**, and when a quantity is read out of shared state,
  find every writer of that state and check whether any runs after your read point.
- ⚠ [VERIFIED 2026-08-10, ADR 0061 §5] **A join between two tables that share column names can compare a
  column against ITSELF and report a perfect match.** Nine columns printed `0.000e+00` because polars kept
  one column per colliding name. **Prefix one side's columns wholesale before joining**, and treat an exact
  zero on a float comparison of two independently written representations as an aliasing bug — the honest
  signature of agreement is the writers' format floor (~5e-6 for `%g`), not zero.

### Resilience / dynamics (line M; full numbers in ADR 0055)

- [VERIFIED 2026-08-05] **The `~0.2-wet → ~0.75-dry` lag-1 AC gradient `DEVELOPMENT_PLAN` §5 quotes is NOT in
  this run** (52 224 cells, per-patch detrended: **flat at 0.452–0.541 over all ten P/PET deciles, driest
  LOWEST**). **The VARIANCE is the climate-graded quantity — CV 1.149 dry → 0.143 wet, 8× — use that as the
  criterion.** ⚠ 20 yr is all the historic table has and detrending is a high-pass filter ⇒ τ ≳ 10 yr is
  unresolvable here, and both sides must share the estimator.
- [VERIFIED 2026-08-05] **The coupled emulator's memory is right and INTERNAL — it lives in F's carbon pools,
  not S's recursion** (year-shuffled forcing leaves AC at 0.460–0.653; `slow = nothing` alone carries
  0.454–0.691) ⇒ **a detrended AC is blind to the count-level drift.** And **an AC is NOT a recovery rate —
  ~20× apart**: AC-implied τ 1.2–2.9 yr vs a measured pool-perturbation e-folding of ~50 yr. Under CYCLIC
  forcing the coupled AGB has **no steady state** (drift 1.39–5.15× / 100 yr); no limit cycle.

### E (energy) — the tower validation (line E; ADR 0070/0072/0073)

- [VERIFIED] Closure to machine precision (13 824 cases; ForwardDiff-vs-FD; Float32); demo daily 1.4e-14,
  biome ≤3e-14 W/m²; Monin–Obukhov aerodynamic identity ~3e-11. Emergent climate-correct Bowen ordering
  (tropical LE-dominated ~0.10; semi-arid/mediterranean H-dominated; boreal low-flux; 2018 drought 0.89).
- [VERIFIED 2026-07-28, ADR 0072] Experiment A (the closure alone: tower forcing **and the tower's own LE**,
  so F's ET error is excluded — `FToE` hands E `le` already formed as λ·ET, hence **E's own outputs are
  T_skin / H / G, not LE**), 497 936 half-hours at 4 sites: **Rn VERIFIED** (R² 0.986–0.996) · **T_skin
  VERIFIED where observable** (daily RMSE 1.41–1.97 K, R² 0.76–0.95; **not at Hainich** — no `LWup`) · **H
  verified in the MEAN only** (76.4 % of DE-Hai daily means inside PLUMBER2's own ±40.9 W/m² band, but daily
  R² 0.125–0.778 and **nocturnal R² −1.0…−5.6**). Half-hourly H R² is **inflated by the diurnal cycle** —
  quote the daily number. Frozen as a CI gate in `energy_closure_tests.jl`.
- [VERIFIED 2026-07-28, ADR 0073] **The nocturnal-H failure is a ground-heat TIMESCALE error, not an
  aerodynamic one.** `H` is the exact residual `Rn_m − LE − G_m`, so its error obeys identically
  `ΔH = ΔRn − ΔG + ε_obs` — and **`g_a` is in none of those terms** (the modelled nocturnal `g_a` is within
  0.7 % of the measured-`u*` value; a 100× bracket never reaches positive nocturnal R²). ⇒ **do NOT retune
  `stab_amp`** — it is **withdrawn** as an integration point. Three independent lines give **`λ_g ≈ 1.0`, not
  the 7.0 default**, at the daily step `run.jl:93` actually runs (daily H R² 0.03→0.64 DE-Hai, 0.33→0.74
  AU-ASM); `lambda_g` is the live **E→M** integration point (no default changed). **Reference-basis limit:**
  mean nocturnal `ε_obs` is −62.3 / −47.5 W/m² at AU-Tum / AU-Rob ⇒ **those towers cannot score a closing
  model's nocturnal H at all**; DE-Hai closes (−0.32) and is the site to tune against. Nocturnal R² > 0 is
  **not** reachable by any `λ_g` in this form — that needs force-restore / two-layer soil + canopy heat
  storage, which **bounds line O's sub-daily online coupling**.
- [VERIFIED 2026-07-28, ADR 0070/0071] **The observational reference and both new forcings are on disk** —
  PLUMBER2 v1-0, 9 sites (`config/paths.yaml` `data.energy_reference*`; skill `plumber2-reference`), and
  daily `sfcwind` + `ps` from ISIMIP3a obsclim GSWP3-W5E5 remapped onto orderA cells (skill
  `obsclim-cell-remap`). **The lat/lon ↔ orderA mapping is PROVEN** (obsclim `tas` vs the model-grid
  `temperature_test.clm`, `max|Δ| = 0.000 °C` over 365 days at all 5 biome cells) — **reuse that route for
  ANY new per-cell input.** ⚠ The raw SSP370 GCM set has `sfcwind` but **no `ps`** ⇒ future psurf is still
  open. Hainich's 0.5° cell vs the DE-Hai tower: wind −10.1 %, psurf +1649 Pa ⇒ **score tower fluxes with
  TOWER forcing, not grid forcing.** The observational data's own traps (fill values that survive
  `np.asarray`, a `_qc` flag that means MISSING, and `Qle_cor` that can be ≈0 garbage rather than a fill
  value) are in the skill — read it before loading a site.

### S (slow) and the ground truth

- ⚠ [VERIFIED 2026-07-31, ADR 0038] **The ssp370 `random_seed2` GROUND TRUTH IS A BIT-IDENTICAL COPY OF
  SEED1 — there is no independent second realization of ssp370.** Both `ind_2020_2100.csv` are
  193 097 583 638 B with equal md5 on sampled blocks. Cause: the seed2 config sets `"random_seed": 2` but
  points `restart_filename` at the **historic seed1** restart, and under `-DFROM_RESTART` the per-cell RAND48
  state is restored from the restart ⇒ **the seed setting is inert** (CLAUDE.md §3 has the full mechanism).
  **Why this is cross-cutting:** any noise floor / ceiling / `%GAP` built from it is FABRICATED (`floor_r ≡ 1`)
  and raises **no error**. The historic pair IS genuinely independent. ⇒ **criterion 1's `%GAP` and criterion
  4's `r_center` are NOT computable for the pooled/ssp370 artifacts.** Gate every new member with
  `scripts/diagnose_ind_seed_independence.py`; equal file size to the sibling is the copy signature.
- ⚠ [VERIFIED 2026-07-28, ADR 0031] **The Component-S training population WAS truncated; fixed.** Every
  `build_slow_*.py` selected `TREE_TYPES=[1,2,3,4,5]`, but `Type` is the 0-based `pftpar` index and **ids 0–6
  are all seven tree PFTs** ⇒ id 0 (tropical broadleaved evergreen) and id 6 (boreal larch) were dropped:
  **32.5 % of 197.7 M survivor tree stems, and 9 011 of 54 020 tree-bearing cells (16.7 %) invisible**.
  **Now ONE imported constant** (`lpjmlfit_emulator.data.TREE_TYPES`) — never re-declare it. Hainich has only
  ids 1–5, which is why every single-cell gate stayed green. **Every "global" S number published before
  2026-07-28 is on the ids-1..5 population** and is superseded by the `t7` artifacts, not restated.
- [VERIFIED] Sibling offline S emulator at `/p/projects/open/Jamir/emulator`. Published noise floor
  {Height 0.020, agb 0.113, npp 0.062, LAI 0.025} — the ~11 % cell-mean agb floor is the yardstick. S is
  **not differentiable** and stays out of the gradient loop (ADR 0014).
- ⚠ [VERIFIED 2026-08-04, ADR 0045/0046] **Recruit traits are *inherited*, not uniform draws**, and a
  per-cell trait statistic is **not** a composition statistic: establishment is a two-channel mixture whose
  inherited weight is closed-form `4/(4 + n_elig)` ⇒ **≈44 % at Hainich, ≈80 % in low-diversity cells** ⇒ the
  establishment marginal is a **functional of the live community**. The measured warming shift is
  **within-PFT, within-age-class selection** (22.2 % composition / 51.3 % within-PFT / 26.6 % interaction;
  the within-PFT part is +112 % within-age-class, with age structure *opposing* it). ⚠ Do **not** port
  `mort_max` alone as "denser wood survives better" — net selection is not sign-definite (CLAUDE.md §3).

### The C oracle — the two provenance rules every line's numbers rest on

*(Mechanics, env-var names and the full rebuild history: CLAUDE.md §1/§3 + skill `lpjmlfit-cbinary`.)*

- ⚠ [VERIFIED 2026-08-10/11, ADR 0061→0123] **The oracle binary has been rebuilt and carries opt-in,
  inert-unless-set hooks.** With their environment variables unset it is numerically identical to the
  previous build (139 decoded quantities + `globalflux` + `ind`); **with a rung-2 variable set it defers its
  demographic kills to the end of the growth loop** — mathematically inert, not bit-identical, and it moves
  the C's own trajectory by 0.05 % of stem-years over 20 yr ⇒ disclose that with any rung-2 number. Standing
  rules for **any** rebuild: run `scripts/diagnose_cbinary_rebuild_equality.py` before quoting a
  C-vs-emulator number (nothing gated rebuilds before this), and never `cmp` a NetCDF — a wall-clock
  timestamp in `history` calls 20 of 21 outputs different for identical physics ⇒ compare **decoded
  variables**.
- ⚠ [VERIFIED 2026-08-03, ADR 0041] **A SUBSET RE-RUN IS NOT A PER-CELL REPLICA OF THE GLOBAL RUN** — the
  per-cell *seek* is decomposition-independent, the *evolution* is not. Same binary, same restart, same
  forcing: one cell alone diverges from the 67 420-cell ground truth at the first step; a 21-cell block is
  bit-identical for 15 years and then diverges. **The RNG is not the cause and the mechanism is
  unestablished.** ⇒ two ground-truth members are a valid seed pair only if run with the same binary AND the
  same `--ntasks`; any equivalence gate needs a **matched-decomposition** run; and a single-cell re-run
  scored against *global* truth compares two different trajectories.

---

## 4. Frozen decisions — owner decisions + the constraint subset

### 🔓 OWNER DECISIONS — standing, do not re-litigate

- **PER-YEAR ESM SPEED IS THE GOAL; THE SPIN-UP SAVING IS NOT (ADR 0094, owner 2026-08-07).** Verbatim:
  *"teh savigns for the spin-up is boring and not my main goal. I want a fast emulator that can be run in an
  ESM without to much compute cost."* Goal ordering: **(1)** faithful per ADR 0106 → **(2)** fast enough for
  an ESM → **(3)** coupled. This **supersedes ADR 0092's** compute-case conclusion. The spin-up saving stays
  true and useful; it is **not** the compute case and must never be offered as the answer to *"is it fast?"*.
  Gate: ≤**0.030** core-s/cell-yr intermediate, ≤**0.0135** target (⚠ a convention = 10 % of a measured
  SpeedyWeather coupled cost, not an owner-set budget — replaceable); **every speed claim names the
  atmosphere it is measured against.** Fidelity is NOT relaxed to buy speed.
- **THE OWNER APPROVED THE ERROR-ATTRIBUTION LADDER (ADR 0093 §6, 2026-08-07):** *"I want to execute your
  plan."* Executable form + rung ownership + pre-registered gates: **`EXECUTION_PLAN.md`**. Owner answers to
  the three open questions: the **compensating-errors** hypothesis is plausible (*"yes sounds true"*) ⇒ if a
  rung scores worse than the coupled result that is the FINDING, not a failed test; the rung-2 interface is
  **NARROW** (replace only who dies and who establishes, leave turnover/allocation/growth to the C).
- 🎯 **THE ACCEPTANCE CRITERION — what "finished" MEANS (owner 2026-08-06; ADR 0106). This SUPERSEDES every
  per-milestone stopping condition, including "at the noise floor".** Verbatim: the emulator must **fully
  emulate the original model**, "of course also and **especially under climate change**"; done =
  **everything, including trait distributions AND medians, within 10 % error**; and "**only finished when
  it's proven to be correct on ALL cells, not only a handful of test sites**" (= the 54 020 tree-bearing
  cells). Both scenarios AND the response between them. A noise-floor statement is still the right
  DIAGNOSTIC; it is no longer the ACCEPTANCE TEST, and **no line may call a milestone done on a five-cell
  result again.**
  ⚠ **One clause needed a decision and has a stated default, not the owner's words:** the original model is
  stochastic and its own two runs differ by **29 % of the mean** for the per-patch count at
  `tropical_amazon` (≈4.7 trees/patch), so a literal 10 % is unmeetable there by ANY emulator. Default in
  use: tolerance = **max(10 %, the original's own two-run spread for that quantity in that cell)**.
  ⚠ **The binding constraint is the climate-change clause, not the fidelity numbers** — work that improves
  present-day agreement is not progress unless it also opens a response channel.
  ⚠ **QUALIFIER (ADR 0108 §1): "the warming response is indistinguishable from zero" is a COUPLED,
  five-cell statement, NOT a global or an offline one.** Measured **offline** on the C's own features, 52 074
  cells, K-fold-by-cell OOS, the emulator's per-cell trait shift regressed on the original's has slope
  **+0.85** (SLA) / **+0.35** (wood density) / **+0.16** (`D95max`) / **+0.69** (`minwscal`), sign agreement
  57–72 % ⇒ the **offline** response channel is **partially open and axis-dependent**; it is the **coupled**
  response that collapses. Same run gives the first global both-scenario level score: per-cell trait medians
  within 10 % for **70.7 / 71.4 / 28.0 / 62.1 %** of cells (historic). Do not quote the unqualified sentence.
- ⚠ **METHOD RULE, ALL LINES (ADR 0108; skill `residual-diagnosis`): MEASURE THE BASELINE BEFORE ARGUING FROM
  CODE STRUCTURE THAT A CHANNEL IS CLOSED.** "Input X is a frozen constant" bounds what **X** can carry and
  says **nothing** about what the model does, because the other inputs are not frozen. A "structurally zero
  by construction" claim reached an ADR draft, a changelog entry, three source-comment blocks and a test
  header before **one 3-minute job** measured the response as clearly non-zero. Name a **response**
  statistic, not a level one, and measure it on the **shipped** artifact first — that number is the reference
  basis, and "success" means beating it.
- 🚫 **CO2 — STANDING, DO NOT RE-LITIGATE (owner, repeatedly; ADR 0004 + 0107).** The emulator **does not see
  CO2 and must not respond to it.** It responds to **climate**, and the SSP scenarios already carry the
  CO2-driven climate signal. LPJmL-FIT runs **constant CO2** for future runs **on purpose**: with
  `with_nitrogen="no"` its CO2 fertilization is unbounded and a rising-CO2 run blows vegetation carbon up —
  i.e. its own CO2 response is wrong. ⇒ `CO2_CONST = 369.0` in every training row is the design working as
  intended, and the emulator having **no CO2 response is FAITHFULNESS, not a gap**. **Never** propose a CO2
  feature, varying-CO2 training rows, or a new model run for CO2; **never** list the absence of a CO2
  response as a defect of the emulator. The correct statement is a validity-envelope disclosure only.
- **REUSE + LICENSING IS CLOSED (ADR 0080/0081, owner 2026-07-28).** The owner is a member of **both** the
  LPJmL-FIT group and **TUM-PIK-ESM** (which hosts SpeedyWeather.jl / Terrarium.jl /
  LPJmL-hybrid-photosynthesis) ⇒ **reuse those models freely; raise no licence question and do not re-audit
  an upstream licence.** NeuralCrop.jl is usable too (CC-BY-NC permits the non-commercial research use we
  make). Reuse is the **default**; reimplementation must be justified in an ADR. **The one standing
  obligation is TRANSPARENT CITATION** across four surfaces kept in agreement —
  `docs/third_party_licensing.md`, `CITATION.cff`, `docs/src/refs.bib`, and source-file headers (skill
  `reuse-citation`) — with provenance stated *accurately*, neither overstated nor omitted.
- **M's coupled BASELINE REGENERATION is PRE-AUTHORISED (owner 2026-08-05)** for deliberately enabling
  `WaterParams.wscal_leafon = true` (ADR 0051). ⚠ The other half of that authorisation is **moot**: the
  Component-S level anchor's flip criterion failed on the patch ensemble and the default stays `anchor = 0`
  (ADR 0105) — do not read it as an outstanding action. The discipline is not waived: own commit,
  before/after numbers recorded, CI green. A third baseline-moving change is a fresh decision.
- **HPC compute is not a reason to defer (owner 2026-08-05):** *"when retraining is needed we do it — we have
  the whole HPC at our service, so there is no need to procrastinate."* Do not park a measurement or a global
  re-fit *solely* because it costs cluster time; scope it and submit it. (Still SLURM-only, still tagged per
  line.)

### The ADR subset that constrains *any* line's work

**Single source of truth: [`docs/decisions/README.md`](docs/decisions/README.md)** (151 ADRs, with the
per-line number blocks and tiers). This file does not duplicate the index — that duplication was a
merge-conflict source and drifted out of order (ADR 0029). ADRs are **immutable once accepted**; supersede,
don't edit.

| ADR | Constraint you must respect |
|---|---|
| 0003 | **Flux-then-integrate** carbon conservation — fire + establishment are IN the budget (`ΔC = NPP − Rh − firec + flux_estabc`) |
| 0004 | **Constant-CO₂ regime** — CO₂ is not a feature and not a projection axis; OOD means warming/precip at fixed CO₂ |
| 0014 | **Runtime `[deps]` stays EMPTY** — AD/ML/coupling deps are `[weakdeps]` + extensions; Aqua enforces it |
| 0018 | **Growth-ownership split** — F_diff owns representative-individual carbon growth; S owns distribution + demography |
| 0020 | **Component S is FLUX-DRIVEN**, not climate-equilibrium — condition on F's delivered fluxes + AR state + slow boundary; this-year raw climate is dropped |
| 0023 | **Train/inference consistency is load-bearing** — the runtime feature vector and the training table must match exactly (a silent mismatch is the worst failure mode here) |
| 0028 | **Branch + worktree per line**, self-merge on green branch CI (supersedes 0013's main-only rule) |
| 0029 | **Per-path line ownership + frozen cross-line contracts** — don't edit another line's exclusive paths |
| 0090 | **CI is PATH-FILTERED — most commits trigger NO gate**: a gate that does not trigger reports **no check-run**, so polling for `test (lts)` hangs forever; derive the expected set from `git diff --name-only origin/main...HEAD` |
| 0091 | **The full data-flow diagram is code-derived and the staleness gate is REAL** — `docs/src/generated/dataflow_full.mmd` comes from `registry.jl`, and component-to-component edge labels are `fieldnames()` of the `src/interface.jl` structs ⇒ **changing ONE field of `SToF`/`FToS`/`FToE`/`EToF`/`EToATM`/`SToE`/`AtmForcing` makes the committed diagram stale and reds `CI` with no registry edit at all** — rerun `julia --project=. scripts/gen_diagrams.jl` in the same commit. ⚠ A green docs build is **not** evidence a mermaid diagram renders (ADR 0091 amendment) |
| 0092 | **The patch ensemble question — ASKED here, ANSWERED by 0093/0094.** Patches are still needed for (a) the comparison basis (the C's gridded truth IS a patch mean), (b) NONLINEARITY (`mean(f(state)) ≠ f(mean(state))`), (c) within-patch suppression structure — but patch *reduction* is worth only ~3× and is **rung 5c, the last lever**, not the first |
| 0106 | **The acceptance criterion** (above) — supersedes every per-milestone stopping condition |
| guardrail 4 | **Opt-in, default byte-identical** — new physics leaves every committed baseline and the AD trainer unchanged until deliberately enabled. ⚠ **Corollary (bitten 3×): it protects you from enabling too early, NOT from never enabling** — pre-register the flip criterion in the same ADR and name it in the *consuming* line's STATE as an ACTION |

---

## 5. Frontier — the open gap, and the deferred issues

**Per-line milestones/gates/NEXT live in `lines/<X>/STATE.md`; the order of work is `EXECUTION_PLAN.md`.**

**The one open scientific gap worth naming here** (line S owns it): trait **per-cell medians** have model
headroom — per-cell-median r SLA 0.87 / minwscal 0.78 / D95max 0.74 / **Wooddens 0.52**, against a
seed1-vs-seed2 floor of **0.90–0.97** ⇒ the signal is **learnable, not RNG-limited**. Cause (not a bug): the
copula conditions on flux+boundary and deliberately excludes stand-state (ADR 0025). Deattenuated, only
**Wooddens and D95max** are actually broken (§3).

### Deferred / known issues (fidelity refinements of an already-in-band core — not blockers)

- **[TODO, DEFERRED] Per-PFT competitive grass water-supply**: `daily_step_canopy` runs one stand-level
  FPC-weighted `wscal` (tree-dominated, saturates near 1) with no competitive per-layer depletion, vs the C's
  per-PFT `wscal` + sequential `aet_cor` cap. **Deferred behind the `FluxHooks` learned lever** because
  `-DPERMUTE` makes a faithful port non-differentiable/non-deterministic and per-PFT `wscal` is
  half-degenerate. Design: `docs/notes/water_supply_perpft_design.md`.
- **[TODO] `sapwood_bg` prognostic growth**: the below-ground root-sapwood pool is added but
  **static-seeded** (opt-in, default byte-identical; in-model CUE 0.512→0.497). ⚠ The C carries **two**
  below-ground wood pools and they are a producer/consumer pair, so a one-field port **leaks carbon** (ADR
  0127), and the demand is paid on **leaf** growth, not stem growth (ADR 0132). Design:
  `docs/notes/sapwood_bg_design.md`.
- **[TODO] Lift the Enzyme pin / the Julia-1.11 canopy guard** (`Enzyme = "0.13.0 - 0.13.188"` in **both**
  `Project.toml` and `test/Project.toml`) when a fixed Enzyme ships — still blocked upstream.
- **[TODO] Lift the `JET` pin** (`JET = "0.9, 0.11"`) by migrating `test/jet_tests.jl` to JET 0.12's
  replacement scoping API. JET **0.12.0** removed the `target_defined_modules` config that `jet_tests.jl:6`
  passes ⇒ `JETConfigError` ⇒ `test (1)` (Julia 1.12) errored repo-wide on a fresh resolve, while
  `test (lts)` stayed green. Second instance of the "**CI resolves deps fresh ⇒ a missing `[compat]` absorbs a
  breaking bump**" class, after Enzyme 0.13.189. ⚠ **Two lines pinned it independently and concurrently** —
  the clearest sign yet that a repo-wide dep break wants ONE integrator action, not four parallel ones.
- **[TODO] Integrator:** wire the **speed gate** as a required CI check (§3, ADR 0084 §6).
- **[TODO] Owner actions**: ratify ADR 0018; the "(c)" nitrogen-track discussion (**P6 is gated — do not
  start it before that conversation**); close stray Dependabot PRs; the `eval`-filename allow decision.

---

## 6. Pointers (don't duplicate here)

- **Environment / build / test / C-binary / CI runbook** → `CLAUDE.md` (+ `config/paths.yaml` for paths,
  `config/hpc_slurm.yaml` for SLURM). Skills in `.claude/skills/` automate the mechanical loops — consult the
  matching one instead of re-deriving its steps.
- **Source map** (`src/` + `ext/`) → `CLAUDE.md` §7. In brief: `fdiff.jl` = the differentiable daily core +
  canopy rollout + allocation/growth (`annual_step!` lives in `components/fast.jl`); `conservation.jl` =
  softmax/flux-then-integrate/budget residuals; `interface.jl` = the S↔F↔E I/O contract; `run.jl` = the
  coupled loop; `components/slow.jl` = S (`DemographicSlowEmulator` + `FluxDrivenSlowEmulator` +
  `RecruitCopula`); `climbuf.jl` = the online transient boundary; `components/energy.jl` =
  `SEBEnergyClosure`; `ext/FDiffTrainingExt.jl` = the NN-hook trainers.
- **Deep dives**: `docs/notes/phase1_p3b_water_closure.md`, `docs/notes/phase2_slow_emulator.md`,
  `docs/notes/phase3_fdiff_cbinary_validation.md`, `docs/notes/sapwood_bg_design.md`,
  `docs/notes/water_supply_perpft_design.md`.
- **Session narrative** → **`lines/<X>/JOURNAL.md`** (per line, append-only). The root `JOURNAL.md` holds the
  pre-2026-07-28 history and is now the **INTEGRATION journal** — appended only from the `main` worktree
  (single-writer ⇒ conflict-free). Never append line narrative there.
- **Change log** → write a **`changelog.d/<X>-<slug>.md` fragment**; the integrator collates into
  `CHANGELOG.md` inside the merge `flock` (`scripts/collate_changelog.py`; ADR 0095). **Never edit
  `CHANGELOG.md` from a line branch.**
- **Parallel-line protocol** → `CLAUDE.md` §9 + ADR 0028/0029; ownership map in ADR 0029; mechanics in the
  `repo-commit` skill. **Per-line state** → `lines/<X>/STATE.md` (§0 router).
- **Archived pre-consolidation docs** → `docs/archive/` (also in git history).
