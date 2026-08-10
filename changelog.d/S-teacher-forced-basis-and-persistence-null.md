### Added

- **Line S / rung 1 — the persistence null control for the count response** (ADR 0112).
  `scripts/build_count_persistence_null.py` writes the predictor "copy LPJmL-FIT's own stem count from last
  year, learn nothing" into a scorable arm directory (shared provenance symlinked, so it cannot drift from the
  table it is a null for), and `scripts/diagnose_truth_yardstick.py` now accepts a comma-separated `COUNT_DIR`
  so an arm and its null are scored in one process, on one cell set, on one basis.
- **Line S / rung 1 — the flux-forced, state-recursed count arm (A1)**:
  `scripts/rung1_count_recursion_arm.jl` feeds each year's own count prediction in as the next year's
  previous-year count, per (Cell, Patch) chain, changing nothing else — same folds, same forests, same seed —
  and prints error against LPJmL-FIT as a function of lead time, which the one-step basis cannot produce.
- **Line S — a proven key attachment for the frozen production count table**:
  `scripts/attach_count_table_keys.py` recovers the (Cell, Patch, Year) key of all 121 495 658 rows by
  replaying the table builder's own key pipeline and verifying it row-for-row against `y.f64`,
  `X[:, n_prev]` and `cells.i64` before writing anything (100.0000 %, both scenarios). The chain the recursion
  needs is not inferable from the frozen table, and both plausible shortcuts corrupt the sparse cells.

### Changed

- **Every published global Component-S fidelity number now carries a forcing basis label** (ADR 0112). All of
  them are **one-step, C-forced**: the count model is handed LPJmL-FIT's own roster and fluxes for the same
  patch-year, including its previous-year count, and the out-of-sample evaluation predicts each row from that
  row's own features. Measured consequence: a persistence null reaches R² 0.9622 against the production model's
  0.9824 and a deattenuated count response slope of 1.029 against 1.006 — so "the count response is faithful
  per cell" is retired as evidence about the emulator, and the wrong-signed regional count responses of
  ADR 0111 §5b are shown to be present in the null as well. The one statistic that still discriminates is the
  aggregate area-weighted response ratio (0.536 null / 0.691 model / 1.0 target).
- **`EXECUTION_PLAN.md` rung 1's arm list is superseded** — its arm B is what is already measured, and the
  missing control is arm A. Replacement ladder in ADR 0112 §4b. That file is integrator-owned; this is an
  integration point, not an edit.
