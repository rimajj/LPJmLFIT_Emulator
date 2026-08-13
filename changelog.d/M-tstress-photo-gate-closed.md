### Added

- `scripts/diagnose_tstress_photo_gate.py` — scores the LPJmL-FIT `tstress < 1e-2` photosynthesis gate
  (`photosynthesis.c:54-61` and `isphoto()` at `water_stressed.c:196`) against F_diff's thresholdless
  linear `tstress` factor, over the five biome cells' own committed daily forcing and PFT composition.
  No simulation, no SLURM, sub-second. Carries the reference basis, the closed-form derivation, the
  falsifiable hypothesis, the conservatism argument for its bound, and a per-cell `CAN BIND` /
  `CANNOT BIND` verdict so a zero explains itself
  ([ADR 0138](docs/decisions/0138-the-tstress-photosynthesis-gate-is-mechanically-negligible.md)).

### Changed

- `src/fdiff.jl` — the comment beside `tree_demand_gate` no longer asserts from code structure that the
  linear `tstress` factor emulates "that HALF" of the C's gate; it now cites the measurement. Comment
  only, no behaviour change.

### Notes

- **ADR 0135's photosynthesis shortlist item (b) is CLOSED without a port and without a flag.** F's
  `agd`, `rd` and `vm` are exactly proportional to `tstress` — verified against F's own kernel to 1.6e-9
  — so the C's gate discards at most 1 % of an affected day's full-suitability value. At the hot end the
  threshold coincides with the `temp ≥ temp_co2_high` hard cutoff **by construction**
  (`k3 = ln(99)/(temp_co2_high − temp_photos_high)`), which F already carries, so only the cold end is
  live: below **+3.0 °C** for the tropical evergreen and **−6.0 °C** for every other tree.
  Assimilation-weighted, that is **0.046 %** of the annual total at `boreal_siberia`, **0.0063 %** at
  Hainich, and structurally **0** at the other three cells, whose temperature never reaches the
  threshold — 65× and 480× below the +3.0 % residual it was shortlisted to explain.
- **`boreal_siberia` carries the method finding: 47 % of its days are gated and the effect is still
  0.046 %**, because the gated days are the darkest and coldest of the year. A day count is not a
  magnitude — scored on incidence this item would have read as the largest term on the shortlist.
- Only item (c) (the phenology trajectory) remains on that shortlist. The count of faithful-but-worse
  terms in the compensating-error search is unchanged at four; this is not a fifth.
