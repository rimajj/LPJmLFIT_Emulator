### Documentation

- **New work line X — project direction & exploration** (`line/X`, worktree `wt-X`, ADR block 0310–0329,
  tier-2 0330–0349 reserved). Created 2026-08-19 on owner instruction, because an architecture-level question
  has no owner among the four component lines: each is mid-ladder on one subsystem and would have to either act
  on such a question (not their call) or drop it. Line X explores directions, holds owner conversations about
  direction, and records them — **it never implements, and it never writes into another line's `STATE.md`,
  `MEMORY.md` or `EXECUTION_PLAN.md`.** Charter, owned paths and its four self-deception traps:
  `lines/X/STATE.md`. The SessionStart hook needed no code change (it is generic over `line/*`); only its
  integrator-worktree hint list gained `wt-X`.

### Verdict

- **A purely data-driven (non-hybrid) emulator is SIX problems with six answers, not one** (ADR 0310,
  **exploratory — no decision, awaiting the owner**). Daily water+carbon: data exist (~1 TB, both scenarios),
  learnability untested. Daily **energy: impossible from this oracle, permanently** — of 421 output slots only
  monthly `ALBEDO`/`SOILTEMP` are energy-adjacent, so sensible heat, net radiation and skin temperature have no
  training target at any data volume. The one-year-ahead operator is already built and **96 % of its skill is
  the persistence null** (0.9824 vs 0.9622). The century rollout is stable, but every reason given for that
  stability was a piecewise-constant-forest artifact, and **rollout training has never been run in this repo**.
  **The warming response is not demonstrated and zero positive evidence exists.** Speed fits the strict
  convention with 4× margin.

### Measured

- **A purely-learned emulator costs ≈0.0032 core-s/cell-year at fp64** (daily head w256/L3, batch ≥ 256, 365
  calls = 0.00314; shared-trunk annual head = 0.00004), single core, Zen-4, measured on a compute node — inside
  the 0.0135 convention with 4× margin. ⚠ The pessimistic corner (fp64, w512/L4, tanh, **batch-1**, the repo's
  single-output forests as the annual head) is **≈0.055 and fails both conventions**, so batching over land
  columns and a shared-trunk annual head are load-bearing, not optional. fp32 would halve it but **cannot meet
  guardrail 2** (water closure ~1e-12, energy ~1e-14, against fp32 eps 1.2e-7).
- **The real speed case is the patch tax, not the raw ratio:** certifying 54 020 cells individually needs
  ~125–192 patches ⇒ the C at acceptance grade is ~1.8–2.7 core-s/cell-year, while a learned operator
  predicting the ensemble expectation pays no patch tax at all.
- **Deeper history buys 0.00024 of variance** for next-year per-patch stem count (lag1 0.97597 → +climate
  0.97600 → +lag2 0.97613 → +lag3 0.97621; 4 220 878 rows) ⇒ the ~2.4 % surviving lag-1 is the C's own
  Bernoulli realisation noise, the ceiling is a **variance** ceiling, the correct target is the ensemble
  expectation, and **single-draw R² cannot discriminate arms.** This also narrows "the observed state is not
  Markov" to the trait-axis selection covariance — it is not true of count predictability.
- **A third forcing leg exists and was recorded nowhere: ssp126, both seeds, complete 2026-08-18** (591 GB,
  ADR-0041-correct second-spin-up protocol, `ind_2020_2100.csv` 186 299 086 970 B vs 186 123 571 505 B so not
  the clone failure). It warms tree cells **0.227×** as much as ssp370 on a common pre-2020 baseline (+0.783 K
  vs +3.440 K), its per-cell pattern correlates only **0.19–0.22** with ssp370's and **15–26 % of scored cells
  cool** ⇒ **useless per cell, but an excellent held-out test a memorised warming pattern must fail.** ⚠ Built
  with an `Aug 12 2026` binary against `Feb 5 2026` for the historic and ssp370-seed1 legs — gate the
  provenance before using it for a response.
- **A 1000-step global state trajectory exists for both seeds:** `vegc_spinup_1999.nc` =
  `VegC(time=1000, lat=280, lon=720)` gC/m² — refuting an "80-step hard cap on rollout depth" for the
  aggregate carbon state.
- **The per-individual bad-growth-years counter IS emitted per stem** in the rung-2 roster dumps, alongside all
  four hazard components, every per-stem pool, the seedbank fields and root-zone water ⇒ the "unobservable"
  claim narrows to the 29-column global `ind` table only, and ADR 0093 §4.4's refutation of the trait-density
  family becomes **testable rather than assumed**.

