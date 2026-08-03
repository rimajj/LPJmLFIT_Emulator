### Added

- **Spatially BLOCKED cross-validation for the recruit-trait copula evaluation** (line S, ADR 0040 —
  the gate on promoting ADR 0038's 14-column artifact). `scripts/eval_slow_copula.jl` gains
  `FOLD_MODE=hash|block`, `BLOCK_DEG`, `BUFFER_DEG`, `CELL_LATLON` and `MTRY`. Blocked mode assigns folds to
  B°×B° tiles and then removes from each fold's TRAINING set every cell within `BUFFER_DEG` of any of that
  fold's test cells, so the evaluation can distinguish an environmental response from spatial interpolation
  off the test cell's immediate neighbours. All five knobs default to the pre-existing behaviour and the
  `pred_<axis>.f64` bytes are **verified byte-identical** with them unset (six of six files on the 50-cell
  smoke table).
- `scripts/build_slow_spatial_controls.py` — provisions the three position artifacts the experiment needs
  from `grid.nc`: `cell_latlon.txt` (plain text, because the eval has no Parquet/NetCDF dependency),
  `cell_geo_tail.parquet` (a pure-position conditioning tail) and `cell_env_perm_tail_s<seed>.parquet`
  (the true env tuples permuted across cells — same width, same cell-level 6-way joint, zero geography,
  asserted by a lexicographic bijection check and a neighbour-correlation report).
- `scripts/blocked_cv_folds_probe.jl` — gates the fold machinery before any compute is spent: re-derives the
  realized nearest-training-cell distance by great-circle brute force (independently of the eval's own grid
  dilation) and asserts the buffer is honoured, plus a block-size × buffer design sweep.
- `scripts/diagnose_slow_neighbour_skill.py` — scores an EXISTING matched prediction pair stratified by each
  test cell's distance to its nearest training cell, at zero new compute.
- `scripts/build_slow_copula_env_augment.py` gains `ENV_PARQUET` / `TAIL_TAG` so the ablation control tails
  ride the same verified transform instead of a forked script, with a new one-row-per-`Cell` gate on the
  input (the `group_by("Cell").mean()` is the identity for a per-cell tail, so a duplicated `Cell` would
  otherwise be silently AVERAGED into a tuple present in neither marginal).

### Fixed

- `lines/S/STATE.md` recorded the pooled `t8` copula baseline as "60-tree/50k/d14"; the evaluation that
  produced those predictions ran at **40** trees (`run_pooled_slow_copula.sh` defaults). The 60 is
  `train_slow_copula.jl`'s artifact setting, printed later in the same log.
