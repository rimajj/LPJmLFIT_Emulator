### Changed

- **Component S — the level anchor's pre-registered flip criterion was scored on the wrong quantity, and is
  re-specified** (ADR 0104). Evaluated verbatim on the 5-cell coupled oracle the criterion FAILS, reproduced
  independently by lines S and M to the same digits. It scores the count model's *prediction*, which the
  anchor never writes; the anchor multiplies the roster density. On the corrected yardstick — the stand's
  density against the C's per-patch mean ÷ `patch_area` — the anchor improves **all five cells at all three
  settings**, mean `|ln(density/truth)|` **0.679 → 0.478 / 0.361 / 0.329** for `a` = 0.1 / 0.25 / 0.5.
  Revised recommendation **`anchor = 0.25`** (was 0.1). The default stays **off**: a modal-patch
  initialisation confound must be cleared on the patch-ensemble driver first.

### Added

- `scripts/biome_slow_oracle_probe.jl` — an opt-in level-anchor arm (`ANCHOR=<a>`) with the pre-registered
  criterion evaluated mechanically, plus the physical-stand table the corrected yardstick needs. With
  `ANCHOR` unset the script runs its previous two arms and prints its previous reports unchanged.
- `scripts/biome_resilience_probe.jl` — opt-in `lvl0`/`lvl1` arms scoring the level anchor's effect on
  year-to-year memory, reported as distance to the C oracle. These are **not** the existing `anchor0` arm
  (which is teacher forcing). Mean `|AC − C's AC|` **0.0439 free → 0.0405 anchored**; the anchor does not
  buy its level fix with dead dynamics. With `ANCHOR` unset the battery and its committed fixtures are
  unchanged; with it set, fixture writes are redirected to scratch so no committed baseline can move.
