---
name: slow-drf-pipeline
description: >
  The recurring pipeline for the Component-S production DRF (the flux-driven slow demography emulator's
  learned count/marginal model): build a RUNTIME-CONSISTENT training table, fit + SERIALIZE the zero-dep
  native-Julia DRF, load it into the coupled loop, and run the Gate-3 oracle vs the LPJmL-FIT C truth at
  Hainich. Use whenever training/retraining the Component-S DRF, changing its feature set, serializing or
  loading a DRF.Forest artifact, scaling the DRF from Hainich to global, or wiring the Gaussian copula
  recruit-trait sampler. Names the artifacts: scripts/build_slow_runtime_table.py,
  scripts/train_slow_drf.jl, scripts/build_slow_oracle_reference.py, DRF.save_forest/load_forest,
  test/testitems/references/drf_forest_hainich.drf, hainich_slow_oracle_{traits,counts}.csv, cell 42490,
  the flux_feature_vector order, and the age_mean-counter train/inference trap. ADR 0023.
---

# slow-drf-pipeline — train / serialize / load / oracle-gate the Component-S DRF

The Component-S `FluxDrivenSlowEmulator` (`src/components/slow.jl`) sets its demography TARGET from a
trained flux-conditioned DRF (`src/drf.jl`, ADR 0022). This is the loop that produces + validates that DRF.
Everything is pure Base (empty runtime `[deps]`, ADR 0014); the DRF submodule is `using LPJmLFITEmulator.DRF`.

## The pipeline (each step names its script + gate)

1. **Build the runtime-consistent training table** — `conda activate py311_new; CELLS=42490 SEED=1
   OUT=/p/tmp/jamirp/slow_runtime python3 scripts/build_slow_runtime_table.py`. Writes `X.f64`/`y.f64`/
   `manifest.txt` (a zero-dep raw-Float64 payload the Julia trainer reads with pure Base IO).
2. **Fit + serialize** — `OUT=/p/tmp/jamirp/slow_runtime julia --project=. scripts/train_slow_drf.jl`
   (login-node fast for one cell; `scripts/sbatch_julia.sh` for global). Writes the COMMITTED artifacts
   `test/testitems/references/drf_forest_hainich.drf` + `..._meta.txt` (nfeat/nhead/boundary/n_init/golden).
3. **In-loop gate** — `test/testitems/slow_production_drf_tests.jl` loads the `.drf` and drives the coupled
   Hainich decade (targets INSIDE the training band ⇒ runtime-consistent; N moves; carbon ~1e-12; energy
   ~7e-15; deterministic). `drf_serialization_tests.jl` gates the bitwise round-trip + the committed golden pairs.
4. **Oracle reference + gate** — `python3 scripts/build_slow_oracle_reference.py` extracts the Hainich C
   ground-truth S-owned marginals → `references/hainich_slow_oracle_{traits,counts}.csv`;
   `test/testitems/slow_oracle_tests.jl` compares the coupled S Height distribution to the C truth as an
   IQR-normalized quantile-RMSE **drift alarm** (~0.31; recursive-vs-nonrecursive, Hainich-only — NOT parity).

## Load-bearing gotchas (this is why the DRF is trusted)

- **Feature order MUST match the runtime `flux_feature_vector`** (`src/components/slow.jl`): `[bm_inc_cell,
  growth_eff, water_stress, soilmoist, hmean, hmax, agb, lai, fpc, age_mean, n_prev, <boundary tail…>]`
  (ADR 0020 §6 — S is conditioned at runtime on the channel it was trained on). A mismatch ⇒ the DRF is fed
  OOD inputs and predicts nonsense while STILL conserving carbon (the error is masked). The in-loop test's
  "targets inside the training band" assertion is the runtime-consistency check.
- **`age_mean` is a DEGENERATE runtime elapsed-year counter** (`s.age` is a fixed roster, +1/yr, never reset
  on recruitment) — train it as `Year − firstyear`, **NOT** mean tree `Age`. Training on mean(Age) is a
  silent train/inference feature-distribution shift (the single biggest correctness risk; ADR 0023 §3).
- **`water_stress` = 1 − wscal_mean** (matches `fast.jl`), NOT the `mort_water` inversion the OOD-experiment
  table used. **`soilmoist`/`lai` are documented PROXIES** (const 0.7 / Σ per-crown ind-LAI) until the global
  pipeline sources `soilmoist` from daily `swc` and `lai` from the C annual `LAI_STAND` (Phase-2 SLURM).
- **Ind `npp`/`agb` are already per-m²** (×nind baked in by the C writer), so per-patch ROW SUMS are per-m²
  stand totals matching the runtime — no `nind` factor (there is no `nind` column; CLAUDE.md §3).
- **Serialization is TEXT `.drf`, never `*.bin`** (git-ignored). `DRF.save_forest`/`load_forest` round-trip
  bitwise (Julia's shortest decimal). Keep `load_forest` closure-free (inlined `pos` cursor) — the JET 0.11.6
  boxed-closure gate (CLAUDE.md §2). The committed Hainich `.drf` is a DEMO (≤~200 KB); the global forest is
  DVC on `/p/tmp/jamirp/emulator_global/drf/`, not git.

## Copula recruit-trait sampler (built, not yet wired)

`DRF.GaussianCopula`/`chol_lower`/`norminv`/`normcdf`/`copula_uniforms!`/`sample_copula!` draw correlated
recruit traits {logHeight, Age, SLA, Wooddens, beta_root} via the Cholesky of a correlation matrix mapped
through per-axis flux-conditioned `predict_quantile` marginals. `GaussianCopula(R)` FACTORS a correlation
matrix (`from_corr=true` default); pass `from_corr=false` for a raw Cholesky `L`. Its consumer — assigning
drawn traits to APPENDED recruit cohorts — needs the membership append/merge path (design risk #5); until
then the fixed-roster establishment keeps frozen traits, so the sampler is not yet in `reconcile_demography!`.
