### Added
- Line X (Germany emulator prototype): a quick cell-level LSTM over yearly cell statistics
  (`scripts/explore_de_rec_lstmstats.py`); padded per-patch tensors and a permutation-invariant neural set model with
  its one-step trainer and engine stepper (`scripts/explore_de_sh_tensors.py`, `explore_de_nset_{model,train,stepper}.py`);
  the structured design's free-run diagnosis and a recruit acceptance filter (`scripts/explore_de_struct_*.py`); and
  three ways to make the quantile growth-efficiency model cheaper — truncation, a residual start from the mean head,
  and distillation (`scripts/explore_de_gquant.py`, stages `shrink`, `r*`, `d*`). Findings: the LSTM reproduces cell
  statistics well on held-out places but shows no transferable scenario contrast; the neural set model's recruits fall
  short for the same grass reason as the tabular design; the structured design's stem deficit is the missing recruit
  acceptance; none of the three cheaper quantile models keeps its accuracy.
### Fixed
- `scripts/explore_de_sh_patchheads.py` splits the recruit entry table in a fixed row order; the structured design's
  stepper acceptance hook no longer crashes on first use.
