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
  ADR 0111 §5b are shown to be present in the null as well. On the aggregate area-weighted response ratio the
  two are also close (0.685 null / 0.707 model / 1.0 target), so on every response statistic the null matches
  the production model — the only place the learned model clearly wins is accuracy.
- **`EXECUTION_PLAN.md` rung 1's arm list is superseded** — its arm B is what is already measured, and the
  missing control is arm A. Replacement ladder in ADR 0112 §4b. That file is integrator-owned; this is an
  integration point, not an edit.

### Added (arm A1, ADR 0113)

- **The rung-1 recursion arm is measured.** Making the count feed itself (`rung1_count_recursion_arm.jl`,
  4 min on 48 cpus over 121 495 658 rows) leaves the *level* almost untouched — error against LPJmL-FIT grows
  from 0.60 to 1.72 stems per patch over 80 years and then stops growing, with a mean bias never above 2 % —
  but the *warming response* collapses and reverses sign: the area-weighted global count response ratio goes
  from +0.707 (one-step) to **−0.226**, and every latitude band gets worse. So for stem counts the level is not
  what fails the acceptance criterion; the response is.
- **The per-cell response slope is retired as a discriminator for counts.** Three arms whose out-of-sample R²
  spans 0.982 → 0.962 → 0.918 and whose global response ratio spans +0.707 → +0.685 → −0.226 all score a
  deattenuated per-cell slope between 0.976 and 1.029.
- **No level anchor for the global count recursion** — there is no runaway to anchor at this scale, which
  contradicts the natural reading of the earlier single-cell drift result and agrees with ADR 0105.

### Fixed

- **A second, unweighted definition of the aggregate response ratio was still live in the count path** of
  `scripts/diagnose_truth_yardstick.py` — the trap ADR 0111 closed on the trait side. It agrees with the
  area-weighted definition on the production arm (0.691 vs 0.707) and disagrees by a factor of four on the
  recursed arm (−0.93 vs −0.226). Now one definition, area-weighted, `n/d` below signal-to-noise 3.
  Consequence: ADR 0111 §4b's "area-mean 0.691×" is the unweighted number mislabelled; the area-weighted value
  is 0.707, and the conclusion it supported is unchanged.
