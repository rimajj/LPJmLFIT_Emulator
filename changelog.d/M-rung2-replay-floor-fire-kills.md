### Fixed

- **Rung-2 replay: the kill set no longer claims fire's victims, and the mortality half of the demography
  interface now replays exactly** (line M, ADR 0121, supersedes ADR 0120 §5's replay numbers). The harness
  derived its kill set as "any `post`-phase tree with `isdead == 1`", but `isdead` has more than one author:
  `fire_tree_ind` also sets it, *after* the hook's decision point. Replaying fire's victims as demographic
  kills both claimed a death the narrow interface does not own and moved the per-cell random stream — fire
  draws `erand48` only for trees that are not already dead, so pre-killing its victim changes how many draws
  it consumes. The roster dump gains a third phase, `mort`, written after the demographic hazards and before
  fire; kills are read there. Terminal stems (replay ÷ recorded, cell 42490, 25 patches, 20 years):
  `kills` **1.37 → 1.000, exact** — identical in every initialised per-tree column and every cell-state
  column, no year differs; `recruits` 0.91 → 0.907; `both` 1.30 → 1.367.

### Added

- **The roster dump's patch record now carries the three channels of cell-level state no per-tree record can
  carry** (line M, ADR 0121): the per-cell RAND48 stream position, the parity of `gasdev()`'s
  process-global spare-deviate cache, and checksums of the top-AGB seedbank contents. This is what turned
  ADR 0120's open question — identical state, different demographic answer — from a claim into a
  measurement: at the divergence onset the `pre` phase agrees in every one of them and the roster, and the
  `post` phase does not. New scorer `scripts/diagnose_rung2_cellstate_equality.py`; `MODE=record` added to
  `scripts/run_rung2_replay_arm.sh`, because a rebuild that changes the dump schema invalidates the recorded
  baseline every arm is scored against.

### Changed

- `cell->treelen_old` / `treelist_old` are documented as **uninitialised memory in every real run** and are
  deliberately not dumped: their sole writer sits behind `if(config->isequal)`, which is TRUE only when
  every cell in a run shares identical coordinates (and is hardwired FALSE for a single cell), so the branch
  is dead and `mergesapling()` has no caller anywhere in the C source.
