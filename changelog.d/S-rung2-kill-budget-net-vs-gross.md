### Added

- `scripts/diagnose_rung2_kill_budget.py` — identifies why the rung-2 substituted demography kills 3.5–4.2×
  too few of the biomass-bearing trees (ADR 0187 §3), from the arm logs plus the `REC` dumps, with no model
  run. Five panels behind ADR 0185 §5's imported completion+coverage gate: the derived-a-priori self-test on
  the uniform arm, the ρ-clamp incidence, the `ρ ≥ 1` gate, the budget-vs-nominations decomposition, and
  FIT's own gross mortality and recruitment by a count identity over the `grow`/`mort`/`post` phases.

### Changed

- Nothing. No flag flipped, no default moved, no committed baseline regenerated, no `src/**` change.

### Fixed

- Nothing shipped was broken. Two basis errors were found and fixed *inside the new scorer* before its
  numbers were published, and both are recorded as reusable traps (ADR 0188 §8, skill `rung2-dump-analysis`
  traps 5g/5h): a recruit identity that ignored ADR 0123's deferred kills, and a gate stricter than the
  identity it was gating.

### Notes

- **ADR 0188** — the mortality budget is the NET count change, not the GROSS flux. ADR 0187 §B's first
  hypothesis (a kill quota formed on the >5 m emitted population under-killing the whole roster) is
  **refuted** by the harness's own algebra: ρ is a scale-free survival fraction applied to the whole-roster
  density, and the uniform arm spends its quota in full (realized/implied **1.004 ± 0.009**, 0.51 σ, against
  the 0.425 H1 requires). The ρ clamp is not binding either. What is wrong instead: the decision is gated
  `if ρ < 1.0`, so **42–46 %** of patch-years produce an empty kill list and a further **27.9 %** of `S1`'s
  years hit `_hazard_tilt`'s reported `θ = 0` give-up; and the budget `(1−ρ)·n_now` approximates the NET
  count change `K − R` while the flux that moves biomass is the GROSS `K`. Measured on FIT's roster: gross
  mortality **5.65–5.96 %/yr**, recruitment **4.62–6.46 %/yr**, net **−0.54/+0.25 %/yr** — near-stationary
  in count while turning over ~6 %/yr — against an operator budget of **0.78–1.02 %/yr**, i.e.
  **6.4–7.6× short**, with FIT's non-negotiable deaths alone overdrawing the whole budget **4.1–5.3×**. A
  mortality-only operator driven by a next-year count target structurally cannot express gross mortality
  flux, because recruitment is 78–108 % of mortality. The next action and its criterion are pre-registered
  with the lever's current size measured; the count channel (ADR 0186 §8.8) is not re-opened.
