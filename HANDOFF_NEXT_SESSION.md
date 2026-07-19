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
  scale ≈1.18 vs 1.20). `Enzyme` is now a 4th extension trigger; runtime `[deps]` still empty. **Julia-version
  caveat (CI-surfaced): the Enzyme-reverse canopy path is verified on Julia 1.10 (lts); Enzyme 0.13 hits an
  internal LLVM compiler error on ≥1.11 for this mutating path** (single-bucket Enzyme gate is fine on 1.11
  — canopy-specific) → the per-individual `FDiffParams{T}` ctor is now positional (Enzyme-transparent) and
  the Enzyme canopy-gate parts are guarded to `VERSION < v"1.11"` (identity runs everywhere); lifting the
  guard is an upstream-Enzyme follow-up. Gate `nn_canopy_training_tests.jl`; report §15; ADR 0016.
- **Phase-3 (session 11) — scale-up step 7b-cell: NN TRAINING vs the REAL C-BINARY DAILY GPP on the FULL
  25-PATCH CELL + the λ LEVER.** The C daily GPP is a CELL-mean over 25 patches, so one shared learned
  correction is trained so the cell-mean GPP matches the C. **Exact per-patch gradient decomposition
  (Gauss–Newton reweighting):** `∂L/∂ps = Σ_p ∂/∂ps[Σ_i c_i·g_{p,i}]`, `c_i = (2/(D·P))(ḡ_i−t_i)` detached,
  so every reverse pass is the PROVEN single-patch Enzyme path (no monolithic multi-patch AD entry point);
  per-patch grads summed by reusing one accumulating `Duplicated` shadow. **Result (kernel-isolation
  C-FAPAR phenology):** GPP annual ratio **1.093 → 1.023 (`:vm`) → 1.010 (`:vm,:λ`)** with the daily
  correlation IMPROVING (GS r 0.997 → 0.999) — the OPPOSITE of the light-limited single-rep path (§14).
  `fdiff_cell_gpp_loss`/`train_fdiff_cell_rollout!`; driver `scripts/train_fdiff_canopy_cell.jl`; gate cell
  testitem (identity Δ=0; cell grad vs FD 6.1e-10; recovery 0.330→0.011, GPP within 0.04 %); report §16.
  **Multi-year through the structure feedback = the documented frontier:** Enzyme reverse through
  `rollout_canopy_years` (`_patch_fpars` + `grow_individual` allocation Newton) raises `EnzymeNoTypeError`
  on 1.10 (type-analysis blocker, NOT a differentiability one — §12's ForwardDiff structure gradients match
  FD). Runtime `[deps]` still EMPTY.
- **Phase-3 (session 12) — scale-up step 7b-multiyear: NN TRAINING THROUGH THE MULTI-YEAR
  STRUCTURE/ALLOCATION FEEDBACK.** §16's documented frontier is reached: the multi-year path (GPP trained
  to match the C while the canopy grows between years via the allocation) is now **Enzyme-differentiable,
  verified vs FiniteDifferences** (~1e-11 scalar hook / 8.2e-10 network-param gradient). Session 11's
  `EnzymeNoTypeError` was NOT the guessed `BitVector`/`_solve_leaf_inc` temporary (both differentiate
  cleanly in isolation) — it is a **struct-in-memory** failure: a `Vector{TreePools}` field-scatter copies
  the struct's trailing `is_grass::Bool`+padding as `Anything`. Fixed with a **struct-of-arrays** refactor:
  `_patch_fpars` split into an Enzyme-typeable SoA core `_patch_fpars_soa` (+ a byte-identical
  `Vector{TreePools}` wrapper, max|Δ|=0.0) + a new dependency-free `rollout_canopy_years_gpp` (multi-year
  coupled rollout in SoA form, returns per-year stand GPP). Extension pair `fdiff_multiyear_gpp_loss`/
  `train_fdiff_multiyear_rollout!`; gate multi-year testitem (identity Δ=0; recovery 99.3 %); runtime
  `[deps]` still EMPTY. The machinery is the deliverable; a real multi-year C fit needs a multi-year
  reference (next step). Report §17; ADR 0016 addendum.
