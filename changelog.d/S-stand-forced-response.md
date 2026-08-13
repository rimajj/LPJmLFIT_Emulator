### Added

- `scripts/slow_stand_forced_response_probe.jl` — hands the tree-count emulator the original model's own
  forest description under both climate scenarios, with no simulation loop anywhere, and asks whether the
  warming response appears. It splits the emulator's inputs into the four groups that different parts of
  the system compute at run time — the daily physics, the forest's own carbon pools, the emulator's own
  memory of last year, and the climate — and moves one group at a time from present-day to end-of-century
  values, so the answer says *which part of the system has to carry the response*. Covers 51 767 of the
  54 020 forested cells, holding out whole cells, and writes its predictions in the format the existing
  scoring script reads so every arm is scored in one process against the same reference.

### Measured

- **The tree-count emulator is a description of the forest, not a response to the weather.** Handed the
  original model's own forest, the count it predicts follows that model's warming-driven change almost
  exactly (a slope of 0.99 against the truth) — but essentially all of that comes from the forest
  description itself (biomass, cover, height, age). The two climate inputs contribute a slope of 0.016 and
  the four daily-physics inputs 0.037. The count is close to an arithmetic consequence of the forest it
  sits in, so its response to warming is inherited rather than learned. This confirms, on 51 432 cells and
  with a completely different instrument, what an earlier 12-cell check had found for the climate inputs
  alone, and extends it to the physics inputs, which had never been tested.
- **Even given a perfect forest, the emulator recovers only 29 % of the original model's total warming
  response** (0.292 against 0.707 for the shipped version), and it gets the tropics wrong by a factor of
  −2.5. So the response is not lost in how the emulator is trained to predict; redesigning what it predicts
  — the plan this measurement was run to price — is not where the problem is.
- **A correction to an earlier conclusion of our own.** An earlier control run was summarised as showing
  that no warming response reaches the count emulator through the forest. Read at the source, that control
  froze only the four climate inputs; the eleven others stayed live on a forest the original model was
  still growing under a warming climate, so any response arriving that way was counted as "drift" by
  construction and was never separated out. The control's own numbers and its conclusion about the climate
  inputs stand; the broader sentence built on it does not, and it had propagated into two later documents
  and the working handoff.
- **Removing last year's tree count is worse than it looked.** An earlier measurement priced that change as
  tripling the climate signal. Scored on the statistic the deliverable is actually judged on, the same
  change takes the total warming response from 0.707 to 0.292 and the tropical response from −0.47 to
  −2.48. Both readings are correct — the small climate channel does triple — because most of the shipped
  model's apparent response was simply repeating last year's answer.

### Fixed

- The probe's own verdict originally keyed on a statistic that a do-nothing baseline scores just as well on
  (all four arms, that baseline included, land between 0.97 and 1.03), so it announced success for an arm
  the binding statistic rates as partial. The correct thresholds were already written into the file before
  the run and simply were not the ones used. The script now refuses to announce a verdict and names the
  statistic that decides it.
- Recorded the trap that the scoring script writes its summary into a committed shared reference file by
  default, and that running it for count arms alone silently deletes every trait row from that file. It now
  prints the redirect that avoids this. Nothing was committed; the file was restored.

Nothing shipped changed: no defaults were flipped, no trained artifact was regenerated, and both jobs write
only to scratch.
