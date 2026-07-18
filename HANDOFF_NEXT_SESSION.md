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
- **Phase 3 (session 5b/5c/6/7/8) — scale-up steps 2, 3, 4, 5, 6: DONE.** (5b) multi-layer 23-layer soil;
  (5c) multi-individual/multi-PFT canopy — GPP level gap CLOSED (0.57→1.06); (6) coupled
  conductance↔carbon — **transpiration level gap CLOSED (1.32→1.02)**; (7) self-computed radiation +
  phenology — **the two C-output crutches REMOVED** (standalone F_diff self-computes its GSI phenology
  + dynamic-albedo `eeq`, matching the dropped C outputs at r 0.99 / 0.999); (8) **dynamic (prognostic)
  canopy structure + the `SharedState`/`AbstractFastCore` adapter** — per-individual pools grow from
  allocated `bm_inc` (pipe-model allocation port, invariant to 2.9e-16, AD matches FD), and `FDiffFastCore`
  wires `FDiff` behind `step!`/`annual_step!` (the flux-then-integrate S↔F handoff).
- **Phase 3 (session 9) — scale-up step 7a: SELF-COMPUTED CANOPY NPP CALIBRATED; the `bm_inc` crutch
  REMOVED.** Two faithful-to-`npp_tree.c` fixes in `FDiff.autotrophic_respiration` (growth-resp floor
  sharpened via `RespParams.βgrowth=50`; fine-root maintenance phen-gated) took standalone annual NPP
  **−25 → +663 gC/m²/yr** (C 507; CUE 0.52 vs 0.46; daily r 0.987); in kernel-isolation the respiration
  **total Ra matches the C to 0.5 %** so the overshoot is the inherited +17 % GPP-phenology level, not a
  respiration bug. The coupled loop now runs **fully self-driven** (grows H 9.41→10.28 over 8 yr, no
  blow-up). Suite **25,865 pass / 0 fail / 4 broken** (JET/Aqua/gradient green); Runic-clean. See §13.
