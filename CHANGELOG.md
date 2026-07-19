# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Per-PFT GSI leaf phenology (Phase-3 scale-up step 8; docs §19).** Generalizes the self-computed leaf
  phenology (§11) from ONE beech GSI applied patch-wide to PER-PFT: the LPJmL-FIT config runs
  `phenology_gsi` for every natural PFT (`lpjmlfit.js` `"new_phenology":true` + `"individual":true`; the
  "evergreen"-named PFTs run the full four-limiter GSI, not static `phen≡1`), so each individual now gets
  its own PFT's leaf-display curve.
  - **`pft_phenparams(id, T)`** — the twelve GSI parameters (`tmin/tmax/light`·slope·base·tau + `wscal`)
    for each 0-based natural PFT id 0–9, verbatim from the ACTIVE `par/pft_lpjmlfit.js`. `wscal_base =
    minwscal_median·100` (the C's individual-mode water inflection, `phenology_gsi.c:64-66`, NOT the inert
    par-file `wscal.base`). `tebs_phenparams()` == `pft_phenparams(3)`.
  - **`per_pft_phenology(pft_ids, forcings; …)`** — standalone per-PFT driver (one `PhenState` per distinct
    PFT → per-day × per-individual leaf display); grasses (id ≥ 7) drive the light limiter with forest-floor
    light `grass_light_frac·swdown`.
  - **Per-individual `phen` wiring** — `daily_step_canopy`/`patch_albedo` accept `phen` as a scalar OR a
    per-individual vector (compile-time-dispatched `_phen_at`; the scalar path is **byte-identical**, so
    every committed baseline + the Enzyme trainer are untouched). `rollout_daily_canopy` gains a `pft_ids`
    kwarg co-solving per-PFT phenology with the stand water feedback + a lag-1 grass forest-floor light
    attenuation. The Enzyme multi-year training path keeps its scalar C-FAPAR phen (unchanged).
  - **Result (25-patch Hainich 2010):** per-PFT phenology moves the standalone cell GPP annual ratio vs the
    C **1.134 → 1.097** (closer to the C) with daily r improving **0.988 → 0.993**, driven by the minority
    the beech-patch-wide phen got wrong (evergreens hold winter leaves; grass understory is light-shaded).
  - **Gate `per_pft_phenology_tests.jl`** (self-contained): param fidelity vs `par/pft_lpjmlfit.js` (all
    ids 0–9); distinct/bounded/physically-ordered trajectories; scalar-vs-vector byte-identity (Δ = 0);
    per-PFT self-driven rollout closes water and reduces to the beech default on an all-beech patch.
  Runtime `[deps]` stays EMPTY.
- **NN training on the CELL × MULTI-YEAR objective against a REAL multi-year reference (Phase-3 scale-up
  step 7b-cell-multiyear; ADR 0016).** Composes §16 (cell) with §17 (multi-year): the learned Vcmax/λ
  correction is trained so the **cell-mean PER-YEAR annual GPP** matches the C binary's own per-year annual
  GPP over the full 25-patch Hainich cell, with **every patch grown across years** through the pipe-model
  allocation. §17's two flagged next steps — the cell-multi-year objective and a real multi-year reference —
  both land here.
  - **Cell × multi-year loss + trainer** `fdiff_cell_multiyear_gpp_loss` / `train_fdiff_cell_multiyear_rollout!`
    (extension): the cell MSE over years `L = (1/NY)Σ_y (Ḡ_y − T_y)²`, `Ḡ_y = (1/P)Σ_p G_{p,y}`, factors
    exactly patch-by-patch (`∂L/∂ps = Σ_p ∂/∂ps Σ_y c_y·G_{p,y}`, `c_y = (2/(NY·P))(Ḡ_y − T_y)` detached), so
    every reverse pass is the proven single-patch multi-year `rollout_canopy_years_gpp` Enzyme path — **no
    monolithic multi-patch AD** — and the per-patch gradients are summed by reusing one accumulating
    `Duplicated` shadow. One Enzyme reverse per patch over the FULL multi-year rollout per epoch (no
    per-chunk TBPTT). Runtime `[deps]` still EMPTY.
  - **Real committed multi-year reference** (`scripts/extract_fdiff_cell_multiyear.py`, sliced from the
    already-on-disk C re-run — no C re-run needed): the 2008 start-year 25-patch structure
    (`hainich_individuals_2008.csv`), per-year 2009–2011 daily forcing (`hainich_multiyear_forcing.csv`), and
    those years' daily C GPP + FAPAR (`hainich_multiyear_targets.csv`).
  - **Verification / gate** — new self-contained cell × multi-year testitem in `nn_canopy_training_tests.jl`
    (3 ragged patches × NY = 2): identity per-year Δ = 0; the per-patch-decomposed cell-multi-year gradient
    vs FiniteDifferences to **max rel err 1.5e-10**; recovery loss down **98.8 %** in 25 epochs, trained cell
    GPP within **0.07 %** of a known `vm=1.15/λ=1.05` target. Enzyme parts guarded `VERSION < v"1.11"`.
    Driver `scripts/train_fdiff_cell_multiyear.jl`; report §18; ADR 0016 (addendum).
  - **Result (full 25-patch cell, real 2008→2011 reference, kernel-isolation C-FAPAR phenology)** — the
    learned correction closes the cell-mean annual-GPP LEVEL against the real C per-year annual GPP through
    the multi-year structure feedback: mean model/C ratio **1.034 → 0.998** (`:vm`) → **0.996** (`:vm,:λ`);
    per-year 1.026/1.014/1.063 → 0.992/0.981/1.022 (`:vm`). One shared correction fit across years trims the
    year-to-year spread (2011 the high-GPP outlier) rather than zeroing each year. Full suite
    **25,943 pass / 0 fail / 4 broken** on Julia 1.10.