- **Phase-3 (session 13) — scale-up step 7b-cell-multiyear: NN TRAINING ON THE CELL × MULTI-YEAR OBJECTIVE
  AGAINST A REAL MULTI-YEAR REFERENCE.** §17's two flagged next steps both land. Composes §16 (cell) with §17
  (multi-year): the learned Vcmax/λ correction is trained so the **cell-mean PER-YEAR annual GPP** matches
  the C binary's OWN per-year annual GPP over the full 25-patch Hainich cell, **every patch grown across
  years** via the allocation. The cell MSE over years factors EXACTLY patch-by-patch (Gauss–Newton
  reweighting, `c_y = (2/(NY·P))(Ḡ_y−T_y)` detached), so every reverse pass is the PROVEN single-patch
  multi-year `rollout_canopy_years_gpp` Enzyme path (no monolithic multi-patch AD; per-patch grads summed
  by reusing one accumulating `Duplicated` shadow). **Real committed reference** (no C re-run —
  `scripts/extract_fdiff_cell_multiyear.py` slices data already on disk): 2008 start-year 25-patch structure
  + per-year 2009–2011 forcing + per-year daily C GPP/FAPAR. `fdiff_cell_multiyear_gpp_loss`/
  `train_fdiff_cell_multiyear_rollout!`; driver `scripts/train_fdiff_cell_multiyear.jl`; gate cell ×
  multi-year testitem (identity per-year Δ=0; cell-multi-year grad vs FD 1.5e-10; recovery 98.8 %, GPP
  within 0.07 %). **Result: mean cell-mean annual-GPP ratio 1.034 → 0.998 (`:vm`) → 0.996 (`:vm,:λ`) over sim years 2009/2010/2011 (per-year model/C ratio 1.026/1.014/1.063 → 0.992/0.981/1.022 with `:vm`); ONE shared correction fit to all years trims the year-to-year spread (2011 the high-GPP outlier, 1.063→1.02) rather than zeroing each year independently — the §16 within-year cell level result carried consistently across years through F_diff's own allocation.** Runtime `[deps]` still EMPTY. Report §18;
  ADR 0016 addendum.
- **Phase-3 (session 14) — scale-up step 8: PER-PFT GSI LEAF PHENOLOGY + the beech-tmin correction.** The
  first-listed frontier item lands. §11's self-computed leaf phenology used ONE beech GSI patch-wide; the FIT
  config runs `phenology_gsi` per PFT (`"new_phenology":true`+`"individual":true`; the "evergreen"-named PFTs
  run the full four-limiter GSI, not static `phen≡1`). Generalized to per-PFT via `pft_phenparams(id)` (the
  twelve GSI numbers for the 10 natural PFTs verbatim from the ACTIVE `par/pft_lpjmlfit.js`; `wscal_base =
  minwscal_median·100`, the individual-mode inflection) + `per_pft_phenology` + a scalar-OR-vector `phen` in
  `daily_step_canopy`/`patch_albedo` (compile-time `_phen_at`; **scalar path byte-identical ⇒ every baseline
  + the Enzyme trainer untouched**) + a `pft_ids` kwarg on `rollout_daily_canopy` (co-solved per-PFT phen +
  lag-1 grass forest-floor light). **Found + fixed a real fidelity bug:** beech `tmin` was sourced from the
  STANDARD `par/pft.js` (2/8) not the active file (4/8.5) — correcting it tightens the standalone canopy GPP
  ratio 1.17→1.13. **Result (25-patch Hainich): per-PFT phenology moves the cell GPP annual ratio vs the C
  1.134→1.097 (closer) with daily r improving 0.988→0.993** (minority-driven: evergreens hold winter leaves,
  grass understory shaded). Only `hainich_canopy_baseline_2010.txt` moved; the Enzyme training path keeps its
  scalar C-FAPAR phen. Gate `per_pft_phenology_tests.jl`; suite **26,106 pass / 0 fail / 4 broken**;
  adversarially verified (0 blockers). Report §19; CHANGELOG. Runtime `[deps]` still EMPTY.

---

## ⭐ WHAT LANDED IN SESSION 14 (on `main`) — PER-PFT GSI LEAF PHENOLOGY + THE BEECH-TMIN CORRECTION (scale-up step 8)

**The handoff's first-listed NEXT landed:** the self-computed leaf phenology (§11) is generalized from one
beech GSI applied patch-wide to per-PFT — each individual now advances its own PFT's four-limiter GSI — plus
a beech-`tmin` parameter-sourcing correction found along the way. (Report §19; CHANGELOG.)

- **★ THE GENERALIZATION.** `pft_phenparams(id, T)` returns the twelve GSI params (`tmin/tmax/light`·slope·
  base·tau + `wscal`) for each 0-based natural PFT id 0–9, **verbatim from the ACTIVE `par/pft_lpjmlfit.js`**
  (adversarially verified — all 120 numbers match). The individual-mode subtlety: `wscal_base =
  minwscal_median·100` (`phenology_gsi.c:64-66` under `config->individual`, NOT the inert par-file
  `wscal.base`). `per_pft_phenology(pft_ids, forcings; …)` advances one `PhenState` per distinct PFT →
  per-day × per-individual leaf display; grasses (id ≥ 7) drive the light limiter with forest-floor light.