- **Phase 3 (session 10) — scale-up step 7b: GRADIENT-BASED ONLINE ROLLOUT TRAINING (NN λ/Vcmax hooks +
  finished TBPTT loop).** Dependency-free `FDiff.FluxHooks` (optional learned Vcmax/λ multiplicative
  corrections; identity fast path ⇒ baselines byte-identical) + `ext/FDiffTrainingExt.jl` package
  extension (Lux MLP, zero-init ⇒ untrained = identity; `train_fdiff_rollout!` = the finished port of
  NeuralCrop's TBPTT scaffold, Zygote reverse + Optimisers + detached state carry). Gate: identity,
  Zygote-vs-FiniteDifferences NN-param gradient (rtol 1e-4), and recovery of a known correction (loss
  0.675→1.4e-3, recovered scale ≈1.31 vs 1.30). **Finding:** the single-representative C GPP gap is
  light-limited (co-limitation saturates at `je`), so Vcmax is the wrong lever there (fit only 0.64→0.79,
  degrades daily r) — the learned correction belongs on the coupled canopy path (Enzyme-reverse, the
  documented NEXT). ADR 0016; report §14. Runtime `[deps]` still empty.
- **Phase 3 (session 10 cont.) — scale-up step 7b-canopy: NN TRAINING ON THE COUPLED CANOPY PATH via
  ENZYME REVERSE.** Per-individual `FluxHooks` in `daily_step_canopy` (identity fast path ⇒ canopy
  baselines byte-identical) + `train_fdiff_canopy_rollout!`/`fdiff_canopy_gpp_loss` (Enzyme reverse —
  `daily_step_canopy` mutates arrays so Zygote can't cross it). **The AD-through-mutation follow-up (open
  since step 2) is CLOSED and proven: the Enzyme gradient w.r.t. the NN params matches FiniteDifferences
  to 1.2e-8** through the mutating multi-individual path; recovery of a known correction (loss 0.205→1.1e-3,
  scale ≈1.18 vs 1.20). `Enzyme` is now a 4th extension trigger; runtime `[deps]` still empty. Gate
  `nn_canopy_training_tests.jl`; report §15; ADR 0016.

---

## ⭐ WHAT LANDED IN SESSION 10 (on `main`) — GRADIENT-BASED ONLINE ROLLOUT TRAINING: NN λ/Vcmax HOOKS + FINISHED TBPTT LOOP (scale-up step 7b)

**The milestone the differentiable-first core (ADR 0014) exists to enable — train a learned closure
end-to-end through the differentiable rollout — landed and is gate-verified on the proven
single-representative path.** Two pieces (ADR 0016):

- **(a) Dependency-free NN hooks in the physics (`FDiff.FluxHooks`).** Optional LEARNED multiplicative
  corrections to the two levers a hybrid trains: Vcmax (`vm`) and the ci:ca ratio `λ`. Each field is
  `nothing` (pure physics — the identity fast path, so **every regression baseline is byte-identical**)
  or a callable `feat -> scale` (`scale ≈ 1`; `feat = [temp, swdown, daylength, apar, w_soil, co2]`).
  `photosynthesis` gained a `vm_scale` kwarg (applied at Vcmax → propagates into potential conductance +
  `rd`); the λ hook re-clamps to the shared bracket `_LAMBDA_LO/HI`. Threaded through
  `daily_step`/`rollout`/`rollout_daily`/`annual_npp`. The runtime only ever *calls* the hook — it stays
  dependency-free.
- **(b) The finished TBPTT loop, a PACKAGE EXTENSION** `ext/FDiffTrainingExt.jl` (weakdeps
  `Lux`/`Zygote`/`Optimisers` + `[extensions]` in root Project.toml; runtime `[deps]` **still empty**).
  A Lux MLP with a **zero-initialized final layer** (untrained ⇒ exactly the identity correction),
  `build_fdiff_nn`/`neural_vm_hook`/`neural_lambda_hook`, the Zygote-safe scalar loss `fdiff_gpp_loss`,
  and `train_fdiff_rollout!` = the working port of NeuralCrop.jl's broken `train_loop_rollout!`
  (Zygote reverse-mode + `Optimisers.update` + detached soil-water state carried across chunk boundaries
  = the truncation in TBPTT). Reverse-mode by necessity: F_diff `convert(T,·)`s its state, so a
  ForwardDiff dual injected only via the NN params would hit that convert; Zygote/Enzyme keep the forward
  values `Float64`. Params are `Lux.f64` (no mixed-precision matmul fallback).
- **★ GATE `test/testitems/nn_training_tests.jl`** (all with margin): (1) IDENTITY — nothing-hook ==
  committed baseline, zero-init net == pure physics to 1e-10; (2) GRADIENT CORRECTNESS — Zygote gradient
  w.r.t. the NN params vs **FiniteDifferences, rtol 1e-4** (the AD-vs-FD discipline of the physics gate,
  now w.r.t. NN params); (3) RECOVERY — the TBPTT loop drives the loss **0.675 → 1.4e-3 (> 99 %)**,
  trained GPP within **0.5 %** of the target, recovered Vcmax scale **≈ 1.31 vs the known 1.30**.
- **★ PHYSICAL FINDING — which lever, which path (the immediate NEXT is set by this).** Fitting the
  learned Vcmax correction to the LPJmL-FIT C daily GPP on the single-representative path only PARTIALLY
  closes the level gap (annual ratio **0.644 → 0.794**) and DEGRADES the growing-season daily shape (r
  **0.957 → 0.810** — trades shape for level). Physics, not a training failure: that gap is
  **light/structure-limited** (Haxeltine–Prentice co-limitation saturates at `je`), so Vcmax can't close
  it — exactly why the multi-individual canopy (§9) closed GPP by spreading light. **(item 7b-canopy) ✅
  DONE (session 10 cont.):** the hooks are wired into `daily_step_canopy` and trained on the coupled
  canopy path with **Enzyme reverse** (the AD-through-mutation follow-up — PROVEN: Enzyme gradient vs
  FiniteDifferences to **1.2e-8**; recovery loss 0.205→1.1e-3, scale ≈1.18 vs 1.20; gate
  `nn_canopy_training_tests.jl`, §15). **★ NEXT: train the canopy correction against the REAL C-binary
  daily GPP** on the full 25-patch Hainich canopy (not a synthetic recovery target) + add the λ lever + a
  multi-year objective through the structure/allocation feedback.
- **Baselines / gates / deps.** NO committed baseline moved (identity fast path). Root Project.toml gains
  `[weakdeps]`+`[extensions]`+their `[compat]`; `test/Project.toml` gains `Lux`/`Zygote`/`Optimisers`
  (+`Random`/`Printf` stdlibs — the first full run caught `using Random` for `randperm` needed it
  declared). Suite **25,879 pass / 0 fail / 4 broken** (JET/Aqua/gradient green; the hooks add a
  `nothing`-typed default the compiler specializes away). Runic-clean; docs strict-build green. Driver
  `scripts/train_fdiff_nn.jl`; report §14; ADR 0016.

---

## ⭐ WHAT LANDED IN SESSION 9 (on `main`) — SELF-COMPUTED CANOPY NPP CALIBRATED, THE `bm_inc` CRUTCH REMOVED (scale-up step 7a)

**The handoff's immediate NEXT — calibrate the self-computed canopy NPP so the coupled loop runs fully
self-driven — landed.** The step-8 over-respiration (≈ −25 vs the C's ≈ +507 gC/m²/yr) was decomposed
(`Ra = R_leaf + R_maint + R_growth` against the C target) to **two faithful-to-`npp_tree.c` fixes**, both in
`FDiff.autotrophic_respiration` — NOT a constants error (the maintenance constants match the C exactly).
Adversarially re-verified against `npp_tree.c` / `water_stressed.c` / `daily_natural.c`.

- **(1) The growth-respiration `max(0,·)` floor was far too soft — the dominant error (~+730 gC/m²/yr).**
  The C is a hard branch — `npp = (assim<mresp) ? assim−mresp : (assim−mresp)·(1−r_growth)`
  (`npp_tree.c:52`, `assim = gpp−rd`, `npp_bnf=0` with no nitrogen) ⇒ `R_growth = r_growth·max(0, gpp−rd−
  mresp)`, **zero whenever a tissue is carbon-negative**. F_diff smoothed that `max(0,·)` with
  `softplus(·, β=1)`, whose `log(2)/β ≈ 0.69 gC` offset (+ slow sub-zero decay) booked a phantom growth
  respiration into **every carbon-negative individual on every day** (deep-winter days with GPP≈0 charged
  R_growth ≈ 2 gC/m²/day). Fix: a dedicated sharpness `RespParams.βgrowth = 50` (matching the other flux
  floors' `βflux`).
- **(2) The fine-root maintenance was not phen-gated.** The C multiplies the root (+`sapwood_bg`)
  maintenance block by `pft->phen` (`npp_tree.c:51`) — a deciduous canopy stops respiring roots when the
  leaves are off — while the above-ground sapwood term runs year-round. Fix: `R_maint = respcoeff·k·gtemp·
  (C_sap/CN_sap + phen·C_root/CN_root)`. The 3 call sites (`daily_step`/`daily_step_ml`/`daily_step_canopy`)
  pass the day's `phen`. (`gtemp_soil` for the root is proxied by `gtemp_air` — no soil-thermal model yet.)
- **★ RESULT.** Standalone canopy annual NPP **−25 → +663 gC/m²/yr** (C 507); winter leaf-off **−250 → −6.7**
  (C −13); daily NPP **r 0.987**; **CUE = NPP/GPP 0.52 vs the C's 0.46** (a physical temperate-forest value).
  In the kernel-isolation config (C FAPAR+PET, so GPP≈C) F_diff's **total Ra = 592.8 vs the C's 595.6 — a
  0.5 % match** ⇒ the standalone NPP overshoot (×1.31) is INHERITED from the documented +17 % GPP-phenology
  level (§11), NOT a respiration miscalibration. Fixing the respiration *physics* (matching the C kernel),
  not fitting NPP down by inflating respiration to mask the GPP residual.
- **The `bm_inc` crutch is REMOVED.** `rollout_canopy_years` defaults fully self-driven (`bm_inc_ext=nothing`
  → `Σ npp_ind`); `FDiffFastCore` always self-accumulated `fl.npp_ind` (never the crutch). Self-driven
  coupled loop (2009 start + 2010 forcing): self-NPP ≈ 594, year-1 mean tree H **9.41 m** (C 2010: 9.344),
  8-year trajectory H 9.41→10.28 (≈ 0.11 m/yr vs C ≈ 0.13), AGB 4927→6736 — all finite, no blow-up.
- **Baselines / gates.** ONLY `references/fdiff_annual_totals.txt` moved — `npp` 871.81 → **893.28**;
  `gpp/transp/evap/runoff/precip` **byte-identical** (the fix is downstream of GPP and the water balance;
  the water/light canopy baselines are unchanged). New self-NPP gate in `multi_individual_tests.jl`
  (positive; ratio ≤ 1.6; CUE ∈ [0.42,0.56]; daily r > 0.95; winter deficit bounded).
  `dynamic_structure_tests.jl` + `coupling_tests.jl` now run the coupled loop **self-driven** (positive
  annual self-NPP + structure growth). Suite **25,865 pass / 0 fail / 4 broken** (JET/Aqua/gradient green —
  the fixes add no new conditionals, so ForwardDiff/Enzyme still match FD); Runic-clean. Report §13; the
  end-to-end driver `scripts/validate_fdiff_canopy.jl` now also reports NPP (and was fixed — it had gone
  stale on the `nind` ctor arg).
- **Two documented second-order residuals stay on item-7c (pre-existing v1, partially cancel):**
  `sapwood_bg` below-ground maintenance is omitted (biases NPP high), and `rd` is not conductance-gated on
  rare water-stress-collapse days (the C zeroes it when `gpd ≤ 1e-5`, `water_stressed.c:196`; biases NPP
  low). Fixing the `rd` gate *alone* would push CUE further from the C; `sapwood_bg` needs a below-ground
  pool.

---

## ⭐ WHAT LANDED IN SESSION 8 (on `main`) — DYNAMIC (PROGNOSTIC) CANOPY STRUCTURE + S↔F ADAPTER (scale-up step 6)

**The two handoff items — (a) prognostic within-year canopy structure and (b) the `SharedState`/
`AbstractFastCore` adapter — both landed.** Verified line-by-line against `/home/jamirp/lpjml56fit`
(9-agent extraction workflow + adversarial re-derivation of the allocation solve).

- **(a) Prognostic structure.** The per-individual carbon pools are now PROGNOSTIC: they accumulate the
  daily `bm_inc` (= Σ daily NPP, per-m² patch basis — the new `npp_ind` flux from `daily_step_canopy`)
  and GROW at the annual boundary via a faithful DIFFERENTIABLE port of `turnover_tree.c` →
  `allocation_tree.c` → `allometry_tree.c` (`annual_tree.c:29-30`). New `FDiff` API: `AllocParams`,
  `TreePools`, `grow_individual` (turnover [reprod 0.1, sapwood→heartwood 0.04/yr, summergreen leaf/1.05,
  root] + pipe-model allocation + allometry), `_alloc_residual`/`_solve_leaf_inc` (fixed-graph damped
  Newton — segment seed + bracket clamp, the λ-solve AD pattern, NOT the C's bisection),
  `individual_from_pools`/`_patch_fpars` (getfpar layered-light recompute as heights grow),
  `rollout_canopy_years` (multi-year coupled loop, optional `bm_inc_ext` crutch), `tebs_allocparams`.
  **Decisive validation:** the pipe-model invariant `leaf ≈ k_latosa·sapwood/(wooddens·H·sla)` holds
  after allocation to **2.9e-16**; carbon conservation exact; **ForwardDiff `d(height)/d(bm_inc)` &
  `d(sapwood)/d(bm_inc)` match FD**; a coupled multi-year rollout (2009 start + 2010 forcing + the C's
  `bm_inc`) gives **year-1 mean tree height 9.34 m = the C's actual 2010 value** (from 2009's 9.21), and an
  8-year trajectory grows smoothly (AGB 4864→6314, H 9.34→10.02) with no blow-up.
- **(b) The `SharedState` adapter — `FDiffFastCore <: AbstractFastCore`, `step!` no longer throws.**
  Daily `step!(fc, state, bc, forcing) -> FToE` maps `SharedState.w` (fraction) ↔ `SoilColumn` mm,
  self-computes daylength/GSI-phen/albedo-`eeq`, runs `daily_step_canopy`, **writes soil water back into
  `state.w` in place**, accumulates `bm_inc`, returns `FToE` (`LE = λ·ET`; SOM/fire/energy 0 in v1); the
  year-end `annual_step!(fc, state) -> FToS` grows the structure and returns the conserved handoff — the
  flux-then-integrate S↔F coupling of DESIGN §8 (F owns allocation, S owns demography).
- **★ KEY FINDING (the immediate NEXT): F_diff's SELF-computed canopy NPP over-respires** (≈ −25 vs the
  C's ≈ +512 gC/m²/yr). The maintenance constants match the C EXACTLY (`param.k=0.0548`, `nc_ratio=1/cn`,
  `CTON_SAP=330`/`CTON_ROOT=30`; `npp_tree.c:190 assim=gpp−rd`), so it is an **un-gated leaf-respiration
  aggregation** issue over the multi-individual canopy (the C-binary validation never gated NPP). Fixed a
  real per-m² maintenance bug (added `nind` to `Individual`; maintenance is now `nind·pool`,
  `npp_tree.c:51` — invisible to the committed water/light baselines). **Until the self-NPP is
  calibrated, the coupled loop + adapter use a `bm_inc` crutch** (the C's per-individual NPP — the same
  kernel-isolation methodology steps 5–7 used for the FAPAR/PET crutches, then removed). A carbon-deficit
  individual (`bm_inc ≤ 0`) STAGNATES (a guard against the pipe-model height blow-up).
- **[VERIFIED src] The ACTIVE PFT file is `par/pft_lpjmlfit.js`** (via `lpjmlfit.js:133 →
  param_lpjmlfit.js`) — beech uses the ANGIO allometry (`ALLOM{1,2,3}_ANGIO` = 117.44/28.749/0.5633,
  `CA_MAX` 225, `K_LATOSA` 4e3 = the `Allometry.TreeAllometry` defaults) — **NOT `par/pft.js`**
  (standard-LPJmL: ALLOM1=250, crownarea_max=100). This confirms allometry.jl was correct all along.
- Gates: `test/testitems/dynamic_structure_tests.jl` (30) + `coupling_tests.jl` (15), self-contained on
  the committed 2010 reference (heartwood from `agb/nind`, `bm_inc` from `npp_ind/nind`). Data:
  `scripts/extract_fdiff_individuals_multiyear.py` (2008–2011 per-individual pools incl. heartwood) +
  committed `references/hainich_structure_growth.txt`; driver `scripts/validate_fdiff_structure.jl`.
  Suite **25,856 pass / 0 fail / 4 broken** (JET/Aqua/gradient green); Runic-clean. Report
  `docs/phase3_fdiff_cbinary_validation.md` §12.

---

## ⭐ WHAT LANDED IN SESSION 7 (on `main`) — SELF-COMPUTED RADIATION + PHENOLOGY (scale-up step 5)

**Removed the two daily C-binary "crutches" the canopy validation leaned on** (handoff item 5), so
standalone F_diff runs from atmospheric forcing + S-structure alone. Three faithful ports (3-agent
C-source extraction, cross-checked by direct reads):
- **GSI leaf phenology** (`phenology_gsi.c` → `PhenParams`/`PhenState`/`phenology_gsi_step`/
  `tebs_phenparams`): four low-passed logistic limiters (cold `tmin`, heat `tmax`, `light`, water
  `wscal`), `f += (sigmoid(±sl·(x−base)) − f)·τ`, `phen = tmin·tmax·light·wscal`. Beech params
  (`par/pft.js:527-550`). Drivers = daily-mean air temp, swdown, prev-day stand water scalar; the
  `soil→temp[0] < 10 °C ⇒ water factor open` gate uses air temp. `stable_sigmoid` (arg clamp ±30)
  guards the steep-slope `exp` overflow the C handles with its `<200` branch. **Self-`phen` ↔ C
  `d_fapar` r 0.99** (mean 0.479 vs the FAPAR-proxy 0.432 — `fapar/peak` under-reads true `phen`
  because `d_fapar` folds `(1−albedo_leaf)` + the stem term).
- **Dynamic patch albedo → self-computed `eeq`** (`albedo_stand.c`/`albedo_tree.c`/`albedo_grass.c` →
  `patch_albedo`): `beta = Σ fpc·(frs·0.65 + (1−frs)·albveg) + max(1−Σfpc,0)·(sfr·0.65 + (1−sfr)·0.30)`;
  leaf-on beech `beta ≈ 0.22` vs the fixed `0.15`. **Self-`eeq` ↔ C `d_pet` r 0.999, annual ratio 0.98**
  (fixed-0.15 was 1.07 — the 6.8 % overshoot is gone). `frs2` canopy-snow-burial neglected (v1;
  negligible at Hainich). `petpar2.c` `eeq` form already matched exactly.
- **`petpar_daylength(lat, doy)`** (`petpar2.c`; branch-free polar-day/night via `clamp(−u/v, −1, 1)`)
  reproduces the forcing daylength to 5e-5 h.

`Individual` gained `albedo_stem`/`albedo_litter`/`snowcanopyfrac` (3 fields; all 4 ctor sites updated).
`rollout_daily_canopy` **self-computes phen + eeq by default** (`phens`/`eeqs` now optional crutch
overrides for kernel isolation). **Standalone Hainich 2010:** GPP annual ratio 1.09→**1.17**, transp
1.02→**1.08** (the faithful GSI phen integrates ~11 % more leaf-display), daily r **0.993/0.978**,
root-zone GS r 0.98; interception 20.4 vs C 23.1 mm (was 17.4). **ForwardDiff** through the
GSI+albedo+water-feedback path matches FD ~1e-11. Baseline `hainich_canopy_baseline_2010.txt`
regenerated (GPP 1205→1286, transp 243→258, interc 17.4→20.4); single-bucket/multilayer baselines
UNCHANGED. Gate `multi_individual_tests.jl` runs the standalone config + 3 crutch-removal asserts.
Suite **25,811 pass / 0 fail / 4 broken**; Runic-clean. Report `docs/phase3_fdiff_cbinary_validation.md` §11.

---

## ⭐ WHAT LANDED IN SESSION 6 (on `main`) — COUPLED CONDUCTANCE ↔ CARBON (scale-up step 4)

Closed the demand-side transpiration residual session 5c localized (handoff item 4). **The
multi-individual canopy transpiration annual ratio goes 1.32 → 1.02 vs the C binary.** Three pieces:
- **Wet-canopy interception** (`interception.c` port): `Individual` gained `lai`+`intc`; `_wet_interc`
  computes `wet = min(intc·lai·phen·rain/(eeq·1.32), 0.9999)`, which reduces each individual's demand by
  `(1−wet)` (new `wet` kwarg on `canopy_conductance`) and evaporates `eeq·1.32·wet·fpc` off the canopy
  (removed from infiltration; new `interc` flux; **water still closes ~1e-12**). Flux tracks the C at
  **r 0.99** (17.4 vs 23.1 mm/yr; the ~25 % magnitude shortfall = sub-5 m saplings absent from the
  reconstruction). `intc` per PFT: trees 0.02 / boreal 0.06 / grass 0.01.
- **`eeq` albedo (kernel isolation):** F_diff's fixed 0.15 albedo makes PET **6.8 %** high (807 vs C
  755.6). Added an optional `eeq_ext`/`eeqs` drive from the C's own daily PET (`pet_C/1.32`, which
  embeds `albedo_patch`) — the same methodology as the FAPAR drive. Full `albedo_patch`/`petpar` port
  (so standalone F_diff needs no PET crutch) is a documented follow-up.