- **`scripts/sbatch_train.sh`** — submit the F_diff NN-training drivers as durable SLURM batch jobs on a
  compute node (`standard`/`qos=short`, `--project=test`, Julia 1.10), so the heavy Enzyme-reverse training
  runs (the cell × multi-year fit is a one-time ~7-min compile + ~30-min run) are off the login node and
  survive a dropped interactive session.
- **NN training THROUGH the multi-year structure/allocation feedback (Phase-3 scale-up step 7b-multiyear;
  ADR 0016).** §16's documented frontier — training GPP to match the C *while the canopy structure grows
  between years via the allocation* — is now Enzyme-differentiable. Session 11's `EnzymeNoTypeError` was
  root-caused (NOT the guessed `BitVector`/`_solve_leaf_inc` temporary, both of which differentiate cleanly
  in isolation) to a **struct-in-memory** failure: a `Vector{TreePools}` field-scatter of `grow_individual`'s
  branchy output copies the struct's trailing `is_grass::Bool` + padding as `Anything` in an 80-byte memcpy.
  - **Struct-of-arrays fix.** `_patch_fpars` split into an Enzyme-typeable SoA core `_patch_fpars_soa`
    (plain `Vector{Float64}` field arrays) + a thin `Vector{TreePools}` unpacking wrapper — **byte-identical**
    (max|Δ| = 0.0), so no committed canopy baseline moves. New dependency-free `rollout_canopy_years_gpp`
    (exported): the multi-year coupled rollout in SoA form (same physics as `rollout_canopy_years`),
    returning per-year annual stand GPP; soil carried across years as fields, `phens` materialized to a
    concrete type — the two smaller `EnzymeNoTypeError` mechanisms documented in the report Enzyme note.
  - **Multi-year trainer** `fdiff_multiyear_gpp_loss` / `train_fdiff_multiyear_rollout!` (extension) — one
    Enzyme reverse gradient of the FULL multi-year loss per epoch (the annual structure feedback stays inside
    the differentiated unit). Runtime `[deps]` still EMPTY.
  - **Verification / gate** — Enzyme reverse through the full SoA structure → daily rollout → grow →
    next-year chain matches FiniteDifferences to ~1e-11 (scalar hook) / 8.2e-10 (network-param gradient);
    ForwardDiff through the physics to ~1e-13. New self-contained multi-year testitem in
    `nn_canopy_training_tests.jl`: identity (Δ = 0), Enzyme-vs-FD gradient, and recovery of a known
    `vm=1.15/λ=1.05` correction (loss 16.2 → 0.12, 99.3 %; trained GPP within 0.28 %). Enzyme parts guarded
    `VERSION < v"1.11"`. Driver `scripts/train_fdiff_multiyear.jl`; report §17; ADR 0016 (addendum).
- **NN training against the REAL C-binary daily GPP on the full 25-patch cell + the λ lever (Phase-3
  scale-up step 7b-cell; ADR 0016).** §15 recovered a *synthetic* correction on one patch; this trains the
  learned correction against the LPJmL-FIT C binary's own daily GPP on the full Hainich cell (25 patches /
  297 individuals) — the honest validation objective — and turns on the λ head.
  - **Cell (multi-patch) loss + trainer** `fdiff_cell_gpp_loss` / `train_fdiff_cell_rollout!` (extension):
    the C daily GPP is the cell-mean over patches, so one shared learned correction is trained so the
    cell-mean GPP matches the C. The cell-MSE gradient is computed by an **exact per-patch decomposition**
    (Gauss–Newton residual reweighting: `∂L/∂ps = Σ_p ∂/∂ps Σ_i c_i·g_{p,i}`, `c_i = (2/(D·P))(ḡ_i−t_i)`
    detached), so every reverse pass is the proven single-patch `daily_step_canopy` Enzyme path — **no
    monolithic multi-patch AD entry point** — and the per-patch gradients are summed by reusing one
    accumulating `Duplicated` shadow. Runtime `[deps]` still empty.
  - **Result (full 25-patch Hainich, kernel-isolation C-FAPAR phenology):** the learned Vcmax lever closes
    the GPP level from **1.093 → 1.023** (`:vm`) and **→ 1.010** (`:vm, :λ`) against the real C daily GPP,
    while the daily correlation **improves** (full-year 0.9978 → 0.9983, growing-season 0.9973 → 0.9990) —
    the opposite of the single-representative path (§14), where the light-limited residual made Vcmax the
    wrong lever and the fit degraded the shape. The canopy residual IS Vcmax-shaped. Driver
    `scripts/train_fdiff_canopy_cell.jl`; report `docs/phase3_fdiff_cbinary_validation.md` §16.
  - **Gate** `test/testitems/nn_canopy_training_tests.jl` (cell testitem, 3 ragged patches, self-contained):
    identity (Δ = 0, both vm+λ hooks); **cell gradient (Gauss–Newton decomposition) vs FiniteDifferences,
    max rel err 6.1e-10** on the full multi-patch cell MSE; recovery of a known vm=1.15/λ=1.05 correction
    (loss 0.330 → 0.011, trained cell GPP within 0.04 %). Enzyme parts guarded to `VERSION < v"1.11"` (§15).
  - **Multi-year objective through the structure/allocation feedback — the next frontier.** Enzyme reverse
    through `rollout_canopy_years` (`_patch_fpars` layered-light recompute + `grow_individual`'s allocation
    Newton) raises `EnzymeNoTypeError` on Julia 1.10 — an Enzyme type-analysis blocker on the composed
    structure path, not a differentiability problem (§12's ForwardDiff `d(structure)/d(bm_inc)` /
    `d(structure)/d(α_c3)` already match FD). Documented in §16 as the follow-up.
