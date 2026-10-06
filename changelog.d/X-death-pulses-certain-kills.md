### Added
- Line X (Germany emulator prototype): death-deficit probes — `scripts/explore_de_death_decomp.py` (at-risk vs rate by
  size class), `explore_de_death_pulse.py` (patch clearings vs diffuse deaths), `explore_de_death_terms.py` (the
  original's per-tree hazards and its two certain-kill rules), `explore_de_death_certain_dump.py` (a free run's own
  certain kills), `explore_de_death_onestep.py` (death one step ahead at true vs sampled growth); `explore_de_gdrift.py`
  gains `--swap-y0/--swap-y1`. Finding: the 2016-25 death shortfall is the original's certain-kill pulses in bad
  years, which the emulator reproduces in timing but at about two thirds of their size.
