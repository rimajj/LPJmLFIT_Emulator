### Added

- Two diagnostics that answer, from the trained artifact alone and with no LPJmL run, why the tree-count
  emulator shows no warming response — closing the question the frozen-climate control left open
  (ADR 0179, ADR 0180).
  - `scripts/slow_climate_partial_dependence_probe.jl` — sweeps the shipped count model over its two
    climate inputs, on its own training rows, using the exact warming excursion the response campaign was
    fed. Reports a channel-liveness panel (split counts per input) first, a pooled between-cell panel and a
    within-cell panel side by side, and a live-channel scale anchor in the same units, so "flat" is
    falsifiable.
  - `scripts/slow_nprev_ablation_probe.jl` — a one-variable arm that neutralises the previous-year
    tree count in place (not dropped, so the fit's internals are unchanged) and retrains the control in
    the same process, to price a retrain before buying it.

### Measured

- **The count model's climate input is wired up and carries almost nothing.** The forest splits on the two
  climate inputs 77 440 times (10.2 % of all splits, thresholds spanning the whole global range), so it is
  not blind to climate by construction — and yet moving climate across its entire global range changes the
  predicted stem count by 0.28 stems, and moving it by each cell's own historic-to-2100 warming changes it
  by 0.057 stems: 4.4 % of what a channel that does work produces on the same rows, and under 10 % of the
  original model's own response at 9 of 12 cells. A third explanation added before the run — that a global
  fit learned climate as a location label rather than as a response — was also refuted. ⇒ the defect is the
  training target and feature set, not the coupled loop.
- **Removing the previous-year count triples the climate response and is still ~7× short.** 0.084 → 0.238
  stems (4.7 % → 13.5 % of the original model's response), larger at 13 of 15 cells, for 0.018 of predictive
  skill. Reported as a partial result, not a fix: it buys magnitude, not direction (7/12 → 8/12 cells with
  the right sign), so it does not on its own justify a global retrain.
- **The stem count is nearly determined by the stand it sits in.** With the previous-year count removed
  entirely, predictive skill is 0.9620 — indistinguishable from simply repeating last year's answer
  (0.9623), because the remaining inputs describe the same year's stand and a stand of a given biomass,
  cover, height and age holds a nearly fixed number of trees. So the count model's climate inputs are a
  small correction on top of a stand-to-count map, and the warming response has to arrive through the fast
  physics moving the stand.

Nothing shipped changed: no defaults were flipped, no trained artifact was regenerated, and both probes
write only to scratch.