- **★ THE BEECH-TMIN CORRECTION (a real fidelity fix).** The committed beech GSI `tmin` was `slope 2 / base
  8` — the STANDARD `par/pft.js` — but the FIT run uses `par/pft_lpjmlfit.js` (`slope 4 / base 8.5`; tmax/
  light/wscal already matched). Correcting it makes the self-phenology consistent with the C binary it
  validates against: standalone 25-patch canopy GPP annual ratio **1.17 → 1.13**, transp **1.08 → 1.05**,
  daily r ≈ 0.99 unchanged. **`par/pft_lpjmlfit.js` is the ACTIVE file for ALL FIT params (session 8
  established this for allometry — it also holds for phenology).**
- **★ AD-SAFE BY CONSTRUCTION.** `daily_step_canopy`/`patch_albedo` accept `phen` as a scalar OR a
  per-individual vector via a compile-time-dispatched `_phen_at`; the scalar specialization constant-folds to
  the plain value, so the scalar path is **byte-identical** (gate: Δ = 0 vs a uniform vector across every
  flux + state). The Enzyme multi-year training path (`rollout_canopy_years_gpp`, `ext/FDiffTrainingExt.jl`)
  keeps passing a scalar C-FAPAR phen per day — structurally untouched (verified). Per-individual phen is a
  Const forcing-derived input on the STANDALONE self-driven path only.
- **★ RESULT (25-patch Hainich 2010, standalone).** Per-PFT phenology moves the cell GPP annual ratio vs the
  C **1.134 → 1.097** (closer) while the daily r improves **0.988 → 0.993** — driven entirely by the minority
  the beech-patch-wide phen got wrong: evergreens now hold winter display (annual-mean phen 0.77/0.89/0.96
  TeNE/TeBE/BoNE vs 0.46 summergreen), the grass understory is light-shaded. Beech self-phen still tracks the
  C FAPAR at r ≈ 0.99. Composition: beech 259, grass 25, evergreen+boreal-summergreen minority 13.
- **★ GATE `per_pft_phenology_tests.jl`** (4 self-contained testitems): param fidelity vs
  `par/pft_lpjmlfit.js` (all ids 0–9); distinct/bounded/physically-ordered trajectories; scalar-vs-vector
  byte-identity (Δ = 0, self-eeq AND kernel-isolation `eeq_ext`); per-PFT self-driven rollout closes water +
  reduces to the beech default on an all-beech patch (rtol 1e-12). Suite **26,106 pass / 0 fail / 4 broken**
  (new gate + Enzyme canopy gates + JET/type-stability green). Only `hainich_canopy_baseline_2010.txt` moved.
- **★ ADVERSARIALLY VERIFIED (4-reviewer workflow, 0 blockers):** all 120 params match the active file (with
  strong `wscal_base=minwscal·100` discriminators); the algorithm is faithful (`soil<10` gate, grass
  forest-floor light); AD-safety confirmed (scalar path byte-identical, Enzyme kernel + `FDiffTrainingExt`
  unmodified); the baseline move is honest (only the self-phen baseline moved, bands intact).
- **★ WHAT THIS IS / IS NOT.** A faithful per-PFT generalization + a beech-tmin sourcing correction —
  essential for running F_diff on non-beech vegetation (the single beech GSI would be badly wrong on
  grasslands/evergreen forests). Documented v1 simplifications: per-individual `minwscal` corridor → PFT
  median; grass forest-floor light is a lag-1 attenuation; the `aphen` COLDEST_DAY reset is omitted (as §11).
  Runtime `[deps]` stays EMPTY.

---

## ⭐ WHAT LANDED IN SESSION 13 (on `main`) — NN TRAINING ON THE CELL × MULTI-YEAR OBJECTIVE AGAINST A REAL MULTI-YEAR REFERENCE (scale-up step 7b-cell-multiyear)

**The handoff's IMMEDIATE NEXT landed:** the cell-multi-year objective — §16's exact per-patch Gauss–Newton
decomposition, each patch now grown across years — trained against a REAL multi-year C annual-GPP reference.
It composes the two proven decompositions (§16 cell + §17 multi-year). (ADR 0016 addendum; report §18.)

