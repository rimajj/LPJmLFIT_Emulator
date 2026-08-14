### Added

- Line S: `scripts/diagnose_rung2_count_precision_budget.py` — measures whether a next-year
  per-patch count target can ever be precise enough to drive a gross mortality budget, from state
  already on disk (no model run). Carries the derivation, the reproduction gate against ADR 0188
  §4, two floors (a cell-and-year conditioning floor and a strict lower bound on the irreducible
  demographic realisation error built from LPJmL-FIT's own per-stem hazards), three refutation
  panels, and the integer-quantisation floor. ADR 0241.
- Line S: `scripts/diagnose_rung2_perstem_mass_decomp.py` — the matched-age / matched-height
  decomposition of the rung-2 arms' per-stem mass excess, with the full profile by height quintile
  of LPJmL-FIT's own terminal stand. ADR 0241 §6.

### Changed

- Line S: the learned count model is retired from the rung-2 **mortality** path (its other
  consumers are unchanged). The required precision for a ±20 % kill budget is ~1.2 % per
  patch-year, which is 2.7–3.9× inside the irreducible realisation floor and 4.1–4.9× inside the
  integer atom of a stem count; LPJmL-FIT's own per-tree hazard applied as a rate replaces it.
  ADR 0241.
