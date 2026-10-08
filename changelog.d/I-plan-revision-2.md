### Changed

- **`EXECUTION_PLAN.md` revision 2: parallel method arms on one yardstick, with response-identifying data first
  ([ADR 0096](docs/decisions/0096-the-plan-becomes-parallel-arms-on-one-yardstick-data-first.md)).** Owner
  instruction 2026-10-08 (*"try all promising methods"*). The goal is unchanged (ADR 0094/0106/0107). The
  2026-08-07 error-attribution ladder is no longer the order of work; its findings are kept as a record (plan §11)
  and its one-variable-per-arm rule stands. New shape: Track D (a constant-climate control of the original, a 3rd
  and 4th member with daily outputs, a fixed ~1000-cell stratified panel, a climate-contrast ensemble built from real
  change patterns; the Germany 2071–2100 re-run pending the owner), Track Y (one scorer and one set of nulls for
  every arm), Track A (eight annual-demography arms, from the hybrid with the original's physics to rollout-trained,
  dataset-aggregation, free-run-calibrated and direct non-recursive models), Track F (the re-implemented physics made
  fast, a learned daily water–carbon model, few-patch fluxes), Track C (300-yr stability gate, complete coupling
  interface incl. soil respiration and fire, equilibrium initialiser, online self-test) and Track U (calibration
  against independent members). Arms are dropped only at pre-registered decision points. Each line's `## NEXT` now
  opens with its assignment.

### Documentation

- **`docs/review_comparison.md`: the emulator compared with 115 published emulator and hybrid studies** (the
  systematic review at `~/dgvm-review-corpus/`), dimension by dimension, with quotes and line numbers, ten ranked
  proposals, and where this project is ahead of the published state of the art. Basis of ADR 0096.
