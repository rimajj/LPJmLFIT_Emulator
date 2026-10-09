### Added
- Line X: a relative-error (log-ratio) training target for the anchored direct map (`explore_panel_a7.py logt`,
  `logt_mix`; ADR 0316 §11). With it on biomass per tree only, the per-cell biomass-per-tree error falls from 1.42× to
  1.26× a second run's (bad cells 1.71× → 1.26×) and the pass rate on held-out climate models rises 0.193 → 0.207.
  `explore_tolerance_measure.py` gains `PRED_ARMS`.
