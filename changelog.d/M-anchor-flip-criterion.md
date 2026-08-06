### Added

- **Line M — the level anchor's flip criterion is measured, and it FAILS (ADR 0056, answering ADR 0103 §6).**
  `scripts/biome_slow_oracle_probe.jl` gains two anchored arms (`anchor = 0.5` and `0.1`) beside the existing
  free and `n_prev`-teacher-forced ones, a clause-by-clause evaluation of line S's pre-registered criterion
  with thresholds fixed in-script before the run, a mechanism check that the anchor actually fired, and a
  per-year report separating the two competing explanations of the one cell that breaks.

### Changed

- Nothing shipped moves. `anchor` stays opt-in and default `0`; no committed baseline, artifact or fixture
  was regenerated, and `src/` is untouched by this change.

### Notes

- **The anchor fires perfectly and the level error it closes is larger than the single-cell evidence showed.**
  Stand density × `patch_area` / the DRF's own target is **1.001 in all five biome cells** at `a = 0.5`, versus
  **1.46–2.21** free-running — so ADR 0103 §2's 41 % over-density is a Hainich number, and across biomes the
  free-running stand sits **46–121 %** denser than its own count model's absolute prediction (worst
  `tropical_amazon`, 2.21×). No gate in this project reads that level.
- **Criterion (iii) carbon closes** in every cell and every arm by six orders of margin; **(i) and (ii) fail.**
  (i) fails structurally — the drift lives in the DRF's *target*, which F's canopy drives, and ADR 0103 itself
  states the anchor does not close ADR 0102 mechanism (A); the criterion asked for something the mechanism
  never claimed. (ii) fails on a new finding: anchoring closes a `density → fpc → target → density` loop that
  is benign in four cells (`tropical_amazon` steps down then recovers, Hainich's gate metric improves
  4.5 → 3.2 noise floors) and **runaway in `semiarid_sahel`** (`fpc` 0.281 → 0.057 monotone, target
  13.5 → 4.46, E/C 1.19 → 0.33). That is the Sahel's fourth independent symptom.
- `anchor = 0.1` is the worst available setting at line M's 10-year horizon: 15–46 % of the level correction
  and essentially none of the drift benefit, while still costing the Sahel.