- **★ LOAD-BEARING BUG FIX — the coarse net-assimilation floor inflated stand conductance ~8×.** The
  `adtmm` conductance driver (`photosynthesis.c:166` `(adt≤0)?0`) was smoothed with a hardcoded
  `softplus(adt, 0.5)` whose floor (`log(2)/0.5 = 1.386 gC`) injected spurious assimilation into every
  LIGHT-STARVED individual; since `gp_i ∝ adtmm` with tiny understory `fpc`, `gp_i/fpc` hit ≈190 and
  `gp_stand = Σgp_i/Σfpc_i` was lifted to **24.5 mm/s** (vs the ~2.9 the C's transp implies) → demand
  ~2× high. It affects ONLY `adtmm` (4th `photosynthesis` return + conductance/λ path), NOT `agd`
  (GPP) — exactly why GPP matched all along while transp ran high. Fix: `PhotoParams.βadt` 0.5→20 →
  `gp_stand`~10.7. **This alone lifts every daily correlation: GPP r 0.95→0.998, transp 0.96→0.988,
  root-zone GS r 0.97→0.98, ratio 0.73→0.84.** GPP annual 1.06→1.09.
- **Baselines regenerated** (intended physics change — βadt touches the single-individual paths too,
  which over-transpired their shoulder seasons): `fdiff_annual_totals`, `hainich_fdiff_baseline` (transp
  383→350), `hainich_ml_baseline` (382→350), `hainich_canopy_baseline` (new §10 config: interception ON
  + C-eeq drive; transp 315→243, +`interc_annual`). Gate `test/testitems/multi_individual_tests.jl`
  tightened (transp ratio 0.9–1.15, interception r>0.9, interc in water closure, ForwardDiff ctor for
  lai/intc). **ForwardDiff** through the interception + per-individual loop matches FD.
- Report `docs/phase3_fdiff_cbinary_validation.md` §10. Full suite **25,807 pass / 0 fail / 4 broken**;
  Runic-clean.

---

## ⭐ WHAT LANDED IN SESSION 5c (on `main`) — MULTI-INDIVIDUAL / MULTI-PFT CANOPY (scale-up step 3)

Replaced the single representative tree with the Hainich cell's **real per-patch set of individuals**
(`FDiff.Individual`, `daily_step_canopy`, `rollout_daily_canopy`): 25 patches × **297 reconstructed
individuals** (trees + grass), each patch a canopy sharing one 23-layer soil column, light distributed
by the FIT **vertical layered Beer–Lambert competition** (`getfpar.c` port — tallest-first, `k_lambert
=0.5`, 2 m layers). Individuals reconstructed from the `ind` output by `scripts/extract_fdiff_individuals.py`
(committed `references/hainich_individuals_2010.csv`); crown/leaf/sapwood via LPJmL-FIT allometry.
- **⭐ RESULT: the GPP LEVEL GAP IS CLOSED — annual ratio 0.57 → 1.06** (full-year daily r 0.95). This
  was the multi-PFT step's primary target. Transpiration improved 1.60 → **1.32** (r 0.96); root-zone
  water GS r 0.97.
- **Three effects close GPP:** (1) the correct **layered** canopy light (Σ≈0.83) — sessions 5/5b drove
  the tree with the *albedo-based* `d_fapar` OUTPUT (≈0.49), a DIFFERENT quantity than the layered
  `pft->fpar` that actually feeds photosynthesis (~1.7× under-fed); (2) de-saturation of the SLA-Vcmax
  cap once light is spread across individuals; (3) a fixed **latent `βvm` bug** — the Vcmax-cap smoothing
  `smoothmin(vm, vm_n, βvm=0.05)` biased ALL Vcmax down by up to ~14, driving light-starved understory
  individuals NEGATIVE. Corrected `βvm 0.05→1.0`; regenerated the cbinary + multilayer drift baselines.
- **Transpiration residual (+32 %) is DEMAND-side** (no interception/wet-canopy, `eeq` ~7 % high from the
  fixed forest albedo, stand conductance→demand) = the documented **coupled-conductance (item 3)** +
  **petpar-albedo (item 4)** items — NOT the multi-PFT structure.
- **Data semantics (verified):** the `ind`-CSV `gpp`==`npp` columns are BOTH `pft->anpp` (= cell **NPP**,
  a genuine FIT bug `daily_natural.c:193 pft->agpp+=npp`); per-individual GROSS GPP is unrecoverable from
  `ind` — the cell `d_gpp` (gross) is the honest target. Reconstruction self-validates: `nind=1/225` for
  every tree ⇒ Jucker crown-area reconstruction matches the C's stored crownarea.
- **AD:** ForwardDiff flows through the per-individual loop (matches FD). Gate
  `test/testitems/multi_individual_tests.jl` + committed `hainich_{individuals,canopy_baseline}_2010`.
  Report `docs/phase3_fdiff_cbinary_validation.md` §9.

---

## WHAT LANDED IN SESSION 5b (on `main`) — MULTI-LAYER SOIL (scale-up step 2)

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
3. ✅ **DONE (session 5c) — Multi-PFT + representative-individual set.** 25 patches × 297 reconstructed
   individuals share one soil column with FIT layered-Beer–Lambert light (`Individual`/`daily_step_canopy`).
   **GPP LEVEL GAP CLOSED (0.57→1.06);** transp improved 1.60→1.32. Localized the transp residual to the
   demand side (items 4 below). Fixed the latent `βvm` Vcmax-cap bug. See §9 + `multi_individual_tests.jl`.
4. ✅ **DONE (session 6) — Coupled conductance↔carbon consistency.** Closed the transp +32% demand-side
   residual: **transp annual ratio 1.32→1.02.** Wet-canopy interception (`interception.c` port, r 0.99),
   `eeq` kernel-isolation drive from the C's daily PET, and a load-bearing **`βadt` net-assimilation-floor
   fix** that removed a ~8× `gp_stand` inflation (and lifted GPP r to 0.998, transp r to 0.988). See §10 +
   `multi_individual_tests.jl`.
5. ✅ **DONE (session 7) — remove the two C-output "crutches".** F_diff now self-computes (a) its `eeq`
   from the **dynamic patch albedo** (`albedo_stand.c`/`albedo_tree.c`/`albedo_grass.c` port → `patch_albedo`;
   self-`eeq` ↔ C `d_pet` r 0.999) + `petpar_daylength(lat,doy)`, and (b) its **GSI leaf phenology**
   (`phenology_gsi.c` port → `phenology_gsi_step`; self-`phen` ↔ C `d_fapar` r 0.99). `albedo_soil.c` is
   dead code in this build (non-FMS → `soil_albedo = c_albsoil` constant). Standalone GPP 1.17 / transp 1.08,
   daily r 0.99/0.98. See §11 + `multi_individual_tests.jl`. Smaller residuals still open: the `gp_stand`
   over-estimate (GS transp +8%) and the interception magnitude (20.4 vs 23.1 mm).
6. ✅ **DONE (session 8) — (a) dynamic (prognostic) canopy structure + (b) the `SharedState` adapter.**
   The per-individual pools are prognostic (`FDiff.grow_individual`/`TreePools`, pipe-model allocation port,
   invariant to 2.9e-16, AD matches FD); `FDiffFastCore <: AbstractFastCore` wires `FDiff` behind `step!`
   (no longer throws) + `annual_step!` = the flux-then-integrate S↔F handoff. See §12 + `dynamic_structure_tests.jl`
   / `coupling_tests.jl`.
7. **(a) ✅ DONE (session 9) — self-computed canopy NPP CALIBRATED; the `bm_inc` crutch REMOVED.** Two
   faithful-to-`npp_tree.c` fixes (`RespParams.βgrowth=50` sharpens the growth-resp floor; fine-root
   maintenance phen-gated) took standalone annual NPP −25 → +663 gC/m²/yr (C 507; CUE 0.52 vs 0.46; daily r
   0.987); kernel-isolation Ra matches the C to 0.5 % ⇒ the residual is the inherited GPP-phenology level.
   The coupled loop runs fully self-driven (no crutch). See §13 + the self-NPP gate in `multi_individual_tests.jl`.
   **(b) ✅ DONE (session 10) — gradient-based online rollout training (machinery).** `FDiff.FluxHooks`
   (dependency-free learned Vcmax/λ corrections) + `ext/FDiffTrainingExt.jl` (Lux MLP + finished TBPTT
   `train_fdiff_rollout!`, Zygote reverse); gate-verified identity + Zygote-vs-FD gradient + recovery of a
   known correction. See §14 + ADR 0016 + `nn_training_tests.jl`.
   **(b-canopy) ✅ DONE (session 10 cont.) — NN training on the coupled canopy path via Enzyme reverse.**
   Per-individual `FluxHooks` in `daily_step_canopy` (identity fast path ⇒ canopy baselines byte-identical)
   + `train_fdiff_canopy_rollout!`/`fdiff_canopy_gpp_loss` (Enzyme reverse — `daily_step_canopy` mutates
   arrays so Zygote can't). **The AD-through-mutation path is proven: Enzyme gradient w.r.t. the NN params
   matches FiniteDifferences to 1.2e-8**; recovery of a known correction (loss 0.205→1.1e-3, scale ≈1.18
   vs 1.20). Gate `nn_canopy_training_tests.jl`; §15; the step-2 follow-up is closed.
   **★ NEXT — train the canopy correction against the REAL C-binary daily GPP** (not a synthetic recovery
   target) on the full 25-patch Hainich canopy; add the λ lever + a multi-year objective through the
   structure/allocation feedback. **(c) Smaller residuals:** per-PFT phenology for the
   evergreen/grass minority (one beech-GSI `phen` patch-wide today); grass structure prognostic
   (`grass_allocation.c`); below-ground root-sapwood (`sapwood_bg`, which — with the rare-day `rd`
   conductance gate — is the small remaining respiration residual, both documented in §13) + carbon-debt in
   the allocation; the full multi-year gradient through the layered-light feedback; whole-tree
   mortality/establishment (S's demography) so the coupled loop is not fixed-N.
8. **λ-solve at scale:** swap the fixed-graph Newton for `SteadyStateAdjoint`/`ImplicitDifferentiation`
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
