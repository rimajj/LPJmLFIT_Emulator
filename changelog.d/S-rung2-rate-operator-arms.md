### Added

- **The rung-2 RATE operator: FIT's own per-tree hazard with no count target at all
  ([ADR 0242](docs/decisions/0242-the-rate-operator-arm.md)).** ADR 0241 retired the learned count model
  from the mortality path — a kill budget is a difference of counts, so the count error is multiplied by
  the level-to-flux ratio, and the precision needed (1.13/1.18 % per patch-year) sits inside the
  irreducible per-stem realisation floor (4.1/4.6 %) and inside the integer atom itself. Its named
  replacement is now built as three harness arms mirroring `S0`/`S0h`/`S1`: **`H1`** hands every stem its
  own hazard (`f = 1 − mort_i`, i.e. `TraitMortality.survival_prob`, the Bernoulli LPJmL-FIT itself
  realizes), **`H0`** draws uniformly at the nind-weighted mean hazard, and **`H0h`** honours the certain
  deaths and thins the rest uniformly — identical expected removal on a given roster, so `H1 − H0h − H0`
  decomposes what per-stem ordering is worth once the RATE is right. No target, no budget, no account,
  and no `ρ < 1` gate (that gate is part of the count-budget architecture and left 42–46 % of `S*`
  patch-years with an empty kill list). **Guardrail 4 measured, not asserted:** `S1` re-run under the new
  code is byte-identical over all 27 pre-existing arm-log columns (500 patch-years) and identical in every
  initialised dump column (40 569 records). **The derivable a-priori gate is new and exact**
  (`scripts/diagnose_rung2_rate_flux_identity.py`): the harness now logs `haz_exp` (FIT's own expected
  removal on that roster), `kill_nind` (realized), and `kill_exp`/`kill_var` (the arm's own implied mean
  and the exact variance of its draw), so the expected-flux identity is checkable row by row (smoke: max
  |diff| 2.4e-17 over 3 525 patch-years) and the realized-vs-implied test carries a **derived** sampling
  SE for **every** arm — ADR 0188's `1.004 ± 0.009` had to hand-roll one from a uniform-draw assumption
  only `S0` meets. The same columns give ADR 0187's rate shortfall from the log with no dump scan: at
  Hainich historic `S1` delivers **0.68** of the mortality its own stand was asking for. Rate arms log
  `rho_eff` as **NaN**, not 1.0, because no thinning ratio is formed. In rung 2 the hazard reads FIT's own
  stress integrals through the rendezvous, so these arms measure a **ceiling** — what an exact hazard buys
  — and do not by themselves close the standalone emulator (ADR 0049 item 4).

- **The rate operator MEETS the criterion, and the per-stem mass excess is gone
  ([ADR 0242](docs/decisions/0242-the-rate-operator-arm.md) §5).** 360-leg campaign, 351 complete (the
  9 losses are the known open C-side duplicate-roster-key fault). On the warming leg at the cells where
  the original model gains stems: the stand holds **+4.4 %** of the original's stem count and **+4.1 %**
  of its biomass, against a pre-registered 40 % tolerance on both — and the per-stem mass departure,
  which five earlier decision records chased (+96 % for the shipped operator, +269 % for the
  gross-budget one), is **−0.3 %**. It removes **2.2 %** of stems a year discretionarily against the
  original's own 2.1, nominates **5.961 %/yr against the original's own gross 5.961**, and its stand is
  stationary over 81 free-running years (roster 1.000×) where the shipped operator climbed
  monotonically to +91 % biomass. Its per-height-quintile mortality rate now has the original's shape
  **at the original's level** in all five bins. The warming response's error falls **4.9×** below a
  do-nothing null and **4.5×** below the shipped operator (RMSE 1.12 stems vs 5.45 and 5.00, slope 1.150
  vs 2.320 and 1.797) — ⚠ the correlation coefficient does **not** discriminate here, the null scores
  0.917, and the null was computed before the arms were read. **The decomposition inverts what the rate
  alone is worth:** spending the original's own mortality flux on the wrong stems annihilates the
  above-5 m stand (−98.5 % count, −99.6 % biomass) while a whole-roster count still reads 0.971×,
  because the stand converts to saplings — so at the full flux WHICH trees die is decisive, refining
  (not contradicting) the earlier finding that the kill set was unbiased at a 4× lower rate. ⚠ **This is
  a CEILING, not a fidelity result**: in this harness the hazard reads the original model's own stress
  integrals through the rendezvous, so agreement is expected; what is new is that the count-budget
  architecture was the whole of the mortality defect and that nothing else in the loop prevents ~5 %
  agreement over 81 free-running years. No `src/**` change and no flag flipped. ⚠ Method: a
  self-normalized martingale pooled over a feedback trajectory is **not** a standard normal — the gate's
  pre-registered |z| clause came out at 4.47, a frozen-roster replay reproduced the logged kills at
  2025 of 2025 patch-years and put 400 redraws at −0.06 % (z −0.83), so the draw is unbiased and the
  statistic was biased; the clause is kept, printed and reported as failing, with the ratio carrying the
  gate (`scripts/diagnose_rung2_rate_draw_replay.jl`).
