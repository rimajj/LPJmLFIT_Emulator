### Added

- **Line M / M2 (in progress):** `scripts/extract_cell_slow_init.py` — folds the per-cell Component-S
  initial state (`n_init`, `age0`) and the 4-column slow boundary
  (`eco_diag_gdd_5, tas_cold_month, soil_depth, co2`, in the runtime
  `flux_feature_vector`/`live_flux_cond` tail order) out of line S's `cell_meta.parquet` sidecar and into the
  committed `references/M_cells.csv`, so the multi-cell coupled driver and its CI gate read one tracked table
  instead of a `/p/tmp` DVC artifact. Re-verifies the artifact's trained boundary order against its own
  `*_meta.txt` rather than assuming it, and **aborts** if any requested cell is absent from the pinned
  `cell_meta` (a cell the pinned DRF never saw has no honest `n_init`/`age0`).

### Fixed

- **CI (integrator, `main` `47c6407a`):** pinned `JET = "0.9, 0.11"` in `test/Project.toml` `[compat]`.
  JET **0.12.0** removed the `target_defined_modules` configuration that `test/jet_tests.jl` passes, so
  `test (1)` (Julia 1.12) errored with `JETConfigError` **repo-wide** on a fresh resolve — reproduced
  identically on `line/M` and `line/O` with no test-tree change, while `test (lts)` stayed green (JET 0.11+
  needs Julia ≥1.12, so 1.10 resolves 0.9.20). Second instance of the "CI resolves deps fresh ⇒ a missing
  `[compat]` absorbs a breaking bump" class after Enzyme 0.13.189.

- `julia-test` skill: the "run the full suite" recipe hard-coded `cd` to what is now the **integrator**
  worktree, so following it from a line session would have submitted a suite testing `main` instead of the
  branch under test.
