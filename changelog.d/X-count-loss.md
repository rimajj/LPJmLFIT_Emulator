### Added
- Line X: count-aware losses (Poisson, Tweedie) for the tree-count model of the anchored direct map
  (`explore_panel_a7.py cnt`; ADR 0316 §12). Result: the same trade-off as the log target — the sparsest cells improve
  (3.45× → 2.19× a second run's error) while typical cells and the area total get slightly worse (1.35× → 1.39×; total
  1.9 % → 3.2 %). No loss weighting brings tree count near a second run; the best arm is unchanged.
