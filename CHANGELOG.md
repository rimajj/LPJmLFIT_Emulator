# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **P1 Tier-1 Step 4 — the PRODUCTION Component-S DRF loads from a serialized artifact + a runtime-consistent
  training table + the Gate-3 oracle + the copula recruit-trait sampler ([ADR 0023](docs/decisions/0023-component-s-production-drf-runtime-consistency.md)).**
  Closes the gap that Step 3's in-loop test used an in-test DRF — the model that is validated is now the model
  that runs. Zero new runtime `[deps]` (all pure Base, ADR 0014).
  - **(4a) DRF serialization + production artifact.** `DRF.save_forest`/`load_forest` (`src/drf.jl`) — a pure-Base
    text round-trip (magic `LPJMLFIT_DRF` + version; Float64 via Julia's shortest round-trippable decimal),
    verified **BITWISE** (predictions strict `==`, both `store_values` modes, NaN fill, ragged leaf values).
    `scripts/build_slow_runtime_table.py` builds a **runtime-consistent** feature table (exact
    `flux_feature_vector` order; `water_stress`=1−wscal_mean — fixing the OOD-table `mort_water`-inversion
    mismatch; `age_mean`=elapsed-year counter, NOT mean Age — closing the biggest train/inference-shift risk;
    `soilmoist`/`lai` documented proxies pending the global C-`LAI_STAND`/`swc` pipeline). `scripts/train_slow_drf.jl`
    fits + serializes the committed Hainich demo artifact `test/testitems/references/drf_forest_hainich.drf`
    (40 trees, ~95 KB, in-sample R²=0.975) + a meta/golden file.
    - **[VERIFIED] `test/testitems/slow_production_drf_tests.jl`:** the LOADED production DRF drives the coupled
      Hainich loop — predicts counts INSIDE its training band (targets 9.5→6.9, no wild extrapolation ⇒
      runtime-consistent), MOVES tree N (F alone holds it fixed), conserves carbon at the S↔F handoff to ~1e-12 gC,
      energy closes (7e-15), deterministic under seed. `drf_serialization_tests.jl` gates the round-trip + the
      committed artifact's golden (feature→prediction) pairs bitwise.
  - **(4b) Gate-3 oracle** (`test/testitems/slow_oracle_tests.jl`; `scripts/build_slow_oracle_reference.py` →
    `references/hainich_slow_oracle_{traits,counts}.csv`). The coupled flux-driven S size distribution matches the
    LPJmL-FIT C ground truth at Hainich (cell 42490): nind-weighted Height quantiles vs the C truth to
    IQR-normalized quantile-RMSE **~0.31** (median 8.9 vs 7.9 m), framed honestly as a recursive-coupled-S
    vs non-recursive-C-truth **drift alarm** (Hainich-only), not a parity gate.
  - **(4c) Gaussian-copula recruit-trait sampler BUILT** (`src/drf.jl`: `chol_lower`, `norminv` [Acklam],
    `normcdf` [A&S 26.2.17], `GaussianCopula`, `copula_uniforms!`, `sample_copula!`). Draws correlated recruit
    traits {logHeight, Age, SLA, Wooddens, beta_root} via the Cholesky of a committed correlation matrix mapped
    through the per-axis flux-conditioned `predict_quantile` marginals — the pure-Base analog of the sibling's
    `ResidualRegressor.sample_u`. **[VERIFIED] `test/testitems/drf_copula_tests.jl`:** recovers a target
    correlation from draws (±0.03), induces positive trait correlation, deterministic under `Xoshiro256pp`,
    Cholesky round-trips + guards non-PD. Its consumer (assigning drawn traits to APPENDED recruit cohorts) lands
    with the membership append/merge path (design risk #5); until then survivors keep frozen traits.
  - **Still open (v3, documented):** the GLOBAL runtime-consistent DRF (C-`LAI_STAND` + daily `swc`, many cells,
    C-truth demography target — a Phase-2 SLURM pipeline); wiring the copula into establishment; the in-loop OOD
    win; promoting the runtime `age_mean` to a true per-cohort mean age + retrain (ADR 0023 §3).
- **P1 Tier-1 Step 3 — the FLUX-DRIVEN Component S is IN the coupled loop (ADR 0020/0021/0022).**
  `FluxDrivenSlowEmulator{T} <: AbstractSlowEmulator` (`src/components/slow.jl`) sets the demography TARGET
  from the trained flux-conditioned DRF instead of Tier-0's constant rate: each year S builds a flux feature
  vector (F's delivered `FToS` fluxes + this-year patch state + the recursive AR count + a baked slow
  bioclimatic boundary), predicts the target with the DRF, and moves the coupled tree density toward
  `target/n_prev` (a UNIT-FREE ratio — the count↔density gap cancels) through the SAME carbon-conserving
  mortality/establishment machinery as Tier-0. Wires in via the existing `reconcile_demography!` interface
  (no change to `run.jl`); opt-in behind `run_coupled_cell(...; slow=)`, `slow=nothing` byte-identical
  (guardrail 4). Zero new runtime `[deps]`/`[weakdeps]` (the DRF + Xoshiro are pure Base, ADR 0022).
  - **[VERIFIED] Gates (Hainich 42490, `test/testitems/slow_flux_driven_tests.jl`; full CI-faithful suite
    green 48127 pass / 0 fail / 4 broken):** the DRF target DRIVES the demography (a decline-predicting
    forest shrinks N 0.076→0.013 indiv/m², a growth-predicting forest grows it 0.076→0.26, monotone in the
    predicted direction); the S↔F handoff CONSERVES carbon to **~1e-12 gC ≪ the 1e-6·C_scale gate** in both
    directions; energy still closes (1.4e-14); the coupled N trajectory is DETERMINISTIC under a seed; and it
    is type-stable + conserving in **Float32** (the SpeedyWeather-coupling type).
- **P1 Tier-1 Step 2 — the flux-driven premise is VALIDATED + a zero-dep native-Julia DRF (ADR 0020/0021/0022).**
  The falsifiable ADR-0020 success test now has a result on the warm+dry OOD holdout (space-for-time SSP370
  proxy), and it **supports ADR 0020** three independent ways. New pieces:
  - `src/drf.jl` (`module DRF`) — a **zero-dependency** distributional random forest in pure Base Julia
    (hand-rolled Xoshiro256++ RNG; subbagged variance-reduction trees; leaves optionally store sample values
    for quantile/distributional queries; per-tree-seeded ⇒ multithreaded fit is bit-reproducible). This is the
    model the flux-driven S will use — trained AND run natively, no new `[deps]`/`[weakdeps]`
    (**[ADR 0022](docs/decisions/0022-component-s-handrolled-drf.md)**; EvoTrees verified available as a fallback
    but deliberately not adopted, to keep the trusted-physics CI free of dependency-churn risk).
  - `scripts/build_slow_count_table.py` — the biome-scale count-model table (1,323,905 rows / 4000 lat-stratified
    tree cells / 400 warm+dry holdout cells) carrying BOTH channels (flux drivers + patch state + AR + slow
    boundary; and the DirectEmulator's raw climate + climatology + the SAME boundary) so the comparison is
    apples-to-apples; `scripts/export_count_matrices.py` dumps a zero-dep raw-Float64 payload;
    `scripts/flux_ood_experiment.jl` fits the DRF on each channel and scores in-distribution vs OOD;
    `scripts/sbatch_python.sh` (the Python twin of `sbatch_julia.sh`).
  - **[VERIFIED 2026-07-22] OOD verdict** (living-tree count / patch; DRF, seed 1): climate-only fails OOD
    (**R²=−0.16**, ≈ the boundary floor — the documented equilibrium-ML failure, reproduced); the flux-driven S
    as designed beats it **2.35×** (OOD MAE 0.68 vs 1.59, **R²=0.76 vs −0.16**); fluxes ISOLATED (no AR/state)
    still beat climate **1.25×** OOD; and holding recursion fixed, flux+AR (R²=0.76) far exceeds climate+AR
    (R²=0.43). Honest nuance: AR/persistence alone reaches OOD R²=0.55, but flux-conditioning adds decisive OOD
    generalisation on top of both climate and recursion. `⇒ ADR 0020's flux-driven premise is validated.`
- **P1 Tier-1 Step 1 — flux-conditioning training data (ADR 0020/0021).** `scripts/build_slow_flux_table.py`
  builds the per-(cell,year,patch,individual) FToS-mapped table for the flux-driven Component S from the
  tier-1 annual `ind` parquet (`/p/tmp/jamirp/emulator_global/ind_hist_seed{1,2}_all.parquet`) + the daily set
  + the slow bioclimatic boundary (`cell_year_feats.parquet`) + CO₂ — no C-binary re-run needed. `bm_inc ← npp`
  (runtime-consistent with `FToS.bm_inc`), `growth_eff` inverted from `mort_npp`, stress inverted from
  `mort_water`/`mort_temp` + daily within-year statistics, AR state from the prev-year distribution summary.
  Parameterised by `CELLS` (Hainich 42490 first, then the biome set). Committed fixture
  `test/testitems/references/slow_flux_table_hainich.csv` (82 rows) + `slow_flux_table_schema.json`.
- **Physics re-verified on real data (spec §7):** `mort_age` recompute matches the emitted column to **4.97e-8**
  and the `mort` additive identity to **8.99e-7** across 5052/5307 real Hainich rows — confirming the
  `[VERIFIED]` beech mortality parameters against the C oracle.

### Fixed
- **`docs/slow_flux_conditioning_data_spec.md` corrections + a new `[VERIFIED]` finding.** (1) §2 wrongly listed
  `stemdiam/crownarea/leafarea/fpc` as present in the annual TXT `ind` output — they are RAW-only (only
  `fpc_ind` is TXT). (2) Pinned the parameter hazards: `mort_age` longevity = JSON key `"age"` = 400 (NOT the
  leaf `"longevity"` = 2.0, a ~200× trap); `k_mort` = 0.01; `mort_prob` is saved AFTER the cap/immediate-death/
  ghost-tree overrides (components don't sum on override rows). (3) **AGE OFF-BY-ONE:** the emitted `Age` is the
  post-increment year-end age, but the row's `mort_*` were computed with the pre-increment age (`Age − 1`) —
  recompute matches to 5e-8 with `Age − 1` vs 1.4e-4 with `Age`; the table carries `age_mort = Age − 1`.
  (4) Tier-2 RAW cannot yield `bm_inc`/`nind`/`turnover` (absent from `Output_ind`); the exact path is a small
  tier-3 patch, and the budget signal is the emitted `npp`/`anpp` (not the post-allocation `pft->bm_inc.carbon`).
- **P1 wiring made runnable + a regression it exposed.** The uncommitted Tier-0 work had never been executed:
  `stand_structure_tof` referenced a `SoilColumn.soildepth` field that did not exist — added it (populated by
  `hainich_soilcolumn` from the `soildepth` kwarg it already receives; the one positional `SoilColumn(...)`
  call in `scripts/grass_drought_rooting_probe.jl` updated to match). Replacing the old
  `step!(::AbstractSlowEmulator,…)` stub with `reconcile_demography!` broke `limiting_cases_tests.jl:38`
  (it expected the old stub to throw `ErrorException`, now a `MethodError`) — updated it to assert the new
  abstract `reconcile_demography!` fallback throws. Caught by the first full SLURM suite run.
- **Multi-cell biome gate — corrected an over-strict latent-heat assertion to the true, BOUNDED invariant.**
  `test/testitems/biome_coupled_tests.jl` asserted `all(le ≥ −1e-9)`, but F's ET is built from `smoothmin`
  (fdiff_smoothops.jl) and `smoothmin(a, b, β) ≤ min(a, b)` undershoots by ≤ log(2)/β EVEN for `a, b ≥ 0`.
  In the fully water-depleted dry-season corner the semi-arid Sahel cell hits `le ≈ −0.6 W/m²` (physical
  ET = 0; this model has no dew/condensation term) — a bounded smooth-surrogate artifact of the committed F
  core, harmless to E's closure (`H := Rn − LE − G` absorbs it). Assert the bound (`le ≥ −2 W/m²`) instead of
  exact non-negativity; full CI-faithful suite green (47906 pass / 0 fail / 4 broken).
- **Component E — documented two `solve_seb` stability-correction caveats** (no behaviour change): the 0.25×
  suppression floor deliberately UNDER-suppresses strongly-stable nocturnal turbulence and is load-bearing
  for the coupled `|T_skin − T_air|` gates; the effective `g_a` is not re-clamped to `[ga_min, ga_max]` after
  the stability multiply (the bound is intentionally on the NEUTRAL conductance; safe as `g_a` is never a
  denominator and `EToF.g_a` is not consumed downstream).

### Added
- **P1 — COMPONENT S IS IN THE COUPLED LOOP (Tier-0): the project's novelty now runs (ADR 0018/0019/0020).**
  `DemographicSlowEmulator` (`src/components/slow.jl`) is the concrete slow emulator wired into
  `run_coupled_cell(...; slow=)`: each year F grows every representative cohort's CARBON at fixed `nind`
  (`grow_annual_accounted!`), then S applies its **demography** — count `N`, establishment (fills the open
  canopy `max(1−Σfpc,0)` into the shortest tree cohort, mixing a fixed sapling), mortality (growth-efficiency
  rate → litter) — routing every carbon movement through a `CarbonLedger`. **Tier-0 is deterministic,
  physical-rate, ML-free (runtime `[deps]` stays EMPTY)** and, per ADR 0020, already **flux-driven** (the
  rate channel reads `FToS.growth_eff`/`water_stress`/`soilmoist` — F's delivered fluxes — not this-year raw
  climate). **Gates met on Hainich (`test/testitems/slow_demography_tests.jl`):** Gate-1 — S runs ≥20 yr,
  energy still closes (1.4e-14 W/m²), and the count `N` evolves year-to-year while the fixed-N F baseline
  holds tree `N` constant (so the change is causally S); Gate-2 — the S↔F handoff conserves carbon to
  **~3e-12 gC ≪ the 1e-6·C_scale gate** on forced N-up / N-down / seeded-`sapwood_bg` / stagnating-cohort
  years; Gate-4 — a FIXED roster of K persistent cohorts (the structural basis of the speed-up; timing via
  `scripts/bench_slow_speedup.jl` off the login node). New `run.jl` `stand_structure_tof` re-derives the full
  `SToF` (incl. D95 rooting depth) from the S-updated population. `slow=nothing` stays byte-identical to the
  pre-S self-growing path. Independently verified by three adversarial reviewers (conservation refutation +
  correctness + test-adequacy). **Tier-1 (flux-conditioned ML inference + the warm+dry OOD benchmark) is the
  next step, now in P1 scope per ADR 0020.**
- **Durable SLURM job infrastructure — long jobs survive session teardown.** `scripts/run_tests_slurm.sh`
  runs the CI-faithful suite (`rm test/Manifest.toml` + fresh re-resolve → `Pkg.test()`) on a compute node,
  and `scripts/sbatch_julia.sh <tag> ...` submits any Julia work the same way; both warm the shared `~/.julia`
  depot on the login node first (compute nodes reach the pkg-server but not GitHub), log to `logs/<tag>.<jobid>.out`
  with a `JOB DONE … exit=N` marker, and are collectable from any later session (`squeue`/`sacct`/the log).
  Documented as the standing default in CLAUDE.md §2 + the `julia-test` skill. [VERIFIED green end-to-end.]
- **PHASE 5 — MULTI-CELL / BIOME GENERALIZATION: the coupled emulator runs across the full climate
  envelope, energy closing everywhere (DEVELOPMENT_PLAN §6 Phase 5).** `scripts/extract_biome_forcing.py`
  pulls REAL GSWP3-W5E5 daily forcing (the model-grid `_test` `.clm`, YEARCELL float32 — the validated
  grid whose cell 42490 = Hainich) for five biome-representative cells and commits small per-cell CSVs
  (`test/testitems/references/biome_forcing_{boreal_siberia,temperate_hainich,mediterranean_iberia,
  semiarid_sahel,tropical_amazon}.csv`, decade 2010–2019). `scripts/run_coupled_biomes.jl` drives the
  coupled S+F+E loop with a COMMON canopy across all cells (isolating the climate effect) and reports the
  emergent, climate-driven energy partitioning:
  - boreal (−7 °C): LE 24, H 9, low fluxes + cold skin; temperate (9 °C): LE 43, Bowen 0.26;
    mediterranean (15 °C): **Bowen 1.27 (H-dominated, summer-dry)**; semi-arid (30 °C): **Bowen 0.87,
    H 72 (water-limited)**; tropical (28 °C, 2158 mm): **LE 102, Bowen 0.10 (LE-dominated), GPP 2275**.
  - **Energy closes to ≤ 3e-14 W/m² in EVERY regime.** Gate `test/testitems/biome_coupled_tests.jl`:
    closure + physical bounds for all five biomes, plus the emergent ordering (tropical LE > boreal;
    dry-biome Bowen > tropical Bowen; tropical Rn > boreal Rn). Honest scope: a common (non-biome-
    calibrated) canopy + constant wind/psurf isolate the climate signal — biome PFT parameters + spin-up
    are the documented next step. Runtime `[deps]` EMPTY.
- **COMPONENT E FIDELITY — Monin–Obukhov surface-layer STABILITY correction on `g_a` (ON by default).**
  The neutral log-law over/under-states turbulent exchange under buoyancy; `H` is the residual and the
  worst-modeled flux (PLUMBER2), so this is the highest-value E refinement. `solve_seb` now multiplies the
  aerodynamic conductance by a smooth, bounded stability factor of the bulk Richardson number
  `Ri_b = g(z−d)(Tair−Tskin)/(Tair·U²)`: `Fs(Ri) = 1 − stab_amp·tanh(stab_k·Ri/2)` (∈ [0.25, 1.75], `Fs(0)=1`,
  C∞ ⇒ AD-safe), solved jointly with `T_skin` by a Picard-coupled fixed-graph Newton (`n_newton` 12→25).
  **Verified:** stable nights suppress `g_a` ⇒ stronger radiative cooling; unstable days enhance `g_a` ⇒ hot
  surface ventilated; closure stays EXACT (machine precision) and the aerodynamic identity holds to ~2e-9;
  ForwardDiff-vs-FiniteDifferences still matches, Float32 clean (`energy_closure_tests.jl` gains a stability
  testitem). Toggle with `SEBParams(enable_stability=false)` for the neutral limit. Runtime `[deps]` EMPTY.
- **PHASE 4 — COMPONENT E (surface energy balance + skin-temperature closure) IMPLEMENTED, and the
  end-to-end coupled S+F+E emulator RUNS on a cell (DEVELOPMENT_PLAN §6 Phase 4; ADR 0017).** The
  ESM-ready closure LPJmL-FIT lacks — the reason the whole project exists — was a stub that only threw;
  it is now real, and F+E run coupled over a cell producing the atmosphere-facing outputs.
  - **`src/components/energy.jl`: `SEBEnergyClosure` + the pure kernels `solve_seb` / `aerodynamic_conductance`.**
    Solves ONE skin temperature `T_skin` from `Rn(T_skin) = SW(1−α) + ε·LW − εσT_skin⁴` and closes
    `Rn = LE + H + G` with `H = ρc_p g_a (T_skin − Tair)` — **LE fixed by F (water-limited), H the
    residual** (the documented "no privileged residual" exception). Fixed-iteration damped Newton with a
    FIXED graph (AD-friendly, the `solve_lambda` pattern); `g_a` from the neutral log-law; `G = λ_g(T_skin
    − T_soil)` with a deep-soil-temp EWMA state E owns. Demand cap (`LE ≤ Rn − G`) implemented but OFF by
    default (uncapped ⇒ exact closure + conservation-safe; capping would drop water F committed to until
    the unused-water return is wired). **Self-contained — no Terrarium.jl runtime dep** (ADR 0017
    supersedes 0006's reuse: open AGPL↔EUPL licensing blocker + the zero-runtime-deps/offline-node
    constraints, exactly as ADR 0014 did for the fast core; physics decisions retained).
  - **`src/run.jl`: the coupled run loop `run_coupled_cell` / `couple_day!` / `stand_structure_toe`.** Per
    day: F (`FDiffFastCore.step!`) → `FToE`; structure (`SToE`) re-derived from F's own prognostic canopy;
    E (`solve!`) → `EToATM` (LE, H, G, T_skin, NBP_atm, z0) + `EToF`; **the mandatory E→F skin-temperature
    feedback** hands `T_skin` back to F's phenology soil-temp gate for the next day. Water & carbon
    conserved by F; energy closed by construction in E.
  - **`FDiffFastCore` gains two fields** — `soiltemp_skin` (the E→F feedback; NaN default ⇒ air-temp proxy
    ⇒ BYTE-IDENTICAL to the pre-feedback adapter) and `last_albedo` (write-only diagnostic so E's Rn uses
    F's dynamic albedo). Every existing baseline + the AD trainer untouched.
  - **Verified (`test/testitems/energy_closure_tests.jl` + `test/testitems/coupled_run_tests.jl`):** energy
    closes to **machine precision** (max |Rn−(LE+H+G)| = 1.4e-14 W/m² over a 13,824-case grid AND every
    day of a real Hainich year); `solve_seb` is AD-friendly (ForwardDiff vs FiniteDifferences) + Float32;
    the coupled Hainich year is physically plausible (skin near air, day heating / night cooling, growing-
    season LE > winter). Full CI-faithful suite green.
  - **DEPLOYMENT DEMONSTRATION (`scripts/run_coupled_cell.jl`):** the coupled emulator run over the Hainich
    cell (25 patches, cell-mean) for the committed decade 2009–2019 produces the full ESM output series and
    **emergently captures the 2018 European drought** — summer Bowen ratio 0.89 vs ~0.15–0.29 in normal
    years (water stress → ET suppressed → sensible heat up), with annual-mean G ≈ 0 (no spurious heat
    sink) and no multi-year drift. Writes `logs/coupled_decadal_hainich.csv`.
  - **Honest scope:** wind + surface pressure are held constant (the underlying LPJmL run never used them;
    the committed forcing CSV omits them) — sourcing GSWP3-W5E5 `sfcwind`/`ps` is the documented next step;
    `g_a` is neutral-only (a stability correction is the next fidelity step); LE uses vaporization λ for all
    ET (a snow-sublimation split is pending); the slow emulator S is not yet wired into deployment (F
    self-computes its structure); E's LE/H/T_skin against FLUXNET/PLUMBER2 is the external-data-bounded
    validation still to source (Hainich = DE-Hai). Runtime `[deps]` still EMPTY.
- **IMPLEMENTED the below-ground root-sapwood pool `sapwood_bg` + its phen-gated maintenance (opt-in,
  default byte-identical) — the §8-GO'd tree-CUE frontier (Phase-3 scale-up step 11 follow-up #11;
  `docs/sapwood_bg_design.md` §8).** F_diff omitted the C's below-ground root-sapwood pool, so it never paid
  that pool's phen-gated maintenance respiration and its tree CUE (NPP/GPP) sat ~0.51 vs the C's ~0.46.
  - **`TreePools` (10→11 fields) + `Individual` (16→17 fields)** gain `sapwood_bg_c` / `c_sapwood_bg`, each
    with a **backward-compatible constructor** (the old arity fills the pool with 0), so all ~33 existing
    construction sites — including the Enzyme SoA trainer `rollout_canopy_years_gpp` and every committed
    baseline — are **byte-identical**. `autotrophic_respiration` gains a default-0 `c_sapwood_bg` kwarg adding
    the phen-gated soil-temp maintenance `phen·c_sapwood_bg/cn_sapwood` (`npp_tree.c:51`); `daily_step_canopy`
    passes `ind.c_sapwood_bg·nind` (trees only). `individual_from_pools` + `grow_individual` carry the pool.
  - **`reconstruct_sapwood_bg(sapwood_c, height, wooddens, rootdist, soildepth)`** seeds the pool at init from
    the C's C_LATERAL allocation demand (`allocation_tree.c:163-189`, verbatim), required because the
    emulator's fixed demography can't bootstrap the C's `>0`-gated pool growth (design §4.1).
  - **Verified in-model (new `test/testitems/sapwood_bg_tests.jl`):** on the committed Hainich 2010 cell,
    seeding the pool moves tree CUE **0.512 → 0.497** (the growth-respiration-rebated decrement the model
    applies), **GPP byte-identical** (maintenance changes NPP, not GPP), CUE stays inside the gate band
    `[0.42, 0.56]`; the reconstructed pool is 531.4 gC/m² (22.7 % of above-ground sapwood) — matching the §8
    probe. Grass seeds 0 (a tree pool). Full CI-faithful suite green.
  - **Scope:** the pool is STATIC-seeded; its prognostic C_LATERAL growth + carbon-debt (design §5.4), the
    Enzyme SoA `sapbgcs` thread, and flipping the seed on by default (with baseline regeneration) are the
    deferred next steps. Runtime `[deps]` still EMPTY.

### Changed
- **RAN the mandated `sapwood_bg` quantification probe → GO (Phase-3 scale-up step 11 follow-up #10;
  `docs/sapwood_bg_design.md` §8).** The design (`sapwood_bg_design.md` §7) required a scripts-only probe to
  predict the tree-CUE decrement of adding the C's below-ground root-sapwood pool BEFORE the invasive
  `TreePools`/`Individual` struct change. `scripts/sapwood_bg_quantification_probe.jl` reuses the validated
  F_diff kernels for the baseline (the CUE-gate's own `mkind` + `rollout_daily_canopy`), reconstructs
  `sapwood_bg` per tree from the C_LATERAL demand (`allocation_tree.c:163-189`, verbatim), and adds only the
  phen-gated maintenance term (`npp_tree.c:51`). Reproduced twice, identical. No `src/`/`test/` change;
  `[deps]` still EMPTY.
  - **GO, and the design §4.2 floor-break fear is REFUTED.** Pool = 531.4 gC/m² (22.7 % of above-ground
    sapwood); ΔRa_bg = 24.3 gC/m²/yr (1.94 % of GPP); CUE moves 0.5118 → 0.4924 (conservative) / 0.4973
    (growth-resp-adjusted). Every prediction incl. the ±30 % band (0.487–0.498) stays inside the gate
    `[0.42, 0.56]` with large margin — no floor-break, struct plumbing de-risked.
  - **HONEST CAVEAT:** `sapwood_bg` ALONE closes only ~40–50 % of the 0.51→0.46 gap (lands ~0.49, ~0.03 above
    the C) — a validated fidelity refinement of an already-in-band metric, not a full closure. Full closure
    needs the coupled `rd`-gate too (design §6, which partially cancels). GO is on the physics + de-risking;
    spending the 2–3 implementation sessions now vs. after higher-value frontiers is a sequencing call.
- **SCOPED the per-PFT competitive water-supply fix + CORRECTED the §26.4 diagnosis in two load-bearing ways
  (Phase-3 scale-up step 11 follow-up #9; `docs/water_supply_perpft_design.md`, docs §26.4 CORRECTION #2).**
  A code-verified deep-read of `water_stressed.c` + `daily_natural.c` vs `daily_step_canopy`, turning §26.4's
  "FIX DIRECTION" into an implementable design. Diagnosis/design only — **no `src/`/`test/` change**, `[deps]`
  still EMPTY.
  - **The mechanism sharpens to the `aet_cor` competitive per-layer supply cap ALONE.** §26.4 bundled the fix
    as "per-PFT `wscal` + the sequential competitive cap"; the source shows the `wscal` half is DEGENERATE in
    this FIT config — `EMAX_ANGIO = EMAX_GRASS = 10.0` (`par/pft_lpjmlfit.js:116-118`) and grass shares beech's
    `beta_root=0.8`, so per-PFT `wscal` is ≈identical between grass and trees and feeds only phenology +
    allocation, not the within-day GPP solve. The entire 2018 grass overshoot rides on `aet_cor`.
  - **`-DPERMUTE` makes an exact faithful port structurally impossible on the AD/deterministic path.** The FIT
    build (`/home/jamirp/lpjml56fit/Makefile.inc:22`; all `config/Makefile.*` platform templates) re-draws the
    PFT depletion order EVERY day via Fisher-Yates on the cell RAND48 seed, so there is no deterministic
    "trees-first" to port — the C's grass suppression is an order-averaged stochastic outcome. A deterministic
    approximation would over-suppress; a faithful replication is non-differentiable + non-deterministic (breaks
    Enzyme/ForwardDiff + `determinism_tests`); and the `aet_cor` cap is a loop-carried read-modify-write
    accumulator directly on the trained-GPP reverse path.
  - **Recommendation: DEFER** behind the `FluxHooks` learned per-individual correction (already sees `wr` +
    per-individual `apar`), exactly as the §26/§26.1 grass LEVEL gap was deferred; pursue the structural cap
    only if the learned lever proves insufficient. Two scripts-only de-risking probes specified before any
    `src/` edit (a deterministic-vs-Monte-Carlo-PERMUTE `aet_cor` magnitude probe + an Enzyme-feasibility spike).
- **The `FDiffFastCore` deployment adapter reaches `rollout_canopy_years` GRASS parity (Phase-3 scale-up step
  11 follow-up #8; docs §27).** §26.3 flipped the self-driven rollout to the validated-faithful grass config
  but the `FDiffFastCore` SharedState adapter (`src/components/fast.jl`, the ESM coupling surface) still grew
  grass with the TREE machinery. Now it mirrors `rollout_canopy_years`, all **grass-only**:
  - **Per-PFT GSI phenology** (per-DISTINCT-PFT filters + lag-1 forest-floor light `grass_lf` for grass,
    carried as persisted struct state since the adapter is day-by-day), the **§26 demand-gate** (constructor
    wraps `params` via `_with_grass_gate`), **grass allocation** (`grow_grass_individual`), and **grass
    establishment** (re-seed when patch FPC < 1).
  - **Nothing regresses:** a tree-only core is **byte-identical** (per-PFT phenology for an all-id-3 patch is
    the same beech GSI; gate/alloc/establishment are `is_grass`-gated). The **AD trainer**
    `rollout_canopy_years_gpp` is untouched (a separate function; this adapter is the non-AD deployment
    surface). No new exports; runtime `[deps]` still EMPTY.
  - **Test:** the `FDiffFastCore` gate (`test/testitems/coupling_tests.jl`), previously tree-only, now also
    drives a mixed tree+grass core 4 coupled years — grass finite, non-negative, no woody pools/height (grass
    allocation ran), trees grow; establishment payoff checked as a provably-≥ differential (survival is
    light-dependent, so not asserted). Full suite **26,214 pass / 0 fail / 4 broken**.
- **DIAGNOSED the 2018 warm/dry-year grass-NPP amplitude residual — a GENUINE grass water-supply gap (Phase-3
  scale-up step 11 follow-up #7; docs §26.4).** §26.2's last honest grass residual — the matched per-year
  structure gives F/C 1.87 in the 2018 European drought (F_diff's grass over-produces) — is diagnosed with
  three cheap matched-structure SLURM probes (diagnosis only; **no `src/`/`test/` change**, `[deps]` still
  EMPTY):
  - **It is NOT a structure/leaf artifact** (`corr(F/C, fed_leaf) = −0.12`) and **NOT the fresh-soil annual
    reset** — carrying F_diff's own multi-year soil column across 2009→2019 gives byte-identical 2018 numbers
    (F/C 1.87, growing-season `wscal` 0.939). It IS a water-supply effect: the drought barely reaches
    F_diff's grass water state (2018 `wscal` 0.939 vs 0.976 normal) while its per-leaf grass NPP stays high
    (F/leaf 2.591 vs the C's 1.386, which the drought DOES suppress).
  - **Root cause (code-verified, both sides; an adversarial C-source cross-check overturned a
    plausible-but-wrong first reading).** `daily_step_canopy` runs ONE stand-level water balance: `wr` from a
    single shared `soil.rootdist` (`fdiff.jl:1467-1473`), each grass's `supply_i = emax·wr·phi` the UNCAPPED
    potential (`:1528`), and the reported `wscal = min(1, Σsupply·fpc/Σdemand·fpc)` (`:1587`) one FPC-weighted
    (tree-dominated) scalar that saturates near 1. It barely moves in 2018 because of demand-saturation
    (Σsupply routinely > Σdemand) + top-layer over-recharge (`_infiltrate` refills to field capacity each rain,
    `:812-832`, no competitive depletion). The C (`water_stressed.c`, per-PFT at `daily_natural.c:181`) shares
    the same soil column but keeps a per-PFT `wscal` (`:130-140`) AND a sequential competitive per-layer
    availability cap (`aet_cor`, `:153-177,264-275`): the dominant trees deplete the shared layers first, so
    the grass's realized supply collapses in drought — the suppression F_diff never sees. **CORRECTION:** the
    C's grass is NOT shallow-rooted (`new_grass.c:40` = full depth, `beta_root=0.8` identical to trees,
    `pft.js:494/1110`) and `gp_stand` is FAITHFUL to the C — so the gap is the per-PFT `wscal` + competitive
    supply depletion, NOT rooting depth and NOT the conductance. The rooting counterfactual (shallowing the
    stand rooting → 2018 `wscal` drop ~6×, F/C 1.87 → 1.13) is a LEVER localizing the effect to the `wr`/supply
    channel, not a match to the C.
  - **Classification.** Same FAMILY as §20/§22 (F_diff aggregates the C's per-PFT state into stand quantities)
    but on the water-SUPPLY axis: per-PFT `wscal` + sequential competitive per-layer depletion — NOT the shared
    `gp_stand` conductance (faithful here), NOT a GPP-response, parameter, or soil-memory gap. Modest,
    extreme-year effect (aggregate grass fidelity ~0.95–1.10). Fix direction: a per-PFT realized-supply water
    balance porting `water_stressed.c`'s per-PFT `wscal` + `aet_cor` competitive cap — a coupled structural
    item, deferred. Reproduction: `scripts/grass_drought_{amplitude,soilmemory,rooting}_probe.jl`.
- **The validated-faithful grass config is now the coupled-rollout DEFAULT (Phase-3 scale-up step 11
  follow-up #6; docs §26.3).** §26.2 settled that F_diff's grass FLUX is faithful to the C, but the two
  mechanisms that make it so — the §26 photosynthesis demand-gate and the §22 grass establishment — were
  still OPT-IN, so the DEFAULT multi-year coupled rollout `rollout_canopy_years` kept the deep-shade grass
  overshoot and (with the gate on) would have extincted dim-patch grass. This flips the default.
  - **`rollout_canopy_years` now defaults `grass_demand_gate=true` + `grass_estab=grass_estabparams(T)`.** A
    helper `_with_grass_gate(p, on)` reconstructs `p.water` with the gate on at the C's sharp step
    `βgpd_gate=1e8` (the value `scripts/grass_daily_curve_fdiff.jl` validated in §26.2; the rollout is the
    non-differentiable diagnostic path, so the steep sigmoid costs no gradient). Pass
    `grass_demand_gate=false` / `grass_estab=nothing` for the pre-§26.3 references.
  - **Grass-only ⇒ nothing validated regresses.** A tree-only rollout is **byte-identical** (gate is gated on
    `ind.is_grass`; establishment is a no-op with no grass — verified `leaf_c`/`height` equal to the last
    bit). The Enzyme/decadal path `rollout_canopy_years_gpp` reads `p.water` directly (gate off) and is
    **unchanged** — trainer byte-identical + gradient-stable, §21 decadal GPP unaffected.
  - **Validated self-driven over the real decade** (`scripts/grass_default_flip_probe.jl`, SLURM: committed
    Hainich 25 mixed patches, 2008 structure self-driven 2009–2019). The two payoffs: the GATE lowers total
    grass carbon 111.0 → 86.6 gC/m² (removes the deep-shade overshoot); ESTABLISHMENT restores the grass the
    gate alone would extinct (survivors **14/25 → 25/25**). Each mechanism alone is worse (gate-alone
    extincts; no-gate overshoots); together they give the gate-corrected level with no extinction, all
    physical over 11 years.
  - **Honest scope:** validates the FLIP's mechanism payoffs + that the default is the §26.2-validated FLUX
    config — NOT that the self-driven grass STRUCTURE matches the C per-patch (the §24 compressed-grass item
    is separate). The `FDiffFastCore` v1 adapter still grows grass as a tree (documented follow-up).
  - Reworked two `grass_structure_tests.jl` testitems (pre-§26.3 references made explicit) + a new "the
    default is now the faithful grass config" gate. Runtime `[deps]` still EMPTY.
- **Grass-equilibrium CO-CALIBRATION — the §25 hard-floor lever REFUTED; the faithful mechanism is the C's
  photosynthesis DEMAND-GATE; the gate EXPOSES the true residual (a grass-NPP LEVEL undershoot); establishment
  stabilizes the self-driven equilibrium (Phase-3 scale-up step 11 follow-up #3; docs §26).** §25 named a
  co-calibrated next step of three interacting faithful mechanisms — (i) the grass-gated hard GPP floor
  `max(0,agd)`, (ii) the grass GSI light-limiter season (`:linear` vs `:exp` forest-floor light), (iii) grass
  establishment. A co-calibration probe (`scripts/grass_cocalibration_probe.jl`: matched-structure per-patch
  spectrum + gate-sharpness sweep + the self-driven 11-yr equilibrium; SLURM) pins them:
  - **REFUTED — the §25 hard-floor lever (i).** Applied grass-gated it drives the deep-shade patches (3/4/18,
    C grass NPP 0.01–0.09) to **−98 / −14 / −30 gC/m²/yr** and extincts **18/25** patches in the self-driven
    rollout. Root cause: flooring the DEMAND `gpd→0` collapses `fac = gpd/1.6·co2`, so the fixed-graph λ-solve
    returns a degenerate low λ that suppresses `agd` while `rd` (from the precomputed `vm`) stays normal ⇒
    `agd − rd ≪ 0`. A hard GPP floor is the WRONG mechanism. (§25's Finding-4 "0.37×" tested a GPP-ONLY floor
    with a soft demand; the scaffolding's `βflux_grass` floored BOTH, exposing the sharper NEGATIVE pathology.)
  - **The C's actual mechanism is a photosynthesis DEMAND-GATE + phen-scaled maintenance:** `water_stressed.c:196`
    `if(gpd>1e-5 && isphoto)` computes `agd`/`rd`, else `agd=0` (photosynthesis skipped); `npp_grass.c`
    `mresp = root·nind·respcoeff·k·nc·gtemp_soil·pft->phen`. F_diff ALREADY matches `mresp·phen`
    (`autotrophic_respiration`; grass `c_sapwood=0`); the only missing piece is the gate.
  - **Committed FIX — a grass photosynthesis DEMAND-GATE** (`WaterParams.grass_demand_gate`, opt-in): a smooth
    `stable_sigmoid(βgpd_gate·(gpd−1e-5))` on the pre-floor demand multiplies grass GPP AND `rd`, zeroing both
    as demand→0 while the λ-solve keeps the bounded soft-`βflux` `fac` (no degeneracy). Eliminates the negative
    pathology — deep-shade grass NPP positive-and-suppressed, the "C<1 ⇒ F<1" shade count **0/4 → 4/4**, no
    negatives (with `:linear`). Grass-gated ⇒ trees byte-identical; opt-in (default off ⇒ byte-identical).
    Replaces the refuted `βflux_grass` knob.
  - **The gate EXPOSES the true residual:** with the faithful gate the matched-structure grass NPP is aggregate
    **0.83× the C** (median 0.48×; bright patches 12–44 % low); the §25 "1.13×" was **inflated by the soft
    `softplus(agd, βflux=50)` floor producing grass GPP on the sub-threshold (`gpd≤1e-5`) days the C GATES OFF**
    — right number, wrong mechanism. The real residual is a grass-NPP LEVEL gap on the *above-threshold* days
    (cross-patch corr unchanged ~0.973 — the ranking is right, only the level is low).
  - **Establishment (`establishment_grass.c`) is NECESSARY for the self-driven equilibrium:** without it the
    gated/shaded grass extincts 17–18/25 patches; with it **0 extinct**. Committed as an opt-in `grass_estab`
    kwarg on `rollout_canopy_years` (`GrassEstabParams`/`grass_estabparams`/`_treepools_fpc`), grass-only.
  - **`:exp` forest-floor light NOT adopted:** with the gate it drives deep-shade grass NPP negative again
    (leaf-on-but-demand-gated days pay phen-scaled root maintenance with no photosynthesis); `:linear` retained.
    The `:exp` mode (`grass_lf_mode`/`phen_params_by_pft` kwargs) is kept inert + characterized.
  - All committed knobs opt-in / grass-gated ⇒ every validated tree path is byte-identical (full suite **26200 pass / 4 broken** (26183 baseline + the §26 gate)). New gate "Grass demand-gate + establishment — §26 faithful
    deep-shade balance; trees byte-identical" (`grass_structure_tests.jl`). Reproduction
    `scripts/grass_cocalibration_probe.jl` (self-checking, SLURM). Runtime `[deps]` stays EMPTY. **Next:** close
    the grass-NPP LEVEL gap on the above-threshold days (grass shares the beech photo params); then flip the
    gate + establishment to the coupled-rollout DEFAULT once validated against a MULTI-YEAR C grass reference.
  - **Follow-up (`scripts/grass_npp_level_probe.jl`): the level gap is NOT the grass temp/albedo params.** The
    ACTIVE grass id 8 has `temp_photos {10,30}` (raises cool-temp NPP: agg 0.833 → 0.901) and `albedo_leaf 0.23`
    (lowers GPP: → 0.757) — **together ≈ 0.82**, the two nearly cancel and the ~18 % undershoot PERSISTS
    (corr ~0.975). So the residual is a deeper grass GPP-vs-light gap (Vcmax / co-limitation / λ), worst at
    intermediate shade — needs the C's daily GRASS GPP for a matched-leaf/light decomposition. The faithful
    grass `temp_photos {10,30}` + `albedo_leaf 0.23` remain a fidelity improvement for a canonical grass builder.
  - **Follow-up #2 (session 23; docs §26.1): the proposed "C re-run" is really a C RECOMPILE, and the residual
    is param-faithful + season-shaped — NOT the forest-floor light or the GSI cold-start.** No physics change;
    diagnosis + roadmap correction + two committed self-checking SLURM reproductions
    (`scripts/grass_npp_light_response_probe.jl` 1540816, `scripts/grass_gsi_warmstart_probe.jl` 1540819).
    (1) **LPJmL-FIT has NO per-PFT/per-individual DAILY GPP output** (`par/outputvars.js`: only annual `PFT_NPP`
    /`ind` + cell-total `d_gpp`/`d_npp`), so "extract per-PFT daily GPP" is impossible and a config-only re-run
    cannot make it — it needs a C-SOURCE change + RECOMPILE (a new class of work). (2) Source audit: the grass
    photosynthesis KERNEL is byte-faithful (co-limitation the exact quadratic `photosynthesis.c:150`), `apar` is
    validated (§20), and grass id 8 respiration params (`respcoeff 1.2`, `cn_ratio.root CTON_ROOT`,
    `ratio.root 1.16`) are LITERALLY beech's — so the ~18 % gap is not a parameter. (3) The undershoot is
    **gate-independent, above-threshold, and tracks the grass ACTIVE-DAY fraction**, growing with shade
    (brightest-half agg F/C 0.861; F/C 0.86 at ff 0.50 → 0.57 at ff 0.29; active-day frac 0.66 → 0.30) — a
    season-shape residual, not GPP-per-active-leaf. (4) The faithful `:exp` forest-floor light is **REFUTED** as
    the fix (brightest-half F/C 0.861 → 0.755, 7 deep-shade negatives — refutes §26's deferred `:exp` lever).
    (5) The grass GSI **cold-start is REFUTED** (5-yr continuous warm-up: year 1 == year 5 to every digit).
    **Recommendation: DEFER to the learned canopy Vcmax/λ correction (§16/§18, proven on trees) rather than
    recompile;** if a hard-coded fix is later wanted, validate a grass-phenology-season fit against a multi-year
    grass NPP reference sliced from the on-disk production `ind` output (no C re-run).
  - **Follow-up #3 (session 24; docs §26.2): BUILT the C's daily grass GPP/NPP output — and it shows F_diff's
    grass is FAITHFUL; the §26/§26.1 "level gap" was a REFERENCE-BASIS ARTIFACT.** Added two scalar daily
    outputs to the LPJmL-FIT C source (`D_GRASS_GPP`/`D_GRASS_NPP`, `include/conf.h` ids 419/420, `NOUT`→421;
    cell-mean per-day accumulation in `src/lpj/daily_natural.c` beside the `GPP`/`NPP` writes; explicit flush in
    `src/lpj/fwriteoutput.c`; registered in `par/outputvars.js`) and rebuilt the FIT binary (18 insertions/1
    deletion — `patches/lpjmlfit_daily_grass_gpp.patch`; a local shim `patches/json_object_iterator.h.shim`
    works around this cluster's truncated `json-c/0.13.1` headers). Verified the new daily output integrates to
    the stock annual `pft_npp` band-8 grass value (50 ≈ 51). **Comparing F_diff's cell-mean daily grass NPP
    (matched 2008 structure, faithful params, demand-gate ON) to the C's OWN daily grass NPP over 2009–2019:
    aggregate ΣF/ΣC = 0.95, mean per-year F/C = 0.98 (range 0.72–1.19, NO systematic bias), season length
    faithful (actR 1.02), amplitude faithful (ampR 0.96), daily r ≈ 0.86.** So F_diff's grass GPP/NPP is
    faithful; the §26/§26.1 "0.82×" came from measuring F_diff (run on 2009 forcing) against the C's 2008
    `ind`-output NPP — a year/basis mismatch (the C's grass NPP swings 28–51 gC/m²/yr year-to-year). No F_diff
    physics change; the already-committed demand-gate + faithful grass params are what make it faithful.
    Committed: the C-source patch + shim (`patches/`), the CI-friendly reference
    `test/testitems/references/hainich_grass_daily_2009_2019.csv`, and scripts `run_fdiff_grass_gpp_cell.sh` /
    `extract_fdiff_grass_daily.py` / `grass_daily_curve_fdiff.jl` / `compare_grass_daily_c_vs_fdiff.py`. The
    grass-NPP thread (§20→§26.2) is CLOSED: the grass is faithful. Runtime `[deps]` stays EMPTY.
    - **Per-year matched-structure check (honest refinement; `scripts/extract_grass_structure_decadal.py` +
      `grass_daily_curve_fdiff.jl` `GRASS_STRUCT_CSV`).** Feeding F_diff each year's OWN C structure (2009–2019,
      the tightest matched-structure+forcing test) gives aggregate ΣF/ΣC = **1.10** (mean 1.12, range 0.77–1.87),
      season faithful (actR≈1.0) with a mild AMPLITUDE overshoot in warm/dry years (2018 European drought F/C
      1.87). So the two matched-forcing tests BRACKET unity (0.95 with 2008 structure, 1.10 per-year) —
      robustly confirming no systematic ~0.82× undershoot, but the honest claim is grass faithful to ~±10–15%
      aggregate with a warm/dry-year amplitude residual (a grass drought-response effect, partly confounded by
      per-year structure reconstruction), not a clean 1.0.
- **Independent adversarial verification of the §24 → §25 grass re-diagnosis chain + §24 superseded-banner /
  factual fixes (Phase-3 scale-up step 11 follow-up #2 verification; docs §24 banner + §25 "Independently
  verified").** A 4-lens refutation workflow (each lens tried to REFUTE a load-bearing claim) + an all-25-patch
  fapar check confirmed §25 and correctly superseded §24's forward-looking lever: (1) `light()`/`light_grass()`
  are dead code in `individual:true` (`annual_natural.c:117`); (2) `reduce_grass` is fpc-only and its
  `fpc_total > 1` cap fires at **0/25** Hainich patches (max FPC 0.955); (3) grass `temp_photos` 10/30 raises
  cool-temp NPP (params can't fix it); (4) the ~2.9 gC/m²/yr floor is the `softplus(agd, βflux=50)` artifact;
  (5) **F_diff's grass fapar reproduces the C's `fpar_leafon` to 6 s.f. at every patch (ratio 1.0)** — the light
  absorption is byte-faithful, so §25's "the gap is phenology, not light" holds. The §25 fix (4.26 → 1.13×) was
  **independently reproduced** (`scripts/grass_phen_probe.jl`, SLURM: beech 4.26/0.93 → per-PFT 1.13/0.973). §24
  now carries a superseded banner (its diagnostic Findings 1–3 HOLD; Finding 4's carbon-balance lever + next step
  are refuted by §25) and two factual fixes (patch-0 FPC 0.47+0.09=0.56; grass `alphaa` 0.5 vs beech 0.55 was
  omitted). New reproduction `scripts/grass_fapar_faithfulness_check.jl` (self-checking `@assert`, SLURM). Also
  refreshed the stale `MEMORY.md` header (§25 had not updated it). Runtime `[deps]` stays EMPTY.
- **Grass-overshoot RE-DIAGNOSIS #3 + FIX — the §24 "carbon balance" is per-PFT grass PHENOLOGY (dominant),
  wired into the coupled rollout; conductance / cover / carbon-balance / respiration / params all RULED OUT
  (Phase-3 scale-up step 11 follow-up #2; docs §25).** §24 (session 19) set the next step as "a light-limited
  grass carbon balance." Five committed SLURM decomposition probes on the Hainich 2008 reference pin that
  lever — it is **two faithful mechanisms F_diff was missing, dominated by per-PFT PHENOLOGY, not any
  carbon-balance/conductance/respiration parameter**, and they interact (must be co-calibrated).
  - **Committed fix** — `rollout_canopy_years` now drives each individual's leaf phenology with its OWN PFT's
    GSI (a `pft_ids` kwarg, default grass→8 / tree→3), so a shaded understory grass runs its light limiter on
    the tree-attenuated forest-floor light and is leaf-on far less than the canopy trees (`phenology_gsi.c:30-35`;
    the FIT `new_phenology:true`). `per_pft_phenology` existed since §19 but was only in `rollout_daily_canopy`,
    not the multi-year coupled rollout. **Effect:** the matched-structure grass NPP overshoot (grass held at the
    C's 2008 leaf, trees fixed, matched fpar) drops **4.26× → 1.13×** the C with cross-patch corr **0.929 →
    0.973**. **Tree path BYTE-IDENTICAL:** the beech GSI `pft_phenparams(3) === tebs_phenparams`, so the id-3
    trees are unchanged — full suite **26174 pass / 0 fail / 4 broken** (unchanged). New gate: the
    "coupled rollout uses PER-PFT grass phenology" testitem in `grass_structure_tests.jl`.
  - **Finding — the softplus GPP floor is the DEEP-SHADE lever, necessary but NOT sufficient.** `softplus(agd,
    βflux=50)` injects `log(2)/50 ≈ 0.0139` gC/m²/day even at ~zero light (≈2.9 gC/m²/yr) — the §24
    light-insensitive floor. A hard `max(0,agd)` (the C's `water_stressed.c:259`) collapses it and extinguishes
    the deepest-shade patches, but leaves the moderate-patch overshoot (that is the phenology). Must be
    grass-gated (a stand-wide `βflux` change perturbs the validated TREE NPP 1.5 %).
  - **Finding — demand/gmin/conductance/respiration/params are faithful/inert.** The `gc·fpc − gmin·fpar`
    demand (`fdiff.jl:1518`) is byte-faithful to `water_stressed.c:194`; grass `gmin` is inert under shade; at
    matched leaf+light the grass GPP-per-absorbed-light is IDENTICAL to the validated trees' (`3.025e-6` gC/J,
    `λ=0.85`) and grass respiration matches the C (`npp_grass.c`; CUE ≈ the trees'). **Rules out §21 (per-PFT
    conductance), §22 (cover competition), §24 (carbon-balance/params).**
  - **Corrected next step (co-calibrated, NOT committed):** the grass-gated hard GPP floor `max(0,agd)` +
    the grass GSI light-limiter season (`light_base`/`grass_lf`) to the C's grass leaf-on days (the hard floor
    alone over-suppresses — matched-structure 0.37× undershoot) + grass **establishment/re-seeding**
    (S-demography) for the self-driven dim-patch grass where NPP < turnover. Reproductions
    `scripts/grass_lightconductance_decomp.jl`, `scripts/grass_carbonbalance_probe.jl`,
    `scripts/grass_phen_probe.jl` (self-checking `@assert`s, SLURM). Runtime `[deps]` stays EMPTY.

### Fixed
- **CI `test (lts)` green again — the failure was an Enzyme 0.13.189 REGRESSION, not the test tree
  (Phase-3 scale-up step 11 CI follow-up; docs §23).** Pinned `Enzyme = "0.13.0 - 0.13.188"` in both the
  root and `test/Project.toml` `[compat]`. **Root cause (conclusively bisected from the CI logs):** the
  green run `a6d6975` resolved **Enzyme v0.13.188** and the Enzyme-reverse canopy testitems
  (`nn_canopy_training_tests.jl:22` and `:145`) PASSED; the very next push (`f65ca84`, ~5 h later) resolved
  **v0.13.189** and those same items began failing with `LLVM error: Canonicalization failed`. The test
  tree was **byte-identical** across the two commits (`git diff a6d6975 HEAD -- test/` is empty), and
  `test/Manifest.toml` is git-ignored so CI re-resolves fresh each run and auto-upgraded 188 → 189. 0.13.189
  is the latest published Enzyme, so the fix is to cap at the last-good 0.13.188 until a fixed Enzyme ships.
  Only `test (lts)` is a REQUIRED check; `test (1)` (Julia 1.11, where the `VERSION < v"1.11"` guards skip
  the Enzyme canopy items) stayed green; `test (macOS, lts)` (non-required) failed for the same Enzyme
  reason and is fixed by the same pin; `test (pre)` is `continue-on-error` (allowed to fail) and fails for
  an unrelated Julia-prerelease `ScopedValue` API break (`setindex!(::ScopedValue, ::Bool)`), untouched here.
  - **Corrects the session-17 diagnosis.** Step 11 (below) attributed the failure to adding the heavy grass
    re-diagnosis `@testitem`s "poisoning" the parallel ReTestItems worker pool, and reverted the test tree to
    `a6d6975` as the fix. That is **refuted**: the revert (`6514fd7`) left CI still red with the identical
    `LLVM error` — because the cause is the moving Enzyme dependency, not the test set. (Keeping the grass
    reproduction as a SLURM script rather than a `@testitem` remains reasonable to keep a heavy compile out of
    CI, but it was never the fix for this failure.)

### Added
- **Grass-overshoot RE-DIAGNOSIS #2 — the §22 cover-competition next step targets an INACTIVE code path;
  the real gap is a light-limited grass carbon balance (Phase-3 scale-up step 11 follow-up; docs §24).**
  §22 (session 17) corrected the roadmap to porting the LPJmL grass cover competition
  (`light.c`→`light_grass.c`→`fpc_grass.c`, "kills excess grass leaf/root to litter"). Re-examined against the
  actually-active FIT code path + a per-patch SLURM reproduction on the committed Hainich 2008/2010 reference;
  no physics change (corrected diagnosis + two committed reproductions + roadmap correction).
  - **Finding 1** — the FIT config runs `"individual":true` (`lpjmlfit.js:34`), and `annual_natural.c:117`
    gates `light()` behind `if(!config->individual)` — so `light()`/`light_grass()` are **never called**. The
    individual-mode cover reduction is `establishmentpft_ind.c:168-176` → `reduce_grass()`, which is **only**
    `pft->fpc /= factor` (`reduce_grass.c`; no carbon killed) and is gated on **total** cover `fpc_total > 1`
    — inactive in the typical Hainich patch (tree+grass FPC < 1). Porting `light_grass.c` carbon-killing would
    add a mechanism the C does not run in this config — the *same class of error* §22 caught in §21.
  - **Finding 2** — the C's grass leaf is a smooth monotone function of forest-floor light (0.011 → 215 gC/m²
    across the 25 patches) satisfying the steady-state balance NPP ≈ 1.8·leaf at *every* patch — bounded by the
    light-limited carbon balance alone, no hard cap.
  - **Finding 3** — F_diff's grass genuinely OVERSHOOTS even with trees held at the C's own structure (Exp A,
    identical forest-floor light): grass leaf median **92.5 (50–194)** vs the C's **6.5 (0.01–215)**, median
    ratio **×13.9**, deep-shade patches ×100–6900, cross-patch corr **0.57** (compressed, not light-tracking).
    Real + structural — not a tree-growth or §22-repro setup artifact.
  - **Finding 4** — the mechanism is an **under-light-limited grass NPP, ~2–3× the C at matched absorbed
    light** (the grass absorbed-PAR reproduces the C's `fpar_leafon` — §20's 5-s.f. match — so the light
    *absorption* is faithful; the gap is GPP/NPP per unit absorbed light). F_diff's grass makes ~2.9 gC/m²/yr
    NPP even at ~zero leaf/light, nearly the same in a shaded vs a bright patch — a light-insensitive NPP floor.
    Through the turnover balance this becomes the extinct-vs-thriving divergence. **Vindicates session 15's
    original "~3× grass NPP" as a per-patch, per-light fact** — §22's "faithful 0.83×" was a cell-total ratio
    dominated by the few high-leaf patches, masking the shaded-patch overshoot.
  - **Corrected next step** — a **light-limited grass carbon balance** (grass GPP/NPP → 0 under deep shade,
    scaling with the already-faithful absorbed light), pinned with a light- vs conductance-limitation
    decomposition (prime suspects: the `gc·fpc` conductance term uses the un-attenuated grass cover while the
    light term uses the tree-attenuated `fpar`, `water_stressed.c:194`/`fdiff.jl:1518`; and the single stand
    `gmin` vs the C's grass `gmin=0.8`). **Grass-specific** (the tree path — decadal GPP ×1.066, §21 — stays
    byte-identical) and AD-safe. **NOT** `light.c`/`light_grass.c` cover competition (inactive), **NOT** per-PFT
    conductance (§22), **NOT** grass photosynthesis params (grass `temp_photos` 10/30 would *raise* NPP at cool
    Hainich temps). Reproductions `scripts/grass_cover_mechanism_diagnosis.jl` + `scripts/grass_lightbalance_probe.jl`
    (self-checking `@assert`s). Runtime `[deps]` stays EMPTY.
- **Grass-overshoot RE-DIAGNOSIS — the §21 per-PFT-conductance next step is REFUTED; roadmap corrected
  (Phase-3 scale-up step 11; docs §22).** Session 16 (§21) attributed the §20 self-driven grass-NPP
  overshoot (~3×) to the shared stand-mean conductance `gp_stand` "over-supplying the understory grass" and
  set **per-PFT/per-individual canopy conductance** as the next step. Re-diagnosed from the LPJmL-FIT C
  source + a faithful instrumented reproduction on the committed Hainich 2010 cell (adversarially verified —
  four independent lenses, all confirming); no physics change (diagnosis + roadmap correction).
  - **Finding 1** — the C's returned GPP uses `gp_stand` for every natural PFT incl. grass (`water_stressed.c`
    line 194 ← `gc` ← `gp_stand`); the per-PFT `gp_pft`/`gc_pft` feed ONLY the `PFT_GCGP` diagnostic
    (`daily_natural.c:187`). So a per-PFT GPP conductance is **less** faithful, not more.
  - **Finding 2** — F_diff's grass GPP **already uses `gp_stand`** (measured `gc_grass ≈ 0.75·gp_stand`; the
    moist Hainich soil, growing-season `wscal ≈ 0.99`, keeps it only mildly water-limited), exactly as the C
    does; the grass's own `gp` is only ~0.14·`gp_stand`, so a per-PFT (own-`gp`) conductance would change the
    grass GPP **~43 %** — a large **de-calibration** away from the C-faithful value, not a fix.
  - **Finding 3** — at the C's OWN structure the per-year grass NPP is **faithful** (total **0.83×**, `fpar`
    matches). The "3×" is a **multi-year structural-feedback over-growth** (leaf → LAI → forest-floor `fpar`
    → NPP), unbounded because F_diff lacks the C's grass **cover/light competition** (`light.c` →
    `light_grass.c` kills excess grass leaf/root back to `1 − tree cover`).
  - **Corrected next step: grass cover/light competition** (`light.c` → `light_grass.c` → `fpc_grass.c`),
    optionally with the supply-side per-layer soil-water competition (`water_stressed.c:153-179`) — **NOT**
    per-PFT conductance (diagnostic-only in the C's GPP, and would degrade the validated tree GPP).
  - **Reproduction `scripts/grass_overshoot_diagnosis.jl`** (self-contained on the committed 2010/2008
    reference; run off the login node via SLURM) reproduces + asserts all three: per-year NPP faithful (ratio
    ∈ [0.6, 1.3], measured 0.832); grass GPP uses the stand mean (`mean gc/gp_stand > 0.5`, measured 0.751;
    own `gp` 0.138·`gp_stand`) + a per-PFT conductance would change grass GPP `> 0.2` (measured 0.427);
    self-driven grass over-grows > 2× (leaf 6.4 → 160, ×25 over 11 yr). It is a **script, not a CI
    `@testitem`, by design** — adding the heavy per-cell conductance instrumentation to the parallel
    ReTestItems pool tripped a pre-existing Enzyme-0.13/Julia-1.10-`lts` `LLVM error: Canonicalization failed`
    in the unrelated Enzyme-reverse canopy testitems (a known Enzyme+worker fragility); the script keeps that
    compilation out of the test pool while staying committed + reproducible. Runtime `[deps]` stays EMPTY.
- **Decadal (11-year) fidelity validation of the coupled multi-year rollout (Phase-3 scale-up step 10;
  docs §21).** §18 validated the cell × multi-year objective over 3 years (2009–2011); this extends the
  committed real reference to a full DECADE (2009–2019) and answers the fidelity-horizon question — starting
  from the 2008 reconstructed 25-patch structure and self-driving 11 years (each patch grown by its own
  pipe-model allocation, kernel-isolation C-FAPAR phenology), does the coupled rollout stay faithful to the
  C's OWN per-year annual GPP?
  - **`scripts/extract_fdiff_decadal.py`** — slices `hainich_decadal_forcing.csv` + `hainich_decadal_targets.csv`
    (2009–2019 daily forcing + per-year daily C GPP/FAPAR) from the full-period single-cell daily CSV already
    on disk (no C re-run), reusing the committed 2008 start structure.
  - **★ Result: the coupled rollout stays faithful over the decade** — mean cell-mean annual-GPP ratio
    **1.066** (the inherited ~+7 % GPP-phenology level, §13/§19), each year bounded 1.01–1.11 (a mild
    mid-decade drift that recovers, **no runaway**), and **interannual correlation r = 0.86** with the C's
    year-to-year variability (tracks the real forcing, not a flat mean).
  - **Gate `decadal_validation_tests.jl`** (self-contained): the 25-patch rollout runs 11 years and stays
    physical (finite/positive/bounded per-year GPP); mean ratio ≤ 1.12; each year 0.9–1.2; per-year
    correlation with the C > 0.7. Runtime `[deps]` stays EMPTY.
  - **Two investigation findings recorded** (roadmap, no code change): the §20 self-driven **grass-NPP
    overshoot is structural** — carbon-only run, grass fPAR matches the C, light-limited, root C:N/respcoeff
    equal the beech values; the residual is the **shared stand-mean conductance** (`gp_stand` over-supplies
    the understory grass), needing per-PFT conductance, not a parameter fix. **[SUPERSEDED by §22 /
    scale-up step 11:** this `gp_stand` attribution is **refuted** — the C's GPP itself uses `gp_stand`, and
    F_diff's grass GPP already matches it (`gc_grass ≈ 0.75·gp_stand`, so a per-PFT conductance would
    *de-calibrate* it ~43 %); the per-year grass NPP is faithful (0.83×) and the overshoot is a multi-year
    cover-competition gap; per-PFT conductance is NOT the fix.**]** The **Enzyme-on-Julia-≥1.11 guard-lift is blocked upstream**
    — the latest Enzyme 0.13.187 still raises `EnzymeInternalError` on the mutating canopy reverse pass on
    Julia 1.11.7.
- **Prognostic GRASS structure — the `allocation_grass.c` port (Phase-3 scale-up step 9; docs §20).** The
  multi-year rollout previously grew only trees; grasses were held fixed and — because the `ind`-output
  reconstruction gives grass rows `leaf_c = crownarea = nind = 0` (grass is a per-**area** cohort) — were
  structurally dropped from the multi-year path. Grass leaf/root carbon are now PROGNOSTIC via a faithful
  differentiable port of the LPJmL-FIT NATURAL-veg annual grass sequence `turnover_grass.c` →
  `allocation_grass.c` (`annual_grass.c:29-30`) — essential for running F_diff on grasslands.
  - **`grow_grass_individual(alloc, tree, bm_inc_ind, wscal_mean)`** — closed-form carbon math: leaf turns
    over daily + root monthly (annual pool `→ pool·(1 − rate)`); reproduction reserve removed before
    allocation; natural-veg full-reallocation partitions `bm_net` at `lmtorm = lmro_ratio·(lmro_offset +
    (1 − lmro_offset)·min(1, wscal))` with the no-reallocation caps + negative-leaf branch.
  - **`grass_allocparams()`** — temperate C3 grass (id 8) verbatim from the active `par/pft_lpjmlfit.js`
    (`lmro_ratio 0.8`, `lmro_offset 0.5`, leaf turnover rate `1.0`, root `0.5`, `reprod_cost 0.1`).
  - **`grass_treepools(agb, vegc, sla)`** — per-area reconstruction (leaf = `agb`, root = `vegc − agb`,
    `crownarea = nind = 1`); with this convention the existing `fpar`/`fpc` recompute reproduces the C
    (recomputed grass `fpar = 0.03042` vs the C's `0.0304233`). Wired into `rollout_canopy_years`/
    `rollout_canopy_years_gpp` via a `galloc` kwarg; the grass branch fires only for `is_grass` individuals,
    so all committed TREE baselines + the Enzyme trainer are **byte-identical**.
  - **Allocation faithfulness (the deliverable):** golden-vs-`allocation_grass.c` across every branch
    **< 1e-5**; carbon conservation **4.4e-16**; fed the C's grass NPP the allocation equilibrates to the
    C's grass leaf:root **0.791 vs 0.799** (the `bm_inc_ext` crutch, as the tree allocation was validated
    before its self-NPP was calibrated in §13).
  - **Honest finding:** F_diff's SELF-computed grass NPP is ~3× the C's (grass shares the beech
    photosynthesis/respiration params), so a self-driven grass overshoots — the grass-NPP calibration is the
    documented next step (parallel to the tree NPP calibration, §13).
  - **Gate `grass_structure_tests.jl`** (5 testitems): param fidelity + reconstruction; golden + conservation
    + bounds; equilibrium-fed-C-NPP → C structure; ForwardDiff (scalar + through the coupled multi-year
    grass-inclusive rollout) vs FD; Enzyme reverse through the grass-inclusive multi-year path (guarded
    `VERSION < 1.11`). Runtime `[deps]` stays EMPTY.
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
