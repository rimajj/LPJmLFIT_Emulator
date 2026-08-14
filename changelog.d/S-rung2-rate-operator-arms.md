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
