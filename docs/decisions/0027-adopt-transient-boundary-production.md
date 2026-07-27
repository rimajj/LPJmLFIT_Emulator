---
status: "accepted"
date: 2026-07-27
deciders: "Jamir Priesner (owner) — chose the transient boundary after reviewing the ablation + cost/interaction analysis; engineering agent recorded the decision"
consulted: "ADR 0026 (the transient-boundary + pooled-multi-regime decision this validates, incl. its §5 falsifiable test), ADR 0020 (flux-driven S — F carries the fast climate signal), ADR 0004 (constant CO2), ADR 0025 (recruit copula); the global hold-out-by-scenario ablations — scripts/eval_slow_scenario_holdout.jl (count) + scripts/eval_slow_copula_scenario_holdout.jl (traits), run on BOTH the transient- and static-boundary pooled tables (jobs 1600416/1600458/1600703)"
informed: "the production global artifacts (drf_forest_global_pooled_w20.drf, recruit_copula_global_pooled_w20.rcop); scripts/run_pooled_slow_{training,copula}.sh (BOUNDARY_WINDOW=20); the online-coupling Climbuf (to build); MEMORY.md; JOURNAL.md; CHANGELOG.md; the slow-drf-pipeline + emulator-validation-figures skills"
---

# Adopt the TRANSIENT boundary as the production configuration for the pooled multi-regime flux-driven emulator (records the ADR 0026 §5 validation outcome)

> **Status note.** `accepted` 2026-07-27. Records the **validation OUTCOME** of ADR 0026 and the owner's
> resulting decision. ADR 0026 §5 pre-registered a falsifiable test (*the transient-boundary model must beat
> a static-boundary model on a held-out regime, "or this decision is falsified and must be revisited"*). The
> honest outcome is a **wash** — so the metric does not decide it, and the choice falls to physical correctness
> vs. cost. The owner chose the transient boundary. Does **not** supersede ADR 0026 (whose opt-in/default-off
> code mechanism stands); it blesses transient as the **production** configuration and records why.

## Context

ADR 0026 built a TRANSIENT (trailing-climatology) bioclimatic boundary and a POOLED multi-regime training
path, then this session validated both at global scale with **hold-out-by-scenario** ablations (train on one
climate regime, test the completely held-out other), run on BOTH the transient- and static-boundary pooled
tables so the static-vs-transient delta isolates the boundary's empirical contribution.

## What the ablations found

- **The pooled multi-regime, flux-driven generalization is STRONG — the real win.** One model trained on one
  regime reproduces the UNSEEN regime: **count held-out-by-scenario R² = 0.9847** (both directions, ≈ the
  within-regime by-cell R² 0.9852); **copula trait marginals held-out-by-scenario KS ≤ 0.05 / nqrmse ≤ 0.09**
  per axis. Present-climate training reproduces the strongly-warmed SSP370 future, and vice versa.
- **Transient vs. static is a WASH, mixed by axis.** Counts: transient R² 0.9847 vs static 0.9844/0.9848
  (tie). Traits (copula scenario-holdout, avg both directions, KS): SLA 0.049 vs 0.028 (static better),
  Wooddens 0.008 vs 0.020 (transient better), D95max 0.012 vs 0.019 (transient better), minwscal 0.026 vs
  0.012 (static better) — no consistent winner, all excellent.
- **Cost is NOT the differentiator.** Offline: transient data-gen is ~1 min/scenario (`build_transient_boundary.py`,
  temperature `.clm` only) and runtime is one vector assignment/year. Online: the transient boundary needs a
  trailing climate buffer (Climbuf) recomputing gdd5/tas_cold from the climate F already consumes — a few
  thousand FLOPs/cell/year against F's millions/cell/year daily core, i.e. ~0% slower; the cost is a small
  amount of CODE, which is the *faithful* implementation (LPJmL-FIT itself uses a ~20-yr Climbuf).
- **Why the wash (confirms ADR 0020, and the F↔boundary interaction).** The boundary does not feed F; it
  CONDITIONS S. F turns the changing climate into changing FLUXES (bm_inc/growth_eff/water_stress/soilmoist),
  so S already sees the regime shift THROUGH F regardless of the boundary. The boundary supplies only the
  *slow* bioclimatic memory (gdd5/tas_cold gating establishment) that this-year fluxes cannot carry — a
  secondary, residual signal in this constant-CO2, flux-driven design. Static "works" online precisely because
  F compensates; the frozen gate is a knowingly-wrong approximation the flux channel happens to mask.

## Decision

1. **The POOLED MULTI-REGIME FLUX-DRIVEN emulator is the production design** (ADR 0026 §4 + ADR 0020) — ONE
   environment-conditioned model across scenarios, not one per scenario. Confirmed by the R²/KS above.
2. **Adopt the TRANSIENT boundary as the production boundary configuration.** On a genuine wash at negligible
   cost, **physical correctness breaks the tie**: a frozen establishment gate is wrong-by-construction under
   +80 yr of warming, whatever the metric says; the transient boundary matches FIT's Climbuf and is robust in
   the regimes the flux channel cannot compensate (a hard establishment threshold-crossing; the excluded
   N-limited / rising-CO2 futures). The production global artifacts are trained with `BOUNDARY_WINDOW=20`
   (`drf_forest_global_pooled_w20.drf`, `recruit_copula_global_pooled_w20.rcop`; `run_pooled_slow_*.sh`).
3. **The code-level opt-in mechanism stays (guardrail 4).** `boundary_series = nothing` / `BOUNDARY_WINDOW`
   unset remains the CODE default so committed baselines, the AD trainer, and the Hainich demo fixture stay
   byte-identical — a plumbing choice orthogonal to the physics decision. "Production uses transient" ≠ "the
   code default flips." The static path is the documented fallback (when the transient data-gen is unavailable).
4. **Report it honestly.** Write-ups state that in this design the flux channel carries the unseen-regime
   generalization and the transient boundary is adopted for physical correctness + faithfulness, a wash on the
   measured metrics — not a demonstrated metric win.

## Consequences

- **Good.** The production design is empirically validated by an honest, pre-registered, falsifiable test, and
  ships the physically-correct boundary at ~zero runtime cost. Faithful to LPJmL-FIT's Climbuf; robust to the
  excluded regimes.
- **To build.** The ONLINE-coupling Climbuf (trailing climate buffer fed by F's climate) — the only remaining
  transient-boundary implementation; negligibly slow, moderate code, and the faithful path. Offline uses the
  pre-baked per-(cell,year) series.
- **Open caveat (follow-on diagnosis).** Transient notably WORSENS SLA + minwscal per-cell KS (0.049 vs 0.028;
  0.026 vs 0.012) while improving Wooddens + D95max — consistent with a mostly-uninformative time-varying
  feature adding noise on axes it doesn't govern. Worth a quick diagnosis (is it noise, or a feature
  interaction?) before treating transient as strictly dominant; it does not change the adopt decision.

## Relationship to prior ADRs

- **Records the validation outcome of ADR 0026 §5** and executes its "must be revisited" clause. Does not
  supersede ADR 0026 — its opt-in/default-off mechanism stands; this fixes the production configuration + the
  claim.
- **Confirms ADR 0020** (flux-driven S): F carries the regime signal (counts + traits, unseen-regime); the
  boundary is the slow-memory residual.
- **Uses ADR 0004** (constant CO2): the wash is scoped to the constant-CO2 regime; a varying-CO2 / N-limited
  future is where the transient boundary should earn a measured win.

ADRs are immutable once accepted — supersede rather than edit.
