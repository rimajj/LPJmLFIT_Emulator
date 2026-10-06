### Added
- Line X (Germany emulator prototype): `scripts/explore_de_certain_rule.py` (which of the original's two certain-kill
  rules fires, from the bad-growth counter recovered out of `mort_npp`) and `scripts/explore_de_streak.py`
  (negative-growth streak starts and continuation, original vs a free run); `explore_de_death_onestep.py` reports
  continuation by counter; `explore_de_gquant.py` gains per-counter sign recalibrations (`signc`, `signc2`; sampler
  options `sign_cal="c"`/`"c2"`). Finding: the original's mortality pulses are all from its 5-bad-years counter rule
  and come from streaks started together years earlier; the emulator starts streaks correctly but under-reproduces
  the year-to-year swing of their continuation, which a recalibration cannot fix (falsified twice).
