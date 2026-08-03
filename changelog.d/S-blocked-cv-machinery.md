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

### Changed

- **ADR 0040 rejects the decision rule proposed in ADR 0038** for the address-vs-response question. The
  fold-mode-matched address null under `block(15°,5°)` is Wooddens **0.140/0.210**, not the `r≈0.80` that
  ADR 0038 named — that figure is a pure address's skill under `mod(hash(cell),k)` folds, so using it as a
  blocked-fold threshold is a reference-basis error (guardrail 7) that would have declared a strong response
  an address. The corrected rule is pre-registered before any forest result is read.
- **A second promotion gate is added: the warming Δ-response.** `emu_r` is a level statistic and
  `sd(Δobs)/sd(level)` is only 0.198–0.306, so the existing gate is 3–5× more sensitive to spatial
  interpolation than to the transient response a coupled run depends on. Measured from existing predictions,
  the shipped env-conditioned artifact damps the mean Wooddens warming shift by **37 %** (tile-cluster
  bootstrap CI excludes zero) and both arms capture only 24–62 % of the transient pattern against a
  0.87–0.96 split-half ceiling.
- ADR 0038's saturation fit and its "0.889 needs ~1052× the table" extrapolation are re-labelled
  **unresolved**: they rest on +0.002/+0.003 `emu_r` increments against a spatial-sampling sd of order 0.01,
  with no seed replication anywhere in the ladder.
