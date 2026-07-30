### Added

- **Two probes that decompose the Component-S recruit-trait GAP before any conditioning change is written**
  (milestone S2). `scripts/diagnose_copula_cond_ceiling.py` splits the ADR-0030 per-cell trait GAP into
  *estimator inefficiency* vs *new-covariate headroom* by fitting a direct per-cell regressor (K-fold by cell)
  on the current conditioning versus a wider environmental set; it validates itself against the documented
  `emu_r`/`floor_r`/`sd_ratio` first and stops if they disagree. `scripts/diagnose_copula_capacity.sh` re-runs
  the K-fold-by-cell OOS evaluation at a chosen estimator capacity on an **unchanged** table — via a shadow
  directory of input-only symlinks, so a re-evaluation can never overwrite a validated generation's
  `pred_<axis>.f64` — and scores the ADR-0030 gate, measuring capacity in isolation from any conditioning
  change.

### Changed

- **Milestone S2 is re-scoped on measurement: the trait GAP is dominated by ESTIMATOR CAPACITY, not by a
  missing covariate.** On `t8` historic (52 165 cells) the estimator share of the GAP is
  +0.080/+0.102/+0.089/+0.032 (SLA/Wooddens/D95max/minwscal) against a new-covariate share of
  +0.011/+0.025/+0.042/+0.004. Wooddens reaches `r` 0.916 and `sd_ratio` 0.896 from the *existing* eight
  conditioning columns — both already past the S2 gate targets (0.889 / 0.75). Mechanism, measured on the
  production artifact: `SUBSAMPLE=50000` against ~158M training rows yields **1063 leaves per tree for 54 020
  cells**, so each leaf hands ~51 cells one identical conditional distribution, and `DRF.predict_quantile`
  pools leaf values across trees into a mixture that reproduces the global marginal (pooled `nqrmse` 0.013,
  KS 0.0065) while leaving the per-cell conditional under-resolved (`sd(pred)/sd(Y1)` 0.678, slope
  `Y1~pred` 1.20). Pooled-marginal metrics are structurally blind to this. The conditioning expansion remains
  a real but secondary, separately-attributable follow-up, because the boundary tail carries no moisture or
  precipitation climatology while FIT's establishment gates are temperature *and* moisture.

### Fixed

- `scripts/diagnose_copula_capacity.sh`'s artifact-clobber guard was locale-sensitive: it hashed
  `ls pred_*.f64 | sort`, and the login node collates in `en_US.UTF-8` (case-insensitive) while the SLURM
  batch shell collates in `C`, so the same untouched files hashed differently and the guard reported a false
  "the shadow leaked". Both sides now force `LC_ALL=C`, and the failure path prints the name/size/mtime
  triples so a real incident is distinguishable from a guard artefact.