- **NN training on the coupled CANOPY path — Enzyme reverse through the array-mutating rollout (Phase-3
  scale-up step 7b-canopy; ADR 0016).** Applies the learned correction where the residual is
  Vcmax/phenology-shaped (the coupled canopy), and closes the AD-through-mutation follow-up flagged since
  step 2.
  - **Per-individual NN hooks in `FDiff.daily_step_canopy`** (threaded through `rollout_daily_canopy` +
    `rollout_canopy_years`): each individual's learned Vcmax/λ correction from its own feature vector
    `[temp, swdown, daylength, apar_i, wr, co2]`, applied consistently to pass-1 (gp_sum) and pass-2
    (GPP/λ) Vcmax. Identity fast path when off ⇒ **every committed canopy baseline byte-identical** (gate
    Δ = 0).
  - **Enzyme-reverse trainer** `train_fdiff_canopy_rollout!` + loss `fdiff_canopy_gpp_loss` (extension):
    `daily_step_canopy` mutates the per-layer soil arrays, which Zygote can't cross — so it trains with
    Enzyme reverse (`Duplicated` params + fresh `make_zero` shadow + `set_runtime_activity`, Lux's
    `AutoEnzyme` idiom). `Enzyme` becomes a 4th extension trigger (`FDiffTrainingExt` now needs
    `Lux`/`Zygote`/`Optimisers`/`Enzyme`); runtime `[deps]` still empty.
  - **Gate** `test/testitems/nn_canopy_training_tests.jl` (self-contained: 4 individuals, 5-layer soil,
    40-day forcing): identity (Δ = 0); **Enzyme gradient w.r.t. NN params vs FiniteDifferences, max rel
    err 1.2e-8** through the mutating canopy path; recovery of a known correction (loss 0.205 → 1.1e-3,
    trained GPP within 3 %, recovered Vcmax scale ≈ 1.18 vs the known 1.20 — the small low-bias is the
    understory `je`-limit). Report `docs/phase3_fdiff_cbinary_validation.md` §15.
  - **Julia-version caveat (CI-surfaced):** the Enzyme-reverse canopy path is verified on **Julia 1.10**
    (lts; `Project.toml` compat `julia = "1.10"`). On **Julia ≥ 1.11**, Enzyme 0.13 raises an internal LLVM
    compiler error through this complex mutating path (the single-bucket Enzyme gate compiles fine on 1.11).
    The per-individual `FDiffParams{T}` construction in `daily_step_canopy` was switched from the keyword to
    the equivalent **positional** constructor (Enzyme-transparent; behaviour-identical), and the
    Enzyme-dependent parts of the canopy gate are guarded to `VERSION < v"1.11"` (identity runs everywhere)
    so CI's forward-compat `test (1)` job stays green. Lifting the guard is an upstream-Enzyme follow-up.
- **Gradient-based online rollout training — NN λ/Vcmax hooks + finished TBPTT loop (Phase-3 scale-up
  step 7b; ADR 0016).** The milestone the differentiable-first core (ADR 0014) exists to enable.
  - **Dependency-free NN hooks in the physics** (`FDiff.FluxHooks`): optional LEARNED multiplicative
    corrections to the two photosynthesis levers a hybrid trains — Vcmax (`vm`) and the ci:ca ratio `λ` —
    threaded through `daily_step`/`rollout`/`annual_npp`. Default `nothing` = the identity fast path, so
    **every regression baseline is byte-identical when the hook is off**; the runtime stays
    dependency-free (the physics only ever *calls* the hook). `photosynthesis` gains a `vm_scale` kwarg
    (applied at Vcmax, propagating into potential conductance + leaf respiration); the λ hook re-clamps to
    the physical bracket. Feature vector `[temp, swdown, daylength, apar, w_soil, co2]`.
  - **Training as a PACKAGE EXTENSION** `ext/FDiffTrainingExt.jl` (weakdeps `Lux`/`Zygote`/`Optimisers`,
    activated by `using` them; runtime `[deps]` stays empty): a Lux MLP with a **zero-initialized final
    layer** (untrained ⇒ exactly the identity correction), `build_fdiff_nn` / `neural_vm_hook` /
    `neural_lambda_hook`, the scalar rollout GPP loss `fdiff_gpp_loss`, and the finished TBPTT
    online-rollout loop `train_fdiff_rollout!` — a working port of NeuralCrop.jl's broken
    `train_loop_rollout!` scaffold (Zygote reverse-mode + `Optimisers.update` + detached soil-water state
    carried across chunk boundaries).
  - **Gate** `test/testitems/nn_training_tests.jl`: (1) identity (hook-off == committed baseline;
    zero-init net == pure physics to 1e-10); (2) gradient correctness (Zygote gradient w.r.t. NN params
    vs FiniteDifferences, rtol 1e-4 — the AD-vs-FD discipline of the physics gradient gate); (3) recovery
    of a known correction (loss 0.67 → ~1e-3, trained GPP within 0.1 %, recovered Vcmax scale ≈ the known
    1.30 — an identifiability proof of the machinery).
  - **Physical finding:** fitting the learned Vcmax correction to the LPJmL-FIT C daily GPP on the
    single-representative path only PARTIALLY closes the level gap (annual ratio ≈ 0.64 → ≈ 0.79) — that
    gap is **light/structure-limited** (Haxeltine–Prentice co-limitation saturates at the light-limited
    rate `je`), so Vcmax is the wrong lever there; it is exactly why the multi-individual canopy step
    (§9) closed GPP by spreading light. The learned Vcmax/λ correction belongs on the **coupled canopy
    path** (Enzyme-reverse-through-mutation), the documented next step. Driver `scripts/train_fdiff_nn.jl`;
    report `docs/phase3_fdiff_cbinary_validation.md` §14; ADR 0016.
