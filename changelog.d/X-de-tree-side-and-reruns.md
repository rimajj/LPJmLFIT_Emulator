### Added
- Line X (Germany emulator prototype): one-step tree check by size (`scripts/explore_de_tree_onestep.py`), an
  instrumented coupled arm (`scripts/explore_de_tab_probe2.py`) with same-tree input-swap attribution
  (`scripts/explore_de_tree_attrib.py`), and a cohort x size split in `scripts/explore_de_recruit_drift.py`. Finding:
  after 2000 the emulator's small trees grow at the right MEAN rate (the earlier excess was in the median only); the
  early excess comes from the tree's own previous-year growth state, not the grass.
- Re-runs of the original model that print every tree incl. those below 5 m (`scripts/explore_de_crerun.py`,
  `scripts/explore_de_crerun_collect.py`, private Dec-2025 build + one writer switch), gated row by row against
  production.

### Fixed
- Re-runs whose MPI tasks spread over nodes of different processor types diverge from production from the first
  year; the driver now pins a run to one node (`--nodes 1`). Documented in CLAUDE.md §3.
