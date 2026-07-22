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
- **Phase-3 (session 15) — scale-up step 9: PROGNOSTIC GRASS structure — the `allocation_grass.c` port.**
  The multi-year rollout grew only trees; grasses were held fixed AND structurally dropped (the `ind`-output
  reconstruction gives grass rows `leaf_c=crownarea=nind=0`, so a round-trip through `individual_from_pools`/
  `_patch_fpars_soa` zeroed grass). Grass leaf/root carbon are now PROGNOSTIC via a faithful differentiable
  port of the NATURAL-veg annual grass sequence `turnover_grass.c`→`allocation_grass.c` — essential for
  running F_diff on grasslands (no trees). `grow_grass_individual` + `grass_allocparams` (temperate C3 grass
  id 8 verbatim from `par/pft_lpjmlfit.js`) + `grass_treepools(agb, vegc, sla)` (per-area convention:
  leaf=agb, root=vegc−agb, `crownarea=nind=1` ⇒ the existing `fpar`/`fpc` recompute reproduces the C exactly);
  wired into both rollouts via a `galloc` kwarg (grass branch fires only for `is_grass` ⇒ every TREE baseline +
  the Enzyme trainer byte-identical). **Allocation faithful (the deliverable):** golden vs `allocation_grass.c`
  across every branch < 1e-5; conservation 4.4e-16; fed the C's grass NPP the grass equilibrates to leaf:root
  0.791 vs the C's 0.799. **Honest finding:** the self-computed grass NPP is ~3× the C's (grass shares the beech
  photosynthesis/respiration params), so a self-driven grass overshoots — the grass-NPP calibration is the NEXT
  step (parallel to the tree NPP calibration, §13). Gate `grass_structure_tests.jl` (5 testitems: param
  fidelity, golden+conservation, equilibrium-fed-C-NPP, ForwardDiff through the coupled multi-year rollout,
  Enzyme reverse guarded `VERSION<1.11`); suite **26,166 pass / 0 fail / 4 broken**; adversarially verified.
  Report §20; CHANGELOG. Runtime `[deps]` still EMPTY.
- **Phase-3 (session 16) — scale-up step 10: DECADAL (11-year) fidelity validation of the coupled multi-year
  rollout + two diagnosed frontier items.** §18 validated the cell × multi-year objective over 3 years; this
  extends the committed real reference to a full DECADE (2009–2019, `scripts/extract_fdiff_decadal.py` slices
  it from the on-disk daily CSV — no C re-run) and answers the FIDELITY-HORIZON question. **Result: starting
  from the 2008 structure and self-driving 11 years (kernel-isolation C-FAPAR phen, each patch grown by its
  own allocation), F_diff's cell-mean per-year annual GPP tracks the C — mean ratio 1.066, each year bounded
  1.01–1.11 (no runaway), interannual r = 0.86.** The coupled rollout is fidelity-stable over a decade (the
  ~+7 % level bias does NOT compound into drift). Gate `decadal_validation_tests.jl`. **Two findings recorded
  (deferrals, no code change):** the §20 self-driven grass-NPP overshoot is STRUCTURAL — carbon-only run,
  grass fPAR matches the C, light-limited, root C:N/respcoeff = beech; the residual is the SHARED stand-mean
  conductance (`gp_stand`), needing per-PFT conductance not a param fix. The Enzyme-≥1.11 guard-lift is BLOCKED
  upstream (latest Enzyme 0.13.187 still `EnzymeInternalError` on the mutating canopy reverse on 1.11.7).
  Report §21; CHANGELOG. Runtime `[deps]` still EMPTY.
- **Phase-3 (session 17) — scale-up step 11: GRASS-OVERSHOOT RE-DIAGNOSIS — the §21 per-PFT-conductance next
  step is REFUTED; roadmap corrected.** Session 16 set **per-PFT/per-individual canopy conductance** as the
  first-listed next step, on the §21 diagnosis that the shared stand-mean `gp_stand` over-supplies the
  understory grass. Re-diagnosed from the LPJmL-FIT C source + a faithful instrumented reproduction on the
  committed Hainich 2010 cell (adversarially verified — 4 independent lenses, ALL confirming): **the
  attribution is wrong.** (1) The C's returned GPP uses `gp_stand` for every natural PFT incl. grass — the
  per-PFT `gp_pft`/`gc_pft` feed ONLY the `PFT_GCGP` diagnostic (`daily_natural.c:187`) — so a per-PFT GPP
  conductance is LESS faithful, not more. (2) F_diff's grass GPP **already uses `gp_stand`** (measured
  `gc_grass ≈ 0.75·gp_stand`; the moist Hainich soil, growing-season `wscal ≈ 0.99`, keeps it only mildly
  water-limited) — exactly as the C does; the grass's own `gp` is only ~0.14·`gp_stand`, so a per-PFT
  (own-`gp`) conductance would change the grass GPP **~43 %**, a large DE-calibration away from the C-faithful
  value. (3) At the C's OWN structure the per-year grass NPP is **faithful** (total **0.83×**, `fpar` matches)
  — so the §20 "3×" is a **multi-year structural-feedback over-growth** (leaf → LAI → forest-floor `fpar` →
  NPP), unbounded because F_diff lacks the C's grass **cover/light competition** (`light.c` → `light_grass.c`
  kills excess grass leaf/root back to the permitted cover). **Corrected next step: grass cover/light
  competition, NOT per-PFT conductance.** Gate
  reproduction script `scripts/grass_overshoot_diagnosis.jl`; no physics change (diagnosis + roadmap correction).
  Report §22; CHANGELOG. Runtime `[deps]` still EMPTY.
- **Phase-3 (session 18) — CI FIX: the `test (lts)` red was an Enzyme 0.13.189 REGRESSION, not the test tree.**
  Pinned `Enzyme = "0.13.0 - 0.13.188"` in both root + `test/Project.toml` `[compat]` (last-good; 0.13.189
  auto-upgraded via the git-ignored `test/Manifest.toml` and broke the Enzyme-reverse canopy testitems with
  `LLVM error: Canonicalization failed`). Corrected the session-17 worker-poisoning theory. Report §23; CHANGELOG.
- **Phase-3 (session 19) — scale-up step 11 follow-up: GRASS-OVERSHOOT RE-DIAGNOSIS #2 — §22's cover-competition
  next step targets an INACTIVE code path; the real gap is a light-limited grass carbon balance.** §22's corrected
  next step (port `light.c`→`light_grass.c`→`fpc_grass.c` to "kill excess grass leaf/root to litter") targets a
  path the FIT config does NOT run: `"individual":true` ⇒ `annual_natural.c:117` gates `light()` behind
  `if(!config->individual)`, so `light_grass()` is never called; the individual-mode reduction is `reduce_grass`
  (fpc-only, `pft->fpc/=factor`, no carbon killed, gated on total cover > 1 which is < 1 at Hainich). The same
  class of error §22 caught in §21. **The overshoot is nonetheless REAL** (per-patch SLURM reproduction, trees
  FIXED at the C structure so forest-floor light is identical): grass leaf median **92.5 (50–194)** vs the C's
  **6.5 (0.011–215)**, median ratio **×13.9**, cross-patch corr **0.57** — F_diff's grass is compressed and
  insensitive to shading while the C's spans four orders of magnitude. **Mechanism:** an under-light-limited
  grass NPP, **~2–3× the C at matched absorbed light** (grass fpar reproduces the C's `fpar_leafon`, so light
  *absorption* is faithful; the gap is GPP/NPP per absorbed light — a light-insensitive NPP floor of ~2.9
  gC/m²/yr even at ~zero light). **Vindicates session 15's "~3× NPP" as a per-patch fact; §22's "0.83×" was a
  cell-total masking it.** No physics change (as §22): deliverable = corrected diagnosis + two committed
  self-checking reproductions (`scripts/grass_cover_mechanism_diagnosis.jl`, `scripts/grass_lightbalance_probe.jl`)
  + roadmap correction. Report §24; CHANGELOG. Runtime `[deps]` still EMPTY.
- **Phase-3 (session 20) — scale-up step 11 follow-up #2: GRASS-OVERSHOOT RE-DIAGNOSIS #3 + FIX — the §24
  "carbon balance" is per-PFT grass PHENOLOGY (dominant), now wired into the coupled rollout; conductance /
  cover / carbon-balance / respiration / params all RULED OUT.** §24's next step ("a light-limited grass carbon
  balance, pinned with a light- vs conductance-limitation decomposition") is executed. **Five committed SLURM
  decomposition probes** pin the lever: the "carbon balance" is TWO faithful mechanisms F_diff was missing,
  **dominated by per-PFT grass PHENOLOGY** (not any carbon-balance / conductance / respiration parameter), and
  they interact. **(1)** The `daily_step_canopy` softplus GPP floor (`softplus(agd, βflux=50)` → 0.0139
  gC/m²/day ≈ 2.9 gC/m²/yr at ~zero light) is the DEEP-SHADE lever — necessary but not sufficient (moderate
  patches barely move). **(2)** The `gc·fpc − gmin·fpar` demand (`fdiff.jl:1518`) is byte-faithful to
  `water_stressed.c:194`; grass `gmin` inert; at matched leaf+light the grass GPP-per-absorbed-light is
  IDENTICAL to the validated trees' (`3.025e-6` gC/J, `λ=0.85`) and grass respiration matches the C
  (`npp_grass.c`; CUE ≈ trees') — so GPP-per-light and CUE are faithful (RULES OUT §21/§22/§24). **(3, THE
  CAUSE)** `rollout_canopy_years` applied the patch-wide **beech** GSI phenology to the understory grass; the C
  (`new_phenology:true`) runs PER-PFT GSI (the grass light-limited by tree-attenuated forest-floor light,
  `phenology_gsi.c:30-35`). **COMMITTED FIX:** a `pft_ids` kwarg on `rollout_canopy_years` (default grass→8 /
  tree→3) → the grass uses its own light-limited GSI. **Matched-structure grass NPP overshoot 4.26 → 1.13× the
  C, cross-patch corr 0.929 → 0.973.** Tree paths BYTE-IDENTICAL (`pft_phenparams(3) === tebs_phenparams`; full
  suite **26174 pass / 0 fail / 4 broken**; decadal §21 uses `rollout_canopy_years_gpp` with supplied phen —
  untouched; mixed-patch trees shift < 0.4 % via water/conductance competition). New gate in
  `grass_structure_tests.jl`. **Levers INTERACT (co-calibrated next step, NOT committed):** the grass-gated
  hard floor `max(0,agd)` ON TOP of per-PFT phenology OVER-corrects to 0.37× (undershoot) — F_diff's grass GSI
  season is over-suppressed in deep shade (`light_base ≈ 76 W/m²`); and the self-driven per-patch equilibrium is
  bimodal (the C maintains dim-patch grass, NPP < turnover, by ESTABLISHMENT/re-seeding, which the fixed-N loop
  lacks). Reproductions `scripts/grass_lightconductance_decomp.jl`, `scripts/grass_carbonbalance_probe.jl`,
  `scripts/grass_phen_probe.jl`. Report §25; CHANGELOG. Runtime `[deps]` still EMPTY.
- **Phase-3 (session 23) — GRASS-NPP LEVEL GAP FOLLOW-UP #2: the proposed "C re-run" is really a C RECOMPILE;
  the residual is parameter-faithful + SEASON-shaped, NOT the forest-floor light or the GSI cold-start.** §26's
  next step (close the above-threshold grass-NPP level gap via a daily grass GPP-vs-light decomposition, needing
  "the C's daily GRASS GPP") is re-scoped before spending a cluster job. **(1)** LPJmL-FIT has NO per-PFT/
  individual DAILY GPP output (`par/outputvars.js`: only annual `PFT_NPP`/`ind` + cell-total `d_gpp`/`d_npp`) —
  so nothing to extract, and a config-only re-run can't make it; it needs a C-SOURCE change + RECOMPILE. **(2)**
  Source audit: the grass photosynthesis kernel is byte-faithful (co-limitation exact `photosynthesis.c:150`),
  `apar` validated (§20), grass id 8 respiration params LITERALLY beech's (`respcoeff 1.2`/`CTON_ROOT`/`1.16`) —
  so not a parameter. **(3)** Two SLURM probes: the undershoot is gate-independent, above-threshold, tracks the
  grass ACTIVE-DAY fraction growing with shade (`grass_npp_light_response_probe.jl` 1540816); the faithful
  `:exp` forest-floor light is REFUTED (makes above-threshold worse) and the GSI cold-start is REFUTED
  (`grass_gsi_warmstart_probe.jl` 1540819, year1==year5). **Recommendation: DEFER the grass level gap to the
  learned canopy Vcmax/λ correction (§16/§18), don't recompile.** No `src/`/`test/` change (suite unaffected
  26200/4). Report §26.1; CHANGELOG. Runtime `[deps]` still EMPTY.