- **★ THE COMPOSITION — §16's CELL decomposition THROUGH §17's MULTI-YEAR rollout.** The objective is the
  cell-mean per-year annual GPP `Ḡ_y = (1/P)·Σ_p G_{p,y}` (mean over patches of each patch's year-`y` stand
  GPP from `rollout_canopy_years_gpp`) vs the C's per-year annual `T_y`. The cell MSE over years
  `L = (1/NY)·Σ_y (Ḡ_y − T_y)²` factors EXACTLY patch-by-patch: `∂L/∂ps = Σ_p ∂/∂ps [Σ_y c_y·G_{p,y}]`,
  `c_y = (2/(NY·P))·(Ḡ_y − T_y)` detached (`Σ_p ∂G_{p,y}/∂ps = P·∂Ḡ_y/∂ps` makes it exact). So every reverse
  pass is the PROVEN single-patch multi-year `rollout_canopy_years_gpp` Enzyme path (§17) — **NO new
  monolithic multi-patch AD entry point** — and the per-patch gradients are summed by reusing one
  accumulating `Duplicated` shadow (fresh per gradient call). One Enzyme reverse per patch over the FULL
  multi-year rollout per epoch (no per-chunk TBPTT — the annual structure feedback stays inside the
  differentiated unit, as §17). `fdiff_cell_multiyear_gpp_loss` / `train_fdiff_cell_multiyear_rollout!` in
  `ext/FDiffTrainingExt.jl` (+ parent stubs/exports); runtime `[deps]` still EMPTY.
