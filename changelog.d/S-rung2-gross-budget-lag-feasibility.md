### Added

- **The derivation ADR 0188 required before building the gross mortality budget: a lagged recruit count
  carries it exactly, but the budget must not be rectified per patch-year
  ([ADR 0189](docs/decisions/0189-the-lag-is-not-the-obstacle-the-rectified-budget-over-kills.md)).**
  `scripts/diagnose_rung2_gross_budget_lag.py`, SLURM job 1788149, **no model run** — 12 cells × 2 legs of
  `REC` `predict` dumps joined to the count model's own replay on that roster, plus `S1`'s own dumps for the
  arm-stand check, behind ADR 0185 §5's imported completion+coverage gate (30 300 patch-years, 0 unmatched).
  **The recruit term is exactly observable at the rendezvous**: `age` at the `grow` phase is post-increment
  and establishment sets age 0, so the age-1 cohort IS last year's recruits — verified at **29 700 of 29 700
  patch-years (100.000 %)**, needing no dump-format change, no index tracking (hence immune to the
  `ERROR043` duplicate-key fault) and **no integration point with line M's `rung2_apply.c`**. The lag is
  safe on three independent grounds: the count departure it introduces **telescopes** to one year's
  recruitment (1.7 stems, 6.4/7.8 % of roster, against 131.6/667.0 % for the current operator), the
  discretionary capacity it buys is **3.525 %/yr against a 1.5 %/yr criterion** and 6.0× the current
  0.590 %, and FIT's own recruitment **rises +39.8 % between the legs** (4.619 → 6.456 %/yr), so the term
  hands the operator a budget that grows under warming — a response channel the net budget does not have.
  ⚠ **But the instrument as pre-registered would over-kill:** rectifying the budget every patch-year is
  convex, so an unbiased-but-noisy budget over-spends — implied total mortality **6.999 %/yr against FIT's
  own 5.961** on FIT's stand and **8.292 vs 5.001** on the arm's own, i.e. a roster falling to **0.62×** and
  **0.11×** over the 81-year leg. The cause is the count model's per-patch-year error, not the gross-budget
  idea: with a perfect target the same budget reproduces FIT's gross kills and net exactly. Spending from a
  running account instead (a "grow" year repays an earlier overspend rather than being clipped to zero)
  lands total mortality at **5.817 vs 5.961 %/yr**, roster **1.70×**, capacity **2.702 %/yr** — and on the
  arm's own stand **1.493 ± 0.180 %/yr, AT the criterion rather than above it**, which is stated in advance.
  Two gotchas: **a derived anchor must be derived through the same nonlinearity as the statistic** (a
  pre-registered oracle band was obtained from a linear identity against a convex statistic, so it "failed"
  for a property of the instrument — the band was kept, printed and replaced by a perfect-input arm whose
  answer is an exact identity, |diff| 0.0000, rather than moved); and **model the gate, not just the
  budget** — assuming certain deaths are always honoured put the current operator's implied roster at 0.45×,
  contradicting ADR 0186's measured on-target count, and fixing it made the panel agree with that published
  number. No flag flipped, no default moved, no baseline regenerated, no `src/**` change.
