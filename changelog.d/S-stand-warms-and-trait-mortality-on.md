### Added

- **Line S:** `scripts/diagnose_rung2_stand_warming.py` — scores whether each rung-2 arm's OWN stand shifts
  between the historic and ssp370 legs, against LPJmL-FIT's own stand at the SAME cells, from the roster
  dumps already on disk (no LPJmL run). Reconstructs the six `flux_feature_vector` stand features per
  (year, patch) at the `grow` rendezvous with the runtime's own formulas, gates on complete legs, runs the
  mandatory liveness panel first, and carries a declared DRIFT CONTROL (the same shift between the two
  halves of the historic leg, where there is no warming excursion). Caches one small `.npz` per dump, so the
  ~38 GB text scan is paid once (ADR 0182).
- **Line S:** `scripts/diagnose_rung2_ported_certain_set.jl` — measures the ported per-individual hazard's
  certain-kill set against LPJmL-FIT's own on the same rosters, reaching `TraitMortality.mortality_hazard`
  as the shipped name rather than copying it, plus a ZEROED-STRESS arm that evaluates the hazard exactly as
  the coupled loop runs it (ADR 0183).

### Changed

- **Line S: `trait_mortality` now defaults to `true`** in `FluxDrivenSlowEmulator`
  (`src/components/slow.jl`), so the ρ-thinning runs on the ported FIT per-individual hazard rather than one
  composition-preserving factor. ADR 0176 §4's pre-registered flip criterion (≥ 12 cells, recall AND
  precision ≥ 0.8 of the ported certain-kill set against FIT's own) is met by a wide margin: over
  **1 568 744 stem-years at 15 cells**, both scenarios, recall = precision = **1.0000** with mean
  |Δhazard| = **5e-18**, and still **recall 0.909–0.972 at precision 1.0000** with `water_stress`/
  `temp_stress` zeroed, which is how the coupled loop actually feeds it. **Guardrail 4 is re-served by the
  opt-out `trait_mortality = false`** — every control arm wanting the pre-0183 operator must pass it
  explicitly instead of relying on the default (ADR 0183). Measured blast radius of the flip, from the full
  CI-faithful suite run with only the default changed: **5 assertions of 275 605**, all in
  `test/testitems/slow_trait_mortality_operator_tests.jl` and all one cause — that file's control arm relied
  on the old default and became a second copy of the arm. No conservation gate, AD gate or committed
  baseline moved. The control now passes `trait_mortality = false` explicitly and a new assertion checks the
  new default on the constructor.

### Fixed

- **Line S:** ADR 0176 §4's premise is corrected — the rung-2 `S0h`/`S1` arms were already using the PORTED
  hazard, not FIT's own (`rung2_s_demography_harness.jl:539` reads `Tree.mort`, which is
  `TraitMortality.mortality_hazard`; the harness never reads the dump's `mort_prob`). Only an inline comment
  said otherwise (ADR 0183 §2).
- **Line S:** the line handoff's claim that a small stand shift in a rung-2 arm would indict the fast core is
  corrected — the Julia fast core never runs in a rung-2 arm, where the C grows the stand (ADR 0182 §6).
