### Changed

- **Line M / ADR 0059 — the C-faithful leaf-on water scalar is now the DEFAULT, and it is worth 3.5× of the
  Sahel's carbon.** `WaterParams.wscal_leafon` flips to `true`; guardrail 4 is re-served by the **opt-out**
  (`wscal_leafon = false` reproduces the pre-ADR-0051 expression exactly, and both arms run on every CI
  pass). This closes the flip line S GO'd explicitly and that CLAUDE.md's guardrail-4 corollary names by
  name as "a defect on a timer" — it shipped opt-in while ADR 0051 measured it, then sat off for a week
  with each line recording the flip as the other's to schedule.

  **A full CI-faithful suite with only the default flipped failed 3 assertions out of 111,237** — the
  opt-in guarantee itself, and `semiarid_sahel`'s two pinned signatures. Nothing else in the tree moves.
  Four of five cells shift by ≤ 1.2 %; the Sahel's GPP goes **0.386 → 1.367 gC/m²/day (+254 %)**, which
  against the C's own tree GPP of 1.513 is **0.26× → 0.90×**. The pre-flip expression scored every leaf-off
  day as fully water-stressed, and that number drives the leaf:root allocation `lmtorm` — so the cell with
  the most leaf-off days starved its own leaf pool. **The honest cost is in the same cell:** its ET goes
  from 1.19× to 1.26× the C's, i.e. the flip trades a large carbon gain for a ~6 % worse ET overshoot
  (ADR 0053's open item (a), unchanged in kind).

  **Why this was worth doing beyond faithfulness:** until now the gate pinned a configuration *no published
  F-vs-C comparison ever ran* — every oracle probe on this line passes `wscal_leafon = true` explicitly, so
  the default arm was the one nobody scored. A default and a measurement basis that disagree is the
  train/inference-shift hazard in its cheapest form, and it survived precisely because both were
  individually documented. Line S's independent endorsement is on the conditioning side: Hainich's annual
  `water_stress` goes 0.3050 → 0.0034 against a C truth of 0.0014 and a trained band of [0, 0.04315].

  Also aligned with line E's parallel default flip (ADR 0075): the pin probe and the coupled gate no longer
  hardcode a ground-heat flag where they meant "the package default", and the stale "the default is off"
  comments are corrected. A control arm that hardcodes a flag stops being a control the moment the default
  moves — which is exactly what ADR 0075 §4 paid for.

  `biome_coupled_tests.jl` item 2's pinned LE/GPP are regenerated for the new defaults
  (`scripts/biome_ensemble_pin_probe.jl`, job 1718307), in their own commit.
