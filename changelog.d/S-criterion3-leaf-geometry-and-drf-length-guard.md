### Fixed

- **Component S / DRF: a wrong-length conditioning row was an out-of-bounds heap read, not an error.**
  `DRF._leaf` reads `x[f]` inside an `@inbounds` block, so querying an `nfeat`-feature forest with a shorter
  row returned whatever bytes followed `x` and produced a plausible in-range trait. `predict` and
  `predict_quantile` now check the length, and `DRF.load_copula` fails fast when any marginal's `nfeat`,
  `length(cond_cols)` or `length(x)` disagrees with the header's `ncond` — the only enforcement of the
  ADR-0023 train/inference contract once a copula's conditioning width changes. Byte-identical for every
  correctly-sized call: the committed Hainich fixture's golden draws are unchanged.
- **Component S: the extended-conditioning env tail selected ZERO cells for SSP370.** `cell_year_feats` is a
  historic climatology table (Year 2000–2019) that the static boundary reads whole for every scenario, but the
  env branch filtered `Year >= FIRSTYEAR[scenario]` — 67 420 cells for `historic`, **0** for `ssp370`, which
  then failed downstream with a message blaming a coverage hole. Both `build_slow_runtime_table.py` and the
  new augment script now use the boundary's basis, verified byte-identical for `historic`.
- **Component S: the capacity harness aborted before submitting when its source table held no predictions.**
  Its clobber-guard fingerprint ran `ls pred_*.f64`, which exits non-zero on an empty match and, under
  `set -o pipefail`, killed `diagnose_copula_capacity.sh` before `sbatch`.

### Added

- **Component S: the ADR-0030 gate's criterion 3 is now actually measured.** The criterion is *pooled KS*, but
  the copula evaluator prints `nqrmse` and the noise-floor gate prints neither, so every capacity rung had been
  scored without it. `scripts/score_slow_copula_ks.py` reports pooled KS, median per-cell KS, `nqrmse` and
  median relative quantile error per axis on one row universe, importing the same `ks2` that produced the
  published `metrics_traits.txt` numbers. The two statistics are not interchangeable — they disagree by ~55×
  in magnitude (`agb`: `nqrmse` 0.6432 vs KS 0.0116) and in *direction* — and on the corrected statistic the
  `b6x2M` capacity rung **improves the pooled marginal on all four trait axes**, reversing the verdict
  recorded in ADR 0037.
- **Component S: per-rung leaf geometry.** `eval_slow_copula.jl` now prints leaves per tree, the leaf-size
  distribution, the share of stored values sitting at `depth == max_depth`, and the size-biased expected draw
  pool. Measured on the `t8` artifact, 99.9–100 % of leaves holding at least `2·min_leaf` values sit exactly at
  `max_depth` and 57–67 % of all stored values are in one — so the marginal forests are truncated by the depth
  budget, and `max_depth` is a lever that costs no artifact bytes while `subsample` scales them linearly.
- **Component S: `scripts/build_slow_copula_env_augment.py`** derives an extended-conditioning copula table by
  appending the per-cell env tail to an existing table's `Xc` rather than rebuilding from the `ind` parquet, so
  a conditioning experiment cannot be confounded by the polars-streaming key-set non-determinism of ADR 0036
  §5b. Verified bitwise-identical on the inherited columns across all 197 721 867 rows.
