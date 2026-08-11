### Added

- **Line S (rung 2):** `scripts/diagnose_recruit_trait_axis_coupling.py` — decides whether the recruit-trait
  axes the rung-2 hook leaves on LPJmL-FIT's own draw cost the interface anything. It audits each axis's
  variability per PFT **first** (a constant column and an uncoupled trait produce the same degenerate
  correlation but have opposite implications), then measures within-(PFT, age-bin) coupling among survivors
  and the one-year selection differential.

### Documented

- **ADR 0117** — line S's reply to the rung-2 demography interface line M raised (and recorded unanswered in
  its own ADR 0120): **S returns a per-individual survival probability and M draws**. A count-only interface
  cannot carry the trait response even in principle, because that response is within-PFT, within-age-class
  differential survival; ranking on the C's own hazard would make any trait result the C's selection rather
  than the emulator's. The existing opt-in trait-dependent mortality operator already emits exactly this
  shape, so the null arm and the selection arm share one wire format and no new model is needed — which also
  unblocks line S's own arm C, whose only blocker was the lack of a roster harness. Records the risk to
  measure first (the learned count target may leave the selection no room) and the free identity gate the
  harness makes available.

### Fixed

- **Line S:** the recruit-axis diagnostic no longer reports a selection differential for a constant column —
  its first run printed −284 standard deviations for an axis with exactly one distinct value, which is
  arithmetically impossible and was a near-zero-variance denominator. It now prints `const`.
