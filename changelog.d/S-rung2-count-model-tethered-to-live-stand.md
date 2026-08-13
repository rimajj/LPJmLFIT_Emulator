### Added

- **Rung-2: the count model's target is tethered to the live stand count, so the warming-response question
  is unanswerable as run — and the arms' stand structure departs by 2×** (line S, ADR 0184). Closes the
  action ADR 0182 pre-registered, with no new model run: the substitution harness already recorded its own
  count target at every rendezvous, so four of the five arms were already measured. New
  `scripts/diagnose_rung2_map_on_rec_stand.jl` supplies the one missing arm (LPJmL-FIT's own roster) by
  replaying the recorded dumps through the *shipped* feature assembly and forest, gated bit-identical
  against the live harness log in the year before any arm diverges; new
  `scripts/diagnose_rung2_map_target_response.py` scores what the map ASKED FOR against what the stand
  REACHED. **Headline:** all 767 rung-2 runs used `--n-prev=roster`, which hands the model the live stem
  count, and the model then returns a count within ±5 % of it in ~85 % of patch-years — its target *is* the
  live count to ±2.3 %. So the two quantities the probe was meant to separate are the same quantity, the
  basis check is passed by a persistence null that learns nothing (12/12 cells, slope 1.06), and the
  pre-registered verdict branch is **overridden as NO VERDICT**. This reconciles three earlier results as
  one mechanism — with the live count the model is accurate but mute, without it expressive but
  mis-levelled — and narrows the earlier "indistinguishable from doing nothing" to a statement about the
  configuration rather than about what the model learned. **Second, independent finding:** nothing anchors
  the stand's size/age structure, and by 2100 the arms hold ~15 % fewer stems but **+99–106 % above-ground
  biomass and +47–84 % mean age** than FIT (the do-nothing null +312 %/+160 %), growing monotonically from
  ~+38 % at the historic leg — a real conditioning defect that no count-based statistic on this line
  detects. A never-before-run `--n-prev=predict` smoke (12 jobs) confirms the map's count state decouples
  from the live stand there (±24 %, ±28 % late century) ⇒ the question *is* answerable in that mode, and the
  full 264-job matrix was submitted. `scripts/rung2_s_demography_harness.jl` gains the repo's standard
  `PROGRAM_FILE` guard so its definitions can be reused instead of copied.
