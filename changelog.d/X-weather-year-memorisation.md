### Added
- Line X (Germany emulator prototype): `scripts/explore_de_contin.py` (what carries the year-to-year continuation of
  a negative-growth streak: cell-grouped vs YEAR-grouped cross-fits of streak-breadth and streak x weather terms) and
  `scripts/explore_de_gsign_yb.py` (refit of the sign head's weather booster with early stopping on held-out years);
  sampler options `sign_cal="k"`/`"kb"`/`"y"` in `explore_de_gquant.py`, `explore_de_death_onestep.py` accepts them.
  Finding: the sign head's year-to-year skill on the seed-2 test member (corr 0.98) was memorised weather years —
  that member shares the training member's weather — and on unseen years it is ~0.78 (same GCM) and 0.43-0.63
  (ACCESS); neither a streak-specific weather term nor year-held-out early stopping raises it. Every weather-driven
  timing score must now be taken on unseen weather years.