- **Phase-3 (session 24) — BUILT the C's daily grass GPP/NPP output; F_diff's grass is FAITHFUL; the §26/§26.1
  "level gap" was a REFERENCE-BASIS ARTIFACT. Grass-NPP thread (§20→§26.2) CLOSED.** The user directed "MAKE
  IT" (the daily GPP output), so the LPJmL-FIT C binary was MODIFIED + REBUILT: two scalar daily outputs
  `D_GRASS_GPP`/`D_GRASS_NPP` (`conf.h` 419/420; cell-mean per-day write in `daily_natural.c`; flush in
  `fwriteoutput.c`; `outputvars.js`) — `patches/lpjmlfit_daily_grass_gpp.patch` (+ a `json_object_iterator.h`
  shim for the cluster's truncated json-c/0.13.1 headers). Re-ran Hainich 2000–2019. **F_diff cell-mean daily
  grass NPP vs the C's OWN daily grass NPP, 2009–2019: aggregate ΣF/ΣC = 0.95, mean per-year F/C = 0.98 (range
  0.72–1.19, no systematic bias), season faithful (actR 1.02), amplitude faithful (ampR 0.96), daily r ≈ 0.86.**
  The §26 "0.82×" was F_diff-on-2009-forcing vs the C's 2008 `ind` NPP (a year/basis mismatch; C grass NPP
  swings 28–51/yr). No F_diff physics change; the §26 demand-gate + faithful params make it faithful. Committed:
  the patch, `test/testitems/references/hainich_grass_daily_2009_2019.csv`, scripts
  `run_fdiff_grass_gpp_cell.sh`/`extract_fdiff_grass_daily.py`/`grass_daily_curve_fdiff.jl`/
  `compare_grass_daily_c_vs_fdiff.py`. Report §26.2; CHANGELOG. Runtime `[deps]` still EMPTY.
- **Phase-3 (session 25) — the validated-faithful grass config is now the coupled-rollout DEFAULT.** §26.2
  proved F_diff's grass FLUX faithful, but the two mechanisms that make it so (§26 photosynthesis demand-gate,
  §22 establishment) were still OPT-IN, so the DEFAULT `rollout_canopy_years` kept the deep-shade grass
  overshoot and would extinct dim-patch grass — the fidelity did not take effect for the global run's many
  grass cells. **Flipped:** `rollout_canopy_years` now defaults `grass_demand_gate=true` (via a
  `_with_grass_gate(p, on)` helper that reconstructs `p.water` at the C's sharp `βgpd_gate=1e8` — the §26.2
  validated value; the rollout is the NON-diff path so no gradient cost) + `grass_estab=grass_estabparams(T)`.
  **Grass-only ⇒ tree-only rollouts BYTE-IDENTICAL, and the Enzyme/decadal path `rollout_canopy_years_gpp`
  UNCHANGED** (reads `p.water` directly, gate off; trainer byte-identical + gradient-stable). Validated
  self-driven over the committed decade (`scripts/grass_default_flip_probe.jl`, SLURM 1542301): the GATE lowers
  total grass carbon 111.0→86.6 gC/m² (removes the deep-shade overshoot), ESTABLISHMENT restores survivors
  **14/25→25/25** (gate-alone extincts 11 dim patches; each mechanism ALONE is worse than pre-§26.3 — together
  they give the gate-corrected level, no extinction, physical over 11 yr). **Honest scope:** validates the
  FLUX-config default + anti-extinction, NOT the self-driven grass STRUCTURE per-patch (§24's compressed-grass
  item is separate). Full suite **26205 pass / 0 fail / 4 broken** (SLURM 1542299). Reworked two
  `grass_structure_tests.jl` testitems + a new "default is now faithful-grass" gate. Report §26.3; CHANGELOG.
  Runtime `[deps]` still EMPTY.
- **Phase-3 (session 26) — DIAGNOSED the 2018 grass drought-amplitude residual: a GENUINE grass water-supply
  gap (per-PFT `wscal` + competitive supply depletion collapsed to a stand aggregate).** §26.2's last honest
  grass residual (matched per-year structure → F/C 1.87 in the 2018 European drought). Three matched-structure
  SLURM probes + an adversarial C-source cross-check: it is NOT structure (`corr(F/C, fed_leaf)=−0.12`) and NOT
  the fresh-soil annual reset (carrying F_diff's own multi-year soil column → byte-identical 2018 numbers); it
  IS a water-supply effect — 2018 `wscal` 0.939 vs 0.976 normal, per-leaf grass NPP stays high (F/leaf 2.591 vs
  the C's 1.386). Root cause (code-verified): `daily_step_canopy` runs ONE stand-level water balance — `wr` from
  a single shared `soil.rootdist`, grass `supply_i` the UNCAPPED potential, `wscal = min(1, Σsupply·fpc/
  Σdemand·fpc)` one FPC-weighted scalar saturating near 1 (`fdiff.jl:1467-1473,1528,1587`); it barely moves in
  2018 via demand-saturation + top-layer over-recharge (`_infiltrate` :812-832). The C keeps a per-PFT `wscal`
  (`water_stressed.c:130-140`) AND a sequential competitive per-layer cap `aet_cor` (`:153-177,264-275`, per PFT
  at `daily_natural.c:181`) — trees deplete the shared column first, grass's realized supply collapses.
  **CORRECTION (cross-check overturned the first reading):** the C's grass is FULL-depth-rooted, `beta_root=0.8`
  identical to trees (`new_grass.c:40`; `pft.js:494/1110`) — no shallow grass rooting to lose; `gp_stand` is
  FAITHFUL. The rooting counterfactual (shallow → 2018 F/C 1.87→1.13) is a LEVER localizing the channel, not the
  C mechanism. Same family as §20/§22 (per-PFT state aggregated to stand), water-SUPPLY axis; fix = per-PFT
  `wscal` + `aet_cor` competitive cap (deferred, coupled structural item). Diagnosis only — no `src/`/`test/`
  change. Report §26.4; CHANGELOG. Probes `scripts/grass_drought_{amplitude,soilmemory,rooting}_probe.jl`.
  Runtime `[deps]` EMPTY.
- **Phase-3 (session 26) — the `FDiffFastCore` deployment adapter reaches `rollout_canopy_years` GRASS
  parity (§27).** The `FDiffFastCore` SharedState adapter (`src/components/fast.jl`, the ESM coupling surface)
  still grew grass with the TREE machinery; now it mirrors `rollout_canopy_years`, all **grass-only**: per-PFT
  GSI phenology (persisted per-DISTINCT-PFT filters + lag-1 `grass_lf`, since the adapter is day-by-day), the
  §26 demand-gate (constructor `_with_grass_gate`), grass allocation (`grow_grass_individual`), grass
  establishment. **Tree-only core BYTE-IDENTICAL** (all `is_grass`-gated); the AD trainer
  `rollout_canopy_years_gpp` is untouched (this adapter is the non-AD deployment surface). `coupling_tests.jl`
  now also drives a mixed tree+grass core. Full suite **26,214 pass / 0 fail / 4 broken**. Report §27;
  CHANGELOG. Runtime `[deps]` EMPTY.
- **Phase-3 (session 27) — TWO FRONTIERS run in parallel + both ops items resolved: (A) the mandated
  `sapwood_bg` quantification probe → GO; (B) the per-PFT competitive water-supply fix SCOPED + §26.4
  CORRECTED in two load-bearing ways.** **(A)** The §7-mandated probe
  (`scripts/sapwood_bg_quantification_probe.jl`, no `src/` change) reconstructs the C's below-ground
  root-sapwood pool from the C_LATERAL demand (`allocation_tree.c:163-189`, verbatim) + adds the phen-gated
  maintenance (`npp_tree.c:51`): pool **531.4 gC/m² (22.7% of ag sapwood)**, **CUE 0.512→~0.49** (ΔRa_bg
  1.94% GPP), every prediction incl. ±30% inside `[0.42,0.56]` with margin ⇒ **GO, the §4.2 floor-break fear
  REFUTED** — but it closes only ~40–50% of the 0.51→0.46 gap (a fidelity refinement, not full closure;
  needs the coupled `rd`-gate §6). Reproduced twice, Runic-clean. **(B)**
  `docs/water_supply_perpft_design.md` + §26.4 CORRECTION #2: the fix is the **`aet_cor` competitive
  per-layer supply cap ALONE** (per-PFT `wscal` DEGENERATE — `EMAX_ANGIO=EMAX_GRASS=10.0`
  `par/pft_lpjmlfit.js:116-118`, shared `beta_root=0.8`), and the build's **`-DPERMUTE`** (daily Fisher-Yates
  PFT-depletion order) makes an exact port **non-differentiable + non-deterministic** (breaks
  Enzyme/ForwardDiff + `determinism_tests`) ⇒ **recommend DEFER behind the `FluxHooks` learned lever**, as the
  grass level gap was. **Ops:** CI green on required checks (`test (lts)`+`test (1)`; `pre` allowed-fail);
  `test/Manifest.toml` stays DEFERRED (Pkg.test sandboxes the test env, root Manifest trivial, Enzyme
  `[compat]` pin already secures CI). **Then IMPLEMENTED the §8-GO'd `sapwood_bg` frontier (C)** — the C's
  below-ground root-sapwood pool + its phen-gated maintenance, as an OPT-IN / default-byte-identical mechanism
  (`TreePools`/`Individual` gain the field with backward-compat constructors, `autotrophic_respiration` gains
  a default-0 maintenance kwarg, `reconstruct_sapwood_bg` seeds from the C_LATERAL demand): seeding moves tree
  CUE **0.512→0.497** with GPP byte-identical, full suite **26228 pass / 0 fail / 4 broken**. Commits
  **d773c701** (B) + **ed7c05a6** (A) + **037543d2** (C). Runtime `[deps]` EMPTY.

---

## ⭐⭐ PHASE 4 LANDED — COMPONENT E (ENERGY BALANCE + SKIN TEMPERATURE) + THE END-TO-END COUPLED EMULATOR RUNS (the emulator is now USABLE)

**This is the keystone the project existed to build.** The prior ~14 sessions were all Phase-3 *fidelity
refinements* of an already-in-band fast core (grass overshoot #1/#2/#3, sapwood_bg, water-supply) — while
the two pieces that make this an actual ESM-ready land component, **Component E (the surface energy balance
+ skin temperature LPJmL-FIT lacks) and the coupled run loop, were never built** (`energy.jl`/`slow.jl` were
stubs that only threw). Phase 4 builds E and couples F+E end-to-end, so the component now returns the
atmosphere-facing tuple (LE, H, G, T_skin, NBP, z0) with energy closed by construction. **Landed on `main`.**

- **Component E — self-contained (`src/components/energy.jl`; ADR 0017).** `SEBEnergyClosure` + pure kernels
  `solve_seb`/`aerodynamic_conductance`. One skin temperature from `Rn(Tₛ)=SW(1−α)+ε·LW−εσTₛ⁴`, closing
  `Rn=LE+H+G` with `H=ρc_p g_a(Tₛ−Tair)` — **LE fixed by F (water-limited), H the residual** (documented
  exception). Fixed-graph damped Newton (AD-friendly, `solve_lambda` pattern); `g_a` neutral log-law; `G=λ_g(Tₛ−T_soil)`
  with a deep-soil-temp EWMA E owns. Demand cap OFF by default (uncapped ⇒ exact closure + conservation-safe).
  **NO Terrarium runtime dep** — ADR 0017 supersedes 0006's reuse (open AGPL↔EUPL licensing blocker +
  zero-deps/offline-node constraints, exactly as ADR 0014 for the fast core; physics decisions retained).
- **Coupled run loop (`src/run.jl`): `run_coupled_cell`/`couple_day!`/`stand_structure_toe`.** Per day F→`FToE`,
  structure (`SToE`) re-derived from F's own prognostic canopy, E→`EToATM`+`EToF`, and the **mandatory E→F
  skin-temperature feedback** into F's phenology soil-temp gate. `FDiffFastCore` gains `soiltemp_skin` (NaN
  default ⇒ air-temp proxy ⇒ **byte-identical**) + `last_albedo` (write-only diagnostic). Every existing
  baseline + the AD trainer untouched.
