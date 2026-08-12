### Added

- **The recruit-channel response arm now spans FIVE biome cells, and the sign instability is systematic
  rather than a three-cell accident ([ADR 0172](docs/decisions/0172-the-recruit-response-sign-is-unstable-within-one-eligibility-regime.md)).**
  Two further 40-seed ensembles (`semiarid_sahel`, `mediterranean_iberia`; jobs 1762007–1762088, 80/80 usable
  with zero hard kills, count overrides or k-cap merges) extend ADR 0171's cross-cell table. The **LEVEL**
  effect survives everywhere — the ported establishment rule raises the standing community's mean wood
  density at all five cells, +19 349 to +30 251 gC/m³ at t = 6.1–7.9, i.e. 8–12× FIT's entire warming shift
  as a static offset — so `recruit_establishment` stays **OFF** and the reason is now five cells. The
  **RESPONSE** contribution does not: −0.89 / +1.98 / −1.91 / −1.67 / +3.56 ×FIT, and the three cells that
  share the *same* eligibility regime (`n_elig = 4`, the modal 49 % of tree-bearing cells) **disagree beyond
  seed noise** — Cochran's Q = 8.03, df 2, **p = 0.018**, I² = 75 %, with two of three pairs separating on a
  Welch test. Meanwhile the *shipped* channel's own response shows **no** heterogeneity across those same
  three cells (Q = 0.51, p = 0.77, I² = 0 %). ⇒ ADR 0171 §5's pre-registered "one cell per eligibility
  regime, sign must agree" condition is retired: it groups on a variable that does not organise the effect.
  Its replacement requires ≥ 12 named cells, a weighted mean in [0.9, 1.1] ×FIT **and** a non-significant Q,
  so that disagreeing cells cannot pool to the right answer by cancellation.
  Per-seed rows: `test/testitems/references/S_recruit_multicell_seed_ensembles.csv` (7 ensembles, 280 rows).

- **`scripts/split_estab_eligibility_percell.py` and `scripts/append_response_ensemble_reference.py` — the
  two hand steps in the cross-cell recipe are scripts now.** The first splits a multi-cell
  `build_estab_eligibility.py` CSV into the per-site fixtures the response probe reads, preserving the header
  and the load-bearing row order; it is gated by reproducing both of ADR 0171's hand-split fixtures
  **byte-identically**. The second prefixes the run identity onto the seed rows and appends them to the
  committed cross-cell reference, refusing a duplicate tag and cross-checking the logs' own `n_init`/`age0`
  and artifact against that site's `M_cells.csv` row.

- **`scripts/build_estab_regime_table.py` — the reproducer ADR 0171 §4's regime table never had, which
  found that the table means something different from what it says
  ([ADR 0172](docs/decisions/0172-the-recruit-response-sign-is-unstable-within-one-eligibility-regime.md)).**
  The published header reads "(2010, `Type <= 6`)", but the classification is the **minimum over the 20
  historic years**, so its `n_elig = 0` class means *"the gate is closed in at least one of 20 years"*, not
  *"this cell is in the pure-inheritance regime"*. On the ADR's own cell universe (52 451, reproduced
  exactly): min-over-window puts 5 882 cells / 11.21 % / 29 median stems in class 0 — the published row, now
  gated — while the single-year snapshot puts 1 931 / 3.7 % there and only **739 cells / 1.4 %** of the
  runnable set are closed in all 20 years, at a median of 1 stem per patch. The committed fixture
  `test/testitems/references/S_estab_regime_table.csv` carries both classifications and both cell bases side
  by side, plus a persistence section.

- **Arm D — the bounded-Beta-vs-copula comparison, re-established like-for-like
  ([ADR 0173](docs/decisions/0173-arm-d-the-beta-advantage-was-three-confounds-not-a-family.md)).**
  `scripts/score_beta_vs_copula_likeforlike.py` prices each confound folded into ADR 0093 §5.3's "2–3×"
  (estimator, grouping, information) on one row universe with the repo's one `ks2`, gated on reproducing the
  published Beta number on its own basis; `scripts/eval_slow_beta_arm.jl` then answers the deployable
  question by deriving the copula's empirical quantile and a bounded Beta from the **same** fitted forest,
  the same leaf pool and the same uniform, so the two arms differ in the marginal family and nothing else —
  checked, not asserted, by a fatal gate against `DRF.predict_quantile`.

### Fixed

- **`scripts/build_hainich_response_forcing.py` and the eligibility builder now cover all five provisioned
  biome cells.** `SITE=semiarid_sahel` and `SITE=mediterranean_iberia` produce their committed transient
  boundary and per-cell(-year) eligible-PFT series; both cells pass the historic and ssp370 boundary gates
  against the trained global table at **worst |diff| = 0** and the daily-forcing fixture gate at ≤ 1.8e-05.
