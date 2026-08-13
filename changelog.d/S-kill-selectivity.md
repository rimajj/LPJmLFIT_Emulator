### Added

- `scripts/diagnose_rung2_kill_selectivity.py` — scores WHICH trees the rung-2 emulator kills against
  LPJmL-FIT's own kills, off the `mort`-phase roster dumps already on disk (no model run). Six panels:
  a provenance gate against the harness's own audit log, the mass-selectivity statistic
  `LAMBDA = kill_frac_m / kill_frac_n` on the discretionary population stratified by patch-year, the
  size-conditional mortality rate profile in the reference arm's own height quintiles, standardized
  selection differentials, the ADR-0186 §8 reachability clause, and a pre-registered verdict gated by a
  derived-a-priori self-test on the uniform-thinning arm (ADR 0187).

### Changed

- ADR 0186's framing "the emulator kills the right NUMBER of trees and the WRONG trees" is **narrowed**:
  the kill set is measured to be **not** size- or mass-biased (mass selectivity 0.93/1.00 against FIT's
  0.90; near-zero selection differentials; the size-conditional rate profile has FIT's shape). The
  shortfall is the mortality **rate** — 3.5–4.2× too few discretionary deaths, 58 % of FIT's annual mass
  flux, which compounds to 2.83–2.90× over the 81-year leg and so more than covers the observed +90 %
  biomass excess. ADR 0186's own numbers are unchanged (ADR 0187).
