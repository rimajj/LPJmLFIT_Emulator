### Added
- Line X (Germany emulator exploration): big-tree growth attribution of the tabular free run — one-step check
  (`scripts/explore_de_growth_onestep.py`), an instrumented stepper gated identical to the analysed run plus a
  grass-replay counterfactual (`scripts/explore_de_tab_probe.py`), and a same-tree input-swap attribution
  (`scripts/explore_de_growth_attrib.py`). Finding: the free-run grass model is the largest single cause of the drift.