- Root `Project.toml` gains `[weakdeps]` + `[extensions]` (`FDiffTrainingExt`) and their `[compat]`; the
  runtime `[deps]` is still empty (dependency-free core, ADR 0014). `test/Project.toml` gains
  `Lux`/`Zygote`/`Optimisers`.

### Changed
- **Beech GSI phenology `tmin` corrected to the ACTIVE FIT parameter file (docs §19).** The beech (TeBS)
  cold-temperature limiter was `tmin_slope=2.0`, `tmin_base=8.0` — the **standard** `par/pft.js` values —
  but the FIT run uses **`par/pft_lpjmlfit.js`** (`tmin_slope=4.0`, `tmin_base=8.5`; the other beech GSI
  params already matched). Correcting them makes the self-computed phenology consistent with the C binary it
  validates against: the standalone 25-patch canopy GPP annual ratio tightens **1.17 → 1.13**, transp
  **1.08 → 1.05**, daily r ≈ 0.99 unchanged. Only `hainich_canopy_baseline_2010.txt` moved (`gpp`
  1286 → 1250, `transp` 258 → 251); the C-FAPAR-driven single-rep/multilayer baselines and
  `fdiff_annual_totals.txt` are unmoved.
- **Self-computed canopy NPP CALIBRATED — the `bm_inc` crutch removed (Phase-3 scale-up step 7a).** The
  step-6 over-respiration (standalone canopy NPP ≈ −25 vs the C's ≈ +507 gC/m²/yr) was decomposed against
  the C target (`Ra = R_leaf + R_maint + R_growth`) to two faithful-to-`npp_tree.c` fixes in
  `FDiff.autotrophic_respiration` — NOT a constants error:
  - **The growth-respiration `max(0,·)` floor was far too soft.** The C is a hard branch
    `npp = (assim<mresp) ? assim−mresp : (assim−mresp)·(1−r_growth)` (`npp_tree.c:52`, `assim = gpp−rd`),
    i.e. `R_growth = r_growth·max(0, gpp−rd−mresp)`, zero when carbon-negative; F_diff smoothed it with
    `softplus(·, β=1)`, whose `log(2)/β ≈ 0.69 gC` offset injected a phantom growth respiration into every
    carbon-negative individual/day (≈ +730 gC/m²/yr aggregated). Sharpened via a new `RespParams.βgrowth`
    (= 50, matching the other flux floors).
  - **Fine-root maintenance is now phen-gated** (`npp_tree.c:51` scales the root/`sapwood_bg` block by
    `pft->phen`, above-ground sapwood year-round): `R_maint = respcoeff·k·gtemp·(C_sap/CN_sap +
    phen·C_root/CN_root)`. The three call sites pass the day's `phen`.
  - **Result:** standalone canopy annual NPP **−25 → +663 gC/m²/yr** (C 507); winter leaf-off **−250 →
    −6.7** (C −13); daily NPP **r 0.987**; carbon-use efficiency **NPP/GPP 0.52 vs the C's 0.46**. In the
    kernel-isolation config (C FAPAR+PET, GPP≈C) the respiration **total Ra = 592.8 vs the C's 595.6 — a
    0.5 % match**, so the standalone NPP overshoot (×1.31) is inherited from the documented +17 %
    GPP-phenology level, not a respiration miscalibration.
  - **The `bm_inc` crutch is removed:** `rollout_canopy_years` defaults fully self-driven, and
    `FDiffFastCore` always self-accumulated its own NPP. The self-driven coupled loop grows structure
    smoothly (year-1 mean tree height 9.41 m vs the C's 9.344; 8-year H 9.41 → 10.28; no blow-up).
  - Adversarially re-verified against `npp_tree.c` / `water_stressed.c` / `daily_natural.c`. Two
    documented second-order residuals remain (both pre-existing v1, partially cancelling): omitted
    `sapwood_bg` below-ground maintenance (NPP high) and un-gated `rd` on rare water-stress-collapse days
    (NPP low). Report `docs/phase3_fdiff_cbinary_validation.md` §13.
- **Numerical-regression baseline** `test/testitems/references/fdiff_annual_totals.txt`: `npp`
  871.81 → 893.28 (the sharpened growth-resp floor removes the phantom respiration on the synthetic
  scenario too); `gpp`/`transp`/`evap`/`runoff`/`precip` are byte-identical (the fix is downstream of GPP
  and the water balance). The water/light canopy baselines are unchanged.
- **Gates:** new self-computed-NPP gate in `multi_individual_tests.jl` (positive NPP; ratio ≤ 1.6; CUE ∈
  [0.42, 0.56]; daily r > 0.95; bounded winter deficit); `dynamic_structure_tests.jl` and
  `coupling_tests.jl` now run the coupled loop fully self-driven. `scripts/validate_fdiff_canopy.jl`
  fixed (stale `nind` constructor) + extended to report NPP/CUE. Full suite **25,865 pass / 0 fail /
  4 broken**; ForwardDiff/Enzyme still match finite differences (the fixes add no new conditionals);
  Runic-clean.

### Added
- **Dynamic (prognostic) canopy structure + the S↔F coupling adapter (Phase-3 scale-up step 6).** The
  multi-individual canopy's per-individual carbon pools are now PROGNOSTIC: they accumulate the daily
  `bm_inc` (= Σ daily NPP, per-m² patch basis — the new `npp_ind` flux) and GROW at the annual boundary
  via a faithful DIFFERENTIABLE port of the LPJmL-FIT year-end sequence `turnover_tree.c` →
  `allocation_tree.c` → `allometry_tree.c`. New `FDiff` API: `AllocParams`, `TreePools`, `grow_individual`
  (reproduction reserve + sapwood→heartwood + summergreen leaf/root recycle + pipe-model allocation +
  allometry), `_alloc_residual`/`_solve_leaf_inc` (a fixed-graph damped-Newton allocation solve — the
  λ-solve AD pattern, not the C's bisection), `individual_from_pools`/`_patch_fpars` (getfpar
  layered-light recompute as heights grow), `rollout_canopy_years` (the multi-year coupled loop),
  `tebs_allocparams`. Verified line-by-line against the C source (9-agent extraction workflow +
  adversarial re-derivation).
  - **Decisive validation:** the pipe-model invariant `leaf ≈ k_latosa·sapwood/(wooddens·H·sla)` holds
    after allocation to **max rel. error 2.9e-16**; carbon conservation `Δ(pools) = bm_net − turnover` is
    exact; **ForwardDiff `d(height)/d(bm_inc)` & `d(sapwood)/d(bm_inc)` match finite differences**; a
    coupled multi-year rollout (2009 start + 2010 forcing + the C's `bm_inc`) gives **year-1 mean tree
    height 9.34 m = the C's actual 2010 value** (from 2009's 9.21) and an 8-year trajectory grows smoothly
    with no blow-up.
  - **`FDiffFastCore <: AbstractFastCore` — `AbstractFastCore.step!` no longer throws.** Daily
    `step!(fc, state::SharedState, bc::SToF, forcing::AtmForcing) -> FToE` maps the shared per-layer soil
    water ↔ the `SoilColumn`, self-computes daylength/GSI-phenology/dynamic-albedo `eeq`, runs one
    `daily_step_canopy`, **writes the soil water back into `SharedState.w` in place**, and returns the
    daily `FToE` (`LE = λ·ET`); the year-end `annual_step!(fc, state) -> FToS` grows the prognostic
    structure and returns the conserved increment for S — the flux-then-integrate S↔F handoff (DESIGN §8).
  - **A load-bearing per-m² maintenance-respiration fix:** `daily_step_canopy` had fed per-individual
    pools into the maintenance term against per-m² GPP/leaf-resp; added `nind` to `FDiff.Individual` and
    the `×nind` factor (`npp_tree.c:51`) so NPP is per-m² consistent (the committed water/light baselines
    are unchanged). **Known residual (RESOLVED in step 7a, above):** F_diff's self-computed canopy NPP
    over-respired (≈ −25 vs the C's ≈ +512 gC/m²/yr) — the real causes were the soft growth-resp floor +
    un-phen-gated root maintenance (the maintenance constants matched the C exactly); until then the
    coupled loop used a `bm_inc` crutch (the C's per-individual NPP — the same kernel-isolation methodology
    used for the FAPAR/PET crutches), and a carbon-deficit individual stagnates rather than blowing up the
    pipe-model height.
  - New gates `test/testitems/dynamic_structure_tests.jl` (allocation invariant, conservation, growth,
    AD; 30 tests) + `test/testitems/coupling_tests.jl` (the `FDiffFastCore` adapter + coupled loop; 15
    tests), self-contained on the committed 2010 reference. Data reconstruction
    `scripts/extract_fdiff_individuals_multiyear.py` (2008–2011 per-individual pools incl. heartwood) +
    committed `references/hainich_structure_growth.txt`; driver `scripts/validate_fdiff_structure.jl`.
    Report `docs/phase3_fdiff_cbinary_validation.md` §12. Full suite **25,856 pass / 0 fail / 4 broken**;
    JET/Aqua/gradient green; Runic-clean.
- **Differentiable multi-layer soil water for `F_diff` (Phase-3 scale-up step 2).** Replaced the single
  soil bucket with a 23-layer differentiable column (`FDiff.SoilColumn`, `FDiffStateML`,
  `daily_step_ml`/`rollout_daily_ml`, `hainich_soilcolumn`): fill-to-field-capacity infiltration
  cascade, Jackson-1996 β root distribution (D95 ≈ 115 cm → ~93 % of roots in the top 1 m), per-layer
  root-weighted transpiration withdrawal, and top-300 mm quadratic soil evaporation. Per-layer
  capacities are taken from the C run's own `whc_nat` output (no pedotransfer port); the runtime stays
  dependency-free and water closes to ~1e-12 mm.
  - Validated on Hainich (same FAPAR-driven harness): **GPP daily correlation 0.76 → 0.93**,
    **transpiration 0.91 → 0.96**, and root-zone water now representable per layer (r = 0.87) — at
    essentially unchanged levels. This **localizes the residual transpiration/GPP level gaps to the
    demand-side / single-representative-individual step, not soil supply** (the next scale-up item).
  - New gate `test/testitems/multilayer_soil_tests.jl` (per-day water closure, no-NaN, soil-water +
    GPP/transp correlations vs the C binary, ForwardDiff differentiability, drift baseline) with
    committed `references/hainich_soilcolumn.txt` + `hainich_ml_baseline_2010.txt`. Report
    `docs/phase3_fdiff_cbinary_validation.md` §8. Full suite **25,788 pass / 0 fail**. ForwardDiff
    differentiates the layered rollout; Enzyme reverse-mode through it is a documented follow-up.
- **`F_diff` ↔ LPJmL-FIT C-binary quantitative validation on the prototype cell (Phase-3 scale-up
  step 1).** `F_diff` driven by Hainich's (global-grid cell **42490**) REAL daily `.clm` forcing + the
  C binary's ACTUAL daily FAPAR (kernel-isolation drive), compared to LPJmL-FIT's own daily
  GPP/transp/PET. **PET/radiation path validated tight** (daily ratio 1.05, r 0.999); **GPP seasonal
  dynamics captured** (annual r 0.96, within-year growing-season daily r 0.96) with level −42%;
  **transpiration timing captured** (r 0.91–0.97) with level +40–47% — the level offsets attributed
  to the documented multi-PFT/representative-individual + 23-layer-soil scale-up gaps (photosynthesis
  kernel `#define`s are byte-identical, so not kernel bugs).
  - New: `scripts/run_fdiff_validation_cell.sh` (single-cell daily re-run adding daily FAPAR + NV_LAI +
    annual FPC_STAND/LAI_STAND), `scripts/extract_fdiff_validation_inputs.py` (LPJmL `.clm` YEARCELL
    reader — validated against the model's own `d_prec` to 0.0 — + `petpar2` daylength + C-target
    extraction), `scripts/validate_fdiff_vs_cbinary.jl` (multi-year analysis driver).
  - New gate `test/testitems/cbinary_validation_tests.jl` (committed one-year 2010 reference:
    `hainich_{forcing,cbinary_targets,fdiff_baseline}_2010.*`) + a `ReferenceTests` drift alarm on
    `F_diff`'s own annual totals on real forcing. Replaces the "`F_diff` pinned against ITSELF" note.
    Report `docs/phase3_fdiff_cbinary_validation.md`; metrics
    `artifacts/metrics/phase3_fdiff_cbinary_validation.json`. Full suite **25,768 pass / 0 fail**.
  - `F_diff` additions (AD-safe; the numerical-regression baseline is unchanged): `Structure.alphaa`
    (PAR-use fraction, default 1.0; TeBS 0.55), the SLA-dependent Vcmax cap (`PhotoParams.issla`,
    default off), an **external-FAPAR drive mode** (`daily_step`/`rollout`/new `rollout_daily` accept a
    per-day `fapar`), and `tebs_params()`/`tebs_structure()` (the beech PFT-3 set). The λ-solve Newton
    iterate is now `clamp`ed to the physical bracket `[0.02, 0.85]` (fixes a deep-winter low-light NaN;
    a `smooth_clamp` was rejected because `softplus(β·huge)` overflows the AD dual). That clamp is a
    conditional, so **Enzyme reverse-mode now uses `set_runtime_activity`** (still exact vs finite
    differences; ForwardDiff unaffected; the gradient-correctness gate is unchanged).
- **⚠️ Corrected the prototype-cell index:** Hainich (DE-Hai) in the **global orderA grid** (all
  ground-truth + daily data) is 0-based index **42490** (lat 51.25/lon 10.25), NOT `28008` (= Sonoran
  desert in that grid; 28008 is Hainich only in the repo default `-DSINGLESITE` grid). Fixed in
  `MEMORY.md`, `DESIGN.md`, `config/paths.yaml`.
- **Differentiable fast core (`F_diff`) — early one-cell spike (ADR 0014/0015).** Built F
  differentiable from the start (owner decision superseding the F1-now/F2-later split): the shared
  **allometry/diagnostics** library (`src/allometry.jl` — pipe-model height, Jucker 2022 crown/stem,
  LAI, Beer–Lambert FPC, pure & differentiable), a **smooth-surrogate** library (`src/fdiff_smoothops.jl`
  — softplus/smoothmin/max/clamp with tested `log(2)/β` deviation bounds), and the **`F_diff` daily
  biophysics** (`src/fdiff.jl` — C3/C4 Haxeltine & Prentice photosynthesis, the λ ci:ca supply/demand
  solve, Priestley–Taylor PET/ET, soil-water bucket + snow, Lloyd–Taylor respiration; pure
  `daily_step` + 365-day `rollout`). Same equations as the LPJmL-FIT C core, C-source constants.
  **Runtime is dependency-free**; AD is a test-time tool (ADR 0014).
  - **Gradient-correctness gate MET:** Enzyme reverse-mode **and** ForwardDiff match FiniteDifferences
    to ~1e-11 for `d(annual NPP)/dx` (x = CO₂, emax, α_c3, initial soil water) through the full daily
    rollout incl. the λ Newton solve and the autoregressive soil-water coupling — no NaN/Inf. This is
    the differentiability the reference repos do not demonstrate (they detach physics).
  - New gates: `allometry_tests.jl` (values/limits/monotonicity/types), `smoothops_tests.jl`
    (surrogate deviation bounds), `fdiff_physics_tests.jl` (water closure ~1e-12, boundedness,
    limiting cases, determinism, Float32), filled-in `gradient_correctness_tests.jl` (AD vs FD) and
    `numerical_regression_tests.jl` (annual-totals baseline `references/fdiff_annual_totals.txt`).
    Full suite: **25,756 pass / 0 fail** (JET clean; a latent `@kwdef` unbound-`T` bug in
    `FDiffParams` that JET caught was fixed). Reuse map + citations in ADR 0015 / CITATION.cff.
  - Report: `docs/phase3_fdiff_spike.md` (feasibility verdict, non-smoothness issues hit, effort
    estimate ≈ 2.5–4 months to cover all of F). `DEVELOPMENT_PLAN.md` §2.3/§6 updated.
- **Phase 0 (DESIGN)** deliverable `DESIGN.md`: re-verified the two load-bearing LPJmL-FIT
  findings (daily output is config-only; no surface energy balance), froze the shared-state
  vector and the S↔F↔E interface contract, froze the data schema, and resolved the build/run
  recipe and input-data paths. Adversarially reviewed (16/22 findings applied).
- Engineering scaffold to `ENGINEERING_STANDARDS.md`: Julia package skeleton
  (`LPJmLFITEmulator`), `@testitem` scientific-gate placeholders (conservation, gradient
  correctness, rollout stability, determinism, resilience battery, …), GitHub Actions CI
  (tests/format/docs/python/TagBot/dependabot), Documenter.jl documentation (Diátaxis +
  citations + model card + datasheets), ADRs for decisions already made, curated Mermaid +
  code/config-derived diagrams, and reproducibility wiring (StableRNGs, DrWatson, DVC, MLflow).
- Resolved `config/paths.yaml` and `config/hpc_slurm.yaml` to the real PIK cluster values
  (LPJROOT `/home/jamirp/lpjml56fit`, verified modules, production input/restart paths,
  Python env `py311_new`).

- **Component S canonical port** (`feat/port-slow-emulator`, ADR 0012): ported the slow
  distributional emulator from the now-frozen sibling `/p/projects/open/Jamir/emulator` into
  `python/src/lpjmlfit_emulator/` — `transforms.py` (signed-log + isotonic monotone links),
  `drivers.py` (annual climate/CO₂ aggregation, xarray-guarded), `features.py`
  (`build_cell_year_feats` + climclusterpy/NetCDF-guarded eco diagnostics), `baseline.py` (the
  DIRECT non-recursive climate→distribution emulator + `ResidualRegressor`/`add_competition`),
  `train.py` (holdout/train/eval helpers, matplotlib-guarded), extended `data.py` (validated
  `load_ind` loader + generalized `build_patch_summaries`, frozen 29-col schema kept), a curated
  `__init__.py` public API, and `python/config/config.yaml`. Each ported module carries a
  provenance header and was adversarially fidelity-checked against its source. New tests
  (`test_transforms.py`, `test_features.py`, `test_noise_floor.py`, extended `test_data.py`) →
  **49 passed / 6 skipped** in `py311_new`; 56 passed + ruff-clean in the locked CI env.
- `noise_floor.py`: seed1-vs-seed2 noise-floor diagnostics (per-cell magnitude floor
  `median|s1-s2|/s1`, ranking ceiling, per-cell error distribution p50/p75/p90, fraction within
  floor, latitude-band bias) layered on `metrics.py`; its test asserts the published per-variable
  floor `{Height:0.020, agb:0.113, npp:0.062, LAI:0.025}`. Rebuilt from the documented discipline
  (the sibling `eval_presentday_critical.py` is unreadable under the auto-mode classifier's
  "eval"-filename heuristic — not an owner-configured hook).

- **Phase 1 / P3b — daily-output re-run + WATER-CLOSURE gate (PASSED).** `scripts/run_daily_subset.sh`
  enables daily output (no recompile) and re-runs the Historical transient from the spinup-end
  `restart_1999.lpj` over a contiguous cell subset; `scripts/water_closure_check.py` verifies closure.
  Boreal validation run (cells 45000–45999, 2000–2002, 83 s): LPJmL's `-DSAFE` per-cell/year water
  balance passed for all 1000 cells × 3 yr (a clean run *is* closure to ≤1.5 mm/yr), daily fluxes
  integrate to the annual `globalflux` to 5 sig figs, cumulative per-cell imbalance median 2.7 %, and
  daily NPP → annual NPP ratio 1.000. Report: [`docs/phase1_p3b_water_closure.md`](docs/phase1_p3b_water_closure.md);
  summary `artifacts/metrics/p3b_water_closure_boreal_c45000_45999.json`. Verified against LPJmL source
  (adversarially): contiguous-subset restart via 0-based positional `startgrid`/`endgrid`; daily via
  `"timestep":"daily"` in the entry's `file` object; `swc` is fractional saturation (`wsats` not output);
  build modules need `json-c/0.13.1` (not 0.17).
- **Full-global daily F/E training dataset generated** — all **67,420 cells × 2000–2019** (186 GB,
  daily prec/transp/evap/interc/runoff/swe/swc/rootmoist/whc_nat/pet/npp/gpp), restarted from the seed1
  spinup-end restart so it reproduces the seed1 Historical trajectory at daily resolution. Water closure
  re-confirmed at scale: clean run with no water-balance error (SAFE, all cells × 20 yr), daily fluxes
  integrate to the annual `globalflux` to ~5 sig figs, per-cell multi-year imbalance median 0.87 %.
  Summary `artifacts/metrics/p3b_water_closure_global_c0_67419.json`; data on `/p/tmp` (DVC, not in git).
  Generator/analysis parameterized (`TIME`/`EXCLUSIVE`) + made dask-lazy/memory-safe for the ~185 GB
  scale. Both Phase-1 gates (carbon + water) now pass.
- **Phase 2 (slow emulator, offline) — gate met at the baseline tier.** `scripts/train_slow_emulator.py`
  trains the ported DIRECT `DirectEmulator` on a biome-stratified 6000-cell set and scores rendered
  holdout distributions vs the seed1-vs-seed2 noise floor (random in-distribution + warm+dry OOD),
  building `tree_step`/`grass`/holdout subsets from the `ind` parquet. In-distribution: median KS 0.023,
  joint energy within 1.72× the floor, drift-free, per-cell NPP conserved ~21% median. Warm+dry OOD:
  ks 32× floor — the documented equilibrium-ML limitation the Phase-3 hybrid targets. No generative
  escalation triggered (ADR 0005). Report [`docs/phase2_slow_emulator.md`](docs/phase2_slow_emulator.md);
  artifacts `artifacts/metrics/phase2_slow_emulator_{random,oodwarm}_6000.json`.

### Changed
- **Workflow → main-only** ([ADR 0013](docs/decisions/0013-main-only-workflow.md)): commit and push
  straight to `main`; no feature branches, PRs, or branch protection (owner declined), and no
  signed-commit enforcement. CI still runs on `push: main` as a smoke alarm (fix-forward if red).
  `ENGINEERING_STANDARDS.md` §1 softened to point at the ADR (original PR/branch-protection posture
  retained struck-through, with the reinstatement command).
- `.github/dependabot.yml` **tamed**: monthly (was weekly) + grouped updates (one consolidated PR per
  ecosystem per cycle) to stop the per-package branch spam.
- `ENGINEERING_STANDARDS.md` §2 and `DESIGN_CHECKPOINT_PROMPT.md` item 2 now lead with an explicit
  **unit-test foundation** (testing pyramid: unit → integration → system) beneath the scientific
  gates, with a project-specific unit-test list (allometry, unit conversions, softmax/allocation,
  config parsing, data loaders, index/date math, numerical kernels, error handling).

### Fixed
- **CI green on `main`** — repaired the three workflows that were red on `57e3a95` (three independent
  causes):
  - `python`: floating `>=` deps with no lockfile let CI resolve breaking majors. Added upper-bound
    caps matching the known-good `py311_new` set, committed `python/uv.lock`, and switched the job to
    `uv sync --frozen`. Also ran `ruff format` on the never-formatted scaffold sources.
  - `format`: reformatted all 18 tracked Julia files with Runic 1.7.0 (the version the job installs).
  - `docs`: fixed a broken `[`checkdims`](@ref)` cross-reference (non-exported symbol → added a
    `CurrentModule` @meta block), enabled `linkcheck` with an ignore for private-repo self-links, and
    silenced two DocumenterCitations `.bib`-comment warnings. Each fix was reproduced and verified
    locally (uv venv for Python; local Julia 1.10 + Documenter 1.17 for format/docs).

### Validation
- Scaffold validated locally end-to-end: **Julia `Pkg.test()` green** (21,071 assertions pass, 6
  intentional `@test_broken` Phase-6 placeholders, 0 fail/error; Aqua + JET clean), **Python `pytest`
  green** (21 pass in `py311_new`), diagram diff-alarm (`gen_diagrams.jl --check`) green, all CI YAML
  parses, and `bin/lpjml -h` runs (netcdf-c/4.9.2). JET caught and fixed a real `SharedState`
  constructor bug (`@kwdef` unbound type parameter) during scaffolding.

### Notes
- No modelling behaviour yet — this release is the design freeze + auditable engineering skeleton.
- Data, model weights, and restarts are never committed (tracked via DVC pointers).
- Root `Manifest.toml` deferred until Phase-3+ deps are added (the package currently has empty `[deps]`).

[Unreleased]: https://github.com/rimajj/LPJmLFIT_Emulator/commits/main
