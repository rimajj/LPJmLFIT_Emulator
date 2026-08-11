### Added

- **Line S (rung 1):** `scripts/rung1_count_ratio_arm.jl` — the ratio-target count arms R0 (teacher-forced)
  and R1 (state-recursed), identical to the A0/A1 arms except for the target `n_t / n_{t-1}` and the
  multiplicative reconstruction, with a free `max |R1 − R0| = 0` gate on the first-year rows.
- **Line S:** `scripts/rung1_response_decay.py` gains three panels — the one-step control's per-band columns
  at every horizon (closing ADR 0114 §5.4), the arm's drift at exact lead resolved by scenario, and the
  response computed at **matched lead depth** (only leads present in both scenarios, equal weight).

### Changed

- **Line S:** `scripts/rung1_response_decay.py` no longer divides `n_living` by the patch-ensemble size — the
  column is already a per-patch stem count. Every ratio it has ever produced is unaffected (the factor
  cancels); its level panels were 25× too small for their "stems/patch" label. ADR 0114 §1's mean row is on
  the old scaling and is flagged, not re-scaled.

### Documented

- **ADR 0115** — the count recursion's drift is **scenario-asymmetric**: it survives exact lead matching, so
  it is not the unequal-chain-length artefact ADR 0114 §2 named, and at lead 18 it manufactures 90 % of
  LPJmL-FIT's own global count-response magnitude with the opposite sign. Training on the year-on-year ratio
  instead of the level is refuted in accuracy, drift, scenario asymmetry and aggregate response — the level
  target is itself the level anchor. Next experiment (no refit): name the conditioning feature that carries
  the scenario signal into the error.
