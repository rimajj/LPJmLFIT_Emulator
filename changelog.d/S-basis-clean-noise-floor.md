### Changed

- **Component-S trait gate (`scripts/noise_floor_vs_emulator.py`) is now basis-clean and
  attenuation-corrected (ADR 0030).** The seed1-vs-seed2 per-cell trait floor is measured on the emulator's
  OWN stem population (two `MODE=copula` builds differing only in `SEED`), gated by a `seed1-basis ≥ 0.99`
  cross-check against an independent parquet re-derivation (now **1.000** on all four axes, was
  0.973/0.488/0.761/0.092). `floor_r` is a realization-vs-realization correlation, so the reported ceiling is
  `√(rel_P·rel_Y)` from each side's split-half reliability, and the headline metric is `(GAP, r_center)` plus
  the between-cell dispersion ratio. Exact per-axis headroom (ids-1..5 population): **Wooddens +0.226 ·
  minwscal +0.153 · SLA +0.115 · D95max +0.102**.
- `scripts/sbatch_python.sh` forwards the full env-knob set (`MODE`, `SCENARIO`, `BOUNDARY_WINDOW`,
  `STEM_CAP`, `SOIL_TBL_PATH`, `LAI_TBL_PATH`, …). Previously an unlisted knob passed as a command prefix
  reached the wrapper but **not** the job, so e.g. `MODE=copula` silently built a *count* table.

### Added

- `scripts/diagnose_ind_type_composition.py` — global per-`Type` census of the `ind` ground truth: stems,
  cells, cells lost entirely, and the per-cell trait-median shift induced by a PFT-set restriction.

### Fixed

- Withdrew two published Component-S claims (ADR 0030): the trait floor is **not** 0.90–0.97 on the
  population the emulator trains on (Wooddens is **0.694**, so the "+0.40 headroom" was ~3× inflated), and
  **D95max is not "at floor"** (+0.102 to the reachable ceiling, not +0.021). The "per-cell-median
  instability" explanation of the low basis cross-checks was also wrong — the cause is PFT-set truncation
  (ADR 0031). Split-half analysis shows the floor is **trajectory divergence**, not finite-stem noise.
