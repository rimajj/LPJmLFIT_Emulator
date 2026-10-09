### Added
- Line X: the panel more-data test scored (ADR 0316 §10). Five more climate models and two more runs of the original raise
  the anchored direct map's pass rate on held-out climate models from 0.161 to 0.193 (prediction held; the climate models
  carry it), but on the "as close as a second run" measure it stays 1.35× (tree count) and 1.42× (biomass per tree) a
  second run's error. `explore_tolerance_measure.py` gains a `PRED_SET` knob.