- **Verified.** `test/testitems/energy_closure_tests.jl` (closure to machine precision over a 13,824-case
  grid; AD via ForwardDiff-vs-FiniteDifferences; Float32; demand-cap opt-in) + `test/testitems/coupled_run_tests.jl`
  (a real Hainich year closes every day, plausible seasonal cycle, feedback on/off). **Full CI-faithful suite green.**
- **Deployment demo (`scripts/run_coupled_cell.jl`).** The coupled emulator over the Hainich cell (25 patches,
  cell-mean) for the committed decade 2009–2019: energy closes to **1.4e-14 W/m²** every day, annual-mean G≈0
  (no spurious heat sink), no multi-year drift, and it **emergently captures the 2018 European drought** —
  summer Bowen ratio **0.89** vs ~0.15–0.29 in normal years (water stress → ET suppressed → sensible heat up).
  Writes `logs/coupled_decadal_hainich.csv`.
- **★ DONE since (follow-ons to Phase 4):** (a) **E fidelity — Monin–Obukhov `g_a` STABILITY correction**
  (ON by default; true-Newton coupled solve ⇒ closure exact + aerodynamic identity to ~3e-11; stable nights
  cool more, unstable days ventilate; AD-safe). (b) **PHASE 5 multi-cell/biome generalization** — REAL
  GSWP3-W5E5 forcing for 5 biome cells (`scripts/extract_biome_forcing.py`, committed CSVs), coupled loop
  runs across the full climate envelope, **energy closes ≤3e-14 W/m² everywhere**, emergent climate-correct
  partitioning (tropical LE-dominated, dry biomes H-dominated, boreal low-flux); gates
  `biome_coupled_tests.jl` + `energy_closure_tests.jl` stability testitem; demo `scripts/run_coupled_biomes.jl`.
- **★ NEXT (highest value first).** (c) **Wire Component S** into deployment (Phase-2 emulator → `SToF`/`SToE`
  per DESIGN §8; F self-computes structure until then) — the last unbuilt architecture piece. (d) **Biome-
  calibrated vegetation** for Phase 5 (biome PFT params + spin-up; the current demo uses a common canopy to
  isolate the climate signal). (e) **Real wind (`sfcwind`) + surface pressure** — the raw-GSWP3 `.clm` are a
  DIFFERENT (int16, re-ordered) grid from the `_test` files (raw cell 42490 ≠ Hainich, verified), so this needs
  a cross-grid lat/lon remap; plus a **snow-sublimation λ** split. (f) **FLUXNET/PLUMBER2 validation of E's
  LE/H/T_skin** (external-data-bounded; Hainich = DE-Hai) — the H residual must be validated hardest. (g) the
  deferred Phase-3 items (sapwood_bg prognostic growth, per-PFT water supply, grass learned lever) remain
  optional fidelity refinements.

---

## ⭐ WHAT LANDED IN SESSION 27 (on `main`) — TWO PARALLEL FRONTIER INVESTIGATIONS + the GO'd IMPLEMENTATION: (A) `sapwood_bg` PROBE → GO; (B) per-PFT WATER-SUPPLY SCOPED + §26.4 CORRECTED → DEFER; (C) `sapwood_bg` IMPLEMENTED (opt-in, default byte-identical)

**Chief-investigator session: dispatched the two open substantive frontiers as parallel background
investigations, independently VERIFIED each against the C source before accepting (this grass/tree thread
has a documented history of mis-attributions), integrated + committed each sequentially, resolved both ops
items directly — and then IMPLEMENTED the frontier the probe (A) cleared (C): the below-ground root-sapwood
pool + its phen-gated maintenance, landed OPT-IN / default byte-identical so nothing regresses. Full
CI-faithful suite 26228 pass / 0 fail / 4 broken; `[deps]` EMPTY.**

### (A) `sapwood_bg` quantification probe → GO — commit `ed7c05a6` (`docs/sapwood_bg_design.md` §8)
- **The design's §7 gate.** `sapwood_bg_design.md` mandated a scripts-only probe to predict the tree-CUE
  decrement BEFORE the invasive `TreePools`/`Individual` struct change (§5), because seeding is mandatory
  (a 0-seed is inert, §4.1) and an over-large seed could push CUE below the 0.42 gate floor (§4.2).