- **★ A REAL, COMMITTED MULTI-YEAR REFERENCE (no C re-run).** The prerequisite §17 flagged — real multi-year
  forcing + per-year C annual-GPP targets — is produced by slicing data already on disk: the single-cell C
  re-run (session 5) already wrote 2000–2019 daily forcing + daily C GPP/FAPAR, and the multi-year structure
  reconstruction (session 8) already wrote per-year per-patch individuals. New
  `scripts/extract_fdiff_cell_multiyear.py` commits a CI-runnable slice: `hainich_individuals_2008.csv`
  (start-year 25-patch structure), `hainich_multiyear_forcing.csv` (per-year daily forcing 2009/2010/2011),
  `hainich_multiyear_targets.csv` (those years' daily C GPP + FAPAR). C per-year annual GPP (cell-mean)
  [1177.4, 1102.5, 1233.1] gC/m²/yr. Start-of-year convention (dynamic-structure validation §12): the
  rollout starts from 2008's reconstructed structure and simulates the subsequent years, so the structure
  entering each sim year is F_diff's own grown structure; kernel isolation drives each year's leaf display
  by that year's C FAPAR (`phens = fapar_C/peak`).
- **★ RESULT (full 25-patch Hainich, real 2008→2011 reference).** mean cell-mean annual-GPP ratio 1.034 → 0.998 (`:vm`) → 0.996 (`:vm,:λ`) over sim years 2009/2010/2011 (per-year model/C ratio 1.026/1.014/1.063 → 0.992/0.981/1.022 with `:vm`); ONE shared correction fit to all years trims the year-to-year spread (2011 the high-GPP outlier, 1.063→1.02) rather than zeroing each year independently — the §16 within-year cell level result carried consistently across years through F_diff's own allocation.
- **★ GATE `nn_canopy_training_tests.jl` — new cell × multi-year testitem** (3 ragged patches × NY=2,
  self-contained; Enzyme parts guarded `VERSION < v"1.11"`): (1) IDENTITY — zero-init net (both vm+λ) ==
  pure-physics cell multi-year rollout, per-year Δ=0; (2) CELL-MULTIYEAR GRADIENT — the per-patch-decomposed
  cell-multi-year MSE gradient vs FiniteDifferences on the FULL multi-patch multi-year loss, **max rel err
  1.5e-10** (both levers); decomposed primal == direct cell MSE; (3) RECOVERY — the cell-multi-year loop
  drives the loss down **98.8 %** in 25 epochs, trained cell GPP within **0.07 %** of a known vm=1.15/λ=1.05
  target. The gate reaches the extension internal `_enzyme_cell_multiyear_grad` via `Base.get_extension`.
- **★ WHAT THIS MILESTONE IS / IS NOT.** The first HONEST cell fit *through* the structure feedback: the
  §16 cell-mean objective (the quantity the C reports) trained against the C's real per-year annual GPP
  trajectory (§17's demo target replaced by a committed real reference), every patch grown by its own
  allocation across years. NOT a multi-decade fit (3-year span, bounded by the committed 2008–2011
  reconstruction) or a demography-coupled run (fixed-N canopy; whole-tree mortality/establishment is S's
  job). **Cost:** baseline forward over all 25 patches ~5 s; first cell-multi-year gradient ~413 s (one-time
  Enzyme compile); ~34 s/epoch post-compile (25 per-patch reverses); driver ≈ 35 min. Runtime `[deps]` EMPTY.

---

## ⭐ WHAT LANDED IN SESSION 12 (on `main`) — NN TRAINING THROUGH THE MULTI-YEAR STRUCTURE/ALLOCATION FEEDBACK (scale-up step 7b-multiyear)

**§16's documented frontier is reached:** the multi-year structure-feedback path — GPP trained to match
the C WITH the canopy structure growing between years via the allocation — is now Enzyme-differentiable,
verified against finite differences. The `EnzymeNoTypeError` that blocked session 11 is root-caused and
fixed by a struct-of-arrays refactor. (ADR 0016 addendum; report §17.)

- **★ THE MULTI-YEAR PATH IS ENZYME-DIFFERENTIABLE.** Enzyme reverse through the full composed chain — SoA
  structure → `_patch_fpars_soa` layered light → build `Individual`s → `daily_step_canopy` daily fold →
  `grow_individual` → next year — matches FiniteDifferences to **~1e-11 (scalar `vm_scale` hook)** /
  **8.2e-10 (network-parameter gradient)** (ForwardDiff through a physics input agrees to ~1e-13). The
  structure/allocation feedback is now trainable by reverse-mode Enzyme, not just differentiable (§12,
  ForwardDiff).
- **★ ROOT CAUSE — session 11's hypothesis was WRONG (bisected).** §16 guessed an untyped temporary (the
  `BitVector` leaf-layer mask in `_patch_fpars` and/or the `_solve_leaf_inc` primal scan). Both
  differentiate cleanly IN ISOLATION (Enzyme=FD to **1e-9** on `_patch_fpars`'s leaf_c derivative;
  `grow_individual` alone fine). The REAL cause is a **struct-in-memory type failure**: Enzyme cannot type
  a reverse pass that stores `grow_individual`'s BRANCHY struct output into a `Vector{TreePools}` and
  field-scatters it (`trees[i].height → scratch[i]`) — the `TreePools` trailing `is_grass::Bool` + 7 bytes
  padding read as `Anything` in the copied 80-byte `memcpy` ⇒ `EnzymeNoTypeError`. Evidence: a branch-free
  growth through the IDENTICAL scatter differentiates fine; `maxtypeoffset!`/`maxtypedepth!` did NOT help
  (not a size limit); `looseTypeAnalysis!(true)` cleared it but returned a WRONG gradient (a genuine
  untyped value). 2nd instance: a `Union{Nothing,Vector}` `phens` phi carried into the daily loop is an
  untypeable `{Pointer,Float64}`.
- **★ THE FIX — struct-of-arrays (SoA).** Keep the differentiated multi-year state as plain
  `Vector{Float64}` field arrays (`heights`/`leaf_c`/`sapwood_c`/`heartwood_c`/`root_c`/`crownarea` + the
  per-tree Const `sla`/`nind`/`wooddens`/`is_grass`), NEVER a `Vector{TreePools}` in the differentiated
  region. (a) `_patch_fpars` refactored into an Enzyme-typeable SoA core `_patch_fpars_soa(…)` + a thin
  `Vector{TreePools}` unpacking wrapper (diagnostic/non-AD) — **byte-identical, max|Δ|=0.0** (every
  §9/§12/§16 canopy baseline unmoved); (b) new dependency-free `rollout_canopy_years_gpp` runs the
  multi-year coupled rollout in SoA form (same physics as `rollout_canopy_years` §12) and returns per-year
  annual stand GPP. Soil carried across years as its FIELDS (`wcol`::Vector, `snow`::scalar), not the
  `FDiffStateML` struct; `phens` materialized to a concrete `Vector{Vector{T}}` up front.
  `rollout_canopy_years_gpp` exported.
- **★ GATE `nn_canopy_training_tests.jl` — new multi-year testitem** (self-contained, 3 trees × 40-day
  forcing × NY=3; Enzyme parts guarded `VERSION < v"1.11"`): (1) IDENTITY — zero-init net == pure-physics
  multi-year rollout, Δ=0; `_patch_fpars_soa` vs the wrapper byte-identical (max|Δ|=0.0); (2) MULTI-YEAR
  GRADIENT — Enzyme vs FiniteDifferences through SoA structure → daily rollout → grow → next year, **max
  rel err 8.2e-10**; Enzyme primal == direct loss; (3) RECOVERY — `train_fdiff_multiyear_rollout!` drives
  the loss **16.2 → 0.12 (99.3 %)** in 25 epochs, trained GPP within **0.28 %** of a known vm=1.15/λ=1.05
  target. New extension pair `fdiff_multiyear_gpp_loss` / `train_fdiff_multiyear_rollout!` (one Enzyme grad
  of the FULL multi-year loss per epoch, no per-chunk TBPTT); runtime `[deps]` still EMPTY. Suite **25,927
  pass / 0 fail / 4 broken** on 1.10; Runic-clean.
- **★ WHAT THIS MILESTONE IS / IS NOT.** The landed deliverable is the *machinery*: the multi-year
  structure feedback is Enzyme-typeable + gate-verified (identity, Enzyme-vs-FD, 99.3 % recovery of a known
  correction THROUGH the between-year allocation). A *real* multi-year C-binary GPP fit is NOT yet done — it
  needs real multi-year forcing + per-year C annual GPP targets (neither committed); the driver
  `scripts/train_fdiff_multiyear.jl` runs the full end-to-end pipeline on the reconstructed Hainich patch
  but against a DEMO target (2010 annual GPP repeated, TODOs flagged). **Entry point is single-patch
  multi-year; the cell-multi-year objective against a real multi-year reference is the next extension.**

---

## ⭐ WHAT LANDED IN SESSION 11 (on `main`) — NN TRAINING vs the REAL C-BINARY DAILY GPP ON THE FULL 25-PATCH CELL + the λ LEVER (scale-up step 7b-cell)

**The handoff's IMMEDIATE NEXT landed:** the learned canopy correction is trained against the LPJmL-FIT
C binary's OWN daily GPP (not a synthetic recovery target) on the full 25-patch Hainich cell, with the λ
lever on. (ADR 0016; report §16.)

- **The objective is a CELL quantity + an EXACT per-patch gradient decomposition.** The C daily GPP is
  the cell-mean over patches, so ONE shared learned correction (one MLP, feature-driven per individual) is
  trained so the cell-mean GPP `ḡ_i = (1/P)·Σ_p g_{p,i}` matches the C. The cell MSE is a sum of squares,
  so its gradient factors into ONE reverse pass PER PATCH with **detached Gauss–Newton residual weights**
  `c_i = (2/(D·P))(ḡ_i−t_i)`: `∂L/∂ps = Σ_p ∂/∂ps[Σ_i c_i·g_{p,i}]` — EXACT (`Σ_p ∂g_{p,i}/∂ps =
  P·∂ḡ_i/∂ps`). So every reverse pass is the **PROVEN single-patch `daily_step_canopy` Enzyme path** (§15)
  and there is **NO new monolithic multi-patch Enzyme entry point**; per-patch grads are summed by reusing
  one accumulating `Duplicated` shadow (Enzyme adds `∂/∂ps` into the shadow — verified 0.0 vs summing
  separate grads). `fdiff_cell_gpp_loss`/`train_fdiff_cell_rollout!` (extension) + parent stubs/exports;
  runtime `[deps]` still EMPTY.
- **★ RESULT (full 25-patch Hainich, kernel-isolation C-FAPAR phenology, window DOY 105–285).** The
  learned Vcmax lever CLOSES the GPP level against the real C daily GPP — annual ratio **1.093 → 1.023**
  (`:vm`), **→ 1.010** (`:vm,:λ`) — while the daily correlation IMPROVES (full-year 0.9978 → 0.9983;
  growing-season 0.9973 → 0.9990). This is the **OPPOSITE of the single-rep path** (§14, r 0.96 → 0.81
  degraded): the CANOPY residual is Vcmax-shaped (light spread across individuals ⇒ Vcmax-limited), so a
  modest effective-Vcmax reduction (mean GS scale ≈ 0.80 `:vm`, ≈ 0.72 with the λ head sharing) removes the
  inherited over-estimate without touching the seasonal shape. Safe residual (identity-at-init, bounded
  `1 + 0.6·tanh`). Driver `scripts/train_fdiff_canopy_cell.jl`.
- **★ GATE `nn_canopy_training_tests.jl` — new cell testitem** (3 ragged patches, self-contained; Enzyme
  parts guarded `VERSION < v"1.11"`): (1) IDENTITY — zero-init net (both vm+λ) == pure-physics cell rollout,
  Δ=0; (2) CELL GRADIENT — the per-patch-decomposed cell-MSE gradient vs FiniteDifferences on the FULL
  multi-patch cell loss, **max rel err 6.1e-10**; (3) RECOVERY — cell TBPTT loop loss **0.330 → 0.011
  (>96 %)**, trained cell GPP within **0.04 %** of a known vm=1.15/λ=1.05 target. The gate reaches the
  extension internal `_enzyme_cell_grad` via `Base.get_extension`.
- **★ MULTI-YEAR THROUGH THE STRUCTURE/ALLOCATION FEEDBACK — probed, the DOCUMENTED FRONTIER.** Enzyme
  reverse through a lean 2-year GPP loss (fold `daily_step_canopy` per year + `grow_individual` between
  years) raises **`EnzymeNoTypeError`** on Julia 1.10 — Enzyme cannot statically type the reverse pass
  through `rollout_canopy_years`'s composed structure path (`_patch_fpars` layered-light recompute +
  `grow_individual`'s allocation Newton; likely the `BitVector` leaf-layer mask in `_patch_fpars` + the
  `_solve_leaf_inc` primal scan). This is a TYPE-ANALYSIS blocker, NOT a differentiability one — **§12
  already verifies the structure/allocation feedback with ForwardDiff** (`d(grown height)/d(bm_inc)`,
  `d(grown height)/d(α_c3)` match FD). Making `_patch_fpars`/`_solve_leaf_inc` Enzyme-typeable (typed
  temporaries, or an `Enzyme.API.maxtypeoffset!` bump) is the next step.
