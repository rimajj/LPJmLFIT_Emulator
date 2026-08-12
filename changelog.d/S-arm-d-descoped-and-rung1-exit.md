### Changed

- **Rung 1 of the error-attribution ladder is CLOSED, with the two-part score and the compensating-errors
  verdict its exit gate asks for
  ([ADR 0174](docs/decisions/0174-rung-1-exit-the-compensating-errors-verdict.md)).** The gate reads *"rung-1
  score reported against the rung-0 noise floor, with the compensating-errors verdict stated"* and the second
  clause had no answer anywhere in the repo; ten ADRs each held a piece. No new computation. **LEVEL: passes
  by a margin** — the free-running count level's bias never exceeds +0.16 stems/patch on a mean of 8.28
  (< 2 %) against the C's own two-run floor of 6.77 % over all cells and 16.63 % in the `<2 stems/patch`
  stratum, and the deattenuated trait slopes are SLA 1.28 / Wooddens 0.66 / D95max 0.73 / minwscal 1.06.
  **RESPONSE: fails, on sign not magnitude** — the area-weighted count response ratio is +0.707 one-step and
  **−0.226 free-running**, with a measured validity horizon of ~3 years. The two verdicts concern different
  mechanisms and must not be averaged, so every rung-1 number now carries two labels: *level or response* and
  *one-step or free-running*. **The compensating-errors verdict is YES, with three named and sized channels:**
  teacher forcing (a null copying LPJmL-FIT's own previous-year count matches or beats the production model on
  every response statistic); a rectified loss-side error (86.7 % of a large decline followed vs 96.2 % of a
  large increase, which against a net-loss global response rectifies into +0.155 stems/patch — the same size
  as FIT's entire global count response, so the component passes its level gate *because of* the error that
  fails its response gate); and a survivor-trained recruit marginal that already contains the selection an
  added mortality operator would supply. Four things are now forbidden by name (a count-level anchor, a
  variance-preserving count predictor, arm D, and the offline pure-inheritance arm), each with the measurement
  that must be refuted first.

- **Rung-1 arm D is DESCOPED — its motivating "bounded Beta beats the copula 2–3×" was three confounds, not a
  distribution family ([ADR 0173](docs/decisions/0173-arm-d-the-beta-advantage-was-three-confounds-not-a-family.md)).**
  ADR 0118 asked for the comparison to be re-established like-for-like before arm D ran; it now is, and the
  claim does not survive. `scripts/score_beta_vs_copula_likeforlike.py` reproduces ADR 0093 §5.3's number on
  its own basis under a hard gate, then prices each confound: the two sides were **not the same statistic**
  (a one-sample KS against a Beta fitted to that sample's own moments, per cell-and-PFT on the densest 400
  cells per PFT, versus a two-sample out-of-sample KS per cell with the PFTs mixed). The estimator alone costs
  1.7–2.4×, the grouping a further 1.2–1.5×, and the published Beta number sits **at its own statistic's noise
  floor** (0.0437–0.0476 against a simulated 0.0434–0.0475 at n = 150). Like for like, the Beta given each
  test cell's **own observed** moments ties the **out-of-sample** copula on two axes and is **7–12 % worse**
  on the other two. Both sit only 1.1–1.5× above the split-half floor of their grouping, so neither family is
  the binding constraint on that score. And the **deployable** arm settles it from the other direction: a Beta
  carrying the *same learned two moments*, off the same forests, leaf pool and uniform as the copula, is worse
  on **all four axes** — median per-cell KS +36 % / +9 % / +13 % / +28 %, pooled KS **6.5–16.6× worse**, every
  axis failing the `≤ 0.02` criterion the copula passes. The run's own control reproduces the published panel
  **to the digit** (median per-cell KS 0.1725 / 0.1287 / 0.1575 / 0.1487, pooled 0.0039 / 0.0065 / 0.0020 /
  0.0040), so both arms sit on exactly the published basis.

### Added

- **`scripts/eval_slow_beta_arm.jl` — three marginal arms from ONE set of forests, with the invariant enforced
  rather than asserted.** It re-runs the copula evaluator's own loop on the same table (same
  `mod(hash(cell), kfolds)` folds, same `fit_forest(...; seed = a)`, same per-row uniform) and reads the
  copula's empirical quantile, a bounded-Beta draw and the conditional **expectation** off the same leaf pool,
  so the arms differ in the marginal family and nothing else. A **fatal** gate checks the pooled reading
  against `DRF.predict_quantile` on sampled rows of every fold and axis; a **reported** gate checks this run's
  copula column against the table's stored one. Output is a shadow dir the existing
  `scripts/score_slow_copula_ks.py` scores with no new scorer and no second KS definition.

- **First measurement of the "determinism dividend"** (predict the ensemble expectation rather than draw a
  realisation — ADR 0093 §5 item 5, an EXECUTION_PLAN rung-1 deliverable that had never been run). It is free
  as a by-product of the Beta's moments. ⚠ Its published +2.9 to +14.4 percentage-point figure is on a
  **mean-based band metric**; the arm here is scored on a **distributional** per-cell KS, where a point mass
  has no dispersion, so the two framings are reported separately and the band-metric half remains open.
  Measured: the expectation arm's median per-cell KS is 3.0–3.9× the copula's (0.496–0.531) and its pooled KS
  48–158× (0.19–0.32). That is the *expected* consequence of a point mass against a distributional target, and
  what it settles is narrow but was genuinely open — the dividend cannot be read as a free win for the
  trait-distribution target; taking it would be a deliberate trade of distributional fidelity for band
  accuracy, and both sides must then be quoted.

### Fixed

- **A stored out-of-sample prediction column on a scratch copula table can be STALE with respect to today's
  evaluator, and nothing flagged it.** The stock, unmodified `scripts/eval_slow_copula.jl` no longer reproduces
  the `pred_<axis>.f64` committed in an old smoke table (all four axes differ, worst |Δ| ≈ 3.0e5 gC/m³ on wood
  density) even at that table's own fold count, while `src/drf.jl`'s default numerics are unchanged. ⚠ The
  **production** table is unaffected — the new arm's re-derived copula column is **bit-identical** to
  `slow_copula_pooled_w20_t8`'s stored one over 402 163 checked rows, which is what anchors the arm-D
  comparison to the published artifact. But building arm D the obvious way — stored column as one arm, fresh
  column as the other — would have put a code change *inside* the family comparison on any table where the
  divergence exists, with no check able to catch it.
