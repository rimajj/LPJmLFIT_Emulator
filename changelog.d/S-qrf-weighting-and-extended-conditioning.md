### Added

- **`DRF.predict_quantile` gains the Meinshausen (2006) quantile-regression-forest leaf weighting, opt-in via
  `qrf = true`** (ADR 0037), threaded through `DRF.sample_copula!` and reachable from
  `scripts/eval_slow_copula.jl` with `QRF=1`. The default remains the pre-existing equal-weight
  concatenation, so every committed artifact, golden draw pair and reference baseline is bitwise unchanged.
- **Opt-in EXTENDED recruit-copula conditioning**, in lockstep on both sides: `COPULA_ENV_COLS` in
  `scripts/build_slow_runtime_table.py` appends per-cell `cell_year_feats` columns after the boundary tail,
  and `live_flux_cond_env(env)` in `src/components/slow.jl` builds the matching runtime row. Both default to
  an empty tail, which reproduces the existing 8-column conditioning exactly. Implemented as a policy
  FACTORY rather than a new field because `RecruitCopula.cond` is already pluggable (ADR 0025) — so this
  needs no struct change, no `.rcop` format change, and no change to `live_flux_cond`, and it leaves the
  count DRF's shared boundary tail (hence its `nfeat` and line M's pinned count artifact) untouched.
- `scripts/diagnose_copula_cond_ceiling.py` gains `ENV_SETS`, ranking compact candidate covariate subsets by
  what they add over the current conditioning — because adding all 28 environmental columns would grow `Xc`
  from 12.6 GB to ~57 GB and push `mtry = round(sqrt(p))` from 3-of-8 to 6-of-36, diluting the informative
  columns among correlated climate ones.

### Fixed

- **The distributional forest was not using its own estimator.** `predict_quantile` concatenated every tree's
  leaf values and took an unweighted quantile, giving each stored value weight `1/sum_t |L_t(x)|` — so a tree
  contributed in proportion to how large its leaf happened to be, instead of the `1/T` a quantile-regression
  forest prescribes. The two coincide only for equal leaf sizes, and the production global copula is far from
  that: over the Wooddens marginal's 70 854 leaves, sizes run min 20 / median 26 / q99 371 / max 4016
  (coefficient of variation 2.01), so per query the largest of 60 leaves took **17-21 %** of the prediction
  weight against QRF's **1.7 %** — a 10-12x over-weighting. The bias has a direction: a large leaf is one
  that stopped splitting early, so it spans a wide region of conditioning space and its values approximate
  the global marginal, meaning the error systematically drags each cell's conditional toward that marginal.
  That is an attenuation mechanism, and it explains why adding trees did not improve per-cell dispersion.
  Verified as a weighting effect and not the accompanying quantile-convention change: measured separately on
  the production artifact, the convention accounts for 0.002-0.014 % and the weighting for 1.67-4.43 %, a
  315-1507x ratio. `DRF.predict` was already correct (it averages leaf means at `1/T`), so the count DRF and
  every count skill number are unaffected.