- **Housekeeping:** `test/Manifest.toml` (a local `Pkg.develop(path=".")` artifact from the
  `--project=test` driver workflow) is now `.gitignore`d — a bare `Pkg.test()` fails with "can not merge
  projects" while it exists (delete it before running `Pkg.test()`). Runic-clean; runtime `[deps]` EMPTY.

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
   **(b-cell) ✅ DONE (session 11) — NN training vs the REAL C-binary daily GPP on the full 25-patch cell +
   the λ lever.** One shared correction trained so the CELL-mean GPP matches the C, via an EXACT per-patch
   Gauss–Newton gradient decomposition (every reverse pass = the proven single-patch Enzyme path; no
   monolithic multi-patch AD). **GPP annual ratio 1.093 → 1.023 (`:vm`) → 1.010 (`:vm,:λ`)** while daily r
   IMPROVES (GS 0.997 → 0.999) — the canopy residual is Vcmax-shaped (opposite of the light-limited single-
   rep path §14). `fdiff_cell_gpp_loss`/`train_fdiff_cell_rollout!`; driver `scripts/train_fdiff_canopy_cell.jl`;
   gate cell testitem (identity Δ=0; cell grad vs FD 6.1e-10; recovery 0.330→0.011, GPP within 0.04 %); §16.
   **(b-multiyear) ✅ DONE (session 12) — NN training THROUGH the multi-year structure/allocation
   feedback.** Session 11's blocker was root-caused (NOT the guessed `BitVector`/`_solve_leaf_inc` temporary
   — both differentiate in isolation; the real cause is a `Vector{TreePools}` field-scatter whose struct
   memcpy copies the trailing `is_grass::Bool`+padding as `Anything` ⇒ `EnzymeNoTypeError`) and fixed with a
   **struct-of-arrays** refactor: `_patch_fpars` → an Enzyme-typeable `_patch_fpars_soa` core (+ a
   byte-identical `Vector{TreePools}` wrapper, max|Δ|=0.0) + a new `rollout_canopy_years_gpp` (multi-year
   coupled rollout in SoA form, per-year stand GPP). **Enzyme reverse through the full SoA structure → daily
   rollout → grow → next-year chain matches FiniteDifferences to ~1e-11 (scalar hook) / 8.2e-10 (network-
   param gradient).** `fdiff_multiyear_gpp_loss`/`train_fdiff_multiyear_rollout!`; driver
   `scripts/train_fdiff_multiyear.jl`; gate multi-year testitem (identity Δ=0; recovery loss 16.2→0.12,
   99.3 %, GPP within 0.28 % of a known vm=1.15/λ=1.05 target); §17; ADR 0016 addendum. Single-patch entry
   point; the *machinery* is the deliverable (a real multi-year C fit needs a multi-year reference — below).
   **(b-cell-multiyear) ✅ DONE (session 13) — NN training on the CELL × MULTI-YEAR objective against a REAL
   multi-year reference.** Composes §16 (cell) with §17 (multi-year): the learned Vcmax/λ correction is
   trained so the cell-mean PER-YEAR annual GPP matches the C's own per-year annual GPP over the full
   25-patch cell, each patch grown across years. The cell MSE over years factors EXACTLY patch-by-patch
   (Gauss–Newton, `c_y = (2/(NY·P))(Ḡ_y−T_y)` detached), so every reverse pass is the proven single-patch
   multi-year `rollout_canopy_years_gpp` Enzyme path (no monolithic multi-patch AD). Real committed reference
   from `scripts/extract_fdiff_cell_multiyear.py` (2008 start structure + 2009–2011 forcing/targets, sliced
   from data already on disk — no C re-run). `fdiff_cell_multiyear_gpp_loss`/`train_fdiff_cell_multiyear_rollout!`;
   driver `scripts/train_fdiff_cell_multiyear.jl`; gate cell × multi-year testitem (identity per-year Δ=0;
   cell-multi-year grad vs FD 1.5e-10; recovery 98.8 %, GPP within 0.07 %); §18. Result:
   mean cell-mean annual-GPP ratio 1.034 → 0.998 (`:vm`) → 0.996 (`:vm,:λ`) over sim years 2009/2010/2011 (per-year model/C ratio 1.026/1.014/1.063 → 0.992/0.981/1.022 with `:vm`); ONE shared correction fit to all years trims the year-to-year spread (2011 the high-GPP outlier, 1.063→1.02) rather than zeroing each year independently — the §16 within-year cell level result carried consistently across years through F_diff's own allocation.
   **(per-PFT-phenology) ✅ DONE (session 14) — per-PFT GSI leaf phenology + the beech-tmin correction
   (scale-up step 8).** Generalized the self-computed leaf phenology (§11) from one beech GSI patch-wide to
   per-PFT: `pft_phenparams(id)` (the 12 GSI numbers for the 10 natural PFTs verbatim from the ACTIVE
   `par/pft_lpjmlfit.js`, `wscal_base = minwscal_median·100`) + `per_pft_phenology` + a scalar-OR-vector
   `phen` in `daily_step_canopy`/`patch_albedo` (compile-time `_phen_at`, **scalar path byte-identical**) +
   a `pft_ids` kwarg on `rollout_daily_canopy` (co-solved per-PFT phen + lag-1 grass forest-floor light).
   Fixed a real bug (beech `tmin` sourced from the standard `par/pft.js`, corrected to the active file's
   4/8.5). **Result: cell GPP ratio vs C 1.134→1.097, daily r 0.988→0.993.** The Enzyme training path keeps
   its scalar C-FAPAR phen (untouched). Gate `per_pft_phenology_tests.jl`; only `hainich_canopy_baseline_2010.txt`
   moved; suite 26,106 pass / 0 fail / 4 broken; adversarially verified (0 blockers). §19; CHANGELOG.
   **★ NEXT:** **grass structure prognostic** (`grass_allocation.c`); below-ground root-sapwood (`sapwood_bg`)
   + carbon-debt in the allocation (**scouted: `sapwood_bg` is a GENUINE SEPARATE carbon pool, `tree.h:50`,
   NOT a fraction of the sapwood pool — a faithful port needs its own establishment/allocation/turnover state
   through the SoA multi-year rollout, higher AD risk**); whole-tree mortality/establishment (S's demography,
   so the coupled loop is not fixed-N); the **upstream-Enzyme-on-Julia-≥1.11 guard-lift** (the `VERSION <
   v"1.11"` guard on the Enzyme gates, §15); and — for a longer trajectory — extend the committed
   reconstruction span beyond 2008–2011. Phenology-fidelity follow-ups: the per-individual `minwscal`
   corridor sampling (now → PFT median) and a canopy-consistent (non-lag) grass forest-floor light.
   **(c) Smaller residuals:** grass structure prognostic (`grass_allocation.c`); below-ground root-sapwood
   (`sapwood_bg`, which — with the rare-day `rd` conductance gate — is the small remaining respiration
   residual, both documented in §13) + carbon-debt in the allocation; whole-tree mortality/establishment
   (S's demography) so the coupled loop is not fixed-N.
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
`2d3d92a` feat(fdiff) NN training on the CELL × MULTI-YEAR objective vs the REAL C per-year annual GPP —
§16 per-patch decomposition THROUGH §17 multi-year rollout + `sbatch_train.sh` (step 7b-cell-multiyear;
CI green — `test (lts)`/`test (1)` pass, `test (pre)` is the allowed pre-release ReTestItems break) ·
`4956529` feat(fdiff) NN training THROUGH the multi-year structure/allocation feedback — SoA fix for the
Enzyme-typeable `rollout_canopy_years_gpp` (step 7b-multiyear) · `433ccb9` feat(fdiff) NN training vs the
REAL C-binary daily GPP on the full 25-patch cell + the λ lever
(step 7b-cell) · `e9b8212` fix(fdiff) make the Enzyme canopy path Julia-1.11-safe (CI test(1) fix-forward)
· `c68c5ea` feat(fdiff) NN training on the canopy path — Enzyme reverse (step 7b-canopy) · `3db1406`
feat(fdiff) gradient-based online rollout training — NN λ/Vcmax hooks + TBPTT (step 7b) · `7a76f45`
feat(fdiff) self-computed canopy NPP calibrated, bm_inc crutch removed (step 7a) · … ·
`8dcf55b` feat(fdiff) F_diff spike (#14 squash) · `bcb3ecb` feat(phase2) gate met · `da12c88`
feat(phase1) global daily dataset · `b3924c9` feat(phase1) water closure · `5bc93ef` docs(ADR 0013).