- **Method (faithful, PM-reproduced).** `scripts/sapwood_bg_quantification_probe.jl` reuses the VALIDATED
  F_diff kernels for the baseline (the CUE gate's own `mkind` + `rollout_daily_canopy`, no `pft_ids`),
  reconstructs `sapwood_bg` per tree from the C_LATERAL demand (`allocation_tree.c:163-189` — vertical +
  lateral `2π/0.81≈7.757` + the `root_sum` decrement) and adds ONLY the phen-gated maintenance analytically
  (`npp_tree.c:51`, `cn_sapwood=330`). I independently reproduced the run and re-verified both C equations.
- **RESULT = GO.** CUE_baseline **0.5118** (GPP 1250.1, NPP 639.9; matches §13's ~0.51); pool **531.4 gC/m²
  = 22.7% of ag sapwood**; ΔRa_bg **24.3 gC/m²/yr = 1.94% GPP**; CUE_new **0.4924** (conservative) /
  **0.4973** (growth-resp-adjusted); ±30% band **0.487–0.498** — all inside `[0.42,0.56]` with large margin.
  The §4.2 fear that the `2π/0.81` lateral factor makes the pool floor-breakingly large is **REFUTED**.
- **★ HONEST CAVEAT (load-bearing for the go-ahead).** `sapwood_bg` ALONE closes only ~40–50% of the
  0.51→0.46 gap (lands ~0.49, ~0.03 above the C). It is a validated FIDELITY REFINEMENT of an ALREADY-IN-BAND
  metric (CUE 0.51 already passes the gate), NOT a gate fix; full closure needs the coupled `rd`-gate too
  (§6, which partially cancels). The probe's own question ("does it break the floor?") is answered NO; the
  design's "lands CUE ~0.46" is met only partially. The struct plumbing is de-risked, but whether to spend
  the 2–3 implementation sessions now vs. after a higher-value frontier is a SEQUENCING call (see NEXT).

### (B) per-PFT competitive water-supply fix — commit `d773c701` (`docs/water_supply_perpft_design.md`; §26.4 CORRECTION #2)
- **Turned §26.4's "FIX DIRECTION" into an implementable design and, in doing so, CORRECTED §26.4 twice
  (both source-verified by me, not paraphrase-trusted):**
  1. **The mechanism SHARPENS to the `aet_cor` competitive per-layer supply cap ALONE.** §26.4 bundled it as
     "per-PFT `wscal` + the cap"; the `wscal` half is DEGENERATE here — `EMAX_ANGIO = EMAX_GRASS = 10.0`
     (`par/pft_lpjmlfit.js:116-118`) + grass shares beech's `beta_root=0.8`, so per-PFT `wscal` is ≈identical
     grass-vs-tree and feeds only phenology + allocation, not the within-day GPP solve.
  2. **`-DPERMUTE` makes an exact faithful port structurally impossible.** The FIT build (active
     `Makefile.inc:22`; all `config/Makefile.*` platform templates carry it) re-draws the PFT depletion order
     EVERY day via Fisher-Yates on the cell RAND48 seed — no deterministic "trees-first"; the C's grass
     suppression is an order-AVERAGED stochastic outcome. A deterministic F_diff order over-suppresses; a
     faithful replication is non-differentiable + non-deterministic (breaks Enzyme/ForwardDiff +
     `determinism_tests`); and `aet_cor` is a loop-carried read-modify-write accumulator directly on the
     trained-GPP reverse path.
- **RECOMMENDATION = DEFER** behind the `FluxHooks` learned per-individual correction (already sees `wr` +
  per-individual `apar`, `fdiff.jl:56,68`), exactly as the §26/§26.1 grass LEVEL gap was deferred. Two
  scripts-only de-risking probes specified in §7 (a deterministic-vs-Monte-Carlo-PERMUTE `aet_cor` magnitude
  probe + an Enzyme-feasibility spike) BEFORE any `src/` edit, if ever pursued.

### Ops (resolved directly)
- **CI green on HEAD** — required checks `test (lts)` + `test (1)` pass; `test (pre)` is `continue-on-error`
  (Julia pre-release, allowed to fail); macOS is a non-required extra.
- **`test/Manifest.toml` stays DEFERRED (the handoff's "commit it for reproducibility" rests on a
  misconception).** `Pkg.test()` resolves the test env in a sandbox temp dir (a committed test manifest would
  not feed CI and would embed a machine-specific `Pkg.develop` path); the root Manifest is genuinely trivial
  (`[deps]` empty by ADR 0014's train/test-only AD design, so the `.gitignore` un-ignore condition is unmet);
  and the Enzyme `[compat]` pin (`0.13.0 - 0.13.188`) already secures CI against the 0.13.189 regression.

### (C) `sapwood_bg` IMPLEMENTATION — commit `037543d2` (`docs/sapwood_bg_design.md` §8.1; new `test/testitems/sapwood_bg_tests.jl`)
- **Landed the §8-GO'd mechanism as OPT-IN / default byte-identical** (the §26 grass-demand-gate discipline),
  so nothing existing regresses and NO baseline was regenerated this session:
  - `TreePools` (10→11) + `Individual` (16→17) gain `sapwood_bg_c`/`c_sapwood_bg`, each with a
    **backward-compatible constructor** (old arity fills the pool 0) ⇒ all ~33 construction sites — incl. the
    Enzyme SoA trainer `rollout_canopy_years_gpp` and every committed baseline — are byte-identical.
  - `autotrophic_respiration` gains a default-0 `c_sapwood_bg` kwarg (`phen·c_sapwood_bg/cn_sapwood`,
    `npp_tree.c:51`); `daily_step_canopy` passes `ind.c_sapwood_bg·nind` for trees. `reconstruct_sapwood_bg`
    seeds from the C_LATERAL demand (`allocation_tree.c:163-189`).
  - **In-model (new gate):** seeding moves tree CUE **0.512→0.497** (the growth-resp-rebated value the model
    applies), **GPP byte-identical** (maintenance ≠ GPP), CUE in `[0.42,0.56]`; pool 531.4 gC/m² (22.7 %) =
    the §8 probe. Full CI-faithful suite **26228 pass / 0 fail / 4 broken** (login-node `Pkg.test`).
- **The pool is STATIC-seeded** (an opt-in, behaviour-unchanged-by-default landing). Its prognostic growth +
  the default-flip are the next steps (see NEXT).

- **★ NEXT (session 28).** In rough value order: **(a) FINISH `sapwood_bg`** — the opt-in mechanism now exists
  (C); the remaining design-§5 steps are the prognostic C_LATERAL pool GROWTH + carbon-debt loan in
  `grow_individual` (§5.4), the Enzyme SoA `sapbgcs` thread (§5.5), adding `sapwood_bg_c` to `vegc_ind` + the
  `dynamic_structure` conservation assertion, and flipping the seed ON by default (regenerating the
  `multi_individual` CUE gate to ~0.497 + the coupled/decadal NPP-derived baselines, which drift §4.3) — only
  after the default-flip does the emulator's default behaviour change. NB it remains a fidelity refinement of
  an already-in-band metric (~half the 0.51→0.46 gap; full closure needs the `rd`-gate, §6). **(b) the
  `FluxHooks` learned grass water/Vcmax correction** — the lever both the grass level gap (§26.1) and the 2018
  water-supply amplitude residual (§26.4) route to; NB (re-checked this session) it needs a grass-SPECIFIC
  correction (the shared MLP has no PFT/`is_grass` feature, so a `w_soil`-driven fix would wrongly scale tree
  GPP) — a feature/architecture change + grass-only loss, not "~0 physics" as previously framed. **(c)** the
  per-PFT competitive water-supply structural port — DEFERRED (see B; only if the learned lever fails, after
  its two de-risking probes). **(d)** the upstream-Enzyme-≥1.11 guard-lift (still blocked upstream).

---

## ⭐ WHAT LANDED IN SESSION 26 (on `main`) — DIAGNOSED THE 2018 GRASS DROUGHT-AMPLITUDE RESIDUAL (per-PFT `wscal` + competitive supply depletion collapsed to a stand aggregate) + `FDiffFastCore` GRASS PARITY

**§26.2's one remaining honest grass residual — the matched per-year structure gives F/C 1.87 in the 2018
European drought (F_diff's grass over-produces) — is now DIAGNOSED (diagnosis-first, because this thread has a
history of mis-attributed grass diagnoses; an adversarial C-source cross-check OVERTURNED a plausible-but-wrong
first reading). It is a GENUINE grass water-supply gap: F_diff collapses the C's per-PFT water-stress state
(per-PFT `wscal` + sequential competitive supply depletion) into one stand aggregate. Diagnosis only — no
`src/`/`test/` change.** (Report §26.4; CHANGELOG.)

- **★ THREE MATCHED-STRUCTURE PROBES (SLURM) + C-SOURCE CROSS-CHECK.** (1) `grass_drought_amplitude_probe.jl` —
  NOT structure (`corr(F/C, fed_leaf)=−0.12`), IS water: 2018 `F/leaf` 2.591 vs the C's `C/leaf` 1.386, 2018
  `wscal` 0.939 vs wet-year 0.976, `corr(F/C,−wscal)=0.66`. (2) `grass_drought_soilmemory_probe.jl` — the
  decisive artifact test: carrying F_diff's OWN multi-year soil column 2009→2019 gives BYTE-IDENTICAL 2018 (F/C
  1.87, wscal 0.939) ⇒ GENUINE (not the fresh-soil reset), soil re-equilibrates within-year (no multi-year
  legacy). (3) `grass_drought_rooting_probe.jl` — a LEVER localizing the channel: shallowing the stand rooting
  DEEP→MID→SHALLOW grows the 2018 `wscal` drop ~6× (−0.037→−0.195→−0.218), F/C 1.87→1.30→1.13. Read as a
  channel-localizer, NOT the C mechanism (it shallows trees too; the C's grass is deep-rooted).
- **★ ROOT CAUSE (both sides, code-verified).** F_diff `daily_step_canopy` runs ONE stand-level water balance:
  `wr` from a single shared `soil.rootdist`, each grass `supply_i` the UNCAPPED potential, `wscal = min(1,
  Σsupply·fpc/Σdemand·fpc)` one FPC-weighted (tree-dominated) scalar saturating near 1 (`src/fdiff.jl:1467-1473,
  1528, 1587`); it barely moves in 2018 via demand-saturation (Σsupply > Σdemand) + top-layer over-recharge
  (`_infiltrate` fills to FC each rain, `:812-832`, no competitive depletion). The C shares the SAME soil column
  but keeps a per-PFT `pft->wscal` (`water_stressed.c:130-140`) AND a sequential competitive per-layer
  availability cap `aet_cor` (`:153-177,264-275`, per PFT at `daily_natural.c:181`): the dominant trees deplete
  the shared layers first, so grass's realized supply collapses in drought — F_diff's grass instead takes the
  uncapped potential.
- **★ CORRECTION (adversarial cross-check).** The C's grass is FULL-depth-rooted, `beta_root=0.8` identical to
  trees (`new_grass.c:40`; `pft.js:494/1110`) — NO shallow grass rooting to lose; and `gp_stand` is FAITHFUL
  (the C also uses it for demand + the GPP-solve gc, `:118,180-194`). So the gap is per-PFT `wscal` + the
  competitive supply depletion, NOT rooting depth and NOT the conductance.
- **★ CLASSIFICATION + FIX.** Same FAMILY as §20/§22 (F_diff aggregates the C's per-PFT state into stand
  quantities) but on the water-SUPPLY axis specifically; NOT a GPP-response/parameter/soil-memory gap (all ruled
  out). Modest extreme-year effect (aggregate grass fidelity ~0.95–1.10). FIX = a per-PFT realized-supply water
  balance porting `water_stressed.c`'s per-PFT `wscal` + the `aet_cor` competitive per-layer cap — a coupled
  structural item, deferred.
- **★ COMMITTED.** Docs §26.4 + CHANGELOG + JOURNAL + HANDOFF + MEMORY; the three reproduction probes. No
  `src/`/`test/` change; `[deps]` EMPTY. SLURM outputs ephemeral (`logs/` git-ignored). Probe jobs 1542639 +
  1542679.

**PLUS — `FDiffFastCore` GRASS PARITY (§27).** The deployment adapter (`src/components/fast.jl`) now mirrors
`rollout_canopy_years`'s grass handling — per-PFT GSI phenology (persisted per-DISTINCT-PFT filters + lag-1
`grass_lf`), the §26 demand-gate (`_with_grass_gate`), grass allocation (`grow_grass_individual`), grass
establishment — all **grass-only** ⇒ a tree-only core is BYTE-IDENTICAL and the AD trainer
`rollout_canopy_years_gpp` is untouched (the adapter is the non-AD deployment surface). The `coupling_tests.jl`
gate now also drives a mixed tree+grass core (grass finite/non-negative, no woody pools/height, trees grow;
establishment differential). Full CI-faithful suite **26,214 pass / 0 fail / 4 broken**; Runic-clean. The
`sapwood_bg` frontier is now scoped (see `docs/sapwood_bg_design.md`).

- **★ NEXT (session 27).** The grass thread is CLOSED (flux faithful §26.2, default flipped §26.3, drought
  residual diagnosed §26.4, deployment adapter at parity §27). Remaining frontiers: **(a) the tree
  `sapwood_bg` + carbon-debt** — the design is scoped (`docs/sapwood_bg_design.md`); START with the
  quantification probe (§7 there: predict the CUE decrement from the committed `sapwood_c/height/wooddens`
  before the invasive AD-path struct change), because seeding is mandatory (a 0-seed never bootstraps) and an
  over-large seed pushes CUE below the 0.42 gate floor. **(b) the per-PFT water-supply balance** (§26.4 fix:
  per-PFT `wscal` + the `aet_cor` competitive per-layer cap) — a coupled structural item, the water-supply
  analog of the §20/§22 per-PFT machinery. **(c)** the upstream-Enzyme-≥1.11 guard-lift (still blocked) and
  committing `test/Manifest.toml` for reproducible CI resolution (a fresh re-resolve now needs a git clone the
  compute nodes can't reach — the login node has pkg-server access; see below).

---

## ⭐ WHAT LANDED IN SESSION 25 (on `main`) — THE VALIDATED-FAITHFUL GRASS CONFIG IS NOW THE COUPLED-ROLLOUT DEFAULT (grass fidelity made real for the global run)

**§26.2 settled that F_diff's grass FLUX is faithful, but the demand-gate (§26) + establishment (§22) that
make it so were OPT-IN — so the DEFAULT multi-year coupled rollout `rollout_canopy_years` still ran the
deep-shade grass overshoot and would extinct dim-patch grass. Ten sessions of grass fidelity did not take
effect in the behaviour a global (many grass-dominated cells) run would see. This session flips the default —
surgically, grass-only, nothing validated regresses.** (Report §26.3; CHANGELOG.)

- **★ THE CHANGE.** `rollout_canopy_years` now DEFAULTS `grass_demand_gate=true` + `grass_estab=grass_estabparams(T)`.
  Helper `_with_grass_gate(p, on)` reconstructs `p.water` with the gate on at the C's sharp step
  `βgpd_gate=1e8` (the §26.2-validated value; `rollout_canopy_years` is the non-differentiable diagnostic /
  self-driven path, so the steep sigmoid costs no gradient). Pass `grass_demand_gate=false` /
  `grass_estab=nothing` for the pre-§26.3 references.
- **★ NOTHING VALIDATED REGRESSES (grass-only).** Tree-only rollouts are **byte-identical** (gate is gated on
  `ind.is_grass`; establishment is a no-op with no grass — verified `leaf_c`/`height` to the last bit). The
  **Enzyme / decadal path `rollout_canopy_years_gpp` is UNCHANGED** (reads `p.water` directly, gate off; the
  NN trainer stays byte-identical + gradient-stable; §21 decadal GPP unaffected). Bare default is bit-identical
  to explicit `grass_demand_gate=true, grass_estab=grass_estabparams()` (new gate assertion).
- **★ VALIDATED self-driven over the real decade** (`scripts/grass_default_flip_probe.jl`, SLURM 1542301;
  committed Hainich 25 mixed patches, 2008 structure self-driven 2009–2019): GATE lowers Σ grass leaf
  111.0→86.6 gC/m² (deep-shade overshoot removed); ESTABLISHMENT survivors **14/25→25/25**; all physical,
  trees grow. Each mechanism alone is worse than pre-§26.3.
- **★ HONEST SCOPE.** Validates the flux-config default + establishment-prevents-extinction + gate-removes-overshoot;
  does NOT claim the self-driven grass STRUCTURE matches the C per-patch (§24 found it compressed/light-insensitive
  — a separate open item). The grass FLUX faithfulness (matched structure) is §26.2, unchanged.
- **★ COMMITTED.** `src/fdiff.jl` (`_with_grass_gate` + defaults + docstring); two reworked
  `grass_structure_tests.jl` testitems + a new default-is-faithful gate; `scripts/grass_default_flip_probe.jl`;
  docs §26.3 + CHANGELOG. Suite 26205 pass / 0 fail / 4 broken. Runtime `[deps]` still EMPTY.
- **★ NEXT (session 26).** Two grass follow-ups + the tree frontier: (a) **the 2018 drought-amplitude residual**
  (§26.2: matched per-year structure gives F/C 1.87 in the 2018 European drought, ampR 1.69 — F_diff's grass
  under-responds to extreme drought/heat) — DIAGNOSE FIRST whether it is a real grass water/heat-stress
  mechanism gap or a per-year `ind` structure-reconstruction artifact (the confound §26.2 flagged), given this
  thread's history of mis-attributed grass diagnoses; (b) bring the **`FDiffFastCore` v1 adapter** to
  `rollout_canopy_years` parity — it still grows grass with the TREE allocation (`grow_individual`) + a single
  beech-style phenology + no gate/establishment (a real deployment-path gap, though not the AD path). The
  larger frontier remains the tree below-ground **`sapwood_bg` + carbon-debt** (scouted §26.2/§13).

---

## ⭐ WHAT LANDED IN SESSION 24 (on `main`) — BUILT THE C'S DAILY GRASS GPP/NPP OUTPUT; F_diff'S GRASS IS FAITHFUL; THE §26/§26.1 "LEVEL GAP" WAS A REFERENCE-BASIS ARTIFACT (grass-NPP thread CLOSED)

**The user directed "if no daily GPP output is needed: MAKE IT!" — so the LPJmL-FIT C binary was MODIFIED +
RECOMPILED to emit the missing daily grass GPP/NPP, Hainich was re-run, and the new ground truth was used to
test F_diff's grass. Result: F_diff's grass GPP/NPP is FAITHFUL to the C; the §26/§26.1 "0.82× level gap" was
an artifact of comparing against the wrong reference.** (Report §26.2; CHANGELOG.)

- **★ THE C-SOURCE CHANGE (built + patch-committed).** Two scalar daily outputs `D_GRASS_GPP`/`D_GRASS_NPP`
  (`include/conf.h` ids 419/420, `NOUT`→421); cell-mean per-day accumulation in `src/lpj/daily_natural.c` beside
  the unconditional `GPP`/`NPP` writes (`if(getpftpar(pft,type)==GRASS) ...+=gpp*frac`); explicit flush in
  `src/lpj/fwriteoutput.c` (ids outside the `D_LAI..D_PET` loop); registered in `par/outputvars.js`. 18 ins/1
  del, `patches/lpjmlfit_daily_grass_gpp.patch`. Rebuild used the production toolchain + a local
  `json_object_iterator.h` shim on `CPATH` (this cluster's `json-c/0.13.1` headers are truncated). Correctness:
  the new `d_grass_npp` annual = 50 ≈ the stock `pft_npp` band-8 grass value 51.
- **★ F_diff GRASS IS FAITHFUL** (`scripts/run_fdiff_grass_gpp_cell.sh`, single cell 2000–2019;
  `scripts/compare_grass_daily_c_vs_fdiff.py`). F_diff cell-mean daily grass NPP (matched 2008 structure,
  faithful params, demand-gate ON) vs the C's OWN daily grass NPP, 2009–2019: **aggregate ΣF/ΣC = 0.947, mean
  per-year F/C = 0.977 (range 0.72–1.19, NO systematic bias), season length faithful (actR 1.02), amplitude
  faithful (ampR 0.96), daily r ≈ 0.86.** Grass CUE (from the new GPP output) 0.55–0.60 in the C, matching F_diff.
- **★ THE §26 ARTIFACT.** §26/§26.1 measured F_diff (2008 structure, 2009 forcing) against the C's **2008**
  per-patch `ind`-output NPP — a year/basis mismatch (C grass NPP swings 28–51 gC/m²/yr). Against the C's
  same-year daily grass flux the offset vanishes (2009 F/C 1.09, not 0.83). The demand-gate + faithful grass
  params (already committed §26/§26.1) make the grass faithful — no further physics change.
- **★ COMMITTED.** C-source patch + json shim (`patches/`); CI-friendly reference
  `test/testitems/references/hainich_grass_daily_2009_2019.csv`; scripts (run/extract/curve/compare). No
  `src/`/`test/` F_diff change. **Rebuilt FIT binary at `/home/jamirp/lpjml56fit/bin/lpjml` now emits daily
  grass GPP/NPP; pristine pre-change binary at `bin/lpjml.pre_dgrass.bak`.**

---

## ⭐ WHAT LANDED IN SESSION 23 (on `main`) — GRASS-NPP LEVEL-GAP FOLLOW-UP #2: THE "C RE-RUN" IS REALLY A C RECOMPILE; THE RESIDUAL IS PARAMETER-FAITHFUL + SEASON-SHAPED (diagnosis + roadmap correction; NO physics change)

**§26 scoped the next step as "close the grass-NPP level gap via the grass GPP-vs-light response, which needs
the C's daily GRASS GPP (extract per-PFT daily GPP from the single-cell output, or a targeted re-run)". This
session re-verified that scoping BEFORE spending a cluster job and found it mis-scoped, then refuted the
leading levers with two zero-core-change SLURM probes.** Deliverable = corrected diagnosis + roadmap + two
committed self-checking reproductions. No `src/`/`test/` change ⇒ suite unaffected (26200/4). (Report §26.1;
CHANGELOG "Changed".)

- **★ FINDING 1 — the "re-run" is a C RECOMPILE.** No per-PFT/individual DAILY GPP output exists in LPJmL-FIT
  (`par/outputvars.js`: annual `PFT_NPP`/`ind` + cell-total `d_gpp`/`d_npp` only). Nothing to extract; a
  config-only re-run can't produce it — needs a C-source output slot + rebuild (a new class of work).
- **★ FINDING 2 — NOT a photosynthesis/respiration PARAMETER** (source audit). Kernel byte-faithful
  (co-limitation exact quadratic `photosynthesis.c:150`==`fdiff.jl:431`; `vm`/`rd`/`adt` match); `apar`
  validated (§20/§21); grass id 8 respiration params (`respcoeff 1.2`, `cn_ratio.root CTON_ROOT`, `ratio.root
  1.16`) are LITERALLY beech id 3's ⇒ CUE faithful. temp/albedo already ruled out (§26 fu#1).
- **★ FINDING 3 — gate-independent, ABOVE-threshold, tracks the grass ACTIVE-DAY fraction, grows with shade**
  (`grass_npp_light_response_probe.jl`, SLURM 1540816). Brightest-half agg F/C 0.861 (~same gate-ON vs OFF);
  per-patch 0.86@ff0.50 → 0.57@ff0.29; active-day frac 0.66→0.30 — a season-shape residual, not GPP-per-leaf.
- **★ FINDING 4 — the faithful `:exp` forest-floor light is REFUTED** as the fix (brightest-half F/C
  0.861→0.755 + 7 deep-shade negatives) — refutes §26 F6's deferred `:exp` lever.
- **★ FINDING 5 — the grass GSI COLD-START is REFUTED** (`grass_gsi_warmstart_probe.jl`, SLURM 1540819;
  5-yr continuous warm-up ⇒ year 1 == year 5 to every digit). The GSI equilibrates within year 1.
- **★ NO-RECOMPILE enabler:** a multi-year (2009–2019) per-patch grass NPP reference is sliceable from the
  on-disk production `ind` output (`/p/tmp/jamirp/emulator_global/ind_hist_seed1_all.parquet`).
- **★ RECOMMENDATION (scope decision for the user): DEFER, don't recompile** — let the learned canopy Vcmax/λ
  correction (§16/§18, proven on trees) absorb the grass level bias; move to another frontier item. If a
  hard-coded fix is wanted, fit the grass phenology season vs the disk-extractable multi-year reference (no C
  re-run); recompile only if that proves insufficient.

---

## ⭐ WHAT LANDED IN SESSION 22 (on `main`) — GRASS-EQUILIBRIUM CO-CALIBRATION: THE §25 HARD-FLOOR LEVER IS REFUTED; THE FAITHFUL MECHANISM IS THE C'S PHOTOSYNTHESIS DEMAND-GATE; THE GATE EXPOSES THE TRUE RESIDUAL (scale-up step 11 follow-up #3)

**§25's co-calibrated next step (three interacting faithful mechanisms) is pinned with a committed
co-calibration probe (`scripts/grass_cocalibration_probe.jl`: matched-structure per-patch spectrum +
gate-sharpness sweep + the self-driven 11-yr equilibrium). The §25 hard-floor lever is REFUTED; the C's
mechanism is a photosynthesis DEMAND-GATE; turning it on EXPOSES a grass-NPP LEVEL undershoot the soft floor
was masking.** All committed knobs are opt-in / grass-gated ⇒ every validated tree path is byte-identical.
(Report §26; CHANGELOG "Changed".)

- **★ REFUTED — the §25 hard-floor lever `max(0,agd)`.** Applied grass-gated it drives deep-shade grass NPP
  NEGATIVE (patches 3/4/18: −98 / −14 / −30 gC/m²/yr) and extincts 18/25 patches self-driven. Root cause:
  flooring the DEMAND `gpd→0` collapses `fac`, so the fixed-graph λ-solve returns a degenerate low λ that
  suppresses `agd` while `rd` stays normal ⇒ `agd−rd ≪ 0`. A hard GPP floor is the WRONG mechanism.
- **★ COMMITTED FIX — a grass photosynthesis DEMAND-GATE** (`WaterParams.grass_demand_gate`, opt-in): the C
  skips photosynthesis when `gpd≤1e-5` (`water_stressed.c:196` ⇒ `agd=0`, no leaf resp) and scales `mresp·phen`
  (`npp_grass.c`; F_diff already matches this). A smooth `stable_sigmoid(βgpd_gate·(gpd−1e-5))` multiplies grass
  GPP AND `rd`, zeroing both as demand→0 while the λ-solve keeps the bounded soft-`βflux` `fac` (no degeneracy).
  Deep-shade grass NPP positive-and-suppressed, shade count 0/4 → 4/4, no negatives. Replaces the refuted
  `βflux_grass`. Grass-gated ⇒ trees byte-identical; opt-in default off ⇒ byte-identical.
- **★ THE GATE EXPOSES THE TRUE RESIDUAL.** With the faithful gate the matched-structure grass NPP is aggregate
  **0.83× the C** (median 0.48×); the §25 "1.13×" was inflated by the soft `softplus` floor producing grass GPP
  on the sub-threshold (`gpd≤1e-5`) days the C GATES OFF. The real residual is a grass-NPP LEVEL gap on the
  ABOVE-threshold days (corr unchanged ~0.973 — ranking right, level low). **This is the corrected next step.**
- **★ ESTABLISHMENT is NECESSARY (committed opt-in `grass_estab`).** `establishment_grass.c` individual mode
  (`est_pft=(1−fpc_total)/n_est`, `leaf+=sapl.leaf·est_pft`): without it the gated grass extincts 17–18/25
  patches; with it 0 extinct. `GrassEstabParams`/`grass_estabparams`/`_treepools_fpc`, grass-only.
- **★ `:exp` forest-floor light NOT adopted** (committed inert): with the gate it drives deep-shade grass NPP
  negative again (leaf-on-but-demand-gated days pay root maintenance); `:linear` retained.
- **★ SUITE + gate.** Full suite 26200 pass / 4 broken (26183 baseline + the §26 gate) (byte-identical defaults, Enzyme
  canopy path intact). New gate "Grass demand-gate + establishment — §26 faithful deep-shade balance; trees
  byte-identical" (`grass_structure_tests.jl`). SLURM 1537797/1537804/1537815/1537816/1537834/1537853.

---

## ⭐ WHAT LANDED IN SESSION 20 (on `main`) — GRASS-OVERSHOOT RE-DIAGNOSIS #3 + FIX: THE §24 "CARBON BALANCE" IS per-PFT grass PHENOLOGY, NOW WIRED INTO THE COUPLED ROLLOUT (scale-up step 11 follow-up #2)

**§24's corrected next step ("a light-limited grass carbon balance, pinned with a light- vs
conductance-limitation decomposition") is executed. The lever is not a carbon-balance / conductance /
respiration parameter — it is per-PFT grass PHENOLOGY, which the coupled rollout was not using.** Five committed
SLURM decomposition probes on the Hainich 2008 reference pin it; the dominant, clean, faithful lever is
committed, the interacting remainder is a pinned co-calibrated next step. (Report §25; CHANGELOG "Changed".)

- **★ COMMITTED FIX — per-PFT grass phenology in `rollout_canopy_years`.** A `pft_ids` kwarg (default grass→8 /
  tree→3) is passed to `rollout_daily_canopy`, so each individual runs its own PFT's GSI. A grass drives its
  light limiter with the tree-attenuated forest-floor light ⇒ a shaded understory grass is leaf-on far less than
  the canopy trees (the FIT `new_phenology:true`). `per_pft_phenology` existed since §19 but was only in
  `rollout_daily_canopy`. **Matched-structure grass NPP overshoot (grass at the C's 2008 leaf, trees fixed,
  matched fpar): 4.26 → 1.13×, corr 0.929 → 0.973** (`scripts/grass_phen_probe.jl`).
- **★ TREE PATHS BYTE-IDENTICAL.** `pft_phenparams(3) === tebs_phenparams` (beech GSI), so the id-3 tree
  leaf-display is unchanged; the tree-only coupled-rollout gates + every tree baseline are unchanged (full suite
  **26174 pass / 0 fail / 4 broken**); the decadal tree-GPP validation (§21) uses `rollout_canopy_years_gpp`
  with SUPPLIED phen, untouched. In a MIXED tree+grass patch the trees shift < 0.4 % — the now-lighter grass
  leaves more soil water / stand conductance for the trees (the C's tree↔grass competition, physically correct;
  only in the grass/mixed coupled rollout, not any validated tree path).
- **★ RULED OUT (5 probes).** The softplus GPP floor is the DEEP-SHADE lever only (necessary, not sufficient);
  the `gc·fpc − gmin·fpar` demand is byte-faithful to `water_stressed.c:194`; grass `gmin` is inert; the grass
  GPP-per-absorbed-light == the validated trees' and grass CUE == the trees' (`npp_grass.c` respiration matched,
  `respcoeff`/`cn_root` ≈ F_diff's). So NOT per-PFT conductance (§21), NOT cover competition (§22), NOT
  carbon-balance / respiration / photosynthesis-params (§24).
- **★ CO-CALIBRATED NEXT STEP (NOT committed; the levers interact).** Grass-gated hard floor `max(0,agd)` +
  grass GSI light-limiter season calibration + grass establishment/re-seeding — see the NEXT section below.

---

## ⭐ WHAT LANDED IN SESSION 19 (on `main`) — GRASS-OVERSHOOT RE-DIAGNOSIS #2: THE §22 COVER-COMPETITION NEXT STEP TARGETS AN INACTIVE CODE PATH (scale-up step 11 follow-up)

**§22's corrected next step is itself wrong — this session proves it and re-points the roadmap at the true
fix.** §22 (session 17) refuted the §21 per-PFT-conductance step and set the next step as porting the LPJmL grass
cover/light competition (`light.c`→`light_grass.c`→`fpc_grass.c`). Reading the ACTUALLY-ACTIVE FIT code path +
a per-patch SLURM reproduction shows that port targets a code path the FIT config never runs, and the real
overshoot is a light-limited **carbon-balance** gap, not a missing cover cap. No physics change (as §22): the
deliverable is the corrected diagnosis, its two committed reproductions, and the roadmap correction. (Report §24;
CHANGELOG.)

- **★ FINDING 1 — `light()`/`light_grass()` are NEVER called in the FIT config (`"individual":true`).**
  `annual_natural.c:117` gates the entire cover-competition call behind `if(!config->individual)`. The
  individual-mode grass cover reduction is `establishmentpft_ind.c:168-176` → `reduce_grass()` = **only**
  `pft->fpc /= factor` (`reduce_grass.c`; `Litter*`/`Config*` args `UNUSED` — no carbon killed), gated on
  **total** patch cover `fpc_total > 1` — which never fires at Hainich (tree+grass FPC < 1, e.g. patch 0:
  0.44 + 0.07 = 0.51). So porting `light_grass.c` carbon-killing adds a mechanism the C does not run — the same
  class of error §22 caught in §21. The C's grass here is bounded by the **light-limited carbon balance alone**.
- **★ FINDING 2 — the C's grass leaf is a smooth monotone function of forest-floor light** (0.011 → 215 gC/m²
  across the 25 patches; shaded `plai≈4` → grass ≈ 0.01, open `plai≈1.4` → grass ≈ 215), satisfying the
  steady-state balance **NPP ≈ 1.8·leaf** at *every* patch — the carbon-balance fingerprint, no hard cap.
- **★ FINDING 3 — F_diff genuinely OVERSHOOTS even with trees fixed at the C's structure** (Exp A, identical
  forest-floor light; `scripts/grass_cover_mechanism_diagnosis.jl`, SLURM 1534524): grass leaf median **92.5
  (50–194)** vs C **6.5 (0.011–215)**, median ratio **×13.87**, deep-shade patches ×100–6900, cross-patch corr
  **0.57**. Compressed + light-insensitive (not the §22-repro setup artifact, not tree-growth).
- **★ FINDING 4 — the mechanism is an under-light-limited grass NPP, ~2–3× the C at matched absorbed light.**
  F_diff's grass fpar reproduces the C's `fpar_leafon` (patch 15: 0.0304 vs 0.03042, the §20 match) — light
  *absorption* is faithful; the gap is GPP/NPP per absorbed light. `scripts/grass_lightbalance_probe.jl`
  (SLURM 1534531): in shaded patch 3 (floor 0.14, C grass extinct at NPP 0.005) F_diff makes NPP **2.94** even
  at leaf 0.01 (fapar 5e-5), and its low-leaf NPP is ≈ the same in a shaded vs a bright patch — a light-insensitive
  floor. Through the turnover balance this ~2–3× surplus becomes the extinct-vs-thriving divergence. **Vindicates
  session 15's "~3× NPP" as a per-patch fact; §22's "0.83×" was a cell-total ratio dominated by the few high-leaf
  patches, masking it.**
- **★ RULED OUT.** Grass photosynthesis params are NOT the fix — grass `temp_photos` 10/30 vs beech 20/30 would
  *raise* NPP at cool Hainich temps; `albedo_leaf` 0.23 vs 0.15 is a ~9 % trim (consistent with §22).
- **★ REPRODUCTIONS** (both committed, self-checking `@assert`s, SLURM, `--project=.`): verified job 1534549
  (MECH_OK: median Exp A/C > 5, corr < 0.75, ≥1 patch > 100×; PROBE_OK: the light-insensitive NPP floor).

---

## ⭐ WHAT LANDED IN SESSION 17 (on `main`) — GRASS-OVERSHOOT RE-DIAGNOSIS: PER-PFT CONDUCTANCE IS REFUTED (scale-up step 11)

**The handoff's own first-listed next step (per-PFT/per-individual canopy conductance) was wrong — this
session proves it and corrects the roadmap.** Session 16's §21 diagnosed the §20 self-driven grass-NPP
overshoot (~3×) as the shared stand-mean `gp_stand` "over-supplying the understory grass" and set per-PFT
conductance as the fix. Reading the LPJmL-FIT C source (`water_stressed.c`, `gp_sum.c`, `daily_natural.c`,
`npp_grass.c`) surfaced a contradiction — the C's *returned GPP* uses `gp_stand` too — so I re-diagnosed from
the source **and** a faithful instrumented reproduction on the committed Hainich 2010 cell, then
adversarially verified with four independent lenses (all confirming). No physics change: the deliverable is
the corrected diagnosis, its gate, and the roadmap correction. (Report §22; CHANGELOG.)

- **★ FINDING 1 — the C's returned GPP uses `gp_stand`, so per-PFT-GPP-conductance is LESS faithful.** In
  `water_stressed.c` the returned assimilation is driven by `gc` (line 194), set from the STAND mean
  `gp_stand` (line 181, and the water-limited else-branch uses the `gp_stand`-based `demand` of line 118). The
  per-PFT `gp_pft`/`demand_pft`/`gc_pft` are diagnostic-only (`gc_pft` is write-only, consumed solely by
  `PFT_GCGP`, `daily_natural.c:187`; the one per-PFT-*supply* path into GPP is the `nitrogen_coupled` branch,
  **off** in the carbon-only FIT config). F_diff already mirrors the C (one shared `gp_stand` for every
  individual, `fdiff.jl:1497/1515`).
- **★ FINDING 2 — F_diff's grass GPP already uses `gp_stand` (like the C); per-PFT would DE-calibrate it.**
  `canopy_conductance` returns `gc = smoothmin(gc_w(supply_i), gp_stand)`. Instrumented on the committed 2010
  cell (state advanced by the REAL `daily_step_canopy`), the grass's actual `gc_grass ≈ 0.75·gp_stand` — the
  moist Hainich soil (growing-season `wscal ≈ 0.99`, min 0.85) keeps it only mildly water-limited, so it uses
  MOST of the stand mean, exactly as the C's `water_stressed.c` returns grass GPP from `gp_stand`. The grass's
  OWN potential `gp` is only ~0.14·`gp_stand`, so a per-PFT (own-`gp`) conductance would change the grass GPP
  **~43 %** — a large de-calibration AWAY from the C-faithful value. So per-PFT conductance is the WRONG lever
  (it would cut the grass GPP and move the validated tree GPP too). *(An initial reproduction reported a
  spurious `0.13·gp_stand` "water-limited" figure — a hand-rolled soil-evolution bug; the real path keeps the
  soil moist, verified against `rollout_daily_canopy`.)*
- **★ FINDING 3 — the per-year grass NPP is FAITHFUL at fixed structure; the "3×" is a MULTI-YEAR
  over-growth.** With the grass at the C's OWN structure (real leaf/root carbon → real maintenance
  respiration), total grass NPP is **0.83×** the C (a mild UNDERshoot; ind-CSV `gpp_ind` is the C NPP),
  `fpar` matches. The "3×" is a multi-year structural-feedback over-growth (leaf → LAI → forest-floor `fpar`
  → NPP), unbounded because F_diff lacks the C's grass **cover/light competition** (`light.c` →
  `light_grass.c` caps grass FPC at `1 − tree cover` and kills excess leaf/root to litter).
- **★ CORRECTED NEXT STEP.** Grass **cover/light competition** (`light.c` → `light_grass.c` → `fpc_grass.c`),
  optionally with the supply-side per-layer soil-water competition (`water_stressed.c:153-179`) — **NOT**
  per-PFT conductance. Grass-specific photosynthesis params (temp-opt 10/30, `alphaa` 0.5, `albedo_leaf` 0.23,
  `k_beer` 0.5) are a faithful minor improvement (grass NPP 0.83 → 0.90) but do not touch the runaway.
- **★ REPRODUCTION `scripts/grass_overshoot_diagnosis.jl`** (self-contained on the committed 2010/2008
  reference; run off the login node via SLURM — verified job 1530883 COMPLETED) reproduces + asserts all three:
  per-year NPP faithful (ratio ∈ [0.6, 1.3], measured 0.832); grass GPP uses the stand mean (`mean gc/gp_stand
  > 0.5`, measured 0.751; own `gp` 0.138·`gp_stand`) + per-PFT would change grass GPP `> 0.2` (measured 0.427);
  self-driven grass over-grows > 2× (leaf 6.4 → 160, ×25 over 11 yr). It is a **script, not a CI `@testitem`,
  by design**: the heavy per-cell conductance instrumentation, added to the parallel ReTestItems pool, tripped
  a pre-existing Enzyme-0.13/Julia-1.10-`lts` `LLVM error: Canonicalization failed` in the unrelated
  Enzyme-reverse canopy testitems (see Housekeeping). Runtime `[deps]` stays EMPTY.

---

## ⭐ WHAT LANDED IN SESSION 16 (on `main`) — DECADAL (11-YEAR) FIDELITY OF THE COUPLED MULTI-YEAR ROLLOUT (scale-up step 10)

**The coupled multi-year rollout is validated over a full decade for the first time.** §18 validated the
cell × multi-year objective over 3 years (2009–2011); this extends the committed real reference to 2009–2019
and shows the self-driven structure stays faithful to the C over 11 years. Plus two decisive diagnoses that
re-scope the roadmap. (Report §21; CHANGELOG.)

- **★ THE DECADAL REFERENCE (committed, no C re-run).** `scripts/extract_fdiff_decadal.py` slices
  `hainich_decadal_forcing.csv` + `hainich_decadal_targets.csv` (2009–2019 per-year daily forcing + per-year
  daily C GPP/FAPAR) from the full-period single-cell daily CSV already on disk, reusing the committed 2008
  start structure. CI-runnable (no `/p/tmp` at test time).
- **★ RESULT — fidelity-stable over the decade.** Starting from the 2008 reconstructed 25-patch structure and
  self-driving 11 years (kernel-isolation C-FAPAR phenology, each patch grown by its own pipe-model
  allocation): **mean cell-mean annual-GPP ratio 1.066** (F_diff's inherited ~+7 % GPP-phenology level,
  §13/§19), **each year bounded 1.01–1.11** (a mild mid-decade drift ~1.11 at 2015–2017 that recovers by
  2019, **no runaway** — cell GPP stays 1118–1401 gC·m⁻²·yr⁻¹), and **interannual r = 0.86** with the C's
  year-to-year variability (mirrors the C's high years 2011/2014/2018/2019 and low years 2010/2013). The level
  bias does NOT compound into a drift; the self-driven structure neither collapses nor blows up.
- **★ GATE `decadal_validation_tests.jl`** (self-contained on the committed decadal reference): the 25-patch
  rollout runs the full 11 years + stays physical (finite/positive/bounded per-year GPP); mean ratio ≤ 1.12;
  each year 0.9–1.2; per-year correlation with the C > 0.7 (measured 0.86). Runtime `[deps]` stays EMPTY.
- **★ FINDING 1 (deferred) — grass-NPP calibration is STRUCTURAL.** Decomposed the §20 self-driven grass
  overshoot (~3×): carbon-only run (`with_nitrogen:"no"` — N ruled out); grass fPAR matches the C exactly
  (0.03042 vs 0.0304233 — open-field light ruled out); grass light-limited, water-insensitive (shared-water
  ruled out); grass root C:N (30) + respcoeff (1.2) = beech (respiration ruled out). The residual is the
  **shared stand-mean conductance** (`gp_stand`) over-supplying the understory grass — a faithful fix needs
  **per-PFT/per-individual conductance** (structural, would move the validated tree transp/GPP), the new
  first-listed NEXT.
- **★ FINDING 2 (deferred) — the Enzyme-≥1.11 guard-lift is BLOCKED upstream.** Probed on Julia 1.11.7 with
  the LATEST Enzyme 0.13.187: forward fine, but the reverse through the mutating canopy path still raises
  `Enzyme.Compiler.EnzymeInternalError`. The `VERSION < 1.11` guards cannot be lifted by a 0.13.x bump —
  upstream-Enzyme / a higher-risk 0.14 migration (Lux/code pin 0.13).

---

## ⭐ WHAT LANDED IN SESSION 15 (on `main`) — PROGNOSTIC GRASS STRUCTURE: THE `allocation_grass.c` PORT (scale-up step 9)

**The handoff's first-listed NEXT landed:** grass leaf/root carbon are now prognostic — a faithful,
differentiable, AD-safe port of the LPJmL-FIT NATURAL-veg annual grass carbon allocation
(`turnover_grass.c` → `allocation_grass.c`), essential for running F_diff on grasslands (where trees are
absent entirely). (Report §20; CHANGELOG.)

- **★ THE GAP.** Through §19 the multi-year rollout grew only trees; grass was held fixed by `grow_individual`
  AND structurally dropped: the `ind`-output reconstruction gives grass rows `leaf_c = crownarea = nind = 0`
  (grass is a per-**area** cohort, carried via `lai`/`fpc`/`fpar`, not per-individual-count), so a round-trip
  through `individual_from_pools`/`_patch_fpars_soa` (which derive structure from those zeros) produced a dead
  grass cohort — every multi-year test filtered grass out (`type ≤ 6`).
- **★ THE PORT (`grow_grass_individual`).** Closed-form carbon math: leaf turns over daily + root monthly
  (annual pool `→ pool·(1 − rate)`, `turnover_daily_grass.c`/`turnover_monthly_grass.c`); reproduction reserve
  removed before allocation; natural-veg full-reallocation partitions `bm_net` at `lmtorm = lmro_ratio·
  (lmro_offset + (1 − lmro_offset)·min(1, wscal))` with the no-reallocation caps + the negative-leaf branch
  (`allocation_grass.c:87-118`). `grass_allocparams` = temperate C3 grass (id 8) verbatim from the active
  `par/pft_lpjmlfit.js` (`lmro_ratio 0.8`, `lmro_offset 0.5`, leaf rate 1.0, root rate 0.5 after the
  `fscanpft_grass.c:124` reciprocal, `reprod_cost 0.1`).
- **★ THE PER-AREA CONVENTION (`grass_treepools`).** Reconstructs grass from the two grass columns the `ind`
  output carries: leaf = `agb` (`agb_grass.c:25`), root = `vegc − agb`; sets `crownarea = nind = 1` so
  `lai = leaf_c·sla` and `fpc = 1 − e^{−k·lai}`. **With this convention NO change to
  `individual_from_pools`/`_patch_fpars_soa` was needed** — the grass `fpar` recompute reproduces the C to
  5 s.f. (0.03042 vs 0.0304233). Wired into `rollout_canopy_years`/`rollout_canopy_years_gpp` via a `galloc`
  kwarg; the grass branch fires only for `is_grass`, so all TREE baselines + the Enzyme trainer are
  **byte-identical**.
- **★ ALLOCATION FAITHFULNESS (the deliverable, gate-verified).** Golden vs `allocation_grass.c` across every
  branch (positive/zero/negative bm; the negative-leaf reallocation) **< 1e-5**; carbon conservation
  Δ(leaf+root) = bm_net − turnover **4.4e-16**; fed the C's Hainich grass NPP (patch-15 `npp = 10.73`) from a
  cold start the grass equilibrates to leaf:root **0.791 vs the C's 6.406/8.023 = 0.799** (within 3 %,
  magnitudes ~8 %) — the `bm_inc_ext` crutch, exactly as the TREE allocation was validated (§12) before its
  self-NPP was calibrated (§13).
- **★ THE HONEST FINDING — the self-computed grass NPP is uncalibrated (~3×).** With the pools live the grass
  gets its per-m² respiration (`nind = 1`) but still the **beech** photosynthesis/respiration params, so
  F_diff's self-computed grass NPP at the C structure is **31.8 vs the C's 10.7** and a self-driven grass
  overshoots (leaf 6.4 → ~48, lai 0.27 → 2.0 over 8 yr). Precisely the tree story — the grass ALLOCATION is
  the deliverable; the grass-NPP calibration is the documented NEXT (see below). Until then, grass-inclusive
  multi-year runs should drive grass with the C's grass NPP crutch.
- **★ GATE `grass_structure_tests.jl`** (5 self-contained testitems): param fidelity + reconstruction; golden
  vs C + conservation + bounds; equilibrium-fed-C-NPP → C structure; ForwardDiff (scalar + d(ΣGPP)/d(α_c3)
  through the coupled multi-year grass-inclusive rollout, AD=FD=6020.82) vs FiniteDifferences; Enzyme reverse
  through the grass-inclusive multi-year path (grad vs FD `rtol 1e-4`, guarded `VERSION < 1.11`). Suite
  **26,166 pass / 0 fail / 4 broken**; Runic-clean; adversarially verified. Runtime `[deps]` stays EMPTY.

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
   **(grass-structure) ✅ DONE (session 15) — prognostic grass structure: the `allocation_grass.c` port
   (scale-up step 9).** Grass leaf/root carbon are now prognostic via a faithful differentiable port of the
   NATURAL-veg annual grass sequence `turnover_grass.c`→`allocation_grass.c`: `grow_grass_individual` +
   `grass_allocparams` (temperate C3 grass id 8 verbatim from `par/pft_lpjmlfit.js`) + `grass_treepools(agb,
   vegc, sla)` (per-area convention leaf=agb/root=vegc−agb/`crownarea=nind=1` ⇒ the existing `fpar`/`fpc`
   recompute reproduces the C exactly, no change needed to `individual_from_pools`/`_patch_fpars_soa`); wired
   into both rollouts via a `galloc` kwarg (grass branch fires only for `is_grass` ⇒ every TREE baseline + the
   Enzyme trainer byte-identical). **Allocation faithful (golden < 1e-5, conservation 4.4e-16, fed the C's
   grass NPP the grass equilibrates to leaf:root 0.791 vs the C's 0.799).** **Self-computed grass NPP ~3× the
   C's (grass shares the beech photosynthesis/respiration params) — a self-driven grass overshoots** (the
   documented next step, below). Gate `grass_structure_tests.jl` (5 testitems incl. ForwardDiff + Enzyme
   through the grass-inclusive multi-year rollout); suite 26,166 pass / 0 fail / 4 broken; adversarially
   verified. §20; CHANGELOG.
   **(decadal-validation) ✅ DONE (session 16) — DECADAL (11-year) fidelity of the coupled multi-year rollout
   + two diagnosed frontier items (scale-up step 10).** Extended the committed real reference to 2009–2019
   (`scripts/extract_fdiff_decadal.py`, sliced from the on-disk daily CSV — no C re-run). The 25-patch rollout,
   self-driving 11 years from the 2008 structure (kernel-isolation C-FAPAR phen), tracks the C: **mean ratio
   1.066, each year 1.01–1.11 (no runaway), interannual r = 0.86** — fidelity-stable over a decade. Gate
   `decadal_validation_tests.jl`. **Also diagnosed + deferred two frontier items:** (a) the §20 grass-NPP
   overshoot is STRUCTURAL — carbon-only run, grass fPAR matches the C, light-limited, root C:N/respcoeff =
   beech; the residual is the shared stand-mean conductance (`gp_stand`), so it needs per-PFT conductance not a
   param fix; (b) the Enzyme-≥1.11 guard-lift is BLOCKED upstream (latest Enzyme 0.13.187 still
   `EnzymeInternalError` on 1.11.7). §21; CHANGELOG.
   **(grass-rediagnosis) ✅ DONE (session 17) — the §21 per-PFT-conductance next step is REFUTED; roadmap
   corrected (scale-up step 11).** Re-diagnosed the §20 self-driven grass-NPP overshoot from the C source +
   a faithful reproduction on the committed Hainich 2010 cell (adversarially verified — 4 independent lenses,
   all confirming). Three findings: (1) the C's returned GPP uses `gp_stand` for EVERY natural PFT incl. grass
   (the per-PFT `gp_pft`/`gc_pft` feed ONLY the `PFT_GCGP` diagnostic, `daily_natural.c:187`), so a per-PFT
   GPP conductance is LESS faithful, not more; (2) F_diff's grass GPP ALREADY uses `gp_stand` (measured
   `gc_grass ≈ 0.75·gp_stand`; moist Hainich soil, `wscal ≈ 0.99`) — like the C — and its own `gp` is only
   ~0.14·`gp_stand`, so per-PFT conductance would change the grass GPP ~43 %, a large DE-calibration; (3) at
   the C's OWN structure the per-year grass NPP is FAITHFUL (total 0.83×, `fpar` matches), so the "3×" is a
   MULTI-YEAR structural-feedback over-growth
   (leaf → LAI → forest-floor `fpar` → NPP), unbounded because F_diff lacks the C's grass COVER/LIGHT
   competition (`light.c` → `light_grass.c` kills excess grass leaf/root back to the permitted cover). Gate
   reproduction `scripts/grass_overshoot_diagnosis.jl`. §22; CHANGELOG. **[SUPERSEDED by session 19 / §24 —
   the cited `light.c`→`light_grass.c` path is INACTIVE in the FIT config (`individual:true`); see below.]**
   **(grass-rediagnosis-2) ✅ DONE (session 19) — §22's cover-competition next step targets an INACTIVE code
   path; the real gap is a light-limited grass carbon balance (scale-up step 11 follow-up).** In the FIT config
   (`"individual":true`, `lpjmlfit.js:34`) `annual_natural.c:117` gates `light()` behind `if(!config->individual)`
   — so `light()`/`light_grass()` are NEVER called; the individual-mode cover reduction is `reduce_grass`
   (fpc-only, no carbon killed, gated on total cover > 1, which is < 1 at Hainich). So the §22 port would add a
   non-faithful mechanism — the same class of error §22 caught in §21. Per-patch SLURM reproduction (trees FIXED
   at the C structure): grass leaf median 92.5 (50–194) vs C 6.5 (0.011–215), median ratio ×13.9, cross-patch
   corr 0.57 — a REAL, structural overshoot. Mechanism: an under-light-limited grass NPP ~2–3× the C at matched
   absorbed light (grass fpar reproduces the C's `fpar_leafon`; the gap is GPP/NPP per absorbed light — a
   light-insensitive NPP floor ~2.9 gC/m²/yr). Vindicates session 15's "~3× NPP" as a per-patch fact; §22's
   "0.83×" was a cell-total masking it. Reproductions `scripts/grass_cover_mechanism_diagnosis.jl` +
   `scripts/grass_lightbalance_probe.jl`. §24; CHANGELOG.
   **(grass-rediagnosis-3) ✅ DONE (session 20) — the §24 "carbon balance" is per-PFT grass PHENOLOGY
   (dominant), wired into the coupled rollout; conductance / respiration / params RULED OUT (scale-up step 11
   follow-up #2).** Five SLURM decomposition probes pinned the lever. The softplus GPP floor is the DEEP-SHADE
   lever only; the `gc·fpc − gmin·fpar` demand is byte-faithful to `water_stressed.c:194`; grass `gmin` inert;
   the grass GPP-per-absorbed-light == the validated trees' and grass CUE == the trees' — so GPP-per-light and
   respiration are faithful. The BROAD overshoot is that `rollout_canopy_years` applied the patch-wide BEECH GSI
   phenology to the understory grass instead of the grass's own light-limited per-PFT GSI. **COMMITTED:** a
   `pft_ids` kwarg on `rollout_canopy_years` (grass→8 / tree→3) ⇒ matched-structure grass NPP overshoot
   4.26 → 1.13×, corr 0.929 → 0.973; tree paths byte-identical (suite 26174/0/4). Report §25; CHANGELOG.
   `scripts/grass_lightconductance_decomp.jl` + `..._carbonbalance_probe.jl` + `..._phen_probe.jl`.
   **(grass-rediagnosis-4 / co-calibration) ✅ DONE (session 22) — the §25 hard-floor lever is REFUTED; the
   faithful mechanism is the C's photosynthesis DEMAND-GATE, committed opt-in.** The co-calibration probe
   (`scripts/grass_cocalibration_probe.jl`) showed a grass-gated hard `max(0,agd)` drives deep-shade grass NPP
   NEGATIVE (flooring the DEMAND collapses `fac` → degenerate λ → `agd−rd≪0`); the C instead GATES photosynthesis
   on `gpd>1e-5` (`water_stressed.c:196`) + scales `mresp·phen` (already matched). Committed: the grass demand-gate
   (`WaterParams.grass_demand_gate`), grass establishment (`grass_estab`), the `:exp` mode (inert) — see the
   session-22 landing log above. Docs §26.

   **(§26 follow-up) ✅ DONE (session 22) — the level gap is NOT the grass temp/albedo params** (`scripts/grass_npp_level_probe.jl`,
   SLURM 1540628). The grass probes built the grass `Individual` with BEECH photo params (§15 v1 simplification):
   `temp_photos` 20/30, `albedo_leaf` 0.15. The ACTIVE grass id 8 has `temp_photos {10,30}` (lower optimum ⇒ RAISES
   cool-temp NPP: matched-structure agg F/C 0.833 → 0.901, gate ON) and `albedo_leaf 0.23` (⇒ LESS absorbed PAR ⇒
   LOWERS GPP → 0.757). **Together ≈ 0.82 — the two nearly CANCEL, so the ~18 % undershoot PERSISTS** (corr ~0.975).
   So temp/albedo are ruled out; the faithful grass `temp_photos {10,30}` + `albedo_leaf 0.23` remain a fidelity
   improvement for a canonical grass-`Individual` builder but don't close the level.

   **(§26 follow-up #2) ✅ DONE (session 23) — the "C re-run" is really a C RECOMPILE; the residual is
   parameter-faithful + SEASON-shaped, NOT the forest-floor light or the GSI cold-start (docs §26.1).** No physics
   change; corrected diagnosis + roadmap + two committed SLURM reproductions
   (`scripts/grass_npp_light_response_probe.jl` 1540816, `scripts/grass_gsi_warmstart_probe.jl` 1540819).
   (1) LPJmL-FIT has **NO per-PFT/individual DAILY GPP output** (`par/outputvars.js`: only annual `PFT_NPP`/`ind`
   + cell-total `d_gpp`/`d_npp`) ⇒ "extract per-PFT daily GPP" is impossible and a config-only re-run can't make
   it — it needs a C-SOURCE change + RECOMPILE (a NEW class of work). (2) Source audit: the grass photosynthesis
   KERNEL is byte-faithful (co-limitation the EXACT quadratic `photosynthesis.c:150`==`fdiff.jl:431`), `apar`
   validated (§20), and grass id 8 respiration params (`respcoeff 1.2`, `cn_ratio.root CTON_ROOT`, `ratio.root
   1.16`) are LITERALLY beech's ⇒ CUE faithful; the ~18 % gap is not a parameter. (3) The undershoot is
   **gate-independent, ABOVE-threshold, tracks the grass ACTIVE-DAY fraction, growing with shade** (brightest-half
   agg F/C 0.861; per-patch 0.86@ff0.50 → 0.57@ff0.29; active-day frac 0.66→0.30) — a season-shape residual, not
   GPP-per-active-leaf. (4) the faithful `:exp` forest-floor light is **REFUTED** as the fix (brightest-half F/C
   0.861→0.755, 7 deep-shade negatives — refutes §26 F6's deferred `:exp` lever). (5) the grass GSI **cold-start is
   REFUTED** (5-yr continuous warm-up: year 1 == year 5 to every digit).

   **(§26.2) ✅ DONE (session 24) — BUILT the C's daily grass GPP/NPP output; F_diff's grass is FAITHFUL; the
   §26/§26.1 "level gap" was a REFERENCE-BASIS ARTIFACT. The grass-NPP thread (§20→§26.2) is CLOSED.** The user
   directed "MAKE IT", so the LPJmL-FIT C binary was MODIFIED + REBUILT to emit the missing daily grass flux:
   two scalar daily outputs `D_GRASS_GPP`/`D_GRASS_NPP` (`conf.h` 419/420, cell-mean per-day write in
   `daily_natural.c` beside `GPP`/`NPP`, explicit flush in `fwriteoutput.c`, `outputvars.js`) — 18 ins/1 del,
   `patches/lpjmlfit_daily_grass_gpp.patch` (+ a `json_object_iterator.h` shim for the cluster's truncated
   json-c/0.13.1 headers). Re-ran Hainich 2000–2019. **Comparing F_diff's cell-mean daily grass NPP (matched
   2008 structure, faithful params, demand-gate ON) to the C's OWN daily grass NPP over 2009–2019: aggregate
   ΣF/ΣC = 0.95, mean per-year F/C = 0.98 (range 0.72–1.19, NO systematic bias), season length faithful
   (actR 1.02), amplitude faithful (ampR 0.96), daily r ≈ 0.86.** The §26/§26.1 "0.82×" was measuring F_diff
   (run on 2009 forcing) against the C's 2008 `ind`-output NPP — a year/basis mismatch (C grass NPP swings 28–51
   gC/m²/yr year-to-year). No F_diff physics change; the demand-gate + faithful grass params (§26/§26.1) make it
   faithful. Committed: the patch, `test/testitems/references/hainich_grass_daily_2009_2019.csv`, and scripts
   `run_fdiff_grass_gpp_cell.sh`/`extract_fdiff_grass_daily.py`/`grass_daily_curve_fdiff.jl`/
   `compare_grass_daily_c_vs_fdiff.py`. Report §26.2. **The rebuilt FIT binary at `/home/jamirp/lpjml56fit/bin/lpjml`
   now emits daily grass GPP/NPP** (pristine pre-change binary backed up at `bin/lpjml.pre_dgrass.bak`).

   **★ NEXT (session 24): the grass thread is CLOSED — move to other frontier items.** The grass GPP/NPP is
   validated faithful; NOT a hard GPP floor (§26 F1), NOT `:exp` light (§26 F6 + §26.1 F4), NOT temp/albedo
   (§26 fu#1), NOT respcoeff/CN (§26.1 F2), NOT GSI cold-start (§26.1 F5), NOT per-PFT conductance (§22) / cover
   competition (§24) / respiration-CUE (§25). Optional grass refinements (low priority): (a) feed F_diff the C's
   per-year grass structure (from the on-disk `ind` parquet) to tighten the 0.72–1.19 year-to-year F/C scatter;
   (b) flip the demand-gate + establishment to the coupled-rollout DEFAULT, validated against
   `hainich_grass_daily_2009_2019.csv` (+ check the steep demand-gate Enzyme gradient). The real frontier:
   below-ground root-sapwood (`sapwood_bg`) + carbon-debt
   (**scouted: a GENUINE SEPARATE carbon pool, `tree.h:50`, NOT a fraction of the sapwood pool — needs the
   per-soil-layer lateral-root-sapwood demand `root_sapwood_layer` (`allocation_tree.c:160-209`, so soil layers
   must reach `grow_individual`) + its own turnover to `heartwood_bg` + maintenance respiration through the SoA
   rollout, touching every `TreePools` reconstruction site; higher AD risk**); whole-tree mortality/
   establishment (S's demography, so the coupled loop is not fixed-N); the **upstream-Enzyme-on-Julia-≥1.11
   guard-lift** (probed session 16 — still blocked on the latest 0.13.187; retry on a future Enzyme 0.14
   migration). Phenology-fidelity follow-ups: the per-individual `minwscal` corridor sampling (now → PFT
   median) and a canopy-consistent (non-lag) grass forest-floor light.
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
- **CI `test (lts)` red after step 11 → an Enzyme 0.13.189 REGRESSION; FIXED by pinning `Enzyme ≤ 0.13.188`
  (session 18; docs §23, CHANGELOG "Fixed").** The `test (lts)` (+ non-required `test (macOS, lts)`) failures
  with `LLVM error: Canonicalization failed` in `nn_canopy_training_tests.jl:22`/`:145` are a **moving-dependency
  regression**, NOT the test set. Bisected from the CI logs: the green `a6d6975` run resolved **Enzyme
  v0.13.188** and those canopy testitems PASSED; the next push `f65ca84` (~5 h later) resolved **v0.13.189** and
  they began erroring — with the test tree **byte-identical** (`git diff a6d6975 6514fd7 -- test/` empty). Since
  `test/Manifest.toml` is git-ignored, CI re-resolves each run and the wide `[compat] Enzyme = "0.13"` auto-upgraded
  188 → 189. **Fix = `Enzyme = "0.13.0 - 0.13.188"` in BOTH root + `test/Project.toml` `[compat]`** (last-good;
  0.13.189 is the latest published Enzyme, so no upstream fix yet). Verified: fresh resolve on Julia 1.10 → 0.13.188;
  full `Pkg.test()` green.
  - **This CORRECTS the earlier session-17 theory** (below) that the heavy grass `@testitem`s "poisoned" the
    parallel ReTestItems worker pool: reverting the test tree to `a6d6975` (`6514fd7`) left CI red with the
    identical error, so the worker-schedule hypothesis is refuted. `retries` (`f1cdad1`) also could not help — a
    deterministic compile-time error, not a flake. (Keeping the grass reproduction as a SLURM script rather than a
    `@testitem` is still fine — it keeps a heavy Enzyme compile out of CI — but it was never this failure's fix.)
  - **Lift the pin** when a fixed Enzyme ships (retry with the Enzyme-≥1.11 guard-lift TODO). Consider committing
    `test/Manifest.toml` so CI resolution is reproducible instead of silently picking up dependency patch bumps.
  - `test (pre)` is `continue-on-error` (allowed to fail); it errors for an UNRELATED Julia-prerelease `ScopedValue`
    API break (`setindex!(::ScopedValue, ::Bool)` at test-item scan) — not our code, left as-is.
  - _[superseded theory, kept for the record]_ Session 17 believed adding the grass re-diagnosis `@testitem`s
    shifted worker scheduling so a heavy Enzyme testitem cold-compiled on a "poisoned" worker. Refuted above.

## Commit history on `main` (recent)
_(this session 22 lands on top: feat(fdiff) grass-equilibrium CO-CALIBRATION — the §25 hard-floor lever is
REFUTED (a grass-gated `max(0,agd)` drives deep-shade grass NPP NEGATIVE: flooring the demand collapses `fac`
→ degenerate λ-solve → `agd−rd≪0`); the C's mechanism is a photosynthesis DEMAND-GATE (`water_stressed.c:196`
`gpd>1e-5`) + `mresp·phen` (already matched). Committed opt-in: the grass demand-gate (`WaterParams.grass_demand_gate`,
replacing the refuted `βflux_grass`), grass establishment (`grass_estab`/`GrassEstabParams`/`_treepools_fpc`),
the `:exp` mode (inert). The gate EXPOSES the true residual — faithfully-gated grass NPP is aggregate 0.83× the
C (the §25 1.13× was the soft-floor artifact on sub-threshold days). All opt-in/grass-gated ⇒ byte-identical
defaults (suite 26183 + the new §26 gate / 4 broken). Docs §26. `git log --oneline -8` for exact HEAD. Next:
close the above-threshold grass-NPP level gap; then flip to default vs a multi-year C grass reference.)_
`5f490d5` fix(ci) pin Enzyme ≤ 0.13.188 — 0.13.189 regressed the Enzyme-reverse canopy path (step 11 CI; §23) ·
`6514fd7`/`f1cdad1`/`f65ca84` step-11 grass re-diagnosis + CI churn (per-PFT conductance REFUTED; §22) ·
`e159724` feat(fdiff) DECADAL (11-year) fidelity validation of the coupled multi-year rollout — extended the
committed real reference to 2009–2019 (`extract_fdiff_decadal.py`, no C re-run); the 25-patch rollout
self-driving 11 years from the 2008 structure tracks the C at **mean ratio 1.066, each year 1.01–1.11 (no
runaway), interannual r = 0.86** (fidelity-stable over a decade). Gate `decadal_validation_tests.jl`. Also
diagnosed + deferred two frontier items: the §20 grass-NPP overshoot is STRUCTURAL (shared `gp_stand`
conductance, needs per-PFT conductance), and the Enzyme-≥1.11 guard-lift is BLOCKED upstream (latest 0.13.187
still `EnzymeInternalError`). Suite 26,174/0/4 (step 10) · `c16c0be` feat(fdiff) prognostic grass structure — the `allocation_grass.c` port (`grow_grass_individual`/
`grass_allocparams`/`grass_treepools`, per-area `crownarea=nind=1`), wired into both rollouts via a `galloc`
kwarg (grass branch fires only for `is_grass` ⇒ tree baselines + Enzyme trainer byte-identical); allocation
golden <1e-5, conservation 4.4e-16, fed the C's grass NPP the grass equilibrates to leaf:root 0.791 vs the
C's 0.799; self-computed grass NPP ~3× the C's (beech params) ⇒ grass-NPP calibration is the NEXT; suite
26,166/0/4 (step 9) · `c33b71d` feat(fdiff) per-PFT GSI leaf phenology + the beech-tmin correction (par/pft_lpjmlfit.js) —
scalar-or-vector `phen` in `daily_step_canopy` (scalar path byte-identical; Enzyme trainer untouched),
`pft_phenparams`/`per_pft_phenology`/`rollout_daily_canopy(;pft_ids)`; cell GPP ratio vs C 1.134→1.097,
daily r 0.988→0.993; suite 26,106/0/4 (step 8) · `2d3d92a` feat(fdiff) NN training on the CELL × MULTI-YEAR
objective vs the REAL C per-year annual GPP — §16 per-patch decomposition THROUGH §17 multi-year rollout +
`sbatch_train.sh` (step 7b-cell-multiyear) · `4956529` feat(fdiff) NN training THROUGH the multi-year
structure/allocation feedback — SoA fix for the Enzyme-typeable `rollout_canopy_years_gpp` (step 7b-multiyear)
· `433ccb9` feat(fdiff) NN training vs the REAL C-binary daily GPP on the full 25-patch cell + the λ lever
(step 7b-cell) · `e9b8212` fix(fdiff) make the Enzyme canopy path Julia-1.11-safe (CI test(1) fix-forward)
· `c68c5ea` feat(fdiff) NN training on the canopy path — Enzyme reverse (step 7b-canopy) · `3db1406`
feat(fdiff) gradient-based online rollout training — NN λ/Vcmax hooks + TBPTT (step 7b) · `7a76f45`
feat(fdiff) self-computed canopy NPP calibrated, bm_inc crutch removed (step 7a) · … ·
`8dcf55b` feat(fdiff) F_diff spike (#14 squash) · `bcb3ecb` feat(phase2) gate met · `da12c88`
feat(phase1) global daily dataset · `b3924c9` feat(phase1) water closure · `5bc93ef` docs(ADR 0013).