### Verified

- **Five numbers were killed by adversarial review before reaching the owner** (all six investigations in the
  14-agent workflow were refuted): a speed figure timed on arrays that had overflowed to `inf` (0.001364 →
  0.00149); a "210× faster than the C" comparison rigged against a 25-patch configuration nobody runs for
  fluxes (the unlearned C **at 1–3 patches already meets the conventions**); a "needs 0.12 % level accuracy /
  cross-leg error correlation ≥ 0.99985" bar computed on an **area-weighted global aggregate that appears in no
  acceptance criterion** (on the per-cell basis: 1.86 % and ρ ≥ 0.965); `rho_within_chain = 0.088` misread as a
  cross-leg error correlation, when ssp370 **continues** the historical chain from `restart_2019` so it is an
  80-year within-chain memory decay of the C's own noise; and the response-recovery headline, which fell to a
  null nobody had run.
- **The null that was missing: a pure lat/lon geographic address (unit-sphere x/y/z, no climate) scores 0.654
  of the 0.748 attributed to learned climate response**, and under spatially blocked 15°×5° folds everything
  collapses (full 0.549, geographic 0.353, warming-increment-only 0.093). ⇒ **any per-cell response score under
  hash/random folds is a spatial-interpolation score until this null is reported beside it.**
- **The recorded near-zero warming response is diagnosed, not explained away.** Causes: the target was 96 %
  determined by the previous year before climate was consulted (3.77 % of variance left); the response it had
  was inherited from the stand (through-origin slope 0.994) not read from climate (0.016) or flux (0.037); the
  rollout arm recursed **1 of 15** features and was trained one-step then merely inferred recursively; the
  trait head carries no roster state at all. ⚠ But the one remedy actually tested recovered only **13.5 %** of
  the gap, so "predominantly an artifact" is **over-claimed** — the defensible statement is that the causes are
  identified and mundane, the standard remedies are untried, and the one tested closed about a seventh.
- **The effective independent spatial sample is ~161 populated 15°×15° tiles**, not 54 020 cells; row counts
  overstate independent spatial evidence by ~4 orders of magnitude. Space-for-time is viable in interpolation
  (spatial temperature sd 12.73 K = 3.94× the mean warming; 95.1 % of cells' 2090s temperature inside today's
  range) but **4.9 % of cells exceed the hottest tree-bearing cell that exists today.**

### Notes

- **Nothing from ADR 0310 was propagated** — no line's `STATE.md`, no `MEMORY.md`, no `EXECUTION_PLAN.md`, no
  `src/**` change, no flag, no artifact — on the owner's explicit instruction. The three measured
  previously-unrecorded facts above live in ADR 0310 §7 only; promoting them is an owner decision.
- **Two structural additions nobody had priced**, recorded for whenever the direction is reopened: a
  **permutation-equivariant set/graph network over the per-stem roster** (purely learned yet keeps the
  individuals ⇒ **2.55e9 paired per-stem labels** instead of 1.2e8 cell-year rows, the only candidate that
  survives ADR 0093 §4.4, and no patch tax), and a **stochastic** transition head (binomial-survival +
  Poisson-birth, conservative by construction) — because rectification, measured as reproducing 86.7 % of a
  large stem decline against 96.2 % of a large increase, is the *definitional* failure mode of a self-fed
  conditional-mean regressor.
- **Literature this repo had never cited**, all directly on point: Integral Projection Models / Usher
  size-class transition matrices (the canonical purely-statistical form of exactly this question, whose
  latent-frailty variants already answer the hidden-state objection); the published LPJ-GUESS ML emulator
  (GMD 18, 4317, 2025 — 97 % runtime saving, a neural net extrapolating better than a random forest to 2100,
  but on grid-cell carbon and silent on counts and traits); Rammer & Seidl's SVD emulating iLand over 500 years
  (the only century-scale autoregressive vegetation-state precedent, which bought stability by discretising to
  1 418 categorical classes and sampling from predicted probabilities); and the agent-based-model surrogate
  literature, whose central lesson is that a surrogate fit to observed trajectories can be accurate yet wrong
  under a changed forcing. **No published DGVM emulator reproduces trait or size distributions at all.**
- **ADR 0310 §10 records five open investigator-vs-reviewer disagreements** — neither side of any of them
  should be quoted as fact, in particular whether the measured −0.226 response inversion bounds a closed
  rollout from below or from above (it changes the prior on the whole question).
