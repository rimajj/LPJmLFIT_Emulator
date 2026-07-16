# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
