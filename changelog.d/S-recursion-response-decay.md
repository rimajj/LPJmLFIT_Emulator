### Added

- **Line S / rung 1 — the count emulator's validity horizon is measured** (ADR 0114).
  `scripts/rung1_response_decay.py` reuses the recursion arm's own predictions and the proven per-row keys — no
  retraining, ~2 minutes — to answer why self-feeding destroys the warming response. It is **not** the model
  collapsing onto an average: after 80 years of feeding on itself the prediction still carries 90 % of the
  truth's between-patch spread and correlates with it at 0.94. What breaks is a slowly-saturating level drift
  (+0.16 stems per patch) that happens to be the same size as LPJmL-FIT's entire global count response, and that
  is not the same size in the two climate scenarios. Measured horizon: **the stem-count warming response is
  faithful for about three years of self-feeding, degraded by ten, and inverted by forty** — and at a single
  step it is right in every latitude band (0.90–1.07), which is the strongest evidence so far that the count
  model does have a warming response at all.
- Consequence recorded as a decision: **do not "fix" the recursion with a variance-preserving or
  distribution-sampling count predictor** — any such proposal has to refute the spread measurement first. The
  next experiments target the drift's dependence on lead time instead.
